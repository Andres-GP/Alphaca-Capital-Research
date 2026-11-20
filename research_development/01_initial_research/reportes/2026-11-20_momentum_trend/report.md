# Informe inicial · Momentum Trend · 2026-11-20

**Estado de la corrida:** revisión cualitativa completa.  
**Motores por rol:** literatura: codex/gpt-6-luna/high (ChatGPT OAuth), datos: codex/gpt-6-luna/high (ChatGPT OAuth), red_team: codex/gpt-6-luna/high (ChatGPT OAuth).  
**Alcance:** investigación cualitativa y revisión documental; esta corrida no leyó precios ni ejecutó backtests.

## Resumen ejecutivo

Este informe organiza revisión de literatura, diagnóstico de datos y crítica independiente. No presenta rentabilidades medidas ni declara un edge validado. La cobertura y los huecos de datos siguen desconocidos hasta calcularlos contra un calendario de sesiones verificado; las gates estadísticas, de robustez y costos siguen pendientes.

## Árbol de investigación

![Árbol de familia, pauta, mercado e hipótesis](tree.svg)

## Hipótesis existentes

- `time_series_momentum/listed_futures/hypothesis.md` — veredicto: pendiente de datos y gates.

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

# Literatura y mecanismo · Momentum y tendencia

**Corte de literatura:** publicaciones hasta el 31-12-2017.  
**Estado para Alphaca:** revisión bibliográfica, no prueba empírica. No se han verificado aquí los contratos, la procedencia ni la cobertura de los datos locales; no hay resultados propios ni un edge confirmado.

## Mecanismo y distinciones

El **momentum de serie temporal (TSMOM)** toma una posición según el signo del retorno pasado del mismo activo. El **momentum transversal** compra activos que superaron a otros y vende los rezagados. Las dos pautas están relacionadas, pero no son intercambiables: difieren en la señal y en los datos necesarios para evaluarlas.

Una explicación posible para la continuación de plazo intermedio es la incorporación gradual de información o el ajuste escalonado de posiciones ante límites de riesgo y capital. En horizontes largos, la sobrerreacción, los cambios de régimen o la reversión podrían debilitar o invertir la pauta. La evidencia descrita abajo es compatible con algunos de estos mecanismos, pero no demuestra que sean la causa ni que apliquen a los instrumentos del proyecto.

## Trabajos académicos anteriores a 2018

- **Moskowitz, Tobias J.; Yao Hua Ooi; Lasse Heje Pedersen (2012), “Time Series Momentum”.** Estudian futuros de índices bursátiles, divisas, materias primas y bonos. Reportan persistencia de retornos entre uno y doce meses y reversión parcial en horizontes más largos en los instrumentos de su estudio. Es evidencia pertinente para formular una hipótesis de TSMOM en futuros; no confirma la pauta en un contrato, feed o estrategia local. [*Journal of Financial Economics*, 104(2), 228–250](https://doi.org/10.1016/j.jfineco.2011.11.003). citeturn0search0

- **Hurst, Brian; Yao Hua Ooi; Lasse Heje Pedersen (2017), “A Century of Evidence on Trend-Following Investing”.** Presentan un análisis histórico de seguimiento de tendencia en mercados globales desde 1880 con una base construida a partir de distintas fuentes. El resultado motiva estudiar la pauta en distintos periodos y clases de activos, pero la longitud histórica no garantiza series homogéneas ni precios directamente ejecutables en el mercado objetivo. [*The Journal of Portfolio Management*, 44(1), 15–29](https://doi.org/10.3905/jpm.2017.44.1.015). citeturn2search3

- **Brock, William; Josef Lakonishok; Blake LeBaron (1992), “Simple Technical Trading Rules and the Stochastic Properties of Stock Returns”.** Evalúan reglas de media móvil y ruptura de rango sobre el Dow Jones Industrial Average entre 1897 y 1986, comparándolas mediante bootstrap con varios modelos nulos. Sus resultados corresponden a esas reglas, índice y periodo; no establecen rentabilidad neta actual ni un mecanismo causal general. [*The Journal of Finance*, 47(5), 1731–1764](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x). citeturn0search1

- **Jegadeesh, Narasimhan; Sheridan Titman (1993), “Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency”.** Documentan retornos positivos para estrategias transversales de compra de ganadores y venta de perdedores con periodos de tenencia de 3 a 12 meses; parte del rendimiento anormal del primer año se disipa en los dos siguientes. Es evidencia sobre acciones y rankings relativos, no una prueba de TSMOM en futuros. [*The Journal of Finance*, 48(1), 65–91](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x). citeturn1search0

- **Hong, Harrison; Terence Lim; Jeremy C. Stein (2000), “Bad News Travels Slowly: Size, Analyst Coverage, and the Profitability of Momentum Strategies”.** En acciones, encuentran mayor rentabilidad de momentum entre empresas con menor cobertura de analistas, manteniendo constante el tamaño, y un efecto más marcado entre las acciones perdedoras. El hallazgo es consistente con difusión gradual de información específica; no demuestra ese mecanismo en futuros o CFDs. [*The Journal of Finance*, 55(1), 265–295](https://doi.org/10.1111/0022-1082.00206). citeturn2search0

- **Daniel, Kent; Tobias J. Moskowitz (2016), “Momentum Crashes”.** Documentan episodios de pérdidas infrecuentes y persistentes en estrategias de momentum y encuentran que aparecen asociados a estados de pánico, caídas previas del mercado, volatilidad elevada y rebotes. Es una cautela para medir pérdidas y dependencia del régimen; no permite anticipar el comportamiento de los instrumentos locales sin probarlo. [*Journal of Financial Economics*, 122(2), 221–247](https://doi.org/10.1016/j.jfineco.2015.12.002). citeturn1search12

## Predicciones falsables para una prueba posterior

Estas son preguntas de investigación, no resultados ni parámetros aprobados:

1. **Continuación TSMOM:** en contratos y venues definidos antes del análisis, ¿el signo del retorno total pasado de 12 meses predice retornos del mismo signo durante los siguientes 1–12 meses? Medir por separado cada horizonte, frente a un benchmark predefinido y antes y después de costos ejecutables.
2. **Continuación y reversión:** ¿la relación entre el retorno pasado y el futuro es positiva a horizontes intermedios y se debilita o invierte a horizontes mayores, dentro del mismo instrumento y feed?
3. **Mecanismo informativo:** si hay medidas comparables de flujo de información o restricciones de posicionamiento, ¿la predictibilidad es mayor donde la información se incorpora más lentamente o el ajuste de posiciones parece más escalonado? Si no se pueden medir esos factores, el mecanismo queda sin identificar.
4. **Régimen y pérdidas:** ¿las pérdidas se concentran en periodos de rebote, alta volatilidad o cambio de tendencia? Definir los regímenes de antemano y reportar también los episodios adversos.

## Límites de inferencia y preguntas abiertas

Los resultados publicados varían en mercado, periodo, frecuencia, definición de retorno y construcción de la cartera. La evidencia de acciones no confirma una pauta en futuros; la evidencia en futuros no confirma una pauta en CFDs, ETF, criptoactivos ni barras intradía. Una base histórica larga tampoco garantiza cobertura sin huecos o ejecución replicable.

Para evaluar la ficha local de TSMOM siguen abiertas preguntas esenciales: ¿qué contrato y venue representa cada símbolo?, ¿cuál es la fuente y cobertura efectiva del historial?, ¿cómo se definirá el retorno total y el rollover?, ¿qué precios y costos corresponden a una ejecución posible? También deben fijarse de antemano el universo, los horizontes, la métrica primaria y el periodo de validación, y tratar correctamente las ventanas solapadas, la dependencia temporal y la selección entre múltiples variantes.

Hasta resolver esas cuestiones y aplicar los gates del proyecto, la hipótesis permanece **no probada**.

## Evidencia empírica y datos

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Evidencia y datos · Momentum y tendencia

**Fecha de revisión:** 2026-11-20  
**Estado:** datos pendientes; no se verificó cobertura ni se ejecutaron pruebas de estrategia.  
**Alcance:** revisé documentación, inventario de archivos y código de carga. No abrí CSV de mercado, no consulté bases remotas y no calculé porcentajes de cobertura. Las fechas que aparecen en nombres de archivo son nominales, no fechas observadas.  
**Entrega:** devuelvo el informe aquí; la instrucción de este rol indica no escribir ni modificar archivos.

## Evaluación general

El repositorio describe varias fuentes posibles, pero no hay procedencia y cobertura verificadas para una prueba de momentum. La auditoría local registra 528 CSV por nombre y ruta; indica que no midió huecos ni cobertura, y que las etiquetas de origen son pistas, no confirmaciones. Las colecciones Mongo dependen de acceso remoto y quedan fuera de esa auditoría.

La ficha de time-series momentum en futuros listados debe permanecer en `data_pending`. Antes de una notebook hacen falta, como mínimo, el contrato y venue exactos, la fuente primaria, el calendario esperado, la regla de retorno y rollover, las marcas de tiempo y costos. Un resultado basado en feed alternativo o series empalmadas debe quedar como `NO CONFIRMADO`.

## Inventario descrito en el repositorio

| Instrumento o candidato | Lo que describe el repo | Lo que se verificó en esta corrida | Pendiente principal |
|---|---|---|---|
| **ES, NQ, 6E, 6J — futuros** | Los notebooks cargan `es_15min`, `nq_15min`, `6e_15min` y `6j_15min` desde MongoDB. También comparan cierres diarios con símbolos de Yahoo Finance (`ES=F`, `NQ=F`, `6E=F`, `6J=F`). | Verifiqué esas referencias en el código de los notebooks. No consulté MongoDB ni confirmé proveedor, contenido, contrato o cobertura. Las URI del `.env.example` están vacías; eso no acredita el estado de una conexión real. | Identificar para cada serie el broker/venue, contratos individuales, calendario, timezone, campos y precios disponibles, sesiones, regla de rollover y costos históricos. Yahoo es una comparación diagnóstica, no sustituto del feed primario. |
| **WTIFS — CFD de petróleo** | El inventario registra `research_development/data/axi/wtifs_H1_200802180000_202611021900.csv`, con etiqueta Axi por ruta/nombre. El notebook busca CSV de WTIFS bajo esa ruta. | Confirmé la referencia en el inventario y el patrón de búsqueda del notebook; no abrí el archivo. La auditoría marca proveedor no verificado y cobertura y huecos desconocidos. | Confirmar que sea exportación íntegra de la cuenta/feed que se pretende estudiar; definir horario y zona del servidor, especificación del CFD, bid/ask, spread, swaps, rollover y calendario esperado. |
| **BTCUSD — CFD** | El inventario registra `research_development/data/axi/BTCUSD_H1_201401150200_202611022200.csv`. El notebook de BTCUSD busca exportaciones CSV tabuladas. También figura un BTCUSD H1 de Dukascopy. | Verifiqué las rutas, no los precios. La auditoría marca ambas procedencias como no verificadas, con cobertura y huecos desconocidos. El descargador de Dukascopy está configurado para H1 y lado BID. | Validar por separado MT5/broker y Dukascopy: símbolo y especificación, timestamp, zona horaria, sesiones 24/7, huecos, BID frente a bid/ask y costos de financiación. El feed Dukascopy no confirma ejecución en Axi. |
| **BTCJPY — CFD** | El inventario registra `btcjpy_H1_201910010000_202611022200.csv` y `btcjpy_h1_utc.csv`. El código de procesamiento declara convertir hora de servidor Axi a UTC con una regla UTC+2/UTC+3 según horario de verano de EE. UU. | Verifiqué los nombres y la lógica documentada del convertidor, no los archivos ni su resultado. El inicio nominal de 2019 del primer nombre no demuestra la cobertura del segundo archivo. Inventario: procedencia, cobertura y huecos desconocidos. | Confirmar el archivo fuente y su historial; validar la regla horaria contra el calendario real del servidor y revisar transiciones DST, barras recortadas, huecos, contrato y costos. No asumir que la conversión declarada prueba que los timestamps sean correctos. |
| **QQQ — ETF** | El notebook solicita `QQQ` a `yfinance`, con inicio declarado en 1999 y `auto_adjust=True`. | Esto identifica la fuente y ajuste que intenta usar ese notebook, no la procedencia de un dataset local ni su cobertura efectiva. La auditoría de fuentes considera provisionales los datos tipo Yahoo hasta registrar adquisición, fechas, ajustes y términos. | Registrar la fuente efectivamente utilizada, historial observado, distribuciones y splits, licencia y calendario. Para investigación de retornos, separar serie ajustada de precios ejecutables sin ajuste para modelar fills. |
| **USDJPY y otros feeds** | Hay un notebook de USDJPY que busca CSV locales; el inventario general menciona fuentes asociadas a Axi, Darwinex, Dukascopy y series tipo Yahoo. | No verifiqué el contenido ni el proveedor de un archivo USDJPY para esta tarea. No es una réplica directa de futuros listados. | Mantenerlo como hipótesis/feed separado. Identificar instrumento OTC exacto, proveedor, zona horaria, sesiones, swaps y costos antes de analizarlo. |

Las fechas embebidas en los nombres de WTIFS y BTCUSD no se tratan como cobertura confirmada: la auditoría de inventario las deja como desconocidas hasta medir observaciones contra el calendario pertinente. Para BTCJPY, el nombre de una exportación indica nominalmente un inicio en 2019, pero no permite concluir el rango del archivo convertido.

## Calidad, calendario y comparabilidad

- **Cobertura y huecos:** desconocidos para los feeds enumerados. No se midieron barras ausentes, duplicados, timestamps fuera de sesión ni cobertura porcentual. No inferir continuidad por fechas de nombre.
- **Zona horaria y sesiones:** no hay manifiesto uniforme por serie. Los H1 de MT5 requieren verificar la zona del servidor y DST; BTCUSD/BTCJPY tienen convenciones y horarios de CFD distintos de un futuro listado. Los calendarios de futuros deben incluir sesiones y cierres pertinentes.
- **Precios y ajustes:** no está acreditado si las series contienen mid, BID, ASK, OHLC de cotización o settlement. Para futuros, una serie continua o back-adjusted no equivale al retorno de un contrato negociable; declarar la regla de roll y conservar los contratos base. Para QQQ, distinguir retorno total ajustado de precio de fill.
- **Costos:** no se encontraron costos históricos específicos por instrumento en la evidencia revisada. Faltan spread, comisión, slippage y, para CFDs, swap/financiación y posibles cambios de especificación. Costos actuales aplicados retrospectivamente no bastan.
- **Diferencias entre feeds:** futuros de Mongo y referencias Yahoo, MT5/Axi y Dukascopy, y precios ajustados/no ajustados pueden diferir en contrato, sesiones, reloj, cotización y rollover. Las comparaciones de EDA no establecen equivalencia de feed. No empalmar esas fuentes para cerrar cobertura.

## Plan mínimo reproducible para cerrar pendientes

1. **Futuros ES, NQ, 6E y 6J:** obtener primero el historial de la fuente del broker/venue que se pretende ejecutar. Guardar metadatos de instrumento, venue, contratos y granularidad; exportar timestamps, precios y campos de cotización disponibles. Documentar calendario, timezone/DST, settlement y costos. Definir de antemano la regla de rollover con información disponible en cada fecha; evitar ajuste retrospectivo del nivel.
2. **WTIFS y BTCUSD Axi:** confirmar documentalmente instrumento, broker, cuenta/feed y especificación del CFD. Identificar el origen del export, convención de hora y cambios de sesión; conseguir historial de bid/ask y spreads, comisiones, swaps/financiación y rollover. Mantener cualquier dato de otro proveedor en una serie aparte.
3. **BTCJPY:** localizar y documentar el archivo fuente del UTC convertido. Reproducir la conversión desde timestamps originales, validar cambios DST y cotejar muestras de inicio, fin y transiciones con el origen; medir aparte las barras descartadas por el convertidor.
4. **QQQ:** registrar la descarga realmente usada y su fecha, proveedor, ajustes corporativos, licencia y periodo observado. Conservar series diferenciadas para retorno total y simulación de ejecución; validar precios/fills con la fuente de broker elegida.
5. **Para cada dataset:** guardar un manifiesto con instrumento, proveedor, frecuencia, timezone, calendario, inicio/fin observados, observaciones esperadas/observadas, huecos, transformaciones, ajustes, costos y diferencias de feed. Definir primero el calendario esperado; después medir cobertura y huecos sin interpolar.
6. **Si se usa un fallback:** medirlo separadamente y documentar el corte y las diferencias respecto a la fuente primaria. Si una conclusión depende de ese fallback o de series empalmadas, marcarla `NO CONFIRMADO`.

## Evidencia necesaria para pasar a notebook

Se puede preparar una notebook de estrategia cuando exista una predicción y métrica fijadas antes de observar resultados, y los datos tengan instrumento/feed identificados, calendario y transformaciones documentados, cobertura calculada de al menos 98% y costos disponibles o declarados faltantes. No rellenar huecos para superar el umbral. Para los futuros listados, también se necesita una regla de rollover reproducible y contratos/venue identificados. Si no se alcanza la muestra objetivo de 100 eventos o trades independientes, registrar la limitación de potencia y mantener el estado pendiente.

El paso a notebook solo autoriza la prueba; no confirma un edge. La evidencia confirmatoria debe superar los gates comunes: ajuste FDR `q <= 0.05`, límite inferior del IC bootstrap del 95% de la métrica neta por encima de cero, resultado agregado positivo y positivo en al menos 2 de 3 ventanas OOS, al menos 70% de parámetros vecinos positivos y escenario de estrés de costos 2x todavía positivo, con reproducción en la fuente primaria.

## Crítica independiente / red team

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Red team · Momentum de serie temporal en futuros listados

**Estado:** revisión metodológica de la ficha; no se inspeccionaron datos ni se ejecutaron pruebas.  
**Corte de evidencia:** 2017-12-31.  
**Veredicto de investigación:** **pendiente**. La hipótesis tiene una predicción contrastable en principio, pero aún no identifica contratos, fuente primaria, construcción de retornos ni métrica primaria suficientes para pasar a un notebook de estrategia.

## Evaluación de la ficha

La ficha propone que el signo del retorno total de los 12 meses anteriores predice continuación durante los siguientes 1–12 meses. También limita el alcance a futuros y reconoce riesgos de rollover, selección, dependencia temporal, regímenes y costos. Esto ofrece una motivación investigable y evita extrapolar directamente la evidencia a CFD, ETF, cripto o intradía.

La predicción sigue siendo demasiado amplia para evaluarla sin decisiones posteriores a observar resultados. No determina qué significa «retorno total» para cada contrato, qué fecha y precio forman la señal, cómo se mide la continuación, qué horizonte será primario ni cómo se agregan los instrumentos. Probar varios horizontes de 1–12 meses y reportar el mejor convertiría una sola ficha en una familia de ensayos.

La ficha menciona los gates comunes, pero todavía no demuestra que pueda cumplirlos: procedencia y cobertura de los datos, costos, potencia, divisiones cronológicas fuera de muestra y grilla paramétrica siguen sin verificar. Los gates son criterios de evaluación, no resultados.

## Objeciones por severidad

| Severidad | Objeción y posible distorsión | Prueba que podría refutarla |
|---|---|---|
| **Bloqueante** | **Instrumento, venue y datos no identificados.** Las colecciones Mongo de ES, NQ, 6E y 6J no acreditan proveedor, contratos, historia ni cobertura. Sin fuente primaria verificable, la hipótesis no está lista para medir. | Para cada contrato, documentar proveedor/broker, símbolo, timestamps, calendario, contratos individuales, rango efectivo y huecos; calcular cobertura del calendario esperado. Si no alcanza 98% sin rellenar datos, dejar pendiente. |
| **Bloqueante** | **Retorno y rollover ambiguos.** «Retorno total» puede depender de settlement, precio de cierre, empalme, ajustes retrospectivos o financiación. Una serie continua mal construida puede crear o borrar tendencia. | Especificar retornos negociables por contrato y regla de roll conocida en cada fecha. Comparar la señal con contratos individuales y una construcción continua sin ajuste retrospectivo que altere rendimientos. Si el signo depende de una convención retrospectiva, no confirmar. |
| **Alta** | **Horizontes múltiples sin métrica primaria.** La predicción abarca retornos siguientes de 1–12 meses, lo que permite seleccionar el horizonte más favorable y multiplica pruebas junto con mercados y variantes. | Antes de medir, fijar una métrica primaria, horizonte, universo, benchmark y grilla completa. Contabilizar los demás horizontes como pruebas secundarias y aplicar ajuste por comparaciones múltiples, con FDR `q <= 0.05` como default. |
| **Alta** | **Ejecución y costos sin especificación.** La evidencia de retorno no equivale a rentabilidad ejecutable. Faltan precio de entrada/salida, latencia, bid/ask, comisión, slippage y costo de roll. | Simular señal disponible tras el cierre y ejecución en el siguiente precio negociable; incorporar costos observados por instrumento y época. Repetir con estrés de 2× spread y comisión. Si el neto deja de ser positivo, descartar como edge ejecutable. |
| **Alta** | **Ventanas solapadas y dependencia serial.** Los resultados de horizontes mensuales solapados no son observaciones independientes; contar cada mes o barra como un evento puede estrechar artificialmente los intervalos. | Usar bootstrap por bloques temporales compatible con el horizonte, reportar eventos independientes y preservar la dependencia en los intervalos. Si el límite inferior del IC bootstrap 95% neto no supera cero, no confirma. |
| **Alta** | **Selección de mercados y supervivencia.** Elegir hoy futuros líquidos o incluir solo los mercados con series completas puede sesgar la cartera hacia supervivientes o ganadores. La ficha no define el universo histórico. | Fijar universo con información disponible en cada fecha; incluir contratos o mercados descontinuados si los datos lo permiten, y documentar exclusiones. Reportar resultados por mercado además del agregado. |
| **Alta** | **Contaminación entre descubrimiento y validación.** No hay protocolo para separar calibración de evaluación final. Si se ajustan decisiones al ver todo el historial, el holdout deja de ser independiente. | Congelar señal, métrica, universo y grilla antes del análisis; preservar un holdout cronológico intocado y validar en tres ventanas OOS predefinidas. Exigir resultado agregado positivo y expectativa neta positiva en al menos dos de tres. |
| **Media-alta** | **Régimen y concentración de pérdidas.** La continuación puede coexistir con pérdidas abruptas en rebotes o cambios de régimen. Un promedio total puede ocultar dependencia de unos pocos episodios. | Reportar drawdowns, peores episodios y retorno por períodos cronológicos o regímenes definidos sin consultar el resultado. Si la rentabilidad depende de uno o pocos episodios, o excede los límites de riesgo acordados, mantener pendiente o descartar. |
| **Media** | **Tamaño de muestra y unidad de observación.** El gate de 100 eventos/trades independientes es mínimo de revisión, no una garantía de potencia. Una señal mensual puede no producir suficientes eventos independientes en ciertos contratos. | Estimar la cantidad de eventos independientes y la potencia antes de interpretar significancia. Si no alcanza, marcar pendiente por potencia; no sustituir eventos por barras correlacionadas. |
| **Media** | **Señal y dimensionamiento pueden confundirse.** No se define si la predicción es direccional simple o incluye volatilidad objetivo. El sizing puede cambiar la métrica y sumar parámetros no contabilizados. | Evaluar primero la señal direccional con exposición definida; analizar sizing por separado, usando estimaciones de volatilidad lagged. Registrar cada variante en la grilla de ensayos. |

## Gates y evidencia

La motivación bibliográfica es pertinente como antecedente de una hipótesis TSMOM en futuros, pero no confirma la señal en los contratos o feeds locales. La ficha reconoce ese límite correctamente.

Los gates están especificados en el documento común: cobertura mínima de 98%, muestra con limitación explícita si hay menos de 100 eventos independientes, control de comparaciones, métrica primaria neta con IC bootstrap 95% positivo, robustez en ventanas OOS, estabilidad en parámetros vecinos y estrés de costos. En esta ficha, todos permanecen **pendientes de aplicación**; no hay evidencia empírica que permita declarar un gate aprobado.

## Mejoras requeridas antes de probar

1. Identificar contrato, venue y feed primario para cada mercado, y verificar cobertura y metadatos antes de calcular señales.
2. Definir el retorno negociable, settlement o cierre, calendario, unidad de señal, regla de rollover y momento de ejecución.
3. Fijar mercado o universo, benchmark, métrica primaria y un horizonte primario; registrar de antemano todas las variantes secundarias.
4. Separar descubrimiento y validación cronológica, y establecer cómo se ajustarán las comparaciones múltiples.
5. Determinar costos por período y plan de inferencia que preserve la dependencia temporal; informar eventos independientes y potencia.
6. Reportar resultados por instrumento, período y episodio, además del agregado, junto con drawdowns y sensibilidad a parámetros y costos.

## Fallos bloqueantes y veredicto

**Bloquean el avance a notebook de estrategia:** falta identificar contratos y fuente primaria; no hay cobertura medida; rollover y retorno total no están operacionalizados; tampoco hay métrica primaria ni horizonte seleccionado antes de evaluar resultados.

**Veredicto: pendiente.** La hipótesis no se descarta: la literatura anterior a 2018 justifica investigarla. La ficha necesita las decisiones y verificaciones anteriores antes de pasar a notebook; superar esa etapa no implicaría validar un edge.

## Datos, cobertura y pendientes

No se leyeron CSV de mercado en esta corrida. El origen, la cobertura porcentual y los huecos deben verificarse por dataset usando la prioridad broker → Dukascopy para CFDs y una fuente licenciada/apropiada para ETFs. No interpolar ni empalmar series sin registrarlo. Si una conclusión requiere datos rellenados o feeds empalmados, marcarla `NO CONFIRMADO`.

## Control de calidad

Cualquier fuente citada debe ser anterior a 2018 y contener DOI o URL estable. Las referencias que no pudieron verificarse deben aparecer explícitamente como `no verificada`; no son evidencia de apoyo hasta revisión humana.
