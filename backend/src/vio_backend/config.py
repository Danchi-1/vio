from dataclasses import dataclass
import os


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    # HMAC key for student_accounts.identity_hash (email) and email_challenges
    # code_hash. Never log, commit, or expose this. Rotating it invalidates
    # every existing identity hash and challenge; see docs/DECISIONS.md.
    identity_hash_secret: str | None
    # HMAC key for student_sessions.token_hash. Separate from
    # identity_hash_secret so the two cannot be used interchangeably.
    session_secret: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_from_address: str | None
    # Approved 2026-11-10: 10-minute expiry, 60-second resend cooldown.
    # Attempt/hourly caps are provisional defaults pending explicit
    # confirmation (see docs/DECISIONS.md, "Pending Before M2 Can Close").
    challenge_ttl_minutes: int
    challenge_resend_cooldown_seconds: int
    challenge_max_attempts: int
    challenge_max_per_hour: int
    session_ttl_days: int
    authority_session_secret: str | None = None
    lecturer_session_secret: str | None = None
    worker_secret: str | None = None
    api_prefix: str = "/api/v1"
    # Groq free-tier model panel. No paid fallback: if the key is missing or
    # Groq returns quota/auth errors, report intake fails closed.
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 20.0
    groq_extractor_model: str = "openai/gpt-oss-20b"
    groq_safety_model: str = "openai/gpt-oss-safeguard-20b"
    groq_consistency_model: str = "qwen/qwen3-32b"
    groq_red_team_model: str = "openai/gpt-oss-120b"
    groq_summary_model: str = "openai/gpt-oss-20b"
    panel_min_confidence: float = 0.80
    hold_ttl_days: int = 14

    @classmethod
    def from_environment(cls) -> "Settings":
        db_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_UNPOOLED")
        sess_secret = os.getenv("SESSION_SECRET")
        return cls(
            database_url=db_url,
            identity_hash_secret=os.getenv("IDENTITY_HASH_SECRET"),
            session_secret=sess_secret,
            authority_session_secret=os.getenv("AUTHORITY_SESSION_SECRET", sess_secret),
            lecturer_session_secret=os.getenv("LECTURER_SESSION_SECRET", sess_secret),
            worker_secret=os.getenv("WORKER_SECRET"),
            smtp_host=os.getenv("SMTP_HOST"),
            smtp_port=_int_env("SMTP_PORT", 587),
            smtp_username=os.getenv("SMTP_USERNAME"),
            smtp_password=os.getenv("SMTP_APP_PASSWORD"),
            smtp_from_address=os.getenv("SMTP_FROM_ADDRESS"),
            challenge_ttl_minutes=_int_env("EMAIL_CHALLENGE_TTL_MINUTES", 10),
            challenge_resend_cooldown_seconds=_int_env("EMAIL_CHALLENGE_RESEND_COOLDOWN_SECONDS", 60),
            challenge_max_attempts=_int_env("EMAIL_CHALLENGE_MAX_ATTEMPTS", 5),
            challenge_max_per_hour=_int_env("EMAIL_CHALLENGE_MAX_PER_HOUR", 5),
            session_ttl_days=_int_env("STUDENT_SESSION_TTL_DAYS", 30),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            groq_timeout_seconds=float(os.getenv("GROQ_TIMEOUT_SECONDS", "20")),
            groq_extractor_model=os.getenv("GROQ_EXTRACTOR_MODEL", "openai/gpt-oss-20b"),
            groq_safety_model=os.getenv("GROQ_SAFETY_MODEL", "openai/gpt-oss-safeguard-20b"),
            groq_consistency_model=os.getenv("GROQ_CONSISTENCY_MODEL", "qwen/qwen3-32b"),
            groq_red_team_model=os.getenv("GROQ_RED_TEAM_MODEL", "openai/gpt-oss-120b"),
            groq_summary_model=os.getenv("GROQ_SUMMARY_MODEL", "openai/gpt-oss-20b"),
            panel_min_confidence=float(os.getenv("PANEL_MIN_CONFIDENCE", "0.80")),
            hold_ttl_days=_int_env("HOLD_TTL_DAYS", 14),
        )
