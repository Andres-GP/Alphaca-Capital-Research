"""
rsi2_engine.py
==============
Reusable research and execution engine for the TIS RSI(2) mean-reversion strategy
on Invesco QQQ Trust (NASDAQ-100 ETF) daily bars.

Strategy Blueprint:
  - Instrument: QQQ Daily bars (split/dividend adjusted via Yahoo Finance).
  - Trend Filter: Close > SMA(200) evaluated at close of day t.
  - Entry Trigger: RSI(2) < 15 evaluated at close of day t -> Buy at OPEN of day t+1.
  - Exit Trigger: Two consecutive green candles (Close > Open) at close of day t -> Sell at OPEN of day t+1.
  - Direction: Long only, no price stop.
  - Execution Costs: 5 bps per side (0.05% per side = 0.0005 fraction), zero commission.
  - Position Sizing:
      (a) "capital" -> 100% of capital per trade.
      (b) "atr"     -> 1% risk sizing with virtual stop ATR(14)x2, exposure capped at 100%.

Strictly lookahead-free: signals evaluated at close of bar t-1, executed at open of bar t.

CHANGELOG (fix):
  - run_rsi2_backtest: removed the `elif sma_len != 200` block that recomputed the SMA
    and dropped extra rows from an already-prepared DataFrame. That shifted i_ent / i_sal
    relative to the DataFrame the caller passes to daily_returns(), corrupting the daily
    MTM series (absurd drawdowns) for any sma_len != 200. The DataFrame must now be
    prepared by the caller with prepare(df, sma_len=...); sma_len is only used when the
    function has to call prepare() itself.
  - walk_forward_fixed: default rules now include sma_len, and a partial `rules` dict is
    merged over the defaults (so {"rsi_thr": 20.0} no longer drops the other settings).

CHANGELOG (review fixes):
  - run_rsi2_backtest: asserts that an already-prepared DataFrame was built with the
    same sma_len that is passed in (sma_len used to be silently ignored).
  - daily_returns: ATR sizing now uses the trade equity 1 + expo * (P/ep - 1), so the
    compounded daily returns of a trade equal its pnl_atr exactly.
  - trade_mtm_paths: new helper, daily MTM return path of each trade (used by the
    Monte Carlo and the validation gate for drawdowns).
  - walk_forward_fixed: mdd_oos is now measured on daily MTM returns, not trade by trade.
  - load_data: drops the last bar if it belongs to today's session and the session
    has not closed yet (partial bar).
  - run_rsi2_backtest: slippage is now passed in explicit basis points
    (slip_bps_per_side) instead of the ambiguous `> 0.005` percent/fraction heuristic.
  - run_rsi2_backtest: new flag strict_post_entry_2green (default False = previous
    behavior) to require that both green candles of the 2green exit are posterior
    to the entry.
"""

from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Optional, Literal, Dict, Any, List


# Frozen rules used when no explicit rules are given to walk_forward_fixed().
DEFAULT_RULES: Dict[str, Any] = {
    "rsi_thr": 15.0,
    "sma_len": 200,
    "exit_mode": "2green",
    "slip_bps_per_side": 5.0,
}


# ---------------------------------------------------------------------------
# 1. DATA INGESTION & INDICATOR PREPARATION
# ---------------------------------------------------------------------------

def load_data(ticker: str = "QQQ", start: str = "1999-01-01", drop_partial_bar: bool = True) -> pd.DataFrame:
    """
    Download daily historical bars for `ticker` from Yahoo Finance.

    Parameters:
    -----------
    ticker : str
        Yahoo Finance symbol (e.g. 'QQQ', 'IWM').
    start : str
        Start date in YYYY-MM-DD format.
    drop_partial_bar : bool
        If True (default), the last bar is dropped when it belongs to today's
        New York session and the session has not closed yet (before 16:00 NY).

    Returns:
    --------
    pd.DataFrame
        Indexed by 'time' with lowercase columns: ['open', 'high', 'low', 'close', 'volume'].
    """
    df_raw = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if isinstance(df_raw.columns, pd.MultiIndex):
        df_raw.columns = df_raw.columns.get_level_values(0)

    df_raw.columns = [str(c).lower() for c in df_raw.columns]
    df = df_raw[["open", "high", "low", "close", "volume"]].copy()
    df.index.name = "time"
    df.index = pd.to_datetime(df.index)

    if drop_partial_bar and len(df) > 0:
        now_ny = pd.Timestamp.now(tz="America/New_York")
        last_date = pd.Timestamp(df.index[-1]).date()
        if last_date == now_ny.date() and now_ny.time() < pd.Timestamp("16:00").time():
            df = df.iloc[:-1].copy()
    return df


def load_qqq(start: str = "1999-01-01", drop_partial_bar: bool = True) -> pd.DataFrame:
    """Backward-compatible wrapper: QQQ daily bars."""
    return load_data("QQQ", start=start, drop_partial_bar=drop_partial_bar)

def rsi_wilder(series: pd.Series, period: int = 2) -> pd.Series:
    """
    Compute Relative Strength Index (RSI) using J. Welles Wilder's
    exponential smoothing (alpha = 1 / period, adjust=False).

    Parameters:
    -----------
    series : pd.Series
        Price series (typically Close price).
    period : int
        RSI lookback period (default 2).

    Returns:
    --------
    pd.Series
        Wilder smoothed RSI values in [0, 100].
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def prepare(df: pd.DataFrame, sma_len: int = 200) -> pd.DataFrame:
    """
    Calculate strategy technical indicators on OHLCV data.

    Calculated columns:
      - 'sma': Simple Moving Average of Close over sma_len.
      - 'rsi2': Wilder RSI(2) on Close.
      - 'green': Binary indicator for candle direction (1 if Close > Open else 0).
      - 'ma5': Simple Moving Average of Close over 5 periods (Connors reference).
      - 'atr14': Wilder Average True Range (14 periods) on OHLC.

    Parameters:
    -----------
    df : pd.DataFrame
        Daily bar data with open, high, low, close columns.
    sma_len : int
        Lookback length for the macro trend filter (default 200).

    Returns:
    --------
    pd.DataFrame
        Copy of DataFrame with indicators added, dropping initial warm-up NaNs.
    """
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
# 2. BACKTEST ENGINE
# ---------------------------------------------------------------------------

def run_rsi2_backtest(
    df: pd.DataFrame,
    rsi_thr: float = 15.0,
    sma_len: int = 200,
    exit_mode: Literal["2green", "ma5", "rsi70"] = "2green",
    slip_bps_per_side: float = 5.0,
    strict_post_entry_2green: bool = False,
) -> pd.DataFrame:
    """
    Simulate the TIS RSI(2) mean-reversion strategy on daily bars.

    Execution logic (strictly lookahead-free):
      - Entry: Evaluated at close of day i-1. If rsi2[i-1] < rsi_thr AND close[i-1] > sma[i-1],
        enter long at open of day i: entry_price = open[i] * (1 + slip).
      - Exit: Evaluated at close of day i-1.
          * '2green': green[i-1] == 1 AND green[i-2] == 1
          * 'ma5'   : close[i-1] > ma5[i-1]
          * 'rsi70' : rsi2[i-1] > 70.0
        Exit at open of day i: exit_price = open[i] * (1 - slip).
      - Terminal state: If in position at dataset end, mark to market at last close
        with reason='open_at_end'.

    IMPORTANT: the columns i_ent / i_sal in the returned trades are positional indices
    into the DataFrame passed here. Pass the SAME DataFrame to daily_returns().

    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with OHLC prices and indicators, already built with
        prepare(df_raw, sma_len=<the SMA you want>). Slices of a prepared DataFrame
        (in-sample / out-of-sample) are fine: the indicators are NOT recomputed.
        If the indicator columns are missing, prepare(df, sma_len=sma_len) is called
        internally (in that case i_ent / i_sal refer to the prepared DataFrame).
        If the DataFrame is already prepared, an assertion checks that its 'sma'
        column corresponds to the sma_len passed here.
    rsi_thr : float
        RSI threshold for entry (default 15.0).
    sma_len : int
        Lookback length for the macro trend filter. Must match the one used in
        prepare() when the DataFrame is already prepared.
    exit_mode : str
        Exit rule: '2green' (default), 'ma5', or 'rsi70'.
    slip_bps_per_side : float
        Slippage/cost per side in basis points (default 5.0 = 0.05% = 0.0005).
    strict_post_entry_2green : bool
        Only for exit_mode='2green'. False (default) keeps the previous behavior:
        at bar i the exit looks at green[i-1] and green[i-2], so on the first
        evaluation (i = ei+1) the signal candle (ei-1) can count as one of the two
        greens. True requires both greens to be bars >= ei (the entry bar or later),
        i.e. the earliest exit is at ei+2.

    Returns:
    --------
    pd.DataFrame
        Trades DataFrame matching utils convention with columns:
        ['entry_time', 'exit_time', 'entry_price', 'exit_price', 'type',
         'reason', 'bars', 'rsi_signal', 'pnl', 'pnl_atr', 'win', 'i_ent', 'i_sal', 'expo']
    """
    # Auto-prepare only if required columns are missing. An already-prepared DataFrame
    # is never modified (no SMA recomputation, no extra rows dropped), so that
    # i_ent / i_sal stay aligned with the DataFrame the caller holds.
    if "sma" not in df.columns or "rsi2" not in df.columns or "atr14" not in df.columns:
        df = prepare(df, sma_len=sma_len)
    else:
        # The SMA of the row sma_len-1 only depends on the first sma_len closes of
        # the DataFrame, so it can be verified even on slices of a prepared DataFrame.
        if len(df) >= sma_len:
            expected_sma = float(df["close"].iloc[:sma_len].mean())
            got_sma = float(df["sma"].iloc[sma_len - 1])
            assert np.isclose(got_sma, expected_sma, rtol=1e-6), (
                f"sma_len={sma_len} does not match the SMA column of the prepared "
                f"DataFrame (expected {expected_sma:.6f}, found {got_sma:.6f}). "
                f"Prepare the DataFrame with prepare(df, sma_len={sma_len})."
            )

    # Slippage fraction from explicit basis points
    slip = slip_bps_per_side / 10_000.0

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

    for i in range(2, len(df)):
        if not in_pos:
            # Entry condition evaluated at close of day i-1
            if rsis[i - 1] < rsi_thr and closes[i - 1] > smas[i - 1]:
                ep = opens[i] * (1.0 + slip)
                ei = i
                # ATR 1% risk sizing: risk 1% with 2x ATR stop -> exposure = 0.01 * ep / (2 * atr[i-1])
                expo_atr = min(1.0, (0.01 * ep) / (2.0 * atrs[i - 1]))
                in_pos = True
        else:
            # Exit condition evaluated at close of day i-1
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
                xp = opens[i] * (1.0 - slip)
                ret_pct = (xp / ep - 1.0) * 100.0
                trades.append({
                    "entry_time": idx[ei],
                    "exit_time": idx[i],
                    "entry_price": ep,
                    "exit_price": xp,
                    "type": "long",
                    "reason": exit_mode,
                    "bars": i - ei,
                    "rsi_signal": rsis[ei - 1],
                    "pnl": ret_pct,
                    "pnl_atr": ret_pct * expo_atr,
                    "win": ret_pct > 0.0,
                    "i_ent": ei,
                    "i_sal": i,
                    "expo": expo_atr,
                })
                in_pos = False

    # Valuate terminal open position at last close
    if in_pos:
        xp = closes[-1] * (1.0 - slip)
        ret_pct = (xp / ep - 1.0) * 100.0
        trades.append({
            "entry_time": idx[ei],
            "exit_time": idx[-1],
            "entry_price": ep,
            "exit_price": xp,
            "type": "long",
            "reason": "open_at_end",
            "bars": len(df) - 1 - ei,
            "rsi_signal": rsis[ei - 1],
            "pnl": ret_pct,
            "pnl_atr": ret_pct * expo_atr,
            "win": ret_pct > 0.0,
            "i_ent": ei,
            "i_sal": len(df) - 1,
            "expo": expo_atr,
        })

    trades_df = pd.DataFrame(trades)
    return trades_df


# ---------------------------------------------------------------------------
# 3. DAILY MARK-TO-MARKET RETURNS
# ---------------------------------------------------------------------------

def _trade_path(closes: np.ndarray, t, sizing: str) -> np.ndarray:
    """
    Daily MTM return path of ONE trade, from its entry day (i_ent) to its exit day (i_sal).

    The equity of the trade on each day is 1 + expo * (P_k / ep - 1), where P_k is the
    close of day k (entry day and holding days) and the exit price (open - slip) on the
    exit day. The daily return is equity_k / equity_{k-1} - 1 (equity_{-1} = 1), so the
    compounded path of the trade equals 1 + expo * (xp / ep - 1) exactly. With
    sizing='capital' (expo = 1) this is the plain close-to-close return.
    """
    expo = 1.0 if sizing == "capital" else min(1.0, float(t["expo"]))
    i_ent = int(t["i_ent"])
    i_sal = int(t["i_sal"])
    ep = float(t["entry_price"])
    xp = float(t["exit_price"])

    prices = np.empty(i_sal - i_ent + 1, dtype=float)
    prices[0] = closes[i_ent]
    prices[1:] = closes[i_ent + 1:i_sal + 1]
    prices[-1] = xp  # exit day: exit price (open - slip) instead of the close

    equity = 1.0 + expo * (prices / ep - 1.0)
    prev = np.concatenate(([1.0], equity[:-1]))
    return equity / prev - 1.0


def trade_mtm_paths(
    df: pd.DataFrame,
    trades: pd.DataFrame,
    sizing: Literal["capital", "atr"] = "capital",
) -> List[np.ndarray]:
    """
    Daily MTM return path of each trade (list aligned row by row with `trades`).

    Used by the block Monte Carlo and by the validation gate to measure drawdowns on
    daily mark-to-market returns instead of trade by trade.

    Parameters:
    -----------
    df : pd.DataFrame
        The SAME DataFrame passed to run_rsi2_backtest().
    trades : pd.DataFrame
        Trades DataFrame returned by run_rsi2_backtest.
    sizing : str
        'capital' (100% position size) or 'atr' (1% risk sizing).

    Returns:
    --------
    list of np.ndarray
        One array of daily fractional returns per trade (length i_sal - i_ent + 1).
    """
    closes = df["close"].values
    return [_trade_path(closes, t, sizing) for _, t in trades.iterrows()]


def daily_returns(
    df: pd.DataFrame,
    trades: pd.DataFrame,
    sizing: Literal["capital", "atr"] = "capital",
) -> pd.Series:
    """
    Generate the daily mark-to-market return Series for the strategy.

    Outside of positions, daily return is 0.0.
    During positions the equity of each trade is 1 + expo * (P / entry_price - 1):
      - Entry day (ei): return from entry_price to close[ei].
      - Intermediate days (k): return from close[k-1] to close[k].
      - Exit day (i): return from close[i-1] to exit_price.
    expo is 1.0 for capital sizing, or min(1.0, expo) for atr sizing. The compounded
    return of each trade equals its pnl (capital) or pnl_atr (atr) exactly.

    Parameters:
    -----------
    df : pd.DataFrame
        Underlying daily price DataFrame. It must be the SAME DataFrame that was
        passed to run_rsi2_backtest() (trades carry positional indices into it).
    trades : pd.DataFrame
        Trades DataFrame returned by run_rsi2_backtest.
    sizing : str
        'capital' (100% position size) or 'atr' (1% risk sizing).

    Returns:
    --------
    pd.Series
        Series of daily fractional returns indexed by df.index.
    """
    r = np.zeros(len(df), dtype=float)
    if len(trades) == 0:
        return pd.Series(r, index=df.index, name="daily_return")

    closes = df["close"].values

    for _, t in trades.iterrows():
        i_ent = int(t["i_ent"])
        i_sal = int(t["i_sal"])
        r[i_ent:i_sal + 1] = _trade_path(closes, t, sizing)

    return pd.Series(r, index=df.index, name="daily_return")


# ---------------------------------------------------------------------------
# 4. FIXED-RULES WALK-FORWARD ANALYSIS
# ---------------------------------------------------------------------------

def walk_forward_fixed(
    df: pd.DataFrame,
    rules: Optional[Dict[str, Any]] = None,
    is_years: int = 3,
) -> pd.DataFrame:
    """
    Run rolling walk-forward analysis with fixed strategy rules (no re-optimization).

    Windows: Rolling IS of `is_years` calendar years / OOS of 1 calendar year.
    Requires >= 600 IS bars and >= 200 OOS bars to ensure valid full-year sampling.

    Parameters:
    -----------
    df : pd.DataFrame
        Prepared price DataFrame, built with the same sma_len as the rules
        (e.g. prepare(df_raw, sma_len=250) when testing SMA 250). Windows are slices
        of this DataFrame, so the SMA is never recomputed per window.
    rules : dict, optional
        Backtest parameters (rsi_thr, sma_len, exit_mode, slip_bps_per_side).
        Keys not provided fall back to DEFAULT_RULES (rsi_thr=15, sma_len=200,
        exit_mode='2green', slip=5 bps). To test a variant, pass its parameters
        explicitly, e.g. rules={"rsi_thr": 20.0, "sma_len": 250}.
    is_years : int
        Number of in-sample years per rolling window (default 3).

    Returns:
    --------
    pd.DataFrame
        Table of walk-forward windows with columns:
        ['year', 'ret_is_anual', 'ret_oos', 'n_oos', 'pf_oos', 'mdd_oos']
        mdd_oos is the max drawdown of the daily mark-to-market equity of the OOS year.
    """
    params = {**DEFAULT_RULES, **(rules or {})}
    years = sorted(set(df.index.year))
    rows = []

    for y in years:
        if y - is_years < years[0]:
            continue
        # Skip incomplete current year if near beginning of year
        if y == years[-1] and df.index[-1].month < 12:
            continue

        d_is = df[(df.index.year >= y - is_years) & (df.index.year < y)]
        d_oos = df[df.index.year == y]

        if len(d_is) < 600 or len(d_oos) < 200:
            continue

        ti = run_rsi2_backtest(d_is, **params)
        to = run_rsi2_backtest(d_oos, **params)

        ri_tot = (np.prod(1.0 + ti["pnl"] / 100.0) - 1.0) if len(ti) > 0 else 0.0
        ri_annual = ri_tot / float(is_years)
        ro_tot = (np.prod(1.0 + to["pnl"] / 100.0) - 1.0) if len(to) > 0 else 0.0

        if len(to) > 0:
            p = to["pnl"].values
            g = p[p > 0].sum()
            l = -p[p < 0].sum()
            pf_oos = float(g / l) if l > 0 else np.inf
            # Drawdown on daily mark-to-market equity (not trade by trade)
            eq = (1.0 + daily_returns(d_oos, to, sizing="capital")).cumprod().values
            pk = np.maximum.accumulate(eq)
            mdd_oos = float(((eq - pk) / pk).min())
        else:
            pf_oos = np.nan
            mdd_oos = 0.0

        rows.append({
            "year": y,
            "ret_is_anual": ri_annual,
            "ret_oos": ro_tot,
            "n_oos": len(to),
            "pf_oos": pf_oos,
            "mdd_oos": mdd_oos,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. SMOKE TEST (__main__)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("rsi2_engine.py - Smoke Test")
    print("=" * 60)

    print("1. Downloading QQQ data...")
    df_raw = load_qqq()
    print(f"   Loaded {len(df_raw)} raw daily bars ({df_raw.index.min().date()} to {df_raw.index.max().date()})")

    print("2. Preparing indicators...")
    df_prep = prepare(df_raw, sma_len=200)
    print(f"   Prepared {len(df_prep)} bars with clean indicators.")

    print("3. Running baseline backtest (frozen rules)...")
    trades = run_rsi2_backtest(df_prep)
    print(f"   Generated {len(trades)} trades.")
    win_rate = trades['win'].mean() * 100.0
    p = trades['pnl'].values
    pf = p[p > 0].sum() / (-p[p < 0].sum())
    print(f"   Win Rate: {win_rate:.1f}% | Profit Factor (Capital): {pf:.3f}")

    print("4. Calculating mark-to-market daily returns...")
    ret_cap = daily_returns(df_prep, trades, sizing="capital")
    ret_atr = daily_returns(df_prep, trades, sizing="atr")
    print(f"   Capital sizing total return: {(np.prod(1 + ret_cap) - 1) * 100:.1f}%")
    print(f"   ATR sizing total return:     {(np.prod(1 + ret_atr) - 1) * 100:.1f}%")

    print("5. Running walk-forward analysis...")
    wf = walk_forward_fixed(df_prep, is_years=3)
    eff = wf['ret_oos'].mean() / wf['ret_is_anual'].mean()
    pct_pos = (wf['ret_oos'] > 0).mean() * 100.0
    worst_dd = wf['mdd_oos'].min() * 100.0
    print(f"   Walk-Forward Windows: {len(wf)} | Efficiency: {eff:.2f} | Positive Years: {pct_pos:.1f}% | Worst MDD: {worst_dd:.1f}%")

    print("=" * 60)
    print("Smoke test completed successfully!")
    print("=" * 60)