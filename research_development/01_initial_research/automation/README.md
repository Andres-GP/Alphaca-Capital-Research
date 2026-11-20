# Automatización de investigación

## Frecuencia y ejecución

`.github/workflows/initial-research.yml` corre lunes, miércoles y viernes a las 11:00 UTC (`0 11 * * 1,3,5`), además de permitir `workflow_dispatch`. En Colombia equivale a las 6:00 a. m. Los cinco jobs de familia se ejecutan en paralelo; el grupo de concurrencia del workflow impide que dos corridas simultáneas compitan por el estado de autenticación. Cada job mantiene sus propias credenciales temporales.

Cada familia produce tres revisiones de rol (literatura/mecanismo, datos/evidencia disponible y red team) con Codex CLI, una después de otra para evitar que varias sesiones renueven simultáneamente el mismo token OAuth. El modelo principal es `gpt-6-luna` con razonamiento `high`. Esto quedó validado en el smoke test manual, [run 44799888305](https://github.com/Andres-GP/Alphaca-Capital-Research/actions/runs/44799888305), que devolvió `AUTH_OK` y terminó correctamente.

## Autenticación y fallback

- `CODEX_AUTH_JSON`: secreto con `auth.json` completo de Codex ChatGPT. Solo se escribe en el runner, con permisos privados, y nunca se registra.
- `GEMINI_API_KEY`: clave de Google AI Studio para el fallback mediante Gemini API (`gemini-3.8-flash`, nivel de pensamiento `high`).
- Si una revisión falla con Codex, el script intenta esa revisión con Gemini API `gemini-3.8-flash` y nivel de pensamiento `high`. Si ambos motores fallan, el error queda en el reporte y la corrida se marca fallida.

El smoke test de Codex usa CLI directamente. La documentación actual de [`openai/codex-action`](https://github.com/openai/codex-action) requiere una API key (`OPENAI_API_KEY`) y no ofrece un input `CODEX_AUTH_JSON`; por ello no se usa el action para la autenticación de ChatGPT que sí pasó el smoke test. Modelo: [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). Fallback: la [Gemini API](https://ai.google.dev/gemini-api/docs/text-generation) con `GEMINI_API_KEY`.

El fallback utiliza directamente la Gemini API con la clave propia, su cuota y facturación; no usa Antigravity ni autenticación OAuth de Google.

## Reportes, rama y PR

Cada corrida guarda tres informes de rol y genera Markdown, JSON válido como YAML, SVG jerárquico y PDF en `reportes/<fecha>_<familia>/`. El job agregador reúne los artefactos, crea/actualiza una rama `research/<fecha>` y abre/actualiza un PR contra la rama por defecto. Solo añade rutas dentro de `research_development/01_initial_research/reportes/`; nunca escribe a la rama por defecto.

Las fichas existentes son contexto, no resultados nuevos. Los agentes no leen datos de mercado ni ejecutan backtests: cobertura, huecos y gates permanecen `unknown`/`pending`, y no se puede declarar un edge validado. Las fuentes externas nuevas deben tener URL/DOI comprobable anterior a 2018; si no se pueden verificar, se marcan como no verificadas.

## Aviso por correo

Al final de cada corrida se envía un resumen HTML con CSS en línea y tablas a `andresgarciapedreros@gmail.com`, aunque falle alguna familia. Secretos requeridos: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` y `SMTP_FROM`. Si falta alguno o SMTP rechaza el envío, el job lo reporta como fallo; el workflow no oculta una notificación fallida.

## Estado y límites

- Smoke test de Codex: aprobado el 2026-11-20.
- Frecuencia, matriz, aislamiento, fallback, informes, PR y correo: implementados en el workflow de producción.
- Gemini API y SMTP se ejecutan solo si el fallback se activa o al enviar el correo; no se han validado por una corrida real.
- Resultados de investigación: no son backtests ni una aprobación para `02_strategy_development`; siguen requiriendo datos, cobertura y gates.
