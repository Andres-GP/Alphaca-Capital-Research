# 1. OVERNIGHT GAP TRADING — HYPOTHESIS DEFINITION & BASELINE BACKTEST
This notebook formulates the quantitative hypothesis and establishes the baseline backtest for the **Alphaca Overnight Gap** strategy on **intraday (5/15-min) bars**.

### 1.1 CORE QUANTITATIVE HYPOTHESIS
Dual-edge hypothesis (Trade it Simple):
* **MR — Mean Reversion** · `0.5% ≤ |gap| < 1.0%` · trade **AGAINST** the gap, target = 50–75% of the gap filled, stop = ATR(5)×0.8–1.2, EOD exit.
* **TF — Trend Following** · `1.0% ≤ |gap| ≤ 4.0%` · trade **WITH** the gap, target = 1.0–2.0× gap, stop = ATR(5)×1.0–1.5, EOD exit.

### 1.2 FROZEN STRATEGY RULES
| Rule Component | Specification |
| :--- | :--- |
| **Instrument** | Intraday bars (5 or 15 min), session 09:30–16:00 America/New_York |
| **Gap** | `gap% = Open[t] / Close[t-1] - 1` (session open vs. previous session close) |
| **Skip** | `|gap| < 0.5%`, `|gap| > 4.0%`, Fridays (optional), contaminated news day (not modelled) |
| **Opening candle** | First confirmation-TF bar of the session (`entry_tf_min`) |
| **Trigger** | Close of any later bar strictly beyond the opening candle high (long) / low (short) |
| **Entry window** | Entry bar between `09:40` and `11:00` (EST); fill at the **OPEN of the bar after the trigger** + slippage |
| **MR target** | Price level = session open ± `fill × |gap|` toward previous close |
| **TF target** | `entry ± mult × |gap|` |
| **Stop** | `entry ∓ stop_mult × ATR(5)[t-1]` (ATR known **before** the session open) |
| **Exit** | Stop, target (`time_exit = target_or_eod`) or last bar close (EOD). Same-bar stop+target → stop |
| **Trading Costs** | `slip_bps_per_side` per side, zero commission |
| **Position Sizing** | (a) **Capital**: 100% equity per trade<br>(b) **ATR Risk**: `risk_per_trade_pct` with `atr_stop_mult × ATR`, capped at `max_exposure` |

### 1.3 STRATEGY PARAMETERS


```python
VARIANT    = "v1_us500_gap"     # only base variants
STOP_LIMIT = 0.09
```

## 2. IMPORTS AND CONFIG


```python
import os, sys, json, importlib
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch, Rectangle
from matplotlib.lines import Line2D
from numpy.lib.stride_tricks import sliding_window_view
from IPython.display import display

# ---- Paths ----
def find_upwards(name, start=None, must_be_dir=True):
    """Sube desde start (cwd por defecto) y devuelve la primera carpeta que contiene `name`."""
    here = (start or Path.cwd()).resolve()
    for base in (here, *here.parents):
        target = base / name
        if target.is_dir() if must_be_dir else target.exists():
            return base
    raise FileNotFoundError(f"Could not find '{name}' walking up from {here}")

EDGE_DIR    = find_upwards('variants')
utils_path  = str(find_upwards('utils') / 'utils')
engine_path = str(EDGE_DIR)
engine_dir  = str(EDGE_DIR / 'overnight_gap')
for p in (utils_path, engine_path, engine_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

import overnight_gap_engine as eng
import variant_config
from variant_config import load_variant, save_json

importlib.reload(eng)          # reinicia ENGINE_DEFAULTS: nada se filtra entre variantes

variant_config.EDGE_DIR = EDGE_DIR
assert (variant_config.EDGE_DIR / "variants").is_dir(), f"Doesn't exist {variant_config.EDGE_DIR / 'variants'}"

# ---- Variant config: single source of truth ----
cfg        = load_variant(VARIANT)
eng.set_engine_defaults(**cfg.get("engine_defaults", {}))
P          = cfg["params"]
RUN_DIR    = cfg["run_dir"]
TICKER     = cfg["instrument"]["ticker"]
DATA_START = cfg["instrument"]["start"]
OOS_START  = cfg["oos_start_ts"]
SLIP_BPS   = P["slip_bps_per_side"]
SLIP       = SLIP_BPS / 10_000

# Una sola fuente de reglas: se reutiliza en TODAS las llamadas al motor.
RULES = dict(
    gap_min_trade=P["gap_min_trade"], gap_threshold=P["gap_threshold"], gap_max_tf=P["gap_max_tf"],
    entry_tf_min=P["entry_tf_min"], mr_fill_target=P["mr_fill_target"], tf_target_mult=P["tf_target_mult"],
    mr_stop_atr_mult=P["mr_stop_atr_mult"], tf_stop_atr_mult=P["tf_stop_atr_mult"],
    time_exit=P.get("time_exit", "target_or_eod"), skip_fridays=P.get("skip_fridays", True),
    slip_bps_per_side=SLIP_BPS,
    entry_window_start=P.get("entry_window_start", "09:40"), entry_window_end=P.get("entry_window_end", "11:00"),
    tf_hold_days=P.get("tf_hold_days", 0),
)
GAP_MIN, GAP_THR, GAP_MAX_TF = RULES["gap_min_trade"], RULES["gap_threshold"], RULES["gap_max_tf"]

# Aviso si el yaml todavía arrastra invert_strategy (ya no se usa)
if "invert_strategy" in P:
    print(f"⚠️  'invert_strategy' presente en yaml pero el motor actual no lo usa — se ignora.")

def run(intra, daily):
    return eng.run_gap_backtest(intra, daily, **RULES)

print("Imports complete.")
print(f"Loaded overnight_gap_engine from: {eng.__file__}")
print(f"Edge dir: {EDGE_DIR}")
print(f"Variant: {cfg['id']} | {TICKER} | gap∈[{GAP_MIN:g}%, {GAP_THR:g}%) MR | "
      f"[{GAP_THR:g}%, {GAP_MAX_TF:g}%] TF | exit={RULES['time_exit']} | tf={RULES['entry_tf_min']}m | {SLIP_BPS:g} bps/side")
print(f"Data source: {eng.ENGINE_DEFAULTS['data_source']} | swap: {eng.ENGINE_DEFAULTS['financing_bps_per_night']:g} bps/night")
print(f"Run folder: {RUN_DIR}")
```

    Imports complete.
    Loaded overnight_gap_engine from: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/notebooks/Overnight_Gap/overnight_gap_engine.py
    Edge dir: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/notebooks/Overnight_Gap
    Variant: v1_us500_gap | us500 | gap∈[1%, 1.5%) MR | [1.5%, 4%] TF | exit=target_or_eod | tf=15m | 3 bps/side
    Data source: csv_intraday | swap: 0 bps/night
    Run folder: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/notebooks/Overnight_Gap/runs/v1_us500_gap


## 3. LOAD DATA AND IN-SAMPLE / OUT-OF-SAMPLE


```python
intraday_raw = eng.load_data(TICKER, start=DATA_START)
daily_raw    = eng.session_daily(intraday_raw)

n_is = int((daily_raw.index < OOS_START).sum())
daily_is, daily_oos = daily_raw.iloc[:n_is].copy(), daily_raw.iloc[n_is:].copy()
assert len(daily_is) > 0 and len(daily_oos) > 0, "Check split.oos_start against the history of this ticker."
oos_start = daily_oos.index[0]

oos_start_dt = pd.Timestamp(OOS_START)
if intraday_raw.index.tz is not None:
    oos_start_dt = oos_start_dt.tz_localize(intraday_raw.index.tz)
intraday_is  = intraday_raw[intraday_raw.index <  oos_start_dt]
intraday_oos = intraday_raw[intraday_raw.index >= oos_start_dt]

print(intraday_raw.index.dayofweek.value_counts().sort_index().to_dict())
print(daily_raw.groupby(daily_raw.index.year).size().to_dict())
print("=" * 70)
print("DATA INGESTION & DATASET SPLIT")
print("=" * 70)
print(f"Intraday bars: {len(intraday_raw):,}  ({intraday_raw.index.min()} → {intraday_raw.index.max()})")
print(f"Total Prepared Sessions: {len(daily_raw):,} ({daily_raw.index.min():%Y-%m-%d} to {daily_raw.index.max():%Y-%m-%d})")
print(f"In-Sample (IS, {len(daily_is)/len(daily_raw)*100:.1f}%): {len(daily_is):,} sessions ({daily_is.index.min():%Y-%m-%d} to {daily_is.index.max():%Y-%m-%d})")
print(f"Out-of-Sample (OOS, {len(daily_oos)/len(daily_raw)*100:.1f}%): {len(daily_oos):,} sessions ({daily_oos.index.min():%Y-%m-%d} to {daily_oos.index.max():%Y-%m-%d})")
print("=" * 70)
daily_raw.head()
```

    {0: 33968, 1: 35523, 2: 35314, 3: 35161, 4: 34512}
    {2018: 252, 2019: 258, 2020: 259, 2021: 258, 2022: 258, 2023: 256, 2024: 259, 2025: 257, 2026: 210}
    ======================================================================
    DATA INGESTION & DATASET SPLIT
    ======================================================================
    Intraday bars: 174,478  (2018-01-02 09:30:00-05:00 → 2026-10-23 15:40:00-04:00)
    Total Prepared Sessions: 2,267 (2018-01-09 to 2026-10-23)
    In-Sample (IS, 45.3%): 1,027 sessions (2018-01-09 to 2021-12-31)
    Out-of-Sample (OOS, 54.7%): 1,240 sessions (2022-01-03 to 2026-10-23)
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
      <th>open</th>
      <th>high</th>
      <th>low</th>
      <th>close</th>
      <th>volume</th>
      <th>prev_close</th>
      <th>gap_pct</th>
      <th>atr5</th>
    </tr>
    <tr>
      <th>session_date</th>
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
      <th>2018-01-09</th>
      <td>2750.249</td>
      <td>2759.100</td>
      <td>2747.349</td>
      <td>2751.880</td>
      <td>14.613460</td>
      <td>2746.520</td>
      <td>0.135772</td>
      <td>15.173400</td>
    </tr>
    <tr>
      <th>2018-01-10</th>
      <td>2743.470</td>
      <td>2750.859</td>
      <td>2735.570</td>
      <td>2747.839</td>
      <td>11.484060</td>
      <td>2751.880</td>
      <td>-0.305609</td>
      <td>14.654720</td>
    </tr>
    <tr>
      <th>2018-01-11</th>
      <td>2753.269</td>
      <td>2767.320</td>
      <td>2751.770</td>
      <td>2767.320</td>
      <td>3.979380</td>
      <td>2747.839</td>
      <td>0.197610</td>
      <td>14.985776</td>
    </tr>
    <tr>
      <th>2018-01-12</th>
      <td>2770.389</td>
      <td>2787.640</td>
      <td>2769.139</td>
      <td>2785.889</td>
      <td>5.832207</td>
      <td>2767.320</td>
      <td>0.110902</td>
      <td>15.884821</td>
    </tr>
    <tr>
      <th>2018-01-15</th>
      <td>2792.650</td>
      <td>2795.149</td>
      <td>2791.649</td>
      <td>2793.710</td>
      <td>1.227259</td>
      <td>2785.889</td>
      <td>0.242687</td>
      <td>16.771857</td>
    </tr>
  </tbody>
</table>
</div>



## 4. BASELINE BACKTEST WITH FROZEN RULES


```python
# ---- Metrics ----
def sharpe(r):
    if len(r) < 2 or r.std(ddof=0) == 0: return 0.0
    return float(np.sqrt(252) * r.mean() / r.std(ddof=0))

def max_dd(eq):
    eq = np.asarray(eq, dtype=float)
    if len(eq) == 0: return 0.0
    pk = np.maximum.accumulate(eq)
    return float(((eq - pk) / pk).min())

def pf(t):
    if len(t) == 0: return 0.0
    p = t["pnl"].values
    g = p[p > 0].sum(); l = -p[p < 0].sum()
    return float(g / l) if l > 0 else np.inf

def as_atr(t):
    return t.assign(pnl=t["pnl_atr"], win=t["pnl_atr"] > 0)

# ---- Run frozen rules: Full / IS / OOS ----
trades_all = run(intraday_raw, daily_raw)
trades_is  = run(intraday_is,  daily_is)
trades_oos = run(intraday_oos, daily_oos)
assert len(trades_all) > 0, "The backtest produced 0 trades: check data, gap thresholds and entry window."

ret_cap_all = eng.daily_returns(daily_raw, trades_all, "capital"); ret_atr_all = eng.daily_returns(daily_raw, trades_all, "atr")
ret_cap_is  = eng.daily_returns(daily_is,  trades_is,  "capital"); ret_atr_is  = eng.daily_returns(daily_is,  trades_is,  "atr")
ret_cap_oos = eng.daily_returns(daily_oos, trades_oos, "capital"); ret_atr_oos = eng.daily_returns(daily_oos, trades_oos, "atr")
eq_cap_all, eq_atr_all = (1 + ret_cap_all).cumprod(), (1 + ret_atr_all).cumprod()

def format_perf_table(t, period, daily):
    rows = []
    for sizing, tt, key in (("100% Capital", t, "capital"), ("1% ATR Risk", as_atr(t), "atr")):
        ret = eng.daily_returns(daily, t, key)
        eq = (1 + ret).cumprod()
        rows.append({
            "Period": period, "Sizing": sizing, "Trades": len(tt),
            "Win Rate": f"{(tt['win'].mean()*100 if len(tt) else 0):.1f}%",
            "Profit Factor": f"{pf(tt):.3f}",
            "Expectancy": f"{(tt['pnl'].mean() if len(tt) else 0):.3f}%",
            "Total Return": f"{(eq.iloc[-1]-1)*100:.1f}%",
            "Sharpe": f"{sharpe(ret):.2f}",
            "Max Drawdown": f"{max_dd(eq)*100:.2f}%",
        })
    return pd.DataFrame(rows)

perf_table = pd.concat([
    format_perf_table(trades_is,  f"In-Sample ({daily_is.index[0].year}-{daily_is.index[-1].year})", daily_is),
    format_perf_table(trades_oos, f"Out-of-Sample ({daily_oos.index[0].year}-{daily_oos.index[-1].year})", daily_oos),
    format_perf_table(trades_all, f"Full Period ({daily_raw.index[0].year}-{daily_raw.index[-1].year})", daily_raw),
], ignore_index=True)

print("=" * 80)
print(f"PERFORMANCE SUMMARY (NET OF {SLIP_BPS:g} BPS SLIPPAGE PER SIDE)")
print("=" * 80)
display(perf_table)

# ---- Split by strategy (MR vs TF) and by exit reason ----
for label, t in (("ALL", trades_all), ("MR", trades_all[trades_all.strategy == "MR"]), ("TF", trades_all[trades_all.strategy == "TF"])):
    if len(t) == 0:
        print(f"{label}: 0 trades"); continue
    print(f"{label}: N={len(t)}, WR={t['win'].mean()*100:.1f}%, PF={pf(t):.3f}, E={t['pnl'].mean():.3f}%")
print("Exit reasons:", trades_all["reason"].value_counts().to_dict())
```

    ================================================================================
    PERFORMANCE SUMMARY (NET OF 3 BPS SLIPPAGE PER SIDE)
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
      <th>Period</th>
      <th>Sizing</th>
      <th>Trades</th>
      <th>Win Rate</th>
      <th>Profit Factor</th>
      <th>Expectancy</th>
      <th>Total Return</th>
      <th>Sharpe</th>
      <th>Max Drawdown</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>In-Sample (2018-2021)</td>
      <td>100% Capital</td>
      <td>33</td>
      <td>72.7%</td>
      <td>2.159</td>
      <td>0.280%</td>
      <td>9.5%</td>
      <td>0.80</td>
      <td>-5.43%</td>
    </tr>
    <tr>
      <th>1</th>
      <td>In-Sample (2018-2021)</td>
      <td>1% ATR Risk</td>
      <td>33</td>
      <td>72.7%</td>
      <td>1.560</td>
      <td>0.076%</td>
      <td>2.5%</td>
      <td>0.45</td>
      <td>-2.62%</td>
    </tr>
    <tr>
      <th>2</th>
      <td>Out-of-Sample (2022-2026)</td>
      <td>100% Capital</td>
      <td>47</td>
      <td>61.7%</td>
      <td>0.766</td>
      <td>-0.100%</td>
      <td>-4.9%</td>
      <td>-0.26</td>
      <td>-10.03%</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Out-of-Sample (2022-2026)</td>
      <td>1% ATR Risk</td>
      <td>47</td>
      <td>61.7%</td>
      <td>0.730</td>
      <td>-0.052%</td>
      <td>-2.5%</td>
      <td>-0.37</td>
      <td>-4.91%</td>
    </tr>
    <tr>
      <th>4</th>
      <td>Full Period (2018-2026)</td>
      <td>100% Capital</td>
      <td>80</td>
      <td>66.2%</td>
      <td>1.163</td>
      <td>0.057%</td>
      <td>4.2%</td>
      <td>0.15</td>
      <td>-10.03%</td>
    </tr>
    <tr>
      <th>5</th>
      <td>Full Period (2018-2026)</td>
      <td>1% ATR Risk</td>
      <td>80</td>
      <td>66.2%</td>
      <td>1.004</td>
      <td>0.001%</td>
      <td>-0.0%</td>
      <td>0.00</td>
      <td>-4.91%</td>
    </tr>
  </tbody>
</table>
</div>


    ALL: N=80, WR=66.2%, PF=1.163, E=0.057%
    MR: N=43, WR=67.4%, PF=1.240, E=0.046%
    TF: N=37, WR=64.9%, PF=1.131, E=0.070%
    Exit reasons: {'eod': 47, 'target': 27, 'stop': 6}



```python
# ---- Plot equity curves + price context ----
BG, PANEL, GRID, TXT, TXT2 = '#15171c', '#1b1e26', '#2a2d37', '#e8e9ec', '#9aa0ab'
split_label = f"OOS Split Date ({oos_start:%Y-%m-%d})"

fig, (ax1, ax2, ax3) = plt.subplots(
    3, 1, figsize=(14, 12), sharex=True, facecolor=BG,
    gridspec_kw={"height_ratios": [1.4, 1, 1]},
)
for ax in (ax1, ax2, ax3):
    ax.set_facecolor(PANEL); ax.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(colors=TXT2, labelsize=9)

# ---------------------------------------------------------------------------
# PANEL 1 — Price context (log) with trade markers
# ---------------------------------------------------------------------------
price_close = daily_raw["close"].astype(float)
price_high  = daily_raw["high"].astype(float)
price_low   = daily_raw["low"].astype(float)

ax1.fill_between(daily_raw.index, price_low, price_high,
                 color='#c0c0d0', alpha=0.10, lw=0, label='Daily High-Low')
ax1.plot(daily_raw.index, price_close, color='#c0c0d0', lw=1.2, label='Close', zorder=3)

# Trade entries: longs ▲ verde, shorts ▼ rojo, ubicados al close del día de la señal
if len(trades_all) > 0:
    td = pd.to_datetime(trades_all["session_date"]).values
    y_entries = daily_raw["close"].reindex(pd.to_datetime(trades_all["session_date"])).values
    longs_mask  = (trades_all["direction"] == "long").values
    shorts_mask = ~longs_mask

    ax1.scatter(td[longs_mask], y_entries[longs_mask],
                marker='^', s=26, color='#34d399', alpha=0.85, edgecolors='none',
                label=f'Long entries  (N={int(longs_mask.sum())})', zorder=4)
    ax1.scatter(td[shorts_mask], y_entries[shorts_mask],
                marker='v', s=26, color='#f87171', alpha=0.85, edgecolors='none',
                label=f'Short entries  (N={int(shorts_mask.sum())})', zorder=4)

ax1.set_yscale('log')
ax1.axvline(oos_start, color='#f5a524', ls='--', lw=1.2, label=split_label)

# Header stats: buy & hold vs strategy
bh_ret = (price_close.iloc[-1] / price_close.iloc[0] - 1) * 100
eq_atr_ret = (eq_atr_all.iloc[-1] - 1) * 100
ax1.text(
    0.015, 0.05,
    f"Buy & Hold: {bh_ret:+.1f}%    |    Strategy (ATR sizing): {eq_atr_ret:+.1f}%",
    transform=ax1.transAxes, color=TXT, fontsize=10, fontweight='bold',
    bbox=dict(boxstyle='round,pad=0.4', fc=PANEL, ec=GRID),
)

ax1.set_title(f'{TICKER} Price Context (log) — trade entries overlaid',
              color=TXT, fontweight='bold', fontsize=11, loc='left', pad=10)
ax1.set_ylabel('Price (log)', color=TXT2, fontsize=9)
ax1.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper left', ncol=5)

# ---------------------------------------------------------------------------
# PANEL 2 — Equity (Capital) + Price (normalized) on twin axis
# ---------------------------------------------------------------------------
ax2.plot(daily_raw.index, eq_cap_all, color='#34d399', lw=1.6,
         label='Equity (100% Capital)', zorder=3)
ax2.axvline(oos_start, color='#f5a524', ls='--', lw=1.2, label=split_label)
ax2.axhline(1.0, color=TXT2, ls=':', lw=0.7, alpha=0.6)
ax2.set_title(f'{TICKER} Overnight Gap — Equity vs. Price (Capital Sizing)',
              color=TXT, fontweight='bold', fontsize=11, loc='left', pad=10)
ax2.set_ylabel('Equity Multiplier', color='#34d399', fontsize=9)
ax2.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper left')

ax2b = ax2.twinx()
ax2b.plot(daily_raw.index, price_close / price_close.iloc[0],
          color='#9aa0ab', lw=1.0, alpha=0.55,
          label='Price / price[t0] (normalized)')
ax2b.set_ylabel('Price (normalized)', color='#9aa0ab', fontsize=9)
ax2b.tick_params(colors=TXT2, labelsize=9)
for s in ax2b.spines.values(): s.set_visible(False)
ax2b.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper right')

# ---------------------------------------------------------------------------
# PANEL 3 — Equity (ATR) + Price (normalized) on twin axis
# ---------------------------------------------------------------------------
ax3.plot(daily_raw.index, eq_atr_all, color='#5468ff', lw=1.6,
         label='Equity (1% ATR Risk)', zorder=3)
ax3.axvline(oos_start, color='#f5a524', ls='--', lw=1.2, label=split_label)
ax3.axhline(1.0, color=TXT2, ls=':', lw=0.7, alpha=0.6)
ax3.set_title(f'{TICKER} Overnight Gap — Equity vs. Price (1% ATR Risk Sizing)',
              color=TXT, fontweight='bold', fontsize=11, loc='left', pad=10)
ax3.set_ylabel('Equity Multiplier', color='#5468ff', fontsize=9)
ax3.set_xlabel('Date', color=TXT2, fontsize=9)
ax3.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper left')

ax3b = ax3.twinx()
ax3b.plot(daily_raw.index, price_close / price_close.iloc[0],
          color='#9aa0ab', lw=1.0, alpha=0.55,
          label='Price / price[t0] (normalized)')
ax3b.set_ylabel('Price (normalized)', color='#9aa0ab', fontsize=9)
ax3b.tick_params(colors=TXT2, labelsize=9)
for s in ax3b.spines.values(): s.set_visible(False)
ax3b.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper right')

plt.tight_layout()
plt.show()
```


    
![png](01_Gap_Hypothesis_Definition_files/01_Gap_Hypothesis_Definition_8_0.png)
    



```python
# ============================================================================
# DIAGNÓSTICO — ¿Por qué la estrategia "muere" en 2025?
# Compara distribución de gaps + fill/continuation rate: pre-2025 vs 2025
# ============================================================================
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

BG, PANEL, GRID, TXT, TXT2 = '#15171c', '#1b1e26', '#2a2d37', '#e8e9ec', '#9aa0ab'
GREEN, RED, AMBER, BLUE = '#34d399', '#f87171', '#f5a524', '#5468ff'

# ---------------------------------------------------------------------------
# 1) Recolectar métricas intradía por sesión
# ---------------------------------------------------------------------------
# Para cada sesión: fill% (qué tanto del gap se recorrió intradía hacia prev_close)
#                   extension% (qué tanto se movió más allá del open en dirección del gap)

day_key = daily_raw.index.values
intraday_dates = intraday_raw.index.normalize().tz_localize(None) if intraday_raw.index.tz is not None \
                 else intraday_raw.index.normalize()
intraday_dates_arr = intraday_dates.values.astype('datetime64[ns]')

rows = []
for sd, r in daily_raw.iterrows():
    sd_ns = np.datetime64(sd)
    mask = intraday_dates_arr == sd_ns
    if mask.sum() < 5:
        continue
    day_bars = intraday_raw.iloc[mask]
    if len(day_bars) == 0:
        continue
    o, h, l, c = r["open"], r["high"], r["low"], r["close"]
    pc = r["prev_close"]
    gap = r["gap_pct"]

    if pd.isna(pc) or gap == 0:
        continue

    gap_abs = abs(gap)
    direction = 1 if gap > 0 else -1
    gap_dist = abs(o - pc)

    # Fill: ¿el precio cruzó el prev_close durante la sesión?
    #   gap up  → necesita low <= prev_close
    #   gap down→ necesita high >= prev_close
    filled = (l <= pc) if direction == 1 else (h >= pc)

    # Cuánto % del gap se rellenó intradía (0–100%)
    if direction == 1:
        best_fill = max(0.0, (o - l) / gap_dist) if gap_dist > 0 else 0.0
    else:
        best_fill = max(0.0, (h - o) / gap_dist) if gap_dist > 0 else 0.0
    fill_pct = min(best_fill * 100, 200)  # cap a 200% (por si supera)

    # Extensión: ¿el cierre quedó en dirección del gap?
    continuation_close = (c > o) if direction == 1 else (c < o)
    ext_pct = ((c - o) / o * 100) * direction  # positivo = continuó, negativo = revirtió
    # Extensión máxima intradía
    best_ext = ((h - o) if direction == 1 else (o - l)) / o * 100

    rows.append({
        "session_date": sd,
        "year": sd.year,
        "gap_pct": gap,
        "gap_abs": gap_abs,
        "direction": "up" if gap > 0 else "down",
        "filled": filled,
        "fill_pct": fill_pct,
        "ext_pct": ext_pct,
        "best_ext_pct": best_ext,
        "continuation_close": continuation_close,
    })

gap_df = pd.DataFrame(rows)
if len(gap_df) == 0:
    print("⚠️  No se pudo reconstruir intraday por sesión (¿timezone mismatch?).")
else:
    # Bin tipo doc
    def _bin(x):
        if x < 0.5:  return "<0.5%"
        if x < 1.0:  return "0.5-1%"
        if x < 2.0:  return "1-2%"
        if x < 3.0:  return "2-3%"
        if x < 4.0:  return "3-4%"
        return "≥4%"
    gap_df["bin"] = gap_df["gap_abs"].apply(_bin)

    # ---------------------------------------------------------------------------
    # 2) Tabla por año
    # ---------------------------------------------------------------------------
    print("=" * 100)
    print("POR AÑO — frecuencia + comportamiento intradía")
    print("=" * 100)

    by_year = gap_df.groupby("year").agg(
        sesiones=("session_date", "count"),
        gap_mean=("gap_abs", "mean"),
        gap_med=("gap_abs", "median"),
        gap_p75=("gap_abs", lambda s: np.percentile(s, 75)),
        gap_p95=("gap_abs", lambda s: np.percentile(s, 95)),
    ).round(3)
    by_year["califican_min"] = gap_df[gap_df["gap_abs"] >= GAP_MIN].groupby("year").size()
    by_year["califican_%"] = (by_year["califican_min"] / by_year["sesiones"] * 100).round(1)
    by_year["fill_rate_%"] = gap_df.groupby("year")["filled"].mean().mul(100).round(1)
    by_year["cont_rate_%"] = gap_df.groupby("year")["continuation_close"].mean().mul(100).round(1)
    by_year["fill_pct_med"] = gap_df.groupby("year")["fill_pct"].median().round(1)
    by_year["ext_med_%"]    = gap_df.groupby("year")["ext_pct"].median().round(3)

    display(by_year)

    # ---------------------------------------------------------------------------
    # 3) Comparación directa 2025 vs pre-2025
    # ---------------------------------------------------------------------------
    pre = gap_df[gap_df["year"] < 2025]
    y25 = gap_df[gap_df["year"] == 2025]

    if len(y25) == 0:
        print("\n⚠️  No hay datos de 2025 en el rango.")
    else:
        print("\n" + "=" * 100)
        print("PRE-2025 vs 2025 — resumen global")
        print("=" * 100)
        comp = pd.DataFrame({
            "Pre-2025": {
                "Sesiones": len(pre),
                "|gap| medio %": f"{pre['gap_abs'].mean():.3f}",
                "|gap| mediana %": f"{pre['gap_abs'].median():.3f}",
                "Sesiones que califican": f"{(pre['gap_abs'] >= GAP_MIN).sum()} "
                                          f"({(pre['gap_abs'] >= GAP_MIN).mean()*100:.1f}%)",
                "Fill rate %": f"{pre['filled'].mean()*100:.1f}",
                "Continuation rate %": f"{pre['continuation_close'].mean()*100:.1f}",
                "Fill % mediano": f"{pre['fill_pct'].median():.1f}",
                "Extensión mediana %": f"{pre['ext_pct'].median():+.3f}",
            },
            "2025": {
                "Sesiones": len(y25),
                "|gap| medio %": f"{y25['gap_abs'].mean():.3f}",
                "|gap| mediana %": f"{y25['gap_abs'].median():.3f}",
                "Sesiones que califican": f"{(y25['gap_abs'] >= GAP_MIN).sum()} "
                                          f"({(y25['gap_abs'] >= GAP_MIN).mean()*100:.1f}%)",
                "Fill rate %": f"{y25['filled'].mean()*100:.1f}",
                "Continuation rate %": f"{y25['continuation_close'].mean()*100:.1f}",
                "Fill % mediano": f"{y25['fill_pct'].median():.1f}",
                "Extensión mediana %": f"{y25['ext_pct'].median():+.3f}",
            },
        })
        display(comp)

        # Diagnóstico automático
        d_fill = y25['filled'].mean() - pre['filled'].mean()
        d_cont = y25['continuation_close'].mean() - pre['continuation_close'].mean()
        d_ses  = (y25['gap_abs'] >= GAP_MIN).mean() - (pre['gap_abs'] >= GAP_MIN).mean()
        print("\n📊 Diagnóstico:")
        print(f"  Cambio en frecuencia de gaps que califican: {d_ses*100:+.1f} pp")
        print(f"  Cambio en fill rate (afecta MR):             {d_fill*100:+.1f} pp")
        print(f"  Cambio en continuation rate (afecta TF):     {d_cont*100:+.1f} pp")

        # Veredicto
        issues = []
        if d_ses < -0.05:  issues.append("menos gaps califican → la estrategia tiene menos oportunidades")
        if d_fill < -0.05: issues.append("fill rate cae → MR pierde su edge")
        if d_cont < -0.05: issues.append("continuation rate cae → TF pierde su edge")
        if d_fill > 0.05 and d_cont > 0.05:
            issues.append("ambos suben → raro, revisar cálculos")
        if not issues:
            issues.append("sin cambios estructurales obvios — el problema podría ser stops/targets o régimen")

        for i, msg in enumerate(issues, 1):
            print(f"  ⚠️  {i}. {msg}")

    # ---------------------------------------------------------------------------
    # 4) Fill rate por bin × periodo (crítico: compara contra la tabla del doc)
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("FILL RATE por bin — pre-2025 vs 2025 (comparar contra tabla del doc)")
    print("=" * 100)

    bin_order = ["<0.5%", "0.5-1%", "1-2%", "2-3%", "3-4%", "≥4%"]
    rows_bin = []
    for b in bin_order:
        s_pre = pre[pre["bin"] == b]
        s_25  = y25[y25["bin"] == b]
        rows_bin.append({
            "Bin": b,
            "N pre": len(s_pre),
            "N 2025": len(s_25),
            "Fill pre %": f"{s_pre['filled'].mean()*100:.0f}" if len(s_pre) else "—",
            "Fill 2025 %": f"{s_25['filled'].mean()*100:.0f}" if len(s_25) else "—",
            "Δ fill (pp)": (f"{(s_25['filled'].mean() - s_pre['filled'].mean())*100:+.0f}"
                            if len(s_pre) and len(s_25) else "—"),
            "Cont pre %": f"{s_pre['continuation_close'].mean()*100:.0f}" if len(s_pre) else "—",
            "Cont 2025 %": f"{s_25['continuation_close'].mean()*100:.0f}" if len(s_25) else "—",
            "Δ cont (pp)": (f"{(s_25['continuation_close'].mean() - s_pre['continuation_close'].mean())*100:+.0f}"
                            if len(s_pre) and len(s_25) else "—"),
        })
    display(pd.DataFrame(rows_bin))

    # ---------------------------------------------------------------------------
    # 5) Plots
    # ---------------------------------------------------------------------------
    years_plot = sorted(gap_df["year"].unique())
    colors_bar = [BLUE if y < 2025 else RED for y in years_plot]

    fig = plt.figure(figsize=(14, 11), facecolor=BG)
    gs = GridSpec(3, 2, height_ratios=[1, 1, 1.1], hspace=0.42, wspace=0.22, figure=fig)

    def _style(ax, title, ylabel=None, xlabel=None):
        ax.set_facecolor(PANEL)
        for s in ax.spines.values(): s.set_visible(False)
        ax.tick_params(colors=TXT2, labelsize=9)
        ax.grid(True, color=GRID, linewidth=0.8, alpha=0.9); ax.set_axisbelow(True)
        ax.set_title(title, color=TXT, fontweight='bold', fontsize=10, loc='left', pad=8)
        if ylabel: ax.set_ylabel(ylabel, color=TXT2, fontsize=9)
        if xlabel: ax.set_xlabel(xlabel, color=TXT2, fontsize=9)

    # 5.1 |gap| mediano y p95 por año
    ax = fig.add_subplot(gs[0, :])
    _style(ax, "Evolución del |gap| por año", "|gap| %", "Año")
    med = gap_df.groupby("year")["gap_abs"].median()
    p75 = gap_df.groupby("year")["gap_abs"].quantile(0.75)
    p95 = gap_df.groupby("year")["gap_abs"].quantile(0.95)
    ax.plot(med.index, med.values, marker='o', color=GREEN, lw=1.8, label="mediana")
    ax.plot(p75.index, p75.values, marker='s', color=AMBER, lw=1.4, label="p75")
    ax.plot(p95.index, p95.values, marker='^', color=RED, lw=1.4, label="p95")
    ax.axvline(2024.5, color=TXT2, ls=':', lw=1.2)
    ax.axhline(GAP_MIN, color=TXT2, ls='--', lw=0.9, alpha=0.6, label=f"gap_min={GAP_MIN}%")
    ax.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper left', ncol=4)
    ax.set_xticks(years_plot)

    # 5.2 % sesiones que califican por año
    ax = fig.add_subplot(gs[1, 0])
    _style(ax, f"% de sesiones con |gap| ≥ {GAP_MIN}%", "%", "Año")
    qual = gap_df.groupby("year").apply(lambda g: (g["gap_abs"] >= GAP_MIN).mean() * 100)
    bars = ax.bar(qual.index, qual.values, color=colors_bar, alpha=0.85, width=0.7)
    for b, v in zip(bars, qual.values):
        ax.text(b.get_x() + b.get_width()/2, v, f"{v:.1f}",
                ha='center', va='bottom', fontsize=8, color=TXT)
    ax.set_xticks(years_plot)

    # 5.3 Fill rate por año
    ax = fig.add_subplot(gs[1, 1])
    _style(ax, "Fill rate por año (¿el gap se cierra?)", "%", "Año")
    fill_y = gap_df.groupby("year")["filled"].mean() * 100
    cont_y = gap_df.groupby("year")["continuation_close"].mean() * 100
    ax.plot(fill_y.index, fill_y.values, marker='o', color=GREEN, lw=1.8, label="Fill (MR)")
    ax.plot(cont_y.index, cont_y.values, marker='s', color=BLUE, lw=1.8, label="Continuación (TF)")
    ax.axhline(50, color=TXT2, ls='--', lw=0.8, alpha=0.5)
    ax.axvline(2024.5, color=RED, ls=':', lw=1.2)
    ax.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='best')
    ax.set_xticks(years_plot)

    # 5.4 Distribución de |gap| — pre-2025 vs 2025 (histograma superpuesto)
    ax = fig.add_subplot(gs[2, 0])
    _style(ax, "Distribución |gap| — pre-2025 vs 2025", "Densidad", "|gap| %")
    bins = np.linspace(0, 4, 41)
    ax.hist(pre["gap_abs"].clip(upper=4), bins=bins, density=True,
            alpha=0.55, color=BLUE, label=f"pre-2025 (N={len(pre)})")
    ax.hist(y25["gap_abs"].clip(upper=4), bins=bins, density=True,
            alpha=0.55, color=RED, label=f"2025 (N={len(y25)})")
    ax.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper right')
    ax.axvline(GAP_MIN, color=TXT2, ls='--', lw=0.9, alpha=0.6)

    # 5.5 Fill rate por bin — comparativa de barras
    ax = fig.add_subplot(gs[2, 1])
    _style(ax, "Fill rate por bin — pre-2025 vs 2025", "%", "Bin de |gap|")
    x = np.arange(len(bin_order))
    w = 0.38
    fill_pre = [pre[pre["bin"] == b]["filled"].mean() * 100 if (pre["bin"] == b).any() else 0
                for b in bin_order]
    fill_25  = [y25[y25["bin"] == b]["filled"].mean() * 100 if (y25["bin"] == b).any() else 0
                for b in bin_order]
    n_pre    = [(pre["bin"] == b).sum() for b in bin_order]
    n_25     = [(y25["bin"] == b).sum() for b in bin_order]

    ax.bar(x - w/2, fill_pre, w, color=BLUE, alpha=0.85,
           label=f"pre-2025 (N={sum(n_pre)})")
    ax.bar(x + w/2, fill_25,  w, color=RED,  alpha=0.85,
           label=f"2025 (N={sum(n_25)})")
    ax.set_xticks(x); ax.set_xticklabels(bin_order, rotation=30, color=TXT2, fontsize=9)
    ax.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper right')
    for i, b in enumerate(bin_order):
        ax.text(i - w/2, fill_pre[i] + 1, f"{n_pre[i]}", ha='center', fontsize=7, color=TXT2)
        ax.text(i + w/2, fill_25[i] + 1, f"{n_25[i]}",  ha='center', fontsize=7, color=TXT2)

    fig.suptitle(f"{TICKER} — Diagnóstico de degradación de gaps (pre-2025 vs 2025)",
                 color=TXT, fontweight='bold', fontsize=13, x=0.02, ha='left', y=0.995)
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    plt.show()
```

    ====================================================================================================
    POR AÑO — frecuencia + comportamiento intradía
    ====================================================================================================



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
      <th>sesiones</th>
      <th>gap_mean</th>
      <th>gap_med</th>
      <th>gap_p75</th>
      <th>gap_p95</th>
      <th>califican_min</th>
      <th>califican_%</th>
      <th>fill_rate_%</th>
      <th>cont_rate_%</th>
      <th>fill_pct_med</th>
      <th>ext_med_%</th>
    </tr>
    <tr>
      <th>year</th>
      <th></th>
      <th></th>
      <th></th>
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
      <th>2018</th>
      <td>252</td>
      <td>0.394</td>
      <td>0.296</td>
      <td>0.526</td>
      <td>1.302</td>
      <td>18</td>
      <td>7.1</td>
      <td>57.1</td>
      <td>49.2</td>
      <td>138.2</td>
      <td>-0.004</td>
    </tr>
    <tr>
      <th>2019</th>
      <td>257</td>
      <td>0.361</td>
      <td>0.264</td>
      <td>0.521</td>
      <td>0.975</td>
      <td>12</td>
      <td>4.7</td>
      <td>56.4</td>
      <td>52.1</td>
      <td>125.7</td>
      <td>0.020</td>
    </tr>
    <tr>
      <th>2020</th>
      <td>259</td>
      <td>0.900</td>
      <td>0.489</td>
      <td>1.004</td>
      <td>3.147</td>
      <td>66</td>
      <td>25.5</td>
      <td>50.2</td>
      <td>50.6</td>
      <td>100.1</td>
      <td>0.024</td>
    </tr>
    <tr>
      <th>2021</th>
      <td>258</td>
      <td>0.354</td>
      <td>0.278</td>
      <td>0.482</td>
      <td>0.963</td>
      <td>13</td>
      <td>5.0</td>
      <td>56.2</td>
      <td>53.9</td>
      <td>127.8</td>
      <td>0.040</td>
    </tr>
    <tr>
      <th>2022</th>
      <td>258</td>
      <td>0.638</td>
      <td>0.489</td>
      <td>0.913</td>
      <td>1.563</td>
      <td>54</td>
      <td>20.9</td>
      <td>62.4</td>
      <td>53.5</td>
      <td>169.8</td>
      <td>0.101</td>
    </tr>
    <tr>
      <th>2023</th>
      <td>256</td>
      <td>0.366</td>
      <td>0.272</td>
      <td>0.525</td>
      <td>0.889</td>
      <td>9</td>
      <td>3.5</td>
      <td>61.3</td>
      <td>48.0</td>
      <td>152.2</td>
      <td>-0.039</td>
    </tr>
    <tr>
      <th>2024</th>
      <td>259</td>
      <td>0.344</td>
      <td>0.239</td>
      <td>0.456</td>
      <td>1.028</td>
      <td>14</td>
      <td>5.4</td>
      <td>62.9</td>
      <td>48.6</td>
      <td>147.1</td>
      <td>-0.030</td>
    </tr>
    <tr>
      <th>2025</th>
      <td>257</td>
      <td>0.467</td>
      <td>0.292</td>
      <td>0.576</td>
      <td>1.400</td>
      <td>32</td>
      <td>12.5</td>
      <td>62.3</td>
      <td>45.9</td>
      <td>159.6</td>
      <td>-0.048</td>
    </tr>
    <tr>
      <th>2026</th>
      <td>210</td>
      <td>0.406</td>
      <td>0.309</td>
      <td>0.553</td>
      <td>1.133</td>
      <td>14</td>
      <td>6.7</td>
      <td>52.4</td>
      <td>48.1</td>
      <td>120.7</td>
      <td>-0.028</td>
    </tr>
  </tbody>
</table>
</div>


    
    ====================================================================================================
    PRE-2025 vs 2025 — resumen global
    ====================================================================================================



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
      <th>Pre-2025</th>
      <th>2025</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>Sesiones</th>
      <td>1799</td>
      <td>257</td>
    </tr>
    <tr>
      <th>|gap| medio %</th>
      <td>0.480</td>
      <td>0.467</td>
    </tr>
    <tr>
      <th>|gap| mediana %</th>
      <td>0.310</td>
      <td>0.292</td>
    </tr>
    <tr>
      <th>Sesiones que califican</th>
      <td>186 (10.3%)</td>
      <td>32 (12.5%)</td>
    </tr>
    <tr>
      <th>Fill rate %</th>
      <td>58.1</td>
      <td>62.3</td>
    </tr>
    <tr>
      <th>Continuation rate %</th>
      <td>50.9</td>
      <td>45.9</td>
    </tr>
    <tr>
      <th>Fill % mediano</th>
      <td>135.6</td>
      <td>159.6</td>
    </tr>
    <tr>
      <th>Extensión mediana %</th>
      <td>+0.012</td>
      <td>-0.048</td>
    </tr>
  </tbody>
</table>
</div>


    
    📊 Diagnóstico:
      Cambio en frecuencia de gaps que califican: +2.1 pp
      Cambio en fill rate (afecta MR):             +4.2 pp
      Cambio en continuation rate (afecta TF):     -4.9 pp
      ⚠️  1. sin cambios estructurales obvios — el problema podría ser stops/targets o régimen
    
    ====================================================================================================
    FILL RATE por bin — pre-2025 vs 2025 (comparar contra tabla del doc)
    ====================================================================================================



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
      <th>Bin</th>
      <th>N pre</th>
      <th>N 2025</th>
      <th>Fill pre %</th>
      <th>Fill 2025 %</th>
      <th>Δ fill (pp)</th>
      <th>Cont pre %</th>
      <th>Cont 2025 %</th>
      <th>Δ cont (pp)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>&lt;0.5%</td>
      <td>1227</td>
      <td>181</td>
      <td>71</td>
      <td>75</td>
      <td>+4</td>
      <td>49</td>
      <td>45</td>
      <td>-3</td>
    </tr>
    <tr>
      <th>1</th>
      <td>0.5-1%</td>
      <td>386</td>
      <td>44</td>
      <td>33</td>
      <td>36</td>
      <td>+3</td>
      <td>56</td>
      <td>48</td>
      <td>-8</td>
    </tr>
    <tr>
      <th>2</th>
      <td>1-2%</td>
      <td>149</td>
      <td>25</td>
      <td>23</td>
      <td>24</td>
      <td>+1</td>
      <td>54</td>
      <td>48</td>
      <td>-6</td>
    </tr>
    <tr>
      <th>3</th>
      <td>2-3%</td>
      <td>20</td>
      <td>3</td>
      <td>25</td>
      <td>0</td>
      <td>-25</td>
      <td>60</td>
      <td>33</td>
      <td>-27</td>
    </tr>
    <tr>
      <th>4</th>
      <td>3-4%</td>
      <td>10</td>
      <td>4</td>
      <td>10</td>
      <td>50</td>
      <td>+40</td>
      <td>50</td>
      <td>50</td>
      <td>+0</td>
    </tr>
    <tr>
      <th>5</th>
      <td>≥4%</td>
      <td>7</td>
      <td>0</td>
      <td>0</td>
      <td>—</td>
      <td>—</td>
      <td>43</td>
      <td>—</td>
      <td>—</td>
    </tr>
  </tbody>
</table>
</div>


    /var/folders/08/5tz1wm0s7w38yfr1g_6f_9n40000gn/T/ipykernel_38356/3655862670.py:288: UserWarning: This figure includes Axes that are not compatible with tight_layout, so results might be incorrect.
      plt.tight_layout(rect=[0, 0, 1, 0.98])



    
![png](01_Gap_Hypothesis_Definition_files/01_Gap_Hypothesis_Definition_9_7.png)
    



```python
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from numpy.lib.stride_tricks import sliding_window_view
from pathlib import Path

# ============================================================================
# CONFIG DEL MAPA 3D (grid ancho para ver el panorama completo)
# ============================================================================
LIMIT      = STOP_LIMIT               # 9% por default (STOP_LIMIT del notebook)
LIMIT_PCT  = LIMIT * 100
STAGE_DAYS = 252
GATE       = "stage"                  # "stage" o "trailing"

# Rango amplio — incluye gaps que en la práctica casi nunca se dan, para ver
# el comportamiento estructural del edge en todo el mapa.
GAP_MIN_VALUES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
GAP_THR_VALUES = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0]

# Todo lo que NO varía (viene de RULES)
FIXED = {k: v for k, v in RULES.items() if k not in ("gap_min_trade", "gap_threshold")}

# ============================================================================
# SWEEP
# ============================================================================
n_grid  = pd.DataFrame(index=GAP_THR_VALUES, columns=GAP_MIN_VALUES, dtype=float)
pf_grid = pd.DataFrame(index=GAP_THR_VALUES, columns=GAP_MIN_VALUES, dtype=float)
dd_grid = pd.DataFrame(index=GAP_THR_VALUES, columns=GAP_MIN_VALUES, dtype=float)
st_grid = pd.DataFrame(index=GAP_THR_VALUES, columns=GAP_MIN_VALUES, dtype=float)

oos_start_naive = (pd.Timestamp(oos_start).tz_localize(None)
                   if pd.Timestamp(oos_start).tz is not None else pd.Timestamp(oos_start))

n_combos = len(GAP_MIN_VALUES) * len(GAP_THR_VALUES)
print(f"Sweeping {n_combos} combos (gap_min_trade × gap_threshold) — esto puede tardar unos minutos...")

for i, gm in enumerate(GAP_MIN_VALUES):
    for gt in GAP_THR_VALUES:
        p = {**FIXED, "gap_min_trade": gm, "gap_threshold": gt}

        # Una sola pasada sobre el periodo completo
        t_full = eng.run_gap_backtest(intraday_raw, daily_raw, **p)
        n_grid.loc[gt, gm] = len(t_full)

        if len(t_full) == 0:
            continue

        # PF in-sample (filtramos los trades del periodo IS)
        sd = pd.to_datetime(t_full["session_date"])
        t_is = t_full[sd < oos_start_naive]
        if len(t_is) > 0:
            pos = t_is["pnl"].values
            g_pos = pos[pos > 0].sum(); l = -pos[pos < 0].sum()
            pf_grid.loc[gt, gm] = g_pos / l if l > 0 else np.inf

        # MaxDD y worst stage loss sobre full period (ATR sizing)
        ret = eng.daily_returns(daily_raw, t_full, sizing="atr").astype(float)
        eq = (1 + ret).cumprod()
        dd_grid.loc[gt, gm] = 100 * float((eq / eq.cummax() - 1).min())
        if len(ret) >= STAGE_DAYS:
            w = sliding_window_view(ret.values, STAGE_DAYS)
            st_grid.loc[gt, gm] = 100 * float(np.cumprod(1 + w, axis=1).min() - 1)

print(f"Done. Trades range: {int(n_grid.min().min())} – {int(n_grid.max().max())}")
print(f"PF range: {float(pf_grid.min().min()):.2f} – {float(pf_grid.max().max()):.2f}")

# ============================================================================
# PLOTLY 3D
# ============================================================================
def _gate():
    dd_, st_ = dd_grid.astype(float), st_grid.astype(float)
    return st_.fillna(dd_) if GATE == "stage" else dd_

colorscale   = [[0.00, "#b5452f"], [0.25, "#e8a46a"], [0.50, "#f4e79a"],
                [0.75, "#8fd19e"], [1.00, "#2f7d55"]]
margin_scale = [[0.00, "#b5452f"], [0.45, "#e8704f"], [0.50, "#f5a524"],
                [0.55, "#8fd19e"], [1.00, "#34d399"]]

g      = _gate()
margin = g + LIMIT_PCT
ok     = (g >= -LIMIT_PCT) & g.notna()
bad    = (g <  -LIMIT_PCT) & g.notna()
verdict = np.where(ok.values, "PASS", np.where(bad.values, "FAIL", "n/a"))

pf_vals = pf_grid.astype(float).replace(np.inf, np.nan)
amax = max(float(np.nanmax(np.abs(margin.values))), 1.0)
z_floor = min(1.0, float(np.nanmin(pf_vals.values))) - 0.35 if pf_vals.notna().any().any() else 0.5
z_top   = float(np.nanmax(pf_vals.values)) + 0.25 if pf_vals.notna().any().any() else 3.0

fig = go.Figure()

# 1) Superficie PF (in-sample)
cd = np.dstack([n_grid.values, dd_grid.values, margin.values, st_grid.values])
fig.add_trace(go.Surface(
    x=GAP_MIN_VALUES, y=GAP_THR_VALUES, z=pf_vals.values, customdata=cd, text=verdict,
    colorscale=colorscale, cmin=1.0, cmax=3.0,
    colorbar=dict(title="PF<br>(IS)", len=0.42, y=0.80, x=0.93, thickness=14),
    hovertemplate=("gap_min %{x}%<br>gap_thr %{y}%<br>PF %{z:.2f}"
                   "<br>Trades %{customdata[0]:.0f}"
                   "<br>MaxDD %{customdata[1]:.1f}%"
                   "<br>Worst stage %{customdata[3]:.1f}%"
                   f"<br>Limit -{LIMIT_PCT:.0f}%: " + "%{text} (%{customdata[2]:+.1f} pp)<extra></extra>"),
))

# 2) Floor map
fig.add_trace(go.Surface(
    x=GAP_MIN_VALUES, y=GAP_THR_VALUES, z=np.full(pf_vals.shape, z_floor),
    surfacecolor=margin.values, customdata=cd, text=verdict,
    colorscale=margin_scale, cmin=-amax, cmax=amax, opacity=0.95,
    colorbar=dict(title=f"Margin to<br>-{LIMIT_PCT:.0f}% (pp)", len=0.42, y=0.30, x=0.93, thickness=14),
    lighting=dict(ambient=1.0, diffuse=0.0, specular=0.0),
    hovertemplate=("FLOOR · gap_min %{x}% · gap_thr %{y}%"
                   "<br>MaxDD %{customdata[1]:.1f}%"
                   "<br>Worst stage %{customdata[3]:.1f}%"
                   f"<br>Limit -{LIMIT_PCT:.0f}%: " + "%{text} (%{customdata[2]:+.1f} pp)<extra></extra>"),
))

# 3) Markers pass/fail sobre la superficie
X, Y = np.meshgrid(GAP_MIN_VALUES, GAP_THR_VALUES)
for mask, name, color, symbol in (
    (ok,  f"Passes -{LIMIT_PCT:.0f}% (full)", "#34d399", "diamond"),
    (bad, f"Breaches -{LIMIT_PCT:.0f}% (full)", "#f87171", "x"),
):
    m = mask.values & pf_vals.notna().values
    fig.add_trace(go.Scatter3d(
        x=X[m], y=Y[m], z=pf_vals.values[m] + 0.04, mode="markers", name=name,
        marker=dict(size=4, color=color, symbol=symbol, line=dict(width=0)),
        hovertemplate=f"{name}<br>gap_min %{{x}}% · gap_thr %{{y}}%<extra></extra>",
    ))

# 4) Drop lines para los que pasan
m = ok.values & pf_vals.notna().values
xs, ys, zs = [], [], []
for xv, yv, zv in zip(X[m], Y[m], pf_vals.values[m]):
    xs += [xv, xv, None]; ys += [yv, yv, None]; zs += [zv, z_floor, None]
fig.add_trace(go.Scatter3d(
    x=xs, y=ys, z=zs, mode="lines", line=dict(color="rgba(52,211,153,0.35)", width=2),
    hoverinfo="skip", showlegend=False,
))

# 5) Chosen config
c_gm = float(RULES["gap_min_trade"])
c_gt = float(RULES["gap_threshold"])
if c_gm in GAP_MIN_VALUES and c_gt in GAP_THR_VALUES:
    c_dd  = float(g.loc[c_gt, c_gm])
    c_ok  = (not np.isnan(c_dd)) and c_dd >= -LIMIT_PCT
    fig.add_trace(go.Scatter3d(
        x=[c_gm], y=[c_gt], z=[float(pf_vals.loc[c_gt, c_gm]) + 0.08],
        mode="markers+text",
        text=[f"chosen {'✓' if c_ok else '✗'}"], textposition="top center",
        textfont=dict(color="#34d399" if c_ok else "#f87171", size=13),
        marker=dict(size=7, color="white",
                    line=dict(color="#34d399" if c_ok else "#f87171", width=3)),
        showlegend=False,
        hovertemplate=f"Chosen: gap_min={c_gm}%, gap_thr={c_gt}%<br>{GATE} loss {c_dd:.2f}% vs -{LIMIT_PCT:.0f}%<extra></extra>",
    ))
else:
    print(f"⚠️  Chosen config (gm={c_gm}, gt={c_gt}) NOT on grid — marker skipped. "
          f"Ajusta GAP_MIN_VALUES / GAP_THR_VALUES para incluirla.")

n_ok, n_tot = int(ok.values.sum()), int(g.notna().values.sum())
title = (f"{cfg['id']} · PF in-sample · {n_ok}/{n_tot} cells keep full-period {GATE} loss "
         f"within -{LIMIT_PCT:.0f}%  ·  grid {len(GAP_MIN_VALUES)}×{len(GAP_THR_VALUES)}")

fig.update_layout(
    template="plotly_dark", paper_bgcolor="#15171c", height=750,
    title=dict(text=title, x=0.02),
    scene=dict(
        xaxis_title="gap_min_trade (%)",
        yaxis_title="gap_threshold (%)",
        zaxis_title="Profit Factor (IS)",
        zaxis=dict(range=[z_floor, z_top]),
        aspectmode="manual", aspectratio=dict(x=1.5, y=1.0, z=0.8),
        camera=dict(eye=dict(x=1.6, y=1.6, z=0.9), center=dict(x=0, y=0, z=-0.1)),
    ),
    legend=dict(x=0.0, y=0.02, bgcolor="rgba(0,0,0,0)", font=dict(color="#9aa0ab", size=11)),
    annotations=[dict(
        text=(f"Height = in-sample Profit Factor. Floor map = headroom vs -{LIMIT_PCT:.0f}% on FULL period "
              f"(ATR sizing, gate = {GATE} loss). Green = passes, amber = edge, red = breaches."),
        x=0.0, y=-0.02, xref="paper", yref="paper", showarrow=False, xanchor="left",
        font=dict(color="#9aa0ab", size=11),
    )],
    margin=dict(l=0, r=0, t=90, b=30),
)

fig.show()
fig.write_html(Path(RUN_DIR) / "01_gap_surface.html", include_plotlyjs="cdn")
print(f"Saved: {RUN_DIR / '01_gap_surface.html'}")

# ============================================================================
# RESUMEN NUMÉRICO (por si el 3D no se ve bien en tu visor)
# ============================================================================
print(f"\n{'='*70}")
print(f"PF surface (IS)  |  rows = gap_threshold, cols = gap_min_trade")
print(f"{'='*70}")
display(pf_vals.round(2))

print(f"\n{'='*70}")
print(f"Margin to -{LIMIT_PCT:.0f}% (pp)  |  >0 = PASS, <0 = FAIL")
print(f"{'='*70}")
display(margin.round(1))
```

    Sweeping 81 combos (gap_min_trade × gap_threshold) — esto puede tardar unos minutos...
    Done. Trades range: 70 – 497
    PF range: 0.60 – 2.16




    Saved: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/notebooks/Overnight_Gap/runs/v1_us500_gap/01_gap_surface.html
    
    ======================================================================
    PF surface (IS)  |  rows = gap_threshold, cols = gap_min_trade
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
      <th>0.1</th>
      <th>0.2</th>
      <th>0.3</th>
      <th>0.4</th>
      <th>0.5</th>
      <th>0.6</th>
      <th>0.7</th>
      <th>0.8</th>
      <th>1.0</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.50</th>
      <td>0.79</td>
      <td>0.80</td>
      <td>0.83</td>
      <td>0.86</td>
      <td>0.93</td>
      <td>0.91</td>
      <td>0.86</td>
      <td>0.82</td>
      <td>0.80</td>
    </tr>
    <tr>
      <th>0.75</th>
      <td>0.70</td>
      <td>0.71</td>
      <td>0.74</td>
      <td>0.77</td>
      <td>0.83</td>
      <td>0.85</td>
      <td>0.87</td>
      <td>0.82</td>
      <td>0.80</td>
    </tr>
    <tr>
      <th>1.00</th>
      <td>0.60</td>
      <td>0.61</td>
      <td>0.63</td>
      <td>0.65</td>
      <td>0.70</td>
      <td>0.71</td>
      <td>0.72</td>
      <td>0.71</td>
      <td>0.80</td>
    </tr>
    <tr>
      <th>1.25</th>
      <td>0.64</td>
      <td>0.66</td>
      <td>0.69</td>
      <td>0.71</td>
      <td>0.78</td>
      <td>0.79</td>
      <td>0.82</td>
      <td>0.82</td>
      <td>0.99</td>
    </tr>
    <tr>
      <th>1.50</th>
      <td>0.82</td>
      <td>0.84</td>
      <td>0.89</td>
      <td>0.95</td>
      <td>1.08</td>
      <td>1.15</td>
      <td>1.27</td>
      <td>1.34</td>
      <td>2.16</td>
    </tr>
    <tr>
      <th>2.00</th>
      <td>0.68</td>
      <td>0.70</td>
      <td>0.74</td>
      <td>0.78</td>
      <td>0.87</td>
      <td>0.90</td>
      <td>0.96</td>
      <td>0.98</td>
      <td>1.38</td>
    </tr>
    <tr>
      <th>2.50</th>
      <td>0.63</td>
      <td>0.64</td>
      <td>0.68</td>
      <td>0.71</td>
      <td>0.79</td>
      <td>0.82</td>
      <td>0.86</td>
      <td>0.86</td>
      <td>1.20</td>
    </tr>
    <tr>
      <th>3.00</th>
      <td>0.62</td>
      <td>0.63</td>
      <td>0.67</td>
      <td>0.70</td>
      <td>0.78</td>
      <td>0.80</td>
      <td>0.84</td>
      <td>0.84</td>
      <td>1.16</td>
    </tr>
    <tr>
      <th>4.00</th>
      <td>0.64</td>
      <td>0.65</td>
      <td>0.68</td>
      <td>0.71</td>
      <td>0.79</td>
      <td>0.81</td>
      <td>0.85</td>
      <td>0.85</td>
      <td>1.10</td>
    </tr>
  </tbody>
</table>
</div>


    
    ======================================================================
    Margin to -9% (pp)  |  >0 = PASS, <0 = FAIL
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
      <th>0.1</th>
      <th>0.2</th>
      <th>0.3</th>
      <th>0.4</th>
      <th>0.5</th>
      <th>0.6</th>
      <th>0.7</th>
      <th>0.8</th>
      <th>1.0</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0.50</th>
      <td>0.0</td>
      <td>-0.0</td>
      <td>-0.1</td>
      <td>0.8</td>
      <td>2.4</td>
      <td>2.6</td>
      <td>1.9</td>
      <td>3.0</td>
      <td>4.2</td>
    </tr>
    <tr>
      <th>0.75</th>
      <td>0.4</td>
      <td>0.3</td>
      <td>0.2</td>
      <td>1.1</td>
      <td>1.3</td>
      <td>2.7</td>
      <td>3.1</td>
      <td>3.0</td>
      <td>4.2</td>
    </tr>
    <tr>
      <th>1.00</th>
      <td>-1.5</td>
      <td>-1.5</td>
      <td>-0.9</td>
      <td>0.2</td>
      <td>0.7</td>
      <td>1.4</td>
      <td>3.0</td>
      <td>2.9</td>
      <td>4.2</td>
    </tr>
    <tr>
      <th>1.25</th>
      <td>-1.1</td>
      <td>-1.1</td>
      <td>-0.4</td>
      <td>0.6</td>
      <td>1.1</td>
      <td>1.9</td>
      <td>3.3</td>
      <td>3.2</td>
      <td>4.9</td>
    </tr>
    <tr>
      <th>1.50</th>
      <td>0.2</td>
      <td>0.2</td>
      <td>0.8</td>
      <td>1.9</td>
      <td>2.4</td>
      <td>3.2</td>
      <td>4.0</td>
      <td>3.9</td>
      <td>4.9</td>
    </tr>
    <tr>
      <th>2.00</th>
      <td>1.4</td>
      <td>1.4</td>
      <td>2.0</td>
      <td>3.1</td>
      <td>3.7</td>
      <td>4.4</td>
      <td>5.0</td>
      <td>5.0</td>
      <td>6.3</td>
    </tr>
    <tr>
      <th>2.50</th>
      <td>1.4</td>
      <td>1.4</td>
      <td>2.0</td>
      <td>3.1</td>
      <td>3.7</td>
      <td>4.4</td>
      <td>5.0</td>
      <td>5.0</td>
      <td>6.3</td>
    </tr>
    <tr>
      <th>3.00</th>
      <td>1.4</td>
      <td>1.4</td>
      <td>2.0</td>
      <td>3.1</td>
      <td>3.7</td>
      <td>4.4</td>
      <td>5.0</td>
      <td>5.0</td>
      <td>6.8</td>
    </tr>
    <tr>
      <th>4.00</th>
      <td>1.4</td>
      <td>1.4</td>
      <td>2.0</td>
      <td>3.1</td>
      <td>3.7</td>
      <td>4.4</td>
      <td>5.0</td>
      <td>5.0</td>
      <td>7.0</td>
    </tr>
  </tbody>
</table>
</div>


## 4.5 ANNUAL RETURNS


```python
LIMIT = STOP_LIMIT
BG, PANEL, GRID, TXT, TXT2 = '#15171c', '#1b1e26', '#2a2d37', '#e8e9ec', '#9aa0ab'
GREEN, RED, AMBER, BLUE = '#34d399', '#f87171', '#f5a524', '#5468ff'
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

ret_atr = ret_atr_all.astype(float)
ret_cap = ret_cap_all.astype(float)

def by_year(ret):
    g = ret.groupby(ret.index.year)
    return pd.DataFrame({
        "Return": g.apply(lambda x: (1 + x).prod() - 1),
        "MaxDD":  g.apply(lambda x: ((1 + x).cumprod() / (1 + x).cumprod().cummax() - 1).min()),
        "Days":   g.size(),
    })

def cagr(ret):
    yrs = (ret.index[-1] - ret.index[0]).days / 365.25
    return (1 + ret).prod() ** (1 / yrs) - 1

a, c = by_year(ret_atr), by_year(ret_cap)
first_y, last_y = ret_atr.index[0].year, ret_atr.index[-1].year
a["Partial"] = [(y in (first_y, last_y)) and d < 0.9 * 252 for y, d in zip(a.index, a["Days"])]

tbl = pd.DataFrame({
    "ATR return": a["Return"], "ATR MaxDD": a["MaxDD"], "Capital return": c["Return"], "Days": a["Days"],
    "Note": np.where(a["Partial"], "partial year", ""),
    "Breaches limit": np.where(a["MaxDD"] <= -LIMIT, "YES", ""),
})
tbl.index.name = "Year"

full = a[~a["Partial"]]
assert len(full) > 0, "No full calendar years available for the annual summary."
summary = pd.DataFrame({
    "ATR (live robot)": {
        "CAGR (whole period)":        cagr(ret_atr),
        "Mean annual (full years)":   full["Return"].mean(),
        "Median annual (full years)": full["Return"].median(),
        "Best year":                  f"{full['Return'].idxmax()}  {full['Return'].max():+.2%}",
        "Worst year":                 f"{full['Return'].idxmin()}  {full['Return'].min():+.2%}",
        "Positive years":             f"{(full['Return'] > 0).sum()} / {len(full)}  ({(full['Return'] > 0).mean():.0%})",
        "Years breaching the limit":  int((a['MaxDD'] <= -LIMIT).sum()),
    },
    "100% Capital": {
        "CAGR (whole period)":        cagr(ret_cap),
        "Mean annual (full years)":   c.loc[full.index, "Return"].mean(),
        "Median annual (full years)": c.loc[full.index, "Return"].median(),
        "Best year":                  f"{c.loc[full.index, 'Return'].idxmax()}  {c.loc[full.index, 'Return'].max():+.2%}",
        "Worst year":                 f"{c.loc[full.index, 'Return'].idxmin()}  {c.loc[full.index, 'Return'].min():+.2%}",
        "Positive years":             f"{(c.loc[full.index, 'Return'] > 0).sum()} / {len(full)}  ({(c.loc[full.index, 'Return'] > 0).mean():.0%})",
        "Years breaching the limit":  "-",
    },
})

print("=" * 78)
print(f"ANNUAL RETURNS | {ret_atr.index[0]:%Y-%m-%d} -> {ret_atr.index[-1]:%Y-%m-%d} | partial years excluded from means")
print("=" * 78)
display(summary.style.format(lambda v: f"{v:+.2%}" if isinstance(v, (float, np.floating)) else v))

def _color(v):
    return f"color: {GREEN}" if v > 0 else f"color: {RED}"
sty = tbl.style.format({"ATR return": "{:+.2%}", "ATR MaxDD": "{:.2%}", "Capital return": "{:+.2%}"})
sty = (sty.map if hasattr(sty, "map") else sty.applymap)(_color, subset=["ATR return", "Capital return"])
display(sty)

# ---- charts ----
def style(ax, title, ylabel=None, xlabel=None):
    ax.set_facecolor(PANEL)
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(colors=TXT2, labelsize=9)
    ax.set_title(title, color=TXT, fontweight='bold', fontsize=11, loc='left', pad=10)
    if ylabel: ax.set_ylabel(ylabel, color=TXT2, fontsize=9)
    if xlabel: ax.set_xlabel(xlabel, color=TXT2, fontsize=9)

monthly = ((1 + ret_atr).groupby([ret_atr.index.year, ret_atr.index.month]).prod() - 1).unstack()
monthly = monthly.reindex(columns=range(1, 13)) * 100
n_years = len(monthly)

fig = plt.figure(figsize=(14, 5.2 + 0.30 * n_years), facecolor=BG)
gs = GridSpec(2, 2, height_ratios=[5.2, 0.30 * n_years], width_ratios=[12, 1.25], hspace=0.32, wspace=0.03, figure=fig)

ax = fig.add_subplot(gs[0, :])
style(ax, 'Annual returns, year by year (ATR sizing)', 'Annual return (%)')
ax.grid(True, axis='y', color=GRID, linewidth=0.8, alpha=0.9); ax.set_axisbelow(True)
yrs = a.index.values
vals = a["Return"].values * 100
bars = ax.bar(yrs, vals, color=[GREEN if v > 0 else RED for v in vals], alpha=0.85, width=0.7)
for b, (_, row) in zip(bars, a.iterrows()):
    if row["Partial"]:
        b.set_alpha(0.4); b.set_hatch('//'); b.set_edgecolor(TXT2)
    if row["MaxDD"] <= -LIMIT:
        b.set_edgecolor(AMBER); b.set_linewidth(2.0)
    v = row["Return"] * 100
    ax.annotate(f"{v:+.1f}%", (b.get_x() + b.get_width() / 2, v), xytext=(0, 4 if v >= 0 else -12),
                textcoords='offset points', ha='center', color=TXT, fontsize=8)
ax.axhline(0, color=TXT2, lw=0.8)
ax.axhline(cagr(ret_atr) * 100, color=BLUE, ls='--', lw=1.3)
ax.axhline(full["Return"].mean() * 100, color=AMBER, ls=':', lw=1.2)
ax.set_xticks(yrs); ax.set_xticklabels(yrs, rotation=45, color=TXT2, fontsize=9)
ax.set_xlim(yrs.min() - 0.7, yrs.max() + 0.7)
ax.axvspan(oos_start.year - 0.5, last_y + 0.5, color=BLUE, alpha=0.07, lw=0)
ax.text(oos_start.year - 0.4, ax.get_ylim()[1] * 0.93, "Out-of-sample", color=TXT2, fontsize=9)
ax.legend(handles=[
    Line2D([0], [0], color=BLUE, ls='--', lw=1.3, label=f"CAGR {cagr(ret_atr):+.2%}"),
    Line2D([0], [0], color=AMBER, ls=':', lw=1.2, label=f"Mean of full years {full['Return'].mean():+.2%}"),
    Patch(facecolor=TXT2, alpha=0.4, hatch='//', label='Partial year'),
    Patch(facecolor='none', edgecolor=AMBER, lw=2, label=f"Year with MaxDD beyond -{LIMIT:.0%}"),
], frameon=False, labelcolor=TXT2, fontsize=9, loc='upper left', ncol=2)

cmap = LinearSegmentedColormap.from_list('rg', [RED, '#2a2d37', GREEN]); cmap.set_bad(PANEL)
vmax = max(float(np.nanpercentile(np.abs(monthly.values), 95)), 0.5)
axh = fig.add_subplot(gs[1, 0])
style(axh, 'Monthly returns (%)')
axh.imshow(np.ma.masked_invalid(monthly.values), cmap=cmap, vmin=-vmax, vmax=vmax, aspect='auto')
axh.set_xticks(range(12)); axh.set_xticklabels(MONTHS, color=TXT2, fontsize=9)
axh.set_yticks(range(n_years)); axh.set_yticklabels(monthly.index, color=TXT2, fontsize=8)
axh.xaxis.tick_top()
axh.set_xticks(np.arange(-0.5, 12, 1), minor=True); axh.set_yticks(np.arange(-0.5, n_years, 1), minor=True)
axh.grid(which='minor', color=BG, linewidth=1.2); axh.tick_params(which='minor', length=0)
for i in range(n_years):
    for j in range(12):
        v = monthly.values[i, j]
        if not np.isnan(v):
            axh.text(j, i, f"{v:.1f}", ha='center', va='center', fontsize=7, color=TXT if abs(v) > vmax * 0.35 else TXT2)

axy = fig.add_subplot(gs[1, 1])
style(axy, 'Year')
yv = (a["Return"].values * 100).reshape(-1, 1)
vmax_y = max(float(np.nanpercentile(np.abs(yv), 95)), 1.0)
axy.imshow(yv, cmap=cmap, vmin=-vmax_y, vmax=vmax_y, aspect='auto')
axy.set_xticks([]); axy.set_yticks([])
axy.set_yticks(np.arange(-0.5, n_years, 1), minor=True)
axy.grid(which='minor', axis='y', color=BG, linewidth=1.2); axy.tick_params(which='minor', length=0)
for i, (_, row) in enumerate(a.iterrows()):
    axy.text(0, i, f"{row['Return'] * 100:+.1f}%{'*' if row['Partial'] else ''}", ha='center', va='center',
             fontsize=8, fontweight='bold', color=TXT)
    if row["MaxDD"] <= -LIMIT:
        axy.add_patch(Rectangle((-0.5, i - 0.5), 1, 1, fill=False, ec=AMBER, lw=1.8))
fig.text(0.985, 0.012, "* partial year   |   amber box = year whose MaxDD went beyond the limit", color=TXT2, fontsize=9, ha='right')
plt.show()
```

    ==============================================================================
    ANNUAL RETURNS | 2018-01-09 -> 2026-10-23 | partial years excluded from means
    ==============================================================================



<style type="text/css">
</style>
<table id="T_3db70">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_3db70_level0_col0" class="col_heading level0 col0" >ATR (live robot)</th>
      <th id="T_3db70_level0_col1" class="col_heading level0 col1" >100% Capital</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_3db70_level0_row0" class="row_heading level0 row0" >CAGR (whole period)</th>
      <td id="T_3db70_row0_col0" class="data row0 col0" >-0.00%</td>
      <td id="T_3db70_row0_col1" class="data row0 col1" >+0.46%</td>
    </tr>
    <tr>
      <th id="T_3db70_level0_row1" class="row_heading level0 row1" >Mean annual (full years)</th>
      <td id="T_3db70_row1_col0" class="data row1 col0" >+0.15%</td>
      <td id="T_3db70_row1_col1" class="data row1 col1" >+0.87%</td>
    </tr>
    <tr>
      <th id="T_3db70_level0_row2" class="row_heading level0 row2" >Median annual (full years)</th>
      <td id="T_3db70_row2_col0" class="data row2 col0" >+0.02%</td>
      <td id="T_3db70_row2_col1" class="data row2 col1" >-0.27%</td>
    </tr>
    <tr>
      <th id="T_3db70_level0_row3" class="row_heading level0 row3" >Best year</th>
      <td id="T_3db70_row3_col0" class="data row3 col0" >2020  +4.54%</td>
      <td id="T_3db70_row3_col1" class="data row3 col1" >2020  +12.45%</td>
    </tr>
    <tr>
      <th id="T_3db70_level0_row4" class="row_heading level0 row4" >Worst year</th>
      <td id="T_3db70_row4_col0" class="data row4 col0" >2025  -3.53%</td>
      <td id="T_3db70_row4_col1" class="data row4 col1" >2025  -7.35%</td>
    </tr>
    <tr>
      <th id="T_3db70_level0_row5" class="row_heading level0 row5" >Positive years</th>
      <td id="T_3db70_row5_col0" class="data row5 col0" >4 / 8  (50%)</td>
      <td id="T_3db70_row5_col1" class="data row5 col1" >4 / 8  (50%)</td>
    </tr>
    <tr>
      <th id="T_3db70_level0_row6" class="row_heading level0 row6" >Years breaching the limit</th>
      <td id="T_3db70_row6_col0" class="data row6 col0" >0</td>
      <td id="T_3db70_row6_col1" class="data row6 col1" >-</td>
    </tr>
  </tbody>
</table>




<style type="text/css">
#T_c205f_row0_col0, #T_c205f_row0_col2, #T_c205f_row3_col0, #T_c205f_row3_col2, #T_c205f_row5_col0, #T_c205f_row5_col2, #T_c205f_row7_col0, #T_c205f_row7_col2, #T_c205f_row8_col0, #T_c205f_row8_col2 {
  color: #f87171;
}
#T_c205f_row1_col0, #T_c205f_row1_col2, #T_c205f_row2_col0, #T_c205f_row2_col2, #T_c205f_row4_col0, #T_c205f_row4_col2, #T_c205f_row6_col0, #T_c205f_row6_col2 {
  color: #34d399;
}
</style>
<table id="T_c205f">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_c205f_level0_col0" class="col_heading level0 col0" >ATR return</th>
      <th id="T_c205f_level0_col1" class="col_heading level0 col1" >ATR MaxDD</th>
      <th id="T_c205f_level0_col2" class="col_heading level0 col2" >Capital return</th>
      <th id="T_c205f_level0_col3" class="col_heading level0 col3" >Days</th>
      <th id="T_c205f_level0_col4" class="col_heading level0 col4" >Note</th>
      <th id="T_c205f_level0_col5" class="col_heading level0 col5" >Breaches limit</th>
    </tr>
    <tr>
      <th class="index_name level0" >Year</th>
      <th class="blank col0" >&nbsp;</th>
      <th class="blank col1" >&nbsp;</th>
      <th class="blank col2" >&nbsp;</th>
      <th class="blank col3" >&nbsp;</th>
      <th class="blank col4" >&nbsp;</th>
      <th class="blank col5" >&nbsp;</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_c205f_level0_row0" class="row_heading level0 row0" >2018</th>
      <td id="T_c205f_row0_col0" class="data row0 col0" >-2.11%</td>
      <td id="T_c205f_row0_col1" class="data row0 col1" >-2.62%</td>
      <td id="T_c205f_row0_col2" class="data row0 col2" >-4.14%</td>
      <td id="T_c205f_row0_col3" class="data row0 col3" >252</td>
      <td id="T_c205f_row0_col4" class="data row0 col4" ></td>
      <td id="T_c205f_row0_col5" class="data row0 col5" ></td>
    </tr>
    <tr>
      <th id="T_c205f_level0_row1" class="row_heading level0 row1" >2019</th>
      <td id="T_c205f_row1_col0" class="data row1 col0" >+1.67%</td>
      <td id="T_c205f_row1_col1" class="data row1 col1" >-0.17%</td>
      <td id="T_c205f_row1_col2" class="data row1 col2" >+3.19%</td>
      <td id="T_c205f_row1_col3" class="data row1 col3" >258</td>
      <td id="T_c205f_row1_col4" class="data row1 col4" ></td>
      <td id="T_c205f_row1_col5" class="data row1 col5" ></td>
    </tr>
    <tr>
      <th id="T_c205f_level0_row2" class="row_heading level0 row2" >2020</th>
      <td id="T_c205f_row2_col0" class="data row2 col0" >+4.54%</td>
      <td id="T_c205f_row2_col1" class="data row2 col1" >-0.11%</td>
      <td id="T_c205f_row2_col2" class="data row2 col2" >+12.45%</td>
      <td id="T_c205f_row2_col3" class="data row2 col3" >259</td>
      <td id="T_c205f_row2_col4" class="data row2 col4" ></td>
      <td id="T_c205f_row2_col5" class="data row2 col5" ></td>
    </tr>
    <tr>
      <th id="T_c205f_level0_row3" class="row_heading level0 row3" >2021</th>
      <td id="T_c205f_row3_col0" class="data row3 col0" >-1.49%</td>
      <td id="T_c205f_row3_col1" class="data row3 col1" >-1.49%</td>
      <td id="T_c205f_row3_col2" class="data row3 col2" >-1.54%</td>
      <td id="T_c205f_row3_col3" class="data row3 col3" >258</td>
      <td id="T_c205f_row3_col4" class="data row3 col4" ></td>
      <td id="T_c205f_row3_col5" class="data row3 col5" ></td>
    </tr>
    <tr>
      <th id="T_c205f_level0_row4" class="row_heading level0 row4" >2022</th>
      <td id="T_c205f_row4_col0" class="data row4 col0" >+2.09%</td>
      <td id="T_c205f_row4_col1" class="data row4 col1" >-0.94%</td>
      <td id="T_c205f_row4_col2" class="data row4 col2" >+4.88%</td>
      <td id="T_c205f_row4_col3" class="data row4 col3" >258</td>
      <td id="T_c205f_row4_col4" class="data row4 col4" ></td>
      <td id="T_c205f_row4_col5" class="data row4 col5" ></td>
    </tr>
    <tr>
      <th id="T_c205f_level0_row5" class="row_heading level0 row5" >2023</th>
      <td id="T_c205f_row5_col0" class="data row5 col0" >-0.42%</td>
      <td id="T_c205f_row5_col1" class="data row5 col1" >-0.89%</td>
      <td id="T_c205f_row5_col2" class="data row5 col2" >-1.11%</td>
      <td id="T_c205f_row5_col3" class="data row5 col3" >256</td>
      <td id="T_c205f_row5_col4" class="data row5 col4" ></td>
      <td id="T_c205f_row5_col5" class="data row5 col5" ></td>
    </tr>
    <tr>
      <th id="T_c205f_level0_row6" class="row_heading level0 row6" >2024</th>
      <td id="T_c205f_row6_col0" class="data row6 col0" >+0.46%</td>
      <td id="T_c205f_row6_col1" class="data row6 col1" >-0.09%</td>
      <td id="T_c205f_row6_col2" class="data row6 col2" >+0.57%</td>
      <td id="T_c205f_row6_col3" class="data row6 col3" >259</td>
      <td id="T_c205f_row6_col4" class="data row6 col4" ></td>
      <td id="T_c205f_row6_col5" class="data row6 col5" ></td>
    </tr>
    <tr>
      <th id="T_c205f_level0_row7" class="row_heading level0 row7" >2025</th>
      <td id="T_c205f_row7_col0" class="data row7 col0" >-3.53%</td>
      <td id="T_c205f_row7_col1" class="data row7 col1" >-3.53%</td>
      <td id="T_c205f_row7_col2" class="data row7 col2" >-7.35%</td>
      <td id="T_c205f_row7_col3" class="data row7 col3" >257</td>
      <td id="T_c205f_row7_col4" class="data row7 col4" ></td>
      <td id="T_c205f_row7_col5" class="data row7 col5" ></td>
    </tr>
    <tr>
      <th id="T_c205f_level0_row8" class="row_heading level0 row8" >2026</th>
      <td id="T_c205f_row8_col0" class="data row8 col0" >-1.00%</td>
      <td id="T_c205f_row8_col1" class="data row8 col1" >-1.26%</td>
      <td id="T_c205f_row8_col2" class="data row8 col2" >-1.59%</td>
      <td id="T_c205f_row8_col3" class="data row8 col3" >210</td>
      <td id="T_c205f_row8_col4" class="data row8 col4" >partial year</td>
      <td id="T_c205f_row8_col5" class="data row8 col5" ></td>
    </tr>
  </tbody>
</table>




    
![png](01_Gap_Hypothesis_Definition_files/01_Gap_Hypothesis_Definition_12_3.png)
    


## 5. SANITY CHECKS & VERIFICATION


```python
print("=" * 70)
print("SANITY CHECKS & REPRODUCIBILITY")
print("=" * 70)

# -----------------------------------------------------------------------------
# Check 1 — no look-ahead / coherencia de cada trade
# -----------------------------------------------------------------------------
problems = []
open_px = intraday_raw["open"]
w0 = eng._hhmm(RULES["entry_window_start"]); w1 = eng._hhmm(RULES["entry_window_end"])

for i, r in trades_all.iterrows():
    et, xt = pd.Timestamp(r["entry_time"]), pd.Timestamp(r["exit_time"])
    d = 1 if r["direction"] == "long" else -1
    if not xt >= et: problems.append((i, "exit < entry"))
    if pd.Timestamp(r["session_date"]).date() != et.date(): problems.append((i, "entry outside session_date"))
    m = et.hour * 60 + et.minute
    if (w0 is not None and m < w0) or (w1 is not None and m > w1): problems.append((i, "entry outside window"))
    if not np.isclose(r["entry_price"], open_px.loc[et] * (1 + SLIP * d), rtol=1e-9):
        problems.append((i, "entry price != open of entry bar (+slip)"))
    if np.isfinite(r["target_price"]) and not d * (r["target_price"] - r["entry_price"]) > 0:
        problems.append((i, "target on the wrong side"))
    if not d * (r["entry_price"] - r["stop_price"]) > 0:
        problems.append((i, "stop on the wrong side"))

    # Dirección esperada: MR = contra el gap, TF = a favor del gap
    exp_dir = ("short" if r["gap_pct"] >= 0 else "long") if r["strategy"] == "MR" \
              else ("long" if r["gap_pct"] > 0 else "short")
    if r["direction"] != exp_dir: problems.append((i, "MR/TF direction"))

    # Bucket de gap por estrategia
    abs_g = abs(r["gap_pct"])
    if r["strategy"] == "MR" and not (GAP_MIN <= abs_g < GAP_THR):
        problems.append((i, "MR gap bucket"))
    if r["strategy"] == "TF" and not (GAP_THR <= abs_g <= GAP_MAX_TF):
        problems.append((i, "TF gap bucket"))

assert not problems, f"Sanity check 1 FAILED ({len(problems)}): {problems[:5]}"
print(f"Sanity Check 1: PASSED across {len(trades_all)} trades (order, window, fills at open+slip, "
      f"stop/target side, MR/TF direction & gap bucket).")

# -----------------------------------------------------------------------------
# Check 2 — el ATR de la sesión t NO depende del rango de la propia sesión t
# -----------------------------------------------------------------------------
sd = daily_raw.index[len(daily_raw) // 2]
day_key = (intraday_raw.index.normalize().tz_localize(None)
           if intraday_raw.index.tz is not None else intraday_raw.index.normalize())
pert = intraday_raw.copy()
mask = np.asarray(day_key == sd)
pert.loc[mask, "high"] = pert.loc[mask, "high"] * 1.05
d2 = eng.session_daily(pert)
nxt = daily_raw.index[len(daily_raw) // 2 + 1]
assert np.isclose(d2.loc[sd, "atr5"], daily_raw.loc[sd, "atr5"]), "ATR of session t depends on session t's own range!"
assert not np.isclose(d2.loc[nxt, "atr5"], daily_raw.loc[nxt, "atr5"]), "Perturbation had no effect on t+1 (test is vacuous)."
print(f"Sanity Check 2: PASSED. ATR(5) at {sd:%Y-%m-%d} unchanged when that session's high is inflated 5% (only t+1 reacts).")

# -----------------------------------------------------------------------------
# Check 3 — frecuencia de trades
# -----------------------------------------------------------------------------
tpy = trades_all.assign(year=pd.to_datetime(trades_all["session_date"]).dt.year).groupby("year").size()
print(f"\nSanity Check 3: Trade Frequency per Year:")
print(f"   - Average trades per year: {tpy.mean():.1f}")
print(f"   - Min trades: {tpy.min()} ({tpy.idxmin()}) | Max trades: {tpy.max()} ({tpy.idxmax()})")

# -----------------------------------------------------------------------------
# Check 4 — sizing ATR: verifica que expo usa el stop REAL de cada estrategia
#           (fix v2 del motor: ya no existe atr_stop_mult, se usa stop_dist real)
# -----------------------------------------------------------------------------
real_stop = (trades_all["entry_price"] - trades_all["stop_price"]).abs()
stop_in_atr = real_stop / trades_all["atr_prev"]
by_strat = stop_in_atr.groupby(trades_all["strategy"]).agg(["median", "mean", "min", "max"])
print("\nSanity Check 4a: stop real en unidades de ATR por estrategia")
print(by_strat.round(3).to_string())
print(f"   - Esperado: MR ≈ {RULES['mr_stop_atr_mult']:.2f} ATR | TF ≈ {RULES['tf_stop_atr_mult']:.2f} ATR")

risk_pct = eng.ENGINE_DEFAULTS["risk_per_trade_pct"]
expo_cap = eng.ENGINE_DEFAULTS["max_exposure"]
expected_expo = np.minimum(expo_cap, (risk_pct / 100.0) * trades_all["entry_price"] / real_stop)
delta = (trades_all["expo"] - expected_expo).abs()
print(f"\nSanity Check 4b: expo usa el stop real (fix v2)")
print(f"   - max |expo - expected| = {delta.max():.2e}  (esperado ≈ 0)")
print(f"   - median expo MR = {trades_all.loc[trades_all.strategy=='MR','expo'].median():.4f}")
print(f"   - median expo TF = {trades_all.loc[trades_all.strategy=='TF','expo'].median():.4f}")
print(f"   - risk_pct = {risk_pct:.2f}%  |  expo_cap = {expo_cap:.2f}")
```

    ======================================================================
    SANITY CHECKS & REPRODUCIBILITY
    ======================================================================
    Sanity Check 1: PASSED across 80 trades (order, window, fills at open+slip, stop/target side, MR/TF direction & gap bucket).
    Sanity Check 2: PASSED. ATR(5) at 2022-06-01 unchanged when that session's high is inflated 5% (only t+1 reacts).
    
    Sanity Check 3: Trade Frequency per Year:
       - Average trades per year: 8.9
       - Min trades: 2 (2021) | Max trades: 19 (2022)
    
    Sanity Check 4a: stop real en unidades de ATR por estrategia
              median  mean   min   max
    strategy                          
    MR          1.00  1.00  1.00  1.00
    TF          1.25  1.25  1.25  1.25
       - Esperado: MR ≈ 1.00 ATR | TF ≈ 1.25 ATR
    
    Sanity Check 4b: expo usa el stop real (fix v2)
       - max |expo - expected| = 4.77e-15  (esperado ≈ 0)
       - median expo MR = 0.5510
       - median expo TF = 0.3631
       - risk_pct = 1.00%  |  expo_cap = 1.00


## 6. MR-ONLY vs TF-ONLY vs COMBINED


```python
def _row(name, t, daily):
    ret = eng.daily_returns(daily, t, "atr"); eq = (1 + ret).cumprod()
    ta = as_atr(t)
    return {"Variant": name, "Trades": len(ta), "Win Rate": f"{(ta['win'].mean()*100 if len(ta) else 0):.1f}%",
            "Profit Factor": f"{pf(ta):.3f}", "Sharpe": f"{sharpe(ret):.2f}", "Max Drawdown": f"{max_dd(eq)*100:.2f}%"}

sub_mr = trades_all[trades_all.strategy == "MR"]; sub_tf = trades_all[trades_all.strategy == "TF"]
comp = pd.DataFrame([_row("Combined (MR+TF)", trades_all, daily_raw), _row("MR only", sub_mr, daily_raw), _row("TF only", sub_tf, daily_raw)])
print("=" * 80); print("COMBINED vs MR-only vs TF-only (ATR sizing, full period)"); print("=" * 80)
display(comp)

ret_mr = eng.daily_returns(daily_raw, sub_mr, "atr"); ret_tf = eng.daily_returns(daily_raw, sub_tf, "atr")
print(f"MR/TF daily-return correlation: {ret_mr.corr(ret_tf):.3f}")
```

    ================================================================================
    COMBINED vs MR-only vs TF-only (ATR sizing, full period)
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
      <th>Variant</th>
      <th>Trades</th>
      <th>Win Rate</th>
      <th>Profit Factor</th>
      <th>Sharpe</th>
      <th>Max Drawdown</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>Combined (MR+TF)</td>
      <td>80</td>
      <td>66.2%</td>
      <td>1.004</td>
      <td>0.00</td>
      <td>-4.91%</td>
    </tr>
    <tr>
      <th>1</th>
      <td>MR only</td>
      <td>43</td>
      <td>67.4%</td>
      <td>0.970</td>
      <td>-0.03</td>
      <td>-1.96%</td>
    </tr>
    <tr>
      <th>2</th>
      <td>TF only</td>
      <td>37</td>
      <td>64.9%</td>
      <td>1.029</td>
      <td>0.02</td>
      <td>-4.37%</td>
    </tr>
  </tbody>
</table>
</div>


    MR/TF daily-return correlation: 0.000


## 6.5 HARD RISK LIMIT CHECK


```python
R0         = 0.01      # r used by the ATR sizing in this run
STAGE_DAYS = 252       # trading days a stage lasts (start-anchored test)
P_MAX      = 0.05      # max tolerated probability of touching the limit within a stage
N_SIM, BLOCK, SEED = 10_000, 20, 42
R_GRID     = [0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009, 0.010]
GATE       = "stage"   # "stage" = loss vs start-of-stage balance | "trailing" = max DD from running peak
GATE_COL   = "Worst stage loss" if GATE == "stage" else "Hist MDD"

ret0 = ret_atr_all.astype(float)
assert len(ret0) > STAGE_DAYS, f"Need more than {STAGE_DAYS} sessions for the stage test."

def underwater(ret):
    eq = (1 + ret).cumprod()
    return eq, eq / eq.cummax() - 1

def stage_losses(ret, window):
    if len(ret) < window:
        return np.array([np.nan])
    w = sliding_window_view(ret.values, window)
    return np.cumprod(1 + w, axis=1).min(axis=1) - 1

rng = np.random.default_rng(SEED)
v = ret0.values
n_blocks = int(np.ceil(STAGE_DAYS / BLOCK))
idx = (rng.integers(0, len(v), size=(N_SIM, n_blocks))[:, :, None] + np.arange(BLOCK)) % len(v)
sim0 = v[idx.reshape(N_SIM, -1)[:, :STAGE_DAYS]]

rows, min_paths = [], {}
for r in sorted(set(R_GRID + [R0])):
    k = r / R0
    ret = ret0 * k
    _, dd = underwater(ret)
    sl = stage_losses(ret, STAGE_DAYS)
    cum = np.cumprod(1 + sim0 * k, axis=1)
    min_paths[r] = cum.min(axis=1) - 1
    mdd_sim = (cum / np.maximum.accumulate(cum, axis=1) - 1).min(axis=1)
    rows.append({"r": r, "Hist MDD": dd.min(), "Worst stage loss": np.nanmin(sl),
                 "Stages > limit": np.nanmean(sl <= -LIMIT),
                 "P(touch limit)": (min_paths[r] <= -LIMIT).mean(),
                 "MDD p95 (stage)": np.percentile(mdd_sim, 5)})
res = pd.DataFrame(rows).set_index("r")
res["OK"] = (res[GATE_COL] >= -LIMIT) & (res["P(touch limit)"] <= P_MAX)

ok_r = res.index[res["OK"]]
r_max = ok_r.max() if len(ok_r) else None
cur = res.loc[R0]
RISK_OK = bool(cur["OK"])

print("=" * 78)
print(f"HARD RISK LIMIT CHECK | limit -{LIMIT:.0%} | stage {STAGE_DAYS} days | ATR sizing, r0 = {R0:.2%} | FULL period")
print("=" * 78)
fmt = {c: "{:.2%}" for c in res.columns if c != "OK"}
display(res.rename(index=lambda x: f"{x:.2%}").style.format(fmt))

eq0, dd0 = underwater(ret0)
trough = dd0.idxmin(); peak = eq0.loc[:trough].idxmax()
print(f"Worst historical drawdown at r={R0:.2%}: {dd0.min():.2%} ({peak:%Y-%m-%d} -> {trough:%Y-%m-%d})")
print(f"Verdict at r={R0:.2%}: {'PASS' if RISK_OK else 'FAIL'}  "
      f"({GATE} loss {cur[GATE_COL]:.2%} vs -{LIMIT:.0%}, P(touch) {cur['P(touch limit)']:.1%} vs {P_MAX:.0%}; "
      f"trailing MDD for reference {cur['Hist MDD']:.2%})")
print(f"Largest r in the grid that passes: {'none' if r_max is None else f'{r_max:.2%}'}")
print("Note: history and bootstrap can't prove 'never'; they bound how likely it is. No hard stop is simulated.")

parts = []
for name, d, t in (("In-Sample", daily_is, trades_is), ("Out-of-Sample", daily_oos, trades_oos), ("Full", daily_raw, trades_all)):
    rr = eng.daily_returns(d, t, sizing="atr").astype(float)
    _, ddp = underwater(rr)
    slp = np.nanmin(stage_losses(rr, STAGE_DAYS)) if len(rr) >= STAGE_DAYS else np.nan
    parts.append({"Period": name, "Max drawdown": ddp.min(), "Worst stage loss": slp,
                  f"vs -{LIMIT:.0%}": "PASS" if ddp.min() >= -LIMIT else "FAIL"})
print("\nDrawdown by period (ATR sizing, r = %.2f%%) - a drawdown that straddles the IS/OOS cut looks smaller in each part:" % (R0 * 100))
display(pd.DataFrame(parts).set_index("Period").style.format({"Max drawdown": "{:.2%}", "Worst stage loss": "{:.2%}"}))

# ---- dashboard ----
lim = -LIMIT * 100
sl0 = stage_losses(ret0, STAGE_DAYS) * 100
sl_dates = ret0.index[:len(sl0)]
breach_days = dd0[dd0 <= -LIMIT]
verdict_col = GREEN if RISK_OK else RED

fig = plt.figure(figsize=(14, 12), facecolor=BG)
gs = GridSpec(3, 2, height_ratios=[1.25, 1, 1.1], hspace=0.42, wspace=0.18, figure=fig)
fig.text(0.015, 0.975, f"{'PASS' if RISK_OK else 'FAIL'}", color=BG, fontsize=13, fontweight='bold',
         va='center', bbox=dict(boxstyle='round,pad=0.45', fc=verdict_col, ec='none'))
fig.text(0.075, 0.975,
         f"Hard limit -{LIMIT:.0%} at r = {R0:.2%}  |  {GATE} loss {cur[GATE_COL]:.2%}  |  "
         f"P(touch) {cur['P(touch limit)']:.1%} (max {P_MAX:.0%})  |  Max passing r: {'none' if r_max is None else f'{r_max:.2%}'}",
         color=TXT, fontsize=11, va='center')

ax1 = fig.add_subplot(gs[0, :])
style(ax1, 'Underwater curve vs. hard drawdown limit (full period)', 'Drawdown (%)')
ax1.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
ax1.axhspan(lim, min(dd0.min() * 100 * 1.15, lim - 1), color=RED, alpha=0.10, lw=0)
ax1.fill_between(dd0.index, dd0 * 100, 0, color=RED, alpha=0.18, lw=0)
ax1.plot(dd0.index, dd0 * 100, color=RED, lw=1.2, label=f"r = {R0:.2%}")
if r_max is not None and r_max != R0:
    ax1.plot(dd0.index, underwater(ret0 * (r_max / R0))[1] * 100, color=GREEN, lw=1.2, label=f"r = {r_max:.2%} (largest passing)")
ax1.axhline(lim, color=AMBER, ls='--', lw=1.2, label=f"Limit -{LIMIT:.0%}")
if len(breach_days):
    ax1.scatter(breach_days.index, breach_days * 100, s=14, color=AMBER, zorder=5, label=f"Breach days ({len(breach_days)})")
ax1.axvspan(peak, trough, color=AMBER, alpha=0.08, lw=0)
ax1.axvline(oos_start, color=TXT2, ls=':', lw=1.1, label=f"IS/OOS cut ({oos_start:%Y-%m-%d})")
ax1.annotate(f"Worst: {dd0.min():.2%}\n{peak:%b %Y} -> {trough:%b %Y}", xy=(trough, dd0.min() * 100), xytext=(30, -8),
             textcoords='offset points', color=TXT, fontsize=9, arrowprops=dict(arrowstyle='->', color=TXT2, lw=1))
ax1.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='lower left', ncol=5)

ax2 = fig.add_subplot(gs[1, :], sharex=ax1)
style(ax2, f'Where it fails: worst loss of a {STAGE_DAYS}-day stage, by start date', 'Worst stage loss (%)')
ax2.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
ax2.plot(sl_dates, sl0, color=BLUE, lw=1.3)
ax2.fill_between(sl_dates, sl0, lim, where=sl0 <= lim, color=RED, alpha=0.55, lw=0, label='Start dates that would breach')
ax2.fill_between(sl_dates, sl0, 0, where=sl0 > lim, color=GREEN, alpha=0.10, lw=0)
pct_bad = (sl0 <= lim).mean()
ax2.text(0.99, 0.08, f"{pct_bad:.1%} of start dates breach the limit", transform=ax2.transAxes, ha='right',
         color=RED if pct_bad else GREEN, fontsize=10, fontweight='bold')
ax2.axhline(lim, color=AMBER, ls='--', lw=1.2, label=f"Limit -{LIMIT:.0%}")
ax2.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='lower left')

ax3 = fig.add_subplot(gs[2, 0])
style(ax3, 'Risk budget: P(touch limit) by r', 'P(touch) (%)', 'Risk per trade (r)')
ax3.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
xs = np.arange(len(res))
bars = ax3.bar(xs, res["P(touch limit)"] * 100, color=[GREEN if ok else RED for ok in res["OK"]], alpha=0.85, width=0.7)
ax3.axhline(P_MAX * 100, color=AMBER, ls='--', lw=1.2, label=f"Max tolerated {P_MAX:.0%}")
ax3.set_xticks(xs); ax3.set_xticklabels([f"{r:.2%}" for r in res.index], rotation=45, color=TXT2, fontsize=8)
i0 = list(res.index).index(R0)
bars[i0].set_edgecolor(TXT); bars[i0].set_linewidth(1.8)
ax3.annotate('current', xy=(i0, res.loc[R0, "P(touch limit)"] * 100), xytext=(0, 8), textcoords='offset points', ha='center', color=TXT, fontsize=9)
ax3.set_ylim(0, max(P_MAX * 100 * 1.6, float((res["P(touch limit)"] * 100).max()) * 1.25))
ax3.text(0.02, 0.80, "No r in the grid passes" if r_max is None else f"Max passing r: {r_max:.2%}  (x{r_max / R0:.2f} of current)",
         transform=ax3.transAxes, color=RED if r_max is None else GREEN, fontsize=9, fontweight='bold')
ax3.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper right')

ax4 = fig.add_subplot(gs[2, 1])
style(ax4, f'Simulated stages at r = {R0:.2%}: worst point', 'Frequency', 'Worst loss in stage (%)')
ax4.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
cnt, edges = np.histogram(min_paths[R0] * 100, bins=60)
centers = (edges[:-1] + edges[1:]) / 2
ax4.bar(centers, cnt, width=np.diff(edges), color=[RED if x <= lim else BLUE for x in centers], alpha=0.85)
ax4.axvline(lim, color=AMBER, ls='--', lw=1.2, label=f"Limit -{LIMIT:.0%}")
ax4.text(0.03, 0.9, f"{cur['P(touch limit)']:.1%} of {N_SIM:,} stages touch the limit", transform=ax4.transAxes,
         color=RED if cur['P(touch limit)'] > P_MAX else GREEN, fontsize=10, fontweight='bold')
ax4.legend(frameon=False, labelcolor=TXT2, fontsize=9, loc='upper left', bbox_to_anchor=(0, 0.85))
plt.show()
```

    ==============================================================================
    HARD RISK LIMIT CHECK | limit -9% | stage 252 days | ATR sizing, r0 = 1.00% | FULL period
    ==============================================================================



<style type="text/css">
</style>
<table id="T_088a3">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_088a3_level0_col0" class="col_heading level0 col0" >Hist MDD</th>
      <th id="T_088a3_level0_col1" class="col_heading level0 col1" >Worst stage loss</th>
      <th id="T_088a3_level0_col2" class="col_heading level0 col2" >Stages > limit</th>
      <th id="T_088a3_level0_col3" class="col_heading level0 col3" >P(touch limit)</th>
      <th id="T_088a3_level0_col4" class="col_heading level0 col4" >MDD p95 (stage)</th>
      <th id="T_088a3_level0_col5" class="col_heading level0 col5" >OK</th>
    </tr>
    <tr>
      <th class="index_name level0" >r</th>
      <th class="blank col0" >&nbsp;</th>
      <th class="blank col1" >&nbsp;</th>
      <th class="blank col2" >&nbsp;</th>
      <th class="blank col3" >&nbsp;</th>
      <th class="blank col4" >&nbsp;</th>
      <th class="blank col5" >&nbsp;</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_088a3_level0_row0" class="row_heading level0 row0" >0.20%</th>
      <td id="T_088a3_row0_col0" class="data row0 col0" >-1.00%</td>
      <td id="T_088a3_row0_col1" class="data row0 col1" >-0.84%</td>
      <td id="T_088a3_row0_col2" class="data row0 col2" >0.00%</td>
      <td id="T_088a3_row0_col3" class="data row0 col3" >0.00%</td>
      <td id="T_088a3_row0_col4" class="data row0 col4" >-0.54%</td>
      <td id="T_088a3_row0_col5" class="data row0 col5" >True</td>
    </tr>
    <tr>
      <th id="T_088a3_level0_row1" class="row_heading level0 row1" >0.30%</th>
      <td id="T_088a3_row1_col0" class="data row1 col0" >-1.49%</td>
      <td id="T_088a3_row1_col1" class="data row1 col1" >-1.26%</td>
      <td id="T_088a3_row1_col2" class="data row1 col2" >0.00%</td>
      <td id="T_088a3_row1_col3" class="data row1 col3" >0.00%</td>
      <td id="T_088a3_row1_col4" class="data row1 col4" >-0.80%</td>
      <td id="T_088a3_row1_col5" class="data row1 col5" >True</td>
    </tr>
    <tr>
      <th id="T_088a3_level0_row2" class="row_heading level0 row2" >0.40%</th>
      <td id="T_088a3_row2_col0" class="data row2 col0" >-1.99%</td>
      <td id="T_088a3_row2_col1" class="data row2 col1" >-1.67%</td>
      <td id="T_088a3_row2_col2" class="data row2 col2" >0.00%</td>
      <td id="T_088a3_row2_col3" class="data row2 col3" >0.00%</td>
      <td id="T_088a3_row2_col4" class="data row2 col4" >-1.07%</td>
      <td id="T_088a3_row2_col5" class="data row2 col5" >True</td>
    </tr>
    <tr>
      <th id="T_088a3_level0_row3" class="row_heading level0 row3" >0.50%</th>
      <td id="T_088a3_row3_col0" class="data row3 col0" >-2.48%</td>
      <td id="T_088a3_row3_col1" class="data row3 col1" >-2.09%</td>
      <td id="T_088a3_row3_col2" class="data row3 col2" >0.00%</td>
      <td id="T_088a3_row3_col3" class="data row3 col3" >0.00%</td>
      <td id="T_088a3_row3_col4" class="data row3 col4" >-1.33%</td>
      <td id="T_088a3_row3_col5" class="data row3 col5" >True</td>
    </tr>
    <tr>
      <th id="T_088a3_level0_row4" class="row_heading level0 row4" >0.60%</th>
      <td id="T_088a3_row4_col0" class="data row4 col0" >-2.97%</td>
      <td id="T_088a3_row4_col1" class="data row4 col1" >-2.50%</td>
      <td id="T_088a3_row4_col2" class="data row4 col2" >0.00%</td>
      <td id="T_088a3_row4_col3" class="data row4 col3" >0.00%</td>
      <td id="T_088a3_row4_col4" class="data row4 col4" >-1.60%</td>
      <td id="T_088a3_row4_col5" class="data row4 col5" >True</td>
    </tr>
    <tr>
      <th id="T_088a3_level0_row5" class="row_heading level0 row5" >0.70%</th>
      <td id="T_088a3_row5_col0" class="data row5 col0" >-3.46%</td>
      <td id="T_088a3_row5_col1" class="data row5 col1" >-2.92%</td>
      <td id="T_088a3_row5_col2" class="data row5 col2" >0.00%</td>
      <td id="T_088a3_row5_col3" class="data row5 col3" >0.00%</td>
      <td id="T_088a3_row5_col4" class="data row5 col4" >-1.87%</td>
      <td id="T_088a3_row5_col5" class="data row5 col5" >True</td>
    </tr>
    <tr>
      <th id="T_088a3_level0_row6" class="row_heading level0 row6" >0.80%</th>
      <td id="T_088a3_row6_col0" class="data row6 col0" >-3.94%</td>
      <td id="T_088a3_row6_col1" class="data row6 col1" >-3.33%</td>
      <td id="T_088a3_row6_col2" class="data row6 col2" >0.00%</td>
      <td id="T_088a3_row6_col3" class="data row6 col3" >0.00%</td>
      <td id="T_088a3_row6_col4" class="data row6 col4" >-2.13%</td>
      <td id="T_088a3_row6_col5" class="data row6 col5" >True</td>
    </tr>
    <tr>
      <th id="T_088a3_level0_row7" class="row_heading level0 row7" >0.90%</th>
      <td id="T_088a3_row7_col0" class="data row7 col0" >-4.43%</td>
      <td id="T_088a3_row7_col1" class="data row7 col1" >-3.74%</td>
      <td id="T_088a3_row7_col2" class="data row7 col2" >0.00%</td>
      <td id="T_088a3_row7_col3" class="data row7 col3" >0.00%</td>
      <td id="T_088a3_row7_col4" class="data row7 col4" >-2.39%</td>
      <td id="T_088a3_row7_col5" class="data row7 col5" >True</td>
    </tr>
    <tr>
      <th id="T_088a3_level0_row8" class="row_heading level0 row8" >1.00%</th>
      <td id="T_088a3_row8_col0" class="data row8 col0" >-4.91%</td>
      <td id="T_088a3_row8_col1" class="data row8 col1" >-4.15%</td>
      <td id="T_088a3_row8_col2" class="data row8 col2" >0.00%</td>
      <td id="T_088a3_row8_col3" class="data row8 col3" >0.00%</td>
      <td id="T_088a3_row8_col4" class="data row8 col4" >-2.66%</td>
      <td id="T_088a3_row8_col5" class="data row8 col5" >True</td>
    </tr>
  </tbody>
</table>



    Worst historical drawdown at r=1.00%: -4.91% (2023-02-16 -> 2026-09-17)
    Verdict at r=1.00%: PASS  (stage loss -4.15% vs -9%, P(touch) 0.0% vs 5%; trailing MDD for reference -4.91%)
    Largest r in the grid that passes: 1.00%
    Note: history and bootstrap can't prove 'never'; they bound how likely it is. No hard stop is simulated.
    
    Drawdown by period (ATR sizing, r = 1.00%) - a drawdown that straddles the IS/OOS cut looks smaller in each part:



<style type="text/css">
</style>
<table id="T_01672">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_01672_level0_col0" class="col_heading level0 col0" >Max drawdown</th>
      <th id="T_01672_level0_col1" class="col_heading level0 col1" >Worst stage loss</th>
      <th id="T_01672_level0_col2" class="col_heading level0 col2" >vs -9%</th>
    </tr>
    <tr>
      <th class="index_name level0" >Period</th>
      <th class="blank col0" >&nbsp;</th>
      <th class="blank col1" >&nbsp;</th>
      <th class="blank col2" >&nbsp;</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_01672_level0_row0" class="row_heading level0 row0" >In-Sample</th>
      <td id="T_01672_row0_col0" class="data row0 col0" >-2.62%</td>
      <td id="T_01672_row0_col1" class="data row0 col1" >-2.62%</td>
      <td id="T_01672_row0_col2" class="data row0 col2" >PASS</td>
    </tr>
    <tr>
      <th id="T_01672_level0_row1" class="row_heading level0 row1" >Out-of-Sample</th>
      <td id="T_01672_row1_col0" class="data row1 col0" >-4.91%</td>
      <td id="T_01672_row1_col1" class="data row1 col1" >-4.15%</td>
      <td id="T_01672_row1_col2" class="data row1 col2" >PASS</td>
    </tr>
    <tr>
      <th id="T_01672_level0_row2" class="row_heading level0 row2" >Full</th>
      <td id="T_01672_row2_col0" class="data row2 col0" >-4.91%</td>
      <td id="T_01672_row2_col1" class="data row2 col1" >-4.15%</td>
      <td id="T_01672_row2_col2" class="data row2 col2" >PASS</td>
    </tr>
  </tbody>
</table>




    
![png](01_Gap_Hypothesis_Definition_files/01_Gap_Hypothesis_Definition_18_4.png)
    


## 7. SUMMARY OF HYPOTHESIS & NEXT STEPS


```python
PF_MIN, WR_MIN = 1.3, 0.55
pf_all, wr_all = pf(trades_all), float(trades_all["win"].mean())
pf_is, pf_oos = pf(trades_is), pf(trades_oos)
max_dd_atr = max_dd(eq_atr_all) * 100
years = (daily_raw.index[-1] - daily_raw.index[0]).days / 365.25
confirmed = (pf_all > PF_MIN) and (wr_all > WR_MIN)
next_nb = "02_Gap_Optimization.ipynb"

if INVERT:
    if confirmed:
        verdict = "Inverted Hypothesis Confirmed"
        interpret = ("Con la inversión activa (pequeños→TF, grandes→MR) el edge SÍ aparece. "
                     "La hipótesis original del doc queda en duda en este activo.")
    else:
        verdict = "Inverted Hypothesis NOT confirmed"
        interpret = ("Ni el original ni el invertido muestran edge claro. "
                     "Probablemente no hay señal, o los costes la comen.")
    label_lo, label_hi = "TF", "MR"
else:
    if confirmed:
        verdict = "Hypothesis Confirmed"
        interpret = "La hipótesis original del doc se sostiene sobre este activo."
    else:
        verdict = "Hypothesis NOT clearly confirmed"
        interpret = ("Con los parámetros actuales no hay edge claro en este activo. "
                     "Prueba invertir (invert_strategy: true) o re-calibrar en el notebook 02.")
    label_lo, label_hi = "MR", "TF"

print("=" * 80)
print("7. SUMMARY OF HYPOTHESIS & NEXT STEPS")
print("=" * 80)
print(f"""
Mode: {'INVERTED' if INVERT else 'ORIGINAL'}
Bucket map:
    gap ∈ [{GAP_MIN:g}%, {GAP_THR:g}%)  → {label_lo}
    gap ∈ [{GAP_THR:g}%, {GAP_MAX_TF:g}%] → {label_hi}

Key Findings:

1. {verdict}: {interpret}
   Numbers: WR = {wr_all*100:.1f}%, PF = {pf_all:.3f} (IS = {pf_is:.3f}, OOS = {pf_oos:.3f}),
   N = {len(trades_all)} trades over {years:.1f} years.

2. Robustness of ATR Sizing: risk_per_trade_pct = {eng.ENGINE_DEFAULTS['risk_per_trade_pct']:g}%
   keeps max drawdown at {max_dd_atr:.2f}% over the {daily_raw.index[0].year}-{daily_raw.index[-1].year} span.
   Hard-limit check at r = {R0:.2%}: {'PASS' if RISK_OK else 'FAIL'}.

3. Reproducibility: benchmark comparison not applicable (edge != RSI2).

4. Next Step: Proceed to {next_nb} to verify the plateau of (gap_min_trade={GAP_MIN:g}%, gap_threshold={GAP_THR:g}%).
""")
```


    ---------------------------------------------------------------------------

    NameError                                 Traceback (most recent call last)

    Cell In[12], line 9
          6 confirmed = (pf_all > PF_MIN) and (wr_all > WR_MIN)
          7 next_nb = "02_Gap_Optimization.ipynb"
    ----> 9 if INVERT:
         10     if confirmed:
         11         verdict = "Inverted Hypothesis Confirmed"


    NameError: name 'INVERT' is not defined


## 8. SAVE THE RESULTS OF THIS NOTEBOOK FOR THE VARIANT


```python
save_json(cfg, "01_hypothesis.json", {
    "variant": cfg["id"], "ticker": TICKER, "params": cfg["params"],
    "oos_start": str(oos_start.date()),
    "all": {"n": int(len(trades_all)), "pf": float(pf_all), "win_rate": float(wr_all)},
    "is":  {"n": int(len(trades_is)),  "pf": float(pf_is)},
    "oos": {"n": int(len(trades_oos)), "pf": float(pf_oos)},
    "max_dd_atr_pct": float(max_dd_atr),
    "risk_limit_ok": bool(RISK_OK),
    "hypothesis_confirmed": bool(confirmed),
})
```

## 9. SIGNAL PARITY


```python
BASE_VARIANT = None   # nombre del yaml base (sin .yaml). En la propia base: None.
                      # Para comparar contra otra variante del MISMO edge (p.ej. otro ticker).
if BASE_VARIANT:
    cb = load_variant(BASE_VARIANT)
    diff = {k: (cb["params"].get(k), cfg["params"].get(k))
            for k in set(cb["params"]) | set(cfg["params"]) if cb["params"].get(k) != cfg["params"].get(k)}
    if diff:
        print("WARNING: base params differ from this variant (base, variant). Both backtests use the VARIANT params:")
        for k, (bv, vv) in sorted(diff.items()):
            print(f"  {k}: {bv} vs {vv}")

    bd = cb.get("engine_defaults", {})
    rb = eng.load_data(cb["instrument"]["ticker"], start=DATA_START,
                       source=bd.get("data_source", eng.ENGINE_DEFAULTS["data_source"]),
                       csv_path=bd.get("csv_path", eng.ENGINE_DEFAULTS["csv_path"]))
    db_ = eng.session_daily(rb)
    tb = run(rb, db_)
    print(f"base ticker: {cb['instrument']['ticker']} | variant ticker: {TICKER}")
    print(f"trades base/variant: {len(tb)}/{len(trades_all)}")
    if len(tb) and len(trades_all):
        print(f"entry sessions shared: {trades_all['session_date'].isin(tb['session_date']).mean():.0%} (variant in base) | "
              f"{tb['session_date'].isin(trades_all['session_date']).mean():.0%} (base in variant)")
else:
    print("Signal parity: not applicable (no base variant for this edge).")
```
