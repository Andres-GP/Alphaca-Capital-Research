# 2. GOTOBI EFFECT · IN-SAMPLE SENSITIVITY & PLATEAU CHECK

In-sample sensitivity of the **USDJPY Gotobi** rule (long 07:30 -> 09:55 JST on Gotobi days, M5 bars, UTC), following the flow of notebook 02 of the Monday / RSI2 edges.

### STRICT METHODOLOGICAL CONSTRAINT
> **IN-SAMPLE ONLY**: everything before `splits.oos_start`. The OOS block belongs to notebook 03.
> Gotobi days and times are **not optimised** (frozen in the YAML). This notebook measures how fragile the frozen rule is; **nothing is re-tuned here**.

### OBJECTIVES
1. **Time-window plateau**: entry x exit grid around the frozen window must be a stable region, not an isolated peak (plateau + anti-cliff).
2. **Cost sensitivity**: flat-spread and feed-scale sweeps, breakeven spread and breakeven multiple.
3. **Calendar anatomy**: which Gotobi days / weekdays / seasons carry the edge, leave-one-label-out, alternative calendar conventions.
4. **Execution filter & spread**: how the entry spread (a winter-rollover effect) interacts with edge, and what the spread filter costs in signals.
5. **Stability through time**: by year, by period, rolling window.

Every gate goes into one `Checks` registry (section 8) that is saved for notebook 03 (section 9).


```python
VARIANT = "v1_axi_usdjpy"              # variants/<name>.yaml
GRID_SPAN_MIN, GRID_STEP_MIN = 30, 10   # time grid: frozen entry/exit +- span, every step (minutes)
ROLL_BINS = 5                      # quantile buckets for the entry-spread analysis
```

## 1. IMPORTS AND CONFIG


```python
import sys, importlib
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

def find_edge_dir(start=None):
    """Folder that holds BOTH variants/ and gotobi_engine.py (notebooks, engine, utils and variants/ live together).
    Looks in cwd and its parents, then one or two levels below each of them."""
    here = (start or Path.cwd()).resolve()
    for base in (here, *here.parents):
        for cand in (base, *base.glob("*"), *base.glob("*/*")):
            if cand.is_dir() and (cand / "variants").is_dir() and (cand / "gotobi_engine.py").is_file():
                return cand
    raise FileNotFoundError(
        f"Could not find a folder with 'variants/' AND 'gotobi_engine.py' near {here}. "
        "Put gotobi_engine.py, gotobi_utils.py and variant_config.py next to variants/ (02_strategy_development/Gotobi/).")

EDGE_DIR = find_edge_dir()
if str(EDGE_DIR) not in sys.path:
    sys.path.insert(0, str(EDGE_DIR))

import gotobi_engine as eng
import gotobi_utils as U
import variant_config
from variant_config import load_variant, save_json

importlib.reload(eng); importlib.reload(U)       # resets ENGINE_DEFAULTS: nothing leaks between variants
variant_config.EDGE_DIR = EDGE_DIR

cfg = load_variant(VARIANT)
eng.set_engine_defaults(**cfg["engine_defaults"])
eng.apply_cfd_preset(cfg["account"]["cfd_preset"])          # contract size / min lot / lot step of the YAML preset
eng.set_engine_defaults(account_ccy=cfg["account"]["ccy"])
INS, RULE, COSTS, ACC = cfg["instrument"], cfg["rule"], cfg["costs"], cfg["acceptance"]
OOS_START, RUN_DIR = cfg["oos_start_ts"], cfg["run_dir"]
ET, XT = RULE["entry_time_jst"], RULE["exit_time_jst"]
MODE, SCALE = COSTS["cost_mode"], float(COSTS["spread_scale"])
FLAT = sorted({float(x) for x in np.atleast_1d(COSTS["robustness"]["flat_spread_pips"])})
PF_MIN, N_MIN = float(ACC["pf_min"]), int(ACC["n_min"])
MAX_DROP = float(ACC.get("plateau_max_drop", 30))          # % PF drop tolerated one step away (not in the YAML: default 30)
share = lambda x: x / 100 if x > 1 else float(x)           # accepts 0.2 or 20 (%)
C = U.Checks()                                             # PASS / FAIL registry (grouped in section 8)

print(f"Variant {cfg['id']} | {INS['symbol']} ({INS['broker']}) | long {ET} -> {XT} JST | cost_mode={MODE}, spread_scale={SCALE:g}")
print(f"Gates: PF >= {PF_MIN}, N >= {N_MIN}, plateau drop <= {MAX_DROP:g}% | frozen rules hash {variant_config.rules_hash(cfg)} | run folder {RUN_DIR}")

# ---- small helpers shared by the sections ----
def summ(t):
    """n / PF / mean net bps / t / win % of a trades frame (net of costs)."""
    s = eng.trade_stats(t)
    return dict(n=s["n"], pf=s["pf"], mean=s["mean_bps"], t=s["t"], win=100 * s["win_rate"])

def parts_table(parts):
    """One row per named trades frame: summ() + standard error of the mean (bps)."""
    out = pd.DataFrame({k: summ(t) for k, t in parts.items()}).T.astype(float)
    out["se"] = [U.mean_se(t["pnl_bps"])[1] for t in parts.values()]
    return out

def bars(ax, tbl, title):
    """Mean net bps per group with +-1 SE and N."""
    x = np.arange(len(tbl))
    ax.bar(x, tbl["mean"], yerr=tbl["se"], width=0.6, ecolor=U.SUB, color=[U.GREEN if v > 0 else U.RED for v in tbl["mean"]])
    ax.axhline(0, color=U.SUB, lw=0.6)
    ax.set_xticks(x); ax.set_xticklabels([str(i) for i in tbl.index], color=U.SUB)
    for i, n in enumerate(tbl["n"]):
        ax.text(i, ax.get_ylim()[0], f"N={int(n)}", color=U.SUB, fontsize=8, ha="center", va="bottom")
    U.set_title(ax, title)

hhmm = lambda m: f"{m // 60:02d}:{m % 60:02d}"
to_min = lambda s: int(s[:2]) * 60 + int(s[3:5])
```

    Variant GOTOBI.usdjpy.cfd.v1 | USDJPY (Axi) | long 07:30 -> 09:55 JST | cost_mode=feed, spread_scale=0.7
    Gates: PF >= 1.2, N >= 600, plateau drop <= 30% | frozen rules hash 99a05a00 | run folder /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy


## 2. IN-SAMPLE DATA SETUP

The raw M5 history is cut at the JST midnight of `oos_start` (`split_df`: no position is open at that instant). The engine has no warm-up, so nothing is lost by cutting. `prepare()` is not used: it would pin the entry/exit times that section 3 sweeps.


```python
df_raw = eng.load_data(start=INS["start"], end=INS.get("end"))
df_is, _ = eng.split_df(df_raw, OOS_START)
a, b = (df_is.index[0] + eng.JST).normalize(), (df_is.index[-1] + eng.JST).normalize()
years_is = (b - a).days / 365.25

base = eng.run_gotobi_backtest(df_is)                     # frozen rules (engine defaults = YAML)
B = summ(base)
tpy = ACC["trades_per_year"]
val = eng.validate(df_is, base, expected_per_year=tuple(tpy) if np.ndim(tpy) else (66, 74))
min_t = float(cfg["evidence_thresholds"]["min_t_net"])
k_hyp = int(cfg["evidence_thresholds"]["hypotheses_tested"])

print("=" * 70)
print(f"IN-SAMPLE WINDOW: {a:%Y-%m-%d} -> {b:%Y-%m-%d} ({years_is:.1f} years, {len(df_is):,} M5 bars)")
print("=" * 70)
print(f"Frozen rule: {B['n']} trades | PF {B['pf']:.3f} | mean {B['mean']:+.2f} bps net | t {B['t']:.2f} | win {B['win']:.1f}% | {B['n'] / years_is:.0f} trades/year")
print(f"Mean round-trip cost {base['cost_bps'].mean():.2f} bps | mean gross {base['pnl_gross_bps'].mean():+.2f} bps | mean entry spread {base['spread_pips'].mean():.2f} pips (Axi-equivalent)")
print(f"Evidence bar: min_t_net {min_t:g} | Bonferroni one-sided threshold for {k_hyp} hypotheses: t >= {eng.hypothesis_threshold(k_hyp):.2f}")
print("Engine validate():", {k: v for k, v in val.items()})

C("2 Setup", "engine validate (in-sample)", val["all_ok"], ", ".join(k for k, v in val.items() if not v and k != "all_ok"))
C("2 Setup", "N in-sample >= n_min", B["n"] >= N_MIN, f"{B['n']} vs {N_MIN}")
C("2 Setup", "PF net (in-sample) >= pf_min", B["pf"] >= PF_MIN, f"{B['pf']:.3f} vs {PF_MIN}")
C("2 Setup", "t net (in-sample) >= min_t_net", B["t"] >= min_t, f"{B['t']:.2f} vs {min_t:g}")
```

    ======================================================================
    IN-SAMPLE WINDOW: 2017-01-02 -> 2022-12-31 (6.0 years, 447,700 M5 bars)
    ======================================================================
    Frozen rule: 425 trades | PF 1.764 | mean +3.02 bps net | t 3.99 | win 60.0% | 71 trades/year
    Mean round-trip cost 0.77 bps | mean gross +3.79 bps | mean entry spread 0.88 pips (Axi-equivalent)
    Evidence bar: min_t_net 2.5 | Bonferroni one-sided threshold for 17 hypotheses: t >= 2.75
    Engine validate(): {'weekly_structure': True, 'no_rollover': True, 'constant_window': True, 'no_overlap': True, 'mtm_reconciles': True, 'trades_per_year': True, 'entry_is_2230_utc': True, 'all_ok': True}
       [PASS] engine validate (in-sample)
       [FAIL] N in-sample >= n_min  ->  425 vs 600
       [PASS] PF net (in-sample) >= pf_min  ->  1.764 vs 1.2
       [PASS] t net (in-sample) >= min_t_net  ->  3.99 vs 2.5





    'PASS'



## 3. TIME-WINDOW PLATEAU (ENTRY x EXIT GRID)

The window is frozen, not optimised, so the question is not "which cell is best" but **"is the frozen cell on a plateau?"**. Each cell re-runs the frozen rule with only `entry_time` / `exit_time` changed (feed costs of the entry bar of that cell; earlier entries sit closer to the rollover, where the winter spread is wide). Blue square = frozen window.

Gate: all 9 cells of the 3x3 neighbourhood with PF >= `pf_min` and N >= `n_min` (plateau), and no neighbour more than `MAX_DROP`% below the centre (anti-cliff).


```python
E0, X0 = to_min(ET), to_min(XT)
ENT = [E0 + d for d in range(-GRID_SPAN_MIN, GRID_SPAN_MIN + 1, GRID_STEP_MIN)]
EXI = [X0 + d for d in range(-GRID_SPAN_MIN, GRID_SPAN_MIN + 1, GRID_STEP_MIN)]
CENTER = (hhmm(E0), hhmm(X0))

TR = {(e, x): eng.run_gotobi_backtest(df_is, entry_time=hhmm(e), exit_time=hhmm(x)) for e in ENT for x in EXI}
SG = {k: summ(t) for k, t in TR.items()}
grid = lambda col: pd.DataFrame({hhmm(x): {hhmm(e): SG[(e, x)][col] for e in ENT} for x in EXI})
pf_g, n_g, mean_g, t_g = grid("pf").clip(upper=99), grid("n"), grid("mean"), grid("t")

def heatmap(ax, g, title, center=0.0, fmt="{:.1f}", mark=None):
    """Annotated heatmap, colour symmetric around `center`; blue square marks the frozen cell."""
    v = g.to_numpy(float)
    span = np.nanmax(np.abs(v - center)) or 1.0
    ax.imshow(v, cmap="RdYlGn", vmin=center - span, vmax=center + span, aspect="auto")
    ax.set_xticks(range(g.shape[1])); ax.set_xticklabels(g.columns, rotation=45, color=U.SUB)
    ax.set_yticks(range(g.shape[0])); ax.set_yticklabels(g.index, color=U.SUB)
    for (r, c), val_ in np.ndenumerate(v):
        ax.text(c, r, fmt.format(val_), ha="center", va="center", fontsize=8, color="#15171c")
    if mark:
        r, c = g.index.get_loc(mark[0]), g.columns.get_loc(mark[1])
        ax.add_patch(plt.Rectangle((c - 0.5, r - 0.5), 1, 1, fill=False, ec=U.BLUE, lw=2.5))
    ax.set_xlabel("exit (JST)", color=U.SUB); ax.set_ylabel("entry (JST)", color=U.SUB)
    U.set_title(ax, title)

def plateau(pf, n, center, pf_min, n_min, max_drop):
    """Plateau + anti-cliff verdict of the 3x3 neighbourhood of `center`."""
    i, j = pf.index.get_loc(center[0]), pf.columns.get_loc(center[1])
    sl = (slice(max(i - 1, 0), i + 2), slice(max(j - 1, 0), j + 2))
    nb, nn, c = pf.iloc[sl], n.iloc[sl], float(pf.iloc[i, j])
    drop = float(max(0.0, (c - nb.min().min()) / c * 100)) if c > 0 else np.nan
    return dict(center_pf=c, worst_drop_pct=drop, plateau=bool((nb >= pf_min).all().all() and (nn >= n_min).all().all()),
                anticliff=bool(drop <= max_drop), edge=bool(i in (0, len(pf) - 1) or j in (0, len(pf.columns) - 1)), nb=nb, nn=nn)

pl = plateau(pf_g, n_g, CENTER, PF_MIN, N_MIN, MAX_DROP)
cells = mean_g.stack()
rank = int((cells > mean_g.loc[CENTER]).sum()) + 1

fig, axes = U.subplots(1, 3, figsize=(17, 4.8), grid=False)
heatmap(axes[0], pf_g, "Profit factor (net)", center=1.0, fmt="{:.2f}", mark=CENTER)
heatmap(axes[1], mean_g, "Mean net return per trade (bps)", center=0.0, mark=CENTER)
heatmap(axes[2], t_g, "t-stat of the mean", center=0.0, fmt="{:.1f}", mark=CENTER)
plt.tight_layout(); plt.show()

print(f"3x3 neighbourhood of the frozen window ({CENTER[0]} -> {CENTER[1]}):")
display(pl["nb"].round(3))
print(f"Center PF {pl['center_pf']:.3f} | worst neighbour drop {pl['worst_drop_pct']:.1f}% (max {MAX_DROP:g}%) | plateau {'YES' if pl['plateau'] else 'NO'} | anti-cliff {'PASS' if pl['anticliff'] else 'FAIL'}")
print(f"Cells with mean net > 0: {int((cells > 0).sum())} of {len(cells)} | cells with PF >= {PF_MIN}: {100 * (pf_g >= PF_MIN).to_numpy().mean():.0f}% | frozen cell ranks #{rank} of {len(cells)} by mean net")

C("3 Time window", "plateau (3x3, PF >= pf_min, N >= n_min)", pl["plateau"], f"center PF {pl['center_pf']:.2f}")
C("3 Time window", "anti-cliff (3x3)", pl["anticliff"], f"worst drop {pl['worst_drop_pct']:.1f}% vs {MAX_DROP:g}%")
C("3 Time window", "frozen cell not on grid edge", not pl["edge"])
C("3 Time window", "majority of grid cells have mean net > 0", (cells > 0).mean() > 0.5, f"{100 * (cells > 0).mean():.0f}% of cells")
```


    
![png](02_Gotobi_Sensitivity_files/02_Gotobi_Sensitivity_7_0.png)
    


    3x3 neighbourhood of the frozen window (07:30 -> 09:55):



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>09:45</th>
      <th>09:55</th>
      <th>10:05</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>07:20</th>
      <td>1.626</td>
      <td>1.848</td>
      <td>1.363</td>
    </tr>
    <tr>
      <th>07:30</th>
      <td>1.545</td>
      <td>1.764</td>
      <td>1.303</td>
    </tr>
    <tr>
      <th>07:40</th>
      <td>1.604</td>
      <td>1.833</td>
      <td>1.331</td>
    </tr>
  </tbody>
</table>
</div>


    Center PF 1.764 | worst neighbour drop 26.1% (max 30%) | plateau NO | anti-cliff PASS
    Cells with mean net > 0: 49 of 49 | cells with PF >= 1.2: 80% | frozen cell ranks #6 of 49 by mean net
       [FAIL] plateau (3x3, PF >= pf_min, N >= n_min)  ->  center PF 1.76
       [PASS] anti-cliff (3x3)  ->  worst drop 26.1% vs 30%
       [PASS] frozen cell not on grid edge
       [PASS] majority of grid cells have mean net > 0  ->  100% of cells





    'PASS'



### 3.1 WHERE DOES THE DRIFT LIVE? (INTRADAY PROFILE VS CONTROL DAYS)

Gross mean return from the entry bar (no costs), Gotobi days vs non-Gotobi business days (control, excluding the neighbouring business day of each Gotobi date), +-2 SE bands. Right: mean return per M5 step. A real Gotobi edge shows a positive slope **inside** the frozen window (shaded) and none on control days.


```python
gd = eng.gotobi_calendar(a, b).index
cd = eng.control_dates(a, b, exclude_neighbors=1)
prof_g = eng.intraday_profile(df_is, gd, "06:30", "11:00", ET)
prof_c = eng.intraday_profile(df_is, cd, "06:30", "11:00", ET)
lab, x = list(prof_g.index), np.arange(len(prof_g))

fig, (ax1, ax2) = U.subplots(1, 2, figsize=(15, 4.4))
for p, col, name in ((prof_c, U.SUB, f"Control days (N={int(prof_c['n'].max())})"), (prof_g, U.GREEN, f"Gotobi days (N={int(prof_g['n'].max())})")):
    ax1.plot(x, p["mean_cum_bps"], color=col, lw=1.8, label=name)
    ax1.fill_between(x, p["mean_cum_bps"] - 2 * p["se_cum_bps"], p["mean_cum_bps"] + 2 * p["se_cum_bps"], color=col, alpha=0.15)
ax2.bar(x, prof_g["mean_step_bps"], width=0.8, color=[U.GREEN if v > 0 else U.RED for v in prof_g["mean_step_bps"]])
ax2.plot(x, prof_c["mean_step_bps"], color=U.SUB, lw=1.2, label="Control days")
for ax in (ax1, ax2):
    ax.axvspan(lab.index(ET), lab.index(XT), color=U.BLUE, alpha=0.08)
    for t_ in (ET, XT):
        ax.axvline(lab.index(t_), color=U.ORANGE, ls="--", lw=1.1)
    ax.set_xticks(x[::6]); ax.set_xticklabels(lab[::6], rotation=45, color=U.SUB)
    U.legend(ax)
ax1.set_ylabel("Cumulative bps from entry (gross)", color=U.SUB); ax2.set_ylabel("bps per M5 step", color=U.SUB)
U.set_title(ax1, "Cumulative intraday drift (JST)"); U.set_title(ax2, "Drift per M5 step")
plt.tight_layout(); plt.show()
print(f"Gross drift entry -> exit: Gotobi {prof_g.loc[XT, 'mean_cum_bps']:+.2f} bps (SE {prof_g.loc[XT, 'se_cum_bps']:.2f}) vs control {prof_c.loc[XT, 'mean_cum_bps']:+.2f} bps (SE {prof_c.loc[XT, 'se_cum_bps']:.2f})")
```


    
![png](02_Gotobi_Sensitivity_files/02_Gotobi_Sensitivity_9_0.png)
    


    Gross drift entry -> exit: Gotobi +3.79 bps (SE 0.76) vs control +0.95 bps (SE 0.91)


## 4. COST SENSITIVITY AND BREAKEVEN

The spread is the whole cost of the strategy (one round-trip spread, charged at entry). Both sweeps run **without the spread filter** so the cost is isolated (with the filter, a larger `spread_scale` would also drop trades).
- **Flat spread** (`cost_mode="flat_pips"`): the robustness check the engine recommends for 2010-2020, when the feed spread is a modelled constant.
- **Feed scale** (`cost_mode="feed"`): the feed spread times `spread_scale` (placeholder 0.7 calibrated on 2024-26).

**Breakeven** = spread (or scale) where the mean net return crosses zero; **breakeven multiple** = breakeven / configured cost.


```python
NOFILT = dict(max_entry_spread_pips=float("inf"))
SPREADS = sorted({0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0} | set(FLAT))
SCALES = sorted({0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0} | {SCALE})
flat_tr = {}
for s in SPREADS:
    with U.engine_overrides(eng, flat_spread_pips=s):
        flat_tr[s] = eng.run_gotobi_backtest(df_is, cost_mode="flat_pips", **NOFILT)
feed_tr = {k: eng.run_gotobi_backtest(df_is, cost_mode="feed", spread_scale=k, **NOFILT) for k in SCALES}
flat_tbl, feed_tbl = parts_table(flat_tr), parts_table(feed_tr)
flat_tbl.index.name, feed_tbl.index.name = "flat spread (pips)", "spread_scale"

def breakeven(tbl):
    """Zero crossing of the mean net return (inf if it never crosses inside the grid and stays positive)."""
    z = U.interp_zero(tbl.index, tbl["mean"])
    return np.inf if np.isnan(z) and (tbl["mean"] > 0).all() else z

be_flat, be_scale = breakeven(flat_tbl), breakeven(feed_tbl)
if MODE == "feed":
    be_mult = be_scale / SCALE
elif MODE == "flat_pips":
    be_mult = be_flat / float(eng.ENGINE_DEFAULTS["flat_spread_pips"])
else:
    be_mult = np.nan

print("FLAT SPREAD SWEEP (in-sample, no spread filter)"); display(flat_tbl.round(3))
print("FEED SCALE SWEEP (in-sample, no spread filter)"); display(feed_tbl.round(3))
print(f"Breakeven flat spread: {be_flat:.2f} pips | breakeven spread_scale: {be_scale:.2f} (configured {SCALE:g}) | breakeven multiple ({MODE}): {be_mult:.2f}x (min {ACC['breakeven_mult_min']})")

fig, (ax1, ax2) = U.subplots(1, 2, figsize=(14, 4.2))
for ax, tbl, marks, be, xl in ((ax1, flat_tbl, FLAT, be_flat, "flat spread (pips)"), (ax2, feed_tbl, [SCALE], be_scale, "spread_scale")):
    ax.errorbar(tbl.index, tbl["mean"], yerr=tbl["se"], color=U.GREEN, marker="o", lw=1.8, ecolor=U.SUB, capsize=2)
    ax.axhline(0, color=U.RED, lw=1.0)
    for m in marks:
        ax.axvline(m, color=U.ORANGE, ls="--", lw=1.1)
    if np.isfinite(be):
        ax.axvline(be, color=U.BLUE, ls=":", lw=1.4, label=f"breakeven {be:.2f}")
        U.legend(ax, "upper right")
    ax.set_xlabel(xl, color=U.SUB); ax.set_ylabel("Mean net bps per trade (+-1 SE)", color=U.SUB)
U.set_title(ax1, "Flat spread sweep (orange = YAML robustness values)"); U.set_title(ax2, "Feed-scale sweep (orange = configured)")
plt.tight_layout(); plt.show()

C("4 Costs", "breakeven multiple >= breakeven_mult_min", None if np.isnan(be_mult) else be_mult >= float(ACC["breakeven_mult_min"]), f"{be_mult:.2f}x vs {ACC['breakeven_mult_min']}")
C("4 Costs", "mean net > 0 at every YAML flat spread", bool((flat_tbl.loc[FLAT, "mean"] > 0).all()), f"worst {flat_tbl.loc[FLAT, 'mean'].min():+.2f} bps at {max(FLAT):g} pips")
```

    FLAT SPREAD SWEEP (in-sample, no spread filter)



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
    <tr>
      <th>flat spread (pips)</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.0</th>
      <td>425.0</td>
      <td>2.039</td>
      <td>3.786</td>
      <td>5.000</td>
      <td>62.353</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>0.5</th>
      <td>425.0</td>
      <td>1.876</td>
      <td>3.342</td>
      <td>4.414</td>
      <td>61.412</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>0.7</th>
      <td>425.0</td>
      <td>1.815</td>
      <td>3.164</td>
      <td>4.179</td>
      <td>60.941</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>1.0</th>
      <td>425.0</td>
      <td>1.727</td>
      <td>2.898</td>
      <td>3.827</td>
      <td>60.000</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>1.5</th>
      <td>425.0</td>
      <td>1.589</td>
      <td>2.454</td>
      <td>3.241</td>
      <td>58.588</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>2.0</th>
      <td>425.0</td>
      <td>1.461</td>
      <td>2.010</td>
      <td>2.654</td>
      <td>56.235</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>3.0</th>
      <td>425.0</td>
      <td>1.235</td>
      <td>1.122</td>
      <td>1.482</td>
      <td>50.353</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>4.0</th>
      <td>425.0</td>
      <td>1.045</td>
      <td>0.234</td>
      <td>0.309</td>
      <td>47.294</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>6.0</th>
      <td>425.0</td>
      <td>0.753</td>
      <td>-1.541</td>
      <td>-2.035</td>
      <td>40.471</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>8.0</th>
      <td>425.0</td>
      <td>0.547</td>
      <td>-3.315</td>
      <td>-4.377</td>
      <td>36.471</td>
      <td>0.757</td>
    </tr>
  </tbody>
</table>
</div>


    FEED SCALE SWEEP (in-sample, no spread filter)



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
    <tr>
      <th>spread_scale</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.0</th>
      <td>425.0</td>
      <td>2.039</td>
      <td>3.786</td>
      <td>5.000</td>
      <td>62.353</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>0.5</th>
      <td>425.0</td>
      <td>1.839</td>
      <td>3.238</td>
      <td>4.279</td>
      <td>60.706</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>0.7</th>
      <td>425.0</td>
      <td>1.764</td>
      <td>3.019</td>
      <td>3.989</td>
      <td>60.000</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>1.0</th>
      <td>425.0</td>
      <td>1.657</td>
      <td>2.691</td>
      <td>3.554</td>
      <td>58.588</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>1.5</th>
      <td>425.0</td>
      <td>1.493</td>
      <td>2.144</td>
      <td>2.827</td>
      <td>56.471</td>
      <td>0.758</td>
    </tr>
    <tr>
      <th>2.0</th>
      <td>425.0</td>
      <td>1.346</td>
      <td>1.597</td>
      <td>2.100</td>
      <td>54.353</td>
      <td>0.760</td>
    </tr>
    <tr>
      <th>3.0</th>
      <td>425.0</td>
      <td>1.097</td>
      <td>0.503</td>
      <td>0.657</td>
      <td>49.647</td>
      <td>0.766</td>
    </tr>
    <tr>
      <th>4.0</th>
      <td>425.0</td>
      <td>0.899</td>
      <td>-0.590</td>
      <td>-0.763</td>
      <td>47.294</td>
      <td>0.774</td>
    </tr>
    <tr>
      <th>6.0</th>
      <td>425.0</td>
      <td>0.619</td>
      <td>-2.776</td>
      <td>-3.476</td>
      <td>40.235</td>
      <td>0.799</td>
    </tr>
  </tbody>
</table>
</div>


    Breakeven flat spread: 4.26 pips | breakeven spread_scale: 3.46 (configured 0.7) | breakeven multiple (feed): 4.94x (min 2.0)



    
![png](02_Gotobi_Sensitivity_files/02_Gotobi_Sensitivity_11_5.png)
    


       [PASS] breakeven multiple >= breakeven_mult_min  ->  4.94x vs 2.0
       [PASS] mean net > 0 at every YAML flat spread  ->  worst +2.90 bps at 1 pips





    'PASS'



## 5. CALENDAR ANATOMY

Descriptive, not for re-tuning: **which part of the calendar carries the edge?** Mean net bps (+-1 SE) by Gotobi label, weekday, US-DST season of the entry (winter = rollover 30 min before entry) and by whether the date was shifted to the previous business day. Then **leave-one-label-out** (the edge must not be one day of the month) and alternative calendar conventions (shift rule, month-end).


```python
ORDER = [str(d) for d in RULE["gotobi_days"]] + (["EOM"] if RULE["include_month_end"] else [])
winter = ~eng.us_dst_mask(pd.DatetimeIndex(base["entry_time"]))
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]
anat = {
    "Gotobi label": parts_table({k: base[base["label"] == k] for k in ORDER}),
    "Weekday": parts_table({DOW[d]: base[base["dow"] == d] for d in sorted(base["dow"].unique())}),
    "Season (entry)": parts_table({"winter": base[winter], "summer": base[~winter]}),
    "Date shifted?": parts_table({"nominal": base[~base["shifted"]], "shifted": base[base["shifted"]]}),
}
fig, axes = U.subplots(1, 4, figsize=(18, 3.9), grid=False)
for ax, (name, tbl) in zip(axes, anat.items()):
    bars(ax, tbl, name)
axes[0].set_ylabel("Mean net bps", color=U.SUB)
plt.tight_layout(); plt.show()
for name, tbl in anat.items():
    print(name); display(tbl.round(3))

# ---- leave-one-label-out ----
loo = parts_table({"all labels": base, **{f"without {k}": base[base["label"] != k] for k in ORDER}})
print("LEAVE-ONE-LABEL-OUT"); display(loo.round(3))

# ---- alternative calendar conventions (descriptive) ----
VARS = {"configured": {}, "shift_rule=next": dict(shift_rule="next"), "shift_rule=none (skip)": dict(shift_rule="none"),
        "no month-end": dict(include_month_end=False), "month-end only": dict(gotobi_days=())}
var_tbl = parts_table({k: eng.run_gotobi_backtest(df_is, **kw) for k, kw in VARS.items()})
print("CALENDAR CONVENTIONS (in-sample)"); display(var_tbl.round(3))

C("5 Calendar", "leave-one-label-out: PF >= pf_min in every case", bool((loo["pf"] >= PF_MIN).all()), f"min PF {loo['pf'].min():.2f} ({loo['pf'].idxmin()})")
C("5 Calendar", "mean net > 0 in every Gotobi label", bool((anat["Gotobi label"]["mean"] > 0).all()), f"{int((anat['Gotobi label']['mean'] > 0).sum())}/{len(ORDER)} labels positive")
```


    
![png](02_Gotobi_Sensitivity_files/02_Gotobi_Sensitivity_13_0.png)
    


    Gotobi label



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>5</th>
      <td>69.0</td>
      <td>0.612</td>
      <td>-2.199</td>
      <td>-1.413</td>
      <td>42.029</td>
      <td>1.557</td>
    </tr>
    <tr>
      <th>10</th>
      <td>72.0</td>
      <td>2.052</td>
      <td>3.861</td>
      <td>1.832</td>
      <td>56.944</td>
      <td>2.108</td>
    </tr>
    <tr>
      <th>15</th>
      <td>72.0</td>
      <td>1.603</td>
      <td>2.621</td>
      <td>1.427</td>
      <td>63.889</td>
      <td>1.837</td>
    </tr>
    <tr>
      <th>20</th>
      <td>72.0</td>
      <td>5.214</td>
      <td>6.360</td>
      <td>4.288</td>
      <td>75.000</td>
      <td>1.483</td>
    </tr>
    <tr>
      <th>25</th>
      <td>68.0</td>
      <td>3.322</td>
      <td>5.818</td>
      <td>3.828</td>
      <td>73.529</td>
      <td>1.520</td>
    </tr>
    <tr>
      <th>EOM</th>
      <td>72.0</td>
      <td>1.266</td>
      <td>1.593</td>
      <td>0.697</td>
      <td>48.611</td>
      <td>2.286</td>
    </tr>
  </tbody>
</table>
</div>


    Weekday



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>Mon</th>
      <td>55.0</td>
      <td>0.695</td>
      <td>-2.451</td>
      <td>-1.009</td>
      <td>38.182</td>
      <td>2.429</td>
    </tr>
    <tr>
      <th>Tue</th>
      <td>59.0</td>
      <td>4.486</td>
      <td>9.072</td>
      <td>3.191</td>
      <td>72.881</td>
      <td>2.843</td>
    </tr>
    <tr>
      <th>Wed</th>
      <td>64.0</td>
      <td>1.487</td>
      <td>1.511</td>
      <td>1.156</td>
      <td>62.500</td>
      <td>1.307</td>
    </tr>
    <tr>
      <th>Thu</th>
      <td>65.0</td>
      <td>1.297</td>
      <td>1.471</td>
      <td>0.712</td>
      <td>56.923</td>
      <td>2.068</td>
    </tr>
    <tr>
      <th>Fri</th>
      <td>182.0</td>
      <td>2.227</td>
      <td>3.794</td>
      <td>4.031</td>
      <td>62.637</td>
      <td>0.941</td>
    </tr>
  </tbody>
</table>
</div>


    Season (entry)



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>winter</th>
      <td>147.0</td>
      <td>1.544</td>
      <td>2.116</td>
      <td>1.874</td>
      <td>58.503</td>
      <td>1.129</td>
    </tr>
    <tr>
      <th>summer</th>
      <td>278.0</td>
      <td>1.877</td>
      <td>3.497</td>
      <td>3.527</td>
      <td>60.791</td>
      <td>0.991</td>
    </tr>
  </tbody>
</table>
</div>


    Date shifted?



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>nominal</th>
      <td>288.0</td>
      <td>1.593</td>
      <td>2.645</td>
      <td>2.682</td>
      <td>59.028</td>
      <td>0.986</td>
    </tr>
    <tr>
      <th>shifted</th>
      <td>137.0</td>
      <td>2.323</td>
      <td>3.807</td>
      <td>3.445</td>
      <td>62.044</td>
      <td>1.105</td>
    </tr>
  </tbody>
</table>
</div>


    LEAVE-ONE-LABEL-OUT



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>all labels</th>
      <td>425.0</td>
      <td>1.764</td>
      <td>3.019</td>
      <td>3.989</td>
      <td>60.000</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>without 5</th>
      <td>356.0</td>
      <td>2.114</td>
      <td>4.031</td>
      <td>4.786</td>
      <td>63.483</td>
      <td>0.842</td>
    </tr>
    <tr>
      <th>without 10</th>
      <td>353.0</td>
      <td>1.710</td>
      <td>2.848</td>
      <td>3.539</td>
      <td>60.623</td>
      <td>0.805</td>
    </tr>
    <tr>
      <th>without 15</th>
      <td>353.0</td>
      <td>1.801</td>
      <td>3.101</td>
      <td>3.728</td>
      <td>59.207</td>
      <td>0.832</td>
    </tr>
    <tr>
      <th>without 20</th>
      <td>353.0</td>
      <td>1.525</td>
      <td>2.338</td>
      <td>2.732</td>
      <td>56.941</td>
      <td>0.856</td>
    </tr>
    <tr>
      <th>without 25</th>
      <td>357.0</td>
      <td>1.588</td>
      <td>2.486</td>
      <td>2.921</td>
      <td>57.423</td>
      <td>0.851</td>
    </tr>
    <tr>
      <th>without EOM</th>
      <td>353.0</td>
      <td>1.937</td>
      <td>3.310</td>
      <td>4.223</td>
      <td>62.323</td>
      <td>0.784</td>
    </tr>
  </tbody>
</table>
</div>


    CALENDAR CONVENTIONS (in-sample)



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>configured</th>
      <td>425.0</td>
      <td>1.764</td>
      <td>3.019</td>
      <td>3.989</td>
      <td>60.000</td>
      <td>0.757</td>
    </tr>
    <tr>
      <th>shift_rule=next</th>
      <td>425.0</td>
      <td>1.605</td>
      <td>2.682</td>
      <td>3.342</td>
      <td>57.882</td>
      <td>0.802</td>
    </tr>
    <tr>
      <th>shift_rule=none (skip)</th>
      <td>288.0</td>
      <td>1.593</td>
      <td>2.645</td>
      <td>2.682</td>
      <td>59.028</td>
      <td>0.986</td>
    </tr>
    <tr>
      <th>no month-end</th>
      <td>356.0</td>
      <td>1.938</td>
      <td>3.298</td>
      <td>4.240</td>
      <td>62.079</td>
      <td>0.778</td>
    </tr>
    <tr>
      <th>month-end only</th>
      <td>72.0</td>
      <td>1.266</td>
      <td>1.593</td>
      <td>0.697</td>
      <td>48.611</td>
      <td>2.286</td>
    </tr>
  </tbody>
</table>
</div>


       [PASS] leave-one-label-out: PF >= pf_min in every case  ->  min PF 1.53 (without 20)
       [FAIL] mean net > 0 in every Gotobi label  ->  5/6 labels positive





    'FAIL'



## 6. EXECUTION FILTER AND ENTRY SPREAD

The feed spread at the entry bar is the engine's cost **and** a filter (`max_entry_spread_pips`). Three views: (left) the Axi-equivalent spread distribution by season, (centre) gross vs net edge by spread quantile, (right) what each cap costs in signals and what it earns **per signal** (mean net x share of signals kept), so a filter that only shrinks N is not mistaken for improvement.

Gate: the configured cap must not discard more than `max_signal_loss` of the signals.


```python
cap0 = eng.ENGINE_DEFAULTS["max_entry_spread_pips"]
cap0 = np.inf if cap0 is None else float(cap0)
CAPS = sorted({1.0, 1.5, 2.0, 3.0, 5.0, np.inf} | {cap0})
cap_tr = {c: eng.run_gotobi_backtest(df_is, max_entry_spread_pips=c) for c in CAPS}
t_all = cap_tr[np.inf]
n_all = len(t_all)
cap_lbl = lambda c: "no filter" if np.isinf(c) else f"<= {c:g} pips"
cap_tbl = parts_table({cap_lbl(c): t for c, t in cap_tr.items()})
cap_tbl["loss_%"] = [100 * (1 - len(t) / n_all) for t in cap_tr.values()]
cap_tbl["bps_per_signal"] = [t["pnl_bps"].sum() / n_all for t in cap_tr.values()]
signal_loss = 1 - len(cap_tr[cap0]) / n_all

bk = pd.qcut(t_all["spread_pips"], ROLL_BINS, duplicates="drop")
bk_lbl = [f"{iv.left:.1f}-{iv.right:.1f}" for iv in bk.cat.categories]
bkt = t_all.groupby(bk, observed=True).agg(n=("pnl_bps", "size"), gross=("pnl_gross_bps", "mean"), net=("pnl_bps", "mean"), cost=("cost_bps", "mean"))
bkt.index = bk_lbl
w_all = ~eng.us_dst_mask(pd.DatetimeIndex(t_all["entry_time"]))
bkt["winter_%"] = 100 * t_all.groupby(bk, observed=True).apply(lambda g: (~eng.us_dst_mask(pd.DatetimeIndex(g["entry_time"]))).mean()).to_numpy()

fig, axes = U.subplots(1, 3, figsize=(18, 4.2))
top = float(t_all["spread_pips"].quantile(0.99))
bins = np.linspace(0, max(top, 1.0), 30)
axes[0].hist(t_all.loc[w_all, "spread_pips"].clip(upper=top), bins=bins, color=U.BLUE, alpha=0.75, label="winter")
axes[0].hist(t_all.loc[~w_all, "spread_pips"].clip(upper=top), bins=bins, color=U.ORANGE, alpha=0.75, label="summer")
axes[0].set_xlabel("Axi-equivalent entry spread (pips, clipped at p99)", color=U.SUB); U.legend(axes[0], "upper right"); U.set_title(axes[0], "Entry spread by season")
xb, w = np.arange(len(bkt)), 0.38
axes[1].bar(xb - w / 2, bkt["gross"], w, color=U.SUB, label="gross"); axes[1].bar(xb + w / 2, bkt["net"], w, color=[U.GREEN if v > 0 else U.RED for v in bkt["net"]], label="net")
axes[1].axhline(0, color=U.SUB, lw=0.6); axes[1].set_xticks(xb); axes[1].set_xticklabels(bkt.index, color=U.SUB)
axes[1].set_xlabel("spread quantile bucket (pips)", color=U.SUB); U.legend(axes[1]); U.set_title(axes[1], "Gross vs net bps by entry spread")
xc = np.arange(len(cap_tbl))
axes[2].bar(xc - w / 2, cap_tbl["mean"], w, color=U.BLUE, label="mean per trade"); axes[2].bar(xc + w / 2, cap_tbl["bps_per_signal"], w, color=U.GREEN, label="mean per signal")
axes[2].axhline(0, color=U.SUB, lw=0.6); axes[2].set_xticks(xc); axes[2].set_xticklabels(cap_tbl.index, rotation=30, color=U.SUB)
for i, l in enumerate(cap_tbl["loss_%"]):
    axes[2].text(i, axes[2].get_ylim()[0], f"-{l:.0f}%", color=U.SUB, fontsize=8, ha="center", va="bottom")
U.legend(axes[2]); U.set_title(axes[2], "Spread cap: edge vs signals lost")
plt.tight_layout(); plt.show()

print("ENTRY-SPREAD BUCKETS"); display(bkt.round(2))
print("SPREAD CAP"); display(cap_tbl.round(3))
print(f"Configured cap: {cap_lbl(cap0)} -> signal loss {100 * signal_loss:.1f}% (max {100 * share(ACC['max_signal_loss']):.0f}%)")
C("6 Execution", "signal loss of configured spread cap <= max_signal_loss", signal_loss <= share(ACC["max_signal_loss"]), f"{100 * signal_loss:.1f}%")
```


    
![png](02_Gotobi_Sensitivity_files/02_Gotobi_Sensitivity_15_0.png)
    


    ENTRY-SPREAD BUCKETS



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>gross</th>
      <th>net</th>
      <th>cost</th>
      <th>winter_%</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>-0.0-0.6</th>
      <td>97</td>
      <td>3.06</td>
      <td>2.76</td>
      <td>0.30</td>
      <td>28.87</td>
    </tr>
    <tr>
      <th>0.6-0.7</th>
      <td>201</td>
      <td>3.67</td>
      <td>3.06</td>
      <td>0.61</td>
      <td>14.43</td>
    </tr>
    <tr>
      <th>0.7-0.9</th>
      <td>47</td>
      <td>5.69</td>
      <td>4.97</td>
      <td>0.71</td>
      <td>40.43</td>
    </tr>
    <tr>
      <th>0.9-8.5</th>
      <td>80</td>
      <td>3.84</td>
      <td>2.07</td>
      <td>1.77</td>
      <td>88.75</td>
    </tr>
  </tbody>
</table>
</div>


    SPREAD CAP



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
      <th>loss_%</th>
      <th>bps_per_signal</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>&lt;= 1 pips</th>
      <td>357.0</td>
      <td>1.877</td>
      <td>3.411</td>
      <td>4.064</td>
      <td>60.504</td>
      <td>0.839</td>
      <td>16.000</td>
      <td>2.865</td>
    </tr>
    <tr>
      <th>&lt;= 1.5 pips</th>
      <td>376.0</td>
      <td>1.842</td>
      <td>3.271</td>
      <td>4.008</td>
      <td>61.170</td>
      <td>0.816</td>
      <td>11.529</td>
      <td>2.894</td>
    </tr>
    <tr>
      <th>&lt;= 2 pips</th>
      <td>382.0</td>
      <td>1.830</td>
      <td>3.212</td>
      <td>3.990</td>
      <td>60.995</td>
      <td>0.805</td>
      <td>10.118</td>
      <td>2.887</td>
    </tr>
    <tr>
      <th>&lt;= 3 pips</th>
      <td>415.0</td>
      <td>1.768</td>
      <td>2.970</td>
      <td>3.932</td>
      <td>60.241</td>
      <td>0.755</td>
      <td>2.353</td>
      <td>2.900</td>
    </tr>
    <tr>
      <th>&lt;= 5 pips</th>
      <td>422.0</td>
      <td>1.769</td>
      <td>2.999</td>
      <td>3.982</td>
      <td>59.953</td>
      <td>0.753</td>
      <td>0.706</td>
      <td>2.978</td>
    </tr>
    <tr>
      <th>no filter</th>
      <td>425.0</td>
      <td>1.764</td>
      <td>3.019</td>
      <td>3.989</td>
      <td>60.000</td>
      <td>0.757</td>
      <td>0.000</td>
      <td>3.019</td>
    </tr>
  </tbody>
</table>
</div>


    Configured cap: no filter -> signal loss 0.0% (max 5%)
       [PASS] signal loss of configured spread cap <= max_signal_loss  ->  0.0%





    'PASS'



## 7. STABILITY THROUGH TIME

Annual mean net bps (+-1 SE), the YAML `periods`, and a rolling mean over `acceptance.roll_trades` trades. A Gotobi edge that only lived in one regime (e.g. a single multi-year stretch) would show up here before it reaches the OOS test.


```python
yr = pd.to_datetime(base["entry_date"]).dt.year
by_year = parts_table({int(y): g for y, g in base.groupby(yr)})
per = eng.period_stats(base, cfg["periods"]).astype(float)
per = per[per["n"] > 0]
ROLL = int(ACC["roll_trades"])
roll = base.set_index(pd.to_datetime(base["entry_date"]))["pnl_bps"].rolling(ROLL).mean().dropna()
need = float(ACC["years_pos_min"])
need = need if need > 1 else need * len(by_year)
n_pos = int((by_year["mean"] > 0).sum())

fig, (ax1, ax2) = U.subplots(1, 2, figsize=(15, 4.2), grid=False)
bars(ax1, by_year, "Mean net bps by entry year")
ax2.set_facecolor(U.PANEL); ax2.grid(True, color=U.GRIDC, alpha=0.9)
ax2.plot(roll.index, roll, color=U.GREEN, lw=1.6); ax2.axhline(0, color=U.RED, lw=1.0)
ax2.fill_between(roll.index, 0, roll, where=roll < 0, color=U.RED, alpha=0.25)
U.set_title(ax2, f"Rolling mean net bps ({ROLL} trades)")
plt.tight_layout(); plt.show()

print("BY YEAR"); display(by_year.round(3))
print("BY PERIOD (YAML periods, in-sample part)"); display(per.round(3))
print(f"Positive years: {n_pos}/{len(by_year)} (need {need:.1f}) | rolling window > 0 in {100 * (roll > 0).mean():.0f}% of the sample | worst rolling mean {roll.min():+.2f} bps")
C("7 Stability", "positive in-sample years >= years_pos_min", n_pos >= need, f"{n_pos}/{len(by_year)} vs {need:.1f}")
C("7 Stability", "every YAML period with data has mean net > 0", bool((per["mean"] > 0).all()), ", ".join(f"{k}: {v:+.1f}" for k, v in per["mean"].items()))
```


    
![png](02_Gotobi_Sensitivity_files/02_Gotobi_Sensitivity_17_0.png)
    


    BY YEAR



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>pf</th>
      <th>mean</th>
      <th>t</th>
      <th>win</th>
      <th>se</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2017</th>
      <td>71.0</td>
      <td>2.560</td>
      <td>5.136</td>
      <td>2.891</td>
      <td>71.831</td>
      <td>1.776</td>
    </tr>
    <tr>
      <th>2018</th>
      <td>71.0</td>
      <td>1.395</td>
      <td>1.726</td>
      <td>1.023</td>
      <td>60.563</td>
      <td>1.687</td>
    </tr>
    <tr>
      <th>2019</th>
      <td>70.0</td>
      <td>1.559</td>
      <td>1.869</td>
      <td>1.400</td>
      <td>61.429</td>
      <td>1.335</td>
    </tr>
    <tr>
      <th>2020</th>
      <td>70.0</td>
      <td>1.770</td>
      <td>3.723</td>
      <td>1.413</td>
      <td>52.857</td>
      <td>2.636</td>
    </tr>
    <tr>
      <th>2021</th>
      <td>71.0</td>
      <td>2.311</td>
      <td>2.566</td>
      <td>2.612</td>
      <td>59.155</td>
      <td>0.982</td>
    </tr>
    <tr>
      <th>2022</th>
      <td>72.0</td>
      <td>1.524</td>
      <td>3.088</td>
      <td>1.373</td>
      <td>54.167</td>
      <td>2.250</td>
    </tr>
  </tbody>
</table>
</div>


    BY PERIOD (YAML periods, in-sample part)



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>n</th>
      <th>mean</th>
      <th>mean_bps</th>
      <th>median_bps</th>
      <th>std_bps</th>
      <th>t</th>
      <th>p_one</th>
      <th>pf</th>
      <th>win_rate</th>
      <th>sum_bps</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2017-2022</th>
      <td>425.0</td>
      <td>3.019</td>
      <td>3.019</td>
      <td>2.175</td>
      <td>15.604</td>
      <td>3.989</td>
      <td>0.0</td>
      <td>1.764</td>
      <td>0.6</td>
      <td>1283.22</td>
    </tr>
  </tbody>
</table>
</div>


    Positive years: 6/6 (need 4.5) | rolling window > 0 in 100% of the sample | worst rolling mean +0.47 bps
       [PASS] positive in-sample years >= years_pos_min  ->  6/6 vs 4.5
       [PASS] every YAML period with data has mean net > 0  ->  2017-2022: +3.0





    'PASS'



## 8. PASS / FAIL SUMMARY


```python
chk = C.frame()
display(chk.style.map(lambda s: {"PASS": "color:#34d399", "FAIL": "color:#f0555a", "SKIP": "color:#f5a524"}.get(s, ""), subset=["status"]))
cnt = C.counts()
print(f"PASS {cnt['PASS']} | FAIL {cnt['FAIL']} | SKIP {cnt['SKIP']}")
```


<style type="text/css">
#T_27cf0_row0_col2, #T_27cf0_row2_col2, #T_27cf0_row3_col2, #T_27cf0_row5_col2, #T_27cf0_row6_col2, #T_27cf0_row7_col2, #T_27cf0_row8_col2, #T_27cf0_row9_col2, #T_27cf0_row10_col2, #T_27cf0_row12_col2, #T_27cf0_row13_col2, #T_27cf0_row14_col2 {
  color: #34d399;
}
#T_27cf0_row1_col2, #T_27cf0_row4_col2, #T_27cf0_row11_col2 {
  color: #f0555a;
}
</style>
<table id="T_27cf0">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_27cf0_level0_col0" class="col_heading level0 col0" >section</th>
      <th id="T_27cf0_level0_col1" class="col_heading level0 col1" >name</th>
      <th id="T_27cf0_level0_col2" class="col_heading level0 col2" >status</th>
      <th id="T_27cf0_level0_col3" class="col_heading level0 col3" >detail</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_27cf0_level0_row0" class="row_heading level0 row0" >0</th>
      <td id="T_27cf0_row0_col0" class="data row0 col0" >2 Setup</td>
      <td id="T_27cf0_row0_col1" class="data row0 col1" >engine validate (in-sample)</td>
      <td id="T_27cf0_row0_col2" class="data row0 col2" >PASS</td>
      <td id="T_27cf0_row0_col3" class="data row0 col3" ></td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row1" class="row_heading level0 row1" >1</th>
      <td id="T_27cf0_row1_col0" class="data row1 col0" >2 Setup</td>
      <td id="T_27cf0_row1_col1" class="data row1 col1" >N in-sample >= n_min</td>
      <td id="T_27cf0_row1_col2" class="data row1 col2" >FAIL</td>
      <td id="T_27cf0_row1_col3" class="data row1 col3" >425 vs 600</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row2" class="row_heading level0 row2" >2</th>
      <td id="T_27cf0_row2_col0" class="data row2 col0" >2 Setup</td>
      <td id="T_27cf0_row2_col1" class="data row2 col1" >PF net (in-sample) >= pf_min</td>
      <td id="T_27cf0_row2_col2" class="data row2 col2" >PASS</td>
      <td id="T_27cf0_row2_col3" class="data row2 col3" >1.764 vs 1.2</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row3" class="row_heading level0 row3" >3</th>
      <td id="T_27cf0_row3_col0" class="data row3 col0" >2 Setup</td>
      <td id="T_27cf0_row3_col1" class="data row3 col1" >t net (in-sample) >= min_t_net</td>
      <td id="T_27cf0_row3_col2" class="data row3 col2" >PASS</td>
      <td id="T_27cf0_row3_col3" class="data row3 col3" >3.99 vs 2.5</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row4" class="row_heading level0 row4" >4</th>
      <td id="T_27cf0_row4_col0" class="data row4 col0" >3 Time window</td>
      <td id="T_27cf0_row4_col1" class="data row4 col1" >plateau (3x3, PF >= pf_min, N >= n_min)</td>
      <td id="T_27cf0_row4_col2" class="data row4 col2" >FAIL</td>
      <td id="T_27cf0_row4_col3" class="data row4 col3" >center PF 1.76</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row5" class="row_heading level0 row5" >5</th>
      <td id="T_27cf0_row5_col0" class="data row5 col0" >3 Time window</td>
      <td id="T_27cf0_row5_col1" class="data row5 col1" >anti-cliff (3x3)</td>
      <td id="T_27cf0_row5_col2" class="data row5 col2" >PASS</td>
      <td id="T_27cf0_row5_col3" class="data row5 col3" >worst drop 26.1% vs 30%</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row6" class="row_heading level0 row6" >6</th>
      <td id="T_27cf0_row6_col0" class="data row6 col0" >3 Time window</td>
      <td id="T_27cf0_row6_col1" class="data row6 col1" >frozen cell not on grid edge</td>
      <td id="T_27cf0_row6_col2" class="data row6 col2" >PASS</td>
      <td id="T_27cf0_row6_col3" class="data row6 col3" ></td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row7" class="row_heading level0 row7" >7</th>
      <td id="T_27cf0_row7_col0" class="data row7 col0" >3 Time window</td>
      <td id="T_27cf0_row7_col1" class="data row7 col1" >majority of grid cells have mean net > 0</td>
      <td id="T_27cf0_row7_col2" class="data row7 col2" >PASS</td>
      <td id="T_27cf0_row7_col3" class="data row7 col3" >100% of cells</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row8" class="row_heading level0 row8" >8</th>
      <td id="T_27cf0_row8_col0" class="data row8 col0" >4 Costs</td>
      <td id="T_27cf0_row8_col1" class="data row8 col1" >breakeven multiple >= breakeven_mult_min</td>
      <td id="T_27cf0_row8_col2" class="data row8 col2" >PASS</td>
      <td id="T_27cf0_row8_col3" class="data row8 col3" >4.94x vs 2.0</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row9" class="row_heading level0 row9" >9</th>
      <td id="T_27cf0_row9_col0" class="data row9 col0" >4 Costs</td>
      <td id="T_27cf0_row9_col1" class="data row9 col1" >mean net > 0 at every YAML flat spread</td>
      <td id="T_27cf0_row9_col2" class="data row9 col2" >PASS</td>
      <td id="T_27cf0_row9_col3" class="data row9 col3" >worst +2.90 bps at 1 pips</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row10" class="row_heading level0 row10" >10</th>
      <td id="T_27cf0_row10_col0" class="data row10 col0" >5 Calendar</td>
      <td id="T_27cf0_row10_col1" class="data row10 col1" >leave-one-label-out: PF >= pf_min in every case</td>
      <td id="T_27cf0_row10_col2" class="data row10 col2" >PASS</td>
      <td id="T_27cf0_row10_col3" class="data row10 col3" >min PF 1.53 (without 20)</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row11" class="row_heading level0 row11" >11</th>
      <td id="T_27cf0_row11_col0" class="data row11 col0" >5 Calendar</td>
      <td id="T_27cf0_row11_col1" class="data row11 col1" >mean net > 0 in every Gotobi label</td>
      <td id="T_27cf0_row11_col2" class="data row11 col2" >FAIL</td>
      <td id="T_27cf0_row11_col3" class="data row11 col3" >5/6 labels positive</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row12" class="row_heading level0 row12" >12</th>
      <td id="T_27cf0_row12_col0" class="data row12 col0" >6 Execution</td>
      <td id="T_27cf0_row12_col1" class="data row12 col1" >signal loss of configured spread cap <= max_signal_loss</td>
      <td id="T_27cf0_row12_col2" class="data row12 col2" >PASS</td>
      <td id="T_27cf0_row12_col3" class="data row12 col3" >0.0%</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row13" class="row_heading level0 row13" >13</th>
      <td id="T_27cf0_row13_col0" class="data row13 col0" >7 Stability</td>
      <td id="T_27cf0_row13_col1" class="data row13 col1" >positive in-sample years >= years_pos_min</td>
      <td id="T_27cf0_row13_col2" class="data row13 col2" >PASS</td>
      <td id="T_27cf0_row13_col3" class="data row13 col3" >6/6 vs 4.5</td>
    </tr>
    <tr>
      <th id="T_27cf0_level0_row14" class="row_heading level0 row14" >14</th>
      <td id="T_27cf0_row14_col0" class="data row14 col0" >7 Stability</td>
      <td id="T_27cf0_row14_col1" class="data row14 col1" >every YAML period with data has mean net > 0</td>
      <td id="T_27cf0_row14_col2" class="data row14 col2" >PASS</td>
      <td id="T_27cf0_row14_col3" class="data row14 col3" >2017-2022: +3.0</td>
    </tr>
  </tbody>
</table>



    PASS 12 | FAIL 3 | SKIP 0


## 9. VERDICT AND HAND-OFF TO NOTEBOOK 03


```python
ready = cnt["FAIL"] == 0
print("=" * 80)
print("9. SUMMARY OF IN-SAMPLE SENSITIVITY")
print("=" * 80)
print(f"""
1. Time window: plateau {'YES' if pl['plateau'] else 'NO'}, worst neighbour drop {pl['worst_drop_pct']:.1f}% (max {MAX_DROP:g}%); {int((cells > 0).sum())}/{len(cells)} cells with mean net > 0; frozen cell ranks #{rank}.
2. Costs: breakeven {be_flat:.2f} flat pips / scale {be_scale:.2f} -> {be_mult:.2f}x the configured cost (min {ACC['breakeven_mult_min']}).
3. Calendar: weakest leave-one-label-out PF {loo['pf'].min():.2f} ({loo['pf'].idxmin()}); {int((anat['Gotobi label']['mean'] > 0).sum())}/{len(ORDER)} labels positive.
4. Execution: spread cap {cap_lbl(cap0)} discards {100 * signal_loss:.1f}% of the signals.
5. Stability: {n_pos}/{len(by_year)} positive years; rolling mean > 0 in {100 * (roll > 0).mean():.0f}% of windows.

Checks: PASS {cnt['PASS']} | FAIL {cnt['FAIL']} | SKIP {cnt['SKIP']}
Next step: {'proceed to 03_Gotobi_Robustness_Testing with the frozen rules.' if ready else 'at least one gate failed. Do NOT re-tune the window or the calendar on this result: document it and carry it to notebook 03 as a known weakness.'}
""")

save_json(cfg, "02_sensitivity.json", dict(
    window=dict(is_start=a.date(), is_end=b.date(), years=years_is),
    baseline_is=B, mean_cost_bps=base["cost_bps"].mean(), mean_gross_bps=base["pnl_gross_bps"].mean(),
    time_grid=dict(center=CENTER, rank_by_mean=rank, share_cells_positive=float((cells > 0).mean()),
                   **{k: v for k, v in pl.items() if k not in ("nb", "nn")}),
    costs=dict(breakeven_flat_pips=be_flat, breakeven_scale=be_scale, breakeven_mult=be_mult),
    calendar=dict(loo_min_pf=float(loo["pf"].min()), by_label_mean_bps=anat["Gotobi label"]["mean"].to_dict()),
    execution=dict(cap=cap0, signal_loss=signal_loss),
    stability=dict(years_positive=n_pos, years=len(by_year), worst_rolling_bps=float(roll.min())),
    checks=C.items, counts=cnt, ready_for_03=ready))
```

    ================================================================================
    9. SUMMARY OF IN-SAMPLE SENSITIVITY
    ================================================================================
    
    1. Time window: plateau NO, worst neighbour drop 26.1% (max 30%); 49/49 cells with mean net > 0; frozen cell ranks #6.
    2. Costs: breakeven 4.26 flat pips / scale 3.46 -> 4.94x the configured cost (min 2.0).
    3. Calendar: weakest leave-one-label-out PF 1.53 (without 20); 5/6 labels positive.
    4. Execution: spread cap no filter discards 0.0% of the signals.
    5. Stability: 6/6 positive years; rolling mean > 0 in 100% of windows.
    
    Checks: PASS 12 | FAIL 3 | SKIP 0
    Next step: at least one gate failed. Do NOT re-tune the window or the calendar on this result: document it and carry it to notebook 03 as a known weakness.
    
    Saved: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy/02_sensitivity.json





    PosixPath('/Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy/02_sensitivity.json')


