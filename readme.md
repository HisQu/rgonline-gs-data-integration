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

## Scope and Assumptions

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
