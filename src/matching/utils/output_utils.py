from pathlib import Path

import pandas as pd


DEFAULT_PROFILE_DISPLAY_COLUMNS = [
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
]


def build_pair_display_columns(
    pred_df: pd.DataFrame,
    base_columns: list[str] | None = None,
    include_score_columns: bool = True,
) -> list[str]:
    """
    Build output columns for pairwise rows with left/right values.

    Most fields are expected as <field>_l / <field>_r.
    Splink source fields may appear as source_dataset_l / source_dataset_r.
    """
    profile_columns = base_columns or DEFAULT_PROFILE_DISPLAY_COLUMNS
    columns: list[str] = []

    for base_col in profile_columns:
        if base_col == "source":
            left_candidates = ["source_dataset_l", "source_l"]
            right_candidates = ["source_dataset_r", "source_r"]
        else:
            left_candidates = [f"{base_col}_l"]
            right_candidates = [f"{base_col}_r"]

        left_col = next((c for c in left_candidates if c in pred_df.columns), None)
        right_col = next((c for c in right_candidates if c in pred_df.columns), None)

        if left_col is not None:
            columns.append(left_col)
        if right_col is not None:
            columns.append(right_col)

    if not include_score_columns:
        return columns

    score_cols = [c for c in ["match_probability", "match_weight"] if c in pred_df.columns]
    return score_cols + columns


def export_dataframe_to_csv(
    df: pd.DataFrame,
    output_path: str | Path,
    top_k: int | None = None,
    columns: list[str] | None = None,
    include_index: bool = False,
) -> Path:
    """
    Export a dataframe (optionally top-k rows) to CSV.

    The dataframe is assumed to already be sorted as desired.
    """
    if top_k is not None and top_k <= 0:
        raise ValueError("top_k must be a positive integer when provided")

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    export_df = df.head(top_k) if top_k is not None else df

    if columns is not None:
        missing_columns = [col for col in columns if col not in export_df.columns]
        if missing_columns:
            raise ValueError(f"Missing columns in dataframe: {missing_columns}")
        export_df = export_df.loc[:, columns]

    export_df.to_csv(out_path, index=include_index)

    return out_path