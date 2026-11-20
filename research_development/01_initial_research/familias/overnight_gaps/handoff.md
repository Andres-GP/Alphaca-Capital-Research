# Handoff · Gaps y transiciones de sesión

## Probado y no probado

- En esta fase solo se creó la estructura. No se ejecutó investigación ni backtest para esta familia.
- No hay edges declarados, resultados propios ni casos casi-pasa registrados.

## Pruebas pendientes y datos

- Definir gap y horarios de referencia por instrumento, incluida la sesión del broker y cambios DST.
- Usar ticks/barras del broker específico para validar apertura y fills; cotejar la fuente de referencia y no mezclar feeds sin anotarlo.
- Incluir spread de apertura, slippage, huecos sin cotización y reglas de ejecución.

## Gates para pasar a notebook de estrategia

Aplicar [`../../GATES.md`](../../GATES.md): cobertura >=98%, muestra objetivo >=100 eventos/trades independientes (si no, pendiente por potencia), FDR q<=0.05, límite inferior del IC bootstrap 95% de la métrica primaria neta >0, resultado positivo agregado y en >=2/3 ventanas OOS, >=70% de parámetros vecinos positivos y estrés de costos 2x spread/comisión aún positivo. Son umbrales iniciales de revisión, no resultados ni garantía de potencia. Descartar si depende de operar a un precio no alcanzable o de gaps originados por fallos del feed.

## Casi-pasa

Ninguno identificado; no se han ejecutado pruebas.
