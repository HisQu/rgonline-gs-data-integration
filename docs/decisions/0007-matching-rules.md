# Entity matching across different historical sources
This document should outline how entities inside one source and across multiple ones can be matched using the Python tool [Splink](link). Inside the three corpora there are three overlapping features that are compared based on different rules.

## Name Matching
Name and byname matching will initially be handled through a reduced feature block focused on normalization, tokenization, and lexical comparison.

Since the three sources differ strongly in how they encode names, the matching process first transforms all preferred names and name
variants into comparable normalized forms and then derives a small set of lexical similarity features from them. Those preprocessing steps are:

- normalize case and whitespace
- remove punctuation and brackets
- separate role and title tokens from names where possible
- normalize common orthographic variants
- use small equivalence lists for common Latin/German first-name variants
- tokenize all preferred names and variant names

This is meant to reduce superficial differences while preserving the core person-related name evidence needed for later matching. Based on these representations, the name matching block uses the following comparison features:

- preferred_preferred_similarity
  comparison of the normalized preferred name of entity A with the normalized
  preferred name of entity B (i.e. GS preferred: ``Gerhard, von Hoya`` vs. DNB preferred: ``Gerhard Hoya``)

- preferred_variant_best_similarity
  best lexical similarity between the preferred name of one entity and any
  variant name of the other entity (i.e. GS preferred: ``Dietrich II. Moers`` vs. DNB variant: `Dietrich, von Moers`)

- variant_variant_best_similarity
  best lexical similarity between any variant name of entity A and any variant
  name of entity B (i.e. RGO variant: `de Moers` vs. DNB variant: `Dietrich, von Moers`)

- all_name_token_overlap
  token overlap over all preferred and variant names of both entities

These features are intended to capture the most common matching situations: direct preferred-name similarity, cross-matches between preferred and variant forms, similarity between variants only, and overlap in the overall set of name
tokens.

For Splink, these features will later be represented through several comparison
levels and the planned logic is approximately as follows:

- very high similarity / strong agreement
- medium similarity / plausible agreement
- weak similarity / low evidence
- no meaningful similarity

For token overlap, a comparable graded structure is intended, e.g.:

- strong token overlap
- partial token overlap
- little or no token overlap

Additional name-based features may later be introduced if needed. These are not part of the first implementation, but remain possible extensions:

- given_name_similarity
- byname_similarity
- roman_numeral_match

These additional features may become useful once the initial lexical feature set has been tested and if further precision is needed for more difficult historical cases.


## Date Matching
The three sources do not provide the same type of temporal information: DNB provides life dates, GS provides life dates and/or periods of activity, whereas RGO provides mention dates derived from regest contexts. For this reason, temporal comparison is based on interval compatibility and plausibility rather than direct string comparison.

The initial preprocessing steps are

- normalize all available date values to comparable year-based representations  
- derive birth year where available  
- derive death year where available  
- derive activity start and end years where available  
- derive mention start and end years from all RGO mention dates  

For RGO, all available mention dates are sorted and aggregated into a mention range:

- `mention_min` = earliest observed mention  
- `mention_max` = latest observed mention  

For GS and DNB, a preferred temporal profile is constructed before comparison:

- life dates are used as the primary temporal information where available  
- if birth and/or death dates are missing, periods of activity are used as fallback temporal information  
- this yields a comparable source-side temporal interval even when the available evidence differs between sources  

This means that the matching step does not compare raw dates directly, but compares:
- life dates where available  
- fallback activity/evidence ranges where life dates are incomplete  
- mention ranges for RGO  

The date matching block uses the following comparison features:

### ``death_compatibility``

GS vs. DNB:
- Level 1: death years equal  
- Level 2: absolute difference ≤ 1 year  
- Level 3: absolute difference ≤ 5 years  
- Level 4: absolute difference > 5 years  
- Level 5: missing value on one or both sides  

RGO vs. GS/DNB: 

- Level 1: mention_max ≤ death_year  
- Level 2: mention_max ≤ death_year + allowance  
- Level 3: mention_min ≤ death_year + allowance < mention_max  
- Level 4: mention_min > death_year + allowance
- Level 5: missing value on one or both sides  
  

### ``birth_compatibility``
Analogue to the death_compatibility: 
GS vs. DNB:

- Level 1: birth years equal  
- Level 2: absolute difference ≤ 2 years  
- Level 3: absolute difference ≤ 10 years  
- Level 4: absolute difference > 10 years  
- Level 5: missing value on one or both sides  

RGO vs. GS/DNB:

- Level 1: mention_min ≥ birth_year  
- Level 2: mention_min within 5 years before birth_year  
- Level 3: mention_min within 20 years before birth_year  
- Level 4: mention_min more than 20 years before birth_year  
- Level 5: missing value on one or both sides  


### ``activity_overlap``
This feature compares the available temporal interval of one source with the available interval of the other source. For DNB and GS, this may be an explicit period of activity or a fallback source-side interval derived from available temporal evidence. For RGO, it is the aggregated mention range.

GS vs. DNB

- Level 1: activity ranges overlap strongly  
- Level 2: activity ranges overlap weakly  
- Level 3: no overlap, but range distance ≤ 5 years  
- Level 4: no overlap, range distance > 5 years  
- Level 5: missing value on one or both sides  

RGO vs. GS/DNB

- Level 1: mention range overlaps activity range  
- Level 2: no overlap, but distance ≤ 5 years  
- Level 3: no overlap, but distance ≤ 15 years  
- Level 4: distance > 15 years  
- Level 5: missing value on one or both sides  

Taken together, these date-based comparison levels provide graded temporal evidence for matching. They allow exact agreement, approximate agreement, partial compatibility, and clear incompatibility to be distinguished explicitly, even though the three sources differ substantially in the kind of temporal information they provide.


## Place Matching

Place information will be treated as contextual compatibility evidence derived from all place-related values associated with a person. Since all three sources may contain multiple place references, place comparison is based on sets of place labels aggregated per entity.

The sources contribute place information in different ways:

- GS provides place-related literals, typically through affiliations 
- DNB provides geographic references and place-of-activity information
- RGO provides places indirectly through places mentioned in connected lemma or
  subentry contexts

The initial preprocessing steps for place information are:

- normalize case and whitespace
- remove punctuation and brackets
- normalize common orthographic variants
- tokenize all place values
- separate or downweight frequent institutional/contextual tokens where useful
  (e.g. words such as dioc, eccl, stift, kloster, domstift)

The place matching block uses the following comparison features:

- place_best_similarity
- place_token_overlap
- place_containment_match

These features are designed to capture three different aspects of place agreement:

- the strongest lexical similarity between any single place mention on both sides
- the overlap of the overall place context
- direct containment relations between shorter and longer place forms

### `place_best_similarity`
All place labels of entity A are compared with all place labels of entity B, and the best lexical score is taken. This captures
cases where at least one place form is strongly similar even if the two entities carry different numbers of place references.

The planned comparison levels are approximately:

- Level 1: exact normalized match between two place values
- Level 2: very high lexical similarity between the best-matching place pair
- Level 3: medium lexical similarity between the best-matching place pair
- Level 4: low or no meaningful lexical similarity
- Level 5: missing value on one or both sides

### `place_token_overlap`
All tokens from all place values on both sides are combined and compared as sets. This is intended to capture broader contextual
agreement across multiple place mentions.

The planned comparison levels are approximately:

- Level 1: strong token overlap across the place sets
- Level 2: medium token overlap
- Level 3: weak token overlap
- Level 4: no meaningful token overlap
- Level 5: missing value on one or both sides

### `place_containment_match`
The comparison checks whether one normalized place form is contained in another, or whether both contain the same core place term. This is useful for cases where one source gives a shorter location label and another gives a longer institutionalized or qualified place form.

Examples of this pattern include:
- "Bremen" vs. "Domstift Bremen"
- "Moers" vs. "de Moers"
- "Hoya" vs. "von Hoya"

The planned comparison levels are approximately:

- Level 1: exact containment or same clear core place expression
- Level 2: partial containment / plausible core-place containment
- Level 3: no containment relation
- Level 4: missing value on one or both sides