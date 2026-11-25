from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vio_backend.reply_assessment import AssessmentAction, ReplyReason, assess_reply
from vio_backend.delivery_store import (
    generate_delivery_token,
    hash_token,
    process_overdue_escalations,
    redeem_delivery_token,
    save_lecturer_reply,
)
from vio_backend.link_auth import (
    create_authority_session_token,
    create_lecturer_session_token,
    verify_signed_token,
)


def test_token_generation_and_hashing():
    raw, hashed = generate_delivery_token()
    assert len(raw) >= 32
    assert len(hashed) == 32
    assert hash_token(raw) == hashed


def test_authority_and_lecturer_signed_sessions():
    secret = "test-secret-12345"
    auth_token = create_authority_session_token(
        secret,
        authority_id="auth-1",
        delivery_id="deliv-1",
        role="hod",
        ttl_hours=1,
    )
    payload = verify_signed_token(secret, auth_token)
    assert payload is not None
    assert payload["authority_id"] == "auth-1"
    assert payload["delivery_id"] == "deliv-1"
    assert payload["role"] == "hod"

    # Tampered signature fails
    assert verify_signed_token("wrong-secret", auth_token) is None
    assert verify_signed_token(secret, auth_token + "tamper") is None

    # Lecturer session
    lec_token = create_lecturer_session_token(
        secret,
        lecturer_id="lec-1",
        email="prof@funaab.edu.ng",
        department_id="dept-1",
        ttl_hours=1,
    )
    lec_payload = verify_signed_token(secret, lec_token)
    assert lec_payload is not None
    assert lec_payload["lecturer_id"] == "lec-1"
    assert lec_payload["email"] == "prof@funaab.edu.ng"


@pytest.mark.asyncio
async def test_redeem_delivery_token_expired():
    session = AsyncMock()
    mock_row = MagicMock()
    mock_row._mapping = {
        "delivery_id": "d1",
        "finding_id": "f1",
        "authority_id": "a1",
        "step_order": 1,
        "status": "sent",
        "due_at": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired!
        "viewed_at": None,
        "acknowledged_at": None,
        "responded_at": None,
        "authority_role": "hod",
        "authority_name": "Dr. Ade",
        "category": "class_not_held",
        "incident_date": date(2026, 10, 1),
        "clearance_tier": 1,
        "public_summary": "Summary",
        "course_code": "MTS201",
        "course_title": "Calculus",
        "department_name": "Math",
    }
    mock_res = MagicMock()
    mock_res.first.return_value = mock_row
    session.execute.return_value = mock_res

    data, err = await redeem_delivery_token(session, "a" * 32)
    assert data is None
    assert err == "expired_link"


@pytest.mark.asyncio
async def test_redeem_delivery_token_already_used():
    session = AsyncMock()
    mock_row = MagicMock()
    mock_row._mapping = {
        "delivery_id": "d1",
        "finding_id": "f1",
        "authority_id": "a1",
        "step_order": 1,
        "status": "viewed",
        "due_at": datetime.now(timezone.utc) + timedelta(days=5),
        "viewed_at": datetime.now(timezone.utc) - timedelta(hours=2),  # Already viewed!
        "acknowledged_at": None,
        "responded_at": None,
        "authority_role": "hod",
        "authority_name": "Dr. Ade",
        "category": "class_not_held",
        "incident_date": date(2026, 10, 1),
        "clearance_tier": 1,
        "public_summary": "Summary",
        "course_code": "MTS201",
        "course_title": "Calculus",
        "department_name": "Math",
    }
    mock_res = MagicMock()
    mock_res.first.return_value = mock_row
    session.execute.return_value = mock_res

    data, err = await redeem_delivery_token(session, "a" * 32)
    assert data is None
    assert err == "link_already_used"


def test_assess_reply_dispute_refers_to_appeals():
    assessment = assess_reply(ReplyReason.DISPUTED, "I held this class in the physics lab.")
    assert assessment.action == AssessmentAction.REFER_TO_APPEALS
    assert assessment.reason == ReplyReason.DISPUTED


def test_assess_reply_illness_records_explanation():
    assessment = assess_reply(ReplyReason.ILLNESS, "I was hospitalized on that day.")
    assert assessment.action == AssessmentAction.RECORD_EXPLANATION


def test_assess_reply_rescheduled_verifies_evidence():
    assessment = assess_reply(ReplyReason.RESCHEDULED, "The class was moved to Wednesday 2pm.")
    assert assessment.action == AssessmentAction.VERIFY_EVIDENCE


@pytest.mark.asyncio
async def test_save_lecturer_reply_records_and_appeals_if_disputed():
    session = AsyncMock()

    # Mock insert lecturer_replies
    mock_reply_ins = MagicMock()
    mock_reply_ins.scalar_one.return_value = "00000000-0000-0000-0000-000000000001"

    # Mock decision log & appeal insert
    mock_hash = MagicMock()
    mock_hash.first.return_value = None
    mock_hash.scalar_one.return_value = 1

    session.execute.side_effect = [
        mock_reply_ins,  # INSERT INTO lecturer_replies
        mock_hash,       # SELECT entry_hash from decision_log
        mock_hash,       # INSERT INTO decision_log RETURNING id
        mock_reply_ins,  # INSERT INTO appeals (since DISPUTED)
        MagicMock(),     # UPDATE findings SET status = 'disputed'
        mock_hash,       # SELECT entry_hash from decision_log
        mock_hash,       # INSERT INTO decision_log RETURNING id
    ]

    reply_id, action = await save_lecturer_reply(
        session,
        finding_id="f1",
        lecturer_id="l1",
        reason=ReplyReason.DISPUTED,
        body="This lecture held at the scheduled venue.",
    )

    assert reply_id == "00000000-0000-0000-0000-000000000001"
    assert action == "refer_to_appeals"


@pytest.mark.asyncio
async def test_process_overdue_escalations_advances_to_next_step():
    session = AsyncMock()

    # 1. Overdue deliveries query
    mock_overdue = MagicMock()
    mock_overdue.all.return_value = [("deliv_1", "finding_1", 1)]

    # Mock finding info query for queue_delivery_for_step
    mock_info = MagicMock()
    mock_info.first.return_value = ("class_not_held", "dept_1", "fac_1", "uni_1")

    # Mock routing step query for step 2 (Dean)
    mock_step = MagicMock()
    mock_step.first.return_value = ("dean", 7)

    # Mock authority resolve query
    mock_auth = MagicMock()
    mock_auth.first.return_value = ["auth_dean_id"]

    # Mock new delivery insert
    mock_new_deliv = MagicMock()
    mock_new_deliv.first.return_value = ["new_deliv_id"]

    # Mock decision log hashes
    mock_hash = MagicMock()
    mock_hash.first.return_value = None
    mock_hash.scalar_one.return_value = 1

    session.execute.side_effect = [
        mock_overdue,    # SELECT deliveries_to_escalate
        MagicMock(),     # UPDATE deliveries SET status = 'escalated'
        mock_info,       # finding info
        mock_step,       # routing_step step 2
        mock_auth,       # resolve Dean authority
        mock_new_deliv,  # insert new delivery
        mock_hash,       # decision log last hash
        mock_hash,       # insert decision log
        mock_hash,       # decision log last hash
        mock_hash,       # insert decision log
    ]

    escalated = await process_overdue_escalations(session)
    assert len(escalated) == 1
    assert escalated[0]["escalated_to_step"] == 2
    assert escalated[0]["new_delivery_queued"] is True
