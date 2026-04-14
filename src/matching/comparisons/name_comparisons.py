import splink.comparison_library as cl
import splink.comparison_level_library as cll
from ..utils import preferred_variant_best_jw_sql

def build_name_comparisons_pref_pref() -> list:
    """
    First minimal name-comparison set.

    Current scope:
    - preferred vs preferred only

    The compared column is assumed to be prepared beforehand in the dataframe:
    - preferred_name_norm
    """
    return [
        cl.CustomComparison(
            output_column_name="preferred_name_similarity",
            comparison_description="Preferred name exact/fuzzy comparison with TF adjustment",
            comparison_levels=[
                cll.CustomLevel(
                    sql_condition='"preferred_name_norm_l" IS NULL OR "preferred_name_norm_r" IS NULL',
                    label_for_charts="Null",
                ).configure(is_null_level=True),

                cll.ExactMatchLevel(
                    "preferred_name_norm",
                    term_frequency_adjustments=True,
                ),
                cll.JaroWinklerLevel("preferred_name_norm", 0.97),
                cll.JaroWinklerLevel("preferred_name_norm", 0.92),
                cll.JaroWinklerLevel("preferred_name_norm", 0.88),

                cll.ElseLevel(),
            ],
        )
    ]

def build_name_comparison_pref_var_best() -> cl.CustomComparison:
    score_sql = preferred_variant_best_jw_sql()

    return cl.CustomComparison(
        output_column_name="preferred_variant_best_similarity",
        comparison_description="Best symmetric Jaro-Winkler similarity between preferred and variant names",
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=f"{score_sql} >= 0.97",
                label_for_charts="preferred-variant best JW >= 0.97",
            ),
            cll.CustomLevel(
                sql_condition=f"{score_sql} >= 0.92",
                label_for_charts="preferred-variant best JW >= 0.90",
            ),
            cll.CustomLevel(
                sql_condition=f"{score_sql} >= 0.88",
                label_for_charts="preferred-variant best JW >= 0.75",
            ),
            cll.CustomLevel(
                sql_condition="""
                    "preferred_name_norm_l" IS NULL
                    OR "preferred_name_norm_r" IS NULL
                    OR "variant_names_norm_l" IS NULL
                    OR "variant_names_norm_r" IS NULL
                """,
                label_for_charts="Null",
            ).configure(is_null_level=True),
            cll.ElseLevel(),
        ],
    )

def build_name_comparison_var_var_best() -> cl.PairwiseStringDistanceFunctionAtThresholds:
    """
    variant_variant_best_similarity

    Compare the most similar normalized variant-name pair across
    variant_names_norm_l and variant_names_norm_r.

    Uses Jaro-Winkler on the array column variant_names_norm.
    """
    return cl.PairwiseStringDistanceFunctionAtThresholds(
        "variant_names_norm",
        distance_function_name="jaro_winkler",
        distance_threshold_or_thresholds=[0.95, 0.80, 0.60],
    )

def build_name_comparison_all_name_token_overlap() -> cl.ArrayIntersectAtSizes:
    """
    all_name_token_overlap

    Compare overlap size between the combined token arrays of preferred and variant names.
    """
    return cl.ArrayIntersectAtSizes(
        "all_name_tokens",
        size_threshold_or_thresholds=[5, 4, 3],
    )