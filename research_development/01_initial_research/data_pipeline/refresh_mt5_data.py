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


def classify_instrument(symbol_info: Any) -> str:
    description = " ".join(
        str(getattr(symbol_info, key, "") or "")
        for key in ("name", "path", "description", "category", "exchange")
    ).lower()
    if any(term in description for term in ("etf", "exchange traded fund")):
        return "etf"
    if any(term in description for term in ("forex", "fx major", "currency pair")):
        return "fx"
    if any(term in description for term in ("crypto", "bitcoin", "ethereum")):
        return "crypto"
    if any(term in description for term in ("index", "indices")):
        return "index"
    if any(term in description for term in ("stock", "share", "equity")):
        return "equity_or_stock_cfd"
    if any(term in description for term in ("metal", "commodity", "energy")):
        return "commodity"
    return "unclassified"


def discover_broker_symbols(broker: str, data_root: Path) -> list[dict[str, Any]]:
    credentials = get_credentials(broker)
    if not mt5.initialize(
        path=credentials["MT5_PATH"],
        login=int(credentials["MT5_LOGIN"]),
        password=credentials["MT5_PASSWORD"],
        server=credentials["MT5_SERVER"],
    ):
        raise RuntimeError(f"MT5 initialize failed for {broker}: {mt5.last_error()}")
    try:
        symbols = mt5.symbols_get()
        if symbols is None:
            raise RuntimeError(f"MT5 symbol discovery failed for {broker}: {mt5.last_error()}")
        disabled_mode = getattr(mt5, "SYMBOL_TRADE_MODE_DISABLED", 0)
        catalog = []
        for info in symbols:
            if getattr(info, "custom", False) or getattr(info, "trade_mode", disabled_mode) == disabled_mode:
                continue
            catalog.append({
                "broker": broker,
                "symbol": info.name,
                "instrument_type": classify_instrument(info),
                "path": getattr(info, "path", "") or "",
                "description": getattr(info, "description", "") or "",
                "exchange": getattr(info, "exchange", "") or "",
                "currency_base": getattr(info, "currency_base", "") or "",
                "currency_profit": getattr(info, "currency_profit", "") or "",
                "trade_mode": int(getattr(info, "trade_mode", 0)),
                "contract_size": float(getattr(info, "trade_contract_size", 0) or 0),
                "digits": int(getattr(info, "digits", 0) or 0),
            })
        catalog.sort(key=lambda item: item["symbol"].casefold())
        catalog_dir = data_root / "catalog"
        catalog_dir.mkdir(parents=True, exist_ok=True)
        catalog_file = catalog_dir / f"{broker}_symbols.json"
        catalog_file.write_text(
            json.dumps({
                "schema_version": 1,
                "provider": broker,
                "discovered_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "tradable_symbol_count": len(catalog),
                "symbols": catalog,
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Discovered {len(catalog)} tradable symbols on {broker}.")
        return catalog
    finally:
        mt5.shutdown()


def attempt_marker(data_root: Path, broker: str, symbol: str, timeframe: str) -> Path:
    return data_root / broker / safe_part(symbol) / f"{timeframe}.error.json"


def series_priority(data_root: Path, entry: dict[str, Any], timeframe: str) -> tuple[str, str, str, str]:
    output = data_root / entry["broker"] / safe_part(entry["symbol"]) / f"{timeframe}.csv"
    metadata_path = output.with_suffix(".metadata.json")
    error_path = attempt_marker(data_root, entry["broker"], entry["symbol"], timeframe)
    if metadata_path.is_file():
        try:
            updated = json.loads(metadata_path.read_text(encoding="utf-8")).get("last_refresh_utc", "")
        except (OSError, json.JSONDecodeError):
            updated = ""
        priority = f"2-{updated}"
    elif error_path.is_file():
        try:
            attempted = json.loads(error_path.read_text(encoding="utf-8")).get("attempted_at_utc", "")
        except (OSError, json.JSONDecodeError):
            attempted = ""
        priority = f"1-{attempted}"
    else:
        priority = "0-"
    return priority, entry["broker"], entry["symbol"].casefold(), timeframe


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
                chunk_end = min(cursor + timedelta(days=365), end)
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
            "instrument_type": entry.get("instrument_type", "unclassified"),
            "broker_symbol_path": entry.get("broker_symbol_path", ""),
            "broker_description": entry.get("broker_description", ""),
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
        settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(settings, dict) or settings.get("schema_version") != 1:
            raise ValueError("market_data_universe.yaml must use schema_version: 1")
        if settings.get("mode") != "discover_all_tradable":
            instruments = load_universe(config_path)
            for entry in instruments:
                for timeframe in entry["timeframes"]:
                    export_series(entry, timeframe, data_root)
            return 0

        brokers = settings.get("brokers", [])
        timeframes = settings.get("screen_timeframes", [])
        if not brokers or any(broker not in {"axi", "darwinex"} for broker in brokers):
            raise ValueError("brokers must include axi and/or darwinex.")
        if not timeframes or any(timeframe not in TIMEFRAMES for timeframe in timeframes):
            raise ValueError(f"screen_timeframes must be chosen from: {', '.join(TIMEFRAMES)}")
        start_utc = settings.get("start_utc")
        if not isinstance(start_utc, str):
            raise ValueError("start_utc is required for initial history discovery.")
        start = parse_utc(start_utc)
        limit = int(settings.get("max_series_per_run", 80))
        if limit <= 0:
            raise ValueError("max_series_per_run must be positive.")

        catalogs: dict[str, list[dict[str, Any]]] = {}
        discovery_errors: dict[str, str] = {}
        for broker in brokers:
            try:
                catalogs[broker] = discover_broker_symbols(broker, data_root)
            except Exception as exc:
                discovery_errors[broker] = f"{type(exc).__name__}: {exc}"
                print(f"Could not discover {broker}: {discovery_errors[broker]}", file=sys.stderr)
        if not catalogs:
            raise RuntimeError("No broker symbol catalog could be read; check MT5 terminals and credentials.")

        entries = [
            {
                "broker": broker,
                "symbol": info["symbol"],
                "instrument_type": info["instrument_type"],
                "broker_symbol_path": info["path"],
                "broker_description": info["description"],
                "timeframes": timeframes,
                "_start": start,
            }
            for broker, items in catalogs.items()
            for info in items
        ]
        tasks = [
            (entry, timeframe)
            for entry in entries
            for timeframe in timeframes
        ]
        tasks.sort(key=lambda task: series_priority(data_root, task[0], task[1]))
        selected = tasks[:limit]
        succeeded: list[str] = []
        errors: list[dict[str, str]] = []
        for entry, timeframe in selected:
            series_id = f"{entry['broker']}/{entry['symbol']}/{timeframe}"
            marker = attempt_marker(data_root, entry["broker"], entry["symbol"], timeframe)
            try:
                export_series(entry, timeframe, data_root)
                marker.unlink(missing_ok=True)
                succeeded.append(series_id)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(json.dumps({
                    "attempted_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "error": message,
                }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                errors.append({"series": series_id, "error": message})
                print(f"Could not refresh {series_id}: {message}", file=sys.stderr)

        summary = {
            "schema_version": 1,
            "refreshed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mode": settings["mode"],
            "discovered_symbols": {broker: len(items) for broker, items in catalogs.items()},
            "timeframes": timeframes,
            "series_per_run_limit": limit,
            "series_pending": max(0, len(tasks) - len(selected)),
            "series_attempted": len(selected),
            "series_succeeded": succeeded,
            "series_errors": errors,
            "discovery_errors": discovery_errors,
            "catalogs": {broker: f"catalog/{broker}_symbols.json" for broker in catalogs},
        }
        summary_dir = data_root / "catalog"
        summary_dir.mkdir(parents=True, exist_ok=True)
        (summary_dir / "latest_refresh_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"Refresh summary: {summary['series_attempted']} attempted, "
            f"{len(succeeded)} succeeded, {len(errors)} errors, "
            f"{summary['series_pending']} series remain in initial backlog."
        )
        if not selected:
            raise RuntimeError("No market-data series were selected for refresh.")
        if not succeeded:
            raise RuntimeError("All selected series failed to refresh; inspect catalog/latest_refresh_summary.json.")
    except Exception as exc:
        print(f"Market data refresh failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
