# Informe de evidencia y datos · Reversión a la media

**Familia:** mean_reversion  
**Fecha de corte:** 2026-11-20  
**Estado:** `data_pending`; no hay datos verificados para una prueba de la hipótesis semanal.  
**Alcance:** se inspeccionaron manifiestos, documentación y código. No se abrieron CSV de mercado, no se descargaron datos y no se calcularon cobertura ni huecos.

## Dictamen

Los datos descritos en el repositorio no bastan para pasar la hipótesis de reversión semanal contrarian a un notebook de estrategia. Hay archivos de precios por ticker y un archivo de membresía S&P 500, pero sus metadatos no acreditan un universo histórico completo, precios de acciones retiradas, continuidad ni costos ejecutables.

El manifiesto local enumera 528 rutas CSV bajo `research_development/data/`: 501 corresponden a `t20/prices/`. Son conteos de rutas del manifiesto, no comprobaciones del contenido. Para esos precios, el manifiesto marca origen como no verificado, cobertura desconocida y huecos no medidos. También lista `t20/sp500_membership.csv`, pero no acredita su procedencia ni su integridad. La auditoría explica que las fechas inferidas de nombres son nominales y que no se compararon timestamps con calendarios de sesión.  
Fuentes locales: `data_audit/README.md`, `data_audit/local_datasets.csv`.

La EDA de QQQ descarga con `yfinance` desde una fecha nominal de 1999 y usa `auto_adjust=True`. El manifiesto no registra un `QQQ.csv` local. QQQ sería una ficha distinta: no sustituye una cartera transversal de acciones. La auditoría de fuentes tampoco considera garantizada una descarga gratuita e histórica de Yahoo para QQQ.  
Fuentes locales: `eda/notebooks_legacy/QQQ_EDA.ipynb`, `data_audit/source_evaluation.md`.

## Datos descritos en el repositorio y límites observados

| Componente | Descrito o presente en el repo | Lo verificado en esta corrida | Pendiente para usarlo |
|---|---|---|---|
| Precios diarios T20 | Archivos por ticker; el código de T20 usa Yahoo Finance vía `yfinance`, con precios ajustados por splits y dividendos. | Código y rutas del manifiesto inspeccionados; no se leyeron CSV. | Proveedor y licencia por archivo, rango real, zona horaria, campos, corporate actions, huecos y precios de ejecución. |
| Universo S&P 500 | Hay una ruta `t20/sp500_membership.csv`. El código de T20 reconstruye intervalos con la lista actual y el historial de cambios de Wikipedia; contempla una degradación a miembros actuales. | Código inspeccionado. Documenta que los precios de retiradas son escasos en Yahoo y que el modo de solo miembros actuales tiene sesgo de supervivencia fuerte. | Verificar qué modo produjo el archivo local, fechas cubiertas, tickers reutilizados y si contiene todos los cambios y retiradas necesarios. No asumir que el archivo presente elimina el sesgo. |
| `download_failed.csv` | El código de T20 puede guardar tickers no descargados. | La ruta aparece en el manifiesto; su contenido no se abrió. | Identificar los símbolos y determinar si faltan precisamente acciones retiradas o semanas críticas. |
| QQQ | La notebook usa `yfinance`, `auto_adjust=True` y solicita barras diarias desde 1999. | Se verificó el código fuente de la notebook, no la ejecución ni el resultado descargado. | Broker/venue, cobertura efectiva, ajustes, sesiones y precio cotizable para fills. No usarlo como sustituto de la hipótesis transversal. |
| Otros instrumentos | El inventario incluye rutas etiquetadas Axi, Darwinex y Dukascopy; las EDA de ES/NQ/6E/6J cargan colecciones MongoDB. | Se verificaron etiquetas, código de carga y advertencias escritas en las auditorías, no los datos ni las colecciones. | Quedan fuera de esta ficha de acciones. No extrapolar evidencia ni mezclar feeds sin una ficha propia. |

En acciones, los retornos ajustados sirven para medir desempeño y manejar distribuciones/corporate actions; no son precios de fill. Se necesitan precios negociables y costos. Los precios ajustados automáticos de Yahoo, por sí solos, no prueban cómo habría ejecutado la cartera.

## Fuente prioritaria para esta hipótesis

La hipótesis registrada trata de acciones ordinarias de EE. UU. en una cartera long-losers/short-winners semanal. Para ese caso:

1. **Universo y retornos históricos:** priorizar una fuente con composición point-in-time, identificadores históricos, acciones retiradas y retornos de delisting; CRSP es una referencia de datos apropiada si está disponible y su licencia permite el uso. La membresía S&P 500 reconstruida desde la lista actual y Wikipedia puede servir como sensibilidad documentada, no como universo validado por sí sola.
2. **Ejecución:** priorizar datos del broker/venue donde se ejecutaría la estrategia para precios de entrada y salida, bid/ask o spreads, y comisiones. Para el tramo short hacen falta costos históricos de préstamo y restricciones de disponibilidad.
3. **Fuentes gratuitas o feeds alternativos:** usarlos como contraste identificado por fuente y período. Si se empalman con otro proveedor, marcar todo resultado dependiente del empalme como **`NO CONFIRMADO`** y reportar cada segmento por separado.

La auditoría del repo indica que Dukascopy puede complementar historia de algunos CFDs, pero no replica las condiciones de Darwinex. Esa observación no resuelve datos de acciones ni costos de short de acciones.

## Cobertura, calendario, sesiones y costos

A día de hoy, **cobertura y huecos son desconocidos**. No hay porcentaje calculado ni se debe inferir continuidad a partir de rangos nominales o número de archivos.

Para medirlos de forma reproducible, primero fijar el universo point-in-time y luego construir el calendario de sesiones de cada mercado en `America/New_York`, incluyendo festivos y cierres anticipados. Definir la semana de formación como la última sesión regular disponible y calcular el denominador sobre las observaciones símbolo-semana en que cada título pertenecía al universo y debía tener datos. Publicar el numerador, el denominador, las exclusiones y las reglas de faltantes; no rellenar huecos. Para títulos que dejan de cotizar, registrar el evento y el retorno de delisting en vez de eliminar la observación.

La señal de la semana debe estar disponible antes de ejecutar. Si se forma con el cierre de la última sesión, modelar el fill en la siguiente oportunidad ejecutable, no en ese mismo cierre. Separar retornos ajustados usados para el cálculo estadístico de precios y cotizaciones usados para el PnL. Estimar costos condicionados a los títulos extremos y al lado de la operación: spreads, comisiones, slippage y préstamo de acciones. Una cotización mid puede servir de diagnóstico, pero no reemplaza el precio ejecutable.

Las diferencias entre feeds que deben registrarse incluyen ajustes por dividendos y splits, cierres y sesiones, identificadores reutilizados, liquidez en títulos extremos, spreads y disponibilidad de préstamo. El código de T20 documenta además un modo de membresía con solo integrantes actuales y carencia de precios de muchos títulos retirados; cualquier resultado construido así no elimina el sesgo de supervivencia.

## Plan mínimo reproducible

1. **Fijar la ficha antes de medir:** universo, semana de formación, semana de tenencia, ponderación, benchmark y ejecución posterior a la señal. Mantener separadas reversión propia de cada título y autocovarianza cruzada de cartera.
2. **Auditar el universo:** documentar la fuente de membresía, intervalos efectivos, títulos añadidos y retirados, identificadores, corporaciones reutilizadas y modo de generación del archivo local.
3. **Auditar cada serie sin completar datos:** registrar origen, versión/fecha de extracción, campos, zona horaria, calendario, primer y último timestamp, duplicados, huecos y corporate actions. Calcular cobertura sobre semanas símbolo elegibles; conservar y explicar datos faltantes.
4. **Alinear feeds y ejecuciones:** comparar cierres semanales en fechas coincidentes y describir las diferencias frente al broker/venue. Usar cotizaciones o precios ejecutables para el PnL y costos históricos de short. No interpolar ni asumir fills al mid.
5. **Entregar evidencia para la puerta de entrada:** manifiesto por serie, método y denominador de cobertura, registro de huecos/exclusiones, evidencia de delistings, costos y prueba de reconciliación de feeds. Solo entonces crear el notebook de estrategia y aplicar los gates comunes de [`GATES.md`](research_development/01_initial_research/GATES.md), incluidos cobertura mínima, muestra independiente, control de comparaciones, ventanas OOS y estrés de costos.

**Resultado de esta revisión:** no hay backtest ni edge propio verificado. La ficha permanece `data_pending`; una prueba basada únicamente en las rutas T20 existentes no demostraría aún cobertura point-in-time ni rentabilidad neta ejecutable.