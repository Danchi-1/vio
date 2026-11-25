"""Student findings and confirmation endpoints (M4).

Implements:
- GET /api/v1/student/findings/confirmable
- GET /api/v1/student/findings/{finding_id}
- POST /api/v1/student/findings/{finding_id}/confirmations

Enforces:
- Registered course requirement.
- Reporter/confirmer independence (a student cannot both report and confirm).
- Single confirmation per student.
- Score recomputation on confirmation.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import finding_store, student_auth
from vio_backend.database import session_dependency
from vio_backend.errors import ApiError
from vio_backend.routers.auth import get_current_student
from vio_backend.routers.reports import _CATEGORY_LABELS, _require_confirmed_session, _require_ready

router = APIRouter(prefix="/api/v1/student/findings", tags=["findings"])


class ConfirmationRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


def _format_finding_summary(row: dict) -> dict:
    cat = row["category"]
    return {
        "finding_id": str(row["id"]),
        "course_code": row["course_code"],
        "course_title": row["course_title"],
        "course_level": row["course_level"],
        "department": row["department_name"],
        "category": cat,
        "category_label": _CATEGORY_LABELS.get(cat, cat),
        "incident_date": row["incident_date"].isoformat() if row["incident_date"] else None,
        "status": row["status"],
        "public_summary": row.get("public_summary"),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/confirmable")
async def list_confirmable_findings(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    _require_ready(record)
    window, academic_session = await _require_confirmed_session(session, record)

    rows, next_cursor = await finding_store.list_confirmable_findings(
        session,
        student_id=record.student_id,
        academic_session=academic_session,
        cursor=cursor,
        limit=limit,
    )
    return {
        "data": [_format_finding_summary(r) for r in rows],
        "meta": {"next_cursor": next_cursor},
    }


@router.get("/{finding_id}")
async def get_finding(
    finding_id: UUID,
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    _require_ready(record)
    window, academic_session = await _require_confirmed_session(session, record)

    row = await finding_store.get_finding_for_student(
        session,
        finding_id=str(finding_id),
        student_id=record.student_id,
        academic_session=academic_session,
    )
    if row is None or not row["is_registered"]:
        raise ApiError(404, "not_found", "Finding not found.")

    data = _format_finding_summary(row)
    data["can_confirm"] = row["can_confirm"]
    data["is_reporter"] = row["is_reporter"]
    data["is_confirmer"] = row["is_confirmer"]
    data["clearance_tier"] = row["clearance_tier"]
    return {"data": data}


@router.post("/{finding_id}/confirmations")
async def confirm_finding(
    finding_id: UUID,
    body: ConfirmationRequest,
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    _require_ready(record)
    window, academic_session = await _require_confirmed_session(session, record)

    finding_str_id = str(finding_id)
    finding = await finding_store.get_finding_for_student(
        session,
        finding_id=finding_str_id,
        student_id=record.student_id,
        academic_session=academic_session,
    )
    if finding is None or not finding["is_registered"]:
        raise ApiError(404, "not_found", "Finding not found.")

    if finding["is_reporter"]:
        raise ApiError(422, "validation_failed", "You cannot confirm an incident that you reported.")
    if finding["is_confirmer"]:
        raise ApiError(422, "validation_failed", "You have already confirmed this incident.")
    if finding["status"] != "collecting":
        raise ApiError(422, "validation_failed", "This finding is no longer open for confirmation.")

    try:
        confirmation_id = await finding_store.add_confirmation(
            session,
            finding_id=finding_str_id,
            student_id=record.student_id,
            comment=body.comment,
        )
        score_res = await finding_store.recompute_and_store_finding_score(
            session, finding_id=finding_str_id
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(422, "validation_failed", "You cannot confirm this incident.") from exc

    return {
        "data": {
            "confirmation_id": confirmation_id,
            "finding_id": finding_str_id,
            "status": "confirmed",
            "message": "Your confirmation was recorded.",
            "total_supporters": score_res.total_supporters,
        }
    }
