# Revisión de literatura · Momentum y seguimiento de tendencia

**Corte temporal:** solo evidencia publicada hasta 2017-12-31.  
**Estado de esta revisión:** lectura de literatura; no se analizaron datasets ni se ejecutaron backtests en Alphaca. No confirma ningún edge en los instrumentos o feeds propios.

## Distinciones necesarias

- **Momentum transversal (cross-sectional):** comprar activos que rindieron mejor que otros activos del universo y vender los rezagados. La señal depende del ranking relativo.
- **Momentum de serie temporal (time-series momentum, TSMOM):** tomar una posición larga/corta según el signo del rendimiento pasado del mismo activo. Es una forma operacional frecuente de trend following, aunque no agota todas sus variantes.
- No intercambiar estos conceptos ni trasladar automáticamente un resultado de acciones individuales a futuros, CFDs, ETF o criptoactivos.

## Evidencia primaria localizada

### [R1] Reglas de media móvil y ruptura en renta variable

William Brock, Josef Lakonishok y Blake LeBaron (1992), “Simple Technical Trading Rules and the Stochastic Properties of Stock Returns”, *The Journal of Finance*, 47(5), 1731–1764. [DOI / Wiley](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x).

Prueban reglas de media móvil y ruptura de rango sobre el Dow Jones Industrial Average entre 1897 y 1986, y usan bootstrap para comparar con varios modelos nulos. El resumen del editor reporta soporte para esas reglas bajo las especificaciones examinadas.

**Qué sustenta:** que reglas técnicas simples eran contrastables y mostraron resultados incompatibles con los modelos nulos que evaluó ese estudio en ese índice y periodo.  
**Qué no sustenta:** rentabilidad neta ejecutable actual, validez en otros mercados, o un mecanismo causal único. Las reglas/datos de una muestra histórica no sustituyen control de búsqueda de parámetros, costos, cambios de mercado y replicación OOS.

### [R2] Momentum transversal en acciones

Narasimhan Jegadeesh y Sheridan Titman (1993), “Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency”, *The Journal of Finance*, 48(1), 65–91. [DOI / Wiley](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x).

Documentan retornos positivos para estrategias de comprar acciones ganadoras y vender perdedoras usando periodos de formación y tenencia de 3–12 meses. Reportan que parte del rendimiento anormal del primer año se disipa durante los dos años siguientes.

**Qué sustenta:** una regularidad de ranking transversal en las acciones y muestra estudiadas, con reversión parcial a horizonte más largo.  
**Qué no sustenta:** un filtro direccional por rendimiento pasado del mismo futuro/CFD; tampoco prueba que el resultado sobreviva a los costos y restricciones de una cuenta actual.

### [R3] Momentum de serie temporal en futuros de varias clases

Tobias J. Moskowitz, Yao Hua Ooi y Lasse Heje Pedersen (2012), “Time Series Momentum”, *Journal of Financial Economics*, 104(2), 228–250. [DOI / ScienceDirect](https://doi.org/10.1016/j.jfineco.2011.11.003).

Estudian 58 futuros líquidos de índices de acciones, divisas, materias primas y bonos. El artículo reporta persistencia de retornos a horizontes de 1–12 meses y reversión parcial a horizontes más largos. Los autores discuten que el patrón es consistente con teorías de sentimiento de subreacción inicial y sobrerreacción posterior; también comparan resultados de especuladores y hedgers.

**Qué sustenta:** una hipótesis TSMOM de plazo intermedio con evidencia publicada en diversas clases de futuros del universo del estudio.  
**Qué no sustenta:** CFDs OTC de broker, los símbolos locales de Alphaca, señales intradía ni ejecución rentable actual. La consistencia con una explicación de sentimiento no identifica causalmente ese mecanismo; asociación entre clases de traders tampoco prueba que el edge sea accesible sin costos/constraints.

### [R4] Difusión gradual de información como mecanismo potencial

Harrison Hong, Terence Lim y Jeremy C. Stein (2000), “Bad News Travels Slowly: Size, Analyst Coverage, and the Profitability of Momentum Strategies”, *The Journal of Finance*, 55(1), 265–295. [DOI / Wiley](https://doi.org/10.1111/0022-1082.00206).

Evalúan acciones y reportan mayor rentabilidad de momentum en empresas de baja cobertura de analistas, manteniendo tamaño, y efecto particularmente marcado entre perdedoras. Sus hallazgos son consistentes con difusión gradual de información específica, en especial noticias negativas.

**Qué sustenta:** una explicación plausible de momentum transversal en acciones ligadas a cobertura/flujo de información.  
**Qué no sustenta:** ese mecanismo en futuros macro, FX mayorista o instrumentos OTC; ni permite inferir causalidad o predecir sin medir cobertura/liquidez comparable en el universo objetivo.

### [R5] Evidencia histórica extensa de tendencia multi-activo

Brian Hurst, Yao Hua Ooi y Lasse Heje Pedersen (2017), “A Century of Evidence on Trend-Following Investing”, *The Journal of Portfolio Management*, 44(1), 15–29. [Registro académico y DOI](https://doi.org/10.3905/jpm.2017.44.1.015).

El artículo extiende el análisis de tendencia de serie temporal a una base histórica multi-mercado desde 1880. El registro académico de Copenhagen Business School resume retornos promedio positivos en cada década de la muestra para la cartera TSMOM estudiada y resultados favorables en la mayoría de los episodios de crisis definidos por los autores.

**Qué sustenta:** que merece investigarse la persistencia multi-activo y su comportamiento entre regímenes usando series largas, sin limitar la motivación a una muestra reciente.  
**Qué no sustenta:** historia homogénea de precios negociables: la base combina series históricas de distintas fuentes y construcciones. El propio dataset, sus reconstrucciones, costos y reglas deben auditarse antes de extrapolar; autores afiliados a AQR tienen interés profesional en el tema, hecho que conviene considerar junto con sus métodos.

## Síntesis del mecanismo

Una hipótesis económicamente plausible es que la información y las órdenes se incorporen gradualmente, o que participantes con límites de riesgo/capital ajusten posiciones de manera escalonada. Eso puede producir autocovarianza positiva de horizonte intermedio. En horizontes más largos, sobreextensión, cambios de régimen o reversión pueden reducir/invertir la predictibilidad. La literatura citada respalda que estos mecanismos se han propuesto y que ciertas regularidades aparecen en muestras concretas; no demuestra que sean la causa universal del retorno observado.

## Preguntas falsables para una ficha posterior

Estas son propuestas para investigar, no hipótesis aprobadas ni resultados:

1. **TSMOM mensual en futuros del instrumento disponible:** dado el signo del retorno total pasado de 12 meses, ¿el retorno siguiente de 1–12 meses conserva dirección, antes y después de costos ejecutables? Comparar contra señal nula y benchmark buy-and-hold; especificar rebalanceo y definición de retorno antes de mirar resultados.
2. **Continuación frente a reversión por horizonte:** ¿la relación señal-retorno cambia de positiva en horizontes intermedios a negativa en horizontes largos en el mismo instrumento/feed? Medirlo en bloques cronológicos y con múltiples pruebas ajustadas.
3. **Regímenes y diversificación:** ¿la señal muestra comportamiento distinto por volatilidad/correlación o solo la cartera diversificada reduce drawdowns? Separar efecto por mercado del efecto de agregación.
4. **Adaptación de la evidencia transversal:** solo si hay un universo de activos y datos point-in-time sin sesgo de supervivencia, contrastar ranking cross-sectional por separado del TSMOM individual. No usar resultados de acciones como evidencia directa para futuros/CFDs.

## Aplicabilidad inicial a Alphaca

Las notebooks EDA existentes incluyen símbolos `ES`, `NQ`, `6E`, `6J`, `WTIFS`, `QQQ`, `USDJPY`, `BTCUSD` y `BTCJPY`, pero el nombre del símbolo no determina venue, tipo de contrato, fuente ni historia disponible. Para cada instrumento, verificar metadatos/dataset primero. La evidencia directa de R3 aplica a futuros líquidos según el estudio; R2/R4 son evidencia de acciones; R1 es DJIA histórico; R5 es cartera reconstruida multi-mercado. Cualquier aplicación a CFD de broker/ETF/cripto queda como extrapolación por probar.

## Riesgos que debe cubrir el red team

- Sobreajuste de ventana de lookback, umbrales, volatilidad objetivo, horario y universo; registrar todas las variantes probadas.
- Comparaciones múltiples y selección de activos supervivientes; preservar universo point-in-time cuando aplique.
- Autocorrelación y solapamiento de tenencias; usar inferencia con dependencia temporal.
- Precios de futuros con rollover/back-adjustment frente a retorno de contrato realmente negociable; splits/dividendos de ETF; feed CFD, spreads, swaps y horarios del broker.
- Costos y capacidad: señal de baja frecuencia puede ser más viable que una regla rápida, pero debe calcularse con fills/quotes apropiados y no suponerse.
- El resultado agregado puede ocultar fallos por instrumento, época, dirección o régimen.

## Fuentes verificadas

Los cinco registros bibliográficos y sus DOI/editoriales fueron localizados en Wiley Online Library, ScienceDirect o el repositorio académico de Copenhagen Business School. Verificar el texto completo y las tablas antes de codificar parámetros precisos; este resumen no reemplaza la lectura metodológica completa. Todas las referencias listadas son anteriores a 2018.
