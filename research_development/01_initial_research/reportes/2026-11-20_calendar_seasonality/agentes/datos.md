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