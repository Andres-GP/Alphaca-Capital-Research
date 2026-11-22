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