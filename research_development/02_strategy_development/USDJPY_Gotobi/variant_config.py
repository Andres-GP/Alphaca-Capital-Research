"""
variant_config.py  ·  02_strategy_development/Gotobi/variant_config.py   (v1.0)

Single source of truth for a Gotobi variant: reads variants/<name>.yaml, validates it and returns ONE normalised dict
that every notebook uses. Nothing is hard-coded in the notebooks.

    load_variant(name)            -> cfg (see keys below)
    save_json(cfg, file, payload) -> writes runs/<variant>/<file> (notebook results, read by the next notebook)
    load_json(cfg, file)          -> reads one of those files back
    list_variants()               -> names found in variants/
    rules_hash(cfg)               -> 8-char hash of the FROZEN rules (rule + costs + instrument window + risk)

cfg keys (besides the raw YAML sections: instrument, account, rule, costs, evidence_thresholds, acceptance, periods,
          splits, placebo_offsets_bdays, risk, open_items):
    id, variant, run_dir, oos_start_ts, params (= rule, alias shared with the other edges),
    engine_defaults (dict ready for gotobi_engine.set_engine_defaults)

Notebooks must set `variant_config.EDGE_DIR = EDGE_DIR` after importing (the folder that holds `variants/`).
Dependency: PyYAML.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import yaml

EDGE_DIR = Path(__file__).resolve().parent

REQUIRED = {
    "id": str,
    "instrument": ("symbol", "broker", "start", "data_csv", "time_mode"),
    "account": ("capital", "ccy", "cfd_preset"),
    "rule": ("gotobi_days", "include_month_end", "shift_rule", "holiday_source", "entry_time_jst", "exit_time_jst",
             "direction", "stop_bps"),
    "costs": ("cost_mode", "spread_scale", "robustness"),
    "evidence_thresholds": ("hypotheses_tested", "min_t_net"),
    "acceptance": ("pf_min", "n_min", "n_oos_min", "alpha", "t_oos_min", "max_signal_loss", "years_pos_min",
                   "breakeven_mult_min", "perm_draws", "seed", "roll_trades", "trades_per_year"),
    "periods": dict,
    "splits": ("is", "oos_start"),
    "placebo_offsets_bdays": list,
    "risk": ("hard_limit", "size_fraction"),
}


def _variants_dir() -> Path:
    return Path(EDGE_DIR) / "variants"


def list_variants() -> list[str]:
    return sorted(p.stem for p in _variants_dir().glob("*.yaml"))


def _validate(raw: dict, name: str) -> None:
    """Fail early with a readable message instead of deep inside a notebook."""
    errs = []
    for key, spec in REQUIRED.items():
        if key not in raw:
            errs.append(f"missing section '{key}'")
        elif isinstance(spec, tuple):
            errs += [f"missing '{key}.{k}'" for k in spec if k not in raw[key]]
        elif not isinstance(raw[key], spec):
            errs.append(f"'{key}' must be a {spec.__name__}")
    if errs:
        raise ValueError(f"variants/{name}.yaml is invalid: " + "; ".join(errs))

    rule, costs, ins = raw["rule"], raw["costs"], raw["instrument"]
    if rule["direction"] != "long":
        errs.append("rule.direction must be 'long' (the engine is long-only)")
    for k in ("entry_time_jst", "exit_time_jst"):
        if not re.fullmatch(r"\d{2}:\d{2}", str(rule[k])):
            errs.append(f"rule.{k} must be 'HH:MM'")
    if rule["shift_rule"] not in ("previous", "next", "none"):
        errs.append("rule.shift_rule must be previous | next | none")
    if rule["holiday_source"] == "csv" and not rule.get("calendar_csv"):
        errs.append("rule.holiday_source='csv' requires rule.calendar_csv")
    if costs["cost_mode"] not in ("feed", "flat_pips", "fixed"):
        errs.append("costs.cost_mode must be feed | flat_pips | fixed")
    if not costs["robustness"].get("flat_spread_pips"):
        errs.append("costs.robustness.flat_spread_pips must list at least one spread")
    start, oos = pd.Timestamp(ins["start"]), pd.Timestamp(raw["splits"]["oos_start"])
    if ins.get("end") and not start < oos < pd.Timestamp(ins["end"]):
        errs.append("splits.oos_start must lie between instrument.start and instrument.end")
    if oos <= start:
        errs.append("splits.oos_start must be after instrument.start")
    if raw["evidence_thresholds"]["hypotheses_tested"] < 1:
        errs.append("evidence_thresholds.hypotheses_tested must be >= 1")
    if errs:
        raise ValueError(f"variants/{name}.yaml is invalid: " + "; ".join(errs))
    if start < pd.Timestamp("2010-01-01"):
        print("WARNING: instrument.start < 2010-01-01. Before ~2010 the MT5 server clock / US DST rules differ and the "
              "feed spreads are 3-5 pips: the engine does not convert that part correctly.")


def _engine_defaults(raw: dict) -> dict:
    """Map the YAML sections to ENGINE_DEFAULTS keys (validated again by set_engine_defaults)."""
    i, r, c, k = raw["instrument"], raw["rule"], raw["costs"], raw["risk"]
    d = dict(
        csv_path=i["data_csv"], time_mode=i["time_mode"],
        gotobi_days=tuple(r["gotobi_days"]), include_month_end=bool(r["include_month_end"]),
        shift_rule=r["shift_rule"], holiday_source=r["holiday_source"], extra_holidays=tuple(r.get("extra_holidays") or ()),
        entry_time=str(r["entry_time_jst"]), exit_time=str(r["exit_time_jst"]), stop_bps=float(r["stop_bps"]),
        cost_mode=c["cost_mode"], spread_scale=float(c["spread_scale"]),
        financing_bps_per_night=float(c.get("financing_bps_per_night", 0.0)),
        max_entry_spread_pips=c.get("max_entry_spread_pips"), size_fraction=float(k["size_fraction"]),
    )
    if r["holiday_source"] == "csv":
        d["calendar_csv"] = r["calendar_csv"]
    return d


def rules_hash(cfg: dict) -> str:
    """Hash of everything that defines the frozen strategy: if it changes, the results are not comparable."""
    keep = {"instrument": {k: cfg["instrument"].get(k) for k in ("symbol", "broker", "start", "end", "time_mode")},
            "rule": cfg["rule"], "costs": cfg["costs"], "risk": cfg["risk"]}
    return hashlib.sha1(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:8]


def load_variant(name: str, verbose: bool = True) -> dict:
    path = _variants_dir() / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"{path} does not exist. Available variants: {list_variants()}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    _validate(raw, name)
    cfg = dict(raw)
    cfg["variant"] = name
    cfg["instrument"] = {**raw["instrument"], "end": raw["instrument"].get("end")}
    cfg["params"] = dict(raw["rule"])                       # alias used by the other edges' notebooks
    cfg["oos_start_ts"] = pd.Timestamp(raw["splits"]["oos_start"])
    cfg["engine_defaults"] = _engine_defaults(raw)
    cfg["run_dir"] = Path(EDGE_DIR) / "runs" / name
    cfg["run_dir"].mkdir(parents=True, exist_ok=True)

    if verbose:
        comm_yaml = raw["costs"].get("commission_bps_per_side")
        print(f"[load_variant] {name} | costs.commission_bps_per_side (YAML) = {comm_yaml} "
              f"| engine_defaults = {cfg['engine_defaults']}")
        if comm_yaml and "commission_bps_per_side" not in cfg["engine_defaults"]:
            print("[load_variant] WARNING: the YAML commission is NOT in engine_defaults "
                  "(_engine_defaults does not map it): apply it in the notebook (see the check cell).")
    return cfg


def _json_default(o):
    """JSON fallback for numpy / pandas / pathlib objects."""
    if hasattr(o, "item") and callable(o.item):
        try:
            return o.item()
        except (ValueError, TypeError):
            pass
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date, Path)):
        return str(o)
    if hasattr(o, "tolist"):
        return o.tolist()
    return str(o)


def save_json(cfg: dict, filename: str, payload: dict) -> Path:
    """Write runs/<variant>/<filename>. Adds the variant id, the rules hash and a UTC timestamp if absent."""
    out = {"variant": cfg["variant"], "id": cfg["id"], "rules_hash": rules_hash(cfg),
           "saved_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), **payload}
    path = Path(cfg["run_dir"]) / filename
    path.write_text(json.dumps(out, indent=2, default=_json_default, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {path}")
    return path


def load_json(cfg: dict, filename: str) -> dict:
    """Read a results file written by a previous notebook. Warns if the frozen rules changed since it was saved."""
    path = Path(cfg["run_dir"]) / filename
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found: run the notebook that produces it first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("rules_hash") not in (None, rules_hash(cfg)):
        print(f"WARNING: {filename} was saved with rules_hash={data['rules_hash']} but the YAML now hashes to "
              f"{rules_hash(cfg)}: the frozen rules changed, re-run the earlier notebooks.")
    return data