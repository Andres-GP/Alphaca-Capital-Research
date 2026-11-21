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

El conector MT5 y el workflow ya contemplan una descarga incremental de una lista allow-listed a un VPS Windows persistente, sin subir los CSV al repositorio. La activación depende de registrar ese VPS como runner, configurar las variables/secrets indicados en `data_pipeline/README.md` y rellenar `data_pipeline/market_data_universe.yaml` con los símbolos exactos de ambas cuentas.

Dukascopy permite una fuente adicional, pero su ruta automática de archivos S3 usa Requester Pays y factura transferencia al descargador. El usuario indicó preferir fuentes gratuitas, así que no se activó ni se descargó. Para ETFs, el feed gratuito IEX de una API como Alpaca no representa el mercado estadounidense consolidado; Darwinex debe confirmar que sirve los ETFs concretos en MT5. No afirmar que hay una segunda fuente ETF gratuita de calidad de ejecución hasta comprobarla.

## Pendiente para completar la corrida automática

1. El usuario debe indicar símbolos exactos de Axi/Darwinex y marcos temporales que quiere cubrir; no conviene bajar todos los símbolos de la cuenta.
2. Deben configurarse el runner Windows, sus terminales MT5 y credenciales de solo lectura en GitHub.
3. Hay que decidir si se acepta el pequeño costo de transferencia de Dukascopy S3 o se omite ese feed. Ninguna compra/proveedor de datos pagado queda aprobado.
4. El runner todavía solo ejecuta hipótesis con preregistro `frozen`; generar y congelar automáticamente nuevas fichas debe respetar el orden preregistro→lectura del dataset→resultado para reducir data snooping.
