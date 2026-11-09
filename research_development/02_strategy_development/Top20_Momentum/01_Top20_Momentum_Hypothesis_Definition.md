# 1. TOP 20 MOMENTUM (US LARGE CAPS) - HYPOTHESIS DEFINITION & BASELINE BACKTEST
Long-only tactical rotation (TIS Strategy #4, **Top 20** version) on a point-in-time S&P 500 universe, daily bars, real costs (slippage per side) and next-open execution.

### 1.1 CORE HYPOTHESIS
Stocks with the strongest 3-month return keep outperforming the eligible universe over the next month, and a trend filter (SPY > SMA200, stock > SMA200) cuts the drawdowns of bear markets.
### 1.2 FROZEN RULES (TIS, not fitted)
1. First Wednesday of the month (signal at the close, trade at the next open). 2. Eligible: S&P 500 member, avg volume >= 2M sh, price > SMA200 and SMA50.
3. Rank by 63-day return, buy the Top N (N = 20) equal weight; held names that stay in the Top N are not touched.
4. SPY < SMA200 -> sell everything, cash until the next monthly rebalance. 5. Weekly check: stock < own SMA200 -> sell it, cash until the next rebalance.
### 1.3 HOW IT IS JUDGED
Every PASS / FAIL is registered; section 6 groups them into a GO / STOP gate. Statistics are at **portfolio level** (monthly returns): trade-level t-stats are inflated because the 20 positions are correlated.
Top 20 (instead of the Top 10 in the TIS PDF) is a variant TIS documents itself (CAGR 13-15%, Sharpe ~0.70, MaxDD ~-28%); it is declared a priori, not chosen from our results.


```python
%pip install lxml yfinance requests
from t20_tools import *
from scipy import stats
VARIANT = "t20_sp500_v1"
S = setup(VARIANT)
eng, P, rules, panel, TH, reg = S.eng, S.P, S.rules, S.panel, S.TH, S.reg
check, OOS, CAP, LIMIT, N = reg.check, S.OOS, S.CAP, S.LIMIT, S.P["top_n"]
```

    Requirement already satisfied: lxml in /opt/homebrew/lib/python3.11/site-packages (6.1.3)
    Requirement already satisfied: yfinance in /opt/homebrew/lib/python3.11/site-packages (1.3.0)
    Requirement already satisfied: requests in /opt/homebrew/lib/python3.11/site-packages (2.33.1)
    Requirement already satisfied: pandas>=1.3.0 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (3.0.2)
    Requirement already satisfied: numpy>=1.16.5 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (2.4.4)
    Requirement already satisfied: multitasking>=0.0.7 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (0.0.13)
    Requirement already satisfied: platformdirs>=2.0.0 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (4.11.3)
    Requirement already satisfied: pytz>=2022.5 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (2026.2)
    Requirement already satisfied: frozendict>=2.3.4 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (2.4.7)
    Requirement already satisfied: peewee>=3.16.2 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (4.0.5)
    Requirement already satisfied: beautifulsoup4>=4.11.1 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (4.15.0)
    Requirement already satisfied: curl_cffi>=0.15 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (0.15.0)
    Requirement already satisfied: protobuf>=3.19.0 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (7.34.1)
    Requirement already satisfied: websockets>=13.0 in /opt/homebrew/lib/python3.11/site-packages (from yfinance) (15.0.1)
    Requirement already satisfied: charset_normalizer<4,>=2 in /opt/homebrew/lib/python3.11/site-packages (from requests) (3.4.7)
    Requirement already satisfied: idna<4,>=2.5 in /opt/homebrew/lib/python3.11/site-packages (from requests) (3.18)
    Requirement already satisfied: urllib3<3,>=1.26 in /opt/homebrew/lib/python3.11/site-packages (from requests) (2.8.0)
    Requirement already satisfied: certifi>=2023.5.7 in /opt/homebrew/lib/python3.11/site-packages (from requests) (2026.10.19)
    Requirement already satisfied: soupsieve>=1.6.1 in /opt/homebrew/lib/python3.11/site-packages (from beautifulsoup4>=4.11.1->yfinance) (2.9.2)
    Requirement already satisfied: typing-extensions>=4.0.0 in /opt/homebrew/lib/python3.11/site-packages (from beautifulsoup4>=4.11.1->yfinance) (4.16.0)
    Requirement already satisfied: cffi>=2.0.0 in /opt/homebrew/lib/python3.11/site-packages (from curl_cffi>=0.15->yfinance) (2.0.0)
    Requirement already satisfied: rich in /opt/homebrew/lib/python3.11/site-packages (from curl_cffi>=0.15->yfinance) (14.3.4)
    Requirement already satisfied: pycparser in /opt/homebrew/lib/python3.11/site-packages (from cffi>=2.0.0->curl_cffi>=0.15->yfinance) (3.0)
    Requirement already satisfied: python-dateutil>=2.8.2 in /opt/homebrew/lib/python3.11/site-packages (from pandas>=1.3.0->yfinance) (2.9.0.post0)
    Requirement already satisfied: six>=1.5 in /opt/homebrew/lib/python3.11/site-packages (from python-dateutil>=2.8.2->pandas>=1.3.0->yfinance) (1.17.0)
    Requirement already satisfied: markdown-it-py>=2.2.0 in /opt/homebrew/lib/python3.11/site-packages (from rich->curl_cffi>=0.15->yfinance) (4.0.0)
    Requirement already satisfied: pygments<3.0.0,>=2.13.0 in /opt/homebrew/lib/python3.11/site-packages (from rich->curl_cffi>=0.15->yfinance) (2.21.0)
    Requirement already satisfied: mdurl~=0.1 in /opt/homebrew/lib/python3.11/site-packages (from markdown-it-py>=2.2.0->rich->curl_cffi>=0.15->yfinance) (0.1.2)
    
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m A new release of pip is available: [0m[31;49m26.2.1[0m[39;49m -> [0m[32;49m26.3[0m
    [1m[[0m[34;49mnotice[0m[1;39;49m][0m[39;49m To update, run: [0m[32;49m/opt/homebrew/opt/python@3.11/bin/python3.11 -m pip install --upgrade pip[0m
    Note: you may need to restart the kernel to use updated packages.
    Data missing or refresh requested ({'ok': False, 'n_files': 0, 'has_benchmark': False, 'has_membership': False, 'last_bar': None, 'age_days': None, 'max_age_days': 45}). Downloading from free sources (one-off, can take 10-20 min)...



    ---------------------------------------------------------------------------

    ValueError                                Traceback (most recent call last)

    Cell In[1], line 5
          3 from scipy import stats
          4 VARIANT = "t20_sp500_v1"
    ----> 5 S = setup(VARIANT)
          6 eng, P, rules, panel, TH, reg = S.eng, S.P, S.rules, S.panel, S.TH, S.reg
          7 check, OOS, CAP, LIMIT, N = reg.check, S.OOS, S.CAP, S.LIMIT, S.P["top_n"]


    File ~/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Top20_Momentum/t20_tools.py:47, in setup(variant, nb_file, panel)
         43 rules = dict(lookback_days=P["lookback_days"], top_n=P["top_n"], slip_bps_per_side=P["slip_bps_per_side"], exec_mode=P["exec_mode"],
         44              spy_ma=P["spy_ma"], stock_ma=P["stock_ma"], fast_ma=P["fast_ma"], min_adv_shares=P["min_adv_shares"],
         45              rebalance=P["rebalance"], weekly_checks=P["weekly_checks"], cash_yield=P["cash_yield_annual"])
         46 if panel:
    ---> 47     import t20_data; importlib.reload(t20_data); t20_data.ensure_data(cfg, eng._res)      # checks the data, downloads it only if missing
         48 pan = eng.load_panel() if panel else None
         49 plt.rcParams.update({"figure.facecolor": BG, "text.color": TXT, "axes.labelcolor": SUB, "axes.titlecolor": TXT, "savefig.facecolor": BG})


    File ~/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Top20_Momentum/t20_data.py:99, in ensure_data(cfg, resolve, refresh)
         97 print(f"Data missing or refresh requested ({st}). Downloading from free sources (one-off, can take 10-20 min)...")
         98 if uni == "sp500_wikipedia":
    ---> 99     mem = fetch_sp500_wikipedia(start); mcsv.parent.mkdir(parents=True, exist_ok=True); mem.to_csv(mcsv, index=False); tickers = mem["ticker"].unique().tolist()
        100     print(f"Membership rebuilt: {len(mem)} intervals, {len(tickers)} tickers ever in the index since {start}")
        101 else:


    File ~/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Top20_Momentum/t20_data.py:67, in fetch_sp500_wikipedia(data_start)
         65 import requests
         66 r = requests.get(WIKI, headers=HDR, timeout=30); r.raise_for_status()
    ---> 67 return parse_sp500_tables(pd.read_html(io.StringIO(r.text)), data_start)


    File ~/Documents/Alphaca Capital/Alphaca-Capital-Research/research_development/02_strategy_development/Top20_Momentum/t20_data.py:54, in parse_sp500_tables(tables, data_start)
         52         t = t.copy(); t.columns = cols; chg = t
         53 if cur is None or chg is None:
    ---> 54     raise ValueError(f"Could not find the Wikipedia tables (current={cur is not None}, changes={chg is not None}). Columns seen: {[_flat(t.columns)[:6] for t in tables[:6]]}")
         55 low = [c.lower() for c in chg.columns]
         56 def pick(word):


    ValueError: Could not find the Wikipedia tables (current=True, changes=False). Columns seen: [['Symbol', 'Security', 'GICS Sector', 'GICS Sub-Industry', 'Headquarters Location', 'Date added'], ['vteS&P 500 companies', 'vteS&P 500 companies.1']]


## 2. BASELINE RUN (FROZEN RULES) AND IN-SAMPLE / OUT-OF-SAMPLE
The strategy is simulated ONCE on the full history (indicators keep their warm-up); IS / OOS only slice the result by date.


```python
full = eng.run_backtest(panel, **rules)
ret, trades, npos = full["ret"], full["trades"], full["npos"]
bh = eng.benchmark_ret(panel, ret)
print(f"{ret.index[0]:%Y-%m-%d} -> {ret.index[-1]:%Y-%m-%d} | closed trades {int((trades.reason != 'open').sum())} | avg positions {npos.mean():.1f} | days in cash {100 * (npos == 0).mean():.0f}%")

def block(mask):
    r = ret[mask]; m, b = eng.perf(r), eng.perf(bh[mask]); mon = eng.monthly(r)
    t = trades[(trades.reason != "open") & trades.entry_time.between(r.index[0], r.index[-1])]; ts = eng.trade_stats(t)
    return dict(CAGR=m["cagr"], Sharpe=m["sharpe"], MaxDD=m["max_dd"], Vol=m["vol"], SPY_CAGR=b["cagr"], SPY_Sharpe=b["sharpe"], SPY_MaxDD=b["max_dd"],
                Trades=ts["n"], PF=ts["pf"], Win=ts["win_pct"], Payoff=ts["payoff"], t_month=eng.tstat(mon), AvgDays=ts["avg_days"])
idx = ret.index
tab = pd.DataFrame({"IS": block(idx < OOS), "OOS": block(idx >= OOS), "All": block(np.ones(len(idx), bool))}).T
print(tab.round(3).to_string())
```

## 3. EXPLORATORY CHECKS OF THE HYPOTHESIS
### 3.1 DOES PAST 3-MONTH RETURN PREDICT THE NEXT MONTH? (CROSS-SECTION, NO COSTS)
At every rebalance date: forward 21-day return of the Top N vs the average of the whole eligible universe, plus the rank correlation (IC) between momentum and forward return.


```python
reb, _ = eng.calendar_flags(panel.dates, rules["rebalance"])
mom, smaS, smaF = panel.mom(rules["lookback_days"]), panel.sma(rules["stock_ma"]), panel.sma(rules["fast_ma"])
rows = []
for t in np.flatnonzero(reb):
    if t < 260 or t + 21 >= len(panel.dates): continue
    el = panel.member[t] & ~np.isnan(mom[t]) & (panel.adv[t] >= rules["min_adv_shares"]) & (panel.close[t] > smaS[t]) & (panel.close[t] > smaF[t])
    ix = np.flatnonzero(el)
    if len(ix) < 2 * N: continue
    fwd = panel.close_ff[t + 21, ix] / panel.close_ff[t, ix] - 1; top = np.argsort(-mom[t, ix])[:N]
    rows.append(dict(date=panel.dates[t], top=fwd[top].mean(), uni=fwd.mean(), ic=stats.spearmanr(mom[t, ix], fwd)[0], n=len(ix)))
xs = pd.DataFrame(rows).set_index("date"); xs["excess"] = xs["top"] - xs["uni"]
t_ex, t_ic = eng.tstat(xs["excess"]), eng.tstat(xs["ic"])
print(f"{len(xs)} rebalances | mean forward 21d: Top {N} {100 * xs['top'].mean():+.2f}% vs universe {100 * xs['uni'].mean():+.2f}% | excess {100 * xs['excess'].mean():+.2f}% (t {t_ex:.2f}) | IC {xs['ic'].mean():+.3f} (t {t_ic:.2f}) | eligible names {xs['n'].median():.0f}")
check("3.1 Signal", f"Top {N} beats the eligible universe (t of monthly excess >= {TH['T_MIN']:g})", t_ex >= TH["T_MIN"], f"excess {100 * xs['excess'].mean():+.2f}% / month, t {t_ex:.2f}")
check("3.1 Signal", f"Information coefficient > 0 (t >= {TH['T_MIN']:g})", t_ic >= TH["T_MIN"], f"IC {xs['ic'].mean():+.3f}, t {t_ic:.2f}")
f, ax = fig(1, 2, figsize=(14, 4)); ax[0].plot((1 + xs["excess"]).cumprod(), color=GREEN); ax[0].set_title("Cumulative monthly excess of Top N over the universe")
ax[1].hist(xs["ic"], bins=30, color=ORANGE); ax[1].axvline(0, color=TXT); ax[1].set_title("IC distribution"); plt.show()
```

### 3.2 THE STRATEGY VS THE BENCHMARKS (SPY BUY & HOLD, EQUAL-WEIGHT ELIGIBLE UNIVERSE)


```python
uni_m = xs["uni"]                                    # monthly forward return of the equal-weight eligible universe (diagnostic)
b_all, m_all = eng.perf(bh), eng.perf(ret)
print(f"Strategy: CAGR {100 * m_all['cagr']:.1f}% Sharpe {m_all['sharpe']:.2f} MaxDD {100 * m_all['max_dd']:.1f}% | SPY: CAGR {100 * b_all['cagr']:.1f}% Sharpe {b_all['sharpe']:.2f} MaxDD {100 * b_all['max_dd']:.1f}%")
check("3.2 Benchmarks", "Sharpe above SPY buy & hold (full period)", m_all["sharpe"] > b_all["sharpe"], f"{m_all['sharpe']:.2f} vs {b_all['sharpe']:.2f}")
check("3.2 Benchmarks", "Max drawdown shallower than SPY buy & hold", m_all["max_dd"] > b_all["max_dd"], f"{100 * m_all['max_dd']:.1f}% vs {100 * b_all['max_dd']:.1f}%")
f, ax = fig(2, 1, figsize=(14, 7), sharex=True); ax[0].plot((1 + ret).cumprod(), color=GREEN, label="Top 20 momentum"); ax[0].plot((1 + bh).cumprod(), color=SUB, label="SPY"); ax[0].set_yscale("log")
ax[0].axvline(OOS, color=ORANGE, ls="--"); ax[0].legend(facecolor=PANEL, labelcolor=TXT); ax[1].fill_between(idx, 100 * eng.drawdown(ret), color=RED, alpha=.6); ax[1].plot(100 * eng.drawdown(bh), color=SUB); ax[1].set_title("Drawdown %"); plt.show()
```

### 3.3 WHAT EACH FILTER CONTRIBUTES (SAME DATA, SAME COSTS)
Reference variants: the configured rules vs removing one piece at a time.


```python
variants = {"Configured": {}, "No market filter (SPY)": dict(market_filter=False), "No stock SMA200 stop": dict(stock_stop=False),
            "No trend entry filter": dict(stock_trend=False), "Pure Top N (no filters)": dict(market_filter=False, stock_stop=False, stock_trend=False),
            "Same-close execution (TIS manual)": dict(exec_mode="close")}
rv = {k: eng.run_backtest(panel, **{**rules, **v}) for k, v in variants.items()}
vt = pd.DataFrame({k: {**eng.perf(r["ret"]), "PF": eng.trade_stats(r["trades"])["pf"], "trades": eng.trade_stats(r["trades"])["n"]} for k, r in rv.items()}).T[["cagr", "sharpe", "max_dd", "calmar", "PF", "trades"]]
print(vt.round(3).to_string())
check("3.3 Filters", "Configured rules beat pure Top N on Sharpe", vt.loc["Configured", "sharpe"] > vt.loc["Pure Top N (no filters)", "sharpe"], f"{vt.loc['Configured', 'sharpe']:.2f} vs {vt.loc['Pure Top N (no filters)', 'sharpe']:.2f}")
check("3.3 Filters", "Market filter reduces max drawdown", vt.loc["Configured", "max_dd"] > vt.loc["No market filter (SPY)", "max_dd"], f"{100 * vt.loc['Configured', 'max_dd']:.1f}% vs {100 * vt.loc['No market filter (SPY)', 'max_dd']:.1f}%")
check("3.3 Filters", "Next-open execution loses < 0.2 Sharpe vs same-close (look-ahead in the manual TIS rule is small)", vt.loc["Same-close execution (TIS manual)", "sharpe"] - vt.loc["Configured", "sharpe"] < 0.2,
      f"same-close {vt.loc['Same-close execution (TIS manual)', 'sharpe']:.2f} vs next-open {vt.loc['Configured', 'sharpe']:.2f}")
```

### 3.4 CONCENTRATION BY CALENDAR YEAR


```python
an = eng.annual(ret, LIMIT); an["spy"] = [(1 + bh[bh.index.year == y]).prod() - 1 for y in an["year"]]
print(an.round(3).to_string(index=False))
full_y = an[~an["partial"]]; pos = (full_y["ret"] > 0).mean(); best = full_y.loc[full_y["ret"].idxmax(), "year"]
rest = eng.monthly(ret[ret.index.year != best]); t_rest = eng.tstat(rest)
check("3.4 Years", f"Share of profitable calendar years >= {TH['YEARS_POS_MIN']:.0%}", pos >= TH["YEARS_POS_MIN"], f"{pos:.0%} of {len(full_y)} years")
check("3.4 Years", "Monthly t-stat survives without the best year (>= 1.5)", t_rest >= 1.5, f"best year {best}, t without it {t_rest:.2f}")
```

## 4. JUDGING THE BASELINE (IS / OOS)


```python
g = tab
check("4. Baseline", f"Trades, full period >= {TH['N_MIN']}", g.loc["All", "Trades"] >= TH["N_MIN"], f"{int(g.loc['All', 'Trades'])}")
check("4. Baseline", f"Trades, OOS >= {TH['N_OOS_MIN']}", g.loc["OOS", "Trades"] >= TH["N_OOS_MIN"], f"{int(g.loc['OOS', 'Trades'])}")
check("4. Baseline", f"Sharpe, IS >= {TH['SHARPE_MIN']:g}", g.loc["IS", "Sharpe"] >= TH["SHARPE_MIN"], f"{g.loc['IS', 'Sharpe']:.2f}")
check("4. Baseline", f"Sharpe, OOS >= {TH['SHARPE_OOS_MIN']:g}", g.loc["OOS", "Sharpe"] >= TH["SHARPE_OOS_MIN"], f"{g.loc['OOS', 'Sharpe']:.2f}")
check("4. Baseline", f"Profit Factor, IS >= {TH['PF_MIN']:g}", g.loc["IS", "PF"] >= TH["PF_MIN"], f"{g.loc['IS', 'PF']:.2f}")
check("4. Baseline", f"Profit Factor, OOS >= {TH['PF_MIN']:g}", g.loc["OOS", "PF"] >= TH["PF_MIN"], f"{g.loc['OOS', 'PF']:.2f}")
check("4. Baseline", f"t-stat of monthly returns >= {TH['T_MIN']:g} (full)", g.loc["All", "t_month"] >= TH["T_MIN"], f"{g.loc['All', 't_month']:.2f} (IS {g.loc['IS', 't_month']:.2f} / OOS {g.loc['OOS', 't_month']:.2f})")
check("4. Baseline", "OOS Sharpe keeps at least half of the IS Sharpe", g.loc["OOS", "Sharpe"] >= 0.5 * g.loc["IS", "Sharpe"], f"{g.loc['OOS', 'Sharpe']:.2f} vs {g.loc['IS', 'Sharpe']:.2f}")
```

### 4.1 SIZING AND HARD LIMIT
Fully invested (equal weight 1/N). If the account rule is tighter than the strategy's drawdown, the allocated fraction is scaled linearly (rest idle cash).


```python
dd = eng.perf(ret)["max_dd"]; frac = eng.fraction_for_limit(ret, LIMIT)
print(f"Max drawdown fully invested {100 * dd:.1f}% | hard limit -{LIMIT:.0%} | fraction of capital that respects it: {frac:.0%} | position size at capital {CAP:,.0f}: {CAP * frac / N:,.0f} each ({N} names)")
check("4.1 Hard limit", "Full allocation respects the hard limit", dd >= -LIMIT, f"{100 * dd:.1f}% vs -{LIMIT:.0%}")
check("4.1 Hard limit", "Position size >= 250 at the declared capital and the limit-fitted fraction", CAP * frac / N >= 250, f"{CAP * frac / N:,.0f} per position")
check("4.1 Hard limit", "No full calendar year breaches the limit (full allocation)", not an.loc[~an["partial"], "breach"].any(), f"breaches: {an.loc[an['breach'], 'year'].tolist()}")
```

## 5. SANITY CHECKS & VERIFICATION


```python
viol = []
tr = trades[trades.reason != "open"]
ok200 = panel.spy_ok(rules["spy_ma"]); pos_of = {d: i for i, d in enumerate(panel.dates)}
rebs = set(panel.dates[np.flatnonzero(reb)])
ent = pd.DatetimeIndex(tr["entry_time"].unique())
for d in ent:                                                       # entries must be the next session after a rebalance day, with SPY above its SMA200 on the signal day
    i = pos_of[d]
    if panel.dates[i - 1] not in rebs: viol.append(f"entry {d:%Y-%m-%d} is not right after a rebalance day")
    elif not ok200[i - 1]: viol.append(f"entry {d:%Y-%m-%d} with SPY below its SMA200")
check("5. Sanity", "No lookahead: entries follow a rebalance close, market filter ON", not viol, f"{len(viol)} violations in {len(ent)} entry days" + (f" e.g. {viol[0]}" if viol else ""))
check("5. Sanity", f"Never more than {N} positions", int(npos.max()) <= N, f"max {int(npos.max())}")
mem_ok = all(panel.member[pos_of[d] - 1, panel.tickers.index(k)] for k, d in zip(tr["ticker"], tr["entry_time"]))
check("5. Sanity", "Point-in-time universe: every entry was an S&P 500 member on the signal date", mem_ok, f"{len(tr)} trades")
last_valid = panel.close_df.apply(lambda s: s.last_valid_index()); gone = (last_valid < panel.dates[-1] - pd.Timedelta(days=30)).mean()
check("5. Sanity", "Data include delisted names (survivorship): >= 5% of tickers stop trading", gone >= .05, f"{100 * gone:.1f}% of {len(panel.tickers)} tickers")
el_by_year = xs.groupby(xs.index.year)["n"].median()
check("5. Sanity", f"Eligible names >= 2 x Top N in every year", (el_by_year >= 2 * N).all(), f"min median {int(el_by_year.min())}")
print("Exit reasons:", tr["reason"].value_counts().to_dict(), "| avg holding days:", round(tr["days"].mean(), 1))
```

## 6. SUMMARY & GO / STOP GATE


```python
ESSENTIAL = [
    ("5. Sanity", "No lookahead", "Fix the execution model first: every number is invalid until this passes."),
    ("5. Sanity", "Point-in-time universe", "The universe is not point-in-time: results are inflated by survivorship. Fix the membership file."),
    ("5. Sanity", "Data include delisted", "Use a database that includes delisted stocks (Norgate 'Current & Past')."),
    ("3.1 Signal", "Top", "Top N does not beat the eligible universe: the ranking has no cross-sectional edge."),
    ("3.2 Benchmarks", "Sharpe above SPY", "Sharpe does not beat SPY: no reason to run this instead of buy & hold."),
    ("3.3 Filters", "Configured rules beat pure", "The filters add nothing over pure Top N: simplify or reject."),
    ("3.3 Filters", "Market filter reduces", "The SPY filter does not reduce drawdown: the protection leg is not confirmed."),
    ("4. Baseline", "Sharpe, IS", "Baseline does not hold in-sample: do not optimize."),
    ("4. Baseline", "Sharpe, OOS", "Baseline does not hold out-of-sample: the edge is not confirmed."),
    ("4. Baseline", "Profit Factor, IS", "PF below the minimum in-sample."), ("4. Baseline", "Profit Factor, OOS", "PF below the minimum out-of-sample."),
    ("4. Baseline", "t-stat of monthly", "Monthly returns are not statistically significant: could be noise."),
    ("4. Baseline", "Trades, full", "Too few trades."), ("4. Baseline", "Trades, OOS", "Too few OOS trades."),
    ("4.1 Hard limit", "Full allocation", "Drawdown exceeds the account limit: scale the fraction (see 4.1) or do not trade it."),
]
go = gate(reg, ESSENTIAL, headline=f"| Sharpe {m_all['sharpe']:.2f} (SPY {b_all['sharpe']:.2f}) | CAGR {100 * m_all['cagr']:.1f}% | MaxDD {100 * m_all['max_dd']:.1f}%")
print("\nNEXT STEP:", "02_Top20_Momentum_Optimization.ipynb: is (63 d, Top 20) on a broad plateau, in-sample only?" if go else "fix the failed gates, or record the variant as rejected.")
```

## 7. SAVE


```python
d = reg.df()
S.vc.save_json(S.cfg, "01_hypothesis.json", dict(variant=S.cfg["id"], go=bool(go), table=tab.round(4).to_dict("index"), filters=vt.round(4).to_dict("index"),
    fraction_for_limit=frac, checks=d.to_dict("records"), n_pass=int((d.status == "PASS").sum()), n_fail=int((d.status == "FAIL").sum())))
```
