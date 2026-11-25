from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vio_backend import gate
from vio_backend.config import Settings
from vio_backend.email_delivery import ConsoleEmailSender, NullEmailSender, build_email_sender
from vio_backend.gate import GateDecision
from vio_backend.model_panel import PanelUnavailable, Vote


def _settings() -> Settings:
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
async def test_evaluate_and_adjudicate_skips_below_tier_1():
    session = AsyncMock()
    status = await gate.evaluate_and_adjudicate(
        session,
        "f1",
        _settings(),
        clearance_tier=0,
        previous_status="collecting",
        previous_tier=0,
    )
    assert status == "collecting"
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_and_adjudicate_publishes_when_publish_breaker_closed():
    session = AsyncMock()
    mock_hash = MagicMock()
    mock_hash.first.return_value = None
    mock_hash.scalar_one.return_value = 1
    session.execute.return_value = mock_hash

    cleared = GateDecision(
        finding_id="f1",
        status="cleared",
        clearance_tier=1,
        public_summary="Summary",
        held_until=None,
        cleared_at=None,
        votes=[Vote("safety", "pass", 0.95)],
        details={},
    )

    with patch("vio_backend.gate.adjudicate_finding", return_value=cleared), \
         patch("vio_backend.gate.is_circuit_breaker_open", return_value=False):
        status = await gate.evaluate_and_adjudicate(
            session,
            "f1",
            _settings(),
            clearance_tier=1,
            previous_status="collecting",
            previous_tier=0,
        )

    assert status == "published"


@pytest.mark.asyncio
async def test_evaluate_and_adjudicate_queues_delivery_on_tier_2():
    session = AsyncMock()
    mock_hash = MagicMock()
    mock_hash.first.return_value = None
    mock_hash.scalar_one.return_value = 1
    session.execute.return_value = mock_hash

    cleared = GateDecision(
        finding_id="f1",
        status="cleared",
        clearance_tier=2,
        public_summary="Summary",
        held_until=None,
        cleared_at=None,
        votes=[Vote("safety", "pass", 0.95)],
        details={},
    )

    with patch("vio_backend.gate.adjudicate_finding", return_value=cleared), \
         patch("vio_backend.gate.is_circuit_breaker_open", return_value=False), \
         patch("vio_backend.delivery_store.queue_delivery_for_step", return_value=("d1", "tok")) as mock_q:
        status = await gate.evaluate_and_adjudicate(
            session,
            "f1",
            _settings(),
            clearance_tier=2,
            previous_status="published",
            previous_tier=1,
        )

    assert status == "published"
    mock_q.assert_awaited_once_with(session, finding_id="f1", step_order=1)


@pytest.mark.asyncio
async def test_evaluate_and_adjudicate_stops_at_cleared_when_publish_breaker_open():
    session = AsyncMock()
    cleared = GateDecision(
        finding_id="f1",
        status="cleared",
        clearance_tier=1,
        public_summary="Summary",
        held_until=None,
        cleared_at=None,
        votes=[Vote("safety", "pass", 0.95)],
        details={},
    )

    with patch("vio_backend.gate.adjudicate_finding", return_value=cleared), \
         patch("vio_backend.gate.is_circuit_breaker_open", return_value=True):
        status = await gate.evaluate_and_adjudicate(
            session,
            "f1",
            _settings(),
            clearance_tier=1,
            previous_status="collecting",
            previous_tier=0,
        )

    assert status == "cleared"
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_and_adjudicate_fails_closed_to_held_on_panel_outage():
    session = AsyncMock()
    mock_res = MagicMock()
    mock_res.first.return_value = None
    mock_res.scalar_one.return_value = 1
    session.execute.return_value = mock_res

    with patch("vio_backend.gate.adjudicate_finding", side_effect=PanelUnavailable("timeout")):
        status = await gate.evaluate_and_adjudicate(
            session,
            "f1",
            _settings(),
            clearance_tier=1,
            previous_status="collecting",
            previous_tier=0,
        )

    assert status == "held"
    assert session.execute.call_count >= 2


@dataclass
class _EmailSettings:
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None
    email_mode: str = "smtp"


def test_email_mode_console_opt_in_only():
    assert isinstance(build_email_sender(_EmailSettings(email_mode="smtp")), NullEmailSender)
    assert isinstance(build_email_sender(_EmailSettings(email_mode="console")), ConsoleEmailSender)
