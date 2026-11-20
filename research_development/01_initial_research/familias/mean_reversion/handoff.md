# Handoff · Reversión a la media

## Probado y no probado

- Se completó revisión bibliográfica inicial y crítica metodológica en `literature_review.md`, `evidence_and_data.md` y `red_team.md`.
- Se creó una ficha contrarian semanal para acciones de EE. UU. como `data_pending`; no se inspeccionaron datasets ni se ejecutaron backtests/gates.
- No hay edges declarados, resultados propios ni casos casi-pasa registrados.

## Pruebas pendientes y datos

- Verificar universo point-in-time, delistings, costos de short y si la predicción se refiere a reversión propia o a autocovarianza cruzada.
- Usar datos del broker del instrumento, incluyendo bid/ask si la frecuencia lo requiere; conservar huecos y extremos, sin rellenarlos silenciosamente.
- Comprobar exposición a tendencia, liquidez, costos y cambios de régimen.

## Gates para pasar a notebook de estrategia

Aplicar [`../../GATES.md`](../../GATES.md): cobertura >=98%, muestra objetivo >=100 eventos/trades independientes (si no, pendiente por potencia), FDR q<=0.05, límite inferior del IC bootstrap 95% de la métrica primaria neta >0, resultado positivo agregado y en >=2/3 ventanas OOS, >=70% de parámetros vecinos positivos y estrés de costos 2x spread/comisión aún positivo. Son umbrales iniciales de revisión, no resultados ni garantía de potencia. Descartar si solo funciona con fills al mid o desaparece con costos realistas.

## Casi-pasa

Ninguno identificado; no se han ejecutado pruebas. Registrar instrumento, mecanismo y gates fallidos cuando exista evidencia.
