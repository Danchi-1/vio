"""Harvest public FUNAAB course-synopsis pages into reviewable records.

This is the department/programme-level counterpart to ``mts_course_synopsis``.
It discovers public WordPress pages through the FUNAAB REST search endpoint,
parses department synopsis pages line-by-line, parses individual course
synopsis pages from their structured fields, and never accesses login-protected
services or Neon. Outputs are review artifacts, not production catalogue data.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import html as html_lib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from vio_backend.catalogue_harvest import validate_public_url
from vio_backend.mts_course_synopsis import SUSPECT_TITLE_TOKENS, title_case

WP_SEARCH_URL = "https://funaab.edu.ng/wp-json/wp/v2/search"
USER_AGENT = "VIO-public-catalogue-research/0.1"
INSTITUTION = "FUNAAB"
SOURCE_STATUS = "official_public_date_unknown"
DEFAULT_MANIFEST = Path("docs/data/funaab_synopsis_sources.json")
DEFAULT_OUTPUT_DIR = Path("docs/data/synopsis")
DEFAULT_CSV = Path("docs/data/funaab_course_synopsis_candidates.csv")
DEFAULT_REPORT = Path("docs/data/funaab_synopsis_harvest_report.json")

COURSE_PAGE_TITLE_RE = re.compile(r"^\s*[A-Z]{2,5}\s*\d{3,4}(?:/\d{3,4})?\s+courses?\s+synopsis", re.IGNORECASE)
COURSE_HEADING_RE = re.compile(
    r"^\s*(?P<prefix>[A-Z]{2,5})\s*(?P<number>\d{3,4}(?:/\d{3,4})?)\b(?P<rest>.*)$",
    re.IGNORECASE,
)
UNITS_RE = re.compile(
    r"\(\s*(?P<units>\d+(?:\.\d+)?|[IVX]+)\s*"
    r"(?P<word>UNITS?|UNTIS|Unit(?:s)?(?:\s+Each)?|Each)\s*\)",
    re.IGNORECASE,
)
LEVEL_RE = re.compile(r"^\s*(\d{3})\s*LEVEL\b(?P<rest>.*)$", re.IGNORECASE)
STOP_LINE_RE = re.compile(
    r"^\s*(?:"
    r"\(\s*\d+\s*\)\s*(?:ON-GOING|REQUIREMENT|LABORATORY|NAME OF DEPARTMENT|FOUNDATION YEAR|"
    r"ACCREDITATION|DEPARTMENTAL AFFLIATION|UNIVERSITY COURSE LEVEL)|"
    r"Course Listing\b|Quick Links\b|Policy Links\b|CONTACT US\b|Lecture Notes?\b|"
    r"Course Coordinator\b|Course Details\b|Other Lecturers\b|Office Location\b|E-?mail\b"
    r")",
    re.IGNORECASE,
)
PREREQ_PREFIX_RE = re.compile(r"^\s*(?:PRQT|PRE-?REQUISITES?|PREREQUISITES?)\s*[,;:]?\s*", re.IGNORECASE)
FIELD_RE = re.compile(
    r"^\s*(?P<key>COURSE\s+CODE|COURSE\s+TITLE|NUMBER\s+OF\s+UNITS|COURSE\s+SYNOPSIS|"
    r"COURSE\s+DURATION|COURSE\s+DETAILS)\s*:?\s*(?P<value>.*)$",
    re.IGNORECASE,
)
STRUCTURED_CODE_RE = re.compile(r"^\s*(?P<prefix>[A-Z]{2,5})\s*(?P<number>\d{3,4}(?:/\d{3,4})?)\s*$", re.IGNORECASE)
FIELD_VALUE_PREFIX_RE = re.compile(r"^[\s:：]+")
STRUCTURED_UNITS_RE = re.compile(r"^\s*(?P<units>\d+(?:\.\d+)?|[IVX]+)\s*(?:units?)?\s*$", re.IGNORECASE)
UPPERCASE_LIST_RE = re.compile(r"^[\d\s,;:/()A-Z&+\-]+$")
ROMAN_UNITS = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}

CSV_FIELDS = [
    "institution",
    "department",
    "department_acronym",
    "source_kind",
    "page_title",
    "course_code",
    "course_title",
    "level",
    "semester",
    "units",
    "prerequisites",
    "source_url",
    "source_status",
    "source_notes",
]


@dataclass(frozen=True)
class SourceMeta:
    url: str
    page_title: str
    page_kind: str
    parse_mode: str
    department: str
    department_acronym: str | None
    source_kind_label: str


def slug_for_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = path.split("/")[-1] if path else "index"
    return re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "index"


def classify_search_item(title: str, url: str) -> dict[str, Any]:
    clean_title = html_lib.unescape(title)
    if COURSE_PAGE_TITLE_RE.match(clean_title):
        return {
            "id": None,
            "title": clean_title,
            "url": url,
            "page_kind": "course_synopsis_page",
            "parse_mode": "structured_fields",
            "status": "pending",
            "course_count": None,
            "error": None,
        }
    if "synopsis" in clean_title.lower():
        return {
            "id": None,
            "title": clean_title,
            "url": url,
            "page_kind": "department_synopsis",
            "parse_mode": "generic_lines",
            "status": "pending",
            "course_count": None,
            "error": None,
        }
    return {
        "id": None,
        "title": clean_title,
        "url": url,
        "page_kind": "other",
        "parse_mode": None,
        "status": "skipped",
        "course_count": None,
        "error": None,
    }


async def discover_sources(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while page <= 10:
        response = await client.get(
            WP_SEARCH_URL,
            params={"search": "course synopsis", "per_page": 100, "page": page, "type": "post", "subtype": "page"},
        )
        response.raise_for_status()
        batch = response.json()
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        source = classify_search_item(item.get("title", ""), url)
        source["id"] = item.get("id")
        sources.append(source)
    return sources


def content_lines(soup: BeautifulSoup) -> list[str]:
    content = soup.select_one(".page-content") or soup.find("main", id="content") or soup.body or soup
    for br in content.find_all("br"):
        br.replace_with("\n")
    text = content.get_text("\n", strip=True)
    lines: list[str] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if line:
            lines.append(line)
    return lines


def clean_department_title(page_title: str) -> str:
    text = html_lib.unescape(page_title)
    text = re.sub(r"\s*[–—-]\s*FUNAAB\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)\bcourse\s+synopses\s+of\b", " ", text)
    text = re.sub(r"(?i)\bcourse\s+synopsis\s+of\b", " ", text)
    text = re.sub(r"(?i)\bcourse\s+synopses\b", " ", text)
    text = re.sub(r"(?i)\bcourse\s+synopsis\b", " ", text)
    text = re.sub(r"(?i)^\s*department\s+of\s+", " ", text)
    text = re.sub(r"(?i)\barea\s+of\s+specialisation\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—:;")
    if not text:
        return ""
    if text.isupper() and len(text) <= 6:
        return text
    return title_case(text)


def format_department_label(cleaned: str) -> str:
    if not cleaned:
        return ""
    if cleaned.isupper() and len(cleaned) <= 6:
        return cleaned
    if "/" in cleaned:
        return "/".join(title_case(part.strip()) for part in cleaned.split("/") if part.strip())
    return title_case(cleaned)


def source_meta(page_title: str, page_kind: str, parse_mode: str, url: str) -> SourceMeta:
    if page_kind == "course_synopsis_page":
        code_match = re.match(r"^\s*(?P<prefix>[A-Z]{2,5})\s*\d{3,4}", page_title, re.IGNORECASE)
        prefix = code_match.group("prefix").upper() if code_match else ""
        return SourceMeta(
            url=url,
            page_title=html_lib.unescape(page_title),
            page_kind=page_kind,
            parse_mode=parse_mode,
            department=prefix,
            department_acronym=prefix or None,
            source_kind_label="individual_course_synopsis_page",
        )
    cleaned = clean_department_title(page_title)
    label = format_department_label(cleaned)
    acronym = label if label.isupper() and len(label) <= 6 else None
    return SourceMeta(
        url=url,
        page_title=html_lib.unescape(page_title),
        page_kind=page_kind,
        parse_mode=parse_mode,
        department=label,
        department_acronym=acronym,
        source_kind_label="department_or_programme_synopsis",
    )


def parse_units_token(token: str, word: str) -> tuple[int | float | None, str | None]:
    upper = token.upper()
    if upper in ROMAN_UNITS:
        value: int | float = ROMAN_UNITS[upper]
    else:
        try:
            numeric = float(token)
            value = int(numeric) if numeric.is_integer() else numeric
        except ValueError:
            return None, "Units value could not be parsed; verify source."
    note = "Combined course code; source states units each." if "each" in word.lower() else None
    return value, note


def level_from_number(number: str) -> int | None:
    first = number.split("/", 1)[0]
    if not first or not first[0].isdigit():
        return None
    return int(first[0]) * 100


def classify_trailing(after_units: str) -> tuple[str, str | None]:
    if not after_units:
        return "none", None
    if PREREQ_PREFIX_RE.match(after_units):
        return "prerequisite", PREREQ_PREFIX_RE.sub("", after_units).strip() or None
    if any(char.islower() for char in after_units):
        return "synopsis", after_units
    if len(after_units) <= 120 and UPPERCASE_LIST_RE.fullmatch(after_units):
        return "prerequisite", after_units
    return "synopsis", after_units


def prerequisite_note(prerequisites: str | None) -> str | None:
    if not prerequisites:
        return None
    upper = prerequisites.upper()
    if upper.startswith("OR ") or re.match(r"^\d{3}\b", prerequisites):
        return "Prerequisite text may be malformed; verify against source."
    return None


def suspect_title_note(title_as_written: str) -> str | None:
    upper = title_as_written.upper()
    if any(token in upper for token in SUSPECT_TITLE_TOKENS):
        return "Source title spelling may be nonstandard; verify canonical title."
    return None


def match_course_heading(line: str) -> dict[str, Any] | None:
    match = COURSE_HEADING_RE.match(line)
    if match is None:
        return None
    rest = match.group("rest")
    units_match = UNITS_RE.search(rest)
    if units_match is None:
        return None
    before_units = re.sub(r"^[\s:;–—-]+", "", rest[: units_match.start()]).strip()
    after_units = rest[units_match.end() :].strip()
    return {
        "prefix": match.group("prefix").upper(),
        "number": match.group("number"),
        "title_as_written": before_units,
        "units_raw": units_match.group("units"),
        "unit_word": units_match.group("word"),
        "trailing": after_units,
        "heading_line": line,
    }


def base_notes(meta: SourceMeta) -> list[str]:
    return [
        "Official FUNAAB public course synopsis page; page version date unknown; verify currentness.",
        f"Source kind: {meta.source_kind_label}.",
    ]


def finalize_generic_course(
    current: dict[str, Any], meta: SourceMeta, section: str
) -> dict[str, Any]:
    trailing_kind, trailing_value = classify_trailing(current["trailing"])
    synopsis_parts = list(current["synopsis_parts"])
    prerequisites = None
    prerequisites_text = None
    if trailing_kind == "prerequisite":
        prerequisites = trailing_value
        prerequisites_text = current["trailing"] or None
    elif trailing_kind == "synopsis" and trailing_value:
        synopsis_parts.insert(0, trailing_value)

    units, units_note = parse_units_token(current["units_raw"], current["unit_word"])
    level = current["level"] if current["level"] is not None else level_from_number(current["number"])
    notes = base_notes(meta)
    if current["level"] is None:
        notes.append("Level derived from course number; no level heading on page.")
    if current["semester"] is None:
        notes.append("Semester not stated on page.")
    malformed = prerequisite_note(prerequisites)
    if malformed:
        notes.append(malformed)
    suspect = suspect_title_note(current["title_as_written"])
    if suspect:
        notes.append(suspect)
    if units_note:
        notes.append(units_note)
    if section:
        notes.append(f"Section heading on page: {section}.")

    return {
        "institution": INSTITUTION,
        "department": meta.department,
        "department_acronym": meta.department_acronym,
        "source_kind": meta.page_kind,
        "source_page_title": meta.page_title,
        "source_url": meta.url,
        "course_code": f"{current['prefix']} {current['number']}",
        "course_number": current["number"],
        "level": level,
        "level_source": "level_heading" if current["level"] is not None else "course_code",
        "semester": current["semester"],
        "semester_source": "level_heading" if current["semester"] is not None else "not_stated",
        "units": units,
        "course_title": title_case(current["title_as_written"]),
        "title_as_written": current["title_as_written"],
        "prerequisites": prerequisites,
        "prerequisites_text": prerequisites_text,
        "synopsis": " ".join(part for part in synopsis_parts if part).strip(),
        "heading_text": current["heading_line"],
        "section": section or None,
        "source_status": SOURCE_STATUS,
        "notes": notes,
    }


def parse_generic_lines(lines: list[str], meta: SourceMeta) -> list[dict[str, Any]]:
    courses: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_level: int | None = None
    current_semester: int | None = None
    section = ""

    def finalize() -> None:
        nonlocal current
        if current is None:
            return
        courses.append(finalize_generic_course(current, meta, section))
        current = None

    for line in lines:
        if STOP_LINE_RE.match(line):
            finalize()
            break
        level_match = LEVEL_RE.match(line)
        if level_match:
            finalize()
            current_level = int(level_match.group(1))
            rest = level_match.group("rest").upper()
            current_semester = 1 if "FIRST" in rest and "SECOND" not in rest else 2 if "SECOND" in rest else None
            section = line
            continue
        heading = match_course_heading(line)
        if heading is not None:
            finalize()
            current = {
                **heading,
                "level": current_level,
                "semester": current_semester,
                "synopsis_parts": [],
            }
            continue
        if current is not None:
            current["synopsis_parts"].append(line)
    finalize()
    return courses


def clean_field_value(value: str) -> str:
    return FIELD_VALUE_PREFIX_RE.sub("", value).strip()


def parse_structured_fields(lines: list[str], meta: SourceMeta) -> list[dict[str, Any]]:
    fields: dict[str, str] = {}
    synopsis_parts: list[str] = []
    in_synopsis = False
    pending_field: str | None = None

    for line in lines:
        if not in_synopsis:
            field_match = FIELD_RE.match(line)
            if field_match:
                pending_field = None
                key = re.sub(r"\s+", "_", field_match.group("key").upper())
                value = clean_field_value(field_match.group("value"))
                if key == "COURSE_SYNOPSIS":
                    in_synopsis = True
                    if value:
                        synopsis_parts.append(value)
                    continue
                if value:
                    fields[key] = value
                else:
                    fields[key] = ""
                    pending_field = key
                continue
            if pending_field:
                fields[pending_field] = clean_field_value(line)
                pending_field = None
                continue
            continue
        if STOP_LINE_RE.match(line) or "lecture note" in line.lower():
            break
        synopsis_parts.append(line)

    code_text = fields.get("COURSE_CODE", "")
    code_match = STRUCTURED_CODE_RE.match(code_text)
    if code_match is None:
        return []
    prefix = code_match.group("prefix").upper()
    number = code_match.group("number")
    units_raw = fields.get("NUMBER_OF_UNITS", "")
    units_match = STRUCTURED_UNITS_RE.match(units_raw)
    units, units_note = parse_units_token(units_match.group("units"), "") if units_match else (None, "Units value could not be parsed; verify source.")
    title_as_written = fields.get("COURSE_TITLE", "")
    level = level_from_number(number)
    notes = base_notes(meta)
    notes.append("Level derived from course number; individual course page has no level/semester heading.")
    notes.append("Semester not stated on page.")
    suspect = suspect_title_note(title_as_written)
    if suspect:
        notes.append(suspect)
    if units_note:
        notes.append(units_note)

    return [
        {
            "institution": INSTITUTION,
            "department": prefix,
            "department_acronym": prefix,
            "source_kind": meta.page_kind,
            "source_page_title": meta.page_title,
            "source_url": meta.url,
            "course_code": f"{prefix} {number}",
            "course_number": number,
            "level": level,
            "level_source": "course_code",
            "semester": None,
            "semester_source": "not_stated",
            "units": units,
            "course_title": title_case(title_as_written),
            "title_as_written": title_as_written,
            "prerequisites": None,
            "prerequisites_text": None,
            "synopsis": " ".join(part for part in synopsis_parts if part).strip(),
            "heading_text": code_text,
            "section": None,
            "source_status": SOURCE_STATUS,
            "notes": notes,
        }
    ]


def parse_page_html(html: str, meta: SourceMeta, fetched_at: str) -> dict[str, Any]:
    validate_public_url(meta.url)
    soup = BeautifulSoup(html, "html.parser")
    lines = content_lines(soup)
    if meta.parse_mode == "structured_fields":
        courses = parse_structured_fields(lines, meta)
    else:
        courses = parse_generic_lines(lines, meta)
    return {
        "source_url": meta.url,
        "final_url": meta.url,
        "fetched_at": fetched_at,
        "page_title": meta.page_title,
        "page_kind": meta.page_kind,
        "parse_mode": meta.parse_mode,
        "institution": INSTITUTION,
        "department": meta.department,
        "department_acronym": meta.department_acronym,
        "course_count": len(courses),
        "courses": courses,
    }


async def fetch_source(client: httpx.AsyncClient, source: dict[str, Any]) -> dict[str, Any]:
    url = source["url"]
    validate_public_url(url)
    response = await client.get(url)
    validate_public_url(str(response.url))
    response.raise_for_status()
    meta = source_meta(source["title"], source["page_kind"], source["parse_mode"] or "generic_lines", url)
    return parse_page_html(response.text, meta, datetime.now(UTC).isoformat())


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_row(course: dict[str, Any]) -> dict[str, Any]:
    return {
        "institution": course["institution"],
        "department": course["department"],
        "department_acronym": course.get("department_acronym") or "",
        "source_kind": course["source_kind"],
        "page_title": course["source_page_title"],
        "course_code": course["course_code"],
        "course_title": course["course_title"],
        "level": course["level"] if course["level"] is not None else "",
        "semester": course["semester"] if course["semester"] is not None else "",
        "units": course["units"] if course["units"] is not None else "",
        "prerequisites": course.get("prerequisites") or "",
        "source_url": course["source_url"],
        "source_status": course["source_status"],
        "source_notes": "; ".join(course["notes"]),
    }


def write_csv(courses: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for course in courses:
            writer.writerow(csv_row(course))


async def harvest_sources(
    sources: list[dict[str, Any]],
    *,
    output_dir: Path,
    csv_path: Path,
    report_path: Path,
    include_course_pages: bool,
    concurrency: int,
    delay: float,
    retries: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = [
        source
        for source in sources
        if source["page_kind"] == "department_synopsis"
        or (include_course_pages and source["page_kind"] == "course_synopsis_page")
    ]
    semaphore = asyncio.Semaphore(concurrency)
    all_courses: list[dict[str, Any]] = []
    report_sources: list[dict[str, Any]] = []

    async def harvest_one(client: httpx.AsyncClient, source: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            payload = None
            last_error: Exception | None = None
            for attempt in range(max(1, retries)):
                try:
                    payload = await fetch_source(client, source)
                    break
                except Exception as exc:  # transient public-site/network failures
                    last_error = exc
                    if attempt + 1 < max(1, retries):
                        await asyncio.sleep(0.5 * (attempt + 1))
            if payload is None:
                return {
                    "url": source["url"],
                    "title": source["title"],
                    "page_kind": source["page_kind"],
                    "status": "error",
                    "course_count": 0,
                    "error": f"{type(last_error).__name__}: {last_error}",
                    "output": None,
                    "courses": [],
                }
            slug = slug_for_url(source["url"])
            out_path = output_dir / f"{slug}.json"
            write_json(payload, out_path)
            await asyncio.sleep(delay)
            return {
                "url": source["url"],
                "title": source["title"],
                "page_kind": source["page_kind"],
                "status": "ok",
                "course_count": payload["course_count"],
                "warning": "no_courses_extracted" if payload["course_count"] == 0 else None,
                "error": None,
                "output": str(out_path),
                "courses": payload["courses"],
            }

    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        results = await asyncio.gather(*(harvest_one(client, source) for source in selected))

    for result in results:
        courses = result.pop("courses", [])
        all_courses.extend(courses)
        report_sources.append(result)

    write_csv(all_courses, csv_path)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "include_course_pages": include_course_pages,
        "selected_sources": len(selected),
        "total_courses": len(all_courses),
        "sources": report_sources,
    }
    write_json(report, report_path)
    return report


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(sources: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def run_discover(manifest_path: Path) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        sources = await discover_sources(client)
    write_manifest(sources, manifest_path)
    return sources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["discover", "harvest", "discover-harvest"])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--include-course-pages", action="store_true")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    if args.command in {"discover", "discover-harvest"}:
        sources = asyncio.run(run_discover(args.manifest))
        counts = {}
        for source in sources:
            counts[source["page_kind"]] = counts.get(source["page_kind"], 0) + 1
        print(f"Discovered {len(sources)} synopsis pages: {counts} -> {args.manifest}")
    else:
        sources = load_manifest(args.manifest)

    if args.command in {"harvest", "discover-harvest"}:
        report = asyncio.run(
            harvest_sources(
                sources,
                output_dir=args.output_dir,
                csv_path=args.csv,
                report_path=args.report,
                include_course_pages=args.include_course_pages,
                concurrency=args.concurrency,
                delay=args.delay,
                retries=args.retries,
            )
        )
        print(
            f"Harvested {report['selected_sources']} sources / {report['total_courses']} courses "
            f"-> {args.output_dir}, {args.csv}, {args.report}"
        )


if __name__ == "__main__":
    main()
