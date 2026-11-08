"""BTC Overnight Seasonality engine v1.0 (Quantpedia: Padysak & Vojtko, "Are There Seasonal Intraday or Overnight
Anomalies in Bitcoin?" and "The Seasonality of Bitcoin").

Rule: LONG BTC from 21:00 UTC for `hold_hours` hours (default 2 -> sell at 23:00 UTC). Optional filters computed with
information known at 00:00 UTC of the same day: uptrend (open 00:00 > SMA of daily 00:00 opens) and high volatility
(30-day hourly vol above its EXPANDING past median, no lookahead). Optional % stop evaluated on hourly lows.

Same API shape as roughneck_engine / monday_effect_engine (load_data / prepare / run_*_backtest / hourly_returns /
trade_mtm_paths / walk_forward_fixed / hard_limit_report(_intrabar) / max_fraction_for_limit / cfd_trade_sizes /
min_capital_for_target / annual_returns / set_engine_defaults / ENGINE_DEFAULTS) plus swap_report().

Conventions (no lookahead):
  * data = MT5 H1 export. Bars are re-indexed to UTC by BAR OPEN time. Entry = OPEN of the bar at entry_hour_utc.
  * time exit = CLOSE of the last held bar (= open of the next bar for a 24/7 market). bars = hold_hours.
  * stop (optional): gap through it fills at the bar OPEN (gap_stop), intrabar at the stop price. The entry bar counts
    (worst case: its low is checked).
  * SWAP (the key cost of this edge): the 21-23 UTC window straddles the broker rollover (17:00 New York = 22:00 UTC in
    winter, 21:00 UTC in summer). A trade that is open at the rollover pays swap_long_pct_annual / 365 per charged night
    times swap_mult[weekday of the rollover day] (MT5 table: Mon-Thu 1, Fri 3). VERIFY the exact charge with real deals
    in notebook 04. A position opened exactly AT the rollover instant is treated as not crossing it.

Timezone handling (v1.0.1):
  * If the CSV timestamps already carry a timezone (e.g. `...Z` or `...+00:00` after any pre-processing step), that tz is
    trusted, `server_ny_offset_h` / `server_tz` are IGNORED and the index is normalised to naive-UTC.
  * If the CSV is tz-naive (stock MT5 export), the previous behaviour is preserved: server -> NY wall clock via
    `server_ny_offset_h`, then NY -> UTC with real DST rules (or `server_tz` localisation if the offset is not set).
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE_DEFAULTS = dict(
    data_source="csv_h1",
    server_tz="UTC",                  # used only when server_ny_offset_h is None AND the CSV is tz-naive
    server_ny_offset_h=None,          # MT5 "NY close" servers: server = NY wall clock + 7h all year. None = use server_tz.
                                      # Ignored when the CSV is already tz-aware.
    rollover_hour_ny=17,              # broker rollover (swap) at 17:00 New York
    swap_long_pct_annual=20.0,        # % of notional per year charged to longs (MT5 "Swap long", percentage type)
    swap_mult={0: 1, 1: 1, 2: 1, 3: 1, 4: 3, 5: 0, 6: 0},   # MT5 swap rates table, key = weekday (Mon=0) of the rollover day
    size_fraction=1.0,                # notional as a fraction of equity
    contract_size=1.0,                # BTC per 1.0 lot (VERIFY in MT5 specification)
    min_lot=0.1,
    lot_step=0.1,
    quote_to_account=1.0,             # USD quote, USD account. BTC-JPY: ~1/USDJPY
)

IND_KEYS = ("entry_hour_utc", "hold_hours", "trend_mode", "sma_len", "vol_mode", "vol_len_days")
BASE_RULES = dict(
    # --- indicator rules (prepare) ---
    entry_hour_utc=21, hold_hours=2,
    trend_mode="off", sma_len=50,          # trend_mode: off | up   (open 00:00 UTC > SMA(sma_len) of daily 00:00 opens)
    vol_mode="off", vol_len_days=30,       # vol_mode: off | high | low  (vs expanding past median of the 30d hourly vol)
    # --- exit / cost / side rules (run) ---
    days=[0, 1, 2, 3, 4, 5, 6],            # UTC weekdays (Mon=0) of the ENTRY bar that are traded
    stop_pct=0.0,                          # 0 = no stop
    side="long",
    cost_bps_per_side=3.0,                 # spread + commission proxy per side (VERIFY with real spreads at 21-23 UTC)
)
TRADE_COLS = ["entry_time", "exit_time", "entry_price", "exit_price", "type", "pnl", "win", "bars", "i_ent", "i_sal",
              "swap_nights", "pnl_usd", "exit_reason", "pnl_frac"]
NY = "America/New_York"


def set_engine_defaults(**kw):
    for k, v in kw.items():
        if k not in ENGINE_DEFAULTS:
            raise KeyError(f"unknown engine default: {k}")
        ENGINE_DEFAULTS[k] = v
    if isinstance(ENGINE_DEFAULTS["swap_mult"], dict):   # YAML may give string keys
        ENGINE_DEFAULTS["swap_mult"] = {int(a): float(b) for a, b in ENGINE_DEFAULTS["swap_mult"].items()}


def _cfg(name, value=None):
    return ENGINE_DEFAULTS[name] if value is None else value


# ------------------------------------------------------------------ data
def _find_csv(ticker):
    """First CSV whose FILE NAME contains `ticker` (case-insensitive), searching the engine folder and 3 parents."""
    here = Path(__file__).resolve().parent
    t = ticker.lower()
    for base in (here, *here.parents[:3]):
        hits = sorted(p for p in glob.glob(str(base / "**" / "*.csv"), recursive=True) if t in Path(p).name.lower())
        if hits:
            return hits[0]
    raise FileNotFoundError(f"no CSV whose name contains '{ticker}' (any case) near {here}")


def _read_csv_any_sep(path):
    for sep in (",", ";", "\t"):
        df = pd.read_csv(path, sep=sep)
        if df.shape[1] >= 5:
            return df
    raise ValueError(f"cannot parse {path}")


def _to_naive_utc(df):
    """Normalise the index to naive-UTC, respecting a pre-existing tz if there is one."""
    idx = df.index
    if idx.tz is not None:
        # CSV already carries a timezone (usually UTC): trust it, do NOT apply server_ny_offset_h.
        # This is what fixes the `TypeError: Already tz-aware` on pandas 2.x.
        print(f"[load_data] input index is tz-aware ({idx.tz}); using its own tz, ignoring server_ny_offset_h/server_tz.")
        return df.set_axis(idx.tz_convert("UTC").tz_localize(None), axis=0)

    off = ENGINE_DEFAULTS.get("server_ny_offset_h")
    if off is not None:
        loc = (idx - pd.Timedelta(hours=float(off))).tz_localize(
            NY, ambiguous="NaT", nonexistent="shift_forward"
        )
    else:
        loc = idx.tz_localize(
            ENGINE_DEFAULTS["server_tz"], ambiguous="NaT", nonexistent="shift_forward"
        )
    ok = ~pd.isna(loc)
    df, loc = df[ok], loc[ok]
    return df.set_axis(pd.DatetimeIndex(loc.tz_convert("UTC").tz_localize(None)), axis=0)


def load_data(ticker, start=None, end=None, csv_path=None):
    """MT5 H1 export (<DATE>,<TIME>,<OPEN>...) or time/open/high/low/close. Returns hourly bars indexed by UTC bar-open
    time (naive). If the CSV is tz-aware, its tz is honoured; otherwise server_ny_offset_h / server_tz is applied."""
    raw = _read_csv_any_sep(csv_path or _find_csv(ticker))
    raw.columns = [c.strip("<>").lower() for c in raw.columns]
    if "date" in raw.columns and "time" in raw.columns and raw["time"].astype(str).str.contains(":").any():
        t = pd.to_datetime(raw["date"].astype(str) + " " + raw["time"].astype(str))
    else:
        t = pd.to_datetime(raw["date"] if "date" in raw.columns else raw["time"])
    df = pd.DataFrame({c: raw[c].astype(float).to_numpy() for c in ("open", "high", "low", "close")},
                      index=pd.DatetimeIndex(t))
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    if df.index.to_series().diff().median() > pd.Timedelta(hours=1):
        raise ValueError("this engine needs H1 data (found a coarser median step)")

    df = _to_naive_utc(df)
    df = df[df.index.notna()]                                # drop any NaT that survived DST localisation
    df = df[~df.index.duplicated(keep="last")].sort_index().dropna()
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    return df


# ------------------------------------------------------------------ indicators
def prepare(df_raw, **ind):
    """Calendar columns, filters and the eligibility mask on the FULL history. ind: any key of IND_KEYS."""
    bad = set(ind) - set(IND_KEYS)
    if bad:
        raise KeyError(f"not an indicator rule: {sorted(bad)}")
    p = {k: BASE_RULES[k] for k in IND_KEYS}
    p.update(ind)
    d = df_raw[["open", "high", "low", "close"]].copy()
    idx = d.index
    d["hour"], d["dow"] = idx.hour, idx.dayofweek
    if idx.tz is not None:                                   # defensive: accept tz-aware input too
        d["ny"] = idx.tz_convert(NY).tz_localize(None)
    else:
        d["ny"] = idx.tz_localize("UTC").tz_convert(NY).tz_localize(None)
    day = pd.Series(idx.normalize(), index=idx)

    # daily 00:00 UTC opens -> trend (known at 00:00, before the 21:00 entry)
    c0 = d.loc[d["hour"] == 0, "open"]
    c0.index = c0.index.normalize()
    sma = c0.rolling(int(p["sma_len"])).mean()
    up = (c0 > sma)
    # 30d hourly vol using days up to D-1; compared with the EXPANDING past median (no lookahead)
    r = np.log(d["close"]).diff()
    dvar = (r ** 2).groupby(idx.normalize()).mean()
    vol = np.sqrt(dvar.rolling(int(p["vol_len_days"])).mean().shift(1))
    vmed = vol.expanding(min_periods=90).median()

    trend_ok = pd.Series(True, index=idx)
    vol_ok = pd.Series(True, index=idx)
    warm = pd.Series(True, index=idx)
    if p["trend_mode"] == "up":
        trend_ok = day.map(up).fillna(False).astype(bool)
        warm &= day.map(sma).notna()
    if p["vol_mode"] in ("high", "low"):
        v, m = day.map(vol), day.map(vmed)
        vol_ok = ((v > m) if p["vol_mode"] == "high" else (v < m)).fillna(False)
        warm &= m.notna()
    d["trend_ok"], d["vol_ok"], d["warm"] = trend_ok.to_numpy(bool), vol_ok.to_numpy(bool), warm.to_numpy(bool)
    d["elig_hour"] = d["hour"] == int(p["entry_hour_utc"])
    d["elig"] = d["elig_hour"] & d["trend_ok"] & d["vol_ok"] & d["warm"]
    d.attrs["ind"] = p
    return d


# ------------------------------------------------------------------ backtest
def run_btcovn_backtest(d, **rules):
    r = {**BASE_RULES, **rules}
    ind = d.attrs.get("ind")
    if ind is not None:
        for k in IND_KEYS:
            if k in rules and rules[k] != ind[k]:
                raise ValueError(f"rule {k}={rules[k]} differs from prepare() ({ind[k]}): call prepare() again")
        r.update({k: ind[k] for k in IND_KEYS})
    if r["side"] != "long":
        raise ValueError("this edge is long-only")
    O, H, L, C = (d[c].to_numpy(float) for c in ("open", "high", "low", "close"))
    idx, ny, n = d.index, d["ny"], len(d)
    elig, dow = d["elig"].to_numpy(bool), d["dow"].to_numpy(int)
    hold, days = int(r["hold_hours"]), {int(x) for x in r["days"]}
    cb, stop_pct = float(r["cost_bps_per_side"]), float(r["stop_pct"])
    swap_pct = float(ENGINE_DEFAULTS["swap_long_pct_annual"])
    smult = {int(a): float(b) for a, b in ENGINE_DEFAULTS["swap_mult"].items()}
    roll_h = int(ENGINE_DEFAULTS["rollover_hour_ny"])
    rows, next_free = [], 0
    for i in np.flatnonzero(elig):
        if i < next_free or dow[i] not in days:
            continue
        j = i + hold - 1
        if j >= n or (idx[j] - idx[i]) != pd.Timedelta(hours=hold - 1):
            continue                                            # missing hourly bars: skip the trade
        E, k, ex, why = O[i], j, C[j], "time"
        if stop_pct > 0:
            sp = E * (1.0 - stop_pct / 100.0)
            for m in range(i, j + 1):
                if m > i and O[m] <= sp:
                    k, ex, why = m, O[m], "gap_stop"; break
                if L[m] <= sp:
                    k, ex, why = m, sp, ("stop_entry_bar" if m == i else "stop"); break
        t_in = ny.iat[i]
        t_out = ny.iat[k] + (pd.Timedelta(hours=1) if why == "time" else pd.Timedelta(0))
        w = 0.0
        for D in (t_in.normalize(), t_in.normalize() + pd.Timedelta(days=1)):
            roll = D + pd.Timedelta(hours=roll_h)
            if t_in < roll <= t_out:
                w += smult[int(D.dayofweek)]
        pnl_usd = ex - E
        pnl = pnl_usd / E * 100.0 - 2.0 * cb / 100.0 - swap_pct / 365.0 * w
        t_exit = idx[k] + (pd.Timedelta(hours=1) if why == "time" else pd.Timedelta(0))
        rows.append((idx[i], t_exit, E, ex, "long", pnl, pnl > 0, k - i + 1, i, k, w, pnl_usd, why,
                     pnl * _cfg("size_fraction")))
        next_free = k + 1
    return pd.DataFrame(rows, columns=TRADE_COLS)


def swap_report(trades):
    """How much of the edge the rollover swap eats: share of trades crossing it and the average drag in % per trade."""
    if trades.empty:
        return {}
    swap_pct = float(ENGINE_DEFAULTS["swap_long_pct_annual"])
    drag = swap_pct / 365.0 * trades["swap_nights"]
    return dict(n=len(trades), pct_crossing=float((trades["swap_nights"] > 0).mean()),
                avg_swap_drag_pct=float(drag.mean()), avg_net_pnl_pct=float(trades["pnl"].mean()),
                avg_gross_of_swap_pct=float((trades["pnl"] + drag).mean()),
                avg_drag_friday_pct=float(drag[trades["swap_nights"] >= 3].mean()) if (trades["swap_nights"] >= 3).any() else 0.0)


# ------------------------------------------------------------------ sizing / paths / returns
def _sizing(sizing, n):
    if isinstance(sizing, str):
        v = {"capital": 1.0, "fraction": float(ENGINE_DEFAULTS["size_fraction"])}[sizing]
        return np.full(n, v)
    a = np.asarray(sizing, float)
    return np.full(n, float(a)) if a.ndim == 0 else a


def trade_mtm_paths(df, trades, sizing="capital"):
    """Per-bar multiplicative returns of every trade; prod(1 + r) = 1 + pnl/100 * size (telescopes exactly)."""
    C, out = df["close"].to_numpy(float), []
    sz = _sizing(sizing, len(trades))
    for f, t in zip(sz, trades.itertuples()):
        v = (C[t.i_ent:t.i_sal + 1] - t.entry_price) / t.entry_price
        v[-1] = t.pnl / 100.0
        w = 1.0 + f * v
        out.append(w / np.concatenate([[1.0], w[:-1]]) - 1.0)
    return out


def hourly_returns(df, trades, sizing="capital"):
    s = np.zeros(len(df))
    for t, p in zip(trades.itertuples(), trade_mtm_paths(df, trades, sizing)):
        s[t.i_ent:t.i_sal + 1] += p
    return pd.Series(s, index=df.index)


daily_returns = hourly_returns   # API compatibility with the daily engines


def _worst_returns(df, trades, sizing):
    """Per-bar return at the worst intrabar point (low for longs); exit bar uses min(extreme, exit)."""
    L = df["low"].to_numpy(float)
    w = np.zeros(len(df))
    sz = _sizing(sizing, len(trades))
    for f, t, p in zip(sz, trades.itertuples(), trade_mtm_paths(df, trades, sizing)):
        cum = np.cumprod(1.0 + p)
        prev = np.concatenate([[1.0], cum[:-1]])
        adv = 1.0 + f * (L[t.i_ent:t.i_sal + 1] - t.entry_price) / t.entry_price
        adv[0] = min(adv[0], cum[0], 1.0)
        adv[-1] = min(adv[-1], cum[-1])
        w[t.i_ent:t.i_sal + 1] += np.minimum(adv / prev - 1.0, p)
    return pd.Series(w, index=df.index)


def _dd_series(r):
    eq = (1.0 + r).cumprod()
    return eq / np.maximum(eq.cummax(), 1.0) - 1.0


def hard_limit_report(returns, limit):
    dd = _dd_series(returns)
    br = dd < -limit
    return dict(max_dd=float(dd.min()), headroom=float(limit + dd.min()), passed=bool(dd.min() >= -limit),
                steps_in_breach=int(br.sum()), first_breach=(dd.index[br][0] if br.any() else None))


def hard_limit_report_intrabar(df, trades, limit, sizing="capital"):
    r = hourly_returns(df, trades, sizing)
    eq = (1.0 + r).cumprod()
    prev = eq.shift(1).fillna(1.0)
    peak_prev = np.maximum(eq.cummax().shift(1).fillna(1.0), 1.0)
    worst_eq = prev * (1.0 + _worst_returns(df, trades, sizing))
    dd_i = float(np.minimum(worst_eq / peak_prev - 1.0, 0.0).min())
    dd_c = float(_dd_series(r).min())
    dd = min(dd_i, dd_c)
    return dict(max_dd=dd, max_dd_close=dd_c, headroom=float(limit + dd), passed=bool(dd >= -limit))


def max_fraction_for_limit(df, trades, limit, hi=20.0):
    """Largest fixed notional fraction whose INTRABAR drawdown stays inside the limit (bisection)."""
    lo = 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if hard_limit_report_intrabar(df, trades, limit, mid)["passed"] else (lo, mid)
    return lo


def annual_returns(returns, trades, limit):
    rows = []
    for y, g in returns.groupby(returns.index.year):
        eq = (1.0 + g).cumprod()
        mdd = float((eq / np.maximum(eq.cummax(), 1.0) - 1.0).min())
        full = g.index[0] <= pd.Timestamp(f"{y}-01-07") and g.index[-1] >= pd.Timestamp(f"{y}-12-24")
        rows.append(dict(year=int(y), ret=float(eq.iloc[-1] - 1), mdd=mdd, breach=mdd < -limit, partial=not full))
    return pd.DataFrame(rows)


def min_capital_for_target(price, target_fraction):
    """Capital at which the minimum lot weighs <= target_fraction of equity (price in QUOTE currency)."""
    e = ENGINE_DEFAULTS
    return e["min_lot"] * e["contract_size"] * price * e["quote_to_account"] / target_fraction


def min_capital_for_stop_risk(stop_dist, risk_frac):
    """Capital at which the minimum lot risks <= risk_frac of equity if a stop of `stop_dist` (quote currency) is hit."""
    e = ENGINE_DEFAULTS
    return e["min_lot"] * e["contract_size"] * stop_dist * e["quote_to_account"] / risk_frac


def worst_adverse_move(df, trades):
    """Largest adverse excursion (price units, positive) of any trade, intrabar and including gap exits."""
    L, w = df["low"].to_numpy(float), 0.0
    for t in trades.itertuples():
        w = max(w, t.entry_price - L[t.i_ent:t.i_sal + 1].min(), -t.pnl_usd)
    return float(w)


def cfd_trade_sizes(trades, capital, size_fraction=None):
    """Lot-adjusted size per trade: floor(capital * fraction / (entry * contract)) to lot_step; 0 -> not taken."""
    e, f = ENGINE_DEFAULTS, _cfg("size_fraction", size_fraction)
    per_lot = e["contract_size"] * trades["entry_price"].to_numpy(float) * e["quote_to_account"]
    lots = np.floor(capital * f / per_lot / e["lot_step"] + 1e-9) * e["lot_step"]
    taken = lots >= e["min_lot"] - 1e-12
    lots = np.where(taken, lots, 0.0)
    return pd.DataFrame({"lots": lots, "size_fraction": lots * per_lot / capital, "taken": taken}, index=trades.index)


# ------------------------------------------------------------------ walk-forward (fixed rules)
def walk_forward_fixed(df, rules=None, is_years=3, sizing="fraction"):
    """Rules are NOT re-fitted: each calendar year is compared with the annualised return of the `is_years` full
    years before it. `df` must come from prepare()."""
    t = run_btcovn_backtest(df, **(rules or {}))
    r = hourly_returns(df, t, sizing)
    first = df.index[0]
    full = [y for y in sorted(set(df.index.year)) if pd.Timestamp(f"{y}-01-01") >= first]
    rows = []
    for y in sorted(set(df.index.year)):
        prev = [p for p in full if y - is_years <= p < y]
        if len(prev) < is_years:
            continue
        is_r = r[(r.index.year >= prev[0]) & (r.index.year <= prev[-1])]
        oos = r[r.index.year == y]
        eq = (1.0 + oos).cumprod()
        rows.append(dict(year=y, ret_is_anual=float((1 + is_r).prod() ** (1.0 / is_years) - 1), ret_oos=float(eq.iloc[-1] - 1),
                         mdd_oos=float((eq / np.maximum(eq.cummax(), 1.0) - 1.0).min()),
                         n_oos=int((pd.to_datetime(t["entry_time"]).dt.year == y).sum())))
    return pd.DataFrame(rows)