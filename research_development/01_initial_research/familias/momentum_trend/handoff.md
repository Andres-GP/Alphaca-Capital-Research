# Handoff · Momentum y tendencia

## Probado y no probado

- Se completó revisión bibliográfica y red-team inicial en `literature_review.md`, `evidence_and_data.md` y `red_team.md`.
- Se creó una ficha de TSMOM para futuros listados como `data_pending`; no se inspeccionaron datasets ni se ejecutaron backtests/gates.
- No hay edges declarados, resultados propios ni casos casi-pasa registrados.

## Pruebas pendientes y datos

- Verificar instrumento/contrato, venue y predicción por mercado antes de proponer cualquier otra ficha; revisar literatura publicada hasta 2017-12-31.
- Usar primero históricos del broker específico del instrumento. Documentar retorno total/ajustes, sesiones, huecos y cobertura antes de medir la pauta.
- Separar descubrimiento de validación temporal; medir costos ejecutables y evitar selección retrospectiva de activos.

## Gates para pasar a notebook de estrategia

Aplicar [`../../GATES.md`](../../GATES.md): cobertura >=98%, muestra objetivo >=100 eventos/trades independientes (si no, pendiente por potencia), FDR q<=0.05, límite inferior del IC bootstrap 95% de la métrica primaria neta >0, resultado positivo agregado y en >=2/3 ventanas OOS, >=70% de parámetros vecinos positivos y estrés de costos 2x spread/comisión aún positivo. Son umbrales iniciales de revisión, no resultados ni garantía de potencia. Descartar si la predicción falla fuera de muestra o desaparece con costos realistas.

## Casi-pasa

Ninguno identificado; no se han ejecutado pruebas. Para cada caso futuro registrar instrumento, mecanismo, gate vinculante y evidencia.
