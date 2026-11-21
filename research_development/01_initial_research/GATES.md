# Gates iniciales y criterios de decisión

Estos son criterios operativos iniciales para seleccionar hipótesis que merecen pruebas de estrategia. No son resultados empíricos, no validan un edge y no sustituyen controles más estrictos que requiera el mercado. Registrar cualquier excepción y justificarla en la ficha.

## Gate A · Investigación inicial → backtest exploratorio

Una corrida inicial no ejecuta ni prueba automáticamente cada idea. Solo se propone backtestear una hipótesis concreta cuando la revisión de viabilidad la marca `READY_FOR_EXPLORATORY_BACKTEST` y existe un preregistro completado en [`templates/backtest_preregistration.yaml`](templates/backtest_preregistration.yaml). Un `HOLD_DATA` o `HOLD_SPECIFICATION` significa que no se ejecuta el backtest; `REFORMULATE` exige corregir la ficha; `REJECT` cierra la hipótesis con su motivo.

Requisitos para `READY_FOR_EXPLORATORY_BACKTEST`:

- Hipótesis falsable y una sola pregunta primaria; instrumento, venue, universo, frecuencia y horizonte definidos.
- Reglas de señal, entrada, salida, sizing y manejo de posiciones especificadas sin ambigüedad y antes de mirar resultados.
- Dataset seleccionado con origen, instrumento, frecuencia, zona horaria, sesiones/calendario, ajustes, intervalo, huecos y método de cobertura documentados. Cobertura medida contra el calendario esperado >=98%; no rellenar huecos para superar el umbral.
- Costos y condiciones de ejecución incluidos (spread, comisión, slippage y swaps/financiación si aplica); si no pueden estimarse, se mantiene `HOLD_DATA`.
- Período y división cronológica de descubrimiento/validación definidos, métrica primaria fijada y número de variantes/pruebas planeado registrado.
- Sin dependencia de feed sustituto o tramos empalmados para pasar el gate. Cualquier dependencia no confirmada bloquea el paso.

El backtest que sigue es **exploratorio**: comprueba que la especificación se puede implementar y puede descartar una hipótesis, pero no la confirma ni autoriza llamarla edge. No se cambian reglas tras ver resultados; cualquier cambio crea una nueva versión preregistrada.

## Gate B · Backtest exploratorio → validación confirmatoria

- Registrar el artefacto reproducible, versión de código, datos, configuración y resultados, incluidos errores y variantes probadas.
- Si la definición, los datos, la cobertura o los costos resultan incorrectos, detener y reformular; no interpretar el PnL como evidencia.
- Para proponer validación confirmatoria, congelar la especificación y el universo de pruebas, y usar datos fuera de muestra aún no consultados.

## Gate C · Para declarar evidencia empírica confirmatoria

- Mecanismo económico/estructural y predicción falsable definidos antes de mirar el resultado.
- Al menos una fuente anterior a 2018 verificada y pertinente al mecanismo; citar límites de aplicabilidad. La falta de literatura no demuestra que no exista efecto, pero obliga a marcar la motivación como exploratoria.
- Dataset con metadatos completos y al menos 98% de cobertura del calendario/sesiones esperados. No rellenar huecos para pasar el umbral. Si solo pasa con feed sustituto o datos completados, marcar `NO CONFIRMADO`.
- Tamaño de muestra previsto suficiente para evaluar la predicción; registrar la potencia o la limitación si no alcanza 100 eventos/trades independientes. El umbral de 100 es un filtro mínimo de revisión, no garantía de potencia.

## Para declarar evidencia empírica confirmatoria

- Definir una métrica primaria y controlar el universo de pruebas; para familias de hipótesis, usar ajuste de comparaciones múltiples (FDR `q <= 0.05` como default).
- Métrica primaria neta de costos positiva y límite inferior del intervalo de confianza bootstrap de 95% mayor que cero en datos fuera de muestra. Preservar dependencia temporal con bloques apropiados.
- Robustez temporal: expectativa neta positiva en al menos 2 de 3 ventanas fuera de muestra cronológicas y resultado agregado positivo; no depender de un único año o episodio.
- Robustez paramétrica: al menos 70% de parámetros vecinos predefinidos conservan expectativa neta positiva. Registrar la grilla antes de evaluar.
- Costos: sigue positivo después de spread/comisión/slippage observados y en un escenario de estrés de 2x spread y comisión; incluir swaps/financiación cuando apliquen.
- Reproducir la conclusión con fuente primaria del broker. Si el resultado solo aparece con datos rellenados o un feed alternativo, conservar estado `NO CONFIRMADO`.

Si falla un gate, registrar la causa y decidir `pendiente` (falta de datos/potencia), `reformular` (mecanismo o medición ambiguos) o `descartar` (predicción falsada o edge económico eliminado por costos). No mover umbrales a posteriori para rescatar una pauta.
