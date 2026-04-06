from typing import Iterable


def sql_is_symmetric_pair(source_a: str, source_b: str) -> str:
    """
    SQL condition for an unordered source pair:
    (source_l=source_a AND source_r=source_b) OR vice versa
    """
    return (
        f'(("source_l" = \'{source_a}\' AND "source_r" = \'{source_b}\') '
        f'OR ("source_l" = \'{source_b}\' AND "source_r" = \'{source_a}\'))'
    )


def sql_is_dnb_gs_pair() -> str:
    """SQL condition for DNB <-> GS pairs."""
    return sql_is_symmetric_pair("dnb", "gs")


def sql_is_rgo_other_pair() -> str:
    """
    SQL condition for RGO <-> (DNB or GS) pairs.

    Under the current link_only setup, these are the only relevant
    source-pair cases involving RGO.
    """
    return (
        '(("source_l" = \'rgo\' AND "source_r" IN (\'dnb\', \'gs\')) '
        'OR ("source_r" = \'rgo\' AND "source_l" IN (\'dnb\', \'gs\')))'
    )


def sql_rgo_value(base_col: str) -> str:
    """
    Return the value of <base_col> from the RGO side of a pair.

    Example:
        sql_rgo_value("mention_end")
        -> CASE WHEN source_l='rgo' THEN mention_end_l ELSE mention_end_r END
    """
    return (
        f'(CASE '
        f'WHEN "source_l" = \'rgo\' THEN "{base_col}_l" '
        f'ELSE "{base_col}_r" '
        f'END)'
    )


def sql_other_value(base_col: str) -> str:
    """
    Return the value of <base_col> from the non-RGO side of a pair.

    Example:
        sql_other_value("death_year")
        -> CASE WHEN source_l='rgo' THEN death_year_r ELSE death_year_l END
    """
    return (
        f'(CASE '
        f'WHEN "source_l" = \'rgo\' THEN "{base_col}_r" '
        f'ELSE "{base_col}_l" '
        f'END)'
    )


def sql_any_null(*expressions: str) -> str:
    """
    Build an OR condition checking whether any SQL expression is NULL.

    Each item can be either:
    - a raw column reference like '"death_year_l"'
    - or a more complex SQL expression like '(CASE WHEN ... END)'
    """
    return "(" + " OR ".join(f"({expr}) IS NULL" for expr in expressions) + ")"


def sql_abs_difference(expr_left: str, expr_right: str) -> str:
    """Absolute numeric difference between two SQL expressions."""
    return f'abs(({expr_left}) - ({expr_right}))'


def sql_sum(expr_left: str, number: int) -> str:
    """Add a Python integer constant to a SQL expression."""
    return f'(({expr_left}) + {int(number)})'


def sql_between_crossing(start_expr: str, pivot_expr: str, end_expr: str) -> str:
    """
    True when the interval [start_expr, end_expr] crosses the pivot:
        start <= pivot < end
    """
    return f'(({start_expr}) <= ({pivot_expr}) AND ({pivot_expr}) < ({end_expr}))'