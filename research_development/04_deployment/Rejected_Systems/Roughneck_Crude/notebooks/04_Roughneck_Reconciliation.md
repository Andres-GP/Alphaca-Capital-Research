# 04 · ROUGHNECK CRUDE OIL · RECONCILIATION
**Alphaca Capital** · compares the MT5 Expert Advisor (Strategy Tester) with the Python engine, in three layers: **(A) data parity** (the EA's D1 candles vs the daily bars the engine builds from H1), **(B) signal parity** (ATR, trigger distance, stop price and decision on every close) and **(C) trade parity** (entries, exits and prices of the Tester's deals).

Expected inputs (the EA writes them from `OnTick` at each new D1 bar and from the Tester report):
- `roughneck_log.csv`, `;`-separated, no header: `time;open;high;low;close;atr;long_dist;short_dist;signal;stop_px;decision;reason` (one row per closed D1 bar; `signal` in `LONG|SHORT|NONE`; `decision` in `BUY_STOP|SELL_STOP|NONE`).
- `roughneck_deals.csv`, `;`-separated, with header: `time_open;time_close;type;price_open;price_close;lots;profit` (Tester history, one row per trade).


```
VARIANT = "v1_axi_usoil"
HARD_LIMIT = 0.09
CAPITAL = 10_000.0
LOG_PATH   = r"../../data/Reconcilation/Roughneck/roughneck_log.csv"
DEALS_PATH = r"../../data/Reconcilation/Roughneck/roughneck_deals.csv"
```

## CONFIG


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

# ---- Acceptance thresholds: every PASS / FAIL in this notebook is judged against these ----
TOL_PRICE_USD   = 0.05     # price tolerance between EA and engine (candles, entries, exits)
TOL_ATR_USD     = 0.01     # ATR tolerance (simple vs Wilder shows up here)
MIN_SIGNAL_MATCH = 0.98    # share of closes with the same decision
MIN_TRADE_MATCH  = 0.95    # share of trades matched by entry date

CHECKS = []
def check(section, name, passed, detail="", quiet=False):
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
print(f"Loaded roughneck_engine from: {eng.__file__}")
print(f"Edge dir: {EDGE_DIR}")
print(f"Variant: {cfg['id']} | {TICKER} | long: trend + close > LL({P['long_low_n']}) + {P['long_atr_mult']:g} ATR({P['atr_len']}) | "
      f"short: close < HH({P['short_high_n']}) - {P['short_atr_mult']:g} ATR | stop ${P['stop_dollar']:g} | {COST_BPS:g} bps/side | size {SIZE_FRAC:.0%}")
print(f"Data source: {eng.ENGINE_DEFAULTS['data_source']} | swap: {eng.ENGINE_DEFAULTS['financing_bps_per_night']:g} bps/night | ATR method: {P['atr_method']}")
print(f"Run folder: {RUN_DIR}")
print(f"CFD: contract {CONTRACT_SIZE:g} bbl/lot | min lot {MIN_LOT:g} | step {LOT_STEP:g} | capital {CAPITAL:,.0f} | hard limit -{HARD_LIMIT:.0%}")

df_raw = eng.load_data(TICKER, start=DATA_START)
df = prep(df_raw)
trades_all = eng.run_roughneck_backtest(df, **RULES)
print(len(df_raw), "daily bars |", df_raw.index[0].date(), "->", df_raw.index[-1].date(), "| engine trades:", len(trades_all))
```

## A. DATA PARITY: EA D1 CANDLES VS ENGINE DAILY BARS


```
log = pd.read_csv(LOG_PATH, sep=";", header=None, parse_dates=["time"] if False else None,
                  names=["time", "open", "high", "low", "close", "atr", "long_dist", "short_dist", "signal", "stop_px", "decision", "reason"])
log["time"] = pd.to_datetime(log["time"]).dt.normalize()
print("duplicated days in the log:", log["time"].duplicated().sum())          # must be 0
log = log[~log["time"].duplicated(keep="last")].set_index("time")

j = df.join(log, how="outer", lsuffix="_eng", rsuffix="_ea", sort=True)
j["_merge"] = np.where(j["open_ea"].isna(), "engine_only", np.where(j["open_eng"].isna(), "ea_only", "both"))
print(j["_merge"].value_counts().to_dict())
both = j[j["_merge"] == "both"]
d_ohlc = pd.DataFrame({c: (both[f"{c}_eng"] - both[f"{c}_ea"]).abs() for c in ("open", "high", "low", "close")})
print("max abs candle difference (USD):", d_ohlc.max().round(3).to_dict())

print("\nCHECKS (A):")
check("A. Data", "Every EA close exists in the engine (no EA-only days)", int((j["_merge"] == "ea_only").sum()) == 0, f"{int((j['_merge'] == 'ea_only').sum())} EA-only days")
check("A. Data", f"Candles match within {TOL_PRICE_USD} USD on >= 99% of days", (d_ohlc.max(axis=1) <= TOL_PRICE_USD).mean() >= 0.99,
      f"{(d_ohlc.max(axis=1) <= TOL_PRICE_USD).mean():.1%} of {len(both)} days")
bad_days = d_ohlc[d_ohlc.max(axis=1) > TOL_PRICE_USD]
print("Days whose candle differs (usually the server-time offset / DST weeks, or the 17:00 NY cutoff):")
display(bad_days.round(3).head(15))
```

## B. SIGNAL PARITY: ATR, TRIGGER DISTANCE, STOP PRICE AND DECISION


```
ref = df[["atr", "long_dist", "short_dist", "long_sig", "short_sig", "long_stop_px", "short_stop_px", "warm"]].copy()
ref["eng_dec"] = np.where(ref["long_sig"] & ref["warm"], "BUY_STOP", np.where(ref["short_sig"] & ref["warm"], "SELL_STOP", "NONE"))
sig = ref.join(log[["atr", "long_dist", "short_dist", "stop_px", "decision", "reason"]], how="inner", rsuffix="_ea")
sig["ea_dec"] = sig["decision"].fillna("NONE")
sig["eng_stop"] = np.where(sig["eng_dec"] == "BUY_STOP", sig["long_stop_px"], np.where(sig["eng_dec"] == "SELL_STOP", sig["short_stop_px"], np.nan))

valid = sig[sig["warm"]]
d_atr = (valid["atr"] - valid["atr_ea"]).abs()
d_ld = (valid["long_dist"] - valid["long_dist_ea"]).abs()
d_sd = (valid["short_dist"] - valid["short_dist_ea"]).abs()
same = valid["eng_dec"] == valid["ea_dec"]
print(f"closes with warm-up done in both: {len(valid)}")
print(f"ATR diff > {TOL_ATR_USD}: {(d_atr > TOL_ATR_USD).sum()} | max {d_atr.max():.4f}")
print(f"trigger-distance diff > 0.01 ATR: long {(d_ld > 0.01).sum()} | short {(d_sd > 0.01).sum()}")
print(f"engine decisions: {valid['eng_dec'].value_counts().to_dict()} | EA decisions: {valid['ea_dec'].value_counts().to_dict()}")
print(f"different decisions: {(~same).sum()}")

print("\nCHECKS (B):")
check("B. Signals", f"ATR matches within {TOL_ATR_USD} USD on >= 99% of closes (simple ATR in both)", (d_atr <= TOL_ATR_USD).mean() >= 0.99, f"{(d_atr <= TOL_ATR_USD).mean():.1%} | max {d_atr.max():.4f}")
check("B. Signals", f"Same decision on >= {MIN_SIGNAL_MATCH:.0%} of closes", same.mean() >= MIN_SIGNAL_MATCH, f"{same.mean():.2%} ({int((~same).sum())} differences)")
st = valid[(valid["eng_dec"] != "NONE") & same]
d_stop = (st["eng_stop"] - st["stop_px"]).abs()
check("B. Signals", f"Stop price matches within {TOL_PRICE_USD} USD when both place an order", (d_stop <= TOL_PRICE_USD).all() if len(st) else None, f"{len(st)} orders | max diff {d_stop.max():.3f}" if len(st) else "no common orders")

bad = valid[~same]
print("\nDays with a different decision:")
display(bad[["atr", "atr_ea", "long_dist", "long_dist_ea", "short_dist", "short_dist_ea", "eng_dec", "ea_dec", "reason"]].round(4).head(25))
warm = log[log["reason"].astype(str).str.contains("warm|history", case=False, na=False)]
print("\nEA warm-up rows:", len(warm), "|", (warm.index.min(), warm.index.max()) if len(warm) else "none")
```

## C. TRADE PARITY: ENTRIES AND EXITS OF THE TESTER VS THE ENGINE


```
deals = pd.read_csv(DEALS_PATH, sep=";", parse_dates=["time_open", "time_close"])
deals["day"] = deals["time_open"].dt.normalize()
eng_t = trades_all.assign(day=pd.to_datetime(trades_all["entry_time"]).dt.normalize())
m = eng_t.merge(deals, on="day", how="outer", indicator=True, suffixes=("_eng", "_ea"))
print("trades EA:", len(deals), "| engine:", len(eng_t))
print(m["_merge"].value_counts().to_dict())
b = m[m["_merge"] == "both"].copy()
b["d_entry"] = (b["entry_price"] - b["price_open"]).abs()
b["d_exit"] = (b["exit_price"] - b["price_close"]).abs()
b["same_dir"] = b["type_eng"] == b["type_ea"].str.lower()
print(f"entry price diff: median {b['d_entry'].median():.3f} max {b['d_entry'].max():.3f} | exit price diff: median {b['d_exit'].median():.3f} max {b['d_exit'].max():.3f}")

print("\nCHECKS (C):")
check("C. Trades", f"Entries matched by date on >= {MIN_TRADE_MATCH:.0%} of trades", (m["_merge"] == "both").mean() >= MIN_TRADE_MATCH, f"{(m['_merge'] == 'both').mean():.1%} ({len(b)} matched)")
check("C. Trades", "Same direction on every matched trade", bool(b["same_dir"].all()), f"{int((~b['same_dir']).sum())} different")
check("C. Trades", f"Entry price within {TOL_PRICE_USD} USD on >= 95% of matched trades (stop fill vs gap fill)", (b["d_entry"] <= TOL_PRICE_USD).mean() >= 0.95, f"{(b['d_entry'] <= TOL_PRICE_USD).mean():.1%}")
check("C. Trades", f"Exit price within {TOL_PRICE_USD} USD on >= 90% of matched trades", (b["d_exit"] <= TOL_PRICE_USD).mean() >= 0.90, f"{(b['d_exit'] <= TOL_PRICE_USD).mean():.1%}")
check("C. Trades", "Same exit date on >= 90% of matched trades", (pd.to_datetime(b["exit_time"]).dt.normalize() == b["time_close"].dt.normalize()).mean() >= 0.90,
      f"{(pd.to_datetime(b['exit_time']).dt.normalize() == b['time_close'].dt.normalize()).mean():.1%}")
print("\nTrades present on one side only:")
display(m[m["_merge"] != "both"][["day", "type_eng", "type_ea", "entry_price", "price_open", "_merge"]].head(20))
print("Matched trades with an exit gap above the tolerance (intrabar ordering: the engine assumes the worst case on the entry bar; the EA sees real ticks):")
display(b[b["d_exit"] > TOL_PRICE_USD][["day", "type_eng", "exit_reason", "entry_price", "price_open", "exit_price", "price_close", "d_exit"]].round(3).head(20))
```

## D. DIAGNOSIS GUIDE
- **Candles differ (A)** -> server-time offset / DST (`server_tz` in the YAML) or the 17:00 NY cutoff; fix the data first, every other layer inherits it.
- **ATR differs (B)** -> the EA uses a different ATR average (simple vs Wilder: `atr_method`) or a different warm-up length.
- **Decision differs with equal ATR and distances** -> a rule was coded differently (trend slope in price units, `>=` vs `>`, 4-day high including or excluding the signal bar).
- **Entry differs by the gap** -> the EA fills a stop at the open when the open is beyond it; so does the engine (`max(stop, open)`): check for the orders' expiry (valid next day only).
- **Exit differs** -> stop recalculated intrabar in the EA (the engine uses stops known at the previous close) or trailing tiers using the wrong ATR (previous close vs current).

## E. SUMMARY


```
chk = pd.DataFrame(CHECKS)
print("=" * 80)
print("RECONCILIATION SUMMARY")
print("=" * 80)
for sec, g in chk.groupby("section", sort=False):
    print(f"\n{sec}")
    for _, row in g.iterrows():
        print(f"   [{row['status']}] {row['name']}" + (f"  ->  {row['detail']}" if row["detail"] else ""))
n_fail = int((chk["status"] == "FAIL").sum())
print("\nVERDICT:", "EA and engine are in parity." if n_fail == 0 else f"{n_fail} check(s) failed: use section D to find the cause before trusting either side.")
save_json(cfg, "04_reconciliation.json", {"variant": cfg["id"], "checks": CHECKS, "parity": n_fail == 0})
```
