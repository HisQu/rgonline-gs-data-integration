# ADR 0004: Do not materialize DNB — federate via QLever, align other sources to GNDO

## Status

Accepted

## Context

The pipeline uses Morph-KGC to materialize non-RDF source data (XML) into RDF. The RGO (Repertorium Germanicum Online)
requires this step because its native format is not RDF. The GS (Germania Sacra) source is already RDF, but does not
adhere to RDF standards (e.g., it uses statements like `:personX a "foaf:Person"^^xsd:string`), so it needs thorough
rewriting; since source changes are infrequent, materialization is acceptable.

The Deutsche Nationalbibliothek (DNB) source is different: GND person data is **already native RDF**, served via a
public SPARQL 1.1 endpoint at `https://sparql.dnb.de/api/gnd`. The endpoint is backed by QLever and supports CONSTRUCT
queries that return N-Triples. Its ontology — the **GND Ontology (GNDO)** — is well-documented and stable.

Because the DNB data is already high-quality RDF and the endpoint supports federation, materializing it locally would
duplicate data unnecessarily. At the same time, adopting a new project-local ontology would require mapping GND data
away from GNDO, discarding the native structure.

## Decision

We do **not** materialize the DNB graph locally. Instead:

1. The DNB SPARQL endpoint is treated as a federation target and queried at integration time via QLever's federated
   query support (`SERVICE` clauses).
2. **All other sources (GS, RGO) are harmonized to GNDO** rather than to a project-local ontology. This keeps the
   DNB data as the schema authority and avoids any lossy translation of GND terms.
3. Materialization of the DNB graph remains an option for reproducibility or offline use — pages can still be fetched
   and stored as N-Triples via `src/dnb/fetch.py` — but it is not a required pipeline step.

No `configs/morph-kgc/source-dnb.ini` or `mappings/source-dnb/mapping.rml.ttl` files are created for DNB.

## Consequences

- Native GND URIs (`https://d-nb.info/gnd/{ID}`) are retained as subject identifiers — no project-local URI minting
  needed for this source.
- GS and RGO harmonization mappings (`mappings/source-gs/`, `mappings/source-rgo/`) must produce GNDO-conformant
  triples rather than mapping to a bespoke ontology.
- Federated queries execute at runtime against the live endpoint; query performance depends on the DNB service.
  If offline reproducibility is required, the fetch script can be used to snapshot the data first.
- The ecclesiastical filter applied during CONSTRUCT queries must be kept in sync with the federated `SERVICE` queries
  to ensure consistent person-set coverage across both access modes.
