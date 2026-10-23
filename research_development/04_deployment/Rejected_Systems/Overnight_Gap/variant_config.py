"""
variant_config.py
=================
Carga una variante YAML y prepara la carpeta de run.

Ubicación: 02_strategy_development/<edge>/variant_config.py
Uso:
    from variant_config import load_variant, save_json, apply_engine_defaults

    cfg = load_variant("v1_us500_gap")
    apply_engine_defaults(cfg)
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import yaml

EDGE_DIR = Path(__file__).resolve().parent

# Sufijos cortos aceptados para alias de grid
_ALIAS_SUFFIXES: Sequence[str] = ("_len", "_thr", "_mult", "_ratio", "_bars", "_pct", "_minutes", "_days")

_REQUIRED_BLOCKS: Sequence[str] = ("id", "instrument", "split", "params", "grid")
_OPTIONAL_DEFAULTS: Dict[str, Any] = {"engine_defaults": {}, "notes": "", "edge": None}


# ---------------------------------------------------------------------------
# Resolución de ejes
# ---------------------------------------------------------------------------
def _is_grid_values(v: Any) -> bool:
    return isinstance(v, (list, tuple, range, np.ndarray, set))


def _resolve_grid_key(grid: Dict[str, Any], param: str) -> Optional[str]:
    """Clave de `grid` para `param` o None si no está gridded."""
    if not isinstance(grid, dict):
        return None
    # 1) <param>_values
    key = f"{param}_values"
    if _is_grid_values(grid.get(key)):
        return key
    # 2) <param>
    if _is_grid_values(grid.get(param)):
        return param
    # 3) alias corto
    for suf in _ALIAS_SUFFIXES:
        if param.endswith(suf):
            k = f"{param[:-len(suf)]}_values"
            if _is_grid_values(grid.get(k)):
                return k
    return None


def _validate_grid_coverage(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Devuelve {param: grid_key} para los params gridded; valida que `chosen` esté en `allowed`."""
    params: Dict[str, Any] = cfg["params"]
    grid:   Dict[str, Any] = cfg["grid"]

    grid_map: Dict[str, str] = {}
    for pname, pval in params.items():
        gkey = _resolve_grid_key(grid, pname)
        if gkey is None:
            continue
        allowed = list(grid[gkey])
        if not allowed:
            raise ValueError(f"grid.{gkey} está vacío")
        # FIX: comparación numérica tolerante (0.1+0.2 vs 0.3, 1 vs 1.0)
        if not any(_same_value(pval, a) for a in allowed):
            raise ValueError(
                f"params.{pname}={pval!r} no está en grid.{gkey}={allowed}. "
                f"El punto elegido debe pertenecer a la rejilla."
            )
        grid_map[pname] = gkey

    if not grid_map:
        raise ValueError(
            "Ningún parámetro de 'params' aparece en 'grid'. Nombra los ejes "
            "como '<param>_values' o usa un alias: "
            "gap_mr_max_pct → gap_mr_max_pct_values, tf_hold_days → tf_hold_days_values, etc."
        )
    return grid_map


def _same_value(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float, np.number)) and isinstance(b, (int, float, np.number)):
        return bool(np.isclose(float(a), float(b), rtol=0.0, atol=1e-12))
    return a == b


def _group_grid(cfg: Dict[str, Any]) -> Dict[str, Dict[str, List[Any]]]:
    """
    Agrupa ejes por sub-estrategia usando `grid.groups` (opcional):

        grid:
          groups:
            mr: [gap_min_trade_values, mr_fill_target_values]   # clave de grid O nombre del param
            tf: [tf_target_mult_values]

    Si el YAML no declara grupos, todo queda en `cfg["grid_groups"]["all"]`.
    Cada clave se resuelve a su `params.<param>`; si no se puede mapear se emite WARNING y se ignora.
    """
    grid_groups_yaml = cfg["grid"].get("groups") or {}
    params = cfg["params"]

    out: Dict[str, Dict[str, List[Any]]] = {}
    if not grid_groups_yaml:
        out["all"] = {p: list(cfg["grid"][gk]) for p, gk in cfg["grid_map"].items()}
        return out

    for gname, keys in grid_groups_yaml.items():
        bucket: Dict[str, List[Any]] = {}
        for gkey in keys:
            matched: Optional[str] = None
            if gkey in cfg["grid_map"]:                      # FIX: también se acepta el nombre del param
                matched = gkey
            else:
                for p in params:
                    if _resolve_grid_key(cfg["grid"], p) == gkey:
                        matched = p
                        break
            if matched is None:
                print(f"WARNING: grid.groups.{gname}: '{gkey}' no mapea a ningún param. Se ignora.")
                continue
            bucket[matched] = list(cfg["grid"][cfg["grid_map"][matched]])
        if bucket:
            out[gname] = bucket

    out["all"] = {p: list(cfg["grid"][gk]) for p, gk in cfg["grid_map"].items()}
    return out


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def load_variant(variant: str) -> dict:
    base = EDGE_DIR / "variants"
    matches = sorted(base.rglob(f"{variant}.yaml"))
    if not matches:
        raise FileNotFoundError(f"No '{variant}.yaml' found under {base}")
    if len(matches) > 1:
        raise ValueError(f"'{variant}.yaml' existe en varias carpetas: {[str(m) for m in matches]}")
    path = matches[0]

    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path} no contiene un mapping YAML válido")

    for block in _REQUIRED_BLOCKS:
        if block not in cfg:
            raise KeyError(f"'{block}' is missing in {path.name}")
    for k, v in _OPTIONAL_DEFAULTS.items():
        if k not in cfg or cfg[k] is None and k == "engine_defaults":
            cfg[k] = copy.deepcopy(v)                         # FIX: no compartir el {} mutable entre llamadas

    if not isinstance(cfg["params"], dict): raise TypeError("'params' debe ser un mapping")
    if not isinstance(cfg["grid"],   dict): raise TypeError("'grid' debe ser un mapping")
    if not isinstance(cfg["split"],  dict): raise TypeError("'split' debe ser un mapping")
    if "oos_start" not in cfg["split"]:     raise KeyError("split.oos_start is missing")
    if not isinstance(cfg["engine_defaults"], dict): raise TypeError("'engine_defaults' debe ser un mapping")

    # Validación edge-agnóstica
    cfg["grid_map"]    = _validate_grid_coverage(cfg)
    cfg["grid_groups"] = _group_grid(cfg)
    cfg["params_barred"] = sorted(cfg["grid_map"].keys())

    # Metadatos
    cfg["variant"]        = variant
    cfg["variant_path"]   = path
    cfg["oos_start_ts"]   = pd.Timestamp(cfg["split"]["oos_start"])
    cfg["run_dir"]        = EDGE_DIR / "runs" / variant
    cfg["run_dir"].mkdir(parents=True, exist_ok=True)
    return cfg


# ---------------------------------------------------------------------------
# Serialización
# ---------------------------------------------------------------------------
def _jsonable(o: Any) -> Any:
    if isinstance(o, np.integer):   return int(o)
    if isinstance(o, np.floating):  return float(o)
    if isinstance(o, np.bool_):     return bool(o)
    if isinstance(o, np.ndarray):   return o.tolist()          # FIX: antes se guardaba como str
    if isinstance(o, (pd.Timestamp, Path)): return str(o)
    if isinstance(o, (set, frozenset)): return sorted(o, key=str)
    return str(o)


def save_json(cfg: dict, name: str, payload: dict) -> Path:
    out = cfg["run_dir"] / name
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_jsonable)
    print(f"Saved: {out}")
    return out


def save_yaml(cfg: dict, name: str, payload: dict) -> Path:
    out = cfg["run_dir"] / name
    # FIX: yaml.safe_dump no sabe serializar np.float64 / Timestamp / Path -> normalizar vía JSON
    clean = json.loads(json.dumps(payload, default=_jsonable))
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(clean, f, sort_keys=False, allow_unicode=True)
    print(f"Saved: {out}")
    return out


# ---------------------------------------------------------------------------
# Engine defaults
# ---------------------------------------------------------------------------
_ENGINE_MODULE_NAMES = ("overnight_gap_engine", "gap_engine", "bbmr_engine", "rsi2_engine", "engine")


def _find_engine_module():
    import importlib
    for name in _ENGINE_MODULE_NAMES:
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "set_engine_defaults"):
            return mod
    # FIX: el motor vive en <edge>/<carpeta>/*_engine.py, no solo en <edge>/*.py
    paths = [EDGE_DIR, *[d for d in EDGE_DIR.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]]
    for d in paths:
        for py in sorted(d.glob("*engine*.py")):
            if str(d) not in sys.path:
                sys.path.insert(0, str(d))
            try:
                mod = importlib.import_module(py.stem)
            except Exception:
                continue
            if hasattr(mod, "set_engine_defaults"):
                return mod
    return None


def apply_engine_defaults(cfg: dict, *, strict: bool = False) -> Optional[dict]:
    engine_defaults = cfg.get("engine_defaults") or {}
    if not engine_defaults:
        return None
    engine_mod = _find_engine_module()
    if engine_mod is None:
        if strict:
            raise ImportError("No engine module with set_engine_defaults() found")
        print("WARNING: no engine module found; engine_defaults NOT applied.")
        return None
    # FIX: antes un KeyError por una clave mal escrita en el YAML se tragaba en silencio
    applied = engine_mod.set_engine_defaults(**engine_defaults)
    print(f"Engine defaults applied for '{cfg['variant']}': {engine_defaults}")
    return applied