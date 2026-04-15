# Entity matching across different historical sources
This document should outline how entities inside one source and across multiple ones can be matched using the Python tool [Splink](link). Inside the three corpora there are three overlapping features that are compared based on different rules.

## Name Matching

Name matching is based on a small lexical feature set derived from normalized preferred names and name variants.

Since the three sources differ strongly in how they encode names, all preferred names and variant names are first transformed into comparable normalized forms. The current preprocessing steps are:

- normalize case and whitespace
- remove punctuation and brackets
- remove configured particles
- map configured Latin/German first-name equivalents
- tokenize preferred names and variant names

This is intended to reduce superficial variation while preserving the core lexical name evidence needed for record linkage.

The active name comparison block currently uses the following features:

- `preferred_name_similarity`  
  comparison of the normalized preferred name of entity A with the normalized preferred name of entity B. This comparison includes:
  - exact normalized match with term-frequency adjustment
  - Jaro-Winkler similarity thresholds at `0.97`, `0.92`, and `0.88`

- `preferred_variant_best_similarity`  
  best symmetric lexical similarity between the preferred name of one entity and any variant name of the other entity. The current comparison uses custom SQL and Jaro-Winkler thresholds at `0.97`, `0.92`, and `0.88`

- `variant_variant_best_similarity`  
  best lexical similarity between any normalized variant name of entity A and any normalized variant name of entity B. This comparison uses pairwise Jaro-Winkler thresholds at `0.95`, `0.80`, and `0.60`

A previously tested global token-overlap feature over all preferred and variant-name tokens, `all_name_token_overlap`, is currently not part of the active model. In practice, it proved to be highly correlated with the preferred/variant similarity features and could therefore lead to unstable or counterintuitive learned weights.

Taken together, the active name features are intended to capture the most common matching situations:
- direct preferred-name similarity
- cross-matches between preferred and variant forms
- cases where matching evidence is only visible in variant-name material

Additional name-based features such as separate given-name similarity, byname similarity, or explicit Roman-numeral handling remain possible extensions, but are not part of the current matcher.


## Date Matching

The three sources do not provide the same type of temporal information: DNB provides life dates, GS provides life dates and/or periods of activity, whereas RGO provides mention dates derived from regest contexts. For this reason, temporal comparison is based on source-aware compatibility rules and effective intervals rather than raw string comparison.

The preprocessing steps derive year-based temporal features as follows:

- normalize all available date values to comparable year representations
- derive `birth_year` where available
- derive `death_year` where available
- derive `activity_start` and `activity_end` where available
- derive `mention_start` and `mention_end` from aggregated RGO mention dates

For RGO, all observed mention dates are aggregated into a mention interval:
- `mention_start` = earliest observed mention
- `mention_end` = latest observed mention

For interval-based comparison, an effective temporal interval is constructed per source side:
- RGO uses the mention interval
- GS prefers the activity interval and falls back to life-date evidence where needed
- DNB uses life dates

The active date comparison block uses the following features:

### `death_dnb_gs`

This comparison applies only to DNB-GS pairs and directly compares death years.

Current levels:
- death years equal
- absolute death-year difference `\leq 1`
- absolute death-year difference `\leq 5`
- absolute death-year difference `> 5`
- irrelevant or missing death evidence

### `death_rgo_other`

This comparison applies only to RGO-DNB and RGO-GS pairs and interprets the RGO mention range against the other side's death year, with an allowance of `5` years.

Current levels:
- mention end `\leq` death year
- mention end `\leq` death year `+ 5`
- mention range crosses death year `+ 5`
- mention start `>` death year `+ 5`
- irrelevant or missing death evidence

### `birth_dnb_gs`

This comparison applies only to DNB-GS pairs and directly compares birth years.

Current levels:
- birth years equal
- absolute birth-year difference `\leq 3`
- absolute birth-year difference `\leq 10`
- absolute birth-year difference `> 10`
- irrelevant or missing birth evidence

### `birth_rgo_other`

This comparison applies only to RGO-DNB and RGO-GS pairs and compares the RGO mention range against the other side's birth year.

The current logic distinguishes whether the first observed mention occurs plausibly after birth, or implausibly before it. The active parameters are:
- allowance before birth: `5` years
- minimum age at first mention: `12` years

Current levels:
- first mention `\geq` birth year `+ 12`
- first mention `\geq` birth year
- mention range crosses birth year `- 5`
- mention end `<` birth year `- 5`
- irrelevant or missing birth evidence

### `activity_overlap`

This feature compares the effective temporal interval of one source with that of the other source. It is not split into separate DNB-GS and RGO-other variants; instead, it uses the source-specific effective intervals described above.

The current implementation distinguishes:
- strong interval overlap
- moderate interval overlap
- small interval overlap
- no overlap, but temporally close
- no overlap and temporally distant
- missing interval evidence

In the active matcher, the parameters are:
- strong overlap: at least `5` years
- moderate overlap: at least `3` years
- small overlap: at least `1` year
- close distance without overlap: at most `5` years

Taken together, these date-based features provide graded temporal evidence for matching. They distinguish exact agreement, approximate agreement, plausible compatibility, and clear incompatibility while remaining sensitive to the fact that DNB, GS, and RGO encode different kinds of temporal information.


## Place Matching

Place information is treated as contextual compatibility evidence derived from all place-related values associated with a person. Since all three sources may contain multiple place references, place comparison is based on aggregated normalized place values rather than a single raw literal.

The place preprocessing steps include:
- normalize case and whitespace
- remove punctuation and brackets
- normalize configured place variants
- remove configured place particles and context tokens

The active place comparison block currently uses two features:

- `place_match_quality`  
  one combined custom comparison over `places_norm`, with the following level order:
  - exact normalized place match
  - containment match between normalized place pairs
  - best pairwise Jaro-Winkler similarity `\geq 0.97`
  - best pairwise Jaro-Winkler similarity `\geq 0.90`
  - else
  - missing place evidence is handled explicitly as a null level

- `place_token_overlap`  
  overlap size over the aggregated normalized place values in `places_norm`, using array-intersection thresholds at `4` and `3`

The combined `place_match_quality` feature is intended to capture different kinds of strong local agreement:
- exact shared place labels
- cases where one normalized place form is contained in another
- very high or medium lexical similarity between the best-matching place pair

Together with the overlap feature, this allows the matcher to capture both strong single-place agreement and broader contextual compatibility across multiple place references. Further details on the implementation of all comparisons can be seen [here](../../src/matching/readme.md)