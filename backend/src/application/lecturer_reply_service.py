from datetime import datetime, timedelta, timezone
from uuid import uuid4
from backend.src.domain.lecturer_reply import (
    LecturerReplyCase,
    ReplyStatus,
)
from backend.src.domain.reply_assessment import (
    ReplyReason,
    assess_reply,
)

class LecturerReplyService:

    def __init__(self, repository):
        self.repository = repository

    def create_case(
        self,
        finding_id: str,
        lecturer_id: str,
    ):
        # Prevent duplicate reply opportunities
        for case in self.repository.list_cases():
            if (
                case.finding_id == finding_id
                and case.lecturer_id == lecturer_id
            ):
                raise ValueError(
                    "A reply case already exists for this "
                    "finding and lecturer."
                )

        case = LecturerReplyCase(
            reply_case_id=str(uuid4()),
            finding_id=finding_id,
            lecturer_id=lecturer_id,
            deadline=datetime.now(timezone.utc)
            + timedelta(days=5),
            status=ReplyStatus.PENDING_NOTIFICATION,
        )

        self.repository.save(case)

        return case

    def mark_notified(
        self,
        reply_case_id: str,
    ):
        case = self.repository.get(reply_case_id)

        if case is None:
            raise ValueError("Reply case not found.")

        if case.status != ReplyStatus.PENDING_NOTIFICATION:
            raise ValueError(
                "Case cannot be marked notified."
            )

        # Begin the five-day window after notification
        case.deadline = (
            datetime.now(timezone.utc)
            + timedelta(days=5)
        )

        case.status = ReplyStatus.AWAITING_REPLY

        self.repository.update(case)

        return case

   
    def submit_reply(
        self,
        reply_case_id: str,
        text: str,
        reason: ReplyReason,
    ):
        case = self.repository.get(reply_case_id)

        if case is None:
            raise ValueError("Reply case not found.")

        # First assess and validate the submitted response
        assessment = assess_reply(
            reason=reason,
            explanation=text,
        )

        # The server determines the current time
        now = datetime.now(timezone.utc)

        # Apply the existing state and deadline rules
        case.submit_reply(text=text, now=now)

        # Store the lecturer's selected reason
        case.reply_reason = assessment.reason.value

        # Save the updated reply case
        self.repository.update(case)

        return case, assessment


    def expire_overdue_cases(self):
        now = datetime.now(timezone.utc)

        expired_cases = []

        for case in self.repository.list_cases():
            if case.check_deadline(now):
                self.repository.update(case)
                expired_cases.append(case)

        return expired_cases
