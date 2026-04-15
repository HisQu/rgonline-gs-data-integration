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
| Repertorium Germanicum Online   | https://rg-online.dhi-roma.it/               | XML             | Approx. 400,000 persons in the full RG; only Volume 8 is intended to be used                                                                   | 3            | The source is principally provided as running text, but first name, surname, and mentioned place are to be extracted                                    |

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

### Install the QLever Triplestore
If you want to be able to query the data with a fast SPARQL interface, you can set up a local QLever instance. You can 
also use ROBOT for this purpose, which is also used in this pipeline and available as a Docker image. 

Consult the documentation for instructions on your platform: https://docs.qlever.dev/quickstart/#debian-and-ubuntu.

You can install QLever on Debian/Ubuntu from a precompiled package:
```bash
sudo apt update && sudo apt install -y wget gpg ca-certificates
wget -qO - https://packages.qlever.dev/pub.asc | gpg --dearmor | sudo tee /usr/share/keyrings/qlever.gpg > /dev/null
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/qlever.gpg] https://packages.qlever.dev/ $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") main" | sudo tee /etc/apt/sources.list.d/qlever.list
sudo apt update
sudo apt install qlever
```

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

- **ROBOT (via Docker)** for SPARQL CONSTRUCT-based cleaning, reduction, and harmonization.
- **Python + uv** for source-specific fetch and transformation scripts.
- **QLever** for indexing and SPARQL querying.
- **LIMES** (`under development`) for future entity resolution.

## Namespace Prefixes

Project mappings use the following preferred prefixes:

- `gsn: <https://personendatenbank.germania-sacra.de/index/gsn/>`
- `rgo: <https://example.org/ontology/>`
- `rg: <https://example.org/rg/>`
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
