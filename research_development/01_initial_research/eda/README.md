# EDA como etapa de Initial Research

EDA sirve para validar estructura, cobertura, calidad, sesiones y propiedades descriptivas de los datos. Sus gráficos y estadísticas exploratorias no prueban que una pauta sea rentable.

## Notebooks históricos

Se copiaron las nueve notebooks de `research_development/01_exploratory_data_analysis/` a `notebooks_legacy/`. Los originales permanecen allí intactos como respaldo. Las rutas relativas a `utils/` y `data/` en las copias se adaptaron al nuevo nivel; las dependencias externas (MongoDB, yfinance, credenciales y CSV del broker) no se alteraron. Revisa origen, periodo, zona horaria, huecos y ajustes antes de ejecutar.

## Checklist para EDA nueva

Usar [`templates/eda_checklist.md`](templates/eda_checklist.md) junto con la ficha YAML/Markdown de la hipótesis. Documentar siempre origen, periodo, frecuencia, zona horaria, sesiones, duplicados, huecos, cobertura calculada y transformaciones. No interpolar silenciosamente. Mantener la utilidad de gráficos existente en `research_development/utils/utils.py` hasta que una migración de imports se haga por separado.
