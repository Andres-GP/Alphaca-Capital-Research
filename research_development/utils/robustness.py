"""
robustness.py  ·  research_development/utils/robustness.py

Trade-level robustness tests. Input convention (same as utils.run_backtest):
    trades_df with 'pnl' in PERCENT per trade, plus 'entry_time' / 'exit_time'.
"""
import numpy as np
import pandas as pd

BG, PANEL_BG, GRID = "#15171c", "#1b1e26", "#2a2d37"
TEXT, SUBTEXT = "#e8e9ec", "#9aa0ab"
GREEN, RED, ORANGE = "#34d399", "#f0555a", "#f5a524"


def profit_factor(pnl):
    pnl = np.asarray(pnl, dtype=float)
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    if losses == 0:
        return np.inf if gains > 0 else 0.0
    return gains / losses


def equity_paths(r, mode="additive"):
    """r: (m, n) per-trade returns as fractions -> equity paths (m, n+1) starting at 1."""
    eq = np.cumprod(1 + r, axis=1) if mode == "compound" else 1 + np.cumsum(r, axis=1)
    return np.hstack([np.ones((r.shape[0], 1)), eq])


def max_dd_paths(eq):
    peak = np.maximum.accumulate(eq, axis=1)
    return ((eq - peak) / peak).min(axis=1)


# ------------------------------------------------------------------ 1. Block Monte Carlo
def monte_carlo_block(trades_df, n_sim=10000, block=5, mode="additive",
                      ruin_level=-0.5, dd_limit=-0.25, seed=42, chunk=1000,
                      mtm_paths=None):
    """
    Circular block bootstrap of the trade sequence (keeps winning/losing streaks).
    mode='additive' (fixed size per trade, futures) or 'compound' (reinvesting).
    ruin_level: MAX DRAWDOWN that counts as ruin (-0.5 = a 50% drawdown from peak).
                prob_ruin = share of simulated paths whose max drawdown is <= ruin_level.
    mtm_paths: optional list of 1-D arrays (one per row of trades_df, same order) with the
               daily mark-to-market returns of each trade (see rsi2_engine.trade_mtm_paths).
               When given, trades are still resampled in blocks, but the equity path of
               each simulation is built by concatenating the daily paths of the sampled
               trades, so drawdowns are measured on daily MTM instead of trade by trade.
               When None, drawdowns are measured trade by trade (previous behavior).
    """
    r = trades_df["pnl"].to_numpy(float) / 100.0
    n = len(r)
    if n < 10:
        raise ValueError("Need at least 10 trades")
    block = max(1, min(block, n))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    offs = np.arange(block)

    paths = None
    if mtm_paths is not None:
        if len(mtm_paths) != n:
            raise ValueError("mtm_paths must have one entry per trade (same order as trades_df)")
        L = max(len(p) for p in mtm_paths)
        paths = np.zeros((n, L))            # zero-padded: a 0 return leaves the equity unchanged
        for i, p in enumerate(mtm_paths):
            paths[i, :len(p)] = p
        chunk = max(1, min(chunk, int(5e6 // (n * L))))   # keep memory bounded

    rets, mdds = [], []
    for start in range(0, n_sim, chunk):
        m = min(chunk, n_sim - start)
        starts = rng.integers(0, n, size=(m, n_blocks))
        idx = ((starts[:, :, None] + offs) % n).reshape(m, -1)[:, :n]
        r_sim = r[idx] if paths is None else paths[idx].reshape(m, -1)
        eq = equity_paths(r_sim, mode)
        rets.append(eq[:, -1] - 1)
        mdds.append(max_dd_paths(eq))
    rets, mdds = np.concatenate(rets), np.concatenate(mdds)

    real_r = r[None, :] if paths is None else paths.reshape(1, -1)
    real_eq = equity_paths(real_r, mode)
    real_ret, real_mdd = float(real_eq[0, -1] - 1), float(max_dd_paths(real_eq)[0])
    return dict(
        n_sim=n_sim, block=block, mode=mode, n_trades=n,
        dd_basis="trade" if paths is None else "mtm",
        ret_p5=float(np.percentile(rets, 5)), ret_p50=float(np.median(rets)), ret_p95=float(np.percentile(rets, 95)),
        mdd_p5=float(np.percentile(mdds, 5)),   # the worst 5% of paths
        mdd_p50=float(np.median(mdds)), mdd_worst=float(mdds.min()),
        prob_positive=float((rets > 0).mean()), prob_dd_worse_than_limit=float((mdds < dd_limit).mean()),
        prob_ruin=float((mdds <= ruin_level).mean()),
        real_ret=real_ret, real_mdd=real_mdd,
        pct_sims_worse_mdd_than_real=float((mdds < real_mdd).mean()),
        rets=rets, mdds=mdds,
    )


# ------------------------------------------------------------------ 2. Monkey test
def monkey_test(df, trades_df, eligible=None, n_sim=2000, entry_col="close",
                exit_col="close", cost_pct_per_side=0.0, seed=42):
    """
    Random entries with the same number of trades and the same holding times (in bars).
    df: price bars; its index must contain the trades' entry_time / exit_time.
    eligible: boolean Series on df.index = days/bars where the strategy is ALLOWED to enter
              (its filters, not its signal). None = every bar.
    entry_col='close' matches utils.run_backtest (enters at the signal bar's close).
    For next-open systems use entry_col='open'.
    trades_df['pnl'] is taken as-is; monkeys pay 2 * cost_pct_per_side.
    NOTE: monkeys exit after a fixed number of bars. For stop/target strategies the
    comparison is approximate; it is cleanest for time/signal exits.
    """
    pos_in = df.index.get_indexer(pd.DatetimeIndex(trades_df["entry_time"]))
    pos_out = df.index.get_indexer(pd.DatetimeIndex(trades_df["exit_time"]))
    ok = (pos_in >= 0) & (pos_out >= pos_in)
    if ok.sum() < 10:
        raise ValueError("Fewer than 10 trades match df.index (check timestamps)")
    dur = (pos_out - pos_in)[ok]
    real_pnl = trades_df["pnl"].to_numpy(float)[ok]
    n = len(dur)

    px_in, px_out = df[entry_col].to_numpy(float), df[exit_col].to_numpy(float)
    mask = np.ones(len(df), bool) if eligible is None else eligible.reindex(df.index).fillna(False).to_numpy(bool)
    mask[-1] = False
    elig = np.flatnonzero(mask)
    if len(elig) == 0:
        raise ValueError("No eligible bars")

    rng = np.random.default_rng(seed)
    replace, cost = len(elig) < n, 2 * cost_pct_per_side
    pfs, exps = [], []
    for _ in range(n_sim):
        ent = elig[rng.choice(len(elig), size=n, replace=replace)]
        ex = np.minimum(ent + rng.choice(dur, size=n), len(df) - 1)
        pnl = (px_out[ex] / px_in[ent] - 1) * 100 - cost
        pfs.append(profit_factor(pnl))
        exps.append(pnl.mean())
    pfs, exps = np.array(pfs), np.array(exps)
    pf_real, exp_real = profit_factor(real_pnl), float(real_pnl.mean())
    return dict(
        n_sim=n_sim, n_trades=n, pf_real=float(pf_real), expectancy_real=exp_real,
        pct_pf=float((pfs < pf_real).mean()),            # share of monkeys the strategy beats
        pct_expectancy=float((exps < exp_real).mean()),
        pf_monkey_median=float(np.median(pfs)), expectancy_monkey_median=float(np.median(exps)),
        pfs=pfs,
    )


# ------------------------------------------------------------------ 3. Grid + plateau
def grid_search(evaluate, a_values, b_values):
    """
    evaluate(a, b) -> (profit_factor, n_trades) or None. Run it on IN-SAMPLE data only.
    Returns two DataFrames (rows = a_values, columns = b_values): pf, n.
    """
    pf = pd.DataFrame(np.nan, index=list(a_values), columns=list(b_values))
    n = pd.DataFrame(0.0, index=list(a_values), columns=list(b_values))
    for a in a_values:
        for b in b_values:
            res = evaluate(a, b)
            if res is not None:
                pf.loc[a, b], n.loc[a, b] = res
    return pf, n


def plateau_check(pf, n, chosen, pf_min=1.3, n_min=30, max_drop_pct=30):
    """
    chosen = (a, b) of the parameters you trade.
    plateau  : every cell in the 3x3 neighborhood has PF >= pf_min and n >= n_min
    anticliff: PF never drops more than max_drop_pct when you move one step away
    """
    ia, ib = pf.index.get_loc(chosen[0]), pf.columns.get_loc(chosen[1])
    sl_a, sl_b = slice(max(ia - 1, 0), ia + 2), slice(max(ib - 1, 0), ib + 2)
    nb, nb_n = pf.iloc[sl_a, sl_b], n.iloc[sl_a, sl_b]
    center = pf.iloc[ia, ib]
    plateau = bool(nb.notna().all().all() and (nb >= pf_min).all().all() and (nb_n >= n_min).all().all())
    drop = float((1 - nb / center).max().max() * 100) if center and center > 0 else np.inf
    best = pf.stack().idxmax()
    return dict(
        center_pf=float(center), plateau=plateau, worst_neighbor_drop_pct=drop,
        anticliff=bool(drop <= max_drop_pct), passed=bool(plateau and drop <= max_drop_pct),
        pct_cells_pf_ok=float((pf.stack() >= pf_min).mean()),
        best_cell=best, best_pf=float(pf.stack().max()),
        edge_of_grid=bool(ia in (0, len(pf.index) - 1) or ib in (0, len(pf.columns) - 1)),
    )


# ------------------------------------------------------------------ plots
def plot_grid(pf, n, chosen, title="Parameter grid · Profit Factor (in-sample)", vmin=1.0, vmax=None):
    import matplotlib.pyplot as plt
    vmax = vmax or max(2.5, float(np.nanmax(pf.values)))
    fig, ax = plt.subplots(figsize=(9, 5.5), facecolor=BG)
    ax.set_facecolor(PANEL_BG)
    im = ax.imshow(pf.values.astype(float), cmap="Greens", vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(pf.columns))); ax.set_xticklabels(pf.columns, color=SUBTEXT)
    ax.set_yticks(range(len(pf.index))); ax.set_yticklabels(pf.index, color=SUBTEXT)
    for i in range(pf.shape[0]):
        for j in range(pf.shape[1]):
            v = pf.iloc[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:.2f}\nN={int(n.iloc[i, j])}", ha="center", va="center", fontsize=8,
                        color="white" if v > 0.7 * vmax else "#132620")
    ia, ib = pf.index.get_loc(chosen[0]), pf.columns.get_loc(chosen[1])
    ax.add_patch(plt.Rectangle((ib - .5, ia - .5), 1, 1, fill=False, ec=ORANGE, lw=3))
    ax.set_title(title, color=TEXT, loc="left", fontweight="bold")
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8)
    plt.show()


def plot_monkey(mk, title="Monkey test · Profit Factor"):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 4), facecolor=BG)
    ax.set_facecolor(PANEL_BG)
    pfs = mk["pfs"][np.isfinite(mk["pfs"])]
    ax.hist(pfs, bins=45, color="#5468ff", alpha=0.75, edgecolor=BG)
    ax.axvline(mk["pf_real"], color=GREEN, lw=3)
    ax.axvline(mk["pf_monkey_median"], color=ORANGE, ls="--")
    ax.text(mk["pf_real"], ax.get_ylim()[1] * 0.9, f"  strategy PF {mk['pf_real']:.2f}\n  beats {mk['pct_pf']*100:.1f}% of monkeys",
            color=GREEN, fontweight="bold")
    ax.set_title(title, color=TEXT, loc="left", fontweight="bold")
    ax.tick_params(colors=SUBTEXT); ax.grid(color=GRID, alpha=0.8)
    plt.show()