# DNB Technical Specification (Current Setup)

## 1. Scope

This document describes how DNB person data is acquired and used in the current
project setup.

Current implementation status:

- Primary acquisition path: local bulk download of the GND person dump.
- Primary runtime path: local file ingestion into QLever (`data/raw/dnb/statements.ttl`).
- No active project code currently queries the DNB SPARQL endpoint for ingestion.

## 2. Data Source Used

The project currently uses the DNB Open Data dump for GND persons:

- `https://data.dnb.de/opendata/authorities-gnd-person_lds.ttl.gz`

This is the authoritative source for the DNB stage in this repository.

## 3. Acquisition Workflow

Acquisition is performed through the `just` recipe `dnb-fetch`.

Command:

```bash
just dnb-fetch
```

Current recipe behavior:

1. Download gzip archive to:
   `data/raw/dnb/authorities-gnd-person_lds.ttl.gz`
2. Decompress to Turtle:
   `data/raw/dnb/statements.ttl`

Equivalent shell logic:

```bash
mkdir -p data/raw/dnb
curl -L -o data/raw/dnb/authorities-gnd-person_lds.ttl.gz \
  https://data.dnb.de/opendata/authorities-gnd-person_lds.ttl.gz
gunzip -c data/raw/dnb/authorities-gnd-person_lds.ttl.gz \
  > data/raw/dnb/statements.ttl
```

## 4. Repository Paths (Current)

Main DNB stage files:

- `data/raw/dnb/authorities-gnd-person_lds.ttl.gz` (compressed source)
- `data/raw/dnb/statements.ttl` (expanded Turtle used by indexing)

Small example/reference files are stored under:

- `data/examples/example-from-gnd-doc.rdf`
- `data/examples/example-person-in-domain.ttl`

## 5. Integration into Query Stack

QLever loads DNB from:

- `data/raw/dnb/statements.ttl`

and mounts it into the named graph configured in `Qleverfile`:

- `<https://data.rgonline-integration.de/graph/dnb>`

This means all harmonization/query work can run against the local indexed graph
without live endpoint dependency.

## 6. Ontology and Modeling Assumptions

The DNB person dump is modeled in GNDO and is treated as schema authority for
cross-source person harmonization.

Main namespace:

- `gndo: <https://d-nb.info/standards/elementset/gnd#>`

Commonly used person terms in this project:

- `gndo:DifferentiatedPerson`
- `gndo:gndIdentifier`
- `gndo:preferredNameForThePerson`
- `gndo:variantNameForThePerson`
- `gndo:preferredNameEntityForThePerson`
- `gndo:dateOfBirth`
- `gndo:dateOfDeath`
- `gndo:associatedDate`
- `gndo:placeOfActivity`

## 7. Operational Notes

- `data/raw/dnb/statements.ttl` is very large (multi-GB).
- Prefer streaming tools (`rg`, `sed`, SPARQL over indexed graph) over loading
  the full file into memory.
- Refresh cadence depends on when `just dnb-fetch` is executed in this project.
  (DNB publishes updated dumps periodically.)

## 8. SPARQL Endpoint Status

DNB endpoint references are retained as optional external references only:

- UI: `https://sparql.dnb.de`
- API (GND): `https://sparql.dnb.de/api/gnd`

They are not the active ingestion path in the current repository setup.

## 9. Change History Note

Earlier versions of this spec described an endpoint-first acquisition strategy.
The repository has since moved to a dump-first workflow (`just dnb-fetch`) and
this document reflects that current state.
