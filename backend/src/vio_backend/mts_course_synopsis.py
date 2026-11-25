"""Scrape the public FUNAAB MTS course synopsis page into reviewable records.

This command only reads the approved public HTTPS page, never accesses
login-protected services, and never writes to Neon. Its JSON output preserves
the source synopsis text for review; the derived CSV is a candidate list, not a
production catalogue import.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

from vio_backend.catalogue_harvest import validate_public_url

SYNOPSIS_URL = "https://funaab.edu.ng/mts-course-synopsis/"
INSTITUTION = "FUNAAB"
DEPARTMENT = "Mathematics"
DEPARTMENT_ACRONYM = "MTS"
SOURCE_STATUS = "official_public_date_unknown"
USER_AGENT = "VIO-public-catalogue-research/0.1"

COURSE_HEADING_RE = re.compile(r"^\s*MTS\s*(\d{3})\b(?P<rest>.*)$", re.IGNORECASE)
UNITS_RE = re.compile(r"\(\s*(\d+)\s*(?:UNITS?|UNTIS)\s*\)", re.IGNORECASE)
STOP_SECTION_RE = re.compile(
    r"^\s*(?:\(\s*5\s*\)\s*ON-GOING|\(\s*12\s*\)\s*UNIVERSITY COURSE LEVEL|Course Listing)\b",
    re.IGNORECASE,
)
LISTING_HEADING_RE = re.compile(r"^\s*(\d{3})\s*Level\s*[–-]\s*(First|Second)\s*Semester\s*$", re.IGNORECASE)
LISTING_COURSE_RE = re.compile(r"^\s*MTS\s*(\d{3})\*?\s*(?P<title>.+?)\s*$", re.IGNORECASE)
PRQT_PREFIX_RE = re.compile(r"^\s*PRQT\s*[,;]?\s*", re.IGNORECASE)

MINOR_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
ROMAN_NUMERALS = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
SEMESTER_NAMES = {1: "First", 2: "Second"}
SUSPECT_TITLE_TOKENS = ("CACULUS", "LESBEGUE", "FLUID DYNAMIC")

CSV_FIELDS = [
    "institution",
    "department",
    "course_code",
    "course_title",
    "level",
    "semester",
    "units",
    "source_url",
    "source_status",
    "source_notes",
]


@dataclass(frozen=True)
class PageBlock:
    lines: tuple[str, ...]
    text: str


def _clean_lines(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def page_blocks(soup: BeautifulSoup) -> list[PageBlock]:
    content = soup.select_one(".page-content") or soup.find("main", id="content") or soup.body or soup
    for br in content.find_all("br"):
        br.replace_with("\n")

    blocks: list[PageBlock] = []
    for child in content.children:
        if isinstance(child, NavigableString):
            lines = _clean_lines(str(child))
        elif isinstance(child, Tag):
            lines = _clean_lines(child.get_text("\n", strip=True))
        else:
            continue
        if lines:
            blocks.append(PageBlock(lines=lines, text=" ".join(lines)))
    return blocks


def title_case(text: str) -> str:
    words = text.split()
    if not words:
        return ""
    rendered: list[str] = []
    for index, word in enumerate(words):
        core = word.strip(".,;:()")
        if core.upper() in ROMAN_NUMERALS:
            rendered.append(core.upper())
        elif 0 < index < len(words) - 1 and core.lower() in MINOR_WORDS:
            rendered.append(core.lower())
        else:
            rendered.append(core.capitalize())
    return " ".join(rendered)


def is_course_heading(text: str) -> bool:
    return COURSE_HEADING_RE.match(text) is not None and UNITS_RE.search(text) is not None


def parse_course_heading(text: str) -> dict[str, Any] | None:
    match = COURSE_HEADING_RE.match(text)
    if match is None:
        return None
    rest = re.sub(r"^[\s:;]+", "", match.group("rest"))
    units_match = UNITS_RE.search(rest)
    if units_match is None:
        return None

    number = match.group(1)
    before_units = rest[: units_match.start()].strip()
    after_units = rest[units_match.end() :].strip()
    prerequisites_text = after_units or None
    prerequisites = PRQT_PREFIX_RE.sub("", after_units).strip() or None

    return {
        "course_code": f"{DEPARTMENT_ACRONYM} {number}",
        "course_number": number,
        "level": int(number[0]) * 100,
        "title_as_written": before_units,
        "course_title": title_case(before_units),
        "units": int(units_match.group(1)),
        "prerequisites": prerequisites,
        "prerequisites_text": prerequisites_text,
        "heading_text": text,
    }


def course_section_end(blocks: list[PageBlock]) -> int:
    for index, block in enumerate(blocks):
        if STOP_SECTION_RE.match(block.text):
            return index
    return len(blocks)


def parse_course_entries(blocks: list[PageBlock]) -> list[dict[str, Any]]:
    end = course_section_end(blocks)
    entries: list[dict[str, Any]] = []
    index = 0
    while index < end:
        block = blocks[index]
        if not is_course_heading(block.text):
            index += 1
            continue

        heading = parse_course_heading(block.text)
        if heading is None:
            index += 1
            continue

        synopsis = ""
        lookahead = index + 1
        while lookahead < end and not blocks[lookahead].text:
            lookahead += 1
        next_is_heading = lookahead < end and is_course_heading(blocks[lookahead].text)
        if lookahead < end and not next_is_heading:
            synopsis = blocks[lookahead].text

        entries.append({**heading, "synopsis": synopsis})
        if next_is_heading:
            index = lookahead
        else:
            index = lookahead + 1 if lookahead < end else end
    return entries


def parse_course_listing(blocks: list[PageBlock]) -> dict[str, dict[str, Any]]:
    listing_start = next(
        (index for index, block in enumerate(blocks) if block.text.strip().lower() == "course listing"),
        None,
    )
    if listing_start is None:
        return {}

    listing: dict[str, dict[str, Any]] = {}
    current_level: int | None = None
    current_semester: int | None = None
    current_section = ""

    for block in blocks[listing_start + 1 :]:
        heading_match = LISTING_HEADING_RE.match(block.text)
        if heading_match:
            current_level = int(heading_match.group(1))
            current_semester = 1 if heading_match.group(2).lower() == "first" else 2
            current_section = block.text
            continue

        if current_level is None or current_semester is None:
            continue

        for line in block.lines:
            course_match = LISTING_COURSE_RE.match(line)
            if course_match is None:
                continue
            number = course_match.group(1)
            code = f"{DEPARTMENT_ACRONYM} {number}"
            listing.setdefault(
                code,
                {
                    "semester": current_semester,
                    "level": current_level,
                    "section": current_section,
                    "title": title_case(course_match.group("title")),
                    "title_as_written": course_match.group("title").strip(),
                },
            )
    return listing


def _prerequisite_note(prerequisites: str | None) -> str | None:
    if not prerequisites:
        return None
    upper = prerequisites.upper()
    if upper.startswith("OR ") or re.match(r"^\d{3}\b", prerequisites):
        return "Prerequisite text may be malformed; verify against source."
    return None


def merge_listing(entries: list[dict[str, Any]], listing: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for entry in entries:
        record = dict(entry)
        course_listing = listing.get(record["course_code"])
        notes: list[str] = [
            "Official FUNAAB MTS Course Synopsis page; page version date unknown; verify currentness."
        ]

        if course_listing is not None:
            record["semester"] = course_listing["semester"]
            record["semester_source"] = "course_listing"
            record["listing_title"] = course_listing["title"]
            record["listing_title_as_written"] = course_listing["title_as_written"]
            record["listing_section"] = course_listing["section"]
            notes.append(
                f"Semester from page Course Listing: {course_listing['level']} Level – "
                f"{SEMESTER_NAMES[course_listing['semester']]} Semester."
            )
            if course_listing["title"] != record["course_title"]:
                notes.append(f"Course listing title differs: \"{course_listing['title_as_written']}\".")
        else:
            record["semester"] = None
            record["semester_source"] = "not_stated"
            record["listing_title"] = None
            record["listing_title_as_written"] = None
            record["listing_section"] = None
            notes.append("Semester not stated in page Course Listing section.")

        malformed = _prerequisite_note(record.get("prerequisites"))
        if malformed:
            notes.append(malformed)
        if any(token in record["title_as_written"].upper() for token in SUSPECT_TITLE_TOKENS):
            notes.append("Source title spelling may be nonstandard; verify canonical title.")

        record["notes"] = notes
        record["institution"] = INSTITUTION
        record["department"] = DEPARTMENT
        record["department_acronym"] = DEPARTMENT_ACRONYM
        record["source_status"] = SOURCE_STATUS
        merged.append(record)
    return merged


def parse_synopsis_html(html: str, *, source_url: str, fetched_at: str) -> dict[str, Any]:
    validate_public_url(source_url)
    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    blocks = page_blocks(soup)
    entries = parse_course_entries(blocks)
    listing = parse_course_listing(blocks)
    courses = merge_listing(entries, listing)
    return {
        "source_url": source_url,
        "fetched_at": fetched_at,
        "page_title": page_title,
        "institution": INSTITUTION,
        "department": DEPARTMENT,
        "department_acronym": DEPARTMENT_ACRONYM,
        "course_count": len(courses),
        "courses": courses,
    }


async def fetch_synopsis(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    validate_public_url(url)
    response = await client.get(url)
    validate_public_url(str(response.url))
    response.raise_for_status()
    return parse_synopsis_html(
        response.text,
        source_url=url,
        fetched_at=datetime.now(UTC).isoformat(),
    )


async def harvest_synopsis(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        return await fetch_synopsis(client, url)


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_row(course: dict[str, Any], source_url: str) -> dict[str, Any]:
    return {
        "institution": course["institution"],
        "department": course["department"],
        "course_code": course["course_code"],
        "course_title": course["course_title"],
        "level": course["level"],
        "semester": course["semester"] if course["semester"] is not None else "",
        "units": course["units"] if course["units"] is not None else "",
        "source_url": source_url,
        "source_status": course["source_status"],
        "source_notes": "; ".join(course["notes"]),
    }


def write_csv(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for course in payload["courses"]:
            writer.writerow(csv_row(course, payload["source_url"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default=SYNOPSIS_URL)
    parser.add_argument("--output-json", type=Path, default=Path("docs/data/mts_course_synopsis.json"))
    parser.add_argument("--output-csv", type=Path, default=Path("docs/data/course_catalogue_candidates.csv"))
    args = parser.parse_args()

    payload = asyncio.run(harvest_synopsis(args.url))
    write_json(payload, args.output_json)
    write_csv(payload, args.output_csv)
    print(
        f"Saved {payload['course_count']} MTS course synopsis records: "
        f"{args.output_json} and {args.output_csv}"
    )


if __name__ == "__main__":
    main()
