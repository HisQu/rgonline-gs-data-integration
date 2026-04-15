import json
import re
from typing import Any, Dict, Iterable, List

import pandas as pd


PUNCT_AND_BRACKETS_RE = re.compile(r"[\.\,\;\:\!\?\(\)\[\]\{\}<>]+")
WHITESPACE_RE = re.compile(r"\s+")


def load_name_normalization_config(config_path: str) -> Dict[str, Any]:
    """Load the external JSON config for name normalization."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config.setdefault("remove_particles", [])
    config.setdefault("first_name_equivalents", {})
    return config


def ensure_list(value: Any) -> List[str]:
    """Normalize scalar/null/list values to a clean Python list of strings."""
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v).strip()]

    if value is None:
        return []

    try:
        if pd.isna(value):
            return []
    except Exception:
        pass

    text = str(value).strip()
    return [text] if text else []


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    """Deduplicate while preserving order."""
    seen = set()
    result = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_basic_name_text(text: Any) -> str:
    """
    Minimal mechanical normalization:
    - lowercase
    - remove punctuation and brackets
    - normalize whitespace
    """
    text = str(text or "").strip().lower()
    text = PUNCT_AND_BRACKETS_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_name_tokens(
    text: Any,
    remove_particles: List[str],
    first_name_equivalents: Dict[str, str],
) -> List[str]:
    """
    Tokenize and apply minimal token-wise normalization:
    - mechanical normalization first
    - split into tokens
    - remove particles
    - map given-name variants via external equivalence list
    """
    normalized = normalize_basic_name_text(text)
    if not normalized:
        return []

    particle_set = {p.lower() for p in remove_particles}
    first_name_map = {k.lower(): v.lower() for k, v in first_name_equivalents.items()}

    tokens = normalized.split()
    out = []

    for token in tokens:
        if token in particle_set:
            continue
        token = first_name_map.get(token, token)
        out.append(token)

    return out


def normalize_name_string(
    text: Any,
    remove_particles: List[str],
    first_name_equivalents: Dict[str, str],
) -> str:
    """Return normalized name as a single space-joined token string."""
    tokens = normalize_name_tokens(
        text=text,
        remove_particles=remove_particles,
        first_name_equivalents=first_name_equivalents,
    )
    return " ".join(tokens)


def normalize_name_list(
    names: List[str],
    remove_particles: List[str],
    first_name_equivalents: Dict[str, str],
) -> List[str]:
    """Normalize a list of names to normalized strings."""
    normalized = [
        normalize_name_string(
            text=name,
            remove_particles=remove_particles,
            first_name_equivalents=first_name_equivalents,
        )
        for name in ensure_list(names)
    ]
    normalized = [n for n in normalized if n]
    return unique_preserve_order(normalized)


def flatten_variant_tokens(
    names: List[str],
    remove_particles: List[str],
    first_name_equivalents: Dict[str, str],
) -> List[str]:
    """Tokenize all variant names and return one flat deduplicated token list."""
    all_tokens = []
    for name in ensure_list(names):
        all_tokens.extend(
            normalize_name_tokens(
                text=name,
                remove_particles=remove_particles,
                first_name_equivalents=first_name_equivalents,
            )
        )
    return unique_preserve_order(all_tokens)


def prepare_name_columns_for_matching(
    df: pd.DataFrame,
    config_path: str,
) -> pd.DataFrame:
    """
    Add minimal helper columns for the first name-matching step.

    New columns:
    - preferred_name_norm
    - preferred_name_tokens
    - preferred_first_token
    - preferred_last_token
    - variant_names_norm
    - variant_name_tokens
    """
    config = load_name_normalization_config(config_path)
    remove_particles = config["remove_particles"]
    first_name_equivalents = config["first_name_equivalents"]

    out = df.copy()

    out["variant_names"] = out["variant_names"].apply(ensure_list)

    out["preferred_name_norm"] = out["preferred_name"].apply(
        lambda x: normalize_name_string(
            text=x,
            remove_particles=remove_particles,
            first_name_equivalents=first_name_equivalents,
        )
    )

    out["preferred_name_tokens"] = out["preferred_name"].apply(
        lambda x: normalize_name_tokens(
            text=x,
            remove_particles=remove_particles,
            first_name_equivalents=first_name_equivalents,
        )
    )

    out["preferred_first_token"] = out["preferred_name_tokens"].apply(
        lambda toks: toks[0] if toks else None
    )
    out["preferred_last_token"] = out["preferred_name_tokens"].apply(
        lambda toks: toks[-1] if toks else None
    )

    out["variant_names_norm"] = out["variant_names"].apply(
        lambda names: normalize_name_list(
            names=names,
            remove_particles=remove_particles,
            first_name_equivalents=first_name_equivalents,
        )
    )

    out["variant_name_tokens"] = out["variant_names"].apply(
        lambda names: flatten_variant_tokens(
            names=names,
            remove_particles=remove_particles,
            first_name_equivalents=first_name_equivalents,
        )
    )

    out["all_name_tokens"] = out.apply(
        lambda row: combine_all_name_tokens(
            preferred_tokens=row["preferred_name_tokens"],
            variant_tokens=row["variant_name_tokens"],
        ),
        axis=1,
    )

    return out

def preferred_variant_best_jw_sql() -> str:
    """
    Symmetric best Jaro-Winkler similarity between preferred_name_norm on one side
    and variant_names_norm on the other side.

    Score = max(
        best_jw(preferred_l, each variant_r),
        best_jw(preferred_r, each variant_l)
    )

    Empty strings are treated like missing values via NULLIF(..., '').
    Empty variant lists naturally collapse to NULL inside list_max(...),
    which we then coalesce to 0.0.
    """

    left_pref_vs_right_vars = """
    coalesce(
        list_max(
            list_transform(
                list_filter(
                    "variant_names_norm_r",
                    lambda x: x IS NOT NULL AND x <> ''
                ),
                lambda x: jaro_winkler_similarity(
                    NULLIF("preferred_name_norm_l", ''),
                    x
                )
            )
        ),
        0.0
    )
    """

    right_pref_vs_left_vars = """
    coalesce(
        list_max(
            list_transform(
                list_filter(
                    "variant_names_norm_l",
                    lambda x: x IS NOT NULL AND x <> ''
                ),
                lambda x: jaro_winkler_similarity(
                    NULLIF("preferred_name_norm_r", ''),
                    x
                )
            )
        ),
        0.0
    )
    """
    return f"greatest(({left_pref_vs_right_vars}), ({right_pref_vs_left_vars}))"
    

def combine_all_name_tokens(
        preferred_tokens: List[str],
        variant_tokens: List[str],
    ) -> List[str]:
        """Combine preferred + variant tokens into one deduplicated token list."""
        return unique_preserve_order(
            list(preferred_tokens or []) + list(variant_tokens or [])
        )