# Carry transversal en forwards G10

> **Estado:** `data_pending` · **Familia:** carry_relative_value · **Pauta:** fx_forward_carry · **Mercado:** forwards G10, universo y proveedor por definir · **Corte de evidencia:** 2017-12-31

## Pregunta y predicción falsable

En un universo G10 definido point-in-time, ¿una cartera long de monedas con mayor forward discount y short de monedas con menor discount produce retorno excedente neto positivo fuera de muestra, sumando spot, forward/funding, comisiones y ejecución? Medir la exposición a volatilidad global y estados de unwind con particiones predefinidas. Esta cartera transversal no equivale a una posición larga o corta aislada en USDJPY.

## Mecanismo económico o estructural

El diferencial de tasas/forward puede compensar riesgo de depreciación, liquidez y shocks globales de monedas de alto rendimiento. Por eso se trata como prima de riesgo potencial, no arbitraje ni retorno garantizado.

## Evidencia previa a 2018

- Lustig, Roussanov y Verdelhan (2011), [*Common Risk Factors in Currency Markets*](https://doi.org/10.1093/rfs/hhr068), analizan carteras de monedas ordenadas por forward discount y un factor de spread. No valida un CFD de par único.
- Menkhoff, Sarno, Schmeling y Schrimpf (2012), [*Carry Trades and Global Foreign Exchange Volatility*](https://doi.org/10.1111/j.1540-6261.2012.01728.x), relacionan resultados de carteras FX carry con volatilidad global y estados de riesgo. No proporciona swaps ni costos del broker local.

## Mercados aplicables

FX forwards G10. El archivo USDJPY del repo está etiquetado como FX/CFD en su ruta, pero una sola serie de spot no permite reproducir una cartera de forward discounts.

## Riesgos y explicaciones alternativas

- Carry puede sufrir pérdidas abruptas y costos de financiación/liquidez cuando se deshacen posiciones.
- Selección de monedas, cambios de universo, controles de capital y periodos excluidos.
- Tasas y forward points revisados o conocidos después de la señal crean look-ahead.
- Convenciones de fixing/settlement, funding y spreads del broker difieren de forwards institucionales.

## Datos requeridos

Se requieren universo G10 point-in-time, spot bid/ask, forward points o tasas por fixing, timestamps de disponibilidad/settlement, costos históricos de financiación, rollover, comisión y slippage. El repo no identifica forwards ni forward points; la cobertura es desconocida. La serie USDJPY CFD no basta para probar esta pauta transversal.

## Gates y veredicto

- Estadística, robustez y costos: **pendientes**; aplicar [`../../../../GATES.md`](../../../../GATES.md).
- **Veredicto actual:** no probado, `data_pending`.

## Próximo paso

Localizar datos históricos point-in-time de forward points para el universo FX elegido junto con costos realmente negociables. Si solo existe spot/CFD, dejar esta prueba pendiente y no sustituirlo por carry forward teórico.
