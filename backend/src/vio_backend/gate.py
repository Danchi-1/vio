"""Multi-model adjudication gate for findings (M5).

Follows docs/DECISIONS.md (2026-11-07, 2026-11-09) and database/schema.sql:
- 3 independent model panel roles: safety, consistency, red-team.
- Calibrated confidence minimum 0.80: confidence below 0.80 counts as abstain.
- Deterministic Gate Transitions:
    * Unanimous pass (all 3 models pass with confidence >= 0.80) -> 'cleared'
    * Any model blocks with confidence >= 0.80 -> 'rejected'
    * Uncertain or abstain -> 'held' for hold_ttl_days (default 14 days)
- Generates neutral anonymized public summary upon clearance.
- Records all panel votes in panel_votes and state changes in decision_log.
- Fail-closed: trips to held if quota exhausted or circuit breaker open.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import audit, model_panel
from vio_backend.config import Settings
from vio_backend.model_panel import PanelUnavailable, Vote


class CircuitBreakerOpen(RuntimeError):
    """Raised when the model_panel circuit breaker is open."""


@dataclass(frozen=True)
class GateDecision:
    finding_id: str
    status: str  # 'cleared' | 'held' | 'rejected'
    clearance_tier: int
    public_summary: str | None
    held_until: datetime | None
    cleared_at: datetime | None
    votes: list[Vote]
    details: dict[str, Any]


async def is_circuit_breaker_open(session: AsyncSession, name: str = "model_panel") -> bool:
    result = await session.execute(
        text("SELECT state FROM circuit_breakers WHERE name = :name"),
        {"name": name},
    )
    row = result.first()
    return bool(row and row[0] == "open")


async def get_model_id(
    session: AsyncSession, *, role: str, model: str
) -> str | None:
    result = await session.execute(
        text(
            """
            SELECT id FROM model_registry
            WHERE role = :role::panel_role AND model = :model AND is_active = true
            ORDER BY created_at DESC LIMIT 1
            """
        ),
        {"role": role, "model": model},
    )
    row = result.first()
    return str(row[0]) if row else None


async def adjudicate_finding(
    session: AsyncSession,
    finding_id: str,
    settings: Settings,
    *,
    force_round: int = 1,
) -> GateDecision:
    """Runs the 3-model panel adjudication on a finding and transitions its status."""
    # 1. Circuit breaker check
    if await is_circuit_breaker_open(session, "model_panel"):
        raise CircuitBreakerOpen("model_panel circuit breaker is open")

    # 2. Fetch finding details and descriptions
    query_finding = """
        SELECT f.id, f.category, f.incident_date, f.status, f.clearance_tier,
               f.public_summary, c.code AS course_code, c.title AS course_title
        FROM findings f
        JOIN courses c ON c.id = f.course_id
        WHERE f.id = :finding_id
    """
    f_res = await session.execute(text(query_finding), {"finding_id": finding_id})
    f_row = f_res.first()
    if f_row is None:
        raise ValueError(f"Finding {finding_id} not found")

    finding_data = dict(f_row._mapping)
    course_code = finding_data["course_code"]
    course_title = finding_data["course_title"]
    category = finding_data["category"]
    incident_date = finding_data["incident_date"].isoformat()
    clearance_tier = finding_data["clearance_tier"]

    # Gather all descriptions from reports and confirmations
    desc_query = """
        SELECT description FROM reports WHERE finding_id = :finding_id
        UNION ALL
        SELECT comment FROM finding_confirmations WHERE finding_id = :finding_id AND comment IS NOT NULL
    """
    desc_res = await session.execute(text(desc_query), {"finding_id": finding_id})
    descriptions = [str(r[0]) for r in desc_res.all() if r[0]]

    if not descriptions:
        descriptions = [f"Class {category} claimed on {incident_date}"]

    # 3. Resolve Model Registry IDs
    safety_model_id = await get_model_id(session, role="safety", model=settings.groq_safety_model)
    consistency_model_id = await get_model_id(
        session, role="consistency", model=settings.groq_consistency_model
    )
    red_team_model_id = await get_model_id(
        session, role="red_team", model=settings.groq_red_team_model
    )

    if not (safety_model_id and consistency_model_id and red_team_model_id):
        raise PanelUnavailable("One or more required model panel roles are not in model_registry")

    # 4. Run the 3-model panel
    safety_vote_res = await model_panel.safety_vote(
        settings, report_text="\n---\n".join(descriptions)
    )
    consistency_vote_res = await model_panel.consistency_vote(
        settings,
        course_code=course_code,
        course_title=course_title,
        category=category,
        incident_date=incident_date,
        descriptions=descriptions,
    )
    red_team_vote_res = await model_panel.red_team_vote(settings, descriptions=descriptions)

    votes = [safety_vote_res, consistency_vote_res, red_team_vote_res]
    model_ids = {
        "safety": safety_model_id,
        "consistency": consistency_model_id,
        "red_team": red_team_model_id,
    }

    # Record panel votes
    for v in votes:
        mid = model_ids[v.role]
        effective_verdict = v.verdict
        if v.confidence < settings.panel_min_confidence:
            effective_verdict = "abstain"

        await session.execute(
            text(
                """
                INSERT INTO panel_votes (subject_type, subject_id, round, role, model_id, verdict, confidence, reasons)
                VALUES ('finding', :subject_id, :round, :role::panel_role, :model_id, :verdict::vote_verdict, :confidence, :reasons)
                ON CONFLICT (subject_type, subject_id, round, role, model_id)
                DO UPDATE SET verdict = EXCLUDED.verdict, confidence = EXCLUDED.confidence, reasons = EXCLUDED.reasons
                """
            ),
            {
                "subject_id": finding_id,
                "round": force_round,
                "role": v.role,
                "model_id": mid,
                "verdict": effective_verdict,
                "confidence": v.confidence,
                "reasons": json.dumps({"reasons": v.reasons}),
            },
        )

    # 5. Deterministic Gate Decision Rules
    now = datetime.now(UTC)
    has_block = any(v.verdict == "block" and v.confidence >= settings.panel_min_confidence for v in votes)
    all_pass = all(v.verdict == "pass" and v.confidence >= settings.panel_min_confidence for v in votes)

    public_summary = finding_data.get("public_summary")
    held_until = None
    cleared_at = None

    if has_block:
        new_status = "rejected"
        details = {
            "verdict": "rejected",
            "reason": "blocked_by_panel",
            "votes": [{"role": v.role, "verdict": v.verdict, "confidence": v.confidence} for v in votes],
        }
    elif all_pass:
        new_status = "cleared"
        cleared_at = now
        try:
            public_summary = await model_panel.generate_public_summary(
                settings,
                course_code=course_code,
                course_title=course_title,
                category=category,
                incident_date=incident_date,
                supporters_count=len(descriptions),
                descriptions=descriptions,
            )
        except Exception:
            # Fallback to deterministic template summary if LLM summary call fails
            public_summary = f"Academic concern regarding {course_code} on {incident_date} corroborated by enrolled students."

        details = {
            "verdict": "cleared",
            "reason": "unanimous_panel_pass",
            "public_summary": public_summary,
            "votes": [{"role": v.role, "verdict": v.verdict, "confidence": v.confidence} for v in votes],
        }
    else:
        new_status = "held"
        held_until = now + timedelta(days=settings.hold_ttl_days)
        details = {
            "verdict": "held",
            "reason": "uncertain_or_abstain",
            "held_until": held_until.isoformat(),
            "votes": [{"role": v.role, "verdict": v.verdict, "confidence": v.confidence} for v in votes],
        }

    # 6. Update Finding in database
    await session.execute(
        text(
            """
            UPDATE findings
            SET status = :status::finding_status,
                public_summary = COALESCE(:public_summary, public_summary),
                held_until = :held_until,
                cleared_at = COALESCE(:cleared_at, cleared_at)
            WHERE id = :finding_id
            """
        ),
        {
            "finding_id": finding_id,
            "status": new_status,
            "public_summary": public_summary,
            "held_until": held_until,
            "cleared_at": cleared_at,
        },
    )

    # 7. Record decision in decision_log
    await audit.record_decision(
        session,
        finding_id=finding_id,
        stage="gate",
        actor="gate_v1",
        decision=new_status,
        details=details,
    )

    return GateDecision(
        finding_id=finding_id,
        status=new_status,
        clearance_tier=clearance_tier,
        public_summary=public_summary,
        held_until=held_until,
        cleared_at=cleared_at,
        votes=votes,
        details=details,
    )
