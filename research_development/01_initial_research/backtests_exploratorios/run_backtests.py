#!/usr/bin/env python3
"""Run preregistered, gated OHLC exploratory tests; never validates an edge."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


FAMILY_NAMES = {
    "momentum_trend",
    "mean_reversion",
    "calendar_seasonality",
    "overnight_gaps",
    "carry_relative_value",
}
SUPPORTED_ENGINE = "ohlc_directional_v1"
SUPPORTED_SIGNALS = {"time_series_momentum", "time_series_mean_reversion"}
FAMILY_SIGNAL = {
    "momentum_trend": "time_series_momentum",
    "mean_reversion": "time_series_mean_reversion",
}


class Blocked(Exception):
    """A known gate/specification issue that should skip execution cleanly."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--family", choices=sorted(FAMILY_NAMES), required=True)
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--gate-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise Blocked(f"Falta {label}.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Blocked(f"{label} no es una fecha ISO-8601 válida.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Blocked(f"{label} debe incluir zona horaria explícita.")
    return parsed.astimezone(timezone.utc)


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise Blocked(f"No se pudo leer el preregistro {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise Blocked(f"El preregistro {path} debe contener un objeto YAML.")
    return value


def gate_verdict(path: Path) -> tuple[str, str | None]:
    if not path.is_file():
        return "REVIEW_FAILED_OR_UNPARSEABLE", None
    text = path.read_text(encoding="utf-8")
    verdict = re.search(r"(?im)^VEREDICTO:\s*([A-Z_]+)\s*$", text)
    hypothesis = re.search(r"(?im)^HIPOTESIS_ID:\s*([^\s]+)\s*$", text)
    return (verdict.group(1) if verdict else "REVIEW_FAILED_OR_UNPARSEABLE",
            hypothesis.group(1) if hypothesis else None)


def write_result(output_dir: Path, result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "manifest_schema": 1,
        "status": result.get("status"),
        "family": result.get("family"),
        "hypothesis_id": result.get("hypothesis_id"),
        "run_date_utc": result.get("run_date_utc"),
        "gate_verdict": result.get("gate_verdict"),
        "engine": result.get("engine"),
        "backtests_run": result.get("backtests_run", False),
        "reason": result.get("reason"),
        "provenance": result.get("provenance", {}),
        "strategy": result.get("strategy"),
        "data_contract": result.get("data_contract"),
        "data_quality": result.get("data_quality"),
        "execution_costs": result.get("execution_costs"),
        "research_need": result.get("research_need"),
        "cost_bps": result.get("cost_bps"),
        "periods": result.get("periods"),
        "periods_2x_cost": result.get("periods_2x_cost"),
        "trade_log": result.get("trade_log"),
    }
    (output_dir / "experiment_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Backtest exploratorio",
        "",
        f"**Estado:** `{result['status']}`  ",
        f"**Hipótesis:** `{result.get('hypothesis_id') or 'sin identificar'}`  ",
        f"**Motor:** `{result.get('engine') or 'no ejecutado'}`",
        "",
        result.get("reason", ""),
        "",
    ]
    if result.get("data_quality"):
        data = result["data_quality"]
        lines.extend([
            "## Datos utilizados",
            "",
            f"- Filas válidas: {data['valid_rows']} / {data['expected_observations']}",
            f"- Cobertura calculada contra el conteo/calendario preregistrado: {data['coverage_pct']:.3f}%",
            f"- Primer timestamp: {data['first_timestamp_utc']}",
            f"- Último timestamp: {data['last_timestamp_utc']}",
            f"- Ruta: `{data['dataset_path']}`",
            "",
        ])
    if result.get("periods"):
        lines.extend([
            "## Resultados descriptivos (netos de costo preregistrado)",
            "",
            "| Periodo | Operaciones | Media neta % | Mediana neta % | Acierto % | Retorno compuesto % |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for name, values in result["periods"].items():
            lines.append(
                f"| {name} | {values['trades']} | {values['mean_net_pct']:.4f} | "
                f"{values['median_net_pct']:.4f} | {values['win_rate_pct']:.2f} | "
                f"{values['compounded_net_pct']:.4f} |"
            )
        lines.append("")
        lines.extend([
            "| Periodo | Media neta a 2x costo % | Retorno compuesto a 2x costo % |",
            "|---|---:|---:|",
        ])
        for name, values in result.get("periods_2x_cost", {}).items():
            lines.append(f"| {name} | {values['mean_net_pct']:.4f} | {values['compounded_net_pct']:.4f} |")
        lines.append("")
        validation_count = result["periods"].get("validation", {}).get("trades", 0)
        target = result.get("independent_events_or_trades_target", 100)
        if validation_count < target:
            lines.extend([
                f"**Muestra insuficiente:** validación tiene {validation_count} operaciones; el preregistro fijó un mínimo de revisión de {target}. No interpretar como evidencia confirmatoria.",
                "",
            ])
    lines.extend([
        "## Interpretación",
        "",
        "Resultado exploratorio para comprobar implementación y descartar hipótesis. "
        "No es evidencia confirmatoria ni aprobación de un edge. No se optimizaron parámetros, "
        "no se estimó significancia estadística y las salidas deben revisarse junto al preregistro "
        "y los costos documentados.",
        "",
    ])
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def period_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [row["net_return"] for row in rows]
    if not returns:
        return {
            "trades": 0,
            "mean_net_pct": 0.0,
            "median_net_pct": 0.0,
            "win_rate_pct": 0.0,
            "compounded_net_pct": 0.0,
        }
    compounded = math.prod(1 + value for value in returns) - 1
    return {
        "trades": len(returns),
        "mean_net_pct": statistics.fmean(returns) * 100,
        "median_net_pct": statistics.median(returns) * 100,
        "win_rate_pct": sum(value > 0 for value in returns) / len(returns) * 100,
        "compounded_net_pct": compounded * 100,
    }


def check_preregistration(config: dict[str, Any], family: str, gate_id: str | None, repo_root: Path) -> None:
    if config.get("schema_version") != 2:
        raise Blocked("El preregistro debe usar schema_version: 2 para el contrato reproducible actual.")
    if config.get("status") != "frozen":
        raise Blocked("El preregistro no está congelado (status debe ser frozen).")
    hyp_id = config.get("hypothesis_id")
    if not isinstance(hyp_id, str) or not hyp_id or hyp_id != gate_id:
        raise Blocked("El ID del preregistro no coincide exactamente con HIPOTESIS_ID del gate.")
    if not hyp_id.startswith(f"{family}."):
        raise Blocked("El ID de hipótesis no corresponde a la familia del job.")
    if config.get("decision", {}).get("exploratory_only") is not True:
        raise Blocked("El preregistro debe marcar decision.exploratory_only: true.")
    if config.get("decision", {}).get("confirmatory_claim_allowed") is not False:
        raise Blocked("El preregistro debe prohibir claims confirmatorios.")

    need = config.get("research_need", {})
    for key in ("question", "decision_use"):
        value = need.get(key)
        if not isinstance(value, str) or not value.strip() or value.startswith("<"):
            raise Blocked(f"Falta research_need.{key}; vincula la prueba a tu necesidad actual.")
    if not isinstance(need.get("brief_path"), str):
        raise Blocked("Falta research_need.brief_path.")
    brief_file = repo_file(repo_root, need["brief_path"], "el brief de necesidad")
    expected_brief_hash = need.get("brief_sha256")
    if not isinstance(expected_brief_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_brief_hash):
        raise Blocked("research_need.brief_sha256 debe fijar el SHA-256 del brief al congelar.")
    if sha256_file(brief_file) != expected_brief_hash:
        raise Blocked("El brief cambió desde que se congeló el preregistro; actualiza la referencia y vuelve a congelar.")

    claim = config.get("claim", {})
    for key in ("falsifiable_prediction", "null_or_comparator"):
        value = claim.get(key)
        if not isinstance(value, str) or not value.strip() or value.startswith("<"):
            raise Blocked(f"Falta claim.{key}.")

    data = config.get("data", {})
    for key in ("provenance_verified", "expected_calendar_verified"):
        if data.get(key) is not True:
            raise Blocked(f"data.{key} debe verificarse explícitamente.")
    if not isinstance(data.get("verification_evidence"), str) or not data["verification_evidence"].strip():
        raise Blocked("Falta evidencia de verificación de procedencia/calendario.")
    for key in ("provider", "feed", "price_basis", "source_timezone", "source_license_status"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip() or value.startswith("<"):
            raise Blocked(f"Falta data.{key}; se requiere el contrato común de datos.")
    for key in ("sha256", "expected_calendar_sha256"):
        value = data.get(key)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise Blocked(f"data.{key} debe contener el SHA-256 congelado.")
    if not isinstance(data.get("adjustments_and_feed_notes"), str) or not data["adjustments_and_feed_notes"].strip() or data["adjustments_and_feed_notes"].startswith("<"):
        raise Blocked("Faltan ajustes, convención de precios y notas de feed.")
    if not isinstance(data.get("path_or_dataset_id"), str) or data["path_or_dataset_id"].startswith("<"):
        raise Blocked("Falta la ruta local al dataset.")
    for key in ("timestamp_column", "open_column", "close_column"):
        if not isinstance(data.get(key), str) or not data[key].strip() or data[key].startswith("<"):
            raise Blocked(f"Falta data.{key}.")
    if not isinstance(data.get("expected_calendar_csv"), str) or data["expected_calendar_csv"].startswith("<"):
        raise Blocked("Falta el calendario de timestamps esperados generado para la sesión/venue." )
    parse_utc(data.get("start_utc"), "data.start_utc")
    parse_utc(data.get("end_utc"), "data.end_utc")

    rules = config.get("strategy_rules", {})
    if rules.get("engine") != SUPPORTED_ENGINE:
        raise Blocked(f"Motor no soportado; se requiere {SUPPORTED_ENGINE}.")
    if rules.get("signal_type") not in SUPPORTED_SIGNALS:
        raise Blocked("signal_type no está soportado por el ejecutor actual.")
    if FAMILY_SIGNAL.get(family) != rules.get("signal_type"):
        raise Blocked("El tipo de señal no corresponde a la familia declarada o aún no está soportado.")
    for key in ("lookback_bars", "holding_bars"):
        if isinstance(rules.get(key), bool) or not isinstance(rules.get(key), int) or rules[key] <= 0:
            raise Blocked(f"strategy_rules.{key} debe ser un entero positivo congelado.")
    expected_signal = "close_return_sign" if rules.get("signal_type") == "time_series_momentum" else "inverse_close_return_sign"
    fixed_rules = {
        "signal": expected_signal,
        "entry": "next_bar_open",
        "exit": "close_after_holding_bars",
        "sizing": "one_unit_no_leverage",
        "position_constraints": "non_overlapping",
    }
    for key, expected in fixed_rules.items():
        if rules.get(key) != expected:
            raise Blocked(f"strategy_rules.{key} debe ser {expected} para este motor.")

    costs = config.get("execution_costs", {})
    if costs.get("round_trip_cost_bps") is None or not math.isfinite(float(costs["round_trip_cost_bps"])) or float(costs["round_trip_cost_bps"]) < 0:
        raise Blocked("Falta un costo total round_trip_cost_bps no negativo.")
    if not isinstance(costs.get("cost_evidence"), str) or not costs["cost_evidence"].strip():
        raise Blocked("Falta execution_costs.cost_evidence.")
    stress = costs.get("stress_scenario")
    if not isinstance(stress, str) or not stress.strip() or stress.startswith("<"):
        raise Blocked("Falta un escenario de estrés de costos preregistrado.")
    if stress != "2x_round_trip_cost":
        raise Blocked("El motor actual requiere stress_scenario: 2x_round_trip_cost.")

    evaluation = config.get("evaluation", {})
    if not isinstance(evaluation.get("primary_metric"), str) or not evaluation["primary_metric"].strip() or evaluation["primary_metric"].startswith("<"):
        raise Blocked("Falta evaluation.primary_metric.")
    for key in ("discovery_period_utc", "validation_period_utc"):
        bounds = evaluation.get(key)
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise Blocked(f"Falta evaluation.{key} [inicio, fin].")
        start, end = parse_utc(bounds[0], f"evaluation.{key}[0]"), parse_utc(bounds[1], f"evaluation.{key}[1]")
        if start >= end:
            raise Blocked(f"evaluation.{key} tiene un intervalo vacío o invertido.")
    discovery_start, discovery_end = [parse_utc(v, "discovery boundary") for v in evaluation["discovery_period_utc"]]
    validation_start, validation_end = [parse_utc(v, "validation boundary") for v in evaluation["validation_period_utc"]]
    data_start, data_end = parse_utc(data["start_utc"], "data.start_utc"), parse_utc(data["end_utc"], "data.end_utc")
    if discovery_end > validation_start:
        raise Blocked("Discovery y validación deben ser cronológicos y no solaparse.")
    if discovery_start < data_start or validation_end > data_end:
        raise Blocked("Los períodos de evaluación deben quedar dentro del intervalo de datos preregistrado.")
    if evaluation.get("primary_metric") != "mean_net_return_per_trade":
        raise Blocked("El motor actual requiere primary_metric: mean_net_return_per_trade.")
    if isinstance(evaluation.get("independent_events_or_trades_target"), bool) or not isinstance(evaluation.get("independent_events_or_trades_target"), int) or evaluation["independent_events_or_trades_target"] < 100:
        raise Blocked("El objetivo debe ser >=100 eventos/operaciones independientes, o Gate A debe mantener HOLD por potencia.")
    if isinstance(evaluation.get("total_planned_tests"), bool) or not isinstance(evaluation.get("total_planned_tests"), int) or evaluation["total_planned_tests"] <= 0:
        raise Blocked("total_planned_tests debe ser un entero positivo preregistrado.")
    if not isinstance(evaluation.get("parameter_variants"), list):
        raise Blocked("parameter_variants debe ser una lista preregistrada.")


def input_file(repo_root: Path, relative_value: str, description: str) -> Path:
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise Blocked(f"La ruta para {description} debe ser relativa al repo y no puede salir del repositorio.")
    resolved_repo = repo_root.resolve()
    repo_candidate = (resolved_repo / relative).resolve()
    try:
        repo_candidate.relative_to(resolved_repo)
    except ValueError as exc:
        raise Blocked(f"La ruta para {description} sale del repositorio.") from exc
    candidates = [repo_candidate]
    data_root = os.environ.get("RESEARCH_DATA_DIR")
    if data_root:
        candidate = (Path(data_root).resolve() / relative).resolve()
        try:
            candidate.relative_to(Path(data_root).resolve())
        except ValueError as exc:
            raise Blocked(f"La ruta para {description} sale de RESEARCH_DATA_DIR.") from exc
        candidates.append(candidate)
    for file_path in candidates:
        if file_path.is_file():
            return file_path
    raise Blocked(f"No existe {description}: {relative} (repo ni RESEARCH_DATA_DIR).")


def repo_file(repo_root: Path, relative_value: str, description: str) -> Path:
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts:
        raise Blocked(f"La ruta para {description} debe permanecer dentro del repo.")
    file_path = (repo_root / relative).resolve()
    try:
        file_path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise Blocked(f"La ruta para {description} sale del repositorio.") from exc
    if not file_path.is_file():
        raise Blocked(f"No existe {description}: {relative}.")
    return file_path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_commit(repo_root: Path) -> str | None:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def load_expected_timestamps(data: dict[str, Any], repo_root: Path) -> set[datetime]:
    calendar_path = input_file(repo_root, data["expected_calendar_csv"], "el calendario esperado")
    expected: set[datetime] = set()
    try:
        with calendar_path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None or "timestamp_utc" not in reader.fieldnames:
                raise Blocked("El calendario esperado debe tener una columna timestamp_utc.")
            for line_number, row in enumerate(reader, start=2):
                stamp = parse_utc(row.get("timestamp_utc"), f"timestamp_utc del calendario, fila {line_number}")
                if stamp in expected:
                    raise Blocked(f"Timestamp duplicado en calendario: {stamp.isoformat()}.")
                expected.add(stamp)
    except OSError as exc:
        raise Blocked(f"No se pudo leer el calendario esperado: {exc}") from exc
    start, end = parse_utc(data["start_utc"], "data.start_utc"), parse_utc(data["end_utc"], "data.end_utc")
    if not expected or any(stamp < start or stamp >= end for stamp in expected):
        raise Blocked("El calendario está vacío o contiene timestamps fuera del intervalo preregistrado.")
    return expected


def load_bars(data: dict[str, Any], repo_root: Path) -> tuple[list[dict[str, Any]], float, int]:
    relative = Path(data["path_or_dataset_id"])
    csv_path = input_file(repo_root, str(relative), "el dataset preregistrado")
    cols = [data[key] for key in ("timestamp_column", "open_column", "close_column")]
    bars: list[dict[str, Any]] = []
    seen: set[datetime] = set()
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None or any(name not in reader.fieldnames for name in cols):
                raise Blocked("El CSV no contiene las columnas preregistradas de timestamp/open/close.")
            for line_number, row in enumerate(reader, start=2):
                try:
                    stamp = parse_utc(row[cols[0]], f"timestamp en fila {line_number}")
                    open_price, close_price = float(row[cols[1]]), float(row[cols[2]])
                except (TypeError, ValueError) as exc:
                    raise Blocked(f"Precio/timestamp faltante o inválido en fila {line_number}.") from exc
                if not math.isfinite(open_price) or not math.isfinite(close_price) or open_price <= 0 or close_price <= 0:
                    raise Blocked(f"Precio no positivo o no finito en fila {line_number}.")
                if stamp in seen:
                    raise Blocked(f"Timestamp duplicado: {stamp.isoformat()}.")
                seen.add(stamp)
                bars.append({"timestamp": stamp, "open": open_price, "close": close_price})
    except OSError as exc:
        raise Blocked(f"No se pudo leer el CSV: {exc}") from exc
    bars.sort(key=lambda row: row["timestamp"])
    start, end = parse_utc(data["start_utc"], "data.start_utc"), parse_utc(data["end_utc"], "data.end_utc")
    if start >= end:
        raise Blocked("El intervalo data.start_utc/data.end_utc es vacío o está invertido.")
    bars = [row for row in bars if start <= row["timestamp"] < end]
    expected = load_expected_timestamps(data, repo_root)
    observed = {row["timestamp"] for row in bars}
    unexpected = observed - expected
    if unexpected:
        raise Blocked(f"El dataset contiene {len(unexpected)} timestamps fuera del calendario esperado; revisar frecuencia, sesión y feed.")
    coverage = len(observed & expected) / len(expected) * 100
    if coverage < 98:
        raise Blocked(f"Cobertura recalculada {coverage:.3f}% < 98% frente al calendario de timestamps esperado.")
    if len(bars) < 3:
        raise Blocked("Se requieren al menos tres observaciones válidas.")
    return bars, coverage, len(expected)


def simulate(bars: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    rules = config["strategy_rules"]
    lookback = rules["lookback_bars"]
    holding = rules["holding_bars"]
    signal_type = rules["signal_type"]
    cost = float(config["execution_costs"]["round_trip_cost_bps"]) / 10000
    trades: list[dict[str, Any]] = []
    last_exit_index = -1
    for signal_index in range(lookback, len(bars) - holding):
        entry_index = signal_index + 1
        exit_index = signal_index + holding
        if entry_index <= last_exit_index:
            continue
        past_close = bars[signal_index - lookback]["close"]
        signal_return = bars[signal_index]["close"] / past_close - 1
        if signal_return == 0:
            continue
        direction = 1 if signal_return > 0 else -1
        if signal_type == "time_series_mean_reversion":
            direction *= -1
        raw_return = (bars[exit_index]["close"] / bars[entry_index]["open"] - 1) * direction
        trades.append({
            "signal_timestamp_utc": bars[signal_index]["timestamp"].isoformat(),
            "entry_timestamp_utc": bars[entry_index]["timestamp"].isoformat(),
            "exit_timestamp_utc": bars[exit_index]["timestamp"].isoformat(),
            "direction": "long" if direction > 0 else "short",
            "gross_return": raw_return,
            "net_return": raw_return - cost,
            "net_return_2x_cost": raw_return - (2 * cost),
        })
        last_exit_index = exit_index
    return {"trades": trades, "cost_bps": cost * 10000}


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    verdict, gate_id = gate_verdict(args.gate_report)
    result: dict[str, Any] = {
        "status": "SKIPPED_GATE",
        "family": args.family,
        "run_date_utc": args.run_date,
        "hypothesis_id": gate_id,
        "gate_verdict": verdict,
        "engine": None,
        "backtests_run": False,
        "periods": {},
        "reason": f"No se ejecutó: el gate devolvió {verdict}; se requiere READY_FOR_EXPLORATORY_BACKTEST.",
        "provenance": {
            "repository_commit": current_commit(args.repo_root),
            "python_version": platform.python_version(),
            "gate_report_sha256": sha256_file(args.gate_report) if args.gate_report.is_file() else None,
            "research_brief_sha256": (
                sha256_file(args.repo_root / "research_development/01_initial_research/research_brief.md")
                if (args.repo_root / "research_development/01_initial_research/research_brief.md").is_file()
                else None
            ),
            "input_sha256": {},
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        },
    }
    prereg_root = args.repo_root / "research_development" / "01_initial_research" / "backtests_exploratorios" / "preregistrations" / args.family
    preregistrations = sorted(prereg_root.glob("*.yaml")) if prereg_root.is_dir() else []

    if verdict != "READY_FOR_EXPLORATORY_BACKTEST":
        write_result(args.output_dir, result)
        return 0
    matching = []
    for path in preregistrations:
        try:
            candidate = load_yaml(path)
        except Blocked:
            continue
        if candidate.get("hypothesis_id") == gate_id:
            matching.append((path, candidate))
    if len(matching) != 1:
        result.update({"status": "BLOCKED_PREREGISTRATION", "reason": f"Se esperaba exactamente un preregistro coincidente y congelado para {gate_id}; se encontraron {len(matching)}."})
        write_result(args.output_dir, result)
        return 0

    prereg_path, config = matching[0]
    result["preregistration"] = str(prereg_path.relative_to(args.repo_root))
    result["provenance"]["input_sha256"]["preregistration"] = sha256_file(prereg_path)
    try:
        check_preregistration(config, args.family, gate_id, args.repo_root)
        data_config = config["data"]
        dataset_path = input_file(args.repo_root, data_config["path_or_dataset_id"], "el dataset")
        calendar_path = input_file(args.repo_root, data_config["expected_calendar_csv"], "el calendario esperado")
        if sha256_file(dataset_path) != data_config["sha256"]:
            raise Blocked("El SHA-256 del dataset no coincide con el preregistro congelado.")
        if sha256_file(calendar_path) != data_config["expected_calendar_sha256"]:
            raise Blocked("El SHA-256 del calendario no coincide con el preregistro congelado.")
        result["provenance"]["input_sha256"].update({
            "dataset": sha256_file(dataset_path),
            "expected_calendar": sha256_file(calendar_path),
        })
        bars, coverage, expected_rows = load_bars(config["data"], args.repo_root)
        minimum_rows = config["strategy_rules"]["lookback_bars"] + config["strategy_rules"]["holding_bars"] + 1
        if len(bars) < minimum_rows:
            raise Blocked(f"El dataset tiene {len(bars)} filas; se necesitan al menos {minimum_rows} para lookback y holding preregistrados.")
    except (Blocked, KeyError, TypeError, ValueError) as exc:
        result.update({"status": "BLOCKED_PREREGISTRATION_OR_DATA", "reason": str(exc)})
        write_result(args.output_dir, result)
        return 0

    try:
        simulation = simulate(bars, config)
        trades = simulation["trades"]
        evaluation = config["evaluation"]
        discovery_start = parse_utc(evaluation["discovery_period_utc"][0], "discovery start")
        discovery_end = parse_utc(evaluation["discovery_period_utc"][1], "discovery end")
        validation_start = parse_utc(evaluation["validation_period_utc"][0], "validation start")
        validation_end = parse_utc(evaluation["validation_period_utc"][1], "validation end")
        periods = {
            "discovery": [t for t in trades if discovery_start <= datetime.fromisoformat(t["entry_timestamp_utc"]) < discovery_end],
            "validation": [t for t in trades if validation_start <= datetime.fromisoformat(t["entry_timestamp_utc"]) < validation_end],
        }
        stress_periods = {
            name: [{**trade, "net_return": trade["net_return_2x_cost"]} for trade in rows]
            for name, rows in periods.items()
        }
        data = config["data"]
        result["data_contract"] = {
            key: data.get(key) for key in (
                "provider", "feed", "price_basis", "source_timezone", "source_license_status"
            )
        }
        result.update({
            "status": "EXECUTED_EXPLORATORY",
            "engine": SUPPORTED_ENGINE,
            "backtests_run": True,
            "reason": "Preregistro congelado y gate aprobados; resultado descriptivo, exploratorio y no confirmatorio.",
            "strategy": {"signal_type": config["strategy_rules"]["signal_type"], "lookback_bars": config["strategy_rules"]["lookback_bars"], "holding_bars": config["strategy_rules"]["holding_bars"]},
            "research_need": config["research_need"],
            "execution_costs": config["execution_costs"],
            "data_quality": {
                "valid_rows": len(bars),
                "expected_observations": expected_rows,
                "coverage_pct": coverage,
                "first_timestamp_utc": bars[0]["timestamp"].isoformat(),
                "last_timestamp_utc": bars[-1]["timestamp"].isoformat(),
                "dataset_path": data["path_or_dataset_id"],
            },
            "cost_bps": simulation["cost_bps"],
            "independent_events_or_trades_target": evaluation["independent_events_or_trades_target"],
            "periods": {name: period_stats(rows) for name, rows in periods.items()},
            "periods_2x_cost": {name: period_stats(rows) for name, rows in stress_periods.items()},
            "trade_log": "trades.csv",
        })
        with (args.output_dir / "trades.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(trades[0]) if trades else ["signal_timestamp_utc", "entry_timestamp_utc", "exit_timestamp_utc", "direction", "gross_return", "net_return"])
            writer.writeheader()
            writer.writerows(trades)
        result["provenance"]["input_sha256"]["trade_log"] = sha256_file(args.output_dir / "trades.csv")
    except Exception as exc:  # Preserve a visible failure artifact while failing the family job.
        result.update({"status": "EXECUTION_ERROR", "reason": f"Fallo inesperado durante la simulación: {type(exc).__name__}: {exc}"})
        write_result(args.output_dir, result)
        print(result["reason"], file=sys.stderr)
        return 1

    write_result(args.output_dir, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
