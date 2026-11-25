from dataclasses import dataclass
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from vio_backend import gate, report_store
from vio_backend.config import Settings
from vio_backend.database import session_dependency
from vio_backend.email_delivery import ConsoleEmailSender, NullEmailSender, build_email_sender
from vio_backend.gate import GateDecision
from vio_backend.main import app
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


def test_spec_dashboard_overview_matches_frontend_contract():
    dept_id = uuid4()
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.mappings.return_value.all.return_value = [
        {
            "department_id": dept_id,
            "department": "Computer Science",
            "category": "class_not_held",
            "month": date(2026, 10, 1),
            "findings": 4,
        }
    ]
    mock_session.execute.return_value = mock_res

    async def override_session():
        yield mock_session

    app.dependency_overrides[session_dependency] = override_session
    try:
        with TestClient(app) as client:
            res = client.get("/api/v1/dashboard/overview?month=2026-10")
        assert res.status_code == 200
        assert res.json() == {
            "data": {
                "rows": [
                    {
                        "department_id": str(dept_id),
                        "department_name": "Computer Science",
                        "month": "2026-10",
                        "category": "class_not_held",
                        "count": 4,
                    }
                ]
            }
        }
    finally:
        app.dependency_overrides.pop(session_dependency, None)


def test_spec_public_track_report_hides_identity_and_returns_timeline():
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.first.return_value._mapping = {
        "tracking_code": "VIO-ABCD2345",
        "created_at": datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc),
        "finding_status": "published",
        "category": "class_not_held",
        "public_summary": "Students reported an unannounced cancellation.",
        "clearance_tier": 1,
        "course_code": "CSC 201",
        "course_title": "Computer Programming I",
        "department": "Computer Science",
        "incident_date": date(2026, 10, 12),
    }
    mock_session.execute.return_value = mock_res

    async def override_session():
        yield mock_session

    app.dependency_overrides[session_dependency] = override_session
    try:
        with TestClient(app) as client:
            res = client.get("/api/v1/reports/track/VIO-ABCD2345")
        assert res.status_code == 200
        body = res.json()["data"]
        assert body["tracking_code"] == "VIO-ABCD2345"
        assert body["finding_status"] == "published"
        assert len(body["timeline"]) == 3
        assert "reporter_id" not in body
        assert "description" not in body
    finally:
        app.dependency_overrides.pop(session_dependency, None)


@pytest.mark.asyncio
async def test_get_student_report_by_tracking_includes_course_level_for_report_json():
    from vio_backend.routers.reports import _report_json

    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.first.return_value._mapping = {
        "id": "r1",
        "tracking_code": "VIO-ABCD2345",
        "description": "Lecture did not hold.",
        "notice_given": False,
        "created_at": datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc),
        "finding_id": "f1",
        "finding_status": "collecting",
        "category": "class_not_held",
        "public_summary": None,
        "clearance_tier": 0,
        "course_code": "CSC 201",
        "course_title": "Computer Programming I",
        "course_level": 200,
        "department": "Computer Science",
        "incident_date": date(2026, 10, 12),
    }
    mock_session.execute.return_value = mock_res

    row = await report_store.get_student_report_by_tracking(mock_session, "stu-1", "VIO-ABCD2345")
    assert row is not None
    sql = str(mock_session.execute.call_args[0][0])
    assert "c.level AS course_level" in sql
    formatted = _report_json(row)
    assert formatted["course_level"] == 200
