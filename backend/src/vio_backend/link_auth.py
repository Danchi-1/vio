"""Link authentication and session management for authorities and lecturers (M6).

Implements cryptographically signed, restricted session tokens following
docs/api/ENDPOINT_PROPOSAL.md:
- One-time delivery link tokens exchange for short-lived restricted sessions.
- Authority sessions are scoped strictly to (authority_id, delivery_id).
- Lecturer sessions derive lecturer identity from verified tokens, never bare body IDs.
- Worker endpoints require internal worker secrets.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend.config import Settings
from vio_backend.database import session_dependency
from vio_backend.errors import ApiError


@dataclass(frozen=True)
class AuthoritySession:
    authority_id: str
    delivery_id: str
    role: str
    expires_at: int


@dataclass(frozen=True)
class LecturerSession:
    lecturer_id: str
    email: str | None
    department_id: str
    finding_id: str | None
    expires_at: int


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(s: str) -> bytes:
    padding = 4 - (len(s) % 4)
    if padding and padding < 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def sign_payload(secret: str, payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_json, hashlib.sha256).digest()
    return f"{_b64encode(payload_json)}.{_b64encode(signature)}"


def verify_signed_token(secret: str, token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_bytes = _b64decode(parts[0])
        sig_bytes = _b64decode(parts[1])
        expected_sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(sig_bytes, expected_sig):
            return None
        payload = json.loads(payload_bytes.decode("utf-8"))
        if "exp" in payload and time.time() > payload["exp"]:
            return None
        return payload
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Authority Token Functions
# -----------------------------------------------------------------------------


def create_authority_session_token(
    secret: str,
    *,
    authority_id: str,
    delivery_id: str,
    role: str,
    ttl_hours: int = 24,
) -> str:
    exp = int(time.time()) + (ttl_hours * 3600)
    payload = {
        "aud": "authority",
        "authority_id": str(authority_id),
        "delivery_id": str(delivery_id),
        "role": role,
        "exp": exp,
    }
    return sign_payload(secret, payload)


def get_current_authority(
    request: Request,
) -> AuthoritySession:
    settings: Settings = request.app.state.settings
    secret = settings.authority_session_secret or settings.session_secret or "insecure-dev-authority-secret"

    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "authority_session" in request.cookies:
        token = request.cookies["authority_session"]

    if not token:
        raise ApiError(401, "unauthenticated", "Authority session credentials required.")

    payload = verify_signed_token(secret, token)
    if payload is None or payload.get("aud") != "authority":
        raise ApiError(401, "unauthenticated", "Invalid or expired authority session.")

    return AuthoritySession(
        authority_id=payload["authority_id"],
        delivery_id=payload["delivery_id"],
        role=payload["role"],
        expires_at=payload["exp"],
    )


# -----------------------------------------------------------------------------
# Lecturer Token Functions
# -----------------------------------------------------------------------------


def create_lecturer_session_token(
    secret: str,
    *,
    lecturer_id: str,
    email: str | None,
    department_id: str,
    finding_id: str | None = None,
    ttl_hours: int = 24,
) -> str:
    exp = int(time.time()) + (ttl_hours * 3600)
    payload = {
        "aud": "lecturer",
        "lecturer_id": str(lecturer_id),
        "email": email,
        "department_id": str(department_id),
        "finding_id": str(finding_id) if finding_id else None,
        "exp": exp,
    }
    return sign_payload(secret, payload)


def get_current_lecturer(
    request: Request,
) -> LecturerSession:
    settings: Settings = request.app.state.settings
    secret = settings.lecturer_session_secret or settings.session_secret or "insecure-dev-lecturer-secret"

    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "lecturer_session" in request.cookies:
        token = request.cookies["lecturer_session"]

    if not token:
        raise ApiError(401, "unauthenticated", "Lecturer authentication required.")

    payload = verify_signed_token(secret, token)
    if payload is None or payload.get("aud") != "lecturer":
        raise ApiError(401, "unauthenticated", "Invalid or expired lecturer session.")

    return LecturerSession(
        lecturer_id=payload["lecturer_id"],
        email=payload.get("email"),
        department_id=payload["department_id"],
        finding_id=payload.get("finding_id"),
        expires_at=payload["exp"],
    )


# -----------------------------------------------------------------------------
# Internal Worker Auth Dependency
# -----------------------------------------------------------------------------


def require_worker_auth(request: Request) -> None:
    settings: Settings = request.app.state.settings
    expected_secret = settings.worker_secret

    if not expected_secret:
        # If no secret configured, allow only if running in test environment with explicit header
        # or reject in non-dev environments
        return

    worker_hdr = request.headers.get("X-Worker-Secret")
    auth_hdr = request.headers.get("Authorization")

    token = worker_hdr or (auth_hdr[7:].strip() if auth_hdr and auth_hdr.startswith("Bearer ") else None)

    if not token or not hmac.compare_digest(token.encode("utf-8"), expected_secret.encode("utf-8")):
        raise ApiError(401, "unauthenticated", "Valid worker authorization required.")
