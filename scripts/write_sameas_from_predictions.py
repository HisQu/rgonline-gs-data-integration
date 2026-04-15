#!/usr/bin/env python3
"""Write owl:sameAs links from matching predictions into cohort Turtle files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rdflib import Graph, URIRef
from rdflib.namespace import OWL

SOURCE_TO_DEFAULT_FILE = {
    "dnb": Path("data/raw/dnb/statments.ttl"),
    "gs": Path("data/raw/gs/statements.ttl"),
    "rgo": Path("data/raw/rgo/statements.ttl"),
}


@dataclass
class WriteStats:
    total_rows: int = 0
    directed_assertions_seen: int = 0
    directed_assertions_existing: int = 0
    directed_assertions_added: int = 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions-csv",
        type=Path,
        default=Path("data/matching_outputs/predictions_pairs.csv"),
        help="Path to predictions_pairs.csv produced by matching.main_match.",
    )
    parser.add_argument(
        "--dnb-file",
        type=Path,
        default=SOURCE_TO_DEFAULT_FILE["dnb"],
        help="Path to DNB cohort Turtle file.",
    )
    parser.add_argument(
        "--gs-file",
        type=Path,
        default=SOURCE_TO_DEFAULT_FILE["gs"],
        help="Path to GS cohort Turtle file.",
    )
    parser.add_argument(
        "--rgo-file",
        type=Path,
        default=SOURCE_TO_DEFAULT_FILE["rgo"],
        help="Path to RGO cohort Turtle file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and report additions without writing cohort files.",
    )
    return parser.parse_args()


def _load_graph(path: Path) -> Graph:
    graph = Graph()
    graph.parse(path, format="turtle")
    graph.bind("owl", OWL, replace=False)
    return graph


def _append_sameas_triples(
    output_path: Path,
    pending_triples: set[tuple[str, str]],
) -> None:
    if not pending_triples:
        return

    lines = [
        f"<{subject}> <{str(OWL.sameAs)}> <{obj}> ."
        for subject, obj in sorted(pending_triples)
    ]

    prepend_newline = False
    if output_path.stat().st_size > 0:
        with output_path.open("rb") as fh:
            fh.seek(-1, 2)
            prepend_newline = fh.read(1) != b"\n"

    with output_path.open("a", encoding="utf-8") as fh:
        if prepend_newline:
            fh.write("\n")
        fh.write("\n".join(lines))
        fh.write("\n")


def _add_directed_sameas(
    graph: Graph,
    pending_triples: set[tuple[str, str]],
    subject_uri: str,
    object_uri: str,
    stats: WriteStats,
) -> None:
    triple_key = (subject_uri, object_uri)
    stats.directed_assertions_seen += 1

    if triple_key in pending_triples:
        stats.directed_assertions_existing += 1
        return

    triple = (URIRef(subject_uri), OWL.sameAs, URIRef(object_uri))
    if triple in graph:
        stats.directed_assertions_existing += 1
        return

    pending_triples.add(triple_key)
    stats.directed_assertions_added += 1


def main() -> None:
    args = _parse_args()

    predictions_path = args.predictions_csv
    source_to_file = {
        "dnb": args.dnb_file,
        "gs": args.gs_file,
        "rgo": args.rgo_file,
    }

    for file_path in source_to_file.values():
        if not file_path.exists():
            raise FileNotFoundError(f"Input cohort file does not exist: {file_path}")

    df = pd.read_csv(predictions_path)

    required_columns = [
        "source_dataset_l",
        "source_dataset_r",
        "entity_id_l",
        "entity_id_r",
    ]
    missing_columns = [c for c in required_columns if c not in df.columns]
    if missing_columns:
        raise ValueError(
            "Missing required columns in predictions CSV: " + ", ".join(missing_columns)
        )

    graphs = {source: _load_graph(path) for source, path in source_to_file.items()}
    stats_by_source = {source: WriteStats() for source in source_to_file}
    pending_by_source: dict[str, set[tuple[str, str]]] = {
        source: set() for source in source_to_file
    }

    for row in df.itertuples(index=False):
        left_source = str(row.source_dataset_l)
        right_source = str(row.source_dataset_r)
        left_id = str(row.entity_id_l)
        right_id = str(row.entity_id_r)

        stats_by_source[left_source].total_rows += 1
        stats_by_source[right_source].total_rows += 1

        # Direction 1: left entity points to right entity in left source graph.
        _add_directed_sameas(
            graph=graphs[left_source],
            pending_triples=pending_by_source[left_source],
            subject_uri=left_id,
            object_uri=right_id,
            stats=stats_by_source[left_source],
        )

        # Direction 2: right entity points to left entity in right source graph.
        _add_directed_sameas(
            graph=graphs[right_source],
            pending_triples=pending_by_source[right_source],
            subject_uri=right_id,
            object_uri=left_id,
            stats=stats_by_source[right_source],
        )

    if not args.dry_run:
        for source, file_path in source_to_file.items():
            _append_sameas_triples(file_path, pending_by_source[source])

    mode = "DRY-RUN" if args.dry_run else "WRITE"
    print(f"[{mode}] Predictions CSV: {predictions_path}")
    for source, file_path in source_to_file.items():
        source_stats = stats_by_source[source]
        print(
            "[{}] {} -> rows: {}, directed_assertions_seen: {}, existing: {}, added: {}".format(
                mode,
                file_path,
                source_stats.total_rows,
                source_stats.directed_assertions_seen,
                source_stats.directed_assertions_existing,
                source_stats.directed_assertions_added,
            )
        )


if __name__ == "__main__":
    main()
