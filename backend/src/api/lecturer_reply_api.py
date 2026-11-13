
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.src.application.stage6_dev_dependencies import (
    get_reply_service,
)

from backend.src.domain.reply_assessment import (
    ReplyReason,
)


# --------------------------------------------------
# API ROUTER
# --------------------------------------------------

router = APIRouter(
    prefix="/lecturer-replies",
    tags=["Lecturer Replies"],
)


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class CreateReplyCaseRequest(BaseModel):
    finding_id: str = Field(min_length=1)
    lecturer_id: str = Field(min_length=1)


class SubmitReplyRequest(BaseModel):
    reason: ReplyReason
    text: str = Field(min_length=1, max_length=2000)


# --------------------------------------------------
# RESPONSE MODELS
# --------------------------------------------------

class ReplyCaseResponse(BaseModel):
    reply_case_id: str
    finding_id: str
    lecturer_id: str
    status: str
    deadline: datetime
    reply_text: str | None = None
    reply_reason: str | None = None


class ReplyAssessmentResponse(BaseModel):
    reason: str
    action: str
    evidence_verified: bool
    explanation: str


class SubmitReplyResponse(BaseModel):
    case: ReplyCaseResponse
    assessment: ReplyAssessmentResponse


# --------------------------------------------------
# SERIALIZATION
# --------------------------------------------------

def serialize_case(case):
    return ReplyCaseResponse(
        reply_case_id=case.reply_case_id,
        finding_id=case.finding_id,
        lecturer_id=case.lecturer_id,
        status=case.status.value,
        deadline=case.deadline,
        reply_text=case.reply_text,
        reply_reason=case.reply_reason,
    )


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@router.get("/health")
def lecturer_reply_health():
    return {
        "status": "ok",
        "module": "Vio Stage 6",
        "message": "Lecturer reply API is running",
    }


# --------------------------------------------------
# CREATE LECTURER REPLY CASE
# --------------------------------------------------

@router.post(
    "/cases",
    response_model=ReplyCaseResponse,
    status_code=201,
)
def create_reply_case(
    payload: CreateReplyCaseRequest,
    service=Depends(get_reply_service),
):
    try:
        case = service.create_case(
            finding_id=payload.finding_id,
            lecturer_id=payload.lecturer_id,
        )

        return serialize_case(case)

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# GET EXISTING REPLY CASE
# --------------------------------------------------

@router.get(
    "/cases/{reply_case_id}",
    response_model=ReplyCaseResponse,
)
def get_reply_case(
    reply_case_id: str,
    service=Depends(get_reply_service),
):
    case = service.repository.get(reply_case_id)

    if case is None:
        raise HTTPException(
            status_code=404,
            detail="Reply case not found.",
        )

    return serialize_case(case)


# --------------------------------------------------
# SIMULATE LECTURER NOTIFICATION
# --------------------------------------------------

@router.post(
    "/cases/{reply_case_id}/notify",
    response_model=ReplyCaseResponse,
)
def notify_lecturer(
    reply_case_id: str,
    service=Depends(get_reply_service),
):
    try:
        case = service.mark_notified(
            reply_case_id=reply_case_id,
        )

        return serialize_case(case)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# --------------------------------------------------
# SUBMIT LECTURER REPLY + ASSESSMENT
# --------------------------------------------------

@router.post(
    "/cases/{reply_case_id}/reply",
    response_model=SubmitReplyResponse,
)
def submit_lecturer_reply(
    reply_case_id: str,
    payload: SubmitReplyRequest,
    service=Depends(get_reply_service),
):
    try:
        case, assessment = service.submit_reply(
            reply_case_id=reply_case_id,
            text=payload.text,
            reason=payload.reason,
        )

        return SubmitReplyResponse(
            case=serialize_case(case),
            assessment=ReplyAssessmentResponse(
                reason=assessment.reason.value,
                action=assessment.action.value,
                evidence_verified=assessment.evidence_verified,
                explanation=assessment.explanation,
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
