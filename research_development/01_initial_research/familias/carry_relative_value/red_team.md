# Red team · Carry y valor relativo

**Estado:** crítica metodológica previa a pruebas; no es un backtest ni un veredicto sobre instrumentos del repositorio. **Corte de literatura:** publicaciones hasta 2017-12-31.

## No reducir carry y valor relativo a una sola pauta

- **FX carry:** comprar divisas de tasas altas y financiar con divisas de tasas bajas. El retorno incluye diferencial de tasas/forward points y variación del spot; no es el diferencial de tasas aislado.
- **Futuros de commodities:** la pendiente de la curva y el roll afectan el retorno del contrato; “roll yield” observado no es una garantía de convergencia o prima futura.
- **Pares/valor relativo:** desviación de spread entre activos puede revertir si hay relación estable; una correlación alta o equilibrio estimado in-sample no basta.
- **CFD/broker:** swaps, horarios de rollover, dividendos, spread y convenciones de financiación son propios de la cuenta/proveedor.

Una ficha debe fijar fórmula de señal, instrumentos, moneda base, horizonte, fuente de financiación, ajuste de riesgo, venue, costos y momento de decisión antes de ver retornos.

## Evidencia primaria que condiciona la lectura

- Fama (1984) separa el diferencial forward-spot en componentes de prima y expectativa de cambio del spot, e informa que la variación observada del forward refleja en gran parte variación de prima bajo el supuesto de mercado racional. Esto enmarca una pregunta de riesgo/expectativas; no demuestra una regla carry rentable para cualquier par o periodo. [*Journal of Monetary Economics*, DOI](https://doi.org/10.1016/0304-3932(84)90046-1).
- Lustig, Roussanov y Verdelhan (2011) identifican un factor “slope” en divisas y relacionan la exposición de monedas de tasas altas con shocks de riesgo global; su explicación incluye riesgo sistemático, no arbitraje gratuito. Sus resultados pertenecen a las monedas y construcción estudiadas. [*Review of Financial Studies*, DOI](https://doi.org/10.1093/rfs/hhr068).
- Brunnermeier, Nagel y Pedersen (2009) documentan asimetría negativa/crash risk en carry y relacionan unwind con menor apetito por riesgo y liquidez de financiación. El promedio puede ocultar pérdidas concentradas; los resultados no cuantifican el swap de un CFD específico. [*NBER Macroeconomics Annual*, DOI](https://doi.org/10.1086/593088).
- Engle y Granger (1987) presentan métodos de cointegración y corrección de errores para series no estacionarias. Ese marco ayuda a plantear una relación de largo plazo, pero una prueba in-sample no demuestra estabilidad futura ni rentabilidad después de costos. [*Econometrica*, JSTOR/DOI](https://doi.org/10.2307/1913236).
- Erb y Harvey (2006) analizan futuros de commodities, term structure y estrategias de cartera, y advierten contra extrapolar rendimientos históricos ingenuamente. Es motivación para estudiar futuros específicos, no evidencia directa sobre WTIFS/USOIL CFD ni sobre el feed local. [Registro institucional de Duke](https://scholars.duke.edu/publication/1092636).

## Riesgos y controles de falsación

| Riesgo | Cómo infla o deforma el resultado | Control requerido |
|---|---|---|
| Carry mal medido | Usar solo tasas overnight o puntos forward omite cambio del spot, basis, calendario de liquidación, bid/ask y costos de financiación. | Descomponer retorno en spot, forward/funding, costos y PnL total con convenciones de moneda y fixing explícitas. Conciliar la definición con el producto que se puede negociar. |
| Tasas/funding con look-ahead | Tasas del banco central, swaps publicados al cierre o fixing descargado con fecha sin hora pueden no haber estado disponibles al decidir. Revisiones históricas pueden filtrar información. | Usar timestamp de publicación y versión disponible entonces (point-in-time); laggear datos según disponibilidad. Una señal que necesita la tasa publicada después del fill falla. |
| Swap/financiación de broker | Swaps de CFDs cambian por símbolo, lado, día triple, tasa de referencia y política del broker. Un valor actual aplicado retrospectivamente da PnL falso. | Obtener tabla histórica efectiva de swap/rollover de la cuenta o dejar costo incierto y gate pendiente; validar días triple, festivos y cambios de especificación. No imputar puntos forward institucionales como si fueran swap del retail CFD. |
| Selección de países/divisas | Elegir a posteriori las monedas que sobrevivieron, conservaron tasas altas o tuvieron buen carry elimina devaluaciones, controles de capital y crisis. | Universo point-in-time con monedas que entran/salen; registrar controles de capital, cambios de régimen, paridades y redenominaciones. Reportar exclusiones, no reconstruir solo ganadores. |
| Crash y asimetría | Ganancias frecuentes pequeñas con crashes raros producen media/Sharpe atractivos; el apalancamiento carry puede deshacer posiciones cuando cae liquidez. | Reportar skew, colas, máximas pérdidas y drawdowns, estrés de gaps, margen y riesgo de liquidación; evaluar periodos de unwind predefinidos. Promedio positivo sin soportar riesgo de cola no pasa. |
| Roll, vencimiento y curvas de futuros | Construir una serie continua con back-adjustment o roll basado en volumen/interés futuro crea señal artificial; vencimientos con liquidez distinta alteran carry observado. | Guardar contratos individuales, curva por fecha y regla de roll disponible ex ante; separar PnL spot/mark-to-market de roll y costos de ejecución. Comparar series continuas solo como diagnóstico. |
| Dividendos, borrow y basis | Pares entre acciones/índices, futuros y ETF pueden aparentar convergencia cuando se omiten dividendos, borrow, tasas, basis, expiry o coste de balanceo. | Crear cash-and-carry completo por fecha: dividendos conocidos, financiación, borrow, margen, vencimientos y roll. No llamar arbitraje a una relación histórica sin replicar costos de ambos legs. |
| Cointegración espuria/inestable | Seleccionar el par y hedge ratio que mejor encaja en la misma muestra garantiza ajuste aparente; múltiples tests cambian los valores críticos. La relación puede romperse por régimen. | Seleccionar pares y parámetros solo en train; corregir el universo de pares; reevaluar hedge ratio/spread en ventanas futuras sin reoptimizar al holdout. Exigir estabilidad económica y test de ruptura; cointegración no equivale a reversión rentable. |
| Sincronización de mercados | Cierres de FX, futuros, ADR/ETF y componentes pueden diferir por zona horaria, DST y feriados; precios stale parecen spreads extremos y luego “revierten”. | Conservar timestamps fuente y zonas IANA, alinear por información realmente disponible, excluir cotizaciones desfasadas por regla previa y validar bid/ask simultáneo. Si desaparece con sincronización correcta, descartar. |
| Selección múltiple | Probar many pairs, currencies, tenors, rebalanceos, filters de volatilidad y umbrales de z-score selecciona falsos positivos. | Prerregistrar métrica/universo; mantener listado de todos los ensayos; usar ajuste por múltiples hipótesis y holdout cronológico intacto. No reutilizar el mismo holdout para elegir. |
| Feed y costos | Fuentes gratuitas, broker, interdealer y CFD difieren en spreads, rollover, swap y sesión; una señal puede pasar solo en el sustituto. | Datos primarios por instrumento y broker; metadatos de cobertura, huecos y origen. Incluir spread por hora, comisiones, swap, slippage, financiación y margen. Si solo pasa con feed completado, marcar `NO CONFIRMADO`. |

## Evidencia que falsaría o dejaría pendiente una hipótesis

Descartar/reformular si el retorno desaparece al incluir spot/basis/financiación real; si el carry depende de datos de tasas no disponibles en el instante de decisión; si un unwind o brecha de liquidez supera límites definidos; si la curva de futuros usa un roll retrospectivo; si la relación de pares no permanece fuera de muestra; si el signo depende de un país, contrato o feed elegido retrospectivamente; o si costos de ambos legs eliminan la expectativa neta. Mantener `data_pending` cuando falten tablas históricas de swaps, dividendos, borrow, contratos o timestamps. Falta de historia no prueba que no exista efecto.

Aplicar los gates comunes de [`../../GATES.md`](../../GATES.md). No se probaron datos FX, swaps, curvas de futuros o cointegración del repositorio; no hay veredicto ni casi-pasa para Alphaca.
