from datetime import date, timedelta

from vio_backend.scoring import (
    SupporterInput,
    calculate_finding_score,
    compute_anomaly_multiplier,
    compute_false_reliability,
    compute_recency_multiplier,
    compute_supporter_contribution,
)


def test_recency_multiplier_intervals():
    today = date(2026, 11, 23)
    # 0 to 21 days
    assert compute_recency_multiplier(today, today) == 1.00
    assert compute_recency_multiplier(today - timedelta(days=21), today) == 1.00
    # 22 to 60 days
    assert compute_recency_multiplier(today - timedelta(days=22), today) == 0.75
    assert compute_recency_multiplier(today - timedelta(days=60), today) == 0.75
    # 61 to 180 days
    assert compute_recency_multiplier(today - timedelta(days=61), today) == 0.50
    assert compute_recency_multiplier(today - timedelta(days=180), today) == 0.50
    # 181 to 365 days
    assert compute_recency_multiplier(today - timedelta(days=181), today) == 0.25
    assert compute_recency_multiplier(today - timedelta(days=365), today) == 0.25
    # > 365 days
    assert compute_recency_multiplier(today - timedelta(days=366), today) == 0.10


def test_false_reliability_calculation():
    assert compute_false_reliability(0) == 1.00
    assert round(compute_false_reliability(1), 2) == 0.90
    assert round(compute_false_reliability(2), 3) == 0.810
    # Floored at 0.50
    assert compute_false_reliability(15) == 0.50


def test_anomaly_multiplier():
    assert compute_anomaly_multiplier([]) == 1.00
    assert round(compute_anomaly_multiplier([0.20]), 2) == 0.80
    assert round(compute_anomaly_multiplier([0.10, 0.40]), 2) == 0.60
    # Floored at 0.25
    assert compute_anomaly_multiplier([0.95]) == 0.25


def test_supporter_contribution_with_verified_email():
    contrib, trust, a_mult, f_rel = compute_supporter_contribution(
        has_verified_email=True, severities=[], false_finding_count=0
    )
    # Trust is 0.10 base + 0.55 email = 0.65
    # Contribution is 0.65 * 0.25 = 0.1625
    assert trust == 0.65
    assert contrib == 0.1625
    assert a_mult == 1.00
    assert f_rel == 1.00


def test_supporter_contribution_without_verified_email():
    contrib, trust, a_mult, f_rel = compute_supporter_contribution(
        has_verified_email=False, severities=[], false_finding_count=0
    )
    # Trust is 0.10 base
    # Contribution is 0.10 * 0.25 = 0.025
    assert trust == 0.10
    assert contrib == 0.025


def test_tier_1_requires_five_distinct_reports():
    incident = date(2026, 11, 20)
    today = date(2026, 11, 23)

    # 4 reports + 4 confirmers (total 8 supporters, score > 0.80, but distinct reports = 4)
    supporters = [
        SupporterInput(f"rep_{i}", "reporter", True, [], 0) for i in range(4)
    ] + [
        SupporterInput(f"conf_{i}", "confirmer", True, [], 0) for i in range(4)
    ]

    result = calculate_finding_score(
        incident_date=incident,
        as_of=today,
        announced_in_advance=False,
        supporters=supporters,
    )

    # 8 * 0.1625 = 1.30. Meets Tier 2 (8 supporters, score >= 1.30),
    # but does NOT meet Tier 1 report floor (only 4 reports).
    # Since Tier 2 is met, clearance_tier is 2.
    assert result.distinct_reports == 4
    assert result.total_supporters == 8
    assert result.clearance_tier == 2


def test_tier_1_reached_with_five_reports():
    incident = date(2026, 11, 20)
    today = date(2026, 11, 23)

    supporters = [
        SupporterInput(f"rep_{i}", "reporter", True, [], 0) for i in range(5)
    ]

    result = calculate_finding_score(
        incident_date=incident,
        as_of=today,
        announced_in_advance=False,
        supporters=supporters,
    )

    # 5 * 0.1625 = 0.8125 (rounds to 0.812 using round-to-even)
    assert result.distinct_reports == 5
    assert result.total_supporters == 5
    assert result.score == 0.812
    assert result.clearance_tier == 1


def test_advance_notice_discounts_finding_score():
    incident = date(2026, 11, 20)
    today = date(2026, 11, 23)

    supporters = [
        SupporterInput(f"rep_{i}", "reporter", True, [], 0) for i in range(5)
    ]

    result = calculate_finding_score(
        incident_date=incident,
        as_of=today,
        announced_in_advance=True,  # 0.50 multiplier
        supporters=supporters,
    )

    # 0.8125 * 0.50 = 0.40625 -> rounds to 0.406
    assert result.score == 0.406
    # Score is < 0.80 so Tier 1 is NOT reached
    assert result.clearance_tier == 0
