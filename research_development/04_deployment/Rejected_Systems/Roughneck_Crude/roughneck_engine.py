"""Roughneck Crude Oil engine v2.1 (LeBeau/Elden 1999; TIS newsletter Vol.03, Aug 2026).

Same API shape as monday_effect_engine (load_data / prepare / run_*_backtest / daily_returns /
trade_mtm_paths / walk_forward_fixed / hard_limit_report(_intrabar) / max_fraction_for_limit /
cfd_trade_sizes / min_capital_for_target / annual_returns / set_engine_defaults / ENGINE_DEFAULTS).

v2.1 changes vs v2.0:
  * _find_csv: case-insensitive match on the FILE NAME (USOIL_H1.csv now matches ticker "usoil").
  * server time -> New York: new ENGINE_DEFAULTS["server_ny_offset_h"] (e.g. 7 for "NY close" MT5 servers, no DST handling);
    None falls back to server_tz with real DST rules. The daily label is computed on the NY wall clock.
  * mode="fade": inverted logic (trade AGAINST the signal, market entry at the next open, stop / target / time stop).

Daily bars, long AND short. No-lookahead convention:
  * the signal is evaluated at the CLOSE of bar i; the entry stop order is valid ONLY on bar i+1;
  * exit stops for bar k use information up to the close of bar k-1 (they are known before bar k opens);
  * gaps through a stop fill at the OPEN (gap_stop); intrabar the stop fills at the stop price;
  * entry bar (rule `entry_bar_path`): "worst" (default) = if the low (high for shorts) of the entry bar touches the base
    stop we are stopped out; "ohlc" = path heuristic up bar O>L>H>C / down bar O>H>L>C, which is OPTIMISTIC for a $1 stop
    on a ~$2 daily range (it manufactures an edge on pure random walks: tests/bias check in notebook 01, section 6).
Indicators (everything that depends on IND_KEYS) are computed ONCE in prepare() on the full history, so
slicing IS/OOS keeps the warm-up. run_roughneck_backtest() only uses exit / cost / side rules.
"""
import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE_DEFAULTS = dict(
    data_source="csv_h1",            # csv_h1 (MT5 hourly -> daily 17:00 NY) | csv_daily
    server_tz="UTC",                 # used only when server_ny_offset_h is None (export in a real tz, e.g. "UTC")
    server_ny_offset_h=None,         # MT5 servers on "NY close" time: server = NY + 7h ALL YEAR (GMT+2/+3 with US DST). None = use server_tz
    cutoff_hour_ny=17,               # daily bar closes at 17:00 New York
    financing_bps_per_night=1.5,     # swap proxy, bps of notional per calendar night
    size_fraction=1.0,               # notional as a fraction of equity (robot sizing)
    contract_size=10.0,              # barrels per 1.0 lot (VERIFY in the MT5 symbol specification)
    min_lot=1.0,
    lot_step=1.0,
    quote_to_account=1.0,            # USD quote, USD account
)

IND_KEYS = ("sma_fast", "sma_slow", "trend_lb", "trend_min", "trend_mode", "atr_len", "atr_method",
            "long_low_n", "long_atr_mult", "long_entry_n", "short_high_n", "short_atr_mult", "short_entry_n",
            "early_n", "t1_n", "t2_n")
BASE_RULES = dict(
    # --- indicator rules (prepare) ---
    sma_fast=10, sma_slow=20, trend_lb=10, trend_min=0.25, trend_mode="on",      # trend_mode: on | off (naked trigger)
    atr_len=45, atr_method="sma",                                                 # sma | wilder
    long_low_n=8, long_atr_mult=1.5, long_entry_n=4,
    short_high_n=3, short_atr_mult=2.0, short_entry_n=4,
    early_n=5, t1_n=4, t2_n=2,
    # --- exit / cost / side rules (run) ---
    stop_dollar=1.0, early_days=4, t1_atr=2.0, t2_atr=4.0, t3_atr=5.0, lock_trigger=1.0, lock_level=0.40,
    use_early=True, use_tiers=True, use_lock=True,                                # exit components (False = ablation)
    entry_bar_path="worst",                                                       # worst | ohlc
    side="both",                                                                  # both | long | short  (the direction of the TRADE)
    cost_bps_per_side=4.0,
    # --- inverted logic ---
    mode="trend",                 # trend = LeBeau original | fade = trade AGAINST the signal (market entry at the next open)
    fade_tp_dollar=1.0,           # fade: take-profit distance, $/bbl (mirror of the base stop)
    fade_max_bars=5,              # fade: time stop in bars, the entry bar counts as bar 1
    fade_tie="worst",             # fade, stop AND target inside the same daily bar: worst = stop first (conservative) | half = exit at the
                                  #   midpoint of both levels (expected value if the order is 50/50; use it for the placebo and as the optimistic bracket)
)
TRADE_COLS = ["entry_time", "exit_time", "entry_price", "exit_price", "type", "pnl", "win", "bars", "i_ent", "i_sal",
              "atr_pct", "dist_atr", "pnl_usd", "exit_reason", "pnl_frac"]


def set_engine_defaults(**kw):
    for k, v in kw.items():
        if k not in ENGINE_DEFAULTS:
            raise KeyError(f"unknown engine default: {k}")
        ENGINE_DEFAULTS[k] = v


def _cfg(name, value=None):
    return ENGINE_DEFAULTS[name] if value is None else value


# ------------------------------------------------------------------ data
def _find_csv(ticker):
    """First CSV whose FILE NAME contains `ticker` (case-insensitive), searching the engine folder and 3 parents.
    If you keep several files for the same ticker (H1 and D1), pass csv_path= to load_data()."""
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


def load_data(ticker, start=None, end=None, csv_path=None):
    """MT5 export (<DATE>,<TIME>,<OPEN>...) or time/open/high/low/close. Hourly files are converted to daily bars
    that close at 17:00 New York (weekend-labelled bars are dropped); daily files are used as they are.
    Server time -> NY wall clock: if ENGINE_DEFAULTS['server_ny_offset_h'] is set (e.g. 7) NY = server - 7h with no DST
    handling (brokers on NY-close time); otherwise server_tz is localised and converted with its own DST rules."""
    raw = _read_csv_any_sep(csv_path or _find_csv(ticker))
    raw.columns = [c.strip("<>").lower() for c in raw.columns]
    if "date" in raw.columns and "time" in raw.columns and raw["time"].astype(str).str.contains(":").any():
        t = pd.to_datetime(raw["date"].astype(str) + " " + raw["time"].astype(str))
    else:
        t = pd.to_datetime(raw["date"] if "date" in raw.columns else raw["time"])
    df = pd.DataFrame({c: raw[c].astype(float).to_numpy() for c in ("open", "high", "low", "close")}, index=pd.DatetimeIndex(t))
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    intraday = df.index.to_series().diff().median() < pd.Timedelta(hours=20)
    ENGINE_DEFAULTS["data_source"] = "csv_h1" if intraday else "csv_daily"
    if intraday:
        off = ENGINE_DEFAULTS.get("server_ny_offset_h")
        if off is not None:
            ny = df.index - pd.Timedelta(hours=float(off))                      # naive NY wall clock, constant offset
        else:
            loc = df.index.tz_localize(ENGINE_DEFAULTS["server_tz"], ambiguous="NaT", nonexistent="shift_forward")
            ok = ~pd.isna(loc)
            df, loc = df[ok], loc[ok]
            ny = loc.tz_convert("America/New_York").tz_localize(None)           # naive NY wall clock
        day = (ny + pd.Timedelta(hours=24 - ENGINE_DEFAULTS["cutoff_hour_ny"])).normalize()   # bar labelled by its closing date
        g = df.groupby(np.asarray(day))
        df = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(), "close": g["close"].last()})
        df.index = pd.DatetimeIndex(df.index)
        df = df[df.index.dayofweek < 5]
    df = df.dropna()
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    return df


# ------------------------------------------------------------------ indicators
def _atr(df, n, method):
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() if method == "wilder" else tr.rolling(n).mean()


def prepare(df_raw, **ind):
    """All indicators and signals on the FULL history. ind: any key of IND_KEYS (defaults = BASE_RULES)."""
    bad = set(ind) - set(IND_KEYS)
    if bad:
        raise KeyError(f"not an indicator rule: {sorted(bad)}")
    p = {k: BASE_RULES[k] for k in IND_KEYS}
    p.update(ind)
    d = df_raw[["open", "high", "low", "close"]].copy()
    d["atr"] = _atr(d, int(p["atr_len"]), p["atr_method"])
    d["atr_pct"] = d["atr"] / d["close"] * 100.0
    sma = lambda s, n: s.rolling(int(n)).mean()
    lo20, hi20 = sma(d["low"], p["sma_slow"]), sma(d["high"], p["sma_slow"])
    up = (sma(d["low"], p["sma_fast"]) > lo20) & (lo20 - lo20.shift(int(p["trend_lb"])) >= p["trend_min"])
    dn = (sma(d["high"], p["sma_fast"]) < hi20) & (hi20.shift(int(p["trend_lb"])) - hi20 >= p["trend_min"])
    if p["trend_mode"] == "off":
        up = dn = pd.Series(True, index=d.index)
    ll = lambda n: d["low"].rolling(int(n)).min()
    hh = lambda n: d["high"].rolling(int(n)).max()
    d["long_dist"] = (d["close"] - ll(p["long_low_n"])) / d["atr"]            # trigger distance in ATRs
    d["short_dist"] = (hh(p["short_high_n"]) - d["close"]) / d["atr"]
    d["trend_up"], d["trend_dn"] = up.fillna(False), dn.fillna(False)
    d["long_sig"] = d["trend_up"] & (d["long_dist"] > p["long_atr_mult"])
    d["short_sig"] = d["trend_dn"] & (d["short_dist"] > p["short_atr_mult"]) & ~d["long_sig"]
    d["long_stop_px"], d["short_stop_px"] = hh(p["long_entry_n"]), ll(p["short_entry_n"])
    for n in {int(p["early_n"]), int(p["t1_n"]), int(p["t2_n"])}:
        d[f"LL{n}"], d[f"HH{n}"] = ll(n), hh(n)
    d["warm"] = d["atr"].notna() & d["long_dist"].notna() & lo20.shift(int(p["trend_lb"])).notna()
    d.attrs["ind"] = p
    return d


# ------------------------------------------------------------------ backtest
def _run_fade(d, r):
    """Inverted Roughneck: a LONG signal (thrust up) -> SELL, a SHORT signal -> BUY, at the OPEN of the next bar.
    Exits (all levels known at entry, so no lookahead): stop at -stop_dollar, target at +fade_tp_dollar, time stop after
    fade_max_bars bars at the close. If stop and target fall in the same bar, fade_tie decides: "worst" = stop first (default,
    conservative); "half" = exit at the midpoint of both levels (unbiased if the order is 50/50).
    Gaps through the stop fill at the open (gap_stop); favourable gaps through the target also fill at the open."""
    cb, fin = float(r["cost_bps_per_side"]), float(ENGINE_DEFAULTS["financing_bps_per_night"])
    O, H, L, C = (d[c].to_numpy(float) for c in ("open", "high", "low", "close"))
    ok = d["warm"].to_numpy(bool)
    ls, ss = d["long_sig"].to_numpy(bool) & ok, d["short_sig"].to_numpy(bool) & ok
    ldist, sdist = d["long_dist"].to_numpy(float), d["short_dist"].to_numpy(float)
    idx, n = d.index, len(d)
    allow_l, allow_s = r["side"] in ("both", "long"), r["side"] in ("both", "short")
    stop_d, tp_d, maxb = float(r["stop_dollar"]), float(r["fade_tp_dollar"]), int(r["fade_max_bars"])
    rows, i = [], 1
    while i < n - 1:
        sd = -1 if ls[i] else (1 if ss[i] else 0)            # fade: opposite to the original signal
        if sd == 0 or (sd == 1 and not allow_l) or (sd == -1 and not allow_s):
            i += 1
            continue
        j = i + 1
        E = O[j]
        stop_px, tp_px = E - sd * stop_d, E + sd * tp_d
        last = min(j + maxb - 1, n - 1)
        ex, why = None, None
        for k in range(j, last + 1):
            if k > j:                                         # the entry bar opens AT the entry price: no gap possible
                if (sd == 1 and O[k] <= stop_px) or (sd == -1 and O[k] >= stop_px):
                    ex, why = O[k], "gap_stop"; break
                if (sd == 1 and O[k] >= tp_px) or (sd == -1 and O[k] <= tp_px):
                    ex, why = O[k], "gap_target"; break
            hit_stop = (L[k] <= stop_px) if sd == 1 else (H[k] >= stop_px)
            hit_tp = (H[k] >= tp_px) if sd == 1 else (L[k] <= tp_px)
            if hit_stop and hit_tp and r["fade_tie"] == "half":
                ex, why = 0.5 * (stop_px + tp_px), "both_touched"; break
            if hit_stop:
                ex, why = stop_px, ("stop_entry_bar" if k == j else "stop"); break
            if hit_tp:
                ex, why = tp_px, "target"; break
        else:
            k = last
            ex, why = C[last], ("time" if last == j + maxb - 1 else "end_of_data")
        pnl_usd = (ex - E) * sd
        nights = max((idx[k] - idx[j]).days, 0)
        pnl = pnl_usd / E * 100.0 - 2.0 * cb / 100.0 - fin * nights / 100.0
        rows.append((idx[j], idx[k], E, ex, "long" if sd == 1 else "short", pnl, pnl > 0, k - j + 1, j, k,
                     d["atr_pct"].iat[i], ldist[i] if ls[i] else sdist[i], pnl_usd, why, pnl * _cfg("size_fraction")))
        i = max(k, i + 1)                                      # next signal is evaluated at the close of the exit bar
    return pd.DataFrame(rows, columns=TRADE_COLS)


def run_roughneck_backtest(d, **rules):
    r = {**BASE_RULES, **rules}
    ind = d.attrs.get("ind")
    if ind is not None:
        for k in IND_KEYS:
            if k in rules and rules[k] != ind[k]:
                raise ValueError(f"rule {k}={rules[k]} differs from prepare() ({ind[k]}): call prepare() again")
        r.update({k: ind[k] for k in IND_KEYS})
    if r["mode"] == "fade":
        return _run_fade(d, r)
    cb, fin = float(r["cost_bps_per_side"]), float(ENGINE_DEFAULTS["financing_bps_per_night"])
    O, H, L, C = (d[c].to_numpy(float) for c in ("open", "high", "low", "close"))
    atr, ok = d["atr"].to_numpy(float), d["warm"].to_numpy(bool)
    ls, ss = d["long_sig"].to_numpy(bool) & ok, d["short_sig"].to_numpy(bool) & ok
    lsp, ssp = d["long_stop_px"].to_numpy(float), d["short_stop_px"].to_numpy(float)
    ldist, sdist = d["long_dist"].to_numpy(float), d["short_dist"].to_numpy(float)
    LLe, HHe = d[f"LL{int(r['early_n'])}"].to_numpy(float), d[f"HH{int(r['early_n'])}"].to_numpy(float)
    LL1, HH1 = d[f"LL{int(r['t1_n'])}"].to_numpy(float), d[f"HH{int(r['t1_n'])}"].to_numpy(float)
    LL2, HH2 = d[f"LL{int(r['t2_n'])}"].to_numpy(float), d[f"HH{int(r['t2_n'])}"].to_numpy(float)
    idx, n = d.index, len(d)
    allow_l, allow_s = r["side"] in ("both", "long"), r["side"] in ("both", "short")

    def stop_for(k, j, E, sd, fav_ext, cfav):
        """Stop in force during bar k (information up to the close of k-1)."""
        a, c1, nd = atr[k - 1], C[k - 1], k - j
        if sd == 1:
            s = E - r["stop_dollar"]
            if r["use_early"] and nd < r["early_days"] and c1 < E: s = max(s, LLe[k - 1])
            if r["use_tiers"]:
                if fav_ext - E > r["t3_atr"] * a: s = max(s, L[k - 1])
                elif fav_ext - E > r["t2_atr"] * a: s = max(s, LL2[k - 1])
                elif fav_ext - E > r["t1_atr"] * a: s = max(s, LL1[k - 1])
            if r["use_lock"] and cfav - E >= r["lock_trigger"]: s = max(s, E + r["lock_level"])
        else:
            s = E + r["stop_dollar"]
            if r["use_early"] and nd < r["early_days"] and c1 > E: s = min(s, HHe[k - 1])
            if r["use_tiers"]:
                if E - fav_ext > r["t3_atr"] * a: s = min(s, H[k - 1])
                elif E - fav_ext > r["t2_atr"] * a: s = min(s, HH2[k - 1])
                elif E - fav_ext > r["t1_atr"] * a: s = min(s, HH1[k - 1])
            if r["use_lock"] and E - cfav >= r["lock_trigger"]: s = min(s, E - r["lock_level"])
        return s

    rows, i = [], 1
    while i < n - 1:
        sd = 1 if (allow_l and ls[i]) else (-1 if (allow_s and ss[i]) else 0)
        if not sd:
            i += 1
            continue
        j = i + 1
        stop_px = lsp[i] if sd == 1 else ssp[i]
        if (sd == 1 and H[j] < stop_px) or (sd == -1 and L[j] > stop_px):
            i += 1
            continue                                   # the order was not triggered: it expires
        E = max(stop_px, O[j]) if sd == 1 else min(stop_px, O[j])
        base = E - sd * r["stop_dollar"]
        k, ex, why = j, None, None
        up_bar = C[j] >= O[j]
        if r["entry_bar_path"] == "ohlc":
            hit = ((L[j] <= base) if not up_bar else (C[j] <= base)) if sd == 1 else ((H[j] >= base) if up_bar else (C[j] >= base))
        else:
            hit = (L[j] <= base) if sd == 1 else (H[j] >= base)
        if hit:
            ex, why = base, "stop_entry_bar"
        else:
            fav_ext = L[j] if sd == 1 else H[j]        # MaxTradeLow (long) / lowest high (short)
            cfav = C[j]
            for k in range(j + 1, n):
                s = stop_for(k, j, E, sd, fav_ext, cfav)
                if sd == 1:
                    if O[k] <= s: ex, why = O[k], "gap_stop"; break
                    if L[k] <= s: ex, why = s, "stop"; break
                    fav_ext, cfav = max(fav_ext, L[k]), max(cfav, C[k])
                else:
                    if O[k] >= s: ex, why = O[k], "gap_stop"; break
                    if H[k] >= s: ex, why = s, "stop"; break
                    fav_ext, cfav = min(fav_ext, H[k]), min(cfav, C[k])
            else:
                k, ex, why = n - 1, C[n - 1], "end_of_data"
        pnl_usd = (ex - E) * sd
        nights = max((idx[k] - idx[j]).days, 0)
        pnl = pnl_usd / E * 100.0 - 2.0 * cb / 100.0 - fin * nights / 100.0
        rows.append((idx[j], idx[k], E, ex, "long" if sd == 1 else "short", pnl, pnl > 0, k - j + 1, j, k,
                     d["atr_pct"].iat[i], ldist[i] if sd == 1 else sdist[i], pnl_usd, why,
                     pnl * _cfg("size_fraction")))
        i = max(k, i + 1)                              # next signal is evaluated at the close of the exit bar
    return pd.DataFrame(rows, columns=TRADE_COLS)


# ------------------------------------------------------------------ sizing / paths / returns
def _sizing(sizing, n):
    if isinstance(sizing, str):
        v = {"capital": 1.0, "fraction": float(ENGINE_DEFAULTS["size_fraction"])}[sizing]
        return np.full(n, v)
    a = np.asarray(sizing, float)
    return np.full(n, float(a)) if a.ndim == 0 else a


def trade_mtm_paths(df, trades, sizing="capital"):
    """Per-bar multiplicative returns of every trade; prod(1 + r) = 1 + pnl/100 * size (telescopes exactly)."""
    C, sz, out = df["close"].to_numpy(float), None, []
    sz = _sizing(sizing, len(trades))
    for f, t in zip(sz, trades.itertuples()):
        sd = 1.0 if t.type == "long" else -1.0
        v = (C[t.i_ent:t.i_sal + 1] - t.entry_price) * sd / t.entry_price
        v[-1] = t.pnl / 100.0
        w = 1.0 + f * v
        out.append(w / np.concatenate([[1.0], w[:-1]]) - 1.0)
    return out


def daily_returns(df, trades, sizing="capital"):
    s = np.zeros(len(df))
    for t, p in zip(trades.itertuples(), trade_mtm_paths(df, trades, sizing)):
        s[t.i_ent:t.i_sal + 1] += p
    return pd.Series(s, index=df.index)


hourly_returns = daily_returns   # API compatibility with the hourly engines (bars are daily here)


def _worst_returns(df, trades, sizing):
    """Per-bar return at the worst intrabar point (low for longs, high for shorts); exit bar uses min(extreme, exit)."""
    H, L = df["high"].to_numpy(float), df["low"].to_numpy(float)
    w = np.zeros(len(df))
    sz = _sizing(sizing, len(trades))
    for f, t, p in zip(sz, trades.itertuples(), trade_mtm_paths(df, trades, sizing)):
        sd = 1.0 if t.type == "long" else -1.0
        cum = np.cumprod(1.0 + p)
        prev = np.concatenate([[1.0], cum[:-1]])
        ext = L[t.i_ent:t.i_sal + 1] if sd == 1 else H[t.i_ent:t.i_sal + 1]
        adv = 1.0 + f * (ext - t.entry_price) * sd / t.entry_price
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
    r = daily_returns(df, trades, sizing)
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
    """Capital at which the minimum lot weighs <= target_fraction of equity."""
    e = ENGINE_DEFAULTS
    return e["min_lot"] * e["contract_size"] * price * e["quote_to_account"] / target_fraction


def min_capital_for_stop_risk(stop_dist, risk_frac):
    """Capital at which the minimum lot risks <= risk_frac of equity if the base stop is hit."""
    e = ENGINE_DEFAULTS
    return e["min_lot"] * e["contract_size"] * stop_dist * e["quote_to_account"] / risk_frac


def worst_adverse_move(df, trades):
    """Largest adverse excursion (price units, positive) of any trade, intrabar and including gap exits."""
    H, L, w = df["high"].to_numpy(float), df["low"].to_numpy(float), 0.0
    for t in trades.itertuples():
        a = (t.entry_price - L[t.i_ent:t.i_sal + 1].min()) if t.type == "long" else (H[t.i_ent:t.i_sal + 1].max() - t.entry_price)
        w = max(w, a, -t.pnl_usd)
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
    years before it. The first (partial) year of data never counts as IS. `df` must come from prepare()."""
    t = run_roughneck_backtest(df, **(rules or {}))
    r = daily_returns(df, t, sizing)
    first = df.index[0]
    full = [y for y in sorted(set(df.index.year)) if pd.Timestamp(f"{y}-01-01") >= first]
    rows = []
    for y in sorted(set(df.index.year)):
        prev = [p for p in full if y - is_years <= p < y]
        if len(prev) < is_years or y not in set(df.index.year):
            continue
        is_r = r[(r.index.year >= prev[0]) & (r.index.year <= prev[-1])]
        oos = r[r.index.year == y]
        eq = (1.0 + oos).cumprod()
        rows.append(dict(year=y, ret_is_anual=float((1 + is_r).prod() ** (1.0 / is_years) - 1), ret_oos=float(eq.iloc[-1] - 1),
                         mdd_oos=float((eq / np.maximum(eq.cummax(), 1.0) - 1.0).min()),
                         n_oos=int((pd.to_datetime(t["entry_time"]).dt.year == y).sum())))
    return pd.DataFrame(rows)