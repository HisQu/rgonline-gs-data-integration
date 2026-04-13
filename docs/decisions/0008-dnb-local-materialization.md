# ADR 0008: Download DNB data locally instead of federating with the live endpoint

## Status

Accepted — supersedes the DNB federation strategy from ADR 0005

## Context

ADR 0005 decided to use QLever with explicit `SERVICE <https://sparql.dnb.de/api/gnd>` federation against the
live DNB SPARQL endpoint. This worked for exploratory SPARQL queries but proved insufficient once entity matching
was introduced into the pipeline.

The entity resolution step (`src/matching/`) operates on flat Pandas DataFrames that are populated by traversing
all three sources' RDF graphs locally (`fetch_context.py`). This requires all person profiles — including those
from DNB — to be available as in-process RDF data. A live SPARQL endpoint cannot be traversed as a graph object;
it only responds to individual queries. Materializing the full DNB cohort via repeated federated queries would
be impractically slow and fragile (network failures, endpoint downtime, rate limits).

The DNB publishes its complete authority data as periodic dumps at <https://data.dnb.de/opendata/>. The relevant
exports ("Gesamtabzug GND Personen" and "Gesamtabzug GND Geografika") cover exactly the entity types needed and
are available for bulk download without authentication. ADR 0005 already identified this path as a valid future
option.

## Decision

We **download a local copy of the relevant DNB data** (GND person and place dumps) and load it into the local
QLever index rather than federating with the live DNB endpoint.

- `just dnb-fetch` downloads the two GND dumps (`persons_full.ttl`, `places_full.ttl`) and merges them into
  `data/raw/dnb/full.ttl`.
- The cohort- and example-filtering steps (`just dnb-reduce`, `just dnb-extract-examples`) produce
  `data/raw/dnb/cohort.ttl` and `data/raw/dnb/example.ttl`, which are swapped in via `just use-cohort` /
  `just use-example` like the other sources.
- `data/raw/dnb/statements.ttl` is indexed into the `https://data.rgonline-integration.de/graph/dnb` named
  graph in QLever alongside GS and RGO.
- `SERVICE` clauses targeting the live DNB endpoint are no longer used in the pipeline.

## Consequences

- Entity matching can traverse all three sources' RDF graphs in-process without any network dependency.
- The pipeline is fully reproducible offline after an initial `just dnb-fetch`.
- The local DNB snapshot can become stale relative to the live GND. For the purposes of this project
  (a fixed RG5 cohort from the 15th century) this is not a concern; the historical persons in scope are not
  updated.
- The GND person dump is large (~1.3 GB compressed). `just dnb-fetch` should be run once and the result cached;
  it does not need to be re-fetched for every pipeline run.
