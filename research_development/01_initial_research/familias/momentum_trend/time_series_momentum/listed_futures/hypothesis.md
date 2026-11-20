# Momentum de serie temporal en futuros listados

> **Estado:** `data_pending` · **Familia:** momentum_trend · **Pauta:** time_series_momentum · **Mercado:** futuros listados por especificar · **Corte de evidencia:** 2017-12-31

## Pregunta y predicción falsable

En futuros líquidos definidos antes de medir el resultado, ¿el signo del retorno total pasado de 12 meses predice continuación neta durante los siguientes 1–12 meses, comparado con un benchmark fijado de antemano? La hipótesis se limita a cada contrato/venue y regla de rollover que pueda verificarse; no se extrapola automáticamente a CFD, ETF, crypto o intradía.

## Mecanismo económico o estructural

El ajuste gradual de posiciones ante información nueva o límites de riesgo/capital podría generar persistencia intermedia. La sobrerreacción, los cambios de régimen y la reversión de largo plazo son explicaciones alternativas que pueden borrar o invertir la señal. La evidencia publicada aporta plausibilidad, no identifica por sí sola el mecanismo causal.

## Evidencia previa a 2018

- Moskowitz, Ooi y Pedersen (2012), [*Time Series Momentum*](https://doi.org/10.1016/j.jfineco.2011.11.003): documentan persistencia de 1–12 meses y reversión parcial posterior en el universo de futuros de su estudio. No confirma que cada símbolo/feed local tenga el efecto.
- Hurst, Ooi y Pedersen (2017), [*A Century of Evidence on Trend-Following Investing*](https://doi.org/10.3905/jpm.2017.44.1.015): evidencia histórica multi-mercado mensual; la composición y construcción de series largas requieren auditoría antes de compararlas con precios negociables locales.

Las dos referencias anteriores a 2018 fueron localizadas en fuentes editoriales/DOI. Los métodos y tablas se deben revisar antes de fijar parámetros precisos.

## Mercados aplicables

Futuros listados líquidos, pendiente identificar contratos y fuente primaria. En el repo aparecen notebooks EDA para ES, NQ, 6E y 6J que cargan colecciones Mongo; su proveedor, continuidad y cobertura no están verificados. CFDs, ETF o crypto requieren hipótesis y datos separados.

## Riesgos y explicaciones alternativas

- Rollover o ajuste retrospectivo puede crear o cambiar tendencias.
- Selección retrospectiva de mercados, sesgo de supervivencia, búsqueda de horizontes y ventanas solapadas.
- Dependencia temporal puede inflar significancia si las observaciones se tratan como iid.
- Reversión de horizonte largo, pérdidas concentradas por régimen y costos variables.
- Sesiones, settlement, DST, spread, slippage y feed difieren entre proveedores.

## Datos requeridos

Primero datos del broker/venue del contrato: timestamp y zona horaria, contrato individual, settlement/precios bid-ask, volumen, regla de rollover conocida en cada fecha, comisiones, spread y slippage. El código del repo muestra MongoDB para colecciones `es_15min`, `nq_15min`, `6e_15min`, `6j_15min`, pero el origen y cobertura de su contenido siguen desconocidos. No se ha medido cobertura ni ejecutado el análisis.

## Gates y veredicto

- Estadística, robustez y costos: **pendientes**; aplicar [`../../../../GATES.md`](../../../../GATES.md).
- **Veredicto actual:** no probado. Es una hipótesis de literatura para resolver si existe data utilizable, no un edge validado.

## Próximo paso

Identificar por contrato la fuente del broker, el rango y cobertura reales, la regla de rollover y los costos. Si los datos no permiten una prueba íntegra, registrar el hueco y mantener la hipótesis pendiente.
