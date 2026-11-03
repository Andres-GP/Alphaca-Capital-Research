# 04 · MONDAY EFFECT · RECONCILIATION
**Alphaca Capital** · `MONDAY.btcjpy.cfd.v1` · vehicle: Axi BTC-JPY CFD, H1 candles.


```python
VARIANT = "v1_btcjpy"
HARD_LIMIT = 0.09
CAPITAL = 10_000.0
```

## CONFIG


```python
import sys
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
VOL_MODE, ATR_PCTL, ATR_LEN = P["vol_mode"], P["atr_pctl"], P["atr_len"]
SKIP1, ENTRY_HOUR, HOLD, COST_BPS = P["skip_first_monday"], P["entry_hour"], P["hold_bars"], P["cost_bps_per_side"]
SIZE_FRAC  = eng.ENGINE_DEFAULTS["size_fraction"]
CONTRACT_SIZE, MIN_LOT, LOT_STEP = (eng.ENGINE_DEFAULTS[k] for k in ("contract_size", "min_lot", "lot_step"))
PPY        = 365    # BTC trades every day: annualisation for Sharpe

# Frozen rules, passed as-is to every backtest call in this notebook
RULES = dict(vol_mode=VOL_MODE, atr_pctl=ATR_PCTL, atr_len=ATR_LEN, skip_first_monday=SKIP1,
             entry_hour=ENTRY_HOUR, hold_bars=HOLD, cost_bps_per_side=COST_BPS)

# ---- Acceptance thresholds: every PASS / FAIL in this notebook is judged against these ----
PF_MIN, T_MIN, N_MIN = 1.3, 2.0, 100      # hypothesis: Profit Factor, t-stat of the mean trade, number of trades
N_OOS_MIN            = 30                 # minimum OOS trades to say anything
ALPHA                = 0.05               # significance level of the statistical tests
MAX_SIGNAL_LOSS      = 0.05               # max share of Mondays without a valid signal bar (gaps / warm-up)
MIN_TRADES_PER_YEAR  = 5                  # every full calendar year should have at least this many trades
YEARS_POS_MIN        = 0.75               # share of full calendar years that must be profitable
REF_TOL_TRADES, REF_TOL_PF = 0.15, 0.25   # relative tolerance vs the published reference (Sanity Check 4)
REF_COST_BPS         = 14.0               # cost per side of the published reference (Binance spot)
FULL_HISTORY_YEARS   = 9.0                # years of history behind N_MIN (Binance 2017-2026); shorter data scales N_MIN down (section 3)

# ---- PASS / FAIL registry: each section registers its checks here, section 8 groups them ----
CHECKS = []

def check(section, name, passed, detail="", quiet=False):
    """Register one check. passed: True -> PASS, False -> FAIL, None -> SKIP (not applicable).
    Re-running a cell overwrites its previous entries instead of duplicating them."""
    status = "SKIP" if passed is None else ("PASS" if bool(passed) else "FAIL")
    entry = {"section": section, "name": name, "status": status, "detail": detail}
    for i, c in enumerate(CHECKS):
        if c["section"] == section and c["name"] == name:
            CHECKS[i] = entry
            break
    else:
        CHECKS.append(entry)
    if not quiet:
        print(f"   [{status}] {name}" + (f"  ->  {detail}" if detail else ""))
    return status

print("Imports complete.")
print(f"Loaded monday_effect_engine from: {eng.__file__}")
print(f"Edge dir: {EDGE_DIR}")
print(f"Variant: {cfg['id']} | {TICKER} | ATR({ATR_LEN})% >= P{ATR_PCTL:g} of {eng.ENGINE_DEFAULTS['pctl_window']} bars | "
      f"skip first Monday={SKIP1} | {COST_BPS:g} bps/side | size {SIZE_FRAC:.0%}")
print(f"Data source: {eng.ENGINE_DEFAULTS['data_source']} | swap: {eng.ENGINE_DEFAULTS['financing_bps_per_night']:g} bps/night")
print(f"CFD: contract {CONTRACT_SIZE:g} | min lot {MIN_LOT:g} | step {LOT_STEP:g} | capital {CAPITAL:,.0f} | hard limit -{HARD_LIMIT:.0%}")
print(f"Run folder: {RUN_DIR}")


df_raw = eng.load_data(TICKER, start=DATA_START)
print(len(df_raw), "hourly bars |", df_raw.index[0], "->", df_raw.index[-1])
print(df_raw.groupby(df_raw.index.year).size().to_dict())
_step_h = df_raw.index.to_series().diff().dt.total_seconds().div(3600).dropna()
print(f"Steps different from 1 h: {int((_step_h != 1).sum())} | largest gap: {_step_h.max():.0f} h")
if (_step_h.iloc[:48] > 1).any():
    print("WARNING: the first candles are not hourly (daily-resolution head). Set instrument.start in the YAML after that head.")

# Indicators are computed ONCE on the full history, so slicing IS/OOS keeps the percentile warm-up
df = eng.prepare(df_raw, atr_len=ATR_LEN, entry_hour=ENTRY_HOUR)

n_is = int((df.index < OOS_START).sum())
df_is, df_oos = df.iloc[:n_is].copy(), df.iloc[n_is:].copy()
assert len(df_is) > 0 and len(df_oos) > 0, "Check split.oos_start against the history of this ticker."
oos_start = df_oos.index[0]

mondays = df[df["entry_ok"]]

# Short history (Axi H1 starts in 2022-06): the trade-count threshold is scaled to the years of usable signals
_warm_end = df.index[min(len(df) - 1, eng.ENGINE_DEFAULTS["pctl_min_bars"] + ATR_LEN)]
_signal_years = (df.index[-1] - _warm_end).days / 365.25
if _signal_years < FULL_HISTORY_YEARS:
    N_MIN = max(30, int(round(N_MIN * _signal_years / FULL_HISTORY_YEARS)))

print("=" * 70)
print("DATA INGESTION & DATASET SPLIT")
print("=" * 70)
print(f"Total Prepared Bars: {len(df):,} ({df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d})")
print(f"In-Sample (IS, {len(df_is)/len(df)*100:.1f}%): {len(df_is):,} bars ({df_is.index.min():%Y-%m-%d} to {df_is.index.max():%Y-%m-%d})")
print(f"Out-of-Sample (OOS, {len(df_oos)/len(df)*100:.1f}%): {len(df_oos):,} bars ({df_oos.index.min():%Y-%m-%d} to {df_oos.index.max():%Y-%m-%d})")
print(f"Mondays with a valid signal bar: {len(mondays)} | with percentile warm-up done: {int(mondays['atr_rank'].notna().sum())}")
print(f"Years with the percentile warm-up done: {_signal_years:.1f} | N_MIN (full period) = {N_MIN} | N_OOS_MIN = {N_OOS_MIN}")
print("=" * 70)

# ---- PASS / FAIL ----
print("CHECKS (section 3):")
# Mondays AFTER the percentile warm-up (the warm-up itself is not a data loss)
exp_mondays = len(pd.date_range(_warm_end.normalize(), df.index[-1].normalize(), freq="W-MON"))
lost = exp_mondays - int((mondays.index >= _warm_end).sum())
check("3. Data", "IS and OOS are both non-empty", len(df_is) > 0 and len(df_oos) > 0,
      f"IS {len(df_is):,} bars | OOS {len(df_oos):,} bars")
check("3. Data", f"Mondays without a valid signal bar <= {MAX_SIGNAL_LOSS:.0%}", lost / exp_mondays <= MAX_SIGNAL_LOSS,
      f"{lost} of {exp_mondays} Mondays lost to gaps ({lost / exp_mondays:.1%})")
df[["open", "high", "low", "close", "atr_pct"]].tail()




trades_is  = eng.run_monday_backtest(df_is,  **RULES)
trades_oos = eng.run_monday_backtest(df_oos, **RULES)
trades_all = eng.run_monday_backtest(df,     **RULES)



df_raw = eng.load_data(TICKER, start=DATA_START)
print(len(df_raw), "hourly bars |", df_raw.index[0], "->", df_raw.index[-1])
print(df_raw.groupby(df_raw.index.year).size().to_dict())
_step_h = df_raw.index.to_series().diff().dt.total_seconds().div(3600).dropna()
print(f"Steps different from 1 h: {int((_step_h != 1).sum())} | largest gap: {_step_h.max():.0f} h")
if (_step_h.iloc[:48] > 1).any():
    print("WARNING: the first candles are not hourly (daily-resolution head). Set instrument.start in the YAML after that head.")

# Indicators are computed ONCE on the full history, so slicing IS/OOS keeps the percentile warm-up
df = eng.prepare(df_raw, atr_len=ATR_LEN, entry_hour=ENTRY_HOUR)
```

    Imports complete.
    Loaded monday_effect_engine from: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Monday_Effect/monday_effect_engine.py
    Edge dir: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Monday_Effect
    Variant: MONDAY.btcjpy.cfd.v1 | btcjpy | ATR(24)% >= P40 of 8760 bars | skip first Monday=True | 5.5 bps/side | size 20%
    Data source: csv_hourly | swap: 4.11 bps/night
    CFD: contract 1 | min lot 0.01 | step 0.01 | capital 10,000 | hard limit -9%
    Run folder: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Monday_Effect/runs/v1_btcjpy
    WARNING: 43 saltos distintos de 1 h en el indice (huecos). Los lunes con hueco se descartan.
    38052 hourly bars | 2022-06-17 21:00:00 -> 2026-10-24 18:00:00
    {2022: 4699, 2023: 8721, 2024: 8772, 2025: 8752, 2026: 7108}
    Steps different from 1 h: 43 | largest gap: 24 h
    WARNING: the first candles are not hourly (daily-resolution head). Set instrument.start in the YAML after that head.
    ======================================================================
    DATA INGESTION & DATASET SPLIT
    ======================================================================
    Total Prepared Bars: 38,052 (2022-06-17 to 2026-10-24)
    In-Sample (IS, 35.7%): 13,588 bars (2022-06-17 to 2024-01-07)
    Out-of-Sample (OOS, 64.3%): 24,464 bars (2024-01-08 to 2026-10-24)
    Mondays with a valid signal bar: 227 | with percentile warm-up done: 201
    Years with the percentile warm-up done: 3.8 | N_MIN (full period) = 43 | N_OOS_MIN = 30
    ======================================================================
    CHECKS (section 3):
       [PASS] IS and OOS are both non-empty  ->  IS 13,588 bars | OOS 24,464 bars
       [PASS] Mondays without a valid signal bar <= 5%  ->  0 of 201 Mondays lost to gaps (0.0%)
    WARNING: 43 saltos distintos de 1 h en el indice (huecos). Los lunes con hueco se descartan.
    38052 hourly bars | 2022-06-17 21:00:00 -> 2026-10-24 18:00:00
    {2022: 4699, 2023: 8721, 2024: 8772, 2025: 8752, 2026: 7108}
    Steps different from 1 h: 43 | largest gap: 24 h
    WARNING: the first candles are not hourly (daily-resolution head). Set instrument.start in the YAML after that head.


## RECONCILIATION


```python
import pandas as pd

ref = df.loc[df["entry_ok"], ["atr_sig", "atr_rank"]].copy()
ref["take"] = ref.index.isin(trades_all["entry_time"])      # lunes en los que el motor opera

log = pd.read_csv(r"../../data/Reconcilation/Monday_Effect/monday_log.csv", sep=";", header=None,
                  names=["time", "atr", "rank", "decision", "reason"],
                  parse_dates=["time"]).set_index("time")

print("lunes duplicados en el log:", log.index.duplicated().sum())    # debe ser 0
log = log[~log.index.duplicated(keep="last")]

print("operaciones del EA:", (log["decision"] == "BUY").sum(), "| del motor:", len(trades_all))

j = ref.merge(log, left_index=True, right_index=True, how="outer", indicator=True)
print(j["_merge"].value_counts())

both = j[j["_merge"] == "both"]
print("dif max ATR%  :", (both["atr_sig"] - both["atr"]).abs().max())
print("dif max rango :", (both["atr_rank"] - both["rank"]).abs().max())

print("\nLunes que están solo en un lado:")
print(j[j["_merge"] != "both"][["take", "decision", "reason", "_merge"]])

bad = both[both["take"] != both["decision"].eq("BUY")]
print("\ndecisiones distintas:", len(bad))
bad[["atr_sig", "atr", "atr_rank", "rank", "take", "decision", "reason"]]
```

    lunes duplicados en el log: 0
    operaciones del EA: 53 | del motor: 54
    _merge
    both          227
    left_only       0
    right_only      0
    Name: count, dtype: int64
    dif max ATR%  : 2.634877116225072
    dif max rango : 0.06280193730407513
    
    Lunes que están solo en un lado:
    Empty DataFrame
    Columns: [take, decision, reason, _merge]
    Index: []
    
    decisiones distintas: 1





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
      <th>atr_sig</th>
      <th>atr</th>
      <th>atr_rank</th>
      <th>rank</th>
      <th>take</th>
      <th>decision</th>
      <th>reason</th>
    </tr>
    <tr>
      <th>time</th>
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
      <th>2023-01-16</th>
      <td>0.785039</td>
      <td>0.785039</td>
      <td>0.414813</td>
      <td>0.382461</td>
      <td>True</td>
      <td>SKIP</td>
      <td>atr low</td>
    </tr>
  </tbody>
</table>
</div>




```python
valid = both[both["atr_rank"].notna() & (both["rank"] >= 0)]
d_atr = (valid["atr_sig"] - valid["atr"]).abs()
d_rk  = (valid["atr_rank"] - valid["rank"]).abs()

print("lunes con percentil válido en ambos:", len(valid))
print("dif ATR  > 1e-4  :", (d_atr > 1e-4).sum(), "| máx:", d_atr.max())
print("dif rango > 1e-3 :", (d_rk > 1e-3).sum(), "| máx:", d_rk.max())

out = valid.assign(d_atr=d_atr, d_rk=d_rk)
print(out.loc[(d_rk > 1e-3) | (d_atr > 1e-4),
              ["atr_sig", "atr", "atr_rank", "rank", "d_rk", "take", "decision"]])

warm = both[both["reason"] == "no history"]
print("\nlunes de calentamiento en el EA:", len(warm), "|", warm.index.min(), "->", warm.index.max())
```

    lunes con percentil válido en ambos: 201
    dif ATR  > 1e-4  : 4 | máx: 0.02692018577926336
    dif rango > 1e-3 : 27 | máx: 0.06280193730407513
                 atr_sig       atr  atr_rank      rank      d_rk   take decision
    time                                                                        
    2022-12-19  0.323618  0.323618  0.020050  0.018276  0.001774  False     SKIP
    2023-01-09  0.286456  0.286456  0.032251  0.029656  0.002595  False     SKIP
    2023-01-16  0.785039  0.785039  0.414813  0.382461  0.032352   True     SKIP
    2023-01-23  0.868899  0.868899  0.484819  0.448135  0.036684   True      BUY
    2023-01-30  0.897811  0.897811  0.515823  0.477923  0.037900   True      BUY
    2023-02-06  0.587419  0.587419  0.246209  0.228629  0.017580  False     SKIP
    2023-02-13  0.472350  0.472350  0.149089  0.138735  0.010354  False     SKIP
    2023-02-20  0.830404  0.830404  0.461368  0.430181  0.031187   True      BUY
    2023-02-27  0.603328  0.603328  0.256784  0.239876  0.016908  False     SKIP
    2023-03-06  0.460048  0.460048  0.133451  0.124887  0.008564  False     SKIP
    2023-03-13  1.611530  1.584610  0.935580  0.872778  0.062802   True      BUY
    2023-03-20  1.099382  1.099382  0.725565  0.681290  0.044275   True      BUY
    2023-03-27  0.827286  0.827286  0.444610  0.418172  0.026438   True      BUY
    2023-04-03  0.642570  0.642570  0.281087  0.264670  0.016417  False     SKIP
    2023-04-10  0.535867  0.535867  0.191293  0.180372  0.010921  False     SKIP
    2023-04-17  0.456719  0.456719  0.130471  0.123186  0.007285  False     SKIP
    2023-04-24  0.719157  0.719157  0.360855  0.341139  0.019716  False     SKIP
    2023-05-01  0.689781  0.689781  0.334304  0.316422  0.017882  False     SKIP
    2023-05-08  0.731601  0.731601  0.367944  0.348792  0.019152  False     SKIP
    2023-05-15  0.531537  0.531537  0.183097  0.173699  0.009398  False     SKIP
    2023-05-22  0.440507  0.440507  0.112779  0.107105  0.005674  False     SKIP
    2023-05-29  0.630480  0.630480  0.280263  0.266436  0.013827  False     SKIP
    2023-06-05  0.620206  0.620206  0.273344  0.261986  0.011358  False     SKIP
    2023-06-12  0.544442  0.544442  0.196987  0.192580  0.004407  False     SKIP
    2024-03-11  0.991122  0.985439  0.815525  0.810959  0.004566   True      BUY
    2025-03-10  1.208078  1.198916  0.805822  0.802397  0.003425   True      BUY
    2026-03-09  0.734905  0.726083  0.624886  0.615525  0.009361   True      BUY
    
    lunes de calentamiento en el EA: 19 | 2022-06-20 00:00:00 -> 2022-11-28 00:00:00

