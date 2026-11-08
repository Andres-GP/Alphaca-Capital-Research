# 1. GOTOBI USDJPY - HYPOTHESIS DEFINITION & BASELINE BACKTEST

This notebook formulates the quantitative hypothesis and establishes the baseline backtest for the **Gotobi effect** on **5-minute Axi USDJPY CFD bars (UTC, converted from the MT5 server time)**.

### 1.1 CORE QUANTITATIVE HYPOTHESIS

- **Payment-day flow**: on Japanese _gotobi_ days (the 5th, 10th, 15th, 20th, 25th and the last day of the month) Japanese importers settle in USD before the **09:55 JST Tokyo fixing**. The structural USD demand should lift USDJPY between the Tokyo open and the fixing. Tested by window return in section 4.1.
- **Only on gotobi days**: the same window on the neighbouring business days (placebos at -2, -1, +1, +2) should show no comparable drift. If it does, the edge is a Tokyo-morning effect, not a gotobi effect. Tested in section 4.2.
- **Not one day driving the result**: the effect should be spread across the six payment dates, not carried by a single one. Tested in section 4.3.
- **Shifted days are still gotobi days**: when a payment day falls on a weekend or holiday, settlement moves to the previous business day, so the shifted days should carry the effect too. Tested in section 4.4.

### 1.2 FROZEN STRATEGY RULES

| Rule Component      | Specification                                                                                                                                    |
| :------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Instrument**      | USDJPY CFD (Axi), 5-minute bars (UTC), Axi MT5 history                                                                                           |
| **Calendar Filter** | JST day-of-month in {5, 10, 15, 20, 25} or last calendar day of the month                                                                        |
| **Shift**           | If the gotobi day is not a business day, trade the **previous** business day                                                                     |
| **Entry**           | Buy at the **OPEN** of the 07:30 JST bar (22:30 UTC of the previous calendar day)                                                                |
| **Exit**            | Sell at the **OPEN** of the 09:55 JST bar (00:55 UTC), the Tokyo fixing                                                                          |
| **Direction**       | Long only, **no stop, no take profit** (position size is the risk management)                                                                    |
| **Trading Costs**   | Feed spread x `spread_scale` per trade (placeholder until the real Axi spread at 22:30 UTC is measured); robustness with a flat 0.7 and 1.0 pips |
| **Position Sizing** | (a) **100 % of capital** (per-trade reference) - (b) **`size_fraction` of capital** (what the robot trades)                                      |

### 1.3 PROVENANCE & VALIDATION DESIGN

- **Naked window**: the same 07:30-09:55 JST window on every business day, no calendar filter. The control group for everything below.
- **Placebo windows**: the gotobi rule moved by -2, -1, +1 and +2 business days.
- **Multiple testing**: 16 hypotheses were tested while building this variant, so the acceptance bar for the net t-stat is raised to `min_t_net` (2.5) instead of the usual 2.0.
- **Split**: IS 2010-2022, OOS from 2023-01-01. Indicators are not used, so nothing is fitted in-sample: IS and OOS differ only in the period.

> **HOLIDAY NOTE**: the calendar rebuilt in this notebook uses the same definition of _Japanese bank business day_ as the engine (Mon-Fri, not a holiday of the `holidays` package, not 31 Dec / 1-3 Jan), month-end included, but it is written independently (plain `datetime`, no numpy `busday`). On a Japanese holiday the FX market still trades, the payment day just moves. Section 6 compares the dates the engine trades with the dates rebuilt here.

### 1.4 STRATEGY PARAMETERS

```python
VARIANT = "v1_axi_usdjpy"
```

## 2. IMPORTS AND CONFIG

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

EDGE_DIR   = find_edge_dir()                           # edge folder (notebooks, engine and variants/ live together)
utils_path = str(find_upwards('utils') / 'utils')      # research_development/utils
for p in (utils_path, str(EDGE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils import compute_metrics
from metrics import sharpe_ratio, max_drawdown
import gotobi_engine as eng
import variant_config
from variant_config import load_variant, save_json

importlib.reload(eng)   # resets ENGINE_DEFAULTS: nothing leaks between variants

variant_config.EDGE_DIR = EDGE_DIR
assert (variant_config.EDGE_DIR / "variants").is_dir(), f"Doesn't exist {variant_config.EDGE_DIR / 'variants'}"

# ---- Variant config: single source of truth ----
cfg        = load_variant(VARIANT)
eng.set_engine_defaults(**cfg.get("engine_defaults", {}))
eng.apply_cfd_preset(cfg["account"]["cfd_preset"])           # contract size / min lot / lot step of the YAML preset
eng.set_engine_defaults(account_ccy=cfg["account"]["ccy"])
RUN_DIR    = cfg["run_dir"]
TICKER     = cfg["instrument"].get("ticker", cfg["instrument"].get("symbol"))
DATA_START = cfg["instrument"]["start"]
OOS_START  = cfg["oos_start_ts"]
P          = cfg["params"]
GOTOBI_DAYS = P["gotobi_days"]
SHIFT      = P.get("shift", P.get("shift_rule"))
ENTRY_JST  = P.get("entry_jst", P.get("entry_time_jst"))
EXIT_JST   = P.get("exit_jst", P.get("exit_time_jst"))
PLACEBOS   = cfg.get("placebo_offsets_bdays", P.get("placebo_offsets", [-2, -1, 1, 2]))
COST_MODE, SPREAD_SCALE = cfg["costs"]["cost_mode"], cfg["costs"]["spread_scale"]
FLAT_PIPS  = cfg["costs"].get("robustness_flat_pips", cfg["costs"].get("robustness", {}).get("flat_spread_pips", [0.7, 1.0]))
EV         = cfg.get("evidence", cfg.get("evidence_thresholds", {}))
HARD_LIMIT = float(cfg.get("risk", {}).get("hard_limit", EV.get("hard_limit", 0.10)))
CAPITAL    = float(cfg.get("account", {}).get("capital", EV.get("capital", 10000.0)))
SIZE_FRAC  = eng.ENGINE_DEFAULTS["size_fraction"]
CONTRACT_SIZE, MIN_LOT, LOT_STEP = (eng.ENGINE_DEFAULTS[k] for k in ("contract_size", "min_lot", "lot_step"))
PPY        = 252    # FX trades on business days: annualisation for Sharpe
PIP        = 0.01   # USDJPY pip size

# Frozen rules, passed as-is to every backtest call in this notebook.
# NOTE: run_gotobi_backtest() and prepare() do not share argument names (gotobi_days vs days, cost_mode only in the backtest)
INCLUDE_EOM = bool(P.get("include_month_end", True))
RULES = dict(gotobi_days=GOTOBI_DAYS, include_month_end=INCLUDE_EOM, shift_rule=SHIFT, entry_time=ENTRY_JST,
             exit_time=EXIT_JST, cost_mode=COST_MODE, spread_scale=SPREAD_SCALE)           # -> run_gotobi_backtest(df, **RULES)
PREP_RULES = dict(days=GOTOBI_DAYS, include_month_end=INCLUDE_EOM, shift_rule=SHIFT, entry_time=ENTRY_JST,
                  exit_time=EXIT_JST, spread_scale=SPREAD_SCALE)                          # -> prepare(df_raw, **PREP_RULES)

# Return-series helpers: the engine shares the API of monday_effect_engine; the per-bar series may be named differently
bar_returns = getattr(eng, "bar_returns", getattr(eng, "hourly_returns", None))
assert bar_returns is not None, "gotobi_engine needs bar_returns() or hourly_returns()"

# ---- Acceptance thresholds: read from the YAML (`acceptance`), declared BEFORE looking at results ----
ACC = cfg["acceptance"]
_share = lambda x: x / 100 if x > 1 else float(x)         # accepts 0.2 or 20 (%)
PF_MIN, T_MIN, N_MIN = float(ACC["pf_min"]), float(EV["min_t_net"]), int(ACC["n_min"])   # PF, net t of the mean trade (raised for the hypotheses tested), trades
N_OOS_MIN            = int(ACC["n_oos_min"])               # minimum OOS trades to say anything
T_OOS_MIN            = float(ACC["t_oos_min"])             # one-sided 5 %: minimum net t of the OOS trades
ALPHA                = float(ACC["alpha"])                 # significance level of the statistical tests
T_PLACEBO_MAX        = 2.0                                 # (not in the YAML) a placebo window with t above this means the effect is not specific to gotobi
MAX_SIGNAL_LOSS      = _share(float(ACC["max_signal_loss"]))   # max share of expected gotobi dates without a tradable window (gaps)
TPY_LO, TPY_HI       = (int(v) for v in ACC["trades_per_year"])   # trades expected in a full calendar year
YEARS_POS_MIN        = _share(float(ACC["years_pos_min"]))     # share of full calendar years that must be profitable

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
print(f"Loaded gotobi_engine from: {eng.__file__}")
print(f"Edge dir: {EDGE_DIR}")
print(f"Variant: {cfg['id']} | {TICKER} M5 | gotobi days {GOTOBI_DAYS} | shift={SHIFT} | {ENTRY_JST}-{EXIT_JST} JST | size {SIZE_FRAC:.0%}")
print(f"Costs: {COST_MODE} x {SPREAD_SCALE:g} | robustness flat pips {FLAT_PIPS} | hypotheses tested {EV['hypotheses_tested']} -> min net t = {T_MIN:g}")
print(f"CFD: contract {CONTRACT_SIZE:g} | min lot {MIN_LOT:g} | step {LOT_STEP:g} | capital {CAPITAL:,.0f} | hard limit -{HARD_LIMIT:.0%}")
print(f"Run folder: {RUN_DIR}")
```

    Imports complete.
    Loaded gotobi_engine from: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/gotobi_engine.py
    Edge dir: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi
    Variant: GOTOBI.usdjpy.cfd.v1 | USDJPY M5 | gotobi days [5, 10, 15, 20, 25] | shift=previous | 07:30-09:55 JST | size 250%
    Costs: feed x 0.7 | robustness flat pips [0.7, 1.0] | hypotheses tested 17 -> min net t = 2.5
    CFD: contract 100000 | min lot 0.01 | step 0.01 | capital 10,000 | hard limit -9%
    Run folder: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy

## 3. LOAD DATA AND IN-SAMPLE / OUT-OF-SAMPLE

```python
df_raw = eng.load_data(TICKER, start=DATA_START)
print(len(df_raw), "M5 bars |", df_raw.index[0], "->", df_raw.index[-1])
print(df_raw.groupby(df_raw.index.year).size().to_dict())
_step_m = df_raw.index.to_series().diff().dt.total_seconds().div(60).dropna()
print(f"Steps different from 5 min: {int((_step_m != 5).sum())} | largest gap: {_step_m.max() / 60:.1f} h")

# The engine adds whatever it needs (window open/close, spread, gotobi flag) in prepare()
df = eng.prepare(df_raw, **PREP_RULES)

df_is, df_oos = eng.split_df(df, OOS_START)      # cut at the JST midnight of OOS_START: no position is open at that instant
assert len(df_is) > 0 and len(df_oos) > 0, "Check split.oos_start against the history of this ticker."
oos_start = df_oos.index[0]

# ---- Gotobi calendar rebuilt in this notebook (JST dates), independent of the engine ----
import datetime as _dt
import holidays as _holidays

def gotobi_calendar_nb(start, end, days=GOTOBI_DAYS, eom=INCLUDE_EOM, shift=SHIFT):
    """Gotobi trade dates (JST) rebuilt with plain datetime (independent of the engine's numpy busday).
    Nominal dates: `days` + last day of the month. Business day = Mon-Fri, not a Japanese holiday, not 31 Dec / 1-3 Jan.
    A nominal date that is not a business day moves to the previous (or next) business day; two nominal dates landing
    on the same day count once. Returns a DataFrame indexed by date with columns label, shifted, nominal."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    jp = _holidays.Japan(years=range(start.year - 1, end.year + 2))
    def is_bday(d):
        return d.weekday() < 5 and d not in jp and not ((d.month == 1 and d.day <= 3) or (d.month == 12 and d.day == 31))
    rows = {}
    for m in pd.period_range(pd.Period(start, "M") - 1, pd.Period(end, "M") + 1, freq="M"):
        last = m.days_in_month
        nominal = [(str(int(d)), _dt.date(m.year, m.month, min(int(d), last))) for d in days]
        if eom:
            nominal.append(("EOM", _dt.date(m.year, m.month, last)))
        for lab, nom in nominal:
            d = nom
            if shift == "previous":
                while not is_bday(d):
                    d -= _dt.timedelta(days=1)
            elif shift == "next":
                while not is_bday(d):
                    d += _dt.timedelta(days=1)
            elif not is_bday(d):
                continue
            key = pd.Timestamp(d)
            if key not in rows or nom < rows[key][2]:            # same trade date from two nominal dates: keep the earliest
                rows[key] = (lab, d != nom, nom)
    cal = pd.DataFrame.from_dict(rows, orient="index", columns=["label", "shifted", "nominal"]).sort_index()
    cal.index.name = "date"
    return cal

def window_times(jst_date):
    """UTC timestamps of the entry and exit bars for a JST trade date (JST = UTC+9, no DST)."""
    t_in  = pd.Timestamp(f"{jst_date:%Y-%m-%d} {ENTRY_JST}") - pd.Timedelta(hours=9)
    t_out = pd.Timestamp(f"{jst_date:%Y-%m-%d} {EXIT_JST}")  - pd.Timedelta(hours=9)
    return t_in, t_out

def tstat(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan

def window_returns(jst_dates):
    """Gross open-to-open return (%) of the 07:30-09:55 JST window for each JST date that has both bars."""
    o = df_raw["open"]
    rows = []
    for d in jst_dates:
        t_in, t_out = window_times(d)
        if t_in in o.index and t_out in o.index:
            rows.append((d, (o.at[t_out] / o.at[t_in] - 1) * 100, o.at[t_in]))
    return pd.DataFrame(rows, columns=["jst_date", "ret", "price_in"]).set_index("jst_date")

START_D = max(pd.Timestamp(DATA_START), df_raw.index[0].normalize() + pd.Timedelta(days=2))
END_D   = df_raw.index[-1].normalize() - pd.Timedelta(days=1)
G_CAL   = gotobi_calendar_nb(START_D, END_D)
G_CAL   = G_CAL[(G_CAL.index >= START_D) & (G_CAL.index <= END_D)]
G_DATES = G_CAL.index
g_win = window_returns(G_DATES)

print("=" * 70)
print("DATA INGESTION & DATASET SPLIT")
print("=" * 70)
print(f"Total Prepared Bars: {len(df):,} ({df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d})")
print(f"In-Sample (IS, {len(df_is)/len(df)*100:.1f}%): {len(df_is):,} bars ({df_is.index.min():%Y-%m-%d} to {df_is.index.max():%Y-%m-%d})")
print(f"Out-of-Sample (OOS, {len(df_oos)/len(df)*100:.1f}%): {len(df_oos):,} bars ({df_oos.index.min():%Y-%m-%d} to {df_oos.index.max():%Y-%m-%d})")
print(f"Gotobi dates expected: {len(G_DATES)} | with both window bars present: {len(g_win)}")
print("=" * 70)

print("CHECKS (section 3):")
lost = len(G_DATES) - len(g_win)
check("3. Data", "IS and OOS are both non-empty", len(df_is) > 0 and len(df_oos) > 0, f"IS {len(df_is):,} bars | OOS {len(df_oos):,} bars")
check("3. Data", f"Gotobi dates without a tradable window <= {MAX_SIGNAL_LOSS:.0%}", lost / len(G_DATES) <= MAX_SIGNAL_LOSS,
      f"{lost} of {len(G_DATES)} dates lost to gaps ({lost / len(G_DATES):.1%})")
if lost:
    miss = [d for d in G_DATES if d not in g_win.index]
    print("   Dates without bars (first 15):", [f"{d:%Y-%m-%d}" for d in miss[:15]])
df[["open", "high", "low", "close"]].tail()
```

    734242 M5 bars | 2017-01-01 22:00:00 -> 2026-11-02 22:50:00
    {2017: 74314, 2018: 74442, 2019: 74469, 2020: 74857, 2021: 74857, 2022: 74761, 2023: 74613, 2024: 74882, 2025: 74540, 2026: 62507}
    Steps different from 5 min: 640 | largest gap: 73.1 h
    ======================================================================
    DATA INGESTION & DATASET SPLIT
    ======================================================================
    Total Prepared Bars: 734,242 (2017-01-01 to 2026-11-02)
    In-Sample (IS, 61.0%): 447,700 bars (2017-01-01 to 2022-12-30)
    Out-of-Sample (OOS, 39.0%): 286,542 bars (2023-01-01 to 2026-11-02)
    Gotobi dates expected: 704 | with both window bars present: 697
    ======================================================================
    CHECKS (section 3):
       [PASS] IS and OOS are both non-empty  ->  IS 447,700 bars | OOS 286,542 bars
       [PASS] Gotobi dates without a tradable window <= 5%  ->  7 of 704 dates lost to gaps (1.0%)
       Dates without bars (first 15): ['2017-12-25', '2018-12-25', '2019-12-25', '2020-12-25', '2023-12-25', '2024-12-25', '2025-12-25']

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
    </tr>
    <tr>
      <th>time</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>2026-11-02 22:30:00</th>
      <td>157.868</td>
      <td>157.869</td>
      <td>157.862</td>
      <td>157.868</td>
    </tr>
    <tr>
      <th>2026-11-02 22:35:00</th>
      <td>157.868</td>
      <td>157.872</td>
      <td>157.865</td>
      <td>157.871</td>
    </tr>
    <tr>
      <th>2026-11-02 22:40:00</th>
      <td>157.871</td>
      <td>157.872</td>
      <td>157.865</td>
      <td>157.868</td>
    </tr>
    <tr>
      <th>2026-11-02 22:45:00</th>
      <td>157.868</td>
      <td>157.901</td>
      <td>157.863</td>
      <td>157.868</td>
    </tr>
    <tr>
      <th>2026-11-02 22:50:00</th>
      <td>157.865</td>
      <td>157.885</td>
      <td>157.865</td>
      <td>157.881</td>
    </tr>
  </tbody>
</table>
</div>

## 4. EXPLORATORY CHECKS OF THE HYPOTHESIS (EDGE-SPECIFIC)

The four claims of section 1.1, checked on the data before any backtest. **Gross** = no costs, **net** = after a flat `FLAT_PIPS[0]` pips round trip (the engine's feed-based costs are used from section 5 on).

### 4.1 IS THE GOTOBI WINDOW SPECIAL? GOTOBI VS EVERY OTHER BUSINESS DAY

```python
SUBPERIODS = {"2010-2014": (2010, 2014), "2015-2019": (2015, 2019), "2020-2022": (2020, 2022), "OOS 2023+": (2023, 2100)}
def period_of(y):
    return next(k for k, (a, b) in SUBPERIODS.items() if a <= y <= b)

all_bd = pd.bdate_range(START_D, END_D)
a_win = window_returns(all_bd)
a_win["gotobi"] = a_win.index.isin(G_DATES)
a_win["period"] = [period_of(y) for y in a_win.index.year]
a_win["net"] = a_win["ret"] - FLAT_PIPS[0] * PIP / a_win["price_in"] * 100
g_all, o_all = a_win[a_win["gotobi"]], a_win[~a_win["gotobi"]]

rows = []
for per in list(SUBPERIODS) + ["All"]:
    g = g_all if per == "All" else g_all[g_all["period"] == per]
    o = o_all if per == "All" else o_all[o_all["period"] == per]
    rows.append({"Period": per, "Gotobi N": len(g), "Gotobi gross %": g["ret"].mean(), "Gotobi t": tstat(g["ret"]),
                 "Other N": len(o), "Other gross %": o["ret"].mean(), "Other t": tstat(o["ret"])})
win_tbl = pd.DataFrame(rows).set_index("Period")
print("=" * 70)
print("07:30-09:55 JST WINDOW RETURN: GOTOBI DAYS VS OTHER BUSINESS DAYS (% gross)")
print("=" * 70)
display(win_tbl.round(4))

print("\nCHECKS (4.1):")
t_gw, p_gw = stats.ttest_ind(g_all["ret"], o_all["ret"], equal_var=False, alternative="greater")
check("4.1 Window", "Gotobi window mean return > 0 in every sub-period", (win_tbl.loc[list(SUBPERIODS), "Gotobi gross %"] > 0).all(),
      "; ".join(f"{p}: {win_tbl.loc[p, 'Gotobi gross %']:+.4f}%" for p in SUBPERIODS))
check("4.1 Window", f"Gotobi beats the other business days (one-sided Welch p < {ALPHA:g})", p_gw < ALPHA,
      f"gotobi {g_all['ret'].mean():+.4f}% vs other {o_all['ret'].mean():+.4f}% | t = {t_gw:.2f}, p = {p_gw:.4f}")
check("4.1 Window", f"Net window drift is significant (t >= {T_MIN:g})", tstat(g_all["net"]) >= T_MIN,
      f"net mean {g_all['net'].mean():+.4f}% | t = {tstat(g_all['net']):.2f} (flat {FLAT_PIPS[0]:g} pips)")
check("4.1 Window", "Gotobi drift is not present in the other business days (t < 2)", tstat(o_all["ret"]) < 2.0,
      f"other-days t = {tstat(o_all['ret']):.2f}")
```

    ======================================================================
    07:30-09:55 JST WINDOW RETURN: GOTOBI DAYS VS OTHER BUSINESS DAYS (% gross)
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
      <th>Gotobi N</th>
      <th>Gotobi gross %</th>
      <th>Gotobi t</th>
      <th>Other N</th>
      <th>Other gross %</th>
      <th>Other t</th>
    </tr>
    <tr>
      <th>Period</th>
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
      <th>2010-2014</th>
      <td>0</td>
      <td>NaN</td>
      <td>NaN</td>
      <td>0</td>
      <td>NaN</td>
      <td>NaN</td>
    </tr>
    <tr>
      <th>2015-2019</th>
      <td>212</td>
      <td>0.0348</td>
      <td>3.7438</td>
      <td>561</td>
      <td>-0.0011</td>
      <td>-0.1857</td>
    </tr>
    <tr>
      <th>2020-2022</th>
      <td>213</td>
      <td>0.0409</td>
      <td>3.4192</td>
      <td>566</td>
      <td>0.0147</td>
      <td>2.3037</td>
    </tr>
    <tr>
      <th>OOS 2023+</th>
      <td>272</td>
      <td>0.0267</td>
      <td>2.4460</td>
      <td>722</td>
      <td>0.0016</td>
      <td>0.2366</td>
    </tr>
    <tr>
      <th>All</th>
      <td>697</td>
      <td>0.0335</td>
      <td>5.3352</td>
      <td>1849</td>
      <td>0.0048</td>
      <td>1.3071</td>
    </tr>
  </tbody>
</table>
</div>

    CHECKS (4.1):
       [FAIL] Gotobi window mean return > 0 in every sub-period  ->  2010-2014: +nan%; 2015-2019: +0.0348%; 2020-2022: +0.0409%; OOS 2023+: +0.0267%
       [PASS] Gotobi beats the other business days (one-sided Welch p < 0.05)  ->  gotobi +0.0335% vs other +0.0048% | t = 3.95, p = 0.0000
       [PASS] Net window drift is significant (t >= 2.5)  ->  net mean +0.0279% | t = 4.44 (flat 0.7 pips)
       [PASS] Gotobi drift is not present in the other business days (t < 2)  ->  other-days t = 1.31





    'PASS'

### 4.2 PLACEBO WINDOWS: THE SAME RULE MOVED BY -2, -1, +1, +2 BUSINESS DAYS

```python
plc_rows, plc_series = [], {}
for k in [0] + list(PLACEBOS):
    d_k = eng.shifted_dates(G_DATES, k)          # k Japanese bank business days away (same convention as the engine's placebo_table)
    d_k = d_k[(d_k >= START_D) & (d_k <= END_D)]
    w = window_returns(d_k)
    plc_series[k] = w["ret"]
    plc_rows.append({"Offset (bdays)": k, "N": len(w), "Gross mean %": w["ret"].mean(), "Gross t": tstat(w["ret"]),
                     "Hit rate %": (w["ret"] > 0).mean() * 100})
plc_tbl = pd.DataFrame(plc_rows).set_index("Offset (bdays)")
print("=" * 70)
print("PLACEBO WINDOWS (offset 0 = the real gotobi window)")
print("=" * 70)
display(plc_tbl.round(4))

print("\nCHECKS (4.2):")
others = plc_tbl.drop(index=0)
check("4.2 Placebos", "Real window has the highest mean of all offsets", plc_tbl["Gross mean %"].idxmax() == 0,
      f"best offset = {plc_tbl['Gross mean %'].idxmax()} | real {plc_tbl.loc[0, 'Gross mean %']:+.4f}% vs best placebo {others['Gross mean %'].max():+.4f}%")
check("4.2 Placebos", f"No placebo window is significant (t < {T_PLACEBO_MAX:g})", (others["Gross t"] < T_PLACEBO_MAX).all(),
      "; ".join(f"{k:+d}: t = {v:.2f}" for k, v in others["Gross t"].items()))
check("4.2 Placebos", "Real window mean is at least 2x the best placebo", plc_tbl.loc[0, "Gross mean %"] >= 2 * others["Gross mean %"].max(),
      f"{plc_tbl.loc[0, 'Gross mean %']:+.4f}% vs {others['Gross mean %'].max():+.4f}%")

fig, ax = plt.subplots(figsize=(8, 3.8), facecolor="#15171c")
ax.set_facecolor("#1b1e26")
ax.bar([str(k) for k in plc_tbl.index], plc_tbl["Gross mean %"], color=["#34d399" if k == 0 else "#9aa0ab" for k in plc_tbl.index], width=0.55)
ax.axhline(0, color="#9aa0ab", lw=0.6)
ax.set_title("Window mean return by offset in business days (%, gross)", color="#e8e9ec", fontweight="bold", loc="left")
ax.tick_params(colors="#9aa0ab")
for s in ax.spines.values(): s.set_visible(False)
plt.tight_layout(); plt.show()
```

    ======================================================================
    PLACEBO WINDOWS (offset 0 = the real gotobi window)
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
      <th>N</th>
      <th>Gross mean %</th>
      <th>Gross t</th>
      <th>Hit rate %</th>
    </tr>
    <tr>
      <th>Offset (bdays)</th>
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
      <td>0.0335</td>
      <td>5.3352</td>
      <td>61.5495</td>
    </tr>
    <tr>
      <th>-2</th>
      <td>702</td>
      <td>0.0135</td>
      <td>2.1778</td>
      <td>56.9801</td>
    </tr>
    <tr>
      <th>-1</th>
      <td>704</td>
      <td>0.0041</td>
      <td>0.7270</td>
      <td>53.2670</td>
    </tr>
    <tr>
      <th>1</th>
      <td>700</td>
      <td>0.0178</td>
      <td>2.9010</td>
      <td>56.1429</td>
    </tr>
    <tr>
      <th>2</th>
      <td>702</td>
      <td>0.0051</td>
      <td>0.9101</td>
      <td>55.8405</td>
    </tr>
  </tbody>
</table>
</div>

    CHECKS (4.2):
       [PASS] Real window has the highest mean of all offsets  ->  best offset = 0 | real +0.0335% vs best placebo +0.0178%
       [FAIL] No placebo window is significant (t < 2)  ->  -2: t = 2.18; -1: t = 0.73; +1: t = 2.90; +2: t = 0.91
       [FAIL] Real window mean is at least 2x the best placebo  ->  +0.0335% vs +0.0178%

![png](01_Gotobi_Hypothesis_Definition_files/01_Gotobi_Hypothesis_Definition_9_3.png)

### 4.3 WHICH PAYMENT DATE CARRIES THE EDGE? (BY DAY OF THE MONTH)

```python
g_all2 = g_all.copy()
# label = the payment day the date belongs to (a shifted date keeps the label of the nominal date it was moved from)
g_all2["bucket"] = G_CAL.loc[g_all2.index, "label"].to_numpy()
order = [str(d) for d in GOTOBI_DAYS] + (["EOM"] if INCLUDE_EOM else [])
dom = g_all2.groupby("bucket")["net"].agg(["size", "mean"]).reindex(order)
dom["t"] = g_all2.groupby("bucket")["net"].apply(tstat).reindex(order)
dom["hit %"] = g_all2.groupby("bucket")["net"].apply(lambda s: (s > 0).mean() * 100).reindex(order)
dom.columns = ["N", "Net mean %", "Net t", "Hit rate %"]
print("=" * 70)
print(f"NET WINDOW RETURN BY PAYMENT DATE (flat {FLAT_PIPS[0]:g} pips)")
print("=" * 70)
display(dom.round(4))

print("\nCHECKS (4.3):")
check("4.3 Payment dates", "Net mean is positive on every payment date", (dom["Net mean %"] > 0).all(),
      "; ".join(f"{i}: {v:+.4f}%" for i, v in dom["Net mean %"].items()))
share = dom["Net mean %"].clip(lower=0) * dom["N"]
top_share = share.max() / share.sum() if share.sum() > 0 else np.nan
check("4.3 Payment dates", "No single payment date carries more than 40% of the net edge", top_share <= 0.40,
      f"top date = {share.idxmax()} with {top_share:.0%} of the net edge")
check("4.3 Payment dates", "At least 4 of the 6 payment dates are individually positive with t > 1", int(((dom['Net mean %'] > 0) & (dom['Net t'] > 1)).sum()) >= 4,
      f"{int(((dom['Net mean %'] > 0) & (dom['Net t'] > 1)).sum())} of 6")

fig, ax = plt.subplots(figsize=(8, 3.8), facecolor="#15171c")
ax.set_facecolor("#1b1e26")
ax.bar(dom.index, dom["Net mean %"], color=["#34d399" if v > 0 else "#f0555a" for v in dom["Net mean %"]], width=0.55)
ax.axhline(0, color="#9aa0ab", lw=0.6)
ax.set_title("Net window return by payment date (%)", color="#e8e9ec", fontweight="bold", loc="left")
ax.tick_params(colors="#9aa0ab")
for s in ax.spines.values(): s.set_visible(False)
plt.tight_layout(); plt.show()
```

    ======================================================================
    NET WINDOW RETURN BY PAYMENT DATE (flat 0.7 pips)
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
      <th>N</th>
      <th>Net mean %</th>
      <th>Net t</th>
      <th>Hit rate %</th>
    </tr>
    <tr>
      <th>bucket</th>
      <th></th>
      <th></th>
      <th></th>
      <th></th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>5</th>
      <td>114</td>
      <td>-0.0194</td>
      <td>-1.2447</td>
      <td>44.7368</td>
    </tr>
    <tr>
      <th>10</th>
      <td>118</td>
      <td>0.0318</td>
      <td>1.8310</td>
      <td>59.3220</td>
    </tr>
    <tr>
      <th>15</th>
      <td>118</td>
      <td>0.0271</td>
      <td>1.8769</td>
      <td>63.5593</td>
    </tr>
    <tr>
      <th>20</th>
      <td>118</td>
      <td>0.0574</td>
      <td>4.7298</td>
      <td>74.5763</td>
    </tr>
    <tr>
      <th>25</th>
      <td>111</td>
      <td>0.0449</td>
      <td>3.4420</td>
      <td>69.3694</td>
    </tr>
    <tr>
      <th>EOM</th>
      <td>118</td>
      <td>0.0248</td>
      <td>1.3872</td>
      <td>50.8475</td>
    </tr>
  </tbody>
</table>
</div>

    CHECKS (4.3):
       [FAIL] Net mean is positive on every payment date  ->  5: -0.0194%; 10: +0.0318%; 15: +0.0271%; 20: +0.0574%; 25: +0.0449%; EOM: +0.0248%
       [PASS] No single payment date carries more than 40% of the net edge  ->  top date = 20 with 31% of the net edge
       [PASS] At least 4 of the 6 payment dates are individually positive with t > 1  ->  5 of 6

![png](01_Gotobi_Hypothesis_Definition_files/01_Gotobi_Hypothesis_Definition_11_3.png)

### 4.4 SHIFTED PAYMENT DAYS VS DAYS THAT FELL ON A BUSINESS DAY

```python
g_all2["shifted"] = G_CAL.loc[g_all2.index, "shifted"].to_numpy().astype(bool)
sh = g_all2.groupby("shifted")["net"].agg(["size", "mean"])
sh["t"] = g_all2.groupby("shifted")["net"].apply(tstat)
sh.index = ["On the date" if not i else "Shifted (weekend / holiday)" for i in sh.index]
sh.columns = ["N", "Net mean %", "Net t"]
print("=" * 70)
print("SHIFTED VS NOT SHIFTED (net window return)")
print("=" * 70)
display(sh.round(4))

print("\nCHECKS (4.4):")
if g_all2["shifted"].sum() >= 20:
    s_ret, n_ret = g_all2.loc[g_all2["shifted"], "net"], g_all2.loc[~g_all2["shifted"], "net"]
    check("4.4 Shift", "Shifted payment days also have a positive net mean", s_ret.mean() > 0, f"shifted {s_ret.mean():+.4f}% (N = {len(s_ret)})")
    check("4.4 Shift", "Shifted days are not significantly worse than the others (one-sided Welch p > 0.05)",
          stats.ttest_ind(s_ret, n_ret, equal_var=False, alternative="less")[1] > ALPHA,
          f"shifted {s_ret.mean():+.4f}% vs on-date {n_ret.mean():+.4f}%")
else:
    check("4.4 Shift", "Shifted payment days behave like the rest", None, f"only {int(g_all2['shifted'].sum())} shifted dates")
```

    ======================================================================
    SHIFTED VS NOT SHIFTED (net window return)
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
      <th>N</th>
      <th>Net mean %</th>
      <th>Net t</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>On the date</th>
      <td>471</td>
      <td>0.0305</td>
      <td>3.8839</td>
    </tr>
    <tr>
      <th>Shifted (weekend / holiday)</th>
      <td>226</td>
      <td>0.0225</td>
      <td>2.1640</td>
    </tr>
  </tbody>
</table>
</div>

    CHECKS (4.4):
       [PASS] Shifted payment days also have a positive net mean  ->  shifted +0.0225% (N = 226)
       [PASS] Shifted days are not significantly worse than the others (one-sided Welch p > 0.05)  ->  shifted +0.0225% vs on-date +0.0305%

## 5. BASELINE BACKTEST WITH FROZEN RULES

```python
trades_is  = eng.run_gotobi_backtest(df_is,  **RULES)
trades_oos = eng.run_gotobi_backtest(df_oos, **RULES)
trades_all = eng.run_gotobi_backtest(df,     **RULES)

def sized(t, sizing):
    return t if sizing == "capital" else t.assign(pnl=t["pnl_frac"], win=t["pnl_frac"] > 0)

def perf_row(t, price_df, period, sizing):
    m = compute_metrics(sized(t, sizing), contract_multiplier=1.0, cost_per_trade=0.0)
    ret = eng.daily_returns(price_df, t, sizing=sizing)
    eq = (1.0 + ret).cumprod()
    yrs = (price_df.index[-1] - price_df.index[0]).days / 365.25
    return {"Period": period, "Sizing": "100% Capital" if sizing == "capital" else f"{SIZE_FRAC:.0%} Capital (robot)",
            "Trades": m["num_trades"], "Win Rate": f"{m['win_rate']:.1f}%", "Profit Factor": f"{m['profit_factor']:.3f}",
            "Expectancy": f"{m['expectancy']:.4f}%", "Total Return": f"{(eq.iloc[-1] - 1) * 100:.1f}%",
            "CAGR": f"{((eq.iloc[-1] ** (1 / yrs)) - 1) * 100:.1f}%" if yrs > 0 else "n/a",
            "Sharpe": f"{sharpe_ratio(ret, periods_per_year=PPY):.2f}", "Max Drawdown": f"{max_drawdown(eq) * 100:.2f}%"}

periods = [(f"In-Sample ({df_is.index[0].year}-{df_is.index[-1].year})", trades_is, df_is),
           (f"Out-of-Sample ({df_oos.index[0].year}-{df_oos.index[-1].year})", trades_oos, df_oos),
           (f"Full Period ({df.index[0].year}-{df.index[-1].year})", trades_all, df)]
perf_table = pd.DataFrame([perf_row(t, d, name, s) for name, t, d in periods for s in ("capital", "fraction")])

print("=" * 80)
print(f"PERFORMANCE SUMMARY (NET OF COSTS: {COST_MODE} x {SPREAD_SCALE:g} · daily MTM drawdown, Sharpe annualised x{PPY})")
print("=" * 80)
display(perf_table)

BG, PANEL, GRIDC, TXT, SUB, GREEN, RED, ORANGE = "#15171c", "#1b1e26", "#2a2d37", "#e8e9ec", "#9aa0ab", "#34d399", "#f0555a", "#f5a524"
def dark_ax(ax):
    ax.set_facecolor(PANEL); ax.grid(True, color=GRIDC, lw=0.8, alpha=0.9)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=SUB, labelsize=9)

ret_cap = eng.daily_returns(df, trades_all, sizing="capital")
ret_fr = eng.daily_returns(df, trades_all, sizing="fraction")
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, facecolor=BG)
for ax, r, col, lab in ((ax1, ret_cap, GREEN, "100% Capital Sizing"), (ax2, ret_fr, "#5468ff", f"{SIZE_FRAC:.0%} Capital Sizing (robot)")):
    dark_ax(ax)
    ax.plot(r.index, (1 + r).cumprod(), color=col, lw=1.6, label=lab)
    ax.axvline(oos_start, color=ORANGE, ls="--", lw=1.2, label=f"OOS Split Date ({oos_start:%Y-%m-%d})")
    ax.set_title(f"{TICKER} Gotobi - Cumulative Equity Curve ({lab})", color=TXT, fontweight="bold", loc="left")
    ax.set_ylabel("Equity Multiplier", color=SUB)
    ax.legend(frameon=False, labelcolor=SUB, fontsize=9, loc="upper left")
plt.tight_layout(); plt.show()

profit_usd = CAPITAL * ((1.0 + ret_fr).cumprod() - 1.0)
price_daily = df["close"].resample("D").last().reindex(ret_fr.index).ffill().bfill()
buy_hold = CAPITAL * (price_daily / price_daily.iloc[0] - 1.0)
entries = trades_all.assign(entry_time=pd.to_datetime(trades_all["entry_time"])).set_index("entry_time")
won = entries["pnl"] > 0

fig, (ax_px, ax_pl) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, facecolor=BG, gridspec_kw={"height_ratios": [3, 2]})
for ax in (ax_px, ax_pl):
    dark_ax(ax); ax.grid(False); ax.axvline(oos_start, color=ORANGE, ls="--", lw=1.2)
ax_px.plot(price_daily.index, price_daily, color=SUB, lw=1.2, label=f"{TICKER} close (daily)")
ax_px.scatter(entries.index[won], entries.loc[won, "entry_price"], marker="^", s=10, color=GREEN, zorder=3, label="Winning trade")
ax_px.scatter(entries.index[~won], entries.loc[~won, "entry_price"], marker="v", s=10, color=RED, zorder=3, label="Losing trade")
ax_px.set_title(f"{TICKER} price vs money earned by the strategy", color=TXT, fontweight="bold", loc="left")
ax_px.set_ylabel("Price", color=SUB)
ax_px.legend(frameon=False, labelcolor=SUB, fontsize=9, loc="upper left")
ax_pl.plot(profit_usd.index, profit_usd, color=GREEN, lw=1.6, label=f"Strategy profit ({SIZE_FRAC:.0%} sizing, capital {CAPITAL:,.0f})")
ax_pl.fill_between(profit_usd.index, profit_usd, 0, color=GREEN, alpha=0.15)
ax_pl.axhline(0, color=SUB, lw=0.8)
ax_pl.set_ylabel("Money earned", color=SUB)
ax_bh = ax_pl.twinx()
ax_bh.plot(buy_hold.index, buy_hold, color=SUB, lw=1.0, ls="--", label="Buy & hold on the same capital (right axis)")
ax_bh.grid(False); ax_bh.tick_params(colors=SUB)
for spine in ax_bh.spines.values():
    spine.set_visible(False)
h1, l1 = ax_pl.get_legend_handles_labels(); h2, l2 = ax_bh.get_legend_handles_labels()
ax_pl.legend(h1 + h2, l1 + l2, frameon=False, labelcolor=SUB, fontsize=9, loc="upper left")
plt.tight_layout(); plt.show()

in_market = float(trades_all["bars"].sum()) / len(df)
print(f"{TICKER} price change: {(price_daily.iloc[-1] / price_daily.iloc[0] - 1) * 100:+,.0f}% | "
      f"strategy profit: {profit_usd.iloc[-1]:,.0f} ({profit_usd.iloc[-1] / CAPITAL * 100:+.1f}% of {CAPITAL:,.0f}) | "
      f"buy & hold profit: {buy_hold.iloc[-1]:,.0f} | time in market: {in_market * 100:.2f}%")

print("\nCHECKS (5):")
m_is, m_oos, m_all = (compute_metrics(t, 1.0, 0.0) for t in (trades_is, trades_oos, trades_all))
t_all = tstat(trades_all["pnl"])
check("5. Baseline", f"Profit Factor, full period >= {PF_MIN:g}", m_all["profit_factor"] >= PF_MIN, f"PF = {m_all['profit_factor']:.3f}")
check("5. Baseline", f"Profit Factor, IS >= {PF_MIN:g}", m_is["profit_factor"] >= PF_MIN, f"PF = {m_is['profit_factor']:.3f}")
check("5. Baseline", f"Profit Factor, OOS >= {PF_MIN:g}", m_oos["profit_factor"] >= PF_MIN, f"PF = {m_oos['profit_factor']:.3f}")
check("5. Baseline", "OOS does not degrade vs IS (OOS PF >= 50% of IS PF)", m_oos["profit_factor"] >= 0.5 * m_is["profit_factor"],
      f"OOS {m_oos['profit_factor']:.3f} vs IS {m_is['profit_factor']:.3f}")
check("5. Baseline", f"Net t-stat of the mean trade >= {T_MIN:g} (raised for {EV['hypotheses_tested']} hypotheses tested)", t_all >= T_MIN, f"t = {t_all:.2f}")
check("5. Baseline", f"Trades, full period >= {N_MIN}", m_all["num_trades"] >= N_MIN, f"{m_all['num_trades']} trades")
check("5. Baseline", f"Trades, OOS >= {N_OOS_MIN}", m_oos["num_trades"] >= N_OOS_MIN, f"{m_oos['num_trades']} trades")
check("5. Baseline", "Expectancy > 0 in IS and OOS (net of costs)", m_is["expectancy"] > 0 and m_oos["expectancy"] > 0,
      f"IS {m_is['expectancy']:+.4f}% | OOS {m_oos['expectancy']:+.4f}%")
```

    ================================================================================
    PERFORMANCE SUMMARY (NET OF COSTS: feed x 0.7 · daily MTM drawdown, Sharpe annualised x252)
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
      <th>CAGR</th>
      <th>Sharpe</th>
      <th>Max Drawdown</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>In-Sample (2017-2022)</td>
      <td>100% Capital</td>
      <td>425</td>
      <td>60.0%</td>
      <td>1.764</td>
      <td>0.0302%</td>
      <td>13.6%</td>
      <td>2.2%</td>
      <td>1.58</td>
      <td>-1.24%</td>
    </tr>
    <tr>
      <th>1</th>
      <td>In-Sample (2017-2022)</td>
      <td>250% Capital (robot)</td>
      <td>425</td>
      <td>60.0%</td>
      <td>1.764</td>
      <td>0.0755%</td>
      <td>37.4%</td>
      <td>5.4%</td>
      <td>1.58</td>
      <td>-3.08%</td>
    </tr>
    <tr>
      <th>2</th>
      <td>Out-of-Sample (2023-2026)</td>
      <td>100% Capital</td>
      <td>272</td>
      <td>59.6%</td>
      <td>1.271</td>
      <td>0.0157%</td>
      <td>4.3%</td>
      <td>1.1%</td>
      <td>0.72</td>
      <td>-1.69%</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Out-of-Sample (2023-2026)</td>
      <td>250% Capital (robot)</td>
      <td>272</td>
      <td>59.6%</td>
      <td>1.271</td>
      <td>0.0393%</td>
      <td>10.9%</td>
      <td>2.7%</td>
      <td>0.72</td>
      <td>-4.23%</td>
    </tr>
    <tr>
      <th>4</th>
      <td>Full Period (2017-2026)</td>
      <td>100% Capital</td>
      <td>697</td>
      <td>59.8%</td>
      <td>1.525</td>
      <td>0.0245%</td>
      <td>18.5%</td>
      <td>1.7%</td>
      <td>1.22</td>
      <td>-1.69%</td>
    </tr>
    <tr>
      <th>5</th>
      <td>Full Period (2017-2026)</td>
      <td>250% Capital (robot)</td>
      <td>697</td>
      <td>59.8%</td>
      <td>1.525</td>
      <td>0.0613%</td>
      <td>52.4%</td>
      <td>4.4%</td>
      <td>1.22</td>
      <td>-4.23%</td>
    </tr>
  </tbody>
</table>
</div>

![png](01_Gotobi_Hypothesis_Definition_files/01_Gotobi_Hypothesis_Definition_15_2.png)

![png](01_Gotobi_Hypothesis_Definition_files/01_Gotobi_Hypothesis_Definition_15_3.png)

    USDJPY price change: +34% | strategy profit: 5,243 (+52.4% of 10,000) | buy & hold profit: 3,442 | time in market: 2.75%

    CHECKS (5):
       [PASS] Profit Factor, full period >= 1.2  ->  PF = 1.525
       [PASS] Profit Factor, IS >= 1.2  ->  PF = 1.764
       [PASS] Profit Factor, OOS >= 1.2  ->  PF = 1.271
       [PASS] OOS does not degrade vs IS (OOS PF >= 50% of IS PF)  ->  OOS 1.271 vs IS 1.764
       [PASS] Net t-stat of the mean trade >= 2.5 (raised for 17 hypotheses tested)  ->  t = 3.91
       [PASS] Trades, full period >= 600  ->  697 trades
       [PASS] Trades, OOS >= 150  ->  272 trades
       [PASS] Expectancy > 0 in IS and OOS (net of costs)  ->  IS +0.0302% | OOS +0.0157%





    'PASS'

## 5.1 LOT-ADJUSTED SIZING AND HARD LIMIT (CFD)

```python
last_price = float(df["close"].iloc[-1])
min_capital = eng.min_capital_for_target(last_price, SIZE_FRAC)
max_frac = eng.max_fraction_for_limit(df, trades_all, HARD_LIMIT)
lot_sizes = eng.cfd_trade_sizes(trades_all, CAPITAL, SIZE_FRAC)
bar_ideal = bar_returns(df, trades_all, sizing="fraction")
bar_lot = bar_returns(df, trades_all, sizing=lot_sizes["size_fraction"].to_numpy())

def drawdown_series(r):
    eq = (1.0 + r).cumprod()
    return eq / np.maximum(eq.cummax(), 1.0) - 1.0

def limit_row(label, r, n_taken):
    rep = eng.hard_limit_report(r, HARD_LIMIT)
    total = (1.0 + r).prod() - 1.0
    return {"Sizing": label, "Trades taken": n_taken, "Total Return": f"{total * 100:.1f}%",
            "Max DD (bar MTM)": f"{rep['max_dd'] * 100:.2f}%", "Headroom": f"{rep['headroom'] * 100:+.2f} pts",
            "Hard limit": "PASS" if rep["passed"] else "FAIL"}

limit_table = pd.DataFrame([
    limit_row(f"{SIZE_FRAC:.0%} ideal fraction", bar_ideal, len(trades_all)),
    limit_row(f"Lot-adjusted (capital {CAPITAL:,.0f})", bar_lot, int(lot_sizes["taken"].sum()))])
print("=" * 80)
print(f"HARD LIMIT -{HARD_LIMIT:.0%} · LOT-ADJUSTED SIZING (min lot {MIN_LOT:g}, step {LOT_STEP:g})")
print("=" * 80)
display(limit_table)
print(f"Minimum capital so the minimum lot weighs <= {SIZE_FRAC:.0%} at {last_price:,.2f}: {min_capital:,.0f}")
print(f"Largest fixed fraction that keeps the bar-level drawdown inside -{HARD_LIMIT:.0%}: {max_frac:.1%} (configured: {SIZE_FRAC:.0%})")

print("\nCHECKS (5.1):")
rep_ideal, rep_lot = eng.hard_limit_report(bar_ideal, HARD_LIMIT), eng.hard_limit_report(bar_lot, HARD_LIMIT)
check("5.1 Hard limit", f"{SIZE_FRAC:.0%} ideal fraction stays inside -{HARD_LIMIT:.0%}", rep_ideal["passed"],
      f"max DD {rep_ideal['max_dd'] * 100:.2f}% | headroom {rep_ideal['headroom'] * 100:+.2f} pts")
check("5.1 Hard limit", f"Lot-adjusted sizing stays inside -{HARD_LIMIT:.0%}", rep_lot["passed"],
      f"max DD {rep_lot['max_dd'] * 100:.2f}% | headroom {rep_lot['headroom'] * 100:+.2f} pts")
check("5.1 Hard limit", "Configured fraction <= largest fraction allowed by the limit", SIZE_FRAC <= max_frac, f"{SIZE_FRAC:.0%} vs {max_frac:.1%}")
check("5.1 Hard limit", "Capital >= minimum capital for the minimum lot", CAPITAL >= min_capital, f"{CAPITAL:,.0f} vs {min_capital:,.0f}")
check("5.1 Hard limit", "Every trade is executable with the minimum lot", int(lot_sizes["taken"].sum()) == len(trades_all),
      f"{int(lot_sizes['taken'].sum())} of {len(trades_all)} trades taken")
rep_ib = eng.hard_limit_report_intrabar(df, trades_all, HARD_LIMIT, sizing=lot_sizes["size_fraction"].to_numpy())
check("5.1 Hard limit", f"Intrabar drawdown (candle lows) stays inside -{HARD_LIMIT:.0%}", rep_ib["passed"],
      f"max DD intrabar {rep_ib['max_dd'] * 100:.2f}% (closes only {rep_ib['max_dd_close'] * 100:.2f}%) | headroom {rep_ib['headroom'] * 100:+.2f} pts")

dd_ideal, dd_lot = drawdown_series(bar_ideal), drawdown_series(bar_lot)
fig, (ax_eq, ax_dd) = plt.subplots(2, 1, figsize=(14, 7), sharex=True, facecolor=BG)
for ax in (ax_eq, ax_dd):
    dark_ax(ax); ax.grid(False); ax.axvline(oos_start, color=ORANGE, ls=":", lw=1.0)
ax_eq.plot(bar_ideal.index, (1.0 + bar_ideal).cumprod(), color=SUB, lw=1.4, label=f"{SIZE_FRAC:.0%} ideal fraction")
ax_eq.plot(bar_lot.index, (1.0 + bar_lot).cumprod(), color=GREEN, lw=1.6, label=f"Lot-adjusted (capital {CAPITAL:,.0f})")
ax_eq.set_title(f"{TICKER} Gotobi - Equity, ideal vs lot-adjusted", color=TXT, fontweight="bold", loc="left")
ax_eq.set_ylabel("Equity Multiplier", color=SUB)
ax_eq.legend(frameon=False, labelcolor=SUB, fontsize=9, loc="upper left")
ax_dd.plot(dd_ideal.index, dd_ideal * 100, color=SUB, lw=1.0)
ax_dd.fill_between(dd_lot.index, dd_lot * 100, 0, color=RED, alpha=0.35)
ax_dd.axhline(-HARD_LIMIT * 100, color=ORANGE, ls="--", lw=1.2, label=f"Hard limit -{HARD_LIMIT:.0%}")
ax_dd.set_ylabel("Drawdown % (bar MTM)", color=SUB)
ax_dd.legend(frameon=False, labelcolor=SUB, fontsize=9, loc="lower left")
plt.tight_layout(); plt.show()
```

    ================================================================================
    HARD LIMIT -9% · LOT-ADJUSTED SIZING (min lot 0.01, step 0.01)
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
      <th>Sizing</th>
      <th>Trades taken</th>
      <th>Total Return</th>
      <th>Max DD (bar MTM)</th>
      <th>Headroom</th>
      <th>Hard limit</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>250% ideal fraction</td>
      <td>697</td>
      <td>52.4%</td>
      <td>-5.07%</td>
      <td>+3.93 pts</td>
      <td>PASS</td>
    </tr>
    <tr>
      <th>1</th>
      <td>Lot-adjusted (capital 10,000)</td>
      <td>697</td>
      <td>51.5%</td>
      <td>-4.98%</td>
      <td>+4.02 pts</td>
      <td>PASS</td>
    </tr>
  </tbody>
</table>
</div>

    Minimum capital so the minimum lot weighs <= 250% at 157.88: 400
    Largest fixed fraction that keeps the bar-level drawdown inside -9%: 436.9% (configured: 250%)

    CHECKS (5.1):
       [PASS] 250% ideal fraction stays inside -9%  ->  max DD -5.07% | headroom +3.93 pts
       [PASS] Lot-adjusted sizing stays inside -9%  ->  max DD -4.98% | headroom +4.02 pts
       [PASS] Configured fraction <= largest fraction allowed by the limit  ->  250% vs 436.9%
       [PASS] Capital >= minimum capital for the minimum lot  ->  10,000 vs 400
       [PASS] Every trade is executable with the minimum lot  ->  697 of 697 trades taken
       [PASS] Intrabar drawdown (candle lows) stays inside -9%  ->  max DD intrabar -5.10% (closes only -4.98%) | headroom +3.90 pts

![png](01_Gotobi_Hypothesis_Definition_files/01_Gotobi_Hypothesis_Definition_17_3.png)

## 5.2 ANNUAL RETURNS AND HARD LIMIT CHECK

```python
def plot_annual_returns(annual, report, hard_limit):
    fig, (ax_ret, ax_dd) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True, facecolor=BG)
    years = annual["year"].astype(str).to_numpy()
    bars = ax_ret.bar(years, annual["ret"] * 100, color=[GREEN if v >= 0 else RED for v in annual["ret"]])
    ax_dd.bar(years, annual["mdd"] * 100, color=[RED if b else SUB for b in annual["breach"]])
    ax_dd.axhline(-hard_limit * 100, color=ORANGE, ls="--", lw=1.2)
    for ax in (ax_ret, ax_dd):
        dark_ax(ax); ax.grid(False)
    for rect, value, partial in zip(bars, annual["ret"], annual["partial"]):
        label = f"{value:+.1%}" + ("*" if partial else "")
        ax_ret.annotate(label, (rect.get_x() + rect.get_width() / 2, value * 100), xytext=(0, 3 if value >= 0 else -3),
                        textcoords="offset points", ha="center", va="bottom" if value >= 0 else "top", color=TXT, fontsize=9)
    status = "PASS" if report["passed"] else "FAIL"
    ax_ret.set_title(f"Annual returns · hard limit -{hard_limit:.0%} · max DD {report['max_dd']:.1%} · {status}", color=TXT, fontweight="bold", loc="left")
    ax_ret.set_ylabel("Return %", color=SUB); ax_dd.set_ylabel("Max DD in year %", color=SUB)
    plt.tight_layout(); plt.show()

annual = eng.annual_returns(bar_lot, trades_all, HARD_LIMIT)
report_annual = eng.hard_limit_report(bar_lot, HARD_LIMIT)
print("=" * 80)
print(f"ANNUAL RETURNS · LOT-ADJUSTED · HARD LIMIT -{HARD_LIMIT:.0%} · * = partial year")
print("=" * 80)
display(annual.style.format({"ret": "{:+.1%}", "mdd": "{:.1%}"}))
print(f"Steps below the limit: {report_annual['steps_in_breach']} | first breach: {report_annual['first_breach']}")

print("\nCHECKS (5.2):")
full_y = annual[~annual["partial"]]
neg = full_y[full_y["ret"] <= 0]
n_pos = len(full_y) - len(neg)
breach_years = annual.loc[annual["breach"], "year"].astype(int).tolist()
check("5.2 Annual", "No calendar year breaches the hard limit", not annual["breach"].any(),
      f"years in breach: {breach_years if breach_years else 'none'} | worst year DD {annual['mdd'].min() * 100:.1f}%")
check("5.2 Annual", f">= {YEARS_POS_MIN:.0%} of full calendar years are profitable", n_pos / len(full_y) >= YEARS_POS_MIN,
      f"{n_pos}/{len(full_y)} full years positive" + (" | non-positive: " + ", ".join(f"{int(y)} ({r:+.1%})" for y, r in zip(neg["year"], neg["ret"])) if len(neg) else ""))
plot_annual_returns(annual, report_annual, HARD_LIMIT)
```

    ================================================================================
    ANNUAL RETURNS · LOT-ADJUSTED · HARD LIMIT -9% · * = partial year
    ================================================================================

<style type="text/css">
</style>
<table id="T_dff7e">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_dff7e_level0_col0" class="col_heading level0 col0" >year</th>
      <th id="T_dff7e_level0_col1" class="col_heading level0 col1" >ret</th>
      <th id="T_dff7e_level0_col2" class="col_heading level0 col2" >mdd</th>
      <th id="T_dff7e_level0_col3" class="col_heading level0 col3" >n_trades</th>
      <th id="T_dff7e_level0_col4" class="col_heading level0 col4" >partial</th>
      <th id="T_dff7e_level0_col5" class="col_heading level0 col5" >breach</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_dff7e_level0_row0" class="row_heading level0 row0" >0</th>
      <td id="T_dff7e_row0_col0" class="data row0 col0" >2017</td>
      <td id="T_dff7e_row0_col1" class="data row0 col1" >+9.3%</td>
      <td id="T_dff7e_row0_col2" class="data row0 col2" >-1.9%</td>
      <td id="T_dff7e_row0_col3" class="data row0 col3" >71</td>
      <td id="T_dff7e_row0_col4" class="data row0 col4" >False</td>
      <td id="T_dff7e_row0_col5" class="data row0 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row1" class="row_heading level0 row1" >1</th>
      <td id="T_dff7e_row1_col0" class="data row1 col0" >2018</td>
      <td id="T_dff7e_row1_col1" class="data row1 col1" >+3.0%</td>
      <td id="T_dff7e_row1_col2" class="data row1 col2" >-2.4%</td>
      <td id="T_dff7e_row1_col3" class="data row1 col3" >71</td>
      <td id="T_dff7e_row1_col4" class="data row1 col4" >False</td>
      <td id="T_dff7e_row1_col5" class="data row1 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row2" class="row_heading level0 row2" >2</th>
      <td id="T_dff7e_row2_col0" class="data row2 col0" >2019</td>
      <td id="T_dff7e_row2_col1" class="data row2 col1" >+3.3%</td>
      <td id="T_dff7e_row2_col2" class="data row2 col2" >-2.8%</td>
      <td id="T_dff7e_row2_col3" class="data row2 col3" >70</td>
      <td id="T_dff7e_row2_col4" class="data row2 col4" >False</td>
      <td id="T_dff7e_row2_col5" class="data row2 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row3" class="row_heading level0 row3" >3</th>
      <td id="T_dff7e_row3_col0" class="data row3 col0" >2020</td>
      <td id="T_dff7e_row3_col1" class="data row3 col1" >+6.4%</td>
      <td id="T_dff7e_row3_col2" class="data row3 col2" >-3.3%</td>
      <td id="T_dff7e_row3_col3" class="data row3 col3" >70</td>
      <td id="T_dff7e_row3_col4" class="data row3 col4" >False</td>
      <td id="T_dff7e_row3_col5" class="data row3 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row4" class="row_heading level0 row4" >4</th>
      <td id="T_dff7e_row4_col0" class="data row4 col0" >2021</td>
      <td id="T_dff7e_row4_col1" class="data row4 col1" >+4.6%</td>
      <td id="T_dff7e_row4_col2" class="data row4 col2" >-1.0%</td>
      <td id="T_dff7e_row4_col3" class="data row4 col3" >71</td>
      <td id="T_dff7e_row4_col4" class="data row4 col4" >False</td>
      <td id="T_dff7e_row4_col5" class="data row4 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row5" class="row_heading level0 row5" >5</th>
      <td id="T_dff7e_row5_col0" class="data row5 col0" >2022</td>
      <td id="T_dff7e_row5_col1" class="data row5 col1" >+5.6%</td>
      <td id="T_dff7e_row5_col2" class="data row5 col2" >-2.1%</td>
      <td id="T_dff7e_row5_col3" class="data row5 col3" >72</td>
      <td id="T_dff7e_row5_col4" class="data row5 col4" >False</td>
      <td id="T_dff7e_row5_col5" class="data row5 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row6" class="row_heading level0 row6" >6</th>
      <td id="T_dff7e_row6_col0" class="data row6 col0" >2023</td>
      <td id="T_dff7e_row6_col1" class="data row6 col1" >+4.1%</td>
      <td id="T_dff7e_row6_col2" class="data row6 col2" >-2.9%</td>
      <td id="T_dff7e_row6_col3" class="data row6 col3" >71</td>
      <td id="T_dff7e_row6_col4" class="data row6 col4" >False</td>
      <td id="T_dff7e_row6_col5" class="data row6 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row7" class="row_heading level0 row7" >7</th>
      <td id="T_dff7e_row7_col0" class="data row7 col0" >2024</td>
      <td id="T_dff7e_row7_col1" class="data row7 col1" >+3.4%</td>
      <td id="T_dff7e_row7_col2" class="data row7 col2" >-5.0%</td>
      <td id="T_dff7e_row7_col3" class="data row7 col3" >71</td>
      <td id="T_dff7e_row7_col4" class="data row7 col4" >False</td>
      <td id="T_dff7e_row7_col5" class="data row7 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row8" class="row_heading level0 row8" >8</th>
      <td id="T_dff7e_row8_col0" class="data row8 col0" >2025</td>
      <td id="T_dff7e_row8_col1" class="data row8 col1" >-0.0%</td>
      <td id="T_dff7e_row8_col2" class="data row8 col2" >-4.2%</td>
      <td id="T_dff7e_row8_col3" class="data row8 col3" >70</td>
      <td id="T_dff7e_row8_col4" class="data row8 col4" >False</td>
      <td id="T_dff7e_row8_col5" class="data row8 col5" >False</td>
    </tr>
    <tr>
      <th id="T_dff7e_level0_row9" class="row_heading level0 row9" >9</th>
      <td id="T_dff7e_row9_col0" class="data row9 col0" >2026</td>
      <td id="T_dff7e_row9_col1" class="data row9 col1" >+3.0%</td>
      <td id="T_dff7e_row9_col2" class="data row9 col2" >-2.4%</td>
      <td id="T_dff7e_row9_col3" class="data row9 col3" >60</td>
      <td id="T_dff7e_row9_col4" class="data row9 col4" >True</td>
      <td id="T_dff7e_row9_col5" class="data row9 col5" >False</td>
    </tr>
  </tbody>
</table>

    Steps below the limit: 0 | first breach: None

    CHECKS (5.2):
       [PASS] No calendar year breaches the hard limit  ->  years in breach: none | worst year DD -5.0%
       [PASS] >= 75% of full calendar years are profitable  ->  8/9 full years positive | non-positive: 2025 (-0.0%)

![png](01_Gotobi_Hypothesis_Definition_files/01_Gotobi_Hypothesis_Definition_19_3.png)

## 6. SANITY CHECKS & VERIFICATION

```python
print("=" * 70)
print("SANITY CHECKS & REPRODUCIBILITY")
print("=" * 70)

# 1. No lookahead + execution model (violations are collected, not asserted, so the notebook keeps running)
violations, prev_end = [], None
t_in_h, t_in_m = (int(x) for x in ENTRY_JST.split(":"))
t_out_h, t_out_m = (int(x) for x in EXIT_JST.split(":"))
exp_hold = (pd.Timedelta(hours=t_out_h, minutes=t_out_m) - pd.Timedelta(hours=t_in_h, minutes=t_in_m))
for idx_, r in trades_all.iterrows():
    et, xt = pd.Timestamp(r["entry_time"]), pd.Timestamp(r["exit_time"])
    jst_in = et + pd.Timedelta(hours=9)
    if not (df.index[int(r["i_ent"])] == et and df.index[int(r["i_sal"])] == xt):
        violations.append(f"trade {idx_}: i_ent / i_sal misaligned")
    if (jst_in.hour, jst_in.minute) != (t_in_h, t_in_m):
        violations.append(f"trade {idx_}: entry is not {ENTRY_JST} JST")
    if xt - et != exp_hold:
        violations.append(f"trade {idx_}: holding is not {exp_hold}")
    if jst_in.dayofweek >= 5:
        violations.append(f"trade {idx_}: entry on a weekend (JST)")
    if prev_end is not None and et < prev_end:
        violations.append(f"trade {idx_}: overlaps the previous trade")
    prev_end = xt
print(f"Sanity Check 1: entry {ENTRY_JST} JST, exit {EXIT_JST} JST, hold {exp_hold}, no overlap ({len(trades_all)} trades).")
print("   - No indicator: the signal is the calendar, known in advance, so there is no lookahead by construction.")
print("   - Execution at the open of the entry and exit bars, costs per cost_mode.")
check("6. Sanity", "No lookahead and execution model respected on every trade", not violations,
      f"{len(trades_all)} trades checked" + (f" | {len(violations)} violations, first: {violations[0]}" if violations else ""))

# 2. Engine dates vs the calendar rebuilt in this notebook
eng_dates = pd.DatetimeIndex(pd.to_datetime(trades_all["entry_date"]).unique()).sort_values()      # entry_date = JST trade date
expected = pd.DatetimeIndex(g_win.index)
only_eng, only_nb = eng_dates.difference(expected), expected.difference(eng_dates)
print(f"\nSanity Check 2: engine trade dates vs notebook calendar: {len(eng_dates)} vs {len(expected)} "
      f"| only engine: {len(only_eng)} | only notebook: {len(only_nb)}")
if len(only_eng): print("   only engine (first 10):", [f"{d:%Y-%m-%d}" for d in only_eng[:10]])
if len(only_nb):  print("   only notebook (first 10):", [f"{d:%Y-%m-%d}" for d in only_nb[:10]])
check("6. Sanity", "Engine calendar matches the notebook calendar (>= 99% of dates)", len(only_eng) + len(only_nb) <= 0.01 * len(expected),
      f"{len(only_eng)} only in engine, {len(only_nb)} only in notebook of {len(expected)}")

# 3. Trade distribution per calendar year (full years only)
trades_all["year"] = pd.to_datetime(trades_all["entry_date"]).dt.year      # JST entry year (same as the engine's validate())
tpy = trades_all.groupby("year").size()
full_years = [y for y in range(df.index[0].year, df.index[-1].year + 1)
              if pd.Timestamp(f"{y}-01-01") >= df.index[0] and pd.Timestamp(f"{y}-12-31") <= df.index[-1]]
tpy_full = tpy.reindex(full_years, fill_value=0)
print("\nSanity Check 3: Trade Frequency per Year:")
print(f"   - Average trades per year: {tpy.mean():.1f}")
print(f"   - Min trades (full years): {tpy_full.min()} ({tpy_full.idxmin()}) | Max trades: {tpy.max()} ({tpy.idxmax()})")
check("6. Sanity", f"Every full calendar year has {TPY_LO}-{TPY_HI} trades (acceptance.trades_per_year)", bool(tpy_full.between(TPY_LO, TPY_HI).all()),
      f"min {tpy_full.min()} ({tpy_full.idxmin()}) | max {tpy_full.max()} ({tpy_full.idxmax()}) over {len(tpy_full)} full years")

# 4. MTM paths reproduce the trade returns exactly
paths = eng.trade_mtm_paths(df, trades_all, sizing="capital")
err = max(abs(np.prod(1 + p) - (1 + pnl / 100)) for p, pnl in zip(paths, trades_all["pnl"]))
print(f"\nSanity Check 4: MTM paths telescope to trade returns (max abs error {err:.2e}).")
check("6. Sanity", "MTM paths telescope to the trade returns (error < 1e-9)", err < 1e-9, f"max abs error {err:.2e}")

# 5. The notebook's own gross window return vs the engine's gross return on the same dates
eng_gross = pd.Series(trades_all["pnl_gross_bps"].to_numpy() / 100.0,                      # engine gross is in bps -> %
                      index=pd.DatetimeIndex(pd.to_datetime(trades_all["entry_date"])))
common = eng_gross.index.intersection(g_win.index)
if eng_gross.notna().any() and len(common) > 0:
    diff = (eng_gross.loc[common] - g_win.loc[common, "ret"]).abs().max()
    print(f"\nSanity Check 5: max |engine gross - notebook gross| = {diff:.2e} % over {len(common)} trades.")
    check("6. Sanity", "Engine gross return equals the notebook window return (error < 1e-6 %)", diff < 1e-6, f"max abs diff {diff:.2e} %")
else:
    check("6. Sanity", "Engine gross return equals the notebook window return", None, "no common dates to compare")
```

    ======================================================================
    SANITY CHECKS & REPRODUCIBILITY
    ======================================================================
    Sanity Check 1: entry 07:30 JST, exit 09:55 JST, hold 0 days 02:25:00, no overlap (697 trades).
       - No indicator: the signal is the calendar, known in advance, so there is no lookahead by construction.
       - Execution at the open of the entry and exit bars, costs per cost_mode.
       [PASS] No lookahead and execution model respected on every trade  ->  697 trades checked

    Sanity Check 2: engine trade dates vs notebook calendar: 697 vs 697 | only engine: 0 | only notebook: 0
       [PASS] Engine calendar matches the notebook calendar (>= 99% of dates)  ->  0 only in engine, 0 only in notebook of 697

    Sanity Check 3: Trade Frequency per Year:
       - Average trades per year: 69.7
       - Min trades (full years): 70 (2019) | Max trades: 72 (2022)
       [PASS] Every full calendar year has 66-74 trades (acceptance.trades_per_year)  ->  min 70 (2019) | max 72 (2022) over 8 full years

    Sanity Check 4: MTM paths telescope to trade returns (max abs error 1.33e-15).
       [PASS] MTM paths telescope to the trade returns (error < 1e-9)  ->  max abs error 1.33e-15

    Sanity Check 5: max |engine gross - notebook gross| = 5.55e-17 % over 697 trades.
       [PASS] Engine gross return equals the notebook window return (error < 1e-6 %)  ->  max abs diff 5.55e-17 %

## 7. REFERENCE VARIANTS: GOTOBI VS NAKED WINDOW VS COST SCENARIOS (SAME BARS, SAME SIZE)

```python
v_gotobi = trades_all
v_naked = eng.run_gotobi_backtest(df, **{**RULES, "dates": all_bd})                # every Mon-Fri JST date (custom `dates`), same window and costs

def run_flat(price_df, fp):
    """The flat Axi spread is an ENGINE DEFAULT (flat_spread_pips), not a backtest argument: set it for the run, then restore it."""
    old = eng.ENGINE_DEFAULTS["flat_spread_pips"]
    eng.set_engine_defaults(flat_spread_pips=float(fp))
    try:
        return eng.run_gotobi_backtest(price_df, **{**RULES, "cost_mode": "flat_pips"})
    finally:
        eng.set_engine_defaults(flat_spread_pips=old)

cost_runs = {f"Gotobi, flat {fp:g} pips": run_flat(df, fp) for fp in FLAT_PIPS}
variants = {"Naked window (every business day)": v_naked, f"Gotobi ({COST_MODE} x {SPREAD_SCALE:g})": v_gotobi, **cost_runs}

rows, curves, raw = [], {}, {}
for name, t in variants.items():
    m = compute_metrics(sized(t, "fraction"), 1.0, 0.0)
    mt = compute_metrics(t, 1.0, 0.0)
    r = eng.daily_returns(df, t, sizing="fraction")
    eq = (1 + r).cumprod()
    curves[name] = eq
    raw[name] = {"pf": mt["profit_factor"], "exp": mt["expectancy"], "sharpe": sharpe_ratio(r, periods_per_year=PPY),
                 "mdd": max_drawdown(eq), "final": float(eq.iloc[-1]), "t": tstat(t["pnl"])}
    rows.append({"Variant": name, "Trades": m["num_trades"], "Win Rate": f"{m['win_rate']:.1f}%", "Profit Factor": f"{mt['profit_factor']:.3f}",
                 "Net t": f"{raw[name]['t']:.2f}", "Sharpe": f"{raw[name]['sharpe']:.2f}", "Max Drawdown": f"{raw[name]['mdd'] * 100:.2f}%",
                 "Final Capital": f"{eq.iloc[-1]:.2f}x"})
print("=" * 80)
print(f"VARIANT COMPARISON ({SIZE_FRAC:.0%} capital per trade)")
print("=" * 80)
display(pd.DataFrame(rows))

print("\nCHECKS (7):")
k_naked, k_g = list(variants)[0], list(variants)[1]
g, nk = raw[k_g], raw[k_naked]
check("7. Variants", "Gotobi Profit Factor beats the naked window", g["pf"] > nk["pf"], f"gotobi {g['pf']:.3f} | naked {nk['pf']:.3f}")
check("7. Variants", "Gotobi expectancy per trade beats the naked window", g["exp"] > nk["exp"], f"gotobi {g['exp']:+.4f}% | naked {nk['exp']:+.4f}%")
check("7. Variants", "Gotobi Sharpe beats the naked window", g["sharpe"] > nk["sharpe"], f"gotobi {g['sharpe']:.2f} | naked {nk['sharpe']:.2f}")
for fp in FLAT_PIPS:
    k = f"Gotobi, flat {fp:g} pips"
    check("7. Variants", f"Survives a flat {fp:g} pips cost (PF >= {PF_MIN:g}, t >= {T_MIN:g})", raw[k]["pf"] >= PF_MIN and raw[k]["t"] >= T_MIN,
          f"PF {raw[k]['pf']:.3f} | t {raw[k]['t']:.2f}")

fig, ax = plt.subplots(figsize=(12, 5), facecolor=BG)
dark_ax(ax)
for (name, eq), col in zip(curves.items(), (SUB, GREEN, "#5468ff", ORANGE)):
    ax.plot(eq.index, eq, color=col, lw=1.6, label=name)
ax.axvline(oos_start, color=ORANGE, ls="--", lw=1.2, label="OOS start")
ax.set_title("Equity Curve Comparison: naked window vs Gotobi vs cost scenarios", color=TXT, fontweight="bold", loc="left")
ax.legend(frameon=False, labelcolor=SUB, fontsize=9, loc="upper left")
plt.tight_layout(); plt.show()
```

    ================================================================================
    VARIANT COMPARISON (250% capital per trade)
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
      <th>Net t</th>
      <th>Sharpe</th>
      <th>Max Drawdown</th>
      <th>Final Capital</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>0</th>
      <td>Naked window (every business day)</td>
      <td>2546</td>
      <td>53.3%</td>
      <td>1.067</td>
      <td>1.14</td>
      <td>0.35</td>
      <td>-18.64%</td>
      <td>1.23x</td>
    </tr>
    <tr>
      <th>1</th>
      <td>Gotobi (feed x 0.7)</td>
      <td>697</td>
      <td>59.8%</td>
      <td>1.525</td>
      <td>3.91</td>
      <td>1.22</td>
      <td>-4.23%</td>
      <td>1.52x</td>
    </tr>
    <tr>
      <th>2</th>
      <td>Gotobi, flat 0.7 pips</td>
      <td>697</td>
      <td>60.4%</td>
      <td>1.614</td>
      <td>4.44</td>
      <td>1.38</td>
      <td>-4.20%</td>
      <td>1.62x</td>
    </tr>
    <tr>
      <th>3</th>
      <td>Gotobi, flat 1 pips</td>
      <td>697</td>
      <td>59.8%</td>
      <td>1.549</td>
      <td>4.06</td>
      <td>1.26</td>
      <td>-4.30%</td>
      <td>1.55x</td>
    </tr>
  </tbody>
</table>
</div>

    CHECKS (7):
       [PASS] Gotobi Profit Factor beats the naked window  ->  gotobi 1.525 | naked 1.067
       [PASS] Gotobi expectancy per trade beats the naked window  ->  gotobi +0.0245% | naked +0.0036%
       [PASS] Gotobi Sharpe beats the naked window  ->  gotobi 1.22 | naked 0.35
       [PASS] Survives a flat 0.7 pips cost (PF >= 1.2, t >= 2.5)  ->  PF 1.614 | t 4.44
       [PASS] Survives a flat 1 pips cost (PF >= 1.2, t >= 2.5)  ->  PF 1.549 | t 4.06

![png](01_Gotobi_Hypothesis_Definition_files/01_Gotobi_Hypothesis_Definition_23_3.png)

## 8. SUMMARY OF HYPOTHESIS & NEXT STEPS

```python
m_all, m_is, m_oos = (compute_metrics(t, 1.0, 0.0) for t in (trades_all, trades_is, trades_oos))
t_all = tstat(trades_all["pnl"])
ret_fr_all = eng.daily_returns(df, trades_all, sizing="fraction")
max_dd_fr = max_drawdown((1 + ret_fr_all).cumprod()) * 100
years = (df.index[-1] - df.index[0]).days / 365.25
next_nb = "02_Gotobi_Sensitivity.ipynb"

confirmed = bool(m_all["profit_factor"] >= PF_MIN and m_oos["profit_factor"] >= PF_MIN and t_all >= T_MIN and m_all["num_trades"] >= N_MIN)
verdict = "Hypothesis Confirmed" if confirmed else "Hypothesis NOT clearly confirmed"
check("8. Verdict", f"Core criteria: PF >= {PF_MIN:g} (full and OOS), net t >= {T_MIN:g}, N >= {N_MIN}", confirmed,
      f"PF {m_all['profit_factor']:.3f} / OOS {m_oos['profit_factor']:.3f} | t {t_all:.2f} | N {m_all['num_trades']}", quiet=True)

# ---- GO / STOP gate: only the checks that decide whether the research continues ----
# (section, start of the check name, what to do if it FAILS). Remove a line to stop treating it as a gate.
ESSENTIAL = [
    ("6. Sanity",       "No lookahead",                        "Fix the execution model first: every other number is invalid until this passes."),
    ("6. Sanity",       "Engine calendar matches",             "The engine trades different dates than the gotobi calendar: review shift, end-of-month and the JST conversion."),
    ("5. Baseline",     "Profit Factor, IS",                   "Baseline does not hold in-sample: the hypothesis is not supported, rethink the rules."),
    ("5. Baseline",     "Profit Factor, OOS",                  "Baseline does not hold out-of-sample: the edge is not confirmed."),
    ("5. Baseline",     "Net t-stat of the mean trade",        "The mean trade does not clear the multiple-testing bar: the edge could be noise."),
    ("5. Baseline",     "Trades, full period",                 "Too few trades to conclude anything."),
    ("5. Baseline",     "Trades, OOS",                         "Too few OOS trades to validate the edge."),
    ("4.2 Placebos",    "No placebo window is significant",    "A neighbouring window is also significant: the effect is a Tokyo-morning drift, not a gotobi effect."),
    ("4.2 Placebos",    "Real window has the highest mean",    "A placebo window beats the real one: the calendar rule adds nothing."),
    ("4.3 Payment dates", "No single payment date",           "One payment date carries the edge: restrict or rethink the calendar."),
    ("7. Variants",     "Gotobi Profit Factor beats",          "Gotobi does not beat the naked window: the calendar filter is not justified."),
    ("7. Variants",     "Survives a flat 1 pips cost",         "The edge disappears with a 1 pip cost: measure the real Axi spread at 22:30 UTC before going on."),
    ("5.1 Hard limit",  "Lot-adjusted sizing stays inside",    "Lot-adjusted sizing breaks the hard limit: reduce the size fraction."),
    ("5.1 Hard limit",  "Capital >= minimum capital",          "Capital is below what the minimum lot needs."),
    ("5.2 Annual",      "No calendar year breaches",           "A calendar year breaches the hard limit: review sizing or the rules of that year."),
]
chk = pd.DataFrame(CHECKS)
n_pass, n_fail, n_skip = (int((chk["status"] == s).sum()) for s in ("PASS", "FAIL", "SKIP"))
key = {(s, n): a for s, n, a in ESSENTIAL}
chk["essential"] = [any(sec == s and nm.startswith(n) for s, n, _ in ESSENTIAL) for sec, nm in zip(chk["section"], chk["name"])]
ess = chk[chk["essential"]]
missing = [f"{s}: {n}" for s, n, _ in ESSENTIAL if not ((chk["section"] == s) & chk["name"].str.startswith(n)).any()]
ess_fail = ess[ess["status"] == "FAIL"]
go = ess_fail.empty and not missing

print("=" * 80)
print("8. SUMMARY OF HYPOTHESIS & NEXT STEPS")
print("=" * 80)
print(f"\nDECISION: {'GO - continue the research' if go else 'STOP - fix the failed gates before continuing'}   "
      f"({int((ess['status'] == 'PASS').sum())} PASS / {len(ess_fail)} FAIL / {int((ess['status'] == 'SKIP').sum())} SKIP of {len(ESSENTIAL)} essential checks)   |   {verdict}")
if missing:
    print("   Not run (run the sections above first): " + "; ".join(missing))
print("\n" + "-" * 80 + "\nESSENTIAL CHECKS\n" + "-" * 80)
for sec, gr in ess.groupby("section", sort=False):
    print(f"\n{sec}")
    for _, row in gr.iterrows():
        print(f"   [{row['status']}] {row['name']}" + (f"  ->  {row['detail']}" if row["detail"] else ""))

print("\n" + "-" * 80 + "\nKEY FINDINGS\n" + "-" * 80)
print(f"""
1. {verdict}: {m_all['num_trades']} trades over {years:.0f}+ years, win rate {m_all['win_rate']:.1f}%, Profit Factor {m_all['profit_factor']:.3f}
   (IS {m_is['profit_factor']:.3f} / OOS {m_oos['profit_factor']:.3f}), net t-stat of the mean trade {t_all:.2f} (bar: {T_MIN:g}).

2. Specificity: real window mean {plc_tbl.loc[0, 'Gross mean %']:+.4f}% vs best placebo {others['Gross mean %'].max():+.4f}% (max placebo t = {others['Gross t'].max():.2f}).

3. Calendar: top payment date carries {top_share:.0%} of the net edge.

4. Risk at {SIZE_FRAC:.0%} sizing: max daily-MTM drawdown {max_dd_fr:.2f}% over {df.index[0].year}-{df.index[-1].year}; hard limit -{HARD_LIMIT:.0%}.

5. Costs are a placeholder ({COST_MODE} x {SPREAD_SCALE:g}): the real Axi spread at 22:30 UTC is still to be measured with the logger.
""")
print("-" * 80 + "\nNEXT STEPS\n" + "-" * 80)
steps = [key[(r["section"], next(n for s, n, _ in ESSENTIAL if s == r["section"] and r["name"].startswith(n)))] for _, r in ess_fail.iterrows()]
if missing:
    steps.append("Run all the sections above so every essential check is evaluated.")
if go:
    steps.append(f"Proceed to {next_nb} to check that the entry / exit window sits on a broad, stable plateau on in-sample data.")
steps.append("Measure the real Axi spread at 22:30 UTC and replace spread_scale in the variant YAML.")
steps.append("Compute the correlation with the Monday Effect (trades_all of both engines) before sizing the portfolio.")
for i, s in enumerate(steps, 1):
    print(f"{i}. {s}")
```

    ================================================================================
    8. SUMMARY OF HYPOTHESIS & NEXT STEPS
    ================================================================================

    DECISION: STOP - fix the failed gates before continuing   (14 PASS / 1 FAIL / 0 SKIP of 15 essential checks)   |   Hypothesis Confirmed

    --------------------------------------------------------------------------------
    ESSENTIAL CHECKS
    --------------------------------------------------------------------------------

    4.2 Placebos
       [PASS] Real window has the highest mean of all offsets  ->  best offset = 0 | real +0.0335% vs best placebo +0.0178%
       [FAIL] No placebo window is significant (t < 2)  ->  -2: t = 2.18; -1: t = 0.73; +1: t = 2.90; +2: t = 0.91

    4.3 Payment dates
       [PASS] No single payment date carries more than 40% of the net edge  ->  top date = 20 with 31% of the net edge

    5. Baseline
       [PASS] Profit Factor, IS >= 1.2  ->  PF = 1.764
       [PASS] Profit Factor, OOS >= 1.2  ->  PF = 1.271
       [PASS] Net t-stat of the mean trade >= 2.5 (raised for 17 hypotheses tested)  ->  t = 3.91
       [PASS] Trades, full period >= 600  ->  697 trades
       [PASS] Trades, OOS >= 150  ->  272 trades

    5.1 Hard limit
       [PASS] Lot-adjusted sizing stays inside -9%  ->  max DD -4.98% | headroom +4.02 pts
       [PASS] Capital >= minimum capital for the minimum lot  ->  10,000 vs 400

    5.2 Annual
       [PASS] No calendar year breaches the hard limit  ->  years in breach: none | worst year DD -5.0%

    6. Sanity
       [PASS] No lookahead and execution model respected on every trade  ->  697 trades checked
       [PASS] Engine calendar matches the notebook calendar (>= 99% of dates)  ->  0 only in engine, 0 only in notebook of 697

    7. Variants
       [PASS] Gotobi Profit Factor beats the naked window  ->  gotobi 1.525 | naked 1.067
       [PASS] Survives a flat 1 pips cost (PF >= 1.2, t >= 2.5)  ->  PF 1.549 | t 4.06

    --------------------------------------------------------------------------------
    KEY FINDINGS
    --------------------------------------------------------------------------------

    1. Hypothesis Confirmed: 697 trades over 10+ years, win rate 59.8%, Profit Factor 1.525
       (IS 1.764 / OOS 1.271), net t-stat of the mean trade 3.91 (bar: 2.5).

    2. Specificity: real window mean +0.0335% vs best placebo +0.0178% (max placebo t = 2.90).

    3. Calendar: top payment date carries 31% of the net edge.

    4. Risk at 250% sizing: max daily-MTM drawdown -4.23% over 2017-2026; hard limit -9%.

    5. Costs are a placeholder (feed x 0.7): the real Axi spread at 22:30 UTC is still to be measured with the logger.

    --------------------------------------------------------------------------------
    NEXT STEPS
    --------------------------------------------------------------------------------
    1. A neighbouring window is also significant: the effect is a Tokyo-morning drift, not a gotobi effect.
    2. Measure the real Axi spread at 22:30 UTC and replace spread_scale in the variant YAML.
    3. Compute the correlation with the Monday Effect (trades_all of both engines) before sizing the portfolio.

## 9. SAVE THE RESULTS OF THIS NOTEBOOK FOR THE VARIANT

```python
limit_report = eng.hard_limit_report(bar_lot, HARD_LIMIT)

save_json(cfg, "01_hypothesis.json", {
    "variant": cfg["id"],
    "ticker": TICKER,
    "params": cfg["params"],
    "costs": cfg["costs"],
    "oos_start": str(oos_start.date()),
    "all": {"n": int(len(trades_all)), "pf": float(m_all["profit_factor"]), "win_rate": float(m_all["win_rate"]), "t_stat": float(t_all)},
    "is":  {"n": int(len(trades_is)),  "pf": float(m_is["profit_factor"])},
    "oos": {"n": int(len(trades_oos)), "pf": float(m_oos["profit_factor"])},
    "max_dd_fraction_sizing_pct": float(max_dd_fr),
    "hard_limit": {"limit": float(HARD_LIMIT), "max_dd_bar_pct": float(limit_report["max_dd"] * 100), "passed": bool(limit_report["passed"])},
    "window_by_period": win_tbl.round(4).reset_index().to_dict(orient="records"),
    "placebos": plc_tbl.round(4).reset_index().to_dict(orient="records"),
    "payment_dates": dom.round(4).reset_index().to_dict(orient="records"),
    "hypotheses_tested": int(EV["hypotheses_tested"]),
    "min_t_net": float(T_MIN),
    "hypothesis_confirmed": bool(confirmed),
    "checks_summary": {"pass": n_pass, "fail": n_fail, "skip": n_skip},
    "checks": CHECKS,
})
```

    Saved: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy/01_hypothesis.json





    PosixPath('/Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/USDJPY_Gotobi/runs/v1_axi_usdjpy/01_hypothesis.json')
