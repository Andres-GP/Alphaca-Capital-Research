"""
validation_gate.py  ·  research_development/utils/validation_gate.py
Runs the robustness phases and returns a pass/fail report.

Verdict (out['status']):
  FAILED     -> at least one gating phase failed.
  INCOMPLETE -> no phase failed, but at least one phase was skipped for lack of inputs.
                A skipped phase is NOT a pass: out['passed'] is False.
  PASSED     -> every gating phase ran and passed.
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
                   chosen=None, oos_start=None, mode="additive", criteria=None, verbose=True,
                   mtm_paths=None, monkey_entry_col="open", monkey_exit_col="open",
                   monkey_cost_pct_per_side=0.05):
    """
    mtm_paths: optional list of 1-D arrays (one per row of trades_df, same order) with the
               daily mark-to-market returns of each trade (rsi2_engine.trade_mtm_paths with
               the same sizing as trades_df['pnl']). When given, drawdowns of phase 1 and
               phase 2 are measured on daily MTM; otherwise they are measured trade by trade
               (reported as dd_basis='trade').
    monkey_entry_col / monkey_exit_col / monkey_cost_pct_per_side: execution model of the
               monkey test; it must match the strategy ('open'/'open' + cost per side in
               percent for next-open systems, 'close'/'close' for signal-bar-close systems).
    """
    c = {**DEFAULTS, **(criteria or {})}
    phases = {}

    # Phase 1 · OOS trades (filtered by ENTRY time: a trade belongs to the OOS if it was opened in it)
    if oos_start is None:
        mask = np.ones(len(trades_df), dtype=bool)
    else:
        mask = (pd.to_datetime(trades_df["entry_time"]) >= pd.Timestamp(oos_start)).to_numpy()
    oos = trades_df[mask]
    pnl = oos["pnl"].to_numpy(float)
    if len(pnl) > 1:
        pf, pf_nb = profit_factor(pnl), profit_factor(np.delete(pnl, pnl.argmax()))
        if mtm_paths is not None:
            # Concatenating the daily paths of the OOS trades gives the same peaks and troughs
            # as the daily MTM equity of those trades (idle days have 0 return).
            oos_r = np.concatenate([mtm_paths[i] for i in np.flatnonzero(mask)])[None, :]
            dd_basis = "mtm"
        else:
            oos_r = pnl[None, :] / 100
            dd_basis = "trade"
        mdd = float(max_dd_paths(equity_paths(oos_r, mode))[0])
        ok = len(pnl) >= c["n_min"] and pf >= c["pf_min"] and pf_nb > 1 and mdd > c["mdd_min"]
    else:
        pf = pf_nb = mdd = np.nan; ok = False
        dd_basis = "mtm" if mtm_paths is not None else "trade"
    phases["1_oos"] = dict(n=len(pnl), pf=pf, pf_without_best_trade=pf_nb, max_dd=mdd,
                           dd_basis=dd_basis, passed=bool(ok))

    # Phase 2 · block Monte Carlo (all trades)
    mc = monte_carlo_block(trades_df, block=c["block"], mode=mode, mtm_paths=mtm_paths)
    ok = mc["ret_p5"] > c["mc_ret_p5_min"] and mc["mdd_p5"] > c["mc_mdd_p5_min"] and mc["prob_ruin"] < c["mc_ruin_max"]
    phases["2_monte_carlo"] = dict(ret_p5=mc["ret_p5"], mdd_p5=mc["mdd_p5"], prob_ruin=mc["prob_ruin"],
                                   dd_basis=mc["dd_basis"], passed=bool(ok))

    # Phase 3 · monkey test
    if df_prices is not None:
        mk = monkey_test(df_prices, trades_df, eligible=eligible,
                         entry_col=monkey_entry_col, exit_col=monkey_exit_col,
                         cost_pct_per_side=monkey_cost_pct_per_side)
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

    failed = any(not p["passed"] for p in phases.values() if "passed" in p)
    skipped = [name for name, p in phases.items() if p.get("skipped")]
    status = "FAILED" if failed else ("INCOMPLETE" if skipped else "PASSED")
    out = dict(phases=phases, passed=bool(status == "PASSED"), status=status, skipped=skipped)

    if verbose:
        print("=" * 60, "\nVALIDATION GATE\n" + "=" * 60)
        for name, p in phases.items():
            tag = "SKIP" if p.get("skipped") else ("INFO" if p.get("informational") else ("PASS" if p["passed"] else "FAIL"))
            body = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items() if k not in ("passed", "skipped", "informational")}
            print(f"[{tag}] {name}: {body}")
        print("-" * 60, f"\nOVERALL: {status}" + (f" (skipped phases: {', '.join(skipped)})" if skipped else ""))
    return out