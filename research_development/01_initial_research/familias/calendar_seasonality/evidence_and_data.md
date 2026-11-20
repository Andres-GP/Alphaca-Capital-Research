# Estacionalidad y calendario · evidencia y datos

**Estado:** revisión de literatura y del inventario visible del repo; no es un backtest ni valida una pauta propia. **Corte de literatura:** 2017-12-31. No se calculó cobertura efectiva.

## Evidencia empírica primaria anterior a 2018

| Fuente | Hallazgo reportado | Relevancia y límites |
|---|---|---|
| French (1980), “Stock Returns and the Weekend Effect”, *Journal of Financial Economics* 8(1), 55–69. [ScienceDirect / DOI](https://doi.org/10.1016/0304-405X(80)90021-5) | Evalúa retornos de acciones de EE. UU. y compara hipótesis de tiempo de calendario con tiempo de negociación; el resumen editorial describe retornos de lunes inferiores a otros días. | Motiva formular una hipótesis de día-de-semana en acciones. Es evidencia de la muestra histórica del paper, no de los instrumentos, feeds o reglas actuales de Alphaca. Las explicaciones basadas en días calendario vs días de negociación deben probarse de forma explícita. |
| Keim (1983), “Size-Related Anomalies and Stock Return Seasonality: Further Empirical Evidence”, *Journal of Financial Economics* 12(1), 13–32. [PDF del autor / referencia y DOI](https://doi.org/10.1016/0304-405X(83)90025-9) | Estudia estacionalidad de los retornos de acciones en relación con el efecto tamaño y la concentración temporal de retornos. | Advierte que un patrón de calendario puede estar mezclado con tamaño/composición del universo. No prueba un efecto homogéneo en índices, ETFs, futuros, FX, CFDs o cripto. |
| Lakonishok y Smidt (1988), “Are Seasonal Anomalies Real? A Ninety-Year Perspective”, *Review of Financial Studies* 1(4), 403–425. [Oxford Academic / DOI](https://doi.org/10.1093/rfs/1.4.403) | Reevalúa varias anomalías estacionales en una historia extensa del Dow Jones, distinguiendo distintas pautas de calendario. | Motiva revisar estabilidad temporal y múltiples patrones; los resultados de un índice histórico no certifican una regla concreta ni su ejecución actual. |

Las referencias son evidencia previa que orienta preguntas. No implican resultados replicados localmente. Las anomalías de calendario conocidas son vulnerables a selección entre muchos días, ventanas, zonas horarias, universos y periodos; una ficha debe fijar estos elementos antes del test.

## Evidencia visible en el repositorio

- Las nueve notebooks en `research_development/01_exploratory_data_analysis/` cubren `WTIFS`, `6E`, `QQQ`, `USDJPY`, `ES`, `6J`, `NQ`, `BTCUSD` y `BTCJPY`. El nombre del notebook no identifica la procedencia histórica ni una hipótesis calendario ya comprobada.
- `research_development/utils/utils.py::plot_seasonality_detailed` calcula y grafica agrupaciones por día de semana, mes y, si hay datos intradía, hora. Es una utilidad descriptiva: no corrige pruebas múltiples, no establece causalidad y no representa por sí misma un backtest ejecutable.
- En EDA y utilidades aparecen series locales y cargas de datos por CSV/MongoDB/Dukascopy. Este inventario de rutas o código no certifica proveedor, rango continuo, sesiones observadas ni cobertura porcentual.

## Datos necesarios por tipo de hipótesis

| Pregunta de calendario | Datos mínimos y fuente prioritaria | Incertidumbres que deben registrarse |
|---|---|---|
| Día de semana / mes del año | OHLC o retornos diarios del broker/venue objetivo; calendario oficial y observaciones esperadas por sesión. Para acciones/ETF, datos con corporate actions y universo point-in-time si hay ranking transversal. | Origen, ajustes, días festivos, cierres extraordinarios, supervivencia, huecos, muestra por cada día/mes y cambios estructurales. |
| Fin de mes / fecha de pago / rollover | Timestamp y calendario de trading del instrumento, precios negociables y volumen; para futuros, contrato individual y regla de roll conocida en ese instante. | Qué significa “mes” según venue, festivos, month-end real frente a último día hábil, rollover, costos y fills disponibles. |
| Hora / sesión / apertura-cierre | Datos intradía del broker (idealmente bid/ask/ticks si se afirma una oportunidad ejecutable), timezone fuente, timezone IANA de conversión, horario de servidor, sesiones y calendario DST. | Barras perdidas, pausas, horario extendido, cambios del server UTC offset, DST, apertura/cierre y spreads condicionados a horario. No asignar buckets horarios antes de fijar y documentar la zona horaria. |
| Efecto pre/post festivo | Calendario oficial del venue con cierres y sesiones cortas, más precios y costos del mismo instrumento. | Festivos móviles, mercados globales con calendarios diferentes, anticipación y pocas observaciones independientes. |

La prioridad es el historial del broker específico del instrumento. Un proveedor gratuito o Dukascopy puede servir como contraste si cubre el instrumento; no se debe usar como sustituto silencioso del feed de ejecución. Un resultado que solo pasa con una serie sustituta o rellenada se marca `NO CONFIRMADO`.

## Riesgos de datos y controles antes de probar

1. Medir cobertura esperada por sesión y bucket horario; informar denominador, observaciones presentes y huecos, no solo total de barras.
2. Conservar timestamp original y convertir explícitamente; calcular día/mes/hora según la convención de mercado predefinida, considerando DST. No inferir la zona horaria por el patrón de velas.
3. Separar retorno de mercado de precio negociable; incluir spread, comisiones, slippage y swaps/funding aplicables, especialmente cerca de apertura, cierre y rollover.
4. Definir la predicción y familia completa de fechas/umbrales antes del análisis; aplicar corrección por comparaciones múltiples y validación cronológica.
5. No interpolar huecos. Si falta cobertura pre-2018, documentar el tramo y dejar la prueba pendiente en el handoff.

## Pendientes explícitos

- Por cada mercado del repo faltan origen verificado, timezone del proveedor, sesiones, calendario aplicado, porcentaje de cobertura y diferencias de feed.
- No se ejecutó prueba de día de semana, mes, hora, fin de mes o festivo en esta investigación.
- No se ha declarado edge, casi-pasa ni veredicto de calendario.
- Para cada hipótesis deben aplicarse los gates comunes de [`../../GATES.md`](../../GATES.md); sus umbrales no son resultados.
