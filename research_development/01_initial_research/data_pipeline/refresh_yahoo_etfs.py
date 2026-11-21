#!/usr/bin/env python3
"""Refresh Yahoo daily ETF history for exploration; Darwinex remains validation feed."""

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

import pandas as pd
import yfinance as yf


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def yahoo_candidate(symbol: str) -> str:
    candidate = symbol.strip().upper()
    candidate = re.sub(r"\.(US|ETF|CFD)$", "", candidate)
    return candidate


def load_etf_catalog(catalog_path: Path) -> list[dict[str, Any]]:
    value = json.loads(catalog_path.read_text(encoding="utf-8"))
    return [item for item in value.get("symbols", []) if item.get("instrument_type") == "etf"]


def refresh_etf(item: dict[str, Any], data_root: Path) -> dict[str, Any]:
    broker_symbol = item["symbol"]
    yahoo_symbol = yahoo_candidate(broker_symbol)
    output_dir = data_root / "yahoo_exploratory" / "etf" / re.sub(r"[^A-Za-z0-9_.-]+", "_", broker_symbol)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "D1.csv"
    # Replace the full exploratory series each run: Yahoo's adjusted-close
    # history can be revised after later distributions/corporate actions.
    history = yf.Ticker(yahoo_symbol).history(
        period="max",
        interval="1d",
        auto_adjust=False,
        actions=True,
        repair=True,
    )
    if history.empty:
        raise ValueError(f"Yahoo returned no daily history for candidate {yahoo_symbol}.")

    normalized = history.rename_axis("date").copy()
    normalized.index = pd.to_datetime(normalized.index).date
    normalized.index.name = "date"
    normalized = normalized.rename(columns={
        "Open": "open", "High": "high", "Low": "low", "Close": "close",
        "Adj Close": "adj_close", "Volume": "volume", "Dividends": "dividends",
        "Stock Splits": "stock_splits",
    })
    normalized = normalized[[column for column in (
        "open", "high", "low", "close", "adj_close", "volume", "dividends", "stock_splits"
    ) if column in normalized.columns]]
    combined = normalized.sort_index()
    combined.to_csv(output, index_label="date")
    metadata = {
        "schema_version": 1,
        "provider": "Yahoo Finance via yfinance",
        "source_role": "exploration_only",
        "broker": "darwinex",
        "broker_symbol": broker_symbol,
        "yahoo_symbol_candidate": yahoo_symbol,
        "mapping_verified": False,
        "instrument_type_source": "Darwinex MT5 symbol path/description heuristic",
        "timeframe": "D1",
        "timestamp_timezone": "exchange-local daily session date; no intraday timestamp",
        "price_basis": "unadjusted daily OHLC; adj_close and corporate-action columns retained when supplied",
        "first_date": str(combined.index.min()),
        "last_date": str(combined.index.max()),
        "row_count": len(combined),
        "last_refresh_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "csv_sha256": sha256_file(output),
        "validation_feed": "Darwinex MT5; Yahoo is not an execution-price substitute",
    }
    output.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Refreshed Yahoo exploration series {broker_symbol} -> {yahoo_symbol}: {len(combined)} rows")
    return metadata


def main() -> int:
    root_text = os.environ.get("RESEARCH_DATA_DIR", "")
    if not root_text:
        print("RESEARCH_DATA_DIR is required.", file=sys.stderr)
        return 2
    data_root = Path(root_text).resolve()
    catalog = data_root / "catalog" / "darwinex_symbols.json"
    if not catalog.is_file():
        print("Darwinex symbol catalog is not available; run MT5 discovery first.", file=sys.stderr)
        return 1
    items = load_etf_catalog(catalog)
    if not items:
        print("No Darwinex symbols were classified as ETFs; Yahoo refresh skipped.")
        return 0

    errors = []
    successes = []
    for item in items:
        try:
            successes.append(refresh_etf(item, data_root))
        except Exception as exc:
            errors.append({"symbol": item.get("symbol"), "error": f"{type(exc).__name__}: {exc}"})
            print(f"Yahoo ETF exploration refresh failed for {item.get('symbol')}: {exc}", file=sys.stderr)
            time.sleep(1)
    report = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "catalog_etfs": len(items),
        "updated": len(successes),
        "errors": errors,
        "role": "Yahoo is discovery context only; final ETF validation must use Darwinex data.",
    }
    report_dir = data_root / "catalog"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "yahoo_etf_refresh_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if successes or not items else 1


if __name__ == "__main__":
    raise SystemExit(main())
