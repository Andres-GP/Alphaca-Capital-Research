"""BTC-overnight helpers (shared helpers stay in utils/: compute_metrics, metrics, robustness, edge_decay, validation_gate).

monkey_test_sided: same output keys as robustness.monkey_test (pf_real, pf_monkey_median, pct_pf, pct_expectancy, pfs, exps)
and the same code as the Roughneck helper: it keeps the direction and the holding time (bars) of every real trade.
Entries are drawn at random ELIGIBLE bars, exits at the same bar distance (here bars are HOURS).

eligible: None (every bar) | bool Series (same for both sides) | dict {"long": Series, "short": Series}.
fin_bps_per_night: calendar-night swap proxy. For this edge pass 0.0: the swap depends on crossing the 17:00 NY rollover,
not on calendar nights, so monkeys pay costs but NOT swap (conservative AGAINST the strategy, which does pay it).
"""
import numpy as np
import pandas as pd


def _pf(x):
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    return np.inf if l == 0 and g > 0 else (g / l if l > 0 else np.nan)


def _elig(eligible, df, side):
    n = len(df)
    if eligible is None:
        return np.ones(n, bool)
    e = eligible[side] if isinstance(eligible, dict) else eligible
    return e.reindex(df.index).fillna(False).to_numpy(bool)


def monkey_test_sided(df, trades, eligible=None, n_sim=2000, cost_pct_per_side=0.0, fin_bps_per_night=0.0,
                      seed=42, entry_col="open", exit_col="open"):
    rng = np.random.default_rng(seed)
    px_in, px_out = df[entry_col].to_numpy(float), df[exit_col].to_numpy(float)
    n = len(df)
    days = df.index.values.astype("datetime64[D]").astype(np.int64)
    is_long = (trades["type"].to_numpy() == "long")
    sd = np.where(is_long, 1.0, -1.0)
    bars = trades["bars"].to_numpy(int)
    real = trades["pnl"].to_numpy(float)
    pf_real, exp_real = _pf(real), real.mean()
    sides = {}
    for name, mask in (("long", is_long), ("short", ~is_long)):
        if not mask.any():
            continue
        ok = _elig(eligible, df, name)
        lim = n - int(bars[mask].max()) - 1
        cand = np.flatnonzero(ok[:max(lim, 0)])
        if len(cand) == 0:
            raise ValueError(f"monkey_test_sided: no eligible entry bars for {name} trades")
        sides[name] = (np.flatnonzero(mask), cand)
    pfs, exps = np.empty(n_sim), np.empty(n_sim)
    for s in range(n_sim):
        e = np.empty(len(trades), int)
        for idx, cand in sides.values():
            e[idx] = rng.choice(cand, size=len(idx), replace=True)
        x = e + bars
        nights = days[x] - days[e]
        pnl = (px_out[x] / px_in[e] - 1.0) * 100.0 * sd - 2.0 * cost_pct_per_side - fin_bps_per_night * nights / 100.0
        pfs[s], exps[s] = _pf(pnl), pnl.mean()
    return dict(pf_real=float(pf_real), pf_monkey_median=float(np.nanmedian(pfs)),
                pct_pf=float(np.mean(pf_real > pfs)), pct_expectancy=float(np.mean(exp_real > exps)), pfs=pfs, exps=exps)