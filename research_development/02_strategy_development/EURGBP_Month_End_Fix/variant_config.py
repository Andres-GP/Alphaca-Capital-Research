"""
variant_config.py  (edge Month-End Fix)
=======================================
Loads a variant YAML and prepares its runs folder. Same API as the Monday Effect and RSI2 ones.

Location: 02_strategy_development/Month_End_Fix/variant_config.py  (next to the engine and variants/)

Use in a notebook:
    from variant_config import load_variant, save_json
    cfg = load_variant("v1_eurgbp")

Differences with the Monday Effect one:
  - There is NO grid. The rule (direction, window, calendar) is frozen before seeing results and sweeping windows
    or parameters is forbidden, so the YAML has no `grid` block and none is validated here.
  - Instead the rule is validated to be COMPLETE and coherent: declared side, intraday window in London time and
    a fresh-data date later than the OOS cut.
  - side = 'relative_equity' (v2) means the direction of each trade comes from the relative performance of two
    equity indices; it requires a `signal` block with the CSV of each index.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

EDGE_DIR = Path(__file__).resolve().parent

RULE_KEYS = ("side", "entry_hour", "exit_hour", "cost_bps_per_side")
SIDES = ("long", "short", "relative_equity")
SIGNAL_KEYS = ("index_a_csv", "index_b_csv")


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

    for block in ("id", "instrument", "split", "params"):
        if block not in cfg:
            raise KeyError(f"'{block}' is missing in {path.name}")
    if "grid" in cfg:
        raise ValueError("This edge has no grid: the rule is frozen, sweeping windows or parameters is not allowed")

    # The frozen rule must be complete and coherent
    p = cfg["params"]
    missing = [k for k in RULE_KEYS if k not in p]
    if missing:
        raise KeyError(f"params is missing {missing} in {path.name}")
    if p["side"] not in SIDES:
        raise ValueError(f"params.side must be one of {SIDES}")
    if not (0 <= p["entry_hour"] < p["exit_hour"] <= 23):
        raise ValueError("params: need 0 <= entry_hour < exit_hour <= 23 (intraday window, London local time)")
    if p["side"] == "relative_equity":
        sig = cfg.get("signal") or {}
        miss = [k for k in SIGNAL_KEYS if k not in sig]
        if miss:
            raise KeyError(f"side 'relative_equity' needs a `signal` block with {miss} in {path.name}")

    cfg["variant"] = variant
    cfg["oos_start_ts"] = pd.Timestamp(cfg["split"]["oos_start"])
    fresh = cfg["split"].get("fresh_start")        # data that was NEVER used to decide the rule
    cfg["fresh_start_ts"] = pd.Timestamp(fresh) if fresh else None
    if cfg["fresh_start_ts"] is not None and cfg["fresh_start_ts"] <= cfg["oos_start_ts"]:
        raise ValueError("split.fresh_start must be later than split.oos_start")
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