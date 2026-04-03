# Germania Sacra API Technical Specifications

## Fetching a TTL file of all persons
```http request
GET https://personendatenbank.germania-sacra.de/api/v1.0/person?query[0][field]=person.vorname&query[0][operator]=contains&query[0][value]=&query[0][connector]=and&query[1][field]=person.familienname&query[1][operator]=contains&query[1][value]=&query[1][connector]=and&query[2][field]=amt.bezeichnung&query[2][operator]=contains&query[2][value]=&query[2][connector]=and&query[3][field]=fundstelle.bandtitel&query[3][operator]=contains&query[3][value]=&format=turtle&limit=1000000
```

## Known Data Quality Flaws

The raw Turtle file returned by the API contains several structural problems that
must be corrected before the data can be used in an RDF knowledge graph.
The cleaning query `mappings/gs/clean.rq` addresses all of them.

Project namespace prefix used in GS mappings:

- `gsn: <https://personendatenbank.germania-sacra.de/index/gsn/>`

### 1. Type assertions encoded as typed string literals

The API serialises RDF type assertions as `xsd:string` literals instead of IRI
references:

```turtle
_:bn a "foaf:Person"^^xsd:string .
_:bn2 a "foaf:Organization"^^xsd:string, "prov:Agent"^^xsd:string .
```

These are semantically meaningless in standard RDF — `rdf:type` expects an IRI,
not a literal.  The clean pass maps each string to its proper class IRI via a
`VALUES` table.

### 2. Persons serialised as blank nodes

Every person is a blank node with an `owl:sameAs` link to the canonical GS URI
(`https://personendatenbank.germania-sacra.de/index/gsn/…`).  Blank nodes are
not addressable across datasets, which breaks entity resolution and linking.
The clean pass promotes each blank node to its canonical GS URI as the subject.

### 3. String-typed name literals

Given names and family names are typed `^^xsd:string` rather than plain strings:

```turtle
_:bn schema:givenName "Adalbero"^^xsd:string .
```

The clean pass strips the explicit datatype, producing a plain literal.

### 4. Untyped or loosely typed date literals

Birth and death dates are always `^^xsd:string`, even when the value is a clean
four-digit year.  Many values are natural-language descriptions:

```
"1753"^^xsd:string   → promoted to "1753"^^xsd:gYear
"um 1172"^^xsd:string
"vor 938"^^xsd:string
"13. Jh."^^xsd:string
"Mitte 10. Jahrhundert"^^xsd:string
"993/994"^^xsd:string
"zwischen Anfang 13. und 15. Jahrhundert"^^xsd:string
"Anfang 15. Jahrhundert"^^xsd:string
```

The clean pass promotes unambiguous four-digit year strings to `xsd:gYear` and
tags the remaining free-text values as `@de`.  The same rule applies to
`participation:startDate` / `participation:endDate` on office records.

### Date normalization for GNDO harmonization

To make the cleaned GS dates usable in GNDO-oriented harmonization, run:

```bash
just gs-fix-dates
```

This executes `scripts/fix_gs_clean_dates.py` on `data/raw/gs/clean.ttl`.
The script applies simple, intentionally broad assumptions and rewrites date
literals as `xsd:gYear`.

Boundary rule:

- lower-bound fields (`schema:birthDate`, `part:startDate`) pick the earliest plausible year
- upper-bound fields (`schema:deathDate`, `part:endDate`) pick the latest plausible year

Examples:

- `1120/1130` -> start `1120`, end `1130`
- `vor 1495` -> start `1395`, end `1495`
- `um 1206` -> start `1196`, end `1216`
- `Ende 14. Jahrhundert` -> end `1500` (wider upper bound)

### 5. Participation links as plain strings

The `participation:role_at` property on office (`#amt-`) records and the
`participation:role` property on organisation (`#organisation-`) records store
cross-references as `xsd:string` literals using a local prefix:

```turtle
<…#amt-371293> participation:role_at "person:024-00002-001#organisation-371293"^^xsd:string .
```

The `person:` pseudo-prefix is not declared anywhere in the file.  The clean
pass reconstructs the full IRI by replacing `person:` with the GS base URI
`https://personendatenbank.germania-sacra.de/index/gsn/`.

### 6. `rdfs:Container` used as a predicate (garbage artefact)

Each blank-node person carries a triple with `rdfs:Container` as the predicate,
pointing to another blank node:

```turtle
_:bn rdfs:Container _:bn2 .
```

`rdfs:Container` is a class, not a property.  This appears to be a serialisation
artefact with no semantic meaning.  The clean pass silently drops it.
