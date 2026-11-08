"""
patch_notebook_long_only.py  (v2, corrected)

Makes notebook 01 (Weekly Momentum hypothesis) direction-aware, so a long_only / short_only variant is judged by
checks that mean something. With direction="both" every number stays EXACTLY as before.

SWITCHING VARIANTS: after patching, the notebook works with either YAML. Change one line in the parameters cell:
    VARIANT = "v1_ethusd"          # both legs (research rules; the research-reference checks run)
    VARIANT = "v2_ethusd_long"     # long only (single-leg checks; reference checks are skipped)
No other edit is needed, and the patch is applied only once.

What changes (6 code cells, nothing else; every edit is an exact-text replacement and the script aborts if a
piece of text is not found exactly once; every patched cell is also compiled before anything is written):

  section 3  gaps check      counts weeks lost against EVERY week with a signal (both signs), not against the
                             traded weeks (before: the 153 down-momentum weeks showed up as "lost to gaps").
                             v2 fix: the first / last week used for the expected count now come from the signal
                             weeks too. In v1 of this patch they came from the traded weeks, so a long-only run
                             compared a signal-week count against a traded-week range and the "lost" number was
                             wrong. The long/short mix print also uses the signal weeks.
  4.1        predictive      uses every signal week (UP and DOWN), because it tests the signal, not the legs traded.
  4.2        excess/perm.    statistic = mean gross move of the TRADED weeks; naked reference = every signal week
                             always long (short_only: always short); the permutation shifts the exposure over all
                             signal weeks. With one leg this is "does momentum pick better weeks than a naked
                             position", which is the question that matters. With both legs the numbers are
                             identical to the original (same rng sequence).
  4.3        costs           only the legs that were traded; the other leg is SKIP, not FAIL.
  6 sanity   trades/year     threshold x 0.5 for a single leg (it is expected to trade about half of the weeks).
                             Fixed a priori, not tuned: a year with few UP weeks can still FAIL it.
  7 variants "v1 both legs"  always the both-legs rule; the four "both legs beat long only" checks become
                             informational (SKIP) when the traded rule is a single leg: that decision is already
                             taken by choosing the variant.

Usage:   python patch_notebook_long_only.py  01_Weekly_Momentum_Hypothesis_Definition.ipynb  [out.ipynb]
Default output: <name>_patched.ipynb (the original is not touched). Code-cell outputs are cleared: re-run all.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def replace_once(src: str, old: str, new: str, what: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"[{what}] expected the text exactly once, found {n} times. Notebook differs from the "
                         f"version this patch was written for; nothing was written.")
    return src.replace(old, new)


# ---------------------------------------------------------------- section 3: data cell
def patch_data(src):
    src = replace_once(src,
        r'''trades_all = eng.run_weekly_backtest(df, **RULES)
trades_is, trades_oos = eng.split_trades(trades_all, oos_start)
''',
        r'''trades_all = eng.run_weekly_backtest(df, **RULES)
trades_is, trades_oos = eng.split_trades(trades_all, oos_start)
# Signal diagnostics (gaps, 4.1, 4.2) always see BOTH signs of the momentum, even if only one leg is traded
trades_sig = trades_all if DIRECTION == "both" else eng.run_weekly_backtest(df, **{**RULES, "direction": "both"})
''', "3 data / trades_sig")
    src = replace_once(src,
        r'''print(f"Long weeks: {(trades_all['side'] > 0).mean():.0%} | short weeks: {(trades_all['side'] < 0).mean():.0%}")''',
        r'''print(f"Signal weeks (both signs): long {(trades_sig['side'] > 0).mean():.0%} | short {(trades_sig['side'] < 0).mean():.0%} | traded: {len(trades_all)} ({DIRECTION})")''',
        "3 data / long-short mix")
    return replace_once(src,
        r'''srv_first = pd.Timestamp(df.loc[df.index[int(trades_all['i_ent'].iloc[0])], "srv_time"]).normalize()
srv_last = pd.Timestamp(df.loc[df.index[int(trades_all['i_ent'].iloc[-1])], "srv_time"]).normalize()
exp_weeks = len(pd.date_range(srv_first, srv_last, freq="W-MON"))
lost = exp_weeks - len(trades_all)''',
        r'''srv_first = pd.Timestamp(df.loc[df.index[int(trades_sig['i_ent'].iloc[0])], "srv_time"]).normalize()
srv_last = pd.Timestamp(df.loc[df.index[int(trades_sig['i_ent'].iloc[-1])], "srv_time"]).normalize()
exp_weeks = len(pd.date_range(srv_first, srv_last, freq="W-MON"))
lost = exp_weeks - len(trades_sig)''', "3 data / gaps")


# ---------------------------------------------------------------- 4.1
HEAD_41_OLD = r'''wk = trades_all.copy()
wk["entry_time"] = pd.to_datetime(wk["entry_time"])
wk["year"] = wk["entry_time"].dt.year
wk["raw"] = wk["side"] * wk["gross_pct"]            # price move of the week (%), before cost and swap
wk["after"] = np.where(wk["side"] > 0, "After UP momentum", "After DOWN momentum")
wk["period"] = np.where(wk["entry_time"] < oos_start, "IS", "OOS")
'''
HEAD_41_NEW = r'''def _week_table(t):
    w = t.copy()
    w["entry_time"] = pd.to_datetime(w["entry_time"])
    w["year"] = w["entry_time"].dt.year
    w["raw"] = w["side"] * w["gross_pct"]            # price move of the week (%), before cost and swap
    w["after"] = np.where(w["side"] > 0, "After UP momentum", "After DOWN momentum")
    w["period"] = np.where(w["entry_time"] < oos_start, "IS", "OOS")
    return w

wk = _week_table(trades_all)        # the weeks that are TRADED (costs and concentration: 4.3 / 4.4)
wk_sig = _week_table(trades_sig)    # every week with a signal, both signs (signal tests: 4.1 / 4.2)
'''


def patch_41(src):
    if not src.startswith(HEAD_41_OLD):
        raise SystemExit("[4.1] the cell does not start with the expected header; nothing was written.")
    rest = re.sub(r"\bwk\b", "wk_sig", src[len(HEAD_41_OLD):])
    return HEAD_41_NEW + rest


# ---------------------------------------------------------------- 4.2 (whole cell)
CELL_42_NEW = r'''rng = np.random.default_rng(42)

# Exposure per signal week: +1 long, -1 short, 0 not traded. With both legs it is just `side` (original behaviour).
def exposure(side):
    side = np.asarray(side, float)
    if DIRECTION == "long_only":
        return (side > 0).astype(float)
    if DIRECTION == "short_only":
        return -(side < 0).astype(float)
    return side

NAKED_SIGN = -1.0 if DIRECTION == "short_only" else 1.0      # passive alternative over the SAME weeks (always long / always short)

def perm_pvalue(expo, raw, n_iter=N_PERM):
    # Circular shift of the exposure vector against the weekly moves: keeps the number of traded weeks, the
    # long/short mix and the drift. Statistic: mean gross move per traded week.
    expo, raw = np.asarray(expo, float), np.asarray(raw, float)
    n_tr = np.abs(expo).sum()
    obs = float((expo * raw).sum() / n_tr)
    shifts = rng.integers(1, len(expo), n_iter)
    null = np.array([(np.roll(expo, k) * raw).sum() / n_tr for k in shifts])
    return obs, float((null >= obs).mean()), float(null.mean())

def drift_row(label, sub):
    expo, raw = exposure(sub["side"]), sub["raw"].to_numpy(float)
    g = (expo * raw)[expo != 0]                            # gross move of the traded weeks only
    obs, p, null_mean = perm_pvalue(expo, raw)
    return {"Sample": label, "n": len(sub), "Traded n": len(g), "Naked long gross %": NAKED_SIGN * raw.mean(), "Momentum gross %": g.mean(),
            "Excess over drift %": g.mean() - NAKED_SIGN * raw.mean(), "Gross t": tstat(g), "Perm null mean %": null_mean, "Perm p (1-sided)": p}

drift = pd.DataFrame([drift_row("IS", wk_sig[wk_sig["period"] == "IS"]), drift_row("OOS", wk_sig[wk_sig["period"] == "OOS"]), drift_row("All", wk_sig)]).set_index("Sample")
print("=" * 70)
print(f"MOMENTUM VS NAKED {'SHORT' if DIRECTION == 'short_only' else 'LONG'} (SAME WEEKS) AND PERMUTATION TEST (gross, per traded week, %)")
print("=" * 70)
display(drift.round(3))

# ---- PASS / FAIL ----
print("\nCHECKS (4.2):")
check("4.2 Excess", f"Gross mean is positive and significant (t >= {T_MIN:g}), all weeks", drift.loc["All", "Momentum gross %"] > 0 and drift.loc["All", "Gross t"] >= T_MIN,
      f"gross {drift.loc['All', 'Momentum gross %']:+.2f}% | t = {drift.loc['All', 'Gross t']:.2f}")
check("4.2 Excess", "Momentum beats naked long on gross mean (all weeks)", drift.loc["All", "Excess over drift %"] > 0,
      f"excess {drift.loc['All', 'Excess over drift %']:+.2f}% per week")
check("4.2 Excess", f"Permutation p < {ALPHA:g} (IS)", drift.loc["IS", "Perm p (1-sided)"] < ALPHA, f"p = {drift.loc['IS', 'Perm p (1-sided)']:.3f}")
check("4.2 Excess", f"Permutation p < {ALPHA:g} (OOS)", drift.loc["OOS", "Perm p (1-sided)"] < ALPHA, f"p = {drift.loc['OOS', 'Perm p (1-sided)']:.3f}")
check("4.2 Excess", f"Permutation p < {ALPHA:g} (all weeks)", drift.loc["All", "Perm p (1-sided)"] < ALPHA, f"p = {drift.loc['All', 'Perm p (1-sided)']:.3f}")
'''


# ---------------------------------------------------------------- 4.3 (whole cell)
CELL_43_NEW = r'''def leg_row(label, sub):
    gross, cost, swap, net = sub["gross_pct"].mean(), sub["cost_pct"].mean(), sub["swap_pct"].mean(), sub["pnl"].mean()
    return {"Leg": label, "n": len(sub), "Gross %": gross, "Spread %": -cost, "Swap %": swap, "Net %": net,
            "Net t": tstat(sub["pnl"]), "Win %": (sub["pnl"] > 0).mean() * 100,
            "Cost+swap / gross": (cost - swap) / gross if gross > 0 else np.nan}

ALL_LEG = "Both" if DIRECTION == "both" else "All traded"
rows43 = [leg_row(name, wk[wk["side"] == s]) for name, s in (("Long", 1), ("Short", -1)) if (wk["side"] == s).any()]
legs = pd.DataFrame(rows43 + [leg_row(ALL_LEG, wk)]).set_index("Leg")
print("=" * 70)
print("MEAN PER TRADE BY LEG (%, per week): gross -> spread -> swap -> net")
print("=" * 70)
display(legs.round(3))
print(f"Spread candles filled with the annual median (SPREAD=0): {wk['spread_filled'].mean():.1%} of the trades")

# ---- PASS / FAIL ----
print("\nCHECKS (4.3):")
for leg in ("Long", "Short"):
    if leg in legs.index:
        check("4.3 Costs", f"{leg} leg is positive net of spread and swap", legs.loc[leg, "Net %"] > 0, f"net {legs.loc[leg, 'Net %']:+.2f}% (t = {legs.loc[leg, 'Net t']:.2f})")
    else:
        check("4.3 Costs", f"{leg} leg is positive net of spread and swap", None, f"not traded (direction = {DIRECTION})")
check("4.3 Costs", f"Spread + swap take less than 50% of the gross mean ({'both legs' if DIRECTION == 'both' else DIRECTION})", legs.loc[ALL_LEG, "Cost+swap / gross"] < 0.5,
      f"{legs.loc[ALL_LEG, 'Cost+swap / gross']:.0%} of the gross mean")
'''


# ---------------------------------------------------------------- section 6 sanity
def patch_sanity(src):
    return replace_once(src,
        r'''check("6. Sanity", f"Every full calendar year has >= {MIN_TRADES_PER_YEAR} trades", (tpy_full >= MIN_TRADES_PER_YEAR).all(),''',
        r'''MIN_TPY = MIN_TRADES_PER_YEAR * (1.0 if DIRECTION == "both" else 0.5)     # one leg trades about half of the weeks (fixed a priori)
check("6. Sanity", f"Every full calendar year has >= {MIN_TPY:g} trades", (tpy_full >= MIN_TPY).all(),''', "6 sanity / trades per year")


# ---------------------------------------------------------------- section 7 variants
CHECKS_7_OLD = r'''v1, lo = var_table.loc["v1: both legs (frozen rules)"], var_table.loc["Long only"]
check("7. Variants", "Both legs beat long only on Profit Factor", v1["PF"] > lo["PF"], f"{v1['PF']:.3f} vs {lo['PF']:.3f}")
check("7. Variants", "Both legs beat long only on Sharpe", v1["Sharpe"] > lo["Sharpe"], f"{v1['Sharpe']:.2f} vs {lo['Sharpe']:.2f}")
check("7. Variants", "Both legs beat long only on expectancy per trade", v1["Expectancy %"] > lo["Expectancy %"], f"{v1['Expectancy %']:+.3f}% vs {lo['Expectancy %']:+.3f}%")
check("7. Variants", "Both legs: max drawdown is not deeper than long only", v1["Max DD %"] >= lo["Max DD %"], f"{v1['Max DD %']:.1f}% vs {lo['Max DD %']:.1f}%")'''
CHECKS_7_NEW = r'''v1, lo = var_table.loc["v1: both legs (frozen rules)"], var_table.loc["Long only"]
_both = DIRECTION == "both"
_note = "" if _both else f"reference only, the traded rule is {DIRECTION}: "
def _cmp(name, ok, detail):
    check("7. Variants", name, ok if _both else None, _note + detail)
_cmp("Both legs beat long only on Profit Factor", v1["PF"] > lo["PF"], f"{v1['PF']:.3f} vs {lo['PF']:.3f}")
_cmp("Both legs beat long only on Sharpe", v1["Sharpe"] > lo["Sharpe"], f"{v1['Sharpe']:.2f} vs {lo['Sharpe']:.2f}")
_cmp("Both legs beat long only on expectancy per trade", v1["Expectancy %"] > lo["Expectancy %"], f"{v1['Expectancy %']:+.3f}% vs {lo['Expectancy %']:+.3f}%")
_cmp("Both legs: max drawdown is not deeper than long only", v1["Max DD %"] >= lo["Max DD %"], f"{v1['Max DD %']:.1f}% vs {lo['Max DD %']:.1f}%")'''


def patch_variants(src):
    src = replace_once(src, r'''variants = [("v1: both legs (frozen rules)", trades_all),''',
                       r'''variants = [("v1: both legs (frozen rules)", trades_sig),''', "7 variants / both-legs row")
    src = replace_once(src, "    t_noswap = eng.run_weekly_backtest(df, **RULES)",
                       '    t_noswap = eng.run_weekly_backtest(df, **{**RULES, "direction": "both"})', "7 variants / no-swap row")
    return replace_once(src, CHECKS_7_OLD, CHECKS_7_NEW, "7 variants / checks")


# ---------------------------------------------------------------- driver
PATCHES = [
    ("section 3 (data)", "df_raw = eng.load_data(TICKER, start=DATA_START)", patch_data),
    ("4.1", "wk = trades_all.copy()", patch_41),
    ("4.2", "def perm_pvalue(side, raw, n_iter=N_PERM):", lambda s: CELL_42_NEW),
    ("4.3", "def leg_row(label, sub):", lambda s: CELL_43_NEW),
    ("6 sanity", "SANITY CHECKS & REPRODUCIBILITY", patch_sanity),
    ("7 variants", "def variant_row(label, t, price_df):", patch_variants),
]


def src_of(cell) -> str:
    s = cell["source"]
    return "".join(s) if isinstance(s, list) else s


def apply(nb: dict) -> dict:
    cells = nb["cells"]
    if any("trades_sig" in src_of(c) for c in cells if c["cell_type"] == "code"):
        raise SystemExit("This notebook already looks patched (it contains 'trades_sig'); nothing was written. "
                         "Patch the original notebook, not a patched copy.")
    staged = []                           # (cell index, new source): nothing is written unless every patch works
    for name, locator, fn in PATCHES:
        hits = [i for i, c in enumerate(cells) if c["cell_type"] == "code" and locator in src_of(c)]
        if len(hits) != 1:
            raise SystemExit(f"[{name}] expected exactly one code cell containing {locator!r}, found {len(hits)}. "
                             f"Nothing was written.")
        old = src_of(cells[hits[0]])
        new = fn(old)
        if new == old:
            raise SystemExit(f"[{name}] the patch did not change the cell; nothing was written.")
        try:
            compile(new, f"<patched {name}>", "exec")
        except SyntaxError as e:
            raise SystemExit(f"[{name}] the patched cell does not compile ({e}); nothing was written.")
        staged.append((name, hits[0], new))
    for name, i, new in staged:
        cells[i]["source"] = new.splitlines(keepends=True)
        print(f"patched: {name} (cell #{i})")
    for c in cells:                       # outputs belong to the old code: force a clean re-run
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    return nb


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else path.with_name(path.stem + "_patched.ipynb")
    nb = json.loads(path.read_text(encoding="utf-8"))
    nb = apply(nb)
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written: {out}\nNow: restart the kernel and run all.")
