from bs4 import BeautifulSoup

from vio_backend.funaab_synopsis import (
    SourceMeta,
    classify_search_item,
    classify_trailing,
    content_lines,
    parse_generic_lines,
    parse_page_html,
    parse_structured_fields,
    source_meta,
)


def meta_for(url: str, title: str, kind: str = "department_synopsis", mode: str = "generic_lines") -> SourceMeta:
    return source_meta(title, kind, mode, url)


def test_department_label_from_acronym_and_full_title() -> None:
    acronym = meta_for("https://funaab.edu.ng/phs-course-synopsis/", "PHS COURSE SYNOPSIS – FUNAAB")
    assert acronym.department == "PHS"
    assert acronym.department_acronym == "PHS"

    full = meta_for(
        "https://funaab.edu.ng/mce-course-synopsis/",
        "COURSE SYNOPSIS OF MECHANICAL ENGINEERING – FUNAAB",
    )
    assert full.department == "Mechanical Engineering"
    assert full.department_acronym is None

    programme = meta_for(
        "https://funaab.edu.ng/agricultural-administration-course-sysnopsis/",
        "Agricultural Administration Course Synopsis",
    )
    assert programme.department == "Agricultural Administration"


def test_classify_search_item_splits_course_and_department_pages() -> None:
    course = classify_search_item("MCE 516 Course Synopsis", "https://funaab.edu.ng/mce-516-course-synopsis/")
    assert course["page_kind"] == "course_synopsis_page"
    assert course["parse_mode"] == "structured_fields"

    department = classify_search_item("FST Course Synopsis", "https://funaab.edu.ng/fst-course-synopsis/")
    assert department["page_kind"] == "department_synopsis"
    assert department["parse_mode"] == "generic_lines"


def test_classify_trailing_distinguishes_prerequisites_from_synopsis() -> None:
    assert classify_trailing("MTS 342") == ("prerequisite", "MTS 342")
    assert classify_trailing("PRQT MTS 101 OR MTS 102") == ("prerequisite", "MTS 101 OR MTS 102")
    assert classify_trailing("BIO 206, BCH 201, 202") == ("prerequisite", "BIO 206, BCH 201, 202")
    assert classify_trailing("Belts, Bolt loading, Brakes") == ("synopsis", "Belts, Bolt loading, Brakes")
    assert classify_trailing("") == ("none", None)


def test_generic_parser_handles_inline_synopsis_and_derived_levels() -> None:
    html = """
    <html><body><div class="page-content">
      <p>COURSE DESCRIPTION</p>
      <p>FST 201: INTRODUCTION TO FOOD TECHNOLOGY (2 Units)<br/>Philosophy and definition of food technology.</p>
      <p>FST 304: FOOD MICROBIOLOGY  (3 Units)<br/>Natural flora of importance in foods.</p>
    </div></body></html>
    """
    meta = meta_for(
        "https://funaab.edu.ng/fst-course-synopsis/",
        "Food Science and Technology Course Synopsis",
    )
    payload = parse_page_html(html, meta, "2026-10-17T00:00:00+00:00")
    assert payload["course_count"] == 2
    first = payload["courses"][0]
    assert first["course_code"] == "FST 201"
    assert first["course_title"] == "Introduction to Food Technology"
    assert first["units"] == 2
    assert first["level"] == 200
    assert first["semester"] is None
    assert first["synopsis"] == "Philosophy and definition of food technology."
    assert first["department"] == "Food Science and Technology"
    second = payload["courses"][1]
    assert second["course_code"] == "FST 304"
    assert second["level"] == 300


def test_generic_parser_handles_level_headings_and_separate_synopsis() -> None:
    html = """
    <html><body><div class="page-content">
      <p>100 LEVEL</p>
      <p><strong>BIO 101 – GENERAL BIOLOGY 1 (2 Units)</strong></p>
      <p>The plant cell, prokaryotic and eukaryotic cells.</p>
      <p>200 LEVEL – FIRST SEMESTER</p>
      <p><strong>BIO 201: GENERAL BIOLOGY II (2 Units)</strong></p>
      <p>Continuation of general biology topics.</p>
      <p>200 LEVEL – SECOND SEMESTER</p>
      <p><strong>BIO 202: BOTANY (2 Units)</strong></p>
      <p>Principles of botany.</p>
    </div></body></html>
    """
    meta = meta_for("https://funaab.edu.ng/pab-course-synopsis/", "PAB COURSE SYNOPSIS")
    courses = parse_generic_lines(content_lines(BeautifulSoup(html, "html.parser")), meta)
    assert [course["course_code"] for course in courses] == ["BIO 101", "BIO 201", "BIO 202"]
    assert courses[0]["level"] == 100
    assert courses[0]["semester"] is None
    assert courses[0]["level_source"] == "level_heading"
    assert courses[1]["level"] == 200
    assert courses[1]["semester"] == 1
    assert courses[2]["semester"] == 2
    assert courses[0]["synopsis"] == "The plant cell, prokaryotic and eukaryotic cells."


def test_structured_course_page_parser() -> None:
    html = """
    <html><body><div class="page-content">
      <p><strong>COURSE CODE:</strong> MCE 516</p>
      <p><strong>COURSE TITLE:</strong> Energy Technology</p>
      <p><strong>NUMBER OF UNITS:</strong> 2 Units</p>
      <p><strong>COURSE SYNOPSIS:</strong></p>
      <p>This course examines energy conversion and conservation principles.</p>
      <p>MCE 516 Lecture Note</p>
      <p>Quick Links</p>
    </div></body></html>
    """
    meta = meta_for(
        "https://funaab.edu.ng/mce-516-course-synopsis/",
        "MCE 516 Course Synopsis",
        kind="course_synopsis_page",
        mode="structured_fields",
    )
    payload = parse_page_html(html, meta, "2026-10-17T00:00:00+00:00")
    assert payload["course_count"] == 1
    course = payload["courses"][0]
    assert course["course_code"] == "MCE 516"
    assert course["department"] == "MCE"
    assert course["course_title"] == "Energy Technology"
    assert course["units"] == 2
    assert course["level"] == 500
    assert course["synopsis"] == "This course examines energy conversion and conservation principles."


def test_structured_course_page_parser_handles_split_labels_and_colon_values() -> None:
    html = """
    <html><body><div class="page-content">
      <p><strong>COURSE CODE</strong>: FSM 311</p>
      <p><strong>COURSE TITLE</strong>: Research Methodology</p>
      <p><strong>NUMBER OF UNITS: </strong>2 Units</p>
      <p><strong>COURSE SYNOPSIS</strong></p>
      <p>The Research process; concept development, focus and objectives.</p>
      <p>FSM 311 Lecture Note</p>
    </div></body></html>
    """
    meta = meta_for(
        "https://funaab.edu.ng/fsm-311-course-synopsis/",
        "FSM 311 Course Synopsis",
        kind="course_synopsis_page",
        mode="structured_fields",
    )
    payload = parse_page_html(html, meta, "2026-10-17T00:00:00+00:00")
    assert payload["course_count"] == 1
    course = payload["courses"][0]
    assert course["course_code"] == "FSM 311"
    assert course["course_title"] == "Research Methodology"
    assert course["units"] == 2
    assert course["synopsis"] == "The Research process; concept development, focus and objectives."
