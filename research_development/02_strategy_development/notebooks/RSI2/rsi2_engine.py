"""RSI(2) mean-reversion engine (daily bars). Data: Yahoo (indices/ETFs) or broker intraday CSV (CFDs)."""

from __future__ import annotations

import numpy as np
import pandas as pd
try:
    import yfinance as yf
except ImportError:
    yf = None
from typing import Optional, Literal, Dict, Any, List


# Frozen rules used when no explicit rules are given to walk_forward_fixed().
DEFAULT_RULES: Dict[str, Any] = {
    "rsi_thr": 15.0,
    "sma_len": 200,
    "exit_mode": "2green",
    "slip_bps_per_side": 5.0,
}

# Set ONCE per notebook from the variant YAML: set_engine_defaults(**cfg["engine_defaults"]).
# Unknown keys raise KeyError.
ENGINE_DEFAULTS: Dict[str, Any] = {
    "financing_bps_per_night": 0.0,   # CFD swap on longs: bps of notional per CALENDAR night held
    "risk_per_trade_pct": 1.0,        # ATR sizing: % of equity risked per trade
    "atr_stop_mult": 2.0,             # ATR sizing: virtual stop distance, in ATRs
    "max_exposure": 1.0,              # ATR sizing: exposure cap (1.0 = 100% of equity)
    "data_source": "yahoo",           # "yahoo" | "csv_intraday"
    "csv_path": None,                 # intraday export (M1/M5/M15/M30), timestamps in UTC
    "session_tz": "America/New_York",
    "session_open": "09:30",
    "session_close": "16:00",
}


def set_engine_defaults(**kwargs) -> Dict[str, Any]:
    unknown = set(kwargs) - set(ENGINE_DEFAULTS)
    if unknown:
        raise KeyError(f"Unknown engine default(s): {sorted(unknown)}. Valid: {sorted(ENGINE_DEFAULTS)}")
    ENGINE_DEFAULTS.update(kwargs)
    return dict(ENGINE_DEFAULTS)


# ---------------------------------------------------------------------------
# 1. DATA
# ---------------------------------------------------------------------------

def _clean_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Sort, de-duplicate and drop rows with missing / non-positive OHLC."""
    out = df[~df.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    return out[out["high"] > out["low"]]


def _build_session_daily(path: str, tz: str, open_t: str, close_t: str,
                         calendar: Optional[str] = "NYSE") -> pd.DataFrame:
    """Daily bars of the regular session from an intraday CSV (UTC timestamps).
    open = first bar starting >= open_t, close = last bar starting < close_t (local time of `tz`).
    Only NYSE trading days. Use M1/M5/M15/M30 (H1 does not align with 09:30)."""
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    tcol = next((c for c in ("time", "date", "datetime", "timestamp") if c in raw.columns), None)
    if tcol is None:
        raise ValueError("intraday CSV needs a time/date/datetime/timestamp column")
    t = raw[tcol]
    ts = (pd.to_datetime(t, unit="ms", utc=True) if pd.api.types.is_numeric_dtype(t)
          else pd.to_datetime(t, utc=True))
    raw.index = pd.DatetimeIndex(ts.dt.tz_convert(tz))
    raw = raw[~raw.index.duplicated(keep="last")].sort_index()

    ses = raw.between_time(open_t, close_t, inclusive="left")
    ses = ses[ses.index.dayofweek < 5]
    dkey = ses.index.tz_localize(None).normalize()
    first_t = ses.index.to_series().groupby(dkey).first().dt.strftime("%H:%M")
    if (first_t != open_t).mean() > 0.5:
        raise ValueError(f"First session bar usually starts at {first_t.mode().iat[0]}, not {open_t}: "
                        f"the CSV timeframe does not align with the session open (use M30 or finer).")
    n_bars = ses.groupby(dkey).size()
    short = n_bars[n_bars < 0.8 * n_bars.median()]
    if len(short):
        print(f"WARNING: {len(short)} sessions with <80% of the median bar count (truncated?): "
            f"{[d.strftime('%Y-%m-%d') for d in short.index[:10]]}...")
    g = ses.groupby(ses.index.tz_localize(None).normalize())
    out = pd.DataFrame({
        "open": g["open"].first(),
        "high": g["high"].max(),
        "low": g["low"].min(),
        "close": g["close"].last(),
        "volume": g["volume"].sum() if "volume" in ses.columns else 0.0,
    })
    out.index.name = "time"

    if calendar:
        import pandas_market_calendars as mcal
        days = mcal.get_calendar(calendar).valid_days(out.index.min(), out.index.max()).tz_localize(None)
        out = out[out.index.isin(days.normalize())]
    return out


def load_data(ticker: str = "QQQ", start: str = "1999-01-01", drop_partial_bar: bool = True,
              source: Optional[str] = None, csv_path: Optional[str] = None) -> pd.DataFrame:
    """
    Daily bars indexed by 'time' with lowercase columns open/high/low/close/volume.

    source (None -> ENGINE_DEFAULTS["data_source"]):
      "yahoo"        : download `ticker` from Yahoo Finance (auto-adjusted).
      "csv_intraday" : build session-aligned daily bars from the broker's intraday CSV
                       (csv_path / session_* in ENGINE_DEFAULTS). `ticker` is then only a label.
    drop_partial_bar: drop the last bar if it is today's New York session and has not closed (16:00 NY).
    """
    source = (source or ENGINE_DEFAULTS["data_source"]).lower()

    if source == "yahoo":
        df_raw = yf.download(ticker, start=start, auto_adjust=True, progress=False)
        if isinstance(df_raw.columns, pd.MultiIndex):
            df_raw.columns = df_raw.columns.get_level_values(0)
        df_raw.columns = [str(c).lower() for c in df_raw.columns]
        df = df_raw[["open", "high", "low", "close", "volume"]].copy()
        df.index.name = "time"
        df.index = pd.to_datetime(df.index)

    elif source == "csv_intraday":
        path = csv_path or ENGINE_DEFAULTS["csv_path"]
        if not path:
            raise ValueError("source 'csv_intraday' needs csv_path (engine_defaults.csv_path in the variant YAML)")
        df = _build_session_daily(str(path), ENGINE_DEFAULTS["session_tz"],
                                  ENGINE_DEFAULTS["session_open"], ENGINE_DEFAULTS["session_close"])
        df = _clean_bars(df[df.index >= pd.Timestamp(start)])

    else:
        raise ValueError(f"Unknown data source: {source!r} (use 'yahoo' or 'csv_intraday')")

    if drop_partial_bar and len(df) > 0:
        now_ny = pd.Timestamp.now(tz="America/New_York")
        if pd.Timestamp(df.index[-1]).date() == now_ny.date() and now_ny.time() < pd.Timestamp("16:00").time():
            df = df.iloc[:-1].copy()
    return df


def load_qqq(start: str = "1999-01-01", drop_partial_bar: bool = True) -> pd.DataFrame:
    """Backward-compatible wrapper: QQQ daily bars from Yahoo."""
    return load_data("QQQ", start=start, drop_partial_bar=drop_partial_bar, source="yahoo")


# ---------------------------------------------------------------------------
# 2. INDICATORS
# ---------------------------------------------------------------------------

def rsi_wilder(series: pd.Series, period: int = 2) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def prepare(df: pd.DataFrame, sma_len: int = 200) -> pd.DataFrame:
    out = df.copy()
    out["sma"] = out["close"].rolling(window=sma_len).mean()
    out["rsi2"] = rsi_wilder(out["close"], period=2)
    out["green"] = (out["close"] > out["open"]).astype(int)
    out["ma5"] = out["close"].rolling(window=5).mean()

    # Wilder ATR(14)
    tr1 = out["high"] - out["low"]
    tr2 = (out["high"] - out["close"].shift(1)).abs()
    tr3 = (out["low"] - out["close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["atr14"] = tr.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean()

    return out.dropna(subset=["sma", "rsi2", "atr14"]).copy()


# ---------------------------------------------------------------------------
# 3. BACKTEST
# ---------------------------------------------------------------------------

def run_rsi2_backtest(
    df: pd.DataFrame,
    rsi_thr: float = 15.0,
    sma_len: int = 200,
    exit_mode: Literal["2green", "ma5", "rsi70"] = "2green",
    slip_bps_per_side: float = 5.0,
    strict_post_entry_2green: bool = False,
    financing_bps_per_night: Optional[float] = None,
    risk_per_trade_pct: Optional[float] = None,
    atr_stop_mult: Optional[float] = None,
    max_exposure: Optional[float] = None,
) -> pd.DataFrame:
    """
    RSI(2) mean-reversion on daily bars, lookahead-free.
      Entry: at close of day i-1, rsi2[i-1] < rsi_thr AND close[i-1] > sma[i-1] -> buy at open[i] * (1 + slip).
      Exit (evaluated at close of i-1): '2green' (two green candles) | 'ma5' (close > MA5) | 'rsi70' (rsi2 > 70)
             -> sell at open[i] * (1 - slip) * (1 - fin * nights).
      Open position at the end: marked at the last close, reason='open_at_end'.

    i_ent / i_sal are positional indices into the DataFrame passed here: pass the SAME DataFrame to daily_returns().
    financing_bps_per_night: CFD swap per CALENDAR night held (None -> ENGINE_DEFAULTS).
    risk_per_trade_pct / atr_stop_mult / max_exposure: ATR sizing (None -> ENGINE_DEFAULTS).

    Returns columns: entry_time, exit_time, entry_price, exit_price, type, reason, bars, rsi_signal,
                     pnl, pnl_atr, win, i_ent, i_sal, expo, nights
    """
    fin_bps = ENGINE_DEFAULTS["financing_bps_per_night"] if financing_bps_per_night is None else financing_bps_per_night
    risk_pct = ENGINE_DEFAULTS["risk_per_trade_pct"] if risk_per_trade_pct is None else risk_per_trade_pct
    stop_mult = ENGINE_DEFAULTS["atr_stop_mult"] if atr_stop_mult is None else atr_stop_mult
    expo_cap = ENGINE_DEFAULTS["max_exposure"] if max_exposure is None else max_exposure

    # Auto-prepare only if columns are missing. A prepared DataFrame is never modified, so i_ent / i_sal
    # stay aligned with the caller's DataFrame.
    if "sma" not in df.columns or "rsi2" not in df.columns or "atr14" not in df.columns:
        df = prepare(df, sma_len=sma_len)
    elif len(df) >= sma_len:
        expected_sma = float(df["close"].iloc[:sma_len].mean())
        got_sma = float(df["sma"].iloc[sma_len - 1])
        assert np.isclose(got_sma, expected_sma, rtol=1e-6), (
            f"sma_len={sma_len} does not match the SMA column of the prepared DataFrame "
            f"(expected {expected_sma:.6f}, found {got_sma:.6f}). Prepare it with prepare(df, sma_len={sma_len})."
        )

    slip = slip_bps_per_side / 10_000.0
    fin = fin_bps / 10_000.0

    opens = df["open"].values
    closes = df["close"].values
    smas = df["sma"].values
    rsis = df["rsi2"].values
    greens = df["green"].values
    ma5s = df["ma5"].values
    atrs = df["atr14"].values
    idx = df.index

    trades = []
    in_pos = False
    ei = 0
    ep = 0.0
    expo_atr = 1.0

    def _trade(i_exit: int, xp: float, reason: str, bars: int, nights: int) -> dict:
        ret_pct = (xp / ep - 1.0) * 100.0
        return {
            "entry_time": idx[ei], "exit_time": idx[i_exit],
            "entry_price": ep, "exit_price": xp, "type": "long", "reason": reason,
            "bars": bars, "rsi_signal": rsis[ei - 1],
            "pnl": ret_pct, "pnl_atr": ret_pct * expo_atr, "win": ret_pct > 0.0,
            "i_ent": ei, "i_sal": i_exit, "expo": expo_atr, "nights": nights,
        }

    for i in range(2, len(df)):
        if not in_pos:
            if rsis[i - 1] < rsi_thr and closes[i - 1] > smas[i - 1]:
                ep = opens[i] * (1.0 + slip)
                ei = i
                # exposure = (risk%/100) * ep / (stop_mult * ATR[i-1]), capped
                expo_atr = min(expo_cap, ((risk_pct / 100.0) * ep) / (stop_mult * atrs[i - 1]))
                in_pos = True
        else:
            if exit_mode == "2green":
                exit_signal = (greens[i - 1] == 1) and (greens[i - 2] == 1)
                if strict_post_entry_2green and (i - 2) < ei:
                    exit_signal = False
            elif exit_mode == "ma5":
                exit_signal = closes[i - 1] > ma5s[i - 1]
            elif exit_mode == "rsi70":
                exit_signal = rsis[i - 1] > 70.0
            else:
                raise ValueError(f"Unknown exit_mode: {exit_mode}")

            if exit_signal:
                nights = int((idx[i] - idx[ei]).days)
                xp = opens[i] * (1.0 - slip) * (1.0 - fin * nights)
                trades.append(_trade(i, xp, exit_mode, i - ei, nights))
                in_pos = False

    if in_pos:  # mark the open position at the last close
        nights = int((idx[-1] - idx[ei]).days)
        xp = closes[-1] * (1.0 - slip) * (1.0 - fin * nights)
        trades.append(_trade(len(df) - 1, xp, "open_at_end", len(df) - 1 - ei, nights))

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# 4. DAILY MARK-TO-MARKET RETURNS
# ---------------------------------------------------------------------------

def _trade_path(closes: np.ndarray, t, sizing: str) -> np.ndarray:
    """
    Daily MTM return path of ONE trade, from i_ent to i_sal. Equity on day k is 1 + expo * (P_k / ep - 1),
    with P_k the close (entry and holding days) and the exit price (open - slip - financing) on the exit day.
    The compounded path equals 1 + expo * (xp / ep - 1) exactly. sizing='capital' -> expo = 1.
    `expo` is already capped by max_exposure when the trade is created (may be > 1 if leverage is allowed).
    """
    expo = 1.0 if sizing == "capital" else float(t["expo"])
    i_ent = int(t["i_ent"])
    i_sal = int(t["i_sal"])
    ep = float(t["entry_price"])
    xp = float(t["exit_price"])

    prices = np.empty(i_sal - i_ent + 1, dtype=float)
    prices[0] = closes[i_ent]
    prices[1:] = closes[i_ent + 1:i_sal + 1]
    prices[-1] = xp

    equity = 1.0 + expo * (prices / ep - 1.0)
    prev = np.concatenate(([1.0], equity[:-1]))
    return equity / prev - 1.0


def trade_mtm_paths(df: pd.DataFrame, trades: pd.DataFrame,
                    sizing: Literal["capital", "atr"] = "capital") -> List[np.ndarray]:
    closes = df["close"].values
    return [_trade_path(closes, t, sizing) for _, t in trades.iterrows()]


def daily_returns(df: pd.DataFrame, trades: pd.DataFrame,
                  sizing: Literal["capital", "atr"] = "capital") -> pd.Series:
    r = np.zeros(len(df), dtype=float)
    closes = df["close"].values
    for _, t in trades.iterrows():
        r[int(t["i_ent"]):int(t["i_sal"]) + 1] = _trade_path(closes, t, sizing)
    return pd.Series(r, index=df.index, name="daily_return")


def intraday_drawdown(df: pd.DataFrame, trades: pd.DataFrame,
                      sizing: Literal["capital", "atr"] = "atr") -> Dict[str, float]:
    """
    Max drawdown on daily closes vs a more conservative one that also marks every holding day at its LOW
    (prop-style loss limits are checked on unrealized P&L in real time). The exit day is not marked at its low.
    Returns {"max_dd_close": ..., "max_dd_intraday": ...} (negative fractions, intraday <= close).
    """
    r = daily_returns(df, trades, sizing=sizing).values
    eq_close = np.concatenate([[1.0], np.cumprod(1.0 + r)])        # eq_close[k+1] = equity at close of day k
    peak_close = np.maximum.accumulate(eq_close)
    dd_close = float(((eq_close - peak_close) / peak_close).min())

    lows = df["low"].values
    worst = dd_close
    for _, t in trades.iterrows():
        expo = 1.0 if sizing == "capital" else float(t["expo"])
        i_ent, i_sal = int(t["i_ent"]), int(t["i_sal"])
        ep = float(t["entry_price"])
        e_start = eq_close[i_ent]                                    # equity at close of day i_ent - 1
        for k in range(i_ent, i_sal):
            trough = e_start * (1.0 + expo * (lows[k] / ep - 1.0))
            worst = min(worst, trough / peak_close[k] - 1.0)
    return {"max_dd_close": dd_close, "max_dd_intraday": float(worst)}


# ---------------------------------------------------------------------------
# 5. LIVE SIZING (CFD / MT4-MT5)
# ---------------------------------------------------------------------------

def position_size_lots(equity: float, price: float, atr: float,
                       contract_size: float = 1.0, lot_step: float = 0.01, min_lot: float = 0.01,
                       max_lot: Optional[float] = None, max_leverage: Optional[float] = None,
                       risk_per_trade_pct: Optional[float] = None, atr_stop_mult: Optional[float] = None,
                       max_exposure: Optional[float] = None) -> Dict[str, float]:
    """
    Same ATR risk sizing as the backtest, converted to lots.
      exposure = min(max_exposure, (risk_pct/100) * price / (atr_stop_mult * atr))
      lots     = floor(equity * exposure / (price * contract_size) / lot_step) * lot_step
    contract_size: units of the underlying per 1.0 lot (symbol specification). max_leverage caps the notional.
    lots = 0.0 means "below min_lot: do not trade".
    """
    risk_pct = ENGINE_DEFAULTS["risk_per_trade_pct"] if risk_per_trade_pct is None else risk_per_trade_pct
    stop_mult = ENGINE_DEFAULTS["atr_stop_mult"] if atr_stop_mult is None else atr_stop_mult
    cap = ENGINE_DEFAULTS["max_exposure"] if max_exposure is None else max_exposure
    if min(equity, price, atr, contract_size, lot_step) <= 0:
        raise ValueError("equity, price, atr, contract_size and lot_step must be > 0")

    expo = min(cap, ((risk_pct / 100.0) * price) / (stop_mult * atr))
    if max_leverage is not None:
        expo = min(expo, float(max_leverage))
    lots = np.floor(equity * expo / (price * contract_size) / lot_step + 1e-9) * lot_step
    if max_lot is not None:
        lots = min(lots, max_lot)
    if lots < min_lot:
        lots = 0.0
    lots = round(float(lots), 8)
    notional = lots * contract_size * price
    return {
        "lots": lots,
        "exposure": notional / equity,
        "notional": notional,
        "margin": (notional / max_leverage) if max_leverage else float("nan"),
        "risk_pct_effective": 100.0 * (notional / equity) * (stop_mult * atr) / price,
    }


# ---------------------------------------------------------------------------
# 6. FIXED-RULES WALK-FORWARD
# ---------------------------------------------------------------------------

def walk_forward_fixed(df: pd.DataFrame, rules: Optional[Dict[str, Any]] = None,
                       is_years: int = 3) -> pd.DataFrame:
    params = {**DEFAULT_RULES, **(rules or {})}
    years = sorted(set(df.index.year))
    rows = []

    for y in years:
        if y - is_years < years[0]:
            continue
        if y == years[-1] and df.index[-1].month < 12:   # skip incomplete current year
            continue

        d_is = df[(df.index.year >= y - is_years) & (df.index.year < y)]
        d_oos = df[df.index.year == y]
        if len(d_is) < 600 or len(d_oos) < 200:
            continue

        ti = run_rsi2_backtest(d_is, **params)
        to = run_rsi2_backtest(d_oos, **params)

        ri_tot = (np.prod(1.0 + ti["pnl"] / 100.0) - 1.0) if len(ti) > 0 else 0.0
        ro_tot = (np.prod(1.0 + to["pnl"] / 100.0) - 1.0) if len(to) > 0 else 0.0

        if len(to) > 0:
            p = to["pnl"].values
            g = p[p > 0].sum()
            l = -p[p < 0].sum()
            pf_oos = float(g / l) if l > 0 else np.inf
            eq = (1.0 + daily_returns(d_oos, to, sizing="capital")).cumprod().values
            pk = np.maximum.accumulate(eq)
            mdd_oos = float(((eq - pk) / pk).min())
        else:
            pf_oos = np.nan
            mdd_oos = 0.0

        rows.append({
            "year": y,
            "ret_is_anual": ri_tot / float(is_years),
            "ret_oos": ro_tot,
            "n_oos": len(to),
            "pf_oos": pf_oos,
            "mdd_oos": mdd_oos,
        })

    return pd.DataFrame(rows)