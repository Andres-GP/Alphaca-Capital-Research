# Retorno nocturno frente a retorno intradía en ETF de acciones de EE. UU.

> **Estado:** `data_pending` · **Familia:** overnight_gaps · **Pauta:** overnight_index_premium · **Mercado:** ETF de acciones de EE. UU.; QQQ candidato · **Corte de evidencia:** 2017-12-31

## Pregunta y predicción falsable

Para QQQ u otro ETF fijado antes del análisis, ¿el retorno total y ajustado por riesgo close-to-open difiere de open-to-close y conserva expectativa neta positiva en un holdout cronológico bajo una regla ejecutable de entrada/salida predefinida? Esta pregunta de prima overnight incondicional es distinta de gap-fill condicional, que requeriría su propia ficha.

## Mecanismo económico o estructural

Noticias y órdenes se acumulan cuando el mercado regular está cerrado, y la apertura puede revalorizar el ETF. La diferencia podría representar exposición overnight y su riesgo, no una ineficiencia. La subasta y los costos de comprar/vender cerca de la apertura son explicaciones alternativas de cualquier reversión posterior.

## Evidencia previa a 2018

- Kelly y Clark (2011), [*Returns in Trading versus Non-Trading Hours: The Difference Is Day and Night*](https://doi.org/10.1057/jam.2011.2), comparan retornos de negociación y no negociación en ETFs de índices, incluido QQQQ en 1999–2006. No prueban que el precio de apertura sea un fill alcanzable actual.
- Berkman, Koch, Tuttle y Zhang (2012), [*Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open*](https://doi.org/10.1017/S0022109012000270), reportan prima overnight y reversión intradía en acciones de su muestra, con costos implícitos de apertura relevantes. No generalizar ese efecto a todo ETF o CFD.

## Mercados aplicables

ETF amplio de acciones de EE. UU.; QQQ es un candidato de datos, no se presume equivalencia con QQQQ o con las muestras publicadas. Separar precios ajustados de retornos de inversión de precios ejecutables para fills.

## Riesgos y explicaciones alternativas

- Prima de riesgo nocturna, cambios de volatilidad y noticias pueden explicar retornos distintos por horario.
- Precio de subasta/primera transacción no necesariamente ejecutable al observarlo; spreads y slippage pueden ser mayores en apertura.
- Corporate actions, dividendos, horario del proveedor, universo de ETFs y selección de ventanas.
- La prima close-to-open no confirma que gaps de cierta magnitud reviertan después.

## Datos requeridos

Necesita timestamp de exchange, calendario regular, precios no ajustados de apertura/cierre, retornos ajustados totales, bid-ask, comisiones, slippage y corporate actions. La EDA QQQ usa `yfinance`, fecha inicial nominal `1999-01-01` y `auto_adjust=True`; cobertura observada y datos de fills del broker no están verificados.

## Gates y veredicto

- Estadística, robustez y costos: **pendientes**; aplicar [`../../../../GATES.md`](../../../../GATES.md).
- **Veredicto actual:** no probado, `data_pending`; no declara edge.

## Próximo paso

Verificar fuente y datos ejecutables del broker, calendario oficial y cobertura antes de calcular close-to-open/open-to-close. Mantener el gap-fill condicional como pregunta separada.
