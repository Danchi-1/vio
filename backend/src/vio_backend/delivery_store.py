"""Data access and workflows for Milestone 6: Deliveries, Escalations, Notices, and Replies.

Follows database/schema.sql, docs/DECISIONS.md, and docs/api/ENDPOINT_PROPOSAL.md.
Integrates domain logic from backend.src.domain and backend.src.application.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import audit
from vio_backend.reply_assessment import (
    AssessmentAction,
    ReplyReason,
    assess_reply,
)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def generate_delivery_token() -> tuple[str, bytes]:
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_token(raw_token)


# -----------------------------------------------------------------------------
# 1. CLASS NOTICES & LECTURER REPLIES
# -----------------------------------------------------------------------------

async def create_class_notice(
    session: AsyncSession,
    *,
    course_id: str,
    lecturer_id: str,
    kind: str,
    for_date: date,
    new_start: datetime | None = None,
    note: str | None = None,
) -> str:
    """Inserts a class notice posted by a lecturer."""
    query = """
        INSERT INTO class_notices (course_id, lecturer_id, kind, for_date, new_start, note, posted_at)
        VALUES (:course_id, :lecturer_id, :kind::notice_kind, :for_date, :new_start, :note, now())
        RETURNING id
    """
    res = await session.execute(
        text(query),
        {
            "course_id": course_id,
            "lecturer_id": lecturer_id,
            "kind": kind,
            "for_date": for_date,
            "new_start": new_start,
            "note": note,
        },
    )
    notice_id = res.scalar_one()
    return str(notice_id)


async def save_lecturer_reply(
    session: AsyncSession,
    *,
    finding_id: str,
    lecturer_id: str,
    reason: ReplyReason,
    body: str,
) -> tuple[str, str]:
    """Records a lecturer reply and automatically evaluates assessment actions."""
    # Run the other dev's domain assessment
    assessment = assess_reply(reason=reason, explanation=body)

    query = """
        INSERT INTO lecturer_replies (finding_id, lecturer_id, reason, body, created_at)
        VALUES (:finding_id, :lecturer_id, :reason::reply_reason, :body, now())
        RETURNING id
    """
    res = await session.execute(
        text(query),
        {
            "finding_id": finding_id,
            "lecturer_id": lecturer_id,
            "reason": reason.value,
            "body": body,
        },
    )
    reply_id = str(res.scalar_one())

    # Log to decision_log
    await audit.record_decision(
        session,
        finding_id=finding_id,
        stage="reply",
        actor="lecturer_reply_service",
        decision=f"reply_received_{reason.value}",
        details={
            "reply_id": reply_id,
            "reason": reason.value,
            "assessment_action": assessment.action.value,
        },
    )

    # If disputed, automatically register an appeal
    if assessment.action == AssessmentAction.REFER_TO_APPEALS:
        await file_appeal(
            session,
            finding_id=finding_id,
            appellant="lecturer",
            appellant_id=lecturer_id,
            body=f"Lecturer disputed finding: {body}",
        )

    return reply_id, assessment.action.value


# -----------------------------------------------------------------------------
# 2. DELIVERIES & AUTHORITY ROUTING
# -----------------------------------------------------------------------------

async def resolve_authority_for_step(
    session: AsyncSession,
    *,
    university_id: str,
    department_id: str,
    faculty_id: str,
    role: str,
) -> str | None:
    """Finds the active authority holding the given role at department/faculty/uni level."""
    if role == "hod":
        query = "SELECT id FROM authorities WHERE department_id = :dept_id AND role = 'hod' AND is_active = true LIMIT 1"
        res = await session.execute(text(query), {"dept_id": department_id})
    elif role == "dean":
        query = "SELECT id FROM authorities WHERE faculty_id = :fac_id AND role = 'dean' AND is_active = true LIMIT 1"
        res = await session.execute(text(query), {"fac_id": faculty_id})
    else:
        query = "SELECT id FROM authorities WHERE university_id = :uni_id AND role = :role::authority_role AND is_active = true LIMIT 1"
        res = await session.execute(text(query), {"uni_id": university_id, "role": role})

    row = res.first()
    return str(row[0]) if row else None


async def queue_delivery_for_step(
    session: AsyncSession,
    *,
    finding_id: str,
    step_order: int = 1,
) -> tuple[str, str] | None:
    """Queues a delivery to the designated authority for the finding's routing step."""
    # Find finding & course/department/faculty info
    info_query = """
        SELECT f.category, c.department_id, d.faculty_id, fac.university_id
        FROM findings f
        JOIN courses c ON c.id = f.course_id
        JOIN departments d ON d.id = c.department_id
        JOIN faculties fac ON fac.id = d.faculty_id
        WHERE f.id = :finding_id
    """
    info_res = await session.execute(text(info_query), {"finding_id": finding_id})
    row = info_res.first()
    if row is None:
        return None

    category, dept_id, fac_id, uni_id = str(row[0]), str(row[1]), str(row[2]), str(row[3])

    # Find routing step
    step_query = """
        SELECT authority_role, wait_days
        FROM routing_steps
        WHERE university_id = :uni_id AND category = :category::report_category AND step_order = :step_order
    """
    step_res = await session.execute(
        text(step_query),
        {"uni_id": uni_id, "category": category, "step_order": step_order},
    )
    step_row = step_res.first()
    if step_row is None:
        # No routing step configured
        return None

    authority_role, wait_days = str(step_row[0]), int(step_row[1])
    authority_id = await resolve_authority_for_step(
        session,
        university_id=uni_id,
        department_id=dept_id,
        faculty_id=fac_id,
        role=authority_role,
    )
    if authority_id is None:
        # Authority holder not found/inactive
        return None

    raw_token, token_hash = generate_delivery_token()
    due_at = datetime.now(UTC) + timedelta(days=wait_days)

    insert_query = """
        INSERT INTO deliveries (finding_id, authority_id, step_order, status, token_hash, queued_at, due_at)
        VALUES (:finding_id, :authority_id, :step_order, 'queued', :token_hash, now(), :due_at)
        ON CONFLICT (finding_id, step_order) DO NOTHING
        RETURNING id
    """
    res = await session.execute(
        text(insert_query),
        {
            "finding_id": finding_id,
            "authority_id": authority_id,
            "step_order": step_order,
            "token_hash": token_hash,
            "due_at": due_at,
        },
    )
    ins_row = res.first()
    if ins_row is None:
        return None

    delivery_id = str(ins_row[0])

    await audit.record_decision(
        session,
        finding_id=finding_id,
        stage="delivery",
        actor="routing_engine",
        decision=f"delivery_queued_step_{step_order}",
        details={
            "delivery_id": delivery_id,
            "authority_id": authority_id,
            "role": authority_role,
            "step_order": step_order,
            "wait_days": wait_days,
        },
    )

    return delivery_id, raw_token


async def redeem_delivery_token(session: AsyncSession, raw_token: str) -> tuple[dict | None, str | None]:
    """Redeems a secure, one-time delivery link token and returns authorized details.
    
    Enforces:
    - Expiration: tokens cannot be redeemed after due_at.
    - Single-use: once redeemed, the raw link token cannot be reused.
    
    Returns (delivery_data, None) on success, or (None, error_code):
    - 'not_found'
    - 'expired_link'
    - 'link_already_used'
    """
    token_hash = hash_token(raw_token)
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
        WHERE d.token_hash = :token_hash
    """
    res = await session.execute(text(query), {"token_hash": token_hash})
    row = res.first()
    if row is None:
        return None, "not_found"

    data = dict(row._mapping)

    # Check expiry
    due_at = data.get("due_at")
    if due_at:
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        if due_at.tzinfo is None:
            now_utc = datetime.utcnow()
        if due_at < now_utc:
            return None, "expired_link"

    # Check one-time link redemption
    if data.get("viewed_at") is not None or data["status"] not in ("queued", "sent"):
        return None, "link_already_used"

    # Mark viewed_at and transition status to viewed
    await session.execute(
        text("UPDATE deliveries SET status = 'viewed', viewed_at = now() WHERE id = :id"),
        {"id": data["delivery_id"]},
    )
    data["status"] = "viewed"

    return data, None


async def acknowledge_delivery(session: AsyncSession, delivery_id: str) -> bool:
    """Marks a delivery as acknowledged by the authority."""
    query = """
        UPDATE deliveries
        SET acknowledged_at = COALESCE(acknowledged_at, now()),
            status = 'acknowledged'
        WHERE id = :delivery_id AND status IN ('queued', 'sent', 'viewed')
        RETURNING finding_id
    """
    res = await session.execute(text(query), {"delivery_id": delivery_id})
    row = res.first()
    if row is None:
        return False

    finding_id = str(row[0])
    await audit.record_decision(
        session,
        finding_id=finding_id,
        stage="delivery",
        actor="authority",
        decision="delivery_acknowledged",
        details={"delivery_id": delivery_id},
    )
    return True


async def record_authority_response(
    session: AsyncSession,
    *,
    delivery_id: str,
    outcome: str,
    body: str,
) -> str | None:
    """Records an official response from an authority."""
    # Check delivery
    d_res = await session.execute(
        text("SELECT finding_id FROM deliveries WHERE id = :delivery_id"),
        {"delivery_id": delivery_id},
    )
    d_row = d_res.first()
    if d_row is None:
        return None
    finding_id = str(d_row[0])

    resp_query = """
        INSERT INTO authority_responses (delivery_id, outcome, body, created_at)
        VALUES (:delivery_id, :outcome::response_outcome, :body, now())
        RETURNING id
    """
    r_res = await session.execute(
        text(resp_query),
        {"delivery_id": delivery_id, "outcome": outcome, "body": body},
    )
    resp_id = str(r_res.scalar_one())

    # Update delivery status
    await session.execute(
        text("UPDATE deliveries SET status = 'responded', responded_at = now() WHERE id = :delivery_id"),
        {"delivery_id": delivery_id},
    )

    await audit.record_decision(
        session,
        finding_id=finding_id,
        stage="delivery",
        actor="authority",
        decision=f"authority_response_{outcome}",
        details={"delivery_id": delivery_id, "response_id": resp_id, "outcome": outcome},
    )
    return resp_id


# -----------------------------------------------------------------------------
# 3. ESCALATION BACKGROUND WORKER
# -----------------------------------------------------------------------------

async def process_overdue_escalations(session: AsyncSession) -> list[dict]:
    """Finds unacknowledged deliveries past due_at using deliveries_to_escalate view,
    marks them escalated, and queues the next escalation step."""
    query = """
        SELECT id, finding_id, step_order
        FROM deliveries_to_escalate
    """
    res = await session.execute(text(query))
    overdue = res.all()

    escalated = []
    for row in overdue:
        deliv_id, finding_id, step_order = str(row[0]), str(row[1]), int(row[2])

        # 1. Mark current delivery escalated
        await session.execute(
            text("UPDATE deliveries SET status = 'escalated' WHERE id = :id"),
            {"id": deliv_id},
        )

        # 2. Queue next step (e.g. step_order + 1)
        next_step = step_order + 1
        new_deliv = await queue_delivery_for_step(session, finding_id=finding_id, step_order=next_step)

        await audit.record_decision(
            session,
            finding_id=finding_id,
            stage="escalation",
            actor="escalation_worker",
            decision=f"escalated_from_step_{step_order}_to_{next_step}",
            details={
                "previous_delivery_id": deliv_id,
                "new_delivery_id": new_deliv[0] if new_deliv else None,
                "step_order": next_step,
            },
        )

        escalated.append({
            "previous_delivery_id": deliv_id,
            "finding_id": finding_id,
            "escalated_to_step": next_step,
            "new_delivery_queued": new_deliv is not None,
        })

    return escalated


# -----------------------------------------------------------------------------
# 4. APPEALS
# -----------------------------------------------------------------------------

async def file_appeal(
    session: AsyncSession,
    *,
    finding_id: str,
    appellant: str,  # 'lecturer', 'authority', 'student'
    appellant_id: str,
    report_id: str | None = None,
    body: str,
) -> str:
    """Registers an appeal against a finding."""
    lecturer_id = appellant_id if appellant == "lecturer" else None
    authority_id = appellant_id if appellant == "authority" else None

    query = """
        INSERT INTO appeals (finding_id, appellant, lecturer_id, authority_id, report_id, body, status, round, created_at)
        VALUES (:finding_id, :appellant::appellant_kind, :lecturer_id, :authority_id, :report_id, :body, 'open', 1, now())
        ON CONFLICT (finding_id, appellant, round) DO UPDATE SET body = EXCLUDED.body
        RETURNING id
    """
    res = await session.execute(
        text(query),
        {
            "finding_id": finding_id,
            "appellant": appellant,
            "lecturer_id": lecturer_id,
            "authority_id": authority_id,
            "report_id": report_id,
            "body": body,
        },
    )
    appeal_id = str(res.scalar_one())

    # Mark finding as disputed while appeal is open
    await session.execute(
        text("UPDATE findings SET status = 'disputed' WHERE id = :finding_id"),
        {"finding_id": finding_id},
    )

    await audit.record_decision(
        session,
        finding_id=finding_id,
        stage="appeal",
        actor=f"{appellant}_appellant",
        decision="appeal_filed",
        details={"appeal_id": appeal_id, "appellant": appellant, "appellant_id": appellant_id},
    )

    return appeal_id
