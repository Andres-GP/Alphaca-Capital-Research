# Backtests exploratorios

Esta carpeta guarda pruebas iniciales reproducibles para hipótesis que pasaron Gate A en [`../GATES.md`](../GATES.md). El workflow ejecuta automáticamente solo preregistros congelados que coinciden exactamente con el ID autorizado por el gate y superan las validaciones deterministas de datos y costos.

## Flujo

1. Copiar `../templates/backtest_preregistration.yaml` a `preregistrations/<familia>/<id>.yaml`, completar y congelar una hipótesis específica.
2. Completar el contrato común de datos: proveedor/feed exactos, base de precio, zona horaria original, estado de licencia, hash SHA-256 del CSV y hash del calendario. Congelar también `expected_calendar_csv`, con una fila `timestamp_utc` por cada barra esperada entre `start_utc` y `end_utc`; debe generarse con el calendario de sesión de la venue/fuente seleccionada y quedar referenciado en `verification_evidence`. El runner compara timestamps observados con este calendario y bloquea cobertura menor de 98%, hashes distintos o timestamps inesperados.
3. Vincular la prueba a `research_brief.md`: registrar la pregunta/decisión que responde y congelar el hash SHA-256 del brief. Si cambia la necesidad, el preregistro queda obsoleto y debe congelarse de nuevo.
4. Obtener el veredicto `READY_FOR_EXPLORATORY_BACKTEST` en la revisión de viabilidad. La revisión sola no basta: el ejecutor verifica el estado congelado, el ID exacto, la pregunta de research congelada, proveedor/feed, hashes, método soportado, CSV, timestamps, precios, cobertura mínima y costos.
5. El motor `ohlc_directional_v1` simula señales univariadas de momentum de serie temporal o reversión de serie temporal: señal al cierre, entrada en apertura siguiente, salida tras el horizonte fijo, tamaño unitario, exposición corta/larga simétrica y sin posiciones solapadas. Aplica costo round-trip registrado y muestra sensibilidad a 2x costo. Otros tipos de señal quedan bloqueados hasta una implementación explícita; no se aproximan con otro método.
6. Cada corrida deja `summary.json`, `summary.md`, `trades.csv` y `experiment_manifest.json` en `reportes/<fecha>_<familia>/backtests/`. El manifiesto registra commit, versiones, run ID, hashes del preregistro/dataset/calendario/gate/brief/trades, motor, parámetros, contrato de datos, costos y resultados. Registra resultados nulos, fallos y resultados adversos igual que uno favorable. No cambiar reglas en la misma versión después de ver resultados.

Los ficheros pesados pueden residir fuera de Git: en Actions, montar/descargar la misma ruta relativa bajo `RESEARCH_DATA_DIR`. El preregistro sigue usando rutas relativas y los hashes congelados; el runner nunca acepta rutas absolutas ni rutas que escapen del directorio.

El backtest exploratorio permite revisar implementación y descartar. No basta para afirmar que hay un edge; eso requiere Gate C y una revisión posterior. Las fichas actuales están `data_pending` y no hay preregistros congelados, por lo que la primera corrida con este ejecutor debe saltarse sin leer precios.
