"""Deterministic intake rules for student reports (M3).

These rules own every accept/reject decision; model output is only ever
advisory input verified against them. All category timing follows
docs/DECISIONS.md (2026-11-09): teaching-period complaints close once the
relevant exam period begins, assessment complaints may be filed during or
after the exam, and filing priority decays with recency but does not bar
verified historical reports.

The academic calendar is currently ``proposed`` (see academic_sessions);
windows are evaluated against it and results inherit that provisional
status. Missing boundary dates fail closed rather than guessing.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import date

from vio_backend.errors import ApiError

REPORT_CATEGORIES = frozenset(
    {
        "class_not_held",
        "practical_not_held",
        "outline_incomplete",
        "poor_delivery",
        "unfair_assessment",
        "unresolved_complaint",
        "other_academic",
        "institutional",
    }
)

# Complaints about teaching that happened (or should have happened) in a
# lecture/practical window. They must be filed before that window's exam
# period begins.
TEACHING_CATEGORIES = frozenset(
    {"class_not_held", "practical_not_held", "outline_incomplete", "poor_delivery"}
)
# Assessment complaints may be filed during or after the exam.
ASSESSMENT_CATEGORIES = frozenset({"unfair_assessment"})
# Remaining categories have no exam-window constraint beyond "not future".
OPEN_CATEGORIES = REPORT_CATEGORIES - TEACHING_CATEGORIES - ASSESSMENT_CATEGORIES

MAX_DESCRIPTION_LENGTH = 2000
MIN_DESCRIPTION_LENGTH = 20
TRACKING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
TRACKING_CODE_LENGTH = 8

_TRACKING_CODE_RE = re.compile(r"^VIO-[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$")


@dataclass(frozen=True)
class SessionWindow:
    """Relevant date boundaries of the current academic session.

    Any field may be None when the source calendar does not state it;
    rules that need a missing boundary fail closed.
    """

    session: str
    status: str
    first_lectures_start: date | None
    first_lectures_end: date | None
    first_exams_start: date | None
    second_lectures_start: date | None
    second_lectures_end: date | None
    second_exams_start: date | None
    session_ends: date | None


def normalize_description(raw: str) -> str:
    description = raw.strip()
    if len(description) < MIN_DESCRIPTION_LENGTH:
        raise ApiError(
            422,
            "validation_failed",
            "Please give a fuller factual account.",
            {"description": [f"Must be at least {MIN_DESCRIPTION_LENGTH} characters."]},
        )
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ApiError(
            422,
            "validation_failed",
            "That report is too long.",
            {"description": [f"Must be at most {MAX_DESCRIPTION_LENGTH} characters."]},
        )
    return description


def validate_category(category: str) -> str:
    if category not in REPORT_CATEGORIES:
        raise ApiError(
            422,
            "validation_failed",
            "Choose a valid report category.",
            {"category": ["Unknown category."]},
        )
    return category


def _require_window(window: SessionWindow, *fields: tuple[str, date | None]) -> None:
    missing = [name for name, value in fields if value is None]
    if missing:
        raise ApiError(
            503,
            "service_unavailable",
            "The academic calendar is missing dates needed to check this report.",
            {"academic_session": [f"Missing {', '.join(missing)}."]},
        )


def _semester_window(window: SessionWindow, incident: date) -> tuple[str, date, date, date | None]:
    """Return (label, lectures_start, lectures_end, exams_start) for the
    semester containing the incident date, or raise if it fits neither."""
    _require_window(
        window,
        ("first_semester_lectures_start", window.first_lectures_start),
        ("first_semester_lectures_end", window.first_lectures_end),
    )
    if window.first_lectures_start <= incident <= window.first_lectures_end:
        _require_window(window, ("first_semester_exams_start", window.first_exams_start))
        return "first", window.first_lectures_start, window.first_lectures_end, window.first_exams_start
    if (
        window.second_lectures_start is not None
        and window.second_lectures_end is not None
        and window.second_lectures_start <= incident <= window.second_lectures_end
    ):
        _require_window(window, ("second_semester_exams_start", window.second_exams_start))
        return "second", window.second_lectures_start, window.second_lectures_end, window.second_exams_start
    raise ApiError(
        422,
        "validation_failed",
        "The incident date does not fall inside a teaching period of the current session.",
        {"incident_date": ["Must be a date within a lecture period."]},
    )


def validate_incident_date(
    incident: date, *, window: SessionWindow, category: str, today: date
) -> None:
    """Enforce the category-specific filing rules. ``today`` is the filing
    date (server date, UTC)."""
    if incident > today:
        raise ApiError(
            422,
            "validation_failed",
            "The incident date cannot be in the future.",
            {"incident_date": ["Must not be after today."]},
        )

    if category in TEACHING_CATEGORIES:
        _, _, _, exams_start = _semester_window(window, incident)
        assert exams_start is not None  # _require_window guarantees it
        if today > exams_start:
            raise ApiError(
                422,
                "validation_failed",
                "It is too late to report this: the exam period for that teaching window has already begun.",
                {"incident_date": ["Filing closed when the exam period started."]},
            )
        return

    if category in ASSESSMENT_CATEGORIES:
        # Assessment complaints may be filed during or after the exam, but
        # not before the session's teaching periods begin or after it ends.
        _require_window(
            window,
            ("first_semester_lectures_start", window.first_lectures_start),
            ("session_ends", window.session_ends),
        )
        if incident < window.first_lectures_start or incident > window.session_ends:
            raise ApiError(
                422,
                "validation_failed",
                "The incident date is outside the current academic session.",
                {"incident_date": ["Must fall within the current session."]},
            )
        return

    # OPEN_CATEGORIES: only the not-in-future rule applies; older verified
    # incidents keep reduced pursuit priority rather than being barred.


def generate_tracking_code() -> str:
    return "VIO-" + "".join(secrets.choice(TRACKING_CODE_ALPHABET) for _ in range(TRACKING_CODE_LENGTH))


def is_valid_tracking_code(code: str) -> bool:
    return bool(_TRACKING_CODE_RE.match(code))
