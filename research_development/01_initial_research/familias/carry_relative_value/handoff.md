# Handoff · Carry y valor relativo

## Probado y no probado

- Se completó revisión bibliográfica inicial y crítica metodológica en `literature_review.md`, `evidence_and_data.md` y `red_team.md`.
- Se creó una ficha de carry transversal FX G10 como `data_pending`; no se localizaron forward points del repo, ni se ejecutaron backtests/gates.
- No hay edges declarados, resultados propios ni casos casi-pasa registrados.

## Pruebas pendientes y datos

- Decidir pauta por separado (FX carry, basis de futuros o pares). Para la ficha FX actual, obtener universo G10 y forward points/tasas point-in-time; USDJPY spot/CFD no es sustituto.
- Obtener precios del broker/venue de ejecución y series del instrumento de referencia; añadir swaps, rollovers, dividendos, borrow y costes aplicables.
- Comparar distintas fuentes con metadatos de cobertura y feed; marcar `NO CONFIRMADO` si una señal pasa solo con datos sustitutos.

## Gates para pasar a notebook de estrategia

Aplicar [`../../GATES.md`](../../GATES.md): cobertura >=98%, muestra objetivo >=100 eventos/trades independientes (si no, pendiente por potencia), FDR q<=0.05, límite inferior del IC bootstrap 95% de la métrica primaria neta >0, resultado positivo agregado y en >=2/3 ventanas OOS, >=70% de parámetros vecinos positivos y estrés de costos 2x spread/comisión aún positivo. Son umbrales iniciales de revisión, no resultados ni garantía de potencia. Descartar si depende de precios asincrónicos o carry no disponible para la cuenta.

## Casi-pasa

Ninguno identificado; no se han ejecutado pruebas.
