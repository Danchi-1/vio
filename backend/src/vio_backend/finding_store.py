"""Data access for findings, confirmations, and scoring (M4).

Follows docs/DECISIONS.md, docs/api/ENDPOINT_PROPOSAL.md, and database/schema.sql.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend.scoring import (
    FORMULA_VERSION,
    ScoreResult,
    SupporterInput,
    calculate_finding_score,
)


async def list_confirmable_findings(
    session: AsyncSession,
    *,
    student_id: str,
    academic_session: str,
    cursor: str | None = None,
    limit: int = 20,
) -> tuple[list[dict], str | None]:
    """Returns findings for courses the student is registered for that the student
    has neither reported nor already confirmed, in 'collecting' status."""
    query = """
        SELECT f.id, f.category, f.incident_date, f.status, f.public_summary, f.created_at,
               c.id AS course_id, c.code AS course_code, c.title AS course_title,
               c.level AS course_level, d.name AS department_name
        FROM findings f
        JOIN courses c ON c.id = f.course_id
        JOIN departments d ON d.id = c.department_id
        JOIN student_course_registrations r
          ON r.course_id = f.course_id
         AND r.student_id = :student_id
         AND r.academic_session = :academic_session
        WHERE f.status = 'collecting'
          AND NOT EXISTS (
              SELECT 1 FROM reports rep
              WHERE rep.finding_id = f.id AND rep.reporter_id = :student_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM finding_confirmations fc
              WHERE fc.finding_id = f.id AND fc.student_id = :student_id
          )
    """
    params: dict = {
        "student_id": student_id,
        "academic_session": academic_session,
        "limit": limit + 1,
    }

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            query += " AND f.created_at < :cursor"
            params["cursor"] = cursor_dt
        except ValueError:
            pass

    query += " ORDER BY f.created_at DESC LIMIT :limit"

    result = await session.execute(text(query), params)
    rows = [dict(row._mapping) for row in result.all()]

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = rows[-1]["created_at"].isoformat()

    return rows, next_cursor


async def get_finding_for_student(
    session: AsyncSession,
    *,
    finding_id: str,
    student_id: str,
    academic_session: str,
) -> dict | None:
    """Gets finding detail if the student is registered for the course, including
    whether the student can confirm it."""
    query = """
        SELECT f.id, f.category, f.incident_date, f.status, f.public_summary, f.created_at,
               f.clearance_tier,
               c.id AS course_id, c.code AS course_code, c.title AS course_title,
               c.level AS course_level, d.name AS department_name,
               EXISTS (
                   SELECT 1 FROM student_course_registrations r
                   WHERE r.course_id = f.course_id
                     AND r.student_id = :student_id
                     AND r.academic_session = :academic_session
               ) AS is_registered,
               EXISTS (
                   SELECT 1 FROM reports rep
                   WHERE rep.finding_id = f.id AND rep.reporter_id = :student_id
               ) AS is_reporter,
               EXISTS (
                   SELECT 1 FROM finding_confirmations fc
                   WHERE fc.finding_id = f.id AND fc.student_id = :student_id
               ) AS is_confirmer
        FROM findings f
        JOIN courses c ON c.id = f.course_id
        JOIN departments d ON d.id = c.department_id
        WHERE f.id = :finding_id
    """
    result = await session.execute(
        text(query),
        {
            "finding_id": finding_id,
            "student_id": student_id,
            "academic_session": academic_session,
        },
    )
    row = result.first()
    if row is None:
        return None

    data = dict(row._mapping)
    data["can_confirm"] = (
        data["is_registered"]
        and not data["is_reporter"]
        and not data["is_confirmer"]
        and data["status"] == "collecting"
    )
    return data


async def add_confirmation(
    session: AsyncSession,
    *,
    finding_id: str,
    student_id: str,
    comment: str | None = None,
) -> str:
    """Inserts confirmation into finding_confirmations table.
    Enforces independence triggers and uniqueness."""
    query = """
        INSERT INTO finding_confirmations (finding_id, student_id, comment)
        VALUES (:finding_id, :student_id, :comment)
        RETURNING id
    """
    result = await session.execute(
        text(query),
        {
            "finding_id": finding_id,
            "student_id": student_id,
            "comment": comment.strip() if comment else None,
        },
    )
    row = result.first()
    return str(row[0])


async def recompute_and_store_finding_score(
    session: AsyncSession,
    finding_id: str,
    as_of: date | None = None,
) -> ScoreResult:
    """Recomputes a finding's score from its supporters and stores the breakdown
    in finding_scores."""
    if as_of is None:
        as_of = datetime.now(UTC).date()

    # 1. Fetch finding details and notice announcement status
    finding_query = """
        SELECT f.incident_date,
               EXISTS (
                   SELECT 1 FROM class_notices n
                   WHERE n.course_id = f.course_id
                     AND n.for_date = f.incident_date
                     AND n.posted_at < (f.incident_date)::timestamptz
               ) AS announced_in_advance
        FROM findings f
        WHERE f.id = :finding_id
    """
    f_res = await session.execute(text(finding_query), {"finding_id": finding_id})
    f_row = f_res.first()
    if f_row is None:
        raise ValueError(f"Finding {finding_id} not found")

    incident_date = f_row[0]
    announced_in_advance = bool(f_row[1])

    # 2. Gather all distinct reporters
    reporters_res = await session.execute(
        text("SELECT reporter_id FROM reports WHERE finding_id = :finding_id"),
        {"finding_id": finding_id},
    )
    reporter_ids = [str(r[0]) for r in reporters_res.all()]

    # 3. Gather all distinct confirmers
    confirmers_res = await session.execute(
        text("SELECT student_id FROM finding_confirmations WHERE finding_id = :finding_id"),
        {"finding_id": finding_id},
    )
    confirmer_ids = [str(c[0]) for c in confirmers_res.all()]

    all_student_ids = list(dict.fromkeys(reporter_ids + confirmer_ids))
    if not all_student_ids:
        supporters_input = []
    else:
        # Check verification status for each student
        verif_res = await session.execute(
            text(
                """
                SELECT student_id, passed
                FROM student_verifications
                WHERE student_id = ANY(:student_ids::uuid[]) AND factor = 'school_email'
                """
            ),
            {"student_ids": all_student_ids},
        )
        verified_map = {str(r[0]): bool(r[1]) for r in verif_res.all()}

        # Check anomaly signals for each student
        anomaly_res = await session.execute(
            text(
                """
                SELECT student_id, severity
                FROM anomaly_signals
                WHERE student_id = ANY(:student_ids::uuid[])
                """
            ),
            {"student_ids": all_student_ids},
        )
        anomaly_map: dict[str, list[float]] = {}
        for r in anomaly_res.all():
            sid = str(r[0])
            anomaly_map.setdefault(sid, []).append(float(r[1]))

        supporters_input = []
        for sid in reporter_ids:
            supporters_input.append(
                SupporterInput(
                    student_id=sid,
                    role="reporter",
                    has_verified_email=verified_map.get(sid, True),  # default True as they signed in via email OTP
                    anomaly_severities=anomaly_map.get(sid, []),
                    false_finding_count=0,
                )
            )
        for sid in confirmer_ids:
            supporters_input.append(
                SupporterInput(
                    student_id=sid,
                    role="confirmer",
                    has_verified_email=verified_map.get(sid, True),
                    anomaly_severities=anomaly_map.get(sid, []),
                    false_finding_count=0,
                )
            )

    score_result = calculate_finding_score(
        incident_date=incident_date,
        as_of=as_of,
        announced_in_advance=announced_in_advance,
        supporters=supporters_input,
    )

    # 4. Insert into finding_scores
    insert_score_query = """
        INSERT INTO finding_scores (finding_id, formula_version, score, supporters, breakdown, computed_at)
        VALUES (:finding_id, :formula_version, :score, :supporters, :breakdown, now())
    """
    await session.execute(
        text(insert_score_query),
        {
            "finding_id": finding_id,
            "formula_version": FORMULA_VERSION,
            "score": score_result.score,
            "supporters": score_result.total_supporters,
            "breakdown": json.dumps(score_result.breakdown),
        },
    )

    # 5. Update clearance_tier on finding if new tier reached
    update_tier_query = """
        UPDATE findings
        SET clearance_tier = GREATEST(clearance_tier, :tier)
        WHERE id = :finding_id
    """
    await session.execute(
        text(update_tier_query),
        {"finding_id": finding_id, "tier": score_result.clearance_tier},
    )

    return score_result
