import json
from pathlib import Path
from typing import Any


def load_shared_normalization_config(config_path: str | Path) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config.setdefault("gs_org_place_prefixes", [])
    config.setdefault(
        "gs_org_place_locative_markers",
        ["in", "im", "zu", "zum", "zur", "bei", "am", "an der", "an dem"],
    )
    config.setdefault(
        "gs_org_place_non_place_starters",
        ["st.", "st", "sankt", "san", "santa", "hl.", "hl", "heilig"],
    )
    return config