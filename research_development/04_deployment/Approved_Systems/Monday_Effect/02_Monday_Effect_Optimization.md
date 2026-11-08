# 2. BTC MONDAY EFFECT - IN-SAMPLE PARAMETER STABILITY & PLATEAU CHECK

This notebook runs the in-sample sensitivity analysis of the **BTC Monday Effect (v3)** rules on hourly Axi BTC-JPY CFD bars (UTC), following the same flow as notebook 02 of the RSI2 edge.

### STRICT METHODOLOGICAL CONSTRAINT
> **IN-SAMPLE DATA ONLY**: everything before `split.oos_start` (2024-01-08). Out-of-sample data is not touched here; it belongs to notebook 03.

### OBJECTIVES
1. **Plateau vs. Cliff Validation**: the configured point (`atr_pctl`, `atr_len`) must sit on a stable region of the grid `grid.atr_pctl_values x grid.atr_len_values`, not on an isolated peak.
2. **Anti-Cliff Check**: one step away in any direction must not drop the Profit Factor by more than the gate limit.

### EDGE-SPECIFIC CHECKS (they matter more than the generic ones)
3. **Dose-response**: more volatility filter (higher percentile) should mean a higher net mean per Monday, not a random profile.
4. **Entry-hour robustness**: the rule should not depend on the exact 00:00 UTC entry.
5. **Filter ablation by era**: what each filter (volatility, calendar) contributes, in the eras that fall inside the in-sample block (on Axi data: the institutional era from 2022-12 onwards).

### STRATEGY PARAMETERS


```python
VARIANT = "v1_btcjpy"  # only base variants here; see variants/*.yaml
SCALE_SAMPLE_GATES = True   # short history (Axi): scale validation_gate plateau_n_min to the in-sample length (printed in section 2)
```

## 1. IMPORTS AND CONFIG


```python
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
from robustness import grid_search, plateau_check, plot_grid, profit_factor
from validation_gate import DEFAULTS as GATE
import monday_effect_engine as eng
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
VOL_MODE, ATR_PCTL, ATR_LEN = P["vol_mode"], float(P["atr_pctl"]), int(P["atr_len"])
SKIP1, ENTRY_HOUR, HOLD, COST_BPS = P["skip_first_monday"], P["entry_hour"], P["hold_bars"], P["cost_bps_per_side"]
PCTLS      = [float(x) for x in cfg["grid"]["atr_pctl_values"]]
ATR_LENS   = [int(x) for x in cfg["grid"]["atr_len_values"]]
CHOSEN     = (ATR_PCTL, ATR_LEN)

# Rules that never change in this notebook (atr_pctl / atr_len are swept)
RULES_KW = dict(vol_mode=VOL_MODE, skip_first_monday=SKIP1, entry_hour=ENTRY_HOUR,
                hold_bars=HOLD, cost_bps_per_side=COST_BPS)

# ---- Style and small helpers (same palette as notebook 01) ----
BG, PANEL, GRIDC, TXT, SUB, GREEN, RED, ORANGE = "#15171c", "#1b1e26", "#2a2d37", "#e8e9ec", "#9aa0ab", "#34d399", "#f0555a", "#f5a524"
def dark_ax(ax):
    ax.set_facecolor(PANEL)
    ax.grid(color=GRIDC, alpha=0.8)
    ax.tick_params(colors=SUB)
    for s in ax.spines.values():
        s.set_visible(False)

ERAS = {"Retail (2017-19)": (2017, 2019), "Institutional (2020-23)": (2020, 2023), "ETF (2024+)": (2024, 2100)}
def era_of(y):
    return next(k for k, (a, b) in ERAS.items() if a <= y <= b)

def tstat(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan

def summarize(t):
    """PF / mean net % / t-stat / win rate of a trades frame (100% capital, net of costs)."""
    if len(t) == 0:
        return dict(n=0, pf=np.nan, mean=np.nan, t=np.nan, win=np.nan)
    return dict(n=len(t), pf=profit_factor(t["pnl"]), mean=float(t["pnl"].mean()),
                t=tstat(t["pnl"]), win=float((t["pnl"] > 0).mean() * 100))

print("Imports complete.")
print(f"Loaded monday_effect_engine from: {eng.__file__}")
print(f"Edge dir: {EDGE_DIR}")
print(f"Variant: {cfg['id']} | {TICKER} | candidate P{ATR_PCTL:g}, ATR({ATR_LEN}) | skip first Monday={SKIP1} | {COST_BPS:g} bps/side")
print(f"Grid: {len(PCTLS)} percentiles x {len(ATR_LENS)} ATR lengths = {len(PCTLS) * len(ATR_LENS)} cells")
print(f"Gate criteria (validation_gate.DEFAULTS): PF >= {GATE['plateau_pf_min']}, N >= {GATE['plateau_n_min']}, max drop {GATE['plateau_max_drop']}%")
print(f"Run folder: {RUN_DIR}")
```

    Imports complete.
    Loaded monday_effect_engine from: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Monday_Effect/monday_effect_engine.py
    Edge dir: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Monday_Effect
    Variant: MONDAY.btcjpy.cfd.v1 | btcjpy | candidate P40, ATR(24) | skip first Monday=True | 5.5 bps/side
    Grid: 7 percentiles x 10 ATR lengths = 70 cells
    Gate criteria (validation_gate.DEFAULTS): PF >= 1.3, N >= 5, max drop 30%
    Run folder: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Monday_Effect/runs/v1_btcjpy


## 2. IN-SAMPLE DATA SETUP

`prepare()` is called once per ATR length on the full history (so the 1-year percentile is warm), then every grid cell is cut to the **same** window: from the first Monday where *all* ATR lengths have a valid percentile, up to the day before `oos_start`.


```python
df_raw = eng.load_data(TICKER, start=DATA_START)

preps = {L: eng.prepare(df_raw, atr_len=L, entry_hour=ENTRY_HOUR) for L in ATR_LENS}
common_start = max(d.index[d["atr_rank"].notna()][0] for d in preps.values())

is_dfs = {}
for L, d in preps.items():
    d = d[d.index >= common_start]
    is_dfs[L] = d[d.index < OOS_START].copy()

assert len({(d.index[0], d.index[-1], len(d)) for d in is_dfs.values()}) == 1, "All ATR lengths must use the same date window."
assert len(is_dfs[ATR_LEN]) > 0, "Check split.oos_start against the history."
d0 = is_dfs[ATR_LEN]

# ---- Short in-sample (Axi H1 starts in 2022-06): scale the sample-size gate, loudly ----
# GATE is validation_gate.DEFAULTS itself (same dict): the change applies to this kernel only.
GATE_ORIG = dict(GATE)
_is_years = (d0.index[-1] - d0.index[0]).days / 365.25
BASE_IS_YEARS = 6.5   # years of in-sample behind validation_gate.DEFAULTS (Binance 2017-05 .. 2023-12)
if SCALE_SAMPLE_GATES and _is_years < BASE_IS_YEARS:
    GATE['plateau_n_min'] = max(5, int(round(GATE_ORIG['plateau_n_min'] * _is_years / BASE_IS_YEARS)))
print(f"In-sample with percentile warm-up done: {_is_years:.1f} years | plateau_n_min: {GATE_ORIG['plateau_n_min']} -> {GATE['plateau_n_min']}")
print('validation_gate.DEFAULTS in use:', GATE)

print("=" * 70)
print("IN-SAMPLE WINDOW (ONE WINDOW FOR EVERY GRID CELL)")
print("=" * 70)
print(f"Strict In-Sample Range: {d0.index.min():%Y-%m-%d} to {d0.index.max():%Y-%m-%d}")
print(f"Total In-Sample Bars: {len(d0):,}")
print(f"Mondays with a valid signal bar and percentile: {int(d0['atr_rank'].notna().sum())}")
print(f"OOS block (not used here) starts: {OOS_START:%Y-%m-%d}")
```

    WARNING: 43 saltos distintos de 1 h en el indice (huecos). Los lunes con hueco se descartan.
    In-sample with percentile warm-up done: 1.0 years | plateau_n_min: 5 -> 5
    validation_gate.DEFAULTS in use: {'n_min': 30, 'pf_min': 1.3, 'mdd_min': -0.2, 'block': 5, 'mc_ret_p5_min': 0.0, 'mc_mdd_p5_min': -0.25, 'mc_ruin_max': 0.05, 'monkey_pct_min': 0.95, 'plateau_pf_min': 1.3, 'plateau_n_min': 5, 'plateau_max_drop': 30}
    ======================================================================
    IN-SAMPLE WINDOW (ONE WINDOW FOR EVERY GRID CELL)
    ======================================================================
    Strict In-Sample Range: 2023-01-02 to 2024-01-07
    Total In-Sample Bars: 8,865
    Mondays with a valid signal bar and percentile: 53
    OOS block (not used here) starts: 2024-01-08


## 3. 2D PARAMETER GRID (ATR PERCENTILE x ATR LENGTH)

Each cell runs the frozen rules with only `atr_pctl` and `atr_len` changed. PF is the plateau metric (as in RSI2); mean net return and t-stat are added because PF alone can be carried by a few Mondays in a strategy that trades ~20 times a year.


```python
TR = {}   # (pctl, atr_len) -> in-sample trades, reused by every later cell

def evaluate(pctl, L):
    t = eng.run_monday_backtest(is_dfs[L], atr_pctl=pctl, atr_len=L, **RULES_KW)
    TR[(pctl, L)] = t
    return (profit_factor(t["pnl"]) if len(t) else 0.0, len(t))

pf_grid, n_grid = grid_search(evaluate, PCTLS, ATR_LENS)
mean_grid = pd.DataFrame({L: {p: summarize(TR[(p, L)])["mean"] for p in PCTLS} for L in ATR_LENS})
t_grid    = pd.DataFrame({L: {p: summarize(TR[(p, L)])["t"] for p in PCTLS} for L in ATR_LENS})

print("=" * 70)
print("IN-SAMPLE PROFIT FACTOR GRID (rows = ATR percentile, columns = ATR length)")
print("=" * 70)
display(pf_grid.round(3))
print("\n" + "=" * 70)
print("IN-SAMPLE TRADE COUNT GRID (N)")
print("=" * 70)
display(n_grid.astype(int))
print("\n" + "=" * 70)
print("MEAN NET RETURN PER MONDAY, % (100% capital)")
print("=" * 70)
display(mean_grid.round(3))
print("\n" + "=" * 70)
print("t-STAT OF THE MEAN")
print("=" * 70)
display(t_grid.round(2))

plot_grid(pf_grid, n_grid, CHOSEN, title="Monday Effect · Profit Factor (in-sample) · orange = configured")
```

    ======================================================================
    IN-SAMPLE PROFIT FACTOR GRID (rows = ATR percentile, columns = ATR length)
    ======================================================================



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
      <th>12</th>
      <th>24</th>
      <th>36</th>
      <th>48</th>
      <th>72</th>
      <th>96</th>
      <th>120</th>
      <th>168</th>
      <th>240</th>
      <th>336</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.0</th>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
    </tr>
    <tr>
      <th>10.0</th>
      <td>1.210</td>
      <td>1.181</td>
      <td>1.172</td>
      <td>1.386</td>
      <td>1.204</td>
      <td>1.272</td>
      <td>1.235</td>
      <td>1.421</td>
      <td>1.520</td>
      <td>1.284</td>
    </tr>
    <tr>
      <th>20.0</th>
      <td>1.193</td>
      <td>1.075</td>
      <td>1.234</td>
      <td>1.410</td>
      <td>1.414</td>
      <td>1.302</td>
      <td>1.316</td>
      <td>1.121</td>
      <td>1.419</td>
      <td>1.726</td>
    </tr>
    <tr>
      <th>30.0</th>
      <td>1.176</td>
      <td>1.751</td>
      <td>1.728</td>
      <td>1.795</td>
      <td>1.217</td>
      <td>1.262</td>
      <td>1.207</td>
      <td>1.132</td>
      <td>1.131</td>
      <td>1.447</td>
    </tr>
    <tr>
      <th>40.0</th>
      <td>1.205</td>
      <td>2.278</td>
      <td>2.278</td>
      <td>13.755</td>
      <td>2.419</td>
      <td>1.794</td>
      <td>1.806</td>
      <td>1.364</td>
      <td>1.568</td>
      <td>1.064</td>
    </tr>
    <tr>
      <th>50.0</th>
      <td>1.232</td>
      <td>2.397</td>
      <td>13.755</td>
      <td>13.755</td>
      <td>13.755</td>
      <td>1.973</td>
      <td>1.822</td>
      <td>1.618</td>
      <td>1.565</td>
      <td>0.237</td>
    </tr>
    <tr>
      <th>60.0</th>
      <td>1.297</td>
      <td>14.662</td>
      <td>11.868</td>
      <td>5.092</td>
      <td>10.875</td>
      <td>7.130</td>
      <td>1.813</td>
      <td>1.614</td>
      <td>0.373</td>
      <td>0.555</td>
    </tr>
  </tbody>
</table>
</div>


    
    ======================================================================
    IN-SAMPLE TRADE COUNT GRID (N)
    ======================================================================



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
      <th>12</th>
      <th>24</th>
      <th>36</th>
      <th>48</th>
      <th>72</th>
      <th>96</th>
      <th>120</th>
      <th>168</th>
      <th>240</th>
      <th>336</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.0</th>
      <td>40</td>
      <td>40</td>
      <td>40</td>
      <td>40</td>
      <td>40</td>
      <td>40</td>
      <td>40</td>
      <td>40</td>
      <td>40</td>
      <td>40</td>
    </tr>
    <tr>
      <th>10.0</th>
      <td>40</td>
      <td>33</td>
      <td>33</td>
      <td>24</td>
      <td>29</td>
      <td>31</td>
      <td>33</td>
      <td>34</td>
      <td>33</td>
      <td>36</td>
    </tr>
    <tr>
      <th>20.0</th>
      <td>37</td>
      <td>23</td>
      <td>21</td>
      <td>19</td>
      <td>23</td>
      <td>24</td>
      <td>25</td>
      <td>28</td>
      <td>25</td>
      <td>26</td>
    </tr>
    <tr>
      <th>30.0</th>
      <td>33</td>
      <td>14</td>
      <td>15</td>
      <td>12</td>
      <td>17</td>
      <td>19</td>
      <td>22</td>
      <td>23</td>
      <td>20</td>
      <td>22</td>
    </tr>
    <tr>
      <th>40.0</th>
      <td>26</td>
      <td>11</td>
      <td>11</td>
      <td>6</td>
      <td>10</td>
      <td>15</td>
      <td>17</td>
      <td>19</td>
      <td>15</td>
      <td>15</td>
    </tr>
    <tr>
      <th>50.0</th>
      <td>20</td>
      <td>7</td>
      <td>6</td>
      <td>6</td>
      <td>6</td>
      <td>11</td>
      <td>13</td>
      <td>14</td>
      <td>12</td>
      <td>11</td>
    </tr>
    <tr>
      <th>60.0</th>
      <td>16</td>
      <td>5</td>
      <td>4</td>
      <td>3</td>
      <td>4</td>
      <td>7</td>
      <td>11</td>
      <td>10</td>
      <td>7</td>
      <td>7</td>
    </tr>
  </tbody>
</table>
</div>


    
    ======================================================================
    MEAN NET RETURN PER MONDAY, % (100% capital)
    ======================================================================



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
      <th>12</th>
      <th>24</th>
      <th>36</th>
      <th>48</th>
      <th>72</th>
      <th>96</th>
      <th>120</th>
      <th>168</th>
      <th>240</th>
      <th>336</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.0</th>
      <td>0.192</td>
      <td>0.192</td>
      <td>0.192</td>
      <td>0.192</td>
      <td>0.192</td>
      <td>0.192</td>
      <td>0.192</td>
      <td>0.192</td>
      <td>0.192</td>
      <td>0.192</td>
    </tr>
    <tr>
      <th>10.0</th>
      <td>0.192</td>
      <td>0.197</td>
      <td>0.187</td>
      <td>0.401</td>
      <td>0.208</td>
      <td>0.249</td>
      <td>0.214</td>
      <td>0.371</td>
      <td>0.442</td>
      <td>0.262</td>
    </tr>
    <tr>
      <th>20.0</th>
      <td>0.190</td>
      <td>0.097</td>
      <td>0.278</td>
      <td>0.471</td>
      <td>0.420</td>
      <td>0.294</td>
      <td>0.295</td>
      <td>0.120</td>
      <td>0.422</td>
      <td>0.652</td>
    </tr>
    <tr>
      <th>30.0</th>
      <td>0.192</td>
      <td>0.943</td>
      <td>0.865</td>
      <td>0.958</td>
      <td>0.272</td>
      <td>0.298</td>
      <td>0.220</td>
      <td>0.144</td>
      <td>0.153</td>
      <td>0.474</td>
    </tr>
    <tr>
      <th>40.0</th>
      <td>0.253</td>
      <td>1.570</td>
      <td>1.570</td>
      <td>3.672</td>
      <td>1.522</td>
      <td>0.772</td>
      <td>0.716</td>
      <td>0.380</td>
      <td>0.616</td>
      <td>0.093</td>
    </tr>
    <tr>
      <th>50.0</th>
      <td>0.293</td>
      <td>2.108</td>
      <td>3.672</td>
      <td>3.672</td>
      <td>3.672</td>
      <td>1.097</td>
      <td>0.901</td>
      <td>0.696</td>
      <td>0.701</td>
      <td>-1.275</td>
    </tr>
    <tr>
      <th>60.0</th>
      <td>0.422</td>
      <td>4.719</td>
      <td>4.693</td>
      <td>2.356</td>
      <td>4.264</td>
      <td>2.979</td>
      <td>0.989</td>
      <td>0.821</td>
      <td>-1.049</td>
      <td>-0.501</td>
    </tr>
  </tbody>
</table>
</div>


    
    ======================================================================
    t-STAT OF THE MEAN
    ======================================================================



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
      <th>12</th>
      <th>24</th>
      <th>36</th>
      <th>48</th>
      <th>72</th>
      <th>96</th>
      <th>120</th>
      <th>168</th>
      <th>240</th>
      <th>336</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.0</th>
      <td>0.41</td>
      <td>0.41</td>
      <td>0.41</td>
      <td>0.41</td>
      <td>0.41</td>
      <td>0.41</td>
      <td>0.41</td>
      <td>0.41</td>
      <td>0.41</td>
      <td>0.41</td>
    </tr>
    <tr>
      <th>10.0</th>
      <td>0.41</td>
      <td>0.35</td>
      <td>0.33</td>
      <td>0.57</td>
      <td>0.35</td>
      <td>0.45</td>
      <td>0.41</td>
      <td>0.70</td>
      <td>0.82</td>
      <td>0.52</td>
    </tr>
    <tr>
      <th>20.0</th>
      <td>0.38</td>
      <td>0.13</td>
      <td>0.35</td>
      <td>0.54</td>
      <td>0.58</td>
      <td>0.44</td>
      <td>0.46</td>
      <td>0.21</td>
      <td>0.62</td>
      <td>0.98</td>
    </tr>
    <tr>
      <th>30.0</th>
      <td>0.34</td>
      <td>0.81</td>
      <td>0.80</td>
      <td>0.75</td>
      <td>0.29</td>
      <td>0.36</td>
      <td>0.30</td>
      <td>0.21</td>
      <td>0.19</td>
      <td>0.62</td>
    </tr>
    <tr>
      <th>40.0</th>
      <td>0.36</td>
      <td>1.11</td>
      <td>1.11</td>
      <td>2.12</td>
      <td>1.05</td>
      <td>0.77</td>
      <td>0.81</td>
      <td>0.46</td>
      <td>0.61</td>
      <td>0.09</td>
    </tr>
    <tr>
      <th>50.0</th>
      <td>0.35</td>
      <td>0.97</td>
      <td>2.12</td>
      <td>2.12</td>
      <td>2.12</td>
      <td>0.81</td>
      <td>0.78</td>
      <td>0.64</td>
      <td>0.56</td>
      <td>-1.89</td>
    </tr>
    <tr>
      <th>60.0</th>
      <td>0.40</td>
      <td>2.39</td>
      <td>1.84</td>
      <td>0.90</td>
      <td>1.60</td>
      <td>1.81</td>
      <td>0.73</td>
      <td>0.55</td>
      <td>-1.00</td>
      <td>-0.64</td>
    </tr>
  </tbody>
</table>
</div>



    
![png](02_Monday_Effect_Optimization_files/02_Monday_Effect_Optimization_7_8.png)
    


## 3.5 3D PROFIT-FACTOR SURFACE (ATR percentile x ATR length)


```python
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

HARD_LIMIT = float(globals().get("HARD_LIMIT", 0.09))        # 0.09 = -9 %. Define HARD_LIMIT earlier if your YAML uses another value
LIMIT_PCT  = HARD_LIMIT * 100.0
FRACTION   = float(eng.ENGINE_DEFAULTS["size_fraction"])      # robot sizing (e.g. 20 %)
DD_MODE    = "intrabar"                                       # "intrabar" (needs engine v3.2) | "close"
SCENARIOS  = [("Base costs", 1.0), ("Costs x2", 2.0), ("Costs x3", 3.0)]
PF_MIN, N_MIN, MAX_DROP = GATE["plateau_pf_min"], GATE["plateau_n_min"], GATE["plateau_max_drop"]


def _full_dd(L, trades):
    """Max drawdown (%, negative) on the FULL period for the trades of one grid cell, at the robot sizing."""
    if len(trades) == 0:
        return np.nan
    dfp = preps[L]
    if DD_MODE == "intrabar" and hasattr(eng, "hard_limit_report_intrabar"):
        rep = eng.hard_limit_report_intrabar(dfp, trades, HARD_LIMIT, FRACTION)
    else:
        rep = eng.hard_limit_report(eng.hourly_returns(dfp, trades, FRACTION), HARD_LIMIT)
    return 100.0 * rep["max_dd"]


def _plateau(pf, n, p, L):
    """(passed, worst neighbour drop %) if cell (p, L) were the configured one."""
    try:
        r = plateau_check(pf.fillna(0.0), n.fillna(0.0), (p, L), pf_min=PF_MIN, n_min=N_MIN, max_drop_pct=MAX_DROP)
        return bool(r["passed"]), float(r["worst_neighbor_drop_pct"])
    except Exception:
        return False, np.nan


# ---- compute every scenario (in-sample PF grid + full-period drawdown grid) ----
grids = {}
for label, mult in SCENARIOS:
    kw = {**RULES_KW, "cost_bps_per_side": COST_BPS * mult}
    mk = lambda: pd.DataFrame(index=PCTLS, columns=ATR_LENS, dtype=float)
    pf, n, mean, tt, dd = mk(), mk(), mk(), mk(), mk()
    for L in ATR_LENS:
        for p in PCTLS:
            t_is = eng.run_monday_backtest(is_dfs[L], atr_pctl=p, atr_len=L, **kw)
            n.loc[p, L] = len(t_is)
            if len(t_is):
                pf.loc[p, L]   = profit_factor(t_is["pnl"])
                mean.loc[p, L] = float(t_is["pnl"].mean())
                tt.loc[p, L]   = tstat(t_is["pnl"])
            t_full = eng.run_monday_backtest(preps[L], atr_pctl=p, atr_len=L, **kw)
            dd.loc[p, L] = _full_dd(L, t_full)
    pf = pf.replace(np.inf, np.nan)
    grids[label] = dict(pf=pf, n=n, mean=mean, t=tt, dd=dd, margin=dd + LIMIT_PCT)

keys = list(grids.keys())
XP = list(range(len(ATR_LENS)))                       # categorical x positions (ATR lengths are unevenly spaced)
XT = [str(L) for L in ATR_LENS]
LL = np.tile(np.array(ATR_LENS), (len(PCTLS), 1))     # ATR length of each cell, for hover text
X, Y = np.meshgrid(XP, PCTLS)
ia, ib = PCTLS.index(ATR_PCTL), ATR_LENS.index(ATR_LEN)

# ---- shared scales so scenarios are comparable ----
pf_all  = [g["pf"].values for g in grids.values()]
z_floor = min(1.0, float(np.nanmin([np.nanmin(a) for a in pf_all]))) - 0.35
z_top   = float(np.nanmax([np.nanmax(a) for a in pf_all])) + 0.25
amax    = max(1.0, max(float(np.nanmax(np.abs(g["margin"].values))) for g in grids.values()))

colorscale   = [[0.00, "#b5452f"], [0.25, "#e8a46a"], [0.50, "#f4e79a"], [0.75, "#8fd19e"], [1.00, "#2f7d55"]]
margin_scale = [[0.00, "#b5452f"], [0.45, "#e8704f"], [0.50, "#f5a524"], [0.55, "#8fd19e"], [1.00, "#34d399"]]

TPS = 7                                               # traces per scenario
fig, titles, summary = go.Figure(), [], []

for i, key in enumerate(keys):
    g = grids[key]
    pf, n, mean, tt, dd, margin = g["pf"], g["n"], g["mean"], g["t"], g["dd"], g["margin"]
    vis = (i == 0)

    # plateau verdict of every cell (as if it were the configured one)
    pas = pd.DataFrame(False, index=pf.index, columns=pf.columns)
    drop = pd.DataFrame(np.nan, index=pf.index, columns=pf.columns)
    for p in PCTLS:
        for L in ATR_LENS:
            pas.loc[p, L], drop.loc[p, L] = _plateau(pf, n, p, L)
    has = pf.notna()
    verdict = np.where(pas.values, "PLATEAU OK", "plateau FAIL")
    n_pass = int((pas.values & has.values).sum())
    cd = np.dstack([n.values, dd.values, margin.values, mean.values, tt.values, drop.values])

    # 1) PF surface (in-sample)
    fig.add_trace(go.Surface(
        x=XP, y=PCTLS, z=pf.values, customdata=cd, text=verdict,
        colorscale=colorscale, cmin=1.0, cmax=2.0,
        colorbar=dict(title="Profit<br>Factor (IS)", len=0.42, y=0.80, x=0.93, thickness=14),
        hovertemplate=("P%{y} · ATR index %{x}<br>PF (IS) %{z:.2f}"
                       "<br>Trades (IS) %{customdata[0]:.0f}"
                       "<br>Mean net/trade %{customdata[3]:.2f}% · t %{customdata[4]:.2f}"
                       "<br>MaxDD (full) %{customdata[1]:.1f}%"
                       f"<br>Hard limit -{LIMIT_PCT:.0f}%: " + "%{customdata[2]:+.1f} pp margin"
                       "<br>Worst neighbour drop %{customdata[5]:.0f}% · %{text}<extra></extra>"),
        visible=vis))

    # 2) floor map: margin to the hard limit
    fig.add_trace(go.Surface(
        x=XP, y=PCTLS, z=np.full(pf.shape, z_floor), surfacecolor=margin.values, customdata=cd, text=verdict,
        colorscale=margin_scale, cmin=-amax, cmax=amax, opacity=0.95,
        colorbar=dict(title=f"Margin to<br>-{LIMIT_PCT:.0f}% (pp)", len=0.42, y=0.30, x=0.93, thickness=14),
        lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0),
        hovertemplate=("FLOOR · P%{y} · ATR index %{x}"
                       "<br>MaxDD (full) %{customdata[1]:.1f}%"
                       f"<br>Hard limit -{LIMIT_PCT:.0f}%: " + "%{customdata[2]:+.1f} pp margin<extra></extra>"),
        visible=vis))

    # 3) markers: cell would pass / fail the plateau gate
    for mask, name, color, symbol in ((pas.values & has.values, "Would pass plateau gate", "#34d399", "diamond"),
                                      (~pas.values & has.values, "Would fail plateau gate", "#f87171", "x")):
        fig.add_trace(go.Scatter3d(
            x=X[mask], y=Y[mask], z=pf.values[mask] + 0.03, mode="markers", name=name, text=LL[mask],
            marker=dict(size=4, color=color, symbol=symbol, line=dict(width=0)),
            hovertemplate=f"{name}<br>P%{{y}} · ATR %{{text}}<extra></extra>",
            showlegend=True, legendgroup=name, visible=vis))

    # 4) drop lines from the surface to the floor for the cells that would pass
    m = pas.values & has.values
    xs, ys, zs = [], [], []
    for xv, yv, zv in zip(X[m], Y[m], pf.values[m]):
        xs += [xv, xv, None]; ys += [yv, yv, None]; zs += [zv, z_floor, None]
    fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", line=dict(color="rgba(52,211,153,0.35)", width=2),
                               hoverinfo="skip", showlegend=False, visible=vis))

    # 5) rings: the 3x3 neighbourhood of the configured cell (what the official gate looks at)
    rr = range(max(ia - 1, 0), min(ia + 2, len(PCTLS)))
    cc = range(max(ib - 1, 0), min(ib + 2, len(ATR_LENS)))
    nx_ = [XP[c] for r in rr for c in cc]
    ny_ = [PCTLS[r] for r in rr for c in cc]
    nz_ = [float(pf.iloc[r, c]) + 0.07 for r in rr for c in cc]
    fig.add_trace(go.Scatter3d(x=nx_, y=ny_, z=nz_, mode="markers", name="3x3 neighbourhood of configured",
                               marker=dict(size=8, color="rgba(0,0,0,0)", symbol="circle-open",
                                           line=dict(color="#f5a524", width=3)),
                               hoverinfo="skip", showlegend=True, legendgroup="nbh", visible=vis))

    # 6) configured cell
    c_ok, c_drop = bool(pas.loc[ATR_PCTL, ATR_LEN]), float(drop.loc[ATR_PCTL, ATR_LEN])
    col = "#34d399" if c_ok else "#f87171"
    fig.add_trace(go.Scatter3d(
        x=[XP[ib]], y=[ATR_PCTL], z=[float(pf.loc[ATR_PCTL, ATR_LEN]) + 0.12], mode="markers+text",
        text=[f"configured {'✓' if c_ok else '✗'}"], textposition="top center", textfont=dict(color=col, size=13),
        marker=dict(size=7, color="white", line=dict(color=col, width=3)), showlegend=False,
        hovertemplate=f"Configured P{ATR_PCTL:g}, ATR({ATR_LEN})<br>plateau gate: {'PASS' if c_ok else 'FAIL'}<extra></extra>",
        visible=vis))

    titles.append(f"{cfg['id']} · PF in-sample · {key} · {n_pass}/{int(has.values.sum())} cells would pass the plateau gate")
    summary.append({"Scenario": key,
                    "PF (IS)": round(float(pf.loc[ATR_PCTL, ATR_LEN]), 3),
                    "N (IS)": int(n.loc[ATR_PCTL, ATR_LEN]),
                    "Mean net %": round(float(mean.loc[ATR_PCTL, ATR_LEN]), 3),
                    "t": round(float(tt.loc[ATR_PCTL, ATR_LEN]), 2),
                    "MaxDD full %": round(float(dd.loc[ATR_PCTL, ATR_LEN]), 2),
                    f"Margin vs -{LIMIT_PCT:.0f}% (pp)": round(float(margin.loc[ATR_PCTL, ATR_LEN]), 2),
                    "Plateau (configured)": "PASS" if c_ok else "FAIL",
                    "Cells passing plateau": n_pass})

PAD = "\u00a0"
buttons = []
for i, key in enumerate(keys):
    v = [False] * (TPS * len(keys))
    for j in range(TPS):
        v[TPS * i + j] = True
    buttons.append(dict(label=f"{PAD}{key}{PAD}", method="update", args=[{"visible": v}, {"title.text": titles[i]}]))

fig.update_layout(
    template="plotly_dark", paper_bgcolor="#15171c", height=700,
    title=dict(text=titles[0], x=0.02),
    scene=dict(
        xaxis=dict(title="ATR length (bars)", tickmode="array", tickvals=XP, ticktext=XT),
        yaxis_title="ATR percentile", zaxis_title="Profit Factor", zaxis=dict(range=[z_floor, z_top]),
        aspectmode="manual", aspectratio=dict(x=1.5, y=1.0, z=0.8),
        camera=dict(eye=dict(x=1.6, y=1.6, z=0.9), center=dict(x=0, y=0, z=-0.1))),
    legend=dict(x=0.0, y=0.02, bgcolor="rgba(0,0,0,0)", font=dict(color="#9aa0ab", size=11)),
    updatemenus=[dict(type="buttons", direction="right", x=0.0, xanchor="left", y=1.12, yanchor="top", active=0,
                      buttons=buttons, bgcolor="#9fb3c8", bordercolor="#4a5160", borderwidth=1,
                      pad=dict(l=3, r=3, t=0, b=0), font=dict(color="#15171c", size=12))],
    annotations=[dict(
        text=(f"Height = in-sample PF. Floor = margin to the -{LIMIT_PCT:.0f}% hard limit on the FULL period "
              f"({DD_MODE} drawdown, {FRACTION:.0%} sizing). Markers = would the cell pass the plateau gate "
              f"(PF >= {PF_MIN}, N >= {N_MIN}, drop <= {MAX_DROP}% in its 3x3). Orange rings = configured cell's neighbourhood."),
        x=0.0, y=-0.02, xref="paper", yref="paper", showarrow=False, xanchor="left",
        font=dict(color="#9aa0ab", size=11))],
    margin=dict(l=0, r=0, t=90, b=30))

print(f"Configured cell P{ATR_PCTL:g}, ATR({ATR_LEN}) by scenario:")
display(pd.DataFrame(summary).set_index("Scenario"))
fig.show()
fig.write_html(Path(RUN_DIR) / "02_pf_surface.html", include_plotlyjs="cdn")
```

    Configured cell P40, ATR(24) by scenario:



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
      <th>PF (IS)</th>
      <th>N (IS)</th>
      <th>Mean net %</th>
      <th>t</th>
      <th>MaxDD full %</th>
      <th>Margin vs -9% (pp)</th>
      <th>Plateau (configured)</th>
      <th>Cells passing plateau</th>
    </tr>
    <tr>
      <th>Scenario</th>
      <th></th>
      <th></th>
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
      <th>Base costs</th>
      <td>2.278</td>
      <td>11</td>
      <td>1.570</td>
      <td>1.11</td>
      <td>-3.20</td>
      <td>5.80</td>
      <td>FAIL</td>
      <td>3</td>
    </tr>
    <tr>
      <th>Costs x2</th>
      <td>2.151</td>
      <td>11</td>
      <td>1.458</td>
      <td>1.03</td>
      <td>-3.31</td>
      <td>5.69</td>
      <td>FAIL</td>
      <td>2</td>
    </tr>
    <tr>
      <th>Costs x3</th>
      <td>2.031</td>
      <td>11</td>
      <td>1.347</td>
      <td>0.95</td>
      <td>-3.42</td>
      <td>5.58</td>
      <td>FAIL</td>
      <td>2</td>
    </tr>
  </tbody>
</table>
</div>




## 4. PLATEAU & ANTI-CLIFF CHECK

Official criterion = `robustness.plateau_check` with the thresholds of `validation_gate.DEFAULTS`. Note that the ATR-length axis is not evenly spaced (12, 24, 48, 72, 96, 168): "one step away" means the adjacent grid value.


```python
pl = plateau_check(pf_grid, n_grid, CHOSEN, pf_min=GATE["plateau_pf_min"], n_min=GATE["plateau_n_min"],
                   max_drop_pct=GATE["plateau_max_drop"])

ia, ib = pf_grid.index.get_loc(ATR_PCTL), pf_grid.columns.get_loc(ATR_LEN)
sl = (slice(max(ia - 1, 0), ia + 2), slice(max(ib - 1, 0), ib + 2))
cells = pf_grid.stack()
rank = int((cells > pf_grid.loc[ATR_PCTL, ATR_LEN]).sum()) + 1

print("=" * 70)
print(f"3x3 NEIGHBORHOOD OF THE CONFIGURED POINT P{ATR_PCTL:g}, ATR({ATR_LEN})")
print("=" * 70)
print("Profit Factor:"); display(pf_grid.iloc[sl].round(3))
print("N trades:");      display(n_grid.iloc[sl].astype(int))
print(f"Center PF: {pl['center_pf']:.3f} | worst neighbor drop: {pl['worst_neighbor_drop_pct']:.1f}% (max {GATE['plateau_max_drop']}%)")
print(f"Plateau (all 9 cells PF >= {GATE['plateau_pf_min']} and N >= {GATE['plateau_n_min']}): {'YES' if pl['plateau'] else 'NO'}")
print(f"Anti-cliff: {'PASS' if pl['anticliff'] else 'FAIL'} | Gate (plateau AND anti-cliff): {'PASS' if pl['passed'] else 'FAIL'}")
print(f"Cells with PF >= {GATE['plateau_pf_min']}: {pl['pct_cells_pf_ok'] * 100:.0f}% of {len(cells)} | cells with mean net > 0: {int((mean_grid.stack() > 0).sum())} of {len(cells)}")
print(f"Configured point ranks #{rank} of {len(cells)} by PF | best cell: {pl['best_cell']} (PF {pl['best_pf']:.3f}) | configured on grid edge: {pl['edge_of_grid']}")

# ---- Secondary diagnostic (NOT the gate): same check inside the institutional era only ----
# The era split is part of the hypothesis (notebook 01, section 1.1), and the retail era (2017-19) is inside the IS block.
a, b = ERAS["Institutional (2020-23)"]
def era_trades(t):
    y = pd.to_datetime(t["entry_time"]).dt.year
    return t[(y >= a) & (y <= b)]
pf_i = pd.DataFrame({L: {p: (profit_factor(era_trades(TR[(p, L)])["pnl"]) if len(era_trades(TR[(p, L)])) else 0.0) for p in PCTLS} for L in ATR_LENS})
n_i  = pd.DataFrame({L: {p: float(len(era_trades(TR[(p, L)]))) for p in PCTLS} for L in ATR_LENS})
pl_i = plateau_check(pf_i, n_i, CHOSEN, pf_min=GATE["plateau_pf_min"], n_min=GATE["plateau_n_min"], max_drop_pct=GATE["plateau_max_drop"])
print("\n" + "-" * 70)
print(f"DIAGNOSTIC · institutional era only ({a}-{b}): center PF {pl_i['center_pf']:.3f} | plateau {'YES' if pl_i['plateau'] else 'NO'} | "
      f"worst drop {pl_i['worst_neighbor_drop_pct']:.1f}% | gate {'PASS' if pl_i['passed'] else 'FAIL'}")
display(pf_i.round(3))
```

    ======================================================================
    3x3 NEIGHBORHOOD OF THE CONFIGURED POINT P40, ATR(24)
    ======================================================================
    Profit Factor:



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
      <th>12</th>
      <th>24</th>
      <th>36</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>30.0</th>
      <td>1.176</td>
      <td>1.751</td>
      <td>1.728</td>
    </tr>
    <tr>
      <th>40.0</th>
      <td>1.205</td>
      <td>2.278</td>
      <td>2.278</td>
    </tr>
    <tr>
      <th>50.0</th>
      <td>1.232</td>
      <td>2.397</td>
      <td>13.755</td>
    </tr>
  </tbody>
</table>
</div>


    N trades:



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
      <th>12</th>
      <th>24</th>
      <th>36</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>30.0</th>
      <td>33</td>
      <td>14</td>
      <td>15</td>
    </tr>
    <tr>
      <th>40.0</th>
      <td>26</td>
      <td>11</td>
      <td>11</td>
    </tr>
    <tr>
      <th>50.0</th>
      <td>20</td>
      <td>7</td>
      <td>6</td>
    </tr>
  </tbody>
</table>
</div>


    Center PF: 2.278 | worst neighbor drop: 48.4% (max 30%)
    Plateau (all 9 cells PF >= 1.3 and N >= 5): NO
    Anti-cliff: FAIL | Gate (plateau AND anti-cliff): FAIL
    Cells with PF >= 1.3: 51% of 70 | cells with mean net > 0: 67 of 70
    Configured point ranks #12 of 70 by PF | best cell: (np.float64(60.0), np.int64(24)) (PF 14.662) | configured on grid edge: False
    
    ----------------------------------------------------------------------
    DIAGNOSTIC · institutional era only (2020-2023): center PF 2.278 | plateau NO | worst drop 48.4% | gate FAIL



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
      <th>12</th>
      <th>24</th>
      <th>36</th>
      <th>48</th>
      <th>72</th>
      <th>96</th>
      <th>120</th>
      <th>168</th>
      <th>240</th>
      <th>336</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.0</th>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
      <td>1.210</td>
    </tr>
    <tr>
      <th>10.0</th>
      <td>1.210</td>
      <td>1.181</td>
      <td>1.172</td>
      <td>1.386</td>
      <td>1.204</td>
      <td>1.272</td>
      <td>1.235</td>
      <td>1.421</td>
      <td>1.520</td>
      <td>1.284</td>
    </tr>
    <tr>
      <th>20.0</th>
      <td>1.193</td>
      <td>1.075</td>
      <td>1.234</td>
      <td>1.410</td>
      <td>1.414</td>
      <td>1.302</td>
      <td>1.316</td>
      <td>1.121</td>
      <td>1.419</td>
      <td>1.726</td>
    </tr>
    <tr>
      <th>30.0</th>
      <td>1.176</td>
      <td>1.751</td>
      <td>1.728</td>
      <td>1.795</td>
      <td>1.217</td>
      <td>1.262</td>
      <td>1.207</td>
      <td>1.132</td>
      <td>1.131</td>
      <td>1.447</td>
    </tr>
    <tr>
      <th>40.0</th>
      <td>1.205</td>
      <td>2.278</td>
      <td>2.278</td>
      <td>13.755</td>
      <td>2.419</td>
      <td>1.794</td>
      <td>1.806</td>
      <td>1.364</td>
      <td>1.568</td>
      <td>1.064</td>
    </tr>
    <tr>
      <th>50.0</th>
      <td>1.232</td>
      <td>2.397</td>
      <td>13.755</td>
      <td>13.755</td>
      <td>13.755</td>
      <td>1.973</td>
      <td>1.822</td>
      <td>1.618</td>
      <td>1.565</td>
      <td>0.237</td>
    </tr>
    <tr>
      <th>60.0</th>
      <td>1.297</td>
      <td>14.662</td>
      <td>11.868</td>
      <td>5.092</td>
      <td>10.875</td>
      <td>7.130</td>
      <td>1.813</td>
      <td>1.614</td>
      <td>0.373</td>
      <td>0.555</td>
    </tr>
  </tbody>
</table>
</div>


## 5. DOSE-RESPONSE: DOES MORE VOLATILITY FILTER MEAN MORE EDGE?

With `atr_len` fixed at the configured value, only the percentile changes. A healthy filter shows a roughly monotonic climb of the net mean per trade (at the cost of fewer trades). `P0` is the unfiltered Monday (still with the calendar filter).


```python
dose = pd.DataFrame({p: summarize(TR[(p, ATR_LEN)]) for p in PCTLS}).T
dose.index.name = "atr_pctl"
rho_d, p_d = stats.spearmanr(dose.index.to_numpy(float), dose["mean"].to_numpy(float))

print("=" * 70)
print(f"DOSE-RESPONSE AT ATR({ATR_LEN}) · in-sample · 100% capital, net of {COST_BPS:g} bps/side")
print("=" * 70)
display(dose.rename(columns={"n": "Trades", "pf": "PF", "mean": "Mean net %", "t": "t-stat", "win": "Win %"}).round(3))
print(f"Spearman (percentile vs mean net return): rho = {rho_d:+.2f} (p = {p_d:.3f}, only {len(dose)} points: descriptive)")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.2), facecolor=BG)
dark_ax(ax1); dark_ax(ax2)
x = np.arange(len(dose))
ax1.bar(x, dose["mean"], color=[GREEN if v > 0 else RED for v in dose["mean"]], width=0.6)
ax1.axhline(0, color=SUB, lw=0.6)
ax1.set_xticks(x); ax1.set_xticklabels([f"P{p:g}" for p in dose.index], color=SUB)
ax1.set_title("Mean net return per Monday (%)", color=TXT, fontweight="bold", loc="left")
ax2.plot(x, dose["pf"].clip(upper=8), color=GREEN, lw=1.8, marker="o")
ax2.axhline(1.0, color=RED, lw=1.0); ax2.axhline(GATE["plateau_pf_min"], color=ORANGE, ls="--", lw=1.0)
ax2.set_xticks(x); ax2.set_xticklabels([f"P{p:g}" for p in dose.index], color=SUB)
ax2.set_title("Profit Factor", color=TXT, fontweight="bold", loc="left")
for i, n in enumerate(dose["n"]):
    ax2.text(i, ax2.get_ylim()[0], f"N={int(n)}", color=SUB, fontsize=8, ha="center", va="bottom")
plt.tight_layout(); plt.show()
```

    ======================================================================
    DOSE-RESPONSE AT ATR(24) · in-sample · 100% capital, net of 5.5 bps/side
    ======================================================================



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
      <th>Trades</th>
      <th>PF</th>
      <th>Mean net %</th>
      <th>t-stat</th>
      <th>Win %</th>
    </tr>
    <tr>
      <th>atr_pctl</th>
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
      <td>40.0</td>
      <td>1.210</td>
      <td>0.192</td>
      <td>0.413</td>
      <td>50.000</td>
    </tr>
    <tr>
      <th>10.0</th>
      <td>33.0</td>
      <td>1.181</td>
      <td>0.197</td>
      <td>0.349</td>
      <td>45.455</td>
    </tr>
    <tr>
      <th>20.0</th>
      <td>23.0</td>
      <td>1.075</td>
      <td>0.097</td>
      <td>0.130</td>
      <td>34.783</td>
    </tr>
    <tr>
      <th>30.0</th>
      <td>14.0</td>
      <td>1.751</td>
      <td>0.943</td>
      <td>0.811</td>
      <td>50.000</td>
    </tr>
    <tr>
      <th>40.0</th>
      <td>11.0</td>
      <td>2.278</td>
      <td>1.570</td>
      <td>1.106</td>
      <td>63.636</td>
    </tr>
    <tr>
      <th>50.0</th>
      <td>7.0</td>
      <td>2.397</td>
      <td>2.108</td>
      <td>0.969</td>
      <td>57.143</td>
    </tr>
    <tr>
      <th>60.0</th>
      <td>5.0</td>
      <td>14.662</td>
      <td>4.719</td>
      <td>2.393</td>
      <td>80.000</td>
    </tr>
  </tbody>
</table>
</div>


    Spearman (percentile vs mean net return): rho = +0.89 (p = 0.007, only 7 points: descriptive)



    
![png](02_Monday_Effect_Optimization_files/02_Monday_Effect_Optimization_13_3.png)
    


## 6. ENTRY-HOUR ROBUSTNESS

The signal is the Sunday 23:00 close and the entry is Monday 00:00 UTC. Here the entry hour moves (the position is always held 24 bars), with the configured volatility and calendar filters, next to the naked Monday at the same hour. If the edge lived only at 00:00 it would be a data artefact.


```python
HOURS = [0, 1, 2, 3, 4, 6, 8, 12]
rows = []
for h in HOURS:
    d = eng.prepare(df_raw, atr_len=ATR_LEN, entry_hour=h)
    start_h = max(d.index[d["atr_rank"].notna()][0], common_start)
    d = d[(d.index >= start_h) & (d.index < OOS_START)]
    kw = dict(atr_len=ATR_LEN, entry_hour=h, hold_bars=HOLD, cost_bps_per_side=COST_BPS)
    tf = eng.run_monday_backtest(d, vol_mode=VOL_MODE, atr_pctl=ATR_PCTL, skip_first_monday=SKIP1, **kw)
    tn = eng.run_monday_backtest(d, vol_mode="none", skip_first_monday=False, **kw)
    sf, sn = summarize(tf), summarize(tn)
    rows.append({"Entry hour (UTC)": h, "Trades": sf["n"], "PF filtered": sf["pf"], "Mean net % filtered": sf["mean"],
                 "t filtered": sf["t"], "PF naked": sn["pf"], "Mean net % naked": sn["mean"]})
hour_tbl = pd.DataFrame(rows).set_index("Entry hour (UTC)")

print("=" * 70)
print(f"ENTRY-HOUR SENSITIVITY · in-sample · configured P{ATR_PCTL:g}, ATR({ATR_LEN}) vs naked Monday")
print("=" * 70)
display(hour_tbl.round(3))

if ENTRY_HOUR in hour_tbl.index:
    ref = summarize(TR[CHOSEN])
    print(f"Consistency check vs section 3 at hour {ENTRY_HOUR}: PF {hour_tbl.loc[ENTRY_HOUR, 'PF filtered']:.3f} vs {ref['pf']:.3f} "
          f"(a small gap is possible if the first valid Monday differs by one week).")
share_ok = float((hour_tbl["PF filtered"] >= GATE["plateau_pf_min"]).mean())
print(f"Share of tested hours with filtered PF >= {GATE['plateau_pf_min']}: {share_ok * 100:.0f}%")
```

    ======================================================================
    ENTRY-HOUR SENSITIVITY · in-sample · configured P40, ATR(24) vs naked Monday
    ======================================================================



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
      <th>Trades</th>
      <th>PF filtered</th>
      <th>Mean net % filtered</th>
      <th>t filtered</th>
      <th>PF naked</th>
      <th>Mean net % naked</th>
    </tr>
    <tr>
      <th>Entry hour (UTC)</th>
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
      <td>11</td>
      <td>2.278</td>
      <td>1.570</td>
      <td>1.106</td>
      <td>1.126</td>
      <td>0.121</td>
    </tr>
    <tr>
      <th>1</th>
      <td>10</td>
      <td>2.189</td>
      <td>1.578</td>
      <td>1.002</td>
      <td>1.154</td>
      <td>0.147</td>
    </tr>
    <tr>
      <th>2</th>
      <td>12</td>
      <td>2.784</td>
      <td>1.880</td>
      <td>1.296</td>
      <td>1.505</td>
      <td>0.398</td>
    </tr>
    <tr>
      <th>3</th>
      <td>12</td>
      <td>4.199</td>
      <td>2.415</td>
      <td>1.651</td>
      <td>1.755</td>
      <td>0.534</td>
    </tr>
    <tr>
      <th>4</th>
      <td>12</td>
      <td>3.369</td>
      <td>2.107</td>
      <td>1.581</td>
      <td>1.764</td>
      <td>0.529</td>
    </tr>
    <tr>
      <th>6</th>
      <td>15</td>
      <td>2.030</td>
      <td>0.982</td>
      <td>0.951</td>
      <td>1.522</td>
      <td>0.355</td>
    </tr>
    <tr>
      <th>8</th>
      <td>16</td>
      <td>2.284</td>
      <td>1.060</td>
      <td>1.097</td>
      <td>1.436</td>
      <td>0.303</td>
    </tr>
    <tr>
      <th>12</th>
      <td>18</td>
      <td>3.305</td>
      <td>1.473</td>
      <td>1.372</td>
      <td>2.115</td>
      <td>0.641</td>
    </tr>
  </tbody>
</table>
</div>


    Consistency check vs section 3 at hour 0: PF 2.278 vs 2.278 (a small gap is possible if the first valid Monday differs by one week).
    Share of tested hours with filtered PF >= 1.3: 100%


## 7. FILTER ABLATION BY ERA (IN-SAMPLE)

What does each filter contribute? Four combinations at the configured `atr_pctl` / `atr_len`, split by the eras that fall inside the in-sample block (the ETF era is out-of-sample and appears in notebook 03). Cells show `PF | mean net % | N`.


```python
combos = {"Naked Monday": dict(vol_mode="none", skip_first_monday=False),
          "Calendar filter only": dict(vol_mode="none", skip_first_monday=True),
          "Volatility filter only": dict(vol_mode=VOL_MODE, skip_first_monday=False),
          "Both (configured)": dict(vol_mode=VOL_MODE, skip_first_monday=SKIP1)}
base_kw = dict(atr_pctl=ATR_PCTL, atr_len=ATR_LEN, entry_hour=ENTRY_HOUR, hold_bars=HOLD, cost_bps_per_side=COST_BPS)
_is_year_set = set(is_dfs[ATR_LEN].index.year)
IS_ERAS = [e for e, (a_, b_) in ERAS.items() if any(a_ <= y <= b_ for y in _is_year_set)]   # eras with in-sample data

abl, rows = {}, []
for name, kw in combos.items():
    t = eng.run_monday_backtest(is_dfs[ATR_LEN], **base_kw, **kw)
    abl[name] = t
    yr = pd.to_datetime(t["entry_time"]).dt.year
    row = {"Variant": name}
    for e in IS_ERAS:
        a_, b_ = ERAS[e]
        s = summarize(t[(yr >= a_) & (yr <= b_)])
        row[e] = f"{s['pf']:.2f} | {s['mean']:+.3f}% | {s['n']}" if s["n"] else "n/a"
    s_all = summarize(t)
    row["All in-sample"] = f"{s_all['pf']:.2f} | {s_all['mean']:+.3f}% | {s_all['n']}"
    rows.append(row)

print("=" * 70)
print(f"FILTER ABLATION · in-sample · net of {COST_BPS:g} bps/side · PF | mean net % | N")
print("=" * 70)
display(pd.DataFrame(rows).set_index("Variant"))

# PF by calendar year for the configured rules (stability inside the IS block)
tc = abl["Both (configured)"]
by_year = tc.assign(year=pd.to_datetime(tc["entry_time"]).dt.year).groupby("year")["pnl"].agg(
    n="size", pf=profit_factor, mean="mean")
print("\nConfigured rules by entry year (in-sample):")
display(by_year.round(3))
```

    ======================================================================
    FILTER ABLATION · in-sample · net of 5.5 bps/side · PF | mean net % | N
    ======================================================================



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
      <th>Institutional (2020-23)</th>
      <th>ETF (2024+)</th>
      <th>All in-sample</th>
    </tr>
    <tr>
      <th>Variant</th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>Naked Monday</th>
      <td>1.04 | +0.036% | 52</td>
      <td>inf | +4.553% | 1</td>
      <td>1.13 | +0.121% | 53</td>
    </tr>
    <tr>
      <th>Calendar filter only</th>
      <td>1.21 | +0.192% | 40</td>
      <td>n/a</td>
      <td>1.21 | +0.192% | 40</td>
    </tr>
    <tr>
      <th>Volatility filter only</th>
      <td>2.41 | +1.526% | 14</td>
      <td>inf | +4.553% | 1</td>
      <td>2.70 | +1.728% | 15</td>
    </tr>
    <tr>
      <th>Both (configured)</th>
      <td>2.28 | +1.570% | 11</td>
      <td>n/a</td>
      <td>2.28 | +1.570% | 11</td>
    </tr>
  </tbody>
</table>
</div>


    
    Configured rules by entry year (in-sample):



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
    </tr>
    <tr>
      <th>year</th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2023</th>
      <td>11</td>
      <td>2.278</td>
      <td>1.57</td>
    </tr>
  </tbody>
</table>
</div>


## 8. VERDICT & NEXT STEPS


```python
mean_both = summarize(abl["Both (configured)"])["mean"]
mean_naked = summarize(abl["Naked Monday"])["mean"]
ready = bool(pl["passed"])

print("=" * 80)
print("8. SUMMARY OF IN-SAMPLE PARAMETER STABILITY")
print("=" * 80)
print(f"""
Key Findings:

1. Plateau gate (full in-sample, official): {'PASS' if pl['passed'] else 'FAIL'} - center PF {pl['center_pf']:.3f}, worst neighbor drop {pl['worst_neighbor_drop_pct']:.1f}%,
   plateau {'yes' if pl['plateau'] else 'no'}; {pl['pct_cells_pf_ok'] * 100:.0f}% of {len(cells)} cells have PF >= {GATE['plateau_pf_min']}; configured point ranks #{rank} by PF.
   Diagnostic inside the institutional era only: {'PASS' if pl_i['passed'] else 'FAIL'} (center PF {pl_i['center_pf']:.3f}).

2. Dose-response: Spearman rho {rho_d:+.2f} between percentile and mean net return at ATR({ATR_LEN}).

3. Entry hour: {share_ok * 100:.0f}% of the tested entry hours keep a filtered PF >= {GATE['plateau_pf_min']}.

4. Ablation: configured mean net {mean_both:+.3f}% per Monday vs {mean_naked:+.3f}% for the naked Monday (in-sample).

5. Next Step: {'proceed to 03_Monday_Robustness_Testing.ipynb with the frozen parameters.' if ready else 'the official gate failed in-sample. Do NOT re-tune the parameters on this result: document it, and carry it to notebook 03 as a known weakness (the validation gate there repeats the plateau phase).'}
""")
```

    ================================================================================
    8. SUMMARY OF IN-SAMPLE PARAMETER STABILITY
    ================================================================================
    
    Key Findings:
    
    1. Plateau gate (full in-sample, official): FAIL - center PF 2.278, worst neighbor drop 48.4%,
       plateau no; 51% of 70 cells have PF >= 1.3; configured point ranks #12 by PF.
       Diagnostic inside the institutional era only: FAIL (center PF 2.278).
    
    2. Dose-response: Spearman rho +0.89 between percentile and mean net return at ATR(24).
    
    3. Entry hour: 100% of the tested entry hours keep a filtered PF >= 1.3.
    
    4. Ablation: configured mean net +1.570% per Monday vs +0.121% for the naked Monday (in-sample).
    
    5. Next Step: the official gate failed in-sample. Do NOT re-tune the parameters on this result: document it, and carry it to notebook 03 as a known weakness (the validation gate there repeats the plateau phase).
    

