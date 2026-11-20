# Mean reversion · evidencia y datos

**Estado:** revisión bibliográfica e inventario de rutas/código; no es un backtest ni valida una pauta local. **Corte de literatura:** 2017-12-31. No se midió cobertura efectiva de ningún dataset.

## Evidencia primaria pre-2018

| Fuente verificable | Hallazgo publicado | Utilidad para esta familia | Límite de aplicación |
|---|---|---|---|
| De Bondt & Thaler (1985), “Does the Stock Market Overreact?”, *Journal of Finance* 40(3), 793–805. [DOI/editor](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x) | Con retornos mensuales de CRSP, los autores reportan que carteras formadas por perdedores extremos superaron a las de ganadores en el periodo posterior que estudian; describen el resultado como consistente con sobrerreacción. | Motiva una hipótesis de reversión de horizonte largo para acciones. | Es una cartera de acciones seleccionada por retornos de varios años; no prueba una señal diaria tipo RSI(2), QQQ por sí solo ni futuros/CFDs/cripto. La interpretación conductual no queda identificada causalmente solo por el retorno posterior. |
| Jegadeesh (1990), “Evidence of Predictable Behavior of Security Returns”, *Journal of Finance* 45(3), 881–898. [DOI/editor](https://doi.org/10.1111/j.1540-6261.1990.tb05110.x) | Reporta autocorrelación mensual de primer orden negativa y correlaciones positivas a lags mayores en acciones individuales, junto con previsibilidad de retornos. | Importa porque el signo de reversión depende del horizonte: una pauta no debe definirse como “reversión” sin horizonte concreto. | Resultados de acciones y frecuencias mensuales; no verifican retornos intradía o de un instrumento aislado. La correlación predictiva no equivale a rentabilidad neta ejecutable. |
| Lehmann (1990), “Fads, Martingales, and Market Efficiency”, *Quarterly Journal of Economics* 105(1), 1–28. [DOI/Oxford](https://doi.org/10.2307/2937816) · [NBER working paper](https://www.nber.org/papers/w2533) | Reporta reversiones semanales de ganadores/perdedores recientes en acciones, incluso tras ciertos ajustes de spreads y costos plausibles dentro de su diseño. | Aporta evidencia de reversión a horizonte corto en portafolios de acciones; el propio paper discute liquidez alrededor de movimientos grandes como posible mecanismo. | Muestra, época, universo y estimación de costos del estudio no representan fills actuales de ETF/CFD ni datos minuto a minuto. El NBER WP es de 1988; la publicación revisada por pares es de 1990. |
| Lo & MacKinlay (1990), “When Are Contrarian Profits Due to Stock Market Overreaction?”, *Review of Financial Studies* 3(2), 175–205. [DOI/Oxford](https://doi.org/10.1093/rfs/3.2.175) | Muestran que retornos contrarian de cartera pueden surgir de cross-autocorrelaciones entre acciones (grandes liderando pequeñas), aun cuando los retornos individuales no tengan autocorrelación negativa; concluyen que la sobrerreacción no es la única fuente. | Exige separar reversión de un activo de una estrategia cross-sectional y medir dependencias entre instrumentos. | No demuestra una regla universal ni respalda atribuir toda ganancia contrarian a sobrerreacción.

Los abstracts/editoriales y DOI de las cuatro referencias se consultaron directamente. Todas son anteriores al corte 2018. Sus resúmenes motivan preguntas, pero no reemplazan la lectura de diseños y resultados completos al definir cada ficha.

## Inventario observable del repositorio

Solo se revisaron nombres de archivos y celdas de carga de la EDA histórica. Las fechas incluidas en nombres son rangos nominales; no establecen continuidad, proveedor íntegro ni cobertura porcentual.

| Candidato | Lo observable | Lo que falta para una prueba de reversión |
|---|---|---|
| QQQ (ETF) | `01_exploratory_data_analysis/QQQ_EDA.ipynb` descarga QQQ con `yfinance`, inicio nominal `1999-01-01` y `auto_adjust=True`. No existe `research_development/data/t20/prices/QQQ.csv` en el inventario consultado. La notebook muestra un resumen de barras al ejecutarse; no se verificó aquí el resultado ni se guardó un dataset local. | La descarga depende del proveedor disponible al ejecutar. Identificar broker de ejecución, rango y huecos reales, split/dividend adjustments, OHLC usados para señales y precio negociable para fills; comparar una fuente fiable gratuita antes de seleccionar proveedor. La base autoajustada es útil para retornos ajustados, pero no representa por sí sola fills históricos. Cobertura: desconocida. |
| Acciones individuales | Hay numerosos CSV en `data/t20/prices/`, incluido `SPY.csv`; el universo incluye acciones por ticker. Los nombres no certifican composición histórica point-in-time ni metadatos de origen/ajustes. | Verificar fuente/licencia, survivorship, delistings, corporate actions, zonas horarias y fechas. Para una estrategia cross-sectional, reconstruir el universo que era observable en cada fecha; una carpeta de símbolos actuales no basta. |
| ES/NQ/6E/6J (futuros) | Las EDA de ES, NQ, 6E y 6J leen colecciones MongoDB indicadas por código. No inspeccionar credenciales ni consultar colecciones en este inventario. | Fuente, contratos, rango, gaps, timezone, settlement, rollover y bid/ask quedan sin confirmar. Priorizar datos del broker/venue y separar reversión de precio por contrato de efectos de empalme.
| FX/CFD, energía y crypto | El repositorio contiene ficheros identificados por ruta como Axi/MT5 para algunos instrumentos (por ejemplo USDJPY, WTIFS/USOIL y BTCUSD), y algunos ficheros Darwinex/Dukascopy. Esto es evidencia de existencia de ficheros, no de integridad ni continuidad. | Verificar instrumento y broker exactos, columnas, rango, huecos, spread, swaps, horario de servidor y cambio de especificación. La evidencia de acciones no se extrapola automáticamente a estos feeds OTC o 24/7. Cobertura: desconocida.

## Preguntas de datos y pruebas sugeridas (no ejecutadas)

1. Separar **reversión temporal** (retorno pasado del mismo instrumento predice retorno futuro opuesto) de **contrarian transversal** (comprar perdedores y vender ganadores dentro de un universo). La literatura citada estudia ambas estructuras a distintos horizontes; son hipótesis y datasets distintos.
2. Para QQQ, declarar antes de medir la pauta, frecuencia, horizonte y benchmark. Usar primero datos del broker de ejecución; usar serie ajustada de mercado para retornos de inversión como comparación independiente, con fuente y método de ajuste identificados.
3. Para acciones múltiples, evitar selección retrospectiva/supervivencia: universo point-in-time, instrumentos retirados y ajuste por comparaciones múltiples. Para futuros, fijar el rollover antes de calcular y revisar si empalmes producen reversión artificial.
4. En alta frecuencia, usar quotes/bid-ask y timestamps para tratar bid-ask bounce, spreads variables, latencia y ejecuciones; en CFD añadir swaps y horario del broker. La evidencia semanal/mensual no valida una regla intradía.
5. Registrar en metadatos origen, cobertura calculada, huecos, timezone, sesiones, ajustes y diferencias esperadas. No rellenar huecos. Si una hipótesis solo pasa con fuentes sustitutas/datos completados, marcar `NO CONFIRMADO`.

## Incertidumbres explícitas

- Ningún dataset fue leído o consultado para medir cobertura; ninguna credencial fue consultada.
- No hay veredicto de reversión, edge validado ni caso casi-pasa en esta revisión.
- La fuente actualmente llamada por `yfinance` y su política de entrega pueden variar; todavía no se evaluó una fuente gratuita fiable y versionable para ETF. Esa elección y límites pertenecen a la fase de datos.
- El inventario de nombres de archivo no equivale a cobertura; todos los orígenes/huecos no demostrados permanecen desconocidos.
