# Revisión de literatura · Carry y valor relativo

**Corte de evidencia:** publicaciones hasta 2017-12-31.  
**Estado:** revisión bibliográfica; no se consultaron datasets locales ni se ejecutaron backtests. Ninguna cita confirma un edge en Alphaca.

## Alcance: tres preguntas relacionadas, no una sola estrategia

La familia reúne fenómenos distintos que deben separarse en fichas por pauta y mercado:

1. **FX carry / forward premium:** exposición a monedas con tasas/forward discount altos financiada con monedas de tasas bajas. Es una prima de riesgo potencial, no arbitraje sin riesgo.
2. **Carry de futuros de commodities:** retorno depende de cambio de precio spot/futuro, basis entre vencimientos, convergencia y factores físicos como inventarios/costo de almacenamiento. “Backwardation” por sí sola no garantiza retorno positivo.
3. **Valor relativo / pares:** posición larga y corta en instrumentos considerados sustitutos; resultado puede provenir de reversión transitoria, riesgo común o microestructura. No equivale al FX carry ni a una curva de futuros.

La taxonomía no presupone que exista una relación negociable entre los instrumentos del repositorio. Cada mercado debe tener su propia predicción, datos y costos.

## Evidencia primaria pre-2018

### FX carry y prima forward

**Fama (1984), “Forward and Spot Exchange Rates,” *Journal of Monetary Economics*, 14(3), 319–338.** [DOI / Elsevier](https://doi.org/10.1016/0304-3932(84)90046-1).

Condicional a la hipótesis de mercado forward racional/eficiente, el análisis encuentra variación temporal tanto en la prima como en el spot futuro esperado; la mayor parte de la variación del forward observada en su muestra se atribuye a la prima, y ambos componentes se relacionan negativamente.

- **Sustenta:** la diferencia forward-spot no se debe tratar como pronóstico puro del spot; medir por separado prima y depreciación/apreciación esperada.
- **No sustenta:** que una regla retail sobre USDJPY spot/CFD obtenga carry positivo. El paper no es un backtest del broker local ni elimina financiamiento, spreads o riesgos de cola.

**Lustig, Roussanov y Verdelhan (2011), “Common Risk Factors in Currency Markets,” *The Review of Financial Studies*, 24(11), 3731–3777.** [DOI / Oxford Academic](https://doi.org/10.1093/rfs/hhr068).

Construyen portafolios de monedas clasificados por forward discount y encuentran un factor de pendiente relacionado con una parte importante de la variación transversal de retornos promedio. Su interpretación es que carry carga exposición a shocks de riesgo global, incluida volatilidad de mercados accionarios.

- **Sustenta:** investigar cross-section de monedas y riesgo común al estudiar carry.
- **No sustenta:** retorno estable de una sola pareja (p. ej. USDJPY), ausencia de pérdidas/crashes ni rentabilidad neta para CFDs. Un CFD añade términos de financiación/swap y condiciones del proveedor.

### Carry y basis en futuros de commodities

**Gorton, Hayashi y Rouwenhorst (2013), “The Fundamentals of Commodity Futures Returns,” *Review of Finance*, 17(1), 35–105.** [DOI / Oxford Academic](https://doi.org/10.1093/rof/rfs019).

Con 31 futuros de commodities y datos de inventarios de 1969–2006, estudian conveniencia, basis y retornos. Reportan que la conveniencia varía de forma no lineal con inventarios; medidas como basis, retornos previos de futuros y de spot son informativas sobre primas en su muestra. El trabajo no atribuye el resultado solo a la posición de hedgers.

- **Sustenta:** construir una prueba de basis/curva que incorpore vencimientos e información de inventario cuando esté disponible.
- **No sustenta:** llamar carry a cualquier CFD de commodity, asumir que backwardation es edge, ni tratar un ajuste de serie continua como precio negociable.

**Szymanowska, De Roon, Nijman y Van den Goorbergh (2014), “An Anatomy of Commodity Futures Risk Premia,” *The Journal of Finance*, 69(1), 453–482.** [DOI / Wiley](https://doi.org/10.1111/jofi.12096).

Separan primas spot relacionadas con riesgo de la commodity y primas de término relacionadas con cambios en basis; examinan variables predictivas, incluido basis, en una sección transversal de futuros.

- **Sustenta:** diferenciar spot premia y term premia; un solo precio continuo no captura necesariamente el basis de vencimientos.
- **No sustenta:** que el resultado se mantenga tras costos de roll actuales o en el contrato de petróleo/CFD local sin datos por vencimiento.

Rouwenhorst y Tang (2012), en su revisión *Commodity Investing*, también señalan evidencia débil para la teoría de normal backwardation como explicación universal y resultados más consistentes con decisiones de almacenamiento. [DOI / Annual Reviews](https://doi.org/10.1146/annurev-financial-110311-101716). Es una revisión de literatura, no una prueba de una pauta local.

### Valor relativo / pares

**Gatev, Goetzmann y Rouwenhorst (2006), “Pairs Trading: Performance of a Relative-Value Arbitrage Rule,” *The Review of Financial Studies*, 19(3), 797–827.** [DOI / Oxford Academic](https://doi.org/10.1093/rfs/hhj020).

Prueban una regla de pares sobre acciones diarias de EE. UU. (1962–2002) con selección por distancia entre trayectorias normalizadas. Reportan retornos históricos en su diseño, pero también discuten posibles efectos de microestructura y construyen controles bootstrap; interpretan su resultado como diferente de beneficios de reversal previamente documentados.

- **Sustenta:** una hipótesis de pares requiere regla de emparejamiento, universo y fechas de formación definidos, y comparación contra explicaciones de microestructura/reversal.
- **No sustenta:** que instrumentos relacionados del repo estén cointegrados, que la relación sea estable, ni que una cartera de pares sobreviva a costos, survivorship y selección múltiple fuera de esa muestra.

## Mecanismos plausibles y límites de inferencia

- En FX, el diferencial de tasas/forward puede compensar exposición a depreciación de moneda de alto rendimiento y riesgo global; no debe presentarse como arbitraje de paridad cubierta.
- En commodities, inventarios, capacidad de almacenamiento y conveniencia física pueden cambiar el basis y la prima; los signos dependen del estado de oferta/demanda y del vencimiento.
- En pares, sustitución económica, convergencia de valoración o factores comunes pueden mover spreads; ruptura del vínculo y ejecución simultánea son riesgos estructurales.
- Cambios de financiación, settlement, rollover, calidad de activos y regulación pueden transformar el mecanismo. La evidencia publicada caracteriza muestras específicas y no identifica automáticamente un mecanismo causal estable.

## Posible relación con activos del repo

La EDA incluye USDJPY y productos rotulados WTIFS/USOIL, además de símbolos de futuros y QQQ. El ticker/ruta no prueba tipo contractual, venue, basis disponible ni historial de costos. USDJPY aislado no forma el portafolio transversal FX carry de la literatura; un CFD OTC no equivale a un forward deliverable. WTIFS/USOIL puede ser CFD y no una cadena de futuros con vencimientos negociables; se debe identificar instrumento y proveedor antes de aplicar literatura de term structure. Los datos y huecos se auditan en un archivo de familia separado.

## Preguntas falsables para fichas posteriores

1. **FX carry transversal:** en un universo de forwards/monedas observable a cada fecha, ¿el retorno neto de alto menos bajo forward discount es positivo fuera de muestra y cómo cambia en shocks de volatilidad? Requiere varias monedas, forward points, reglas de rebalanceo y financiación; una sola pareja no replica este test.
2. **Basis de commodities:** ¿basis por vencimiento/inventarios predice futuros retornos spot y de término por separado? Requiere contratos individuales, curvas y regla de roll fijada con información contemporánea, no una serie continuamente back-adjusted.
3. **Pares:** ¿un spread entre sustitutos económicos predefinidos revierte fuera de muestra tras costos y sobrevive selección del par/universo? Aclarar si es un test de cointegración, distancia histórica o factor común.
4. En todos los casos, ¿la rentabilidad restante compensa riesgo de cola, liquidación, funding, spread, comisión, slippage y costos de roll reales?

Son preguntas de investigación, no resultados. Antes de crear fichas por instrumento hay que comprobar que los datos requeridos existen. Los gates estadísticos, robustez y costos continúan pendientes hasta una ejecución reproducible.
