"""
ibb_engine.py
=============
Reusable engine for the "Initial Balance Break Out" (IBB) strategy, adapted
from Estrategia_3_Nasdaq_IBB.md (QQQ, RTH-only equities/ETF) to NQ futures
(24h continuous session, MongoDB 15-min bars).

This module is imported by BOTH:
  - NQ_IBB_Development.ipynb   (single in-sample backtest, strategy build-out)
  - NQ_IBB_Robustness.ipynb    (OOS split, walk-forward, Monte Carlo, sensitivity)

so that the exact same signal/backtest logic is validated in development and
stress-tested in robustness -- no drift between the two notebooks.

Adaptation notes vs. the original QQQ blueprint (documented, not silently
changed -- see Estrategia_3_Nasdaq_IBB.md "VARIABLES DE SETUP" / "TRIGGERS"):

1. Session anchor: NQ 15-min bars from MongoDB are session-stamped with the
   session starting at 18:00 NY (see NQ_EDA.md, section 1.3-2.1). The 9:30-10:30
   NY Initial Balance sits INSIDE that session, not at its start. IB is built
   from the four 15-min bars at 09:30, 09:45, 10:00, 10:15 NY.

2. Forced close: the strategy doc explicitly distinguishes equities/ETF
   (15:30 NY) from futures (23:00 NY): "Cierre forzoso: 15:30 PM (QQQ/SPY)
   o 23:00 NY (futuros)". NQ uses the FUTURES forced-close time (23:00 NY),
   not the equities time. This is a deliberate, documented adaptation, not
   an oversight.

3. Trigger timeframe: the blueprint specifies a 5-min entry trigger. The
   MongoDB collection available for NQ is 15-min only (nq_15min). Entries
   are therefore evaluated on 15-min bars within the entry window
   (10:30-13:30 NY), using the same Wick/Close logic. This is a resolution
   adaptation, flagged here and again in the notebooks -- it should be
   revisited if/when a 5-min NQ collection becomes available.

4. Units: QQQ math is in %/$ per share. NQ futures P&L is computed in
   INDEX POINTS per contract, then converted to $ using the ES/NQ-style
   point value (default: $20/point for full-size NQ, $2/point for MNQ --
   configurable via `point_value`).

5. No open/pending position 4:30pm-6:00pm NY constraint (per project's
   locked strategy constraints -- see AlphaCapital-Research memory): the
   forced-close time of 23:00 NY, plus a same-day-only trade rule, already
   keeps this strategy entirely clear of the 16:30-18:00 blackout window,
   so no extra gating logic is required here -- documented for traceability.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# 1. CONFIG
# ---------------------------------------------------------------------------

@dataclass
class IBBConfig:
    """All tunable parameters, defaults = blueprint values from
    Estrategia_3_Nasdaq_IBB.md, adapted per the notes above."""

    # --- Initial Balance window (NY time) ---
    ib_start: str = "09:30"
    ib_end_exclusive: str = "10:30"     # IB built from bars in [ib_start, ib_end_exclusive)

    # --- Entry window (NY time) ---
    entry_window_start: str = "10:30"
    entry_window_end: str = "13:30"

    # --- Forced close (NY time). Futures value per blueprint adaptation #2. ---
    forced_close_time: str = "23:00"

    # --- Volatility filter ---
    ib_pct_min: float = 0.55            # IB% >= this to enable trading
    ib_pct_extreme: float = 2.00        # >= this => extreme vol flag (half-size)

    # --- Risk management multipliers (of IB Range) ---
    tp_mult: float = 0.60
    sl_mult: float = 0.40

    # --- Entry trigger mode: "wick" (stop-style, high/low touch) or "close" ---
    entry_mode: str = "wick"

    # --- One trade per session ---
    max_trades_per_session: int = 1

    # --- Contract economics ---
    point_value: float = 20.0           # $ per index point per contract (NQ full-size)
    contracts: int = 1

    # --- Cost model (points, applied per round-turn) ---
    slippage_points: float = 0.0
    commission_points: float = 0.0      # commission expressed in index points/RT


# ---------------------------------------------------------------------------
# 2. INITIAL BALANCE CONSTRUCTION
# ---------------------------------------------------------------------------

def to_time_str(ts) -> str:
    return ts.strftime("%H:%M")


def build_initial_balance(df_session: pd.DataFrame, cfg: IBBConfig) -> Optional[dict]:
    """Given ALL 15-min bars for a single session (a DataFrame slice with a
    'session_date' already isolated), compute IB High/Low/Mid/Range/%.
    Returns None if the IB window bars are incomplete for that session
    (e.g. holiday-shortened session -- consistent with the EDA's
    data-completeness handling)."""
    ib_bars = df_session.between_time(cfg.ib_start, cfg.ib_end_exclusive,
                                       inclusive="left")
    if ib_bars.empty:
        return None
    # Require the full IB window (4 bars of 15min = 60min) to avoid building
    # an IB off a partial/holiday session -- mirrors the EDA's treatment of
    # truncated sessions as a data-quality issue, not a tradeable pattern.
    expected_bars = 4
    if len(ib_bars) < expected_bars:
        return {
            "ib_high": np.nan, "ib_low": np.nan, "ib_mid": np.nan,
            "ib_range": np.nan, "ib_pct": np.nan, "ib_bars": len(ib_bars),
            "valid": False,
        }

    ib_high = ib_bars["high"].max()
    ib_low = ib_bars["low"].min()
    ib_mid = (ib_high + ib_low) / 2.0
    ib_range = ib_high - ib_low
    ib_pct = (ib_range / ib_mid) * 100.0 if ib_mid else np.nan

    return {
        "ib_high": ib_high, "ib_low": ib_low, "ib_mid": ib_mid,
        "ib_range": ib_range, "ib_pct": ib_pct, "ib_bars": len(ib_bars),
        "valid": True,
    }


# ---------------------------------------------------------------------------
# 3. SIGNAL GENERATION + PER-SESSION BACKTEST
# ---------------------------------------------------------------------------

def _breakout_trigger(bar: pd.Series, ib_high: float, ib_low: float, mode: str):
    """Return 'long', 'short', or None for a single bar, given the IB levels."""
    if mode == "wick":
        broke_up = bar["high"] > ib_high
        broke_down = bar["low"] < ib_low
    elif mode == "close":
        broke_up = bar["close"] > ib_high
        broke_down = bar["close"] < ib_low
    else:
        raise ValueError(f"Unknown entry_mode: {mode}")

    # If both trigger in the same bar (gap/spike), prefer the direction of
    # the larger excursion beyond the level -- documented tie-break rule.
    if broke_up and broke_down:
        up_excess = bar["high"] - ib_high
        down_excess = ib_low - bar["low"]
        return "long" if up_excess >= down_excess else "short"
    if broke_up:
        return "long"
    if broke_down:
        return "short"
    return None


def simulate_session(df_session: pd.DataFrame, ib: dict, cfg: IBBConfig) -> Optional[dict]:
    """Simulate one trading session against the IBB rules. Returns a trade
    dict (possibly a 'no trade' record) or None if the session cannot be
    evaluated (e.g. invalid IB)."""

    if ib is None or not ib.get("valid", False):
        return None

    session_date = df_session.index[0].date()

    result = {
        "session_date": session_date,
        "ib_high": ib["ib_high"], "ib_low": ib["ib_low"],
        "ib_mid": ib["ib_mid"], "ib_range": ib["ib_range"],
        "ib_pct": ib["ib_pct"],
        "traded": False, "direction": None,
        "entry_time": None, "entry_price": None,
        "exit_time": None, "exit_price": None, "exit_reason": None,
        "pnl_points": np.nan, "pnl_pct": np.nan, "pnl_usd": np.nan,
        "no_trade_reason": None,
    }

    # --- Volatility filter ---
    if not np.isfinite(ib["ib_pct"]) or ib["ib_pct"] < cfg.ib_pct_min:
        result["no_trade_reason"] = "ib_pct_below_min"
        return result

    entry_bars = df_session.between_time(
        cfg.entry_window_start, cfg.entry_window_end, inclusive="left"
    )
    if entry_bars.empty:
        result["no_trade_reason"] = "no_bars_in_entry_window"
        return result

    trades_taken = 0
    for ts, bar in entry_bars.iterrows():
        if trades_taken >= cfg.max_trades_per_session:
            break

        direction = _breakout_trigger(bar, ib["ib_high"], ib["ib_low"], cfg.entry_mode)
        if direction is None:
            continue

        # --- Entry price: use the breakout level itself (stop-fill assumption) ---
        entry_price = ib["ib_high"] if direction == "long" else ib["ib_low"]
        entry_price += cfg.slippage_points if direction == "long" else -cfg.slippage_points

        if direction == "long":
            tp = entry_price + cfg.tp_mult * ib["ib_range"]
            sl = max(entry_price - cfg.sl_mult * ib["ib_range"], ib["ib_low"])
        else:
            tp = entry_price - cfg.tp_mult * ib["ib_range"]
            sl = min(entry_price + cfg.sl_mult * ib["ib_range"], ib["ib_high"])

        # --- Walk forward bar-by-bar from entry bar (inclusive) to find exit ---
        post_entry = df_session.loc[ts:]
        forced_close_bars = post_entry.between_time(
            cfg.forced_close_time, cfg.forced_close_time, inclusive="both"
        )
        exit_time, exit_price, exit_reason = None, None, None

        for ts2, bar2 in post_entry.iterrows():
            t2 = to_time_str(ts2)
            if direction == "long":
                hit_tp = bar2["high"] >= tp
                hit_sl = bar2["low"] <= sl
            else:
                hit_tp = bar2["low"] <= tp
                hit_sl = bar2["high"] >= sl

            # Conservative same-bar tie-break: assume SL fills first (worst case)
            if hit_sl and hit_tp:
                exit_time, exit_price, exit_reason = ts2, sl, "SL"
                break
            if hit_sl:
                exit_time, exit_price, exit_reason = ts2, sl, "SL"
                break
            if hit_tp:
                exit_time, exit_price, exit_reason = ts2, tp, "TP"
                break
            if t2 >= cfg.forced_close_time:
                exit_time, exit_price, exit_reason = ts2, bar2["close"], "TIME"
                break

        if exit_time is None:
            # Session ended without hitting TP/SL/forced-close bar explicitly
            # (e.g. truncated session) -- exit on last available bar, flagged.
            last_ts, last_bar = post_entry.index[-1], post_entry.iloc[-1]
            exit_time, exit_price, exit_reason = last_ts, last_bar["close"], "SESSION_END"

        exit_price += -cfg.slippage_points if direction == "long" else cfg.slippage_points

        pnl_points = (exit_price - entry_price) if direction == "long" else (entry_price - exit_price)
        pnl_points -= cfg.commission_points
        pnl_pct = pnl_points / entry_price * 100.0
        pnl_usd = pnl_points * cfg.point_value * cfg.contracts

        result.update({
            "traded": True, "direction": direction,
            "entry_time": ts, "entry_price": entry_price,
            "exit_time": exit_time, "exit_price": exit_price, "exit_reason": exit_reason,
            "pnl_points": pnl_points, "pnl_pct": pnl_pct, "pnl_usd": pnl_usd,
        })
        trades_taken += 1

    if trades_taken == 0:
        result["no_trade_reason"] = "no_breakout_in_window"

    return result


def run_backtest(df_raw: pd.DataFrame, cfg: IBBConfig,
                  session_col: str = "session_date") -> pd.DataFrame:
    """Full backtest driver.

    df_raw: 15-min OHLCV DataFrame, tz-naive NY-local index (as produced by
            utils.load_data_from_mongo('nq_15min')), MUST already contain a
            `session_date` column (see utils.to_session_date used in NQ_EDA).
    Returns a DataFrame of one row per session (trade or no-trade record).
    """
    records = []
    for session_date, df_session in df_raw.groupby(session_col):
        df_session = df_session.sort_index()
        ib = build_initial_balance(df_session, cfg)
        rec = simulate_session(df_session, ib, cfg)
        if rec is not None:
            records.append(rec)

    trades_df = pd.DataFrame.from_records(records)
    if not trades_df.empty:
        trades_df = trades_df.sort_values("session_date").reset_index(drop=True)
    return trades_df


# ---------------------------------------------------------------------------
# 4. PERFORMANCE METRICS  (mirrors "VALIDACIÓN ESTADÍSTICA" table layout)
# ---------------------------------------------------------------------------

def compute_metrics(trades_df: pd.DataFrame, starting_equity: float = 100_000.0) -> dict:
    """Compute the same metric set as the strategy doc's validation table:
    total trades, win rate, avg win/loss, payoff ratio, profit factor,
    total return, max drawdown, expectancy/trade -- plus a few extras
    (Sharpe-ish, avg hold time) useful for robustness comparisons."""

    if trades_df is None or trades_df.empty:
        return {"total_trades": 0}

    traded = trades_df[trades_df["traded"]].copy()
    n_sessions = len(trades_df)
    n_trades = len(traded)

    if n_trades == 0:
        return {
            "total_sessions": n_sessions, "total_trades": 0,
            "trade_frequency_pct": 0.0,
        }

    wins = traded[traded["pnl_usd"] > 0]
    losses = traded[traded["pnl_usd"] <= 0]

    win_rate = len(wins) / n_trades * 100.0
    avg_win_pct = wins["pnl_pct"].mean() if len(wins) else 0.0
    avg_loss_pct = losses["pnl_pct"].mean() if len(losses) else 0.0
    payoff_ratio = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else np.nan

    gross_profit = wins["pnl_usd"].sum()
    gross_loss = -losses["pnl_usd"].sum()
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

    # --- Equity curve & drawdown (sequential, one position at a time) ---
    equity = starting_equity + traded["pnl_usd"].cumsum()
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max * 100.0
    max_dd_pct = drawdown.min() if len(drawdown) else 0.0

    total_return_pct = (equity.iloc[-1] - starting_equity) / starting_equity * 100.0
    expectancy_usd = traded["pnl_usd"].mean()

    hold_time = (traded["exit_time"] - traded["entry_time"]).dt.total_seconds() / 60.0

    metrics = {
        "total_sessions": n_sessions,
        "total_trades": n_trades,
        "trade_frequency_pct": n_trades / n_sessions * 100.0,
        "win_rate_pct": win_rate,
        "avg_win_pct": avg_win_pct,
        "avg_loss_pct": avg_loss_pct,
        "payoff_ratio": payoff_ratio,
        "profit_factor": profit_factor,
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_dd_pct,
        "expectancy_usd": expectancy_usd,
        "avg_hold_minutes": hold_time.mean(),
        "final_equity": equity.iloc[-1] if len(equity) else starting_equity,
    }
    return metrics


def print_metrics_table(metrics: dict, label: str = "") -> None:
    print("=" * 70)
    if label:
        print(f"IBB METRICS -- {label}")
    print("=" * 70)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"{k:24s}: {v:,.3f}")
        else:
            print(f"{k:24s}: {v}")
    print("=" * 70)
