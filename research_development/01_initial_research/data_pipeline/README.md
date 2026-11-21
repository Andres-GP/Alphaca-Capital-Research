# Descarga privada de históricos MT5

El conector mantiene barras de Axi y Darwinex fuera de Git, en el disco persistente del VPS Windows. GitHub Actions se conecta al terminal MT5 instalado allí, descarga de forma incremental los símbolos permitidos en `market_data_universe.yaml`, y actualiza CSV más metadatos JSON. Los CSV contienen OHLC, volumen y spread reportado por barra; **no son ticks históricos ni reconstruyen bid/ask ejecutable**.

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
5. En `market_data_universe.yaml`, anota solo los símbolos exactos de MetaTrader, las temporalidades necesarias y la fecha de inicio del backfill. El proceso no descarga todos los instrumentos automáticamente.
6. Ejecuta `Initial Research` manualmente para la primera descarga y confirma que los metadatos y cobertura reflejan tu cuenta. Después, los runs programados actualizarán el histórico antes del panel de research.

Las rutas y logins se usan como configuración de Actions; las contraseñas solo como secrets. Si MT5 ofrece una contraseña de inversor/solo lectura, úsala para la extracción. No pongas credenciales en YAML, CSV, notebooks, logs ni en el brief. Las credenciales no se guardan en los metadatos descargados. Limita el runner a los workflows de este repositorio y deja el VPS conectado; si está fuera de línea, la corrida queda en cola.

## Límites de datos

- La serie mantiene separado cada broker, símbolo y marco temporal. Nunca empalma Axi, Darwinex y un feed externo bajo el mismo ID.
- MetaTrader reporta barras y spread en puntos por barra; no son cotizaciones históricas tick a tick. Estrategias intrabarra, de gaps de apertura o sensibles al spread necesitan ticks/quotes y un motor compatible antes de backtest.
- Solo los motores implementados y preregistrados pueden ejecutarse. Descargar más datos no convierte por sí solo un resultado exploratorio en un edge.
- El primer backfill depende del rango que el servidor MT5 entregue y de la configuración de historial del terminal. La cobertura contra el calendario esperado seguirá siendo una gate obligatoria.
- Dukascopy publica un archivo histórico automatizable con política AWS Requester Pays. La transferencia se factura al descargador; no se habilita en Actions hasta definir instrumentos y aceptar ese costo. Darwinex FTP no se asume como feed de ETFs: hay que confirmar el símbolo en la oferta de la cuenta.
