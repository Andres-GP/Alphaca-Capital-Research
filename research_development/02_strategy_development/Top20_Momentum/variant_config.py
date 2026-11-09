"""variant_config.py (Top-N Momentum edge). load_variant("t20_sp500_v1") -> cfg dict; save_json(cfg, name, payload)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd, yaml

EDGE_DIR = Path(__file__).resolve().parent
VALID_EXEC = ("next_open", "close")
VALID_REBAL = ("first_trading_day", *(f"{o}_{d}" for o in ("first", "second", "third") for d in ("monday", "tuesday", "wednesday", "thursday", "friday")))

def load_variant(variant: str) -> dict:
    matches = sorted((EDGE_DIR / "variants").rglob(f"{variant}.yaml"))
    if len(matches) != 1: raise FileNotFoundError(f"expected exactly one '{variant}.yaml' under variants/, found {len(matches)}")
    cfg = yaml.safe_load(open(matches[0], encoding="utf-8"))
    for b in ("id", "instrument", "split", "params", "grid", "risk"):
        if b not in cfg: raise KeyError(f"'{b}' is missing in {matches[0].name}")
    P, G = cfg["params"], cfg["grid"]
    if P["lookback_days"] not in G["lookback_days_values"]: raise ValueError("params.lookback_days must be in grid.lookback_days_values")
    if P["top_n"] not in G["top_n_values"]: raise ValueError("params.top_n must be in grid.top_n_values")
    if P["exec_mode"] not in VALID_EXEC: raise ValueError(f"params.exec_mode must be one of {VALID_EXEC}")
    if P["rebalance"] not in VALID_REBAL: raise ValueError(f"params.rebalance must be one of {VALID_REBAL}")
    cfg["variant"], cfg["oos_start_ts"] = variant, pd.Timestamp(cfg["split"]["oos_start"])
    cfg["run_dir"] = EDGE_DIR / "runs" / variant; cfg["run_dir"].mkdir(parents=True, exist_ok=True)
    return cfg

def _j(o):
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.floating): return float(o)
    if isinstance(o, np.bool_): return bool(o)
    return str(o)

def save_json(cfg, name, payload):
    out = cfg["run_dir"] / name
    json.dump(payload, open(out, "w", encoding="utf-8"), indent=2, default=_j); print(f"Saved: {out}"); return out
