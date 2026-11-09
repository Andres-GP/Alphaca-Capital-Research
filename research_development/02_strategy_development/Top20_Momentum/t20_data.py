"""
t20_data.py - free-data bootstrap for the Top-N momentum edge. Every notebook calls it through t20_tools.setup(): if the data is already there it
only checks it (a few ms); if not, it downloads it once and every later run is offline.
Sources (free): Yahoo Finance via `yfinance` (daily, split+dividend adjusted) and Wikipedia (S&P 500 constituents + change history).
Install once:  pip install yfinance lxml requests
KNOWN LIMITS (they bias the backtest upwards, the notebooks report them):
  - Yahoo has almost no prices for DELISTED stocks -> survivorship bias remains for the names that were removed from the index and no longer trade.
  - Membership is rebuilt from today's list + Wikipedia's change table (approximate, usually good back to ~2000); reused tickers can map to the wrong company.

MEMBERSHIP MODES
  - "changes": today's list + Wikipedia change table (best, used whenever the change table can be read).
  - "current_only" (automatic fallback, Wikipedia no longer serves the change table): today's list + each stock's 'Date added' as its start date.
    Removes the look-ahead of "was already in the index before it joined", but it contains ONLY current members -> STRONG survivorship bias
    (every stock that left the index is missing). Treat the backtest as an optimistic upper bound.

CHANGES vs previous version
  - Wikipedia: reads hidden/collapsed tables (displayed_only=False) and, as 3rd attempt, uses the MediaWiki API (always returns the full HTML).
  - Descriptive User-Agent (Wikimedia blocks generic ones). EDIT `HDR` WITH YOUR EMAIL.
  - Safe column picking (the old `next(..., next(...))` default was evaluated eagerly), footnote markers like "[1]" stripped from tickers.
  - Yahoo: robust to MultiIndex columns also for single-ticker batches (old code could write a 2-row CSV header), retry per batch,
    and resume (already downloaded tickers are skipped unless refresh=True).
"""
from __future__ import annotations
import io, re, time
from pathlib import Path
import numpy as np, pandas as pd

HDR = {"User-Agent": "Top20MomentumResearch/1.0 (personal research; tu_email@ejemplo.com)"}   # <- put your email
WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
WIKI_API = "https://en.wikipedia.org/w/api.php"

def _y(t):                                                           # Yahoo uses BRK-B, the Darwinex list uses BRK.B
    return re.sub(r"\[.*?\]", "", str(t)).strip().upper().replace(".", "-")

def status(prices_dir: Path, membership_csv: Path, benchmark="SPY", min_files=50, max_age_days=45, need_membership=True):
    files = list(Path(prices_dir).glob("*.csv")) if Path(prices_dir).is_dir() else []
    has_b = (Path(prices_dir) / f"{benchmark}.csv").exists(); has_m = Path(membership_csv).exists()
    last = None
    if has_b:
        last = pd.read_csv(Path(prices_dir) / f"{benchmark}.csv", usecols=["Date"], parse_dates=["Date"])["Date"].max()
    ok = has_b and len(files) - int(has_b) >= min_files and (has_m or not need_membership)
    return dict(ok=ok, n_files=len(files), has_benchmark=has_b, has_membership=has_m, last_bar=last,
                age_days=(pd.Timestamp.today().normalize() - last).days if last is not None else None, max_age_days=max_age_days)

def build_membership(current: pd.DataFrame, changes: pd.DataFrame, data_start) -> pd.DataFrame:
    """current: [ticker]; changes: [date, added, removed] (tickers may be NaN). Walks the changes backwards from today's list -> intervals ticker,start,end."""
    data_start = pd.Timestamp(data_start); open_ = {_y(t): pd.NaT for t in current["ticker"]}; out = []
    ch = changes.dropna(subset=["date"]).sort_values("date", kind="stable")
    for r in ch[::-1].itertuples():
        if r.date < data_start: break
        if isinstance(r.added, str) and r.added.strip():
            a = _y(r.added)
            if a in open_: out.append((a, r.date, open_.pop(a)))
        if isinstance(r.removed, str) and r.removed.strip(): open_[_y(r.removed)] = r.date
    out += [(t, data_start, e) for t, e in open_.items()]
    return pd.DataFrame(out, columns=["ticker", "start", "end"]).sort_values(["ticker", "start"]).reset_index(drop=True)

def build_membership_current_only(cur: pd.DataFrame, data_start) -> pd.DataFrame:
    """Only today's members: start = 'Date added' (clipped to data_start; unknown -> data_start), end = open. Stocks that left the index are NOT here."""
    data_start = pd.Timestamp(data_start); added = pd.to_datetime(cur["added"], errors="coerce") if "added" in cur else pd.Series(pd.NaT, index=cur.index)
    out = pd.DataFrame({"ticker": cur["ticker"].map(_y), "start": added.fillna(data_start).clip(lower=data_start), "end": pd.NaT})
    return out.drop_duplicates("ticker").sort_values("ticker").reset_index(drop=True)

def _flat(cols): return [" ".join(dict.fromkeys(map(str, c))).strip() if isinstance(c, tuple) else str(c) for c in cols]

_TK = r"^[A-Z][A-Z0-9.\-]{0,5}$"
def _changes_by_content(t):
    """Fallback when the headers have unexpected names: one date column + the first two ticker-like columns (Wikipedia order: added, removed)."""
    t = t.copy(); t.columns = _flat(t.columns); t.columns = [f"{c}#{i}" for i, c in enumerate(t.columns)]
    if len(t) < 50: return None
    dc = next((c for c in t.columns[:3] if pd.to_datetime(t[c], errors="coerce", format="mixed").notna().mean() > .6), None)
    tk = [c for c in t.columns if c != dc and t[c].dropna().astype(str).str.strip().str.match(_TK).mean() > .3]
    return (dc, tk[0], tk[1], t) if dc and len(tk) >= 2 else None

def _changes_by_header(t):
    """Normal case: headers like 'Effective Date', 'Added Ticker', 'Added Security', 'Removed Ticker', 'Removed Security'."""
    c = t.copy(); c.columns = _flat(c.columns); low = [x.lower() for x in c.columns]
    if len(c) <= 50: return None
    if not (any("added" in x and "date" not in x for x in low) and any("removed" in x for x in low)): return None
    def pick(w):
        cand = [k for k, l in zip(c.columns, low) if w in l and "date" not in l]
        tk = [k for k in cand if any(z in k.lower() for z in ("ticker", "symbol"))]
        return (tk or cand or [None])[0]
    a, r = pick("added"), pick("removed")
    d = next((k for k, l in zip(c.columns, low) if ("date" in l or "effective" in l) and "added" not in l and "removed" not in l), c.columns[0])
    return (d, a, r, c) if a and r else None

def parse_sp500_tables(tables, data_start, allow_current_only=False):
    """Finds the 'current constituents' and the 'changes' tables by content (Wikipedia changes layout / order / header names over time)."""
    cur = None; res = None
    for t in tables:
        low = [c.lower() for c in _flat(t.columns)]
        if cur is None and len(t) > 400 and any(c.startswith(("symbol", "ticker")) for c in low):
            i = next(k for k, c in enumerate(low) if c.startswith(("symbol", "ticker")))
            j = next((k for k, c in enumerate(low) if c.startswith("date") and "add" in c), None)          # 'Date added' / 'Date first added'
            cur = pd.DataFrame({"ticker": t.iloc[:, i].astype(str),
                                "added": pd.to_datetime(t.iloc[:, j], errors="coerce", format="mixed") if j is not None else pd.NaT})
    for t in tables:                                                                   # 1) by header names
        res = _changes_by_header(t)
        if res: break
    if res is None:                                                                    # 2) by content
        for t in tables:
            res = _changes_by_content(t)
            if res: break
    if cur is not None and res is None and allow_current_only:
        print("WARNING: Wikipedia change table not available -> membership from today's list + 'Date added' only (STRONG survivorship bias, optimistic backtest).")
        return build_membership_current_only(cur, data_start)
    if cur is None or res is None:
        info = [(i, t.shape, [str(x)[:25] for x in _flat(t.columns)[:5]]) for i, t in enumerate(tables)]
        raise ValueError(f"Could not find the Wikipedia tables (current={cur is not None}, changes={res is not None}). Tables seen (index, shape, columns): {info}")
    dcol, acol, rcol, c = res
    ch = pd.DataFrame({"date": pd.to_datetime(c[dcol], errors="coerce", format="mixed"), "added": c[acol], "removed": c[rcol]})
    print(f"Wikipedia: {len(cur)} current members, {len(ch)} index changes (date='{dcol}', added='{acol}', removed='{rcol}')")
    return build_membership(cur, ch, data_start)

def _read_tables(html):
    """All tables of the page, INCLUDING the ones pandas would hide (display:none / collapsed), plus the one with id='changes' if present."""
    tabs = pd.read_html(io.StringIO(html), displayed_only=False)
    if 'id="changes"' in html:
        try: tabs += pd.read_html(io.StringIO(html), attrs={"id": "changes"}, displayed_only=False)
        except ValueError: pass
    return tabs

def fetch_sp500_wikipedia(data_start):
    import requests
    attempts = [(WIKI, None),                                                          # normal page
                (WIKI + "?action=render", None),                                       # bare article HTML (no skin), same content
                (WIKI_API, dict(action="parse", page="List_of_S&P_500_companies", prop="text", format="json", formatversion=2, redirects=1))]   # MediaWiki API
    last, good_html = None, None
    for url, params in attempts:
        try:
            r = requests.get(url, params=params, headers=HDR, timeout=30); r.raise_for_status()
            html = r.json()["parse"]["text"] if params else r.text
            good_html = good_html or html
            return parse_sp500_tables(_read_tables(html), data_start)
        except Exception as e:
            last = f"{type(e).__name__}: {e} | {url}"
            print(f"   Wikipedia attempt failed ({url.split('?')[0]}): {str(e)[:300]}")
    if good_html:                                                                      # page readable but no change table -> degraded mode
        return parse_sp500_tables(_read_tables(good_html), data_start, allow_current_only=True)
    raise ValueError(last)

def _extract(raw, t):
    """One ticker's OHLCV out of yf.download's result, whatever the column layout (flat, (ticker, field) or (field, ticker))."""
    if isinstance(raw.columns, pd.MultiIndex):
        if t in raw.columns.get_level_values(0): return raw[t]
        if t in raw.columns.get_level_values(1): return raw.xs(t, axis=1, level=1)
        raise KeyError(t)
    return raw

def download_prices(tickers, out_dir: Path, start, min_days=252, batch=40, overwrite=False):
    import yfinance as yf
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True); got, failed = [], []
    tickers = sorted({_y(t) for t in tickers})
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        if not overwrite:                                                              # resume: skip what is already on disk
            done = [t for t in chunk if (out_dir / f"{t}.csv").exists()]; got += done; chunk = [t for t in chunk if t not in done]
            if not chunk: continue
        raw = None
        for attempt in range(2):                                                       # one retry (Yahoo rate limits / transient errors)
            try:
                raw = yf.download(chunk, start=start, auto_adjust=True, group_by="ticker", progress=False, threads=True)
                if raw is not None and len(raw): break
            except Exception as e: print("\nbatch failed:", str(e)[:200])
            time.sleep(3)
        if raw is None or not len(raw): failed += chunk; continue
        for t in chunk:
            try: d = _extract(raw, t)[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
            except KeyError: failed.append(t); continue
            if len(d) < min_days: failed.append(t); continue
            d.index.name = "Date"; d.to_csv(out_dir / f"{t}.csv"); got.append(t)
        print(f"   downloaded {min(i + batch, len(tickers))}/{len(tickers)}", end="\r"); time.sleep(0.5)
    print(); return got, failed

def ensure_data(cfg: dict, resolve, refresh=False):
    """Check the data; download only if something is missing (or refresh=True). `resolve` maps the paths of engine_defaults to absolute ones."""
    ed, dc = cfg["engine_defaults"], cfg.get("data", {})
    pdir, mcsv, bench = Path(resolve(ed["prices_dir"])), Path(resolve(ed["membership_csv"])), ed.get("benchmark", "SPY").upper()
    uni = dc.get("universe", "sp500_wikipedia"); start = ed.get("data_start", "2003-01-01")
    st = status(pdir, mcsv, bench, max_age_days=dc.get("max_age_days", 45), need_membership=(uni == "sp500_wikipedia"))
    if st["ok"] and not refresh:
        print(f"Data OK: {st['n_files'] - 1} tickers + {bench}, last bar {st['last_bar']:%Y-%m-%d}, membership {'yes' if st['has_membership'] else 'no'}")
        if st["age_days"] is not None and st["age_days"] > st["max_age_days"]: print(f"   NOTE: data is {st['age_days']} days old (refresh with ensure_data(..., refresh=True) if you need it).")
        return st
    if not dc.get("auto_download", True): raise FileNotFoundError(f"Data missing in {pdir} and data.auto_download is false: {st}")
    print(f"Data missing or refresh requested ({st}). Downloading from free sources (one-off, can take 10-20 min)...")
    if uni == "sp500_wikipedia":
        mem = fetch_sp500_wikipedia(start); mcsv.parent.mkdir(parents=True, exist_ok=True); mem.to_csv(mcsv, index=False); tickers = mem["ticker"].unique().tolist()
        print(f"Membership rebuilt: {len(mem)} intervals, {len(tickers)} tickers ever in the index since {start}")
    else:
        tickers = [l.strip() for l in open(resolve(dc["tickers_file"]), encoding="utf-8") if l.strip() and not l.startswith("#")]
    got, failed = download_prices(tickers + [bench], pdir, start, dc.get("min_history_days", 252), overwrite=refresh)
    print(f"Prices saved: {len(got)} | not available on Yahoo: {len(failed)} ({100 * len(failed) / max(len(tickers), 1):.0f}%) - mostly delisted names -> survivorship bias stays for them.")
    if failed: pd.Series(failed, name="ticker").to_csv(pdir.parent / "download_failed.csv", index=False)
    return status(pdir, mcsv, bench, need_membership=(uni == "sp500_wikipedia"))