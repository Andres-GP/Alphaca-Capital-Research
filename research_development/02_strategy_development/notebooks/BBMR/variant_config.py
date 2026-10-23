"""
variant_config.py
=================
Loads a variant YAML and prepares its run folder.

Location: 02_strategy_development/<edge>/variant_config.py  (next to the engine and the notebooks)

Usage inside a notebook:
    from variant_config import load_variant, save_json, apply_engine_defaults

    cfg = load_variant("v1_qqq")
    apply_engine_defaults(cfg)          # opcional: set_engine_defaults(**cfg["engine_defaults"])
    # ... backtest / grid / walk-forward usando cfg["params"] y cfg["grid"]

Convención de grid (edge-agnóstica, ya NO hardcodeada a RSI(2)):
    Cada parámetro de 'params' que quiera barrerse debe tener en 'grid' una clave con la
    lista de valores permitidos. Nombres aceptados para esa clave (en este orden):
        1) "<param>_values"      p.ej. adx_thr        -> adx_thr_values
        2) "<param>"             p.ej. bb_len         -> bb_len
        3) alias corto, solo si el nombre termina en
           _len / _thr / _mult / _ratio / _bars / _pct:
                                 p.ej. sma_len        -> sma_values
                                      adx_thr        -> adx_values
                                      atr_stop_mult  -> atr_stop_values
                                      rejection_ratio-> rejection_values
    Los parámetros de 'params' sin clave en 'grid' se consideran FIJOS (no se barren).
    Se exige que al menos un parámetro esté gridded (para que el análisis de plateau
    tenga sentido).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import yaml

EDGE_DIR = Path(__file__).resolve().parent

# Sufijos aceptados para alias cortos de grid: "<base>_values" = valores de "<base>_<suf>"
_ALIAS_SUFFIXES: Sequence[str] = ("_len", "_thr", "_mult", "_ratio", "_bars", "_pct")

# Bloques obligatorios del YAML
_REQUIRED_BLOCKS: Sequence[str] = ("id", "instrument", "split", "params", "grid")

# Bloques opcionales, con defaults razonables
_OPTIONAL_DEFAULTS: Dict[str, Any] = {
    "engine_defaults": {},
    "notes": "",
}


# ---------------------------------------------------------------------------
# Resolución de ejes de grid
# ---------------------------------------------------------------------------
def _is_grid_values(v: Any) -> bool:
    """¿v es una colección de valores aceptables para un eje de grid?"""
    return isinstance(v, (list, tuple, range, np.ndarray, set))


def _resolve_grid_key(grid: Dict[str, Any], param: str) -> Optional[str]:
    """
    Devuelve la clave de `grid` que contiene los valores permitidos para `param`,
    o None si `param` no está gridded. Orden de preferencia:
       1) "<param>_values"
       2) "<param>"
       3) "<base>_values"  si `param` termina en un sufijo conocido (base = param sin sufijo)
    """
    if not isinstance(grid, dict):
        return None

    # 1) nombre largo: "<param>_values"
    key = f"{param}_values"
    if _is_grid_values(grid.get(key)):
        return key

    # 2) nombre exacto: "<param>"
    if _is_grid_values(grid.get(param)):
        return param

    # 3) alias corto
    for suf in _ALIAS_SUFFIXES:
        if param.endswith(suf):
            key = f"{param[:-len(suf)]}_values"
            if _is_grid_values(grid.get(key)):
                return key
    return None


def _validate_grid_coverage(cfg: Dict[str, Any]) -> Dict[str, str]:
    """
    Valida que cada eje declarado en `grid` sea efectivamente usado por `params` y
    que el valor elegido en `params` esté entre los permitidos.
    Devuelve {param: grid_key} para los parámetros gridded.
    """
    params: Dict[str, Any] = cfg["params"]
    grid: Dict[str, Any] = cfg["grid"]

    grid_map: Dict[str, str] = {}
    for pname, pval in params.items():
        gkey = _resolve_grid_key(grid, pname)
        if gkey is None:
            continue
        allowed = list(grid[gkey])
        if not allowed:
            raise ValueError(f"grid.{gkey} está vacío; un eje sin valores no tiene sentido.")
        if pval not in allowed:
            raise ValueError(
                f"params.{pname}={pval!r} no está en grid.{gkey}={allowed}. "
                f"El punto elegido debe pertenecer a la rejilla."
            )
        grid_map[pname] = gkey

    if not grid_map:
        raise ValueError(
            "Ningún parámetro de 'params' aparece en 'grid'. Nombra los ejes como "
            "'<param>_values' (o usa un alias: sma_len->sma_values, adx_thr->adx_values, ...)."
        )
    return grid_map


# ---------------------------------------------------------------------------
# Carga de variante
# ---------------------------------------------------------------------------
def load_variant(variant: str) -> dict:
    """Carga `variants/**/<variant>.yaml` y devuelve el cfg con run_dir y metadatos."""
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
    if not isinstance(cfg, dict):
        raise ValueError(f"{path} no contiene un mapeo YAML válido.")

    # Bloques obligatorios
    for block in _REQUIRED_BLOCKS:
        if block not in cfg:
            raise KeyError(f"'{block}' is missing in {path.name}")

    # Defaults de bloques opcionales
    for k, v in _OPTIONAL_DEFAULTS.items():
        cfg.setdefault(k, v)

    # Validación de tipos básicos
    if not isinstance(cfg["params"], dict):
        raise TypeError("'params' debe ser un mapping.")
    if not isinstance(cfg["grid"], dict):
        raise TypeError("'grid' debe ser un mapping.")
    if "oos_start" not in cfg["split"]:
        raise KeyError("split.oos_start is missing")

    # Validación del grid (edge-agnóstica)
    cfg["grid_map"] = _validate_grid_coverage(cfg)

    # Metadatos de ejecución
    cfg["variant"] = variant
    cfg["variant_path"] = path
    cfg["oos_start_ts"] = pd.Timestamp(cfg["split"]["oos_start"])
    cfg["run_dir"] = EDGE_DIR / "runs" / variant
    cfg["run_dir"].mkdir(parents=True, exist_ok=True)
    return cfg


# ---------------------------------------------------------------------------
# Serialización
# ---------------------------------------------------------------------------
def _jsonable(o: Any) -> Any:
    """Fallback serializer para objetos numpy / pandas / Path."""
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
    """Escribe `payload` en runs/<variant>/<name> (JSON) y devuelve la ruta."""
    out = cfg["run_dir"] / name
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_jsonable)
    print(f"Saved: {out}")
    return out


def save_yaml(cfg: dict, name: str, payload: dict) -> Path:
    """Escribe `payload` en runs/<variant>/<name> (YAML) y devuelve la ruta."""
    out = cfg["run_dir"] / name
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)
    print(f"Saved: {out}")
    return out


# ---------------------------------------------------------------------------
# Helper: aplicar engine defaults de la variante al motor
# ---------------------------------------------------------------------------
def apply_engine_defaults(cfg: dict, *, strict: bool = False) -> Optional[dict]:
    """
    Llama a `set_engine_defaults(**cfg["engine_defaults"])` del motor.
    Importa el módulo del motor desde el mismo directorio que este archivo.

    strict=False (default): si el motor no se puede importar o no tiene
    `set_engine_defaults`, se devuelve None sin romper el notebook.
    strict=True: propaga el ImportError / KeyError.
    """
    engine_defaults = cfg.get("engine_defaults") or {}
    if not engine_defaults:
        return None
    try:
        # El motor vive junto a este archivo. Se importa de forma perezosa para
        # no acoplar variant_config.py a un nombre concreto de módulo cuando
        # se trabaja en varios edges con estructuras distintas.
        import importlib
        import sys

        candidates = [
            "engine",                        # nombre canónico recomendado
            Path(__file__).stem + "_engine", # variante
        ]
        engine_mod = None
        for name in candidates:
            if name in sys.modules:
                engine_mod = sys.modules[name]
                break
        if engine_mod is None:
            # Búsqueda por archivo: cualquier .py en EDGE_DIR con set_engine_defaults
            import inspect
            for py in EDGE_DIR.glob("*.py"):
                if py.name in ("variant_config.py", "__init__.py"):
                    continue
                try:
                    mod = importlib.import_module(py.stem)
                except Exception:
                    continue
                if hasattr(mod, "set_engine_defaults"):
                    engine_mod = mod
                    break
        if engine_mod is None:
            if strict:
                raise ImportError("No se encontró el motor con set_engine_defaults().")
            return None

        applied = engine_mod.set_engine_defaults(**engine_defaults)
        print(f"Engine defaults applied for variant '{cfg['variant']}': {engine_defaults}")
        return applied
    except Exception:
        if strict:
            raise
        return None