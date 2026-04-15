import splink.comparison_library as cl
import splink.comparison_level_library as cll

from ..utils import (
    sql_abs_difference,
    sql_any_null,
    sql_between_crossing,
    sql_is_dnb_gs_pair,
    sql_is_rgo_other_pair,
    sql_other_value,
    sql_rgo_value,
    sql_sum,
    sql_effective_interval_end,
    sql_effective_interval_start,
    sql_interval_overlap_years,
    sql_interval_distance_years,
)


def build_date_comparison_death_dnb_gs(
    small_diff: int = 1,
    medium_diff: int = 5,
) -> cl.CustomComparison:
    """
    death_dnb_gs

    Only applies to DNB <-> GS pairs.
    Other source combinations are treated as null/irrelevant for this comparison.
    """
    dnb_gs_pair = sql_is_dnb_gs_pair()

    death_l = '"death_year_l"'
    death_r = '"death_year_r"'
    death_abs_diff = sql_abs_difference(death_l, death_r)

    null_or_irrelevant = (
        f'(NOT ({dnb_gs_pair}) OR {sql_any_null(death_l, death_r)})'
    )

    return cl.CustomComparison(
        output_column_name="death_dnb_gs",
        comparison_description="Direct death-year comparison for DNB-GS pairs only",
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing death evidence",
            ).configure(is_null_level=True),

            cll.CustomLevel(
                sql_condition=f'({dnb_gs_pair}) AND ({death_l} = {death_r})',
                label_for_charts="death years equal",
            ),
            cll.CustomLevel(
                sql_condition=f'({dnb_gs_pair}) AND ({death_abs_diff} <= {int(small_diff)})',
                label_for_charts=f"death year diff <= {int(small_diff)}",
            ),
            cll.CustomLevel(
                sql_condition=f'({dnb_gs_pair}) AND ({death_abs_diff} <= {int(medium_diff)})',
                label_for_charts=f"death year diff <= {int(medium_diff)}",
            ),
            cll.CustomLevel(
                sql_condition=f'({dnb_gs_pair}) AND ({death_abs_diff} > {int(medium_diff)})',
                label_for_charts=f"death year diff > {int(medium_diff)}",
            ),
            cll.ElseLevel(),
        ],
    )

def build_date_comparison_death_rgo_other(
    allowance: int = 5,
) -> cl.CustomComparison:
    """
    death_rgo_other

    Only applies to RGO <-> (DNB or GS) pairs.
    Interprets RGO mention range against the other side's death year.
    """
    rgo_other_pair = sql_is_rgo_other_pair()

    mention_min = sql_rgo_value("mention_start")
    mention_max = sql_rgo_value("mention_end")
    other_death = sql_other_value("death_year")
    other_death_plus_allowance = sql_sum(other_death, allowance)

    null_or_irrelevant = (
        f'(NOT ({rgo_other_pair}) OR {sql_any_null(mention_min, mention_max, other_death)})'
    )

    return cl.CustomComparison(
        output_column_name="death_rgo_other",
        comparison_description=(
            "RGO mention-range compatibility with the other side's death year"
        ),
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing death evidence",
            ).configure(is_null_level=True),

            cll.CustomLevel(
                sql_condition=f'({rgo_other_pair}) AND ({mention_max} <= {other_death})',
                label_for_charts="mention end <= death year",
            ),
            cll.CustomLevel(
                sql_condition=f'({rgo_other_pair}) AND ({mention_max} <= {other_death_plus_allowance})',
                label_for_charts=f"mention end <= death year + {int(allowance)}",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND '
                    f'{sql_between_crossing(mention_min, other_death_plus_allowance, mention_max)}'
                ),
                label_for_charts=f"mention range crosses death year + {int(allowance)}",
            ),
            cll.CustomLevel(
                sql_condition=f'({rgo_other_pair}) AND ({mention_min} > {other_death_plus_allowance})',
                label_for_charts=f"mention start > death year + {int(allowance)}",
            ),
            cll.ElseLevel(),
        ],
    )

def build_date_comparison_birth_dnb_gs(
    small_diff: int = 1,
    medium_diff: int = 5,
) -> cl.CustomComparison:
    """
    birth_dnb_gs

    Only applies to DNB <-> GS pairs.
    Other source combinations are treated as null/irrelevant for this comparison.
    """
    dnb_gs_pair = sql_is_dnb_gs_pair()

    birth_l = '"birth_year_l"'
    birth_r = '"birth_year_r"'
    birth_abs_diff = sql_abs_difference(birth_l, birth_r)

    null_or_irrelevant = (
        f'(NOT ({dnb_gs_pair}) OR {sql_any_null(birth_l, birth_r)})'
    )

    return cl.CustomComparison(
        output_column_name="birth_dnb_gs",
        comparison_description="Direct birth-year comparison for DNB-GS pairs only",
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing birth evidence",
            ).configure(is_null_level=True),

            cll.CustomLevel(
                sql_condition=f'({dnb_gs_pair}) AND ({birth_l} = {birth_r})',
                label_for_charts="birth years equal",
            ),
            cll.CustomLevel(
                sql_condition=f'({dnb_gs_pair}) AND ({birth_abs_diff} <= {int(small_diff)})',
                label_for_charts=f"birth year diff <= {int(small_diff)}",
            ),
            cll.CustomLevel(
                sql_condition=f'({dnb_gs_pair}) AND ({birth_abs_diff} <= {int(medium_diff)})',
                label_for_charts=f"birth year diff <= {int(medium_diff)}",
            ),
            cll.CustomLevel(
                sql_condition=f'({dnb_gs_pair}) AND ({birth_abs_diff} > {int(medium_diff)})',
                label_for_charts=f"birth year diff > {int(medium_diff)}",
            ),
            cll.ElseLevel(),
        ],
    )

def build_date_comparison_birth_rgo_other(
    allowance: int = 5,
    minimum_age_at_first_mention: int = 12,
) -> cl.CustomComparison:
    """
    birth_rgo_other

    Only applies to RGO <-> (DNB or GS) pairs.

    Compares RGO mention range against the other side's birth year.
    Stronger positive level when first mention occurs at least
    `minimum_age_at_first_mention` years after birth.
    """
    rgo_other_pair = sql_is_rgo_other_pair()

    mention_min = sql_rgo_value("mention_start")
    mention_max = sql_rgo_value("mention_end")
    other_birth = sql_other_value("birth_year")

    other_birth_minus_allowance = f'(({other_birth}) - {int(allowance)})'
    other_birth_plus_min_age = sql_sum(other_birth, minimum_age_at_first_mention)

    null_or_irrelevant = (
        f'(NOT ({rgo_other_pair}) OR {sql_any_null(mention_min, mention_max, other_birth)})'
    )

    return cl.CustomComparison(
        output_column_name="birth_rgo_other",
        comparison_description=(
            "RGO mention-range compatibility with the other side's birth year"
        ),
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing birth evidence",
            ).configure(is_null_level=True),

            cll.CustomLevel(
                sql_condition=f'({rgo_other_pair}) AND ({mention_min} >= {other_birth_plus_min_age})',
                label_for_charts=f"first mention >= birth year + {int(minimum_age_at_first_mention)}",
            ),
            cll.CustomLevel(
                sql_condition=f'({rgo_other_pair}) AND ({mention_min} >= {other_birth})',
                label_for_charts="first mention >= birth year",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND '
                    f'{sql_between_crossing(mention_min, other_birth_minus_allowance, mention_max)}'
                ),
                label_for_charts=f"mention range crosses birth year - {int(allowance)}",
            ),
            cll.CustomLevel(
                sql_condition=f'({rgo_other_pair}) AND ({mention_max} < {other_birth_minus_allowance})',
                label_for_charts=f"mention end < birth year - {int(allowance)}",
            ),
            cll.ElseLevel(),
        ],
    )

def build_date_comparison_activity_overlap(
    strong_overlap_years: int = 10,
    moderate_overlap_years: int = 3,
    close_distance_years: int = 5,
) -> cl.CustomComparison:
    """
    activity_overlap

    Compare effective temporal intervals rather than raw date strings.

    Effective interval per side:
    - RGO: mention_start / mention_end
    - GS: prefer activity_start / activity_end, fallback to birth/death
    - DNB: birth/death

    Comparison levels:
    - strong overlap
    - moderate overlap
    - no overlap but close in time
    - no overlap and distant
    """
    start_l = sql_effective_interval_start("l")
    end_l = sql_effective_interval_end("l")
    start_r = sql_effective_interval_start("r")
    end_r = sql_effective_interval_end("r")

    overlap_years = sql_interval_overlap_years(start_l, end_l, start_r, end_r)
    distance_years = sql_interval_distance_years(start_l, end_l, start_r, end_r)

    missing_condition = sql_any_null(start_l, end_l, start_r, end_r)

    return cl.CustomComparison(
        output_column_name="activity_overlap",
        comparison_description=(
            "Compatibility of effective temporal intervals: "
            "RGO uses mention range, GS prefers activity with life-date fallback, "
            "DNB uses life dates"
        ),
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=missing_condition,
                label_for_charts="missing interval evidence",
            ).configure(is_null_level=True),

            cll.CustomLevel(
                sql_condition=f"({overlap_years} >= {int(strong_overlap_years)})",
                label_for_charts=f"strong interval overlap >= {int(strong_overlap_years)} years",
            ),
            cll.CustomLevel(
                sql_condition=f"({overlap_years} >= {int(moderate_overlap_years)})",
                label_for_charts=f"moderate interval overlap >= {int(moderate_overlap_years)} years",
            ),
            cll.CustomLevel(
                sql_condition=f"({overlap_years} >= 1)",
                label_for_charts=f"small interval overlap >= 1 years",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f"({overlap_years} = 0) AND ({distance_years} <= {int(close_distance_years)})"
                ),
                label_for_charts=f"no overlap, distance <= {int(close_distance_years)} years",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f"({overlap_years} = 0) AND ({distance_years} > {int(close_distance_years)})"
                ),
                label_for_charts=f"no overlap, distance > {int(close_distance_years)} years",
            ),
            cll.ElseLevel(),
        ],
    )