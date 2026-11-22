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