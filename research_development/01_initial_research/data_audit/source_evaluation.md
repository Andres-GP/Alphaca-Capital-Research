# Evaluación de fuentes gratuitas

Fecha de consulta: 2026-11-20. Esta revisión compara fuentes para obtener series históricas utilizables en investigación; no supone que exista una fuente gratuita con derechos de redistribución o uso comercial.

## ETFs de EE. UU.

| Fuente | Evidencia de acceso/cobertura | Evaluación |
|---|---|---|
| Yahoo Finance | La ayuda oficial indica que la descarga CSV de históricos requiere Yahoo Finance Gold; la página de QQQ muestra precios históricos. [Ayuda de descarga](https://help.yahoo.com/kb/finance-app-for-ios/download-historical-data-yahoo-finance-sln2311.html) · [QQQ histórico](https://finance.yahoo.com/quote/QQQ/history/) | La navegación permite inspección; no se considera una descarga gratuita garantizada. Los CSV locales de QQQ con origen tipo Yahoo son provisionales hasta registrar método de adquisición, fechas, ajustes y términos aplicables. |
| Alpha Vantage | Su API documenta la serie diaria y un límite de 25 solicitudes gratuitas por día. La respuesta `compact` ofrece 100 observaciones; `full` ofrece más de 25 años, pero la documentación reserva `full` para claves premium en la serie diaria. [Documentación](https://www.alphavantage.co/documentation/) · [Límites](https://www.alphavantage.co/support/api-key/) | No satisface gratuitamente una necesidad de backfill diario largo según la documentación consultada. No se tomó como fuente aprobada. |
| Datos oficiales de broker | Cumplen la prioridad de fuente indicada por el proceso si el broker ofrece el ETF y su historial requerido. | Preferidos para la prueba; comprobar disponibilidad, ajustes por distribuciones, sesiones y licencia por instrumento. |

**Decisión:** no se ha verificado una fuente adicional gratuita que garantice a la vez cobertura histórica suficiente, ajustes apropiados y términos adecuados para ETFs. Mantener los datos locales como provisionales y dejar pendientes las pruebas que necesiten historial no disponible. No interpolar ni tratar la serie tipo Yahoo como fuente confirmada. Si se habilita una fuente licenciada o se obtiene exportación del broker, registrar metadatos antes de usarla.

## Darwinex y Dukascopy

Dukascopy ya aparece en los datos locales y la fase prioriza usarlo para complementar CFDs anteriores a 2018. Para Darwinex, Dukascopy es una fuente alternativa gratuita que puede ayudar a ampliar fechas, pero no replica el feed de ejecución Darwinex: pueden diferir zona horaria, sesiones, bid/ask, spreads, swaps, rollover y reglas de CFD. Por tanto, los resultados basados en Dukascopy sirven como comprobación externa y no sustituyen la confirmación en Darwinex.

No se aprueba aquí otro proveedor gratuito adicional: el inventario no demuestra que cubra los instrumentos, granularidades y años requeridos ni que permita una comparación consistente. La selección queda pendiente de la ficha de datos por instrumento y de la verificación de cobertura. Nunca empalmar feeds sin identificar el corte y repetir las gates en cada feed.

## Qué falta para cerrar la auditoría

1. Para cada instrumento: exportar/identificar el historial del broker prioritario y calcular cobertura contra su calendario.
2. Medir huecos y diferencias de feed; registrar la metodología y el período esperado.
3. Verificar acceso y términos de cada proveedor antes de guardar o distribuir datos.
4. Actualizar `local_datasets.csv` o crear metadatos por serie con resultados observados. Hasta entonces, cobertura y huecos siguen desconocidos.
