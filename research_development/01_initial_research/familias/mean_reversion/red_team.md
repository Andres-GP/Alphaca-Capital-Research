# Red team · Reversión a la media

**Estado:** crítica metodológica previa a pruebas; no es backtest ni veredicto sobre un instrumento. **Corte:** literatura publicada hasta 2017-12-31.

## La etiqueta “reversión” puede esconder hipótesis distintas

- Reversión de corto plazo en retornos de un mismo activo.
- Reversión de largo plazo después de movimientos extremos.
- Reversión relativa entre activos/portafolios, potencialmente impulsada por covarianzas cruzadas.
- Rebote mecánico de cotizaciones por bid-ask bounce, precios stale o liquidez.

No agruparlas como si fueran un solo mecanismo. La ficha debe fijar activo/universo, variable de referencia, horizonte, regla de entrada/salida, precio de ejecución y benchmark antes de observar resultados.

## Evidencia primaria que condiciona la lectura

- De Bondt y Thaler (1985) reportan evidencia consistente con sobrerreacción y reversión de portafolios extremos en retornos mensuales de acciones CRSP. Su resultado motiva una hipótesis de horizonte largo en ese universo; no demuestra un mecanismo causal único ni una reversión intradía/CFD/crypto. [The Journal of Finance, DOI](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x).
- Jegadeesh (1990) encuentra autocorrelación mensual negativa de primer orden y positiva a rezagos más largos en acciones individuales de EE. UU. Por tanto, no se debe generalizar “reversión” a todos los horizontes: el signo puede cambiar con el horizonte. [The Journal of Finance, DOI](https://doi.org/10.1111/j.1540-6261.1990.tb05110.x).
- Lo y MacKinlay (1990) muestran que beneficios de portafolios contrarian pueden originarse en autocovarianzas cruzadas entre acciones, incluso cuando los retornos individuales no presentan autocorrelación negativa. Una curva de portafolio contrarian por sí sola no identifica sobrerreacción. [The Review of Financial Studies, PDF del artículo](https://finance.martinsewell.com/stylized-facts/dependence/LoMacKinlay1990.pdf).
- Roll (1984) presenta una medida implícita del spread efectivo y discute su relación con autocovarianza negativa de retornos observados. Efectos aparentes en barras/cierres de alta frecuencia deben separarse de la mecánica bid-ask. [The Journal of Finance, DOI](https://doi.org/10.1111/j.1540-6261.1984.tb03897.x).

Estos estudios son evidencia publicada anterior a 2018 en acciones, no prueba de resultados ni de disponibilidad de datos de Alphaca. Revisar definición de muestra, costos y tablas antes de calibrar una prueba concreta.

## Riesgos y controles de falsación

| Riesgo | Cómo produce una reversión aparente | Control requerido |
|---|---|---|
| Sobreajuste/múltiples pruebas | Seleccionar retrospectivamente umbral de sobreventa, lookback, holding period, hora, universo y stop que mejor funcionó. | Prerregistrar métrica primaria, horizonte, filtros y grilla; conservar todos los ensayos. Corregir selección múltiple y probar un holdout cronológico intacto. Si la señal no sobrevive la corrección, no pasa. |
| Horizonte ambiguo | Un resultado de largo plazo se usa para justificar una entrada intradía o viceversa; además, reversión a un precio “medio” puede no ser retorno predecible. | Definir si predice retorno del activo, spread relativo o desviación de nivel, con horizonte y benchmark explícitos. Reportar resultados separados por horizonte sin mover el corte tras verlos. |
| Sesgo de supervivencia/selección | Los perdedores extremos que quebraron o fueron excluidos del universo desaparecen, alterando el retorno de carteras loser-winner. | Usar universo point-in-time e incluir delistings/corporate actions y cambios de composición; informar exclusiones y datos faltantes. |
| Look-ahead y precio de fill | Calcular extremidad con el cierre de una barra y suponer ejecución en ese mismo cierre; usar datos futuros para normalizar volatilidad o determinar el mínimo/máximo. | Señal solo tras el dato disponible; fill al siguiente precio cotizable con bid/ask y slippage. El resultado dependiente del cierre que forma la señal falla. |
| Bid-ask bounce y precios stale | Alternar transacciones al bid y ask crea autocorrelación negativa observada aunque el valor eficiente no revierta. Cotizaciones asincrónicas generan rebotes espurios. | Recalcular con midpoint solo como diagnóstico y con bid/ask ejecutable para PnL; analizar ticks/quotes, frecuencia y sincronización. Si el efecto desaparece al quitar el bounce o cuesta más que el edge, descartar. |
| Liquidez y selección de extremos | Los instrumentos más extremos suelen ser menos líquidos; los precios pueden no ser ejecutables o los costos pueden ser mayores precisamente tras la señal. | Modelar spreads y slippage condicionales a la señal, tamaño y horario; evitar asumir fills completos al mid. No extrapolar costos entre activos. |
| Dependencia temporal/solapamiento | Posiciones de varias barras o meses producen observaciones correlacionadas; errores iid exageran significancia. | Inferencia HAC o bootstrap por bloques acorde al horizonte; reportar episodios independientes y no solo número de barras/trades. |
| Cambios de régimen/colas | Reversión puede fallar durante caídas persistentes, crisis, cambio de política o instrumentos en tendencia; pocas recuperaciones dominan el promedio. | Reportar peores episodios/drawdowns y ventanas cronológicas predefinidas. No añadir filtros de régimen optimizados a posteriori; documentar controles de riesgo. |
| Universo/covarianza cruzada | En una cartera contrarian, liderazgo rezagado entre tamaños/activos se confunde con reversión de cada activo. | Separar pruebas por instrumento de la estrategia de cartera; estimar cross-autocovariances y fijar formación de portafolio point-in-time. |
| Costos y restricciones | Rotación alta, spreads, comisión, borrow/short-sale, swaps y slippage consumen el retorno; CFD/ETF/FX tienen convenciones diferentes. | Calcular neto con costos del broker/venue y financiación real por época. Si no hay datos históricos de costos, dejar gate en `pending` y evitar veredicto ejecutable. |
| Feed y horario | Sesiones, DST, timezone, velas, rollover, corporate actions o pausas alteran extremos y el supuesto nivel medio. | Registrar fuente, timezone, sesión, corporate actions y construcción de barras; replicar en fuente primaria del instrumento. Resultado que solo pasa con datos sustitutos o rellenados: `NO CONFIRMADO`. |

## Evidencia que falsaría o dejaría pendiente una ficha

Descartar/reformular si el signo no se reproduce en holdout cronológico; si el resultado depende de una grilla amplia no corregida; si el IC robusto a dependencia temporal incluye cero; si solo aparece al mid/sin spread; si el efecto se explica por bounce o covarianzas cruzadas pero la hipótesis afirmaba reversión individual; si los costos reales eliminan la expectativa neta; o si faltan datos point-in-time, bid/ask o de delistings necesarios para interpretar la señal. Si falla solo por datos incompletos o potencia insuficiente, mantener `data_pending` en vez de llamarlo edge nulo o positivo.

Aplicar los gates comunes de [`../../GATES.md`](../../GATES.md). Ningún resultado de los estudios citados confirma una señal para QQQ, ES/NQ, FX, CFDs o cripto del repositorio.
