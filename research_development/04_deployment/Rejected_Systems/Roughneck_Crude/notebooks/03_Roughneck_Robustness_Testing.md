# 3. ROUGHNECK CRUDE OIL - ROBUSTNESS BATTERY & VALIDATION GATE
This notebook runs the multi-phase robustness battery and the validation gate for **Roughneck Crude Oil** on daily bars of an oil CFD, following the structure of notebook 03 of the Monday Effect. The rules are the ones frozen in notebooks 01 and 02: nothing is re-tuned here.

### ROBUSTNESS BATTERY SCOPE
1. **Phase 1 · Out-Of-Sample**: untouched data since `oos_start_ts`.
2. **Phase 2 · Walk-Forward (fixed rules, 3y IS / 1y OOS)**.
3. **Phase 3 · Block Monte Carlo**: 10,000 circular block resamplings (block = 5), at the robot's sizing and at 1.5x.
4. **Phase 4 · Monkey Test**: (A) random entries on any day, same direction and holding time as each real trade; (B) random choice among all naked-trigger days (does the trend filter beat picking trigger days at random?).
5. **Phase 5 · Stress**: cost sweep and break-even (what matters for Darwinex / Axi), best-years removal, worst-trade (gap) dependence, regimes, concentration of profit and of losses by year.
6. **Phase 6 · Edge Decay**: rolling PF, PF by year and the z wear-and-tear protocol (last 20 trades vs reference).
7. **Phase 7 · Full Validation Gate** via `validation_gate.run_validation`.

### STRATEGY PARAMETERS


```
VARIANT = "v1_axi_usoil"  # only base variants here; see variants/*.yaml
SCALE_SAMPLE_GATES = True   # short history: scale validation_gate plateau_n_min to the in-sample length (printed in section 8)
HARD_LIMIT = 0.09
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

from roughneck_utils import monkey_test_sided   # Roughneck-only: keeps trade direction and variable holding time
SIZES      = {f"{SIZE_FRAC:.0%} (robot)": SIZE_FRAC, f"{1.5 * SIZE_FRAC:.0%}": 1.5 * SIZE_FRAC}   # first = official run
OFFICIAL   = next(iter(SIZES))

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

ERAS = ERAS_ALL
def scaled(t, frac):
    """Trades with pnl rescaled to a fraction of capital (pnl in % of equity)."""
    return t.assign(pnl=t["pnl"] * frac, win=t["pnl"] * frac > 0)

print("Imports complete.")
print(f"Loaded roughneck_engine from: {eng.__file__}")
print(f"Edge dir: {EDGE_DIR}")
print(f"Variant: {cfg['id']} | {TICKER} | long: trend + close > LL({P['long_low_n']}) + {P['long_atr_mult']:g} ATR({P['atr_len']}) | "
      f"short: close < HH({P['short_high_n']}) - {P['short_atr_mult']:g} ATR | stop ${P['stop_dollar']:g} | {COST_BPS:g} bps/side | size {SIZE_FRAC:.0%}")
print(f"Data source: {eng.ENGINE_DEFAULTS['data_source']} | swap: {eng.ENGINE_DEFAULTS['financing_bps_per_night']:g} bps/night | ATR method: {P['atr_method']}")
print(f"Run folder: {RUN_DIR}")
print(f"Sizes {list(SIZES)} | hard limit -{HARD_LIMIT:.0%} | frozen rules: {json.dumps({k: RULES[k] for k in ('long_atr_mult','short_atr_mult','atr_len','atr_method','stop_dollar','side')})}")
```

## 2. OUT-OF-SAMPLE (OOS) PERFORMANCE & COMPARISON
Indicators are computed once on the full history so the OOS slice keeps the warm-up (same as notebook 01).


```
df_raw = eng.load_data(TICKER, start=DATA_START)
preps = {L: prep(df_raw, atr_len=L) for L in ATR_LENS}   # one prepare per ATR length (also used by the gate grid)
df = preps[RULES["atr_len"]]

n_is = int((df.index < OOS_START).sum())
df_is, df_oos = df.iloc[:n_is].copy(), df.iloc[n_is:].copy()
oos_start = df_oos.index[0]

trades_all = eng.run_roughneck_backtest(df,     **RULES)
trades_is  = eng.run_roughneck_backtest(df_is,  **RULES)
trades_oos = eng.run_roughneck_backtest(df_oos, **RULES)

def sized(t, sizing):
    return t if sizing == "capital" else t.assign(pnl=t["pnl_frac"], win=t["pnl_frac"] > 0)

def perf_row(t, price_df, period, sizing):
    m = compute_metrics(sized(t, sizing), contract_multiplier=1.0, cost_per_trade=0.0)
    ret = eng.daily_returns(price_df, t, sizing=sizing)
    eq = (1.0 + ret).cumprod()
    yrs = (price_df.index[-1] - price_df.index[0]).days / 365.25
    return {"Period": period, "Sizing": "100% Capital" if sizing == "capital" else f"{SIZE_FRAC:.0%} Capital (robot)",
            "Trades": m["num_trades"], "Win Rate": f"{m['win_rate']:.1f}%", "Profit Factor": f"{m['profit_factor']:.3f}",
            "Expectancy": f"{m['expectancy']:.3f}%", "Total Return": f"{(eq.iloc[-1] - 1) * 100:.1f}%",
            "CAGR": f"{((eq.iloc[-1] ** (1 / yrs)) - 1) * 100:.1f}%" if yrs > 0 else "n/a",
            "Sharpe": f"{sharpe_ratio(ret, periods_per_year=PPY):.2f}", "Max Drawdown": f"{max_drawdown(eq) * 100:.2f}%"}

periods = [(f"In-Sample ({df_is.index[0].year}-{df_is.index[-1].year})", trades_is, df_is),
           (f"Out-of-Sample ({df_oos.index[0].year}-{df_oos.index[-1].year})", trades_oos, df_oos),
           (f"Full Period ({df.index[0].year}-{df.index[-1].year})", trades_all, df)]
perf_table = pd.DataFrame([perf_row(t, d, name, s) for name, t, d in periods for s in ("capital", "fraction")])
print("=" * 80)
print(f"OOS PERFORMANCE & COMPARISON (NET OF {COST_BPS:g} BPS PER SIDE + SWAP)")
print("=" * 80)
display(perf_table)

m_is, m_oos = compute_metrics(trades_is, 1.0, 0.0), compute_metrics(trades_oos, 1.0, 0.0)
pnl_oos = trades_oos["pnl"].to_numpy(float)
pf_oos_nb = profit_factor(np.delete(pnl_oos, pnl_oos.argmax())) if len(pnl_oos) > 1 else np.nan
print(f"PF IS {m_is['profit_factor']:.3f} -> OOS {m_oos['profit_factor']:.3f} | OOS without best trade {pf_oos_nb:.3f} | OOS t-stat of the mean {tstat(pnl_oos):.2f} | OOS trades {len(trades_oos)}")

ret_fr = eng.daily_returns(df, trades_all, sizing="fraction")
fig, ax = plt.subplots(figsize=(14, 5), facecolor=BG)
dark_ax(ax)
ax.plot(ret_fr.index, (1 + ret_fr).cumprod(), color="#5468ff", lw=1.6, label=f"{SIZE_FRAC:.0%} Capital (robot)")
ax.axvline(oos_start, color=ORANGE, ls="--", lw=1.2, label=f"OOS start ({oos_start:%Y-%m-%d})")
ax.set_title("Equity curve, in-sample vs out-of-sample", color=TXT, fontweight="bold", loc="left")
ax.legend(frameon=False, labelcolor=SUB, fontsize=9, loc="upper left")
plt.tight_layout(); plt.show()
```

## 3. WALK-FORWARD ANALYSIS (FIXED RULES: 3Y IS / 1Y OOS)
Rules are not re-fitted: each calendar year is compared with the annualised return of the full years before it. The first year of data is partial and never counts as IS; the IS window is shortened automatically (3 -> 2 -> 1 years) until there are at least two folds. Gate thresholds as in the Monday Effect (efficiency >= 0.5, positive years >= 60 %, worst-year drawdown > -20 %). Oil trades only ~6-10 times a year, so a single year can hold 3 trades: read it as descriptive when the folds are few.


```
WF_IS_YEARS = 3
for _y in (3, 2, 1):
    wf_df = eng.walk_forward_fixed(df, rules=RULES, is_years=_y, sizing="fraction")
    WF_IS_YEARS = _y
    if len(wf_df) >= 2:
        break
assert len(wf_df) > 0, "No walk-forward windows: need at least one full year before the first tested year."
print(f"Walk-forward IS window: {WF_IS_YEARS} year(s)" + ("" if WF_IS_YEARS == 3 else "  (shortened from 3: not enough full years in the data)"))

mean_is, mean_oos = wf_df["ret_is_anual"].mean(), wf_df["ret_oos"].mean()
efficiency = mean_oos / mean_is if mean_is > 0 else np.nan
pct_positive_years = float((wf_df["ret_oos"] > 0).mean())
worst_oos_mdd = float(wf_df["mdd_oos"].min())
wf_pass = bool(np.isfinite(efficiency) and efficiency >= 0.5 and pct_positive_years >= 0.60 and worst_oos_mdd > -0.20)
print("=" * 70)
print(f"WALK-FORWARD SUMMARY ({len(wf_df)} ROLLING WINDOWS, {SIZE_FRAC:.0%} sizing)")
print("=" * 70)
print(f"Walk-Forward Efficiency (OOS mean / IS annual mean): {efficiency:.3f} (>= 0.50)")
print(f"Positive OOS years ratio: {pct_positive_years * 100:.1f}% ({int((wf_df['ret_oos'] > 0).sum())}/{len(wf_df)}) (>= 60%)")
print(f"Worst single-year OOS drawdown: {worst_oos_mdd * 100:.2f}% (> -20%)")
print(f"Walk-Forward Gate Verdict: {'PASSED' if wf_pass else 'FAILED'}")
display(wf_df.round(4))

fig, ax = plt.subplots(figsize=(14, 5), facecolor=BG)
dark_ax(ax)
x, w = np.arange(len(wf_df)), 0.35
ax.bar(x - w / 2, wf_df["ret_is_anual"] * 100, w, label="IS annualised return (%)", color="#5468ff", alpha=0.8)
ax.bar(x + w / 2, wf_df["ret_oos"] * 100, w, label="OOS return (%)", color=[GREEN if r > 0 else RED for r in wf_df["ret_oos"]], alpha=0.85)
ax.axhline(0, color=SUB, lw=0.8)
ax.set_xticks(x); ax.set_xticklabels(wf_df["year"], color=SUB)
ax.set_title("Walk-forward by calendar year", color=TXT, fontweight="bold", loc="left")
ax.legend(frameon=False, labelcolor=SUB, fontsize=9, loc="upper left")
plt.tight_layout(); plt.show()
```

## 4. BLOCK MONTE CARLO BOOTSTRAP (10,000 SIMULATIONS)
Trades are resampled in blocks of 5 (streaks preserved) and each simulated equity path is built from the **daily MTM paths** of the sampled trades. Run at the robot's sizing and at 1.5x. The stop and the size are the risk controls of this edge; the tail that matters is the gap, which the paths contain because gap exits are real prices.


```
paths = {k: eng.trade_mtm_paths(df, trades_all, sizing=f) for k, f in SIZES.items()}
mcs = {k: monte_carlo_block(scaled(trades_all, f), n_sim=10000, block=5, mode="compound", seed=42, mtm_paths=paths[k]) for k, f in SIZES.items()}
rows = []
for k, m in mcs.items():
    rows.append({"Sizing": k, "Median return": f"{m['ret_p50'] * 100:.1f}%", "p5 return": f"{m['ret_p5'] * 100:.1f}%",
                 "Median max DD": f"{m['mdd_p50'] * 100:.2f}%", "Worst-5% DD (mdd_p5)": f"{m['mdd_p5'] * 100:.2f}%",
                 "Worst simulated DD": f"{m['mdd_worst'] * 100:.2f}%", "Prob. ruin (50% DD)": f"{m['prob_ruin'] * 100:.2f}%",
                 "Prob. positive": f"{m['prob_positive'] * 100:.1f}%", "Real DD of this history": f"{m['real_mdd'] * 100:.2f}%"})
print("=" * 70)
print("BLOCK MONTE CARLO SUMMARY (10,000 RUNS, daily-MTM drawdown)")
print("=" * 70)
display(pd.DataFrame(rows).set_index("Sizing"))
print(f"Gate limit on mdd_p5: {GATE['mc_mdd_p5_min'] * 100:.0f}% | the project's hard limit is -{HARD_LIMIT:.0%}: mdd_p5 should also stay inside it.")

mc0 = mcs[OFFICIAL]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.8), facecolor=BG)
dark_ax(ax1); dark_ax(ax2)
ax1.hist(mc0["rets"] * 100, bins=60, color="#5468ff", alpha=0.8, edgecolor=BG)
ax1.axvline(0, color=RED, lw=1.2); ax1.axvline(mc0["ret_p5"] * 100, color=ORANGE, ls="--", lw=1.2)
ax1.set_title(f"Simulated total return (%) · {OFFICIAL}", color=TXT, fontweight="bold", loc="left")
ax2.hist(mc0["mdds"] * 100, bins=60, color="#5468ff", alpha=0.8, edgecolor=BG)
ax2.axvline(GATE["mc_mdd_p5_min"] * 100, color=RED, lw=1.2, label="gate limit")
ax2.axvline(-HARD_LIMIT * 100, color=ORANGE, lw=1.2, label="hard limit")
ax2.axvline(mc0["mdd_p5"] * 100, color=GREEN, ls="--", lw=1.2, label="worst 5%")
ax2.set_title("Simulated max drawdown (%)", color=TXT, fontweight="bold", loc="left")
ax2.legend(frameon=False, labelcolor=SUB, fontsize=9)
plt.tight_layout(); plt.show()
```

## 5. MONKEY TEST (2,000 SYNTHETIC RANDOM PORTFOLIOS)
Same number of trades, same direction and holding time as each real trade, same costs.
- **A · Timing monkey**: random entry on *any* day. It rules out that the result is oil drift plus a stop.
- **B · Filter monkey**: random choice among all **naked-trigger** days (trend filter off). It answers whether the trend filter picks better days than the trigger alone.


```
df_naked = prep(df_raw, trend_mode="off")
elig_A = pd.Series(True, index=df.index)
elig_B = (df_naked["long_sig"] | df_naked["short_sig"]).shift(1, fill_value=False)   # entry bar = signal bar + 1
mk_kw = dict(n_sim=2000, entry_col="open", exit_col="open", cost_pct_per_side=COST_BPS / 100.0, seed=42)
mk_A = monkey_test_sided(df, trades_all, eligible=elig_A, **mk_kw)
mk_B = monkey_test_sided(df, trades_all, eligible=elig_B, **mk_kw)

def plot_monkey_local(mk, title):
    fig, ax = plt.subplots(figsize=(10, 3.8), facecolor=BG)
    dark_ax(ax)
    ax.hist(np.clip(mk["pfs"], 0, 5), bins=60, color="#5468ff", alpha=0.8, edgecolor=BG)
    ax.axvline(mk["pf_real"], color=GREEN, lw=1.8, label=f"strategy PF {mk['pf_real']:.2f}")
    ax.axvline(mk["pf_monkey_median"], color=ORANGE, ls="--", lw=1.2, label=f"monkey median {mk['pf_monkey_median']:.2f}")
    ax.set_title(title, color=TXT, fontweight="bold", loc="left")
    ax.legend(frameon=False, labelcolor=SUB, fontsize=9)
    plt.tight_layout(); plt.show()

print("=" * 70 + "\nMONKEY TEST RESULTS\n" + "=" * 70)
for name, mk in (("A · timing monkey (any day)", mk_A), ("B · filter monkey (any naked-trigger day)", mk_B)):
    print(f"{name}: strategy PF {mk['pf_real']:.3f} | monkey median PF {mk['pf_monkey_median']:.3f} | beats {mk['pct_pf'] * 100:.1f}% on PF, "
          f"{mk['pct_expectancy'] * 100:.1f}% on expectancy (gate >= {GATE['monkey_pct_min'] * 100:.0f}%)")
plot_monkey_local(mk_A, "Monkey test A · random entries, same direction and duration")
plot_monkey_local(mk_B, "Monkey test B · random naked-trigger days")
```

## 6. STRESS TESTING: COSTS, WINDFALL EXCLUSION, GAP DEPENDENCE, REGIMES & CONCENTRATION
The cost sweep is the key edge-specific stress: the newsletter's own question is whether $200 or $100 round trip changes the picture. At ~$80 per barrel and 1,000 barrels, $100 round trip is about 6 bps per side and $200 about 12. The variants for Darwinex and Axi must be read against the break-even found here.


```
print("=" * 70 + "\nSTRESS TESTING BATTERY\n" + "=" * 70)
rows = []
for c in sorted({COST_BPS, 2 * COST_BPS, 6.0, 12.0, 20.0, 30.0, 45.0, 60.0}):
    t = eng.run_roughneck_backtest(df, **{**RULES, "cost_bps_per_side": c})
    m = compute_metrics(t, 1.0, 0.0)
    rows.append({"Cost bps/side": c, "Round trip %": 2 * c / 100, "Trades": len(t), "Profit Factor": round(m["profit_factor"], 3),
                 "Mean net %": round(m["expectancy"], 3), "t-stat": round(tstat(t["pnl"]), 2)})
cost_tbl = pd.DataFrame(rows).set_index("Cost bps/side")
mean0 = float(cost_tbl.loc[COST_BPS, "Mean net %"])
breakeven_bps = COST_BPS + mean0 * 50.0     # mean net falls by 2*c/100 % per extra bps per side
display(cost_tbl)
print(f"Approximate break-even cost: {breakeven_bps:.0f} bps per side ({breakeven_bps * 2 / 100:.2f}% round trip) at the configured rules.")

trades_all["year"] = pd.to_datetime(trades_all["entry_time"]).dt.year
annual = trades_all.groupby("year")["pnl"].sum()
top2 = annual.sort_values(ascending=False).head(2).index.tolist()
t_ex = trades_all[~trades_all["year"].isin(top2)]
m_ex = compute_metrics(t_ex, 1.0, 0.0)

k = max(1, int(np.ceil(0.10 * len(trades_all))))
srt = trades_all["pnl"].sort_values(ascending=False)
share_top10 = float(srt.head(k).sum() / trades_all["pnl"].clip(lower=0).sum())
pf_ex_top10 = profit_factor(srt.iloc[k:].to_numpy())

# gap dependence: remove the 3 worst trades (the April-2020 type): does the edge need luck in the left tail?
worst3 = trades_all["pnl"].nsmallest(3).index
pf_ex_worst3 = profit_factor(trades_all.drop(worst3)["pnl"].to_numpy())
gross_loss = -trades_all.loc[trades_all["pnl"] < 0, "pnl"].sum()
share_worst3 = float(-trades_all.loc[worst3, "pnl"].sum() / gross_loss) if gross_loss > 0 else np.nan

m_base, m_x2 = compute_metrics(trades_all, 1.0, 0.0), cost_tbl.loc[2 * COST_BPS]
stress_rows = [
    {"Stress Scenario": f"Baseline ({COST_BPS:g} bps / side)", "Trades": len(trades_all), "Profit Factor": f"{m_base['profit_factor']:.3f}", "Expectancy": f"{m_base['expectancy']:.3f}%"},
    {"Stress Scenario": f"Costs x2 ({2 * COST_BPS:g} bps / side)", "Trades": int(m_x2["Trades"]), "Profit Factor": f"{m_x2['Profit Factor']:.3f}", "Expectancy": f"{m_x2['Mean net %']:.3f}%"},
    {"Stress Scenario": f"Exclude best years ({top2[0]}, {top2[1]})", "Trades": len(t_ex), "Profit Factor": f"{m_ex['profit_factor']:.3f}", "Expectancy": f"{m_ex['expectancy']:.3f}%"},
    {"Stress Scenario": f"Exclude best 10% of trades ({k})", "Trades": len(trades_all) - k, "Profit Factor": f"{pf_ex_top10:.3f}", "Expectancy": f"{srt.iloc[k:].mean():.3f}%"},
    {"Stress Scenario": "Long side only", "Trades": int((trades_all["type"] == "long").sum()), "Profit Factor": f"{profit_factor(trades_all.loc[trades_all['type'] == 'long', 'pnl']):.3f}", "Expectancy": f"{trades_all.loc[trades_all['type'] == 'long', 'pnl'].mean():.3f}%"},
    {"Stress Scenario": "Short side only", "Trades": int((trades_all["type"] == "short").sum()), "Profit Factor": f"{profit_factor(trades_all.loc[trades_all['type'] == 'short', 'pnl']):.3f}", "Expectancy": f"{trades_all.loc[trades_all['type'] == 'short', 'pnl'].mean():.3f}%"},
]
for name, (a, b) in {"COVID year (2020)": (2020, 2020), "Post-COVID (2021+)": (2021, 2100), "Pre-COVID (<=2019)": (1990, 2019)}.items():
    tr = trades_all[(trades_all["year"] >= a) & (trades_all["year"] <= b)]
    if len(tr):
        mr = compute_metrics(tr, 1.0, 0.0)
        stress_rows.append({"Stress Scenario": name, "Trades": len(tr), "Profit Factor": f"{mr['profit_factor']:.3f}", "Expectancy": f"{mr['expectancy']:.3f}%"})
print()
display(pd.DataFrame(stress_rows).set_index("Stress Scenario"))
print(f"Best 10% of trades ({k}) carry {share_top10 * 100:.0f}% of gross profit | the 3 worst trades carry {share_worst3 * 100:.0f}% of gross loss (PF without them {pf_ex_worst3:.2f}).")

# the newsletter's other question: which years concentrate the losses?
by_year = trades_all.groupby("year")["pnl"].agg(n="size", net="sum", worst="min")
by_year["share_of_gross_loss_%"] = (-trades_all[trades_all["pnl"] < 0].groupby("year")["pnl"].sum() / gross_loss * 100).reindex(by_year.index).fillna(0)
print("\nNet result and share of gross loss by year:")
display(by_year.round(2))
max_year_loss_share = float(by_year["share_of_gross_loss_%"].max())

era_rows = []
for e, (a, b) in ERAS.items():
    te = trades_all[(trades_all["year"] >= a) & (trades_all["year"] <= b)]
    if len(te):
        era_rows.append({"Regime": e, "Trades": len(te), "PF": round(profit_factor(te["pnl"]), 3), "Mean net %": round(te["pnl"].mean(), 3), "t-stat": round(tstat(te["pnl"]), 2)})
print()
display(pd.DataFrame(era_rows).set_index("Regime"))
stress_ok = bool(m_x2["Profit Factor"] >= 1.0 and m_ex["profit_factor"] >= 1.0 and pf_ex_worst3 >= 1.0)
```

## 7. EDGE DECAY & TEMPORAL STABILITY
Rolling Profit Factor of the last 30 trades, PF by year, and the **z wear-and-tear protocol**: z = (mean of the last 20 trades - mu0) / (sigma0 / sqrt(20)), green > -1, yellow -1 to -2, red <= -2. mu0 and sigma0 come from the in-sample trades (before `oos_start_ts`).


```
oos_ts = pd.Timestamp(OOS_START)
roll = rolling_pf(trades_all, window=30)
plot_rolling_pf(roll, oos_start=oos_start, window=30)
py = pf_by_year(trades_all)
print("PF by year:"); display(py.round(3))
ed = edge_decay_summary(trades_all)
print(f"Recent years {ed['recent_years']} PF {ed['recent']['pf']:.3f} vs historical PF {ed['historical']['pf']:.3f} | expectancy ratio {ed['expectancy_ratio']:.2f} | decay warning: {ed['warning']}")

W = 20
ref = trades_all.loc[pd.to_datetime(trades_all["entry_time"]) < oos_ts, "pnl"]
mu0, sd0 = float(ref.mean()), float(ref.std(ddof=1))
s = trades_all.set_index(pd.to_datetime(trades_all["exit_time"]))["pnl"]
z = (s.rolling(W).mean() - mu0) / (sd0 / np.sqrt(W))
zc = z.dropna()
zone = pd.cut(zc, [-np.inf, -2, -1, np.inf], labels=["red", "yellow", "green"])
after = zone[zc.index >= oos_start]
print(f"\nReference (in-sample trades): mu0 = {mu0:+.3f}%, sigma0 = {sd0:.3f}%, n = {len(ref)}")
print(f"z today = {zc.iloc[-1]:+.2f} ({zone.iloc[-1]}) | minimum z = {zc.min():+.2f} on {zc.idxmin():%Y-%m-%d}")
print(f"Trades since OOS start by zone: {after.value_counts().to_dict()}")
fig, ax = plt.subplots(figsize=(14, 4.5), facecolor=BG)
dark_ax(ax)
ax.plot(zc.index, zc, color=TXT, lw=1.4)
ax.axhspan(-1, ax.get_ylim()[1], color=GREEN, alpha=0.06); ax.axhspan(-2, -1, color=ORANGE, alpha=0.10); ax.axhspan(ax.get_ylim()[0], -2, color=RED, alpha=0.10)
ax.axhline(-1, color=ORANGE, ls="--", lw=1); ax.axhline(-2, color=RED, ls="--", lw=1); ax.axvline(oos_start, color=SUB, ls=":")
ax.set_title("z wear-and-tear protocol (last 20 trades)", color=TXT, fontweight="bold", loc="left")
plt.tight_layout(); plt.show()
```

## 8. FULL VALIDATION GATE RUN (AUTOMATED MULTI-PHASE AUDIT)
The plateau phase needs the in-sample grid, so it is rebuilt here with the same window logic as notebook 02. The official verdict is the robot's sizing; the 1.5x run is shown for transparency. **Note:** `validation_gate`'s internal monkey phase uses `eligible` / entry-exit columns of the library; if it is long-only, treat phase 3 as indicative and rely on section 5 (direction-aware).


```
def _first_ok(d):
    return d.index[d["warm"].to_numpy().argmax()]
common_start = max(_first_ok(d) for d in preps.values())

GATE_ORIG = dict(GATE)
_is_years = (pd.Timestamp(OOS_START) - common_start).days / 365.25
BASE_IS_YEARS = 6.5
if SCALE_SAMPLE_GATES and _is_years < BASE_IS_YEARS:
    GATE['plateau_n_min'] = max(5, int(round(GATE_ORIG['plateau_n_min'] * _is_years / BASE_IS_YEARS)))
print(f"In-sample with warm-up done: {_is_years:.1f} years | plateau_n_min: {GATE_ORIG['plateau_n_min']} -> {GATE['plateau_n_min']}")
print('validation_gate.DEFAULTS in use:', GATE)

def evaluate_gate(m, L):
    d = prep(df_raw, atr_len=L, long_atr_mult=m)
    d = d[(d.index >= common_start) & (d.index < OOS_START)]
    t = eng.run_roughneck_backtest(d, **{**RULES, "long_atr_mult": m, "atr_len": L})
    return (profit_factor(t["pnl"]) if len(t) else 0.0, len(t))

pf_grid, n_grid = grid_search(evaluate_gate, MULTS, ATR_LENS)
validations = {}
for i, (k, f) in enumerate(SIZES.items(), 1):
    print("\n" + "=" * 70)
    print(f"{i}. VALIDATION GATE: {k} SIZING" + (" (OFFICIAL VERDICT)" if k == OFFICIAL else " (FOR TRANSPARENCY)"))
    print("=" * 70)
    validations[k] = run_validation(
        trades_df=scaled(trades_all, f), df_prices=df, eligible=elig_A, grid_pf=pf_grid, grid_n=n_grid, chosen=CHOSEN,
        oos_start=oos_start, mode="compound", mtm_paths=paths[k],
        monkey_entry_col="open", monkey_exit_col="open", monkey_cost_pct_per_side=COST_BPS / 100.0, verbose=True)
validation = validations[OFFICIAL]
```

## 9. STRATEGY METRICS DEFINITION & VERDICT


```
ret_series = eng.daily_returns(df, trades_all, sizing="fraction")
eq_series = (1.0 + ret_series).cumprod()
metrics = {"sharpe": float(sharpe_ratio(ret_series, periods_per_year=PPY)), "max_drawdown": float(max_drawdown(eq_series)), "num_trades": int(len(trades_all))}
print("=" * 70 + f"\nFINAL STRATEGY METRICS ({OFFICIAL} SIZING, WHOLE PERIOD)\n" + "=" * 70)
print(f"Sharpe Ratio : {metrics['sharpe']:.2f}\nMax Drawdown : {metrics['max_drawdown'] * 100:.2f}%\nTotal Trades : {metrics['num_trades']}")
print(f"Validation Gate Overall ({OFFICIAL}): {validation['status']}")

ph = validation["phases"]
mdd_p5 = ph["2_monte_carlo"]["mdd_p5"]
mc_margin_ok = bool(mdd_p5 > GATE["mc_mdd_p5_min"] - 0.01)
mc_hard_ok = bool(mdd_p5 > -HARD_LIMIT)
print("\n" + "=" * 70 + "\nVERDICT SUMMARY\n" + "=" * 70)
def tag(p):
    return "INFO" if p.get("informational") else ("SKIP" if p.get("skipped") else ("PASS" if p["passed"] else "FAIL"))
for name, p in ph.items():
    print(f"[{tag(p)}] {name}")
for k, v in validations.items():
    print(f"Gate at {k}: {v['status']} (failed: {[n for n, p in v['phases'].items() if 'passed' in p and not p['passed']]})")
print(f"Walk-forward gate: {'PASSED' if wf_pass else 'FAILED'} | stress (x2 costs, ex best years, ex 3 worst trades keep PF >= 1): {'OK' if stress_ok else 'NOT OK'}")
print(f"Monkey A (timing): beats {mk_A['pct_pf'] * 100:.1f}% | Monkey B (trend filter vs naked trigger days): beats {mk_B['pct_pf'] * 100:.1f}% (direction-aware, section 5)")
print(f"Monte Carlo mdd_p5 at {OFFICIAL}: {mdd_p5 * 100:.2f}% | gate limit {GATE['mc_mdd_p5_min'] * 100:.0f}% (1-point margin ok: {mc_margin_ok}) | inside the hard limit -{HARD_LIMIT:.0%}: {mc_hard_ok}")
print(f"Cost break-even: ~{breakeven_bps:.0f} bps per side | worst year holds {max_year_loss_share:.0f}% of gross loss | z today: {zc.iloc[-1]:+.2f} ({zone.iloc[-1]})")
print()
print("OVERALL (official run, strict gate): " + validation["status"] + (". Edge confirmed for the next stage." if validation["passed"] else ". Do not promote without documenting the failed phases (a margin or an exception must be declared, not silently applied)."))
```

## 10. SAVE THE RESULTS OF THIS NOTEBOOK FOR THE VARIANT


```
def _scalars(p):
    return {k: v for k, v in p.items() if isinstance(v, (int, float, str, bool, np.generic))}

save_json(cfg, "03_validation.json", {
    "variant": cfg["id"], "ticker": TICKER, "params": cfg["params"], "oos_start": str(oos_start.date()), "official_sizing": OFFICIAL,
    "status": {k: v["status"] for k, v in validations.items()}, "metrics": metrics,
    "phases": {k: {n: _scalars(p) for n, p in v["phases"].items()} for k, v in validations.items()},
    "walk_forward": {"efficiency": float(efficiency), "pct_positive_years": pct_positive_years, "worst_mdd": worst_oos_mdd, "passed": wf_pass},
    "monkey": {"A_pct_pf": mk_A["pct_pf"], "B_pct_pf": mk_B["pct_pf"]},
    "monte_carlo_mdd_p5": {k: m["mdd_p5"] for k, m in mcs.items()},
    "mc_passes_with_1pt_margin": mc_margin_ok, "mc_inside_hard_limit": mc_hard_ok,
    "cost_breakeven_bps_per_side": float(breakeven_bps), "cost_sweep": cost_tbl.reset_index().to_dict(orient="records"),
    "profit_share_top10pct_trades": share_top10, "gross_loss_share_worst3": share_worst3, "pf_ex_worst3": float(pf_ex_worst3),
    "max_year_gross_loss_share_pct": max_year_loss_share,
    "z_protocol": {"mu0": mu0, "sigma0": sd0, "z_today": float(zc.iloc[-1]), "zone_today": str(zone.iloc[-1]), "z_min": float(zc.min())},
    "edge_decay_warning": bool(ed["warning"]), "stress_ok": stress_ok,
})
```
