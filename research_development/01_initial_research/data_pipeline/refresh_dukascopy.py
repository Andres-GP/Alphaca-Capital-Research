#!/usr/bin/env python3
"""Refresh matching CFD/FX history using the same Dukascopy Python feed as utils/download_dukascopy.py."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dukascopy_python as dp
import pandas as pd
from dukascopy_python import instruments as ins


INTERVALS = {
    "M15": (dp.INTERVAL_MIN_15, "15min"),
    "H1": (dp.INTERVAL_HOUR_1, "1h"),
}
START_YEAR = 2000
MAX_SERIES_PER_RUN = 12
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5
OFFER_SIDE = dp.OFFER_SIDE_BID


def normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def base_symbol(symbol: str) -> str:
    # MT5 broker suffixes such as .a, .pro or # are not part of Dukascopy names.
    return re.sub(r"[.#][A-Za-z0-9_-]*$", "", symbol).upper()


def source_instruments() -> list[tuple[str, Any, str, set[str]]]:
    result = []
    for name in dir(ins):
        if not name.startswith("INSTRUMENT_"):
            continue
        value = getattr(ins, name)
        label = name.removeprefix("INSTRUMENT_")
        value_text = str(value)
        value_name = str(getattr(value, "name", "") or "")
        normalized = {normalize(label), normalize(value_text), normalize(value_name)}
        result.append((label, value, " ".join(x for x in (label, value_text, value_name) if x), normalized))
    return result


def match_instrument(symbol: str, available: list[tuple[str, Any, str, set[str]]]) -> tuple[str, Any, str] | None:
    target = normalize(base_symbol(symbol))
    exact = [item for item in available if target in item[3]]
    if len(exact) == 1:
        name, value, label, _ = exact[0]
        return name, value, label
    # Match a broker suffix only when it leaves one unambiguous provider instrument.
    # Provider constants sometimes add an asset-class prefix (for example
    # FX_EURUSD); accept either side only when the match is unique.
    partial = [
        item for item in available
        if any(token.startswith(target) or token.endswith(target) for token in item[3] if token)
    ]
    if len(partial) == 1:
        name, value, label, _ = partial[0]
        return name, value, label
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_catalogs(data_root: Path) -> list[dict[str, Any]]:
    entries = []
    for broker in ("axi", "darwinex"):
        path = data_root / "catalog" / f"{broker}_symbols.json"
        if not path.is_file():
            continue
        contents = json.loads(path.read_text(encoding="utf-8"))
        entries.extend(contents.get("symbols", []))
    return entries


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    result = frame.copy()
    result.index = pd.to_datetime(result.index, utc=True)
    result.index.name = "timestamp_utc"
    result = result.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close",
        "Volume": "volume", "AskVolume": "volume",
    })
    required = [column for column in ("open", "high", "low", "close", "volume") if column in result.columns]
    result = result[required]
    return result[~result.index.duplicated(keep="last")].sort_index()


def fetch_year(instrument: Any, interval: Any, year: int) -> pd.DataFrame:
    start = datetime(year, 1, 1)
    end = min(datetime(year + 1, 1, 1), datetime.now(timezone.utc).replace(tzinfo=None))
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return normalize_frame(dp.fetch(instrument, interval, OFFER_SIDE, start, end))
        except Exception:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_WAIT_SECONDS * attempt)
    return pd.DataFrame()


def fetch_recent(instrument: Any, interval: Any, start: pd.Timestamp) -> pd.DataFrame:
    start_naive = start.to_pydatetime().astimezone(timezone.utc).replace(tzinfo=None)
    end_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return normalize_frame(dp.fetch(instrument, interval, OFFER_SIDE, start_naive, end_naive))
        except Exception:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_WAIT_SECONDS * attempt)
    return pd.DataFrame()


def update_series(
    source_name: str,
    source_value: Any,
    source_label: str,
    timeframe: str,
    interval: Any,
    data_root: Path,
    symbol_aliases: list[str],
) -> dict[str, Any]:
    output_dir = data_root / "dukascopy" / re.sub(r"[^A-Za-z0-9_.-]+", "_", source_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{timeframe}.csv"

    existing = None
    if output.is_file():
        existing = pd.read_csv(output, parse_dates=["timestamp_utc"]).set_index("timestamp_utc")
        existing.index = pd.to_datetime(existing.index, utc=True)
        start = existing.index.max() - pd.Timedelta(days=7)
        fresh = fetch_recent(source_value, interval, start)
        combined = pd.concat([existing, fresh])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        annual = []
        started = False
        for year in range(START_YEAR, datetime.now(timezone.utc).year + 1):
            frame = fetch_year(source_value, interval, year)
            if frame.empty:
                # Skip prehistory; once a series has begun, an empty year is an unexplained gap.
                if started:
                    raise ValueError(f"No {timeframe} data in {year} after the series already began.")
                continue
            started = True
            annual.append(frame)
        if not annual:
            raise ValueError(f"No Dukascopy history available for {source_name}/{timeframe}.")
        combined = pd.concat(annual)
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()

    combined = combined[(combined[["open", "high", "low", "close"]] > 0).all(axis=1)]
    if combined.empty:
        raise ValueError(f"No valid positive OHLC bars remain for {source_name}/{timeframe}.")
    combined.to_csv(output, index_label="timestamp_utc")
    metadata = {
        "schema_version": 1,
        "provider": "Dukascopy via dukascopy-python (same fetch method as research_development/utils/download_dukascopy.py)",
        "source_instrument": source_name,
        "source_instrument_label": source_label,
        "matched_broker_symbols": sorted(set(symbol_aliases)),
        "timeframe": timeframe,
        "offer_side": "BID",
        "price_basis": "Dukascopy BID OHLC; broker-specific spreads/swaps/execution are not represented",
        "first_timestamp_utc": combined.index.min().isoformat(),
        "last_timestamp_utc": combined.index.max().isoformat(),
        "bar_count": len(combined),
        "last_refresh_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "csv_sha256": sha256_file(output),
        "role": "secondary CFD/FX exploration and cross-feed comparison; not broker fill data",
    }
    output.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> int:
    root_text = os.environ.get("RESEARCH_DATA_DIR", "")
    if not root_text:
        print("RESEARCH_DATA_DIR is required.", file=sys.stderr)
        return 2
    data_root = Path(root_text).resolve()
    catalogs = load_catalogs(data_root)
    if not catalogs:
        print("MT5 symbol catalogs are unavailable; run discovery first.", file=sys.stderr)
        return 1

    available = source_instruments()
    matched: dict[str, dict[str, Any]] = {}
    unmatched = []
    for broker_item in catalogs:
        if broker_item.get("instrument_type") == "etf":
            continue
        found = match_instrument(broker_item.get("symbol", ""), available)
        if not found:
            unmatched.append(f"{broker_item.get('broker')}/{broker_item.get('symbol')}")
            continue
        source_name, source_value, source_label = found
        item = matched.setdefault(source_name, {
            "name": source_name,
            "value": source_value,
            "label": source_label,
            "aliases": [],
        })
        item["aliases"].append(f"{broker_item['broker']}/{broker_item['symbol']}")

    tasks = []
    for item in matched.values():
        for timeframe, (interval, _) in INTERVALS.items():
            output = data_root / "dukascopy" / re.sub(r"[^A-Za-z0-9_.-]+", "_", item["name"]) / f"{timeframe}.csv"
            updated = ""
            if output.with_suffix(".metadata.json").is_file():
                try:
                    updated = json.loads(output.with_suffix(".metadata.json").read_text(encoding="utf-8")).get("last_refresh_utc", "")
                except (OSError, json.JSONDecodeError):
                    pass
            priority = "0" if not output.is_file() else "1"
            tasks.append((priority, updated, item, timeframe, interval))
    tasks.sort(key=lambda row: (row[0], row[1], row[2]["name"], row[3]))

    successes = []
    errors = []
    for _, _, item, timeframe, interval in tasks[:MAX_SERIES_PER_RUN]:
        try:
            result = update_series(
                item["name"], item["value"], item["label"],
                timeframe, interval, data_root, item["aliases"],
            )
            successes.append(result)
            print(f"Dukascopy refreshed {item['name']}/{timeframe}: {result['bar_count']} bars")
        except Exception as exc:
            errors.append({"source_instrument": item["name"], "timeframe": timeframe, "error": f"{type(exc).__name__}: {exc}"})
            print(f"Dukascopy refresh failed for {item['name']}/{timeframe}: {exc}", file=sys.stderr)

    report = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "matched_source_instruments": len(matched),
        "series_attempted": min(len(tasks), MAX_SERIES_PER_RUN),
        "series_pending": max(0, len(tasks) - MAX_SERIES_PER_RUN),
        "series_updated": len(successes),
        "errors": errors,
        "mt5_symbols_without_unambiguous_dukascopy_match": unmatched,
        "role": "external exploration only; repeat candidates against Axi/Darwinex MT5 before validation",
    }
    report_dir = data_root / "catalog"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "dukascopy_refresh_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if successes or not tasks else 1


if __name__ == "__main__":
    raise SystemExit(main())
