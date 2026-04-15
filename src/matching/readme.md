# Matching Workflow (DNB, GS, RGO)

This module builds source-specific person profiles from RDF, harmonizes them into one shared schema, and performs probabilistic record linkage with Splink (DuckDB backend).

Main orchestration files:
- `src/matching/fetch_context.py`: extract and unify context from DNB, GS, and RGO
- `src/matching/main_match.py`: normalize, compare, train, and predict matches
- `src/matching/comparisons/`: custom comparison definitions
- `src/matching/utils/`: normalization and SQL helper utilities

## 1) What Is Extracted From Each Source

The extraction target schema (in `fetch_context.py`) contains one row per source-specific person profile:
- `entity_id`, `source`
- `preferred_name`, `variant_names`
- `birth_year`, `death_year`
- `activity_start`, `activity_end`
- `mention_start`, `mention_end`
- `places`
- `gnd_id`, `wikidata_id`

### DNB

From DNB person and place RDF:
- Preferred name from `gndo:preferredNameForThePerson`
- Variant names from `gndo:variantNameForThePerson`
- Birth/death year from corresponding GND date predicates
- Places from `placeOfActivity`, `placeOfBirth`, `placeOfDeath` (resolved to labels)
- `gnd_id` from `gndo:gndIdentifier` or URI fallback
- `wikidata_id` from `owl:sameAs` when present

DNB rows do not carry mention intervals (`mention_start`/`mention_end` stay empty).

### GS

From GS RDF person nodes:
- Preferred name composed from `schema:givenName` + `schema:familyName`
- Variant names currently left empty (no reliable variant-name property used)
- Birth/death year from `schema:birthDate` and `schema:deathDate` when available
- Activity interval from all held offices (`part:holder_of`, then min start / max end)
- `gnd_id` from `owl:sameAs` links to DNB
- Places inferred from organization labels attached through `org:memberOf`

GS place extraction uses configurable heuristics from `data/name_normalization_config.json`:
- `gs_org_place_prefixes`
- `gs_org_place_locative_markers`
- `gs_org_place_non_place_starters`

Heuristic order to derive place candidates from org labels:
1. Rightmost comma segment
2. Locative marker pattern (for example `in`, `zu`, `bei`, `an der`)
3. Institution-prefix stripping (for example `Domstift`, `Kloster`, ...)
4. Fallback to last token

### RGO

From RGO person resources:
- Preferred name and variant names via GNDO person-name predicates
- Mention interval (`mention_start`, `mention_end`) from aggregated `rgo:dateValue` across lemma/subentry context
- Places from lemma `rgo:mentionsPlace` relations (label-based)

RGO context aggregation follows both direct and inverse paths:
- `person -> rgo:appearsInLemma -> lemma`
- `lemma -> rgo:mentionsPerson -> person`
- lemma/subentry relations in both directions


## 2) Normalization Prior to Matching

In `main_match.py`, normalization is applied in two stages:
- `prepare_name_columns_for_matching(...)`
- `prepare_place_columns_for_matching(...)`

### Name normalization

Config keys used from `data/name_normalization_config.json`:
- `remove_particles`
- `first_name_equivalents`

Helper columns produced:
- `preferred_name_norm`
- `preferred_name_tokens`
- `preferred_first_token`, `preferred_last_token`
- `variant_names_norm`
- `variant_name_tokens`
- `all_name_tokens` (union of preferred and variant tokens)

This is where Latin/German first-name equivalents (for example `henricus -> heinrich`) are harmonized.

### Place normalization

Config keys used from `data/name_normalization_config.json`:
- `place_equivalents`
- `place_remove_particles`
- `place_remove_context_tokens`

Helper columns produced:
- `places_norm`
- `place_tokens`

The heuristic first-name and place normalization rules were initially created from a lightweight exploratory skim of source labels/names using [extract_common_names.py](../rgo/extract_common_names.py) and [extract_place_prefixes.py](../gs/extract_place_prefixes.py), then iteratively refined during matching experiments. This reduces orthographic noise and strips context tokens so place evidence can be compared more robustly.

## 3) What Is Compared

Comparison features are assembled in `main_match.py` from `comparisons/`.

### Name comparisons

1. Preferred vs preferred
- Jaro-Winkler on `preferred_name_norm`
- Thresholds: `0.97`, `0.92`, `0.88`

2. Preferred vs variant (best symmetric)
- Custom SQL computes best Jaro-Winkler between preferred on one side and variant list on the other, in both directions, then takes the max
- Thresholds: `0.95`, `0.80`, `0.60`

3. Variant vs variant (best pair)
- Pairwise best Jaro-Winkler across `variant_names_norm` arrays
- Thresholds: `0.95`, `0.80`, `0.60`

### Date comparisons

1. Death compatibility (source-aware)
- DNB-GS: absolute death-year differences
- RGO-other: RGO mention range versus other-side death year with allowance (default `5` years)

2. Birth compatibility (source-aware)
- DNB-GS: absolute birth-year differences
- RGO-other: RGO mention range versus other-side birth year with allowance (default `5` years)

3. Activity overlap (effective intervals)
- RGO uses mention interval
- GS prefers activity interval, falls back to life dates
- DNB uses life dates
- Levels distinguish strong/moderate/weak overlap, close no-overlap, far no-overlap, and missing evidence

Date helper SQL lives in `utils/date_utils.py`.

### Place comparisons

1. Place match quality
- One combined custom comparison on `places_norm`
- Level order:
  - exact normalized place match (`halle` vs. `halle`)
  - containment match between normalized place pairs (`magdeburg` vs. `kloster magdeburg`)
  - best pairwise Jaro-Winkler >= `0.97`
  - best pairwise Jaro-Winkler >= `0.90`
  - else
- Missing place evidence is handled explicitly as a null level

2. Place token overlap
- Array intersection size on `places_norm`
- Thresholds: `4`, `3`

Place helper SQL lives in `utils/place_utils.py`.

## 4) How the Model Is Trained and Used

The matching run is orchestrated in `main_match.py`.

### Link mode and source split

- Splink runs in `link_only` mode (no within-source deduplication)
- Input is split into three tables (`dnb`, `gs`, `rgo`)
- Predictions are therefore only cross-source pairs

### Blocking for prediction

Conservative blocking rules used for full prediction:
- `preferred_first_token` + `preferred_last_token`
- `preferred_first_token` + `death_year`

### Parameter estimation

Training attempts three steps:
1. Prior estimate from deterministic rule (`preferred_name_norm` equality)
2. `u` estimation via random sampling
3. Multiple EM sessions with rotating blocks:
	- `preferred_first_token`
	- `preferred_last_token`
	- `birth_year`
	- `death_year`

Rationale: a comparison feature cannot be estimated in an EM run if that same feature is used to block that run, so multiple EM rounds improve parameter coverage.

### Inference and output

- Pair prediction uses `threshold_match_probability` (default `0.5` in workflow function)
- Outputs include `match_probability` and `match_weight` plus retained profile/context columns
- Results are sorted descending by score
- Top pairs are exported to `data/matching_outputs/predictions_pairs.csv`
- A waterfall chart can be generated for inspection (`waterfall.html`)

## 5) Summary

The current matcher combines:
- Name similarity (preferred/variant and token overlap)
- Temporal plausibility (birth/death/activity/mention intervals)
- Place compatibility (string similarity, token overlap, containment signal)

It is explicitly source-aware:
- DNB and GS contribute stronger life/activity metadata
- RGO contributes mention-time and contextual place evidence
- Date logic adapts by source pair instead of applying one rigid rule to all records


# Evaluation

A minimal evaluation, is based upon comparing the predicted matching pairs to existing GS-DNB links via their shared `gnd_id` values. Some GS profiles already contain a `gnd_id` that points to the corresponding DNB person. These identifiers are used as external evidence for known true matches.

A reference pair is defined as:
- one GS row with non-empty `gnd_id`
- one DNB row with the same `gnd_id`

If a `gnd_id` occurs multiple times on either side, all resulting GS-DNB pairings are included as reference pairs.

## What is compared
The [evaluation script](./evaluate_matches.py) iterates through the tabular entity data and extracts all GS-DNB pairs via the shared `gnd_id`. It then checks which of those pairs are present in the predicted matches dataframe and distinguishes missed pairs by cause.

## Miss categories
Missed reference pairs are split into two groups:

- `failed_prediction_blocking`  
  The pair would not satisfy any of the prediction blocking rules and therefore could never appear in the exported matches.

- `passed_blocking_but_below_threshold`  
  The pair is compatible with at least one prediction blocking rule, but still does not appear in the exported thresholded matches.

## Current results
Evaluation summary:
- prediction file: `data/matching_outputs/predictions_pairs.pkl`
- GS rows with `gnd_id`: 842
- DNB rows with `gnd_id`: 9302
- reference positive pairs total: 530
- reference pairs found by Splink: 177
- reference pairs missed by Splink: 353
- recall on all reference pairs: 0.3340
- missed due to prediction blocking: 183
- missed despite passing blocking: 170

Expressed as formulas:

- raw recall:
  - `177 / 530 = 0.33396`
- recall after excluding pairs that are impossible under the current blocking rules:
  - `177 / (530 - 183) = 177 / 347 = 0.51009`

## Interpretation
These numbers should be interpreted as a minimal recall-oriented evaluation on a restricted GS-DNB subset with existing identifier evidence. They do not measure any precision-oriented metric. They also do not account for pairs without an existing `gnd_id`, namely all RGO records and some GS records. The results are nevertheless useful because they show how much loss is already caused by blocking and how much additional loss occurs later during probabilistic scoring and thresholding.