# Literatura y mecanismo · reversión a la media

**Alcance.** Este informe se centra en la hipótesis de reversión semanal contrarian entre acciones ordinarias de EE. UU. La literatura citada motiva pruebas; no valida una señal del repositorio. No se han inspeccionado datos ni ejecutado backtests.

## Mecanismos posibles

- **Presión transitoria de liquidez.** Una necesidad temporal de comprar o vender puede mover precios y después revertirse cuando cede la presión. Lehmann interpreta sus resultados semanales como posiblemente relacionados con la liquidez alrededor de movimientos grandes. Es una explicación propuesta, no un mecanismo demostrado para los datos de este proyecto.
- **Sobrerreacción.** Los inversores podrían extrapolar demasiado noticias o movimientos recientes y corregir después sus valoraciones. De Bondt y Thaler encuentran evidencia compatible con esta explicación en carteras de acciones formadas a partir de retornos de varios años; eso no establece que explique reversiones semanales.
- **Dependencia entre acciones.** Una cartera que compra perdedores y vende ganadores puede beneficiarse de relaciones de liderazgo y rezago entre títulos, incluso sin reversión propia en cada acción. Por tanto, el retorno contrarian de una cartera no identifica por sí solo el mecanismo.

## Predicciones falsables

Para la ficha semanal, conviene fijar antes de medir:

1. Si los retornos de la semana previa predicen retornos de signo contrario durante la siguiente semana en las mismas acciones, y si el resultado neto supera un control predefinido.
2. Si la señal persiste al modelar bid-ask, costos de transacción, liquidez y restricciones de venta corta, con universo point-in-time y títulos retirados incluidos.
3. Si el retorno de cartera se mantiene al separar autocorrelación propia de autocovarianzas cruzadas y efectos de liderazgo entre acciones.
4. Si la conclusión se sostiene en ventanas cronológicas fuera de muestra sin escoger retrospectivamente umbrales, horizontes o filtros.

Estas son pruebas propuestas, no resultados obtenidos.

## Estudios relevantes publicados antes de 2018

- **Bruce N. Lehmann (1990), “Fads, Martingales, and Market Efficiency.”** Reporta reversión semanal de carteras de ganadores y perdedores en su muestra, que persiste tras ciertos ajustes de spread y costos plausibles en el diseño del estudio. Propone que el resultado probablemente refleja ineficiencia en el mercado de liquidez alrededor de movimientos grandes. La muestra y los costos del artículo no establecen ejecutabilidad actual. [*The Quarterly Journal of Economics*, DOI](https://doi.org/10.2307/2937816).
- **Andrew W. Lo y A. Craig MacKinlay (1990), “When Are Contrarian Profits Due to Stock Market Overreaction?”** Muestran que las estrategias contrarian pueden obtener retornos esperados por relaciones de liderazgo y rezago entre acciones; reportan liderazgo de acciones grandes sobre pequeñas y concluyen que la sobrerreacción no es la única fuente posible de beneficios contrarian. [*The Review of Financial Studies*, DOI](https://doi.org/10.1093/rfs/3.2.175).
- **Richard Roll (1984), “A Simple Implicit Measure of the Effective Bid-Ask Spread in an Efficient Market.”** Analiza cómo las transacciones que alternan entre bid y ask pueden inducir autocovarianza negativa en los retornos observados. Esto hace necesario distinguir reversión económica de rebote de cotización, especialmente a frecuencias altas. [*The Journal of Finance*, DOI](https://doi.org/10.1111/j.1540-6261.1984.tb03897.x).
- **Werner F. M. De Bondt y Richard Thaler (1985), “Does the Stock Market Overreact?”** Encuentran resultados compatibles con sobrerreacción en carteras de acciones basadas en retornos mensuales de CRSP y movimientos extremos de varios años. Motivan una hipótesis de reversión de largo plazo; no prueban una regla semanal. [*The Journal of Finance*, DOI](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x).
- **Narasimhan Jegadeesh (1990), “Evidence of Predictable Behavior of Security Returns.”** Reporta autocorrelación negativa mensual de primer orden y autocorrelación positiva a rezagos mayores en acciones individuales. El signo de la predictibilidad depende del horizonte, así que “reversión” debe definirse con precisión temporal. [*The Journal of Finance*, DOI](https://doi.org/10.1111/j.1540-6261.1990.tb05110.x).

## Límites de inferencia y preguntas abiertas

Estos estudios difieren en periodo, frecuencia, universo y diseño. Sus resultados no demuestran rentabilidad neta actual, ni se trasladan automáticamente a QQQ, futuros, CFDs, FX o cripto. Tampoco permiten atribuir una reversión observada a sobrerreacción sin descartar liquidez, microestructura y dependencias entre títulos.

Para esta familia siguen abiertas preguntas sobre la cobertura y procedencia de los datos, la composición histórica del universo, delistings, costos de short y spreads condicionales a la señal. El estado actual de la hipótesis semanal del repositorio es `data_pending`: no hay resultados propios ni edge validado.