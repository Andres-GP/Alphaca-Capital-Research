# Informe de evidencia y datos · carry y valor relativo

**Fecha UTC:** 2026-11-20  
**Estado:** no se verificó un conjunto de datos ejecutable para ninguna pauta de la familia. No se leyeron series CSV de mercado, no se descargaron ni interpolaron datos y no se calculó cobertura en esta corrida. La ficha de forwards G10 continúa en `data_pending`.

## Qué está descrito y qué se verificó

**Descrito en los archivos de la familia:** hay referencias a históricos Axi de USDJPY y EURGBP, series de petróleo rotuladas USOIL/WTIFS y XTIUSD de Axi o Darwinex, y colecciones Mongo para ES/NQ/6E/6J. No se localizaron forward points G10, swaps históricos, curvas de futuros por vencimiento, inventarios ni costes de financiación. Esas referencias identifican candidatos, no validan un edge ni su disponibilidad en una cuenta.

**Verificado en esta corrida:** se revisaron los archivos de auditoría e inventario del repositorio, sin abrir los CSV de mercado. El manifiesto existente registra ventanas nominales, marcas temporales y algunos controles básicos de formato para varias series. A la vez, deja la procedencia sin verificar, la cobertura sin calcular y la zona horaria de los CSV etiquetados Axi/Darwinex como desconocida. No revalidé esos metadatos contra los archivos originales.

El manifiesto registra, por ejemplo, USDJPY M5 de Axi con fechas nominales 2000-01-02 a 2026-11-03, EURGBP M5 de Axi de 2017-01-02 a 2026-11-06, WTIFS H1 de 2008-02-18 a 2026-11-02 y XTIUSD H1 de Darwinex de 2010-05-02 a 2026-11-02. Las fechas son ventanas nominales del inventario; **no demuestran cobertura continua**. El control anterior cuenta huecos brutos mayores a cuatro días naturales en orden de archivo, pero no contrasta sesiones ni festivos. Un conteo cero no demuestra continuidad; un conteo positivo requiere investigar el tramo.

| Instrumento o candidato | Evidencia local del inventario | Limitación para carry/valor relativo |
|---|---|---|
| FX USDJPY / EURGBP | CSV M5 etiquetados Axi; USDJPY también tiene una serie M5 Darwinex de ventana nominal mucho más corta. | Spot no aporta forward points, financiación ni swaps históricos. Proveedor, zona horaria, sesiones, spread ejecutable y especificación no están confirmados. USDJPY aislado tampoco constituye una cartera transversal G10. |
| Petróleo WTIFS / USOIL / XTIUSD | CSV H1 etiquetados Axi/Darwinex, con ventanas nominales largas. | Los nombres no prueban si son CFDs, qué subyacente replican ni qué ajustes/rollover aplican. No se identificó una cadena de contratos con vencimientos negociables; no se puede inferir basis de futuros de una serie spot/CFD. |
| Futuros ES/NQ/6E/6J | Notebooks EDA mencionan colecciones Mongo como `es_15min`, `nq_15min`, `6e_15min` y `6j_15min`. | No se consultó Mongo ni se identificaron proveedor, contrato, calendario, settlement, reglas de roll o financiación. |
| Pares/acciones/ETF | Hay referencias generales a QQQ y a datos de acciones en otros análisis del repositorio. | No se verificó un universo de pares definido para esta familia ni datos sincronizados con dividendos, borrow, financiación y costes de ambos lados. |

## Fuentes prioritarias y datos faltantes

1. **FX forwards G10:** primero, datos históricos point-in-time de spot y forward points bid/ask para un universo y fixing definidos, idealmente de un proveedor ejecutable o institucional con metadatos de timestamp y settlement. Como comprobación independiente, conservar tasas oficiales de cada moneda con hora de publicación; esas tasas pueden servir para contraste, pero no reemplazan forwards observados ni los swaps de un CFD. Faltan además universo G10 point-in-time, calendarios de settlement y festivos, coste por lado, rollover y slippage.
2. **CFD FX del broker:** obtener especificaciones del símbolo y el historial de swaps/financiación por lado y fecha, incluidos días de cargo múltiple, cambios de condiciones y calendario de rollover. Añadir cotizaciones bid/ask o spreads históricos y comisiones de la cuenta. No imputar forward points institucionales como si fueran financiación retail.
3. **Basis de futuros de commodities:** identificar primero el subyacente, venue y contrato exactos detrás de WTIFS/USOIL/XTIUSD. Después obtener settlements y cotizaciones por vencimiento, especificaciones, volumen/liquidez, regla de roll fijada ex ante y costes de ejecución. Para investigar inventarios, añadir una serie histórica de fuente primaria con fecha de publicación y vintage disponible entonces. Un CFD aislado no cierra este requisito.
4. **Futuros ES/NQ/6E/6J:** documentar el origen y esquema de las colecciones, contratos individuales, zona horaria, calendario de sesión, settlement y roll. Si no se accede a Mongo, la disponibilidad de esas series queda pendiente.
5. **Pares/valor relativo:** fijar instrumentos y universo antes del test; obtener precios sincronizados bid/ask, timestamps y divisas, junto con dividendos, borrow, financiación, vencimientos y costes de ambos legs. No hay evidencia local verificada de que las parejas candidatas tengan datos suficientes para una prueba de esta familia.

## Plan mínimo reproducible

Para cada pauta, guardar un manifiesto versionado con proveedor, instrumento y contrato, licencia/forma de adquisición, granularidad, timezone IANA y convención DST, sesión y calendario, primera y última observación, fecha de descarga, ajustes, campos disponibles y costes. Conservar timestamps originales y normalizados a UTC; no unir series por fecha sin verificar cuándo estaba disponible cada dato.

Definir antes de medir cobertura el calendario esperado de cada instrumento y granularidad. Comparar observaciones contra ese calendario para calcular cobertura, huecos de sesión, duplicados, timestamps fuera de orden y barras ausentes; investigar los huecos antes de cualquier backtest. El valor de cobertura sigue **desconocido** hasta ese cálculo. No rellenar ausencias.

Comparar feeds en un tramo solapado y horario común, usando timestamps y cotizaciones compatibles. Registrar por separado diferencias de sesión, spread, bid/ask, precios, roll, swaps y especificaciones; no empalmar feeds para presentar una historia única. Si una conclusión depende de una serie sustituta, ajustada o empalmada, etiquetarla **NO CONFIRMADO** y reportar los tramos y resultados por feed.

Para G10, el paquete mínimo debe incluir moneda base, universo point-in-time, fixing, maturities, retornos spot y forward/funding, costes, calendarios y momento de disponibilidad de cada input. Para futuros, debe contener contratos por vencimiento y la regla de roll reproducible. Para pares, debe incluir timestamps sincronizados y todos los flujos/costes de los dos legs.

## Evidencia necesaria antes de pasar a notebook

Puede prepararse un notebook de **auditoría de datos** cuando estén definidos los instrumentos, el calendario esperado y los archivos con procedencia y timestamps documentados. Para pasar a un notebook de estrategia, la evidencia mínima es: cobertura calculada de al menos 98% según el gate común; costes y financiación históricos aplicables; fuentes point-in-time; y conciliación de diferencias entre feeds. La hipótesis de forwards G10 requiere forwards/forward points o una convención de tasas documentada y disponible en cada fecha; spot M5 de USDJPY por sí solo no basta.

Aun si se completa ese paquete, los gates estadísticos, de muestra, robustez, costes estresados y ventanas fuera de muestra siguen pendientes. No se ejecutaron backtests ni se identificaron casos casi-pasa.