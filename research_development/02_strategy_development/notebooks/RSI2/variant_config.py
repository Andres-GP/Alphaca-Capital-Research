"""
variant_config.py
=================
Loads a variant YAML and prepares its run folder.

Location: 02_strategy_development/<edge>/variant_config.py  (next to the engine and the notebooks)

Usage inside a notebook:
    from variant_config import load_variant, save_json
    cfg = load_variant("v1_qqq")
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

EDGE_DIR = Path(__file__).resolve().parent


def load_variant(variant: str) -> dict:
    # The YAML can live in any subfolder of variants/ (any name, any depth).
    base = EDGE_DIR / "variants"
    matches = sorted(base.rglob(f"{variant}.yaml"))
    if not matches:
        raise FileNotFoundError(f"No '{variant}.yaml' found under {base}")
    if len(matches) > 1:
        raise ValueError(
            f"'{variant}.yaml' exists in several folders, rename one: {[str(m) for m in matches]}"
        )
    path = matches[0]

    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Required blocks
    for block in ("id", "instrument", "split", "params", "grid"):
        if block not in cfg:
            raise KeyError(f"'{block}' is missing in {path.name}")

    # The chosen point must live inside the grid, otherwise plateau checks make no sense
    if cfg["params"]["sma_len"] not in cfg["grid"]["sma_values"]:
        raise ValueError("params.sma_len must be one of grid.sma_values")
    if cfg["params"]["rsi_thr"] not in cfg["grid"]["rsi_values"]:
        raise ValueError("params.rsi_thr must be one of grid.rsi_values")

    cfg["variant"] = variant
    cfg["oos_start_ts"] = pd.Timestamp(cfg["split"]["oos_start"])
    cfg["run_dir"] = EDGE_DIR / "runs" / variant
    cfg["run_dir"].mkdir(parents=True, exist_ok=True)
    return cfg


def _jsonable(o):
    """Fallback serializer for numpy / pandas objects."""
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, (pd.Timestamp, Path)):
        return str(o)
    return str(o)


def save_json(cfg: dict, name: str, payload: dict) -> Path:
    """Write payload to runs/<variant>/<name> as JSON and return the path."""
    out = cfg["run_dir"] / name
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_jsonable)
    print(f"Saved: {out}")
    return out