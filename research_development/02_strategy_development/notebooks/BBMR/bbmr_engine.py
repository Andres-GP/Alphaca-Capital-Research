"""BBMR — Bollinger Band Mean Reversion with ADX Regime Filter (daily bars).

Edge (reemplaza al RSI(2) de Connors):
  - Filtro de régimen:  ADX(14) < adx_thr  -> mercado en rango, no tendencial.
  - Filtro de tendencia: close > SMA(sma_len) -> solo largos en tendencia alcista de fondo.
  - Entrada (lookahead-free): en el cierre de la barra i-1
        low[i-1] <= bb_lower[i-1]                     (toque de banda inferior)
        AND adx[i-1] < adx_thr                        (régimen de rango)
        AND close[i-1] > sma[i-1]                     (filtro de tendencia)
        AND (close[i-1]-low[i-1])/(high[i-1]-low[i-1]) >= rejection_ratio  (vela de rechazo)
    -> compra en open[i] * (1 + slip).
  - Stop real:   atr_stop_mult * ATR(14)[i-1]  por debajo del precio de entrada.
                 Se evalúa intrabar (low[i] <= stop_price) y se ejecuta en min(open, stop) * (1 - slip).
                 También dimensiona la posición (el "virtual stop" del motor original ahora es un stop REAL).
  - Objetivo:    close[i-1] >= bb_mid[i-1]  -> salida en open[i] * (1 - slip).
  - Stop tiempo: (i - i_ent) >= max_bars    -> salida en open[i] * (1 - slip).

Datos: Yahoo (índices/ETFs) o CSV intraday/diario del broker. Misma API de data que el motor RSI(2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
try:
    import yfinance as yf
except ImportError:
    yf = None
from typing import Optional, Literal, Dict, Any, List


# ---------------------------------------------------------------------------
# Reglas congeladas para walk_forward_fixed()
# ---------------------------------------------------------------------------
DEFAULT_RULES: Dict[str, Any] = {
    "bb_len": 20,
    "bb_std": 2.0,
    "adx_thr": 25.0,
    "sma_len": 200,
    "rejection_ratio": 0.5,   # 0.0 = desactiva el filtro de vela de rechazo
    "max_bars": 15,
    "atr_stop_mult": 2.0,     # stop REAL + sizing
    "slip_bps_per_side": 5.0,
}

# Defaults del motor (idénticos al original; atr_stop_mult se hereda si no se pasa)
ENGINE_DEFAULTS: Dict[str, Any] = {
    "financing_bps_per_night": 0.0,
    "risk_per_trade_pct": 1.0,
    "atr_stop_mult": 2.0,
    "max_exposure": 1.0,
    "data_source": "yahoo",
    "csv_path": None,
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
# 1. DATA (sin cambios)
# ---------------------------------------------------------------------------
def _clean_bars(df: pd.DataFrame) -> pd.DataFrame:
    out = df[~df.index.duplicated(keep="last")].sort_index()
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    return out[out["high"] > out["low"]]


def _build_session_daily(path: str, tz: str, open_t: str, close_t: str,
                         calendar: Optional[str] = "NYSE") -> pd.DataFrame:
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
        print(f"WARNING: {len(short)} sessions with <80% of median bar count: "
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
            raise ValueError("source 'csv_intraday' needs csv_path")
        df = _build_session_daily(str(path), ENGINE_DEFAULTS["session_tz"],
                                  ENGINE_DEFAULTS["session_open"], ENGINE_DEFAULTS["session_close"])
        df = _clean_bars(df[df.index >= pd.Timestamp(start)])
    elif source == "csv_daily":
        path = csv_path or ENGINE_DEFAULTS["csv_path"]
        if not path:
            raise ValueError("source 'csv_daily' needs csv_path")
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
        df = df[df.index >= pd.Timestamp(start)]
    else:
        raise ValueError(f"Unknown data source: {source!r}")

    if drop_partial_bar and len(df) > 0:
        now_ny = pd.Timestamp.now(tz="America/New_York")
        if pd.Timestamp(df.index[-1]).date() == now_ny.date() and now_ny.time() < pd.Timestamp("16:00").time():
            df = df.iloc[:-1].copy()
    return df


def load_qqq(start: str = "1999-01-01", drop_partial_bar: bool = True) -> pd.DataFrame:
    return load_data("QQQ", start=start, drop_partial_bar=drop_partial_bar, source="yahoo")


# ---------------------------------------------------------------------------
# 2. INDICATORS
# ---------------------------------------------------------------------------
def _wilder_ema(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def adx_wilder(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up = high - high.shift(1)
    down = low.shift(1) - low
    plus_dm = pd.Series(np.where((up > down) & (up > 0.0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0.0), down, 0.0), index=high.index)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = _wilder_ema(tr, period)

    plus_di = 100.0 * _wilder_ema(plus_dm, period) / atr.replace(0.0, np.nan)
    minus_di = 100.0 * _wilder_ema(minus_dm, period) / atr.replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return _wilder_ema(dx, period)


def prepare(df: pd.DataFrame, sma_len: int = 200, bb_len: int = 20, bb_std: float = 2.0) -> pd.DataFrame:
    out = df.copy()
    out["sma"] = out["close"].rolling(window=sma_len).mean()

    mid = out["close"].rolling(window=bb_len).mean()
    sd = out["close"].rolling(window=bb_len).std(ddof=0)
    out["bb_mid"] = mid
    out["bb_upper"] = mid + bb_std * sd
    out["bb_lower"] = mid - bb_std * sd

    # ADX(14) con pre-filtros de Wilder
    out["adx"] = adx_wilder(out["high"], out["low"], out["close"], period=14)

    # ATR(14) Wilder
    tr1 = out["high"] - out["low"]
    tr2 = (out["high"] - out["close"].shift(1)).abs()
    tr3 = (out["low"] - out["close"].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    out["atr14"] = tr.ewm(alpha=1.0 / 14.0, min_periods=14, adjust=False).mean()

    # Vela de rechazo: cierre en la parte alta del rango de la barra
    rng = (out["high"] - out["low"]).replace(0.0, np.nan)
    out["rejection"] = (out["close"] - out["low"]) / rng

    return out.dropna(subset=["sma", "bb_mid", "bb_upper", "bb_lower", "adx", "atr14", "rejection"]).copy()


# ---------------------------------------------------------------------------
# 3. BACKTEST (BBMR)
# ---------------------------------------------------------------------------
def run_bbmr_backtest(
    df: pd.DataFrame,
    bb_len: int = 20,
    bb_std: float = 2.0,
    adx_thr: float = 25.0,
    sma_len: int = 200,
    rejection_ratio: float = 0.5,
    max_bars: int = 15,
    atr_stop_mult: Optional[float] = None,
    slip_bps_per_side: float = 5.0,
    financing_bps_per_night: Optional[float] = None,
    risk_per_trade_pct: Optional[float] = None,
    max_exposure: Optional[float] = None,
) -> pd.DataFrame:
    """
    BBMR mean-reversion en barras diarias, lookahead-free.
      Entrada: en el cierre de i-1 -> low[i-1]<=bb_lower AND adx[i-1]<adx_thr AND close[i-1]>sma
               AND rejection[i-1]>=rejection_ratio  -> compra en open[i]*(1+slip).
      Stop:    open[i]*(1+slip) - atr_stop_mult*ATR[i-1]  (se evalúa intrabar).
      Salida:  target (close[i-1]>=bb_mid), time (i-i_ent>=max_bars) o hard_stop.
      Posición abierta al final: valorada al último cierre, reason='open_at_end'.
    """
    fin_bps = ENGINE_DEFAULTS["financing_bps_per_night"] if financing_bps_per_night is None else financing_bps_per_night
    risk_pct = ENGINE_DEFAULTS["risk_per_trade_pct"] if risk_per_trade_pct is None else risk_per_trade_pct
    stop_mult = ENGINE_DEFAULTS["atr_stop_mult"] if atr_stop_mult is None else atr_stop_mult
    expo_cap = ENGINE_DEFAULTS["max_exposure"] if max_exposure is None else max_exposure

    needed = {"sma", "bb_mid", "bb_upper", "bb_lower", "adx", "atr14", "rejection"}
    if not needed.issubset(df.columns):
        df = prepare(df, sma_len=sma_len, bb_len=bb_len, bb_std=bb_std)
    else:
        # sanity check de consistencia del SMA
        if len(df) >= sma_len:
            expected = float(df["close"].iloc[:sma_len].mean())
            got = float(df["sma"].iloc[sma_len - 1])
            assert np.isclose(got, expected, rtol=1e-6), (
                f"sma_len={sma_len} no coincide con la columna 'sma' precomputada."
            )

    slip = slip_bps_per_side / 10_000.0
    fin = fin_bps / 10_000.0

    opens = df["open"].values
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    smas = df["sma"].values
    mids = df["bb_mid"].values
    lowers = df["bb_lower"].values
    adxs = df["adx"].values
    atrs = df["atr14"].values
    rejs = df["rejection"].values
    idx = df.index

    trades: List[dict] = []
    in_pos = False
    ei = 0
    ep = 0.0
    expo_atr = 1.0
    stop_price: Optional[float] = None

    def _trade(i_exit: int, xp: float, reason: str, bars: int, nights: int) -> dict:
        ret_pct = (xp / ep - 1.0) * 100.0
        return {
            "entry_time": idx[ei], "exit_time": idx[i_exit],
            "entry_price": ep, "exit_price": xp, "type": "long", "reason": reason,
            "bars": bars, "adx_signal": adxs[ei - 1],
            "pnl": ret_pct, "pnl_atr": ret_pct * expo_atr, "win": ret_pct > 0.0,
            "i_ent": ei, "i_sal": i_exit, "expo": expo_atr, "nights": nights,
            "stop_price": stop_price,
        }

    for i in range(2, len(df)):
        if in_pos:
            # (1) salidas por señal: target o stop temporal, evaluadas en close[i-1], ejecutadas en open[i]
            exit_signal = False
            reason: Optional[str] = None
            if closes[i - 1] >= mids[i - 1]:
                exit_signal, reason = True, "target"
            elif (i - ei) >= max_bars:
                exit_signal, reason = True, "time"

            if exit_signal:
                nights = int((idx[i] - idx[ei]).days)
                xp = opens[i] * (1.0 - slip) * (1.0 - fin * nights)
                trades.append(_trade(i, xp, reason, i - ei, nights))
                in_pos = False
            else:
                # (2) hard stop intrabar
                if stop_price is not None and lows[i] <= stop_price:
                    fill = min(opens[i], stop_price)  # gap-through handled
                    nights = int((idx[i] - idx[ei]).days)
                    xp = fill * (1.0 - slip) * (1.0 - fin * nights)
                    trades.append(_trade(i, xp, "hard_stop", i - ei, nights))
                    in_pos = False

        if not in_pos:
            # (3) entrada: señal en close[i-1], ejecución en open[i]
            if (lows[i - 1] <= lowers[i - 1]
                    and adxs[i - 1] < adx_thr
                    and closes[i - 1] > smas[i - 1]
                    and rejs[i - 1] >= rejection_ratio):
                ep = opens[i] * (1.0 + slip)
                ei = i
                stop_price = ep - stop_mult * atrs[i - 1]
                expo_atr = min(expo_cap, ((risk_pct / 100.0) * ep) / (stop_mult * atrs[i - 1]))
                in_pos = True
                # (4) stop intrabar en la misma barra de entrada (gap / pierna bajista fuerte)
                if lows[i] <= stop_price:
                    fill = min(opens[i], stop_price)
                    xp = fill * (1.0 - slip)  # 0 noches
                    trades.append({
                        "entry_time": idx[ei], "exit_time": idx[i],
                        "entry_price": ep, "exit_price": xp, "type": "long", "reason": "hard_stop",
                        "bars": 0, "adx_signal": adxs[ei - 1],
                        "pnl": (xp / ep - 1.0) * 100.0,
                        "pnl_atr": (xp / ep - 1.0) * 100.0 * expo_atr,
                        "win": xp > ep,
                        "i_ent": ei, "i_sal": i, "expo": expo_atr, "nights": 0,
                        "stop_price": stop_price,
                    })
                    in_pos = False

    if in_pos:  # valorar posición abierta al último cierre
        nights = int((idx[-1] - idx[ei]).days)
        xp = closes[-1] * (1.0 - slip) * (1.0 - fin * nights)
        trades.append(_trade(len(df) - 1, xp, "open_at_end", len(df) - 1 - ei, nights))

    return pd.DataFrame(trades)


# Alias de compatibilidad para cuadernos antiguos (misma firma pública)
def run_rsi2_backtest(*args, **kwargs):
    raise RuntimeError(
        "run_rsi2_backtest() ha sido sustituido por run_bbmr_backtest() en este motor "
        "(edge: BBMR - Bollinger Band Mean Reversion con filtro ADX)."
    )


# ---------------------------------------------------------------------------
# 4. DAILY MTM RETURNS (ligeramente extendido para hard_stop)
# ---------------------------------------------------------------------------
def _trade_path(closes: np.ndarray, t, sizing: str) -> np.ndarray:
    expo = 1.0 if sizing == "capital" else float(t["expo"])
    i_ent = int(t["i_ent"]); i_sal = int(t["i_sal"])
    ep = float(t["entry_price"]); xp = float(t["exit_price"])

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
    Drawdown sobre cierres vs. uno más conservador que marca cada día en tenencia al LOW.
    Con hard stop, el trough intradía efectivo es max(low[k], stop_price), ya que el trade se cierra ahí.
    """
    r = daily_returns(df, trades, sizing=sizing).values
    eq_close = np.concatenate([[1.0], np.cumprod(1.0 + r)])
    peak_close = np.maximum.accumulate(eq_close)
    dd_close = float(((eq_close - peak_close) / peak_close).min())

    lows = df["low"].values
    worst = dd_close
    for _, t in trades.iterrows():
        expo = 1.0 if sizing == "capital" else float(t["expo"])
        i_ent, i_sal = int(t["i_ent"]), int(t["i_sal"])
        ep = float(t["entry_price"])
        stop_p = t.get("stop_price", None) if hasattr(t, "get") else t["stop_price"]
        e_start = eq_close[i_ent]
        for k in range(i_ent, i_sal):
            trough_price = lows[k]
            if stop_p is not None and not (isinstance(stop_p, float) and np.isnan(stop_p)):
                trough_price = max(trough_price, float(stop_p))
            trough = e_start * (1.0 + expo * (trough_price / ep - 1.0))
            worst = min(worst, trough / peak_close[k] - 1.0)
    return {"max_dd_close": dd_close, "max_dd_intraday": float(worst)}


# ---------------------------------------------------------------------------
# 5. LIVE SIZING (sin cambios funcionales; usa atr_stop_mult como stop REAL)
# ---------------------------------------------------------------------------
def position_size_lots(equity: float, price: float, atr: float,
                       contract_size: float = 1.0, lot_step: float = 0.01, min_lot: float = 0.01,
                       max_lot: Optional[float] = None, max_leverage: Optional[float] = None,
                       risk_per_trade_pct: Optional[float] = None, atr_stop_mult: Optional[float] = None,
                       max_exposure: Optional[float] = None) -> Dict[str, float]:
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
# 6. FIXED-RULES WALK-FORWARD (usa run_bbmr_backtest)
# ---------------------------------------------------------------------------
def walk_forward_fixed(df: pd.DataFrame, rules: Optional[Dict[str, Any]] = None,
                       is_years: int = 3) -> pd.DataFrame:
    params = {**DEFAULT_RULES, **(rules or {})}
    years = sorted(set(df.index.year))
    rows = []

    for y in years:
        if y - is_years < years[0]:
            continue
        if y == years[-1] and df.index[-1].month < 12:
            continue

        d_is = df[(df.index.year >= y - is_years) & (df.index.year < y)]
        d_oos = df[df.index.year == y]
        if len(d_is) < 600 or len(d_oos) < 200:
            continue

        ti = run_bbmr_backtest(d_is, **params)
        to = run_bbmr_backtest(d_oos, **params)

        ri_tot = (np.prod(1.0 + ti["pnl"] / 100.0) - 1.0) if len(ti) > 0 else 0.0
        ro_tot = (np.prod(1.0 + to["pnl"] / 100.0) - 1.0) if len(to) > 0 else 0.0

        if len(to) > 0:
            p = to["pnl"].values
            g = p[p > 0].sum(); l = -p[p < 0].sum()
            pf_oos = float(g / l) if l > 0 else np.inf
            eq = (1.0 + daily_returns(d_oos, to, sizing="capital")).cumprod().values
            pk = np.maximum.accumulate(eq)
            mdd_oos = float(((eq - pk) / pk).min())
        else:
            pf_oos = np.nan; mdd_oos = 0.0

        rows.append({
            "year": y,
            "ret_is_anual": ri_tot / float(is_years),
            "ret_oos": ro_tot,
            "n_oos": len(to),
            "pf_oos": pf_oos,
            "mdd_oos": mdd_oos,
        })

    return pd.DataFrame(rows)