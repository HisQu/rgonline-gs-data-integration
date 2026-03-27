"""
Set up RDF4J server repositories for the ecclesiastical-persons integration.

Creates:
  - gs         native repository  ← Germania Sacra (materialized)
  - rgo        native repository  ← Repertorium Germanicum Online (materialized, placeholder)
  - integration FedX repository   ← federates gs + rgo + DNB SPARQL endpoint

Then loads data/raw/gs/data.ttl into the gs repository (if the file exists).

Idempotent: safe to re-run (existing repos and data are replaced/re-uploaded).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8080/rdf4j-server"
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Repository configs (Turtle)
# ---------------------------------------------------------------------------

NATIVE_REPO_CONFIG = """\
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix config: <tag:rdf4j.org,2023:config/> .

[] a config:Repository ;
   config:rep.id "{repo_id}" ;
   rdfs:label "{label}" ;
   config:rep.impl [
     config:rep.type "openrdf:SailRepository" ;
     config:sail.impl [
       config:sail.type "openrdf:NativeStore" ;
       config:native.tripleIndexes "spoc,posc"
     ]
   ] .
"""

# FedX federates the two local repos (ResolvableRepository = same RDF4J instance,
# no HTTP round-trip) plus the live DNB/GND SPARQL endpoint for query-time rewriting.
FEDX_REPO_CONFIG = """\
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix config: <tag:rdf4j.org,2023:config/> .
@prefix fedx: <http://rdf4j.org/config/federation#> .

[] a config:Repository ;
   config:rep.id "integration" ;
   rdfs:label "Ecclesiastical Persons — Integrated (GS + RGO + DNB)" ;
   config:rep.impl [
     config:rep.type "fedx:FedXRepository" ;
     fedx:member [
       fedx:store "ResolvableRepository" ;
       fedx:repositoryName "gs"
     ] ;
     fedx:member [
       fedx:store "ResolvableRepository" ;
       fedx:repositoryName "rgo"
     ] ;
     fedx:member [
       fedx:store "SPARQLEndpoint" ;
       fedx:repositoryName "dnb" ;
       fedx:endpointURI "https://sparql.dnb.de/api/gnd"
     ]
   ] .
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_server(client: httpx.Client, retries: int = 30, delay: float = 2.0) -> None:
    url = f"{BASE}/protocol"
    print(f"Waiting for RDF4J server at {url} ...", flush=True)
    for attempt in range(1, retries + 1):
        try:
            r = client.get(url, timeout=5)
            if r.status_code == 200:
                print(f"  Server ready (attempt {attempt})")
                return
        except httpx.TransportError:
            pass
        print(f"  Not ready yet (attempt {attempt}/{retries}), retrying in {delay}s ...")
        time.sleep(delay)
    print("ERROR: RDF4J server did not become ready in time.", file=sys.stderr)
    sys.exit(1)


def delete_repo_if_exists(client: httpx.Client, repo_id: str) -> None:
    r = client.delete(f"{BASE}/repositories/{repo_id}", timeout=30)
    if r.status_code in (200, 204):
        print(f"  Deleted existing '{repo_id}' repository")
    elif r.status_code in (400, 404):
        pass  # didn't exist — RDF4J returns 400 "could not locate repository configuration"
    else:
        r.raise_for_status()


def create_repo(client: httpx.Client, repo_id: str, config_ttl: str) -> None:
    r = client.put(
        f"{BASE}/repositories/{repo_id}",
        content=config_ttl.encode(),
        headers={"Content-Type": "text/turtle"},
        timeout=30,
    )
    r.raise_for_status()
    print(f"  Created '{repo_id}' repository")


def load_data(client: httpx.Client, repo_id: str, ttl_path: Path) -> None:
    if not ttl_path.exists():
        print(f"  Skipping data load — {ttl_path} not found")
        return
    size_mb = ttl_path.stat().st_size / 1_048_576
    print(f"  Loading {ttl_path.name} ({size_mb:.1f} MB) into '{repo_id}' ...", flush=True)
    with ttl_path.open("rb") as fh:
        r = client.post(
            f"{BASE}/repositories/{repo_id}/statements",
            content=fh.read(),
            headers={"Content-Type": "text/turtle"},
            timeout=600,
        )
    r.raise_for_status()
    print(f"  Data loaded into '{repo_id}'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    with httpx.Client() as client:
        wait_for_server(client)

        # --- gs (Germania Sacra) ---
        print("\nSetting up 'gs' repository ...")
        delete_repo_if_exists(client, "gs")
        create_repo(client, "gs", NATIVE_REPO_CONFIG.format(
            repo_id="gs", label="Germania Sacra"
        ))
        load_data(client, "gs", PROJECT_ROOT / "data" / "raw" / "gs" / "data.ttl")

        # --- rgo (Repertorium Germanicum Online, placeholder) ---
        print("\nSetting up 'rgo' repository ...")
        delete_repo_if_exists(client, "rgo")
        create_repo(client, "rgo", NATIVE_REPO_CONFIG.format(
            repo_id="rgo", label="Repertorium Germanicum Online"
        ))
        load_data(client, "rgo", PROJECT_ROOT / "data" / "raw" / "rgo" / "data.ttl")

        # --- integration (FedX: gs + rgo + DNB) ---
        print("\nSetting up 'integration' FedX repository ...")
        delete_repo_if_exists(client, "integration")
        create_repo(client, "integration", FEDX_REPO_CONFIG)

    print("\nDone — RDF4J Workbench at http://localhost:8080/rdf4j-workbench")
    print("  Repositories: gs, rgo, integration (federated)")


if __name__ == "__main__":
    main()
