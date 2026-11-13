from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone

class ReplyStatus(str, Enum):
    PENDING_NOTIFICATION = "pending_notification"
    AWAITING_REPLY = "awaiting_reply"
    REPLIED = "replied"
    EXPIRED = "expired"

ALLOWED_TRANSITIONS = {
    ReplyStatus.PENDING_NOTIFICATION: {
        ReplyStatus.AWAITING_REPLY
    },
    ReplyStatus.AWAITING_REPLY: {
        ReplyStatus.REPLIED,
        ReplyStatus.EXPIRED
    },
    ReplyStatus.REPLIED: set(),
    ReplyStatus.EXPIRED: set()
}


def can_transition(current_status, new_status):
    allowed = ALLOWED_TRANSITIONS.get(
        current_status, set()
    )
    return new_status in allowed


@dataclass
class LecturerReplyCase:
    reply_case_id: str
    finding_id: str
    lecturer_id: str
    deadline: datetime
    status: ReplyStatus = ReplyStatus.PENDING_NOTIFICATION
    reply_text: str | None = None
    reply_reason: str | None = None
    
    def submit_reply(self, text: str, now: datetime):
        if self.status != ReplyStatus.AWAITING_REPLY:
            raise ValueError("This case is not accepting replies.")

        if now > self.deadline:
            raise ValueError("The reply deadline has passed.")

        if not text.strip():
            raise ValueError("Reply cannot be empty.")

        self.reply_text = text
        self.status = ReplyStatus.REPLIED


    def check_deadline(self, now: datetime):
        if self.status != ReplyStatus.AWAITING_REPLY:
            return False

        if now > self.deadline:
            self.status = ReplyStatus.EXPIRED
            return True

        return False

