from dataclasses import dataclass
from enum import Enum

class ReplyReason(str, Enum):
    ILLNESS = "illness"
    OFFICIAL_DUTY = "official_duty"
    RESCHEDULED = "rescheduled"
    VENUE_ISSUE = "venue_issue"
    DISPUTED = "disputed"
    OTHER = "other"

class AssessmentAction(str, Enum):
    RECORD_EXPLANATION = "record_explanation"
    VERIFY_EVIDENCE = "verify_evidence"
    REFER_TO_APPEALS = "refer_to_appeals"
    REQUIRE_FURTHER_ASSESSMENT = "require_further_assessment"

@dataclass(frozen=True)
class ReplyAssessment:
    reason: ReplyReason
    action: AssessmentAction
    evidence_verified: bool
    explanation: str


def assess_reply(
    reason: ReplyReason,
    explanation: str,
) -> ReplyAssessment:

    if not isinstance(reason, ReplyReason):
        raise ValueError("Invalid lecturer reply reason.")

    if not isinstance(explanation, str):
        raise ValueError("Explanation must be text.")

    explanation = explanation.strip()

    if not explanation:
        raise ValueError("Explanation cannot be empty.")

    if len(explanation) > 2000:
        raise ValueError("Explanation exceeds 2000 characters.")

    if reason == ReplyReason.DISPUTED:
        action = AssessmentAction.REFER_TO_APPEALS

    elif reason == ReplyReason.RESCHEDULED:
        action = AssessmentAction.VERIFY_EVIDENCE

    elif reason == ReplyReason.OTHER:
        action = AssessmentAction.REQUIRE_FURTHER_ASSESSMENT

    else:
        action = AssessmentAction.RECORD_EXPLANATION

    return ReplyAssessment(
        reason=reason,
        action=action,
        evidence_verified=False,
        explanation=explanation,
    )
