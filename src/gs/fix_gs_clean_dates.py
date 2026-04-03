#!/usr/bin/env python3
"""Normalize fuzzy GS date literals in clean.ttl to xsd:gYear.

The script rewrites date literals for these predicates:
- schema:birthDate  (treated as lower bound)
- schema:deathDate  (treated as upper bound)
- part:startDate    (treated as lower bound)
- part:endDate      (treated as upper bound)

Rule style: intentionally conservative toward wider intervals.
When a value is ambiguous, lower-bound fields choose the earliest plausible year,
upper-bound fields choose the latest plausible year.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

DATE_FIELD_BOUNDARY = {
    "schema:birthDate": "start",
    "schema:deathDate": "end",
    "part:startDate": "start",
    "part:endDate": "end",
}

FIELD_RE = re.compile(r"\b(schema:birthDate|schema:deathDate|part:startDate|part:endDate)\b")
LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"(?:@[A-Za-z0-9-]+|\^\^[^\s;,.]+)?')

YEAR_RE = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")
YEAR_RANGE_RE = re.compile(r"(?<!\d)(\d{3,4})\s*/\s*(\d{3,4})(?!\d)")
YEAR_RANGE_SHORT_RE = re.compile(r"(?<!\d)(\d{1,4})\s*/\s*(\d{1,4})(?!\d)")
AROUND_RE = re.compile(r"\b(?:um|ca\.?|circa)\s*(\d{3,4})\b")
BEFORE_RE = re.compile(r"\bvor\s*(\d{3,4})\b")
AFTER_RE = re.compile(r"\bnach\s*(\d{3,4})\b")
EXACT_NUMERIC_RE = re.compile(r"^\d{1,4}$")
ERA_RE = re.compile(r"(?:\b(um|ca\.?|circa)\s*)?(\d{1,4})\s*([vn])\.?\s*chr\.?")
CENTURY_TOKEN = r"(?:jh\.?s?\.?|jahrhunder[tz](?:s)?)"
CENTURY_RE = re.compile(rf"(\d{{1,2}})\.?\s*{CENTURY_TOKEN}")
CENTURY_RANGE_RE = re.compile(
    rf"zwischen\s+(?:anfang|mitte|ende)?(?:\s+des)?\s*(\d{{1,2}})\.?\s*(?:und|bis|-)\s*"
    rf"(?:anfang|mitte|ende)?(?:\s+des)?\s*(\d{{1,2}})\.?\s*{CENTURY_TOKEN}"
)
CENTURY_SLASH_RE = re.compile(rf"(\d{{1,2}})\.?\s*/\s*(\d{{1,2}})\.?\s*{CENTURY_TOKEN}")


def _normalize_text(value: str) -> str:
    text = value.lower().strip()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return text


def _collect_year_candidates(value: str) -> list[int]:
    text = _normalize_text(value)
    candidates: list[int] = []
    contains_chr = "chr" in text

    for match in ERA_RE.finditer(text):
        approx = match.group(1) is not None
        year = int(match.group(2))
        era = match.group(3)
        base = -year if era == "v" else year
        if approx:
            candidates.extend([base - 10, base + 10])
        else:
            candidates.append(base)

    if not contains_chr:
        for match in YEAR_RANGE_RE.finditer(text):
            candidates.append(int(match.group(1)))
            candidates.append(int(match.group(2)))

        for match in YEAR_RANGE_SHORT_RE.finditer(text):
            candidates.append(int(match.group(1)))
            candidates.append(int(match.group(2)))

        for match in AROUND_RE.finditer(text):
            year = int(match.group(1))
            candidates.extend([year - 10, year + 10])

        for match in BEFORE_RE.finditer(text):
            year = int(match.group(1))
            candidates.extend([year - 100, year])

        for match in AFTER_RE.finditer(text):
            year = int(match.group(1))
            candidates.extend([year, year + 100])

    for match in CENTURY_RANGE_RE.finditer(text):
        start_century = int(match.group(1))
        end_century = int(match.group(2))
        low = (min(start_century, end_century) - 1) * 100
        high = (max(start_century, end_century) + 1) * 100
        candidates.extend([low, high])

    for match in CENTURY_SLASH_RE.finditer(text):
        start_century = int(match.group(1))
        end_century = int(match.group(2))
        low = (min(start_century, end_century) - 1) * 100
        high = (max(start_century, end_century) + 1) * 100
        candidates.extend([low, high])

    for match in CENTURY_RE.finditer(text):
        century = int(match.group(1))
        candidates.extend([(century - 1) * 100, (century + 1) * 100])

    if not contains_chr:
        if EXACT_NUMERIC_RE.fullmatch(text):
            candidates.append(int(text))

        for match in YEAR_RE.finditer(text):
            candidates.append(int(match.group(1)))

    # Remove impossible values and duplicates while preserving order.
    unique: list[int] = []
    seen = set()
    for year in candidates:
        if year < -2999:
            continue
        if year > 2999:
            continue
        if year not in seen:
            seen.add(year)
            unique.append(year)
    return unique


def _choose_year(value: str, boundary: str) -> int | None:
    candidates = _collect_year_candidates(value)
    if not candidates:
        return None
    return min(candidates) if boundary == "start" else max(candidates)


def _format_gyear(year: int) -> str:
    if year < 0:
        return f"-{abs(year):04d}"
    return f"{year:04d}"


def normalize_line(line: str) -> tuple[str, bool, bool]:
    field_match = FIELD_RE.search(line)
    if not field_match:
        return line, False, False

    field = field_match.group(1)
    boundary = DATE_FIELD_BOUNDARY[field]

    literal_match = LITERAL_RE.search(line, field_match.end())
    if not literal_match:
        return line, True, False

    literal_value = literal_match.group(1)
    year = _choose_year(literal_value, boundary)
    if year is None:
        return line, True, False

    replacement = f'"{_format_gyear(year)}"^^xsd:gYear'
    new_line = line[: literal_match.start()] + replacement + line[literal_match.end() :]
    changed = new_line != line
    return new_line, True, changed


def process_file(input_path: Path, output_path: Path) -> tuple[int, int, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_lines = 0
    date_lines = 0
    changed_lines = 0

    with input_path.open("r", encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            total_lines += 1
            new_line, is_date_line, changed = normalize_line(line)
            if is_date_line:
                date_lines += 1
            if changed:
                changed_lines += 1
            dst.write(new_line)

    return total_lines, date_lines, changed_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize fuzzy GS dates to xsd:gYear")
    parser.add_argument(
        "--input",
        default="data/raw/gs/clean.ttl",
        help="Input Turtle file (default: data/raw/gs/clean.ttl)",
    )
    parser.add_argument(
        "--output",
        default="data/raw/gs/clean.ttl",
        help="Output Turtle file (default: overwrite input)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if input_path.resolve() == output_path.resolve():
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        total_lines, date_lines, changed_lines = process_file(input_path, temp_path)
        if changed_lines == 0:
            temp_path.unlink(missing_ok=True)
            print(f"Processed {total_lines} lines")
            print(f"Date lines seen: {date_lines}")
            print(f"Date lines changed: {changed_lines}")
            print(f"No changes needed: {output_path} is already normalized")
        else:
            temp_path.replace(output_path)
            print(f"Processed {total_lines} lines")
            print(f"Date lines seen: {date_lines}")
            print(f"Date lines changed: {changed_lines}")
            print(f"Overwrote: {output_path}")
    else:
        total_lines, date_lines, changed_lines = process_file(input_path, output_path)
        print(f"Processed {total_lines} lines")
        print(f"Date lines seen: {date_lines}")
        print(f"Date lines changed: {changed_lines}")
        print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
