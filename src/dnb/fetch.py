"""Fetch and materialize ecclesiastical person data from the DNB/GND SPARQL endpoint.

Executes paginated CONSTRUCT queries against https://sparql.dnb.de/api/gnd,
caches raw N-Triples pages locally, then deduplicates, validates, and writes
a single Turtle file to data/interim/rdf/source-dnb.ttl.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from rdflib import Graph, URIRef

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERIES_DIR = PROJECT_ROOT / "queries" / "acquisition" / "dnb"
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "dnb"

ENDPOINT = "https://sparql.dnb.de/api/gnd"
DEFAULT_PAGE_SIZE = 10_000
MAX_RETRIES = 5
INITIAL_BACKOFF_S = 2.0
REQUEST_TIMEOUT_S = 300.0


# ---------------------------------------------------------------------------
# SPARQL helpers
# ---------------------------------------------------------------------------

def load_query(name: str) -> str:
    path = QUERIES_DIR / name
    return path.read_text(encoding="utf-8")


def run_count_query(client: httpx.Client) -> int:
    query = load_query("count.rq")
    resp = client.get(
        ENDPOINT,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"},
    )
    resp.raise_for_status()
    bindings = resp.json()["results"]["bindings"]
    return int(bindings[0]["total"]["value"])


def run_construct_page(
    client: httpx.Client,
    query_file: str,
    offset: int,
    limit: int,
) -> str:
    template = load_query(query_file)
    query = template.replace("{offset}", str(offset)).replace("{limit}", str(limit))
    resp = client.get(
        ENDPOINT,
        params={"query": query},
        headers={"Accept": "application/n-triples"},
    )
    resp.raise_for_status()
    return resp.text


def fetch_with_retry(
    client: httpx.Client,
    query_file: str,
    offset: int,
    limit: int,
) -> str:
    backoff = INITIAL_BACKOFF_S
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return run_construct_page(client, query_file, offset, limit)
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            if attempt == MAX_RETRIES:
                raise
            logger.warning(
                "Attempt %d/%d failed (offset=%d): %s. Retrying in %.1fs...",
                attempt,
                MAX_RETRIES,
                offset,
                exc,
                backoff,
            )
            time.sleep(backoff)
            backoff *= 2
    raise RuntimeError("unreachable")


def fetch_all_pages(
    client: httpx.Client,
    query_file: str,
    total: int,
    page_size: int,
    output_dir: Path,
) -> list[Path]:
    pages: list[Path] = []
    for offset in range(0, total, page_size):
        page_num = offset // page_size
        page_path = output_dir / f"persons-page-{page_num:04d}.nt"

        if page_path.exists() and page_path.stat().st_size > 0:
            logger.info("Skipping existing page %d (offset=%d)", page_num, offset)
            pages.append(page_path)
            continue

        logger.info(
            "Fetching page %d (offset=%d, limit=%d)...", page_num, offset, page_size
        )
        data = fetch_with_retry(client, query_file, offset, page_size)
        page_path.write_text(data, encoding="utf-8")
        pages.append(page_path)
        logger.info("  -> %d bytes written to %s", len(data), page_path.name)

    return pages


# ---------------------------------------------------------------------------
# Materialization: dedup, validate, convert
# ---------------------------------------------------------------------------

def concatenate_and_dedup(pages: list[Path], output_path: Path) -> int:
    """Concatenate N-Triples pages and deduplicate using sort -u.

    Returns the number of unique lines (triples) written.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".nt", delete=False, dir=output_path.parent
    ) as tmp:
        tmp_path = Path(tmp.name)
        for page in pages:
            tmp.write(page.read_text(encoding="utf-8"))

    result = subprocess.run(
        ["sort", "-u", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    tmp_path.unlink()

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def validate_and_convert(nt_path: Path, ttl_path: Path) -> Graph:
    """Parse N-Triples, log stats, and serialize as Turtle."""
    g = Graph()
    g.parse(nt_path, format="nt")
    logger.info("Parsed %d triples from %s", len(g), nt_path.name)

    gndo = "https://d-nb.info/standards/elementset/gnd#"
    persons = set(g.subjects(
        URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"),
        URIRef(gndo + "Person"),
    ))
    logger.info("Distinct persons (typed gndo:Person): %d", len(persons))

    for prop in [
        "preferredNameForThePerson", "dateOfBirth", "dateOfDeath",
        "professionOrOccupation", "placeOfBirth", "placeOfDeath",
    ]:
        count = len(set(g.subjects(URIRef(gndo + prop))))
        pct = (count / len(persons) * 100) if persons else 0
        logger.info("  %s: %d persons (%.1f%%)", prop, count, pct)

    g.serialize(destination=str(ttl_path), format="turtle")
    logger.info("Wrote Turtle to %s (%d bytes)", ttl_path, ttl_path.stat().st_size)
    return g


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def write_metadata(
    output_dir: Path,
    *,
    endpoint: str,
    total: int,
    page_size: int,
    num_pages: int,
    query_hash: str,
    query_file: str,
    started_at: str,
    finished_at: str,
    num_triples: int,
) -> Path:
    meta = {
        "endpoint": endpoint,
        "query_file": query_file,
        "query_sha256": query_hash,
        "total_persons": total,
        "page_size": page_size,
        "num_pages": num_pages,
        "num_triples_deduped": num_triples,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    path = output_dir / "fetch-metadata.json"
    path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"Number of persons per CONSTRUCT page (default: {DEFAULT_PAGE_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only run the COUNT query, do not fetch data",
    )
    parser.add_argument(
        "--include-literal-occ",
        action="store_true",
        help="Also run the secondary literal-occupation query",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_DIR,
        help=f"Directory for raw page cache (default: {RAW_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RAW_DIR,
        help=f"Directory for materialized Turtle output (default: {RAW_DIR})",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=REQUEST_TIMEOUT_S) as client:
        # --- Count ---
        logger.info("Counting ecclesiastical persons on %s ...", ENDPOINT)
        total = run_count_query(client)
        logger.info("Total persons: %d", total)

        if args.dry_run:
            print(f"Total ecclesiastical persons: {total}")
            return

        started_at = datetime.now(timezone.utc).isoformat()

        # --- Fetch pages ---
        query_file = "construct.rq"
        query_text = load_query(query_file)
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()

        num_pages = (total + args.page_size - 1) // args.page_size
        logger.info("Fetching %d pages (page_size=%d)...", num_pages, args.page_size)
        pages = fetch_all_pages(
            client, query_file, total, args.page_size, args.raw_dir
        )

        if args.include_literal_occ:
            lit_query_file = "construct-literal-occ.rq"
            logger.info("Fetching literal-occupation persons...")
            lit_pages = fetch_all_pages(
                client, lit_query_file, total, args.page_size, args.raw_dir
            )
            pages.extend(lit_pages)

    # --- Materialize: dedup + validate + convert ---
    logger.info("Deduplicating %d page files...", len(pages))
    deduped_path = args.output_dir / "data.nt"
    num_triples = concatenate_and_dedup(pages, deduped_path)
    logger.info("Deduplicated to %d unique triples", num_triples)

    ttl_path = args.output_dir / "data.ttl"
    validate_and_convert(deduped_path, ttl_path)

    finished_at = datetime.now(timezone.utc).isoformat()

    meta_path = write_metadata(
        args.raw_dir,
        endpoint=ENDPOINT,
        total=total,
        page_size=args.page_size,
        num_pages=len(pages),
        query_hash=query_hash,
        query_file=query_file,
        started_at=started_at,
        finished_at=finished_at,
        num_triples=num_triples,
    )

    logger.info("Metadata written to %s", meta_path)
    logger.info("Done. Materialized %d triples -> %s", num_triples, ttl_path)


if __name__ == "__main__":
    main()
