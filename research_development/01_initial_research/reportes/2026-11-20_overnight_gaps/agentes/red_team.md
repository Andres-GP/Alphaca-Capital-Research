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