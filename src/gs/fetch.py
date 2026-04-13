"""Fetch all Germania Sacra person data.

The GS API paginates alphabetically by surname (~2 775 pages total).

Pages are cached under data/raw/gs/pages/ so re-runs skip already-fetched
pages. Merged output is written to data/raw/gs/full.ttl.

Polite scraping: 1.5 s between requests, User-Agent identifies the project.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import httpx
from rdflib import Graph, URIRef
from rdflib.namespace import OWL

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAGES_DIR = PROJECT_ROOT / "data" / "raw" / "gs" / "pages"
OUTPUT = PROJECT_ROOT / "data" / "raw" / "gs" / "full.ttl"

# API endpoint — square brackets in field names require percent-encoding so
# that httpx / curl do not interpret them as glob patterns.
API_URL = (
    "https://personendatenbank.germania-sacra.de/api/v1.0/person"
    "?query%5B0%5D%5Bfield%5D=person.vorname"
    "&query%5B0%5D%5Boperator%5D=contains"
    "&query%5B0%5D%5Bvalue%5D="
    "&query%5B0%5D%5Bconnector%5D=and"
    "&query%5B1%5D%5Bfield%5D=person.familienname"
    "&query%5B1%5D%5Boperator%5D=contains"
    "&query%5B1%5D%5Bvalue%5D="
    "&query%5B1%5D%5Bconnector%5D=and"
    "&query%5B2%5D%5Bfield%5D=amt.bezeichnung"
    "&query%5B2%5D%5Boperator%5D=contains"
    "&query%5B2%5D%5Bvalue%5D="
    "&query%5B2%5D%5Bconnector%5D=and"
    "&query%5B3%5D%5Bfield%5D=fundstelle.bandtitel"
    "&query%5B3%5D%5Boperator%5D=contains"
    "&query%5B3%5D%5Bvalue%5D="
    "&query%5B3%5D%5Bconnector%5D=and"
    "&format=turtle"
)

USER_AGENT = "Friedrich-Schiller-Universitaet Jena, daniel.motz@uni-jena.de"
REQUEST_TIMEOUT_S = 60.0
REQUEST_DELAY_S = 1.5  # seconds between requests — be polite

GS_BASE = "https://personendatenbank.germania-sacra.de/index/gsn/"


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _fetch_page(client: httpx.Client, page: int) -> str:
    url = f"{API_URL}&page={page}"
    resp = client.get(url, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def _is_empty(text: str) -> bool:
    """True when the API returns a page with no person data."""
    return len(text.strip()) <= 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-page", type=int, default=1,
        help="First page to fetch (default: 1)",
    )
    parser.add_argument(
        "--delay", type=float, default=REQUEST_DELAY_S,
        help=f"Seconds between requests (default: {REQUEST_DELAY_S})",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    merged = Graph()
    page = args.start_page
    total_persons = 0

    with httpx.Client(timeout=REQUEST_TIMEOUT_S) as client:
        while True:
            page_path = PAGES_DIR / f"page-{page:05d}.ttl"

            if page_path.exists() and page_path.stat().st_size > 1:
                ttl = page_path.read_text(encoding="utf-8")
                logger.debug("Page %d: cached (%d bytes)", page, len(ttl))
            else:
                logger.info("Page %d: fetching...", page)
                ttl = _fetch_page(client, page)
                page_path.write_text(ttl, encoding="utf-8")
                logger.debug("Page %d: %d bytes", page, len(ttl))
                time.sleep(args.delay)

            if _is_empty(ttl):
                logger.info("Page %d: empty — end of dataset", page)
                break

            pg = Graph()
            try:
                pg.parse(data=ttl, format="turtle")
            except Exception as exc:
                logger.warning("Page %d: parse error — %s", page, exc)
                page += 1
                continue

            for triple in pg:
                merged.add(triple)
            new_persons = sum(
                1 for _, _, o in pg.triples((None, OWL.sameAs, None))
                if isinstance(o, URIRef) and str(o).startswith(GS_BASE)
                and "#" not in str(o)
            )
            total_persons += new_persons
            logger.info(
                "Page %d: %d persons (total so far: %d)",
                page, new_persons, total_persons,
            )

            page += 1

    logger.info(
        "Done. %d total relevant persons across %d pages. Serialising...",
        total_persons, page - args.start_page,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    merged.serialize(destination=str(OUTPUT), format="turtle")
    logger.info("Written %d bytes to %s", OUTPUT.stat().st_size, OUTPUT)


if __name__ == "__main__":
    main()
