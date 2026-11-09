"""
t20_engine.py  -  Top-N Momentum rotation (TIS Strategy #4, T20 version).  Long-only TAA on US large caps.
Rules: monthly rebalance (first Wednesday), rank by 3-month return, Top N equal weight, eligible = price > SMA200 and SMA50,
SPY < SMA200 -> 100% cash, weekly check: stock < its SMA200 -> sell it.
Convention: decision at the CLOSE of day t; execution at the OPEN of t+1 (exec_mode="next_open", no lookahead) or at the close of t ("close").
Data: one daily CSV per ticker (Date,Open,High,Low,Close,Volume; dividend/split adjusted) + SP500 point-in-time membership CSV (ticker,start,end).
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd

EDGE_DIR = Path(__file__).resolve().parent
ENGINE_DEFAULTS = dict(prices_dir="data/t20/prices", membership_csv="data/t20/sp500_membership.csv", benchmark="SPY", data_start="2003-01-01")

def set_engine_defaults(**kw): ENGINE_DEFAULTS.update(kw)
def _res(p): p = Path(p); return p if p.is_absolute() else (EDGE_DIR / p)

class Panel:
    """Aligned daily arrays (dates x tickers) on the benchmark calendar + cached indicators."""
    def __init__(self, open_, close, volume, member, spy_close):
        self.dates, self.tickers = close.index, list(close.columns)
        self.close_df = close
        self.close = close.to_numpy(float)
        self.close_ff = close.ffill().to_numpy(float)                       # last valid close (delisted names keep their last price)
        self.open_f = open_.where(open_.notna(), close).ffill().to_numpy(float)
        self.adv = volume.rolling(50, min_periods=20).mean().to_numpy(float)  # 50-day average volume, SHARES
        self.member = member.to_numpy(bool)
        self.spy = spy_close.reindex(self.dates)
        self._sma, self._mom = {}, {}
    def sma(self, n):
        if n not in self._sma: self._sma[n] = self.close_df.rolling(n, min_periods=n).mean().to_numpy(float)
        return self._sma[n]
    def mom(self, lb):
        if lb not in self._mom: self._mom[lb] = (self.close_df / self.close_df.shift(lb) - 1).to_numpy(float)
        return self._mom[lb]
    def spy_ok(self, n): return (self.spy > self.spy.rolling(n, min_periods=n).mean()).to_numpy(bool)

def load_panel(prices_dir=None, membership_csv=None, benchmark=None, start=None):
    prices_dir, membership_csv = _res(prices_dir or ENGINE_DEFAULTS["prices_dir"]), _res(membership_csv or ENGINE_DEFAULTS["membership_csv"])
    benchmark, start = (benchmark or ENGINE_DEFAULTS["benchmark"]).upper(), start or ENGINE_DEFAULTS["data_start"]
    raw = {}
    for f in sorted(prices_dir.glob("*.csv")):
        d = pd.read_csv(f, parse_dates=["Date"], index_col="Date").sort_index()
        raw[f.stem.upper()] = d[["Open", "Close", "Volume"]]
    if benchmark not in raw: raise FileNotFoundError(f"{benchmark}.csv not found in {prices_dir}")
    spy = raw.pop(benchmark)
    idx = spy.index[spy.index >= pd.Timestamp(start)]
    O, C, V = (pd.DataFrame({k: v[c] for k, v in raw.items()}).reindex(idx) for c in ("Open", "Close", "Volume"))
    mem = pd.DataFrame(False, index=idx, columns=C.columns)
    if membership_csv.exists():
        m = pd.read_csv(membership_csv, parse_dates=["start", "end"])
        m["ticker"] = m["ticker"].str.upper()
        for r in m.itertuples():
            if r.ticker in mem.columns:
                mem.loc[(mem.index >= r.start) & ((mem.index <= r.end) if pd.notna(r.end) else True), r.ticker] = True
    else:
        print(f"WARNING: {membership_csv.name} not found -> every ticker is eligible on every date (SURVIVORSHIP / look-ahead risk).")
        mem[:] = True
    return Panel(O, C, V, mem, spy["Close"].reindex(idx))

_ORD = {"first": 1, "second": 2, "third": 3}
_DOW = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}
def calendar_flags(dates, rule="first_wednesday"):
    """(rebalance flags, weekly-check flags). rule: first_trading_day | <first|second|third>_<weekday>."""
    reb = np.zeros(len(dates), bool); per = dates.to_period("M")
    for p in pd.unique(per):
        m = np.flatnonzero(per == p)
        if rule == "first_trading_day": reb[m[0]] = True; continue
        o, d = rule.split("_"); days = [i for i in m if dates[i].weekday() == _DOW[d]]
        target = dates[days[min(_ORD[o], len(days)) - 1]] if days else dates[m[0]]
        reb[m[np.searchsorted(dates[m], target)] if np.searchsorted(dates[m], target) < len(m) else m[-1]] = True
    wk = dates.to_period("W"); chk = np.r_[wk[1:] != wk[:-1], True]       # last trading day of each week (executes next open = Monday)
    return reb, chk

TRADE_COLS = ["ticker", "entry_time", "exit_time", "entry_price", "exit_price", "pnl", "win", "days", "reason", "usd"]

def run_backtest(P, lookback_days=63, top_n=20, slip_bps_per_side=5.0, exec_mode="next_open", spy_ma=200, stock_ma=200, fast_ma=50,
                 min_adv_shares=2_000_000, rebalance="first_wednesday", weekly_checks=True, market_filter=True, stock_stop=True,
                 stock_trend=True, sim_start=None, sim_end=None, selector=None, rng=None, cash_yield=0.0):
    """Return dict(trades, equity, ret, npos). Equity starts at 1.0 at the first simulated day. selector(t, idx, rng) -> ordered idx (monkey test)."""
    T, K, slip = len(P.dates), len(P.tickers), slip_bps_per_side / 1e4
    mom, smaS, smaF, ok = P.mom(lookback_days), P.sma(stock_ma), P.sma(fast_ma), (P.spy_ok(spy_ma) if market_filter else np.ones(T, bool))
    reb, chk = calendar_flags(P.dates, rebalance)
    warm = max(spy_ma, stock_ma, fast_ma, lookback_days) + 1
    t0 = max(warm, int(P.dates.searchsorted(pd.Timestamp(sim_start)) if sim_start is not None else 0))
    t1 = (int(P.dates.searchsorted(pd.Timestamp(sim_end))) - 1) if sim_end is not None else T - 1
    sh, ent_px, ent_t, cash = np.zeros(K), np.zeros(K), np.zeros(K, int), 1.0
    eq, npos, trades, pend = np.full(T, np.nan), np.zeros(T, int), [], None

    def do_sell(j, t, px, reason):
        nonlocal cash
        p = px * (1 - slip); cash += sh[j] * p
        trades.append((P.tickers[j], P.dates[ent_t[j]], P.dates[t], ent_px[j], p, p / ent_px[j] - 1, p > ent_px[j], t - ent_t[j], reason, sh[j] * ent_px[j]))
        sh[j] = 0.0

    def execute(order, t, px):
        nonlocal cash
        sells, buys, eqd, why = order
        for j in np.flatnonzero(sells & (sh > 0)): do_sell(j, t, px[j], why[j])
        buys = [j for j in buys if sh[j] == 0 and px[j] > 0]
        if buys:
            alloc = min(eqd / top_n, cash / len(buys))
            for j in buys:
                p = px[j] * (1 + slip); sh[j] = alloc / p; cash -= alloc; ent_px[j], ent_t[j] = p, t

    def decide(t):
        held = sh > 0
        sells = held.copy() if not ok[t] else (held & (P.close[t] < smaS[t]) if stock_stop else np.zeros(K, bool))
        why = np.full(K, "market_filter" if not ok[t] else "stop", dtype=object)
        buys = []
        if reb[t] and ok[t]:
            el = P.member[t] & ~np.isnan(mom[t]) & (P.adv[t] >= min_adv_shares) & ~np.isnan(P.close[t])
            if stock_trend: el &= (P.close[t] > smaS[t]) & (P.close[t] > smaF[t])
            idx = np.flatnonzero(el)
            sel = (idx[np.argsort(-mom[t, idx], kind="stable")] if selector is None else np.asarray(selector(t, idx, rng), int))[:top_n]
            tgt = np.zeros(K, bool); tgt[sel] = True
            why[held & ~tgt & ~sells] = "rebalance"; sells |= held & ~tgt
            keep = held & ~sells
            buys = [j for j in sel if not keep[j]]
        return sells, buys, eq[t], why

    for t in range(t0, t1 + 1):
        cash *= 1 + cash_yield / 252
        h = np.flatnonzero(sh > 0)
        for j in h[np.isnan(P.close[t, h])]: do_sell(j, t, P.close_ff[t, j], "delisted")      # no more prices: out at the last close
        if pend is not None: execute(pend, t, P.open_f[t]); pend = None
        h = np.flatnonzero(sh > 0); eq[t] = cash + (sh[h] * P.close_ff[t, h]).sum()
        if (reb[t] or (weekly_checks and chk[t])) and t < t1:
            order = decide(t)
            if exec_mode == "close":
                execute(order, t, P.close_ff[t]); h = np.flatnonzero(sh > 0); eq[t] = cash + (sh[h] * P.close_ff[t, h]).sum()
            else: pend = order
        npos[t] = int((sh > 0).sum())
    for j in np.flatnonzero(sh > 0):                                                          # mark open positions (excluded from trade stats)
        p = P.close_ff[t1, j]; trades.append((P.tickers[j], P.dates[ent_t[j]], P.dates[t1], ent_px[j], p, p / ent_px[j] - 1, p > ent_px[j], t1 - ent_t[j], "open", sh[j] * ent_px[j]))
    s = pd.Series(eq, P.dates).iloc[t0:t1 + 1]
    return dict(trades=pd.DataFrame(trades, columns=TRADE_COLS), equity=s / s.iloc[0], ret=s.pct_change().fillna(0.0), npos=pd.Series(npos, P.dates).iloc[t0:t1 + 1])

# ------------------------------------------------------------------ metrics
def drawdown(ret): e = (1 + ret).cumprod(); return e / e.cummax() - 1
def perf(ret, ppy=252):
    ret = pd.Series(ret).dropna(); y = len(ret) / ppy
    tot = (1 + ret).prod(); sd = ret.std(ddof=1)
    mdd = drawdown(ret).min() if len(ret) else np.nan
    cagr = tot ** (1 / y) - 1 if y > 0 and tot > 0 else np.nan
    return dict(cagr=cagr, vol=sd * np.sqrt(ppy), sharpe=ret.mean() / sd * np.sqrt(ppy) if sd > 0 else np.nan, max_dd=mdd,
                calmar=cagr / abs(mdd) if mdd and mdd < 0 else np.nan, total=tot - 1, years=y)
def tstat(x):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan
def monthly(ret): return (1 + ret).resample("ME").prod() - 1
def trade_stats(trades):
    c = trades[trades["reason"] != "open"]; x = c["pnl"].to_numpy(float)
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    return dict(n=len(x), mean_pct=100 * x.mean() if len(x) else np.nan, win_pct=100 * (x > 0).mean() if len(x) else np.nan,
                pf=g / l if l > 0 else np.inf, payoff=(x[x > 0].mean() / -x[x < 0].mean()) if (x > 0).any() and (x < 0).any() else np.nan,
                avg_days=c["days"].mean() if len(c) else np.nan)
def annual(ret, hard_limit=None):
    rows = []
    for y, r in ret.groupby(ret.index.year):
        rows.append(dict(year=y, ret=(1 + r).prod() - 1, mdd=drawdown(r).min(), days=len(r), partial=len(r) < 240,
                         breach=bool(hard_limit is not None and drawdown(r).min() < -hard_limit)))
    return pd.DataFrame(rows)
def scale_ret(ret, fraction): return ret * fraction           # fraction of capital allocated (rest idle cash)
def fraction_for_limit(ret, hard_limit, tol=1e-4):
    lo, hi = 0.0, 1.0
    if drawdown(ret).min() >= -hard_limit: return 1.0
    while hi - lo > tol:
        mid = (lo + hi) / 2
        (lo, hi) = (mid, hi) if drawdown(ret * mid).min() >= -hard_limit else (lo, mid)
    return lo
def benchmark_ret(P, ret): return P.spy.pct_change().reindex(ret.index).fillna(0.0)
def block_bootstrap(ret, n=5000, block=21, seed=1):
    r, rng = ret.to_numpy(float), np.random.default_rng(seed); T = len(r); nb = -(-T // block); out = []
    for _ in range(n):
        s = rng.integers(0, T - block, nb); x = np.concatenate([r[i:i + block] for i in s])[:T]
        e = np.cumprod(1 + x); out.append((e[-1] ** (252 / T) - 1, (e / np.maximum.accumulate(e) - 1).min(), x.mean() / x.std(ddof=1) * np.sqrt(252)))
    return pd.DataFrame(out, columns=["cagr", "max_dd", "sharpe"])
def walk_forward(ret, is_years=3, oos_years=1):
    """Fixed rules (nothing is re-fitted): rolling windows of the SAME run. Returns one row per OOS window."""
    rows, y0 = [], ret.index[0].year
    for y in range(y0 + is_years, ret.index[-1].year + 1, oos_years):
        a, b = ret[(ret.index.year >= y - is_years) & (ret.index.year < y)], ret[(ret.index.year >= y) & (ret.index.year < y + oos_years)]
        if len(b) > 60: rows.append(dict(oos_year=y, is_sharpe=perf(a)["sharpe"], oos_sharpe=perf(b)["sharpe"], oos_ret=perf(b)["total"], oos_mdd=perf(b)["max_dd"]))
    return pd.DataFrame(rows)
def random_selector(t, idx, rng): return rng.permutation(idx)
def monkey(P, rules, n=300, seed=7, **kw):
    """Same rules (filters, calendar, costs, stops) but the Top N is picked AT RANDOM among eligible names."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame([perf(run_backtest(P, **rules, selector=random_selector, rng=rng, **kw)["ret"]) for _ in range(n)])[["cagr", "sharpe", "max_dd"]]
def grid(P, lookbacks, tops, rules, **kw):
    rows = []
    for lb in lookbacks:
        for n in tops:
            r = run_backtest(P, **{**rules, "lookback_days": lb, "top_n": n}, **kw); m = perf(r["ret"]); ts = trade_stats(r["trades"])
            rows.append(dict(lookback=lb, top_n=n, cagr=m["cagr"], sharpe=m["sharpe"], max_dd=m["max_dd"], pf=ts["pf"], n=ts["n"]))
    return pd.DataFrame(rows)
