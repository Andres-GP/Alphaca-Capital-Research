"""
weekly_momentum_engine.py  ·  02_strategy_development/Weekly_Momentum/weekly_momentum_engine.py   (v2)

Engine of the Weekly Momentum edge (weekly time-series momentum) on 1 h candles (UTC) of an Axi CFD
(variants v1_ethusd / v2_ethusd_long). Same API shape as monday_effect_engine / rsi2_engine so notebooks 01/02/03
follow the same pattern:

    load_data / prepare / run_weekly_backtest / daily_returns / trade_mtm_paths /
    walk_forward_fixed / set_engine_defaults / ENGINE_DEFAULTS
    apply_cfd_preset / CFD_PRESETS · lot_size / min_capital_for_target / cfd_trade_sizes
    hourly_returns / hourly_worst_returns / hard_limit_report / hard_limit_report_intrabar
    annual_returns / max_fraction_for_limit · split_trades · max_concurrent

What changed in v2 (nothing changes unless you ask for it; with trend_filter_days = 0 every number is identical
to v1 of the engine):
  - NEW optional regime filter `trend_filter_days` (0 = OFF, the default). With N > 0 a LONG is only taken if the
    close of the signal candle is above the mean of the closes of the previous N calendar days, and a SHORT only
    if it is below. It is evaluated at the signal candle (the candle BEFORE the entry): no lookahead. Skipped
    weeks are counted in trades.attrs['skipped']['trend_filter'] / ['trend_warmup'].
    It is ONE pre-declared rule, not a grid: choosing N after looking at the results is another trial on the
    same dataset and must be counted as such in the multiple-trials correction.
  - NEW helper max_concurrent(trades): maximum number of trades open at the same time. With hold_days > 7 the
    weekly trades OVERLAP by design (hold 11 -> up to 2 open at once), so "no overlap" is only a valid sanity
    check for hold_days <= 7; for longer holds the check is max_concurrent <= ceil(hold_days / 7).
  - Docstrings: the research rule (28 d / 7 d) is the DEFAULT; the candidate variants set lookback_days and
    hold_days in their YAML (candidate: 31 / 11, long only). Rollovers crossed per trade = hold_days.

Data input (load_data):
  - Either a CSV already converted (column 'time' in UTC) or the RAW MetaTrader 5 export as it comes out of
    the terminal (headers <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>, SERVER time,
    comma or tab separated). The raw export is converted INSIDE load_data (server time -> UTC), so there is no
    separate conversion step: the same file that MT5 gives is the one the engine reads.

Rule (research reference, frozen on ETHUSD H1 Axi 2018-2026; defaults lookback 28 d / hold 7 d):
  - Every MONDAY 00:00 Axi SERVER time (= New York time + 7 h; in UTC it falls on Sunday 21:00 or 22:00).
  - Signal at the CLOSE of the candle before the entry (no lookahead): sign of the return of the previous
    `lookback_days` days, measured against the close of the candle before the entry `lookback_days` days earlier.
  - LONG if the return > 0, SHORT if < 0. Entry at the OPEN of the 00:00 server candle; exit at the open of the
    00:00 server candle `hold_days` days later. No stop, no target (optional trend filter, see above).
  - CSV prices are BID. LONG pays the spread of the ENTRY candle (buys at the ask);
    SHORT pays the spread of the EXIT candle (buys back at the ask). cost_mode="fixed" uses cost_bps_per_side.
  - Swap in annual % on the current price (Axi ETHUSD: long -20, short -5), charged at every server rollover
    (00:00) with a multiplier per server day ending at that rollover: Mon-Thu x1, Fri x3, Sat/Sun x0
    (= 7 nights per week).

Deliberate differences from monday_effect_engine:
  - There are LONG and SHORT positions: trades['type'] is 'long'/'short' (and trades['side'] = +1/-1).
  - The MTM return is measured with a FIXED NOTIONAL at entry (a CFD with constant lots), not rescaled every
    hour: with sizing<1 the product of the steps is exactly 1 + sizing*pnl/100 (also true for shorts).
  - The entry is defined on the SERVER clock (it respects the New York daylight-saving change: the change
    weeks last 167 or 169 h in UTC). entry_clock="utc" uses the UTC clock instead.
  - below_min_lot: "skip" (default, like the Monday engine: 0 lots = trade not taken) or "min_lot" (trades the
    minimum lot even if it weighs more than size_fraction; useful to measure the real drawdown with small capital).
  - With hold_days > 7 positions overlap; the MTM / drawdown functions add the exposure of every open trade.

Conventions (same as Monday):
  - trades['pnl'] is in % of the entry notional, NET of cost and swap (same as utils.compute_metrics).
  - trades['pnl_frac'] = pnl * size_fraction.
  - Indicators are precomputed in prepare() over the WHOLE history; df can then be sliced into IS/OOS
    without losing the signal warm-up. A trade whose exit falls outside the df it receives is discarded
    (and counted in trades.attrs['skipped']); for the IS/OOS split the cleanest way is to run on the full df
    and split with split_trades().
  - Bars with SPREAD=0 (not recorded) are NOT discarded: cost uses the ANNUAL median of the non-zero spread
    (column spread_filled in trades).
  - `sizing` accepts 'capital', 'fraction', a number, or an array/Series with one fraction per trade
    (the output of cfd_trade_sizes).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
H1 = pd.Timedelta(hours=1)

ENGINE_DEFAULTS = dict(
    data_source="csv_hourly",
    csv_path=None,                 # see _find_csv: relative to cwd or to this file, or absolute
    lookback_days=28,
    hold_days=7,
    entry_dow=0,                   # 0 = Monday (of the clock chosen in entry_clock)
    entry_hour=0,                  # 0 = 00:00 server time
    entry_clock="server",          # "server" (NY + server_offset_hours, research rule) | "utc"
    server_offset_hours=7,
    direction="both",              # "both" | "long_only" | "short_only"
    cost_mode="spread",            # "spread" = spread of the correct candle | "fixed" = cost_bps_per_side
    cost_bps_per_side=0.0,
    trend_filter_days=0,           # 0 = OFF. N > 0: long only above / short only below the mean close of the last N days
    point_size=0.001,              # Axi ETHUSD: 3 digits (the CSV SPREAD is expressed in points)
    use_swap=True,
    swap_long_pct_annual=-20.0,    # annual % on the current price
    swap_short_pct_annual=-5.0,
    swap_day_mult={0: 1, 1: 1, 2: 1, 3: 1, 4: 3, 5: 0, 6: 0},   # server day that ENDS at the rollover
    swap_days_per_year=365.0,
    size_fraction=0.25,
    contract_size=1.0,             # 1 CFD = 1 ETH
    min_lot=0.1,
    lot_step=0.1,
    quote_to_account=1.0,          # ETHUSD is quoted in USD and the account is in USD
    below_min_lot="skip",          # "skip" | "min_lot"
)

CFD_PRESETS = {
    "axi_ethusd": dict(contract_size=1.0, min_lot=0.1, lot_step=0.1, point_size=0.001,
                       swap_long_pct_annual=-20.0, swap_short_pct_annual=-5.0,
                       swap_day_mult={0: 1, 1: 1, 2: 1, 3: 1, 4: 3, 5: 0, 6: 0}),
}


def set_engine_defaults(**kw):
    for k, v in kw.items():
        if k not in ENGINE_DEFAULTS:
            raise KeyError(f"'{k}' is not a valid engine_default. Valid ones: {sorted(ENGINE_DEFAULTS)}")
        ENGINE_DEFAULTS[k] = v


def apply_cfd_preset(name, cost_bps_per_side=None, quote_to_account=None):
    """Loads minimum lot, step, contract size, digits and swap of the symbol. cost_bps_per_side only if you
    pass it (it is not used with cost_mode='spread'). quote_to_account: price -> account currency factor."""
    if name not in CFD_PRESETS:
        raise KeyError(f"Preset '{name}' does not exist. Valid ones: {sorted(CFD_PRESETS)}")
    extra = {}
    if cost_bps_per_side is not None:
        extra["cost_bps_per_side"] = float(cost_bps_per_side)
    if quote_to_account is not None:
        extra["quote_to_account"] = float(quote_to_account)
    set_engine_defaults(**CFD_PRESETS[name], **extra)
    return {k: ENGINE_DEFAULTS[k] for k in (*CFD_PRESETS[name], *extra)}


def _cfg(name, value):
    return ENGINE_DEFAULTS[name] if value is None else value


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
    """Reads the CSV with a comma (the usual case). If it comes out as a single column (the MT5 export is
    tab separated), retries detecting the separator."""
    raw = pd.read_csv(path)
    if raw.shape[1] == 1:
        raw = pd.read_csv(path, sep=None, engine="python")
    return raw


def _convert_raw_mt(raw: pd.DataFrame) -> pd.DataFrame:
    """RAW MetaTrader 5 export (<DATE> <TIME> <OPEN> ... in SERVER time) -> DataFrame with a 'time' column in
    naive UTC plus open, high, low, close, spread, volume.

    Server time is New York time + server_offset_hours (Axi: +7 h, i.e. GMT+2 in winter / GMT+3 in summer,
    switching on the US dates). So: NY wall clock = server - offset, then NY -> UTC with the real tz rules.
    The hour that repeats in the autumn change is resolved by order of appearance (first occurrence = summer
    time, second = winter time); the hour that does not exist in spring is shifted forward. Duplicates that
    this may create are dropped afterwards by load_data (first kept). Hours missing at the changes show up in
    load_data's gap warning."""
    r = raw.copy()
    r.columns = [str(c).strip().strip("<>").strip().lower() for c in r.columns]
    miss = [c for c in ("date", "time", "open", "high", "low", "close") if c not in r.columns]
    if miss:
        raise KeyError(f"Raw MT5 export without columns {miss}. Columns: {list(raw.columns)}")
    stamp = r["date"].astype(str).str.strip() + " " + r["time"].astype(str).str.strip()
    srv = None
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            srv = pd.to_datetime(stamp, format=fmt)
            break
        except (ValueError, TypeError):
            continue
    if srv is None:
        raise ValueError(f"Could not parse <DATE> <TIME> (expected 'YYYY.MM.DD HH:MM[:SS]'). "
                         f"First value: '{stamp.iloc[0]}'")
    ny_wall = pd.DatetimeIndex(srv) - pd.Timedelta(hours=ENGINE_DEFAULTS["server_offset_hours"])
    is_dst = ~ny_wall.duplicated(keep="first")      # only used by pandas for the repeated autumn hour
    utc = (ny_wall.tz_localize("America/New_York", ambiguous=np.asarray(is_dst), nonexistent="shift_forward")
                  .tz_convert("UTC").tz_localize(None))
    out = pd.DataFrame({"time": utc, "open": r["open"].to_numpy(), "high": r["high"].to_numpy(),
                        "low": r["low"].to_numpy(), "close": r["close"].to_numpy()})
    if "spread" in r.columns:
        out["spread"] = r["spread"].to_numpy()
    vcol = "tickvol" if "tickvol" in r.columns else ("vol" if "vol" in r.columns else None)
    if vcol:
        out["volume"] = r[vcol].to_numpy()
    return out


def load_data(ticker=None, start=None, end=None, source=None, csv_path=None):
    """Hourly CSV -> OHLC(+spread, volume) DataFrame with a naive UTC index (named 'time').
    Accepts a converted CSV (column 'time' in UTC) or the raw MT5 export (server time, converted here).
    The 'spread' column (in points) is kept if present: cost_mode='spread' uses it."""
    source = source or ENGINE_DEFAULTS["data_source"]
    if source != "csv_hourly":
        raise ValueError("This engine only uses hourly CSV data (csv_hourly).")
    if (csv_path or ENGINE_DEFAULTS["csv_path"]) is None:
        raise FileNotFoundError("No csv_path: set it in the YAML engine_defaults or pass it to load_data().")
    path = _find_csv(csv_path or ENGINE_DEFAULTS["csv_path"])
    raw = _read_csv_any_sep(path)
    if any(str(c).strip().startswith("<") for c in raw.columns):
        raw = _convert_raw_mt(raw)          # raw MT5 export: server time -> UTC
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
    cols = need + [c for c in ("spread", "volume") if c in raw.columns]
    df = raw[cols].astype(float)
    df.index = pd.DatetimeIndex(idx).tz_convert(None)
    df.index.name = "time"
    df = df[~df.index.duplicated(keep="first")].sort_index()
    if start is not None:
        df = df[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    gaps = int((df.index.to_series().diff().dropna() != H1).sum())
    if gaps:
        print(f"WARNING: {gaps} steps different from 1 h in the index (gaps). Weeks with a gap at the entry, "
              f"the exit or the reference are discarded.")
    return df


# ------------------------------------------------------------------ indicators
def _server_clock(index) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if ENGINE_DEFAULTS["entry_clock"] == "utc":
        return idx
    ny = idx.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
    return ny + pd.Timedelta(hours=ENGINE_DEFAULTS["server_offset_hours"])


def _spread_px(df: pd.DataFrame):
    """Spread per candle in price units. Zeros / NaN (not recorded) -> ANNUAL median of the non-zero spread
    (for the cost only). Returns (spread_px, filled)."""
    if "spread" not in df.columns:
        return np.full(len(df), np.nan), np.zeros(len(df), dtype=bool)
    pts = df["spread"].to_numpy(float)
    bad = ~(pts > 0)
    px = pts * ENGINE_DEFAULTS["point_size"]
    s = pd.Series(np.where(bad, np.nan, px), index=df.index)
    yearly = s.groupby(s.index.year).transform("median")
    overall = float(np.nanmedian(s.to_numpy())) if np.isfinite(s.to_numpy()).any() else np.nan
    return np.where(bad, yearly.fillna(overall).to_numpy(), px), bad


def _anchors(srv: pd.DatetimeIndex, entry_hour: int) -> pd.Series:
    """Position of every candle whose clock is exactly entry_hour:00, indexed by its time (chosen clock)."""
    mask = (srv.hour == entry_hour) & (srv.minute == 0)
    anch = pd.Series(np.flatnonzero(mask), index=srv[mask])
    return anch[~anch.index.duplicated(keep="first")]


def _momentum(df, srv, anch, ie, lookback_days) -> np.ndarray:
    """Return (%) of the previous `lookback_days` days, measured at the CLOSE of the candle before the entry and
    of the candle before the entry `lookback_days` days earlier. NaN if a candle is missing or there is no history."""
    c = df["close"].to_numpy(float)
    idx = df.index
    lb = anch.reindex(srv[ie] - pd.Timedelta(days=lookback_days)).to_numpy()
    out = np.full(len(ie), np.nan)
    ok = np.isfinite(lb) & (ie > 0)
    lbi = np.where(ok, lb, 0).astype(int)
    ok &= lbi > 0
    ip, lp = np.maximum(ie - 1, 0), np.maximum(lbi - 1, 0)
    one_h = np.timedelta64(1, "h")
    ok &= (idx[ie].values - idx[ip].values) == one_h
    ok &= (idx[lbi].values - idx[lp].values) == one_h
    out[ok] = (c[ip[ok]] / c[lp[ok]] - 1.0) * 100.0
    return out


def _trend_dev(df, ie, trend_days) -> np.ndarray:
    """Deviation (%) of the close of the SIGNAL candle (the one before each entry) from the mean close of the
    previous `trend_days` calendar days (window ending at that same candle, inclusive). NaN if the window is
    less than 90% full (start of the data, big gaps). Uses only information available at the signal candle."""
    s = df["close"]
    ma = s.rolling(f"{int(trend_days)}D", min_periods=int(0.9 * 24 * int(trend_days))).mean().to_numpy(float)
    ip = np.maximum(ie - 1, 0)
    c = s.to_numpy(float)
    out = (c[ip] / ma[ip] - 1.0) * 100.0
    out[ie < 1] = np.nan
    return out


def prepare(df, lookback_days=None, entry_dow=None, entry_hour=None, trend_filter_days=None):
    """
    Adds: srv_time (server clock), is_roll / roll_day_mult (swap rollovers), spread_px / spread_filled and,
    ONLY on the entry candles (entry_ok=True, with a contiguous signal candle): mom_ret (% of the previous
    `lookback_days` days; NaN during the warm-up or if a reference candle is missing) and trend_dev (% distance
    of the signal close from its N-day mean; NaN everywhere if trend_filter_days = 0).
    Computed ONCE over the whole history so IS/OOS can be sliced without losing the warm-up.
    """
    lookback_days = int(_cfg("lookback_days", lookback_days))
    entry_dow, entry_hour = _cfg("entry_dow", entry_dow), _cfg("entry_hour", entry_hour)
    trend_days = int(_cfg("trend_filter_days", trend_filter_days))
    d = df.copy()
    srv = _server_clock(d.index)
    d["srv_time"] = srv
    d["is_roll"] = (srv.hour == 0) & (srv.minute == 0)
    mult = {int(k): float(v) for k, v in ENGINE_DEFAULTS["swap_day_mult"].items()}
    ending_day = (srv.dayofweek.to_numpy() - 1) % 7     # server day that ENDS at this rollover
    d["roll_day_mult"] = np.array([mult.get(k, 0.0) for k in range(7)])[ending_day]
    d["spread_px"], d["spread_filled"] = _spread_px(d)

    cand = np.flatnonzero((srv.hour == entry_hour) & (srv.minute == 0) & (srv.dayofweek == entry_dow))
    cand = cand[cand >= 1]
    cand = cand[np.asarray((d.index[cand] - d.index[cand - 1]) == H1)]      # contiguous signal candle
    mom = np.full(len(d), np.nan)
    mom[cand] = _momentum(d, srv, _anchors(srv, entry_hour), cand, lookback_days)
    tdev = np.full(len(d), np.nan)
    if trend_days > 0 and len(cand):
        tdev[cand] = _trend_dev(d, cand, trend_days)
    entry_ok = np.zeros(len(d), bool)
    entry_ok[cand] = True
    d["mom_ret"], d["entry_ok"], d["trend_dev"] = mom, entry_ok, tdev
    d.attrs.update(lookback_days=lookback_days, entry_dow=entry_dow, entry_hour=entry_hour,
                   entry_clock=ENGINE_DEFAULTS["entry_clock"], trend_filter_days=trend_days)
    return d


def _pick(df, key, value):
    have = df.attrs.get(key)
    if value is not None and have is not None and have != value:
        raise ValueError(f"df was prepared with {key}={have} but you asked for {key}={value}: call prepare() again.")
    return value if value is not None else (have if have is not None else ENGINE_DEFAULTS[key])


# ------------------------------------------------------------------ backtest
TRADE_COLS = ["entry_time", "exit_time", "entry_price", "exit_price", "type", "side", "pnl", "win", "bars",
              "i_ent", "i_sal", "mom_ret", "gross_pct", "cost_pct", "swap_pct", "n_rolls", "spread_filled",
              "pnl_frac"]


def run_weekly_backtest(df, lookback_days=None, hold_days=None, entry_dow=None, entry_hour=None,
                        direction=None, cost_mode=None, cost_bps_per_side=None, use_swap=None,
                        size_fraction=None, trend_filter_days=None):
    """
    One trade per week. direction: 'both' | 'long_only' | 'short_only'.
    cost_mode: 'spread' (spread of the correct candle; long = entry, short = exit) | 'fixed' (bps per side).
    trend_filter_days: 0 = off; N > 0 = long only above / short only below the N-day mean close (see module doc).
    pnl is in % of the entry notional, net of cost and swap. i_ent / i_sal are positions inside the df received.
    With hold_days > 7 consecutive trades overlap (see max_concurrent).
    Discarded weeks are counted in trades.attrs['skipped'].
    """
    if "mom_ret" not in df.columns:
        raise ValueError("Call prepare(df) first.")
    lb = int(_pick(df, "lookback_days", lookback_days))
    edow, ehr = _pick(df, "entry_dow", entry_dow), _pick(df, "entry_hour", entry_hour)
    tf = int(_pick(df, "trend_filter_days", trend_filter_days))
    hold = int(_cfg("hold_days", hold_days))
    direction, cost_mode = _cfg("direction", direction), _cfg("cost_mode", cost_mode)
    cost_bps = float(_cfg("cost_bps_per_side", cost_bps_per_side))
    use_swap = bool(_cfg("use_swap", use_swap))
    frac = _cfg("size_fraction", size_fraction)
    if direction not in ("both", "long_only", "short_only"):
        raise ValueError("direction must be 'both', 'long_only' or 'short_only'")
    if cost_mode not in ("spread", "fixed"):
        raise ValueError("cost_mode must be 'spread' or 'fixed'")
    if cost_mode == "spread" and not np.isfinite(df["spread_px"].to_numpy()).any():
        raise ValueError("cost_mode='spread' needs the 'spread' column in the CSV; use cost_mode='fixed'.")

    D = ENGINE_DEFAULTS
    n, idx = len(df), df.index
    srv = pd.DatetimeIndex(df["srv_time"])
    anch = _anchors(srv, ehr)
    ie = np.flatnonzero(df["entry_ok"].to_numpy(bool))
    mom_all = df["mom_ret"].to_numpy(float)[ie]
    T = srv[ie]
    sk = dict(candidates=len(ie), warmup=0, no_signal_bar=0, zero_signal=0, no_exit=0, direction_filter=0,
              trend_warmup=0, trend_filter=0)
    warm = (T - pd.Timedelta(days=lb)) < srv.min()
    sk["warmup"] = int(warm.sum())
    sk["no_signal_bar"] = int((~np.isfinite(mom_all) & ~warm).sum())
    ix = anch.reindex(T + pd.Timedelta(days=hold)).to_numpy()
    sk["no_exit"] = int((np.isfinite(mom_all) & ~np.isfinite(ix)).sum())
    ok = np.isfinite(mom_all) & np.isfinite(ix)
    sk["zero_signal"] = int((ok & (mom_all == 0)).sum())
    ok &= mom_all != 0
    side_all = np.where(mom_all > 0, 1, -1)
    if direction != "both":
        want = 1 if direction == "long_only" else -1
        sk["direction_filter"] = int((ok & (side_all != want)).sum())
        ok &= side_all == want
    if tf > 0:
        tdev = df["trend_dev"].to_numpy(float)[ie]
        sk["trend_warmup"] = int((ok & ~np.isfinite(tdev)).sum())
        ok &= np.isfinite(tdev)
        agree = ((side_all > 0) & (tdev > 0)) | ((side_all < 0) & (tdev < 0))
        sk["trend_filter"] = int((ok & ~agree).sum())
        ok &= agree

    i0, i1 = ie[ok], ix[ok].astype(int)
    sd, sig = side_all[ok], mom_all[ok]
    o = df["open"].to_numpy(float)
    sp = df["spread_px"].to_numpy(float)
    filled_arr = df["spread_filled"].to_numpy(bool)

    if cost_mode == "fixed":
        c = cost_bps / 1e4
        e = np.where(sd > 0, o[i0] * (1 + c), o[i0] * (1 - c))
        x = np.where(sd > 0, o[i1] * (1 - c), o[i1] * (1 + c))
        filled = np.zeros(len(i0), bool)
    else:
        e = np.where(sd > 0, o[i0] + sp[i0], o[i0])        # long buys at the ask: bid + ENTRY spread
        x = np.where(sd > 0, o[i1], o[i1] + sp[i1])        # short buys back at the ask: bid + EXIT spread
        filled = np.where(sd > 0, filled_arr[i0], filled_arr[i1])
    price_pnl = sd * (x - e) / e
    gross = sd * (o[i1] - o[i0]) / o[i0]

    roll_pos = np.flatnonzero(df["is_roll"].to_numpy(bool))
    roll_mult = df["roll_day_mult"].to_numpy(float)[roll_pos]
    per_night = {1: D["swap_long_pct_annual"] / 100.0 / D["swap_days_per_year"],
                 -1: D["swap_short_pct_annual"] / 100.0 / D["swap_days_per_year"]}
    swap, n_rolls = np.zeros(len(i0)), np.zeros(len(i0), dtype=int)
    for j in range(len(i0)):
        lo, hi = np.searchsorted(roll_pos, i0[j], "right"), np.searchsorted(roll_pos, i1[j], "right")
        n_rolls[j] = hi - lo
        if use_swap and hi > lo:
            swap[j] = per_night[int(sd[j])] * float(np.sum(roll_mult[lo:hi] * o[roll_pos[lo:hi]] / e[j]))

    pnl = (price_pnl + swap) * 100.0
    trades = pd.DataFrame({
        "entry_time": idx[i0], "exit_time": idx[i1], "entry_price": e, "exit_price": x,
        "type": np.where(sd > 0, "long", "short"), "side": sd, "pnl": pnl, "win": pnl > 0, "bars": i1 - i0,
        "i_ent": i0, "i_sal": i1, "mom_ret": sig, "gross_pct": gross * 100.0,
        "cost_pct": (gross - price_pnl) * 100.0, "swap_pct": swap * 100.0, "n_rolls": n_rolls,
        "spread_filled": filled, "pnl_frac": pnl * frac}, columns=TRADE_COLS)
    trades.attrs["skipped"] = sk
    return trades.reset_index(drop=True)


def split_trades(trades, oos_start):
    """Splits the trades by entry date: (IS: entry_time < oos_start, OOS: entry_time >= oos_start)."""
    et, ts = pd.to_datetime(trades["entry_time"]), pd.Timestamp(oos_start)
    return trades[et < ts].copy(), trades[et >= ts].copy()


def max_concurrent(trades) -> int:
    """Maximum number of trades open at the same time (a trade is open from its entry candle up to, not
    including, its exit candle). 1 when hold_days <= 7; with hold_days = 11 and a weekly entry it is 2.
    Sanity bound for any hold: max_concurrent(trades) <= ceil(hold_days / 7)."""
    if len(trades) == 0:
        return 0
    starts = np.sort(trades["i_ent"].to_numpy(int))
    ends = np.sort(trades["i_sal"].to_numpy(int))
    open_at_start = np.searchsorted(starts, starts, "right") - np.searchsorted(ends, starts, "right")
    return int(open_at_start.max())


# ------------------------------------------------------------------ CFD sizing
def lot_size(capital, price, target_fraction=None, contract_size=None, min_lot=None, lot_step=None,
             quote_to_account=None, below_min_lot=None):
    """Lots that can be opened without exceeding target_fraction of the capital. If it does not reach the
    minimum lot: 0.0 with below_min_lot='skip', or min_lot with 'min_lot'. price * quote_to_account = price
    in account currency."""
    target_fraction = _cfg("size_fraction", target_fraction)
    contract_size = _cfg("contract_size", contract_size)
    min_lot, lot_step = _cfg("min_lot", min_lot), _cfg("lot_step", lot_step)
    policy = _cfg("below_min_lot", below_min_lot)
    fx = float(_cfg("quote_to_account", quote_to_account))
    if capital <= 0 or price <= 0 or fx <= 0:
        return 0.0
    raw = capital * target_fraction / (price * fx * contract_size)
    lots = round(np.floor(raw / lot_step + 1e-9) * lot_step, 8)
    if lots >= min_lot - 1e-12:
        return float(lots)
    return float(min_lot) if policy == "min_lot" else 0.0


def min_capital_for_target(price, target_fraction=None, contract_size=None, min_lot=None, quote_to_account=None):
    """Minimum capital (account currency) so the minimum lot does not weigh more than target_fraction."""
    target_fraction = _cfg("size_fraction", target_fraction)
    contract_size, min_lot = _cfg("contract_size", contract_size), _cfg("min_lot", min_lot)
    fx = float(_cfg("quote_to_account", quote_to_account))
    return float(min_lot * contract_size * price * fx / target_fraction)


def cfd_trade_sizes(trades, capital, target_fraction=None, contract_size=None, min_lot=None,
                    lot_step=None, compounding=True, quote_to_account=None, below_min_lot=None):
    """
    One row per trade: lots, notional (account currency) and the effective fraction of the capital at entry
    (size_fraction, ready to be used as `sizing`). With compounding=True the size follows the equity;
    with False it is computed on the initial `capital`. With below_min_lot='skip' a trade with 0 lots is not
    taken; with 'min_lot' the minimum lot is traded and flagged forced_min_lot=True.
    Note: the equity used here is updated trade by trade (each trade's pnl is booked in entry order), an
    approximation when trades overlap (hold_days > 7); the MTM functions below are the exact path.
    """
    contract_size = _cfg("contract_size", contract_size)
    fx = float(_cfg("quote_to_account", quote_to_account))
    min_lot_v = float(_cfg("min_lot", min_lot))
    n = len(trades)
    lots, notional, frac_eff, equity_after = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    forced = np.zeros(n, bool)
    equity = float(capital)
    for k, r in enumerate(trades.itertuples()):
        base = equity if compounding else float(capital)
        l = lot_size(base, r.entry_price, target_fraction, contract_size, min_lot, lot_step, fx, below_min_lot)
        ideal = lot_size(base, r.entry_price, target_fraction, contract_size, min_lot, lot_step, fx, "skip")
        forced[k] = l > 0 and ideal == 0
        nom = l * contract_size * r.entry_price * fx
        f = nom / equity if equity > 0 else 0.0
        lots[k], notional[k], frac_eff[k] = l, nom, f
        equity *= 1.0 + f * r.pnl / 100.0
        equity_after[k] = equity
    return pd.DataFrame(dict(entry_time=trades["entry_time"].to_numpy(), lots=lots, notional=notional,
                             size_fraction=frac_eff, taken=lots > 0, forced_min_lot=forced,
                             equity_after=equity_after), index=trades.index)


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


def _trade_pnl_paths(df, trades):
    """Per trade: (i0, i1, close_pnl, worst_pnl), cumulative pnl per candle per unit of entry notional.
    close_pnl marks to market at the close (bid) and adds the accrued swap; the last candle is fixed at the
    trade's final pnl (with exit cost and all the swap), so the product of the steps telescopes exactly.
    worst_pnl uses the candle low (longs) or high (shorts)."""
    D = ENGINE_DEFAULTS
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    roll_pos = np.flatnonzero(df["is_roll"].to_numpy(bool)) if D["use_swap"] else np.array([], int)
    roll_mult = df["roll_day_mult"].to_numpy(float)[roll_pos] if D["use_swap"] else np.array([])
    per_night = {1: D["swap_long_pct_annual"] / 100.0 / D["swap_days_per_year"],
                 -1: D["swap_short_pct_annual"] / 100.0 / D["swap_days_per_year"]}
    out = []
    for r in trades.itertuples(index=False):
        i0, i1, s, e = int(r.i_ent), int(r.i_sal), int(r.side), float(r.entry_price)
        k = np.arange(i0, i1)
        close_pnl = s * (c[k] - e) / e
        worst_pnl = s * ((l[k] if s > 0 else h[k]) - e) / e
        if len(roll_pos):
            lo, hi = np.searchsorted(roll_pos, i0, "right"), np.searchsorted(roll_pos, i1, "right")
            for p, m in zip(roll_pos[lo:hi], roll_mult[lo:hi]):
                if p < i1:
                    ch = per_night[s] * m * o[p] / e
                    close_pnl[p - i0:] += ch
                    worst_pnl[p - i0:] += ch
        close_pnl[-1] = float(r.pnl) / 100.0
        out.append((i0, i1, close_pnl, np.minimum(worst_pnl, close_pnl)))
    return out


def _g(pnl, size):
    return np.maximum(1.0 + size * pnl, 1e-12)      # equity relative to the entry equity; 1e-12 = liquidation


def _bar_returns(pnl_path, size):
    g = _g(pnl_path, size)
    return g / np.concatenate(([1.0], g[:-1])) - 1.0


def trade_mtm_paths(df, trades, sizing="fraction"):
    """One return series per trade (one step per 1 h candle, already scaled to the size). With sizing='capital'
    the product of (1 + step) is exactly 1 + pnl/100."""
    sizes = _sizes(sizing, len(trades))
    return [_bar_returns(p[2], s) for p, s in zip(_trade_pnl_paths(df, trades), sizes)]


def _step_log_returns(price_df, trades, sizing):
    lr = np.zeros(len(price_df))
    if len(trades):
        for (i0, i1, pc, _), s in zip(_trade_pnl_paths(price_df, trades), _sizes(sizing, len(trades))):
            lr[i0:i1] += np.log1p(_bar_returns(pc, s))
    return pd.Series(lr, index=price_df.index)


def hourly_returns(price_df, trades, sizing="fraction"):
    """MTM return per 1 h candle (0 on candles without a position). Basis of the hour-by-hour drawdown."""
    return np.expm1(_step_log_returns(price_df, trades, sizing))


def daily_returns(price_df, trades, sizing="fraction"):
    """MTM return per UTC day (0 on days without a position)."""
    s = _step_log_returns(price_df, trades, sizing).groupby(price_df.index.normalize()).sum()
    return np.expm1(s)


def hourly_worst_returns(price_df, trades, sizing="fraction"):
    """Worst return of each 1 h candle INSIDE the candle (long valued at the low, short at the high), measured
    against the previous close (the first candle, against the entry price with cost) and scaled to the size.
    0 on candles without a position. Always <= hourly_returns of that candle."""
    out = np.zeros(len(price_df))
    for (i0, i1, pc, pw), s in zip(_trade_pnl_paths(price_df, trades), _sizes(sizing, len(trades))):
        out[i0:i1] = _g(pw, s) / np.concatenate(([1.0], _g(pc, s)[:-1])) - 1.0
    return pd.Series(out, index=price_df.index)


def hard_limit_report_intrabar(price_df, trades, hard_limit, sizing="fraction"):
    """
    Maximum equity drawdown against the hard limit, also measuring the worst intra-candle point (long: low,
    short: high). Returns max_dd (intra-candle), max_dd_close (closes only), passed, headroom and trough_date.
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
    Annual table from per-step returns (hourly_returns or daily_returns). Columns: year, ret (return of the
    year), mdd (maximum drawdown within the year, starting from the capital on 1 January), n_trades (by entry
    year), partial (year with fewer than 358 days of data) and breach (mdd worse than -hard_limit; False if
    hard_limit is None).
    """
    r = pd.Series(step_returns, dtype=float)
    r = r[~r.index.duplicated(keep="first")].sort_index().fillna(0.0)
    if len(r) == 0:
        return pd.DataFrame(columns=ANNUAL_COLS)
    if trades is not None and len(trades):
        counts = pd.to_datetime(trades["entry_time"]).dt.year.value_counts()
    else:
        counts = pd.Series(dtype=int)
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
    hour-by-hour check (closes only; for the worst intra-candle point use hard_limit_report_intrabar).
    Returns max_dd (negative), passed, headroom (hard_limit + max_dd), peak and trough dates, how many steps
    were below the limit and the first date the limit was crossed.
    """
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


def max_fraction_for_limit(price_df, trades, hard_limit, hi=2.0, tol=1e-4, intrabar=False):
    """Largest fixed fraction of capital per trade whose historical hour-by-hour drawdown respects the hard
    limit. intrabar=True uses the worst intra-candle point instead of closes only."""
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
    Fixed rules (no refitting): for every year Y with `is_years` full previous years, compares the annualised
    return of the IS with the return of year Y (OOS). The first year of the data is considered partial and
    does not count as IS. Returns year, ret_is_anual, ret_oos, mdd_oos, n_oos.
    """
    trades = run_weekly_backtest(df, **rules)
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