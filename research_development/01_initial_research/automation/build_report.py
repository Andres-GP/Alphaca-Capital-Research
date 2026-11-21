#!/usr/bin/env python3
"""Build reproducible Markdown, YAML/JSON, SVG, and PDF family reports."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
import unicodedata
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROLE_TITLES = {
    "literatura": "Literatura y mecanismo económico",
    "datos": "Evidencia empírica y datos",
    "red_team": "Crítica independiente / red team",
    "backtest_gate": "Viabilidad del backtest exploratorio",
}
BACKTEST_GATE_STATUSES = {
    "READY_FOR_EXPLORATORY_BACKTEST",
    "HOLD_DATA",
    "HOLD_SPECIFICATION",
    "REFORMULATE",
    "REJECT",
}
PALETTE = {
    "forest": colors.HexColor("#1F3D36"),
    "lime": colors.HexColor("#C8F5A8"),
    "ink": colors.HexColor("#202725"),
    "muted": colors.HexColor("#60706A"),
    "paper": colors.HexColor("#F7F8F5"),
    "line": colors.HexColor("#DCE4DE"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True)
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--family-dir", required=True, type=Path)
    return parser.parse_args()


def load_roles(report_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    outputs: dict[str, str] = {}
    engines: dict[str, str] = {}
    for role in ROLE_TITLES:
        output_path = report_dir / "agentes" / f"{role}.md"
        engine_path = report_dir / "agentes" / f"{role}_engine.txt"
        outputs[role] = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else "FALLO: no se recibió salida para este rol."
        engines[role] = engine_path.read_text(encoding="utf-8").strip() if engine_path.exists() else "failed"
        if outputs[role].startswith("FALLO:"):
            engines[role] = "failed"
    return outputs, engines


def hypothesis_paths(family_dir: Path) -> list[Path]:
    return sorted(family_dir.glob("**/hypothesis.md"))


def backtest_gate_status(output: str) -> str:
    match = re.search(r"(?im)^VEREDICTO:\s*([A-Z_]+)\s*$", output)
    if not match or match.group(1) not in BACKTEST_GATE_STATUSES:
        return "REVIEW_FAILED_OR_UNPARSEABLE"
    return match.group(1)


def report_markdown(family: str, run_date: str, outputs: dict[str, str], engines: dict[str, str], family_dir: Path, hypotheses: list[Path], backtest_result: dict) -> str:
    status = "revisión cualitativa completa" if all(engines.values()) and all(x != "failed" for x in engines.values()) else "revisión parcial; uno o más roles fallaron"
    gate_status = backtest_gate_status(outputs["backtest_gate"])
    backtests_run = bool(backtest_result.get("backtests_run"))
    scope = (
        "revisión documental y backtest exploratorio determinista sobre datos preregistrados; el resultado no es confirmatorio."
        if backtests_run else
        "investigación cualitativa y revisión documental; esta corrida no leyó precios ni ejecutó backtests."
    )
    sections = [
        f"# Informe inicial · {family.replace('_', ' ').title()} · {run_date}",
        "",
        f"**Estado de la corrida:** {status}.  ",
        f"**Motores por rol:** {', '.join(f'{role}: {engines[role]}' for role in ROLE_TITLES)}.  ",
        f"**Alcance:** {scope} El gate de viabilidad no confirma ni aprueba automáticamente un edge.",
        "",
        "## Resumen ejecutivo",
        "",
        "Este informe organiza revisión de literatura, diagnóstico de datos, crítica independiente y viabilidad del backtest exploratorio. La necesidad actual del usuario orienta qué preguntas son pertinentes. No declara un edge validado. La cobertura solo se considera calculada cuando el ejecutor la compara con el calendario de timestamps preregistrado; las gates confirmatorias de estadística, robustez y costos siguen pendientes.",
        "",
        "## Árbol de investigación",
        "",
        f"![Árbol de familia, pauta, mercado e hipótesis](tree.svg)",
        "",
        "## Hipótesis existentes",
        "",
    ]
    if hypotheses:
        sections.extend(f"- `{path.relative_to(family_dir).as_posix()}` — veredicto: pendiente de datos y gates." for path in hypotheses)
    else:
        sections.append("No se encontró una ficha de hipótesis en el árbol de la familia.")
    sections.extend(["", "## Gates", "", "| Gate | Estado |", "|---|---|", f"| Viabilidad del backtest exploratorio | `{gate_status}` |", "| Estadística fuera de muestra | Pendiente; sin backtest |", "| Robustez | Pendiente; sin backtest |", "| Costos/spreads/swaps | Pendiente; sin backtest |", "| Aprobación de edge | No confirmado |", ""])
    for role, title in ROLE_TITLES.items():
        sections.extend([f"## {title}", "", f"*Motor:* `{engines[role]}`", "", outputs[role] or "Sin contenido.", ""])
    sections.extend([
        "## Datos, cobertura y pendientes",
        "",
        ("El ejecutor leyó únicamente el dataset preregistrado indicado en el resultado del backtest; su cobertura calculada se reporta allí, contra el calendario local declarado. " if backtests_run else "No se leyeron CSV de mercado en esta corrida; origen, cobertura y huecos siguen sin verificar. ") + "La procedencia del feed y sus condiciones de ejecución deben tener evidencia independiente. No interpolar ni empalmar series sin registrarlo. Si una conclusión requiere datos rellenados o feeds empalmados, marcarla `NO CONFIRMADO`.",
        "",
        "## Control de calidad",
        "",
        "Cualquier fuente citada debe ser anterior a 2018 y contener DOI o URL estable. Las referencias que no pudieron verificarse deben aparecer explícitamente como `no verificada`; no son evidencia de apoyo hasta revisión humana.",
        "",
    ])
    backtest_report = backtest_result.get("report_markdown")
    if isinstance(backtest_report, str) and backtest_report.strip():
        sections.extend(["## Ejecución del backtest exploratorio", "", backtest_report.strip(), ""])
    return "\n".join(sections)


def tree_svg(family: str, family_dir: Path, hypotheses: list[Path]) -> str:
    rows: list[tuple[str, str, str, str]] = []
    for path in hypotheses:
        relative = path.relative_to(family_dir)
        parts = relative.parts
        pattern = parts[0] if len(parts) > 1 else "pauta pendiente"
        market = parts[1] if len(parts) > 2 else "mercado pendiente"
        title = " ".join(path.parent.name.split("_"))
        rows.append((pattern.replace("_", " "), market.replace("_", " "), title, "Pendiente"))
    if not rows:
        rows = [("pauta pendiente", "mercado pendiente", "sin ficha", "Pendiente")]
    height = 118 + len(rows) * 74
    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="{height}" viewBox="0 0 1120 {height}">',
        '<rect width="1120" height="100%" fill="#101613" rx="18"/>',
        '<text x="36" y="44" fill="#C8F5A8" font-family="Arial,sans-serif" font-size="14" letter-spacing="2">ALPHACA CAPITAL · INITIAL RESEARCH</text>',
        f'<text x="36" y="82" fill="#F4F7F3" font-family="Arial,sans-serif" font-size="24" font-weight="700">{html.escape(family.replace("_", " ").title())}</text>',
    ]
    for idx, (pattern, market, title, verdict) in enumerate(rows):
        y = 130 + idx * 74
        if idx == 0:
            chunks.append(f'<path d="M 292 85 V {y+22} H 322" stroke="#3E6557" stroke-width="2" fill="none"/>')
        else:
            chunks.append(f'<path d="M 292 {130+22} V {y+22} H 322" stroke="#3E6557" stroke-width="2" fill="none"/>')
        chunks.extend([
            f'<rect x="36" y="{y}" width="256" height="44" rx="8" fill="#1F3D36"/>',
            f'<text x="52" y="{y+28}" fill="#F4F7F3" font-family="Arial,sans-serif" font-size="15">{html.escape(pattern)}</text>',
            f'<path d="M 292 {y+22} H 322" stroke="#3E6557" stroke-width="2"/>',
            f'<rect x="322" y="{y}" width="200" height="44" rx="8" fill="#202925" stroke="#3E6557"/>',
            f'<text x="338" y="{y+28}" fill="#F4F7F3" font-family="Arial,sans-serif" font-size="14">{html.escape(market)}</text>',
            f'<path d="M 522 {y+22} H 552" stroke="#3E6557" stroke-width="2"/>',
            f'<rect x="552" y="{y}" width="300" height="44" rx="8" fill="#202925" stroke="#3E6557"/>',
            f'<text x="568" y="{y+28}" fill="#F4F7F3" font-family="Arial,sans-serif" font-size="14">{html.escape(title)}</text>',
            f'<path d="M 852 {y+22} H 882" stroke="#3E6557" stroke-width="2"/>',
            f'<rect x="882" y="{y}" width="202" height="44" rx="8" fill="#C8F5A8"/>',
            f'<text x="898" y="{y+28}" fill="#1F3D36" font-family="Arial,sans-serif" font-size="14" font-weight="700">{verdict}</text>',
        ])
    chunks.append('</svg>')
    return "\n".join(chunks)


def pdf_report(path: Path, family: str, run_date: str, markdown: str, outputs: dict[str, str], engines: dict[str, str], backtest_result: dict) -> None:
    def pdf_safe(text: str) -> str:
        # The built-in Helvetica font supports Windows-1252; replace uncommon
        # glyphs so agent prose cannot make PDF generation fail.
        return unicodedata.normalize("NFKC", text).encode("cp1252", "replace").decode("cp1252")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BrandTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=26, textColor=PALETTE["lime"], alignment=TA_LEFT, spaceAfter=8))
    styles.add(ParagraphStyle(name="BrandHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=PALETTE["forest"], spaceBefore=12, spaceAfter=5))
    styles.add(ParagraphStyle(name="BrandBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=PALETTE["ink"], spaceAfter=5))
    doc = SimpleDocTemplate(str(path), pagesize=letter, rightMargin=0.65*inch, leftMargin=0.65*inch, topMargin=0.65*inch, bottomMargin=0.6*inch, title=f"Initial Research · {family} · {run_date}", author="Alphaca Capital Research")
    story = []
    title_box = Table([[Paragraph(escape(pdf_safe(f"Initial Research | {family.replace('_', ' ').title()}")), styles["BrandTitle"])], [Paragraph(escape(run_date), ParagraphStyle("Date", parent=styles["BodyText"], textColor=colors.white, fontSize=9))]], colWidths=[7.2*inch])
    title_box.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), PALETTE["forest"]), ("BOX", (0,0), (-1,-1), 0, PALETTE["forest"]), ("LEFTPADDING", (0,0), (-1,-1), 14), ("RIGHTPADDING", (0,0), (-1,-1), 14), ("TOPPADDING", (0,0), (-1,-1), 10), ("BOTTOMPADDING", (0,0), (-1,-1), 10)]))
    story.extend([title_box, Spacer(1, 12), Paragraph("Resumen de corrida", styles["BrandHeading"])])
    rows = [["Rol", "Motor", "Estado"], *[[ROLE_TITLES[r], engines[r], "Completo" if engines[r] != "failed" else "Falló"] for r in ROLE_TITLES]]
    header_style = ParagraphStyle("TableHeader", parent=styles["BrandBody"], fontName="Helvetica-Bold", textColor=colors.white)
    summary_data = [[Paragraph(escape(pdf_safe(str(cell))), header_style if idx == 0 else styles["BrandBody"]) for cell in row] for idx, row in enumerate(rows)]
    summary = Table(summary_data, colWidths=[3.3*inch, 2.5*inch, 1.2*inch], repeatRows=1)
    summary.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), PALETTE["forest"]), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("BACKGROUND", (0,1), (-1,-1), PALETTE["paper"]), ("GRID", (0,0), (-1,-1), 0.4, PALETTE["line"]), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7)]))
    backtest_scope = (
        "Alcance: revisión cualitativa y backtest exploratorio preregistrado; no se validó ningún edge."
        if backtest_result.get("backtests_run") else
        "Alcance: revisión cualitativa; no se leyeron precios, no se ejecutaron backtests y no se validó ningún edge."
    )
    story.extend([summary, Spacer(1, 10), Paragraph(escape(pdf_safe(backtest_scope)), styles["BrandBody"])])
    story.append(Paragraph("Estado del backtest exploratorio", styles["BrandHeading"]))
    story.append(Paragraph(escape(pdf_safe(str(backtest_result.get("status", "NOT_RUN")))), styles["BrandBody"]))
    if backtest_result.get("data_quality"):
        data = backtest_result["data_quality"]
        story.append(Paragraph(escape(pdf_safe(
            f"Dataset: {data['dataset_path']} · cobertura contra calendario preregistrado: {data['coverage_pct']:.3f}% · "
            f"filas: {data['valid_rows']}/{data['expected_observations']}"
        )), styles["BrandBody"]))
    for period, metrics in backtest_result.get("periods", {}).items():
        stressed = backtest_result.get("periods_2x_cost", {}).get(period, {})
        story.append(Paragraph(escape(pdf_safe(
            f"{period}: {metrics['trades']} operaciones; media neta {metrics['mean_net_pct']:.4f}%; "
            f"media neta a 2x costo {stressed.get('mean_net_pct', 0):.4f}%"
        )), styles["BrandBody"]))
    for role, title in ROLE_TITLES.items():
        story.append(Paragraph(escape(title), styles["BrandHeading"]))
        text = outputs[role]
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                story.append(Spacer(1, 3))
                continue
            if line.startswith("#"):
                line = re.sub(r"^#+\s*", "", line)
                story.append(Paragraph(escape(pdf_safe(line)), styles["BrandHeading"]))
            elif line.startswith(("- ", "* ")):
                story.append(Paragraph("- " + escape(pdf_safe(line[2:])), styles["BrandBody"]))
            else:
                story.append(Paragraph(escape(pdf_safe(line)), styles["BrandBody"]))
    story.extend([Spacer(1, 10), Paragraph("El backtest exploratorio sirve para comprobar la implementación y descartar; no constituye evidencia confirmatoria. Gates confirmatorias de estadística, robustez y costos siguen pendientes. Ver Markdown y JSON adjunto para fuentes completas y trazabilidad.", styles["BrandBody"])])
    doc.build(story)


def main() -> None:
    args = parse_args()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    outputs, engines = load_roles(args.report_dir)
    hypotheses = hypothesis_paths(args.family_dir)
    backtest_summary_path = args.report_dir / "backtests" / "summary.json"
    backtest_result = json.loads(backtest_summary_path.read_text(encoding="utf-8")) if backtest_summary_path.is_file() else {
        "status": "NOT_RUN", "backtests_run": False,
        "report_markdown": "No se recibió artefacto de ejecución del backtest.",
    }
    backtest_markdown_path = args.report_dir / "backtests" / "summary.md"
    if backtest_markdown_path.is_file():
        backtest_result["report_markdown"] = backtest_markdown_path.read_text(encoding="utf-8")
    md = report_markdown(args.family, args.run_date, outputs, engines, args.family_dir, hypotheses, backtest_result)
    (args.report_dir / "report.md").write_text(md, encoding="utf-8")
    (args.report_dir / "tree.svg").write_text(tree_svg(args.family, args.family_dir, hypotheses), encoding="utf-8")
    structured = {
        "family": args.family,
        "run_date_utc": args.run_date,
        "status": "qualitative_complete" if all(x != "failed" for x in engines.values()) else "partial_failure",
        "engines": engines,
        "model_primary": "gpt-6-luna",
        "reasoning_effort": "high",
        "hypotheses": [str(path.relative_to(args.family_dir)) for path in hypotheses],
        "data": {
            "market_data_read": bool(backtest_result.get("backtests_run")),
            "coverage_pct": backtest_result.get("data_quality", {}).get("coverage_pct", "unknown"),
            "gaps": "see backtest artifact" if backtest_result.get("backtests_run") else "not measured",
            "feed_comparison": "see preregistration" if backtest_result.get("backtests_run") else "pending",
        },
        "backtests_run": bool(backtest_result.get("backtests_run")),
        "backtest_result": backtest_result,
        "exploratory_backtest_gate": {
            "status": backtest_gate_status(outputs["backtest_gate"]),
            "report_role": "agentes/backtest_gate.md",
            "executes_backtest": backtests_run,
        },
        "gates": {"data_quality": "pending", "statistics_oos": "pending", "robustness": "pending", "costs": "pending", "edge_verdict": "not confirmed"},
        "source_policy": "Evidence sources must predate 2018; unverifiable citations remain explicitly marked.",
    }
    (args.report_dir / "report.yaml").write_text(json.dumps(structured, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pdf_report(args.report_dir / "report.pdf", args.family, args.run_date, md, outputs, engines, backtest_result)
    print(f"Built report bundle: {args.report_dir}")


if __name__ == "__main__":
    main()
