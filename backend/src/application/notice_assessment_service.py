from dataclasses import dataclass
from datetime import date, datetime
from backend.src.domain.notice_verification import (
    NoticeVerificationStatus,
    verify_advance_notice,
)


@dataclass(frozen=True)
class NoticeAssessment:
    finding_id: str
    verified: bool
    notice_id: str | None
    explanation: str


class NoticeAssessmentService:

    def __init__(self, notice_repository):
        self.notice_repository = notice_repository

    def assess_advance_notice(
        self,
        finding_id: str,
        course_id: str,
        lecturer_id: str,
        incident_date: date,
        scheduled_start: datetime,
    ) -> NoticeAssessment:

        notices = self.notice_repository.find_for_incident(
            course_id=course_id,
            incident_date=incident_date,
        )

        if not notices:
            return NoticeAssessment(
                finding_id=finding_id,
                verified=False,
                notice_id=None,
                explanation="No matching notice was found.",
            )

        rejection_reasons = []

        for notice in notices:
            result = verify_advance_notice(
                notice=notice,
                course_id=course_id,
                lecturer_id=lecturer_id,
                incident_date=incident_date,
                scheduled_start=scheduled_start,
            )

            if result.status == NoticeVerificationStatus.VERIFIED:
                return NoticeAssessment(
                    finding_id=finding_id,
                    verified=True,
                    notice_id=result.notice_id,
                    explanation=result.reason,
                )

            rejection_reasons.append(result.reason)

        return NoticeAssessment(
            finding_id=finding_id,
            verified=False,
            notice_id=None,
            explanation=(
                "No qualifying advance notice was found. "
                + "; ".join(rejection_reasons)
            ),
        )
