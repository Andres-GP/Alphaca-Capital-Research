"""t20_tools.py - notebook boilerplate shared by notebooks 01-04: setup, PASS/FAIL registry, style."""
from __future__ import annotations
import sys, importlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np, pandas as pd
import matplotlib.pyplot as plt

BG, PANEL, GRIDC, TXT, SUB, GREEN, RED, ORANGE = "#15171c", "#1b1e26", "#2a2d37", "#e8e9ec", "#9aa0ab", "#34d399", "#f0555a", "#f5a524"
def dark_ax(ax):
    ax.set_facecolor(PANEL); ax.grid(True, color=GRIDC, lw=.8, alpha=.9); [s.set_visible(False) for s in ax.spines.values()]; ax.tick_params(colors=SUB, labelsize=9)
def fig(*a, **k):
    f, ax = plt.subplots(*a, **k); f.patch.set_facecolor(BG); [dark_ax(x) for x in np.atleast_1d(ax).ravel()]; return f, ax

# thresholds shared by every notebook (declared a priori)
TH = dict(PF_MIN=1.3, T_MIN=2.0, N_MIN=100, N_OOS_MIN=30, ALPHA=0.05, N_MONKEY=300, YEARS_POS_MIN=0.70, SHARPE_MIN=0.5, SHARPE_OOS_MIN=0.4,
          MAX_DD_VS_BH=1.0, PLATEAU_MIN=0.6)

class Registry:
    def __init__(self): self.items = []
    def check(self, section, name, passed, detail="", quiet=False):
        st = "SKIP" if passed is None else ("PASS" if bool(passed) else "FAIL")
        e = dict(section=section, name=name, status=st, detail=detail)
        for i, c in enumerate(self.items):
            if c["section"] == section and c["name"] == name: self.items[i] = e; break
        else: self.items.append(e)
        if not quiet: print(f"   [{st}] {name}" + (f"  ->  {detail}" if detail else ""))
        return st
    def df(self): return pd.DataFrame(self.items)
    def summary(self, essential=None):
        d = self.df(); d = d if essential is None else d[d["name"].str.startswith(tuple(essential))]
        return {s: int((d["status"] == s).sum()) for s in ("PASS", "FAIL", "SKIP")}

def setup(variant, nb_file=None, panel=True):
    """Find the edge folder, load the variant, the engine and (optionally) the data panel."""
    here = Path.cwd().resolve()
    edge = next(b for b in (here, *here.parents) if (b / "variants").is_dir())
    sys.path.insert(0, str(edge))
    import t20_engine as eng, variant_config as vc
    importlib.reload(eng); vc.EDGE_DIR = edge; eng.EDGE_DIR = edge
    cfg = vc.load_variant(variant); eng.set_engine_defaults(**cfg.get("engine_defaults", {}))
    P = cfg["params"]
    rules = dict(lookback_days=P["lookback_days"], top_n=P["top_n"], slip_bps_per_side=P["slip_bps_per_side"], exec_mode=P["exec_mode"],
                 spy_ma=P["spy_ma"], stock_ma=P["stock_ma"], fast_ma=P["fast_ma"], min_adv_shares=P["min_adv_shares"],
                 rebalance=P["rebalance"], weekly_checks=P["weekly_checks"], cash_yield=P["cash_yield_annual"])
    if panel:
        import t20_data; importlib.reload(t20_data); t20_data.ensure_data(cfg, eng._res)      # checks the data, downloads it only if missing
    pan = eng.load_panel() if panel else None
    plt.rcParams.update({"figure.facecolor": BG, "text.color": TXT, "axes.labelcolor": SUB, "axes.titlecolor": TXT, "savefig.facecolor": BG})
    print(f"Variant {cfg['id']} | Top {P['top_n']} | momentum {P['lookback_days']} d | {P['rebalance']} | {P['exec_mode']} | slip {P['slip_bps_per_side']} bps/side")
    if pan is not None: print(f"Panel: {len(pan.tickers)} tickers, {pan.dates[0]:%Y-%m-%d} -> {pan.dates[-1]:%Y-%m-%d}, OOS from {cfg['oos_start_ts']:%Y-%m-%d}")
    return SimpleNamespace(eng=eng, cfg=cfg, P=P, rules=rules, panel=pan, vc=vc, OOS=cfg["oos_start_ts"], RUN=cfg["run_dir"],
                           CAP=cfg["risk"]["capital"], LIMIT=cfg["risk"]["hard_limit"], reg=Registry(), TH=TH)

def gate(reg, essential, headline=""):
    """GO / STOP: essential = [(section, check-name prefix, action if FAIL)]. Everything else is informative."""
    d = reg.df()
    d["ess"] = [any(s == a and n.startswith(b) for a, b, _ in essential) for s, n in zip(d.section, d.name)]
    miss = [f"{a}: {b}" for a, b, _ in essential if not ((d.section == a) & d.name.str.startswith(b)).any()]
    ess = d[d.ess]; fails = ess[ess.status == "FAIL"]; go = fails.empty and not miss
    print("=" * 80)
    print(f"DECISION: {'GO' if go else 'STOP'}  ({int((ess.status == 'PASS').sum())} PASS / {len(fails)} FAIL / {int((ess.status == 'SKIP').sum())} SKIP of {len(essential)} essential)  {headline}")
    print("=" * 80)
    if miss: print("Not run (run the sections above): " + "; ".join(miss))
    for sec, g in ess.groupby("section", sort=False):
        print(f"\n{sec}")
        for _, r in g.iterrows(): print(f"   [{r['status']}] {r['name']}  ->  {r['detail']}")
    print("\nOTHER CHECKS (informative, they do not decide GO / STOP)")
    for _, r in d[~d.ess].iterrows(): print(f"   [{r['status']}] {r['section']} · {r['name']}  ->  {r['detail']}")
    print()
    for _, r in fails.iterrows(): print("ACTION:", next(c for a, b, c in essential if a == r["section"] and r["name"].startswith(b)))
    return go
