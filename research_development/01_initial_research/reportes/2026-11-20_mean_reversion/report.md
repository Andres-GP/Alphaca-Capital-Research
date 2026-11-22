# Informe inicial · Mean Reversion · 2026-11-20

**Estado de la corrida:** revisión cualitativa completa.  
**Motores por rol:** literatura: codex/gpt-6-luna/high (ChatGPT OAuth), datos: codex/gpt-6-luna/high (ChatGPT OAuth), red_team: codex/gpt-6-luna/high (ChatGPT OAuth).  
**Alcance:** investigación cualitativa y revisión documental; esta corrida no leyó precios ni ejecutó backtests.

## Resumen ejecutivo

Este informe organiza revisión de literatura, diagnóstico de datos y crítica independiente. No presenta rentabilidades medidas ni declara un edge validado. La cobertura y los huecos de datos siguen desconocidos hasta calcularlos contra un calendario de sesiones verificado; las gates estadísticas, de robustez y costos siguen pendientes.

## Árbol de investigación

![Árbol de familia, pauta, mercado e hipótesis](tree.svg)

## Hipótesis existentes

- `cross_sectional_weekly_contrarian/us_equities/hypothesis.md` — veredicto: pendiente de datos y gates.

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

# Literatura y mecanismo · reversión a la media

**Alcance.** Este informe se centra en la hipótesis de reversión semanal contrarian entre acciones ordinarias de EE. UU. La literatura citada motiva pruebas; no valida una señal del repositorio. No se han inspeccionado datos ni ejecutado backtests.

## Mecanismos posibles

- **Presión transitoria de liquidez.** Una necesidad temporal de comprar o vender puede mover precios y después revertirse cuando cede la presión. Lehmann interpreta sus resultados semanales como posiblemente relacionados con la liquidez alrededor de movimientos grandes. Es una explicación propuesta, no un mecanismo demostrado para los datos de este proyecto.
- **Sobrerreacción.** Los inversores podrían extrapolar demasiado noticias o movimientos recientes y corregir después sus valoraciones. De Bondt y Thaler encuentran evidencia compatible con esta explicación en carteras de acciones formadas a partir de retornos de varios años; eso no establece que explique reversiones semanales.
- **Dependencia entre acciones.** Una cartera que compra perdedores y vende ganadores puede beneficiarse de relaciones de liderazgo y rezago entre títulos, incluso sin reversión propia en cada acción. Por tanto, el retorno contrarian de una cartera no identifica por sí solo el mecanismo.

## Predicciones falsables

Para la ficha semanal, conviene fijar antes de medir:

1. Si los retornos de la semana previa predicen retornos de signo contrario durante la siguiente semana en las mismas acciones, y si el resultado neto supera un control predefinido.
2. Si la señal persiste al modelar bid-ask, costos de transacción, liquidez y restricciones de venta corta, con universo point-in-time y títulos retirados incluidos.
3. Si el retorno de cartera se mantiene al separar autocorrelación propia de autocovarianzas cruzadas y efectos de liderazgo entre acciones.
4. Si la conclusión se sostiene en ventanas cronológicas fuera de muestra sin escoger retrospectivamente umbrales, horizontes o filtros.

Estas son pruebas propuestas, no resultados obtenidos.

## Estudios relevantes publicados antes de 2018

- **Bruce N. Lehmann (1990), “Fads, Martingales, and Market Efficiency.”** Reporta reversión semanal de carteras de ganadores y perdedores en su muestra, que persiste tras ciertos ajustes de spread y costos plausibles en el diseño del estudio. Propone que el resultado probablemente refleja ineficiencia en el mercado de liquidez alrededor de movimientos grandes. La muestra y los costos del artículo no establecen ejecutabilidad actual. [*The Quarterly Journal of Economics*, DOI](https://doi.org/10.2307/2937816).
- **Andrew W. Lo y A. Craig MacKinlay (1990), “When Are Contrarian Profits Due to Stock Market Overreaction?”** Muestran que las estrategias contrarian pueden obtener retornos esperados por relaciones de liderazgo y rezago entre acciones; reportan liderazgo de acciones grandes sobre pequeñas y concluyen que la sobrerreacción no es la única fuente posible de beneficios contrarian. [*The Review of Financial Studies*, DOI](https://doi.org/10.1093/rfs/3.2.175).
- **Richard Roll (1984), “A Simple Implicit Measure of the Effective Bid-Ask Spread in an Efficient Market.”** Analiza cómo las transacciones que alternan entre bid y ask pueden inducir autocovarianza negativa en los retornos observados. Esto hace necesario distinguir reversión económica de rebote de cotización, especialmente a frecuencias altas. [*The Journal of Finance*, DOI](https://doi.org/10.1111/j.1540-6261.1984.tb03897.x).
- **Werner F. M. De Bondt y Richard Thaler (1985), “Does the Stock Market Overreact?”** Encuentran resultados compatibles con sobrerreacción en carteras de acciones basadas en retornos mensuales de CRSP y movimientos extremos de varios años. Motivan una hipótesis de reversión de largo plazo; no prueban una regla semanal. [*The Journal of Finance*, DOI](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x).
- **Narasimhan Jegadeesh (1990), “Evidence of Predictable Behavior of Security Returns.”** Reporta autocorrelación negativa mensual de primer orden y autocorrelación positiva a rezagos mayores en acciones individuales. El signo de la predictibilidad depende del horizonte, así que “reversión” debe definirse con precisión temporal. [*The Journal of Finance*, DOI](https://doi.org/10.1111/j.1540-6261.1990.tb05110.x).

## Límites de inferencia y preguntas abiertas

Estos estudios difieren en periodo, frecuencia, universo y diseño. Sus resultados no demuestran rentabilidad neta actual, ni se trasladan automáticamente a QQQ, futuros, CFDs, FX o cripto. Tampoco permiten atribuir una reversión observada a sobrerreacción sin descartar liquidez, microestructura y dependencias entre títulos.

Para esta familia siguen abiertas preguntas sobre la cobertura y procedencia de los datos, la composición histórica del universo, delistings, costos de short y spreads condicionales a la señal. El estado actual de la hipótesis semanal del repositorio es `data_pending`: no hay resultados propios ni edge validado.

## Evidencia empírica y datos

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Informe de evidencia y datos · Reversión a la media

**Familia:** mean_reversion  
**Fecha de corte:** 2026-11-20  
**Estado:** `data_pending`; no hay datos verificados para una prueba de la hipótesis semanal.  
**Alcance:** se inspeccionaron manifiestos, documentación y código. No se abrieron CSV de mercado, no se descargaron datos y no se calcularon cobertura ni huecos.

## Dictamen

Los datos descritos en el repositorio no bastan para pasar la hipótesis de reversión semanal contrarian a un notebook de estrategia. Hay archivos de precios por ticker y un archivo de membresía S&P 500, pero sus metadatos no acreditan un universo histórico completo, precios de acciones retiradas, continuidad ni costos ejecutables.

El manifiesto local enumera 528 rutas CSV bajo `research_development/data/`: 501 corresponden a `t20/prices/`. Son conteos de rutas del manifiesto, no comprobaciones del contenido. Para esos precios, el manifiesto marca origen como no verificado, cobertura desconocida y huecos no medidos. También lista `t20/sp500_membership.csv`, pero no acredita su procedencia ni su integridad. La auditoría explica que las fechas inferidas de nombres son nominales y que no se compararon timestamps con calendarios de sesión.  
Fuentes locales: `data_audit/README.md`, `data_audit/local_datasets.csv`.

La EDA de QQQ descarga con `yfinance` desde una fecha nominal de 1999 y usa `auto_adjust=True`. El manifiesto no registra un `QQQ.csv` local. QQQ sería una ficha distinta: no sustituye una cartera transversal de acciones. La auditoría de fuentes tampoco considera garantizada una descarga gratuita e histórica de Yahoo para QQQ.  
Fuentes locales: `eda/notebooks_legacy/QQQ_EDA.ipynb`, `data_audit/source_evaluation.md`.

## Datos descritos en el repositorio y límites observados

| Componente | Descrito o presente en el repo | Lo verificado en esta corrida | Pendiente para usarlo |
|---|---|---|---|
| Precios diarios T20 | Archivos por ticker; el código de T20 usa Yahoo Finance vía `yfinance`, con precios ajustados por splits y dividendos. | Código y rutas del manifiesto inspeccionados; no se leyeron CSV. | Proveedor y licencia por archivo, rango real, zona horaria, campos, corporate actions, huecos y precios de ejecución. |
| Universo S&P 500 | Hay una ruta `t20/sp500_membership.csv`. El código de T20 reconstruye intervalos con la lista actual y el historial de cambios de Wikipedia; contempla una degradación a miembros actuales. | Código inspeccionado. Documenta que los precios de retiradas son escasos en Yahoo y que el modo de solo miembros actuales tiene sesgo de supervivencia fuerte. | Verificar qué modo produjo el archivo local, fechas cubiertas, tickers reutilizados y si contiene todos los cambios y retiradas necesarios. No asumir que el archivo presente elimina el sesgo. |
| `download_failed.csv` | El código de T20 puede guardar tickers no descargados. | La ruta aparece en el manifiesto; su contenido no se abrió. | Identificar los símbolos y determinar si faltan precisamente acciones retiradas o semanas críticas. |
| QQQ | La notebook usa `yfinance`, `auto_adjust=True` y solicita barras diarias desde 1999. | Se verificó el código fuente de la notebook, no la ejecución ni el resultado descargado. | Broker/venue, cobertura efectiva, ajustes, sesiones y precio cotizable para fills. No usarlo como sustituto de la hipótesis transversal. |
| Otros instrumentos | El inventario incluye rutas etiquetadas Axi, Darwinex y Dukascopy; las EDA de ES/NQ/6E/6J cargan colecciones MongoDB. | Se verificaron etiquetas, código de carga y advertencias escritas en las auditorías, no los datos ni las colecciones. | Quedan fuera de esta ficha de acciones. No extrapolar evidencia ni mezclar feeds sin una ficha propia. |

En acciones, los retornos ajustados sirven para medir desempeño y manejar distribuciones/corporate actions; no son precios de fill. Se necesitan precios negociables y costos. Los precios ajustados automáticos de Yahoo, por sí solos, no prueban cómo habría ejecutado la cartera.

## Fuente prioritaria para esta hipótesis

La hipótesis registrada trata de acciones ordinarias de EE. UU. en una cartera long-losers/short-winners semanal. Para ese caso:

1. **Universo y retornos históricos:** priorizar una fuente con composición point-in-time, identificadores históricos, acciones retiradas y retornos de delisting; CRSP es una referencia de datos apropiada si está disponible y su licencia permite el uso. La membresía S&P 500 reconstruida desde la lista actual y Wikipedia puede servir como sensibilidad documentada, no como universo validado por sí sola.
2. **Ejecución:** priorizar datos del broker/venue donde se ejecutaría la estrategia para precios de entrada y salida, bid/ask o spreads, y comisiones. Para el tramo short hacen falta costos históricos de préstamo y restricciones de disponibilidad.
3. **Fuentes gratuitas o feeds alternativos:** usarlos como contraste identificado por fuente y período. Si se empalman con otro proveedor, marcar todo resultado dependiente del empalme como **`NO CONFIRMADO`** y reportar cada segmento por separado.

La auditoría del repo indica que Dukascopy puede complementar historia de algunos CFDs, pero no replica las condiciones de Darwinex. Esa observación no resuelve datos de acciones ni costos de short de acciones.

## Cobertura, calendario, sesiones y costos

A día de hoy, **cobertura y huecos son desconocidos**. No hay porcentaje calculado ni se debe inferir continuidad a partir de rangos nominales o número de archivos.

Para medirlos de forma reproducible, primero fijar el universo point-in-time y luego construir el calendario de sesiones de cada mercado en `America/New_York`, incluyendo festivos y cierres anticipados. Definir la semana de formación como la última sesión regular disponible y calcular el denominador sobre las observaciones símbolo-semana en que cada título pertenecía al universo y debía tener datos. Publicar el numerador, el denominador, las exclusiones y las reglas de faltantes; no rellenar huecos. Para títulos que dejan de cotizar, registrar el evento y el retorno de delisting en vez de eliminar la observación.

La señal de la semana debe estar disponible antes de ejecutar. Si se forma con el cierre de la última sesión, modelar el fill en la siguiente oportunidad ejecutable, no en ese mismo cierre. Separar retornos ajustados usados para el cálculo estadístico de precios y cotizaciones usados para el PnL. Estimar costos condicionados a los títulos extremos y al lado de la operación: spreads, comisiones, slippage y préstamo de acciones. Una cotización mid puede servir de diagnóstico, pero no reemplaza el precio ejecutable.

Las diferencias entre feeds que deben registrarse incluyen ajustes por dividendos y splits, cierres y sesiones, identificadores reutilizados, liquidez en títulos extremos, spreads y disponibilidad de préstamo. El código de T20 documenta además un modo de membresía con solo integrantes actuales y carencia de precios de muchos títulos retirados; cualquier resultado construido así no elimina el sesgo de supervivencia.

## Plan mínimo reproducible

1. **Fijar la ficha antes de medir:** universo, semana de formación, semana de tenencia, ponderación, benchmark y ejecución posterior a la señal. Mantener separadas reversión propia de cada título y autocovarianza cruzada de cartera.
2. **Auditar el universo:** documentar la fuente de membresía, intervalos efectivos, títulos añadidos y retirados, identificadores, corporaciones reutilizadas y modo de generación del archivo local.
3. **Auditar cada serie sin completar datos:** registrar origen, versión/fecha de extracción, campos, zona horaria, calendario, primer y último timestamp, duplicados, huecos y corporate actions. Calcular cobertura sobre semanas símbolo elegibles; conservar y explicar datos faltantes.
4. **Alinear feeds y ejecuciones:** comparar cierres semanales en fechas coincidentes y describir las diferencias frente al broker/venue. Usar cotizaciones o precios ejecutables para el PnL y costos históricos de short. No interpolar ni asumir fills al mid.
5. **Entregar evidencia para la puerta de entrada:** manifiesto por serie, método y denominador de cobertura, registro de huecos/exclusiones, evidencia de delistings, costos y prueba de reconciliación de feeds. Solo entonces crear el notebook de estrategia y aplicar los gates comunes de [`GATES.md`](research_development/01_initial_research/GATES.md), incluidos cobertura mínima, muestra independiente, control de comparaciones, ventanas OOS y estrés de costos.

**Resultado de esta revisión:** no hay backtest ni edge propio verificado. La ficha permanece `data_pending`; una prueba basada únicamente en las rutas T20 existentes no demostraría aún cobertura point-in-time ni rentabilidad neta ejecutable.

## Crítica independiente / red team

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Red team independiente · Reversión semanal contrarian en acciones de EE. UU.

**Estado:** crítica previa a pruebas; no se inspeccionaron datasets ni se ejecutaron backtests.  
**Veredicto:** `pendiente` (`data_pending`). La pregunta es falsable en términos generales, pero faltan definiciones operativas y datos para evaluar los gates. No hay evidencia de un edge local.

## Objeciones por severidad

| Severidad | Objeción | Prueba que podría refutarla |
|---|---|---|
| **Bloqueante** | **El calendario de señal, formación, ejecución y tenencia no está fijado.** “Retorno de la semana previa” y “semana siguiente” no especifican días, hora de corte ni si se opera al cierre que forma la señal. Elegirlos después de ver resultados permitiría look-ahead o selección de calendario. | Prerregistrar semanas, precios y marcas temporales: calcular la señal solo con datos disponibles al corte y ejecutar después de ese corte a precios cotizables. Verificar que el resultado persiste con esa secuencia temporal. |
| **Bloqueante** | **El universo point-in-time y los delistings están sin verificar.** Un archivo por ticker o una lista de acciones actuales puede excluir empresas desaparecidas y sesgar especialmente el grupo de perdedores. La ficha reconoce esta carencia; por ahora impide interpretar una prueba histórica como representativa. | Reconstruir la elegibilidad del universo en cada fecha, incluir títulos retirados y sus retornos de salida, y comparar con el universo actual solo como diagnóstico. Si no se dispone de ello, mantener la limitación explícita y el estado pendiente. |
| **Bloqueante** | **No hay datos de ejecución ni costos históricos demostrados.** Los perdedores extremos pueden tener spreads, impacto y dificultad de préstamo mayores justo al formarse la señal. Precios ajustados de retorno no establecen precios ejecutables; costos promedio pueden subestimar los de estos títulos. | Usar precios y quotes del broker o venue para entradas y salidas, costos condicionados a la señal y al tamaño, y disponibilidad/costo de préstamo. Aplicar el gate de estrés de 2× spread y comisión. Si el retorno neto no es positivo, descartar la hipótesis operativa. |
| **Alta** | **La métrica primaria, el control y la construcción del portafolio no están definidos.** “Retorno neto positivo frente a un control fijado de antemano” no identifica el control ni los pesos, límites de posición, neutralización de mercado o reglas de elegibilidad. Esos grados de libertad pueden cambiar el resultado. | Antes de calcular retornos, fijar benchmark, métrica primaria, ponderación, límites, tratamiento de empates y acciones no negociables. Publicar la especificación y evaluar toda variante como prueba adicional. |
| **Alta** | **La ganancia de cartera no identificaría por sí sola reversión propia.** La hipótesis reconoce la autocovarianza cruzada, pero no define cómo separarla de la reversión individual. Liderazgo rezagado entre títulos podría producir el retorno del portafolio contrarian sin confirmar el mecanismo planteado. | Descomponer el retorno de cartera en componentes de autocovarianza propia y cruzada, y probar si los retornos futuros de cada título se relacionan negativamente con sus propios retornos pasados. Si solo sobrevive el componente cruzado, reformular el mecanismo. |
| **Alta** | **La independencia y la potencia pueden estar sobreestimadas.** Semanas contiguas comparten condiciones de mercado; las acciones también están expuestas a shocks comunes. Contar cada acción-semana como evento independiente inflaría la muestra y estrecharía los intervalos. | Definir eventos independientes y remuestrear en bloques que preserven dependencia temporal y transversal. Informar potencia o limitación si no se alcanzan 100 eventos/trades independientes; ese umbral es un filtro inicial, no garantía de potencia. |
| **Alta** | **La reversión aparente puede ser bid-ask bounce o rebote de liquidez.** La señal se forma con títulos cuyo movimiento reciente puede reflejar cotizaciones al bid o al ask, precios stale y spreads amplios. El uso de cierres o midpoints como fills podría exagerar la reversión. | Comparar diagnósticos con midpoint frente a PnL ejecutable a bid/ask y spreads observados al momento de la señal. Analizar por liquidez y tamaño. Si el efecto solo aparece al mid o se elimina con costos realistas, descartarlo como estrategia ejecutable. |
| **Alta** | **Hay riesgo de snooping y contaminación entre muestra y validación.** La ficha aún no registra grilla de horizontes, filtros, ponderaciones y parámetros, ni un holdout cronológico intacto. Probar variantes y conservar la mejor invalidaría la lectura confirmatoria. | Prerregistrar la grilla y la métrica primaria, conservar todos los ensayos y reservar ventanas cronológicas fuera de muestra. Ajustar comparaciones múltiples (FDR `q <= 0.05`) según la familia de pruebas. |
| **Media** | **El resultado puede depender de uno o pocos regímenes.** Una recuperación tras ventas forzadas podría dominar el promedio; tendencias bajistas persistentes pueden perjudicar a una regla que compra perdedores semanalmente. | Reportar ventanas cronológicas predefinidas, resultado agregado, peores episodios y drawdowns. Exigir resultado agregado positivo y positivo en al menos 2 de 3 ventanas OOS, sin crear filtros de régimen después de observar los datos. |
| **Media** | **Los ajustes corporativos y precios de formación pueden mezclar retorno económico y fill.** Dividendos, splits y eventos corporativos afectan la señal y el rendimiento calculado, pero una serie ajustada no representa por sí misma el precio negociable. | Documentar fuente, ajustes y corporate actions; calcular retornos con la convención definida y fills con precios negociables. Reconciliar eventos relevantes y conservar los huecos en lugar de completarlos silenciosamente. |

## Predicción y gates

La pregunta plantea una dirección y un horizonte contrarian, por lo que puede hacerse falsable. Aún necesita precisar el calendario, benchmark, métrica primaria, construcción del portafolio y regla de ejecución para evitar decisiones posteriores al resultado.

La ficha cita literatura anterior a 2018 pertinente a estrategias semanales de cartera y advierte correctamente que los resultados de cartera no prueban reversión individual. Los datos, su cobertura efectiva, la composición histórica del universo y los costos siguen sin verificarse. Por ello, no puede afirmarse que se cumplan los gates iniciales de cobertura de al menos 98% o muestra suficiente.

Para declarar evidencia confirmatoria siguen pendientes todos los gates empíricos aplicables: corrección por comparaciones múltiples, métrica primaria neta con límite inferior del IC bootstrap de 95% mayor que cero, robustez en ventanas OOS, al menos 70% de parámetros vecinos positivos, estrés de costos y reproducción con fuente primaria del broker.

## Mejoras prioritarias

1. Fijar calendario, precios de señal y ejecución, benchmark, métrica primaria, ponderación y elegibilidad antes de consultar resultados.
2. Verificar universo point-in-time, acciones retiradas, corporate actions y cobertura efectiva; documentar origen y huecos.
3. Conseguir bid/ask ejecutable y costos históricos de transacción y préstamo, especialmente para los títulos seleccionados como extremos.
4. Definir cómo se separarán autocovarianza propia y cruzada, y cómo se contará la muestra independiente.
5. Prerregistrar la grilla de pruebas, los bloques de bootstrap y las ventanas OOS.

**Conclusión:** mantener `pendiente` (`data_pending`). La ficha justifica una investigación, pero no está lista para una prueba confirmatoria ni para declarar un edge. Puede avanzar a notebook cuando se cierren las definiciones operativas y los requisitos de datos; cualquier resultado deberá pasar los gates antes de cambiar el veredicto.

## Datos, cobertura y pendientes

No se leyeron CSV de mercado en esta corrida. El origen, la cobertura porcentual y los huecos deben verificarse por dataset usando la prioridad broker → Dukascopy para CFDs y una fuente licenciada/apropiada para ETFs. No interpolar ni empalmar series sin registrarlo. Si una conclusión requiere datos rellenados o feeds empalmados, marcarla `NO CONFIRMADO`.

## Control de calidad

Cualquier fuente citada debe ser anterior a 2018 y contener DOI o URL estable. Las referencias que no pudieron verificarse deben aparecer explícitamente como `no verificada`; no son evidencia de apoyo hasta revisión humana.
