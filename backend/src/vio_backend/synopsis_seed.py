"""Seed the database catalogue from the review-only FUNAAB synopsis CSV.

This imports department/programme synopsis rows as *unverified* catalogue
data so student profile setup can function before a canonical catalogue
exists. It only uses ``source_kind == 'department_synopsis'`` rows, drops
levels outside the schema's 100-600 range (e.g. 700-level postgraduate
rows), deduplicates by (department, course_code), and prefers rows that
state a semester for curriculum_entries. Nothing here asserts currency or
ownership; the faculty is deliberately named as an unverified import
bucket rather than a real college.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend.database import make_engine, make_session_factory

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV = REPO_ROOT / "docs/data/funaab_course_synopsis_candidates.csv"
DEFAULT_ENV_FILE = REPO_ROOT / ".env.local"
DEFAULT_UNIVERSITY = "FUNAAB"
DEFAULT_FACULTY = "Unverified Public Synopsis Imports"
VALID_LEVELS = {100, 200, 300, 400, 500, 600}
CURRICULUM_SOURCE = "courseform"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_seed_rows(csv_path: Path, *, source_kind: str = "department_synopsis") -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("source_kind") != source_kind:
                continue
            department = (row.get("department") or "").strip()
            code = (row.get("course_code") or "").strip()
            title = (row.get("course_title") or "").strip()
            try:
                level = int(row.get("level") or 0)
            except ValueError:
                continue
            if not department or not code or not title or level not in VALID_LEVELS:
                continue
            semester_raw = (row.get("semester") or "").strip()
            semester = int(semester_raw) if semester_raw in {"1", "2"} else None
            key = (department, code)
            candidate = {
                "department": department,
                "course_code": code,
                "course_title": title,
                "level": level,
                "semester": semester,
            }
            existing = best.get(key)
            if existing is None:
                best[key] = candidate
                order.append(key)
            elif existing["semester"] is None and semester is not None:
                best[key] = candidate
    return [best[key] for key in order]


async def _scalar(session: AsyncSession, sql: str, params: dict) -> object:
    result = await session.execute(text(sql), params)
    return result.scalar_one()


async def seed_catalogue(
    session: AsyncSession,
    rows: list[dict],
    *,
    university_short_name: str = DEFAULT_UNIVERSITY,
    faculty_name: str = DEFAULT_FACULTY,
) -> dict[str, int]:
    university_id = await _scalar(
        session,
        "SELECT id FROM universities WHERE lower(short_name) = lower(:short_name)",
        {"short_name": university_short_name},
    )
    if university_id is None:
        raise RuntimeError(f"University {university_short_name!r} is not seeded")

    await session.execute(
        text(
            """
            INSERT INTO faculties (university_id, name)
            VALUES (:university_id, :name)
            ON CONFLICT (university_id, name) DO NOTHING
            """
        ),
        {"university_id": university_id, "name": faculty_name},
    )
    faculty_id = await _scalar(
        session,
        "SELECT id FROM faculties WHERE university_id = :university_id AND name = :name",
        {"university_id": university_id, "name": faculty_name},
    )

    department_ids: dict[str, object] = {}
    for department in sorted({row["department"] for row in rows}):
        await session.execute(
            text(
                """
                INSERT INTO departments (faculty_id, name)
                VALUES (:faculty_id, :name)
                ON CONFLICT (faculty_id, name) DO NOTHING
                """
            ),
            {"faculty_id": faculty_id, "name": department},
        )
        department_ids[department] = await _scalar(
            session,
            "SELECT id FROM departments WHERE faculty_id = :faculty_id AND name = :name",
            {"faculty_id": faculty_id, "name": department},
        )

    courses_inserted = 0
    entries_inserted = 0
    for row in rows:
        department_id = department_ids[row["department"]]
        course_id = await session.scalar(
            text(
                """
                INSERT INTO courses (department_id, code, title, level)
                VALUES (:department_id, :code, :title, :level)
                ON CONFLICT (department_id, code) DO NOTHING
                RETURNING id
                """
            ),
            {
                "department_id": department_id,
                "code": row["course_code"],
                "title": row["course_title"],
                "level": row["level"],
            },
        )
        if course_id is None:
            course_id = await _scalar(
                session,
                "SELECT id FROM courses WHERE department_id = :department_id AND code = :code",
                {"department_id": department_id, "code": row["course_code"]},
            )
        else:
            courses_inserted += 1
        if row["semester"] is None:
            continue
        result = await session.execute(
            text(
                """
                INSERT INTO curriculum_entries (department_id, course_id, level, semester, is_elective, source)
                VALUES (:department_id, :course_id, :level, :semester, false, :source)
                ON CONFLICT DO NOTHING
                RETURNING course_id
                """
            ),
            {
                "department_id": department_id,
                "course_id": course_id,
                "level": row["level"],
                "semester": row["semester"],
                "source": CURRICULUM_SOURCE,
            },
        )
        if result.first() is not None:
            entries_inserted += 1

    return {
        "departments": len(department_ids),
        "courses_inserted": courses_inserted,
        "curriculum_entries_inserted": entries_inserted,
    }


async def run_seed(
    *,
    csv_path: Path,
    database_url: str,
    university_short_name: str,
    faculty_name: str,
) -> dict[str, int]:
    rows = load_seed_rows(csv_path)
    engine = make_engine(database_url)
    try:
        factory = make_session_factory(engine)
        async with factory() as session:
            counts = await seed_catalogue(
                session,
                rows,
                university_short_name=university_short_name,
                faculty_name=faculty_name,
            )
            await session.commit()
    finally:
        await engine.dispose()
    return {"input_rows": len(rows), **counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--university", default=DEFAULT_UNIVERSITY)
    parser.add_argument("--faculty-name", default=DEFAULT_FACULTY)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = load_seed_rows(args.csv)
    departments = len({row["department"] for row in rows})
    if args.dry_run:
        print(f"Dry run: {len(rows)} seed rows across {departments} departments -> {args.csv}")
        return

    load_env_file(args.env_file)
    database_url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_UNPOOLED")
    if not database_url:
        raise SystemExit("DATABASE_URL (or DATABASE_URL_UNPOOLED) is not set (checked environment and --env-file).")

    import asyncio

    counts = asyncio.run(
        run_seed(
            csv_path=args.csv,
            database_url=database_url,
            university_short_name=args.university,
            faculty_name=args.faculty_name,
        )
    )
    print(counts)


if __name__ == "__main__":
    main()
