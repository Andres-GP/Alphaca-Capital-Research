# Evaluación de fuentes gratuitas

Fecha de consulta: 2026-11-20. Esta revisión compara fuentes para obtener series históricas utilizables en investigación; no supone que exista una fuente gratuita con derechos de redistribución o uso comercial.

## ETFs de EE. UU.

| Fuente | Evidencia de acceso/cobertura | Evaluación |
|---|---|---|
| Yahoo Finance | El cliente de descarga `yfinance` permite solicitar barras diarias y acciones corporativas; la página de QQQ muestra históricos. [Ayuda de descarga](https://help.yahoo.com/kb/finance-app-for-ios/download-historical-data-yahoo-finance-sln2311.html) · [QQQ histórico](https://finance.yahoo.com/quote/QQQ/history/) | Se usa solo para exploración D1, con ticker candidato derivado del símbolo MT5 y coincidencia marcada como no verificada. No se supone disponibilidad, estabilidad ni licencia comercial; Darwinex debe validar la serie y el instrumento exactos. |
| Alpha Vantage | Su API documenta la serie diaria y un límite de 25 solicitudes gratuitas por día. La respuesta `compact` ofrece 100 observaciones; `full` ofrece más de 25 años, pero la documentación reserva `full` para claves premium en la serie diaria. [Documentación](https://www.alphavantage.co/documentation/) · [Límites](https://www.alphavantage.co/support/api-key/) | No satisface gratuitamente una necesidad de backfill diario largo según la documentación consultada. No se tomó como fuente aprobada. |
| Datos oficiales de broker | Cumplen la prioridad de fuente indicada por el proceso si el broker ofrece el ETF y su historial requerido. | Preferidos para la prueba; comprobar disponibilidad, ajustes por distribuciones, sesiones y licencia por instrumento. |
| Alpaca Market Data API | API oficial de histórico de barras, operaciones y cotizaciones para acciones; admite feeds distintos. El feed SIP consolida mercados de EE. UU.; IEX representa una sola bolsa y no el mercado consolidado. [Históricos](https://docs.alpaca.markets/us/docs/historical-api) · [feeds](https://docs.alpaca.markets/us/docs/market-data-faq) | Candidato automatizable para backfill y contraste de ETFs estadounidenses, sujeto a confirmar símbolo, plan/feed y términos. Para research de ejecución, no tratar IEX como sustituto de SIP/NBBO. |
| Darwinex Historical Tick Data | Acceso FTP autenticado para clientes con cuenta real; la lista pública incluye FX, índices, commodities y otros instrumentos, pero no demuestra disponibilidad de los ETFs concretos de esta investigación. [Acceso y lista](https://www.darwinex.com/algorithmic-trading/tick-data) | Buena opción de contraste para activos listados en su feed. Confirmar en la cuenta el símbolo exacto; no asumir que su FTP cubre ETFs cash. El historial MT5 del broker puede requerir terminal activo para automatizarse. |

**Decisión:** el pipeline usa Yahoo D1 únicamente para dar contexto exploratorio a ETFs encontrados en el catálogo MT5 de Darwinex. El símbolo/ticker no se considera confirmado por similitud de nombre. Para cada candidato que avance, repetir cobertura, ajustes, calendario y backtest con Darwinex. Alpaca u otro proveedor no se añade: no hace falta ampliar la infraestructura hasta observar una carencia concreta de cobertura.

## Darwinex y Dukascopy

Dukascopy se actualiza con `dukascopy-python` usando el mismo método `dp.fetch` que el descargador que ya existe en `research_development/utils/download_dukascopy.py`. El pipeline solo toma coincidencias únicas del catálogo de instrumentos, en BID, M15 y H1. Puede ampliar exploración en CFD/FX que cubra, pero no replica el feed del broker de ejecución: pueden diferir zona horaria, sesiones, bid/ask, spreads, swaps, rollover y reglas de CFD. Por tanto, resultados de Dukascopy son hipótesis externas y deben repetirse con datos del broker.

Axi documenta descarga de históricos desde MetaTrader 4/5. [Histórico Axi](https://help.axi.com/en-US/axiv2--axicorp-prod/article/k_1LMcCI-how-do-i-download-historical-trade-data). La automatización propuesta se conecta al terminal MT5 autenticado en un runner Windows persistente y registra la cobertura realmente devuelta por cuenta y símbolo.

La descarga de Yahoo y Dukascopy ya está integrada como exploración secundaria; la cobertura real y los términos aplicables deben verificarse por instrumento y período. No empalmar feeds sin identificar el corte y repetir las gates en cada feed.

## Qué falta para cerrar la auditoría

1. Habilitar el runner Windows, las rutas MT5 y credenciales de lectura en GitHub Actions.
2. Revisar catálogos, conteos, errores y períodos observados en los resúmenes JSON de `RESEARCH_DATA_DIR`.
3. Medir huecos contra el calendario específico y comparar diferencias entre feeds para cada instrumento candidato.
4. Verificar acceso y términos de cada proveedor antes de distribuir datos o usarlos fuera del research privado.
