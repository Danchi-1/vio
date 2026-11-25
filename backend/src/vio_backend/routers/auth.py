"""Student email-challenge sign-in and session management.

See docs/api/ENDPOINT_PROPOSAL.md ("Student Authentication and Profile") and
docs/DECISIONS.md for the approved behavior this implements:
- Session transport is a secure, HttpOnly, SameSite cookie (proceeding under
  the project owner's general go-ahead; no bearer-token alternative is built).
- The raw student email is used only to send the code, then discarded; only
  its HMAC (identity_hash) and the code's HMAC (code_hash) are persisted.
- Code expiry is 10 minutes, resend cooldown is 60 seconds (approved
  2026-11-10). Attempt/hourly caps default to 5/5, proposed but not yet
  explicitly confirmed.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import student_auth
from vio_backend.config import Settings
from vio_backend.database import session_dependency
from vio_backend.email_delivery import EmailDeliveryUnavailable, build_email_sender
from vio_backend.errors import ApiError
from vio_backend.security import (
    code_matches,
    compute_code_hash,
    compute_identity_hash,
    compute_session_token_hash,
    generate_otp_code,
    generate_session_token,
    mask_email,
    normalize_email,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

SESSION_COOKIE_NAME = "vio_session"


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise ApiError(503, "service_unavailable", "The service is not configured.")
    return settings


def _require_secret(value: str | None, what: str) -> str:
    if not value:
        raise ApiError(503, "service_unavailable", f"{what} is not configured.")
    return value


class EmailChallengeRequest(BaseModel):
    university_id: UUID
    email: str = Field(min_length=3, max_length=320)


@router.post("/student/email-challenges")
async def request_email_challenge(
    body: EmailChallengeRequest,
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(get_settings),
) -> dict:
    identity_secret = _require_secret(settings.identity_hash_secret, "Identity hashing")
    university_id = str(body.university_id)

    email_domain = await student_auth.get_university_email_domain(session, university_id)
    if not email_domain:
        # Covers both "unknown university" and "domain not yet confirmed" (e.g.
        # a university seeded with email_domain = NULL): never guess a domain.
        raise ApiError(503, "service_unavailable", "Student sign-in is not available for this university yet.")

    normalized = normalize_email(body.email)
    if not normalized.endswith("@" + email_domain.lower()):
        raise ApiError(400, "invalid_request", "Use your official student school email address.")

    identity_hash = compute_identity_hash(identity_secret, normalized)
    now = datetime.now(UTC)

    latest = await student_auth.get_latest_challenge_time(session, university_id, identity_hash)
    cooldown = timedelta(seconds=settings.challenge_resend_cooldown_seconds)
    if latest is not None and now - latest < cooldown:
        raise ApiError(429, "rate_limited", "Please wait before requesting another code.")

    recent_count = await student_auth.count_recent_challenges(
        session, university_id, identity_hash, now - timedelta(hours=1)
    )
    if recent_count >= settings.challenge_max_per_hour:
        raise ApiError(429, "rate_limited", "Too many requests. Try again later.")

    code = generate_otp_code()
    code_hash = compute_code_hash(identity_secret, code)
    challenge_id, expires_at = await student_auth.create_challenge(
        session,
        university_id=university_id,
        identity_hash=identity_hash,
        code_hash=code_hash,
        ttl_minutes=settings.challenge_ttl_minutes,
        max_attempts=settings.challenge_max_attempts,
    )
    await session.commit()

    sender = build_email_sender(settings)
    try:
        await sender.send(
            to_address=normalized,
            subject="Your VIO verification code",
            body=(
                f"Your VIO verification code is {code}. "
                f"It expires in {settings.challenge_ttl_minutes} minutes. "
                "If you did not request this, ignore this email."
            ),
        )
    except EmailDeliveryUnavailable as exc:
        raise ApiError(503, "service_unavailable", "Email delivery is not available right now.") from exc

    resend_at = now + cooldown
    return {
        "data": {
            "challenge_id": challenge_id,
            "masked_destination": mask_email(normalized),
            "expires_at": expires_at.isoformat(),
            "resend_at": resend_at.isoformat(),
        }
    }


class EmailChallengeVerifyRequest(BaseModel):
    challenge_id: UUID
    code: str = Field(min_length=6, max_length=6)


@router.post("/student/email-challenges/verify")
async def verify_email_challenge(
    body: EmailChallengeVerifyRequest,
    response: Response,
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(get_settings),
) -> dict:
    identity_secret = _require_secret(settings.identity_hash_secret, "Identity hashing")
    session_secret = _require_secret(settings.session_secret, "Session signing")

    challenge = await student_auth.get_challenge(session, str(body.challenge_id))
    if challenge is None:
        raise ApiError(404, "not_found", "That verification code is invalid.")

    now = datetime.now(UTC)
    if challenge.consumed_at is not None:
        raise ApiError(400, "link_already_used", "That verification code has already been used.")
    if now > challenge.expires_at:
        raise ApiError(400, "expired_link", "That verification code has expired. Request a new one.")
    if challenge.attempts >= challenge.max_attempts:
        raise ApiError(400, "invalid_request", "That verification code is no longer valid. Request a new one.")

    if not code_matches(identity_secret, body.code, challenge.code_hash):
        await student_auth.register_failed_attempt(session, challenge.id)
        await session.commit()
        raise ApiError(400, "invalid_request", "That code did not match. Check it and try again.")

    await student_auth.consume_challenge(session, challenge.id)
    student_id = await student_auth.get_or_create_student(session, challenge.university_id, challenge.identity_hash)
    await student_auth.ensure_email_verification(session, student_id)

    token = generate_session_token()
    token_hash = compute_session_token_hash(session_secret, token)
    expires_at = await student_auth.create_session(
        session, student_id=student_id, token_hash=token_hash, ttl_days=settings.session_ttl_days
    )
    await session.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        expires=int(expires_at.timestamp()),
        path="/",
    )
    return {"data": {"role": "student"}}


async def get_current_student(
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(get_settings),
    vio_session: str | None = Cookie(default=None),
) -> student_auth.StudentSession:
    session_secret = _require_secret(settings.session_secret, "Session signing")
    if not vio_session:
        raise ApiError(401, "unauthenticated", "Sign in to continue.")
    token_hash = compute_session_token_hash(session_secret, vio_session)
    record = await student_auth.get_session(session, token_hash)
    if record is None:
        raise ApiError(401, "unauthenticated", "Your session has expired. Sign in again.")
    return record


def _setup_state(record: student_auth.StudentSession, current_session: str | None) -> str:
    if record.department_id is None or record.level is None:
        return "profile_required"
    if current_session is not None and record.confirmed_session != current_session:
        return "session_confirmation_required"
    return "ready"


@router.get("/session")
async def get_session_summary(
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    current = await student_auth.get_latest_academic_session(session, record.university_id)
    return {
        "data": {
            "role": "student",
            "setup_state": _setup_state(record, current.session if current else None),
            "academic_session": current.session if current else None,
            "academic_session_status": current.status if current else "unavailable",
        }
    }


@router.delete("/session", status_code=204)
async def delete_session(
    response: Response,
    session: AsyncSession = Depends(session_dependency),
    settings: Settings = Depends(get_settings),
    vio_session: str | None = Cookie(default=None),
) -> None:
    if vio_session:
        session_secret = _require_secret(settings.session_secret, "Session signing")
        token_hash = compute_session_token_hash(session_secret, vio_session)
        await student_auth.revoke_session(session, token_hash)
        await session.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
