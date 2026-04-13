# ADR 0005: Use QLever for federation instead of RDF4J+FedX

## Status

Superseded by ADR 0008 (DNB federation replaced by local materialization)

## Context

When designing the integration layer we evaluated two approaches to combining the three data sources (GS, DNB, RGO)
without fully materializing all of them:

**Option A — RDF4J with FedX and a custom ontology.**
RDF4J supports virtual knowledge graph integration: a mediator ontology is defined, each source is mapped to it via
R2RML/RML, and FedX rewrites incoming SPARQL queries at runtime so that the right sub-queries are sent to each
endpoint transparently. This approach is attractive when sources use incompatible schemas, because the ontology acts
as a common semantic layer and query rewriting hides source heterogeneity from the query author.

**Option B — QLever with explicit `SERVICE` federation.**
QLever supports `SERVICE` clauses in SPARQL 1.1, which let a query author explicitly direct sub-queries to remote
endpoints. No mediator ontology or automatic rewriting is involved; the query author controls the federation
boundaries directly.

The deciding factor was the **choice of shared ontology**. We initially planned to write a project-local ontology
and map all three sources into it. However, the DNB data is already modelled with the
**GND Ontology (GNDO)** — a mature, well-documented vocabulary covering exactly the domain we need (persons,
corporate bodies, places, subject headings). Adopting a bespoke ontology would have required mapping GND data
*away* from GNDO, which would lose precision and create maintenance burden.

Once we decided (ADR 0004) to treat GNDO as the schema authority and harmonize GS and RGO *into* GNDO, the main
motivation for RDF4J+FedX disappeared: there is no heterogeneous schema to hide, and no query rewriting is needed.
Simple `SERVICE`-based federation against the DNB SPARQL endpoint
(`https://sparql.dnb.de/api/gnd`) is sufficient.

## Decision

We use **QLever** for SPARQL federation with explicit `SERVICE` clauses. RDF4J+FedX is not adopted.

Federation queries reference the live DNB endpoint directly. Because the integration strategy starts with aligning
GS to the GND data (as a first integration milestone before adding RGO), this approach is sufficient for the
foreseeable scope of the project.

Partial materialization of GND data remains a valid future option. The DNB publishes full data dumps at
<https://data.dnb.de/opendata/>; the "Gesamtabzug GND" (complete GND export, approx. 1.3 GB) can be downloaded and
loaded into the local QLever index if offline availability or lower query latency becomes a requirement.

## Consequences

- Queries that join local GS/RGO data with GND data must include an explicit `SERVICE <https://sparql.dnb.de/api/gnd>`
  clause — the federation is not transparent to the query author.
- No mediator ontology infrastructure (R2RML wrappers, FedX source descriptors, RDF4J server) needs to be set up or
  maintained.
- If the DNB endpoint is unavailable, federated queries fail. Materializing the "Gesamtabzug" dump into the local
  QLever index would make the pipeline endpoint-independent.
- The GND dump path (`data/raw/dnb/`) and existing fetch machinery (`src/dnb/fetch.py`) are compatible with a future
  switch to local materialization — the same pipeline step would simply load the dump instead of querying the live
  endpoint.
