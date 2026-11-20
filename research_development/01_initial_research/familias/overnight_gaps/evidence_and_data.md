# Gaps y transiciones de sesión · evidencia y datos

**Estado:** revisión bibliográfica inicial e inventario de rutas/código; no es un backtest ni valida una pauta local. **Corte de literatura:** 2017-12-31. No se midió cobertura ni se consultaron credenciales/datasets remotos.

## Definiciones que no deben mezclarse

- **Gap de apertura de acciones:** precio de apertura de la sesión cash frente al cierre previo, con una definición de apertura/close del venue y de precio ejecutable.
- **Retorno overnight de acciones:** cierre-a-apertura; el retorno de día es apertura-a-cierre. No equivale a gap de fin de semana ni a un gap de CFD.
- **Gap de futuros casi continuos:** salto entre sesiones elegidas por la investigación (por ejemplo, cierre cash anterior frente a apertura cash); la negociación electrónica puede continuar durante la noche. Rollovers y pausas de mantenimiento son otro tipo de salto.
- **CFD de broker:** sesión, rollover, horario de servidor, spread y cotización son específicos del proveedor; “gap” respecto del cierre cash o una vela del broker son definiciones distintas.

Toda hipótesis debe registrar la fórmula de gap, ambos precios/timestamps, fuente, timezone, sesión/venue, calendario y regla de ejecución antes de mirar resultados.

## Evidencia primaria anterior a 2018

| Fuente | Hallazgo publicado | Qué motiva | Límite |
|---|---|---|---|
| French & Roll (1986), “Stock Return Variances: The Arrival of Information and the Reaction of Traders”, *Journal of Financial Economics* 17(1), 5–26. [DOI](https://doi.org/10.1016/0304-405X(86)90004-8) | Analizan cómo varía la varianza de retornos con periodos de negociación y cierres; la varianza durante cierres contiene información y puede diferir de la varianza durante negociación. | Separar periodo sin negociación y sesión abierta al analizar retornos close-to-open/open-to-close. | Evidencia sobre varianza/información en acciones, no prueba una estrategia de gap fill ni una señal actual.
| Cooper, Cliff & Gulen (2008), “Return Differences between Trading and Non-Trading Hours: Like Night and Day”, working paper SSRN. [Registro/versión de autores](https://doi.org/10.2139/ssrn.1004081) | Preprint de 2008 descompone retornos de acciones, índices y futuros de índices en día/noche; reporta diferencias entre periodos y destaca que precios de apertura relativamente altos pueden revertir durante la primera hora. | Motiva medir overnight y sesión intradía por separado y estudiar la formación de precios de apertura. | Se cita como working paper/preprint, no como prueba de un gap fill general ni de rentabilidad neta para futuros, CFD o feed local. Verificar versión/metodología completa antes de especificar una ficha.
| Berkman, Koch, Tuttle & Zhang (2012), “Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open”, *Journal of Financial and Quantitative Analysis* 47(4), 715–741. [DOI/editor](https://doi.org/10.1017/S0022109012000270) | Encuentran retornos positivos overnight seguidos de reversión durante el día en acciones, concentrados en acciones de alta atención; señalan que costos implícitos de comprar en la apertura pueden superar el spread efectivo. | Motiva distinguir una diferencia estadística overnight/intradía de una oportunidad ejecutable a la apertura. | Universo de acciones y muestra del estudio; no transferir el efecto o sus magnitudes a QQQ, futuros, CFDs ni símbolos del repo.

La bibliografía respalda investigar componentes de retorno y formación de precios en aperturas. No prueba que un gap de una definición concreta revierta, ni que el resultado sobreviva a costos. No se encontró en esta revisión una fuente pre-2018 que valide directamente una regla general de “gap fill” para los feeds locales; esa falta no demuestra que no haya más literatura.

## Inventario visible en el repositorio

Las rutas/nombres que siguen son observaciones de archivos o código. Las fechas de nombre son nominales y no certifican cobertura, zona horaria, integridad, sesión del proveedor ni cotizaciones ejecutables.

| Mercado/candidato | Evidencia local observada | Fuente/origen identificable | Pendiente antes de usar |
|---|---|---|---|
| ES, NQ (futuros de índices) | Las notebooks EDA cargan `es_15min` y `nq_15min` desde MongoDB y descargan `ES=F`/`NQ=F` de Yahoo para comparación. El código agrupa la sesión con `SESSION_START_HOUR = 18` y desplaza timestamps de esa hora en adelante a la fecha de sesión siguiente. | El código confirma MongoDB y Yahoo como interfaces de lectura/comparación, pero no identifica el broker/feed contenido en las colecciones. La regla 18:00 es una convención escrita en EDA; su timezone y correspondencia con venue no están confirmados. | Rango real, contrato, fuente del broker, calendario y timezone; bid/ask, pausas, close de referencia, rollovers, feriados y gaps por sesión. No tratar `ES=F`/`NQ=F` como ejecución del broker.
| WTIFS / USOIL (CFD de energía) | Archivos locales: `data/axi/wtifs_H1_200802180000_202611021900.csv` y `data/axi/usoil_H1_201007080000_202611021900.csv`; la EDA WTIFS lee CSV locales de Axi. | Identificadores Axi en rutas/nombres, no metadatos verificados del export/feed. | Confirmar símbolo contractual exacto, timestamp/origen, cambio de sesión/rollover, spread variable, swap, cierres semanales y cobertura real. CFD no comparte necesariamente la sesión/close del futuro subyacente.
| USDJPY (CFD/FX broker) | Archivo local `data/axi/usdjpy_M5_200001022200_202611030050.csv`; la EDA identifica export local de Axi. | Etiquetado de ruta/notebook; no se comprobó origen del fichero por metadatos. | Confirmar timezone del servidor, horarios 24/5, pausa diaria/rollover, precio bid/ask, swaps, spread alrededor de reopen y huecos. No asumir que la hora `00` del nombre es UTC.
| BTCUSD (CFD) | Archivo local `data/axi/BTCUSD_H1_201401150200_202611022200.csv`; EDA usa CSV etiquetado Axi/MT5. También existe `data/dukascopy/btcusd_h1_utc.csv`. | Rutas identifican supuestos de origen separados (Axi y Dukascopy); no certifican cobertura ni coincidencia de feed. | CFD puede cotizar casi 24/7, pero horario, spread y pausas pertenecen al broker. Comparar ambos feeds con metadatos; no mezclar huecos como si fueran una sola serie. BTCJPY empieza nominalmente en 2019 y requiere análisis separado.
| QQQ (ETF) / acciones de EE. UU. | La notebook EDA descarga QQQ con `yfinance`, `start="1999-01-01"`, `auto_adjust=True`. Hay numerosos CSV de acciones en `data/t20/prices/`; no se identificó en este inventario una serie local de QQQ. | Yahoo Finance vía la librería es el origen indicado para la EDA, pero la entrega remota depende del momento de descarga. Los CSV de T20 no documentan aquí proveedor ni composición point-in-time. | Precio de apertura/close y zona del mercado, ajustes corporativos frente a fills, timestamps y spread de apertura; descargar datos de broker/venue para ejecución y fijar fuente gratuita versionable para contraste. Los ETFs cash no negocian toda la noche del mismo modo que futuros.

## Metadatos mínimos por dataset de gaps

```yaml
instrument: "<símbolo, contrato, venue y tipo de producto>"
gap_definition: "<precio A/timestamp A frente a precio B/timestamp B>"
origin_type: "broker | dukascopy | other"
origin_name: "<proveedor y export/interface>"
timestamp_source_timezone: "unknown"
normalized_timezone: "UTC"
session_calendar: "unknown"
start_nominal: "<del archivo si aplica; no equivale a cobertura>"
end_nominal: "<del archivo si aplica; no equivale a cobertura>"
coverage_pct: null
gaps: []
spread_and_costs: "unknown"
expected_feed_differences: []
status: "unverified"
```

## Datos y controles pendientes

1. Priorizar datos del broker/venue específico y obtener quotes bid/ask si se afirma que el gap es ejecutable; no calcular fills al mid de una fuente distinta.
2. Registrar zona horaria fuente y convertir a UTC sin perder el timestamp original. Construir `trading_date` con calendario/horario histórico del venue; probar DST, sesiones cortas y festivos.
3. Separar gaps de fin de semana, reaperturas normales, pausa diaria, rollover de contrato, errores de feed y huecos de datos. No reemplazar huecos por precios de cierre ni por otro proveedor sin marcarlos.
4. Medir observaciones esperadas vs presentes por sesión y bucket de apertura; reportar denominador, huecos, spread, slippage y swaps/financiación relevantes.
5. Para CFDs, contrastar Dukascopy solo donde cubra el instrumento y registrar diferencias esperadas; la serie externa no sustituye automáticamente el feed del broker. Si la señal solo pasa con un feed rellenado/sustituto, marcar `NO CONFIRMADO`.
6. Para ETF, distinguir retornos ajustados para análisis de inversión de precios no ajustados/quotes usados para simular ejecución.

## Incertidumbres explícitas

- No se leyó contenido de datos, ni se consultó Mongo, ni se midió cobertura; no se accedió a secretos.
- Los inicios/finales de los nombres de CSV no validan continuidad, timestamp timezone ni presencia de las barras de apertura/cierre.
- `SESSION_START_HOUR = 18` en EDA no establece el timezone real ni un horario oficial del mercado.
- No se probó reversión de gaps ni se declaró edge/casi-pasa. Las fuentes son contexto histórico, no resultados locales.
- Documentar mecanismo, pauta y mercado en una ficha concreta y aplicar los gates comunes de [`../../GATES.md`](../../GATES.md) antes de cualquier veredicto.
