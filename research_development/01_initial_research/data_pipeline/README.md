# Descarga privada de históricos y fuentes exploratorias

El pipeline mantiene datos fuera de Git, en el disco persistente del VPS Windows. GitHub Actions se conecta a los terminales MT5 de Axi y Darwinex, descubre los símbolos negociables y actualiza CSV con metadatos JSON. El screening cubre todas las temporalidades MT5 habilitadas por el adaptador: M1, M5, M15, M30, H1, H4, D1, W1 y MN1. El límite de 16 series MT5 por corrida evita sobrecargar el runner; el resumen informa qué series quedan pendientes.

Los CSV de MT5 contienen OHLC, volumen y spread reportado por barra; **no son ticks históricos ni reconstruyen bid/ask ejecutable**. Cada broker, fuente, símbolo y marco queda en una serie separada.

## Activación

1. En el VPS Windows, instala los terminales MT5 de Axi y Darwinex y confirma que puedes iniciar sesión y ver los símbolos/históricos que necesitas.
2. Registra un runner de GitHub Actions para este repositorio como servicio, con la etiqueta adicional `mt5-research`. No ejecutes jobs desde ramas no confiables en ese runner.
3. Configura GitHub **Variables**:
   - `MARKET_DATA_AUTOMATION_ENABLED=true`
   - `RESEARCH_RUNNER_LABEL=mt5-research`
   - `RESEARCH_DATA_DIR=D:\AlphacaResearchData` (carpeta persistente, fuera del checkout)
   - `AXI_MT5_PATH` y `DARWINEX_MT5_PATH` con rutas a los ejecutables `terminal64.exe`.
4. Configura estos GitHub **Secrets**:
   - `AXI_MT5_LOGIN`, `AXI_MT5_PASSWORD`, `AXI_MT5_SERVER`
   - `DARWINEX_MT5_LOGIN`, `DARWINEX_MT5_PASSWORD`, `DARWINEX_MT5_SERVER`
5. `market_data_universe.yaml` está configurado para descubrir todos los símbolos negociables de ambas cuentas y cubrir las nueve temporalidades habilitadas desde la fecha indicada. MT5-disabled y símbolos personalizados quedan excluidos. Revisa los catálogos JSON y el resumen de descarga en `RESEARCH_DATA_DIR` después de la primera corrida.
6. En cada corrida, el proceso actualiza las series de broker y busca símbolos ETF de Darwinex para explorarlos con Yahoo Finance en D1. La coincidencia del ticker Yahoo es heurística y queda marcada como no verificada; Darwinex sigue siendo el feed requerido para validar una hipótesis ETF.
7. El proceso usa `dukascopy-python` con el mismo mecanismo que `research_development/utils/download_dukascopy.py` para los instrumentos CFD/FX que tengan una coincidencia exacta y no ambigua. Mantiene BID separado del broker y registra los símbolos sin coincidencia.
8. Ejecuta `Initial Research` manualmente para la primera descarga. Los runs programados lunes, miércoles y viernes actualizan datos antes del panel de research.

Las rutas y logins se usan como configuración de Actions; las contraseñas solo como secrets. Si MT5 ofrece una contraseña de inversor/solo lectura, úsala para la extracción. No pongas credenciales en YAML, CSV, notebooks, logs ni en el brief. Las credenciales no se guardan en los metadatos descargados. Limita el runner a los workflows de este repositorio y deja el VPS conectado; si está fuera de línea, la corrida queda en cola.

## Límites de datos

- La serie mantiene separado cada broker, símbolo y marco temporal. Nunca empalma Axi, Darwinex y un feed externo bajo el mismo ID.
- MetaTrader reporta barras y spread en puntos por barra; no son cotizaciones históricas tick a tick. Estrategias intrabarra, de gaps de apertura o sensibles al spread necesitan ticks/quotes y un motor compatible antes de backtest.
- Solo los motores implementados y preregistrados pueden ejecutarse. Descargar más datos no convierte por sí solo un resultado exploratorio en un edge.
- El primer backfill depende del rango que el servidor MT5 entregue y de la configuración de historial del terminal. La cobertura contra el calendario esperado seguirá siendo una gate obligatoria.
- Dukascopy es una fuente BID secundaria de exploración; no aporta spreads del broker, swaps, rollover ni fills de Axi/Darwinex. La disponibilidad de símbolos y cobertura depende de su catálogo público.
- Yahoo solo aporta contexto histórico exploratorio para ETFs. Los ajustes corporativos y la sesión pueden diferir del CFD/listado de Darwinex; no mezclar ni presentar esa serie como precio ejecutable.
- El descubrimiento cubre todos los símbolos que MT5 marque como negociables, pero la descarga avanza por lotes de 16 series MT5 por corrida. `catalog/latest_refresh_summary.json`, `catalog/dukascopy_refresh_summary.json` y `catalog/yahoo_etf_refresh_summary.json` guardan backlog, fallos y cobertura de cada corrida. La cantidad de datos disponibles varía por cuenta, símbolo y marco.
- El panel no backtestea automáticamente todas las familias/símbolos/temporalidades. Solo ejecuta motores implementados y experimentos con preregistro congelado que superen las gates deterministas.
