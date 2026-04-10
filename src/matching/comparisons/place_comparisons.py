import splink.comparison_library as cl
import splink.comparison_level_library as cll

from ..utils import sql_any_place_pair, sql_missing_places


def build_place_comparison_best_similarity() -> cl.PairwiseStringDistanceFunctionAtThresholds:
    """
    place_best_similarity

    Compare the most similar normalized place pair across
    places_norm_l and places_norm_r.

    Levels are implicitly:
    - exact normalized match between any pair
    - very high best-pair similarity
    - medium best-pair similarity
    - else
    """
    return cl.PairwiseStringDistanceFunctionAtThresholds(
        "places_norm",
        distance_function_name="jaro_winkler",
        distance_threshold_or_thresholds=[0.95, 0.85],
    )

def build_place_comparison_token_overlap() -> cl.ArrayIntersectAtSizes:
    """
    place_token_overlap

    Compare overlap size between the aggregated normalized place-token arrays.
    """
    return cl.ArrayIntersectAtSizes(
        "place_tokens",
        size_threshold_or_thresholds=[3, 2, 1],
    )

def build_place_comparison_containment_match() -> cl.CustomComparison:
    """
    place_containment_match

    Levels:
    - Level 1: exact containment or same clear normalized place expression
    - Level 2: partial containment / plausible core-place relation
               (implemented here as any shared token across any place pair)
    - Level 3: no containment relation
    - Level 4: missing value on one or both sides
    """
    # Level 1:
    # - exact normalized match
    # - or word-boundary containment in either direction
    level_1_sql = sql_any_place_pair(
        "("
        "({lval} = {rval}) "
        "OR contains(' ' || {lval} || ' ', ' ' || {rval} || ' ') "
        "OR contains(' ' || {rval} || ' ', ' ' || {lval} || ' ')"
        ")"
    )

    # Level 2:
    # - any shared token between any place pair
    # Because places_norm is already stripped of many context tokens,
    # this acts as a plausible reduced-core containment signal.
    level_2_sql = sql_any_place_pair(
        "list_has_any(string_split({lval}, ' '), string_split({rval}, ' '))"
    )

    return cl.CustomComparison(
        output_column_name="place_containment_match",
        comparison_description=(
            "Containment-style place compatibility based on normalized place arrays"
        ),
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=sql_missing_places(),
                label_for_charts="missing place evidence",
            ).configure(is_null_level=True),
            cll.CustomLevel(
                sql_condition=level_1_sql,
                label_for_charts="exact/containment place match",
            ),
            cll.CustomLevel(
                sql_condition=level_2_sql,
                label_for_charts="partial/plausible place containment",
            ),
            cll.ElseLevel(),
        ],
    )