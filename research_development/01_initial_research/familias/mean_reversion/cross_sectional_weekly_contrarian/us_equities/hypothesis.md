# Reversión semanal contrarian en acciones de EE. UU.

> **Estado:** `data_pending` · **Familia:** mean_reversion · **Pauta:** cross-sectional weekly contrarian · **Mercado:** acciones ordinarias de EE. UU. · **Corte de evidencia:** 2017-12-31

## Pregunta y predicción falsable

En un universo point-in-time predefinido de acciones ordinarias de EE. UU., ¿un portafolio long-losers/short-winners formado por retornos de la semana previa obtiene retorno neto positivo durante la semana siguiente frente a un control fijado de antemano? Separar reversión de retornos propios y autocovarianza cruzada entre títulos antes de interpretar el mecanismo.

## Mecanismo económico o estructural

La presión transitoria de liquidez o negociación podría revertir parte del movimiento reciente. Otra explicación es el liderazgo rezagado entre títulos, capaz de crear beneficio de cartera contrarian sin autocorrelación negativa propia en cada acción. Estas explicaciones compiten; no se asume cuál opera.

## Evidencia previa a 2018

- Lehmann (1990), [*Fads, Martingales, and Market Efficiency*](https://doi.org/10.2307/2937816), reporta reversiones semanales de carteras de ganadores/perdedores en su muestra de acciones. No confirma fills o costos actuales.
- Lo y MacKinlay (1990), [*When Are Contrarian Profits Due to Stock Market Overreaction?*](https://doi.org/10.1093/rfs/3.2.175), muestran que efectos cruzados entre activos pueden generar beneficios contrarian de cartera sin reversal propio.

La evidencia apoya investigar la estructura de cartera en acciones; no valida una pauta específica, QQQ ni operaciones de corto plazo para una cuenta actual.

## Mercados aplicables

Acciones ordinarias de EE. UU. La carpeta T20 del repo contiene precios por ticker, pero su universo histórico y origen no están verificados. Un ETF como QQQ no replica el mismo universo/estrategia y requeriría ficha separada.

## Riesgos y explicaciones alternativas

- Supervivencia y delistings, sesgo de selección del universo, y múltiples horizontes/umbrales.
- Bid-ask bounce, spreads que aumentan en títulos extremos, baja liquidez y costos de short/borrow.
- Autocovarianzas cruzadas pueden explicar el portafolio sin reversión de cada instrumento.
- Ajustes de corporate actions, cierres, retrasos de información y diferencias entre retorno ajustado y fill negociable.

## Datos requeridos

Se necesita composición point-in-time del universo, acciones retiradas, retornos ajustados para medir desempeño, precios sin ajustar para fills, bid-ask/spreads, volumen, corporate actions y costo de préstamo/short. Existe un archivo por ticker, pero cobertura, proveedor y sesgo de supervivencia no se comprobaron. Por tanto, `coverage: unknown` y no se ejecutó prueba.

## Gates y veredicto

- Estadística, robustez y costos: **pendientes**; aplicar [`../../../../GATES.md`](../../../../GATES.md).
- **Veredicto actual:** no probado, `data_pending`; la ficha no indica edge válido.

## Próximo paso

Comprobar si se dispone de universo point-in-time que incluya títulos retirados y costos históricos ejecutables. Si no, limitar la pregunta y marcar explícitamente el sesgo no resuelto.
