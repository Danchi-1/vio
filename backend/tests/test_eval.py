from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vio_backend.config import Settings
from vio_backend.eval_service import (
    reset_circuit_breaker,
    run_safety_eval,
    trip_circuit_breaker,
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


@pytest.mark.asyncio
async def test_trip_and_reset_circuit_breaker():
    session = AsyncMock()
    # Mock last entry_hash for decision_log
    mock_hash = MagicMock()
    mock_hash.first.return_value = None
    mock_hash.scalar_one.return_value = 1
    session.execute.return_value = mock_hash

    await trip_circuit_breaker(session, name="model_panel", reason="High drift detected")
    session.execute.assert_called()

    await reset_circuit_breaker(session, name="model_panel")
    session.execute.assert_called()


@pytest.mark.asyncio
async def test_run_safety_eval_passes_when_accurate():
    session = AsyncMock()

    # Empty golden_cases table -> uses DEFAULT_CANARY_CASES (4 cases)
    mock_cases = MagicMock()
    mock_cases.all.return_value = []

    # Model ID query
    mock_model_id = MagicMock()
    mock_model_id.first.return_value = ["00000000-0000-0000-0000-000000000001"]

    session.execute.side_effect = [
        mock_cases,     # golden_cases query
        mock_model_id,  # model_id query
        MagicMock(),    # insert eval_runs
    ]

    # Mock safety model votes: 2 genuine (pass), 1 abusive (block), 1 injection (block)
    mock_votes = [
        Vote("safety", "pass", 0.95),
        Vote("safety", "pass", 0.90),
        Vote("safety", "block", 0.99),
        Vote("safety", "block", 0.98),
    ]

    with patch("vio_backend.model_panel.safety_vote", side_effect=mock_votes):
        res = await run_safety_eval(session, dummy_settings(), min_accuracy=0.75)

    assert res["passed"] is True
    assert res["accuracy"] == 1.0
    assert res["correct"] == 4


@pytest.mark.asyncio
async def test_run_safety_eval_trips_breaker_when_inaccurate():
    session = AsyncMock()

    mock_cases = MagicMock()
    mock_cases.all.return_value = []

    mock_model_id = MagicMock()
    mock_model_id.first.return_value = ["00000000-0000-0000-0000-000000000001"]

    mock_last_hash = MagicMock()
    mock_last_hash.first.return_value = None

    mock_insert_log = MagicMock()
    mock_insert_log.scalar_one.return_value = 1

    session.execute.side_effect = [
        mock_cases,         # golden_cases query
        mock_model_id,      # model_id query
        MagicMock(),        # insert eval_runs
        MagicMock(),        # update circuit_breakers (trip)
        mock_last_hash,     # last entry_hash for decision_log
        mock_insert_log,    # insert decision_log RETURNING id
    ]

    # Inaccurate model: predicts pass for everything (fails on abusive and injection)
    mock_votes = [
        Vote("safety", "pass", 0.95),
        Vote("safety", "pass", 0.90),
        Vote("safety", "pass", 0.99),  # WRONG (expected block)
        Vote("safety", "pass", 0.98),  # WRONG (expected block)
    ]

    with patch("vio_backend.model_panel.safety_vote", side_effect=mock_votes):
        res = await run_safety_eval(session, dummy_settings(), min_accuracy=0.75)

    assert res["passed"] is False
    assert res["accuracy"] == 0.50
    # Breaker trip was called
    assert session.execute.call_count >= 4
