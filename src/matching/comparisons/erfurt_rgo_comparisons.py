import splink.comparison_level_library as cll
import splink.comparison_library as cl

from ..utils.date_utils import sql_abs_difference, sql_any_null, sql_is_symmetric_pair


def sql_is_erfurt_rgo_pair() -> str:
    return sql_is_symmetric_pair("erfurt", "rgo")


def sql_value_for_source(source: str, base_col: str) -> str:
    return (
        f"(CASE "
        f"WHEN \"source_l\" = '{source}' THEN \"{base_col}_l\" "
        f"WHEN \"source_r\" = '{source}' THEN \"{base_col}_r\" "
        f"ELSE NULL "
        f"END)"
    )


def sql_nonempty_list(list_expr: str) -> str:
    return f"list_filter({list_expr}, lambda x: x IS NOT NULL AND x <> '')"


def sql_list_missing(list_expr: str) -> str:
    nonempty = sql_nonempty_list(list_expr)
    return f"(({list_expr}) IS NULL OR list_count({nonempty}) = 0)"


def sql_any_list_value(list_expr: str, predicate_sql_template: str) -> str:
    nonempty = sql_nonempty_list(list_expr)
    predicate = predicate_sql_template.format(value="value")
    return f"list_count(list_filter({nonempty}, lambda value: {predicate})) > 0"


def sql_best_list_value_jw(list_expr: str, scalar_expr: str) -> str:
    nonempty = sql_nonempty_list(list_expr)
    return (
        f"coalesce("
        f"  list_max("
        f"    list_transform("
        f"      {nonempty}, "
        f"      lambda value: jaro_winkler_similarity(value, {scalar_expr})"
        f"    )"
        f"  ), "
        f"  0.0"
        f")"
    )


def sql_any_pair(
    left_list_expr: str,
    right_list_expr: str,
    predicate_sql_template: str,
) -> str:
    left_nonempty = sql_nonempty_list(left_list_expr)
    right_nonempty = sql_nonempty_list(right_list_expr)
    predicate = predicate_sql_template.format(lval="lval", rval="rval")
    return (
        f"list_count("
        f"  list_filter("
        f"    {left_nonempty}, "
        f"    lambda lval: list_count("
        f"      list_filter("
        f"        {right_nonempty}, "
        f"        lambda rval: {predicate}"
        f"      )"
        f"    ) > 0"
        f"  )"
        f") > 0"
    )


def sql_best_pair_jw(left_list_expr: str, right_list_expr: str) -> str:
    left_nonempty = sql_nonempty_list(left_list_expr)
    right_nonempty = sql_nonempty_list(right_list_expr)
    return (
        f"coalesce("
        f"  list_max("
        f"    list_transform("
        f"      {left_nonempty}, "
        f"      lambda lval: coalesce("
        f"        list_max("
        f"          list_transform("
        f"            {right_nonempty}, "
        f"            lambda rval: jaro_winkler_similarity(lval, rval)"
        f"          )"
        f"        ), "
        f"        0.0"
        f"      )"
        f"    )"
        f"  ), "
        f"  0.0"
        f")"
    )


def build_erfurt_rgo_given_name_comparison() -> cl.CustomComparison:
    pair = sql_is_erfurt_rgo_pair()
    erfurt_given = sql_value_for_source("erfurt", "given_name_norm")
    rgo_given = sql_value_for_source("rgo", "preferred_first_token")
    jw_score = f"jaro_winkler_similarity({erfurt_given}, {rgo_given})"
    null_or_irrelevant = f"(NOT ({pair}) OR {sql_any_null(erfurt_given, rgo_given)})"

    return cl.CustomComparison(
        output_column_name="erfurt_rgo_given_name",
        comparison_description="Erfurt given name against RGO preferred name",
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing given-name evidence",
            ).configure(is_null_level=True),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({erfurt_given} = {rgo_given})",
                label_for_charts="normalized given names equal",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({jw_score} >= 0.95)",
                label_for_charts="given-name JW >= 0.95",
            ),
            cll.ElseLevel(),
        ],
    )


def build_erfurt_rgo_surname_byname_comparison() -> cl.CustomComparison:
    pair = sql_is_erfurt_rgo_pair()
    erfurt_surname = sql_value_for_source("erfurt", "surname_norm")
    rgo_variants = sql_value_for_source("rgo", "variant_names_norm")
    exact_sql = sql_any_list_value(rgo_variants, "{value} = " + erfurt_surname)
    containment_sql = sql_any_list_value(
        rgo_variants,
        "("
        "({value} <> " + erfurt_surname + ") AND ("
        "contains(' ' || {value} || ' ', ' ' || " + erfurt_surname + " || ' ') "
        "OR contains(' ' || " + erfurt_surname + " || ' ', ' ' || {value} || ' ')"
        ")"
        ")",
    )
    best_jw_sql = sql_best_list_value_jw(rgo_variants, erfurt_surname)
    null_or_irrelevant = (
        f"(NOT ({pair}) OR {sql_any_null(erfurt_surname)} OR {sql_list_missing(rgo_variants)})"
    )

    return cl.CustomComparison(
        output_column_name="erfurt_rgo_surname_byname",
        comparison_description="Erfurt surname against RGO byname/variant material",
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing surname/byname evidence",
            ).configure(is_null_level=True),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({exact_sql})",
                label_for_charts="Erfurt surname equals an RGO variant",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({containment_sql})",
                label_for_charts="Erfurt surname contained in an RGO variant",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({best_jw_sql} >= 0.85)",
                label_for_charts="surname/byname JW >= 0.95",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({best_jw_sql} >= 0.7)",
                label_for_charts="surname/byname JW >= 0.88",
            ),
            cll.ElseLevel(),
        ],
    )


def build_erfurt_rgo_preferred_variant_comparison() -> cl.CustomComparison:
    pair = sql_is_erfurt_rgo_pair()
    erfurt_preferred = sql_value_for_source("erfurt", "preferred_name_norm")
    rgo_variants = sql_value_for_source("rgo", "variant_names_norm")
    exact_sql = sql_any_list_value(rgo_variants, "{value} = " + erfurt_preferred)
    containment_sql = sql_any_list_value(
        rgo_variants,
        "("
        "({value} <> " + erfurt_preferred + ") AND ("
        "contains(' ' || {value} || ' ', ' ' || " + erfurt_preferred + " || ' ') "
        "OR contains(' ' || " + erfurt_preferred + " || ' ', ' ' || {value} || ' ')"
        ")"
        ")",
    )
    best_jw_sql = sql_best_list_value_jw(rgo_variants, erfurt_preferred)
    null_or_irrelevant = (
        f"(NOT ({pair}) OR {sql_any_null(erfurt_preferred)} OR {sql_list_missing(rgo_variants)})"
    )

    return cl.CustomComparison(
        output_column_name="erfurt_rgo_preferred_variant",
        comparison_description="Erfurt preferred name against RGO variant names",
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing preferred/variant evidence",
            ).configure(is_null_level=True),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({exact_sql})",
                label_for_charts="Erfurt preferred name equals an RGO variant",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({containment_sql})",
                label_for_charts="Erfurt preferred name contained in an RGO variant",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({best_jw_sql} >= 0.95)",
                label_for_charts="preferred/variant JW >= 0.95",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({best_jw_sql} >= 0.88)",
                label_for_charts="preferred/variant JW >= 0.88",
            ),
            cll.ElseLevel(),
        ],
    )


def build_erfurt_rgo_origin_place_comparison() -> cl.CustomComparison:
    pair = sql_is_erfurt_rgo_pair()
    erfurt_places = sql_value_for_source("erfurt", "places_norm")
    rgo_places = sql_value_for_source("rgo", "places_norm")
    exact_sql = sql_any_pair(erfurt_places, rgo_places, "{lval} = {rval}")
    containment_sql = sql_any_pair(
        erfurt_places,
        rgo_places,
        "("
        "({lval} <> {rval}) AND ("
        "contains(' ' || {lval} || ' ', ' ' || {rval} || ' ') "
        "OR contains(' ' || {rval} || ' ', ' ' || {lval} || ' ')"
        ")"
        ")",
    )
    best_jw_sql = sql_best_pair_jw(erfurt_places, rgo_places)
    null_or_irrelevant = (
        f"(NOT ({pair}) OR {sql_list_missing(erfurt_places)} OR {sql_list_missing(rgo_places)})"
    )

    return cl.CustomComparison(
        output_column_name="erfurt_rgo_origin_place",
        comparison_description="Erfurt Herkunftsname against RGO place context",
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing origin/place evidence",
            ).configure(is_null_level=True),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({exact_sql})",
                label_for_charts="exact normalized origin/place match",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({containment_sql})",
                label_for_charts="containment origin/place match",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({best_jw_sql} >= 0.95)",
                label_for_charts="origin/place JW >= 0.95",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({best_jw_sql} >= 0.88)",
                label_for_charts="origin/place JW >= 0.88",
            ),
            cll.ElseLevel(),
        ],
    )


def build_erfurt_rgo_semester_year_comparison(
    small_distance: int = 1,
    medium_distance: int = 5,
) -> cl.CustomComparison:
    pair = sql_is_erfurt_rgo_pair()
    erfurt_year = sql_value_for_source("erfurt", "mention_start")
    rgo_start = sql_value_for_source("rgo", "mention_start")
    rgo_end = sql_value_for_source("rgo", "mention_end")
    distance_to_interval = (
        f"(CASE "
        f"WHEN {erfurt_year} < {rgo_start} THEN {sql_abs_difference(erfurt_year, rgo_start)} "
        f"WHEN {erfurt_year} > {rgo_end} THEN {sql_abs_difference(erfurt_year, rgo_end)} "
        f"ELSE 0 "
        f"END)"
    )
    null_or_irrelevant = (
        f"(NOT ({pair}) OR {sql_any_null(erfurt_year, rgo_start, rgo_end)})"
    )

    return cl.CustomComparison(
        output_column_name="erfurt_rgo_semester_year",
        comparison_description="Erfurt semester year against RGO mention interval",
        comparison_levels=[
            cll.CustomLevel(
                sql_condition=null_or_irrelevant,
                label_for_charts="irrelevant or missing semester/mention evidence",
            ).configure(is_null_level=True),
            cll.CustomLevel(
                sql_condition=(
                    f"({pair}) AND ({rgo_start} <= {erfurt_year}) AND ({erfurt_year} <= {rgo_end})"
                ),
                label_for_charts="semester year inside RGO mention interval",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({distance_to_interval} <= {int(small_distance)})",
                label_for_charts=f"semester year within {int(small_distance)} year",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({distance_to_interval} <= {int(medium_distance)})",
                label_for_charts=f"semester year within {int(medium_distance)} years",
            ),
            cll.CustomLevel(
                sql_condition=f"({pair}) AND ({distance_to_interval} > {int(medium_distance)})",
                label_for_charts=f"semester year distance > {int(medium_distance)} years",
            ),
            cll.ElseLevel(),
        ],
    )


def build_erfurt_rgo_comparisons() -> list[cl.CustomComparison]:
    return [
        build_erfurt_rgo_given_name_comparison(),
        build_erfurt_rgo_surname_byname_comparison(),
        #build_erfurt_rgo_preferred_variant_comparison(),
        build_erfurt_rgo_origin_place_comparison(),
        build_erfurt_rgo_semester_year_comparison(),
    ]
