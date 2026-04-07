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


def build_date_comparison_death_compatibility(allowance: int = 5) -> cl.CustomComparison:
    """
    death_compatibility

    A source-aware custom comparison that treats all levels as expressing
    temporal compatibility with respect to a death year, but adapts the logic
    to the evidence type available in the compared sources.

    Cases:
    1) DNB <-> GS:
       compare death_year_l vs death_year_r by absolute year difference

    2) RGO <-> (DNB or GS):
       compare RGO mention range [mention_start, mention_end]
       against the other side's death_year with an allowance parameter
    """
    dnb_gs_pair = sql_is_dnb_gs_pair()
    rgo_other_pair = sql_is_rgo_other_pair()

    # DNB <-> GS expressions
    death_l = '"death_year_l"'
    death_r = '"death_year_r"'
    death_abs_diff = sql_abs_difference(death_l, death_r)

    # RGO <-> other expressions
    mention_min = sql_rgo_value("mention_start")
    mention_max = sql_rgo_value("mention_end")
    other_death = sql_other_value("death_year")
    other_death_plus_allowance = sql_sum(other_death, allowance)

    # Missingness is branch-specific:
    # - DNB <-> GS requires death_year on both sides
    # - RGO <-> other requires mention_start, mention_end, death_year
    missing_condition = (
        f'(({dnb_gs_pair}) AND {sql_any_null(death_l, death_r)}) '
        f'OR '
        f'(({rgo_other_pair}) AND {sql_any_null(mention_min, mention_max, other_death)})'
    )

    return cl.CustomComparison(
        output_column_name="death_compatibility",
        comparison_description=(
            "Temporal compatibility with respect to death year, using direct "
            "year-difference logic for DNB-GS and mention-vs-death plausibility "
            "logic for RGO-other pairs"
        ),
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=missing_condition,
                label_for_charts="missing death evidence",
            ).configure(is_null_level=True),

            # DNB <-> GS: direct death-year comparison
            cll.CustomLevel(
                sql_condition=(
                    f'({dnb_gs_pair}) AND ({death_l} = {death_r})'
                ),
                label_for_charts="death years equal",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({dnb_gs_pair}) AND ({death_abs_diff} <= 1)'
                ),
                label_for_charts="death year diff <= 1",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({dnb_gs_pair}) AND ({death_abs_diff} <= 5)'
                ),
                label_for_charts="death year diff <= 5",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({dnb_gs_pair}) AND ({death_abs_diff} > 5)'
                ),
                label_for_charts="death year diff > 5",
            ),

            # RGO <-> (DNB or GS): mention range vs death year
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND ({mention_max} <= {other_death})'
                ),
                label_for_charts="mention end <= death year",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND ({mention_max} <= {other_death_plus_allowance})'
                ),
                label_for_charts=f"mention end <= death year + {allowance}",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND '
                    f'{sql_between_crossing(mention_min, other_death_plus_allowance, mention_max)}'
                ),
                label_for_charts=f"mention range crosses death year + {allowance}",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND ({mention_min} > {other_death_plus_allowance})'
                ),
                label_for_charts=f"mention start > death year + {allowance}",
            ),

            cll.ElseLevel(),
        ],
    )

def build_date_comparison_birth_compatibility(allowance: int = 5) -> cl.CustomComparison:
    """
    birth_compatibility

    A source-aware custom comparison that treats all levels as expressing
    temporal compatibility with respect to a birth year, but adapts the logic
    to the evidence type available in the compared sources.

    Cases:
    1) DNB <-> GS:
       compare birth_year_l vs birth_year_r by absolute year difference

    2) RGO <-> (DNB or GS):
       compare RGO mention range [mention_start, mention_end]
       against the other side's birth_year with an allowance parameter
    """
    dnb_gs_pair = sql_is_dnb_gs_pair()
    rgo_other_pair = sql_is_rgo_other_pair()

    # DNB <-> GS expressions
    birth_l = '"birth_year_l"'
    birth_r = '"birth_year_r"'
    birth_abs_diff = sql_abs_difference(birth_l, birth_r)

    # RGO <-> other expressions
    mention_min = sql_rgo_value("mention_start")
    mention_max = sql_rgo_value("mention_end")
    other_birth = sql_other_value("birth_year")
    other_birth_minus_allowance = f'(({other_birth}) - {int(allowance)})'

    # Missingness is branch-specific:
    # - DNB <-> GS requires birth_year on both sides
    # - RGO <-> other requires mention_start, mention_end, birth_year
    missing_condition = (
        f'(({dnb_gs_pair}) AND {sql_any_null(birth_l, birth_r)}) '
        f'OR '
        f'(({rgo_other_pair}) AND {sql_any_null(mention_min, mention_max, other_birth)})'
    )

    return cl.CustomComparison(
        output_column_name="birth_compatibility",
        comparison_description=(
            "Temporal compatibility with respect to birth year, using direct "
            "year-difference logic for DNB-GS and mention-vs-birth plausibility "
            "logic for RGO-other pairs"
        ),
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=missing_condition,
                label_for_charts="missing birth evidence",
            ).configure(is_null_level=True),

            # DNB <-> GS: direct birth-year comparison
            cll.CustomLevel(
                sql_condition=(
                    f'({dnb_gs_pair}) AND ({birth_l} = {birth_r})'
                ),
                label_for_charts="birth years equal",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({dnb_gs_pair}) AND ({birth_abs_diff} <= 1)'
                ),
                label_for_charts="birth year diff <= 1",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({dnb_gs_pair}) AND ({birth_abs_diff} <= 5)'
                ),
                label_for_charts="birth year diff <= 5",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({dnb_gs_pair}) AND ({birth_abs_diff} > 5)'
                ),
                label_for_charts="birth year diff > 5",
            ),

            # RGO <-> (DNB or GS): mention range vs birth year
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND ({mention_min} >= {other_birth})'
                ),
                label_for_charts="mention start >= birth year",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND ({mention_min} >= {other_birth_minus_allowance})'
                ),
                label_for_charts=f"mention start >= birth year - {allowance}",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND '
                    f'{sql_between_crossing(mention_min, other_birth_minus_allowance, mention_max)}'
                ),
                label_for_charts=f"mention range crosses birth year - {allowance}",
            ),
            cll.CustomLevel(
                sql_condition=(
                    f'({rgo_other_pair}) AND ({mention_max} < {other_birth_minus_allowance})'
                ),
                label_for_charts=f"mention end < birth year - {allowance}",
            ),

            cll.ElseLevel(),
        ],
    )

def build_date_comparison_activity_overlap(
    strong_overlap_years: int = 5,
    weak_overlap_years: int = 1,
    close_distance_years: int = 10,
) -> cl.CustomComparison:
    """
    activity_overlap

    Compare effective temporal intervals rather than raw date strings.

    Effective interval per side:
    - RGO: mention_start / mention_end
    - GS: prefer activity_start / activity_end, fallback to birth/death
    - DNB: birth/death

    Levels:
    1. strong overlap
    2. weak overlap
    3. no overlap, distance <= close_distance_years
    4. no overlap, distance > close_distance_years
    5. missing on one or both sides
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
            # Missing evidence
            cll.CustomLevel(
                sql_condition=missing_condition,
                label_for_charts="missing interval evidence",
            ),

            # Overlap levels
            cll.CustomLevel(
                sql_condition=f"({overlap_years} >= {int(strong_overlap_years)})",
                label_for_charts=f"strong interval overlap >= {int(strong_overlap_years)} years",
            ),
            cll.CustomLevel(
                sql_condition=f"({overlap_years} >= {int(weak_overlap_years)})",
                label_for_charts=f"weak interval overlap >= {int(weak_overlap_years)} year(s)",
            ),

            # No-overlap but close / far
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

            # Safety fallback
            cll.ElseLevel(),
        ],
    )