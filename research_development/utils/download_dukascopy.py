"""
download_dukascopy.py  (v4, BTCUSD)

Descarga historia de Dukascopy (BID) y guarda CSV(s) por instrumento.

Cambios v4.1 (para monday_effect_engine.py):
  - Salida en UN solo CSV: btcusd_h1_utc.csv, columna de tiempo 'time' (UTC), open/high/low/close/volume.
    (Si pesara mas de MAX_FILE_MB cae al esquema de partes.) En el motor:
        set_engine_defaults(csv_path="research_development/data/dukascopy/btcusd_h1_utc.csv")
  - Chequeo "engine ready": velas en punto, y cuantos lunes tienen la ventana completa
    (domingo 23:00 -> martes 00:00, sin huecos) + primer lunes operable por el calentamiento del percentil.

Cambios v4 respecto a v3 (DAX):
  - Instrumento: BTCUSD (resuelto por nombre, ver resolve_instrument).
  - START_YEAR = 2013 (los anios vacios al inicio se saltan; Dukascopy probablemente
    empieza bastante despues de 2013).
  - INTERVAL = H1 por defecto (cambia a dp.INTERVAL_MIN_5 si quieres M5).
  - Se quitan los chequeos de sesion cash/Berlin y gap del lunes (BTC es 24/7).
    Nuevos chequeos: espaciado, cobertura por anio, huecos mas grandes y
    cobertura de las horas 21-23 UTC (ventana overnight).
  - Se mantiene el split en archivos de max MAX_FILE_MB (corta solo entre dias UTC):
        btcusd_h1_utc_part01.csv, btcusd_h1_utc_part02.csv, ...
  - load_parts(name) los une en un DataFrame ordenado.

Uso:
    pip install dukascopy-python pandas numpy
    python download_dukascopy.py
Si resolve_instrument() no encuentra BTC, corre find_instruments("BTC") y ajusta INSTRUMENT_KEYWORDS.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import dukascopy_python as dp
import numpy as np
import pandas as pd
from dukascopy_python import instruments as ins


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
# nombre de salida -> palabras clave para ubicar la constante en dukascopy_python.instruments
INSTRUMENT_KEYWORDS = {
    "btcusd": ["BTC_USD", "BTCUSD", "BTC/USD"],
}

START_YEAR = 2013                     # los anios vacios al inicio se saltan
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

OFFER_SIDE = dp.OFFER_SIDE_BID        # BID, igual que los CSV de Axi/MT5
OUTPUT_DIR = Path("research_development/data/dukascopy")
OVERWRITE = False
MAX_FILE_MB = 28                      # tamano maximo por archivo (MB = 1024*1024 bytes)
SINGLE_FILE = True                    # un solo CSV (lo que lee monday_effect_engine); cae a partes si pesa de mas

# Requisitos del motor (ENGINE_DEFAULTS de monday_effect_engine.py)
ENGINE_ENTRY_DOW = 0                  # lunes
ENGINE_HOLD_BARS = 24                 # salida martes 00:00
ENGINE_PCTL_MIN_BARS = 4380           # velas minimas de calentamiento del percentil

MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5

# Ventana overnight a revisar (horas UTC)
OVERNIGHT_HOURS = (21, 22, 23)
MIN_HOUR_COVERAGE = 0.90
BIG_GAP = timedelta(hours=6)          # huecos mayores a esto se listan


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def find_instruments(keyword: str):
    """Imprime y devuelve las constantes de instrumento cuyo nombre/valor contiene `keyword`."""
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


def resolve_instrument(keywords: list[str]):
    """Devuelve la constante del instrumento; aborta mostrando candidatos si es ambiguo o no existe."""
    for kw in keywords:
        hits = [
            (name, getattr(ins, name))
            for name in dir(ins)
            if name.startswith("INSTRUMENT_") and kw.upper() in f"{name} {getattr(ins, name)}".upper()
        ]
        if len(hits) == 1:
            print(f"Instrumento: {hits[0][0]} -> {hits[0][1]}")
            return hits[0][1]
        if len(hits) > 1:
            print(f"Varios candidatos para '{kw}':")
            for n, v in hits:
                print(f"  {n} -> {v}")
            raise ValueError("Ambiguo: ajusta INSTRUMENT_KEYWORDS (candidatos arriba).")
    raise ValueError(f"No encontre el instrumento con {keywords}. Usa find_instruments('BTC').")


def part_glob(name: str) -> str:
    return f"{name}_{INTERVAL_TAG}_utc_part*.csv"


def existing_parts(name: str) -> list[Path]:
    return sorted(OUTPUT_DIR.glob(part_glob(name)))


def single_path(name: str) -> Path:
    return OUTPUT_DIR / f"{name}_{INTERVAL_TAG}_utc.csv"


def write_output(name: str, df: pd.DataFrame) -> list[Path]:
    """Un solo CSV con columna 'time' (formato del motor); si excede MAX_FILE_MB, partes."""
    if SINGLE_FILE:
        csv = df.to_csv(index_label="time")
        if len(csv.encode("utf-8")) <= MAX_FILE_MB * 1024 * 1024:
            for old in existing_parts(name):
                old.unlink()
            path = single_path(name)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(csv)
            return [path]
        print(f"  [WARN] el CSV unico excede {MAX_FILE_MB} MB: se guarda en partes (el motor lee un solo archivo).")
    return write_parts(name, df)


def write_parts(name: str, df: pd.DataFrame) -> list[Path]:
    """Guarda df en orden cronologico en archivos <= MAX_FILE_MB, cortando solo entre dias UTC."""
    limit = int(MAX_FILE_MB * 1024 * 1024)
    lines = df.to_csv(index_label="timestamp").splitlines(keepends=True)
    header, body = lines[0], lines[1:]
    header_bytes = len(header.encode("utf-8"))

    # agrupar por dia UTC (los primeros 10 caracteres del timestamp ISO son la fecha)
    days: list[list[str]] = []
    last_key = None
    for ln in body:
        key = ln[:10]
        if key != last_key:
            days.append([])
            last_key = key
        days[-1].append(ln)

    chunks: list[list[str]] = [[]]
    size = header_bytes
    for day in days:
        day_bytes = sum(len(x.encode("utf-8")) for x in day)
        if header_bytes + day_bytes > limit:
            raise ValueError(f"Un solo dia ({day[0][:10]}) excede {MAX_FILE_MB} MB; aumenta MAX_FILE_MB.")
        if size + day_bytes > limit and chunks[-1]:
            chunks.append([])
            size = header_bytes
        chunks[-1].extend(day)
        size += day_bytes

    for old in existing_parts(name):          # limpia partes viejas (solo llega aqui con OVERWRITE)
        old.unlink()
    paths: list[Path] = []
    for i, chunk in enumerate(chunks, start=1):
        path = OUTPUT_DIR / f"{name}_{INTERVAL_TAG}_utc_part{i:02d}.csv"
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(header)
            fh.writelines(chunk)
        paths.append(path)
    return paths


def load_parts(name: str) -> pd.DataFrame:
    """Une las partes en un DataFrame con indice UTC ordenado."""
    files = [single_path(name)] if single_path(name).exists() else existing_parts(name)
    if not files:
        raise FileNotFoundError(f"No hay datos para {name} en {OUTPUT_DIR}")
    df = pd.concat(pd.read_csv(f, index_col=0, parse_dates=True) for f in files)
    return df[~df.index.duplicated(keep="last")].sort_index()


def fetch_year(instrument, year: int) -> Optional[pd.DataFrame]:
    """Descarga un anio calendario. Devuelve DataFrame (posiblemente vacio) o None si falla."""
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


# ---------------------------------------------------------------------------
# CHECKS
# ---------------------------------------------------------------------------
def check_spacing(name: str, df: pd.DataFrame) -> None:
    """Aborta si las barras no son del timeframe pedido."""
    spacing = df.index.to_series().diff().median()
    if spacing != EXPECTED_SPACING:
        raise ValueError(
            f"{name}: median spacing between bars is {spacing}, expected {EXPECTED_SPACING} "
            f"({INTERVAL_TAG}). Not saving: the content would not match the file name."
        )
    print(f"  spacing check OK: median bar spacing = {spacing}")


def check_year_coverage(df: pd.DataFrame) -> None:
    """Barras reales vs esperadas por anio (entre la primera y la ultima barra de ese anio)."""
    rows = []
    for year, g in df.groupby(df.index.year):
        span = g.index.max() - g.index.min()
        expected = int(span / EXPECTED_SPACING) + 1
        rows.append((year, len(g), expected, len(g) / expected))
    cov = pd.DataFrame(rows, columns=["year", "bars", "expected", "coverage"]).set_index("year")
    cov["coverage"] = (cov.coverage * 100).round(1)
    print("  cobertura por anio (%):")
    print(cov.to_string())


def check_big_gaps(df: pd.DataFrame) -> None:
    """Lista los huecos mas grandes entre barras consecutivas."""
    d = df.index.to_series().diff()
    big = d[d > BIG_GAP].sort_values(ascending=False)
    if big.empty:
        print(f"  [OK] sin huecos mayores a {BIG_GAP}")
        return
    print(f"  [WARN] {len(big)} huecos mayores a {BIG_GAP} (top 5):")
    for ts, gap in big.head(5).items():
        print(f"    {ts - gap} -> {ts}  ({gap})")


def check_overnight_hours(df: pd.DataFrame) -> None:
    """% de dias UTC con al menos una barra en cada hora de la ventana overnight."""
    days = df.index.normalize().unique()
    n = len(days)
    for h in OVERNIGHT_HOURS:
        have = df.index[df.index.hour == h].normalize().nunique()
        frac = have / n if n else 0.0
        status = "OK" if frac >= MIN_HOUR_COVERAGE else "WARN"
        print(f"  [{status}] hora {h:02d} UTC: {frac:.1%} ({have}/{n} dias)")


def check_weekdays(df: pd.DataFrame) -> None:
    """Barras por dia de la semana (para ver si hay cierre de fin de semana o no)."""
    names = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    counts = df.groupby(df.index.dayofweek).size().reindex(range(7), fill_value=0)
    print("  barras por dia de semana: " + " | ".join(f"{names[i]} {counts[i]:,}" for i in range(7)))


def check_prices(df: pd.DataFrame) -> None:
    """Sanity basico: precios no positivos y high < low."""
    bad_px = int((df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    bad_hl = int((df.high < df.low).sum())
    status = "OK" if bad_px == 0 and bad_hl == 0 else "WARN"
    print(f"  [{status}] precios <= 0: {bad_px} | high < low: {bad_hl}")


def check_engine_ready(df: pd.DataFrame) -> None:
    """Lo que necesita monday_effect_engine: velas H1 en punto y ventana del lunes completa."""
    if EXPECTED_SPACING != timedelta(hours=1):
        print("  [WARN] el motor espera velas de 1 h; con otro INTERVAL no lo va a poder leer bien.")
        return
    off = int((df.index.minute != 0).sum())
    print(f"  [{'OK' if off == 0 else 'WARN'}] velas fuera de la hora en punto: {off} (gap_mode='strict' las rechaza)")

    # cada lunes 00:00 UTC necesita: vela de senal (dom 23:00) ... hasta la salida (mar 00:00), sin huecos
    mondays = pd.date_range(df.index.min().normalize(), df.index.max(), freq="W-MON")
    ok_days = []
    for m in mondays:
        need = pd.date_range(m - timedelta(hours=1), m + timedelta(hours=ENGINE_HOLD_BARS), freq="1h")
        if df.index.isin(need).sum() == len(need):
            ok_days.append(m)
    n = len(mondays)
    frac = len(ok_days) / n if n else 0.0
    print(f"  [{'OK' if frac >= 0.90 else 'WARN'}] lunes con ventana completa "
          f"(dom 23:00 -> mar 00:00): {frac:.1%} ({len(ok_days)}/{n})")
    if frac < 0.50:
        print("    Casi ningun lunes sirve: puede que el instrumento cierre fines de semana. "
              "El motor descartaria esos lunes.")

    # calentamiento del percentil: el primer lunes operable necesita >= ENGINE_PCTL_MIN_BARS velas previas
    first_ok = next((m for m in ok_days if (df.index < m).sum() >= ENGINE_PCTL_MIN_BARS), None)
    print(f"  primer lunes operable (>= {ENGINE_PCTL_MIN_BARS} velas previas): {first_ok}")


# ---------------------------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------------------------
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
                print(f"  {year}: EMPTY (hole after data - aborting)")
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
    check_prices(df)
    check_year_coverage(df)
    check_big_gaps(df)
    check_overnight_hours(df)
    check_weekdays(df)
    check_engine_ready(df)

    paths = write_output(name, df)
    for p in paths:
        print(f"  {p.name}: {p.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Saved {len(paths)} part(s): {df.index.min()} -> {df.index.max()} ({len(df):,} candles)")
    if empty_before_data:
        print(f"  (skipped pre-history years: {empty_before_data})")
    return df


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not OVERWRITE:
        existing = [p for n in INSTRUMENT_KEYWORDS
                    for p in existing_parts(n) + ([single_path(n)] if single_path(n).exists() else [])]
        if existing:
            raise FileExistsError(
                f"Already exists: {[str(p) for p in existing]}. "
                f"Rename/move them or set OVERWRITE = True."
            )

    summary = []
    for name, kws in INSTRUMENT_KEYWORDS.items():
        instrument = resolve_instrument(kws)
        df = download_instrument(name, instrument)
        if df is not None:
            summary.append((name, df.index.min(), df.index.max(), len(df)))

    print("\n=== SUMMARY (first available date per instrument) ===")
    for name, first, last, n in summary:
        print(f"{name:8s} {INTERVAL_TAG}  {first:%Y-%m-%d} -> {last:%Y-%m-%d}  {n:,} candles")


if __name__ == "__main__":
    main()