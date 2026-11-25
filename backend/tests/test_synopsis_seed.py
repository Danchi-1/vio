import csv

from vio_backend.synopsis_seed import load_seed_rows


def write_csv(path, rows):
    fields = [
        "institution", "department", "department_acronym", "source_kind", "page_title",
        "course_code", "course_title", "level", "semester", "units", "prerequisites",
        "source_url", "source_status", "source_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def row(**overrides):
    base = {
        "institution": "FUNAAB",
        "department": "Electrical/Electronics Engineering",
        "department_acronym": "",
        "source_kind": "department_synopsis",
        "page_title": "ELE Course Synopsis",
        "course_code": "ELE 201",
        "course_title": "Applied Electricity I",
        "level": "200",
        "semester": "1",
        "units": "2",
        "prerequisites": "",
        "source_url": "https://funaab.edu.ng/ele-course-synopsis/",
        "source_status": "official_public_date_unknown",
        "source_notes": "",
    }
    base.update(overrides)
    return base


def test_load_seed_rows_filters_and_deduplicates(tmp_path):
    csv_path = tmp_path / "candidates.csv"
    write_csv(
        csv_path,
        [
            row(),
            row(course_code="ELE 999", course_title="Postgraduate Course", level="700"),
            row(course_code="ELE 201", course_title="Duplicate", semester=""),
            row(course_code="ELE 202", course_title="Applied Electricity II", semester="2"),
            row(source_kind="course_synopsis_page", course_code="ELE 999", course_title="Course Page"),
        ],
    )
    rows = load_seed_rows(csv_path)
    assert [(r["course_code"], r["semester"]) for r in rows] == [("ELE 201", 1), ("ELE 202", 2)]


def test_load_seed_rows_prefers_row_with_semester_on_duplicate(tmp_path):
    csv_path = tmp_path / "candidates.csv"
    write_csv(
        csv_path,
        [
            row(course_code="ELE 201", semester=""),
            row(course_code="ELE 201", course_title="Applied Electricity I", semester="1"),
        ],
    )
    rows = load_seed_rows(csv_path)
    assert len(rows) == 1
    assert rows[0]["semester"] == 1
