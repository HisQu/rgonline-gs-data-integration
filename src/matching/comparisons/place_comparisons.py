import splink.comparison_library as cl
import splink.comparison_level_library as cll

from ..utils import sql_any_place_pair, sql_missing_places, sql_best_place_pair_jw


def build_place_comparison_token_overlap() -> cl.ArrayIntersectAtSizes:
    """
    place_token_overlap

    Compare overlap size between the aggregated normalized place-token arrays.
    """
    return cl.ArrayIntersectAtSizes(
        "places_norm",
        size_threshold_or_thresholds=[4,3],
    )


def build_place_comparison_match_quality() -> cl.CustomComparison:
    """
    place_match_quality

    One combined place comparison with this order:
    1) exact normalized place pair match
    2) containment match between place pairs
    3) very high pairwise Jaro-Winkler similarity
    4) medium pairwise Jaro-Winkler similarity
    5) else
    """

    exact_sql = sql_any_place_pair("{lval} = {rval}")

    containment_sql = sql_any_place_pair(
        "("
        "({lval} <> {rval}) AND ("
        "contains(' ' || {lval} || ' ', ' ' || {rval} || ' ') "
        "OR contains(' ' || {rval} || ' ', ' ' || {lval} || ' ')"
        ")"
        ")"
    )

    best_jw_sql = sql_best_place_pair_jw()

    return cl.CustomComparison(
        output_column_name="place_match_quality",
        comparison_description=(
            "Combined place comparison using exact match, containment, "
            "and best pairwise Jaro-Winkler similarity"
        ),
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=sql_missing_places(),
                label_for_charts="missing place evidence",
            ).configure(is_null_level=True),

            cll.CustomLevel(
                sql_condition=exact_sql,
                label_for_charts="exact normalized place match",
            ),

            cll.CustomLevel(
                sql_condition=containment_sql,
                label_for_charts="containment place match",
            ),

            cll.CustomLevel(
                sql_condition=f"{best_jw_sql} >= 0.97",
                label_for_charts="best place-pair JW >= 0.97",
            ),

            cll.CustomLevel(
                sql_condition=f"{best_jw_sql} >= 0.90",
                label_for_charts="best place-pair JW >= 0.90",
            ),

            cll.ElseLevel(),
        ],
    )