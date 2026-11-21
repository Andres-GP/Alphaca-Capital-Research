#!/usr/bin/env python3
"""Incrementally export allow-listed Axi/Darwinex MT5 bars outside Git."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5
import yaml


TIMEFRAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
    "W1": "TIMEFRAME_W1",
    "MN1": "TIMEFRAME_MN1",
}
CSV_FIELDS = [
    "timestamp_utc", "open", "high", "low", "close", "tick_volume",
    "spread_points", "real_volume",
]


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timestamp must include timezone: {value}")
    return parsed.astimezone(timezone.utc)


def safe_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError(f"Unsafe path component: {value!r}")
    return cleaned


def get_credentials(broker: str) -> dict[str, str]:
    prefix = broker.upper()
    required = ("MT5_PATH", "MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")
    values = {key: os.environ.get(f"{prefix}_{key}", "") for key in required}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"Missing GitHub secrets for {broker}: {', '.join(prefix + '_' + x for x in missing)}")
    return values


def load_universe(path: Path) -> list[dict[str, Any]]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("market_data_universe.yaml must use schema_version: 1")
    instruments = value.get("instruments")
    if not isinstance(instruments, list) or not instruments:
        raise ValueError("Add at least one allow-listed instrument before running refresh.")
    for entry in instruments:
        if not isinstance(entry, dict) or entry.get("broker") not in {"axi", "darwinex"}:
            raise ValueError("Each instrument must identify broker: axi or darwinex.")
        if not isinstance(entry.get("symbol"), str) or not entry["symbol"].strip():
            raise ValueError("Each instrument requires its exact MT5 symbol.")
        if not isinstance(entry.get("timeframes"), list) or not entry["timeframes"]:
            raise ValueError(f"No timeframes configured for {entry.get('symbol')}.")
        if any(tf not in TIMEFRAMES for tf in entry["timeframes"]):
            raise ValueError(f"Unsupported timeframe for {entry['symbol']}; allowed: {', '.join(TIMEFRAMES)}")
        entry["_start"] = parse_utc(entry["start_utc"])
    return instruments


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def last_epoch(path: Path) -> int | None:
    if not path.exists():
        return None
    latest: int | None = None
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            latest = int(row["timestamp_epoch"])
    return latest


def interval_for_timeframe(timeframe: str) -> timedelta:
    return {
        "M1": timedelta(minutes=1), "M5": timedelta(minutes=5),
        "M15": timedelta(minutes=15), "M30": timedelta(minutes=30),
        "H1": timedelta(hours=1), "H4": timedelta(hours=4),
        "D1": timedelta(days=1), "W1": timedelta(days=7),
        "MN1": timedelta(days=31),
    }[timeframe]


def export_series(entry: dict[str, Any], timeframe: str, data_root: Path) -> None:
    broker, symbol = entry["broker"], entry["symbol"]
    relative = Path(broker) / safe_part(symbol) / f"{timeframe}.csv"
    output = data_root / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    previous_last = last_epoch(output)

    credentials = get_credentials(broker)
    initialized = mt5.initialize(
        path=credentials["MT5_PATH"],
        login=int(credentials["MT5_LOGIN"]),
        password=credentials["MT5_PASSWORD"],
        server=credentials["MT5_SERVER"],
    )
    if not initialized:
        raise RuntimeError(f"MT5 initialize failed for {broker}: {mt5.last_error()}")
    try:
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise RuntimeError(f"MT5 symbol not found on {broker}: {symbol}")
        if not symbol_info.visible and not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Could not enable MT5 symbol {symbol}: {mt5.last_error()}")
        rate_name = TIMEFRAMES[timeframe]
        mt5_timeframe = getattr(mt5, rate_name)
        overlap = interval_for_timeframe(timeframe) * 2
        if previous_last is not None:
            start = datetime.fromtimestamp(previous_last, tz=timezone.utc) - overlap
        else:
            start = entry["_start"]
        end = datetime.now(timezone.utc)
        downloaded = output.with_suffix(".download.csv.tmp")
        downloaded_count = 0
        downloaded_last: int | None = None
        with downloaded.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[*CSV_FIELDS, "timestamp_epoch"])
            writer.writeheader()
            cursor = start
            while cursor < end:
                chunk_end = min(cursor + timedelta(days=30), end)
                rates = mt5.copy_rates_range(symbol, mt5_timeframe, cursor, chunk_end)
                if rates is None:
                    raise RuntimeError(f"MT5 history request failed for {broker}/{symbol}/{timeframe}: {mt5.last_error()}")
                for bar in rates:
                    epoch = int(bar["time"])
                    if (
                        epoch < int(start.timestamp())
                        or (downloaded_last is not None and epoch <= downloaded_last)
                    ):
                        continue
                    stamp = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")
                    writer.writerow({
                        "timestamp_utc": stamp,
                        "timestamp_epoch": str(epoch),
                        "open": str(float(bar["open"])),
                        "high": str(float(bar["high"])),
                        "low": str(float(bar["low"])),
                        "close": str(float(bar["close"])),
                        "tick_volume": str(int(bar["tick_volume"])),
                        "spread_points": str(int(bar["spread"])),
                        "real_volume": str(int(bar["real_volume"])),
                    })
                    downloaded_last = epoch
                    downloaded_count += 1
                cursor = chunk_end

        if previous_last is None and downloaded_count == 0:
            downloaded.unlink(missing_ok=True)
            raise RuntimeError(f"No historical bars returned for {broker}/{symbol}/{timeframe}.")
        if downloaded_count:
            merged = output.with_suffix(".merged.csv.tmp")
            count = 0
            with merged.open("w", newline="", encoding="utf-8") as destination:
                writer = csv.DictWriter(destination, fieldnames=[*CSV_FIELDS, "timestamp_epoch"])
                writer.writeheader()
                if output.exists():
                    with output.open(newline="", encoding="utf-8") as source:
                        for row in csv.DictReader(source):
                            if int(row["timestamp_epoch"]) < int(start.timestamp()):
                                writer.writerow(row)
                                count += 1
                with downloaded.open(newline="", encoding="utf-8") as source:
                    for row in csv.DictReader(source):
                        writer.writerow(row)
                        count += 1
            merged.replace(output)
            downloaded.unlink(missing_ok=True)
        else:
            count = 0
            with output.open(newline="", encoding="utf-8") as stream:
                count = sum(1 for _ in csv.DictReader(stream))
            downloaded.unlink(missing_ok=True)

        if count == 0:
            raise RuntimeError(f"No usable bars remain for {broker}/{symbol}/{timeframe}.")
        first_stamp = last_stamp = None
        with output.open(newline="", encoding="utf-8") as stream:
            final_rows = csv.DictReader(stream)
            for row in final_rows:
                first_stamp = first_stamp or row["timestamp_utc"]
                last_stamp = row["timestamp_utc"]

        # Never persist login, password, or account number in market-data metadata.
        info_fields = (
            "name", "path", "description", "currency_base", "currency_profit",
            "currency_margin", "digits", "point", "trade_contract_size",
            "trade_tick_size", "trade_tick_value", "swap_long", "swap_short",
            "swap_rollover3days", "trade_calc_mode",
        )
        metadata = {
            "schema_version": 1,
            "provider": broker,
            "feed": f"{broker} MT5 broker history",
            "symbol": symbol,
            "timeframe": timeframe,
            "price_basis": "broker_chart_ohlc; MT5 spread_points exported separately",
            "timestamp_timezone": "UTC (MetaTrader epoch timestamps)",
            "source_license_status": "broker-account access; redistribution terms not assessed",
            "first_timestamp_utc": first_stamp,
            "last_timestamp_utc": last_stamp,
            "bar_count": count,
            "last_refresh_utc": end.isoformat().replace("+00:00", "Z"),
            "contract_specification": {
                key: getattr(symbol_info, key, None) for key in info_fields
            },
            "csv_sha256": sha256_file(output),
            "note": "MT5 bar history; spread is broker-reported points per bar, not historical tick-by-tick executable bid/ask. The latest bar may still be forming; frozen expected calendars must include closed bars only.",
        }
        output.with_suffix(".metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Updated {relative}: {count} bars, sha256={metadata['csv_sha256']}")
    finally:
        mt5.shutdown()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    config_path = Path(os.environ.get("MARKET_DATA_UNIVERSE", repo_root / "research_development/01_initial_research/data_pipeline/market_data_universe.yaml"))
    data_root_text = os.environ.get("RESEARCH_DATA_DIR", "")
    if not data_root_text:
        print("RESEARCH_DATA_DIR must point to persistent storage outside the Git checkout.", file=sys.stderr)
        return 2
    data_root = Path(data_root_text).resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    try:
        instruments = load_universe(config_path)
        for entry in instruments:
            for timeframe in entry["timeframes"]:
                export_series(entry, timeframe, data_root)
    except Exception as exc:
        print(f"Market data refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
