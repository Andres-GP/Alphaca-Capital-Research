# 2. ROUGHNECK CRUDE OIL - IN-SAMPLE PARAMETER STABILITY & PLATEAU CHECK
This notebook checks, **on in-sample data only**, that the configured rules sit on a broad, stable plateau of the parameter space and not on a lucky isolated peak. The out-of-sample block is never touched here.

### STRICT METHODOLOGICAL CONSTRAINT
Nothing is tuned to the data. The configured point comes from the published rules (LeBeau / Elden); the grid only asks *how fragile it is*. If the plateau gate fails, we document it and carry it to notebook 03 with the frozen parameters: we do not re-tune on this result.

### OBJECTIVES
1. 2D grid on the two parameters that define the long trigger: `long_atr_mult` x `atr_len`.
2. The same grid with costs x2 and x3 (the broker's spread and swap decide whether this edge exists).
3. Plateau + anti-cliff gate (`validation_gate.plateau_check`).
4. One-at-a-time sensitivity of the other rules (short trigger, stop, trend slope, entry window).
5. Dose-response of the trigger multiple and ATR method (simple vs Wilder).
6. Ablation by regime: trend filter, each exit component and sides.

### EDGE-SPECIFIC CHECKS (they matter more than the generic ones)
- The $1 stop and the 0.25 trend slope are in **price units**: they scale with the oil price level, so a plateau in the stop is as important as a plateau in the ATR multiple.
- Few trades per year (about 6-10): a single trade moves a cell's PF, so the sample-size gate is scaled to the in-sample length.

### STRATEGY PARAMETERS


```
VARIANT = "v1_axi_usoil"  # only base variants here; see variants/*.yaml
SCALE_SAMPLE_GATES = True   # short history: scale validation_gate plateau_n_min to the in-sample length (printed in section 2)
```

## 1. IMPORTS AND CONFIG


```
import os
import sys
import json
import importlib
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

# ---- Paths ----
def find_upwards(name, start=None, must_be_dir=True):
    """Walk up from start (cwd by default) and return the first folder that contains `name`."""
    here = (start or Path.cwd()).resolve()
    for base in (here, *here.parents):
        target = base / name
        if target.is_dir() if must_be_dir else target.exists():
            return base
    raise FileNotFoundError(f"Could not find '{name}' walking up from {here}")

EDGE_DIR   = find_upwards('variants')                  # edge folder (notebooks, engine and variants/ live together)
utils_path = str(find_upwards('utils') / 'utils')      # research_development/utils
for p in (utils_path, str(EDGE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils import compute_metrics
from metrics import sharpe_ratio, max_drawdown
from robustness import monte_carlo_block, monkey_test, grid_search, plateau_check, plot_grid, plot_monkey, profit_factor
from edge_decay import rolling_pf, plot_rolling_pf, pf_by_year, edge_decay_summary
from validation_gate import run_validation, DEFAULTS as GATE
import roughneck_engine as eng
import variant_config
from variant_config import load_variant, save_json

importlib.reload(eng)   # resets ENGINE_DEFAULTS: nothing leaks between variants

variant_config.EDGE_DIR = EDGE_DIR
assert (variant_config.EDGE_DIR / "variants").is_dir(), f"Doesn't exist {variant_config.EDGE_DIR / 'variants'}"

# ---- Variant config: single source of truth ----
cfg        = load_variant(VARIANT)
eng.set_engine_defaults(**cfg.get("engine_defaults", {}))
RUN_DIR    = cfg["run_dir"]
TICKER     = cfg["instrument"]["ticker"]
DATA_START = cfg["instrument"]["start"]
OOS_START  = cfg["oos_start_ts"]
P          = cfg["params"]
COST_BPS   = P["cost_bps_per_side"]
SIZE_FRAC  = eng.ENGINE_DEFAULTS["size_fraction"]
CONTRACT_SIZE, MIN_LOT, LOT_STEP = (eng.ENGINE_DEFAULTS[k] for k in ("contract_size", "min_lot", "lot_step"))
PPY        = 252    # daily bars, futures-like calendar: annualisation for Sharpe
MULTS      = [float(x) for x in cfg["grid"]["long_atr_mult_values"]]
ATR_LENS   = [int(x) for x in cfg["grid"]["atr_len_values"]]
CHOSEN     = (float(P["long_atr_mult"]), int(P["atr_len"]))

# Frozen rules, passed as-is to every backtest call. Indicator rules go to prepare(), the rest to the backtest.
RULES = dict(P)
IND   = {k: RULES[k] for k in eng.IND_KEYS}
def prep(df_raw, **over):
    """prepare() with the frozen indicator rules, optionally overriding some (e.g. atr_len, trend_mode)."""
    return eng.prepare(df_raw, **{**IND, **over})

# Rules that never change in this notebook (long_atr_mult / atr_len are swept)
RULES_KW = {k: v for k, v in RULES.items() if k not in ("long_atr_mult", "atr_len")}

# ---- Style and helpers ----
BG, PANEL, GRIDC, TXT, SUB, GREEN, RED, ORANGE = "#15171c", "#1b1e26", "#2a2d37", "#e8e9ec", "#9aa0ab", "#34d399", "#f0555a", "#f5a524"
def dark_ax(ax):
    ax.set_facecolor(PANEL)
    ax.grid(color=GRIDC, alpha=0.8)
    ax.tick_params(colors=SUB)
    for s in ax.spines.values():
        s.set_visible(False)

# Oil regimes (an edge that only lives in one regime is a different edge): only the ones present in the data are used
ERAS_ALL = {"Pre-COVID (<=2019)": (1990, 2019), "COVID (2020)": (2020, 2020), "Post-COVID (2021+)": (2021, 2100)}
def era_of(y):
    return next(k for k, (a, b) in ERAS_ALL.items() if a <= y <= b)

def tstat(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan

def summarize(t):
    """PF / mean net % / t-stat / win rate of a trades frame (100% capital, net of costs)."""
    if len(t) == 0:
        return dict(n=0, pf=np.nan, mean=np.nan, t=np.nan, win=np.nan)
    return dict(n=len(t), pf=profit_factor(t["pnl"]), mean=float(t["pnl"].mean()), t=tstat(t["pnl"]), win=float((t["pnl"] > 0).mean() * 100))

print("Imports complete.")
print(f"Loaded roughneck_engine from: {eng.__file__}")
print(f"Edge dir: {EDGE_DIR}")
print(f"Variant: {cfg['id']} | {TICKER} | long: trend + close > LL({P['long_low_n']}) + {P['long_atr_mult']:g} ATR({P['atr_len']}) | "
      f"short: close < HH({P['short_high_n']}) - {P['short_atr_mult']:g} ATR | stop ${P['stop_dollar']:g} | {COST_BPS:g} bps/side | size {SIZE_FRAC:.0%}")
print(f"Data source: {eng.ENGINE_DEFAULTS['data_source']} | swap: {eng.ENGINE_DEFAULTS['financing_bps_per_night']:g} bps/night | ATR method: {P['atr_method']}")
print(f"Run folder: {RUN_DIR}")
print(f"Grid: {len(MULTS)} long_atr_mult x {len(ATR_LENS)} ATR lengths = {len(MULTS) * len(ATR_LENS)} cells | candidate {CHOSEN}")
print(f"Gate criteria (validation_gate.DEFAULTS): PF >= {GATE['plateau_pf_min']}, N >= {GATE['plateau_n_min']}, max drop {GATE['plateau_max_drop']}%")
```

## 2. IN-SAMPLE DATA SETUP


```
df_raw = eng.load_data(TICKER, start=DATA_START)
_first_ok = lambda d: d.index[d["warm"].to_numpy().argmax()]
common_start = max(_first_ok(prep(df_raw, atr_len=L)) for L in ATR_LENS)

_cache = {}
def is_df(m, L):
    """In-sample slice of the indicators for (long_atr_mult=m, atr_len=L). Indicators use the full history (warm-up kept)."""
    if (m, L) not in _cache:
        d = prep(df_raw, atr_len=L, long_atr_mult=m)
        _cache[(m, L)] = d[(d.index >= common_start) & (d.index < OOS_START)]
    return _cache[(m, L)]

d0 = is_df(*CHOSEN)
assert len(d0) > 0, "Check oos_start_ts against the history."

GATE_ORIG = dict(GATE)
_is_years = (d0.index[-1] - d0.index[0]).days / 365.25
BASE_IS_YEARS = 6.5   # years of in-sample behind validation_gate.DEFAULTS
if SCALE_SAMPLE_GATES and _is_years < BASE_IS_YEARS:
    GATE['plateau_n_min'] = max(5, int(round(GATE_ORIG['plateau_n_min'] * _is_years / BASE_IS_YEARS)))
print(f"In-sample with warm-up done: {_is_years:.1f} years | plateau_n_min: {GATE_ORIG['plateau_n_min']} -> {GATE['plateau_n_min']}")
print('validation_gate.DEFAULTS in use:', GATE)
print("=" * 70)
print("IN-SAMPLE WINDOW (ONE WINDOW FOR EVERY GRID CELL)")
print("=" * 70)
print(f"Strict In-Sample Range: {d0.index.min():%Y-%m-%d} to {d0.index.max():%Y-%m-%d}")
print(f"Total In-Sample Bars: {len(d0):,}")
print(f"OOS block (not used here) starts: {pd.Timestamp(OOS_START):%Y-%m-%d}")
```

## 3. 2D PARAMETER GRID (LONG TRIGGER MULTIPLE x ATR LENGTH)


```
TR = {}   # (mult, atr_len) -> in-sample trades, reused by every later cell

def run_cell(m, L, **kw):
    return eng.run_roughneck_backtest(is_df(m, L), **{**RULES_KW, "long_atr_mult": m, "atr_len": L, **kw})

def evaluate(m, L):
    t = run_cell(m, L)
    TR[(m, L)] = t
    return (profit_factor(t["pnl"]) if len(t) else 0.0, len(t))

pf_grid, n_grid = grid_search(evaluate, MULTS, ATR_LENS)
mean_grid = pd.DataFrame({L: {m: summarize(TR[(m, L)])["mean"] for m in MULTS} for L in ATR_LENS})
t_grid    = pd.DataFrame({L: {m: summarize(TR[(m, L)])["t"] for m in MULTS} for L in ATR_LENS})

print("=" * 70)
print("IN-SAMPLE PROFIT FACTOR GRID (rows = long_atr_mult, columns = ATR length)")
print("=" * 70)
display(pf_grid.round(3))
print("\n" + "=" * 70 + "\nIN-SAMPLE TRADE COUNT GRID (N)\n" + "=" * 70)
display(n_grid.astype(int))
print("\n" + "=" * 70 + "\nMEAN NET RETURN PER TRADE, % (100% capital)\n" + "=" * 70)
display(mean_grid.round(3))
print("\n" + "=" * 70 + "\nt-STAT OF THE MEAN\n" + "=" * 70)
display(t_grid.round(2))
plot_grid(pf_grid, n_grid, CHOSEN, title="Roughneck · Profit Factor (in-sample) · orange = configured")
```

## 3.5 COST-STRESSED GRIDS (x2 AND x3 COSTS)
The same grid with doubled and tripled spread. If the plateau disappears at x2, the edge depends on a tight broker.


```
stress = {}
for label, mult in (("Costs x2", 2.0), ("Costs x3", 3.0)):
    def ev(m, L, _mult=mult):
        t = run_cell(m, L, cost_bps_per_side=COST_BPS * _mult)
        return (profit_factor(t["pnl"]) if len(t) else 0.0, len(t))
    stress[label] = grid_search(ev, MULTS, ATR_LENS)
    print(f"\n{label}: PF grid")
    display(stress[label][0].round(3))
    plst = plateau_check(stress[label][0], stress[label][1], CHOSEN, pf_min=GATE["plateau_pf_min"], n_min=GATE["plateau_n_min"], max_drop_pct=GATE["plateau_max_drop"])
    print(f"{label}: center PF {plst['center_pf']:.3f} | plateau {'YES' if plst['plateau'] else 'NO'} | gate {'PASS' if plst['passed'] else 'FAIL'} | "
          f"cells with PF >= {GATE['plateau_pf_min']}: {plst['pct_cells_pf_ok'] * 100:.0f}%")
```

## 4. PLATEAU & ANTI-CLIFF CHECK


```
pl = plateau_check(pf_grid, n_grid, CHOSEN, pf_min=GATE["plateau_pf_min"], n_min=GATE["plateau_n_min"], max_drop_pct=GATE["plateau_max_drop"])
ia, ib = pf_grid.index.get_loc(CHOSEN[0]), pf_grid.columns.get_loc(CHOSEN[1])
sl = (slice(max(ia - 1, 0), ia + 2), slice(max(ib - 1, 0), ib + 2))
cells = pf_grid.stack()
rank = int((cells > pf_grid.loc[CHOSEN[0], CHOSEN[1]]).sum()) + 1

print("=" * 70)
print(f"3x3 NEIGHBORHOOD OF THE CONFIGURED POINT long_atr_mult={CHOSEN[0]:g}, ATR({CHOSEN[1]})")
print("=" * 70)
print("Profit Factor:"); display(pf_grid.iloc[sl].round(3))
print("N trades:");      display(n_grid.iloc[sl].astype(int))
print(f"Center PF: {pl['center_pf']:.3f} | worst neighbor drop: {pl['worst_neighbor_drop_pct']:.1f}% (max {GATE['plateau_max_drop']}%)")
print(f"Plateau (all 9 cells PF >= {GATE['plateau_pf_min']} and N >= {GATE['plateau_n_min']}): {'YES' if pl['plateau'] else 'NO'}")
print(f"Anti-cliff: {'PASS' if pl['anticliff'] else 'FAIL'} | Gate (plateau AND anti-cliff): {'PASS' if pl['passed'] else 'FAIL'}")
print(f"Cells with PF >= {GATE['plateau_pf_min']}: {pl['pct_cells_pf_ok'] * 100:.0f}% of {len(cells)} | cells with mean net > 0: {int((mean_grid.stack() > 0).sum())} of {len(cells)}")
print(f"Configured point ranks #{rank} of {len(cells)} by PF | best cell: {pl['best_cell']} (PF {pl['best_pf']:.3f}) | configured on grid edge: {pl['edge_of_grid']}")

# ---- Secondary diagnostic (NOT the gate): same check on the shorts-excluded (long-only) book ----
def grid_for(**kw):
    def ev(m, L):
        t = run_cell(m, L, **kw)
        return (profit_factor(t["pnl"]) if len(t) else 0.0, len(t))
    return grid_search(ev, MULTS, ATR_LENS)
pf_l, n_l = grid_for(side="long")
pl_l = plateau_check(pf_l, n_l, CHOSEN, pf_min=GATE["plateau_pf_min"], n_min=max(3, GATE["plateau_n_min"] // 2), max_drop_pct=GATE["plateau_max_drop"])
print("\n" + "-" * 70)
print(f"DIAGNOSTIC · long side only: center PF {pl_l['center_pf']:.3f} | plateau {'YES' if pl_l['plateau'] else 'NO'} | worst drop {pl_l['worst_neighbor_drop_pct']:.1f}% | gate {'PASS' if pl_l['passed'] else 'FAIL'}")
display(pf_l.round(3))
```

## 4.1 ONE-AT-A-TIME SENSITIVITY OF THE OTHER RULES
The grid above only moves the long trigger. Here each remaining rule is moved alone, around its configured value, with everything else frozen.


```
IND_SWEEP = set(eng.IND_KEYS)
SWEEPS = {"short_atr_mult": [1.5, 1.75, 2.0, 2.25, 2.5], "stop_dollar": [0.5, 0.75, 1.0, 1.25, 1.5], "trend_min": [0.0, 0.1, 0.25, 0.4, 0.6],
          "long_entry_n": [2, 3, 4, 5, 6], "long_low_n": [5, 6, 8, 10, 12], "lock_level": [0.0, 0.2, 0.4, 0.6, 0.8]}
sweep_rows = []
for k, vals in SWEEPS.items():
    for v in vals:
        if k in IND_SWEEP:
            d = prep(df_raw, **{k: v}); d = d[(d.index >= common_start) & (d.index < OOS_START)]
            t = eng.run_roughneck_backtest(d, **{**RULES, k: v})
        else:
            t = eng.run_roughneck_backtest(d0, **{**RULES, k: v})
        s = summarize(t)
        sweep_rows.append({"rule": k, "value": v, "configured": v == RULES[k], "N": s["n"], "PF": s["pf"], "mean net %": s["mean"], "t": s["t"]})
sweep = pd.DataFrame(sweep_rows)
display(sweep.pivot_table(index="value", columns="rule", values="PF").round(2) if False else sweep.round(3).set_index(["rule", "value"]))
ok_share = sweep.groupby("rule").apply(lambda g: float((g["PF"] >= GATE["plateau_pf_min"]).mean()))
print("Share of tested values per rule with PF >= plateau_pf_min:"); print(ok_share.round(2).to_dict())
fragile = [r for r, s in ok_share.items() if s < 0.6]
print("Fragile rules (< 60% of tested values pass):", fragile if fragile else "none")
```

## 5. DOSE-RESPONSE: DOES A STRONGER TRIGGER MEAN MORE EDGE?


```
dose = pd.DataFrame({m: summarize(TR[(m, CHOSEN[1])]) for m in MULTS}).T
dose.index.name = "long_atr_mult"
rho_d, p_d = stats.spearmanr(dose.index.to_numpy(float), dose["mean"].to_numpy(float))
print("=" * 70)
print(f"DOSE-RESPONSE AT ATR({CHOSEN[1]}) · in-sample · 100% capital, net of {COST_BPS:g} bps/side")
print("=" * 70)
display(dose.rename(columns={"n": "Trades", "pf": "PF", "mean": "Mean net %", "t": "t-stat", "win": "Win %"}).round(3))
print(f"Spearman (multiple vs mean net return): rho = {rho_d:+.2f} (p = {p_d:.3f}, only {len(dose)} points: descriptive)")
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.2), facecolor=BG)
dark_ax(ax1); dark_ax(ax2)
x = np.arange(len(dose))
ax1.bar(x, dose["mean"], color=[GREEN if v > 0 else RED for v in dose["mean"]], width=0.6); ax1.axhline(0, color=SUB, lw=0.6)
ax1.set_xticks(x); ax1.set_xticklabels([f"{m:g}" for m in dose.index], color=SUB)
ax1.set_title("Mean net return per trade (%)", color=TXT, fontweight="bold", loc="left")
ax2.plot(x, dose["pf"].clip(upper=8), color=GREEN, lw=1.8, marker="o")
ax2.axhline(1.0, color=RED, lw=1.0); ax2.axhline(GATE["plateau_pf_min"], color=ORANGE, ls="--", lw=1.0)
ax2.set_xticks(x); ax2.set_xticklabels([f"{m:g}" for m in dose.index], color=SUB)
ax2.set_title("Profit Factor", color=TXT, fontweight="bold", loc="left")
for i, n in enumerate(dose["n"]):
    ax2.text(i, ax2.get_ylim()[0], f"N={int(n)}", color=SUB, fontsize=8, ha="center", va="bottom")
plt.tight_layout(); plt.show()
```

## 6. ATR METHOD: SIMPLE AVERAGE VS WILDER (THE NEWSLETTER'S OPEN QUESTION)
The original system probably used Wilder's ATR (TradeStation `AvgTrueRange` is a simple average, `Average True Range` in some platforms is Wilder). Both are tested at the configured length and across the ATR-length grid.


```
rows = []
for method in ("sma", "wilder"):
    for L in ATR_LENS:
        d = prep(df_raw, atr_len=L, atr_method=method); d = d[(d.index >= common_start) & (d.index < OOS_START)]
        s = summarize(eng.run_roughneck_backtest(d, **{**RULES, "atr_len": L, "atr_method": method}))
        rows.append({"ATR method": method, "ATR length": L, "Trades": s["n"], "PF": s["pf"], "Mean net %": s["mean"], "t": s["t"]})
atr_tbl = pd.DataFrame(rows)
display(atr_tbl.pivot_table(index="ATR length", columns="ATR method", values="PF").round(3))
pf_by_method = atr_tbl.groupby("ATR method")["PF"].median()
print("Median PF across ATR lengths:", pf_by_method.round(3).to_dict())
```

## 7. ABLATION BY REGIME (IN-SAMPLE)


```
combos = {"No trend filter (naked trigger)": dict(trend_mode="off"),
          "No early exit": dict(use_early=False),
          "No ATR tiers": dict(use_tiers=False),
          "No lock at +$1": dict(use_lock=False),
          "Long only": dict(side="long"),
          "Short only": dict(side="short"),
          "All (configured)": dict()}
_is_year_set = set(d0.index.year)
IS_ERAS = [e for e, (a_, b_) in ERAS_ALL.items() if any(a_ <= y <= b_ for y in _is_year_set)]
abl, rows = {}, []
for name, kw in combos.items():
    ind_kw = {k: v for k, v in kw.items() if k in IND_SWEEP}
    d = prep(df_raw, **ind_kw); d = d[(d.index >= common_start) & (d.index < OOS_START)]
    t = eng.run_roughneck_backtest(d, **{**RULES, **kw})
    abl[name] = t
    yr = pd.to_datetime(t["entry_time"]).dt.year
    row = {"Variant": name}
    for e in IS_ERAS:
        a_, b_ = ERAS_ALL[e]
        s = summarize(t[(yr >= a_) & (yr <= b_)])
        row[e] = f"{s['pf']:.2f} | {s['mean']:+.3f}% | {s['n']}" if s["n"] else "n/a"
    s_all = summarize(t)
    row["All in-sample"] = f"{s_all['pf']:.2f} | {s_all['mean']:+.3f}% | {s_all['n']}"
    rows.append(row)
print("=" * 70)
print(f"ABLATION · in-sample · net of {COST_BPS:g} bps/side · PF | mean net % | N")
print("=" * 70)
display(pd.DataFrame(rows).set_index("Variant"))
tc = abl["All (configured)"]
by_year = tc.assign(year=pd.to_datetime(tc["entry_time"]).dt.year).groupby("year")["pnl"].agg(n="size", pf=profit_factor, mean="mean")
print("\nConfigured rules by entry year (in-sample):")
display(by_year.round(3))
```

## 8. VERDICT & NEXT STEPS


```
mean_all, mean_naked = summarize(abl["All (configured)"])["mean"], summarize(abl["No trend filter (naked trigger)"])["mean"]
ready = bool(pl["passed"])
print("=" * 80)
print("8. SUMMARY OF IN-SAMPLE PARAMETER STABILITY")
print("=" * 80)
print(f"""
Key Findings:

1. Plateau gate (full in-sample, official): {'PASS' if pl['passed'] else 'FAIL'} - center PF {pl['center_pf']:.3f}, worst neighbor drop {pl['worst_neighbor_drop_pct']:.1f}%,
   plateau {'yes' if pl['plateau'] else 'no'}; {pl['pct_cells_pf_ok'] * 100:.0f}% of {len(cells)} cells have PF >= {GATE['plateau_pf_min']}; configured point ranks #{rank} by PF.
   Diagnostic, long side only: {'PASS' if pl_l['passed'] else 'FAIL'} (center PF {pl_l['center_pf']:.3f}).

2. Cost stress: center PF at x2 costs {stress['Costs x2'][0].loc[CHOSEN[0], CHOSEN[1]]:.3f} | at x3 {stress['Costs x3'][0].loc[CHOSEN[0], CHOSEN[1]]:.3f}.

3. Other rules (one at a time): fragile rules = {fragile if fragile else 'none'}.

4. Dose-response: Spearman rho {rho_d:+.2f} between the trigger multiple and mean net return at ATR({CHOSEN[1]}); ATR median PF sma {pf_by_method.get('sma', float('nan')):.2f} vs Wilder {pf_by_method.get('wilder', float('nan')):.2f}.

5. Ablation: configured mean net {mean_all:+.3f}% per trade vs {mean_naked:+.3f}% for the naked trigger without the trend filter (in-sample).

6. Next Step: {'proceed to 03_Roughneck_Robustness_Testing.ipynb with the frozen parameters.' if ready else 'the official gate failed in-sample. Do NOT re-tune the parameters on this result: document it, and carry it to notebook 03 as a documented exception only if the other evidence holds.'}
""")
```

## 9. SAVE THE RESULTS OF THIS NOTEBOOK FOR THE VARIANT


```
save_json(cfg, "02_optimization.json", {
    "variant": cfg["id"], "ticker": TICKER, "chosen": {"long_atr_mult": CHOSEN[0], "atr_len": CHOSEN[1]},
    "is_window": [str(d0.index.min().date()), str(d0.index.max().date())],
    "plateau": {k: (bool(v) if isinstance(v, (bool, np.bool_)) else (float(v) if isinstance(v, (int, float, np.floating)) else str(v))) for k, v in pl.items()},
    "plateau_n_min_used": int(GATE["plateau_n_min"]),
    "pf_grid": pf_grid.round(4).reset_index().to_dict(orient="records"), "n_grid": n_grid.astype(int).reset_index().to_dict(orient="records"),
    "cost_stress_center_pf": {k: float(v[0].loc[CHOSEN[0], CHOSEN[1]]) for k, v in stress.items()},
    "fragile_rules": fragile, "dose_spearman": {"rho": float(rho_d), "p": float(p_d)},
    "atr_median_pf": {k: float(v) for k, v in pf_by_method.items()},
    "ready_for_03": ready,
})
```
