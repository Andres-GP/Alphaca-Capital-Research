"""
variant_config.py  (edge Efecto Lunes)
======================================
Carga un YAML de variante y prepara su carpeta de runs. Misma API que la del edge RSI2.

Ubicacion: 02_strategy_development/MondayEffect/variant_config.py  (junto al motor y a variants/)

Uso en un notebook:
    from variant_config import load_variant, save_json
    cfg = load_variant("base_btcusdt")

Unica diferencia con la de RSI2: la grilla es ATR-percentil x ATR-ventana
(grid.atr_pctl_values x grid.atr_len_values) y el punto elegido debe vivir dentro de ella.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

EDGE_DIR = Path(__file__).resolve().parent


def load_variant(variant: str) -> dict:
    # El YAML puede vivir en cualquier subcarpeta de variants/ (cualquier nombre, cualquier profundidad).
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

    # El punto elegido debe estar dentro de la grilla, si no el plateau no tiene sentido
    if cfg["params"]["atr_pctl"] not in cfg["grid"]["atr_pctl_values"]:
        raise ValueError("params.atr_pctl must be one of grid.atr_pctl_values")
    if cfg["params"]["atr_len"] not in cfg["grid"]["atr_len_values"]:
        raise ValueError("params.atr_len must be one of grid.atr_len_values")

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