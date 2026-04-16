# Information Integration Project

For the lecture Information Integration by Birgitta König-Ries at Friedrich-Schiller-Universität.

## Overview

A project with a methodological focus in the field of Historical Research / Digital Humanities (HisQu/DH) is being prepared in 
collaboration with Patrick Stahl. The project is intended to explore the integration, comparison, and possible linkage of historical 
person data drawn from multiple scholarly sources.

## Project Goal

The project is intended to support the methodological investigation of historical person data across multiple 
digital resources. A focus is expected to be placed on:

- entity extraction,
- normalization of person names and related metadata,
- comparison of attributes across sources, and
- possible record linkage between datasets.

## Selected Data Sources

The following data sources have been selected for the project:

| Name                            | URL                                          | Format          | # Entities                                                                                                                                     | # Attributes | Attribute List                                                                                                                                          |
|---------------------------------|----------------------------------------------|-----------------|------------------------------------------------------------------------------------------------------------------------------------------------|--------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| Germania Sacra Personenregister | https://personendatenbank.germania-sacra.de/ | JSON, XML, RDF  | 83,134                                                                                                                                         | >10          | First name, name prefix, family name, source/reference data, GND number, WIAG ID, Wikidata ID, offices/positions (designation, type, institution, etc.) |
| Deutsche Nationalbibliothek     | https://www.dnb.de/                          | Relational, RDF | 145,112 persons between 1200 and 1600; the dataset can be narrowed further because only ecclesiastical representatives are considered relevant | >6           | Person, alternative names, time, country, geographic reference, profession(s), additional information, type, etc.                                       |
| Repertorium Germanicum Online   | https://rg-online.dhi-roma.it/               | XML             | Approx. 400,000 persons in the full RG; only Volume 5 is used                                                                   | 3            | The source is principally provided as running text, but first name, surname, and mentioned place are to be extracted                                    |

## Short Summary

### Integration
We integrated the three data sources with the aim to make the information from all of them available using one vocabulary (as of now). 
For this, we materialized all three data sources using the GND-Ontology (GNDO), except for the aspects that cannot be accurately described with it, i.e.
statements about the Repertorium Germanicum (RG). 

The goal is to merge information about persons, e.g. preferred names, variants of their names, dates of activity etc. It was decided to keep the IRIs of each data source, e.g. `rg:101..5` and `gnd:45...X` and connect them with `owl:sameAs` if we find a match. Also, everything that we found could be mapped to the GNDO was materialized in the target graph using SPARQL construct queries, and the original vocabularies were stripped, e.g. the Germania Sacra (GS) used `foaf:`,`schema:`. However, these mapping decisions are stored in an ontology file (in the form of `sameAs` assertions) and available to the Fuseki server.

The data from the Repertorium Germanicum (RG) was in XML format, and we had to create a vocabulary for it. This vocabulary uses the same terminology and structure as the original XML. A thorough documentation from the authors of this source is not available, but we asked them and documented our insights. The source itself is also not publicly available, but we can make it available if that is necessary.

The project in its current state does not make use of the existing identification provided by the GS to the GND. **Only persons are matched.** Future work should also match mentioned institutions, which however was out-of-scope for this milestone.

**Why are the RG fragments not mapped to the GNDO?** The RG is a collection of summaries (sg. Regest, pl. Regeste) of original charters, grouped by popes 
(i.e. their time of reign). These summaries contain information about persons performing legal actions at a specific point of time, e.g. claiming a benefice 
(ecclesiastical office), and they are also called "lemma" (there should be one lemma for each person), consisting of "sublemmas" (or also called subentries), 
referring to  a specific event in the lifetime of this person during the reign of this pope. This can be represented using the GNDO (see below, can be 
analogously done for a Regest). However, after discussion with experts in this field (mediavistic historians), we decided to postpone this step, as 
`gndo:Work` did not seem to be an appropriate term to be presented to the user (although it is a work, by someone who subsumed all charters to a person 
in a Regest). In future work, we will examine whether to use `rgo:Regest` as a subclass of `gndo:Work` and then also the rest of the GNDO.

Further information on specifications about the original sources can be found in `docs/{dnb,gs,rg}/technical-specs.md`.

```ttl
@prefix gndo: <https://d-nb.info/standards/elementset/gnd#> .
@prefix ex:   <https://example.org/charter/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

# ── The main charter as a physical manuscript ──────────────────────────────
ex:charter1 a gndo:Manuscript ;
    gndo:preferredNameForTheWork "Stadtrechtsurkunde von Musterburg" ;
    gndo:dateOfProduction "1347"^^xsd:gYear ;
    gndo:narrowerTermPartitive ex:part1 , ex:part2 , ex:part3 .

# ── Preamble ────────────────────────────────────────────────────────
ex:part1 a gndo:Work ;
    gndo:preferredNameForTheWork "Präambel" ;
    gndo:broaderTermPartitive ex:charter1 ;
    gndo:contributingPerson ex:person_heinrich .

# ── Land grant clause ───────────────────────────────────────────────
ex:part2 a gndo:Work ;
    gndo:preferredNameForTheWork "Landverleihungsklausel" ;
    gndo:broaderTermPartitive ex:charter1 ;
    gndo:contributingPerson ex:person_heinrich , ex:person_margarethe .

# ── Witness list ────────────────────────────────────────────────────
ex:part3 a gndo:Work ;
    gndo:preferredNameForTheWork "Zeugenliste" ;
    gndo:broaderTermPartitive ex:charter1 ;
    gndo:contributingPerson ex:person_konrad .

# ── Persons referenced in the document ─────────────────────────────────────
ex:person_heinrich a gndo:DifferentiatedPerson ;
    gndo:preferredNameForThePerson "Heinrich von Musterburg" ;
    gndo:dateOfBirth "1310"^^xsd:gYear ;
    gndo:dateOfDeath "1372"^^xsd:gYear .

ex:person_margarethe a gndo:DifferentiatedPerson ;
    gndo:preferredNameForThePerson "Margarethe von Stein" .

ex:person_konrad a gndo:DifferentiatedPerson ;
    gndo:preferredNameForThePerson "Konrad der Ältere" .
```

### Matching/NEI
The document [0007-matching-rules.md](docs/decisions/0007-matching-rules.md) describes how the identification works. `just match` runs the matching.

### Evaluation
We evaluated
- the integrated data → with competency questions, see [cqs.md](docs/cqs.md)
- the matching results → evaluate with known TP (GS-to-GND-pointers) [readme.md](src/matching/readme.md)
- the matching rules → with the "waterfall"-explanation, see [waterfall.html](waterfall.html)


## Scope

At this stage, the project scope has been defined through the selection of three candidate datasets that appear suitable for 
methodological comparison. A shared thematic focus on historical persons, especially in ecclesiastical contexts, has been identified 
across the sources.

It is expected that the selected resources will provide sufficient material for:

1. the extraction of comparable person-related entities,
2. the identification of overlapping or potentially matching records, and
3. the testing of DH-oriented matching and reconciliation methods.

## Repository Purpose

This repository is intended to be used for:

- documenting the dataset selection process,
- recording assumptions and methodological decisions,
- storing scripts and transformation workflows,
- tracking extraction and matching experiments, and
- presenting project results in a transparent and reproducible way.

## Prerequisites

- Docker
- Python3 + uv

## Pipeline Steps

The current pipeline is implemented via `just` recipes:

1. **Environment and tests**  
   `just sync` and `just test`

2. **Data acquisition**  
   `just fetch` (runs `gndo-doc-fetch`, `gs-fetch`, `rgo-fetch`, `dnb-fetch`)  
   `rgo-fetch` downloads `rg5.xml` from the configured RG repository and ref.  
   Note: export `GITHUB_TOKEN` before running `just rgo-fetch` or `just fetch`.

3. **Build reduced datasets**  
   `just reduce` creates `cohort.ttl` for each source using year-based filtering:
   - include a person if birth year is in [1361, 1447] — the RG5 start year minus 70 years and the RG5 end year
   - if birth year is missing, include if death year is in [1431, 1497] — the RG5 start year and the RG5 end year plus 50 years
   - for fuzzy date values, the first 4-digit year in the lexical form is used  
   `just extract-examples` creates `example.ttl` for each source with the four cross-source example persons present in all three data sources.

4. **Choose active input variant**  
   `just use-full`, `just use-cohort`, or `just use-example` copies the selected variant to `statements.ttl`.

5. **Clean GS source graph**  
   `just clean` (currently `gs-clean`) generates `data/raw/gs/clean.ttl`.

6. **Harmonize to GNDO**  
   `just harmonize` runs ROBOT mappings and writes merged output to `data/harmonized/statements.ttl`.

7. **Export per-person harmonized examples**  
   `just examples-export` writes person files to `data/examples/harmonized/`.  
   Use `just examples-export --mode neighborhood` to reproduce the previous broad export behavior.

8. **Index and query services**  
   `just qlever` and `just ui`.

9. **Build matching context table**  
   `just match-context` runs `src/matching/fetch_context.py` and creates:
   - `data/tabular/common_profiles.csv`
   - `data/tabular/common_profiles.pkl`

10. **Run entity matching**  
   `just match-run` runs `src/matching/main_match.py` on `common_profiles.pkl` and writes:
   - `data/matching_outputs/predictions_pairs.csv`

Convenience command for both steps in the correct order:

```bash
just match
```

The default end-to-end command currently runs the reduced-example workflow:

```bash
just go
```

## Tech Stack Specification

The currently used core technologies are:

- **ROBOT** for SPARQL CONSTRUCT-based cleaning, reduction, and harmonization.
- **Python + uv** for source-specific fetch and transformation scripts.
- **Fuseki** for SPARQL queries and reasoning.

## Namespace Prefixes

Project mappings use the following preferred prefixes:

- `gsn: <https://personendatenbank.germania-sacra.de/index/gsn/>`
- `rgo: <https://rg-online.dhi-roma.it/ontology/>`
- `rg: <https://rg-online.dhi-roma.it/rg/>`
- `gndo: <https://d-nb.info/standards/elementset/gnd#>`
- `gnd: <https://d-nb.info/gnd/>`

## Set up for production use

### Software Requirements
- Docker
- Python3 + uv

## Data Variants and Switching

Each source directory under `data/raw/` now supports three files:

- `full.ttl`: complete source snapshot (written by the fetcher)
- `cohort.ttl`: year-filtered subset written by `just reduce`
- `example.ttl`: four cross-source example persons written by `just extract-examples`
- `statements.ttl`: active file used by the rest of the pipeline

This keeps downstream steps agnostic: they always read `statements.ttl`.

### Build reduced datasets

Run all reducers:

```bash
just reduce
```

Or per source:

```bash
just gs-reduce
just dnb-reduce
just rgo-reduce
```

### Switch active pipeline input

Use full data:

```bash
just use-full
```

Use cohort-filtered data:

```bash
just use-cohort
```

Use four-person examples:

```bash
just use-example
```

## Matching Workflow

The current matching workflow is implemented with Splink in two explicit steps:

1. Build context table from RDF source snapshots:

```bash
just match-context
```

2. Run pairwise matching on the generated context table:

```bash
just match-run
```

Or run both in one command:

```bash
just match
```


## Maybe?

Erfurter Matrikel
https://digital.slub-dresden.de/werkansicht/dlf/62603/1
