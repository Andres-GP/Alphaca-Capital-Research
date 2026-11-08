"""
01b_v2_relative_equity_test.py  ·  02_strategy_development/Month_End_Fix/

ONE-SHOT test of the v2 rule (direction from GER40 - UK100 relative performance). Same gates and thresholds as
notebook 01; the only difference is that the permutation gate shuffles the SIGNS of the trades (does the signal
add anything?) instead of drawing random windows. Run it once: the rule is declared in the YAML (k = 18).

Run:   python 01b_v2_relative_equity_test.py          (or paste it in a notebook cell)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

EDGE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
if str(EDGE_DIR) not in sys.path:
    sys.path.insert(0, str(EDGE_DIR))
import month_end_fix_engine as eng
import variant_config
from variant_config import load_variant, save_json

variant_config.EDGE_DIR = EDGE_DIR
VARIANT, HARD_LIMIT, CAPITALS = "v2_eurgbp_relequity", 0.09, (1_000.0, 2_000.0)

# ---- Screen thresholds: identical to notebook 01, k = 18 now ----
T_MIN, T_OOS_MIN, PF_MIN, N_OOS_MIN = 2.0, 1.645, 1.3, 30
K_TESTS, ALPHA = 18, 0.05
T_CORR = float(stats.norm.ppf(1 - ALPHA / K_TESTS))
YEARS_POS_MIN, TRIM_SHARE, EDGE_SPREAD_MIN, DECAY_MAX, CASI_TOL = 0.75, 0.10, 3.0, 0.50, 0.10

cfg = load_variant(VARIANT)
eng.set_engine_defaults(**cfg.get("engine_defaults", {}))
P, SIG = cfg["params"], cfg["signal"]
ENTRY_H, EXIT_H, COST_BPS = P["entry_hour"], P["exit_hour"], P["cost_bps_per_side"]
SPREAD_BPS, OOS_START = 2 * COST_BPS, cfg["oos_start_ts"]
MIN_LOT = eng.ENGINE_DEFAULTS["min_lot"]

# ---- Data ----
df = eng.prepare(eng.load_data(cfg["instrument"]["ticker"], start=cfg["instrument"]["start"]),
                 entry_hour=ENTRY_H, exit_hour=EXIT_H)
idx_a, idx_b = eng.load_data(csv_path=SIG["index_a_csv"]), eng.load_data(csv_path=SIG["index_b_csv"])
print(f"GER40: {idx_a.index[0]:%Y-%m-%d} -> {idx_a.index[-1]:%Y-%m-%d} | UK100: {idx_b.index[0]:%Y-%m-%d} -> {idx_b.index[-1]:%Y-%m-%d}")

sig = eng.relative_equity_signal(df, idx_a, idx_b, entry_hour=ENTRY_H)
n_me, n_sig = len(sig), int(sig["side"].notna().sum())
print(f"Month-ends: {n_me} | with a signal: {n_sig} | skipped (no index data or R = 0): {n_me - n_sig}")
print(f"Signal: {int((sig['side'] == 'short').sum())} short / {int((sig['side'] == 'long').sum())} long")

RULES = dict(entry_hour=ENTRY_H, exit_hour=EXIT_H, cost_bps_per_side=COST_BPS, side_by_entry=sig["side"].dropna())
trades_all = eng.run_fix_backtest(df, **RULES)
et = pd.to_datetime(trades_all["entry_time"])
trades_is, trades_oos = trades_all[et < OOS_START], trades_all[et >= OOS_START]
net_all, net_is, net_oos = (t["net_bps"].to_numpy() for t in (trades_all, trades_is, trades_oos))

# ---- Statistics ----
t_all, t_oos = eng.tstat(net_all), eng.tstat(net_oos)
pf_all, pf_is, pf_oos = (eng.profit_factor(x) for x in (net_all, net_is, net_oos))
ypos, by_year = eng.years_positive(net_all, et)
trim_mean = eng.drop_best(net_all, TRIM_SHARE)
edge_x = float(trades_all["gross_bps"].mean() / SPREAD_BPS)
decay = float(1 - net_oos.mean() / net_is.mean()) if len(net_is) and net_is.mean() > 0 else np.inf

signs = trades_all["type"].map({"long": 1.0, "short": -1.0}).to_numpy()
long_bps = trades_all["gross_bps"].to_numpy() * signs                 # gross return as if every window were LONG
perm = eng.sign_permutation_test(long_bps, signs)

dd_worst = 0.0
for cap in CAPITALS:
    sizes = eng.cfd_trade_sizes(trades_all, cap, lots=MIN_LOT)
    dd_worst = min(dd_worst, eng.hard_limit_report_intrabar(df, trades_all, HARD_LIMIT, sizing=sizes["size_fraction"])["max_dd"])

# ---- Reference: v1 (always short) on the same month-ends ----
v1 = eng.run_fix_backtest(df, side="short", entry_hour=ENTRY_H, exit_hour=EXIT_H, cost_bps_per_side=COST_BPS)
v1 = v1[v1["entry_time"].isin(trades_all["entry_time"])]

gates = [
    eng.gate("t net (full period)", t_all, T_MIN, ">="),
    eng.gate(f"t net corrected (k = {K_TESTS})", t_all, T_CORR, ">="),
    eng.gate("Profit Factor", pf_all, PF_MIN, ">="),
    eng.gate("n OOS", len(net_oos), N_OOS_MIN, ">="),
    eng.gate("t OOS", t_oos, T_OOS_MIN, ">=", kill=True),
    eng.gate("Positive years", ypos, YEARS_POS_MIN, ">="),
    eng.gate("Sign permutation p (does the signal add value?)", perm["p"], ALPHA, "<", kill=True),
    eng.gate(f"Net mean without the best {TRIM_SHARE:.0%} (bps)", trim_mean, 0.0, ">"),
    eng.gate("Gross edge / spread", edge_x, EDGE_SPREAD_MIN, ">="),
    eng.gate("Intrabar DD, min lot (%)", dd_worst * 100, -HARD_LIMIT * 100, ">="),
    eng.gate("IS -> OOS decay", decay, DECAY_MAX, "<", kill=True),
    eng.gate("|Correlation| with Gotobi", None, 0.30, "<"),            # PENDING until the trades CSV exists
]
verdict = eng.screen_verdict(gates, t_oos=t_oos, t_oos_min=T_OOS_MIN, casi_tol=CASI_TOL, declared=True)

tbl = pd.DataFrame([{"Gate": g["name"], "Value": "n/a" if g["value"] is None else f"{g['value']:.3f}",
                     "Threshold": f"{g['op']} {g['threshold']:g}", "Status": g["status"],
                     "Immediate discard": "yes" if g["kill"] else ""} for g in gates]).set_index("Gate")
print("=" * 80)
print(f"v2 RELATIVE EQUITY: VERDICT {verdict}")
print("=" * 80)
print(tbl.to_string())
print(f"\n{len(trades_all)} trades ({len(trades_oos)} OOS): net {net_all.mean():+.2f} bps (IS {net_is.mean():+.2f} / OOS {net_oos.mean():+.2f}), "
      f"PF {pf_all:.3f}, t {t_all:.2f} (corrected threshold {T_CORR:.2f}), t OOS {t_oos:.2f}")
print(f"Sign permutation: observed {perm['obs']:+.2f} bps vs shuffled signs {perm['ctrl_mean']:+.2f} (z {perm['z']:.2f}, p {perm['p']:.4f})")
print(f"Same month-ends, v1 always short: net {v1['net_bps'].mean():+.2f} bps, t {eng.tstat(v1['net_bps']):.2f}")
print("Years: " + ", ".join(f"{y}: {v:+.1f}" for y, v in by_year.items()))
print("\nDecision rule (declared in the YAML): any failed kill gate -> status: rejected, archive v1 and v2, close the edge.")

save_json(cfg, "01b_v2_test.json", {
    "variant": cfg["id"], "k_tests": K_TESTS, "verdict": verdict, "signal_counts": {"month_ends": n_me, "with_signal": n_sig},
    "all": {"n": int(len(trades_all)), "net_bps": float(net_all.mean()), "pf": float(pf_all), "t_stat": float(t_all)},
    "is": {"n": int(len(trades_is)), "net_bps": float(net_is.mean())},
    "oos": {"n": int(len(trades_oos)), "net_bps": float(net_oos.mean()), "t_stat": float(t_oos)},
    "sign_permutation": {"p": float(perm["p"]), "obs": float(perm["obs"]), "ctrl": float(perm["ctrl_mean"])},
    "v1_same_days": {"n": int(len(v1)), "net_bps": float(v1["net_bps"].mean())},
    "gates": gates})
