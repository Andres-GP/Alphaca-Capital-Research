"""
download_dukascopy.py

Download historical index data from Dukascopy and save one CSV per instrument.

Corrections (v2):
  FIX #1  INTERVAL = MIN_5 (antes MIN_30). El doc pide confirmación 5-15 min.
  FIX #2  START_YEAR = 2018 (alineado con id config start: "2018-01-01").
  NEW #3  Session-open check: warn si <90% de sesiones arrancan a 09:30 NY.
  NEW #4  Soporte M1/M5/M15/M30/H1 en el mapa de intervalos.
  NEW #5  DST-aware: check 09:30 se hace en America/New_York, no en UTC.
  FIX #6  Pre-history: años vacíos al inicio NO abortan. Holes en medio SÍ.

Uso:
    python download_dukascopy.py
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone, time as dtime
from pathlib import Path
from typing import Optional

import dukascopy_python as dp
import numpy as np
import pandas as pd
from dukascopy_python import instruments as ins


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
INSTRUMENTS = {
    "btcusd": ins.INSTRUMENT_VCCY_BTC_USD,
}

START_YEAR = 2010                     # baja todo lo disponible; los años vacíos se saltan
END_DATE = datetime.now(timezone.utc).replace(tzinfo=None)

INTERVAL = dp.INTERVAL_HOUR_1
_INTERVALS = {
    dp.INTERVAL_MIN_1:    ("m1",  timedelta(minutes=1)),
    dp.INTERVAL_MIN_5:    ("m5",  timedelta(minutes=5)),
    dp.INTERVAL_MIN_15:   ("m15", timedelta(minutes=15)),
    dp.INTERVAL_MIN_30:   ("m30", timedelta(minutes=30)),
    dp.INTERVAL_HOUR_1:   ("h1",  timedelta(hours=1)),
}
INTERVAL_TAG, EXPECTED_SPACING = _INTERVALS[INTERVAL]

OFFER_SIDE = dp.OFFER_SIDE_BID
OUTPUT_DIR = Path("research_development/data/dukascopy")
OVERWRITE = False

MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5

# NEW #3 / NEW #5
SESSION_TZ = "America/New_York"
SESSION_OPEN = dtime(9, 30)
MIN_SESSION_COVERAGE = 0.90


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def find_instruments(keyword: str):
    """Print and return instrument constants whose name/value contains `keyword`."""
    hits = [
        (name, getattr(ins, name))
        for name in dir(ins)
        if name.startswith("INSTRUMENT_")
        and keyword.upper() in f"{name} {getattr(ins, name)}".upper()
    ]
    for name, value in hits:
        print(f"{name} -> {value}")
    if not hits:
        print(f"No instrument constants match '{keyword}'.")
    return hits


def output_path(name: str) -> Path:
    return OUTPUT_DIR / f"{name}_{INTERVAL_TAG}_utc.csv"


def fetch_year(instrument, year: int) -> Optional[pd.DataFrame]:
    """Fetch one calendar year. Returns DataFrame (possibly empty) or None on hard failure."""
    start = datetime(year, 1, 1)
    end = min(datetime(year + 1, 1, 1), END_DATE)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return dp.fetch(instrument, INTERVAL, OFFER_SIDE, start, end)
        except Exception as exc:
            print(f"  {year}: attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS)
    return None


def check_spacing(name: str, df: pd.DataFrame) -> None:
    """Abort if downloaded bars are not the timeframe we asked for."""
    spacing = df.index.to_series().diff().median()
    if spacing != EXPECTED_SPACING:
        raise ValueError(
            f"{name}: median spacing between bars is {spacing}, expected {EXPECTED_SPACING} "
            f"({INTERVAL_TAG}). Not saving: the content would not match the file name."
        )
    print(f"  spacing check OK: median bar spacing = {spacing}")


def check_session_open(name: str, df: pd.DataFrame) -> float:
    """NEW #3 / NEW #5: % of sessions whose first bar is exactly 09:30 NY."""
    ny_idx = df.index.tz_convert(SESSION_TZ)
    dates = ny_idx.normalize()
    first_bars = df.groupby(dates).head(1)
    first_times = first_bars.index.tz_convert(SESSION_TZ).time
    total = len(first_times)
    sessions_at_open = int(sum(1 for t in first_times if t == SESSION_OPEN))
    frac = sessions_at_open / total if total else 0.0

    status = "OK" if frac >= MIN_SESSION_COVERAGE else "WARN"
    print(f"  [{status}] session-open 09:30 NY: {frac:.1%} ({sessions_at_open}/{total} sesiones)")
    if frac < MIN_SESSION_COVERAGE:
        print(
            "    ⚠  Muchas sesiones no arrancan a 09:30 NY. Posibles causas:\n"
            "       - Timestamps estampados al CIERRE de la barra (deberían ser al OPEN).\n"
            "       - Holes de datos en Dukascopy para esas fechas.\n"
            "       - Instrumento no cotiza 09:30 NY (raro para índices US).\n"
            "       El motor descarta sesiones sin barra 09:30 exacta (tod[s] != open_min)."
        )
    return frac


def download_instrument(name: str, instrument) -> Optional[pd.DataFrame]:
    print(f"\n=== {name} ({INTERVAL_TAG}) ===")
    parts: list[pd.DataFrame] = []
    failed: list[int] = []
    empty_after_data: list[int] = []
    empty_before_data: list[int] = []
    seen_data = False

    for year in range(START_YEAR, END_DATE.year + 1):
        data = fetch_year(instrument, year)
        if data is None:
            print(f"  {year}: FAILED (network/retries)")
            failed.append(year)
            continue
        if len(data) == 0:
            if seen_data:
                print(f"  {year}: EMPTY (hole after data — aborting)")
                empty_after_data.append(year)
            else:
                print(f"  {year}: empty (pre-history, skipping)")
                empty_before_data.append(year)
            continue
        print(f"  {year}: {len(data):,} candles")
        seen_data = True
        parts.append(data)

    if failed or empty_after_data:
        raise RuntimeError(
            f"{name}: years failed={failed}, holes={empty_after_data}. "
            f"Not saving a file with gaps; rerun."
        )
    if not parts:
        print(f"No data downloaded for {name}.")
        return None

    df = pd.concat(parts)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")

    check_spacing(name, df)
    check_session_open(name, df)

    path = output_path(name)
    df.to_csv(path, index_label="timestamp")
    print(f"Saved {path}: {df.index.min()} -> {df.index.max()} ({len(df):,} candles)")
    if empty_before_data:
        print(f"  (skipped pre-history years: {empty_before_data})")
    return df


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not OVERWRITE:
        existing = [output_path(n) for n in INSTRUMENTS if output_path(n).exists()]
        if existing:
            raise FileExistsError(
                f"Already exists: {[str(p) for p in existing]}. "
                f"Rename/move them or set OVERWRITE = True."
            )

    summary = []
    for name, instrument in INSTRUMENTS.items():
        df = download_instrument(name, instrument)
        if df is not None:
            summary.append((name, df.index.min(), df.index.max(), len(df)))

    print("\n=== SUMMARY (first available date per instrument) ===")
    for name, first, last, n in summary:
        print(f"{name:8s} {INTERVAL_TAG}  {first:%Y-%m-%d} -> {last:%Y-%m-%d}  {n:,} candles")


if __name__ == "__main__":
    main()