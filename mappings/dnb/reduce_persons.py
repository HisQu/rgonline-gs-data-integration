#!/usr/bin/env python3
"""Extract a DNB person cohort from a large Turtle dump.

Input:  data/raw/dnb/full.ttl
Output: data/raw/dnb/example.ttl

Selection rule:
- include a person if birth year is in [1361, 1447], which is the start year of the RG5 minus 70 years and RG5 end year
- if birth year is missing, include if death year is in [1431, 1497], which is the start year of the RG5 and the end year plus 50 years
- for fuzzy values, use the first 4-digit year in the lexical form

The extractor keeps full top-level blocks for selected person URIs and their
`/about` resources plus recursively referenced blank-node blocks so that person
name entities and list nodes remain intact.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

BIRTH_START = 1361
BIRTH_END = 1447
DEATH_FALLBACK_START = 1431
DEATH_FALLBACK_END = 1497

SUBJECT_RE = re.compile(r"^\s*(<[^>]+>|_:[A-Za-z][A-Za-z0-9._-]*)\s+")
BLANK_RE = re.compile(r"_:[A-Za-z][A-Za-z0-9._-]*")
YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
PERSON_URI_RE = re.compile(r"^https?://d-nb\.info/gnd/[0-9A-Za-z-]+$")

BIRTH_PREDICATES = (
    "gndo:dateOfBirth",
    "<https://d-nb.info/standards/elementset/gnd#dateOfBirth>",
)

DEATH_PREDICATES = (
    "gndo:dateOfDeath",
    "<https://d-nb.info/standards/elementset/gnd#dateOfDeath>",
)


def iter_blocks(path: Path):
    """Yield (header_lines, block_text) where header_lines is only set once."""
    header: list[str] = []
    block: list[str] = []
    seen_data = False

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not seen_data:
                if SUBJECT_RE.match(line):
                    seen_data = True
                    block = [line]
                else:
                    header.append(line)
                continue

            if line.strip() == "":
                if block:
                    yield None, "".join(block)
                    block = []
                continue

            block.append(line)

    if block:
        yield None, "".join(block)

    yield header, ""


def subject_of_block(block: str) -> str | None:
    for line in block.splitlines():
        m = SUBJECT_RE.match(line)
        if m:
            term = m.group(1)
            if term.startswith("<") and term.endswith(">"):
                return term[1:-1]
            return term
    return None


def blank_objects_of_block(block: str) -> set[str]:
    subject = subject_of_block(block)
    nodes = set(BLANK_RE.findall(block))
    if subject and subject.startswith("_:"):
        nodes.discard(subject)
    return nodes


def is_person_block(block: str) -> bool:
    return (
        " a gndo:DifferentiatedPerson" in block
        or " a <https://d-nb.info/standards/elementset/gnd#DifferentiatedPerson>" in block
    )


def first_year_for_predicates(block: str, predicates: tuple[str, ...]) -> int | None:
    for pred in predicates:
        # Capture the predicate object up to the next statement separator.
        # This supports wrapped Turtle lines where the literal is not on the
        # same line as the predicate token.
        pattern = re.compile(re.escape(pred) + r"\s+([^.;]+)", re.DOTALL)
        for match_obj in pattern.finditer(block):
            value_fragment = match_obj.group(1)
            year_match = YEAR_RE.search(value_fragment)
            if year_match:
                return int(year_match.group(1))
    return None


def collect_cohort_persons(input_path: Path) -> set[str]:
    selected: set[str] = set()
    person_flags: dict[str, bool] = {}
    birth_years: dict[str, int] = {}
    death_years: dict[str, int] = {}

    for hdr, block in iter_blocks(input_path):
        if hdr is not None:
            continue

        subject = subject_of_block(block)
        if not subject or not PERSON_URI_RE.match(subject):
            continue

        birth_year = first_year_for_predicates(block, BIRTH_PREDICATES)
        death_year = first_year_for_predicates(block, DEATH_PREDICATES)

        if is_person_block(block):
            person_flags[subject] = True

        if birth_year is not None and subject not in birth_years:
            birth_years[subject] = birth_year

        if death_year is not None and subject not in death_years:
            death_years[subject] = death_year

    for subject in person_flags:
        birth_year = birth_years.get(subject)
        death_year = death_years.get(subject)

        if birth_year is not None:
            if BIRTH_START <= birth_year <= BIRTH_END:
                selected.add(subject)
            continue

        if death_year is not None and DEATH_FALLBACK_START <= death_year <= DEATH_FALLBACK_END:
            selected.add(subject)

    return selected


def reduce_dnb(input_path: Path, output_path: Path) -> tuple[int, int, int]:
    persons = collect_cohort_persons(input_path)
    abouts = {f"{uri}/about" for uri in persons}

    include_subjects: set[str] = set(persons) | set(abouts)
    included_blocks: list[str] = []
    included_seen: set[str] = set()

    header_lines: list[str] | None = None

    # Fixed-point passes: discover blank nodes referenced from already included blocks.
    while True:
        before = len(include_subjects)

        for hdr, block in iter_blocks(input_path):
            if hdr is not None:
                header_lines = hdr
                continue

            subject = subject_of_block(block)
            if not subject or subject not in include_subjects:
                continue

            block_key = f"{subject}\n{block}"
            if block_key not in included_seen:
                included_blocks.append(block)
                included_seen.add(block_key)

            include_subjects.update(blank_objects_of_block(block))

        if len(include_subjects) == before:
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out:
        if header_lines:
            out.writelines(header_lines)
            if header_lines and header_lines[-1].strip() != "":
                out.write("\n")
        for block in included_blocks:
            out.write(block)
            out.write("\n")

    return len(persons), len(included_blocks), len(include_subjects)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/dnb/persons_full.ttl")
    parser.add_argument("--output", default="data/raw/dnb/persons_example.ttl")
    args = parser.parse_args()

    persons, blocks, subjects = reduce_dnb(Path(args.input), Path(args.output))
    print(f"Persons selected: {persons}")
    print(f"Blocks written: {blocks}")
    print(f"Subjects retained: {subjects}")
    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()
