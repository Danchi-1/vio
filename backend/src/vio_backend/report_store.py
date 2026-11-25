"""Data access for the M3 reporting workflow.

Reports are claims attached to findings; nothing here promotes a report
to a public fact. The reporter identity is stored for independence and
scoring rules but is never returned by the API layer.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend.report_rules import SessionWindow, generate_tracking_code


async def get_session_window(session: AsyncSession, university_id: str) -> SessionWindow | None:
    result = await session.execute(
        text(
            """
            SELECT session, status,
                   first_semester_lectures_start, first_semester_lectures_end,
                   first_semester_exams_start,
                   second_semester_lectures_start, second_semester_lectures_end,
                   second_semester_exams_start, session_ends
            FROM academic_sessions
            WHERE university_id = :university_id
            ORDER BY session DESC LIMIT 1
            """
        ),
        {"university_id": university_id},
    )
    row = result.first()
    if row is None:
        return None
    return SessionWindow(
        session=row[0],
        status=row[1],
        first_lectures_start=row[2],
        first_lectures_end=row[3],
        first_exams_start=row[4],
        second_lectures_start=row[5],
        second_lectures_end=row[6],
        second_exams_start=row[7],
        session_ends=row[8],
    )


async def is_course_registered(
    session: AsyncSession, student_id: str, academic_session: str, course_id: str
) -> bool:
    result = await session.execute(
        text(
            """
            SELECT 1 FROM student_course_registrations
            WHERE student_id = :student_id AND academic_session = :academic_session
              AND course_id = :course_id
            """
        ),
        {"student_id": student_id, "academic_session": academic_session, "course_id": course_id},
    )
    return result.first() is not None


async def reports_per_week_limit(session: AsyncSession) -> int:
    result = await session.execute(
        text("SELECT value FROM platform_settings WHERE key = 'reports_per_week'")
    )
    row = result.first()
    return int(row[0]) if row else 5


async def count_recent_reports(session: AsyncSession, student_id: str, since: datetime) -> int:
    result = await session.execute(
        text("SELECT count(*) FROM reports WHERE reporter_id = :student_id AND created_at >= :since"),
        {"student_id": student_id, "since": since},
    )
    return int(result.scalar_one())


async def get_finding_id(
    session: AsyncSession,
    *,
    course_id: str,
    category: str,
    incident_date: date,
    slot_id: str | None,
) -> str | None:
    result = await session.execute(
        text(
            """
            SELECT id FROM findings
            WHERE course_id = :course_id AND category = :category
              AND incident_date = :incident_date
              AND slot_id IS NOT DISTINCT FROM :slot_id
            """
        ),
        {
            "course_id": course_id,
            "category": category,
            "incident_date": incident_date,
            "slot_id": slot_id,
        },
    )
    row = result.first()
    return str(row[0]) if row else None


async def create_finding(
    session: AsyncSession,
    *,
    course_id: str,
    category: str,
    incident_date: date,
    slot_id: str | None,
) -> str:
    try:
        result = await session.execute(
            text(
                """
                INSERT INTO findings (course_id, category, incident_date, slot_id)
                VALUES (:course_id, :category, :incident_date, :slot_id)
                RETURNING id
                """
            ),
            {
                "course_id": course_id,
                "category": category,
                "incident_date": incident_date,
                "slot_id": slot_id,
            },
        )
        return str(result.scalar_one())
    except IntegrityError:
        # A concurrent report created the same incident; join it instead.
        finding_id = await get_finding_id(
            session, course_id=course_id, category=category, incident_date=incident_date, slot_id=slot_id
        )
        if finding_id is None:
            raise
        return finding_id


async def create_report(
    session: AsyncSession,
    *,
    reporter_id: str,
    finding_id: str,
    description: str,
    notice_given: bool | None,
) -> tuple[str, str]:
    """Insert a report with a unique tracking code. Returns (report_id, tracking_code)."""
    for _ in range(5):
        tracking_code = generate_tracking_code()
        try:
            result = await session.execute(
                text(
                    """
                    INSERT INTO reports (tracking_code, reporter_id, finding_id, description, notice_given)
                    VALUES (:tracking_code, :reporter_id, :finding_id, :description, :notice_given)
                    RETURNING id
                    """
                ),
                {
                    "tracking_code": tracking_code,
                    "reporter_id": reporter_id,
                    "finding_id": finding_id,
                    "description": description,
                    "notice_given": notice_given,
                },
            )
            return str(result.scalar_one()), tracking_code
        except IntegrityError:
            # Either a tracking-code collision (retry) or the independence
            # trigger fired (reporter already reported/confirmed this
            # finding) — re-raise the latter distinctly.
            existing = await session.execute(
                text("SELECT 1 FROM reports WHERE tracking_code = :code"),
                {"code": tracking_code},
            )
            if existing.first() is not None:
                continue
            raise
    raise RuntimeError("Could not allocate a unique tracking code")


async def get_panel_model_id(session: AsyncSession, *, role: str, model: str) -> str | None:
    result = await session.execute(
        text(
            """
            SELECT id FROM model_registry
            WHERE role = :role AND model = :model AND is_active
            ORDER BY created_at DESC LIMIT 1
            """
        ),
        {"role": role, "model": model},
    )
    row = result.first()
    return str(row[0]) if row else None


async def record_panel_vote(
    session: AsyncSession,
    *,
    subject_type: str,
    subject_id: str,
    role: str,
    model_id: str,
    verdict: str,
    reasons: list,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO panel_votes (subject_type, subject_id, round, role, model_id, verdict, reasons)
            VALUES (:subject_type, :subject_id, 1, :role, :model_id, :verdict, CAST(:reasons AS jsonb))
            ON CONFLICT (subject_type, subject_id, round, role, model_id) DO NOTHING
            """
        ),
        {
            "subject_type": subject_type,
            "subject_id": subject_id,
            "role": role,
            "model_id": model_id,
            "verdict": verdict,
            "reasons": _json_dumps(reasons),
        },
    )


def _json_dumps(value) -> str:
    import json

    return json.dumps(value)


async def _cursor_position(
    session: AsyncSession, student_id: str, cursor: str
) -> tuple[datetime, str] | None:
    result = await session.execute(
        text("SELECT created_at, id FROM reports WHERE reporter_id = :student_id AND id = :id"),
        {"student_id": student_id, "id": cursor},
    )
    row = result.first()
    return (row[0], str(row[1])) if row else None


async def list_student_reports(
    session: AsyncSession, student_id: str, *, cursor: str | None, limit: int
) -> tuple[list[dict], str | None]:
    """Keyset pagination on (created_at, id) descending. Returns rows plus
    the next cursor (last row's report id), or None when exhausted."""
    params: dict = {"student_id": student_id, "limit": limit + 1}
    where = "r.reporter_id = :student_id"
    if cursor:
        position = await _cursor_position(session, student_id, cursor)
        if position is None:
            return [], None
        params["cursor_created_at"] = position[0]
        params["cursor_id"] = position[1]
        where += " AND (r.created_at, r.id) < (:cursor_created_at, :cursor_id)"

    result = await session.execute(
        text(
            f"""
            SELECT r.id, r.tracking_code, r.description, r.notice_given, r.created_at,
                   f.id AS finding_id, f.status AS finding_status, f.category,
                   c.code AS course_code, c.title AS course_title, c.level AS course_level,
                   d.name AS department, f.incident_date
            FROM reports r
            JOIN findings f ON f.id = r.finding_id
            JOIN courses c ON c.id = f.course_id
            JOIN departments d ON d.id = c.department_id
            WHERE {where}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT :limit
            """
        ),
        params,
    )
    rows = [dict(row) for row in result.mappings().all()]
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(rows[-1]["id"])
    return rows, next_cursor


async def get_student_report_by_tracking(
    session: AsyncSession, student_id: str, tracking_code: str
) -> dict | None:
    result = await session.execute(
        text(
            """
            SELECT r.id, r.tracking_code, r.description, r.notice_given, r.created_at,
                   f.id AS finding_id, f.status AS finding_status, f.category,
                   f.public_summary, f.clearance_tier,
                   c.code AS course_code, c.title AS course_title,
                   d.name AS department, f.incident_date
            FROM reports r
            JOIN findings f ON f.id = r.finding_id
            JOIN courses c ON c.id = f.course_id
            JOIN departments d ON d.id = c.department_id
            WHERE r.reporter_id = :student_id AND r.tracking_code = :tracking_code
            """
        ),
        {"student_id": student_id, "tracking_code": tracking_code},
    )
    row = result.first()
    return dict(row._mapping) if row else None


async def list_registered_courses(session: AsyncSession, student_id: str, academic_session: str) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT c.id, c.code, c.title, c.level, d.name AS department
            FROM student_course_registrations r
            JOIN courses c ON c.id = r.course_id
            JOIN departments d ON d.id = c.department_id
            WHERE r.student_id = :student_id AND r.academic_session = :academic_session
            ORDER BY c.code
            """
        ),
        {"student_id": student_id, "academic_session": academic_session},
    )
    return [dict(row) for row in result.mappings().all()]


async def get_slot_for_course(
    session: AsyncSession, course_id: str, academic_session: str, slot_id: str
) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM timetable_slots WHERE id = :id AND course_id = :course_id AND academic_session = :session"),
        {"id": slot_id, "course_id": course_id, "session": academic_session},
    )
    return result.first() is not None
