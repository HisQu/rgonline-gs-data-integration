from pathlib import Path
from typing import Tuple

import pandas as pd
from splink import DuckDBAPI, Linker, SettingsCreator, block_on

from .comparisons import (
    build_name_comparisons_pref_pref,
    build_name_comparison_pref_var_best,
    build_name_comparison_var_var_best,
    build_name_comparison_all_name_token_overlap,
    build_name_comparison_name_structure,
    build_date_comparison_death_compatibility,
    build_date_comparison_birth_compatibility,
    build_date_comparison_activity_overlap,
    build_place_comparison_best_similarity,
    build_place_comparison_token_overlap,
    build_place_comparison_containment_match,
)
from .utils import (
    DEFAULT_PROFILE_DISPLAY_COLUMNS,
    build_pair_display_columns,
    export_dataframe_to_csv,
    prepare_name_columns_for_matching,
    prepare_place_columns_for_matching,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT_DIR / "data" / "name_normalization_config.json"


def split_for_link_only(prepared_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split the combined dataframe into one dataframe per source.

    Splink link_only expects a list of input tables and only generates
    between-dataset comparisons.
    """
    keep_cols = [
        "entity_id",
        "source",
        "preferred_name",
        "variant_names",
        "birth_year",
        "death_year",
        "activity_start",
        "activity_end",
        "mention_start",
        "mention_end",
        "places",
        "gnd_id",
        "wikidata_id",
        # helper columns from name_utils
        "preferred_name_norm",
        "preferred_name_tokens",
        "preferred_first_token",
        "preferred_last_token",
        "variant_names_norm",
        "variant_name_tokens",
        "all_name_tokens",
        # helper columns from place_utils
        "places_norm",
        "place_tokens",
    ]

    dnb_df = prepared_df.loc[prepared_df["source"] == "dnb", keep_cols].copy()
    gs_df = prepared_df.loc[prepared_df["source"] == "gs", keep_cols].copy()
    rgo_df = prepared_df.loc[prepared_df["source"] == "rgo", keep_cols].copy()

    return dnb_df, gs_df, rgo_df


def build_prediction_blocking_rules() -> list:
    """
    Tight blocking rules for prediction on the full dataset.
    Keep this conservative to avoid exploding candidate counts.
    """
    return [
        block_on("preferred_first_token", "preferred_last_token"),
        block_on("preferred_first_token", "death_year"),
    ]


def build_em_training_blocking_rules() -> list:
    """
    Multiple EM blocking rules ('round robin').

    Rationale:
    - A comparison cannot be estimated in an EM session if it is part of the
      blocking rule for that session.
    - So we use several sessions with different blocks.
    """
    return [
        block_on("preferred_first_token"),
        block_on("preferred_last_token"),
        block_on("birth_year"),
        block_on("death_year"),
    ]


def build_linker(
    dnb_df: pd.DataFrame,
    gs_df: pd.DataFrame,
    rgo_df: pd.DataFrame,
) -> Linker:
    """
    Build the first Splink linker for name matching.

    Current model:
    - link_only across DNB, GS, RGO
    - blocking on first/last normalized preferred-name token
    - one comparison: preferred_name_norm vs preferred_name_norm
    """
    settings = SettingsCreator(
        link_type="link_only",
        unique_id_column_name="entity_id",
        probability_two_random_records_match=0.05,
        blocking_rules_to_generate_predictions=build_prediction_blocking_rules(),
        comparisons=[
            *build_name_comparisons_pref_pref(),
            build_name_comparison_pref_var_best(),
            build_name_comparison_var_var_best(),
            build_name_comparison_all_name_token_overlap(),
            #build_name_comparison_name_structure(),
            build_date_comparison_death_compatibility(allowance=5),
            build_date_comparison_birth_compatibility(allowance=5),
            build_date_comparison_activity_overlap(strong_overlap_years=5, weak_overlap_years=1, close_distance_years=5),
            build_place_comparison_best_similarity(),
            build_place_comparison_token_overlap(),
            build_place_comparison_containment_match(),
        ],
        retain_matching_columns=True,
        retain_intermediate_calculation_columns=True,
        additional_columns_to_retain=[
            "source",
            "preferred_name",
            "preferred_name_norm",
            "preferred_name_tokens",
            "variant_names",
            "variant_names_norm",
            "variant_name_tokens",
            "gnd_id",
            "wikidata_id",
            "places",
        ],
    )

    linker = Linker(
        [dnb_df, gs_df, rgo_df],
        settings,
        db_api=DuckDBAPI(),
        input_table_aliases=["dnb", "gs", "rgo"],
    )
    return linker


def train_linker(linker: Linker) -> tuple[Linker, list]:
    """
    Train the model using:
    - prior estimation
    - u estimation from random sampling
    - multiple EM passes with different blocking rules
    """
    deterministic_rules = [
        'l."preferred_name_norm" = r."preferred_name_norm"'
    ]

    try:
        linker.training.estimate_probability_two_random_records_match(
            deterministic_rules,
            recall=0.5,
        )
    except Exception as exc:
        print(f"[INFO] Prior estimation skipped: {exc}")

    try:
        linker.training.estimate_u_using_random_sampling(
            max_pairs=200_000,
            seed=42,
        )
    except Exception as exc:
        print(f"[INFO] U-estimation skipped: {exc}")

    training_sessions = []

    for em_rule in build_em_training_blocking_rules():
        try:
            session = linker.training.estimate_parameters_using_expectation_maximisation(
                em_rule
            )
            training_sessions.append(session)
        except Exception as exc:
            print(f"[INFO] EM training skipped for {em_rule}: {exc}")

    return linker, training_sessions


def predict_matches(
    linker: Linker,
    threshold_match_probability: float = 0.85,
):
    """
    Run pairwise predictions and return the SplinkDataFrame.
    """
    pred_splink_df = linker.inference.predict(
        threshold_match_probability=threshold_match_probability
    )
    return pred_splink_df


def run_matching(
    combined_df: pd.DataFrame,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    threshold_match_probability: float = 0.85,
) -> tuple[pd.DataFrame, pd.DataFrame, object, Linker, list]:
    """
    Workflow:
    1. Prepare helper columns
    2. Split into DNB / GS / RGO inputs
    3. Build linker
    4. Train model
    5. Predict pairwise scores once
    """
    prepared_df = prepare_name_columns_for_matching(
        df=combined_df,
        config_path=config_path,
    )

    prepared_df = prepare_place_columns_for_matching(
        df=prepared_df,
        config_path=config_path,
    )

    dnb_df, gs_df, rgo_df = split_for_link_only(prepared_df)

    linker = build_linker(
        dnb_df=dnb_df,
        gs_df=gs_df,
        rgo_df=rgo_df,
    )

    linker, training_sessions = train_linker(linker)

    pred_splink_df = predict_matches(
        linker=linker,
        threshold_match_probability=threshold_match_probability,
    )

    pred_df = pred_splink_df.as_pandas_dataframe()

    sort_cols = [c for c in ["match_probability", "match_weight"] if c in pred_df.columns]
    if sort_cols:
        pred_df = pred_df.sort_values(sort_cols, ascending=False).reset_index(drop=True)

    return prepared_df, pred_df, pred_splink_df, linker, training_sessions


if __name__ == "__main__":
    combined_df = pd.read_pickle(ROOT_DIR / "data" / "tabular" / "common_profiles.pkl")

    prepared_df, pred_df, pred_splink_df, linker, training_sessions = run_matching(
        combined_df,
        threshold_match_probability=0.5,
    )

    sql = f"""
    select *
    from {pred_splink_df.physical_name}
    order by match_probability desc
    limit 100
    """

    top50_splink_df = linker.misc.query_sql(sql, output_type="splink_df")
    records = top50_splink_df.as_record_dict()
    chart = linker.visualisations.waterfall_chart(records)
    chart.save("waterfall.html")

    pair_display_columns = build_pair_display_columns(pred_df)

    csv_path = export_dataframe_to_csv(
        pred_df,
        ROOT_DIR / "data" / "matching_outputs" / "predictions_pairs.csv",
        top_k=500,
        columns=pair_display_columns,
    )

    print(prepared_df.loc[:, DEFAULT_PROFILE_DISPLAY_COLUMNS].head())
    print(pred_df.head(10))
    print(f"Exported top predictions CSV to: {csv_path}")