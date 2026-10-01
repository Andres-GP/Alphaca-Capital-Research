"""
edge_decay.py  ·  research_development/utils/edge_decay.py
Is the edge fading? Rolling PF, PF by year, recent vs historical comparison.
"""
import numpy as np
import pandas as pd
from robustness import profit_factor, BG, PANEL_BG, GRID, SUBTEXT, TEXT, GREEN, RED, ORANGE


def rolling_pf(trades_df, window=40, cap=8.0, date_col="exit_time"):
    pnl = trades_df["pnl"].to_numpy(float)
    dates = pd.to_datetime(trades_df[date_col]).to_numpy()
    rows = [(dates[i - 1], min(profit_factor(pnl[i - window:i]), cap), pnl[i - window:i].mean())
            for i in range(window, len(pnl) + 1)]
    return pd.DataFrame(rows, columns=["date", "pf", "expectancy"]).set_index("date")


def pf_by_year(trades_df, date_col="exit_time"):
    t = trades_df.copy()
    t["year"] = pd.to_datetime(t[date_col]).dt.year
    g = t.groupby("year")["pnl"]
    return pd.DataFrame({
        "n": g.size(), "pf": g.apply(profit_factor), "expectancy": g.mean(),
        "win_rate": g.apply(lambda s: (s > 0).mean()), "total_pnl": g.sum(),
    })


def edge_decay_summary(trades_df, last_n=3, date_col="exit_time", min_ratio=0.5):
    """
    Compares the last `last_n` full years vs everything before them.
    The last year in the data is treated as partial and excluded from 'recent'.
    warning = recent PF < 1, or recent expectancy < min_ratio * historical expectancy.
    """
    t = trades_df.copy()
    t["year"] = pd.to_datetime(t[date_col]).dt.year
    last = t["year"].max()
    recent = t[(t["year"] >= last - last_n) & (t["year"] < last)]
    hist = t[t["year"] < last - last_n]

    def agg(x):
        if len(x) == 0:
            return dict(trades_per_year=np.nan, expectancy=np.nan, pf=np.nan)
        return dict(trades_per_year=len(x) / max(x["year"].nunique(), 1),
                    expectancy=float(x["pnl"].mean()), pf=float(profit_factor(x["pnl"])))

    h, r = agg(hist), agg(recent)
    ratio = r["expectancy"] / h["expectancy"] if h["expectancy"] and h["expectancy"] > 0 else np.nan
    warning = bool((r["pf"] < 1) or (np.isfinite(ratio) and ratio < min_ratio))
    return dict(historical=h, recent=r, recent_years=sorted(recent["year"].unique().tolist()),
                expectancy_ratio=ratio, warning=warning)


def plot_rolling_pf(roll, oos_start=None, window=40):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(12, 4.5), facecolor=BG)
    ax.set_facecolor(PANEL_BG)
    ax.plot(roll.index, roll["pf"], color=GREEN, lw=1.8)
    ax.axhline(1, color=RED, lw=1.2)
    ax.axhline(1.3, color=ORANGE, ls="--", lw=1)
    if oos_start is not None:
        ax.axvline(pd.Timestamp(oos_start), color=SUBTEXT, ls=":")
        ax.text(pd.Timestamp(oos_start), ax.get_ylim()[1] * 0.95, "  out of sample →", color=SUBTEXT)
    ax.set_ylabel(f"PF of last {window} trades", color=SUBTEXT)
    ax.set_title("Is the edge fading? Rolling Profit Factor", color=TEXT, loc="left", fontweight="bold")
    ax.tick_params(colors=SUBTEXT); ax.grid(color=GRID, alpha=0.8)
    plt.show()