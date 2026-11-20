# Handoff · Gaps y transiciones de sesión

## Probado y no probado

- Se completó revisión bibliográfica inicial y crítica metodológica en `literature_review.md`, `evidence_and_data.md` y `red_team.md`.
- Se creó una ficha de descomposición nocturna/intradía para ETF de acciones de EE. UU. como `data_pending`; no se verificó cobertura ni se ejecutaron backtests/gates.
- No hay edges declarados, resultados propios ni casos casi-pasa registrados.

## Pruebas pendientes y datos

- Separar prima overnight incondicional de gap-fill condicional; definir horarios, precios de apertura/cierre y reglas de ejecución por instrumento, incluida la sesión del broker y DST.
- Usar ticks/barras del broker específico para validar apertura y fills; cotejar la fuente de referencia y no mezclar feeds sin anotarlo.
- Incluir spread de apertura, slippage, huecos sin cotización y reglas de ejecución.

## Gates para pasar a notebook de estrategia

Aplicar [`../../GATES.md`](../../GATES.md): cobertura >=98%, muestra objetivo >=100 eventos/trades independientes (si no, pendiente por potencia), FDR q<=0.05, límite inferior del IC bootstrap 95% de la métrica primaria neta >0, resultado positivo agregado y en >=2/3 ventanas OOS, >=70% de parámetros vecinos positivos y estrés de costos 2x spread/comisión aún positivo. Son umbrales iniciales de revisión, no resultados ni garantía de potencia. Descartar si depende de operar a un precio no alcanzable o de gaps originados por fallos del feed.

## Casi-pasa

Ninguno identificado; no se han ejecutado pruebas.
