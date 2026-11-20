# Handoff · Estacionalidad y calendario

## Probado y no probado

- Se completó revisión bibliográfica inicial y crítica metodológica en `literature_review.md`, `evidence_and_data.md` y `red_team.md`.
- Se creó una ficha de día de semana para índice de acciones de EE. UU. como `data_pending`; no se verificó cobertura ni se ejecutaron backtests/gates.
- No hay edges declarados, resultados propios ni casos casi-pasa registrados.

## Pruebas pendientes y datos

- Fijar benchmark, instrumento, definición del retorno y calendario/timezone/DST/sesión antes de consultar resultados.
- Priorizar históricos del broker del instrumento; contrastar horario/feed si se usa otra fuente. Medir cobertura de cada sesión/fecha esperada.
- Controlar pruebas múltiples y cambios de calendario/regulación a lo largo del tiempo.

## Gates para pasar a notebook de estrategia

Aplicar [`../../GATES.md`](../../GATES.md): cobertura >=98%, muestra objetivo >=100 eventos/trades independientes (si no, pendiente por potencia), FDR q<=0.05, límite inferior del IC bootstrap 95% de la métrica primaria neta >0, resultado positivo agregado y en >=2/3 ventanas OOS, >=70% de parámetros vecinos positivos y estrés de costos 2x spread/comisión aún positivo. Son umbrales iniciales de revisión, no resultados ni garantía de potencia. Descartar patrones que dependan de una convención horaria no ejecutable o de pocas observaciones.

## Casi-pasa

Ninguno identificado; no se han ejecutado pruebas.
