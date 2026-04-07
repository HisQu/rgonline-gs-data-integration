import json
import re
from typing import Any, Dict, Iterable, List

import pandas as pd


PUNCT_AND_BRACKETS_RE = re.compile(r"[\.\,\;\:\!\?\(\)\[\]\{\}<>]+")
WHITESPACE_RE = re.compile(r"\s+")


def load_place_normalization_config(config_path: str) -> Dict[str, Any]:
    """
    Load optional place-normalization settings from the shared JSON config.

    Expected optional keys:
    - place_equivalents: dict[str, str]
    - place_remove_particles: list[str]
    - place_remove_context_tokens: list[str]
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config.setdefault("place_equivalents", {})
    config.setdefault("place_remove_particles", [])
    config.setdefault("place_remove_context_tokens", [])
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


def normalize_basic_place_text(text: Any) -> str:
    """
    Minimal mechanical normalization for place strings:
    - lowercase
    - remove punctuation and brackets
    - normalize whitespace
    """
    text = str(text or "").strip().lower()
    text = PUNCT_AND_BRACKETS_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_place_tokens(
    text: Any,
    place_equivalents: Dict[str, str],
    place_remove_particles: List[str],
    place_remove_context_tokens: List[str],
) -> List[str]:
    """
    Tokenize and apply place normalization:
    - mechanical normalization first
    - split into tokens
    - map orthographic place variants via external equivalence list
    - remove place-specific particles
    - remove place-specific context/institution tokens
    """
    normalized = normalize_basic_place_text(text)
    if not normalized:
        return []

    token_map = {k.lower(): v.lower() for k, v in place_equivalents.items()}
    remove_particles = {t.lower() for t in place_remove_particles}
    remove_context = {t.lower() for t in place_remove_context_tokens}

    tokens = normalized.split()
    out = []

    for token in tokens:
        token = token_map.get(token, token)

        if token in remove_particles:
            continue
        if token in remove_context:
            continue

        out.append(token)

    return out


def normalize_place_string(
    text: Any,
    place_equivalents: Dict[str, str],
    place_remove_particles: List[str],
    place_remove_context_tokens: List[str],
) -> str:
    """Return normalized place as a single space-joined token string."""
    tokens = normalize_place_tokens(
        text=text,
        place_equivalents=place_equivalents,
        place_remove_particles=place_remove_particles,
        place_remove_context_tokens=place_remove_context_tokens,
    )
    return " ".join(tokens)


def normalize_place_list(
    places: List[str],
    place_equivalents: Dict[str, str],
    place_remove_particles: List[str],
    place_remove_context_tokens: List[str],
) -> List[str]:
    """Normalize a list of place strings to normalized strings."""
    normalized = [
        normalize_place_string(
            text=place,
            place_equivalents=place_equivalents,
            place_remove_particles=place_remove_particles,
            place_remove_context_tokens=place_remove_context_tokens,
        )
        for place in ensure_list(places)
    ]
    normalized = [p for p in normalized if p]
    return unique_preserve_order(normalized)


def flatten_place_tokens(
    places: List[str],
    place_equivalents: Dict[str, str],
    place_remove_particles: List[str],
    place_remove_context_tokens: List[str],
) -> List[str]:
    """Tokenize all place strings and return one flat deduplicated token list."""
    all_tokens = []
    for place in ensure_list(places):
        all_tokens.extend(
            normalize_place_tokens(
                text=place,
                place_equivalents=place_equivalents,
                place_remove_particles=place_remove_particles,
                place_remove_context_tokens=place_remove_context_tokens,
            )
        )
    return unique_preserve_order(all_tokens)


def prepare_place_columns_for_matching(
    df: pd.DataFrame,
    config_path: str,
) -> pd.DataFrame:
    """
    Add helper columns for place matching.

    New columns:
    - places_norm
    - place_tokens
    """
    config = load_place_normalization_config(config_path)
    place_equivalents = config["place_equivalents"]
    place_remove_particles = config["place_remove_particles"]
    place_remove_context_tokens = config["place_remove_context_tokens"]

    out = df.copy()

    out["places"] = out["places"].apply(ensure_list)

    out["places_norm"] = out["places"].apply(
        lambda places: normalize_place_list(
            places=places,
            place_equivalents=place_equivalents,
            place_remove_particles=place_remove_particles,
            place_remove_context_tokens=place_remove_context_tokens,
        )
    )

    out["place_tokens"] = out["places"].apply(
        lambda places: flatten_place_tokens(
            places=places,
            place_equivalents=place_equivalents,
            place_remove_particles=place_remove_particles,
            place_remove_context_tokens=place_remove_context_tokens,
        )
    )

    return out


def sql_nonempty_places(side: str) -> str:
    """
    Return a filtered place array expression without NULL/empty elements.
    side must be "l" or "r".
    """
    if side not in {"l", "r"}:
        raise ValueError("side must be 'l' or 'r'")

    return (
        f'list_filter("places_norm_{side}", lambda x: x IS NOT NULL AND x <> \'\')'
    )


def sql_any_place_pair(predicate_sql_template: str) -> str:
    """
    Return SQL that checks whether ANY pair (lval, rval) across places_norm_l/r
    satisfies the given predicate.

    The template receives the placeholders:
    - {lval}
    - {rval}
    """
    places_l = sql_nonempty_places("l")
    places_r = sql_nonempty_places("r")

    predicate = predicate_sql_template.format(lval="lval", rval="rval")

    return (
        f"list_count("
        f"  list_filter("
        f"    {places_l}, "
        f"    lambda lval: list_count("
        f"      list_filter("
        f"        {places_r}, "
        f"        lambda rval: {predicate}"
        f"      )"
        f"    ) > 0"
        f"  )"
        f") > 0"
    )


def sql_missing_places() -> str:
    """Missing if one side has no usable normalized place values."""
    places_l = sql_nonempty_places("l")
    places_r = sql_nonempty_places("r")

    return (
        f'("places_norm_l" IS NULL OR list_count({places_l}) = 0 '
        f'OR "places_norm_r" IS NULL OR list_count({places_r}) = 0)'
    )