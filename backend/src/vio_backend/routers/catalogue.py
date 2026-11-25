from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend.database import session_dependency
from vio_backend.errors import ApiError

router = APIRouter(prefix="/api/v1", tags=["catalogue"])


@router.get("/universities")
async def list_universities(session: AsyncSession = Depends(session_dependency)) -> dict:
    result = await session.execute(text("SELECT id, short_name, name FROM universities ORDER BY name"))
    return {"data": [dict(row) for row in result.mappings().all()]}


@router.get("/universities/{short_name}/catalogue")
async def get_catalogue(short_name: str, session: AsyncSession = Depends(session_dependency)) -> dict:
    result = await session.execute(
        text("""
            SELECT f.name AS faculty, d.name AS department, d.id AS department_id,
                   c.id AS course_id, c.code AS course_code, c.title AS course_title, c.level,
                   ce.semester, ce.is_elective
            FROM universities u
            JOIN faculties f ON f.university_id = u.id
            JOIN departments d ON d.faculty_id = f.id
            JOIN courses c ON c.department_id = d.id
            LEFT JOIN curriculum_entries ce
              ON ce.course_id = c.id AND ce.department_id = d.id
            WHERE lower(u.short_name) = lower(:short_name)
            ORDER BY f.name, d.name, c.level, c.code, ce.semester
        """),
        {"short_name": short_name},
    )
    return {"data": [dict(row) for row in result.mappings().all()]}


@router.get("/universities/{short_name}/faculties")
async def list_faculties(short_name: str, session: AsyncSession = Depends(session_dependency)) -> dict:
    result = await session.execute(
        text(
            """
            SELECT f.id, f.name FROM faculties f
            JOIN universities u ON u.id = f.university_id
            WHERE lower(u.short_name) = lower(:short_name)
            ORDER BY f.name
            """
        ),
        {"short_name": short_name},
    )
    return {"data": [dict(row) for row in result.mappings().all()]}


@router.get("/faculties/{faculty_id}/departments")
async def list_departments(faculty_id: UUID, session: AsyncSession = Depends(session_dependency)) -> dict:
    faculty = await session.execute(text("SELECT id FROM faculties WHERE id = :id"), {"id": str(faculty_id)})
    if faculty.first() is None:
        raise ApiError(404, "not_found", "That faculty was not found.")
    result = await session.execute(
        text("SELECT id, name FROM departments WHERE faculty_id = :id ORDER BY name"),
        {"id": str(faculty_id)},
    )
    return {"data": [dict(row) for row in result.mappings().all()]}


@router.get("/academic-sessions")
async def list_academic_sessions(session: AsyncSession = Depends(session_dependency)) -> dict:
    """Public. 'status' is 'proposed' or 'confirmed' per docs/DECISIONS.md;
    the frontend must show provisional sessions as such, not as settled fact.
    Date fields are returned so clients can display the calendar, but they are
    only as authoritative as 'status' and 'source' indicate."""
    result = await session.execute(
        text(
            """
            SELECT u.short_name AS university, s.session, s.status,
                   s.returning_registration_starts, s.fresh_registration_starts,
                   s.late_registration_starts, s.late_registration_ends,
                   s.matriculation_date,
                   s.first_semester_lectures_start, s.first_semester_lectures_end,
                   s.first_semester_exams_start, s.first_semester_exams_end,
                   s.second_semester_lectures_start, s.second_semester_lectures_end,
                   s.second_semester_exams_start, s.second_semester_exams_end,
                   s.session_ends, s.source
            FROM academic_sessions s
            JOIN universities u ON u.id = s.university_id
            ORDER BY s.session DESC
            """
        )
    )
    return {"data": [dict(row) for row in result.mappings().all()]}
