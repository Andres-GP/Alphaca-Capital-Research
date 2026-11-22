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