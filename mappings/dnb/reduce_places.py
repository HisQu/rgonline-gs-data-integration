from __future__ import annotations
from rdflib import Graph, Namespace
import argparse
import re
from pathlib import Path

SUBJECT_RE = re.compile(r"^\s*(<[^>]+>|_:[A-Za-z][A-Za-z0-9._-]*)\s+")
BLANK_RE = re.compile(r"_:[A-Za-z][A-Za-z0-9._-]*")
DNB_URI_RE = re.compile(r"<(https?://d-nb\.info/gnd/[0-9A-Za-z-]+)>")

GNDO = Namespace("https://d-nb.info/standards/elementset/gnd#")

PLACE_PREDICATES = (
    "gndo:placeOfActivity",
    "<https://d-nb.info/standards/elementset/gnd#placeOfActivity>",
    "gndo:placeOfDeath",
    "<https://d-nb.info/standards/elementset/gnd#placeOfDeath>",
    "gndo:placeOfBirth",
    "<https://d-nb.info/standards/elementset/gnd#placeOfBirth>",
)

PLACE_URI_RE = re.compile(r"^https?://d-nb\.info/gnd/[0-9A-Za-z-]+$")


def iter_blocks(path: Path):
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



def collect_referenced_place_uris(persons_subset_path: Path) -> set[str]:
    graph = Graph()
    graph.parse(str(persons_subset_path), format="turtle")

    place_uris: set[str] = set()

    for predicate in (
        GNDO.placeOfActivity,
        GNDO.placeOfDeath,
        GNDO.placeOfBirth,
    ):
        for _, _, obj in graph.triples((None, predicate, None)):
            text = str(obj).strip()
            if PLACE_URI_RE.match(text):
                place_uris.add(text)

    return place_uris


def reduce_places(
    persons_subset_path: Path,
    places_input_path: Path,
    output_path: Path,
) -> tuple[int, int, int]:
    place_uris = collect_referenced_place_uris(persons_subset_path)
    abouts = {f"{uri}/about" for uri in place_uris}

    include_subjects: set[str] = set(place_uris) | set(abouts)
    included_blocks: list[str] = []
    included_seen: set[str] = set()

    header_lines: list[str] | None = None

    while True:
        before = len(include_subjects)

        for hdr, block in iter_blocks(places_input_path):
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

    return len(place_uris), len(included_blocks), len(include_subjects)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persons", default="data/raw/dnb/persons_example.ttl")
    parser.add_argument("--places-input", default="data/raw/dnb/places_full.ttl")
    parser.add_argument("--output", default="data/raw/dnb/places_example.ttl")
    args = parser.parse_args()

    place_uris, blocks, subjects = reduce_places(
        Path(args.persons),
        Path(args.places_input),
        Path(args.output),
    )
    print(f"Referenced place URIs: {place_uris}")
    print(f"Blocks written: {blocks}")
    print(f"Subjects retained: {subjects}")
    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()