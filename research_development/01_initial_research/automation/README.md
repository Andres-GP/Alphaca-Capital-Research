# Automatización de investigación

## Smoke test de autenticación

`.github/workflows/research-auth-smoke.yml` es manual (`workflow_dispatch`) y ejecuta un prompt trivial sin escribir en el repositorio. Antes de lanzarlo, configura el secreto de GitHub Actions `CODEX_AUTH_JSON` con el contenido de un `auth.json` válido. El workflow lo escribe únicamente en el directorio temporal del runner, con permisos privados, y no registra su contenido.

El modelo solicitado es `gpt-6-luna` con esfuerzo `high`. El nombre exacto y ese nivel están documentados por OpenAI en el [catálogo del modelo](https://developers.openai.com/api/docs/models/gpt-6-luna). Un resultado correcto valida solo ese runner, autenticación y disponibilidad de modelo en ese momento; no implica que cuotas futuras estén disponibles.

## Límite de `openai/codex-action`

La documentación actual de [`openai/codex-action`](https://github.com/openai/codex-action) indica que requiere una API key del proveedor en GitHub Secrets y que expone `model`, `effort` y `codex-home`, pero no un input `CODEX_AUTH_JSON`. Por eso el smoke test usa el CLI directamente para probar el login de ChatGPT pedido. No se presenta como una validación de `codex-action`.

Antes de construir el workflow programado/matricial, resolver la autenticación soportada para el action: una API key de OpenAI mediante `OPENAI_API_KEY`, o continuar con Codex CLI y `CODEX_AUTH_JSON` si el smoke test confirma que el acceso ChatGPT funciona y se decide no usar el action. No guardar credenciales en el repositorio ni imprimirlas en logs.

## Fallback y cumplimiento

El nombre exacto del fallback documentado es `gemini-3.8-flash-high`; Antigravity CLI acepta `--effort high`. Ver [headless mode](https://antigravity.google/docs/cli/headless/). Se requiere decidir y provisionar una credencial válida de Google en GitHub Secrets; no está configurada desde este entorno.

No implementar rotación de cuentas con `ccswap`. Los términos de Antigravity prohíben el uso de software/servicios de terceros para acceder a Antigravity y citan herramientas de automatización con OAuth como ejemplo; la rotación para eludir cuotas tampoco es una ruta aceptable. Ver [términos de Google Antigravity](https://antigravity.google/terms). Para el fallback, usar una credencial autorizada de API, respetando su cuota y facturación.

## Estado

- Hecho: workflow manual de smoke test de Codex CLI; sin secretos en el repo.
- Pendiente: ejecutar el workflow con `CODEX_AUTH_JSON` en GitHub y registrar el resultado.
- Pendiente: elegir autenticación compatible con el runner/action, configurar secretos del motor principal y fallback, y validar Antigravity.
- Pendiente tras validaciones: crear cron `0 11 * * 1,3,5`, matriz por familia, concurrencia, rama `research/<fecha>`, PR y notificación de resultados.

El workflow de producción no se habilita hasta que las pruebas mínimas de autenticación funcionen. Ninguna corrida debe escribir a `main`.
