# Diferencia de retorno del lunes en acciones amplias de EE. UU.

> **Estado:** `data_pending` · **Familia:** calendar_seasonality · **Pauta:** weekday_returns · **Mercado:** índice amplio de acciones de EE. UU. · **Corte de evidencia:** 2017-12-31

## Pregunta y predicción falsable

¿La distribución o expectativa de retornos de lunes difiere de martes a viernes en un índice amplio de acciones de EE. UU. durante un periodo fuera de muestra, una vez definida la convención de sesión y ajustado por las pautas alternativas examinadas? Fijar por adelantado retorno viernes-cierre a lunes-apertura frente a lunes cierre-a-cierre; no intercambiar ambos.

## Mecanismo económico o estructural

El intervalo sin negociación del fin de semana puede acumular noticias y generar una distribución distinta del retorno calendario del lunes. El mecanismo causal no está identificado; la evidencia histórica no permite atribuir por sí sola el patrón a conducta, liquidez ni tiempo calendario. Contrastar la partición de tiempo calendario frente a tiempo de negociación.

## Evidencia previa a 2018

- French (1980), [*Stock Returns and the Weekend Effect*](https://doi.org/10.1016/0304-405X(80)90021-5), reporta retornos medios de lunes inferiores en el portafolio S&P de 1953–1977 y encuentra que no encajan claramente con dos explicaciones simples de tiempo calendario/de negociación. No valida un edge actual.
- Sullivan, Timmermann y White (1999), [*Data-Snooping, Technical Trading Rule Performance, and the Bootstrap*](https://doi.org/10.1111/0022-1082.00163), documentan por qué se debe corregir la búsqueda sobre una familia completa de reglas; es cautela metodológica, no evidencia del efecto lunes.

## Mercados aplicables

Índice amplio de acciones de EE. UU. Separar retorno del índice/benchmark de la ejecución en ETF o futuro; una ficha para QQQ como producto sería distinta.

## Riesgos y explicaciones alternativas

- Bucket de día afectado por timezone, DST, sesión del broker, festivos o cierres extraordinarios.
- Búsqueda entre días, meses, activos, subperiodos y definiciones de retorno.
- Cambios institucionales y posibles desaparición de la anomalía histórica.
- Diferencia estadística sin retorno neto ejecutable después de spread y fills.

## Datos requeridos

Historial del broker/venue para el instrumento ejecutable, timestamp fuente, timezone IANA/offset, calendario de sesión por año, OHLC/bid-ask y corporate actions. El notebook QQQ usa `yfinance`, fecha inicial nominal 1999-01-01 y `auto_adjust=True`; no se midió cobertura observada ni se verificó que represente fills del broker. Origen/cobertura permanecen pendientes.

## Gates y veredicto

- Estadística, robustez y costos: **pendientes**; aplicar [`../../../../GATES.md`](../../../../GATES.md).
- **Veredicto actual:** no probado, `data_pending`; no es una declaración de edge.

## Próximo paso

Escoger benchmark e instrumento, fijar la definición exacta de sesión/retorno y verificar cobertura y fuente primaria antes de examinar resultados.
