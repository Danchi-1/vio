"""Cryptographic helpers for student identity, OTP codes, and session tokens.

Nothing here ever persists a raw email, raw OTP code, or raw session token.
Only HMAC-SHA256 digests of them are stored; the secrets used as HMAC keys
live only in environment configuration (see config.Settings).
"""

import hashlib
import hmac
import secrets


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _hmac_digest(secret: str, value: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()


def compute_identity_hash(secret: str, email: str) -> bytes:
    """HMAC-SHA256(secret, normalized email). Enforces one account per student
    without ever storing the email itself."""
    return _hmac_digest(secret, normalize_email(email))


def generate_otp_code() -> str:
    """A zero-padded 6-digit code using a cryptographically secure RNG."""
    return f"{secrets.randbelow(1_000_000):06d}"


def compute_code_hash(secret: str, code: str) -> bytes:
    return _hmac_digest(secret, code)


def code_matches(secret: str, code: str, code_hash: bytes) -> bool:
    return hmac.compare_digest(compute_code_hash(secret, code), code_hash)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def compute_session_token_hash(secret: str, token: str) -> bytes:
    return _hmac_digest(secret, token)


def mask_email(email: str) -> str:
    """Mask the local part of an email for display, e.g. 'su**********@student.funaab.edu.ng'."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    visible = local[:2]
    masked = visible + "*" * max(len(local) - len(visible), 1)
    return f"{masked}@{domain}"
