import argparse
from pathlib import Path
from typing import Sequence

import pandas as pd
from splink import DuckDBAPI, Linker, SettingsCreator, block_on

from .comparisons import (
    build_name_comparisons_pref_pref,
    build_name_comparison_pref_var_best,
    build_name_comparison_var_var_best,
    build_name_comparison_all_name_token_overlap,
    build_date_comparison_birth_rgo_other,
    build_date_comparison_birth_dnb_gs,
    build_date_comparison_death_dnb_gs,
    build_date_comparison_death_rgo_other,
    build_date_comparison_activity_overlap,
    build_place_comparison_token_overlap,
    build_place_comparison_match_quality,
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
DEFAULT_INPUT_PATH = ROOT_DIR / "data" / "tabular" / "common_profiles.pkl"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "matching_outputs"

MATCHING_COLUMNS = [
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


def validate_selected_sources(
    prepared_df: pd.DataFrame,
    sources: Sequence[str] | None = None,
) -> list[str]:
    available_sources = list(dict.fromkeys(prepared_df["source"].dropna().astype(str)))
    if sources is None:
        selected_sources = available_sources
    else:
        selected_sources = list(dict.fromkeys(source.lower() for source in sources))

    unknown = sorted(set(selected_sources) - set(available_sources))
    if unknown:
        known = ", ".join(available_sources)
        raise ValueError(f"Unknown source(s): {', '.join(unknown)}. Available sources: {known}")

    if len(set(selected_sources)) < 2:
        raise ValueError("At least two distinct sources are required for matching")

    for source in selected_sources:
        row_count = int((prepared_df["source"] == source).sum())
        if row_count == 0:
            raise ValueError(f"Selected source has no rows: {source}")

    return selected_sources


def split_for_link_only(
    prepared_df: pd.DataFrame,
    sources: Sequence[str] | None = None,
) -> tuple[list[pd.DataFrame], list[str]]:
    """
    Split the combined dataframe into one dataframe per source.

    Splink link_only expects a list of input tables and only generates
    between-dataset comparisons.
    """
    selected_sources = validate_selected_sources(prepared_df, sources)
    source_frames = [
        prepared_df.loc[prepared_df["source"] == source, MATCHING_COLUMNS].copy()
        for source in selected_sources
    ]
    return source_frames, selected_sources


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
    source_frames: Sequence[pd.DataFrame],
    source_aliases: Sequence[str],
) -> Linker:
    """
    Build the first Splink linker for name matching.

    Current model:
    - link_only across the selected source tables
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
            #build_name_comparison_all_name_token_overlap(), # not used since highly correlated to pref_var and var_var
            build_date_comparison_death_dnb_gs(small_diff=1, medium_diff=5),
            build_date_comparison_death_rgo_other(allowance=5),
            build_date_comparison_birth_dnb_gs(small_diff=3, medium_diff=10),
            build_date_comparison_birth_rgo_other(allowance=5, minimum_age_at_first_mention=12),
            build_date_comparison_activity_overlap(
                strong_overlap_years=5,
                moderate_overlap_years=3,
                close_distance_years=5,
            ),
            build_place_comparison_match_quality(),
            build_place_comparison_token_overlap(),
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
        list(source_frames),
        settings,
        db_api=DuckDBAPI(),
        input_table_aliases=list(source_aliases),
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
            max_pairs=1e6,
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
    sources: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, object, Linker, list]:
    """
    Workflow:
    1. Prepare helper columns
    2. Split into selected source inputs
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

    source_frames, source_aliases = split_for_link_only(prepared_df, sources=sources)

    linker = build_linker(
        source_frames=source_frames,
        source_aliases=source_aliases,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Splink matching for selected sources from a common profile table."
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        help="Sources to match. Defaults to all sources present in the profile table.",
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Path to the common profile pickle.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for matching outputs.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Minimum match probability for exported predictions.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    combined_df = pd.read_pickle(args.input)

    prepared_df, pred_df, pred_splink_df, linker, training_sessions = run_matching(
        combined_df,
        threshold_match_probability=args.threshold,
        sources=args.sources,
    )


    # Full thresholded dataframe
    thresholded_matches_pkl = output_dir / f"predictions_pairs.pkl"
    pred_df.to_pickle(thresholded_matches_pkl)

    thresholded_matches_csv = output_dir / f"predictions_pairs.csv"
    pred_df.to_csv(thresholded_matches_csv, index=False)

    sql = f"""
    select *
    from {pred_splink_df.physical_name}
    order by match_probability desc
    limit 100
    """

    top100_splink_df = linker.misc.query_sql(sql, output_type="splink_df")
    records = top100_splink_df.as_record_dict()
    chart = linker.visualisations.waterfall_chart(records)
    chart.save(str(output_dir / "waterfall.html"))

    pair_display_columns = build_pair_display_columns(pred_df)

    debug_csv_path = export_dataframe_to_csv(
        pred_df,
        output_dir / f"predictions_pairs_top500.csv",
        top_k=500,
        columns=pair_display_columns,
    )

    print(prepared_df.loc[:, DEFAULT_PROFILE_DISPLAY_COLUMNS].head())
    print(pred_df.head(10))
    print(f"Exported thresholded match dataframe to: {thresholded_matches_pkl}")
    print(f"Exported thresholded match CSV to: {thresholded_matches_csv}")
    print(f"Exported top predictions CSV to: {debug_csv_path}")


if __name__ == "__main__":
    main()
