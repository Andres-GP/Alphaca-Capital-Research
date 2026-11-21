# Evaluación de fuentes gratuitas

Fecha de consulta: 2026-11-20. Esta revisión compara fuentes para obtener series históricas utilizables en investigación; no supone que exista una fuente gratuita con derechos de redistribución o uso comercial.

## ETFs de EE. UU.

| Fuente | Evidencia de acceso/cobertura | Evaluación |
|---|---|---|
| Yahoo Finance | La ayuda oficial indica que la descarga CSV de históricos requiere Yahoo Finance Gold; la página de QQQ muestra precios históricos. [Ayuda de descarga](https://help.yahoo.com/kb/finance-app-for-ios/download-historical-data-yahoo-finance-sln2311.html) · [QQQ histórico](https://finance.yahoo.com/quote/QQQ/history/) | La navegación permite inspección; no se considera una descarga gratuita garantizada. Los CSV locales de QQQ con origen tipo Yahoo son provisionales hasta registrar método de adquisición, fechas, ajustes y términos aplicables. |
| Alpha Vantage | Su API documenta la serie diaria y un límite de 25 solicitudes gratuitas por día. La respuesta `compact` ofrece 100 observaciones; `full` ofrece más de 25 años, pero la documentación reserva `full` para claves premium en la serie diaria. [Documentación](https://www.alphavantage.co/documentation/) · [Límites](https://www.alphavantage.co/support/api-key/) | No satisface gratuitamente una necesidad de backfill diario largo según la documentación consultada. No se tomó como fuente aprobada. |
| Datos oficiales de broker | Cumplen la prioridad de fuente indicada por el proceso si el broker ofrece el ETF y su historial requerido. | Preferidos para la prueba; comprobar disponibilidad, ajustes por distribuciones, sesiones y licencia por instrumento. |
| Alpaca Market Data API | API oficial de histórico de barras, operaciones y cotizaciones para acciones; admite feeds distintos. El feed SIP consolida mercados de EE. UU.; IEX representa una sola bolsa y no el mercado consolidado. [Históricos](https://docs.alpaca.markets/us/docs/historical-api) · [feeds](https://docs.alpaca.markets/us/docs/market-data-faq) | Candidato automatizable para backfill y contraste de ETFs estadounidenses, sujeto a confirmar símbolo, plan/feed y términos. Para research de ejecución, no tratar IEX como sustituto de SIP/NBBO. |
| Darwinex Historical Tick Data | Acceso FTP autenticado para clientes con cuenta real; la lista pública incluye FX, índices, commodities y otros instrumentos, pero no demuestra disponibilidad de los ETFs concretos de esta investigación. [Acceso y lista](https://www.darwinex.com/algorithmic-trading/tick-data) | Buena opción de contraste para activos listados en su feed. Confirmar en la cuenta el símbolo exacto; no asumir que su FTP cubre ETFs cash. El historial MT5 del broker puede requerir terminal activo para automatizarse. |

**Decisión:** Alpaca SIP es el candidato de API más directo para ampliar automáticamente históricos de ETF de EE. UU.; su IEX gratuito no es un feed consolidado y no debe pasar como equivalencia. Darwinex debe confirmar disponibilidad exacta de los ETFs y su acceso por API/FTP. No comprar ni activar un plan sin autorización; por ahora no hay feed de ETF automatizado aprobado. Mantener los CSV locales como provisionales. No interpolar ni tratar la serie tipo Yahoo como fuente confirmada.

## Darwinex y Dukascopy

Dukascopy publica un exportador histórico con tick y barras hasta mensual, y una guía para acceso a sus archivos históricos en S3. [Exportador histórico](https://www.dukascopy.com/swiss/english/marketwatch/historical/) · [guía de datos](https://wiki.dukascopy.com/en/development/data-export/). Puede ampliar exploración en CFDs que cubra, pero no replica el feed del broker de ejecución: pueden diferir zona horaria, sesiones, bid/ask, spreads, swaps, rollover y reglas de CFD. Por tanto, resultados de Dukascopy son una hipótesis externa y deben repetirse con datos del broker.

Axi documenta descarga de históricos desde MetaTrader 4/5, con límite habitual de hasta 12 meses en la mayoría de temporalidades. [Histórico Axi](https://help.axi.com/en-US/axiv2--axicorp-prod/article/k_1LMcCI-how-do-i-download-historical-trade-data). El acceso manual desde un terminal no equivale a una API que GitHub Actions pueda consultar: para automatizarlo directamente hará falta un terminal MT5 autenticado en un runner Windows persistente u otra vía oficialmente soportada.

No se aprueba aquí otro proveedor gratuito adicional: el inventario no demuestra que cubra los instrumentos, granularidades y años requeridos ni que permita una comparación consistente. La selección queda pendiente de la ficha de datos por instrumento y de la verificación de cobertura. Nunca empalmar feeds sin identificar el corte y repetir las gates en cada feed.

## Qué falta para cerrar la auditoría

1. Para cada instrumento: exportar/identificar el historial del broker prioritario y calcular cobertura contra su calendario.
2. Medir huecos y diferencias de feed; registrar la metodología y el período esperado.
3. Verificar acceso y términos de cada proveedor antes de guardar o distribuir datos.
4. Actualizar `local_datasets.csv` o crear metadatos por serie con resultados observados. Hasta entonces, cobertura y huecos siguen desconocidos.
