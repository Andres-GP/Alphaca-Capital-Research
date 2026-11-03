"""
gotobi_engine.py  ·  02_strategy_development/Gotobi/gotobi_engine.py   (v1.0)

Engine for the USDJPY edge · Gotobi effect (5-minute bars, UTC). Same API shape as monday_effect_engine and
rsi2_engine, so notebooks 01/02/03/04 follow the same pattern:

    load_data / prepare / run_gotobi_backtest / daily_returns / trade_mtm_paths /
    walk_forward_fixed / set_engine_defaults / ENGINE_DEFAULTS

Dependency specific to this edge:  holidays  (requirements_gotobi.txt; tested with 0.108). It is only used for the
Japanese holiday calendar; alternative: holiday_source="csv" and calendar_csv="<file>.csv" (one 'date' column).

RULE (frozen, see variants/*.yaml)
  - Gotobi days (Japan time): 5, 10, 15, 20, 25 and the LAST DAY OF THE MONTH (EOM: 28/29/30/31). If the date is not
    a Japanese BANK business day (Saturday, Sunday, holiday, 31 Dec, 1-3 Jan) it moves to the PREVIOUS business day.
    Two dates falling on the same day count once (e.g. 5 May and 30 Apr in Golden Week).
  - Entry: buy at the OPEN of the 07:30 JST M5 bar (= 22:30 UTC of the previous day).
  - Exit:  sell at the OPEN of the 09:55 JST M5 bar (= 00:55 UTC, Tokyo fixing). Always 29 bars.
  - Long only. No stop or target (stop_bps is OPT-IN, only for tail tests / EA). Days and times are NOT optimised.
  - The position never crosses a rollover (it opens 30 min after the winter one and 90 min after the summer one):
    swap = 0, checked and stored in trades['rollovers'].

DATA AND TIME (verified on usdjpy_M5_200001022200_202611030050.csv; symbol = USDJPY, 3 decimals)
  - Raw MetaTrader export in SERVER time (GMT+2 winter / GMT+3 summer, US DST). load_data converts it to UTC
    (time_mode="mt5_server_ny"); check_weekly_structure() verifies it (99.8 % of weekly opens OK).
  - Before ~2008 the server used another clock and US DST rules were different: use start >= 2010.
  - The CSV price is BID. A buy fills at the ASK (= bid + spread) and exits at the BID: the round-trip cost is ONE
    spread, that of the entry bar. CSV SPREAD is in points (1 pip = 10 points).

  WARNINGS ABOUT THE FEED SPREAD (measured, see validate() and spread_summary()):
    * Until ~2020 the historical feed spread is almost CONSTANT within a year (p50 = p90) and jumps between years
      (0.2 pips in 2013, 1.9 in 2010): it is the modelled history spread, not the real one. A real tail only appears
      from 2021. Hence spread_scale (calibrated on 2024-26) is NOT valid for 2010-2020: use cost_mode="flat_pips"
      as a robustness check of the historical net result.
    * The wide tail (p90 ~ 6.8 pips) is a WINTER effect: 95 % of the trades at p90+ are winter trades; at 22:30 UTC
      only 30 min have passed since the rollover. In summer p90 = 1.8 pips.

Costs (cost_mode):
  "feed"      : entry = open + entry_bar_spread * spread_scale, exit = open.
  "flat_pips" : entry = open + flat_spread_pips * pip_size (flat Axi spread; robustness), exit = open.
  "fixed"     : entry = open*(1+c), exit = open*(1-c), c = cost_bps_per_side (convention of the other engines).
  In all modes commission_bps_per_side and slippage_bps_per_side are added (per side, default 0).

Conventions:
  - df index = UTC naive ('time'). Trade dates are JAPAN dates (JST = UTC+9).
  - trades['pnl'] is in % with 100 % of capital (same as utils.compute_metrics); pnl_bps = pnl*100.
  - trades['pnl_frac'] = pnl * size_fraction (NOMINAL fraction of capital; may be > 1 = leverage).
    Real risk is measured with hard_limit_report_intrabar / max_fraction_for_limit.
  - CFD approximation: P&L in a USD account ignores convexity (fixed USD notional): < 0.3 % of P&L.
  - Daily returns use business days (Mon-Fri, JST date) with 0 on days without a trade.
  - Statistics (t, p) use a normal approximation; trades do not overlap. The significance threshold depends on the
    number of hypotheses tested: hypothesis_threshold(k).
"""
from __future__ import annotations

import datetime as dt
from statistics import NormalDist
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
M5 = pd.Timedelta(minutes=5)
JST = pd.Timedelta(hours=9)
_UNSET = None

ENGINE_DEFAULTS = dict(
    data_source="csv_m5",
    csv_path="../../data/axi/usdjpy_M5_200001022200_202611030050.csv",
    time_mode="mt5_server_ny",
    server_utc_offset_hours=2.0,  # only if time_mode="fixed"
    point_size=0.001,  # symbol point size (USDJPY: 3 decimals)
    pip_size=0.01,
    # --- calendar ---
    gotobi_days=(5, 10, 15, 20, 25),
    include_month_end=True,
    shift_rule="previous",  # "previous" | "next" | "none" (if not a business day, skip it)
    holiday_source="holidays",  # "holidays" (package) | "csv"
    calendar_csv=None,
    extra_holidays=(),
    # --- trade window (Japan time) ---
    entry_time="07:30",
    exit_time="09:55",
    max_delay_min=5,  # if the exact bar is missing, use the next one within this margin (else no trade)
    # --- costs ---
    cost_mode="feed",              # "feed" | "flat_pips" | "fixed"
    flat_spread_pips=1.0,          # only "flat_pips": flat Axi spread (pips)
    cost_bps_per_side=0.5,
    spread_scale=0.7,  # PLACEHOLDER: Axi spread / median feed spread (0.7 pips / 1.0 pips)
    commission_bps_per_side=0.0,
    slippage_bps_per_side=0.0,
    max_entry_spread_pips=None,  # execution filter (Axi-equivalent spread); float("inf") = no filter
    stop_bps=0.0,  # 0 = no stop
    stop_slippage_bps=0.0,
    financing_bps_per_night=0.0,  # trade never crosses a rollover: only matters if you change the window
    # --- sizing ---
    size_fraction=1.0,
    account_ccy="USD",
    contract_size=100000.0,  # units of base currency per lot
    min_lot=0.01,
    lot_step=0.01,
)

CFD_PRESETS = {
    "axi_usdjpy": dict(contract_size=100000.0, min_lot=0.01, lot_step=0.01, point_size=0.001, pip_size=0.01,
                       financing_bps_per_night=0.0),
}


def set_engine_defaults(**kw):
    """Override ENGINE_DEFAULTS in place (validated keys only)."""
    for k, v in kw.items():
        if k not in ENGINE_DEFAULTS:
            raise KeyError(f"'{k}' is not a valid engine default. Valid keys: {sorted(ENGINE_DEFAULTS)}")
        if k in ("gotobi_days", "extra_holidays") and v is not None:
            v = tuple(v)
        ENGINE_DEFAULTS[k] = v


def apply_cfd_preset(name, spread_scale=None, **extra):
    """Apply a CFD preset (contract size, lot step, ...) and optionally the Axi spread scale."""
    if name not in CFD_PRESETS:
        raise KeyError(f"Preset '{name}' does not exist. Valid presets: {sorted(CFD_PRESETS)}")
    kw = dict(CFD_PRESETS[name])
    if spread_scale is not None:
        kw["spread_scale"] = float(spread_scale)
    kw.update(extra)
    set_engine_defaults(**kw)
    return {k: ENGINE_DEFAULTS[k] for k in kw}


def _cfg(name, value):
    return ENGINE_DEFAULTS[name] if value is None else value


def _nth_sunday(year, month, n):
    """The n-th Sunday of a month."""
    d = pd.Timestamp(year, month, 1)
    return d + pd.Timedelta(days=(6 - d.dayofweek) % 7) + pd.Timedelta(weeks=n - 1)


def us_dst_mask(index) -> np.ndarray:
    """True during US daylight saving time (2nd Sunday of March <= date < 1st Sunday of November).
        Decided by DATE: that Sunday the market is closed, so there is no ambiguity."""
    ix = pd.DatetimeIndex(index)
    day, out = ix.normalize(), np.zeros(len(ix), bool)
    for y in np.unique(ix.year):
        out |= (ix.year == y) & (day >= _nth_sunday(y, 3, 2)) & (day < _nth_sunday(y, 11, 1))
    return out


def server_to_utc(index, mode=None) -> pd.DatetimeIndex:
    """Server time -> UTC. 'mt5_server_ny': GMT+2 in winter / GMT+3 in summer (US DST)."""
    mode, ix = _cfg("time_mode", mode), pd.DatetimeIndex(index)
    if mode == "utc":
        return ix
    if mode == "fixed":
        return ix - pd.Timedelta(hours=float(ENGINE_DEFAULTS["server_utc_offset_hours"]))
    if mode == "mt5_server_ny":
        return ix - pd.to_timedelta(np.where(us_dst_mask(ix), 3, 2), unit="h")
    raise ValueError("time_mode must be 'mt5_server_ny', 'utc' or 'fixed'")


def utc_to_server(index, mode=None) -> pd.DatetimeIndex:
    """UTC -> server time (what the EA sees with TimeCurrent())."""
    mode, ix = _cfg("time_mode", mode), pd.DatetimeIndex(index)
    if mode == "utc":
        return ix
    if mode == "fixed":
        return ix + pd.Timedelta(hours=float(ENGINE_DEFAULTS["server_utc_offset_hours"]))
    if mode == "mt5_server_ny":
        return ix + pd.to_timedelta(np.where(us_dst_mask(ix), 3, 2), unit="h")
    raise ValueError("time_mode must be 'mt5_server_ny', 'utc' or 'fixed'")


def _hhmm(s) -> pd.Timedelta:
    """"HH:MM" -> Timedelta."""
    parts = str(s).strip().split(":")
    return pd.Timedelta(hours=int(parts[0]), minutes=int(parts[1]))


def _find_csv(csv_path) -> Path:
    """Resolve a CSV path robustly (absolute, relative to cwd, to this file, or to any parent folder)."""
    p = Path(csv_path)
    if p.is_absolute():
        if p.is_file():
            return p
        raise FileNotFoundError(p)
    tail = Path(*[s for s in p.parts if s != ".."])
    cwd = Path.cwd().resolve()
    cands = [cwd / p, _HERE / p]
    cands += [b / tail for b in (cwd, *cwd.parents, _HERE, *_HERE.parents)]
    for c in cands:
        if c.is_file():
            return c.resolve()
    raise FileNotFoundError(f"Could not find '{csv_path}'. Searched from cwd={cwd} and from {_HERE}.")


def load_data(ticker=None, start=None, end=None, source=None, csv_path=None, time_mode=None, verbose=True):
    """M5 CSV (raw MetaTrader export or CSV with a 'time' column) -> DataFrame with a UTC naive index.
        Columns: open, high, low, close, spread (points) and volume (tick volume if present)."""
    source = source or ENGINE_DEFAULTS["data_source"]
    if source != "csv_m5":
        raise ValueError("This engine only reads M5 CSV files (csv_m5).")
    path = _find_csv(csv_path or ENGINE_DEFAULTS["csv_path"])
    with open(path, "r", encoding="utf-8-sig") as f:
        head = f.readline()
    sep = max(("\t", ";", ","), key=head.count)
    raw = pd.read_csv(path, sep=sep)
    raw.columns = [str(c).strip().strip("<>").strip().lower().replace(" ", "_") for c in raw.columns]
    need = ["open", "high", "low", "close"]
    miss = [c for c in need if c not in raw.columns]
    if miss:
        raise KeyError(f"Missing columns {miss} in '{path}'. Columns found: {list(raw.columns)}")
    mode = _cfg("time_mode", time_mode)
    if start is not None and "date" in raw.columns:
        floor = (pd.Timestamp(start) - pd.Timedelta(days=7)).strftime("%Y.%m.%d")
        raw = raw[raw["date"].astype(str).str.replace("-", ".") >= floor]
    if "date" in raw.columns and "time" in raw.columns and ":" in str(raw["time"].iloc[0])[:8]:
        stamp = raw["date"].astype(str).str.replace("-", ".") + " " + raw["time"].astype(str)
        idx = pd.to_datetime(stamp, format="%Y.%m.%d %H:%M:%S", errors="coerce")
        if idx.isna().all():
            idx = pd.to_datetime(stamp, format="%Y.%m.%d %H:%M", errors="coerce")
    else:
        tcol = next((c for c in ("time", "timestamp", "datetime", "date", "open_time") if c in raw.columns), None)
        if tcol is None:
            raise KeyError(f"No time column in '{path}'. Columns found: {list(raw.columns)}")
        t = raw[tcol]
        if pd.api.types.is_numeric_dtype(t):
            m = float(t.iloc[0])
            idx = pd.to_datetime(t, unit="us" if m > 1e15 else "ms" if m > 1e11 else "s")
        else:
            idx = pd.to_datetime(t)
        idx = pd.DatetimeIndex(idx).tz_localize(None) if getattr(idx.dt, "tz", None) is not None else idx
    cols = need + [c for c in ("spread",) if c in raw.columns]
    df = raw[cols].astype(float).copy()
    if "spread" not in df.columns:
        df["spread"] = np.nan
    vcol = next((c for c in ("tickvol", "tick_volume", "volume") if c in raw.columns), None)
    if vcol is not None:
        df["volume"] = raw[vcol].astype(float).to_numpy()
    df.index = pd.DatetimeIndex(idx)
    df = df[df.index.notna()]
    df.index = server_to_utc(df.index, mode)
    df.index.name = "time"
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df = df[(df[need] > 0).all(axis=1)]
    if start is not None:
        df = df[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    if verbose and len(df) and df.index[0] < pd.Timestamp("2008-06-01") and mode == "mt5_server_ny":
        print("WARNING: before ~2008 the server used a different clock: that part is not converted correctly. "
              "Set instrument.start >= 2010.")
    return df


def check_weekly_structure(df) -> dict:
    """The week must open on Sunday at 22:00 UTC (winter) or 21:00 UTC (summer). If the time conversion is wrong,
        these opens shift by one hour. Weeks whose open is delayed by holidays are ignored."""
    ix = df.index.to_series()
    gap = ix.diff()
    opens = ix[gap > pd.Timedelta(hours=24)]
    opens = opens[opens.dt.dayofweek == 6]
    exp = 22 - us_dst_mask(pd.DatetimeIndex(opens)).astype(int)
    ok = (opens.dt.hour.to_numpy() == exp) & (opens.dt.minute.to_numpy() < 30)
    bad = opens[~ok]
    return dict(weeks=int(len(opens)), ok_share=float(ok.mean()) if len(opens) else np.nan,
                bad_weeks=[str(t) for t in bad.index[:10]])


@lru_cache(maxsize=16)
def _holiday_array(y0: int, y1: int, source: str, extra: tuple, csv: str | None) -> np.ndarray:
    """Japanese bank NON-business days (excluding weekends) between y0 and y1, as datetime64[D]."""
    days = set()
    if source == "holidays":
        try:
            import holidays
        except ImportError as e:
            raise ImportError("Missing package 'holidays' (pip install -r requirements_gotobi.txt) or use holiday_source='csv' with calendar_csv.") from e
        days |= set(holidays.Japan(years=range(y0, y1 + 1)).keys())
    elif source == "csv":
        if not csv:
            raise ValueError("holiday_source='csv' requires calendar_csv")
        col = pd.read_csv(_find_csv(csv)).iloc[:, 0]
        days |= {d.date() for d in pd.to_datetime(col)}
    else:
        raise ValueError("holiday_source must be 'holidays' or 'csv'")
    for y in range(y0, y1 + 1):
        days |= {dt.date(y, 1, 1), dt.date(y, 1, 2), dt.date(y, 1, 3), dt.date(y, 12, 31)}
    days |= {pd.Timestamp(x).date() for x in extra}
    return np.array(sorted(days), dtype="datetime64[D]")


def _hol(y0, y1):
    """Cached holiday array for the years covered by the data (plus margin)."""
    return _holiday_array(int(y0), int(y1), ENGINE_DEFAULTS["holiday_source"],
                          tuple(str(x) for x in ENGINE_DEFAULTS["extra_holidays"]), ENGINE_DEFAULTS["calendar_csv"])


def is_business_day(dates) -> np.ndarray:
    """Boolean mask: Japanese bank business day."""
    d = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    return np.is_busday(d.values.astype("datetime64[D]"), holidays=_hol(d.year.min() - 1, d.year.max() + 1))


def business_days(start, end) -> pd.DatetimeIndex:
    """Japanese bank business days between start and end (JST dates at midnight)."""
    a, b = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    rng = pd.date_range(a, b, freq="D")
    return rng[is_business_day(rng)] if len(rng) else rng


def gotobi_calendar(start, end, days=None, include_month_end=None, shift_rule=None, offset_bdays=0) -> pd.DataFrame:
    """Gotobi dates (JST) between start and end. Index = date at midnight. Columns: label ('5','10',...,'EOM'),
        nominal (unshifted date), shifted (moved because it was not a business day), dow (0=Monday).
        offset_bdays != 0 shifts each date by that many business days (PLACEBO: -2, -1, +1, +2)."""
    days = tuple(_cfg("gotobi_days", days))
    eom = bool(_cfg("include_month_end", include_month_end))
    rule = _cfg("shift_rule", shift_rule)
    if rule not in ("previous", "next", "none"):
        raise ValueError("shift_rule must be 'previous', 'next' or 'none'")
    a, b = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    months = pd.period_range(a.to_period("M") - 1, b.to_period("M") + 1, freq="M")
    nom, lab = [], []
    for p in months:
        last = p.days_in_month
        for d in days:
            nom.append(dt.date(p.year, p.month, min(int(d), last))), lab.append(str(int(d)))
        if eom:
            nom.append(dt.date(p.year, p.month, last)), lab.append("EOM")
    nominal = np.array(nom, dtype="datetime64[D]")
    hol = _hol(a.year - 1, b.year + 1)
    if rule == "none":
        keep = np.is_busday(nominal, holidays=hol)
        rolled, nominal, lab = nominal[keep], nominal[keep], [x for x, k in zip(lab, keep) if k]
    else:
        rolled = np.busday_offset(nominal, 0, roll="backward" if rule == "previous" else "forward", holidays=hol)
    if offset_bdays:
        rolled = np.busday_offset(rolled, int(offset_bdays), holidays=hol)
    cal = pd.DataFrame({"date": pd.to_datetime(rolled), "label": lab, "nominal": pd.to_datetime(nominal)})
    cal["shifted"] = cal["date"] != cal["nominal"]
    cal = cal.sort_values(["date", "nominal"]).drop_duplicates("date", keep="first")
    cal = cal[(cal["date"] >= a) & (cal["date"] <= b)].set_index("date")
    cal["dow"] = cal.index.dayofweek
    return cal


def shifted_dates(dates, k) -> pd.DatetimeIndex:
    """Move each date k business days (placebo). k may be negative."""
    d = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    hol = _hol(d.year.min() - 1, d.year.max() + 1)
    out = np.busday_offset(d.values.astype("datetime64[D]"), int(k), roll="backward", holidays=hol)
    return pd.DatetimeIndex(pd.to_datetime(out))


def control_dates(start, end, exclude_neighbors=0, **cal_kw) -> pd.DatetimeIndex:
    """Business days that are NOT Gotobi (control group). exclude_neighbors=n also removes the n business days on
        each side of every Gotobi date (so the control does not mix in the effect)."""
    bd = business_days(start, end)
    g = gotobi_calendar(start, end, **cal_kw).index
    bad = set(g)
    for k in range(1, int(exclude_neighbors) + 1):
        bad |= set(shifted_dates(g, k)) | set(shifted_dates(g, -k))
    return bd[~bd.isin(bad)]


def _resolve_dates(df, dates, days, include_month_end, shift_rule, offset_bdays) -> pd.DataFrame:
    """Calendar rows to trade: the Gotobi calendar (dates=None) or a custom list of JST dates."""
    if dates is None:
        a = (df.index[0] + JST).normalize()
        b = (df.index[-1] + JST).normalize()
        return gotobi_calendar(a, b, days, include_month_end, shift_rule, offset_bdays)
    d = pd.DatetimeIndex(pd.to_datetime(dates)).normalize().unique().sort_values()
    return pd.DataFrame({"label": "custom", "nominal": d, "shifted": False, "dow": d.dayofweek}, index=d.rename("date"))


def _candidates(df, cal, entry_time, exit_time, max_delay_min, spread_scale, max_spread_pips) -> pd.DataFrame:
    """For each date: position of the entry/exit bar, spread and the reason for any discard. Single source of
        truth: used by run_gotobi_backtest, prepare and signal_table."""
    idx, n = df.index, len(df.index)
    et, xt = _hhmm(entry_time), _hhmm(exit_time)
    tol = pd.Timedelta(minutes=float(max_delay_min))
    t_in, t_out = cal.index + et - JST, cal.index + xt - JST
    i, j = idx.searchsorted(t_in, side="left"), idx.searchsorted(t_out, side="left")
    ii, jj = np.minimum(i, n - 1), np.minimum(j, n - 1)
    ok_in = (i < n) & np.asarray((idx[ii] - t_in) <= tol)
    ok_out = (j < n) & np.asarray((idx[jj] - t_out) <= tol) & (jj > ii)
    sp = df["spread"].to_numpy(float)[ii] if "spread" in df.columns else np.full(len(cal), np.nan)
    pip_feed = sp * float(ENGINE_DEFAULTS["point_size"]) / float(ENGINE_DEFAULTS["pip_size"])
    pip_axi = pip_feed * float(spread_scale)
    reason = np.where(~ok_in, "no entry bar", np.where(~ok_out, "no exit bar", "ok")).astype(object)
    lim = np.inf if max_spread_pips is None else float(max_spread_pips)
    reason = np.where((reason == "ok") & ~np.isfinite(pip_axi) & (_cfg("cost_mode", None) == "feed"), "no spread", reason)
    reason = np.where((reason == "ok") & np.isfinite(pip_axi) & (pip_axi > lim), "spread wide", reason)
    out = cal[["label", "shifted", "dow"]].copy()
    out["i"], out["j"] = np.where(ok_in, i, -1), np.where(ok_out, j, -1)
    out["t_in"], out["t_out"] = t_in, t_out
    out["entry_bar"] = np.where(ok_in, idx[ii], pd.NaT)
    out["exit_bar"] = np.where(ok_out, idx[jj], pd.NaT)
    out["spread_pips_feed"], out["spread_pips"] = pip_feed, pip_axi
    out["reason"] = reason
    return out


def _pick(df, key, value):
    """Resolve a parameter: explicit value > value stored by prepare() > ENGINE_DEFAULTS (with a consistency check)."""
    have = df.attrs.get(key)
    if value is not None and have is not None and have != value:
        raise ValueError(f"df was prepared with {key}={have} but you asked for {key}={value}: call prepare() again.")
    return value if value is not None else (have if have is not None else ENGINE_DEFAULTS[key])


def prepare(df, entry_time=None, exit_time=None, max_delay_min=None, days=None, include_month_end=None,
            shift_rule=None, spread_scale=None, max_entry_spread_pips=None):
    """Adds spread_pips (feed spread in pips) and entry_ok (True on the entry bar of each Gotobi date that has valid
        entry AND exit bars). There is no warm-up: cutting df into IS/OOS loses nothing
        (use split_df to cut without splitting a trade)."""
    et, xt = _cfg("entry_time", entry_time), _cfg("exit_time", exit_time)
    cal = _resolve_dates(df, None, days, include_month_end, shift_rule, 0)
    cand = _candidates(df, cal, et, xt, _cfg("max_delay_min", max_delay_min), _cfg("spread_scale", spread_scale),
                       None)
    d = df.copy()
    d["spread_pips"] = d["spread"] * float(ENGINE_DEFAULTS["point_size"]) / float(ENGINE_DEFAULTS["pip_size"])
    flag = np.zeros(len(d), bool)
    flag[cand.loc[cand["reason"].isin(["ok", "spread wide", "no spread"]), "i"].to_numpy(int)] = True
    d["entry_ok"] = flag
    d.attrs.update(entry_time=et, exit_time=xt)
    return d


def split_df(df, oos_start):
    """Cut df into (IS, OOS) at the JST midnight of oos_start. No position is open at that instant."""
    cut = pd.Timestamp(oos_start) - JST
    n = int(df.index.searchsorted(cut, side="left"))
    return df.iloc[:n], df.iloc[n:]


def _rollovers(t0, t1) -> int:
    """Count the 17:00 New York closes (22:00 UTC winter / 21:00 UTC summer) inside (t0, t1]."""
    n = 0
    for k in range(-1, (t1.normalize() - t0.normalize()).days + 2):
        d = t0.normalize() + pd.Timedelta(days=k)
        r = d + pd.Timedelta(hours=21 if bool(us_dst_mask(pd.DatetimeIndex([d]))[0]) else 22)
        if t0 < r <= t1:
            n += 1
    return n


TRADE_COLS = ["entry_date", "entry_time", "exit_time", "entry_price", "exit_price", "type", "pnl", "win", "bars",
              "i_ent", "i_sal", "label", "shifted", "dow", "spread_pips", "cost_bps", "pnl_gross_bps", "pnl_bps",
              "mae_bps", "mfe_bps", "rollovers", "stopped", "pnl_frac"]


def run_gotobi_backtest(df, dates=None, entry_time=None, exit_time=None, gotobi_days=None, include_month_end=None,
                        shift_rule=None, offset_bdays=0, cost_mode=None, cost_bps_per_side=None, spread_scale=None,
                        commission_bps_per_side=None, slippage_bps_per_side=None, max_entry_spread_pips=None,
                        stop_bps=None, stop_slippage_bps=None, max_delay_min=None, financing_bps_per_night=None,
                        size_fraction=None):
    """dates: None = Gotobi calendar; or a list of JST dates (placebo, control, random...).
        max_entry_spread_pips: None = ENGINE_DEFAULTS value; float('inf') = no filter. stop_bps: 0 = no stop.
        The (opt-in) stop fills at min(level, bar open) minus stop_slippage_bps: an M5 approximation.
        Costs: see cost_mode in the module docstring. Long only; entry at ask, exit at bid."""
    et, xt = _pick(df, "entry_time", entry_time), _pick(df, "exit_time", exit_time)
    mode = _cfg("cost_mode", cost_mode)
    if mode not in ("feed", "flat_pips", "fixed"):
        raise ValueError("cost_mode must be 'feed', 'flat_pips' or 'fixed'")
    scale = float(_cfg("spread_scale", spread_scale))
    side_fix = float(_cfg("cost_bps_per_side", cost_bps_per_side)) / 1e4
    extra = (float(_cfg("commission_bps_per_side", commission_bps_per_side))
             + float(_cfg("slippage_bps_per_side", slippage_bps_per_side))) / 1e4
    cap = _cfg("max_entry_spread_pips", max_entry_spread_pips)
    stop = float(_cfg("stop_bps", stop_bps)) / 1e4
    stop_slip = float(_cfg("stop_slippage_bps", stop_slippage_bps)) / 1e4
    fin_bps = float(_cfg("financing_bps_per_night", financing_bps_per_night))
    frac = float(_cfg("size_fraction", size_fraction))
    ptsz = float(ENGINE_DEFAULTS["point_size"])
    flat = float(ENGINE_DEFAULTS["flat_spread_pips"]) * float(ENGINE_DEFAULTS["pip_size"])
    if mode == "feed" and ("spread" not in df.columns or df["spread"].isna().all()):
        raise ValueError("cost_mode='feed' needs the spread column; use cost_mode='fixed'.")

    cal = _resolve_dates(df, dates, gotobi_days, include_month_end, shift_rule, offset_bdays)
    cand = _candidates(df, cal, et, xt, _cfg("max_delay_min", max_delay_min), scale, cap)
    idx = df.index
    o, h, l = (df[c].to_numpy(float) for c in ("open", "high", "low"))
    sp = df["spread"].to_numpy(float)
    rows = []
    for date, r in cand[cand["reason"] == "ok"].iterrows():
        i, j = int(r["i"]), int(r["j"])
        entry = o[i] + (sp[i] * ptsz * scale if mode == "feed" else flat if mode == "flat_pips" else 0.0)
        entry *= (1 + extra) if mode != "fixed" else (1 + side_fix + extra)
        stopped, j_eff, fill = False, j, o[j]
        if stop > 0:
            hit = np.flatnonzero(l[i:j] <= entry * (1 - stop))
            if len(hit):
                k = int(hit[0])
                fill = min(entry * (1 - stop), o[i + k]) * (1 - stop_slip)
                stopped, j_eff = True, i + k + 1
        exit_ = fill * ((1 - extra) if mode != "fixed" else (1 - side_fix - extra))
        nights = _rollovers(idx[i], idx[j_eff])
        pnl = (exit_ / entry - 1) * 100.0 - nights * fin_bps / 100.0
        gross = (fill / o[i] - 1) * 1e4
        rows.append(dict(entry_date=date, entry_time=idx[i], exit_time=idx[j_eff], entry_price=entry,
                         exit_price=exit_, type="long", pnl=pnl, win=pnl > 0, bars=j_eff - i, i_ent=i, i_sal=j_eff,
                         label=r["label"], shifted=bool(r["shifted"]), dow=int(r["dow"]),
                         spread_pips=r["spread_pips"], cost_bps=gross - (exit_ / entry - 1) * 1e4,
                         pnl_gross_bps=gross, pnl_bps=pnl * 100.0,
                         mae_bps=(l[i:j_eff].min() / entry - 1) * 1e4, mfe_bps=(h[i:j_eff].max() / entry - 1) * 1e4,
                         rollovers=nights, stopped=stopped, pnl_frac=pnl * frac))
    return pd.DataFrame(rows, columns=TRADE_COLS)


def signal_table(df, entry_time=None, exit_time=None, max_delay_min=None, days=None, include_month_end=None,
                 shift_rule=None, spread_scale=None, max_entry_spread_pips=None) -> pd.DataFrame:
    """One row per Gotobi date (index = JST date): what the engine decides and with which data. Reference for the
        reconciliation notebook 04 (the EA log has the same shape: date, spread, decision, reason).
        Columns: label, shifted, entry_utc/exit_utc, entry_server/exit_server (server time, for the EA),
        spread_pips_feed, spread_pips (Axi-equivalent), take (bool), reason, us_dst, season."""
    et, xt = _pick(df, "entry_time", entry_time), _pick(df, "exit_time", exit_time)
    cal = _resolve_dates(df, None, days, include_month_end, shift_rule, 0)
    cap = _cfg("max_entry_spread_pips", max_entry_spread_pips)
    c = _candidates(df, cal, et, xt, _cfg("max_delay_min", max_delay_min), _cfg("spread_scale", spread_scale), cap)
    out = c[["label", "shifted", "dow", "spread_pips_feed", "spread_pips", "reason"]].copy()
    out["entry_utc"], out["exit_utc"] = c["t_in"], c["t_out"]
    out["entry_server"], out["exit_server"] = utc_to_server(c["t_in"]), utc_to_server(c["t_out"])
    out["take"] = c["reason"] == "ok"
    out["us_dst"] = us_dst_mask(c["t_in"])
    out["season"] = np.where(out["us_dst"], "summer", "winter")
    return out


def export_calendar(path, start, end, **cal_kw) -> Path:
    """CSV (';' separated) with the calendar so the EA does not compute holidays: one row per Gotobi date with the
        entry and exit times in UTC and in server time."""
    cal = gotobi_calendar(start, end, **cal_kw)
    et, xt = _hhmm(ENGINE_DEFAULTS["entry_time"]), _hhmm(ENGINE_DEFAULTS["exit_time"])
    t_in, t_out = cal.index + et - JST, cal.index + xt - JST
    out = pd.DataFrame({"date_jst": cal.index.strftime("%Y-%m-%d"), "label": cal["label"].to_numpy(),
                        "shifted": cal["shifted"].astype(int).to_numpy(),
                        "entry_utc": t_in.strftime("%Y-%m-%d %H:%M"), "exit_utc": t_out.strftime("%Y-%m-%d %H:%M"),
                        "entry_server": utc_to_server(t_in).strftime("%Y-%m-%d %H:%M"),
                        "exit_server": utc_to_server(t_out).strftime("%Y-%m-%d %H:%M")})
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(p, sep=";", index=False)
    return p


def price_grid(df, dates, times, field="open") -> pd.DataFrame:
    """Matrix dates x JST times with the `field` of the exact M5 bar (NaN if missing). times: ['07:30', '07:35', ...]."""
    d = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    tod = pd.to_timedelta([_hhmm(t) for t in times])
    ts = (d.values[:, None] + tod.values[None, :] - np.timedelta64(9, "h")).ravel()
    pos = df.index.get_indexer(pd.DatetimeIndex(ts))
    arr = df[field].to_numpy(float)
    vals = np.where(pos >= 0, arr[np.maximum(pos, 0)], np.nan).reshape(len(d), len(tod))
    return pd.DataFrame(vals, index=d, columns=list(times))


def intraday_profile(df, dates, start_time="06:00", end_time="11:00", ref_time="07:30") -> pd.DataFrame:
    """Mean intraday profile (bps) of the given dates: cumulative return from ref_time and return per M5 step."""
    a, b = _hhmm(start_time), _hhmm(end_time)
    n = int((b - a) / M5) + 1
    times = [f"{int((a + k * M5).total_seconds() // 3600):02d}:{int((a + k * M5).total_seconds() % 3600 // 60):02d}"
             for k in range(n)]
    g = price_grid(df, dates, times)
    ref = g[ref_time]
    cum = (g.div(ref, axis=0) - 1) * 1e4
    step = (g.diff(axis=1).div(g.shift(1, axis=1))) * 1e4
    nn = cum.notna().sum()
    return pd.DataFrame({"n": nn, "mean_cum_bps": cum.mean(), "se_cum_bps": cum.std() / np.sqrt(nn.clip(lower=1)),
                         "mean_step_bps": step.mean(), "se_step_bps": step.std() / np.sqrt(step.notna().sum().clip(lower=1))})


def _account_per_base(price, ccy):
    """Account-currency value of one unit of base currency (JPY account: the price; USD account: 1)."""
    return float(price) if ccy == "JPY" else 1.0


def lot_size(capital, price, target_fraction=None, contract_size=None, min_lot=None, lot_step=None, account_ccy=None):
    """Lots that can be opened without exceeding target_fraction of capital (notional). 0.0 if below the minimum lot.
        In a USD account the notional is lots*contract_size (USDJPY: base is USD); in a JPY account it is multiplied by price."""
    target_fraction = _cfg("size_fraction", target_fraction)
    contract_size = _cfg("contract_size", contract_size)
    min_lot, lot_step = _cfg("min_lot", min_lot), _cfg("lot_step", lot_step)
    fx = _account_per_base(price, _cfg("account_ccy", account_ccy))
    if capital <= 0 or price <= 0:
        return 0.0
    raw = capital * target_fraction / (contract_size * fx)
    lots = round(np.floor(raw / lot_step + 1e-9) * lot_step, 8)
    return float(lots) if lots >= min_lot - 1e-12 else 0.0


def min_capital_for_target(price, target_fraction=None, contract_size=None, min_lot=None, account_ccy=None):
    """Minimum capital so that the minimum lot does not weigh more than target_fraction (notional)."""
    target_fraction = _cfg("size_fraction", target_fraction)
    contract_size, min_lot = _cfg("contract_size", contract_size), _cfg("min_lot", min_lot)
    return float(min_lot * contract_size * _account_per_base(price, _cfg("account_ccy", account_ccy)) / target_fraction)


def cfd_trade_sizes(trades, capital, target_fraction=None, contract_size=None, min_lot=None, lot_step=None,
                    compounding=True, account_ccy=None):
    """One row per trade: lots, notional (account currency) and effective fraction of the capital at entry
        (size_fraction, ready to use as `sizing`). A trade with 0 lots is not taken (return 0)."""
    contract_size, ccy = _cfg("contract_size", contract_size), _cfg("account_ccy", account_ccy)
    n = len(trades)
    lots, notional, frac_eff, equity_after = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    equity = float(capital)
    for k, r in enumerate(trades.itertuples()):
        base = equity if compounding else float(capital)
        lt = lot_size(base, r.entry_price, target_fraction, contract_size, min_lot, lot_step, ccy)
        nom = lt * contract_size * _account_per_base(r.entry_price, ccy)
        f = nom / equity if equity > 0 else 0.0
        lots[k], notional[k], frac_eff[k] = lt, nom, f
        equity *= 1.0 + f * r.pnl / 100.0
        equity_after[k] = equity
    return pd.DataFrame(dict(entry_time=trades["entry_time"].to_numpy(), lots=lots, notional=notional,
                             size_fraction=frac_eff, taken=lots > 0, equity_after=equity_after), index=trades.index)


def _size(sizing):
    """Scalar size from a sizing spec."""
    if isinstance(sizing, (int, float)):
        return float(sizing)
    if sizing == "capital":
        return 1.0
    if sizing == "fraction":
        return float(ENGINE_DEFAULTS["size_fraction"])
    raise ValueError("sizing must be 'capital', 'fraction', a number, or an array with one fraction per trade")


def _sizes(sizing, n):
    """One size per trade from a sizing spec."""
    if isinstance(sizing, (np.ndarray, pd.Series, list, tuple)):
        arr = np.asarray(sizing, float)
        if len(arr) != n:
            raise ValueError(f"sizing has {len(arr)} elements but there are {n} trades")
        return arr
    return np.full(n, _size(sizing))


def trade_mtm_paths(df, trades, sizing="fraction"):
    """One return series per trade (5-minute steps, already scaled to size). One per row of trades."""
    sizes, c, out = _sizes(sizing, len(trades)), df["close"].to_numpy(float), []
    for s, r in zip(sizes, trades.itertuples()):
        i, j = int(r.i_ent), int(r.i_sal)
        fin = (r.exit_price / r.entry_price - 1.0) - r.pnl / 100.0
        p = np.empty(j - i + 1)
        p[0] = c[i] / r.entry_price - 1.0
        p[1:j - i] = c[i + 1:j] / c[i:j - 1] - 1.0
        p[j - i] = (r.exit_price - fin * r.entry_price) / c[j - 1] - 1.0
        out.append(s * p)
    return out


def _step_log_returns(price_df, trades, sizing):
    """Per-bar log returns of the whole strategy (0 on bars without a position)."""
    lr = np.zeros(len(price_df))
    if len(trades):
        for (i, j), p in zip(trades[["i_ent", "i_sal"]].to_numpy(int), trade_mtm_paths(price_df, trades, sizing)):
            lg, m = np.log1p(p), j - i
            lr[i:j] += lg[:m]
            lr[j - 1] += lg[m]
    return pd.Series(lr, index=price_df.index)


def bar_returns(price_df, trades, sizing="fraction"):
    """MTM return per M5 bar (0 on bars without a position). Basis of the bar-by-bar drawdown."""
    return np.expm1(_step_log_returns(price_df, trades, sizing))


hourly_returns = bar_returns


def daily_returns(price_df, trades, sizing="fraction"):
    """MTM return per JST business day (0 on days without a trade). Each trade falls inside a single JST day."""
    lr = _step_log_returns(price_df, trades, sizing)
    nz = lr[lr != 0]
    s = np.expm1(nz.groupby((nz.index + JST).normalize()).sum())
    if len(price_df) == 0:
        return s
    full = pd.bdate_range((price_df.index[0] + JST).normalize(), (price_df.index[-1] + JST).normalize())
    return s.reindex(full.union(s.index)).fillna(0.0)


def worst_returns(price_df, trades, sizing="fraction"):
    """Worst return of each M5 bar INSIDE the bar (long position valued at the bar `low`), scaled to size.
        Each step is measured against the previous close (the first bar, against the entry price with cost).
        0 on bars without a position. Always <= bar_returns of that bar (the final exit step is not included)."""
    sizes = _sizes(sizing, len(trades))
    lo, c = price_df["low"].to_numpy(float), price_df["close"].to_numpy(float)
    out = np.zeros(len(price_df))
    for s, r in zip(sizes, trades.itertuples()):
        i, j = int(r.i_ent), int(r.i_sal)
        w = np.empty(j - i)
        w[0] = lo[i] / r.entry_price - 1.0
        if j - i > 1:
            w[1:] = lo[i + 1:j] / c[i:j - 1] - 1.0
        out[i:j] = s * w
    return pd.Series(out, index=price_df.index)


hourly_worst_returns = worst_returns


def hard_limit_report_intrabar(price_df, trades, hard_limit, sizing="fraction"):
    """Maximum equity drawdown against the hard limit, also using the intrabar minimum (long: low of each M5 bar).
        Returns max_dd (intrabar), max_dd_close (closes only), passed, headroom and trough_date."""
    hard_limit = float(hard_limit)
    hr = bar_returns(price_df, trades, sizing).fillna(0.0)
    wr = worst_returns(price_df, trades, sizing)
    keep = ((hr != 0) | (wr != 0)).to_numpy()
    if not keep.any():
        return dict(hard_limit=hard_limit, max_dd=0.0, max_dd_close=0.0, passed=True, headroom=hard_limit,
                    trough_date=None)
    hr, wr = hr[keep], wr[keep]
    eq = (1.0 + hr).cumprod()
    prev_eq = eq.shift(1).fillna(1.0)
    prev_peak = np.maximum(eq.cummax().shift(1).fillna(1.0), 1.0)
    dd_close = eq / np.maximum(eq.cummax(), 1.0) - 1.0
    dd_low = prev_eq * (1.0 + wr) / prev_peak - 1.0
    dd = np.minimum(dd_close, dd_low)
    mdd = float(dd.min())
    return dict(hard_limit=hard_limit, max_dd=mdd, max_dd_close=float(dd_close.min()),
                passed=bool(mdd >= -hard_limit), headroom=float(hard_limit + mdd), trough_date=dd.idxmin())


ANNUAL_COLS = ["year", "ret", "mdd", "n_trades", "partial", "breach"]


def annual_returns(step_returns, trades=None, hard_limit=None):
    """Annual table from step returns (bar_returns or daily_returns). Columns: year, ret, mdd (maximum drawdown within
        the year, starting from capital at 1 January), n_trades (by JST entry year), partial (year with fewer than 358
        days of data) and breach (mdd worse than -hard_limit; False if hard_limit is None)."""
    r = pd.Series(step_returns, dtype=float)
    r = r[~r.index.duplicated(keep="first")].sort_index().fillna(0.0)
    if len(r) == 0:
        return pd.DataFrame(columns=ANNUAL_COLS)
    if trades is not None and len(trades):
        key = "entry_date" if "entry_date" in trades.columns else "entry_time"
        counts = pd.to_datetime(trades[key]).dt.year.value_counts()
    else:
        counts = pd.Series(dtype=int)
    rows = []
    for year, g in r.groupby(r.index.year):
        eq = (1.0 + g).cumprod()
        dd = eq / np.maximum(eq.cummax(), 1.0) - 1.0
        span = (g.index.max().normalize() - g.index.min().normalize()).days + 1
        mdd = float(dd.min())
        rows.append(dict(year=int(year), ret=float(eq.iloc[-1] - 1.0), mdd=mdd, n_trades=int(counts.get(year, 0)),
                         partial=bool(span < 358), breach=bool(hard_limit is not None and mdd < -float(hard_limit))))
    return pd.DataFrame(rows, columns=ANNUAL_COLS)


def hard_limit_report(step_returns, hard_limit):
    """Maximum equity drawdown (starting at 1.0) against the hard limit, using closes only (for the intrabar minimum use
        hard_limit_report_intrabar). Returns max_dd (negative), passed, headroom, peak and trough dates, how many steps
        were below the limit and the first date it was crossed."""
    hard_limit = float(hard_limit)
    r = pd.Series(step_returns, dtype=float).fillna(0.0)
    if len(r) == 0:
        return dict(hard_limit=hard_limit, max_dd=0.0, passed=True, headroom=hard_limit, peak_date=None,
                    trough_date=None, steps_in_breach=0, first_breach=None)
    eq = (1.0 + r).cumprod()
    peak = np.maximum(eq.cummax(), 1.0)
    dd = eq / peak - 1.0
    trough = dd.idxmin()
    pre = eq.loc[:trough]
    peak_date = pre.idxmax() if pre.max() >= 1.0 else r.index[0]
    breached = dd < -hard_limit
    return dict(hard_limit=hard_limit, max_dd=float(dd.min()), passed=bool(dd.min() >= -hard_limit),
                headroom=float(hard_limit + dd.min()), peak_date=peak_date, trough_date=trough,
                steps_in_breach=int(breached.sum()),
                first_breach=(dd.index[breached.to_numpy()][0] if breached.any() else None))


def max_fraction_for_limit(price_df, trades, hard_limit, hi=50.0, tol=1e-3, intrabar=True):
    """Largest fixed fraction of capital (notional) per trade whose historical drawdown respects the hard limit.
        intrabar=True (default) uses the minimum of each M5 bar; False, daily closes only."""
    def mdd_at(s):
        if intrabar:
            return hard_limit_report_intrabar(price_df, trades, hard_limit, float(s))["max_dd"]
        return hard_limit_report(daily_returns(price_df, trades, float(s)), hard_limit)["max_dd"]

    if len(trades) == 0 or mdd_at(hi) >= -float(hard_limit):
        return float(hi)
    lo, up = 0.0, float(hi)
    while up - lo > tol:
        mid = (lo + up) / 2.0
        if mdd_at(mid) >= -float(hard_limit):
            lo = mid
        else:
            up = mid
    return float(lo)


def walk_forward_fixed(df, rules, is_years=3, sizing="fraction"):
    """Fixed rules (no refitting): for each year Y with `is_years` full prior years, compare the annualised IS return with
        the return of year Y (OOS). A partial first year is not used as IS. Returns year, ret_is_annual, ret_oos, mdd_oos, n_oos."""
    trades = run_gotobi_backtest(df, **rules)
    daily = daily_returns(df, trades, sizing)
    years = sorted(set(daily.index.year))
    ty = pd.to_datetime(trades["entry_date"]).dt.year if len(trades) else pd.Series(dtype=int)
    first_partial = daily.index[0] > pd.Timestamp(years[0], 1, 10)      # the first year only counts as IS if it is complete
    full_years = years[1:] if first_partial else years
    rows = []
    for y in years:
        is_ys = list(range(y - is_years, y))
        if not all(k in full_years for k in is_ys):
            continue
        tot_is = (1 + daily[daily.index.year.isin(is_ys)]).prod()
        eq = (1 + daily[daily.index.year == y]).cumprod()
        rows.append(dict(year=y, ret_is_annual=tot_is ** (1 / is_years) - 1, ret_oos=float(eq.iloc[-1] - 1),
                         mdd_oos=float((eq / eq.cummax() - 1).min()), n_oos=int((ty == y).sum())))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ edge statistics
def trade_stats(trades, col="pnl_bps") -> dict:
    """n, mean/median (bps), t and one-sided p (normal approximation; long direction fixed a priori), PF, win rate."""
    x = pd.Series(trades[col], dtype=float).dropna() if len(trades) else pd.Series(dtype=float)
    n = len(x)
    if n < 2:
        return dict(n=n, mean_bps=np.nan, median_bps=np.nan, std_bps=np.nan, t=np.nan, p_one=np.nan, pf=np.nan,
                    win_rate=np.nan, sum_bps=float(x.sum()) if n else 0.0)
    sd = float(x.std(ddof=1))
    t = float(x.mean() / (sd / np.sqrt(n))) if sd > 0 else np.nan
    gl = float(-x[x < 0].sum())
    return dict(n=n, mean_bps=float(x.mean()), median_bps=float(x.median()), std_bps=sd, t=t,
                p_one=float(1 - NormalDist().cdf(t)) if np.isfinite(t) else np.nan,
                pf=float(x[x > 0].sum() / gl) if gl > 0 else np.inf, win_rate=float((x > 0).mean()),
                sum_bps=float(x.sum()))


def period_stats(trades, periods, col="pnl_bps") -> pd.DataFrame:
    """periods: {'2010-17': (2010, 2017), ...} (JST entry years, inclusive). One row per period."""
    yr = pd.to_datetime(trades["entry_date"]).dt.year
    rows = {k: trade_stats(trades[(yr >= a) & (yr <= b)], col) for k, (a, b) in periods.items()}
    return pd.DataFrame(rows).T


def hypothesis_threshold(n_hypotheses, alpha=0.05, one_sided=True) -> float:
    """Critical t (Bonferroni, normal approximation) after n_hypotheses tests. one_sided=True: the edge is long a priori."""
    k = max(int(n_hypotheses), 1)
    return float(NormalDist().inv_cdf(1 - alpha / k / (1 if one_sided else 2)))


def placebo_table(df, offsets=(-2, -1, 1, 2), **bt_kw) -> pd.DataFrame:
    """Backtest with the same calendar shifted k business days (0 = real). Same window and same costs.
        Returns one row per offset with gross and net stats."""
    rows = []
    for k in (0, *offsets):
        tr = run_gotobi_backtest(df, offset_bdays=k, **bt_kw)
        g, n = trade_stats(tr, "pnl_gross_bps"), trade_stats(tr, "pnl_bps")
        rows.append(dict(offset=k, n=g["n"], gross_bps=g["mean_bps"], gross_t=g["t"], net_bps=n["mean_bps"],
                         net_t=n["t"], pf_net=n["pf"]))
    return pd.DataFrame(rows).set_index("offset")


def window_returns_bps(df, dates, entry_time=None, exit_time=None) -> pd.Series:
    """GROSS open->open return (bps) of the window for each JST date (NaN if a bar is missing). No costs."""
    et, xt = _pick(df, "entry_time", entry_time), _pick(df, "exit_time", exit_time)
    g = price_grid(df, dates, [et, xt])
    return ((g[xt] / g[et] - 1) * 1e4).dropna()


def random_date_test(df, n_draws=5000, seed=0, exclude_neighbors=0, **cal_kw) -> dict:
    """Permutation test: mean gross window return on Gotobi dates vs that of n random dates drawn from the NON-Gotobi
        business days (optionally without the `exclude_neighbors` neighbouring business days; resampled with replacement
        if the control is too small). One-sided p = P(simulated mean >= real)."""
    a, b = (df.index[0] + JST).normalize(), (df.index[-1] + JST).normalize()
    gd = gotobi_calendar(a, b, **cal_kw).index
    real = window_returns_bps(df, gd)
    ctrl = window_returns_bps(df, control_dates(a, b, exclude_neighbors=exclude_neighbors, **cal_kw)).to_numpy()
    rng = np.random.default_rng(seed)
    n = len(real)
    repl = len(ctrl) < n          # con muchos vecinos excluidos puede no haber control suficiente: se remuestrea con reemplazo
    sims = np.array([rng.choice(ctrl, n, replace=repl).mean() for _ in range(int(n_draws))])
    return dict(n=n, n_control=len(ctrl), real_mean_bps=float(real.mean()), control_mean_bps=float(ctrl.mean()),
                sim_mean_bps=float(sims.mean()), sim_sd_bps=float(sims.std()),
                z=float((real.mean() - sims.mean()) / sims.std()),
                p_one=float((1 + (sims >= real.mean()).sum()) / (n_draws + 1)), sims=sims)


def spread_summary(sig, by="season") -> pd.DataFrame:
    """Feed spread summary (pips) from signal_table(df): by = 'season' | 'year' | 'dow' | 'label'."""
    d = sig.copy()
    d["year"] = d.index.year
    d = d[d["spread_pips_feed"].notna()]
    g = d.groupby(by)["spread_pips_feed"]
    return pd.DataFrame(dict(n=g.size(), mean=g.mean(), p50=g.median(), p90=g.quantile(0.9), max=g.max()))


def validate(df, trades, expected_per_year=(66, 74)) -> dict:
    """Engine quality gate: everything must be True before interpreting results."""
    wk = check_weekly_structure(df)
    yr = pd.to_datetime(trades["entry_date"]).dt.year
    full = yr.value_counts().sort_index().iloc[1:-1]
    p = trade_mtm_paths(df, trades, 1.0)
    err = max((abs(np.prod(1 + x) - 1 - r.pnl / 100) for x, r in zip(p, trades.itertuples())), default=0.0)
    checks = dict(
        weekly_structure=bool(wk["ok_share"] >= 0.99),
        no_rollover=bool((trades["rollovers"] == 0).all()),
        constant_window=bool(trades["bars"].nunique() == 1),
        no_overlap=bool((trades["exit_time"].to_numpy()[:-1] < trades["entry_time"].to_numpy()[1:]).all()),
        mtm_reconciles=bool(err < 1e-9),
        trades_per_year=bool(full.between(*expected_per_year).all()),
        entry_is_2230_utc=bool((pd.DatetimeIndex(trades["entry_time"]).strftime("%H:%M") == "22:30").all()),
    )
    checks["all_ok"] = all(checks.values())
    return checks