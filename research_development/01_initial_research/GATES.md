# Gates iniciales y criterios de decisión

Estos son criterios operativos iniciales para seleccionar hipótesis que merecen pruebas de estrategia. No son resultados empíricos, no validan un edge y no sustituyen controles más estrictos que requiera el mercado. Registrar cualquier excepción y justificarla en la ficha.

## Para pasar de investigación inicial a notebook de estrategia

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
