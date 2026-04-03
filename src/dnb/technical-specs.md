# Technical specification: accessing DNB person data via the SPARQL endpoint

## 1. Purpose and project role

This document specifies how the **Deutsche Nationalbibliothek (DNB)** contribution shall be accessed for the information integration project **via the DNB SPARQL service**, without relying on bulk materialization as the primary access path.

For this project, the relevant DNB dataset is the **GND authority data** for persons. The default machine endpoint shall therefore be the **GND-only SPARQL endpoint**:

- **Web UI:** `https://sparql.dnb.de`
- **GND-only API endpoint:** `https://sparql.dnb.de/api/gnd`
- **Combined DNB + GND API endpoint:** `https://sparql.dnb.de/api/dnbgnd`


The GND-only endpoint shall be preferred unless bibliographic title data from the Deutsche Nationalbibliografie must be queried together with GND entities.

## 2. Normative sources

The implementation and data modeling shall follow these official DNB resources:

1. **DNB SPARQL Service (BETA)**  
   `https://wiki.dnb.de/spaces/LINKEDDATASERVICE/pages/449878933/DNB+SPARQL+Service+BETA`
2. **GND Ontology**  
   `https://d-nb.info/standards/elementset/gnd`
3. **Linked Data Service: metadata in direct access**  
   `https://www.dnb.de/EN/Professionell/Metadatendienste/Datenbezug/LDS/ldsZugriff.html`
4. **Collection of DNB SPARQL queries**  
   `https://wiki.dnb.de/spaces/LINKEDDATASERVICE/pages/480810660/Sammlung+SPARQL+Anfragen`
5. **RDF vocabularies overview**  
   `https://www.dnb.de/EN/Professionell/Metadatendienste/Exportformate/RDF-Vokabulare/rdf.html`
6. **TTL dump**
   `https://data.dnb.de/opendata/authorities-gnd-person_lds.ttl.gz`

## 3. Service characteristics

According to DNB, the SPARQL service:

- is a **SPARQL 1.1** retrieval interface,
- is operated with **QLever**,
- is currently in **public beta**,
- provides a **GND-only** endpoint and a **combined DNB+GND** endpoint,
- updates both the GND and DNB title data **monthly**,
- supports the following output media types via the API:
  - `text/tab-separated-values`
  - `application/sparql-results+json`
  - `application/sparql-results+xml`
  - `application/n-triples`

The service is read-only from the perspective of this project.

## 4. Core ontology and namespaces

### 4.1 Main ontology

The core vocabulary for GND authority data is the **GND Ontology**.

- **Ontology URI:** `https://d-nb.info/standards/elementset/gnd`
- **Preferred namespace prefix:** `gndo`
- **Preferred namespace URI:** `https://d-nb.info/standards/elementset/gnd#`

The ontology documentation is published by DNB and is available in RDF/XML, Turtle, and N-Triples via the namespace URI.

### 4.2 Common prefixes

The following prefixes should be used in project queries unless there is a specific reason to diverge:

```sparql
PREFIX gndo: <https://d-nb.info/standards/elementset/gnd#>
PREFIX gnd:  <https://d-nb.info/gnd/>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
```

## 5. Resource identification and direct dereferencing

A known GND entity is identified by a persistent URI in the `d-nb.info` namespace.

### 5.1 Entity URI

Pattern:

```text
https://d-nb.info/gnd/{GND_ID}
```

Example:

```text
https://d-nb.info/gnd/118514768
```

Calling the entity URI causes an HTTP redirect to the corresponding description resource.

### 5.2 Description URI

Pattern:

```text
https://d-nb.info/gnd/{GND_ID}/about
```

This identifies the description of the entity.

### 5.3 Linked Data Service RDF description URI

Pattern:

```text
https://d-nb.info/gnd/{GND_ID}/about/lds
```

If called without an explicit serialization, DNB states that Turtle is delivered by default.

### 5.4 Content-negotiated and explicit serializations

DNB documents support for these RDF media types for GND entities:

- `application/rdf+xml`
- `text/turtle`
- `application/ld+json`

Explicit content URLs are also available:

- `https://d-nb.info/gnd/{GND_ID}/about/lds.rdf`
- `https://d-nb.info/gnd/{GND_ID}/about/lds.ttl`
- `https://d-nb.info/gnd/{GND_ID}/about/lds.jsonld`

These direct RDF access forms are useful for validation, debugging, and record-level inspection alongside SPARQL queries.

## 6. Calling the SPARQL endpoint

### 6.1 Endpoint selection

Use:

```text
https://sparql.dnb.de/api/gnd
```

for person authority data.

Use:

```text
https://sparql.dnb.de/api/dnbgnd
```

only if the query must join GND entities with DNB title data.

### 6.2 Standard request model

The service follows the **SPARQL 1.1 protocol**. Queries can therefore be sent as standard SPARQL requests with a `query` parameter over HTTP.

Example with `curl`:

```bash
curl -G 'https://sparql.dnb.de/api/gnd' \
  --data-urlencode 'query=
    PREFIX gndo: <https://d-nb.info/standards/elementset/gnd#>
    SELECT ?person ?name WHERE {
      VALUES ?person { <https://d-nb.info/gnd/118514768> }
      ?person gndo:preferredNameForThePerson ?name .
    }' \
  -H 'Accept: application/sparql-results+json'
```

### 6.3 Output formats

For `SELECT` queries, use one of:

- `application/sparql-results+json`
- `application/sparql-results+xml`
- `text/tab-separated-values`

For graph-producing queries such as `CONSTRUCT`, use:

- `application/n-triples`

## 7. Person modeling in the GND ontology

### 7.1 Person classes

The general person class in the ontology is:

```text
gndo:Person
```

DNB’s own SPARQL examples query persons by traversing subclasses of `gndo:Person` via `rdfs:subClassOf*`.

Example pattern from DNB’s example collection:

```sparql
?type rdfs:subClassOf* gndo:Person .
?subject a ?type .
```

This pattern shall be used whenever the implementation must include person subclasses rather than assuming one single concrete class only.

### 7.2 Important distinction for person properties

Many person-specific properties in the ontology have the domain **Differentiated person** rather than the abstract superclass `gndo:Person`. In practice, this means:

- broad candidate retrieval may start with `gndo:Person` plus subclasses,
- detailed biographical extraction often relies on properties documented for **Differentiated person**.

The implementation should therefore not assume that every property is attached uniformly to every abstract person-type node.

## 8. Core person properties to use

The following ontology terms are the primary access terms for person data in this project.

### 8.1 Canonical identifier

The canonical person identifier on the DNB side is the entity URI itself:

```text
https://d-nb.info/gnd/{GND_ID}
```

This URI shall be retained unchanged as the stable DNB/GND-side identifier in the integration layer.

### 8.2 Names

Preferred and alternative person names:

- `gndo:preferredNameForThePerson`
- `gndo:variantNameForThePerson`

These are literal-valued properties and should be the default fields for lexical matching, display, and candidate generation.

### 8.3 Structured name access

If structured name parts are needed, the preferred entry point is:

- `gndo:preferredNameEntityForThePerson`

This links the person to a `gndo:NameOfThePerson` node.

On that name node, the following structured components can be queried:

- `gndo:forename`
- `gndo:surname`
- `gndo:prefix`
- `gndo:personalName`
- `gndo:nameAddition`

This path should be used when explicit name-part extraction is required for matching or normalization.

### 8.4 Dates and activity period

Use the following temporal properties:

- `gndo:dateOfBirth`
- `gndo:dateOfDeath`
- `gndo:periodOfActivity`

These properties support temporal narrowing and disambiguation.

### 8.5 Occupation and ecclesiastical role cues

Use:

- `gndo:professionOrOccupation`
- `gndo:professionOrOccupationAsLiteral`

`gndo:professionOrOccupation` links to a GND subject-heading resource.  
`gndo:professionOrOccupationAsLiteral` provides a literal fallback for the same concept.

For this project, these properties are central for identifying ecclesiastical persons.

### 8.6 Geographic information

Use:

- `gndo:placeOfBirth`
- `gndo:placeOfBirthAsLiteral`
- `gndo:placeOfDeath`
- `gndo:placeOfDeathAsLiteral`
- `gndo:placeOfActivity`
- `gndo:geographicAreaCode`

Important: the non-literal place properties point to geographic entities, not to strings.

### 8.7 Additional disambiguation fields

Use where available:

- `gndo:biographicalOrHistoricalInformation`
- `gndo:gender`
- `gndo:oldAuthorityNumber`

## 9. Accessing linked values correctly

Several person properties do not directly contain strings, but links to other GND authority entities.

### 9.1 Occupation labels

When querying `gndo:professionOrOccupation`, the object is typically a subject-heading entity. To retrieve a human-readable label, query:

```sparql
gndo:preferredNameForTheSubjectHeading
```

on the linked occupation node.

### 9.2 Place labels

When querying `gndo:placeOfBirth`, `gndo:placeOfDeath`, or `gndo:placeOfActivity`, the object is typically a place/geographic entity. To retrieve a human-readable label, query:

```sparql
gndo:preferredNameForThePlaceOrGeographicName
```

on the linked place node.

## 10. Canonical query templates

### 10.1 Retrieve one known person by GND URI

```sparql
PREFIX gndo: <https://d-nb.info/standards/elementset/gnd#>

SELECT ?name ?birth ?death ?bio WHERE {
  VALUES ?person { <https://d-nb.info/gnd/118514768> }

  OPTIONAL { ?person gndo:preferredNameForThePerson ?name }
  OPTIONAL { ?person gndo:dateOfBirth ?birth }
  OPTIONAL { ?person gndo:dateOfDeath ?death }
  OPTIONAL { ?person gndo:biographicalOrHistoricalInformation ?bio }
}
```

### 10.2 Find persons by preferred or variant name

```sparql
PREFIX gndo: <https://d-nb.info/standards/elementset/gnd#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?person ?label WHERE {
  ?type rdfs:subClassOf* gndo:Person .
  ?person a ?type .
  ?person (gndo:preferredNameForThePerson | gndo:variantNameForThePerson) ?label .
  FILTER(CONTAINS(LCASE(STR(?label)), "franckenstein"))
}
ORDER BY ?label
```

### 10.3 Retrieve person data with readable occupation and place labels

```sparql
PREFIX gndo: <https://d-nb.info/standards/elementset/gnd#>

SELECT ?person ?name ?occupationLabel ?birthPlaceLabel ?deathPlaceLabel WHERE {
  ?person gndo:preferredNameForThePerson ?name .

  OPTIONAL {
    ?person gndo:professionOrOccupation ?occupation .
    ?occupation gndo:preferredNameForTheSubjectHeading ?occupationLabel .
  }

  OPTIONAL {
    ?person gndo:placeOfBirth ?birthPlace .
    ?birthPlace gndo:preferredNameForThePlaceOrGeographicName ?birthPlaceLabel .
  }

  OPTIONAL {
    ?person gndo:placeOfDeath ?deathPlace .
    ?deathPlace gndo:preferredNameForThePlaceOrGeographicName ?deathPlaceLabel .
  }
}
LIMIT 100
```

### 10.4 Retrieve structured name parts

```sparql
PREFIX gndo: <https://d-nb.info/standards/elementset/gnd#>

SELECT ?person ?forename ?surname ?prefix ?personalName ?nameAddition WHERE {
  ?person gndo:preferredNameEntityForThePerson ?nameNode .
  OPTIONAL { ?nameNode gndo:forename ?forename }
  OPTIONAL { ?nameNode gndo:surname ?surname }
  OPTIONAL { ?nameNode gndo:prefix ?prefix }
  OPTIONAL { ?nameNode gndo:personalName ?personalName }
  OPTIONAL { ?nameNode gndo:nameAddition ?nameAddition }
}
LIMIT 100
```

### 10.5 Retrieve ecclesiastical-person candidates

```sparql
PREFIX gndo: <https://d-nb.info/standards/elementset/gnd#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?person ?name ?birth ?death ?activity ?occLabel WHERE {
  ?type rdfs:subClassOf* gndo:Person .
  ?person a ?type ;
          gndo:preferredNameForThePerson ?name .

  OPTIONAL { ?person gndo:dateOfBirth ?birth }
  OPTIONAL { ?person gndo:dateOfDeath ?death }
  OPTIONAL { ?person gndo:periodOfActivity ?activity }

  OPTIONAL {
    ?person gndo:professionOrOccupation ?occ .
    ?occ gndo:preferredNameForTheSubjectHeading ?occLabel .
  }

  FILTER(
    !BOUND(?occLabel) ||
    REGEX(LCASE(STR(?occLabel)), "bischof|abt|kanoniker|domherr|geistlich|propst")
  )
}
LIMIT 500
```

This is a project-specific starter query. The ecclesiastical occupation vocabulary must still be tuned empirically during data profiling.

## 11. Minimal extraction profile for integration

For each DNB person selected into the project’s working set, the following fields should be extracted when available:

- person URI (`https://d-nb.info/gnd/{GND_ID}`)
- preferred name
- variant names
- structured name parts
- date of birth
- date of death
- period of activity
- profession/occupation URI
- profession/occupation label
- profession/occupation literal
- place of birth URI and label
- place of death URI and label
- place of activity URI and label
- geographic area code
- gender
- biographical or historical information
- old authority number

## 12. Recommended usage rules for this project

1. **Use the GND-only endpoint by default.**  
   The combined DNB+GND endpoint should only be used when title data is explicitly needed.

2. **Treat the GND URI as the canonical DNB-side identifier.**  
   Do not replace it with a locally invented identifier.

3. **Use literal name properties for matching first.**  
   Use the structured name-entity path only when name-part splitting is needed.

4. **Resolve linked objects to labels explicitly.**  
   Do not treat linked occupation or place URIs as final display values.

5. **Use subclass-aware person retrieval.**  
   Prefer the `rdfs:subClassOf* gndo:Person` pattern for broad person selection.

6. **Cache extracted result sets locally for reproducibility.**  
   The DNB service is officially marked as beta and updated monthly.

## 13. References

- DNB SPARQL Service (BETA): `https://wiki.dnb.de/spaces/LINKEDDATASERVICE/pages/449878933/DNB+SPARQL+Service+BETA`
- DNB SPARQL example collection: `https://wiki.dnb.de/spaces/LINKEDDATASERVICE/pages/480810660/Sammlung+SPARQL+Anfragen`
- GND Ontology: `https://d-nb.info/standards/elementset/gnd`
- Linked Data Service direct access: `https://www.dnb.de/EN/Professionell/Metadatendienste/Datenbezug/LDS/ldsZugriff.html`
- RDF vocabularies overview: `https://www.dnb.de/EN/Professionell/Metadatendienste/Exportformate/RDF-Vokabulare/rdf.html`
