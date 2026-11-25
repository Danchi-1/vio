"""Cryptographic hash-chained audit decision log (M5/M8).

Follows database/schema.sql (decision_log table):
  entry_hash = SHA256(prev_hash || canonical_row_data)

This ensures that any modification, reordering, or retroactive tampering
with institutional decisions breaks the cryptographic hash chain.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GENESIS_HASH = b"\x00" * 32


def canonical_json(details: dict[str, Any] | None) -> str:
    if details is None:
        return ""
    return json.dumps(details, sort_keys=True, separators=(",", ":"))


def compute_entry_hash(
    *,
    prev_hash: bytes,
    finding_id: str | None,
    stage: str,
    actor: str,
    decision: str,
    details: dict[str, Any] | None,
) -> bytes:
    canonical_details = canonical_json(details)
    payload = (
        prev_hash
        + f"{finding_id or ''}:{stage}:{actor}:{decision}:{canonical_details}".encode("utf-8")
    )
    return hashlib.sha256(payload).digest()


async def record_decision(
    session: AsyncSession,
    *,
    finding_id: str | None,
    stage: str,
    actor: str,
    decision: str,
    details: dict[str, Any] | None = None,
) -> int:
    """Appends a new verified decision to the hash-chained decision_log.
    
    Uses pg_advisory_xact_lock to prevent race conditions and hash-chain forks
    during concurrent decision appends.
    """
    bind = getattr(session, "bind", None)
    if bind and hasattr(bind, "dialect") and getattr(bind.dialect, "name", None) == "postgresql":
        try:
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('decision_log_chain'))"))
        except Exception:
            pass

    last_res = await session.execute(
        text("SELECT entry_hash FROM decision_log ORDER BY id DESC LIMIT 1")
    )
    row = last_res.first()
    if row and isinstance(row[0], (bytes, bytearray, memoryview)):
        prev_hash = bytes(row[0])
    else:
        prev_hash = GENESIS_HASH

    entry_hash = compute_entry_hash(
        prev_hash=prev_hash,
        finding_id=finding_id,
        stage=stage,
        actor=actor,
        decision=decision,
        details=details,
    )

    query = """
        INSERT INTO decision_log (finding_id, stage, actor, decision, details, prev_hash, entry_hash)
        VALUES (:finding_id, :stage, :actor, :decision, :details, :prev_hash, :entry_hash)
        RETURNING id
    """
    result = await session.execute(
        text(query),
        {
            "finding_id": finding_id,
            "stage": stage,
            "actor": actor,
            "decision": decision,
            "details": json.dumps(details) if details is not None else None,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
        },
    )
    new_id = result.scalar_one()
    return int(new_id)


async def verify_chain_integrity(session: AsyncSession) -> tuple[bool, int, str | None]:
    """Verifies that the entire decision_log hash chain is intact and un-tampered."""
    query = """
        SELECT id, finding_id, stage, actor, decision, details, prev_hash, entry_hash
        FROM decision_log
        ORDER BY id ASC
    """
    result = await session.execute(text(query))
    rows = result.all()

    expected_prev = GENESIS_HASH
    for i, row in enumerate(rows):
        row_id, f_id, stage, actor, decision, details, prev_hash, entry_hash = row
        if prev_hash != expected_prev:
            return False, i, f"Hash chain broken at row {row_id}: prev_hash does not match preceding entry_hash"

        recomputed = compute_entry_hash(
            prev_hash=prev_hash,
            finding_id=str(f_id) if f_id else None,
            stage=stage,
            actor=actor,
            decision=decision,
            details=details,
        )
        if recomputed != entry_hash:
            return False, i, f"Tampering detected at row {row_id}: recomputed hash does not match stored entry_hash"

        expected_prev = entry_hash

    return True, len(rows), None
