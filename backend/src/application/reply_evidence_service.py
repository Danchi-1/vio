from dataclasses import dataclass
from datetime import date, datetime
from backend.src.domain.reply_assessment import (
    ReplyReason,
    AssessmentAction,
    assess_reply,
)
from backend.src.application.notice_assessment_service import (
    NoticeAssessmentService,
)


@dataclass(frozen=True)
class ReplyEvidenceResult:
    finding_id: str
    lecturer_id: str
    reply_reason: str
    assessment_action: str
    notice_verified: bool
    notice_id: str | None
    next_action: str
    explanation: str


class ReplyEvidenceService:

    def __init__(self, notice_repository):
        self.notice_service = NoticeAssessmentService(
            notice_repository
        )

    def process_reply(
        self,
        finding_id: str,
        lecturer_id: str,
        course_id: str,
        incident_date: date,
        scheduled_start: datetime,
        reason: ReplyReason,
        reply_text: str,
    ) -> ReplyEvidenceResult:

        # Step 1: Validate and classify the reply
        assessment = assess_reply(
            reason=reason,
            explanation=reply_text,
        )

        # Step 2: Handle disputes separately
        if assessment.action == AssessmentAction.REFER_TO_APPEALS:
            return ReplyEvidenceResult(
                finding_id=finding_id,
                lecturer_id=lecturer_id,
                reply_reason=reason.value,
                assessment_action=assessment.action.value,
                notice_verified=False,
                notice_id=None,
                next_action="refer_to_appeals",
                explanation="Lecturer disputes the finding.",
            )

        # Step 3: Check whether evidence verification
        # is required by the preliminary classification
        if assessment.action != AssessmentAction.VERIFY_EVIDENCE:
            return ReplyEvidenceResult(
                finding_id=finding_id,
                lecturer_id=lecturer_id,
                reply_reason=reason.value,
                assessment_action=assessment.action.value,
                notice_verified=False,
                notice_id=None,
                next_action=assessment.action.value,
                explanation=(
                    "No advance-notice verification was "
                    "requested by this rule."
                ),
            )

        # Step 4: Verify advance notice
        notice_result = (
            self.notice_service.assess_advance_notice(
                finding_id=finding_id,
                course_id=course_id,
                lecturer_id=lecturer_id,
                incident_date=incident_date,
                scheduled_start=scheduled_start,
            )
        )

        # Step 5: Determine the next workflow action
        if notice_result.verified:
            next_action = "send_evidence_to_scoring"
        else:
            next_action = "hold_for_evidence"

        return ReplyEvidenceResult(
            finding_id=finding_id,
            lecturer_id=lecturer_id,
            reply_reason=reason.value,
            assessment_action=assessment.action.value,
            notice_verified=notice_result.verified,
            notice_id=notice_result.notice_id,
            next_action=next_action,
            explanation=notice_result.explanation,
        )
