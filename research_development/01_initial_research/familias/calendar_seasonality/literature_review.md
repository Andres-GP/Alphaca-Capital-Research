# Revisión de literatura · Estacionalidad y calendario

**Corte temporal:** evidencia publicada hasta 2017-12-31.  
**Estado:** revisión bibliográfica inicial; no se consultaron datos locales ni se ejecutaron backtests. No confirma un edge en ningún instrumento de Alphaca.

## Alcance

Los efectos de día de semana, turno de mes/año, feriados e intradía son hipótesis distintas. Cambian la definición de calendario, el intervalo de retorno, la frecuencia y los mecanismos posibles. No agruparlos bajo una ficha ni inferir que un patrón documentado en acciones estadounidenses se traslada a futuros, CFDs, ETF, FX o cripto.

## Evidencia primaria anterior a 2018

### [R1] Día de semana y fin de semana

Kenneth R. French (1980), “Stock Returns and the Weekend Effect”, *Journal of Financial Economics*, 8(1), 55–69. [Artículo/DOI de Elsevier](https://doi.org/10.1016/0304-405X(80)90021-5).

Con retornos diarios del portafolio S&P Composite entre 1953 y 1977, French reporta retornos promedio de lunes significativamente negativos en cada uno de cinco subperiodos. El patrón no encaja con las dos hipótesis simples de tiempo calendario y tiempo negociado que contrasta.

**Qué sustenta:** formular pruebas sobre retornos por día de semana y distinguir periodo no negociado de sesión activa.  
**Qué no sustenta:** que el efecto sea una prima causal, que ocurra en otro mercado/feed o que sobreviva costos actuales y tests múltiples.

### [R2] Patrones de largo plazo alrededor de cambios de calendario

Josef Lakonishok y Seymour Smidt (1988), “Are Seasonal Anomalies Real? A Ninety-Year Perspective”, *The Review of Financial Studies*, 1(4), 403–425. [Artículo/DOI de Oxford Academic](https://doi.org/10.1093/rfs/1.4.403).

Usando 90 años de datos diarios del Dow Jones Industrial Average, evalúan la persistencia de patrones estacionales. Reportan retornos anómalos persistentes alrededor del cambio de semana, cambio de mes, cambio de año y feriados, y discuten problemas metodológicos de los tests de estacionalidad.

**Qué sustenta:** usar muestras extensas y examinar calendario de semana, mes, año y feriados con controles metodológicos.  
**Qué no sustenta:** rentabilidad neta ejecutable en un activo concreto ni que cada subpauta conserve el mismo signo en periodos recientes.

### [R3] Turno de mes

Ronen A. Ariel (1987), “A Monthly Effect in Stock Returns”, *Journal of Financial Economics*, 18(1), 161–174. [Artículo/DOI de Elsevier](https://doi.org/10.1016/0304-405X(87)90066-3).

El resumen del artículo reporta que el retorno medio de acciones fue positivo principalmente en los días inmediatamente anteriores y en la primera mitad del mes calendario; para la segunda mitad fue indistinguible de cero según la muestra estudiada.

**Qué sustenta:** una pregunta falsable sobre retorno por posición dentro del mes en acciones.  
**Qué no sustenta:** que la misma ventana o magnitud se replique en un ETF o en productos OTC, ni una explicación única del patrón.

### [R4] Descomposición intradía del efecto semanal

Lawrence Harris (1986), “A Transaction Data Study of Weekly and Intradaily Patterns in Stock Returns”, *Journal of Financial Economics*, 16(1), 99–117. [DOI](https://doi.org/10.1016/0304-405X(86)90044-9) · [copia del artículo](https://www-2.rotman.utoronto.ca/~kan/3032/pdf/FinancialAssetReturns/Harris_JFE_1986.pdf).

Con datos de transacciones de acciones, el autor reporta que el retorno negativo de lunes se concentra en franjas distintas según tamaño de empresa; para firmas grandes aparece entre el cierre del viernes y la apertura del lunes. También documenta diferencias intradía entre días en los primeros 45 minutos tras la apertura.

**Qué sustenta:** separar retornos overnight y dentro de sesión antes de atribuir un patrón al día de semana.  
**Qué no sustenta:** que una pauta intradía sea rentable neta; el propio artículo concluye que las reglas basadas solo en esos patrones semanales e intradía no serían rentables debido a costos de transacción. Tampoco demuestra replicabilidad con velas de otro proveedor.

### [R5] Data snooping en reglas técnicas y de calendario

Ryan Sullivan, Allan Timmermann y Halbert White (1999), “Data-Snooping, Technical Trading Rule Performance, and the Bootstrap”, *The Journal of Finance*, 54(5), 1647–1691. [Artículo/DOI de Wiley](https://doi.org/10.1111/0022-1082.00163).

El estudio evalúa un universo amplio de reglas técnicas y aplica White's Reality Check para considerar data snooping. El paper no es exclusivamente sobre anomalías de calendario, pero su método es pertinente al probar muchas variantes de días, meses, ventanas, horarios e instrumentos.

**Qué sustenta:** contabilizar la búsqueda completa de reglas en lugar de reportar solo el ganador y aplicar inferencia que considere data snooping.  
**Qué no sustenta:** un umbral estadístico universal para toda pauta o una validación automática en los mercados del repo.

## Mecanismos posibles y explicaciones alternativas

- Flujos de efectivo y rebalanceos alrededor de fechas periódicas podrían crear presión temporal; debe medirse y distinguirse del mero patrón descriptivo.
- Procesamiento de información y anuncios pueden concentrarse en ciertas horas/días; se necesita timestamp de publicación y retorno ejecutable para probarlo.
- Horarios de mercado, fin de semana, subasta de apertura/cierre, bid-ask bounce y convenciones del proveedor pueden producir diferencias medidas sin una prima negociable.
- Variación de volatilidad, composición del universo, microestructura y cambios estructurales pueden explicar que una anomalía histórica se debilite o desaparezca.

Estos mecanismos son explicaciones a investigar, no conclusiones causales de la literatura arriba resumida.

## Aplicabilidad preliminar a Alphaca

La carpeta EDA contiene notebooks para ES, NQ, 6E, 6J, WTIFS, QQQ, USDJPY, BTCUSD y BTCJPY. El símbolo no identifica por sí solo el venue, feed, calendario o cobertura. Las fuentes R1–R5 estudian principalmente acciones; sirven para formular preguntas y controles, pero no son evidencia directa para los productos listados en las notebooks. Para cada mercado se debe documentar timezone, sesión, DST, festivos, hora de settlement/cierre, rollover y huecos.

## Preguntas falsables para fichas posteriores

1. Para un instrumento, calendario de sesión y fuente fijados ex ante, ¿difiere el retorno entre días de semana o periodos de mes/año fuera de muestra, frente a días de control, neto de costos?
2. ¿La diferencia aparece overnight o durante la sesión? Usar datos con timestamps y precios bid/ask cuando sea posible; comparar con datos agregados solo como sensibilidad.
3. ¿Sobrevive al controlar el universo completo de calendarios, subperiodos y mercados explorados, y a corrección de pruebas múltiples?
4. ¿El patrón es estable por régimen y periodo, o depende de unas pocas fechas/mercados?

Estas son preguntas; ninguna prueba local se ejecutó. La ficha concreta debe elegir una sola pauta, un calendario y un mercado antes de explorar resultados, registrar todo el universo de tests y aplicar los gates comunes de [`../../GATES.md`](../../GATES.md).

## Referencias

Todos los artículos indicados fueron publicados antes del corte y se enlazan a DOI/editoriales o al texto primario. No se infieren resultados en instrumentos del repositorio a partir de sus abstracts.
