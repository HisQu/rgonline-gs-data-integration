import json
from pathlib import Path
from typing import Any

import pandas as pd

from .main_match import ROOT_DIR, DEFAULT_CONFIG_PATH
from .utils import prepare_name_columns_for_matching


COMMON_PROFILES_FILE = ROOT_DIR / "data" / "tabular" / "common_profiles.pkl"
MATCHING_OUTPUT_DIR = ROOT_DIR / "data" / "matching_outputs"
EVAL_OUTPUT_DIR = ROOT_DIR / "data" / "evaluation"


def normalize_nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip()
    return text if text else None


def load_predictions_dataframe(file_path: str | Path) -> pd.DataFrame:
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix in {".pkl", ".pickle"}:
        return pd.read_pickle(file_path)
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix == ".parquet":
        return pd.read_parquet(file_path)

    raise ValueError(f"Unsupported predictions file format: {file_path}")


def prepare_common_profiles_for_evaluation(
    common_profiles_path: str | Path,
    config_path: str | Path,
) -> pd.DataFrame:
    combined_df = pd.read_pickle(common_profiles_path)

    prepared_df = prepare_name_columns_for_matching(
        df=combined_df,
        config_path=config_path,
    )

    prepared_df["gnd_id_norm"] = prepared_df["gnd_id"].apply(normalize_nullable_string)
    return prepared_df


def build_reference_pairs_from_gnd(prepared_df: pd.DataFrame) -> pd.DataFrame:
    """
    Uses ALL pairings if a gnd_id occurs multiple times on either side.
    """
    gs_df = prepared_df.loc[
        (prepared_df["source"] == "gs") & prepared_df["gnd_id_norm"].notna()
    ].copy()

    dnb_df = prepared_df.loc[
        (prepared_df["source"] == "dnb") & prepared_df["gnd_id_norm"].notna()
    ].copy()

    gs_cols = [
        "entity_id",
        "preferred_name",
        "birth_year",
        "death_year",
        "gnd_id_norm",
        "preferred_name_norm",
        "preferred_first_token",
        "preferred_last_token",
    ]

    dnb_cols = [
        "entity_id",
        "preferred_name",
        "birth_year",
        "death_year",
        "gnd_id_norm",
        "preferred_name_norm",
        "preferred_first_token",
        "preferred_last_token",
    ]

    reference_df = dnb_df[dnb_cols].merge(
        gs_df[gs_cols],
        on="gnd_id_norm",
        how="inner",
        suffixes=("_dnb", "_gs"),
    )

    reference_df = reference_df.rename(
        columns={
            "gnd_id_norm": "gnd_id",
            "entity_id_dnb": "entity_id_dnb",
            "entity_id_gs": "entity_id_gs",
            "preferred_name_dnb": "preferred_name_dnb",
            "preferred_name_gs": "preferred_name_gs",
            "birth_year_dnb": "birth_year_dnb",
            "birth_year_gs": "birth_year_gs",
            "death_year_dnb": "death_year_dnb",
            "death_year_gs": "death_year_gs",
            "preferred_name_norm_dnb": "preferred_name_norm_dnb",
            "preferred_name_norm_gs": "preferred_name_norm_gs",
            "preferred_first_token_dnb": "preferred_first_token_dnb",
            "preferred_first_token_gs": "preferred_first_token_gs",
            "preferred_last_token_dnb": "preferred_last_token_dnb",
            "preferred_last_token_gs": "preferred_last_token_gs",
        }
    )

    reference_df = reference_df.drop_duplicates(
        subset=["entity_id_dnb", "entity_id_gs"]
    ).reset_index(drop=True)

    reference_df["reference_pair_key"] = (
        reference_df["entity_id_dnb"].astype(str)
        + "||"
        + reference_df["entity_id_gs"].astype(str)
    )

    return reference_df


def extract_predicted_gs_dnb_pairs(pred_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract GS<->DNB pairs and orient them as (dnb, gs)
    """
    if pred_df.empty:
        return pd.DataFrame()

    source_l = pred_df["source_dataset_l"].astype(str)
    source_r = pred_df["source_dataset_r"].astype(str)

    gs_dnb_mask = (
        ((source_l == "dnb") & (source_r == "gs"))
        | ((source_l == "gs") & (source_r == "dnb"))
    )

    out = pred_df.loc[gs_dnb_mask].copy()

    if out.empty:
        return out

    left_is_dnb = out["source_dataset_l"].astype(str) == "dnb"

    out["entity_id_dnb"] = out["entity_id_l"].where(left_is_dnb, out["entity_id_r"])
    out["entity_id_gs"] = out["entity_id_r"].where(left_is_dnb, out["entity_id_l"])

    if "preferred_name_l" in out.columns and "preferred_name_r" in out.columns:
        out["preferred_name_dnb"] = out["preferred_name_l"].where(left_is_dnb, out["preferred_name_r"])
        out["preferred_name_gs"] = out["preferred_name_r"].where(left_is_dnb, out["preferred_name_l"])

    if "gnd_id_l" in out.columns and "gnd_id_r" in out.columns:
        out["gnd_id_dnb"] = out["gnd_id_l"].where(left_is_dnb, out["gnd_id_r"])
        out["gnd_id_gs"] = out["gnd_id_r"].where(left_is_dnb, out["gnd_id_l"])

    out["reference_pair_key"] = (
        out["entity_id_dnb"].astype(str)
        + "||"
        + out["entity_id_gs"].astype(str)
    )

    out = out.sort_values(
        by=["match_probability", "match_weight"],
        ascending=False,
        na_position="last",
    ).drop_duplicates(subset=["entity_id_dnb", "entity_id_gs"])

    return out.reset_index(drop=True)


def _notna_and_equal(left: pd.Series, right: pd.Series) -> pd.Series:
    return left.notna() & right.notna() & (left.astype(str) == right.astype(str))


def annotate_prediction_blocking(reference_df: pd.DataFrame) -> pd.DataFrame:
    """
    Diagnose whether a reference GS<->DNB pair would pass at least one
    prediction blocking rule from main_match
    """
    out = reference_df.copy()

    rule_1 = (
        _notna_and_equal(out["preferred_first_token_dnb"], out["preferred_first_token_gs"])
        & _notna_and_equal(out["preferred_last_token_dnb"], out["preferred_last_token_gs"])
    )

    rule_2 = (
        _notna_and_equal(out["preferred_first_token_dnb"], out["preferred_first_token_gs"])
        & out["death_year_dnb"].notna()
        & out["death_year_gs"].notna()
        & (out["death_year_dnb"] == out["death_year_gs"])
    )

    out["passes_block_rule_pref_first_last"] = rule_1
    out["passes_block_rule_pref_first_death"] = rule_2
    out["passes_any_prediction_blocking_rule"] = rule_1 | rule_2

    return out

def compute_classification_metrics(
    reference_df: pd.DataFrame,
    predicted_pairs_df: pd.DataFrame,
) -> dict[str, float | int | None]:
    """
    Computes TP, FP, FN, TN (approx) and derived metrics.

    IMPORTANT:
    - TP: reference pairs found by Splink
    - FN: reference pairs missed
    - FP: predicted pairs NOT in reference
    - TN: approximated as all possible pairs minus TP, FP, FN
          (can be huge / not always meaningful in record linkage!)
    """

    # --- Keys ---
    ref_keys = set(reference_df["reference_pair_key"])
    pred_keys = set(predicted_pairs_df["reference_pair_key"])

    # --- Confusion matrix ---
    tp = len(ref_keys & pred_keys)
    fn = len(ref_keys - pred_keys)
    fp = len(pred_keys - ref_keys)

    # --- Total possible pairs (GS x DNB) ---
    # approximate from reference_df
    n_dnb = reference_df["entity_id_dnb"].nunique()
    n_gs = reference_df["entity_id_gs"].nunique()
    total_pairs = n_dnb * n_gs

    tn = total_pairs - tp - fn - fp

    # --- Metrics ---
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision is not None and recall is not None and (precision + recall))
        else None
    )

    accuracy = (tp + tn) / total_pairs if total_pairs else None

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "total_pairs": total_pairs,
    }

def compare_reference_to_predictions(
    reference_df: pd.DataFrame,
    predicted_pairs_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pred_keep_cols = [
        c
        for c in [
            "reference_pair_key",
            "match_probability",
            "match_weight",
            "entity_id_l",
            "entity_id_r",
            "source_dataset_l",
            "source_dataset_r",
            "preferred_name_l",
            "preferred_name_r",
            "gnd_id_l",
            "gnd_id_r",
            "birth_year_l",
            "birth_year_r",
            "death_year_l",
            "death_year_r",
            "activity_start_l",
            "activity_start_r",
            "activity_end_l",
            "activity_end_r",
            "mention_start_l",
            "mention_start_r",
            "mention_end_l",
            "mention_end_r",
            "places_l",
            "places_r",
        ]
        if c in predicted_pairs_df.columns
    ]

    merged = reference_df.merge(
        predicted_pairs_df[pred_keep_cols],
        on="reference_pair_key",
        how="left",
    )

    merged["found_by_splink"] = merged["match_probability"].notna()

    merged["miss_reason"] = None
    merged.loc[
        ~merged["found_by_splink"] & ~merged["passes_any_prediction_blocking_rule"],
        "miss_reason",
    ] = "failed_prediction_blocking"
    merged.loc[
        ~merged["found_by_splink"] & merged["passes_any_prediction_blocking_rule"],
        "miss_reason",
    ] = "passed_blocking_but_below_threshold"

    found_df = merged.loc[merged["found_by_splink"]].copy()
    missed_df = merged.loc[~merged["found_by_splink"]].copy()

    return merged, found_df, missed_df


def build_summary(
    prepared_df: pd.DataFrame,
    reference_df: pd.DataFrame,
    found_df: pd.DataFrame,
    missed_df: pd.DataFrame,
    predictions_file: str | Path,
) -> dict[str, Any]:
    gs_with_gnd = prepared_df.loc[
        (prepared_df["source"] == "gs") & prepared_df["gnd_id_norm"].notna()
    ]
    dnb_with_gnd = prepared_df.loc[
        (prepared_df["source"] == "dnb") & prepared_df["gnd_id_norm"].notna()
    ]

    total_reference = len(reference_df)
    total_found = len(found_df)
    total_missed = len(missed_df)

    return {
        "predictions_file": str(predictions_file),
        "gs_rows_with_gnd_id": int(len(gs_with_gnd)),
        "dnb_rows_with_gnd_id": int(len(dnb_with_gnd)),
        "reference_positive_pairs_total": int(total_reference),
        "reference_positive_pairs_found_by_splink": int(total_found),
        "reference_positive_pairs_missed_by_splink": int(total_missed),
        "reference_recall_for_exported_threshold": (
            float(total_found / total_reference) if total_reference else None
        ),
        "missed_failed_prediction_blocking": int(
            (missed_df["miss_reason"] == "failed_prediction_blocking").sum()
        ),
        "missed_passed_blocking_but_below_threshold": int(
            (missed_df["miss_reason"] == "passed_blocking_but_below_threshold").sum()
        ),
    }


def save_outputs(
    output_dir: Path,
    reference_df: pd.DataFrame,
    found_df: pd.DataFrame,
    missed_df: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    reference_path = output_dir / f"reference_pairs.csv"
    found_path = output_dir / f"reference_found.csv"
    missed_path = output_dir / f"reference_missed.csv"
    summary_path = output_dir / f"summary.json"

    reference_df.to_csv(reference_path, index=False)
    found_df.to_csv(found_path, index=False)
    missed_df.to_csv(missed_path, index=False)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"[OK] Wrote reference pairs: {reference_path}")
    print(f"[OK] Wrote found pairs:     {found_path}")
    print(f"[OK] Wrote missed pairs:    {missed_path}")
    print(f"[OK] Wrote summary:         {summary_path}")


def run_gs_dnb_gnd_evaluation(
    common_profiles_path: str | Path,
    predictions_path: str | Path,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    prepared_df = prepare_common_profiles_for_evaluation(
        common_profiles_path=common_profiles_path,
        config_path=config_path,
    )

    pred_df = load_predictions_dataframe(predictions_path)

    reference_df = build_reference_pairs_from_gnd(prepared_df)
    reference_df = annotate_prediction_blocking(reference_df)

    predicted_pairs_df = extract_predicted_gs_dnb_pairs(pred_df)
    metrics = compute_classification_metrics(
        reference_df=reference_df,
        predicted_pairs_df=predicted_pairs_df,
    )

    reference_with_eval_df, found_df, missed_df = compare_reference_to_predictions(
        reference_df=reference_df,
        predicted_pairs_df=predicted_pairs_df,
    )

    summary = build_summary(
        prepared_df=prepared_df,
        reference_df=reference_with_eval_df,
        found_df=found_df,
        missed_df=missed_df,
        predictions_file=predictions_path,
    )
    summary.update(metrics)

    return reference_with_eval_df, found_df, missed_df, summary


if __name__ == "__main__":
    predictions_file = MATCHING_OUTPUT_DIR / f"predictions_pairs.pkl"

    reference_df, found_df, missed_df, summary = run_gs_dnb_gnd_evaluation(
        common_profiles_path=COMMON_PROFILES_FILE,
        predictions_path=predictions_file,
        config_path=DEFAULT_CONFIG_PATH,
    )


    save_outputs(
        output_dir=EVAL_OUTPUT_DIR,
        reference_df=reference_df,
        found_df=found_df,
        missed_df=missed_df,
        summary=summary,
    )

    print()
    print("Evaluation summary")
    print("------------------")
    for key, value in summary.items():
        print(f"{key}: {value}")