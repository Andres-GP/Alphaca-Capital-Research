# Informe inicial · Overnight Gaps · 2026-11-20

**Estado de la corrida:** revisión cualitativa completa.  
**Motores por rol:** literatura: codex/gpt-6-luna/high (ChatGPT OAuth), datos: codex/gpt-6-luna/high (ChatGPT OAuth), red_team: codex/gpt-6-luna/high (ChatGPT OAuth).  
**Alcance:** investigación cualitativa y revisión documental; esta corrida no leyó precios ni ejecutó backtests.

## Resumen ejecutivo

Este informe organiza revisión de literatura, diagnóstico de datos y crítica independiente. No presenta rentabilidades medidas ni declara un edge validado. La cobertura y los huecos de datos siguen desconocidos hasta calcularlos contra un calendario de sesiones verificado; las gates estadísticas, de robustez y costos siguen pendientes.

## Árbol de investigación

![Árbol de familia, pauta, mercado e hipótesis](tree.svg)

## Hipótesis existentes

- `overnight_index_premium/us_equity_etf/hypothesis.md` — veredicto: pendiente de datos y gates.

## Gates

| Gate | Estado |
|---|---|
| Calidad/cobertura de datos | Pendiente; no recalculada en esta corrida |
| Estadística fuera de muestra | Pendiente; sin backtest |
| Robustez | Pendiente; sin backtest |
| Costos/spreads/swaps | Pendiente; sin backtest |
| Aprobación de edge | No confirmado |

## Literatura y mecanismo económico

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Literatura y mecanismo · Gaps y transiciones de sesión

**Corte:** estudios publicados antes del 1 de enero de 2018. **Estado:** síntesis bibliográfica; no se analizaron datos locales ni se probaron estrategias.

## Mecanismo

Un retorno close-to-open puede reflejar noticias y órdenes que se acumulan mientras una sesión regular está cerrada y se incorporan al precio cuando vuelve a negociarse. En acciones y ETF, la subasta o las primeras operaciones también pueden producir precios de apertura distintos de los precios posteriores. Esa diferencia puede deberse a formación de precios, liquidez o atención de inversores; por sí sola no demuestra una anomalía explotable.

Conviene mantener separadas tres preguntas:

- **Prima overnight incondicional:** cómo se compara el retorno close-to-open con el open-to-close.
- **Reversión condicional:** si, dado el tamaño y signo de un gap ya observado, el precio se mueve después hacia el cierre anterior.
- **Rentabilidad ejecutable:** si una regla que entra después de conocer el gap obtiene resultados netos de spread, slippage y demás costos.

Un resultado sobre una no responde automáticamente a las otras. Además, “cierre” y “apertura” dependen del mercado y del feed. En futuros casi continuos, FX y CFD, las sesiones pueden incluir negociación nocturna, pausas, rollovers y horarios propios del proveedor; sus gaps no son necesariamente comparables con aperturas de acciones.

## Predicciones falsables

1. **Componentes del retorno:** para un instrumento, calendario y fuente predefinidos, medir close-to-open y open-to-close por separado. La prima overnight propuesta predice una diferencia sistemática entre ambos tramos. Se falsaría si no aparece en periodos fuera de muestra o depende de una convención particular de cierre o apertura.

2. **Reversión tras el gap:** definir el gap con precios y timestamps fijados de antemano; luego medir el retorno desde un fill posterior a la observación del gap. La hipótesis de reversión predice que gaps de cierta magnitud o signo anticipan un movimiento posterior hacia el cierre anterior. Debe probarse aparte de la prima overnight y con umbrales fijados antes de evaluar resultados.

3. **Precio negociable:** simular entrada y salida con cotizaciones bid/ask y una regla temporal realizable. Si la pauta desaparece al incluir el spread de apertura, slippage o latencia, los datos no respaldan una estrategia ejecutable bajo esos supuestos.

4. **Efecto de sesión:** comparar aperturas regulares, lunes o reaperturas tras feriados, y pausas o rollovers solo cuando esas categorías y sus calendarios estén definidos antes del análisis. No agrupar automáticamente eventos con duraciones y mecanismos distintos.

## Trabajos académicos

- **Wood, Robert A.; Thomas H. McInish; J. Keith Ord (1985).** “An Investigation of Transactions Data for NYSE Stocks”. *The Journal of Finance*, 40(3), 723–739. Con datos transaccionales de NYSE, encuentran diferencias en las distribuciones de retornos entre overnight, primeros 30 minutos, cierre y resto del día, con retornos y desviaciones estándar inusualmente altos al principio y al final de la sesión. El estudio motiva separar esos tramos y considerar microestructura; no prueba una regla de gap-fill. [DOI / Wiley](https://doi.org/10.1111/j.1540-6261.1985.tb04996.x)

- **Lockwood, Larry J.; Scott C. Linn (1990).** “An Examination of Stock Market Return Volatility During Overnight and Intraday Periods, 1964–1989”. *The Journal of Finance*, 45(2), 591–601. En su muestra de retornos horarios del mercado, reportan volatilidad intradía significativamente mayor que la overnight, con variación a lo largo de la sesión. Es evidencia sobre perfiles de riesgo históricos, no sobre retorno esperado positivo o reversión. [DOI / Wiley](https://doi.org/10.1111/j.1540-6261.1990.tb03705.x)

- **Harris, Lawrence (1986).** “A Transaction Data Study of Weekly and Intradaily Patterns in Stock Returns”. *Journal of Financial Economics*, 16(1), 99–117. Encuentra que, para empresas grandes de su muestra, los retornos negativos de lunes se acumularon entre el cierre del viernes y la apertura del lunes; para empresas pequeñas, principalmente durante la sesión del lunes. Esto motiva separar fines de semana de noches ordinarias, pero no establece un mecanismo universal ni una oportunidad actual. [DOI / Elsevier](https://doi.org/10.1016/0304-405X(86)90044-9)

- **Berkman, Henk; Paul D. Koch; Laura Tuttle; Ying Jenny Zhang (2012).** “Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open”. *Journal of Financial and Quantitative Analysis*, 47(4), 715–741. En acciones de EE. UU., reportan retornos overnight positivos seguidos de reversión intradía, concentrados en títulos de alta atención; también encuentran costos implícitos relevantes para comprar cerca de la apertura. Proponen una explicación vinculada a atención minorista y acciones difíciles de valorar o arbitrar. La evidencia no implica que cualquier gap revierta ni que el efecto se transfiera a otros instrumentos. [DOI / Cambridge](https://doi.org/10.1017/S0022109012000270)

- **Kelly, Michael A.; Steven P. Clark (2011).** “Returns in Trading versus Non-Trading Hours: The Difference Is Day and Night”. *Journal of Asset Management*, 12(2), 132–145. Comparan retornos dentro y fuera del horario regular en ETF amplios y reportan diferencias en medidas ajustadas por riesgo; para QQQQ en 1999–2006, informan primas de riesgo close-to-open y open-to-close de +23,7 % y −23,3 %, respectivamente, según su construcción. El resultado depende de su muestra y método; no valida un gap-fill ni un precio de apertura alcanzable en otros datos. [DOI / Springer](https://doi.org/10.1057/jam.2011.2)

- **Liu, Qingfu; Yiuman Tse (2017).** “Overnight Returns of Stock Indexes: Evidence from ETFs and Futures”. *International Review of Economics & Finance*, 48, 440–451. Para 1999–2014, reportan retornos overnight significativamente positivos en ETF de índices de EE. UU. y la mayoría de los futuros internacionales estudiados, junto con mayor volatilidad diurna; en los mercados estadounidenses, encuentran relaciones predictivas distintas para los primeros y últimos 30 minutos. Esos resultados no equivalen a un fill de apertura ni a una señal general de gap-fill. [DOI / Elsevier](https://doi.org/10.1016/j.iref.2017.01.005)

## Límites de inferencia y preguntas abiertas

Los estudios citados se refieren a muestras históricas de acciones, ETF o futuros con definiciones y estructuras de mercado concretas. No establecen que el mismo patrón persista hoy, que sea causalmente atribuible a un solo mecanismo o que se reproduzca en los símbolos y feeds del repositorio. Un retorno estimado con precios de apertura puede no ser capturable si la señal solo se conoce una vez fijado ese precio.

Siguen abiertas, para cada instrumento candidato, estas preguntas:

- ¿Qué venue, sesión, calendario, timezone y fuente definen el cierre y la apertura?
- ¿La comparación usa precios de transacción, subasta, barras o cotizaciones ejecutables? ¿Cómo se mide el spread en la apertura?
- ¿La prima close-to-open persiste en una réplica con datos actuales y ventanas fuera de muestra?
- ¿La reversión condicional existe después de un fill alcanzable, neta de costos?
- ¿Cambian los resultados en fines de semana, feriados, pausas de mantenimiento o rollovers?
- ¿Se trata de una apertura de acciones/ETF, de una transición de sesión en futuros o de una convención de horario del broker?

Para los datos locales, la cobertura, zona horaria, sesiones y precios ejecutables siguen sin verificarse; no hay evidencia aquí de un edge propio ni de una prueba de gap-fill.

## Evidencia empírica y datos

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Informe de evidencia y datos · gaps y transiciones de sesión

**Fecha UTC:** 2026-11-20  
**Rol:** evidencia empírica y datos  
**Estado general:** `data_pending`. El inventario permite identificar candidatos y algunas rutas de carga, pero no demuestra cobertura por sesión ni precios ejecutables. No se analizaron archivos de mercado ni se calcularon porcentajes de cobertura en esta corrida.

## Alcance y estado de verificación

Distingo entre **datos descritos en el repositorio** —rutas, nombres, manifiestos y código EDA— y **datos verificados en esta corrida**. Revisé documentación de auditoría y código fuente de las notebooks, sin abrir ni recorrer CSV de mercado. No consulté MongoDB, credenciales ni fuentes remotas.

La auditoría local registra 528 CSV encontrados por ruta y nombre, pero advierte que el inventario no verifica de forma uniforme proveedor, instrumento, zona horaria, calendario ni continuidad. Sus fechas nominales y recuentos de huecos de archivo no equivalen a cobertura de sesiones: falta definir primero las observaciones esperadas según el calendario pertinente. En esta corrida no verifiqué la existencia actual ni el contenido de cada serie.

## Evaluación por instrumento

| Instrumento candidato | Datos descritos en el repositorio | Evaluación actual | Fuente prioritaria y cierre mínimo |
|---|---|---|---|
| **QQQ, ETF de EE. UU.** | La notebook EDA carga datos diarios de QQQ con `yfinance`, desde `1999-01-01`, usando `auto_adjust=True`. La auditoría no identifica una serie local de QQQ con procedencia confirmada. | La serie diaria ajustada puede servir para análisis exploratorio de retornos, pero no verifica precios sin ajustar, quotes ni fills de apertura. No se puede dar por validado el tramo close-to-open para ejecución. Cobertura y huecos por sesión: **desconocidos**. | Priorizar export histórico de broker/venue con precios ejecutables y metadatos de descarga. Conservar por separado OHLC sin ajustar, ajustes corporativos y retornos totales; definir calendario regular de NYSE/Nasdaq, zona IANA y reglas de apertura/cierre. Contrastar con una serie de referencia documentada. |
| **ES y NQ, futuros de índices** | Las notebooks cargan `es_15min` y `nq_15min` de MongoDB y usan Yahoo (`ES=F`, `NQ=F`) para comparación. El código asigna sesiones con `SESSION_START_HOUR = 18`. | La conexión de Mongo es una interfaz descrita en código, no evidencia verificada aquí de proveedor, contrato o cobertura de las colecciones. La hora 18:00 es una convención de la notebook; no confirma timezone ni sesión oficial. Yahoo es referencia comparativa, no feed de fills. Cobertura y huecos por contrato/sesión: **desconocidos**. | Priorizar ticks o barras bid/ask del broker o exchange, contratos individuales y metadatos de origen. Fijar si el evento es apertura cash, pausa electrónica, settlement o rollover. Validar calendario CME, DST, feriados, pausas, roll y reglas de empalme antes de calcular retornos. |
| **WTIFS / USOIL, CFD de energía** | Se describen CSV locales bajo `data/axi/` y la notebook WTIFS lee archivos Axi etiquetados como H1. | La ruta/nombre apunta a Axi, pero no verifica export, especificación del CFD ni convención horaria del servidor. Una etiqueta H1 no prueba que la apertura o cierre de interés sea ejecutable. Cobertura y huecos de sesión: **desconocidos**. | Priorizar ticks o barras bid/ask del mismo broker y símbolo contractual. Documentar horario del servidor, DST, cierres semanales, mantenimiento, rollover, spread variable, swaps y relación —si se usa— con el futuro subyacente. Mantener separados gaps del CFD y del futuro. |
| **USDJPY, FX/CFD** | Se describe un archivo local de Axi en M5 y una notebook que lo carga para análisis. La auditoría también enumera una serie etiquetada Darwinex, pero no acredita procedencia ni equivalencia. | Los nombres no demuestran timezone ni calendario. No asumir que la hora nominal del archivo es UTC. Axi y Darwinex no deben combinarse como una serie continua. Cobertura y huecos de reapertura: **desconocidos**. | Para una estrategia de Axi, priorizar Axi; para una de Darwinex, priorizar Darwinex. Registrar horas del servidor y calendario de cada broker, cotizaciones bid/ask, pausa diaria, rollover, spread y financiación. Usar Dukascopy solo como control externo etiquetado, no como sustituto de ejecución. |
| **BTCUSD, CFD y referencia externa** | Se describen un CSV H1 etiquetado Axi y otra serie H1 etiquetada Dukascopy; la notebook BTCUSD usa la ruta Axi. | Los nombres indican fuentes distintas, no feeds compatibles. El horario y los precios de un CFD pueden diferir de la referencia externa aunque ambos cubran BTCUSD. Un resultado que los empalme sin reconciliación debe marcarse **`NO CONFIRMADO`**. Cobertura y diferencias por evento: **desconocidas**. | Priorizar el broker usado para ejecutar. Comparar con Dukascopy solo en periodos y timestamps coincidentes; reportar diferencias de horario, OHLC, huecos y spread por feed. No rellenar huecos ni extender una serie con la otra. |
| **BTCJPY** | El inventario describe una serie Axi con inicio nominal en 2019; hay una notebook EDA asociada. | El inicio del nombre no verifica continuidad, sesiones ni timezone. No se debe inferir cobertura 24/7 solo por tratarse de cripto. Cobertura y huecos: **desconocidos**. | Validar el feed Axi y sus pausas/calendario, con timestamps originales y bid/ask si están disponibles. Analizarlo por separado de BTCUSD y de cualquier referencia de otro proveedor. |

## Riesgos de datos que afectan la hipótesis

- **Definición de gap:** el close previo y la apertura siguiente deben pertenecer al mismo instrumento, fuente y convención de sesión. Para ETF, distinguir subasta/apertura regular de primera transacción; para futuros, distinguir sesión electrónica, horario cash, settlement y rollover; para CFDs, usar los límites publicados por el broker.
- **Timezone y DST:** conservar timestamp fuente y normalizar a UTC sin perder el original. Asociar cada observación con un calendario histórico y offsets de broker/venue. Las reglas de sesión escritas en EDA no validan estos metadatos.
- **Huecos y cierres especiales:** medir observaciones esperadas y presentes por sesión. Separar fin de semana, feriados, sesiones cortas, pausa diaria, mantenimiento, rollover y huecos inesperados del feed. Un gap de archivo de varios días no revela por sí solo si faltan cotizaciones esperadas.
- **Precio ejecutable y coste:** OHLC o mid no acreditan fills. Se requieren bid/ask alrededor de entrada y salida, spread de apertura, latencia/slippage, comisiones y, según producto, swap o financiación. Ajustes por dividendos y splits sirven para retornos totales, pero no reemplazan precios de ejecución.
- **Diferencias entre feeds:** Axi, Darwinex, Dukascopy, Yahoo y Mongo no se deben tratar como intercambiables. Toda comparación debe conservar fuente, periodo y cortes; si la conclusión depende de una serie empalmada o de huecos completados con otro feed, marcar **`NO CONFIRMADO`**.

## Plan mínimo reproducible para cerrar los pendientes

1. **Congelar la pregunta y la serie.** Registrar instrumento, venue o broker, símbolo/contrato, definición matemática del gap, precios y timestamps que lo forman, horizonte y regla de entrada/salida. Mantener la prima overnight incondicional separada de la reversión condicional.
2. **Fijar fuente y calendario antes del análisis.** Registrar proveedor, export/API, frecuencia, timezone original, calendario histórico, zona IANA, DST, feriados y sesiones cortas. Guardar fecha de extracción y ajustes aplicados.
3. **Auditar integridad por sesión.** Comparar timestamps observados con los esperados para esa fuente y calendario; informar denominador, cobertura calculada, duplicados y huecos con sus causas o estado desconocido. No rellenar ni interpolar.
4. **Validar eventos y ejecución.** Cotejar cierres/aperturas contra la fuente de referencia pertinente y confirmar entradas/salidas con datos bid/ask del feed de ejecución. Documentar spread, slippage, comisiones y financiación aplicables.
5. **Comparar feeds sin empalmarlos.** Donde exista referencia secundaria, medir diferencias en intervalos comunes y presentar resultados por feed. No sustituir datos ausentes de forma silenciosa.
6. **Entregar evidencia trazable.** Adjuntar manifiesto por serie, calendario utilizado, reporte de cobertura/huecos, muestras de timestamps auditados, comparación con referencia y definición de coste. Con eso puede construirse un notebook descriptivo y reproducible; todavía no implica aprobar una estrategia.

## Evidencia requerida para pasar a notebook de estrategia

Para el candidato ETF, primero hacen falta precios adecuados para separar close-to-open y open-to-close, y datos de ejecución para no atribuir a la estrategia el movimiento anterior al fill. Para futuros y productos OTC hacen falta la fuente primaria, sus sesiones históricas y reglas de contrato/broker identificadas. En todos los casos se necesita cobertura calculada frente al calendario definido, tratamiento explícito de huecos y costes observables o conservadoramente especificados.

Según el handoff, el paso posterior exige aplicar los gates comunes: cobertura mínima de 98%, objetivo de al menos 100 eventos/trades independientes —si no, dejar pendiente por potencia—, control FDR `q <= 0.05`, límite inferior del IC bootstrap del 95% de la métrica neta primaria mayor que cero, resultado agregado positivo y en al menos dos de tres ventanas OOS, al menos 70% de parámetros vecinos positivos y rentabilidad bajo estrés de costos de 2× spread/comisión. Son criterios de revisión, no evidencia disponible ni garantía de potencia.

**Veredicto de datos:** los candidatos están descritos, pero no hay evidencia en esta corrida para asignar cobertura o continuidad a ningún instrumento, ni para certificar precios de apertura/fills. La ficha QQQ y las pruebas de gaps permanecen `data_pending`; no hay base para declarar edge ni para descartar uno por ausencia de efecto.

## Crítica independiente / red team

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Red team · Prima overnight en ETF de acciones de EE. UU.

**Estado de la revisión:** crítica de diseño; no se analizaron datos ni se ejecutaron pruebas. **Veredicto:** `pendiente` (`data_pending`). La ficha plantea una pregunta investigable, pero todavía no fija una regla de ejecución y una métrica primaria que permitan decidirla sin ambigüedad.

## Evaluación de la predicción y los gates

La ficha separa correctamente la prima close-to-open del gap-fill condicional y advierte que QQQ no es equivalente a QQQQ ni a los mercados de otros instrumentos del repositorio. También identifica la necesidad de distinguir retornos ajustados de precios ejecutables.

La predicción sigue siendo demasiado amplia para una prueba confirmatoria: «difiere» no fija qué diferencia debe observarse, y «expectativa neta positiva» no determina qué posición produce esa expectativa. Especificar si la estrategia mantiene QQQ desde un cierre hasta la apertura siguiente, cuál es el comparador y cómo se mide el ajuste por riesgo. Fijar además una métrica primaria; el retorno bruto de cada tramo puede describirse, pero no sustituye una regla neta ejecutable.

Los gates comunes están referenciados, pero aún no se traducen a un protocolo para esta ficha. Faltan el universo y la fecha de congelación, la partición cronológica, la métrica primaria, los costos y fills, y la grilla de parámetros vecinos. Por tanto, no se puede evaluar todavía si se cumplen los gates ni si las decisiones analíticas se tomarán antes de observar los resultados.

## Objeciones y pruebas de refutación

| Severidad | Objeción | Prueba que podría refutarla |
|---|---|---|
| **Bloqueante** | **Regla y métrica primaria incompletas.** La comparación close-to-open/open-to-close no especifica qué operación se evalúa ni cómo se define «ajustado por riesgo». Elegir entre retorno medio, Sharpe u otra métrica después de mirar los resultados permitiría selección retrospectiva. | Antes de acceder a los resultados, registrar instrumento, dirección, entrada/salida, benchmark, métrica primaria y tratamiento del riesgo. Ejecutar el análisis con esa especificación congelada y conservar los análisis secundarios como exploratorios. |
| **Bloqueante** | **Datos ejecutables y cobertura sin verificar.** La referencia a `yfinance` y a precios con `auto_adjust=True` no valida cobertura ni precios alcanzables. Esos precios pueden servir para análisis de retornos totales, pero no bastan para simular fills. | Auditar calendario y sesiones esperados, faltantes, timestamps, ajustes y distribución de QQQ. Exigir cobertura ≥98% sin rellenar huecos; cotejar precios de referencia con quotes o fills del broker/venue y documentar discrepancias. |
| **Bloqueante** | **Riesgo de atribuir al trade el retorno anterior a una señal observable.** Si la estrategia compra después de conocer la apertura, no puede capturar el tramo cierre-apertura. Una compra programada en el cierre y venta en la apertura es otra estrategia y requiere definir sus órdenes y fills. | Comparar por separado (a) la estadística descriptiva close-to-open y (b) el P&L de una regla ejecutable, especificando cuándo se envían las órdenes y modelando los fills de subasta o las primeras cotizaciones disponibles. No asignar al trade el movimiento que ocurrió antes de su entrada. |
| **Alta** | **Precio de cierre/apertura y fills de subasta.** El cierre diario y la apertura pueden representar subastas, últimas transacciones o primeras barras, con spreads y slippage diferentes. Un OHLC ajustado no prueba que la estrategia obtuviera esos precios. | Fijar la definición de cada precio y calcular el P&L con precios de ejecución disponibles, costos observados y sensibilidad a spreads/slippage. Comparar con la serie diaria solo como referencia estadística. |
| **Alta** | **Dividendos, distribuciones y ajustes corporativos.** Mezclar retornos totales ajustados con fills de precios no ajustados puede mover retornos entre tramos o distorsionar la comparación alrededor de fechas ex-dividendo. | Mantener series separadas: retornos totales para medir rendimiento de inversión y precios/quotes ejecutables para simular órdenes. Auditar fechas ex-dividendo, splits y factores de ajuste. |
| **Alta** | **Snooping y contaminación del holdout.** La ficha deja abierto «QQQ u otro ETF». Probar varios ETF, periodos, definiciones y métricas, y luego conservar el que mejor funcione, invalida un holdout si esas decisiones se toman con sus resultados. | Congelar activo, fechas, especificación y número de ensayos antes del análisis. Mantener un holdout cronológico intacto; contabilizar ensayos y aplicar FDR con `q <= 0.05` si se evalúa una familia de hipótesis. |
| **Alta** | **Dependencia temporal y episodios concentrados.** Los retornos diarios pueden agruparse en episodios de volatilidad o noticias; tratar cada día como independiente puede estrechar indebidamente los intervalos. | Usar bootstrap por bloques que preserve dependencia temporal. Informar contribución por ventanas y episodios, además del resultado agregado y de la distribución de retornos. |
| **Media** | **Tamaño efectivo de muestra y potencia.** Cien observaciones diarias no equivalen necesariamente a cien eventos independientes ni garantizan potencia para detectar una prima pequeña. | Registrar el número de sesiones y episodios independientes, estimar potencia para una magnitud económicamente relevante y mantener `pendiente` si la muestra no permite una conclusión informativa. |
| **Media** | **Comparación entre tramos potencialmente engañosa.** Close-to-open y open-to-close difieren en duración, exposición, volatilidad y costos. Una diferencia de Sharpe o retorno no identifica por sí misma una anomalía ni una ventaja explotable. | Reportar retornos y riesgo por tramo con definiciones consistentes; evaluar la estrategia con exposición, costos y benchmark predefinidos. Interpretar cualquier diferencia como descriptiva hasta que la prueba neta fuera de muestra la respalde. |
| **Media** | **Selección del ETF y supervivencia, si se amplía el universo.** La ficha no fija todavía si probará solo QQQ o un conjunto de ETF. Elegir retrospectivamente ETF existentes o exitosos puede sesgar el resultado. | Si se amplía el universo, fijarlo con criterios ex ante e incluir fondos que hayan cerrado o cambiado de composición cuando corresponda. Ajustar por comparaciones múltiples y no elegir el universo según desempeño. |

## Fallos bloqueantes

Antes de pasar de `data_pending` a una prueba confirmatoria faltan, como mínimo:

1. Una regla de posición explícita —por ejemplo, mantener desde cierre hasta apertura— y un benchmark definido.
2. Una métrica primaria y un protocolo que distinga la descomposición estadística de retornos del P&L ejecutable.
3. Metadatos de fuente, calendario, timestamps y cobertura; datos adecuados para estimar fills y costos.
4. Fechas, ventanas OOS y universo de ensayos congelados antes de consultar resultados.

## Mejoras para la ficha

Registrar por anticipado si el activo será QQQ, cómo se tratarán días festivos y sesiones cortas, y cómo se contabilizarán distribuciones y costos. Definir una grilla limitada de parámetros vecinos para el gate de robustez, sin ampliar cortes u horarios tras ver el holdout.

Para la evaluación empírica, aplicar los gates comunes: cobertura ≥98%, muestra suficiente —con limitaciones de potencia documentadas si no alcanza 100 eventos independientes—, control de comparaciones múltiples, métrica primaria neta con límite inferior del IC bootstrap del 95% mayor que cero fuera de muestra, resultado positivo agregado y en al menos 2 de 3 ventanas OOS, ≥70% de vecinos predefinidos positivos y costos estresados. El gate de fuente primaria exige replicar con datos del broker/venue; un resultado que dependa de datos rellenados o alternativos queda `NO CONFIRMADO`.

## Veredicto

**`pendiente` (`data_pending`).** La hipótesis es falsable en principio y la separación respecto del gap-fill está bien planteada, pero la regla ejecutable, la métrica primaria y los datos de fills no están especificados o verificados. No hay evidencia local que permita declarar un edge ni descartarlo. Con el protocolo congelado y datos que superen los gates, la ficha podría pasar a notebook de estrategia.

## Datos, cobertura y pendientes

No se leyeron CSV de mercado en esta corrida. El origen, la cobertura porcentual y los huecos deben verificarse por dataset usando la prioridad broker → Dukascopy para CFDs y una fuente licenciada/apropiada para ETFs. No interpolar ni empalmar series sin registrarlo. Si una conclusión requiere datos rellenados o feeds empalmados, marcarla `NO CONFIRMADO`.

## Control de calidad

Cualquier fuente citada debe ser anterior a 2018 y contener DOI o URL estable. Las referencias que no pudieron verificarse deben aparecer explícitamente como `no verificada`; no son evidencia de apoyo hasta revisión humana.
