# Handoff · Carry y valor relativo

## Probado y no probado

- En esta fase solo se creó la estructura. No se ejecutó investigación ni backtest para esta familia.
- No hay edges declarados, resultados propios ni casos casi-pasa registrados.

## Pruebas pendientes y datos

- Definir el mecanismo (financiación, futuros, cesta o relación relativa), fórmula, sincronización y exposición.
- Obtener precios del broker/venue de ejecución y series del instrumento de referencia; añadir swaps, rollovers, dividendos, borrow y costes aplicables.
- Comparar distintas fuentes con metadatos de cobertura y feed; marcar `NO CONFIRMADO` si una señal pasa solo con datos sustitutos.

## Gates para pasar a notebook de estrategia

Aplicar [`../../GATES.md`](../../GATES.md): cobertura >=98%, muestra objetivo >=100 eventos/trades independientes (si no, pendiente por potencia), FDR q<=0.05, límite inferior del IC bootstrap 95% de la métrica primaria neta >0, resultado positivo agregado y en >=2/3 ventanas OOS, >=70% de parámetros vecinos positivos y estrés de costos 2x spread/comisión aún positivo. Son umbrales iniciales de revisión, no resultados ni garantía de potencia. Descartar si depende de precios asincrónicos o carry no disponible para la cuenta.

## Casi-pasa

Ninguno identificado; no se han ejecutado pruebas.
