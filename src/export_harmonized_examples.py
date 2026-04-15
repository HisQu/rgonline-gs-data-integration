#!/usr/bin/env python3
"""Export per-person harmonized example graphs.

Reads harmonized output plus DNB and GS statements (if present) and writes one
Turtle file per selected person into data/examples/harmonized/.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

PERSONS = {
    "gerhard_hoya": {
        "gnd": "136175414",
        "rgo": "https://rg-online.dhi-roma.it/rg/person/10504820",
        "gs": "https://personendatenbank.germania-sacra.de/index/gsn/005-02827-001",
    },
    "dietrich_ii_moers": {
        "gnd": "118525530",
        "rgo": "https://rg-online.dhi-roma.it/rg/person/10517697",
        "gs": "https://personendatenbank.germania-sacra.de/index/gsn/012-00347-001",
    },
    "heinrich_bodo": {
        "gnd": "10427526X",
        "rgo": "https://rg-online.dhi-roma.it/rg/person/10505909",
        "gs": "https://personendatenbank.germania-sacra.de/index/gsn/015-00498-001",
    },
    "friedrich_arnsberg": {
        "gnd": "137509782",
        "rgo": "https://rg-online.dhi-roma.it/rg/person/10504302",
        "gs": "https://personendatenbank.germania-sacra.de/index/gsn/048-02156-001",
    },
}

GNDO_DIFFERENTIATED_PERSON = URIRef(
    "https://d-nb.info/standards/elementset/gnd#DifferentiatedPerson"
)
PREFERRED_PREFIXES = {
    "gnd": "https://d-nb.info/gnd/",
    "gndo": "https://d-nb.info/standards/elementset/gnd#",
    "gsn": "https://personendatenbank.germania-sacra.de/index/gsn/",
    "rgo": "https://rg-online.dhi-roma.it/ontology/",
    "rg": "https://rg-online.dhi-roma.it/rg/",
}


def build_source_graph(paths: list[Path]) -> Graph:
    g = Graph()
    for path in paths:
        if not path.exists():
            continue
        g.parse(path, format="turtle")
    return g


def bind_prefixes(graph: Graph, source: Graph) -> None:
    # Carry over parsed prefixes and enforce stable readable project prefixes.
    for prefix, namespace in source.namespace_manager.namespaces():
        graph.bind(prefix, namespace, replace=False)
    for prefix, namespace in PREFERRED_PREFIXES.items():
        graph.bind(prefix, namespace, replace=True)


def extract_subgraph_neighborhood(
    source: Graph, seeds: list[URIRef], max_depth: int = 3
) -> Graph:
    out = Graph()
    seen: set[URIRef] = set()
    queue: deque[tuple[URIRef, int]] = deque((seed, 0) for seed in seeds)

    while queue:
        node, depth = queue.popleft()
        if node in seen or depth > max_depth:
            continue
        seen.add(node)

        for s, p, o in source.triples((node, None, None)):
            out.add((s, p, o))
            if isinstance(o, URIRef):
                queue.append((o, depth + 1))

    return out


def extract_subgraph_focused(
    source: Graph, seeds: list[URIRef], max_depth: int = 3
) -> Graph:
    """Export a person-focused neighborhood without pulling in other persons."""
    out = Graph()
    seen: set[URIRef] = set()
    queue: deque[tuple[URIRef, int]] = deque((seed, 0) for seed in seeds)
    seed_set = set(seeds)
    person_nodes = set(source.subjects(RDF.type, GNDO_DIFFERENTIATED_PERSON))

    def is_non_seed_person(node: URIRef) -> bool:
        if node in seed_set:
            return False
        if node in person_nodes:
            return True
        node_str = str(node)
        return (
            node_str.startswith("https://rg-online.dhi-roma.it/rg/person/")
            or node_str.startswith("http://rg-online.dhi-roma.it/rg/person/")
            or node_str.startswith("https://d-nb.info/gnd/")
            or node_str.startswith("http://d-nb.info/gnd/")
            or node_str.startswith(
                "https://personendatenbank.germania-sacra.de/index/gsn/"
            )
            or node_str.startswith(
                "http://personendatenbank.germania-sacra.de/index/gsn/"
            )
        )

    while queue:
        node, depth = queue.popleft()
        if node in seen or depth > max_depth:
            continue
        seen.add(node)

        # Keep the export centered on one person; do not expand through others.
        if is_non_seed_person(node):
            continue

        for s, p, o in source.triples((node, None, None)):
            if isinstance(o, URIRef) and is_non_seed_person(o):
                continue
            out.add((s, p, o))
            if isinstance(o, URIRef):
                queue.append((o, depth + 1))

    return out


def add_cross_source_same_as(graph: Graph, meta: dict[str, str]) -> None:
    person_uris = [
        URIRef(f"https://d-nb.info/gnd/{meta['gnd']}"),
        URIRef(meta["rgo"]),
        URIRef(meta["gs"]),
    ]
    for idx, left in enumerate(person_uris):
        for right in person_uris[idx + 1 :]:
            graph.add((left, OWL.sameAs, right))
            graph.add((right, OWL.sameAs, left))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harmonized", default="data/harmonized/statements.ttl")
    parser.add_argument("--gs", default="data/harmonized/gs.ttl")
    parser.add_argument("--dnb", default="data/raw/dnb/statements.ttl")
    parser.add_argument("--output-dir", default="data/examples/harmonized")
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument(
        "--mode",
        choices=["focused", "neighborhood"],
        default="focused",
        help=(
            "Export mode. 'focused' keeps one person per file by excluding other "
            "DifferentiatedPerson nodes; 'neighborhood' reproduces the previous "
            "broader traversal behavior."
        ),
    )
    args = parser.parse_args()

    source = build_source_graph([Path(args.harmonized), Path(args.gs), Path(args.dnb)])
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for slug, meta in PERSONS.items():
        gnd = meta["gnd"]
        seeds = [
            URIRef(f"https://d-nb.info/gnd/{gnd}"),
            URIRef(f"http://d-nb.info/gnd/{gnd}"),
            URIRef(meta["rgo"]),
            URIRef(meta["gs"]),
        ]
        if args.mode == "neighborhood":
            sub = extract_subgraph_neighborhood(source, seeds, max_depth=args.depth)
        else:
            sub = extract_subgraph_focused(source, seeds, max_depth=args.depth)
        add_cross_source_same_as(sub, meta)
        bind_prefixes(sub, source)
        out_path = output_dir / f"{slug}.ttl"
        sub.serialize(destination=str(out_path), format="turtle")
        print(f"{slug} [{args.mode}]: {len(sub)} triples -> {out_path}")


if __name__ == "__main__":
    main()
