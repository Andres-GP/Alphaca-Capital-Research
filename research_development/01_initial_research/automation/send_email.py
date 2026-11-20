#!/usr/bin/env python3
"""Send the final research run summary with inline-styled HTML over SMTP."""

from __future__ import annotations

import html
import json
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path


RECIPIENT = "andresgarciapedreros@gmail.com"
REPO = "Andres-GP/Alphaca-Capital-Research"


def main() -> int:
    summary_path = Path(os.environ["RUN_SUMMARY_JSON"])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    run_date = summary["date"]
    family_rows = summary.get("families", [])
    pr_url = os.environ.get("PULL_REQUEST_URL", "")
    publish_status = os.environ.get("PUBLISH_STATUS", "unknown")
    family_ok = all(row.get("status") == "qualitative_complete" for row in family_rows)
    run_ok = family_ok and publish_status == "success"
    subject = f"{'ÉXITO' if run_ok else 'FALLO'} · Initial Research · {run_date}"
    branch = f"research/{run_date}"

    plain_rows = []
    html_rows = []
    for row in family_rows:
        family = row.get("family", "desconocida")
        status = row.get("status", "unknown")
        engines = row.get("engines", {})
        engine_text = "; ".join(f"{role}: {engine}" for role, engine in engines.items()) or "sin datos de motor"
        failures = ", ".join(row.get("failures", [])) or "ninguno"
        report_url = f"https://github.com/{REPO}/blob/{branch}/{row['report_path']}" if row.get("report_path") else "sin reporte disponible"
        plain_rows.append(f"- {family}: {status}; motores: {engine_text}; fallos: {failures}; reporte: {report_url}")
        html_rows.append(
            "<tr>"
            f"<td style=\"padding:12px;border-bottom:1px solid #dce4de;color:#202725\">{html.escape(family.replace('_', ' ').title())}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #dce4de;color:#202725\">{html.escape(status)}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #dce4de;color:#202725\">{html.escape(engine_text)}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #dce4de;color:#202725\">{html.escape(failures)}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #dce4de\"><a style=\"color:#1f3d36\" href=\"{html.escape(report_url, quote=True)}\">Abrir reporte</a></td>"
            "</tr>"
        )

    pr_link = f'<a style="color:#1f3d36" href="{html.escape(pr_url, quote=True)}">Abrir PR</a>' if pr_url else "No se creó un PR."
    html_body = f"""<!doctype html>
<html lang="es"><body style="margin:0;padding:24px;background:#eef2ef;font-family:Arial,Helvetica,sans-serif;color:#202725">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:760px;margin:0 auto;background:#ffffff;border-collapse:collapse">
    <tr><td style="padding:28px 32px;background:#1f3d36;color:#f4f7f3">
      <div style="font-size:12px;letter-spacing:2px;color:#c8f5a8">ALPHACA CAPITAL · RESEARCH</div>
      <h1 style="margin:12px 0 0;font-size:24px;line-height:1.25">{html.escape(subject)}</h1>
    </td></tr>
    <tr><td style="padding:24px 32px">
      <p style="margin:0 0 10px;line-height:1.55">Corrida cualitativa de Initial Research para el {html.escape(run_date)}. Modelo principal: <strong>GPT-6 Luna</strong>, esfuerzo <strong>high</strong>. Fallback configurado: <strong>Gemini 3.8 Flash</strong> (thinking high) vía Gemini API.</p>
      <p style="margin:0 0 20px;line-height:1.55">Rama prevista: <code>{html.escape(branch)}</code>. Publicación: {pr_link}.</p>
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse">
        <thead><tr style="background:#f1f5f1"><th align="left" style="padding:12px;color:#1f3d36">Familia</th><th align="left" style="padding:12px;color:#1f3d36">Estado</th><th align="left" style="padding:12px;color:#1f3d36">Motor por rol</th><th align="left" style="padding:12px;color:#1f3d36">Fallos</th><th align="left" style="padding:12px;color:#1f3d36">Reporte</th></tr></thead>
        <tbody>{''.join(html_rows)}</tbody>
      </table>
      <div style="margin-top:22px;padding:16px;background:#f7f8f5;border-left:4px solid #c8f5a8;line-height:1.55">
        <strong>Edges nuevos:</strong> ninguno validado en esta corrida; no se leyeron precios ni se ejecutaron backtests.<br>
        <strong>Casi-pasa:</strong> no aplica; gates estadísticas, robustez, costos y cobertura permanecen pendientes.<br>
        <strong>Publicación:</strong> {html.escape(publish_status)}.
      </div>
    </td></tr>
    <tr><td style="padding:18px 32px;background:#f7f8f5;color:#60706a;font-size:12px;line-height:1.5">Reporte preliminar de investigación. Hipótesis y referencias requieren revisión; ningún resultado de esta corrida es una aprobación para Research & Development.</td></tr>
  </table>
</body></html>"""

    plain_body = "\n".join([
        subject,
        f"Corrida cualitativa de Initial Research · {run_date}",
        "Modelo principal: gpt-6-luna; esfuerzo high. Fallback: gemini-3.8-flash (thinking high) vía Gemini API.",
        f"Rama: {branch}",
        f"PR: {pr_url or 'no disponible'}",
        *plain_rows,
        "Edges nuevos: ninguno validado; no se ejecutaron backtests.",
        "Casi-pasa: no aplica; gates pendientes.",
        f"Publicación: {publish_status}",
    ])
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USERNAME", "")
    message["To"] = RECIPIENT
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT") or "587")
    username = os.environ.get("SMTP_USERNAME", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    if not all([host, username, password, message["From"]]):
        print("SMTP configuration is incomplete (host, username, password, and sender are required).", file=sys.stderr)
        return 2
    tls_context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=tls_context, timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=tls_context)
            smtp.ehlo()
            smtp.login(username, password)
            smtp.send_message(message)
    print(f"Research run notification sent to {RECIPIENT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
