"""Deterministic scoring engine for findings and confirmations (M4).

Follows docs/DECISIONS.md (2026-11-07, 2026-11-09):
- Trust is base 0.10 + verified school email 0.55 (= 0.65 for email-verified students).
  Timetable provides 0.00 personal trust and is used for eligibility only.
- Supporter contribution:
    contribution_i = min(0.20, trust_i * 0.25 * anomaly_multiplier_i * false_reliability_i)
- False reliability:
    max(0.50, 0.90 ** finalized_false_finding_count)
- Anomaly multiplier:
    1.0 - max(severity), floored at 0.25
- Finding modifiers:
    Recency pursuit multiplier:
      0-21 days: 1.00
      22-60 days: 0.75
      61-180 days: 0.50
      181-365 days: 0.25
      >365 days: 0.10
    Advance notice multiplier:
      0.50 if announced in advance, else 1.00
- Tier thresholds:
    Tier 1: distinct_reports >= 5 AND score >= 0.80
    Tier 2: total_supporters >= 8 AND score >= 1.30
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

FORMULA_VERSION = "v1-balanced"

BASE_TRUST = 0.10
SCHOOL_EMAIL_TRUST = 0.55
CONTRIBUTION_NORMALIZATION = 0.25
PER_SUPPORTER_CAP = 0.20
ANOMALY_MULTIPLIER_FLOOR = 0.25
ADVANCE_NOTICE_MULTIPLIER = 0.50

TIER_1_MIN_REPORTS = 5
TIER_1_MIN_SCORE = 0.80
TIER_2_MIN_SUPPORTERS = 8
TIER_2_MIN_SCORE = 1.30


def compute_recency_multiplier(incident_date: date, as_of: date) -> float:
    days = (as_of - incident_date).days
    if days < 0:
        # Incident claimed today or edge case in same day
        return 1.00
    if days <= 21:
        return 1.00
    if days <= 60:
        return 0.75
    if days <= 180:
        return 0.50
    if days <= 365:
        return 0.25
    return 0.10


def compute_false_reliability(false_finding_count: int) -> float:
    if false_finding_count <= 0:
        return 1.00
    factor = 0.90 ** false_finding_count
    return max(0.50, factor)


def compute_anomaly_multiplier(severities: list[float]) -> float:
    if not severities:
        return 1.00
    max_severity = max(severities)
    multiplier = 1.0 - max_severity
    return max(ANOMALY_MULTIPLIER_FLOOR, multiplier)


def compute_supporter_contribution(
    *,
    has_verified_email: bool,
    severities: list[float],
    false_finding_count: int,
) -> tuple[float, float, float, float]:
    """Returns (contribution, trust, anomaly_multiplier, false_reliability)."""
    trust = BASE_TRUST + (SCHOOL_EMAIL_TRUST if has_verified_email else 0.0)
    anomaly_mult = compute_anomaly_multiplier(severities)
    false_rel = compute_false_reliability(false_finding_count)
    raw = trust * CONTRIBUTION_NORMALIZATION * anomaly_mult * false_rel
    contribution = min(PER_SUPPORTER_CAP, raw)
    return round(contribution, 4), round(trust, 2), round(anomaly_mult, 3), round(false_rel, 3)


@dataclass(frozen=True)
class SupporterInput:
    student_id: str
    role: str  # "reporter" or "confirmer"
    has_verified_email: bool
    anomaly_severities: list[float]
    false_finding_count: int


@dataclass(frozen=True)
class ScoreResult:
    score: float
    distinct_reports: int
    distinct_confirmations: int
    total_supporters: int
    clearance_tier: int
    breakdown: dict[str, Any]


def calculate_finding_score(
    *,
    incident_date: date,
    as_of: date,
    announced_in_advance: bool,
    supporters: list[SupporterInput],
) -> ScoreResult:
    reports_count = sum(1 for s in supporters if s.role == "reporter")
    confirmations_count = sum(1 for s in supporters if s.role == "confirmer")
    total_supporters = len(supporters)

    recency_days = max(0, (as_of - incident_date).days)
    recency_mult = compute_recency_multiplier(incident_date, as_of)
    notice_mult = ADVANCE_NOTICE_MULTIPLIER if announced_in_advance else 1.00

    supporter_breakdowns = []
    base_supporter_score = 0.0

    for s in supporters:
        contrib, trust, a_mult, f_rel = compute_supporter_contribution(
            has_verified_email=s.has_verified_email,
            severities=s.anomaly_severities,
            false_finding_count=s.false_finding_count,
        )
        base_supporter_score += contrib
        supporter_breakdowns.append(
            {
                "student_id": s.student_id,
                "role": s.role,
                "trust": trust,
                "anomaly_multiplier": a_mult,
                "false_reliability": f_rel,
                "contribution": contrib,
            }
        )

    final_score = round(base_supporter_score * recency_mult * notice_mult, 3)

    tier_1_reached = (reports_count >= TIER_1_MIN_REPORTS) and (final_score >= TIER_1_MIN_SCORE)
    tier_2_reached = (total_supporters >= TIER_2_MIN_SUPPORTERS) and (final_score >= TIER_2_MIN_SCORE)

    if tier_2_reached:
        clearance_tier = 2
    elif tier_1_reached:
        clearance_tier = 1
    else:
        clearance_tier = 0

    breakdown = {
        "formula_version": FORMULA_VERSION,
        "distinct_reports": reports_count,
        "distinct_confirmations": confirmations_count,
        "total_supporters": total_supporters,
        "base_supporter_score": round(base_supporter_score, 4),
        "recency_days": recency_days,
        "recency_multiplier": recency_mult,
        "announced_in_advance": announced_in_advance,
        "advance_notice_multiplier": notice_mult,
        "final_score": final_score,
        "clearance_tier": clearance_tier,
        "tier_1_reached": tier_1_reached,
        "tier_2_reached": tier_2_reached,
        "supporters": supporter_breakdowns,
    }

    return ScoreResult(
        score=final_score,
        distinct_reports=reports_count,
        distinct_confirmations=confirmations_count,
        total_supporters=total_supporters,
        clearance_tier=clearance_tier,
        breakdown=breakdown,
    )
