# Informe inicial · Calendar Seasonality · 2026-11-20

**Estado de la corrida:** revisión cualitativa completa.  
**Motores por rol:** literatura: codex/gpt-6-luna/high (ChatGPT OAuth), datos: codex/gpt-6-luna/high (ChatGPT OAuth), red_team: codex/gpt-6-luna/high (ChatGPT OAuth).  
**Alcance:** investigación cualitativa y revisión documental; esta corrida no leyó precios ni ejecutó backtests.

## Resumen ejecutivo

Este informe organiza revisión de literatura, diagnóstico de datos y crítica independiente. No presenta rentabilidades medidas ni declara un edge validado. La cobertura y los huecos de datos siguen desconocidos hasta calcularlos contra un calendario de sesiones verificado; las gates estadísticas, de robustez y costos siguen pendientes.

## Árbol de investigación

![Árbol de familia, pauta, mercado e hipótesis](tree.svg)

## Hipótesis existentes

- `weekday_returns/us_equity_index/hypothesis.md` — veredicto: pendiente de datos y gates.

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

# Literatura y mecanismo · Estacionalidad y calendario

**Corte de literatura:** 2017-12-31.  
**Estado para Alphaca:** los archivos proporcionados no documentan una prueba local ni confirman un efecto de calendario. Los hallazgos siguientes pertenecen a las muestras e instrumentos de los estudios citados.

## Mecanismo y predicciones falsables

Para una pauta de día de semana en acciones de EE. UU., el fin de semana puede cambiar la distribución de noticias y el intervalo sin negociación. También pueden influir los horarios de liquidación, la microestructura de apertura y el momento en que se publican noticias. Son explicaciones posibles, no causas demostradas para los datos de Alphaca.

De esas explicaciones surgen pruebas separables:

- **Tiempo calendario frente a tiempo de negociación:** fijar por adelantado si se mide viernes-cierre a lunes-cierre, viernes-cierre a lunes-apertura o lunes durante la sesión. Comparar las predicciones de cada hipótesis.
- **Acumulación de noticias:** separar el retorno de fin de semana del retorno intradía del lunes; contrastar el patrón con timestamps de anuncios disponibles entonces.
- **Liquidación y microestructura:** examinar si el diferencial se concentra en apertura o en ciertos intervalos, y si persiste con precios ejecutables y costos variables por horario.
- **Estabilidad:** fijar ventanas cronológicas fuera de muestra. Un diferencial histórico de medias no implica que se mantenga ni que pueda negociarse hoy.

## Trabajos académicos anteriores a 2018

- **Kenneth R. French (1980), “Stock Returns and the Weekend Effect.”** En retornos diarios del portafolio S&P Composite entre 1953 y 1977, reporta retornos medios de lunes significativamente negativos en cada uno de cinco subperiodos. Los datos no encajan con claridad con las hipótesis simples de tiempo calendario y tiempo negociado que compara. [DOI y artículo de Elsevier](https://doi.org/10.1016/0304-405X(80)90021-5). Este resultado motiva una prueba, pero no establece un mecanismo causal ni evidencia para otro periodo, instrumento o feed.

- **Josef Lakonishok y Maurice Levi (1982), “Weekend Effects on Stock Returns: A Note.”** El artículo examina explicaciones institucionales del efecto de fin de semana, entre ellas la liquidación. [DOI y artículo de Wiley](https://doi.org/10.1111/j.1540-6261.1982.tb02231.x). Sirve para formular una hipótesis estructural; no basta para atribuir un patrón observado en otros datos al sistema de liquidación.

- **Lawrence Harris (1986), “A Transaction Data Study of Weekly and Intradaily Patterns in Stock Returns.”** Con datos de transacciones, encuentra que el retorno negativo de lunes se distribuye de manera distinta según el tamaño de las empresas: para las grandes aparece entre el cierre del viernes y la apertura del lunes; para las pequeñas, principalmente durante la sesión del lunes. También reporta diferencias entre días en los primeros 45 minutos. [DOI y copia del artículo](https://doi.org/10.1016/0304-405X(86)90044-9). El trabajo respalda separar intervalos y horarios; no valida rentabilidad neta en otro mercado.

- **Josef Lakonishok y Seymour Smidt (1988), “Are Seasonal Anomalies Real? A Ninety-Year Perspective.”** Con 90 años de datos diarios del Dow Jones, reportan patrones persistentes alrededor del cambio de semana, mes y año, y de los feriados. [DOI y artículo de Oxford Academic](https://doi.org/10.1093/rfs/1.4.403). La muestra larga permite estudiar persistencia histórica, pero no certifica una regla actual ni su ejecución.

- **Ronen A. Ariel (1987), “A Monthly Effect in Stock Returns.”** Reporta que, en la muestra estudiada, el retorno medio de acciones era positivo principalmente en días inmediatamente anteriores y durante la primera mitad de los meses calendario, e indistinguible de cero en la segunda mitad. [DOI y artículo de Elsevier](https://doi.org/10.1016/0304-405X(87)90066-3). Es una pauta distinta del efecto semanal y no debe mezclarse con ella ni extrapolarse a otros activos.

- **Ryan Sullivan, Allan Timmermann y Halbert White (1999), “Data-Snooping, Technical Trading Rule Performance, and the Bootstrap.”** Aplican White’s Reality Check al universo de reglas técnicas evaluadas para cuantificar el sesgo de búsqueda. [DOI y artículo de Wiley](https://doi.org/10.1111/0022-1082.00163). No es evidencia de un efecto calendario concreto, pero sí fundamenta corregir por la familia completa de variantes exploradas.

## Límites de inferencia y preguntas abiertas

La evidencia citada estudia principalmente acciones y períodos históricos específicos. No demuestra que un patrón se traslade a ETF, futuros, FX, CFDs o cripto, ni que sobreviva a cambios de horario, mercado, feed y costos. En particular, una vela diaria del proveedor puede no coincidir con la sesión del venue; asignar mal la fecha o mezclar retornos overnight e intradía puede alterar la pauta medida.

Para Alphaca quedan abiertas estas preguntas:

1. ¿Qué benchmark e instrumento se analizarán, y cuál será su fuente primaria de precios?
2. ¿Qué sesión, zona horaria, reglas DST y calendario oficial definirán cada fecha?
3. ¿La predicción se refiere al retorno viernes-cierre a lunes-apertura, al lunes intradía o al cierre-a-cierre?
4. ¿El patrón se mantiene fuera de muestra, después de registrar y corregir el universo de días, ventanas y mercados probados?
5. ¿Persiste con precios ejecutables, cobertura verificada y costos del instrumento?

Hasta fijar esas definiciones y probar los datos, la pauta sigue siendo una hipótesis; la literatura no constituye evidencia de un edge propio.

## Evidencia empírica y datos

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Revisión de evidencia empírica y datos · estacionalidad y calendario

**Fecha UTC:** 2026-11-20  
**Alcance:** revisión de metadatos, inventario y documentación del repo. No se leyeron CSV de mercado, no se descargaron datos, no se midió cobertura ni se ejecutó un backtest.

## Estado de la evidencia

La ficha de lunes en acciones amplias de EE. UU. sigue en `data_pending`. La documentación registra una hipótesis histórica motivada por French (1980), pero aún no define el benchmark, el instrumento ejecutable ni la convención primaria del retorno. El retorno viernes-cierre a lunes-apertura y el cierre-a-cierre del lunes son preguntas diferentes y no deben combinarse después de ver resultados.

La auditoría local declara un inventario de 528 CSV generado a partir de rutas y nombres. Sus rangos son nominales; `coverage_pct` permanece desconocido y los huecos no se midieron. El manifiesto indica que sus metadatos se derivan de los archivos, pero no confirma el proveedor ni la integridad del feed. Las colecciones MongoDB no se consultaron.

| Tema | Descrito en el repo | Verificado en esta corrida |
|---|---|---|
| Hipótesis de lunes | Estado `data_pending`; QQQ se menciona como posible proxy, con una notebook que usaría `yfinance`, inicio nominal 1999-01-01 y `auto_adjust=True`. | Se verificaron la ficha YAML y los documentos de auditoría. No se verificaron la descarga ni sus observaciones. |
| CSV y rangos | El inventario registra rutas asociadas a Axi, Darwinex y Dukascopy, con metadatos nominales en algunos nombres de archivo. | Se revisó la documentación e inventario textual. No se abrió ningún CSV ni se confirmó su contenido. |
| Futuros ES, NQ, 6E, 6J | Las notebooks EDA se describen como usuarias de colecciones MongoDB. | No se consultaron colecciones, credenciales, símbolos de contrato ni metadatos de proveedor. |
| Cobertura y huecos | La auditoría deja cobertura desconocida y huecos sin medir. | Siguen desconocidos; no se calcularon porcentajes. |
| Sesiones, zona horaria y costos | Se identifican como metadatos pendientes de registrar por dataset. | No se verificaron calendarios, horarios, DST, costos ni diferencias de feeds. |
| Backtests y gates | El handoff declara que no se ejecutaron pruebas ni se registraron edges o casi-pasa. | No se ejecutó ninguna prueba en esta revisión. |

## Calidad y prioridad de datos por instrumento

La hipótesis apunta a acciones amplias de EE. UU., no a todos los símbolos de las notebooks EDA. La evidencia publicada sobre acciones históricas sirve para formular la pregunta, pero no reemplaza la fuente del instrumento elegido.

| Instrumento o fuente descrita | Valor para esta hipótesis | Pendientes antes de usar |
|---|---|---|
| Índice amplio de acciones de EE. UU. | Benchmark adecuado para definir el fenómeno, si se selecciona uno concreto. | No hay una serie identificada en la ficha. Elegir benchmark, proveedor, periodo, tratamiento de dividendos y calendario oficial. Distinguir el retorno del índice de la ejecución en un producto negociable. |
| QQQ vía `yfinance` en EDA | Posible proxy descriptivo; su uso está descrito en la ficha, no verificado aquí. | Registrar proveedor y método de adquisición, fechas observadas, ajustes, sesiones y diferencias frente al broker. La serie autoajustada no representa por sí sola precios de fills. La auditoría de fuentes no considera garantizada una descarga gratuita larga ni aprobada la serie local tipo Yahoo. |
| ES, NQ, 6E, 6J vía MongoDB | No son sustitutos de un índice de acciones; requieren hipótesis separadas si se quieren investigar. | Identificar broker/feed, contratos, sesiones, zona horaria, settlement, rollover, huecos, bid/ask y costos. No se consultaron las colecciones. |
| USDJPY, WTIFS, BTCUSD, BTCJPY y otros feeds OTC/CFD o cripto | No son evidencia directa ni sustitutos de acciones amplias de EE. UU. | Si se estudian, crear fichas independientes. Verificar instrumento, fuente primaria, horario, especificación histórica, spread, swaps/financiación y costos por periodo. |
| Dukascopy u otro proveedor alternativo | Puede servir como contraste cuando cubra el instrumento; no replica automáticamente el feed de ejecución. | Documentar lado de cotización, sesiones, bid/ask, horario y periodo. No empalmarlo silenciosamente con el feed primario. Si el resultado depende del feed alternativo o de un empalme, marcar `NO CONFIRMADO`. |

**Prioridad recomendada:** escoger primero el benchmark y el instrumento ejecutable. Obtener el historial del broker/venue de ese instrumento para la prueba principal y usar una fuente externa solo como contraste identificado. Si el objeto de estudio es un índice y no un ETF o futuro, aclarar si se busca una pauta descriptiva de benchmark o una estrategia ejecutable.

## Calendario, zona horaria y cobertura

No hay cobertura porcentual verificada para la ficha de lunes. Tampoco se ha demostrado que las rutas nominales cubran todas las sesiones esperadas, ni que sus timestamps correspondan a la fecha de negociación del mercado objetivo.

Antes de etiquetar lunes, el dataset debe conservar el timestamp original y su convención de origen; especificar la zona horaria IANA, la conversión a UTC y la regla para obtener la fecha de negociación; y usar un calendario versionado del venue que recoja festivos, sesiones cortas, cierres extraordinarios y cambios de horario. Para una serie de QQQ deben documentarse sesión regular o extendida, ajustes corporativos y comparación con el feed ejecutable. Para futuros deben añadirse contrato, settlement y regla de rollover. Para productos OTC/FX/cripto deben verificarse horario del servidor, cierres y cambios históricos de especificación.

La cobertura debe calcularse solo después de fijar ese calendario y el intervalo que se espera observar. Informar observaciones esperadas y presentes, huecos y duplicados por periodo o sesión; no interpolar ni usar la fecha inicial declarada en un nombre de archivo como prueba de continuidad.

## Costos y diferencias entre feeds

Una diferencia estadística entre días no demuestra que exista una oportunidad negociable. Si se evalúa una regla ejecutable, hay que especificar el momento de entrada y salida y usar precios alcanzables, incluyendo spread, comisión y slippage; incorporar swaps, financiación o costos de rollover cuando correspondan. En el caso de QQQ, separar precios ajustados para medir retornos de precios y condiciones de ejecución para fills. En otros productos, no asumir que un cierre, midpoint o precio de un feed externo es el fill del broker.

Comparar las series por fechas y sesiones comunes y documentar ajustes, horarios, bid/ask y divergencias. Un resultado que solo aparece con datos sustitutos, rellenos o feeds empalmados queda como `NO CONFIRMADO`.

## Plan mínimo reproducible para cerrar pendientes

1. **Fijar la prueba:** decidir benchmark, instrumento ejecutable, proveedor primario, intervalo y retorno primario antes de examinar resultados. Registrar por separado viernes-cierre a lunes-apertura y cierre-a-cierre si se investigan ambos, e incluir ambos en el universo de pruebas.
2. **Completar metadatos de origen:** guardar instrumento y símbolo, broker/venue, método de adquisición, granularidad, lado de cotización, ajustes, timestamps originales, zona horaria, periodo esperado y fecha de extracción. No consultar feeds o bases que requieran acceso no disponible.
3. **Definir calendario:** obtener la fuente oficial pertinente y fijar sesiones, festivos, cierres parciales, DST y regla de fecha de negociación; versionar el calendario utilizado.
4. **Auditar integridad:** comparar observaciones con el calendario esperado; calcular cobertura por sesión y periodo, y reportar faltantes, duplicados, discontinuidades y diferencias entre feeds. Mantener huecos sin rellenar.
5. **Reconciliar ejecución:** documentar precios negociables, spread, comisión, slippage y costos de tenencia aplicables. Comparar cualquier feed externo con el primario en fechas comunes; informar por separado los tramos que no coincidan.
6. **Registrar resultado de auditoría:** completar metadatos por serie y actualizar la ficha solo con valores calculados y método reproducible. Si falta una definición de calendario, un origen verificable o cobertura suficiente, mantener `data_pending`.

## Evidencia mínima para pasar a notebook de estrategia

Para esta hipótesis, antes de construir una notebook de estrategia se requiere benchmark e instrumento fijados; definición primaria del retorno y timestamp ejecutable; fuente primaria identificada; calendario y zona horaria documentados; y cobertura y huecos calculados contra las sesiones esperadas. Debe alcanzarse el gate inicial de **al menos 98% de cobertura**, sin rellenar huecos. Registrar si la muestra ofrece al menos 100 eventos/trades independientes o dejar explícita la limitación de potencia.

Ese paso solo habilita la prueba; no confirma un edge. Para declarar evidencia confirmatoria siguen pendientes los demás gates comunes: controlar comparaciones múltiples (`FDR q <= 0.05` como criterio predeterminado), métrica neta de costos con límite inferior del IC bootstrap del 95% mayor que cero fuera de muestra, resultado positivo agregado y en al menos dos de tres ventanas OOS cronológicas, robustez de al menos 70% de parámetros vecinos y resultado aún positivo con estrés de costos de 2x spread y comisión. También se requiere reproducir la conclusión en el feed primario.

## Crítica independiente / red team

*Motor:* `codex/gpt-6-luna/high (ChatGPT OAuth)`

# Red team · Diferencia de retorno del lunes en acciones amplias de EE. UU.

**Alcance:** revisión crítica de la ficha `weekday_returns/us_equity_index/hypothesis.md` y del contexto suministrado. No se consultaron datos ni se ejecutaron pruebas. No hay evidencia local de un edge.

## Veredicto

**Pendiente; no pasar todavía a un notebook de estrategia.** La ficha plantea una pregunta histórica razonable, pero no fija el benchmark, el instrumento ejecutable, el intervalo de retorno ni el periodo de evaluación. La condición de comparar viernes-cierre a lunes-apertura con lunes cierre-a-cierre está expresada como una decisión futura, no como una predicción ya especificada.

La evidencia citada motiva la investigación en acciones estadounidenses; no establece que el efecto siga vigente ni que pueda operarse neto de costos. La ficha reconoce parte de esta limitación.

## Objeciones

| Severidad | Objeción | Prueba que podría refutarla |
|---|---|---|
| **Bloqueante** | **La predicción admite resultados distintos.** “La distribución o expectativa” puede significar una diferencia de medias, de distribución o de riesgo. Además, las dos ventanas propuestas incluyen exposiciones distintas; escoger la que dé mejor resultado después de mirar los datos sería selección retrospectiva. | Antes de consultar resultados, fijar una métrica primaria, el signo o contraste esperado, la ventana exacta, las reglas de entrada y salida y el benchmark. Registrar la otra ventana como análisis secundario. Evaluar ambas con datos cronológicos reservados. |
| **Bloqueante** | **Benchmark e instrumento no están definidos.** Un índice amplio, QQQ y un futuro sobre índice no son intercambiables. El índice puede servir de referencia estadística, pero no especifica un precio alcanzable, spread, comisiones, horario ni fills. La serie QQQ de `yfinance` mencionada en la ficha tampoco acredita ejecución en el broker. | Definir una hipótesis por instrumento y fuente primaria. Contrastar el retorno del benchmark con precios y costos del instrumento operable; probar sensibilidad con un feed alternativo identificado, sin sustituir silenciosamente el primario. |
| **Bloqueante** | **La convención de sesión puede cambiar la asignación del día.** Faltan calendario, timezone, tratamiento de DST, feriados, cierres parciales y definición del cierre y la apertura. Un retorno que atraviesa el fin de semana puede incorporar sesiones o timestamps distintos según la fuente. | Conservar timestamp original, documentar zona IANA y calendario histórico del venue, y comparar la asignación contra timestamps de exchange. Informar cobertura por sesión y excluir o modelar por separado cierres parciales según una regla predefinida. |
| **Alta** | **La búsqueda múltiple puede convertir al lunes en ganador por azar.** La ficha alude a ajustar pautas alternativas, pero no especifica cuáles ni cómo incluirá otros días, ventanas, activos o subperiodos que se hayan probado. Corregir solo por las variantes finalmente reportadas no controla la búsqueda completa. | Congelar el universo de pruebas y registrar también las exploraciones descartadas. Aplicar una corrección adecuada a la familia completa —por ejemplo, un procedimiento tipo Reality Check cuando corresponda— y validar la regla primaria en un holdout cronológico intacto. |
| **Alta** | **Dependencia temporal e independencia de observaciones.** Los retornos semanales pueden tener dependencia serial y los contrastes entre días comparten condiciones de mercado. Contar cada lunes como un evento independiente podría inflar precisión y dar una lectura demasiado optimista de los gates de muestra. | Informar número de semanas y eventos, revisar autocorrelación y usar inferencia robusta al horizonte, como bootstrap por bloques o errores HAC apropiados. Justificar qué cuenta como evento independiente antes de aplicar el mínimo de muestra. |
| **Alta** | **Un cierre o una apertura publicados no garantizan un fill.** La subasta, el spread, la latencia, los precios stale y el slippage pueden concentrar diferencias justo en los extremos de sesión. Una diferencia estadística del índice puede no sobrevivir en el precio negociable. | Separar retorno de benchmark, mid y PnL ejecutable. Simular entradas y salidas con quotes o fills del instrumento, costos variables por horario y supuestos de ejecución conservadores; repetir con estrés de costos 2x. |
| **Alta** | **El cambio de régimen puede borrar o invertir la regularidad histórica.** French (1980) estudia 1953–1977. Esa muestra no establece persistencia hasta 2026, ni tras cambios de mercado, reglas de subasta, composición o microestructura. | Mostrar resultados por ventanas cronológicas predefinidas y en al menos dos tercios de ventanas OOS. Examinar cambios institucionales sin diseñar filtros de régimen después de ver los resultados. |
| **Media** | **La medición del índice puede incorporar revisiones o reglas cambiantes.** Para un índice histórico se debe verificar si la serie representa el índice tal como se publicó en cada fecha, cómo trata dividendos y ajustes, y si la metodología o fuente cambió. El sesgo de supervivencia es especialmente relevante si se reemplaza el índice por acciones actuales. | Identificar proveedor, tipo de índice (precio o retorno total), ajustes y metodología histórica. Si se usa un universo de acciones, emplear composición point-in-time, delistings y acciones corporativas; tratar esa prueba como una hipótesis distinta. |
| **Media** | **La propuesta no identifica un mecanismo.** El intervalo de fin de semana puede acumular noticias, pero eso no demuestra que la diferencia sea causada por el calendario ni que sea predecible antes de ejecutar. Anuncios, rebalanceos y cierres fiscales pueden producir exposiciones coincidentes. | Mantener la hipótesis como descriptiva salvo que se preregistre una predicción causal más concreta. Si se investiga un mecanismo, usar calendarios de eventos disponibles ex ante y analizarlo por separado, sin reinterpretar el resultado principal. |

## Revisión de las gates

El handoff enumera gates generales: cobertura ≥98%, muestra objetivo ≥100 eventos/trades independientes, FDR q≤0.05, límite inferior del IC bootstrap 95% de la métrica neta >0, resultado agregado positivo y en ≥2/3 de ventanas OOS, ≥70% de parámetros vecinos positivos y positividad bajo estrés de costos 2x spread/comisión.

Están **especificadas a nivel de familia**, pero la ficha no convierte varias en criterios operativos para esta hipótesis. Antes de analizar, debe definir:

- Qué cobertura se mide y cuál es el denominador de sesiones esperadas.
- Qué evento cuenta como independiente y cómo se aplica el umbral de muestra al horizonte elegido.
- La métrica neta primaria, el método de bootstrap y la familia concreta de pruebas para FDR.
- Las ventanas OOS cronológicas y los parámetros vecinos pertinentes. Para una hipótesis categórica de día de semana, “parámetros vecinos” necesita una definición concreta o una justificación de por qué no aplica.
- La regla de ejecución, sus costos y el benchmark de comparación.

Las gates son umbrales de revisión, no resultados ni garantía de potencia estadística.

## Fallos bloqueantes y mejoras

**Bloqueantes para probar:** instrumento y benchmark sin fijar; ventana y métrica primaria sin elegir; calendario, sesión y fuente ejecutable sin verificar; y universo de pruebas sin registrar. Con esos elementos abiertos, el resultado podría depender de decisiones tomadas después de observar los datos.

**Mejoras previas:** especificar la hipótesis en una sola regla primaria; documentar fuente, cobertura y reglas de sesión; definir el holdout antes del análisis; y predefinir cómo se medirá PnL neto y dependencia temporal. Mantener separadas las pruebas del índice y del producto operable.

## Conclusión

**Veredicto de investigación: pendiente (`data_pending`).** La pregunta puede pasar a una fase de definición y auditoría de datos. La ficha no está lista para evaluar un edge ni para escoger una variante de calendario con base en resultados. Sólo debería pasar a notebook de estrategia después de resolver los bloqueantes y aplicar las gates indicadas.

## Datos, cobertura y pendientes

No se leyeron CSV de mercado en esta corrida. El origen, la cobertura porcentual y los huecos deben verificarse por dataset usando la prioridad broker → Dukascopy para CFDs y una fuente licenciada/apropiada para ETFs. No interpolar ni empalmar series sin registrarlo. Si una conclusión requiere datos rellenados o feeds empalmados, marcarla `NO CONFIRMADO`.

## Control de calidad

Cualquier fuente citada debe ser anterior a 2018 y contener DOI o URL estable. Las referencias que no pudieron verificarse deben aparecer explícitamente como `no verificada`; no son evidencia de apoyo hasta revisión humana.
