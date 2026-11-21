# Comparación del proceso y cambios de eficiencia

Consulta: 2026-11-20. Alcance: `01_initial_research` y el repositorio adjunto `Alphaca-Capital-Data`. No se modificaron etapas `02`, `03` ni `04`.

| Referencia | Práctica útil | Diferencia/brecha observada | Decisión para Initial Research |
|---|---|---|---|
| `Alphaca-Capital-Data` | Workflow programado, descarga incremental y almacenamiento separado del código (MongoDB). | El validador local compara colecciones con `ES=F` aunque pertenezcan a otros símbolos y marca gaps con un umbral fijo de 60 minutos; no valida el calendario y feed de cada instrumento. | Reutilizar el patrón de actualización periódica, pero traer la historia específica de la cuenta MT5 y validar cada símbolo contra su calendario. MongoDB no es requisito. |
| Microsoft Qlib Recorder | Cada experimento tiene una corrida registrada con parámetros, métricas y artifacts. [Documentación de Recorder](https://github.com/microsoft/qlib/blob/main/docs/component/recorder.rst) | Añadir Qlib/MLflow sería más infraestructura de la que requiere el ejecutor inicial actual. | Adoptar el contrato de trazabilidad en `experiment_manifest.json`: commit, run ID, hashes, parámetros, feed, costos, resultados y archivos generados. |
| Recomendación de gates reproducibles | Los gates requieren inputs, reglas, fechas y costos verificables; IA asesora, código bloquea incumplimientos. | Antes había varios controles deterministas, pero el resultado no fijaba el hash de los datos ni conectaba formalmente el test con la necesidad del usuario. | El preregistro v2 exige el hash de dataset/calendario y referencia/hash del brief. Rutas externas solo se resuelven bajo el directorio de datos del runner. |

## Motores cuantitativos

No se añadió un motor común que trate momentum, carry, estacionalidad y gaps como si fueran la misma operación. El runner actual admite solo momentum de serie temporal y reversión de serie temporal con OHLC. Aún no modela ticks, bid/ask histórico, fills, swaps históricos ni rollovers; por eso esas familias deben quedar en `HOLD_SPECIFICATION` hasta que una hipótesis y su fuente de datos tengan una implementación específica.

## Estado de automatización de datos

El conector MT5 y el workflow descubren automáticamente los símbolos negociables de Axi y Darwinex y refrescan las nueve temporalidades MT5 habilitadas (M1, M5, M15, M30, H1, H4, D1, W1 y MN1), hasta 16 series por corrida, en el VPS Windows persistente. Los CSV quedan fuera del repositorio. La activación depende de registrar ese VPS como runner y configurar las variables/secrets indicados en `data_pipeline/README.md`; el YAML define marcos y rango inicial, no exige transcribir símbolos.

Dukascopy se consulta automáticamente mediante el mismo paquete y método ya usado por `utils/download_dukascopy.py`, solo para coincidencias de símbolo únicas; su feed BID queda separado y sus resultados se confirman con el broker. Yahoo Finance explora series D1 de los ETFs que el catálogo MT5 de Darwinex clasifique como tales. La asignación de ticker es tentativa y Darwinex valida los candidatos. Ninguna de esas fuentes cambia los límites de spread, swaps, fills o ejecución que tienen los históricos de barras del broker.

## Pendiente para completar la corrida automática

1. Configurar y registrar el runner Windows, sus terminales MT5, rutas, directorio de datos persistente y credenciales de lectura en GitHub.
2. Revisar el backlog y los fallos de descarga en los resúmenes de `RESEARCH_DATA_DIR`; la cobertura completa se construye por lotes.
3. Las fuentes no amplían los motores: el runner todavía solo ejecuta hipótesis con preregistro `frozen` y motores implementados. Nuevas fichas deben congelarse antes de usar datos para reducir data snooping.
