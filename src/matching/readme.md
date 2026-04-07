# README – Splink-based matching workflow for historical person profiles

## Overview

This project implements a stepwise matching workflow for historical person profiles from three different sources:

- DNB
- Germania Sacra (GS)
- RG Online (RGO)

The three sources provide different types of evidence:
- DNB mainly contains normalized person information, life dates, and in some cases place references
- GS contains life dates as well as activity/office periods
- RGO mainly contains mention periods and place-related contexts derived from lemma and sublemma relations

The goal is to identify the same entities despite these differences. For this purpose, the system uses Splink and organizes the comparison logic into three thematic blocks:

- Name Matching
- Date Matching
- Place Matching

Each block defines its own comparisons, which can be integrated modularly into the main script.
---

## Project idea

The workflow is based on a shared, already prepared DataFrame in which each row represents exactly one source entity. This common profile format includes, among other things:

- $$entity_id$$
- $$source$$
- $$preferred_name$$
- $$variant_names$$
- $$birth_year$$
- $$death_year$$
- $$activity_start$$
- $$activity_end$$
- $$mention_start$$
- $$mention_end$$
- $$places$$
- $$gnd_id$$
- $$wikidata_id$$

Additional helper columns are derived from this structure specifically for matching purposes, for example normalized name or place forms.

---

## Core architecture

The matching logic is split across several files so that preprocessing, comparison definitions, and execution remain clearly separated.

### Main script: $$main_match$$

The main script is the central orchestration layer of the Splink workflow. It is designed so that new comparisons can be added easily or existing ones changed without rebuilding the overall structure.

Typical tasks of $$main_match$$ are:

1. Load prepared profile data
2. Create helper columns for matching
3. Build a Splink linker with configurable comparisons
4. Define blocking rules
5. Train the model
6. Calculate pairwise scores and match probabilities

---

## Comparison blocks

The actual domain-specific modeling is structured into three major blocks:

- Name
- Date
- Place

Each block is modular and defines its own comparisons. This makes it possible to add features step by step and test them in isolation.

---

## 1. Name Matching

The name comparisons form the first and most fundamental matching block.

### Preprocessing

For names, helper columns are generated from $$preferred_name$$ and $$variant_names$$. The normalization is deliberately kept controlled and transparent.

This includes:

- lowercasing
- whitespace normalization
- removing punctuation and brackets
- small token-wise equivalence lists for first names
- tokenization of preferred and variant names

Examples of such normalizations are:

- $$Henricus$$ → $$heinrich$$
- $$Gerardus$$ → $$gerhard$$
- $$Fridericus$$ → $$friedrich$$
- $$Theodericus$$ → $$dietrich$$

### Name comparisons

Several comparisons are planned or already implemented in the name block:

- $$preferred\_preferred\_similarity$$  
  comparison of the normalized preferred name on both sides, initially via Jaro-Winkler

- $$preferred\_variant\_best\_similarity$$  
  comparison of the preferred name on one side with the variants on the other side; modeled symmetrically

- $$variant\_variant\_best\_similarity$$  
  best comparison between two variant lists

- $$all\_name\_token\_overlap$$  
  overlap across aggregated name tokens

The name comparisons are designed to capture different aspects of name similarity:
- direct main-name comparison
- main name against alternative name forms
- variant lists against each other
- global token context

---

## 2. Date Matching

The date block does not compare raw date strings, but models temporal compatibility.

This is necessary because the three sources provide different types of temporal information:

- DNB: mostly life dates
- GS: life dates and/or activity dates
- RGO: mention periods

### Basic idea

Temporal comparison is modeled as compatibility rather than lexical equality.

This means:
- exact years can be compared directly
- intervals are compared by overlap, distance, or plausibility
- RGO mention ranges are checked against life-date or activity evidence from the other sources

### Date comparisons

#### $$death\_compatibility$$

This comparison is source-aware, but intentionally modeled as a shared feature because both branches express the same domain question:

**Is the pair temporally compatible with respect to a death point?**

- DNB vs GS: direct comparison of death years by year difference
- RGO vs DNB/GS: comparison of $$mention\_start$$ / $$mention\_end$$ against $$death\_year$$ with a configurable allowance

#### $$birth\_compatibility$$

Analogous to $$death\_compatibility$$, but referring to birth:

- DNB vs GS: direct comparison of birth years
- RGO vs DNB/GS: comparison of earliest/latest mentions against $$birth\_year$$ with allowance

#### $$activity\_overlap$$

Here, an effective temporal interval is first constructed for each side:

- RGO: mention range
- GS: preferred activity range, otherwise fallback to life dates
- DNB: life dates

These intervals are then compared, for example by:
- strong overlap
- weak overlap
- small distance without overlap
- large distance without overlap

This block is particularly important because it does not treat source differences as a problem, but as a modelable evidence structure.

---

## 3. Place Matching

Places are treated as contextual information rather than as one single canonical place ID. Each person can carry multiple place values, and depending on the source these originate from very different contexts.

### Origin of place information

- GS: place-related literals, usually in institutional or affiliative contexts
- DNB: geographic references and place-of-activity
- RGO: places derived from lemma and sublemma contexts

### Preprocessing

Place preprocessing follows the same general logic as for names, but is configured specifically for places.

This includes:

- lowercasing
- whitespace normalization
- removing punctuation and brackets
- token-wise normalization of orthographic variants
- removal of place-specific particles
- removal of frequent contextual and institutional tokens

Examples of removable contextual vocabulary include:

- $$dioc$$
- $$eccl$$
- $$stift$$
- $$kloster$$
- $$domstift$$
- $$ep$$
- $$aep$$

This decision is deliberately pragmatic: for matching purposes, a slightly over-generalized place core is often more useful than an overly specific institutional form.

### Place comparisons

#### $$place\_best\_similarity$$

Compares the best place pair between two place lists.
The implementation is based on pairwise string comparison between elements of two arrays.

This feature captures:
- exact agreement of one place expression
- very high lexical similarity
- medium similarity
- otherwise non-similarity

#### $$place\_token\_overlap$$

Aggregates all normalized place tokens per entity and compares the overlap of the two token sets.

This feature captures the overall place context more than a single best place value.

#### $$place\_containment\_match$$

Checks containment-like relations between place expressions.
This is especially useful for cases such as:

- $$Bremen$$ vs $$Domstift Bremen$$
- $$Moers$$ vs $$de Moers$$
- $$Hoya$$ vs $$von Hoya$$

This comparison models:
- exact or containment-style matches
- partial/plausible core-place containment relations
- otherwise no containment evidence
- optional missing level, depending on the modeling decision

This feature complements the other two place features well because it is robust against different lengths and institutionally expanded forms.

---

## Summary

The project consists of a flexible Splink-based matching workflow with:

- a central main script for blocking, training, and inference
- separate utility files for preprocessing
- separate comparison files for Name, Date, and Place
- a modularly extensible structure for further matching features

The current modeling takes into account that historical sources provide different types of evidence. Instead of ignoring these differences, they are integrated into the matching process as distinct comparison logics.
