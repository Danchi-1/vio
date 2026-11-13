from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum

class NoticeKind(str, Enum):
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    EXTRA_CLASS = "extra_class"

class NoticeVerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class ClassNotice:
    notice_id: str
    course_id: str
    lecturer_id: str
    kind: NoticeKind
    for_date: date
    posted_at: datetime
    trusted_source: bool


@dataclass(frozen=True)
class NoticeVerificationResult:
    status: NoticeVerificationStatus
    notice_id: str | None
    reason: str


def verify_advance_notice(
    notice: ClassNotice | None,
    course_id: str,
    lecturer_id: str,
    incident_date: date,
    scheduled_start: datetime,
) -> NoticeVerificationResult:

    if notice is None:
        return NoticeVerificationResult(
            status=NoticeVerificationStatus.UNVERIFIED,
            notice_id=None,
            reason="No notice record was found.",
        )

    if not notice.trusted_source:
        return NoticeVerificationResult(
            status=NoticeVerificationStatus.UNVERIFIED,
            notice_id=notice.notice_id,
            reason="The notice source is not trusted.",
        )

    if notice.course_id != course_id:
        return NoticeVerificationResult(
            status=NoticeVerificationStatus.UNVERIFIED,
            notice_id=notice.notice_id,
            reason="Notice belongs to another course.",
        )

    if notice.lecturer_id != lecturer_id:
        return NoticeVerificationResult(
            status=NoticeVerificationStatus.UNVERIFIED,
            notice_id=notice.notice_id,
            reason="Notice belongs to another lecturer.",
        )

    if notice.for_date != incident_date:
        return NoticeVerificationResult(
            status=NoticeVerificationStatus.UNVERIFIED,
            notice_id=notice.notice_id,
            reason="Notice refers to another date.",
        )

    if notice.kind not in {
        NoticeKind.CANCELLED,
        NoticeKind.RESCHEDULED,
    }:
        return NoticeVerificationResult(
            status=NoticeVerificationStatus.UNVERIFIED,
            notice_id=notice.notice_id,
            reason="Notice type is not relevant.",
        )

    if (
        notice.posted_at.tzinfo is None
        or scheduled_start.tzinfo is None
    ):
        raise ValueError(
            "Timestamps must include timezone information."
        )

    if notice.posted_at >= scheduled_start:
        return NoticeVerificationResult(
            status=NoticeVerificationStatus.UNVERIFIED,
            notice_id=notice.notice_id,
            reason="Notice was not posted before the lecture.",
        )

    return NoticeVerificationResult(
        status=NoticeVerificationStatus.VERIFIED,
        notice_id=notice.notice_id,
        reason="Advance notice passed all verification checks.",
    )
