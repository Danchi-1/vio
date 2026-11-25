from datetime import date

import pytest

from vio_backend.errors import ApiError
from vio_backend.report_rules import (
    SessionWindow,
    generate_tracking_code,
    is_valid_tracking_code,
    normalize_description,
    validate_category,
    validate_incident_date,
)


def window(**overrides) -> SessionWindow:
    base = dict(
        session="2026/2027",
        status="proposed",
        first_lectures_start=date(2026, 9, 21),
        first_lectures_end=date(2026, 12, 18),
        first_exams_start=date(2027, 1, 4),
        second_lectures_start=date(2027, 2, 15),
        second_lectures_end=date(2027, 5, 14),
        second_exams_start=date(2027, 5, 24),
        session_ends=date(2027, 7, 29),
    )
    base.update(overrides)
    return SessionWindow(**base)


def test_normalize_description_rejects_short_and_long():
    with pytest.raises(ApiError) as exc:
        normalize_description("too short")
    assert exc.value.status_code == 422
    with pytest.raises(ApiError):
        normalize_description("x" * 2001)
    assert normalize_description("  " + "a" * 25 + "  ") == "a" * 25


def test_validate_category_rejects_unknown():
    assert validate_category("class_not_held") == "class_not_held"
    with pytest.raises(ApiError):
        validate_category("not_a_category")


def test_teaching_category_accepts_incident_inside_lecture_window():
    validate_incident_date(
        date(2026, 10, 12),
        window=window(),
        category="class_not_held",
        today=date(2026, 11, 22),
    )


def test_teaching_category_rejects_after_exam_period_begins():
    with pytest.raises(ApiError) as exc:
        validate_incident_date(
            date(2026, 10, 12),
            window=window(),
            category="poor_delivery",
            today=date(2027, 1, 10),  # after first_semester_exams_start
        )
    assert exc.value.status_code == 422


def test_teaching_category_rejects_incident_outside_lecture_windows():
    with pytest.raises(ApiError):
        validate_incident_date(
            date(2027, 1, 10),  # inside exam period, not lectures
            window=window(),
            category="class_not_held",
            today=date(2026, 11, 22),
        )


def test_teaching_category_uses_second_semester_window():
    validate_incident_date(
        date(2027, 3, 1),
        window=window(),
        category="practical_not_held",
        today=date(2027, 4, 1),
    )
    with pytest.raises(ApiError):
        validate_incident_date(
            date(2027, 3, 1),
            window=window(),
            category="practical_not_held",
            today=date(2027, 5, 25),  # after second_semester_exams_start
        )


def test_assessment_category_allows_exam_period_but_not_outside_session():
    validate_incident_date(
        date(2027, 1, 10),  # during first-semester exams
        window=window(),
        category="unfair_assessment",
        today=date(2027, 1, 15),
    )
    with pytest.raises(ApiError):
        validate_incident_date(
            date(2026, 8, 1),  # before lectures start
            window=window(),
            category="unfair_assessment",
            today=date(2026, 11, 22),
        )


def test_open_category_only_rejects_future_dates():
    validate_incident_date(
        date(2026, 1, 5),
        window=window(),
        category="other_academic",
        today=date(2026, 11, 22),
    )
    with pytest.raises(ApiError):
        validate_incident_date(
            date(2027, 1, 1),
            window=window(),
            category="institutional",
            today=date(2026, 11, 22),
        )


def test_missing_calendar_boundary_fails_closed():
    with pytest.raises(ApiError) as exc:
        validate_incident_date(
            date(2026, 10, 12),
            window=window(first_exams_start=None),
            category="class_not_held",
            today=date(2026, 11, 22),
        )
    assert exc.value.status_code == 503


def test_tracking_code_format():
    code = generate_tracking_code()
    assert is_valid_tracking_code(code)
    assert code.startswith("VIO-")
    assert len(code) == 12
    assert not is_valid_tracking_code("vio-abcdefgh")
    assert not is_valid_tracking_code("VIO-ABCDEFGH0")  # invalid char? 0 not in alphabet
