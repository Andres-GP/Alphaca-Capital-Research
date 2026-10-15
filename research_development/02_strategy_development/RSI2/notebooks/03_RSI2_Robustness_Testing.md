# 3. QQQ Daily RSI(2) Mean Reversion - Robustness Battery & Validation Gate
## Systematic Trading Approach following Alphaca Framework

This notebook executes the full multi-phase statistical robustness battery and validation gate for the **Alphaca RSI(2) Mean Reversion** strategy on **QQQ daily bars**.

### Robustness Battery Scope:
1. **Phase 1 · Out-Of-Sample Validation**: Performance evaluation on untouched OOS data (2018-09-17 to present) under both 100% Capital and 1% Risk ATR sizing.
2. **Phase 2 · Walk-Forward Analysis**: 23 rolling 3-year In-Sample / 1-year Out-of-Sample windows with strictly fixed rules.
3. **Phase 3 · Block Monte Carlo Simulation**: 10,000 circular block resamplings (block=5) to preserve winning/losing streaks and stress-test tail risk.
4. **Phase 4 · Monkey Test**: 2,000 synthetic portfolios using identical trade durations and filter eligibility to rule out market-drift artifacts.
5. **Phase 5 · Stress Testing**: Doubled execution costs (10 bps/side), removal of the 2 best years, and performance during major historical crisis regimes (2000-2002, 2008, 2022).
6. **Phase 6 · Edge Decay Analysis**: Rolling 40-trade Profit Factor and recent vs. historical performance tracking.
7. **Phase 7 · Full Validation Gate**: Automated execution of all gating criteria via `validation_gate.py`.

# Strategy Parameters


```python
VARIANT = "v1_qqq"
```

## 1. IMPORTS AND CONFIG


```python
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ---- Paths ----
# Notebook en RSI2/notebooks/ -> utils está 3 niveles arriba; rsi2_engine y variants están en '..'
utils_path  = os.path.abspath('../../../utils')
engine_path = os.path.abspath('..')                  # rsi2_engine.py suelto junto a notebooks/
engine_dir  = os.path.abspath('../rsi2_engine')      # o rsi2_engine/ como carpeta

for p in (utils_path, engine_path, engine_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils import compute_metrics, plot_equity_curve
from metrics import sharpe_ratio, max_drawdown
from robustness import monte_carlo_block, monkey_test, grid_search, plateau_check, plot_grid, plot_monkey
from edge_decay import rolling_pf, plot_rolling_pf, pf_by_year, edge_decay_summary
from validation_gate import run_validation
import rsi2_engine as eng
import variant_config
from variant_config import load_variant, save_json

# variants/ está al mismo nivel que notebooks/, no en utils/
variant_config.EDGE_DIR = Path('..').resolve()

# ---- Variant config: single source of truth ----
cfg        = load_variant(VARIANT)
RUN_DIR    = cfg["run_dir"]
TICKER     = cfg["instrument"]["ticker"]
DATA_START = cfg["instrument"]["start"]
OOS_START  = cfg["oos_start_ts"]
SMA_LEN    = cfg["params"]["sma_len"]
RSI_THR    = cfg["params"]["rsi_thr"]
EXIT_MODE  = cfg["params"]["exit_mode"]
SLIP_BPS   = cfg["params"]["slip_bps_per_side"]
RSI_VALUES = cfg["grid"]["rsi_values"]
SMA_VALUES = cfg["grid"]["sma_values"]

print("Imports complete.")
print(f"Loaded utils from: {utils_path}")
print(f"Variant: {cfg['id']} | {TICKER} | RSI(2) < {RSI_THR:g} | SMA({SMA_LEN}) | exit={EXIT_MODE} | {SLIP_BPS:g} bps/side")
```


    ---------------------------------------------------------------------------

    ModuleNotFoundError                       Traceback (most recent call last)

    Cell In[2], line 12
          9     sys.path.insert(0, utils_path)
         10 sys.path.insert(0, os.path.abspath('.'))
    ---> 12 from utils import compute_metrics, plot_equity_curve
         13 from metrics import sharpe_ratio, max_drawdown
         14 from robustness import monte_carlo_block, monkey_test, grid_search, plateau_check, plot_grid, plot_monkey


    ModuleNotFoundError: No module named 'utils'


## 2. OUT-OF-SAMPLE (OOS) PERFORMANCE & COMPARISON


```python
# OOS_START, TICKER, DATA_START, SMA_LEN, RSI_THR, EXIT_MODE and SLIP_BPS come from the config cell
df_raw = eng.load_data(TICKER, start=DATA_START)
common_start = eng.prepare(df_raw, sma_len=SMA_LEN).index[0]   # common start across grid
df = eng.prepare(df_raw, sma_len=SMA_LEN)
df = df[df.index >= common_start]

n_is = int((df.index < OOS_START).sum())
df_is, df_oos = df.iloc[:n_is].copy(), df.iloc[n_is:].copy()
oos_start = df_oos.index[0]

# Run baseline backtest on full dataset and separate slices
trades_all = eng.run_rsi2_backtest(df,     rsi_thr=RSI_THR, sma_len=SMA_LEN, exit_mode=EXIT_MODE, slip_bps_per_side=SLIP_BPS)
trades_is  = eng.run_rsi2_backtest(df_is,  rsi_thr=RSI_THR, sma_len=SMA_LEN, exit_mode=EXIT_MODE, slip_bps_per_side=SLIP_BPS)
trades_oos = eng.run_rsi2_backtest(df_oos, rsi_thr=RSI_THR, sma_len=SMA_LEN, exit_mode=EXIT_MODE, slip_bps_per_side=SLIP_BPS)

# Form ATR-sized trades DataFrame
trades_atr = trades_all.assign(pnl=trades_all['pnl_atr'], win=trades_all['pnl_atr'] > 0)
trades_is_atr = trades_is.assign(pnl=trades_is['pnl_atr'], win=trades_is['pnl_atr'] > 0)
trades_oos_atr = trades_oos.assign(pnl=trades_oos['pnl_atr'], win=trades_oos['pnl_atr'] > 0)

# Compute daily mark-to-market returns
ret_cap_is = eng.daily_returns(df_is, trades_is, sizing="capital")
ret_cap_oos = eng.daily_returns(df_oos, trades_oos, sizing="capital")
ret_atr_is = eng.daily_returns(df_is, trades_is, sizing="atr")
ret_atr_oos = eng.daily_returns(df_oos, trades_oos, sizing="atr")

eq_cap_oos = (1 + ret_cap_oos).cumprod()
eq_atr_oos = (1 + ret_atr_oos).cumprod()

oos_comparison = pd.DataFrame([
    {
        'Metric': 'Trades Count (N)',
        'IS (Capital)': len(trades_is),
        'OOS (Capital)': len(trades_oos),
        'IS (ATR 1% Risk)': len(trades_is_atr),
        'OOS (ATR 1% Risk)': len(trades_oos_atr)
    },
    {
        'Metric': 'Win Rate (%)',
        'IS (Capital)': f"{trades_is['win'].mean()*100:.1f}%",
        'OOS (Capital)': f"{trades_oos['win'].mean()*100:.1f}%",
        'IS (ATR 1% Risk)': f"{trades_is_atr['win'].mean()*100:.1f}%",
        'OOS (ATR 1% Risk)': f"{trades_oos_atr['win'].mean()*100:.1f}%"
    },
    {
        'Metric': 'Profit Factor',
        'IS (Capital)': f"{compute_metrics(trades_is, 1.0)['profit_factor']:.3f}",
        'OOS (Capital)': f"{compute_metrics(trades_oos, 1.0)['profit_factor']:.3f}",
        'IS (ATR 1% Risk)': f"{compute_metrics(trades_is_atr, 1.0)['profit_factor']:.3f}",
        'OOS (ATR 1% Risk)': f"{compute_metrics(trades_oos_atr, 1.0)['profit_factor']:.3f}"
    },
    {
        'Metric': 'Expectancy (% per trade)',
        'IS (Capital)': f"{trades_is['pnl'].mean():.3f}%",
        'OOS (Capital)': f"{trades_oos['pnl'].mean():.3f}%",
        'IS (ATR 1% Risk)': f"{trades_is_atr['pnl'].mean():.3f}%",
        'OOS (ATR 1% Risk)': f"{trades_oos_atr['pnl'].mean():.3f}%"
    },
    {
        'Metric': 'Sharpe Ratio (Daily MTM)',
        'IS (Capital)': f"{sharpe_ratio(ret_cap_is):.2f}",
        'OOS (Capital)': f"{sharpe_ratio(ret_cap_oos):.2f}",
        'IS (ATR 1% Risk)': f"{sharpe_ratio(ret_atr_is):.2f}",
        'OOS (ATR 1% Risk)': f"{sharpe_ratio(ret_atr_oos):.2f}"
    },
    {
        'Metric': 'Max Drawdown (Daily MTM)',
        'IS (Capital)': f"{max_drawdown((1+ret_cap_is).cumprod())*100:.2f}%",
        'OOS (Capital)': f"{max_drawdown(eq_cap_oos)*100:.2f}%",
        'IS (ATR 1% Risk)': f"{max_drawdown((1+ret_atr_is).cumprod())*100:.2f}%",
        'OOS (ATR 1% Risk)': f"{max_drawdown(eq_atr_oos)*100:.2f}%"
    }
])

print("=" * 80)
print("IN-SAMPLE VS. OUT-OF-SAMPLE PERFORMANCE COMPARISON")
print(f"OOS Period: {oos_start.strftime('%Y-%m-%d')} to {df_oos.index[-1].strftime('%Y-%m-%d')}")
print("=" * 80)
display(oos_comparison)

# Plot OOS Equity Curves
fig, ax = plt.subplots(figsize=(12, 5), facecolor='#15171c')
ax.set_facecolor('#1b1e26')
ax.grid(True, color='#2a2d37', linewidth=0.8, alpha=0.9)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(colors='#9aa0ab', labelsize=9)

ax.plot(df_oos.index, eq_cap_oos, color='#34d399', lw=1.6, label=f'OOS Capital Sizing (PF={compute_metrics(trades_oos, 1.0)["profit_factor"]:.2f})')
ax.plot(df_oos.index, eq_atr_oos, color='#5468ff', lw=1.6, label=f'OOS ATR 1% Risk Sizing (PF={compute_metrics(trades_oos_atr, 1.0)["profit_factor"]:.2f})')
ax.set_title(f'{TICKER} Out-of-Sample Performance ({oos_start.year} - {df_oos.index[-1].year})', color='#e8e9ec', fontweight='bold', fontsize=12, loc='left', pad=12)
ax.set_ylabel('Equity Multiplier', color='#9aa0ab', fontsize=9)
ax.legend(frameon=False, labelcolor='#9aa0ab', fontsize=9, loc='upper left')

plt.tight_layout()
plt.show()
```

    ================================================================================
    IN-SAMPLE VS. OUT-OF-SAMPLE PERFORMANCE COMPARISON
    OOS Period: 2018-09-24 to 2026-10-14
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
      <th>Metric</th>
      <th>IS (Capital)</th>
      <th>OOS (Capital)</th>
      <th>IS (ATR 1% Risk)</th>
      <th>OOS (ATR 1% Risk)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>Trades Count (N)</td>
      <td>237</td>
      <td>123</td>
      <td>237</td>
      <td>123</td>
    </tr>
    <tr>
      <th>1</th>
      <td>Win Rate (%)</td>
      <td>65.8%</td>
      <td>78.0%</td>
      <td>65.8%</td>
      <td>78.0%</td>
    </tr>
    <tr>
      <th>2</th>
      <td>Profit Factor</td>
      <td>1.875</td>
      <td>2.513</td>
      <td>1.905</td>
      <td>2.330</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Expectancy (% per trade)</td>
      <td>0.504%</td>
      <td>0.777%</td>
      <td>0.171%</td>
      <td>0.240%</td>
    </tr>
    <tr>
      <th>4</th>
      <td>Sharpe Ratio (Daily MTM)</td>
      <td>0.56</td>
      <td>1.01</td>
      <td>0.63</td>
      <td>0.95</td>
    </tr>
    <tr>
      <th>5</th>
      <td>Max Drawdown (Daily MTM)</td>
      <td>-21.79%</td>
      <td>-12.14%</td>
      <td>-6.69%</td>
      <td>-4.68%</td>
    </tr>
  </tbody>
</table>
</div>



    
![png](03_RSI2_Robustness_Testing_files/03_RSI2_Robustness_Testing_6_2.png)
    


## 3. WALK-FORWARD ANALYSIS (FIXED RULES: 3Y IS / 1Y OOS)


```python
wf_df = eng.walk_forward_fixed(
    df,
    rules={"rsi_thr": RSI_THR, "sma_len": SMA_LEN, "exit_mode": EXIT_MODE, "slip_bps_per_side": SLIP_BPS},
    is_years=3,
)

mean_is = wf_df['ret_is_anual'].mean()
mean_oos = wf_df['ret_oos'].mean()
efficiency = mean_oos / mean_is if mean_is > 0 else np.nan
pct_positive_years = (wf_df['ret_oos'] > 0).mean()
worst_oos_mdd = wf_df['mdd_oos'].min()

wf_pass = (efficiency >= 0.5) and (pct_positive_years >= 0.60) and (worst_oos_mdd > -0.20)

print("=" * 70)
print("WALK-FORWARD ANALYSIS SUMMARY (23 ROLLING WINDOWS)")
print("=" * 70)
print(f"Walk-Forward Efficiency (OOS Mean / IS Annual Mean) : {efficiency:.3f} (Threshold >= 0.50)")
print(f"Positive OOS Years Ratio                           : {pct_positive_years*100:.1f}% ({int(pct_positive_years*len(wf_df))}/{len(wf_df)}) (Threshold >= 60%)")
print(f"Worst Single-Year OOS Drawdown                     : {worst_oos_mdd*100:.2f}% (Threshold > -20%)")
print(f"Walk-Forward Gate Verdict                          : {'PASSED' if wf_pass else 'FAILED'}")
print("=" * 70)

display(wf_df)

# Plot Walk-Forward Annual Comparison
fig, ax = plt.subplots(figsize=(14, 5), facecolor='#15171c')
ax.set_facecolor('#1b1e26')
ax.grid(True, color='#2a2d37', linewidth=0.8, alpha=0.9)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(colors='#9aa0ab', labelsize=9)

x = np.arange(len(wf_df))
width = 0.35
ax.bar(x - width/2, wf_df['ret_is_anual']*100, width, label='IS Annualized Return (%)', color='#5468ff', alpha=0.8)
colors_oos = ['#34d399' if r > 0 else '#f0555a' for r in wf_df['ret_oos']]
ax.bar(x + width/2, wf_df['ret_oos']*100, width, label='OOS Return (%)', color=colors_oos, alpha=0.85)

ax.axhline(0, color='#9aa0ab', lw=0.8)
ax.set_xticks(x)
ax.set_xticklabels(wf_df['year'], rotation=45, color='#9aa0ab')
ax.set_title('Walk-Forward Rolling Performance by Calendar Year', color='#e8e9ec', fontweight='bold', fontsize=12, loc='left', pad=12)
ax.set_ylabel('Return (%)', color='#9aa0ab', fontsize=9)
ax.legend(frameon=False, labelcolor='#9aa0ab', fontsize=9, loc='upper left')

plt.tight_layout()
plt.show()
```

    ======================================================================
    WALK-FORWARD ANALYSIS SUMMARY (23 ROLLING WINDOWS)
    ======================================================================
    Walk-Forward Efficiency (OOS Mean / IS Annual Mean) : 1.092 (Threshold >= 0.50)
    Positive OOS Years Ratio                           : 69.6% (16/23) (Threshold >= 60%)
    Worst Single-Year OOS Drawdown                     : -13.76% (Threshold > -20%)
    Walk-Forward Gate Verdict                          : PASSED
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
      <th>year</th>
      <th>ret_is_anual</th>
      <th>ret_oos</th>
      <th>n_oos</th>
      <th>pf_oos</th>
      <th>mdd_oos</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>2003</td>
      <td>0.053904</td>
      <td>0.346181</td>
      <td>17</td>
      <td>55.503434</td>
      <td>-0.060834</td>
    </tr>
    <tr>
      <th>1</th>
      <td>2004</td>
      <td>0.115394</td>
      <td>-0.012037</td>
      <td>12</td>
      <td>0.910582</td>
      <td>-0.091110</td>
    </tr>
    <tr>
      <th>2</th>
      <td>2005</td>
      <td>0.109992</td>
      <td>-0.023869</td>
      <td>15</td>
      <td>0.737870</td>
      <td>-0.064510</td>
    </tr>
    <tr>
      <th>3</th>
      <td>2006</td>
      <td>0.088611</td>
      <td>0.125538</td>
      <td>15</td>
      <td>2.803900</td>
      <td>-0.077895</td>
    </tr>
    <tr>
      <th>4</th>
      <td>2007</td>
      <td>0.031152</td>
      <td>0.201285</td>
      <td>17</td>
      <td>4.791920</td>
      <td>-0.073731</td>
    </tr>
    <tr>
      <th>5</th>
      <td>2008</td>
      <td>0.121195</td>
      <td>-0.027189</td>
      <td>3</td>
      <td>0.259471</td>
      <td>-0.058119</td>
    </tr>
    <tr>
      <th>6</th>
      <td>2009</td>
      <td>0.080567</td>
      <td>-0.004374</td>
      <td>10</td>
      <td>0.958879</td>
      <td>-0.082296</td>
    </tr>
    <tr>
      <th>7</th>
      <td>2010</td>
      <td>0.032793</td>
      <td>0.039394</td>
      <td>14</td>
      <td>1.370149</td>
      <td>-0.104508</td>
    </tr>
    <tr>
      <th>8</th>
      <td>2011</td>
      <td>0.002237</td>
      <td>0.006199</td>
      <td>16</td>
      <td>1.081054</td>
      <td>-0.137553</td>
    </tr>
    <tr>
      <th>9</th>
      <td>2012</td>
      <td>0.020030</td>
      <td>0.069699</td>
      <td>17</td>
      <td>1.620209</td>
      <td>-0.088387</td>
    </tr>
    <tr>
      <th>10</th>
      <td>2013</td>
      <td>0.046320</td>
      <td>0.187517</td>
      <td>18</td>
      <td>18.844370</td>
      <td>-0.033108</td>
    </tr>
    <tr>
      <th>11</th>
      <td>2014</td>
      <td>0.092720</td>
      <td>0.092474</td>
      <td>20</td>
      <td>2.416030</td>
      <td>-0.087603</td>
    </tr>
    <tr>
      <th>12</th>
      <td>2015</td>
      <td>0.129252</td>
      <td>0.067713</td>
      <td>16</td>
      <td>2.331750</td>
      <td>-0.078940</td>
    </tr>
    <tr>
      <th>13</th>
      <td>2016</td>
      <td>0.118692</td>
      <td>-0.042984</td>
      <td>10</td>
      <td>0.620376</td>
      <td>-0.128075</td>
    </tr>
    <tr>
      <th>14</th>
      <td>2017</td>
      <td>0.022246</td>
      <td>0.129468</td>
      <td>15</td>
      <td>15.283590</td>
      <td>-0.035755</td>
    </tr>
    <tr>
      <th>15</th>
      <td>2018</td>
      <td>0.044411</td>
      <td>-0.081351</td>
      <td>10</td>
      <td>0.519173</td>
      <td>-0.104880</td>
    </tr>
    <tr>
      <th>16</th>
      <td>2019</td>
      <td>0.007840</td>
      <td>0.065418</td>
      <td>13</td>
      <td>1.856319</td>
      <td>-0.072676</td>
    </tr>
    <tr>
      <th>17</th>
      <td>2020</td>
      <td>0.044238</td>
      <td>0.307593</td>
      <td>14</td>
      <td>7.452406</td>
      <td>-0.092769</td>
    </tr>
    <tr>
      <th>18</th>
      <td>2021</td>
      <td>0.093267</td>
      <td>0.228037</td>
      <td>20</td>
      <td>4.498349</td>
      <td>-0.087212</td>
    </tr>
    <tr>
      <th>19</th>
      <td>2022</td>
      <td>0.240047</td>
      <td>-0.014994</td>
      <td>2</td>
      <td>0.503716</td>
      <td>-0.102392</td>
    </tr>
    <tr>
      <th>20</th>
      <td>2023</td>
      <td>0.174680</td>
      <td>0.190411</td>
      <td>20</td>
      <td>4.320275</td>
      <td>-0.053690</td>
    </tr>
    <tr>
      <th>21</th>
      <td>2024</td>
      <td>0.126647</td>
      <td>0.186263</td>
      <td>22</td>
      <td>2.378853</td>
      <td>-0.104672</td>
    </tr>
    <tr>
      <th>22</th>
      <td>2025</td>
      <td>0.126276</td>
      <td>0.063062</td>
      <td>15</td>
      <td>1.714010</td>
      <td>-0.107228</td>
    </tr>
  </tbody>
</table>
</div>



    
![png](03_RSI2_Robustness_Testing_files/03_RSI2_Robustness_Testing_8_2.png)
    


## 4. BLOCK MONTE CARLO BOOTSTRAP (10,000 SIMULATIONS)


```python
# Execute 10,000 circular block resamplings (block size = 5 trades)
# Drawdowns are measured on daily MTM: each simulated path concatenates the daily paths of the sampled trades.
paths_cap = eng.trade_mtm_paths(df, trades_all, sizing="capital")
paths_atr = eng.trade_mtm_paths(df, trades_all, sizing="atr")

mc_cap = monte_carlo_block(trades_all, n_sim=10000, block=5, mode="compound", seed=42, mtm_paths=paths_cap)
mc_atr = monte_carlo_block(trades_atr, n_sim=10000, block=5, mode="compound", seed=42, mtm_paths=paths_atr)

mc_summary = pd.DataFrame([
    {
        'Metric': 'Median Compound Return (p50)',
        'Capital Sizing': f"{mc_cap['ret_p50']*100:.1f}%",
        'ATR Sizing': f"{mc_atr['ret_p50']*100:.1f}%"
    },
    {
        'Metric': '5th Percentile Return (p5)',
        'Capital Sizing': f"{mc_cap['ret_p5']*100:.1f}%",
        'ATR Sizing': f"{mc_atr['ret_p5']*100:.1f}%"
    },
    {
        'Metric': 'Median Max Drawdown (mdd_p50)',
        'Capital Sizing': f"{mc_cap['mdd_p50']*100:.2f}%",
        'ATR Sizing': f"{mc_atr['mdd_p50']*100:.2f}%"
    },
    {
        'Metric': 'Worst 5% Drawdown (mdd_p5)',
        'Capital Sizing': f"{mc_cap['mdd_p5']*100:.2f}%",
        'ATR Sizing': f"{mc_atr['mdd_p5']*100:.2f}%"
    },
    {
        'Metric': 'Worst Simulation Drawdown',
        'Capital Sizing': f"{mc_cap['mdd_worst']*100:.2f}%",
        'ATR Sizing': f"{mc_atr['mdd_worst']*100:.2f}%"
    },
    {
        'Metric': 'Probability of Ruin (50% DD)',
        'Capital Sizing': f"{mc_cap['prob_ruin']*100:.2f}%",
        'ATR Sizing': f"{mc_atr['prob_ruin']*100:.2f}%"
    },
    {
        'Metric': 'Probability of Positive Return',
        'Capital Sizing': f"{mc_cap['prob_positive']*100:.2f}%",
        'ATR Sizing': f"{mc_atr['prob_positive']*100:.2f}%"
    }
])

print("=" * 70)
print("BLOCK MONTE CARLO SUMMARY (10,000 RUNS)")
print("=" * 70)
display(mc_summary)

# Plot Monte Carlo Drawdown Distribution
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), facecolor='#15171c')
for ax in (ax1, ax2):
    ax.set_facecolor('#1b1e26')
    ax.grid(True, color='#2a2d37', linewidth=0.8, alpha=0.9)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors='#9aa0ab', labelsize=9)

ax1.hist(mc_cap['mdds'] * 100, bins=50, color='#f0555a', alpha=0.75, edgecolor='#15171c')
ax1.axvline(mc_cap['mdd_p5'] * 100, color='#f5a524', ls='--', lw=1.5, label=f"5th Pct: {mc_cap['mdd_p5']*100:.1f}%")
ax1.axvline(mc_cap['mdd_p50'] * 100, color='#34d399', ls='-', lw=1.5, label=f"Median: {mc_cap['mdd_p50']*100:.1f}%")
ax1.set_title('Monte Carlo Max Drawdown (Capital Sizing)', color='#e8e9ec', fontweight='bold', fontsize=11, loc='left')
ax1.set_xlabel('Max Drawdown (%)', color='#9aa0ab')
ax1.legend(frameon=False, labelcolor='#9aa0ab', fontsize=9)

ax2.hist(mc_atr['mdds'] * 100, bins=50, color='#5468ff', alpha=0.75, edgecolor='#15171c')
ax2.axvline(mc_atr['mdd_p5'] * 100, color='#f5a524', ls='--', lw=1.5, label=f"5th Pct: {mc_atr['mdd_p5']*100:.1f}%")
ax2.axvline(mc_atr['mdd_p50'] * 100, color='#34d399', ls='-', lw=1.5, label=f"Median: {mc_atr['mdd_p50']*100:.1f}%")
ax2.set_title('Monte Carlo Max Drawdown (1% ATR Risk Sizing)', color='#e8e9ec', fontweight='bold', fontsize=11, loc='left')
ax2.set_xlabel('Max Drawdown (%)', color='#9aa0ab')
ax2.legend(frameon=False, labelcolor='#9aa0ab', fontsize=9)

plt.tight_layout()
plt.show()
```

    ======================================================================
    BLOCK MONTE CARLO SUMMARY (10,000 RUNS)
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
      <th>Metric</th>
      <th>Capital Sizing</th>
      <th>ATR Sizing</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>Median Compound Return (p50)</td>
      <td>685.9%</td>
      <td>100.0%</td>
    </tr>
    <tr>
      <th>1</th>
      <td>5th Percentile Return (p5)</td>
      <td>292.8%</td>
      <td>59.3%</td>
    </tr>
    <tr>
      <th>2</th>
      <td>Median Max Drawdown (mdd_p50)</td>
      <td>-21.79%</td>
      <td>-6.83%</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Worst 5% Drawdown (mdd_p5)</td>
      <td>-29.96%</td>
      <td>-10.29%</td>
    </tr>
    <tr>
      <th>4</th>
      <td>Worst Simulation Drawdown</td>
      <td>-44.17%</td>
      <td>-17.76%</td>
    </tr>
    <tr>
      <th>5</th>
      <td>Probability of Ruin (50% DD)</td>
      <td>0.00%</td>
      <td>0.00%</td>
    </tr>
    <tr>
      <th>6</th>
      <td>Probability of Positive Return</td>
      <td>100.00%</td>
      <td>100.00%</td>
    </tr>
  </tbody>
</table>
</div>



    
![png](03_RSI2_Robustness_Testing_files/03_RSI2_Robustness_Testing_10_2.png)
    


## 5. MONKEY TEST (2,000 SYNTHETIC RANDOM PORTFOLIOS)


```python
# Eligible filter condition: Close > SMA evaluated at t-1 (shifted by 1 for execution at open)
eligible = (df['close'] > df['sma']).shift(1)

mk = monkey_test(
    df=df,
    trades_df=trades_all,
    eligible=eligible,
    n_sim=2000,
    entry_col="open",
    exit_col="open",
    cost_pct_per_side=SLIP_BPS / 100.0, 
    seed=42
)

print("=" * 70)
print("MONKEY TEST RESULTS")
print("=" * 70)
print(f"Strategy Realized Profit Factor : {mk['pf_real']:.3f}")
print(f"Random Monkey Median PF         : {mk['pf_monkey_median']:.3f}")
print(f"Share of Monkeys Outperformed   : {mk['pct_pf']*100:.2f}% (Threshold >= 95.0%)")
print(f"Monkey Test Verdict             : {'PASSED' if mk['pct_pf'] >= 0.95 else 'FAILED'}")
print("=" * 70)

plot_monkey(mk, title=f"Monkey Test · {TICKER} RSI(2) vs 2,000 Random Filter-Eligible Portfolios")
```

    ======================================================================
    MONKEY TEST RESULTS
    ======================================================================
    Strategy Realized Profit Factor : 2.079
    Random Monkey Median PF         : 1.220
    Share of Monkeys Outperformed   : 100.00% (Threshold >= 95.0%)
    Monkey Test Verdict             : PASSED
    ======================================================================



    
![png](03_RSI2_Robustness_Testing_files/03_RSI2_Robustness_Testing_12_1.png)
    


## 6. STRESS TESTING: COSTS X2, WINDFALL EXCLUSION & CRISIS REGIMES


```python
print("=" * 70)
print("STRESS TESTING BATTERY")
print("=" * 70)

# 1. Costs x2 Stress (10 bps per side = 20 bps round trip)
trades_x2 = eng.run_rsi2_backtest(df, rsi_thr=RSI_THR, sma_len=SMA_LEN, exit_mode=EXIT_MODE, slip_bps_per_side=2 * SLIP_BPS)
m_x2 = compute_metrics(trades_x2, 1.0, 0.0)

# 2. Exclude 2 Best Windfall Years
trades_all['year'] = pd.to_datetime(trades_all['entry_time']).dt.year
annual_pnl = trades_all.groupby('year')['pnl'].sum()
top_2_years = annual_pnl.sort_values(ascending=False).head(2).index.tolist()
trades_ex_top = trades_all[~trades_all['year'].isin(top_2_years)]
m_ex_top = compute_metrics(trades_ex_top, 1.0, 0.0)

# 3. Crisis Regimes
regimes = {
    'Dot-Com Bust (2000-2002)': (2000, 2002),
    'Great Financial Crisis (2008)': (2008, 2008),
    'Rate Hike Bear Market (2022)': (2022, 2022)
}

stress_rows = [
    {
        'Stress Scenario': 'Baseline (5 bps / side)',
        'Trades': len(trades_all),
        'Win Rate': f"{trades_all['win'].mean()*100:.1f}%",
        'Profit Factor': f"{compute_metrics(trades_all, 1.0)['profit_factor']:.3f}",
        'Expectancy': f"{trades_all['pnl'].mean():.2f}%",
        'Notes': 'Standard trading friction'
    },
    {
        'Stress Scenario': 'Costs x2 (10 bps / side)',
        'Trades': len(trades_x2),
        'Win Rate': f"{trades_x2['win'].mean()*100:.1f}%",
        'Profit Factor': f"{m_x2['profit_factor']:.3f}",
        'Expectancy': f"{m_x2['expectancy']:.2f}%",
        'Notes': 'Severe liquidity friction test'
    },
    {
        'Stress Scenario': f"Exclude Best Years ({top_2_years[0]}, {top_2_years[1]})",
        'Trades': len(trades_ex_top),
        'Win Rate': f"{trades_ex_top['win'].mean()*100:.1f}%",
        'Profit Factor': f"{m_ex_top['profit_factor']:.3f}",
        'Expectancy': f"{m_ex_top['expectancy']:.2f}%",
        'Notes': 'Test resilience without top windfalls'
    }
]

for name, (start_y, end_y) in regimes.items():
    t_reg = trades_all[(trades_all['year'] >= start_y) & (trades_all['year'] <= end_y)]
    if len(t_reg) > 0:
        m_r = compute_metrics(t_reg, 1.0, 0.0)
        stress_rows.append({
            'Stress Scenario': name,
            'Trades': len(t_reg),
            'Win Rate': f"{t_reg['win'].mean()*100:.1f}%",
            'Profit Factor': f"{m_r['profit_factor']:.3f}",
            'Expectancy': f"{m_r['expectancy']:.2f}%",
            'Notes': 'Macro trend filter active'
        })
    else:
        stress_rows.append({
            'Stress Scenario': name,
            'Trades': 0,
            'Win Rate': 'N/A',
            'Profit Factor': 'N/A',
            'Expectancy': 'N/A',
            'Notes': '100% capital protected in cash'
        })

stress_df = pd.DataFrame(stress_rows)
display(stress_df)
```

    ======================================================================
    STRESS TESTING BATTERY
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
      <th>Stress Scenario</th>
      <th>Trades</th>
      <th>Win Rate</th>
      <th>Profit Factor</th>
      <th>Expectancy</th>
      <th>Notes</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>Baseline (5 bps / side)</td>
      <td>360</td>
      <td>70.3%</td>
      <td>2.079</td>
      <td>0.60%</td>
      <td>Standard trading friction</td>
    </tr>
    <tr>
      <th>1</th>
      <td>Costs x2 (10 bps / side)</td>
      <td>360</td>
      <td>68.9%</td>
      <td>1.852</td>
      <td>0.50%</td>
      <td>Severe liquidity friction test</td>
    </tr>
    <tr>
      <th>2</th>
      <td>Exclude Best Years (2003, 2020)</td>
      <td>329</td>
      <td>68.7%</td>
      <td>1.811</td>
      <td>0.48%</td>
      <td>Test resilience without top windfalls</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Dot-Com Bust (2000-2002)</td>
      <td>10</td>
      <td>60.0%</td>
      <td>2.049</td>
      <td>1.65%</td>
      <td>Macro trend filter active</td>
    </tr>
    <tr>
      <th>4</th>
      <td>Great Financial Crisis (2008)</td>
      <td>3</td>
      <td>33.3%</td>
      <td>0.104</td>
      <td>-2.74%</td>
      <td>Macro trend filter active</td>
    </tr>
    <tr>
      <th>5</th>
      <td>Rate Hike Bear Market (2022)</td>
      <td>2</td>
      <td>0.0%</td>
      <td>0.000</td>
      <td>-2.84%</td>
      <td>Macro trend filter active</td>
    </tr>
  </tbody>
</table>
</div>


## 7. EDGE DECAY & TEMPORAL STABILITY


```python
roll = rolling_pf(trades_all, window=40, cap=8.0, date_col="exit_time")
plot_rolling_pf(roll, oos_start=oos_start, window=40)

by_year = pf_by_year(trades_all, date_col="exit_time")
print("=" * 70)
print("ANNUAL PERFORMANCE BREAKDOWN")
print("=" * 70)
display(by_year.round(3))

decay_summary = edge_decay_summary(trades_all, last_n=3, date_col="exit_time")
print("=" * 70)
print("EDGE DECAY DIAGNOSTIC SUMMARY:")
print("=" * 70)
print(f"Historical PF (prior to last 3 years) : {decay_summary['historical']['pf']:.3f}")
print(f"Recent PF (last 3 full years)         : {decay_summary['recent']['pf']:.3f}")
print(f"Recent / Historical Expectancy Ratio  : {decay_summary['expectancy_ratio']:.3f}")
print(f"Edge Decay Warning Flag               : {decay_summary['warning']}")
print("=" * 70)
```


    
![png](03_RSI2_Robustness_Testing_files/03_RSI2_Robustness_Testing_16_0.png)
    


    ======================================================================
    ANNUAL PERFORMANCE BREAKDOWN
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
      <th>n</th>
      <th>pf</th>
      <th>expectancy</th>
      <th>win_rate</th>
      <th>total_pnl</th>
    </tr>
    <tr>
      <th>year</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2000</th>
      <td>10</td>
      <td>2.049</td>
      <td>1.650</td>
      <td>0.600</td>
      <td>16.502</td>
    </tr>
    <tr>
      <th>2003</th>
      <td>17</td>
      <td>55.503</td>
      <td>1.772</td>
      <td>0.882</td>
      <td>30.126</td>
    </tr>
    <tr>
      <th>2004</th>
      <td>12</td>
      <td>0.911</td>
      <td>-0.082</td>
      <td>0.500</td>
      <td>-0.978</td>
    </tr>
    <tr>
      <th>2005</th>
      <td>14</td>
      <td>0.674</td>
      <td>-0.223</td>
      <td>0.429</td>
      <td>-3.122</td>
    </tr>
    <tr>
      <th>2006</th>
      <td>16</td>
      <td>3.038</td>
      <td>0.859</td>
      <td>0.812</td>
      <td>13.738</td>
    </tr>
    <tr>
      <th>2007</th>
      <td>17</td>
      <td>4.792</td>
      <td>1.097</td>
      <td>0.765</td>
      <td>18.657</td>
    </tr>
    <tr>
      <th>2008</th>
      <td>3</td>
      <td>0.104</td>
      <td>-2.744</td>
      <td>0.333</td>
      <td>-8.232</td>
    </tr>
    <tr>
      <th>2009</th>
      <td>10</td>
      <td>0.959</td>
      <td>-0.030</td>
      <td>0.500</td>
      <td>-0.299</td>
    </tr>
    <tr>
      <th>2010</th>
      <td>14</td>
      <td>1.370</td>
      <td>0.299</td>
      <td>0.571</td>
      <td>4.182</td>
    </tr>
    <tr>
      <th>2011</th>
      <td>17</td>
      <td>1.223</td>
      <td>0.167</td>
      <td>0.706</td>
      <td>2.844</td>
    </tr>
    <tr>
      <th>2012</th>
      <td>17</td>
      <td>1.620</td>
      <td>0.422</td>
      <td>0.471</td>
      <td>7.178</td>
    </tr>
    <tr>
      <th>2013</th>
      <td>18</td>
      <td>18.844</td>
      <td>0.964</td>
      <td>0.889</td>
      <td>17.351</td>
    </tr>
    <tr>
      <th>2014</th>
      <td>20</td>
      <td>2.416</td>
      <td>0.452</td>
      <td>0.800</td>
      <td>9.037</td>
    </tr>
    <tr>
      <th>2015</th>
      <td>16</td>
      <td>1.865</td>
      <td>0.284</td>
      <td>0.500</td>
      <td>4.547</td>
    </tr>
    <tr>
      <th>2016</th>
      <td>10</td>
      <td>0.513</td>
      <td>-0.641</td>
      <td>0.500</td>
      <td>-6.413</td>
    </tr>
    <tr>
      <th>2017</th>
      <td>16</td>
      <td>15.976</td>
      <td>0.804</td>
      <td>0.812</td>
      <td>12.871</td>
    </tr>
    <tr>
      <th>2018</th>
      <td>11</td>
      <td>0.669</td>
      <td>-0.496</td>
      <td>0.545</td>
      <td>-5.456</td>
    </tr>
    <tr>
      <th>2019</th>
      <td>13</td>
      <td>1.856</td>
      <td>0.505</td>
      <td>0.615</td>
      <td>6.565</td>
    </tr>
    <tr>
      <th>2020</th>
      <td>14</td>
      <td>7.452</td>
      <td>1.957</td>
      <td>0.857</td>
      <td>27.400</td>
    </tr>
    <tr>
      <th>2021</th>
      <td>21</td>
      <td>4.589</td>
      <td>1.022</td>
      <td>0.810</td>
      <td>21.469</td>
    </tr>
    <tr>
      <th>2022</th>
      <td>2</td>
      <td>0.000</td>
      <td>-2.843</td>
      <td>0.000</td>
      <td>-5.685</td>
    </tr>
    <tr>
      <th>2023</th>
      <td>20</td>
      <td>4.320</td>
      <td>0.891</td>
      <td>0.850</td>
      <td>17.819</td>
    </tr>
    <tr>
      <th>2024</th>
      <td>21</td>
      <td>2.546</td>
      <td>0.865</td>
      <td>0.810</td>
      <td>18.160</td>
    </tr>
    <tr>
      <th>2025</th>
      <td>15</td>
      <td>2.105</td>
      <td>0.608</td>
      <td>0.867</td>
      <td>9.124</td>
    </tr>
    <tr>
      <th>2026</th>
      <td>16</td>
      <td>2.161</td>
      <td>0.503</td>
      <td>0.750</td>
      <td>8.053</td>
    </tr>
  </tbody>
</table>
</div>


    ======================================================================
    EDGE DECAY DIAGNOSTIC SUMMARY:
    ======================================================================
    Historical PF (prior to last 3 years) : 1.970
    Recent PF (last 3 full years)         : 2.777
    Recent / Historical Expectancy Ratio  : 1.429
    Edge Decay Warning Flag               : False
    ======================================================================


## 8. FULL VALIDATION GATE RUN (AUTOMATED MULTI-PHASE AUDIT)


```python
rsi_vals = RSI_VALUES
sma_vals = SMA_VALUES
is_dfs = {s: eng.prepare(df_raw, sma_len=s)[eng.prepare(df_raw, sma_len=s).index < oos_start] for s in sma_vals}

def evaluate_gate(rsi, sma):
    d = is_dfs[sma]
    t = eng.run_rsi2_backtest(d, rsi_thr=rsi, sma_len=sma, exit_mode=EXIT_MODE, slip_bps_per_side=SLIP_BPS)if len(t) == 0: return (0.0, 0)
    p = t['pnl'].values; g, l = p[p > 0].sum(), -p[p < 0].sum()
    return (float(g / l) if l > 0 else np.inf, int(len(t)))

pf_grid, n_grid = grid_search(evaluate_gate, rsi_vals, sma_vals)

# Run full validation gate on ATR-sized run (official determining run per Alphaca framework)
print("\n" + "=" * 70)
print("1. VALIDATION GATE: ATR-SIZED RUN (OFFICIAL VERDICT)")
print("=" * 70)
validation = run_validation(
    trades_df=trades_atr,
    df_prices=df,
    eligible=eligible,
    grid_pf=pf_grid,
    grid_n=n_grid,
    chosen=(int(RSI_THR), int(SMA_LEN)),
    oos_start=oos_start,
    mode="compound",
    mtm_paths=paths_atr,
    monkey_entry_col="open",
    monkey_exit_col="open",
    monkey_cost_pct_per_side=SLIP_BPS / 100.0,
    verbose=True
)

# Run validation gate on Capital-sized run for transparency
print("\n" + "=" * 70)
print("2. VALIDATION GATE: 100% CAPITAL SIZING RUN")
print("=" * 70)
validation_cap = run_validation(
    trades_df=trades_all,
    df_prices=df,
    eligible=eligible,
    grid_pf=pf_grid,
    grid_n=n_grid,
    chosen=(int(RSI_THR), int(SMA_LEN)),
    oos_start=oos_start,
    mode="compound",
    mtm_paths=paths_cap,
    monkey_entry_col="open",
    monkey_exit_col="open",
    monkey_cost_pct_per_side=SLIP_BPS / 100.0,
    verbose=True
)
```

    
    ======================================================================
    1. VALIDATION GATE: ATR-SIZED RUN (OFFICIAL VERDICT)
    ======================================================================
    ============================================================ 
    VALIDATION GATE
    ============================================================
    [PASS] 1_oos: {'n': 123, 'pf': np.float64(2.33), 'pf_without_best_trade': np.float64(2.225), 'max_dd': -0.047, 'dd_basis': 'mtm'}
    [PASS] 2_monte_carlo: {'ret_p5': 0.593, 'mdd_p5': -0.103, 'prob_ruin': 0.0, 'dd_basis': 'mtm'}
    [PASS] 3_monkey: {'pf_real': 2.049, 'pct_pf': 1.0}
    [PASS] 4_plateau: {'center_pf': 1.875, 'plateau': True, 'worst_drop_pct': 19.615}
    [INFO] 5_edge_decay: {'recent_pf': 2.909, 'historical_pf': 1.932, 'warning': False}
    ------------------------------------------------------------ 
    OVERALL: PASSED
    
    ======================================================================
    2. VALIDATION GATE: 100% CAPITAL SIZING RUN
    ======================================================================
    ============================================================ 
    VALIDATION GATE
    ============================================================
    [PASS] 1_oos: {'n': 123, 'pf': np.float64(2.513), 'pf_without_best_trade': np.float64(2.408), 'max_dd': -0.121, 'dd_basis': 'mtm'}
    [FAIL] 2_monte_carlo: {'ret_p5': 2.928, 'mdd_p5': -0.3, 'prob_ruin': 0.0, 'dd_basis': 'mtm'}
    [PASS] 3_monkey: {'pf_real': 2.079, 'pct_pf': 1.0}
    [PASS] 4_plateau: {'center_pf': 1.875, 'plateau': True, 'worst_drop_pct': 19.615}
    [INFO] 5_edge_decay: {'recent_pf': 2.777, 'historical_pf': 1.97, 'warning': False}
    ------------------------------------------------------------ 
    OVERALL: FAILED


## 9. STRATEGY METRICS DEFINITION & VERDICT


```python
# Required metrics dict for utils/validate_strategy.py and CI gatekeeper
# ATR-sized, whole dataset period (1999-2026)
ret_series_atr = eng.daily_returns(df, trades_all, sizing="atr")
eq_series_atr = (1.0 + ret_series_atr).cumprod()

metrics = {
    "sharpe": float(sharpe_ratio(ret_series_atr)),
    "max_drawdown": float(max_drawdown(eq_series_atr)),
    "num_trades": int(len(trades_all))
}

print("=" * 70)
print("FINAL STRATEGY METRICS (ATR SIZING, WHOLE PERIOD):")
print("=" * 70)
print(f"Sharpe Ratio  : {metrics['sharpe']:.2f}")
print(f"Max Drawdown  : {metrics['max_drawdown']*100:.2f}%")
print(f"Total Trades  : {metrics['num_trades']}")
print(f"Validation Gate Overall: {validation['status']}")
print("=" * 70)
```

    ======================================================================
    FINAL STRATEGY METRICS (ATR SIZING, WHOLE PERIOD):
    ======================================================================
    Sharpe Ratio  : 0.73
    Max Drawdown  : -6.69%
    Total Trades  : 360
    Validation Gate Overall: PASSED
    ======================================================================


## 10. VERDICT SUMMARY


```python
from IPython.display import Markdown, display
from validation_gate import DEFAULTS as GATE

V, C = validation["phases"], validation_cap["phases"]

def tag(p):
    if p.get("skipped"):
        return "SKIP"
    if p.get("informational"):
        return "INFO"
    return "PASS" if p["passed"] else "FAIL"

def res(name):
    a, c = tag(V[name]), tag(C[name])
    return f"**{a}**" if a == c else f"**{a}** (ATR) / **{c}** (Capital)"

p1a, p1c = V["1_oos"], C["1_oos"]
p2a, p2c = V["2_monte_carlo"], C["2_monte_carlo"]
p3a, p3c = V["3_monkey"], C["3_monkey"]
p4a = V["4_plateau"]
p5a = V["5_edge_decay"]

d1 = (f"OOS PF = {p1a['pf']:.3f} (ATR) / {p1c['pf']:.3f} (Capital), "
      f"{p1a['n']} trades (min. {GATE['n_min']}), "
      f"MDD {p1a['max_dd']*100:.2f}% / {p1c['max_dd']*100:.2f}% "
      f"(limit {GATE['mdd_min']*100:.0f}%, basis {p1a['dd_basis']})")

d2 = (f"p5 return {p2a['ret_p5']*100:.1f}% / {p2c['ret_p5']*100:.1f}% (must be > 0), "
      f"p5 MDD {p2a['mdd_p5']*100:.2f}% / {p2c['mdd_p5']*100:.2f}% (limit {GATE['mc_mdd_p5_min']*100:.0f}%), "
      f"prob. of ruin {p2a['prob_ruin']*100:.2f}% / {p2c['prob_ruin']*100:.2f}% "
      f"(max {GATE['mc_ruin_max']*100:.0f}%)")

if p3a.get("skipped") or p3c.get("skipped"):
    d3 = "Phase skipped (no price data provided)"
else:
    d3 = (f"Strategy beats {p3a['pct_pf']*100:.1f}% (ATR) / {p3c['pct_pf']*100:.1f}% (Capital) "
          f"of random filter-eligible entries (min. {GATE['monkey_pct_min']*100:.0f}%)")

if p4a.get("skipped"):
    d4 = "Phase skipped (no parameter grid provided)"
else:
    d4 = (f"3x3 plateau: {'yes' if p4a['plateau'] else 'no'}; center PF = {p4a['center_pf']:.3f}; "
          f"worst neighbor drop = {p4a['worst_drop_pct']:.1f}% (max {GATE['plateau_max_drop']}%)")

trend = "higher" if p5a["recent_pf"] > p5a["historical_pf"] else "lower"
d5 = (f"Recent PF ({p5a['recent_pf']:.3f}) is {trend} than historical PF ({p5a['historical_pf']:.3f}); "
      f"{'edge decay WARNING' if p5a['warning'] else 'no decay warning'}")

status, status_cap = validation["status"], validation_cap["status"]

if status == "PASSED":
    summary = (f"The Alphaca RSI(2) Mean Reversion strategy on {TICKER} daily bars passes every gating phase "
               "of the validation gate under ATR sizing (the official run).")
elif status == "INCOMPLETE":
    summary = ("No phase failed, but some phases were skipped: "
               f"{', '.join(validation['skipped'])}. An incomplete verdict does not count as a pass.")
else:
    failed = [n for n, p in V.items() if "passed" in p and not p["passed"]]
    summary = f"The validation gate FAILED under ATR sizing in: {', '.join(failed)}."

if status_cap != status:
    summary += f" Under 100% capital sizing the result is {status_cap}."

display(Markdown(f"""## 10. VERDICT SUMMARY

| Phase | Test Description | Result | Details |
| :--- | :--- | :---: | :--- |
| **Phase 1** | **Out-of-Sample Performance** | {res('1_oos')} | {d1} |
| **Phase 2** | **Block Monte Carlo (10k runs)** | {res('2_monte_carlo')} | {d2} |
| **Phase 3** | **Monkey Test (2,000 runs)** | {res('3_monkey')} | {d3} |
| **Phase 4** | **Parameter Plateau** | {res('4_plateau')} | {d4} |
| **Phase 5** | **Edge Decay Audit** | **INFO** | {d5} |

### OVERALL VERDICT (ATR, official): **{status}**  ·  Capital: **{status_cap}**

{summary}
"""))
```


## 10. VERDICT SUMMARY

| Phase | Test Description | Result | Details |
| :--- | :--- | :---: | :--- |
| **Phase 1** | **Out-of-Sample Performance** | **PASS** | OOS PF = 2.330 (ATR) / 2.513 (Capital), 123 trades (min. 30), MDD -4.68% / -12.14% (limit -20%, basis mtm) |
| **Phase 2** | **Block Monte Carlo (10k runs)** | **PASS** (ATR) / **FAIL** (Capital) | p5 return 59.3% / 292.8% (must be > 0), p5 MDD -10.29% / -29.96% (limit -25%), prob. of ruin 0.00% / 0.00% (max 5%) |
| **Phase 3** | **Monkey Test (2,000 runs)** | **PASS** | Strategy beats 100.0% (ATR) / 100.0% (Capital) of random filter-eligible entries (min. 95%) |
| **Phase 4** | **Parameter Plateau** | **PASS** | 3x3 plateau: yes; center PF = 1.875; worst neighbor drop = 19.6% (max 30%) |
| **Phase 5** | **Edge Decay Audit** | **INFO** | Recent PF (2.909) is higher than historical PF (1.932); no decay warning |

### OVERALL VERDICT (ATR, official): **PASSED**  ·  Capital: **FAILED**

The Alphaca RSI(2) Mean Reversion strategy on QQQ daily bars passes every gating phase of the validation gate under ATR sizing (the official run). Under 100% capital sizing the result is FAILED.




```python
import shutil
from variant_config import EDGE_DIR

# Daily returns and trades of the frozen run (needed later to compare variants)
ret_series_atr.rename("ret_atr").to_csv(RUN_DIR / "daily_returns_atr.csv")
eng.daily_returns(df, trades_all, sizing="capital").rename("ret_cap").to_csv(RUN_DIR / "daily_returns_capital.csv")
trades_all.to_csv(RUN_DIR / "trades_all.csv", index=False)

# Snapshot of the exact config used for this verdict
shutil.copy(EDGE_DIR / "variants" / f"{VARIANT}.yaml", RUN_DIR / "config_snapshot.yaml")

def _scalars(d):
    return {k: v for k, v in d.items() if v is None or isinstance(v, (int, float, str, bool, np.generic))}

save_json(cfg, "03_validation.json", {
    "variant": cfg["id"],
    "ticker": TICKER,
    "params": cfg["params"],
    "status_atr": validation["status"],
    "status_capital": validation_cap["status"],
    "metrics": metrics,
    "phases_atr": {name: _scalars(p) for name, p in validation["phases"].items()},
    "phases_capital": {name: _scalars(p) for name, p in validation_cap["phases"].items()},
})
```
