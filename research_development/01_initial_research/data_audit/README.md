# Auditoría inicial del inventario de datos

`local_datasets.csv` enumera los 528 CSV encontrados bajo `research_development/data/`. Se generó a partir de rutas y nombres; no se leyó ni se recalculó el contenido completo de los archivos. Por eso, las fechas inferidas de nombres son nominales y no equivalen a cobertura verificada.

## Interpretación

- `origin_label` es una pista basada en la ruta o el nombre, no una verificación de proveedor.
- `origin_verified=no` indica que falta confirmar proveedor, instrumento, tipo de precio y condiciones de licencia.
- `coverage_pct` queda desconocida hasta comparar timestamps con el calendario de sesiones pertinente. No se calcularon porcentajes ni se rellenaron series.
- `gap_status` indica que no se midieron huecos; no debe interpretarse como continuidad.
- `expected_feed_differences` enumera diferencias que deben reconciliarse antes de comparar resultados entre feeds.

Los ficheros disponibles muestran fuentes/rutas asociadas con Axi, Darwinex, Dukascopy y series diarias tipo Yahoo Finance. Los CSV locales no tienen un manifiesto uniforme con zona horaria, sesiones, ajustes, instrumento exacto y ventana solicitada. Las colecciones Mongo y cualquier fuente que requiera credenciales o acceso remoto quedan fuera de esta auditoría. No se leyeron credenciales.

## Estado para investigación

Las fichas de hipótesis siguen en `data_pending`. Hasta validar el feed y la cobertura requerida, no se puede declarar una prueba completa ni confirmar un edge. Si un resultado futuro depende de datos rellenados o de empalmar proveedores, debe etiquetarse `NO CONFIRMADO` y documentar el tramo afectado.

## Próximos datos de metadatos

Para cada serie usada, completar proveedor/origen, instrumento y símbolo, granularidad, zona horaria, sesión/calendario esperado, primera y última observación, cobertura porcentual, huecos, ajustes, costes/spreads/swaps aplicables, fecha de descarga y diferencias esperadas frente a feeds de broker. La cobertura debe calcularse solo tras definir el calendario de observaciones esperado.
