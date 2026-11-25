from vio_backend.mts_course_synopsis import (
    CSV_FIELDS,
    csv_row,
    parse_course_entries,
    parse_course_listing,
    parse_synopsis_html,
    page_blocks,
    title_case,
)
from bs4 import BeautifulSoup


FIXTURE_HTML = """
<html>
<head><title>MTS Course Synopsis</title></head>
<body>
<main id="content">
<div class="page-content">
<p><strong>COURSE SYNOPSES</strong></p>
<p><strong>MTS 101: ALGEBRA (3 UNITS)</strong></p>
<p>Set theory and algebra synopsis.</p>
<p></p>
<p>MTS 102 CACULUS AND TRIGONOMETRY (3UNITS)</p>
<p>Calculus synopsis.</p>
<p>MTS 363 INTRODUCTION TO OPERATIONS RESEARCH (2 UNITS) PRQT MTS 223 OR MTS 212</p>
<p>Operations research synopsis.</p>
<p>MTS 465; OPTIMIZATION THEORY (3 UNTIS) PRQT MTS 363 OR MTS 351</p>
<p>Optimization synopsis.</p>
<p>MTS 499: PROJECT (6 UNITS)</p>
<p>Independent research works in mathematics</p>
<p>(5) ON-GOING DEPARTMENTAL RESEARCH</p>
<p>Course Listing</p>
<p>100 Level – First Semester</p>
<p>Course Code Course Title<br>MTS 101 Algebra<br>MTS 102 Calculus and Trigonometry</p>
<p>100 Level – Second Semester</p>
<p>Course Code Course Title<br>MTS 103 Vector and Geometry</p>
</div>
</main>
</body>
</html>
"""


def test_title_case_preserves_roman_numerals_and_minor_words():
    assert title_case("MATHEMATICAL METHODS II") == "Mathematical Methods II"
    assert title_case("INTRODUCTION TO OPERATIONS RESEARCH") == "Introduction to Operations Research"
    assert title_case("REAL ANALYSIS I") == "Real Analysis I"


def test_parse_course_entries_handles_source_format_variants():
    soup = BeautifulSoup(FIXTURE_HTML, "html.parser")
    entries = parse_course_entries(page_blocks(soup))

    assert [entry["course_code"] for entry in entries] == [
        "MTS 101",
        "MTS 102",
        "MTS 363",
        "MTS 465",
        "MTS 499",
    ]
    by_code = {entry["course_code"]: entry for entry in entries}
    assert by_code["MTS 101"]["course_title"] == "Algebra"
    assert by_code["MTS 101"]["units"] == 3
    assert by_code["MTS 102"]["units"] == 3
    assert by_code["MTS 363"]["prerequisites"] == "MTS 223 OR MTS 212"
    assert by_code["MTS 465"]["course_title"] == "Optimization Theory"
    assert by_code["MTS 465"]["units"] == 3
    assert by_code["MTS 499"]["synopsis"] == "Independent research works in mathematics"


def test_parse_course_listing_extracts_explicit_semesters():
    soup = BeautifulSoup(FIXTURE_HTML, "html.parser")
    listing = parse_course_listing(page_blocks(soup))

    assert listing["MTS 101"]["semester"] == 1
    assert listing["MTS 101"]["title"] == "Algebra"
    assert listing["MTS 102"]["semester"] == 1
    assert listing["MTS 103"]["semester"] == 2
    assert "MTS 363" not in listing


def test_parse_synopsis_html_merges_listing_and_preserves_synopses():
    payload = parse_synopsis_html(
        FIXTURE_HTML,
        source_url="https://funaab.edu.ng/mts-course-synopsis/",
        fetched_at="2026-11-15T00:00:00+00:00",
    )

    assert payload["page_title"] == "MTS Course Synopsis"
    assert payload["course_count"] == 5
    courses = {course["course_code"]: course for course in payload["courses"]}

    assert courses["MTS 101"]["semester"] == 1
    assert courses["MTS 101"]["semester_source"] == "course_listing"
    assert courses["MTS 101"]["synopsis"] == "Set theory and algebra synopsis."
    assert courses["MTS 363"]["semester"] is None
    assert courses["MTS 363"]["semester_source"] == "not_stated"
    assert courses["MTS 465"]["course_title"] == "Optimization Theory"
    assert any("Prerequisite text may be malformed" in note for note in courses["MTS 465"]["notes"]) is False


def test_csv_row_uses_existing_candidate_columns():
    payload = parse_synopsis_html(
        FIXTURE_HTML,
        source_url="https://funaab.edu.ng/mts-course-synopsis/",
        fetched_at="2026-11-15T00:00:00+00:00",
    )
    row = csv_row(payload["courses"][0], payload["source_url"])

    assert list(row) == CSV_FIELDS
    assert row["course_code"] == "MTS 101"
    assert row["semester"] == 1
    assert row["source_status"] == "official_public_date_unknown"
