# Revisión de literatura · Gaps y retornos overnight

**Corte temporal:** evidencia publicada hasta 2017-12-31.  
**Estado:** revisión bibliográfica; no se analizaron datos de Alphaca ni se ejecutaron backtests. No confirma un edge en ningún instrumento del repo.

## Definiciones que no se deben mezclar

- **Retorno overnight / close-to-open:** cierre de una sesión al precio de apertura de la siguiente. Puede incluir el fin de semana y noticias publicadas cuando el mercado regular está cerrado.
- **Retorno intradía / open-to-close:** apertura a cierre dentro de una sesión.
- **Gap:** diferencia entre la apertura y el cierre previo; depende de qué sesión y qué precios exactos se tomen. No es lo mismo que un retorno negociable continuo mientras el mercado está cerrado.
- **Gap fill / reversal:** hipótesis posterior de reversión desde la apertura hacia el cierre previo; debe especificar entrada ejecutable después de la apertura, horizonte y precio de fill.

La literatura siguiente estudia principalmente acciones e índices de EE. UU. No valida gaps en futuros, CFDs del broker, FX o cripto, cuyos horarios y cotizaciones son distintos.

## Evidencia primaria anterior a 2018

### [R1] Apertura, cierre y patrones transaccionales

Robert A. Wood, Thomas H. McInish y J. Keith Ord (1985), “An Investigation of Transactions Data for NYSE Stocks”, *The Journal of Finance*, 40(3), 723–739. [DOI / Wiley](https://doi.org/10.1111/j.1540-6261.1985.tb04996.x).

Con datos transaccionales, examinan distribuciones de retornos overnight, los primeros 30 minutos, el cierre y el resto de la sesión. Reportan retornos y desviaciones estándar inusualmente altos al inicio y al final del día; al excluir esos extremos, la autocorrelación de la serie de retornos de mercado disminuye sustancialmente.

**Qué sustenta:** tratar apertura/cierre como segmentos de microestructura separados y no inferir un gap ejecutable solo de barras diarias.  
**Qué no sustenta:** rentabilidad de una estrategia de gap fill ni que los patrones se reproduzcan en feeds actuales.

### [R2] Volatilidad overnight frente a intradía

Larry J. Lockwood y Scott C. Linn (1990), “An Examination of Stock Market Return Volatility During Overnight and Intraday Periods, 1964–1989”, *The Journal of Finance*, 45(2), 591–601. [DOI / Wiley](https://doi.org/10.1111/j.1540-6261.1990.tb03705.x).

Analizan varianzas de retornos horarios de 1964 a 1989 y reportan que la volatilidad cambia a lo largo de la sesión y que la volatilidad intradía es significativamente mayor que la overnight en su muestra.

**Qué sustenta:** separar el perfil de riesgo por periodo de negociación al evaluar gaps.  
**Qué no sustenta:** que el retorno esperado overnight sea positivo, que un gap revierta o que la diferencia de volatilidad sea explotable.

### [R3] Descomposición del retorno semanal e intradía

Lawrence Harris (1986), “A Transaction Data Study of Weekly and Intradaily Patterns in Stock Returns”, *Journal of Financial Economics*, 16(1), 99–117. [DOI / Elsevier](https://doi.org/10.1016/0304-405X(86)90044-9).

Con datos de transacciones, encuentra diferencias intradía por tamaño y día de la semana; parte de los retornos de lunes de firmas grandes ocurre entre el cierre del viernes y la apertura del lunes.

**Qué sustenta:** distinguir el componente de fin de semana del retorno dentro de sesión al estudiar el lunes.  
**Qué no sustenta:** un mecanismo causal común ni una oportunidad negociable actual. El resultado está ligado a acciones y a la estructura de mercado del periodo estudiado.

### [R4] Retornos nocturnos, reversión intradía y costo de abrir una posición

Henk Berkman, Paul D. Koch, Laura Tuttle y Ying Jenny Zhang (2012), “Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open”, *Journal of Financial and Quantitative Analysis*, 47(4), 715–741. [Artículo / DOI Cambridge](https://doi.org/10.1017/S0022109012000270).

Reportan una tendencia a retornos positivos overnight seguidos de reversión durante la sesión en acciones; relacionan el patrón con apertura relativamente alta, atención reciente de inversores retail y títulos difíciles de valorar/arbitrar. El costo implícito de comprar cerca de la apertura puede superar el half-spread efectivo para acciones con alta atención.

**Qué sustenta:** investigar separadamente open-to-close y close-to-open, y contabilizar el precio de compra de apertura como posible costo económico.  
**Qué no sustenta:** que el gap de cada activo revierta, ni una estrategia de comprar en apertura rentable después de costos en otros mercados.

### [R5] Diferencias de riesgo ajustado en ETF de índices

Michael A. Kelly y Steven P. Clark (2011), “Returns in Trading versus Non-Trading Hours: The Difference Is Day and Night”, *Journal of Asset Management*, 12, 132–145. [Artículo / DOI Springer](https://doi.org/10.1057/jam.2011.2).

Comparan retornos de ETFs de índices dentro y fuera del horario regular y reportan diferencias en ratios de Sharpe. Para QQQQ de 1999–2006, el abstract del editor reporta retornos geométricos de prima de riesgo close-to-open y open-to-close de +23.7% y −23.3%, respectivamente.

**Qué sustenta:** que separar el horario puede importar en ETFs amplios y motiva una réplica histórica claramente definida.  
**Qué no sustenta:** un gap fill o fill alcanzable al precio de apertura en todos los activos. El resultado requiere revisar construcción, riesgo, costos y muestra antes de intentar reproducirlo; QQQQ de ese periodo no equivale a un CFD o futuro del repo.

## Mecanismos posibles y explicaciones alternativas

- **Acumulación de información fuera de sesión:** noticias se incorporan mientras el mercado regular no negocia; el retorno de apertura compensa riesgo de precio y no es necesariamente “gap anomalous”.
- **Subasta/apertura y atención:** el precio de apertura puede reflejar desequilibrios de órdenes y luego ajustarse; el efecto depende de quién negocia, liquidez y mecanismo de apertura.
- **Riesgo y selección de exposición:** comparar overnight e intradía puede combinar prima de riesgo, cambios de apalancamiento o restricciones de mantener posiciones fuera de horario.
- **Microestructura y fills:** bid-ask, primera transacción, spreads, baja liquidez y precios de cierre/apertura no ejecutables pueden crear reversión aparente.
- **Gaps de feed o sesión:** para FX/CFD/futuros, pausas, mantenimiento, rollover y zona horaria del broker pueden crear saltos que no corresponden al mismo evento económico de una apertura de acciones.

Estas son explicaciones a distinguir, no mecanismos demostrados de forma universal por los artículos citados.

## Aplicabilidad preliminar al repositorio

Hay EDA para ES, NQ, 6E, 6J, WTIFS, QQQ, USDJPY, BTCUSD y BTCJPY, pero los nombres no fijan venue, proveedor ni horario. Evidencia R1–R5 se refiere a acciones/ETF de EE. UU.; es solo motivación para diseñar fichas de mercados compatibles. Una prueba en un CFD que cotiza casi 24/5 no replica la partición de sesión regular/nocturna del NYSE.

## Preguntas falsables para fichas posteriores

1. Para un instrumento, sesión y calendario especificados, ¿qué proporción del retorno close-to-close se forma close-to-open frente a open-to-close, y cómo varía por periodo?
2. Condicionado al tamaño/signo del gap calculado con datos previos a la decisión, ¿hay retorno posterior desde un fill alcanzable después de la apertura, neto de spread, slippage y reglas de ejecución?
3. ¿La relación es distinta en aperturas regulares, lunes después de fin de semana, feriados o gaps de mantenimiento? Definir esos grupos antes del análisis y corregir múltiples comparaciones.
4. ¿Un resultado sobrevive al feed del broker y a datos bid/ask; o aparece solo con OHLC/mid, un precio de apertura poco negociable o una fuente sustituta?

## Referencias

Todas las referencias seleccionadas fueron publicadas antes del corte y enlazan a DOI editorial. Los hallazgos de artículos se limitan a sus muestras; no se inspeccionaron datos ni se evaluó cobertura de Alphaca. Ninguna cita valida un edge propio.
