"""Student profile setup. See docs/api/ENDPOINT_PROPOSAL.md ("Student
Authentication and Profile") and docs/DECISIONS.md, "Pending Before M2 Can
Close" #2: the course catalogue is explicitly deferred, so profile updates
must surface a clear unavailable state rather than fabricate departments."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from vio_backend import student_auth
from vio_backend.database import session_dependency
from vio_backend.errors import ApiError
from vio_backend.routers.auth import get_current_student

router = APIRouter(prefix="/api/v1/student", tags=["student"])

_VALID_LEVELS = (100, 200, 300, 400, 500, 600)


@router.get("/profile")
async def get_profile(
    record: student_auth.StudentSession = Depends(get_current_student),
) -> dict:
    return {
        "data": {
            "department_id": record.department_id,
            "level": record.level,
            "confirmed_session": record.confirmed_session,
            "setup_state": "profile_required" if record.department_id is None else "ready",
        }
    }


class ProfileUpdateRequest(BaseModel):
    department_id: UUID
    level: int = Field(ge=100, le=600)


@router.put("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    if body.level not in _VALID_LEVELS:
        raise ApiError(
            422, "validation_failed", "Select a valid level.", {"level": ["Must be one of 100-600."]}
        )
    department_id = str(body.department_id)
    if not await student_auth.catalogue_is_available(session, record.university_id):
        raise ApiError(503, "service_unavailable", "The course catalogue is not available yet.")
    if not await student_auth.department_belongs_to_university(session, record.university_id, department_id):
        raise ApiError(
            422,
            "validation_failed",
            "Select a department from the configured catalogue.",
            {"department_id": ["Unknown department for this university."]},
        )

    await student_auth.set_profile(session, record.student_id, department_id, body.level)
    await session.commit()
    return {"data": {"department_id": department_id, "level": body.level}}


class ConfirmSessionRequest(BaseModel):
    academic_session: str


@router.post("/profile/confirm-session")
async def confirm_session(
    body: ConfirmSessionRequest,
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    current = await student_auth.get_latest_academic_session(session, record.university_id)
    if current is None:
        raise ApiError(503, "service_unavailable", "The academic session calendar is not available yet.")
    if body.academic_session != current.session:
        raise ApiError(
            422,
            "validation_failed",
            "That is not the current academic session.",
            {"academic_session": [f"Expected {current.session}."]},
        )

    await student_auth.confirm_session(session, record.student_id, body.academic_session)
    await session.commit()
    return {"data": {"academic_session": body.academic_session, "status": current.status}}


@router.get("/courses")
async def get_courses(
    academic_session: str | None = None,
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    current = await student_auth.get_latest_academic_session(session, record.university_id)
    if current is None:
        raise ApiError(503, "service_unavailable", "The academic session calendar is not available yet.")
    session_label = academic_session or record.confirmed_session or current.session
    if session_label != current.session:
        raise ApiError(
            422,
            "validation_failed",
            "That is not the current academic session.",
            {"academic_session": [f"Expected {current.session}."]},
        )
    courses = await student_auth.list_course_registrations(session, record.student_id, session_label)
    return {"data": courses}


class CourseRegistrationRequest(BaseModel):
    academic_session: str
    course_ids: list[UUID] = Field(default_factory=list)


@router.put("/courses")
async def replace_courses(
    body: CourseRegistrationRequest,
    record: student_auth.StudentSession = Depends(get_current_student),
    session: AsyncSession = Depends(session_dependency),
) -> dict:
    if record.department_id is None:
        raise ApiError(409, "profile_required", "Complete your profile before registering courses.")
    current = await student_auth.get_latest_academic_session(session, record.university_id)
    if current is None:
        raise ApiError(503, "service_unavailable", "The academic session calendar is not available yet.")
    if body.academic_session != current.session or record.confirmed_session != current.session:
        raise ApiError(
            422,
            "validation_failed",
            "Confirm the current academic session before registering courses.",
            {"academic_session": [f"Expected {current.session}."]},
        )

    requested_ids = [str(course_id) for course_id in body.course_ids]
    valid_ids = await student_auth.courses_in_department(session, record.department_id, requested_ids)
    if len(valid_ids) != len(set(requested_ids)):
        raise ApiError(
            422,
            "validation_failed",
            "Every course must belong to your selected department.",
            {"course_ids": ["Unknown course for your department."]},
        )

    await student_auth.replace_course_registrations(session, record.student_id, current.session, requested_ids)
    await session.commit()
    courses = await student_auth.list_course_registrations(session, record.student_id, current.session)
    return {"data": courses}
