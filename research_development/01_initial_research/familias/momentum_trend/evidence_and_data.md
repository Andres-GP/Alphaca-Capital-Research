# Momentum / tendencia · evidencia empírica y datos

**Estado:** revisión bibliográfica inicial; no es backtest ni validación de un edge propio. Corte solicitado para evidencia: 2017-12-31. Cobertura de datasets del repo no verificada en esta revisión.

## Evidencia primaria anterior a 2018

| Fuente | Evidencia publicada | Qué informa para la hipótesis | Alcance y límites |
|---|---|---|---|
| Moskowitz, Ooi & Pedersen (2012), “Time Series Momentum”, *Journal of Financial Economics* 104(2), 228–250. [DOI](https://doi.org/10.1016/j.jfineco.2011.11.003) · [versión de autores, CBS](https://research-api.cbs.dk/ws/portalfiles/portal/58851003/time_series_momentum_lasse_heje.pdf) | Los autores reportan persistencia de retornos de 1 a 12 meses seguida de reversión parcial a horizontes mayores, en futuros de índices de acciones, divisas, commodities y bonos, en su universo de 58 instrumentos. | Da una motivación previa para probar continuación temporal en futuros y varios horizontes. El paper no demuestra que cada futuro actual (ES, NQ, 6E, 6J), feed, frecuencia intradía, CFD, ETF o cripto del repo tenga la misma señal neta de costos. | Resultados y universo dependen de sus datos, construcción y costos. No transferir coeficientes ni rentabilidad publicada al broker/feed local. |
| Hurst, Ooi & Pedersen (2017), “A Century of Evidence on Trend-Following Investing”, *The Journal of Portfolio Management* 44(1). [PDF de autores](https://fairmodel.econ.yale.edu/ec439/hurst.pdf) · [copia SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026) | Extiende el análisis de time-series momentum hasta 1880 mediante 67 mercados mensuales de cuatro clases de activos, combinando series históricas de varias fuentes. | Sugiere que la pregunta de persistencia de tendencias merece investigación multiactivo y por régimen. | Evidencia histórica agregada y mensual; parte de la serie larga usa fuentes construidas/transcritas y no representa ejecución moderna intradía, contratos específicos, feed de CFD o costos de cuenta. No equivale a una réplica independiente con los datos disponibles aquí. |

**Implicación de investigación:** ambas fuentes respaldan la plausibilidad de una pauta de seguimiento de tendencia en ciertas clases de activos y horizontes. No respaldan por sí solas un veredicto positivo para un instrumento o estrategia del repo. Conviene separar (1) time-series momentum, señal respecto del propio retorno pasado, de (2) cross-sectional momentum, ranking relativo entre activos; no asumir que son la misma hipótesis.

## Datos y cobertura observables en este repositorio

Inventario de nombres y referencias de código solamente. Los rangos de fechas de nombres de archivo no certifican continuidad, zona horaria, integridad ni cobertura porcentual.

| Mercado / candidato | Evidencia en repo | Origen identificable | Pendiente antes de usar |
|---|---|---|---|
| ES, NQ, 6E, 6J (futuros) | Las EDA antiguas cargan colecciones MongoDB `es_15min`, `nq_15min`, `6e_15min`, `6j_15min`; `.env.example` enumera tres URI de futuros. | La ruta de código confirma MongoDB como mecanismo de carga; el broker, proveedor y contenido real de cada colección no están identificados en estos archivos. | Consultar metadatos/colección con acceso autorizado; identificar feed/broker, fechas, símbolos de contrato, rollover, sesiones, timezone, huecos, bid/ask y costos. **Cobertura: desconocida.** |
| WTIFS (CFD petróleo) | Archivo local `research_development/data/axi/wtifs_H1_200802180000_202611021900.csv`; notebook EDA de WTIFS busca CSV locales de Axi. | Etiquetado como Axi en nombre/ruta de proyecto; eso no demuestra que todos los precios sean un extracto íntegro del broker ni su convención de rollover. | Validar cabecera, observaciones, huecos, horario, cotización, swaps/rollover y comparación con MT5 original. Inicio nominal anterior a 2018; cobertura real **desconocida**. |
| BTCUSD (CFD) | Archivo local `research_development/data/axi/BTCUSD_H1_201401150200_202611022200.csv`; notebook EDA identifica exportación MT5 de Axi. | Etiquetado Axi/MT5 en ruta y notebook. | Comprobar días faltantes, zona horaria, continuidad, especificación histórica del contrato y swaps/spread. Aunque el nombre cubre nominalmente fechas anteriores a 2018, porcentaje real **desconocido**. |
| BTCJPY (CFD) | Archivo local `research_development/data/axi/btcjpy_H1_201910010000_202611022200.csv`; existe además `btcjpy_h1_utc.csv`. | Etiquetado como Axi en EDA/ruta. | La fecha nominal de esta exportación comienza en 2019; **no cubre el periodo pre-2018** por nombre. Revisar el segundo archivo y sus metadatos antes de concluir cobertura. |
| QQQ (ETF) | Existe `QQQ_EDA.ipynb`; no se confirmó aquí un archivo local de precios ni proveedor en el contenido fuente. | Desconocido. | Determinar fuente exacta, ajustes por splits/dividendos, cobertura y licencia; validar contra broker/mercado de ejecución. No inferir proveedor o cobertura a partir del ticker ni del nombre de notebook. |
| Dukascopy (fallback) | El repo contiene `research_development/utils/download_dukascopy.py` y un archivo `data/dukascopy/btcusd_h1_utc.csv`; el downloader declara BID. | La página oficial describe exportación histórica de varios instrumentos financieros y granularidades desde tick hasta mensual. [Dukascopy Historical Data Export](https://www.dukascopy.com/swiss/english/marketwatch/historical/) | Confirmar si cada instrumento y fecha está disponible en el export actual, granularidad, huecos, timezone, precisión, volumen y licencias/uso. BID no sustituye bid/ask ni es el feed del broker; datos de relleno deben llevar `NO CONFIRMADO` si son los únicos que hacen pasar una hipótesis. |

La guía oficial actual de Axi indica que el History Center de MT4/MT5 ofrece “hasta 12 meses” para la mayoría de timeframes. [Axi: descarga de datos históricos](https://help.axi.com/en-US/axiv2--axicorp-prod/article/k_1LMcCI-how-do-i-download-historical-trade-data). Por tanto, esa interfaz no puede asumirse como fuente suficiente para un estudio pre-2018; investigar si existe otro archivo de cuenta/broker con cobertura histórica y documentar evidencia de origen. La limitación publicada es “para la mayoría” de timeframes y no prueba el estado de cada cuenta o exportación histórica del repo.

## Preguntas de datos antes de proponer una prueba

1. **Primario:** ¿qué broker/venue y símbolo exactos originaron ES/NQ/6E/6J y qué historial pre-2018 está realmente disponible? La conexión Mongo no es metadato de procedencia.
2. **Rollover y contratos:** ¿series continuas o contratos individuales? Registrar regla de empalme y no permitir ajustes retrospectivos que creen momentum artificial.
3. **Retornos:** definir close-to-close/settlement y unidades; incorporar multiplicador y cambios de contrato.
4. **Sesiones y reloj:** guardar timestamp del proveedor y normalización UTC; identificar calendario, DST y barras ausentes.
5. **Ejecución/costos:** buscar bid/ask o spread histórico, comisión, slippage y funding/swaps por instrumento y lado.
6. **Cripto/CFD:** tratar horas 24/7, especificación del CFD, financiación nocturna y cambios de horario del broker por separado de futuros listados.
7. **ETF:** usar series ajustadas solo para retornos de inversión total y precios no ajustados para modelar fills; registrar fuente y política de corporate actions.

## Pruebas sugeridas (no ejecutadas)

- Empezar con predicción de time-series momentum definida a priori, mensual/semanal según fuente disponible; medir primero sobre el broker/feed objetivo y contrastar con benchmark simple.
- Para futuros, separar universo por clase y evitar elegir instrumentos según su desempeño observado; declarar regla de rollover antes del cómputo.
- Mantener señales, ventanas y métricas preregistradas. Reportar resultados por instrumento, por periodo y agregados con exposición/riesgo comparable.
- No usar CFD/ETF/crypto para rellenar huecos de futuros y llamar a eso réplica del mismo instrumento. Comparar feeds es un análisis de sensibilidad aparte.

## Incertidumbres explícitas

- No se inspeccionaron valores, credenciales, colecciones Mongo ni contenido completo de datasets. No se calcula cobertura ni se confirma disponibilidad histórica efectiva.
- La fuente de QQQ queda **no identificada**; no atribuirla a Yahoo Finance hasta verificar el notebook y los datos utilizados.
- Ningún edge propio fue probado; no hay resultados, gates aprobados ni casi-pasa.
- La evidencia citada es bibliográfica y motiva la pregunta, no sustituye la investigación pre-2018 por pauta/mercado ni los gates automáticos del proceso.
