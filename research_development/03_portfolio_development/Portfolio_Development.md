# PORTFOLIO CONSTRUCTION
**Alphaca Capital** · how much weight each edge gets · theory: *Strategy Decorrelation Guide* (TIS · Markowitz 1952), *Workshop 3 · AI without overfitting*, *Walk-Forward Analysis*.

**Reusable workflow:** edit only the `EXPERIMENT` block (section 1), then *Run All*. Each edge is a variant (`<Edge>/variants/<variant>.yaml`) found in `02_strategy_development` or `04_deployment/Approved_Systems`. **No synthetic data**: if an edge cannot be found or run, the notebook stops with an error.

It answers two separate questions:
1. **How is risk split across edges?** → weights `w` (sum to 1).
2. **How much total risk do we run?** → portfolio leverage `L`, capped by the account hard limit.

Output: the final `size_fraction` of each edge + `portfolio.json`, to paste into each variant's YAML (then re-run that edge's notebook 04 for lots).

| § | Step | Guide |
|---|---|---|
| 2 | Find edges, load real daily returns, common window | §3.1 common frequency |
| 3 | Standalone stats | — |
| 4 | Correlation, co-activity, bad days, rolling, JPY factor | §2, §3, §5, §6.2 |
| 5 | 1/√N | §7 |
| 6-7 | Weight schemes and stability (bootstrap) | Markowitz |
| 8 | Risk budget: weights → `size_fraction` | hard limit |
| 9 | Compounding effect | §8 |
| 10 | Stress: correlation → 1 | §2.3 |
| 11 | Walk-forward of the weights | Walk-Forward |
| 12 | PASS / FAIL verdict and save | — |

## DECISION RULE (declared BEFORE looking at results)
With few trades per edge, **expected returns are not identified**. So:
- **Base** = risk-based weights (ERC on a covariance with correlation shrunk to a structural prior).
- A **return tilt** (max-Sharpe on shrunk means) only enters if the bootstrap identifies it (narrow 5-95 interval). Otherwise weights = base.
- Never pick weights at the Sharpe peak: read the **shape** (plateau, not peak).
- `L` comes from the account limit (intrabar Monte Carlo), not from the return you want.
- With N = 2 equal-vol sleeves every risk-based scheme collapses to 50/50; they only diverge for N ≥ 3.

## 1. EXPERIMENT — what is being tested


```
# AXI PORTFOLIO V1 ANDRES
# # ======================= EXPERIMENT (the only block you edit) =======================
PORTFOLIO_ID = "portfolio_Axi_v1_Andres"
EDGES        = ["v1_axi_usdjpy", "v1_btcjpy"]   # variant file names (variants/<name>.yaml) or YAML ids
CAPITAL      = 10_000.0
HARD_LIMIT   = 0.08                             # max drawdown the account tolerates
MAX_SIZE     = {"v1_axi_usdjpy": 4.37, "v1_btcjpy": 0.30}   # optional: largest size_fraction each edge was validated at
WHY_UNCORRELATED = ("Different asset (USDJPY vs BTCJPY), logic (bank calendar vs Monday+ATR), horizon (2.5 h vs 24 h). "
                    "SHARED RISK: both long vs JPY; a sharp yen rally hits both.")
# # =====================================================================================

# DARWINEX PORTFOLIO
# # ======================= EXPERIMENT (the only block you edit) =======================
# PORTFOLIO_ID = "portfolio_darwinex"
# EDGES        = ["v1_axi_usdjpy", "v1_qqq"]   # variant file names (variants/<name>.yaml) or YAML ids
# CAPITAL      = 10_000.0
# HARD_LIMIT   = 0.08                          # max drawdown the account tolerates
# MAX_SIZE     = {"v1_axi_usdjpy": 4.37}       # optional: largest size_fraction each edge was validated at (QQQ: no cap declared)
# WHY_UNCORRELATED = ("Different asset class (USDJPY FX vs QQQ equity ETF), logic (Japanese payment-day calendar vs RSI(2) pullback "
#                     "in an uptrend), horizon (2.5 h intraday vs multi-day holds). "
#                     "SHARED RISK: both are long; a risk-off shock hits both (USDJPY falls as the yen rallies while QQQ sells off), "
#                     "and RSI(2) tends to buy into it.")
# # =====================================================================================

```


```
import json, re, hashlib, warnings, subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy import optimize
warnings.filterwarnings("ignore", category=FutureWarning)

# ---- Method (leave as is; every knob is a degree of freedom: change it -> note it) ----
SEARCH_ROOTS    = {"development": "02_strategy_development", "approved": "04_deployment/Approved_Systems"}
SOURCE_PRIORITY = ["approved", "development"]   # same variant in both roots -> first one wins
FORCE_REFRESH   = False                         # True = regenerate every daily_returns.csv from the engines
PPY             = 365                           # calendar days (BTC trades every day)
JPY_PROXY_CSV   = None                          # optional daily USDJPY CSV (date, close) for the shared JPY factor (4.3)
INTRABAR_FACTOR = 1.25                          # intrabar DD ~ 1.25 x close DD
TARGET_VOL      = 0.10                          # edges scaled to this annual vol before splitting (scale only)
PRIOR_RHO, SHRINK_RHO = 0.20, 0.50              # structural prior for correlation and its weight
MEAN_SHRINK     = 0.50                          # shrink edge means toward the cross-sectional mean (max-Sharpe)
SEED, N_BOOT, N_MC, BLOCK_DAYS, MC_YEARS = 42, 300, 2000, 21, 3
MC_BREACH_MAX   = 0.05                          # max P(touching the hard limit)
CORR_ALERT, CORR_OK, N_MIN_COACTIVE, MIN_OVERLAP_YEARS = 0.50, 0.20, 30, 2.0
W_IDENT_WIDTH, BLEND_IF_IDENT, PLATEAU_TOL, MIN_TRAIN_YEARS = 0.40, 0.50, 0.10, 1.0
HYPOTHESIS = f"Risk-parity base across {', '.join(EDGES)} keeps the account inside -{HARD_LIMIT:.0%}."

# ---- Dark style shared with the Monday Effect notebooks ----
BG, PANEL, GRIDC, TXT, SUB, GREEN, RED, ORANGE, BLUE = "#15171c", "#1b1e26", "#2a2d37", "#e8e9ec", "#9aa0ab", "#34d399", "#f0555a", "#f5a524", "#5468ff"
PAL = [BLUE, GREEN, ORANGE, RED, "#a78bfa", "#22d3ee", "#f472b6"]
def dark_ax(ax):
    ax.set_facecolor(PANEL); ax.grid(color=GRIDC, alpha=0.8); ax.tick_params(colors=SUB)
    for s in ax.spines.values(): s.set_visible(False)
def figs(nr=1, nc=1, size=(14, 4.5)):
    fig, ax = plt.subplots(nr, nc, figsize=size, facecolor=BG)
    for a in np.atleast_1d(ax).ravel(): dark_ax(a)
    return fig, ax
def ttl(ax, s): ax.set_title(s, color=TXT, fontweight="bold", loc="left")
def leg(ax, loc="best"): ax.legend(frameon=False, labelcolor=SUB, fontsize=9, loc=loc)
def lab(ax, x=None, y=None):
    if x: ax.set_xlabel(x, color=SUB)
    if y: ax.set_ylabel(y, color=SUB)

CHECKS = []
def check(section, name, passed, detail=""):
    st = "SKIP" if passed is None else ("PASS" if bool(passed) else "FAIL")
    e = dict(section=section, name=name, status=st, detail=detail)
    for i, c in enumerate(CHECKS):
        if c["section"] == section and c["name"] == name: CHECKS[i] = e; break
    else: CHECKS.append(e)
    print(f"   [{st}] {name}" + (f"  ->  {detail}" if detail else "")); return st
keys = list(EDGES); N = len(keys)
print(f"{PORTFOLIO_ID} | {N} edges: {keys}")
```

    portfolio_Axi_v1_Andres | 2 edges: ['v1_axi_usdjpy', 'v1_btcjpy']


## 2. FIND EDGES AND LOAD DAILY RETURNS
For each edge the notebook reads `runs/<variant>/daily_returns.csv` (daily mark-to-market return at the variant's `size_fraction`). If the file is missing or the YAML changed, it **runs the edge's real engine once** (same data and rules as its notebooks 03/04) in a separate process and caches the CSV + `size_fraction` next to the run. Validation status is read from `03_validation.json`. Supported engines: Gotobi, Monday Effect; a new engine = one entry in `RECIPES`.


```
# ---- 1) Find the edges: <root>/<Edge>/variants/<variant>.yaml  +  <Edge>/runs/<variant>/ ----
def find_dir(rel):
    here = Path.cwd().resolve()
    for base in (here, *here.parents):
        for r in (rel, rel.replace("Systems", "Sustems")):      # tolerates the 'Sustems' typo folder
            if (base / r).is_dir(): return base / r
    return None
ROOTS = {k: find_dir(v) for k, v in SEARCH_ROOTS.items()}

def read_yaml(p):
    import yaml; return yaml.safe_load(p.read_text()) or {}

rows = []
for src, base in ROOTS.items():
    for y in sorted(base.glob("*/variants/*.yaml")) if base else []:
        edge = y.parent.parent; cfg = read_yaml(y)
        rows.append(dict(source=src, id=str(cfg.get("id", y.stem)), variant=y.stem, edge=edge.name, edge_dir=edge, run_dir=edge / "runs" / y.stem, yaml=y))
CAT = pd.DataFrame(rows, columns=["source", "id", "variant", "edge", "edge_dir", "run_dir", "yaml"])
print("Roots:", {k: (str(v) if v else "NOT FOUND") for k, v in ROOTS.items()})
if CAT.empty: raise FileNotFoundError("No variants/*.yaml found under SEARCH_ROOTS. Run this notebook from inside research_development.")

def resolve(name):
    low = name.lower()
    for m in (CAT[CAT.variant.str.lower() == low], CAT[CAT.id.str.lower() == low], CAT[(CAT.edge + "/" + CAT.variant).str.lower() == low]):
        for s in SOURCE_PRIORITY:
            mm = m[m.source == s]
            if len(mm): return mm.iloc[0]
    raise KeyError(f"'{name}' is not a variant or YAML id. Available: {sorted(CAT.variant.unique())}")

# ---- 2) Daily returns: read runs/<variant>/daily_returns.csv, or build it ONCE from the real engine ----
# The engines are run in a fresh Python process (both ship a variant_config.py with the same name; they would clash in one kernel).
RECIPES = {
"gotobi_engine.py": """
import gotobi_engine as eng, variant_config as vc
vc.EDGE_DIR = Path(EDGE); cfg = vc.load_variant(VARIANT)
eng.set_engine_defaults(**cfg["engine_defaults"]); eng.apply_cfd_preset(cfg["account"]["cfd_preset"]); eng.set_engine_defaults(account_ccy=cfg["account"]["ccy"])
INS = cfg["instrument"]; FRAC = float(cfg["risk"]["size_fraction"])
df = eng.load_data(start=INS["start"], end=INS.get("end")); trades = eng.run_gotobi_backtest(df)
ret = eng.daily_returns(df, trades, FRAC)
""",
"monday_effect_engine.py": """
import monday_effect_engine as eng, variant_config as vc
vc.EDGE_DIR = Path(EDGE); cfg = vc.load_variant(VARIANT)
eng.set_engine_defaults(**cfg.get("engine_defaults", {})); P = cfg["params"]
_p = Path(eng.ENGINE_DEFAULTS["csv_path"])
if not _p.is_absolute() and not _p.exists():          # configured path does not resolve: find (or build) the UTC file by symbol + timeframe
    _pre = "_".join(_p.stem.lower().split("_")[:2])   # e.g. "btcjpy_h1"
    _hit = _raw = None
    for b in Path(EDGE).resolve().parents:
        d = b / "data" / _p.parent.name               # same source folder as configured (axi / darwinex / ...)
        if not d.is_dir(): continue
        utc = sorted(x for x in d.rglob("*.csv") if x.name.lower().startswith(_pre) and "utc" in x.name.lower())
        if utc: _hit = utc[-1]; break
        rawc = sorted(x for x in d.glob("*.csv") if x.name.lower().startswith(_pre))
        if rawc: _raw, _hit = rawc[-1], d / _p.name; break
    if _hit is None: raise FileNotFoundError("no '" + _pre + "*.csv' in any <ancestor>/data/" + _p.parent.name + " folder")
    if not _hit.exists():                             # one-time conversion of the raw MetaTrader export to UTC (replaces convert_axi_h1.py)
        r = pd.read_csv(_raw, sep=None, engine="python"); r.columns = [c.strip("<>").lower() for c in r.columns]
        t = pd.to_datetime(r["date"].astype(str) + " " + r["time"].astype(str), format="%Y.%m.%d %H:%M:%S")
        # MT5 server time = New York time + 7 h (GMT+2 winter / GMT+3 summer, US DST) -> UTC
        utc_t = (t - pd.Timedelta(hours=7)).dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC").dt.tz_localize(None)
        o = pd.DataFrame({"time": utc_t, "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"], "volume": r["tickvol"] if "tickvol" in r else r["vol"]})
        o = o.dropna(subset=["time"]).sort_values("time").drop_duplicates("time"); o.to_csv(_hit, index=False)
        print("converted", _raw.name, "->", _hit, "|", len(o), "rows |", o.time.iloc[0], "->", o.time.iloc[-1])
    eng.ENGINE_DEFAULTS["csv_path"] = str(_hit); print("data file:", _hit)
RULES = dict(vol_mode=P["vol_mode"], atr_pctl=float(P["atr_pctl"]), atr_len=int(P["atr_len"]), skip_first_monday=P["skip_first_monday"],
             entry_hour=P["entry_hour"], hold_bars=P["hold_bars"], cost_bps_per_side=P["cost_bps_per_side"])
raw = eng.load_data(cfg["instrument"]["ticker"], start=cfg["instrument"]["start"])
df = eng.prepare(raw, atr_len=RULES["atr_len"], entry_hour=RULES["entry_hour"]); trades = eng.run_monday_backtest(df, **RULES)
FRAC = float(eng.ENGINE_DEFAULTS["size_fraction"]); ret = eng.daily_returns(df, trades, sizing="fraction")
""",
"rsi2_engine.py": """
sys.path.insert(0, str(Path(EDGE) / "rsi2_engine"))   # same import order as the RSI2 notebooks
import rsi2_engine as eng, variant_config as vc
vc.EDGE_DIR = Path(EDGE); cfg = vc.load_variant(VARIANT)
eng.set_engine_defaults(**cfg.get("engine_defaults", {}))
_cp = eng.ENGINE_DEFAULTS.get("csv_path")
if _cp and not Path(_cp).is_absolute() and not Path(_cp).exists():      # relative data path does not resolve from here: look in <ancestor>/data/**
    _hit = next((h for b in Path(EDGE).resolve().parents if (b / "data").is_dir() for h in (b / "data").rglob(Path(_cp).name)), None)
    if _hit is None: raise FileNotFoundError("data file " + Path(_cp).name + " not found in any <ancestor>/data folder of " + EDGE)
    eng.ENGINE_DEFAULTS["csv_path"] = str(_hit)
P = cfg["params"]
raw = eng.load_data(cfg["instrument"]["ticker"], start=cfg["instrument"]["start"])
df = eng.prepare(raw, sma_len=P["sma_len"])
trades = eng.run_rsi2_backtest(df, rsi_thr=P["rsi_thr"], sma_len=P["sma_len"], exit_mode=P["exit_mode"], slip_bps_per_side=P["slip_bps_per_side"])
FRAC = 1.0                                             # official run = 1% risk ATR sizing; size_fraction here = multiple of that sizing
ret = eng.daily_returns(df, trades, sizing="atr")
""",
}
RUNNER = """
import sys, json
from pathlib import Path
import pandas as pd
EDGE, VARIANT, OUT, YSHA = {edge!r}, {variant!r}, {out!r}, {ysha!r}
sys.path.insert(0, EDGE)
for b in (Path(EDGE).resolve(), *Path(EDGE).resolve().parents):
    if (b / "utils" / "utils").is_dir(): sys.path.insert(0, str(b / "utils" / "utils")); break
{recipe}
pd.Series(ret, name="ret").to_csv(OUT, index_label="date")
Path(OUT + ".meta.json").write_text(json.dumps(dict(frac=FRAC, yaml_sha=YSHA)))
"""

def get_returns(row):
    csv = row.run_dir / "daily_returns.csv"; meta = Path(str(csv) + ".meta.json")
    ysha = hashlib.sha1(row.yaml.read_bytes()).hexdigest()[:10]
    fresh = csv.exists() and meta.exists() and json.loads(meta.read_text()).get("yaml_sha") == ysha and not FORCE_REFRESH
    if not fresh:
        recipe = next((r for f, r in RECIPES.items() if any(p.is_file() for p in (row.edge_dir / f, row.edge_dir / Path(f).stem / f))), None)
        if recipe is None: raise RuntimeError(f"{row.variant}: no engine recipe for {row.edge_dir.name}. Add one to RECIPES or drop a daily_returns.csv in {row.run_dir}")
        print(f"   building {row.variant} from its engine (one time; cached afterwards)...")
        row.run_dir.mkdir(parents=True, exist_ok=True)
        code = RUNNER.format(edge=str(row.edge_dir), variant=row.variant, out=str(csv), ysha=ysha, recipe=recipe)
        # engines resolve relative data paths (../../data/...) from cwd: use the 02_strategy_development copy of the edge folder, which has that depth
        dev = ROOTS["development"]; cwd = next((d for d in (dev / row.edge_dir.name, row.edge_dir) if d.is_dir()), row.edge_dir)
        p = subprocess.run([sys.executable, "-c", code], cwd=cwd, capture_output=True, text=True)
        if p.returncode: raise RuntimeError(f"{row.variant}: engine failed\n{p.stderr[-3000:]}")
    s = pd.read_csv(csv, index_col=0, parse_dates=True).iloc[:, 0].astype(float)
    s.index = pd.to_datetime(s.index)
    if getattr(s.index, "tz", None) is not None: s.index = s.index.tz_localize(None)
    s = s.groupby(s.index.normalize()).sum()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D")).fillna(0.0), float(json.loads(meta.read_text())["frac"])

def validation_status(run_dir):
    f = run_dir / "03_validation.json"
    if not f.exists(): return "03_validation.json not found"
    j = json.loads(f.read_text())
    hit = next((f"{k}={j[k]}" for k in ("overall", "verdict", "status", "passed") if k in j), None)
    return hit or f"see {f.name}"

SL, raw = {}, {}
for k in keys:
    row = resolve(k); raw[k], frac = get_returns(row)
    SL[k] = dict(name=row.id, frac=frac, max_frac=MAX_SIZE.get(k, np.inf), status=validation_status(row.run_dir), path=row.run_dir / "daily_returns.csv", source=row.source)
display(pd.DataFrame({k: dict(id=v["name"], source=v["source"], size_fraction=v["frac"], days=len(raw[k]), first=raw[k].index[0].date(), last=raw[k].index[-1].date()) for k, v in SL.items()}).T)

OUT_DIR = Path.cwd() / "runs" / PORTFOLIO_ID; OUT_DIR.mkdir(parents=True, exist_ok=True)   # next to this notebook

unit = {k: raw[k] / SL[k]["frac"] for k in keys}                 # return per 1.0x nominal exposure
first = {k: r[r != 0].index[0] for k, r in raw.items()}; last = {k: r[r != 0].index[-1] for k, r in raw.items()}
START, END = max(first.values()), min(last.values())             # common window: all edges already trading
U = pd.concat(unit, axis=1).loc[START:END].fillna(0.0); YEARS = len(U) / PPY
print(f"Common window: {START:%Y-%m-%d} -> {END:%Y-%m-%d} | {len(U)} days | {YEARS:.2f} years")
check("2. Data", f"common window >= {MIN_OVERLAP_YEARS:g} years", YEARS >= MIN_OVERLAP_YEARS, f"{YEARS:.2f}")
```

    Roots: {'development': '/Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development', 'approved': '/Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/04_deployment/Approved_Systems'}



<div>
<style scoped>
    .dataframe tbody tr th:only-of-type {
        vertical-align: middle;
    }

    .dataframe tbody tr th {
        vertical-align: top;
    }

    .dataframe thead th {
        text-align: right;
    }
</style>
<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>id</th>
      <th>source</th>
      <th>size_fraction</th>
      <th>days</th>
      <th>first</th>
      <th>last</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>v1_axi_usdjpy</th>
      <td>GOTOBI.usdjpy.cfd.v1</td>
      <td>development</td>
      <td>2.5</td>
      <td>3593</td>
      <td>2017-01-02</td>
      <td>2026-11-03</td>
    </tr>
    <tr>
      <th>v1_btcjpy</th>
      <td>MONDAY.btcjpy.cfd.v1</td>
      <td>approved</td>
      <td>0.2</td>
      <td>1600</td>
      <td>2022-06-17</td>
      <td>2026-11-02</td>
    </tr>
  </tbody>
</table>
</div>


    Common window: 2023-01-16 -> 2026-08-24 | 1317 days | 3.61 years
       [PASS] common window >= 2 years  ->  3.61





    'PASS'



## 3. STANDALONE STATS
Same metrics for all edges on calendar days (PPY=365); each edge's own notebook may annualise with 252, so Sharpe can differ slightly.


```
def perf(r, ppy=PPY):
    r = r.astype(float); eq = (1 + r).cumprod(); yrs = len(r) / ppy; mu, sd = r.mean() * ppy, r.std() * np.sqrt(ppy)
    return dict(years=yrs, ann_ret=mu, vol=sd, sharpe=mu / sd if sd > 0 else np.nan, cagr=eq.iloc[-1] ** (1 / yrs) - 1,
                maxdd=(eq / eq.cummax() - 1).min(), active_days=(r != 0).mean())
F = {"years": "{:.2f}", "ann_ret": "{:.1%}", "vol": "{:.1%}", "sharpe": "{:.2f}", "cagr": "{:.1%}", "maxdd": "{:.2%}", "active_days": "{:.1%}"}
print("A) Full history of each edge, at its configured size_fraction"); display(pd.DataFrame({k: perf(raw[k]) for k in keys}).T.style.format(F))
print("B) Common window only, same size");                              display(pd.DataFrame({k: perf(U[k] * SL[k]["frac"]) for k in keys}).T.style.format(F))
```

    A) Full history of each edge, at its configured size_fraction



<style type="text/css">
</style>
<table id="T_c6036">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_c6036_level0_col0" class="col_heading level0 col0" >years</th>
      <th id="T_c6036_level0_col1" class="col_heading level0 col1" >ann_ret</th>
      <th id="T_c6036_level0_col2" class="col_heading level0 col2" >vol</th>
      <th id="T_c6036_level0_col3" class="col_heading level0 col3" >sharpe</th>
      <th id="T_c6036_level0_col4" class="col_heading level0 col4" >cagr</th>
      <th id="T_c6036_level0_col5" class="col_heading level0 col5" >maxdd</th>
      <th id="T_c6036_level0_col6" class="col_heading level0 col6" >active_days</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_c6036_level0_row0" class="row_heading level0 row0" >v1_axi_usdjpy</th>
      <td id="T_c6036_row0_col0" class="data row0 col0" >9.84</td>
      <td id="T_c6036_row0_col1" class="data row0 col1" >4.3%</td>
      <td id="T_c6036_row0_col2" class="data row0 col2" >3.5%</td>
      <td id="T_c6036_row0_col3" class="data row0 col3" >1.24</td>
      <td id="T_c6036_row0_col4" class="data row0 col4" >4.4%</td>
      <td id="T_c6036_row0_col5" class="data row0 col5" >-4.23%</td>
      <td id="T_c6036_row0_col6" class="data row0 col6" >19.4%</td>
    </tr>
    <tr>
      <th id="T_c6036_level0_row1" class="row_heading level0 row1" >v1_btcjpy</th>
      <td id="T_c6036_row1_col0" class="data row1 col0" >4.38</td>
      <td id="T_c6036_row1_col1" class="data row1 col1" >3.8%</td>
      <td id="T_c6036_row1_col2" class="data row1 col2" >2.6%</td>
      <td id="T_c6036_row1_col3" class="data row1 col3" >1.47</td>
      <td id="T_c6036_row1_col4" class="data row1 col4" >3.9%</td>
      <td id="T_c6036_row1_col5" class="data row1 col5" >-2.20%</td>
      <td id="T_c6036_row1_col6" class="data row1 col6" >3.4%</td>
    </tr>
  </tbody>
</table>



    B) Common window only, same size



<style type="text/css">
</style>
<table id="T_b7839">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_b7839_level0_col0" class="col_heading level0 col0" >years</th>
      <th id="T_b7839_level0_col1" class="col_heading level0 col1" >ann_ret</th>
      <th id="T_b7839_level0_col2" class="col_heading level0 col2" >vol</th>
      <th id="T_b7839_level0_col3" class="col_heading level0 col3" >sharpe</th>
      <th id="T_b7839_level0_col4" class="col_heading level0 col4" >cagr</th>
      <th id="T_b7839_level0_col5" class="col_heading level0 col5" >maxdd</th>
      <th id="T_b7839_level0_col6" class="col_heading level0 col6" >active_days</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_b7839_level0_row0" class="row_heading level0 row0" >v1_axi_usdjpy</th>
      <td id="T_b7839_row0_col0" class="data row0 col0" >3.61</td>
      <td id="T_b7839_row0_col1" class="data row0 col1" >3.5%</td>
      <td id="T_b7839_row0_col2" class="data row0 col2" >3.8%</td>
      <td id="T_b7839_row0_col3" class="data row0 col3" >0.90</td>
      <td id="T_b7839_row0_col4" class="data row0 col4" >3.4%</td>
      <td id="T_b7839_row0_col5" class="data row0 col5" >-4.23%</td>
      <td id="T_b7839_row0_col6" class="data row0 col6" >19.4%</td>
    </tr>
    <tr>
      <th id="T_b7839_level0_row1" class="row_heading level0 row1" >v1_btcjpy</th>
      <td id="T_b7839_row1_col0" class="data row1 col0" >3.61</td>
      <td id="T_b7839_row1_col1" class="data row1 col1" >4.6%</td>
      <td id="T_b7839_row1_col2" class="data row1 col2" >2.9%</td>
      <td id="T_b7839_row1_col3" class="data row1 col3" >1.62</td>
      <td id="T_b7839_row1_col4" class="data row1 col4" >4.7%</td>
      <td id="T_b7839_row1_col5" class="data row1 col5" >-2.20%</td>
      <td id="T_b7839_row1_col6" class="data row1 col6" >4.1%</td>
    </tr>
  </tbody>
</table>



## 4. CORRELATION (Guide §2, §3, §5)
Returns, never equity levels · common frequency (daily / weekly / monthly) · `> 0.50` red alert, `0.20-0.50` watch, `< 0.20` good · structural vs parametric.

**Trap for sparse edges:** a series full of zeros correlates ≈ 0 *by construction*. So co-activity and the number of overlapping periods are reported; with too few co-active weeks the number proves nothing.


```
def at_freq(df, f): return df if f == "D" else (1 + df).resample(f).prod() - 1
def block_idx(n, size, block, rng, nsim):
    nb = int(np.ceil(size / block)); st = rng.integers(0, n, size=(nsim, nb))
    return ((st[:, :, None] + np.arange(block)[None, None, :]) % n).reshape(nsim, -1)[:, :size]
R = U * pd.Series({k: SL[k]["frac"] for k in keys})              # returns at configured size (what runs today)
rng = np.random.default_rng(SEED); pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]
rows, mats = [], {}
for f, nm, blk in (("D", "daily", BLOCK_DAYS), ("W", "weekly", 4), ("MS", "monthly", 2)):
    X = at_freq(R, f); mats[nm] = X.corr(); A = X != 0
    for a, b in pairs:
        bi = block_idx(len(X), len(X), min(blk, len(X)), rng, 500)
        bs = [pd.Series(X[a].values[i]).corr(pd.Series(X[b].values[i])) for i in bi]
        rows.append(dict(freq=nm, pair=f"{a} / {b}", corr=X[a].corr(X[b]), ci5=np.nanpercentile(bs, 5), ci95=np.nanpercentile(bs, 95), periods=len(X), both_active=int((A[a] & A[b]).sum())))
ct = pd.DataFrame(rows); display(ct.style.format({"corr": "{:+.2f}", "ci5": "{:+.2f}", "ci95": "{:+.2f}"}))
fig, ax = figs(1, 1, (5.2, 4.2)); Cw = mats["weekly"]
im = ax.imshow(Cw.values, cmap=LinearSegmentedColormap.from_list("c", [GREEN, PANEL, RED]), vmin=-1, vmax=1); ax.grid(False)
ax.set_xticks(range(N)); ax.set_xticklabels(keys, color=SUB); ax.set_yticks(range(N)); ax.set_yticklabels(keys, color=SUB)
for i in range(N):
    for j in range(N): ax.text(j, i, f"{Cw.values[i, j]:+.2f}", ha="center", va="center", color=TXT, fontsize=11, fontweight="bold")
ttl(ax, "Decorrelation matrix (weekly)"); plt.tight_layout(); plt.show()
for a, b in pairs:
    w = ct[(ct.freq == "weekly") & (ct.pair == f"{a} / {b}")].iloc[0]
    check("4. Correlation", f"{a}/{b}: weekly corr estimable (>= {N_MIN_COACTIVE} co-active weeks)", w.both_active >= N_MIN_COACTIVE,
          f"{w.both_active} co-active weeks" + ("" if w.both_active >= N_MIN_COACTIVE else f": the {w['corr']:+.2f} does NOT prove decorrelation (zeros dominate)"))
    check("4. Correlation", f"{a}/{b}: weekly corr < {CORR_ALERT}", w["corr"] < CORR_ALERT, f"{w['corr']:+.2f} (CI90 {w.ci5:+.2f}..{w.ci95:+.2f})")
check("4. Correlation", "structural reason declared (WHY_UNCORRELATED)", bool(WHY_UNCORRELATED.strip()), "see EXPERIMENT")
```


<style type="text/css">
</style>
<table id="T_f2a34">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_f2a34_level0_col0" class="col_heading level0 col0" >freq</th>
      <th id="T_f2a34_level0_col1" class="col_heading level0 col1" >pair</th>
      <th id="T_f2a34_level0_col2" class="col_heading level0 col2" >corr</th>
      <th id="T_f2a34_level0_col3" class="col_heading level0 col3" >ci5</th>
      <th id="T_f2a34_level0_col4" class="col_heading level0 col4" >ci95</th>
      <th id="T_f2a34_level0_col5" class="col_heading level0 col5" >periods</th>
      <th id="T_f2a34_level0_col6" class="col_heading level0 col6" >both_active</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_f2a34_level0_row0" class="row_heading level0 row0" >0</th>
      <td id="T_f2a34_row0_col0" class="data row0 col0" >daily</td>
      <td id="T_f2a34_row0_col1" class="data row0 col1" >v1_axi_usdjpy / v1_btcjpy</td>
      <td id="T_f2a34_row0_col2" class="data row0 col2" >+0.01</td>
      <td id="T_f2a34_row0_col3" class="data row0 col3" >-0.02</td>
      <td id="T_f2a34_row0_col4" class="data row0 col4" >+0.05</td>
      <td id="T_f2a34_row0_col5" class="data row0 col5" >1317</td>
      <td id="T_f2a34_row0_col6" class="data row0 col6" >11</td>
    </tr>
    <tr>
      <th id="T_f2a34_level0_row1" class="row_heading level0 row1" >1</th>
      <td id="T_f2a34_row1_col0" class="data row1 col0" >weekly</td>
      <td id="T_f2a34_row1_col1" class="data row1 col1" >v1_axi_usdjpy / v1_btcjpy</td>
      <td id="T_f2a34_row1_col2" class="data row1 col2" >+0.07</td>
      <td id="T_f2a34_row1_col3" class="data row1 col3" >-0.06</td>
      <td id="T_f2a34_row1_col4" class="data row1 col4" >+0.21</td>
      <td id="T_f2a34_row1_col5" class="data row1 col5" >189</td>
      <td id="T_f2a34_row1_col6" class="data row1 col6" >52</td>
    </tr>
    <tr>
      <th id="T_f2a34_level0_row2" class="row_heading level0 row2" >2</th>
      <td id="T_f2a34_row2_col0" class="data row2 col0" >monthly</td>
      <td id="T_f2a34_row2_col1" class="data row2 col1" >v1_axi_usdjpy / v1_btcjpy</td>
      <td id="T_f2a34_row2_col2" class="data row2 col2" >-0.01</td>
      <td id="T_f2a34_row2_col3" class="data row2 col3" >-0.28</td>
      <td id="T_f2a34_row2_col4" class="data row2 col4" >+0.18</td>
      <td id="T_f2a34_row2_col5" class="data row2 col5" >44</td>
      <td id="T_f2a34_row2_col6" class="data row2 col6" >27</td>
    </tr>
  </tbody>
</table>




    
![png](Portfolio_Development_files/Portfolio_Development_8_1.png)
    


       [PASS] v1_axi_usdjpy/v1_btcjpy: weekly corr estimable (>= 30 co-active weeks)  ->  52 co-active weeks
       [PASS] v1_axi_usdjpy/v1_btcjpy: weekly corr < 0.5  ->  +0.07 (CI90 -0.06..+0.21)
       [PASS] structural reason declared (WHY_UNCORRELATED)  ->  see EXPERIMENT





    'PASS'



### 4.2 Co-activity and bad days (Guide §6.2)
`lift = P(both active) / (P(A)·P(B))`: ≈ 1 independent in calendar, > 1 tend to coincide. Then the worst days of each edge and what the others did that day.


```
Act, Loss = (R != 0), (R < 0); rows = []
for a, b in pairs:
    pa, pb, pab = Act[a].mean(), Act[b].mean(), (Act[a] & Act[b]).mean()
    rows.append(dict(pair=f"{a} / {b}", P_A=pa, P_B=pb, P_both=pab, lift=pab / (pa * pb) if pa * pb else np.nan,
                     joint_loss_days=int((Loss[a] & Loss[b]).sum()), expected_if_indep=Loss[a].sum() * Loss[b].mean()))
display(pd.DataFrame(rows).style.format({"P_A": "{:.1%}", "P_B": "{:.1%}", "P_both": "{:.2%}", "lift": "{:.2f}", "expected_if_indep": "{:.1f}"}))
for k in keys:
    d = R[k].nsmallest(8); t = R.loc[d.index].copy(); t["others_also_lose"] = (t.drop(columns=k) < 0).any(axis=1)
    print(f"Worst days of {k} (configured size)"); display(t.style.format({c: "{:+.3%}" for c in keys}))
```


<style type="text/css">
</style>
<table id="T_e3d76">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_e3d76_level0_col0" class="col_heading level0 col0" >pair</th>
      <th id="T_e3d76_level0_col1" class="col_heading level0 col1" >P_A</th>
      <th id="T_e3d76_level0_col2" class="col_heading level0 col2" >P_B</th>
      <th id="T_e3d76_level0_col3" class="col_heading level0 col3" >P_both</th>
      <th id="T_e3d76_level0_col4" class="col_heading level0 col4" >lift</th>
      <th id="T_e3d76_level0_col5" class="col_heading level0 col5" >joint_loss_days</th>
      <th id="T_e3d76_level0_col6" class="col_heading level0 col6" >expected_if_indep</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_e3d76_level0_row0" class="row_heading level0 row0" >0</th>
      <td id="T_e3d76_row0_col0" class="data row0 col0" >v1_axi_usdjpy / v1_btcjpy</td>
      <td id="T_e3d76_row0_col1" class="data row0 col1" >19.4%</td>
      <td id="T_e3d76_row0_col2" class="data row0 col2" >4.1%</td>
      <td id="T_e3d76_row0_col3" class="data row0 col3" >0.84%</td>
      <td id="T_e3d76_row0_col4" class="data row0 col4" >1.05</td>
      <td id="T_e3d76_row0_col5" class="data row0 col5" >2</td>
      <td id="T_e3d76_row0_col6" class="data row0 col6" >1.2</td>
    </tr>
  </tbody>
</table>



    Worst days of v1_axi_usdjpy (configured size)



<style type="text/css">
</style>
<table id="T_5791f">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_5791f_level0_col0" class="col_heading level0 col0" >v1_axi_usdjpy</th>
      <th id="T_5791f_level0_col1" class="col_heading level0 col1" >v1_btcjpy</th>
      <th id="T_5791f_level0_col2" class="col_heading level0 col2" >others_also_lose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_5791f_level0_row0" class="row_heading level0 row0" >2023-12-08 00:00:00</th>
      <td id="T_5791f_row0_col0" class="data row0 col0" >-1.921%</td>
      <td id="T_5791f_row0_col1" class="data row0 col1" >+0.000%</td>
      <td id="T_5791f_row0_col2" class="data row0 col2" >False</td>
    </tr>
    <tr>
      <th id="T_5791f_level0_row1" class="row_heading level0 row1" >2024-08-05 00:00:00</th>
      <td id="T_5791f_row1_col0" class="data row1 col0" >-1.906%</td>
      <td id="T_5791f_row1_col1" class="data row1 col1" >+0.000%</td>
      <td id="T_5791f_row1_col2" class="data row1 col2" >False</td>
    </tr>
    <tr>
      <th id="T_5791f_level0_row2" class="row_heading level0 row2" >2024-11-29 00:00:00</th>
      <td id="T_5791f_row2_col0" class="data row2 col0" >-1.478%</td>
      <td id="T_5791f_row2_col1" class="data row2 col1" >+0.000%</td>
      <td id="T_5791f_row2_col2" class="data row2 col2" >False</td>
    </tr>
    <tr>
      <th id="T_5791f_level0_row3" class="row_heading level0 row3" >2023-02-24 00:00:00</th>
      <td id="T_5791f_row3_col0" class="data row3 col0" >-1.046%</td>
      <td id="T_5791f_row3_col1" class="data row3 col1" >+0.000%</td>
      <td id="T_5791f_row3_col2" class="data row3 col2" >False</td>
    </tr>
    <tr>
      <th id="T_5791f_level0_row4" class="row_heading level0 row4" >2025-04-10 00:00:00</th>
      <td id="T_5791f_row4_col0" class="data row4 col0" >-0.926%</td>
      <td id="T_5791f_row4_col1" class="data row4 col1" >+0.000%</td>
      <td id="T_5791f_row4_col2" class="data row4 col2" >False</td>
    </tr>
    <tr>
      <th id="T_5791f_level0_row5" class="row_heading level0 row5" >2025-06-13 00:00:00</th>
      <td id="T_5791f_row5_col0" class="data row5 col0" >-0.852%</td>
      <td id="T_5791f_row5_col1" class="data row5 col1" >+0.000%</td>
      <td id="T_5791f_row5_col2" class="data row5 col2" >False</td>
    </tr>
    <tr>
      <th id="T_5791f_level0_row6" class="row_heading level0 row6" >2025-07-10 00:00:00</th>
      <td id="T_5791f_row6_col0" class="data row6 col0" >-0.788%</td>
      <td id="T_5791f_row6_col1" class="data row6 col1" >+0.000%</td>
      <td id="T_5791f_row6_col2" class="data row6 col2" >False</td>
    </tr>
    <tr>
      <th id="T_5791f_level0_row7" class="row_heading level0 row7" >2024-07-25 00:00:00</th>
      <td id="T_5791f_row7_col0" class="data row7 col0" >-0.780%</td>
      <td id="T_5791f_row7_col1" class="data row7 col1" >+0.000%</td>
      <td id="T_5791f_row7_col2" class="data row7 col2" >False</td>
    </tr>
  </tbody>
</table>



    Worst days of v1_btcjpy (configured size)



<style type="text/css">
</style>
<table id="T_3cd6f">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_3cd6f_level0_col0" class="col_heading level0 col0" >v1_axi_usdjpy</th>
      <th id="T_3cd6f_level0_col1" class="col_heading level0 col1" >v1_btcjpy</th>
      <th id="T_3cd6f_level0_col2" class="col_heading level0 col2" >others_also_lose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_3cd6f_level0_row0" class="row_heading level0 row0" >2023-12-11 00:00:00</th>
      <td id="T_3cd6f_row0_col0" class="data row0 col0" >+0.000%</td>
      <td id="T_3cd6f_row0_col1" class="data row0 col1" >-1.079%</td>
      <td id="T_3cd6f_row0_col2" class="data row0 col2" >False</td>
    </tr>
    <tr>
      <th id="T_3cd6f_level0_row1" class="row_heading level0 row1" >2024-11-25 00:00:00</th>
      <td id="T_3cd6f_row1_col0" class="data row1 col0" >-0.266%</td>
      <td id="T_3cd6f_row1_col1" class="data row1 col1" >-1.042%</td>
      <td id="T_3cd6f_row1_col2" class="data row1 col2" >True</td>
    </tr>
    <tr>
      <th id="T_3cd6f_level0_row2" class="row_heading level0 row2" >2023-01-30 00:00:00</th>
      <td id="T_3cd6f_row2_col0" class="data row2 col0" >+0.000%</td>
      <td id="T_3cd6f_row2_col1" class="data row2 col1" >-0.705%</td>
      <td id="T_3cd6f_row2_col2" class="data row2 col2" >False</td>
    </tr>
    <tr>
      <th id="T_3cd6f_level0_row3" class="row_heading level0 row3" >2025-03-10 00:00:00</th>
      <td id="T_3cd6f_row3_col0" class="data row3 col0" >-0.606%</td>
      <td id="T_3cd6f_row3_col1" class="data row3 col1" >-0.619%</td>
      <td id="T_3cd6f_row3_col2" class="data row3 col2" >True</td>
    </tr>
    <tr>
      <th id="T_3cd6f_level0_row4" class="row_heading level0 row4" >2024-04-15 00:00:00</th>
      <td id="T_3cd6f_row4_col0" class="data row4 col0" >+0.273%</td>
      <td id="T_3cd6f_row4_col1" class="data row4 col1" >-0.615%</td>
      <td id="T_3cd6f_row4_col2" class="data row4 col2" >False</td>
    </tr>
    <tr>
      <th id="T_3cd6f_level0_row5" class="row_heading level0 row5" >2024-12-09 00:00:00</th>
      <td id="T_3cd6f_row5_col0" class="data row5 col0" >+0.000%</td>
      <td id="T_3cd6f_row5_col1" class="data row5 col1" >-0.604%</td>
      <td id="T_3cd6f_row5_col2" class="data row5 col2" >False</td>
    </tr>
    <tr>
      <th id="T_3cd6f_level0_row6" class="row_heading level0 row6" >2023-03-27 00:00:00</th>
      <td id="T_3cd6f_row6_col0" class="data row6 col0" >+0.000%</td>
      <td id="T_3cd6f_row6_col1" class="data row6 col1" >-0.588%</td>
      <td id="T_3cd6f_row6_col2" class="data row6 col2" >False</td>
    </tr>
    <tr>
      <th id="T_3cd6f_level0_row7" class="row_heading level0 row7" >2024-07-29 00:00:00</th>
      <td id="T_3cd6f_row7_col0" class="data row7 col0" >+0.000%</td>
      <td id="T_3cd6f_row7_col1" class="data row7 col1" >-0.497%</td>
      <td id="T_3cd6f_row7_col2" class="data row7 col2" >False</td>
    </tr>
  </tbody>
</table>



### 4.3 Rolling correlation and shared JPY factor
Guide §2.3: correlation is not constant. The JPY block is the most serious structural objection (both edges are long vs the yen); set `JPY_PROXY_CSV` to activate it.


```
Wk = at_freq(R, "W")
if len(Wk) >= 70:
    fig, ax = figs(1, 1, (14, 3.4))
    for i, (a, b) in enumerate(pairs): ax.plot(Wk.index, Wk[a].rolling(52).corr(Wk[b]), color=PAL[i % len(PAL)], lw=1.5, label=f"{a}/{b}")
    ax.axhline(CORR_ALERT, color=RED, ls="--", lw=1.1, label=f"alert {CORR_ALERT}"); ax.axhline(0, color=SUB, lw=.7)
    ttl(ax, "Rolling weekly correlation (52 weeks)"); leg(ax); plt.tight_layout(); plt.show()
else: print(f"Only {len(Wk)} weeks: too short for a 52-week rolling correlation.")

if JPY_PROXY_CSV is None:
    check("4. Correlation", "shared JPY factor measured", None, "set JPY_PROXY_CSV")
else:
    fx = pd.read_csv(JPY_PROXY_CSV, index_col=0, parse_dates=True).iloc[:, 0].astype(float)
    fx.index = (fx.index.tz_localize(None) if getattr(fx.index, "tz", None) else fx.index).normalize()
    jr = fx.pct_change().reindex(R.index).fillna(0.0); rally = jr <= jr[jr != 0].quantile(0.05)
    t = pd.DataFrame({k: dict(corr_vs_USDJPY_active=R.loc[Act[k], k].corr(jr[Act[k]]) if Act[k].sum() > 5 else np.nan,
                              active_in_yen_rally=int((Act[k] & rally).sum()), mean_pnl_in_rally=R.loc[Act[k] & rally, k].mean(),
                              mean_pnl_otherwise=R.loc[Act[k] & ~rally, k].mean()) for k in keys}).T
    display(t.style.format({"corr_vs_USDJPY_active": "{:+.2f}", "mean_pnl_in_rally": "{:+.3%}", "mean_pnl_otherwise": "{:+.3%}"}))
    check("4. Correlation", "shared JPY factor measured", True, "if all edges lose in yen rallies, the decorrelation is parametric")
```


    
![png](Portfolio_Development_files/Portfolio_Development_12_0.png)
    


       [SKIP] shared JPY factor measured  ->  set JPY_PROXY_CSV


## 5. HOW MANY EDGES: 1/√N (Guide §7)
`σ_portfolio / σ_edge = √(1/N + (1 − 1/N)·ρ)`. *"3 truly different systems beat 15 cousins."*


```
rr = lambda n, rho: np.sqrt(1 / n + (1 - 1 / n) * rho)
off = ~np.eye(N, dtype=bool); rho_hat = np.nanmean(mats["weekly"].values[off]); rho_use = (1 - SHRINK_RHO) * rho_hat + SHRINK_RHO * PRIOR_RHO
ns = np.arange(1, 11); fig, ax = figs(1, 1, (8, 3.8))
for i, (rho, ls) in enumerate(((0.0, "-"), (0.3, "--"), (0.6, ":"))): ax.plot(ns, rr(ns, rho), ls, color=PAL[i], lw=1.6, label=f"ρ = {rho}")
ax.scatter([N], [rr(N, rho_use)], color=ORANGE, s=70, zorder=5, label=f"you: N={N}, ρ={rho_use:.2f}")
ttl(ax, "The risk floor is set by ρ, not by N"); lab(ax, "N edges", "portfolio risk / single-edge risk"); leg(ax); plt.tight_layout(); plt.show()
print(f"measured weekly ρ = {rho_hat:+.2f} | shrunk ρ (prior {PRIOR_RHO}, λ={SHRINK_RHO}) = {rho_use:.2f} | relative risk at N={N}: {rr(N, rho_use):.2f} (floor: {np.sqrt(max(rho_use, 0)):.2f})")
```


    
![png](Portfolio_Development_files/Portfolio_Development_14_0.png)
    


    measured weekly ρ = +0.07 | shrunk ρ (prior 0.2, λ=0.5) = 0.13 | relative risk at N=2: 0.75 (floor: 0.36)


## 6. WEIGHT SCHEMES
**Normalise:** each edge is scaled to `TARGET_VOL` by `SCALE_i = TARGET_VOL / σ_i`; weights `w` are then a **risk split** and the final size is `exposure_i = L · w_i · SCALE_i`.
Schemes: `equal_vol` · `erc` (equal risk contribution, shrunk covariance) · `min_var` · `max_sharpe_shrunk` · `as_configured` (reference: what runs today).


```
sig_u = U.std() * np.sqrt(PPY); SCALE = TARGET_VOL / sig_u; V = U * SCALE
mu_hat, cov_hat = V.mean().values * PPY, V.cov().values * PPY
def shrink_cov(cov, prior=PRIOR_RHO, lam=SHRINK_RHO):
    d = np.sqrt(np.diag(cov)); rho = cov / np.outer(d, d); o = ~np.eye(len(d), dtype=bool); rho[o] = (1 - lam) * rho[o] + lam * prior
    return rho * np.outer(d, d)
def _solve(fun, n):
    r = optimize.minimize(fun, np.full(n, 1 / n), bounds=[(0, 1)] * n, method="SLSQP", constraints=({"type": "eq", "fun": lambda w: w.sum() - 1},))
    w = np.clip(r.x, 0, None); return w / w.sum()
def w_equal(mu, cov):  return np.full(len(mu), 1 / len(mu))
def w_minvar(mu, cov): return _solve(lambda w: w @ cov @ w, len(mu))
def w_erc(mu, cov):
    n = len(mu)
    def f(w): rc = w * (cov @ w); rc = rc / rc.sum(); return ((rc - 1 / n) ** 2).sum()
    return _solve(f, n)
def w_maxsr(mu, cov):
    m = (1 - MEAN_SHRINK) * mu + MEAN_SHRINK * mu.mean(); return _solve(lambda w: -(w @ m) / np.sqrt(w @ cov @ w), len(mu))
SCHEMES = {"equal_vol": w_equal, "erc": w_erc, "min_var": w_minvar, "max_sharpe_shrunk": w_maxsr}
cov_s = shrink_cov(cov_hat); W = pd.DataFrame({n: f(mu_hat, cov_s) for n, f in SCHEMES.items()}, index=keys)
cfg_exp = np.array([SL[k]["frac"] for k in keys]); cfg_w = cfg_exp / SCALE.values; W["as_configured"] = cfg_w / cfg_w.sum()
pm = lambda w, L=1.0: perf(pd.Series(L * V.values @ np.asarray(w), index=V.index))
print("Risk weights by scheme (sum to 1)"); display(W.style.format("{:.1%}"))
print("Common-window performance, normalised space (L=1). Descriptive, NOT a selection criterion:")
display(pd.DataFrame({n: pm(W[n]) for n in W.columns}).T[["ann_ret", "vol", "sharpe", "cagr", "maxdd"]].style.format(F))
print("Nominal exposure each edge needs to sit at TARGET_VOL:", {k: f"{SCALE[k]:.2f}x" for k in keys}, "| configured today:", {k: f"{SL[k]['frac']:.2f}x" for k in keys})
print("=> risk split implied by today's sizes:", {k: f"{v:.0%}" for k, v in zip(keys, W['as_configured'])})
```

    Risk weights by scheme (sum to 1)



<style type="text/css">
</style>
<table id="T_16e2d">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_16e2d_level0_col0" class="col_heading level0 col0" >equal_vol</th>
      <th id="T_16e2d_level0_col1" class="col_heading level0 col1" >erc</th>
      <th id="T_16e2d_level0_col2" class="col_heading level0 col2" >min_var</th>
      <th id="T_16e2d_level0_col3" class="col_heading level0 col3" >max_sharpe_shrunk</th>
      <th id="T_16e2d_level0_col4" class="col_heading level0 col4" >as_configured</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_16e2d_level0_row0" class="row_heading level0 row0" >v1_axi_usdjpy</th>
      <td id="T_16e2d_row0_col0" class="data row0 col0" >50.0%</td>
      <td id="T_16e2d_row0_col1" class="data row0 col1" >50.0%</td>
      <td id="T_16e2d_row0_col2" class="data row0 col2" >50.0%</td>
      <td id="T_16e2d_row0_col3" class="data row0 col3" >41.2%</td>
      <td id="T_16e2d_row0_col4" class="data row0 col4" >57.1%</td>
    </tr>
    <tr>
      <th id="T_16e2d_level0_row1" class="row_heading level0 row1" >v1_btcjpy</th>
      <td id="T_16e2d_row1_col0" class="data row1 col0" >50.0%</td>
      <td id="T_16e2d_row1_col1" class="data row1 col1" >50.0%</td>
      <td id="T_16e2d_row1_col2" class="data row1 col2" >50.0%</td>
      <td id="T_16e2d_row1_col3" class="data row1 col3" >58.8%</td>
      <td id="T_16e2d_row1_col4" class="data row1 col4" >42.9%</td>
    </tr>
  </tbody>
</table>



    Common-window performance, normalised space (L=1). Descriptive, NOT a selection criterion:



<style type="text/css">
</style>
<table id="T_bb4ab">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_bb4ab_level0_col0" class="col_heading level0 col0" >ann_ret</th>
      <th id="T_bb4ab_level0_col1" class="col_heading level0 col1" >vol</th>
      <th id="T_bb4ab_level0_col2" class="col_heading level0 col2" >sharpe</th>
      <th id="T_bb4ab_level0_col3" class="col_heading level0 col3" >cagr</th>
      <th id="T_bb4ab_level0_col4" class="col_heading level0 col4" >maxdd</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_bb4ab_level0_row0" class="row_heading level0 row0" >equal_vol</th>
      <td id="T_bb4ab_row0_col0" class="data row0 col0" >12.6%</td>
      <td id="T_bb4ab_row0_col1" class="data row0 col1" >7.1%</td>
      <td id="T_bb4ab_row0_col2" class="data row0 col2" >1.77</td>
      <td id="T_bb4ab_row0_col3" class="data row0 col3" >13.2%</td>
      <td id="T_bb4ab_row0_col4" class="data row0 col4" >-5.80%</td>
    </tr>
    <tr>
      <th id="T_bb4ab_level0_row1" class="row_heading level0 row1" >erc</th>
      <td id="T_bb4ab_row1_col0" class="data row1 col0" >12.6%</td>
      <td id="T_bb4ab_row1_col1" class="data row1 col1" >7.1%</td>
      <td id="T_bb4ab_row1_col2" class="data row1 col2" >1.77</td>
      <td id="T_bb4ab_row1_col3" class="data row1 col3" >13.2%</td>
      <td id="T_bb4ab_row1_col4" class="data row1 col4" >-5.80%</td>
    </tr>
    <tr>
      <th id="T_bb4ab_level0_row2" class="row_heading level0 row2" >min_var</th>
      <td id="T_bb4ab_row2_col0" class="data row2 col0" >12.6%</td>
      <td id="T_bb4ab_row2_col1" class="data row2 col1" >7.1%</td>
      <td id="T_bb4ab_row2_col2" class="data row2 col2" >1.77</td>
      <td id="T_bb4ab_row2_col3" class="data row2 col3" >13.2%</td>
      <td id="T_bb4ab_row2_col4" class="data row2 col4" >-5.80%</td>
    </tr>
    <tr>
      <th id="T_bb4ab_level0_row3" class="row_heading level0 row3" >max_sharpe_shrunk</th>
      <td id="T_bb4ab_row3_col0" class="data row3 col0" >13.2%</td>
      <td id="T_bb4ab_row3_col1" class="data row3 col1" >7.2%</td>
      <td id="T_bb4ab_row3_col2" class="data row3 col2" >1.83</td>
      <td id="T_bb4ab_row3_col3" class="data row3 col3" >13.9%</td>
      <td id="T_bb4ab_row3_col4" class="data row3 col4" >-5.84%</td>
    </tr>
    <tr>
      <th id="T_bb4ab_level0_row4" class="row_heading level0 row4" >as_configured</th>
      <td id="T_bb4ab_row4_col0" class="data row4 col0" >12.1%</td>
      <td id="T_bb4ab_row4_col1" class="data row4 col1" >7.2%</td>
      <td id="T_bb4ab_row4_col2" class="data row4 col2" >1.68</td>
      <td id="T_bb4ab_row4_col3" class="data row4 col3" >12.6%</td>
      <td id="T_bb4ab_row4_col4" class="data row4 col4" >-6.41%</td>
    </tr>
  </tbody>
</table>



    Nominal exposure each edge needs to sit at TARGET_VOL: {'v1_axi_usdjpy': '6.55x', 'v1_btcjpy': '0.70x'} | configured today: {'v1_axi_usdjpy': '2.50x', 'v1_btcjpy': '0.20x'}
    => risk split implied by today's sizes: {'v1_axi_usdjpy': '57%', 'v1_btcjpy': '43%'}


### 6.1 Shape, not peak (N = 2 only)
Sweep the weight of the 2nd edge. If the Sharpe curve is flat over a wide range, the exact weight does not matter and the centre of the plateau is preferred.


```
PLATEAU = None
if N == 2:
    g = np.linspace(0, 1, 21); sh = np.array([pm([1 - x, x])["sharpe"] for x in g]); dd = np.array([pm([1 - x, x])["maxdd"] for x in g])
    ok = sh >= sh.max() * (1 - PLATEAU_TOL); PLATEAU = (g[ok].min(), g[ok].max())
    fig, ax = figs(1, 2, (14, 4.2))
    ax[0].plot(g, sh, color=BLUE, lw=1.8); ax[0].axvspan(*PLATEAU, color=GREEN, alpha=.15, label=f"plateau (Sharpe ≥ {1 - PLATEAU_TOL:.0%} of max)")
    ax[0].axvline(0.5, color=ORANGE, ls="--", lw=1.2, label="50 / 50"); ttl(ax[0], "Sharpe vs weight"); lab(ax[0], f"weight of {keys[1]}", "Sharpe"); leg(ax[0])
    ax[1].plot(g, dd * 100, color=RED, lw=1.8); ttl(ax[1], "Close drawdown vs weight"); lab(ax[1], f"weight of {keys[1]}", "max DD (%)")
    plt.tight_layout(); plt.show(); print(f"Plateau of {keys[1]} weight: {PLATEAU[0]:.0%} – {PLATEAU[1]:.0%} | max at {g[sh.argmax()]:.0%}")
else: print("N > 2: read the shape from the stability table (section 7).")
```


    
![png](Portfolio_Development_files/Portfolio_Development_18_0.png)
    


    Plateau of v1_btcjpy weight: 45% – 95% | max at 65%


## 7. WEIGHT STABILITY (block bootstrap)
How much would the max-Sharpe weight change if history had been different? If the 5-95 interval is wide, the tilt is **not identified** and the risk-based base is used.


```
rng = np.random.default_rng(SEED); bi = block_idx(len(V), len(V), BLOCK_DAYS, rng, N_BOOT)
Wb = pd.DataFrame([w_maxsr(V.values[i].mean(0) * PPY, shrink_cov(np.cov(V.values[i].T) * PPY)) for i in bi], columns=keys)
st = pd.DataFrame({"median": Wb.median(), "p5": Wb.quantile(.05), "p95": Wb.quantile(.95)}); st["width"] = st.p95 - st.p5; display(st.style.format("{:.1%}"))
fig, ax = figs(1, 1, (14, 3.6))
for i, k in enumerate(keys): ax.hist(Wb[k], bins=30, color=PAL[i % len(PAL)], alpha=0.8, edgecolor=BG, label=k)
ttl(ax, "Bootstrap distribution of the max-Sharpe weight (shrunk means)"); lab(ax, "weight", "count"); leg(ax); plt.tight_layout(); plt.show()
IDENT = bool((st["width"] < W_IDENT_WIDTH).all()); BLEND = BLEND_IF_IDENT if IDENT else 0.0
w_tilt = (st["median"] / st["median"].sum()).values; W_FINAL = pd.Series((1 - BLEND) * W["erc"].values + BLEND * w_tilt, index=keys)
wd = {k: f"{st.loc[k, 'width']:.0%}" for k in keys}
print(f"5-95 widths: {wd} -> " + ("tilt identified: blended" if IDENT else "NOT identified: risk-based base (that is the rule, not a failure)"))
if N == 2:
    s_f = pm([1 - W_FINAL.iloc[1], W_FINAL.iloc[1]])["sharpe"]; s_b = sh.max()
    print(f"In-sample Sharpe at the final weight {s_f:.2f} vs grid max {s_b:.2f}: giving up {1 - s_f / s_b:.0%} to avoid leaning on unidentified means.")
print("FINAL RISK WEIGHTS:", {k: f"{W_FINAL[k]:.1%}" for k in keys})
check("7. Weights", "final weights sum to 1 and are >= 0", abs(W_FINAL.sum() - 1) < 1e-9 and (W_FINAL >= 0).all(), str({k: round(float(v), 3) for k, v in W_FINAL.items()}))
```


<style type="text/css">
</style>
<table id="T_e4881">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_e4881_level0_col0" class="col_heading level0 col0" >median</th>
      <th id="T_e4881_level0_col1" class="col_heading level0 col1" >p5</th>
      <th id="T_e4881_level0_col2" class="col_heading level0 col2" >p95</th>
      <th id="T_e4881_level0_col3" class="col_heading level0 col3" >width</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_e4881_level0_row0" class="row_heading level0 row0" >v1_axi_usdjpy</th>
      <td id="T_e4881_row0_col0" class="data row0 col0" >41.5%</td>
      <td id="T_e4881_row0_col1" class="data row0 col1" >17.6%</td>
      <td id="T_e4881_row0_col2" class="data row0 col2" >53.1%</td>
      <td id="T_e4881_row0_col3" class="data row0 col3" >35.5%</td>
    </tr>
    <tr>
      <th id="T_e4881_level0_row1" class="row_heading level0 row1" >v1_btcjpy</th>
      <td id="T_e4881_row1_col0" class="data row1 col0" >58.5%</td>
      <td id="T_e4881_row1_col1" class="data row1 col1" >46.9%</td>
      <td id="T_e4881_row1_col2" class="data row1 col2" >82.4%</td>
      <td id="T_e4881_row1_col3" class="data row1 col3" >35.5%</td>
    </tr>
  </tbody>
</table>




    
![png](Portfolio_Development_files/Portfolio_Development_20_1.png)
    


    5-95 widths: {'v1_axi_usdjpy': '35%', 'v1_btcjpy': '35%'} -> tilt identified: blended
    In-sample Sharpe at the final weight 1.81 vs grid max 1.84: giving up 2% to avoid leaning on unidentified means.
    FINAL RISK WEIGHTS: {'v1_axi_usdjpy': '45.8%', 'v1_btcjpy': '54.2%'}
       [PASS] final weights sum to 1 and are >= 0  ->  {'v1_axi_usdjpy': 0.458, 'v1_btcjpy': 0.542}





    'PASS'



## 8. RISK BUDGET: FROM WEIGHTS TO `size_fraction`
1. **`L` by intrabar Monte Carlo:** resample day blocks, find the largest `L` with `P(intrabar DD < −HARD_LIMIT) ≤ MC_BREACH_MAX` over `MC_YEARS` (intrabar ≈ close DD × `INTRABAR_FACTOR`).
2. **Per-edge caps:** no edge exceeds the size it was validated at (`max_frac`); a binding cap shifts the risk split.
3. **Final check** with the exposures that actually result.


```
H = int(MC_YEARS * PPY); MC_IDX = block_idx(len(U), H, BLOCK_DAYS, np.random.default_rng(SEED + 1), N_MC)
def mc_stats(daily):
    eq = np.cumprod(1 + np.asarray(daily)[MC_IDX], axis=1); pk = np.maximum.accumulate(np.maximum(eq, 1.0), axis=1)
    dd = (eq / pk - 1).min(axis=1) * INTRABAR_FACTOR
    return dict(p_breach=float((dd < -HARD_LIMIT).mean()), dd_p50=float(np.median(dd)), dd_p5=float(np.percentile(dd, 5)), ret_p5=float(np.percentile(eq[:, -1] - 1, 5)))
pw = V.values @ W_FINAL.values; lo, hi = 0.0, 50.0
for _ in range(40):
    mid = (lo + hi) / 2
    if mc_stats(mid * pw)["p_breach"] <= MC_BREACH_MAX: lo = mid
    else: hi = mid
L_MC = lo; E_RAW = L_MC * W_FINAL.values * SCALE.values; caps = np.array([SL[k]["max_frac"] for k in keys])
E_FINAL = pd.Series(np.minimum(E_RAW, caps), index=keys); bind = [k for k, e, c in zip(keys, E_RAW, caps) if e > c]
tab = pd.DataFrame({"risk_weight": W_FINAL, "size_fraction_final": E_FINAL, "configured_today": pd.Series({k: SL[k]["frac"] for k in keys}), "validated_cap": pd.Series(dict(zip(keys, caps)))})
tab["change_vs_today"] = tab.size_fraction_final / tab.configured_today - 1; tab["notional_USD"] = tab.size_fraction_final * CAPITAL
display(tab.style.format({"risk_weight": "{:.1%}", "size_fraction_final": "{:.3f}x", "configured_today": "{:.2f}x", "validated_cap": "{:.2f}x", "change_vs_today": "{:+.0%}", "notional_USD": "{:,.0f}"}))
print(f"L (hard limit only, MC) = {L_MC:.2f} | binding caps: {bind or 'none'}")
daily_final, daily_today = (U * E_FINAL).sum(axis=1), (U * cfg_exp).sum(axis=1)
cmp = pd.DataFrame({"final": {**perf(daily_final), **mc_stats(daily_final.values)}, "today (configured)": {**perf(daily_today), **mc_stats(daily_today.values)}}).T
print("\nFinal portfolio vs current configuration (common window + intrabar Monte Carlo):")
display(cmp[["ann_ret", "vol", "sharpe", "cagr", "maxdd", "p_breach", "dd_p50", "dd_p5", "ret_p5"]].style.format({**F, "p_breach": "{:.1%}", "dd_p50": "{:.2%}", "dd_p5": "{:.2%}", "ret_p5": "{:.1%}"}))
fin, pf = mc_stats(daily_final.values), perf(daily_final)
check("8. Risk", f"P(touching -{HARD_LIMIT:.0%}) <= {MC_BREACH_MAX:.0%} at final sizes", fin["p_breach"] <= MC_BREACH_MAX, f"{fin['p_breach']:.1%}")
check("8. Risk", "historical close DD x intrabar factor inside the hard limit", abs(pf["maxdd"]) * INTRABAR_FACTOR < HARD_LIMIT, f"{abs(pf['maxdd']) * INTRABAR_FACTOR:.2%} vs {HARD_LIMIT:.0%}")
check("8. Risk", f"p5 of {MC_YEARS}-year return > 0", fin["ret_p5"] > 0, f"{fin['ret_p5']:.1%}")
check("8. Risk", "no edge above its validated size", bool((E_FINAL <= caps + 1e-12).all()), f"clipped: {bind or 'none'}")

eqs = pd.DataFrame({k: (1 + U[k] * E_FINAL[k]).cumprod() for k in keys}); eqs["PORTFOLIO"] = (1 + daily_final).cumprod()
fig, ax = figs(1, 2, (14, 4.5))
for i, c in enumerate(eqs.columns):
    p = c == "PORTFOLIO"; col = TXT if p else PAL[i % len(PAL)]
    ax[0].plot(eqs.index, eqs[c], color=col, lw=2.4 if p else 1.4, label=c); ax[1].plot(eqs.index, (eqs[c] / eqs[c].cummax() - 1) * 100, color=col, lw=2.0 if p else 1.1, label=c)
ttl(ax[0], "Equity at final sizes (common window)"); leg(ax[0], "upper left"); ttl(ax[1], "Close drawdown (%)"); plt.tight_layout(); plt.show()
```


<style type="text/css">
</style>
<table id="T_8055a">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_8055a_level0_col0" class="col_heading level0 col0" >risk_weight</th>
      <th id="T_8055a_level0_col1" class="col_heading level0 col1" >size_fraction_final</th>
      <th id="T_8055a_level0_col2" class="col_heading level0 col2" >configured_today</th>
      <th id="T_8055a_level0_col3" class="col_heading level0 col3" >validated_cap</th>
      <th id="T_8055a_level0_col4" class="col_heading level0 col4" >change_vs_today</th>
      <th id="T_8055a_level0_col5" class="col_heading level0 col5" >notional_USD</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_8055a_level0_row0" class="row_heading level0 row0" >v1_axi_usdjpy</th>
      <td id="T_8055a_row0_col0" class="data row0 col0" >45.8%</td>
      <td id="T_8055a_row0_col1" class="data row0 col1" >1.821x</td>
      <td id="T_8055a_row0_col2" class="data row0 col2" >2.50x</td>
      <td id="T_8055a_row0_col3" class="data row0 col3" >4.37x</td>
      <td id="T_8055a_row0_col4" class="data row0 col4" >-27%</td>
      <td id="T_8055a_row0_col5" class="data row0 col5" >18,206</td>
    </tr>
    <tr>
      <th id="T_8055a_level0_row1" class="row_heading level0 row1" >v1_btcjpy</th>
      <td id="T_8055a_row1_col0" class="data row1 col0" >54.2%</td>
      <td id="T_8055a_row1_col1" class="data row1 col1" >0.230x</td>
      <td id="T_8055a_row1_col2" class="data row1 col2" >0.20x</td>
      <td id="T_8055a_row1_col3" class="data row1 col3" >0.30x</td>
      <td id="T_8055a_row1_col4" class="data row1 col4" >+15%</td>
      <td id="T_8055a_row1_col5" class="data row1 col5" >2,302</td>
    </tr>
  </tbody>
</table>



    L (hard limit only, MC) = 0.61 | binding caps: none
    
    Final portfolio vs current configuration (common window + intrabar Monte Carlo):



<style type="text/css">
</style>
<table id="T_da2ab">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_da2ab_level0_col0" class="col_heading level0 col0" >ann_ret</th>
      <th id="T_da2ab_level0_col1" class="col_heading level0 col1" >vol</th>
      <th id="T_da2ab_level0_col2" class="col_heading level0 col2" >sharpe</th>
      <th id="T_da2ab_level0_col3" class="col_heading level0 col3" >cagr</th>
      <th id="T_da2ab_level0_col4" class="col_heading level0 col4" >maxdd</th>
      <th id="T_da2ab_level0_col5" class="col_heading level0 col5" >p_breach</th>
      <th id="T_da2ab_level0_col6" class="col_heading level0 col6" >dd_p50</th>
      <th id="T_da2ab_level0_col7" class="col_heading level0 col7" >dd_p5</th>
      <th id="T_da2ab_level0_col8" class="col_heading level0 col8" >ret_p5</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_da2ab_level0_row0" class="row_heading level0 row0" >final</th>
      <td id="T_da2ab_row0_col0" class="data row0 col0" >7.8%</td>
      <td id="T_da2ab_row0_col1" class="data row0 col1" >4.3%</td>
      <td id="T_da2ab_row0_col2" class="data row0 col2" >1.81</td>
      <td id="T_da2ab_row0_col3" class="data row0 col3" >8.1%</td>
      <td id="T_da2ab_row0_col4" class="data row0 col4" >-3.46%</td>
      <td id="T_da2ab_row0_col5" class="data row0 col5" >5.0%</td>
      <td id="T_da2ab_row0_col6" class="data row0 col6" >-4.57%</td>
      <td id="T_da2ab_row0_col7" class="data row0 col7" >-8.00%</td>
      <td id="T_da2ab_row0_col8" class="data row0 col8" >11.3%</td>
    </tr>
    <tr>
      <th id="T_da2ab_level0_row1" class="row_heading level0 row1" >today (configured)</th>
      <td id="T_da2ab_row1_col0" class="data row1 col0" >8.1%</td>
      <td id="T_da2ab_row1_col1" class="data row1 col1" >4.8%</td>
      <td id="T_da2ab_row1_col2" class="data row1 col2" >1.68</td>
      <td id="T_da2ab_row1_col3" class="data row1 col3" >8.3%</td>
      <td id="T_da2ab_row1_col4" class="data row1 col4" >-4.32%</td>
      <td id="T_da2ab_row1_col5" class="data row1 col5" >14.8%</td>
      <td id="T_da2ab_row1_col6" class="data row1 col6" >-5.54%</td>
      <td id="T_da2ab_row1_col7" class="data row1 col7" >-10.02%</td>
      <td id="T_da2ab_row1_col8" class="data row1 col8" >10.2%</td>
    </tr>
  </tbody>
</table>



       [PASS] P(touching -8%) <= 5% at final sizes  ->  5.0%
       [PASS] historical close DD x intrabar factor inside the hard limit  ->  4.32% vs 8%
       [PASS] p5 of 3-year return > 0  ->  11.3%
       [PASS] no edge above its validated size  ->  clipped: none



    
![png](Portfolio_Development_files/Portfolio_Development_22_4.png)
    


## 9. COMPOUNDING EFFECT (Guide §8)
`compound ≈ mean − variance/2`. The fair comparison is **at equal risk**: each edge alone scaled to the portfolio's vol vs the portfolio. The gap is `(Sharpe_portfolio − Sharpe_edge) · σ_portfolio`: what diversifying earns, not what betting harder earns.


```
sp = pf["vol"]; rows = {"PORTFOLIO": dict(arith_mean=pf["ann_ret"], vol=sp, half_var=sp ** 2 / 2, compound_approx=pf["ann_ret"] - sp ** 2 / 2, sharpe=pf["sharpe"])}
for k in keys:
    p = perf(U[k] * E_FINAL[k]); m = p["ann_ret"] * sp / p["vol"]
    rows[f"{k} alone, same vol"] = dict(arith_mean=m, vol=sp, half_var=sp ** 2 / 2, compound_approx=m - sp ** 2 / 2, sharpe=p["sharpe"])
display(pd.DataFrame(rows).T.style.format({"arith_mean": "{:.2%}", "vol": "{:.2%}", "half_var": "{:.2%}", "compound_approx": "{:.2%}", "sharpe": "{:.2f}"}))
sr = [perf(U[k] * E_FINAL[k])["sharpe"] for k in keys]
check("9. Compounding", "portfolio Sharpe >= mean Sharpe of its edges (diversification adds)", pf["sharpe"] >= np.mean(sr) - 1e-9, f"{pf['sharpe']:.2f} vs {np.mean(sr):.2f} (best edge {max(sr):.2f})")
```


<style type="text/css">
</style>
<table id="T_30609">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_30609_level0_col0" class="col_heading level0 col0" >arith_mean</th>
      <th id="T_30609_level0_col1" class="col_heading level0 col1" >vol</th>
      <th id="T_30609_level0_col2" class="col_heading level0 col2" >half_var</th>
      <th id="T_30609_level0_col3" class="col_heading level0 col3" >compound_approx</th>
      <th id="T_30609_level0_col4" class="col_heading level0 col4" >sharpe</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_30609_level0_row0" class="row_heading level0 row0" >PORTFOLIO</th>
      <td id="T_30609_row0_col0" class="data row0 col0" >7.85%</td>
      <td id="T_30609_row0_col1" class="data row0 col1" >4.34%</td>
      <td id="T_30609_row0_col2" class="data row0 col2" >0.09%</td>
      <td id="T_30609_row0_col3" class="data row0 col3" >7.75%</td>
      <td id="T_30609_row0_col4" class="data row0 col4" >1.81</td>
    </tr>
    <tr>
      <th id="T_30609_level0_row1" class="row_heading level0 row1" >v1_axi_usdjpy alone, same vol</th>
      <td id="T_30609_row1_col0" class="data row1 col0" >3.92%</td>
      <td id="T_30609_row1_col1" class="data row1 col1" >4.34%</td>
      <td id="T_30609_row1_col2" class="data row1 col2" >0.09%</td>
      <td id="T_30609_row1_col3" class="data row1 col3" >3.83%</td>
      <td id="T_30609_row1_col4" class="data row1 col4" >0.90</td>
    </tr>
    <tr>
      <th id="T_30609_level0_row2" class="row_heading level0 row2" >v1_btcjpy alone, same vol</th>
      <td id="T_30609_row2_col0" class="data row2 col0" >7.02%</td>
      <td id="T_30609_row2_col1" class="data row2 col1" >4.34%</td>
      <td id="T_30609_row2_col2" class="data row2 col2" >0.09%</td>
      <td id="T_30609_row2_col3" class="data row2 col3" >6.93%</td>
      <td id="T_30609_row2_col4" class="data row2 col4" >1.62</td>
    </tr>
  </tbody>
</table>



       [PASS] portfolio Sharpe >= mean Sharpe of its edges (diversification adds)  ->  1.81 vs 1.26 (best edge 1.62)





    'PASS'



## 10. STRESS (Guide §2.3: correlation jumps to +1 when you need it low)
Diversification cuts normal risk, **not tail risk**. (1) every edge has its worst day on the same day, (2) twice that, (3) one edge dies (edge decay), same sizes.


```
l1 = float((E_FINAL * U.min()).sum())
display(pd.DataFrame([dict(scenario="Worst day of every edge, same day", loss=l1, intrabar=l1 * INTRABAR_FACTOR),
                      dict(scenario="2 x worst day of every edge, same day", loss=2 * l1, intrabar=2 * l1 * INTRABAR_FACTOR)]).style.format({"loss": "{:.2%}", "intrabar": "{:.2%}"}))
check("10. Stress", "simultaneous worst day (intrabar) inside the hard limit", abs(l1) * INTRABAR_FACTOR < HARD_LIMIT, f"{l1 * INTRABAR_FACTOR:.2%} vs -{HARD_LIMIT:.0%}")
rows = {}
for d in keys:
    keep = [k for k in keys if k != d]; p = perf((U[keep] * E_FINAL[keep]).sum(axis=1))
    rows[f"without {d}"] = dict(sharpe=p["sharpe"], cagr=p["cagr"], maxdd=p["maxdd"], return_it_contributed=1 - p["ann_ret"] / pf["ann_ret"])
rows["full portfolio"] = dict(sharpe=pf["sharpe"], cagr=pf["cagr"], maxdd=pf["maxdd"], return_it_contributed=np.nan)
display(pd.DataFrame(rows).T.style.format({"sharpe": "{:.2f}", "cagr": "{:.1%}", "maxdd": "{:.2%}", "return_it_contributed": "{:.0%}"}))
print("'return_it_contributed' = share of mean portfolio return lost when that edge is removed; if one edge carries almost everything, the portfolio is one bet.")
```


<style type="text/css">
</style>
<table id="T_13b81">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_13b81_level0_col0" class="col_heading level0 col0" >scenario</th>
      <th id="T_13b81_level0_col1" class="col_heading level0 col1" >loss</th>
      <th id="T_13b81_level0_col2" class="col_heading level0 col2" >intrabar</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_13b81_level0_row0" class="row_heading level0 row0" >0</th>
      <td id="T_13b81_row0_col0" class="data row0 col0" >Worst day of every edge, same day</td>
      <td id="T_13b81_row0_col1" class="data row0 col1" >-2.64%</td>
      <td id="T_13b81_row0_col2" class="data row0 col2" >-3.30%</td>
    </tr>
    <tr>
      <th id="T_13b81_level0_row1" class="row_heading level0 row1" >1</th>
      <td id="T_13b81_row1_col0" class="data row1 col0" >2 x worst day of every edge, same day</td>
      <td id="T_13b81_row1_col1" class="data row1 col1" >-5.28%</td>
      <td id="T_13b81_row1_col2" class="data row1 col2" >-6.60%</td>
    </tr>
  </tbody>
</table>



       [PASS] simultaneous worst day (intrabar) inside the hard limit  ->  -3.30% vs -8%



<style type="text/css">
</style>
<table id="T_7a0c2">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_7a0c2_level0_col0" class="col_heading level0 col0" >sharpe</th>
      <th id="T_7a0c2_level0_col1" class="col_heading level0 col1" >cagr</th>
      <th id="T_7a0c2_level0_col2" class="col_heading level0 col2" >maxdd</th>
      <th id="T_7a0c2_level0_col3" class="col_heading level0 col3" >return_it_contributed</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_7a0c2_level0_row0" class="row_heading level0 row0" >without v1_axi_usdjpy</th>
      <td id="T_7a0c2_row0_col0" class="data row0 col0" >1.62</td>
      <td id="T_7a0c2_row0_col1" class="data row0 col1" >5.4%</td>
      <td id="T_7a0c2_row0_col2" class="data row0 col2" >-2.52%</td>
      <td id="T_7a0c2_row0_col3" class="data row0 col3" >32%</td>
    </tr>
    <tr>
      <th id="T_7a0c2_level0_row1" class="row_heading level0 row1" >without v1_btcjpy</th>
      <td id="T_7a0c2_row1_col0" class="data row1 col0" >0.90</td>
      <td id="T_7a0c2_row1_col1" class="data row1 col1" >2.5%</td>
      <td id="T_7a0c2_row1_col2" class="data row1 col2" >-3.09%</td>
      <td id="T_7a0c2_row1_col3" class="data row1 col3" >68%</td>
    </tr>
    <tr>
      <th id="T_7a0c2_level0_row2" class="row_heading level0 row2" >full portfolio</th>
      <td id="T_7a0c2_row2_col0" class="data row2 col0" >1.81</td>
      <td id="T_7a0c2_row2_col1" class="data row2 col1" >8.1%</td>
      <td id="T_7a0c2_row2_col2" class="data row2 col2" >-3.46%</td>
      <td id="T_7a0c2_row2_col3" class="data row2 col3" >nan%</td>
    </tr>
  </tbody>
</table>



    'return_it_contributed' = share of mean portfolio return lost when that edge is removed; if one edge carries almost everything, the portfolio is one bet.


## 11. WALK-FORWARD OF THE WEIGHTS
For each year `Y`, `SCALE` and weights are estimated on data **before** `Y`, applied to `Y`, and the OOS results are chained. With few years it is **descriptive**.


```
def wf_w(Utr, n):
    s = TARGET_VOL / (Utr.std() * np.sqrt(PPY)); Vt = Utr * s
    return SCHEMES[n](Vt.mean().values * PPY, shrink_cov(Vt.cov().values * PPY)), s
oos = {n: [] for n in ("erc", "max_sharpe_shrunk", "as_configured")}; wp = []
for y in sorted(set(U.index.year)):
    tr, te = U[U.index < f"{y}-01-01"], U[U.index.year == y]
    if len(tr) < MIN_TRAIN_YEARS * PPY or len(te) < 30: continue
    for n in ("erc", "max_sharpe_shrunk"):
        w, s = wf_w(tr, n); oos[n].append(pd.Series(te.values @ (w * s.values), index=te.index))
        if n == "erc": wp.append(dict(year=y, **{k: w[i] for i, k in enumerate(keys)}, train_days=len(tr)))
    oos["as_configured"].append(te @ pd.Series(cfg_exp, index=keys))
if not wp: print("Not enough prior history for any fold."); check("11. Walk-forward", "walk-forward weights evaluable", None, "insufficient history")
else:
    print(f"{len(wp)} yearly OOS fold(s) | ERC weights by year:"); display(pd.DataFrame(wp).set_index("year").style.format({k: "{:.0%}" for k in keys}))
    res = {n: perf(pd.concat(v)) for n, v in oos.items()}
    display(pd.DataFrame(res).T[["years", "ann_ret", "vol", "sharpe", "maxdd"]].style.format(F))
    print("Vols differ across schemes (as_configured is not normalised): compare Sharpe, not return.")
    check("11. Walk-forward", "OOS Sharpe of ERC (weights without looking ahead) > 0", res["erc"]["sharpe"] > 0, f"{res['erc']['sharpe']:.2f} over {len(wp)} fold(s)")
    print(f"Informative: OOS Sharpe ERC {res['erc']['sharpe']:.2f} | as_configured {res['as_configured']['sharpe']:.2f} | max_sharpe_shrunk {res['max_sharpe_shrunk']['sharpe']:.2f} (does not decide anything on its own).")
```

    2 yearly OOS fold(s) | ERC weights by year:



<style type="text/css">
</style>
<table id="T_5640b">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_5640b_level0_col0" class="col_heading level0 col0" >v1_axi_usdjpy</th>
      <th id="T_5640b_level0_col1" class="col_heading level0 col1" >v1_btcjpy</th>
      <th id="T_5640b_level0_col2" class="col_heading level0 col2" >train_days</th>
    </tr>
    <tr>
      <th class="index_name level0" >year</th>
      <th class="blank col0" >&nbsp;</th>
      <th class="blank col1" >&nbsp;</th>
      <th class="blank col2" >&nbsp;</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_5640b_level0_row0" class="row_heading level0 row0" >2025</th>
      <td id="T_5640b_row0_col0" class="data row0 col0" >50%</td>
      <td id="T_5640b_row0_col1" class="data row0 col1" >50%</td>
      <td id="T_5640b_row0_col2" class="data row0 col2" >716</td>
    </tr>
    <tr>
      <th id="T_5640b_level0_row1" class="row_heading level0 row1" >2026</th>
      <td id="T_5640b_row1_col0" class="data row1 col0" >50%</td>
      <td id="T_5640b_row1_col1" class="data row1 col1" >50%</td>
      <td id="T_5640b_row1_col2" class="data row1 col2" >1081</td>
    </tr>
  </tbody>
</table>




<style type="text/css">
</style>
<table id="T_5ba2f">
  <thead>
    <tr>
      <th class="blank level0" >&nbsp;</th>
      <th id="T_5ba2f_level0_col0" class="col_heading level0 col0" >years</th>
      <th id="T_5ba2f_level0_col1" class="col_heading level0 col1" >ann_ret</th>
      <th id="T_5ba2f_level0_col2" class="col_heading level0 col2" >vol</th>
      <th id="T_5ba2f_level0_col3" class="col_heading level0 col3" >sharpe</th>
      <th id="T_5ba2f_level0_col4" class="col_heading level0 col4" >maxdd</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th id="T_5ba2f_level0_row0" class="row_heading level0 row0" >erc</th>
      <td id="T_5ba2f_row0_col0" class="data row0 col0" >1.65</td>
      <td id="T_5ba2f_row0_col1" class="data row0 col1" >5.8%</td>
      <td id="T_5ba2f_row0_col2" class="data row0 col2" >4.6%</td>
      <td id="T_5ba2f_row0_col3" class="data row0 col3" >1.27</td>
      <td id="T_5ba2f_row0_col4" class="data row0 col4" >-3.05%</td>
    </tr>
    <tr>
      <th id="T_5ba2f_level0_row1" class="row_heading level0 row1" >max_sharpe_shrunk</th>
      <td id="T_5ba2f_row1_col0" class="data row1 col0" >1.65</td>
      <td id="T_5ba2f_row1_col1" class="data row1 col1" >5.9%</td>
      <td id="T_5ba2f_row1_col2" class="data row1 col2" >4.2%</td>
      <td id="T_5ba2f_row1_col3" class="data row1 col3" >1.41</td>
      <td id="T_5ba2f_row1_col4" class="data row1 col4" >-2.21%</td>
    </tr>
    <tr>
      <th id="T_5ba2f_level0_row2" class="row_heading level0 row2" >as_configured</th>
      <td id="T_5ba2f_row2_col0" class="data row2 col0" >1.65</td>
      <td id="T_5ba2f_row2_col1" class="data row2 col1" >4.2%</td>
      <td id="T_5ba2f_row2_col2" class="data row2 col2" >3.6%</td>
      <td id="T_5ba2f_row2_col3" class="data row2 col3" >1.14</td>
      <td id="T_5ba2f_row2_col4" class="data row2 col4" >-2.68%</td>
    </tr>
  </tbody>
</table>



    Vols differ across schemes (as_configured is not normalised): compare Sharpe, not return.
       [PASS] OOS Sharpe of ERC (weights without looking ahead) > 0  ->  1.27 over 2 fold(s)
    Informative: OOS Sharpe ERC 1.27 | as_configured 1.14 | max_sharpe_shrunk 1.41 (does not decide anything on its own).


## 12. VERDICT AND SAVE


```
print("=" * 78 + "\nPASS / FAIL SUMMARY" + "" + "\n" + "=" * 78)
for sec in dict.fromkeys(c["section"] for c in CHECKS):
    print(f"\n{sec}")
    for c in [c for c in CHECKS if c["section"] == sec]: print(f"  [{c['status']}] {c['name']}" + (f"  ->  {c['detail']}" if c["detail"] else ""))
fails = [c for c in CHECKS if c["status"] == "FAIL"]
print("\n" + "=" * 78 + "\nSIZE PLAN (paste into risk.size_fraction of each variant, then re-run that edge's notebook 04 for lots):")
for k in keys: print(f"  {k:<10} {SL[k]['name']:<28} size_fraction = {E_FINAL[k]:.3f} (today {SL[k]['frac']:.2f}) | risk weight {W_FINAL[k]:.0%} | ~{E_FINAL[k] * CAPITAL:,.0f} USD notional")
print("OVERALL: " + ("PASS" if not fails else f"{len(fails)} FAIL -> document each before trading (a margin or exception is declared, not applied silently)") + "\n" + "=" * 78)
P = dict(portfolio_id=PORTFOLIO_ID, hypothesis=HYPOTHESIS, window=[str(START.date()), str(END.date())], capital=CAPITAL, hard_limit=HARD_LIMIT,
         edges={k: dict(id=SL[k]["name"], source=SL[k]["source"], risk_weight=float(W_FINAL[k]), size_fraction=float(E_FINAL[k]), configured=SL[k]["frac"]) for k in keys},
         L_hard_limit=float(L_MC), binding_caps=bind, tilt_identified=bool(IDENT), blend=float(BLEND), schemes_compared=len(SCHEMES),
         params=dict(TARGET_VOL=TARGET_VOL, PRIOR_RHO=PRIOR_RHO, SHRINK_RHO=SHRINK_RHO, MEAN_SHRINK=MEAN_SHRINK, INTRABAR_FACTOR=INTRABAR_FACTOR,
                     BLOCK_DAYS=BLOCK_DAYS, MC_YEARS=MC_YEARS, MC_BREACH_MAX=MC_BREACH_MAX, N_BOOT=N_BOOT, N_MC=N_MC, SEED=SEED), checks=CHECKS)
P["params_hash"] = hashlib.sha1(json.dumps(P["params"], sort_keys=True).encode()).hexdigest()[:8]
out = OUT_DIR / "portfolio.json"; out.write_text(json.dumps(P, indent=2, default=str)); print("Saved:", out)
```

    ==============================================================================
    PASS / FAIL SUMMARY
    ==============================================================================
    
    2. Data
      [PASS] common window >= 2 years  ->  3.61
    
    4. Correlation
      [PASS] v1_axi_usdjpy/v1_btcjpy: weekly corr estimable (>= 30 co-active weeks)  ->  52 co-active weeks
      [PASS] v1_axi_usdjpy/v1_btcjpy: weekly corr < 0.5  ->  +0.07 (CI90 -0.06..+0.21)
      [PASS] structural reason declared (WHY_UNCORRELATED)  ->  see EXPERIMENT
      [SKIP] shared JPY factor measured  ->  set JPY_PROXY_CSV
    
    7. Weights
      [PASS] final weights sum to 1 and are >= 0  ->  {'v1_axi_usdjpy': 0.458, 'v1_btcjpy': 0.542}
    
    8. Risk
      [PASS] P(touching -8%) <= 5% at final sizes  ->  5.0%
      [PASS] historical close DD x intrabar factor inside the hard limit  ->  4.32% vs 8%
      [PASS] p5 of 3-year return > 0  ->  11.3%
      [PASS] no edge above its validated size  ->  clipped: none
    
    9. Compounding
      [PASS] portfolio Sharpe >= mean Sharpe of its edges (diversification adds)  ->  1.81 vs 1.26 (best edge 1.62)
    
    10. Stress
      [PASS] simultaneous worst day (intrabar) inside the hard limit  ->  -3.30% vs -8%
    
    11. Walk-forward
      [PASS] OOS Sharpe of ERC (weights without looking ahead) > 0  ->  1.27 over 2 fold(s)
    
    ==============================================================================
    SIZE PLAN (paste into risk.size_fraction of each variant, then re-run that edge's notebook 04 for lots):
      v1_axi_usdjpy GOTOBI.usdjpy.cfd.v1         size_fraction = 1.821 (today 2.50) | risk weight 46% | ~18,206 USD notional
      v1_btcjpy  MONDAY.btcjpy.cfd.v1         size_fraction = 0.230 (today 0.20) | risk weight 54% | ~2,302 USD notional
    OVERALL: PASS
    ==============================================================================
    Saved: /Users/luyandy/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/03_portfolio_development/runs/portfolio_Axi_v1_Andres/portfolio.json


## ADDING A NEW TYPE OF EDGE

A new variant of an existing edge (Gotobi, Monday, RSI2) needs no code: add its name to `EDGES`.
A **new type** of edge needs this, once.

**1. At the end of the edge's notebook 03/04**, where `ret` (daily returns, net of costs), `FRAC`, `RUN_DIR`, `EDGE_DIR` and `VARIANT` exist:

```python
import json, hashlib
from pathlib import Path
import pandas as pd

yaml_path = Path(EDGE_DIR) / "variants" / f"{VARIANT}.yaml"
csv = Path(RUN_DIR) / "daily_returns.csv"
pd.Series(ret, name="ret").to_csv(csv, index_label="date")
Path(str(csv) + ".meta.json").write_text(json.dumps(dict(
    frac=float(FRAC),                                              # size at which `ret` was computed
    yaml_sha=hashlib.sha1(yaml_path.read_bytes()).hexdigest()[:10])))
```

**2. `FRAC`** is the unit of the final `size_fraction`: the edge's own `size_fraction` if it sizes by capital fraction, or `1.0` (official sizing) if it sizes by risk, so the output is a multiple of it.

**3. Here:** add the variant to `EDGES`, `MAX_SIZE` if it has a validated cap, update `WHY_UNCORRELATED`, Run All.

Re-export after any YAML change (the notebook stops if the hash differs).
