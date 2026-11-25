import hashlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from vio_backend.audit import (
    GENESIS_HASH,
    compute_entry_hash,
    record_decision,
    verify_chain_integrity,
)


def test_compute_entry_hash_is_deterministic():
    prev = b"\x01" * 32
    hash1 = compute_entry_hash(
        prev_hash=prev,
        finding_id="f1",
        stage="gate",
        actor="gate_v1",
        decision="cleared",
        details={"score": 1.3},
    )
    hash2 = compute_entry_hash(
        prev_hash=prev,
        finding_id="f1",
        stage="gate",
        actor="gate_v1",
        decision="cleared",
        details={"score": 1.3},
    )
    assert hash1 == hash2
    assert len(hash1) == 32


def test_hash_changes_if_data_altered():
    prev = b"\x01" * 32
    orig_hash = compute_entry_hash(
        prev_hash=prev,
        finding_id="f1",
        stage="gate",
        actor="gate_v1",
        decision="cleared",
        details={"score": 1.3},
    )
    tampered_hash = compute_entry_hash(
        prev_hash=prev,
        finding_id="f1",
        stage="gate",
        actor="gate_v1",
        decision="cleared",
        details={"score": 0.5},  # altered score
    )
    assert orig_hash != tampered_hash


@pytest.mark.asyncio
async def test_record_decision_appends_to_chain():
    session = AsyncMock()

    # Mock no prior entries
    mock_res = MagicMock()
    mock_res.first.return_value = None
    session.execute.return_value = mock_res
    mock_res.scalar_one.return_value = 1

    entry_id = await record_decision(
        session,
        finding_id="f1",
        stage="gate",
        actor="gate_v1",
        decision="cleared",
        details={"test": True},
    )

    assert entry_id == 1
    session.execute.assert_called()


@pytest.mark.asyncio
async def test_verify_chain_integrity_detects_tampering():
    session = AsyncMock()

    prev = GENESIS_HASH
    h1 = compute_entry_hash(
        prev_hash=prev,
        finding_id="f1",
        stage="gate",
        actor="gate_v1",
        decision="cleared",
        details=None,
    )
    # Tampered second row: stored entry_hash does not match recomputed
    tampered_h2 = b"\x99" * 32

    mock_res = MagicMock()
    mock_res.all.return_value = [
        (1, "f1", "gate", "gate_v1", "cleared", None, prev, h1),
        (2, "f2", "gate", "gate_v1", "held", None, h1, tampered_h2),
    ]
    session.execute.return_value = mock_res

    is_valid, row_idx, err = await verify_chain_integrity(session)
    assert is_valid is False
    assert row_idx == 1
    assert "Tampering detected" in err
