"""
long_only_check.py  (v2)  ·  ETHUSD_Weekly_Momentum/long_only_check.py

Evaluates ONE pre-declared change to v1: drop the short leg (direction="long_only"). Nothing else changes:
same data, same instrument.start, same IS/OOS split, same cost model, same lookback/hold. It reads the config of
a variant (single source of truth) and ignores its `direction`: the reference is always "both" and the candidate
is always "long_only", so you can point it at EITHER yaml (v1_ethusd or v2_ethusd_long) and get the same answer.

Why a separate script as well as the patched notebook 01: this one is a one-shot comparison v1 vs long-only with
the multiple-trials correction; the patched notebook judges the variant you select with VARIANT = "...".

Honest bookkeeping (printed at the end):
  - This variant was chosen AFTER seeing the full-sample results of v1 (the short leg had t = 0.68). Its OOS is
    therefore NOT independent. It counts as trial #2 on this dataset, so the permutation gate uses
    alpha / N_TRIALS instead of alpha.
  - Even if every gate passes, the result is a "conditional candidate" that needs forward data.

Run from the edge folder:   python long_only_check.py [variant]     (default: v1_ethusd)
                       or   %run long_only_check.py [variant]       in Jupyter
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---- same thresholds as notebook 01 ----
PF_MIN, T_MIN, N_MIN, N_OOS_MIN = 1.3, 2.0, 100, 30
ALPHA, N_PERM = 0.05, 5000
N_TRIALS = 2                                   # v1 (both legs) + this long-only variant, same dataset
HARD_LIMIT = 0.09
CAP_GRID = [1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000, 10000]
CAPITAL = 2_000.0
SEED = 20260107
DEFAULT_VARIANT = "v1_ethusd"


def tstat(x) -> float:
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def profit_factor(x) -> float:
    x = np.asarray(x, float)
    gain, loss = x[x > 0].sum(), -x[x < 0].sum()
    return float(gain / loss) if loss > 0 else float("inf")


def perm_p(raw, is_long, rng, n_perm=N_PERM):
    """Does picking the long weeks with momentum beat picking the SAME NUMBER of weeks at random?
    Statistic: mean price move (%) of the selected weeks. This controls for the ETH drift."""
    raw, is_long = np.asarray(raw, float), np.asarray(is_long, bool)
    k = int(is_long.sum())
    if k == 0 or k == len(raw):
        return dict(p=float("nan"), obs=float("nan"), null=float("nan"), k=k)
    obs = float(raw[is_long].mean())
    pick = np.argsort(rng.random((n_perm, len(raw))), axis=1)[:, :k]
    null = raw[pick].mean(axis=1)
    return dict(p=float((1 + (null >= obs).sum()) / (n_perm + 1)), obs=obs, null=float(null.mean()), k=k)


def summarize(label, trades, oos_start):
    et = pd.to_datetime(trades["entry_time"])
    rows = []
    for per, sub in (("IS", trades[et < oos_start]), ("OOS", trades[et >= oos_start]), ("All", trades)):
        x = sub["pnl"].to_numpy(float)
        rows.append({"Variant": label, "Period": per, "Trades": len(x), "Mean net %": x.mean() if len(x) else np.nan,
                     "t-stat": tstat(x), "PF": profit_factor(x) if len(x) else np.nan,
                     "Win %": 100 * (x > 0).mean() if len(x) else np.nan})
    return pd.DataFrame(rows)


def run(cfg, save=True, eng=None, save_json=None):
    if eng is None:
        import weekly_momentum_engine as eng
        importlib.reload(eng)
    eng.set_engine_defaults(**cfg.get("engine_defaults", {}))
    P = cfg["params"]
    rules = dict(lookback_days=P["lookback_days"], hold_days=P["hold_days"], entry_dow=P["entry_dow"],
                 entry_hour=P["entry_hour"], direction="both", cost_mode=P["cost_mode"],
                 cost_bps_per_side=P["cost_bps_per_side"])

    df = eng.prepare(eng.load_data(cfg["instrument"]["ticker"], start=cfg["instrument"]["start"]),
                     lookback_days=rules["lookback_days"], entry_dow=rules["entry_dow"], entry_hour=rules["entry_hour"])
    n_is = int((df.index < cfg["oos_start_ts"]).sum())
    oos_start = df.index[n_is]

    t_both = eng.run_weekly_backtest(df, **rules)
    t_long = eng.run_weekly_backtest(df, **{**rules, "direction": "long_only"})
    assert (t_long["side"] > 0).all() and len(t_long) == int((t_both["side"] > 0).sum()), "long_only != long weeks of v1"

    # ---------------- 1. IS / OOS table, v1 next to long-only ----------------
    tab = pd.concat([summarize("v1 both legs", t_both, oos_start), summarize("Long only", t_long, oos_start)],
                    ignore_index=True)
    print("=" * 80)
    print(f"LONG-ONLY CHECK · {cfg['id']} · OOS from {oos_start:%Y-%m-%d} · data {df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}")
    print("=" * 80)
    print(tab.round(3).to_string(index=False))

    # ---------------- 2. Permutation: momentum long weeks vs random weeks of the same count ----------------
    wk = t_both.copy()
    wk["raw"] = wk["side"] * wk["gross_pct"]                      # price move of the week (%), no sign
    wk["is_long"] = wk["side"] > 0
    is_mask = pd.to_datetime(wk["entry_time"]) < oos_start
    rng = np.random.default_rng(SEED)
    perms = {}
    for per, m in (("IS", is_mask), ("OOS", ~is_mask), ("All", np.ones(len(wk), bool))):
        perms[per] = perm_p(wk.loc[m, "raw"], wk.loc[m, "is_long"], rng)
    print("\nPERMUTATION (mean price move of the long weeks vs the same number of random weeks)")
    for per, r in perms.items():
        print(f"   {per:>3}: long weeks {r['k']:>3} | observed {r['obs']:+.2f}% vs random {r['null']:+.2f}% | p = {r['p']:.3f}")

    # ---------------- 3. Hard limit with the minimum lot, by capital ----------------
    rows, cap_needed = [], None
    for cap in CAP_GRID:
        ls = eng.cfd_trade_sizes(t_long, cap, target_fraction=0.0001, below_min_lot="min_lot")
        rep = eng.hard_limit_report_intrabar(df, t_long, HARD_LIMIT, sizing=ls["size_fraction"].to_numpy())
        rows.append({"Capital": cap, "Max DD (intra-candle) %": rep["max_dd"] * 100, "Hard limit": "PASS" if rep["passed"] else "FAIL"})
        if rep["passed"] and cap_needed is None:
            cap_needed = cap
    print(f"\nMINIMUM LOT ON EVERY TRADE (long only), hard limit -{HARD_LIMIT:.0%}")
    print(pd.DataFrame(rows).round(1).to_string(index=False))
    print(f"Smallest capital in the grid that respects the limit: {cap_needed}")

    cap_use = float(cap_needed if cap_needed is not None else CAP_GRID[-1])
    ls = eng.cfd_trade_sizes(t_long, cap_use, target_fraction=0.0001, below_min_lot="min_lot")
    hourly = eng.hourly_returns(df, t_long, sizing=ls["size_fraction"].to_numpy())
    annual = eng.annual_returns(hourly, t_long, HARD_LIMIT)
    print(f"\nANNUAL (minimum lot, capital {cap_use:,.0f})")
    print(annual.round(3).to_string(index=False))

    # ---------------- 4. Gates ----------------
    g = {r["Period"]: r for _, r in tab[tab["Variant"] == "Long only"].iterrows()}
    alpha_adj = ALPHA / N_TRIALS
    checks = [
        (f"Trades, full period >= {N_MIN}", g["All"]["Trades"] >= N_MIN, f"{int(g['All']['Trades'])}"),
        (f"Trades, OOS >= {N_OOS_MIN}", g["OOS"]["Trades"] >= N_OOS_MIN, f"{int(g['OOS']['Trades'])}"),
        (f"Profit Factor, IS >= {PF_MIN}", g["IS"]["PF"] >= PF_MIN, f"{g['IS']['PF']:.3f}"),
        (f"Profit Factor, OOS >= {PF_MIN}", g["OOS"]["PF"] >= PF_MIN, f"{g['OOS']['PF']:.3f}"),
        (f"t-stat >= {T_MIN:g} in IS", g["IS"]["t-stat"] >= T_MIN, f"{g['IS']['t-stat']:.2f}"),
        (f"t-stat >= {T_MIN:g} in OOS", g["OOS"]["t-stat"] >= T_MIN, f"{g['OOS']['t-stat']:.2f}"),
        (f"Permutation p < {alpha_adj:.3f} (IS, corrected for {N_TRIALS} trials)", perms["IS"]["p"] < alpha_adj, f"p = {perms['IS']['p']:.3f}"),
        (f"Permutation p < {alpha_adj:.3f} (OOS, corrected for {N_TRIALS} trials)", perms["OOS"]["p"] < alpha_adj, f"p = {perms['OOS']['p']:.3f}"),
        ("Hard limit reachable with the minimum lot in the grid", cap_needed is not None, f"capital {cap_needed}"),
        (f"Capital {CAPITAL:,.0f} is enough for that", cap_needed is not None and CAPITAL >= cap_needed, f"needed {cap_needed}"),
        ("No full calendar year breaches the limit at that capital",
         not annual.loc[~annual["partial"], "breach"].any(), f"breaches: {annual.loc[annual['breach'], 'year'].tolist()}"),
    ]
    print("\nCHECKS")
    for name, ok, detail in checks:
        print(f"   [{'PASS' if bool(ok) else 'FAIL'}] {name}  ->  {detail}")
    n_fail = sum(not bool(ok) for _, ok, _ in checks)
    print(f"\n{len(checks) - n_fail} PASS / {n_fail} FAIL")
    print(f"NOTE: this variant was picked after seeing v1's full-sample results (trial {N_TRIALS} on this dataset), so its OOS "
          f"is not independent. Even with every check in PASS it stays a conditional candidate until it has forward data.")

    result = dict(variant=cfg["id"] + ".long_only", oos_start=str(oos_start.date()), n_trials=N_TRIALS,
                  table=tab.round(4).to_dict(orient="records"),
                  permutation={k: {a: float(b) for a, b in v.items()} for k, v in perms.items()},
                  capital_needed=cap_needed, checks=[dict(name=n, passed=bool(o), detail=d) for n, o, d in checks])
    if save and save_json is not None:
        save_json(cfg, "01b_long_only_check.json", result)
    return result


if __name__ == "__main__":
    def _find_upwards(name, start):
        for base in (start, *start.parents):
            if (base / name).is_dir():
                return base
        raise FileNotFoundError(f"Could not find '{name}' walking up from {start}")

    here = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd().resolve()
    edge = _find_upwards("variants", here)
    if str(edge) not in sys.path:
        sys.path.insert(0, str(edge))
    import variant_config
    from variant_config import load_variant, save_json

    variant_config.EDGE_DIR = edge
    args = [a for a in sys.argv[1:] if not a.startswith("-")]      # ignore kernel / flag arguments
    run(load_variant(args[0] if args else DEFAULT_VARIANT), save=True, save_json=save_json)
