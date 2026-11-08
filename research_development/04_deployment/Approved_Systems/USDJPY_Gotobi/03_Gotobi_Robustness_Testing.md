# 3. GOTOBI EFFECT · ROBUSTNESS BATTERY & VALIDATION GATE

Robustness battery of the **USDJPY Gotobi** rule on M5 Axi bars (UTC), following the structure of notebook 03 of the Monday / RSI2 edges. The rules are the ones frozen in notebooks 01 and 02 (`variants/*.yaml`): **nothing is re-tuned here**.

### BATTERY
1. **Out-of-sample**: untouched data since `splits.oos_start` (gates: `n_oos_min`, `t_oos_min`, `alpha`, `pf_min`).
2. **Walk-forward** with fixed rules (3 y IS -> 1 y OOS).
3. **Statistical evidence (edge-specific)**: Bonferroni threshold, **placebo calendars** (dates shifted by k business days) and **permutation test** against random non-Gotobi days.
4. **Costs across periods**: the feed spread is a modelled constant before ~2020, so the historical net result is checked with flat spreads; breakeven multiple.
5. **Hard limit & sizing**: intrabar drawdown vs `risk.hard_limit`, maximum fraction, annual table.
6. **Block Monte Carlo** on the 5-minute MTM paths of every trade.
7. **Stress & tail**: costs x2, best years / best trades removed, season split, opt-in stop test.
8. **Edge decay**: rolling mean / PF, recent vs historical, z wear-and-tear protocol.
9. **PASS / FAIL registry** (`Checks`, same as notebook 02) and 10. **save** for notebook 04.


```python
VARIANT = "v1_axi_usdjpy"     # variants/<name>.yaml
MC_BLOCK = 5              # block length (trades) of the Monte Carlo
MC_MAX_BREACH = 0.05      # max simulated probability of touching the hard limit
STOPS_BPS = [0, 10, 20, 30, 50]   # opt-in stop levels for the tail test (the rule itself has no stop)
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
from variant_config import load_variant, save_json, load_json

importlib.reload(eng); importlib.reload(U)
variant_config.EDGE_DIR = EDGE_DIR

cfg = load_variant(VARIANT)
eng.set_engine_defaults(**cfg["engine_defaults"])
eng.apply_cfd_preset(cfg["account"]["cfd_preset"])          # contract size / min lot / lot step of the YAML preset
eng.set_engine_defaults(account_ccy=cfg["account"]["ccy"])
INS, RULE, COSTS, ACC, RISK = cfg["instrument"], cfg["rule"], cfg["costs"], cfg["acceptance"], cfg["risk"]
OOS_START, RUN_DIR = cfg["oos_start_ts"], cfg["run_dir"]
ET, XT = RULE["entry_time_jst"], RULE["exit_time_jst"]
MODE, SCALE = COSTS["cost_mode"], float(COSTS["spread_scale"])
FLAT = sorted({float(x) for x in np.atleast_1d(COSTS["robustness"]["flat_spread_pips"])})
PF_MIN = float(ACC["pf_min"])
ALPHA, T_OOS_MIN, N_OOS_MIN = float(ACC["alpha"]), float(ACC["t_oos_min"]), int(ACC["n_oos_min"])
DRAWS, SEED, ROLL = int(ACC["perm_draws"]), int(ACC["seed"]), int(ACC["roll_trades"])
HARD, FRAC = float(RISK["hard_limit"]), float(RISK["size_fraction"])
MIN_T = float(cfg["evidence_thresholds"]["min_t_net"])
K_HYP = int(cfg["evidence_thresholds"]["hypotheses_tested"])
PLACEBO = [int(k) for k in cfg["placebo_offsets_bdays"]]
share = lambda x: x / 100 if x > 1 else float(x)
C = U.Checks()

print(f"Variant {cfg['id']} | {INS['symbol']} ({INS['broker']}) | long {ET} -> {XT} JST | cost_mode={MODE}, spread_scale={SCALE:g}")
print(f"Risk: hard limit -{HARD:.0%}, nominal fraction {FRAC:.0%} | OOS from {OOS_START:%Y-%m-%d} | rules hash {variant_config.rules_hash(cfg)} | run folder {RUN_DIR}")

# ---- helpers (same as notebook 02) ----
def summ(t):
    s = eng.trade_stats(t)
    return dict(n=s["n"], pf=s["pf"], mean=s["mean_bps"], t=s["t"], win=100 * s["win_rate"])

def parts_table(parts):
    out = pd.DataFrame({k: summ(t) for k, t in parts.items()}).T.astype(float)
    out["se"] = [U.mean_se(t["pnl_bps"])[1] for t in parts.values()]
    return out

def bars(ax, tbl, title):
    x = np.arange(len(tbl))
    ax.bar(x, tbl["mean"], yerr=tbl["se"], width=0.6, ecolor=U.SUB, color=[U.GREEN if v > 0 else U.RED for v in tbl["mean"]])
    ax.axhline(0, color=U.SUB, lw=0.6)
    ax.set_xticks(x); ax.set_xticklabels([str(i) for i in tbl.index], color=U.SUB)
    for i, n in enumerate(tbl["n"]):
        ax.text(i, ax.get_ylim()[0], f"N={int(n)}", color=U.SUB, fontsize=8, ha="center", va="bottom")
    U.set_title(ax, title)

def heatmap(ax, g, title, center=0.0, fmt="{:.1f}"):
    v = g.to_numpy(float)
    span = np.nanmax(np.abs(v - center)) or 1.0
    ax.imshow(v, cmap="RdYlGn", vmin=center - span, vmax=center + span, aspect="auto")
    ax.set_xticks(range(g.shape[1])); ax.set_xticklabels(g.columns, rotation=30, ha="right", color=U.SUB)
    ax.set_yticks(range(g.shape[0])); ax.set_yticklabels(g.index, color=U.SUB)
    for (r, c), val in np.ndenumerate(v):
        ax.text(c, r, fmt.format(val), ha="center", va="center", fontsize=8, color="#15171c")
    U.set_title(ax, title)

def breakeven(tbl):
    z = U.interp_zero(tbl.index, tbl["mean"])
    return np.inf if np.isnan(z) and (tbl["mean"] > 0).all() else z
```

    Variant GOTOBI.usdjpy.cfd.v1 | USDJPY (Axi) | long 07:30 -> 09:55 JST | cost_mode=feed, spread_scale=0.7
    Risk: hard limit -9%, nominal fraction 250% | OOS from 2023-01-01 | rules hash 99a05a00 | run folder /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy


## 2. OUT-OF-SAMPLE PERFORMANCE

The engine has no warm-up, so the rules run once on the full history and trades are split by JST entry date (`oos_start` is a JST midnight: no position crosses it). Returns are mark-to-market per business day at the nominal fraction `risk.size_fraction`. Gates: `n_oos_min`, one-sided t and p (`t_oos_min`, `alpha`) and `pf_min`.


```python
df_raw = eng.load_data(start=INS["start"], end=INS.get("end"))
a, b = (df_raw.index[0] + eng.JST).normalize(), (df_raw.index[-1] + eng.JST).normalize()
trades = eng.run_gotobi_backtest(df_raw)
ret = eng.daily_returns(df_raw, trades, FRAC)
ent = pd.to_datetime(trades["entry_date"])
SPLIT = {"In-sample": (a, OOS_START - pd.Timedelta(days=1)), "Out-of-sample": (OOS_START, b), "Full": (a, b)}
sub = lambda t, lo, hi: t[(pd.to_datetime(t["entry_date"]) >= lo) & (pd.to_datetime(t["entry_date"]) <= hi)]

rows = {}
for k, (lo, hi) in SPLIT.items():
    r, yrs = ret.loc[lo:hi], (hi - lo).days / 365.25
    eq = (1 + r).cumprod()
    rows[k] = {**summ(sub(trades, lo, hi)), "ret_%": 100 * (eq.iloc[-1] - 1), "cagr_%": 100 * (eq.iloc[-1] ** (1 / yrs) - 1),
               "sharpe": r.mean() / r.std() * np.sqrt(252), "maxdd_close_%": 100 * U.drawdown(r).min()}
perf = pd.DataFrame(rows).T
t_is, t_oos = sub(trades, *SPLIT["In-sample"]), sub(trades, *SPLIT["Out-of-sample"])
S_is, S_oos, S_all = summ(t_is), summ(t_oos), summ(trades)
st_oos = eng.trade_stats(t_oos)

print("=" * 80)
print(f"PERFORMANCE · net of costs · return metrics at {FRAC:.0%} nominal fraction")
print("=" * 80)
display(perf.round(3))
print(f"Mean net IS {S_is['mean']:+.2f} bps -> OOS {S_oos['mean']:+.2f} bps (retention {S_oos['mean'] / S_is['mean']:.2f}) | OOS t {S_oos['t']:.2f}, one-sided p {st_oos['p_one']:.3f} | OOS N {S_oos['n']}")

fig, (ax1, ax2) = U.subplots(2, 1, figsize=(14, 6.5), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
ax1.plot(ret.index, (1 + ret).cumprod(), color=U.BLUE, lw=1.5, label=f"{FRAC:.0%} nominal fraction")
ax2.fill_between(ret.index, 100 * U.drawdown(ret), 0, color=U.RED, alpha=0.5)
ax2.axhline(-100 * HARD, color=U.ORANGE, ls="--", lw=1.2, label=f"hard limit -{HARD:.0%}")
for ax in (ax1, ax2):
    ax.axvline(OOS_START, color=U.ORANGE, ls="--", lw=1.2)
ax1.set_yscale("log"); ax2.set_ylabel("Daily-close DD %", color=U.SUB)
U.set_title(ax1, f"Equity curve (log) · dashed = OOS start {OOS_START:%Y-%m-%d}"); U.legend(ax1); U.legend(ax2, "lower left")
plt.tight_layout(); plt.show()

C("2 OOS", "N OOS >= n_oos_min", S_oos["n"] >= N_OOS_MIN, f"{S_oos['n']} vs {N_OOS_MIN}")
C("2 OOS", "t net OOS >= t_oos_min", S_oos["t"] >= T_OOS_MIN, f"{S_oos['t']:.2f} vs {T_OOS_MIN:g}")
C("2 OOS", "one-sided p OOS < alpha", st_oos["p_one"] < ALPHA, f"p {st_oos['p_one']:.3f} vs {ALPHA:g}")
C("2 OOS", "PF net OOS >= pf_min", S_oos["pf"] >= PF_MIN, f"{S_oos['pf']:.3f} vs {PF_MIN}")
```

    ================================================================================
    PERFORMANCE · net of costs · return metrics at 250% nominal fraction
    ================================================================================



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
      <th>ret_%</th>
      <th>cagr_%</th>
      <th>sharpe</th>
      <th>maxdd_close_%</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>In-sample</th>
      <td>425.0</td>
      <td>1.764</td>
      <td>3.019</td>
      <td>3.989</td>
      <td>60.000</td>
      <td>37.399</td>
      <td>5.444</td>
      <td>1.580</td>
      <td>-3.082</td>
    </tr>
    <tr>
      <th>Out-of-sample</th>
      <td>272.0</td>
      <td>1.271</td>
      <td>1.571</td>
      <td>1.444</td>
      <td>59.559</td>
      <td>10.941</td>
      <td>2.742</td>
      <td>0.721</td>
      <td>-4.226</td>
    </tr>
    <tr>
      <th>Full</th>
      <td>697.0</td>
      <td>1.525</td>
      <td>2.454</td>
      <td>3.913</td>
      <td>59.828</td>
      <td>52.432</td>
      <td>4.380</td>
      <td>1.216</td>
      <td>-4.226</td>
    </tr>
  </tbody>
</table>
</div>


    Mean net IS +3.02 bps -> OOS +1.57 bps (retention 0.52) | OOS t 1.44, one-sided p 0.074 | OOS N 272



    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_5_3.png)
    


       [PASS] N OOS >= n_oos_min  ->  272 vs 150
       [FAIL] t net OOS >= t_oos_min  ->  1.44 vs 1.645
       [FAIL] one-sided p OOS < alpha  ->  p 0.074 vs 0.05
       [PASS] PF net OOS >= pf_min  ->  1.271 vs 1.2





    'PASS'



## 3. WALK-FORWARD (FIXED RULES, 3 y IS -> 1 y OOS)

No refitting: each calendar year is compared with the annualised return of the three full years before it. Gates: efficiency (mean OOS / mean IS) >= 0.5, positive years >= `years_pos_min`, worst-year drawdown inside the hard limit.


```python
wf = eng.walk_forward_fixed(df_raw, rules={}, is_years=3, sizing=FRAC)
eff = wf["ret_oos"].mean() / wf["ret_is_annual"].mean() if wf["ret_is_annual"].mean() > 0 else np.nan
pos = float((wf["ret_oos"] > 0).mean())
worst = float(wf["mdd_oos"].min())
print(f"{len(wf)} folds | efficiency {eff:.2f} (>= 0.50) | positive years {100 * pos:.0f}% ({int((wf['ret_oos'] > 0).sum())}/{len(wf)}) | worst-year DD {100 * worst:.2f}% (limit -{HARD:.0%})")
display(wf.round(4))

fig, ax = U.subplots(figsize=(14, 4.5))
x, w = np.arange(len(wf)), 0.38
ax.bar(x - w / 2, 100 * wf["ret_is_annual"], w, color=U.BLUE, alpha=0.8, label="IS annualised (%)")
ax.bar(x + w / 2, 100 * wf["ret_oos"], w, color=[U.GREEN if r > 0 else U.RED for r in wf["ret_oos"]], label="OOS year (%)")
ax.axhline(0, color=U.SUB, lw=0.8); ax.set_xticks(x); ax.set_xticklabels(wf["year"], color=U.SUB)
U.set_title(ax, "Walk-forward by calendar year"); U.legend(ax)
plt.tight_layout(); plt.show()

C("3 Walk-forward", "efficiency >= 0.5", bool(np.isfinite(eff) and eff >= 0.5), f"{eff:.2f}")
C("3 Walk-forward", "positive OOS years >= years_pos_min", pos >= share(ACC["years_pos_min"]) if ACC["years_pos_min"] <= 1 else pos * len(wf) >= ACC["years_pos_min"], f"{100 * pos:.0f}%")
C("3 Walk-forward", "worst-year DD inside hard limit", worst >= -HARD, f"{100 * worst:.2f}%")
```

    7 folds | efficiency 0.87 (>= 0.50) | positive years 86% (6/7) | worst-year DD -4.23% (limit -9%)



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
      <th>year</th>
      <th>ret_is_annual</th>
      <th>ret_oos</th>
      <th>mdd_oos</th>
      <th>n_oos</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>2020</td>
      <td>0.0524</td>
      <td>0.0665</td>
      <td>-0.0308</td>
      <td>70</td>
    </tr>
    <tr>
      <th>1</th>
      <td>2021</td>
      <td>0.0432</td>
      <td>0.0464</td>
      <td>-0.0066</td>
      <td>71</td>
    </tr>
    <tr>
      <th>2</th>
      <td>2022</td>
      <td>0.0485</td>
      <td>0.0563</td>
      <td>-0.0152</td>
      <td>72</td>
    </tr>
    <tr>
      <th>3</th>
      <td>2023</td>
      <td>0.0564</td>
      <td>0.0411</td>
      <td>-0.0279</td>
      <td>71</td>
    </tr>
    <tr>
      <th>4</th>
      <td>2024</td>
      <td>0.0479</td>
      <td>0.0350</td>
      <td>-0.0423</td>
      <td>71</td>
    </tr>
    <tr>
      <th>5</th>
      <td>2025</td>
      <td>0.0441</td>
      <td>-0.0006</td>
      <td>-0.0351</td>
      <td>70</td>
    </tr>
    <tr>
      <th>6</th>
      <td>2026</td>
      <td>0.0250</td>
      <td>0.0303</td>
      <td>-0.0217</td>
      <td>60</td>
    </tr>
  </tbody>
</table>
</div>



    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_7_2.png)
    


       [PASS] efficiency >= 0.5  ->  0.87
       [PASS] positive OOS years >= years_pos_min  ->  86%
       [PASS] worst-year DD inside hard limit  ->  -4.23%





    'PASS'



## 4. STATISTICAL EVIDENCE: HOW LIKELY IS THIS TO BE CHANCE?

1. **Multiple-testing bar**: `hypothesis_threshold(k)` (Bonferroni, one-sided) with the `hypotheses_tested` of the YAML.
2. **Placebo calendars**: the same window and costs on the Gotobi calendar shifted by k business days. If the effect is real it lives on the true dates and fades on the shifted ones.
3. **Permutation test** (gross window return): Gotobi dates vs random draws of non-Gotobi business days; once with all of them, once excluding the neighbouring business days, and once on the OOS slice alone.


```python
t_bonf = eng.hypothesis_threshold(K_HYP)
print(f"Net t (full) {S_all['t']:.2f} | min_t_net {MIN_T:g} | Bonferroni threshold ({K_HYP} hypotheses) {t_bonf:.2f}")

plc = eng.placebo_table(df_raw, offsets=PLACEBO)
real, others = plc.loc[0], plc.drop(index=0)
fig, (ax1, ax2) = U.subplots(1, 2, figsize=(14, 4.2), grid=False)
for ax, col, name in ((ax1, "gross", "Gross"), (ax2, "net", "Net")):
    v, tt = plc[f"{col}_bps"], plc[f"{col}_t"]
    ax.bar([f"{k:+d}" for k in plc.index], v, color=[U.BLUE if k == 0 else U.SUB for k in plc.index], width=0.6)
    ax.axhline(0, color=U.SUB, lw=0.6)
    for i, (val, t_) in enumerate(zip(v, tt)):
        ax.text(i, val, f"t={t_:.1f}", color=U.TXT, fontsize=8, ha="center", va="bottom" if val >= 0 else "top")
    ax.set_xlabel("calendar shift (business days; 0 = real)", color=U.SUB); U.set_title(ax, f"{name} mean bps per trade")
plt.tight_layout(); plt.show()
display(plc.round(3))

df_oos = eng.split_df(df_raw, OOS_START)[1]
rds = {"Full · all controls": eng.random_date_test(df_raw, n_draws=DRAWS, seed=SEED),
       "Full · controls without neighbours": eng.random_date_test(df_raw, n_draws=DRAWS, seed=SEED, exclude_neighbors=1),
       "OOS only": eng.random_date_test(df_oos, n_draws=DRAWS, seed=SEED)}
fig, axes = U.subplots(1, 3, figsize=(17, 3.8))
for ax, (name, rd) in zip(axes, rds.items()):
    ax.hist(rd["sims"], bins=50, color=U.SUB, alpha=0.8)
    ax.axvline(rd["real_mean_bps"], color=U.GREEN, lw=2, label=f"real {rd['real_mean_bps']:+.2f} bps")
    ax.set_xlabel("mean gross bps of random dates", color=U.SUB); U.legend(ax, "upper left")
    U.set_title(ax, f"{name} · z {rd['z']:.1f} · p {rd['p_one']:.4f}")
plt.tight_layout(); plt.show()
display(pd.DataFrame({k: {m: v for m, v in rd.items() if m != "sims"} for k, rd in rds.items()}).T.round(4))

C("4 Evidence", "net t (full) >= min_t_net", S_all["t"] >= MIN_T, f"{S_all['t']:.2f} vs {MIN_T:g}")
C("4 Evidence", "net t (full) >= Bonferroni threshold", S_all["t"] >= t_bonf, f"{S_all['t']:.2f} vs {t_bonf:.2f}")
C("4 Evidence", "placebo: real gross bps > every shifted calendar", bool(real["gross_bps"] > others["gross_bps"].max()), f"{real['gross_bps']:+.2f} vs max {others['gross_bps'].max():+.2f}")
C("4 Evidence", "placebo: real net t > every shifted calendar", bool(real["net_t"] > others["net_t"].max()), f"{real['net_t']:.1f} vs max {others['net_t'].max():.1f}")
for name, rd in rds.items():
    C("4 Evidence", f"permutation p < alpha · {name}", rd["p_one"] < ALPHA, f"p {rd['p_one']:.4f}, z {rd['z']:.1f}")
```

    Net t (full) 3.91 | min_t_net 2.5 | Bonferroni threshold (17 hypotheses) 2.75



    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_9_1.png)
    



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
      <th>gross_bps</th>
      <th>gross_t</th>
      <th>net_bps</th>
      <th>net_t</th>
      <th>pf_net</th>
    </tr>
    <tr>
      <th>offset</th>
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
      <th>0</th>
      <td>697</td>
      <td>3.350</td>
      <td>5.335</td>
      <td>2.454</td>
      <td>3.913</td>
      <td>1.525</td>
    </tr>
    <tr>
      <th>-2</th>
      <td>703</td>
      <td>1.370</td>
      <td>2.218</td>
      <td>0.463</td>
      <td>0.754</td>
      <td>1.084</td>
    </tr>
    <tr>
      <th>-1</th>
      <td>704</td>
      <td>0.409</td>
      <td>0.727</td>
      <td>-0.463</td>
      <td>-0.820</td>
      <td>0.916</td>
    </tr>
    <tr>
      <th>1</th>
      <td>702</td>
      <td>1.828</td>
      <td>2.979</td>
      <td>0.912</td>
      <td>1.494</td>
      <td>1.171</td>
    </tr>
    <tr>
      <th>2</th>
      <td>703</td>
      <td>0.429</td>
      <td>0.759</td>
      <td>-0.463</td>
      <td>-0.818</td>
      <td>0.918</td>
    </tr>
  </tbody>
</table>
</div>



    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_9_3.png)
    



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
      <th>n_control</th>
      <th>real_mean_bps</th>
      <th>control_mean_bps</th>
      <th>sim_mean_bps</th>
      <th>sim_sd_bps</th>
      <th>z</th>
      <th>p_one</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>Full · all controls</th>
      <td>697.0</td>
      <td>1694.0</td>
      <td>3.3499</td>
      <td>0.9387</td>
      <td>0.9463</td>
      <td>0.4575</td>
      <td>5.2538</td>
      <td>0.0002</td>
    </tr>
    <tr>
      <th>Full · controls without neighbours</th>
      <td>697.0</td>
      <td>380.0</td>
      <td>3.3499</td>
      <td>1.0670</td>
      <td>1.0714</td>
      <td>0.5948</td>
      <td>3.8310</td>
      <td>0.0002</td>
    </tr>
    <tr>
      <th>OOS only</th>
      <td>272.0</td>
      <td>661.0</td>
      <td>2.6691</td>
      <td>0.7121</td>
      <td>0.6874</td>
      <td>0.8292</td>
      <td>2.3901</td>
      <td>0.0084</td>
    </tr>
  </tbody>
</table>
</div>


       [PASS] net t (full) >= min_t_net  ->  3.91 vs 2.5
       [PASS] net t (full) >= Bonferroni threshold  ->  3.91 vs 2.75
       [PASS] placebo: real gross bps > every shifted calendar  ->  +3.35 vs max +1.83
       [PASS] placebo: real net t > every shifted calendar  ->  3.9 vs max 1.5
       [PASS] permutation p < alpha · Full · all controls  ->  p 0.0002, z 5.3
       [PASS] permutation p < alpha · Full · controls without neighbours  ->  p 0.0002, z 3.8
       [PASS] permutation p < alpha · OOS only  ->  p 0.0084, z 2.4


## 5. COSTS ACROSS PERIODS

Until ~2020 the feed spread is a modelled constant, so `spread_scale` is not valid there and the historical net result is read with **flat spreads** (YAML `costs.robustness`). The heatmap shows mean net bps and t by period (YAML `periods`) and cost scenario; sweeps run without the spread filter to isolate the cost. Breakeven multiple = breakeven spread / configured cost.


```python
NOFILT = dict(max_entry_spread_pips=float("inf"))
SPREADS = sorted({0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0} | set(FLAT))
SCALES = sorted({0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0} | {SCALE, 2 * SCALE})
flat_tr = {}
for s in SPREADS:
    with U.engine_overrides(eng, flat_spread_pips=s):
        flat_tr[s] = eng.run_gotobi_backtest(df_raw, cost_mode="flat_pips", **NOFILT)
feed_tr = {k: eng.run_gotobi_backtest(df_raw, cost_mode="feed", spread_scale=k, **NOFILT) for k in SCALES}
flat_tbl, feed_tbl = parts_table(flat_tr), parts_table(feed_tr)
be_flat, be_scale = breakeven(flat_tbl), breakeven(feed_tbl)
be_mult = (be_scale / SCALE if MODE == "feed" else be_flat / float(eng.ENGINE_DEFAULTS["flat_spread_pips"]) if MODE == "flat_pips" else np.nan)

scen = {"configured": trades, f"feed x{SCALE:g}": feed_tr[SCALE], f"feed x{2 * SCALE:g}": feed_tr[2 * SCALE], **{f"flat {s:g}p": flat_tr[s] for s in FLAT}}
pst = {k: eng.period_stats(t, cfg["periods"]).astype(float) for k, t in scen.items()}
pm = pd.DataFrame({k: v["mean_bps"] for k, v in pst.items()})
pt = pd.DataFrame({k: v["t"] for k, v in pst.items()})
pn = pst["configured"]["n"]

fig, (ax1, ax2) = U.subplots(1, 2, figsize=(16, 4.4), grid=False)
heatmap(ax1, pm, "Mean net bps · period x cost scenario", 0.0)
heatmap(ax2, pt, "t-stat of the mean · period x cost scenario", 0.0)
plt.tight_layout(); plt.show()
print("N per period:", pn.astype(int).to_dict())
display(flat_tbl.round(3))
print(f"Breakeven: {be_flat:.2f} flat pips | spread_scale {be_scale:.2f} (configured {SCALE:g}) | multiple ({MODE}) {be_mult:.2f}x (min {ACC['breakeven_mult_min']})")

worst_flat = f"flat {max(FLAT):g}p"
C("5 Costs", "breakeven multiple >= breakeven_mult_min", None if np.isnan(be_mult) else be_mult >= float(ACC["breakeven_mult_min"]), f"{be_mult:.2f}x")
C("5 Costs", "mean net > 0 (full) at every YAML flat spread", bool((flat_tbl.loc[FLAT, "mean"] > 0).all()), f"worst {flat_tbl.loc[FLAT, 'mean'].min():+.2f} bps")
C("5 Costs", f"periods with mean net > 0 at {worst_flat} >= years_pos_min", float((pm[worst_flat] > 0).mean()) >= share(ACC["years_pos_min"]), f"{int((pm[worst_flat] > 0).sum())}/{len(pm)} periods")
```


    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_11_0.png)
    


    N per period: {'2017-2022': 425, '2023+': 272}



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
      <th>0.0</th>
      <td>697.0</td>
      <td>1.775</td>
      <td>3.350</td>
      <td>5.335</td>
      <td>61.549</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>0.5</th>
      <td>697.0</td>
      <td>1.658</td>
      <td>2.948</td>
      <td>4.696</td>
      <td>60.689</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>0.7</th>
      <td>697.0</td>
      <td>1.614</td>
      <td>2.788</td>
      <td>4.440</td>
      <td>60.402</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>1.0</th>
      <td>697.0</td>
      <td>1.549</td>
      <td>2.547</td>
      <td>4.057</td>
      <td>59.828</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>1.5</th>
      <td>697.0</td>
      <td>1.447</td>
      <td>2.145</td>
      <td>3.418</td>
      <td>58.824</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>2.0</th>
      <td>697.0</td>
      <td>1.351</td>
      <td>1.744</td>
      <td>2.778</td>
      <td>56.815</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>3.0</th>
      <td>697.0</td>
      <td>1.176</td>
      <td>0.941</td>
      <td>1.499</td>
      <td>52.511</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>4.0</th>
      <td>697.0</td>
      <td>1.024</td>
      <td>0.138</td>
      <td>0.220</td>
      <td>49.785</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>6.0</th>
      <td>697.0</td>
      <td>0.778</td>
      <td>-1.467</td>
      <td>-2.338</td>
      <td>43.042</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>8.0</th>
      <td>697.0</td>
      <td>0.594</td>
      <td>-3.072</td>
      <td>-4.895</td>
      <td>38.594</td>
      <td>0.628</td>
    </tr>
  </tbody>
</table>
</div>


    Breakeven: 4.17 flat pips | spread_scale 2.62 (configured 0.7) | multiple (feed) 3.74x (min 2.0)
       [PASS] breakeven multiple >= breakeven_mult_min  ->  3.74x
       [PASS] mean net > 0 (full) at every YAML flat spread  ->  worst +2.55 bps
       [PASS] periods with mean net > 0 at flat 1p >= years_pos_min  ->  2/2 periods





    'PASS'



## 6. HARD LIMIT AND SIZING

Long-only, no stop: **the position size is the only risk control**. Drawdown is measured on the equity of the 5-minute bars using each bar's low (intrabar). `max_fraction_for_limit` is the largest fixed nominal fraction (may exceed 100 % = leverage) whose *historical* drawdown still respects the hard limit; it is a ceiling, not a recommendation. This cell runs a bisection over the full M5 history and can take a minute.


```python
rep = eng.hard_limit_report_intrabar(df_raw, trades, HARD, FRAC)
fmax = eng.max_fraction_for_limit(df_raw, trades, HARD)
annual = eng.annual_returns(ret, trades, HARD)
U.plot_annual_returns(annual, rep, HARD)
display(annual.round(4))
print(f"Intrabar max DD {100 * rep['max_dd']:.2f}% (closes only {100 * rep['max_dd_close']:.2f}%) | limit -{HARD:.0%} | headroom {100 * rep['headroom']:.2f} pp | trough {rep['trough_date']}")
print(f"Max fraction for the limit: {fmax:.2f}x capital | configured {FRAC:.2f}x = {FRAC / fmax:.0%} of the ceiling | years in breach: {int(annual['breach'].sum())}")

C("6 Risk", "historical intrabar max DD inside hard limit", rep["passed"], f"{100 * rep['max_dd']:.2f}% vs -{HARD:.0%}")
C("6 Risk", "no calendar year breaches the hard limit", not bool(annual["breach"].any()), f"{int(annual['breach'].sum())} years")
C("6 Risk", "worst single trade at nominal size < hard limit", bool(trades["pnl_frac"].min() / 100 > -HARD), f"{trades['pnl_frac'].min():.2f}% (pnl_frac)")
```


    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_13_0.png)
    



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
      <th>year</th>
      <th>ret</th>
      <th>mdd</th>
      <th>n_trades</th>
      <th>partial</th>
      <th>breach</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>2017</td>
      <td>0.0948</td>
      <td>-0.0143</td>
      <td>71</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>1</th>
      <td>2018</td>
      <td>0.0307</td>
      <td>-0.0139</td>
      <td>71</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>2</th>
      <td>2019</td>
      <td>0.0329</td>
      <td>-0.0271</td>
      <td>70</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>3</th>
      <td>2020</td>
      <td>0.0665</td>
      <td>-0.0308</td>
      <td>70</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>4</th>
      <td>2021</td>
      <td>0.0464</td>
      <td>-0.0066</td>
      <td>71</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>5</th>
      <td>2022</td>
      <td>0.0563</td>
      <td>-0.0152</td>
      <td>72</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>6</th>
      <td>2023</td>
      <td>0.0411</td>
      <td>-0.0279</td>
      <td>71</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>7</th>
      <td>2024</td>
      <td>0.0350</td>
      <td>-0.0423</td>
      <td>71</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>8</th>
      <td>2025</td>
      <td>-0.0006</td>
      <td>-0.0351</td>
      <td>70</td>
      <td>False</td>
      <td>False</td>
    </tr>
    <tr>
      <th>9</th>
      <td>2026</td>
      <td>0.0303</td>
      <td>-0.0217</td>
      <td>60</td>
      <td>True</td>
      <td>False</td>
    </tr>
  </tbody>
</table>
</div>


    Intrabar max DD -5.19% (closes only -5.07%) | limit -9% | headroom 3.81 pp | trough 2024-09-04 23:35:00
    Max fraction for the limit: 4.37x capital | configured 2.50x = 57% of the ceiling | years in breach: 0
       [PASS] historical intrabar max DD inside hard limit  ->  -5.19% vs -9%
       [PASS] no calendar year breaches the hard limit  ->  0 years
       [PASS] worst single trade at nominal size < hard limit  ->  -1.93% (pnl_frac)





    'PASS'



## 7. BLOCK MONTE CARLO

Trades are resampled in circular blocks (streaks kept) and every simulated equity path is built from the **5-minute MTM path of each trade** (per trade: growth multiplier, best and worst point inside the trade), so the drawdown is intrabar. Run at the nominal fraction and at the ceiling of section 6, which by construction touches the limit in the real history. Gates: probability of touching the hard limit <= `MC_MAX_BREACH` and p5 of total return > 0.


```python
def trade_vectors(t, f):
    """Per trade: growth multiplier, highest and lowest equity multiplier inside the trade."""
    g, hi, lo = [], [], []
    for p in eng.trade_mtm_paths(df_raw, t, sizing=f):
        c = np.cumprod(1 + p)
        g.append(c[-1]); hi.append(c.max()); lo.append(c.min())
    return np.array(g), np.array(hi), np.array(lo)

def mc_core(vec, idx):
    """(total return, max intrabar drawdown) of each resampled sequence of trades (rows of idx)."""
    g, hi, lo = vec
    gs = g[idx]
    E = np.cumprod(gs, axis=1); prev = E / gs
    H = np.maximum(prev * hi[idx], E)
    peak = np.concatenate([np.ones((len(idx), 1)), np.maximum(1.0, np.maximum.accumulate(H, axis=1))[:, :-1]], axis=1)
    return E[:, -1] - 1, (prev * lo[idx] / np.maximum(peak, prev) - 1).min(axis=1)

def block_mc(vec, n_sim, block, seed):
    n = len(vec[0])
    rng = np.random.default_rng(seed)
    idx = ((rng.integers(0, n, (n_sim, -(-n // block)))[:, :, None] + np.arange(block)) % n).reshape(n_sim, -1)[:, :n]
    rets, mdds = mc_core(vec, idx)
    real_ret, real_mdd = (x[0] for x in mc_core(vec, np.arange(n)[None, :]))
    return dict(rets=rets, mdds=mdds, ret_p5=np.percentile(rets, 5), ret_p50=np.median(rets), mdd_p50=np.median(mdds),
                mdd_p5=np.percentile(mdds, 5), mdd_worst=mdds.min(), prob_breach=float((mdds <= -HARD).mean()),
                prob_pos=float((rets > 0).mean()), real_mdd=real_mdd, real_ret=real_ret)

MC_SIMS = min(DRAWS, 5000)
SIZES = {f"{FRAC:.2f}x (robot)": FRAC, f"{fmax:.2f}x (ceiling)": fmax}
OFFICIAL = next(iter(SIZES))
mcs = {k: block_mc(trade_vectors(trades, f), MC_SIMS, MC_BLOCK, SEED) for k, f in SIZES.items()}
mc_tbl = pd.DataFrame({k: {"Median return %": 100 * m["ret_p50"], "p5 return %": 100 * m["ret_p5"], "Median max DD %": 100 * m["mdd_p50"],
                           "Worst-5% DD %": 100 * m["mdd_p5"], "Worst simulated DD %": 100 * m["mdd_worst"],
                           f"P(DD beyond -{HARD:.0%}) %": 100 * m["prob_breach"], "P(return > 0) %": 100 * m["prob_pos"],
                           "Real-history DD %": 100 * m["real_mdd"]} for k, m in mcs.items()}).T
display(mc_tbl.round(2))

mc0 = mcs[OFFICIAL]
fig, (ax1, ax2) = U.subplots(1, 2, figsize=(14, 4.4))
ax1.hist(100 * mc0["rets"], bins=60, color=U.BLUE, alpha=0.8); ax1.axvline(0, color=U.RED, lw=1.2); ax1.axvline(100 * mc0["ret_p5"], color=U.ORANGE, ls="--", lw=1.2)
ax2.hist(100 * mc0["mdds"], bins=60, color=U.BLUE, alpha=0.8)
ax2.axvline(-100 * HARD, color=U.RED, lw=1.2, label="hard limit"); ax2.axvline(100 * mc0["mdd_p5"], color=U.ORANGE, ls="--", lw=1.2, label="worst 5%")
ax2.axvline(100 * mc0["real_mdd"], color=U.GREEN, ls=":", lw=1.4, label="real history"); U.legend(ax2, "upper left")
U.set_title(ax1, f"Simulated total return % · {OFFICIAL}"); U.set_title(ax2, "Simulated max intrabar drawdown %")
plt.tight_layout(); plt.show()

C("7 Monte Carlo", "P(touching hard limit) <= max (robot size)", mc0["prob_breach"] <= MC_MAX_BREACH, f"{100 * mc0['prob_breach']:.1f}% vs {100 * MC_MAX_BREACH:.0f}%")
C("7 Monte Carlo", "p5 of total return > 0 (robot size)", mc0["ret_p5"] > 0, f"{100 * mc0['ret_p5']:.1f}%")
```


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
      <th>Median return %</th>
      <th>p5 return %</th>
      <th>Median max DD %</th>
      <th>Worst-5% DD %</th>
      <th>Worst simulated DD %</th>
      <th>P(DD beyond -9%) %</th>
      <th>P(return &gt; 0) %</th>
      <th>Real-history DD %</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2.50x (robot)</th>
      <td>51.67</td>
      <td>26.30</td>
      <td>-5.32</td>
      <td>-8.64</td>
      <td>-16.84</td>
      <td>3.58</td>
      <td>99.98</td>
      <td>-5.07</td>
    </tr>
    <tr>
      <th>4.37x (ceiling)</th>
      <td>105.52</td>
      <td>49.23</td>
      <td>-9.18</td>
      <td>-14.73</td>
      <td>-27.87</td>
      <td>53.00</td>
      <td>99.98</td>
      <td>-8.80</td>
    </tr>
  </tbody>
</table>
</div>



    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_15_1.png)
    


       [PASS] P(touching hard limit) <= max (robot size)  ->  3.6% vs 5%
       [PASS] p5 of total return > 0 (robot size)  ->  26.3%





    'PASS'



## 8. STRESS AND TAIL TESTS

- **Stress table**: costs x2 (without the spread filter), best 2 years removed, best 10 % of trades removed (concentration), winter vs summer entries.
- **Tail / stop test**: the rule has **no stop**; here an opt-in stop (`stop_bps`, filled at min(level, bar open): M5 approximation) shows how much tail it cuts and what it costs. Left: distribution of net PnL; centre: MAE of every trade; right: mean net per stop level.


```python
if MODE == "feed":
    t_x2 = eng.run_gotobi_backtest(df_raw, spread_scale=2 * SCALE, **NOFILT)
elif MODE == "flat_pips":
    with U.engine_overrides(eng, flat_spread_pips=2 * eng.ENGINE_DEFAULTS["flat_spread_pips"]):
        t_x2 = eng.run_gotobi_backtest(df_raw, **NOFILT)
else:
    t_x2 = eng.run_gotobi_backtest(df_raw, cost_bps_per_side=2 * eng.ENGINE_DEFAULTS["cost_bps_per_side"], **NOFILT)
yr = pd.to_datetime(trades["entry_date"]).dt.year
top2 = trades.groupby(yr)["pnl_bps"].sum().nlargest(2).index.tolist()
k10 = max(1, int(np.ceil(0.10 * len(trades))))
srt = trades["pnl_bps"].sort_values(ascending=False)
share_top10 = float(srt.head(k10).sum() / trades.loc[trades["pnl_bps"] > 0, "pnl_bps"].sum())
winter = ~eng.us_dst_mask(pd.DatetimeIndex(trades["entry_time"]))
stress = parts_table({"Baseline": trades, "Costs x2 (no spread filter)": t_x2, f"Without best 2 years {top2}": trades[~yr.isin(top2)],
                      f"Without best 10% of trades ({k10})": trades.loc[srt.index[k10:]], "Winter entries": trades[winter], "Summer entries": trades[~winter]})
display(stress.round(3))
print(f"Best 10% of trades carry {100 * share_top10:.0f}% of gross profit.")

stop_tr = {("no stop" if s == 0 else f"stop {s} bps"): eng.run_gotobi_backtest(df_raw, stop_bps=float(s)) for s in STOPS_BPS}
stop_tbl = parts_table(stop_tr)
stop_tbl["stopped_%"] = [100 * t["stopped"].mean() for t in stop_tr.values()]
stop_tbl["p1_bps"] = [t["pnl_bps"].quantile(0.01) for t in stop_tr.values()]
stop_tbl["worst_bps"] = [t["pnl_bps"].min() for t in stop_tr.values()]
display(stop_tbl.round(3))

fig, axes = U.subplots(1, 3, figsize=(18, 4.2))
axes[0].hist(trades["pnl_bps"], bins=80, color=U.BLUE, alpha=0.85)
for q, col in ((0.01, U.RED), (0.05, U.ORANGE)):
    axes[0].axvline(trades["pnl_bps"].quantile(q), color=col, ls="--", lw=1.2, label=f"p{int(q * 100)} {trades['pnl_bps'].quantile(q):.1f}")
axes[0].axvline(0, color=U.SUB, lw=0.8); U.legend(axes[0], "upper left"); U.set_title(axes[0], "Net PnL per trade (bps)")
axes[1].hist(trades["mae_bps"], bins=80, color=U.SUB, alpha=0.85)
for s in STOPS_BPS[1:]:
    axes[1].axvline(-s, color=U.ORANGE, ls=":", lw=1)
U.set_title(axes[1], "MAE inside the trade (bps) · dotted = stop levels")
bars(axes[2], stop_tbl, "Mean net bps by stop level")
plt.tight_layout(); plt.show()

C("8 Stress", "costs x2: PF >= 1", stress.loc["Costs x2 (no spread filter)", "pf"] >= 1.0, f"PF {stress.loc['Costs x2 (no spread filter)', 'pf']:.3f}")
C("8 Stress", "without best 2 years: PF >= 1", stress.iloc[2]["pf"] >= 1.0, f"PF {stress.iloc[2]['pf']:.3f}")
C("8 Stress", "without best 10% of trades: mean net >= 0", stress.iloc[3]["mean"] >= 0, f"{stress.iloc[3]['mean']:+.2f} bps")
```


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
      <th>Baseline</th>
      <td>697.0</td>
      <td>1.525</td>
      <td>2.454</td>
      <td>3.913</td>
      <td>59.828</td>
      <td>0.627</td>
    </tr>
    <tr>
      <th>Costs x2 (no spread filter)</th>
      <td>697.0</td>
      <td>1.309</td>
      <td>1.558</td>
      <td>2.480</td>
      <td>57.102</td>
      <td>0.628</td>
    </tr>
    <tr>
      <th>Without best 2 years [2017, 2020]</th>
      <td>556.0</td>
      <td>1.404</td>
      <td>1.952</td>
      <td>2.889</td>
      <td>59.173</td>
      <td>0.675</td>
    </tr>
    <tr>
      <th>Without best 10% of trades (70)</th>
      <td>627.0</td>
      <td>0.826</td>
      <td>-0.905</td>
      <td>-1.751</td>
      <td>55.343</td>
      <td>0.517</td>
    </tr>
    <tr>
      <th>Winter entries</th>
      <td>232.0</td>
      <td>1.328</td>
      <td>1.611</td>
      <td>1.561</td>
      <td>58.621</td>
      <td>1.033</td>
    </tr>
    <tr>
      <th>Summer entries</th>
      <td>465.0</td>
      <td>1.631</td>
      <td>2.874</td>
      <td>3.655</td>
      <td>60.430</td>
      <td>0.786</td>
    </tr>
  </tbody>
</table>
</div>


    Best 10% of trades carry 46% of gross profit.



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
      <th>stopped_%</th>
      <th>p1_bps</th>
      <th>worst_bps</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>no stop</th>
      <td>697.0</td>
      <td>1.525</td>
      <td>2.454</td>
      <td>3.913</td>
      <td>59.828</td>
      <td>0.627</td>
      <td>0.000</td>
      <td>-39.736</td>
      <td>-77.056</td>
    </tr>
    <tr>
      <th>stop 10 bps</th>
      <td>697.0</td>
      <td>1.407</td>
      <td>1.772</td>
      <td>3.410</td>
      <td>49.067</td>
      <td>0.520</td>
      <td>39.598</td>
      <td>-10.000</td>
      <td>-10.036</td>
    </tr>
    <tr>
      <th>stop 20 bps</th>
      <td>697.0</td>
      <td>1.412</td>
      <td>1.999</td>
      <td>3.422</td>
      <td>57.819</td>
      <td>0.584</td>
      <td>16.356</td>
      <td>-20.000</td>
      <td>-20.000</td>
    </tr>
    <tr>
      <th>stop 30 bps</th>
      <td>697.0</td>
      <td>1.488</td>
      <td>2.335</td>
      <td>3.793</td>
      <td>59.541</td>
      <td>0.615</td>
      <td>6.600</td>
      <td>-30.000</td>
      <td>-30.000</td>
    </tr>
    <tr>
      <th>stop 50 bps</th>
      <td>697.0</td>
      <td>1.474</td>
      <td>2.290</td>
      <td>3.608</td>
      <td>59.828</td>
      <td>0.635</td>
      <td>1.578</td>
      <td>-50.000</td>
      <td>-50.000</td>
    </tr>
  </tbody>
</table>
</div>



    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_17_3.png)
    


       [PASS] costs x2: PF >= 1  ->  PF 1.309
       [PASS] without best 2 years: PF >= 1  ->  PF 1.404
       [FAIL] without best 10% of trades: mean net >= 0  ->  -0.91 bps





    'FAIL'



## 9. EDGE DECAY AND TEMPORAL STABILITY

Rolling mean and PF over `acceptance.roll_trades`, PF by year, recent (last 3 calendar years) vs historical mean, and the **z wear-and-tear protocol**: z = (mean of the last 20 trades - mu0) / (sigma0 / sqrt(20)) with mu0 / sigma0 from the in-sample trades; green > -1, yellow -1 to -2, red <= -2. Inside the IS block it shows how the protocol *would* have warned on the same data.


```python
pnl = trades.set_index(pd.to_datetime(trades["entry_date"]))["pnl_bps"]
roll_mean, roll_pf = pnl.rolling(ROLL).mean(), pnl.rolling(ROLL).apply(U.profit_factor, raw=True)
by_year = parts_table({int(y): g for y, g in trades.groupby(yr)})
last = int(yr.max())
recent, hist = trades[yr >= last - 2], trades[yr < last - 2]
ratio = recent["pnl_bps"].mean() / hist["pnl_bps"].mean() if hist["pnl_bps"].mean() > 0 else np.nan

W = 20
ref = pnl[pnl.index < OOS_START]
mu0, sd0 = float(ref.mean()), float(ref.std(ddof=1))
z = ((pnl.rolling(W).mean() - mu0) / (sd0 / np.sqrt(W))).dropna()
zone = pd.cut(z, [-np.inf, -2, -1, np.inf], labels=["red", "yellow", "green"])

fig, (ax1, ax2, ax3) = U.subplots(3, 1, figsize=(14, 10), sharex=True)
ax1.plot(roll_mean.index, roll_mean, color=U.GREEN, lw=1.5); ax1.axhline(0, color=U.RED, lw=1.0); ax1.axhline(pnl.mean(), color=U.SUB, ls=":")
ax2.plot(roll_pf.index, roll_pf.clip(upper=6), color=U.BLUE, lw=1.5); ax2.axhline(1, color=U.RED, lw=1.0); ax2.axhline(PF_MIN, color=U.ORANGE, ls="--", lw=1.0)
ax3.plot(z.index, z, color=U.TXT, lw=1.3)
lo_, hi_ = min(z.min() - 0.5, -2.5), max(z.max() + 0.5, 1.5)
ax3.axhspan(-1, hi_, color=U.GREEN, alpha=0.06); ax3.axhspan(-2, -1, color=U.ORANGE, alpha=0.10); ax3.axhspan(lo_, -2, color=U.RED, alpha=0.10); ax3.set_ylim(lo_, hi_)
for ax in (ax1, ax2, ax3):
    ax.axvline(OOS_START, color=U.SUB, ls=":")
U.set_title(ax1, f"Rolling mean net bps ({ROLL} trades)"); U.set_title(ax2, f"Rolling PF ({ROLL} trades, clipped at 6)"); U.set_title(ax3, f"z wear-and-tear protocol (last {W} trades)")
plt.tight_layout(); plt.show()

display(by_year.round(3))
print(f"Recent ({last - 2}-{last}) mean {recent['pnl_bps'].mean():+.2f} bps vs historical {hist['pnl_bps'].mean():+.2f} bps -> ratio {ratio:.2f}")
print(f"Reference (IS): mu0 {mu0:+.2f} bps, sigma0 {sd0:.2f} bps, n {len(ref)} | z today {z.iloc[-1]:+.2f} ({zone.iloc[-1]}) | min z {z.min():+.2f} on {z.idxmin():%Y-%m-%d}")
print("Trades since OOS start by zone:", zone[z.index >= OOS_START].value_counts().to_dict())

C("9 Decay", "recent 3 years / historical mean >= 0.5", bool(np.isfinite(ratio) and ratio >= 0.5), f"{ratio:.2f}")
C("9 Decay", "z today not red (> -2)", bool(z.iloc[-1] > -2), f"z {z.iloc[-1]:+.2f}")
C("9 Decay", "positive years >= years_pos_min (full history)", int((by_year["mean"] > 0).sum()) >= (ACC["years_pos_min"] if ACC["years_pos_min"] > 1 else ACC["years_pos_min"] * len(by_year)), f"{int((by_year['mean'] > 0).sum())}/{len(by_year)}")
```


    
![png](03_Gotobi_Robustness_Testing_files/03_Gotobi_Robustness_Testing_19_0.png)
    



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
    <tr>
      <th>2023</th>
      <td>71.0</td>
      <td>1.396</td>
      <td>2.311</td>
      <td>0.965</td>
      <td>63.380</td>
      <td>2.394</td>
    </tr>
    <tr>
      <th>2024</th>
      <td>71.0</td>
      <td>1.315</td>
      <td>2.002</td>
      <td>0.850</td>
      <td>63.380</td>
      <td>2.354</td>
    </tr>
    <tr>
      <th>2025</th>
      <td>70.0</td>
      <td>1.001</td>
      <td>0.005</td>
      <td>0.003</td>
      <td>55.714</td>
      <td>1.958</td>
    </tr>
    <tr>
      <th>2026</th>
      <td>60.0</td>
      <td>1.459</td>
      <td>2.011</td>
      <td>1.073</td>
      <td>55.000</td>
      <td>1.875</td>
    </tr>
  </tbody>
</table>
</div>


    Recent (2024-2026) mean +1.31 bps vs historical +2.92 bps -> ratio 0.45
    Reference (IS): mu0 +3.02 bps, sigma0 15.60 bps, n 425 | z today -0.27 (green) | min z -3.30 on 2024-10-18
    Trades since OOS start by zone: {'green': 213, 'yellow': 37, 'red': 22}
       [FAIL] recent 3 years / historical mean >= 0.5  ->  0.45
       [PASS] z today not red (> -2)  ->  z -0.27
       [PASS] positive years >= years_pos_min (full history)  ->  10/10





    'PASS'



## 10. PASS / FAIL SUMMARY, VERDICT AND SAVE

Weaknesses that notebook 02 carried over (failed in-sample checks) are listed next to the verdict: a gate that failed there must be declared here, not silently ignored.


```python
chk = C.frame()
display(chk.style.map(lambda s: {"PASS": "color:#34d399", "FAIL": "color:#f0555a", "SKIP": "color:#f5a524"}.get(s, ""), subset=["status"]))
cnt = C.counts()
try:
    s02 = load_json(cfg, "02_sensitivity.json")
    weak02 = [c["name"] for c in s02["checks"] if c["status"] == "FAIL"]
except FileNotFoundError:
    s02, weak02 = None, []
ready = cnt["FAIL"] == 0
failed = chk.loc[chk["status"] == "FAIL", "name"].tolist()

print("=" * 80)
print("VERDICT")
print("=" * 80)
print(f"PASS {cnt['PASS']} | FAIL {cnt['FAIL']} | SKIP {cnt['SKIP']}")
print(f"Notebook 02 weaknesses carried over: {weak02 if s02 else 'notebook 02 results not found'}")
print(f"Net {S_all['mean']:+.2f} bps/trade (t {S_all['t']:.1f}) | OOS {S_oos['mean']:+.2f} bps (t {S_oos['t']:.1f}, N {S_oos['n']}) | hard-limit DD {100 * rep['max_dd']:.2f}% at {FRAC:.2f}x (ceiling {fmax:.2f}x) | breakeven {be_mult:.2f}x cost | z {z.iloc[-1]:+.2f}")
print("OVERALL: " + ("PASS. Edge confirmed for the reconciliation stage (notebook 04)." if ready else f"FAIL on {failed}. Do not promote without documenting the failed checks (a margin or an exception must be declared, not silently applied)."))

save_json(cfg, "03_validation.json", dict(
    oos_start=OOS_START.date(), sizing=dict(fraction=FRAC, max_fraction=fmax, hard_limit=HARD),
    performance=perf.to_dict("index"), oos=dict(**S_oos, p_one=st_oos["p_one"]),
    walk_forward=dict(efficiency=eff, pct_positive=pos, worst_mdd=worst, folds=len(wf)),
    evidence=dict(t_bonferroni=t_bonf, placebo=plc.to_dict("index"), permutation={k: {m: v for m, v in rd.items() if m != "sims"} for k, rd in rds.items()}),
    costs=dict(breakeven_flat_pips=be_flat, breakeven_scale=be_scale, breakeven_mult=be_mult, mean_net_by_period=pm.to_dict("index")),
    risk=dict(max_dd=rep["max_dd"], max_dd_close=rep["max_dd_close"], passed=rep["passed"], trough_date=rep["trough_date"], years_in_breach=int(annual["breach"].sum())),
    monte_carlo={k: {m: v for m, v in mc.items() if m not in ("rets", "mdds")} for k, mc in mcs.items()},
    stress=stress.to_dict("index"), decay=dict(recent_ratio=ratio, z_today=float(z.iloc[-1]), mu0=mu0, sd0=sd0),
    carried_from_02=weak02, checks=C.items, counts=cnt, ready_for_04=ready))
```


<style type="text/css">
#T_d6f03_row0_col2, #T_d6f03_row3_col2, #T_d6f03_row4_col2, #T_d6f03_row5_col2, #T_d6f03_row6_col2, #T_d6f03_row7_col2, #T_d6f03_row8_col2, #T_d6f03_row9_col2, #T_d6f03_row10_col2, #T_d6f03_row11_col2, #T_d6f03_row12_col2, #T_d6f03_row13_col2, #T_d6f03_row14_col2, #T_d6f03_row15_col2, #T_d6f03_row16_col2, #T_d6f03_row17_col2, #T_d6f03_row18_col2, #T_d6f03_row19_col2, #T_d6f03_row20_col2, #T_d6f03_row21_col2, #T_d6f03_row22_col2, #T_d6f03_row23_col2, #T_d6f03_row26_col2, #T_d6f03_row27_col2 {
  color: #34d399;
}
#T_d6f03_row1_col2, #T_d6f03_row2_col2, #T_d6f03_row24_col2, #T_d6f03_row25_col2 {
  color: #f0555a;
}
</style>
<table id="T_d6f03">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_d6f03_level0_col0" class="col_heading level0 col0" >section</th>
      <th id="T_d6f03_level0_col1" class="col_heading level0 col1" >name</th>
      <th id="T_d6f03_level0_col2" class="col_heading level0 col2" >status</th>
      <th id="T_d6f03_level0_col3" class="col_heading level0 col3" >detail</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_d6f03_level0_row0" class="row_heading level0 row0" >0</th>
      <td id="T_d6f03_row0_col0" class="data row0 col0" >2 OOS</td>
      <td id="T_d6f03_row0_col1" class="data row0 col1" >N OOS >= n_oos_min</td>
      <td id="T_d6f03_row0_col2" class="data row0 col2" >PASS</td>
      <td id="T_d6f03_row0_col3" class="data row0 col3" >272 vs 150</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row1" class="row_heading level0 row1" >1</th>
      <td id="T_d6f03_row1_col0" class="data row1 col0" >2 OOS</td>
      <td id="T_d6f03_row1_col1" class="data row1 col1" >t net OOS >= t_oos_min</td>
      <td id="T_d6f03_row1_col2" class="data row1 col2" >FAIL</td>
      <td id="T_d6f03_row1_col3" class="data row1 col3" >1.44 vs 1.645</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row2" class="row_heading level0 row2" >2</th>
      <td id="T_d6f03_row2_col0" class="data row2 col0" >2 OOS</td>
      <td id="T_d6f03_row2_col1" class="data row2 col1" >one-sided p OOS < alpha</td>
      <td id="T_d6f03_row2_col2" class="data row2 col2" >FAIL</td>
      <td id="T_d6f03_row2_col3" class="data row2 col3" >p 0.074 vs 0.05</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row3" class="row_heading level0 row3" >3</th>
      <td id="T_d6f03_row3_col0" class="data row3 col0" >2 OOS</td>
      <td id="T_d6f03_row3_col1" class="data row3 col1" >PF net OOS >= pf_min</td>
      <td id="T_d6f03_row3_col2" class="data row3 col2" >PASS</td>
      <td id="T_d6f03_row3_col3" class="data row3 col3" >1.271 vs 1.2</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row4" class="row_heading level0 row4" >4</th>
      <td id="T_d6f03_row4_col0" class="data row4 col0" >3 Walk-forward</td>
      <td id="T_d6f03_row4_col1" class="data row4 col1" >efficiency >= 0.5</td>
      <td id="T_d6f03_row4_col2" class="data row4 col2" >PASS</td>
      <td id="T_d6f03_row4_col3" class="data row4 col3" >0.87</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row5" class="row_heading level0 row5" >5</th>
      <td id="T_d6f03_row5_col0" class="data row5 col0" >3 Walk-forward</td>
      <td id="T_d6f03_row5_col1" class="data row5 col1" >positive OOS years >= years_pos_min</td>
      <td id="T_d6f03_row5_col2" class="data row5 col2" >PASS</td>
      <td id="T_d6f03_row5_col3" class="data row5 col3" >86%</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row6" class="row_heading level0 row6" >6</th>
      <td id="T_d6f03_row6_col0" class="data row6 col0" >3 Walk-forward</td>
      <td id="T_d6f03_row6_col1" class="data row6 col1" >worst-year DD inside hard limit</td>
      <td id="T_d6f03_row6_col2" class="data row6 col2" >PASS</td>
      <td id="T_d6f03_row6_col3" class="data row6 col3" >-4.23%</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row7" class="row_heading level0 row7" >7</th>
      <td id="T_d6f03_row7_col0" class="data row7 col0" >4 Evidence</td>
      <td id="T_d6f03_row7_col1" class="data row7 col1" >net t (full) >= min_t_net</td>
      <td id="T_d6f03_row7_col2" class="data row7 col2" >PASS</td>
      <td id="T_d6f03_row7_col3" class="data row7 col3" >3.91 vs 2.5</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row8" class="row_heading level0 row8" >8</th>
      <td id="T_d6f03_row8_col0" class="data row8 col0" >4 Evidence</td>
      <td id="T_d6f03_row8_col1" class="data row8 col1" >net t (full) >= Bonferroni threshold</td>
      <td id="T_d6f03_row8_col2" class="data row8 col2" >PASS</td>
      <td id="T_d6f03_row8_col3" class="data row8 col3" >3.91 vs 2.75</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row9" class="row_heading level0 row9" >9</th>
      <td id="T_d6f03_row9_col0" class="data row9 col0" >4 Evidence</td>
      <td id="T_d6f03_row9_col1" class="data row9 col1" >placebo: real gross bps > every shifted calendar</td>
      <td id="T_d6f03_row9_col2" class="data row9 col2" >PASS</td>
      <td id="T_d6f03_row9_col3" class="data row9 col3" >+3.35 vs max +1.83</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row10" class="row_heading level0 row10" >10</th>
      <td id="T_d6f03_row10_col0" class="data row10 col0" >4 Evidence</td>
      <td id="T_d6f03_row10_col1" class="data row10 col1" >placebo: real net t > every shifted calendar</td>
      <td id="T_d6f03_row10_col2" class="data row10 col2" >PASS</td>
      <td id="T_d6f03_row10_col3" class="data row10 col3" >3.9 vs max 1.5</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row11" class="row_heading level0 row11" >11</th>
      <td id="T_d6f03_row11_col0" class="data row11 col0" >4 Evidence</td>
      <td id="T_d6f03_row11_col1" class="data row11 col1" >permutation p < alpha · Full · all controls</td>
      <td id="T_d6f03_row11_col2" class="data row11 col2" >PASS</td>
      <td id="T_d6f03_row11_col3" class="data row11 col3" >p 0.0002, z 5.3</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row12" class="row_heading level0 row12" >12</th>
      <td id="T_d6f03_row12_col0" class="data row12 col0" >4 Evidence</td>
      <td id="T_d6f03_row12_col1" class="data row12 col1" >permutation p < alpha · Full · controls without neighbours</td>
      <td id="T_d6f03_row12_col2" class="data row12 col2" >PASS</td>
      <td id="T_d6f03_row12_col3" class="data row12 col3" >p 0.0002, z 3.8</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row13" class="row_heading level0 row13" >13</th>
      <td id="T_d6f03_row13_col0" class="data row13 col0" >4 Evidence</td>
      <td id="T_d6f03_row13_col1" class="data row13 col1" >permutation p < alpha · OOS only</td>
      <td id="T_d6f03_row13_col2" class="data row13 col2" >PASS</td>
      <td id="T_d6f03_row13_col3" class="data row13 col3" >p 0.0084, z 2.4</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row14" class="row_heading level0 row14" >14</th>
      <td id="T_d6f03_row14_col0" class="data row14 col0" >5 Costs</td>
      <td id="T_d6f03_row14_col1" class="data row14 col1" >breakeven multiple >= breakeven_mult_min</td>
      <td id="T_d6f03_row14_col2" class="data row14 col2" >PASS</td>
      <td id="T_d6f03_row14_col3" class="data row14 col3" >3.74x</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row15" class="row_heading level0 row15" >15</th>
      <td id="T_d6f03_row15_col0" class="data row15 col0" >5 Costs</td>
      <td id="T_d6f03_row15_col1" class="data row15 col1" >mean net > 0 (full) at every YAML flat spread</td>
      <td id="T_d6f03_row15_col2" class="data row15 col2" >PASS</td>
      <td id="T_d6f03_row15_col3" class="data row15 col3" >worst +2.55 bps</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row16" class="row_heading level0 row16" >16</th>
      <td id="T_d6f03_row16_col0" class="data row16 col0" >5 Costs</td>
      <td id="T_d6f03_row16_col1" class="data row16 col1" >periods with mean net > 0 at flat 1p >= years_pos_min</td>
      <td id="T_d6f03_row16_col2" class="data row16 col2" >PASS</td>
      <td id="T_d6f03_row16_col3" class="data row16 col3" >2/2 periods</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row17" class="row_heading level0 row17" >17</th>
      <td id="T_d6f03_row17_col0" class="data row17 col0" >6 Risk</td>
      <td id="T_d6f03_row17_col1" class="data row17 col1" >historical intrabar max DD inside hard limit</td>
      <td id="T_d6f03_row17_col2" class="data row17 col2" >PASS</td>
      <td id="T_d6f03_row17_col3" class="data row17 col3" >-5.19% vs -9%</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row18" class="row_heading level0 row18" >18</th>
      <td id="T_d6f03_row18_col0" class="data row18 col0" >6 Risk</td>
      <td id="T_d6f03_row18_col1" class="data row18 col1" >no calendar year breaches the hard limit</td>
      <td id="T_d6f03_row18_col2" class="data row18 col2" >PASS</td>
      <td id="T_d6f03_row18_col3" class="data row18 col3" >0 years</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row19" class="row_heading level0 row19" >19</th>
      <td id="T_d6f03_row19_col0" class="data row19 col0" >6 Risk</td>
      <td id="T_d6f03_row19_col1" class="data row19 col1" >worst single trade at nominal size < hard limit</td>
      <td id="T_d6f03_row19_col2" class="data row19 col2" >PASS</td>
      <td id="T_d6f03_row19_col3" class="data row19 col3" >-1.93% (pnl_frac)</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row20" class="row_heading level0 row20" >20</th>
      <td id="T_d6f03_row20_col0" class="data row20 col0" >7 Monte Carlo</td>
      <td id="T_d6f03_row20_col1" class="data row20 col1" >P(touching hard limit) <= max (robot size)</td>
      <td id="T_d6f03_row20_col2" class="data row20 col2" >PASS</td>
      <td id="T_d6f03_row20_col3" class="data row20 col3" >3.6% vs 5%</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row21" class="row_heading level0 row21" >21</th>
      <td id="T_d6f03_row21_col0" class="data row21 col0" >7 Monte Carlo</td>
      <td id="T_d6f03_row21_col1" class="data row21 col1" >p5 of total return > 0 (robot size)</td>
      <td id="T_d6f03_row21_col2" class="data row21 col2" >PASS</td>
      <td id="T_d6f03_row21_col3" class="data row21 col3" >26.3%</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row22" class="row_heading level0 row22" >22</th>
      <td id="T_d6f03_row22_col0" class="data row22 col0" >8 Stress</td>
      <td id="T_d6f03_row22_col1" class="data row22 col1" >costs x2: PF >= 1</td>
      <td id="T_d6f03_row22_col2" class="data row22 col2" >PASS</td>
      <td id="T_d6f03_row22_col3" class="data row22 col3" >PF 1.309</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row23" class="row_heading level0 row23" >23</th>
      <td id="T_d6f03_row23_col0" class="data row23 col0" >8 Stress</td>
      <td id="T_d6f03_row23_col1" class="data row23 col1" >without best 2 years: PF >= 1</td>
      <td id="T_d6f03_row23_col2" class="data row23 col2" >PASS</td>
      <td id="T_d6f03_row23_col3" class="data row23 col3" >PF 1.404</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row24" class="row_heading level0 row24" >24</th>
      <td id="T_d6f03_row24_col0" class="data row24 col0" >8 Stress</td>
      <td id="T_d6f03_row24_col1" class="data row24 col1" >without best 10% of trades: mean net >= 0</td>
      <td id="T_d6f03_row24_col2" class="data row24 col2" >FAIL</td>
      <td id="T_d6f03_row24_col3" class="data row24 col3" >-0.91 bps</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row25" class="row_heading level0 row25" >25</th>
      <td id="T_d6f03_row25_col0" class="data row25 col0" >9 Decay</td>
      <td id="T_d6f03_row25_col1" class="data row25 col1" >recent 3 years / historical mean >= 0.5</td>
      <td id="T_d6f03_row25_col2" class="data row25 col2" >FAIL</td>
      <td id="T_d6f03_row25_col3" class="data row25 col3" >0.45</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row26" class="row_heading level0 row26" >26</th>
      <td id="T_d6f03_row26_col0" class="data row26 col0" >9 Decay</td>
      <td id="T_d6f03_row26_col1" class="data row26 col1" >z today not red (> -2)</td>
      <td id="T_d6f03_row26_col2" class="data row26 col2" >PASS</td>
      <td id="T_d6f03_row26_col3" class="data row26 col3" >z -0.27</td>
    </tr>
    <tr>
      <th id="T_d6f03_level0_row27" class="row_heading level0 row27" >27</th>
      <td id="T_d6f03_row27_col0" class="data row27 col0" >9 Decay</td>
      <td id="T_d6f03_row27_col1" class="data row27 col1" >positive years >= years_pos_min (full history)</td>
      <td id="T_d6f03_row27_col2" class="data row27 col2" >PASS</td>
      <td id="T_d6f03_row27_col3" class="data row27 col3" >10/10</td>
    </tr>
  </tbody>
</table>



    ================================================================================
    VERDICT
    ================================================================================
    PASS 24 | FAIL 4 | SKIP 0
    Notebook 02 weaknesses carried over: ['N in-sample >= n_min', 'plateau (3x3, PF >= pf_min, N >= n_min)', 'mean net > 0 in every Gotobi label']
    Net +2.45 bps/trade (t 3.9) | OOS +1.57 bps (t 1.4, N 272) | hard-limit DD -5.19% at 2.50x (ceiling 4.37x) | breakeven 3.74x cost | z -0.27
    OVERALL: FAIL on ['t net OOS >= t_oos_min', 'one-sided p OOS < alpha', 'without best 10% of trades: mean net >= 0', 'recent 3 years / historical mean >= 0.5']. Do not promote without documenting the failed checks (a margin or an exception must be declared, not silently applied).
    Saved: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy/03_validation.json





    PosixPath('/Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy/03_validation.json')


