# Backtests exploratorios

Esta carpeta guarda pruebas iniciales reproducibles para hipótesis que pasaron Gate A en [`../GATES.md`](../GATES.md). El workflow ejecuta automáticamente solo preregistros congelados que coinciden exactamente con el ID autorizado por el gate y superan las validaciones deterministas de datos y costos.

## Flujo

1. Copiar `../templates/backtest_preregistration.yaml` a `preregistrations/<familia>/<id>.yaml`, completar y congelar una hipótesis específica.
2. Medir y registrar calidad/cobertura del dataset y las condiciones de ejecución. Congelar también `expected_calendar_csv`, con una fila `timestamp_utc` por cada barra esperada entre `start_utc` y `end_utc`; debe generarse con el calendario de sesión de la venue/fuente seleccionada y quedar referenciado en `verification_evidence`. El runner compara timestamps observados con este calendario y bloquea cobertura menor de 98% o timestamps inesperados. Con el inventario actual, los datos permanecen provisionales hasta completar esa revisión.
3. Obtener el veredicto `READY_FOR_EXPLORATORY_BACKTEST` en la revisión de viabilidad. La revisión sola no basta: el ejecutor verifica el estado congelado, el ID exacto, el método soportado, el CSV/ruta, timestamps, precios, cobertura mínima y costos registrados.
4. El motor `ohlc_directional_v1` simula señales univariadas de momentum de serie temporal o reversión de serie temporal: señal al cierre, entrada en apertura siguiente, salida tras el horizonte fijo, tamaño unitario, exposición corta/larga simétrica y sin posiciones solapadas. Aplica costo round-trip registrado y muestra sensibilidad a 2x costo. Otros tipos de señal quedan bloqueados hasta una implementación explícita; no se aproximan con otro método.
5. Cada corrida deja `summary.json`, `summary.md` y `trades.csv` en `reportes/<fecha>_<familia>/backtests/`. Registra resultados nulos, fallos y resultados adversos igual que uno favorable. No cambiar reglas en la misma versión después de ver resultados.

El backtest exploratorio permite revisar implementación y descartar. No basta para afirmar que hay un edge; eso requiere Gate C y una revisión posterior. Las fichas actuales están `data_pending` y no hay preregistros congelados, por lo que la primera corrida con este ejecutor debe saltarse sin leer precios.
