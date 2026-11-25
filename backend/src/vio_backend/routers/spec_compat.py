"""Compatibility aliases matching VIO_HACKATHON_SPECIFICATION.md Section 8 and the frontend API client."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
import re
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import dashboard_store, report_store, student_auth
from vio_backend.config import Settings
from vio_backend.database import session_dependency
from vio_backend.errors import ApiError
from vio_backend.report_rules import is_valid_tracking_code
from vio_backend.routers import auth as auth_router
from vio_backend.routers import findings as findings_router
from vio_backend.routers import reports as reports_router
from vio_backend.security import compute_identity_hash, normalize_email

router = APIRouter(prefix="/api/v1", tags=["spec-compat"])

_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")


class SpecOtpRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class SpecOtpVerify(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=6, max_length=6)


async def _resolve_university_by_email(session: AsyncSession, email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized:
        raise ApiError(400, "invalid_request", "Use your official student school email address.")
    domain = normalized.split("@", 1)[1]
    res = await session.execute(
        text("SELECT id FROM universities WHERE lower(email_domain) = :domain LIMIT 1"),
        {"domain": domain},
    )
    row = res.first()
    if row is None:
        raise ApiError(400, "invalid_request", "Use your official student school email address.")
    return str(row[0])


@router.post("/student/auth/request-otp")
async def spec_request_otp(
    body: SpecOtpRequest,
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(auth_router.get_settings),
) -> dict:
    uni_id = await _resolve_university_by_email(session, body.email)
    return await auth_router.request_email_challenge(
        auth_router.EmailChallengeRequest(university_id=UUID(uni_id), email=body.email),
        session=session,
        settings=settings,
    )


@router.post("/student/auth/verify-otp")
async def spec_verify_otp(
    body: SpecOtpVerify,
    response: Response,
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(auth_router.get_settings),
) -> dict:
    identity_secret = auth_router._require_secret(settings.identity_hash_secret, "Identity hashing")
    uni_id = await _resolve_university_by_email(session, body.email)
    ihash = compute_identity_hash(identity_secret, normalize_email(body.email))
    res = await session.execute(
        text(
            """
            SELECT id FROM email_challenges
            WHERE university_id = :uni_id AND identity_hash = :ihash
              AND consumed_at IS NULL
            ORDER BY created_at DESC LIMIT 1
            """
        ),
        {"uni_id": uni_id, "ihash": ihash},
    )
    row = res.first()
    if row is None:
        raise ApiError(404, "not_found", "That verification code is invalid.")
    return await auth_router.verify_email_challenge(
        auth_router.EmailChallengeVerifyRequest(challenge_id=UUID(str(row[0])), code=body.code),
        response=response,
        session=session,
        settings=settings,
    )


@router.post("/reports")
async def spec_create_report(
    body: reports_router.ReportRequest,
    record: student_auth.StudentSession = Depends(auth_router.get_current_student),
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(auth_router.get_settings),
) -> dict:
    return await reports_router.submit_report(
        body=body, record=record, session=session, settings=settings
    )


@router.get("/reports/track/{tracking_code}")
async def spec_track_report(
    tracking_code: str,
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    if not is_valid_tracking_code(tracking_code):
        raise ApiError(404, "not_found", "Report not found.")
    row = await report_store.get_public_report_by_tracking(session, tracking_code)
    if row is None:
        raise ApiError(404, "not_found", "Report not found.")
    return {
        "data": {
            "tracking_code": row["tracking_code"],
            "status": row["finding_status"],
            "finding_status": row["finding_status"],
            "category": row["category"],
            "course_code": row["course_code"],
            "course_title": row["course_title"],
            "department": row["department"],
            "incident_date": row["incident_date"].isoformat() if row["incident_date"] else None,
            "public_summary": row["public_summary"],
            "clearance_tier": row["clearance_tier"],
            "timeline": reports_router.build_tracking_timeline(row),
        }
    }


@router.post("/findings/{finding_id}/confirm")
async def spec_confirm_finding(
    finding_id: UUID,
    body: findings_router.ConfirmationRequest,
    record: student_auth.StudentSession = Depends(auth_router.get_current_student),
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(auth_router.get_settings),
) -> dict:
    return await findings_router.confirm_finding(
        finding_id=finding_id, body=body, record=record, session=session, settings=settings
    )


@router.get("/dashboard/overview")
async def spec_dashboard_overview(
    department_id: UUID | None = Query(None),
    month: str | None = Query(None, description="YYYY-MM filter"),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    start_month: date | None = None
    end_month: date | None = None
    if month:
        m = _MONTH_RE.match(month.strip())
        if not m:
            raise ApiError(400, "invalid_date_range", "month must use YYYY-MM format")
        year, mon = int(m.group(1)), int(m.group(2))
        if not 1 <= mon <= 12:
            raise ApiError(400, "invalid_date_range", "month must use YYYY-MM format")
        start_month = date(year, mon, 1)
        end_month = date(year, mon, monthrange(year, mon)[1])

    metrics = await dashboard_store.get_public_dashboard_metrics(
        session,
        department_id=department_id,
        start_month=start_month,
        end_month=end_month,
    )
    rows = [
        {
            "department_id": item["department_id"],
            "department_name": item["department"],
            "month": str(item["month"])[:7],
            "category": item["category"],
            "count": item["findings"],
        }
        for item in metrics
    ]
    return {"data": {"rows": rows}}
