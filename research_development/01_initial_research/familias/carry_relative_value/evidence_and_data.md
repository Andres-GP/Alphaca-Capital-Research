# Carry y valor relativo · evidencia y datos

**Estado:** revisión bibliográfica e inventario de archivos/código no sensibles; no es un backtest ni valida una pauta propia. **Corte de literatura:** 2017-12-31. No se midió cobertura de datos ni se consultaron credenciales o colecciones remotas.

## Mecanismos y definiciones que deben separarse

- **FX carry:** mantener una posición en moneda de tasa alta financiada por moneda de tasa baja. El carry realizado depende de forward points/financiación además de movimientos spot; exposición a riesgo global y pérdidas abruptas son explicaciones relevantes. Una diferencia spot entre dos pares no equivale a carry.
- **Carry de CFD/broker:** swaps/financiación y multiplicadores/rollover definidos por el broker, potencialmente variables por día y símbolo. Las velas de precio no contienen por sí solas la tasa cobrada o acreditada.
- **Basis/term structure de futuros de commodities:** pendiente de la curva entre vencimientos, inventarios y convenience yield pueden relacionarse con primas de riesgo. Un único CFD spot o una serie continua sin contratos individuales no identifica basis ni rollover negociable.
- **Valor relativo entre instrumentos:** requiere precios y exposiciones sincronizados, una regla de hedge/cointegración fijada ex ante y costos de ambos lados. Correlación visual no basta para afirmar neutralidad de mercado.

## Evidencia primaria previa a 2018

### [R1] Forward premium y retornos de divisas

Hanno Lustig, Nikolai Roussanov y Adrien Verdelhan (2011), “Common Risk Factors in Currency Markets”, *The Review of Financial Studies*, 24(11), 3731–3777. [Oxford Academic / DOI](https://doi.org/10.1093/rfs/hhr068).

Construyen carteras de monedas ordenadas por forward discount y estudian retornos excedentes; el factor de spread entre monedas de tasa alta y baja explica una parte importante de la variación transversal en sus datos. Relacionan la exposición del carry a choques globales y volatilidad. **Motiva:** medir carry como retorno total de posiciones long/short con forwards, no spot solamente. **No demuestra:** que USDJPY u otro par individual, un CFD de broker o un swap retail tenga el mismo retorno/riesgo.

### [R2] Riesgo cambiario global y carry crashes

Lucio Menkhoff, Lucio Sarno, Maik Schmeling y Andreas Schrimpf (2012), “Carry Trades and Global Foreign Exchange Volatility”, *The Journal of Finance*, 67(2), 681–718. [Wiley / DOI](https://doi.org/10.1111/j.1540-6261.2012.01728.x).

Analizan carteras de carry FX y muestran asociación entre volatilidad global de FX y retornos de carry, con bajo desempeño en periodos de volatilidad alta y riesgo de pérdidas en estados adversos. **Motiva:** medir distribuciones condicionales, riesgo de cola y financiación. **No demuestra:** que volatilidad spot sea una regla causal suficiente para sincronizar o evitar pérdidas en la cuenta local.

### [R3] Basis, inventarios y primas de riesgo en commodities

Gary B. Gorton, Fumio Hayashi y K. Geert Rouwenhorst (2013), “The Fundamentals of Commodity Futures Returns”, *Review of Finance*, 17(1), 35–105. [Oxford Academic / DOI](https://doi.org/10.1093/rof/rfs019).

Usan futuros de 31 commodities y datos de inventarios físicos de 1971–2010. Encuentran que inventarios y variables como basis, retornos pasados y volatilidad contienen información sobre primas de riesgo de futuros; no encuentran evidencia de que posiciones de participantes predigan esas primas. **Motiva:** analizar term structure e inventarios por commodity. **No demuestra:** carry ejecutable en CFD spot, ni que un indicador de contango/backwardation reconstruido sin contratos refleje el retorno de roll disponible.

## Inventario visible del repositorio

Los nombres y rutas son evidencia de artefactos presentes, no certificación del origen íntegro o de su cobertura. No se inspeccionaron secretos ni se conectó a MongoDB.

| Mercado/candidato | Lo visible en repo | Origen identificable | Requisitos y huecos antes de una prueba |
|---|---|---|---|
| FX USDJPY / EURGBP | CSV Axi `usdjpy_M5_200001022200_202611030050.csv`, `eurgbp_M5_201701020000_202611062355.csv`; CSV Darwinex USDJPY desde 2025; notebooks EDA FX. | Rutas/nombres etiquetados Axi/Darwinex; el feed y sus swaps históricos no están verificados en metadatos revisados. | Para FX carry: spot y forwards/forward points (o tasas de ambas divisas), financiación efectiva, bid/ask y calendario de roll por fecha. Para CFD: historial de swaps por lado/día, multiplicador, rollover triple y cambios de especificación del broker. Spot M5 por sí solo no basta. Cobertura efectiva: desconocida. |
| Energía USD OIL / WTIFS / XTIUSD | CSV Axi `usoil_H1_201007080000_202611021900.csv`, `wtifs_H1_200802180000_202611021900.csv`; Darwinex `xtiusd_H1_201005020000_202611021200.csv`. | Nombres/rutas de export identificados; no se ha verificado broker/feed completo, ajustes ni contratos. | Para basis de futuros se requieren contratos por vencimiento, precios sincronizados, regla de roll y, para mechanism inventory-based, datos históricos de inventarios. Un CFD/serie spot aislado no proporciona curva ni costos de roll. Swaps/financiación históricos y spreads también faltan. |
| Futuros ES/NQ/6E/6J | EDA carga colecciones Mongo por nombre (`es_15min`, `nq_15min`, `6e_15min`, `6j_15min`). | El loader apunta a Mongo; no se consultaron datos, la fuente del broker no está identificada. | Carry/rates y basis requieren instrumentos y series adicionales; rollover de contrato, settlement y funding deben verificarse. Cobertura y costos: desconocidos. |
| Crypto/CFD BTCUSD, ETHUSD, BTCJPY | CSV Axi BTCUSD y ETHUSD, BTCJPY desde 2019; Dukascopy BTCUSD H1; varias fuentes no sincronizadas. | Etiquetas de origen en ruta/nombre, no metadatos auditados del export. | Funding/swaps por broker y lado, cambios históricos de contrato, timezone y spreads; BTCJPY no tiene periodo nominal pre-2018 en ese archivo. No inferir carry de retornos spot de crypto. |
| Acciones/ETF T20 y QQQ | T20 contiene CSV por ticker; QQQ EDA descarga por `yfinance`. | Proveedor y universo histórico de T20 no verificados aquí; QQQ notebook indica Yahoo Finance. | Dividendos, borrow/short costs, corporate actions y universo point-in-time; datos sincronizados y spreads para long/short. Precio de acción/ETF sin estos campos no representa carry total ni coste de financiación. |

## Datos requeridos y prioridad

1. **Broker/venue del instrumento:** bid/ask, especificación, multiplicador, comisión, rollover y swap/financiación histórica por símbolo/lado. Para Darwinex/CFDs, mantener el feed del broker separado del histórico sustituto.
2. **FX carry:** forwards/forward points contemporáneos y spot de cierre compatibles, o tasas históricas de ambas monedas más convención de cálculo; verificar calendario de settlement y días festivos. Los tipos oficiales gratuitos pueden servir para una aproximación/investigación, pero no prueban puntos forward ni la financiación de CFD negociable.
3. **Futuros commodities:** cadena de contratos por vencimiento y settlement histórico, curva completa, roll rule decidida ex ante y costos; agregar datos de inventario de fuente primaria si se prueba el mecanismo de convenience yield.
4. **Valor relativo:** calendario común, timestamp de cada mercado, divisas y hedge ratios calculados solo con información pasada. Evitar sincronización a posteriori de cierres distintos.
5. Cada dataset debe llevar cobertura, huecos, proveedor, timezone, sesiones y diferencia esperada respecto a feed ejecutable. No interpolar ni rellenar. Si solo pasa con serie externa/ajustada, marcar `NO CONFIRMADO`.

## Pendientes explícitos

- No se verificaron históricos de swaps, forward points, tasas, contratos futuros por vencimiento, inventarios ni costos de short/financiación.
- Las series CFD de petróleo o FX por sí mismas no permiten afirmar carry/basis sin los componentes económicos y contractuales correspondientes.
- No se evaluó fuente gratuita adicional ni cobertura; corresponde al trabajo de datos antes de cualquier backtest.
- No hay hipótesis de mercado con resultado probado, gates pasados ni casos casi-pasa en esta revisión.
