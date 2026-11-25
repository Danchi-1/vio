"""Database access for student email-challenge auth, sessions, and profile.

Functions here never commit; callers (router handlers) commit once after a
successful sequence of writes, so a failure partway through a request rolls
back cleanly instead of leaving e.g. a consumed challenge with no session.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ChallengeRecord:
    id: str
    university_id: str
    identity_hash: bytes
    code_hash: bytes
    attempts: int
    max_attempts: int
    expires_at: datetime
    consumed_at: datetime | None


@dataclass(frozen=True)
class StudentSession:
    student_id: str
    university_id: str
    department_id: str | None
    level: int | None
    confirmed_session: str | None


@dataclass(frozen=True)
class AcademicSessionInfo:
    session: str
    status: str


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def get_university_email_domain(session: AsyncSession, university_id: str) -> str | None:
    result = await session.execute(
        text("SELECT email_domain FROM universities WHERE id = :university_id"),
        {"university_id": university_id},
    )
    row = result.first()
    return row[0] if row else None


async def get_latest_challenge_time(
    session: AsyncSession, university_id: str, identity_hash: bytes
) -> datetime | None:
    result = await session.execute(
        text(
            """
            SELECT created_at FROM email_challenges
            WHERE university_id = :university_id AND identity_hash = :identity_hash
            ORDER BY created_at DESC LIMIT 1
            """
        ),
        {"university_id": university_id, "identity_hash": identity_hash},
    )
    row = result.first()
    return _aware(row[0]) if row else None


async def count_recent_challenges(
    session: AsyncSession, university_id: str, identity_hash: bytes, since: datetime
) -> int:
    result = await session.execute(
        text(
            """
            SELECT COUNT(*) FROM email_challenges
            WHERE university_id = :university_id
              AND identity_hash = :identity_hash
              AND created_at >= :since
            """
        ),
        {"university_id": university_id, "identity_hash": identity_hash, "since": since},
    )
    return int(result.scalar_one())


async def create_challenge(
    session: AsyncSession,
    *,
    university_id: str,
    identity_hash: bytes,
    code_hash: bytes,
    ttl_minutes: int,
    max_attempts: int,
) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    result = await session.execute(
        text(
            """
            INSERT INTO email_challenges (university_id, identity_hash, code_hash, max_attempts, expires_at)
            VALUES (:university_id, :identity_hash, :code_hash, :max_attempts, :expires_at)
            RETURNING id, expires_at
            """
        ),
        {
            "university_id": university_id,
            "identity_hash": identity_hash,
            "code_hash": code_hash,
            "max_attempts": max_attempts,
            "expires_at": expires_at,
        },
    )
    row = result.one()
    return str(row[0]), _aware(row[1])


async def get_challenge(session: AsyncSession, challenge_id: str) -> ChallengeRecord | None:
    result = await session.execute(
        text(
            """
            SELECT id, university_id, identity_hash, code_hash, attempts, max_attempts, expires_at, consumed_at
            FROM email_challenges WHERE id = :id
            """
        ),
        {"id": challenge_id},
    )
    row = result.first()
    if row is None:
        return None
    return ChallengeRecord(
        id=str(row[0]),
        university_id=str(row[1]),
        identity_hash=bytes(row[2]),
        code_hash=bytes(row[3]),
        attempts=row[4],
        max_attempts=row[5],
        expires_at=_aware(row[6]),
        consumed_at=_aware(row[7]) if row[7] else None,
    )


async def register_failed_attempt(session: AsyncSession, challenge_id: str) -> None:
    await session.execute(
        text("UPDATE email_challenges SET attempts = attempts + 1 WHERE id = :id"),
        {"id": challenge_id},
    )


async def consume_challenge(session: AsyncSession, challenge_id: str) -> None:
    await session.execute(
        text("UPDATE email_challenges SET consumed_at = now() WHERE id = :id"),
        {"id": challenge_id},
    )


async def get_or_create_student(session: AsyncSession, university_id: str, identity_hash: bytes) -> str:
    result = await session.execute(
        text(
            """
            INSERT INTO student_accounts (university_id, identity_hash)
            VALUES (:university_id, :identity_hash)
            ON CONFLICT (university_id, identity_hash) DO NOTHING
            RETURNING id
            """
        ),
        {"university_id": university_id, "identity_hash": identity_hash},
    )
    row = result.first()
    if row is None:
        existing = await session.execute(
            text(
                """
                SELECT id FROM student_accounts
                WHERE university_id = :university_id AND identity_hash = :identity_hash
                """
            ),
            {"university_id": university_id, "identity_hash": identity_hash},
        )
        row = existing.one()
    return str(row[0])


async def ensure_email_verification(session: AsyncSession, student_id: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO student_verifications (student_id, factor, passed)
            VALUES (:student_id, 'school_email', true)
            ON CONFLICT (student_id, factor) DO UPDATE SET passed = true
            """
        ),
        {"student_id": student_id},
    )


async def create_session(
    session: AsyncSession, *, student_id: str, token_hash: bytes, ttl_days: int
) -> datetime:
    expires_at = datetime.now(UTC) + timedelta(days=ttl_days)
    await session.execute(
        text(
            """
            INSERT INTO student_sessions (student_id, token_hash, expires_at)
            VALUES (:student_id, :token_hash, :expires_at)
            """
        ),
        {"student_id": student_id, "token_hash": token_hash, "expires_at": expires_at},
    )
    return expires_at


async def get_session(session: AsyncSession, token_hash: bytes) -> StudentSession | None:
    result = await session.execute(
        text(
            """
            SELECT s.student_id, a.university_id, a.department_id, a.level, a.confirmed_session
            FROM student_sessions s
            JOIN student_accounts a ON a.id = s.student_id
            WHERE s.token_hash = :token_hash
              AND s.revoked_at IS NULL
              AND s.expires_at > now()
            """
        ),
        {"token_hash": token_hash},
    )
    row = result.first()
    if row is None:
        return None
    return StudentSession(
        student_id=str(row[0]),
        university_id=str(row[1]),
        department_id=str(row[2]) if row[2] else None,
        level=row[3],
        confirmed_session=row[4],
    )


async def revoke_session(session: AsyncSession, token_hash: bytes) -> None:
    await session.execute(
        text(
            """
            UPDATE student_sessions SET revoked_at = now()
            WHERE token_hash = :token_hash AND revoked_at IS NULL
            """
        ),
        {"token_hash": token_hash},
    )


async def catalogue_is_available(session: AsyncSession, university_id: str) -> bool:
    result = await session.execute(
        text(
            """
            SELECT EXISTS (
              SELECT 1 FROM departments d
              JOIN faculties f ON f.id = d.faculty_id
              WHERE f.university_id = :university_id
            )
            """
        ),
        {"university_id": university_id},
    )
    return bool(result.scalar_one())


async def department_belongs_to_university(
    session: AsyncSession, university_id: str, department_id: str
) -> bool:
    result = await session.execute(
        text(
            """
            SELECT EXISTS (
              SELECT 1 FROM departments d
              JOIN faculties f ON f.id = d.faculty_id
              WHERE f.university_id = :university_id AND d.id = :department_id
            )
            """
        ),
        {"university_id": university_id, "department_id": department_id},
    )
    return bool(result.scalar_one())


async def set_profile(session: AsyncSession, student_id: str, department_id: str, level: int) -> None:
    await session.execute(
        text("UPDATE student_accounts SET department_id = :department_id, level = :level WHERE id = :id"),
        {"department_id": department_id, "level": level, "id": student_id},
    )


async def confirm_session(session: AsyncSession, student_id: str, academic_session: str) -> None:
    await session.execute(
        text("UPDATE student_accounts SET confirmed_session = :academic_session WHERE id = :id"),
        {"academic_session": academic_session, "id": student_id},
    )


async def get_latest_academic_session(
    session: AsyncSession, university_id: str
) -> AcademicSessionInfo | None:
    result = await session.execute(
        text(
            """
            SELECT session, status FROM academic_sessions
            WHERE university_id = :university_id
            ORDER BY session DESC LIMIT 1
            """
        ),
        {"university_id": university_id},
    )
    row = result.first()
    return AcademicSessionInfo(session=row[0], status=row[1]) if row else None


async def courses_in_department(
    session: AsyncSession,
    department_id: str,
    course_ids: list[str],
) -> set[str]:
    if not course_ids:
        return set()
    result = await session.execute(
        text(
            """
            SELECT id FROM courses
            WHERE department_id = :department_id AND id = ANY(:course_ids)
            """
        ),
        {"department_id": str(department_id), "course_ids": [str(course_id) for course_id in course_ids]},
    )
    return {str(row["id"]) for row in result.mappings().all()}


async def replace_course_registrations(
    session: AsyncSession,
    student_id: str,
    academic_session: str,
    course_ids: list[str],
) -> None:
    await session.execute(
        text(
            "DELETE FROM student_course_registrations WHERE student_id = :student_id AND academic_session = :academic_session"
        ),
        {"student_id": str(student_id), "academic_session": academic_session},
    )
    for course_id in course_ids:
        await session.execute(
            text(
                """
                INSERT INTO student_course_registrations (student_id, course_id, academic_session)
                VALUES (:student_id, :course_id, :academic_session)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "student_id": str(student_id),
                "course_id": str(course_id),
                "academic_session": academic_session,
            },
        )


async def list_course_registrations(
    session: AsyncSession,
    student_id: str,
    academic_session: str,
) -> list[dict]:
    result = await session.execute(
        text(
            """
            SELECT c.id AS course_id, c.code, c.title, c.level,
                   d.name AS department, r.academic_session
            FROM student_course_registrations r
            JOIN courses c ON c.id = r.course_id
            JOIN departments d ON d.id = c.department_id
            WHERE r.student_id = :student_id AND r.academic_session = :academic_session
            ORDER BY c.code
            """
        ),
        {"student_id": str(student_id), "academic_session": academic_session},
    )
    return [
        {
            "course_id": str(row["course_id"]),
            "course_code": row["code"],
            "course_title": row["title"],
            "level": row["level"],
            "department": row["department"],
            "academic_session": row["academic_session"],
            "verification_status": "self_declared_unverified",
        }
        for row in result.mappings().all()
    ]
