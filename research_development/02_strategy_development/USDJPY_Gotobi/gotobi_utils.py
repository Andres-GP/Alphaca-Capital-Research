"""
gotobi_utils.py  ·  02_strategy_development/Gotobi/gotobi_utils.py   (v1.0)

Edge-local helpers shared by the Gotobi notebooks (01 hypothesis, 02 sensitivity, 03 robustness, 04 reconciliation).
Nothing here depends on gotobi_engine except `engine_overrides`, which receives the engine module as an argument.

    Theme / plots   : dark_ax, subplots, set_title, legend, plot_annual_returns
    PASS/FAIL gate  : Checks  (one registry per notebook; section 8 groups it, section 9 saves it)
    Small stats     : tstat, mean_se, welch, profit_factor, drawdown, interp_zero
    Engine helpers  : engine_overrides (temporary ENGINE_DEFAULTS), independent_gotobi_dates (calendar cross-check)
"""
from __future__ import annotations

import calendar
import contextlib
import datetime as dt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

# ------------------------------------------------------------------ theme
BG, PANEL, GRIDC, TXT, SUB = "#15171c", "#1b1e26", "#2a2d37", "#e8e9ec", "#9aa0ab"
GREEN, RED, ORANGE, BLUE = "#34d399", "#f0555a", "#f5a524", "#5468ff"


def dark_ax(ax, grid=True):
    """Apply the dark research theme to one axis."""
    ax.set_facecolor(PANEL)
    ax.grid(grid, color=GRIDC, lw=0.8, alpha=0.9)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=SUB, labelsize=9)
    return ax


def subplots(nrows=1, ncols=1, figsize=(12, 4), grid=True, **kw):
    """plt.subplots with the dark theme already applied to every axis."""
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, facecolor=BG, **kw)
    for ax in np.atleast_1d(axes).ravel():
        dark_ax(ax, grid)
    return fig, axes


def set_title(ax, text):
    ax.set_title(text, color=TXT, fontweight="bold", loc="left")


def legend(ax, loc="upper left"):
    ax.legend(frameon=False, labelcolor=SUB, fontsize=9, loc=loc)


def plot_annual_returns(annual, report, hard_limit):
    """Annual return bars (top) and in-year max drawdown bars (bottom) against the hard limit."""
    fig, (ax_ret, ax_dd) = subplots(2, 1, figsize=(11, 6.5), grid=False, sharex=True)
    years = annual["year"].astype(str).to_numpy()
    bars = ax_ret.bar(years, annual["ret"] * 100, color=[GREEN if v >= 0 else RED for v in annual["ret"]])
    ax_dd.bar(years, annual["mdd"] * 100, color=[RED if b else SUB for b in annual["breach"]])
    ax_dd.axhline(-hard_limit * 100, color=ORANGE, ls="--", lw=1.2)
    for rect, value, partial in zip(bars, annual["ret"], annual["partial"]):
        ax_ret.annotate(f"{value:+.1%}" + ("*" if partial else ""), (rect.get_x() + rect.get_width() / 2, value * 100),
                        xytext=(0, 3 if value >= 0 else -3), textcoords="offset points",
                        ha="center", va="bottom" if value >= 0 else "top", color=TXT, fontsize=9)
    set_title(ax_ret, f"Annual returns · hard limit -{hard_limit:.0%} · max DD {report['max_dd']:.1%} · "
                      f"{'PASS' if report['passed'] else 'FAIL'}")
    ax_ret.set_ylabel("Return %", color=SUB)
    ax_dd.set_ylabel("Max DD in year %", color=SUB)
    plt.tight_layout()
    plt.show()


# ------------------------------------------------------------------ PASS / FAIL registry
class Checks:
    """Registry of PASS / FAIL / SKIP checks. Calling the instance registers one check.
    Re-running a cell overwrites its previous entries instead of duplicating them."""

    def __init__(self):
        self.items: list[dict] = []

    def __call__(self, section, name, passed, detail="", quiet=False):
        status = "SKIP" if passed is None else ("PASS" if bool(passed) else "FAIL")
        entry = {"section": section, "name": name, "status": status, "detail": detail}
        for i, c in enumerate(self.items):
            if c["section"] == section and c["name"] == name:
                self.items[i] = entry
                break
        else:
            self.items.append(entry)
        if not quiet:
            print(f"   [{status}] {name}" + (f"  ->  {detail}" if detail else ""))
        return status

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.items)

    def counts(self) -> dict:
        s = [c["status"] for c in self.items]
        return {k: s.count(k) for k in ("PASS", "FAIL", "SKIP")}


# ------------------------------------------------------------------ small statistics
def tstat(x) -> float:
    """t-statistic of the mean (NaN if fewer than 3 observations or zero variance)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    sd = x.std(ddof=1) if len(x) > 2 else 0.0
    return float(x.mean() / (sd / np.sqrt(len(x)))) if sd > 0 else np.nan


def mean_se(x):
    """(mean, standard error) ignoring NaN."""
    x = pd.Series(x, dtype=float).dropna()
    return (float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 1 else (np.nan, np.nan)


def welch(a, b, alternative="greater"):
    """Welch t-test (unequal variances). Returns (t, p)."""
    t, p = stats.ttest_ind(np.asarray(a, float), np.asarray(b, float), equal_var=False, alternative=alternative)
    return float(t), float(p)


def profit_factor(x) -> float:
    x = pd.Series(x, dtype=float).dropna()
    gl = -x[x < 0].sum()
    return float(x[x > 0].sum() / gl) if gl > 0 else np.inf


def drawdown(returns) -> pd.Series:
    """Drawdown of the equity curve (starting at 1.0) as a fraction (<= 0)."""
    eq = (1.0 + pd.Series(returns, dtype=float).fillna(0.0)).cumprod()
    return eq / np.maximum(eq.cummax(), 1.0) - 1.0


def interp_zero(x, y) -> float:
    """First x where y crosses zero (linear interpolation). NaN if it never does."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    for k in range(len(x) - 1):
        if np.isfinite(y[k]) and np.isfinite(y[k + 1]) and y[k] != y[k + 1] and y[k] * y[k + 1] <= 0:
            return float(x[k] - y[k] * (x[k + 1] - x[k]) / (y[k + 1] - y[k]))
    return np.nan


# ------------------------------------------------------------------ engine helpers
@contextlib.contextmanager
def engine_overrides(eng, **kw):
    """Temporarily change ENGINE_DEFAULTS (e.g. flat_spread_pips) and restore them on exit."""
    old = {k: eng.ENGINE_DEFAULTS[k] for k in kw}
    eng.set_engine_defaults(**kw)
    try:
        yield
    finally:
        eng.set_engine_defaults(**old)


def independent_gotobi_dates(start, end, days=(5, 10, 15, 20, 25), month_end=True, shift_rule="previous"):
    """Gotobi calendar re-implemented with plain `datetime` and the `holidays` package (no numpy busday).
    Used as an independent cross-check of gotobi_engine.gotobi_calendar. Returns a set of datetime.date."""
    import holidays

    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    hol = holidays.Japan(years=range(start.year - 1, end.year + 2))

    def bank_day(d):
        return d.weekday() < 5 and d not in hol and not (d.month == 12 and d.day == 31) and not (d.month == 1 and d.day <= 3)

    step = {"previous": -1, "next": 1}.get(shift_rule, 0)
    out = set()
    for y in range(start.year - 1, end.year + 2):
        for m in range(1, 13):
            last = calendar.monthrange(y, m)[1]
            for d in [dt.date(y, m, min(int(k), last)) for k in days] + ([dt.date(y, m, last)] if month_end else []):
                while not bank_day(d):
                    if step == 0:
                        d = None
                        break
                    d += dt.timedelta(days=step)
                if d is not None:
                    out.add(d)
    return {d for d in out if start <= d <= end}