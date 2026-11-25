"""Student report submission and tracking (M3).

A report is a claim attached to a finding (one incident = course + date +
category [+ slot]). Intake is fail-closed: deterministic rules run first,
then the Groq safety and extractor models vote; any panel outage rejects
the request as unavailable rather than accepting unvetted text. Rejected
reports are never persisted. See docs/DECISIONS.md and
docs/api/ENDPOINT_PROPOSAL.md ("Reports, Findings, Confirmation, and
Tracking").
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import finding_store, model_panel, report_store, student_auth
from vio_backend.database import session_dependency
from vio_backend.errors import ApiError
from vio_backend.report_rules import (
    ASSESSMENT_CATEGORIES,
    MAX_DESCRIPTION_LENGTH,
    MIN_DESCRIPTION_LENGTH,
    OPEN_CATEGORIES,
    REPORT_CATEGORIES,
    TEACHING_CATEGORIES,
    SessionWindow,
    is_valid_tracking_code,
    normalize_description,
    validate_category,
    validate_incident_date,
)
from vio_backend.config import Settings
from vio_backend.routers.auth import get_current_student, get_settings

router = APIRouter(prefix="/api/v1/student", tags=["reports"])

_CATEGORY_LABELS = {
    "class_not_held": "Class not held",
    "practical_not_held": "Practical not held",
    "outline_incomplete": "Course outline incomplete",
    "poor_delivery": "Poor course delivery",
    "unfair_assessment": "Unfair assessment",
    "unresolved_complaint": "Unresolved complaint",
    "other_academic": "Other academic issue",
    "institutional": "Institutional issue",
}


def _require_ready(record: student_auth.StudentSession) -> None:
    if record.department_id is None or record.level is None:
        raise ApiError(409, "profile_required", "Complete your profile before reporting.")


async def _require_confirmed_session(
    session: AsyncSession, record: student_auth.StudentSession
) -> tuple[SessionWindow, str]:
    current = await student_auth.get_latest_academic_session(session, record.university_id)
    if current is None:
        raise ApiError(503, "service_unavailable", "The academic session calendar is not available yet.")
    if record.confirmed_session != current.session:
        raise ApiError(
            409, "session_confirmation_required", "Confirm the current academic session before reporting."
        )
    window = await report_store.get_session_window(session, record.university_id)
    if window is None:
        raise ApiError(503, "service_unavailable", "The academic session calendar is not available yet.")
    return window, current.session


@router.get("/report-options")
async def report_options(
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    window, academic_session = await _require_confirmed_session(session, record)
    courses = await report_store.list_registered_courses(session, record.student_id, academic_session)
    earliest = window.first_lectures_start
    latest = window.session_ends or window.second_lectures_end or window.first_lectures_end
    return {
        "data": {
            "academic_session": academic_session,
            "academic_session_status": window.status,
            "categories": [
                {"value": c, "label": _CATEGORY_LABELS[c]}
                for c in sorted(REPORT_CATEGORIES)
            ],
            "teaching_categories": sorted(TEACHING_CATEGORIES),
            "assessment_categories": sorted(ASSESSMENT_CATEGORIES),
            "open_categories": sorted(OPEN_CATEGORIES),
            "description": {
                "min_length": MIN_DESCRIPTION_LENGTH,
                "max_length": MAX_DESCRIPTION_LENGTH,
            },
            "incident_date": {
                "earliest": earliest.isoformat() if earliest else None,
                "latest": latest.isoformat() if latest else None,
                "note": "Teaching-period categories must fall inside a lecture window and are filed before that window's exam period begins.",
            },
            "courses": [
                {
                    "course_id": str(c["id"]),
                    "course_code": c["code"],
                    "course_title": c["title"],
                    "level": c["level"],
                    "department": c["department"],
                    "registration_status": "self_declared_unverified",
                }
                for c in courses
            ],
        }
    }


class ReportRequest(BaseModel):
    course_id: UUID
    incident_date: str = Field(min_length=10, max_length=10)
    category: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=5000)
    notice_given: bool | None = None
    slot_id: UUID | None = None


def _parse_incident_date(raw: str):
    from datetime import date as _date

    try:
        return _date.fromisoformat(raw)
    except ValueError:
        pass
    raise ApiError(
        422, "validation_failed", "Use YYYY-MM-DD for the incident date.",
        {"incident_date": ["Invalid date."]},
    )


@router.post("/reports")
async def submit_report(
    body: ReportRequest,
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(get_settings),
) -> dict:
    _require_ready(record)
    window, academic_session = await _require_confirmed_session(session, record)

    category = validate_category(body.category)
    description = normalize_description(body.description)
    incident = _parse_incident_date(body.incident_date)
    course_id = str(body.course_id)
    slot_id = str(body.slot_id) if body.slot_id else None

    if not await report_store.is_course_registered(
        session, record.student_id, academic_session, course_id
    ):
        raise ApiError(
            422,
            "validation_failed",
            "You can only report a course you have registered for this session.",
            {"course_id": ["Not in your registered courses."]},
        )
    if slot_id and not await report_store.get_slot_for_course(
        session, course_id, academic_session, slot_id
    ):
        raise ApiError(
            422,
            "validation_failed",
            "That timetable slot does not belong to this course and session.",
            {"slot_id": ["Unknown slot."]},
        )

    validate_incident_date(
        incident, window=window, category=category, today=datetime.now(UTC).date()
    )

    now = datetime.now(UTC)
    recent = await report_store.count_recent_reports(session, record.student_id, now - timedelta(days=7))
    limit = await report_store.reports_per_week_limit(session)
    if recent >= limit:
        raise ApiError(429, "rate_limited", "You have reached the weekly report limit. Try again later.")

    # Panel model IDs must exist before we call the models, so a missing
    # registry row fails closed the same way a missing API key does.
    safety_model_id = await report_store.get_panel_model_id(
        session, role="safety", model=settings.groq_safety_model
    )
    extractor_model_id = await report_store.get_panel_model_id(
        session, role="extractor", model=settings.groq_extractor_model
    )
    if safety_model_id is None or extractor_model_id is None:
        raise ApiError(503, "service_unavailable", "Report processing is not configured yet.")

    try:
        safety = await model_panel.safety_vote(settings, report_text=description)
        extraction = await model_panel.extract_report(
            settings, report_text=description, claimed_category=category
        )
    except model_panel.PanelUnavailable as exc:
        raise ApiError(503, "service_unavailable", "Report processing is temporarily unavailable.") from exc

    if safety.verdict != "pass":
        raise ApiError(
            422,
            "report_rejected",
            "This report could not be accepted after automated safety review.",
        )

    # Rule verification of extractor output: the model must independently
    # recover the claimed category and must not contradict the incident date.
    if extraction.category != category:
        raise ApiError(
            422,
            "report_rejected",
            "The report details could not be verified against the chosen category. Please review and resubmit.",
        )
    if extraction.incident_date and extraction.incident_date != incident.isoformat():
        raise ApiError(
            422,
            "report_rejected",
            "The report details could not be verified against the incident date. Please review and resubmit.",
        )

    finding_id = await report_store.get_finding_id(
        session, course_id=course_id, category=category, incident_date=incident, slot_id=slot_id
    )
    if finding_id is None:
        try:
            finding_id = await report_store.create_finding(
                session, course_id=course_id, category=category, incident_date=incident, slot_id=slot_id
            )
        except IntegrityError:
            finding_id = await report_store.get_finding_id(
                session, course_id=course_id, category=category, incident_date=incident, slot_id=slot_id
            )
            if finding_id is None:
                raise

    try:
        report_id, tracking_code = await report_store.create_report(
            session,
            reporter_id=record.student_id,
            finding_id=finding_id,
            description=description,
            notice_given=body.notice_given,
        )
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            422,
            "validation_failed",
            "You have already reported or confirmed this incident.",
        ) from exc

    await report_store.record_panel_vote(
        session,
        subject_type="report",
        subject_id=report_id,
        role="safety",
        model_id=safety_model_id,
        verdict="pass",
        reasons={"model_reasons": safety.reasons, "extraction": extraction.raw},
    )
    await report_store.record_panel_vote(
        session,
        subject_type="report",
        subject_id=report_id,
        role="extractor",
        model_id=extractor_model_id,
        verdict="pass",
        reasons={"extraction": extraction.raw},
    )
    await finding_store.recompute_and_store_finding_score(session, finding_id=finding_id)
    await session.commit()

    return {
        "data": {
            "tracking_code": tracking_code,
            "status": "collecting",
            "message": "Your report was received. It has not been established as a finding.",
            "timeline": [
                {
                    "event": "received",
                    "occurred_at": datetime.now(UTC).isoformat(),
                    "label": "Report received",
                }
            ],
            "available_actions": [],
        }
    }


def _report_json(row: dict) -> dict:
    return {
        "tracking_code": row["tracking_code"],
        "category": row["category"],
        "course_code": row["course_code"],
        "course_title": row["course_title"],
        "course_level": row["course_level"],
        "department": row["department"],
        "incident_date": row["incident_date"].isoformat() if row["incident_date"] else None,
        "finding_status": row["finding_status"],
        "description": row["description"],
        "notice_given": row["notice_given"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/reports")
async def list_reports(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    rows, next_cursor = await report_store.list_student_reports(
        session, record.student_id, cursor=cursor, limit=limit
    )
    return {
        "data": [_report_json(row) for row in rows],
        "meta": {"next_cursor": next_cursor},
    }


@router.get("/reports/{tracking_code}")
async def get_report(
    tracking_code: str,
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    if not is_valid_tracking_code(tracking_code):
        raise ApiError(404, "not_found", "Report not found.")
    row = await report_store.get_student_report_by_tracking(session, record.student_id, tracking_code)
    if row is None:
        raise ApiError(404, "not_found", "Report not found.")
    data = _report_json(row)
    data["public_summary"] = row["public_summary"]
    timeline = [
        {
            "event": "received",
            "occurred_at": row["created_at"].isoformat() if row["created_at"] else None,
            "label": "Report received",
        }
    ]
    status = row.get("finding_status")
    if status == "collecting":
        timeline.append({
            "event": "collecting",
            "occurred_at": None,
            "label": "Collecting corroborating student confirmations",
        })
    elif status == "pending_panel":
        timeline.append({
            "event": "evaluating",
            "occurred_at": None,
            "label": "Under automated verification",
        })
    elif status == "cleared":
        timeline.append({
            "event": "cleared",
            "occurred_at": None,
            "label": "Finding verified and established",
        })
    elif status == "published":
        timeline.append({
            "event": "cleared",
            "occurred_at": None,
            "label": "Finding verified and established",
        })
        timeline.append({
            "event": "published",
            "occurred_at": None,
            "label": "Aggregated on public institutional dashboard",
        })
    elif status == "held":
        timeline.append({
            "event": "held",
            "occurred_at": None,
            "label": "Held pending additional corroborating evidence",
        })
    elif status == "rejected":
        timeline.append({
            "event": "closed",
            "occurred_at": None,
            "label": "Closed: insufficient evidence",
        })

    data["timeline"] = timeline
    return {"data": data}
