#!/usr/bin/env python3
"""Extract four example DNB persons from a large Turtle dump.

Input:  data/raw/dnb/full.ttl
Output: data/raw/dnb/example.ttl

The extractor keeps full top-level blocks for the target person URIs and their
`/about` resources plus recursively referenced blank-node blocks so that person
name entities and list nodes remain intact.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

TARGET_GND_IDS = (
    "136175414",   # Gerhard Hoya
    "118525530",   # Dietrich II. Moers
    "10427526X",   # Heinrich Bodo
    "137509782",   # Friedrich Arnsberg
)

SUBJECT_RE = re.compile(r"^\s*(<[^>]+>|_:[A-Za-z][A-Za-z0-9._-]*)\s+")
BLANK_RE = re.compile(r"_:[A-Za-z][A-Za-z0-9._-]*")


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


def reduce_dnb(input_path: Path, output_path: Path) -> tuple[int, int, int]:
    persons = {f"https://d-nb.info/gnd/{gid}" for gid in TARGET_GND_IDS}
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
    parser.add_argument("--input", default="data/raw/dnb/full.ttl")
    parser.add_argument("--output", default="data/raw/dnb/example_min.ttl")
    args = parser.parse_args()

    persons, blocks, subjects = reduce_dnb(Path(args.input), Path(args.output))
    print(f"Persons selected: {persons}")
    print(f"Blocks written: {blocks}")
    print(f"Subjects retained: {subjects}")
    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()
