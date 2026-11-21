# 01 · Initial Research

Etapa para identificar mecanismos económicos o estructurales, registrar evidencia histórica y decidir qué hipótesis merece pasar a `02_strategy_development`. Una hipótesis es una pregunta comprobable; no es un edge validado.

## Estructura

```text
01_initial_research/
├── familias/<familia>/<pauta>/<mercado>/
│   ├── hypothesis.yaml
│   └── hypothesis.md
├── familias/<familia>/handoff.md
├── research_brief.md           # Necesidad actual; contexto para todas las familias
├── backtests_exploratorios/    # Pruebas iniciales solo tras pasar el Gate A
├── eda/
│   ├── notebooks_legacy/       # Copias de las EDA existentes, con rutas adaptadas
│   └── templates/
├── templates/                  # Ficha estandarizada YAML + Markdown
└── reportes/<fecha>_<familia>/ # Salida de cada investigación
```

La taxonomía inicial de `familias/` es provisional: organiza preguntas para investigar, no afirma que exista un edge. Crear una pauta o mercado implica completar la ficha con fuentes verificables y estado explícito.

## Proceso y estados

1. Registrar mecanismo, predicción falsable y evidencia anterior a 2018 en la ficha.
2. Documentar fuente, cobertura, huecos, feed y diferencias de sesión en los metadatos del dataset.
3. Hacer EDA para entender calidad y estructura de datos; no usarla para declarar validez.
4. Aplicar Gate A de [`GATES.md`](GATES.md). Solo una hipótesis con estado `READY_FOR_EXPLORATORY_BACKTEST` y preregistro congelado puede pasar a `backtests_exploratorios/`.
5. El backtest inicial sirve como filtro de implementación y descarte, no como confirmación. Aplicar Gate B antes de proponer validación confirmatoria; aplicar Gate C antes de afirmar que hay evidencia empírica.
6. Pasar a `02_strategy_development` solo con handoff trazable y autorización del flujo de desarrollo correspondiente. Si una prueba depende de datos rellenados, marcar `NO CONFIRMADO`.

Antes de cada corrida, actualiza [`research_brief.md`](research_brief.md) con la necesidad que quieres resolver. El workflow incluye ese brief en los cuatro roles de revisión de cada familia y les pide priorizar la relevancia, sin rebajar los requisitos de evidencia.

El workflow automático de Initial Research realiza análisis documental y califica la preparación; no ejecuta backtests. La carpeta `backtests_exploratorios/` recibe artefactos solo cuando una hipótesis pasa el gate y tiene datos y reglas verificados. Las fichas existentes no se consideran aprobadas por defecto.

Las citas se enlazan a la fuente primaria siempre que sea posible. Una fuente no localizada se etiqueta `no verificada`; no se inventan resultados, cobertura ni citas.

## Diseño de reportes

Referencia visual revisada el 2026-11-20: [landing de Alphaca Capital](https://alphaca-capital-landing.vercel.app/). La página declara tema oscuro. Los estilos observados usan verde bosque `#1F3D36`, acento lima `#C8F5A8`, tipografía Bricolage Grotesque y espaciado basado en incrementos de 4 px. Mantener jerarquía editorial sobria, títulos directos, suficiente espacio y tablas legibles. Para gráficos cuantitativos, conservar la paleta existente en `research_development/utils/utils.py` (fondo `#15171c`, panel `#1b1e26`, verde `#34d399`, rojo `#f0555a`, ámbar `#f5a524`), usando el verde de marca como acento de títulos o navegación, no alterando el significado de las series.

## EDA histórica

Las nueve EDA originales siguen en `../01_exploratory_data_analysis/` sin cambios. Copias de trabajo están en [`eda/notebooks_legacy/`](eda/notebooks_legacy/); sus rutas relativas se adaptaron al nuevo nivel de carpeta. Esa copia conserva las salidas existentes. Antes de una ejecución, confirmar credenciales y cobertura de cada fuente de datos.

## Handoff y reportes

Cada familia mantiene un `handoff.md` que distingue lo probado de lo pendiente y registra datos y gates necesarios. El formato de ficha está en [`templates/`](templates/); las salidas finales se guardan bajo `reportes/` con una fecha y familia en el nombre.
