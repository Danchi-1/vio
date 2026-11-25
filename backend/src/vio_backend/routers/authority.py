"""Authority router for delivery access, acknowledgement, responses, and escalation (M6).

Enforces:
- One-time link token redemption (no token reuse, strictly expiring).
- HMAC-signed authority session tokens binding subsequent actions to (authority_id, delivery_id).
- Authenticated acknowledgement, response, and appeal endpoints (no bare UUID submissions).
- Protected escalation worker endpoint via worker secret.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import delivery_store
from vio_backend.config import Settings
from vio_backend.database import session_dependency
from vio_backend.errors import ApiError
from vio_backend.link_auth import (
    AuthoritySession,
    create_authority_session_token,
    get_current_authority,
    require_worker_auth,
)

router = APIRouter(prefix="/api/v1/authority", tags=["authority"])


class RedeemTokenRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class AuthorityResponseRequest(BaseModel):
    outcome: str = Field(description="action_taken, explanation_accepted, disputed, no_action")
    body: str = Field(min_length=1, max_length=4000)


class AuthorityAppealRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.post("/access")
async def redeem_access_token(
    request: Request,
    response: Response,
    body: RedeemTokenRequest,
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    """Redeems a secure, one-time delivery link token and sets a restricted session."""
    delivery_data, error_code = await delivery_store.redeem_delivery_token(session, body.token)
    if error_code == "expired_link":
        raise ApiError(410, "expired_link", "This access link has expired.")
    if error_code == "link_already_used":
        raise ApiError(409, "link_already_used", "This access link has already been used.")
    if delivery_data is None:
        raise ApiError(404, "not_found", "The access link is invalid.")

    await session.commit()

    settings: Settings = request.app.state.settings
    secret = settings.authority_session_secret or settings.session_secret or "insecure-dev-authority-secret"

    delivery_id = str(delivery_data["delivery_id"])
    authority_id = str(delivery_data["authority_id"])
    role = delivery_data["authority_role"]

    session_token = create_authority_session_token(
        secret,
        authority_id=authority_id,
        delivery_id=delivery_id,
        role=role,
        ttl_hours=24,
    )

    response.set_cookie(
        key="authority_session",
        value=session_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax" if settings.cookie_samesite == "strict" else settings.cookie_samesite,
        max_age=86400,
    )

    return {
        "data": {
            "session_token": session_token,
            "delivery_id": delivery_id,
            "finding_id": str(delivery_data["finding_id"]),
            "authority_role": role,
            "authority_name": delivery_data["authority_name"],
            "step_order": delivery_data["step_order"],
            "status": delivery_data["status"],
            "due_at": delivery_data["due_at"].isoformat() if delivery_data["due_at"] else None,
            "incident": {
                "course_code": delivery_data["course_code"],
                "course_title": delivery_data["course_title"],
                "department": delivery_data["department_name"],
                "category": delivery_data["category"],
                "incident_date": delivery_data["incident_date"].isoformat() if delivery_data["incident_date"] else None,
                "public_summary": delivery_data["public_summary"],
                "clearance_tier": delivery_data["clearance_tier"],
            },
        }
    }


@router.get("/deliveries/{delivery_id}")
async def get_delivery_details(
    delivery_id: UUID,
    authority: AuthoritySession = Depends(get_current_authority),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    """Retrieves delivery details authorized for the authenticated authority session."""
    if str(delivery_id) != authority.delivery_id:
        raise ApiError(403, "forbidden", "Access to this delivery is unauthorized.")

    query = """
        SELECT d.id AS delivery_id, d.finding_id, d.authority_id, d.step_order, d.status,
               d.due_at, d.viewed_at, d.acknowledged_at, d.responded_at,
               a.role AS authority_role, a.full_name AS authority_name,
               f.category, f.incident_date, f.clearance_tier, f.public_summary,
               c.code AS course_code, c.title AS course_title,
               dept.name AS department_name
        FROM deliveries d
        JOIN authorities a ON a.id = d.authority_id
        JOIN findings f ON f.id = d.finding_id
        JOIN courses c ON c.id = f.course_id
        JOIN departments dept ON dept.id = c.department_id
        WHERE d.id = :id
    """
    res = await session.execute(text(query), {"id": str(delivery_id)})
    row = res.first()
    if row is None:
        raise ApiError(404, "not_found", "Delivery not found.")

    d = dict(row._mapping)
    return {
        "data": {
            "delivery_id": str(d["delivery_id"]),
            "finding_id": str(d["finding_id"]),
            "authority_role": d["authority_role"],
            "authority_name": d["authority_name"],
            "step_order": d["step_order"],
            "status": d["status"],
            "due_at": d["due_at"].isoformat() if d["due_at"] else None,
            "acknowledged_at": d["acknowledged_at"].isoformat() if d["acknowledged_at"] else None,
            "incident": {
                "course_code": d["course_code"],
                "course_title": d["course_title"],
                "department": d["department_name"],
                "category": d["category"],
                "incident_date": d["incident_date"].isoformat() if d["incident_date"] else None,
                "public_summary": d["public_summary"],
                "clearance_tier": d["clearance_tier"],
            },
        }
    }


@router.post("/deliveries/{delivery_id}/acknowledgement")
async def acknowledge_delivery(
    delivery_id: UUID,
    authority: AuthoritySession = Depends(get_current_authority),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    """Marks a delivery as officially acknowledged by the authenticated authority."""
    if str(delivery_id) != authority.delivery_id:
        raise ApiError(403, "forbidden", "Access to this delivery is unauthorized.")

    success = await delivery_store.acknowledge_delivery(session, str(delivery_id))
    if not success:
        raise ApiError(404, "not_found", "Delivery not found or cannot be acknowledged.")
    await session.commit()

    return {
        "data": {
            "delivery_id": str(delivery_id),
            "status": "acknowledged",
            "message": "Delivery receipt acknowledged.",
        }
    }


@router.post("/deliveries/{delivery_id}/responses")
async def submit_response(
    delivery_id: UUID,
    body: AuthorityResponseRequest,
    authority: AuthoritySession = Depends(get_current_authority),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    """Records an official outcome and explanation from the authenticated authority."""
    if str(delivery_id) != authority.delivery_id:
        raise ApiError(403, "forbidden", "Access to this delivery is unauthorized.")

    if body.outcome not in ("action_taken", "explanation_accepted", "disputed", "no_action"):
        raise ApiError(400, "invalid_request", "Invalid response outcome.")

    resp_id = await delivery_store.record_authority_response(
        session,
        delivery_id=str(delivery_id),
        outcome=body.outcome,
        body=body.body,
    )
    if resp_id is None:
        raise ApiError(404, "not_found", "Delivery not found.")
    await session.commit()

    return {
        "data": {
            "response_id": resp_id,
            "delivery_id": str(delivery_id),
            "outcome": body.outcome,
            "status": "responded",
            "message": "Authority response recorded.",
        }
    }


@router.post("/deliveries/{delivery_id}/appeals")
async def submit_appeal(
    delivery_id: UUID,
    body: AuthorityAppealRequest,
    authority: AuthoritySession = Depends(get_current_authority),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    """Files an official authority appeal on a delivery finding."""
    if str(delivery_id) != authority.delivery_id:
        raise ApiError(403, "forbidden", "Access to this delivery is unauthorized.")

    query = "SELECT finding_id FROM deliveries WHERE id = :id"
    d_res = await session.execute(text(query), {"id": str(delivery_id)})
    row = d_res.first()
    if row is None:
        raise ApiError(404, "not_found", "Delivery not found.")

    finding_id = str(row[0])
    appeal_id = await delivery_store.file_appeal(
        session,
        finding_id=finding_id,
        appellant="authority",
        appellant_id=authority.authority_id,
        body=body.body,
    )
    await session.commit()

    return {
        "data": {
            "appeal_id": appeal_id,
            "finding_id": finding_id,
            "status": "open",
            "message": "Appeal filed successfully.",
        }
    }


@router.post("/escalations/process")
async def trigger_escalation_process(
    _worker: None = Depends(require_worker_auth),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    """Protected worker endpoint to process unacknowledged overdue deliveries."""
    escalated = await delivery_store.process_overdue_escalations(session)
    await session.commit()
    return {
        "data": {
            "processed_count": len(escalated),
            "escalated_deliveries": escalated,
        }
    }
