from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vio_backend.config import Settings
from vio_backend.gate import (
    CircuitBreakerOpen,
    adjudicate_finding,
    is_circuit_breaker_open,
)
from vio_backend.model_panel import Vote


def dummy_settings() -> Settings:
    return Settings(
        database_url=None,
        identity_hash_secret="test-secret",
        session_secret="test-session-secret",
        smtp_host=None,
        smtp_port=587,
        smtp_username=None,
        smtp_password=None,
        smtp_from_address=None,
        challenge_ttl_minutes=10,
        challenge_resend_cooldown_seconds=60,
        challenge_max_attempts=5,
        challenge_max_per_hour=5,
        session_ttl_days=30,
        groq_api_key="mock-key",
    )


def make_exec_side_effect(mock_breaker, mock_finding, mock_desc, mock_model_id):
    mock_last_hash = MagicMock()
    mock_last_hash.first.return_value = None
    mock_insert_log = MagicMock()
    mock_insert_log.scalar_one.return_value = 1
    return [
        mock_breaker,   # circuit breaker check
        mock_finding,   # finding query
        mock_desc,      # descriptions query
        mock_model_id,  # safety model ID
        mock_model_id,  # consistency model ID
        mock_model_id,  # red_team model ID
        MagicMock(),    # insert safety vote
        MagicMock(),    # insert consistency vote
        MagicMock(),    # insert red_team vote
        MagicMock(),    # update finding status
        mock_last_hash, # last entry_hash for decision_log
        mock_insert_log,# insert decision_log
    ]


@pytest.mark.asyncio
async def test_gate_trips_when_circuit_breaker_is_open():
    session = AsyncMock()
    mock_res = MagicMock()
    mock_res.first.return_value = ["open"]
    session.execute.return_value = mock_res

    with pytest.raises(CircuitBreakerOpen):
        await adjudicate_finding(session, "f1", dummy_settings())


@pytest.mark.asyncio
async def test_gate_unanimous_pass_clears_finding():
    session = AsyncMock()

    mock_breaker = MagicMock()
    mock_breaker.first.return_value = ["closed"]

    mock_finding = MagicMock()
    mock_finding.first.return_value._mapping = {
        "id": "f1",
        "category": "class_not_held",
        "incident_date": date(2026, 10, 12),
        "status": "collecting",
        "clearance_tier": 1,
        "public_summary": None,
        "course_code": "MTE301",
        "course_title": "Mechatronics",
    }

    mock_desc = MagicMock()
    mock_desc.all.return_value = [("The class did not hold at 8am.",)]

    mock_model_id = MagicMock()
    mock_model_id.first.return_value = ["00000000-0000-0000-0000-000000000001"]

    session.execute.side_effect = make_exec_side_effect(
        mock_breaker, mock_finding, mock_desc, mock_model_id
    )

    with patch("vio_backend.model_panel.safety_vote", return_value=Vote("safety", "pass", 0.95)), \
         patch("vio_backend.model_panel.consistency_vote", return_value=Vote("consistency", "pass", 0.90)), \
         patch("vio_backend.model_panel.red_team_vote", return_value=Vote("red_team", "pass", 0.92)), \
         patch("vio_backend.model_panel.generate_public_summary", return_value="Class MTE301 was reported not held on 2026-10-12."):

        decision = await adjudicate_finding(session, "f1", dummy_settings())

    assert decision.status == "cleared"
    assert decision.cleared_at is not None
    assert decision.public_summary == "Class MTE301 was reported not held on 2026-10-12."


@pytest.mark.asyncio
async def test_gate_block_rejects_finding():
    session = AsyncMock()

    mock_breaker = MagicMock()
    mock_breaker.first.return_value = ["closed"]

    mock_finding = MagicMock()
    mock_finding.first.return_value._mapping = {
        "id": "f1",
        "category": "poor_delivery",
        "incident_date": date(2026, 10, 12),
        "status": "collecting",
        "clearance_tier": 1,
        "public_summary": None,
        "course_code": "MTE301",
        "course_title": "Mechatronics",
    }

    mock_desc = MagicMock()
    mock_desc.all.return_value = [("Malicious abusive text.",)]

    mock_model_id = MagicMock()
    mock_model_id.first.return_value = ["00000000-0000-0000-0000-000000000001"]

    session.execute.side_effect = make_exec_side_effect(
        mock_breaker, mock_finding, mock_desc, mock_model_id
    )

    # Safety blocks!
    with patch("vio_backend.model_panel.safety_vote", return_value=Vote("safety", "block", 0.95)), \
         patch("vio_backend.model_panel.consistency_vote", return_value=Vote("consistency", "pass", 0.90)), \
         patch("vio_backend.model_panel.red_team_vote", return_value=Vote("red_team", "pass", 0.92)):

        decision = await adjudicate_finding(session, "f1", dummy_settings())

    assert decision.status == "rejected"


@pytest.mark.asyncio
async def test_gate_low_confidence_holds_finding():
    session = AsyncMock()

    mock_breaker = MagicMock()
    mock_breaker.first.return_value = ["closed"]

    mock_finding = MagicMock()
    mock_finding.first.return_value._mapping = {
        "id": "f1",
        "category": "outline_incomplete",
        "incident_date": date(2026, 10, 12),
        "status": "collecting",
        "clearance_tier": 1,
        "public_summary": None,
        "course_code": "MTE301",
        "course_title": "Mechatronics",
    }

    mock_desc = MagicMock()
    mock_desc.all.return_value = [("Uncertain complaint details.",)]

    mock_model_id = MagicMock()
    mock_model_id.first.return_value = ["00000000-0000-0000-0000-000000000001"]

    session.execute.side_effect = make_exec_side_effect(
        mock_breaker, mock_finding, mock_desc, mock_model_id
    )

    # Confidence below 0.80 counts as abstain -> finding is held
    with patch("vio_backend.model_panel.safety_vote", return_value=Vote("safety", "pass", 0.95)), \
         patch("vio_backend.model_panel.consistency_vote", return_value=Vote("consistency", "pass", 0.60)), \
         patch("vio_backend.model_panel.red_team_vote", return_value=Vote("red_team", "pass", 0.92)):

        decision = await adjudicate_finding(session, "f1", dummy_settings())

    assert decision.status == "held"
    assert decision.held_until is not None
