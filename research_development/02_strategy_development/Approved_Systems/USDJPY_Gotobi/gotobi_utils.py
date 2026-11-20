"""
gotobi_utils.py  ·  02_strategy_development/Gotobi/gotobi_utils.py   (v1.0)

Helpers shared by notebooks 02, 03 and 04 of the Gotobi edge (they live next to gotobi_engine.py and variant_config.py):

    Checks                      PASS / FAIL / SKIP registry (callable; .items, .frame(), .counts())
    mean_se, interp_zero, profit_factor, drawdown
    engine_overrides(eng, **kw) context manager: temporarily change ENGINE_DEFAULTS
    plot theme                  BG, PANEL, GRIDC, TXT, SUB, GREEN, RED, ORANGE, BLUE, subplots, set_title, legend
    plot_annual_returns         annual return / max-DD bars against the hard limit
    independent_gotobi_dates    Gotobi calendar rebuilt with plain `datetime` + the `holidays` package (cross-check of
                                gotobi_engine.gotobi_calendar, notebook 04)
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------------------------------------------------ theme (same palette as notebook 01)
BG, PANEL, GRIDC, TXT, SUB = "#15171c", "#1b1e26", "#2a2d37", "#e8e9ec", "#9aa0ab"
GREEN, RED, ORANGE, BLUE = "#34d399", "#f0555a", "#f5a524", "#5468ff"


def _style(ax, grid=True):
    ax.set_facecolor(PANEL)
    if grid:
        ax.grid(True, color=GRIDC, lw=0.8, alpha=0.9)
    else:
        ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=SUB, labelsize=9)
    return ax


def subplots(nrows=1, ncols=1, figsize=(10, 4), grid=True, **kw):
    """plt.subplots with the dark theme. Same return shape as plt.subplots (single Axes if 1x1)."""
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, facecolor=BG, **kw)
    for ax in np.atleast_1d(axes).ravel():
        _style(ax, grid)
    return fig, axes


def set_title(ax, title):
    ax.set_title(title, color=TXT, fontweight="bold", loc="left")


def legend(ax, loc="upper left"):
    h, l = ax.get_legend_handles_labels()
    if h:
        ax.legend(frameon=False, labelcolor=SUB, fontsize=9, loc=loc)


# ------------------------------------------------------------------ PASS / FAIL registry
class Checks:
    """Registry of checks. C(section, name, passed, detail) -> 'PASS' | 'FAIL' | 'SKIP' (passed=None).
    Re-running a cell overwrites its previous entry (same section + name) instead of duplicating it."""

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
        return pd.DataFrame(self.items, columns=["section", "name", "status", "detail"])

    def counts(self) -> dict:
        s = [c["status"] for c in self.items]
        return {k: int(s.count(k)) for k in ("PASS", "FAIL", "SKIP")}


# ------------------------------------------------------------------ small numerics
def mean_se(x):
    """(mean, standard error of the mean) ignoring NaN. (nan, nan) if fewer than 2 values."""
    x = pd.Series(x, dtype=float).dropna().to_numpy()
    if len(x) < 2:
        return (float(x.mean()) if len(x) else np.nan), np.nan
    return float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x)))


def interp_zero(x, y) -> float:
    """First zero crossing of y(x) by linear interpolation (x sorted ascending). NaN if y never changes sign."""
    xs, ys = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(xs) & np.isfinite(ys)
    xs, ys = xs[ok], ys[ok]
    for k in range(len(xs)):
        if ys[k] == 0:
            return float(xs[k])
        if k and ys[k - 1] * ys[k] < 0:
            return float(xs[k - 1] + (0 - ys[k - 1]) * (xs[k] - xs[k - 1]) / (ys[k] - ys[k - 1]))
    return float("nan")


def profit_factor(x) -> float:
    """Gross profit / gross loss of an array of trade results (inf if there are no losses, nan if empty)."""
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return float("nan")
    gl = -x[x < 0].sum()
    return float(x[x > 0].sum() / gl) if gl > 0 else float("inf")


def drawdown(r) -> pd.Series:
    """Drawdown series of a return series, equity starting at 1.0 (same convention as the engine's hard_limit_report)."""
    r = pd.Series(r, dtype=float).fillna(0.0)
    eq = (1.0 + r).cumprod()
    return eq / np.maximum(eq.cummax(), 1.0) - 1.0


@contextmanager
def engine_overrides(eng, **kw):
    """Temporarily change ENGINE_DEFAULTS (e.g. flat_spread_pips) and restore them afterwards, even on error."""
    old = {k: eng.ENGINE_DEFAULTS[k] for k in kw}
    eng.set_engine_defaults(**kw)
    try:
        yield
    finally:
        eng.set_engine_defaults(**old)


# ------------------------------------------------------------------ annual plot
def plot_annual_returns(annual, report, hard_limit):
    """Bars of annual return (top) and max drawdown inside each year (bottom, red = breach); * = partial year."""
    fig, (ax_ret, ax_dd) = subplots(2, 1, figsize=(11, 6.5), grid=False, sharex=True)
    years = annual["year"].astype(str).to_numpy()
    bars_ = ax_ret.bar(years, annual["ret"] * 100, color=[GREEN if v >= 0 else RED for v in annual["ret"]])
    ax_dd.bar(years, annual["mdd"] * 100, color=[RED if b else SUB for b in annual["breach"]])
    ax_dd.axhline(-hard_limit * 100, color=ORANGE, ls="--", lw=1.2)
    for rect, value, partial in zip(bars_, annual["ret"], annual["partial"]):
        ax_ret.annotate(f"{value:+.1%}" + ("*" if partial else ""), (rect.get_x() + rect.get_width() / 2, value * 100),
                        xytext=(0, 3 if value >= 0 else -3), textcoords="offset points", ha="center",
                        va="bottom" if value >= 0 else "top", color=TXT, fontsize=9)
    status = "PASS" if report["passed"] else "FAIL"
    set_title(ax_ret, f"Annual returns · hard limit -{hard_limit:.0%} · max DD {report['max_dd']:.1%} · {status}")
    ax_ret.set_ylabel("Return %", color=SUB)
    ax_dd.set_ylabel("Max DD in year %", color=SUB)
    plt.tight_layout()
    plt.show()
    return fig


# ------------------------------------------------------------------ independent calendar (notebook 04)
def independent_gotobi_dates(start, end, days=(5, 10, 15, 20, 25), month_end=True, shift_rule="previous") -> set:
    """Gotobi trade dates (JST) between start and end, rebuilt WITHOUT numpy busday and WITHOUT the engine:
        - nominal dates: each day in `days` (clamped to the last day of short months) + last day of the month;
        - Japanese bank business day = Mon-Fri, not a holiday (`holidays.Japan`), not 31 Dec nor 1-3 Jan;
        - not a business day -> previous (or next) business day, or skipped when shift_rule == 'none';
        - two nominal dates landing on the same day count once.
    Returns a set of datetime.date."""
    import holidays

    a, b = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    jp = holidays.Japan(years=range(a.year - 1, b.year + 2))

    def is_bday(d: dt.date) -> bool:
        if d.weekday() >= 5 or d in jp:
            return False
        return not ((d.month == 1 and d.day <= 3) or (d.month == 12 and d.day == 31))

    if shift_rule not in ("previous", "next", "none"):
        raise ValueError("shift_rule must be 'previous', 'next' or 'none'")
    out = set()
    for per in pd.period_range(pd.Period(a, "M") - 1, pd.Period(b, "M") + 1, freq="M"):
        last = per.days_in_month
        nominal = [dt.date(per.year, per.month, min(int(d), last)) for d in days]
        if month_end:
            nominal.append(dt.date(per.year, per.month, last))
        for d in nominal:
            if shift_rule == "previous":
                while not is_bday(d):
                    d -= dt.timedelta(days=1)
            elif shift_rule == "next":
                while not is_bday(d):
                    d += dt.timedelta(days=1)
            elif not is_bday(d):
                continue
            if a <= d <= b:
                out.add(d)
    return out