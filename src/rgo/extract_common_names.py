#!/usr/bin/env python3
"""Count frequent first-name tokens in an RGO Turtle file.

Default behaviour:
- count preferred-name first tokens from gndo:preferredNameForThePerson
- also count first two tokens
- print raw and normalized frequency tables

Optional:
- include variant names as additional evidence
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

GNDO = Namespace("https://d-nb.info/standards/elementset/gnd#")

PUNCT_RE = re.compile(r"^[\s\.,;:!\?\(\)\[\]\{\}'\"“”‘’\-]+|[\s\.,;:!\?\(\)\[\]\{\}'\"“”‘’\-]+$")
INNER_WS_RE = re.compile(r"\s+")


def clean_text(value: object) -> str:
    text = str(value).strip()
    text = INNER_WS_RE.sub(" ", text)
    return text


def normalize_token(token: str) -> str:
    token = clean_text(token).lower()
    token = PUNCT_RE.sub("", token)
    return token


def tokenize_name(name: str) -> list[str]:
    """
    Conservative tokenization for person names.

    Examples:
    - 'Fridericus' -> ['Fridericus']
    - 'Johannes Baptista' -> ['Johannes', 'Baptista']
    - 'Hunt Hund [de Arnsberg]' -> ['Hunt', 'Hund', 'de', 'Arnsberg']
    """
    name = clean_text(name)
    if not name:
        return []

    # Replace bracket-like punctuation with spaces so tokens stay visible
    name = re.sub(r"[\[\]\(\)\{\},;:]+", " ", name)
    name = INNER_WS_RE.sub(" ", name).strip()

    tokens = [t for t in name.split(" ") if t]
    return tokens


def iter_rgo_persons(graph: Graph) -> list[URIRef]:
    """
    Iterate RGO persons via rdf:type gndo:DifferentiatedPerson.
    Fallback: also accept subjects that have a preferred person name.
    """
    persons = set(graph.subjects(RDF.type, GNDO.DifferentiatedPerson))
    persons.update(graph.subjects(GNDO.preferredNameForThePerson, None))
    return [p for p in persons if isinstance(p, URIRef)]


def iter_name_values(
    graph: Graph,
    include_variants: bool = False,
) -> Iterable[str]:
    for person in iter_rgo_persons(graph):
        for obj in graph.objects(person, GNDO.preferredNameForThePerson):
            name = clean_text(obj)
            if name:
                yield name

        if include_variants:
            for obj in graph.objects(person, GNDO.variantNameForThePerson):
                name = clean_text(obj)
                if name:
                    yield name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/raw/rgo/example.ttl",
        help="Path to RGO Turtle file",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="How many rows to print per frequency table",
    )
    parser.add_argument(
        "--include-variants",
        action="store_true",
        help="Also count gndo:variantNameForThePerson values",
    )
    args = parser.parse_args()

    graph = Graph()
    graph.parse(args.input, format="turtle")

    first_token_raw = Counter()
    first_two_tokens_raw = Counter()
    first_token_norm = Counter()
    first_two_tokens_norm = Counter()

    total_names = 0

    for name in iter_name_values(graph, include_variants=args.include_variants):
        tokens = tokenize_name(name)
        if not tokens:
            continue

        total_names += 1

        # raw counters
        first_token_raw[tokens[0]] += 1
        if len(tokens) >= 2:
            first_two_tokens_raw[" ".join(tokens[:2])] += 1

        # normalized counters
        norm_tokens = [normalize_token(t) for t in tokens]
        norm_tokens = [t for t in norm_tokens if t]
        if not norm_tokens:
            continue

        first_token_norm[norm_tokens[0]] += 1
        if len(norm_tokens) >= 2:
            first_two_tokens_norm[" ".join(norm_tokens[:2])] += 1

    print(f"Input file: {Path(args.input)}")
    print(f"Names counted: {total_names}")
    print(f"Include variants: {args.include_variants}")
    print()

    print("Top raw first tokens:")
    for token, count in first_token_raw.most_common(args.top):
        print(f"{count:>5}  {token}")

    print("\nTop normalized first tokens:")
    for token, count in first_token_norm.most_common(args.top):
        print(f"{count:>5}  {token}")

    print("\nTop raw first two tokens:")
    for token, count in first_two_tokens_raw.most_common(args.top):
        print(f"{count:>5}  {token}")

    print("\nTop normalized first two tokens:")
    for token, count in first_two_tokens_norm.most_common(args.top):
        print(f"{count:>5}  {token}")


if __name__ == "__main__":
    main()