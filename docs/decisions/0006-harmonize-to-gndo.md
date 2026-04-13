# ADR 0006: Harmonize GS and RGO to GNDO (with RG ontology fallback)

## Status

Proposed

## Context

The integration combines three person-centric sources:

- Germania Sacra (GS)
- Repertorium Germanicum Online, vol. 5 (RGO)
- Deutsche Nationalbibliothek / GND (DNB)

DNB already uses GNDO. GS and RGO use source-specific structures and must be harmonized so that users can query across all sources with GNDO terms.

A pure GNDO projection is not sufficient because parts of GS/RGO carry source semantics that GNDO does not model directly (for example lemma/sublemma structure and GS office role wiring).

## Decision

1. GNDO is the primary query vocabulary for cross-source person access.
2. Statements that cannot be expressed cleanly in GNDO are preserved under RG ontology terms (`rgo:*`).
3. Harmonization is implemented as SPARQL `CONSTRUCT` queries:
   - `mappings/gs/harmonize.rq`
   - `mappings/rgo/harmonize.rq`
4. Example snapshots are maintained for multi-source validation.

## Selected Multi-Source Examples

- Albertus Blarer (`gnd:1017854483`) — RGO `person/10500219`
- Gerhard Hoya (`gnd:136175414`) — RGO `person/10504820`
- Dietrich II. Moers (`gnd:118525530`) — RGO `person/10517697`
- Heinrich Bodo (`gnd:10427526X`) — RGO `person/10505909`
- Friedrich Arnsberg (`gnd:137509782`) — RGO `person/10504302`

## Files

- `mappings/gs/harmonize.rq`
- `mappings/rgo/harmonize.rq`
- `data/examples/albertus_blarer.ttl`
- `gerhard_hoya.ttl`
- `dietrich_ii_moers.ttl`
- `heinrich_bodo.ttl`
- `friedrich_arnsberg.ttl`
- `data/examples/johannes_xxiii.ttl` (kept as historical reference sample)
- `data/examples/example-from-gnd-doc.rdf`
- `data/examples/example-person-in-domain.ttl`

## Mapping Rules

### GS -> GNDO

- `foaf:Person` (or raw literal typed equivalent) -> `gndo:DifferentiatedPerson`
- `schema:givenName` + `schema:familyName` -> `gndo:preferredNameForThePerson`
- name parts -> `gndo:NameOfThePerson` via `gndo:preferredNameEntityForThePerson`
- `schema:birthDate` -> `gndo:dateOfBirth`
- `schema:deathDate` -> `gndo:dateOfDeath`
- `foaf:name` on GS office entries -> `gndo:professionOrOccupationAsLiteral`
- `org:memberOf` / organisation links -> `gndo:affiliation` and `gndo:affiliationAsLiteral`
- organisation labels -> `gndo:preferredNameForTheCorporateBody` with `gndo:CorporateBody`
- office start/end hints -> `gndo:periodOfActivity` (literalized range)
- GS `owl:sameAs` links to DNB GND are preserved

### RGO -> GNDO

RGO already contains partial GNDO person modeling; harmonization adds:

- `rgo:mentionsPerson` -> `gndo:relatedPerson`
- `rgo:mentionsPlace` -> `gndo:relatedPlaceOrGeographicName`
- `rgo:dateValue` -> `gndo:associatedDate`
- lift sublemma dates to person level as `gndo:associatedDate`
- lift place linkage through lemmas to person level as `gndo:placeOfActivity`

RGO source structure is retained in RG ontology fallback:

- `rgo:RegestEntry` / `rgo:SubEntry` class distinction (`rgo:Lemma`, `rgo:Sublemma`)
- `rgo:sourceId`, `rgo:appearsInLemma`, `rgo:hasSubEntry`, `rgo:partOfLemma`
- fields without practical GNDO equivalents in this dataset (currently `volume`, `fundReferencePart*`)

## Consequences

- Cross-source person queries can use GNDO as the default schema.
- Source-faithful lemma/sublemma semantics remain available via `rgo:*` where GNDO has no direct equivalent.
- Some identity alignments remain historical-source dependent and should be treated as curated links (not guaranteed modern authority equivalence in every case).

## Future Work

- Move remaining root-level person example TTLs into `data/examples/` for consistency.
- Add automated harmonization validation tests for the five selected persons.
- Add a deterministic extraction script to regenerate person snapshots from source stages.
