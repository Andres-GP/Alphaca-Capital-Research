"""Overnight Gap Trading engine (5/15-min bars).
   MR (< gap_threshold) = trade AGAINST the gap.
   TF (>= gap_threshold) = trade WITH the gap.

v2 fixes:
  FIX #1  expo usa stop_dist real (MR: mr_stop_atr_mult·ATR, TF: tf_stop_atr_mult·ATR)
  NEW #2  tf_hold_days (0 = intradía; 1-3 = hold si cierre favorable, TF only)
  NEW #3  bad_dates (lista de fechas contaminadas a saltar)
  FIX #4  walk_forward_fixed acepta oos_start
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, Literal, Dict, Any, List, Iterable

DEFAULT_RULES: Dict[str, Any] = {
    "gap_min_trade": 0.5,
    "gap_threshold": 1.0,
    "gap_max_tf": 4.0,
    "entry_tf_min": 15,
    "mr_fill_target": 0.75,
    "tf_target_mult": 1.5,
    "mr_stop_atr_mult": 1.0,
    "tf_stop_atr_mult": 1.25,
    "time_exit": "target_or_eod",
    "skip_fridays": True,
    "slip_bps_per_side": 5.0,
    "entry_window_start": "09:40",
    "entry_window_end": "11:00",
    "tf_hold_days": 0,
}

ENGINE_DEFAULTS: Dict[str, Any] = {
    "financing_bps_per_night": 0.0,
    "risk_per_trade_pct": 1.0,
    "max_exposure": 1.0,
    "data_source": "csv_intraday",
    "csv_path": None,
    "session_tz": "America/New_York",
    "session_open": "09:30",
    "session_close": "16:00",
}

TIME_EXIT_MODES = ("eod", "target_or_eod")

_TRADE_COLS = ["session_date", "entry_time", "exit_time", "direction", "strategy", "gap_pct",
               "entry_price", "exit_price", "target_price", "stop_price", "reason", "bars",
               "nights", "pnl", "pnl_atr", "win", "expo", "atr_prev"]


def set_engine_defaults(**kwargs) -> Dict[str, Any]:
    unknown = set(kwargs) - set(ENGINE_DEFAULTS)
    if unknown:
        raise KeyError(f"Unknown engine default(s): {sorted(unknown)}. Valid: {sorted(ENGINE_DEFAULTS)}")
    ENGINE_DEFAULTS.update(kwargs)
    return dict(ENGINE_DEFAULTS)


def _hhmm(s: Optional[str]) -> Optional[int]:
    if s is None:
        return None
    h, m = str(s).split(":")[:2]
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------------------
# 1. DATA
# ---------------------------------------------------------------------------

def _clean_bars(df: pd.DataFrame) -> pd.DataFrame:
    out = df[~df.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    return out[out["high"] >= out["low"]]


def _load_intraday_csv(path: str, tz: str, open_t: str, close_t: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    tcol = next((c for c in ("time", "date", "datetime", "timestamp") if c in raw.columns), None)
    if tcol is None:
        raise ValueError("intraday CSV needs a time/date/datetime/timestamp column")
    t = raw[tcol]
    if pd.api.types.is_numeric_dtype(t):
        unit = "s" if float(t.abs().max()) < 1e11 else "ms"
        ts = pd.to_datetime(t, unit=unit, utc=True)
    else:
        ts = pd.to_datetime(t, utc=True)
    raw.index = pd.DatetimeIndex(ts.dt.tz_convert(tz))
    raw = raw[~raw.index.duplicated(keep="last")].sort_index()
    ses = raw.between_time(open_t, close_t, inclusive="left")
    return ses[ses.index.dayofweek < 5]


def load_data(ticker: str = "SPY", start: str = "2019-01-01",
              source: Optional[str] = None, csv_path: Optional[str] = None) -> pd.DataFrame:
    source = (source or ENGINE_DEFAULTS["data_source"]).lower()
    if source == "csv_intraday":
        path = csv_path or ENGINE_DEFAULTS["csv_path"]
        if not path:
            raise ValueError("csv_intraday needs csv_path")
        df = _load_intraday_csv(path, ENGINE_DEFAULTS["session_tz"],
                                ENGINE_DEFAULTS["session_open"],
                                ENGINE_DEFAULTS["session_close"])
        return _clean_bars(df[df.index >= pd.Timestamp(start, tz=df.index.tz)])
    elif source == "csv_daily":
        path = csv_path or ENGINE_DEFAULTS["csv_path"]
        if not path:
            raise ValueError("csv_daily needs csv_path")
        raw = pd.read_csv(path)
        raw.columns = [str(c).strip().lower() for c in raw.columns]
        tcol = next((c for c in ("time", "date", "datetime", "timestamp") if c in raw.columns), None)
        if tcol is None:
            raise ValueError("daily CSV needs a time/date/datetime/timestamp column")
        idx = pd.DatetimeIndex(pd.to_datetime(raw[tcol]))
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        raw.index = idx.normalize()
        raw.index.name = "time"
        if "volume" not in raw.columns:
            raw["volume"] = 0.0
        df = _clean_bars(raw[["open", "high", "low", "close", "volume"]])
        return df[df.index >= pd.Timestamp(start)]
    else:
        raise ValueError(f"Unknown source: {source!r}. Use 'csv_intraday' or 'csv_daily'.")


# ---------------------------------------------------------------------------
# 2. DAILY AGGREGATION FROM INTRADAY
# ---------------------------------------------------------------------------

def session_daily(intraday_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate intraday bars to session-daily OHLC + gap% + prev_close + ATR(5).

    `atr5` en la fila de la sesión t es el ATR(5) calculado con datos HASTA t-1
    (no incluye el rango de la propia sesión t), así que es usable en la apertura de t.
    """
    dkey = intraday_df.index.normalize()
    g = intraday_df.groupby(dkey)
    daily = pd.DataFrame({
        "open": g["open"].first(),
        "high": g["high"].max(),
        "low": g["low"].min(),
        "close": g["close"].last(),
        "volume": g["volume"].sum() if "volume" in intraday_df.columns else 0.0,
    })
    daily.index.name = "session_date"
    if daily.index.tz is not None:
        daily.index = daily.index.tz_localize(None)
    daily["prev_close"] = daily["close"].shift(1)
    daily["gap_pct"] = (daily["open"] / daily["prev_close"] - 1.0) * 100.0
    tr1 = daily["high"] - daily["low"]
    tr2 = (daily["high"] - daily["prev_close"]).abs()
    tr3 = (daily["low"] - daily["prev_close"]).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / 5.0, min_periods=5, adjust=False).mean()
    daily["atr5"] = atr.shift(1)          # FIX: sin look-ahead
    return daily.dropna(subset=["prev_close", "atr5"]).copy()


def prepare(intraday_df: pd.DataFrame) -> pd.DataFrame:
    return session_daily(intraday_df)


# ---------------------------------------------------------------------------
# 3. HELPERS
# ---------------------------------------------------------------------------

def _resolve_in_session(j0, direction, stop_px, target_px, use_target, o, h, l, c, slip):
    """Resuelve stop/target/EOD dentro de la sesión actual. Devuelve (jx_local, exit_px, reason)."""
    hh, ll = h[j0:], l[j0:]
    if direction == 1:
        s_hit = np.flatnonzero(ll <= stop_px)
        t_hit = np.flatnonzero(hh >= target_px) if use_target else np.array([], dtype=int)
    else:
        s_hit = np.flatnonzero(hh >= stop_px)
        t_hit = np.flatnonzero(ll <= target_px) if use_target else np.array([], dtype=int)
    i_s = int(s_hit[0]) if len(s_hit) else None
    i_t = int(t_hit[0]) if len(t_hit) else None
    if i_s is not None and (i_t is None or i_s <= i_t):
        jx = j0 + i_s
        raw = min(float(o[jx]), stop_px) if direction == 1 else max(float(o[jx]), stop_px)
        return jx, raw * (1.0 - slip * direction), "stop"
    if i_t is not None:
        jx = j0 + i_t
        return jx, target_px * (1.0 - slip * direction), "target"
    jx = len(c) - 1
    return jx, float(c[jx]) * (1.0 - slip * direction), "eod"


def _walk_forward_hold(k, direction, entry_px, stop_px, target_px, tf_hold_days,
                       O, H, L, C, starts, ends, slip):
    """Extiende un trade TF a sesiones siguientes mientras el cierre quede a favor.
    Devuelve (exit_global_idx, exit_px, reason) o None si no se puede extender."""
    last_exit_global = None
    for extra_day in range(1, tf_hold_days + 1):
        next_k = k + extra_day
        if next_k >= len(starts):
            break
        s_next, e_next = int(starts[next_k]), int(ends[next_k])
        if e_next - s_next < 2:
            break
        next_o = float(O[s_next])
        if (direction == 1 and next_o <= stop_px) or (direction == -1 and next_o >= stop_px):
            return s_next, next_o * (1.0 - slip * direction), "stop_gap"
        hh_n, ll_n = H[s_next:e_next], L[s_next:e_next]
        if direction == 1:
            s_hit = np.flatnonzero(ll_n <= stop_px)
            t_hit = np.flatnonzero(hh_n >= target_px)
        else:
            s_hit = np.flatnonzero(hh_n >= stop_px)
            t_hit = np.flatnonzero(ll_n <= target_px)
        i_s = int(s_hit[0]) if len(s_hit) else None
        i_t = int(t_hit[0]) if len(t_hit) else None
        if i_s is not None and (i_t is None or i_s <= i_t):
            jx = s_next + i_s
            raw = min(float(O[jx]), stop_px) if direction == 1 else max(float(O[jx]), stop_px)
            return jx, raw * (1.0 - slip * direction), "stop"
        if i_t is not None:
            jx = s_next + i_t
            return jx, target_px * (1.0 - slip * direction), "target"
        close_n = float(C[e_next - 1])
        if direction * (close_n - entry_px) <= 0:
            return e_next - 1, close_n * (1.0 - slip * direction), "eod_unfavorable"
        last_exit_global = e_next - 1
    if last_exit_global is not None:
        return last_exit_global, float(C[last_exit_global]) * (1.0 - slip * direction), "max_hold"
    return None


# ---------------------------------------------------------------------------
# 4. BACKTEST
# ---------------------------------------------------------------------------

def run_gap_backtest(
    intraday_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    gap_min_trade: float = 0.5,
    gap_threshold: float = 1.0,
    gap_max_tf: float = 4.0,
    entry_tf_min: int = 15,
    mr_fill_target: float = 0.75,
    tf_target_mult: float = 1.5,
    mr_stop_atr_mult: float = 1.0,
    tf_stop_atr_mult: float = 1.25,
    time_exit: Literal["eod", "target_or_eod"] = "target_or_eod",
    skip_fridays: bool = True,
    slip_bps_per_side: float = 5.0,
    entry_window_start: Optional[str] = "09:40",
    entry_window_end: Optional[str] = "11:00",
    financing_bps_per_night: Optional[float] = None,
    risk_per_trade_pct: Optional[float] = None,
    max_exposure: Optional[float] = None,
    tf_hold_days: int = 0,
    bad_dates: Optional[Iterable[Any]] = None,
) -> pd.DataFrame:
    """time_exit:
        "eod"           -> stop + salida al cierre (SIN objetivo)
        "target_or_eod" -> stop + objetivo + salida al cierre
    tf_hold_days: 0 = intradía; 1-3 = hold si cierre favorable (TF only)
    bad_dates: fechas (o DatetimeIndex) con noticias contaminantes a saltar.
    """
    if time_exit not in TIME_EXIT_MODES:
        raise ValueError(f"time_exit must be one of {TIME_EXIT_MODES}, got {time_exit!r}")
    use_target = time_exit == "target_or_eod"

    fin_bps = ENGINE_DEFAULTS["financing_bps_per_night"] if financing_bps_per_night is None else financing_bps_per_night
    risk_pct = ENGINE_DEFAULTS["risk_per_trade_pct"] if risk_per_trade_pct is None else risk_per_trade_pct
    expo_cap = ENGINE_DEFAULTS["max_exposure"] if max_exposure is None else max_exposure

    slip = slip_bps_per_side / 10_000.0
    fin = fin_bps / 10_000.0
    w_start, w_end = _hhmm(entry_window_start), _hhmm(entry_window_end)
    open_min = _hhmm(ENGINE_DEFAULTS["session_open"])

    n = len(intraday_df)
    if n < 2 or len(daily_df) == 0:
        return pd.DataFrame(columns=_TRADE_COLS)

    idx = intraday_df.index
    O = intraday_df["open"].to_numpy(float)
    H = intraday_df["high"].to_numpy(float)
    L = intraday_df["low"].to_numpy(float)
    C = intraday_df["close"].to_numpy(float)
    t_ns = idx.values.astype("datetime64[ns]").astype("int64")
    tod = (idx.hour * 60 + idx.minute).to_numpy()

    dnorm = idx.normalize()
    if dnorm.tz is not None:
        dnorm = dnorm.tz_localize(None)
    dvals = dnorm.values.astype("datetime64[ns]")
    usess, starts = np.unique(dvals, return_index=True)
    ends = np.r_[starts[1:], n]

    same = dvals[1:] == dvals[:-1]
    diffs = np.diff(t_ns)[same]
    step_min = max(int(round(float(np.median(diffs)) / 6e10)), 1) if len(diffs) else 1
    tf = max(int(entry_tf_min), step_min)
    if tf % step_min:
        raise ValueError(f"entry_tf_min={entry_tf_min} no es múltiplo de la barra nativa ({step_min} min)")
    tf_ns = tf * 60_000_000_000

    sess_idx = pd.DatetimeIndex(usess)
    dd = daily_df.reindex(sess_idx)
    gaps = dd["gap_pct"].to_numpy(float)
    s_open = dd["open"].to_numpy(float)
    prevc = dd["prev_close"].to_numpy(float)
    atrs = dd["atr5"].to_numpy(float)
    dow = sess_idx.dayofweek.to_numpy()

    ok = np.isfinite(gaps) & np.isfinite(atrs) & np.isfinite(prevc) \
         & (np.abs(gaps) >= gap_min_trade) & (np.abs(gaps) <= gap_max_tf)
    if skip_fridays:
        ok &= dow != 4
    if bad_dates is not None:
        bad_arr = pd.to_datetime(list(bad_dates)).normalize().values.astype("datetime64[ns]")
        ok &= ~np.isin(usess, bad_arr)

    trades: List[Dict[str, Any]] = []
    for k in np.flatnonzero(ok):
        s, e = int(starts[k]), int(ends[k])
        if e - s < 2 or tod[s] != open_min:
            continue
        gap = float(gaps[k]); gap_abs = abs(gap); atr_prev = float(atrs[k])
        if atr_prev <= 0:
            continue

        if gap_abs < gap_threshold:
            strategy, direction = "MR", (-1 if gap > 0 else 1)
        else:
            strategy, direction = "TF", (1 if gap > 0 else -1)

        o, h, l, c, tt, ts = O[s:e], H[s:e], L[s:e], C[s:e], tod[s:e], t_ns[s:e]

        # barras de confirmación
        if tf > step_min:
            rel = (ts - ts[0]) // tf_ns
            b0 = np.r_[0, np.flatnonzero(np.diff(rel)) + 1]
            th = np.maximum.reduceat(h, b0)
            tl = np.minimum.reduceat(l, b0)
            tc = c[np.r_[b0[1:] - 1, len(c) - 1]]
        else:
            b0, th, tl, tc = np.arange(len(c)), h, l, c

        level = th[0] if direction == 1 else tl[0]
        j0 = None
        for q in range(1, len(b0) - 1):
            hit = tc[q] > level if direction == 1 else tc[q] < level
            if not hit:
                continue
            cand = int(b0[q + 1])
            m = tt[cand]
            if w_start is not None and m < w_start:
                continue
            if w_end is not None and m > w_end:
                break
            j0 = cand
            break
        if j0 is None:
            continue

        entry_px = float(o[j0]) * (1.0 + slip * direction)
        gap_dist = abs(float(s_open[k]) - float(prevc[k]))

        if strategy == "MR":
            target_px = float(s_open[k]) + direction * mr_fill_target * gap_dist
            stop_dist = mr_stop_atr_mult * atr_prev
        else:
            target_px = entry_px + direction * tf_target_mult * gap_dist
            stop_dist = tf_stop_atr_mult * atr_prev
        stop_px = entry_px - direction * stop_dist

        if use_target and direction * (target_px - entry_px) <= 0:
            continue

        # resolución intradía
        jx_local, exit_px, reason = _resolve_in_session(
            j0, direction, stop_px, target_px, use_target, o, h, l, c, slip
        )
        jx_global = s + jx_local

        # extensión a sesiones siguientes (TF + tf_hold_days)
        if strategy == "TF" and tf_hold_days > 0 and reason == "eod":
            close_session = float(c[-1])
            if direction * (close_session - entry_px) > 0:
                ext = _walk_forward_hold(
                    k, direction, entry_px, stop_px, target_px, tf_hold_days,
                    O, H, L, C, starts, ends, slip
                )
                if ext is not None:
                    jx_global, exit_px, reason = ext

        entry_time = idx[s + j0]
        exit_time = idx[jx_global]
        nights = int((exit_time.date() - entry_time.date()).days)
        exit_px *= (1.0 - direction * fin * nights)

        pnl = direction * (exit_px / entry_px - 1.0) * 100.0
        # FIX #1: expo usa stop_dist real de cada estrategia
        expo = min(expo_cap, (risk_pct / 100.0) * entry_px / stop_dist)

        trades.append({
            "session_date": pd.Timestamp(usess[k]),
            "entry_time": entry_time,
            "exit_time": exit_time,
            "direction": "long" if direction == 1 else "short",
            "strategy": strategy,
            "gap_pct": gap,
            "entry_price": entry_px,
            "exit_price": exit_px,
            "target_price": target_px if use_target else np.nan,
            "stop_price": stop_px,
            "reason": reason,
            "bars": int(jx_global - (s + j0) + 1),
            "nights": nights,
            "pnl": pnl,
            "pnl_atr": pnl * expo,
            "win": pnl > 0.0,
            "expo": expo,
            "atr_prev": atr_prev,
        })

    return pd.DataFrame(trades, columns=_TRADE_COLS)


# ---------------------------------------------------------------------------
# 5. DAILY RETURNS
# ---------------------------------------------------------------------------

def daily_returns(daily_df: pd.DataFrame, trades: pd.DataFrame,
                  sizing: Literal["capital", "atr"] = "capital") -> pd.Series:
    r = np.zeros(len(daily_df), dtype=float)
    if len(trades) == 0:
        return pd.Series(r, index=daily_df.index, name="daily_return")
    for _, t in trades.iterrows():
        exit_d = pd.Timestamp(t["exit_time"])
        exit_d = exit_d.tz_localize(None) if exit_d.tz is not None else exit_d
        exit_d = exit_d.normalize()
        if exit_d in daily_df.index:
            k = daily_df.index.get_loc(exit_d)
            scale = 1.0 if sizing == "capital" else float(t["expo"])
            r[k] += (t["pnl"] / 100.0) * scale
    return pd.Series(r, index=daily_df.index, name="daily_return")


def trade_mtm_paths(daily_df: pd.DataFrame, trades: pd.DataFrame,
                    sizing: Literal["capital", "atr"] = "capital") -> List[np.ndarray]:
    """Single-day trades: MTM path is a one-element array with the exit-day return."""
    paths = []
    for _, t in trades.iterrows():
        scale = 1.0 if sizing == "capital" else float(t["expo"])
        paths.append(np.array([(t["pnl"] / 100.0) * scale]))
    return paths


# ---------------------------------------------------------------------------
# 6. WALK-FORWARD
# ---------------------------------------------------------------------------

def walk_forward_fixed(daily_df: pd.DataFrame, intraday_df: pd.DataFrame,
                       rules: Optional[Dict[str, Any]] = None,
                       is_years: int = 3,
                       oos_start: Optional[str] = None) -> pd.DataFrame:
    """Rolling 1-year OOS walk-forward. `oos_start` filtra los años OOS a evaluar."""
    params = {**DEFAULT_RULES, **(rules or {})}
    years = sorted(set(daily_df.index.year))
    rows = []

    intraday_dates = intraday_df.index.normalize().tz_localize(None) if intraday_df.index.tz is not None \
                     else intraday_df.index.normalize()
    intraday_years = intraday_dates.year

    oos_year_floor = pd.Timestamp(oos_start).year if oos_start is not None else None

    for y in years:
        if y - is_years < years[0]:
            continue
        if oos_year_floor is not None and y < oos_year_floor:
            continue
        if y == years[-1] and daily_df.index[-1].month < 12:
            continue

        d_is = daily_df[(daily_df.index.year >= y - is_years) & (daily_df.index.year < y)]
        d_oos = daily_df[daily_df.index.year == y]
        i_is = intraday_df[(intraday_years >= y - is_years) & (intraday_years < y)]
        i_oos = intraday_df[intraday_years == y]

        if len(d_is) < 100 or len(d_oos) < 30:
            continue

        ti = run_gap_backtest(i_is, d_is, **params)
        to = run_gap_backtest(i_oos, d_oos, **params)

        ri_tot = (np.prod(1.0 + ti["pnl"] / 100.0) - 1.0) if len(ti) > 0 else 0.0
        ro_tot = (np.prod(1.0 + to["pnl"] / 100.0) - 1.0) if len(to) > 0 else 0.0

        if len(to) > 0:
            p = to["pnl"].values
            g = p[p > 0].sum(); l = -p[p < 0].sum()
            pf = float(g / l) if l > 0 else np.inf
            eq = (1.0 + daily_returns(d_oos, to, "capital")).cumprod().values
            pk = np.maximum.accumulate(eq)
            mdd = float(((eq - pk) / pk).min())
        else:
            pf = np.nan; mdd = 0.0

        rows.append({
            "year": y,
            "ret_is_anual": ri_tot / is_years,
            "ret_oos": ro_tot,
            "n_oos": len(to),
            "pf_oos": pf,
            "mdd_oos": mdd,
        })
    return pd.DataFrame(rows)