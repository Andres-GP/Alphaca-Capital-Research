"""
validation_gate.py  ·  research_development/utils/validation_gate.py
Runs the robustness phases and returns a pass/fail report.
Phases without inputs are skipped (not counted against the strategy).
"""
import numpy as np
import pandas as pd
from robustness import (profit_factor, equity_paths, max_dd_paths,
                        monte_carlo_block, monkey_test, plateau_check)
from edge_decay import edge_decay_summary

DEFAULTS = dict(
    n_min=30, pf_min=1.3, mdd_min=-0.20,                     # phase 1 (OOS trades)
    block=5, mc_ret_p5_min=0.0, mc_mdd_p5_min=-0.25, mc_ruin_max=0.05,   # phase 2
    monkey_pct_min=0.95,                                      # phase 3
    plateau_pf_min=1.3, plateau_n_min=30, plateau_max_drop=30,           # phase 4
)


def run_validation(trades_df, df_prices=None, eligible=None, grid_pf=None, grid_n=None,
                   chosen=None, oos_start=None, mode="additive", criteria=None, verbose=True):
    c = {**DEFAULTS, **(criteria or {})}
    phases = {}

    # Phase 1 · OOS trades
    oos = trades_df if oos_start is None else trades_df[pd.to_datetime(trades_df["exit_time"]) >= pd.Timestamp(oos_start)]
    pnl = oos["pnl"].to_numpy(float)
    if len(pnl) > 1:
        pf, pf_nb = profit_factor(pnl), profit_factor(np.delete(pnl, pnl.argmax()))
        mdd = float(max_dd_paths(equity_paths(pnl[None, :] / 100, mode))[0])
        ok = len(pnl) >= c["n_min"] and pf >= c["pf_min"] and pf_nb > 1 and mdd > c["mdd_min"]
    else:
        pf = pf_nb = mdd = np.nan; ok = False
    phases["1_oos"] = dict(n=len(pnl), pf=pf, pf_without_best_trade=pf_nb, max_dd=mdd, passed=bool(ok))

    # Phase 2 · block Monte Carlo (all trades)
    mc = monte_carlo_block(trades_df, block=c["block"], mode=mode)
    ok = mc["ret_p5"] > c["mc_ret_p5_min"] and mc["mdd_p5"] > c["mc_mdd_p5_min"] and mc["prob_ruin"] < c["mc_ruin_max"]
    phases["2_monte_carlo"] = dict(ret_p5=mc["ret_p5"], mdd_p5=mc["mdd_p5"], prob_ruin=mc["prob_ruin"], passed=bool(ok))

    # Phase 3 · monkey test
    if df_prices is not None:
        mk = monkey_test(df_prices, trades_df, eligible=eligible)
        phases["3_monkey"] = dict(pf_real=mk["pf_real"], pct_pf=mk["pct_pf"], passed=bool(mk["pct_pf"] >= c["monkey_pct_min"]))
    else:
        phases["3_monkey"] = dict(skipped=True)

    # Phase 4 · parameter plateau
    if grid_pf is not None and chosen is not None:
        pl = plateau_check(grid_pf, grid_n, chosen, c["plateau_pf_min"], c["plateau_n_min"], c["plateau_max_drop"])
        phases["4_plateau"] = dict(center_pf=pl["center_pf"], plateau=pl["plateau"],
                                   worst_drop_pct=pl["worst_neighbor_drop_pct"], passed=pl["passed"])
    else:
        phases["4_plateau"] = dict(skipped=True)

    # Phase 5 · edge decay (informational, does not gate)
    ed = edge_decay_summary(trades_df)
    phases["5_edge_decay"] = dict(recent_pf=ed["recent"]["pf"], historical_pf=ed["historical"]["pf"],
                                  warning=ed["warning"], informational=True)

    gating = [p["passed"] for p in phases.values() if "passed" in p]
    out = dict(phases=phases, passed=bool(all(gating)))

    if verbose:
        print("=" * 60, "\nVALIDATION GATE\n" + "=" * 60)
        for name, p in phases.items():
            tag = "SKIP" if p.get("skipped") else ("INFO" if p.get("informational") else ("PASS" if p["passed"] else "FAIL"))
            body = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items() if k not in ("passed", "skipped", "informational")}
            print(f"[{tag}] {name}: {body}")
        print("-" * 60, f"\nOVERALL: {'PASSED' if out['passed'] else 'FAILED'}")
    return out