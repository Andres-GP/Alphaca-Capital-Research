"""
variant_config.py  (Weekly Momentum edge)
=========================================
Loads a variant YAML and prepares its runs folder. Same API as the Monday Effect / RSI2 edges.

Location: 02_strategy_development/ETHUSD_Weekly_Momentum/variant_config.py  (next to the engine and to variants/)

Usage in a notebook:
    from variant_config import load_variant, save_json
    cfg = load_variant("v1_ethusd")            # both legs (research rules)
    cfg = load_variant("v2_ethusd_long")       # long only

Only difference from the Monday Effect one: the grid is lookback x holding period
(grid.lookback_days_values x grid.hold_days_values) and the chosen point must live inside it.

v2: params.direction and params.cost_mode are validated here, so a typo in a variant fails at load time with a
clear message instead of deep inside the engine (the engine only accepts these values).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

EDGE_DIR = Path(__file__).resolve().parent

VALID_DIRECTIONS = ("both", "long_only", "short_only")
VALID_COST_MODES = ("spread", "fixed")


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

    for block in ("id", "instrument", "split", "params", "grid"):
        if block not in cfg:
            raise KeyError(f"'{block}' is missing in {path.name}")

    # The chosen point must be inside the grid, otherwise the plateau makes no sense
    if cfg["params"]["lookback_days"] not in cfg["grid"]["lookback_days_values"]:
        raise ValueError("params.lookback_days must be one of grid.lookback_days_values")
    if cfg["params"]["hold_days"] not in cfg["grid"]["hold_days_values"]:
        raise ValueError("params.hold_days must be one of grid.hold_days_values")

    # Same values the engine accepts: fail here, not in the middle of a backtest
    if cfg["params"].get("direction") not in VALID_DIRECTIONS:
        raise ValueError(f"params.direction must be one of {VALID_DIRECTIONS}, got {cfg['params'].get('direction')!r} in {path.name}")
    if cfg["params"].get("cost_mode") not in VALID_COST_MODES:
        raise ValueError(f"params.cost_mode must be one of {VALID_COST_MODES}, got {cfg['params'].get('cost_mode')!r} in {path.name}")

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
        return str(o)    return str(o)


def save_json(cfg: dict, name: str, payload: dict) -> Path:
    """Write payload to runs/<variant>/<name> as JSON and return the path."""
    out = cfg["run_dir"] / name
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_jsonable)
    print(f"Saved: {out}")
    return out