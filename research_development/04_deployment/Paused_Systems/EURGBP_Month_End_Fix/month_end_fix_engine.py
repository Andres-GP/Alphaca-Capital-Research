"""
month_end_fix_engine.py  ·  02_strategy_development/Month_End_Fix/month_end_fix_engine.py

Engine for the FX month-end fix edge (1 h candles in UTC; the rules are expressed in London LOCAL time).
Same API shape as monday_effect_engine so notebooks 01/02/03 follow the same pattern:

    load_data / prepare / run_fix_backtest / daily_returns / trade_mtm_paths /
    walk_forward_fixed / set_engine_defaults / ENGINE_DEFAULTS

Input data (load_data) accepts THREE CSV formats:
    1. Hourly CSV in UTC with a 'time' column (or open_time / timestamp / datetime / date).
    2. Any UTC CSV with candles shorter than 1 h (M1, M5, M15...): aggregated to 1 h candles (resample_h1=True).
    3. RAW MetaTrader 5 export (headers <DATE> <TIME> <OPEN> ... <SPREAD>, tab-separated, SERVER time).
       The server timezone must be given with `server_tz`:
           'ny_close'            -> server is GMT+2 / GMT+3 with the US DST (the FX day closes at 17:00 NY = 00:00 server)
           'Europe/Athens', etc. -> any IANA timezone
       Verify the timezone with weekly_boundaries_check(df) before trusting the 12:00 / 16:00 windows.
       If the export has <SPREAD>, it is kept in the `spread_pts` column (hourly mean, in broker points).

CFD and risk extensions (inherited from the Monday Effect engine, now with short support):

    apply_cfd_preset / CFD_PRESETS            symbol lot and swap specs (Axi MT5)
    lot_size / min_capital_for_target         real position size in lots and minimum capital for the minimum lot
    cfd_trade_sizes                           effective fraction per trade (rounded lots or fixed `lots`)
    hourly_returns / hourly_worst_returns     MTM return per 1 h candle and its INTRABAR worst case
    hard_limit_report / _intrabar             max drawdown check against the hard limit
    annual_returns / max_fraction_for_limit   yearly table and largest fraction that respects the hard limit

Screening statistics (everything lives here so the notebooks read like the threshold table):

    window_table                              gross return of ALL contiguous windows of `hold` candles
    permutation_test                          rule mean against draws of random windows
    tstat / profit_factor / drop_best /       t of the mean trade, PF, mean without the best X %, % of positive years
    years_positive
    gate / screen_verdict                     one gate = value vs threshold; PASA / CASI / STOP
    daily_trade_pnl / return_correlation      daily return correlation with another edge's trades CSV
    weekly_boundaries_check                   timezone check (last Friday candle / first Sunday candle)

Rule (v1, FROZEN before seeing results):
  - Calendar: LAST BUSINESS DAY (Monday to Friday) of each month, in London local date. No data in between:
    it is a calendar rule, not a price rule, so there is no signal and no lookahead risk.
  - Entry: OPEN of the `entry_hour` candle (12:00 London). Exit: OPEN of the `exit_hour` candle (16:00 London,
    the WM/Reuters fix hour), `exit_hour - entry_hour` candles later. No stop, no target.
  - Direction: `side` ('short' in v1: sell EURGBP, declared before seeing data). The opposite direction is not tested.
  - Costs (BID prices): a trade pays ONE round-trip spread. cost_bps_per_side is half the spread per side.
    Long: entry = open*(1+c), exit = open*(1-c). Short: entry = open*(1-c), exit = open*(1+c).
    Intraday: it does not cross the rollover (rollover_hour_utc), so swap is 0 nights (checked in `nights`).
  - Sweeping windows, days or parameters is forbidden: this engine deliberately exposes no grid.

Rule (v2, conditional direction, FROZEN before running; only used by the v2 variant):
  - Same days, same window, same costs as v1. The only change is the direction of each trade, set by
    relative_equity_signal(): R = (GER40 return) - (UK100 return), from the OPEN of the entry_hour bar on the last
    business day of the PREVIOUS month to the OPEN of the entry_hour bar on the fix day (both known at entry).
    R > 0 -> short EURGBP, R < 0 -> long EURGBP, R == 0 or missing index data -> no trade. No threshold, no parameters.
  - Whether the signal adds anything is judged by sign_permutation_test(). The opposite mapping is NOT tested.

Conventions:
  - trades['pnl'] is in % at 100 % of capital (same as utils.compute_metrics). net_bps = pnl * 100.
  - trades['gross_bps'] = return in the trade direction, before costs.
  - trades['pnl_frac'] = pnl * size_fraction (the real size of the robot).
  - Value of 1 unit of capital during the trade: long V = P/entry; short V = 2 - P/entry. With this, the MTM
    telescopes exactly to the trade pnl in both directions.
  - `sizing` accepts 'capital', 'fraction', a number, or an array/Series with one fraction per trade
    (the output of cfd_trade_sizes).
  - Column names i_ent / i_sal (entry / exit bar position) are kept for compatibility with the notebooks.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
H1 = pd.Timedelta(hours=1)
LONDON = "Europe/London"

ENGINE_DEFAULTS = dict(
    data_source="csv_hourly",
    csv_path="../../data/axi/eurgbp_h1_utc.csv",
    server_tz=None,            # raw MT5 export only: 'ny_close' or an IANA zone (None = the CSV is already in UTC)
    resample_h1=True,          # if the CSV has candles shorter than 1 h (M1/M5/M15...), aggregate to 1 h UTC candles
    side="short",              # 'short' | 'long'
    entry_hour=12,             # London LOCAL hour
    exit_hour=16,              # London LOCAL hour (the 16:00 fix)
    tz=LONDON,
    cost_bps_per_side=0.5,     # half the spread per side (spread ~1 bp round trip)
    financing_bps_per_night=0.0,
    rollover_hour_utc=22,      # only counts if financing_bps_per_night > 0
    size_fraction=1.0,         # notional / capital (1.0 = 1x)
    contract_size=100_000.0,   # 1 lot = 100,000 EUR (base currency)
    min_lot=0.01,
    lot_step=0.01,
    quote_to_account=1.30,     # GBP -> USD: the price is quoted in GBP, the account is in USD
)

CFD_PRESETS = {
    "axi_eurgbp": dict(contract_size=100_000.0, min_lot=0.01, lot_step=0.01,
                       financing_bps_per_night=0.0, rollover_hour_utc=22),
}


def set_engine_defaults(**kw):
    for k, v in kw.items():
        if k not in ENGINE_DEFAULTS:
            raise KeyError(f"'{k}' is not a valid engine_default. Valid ones: {sorted(ENGINE_DEFAULTS)}")
        ENGINE_DEFAULTS[k] = v


def apply_cfd_preset(name, cost_bps_per_side, quote_to_account=None):
    """Load minimum lot, lot step, contract size and swap of the symbol. The spread per side is passed by hand."""
    if name not in CFD_PRESETS:
        raise KeyError(f"Preset '{name}' does not exist. Valid ones: {sorted(CFD_PRESETS)}")
    extra = {} if quote_to_account is None else dict(quote_to_account=float(quote_to_account))
    set_engine_defaults(**CFD_PRESETS[name], cost_bps_per_side=float(cost_bps_per_side), **extra)
    return {k: ENGINE_DEFAULTS[k] for k in (*CFD_PRESETS[name], "cost_bps_per_side", "quote_to_account")}


def _cfg(name, value):
    return ENGINE_DEFAULTS[name] if value is None else value


def _sign(side) -> float:
    if side not in ("long", "short"):
        raise ValueError("side must be 'long' or 'short'")
    return 1.0 if side == "long" else -1.0


# ------------------------------------------------------------------ data
def _find_csv(csv_path) -> Path:
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
    raise FileNotFoundError(f"Could not find '{csv_path}'. Tried from cwd={cwd} and from {_HERE}.")


def _read_csv_any_sep(path: Path) -> pd.DataFrame:
    """Read the CSV detecting the encoding (UTF-8 / UTF-16) and the separator (comma, tab, semicolon) from the
    first line. MetaTrader writes tab-separated files. Uses the pandas C engine (fast with millions of rows)."""
    with open(path, "rb") as f:
        bom = f.read(2)
    enc = "utf-16" if bom in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    with open(path, "r", encoding=enc, errors="replace") as f:
        head = f.readline()
    sep = max(("\t", ";", ","), key=head.count)
    return pd.read_csv(path, sep=sep, encoding=enc)


def _server_to_utc(ts: pd.DatetimeIndex, server_tz: str):
    """MT5 server time (naive) -> UTC. 'ny_close' = New York + 7 h (the FX day closes at 17:00 NY = 00:00 server,
    i.e. GMT+2 in winter and GMT+3 in summer with the US DST). Any other string is taken as an IANA timezone.
    Ambiguous or nonexistent hours (DST changeover, market closed) are dropped.
    Returns (tz-aware UTC index, mask of kept rows)."""
    if server_tz == "ny_close":
        loc = (ts - pd.Timedelta(hours=7)).tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
    else:
        loc = ts.tz_localize(server_tz, ambiguous="NaT", nonexistent="NaT")
    keep = np.asarray(~loc.isna())
    return loc[keep].tz_convert("UTC"), keep


def _to_h1(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate candles shorter than 1 h into 1 h UTC candles (label = start of the hour; open=first, close=last)."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "spread_pts" in df.columns:
        agg["spread_pts"] = "mean"
    out = df.resample("1h").agg(agg)
    return out.dropna(subset=["open", "high", "low", "close"])


def load_data(ticker=None, start=None, end=None, source=None, csv_path=None, server_tz=None):
    """CSV (UTC H1 or shorter, or raw MT5 export with server_tz) -> 1 h OHLC DataFrame with a naive UTC index
    (named 'time'). If the CSV carries MT5 spread, adds the `spread_pts` column."""
    source = source or ENGINE_DEFAULTS["data_source"]
    if source != "csv_hourly":
        raise ValueError("This engine only uses hourly CSV (csv_hourly); there is no Yahoo source.")
    path = _find_csv(csv_path or ENGINE_DEFAULTS["csv_path"])
    server_tz = server_tz or ENGINE_DEFAULTS["server_tz"]
    raw = _read_csv_any_sep(path)

    if any(str(c).strip().startswith("<") for c in raw.columns):          # raw MetaTrader export
        if server_tz is None:
            raise ValueError(
                f"'{path.name}' is a RAW MetaTrader export (<DATE> <TIME> headers): it is in SERVER time, not "
                f"UTC. Pass server_tz='ny_close' (or an IANA zone) to load_data / engine_defaults, or convert "
                f"to UTC first. Columns: {list(raw.columns)}")
        raw.columns = [str(c).strip().strip("<>").lower() for c in raw.columns]
        if "date" not in raw.columns or "time" not in raw.columns:
            raise KeyError(f"MT5 export without <DATE>/<TIME>. Columns: {list(raw.columns)}")
        stamp = raw["date"].astype(str).str.strip() + " " + raw["time"].astype(str).str.strip()
        try:
            naive = pd.DatetimeIndex(pd.to_datetime(stamp, format="%Y.%m.%d %H:%M:%S"))
        except (ValueError, TypeError):
            naive = pd.DatetimeIndex(pd.to_datetime(stamp))               # e.g. H1 export with <TIME> = HH:MM
        idx_utc, keep = _server_to_utc(naive, server_tz)
        raw = raw.loc[keep].reset_index(drop=True)
        raw["time"] = idx_utc
        if "spread" in raw.columns:
            raw["spread_pts"] = raw["spread"]
    else:
        raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]

    tcol = next((c for c in ("open_time", "timestamp", "time", "datetime", "date", "open_timestamp")
                 if c in raw.columns), None)
    if tcol is None:
        raise KeyError(f"No time column in '{path}'. Rename the date column to 'time' (UTC). "
                       f"Columns: {list(raw.columns)}")
    t = raw[tcol]
    if pd.api.types.is_numeric_dtype(t):
        m = float(t.iloc[0])
        unit = "us" if m > 1e15 else "ms" if m > 1e11 else "s"
        idx = pd.to_datetime(t, unit=unit, utc=True)
    else:
        idx = pd.to_datetime(t, utc=True)
    need = ["open", "high", "low", "close"]
    miss = [c for c in need if c not in raw.columns]
    if miss:
        raise KeyError(f"Missing columns {miss}. Columns: {list(raw.columns)}")
    cols = need + (["spread_pts"] if "spread_pts" in raw.columns else [])
    df = raw[cols].astype(float)
    df.index = pd.DatetimeIndex(idx).tz_convert(None)
    df.index.name = "time"
    df = df[~df.index.duplicated(keep="first")].sort_index()

    # Candles shorter than 1 h (M1/M5/M15...) -> 1 h UTC candles. Aggregated BEFORE trimming by dates.
    step = df.index.to_series().diff().median()
    if ENGINE_DEFAULTS["resample_h1"] and pd.notna(step) and step < H1:
        n0 = len(df)
        df = _to_h1(df)
        print(f"Aggregated to H1: {n0:,} candles of {step} -> {len(df):,} candles of 1 h.")

    if start is not None:
        df = df[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    # FX: the weekend gap (~48 h) is normal. Only warn about gaps INSIDE the week (1 h < gap < 40 h)
    step = df.index.to_series().diff().dropna()
    gaps = int(((step > H1) & (step < pd.Timedelta(hours=40))).sum())
    if gaps:
        print(f"WARNING: {gaps} intraweek gaps in the index (holidays or missing candles). "
              f"Windows with a gap are discarded.")
    return df


def weekly_boundaries_check(df):
    """
    Timezone check for the server clock. With the right conversion, the FX market closes on Friday at 17:00 NY
    (= 22:00 London) and opens on Sunday at 17:00 NY (= 22:00 London), so the LAST Friday candle has London local
    hour 21 and the FIRST Sunday candle has hour 22 (except the ~3 weeks a year when the US and UK DST changes do
    not coincide: there it shows 20/21 and 21/22). If most weeks fall elsewhere, server_tz is wrong.
    Returns a dict with two Series of counts by London local hour.
    """
    loc = df.index.tz_localize("UTC").tz_convert(LONDON).tz_localize(None)
    s = pd.Series(loc.hour, index=loc)
    dow = s.index.dayofweek
    fri, sun = s[dow == 4], s[dow == 6]
    last_fri = fri.groupby(fri.index.normalize()).last()
    first_sun = sun.groupby(sun.index.normalize()).first()
    return dict(friday_last_hour=last_fri.value_counts().sort_index(),
                sunday_first_hour=first_sun.value_counts().sort_index())


# ------------------------------------------------------------------ calendar and preparation
def month_end_days(first, last) -> pd.DatetimeIndex:
    """Last business day (Monday to Friday) of each month between two local dates, both inclusive."""
    first, last = pd.Timestamp(first).normalize(), pd.Timestamp(last).normalize()
    months = pd.period_range(first, last, freq="M")
    days = pd.DatetimeIndex([(m.to_timestamp() + pd.offsets.BMonthEnd(0)).normalize() for m in months])
    return days[(days >= first) & (days <= last)]


def prepare(df, entry_hour=None, exit_hour=None, tz=None):
    """
    Adds the local-time calendar columns (local_hour, local_date, local_dow, is_month_end_day) and three window
    flags, all with `hold` contiguous candles and exit exactly at `exit_hour`:
        entry_ok  entry candle of the rule (last business day of the month, 12:00 local)
        day_ok    the same window on ANY business day (control group: 'naked')
        win_ok    contiguous window of `hold` candles from any hour (basis of the permutation draws)
    There are no indicators: the rule is calendar-based.
    """
    entry_hour, exit_hour, tz = _cfg("entry_hour", entry_hour), _cfg("exit_hour", exit_hour), _cfg("tz", tz)
    hold = int(exit_hour - entry_hour)
    if hold <= 0:
        raise ValueError("exit_hour must be later than entry_hour (the trade is intraday)")
    d = df.copy()
    local = d.index.tz_localize("UTC").tz_convert(tz).tz_localize(None)
    d["local_hour"], d["local_date"], d["local_dow"] = local.hour, local.normalize(), local.dayofweek
    d["is_month_end_day"] = d["local_date"].isin(month_end_days(d["local_date"].min(), d["local_date"].max()))

    n, idx = len(d), d.index
    win_ok, exit_ok = np.zeros(n, bool), np.zeros(n, bool)
    hh = d["local_hour"].to_numpy()
    if n > hold:
        win_ok[:-hold] = (idx[hold:] - idx[:-hold]) == hold * H1
        exit_ok[:-hold] = hh[hold:] == exit_hour
    start = (hh == entry_hour) & np.asarray(idx.minute == 0) & (d["local_dow"].to_numpy() < 5)
    d["win_ok"] = win_ok
    d["day_ok"] = win_ok & exit_ok & start
    d["entry_ok"] = d["day_ok"] & d["is_month_end_day"].to_numpy()
    d.attrs.update(entry_hour=entry_hour, exit_hour=exit_hour, hold=hold, tz=tz)
    return d


def _pick(df, key, value):
    have = df.attrs.get(key)
    if value is not None and have is not None and have != value:
        raise ValueError(f"df was prepared with {key}={have} but you asked for {key}={value}: call prepare() again.")
    return value if value is not None else (have if have is not None else ENGINE_DEFAULTS[key])


def _rollovers(t0, t1, hour):
    first = t0.normalize() + pd.Timedelta(hours=hour)
    if first <= t0:
        first += pd.Timedelta(days=1)
    return 0 if first > t1 else int((t1 - first) / pd.Timedelta(days=1)) + 1


# ------------------------------------------------------------------ backtest
TRADE_COLS = ["entry_time", "exit_time", "entry_price", "exit_price", "type", "pnl", "win", "bars",
              "i_ent", "i_sal", "gross_bps", "net_bps", "nights", "pnl_frac"]


def run_fix_backtest(df, side=None, entry_hour=None, exit_hour=None, universe="month_end",
                     cost_bps_per_side=None, financing_bps_per_night=None, rollover_hour_utc=None,
                     size_fraction=None, side_by_entry=None):
    """
    universe: 'month_end' (the rule: last business day of the month) | 'every_day' (same window every business
    day = 'naked' control group). Costs and financing as in the header.
    side_by_entry: optional Series/dict {entry_time: 'long' | 'short'} (v2). Entries not in it are not traded and
    `side` is ignored.
    """
    if "entry_ok" not in df.columns:
        raise ValueError("Call prepare(df) first.")
    _pick(df, "entry_hour", entry_hour), _pick(df, "exit_hour", exit_hour)   # only validates against prepare()
    if universe not in ("month_end", "every_day"):
        raise ValueError("universe must be 'month_end' or 'every_day'")
    side = _cfg("side", side) if side_by_entry is None else None
    hold = int(df.attrs["hold"])
    if side is not None:
        _sign(side)                                                       # validates 'long' / 'short'
    side_map = None if side_by_entry is None else {pd.Timestamp(k): v for k, v in dict(side_by_entry).items()}
    cost = _cfg("cost_bps_per_side", cost_bps_per_side) / 1e4
    fin_bps = _cfg("financing_bps_per_night", financing_bps_per_night)
    roll_h = _cfg("rollover_hour_utc", rollover_hour_utc)
    frac = _cfg("size_fraction", size_fraction)

    idx, o = df.index, df["open"].to_numpy(float)
    flag = "entry_ok" if universe == "month_end" else "day_ok"
    rows = []
    for i in np.flatnonzero(df[flag].to_numpy(bool)):
        j = i + hold
        if j >= len(df) or (idx[j] - idx[i]) != hold * H1:
            continue
        sd = side if side_map is None else side_map.get(idx[i])
        if sd is None:                                                    # v2: no signal for this day -> no trade
            continue
        s = _sign(sd)
        entry, exit_ = o[i] * (1 + s * cost), o[j] * (1 - s * cost)
        nights = _rollovers(idx[i], idx[j], roll_h)
        pnl = s * (exit_ / entry - 1) * 100.0 - nights * fin_bps / 100.0
        rows.append(dict(entry_time=idx[i], exit_time=idx[j], entry_price=entry, exit_price=exit_, type=sd,
                         pnl=pnl, win=pnl > 0, bars=hold, i_ent=int(i), i_sal=int(j),
                         gross_bps=s * (o[j] / o[i] - 1) * 1e4, net_bps=pnl * 100.0, nights=int(nights),
                         pnl_frac=pnl * frac))
    return pd.DataFrame(rows, columns=TRADE_COLS)


# ------------------------------------------------------------------ v2: direction from relative equity performance
def _open_at(px: pd.DataFrame, ts, tol: pd.Timedelta) -> float:
    """Open of the last bar at or before `ts` (UTC naive). NaN if there is none within `tol` (no lookahead)."""
    pos = px.index.searchsorted(ts, side="right") - 1
    if pos < 0 or ts - px.index[pos] > tol:
        return np.nan
    return float(px["open"].iloc[pos])


def relative_equity_signal(df, idx_a, idx_b, entry_hour=None, tz=None, tol_hours=6):
    """
    v2 signal. df = prepared EURGBP frame (needs entry_ok / local_date); idx_a = GER40 and idx_b = UK100, both as
    returned by load_data (1 h, UTC naive). For each month-end entry:
        R (bps) = [A(entry open) / A(prev month-end, entry_hour London open) - 1]
                - [B(entry open) / B(prev month-end, entry_hour London open) - 1]
    Everything is known at the entry open: no lookahead. Direction (declared before running, never inverted):
        R > 0 -> 'short' EURGBP | R < 0 -> 'long' EURGBP | R == 0 or missing data -> no trade.
    Returns a DataFrame indexed by entry_time with columns r_bps and side (side is NaN where there is no trade).
    """
    entry_hour, tz = _cfg("entry_hour", entry_hour), _cfg("tz", tz)
    tol = pd.Timedelta(hours=tol_hours)
    mask = df["entry_ok"].to_numpy(bool)
    ent, dates = df.index[mask], df.loc[mask, "local_date"]
    rows = []
    for t, d in zip(ent, dates):
        prev = d.to_period("M") - 1
        prev_end = month_end_days(prev.start_time, prev.end_time)[-1]            # last business day of prev month
        ts_prev = (prev_end + pd.Timedelta(hours=entry_hour)).tz_localize(tz, ambiguous="NaT", nonexistent="NaT")
        if pd.isna(ts_prev):
            rows.append((t, np.nan))
            continue
        ts_prev = ts_prev.tz_convert("UTC").tz_localize(None)
        a0, b0 = _open_at(idx_a, ts_prev, tol), _open_at(idx_b, ts_prev, tol)
        a1, b1 = _open_at(idx_a, t, tol), _open_at(idx_b, t, tol)
        rows.append((t, ((a1 / a0 - 1.0) - (b1 / b0 - 1.0)) * 1e4))
    out = pd.DataFrame(rows, columns=["entry_time", "r_bps"]).set_index("entry_time")
    out["side"] = np.where(out["r_bps"] > 0, "short", np.where(out["r_bps"] < 0, "long", None))
    return out


def sign_permutation_test(long_bps, signs, draws=5000, seed=7):
    """
    One-sided test that the signal adds value. long_bps = gross return of EURGBP over each window as if LONG;
    signs = +1 (long) / -1 (short) actually taken. Observed = mean(signs * long_bps) against `draws` random
    permutations of the signs across the same windows (same number of longs and shorts), so the baseline drift
    is neutralised and only the TIMING of the direction is tested. p = (1 + #draws >= obs) / (1 + draws).
    """
    r, sg = np.asarray(long_bps, float), np.asarray(signs, float)
    rng = np.random.default_rng(seed)
    order = np.argsort(rng.random((draws, len(sg))), axis=1)
    sims = (sg[order] * r).mean(axis=1)
    obs = float((sg * r).mean())
    return dict(p=float((1 + (sims >= obs).sum()) / (1 + draws)), obs=obs, ctrl_mean=float(sims.mean()),
                ctrl_sd=float(sims.std(ddof=1)), z=float((obs - sims.mean()) / sims.std(ddof=1)), sims=sims)


# ------------------------------------------------------------------ CFD sizing
def lot_size(capital, price, target_fraction=None, contract_size=None, min_lot=None, lot_step=None,
             quote_to_account=None):
    """Lots that can be opened without exceeding target_fraction of the capital. 0.0 if below the minimum lot.
    price * quote_to_account = price in the account currency."""
    target_fraction = _cfg("size_fraction", target_fraction)
    contract_size = _cfg("contract_size", contract_size)
    min_lot, lot_step = _cfg("min_lot", min_lot), _cfg("lot_step", lot_step)
    fx = float(_cfg("quote_to_account", quote_to_account))
    if capital <= 0 or price <= 0 or fx <= 0:
        return 0.0
    raw = capital * target_fraction / (price * fx * contract_size)
    lots = round(np.floor(raw / lot_step + 1e-9) * lot_step, 8)
    return float(lots) if lots >= min_lot - 1e-12 else 0.0


def min_capital_for_target(price, target_fraction=None, contract_size=None, min_lot=None, quote_to_account=None):
    """Minimum capital (in the account currency) so that the minimum lot does not weigh more than target_fraction."""
    target_fraction = _cfg("size_fraction", target_fraction)
    contract_size, min_lot = _cfg("contract_size", contract_size), _cfg("min_lot", min_lot)
    fx = float(_cfg("quote_to_account", quote_to_account))
    return float(min_lot * contract_size * price * fx / target_fraction)


def cfd_trade_sizes(trades, capital, target_fraction=None, contract_size=None, min_lot=None,
                    lot_step=None, compounding=True, quote_to_account=None, lots=None):
    """
    One row per trade: lots, notional (in the account currency) and effective fraction of the capital in force at
    entry (size_fraction, ready to use as `sizing`). With compounding=True the size follows the equity; with
    False it is always computed on the initial `capital`. `lots` fixes the size (e.g. the minimum lot) instead of
    deriving it from target_fraction. A trade with 0 lots is not taken (return 0).
    """
    contract_size = _cfg("contract_size", contract_size)
    fx = float(_cfg("quote_to_account", quote_to_account))
    n = len(trades)
    lot_arr, notional, frac_eff, equity_after = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    equity = float(capital)
    for k, r in enumerate(trades.itertuples()):
        base = equity if compounding else float(capital)
        l = float(lots) if lots is not None else lot_size(base, r.entry_price, target_fraction, contract_size,
                                                          min_lot, lot_step, fx)
        nom = l * contract_size * r.entry_price * fx
        f = nom / equity if equity > 0 else 0.0
        lot_arr[k], notional[k], frac_eff[k] = l, nom, f
        equity *= 1.0 + f * r.pnl / 100.0
        equity_after[k] = equity
    return pd.DataFrame(dict(entry_time=trades["entry_time"].to_numpy(), lots=lot_arr, notional=notional,
                             size_fraction=frac_eff, taken=lot_arr > 0, equity_after=equity_after),
                        index=trades.index)


# ------------------------------------------------------------------ returns (MTM)
def _size(sizing):
    if isinstance(sizing, (int, float)):
        return float(sizing)
    if sizing == "capital":
        return 1.0
    if sizing == "fraction":
        return float(ENGINE_DEFAULTS["size_fraction"])
    raise ValueError("sizing must be 'capital', 'fraction', a number or an array with one fraction per trade")


def _sizes(sizing, n):
    if isinstance(sizing, (np.ndarray, pd.Series, list, tuple)):
        arr = np.asarray(sizing, float)
        if len(arr) != n:
            raise ValueError(f"sizing has {len(arr)} elements and there are {n} trades")
        return arr
    return np.full(n, _size(sizing))


def _value(price, entry, s):
    """Value of 1 unit of capital (100 % size) when the price is `price`: long P/E, short 2 - P/E."""
    return price / entry if s > 0 else 2.0 - price / entry


def trade_mtm_paths(df, trades, sizing="fraction"):
    """One return series per trade (hourly steps, already scaled to the size). One per row of trades.
    The product of (1 + step) at 100 % size is exactly 1 + pnl/100, for both long and short."""
    sizes, c, out = _sizes(sizing, len(trades)), df["close"].to_numpy(float), []
    for s_size, r in zip(sizes, trades.itertuples()):
        i, j, s = int(r.i_ent), int(r.i_sal), _sign(r.type)
        v = _value(c[i:j], r.entry_price, s)                       # value at the close of each candle of the trade
        p = np.empty(j - i + 1)
        p[0] = v[0] - 1.0
        p[1:j - i] = v[1:] / v[:-1] - 1.0
        p[j - i] = (1.0 + r.pnl / 100.0) / v[-1] - 1.0             # final step: exit open, with costs and swap
        out.append(s_size * p)
    return out


def _step_log_returns(price_df, trades, sizing):
    lr = np.zeros(len(price_df))
    if len(trades):
        for (i, j), p in zip(trades[["i_ent", "i_sal"]].to_numpy(int), trade_mtm_paths(price_df, trades, sizing)):
            l, m = np.log1p(p), j - i
            lr[i:j] += l[:m]
            lr[j - 1] += l[m]
    return pd.Series(lr, index=price_df.index)


def hourly_returns(price_df, trades, sizing="fraction"):
    """MTM return per 1 h candle (0 on candles with no position). Basis of the hour-by-hour drawdown."""
    return np.expm1(_step_log_returns(price_df, trades, sizing))


def daily_returns(price_df, trades, sizing="fraction"):
    """MTM return per UTC day (0 on days with no position). The final exit step goes to the day of the last candle."""
    s = _step_log_returns(price_df, trades, sizing).groupby(price_df.index.normalize()).sum()
    return np.expm1(s)


def hourly_worst_returns(price_df, trades, sizing="fraction"):
    """
    Worst return of each 1 h candle INSIDE the candle (long: valued at the `low`; short: at the `high`), scaled to
    the size. Each step is measured against the previous close (the first candle, against the entry price with
    cost). 0 on candles with no position. Always <= hourly_returns of that candle.
    """
    sizes = _sizes(sizing, len(trades))
    lo, hi, c = (price_df[k].to_numpy(float) for k in ("low", "high", "close"))
    out = np.zeros(len(price_df))
    for s_size, r in zip(sizes, trades.itertuples()):
        i, j, s = int(r.i_ent), int(r.i_sal), _sign(r.type)
        worst = lo if s > 0 else hi
        v_prev = np.r_[1.0, _value(c[i:j - 1], r.entry_price, s)]  # value at the start of each candle (entry = 1.0)
        out[i:j] = s_size * (_value(worst[i:j], r.entry_price, s) / v_prev - 1.0)
    return pd.Series(out, index=price_df.index)


def hard_limit_report_intrabar(price_df, trades, hard_limit, sizing="fraction"):
    """
    Maximum equity drawdown against the hard limit, also measuring the worst intrabar point.
    Returns max_dd (intrabar), max_dd_close (closes only), passed, headroom and trough_date.
    """
    hard_limit = float(hard_limit)
    hr = hourly_returns(price_df, trades, sizing).fillna(0.0)
    wr = hourly_worst_returns(price_df, trades, sizing)
    eq = (1.0 + hr).cumprod()
    prev_eq = eq.shift(1).fillna(1.0)
    prev_peak = np.maximum(eq.cummax().shift(1).fillna(1.0), 1.0)
    dd_close = eq / np.maximum(eq.cummax(), 1.0) - 1.0
    dd_low = prev_eq * (1.0 + wr) / prev_peak - 1.0
    dd = np.minimum(dd_close, dd_low)
    mdd = float(dd.min()) if len(dd) else 0.0
    return dict(hard_limit=hard_limit, max_dd=mdd, max_dd_close=float(dd_close.min()) if len(dd) else 0.0,
                passed=bool(mdd >= -hard_limit), headroom=float(hard_limit + mdd),
                trough_date=(dd.idxmin() if len(dd) else None))


# ------------------------------------------------------------------ annual report and hard limit
ANNUAL_COLS = ["year", "ret", "mdd", "n_trades", "partial", "breach"]


def annual_returns(step_returns, trades=None, hard_limit=None):
    """
    Yearly table from per-step returns (hourly_returns or daily_returns). Columns: year, ret (yearly return),
    mdd (max drawdown within the year, starting from the capital on January 1st), n_trades (by entry year),
    partial (year with fewer than 358 days of data) and breach (mdd worse than -hard_limit).
    """
    r = pd.Series(step_returns, dtype=float)
    r = r[~r.index.duplicated(keep="first")].sort_index().fillna(0.0)
    if len(r) == 0:
        return pd.DataFrame(columns=ANNUAL_COLS)
    counts = (pd.to_datetime(trades["entry_time"]).dt.year.value_counts()
              if trades is not None and len(trades) else pd.Series(dtype=int))
    rows = []
    for year, g in r.groupby(r.index.year):
        eq = (1.0 + g).cumprod()
        dd = eq / np.maximum(eq.cummax(), 1.0) - 1.0
        span = (g.index.max().normalize() - g.index.min().normalize()).days + 1
        mdd = float(dd.min())
        rows.append(dict(year=int(year), ret=float(eq.iloc[-1] - 1.0), mdd=mdd,
                         n_trades=int(counts.get(year, 0)), partial=bool(span < 358),
                         breach=bool(hard_limit is not None and mdd < -float(hard_limit))))
    return pd.DataFrame(rows, columns=ANNUAL_COLS)


def hard_limit_report(step_returns, hard_limit):
    """
    Maximum equity drawdown (starting from 1.0) against the hard limit. With hourly_returns it is the
    hour-by-hour check (closes only; to include the worst intrabar point use hard_limit_report_intrabar).
    """
    hard_limit = float(hard_limit)
    r = pd.Series(step_returns, dtype=float).fillna(0.0)
    if len(r) == 0:
        return dict(hard_limit=hard_limit, max_dd=0.0, passed=True, headroom=hard_limit, peak_date=None,
                    trough_date=None, steps_in_breach=0, first_breach=None)
    eq = (1.0 + r).cumprod()
    dd = eq / np.maximum(eq.cummax(), 1.0) - 1.0
    trough = dd.idxmin()
    pre = eq.loc[:trough]
    peak_date = pre.idxmax() if pre.max() >= 1.0 else r.index[0]
    breached = dd < -hard_limit
    return dict(hard_limit=hard_limit, max_dd=float(dd.min()), passed=bool(dd.min() >= -hard_limit),
                headroom=float(hard_limit + dd.min()), peak_date=peak_date, trough_date=trough,
                steps_in_breach=int(breached.sum()),
                first_breach=(dd.index[breached.to_numpy()][0] if breached.any() else None))


def max_fraction_for_limit(price_df, trades, hard_limit, hi=2.0, tol=1e-4, intrabar=False):
    """Largest fixed fraction of capital per trade whose historical hour-by-hour drawdown respects the hard limit.
    intrabar=True uses the worst intrabar point instead of closes only."""
    def mdd_at(s):
        if intrabar:
            return hard_limit_report_intrabar(price_df, trades, hard_limit, float(s))["max_dd"]
        return hard_limit_report(hourly_returns(price_df, trades, float(s)), hard_limit)["max_dd"]

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
    """
    Fixed rules (no refitting): for each year Y with `is_years` full prior years, compares the annualized return
    of the IS with the return of year Y (OOS). The first year of the data is treated as partial and does not
    count as IS. Returns year, ret_is_anual, ret_oos, mdd_oos, n_oos.
    """
    trades = run_fix_backtest(df, **rules)
    daily = daily_returns(df, trades, sizing)
    years = sorted(set(daily.index.year))
    ty = pd.to_datetime(trades["entry_time"]).dt.year if len(trades) else pd.Series(dtype=int)
    rows = []
    for y in years:
        is_ys = list(range(y - is_years, y))
        if y - is_years <= years[0] or not all(k in years for k in is_ys):
            continue
        tot_is = (1 + daily[daily.index.year.isin(is_ys)]).prod()
        eq = (1 + daily[daily.index.year == y]).cumprod()
        rows.append(dict(year=y, ret_is_anual=tot_is ** (1 / is_years) - 1, ret_oos=float(eq.iloc[-1] - 1),
                         mdd_oos=float((eq / eq.cummax() - 1).min()), n_oos=int((ty == y).sum())))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ screening: windows, permutation, statistics
def window_table(df, side=None):
    """
    Gross return (bps, in the `side` direction) of ALL contiguous windows of `hold` candles that start on a local
    business day, from any hour. Columns: gross_bps, hour (local start hour), month_end (the window starts on the
    last business day of the month). It is the basis of the permutation test and of the placebos.
    """
    s, hold = _sign(_cfg("side", side)), int(df.attrs["hold"])
    pos = np.flatnonzero(df["win_ok"].to_numpy(bool) & (df["local_dow"].to_numpy() < 5))
    o = df["open"].to_numpy(float)
    return pd.DataFrame({"gross_bps": s * (o[pos + hold] / o[pos] - 1.0) * 1e4,
                         "hour": df["local_hour"].to_numpy()[pos],
                         "month_end": df["is_month_end_day"].to_numpy()[pos]}, index=df.index[pos])


def permutation_test(rule_bps, pool_bps, draws=5000, seed=7):
    """
    One-sided test: gross mean of the rule against `draws` samples (with replacement) of len(rule_bps) windows
    from `pool_bps` (control windows of equal length). p = (1 + #draws >= rule) / (1 + draws).
    """
    rule, pool = np.asarray(rule_bps, float), np.asarray(pool_bps, float)
    sims = np.random.default_rng(seed).choice(pool, size=(draws, len(rule))).mean(axis=1)
    obs = float(rule.mean())
    return dict(p=float((1 + (sims >= obs).sum()) / (1 + draws)), obs=obs, ctrl_mean=float(pool.mean()),
                ctrl_sd=float(sims.std(ddof=1)), z=float((obs - sims.mean()) / sims.std(ddof=1)), sims=sims)


def tstat(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan


def profit_factor(x):
    x = np.asarray(x, float)
    loss = -x[x < 0].sum()
    return float(x[x > 0].sum() / loss) if loss > 0 else np.inf


def drop_best(x, share=0.10):
    """Mean of the trades left after removing the best `share` (highest first)."""
    x = np.sort(np.asarray(x, float))
    return float(x[: int(len(x) * (1.0 - share))].mean())


def years_positive(values, index):
    """Share of years (with at least one trade) whose mean is positive."""
    by_year = pd.Series(np.asarray(values, float), index=pd.DatetimeIndex(index)).groupby(lambda t: t.year).mean()
    return float((by_year > 0).mean()), by_year


def gate(name, value, threshold, op=">=", kill=False):
    """
    One screening gate: `value` against `threshold` with op '>=' | '>' | '<'. value=None/NaN -> PENDING (cannot
    be evaluated yet, does not count as a failure). shortfall = how much it misses by, relative to the threshold
    (CASI < 10 %). kill=True: a failure is an immediate discard (OOS, permutation, decay).
    """
    ok_ops = {">=": lambda v, t: v >= t, ">": lambda v, t: v > t, "<": lambda v, t: v < t}
    if op not in ok_ops:
        raise ValueError("op must be '>=', '>' or '<'")
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return dict(name=name, value=None, threshold=threshold, op=op, kill=kill, status="PENDING", shortfall=0.0)
    passed = bool(ok_ops[op](value, threshold))
    gap = (threshold - value) if op in (">=", ">") else (value - threshold)
    shortfall = 0.0 if passed else (gap / abs(threshold) if threshold else np.inf)
    return dict(name=name, value=float(value), threshold=threshold, op=op, kill=kill,
                status="PASS" if passed else "FAIL", shortfall=float(shortfall))


def screen_verdict(gates, t_oos, t_oos_min=1.645, casi_tol=0.10, declared=True):
    """
    PASA: every gate passes. CASI: exactly ONE gate fails by less than `casi_tol` of its threshold, the OOS t
    reaches `t_oos_min` and the direction and window were declared before seeing results. A kill failure (OOS,
    permutation, decay) is an immediate STOP. PENDING gates do not count, but are noted in the verdict.
    (Verdict labels PASA / CASI / STOP are kept as-is for compatibility with the notebooks.)
    """
    fails = [g for g in gates if g["status"] == "FAIL"]
    pending = [g["name"] for g in gates if g["status"] == "PENDING"]
    note = f" (pending: {', '.join(pending)})" if pending else ""
    if not fails:
        return "PASA" + note
    if any(g["kill"] for g in fails):
        return "STOP"
    t_ok = t_oos is not None and not np.isnan(t_oos) and t_oos >= t_oos_min
    if len(fails) == 1 and fails[0]["shortfall"] < casi_tol and declared and t_ok:
        return "CASI" + note
    return "STOP"


# ------------------------------------------------------------------ correlation with other edges
def daily_trade_pnl(trades, col="pnl_frac", when="exit_time"):
    """Return per day (date of `when`) from a trades table. Sums the trades of the same day."""
    s = pd.Series(trades[col].to_numpy(float), index=pd.to_datetime(trades[when]).dt.normalize())
    return s.groupby(level=0).sum()


def return_correlation(a, b):
    """Pearson correlation of two daily series over the common range, with 0 on days without a trade in each.
    Returns (corr, n_common_days, n_days_with_both): with few overlapping days the correlation says little."""
    lo, hi = max(a.index.min(), b.index.min()), min(a.index.max(), b.index.max())
    days = pd.date_range(lo, hi, freq="D")
    x, y = a.reindex(days).fillna(0.0), b.reindex(days).fillna(0.0)
    both = int(((x != 0) & (y != 0)).sum())
    corr = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else np.nan
    return corr, len(days), both
