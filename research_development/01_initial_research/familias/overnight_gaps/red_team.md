# Red team · Gaps y transiciones de sesión

**Estado:** crítica metodológica previa a pruebas; no es un backtest ni un veredicto sobre mercados del repositorio. **Corte de literatura:** publicaciones hasta 2017-12-31.

## Primero, fijar qué significa “gap”

“Gap overnight” no es una definición suficiente. Una ficha debe especificar el instrumento y venue, calendario, precio de cierre, precio de apertura, horizonte y fill:

1. **Cierre a apertura de acciones/ETF:** último precio de la sesión regular anterior a primera cotización/subasta de la nueva sesión. Este retorno ocurre mientras el instrumento no negocia en la sesión regular; un fill de apertura no implica que se pudiera capturar el movimiento anterior a ese fill.
2. **Cierre a siguiente apertura de futuros:** depende de la sesión electrónica, pausa diaria, settlement y contrato elegido. Muchos futuros negocian casi todo el día; el término “overnight” puede designar solo la pausa o el tramo fuera de la sesión regular de efectivo.
3. **Close-to-open de barras del broker:** los límites diarios los define el feed, horario de servidor, DST y producto. No equivale necesariamente a cierre/apertura de exchange.
4. **Cierre del viernes a apertura del lunes o post-feriado:** intervalo de varios días calendario, noticias y horarios especiales. No mezclarlo con noche ordinaria.
5. **Gap-fill/reversal tras la apertura:** regla condicional sobre el gap ya observado; es una hipótesis distinta del retorno overnight y debe medir fills después de que el gap sea observable.

Registrar por separado `overnight_return`, `open_to_close_return` y `close_to_close_return`; no llamar “reversión del gap” a un retorno overnight positivo sin especificar una entrada realizable posterior.

## Qué sugiere la evidencia y qué no

- Cooper, Cliff y Gulen (2008), *Return Differences between Trading and Non-Trading Hours: Like Night and Day*, working paper [SSRN](https://doi.org/10.2139/ssrn.1004081), reportan que en su muestra de renta variable de EE. UU. los retornos agregados se concentraban en horas no negociadas; también describen precios de apertura altos que caen durante la primera hora. Es un resultado de muestra/definición histórica y un working paper; no valida gaps de ES/NQ, CFD ni la ejecución tras ver la apertura.
- Kelly y Clark (2011), “Returns in Trading versus Non-Trading Hours: The Difference is Day and Night”, *Journal of Asset Management* 12(2), 132–145, [DOI](https://doi.org/10.1057/jam.2011.2), estudian ETF amplios y distinguen close-to-open y open-to-close. Su abstract reporta retornos ajustados por riesgo diferentes entre tramos; no es evidencia de que una regla direccional condicional al tamaño del gap sea rentable en otros feeds o periodos.
- Liu y Tse (2017), “Overnight Returns of Stock Indexes: Evidence from ETFs and Futures”, *International Review of Economics & Finance*, 48, 440–451, [DOI](https://doi.org/10.1016/j.iref.2017.01.005), usan datos TAQ y futuros y reportan retornos overnight positivos en sus muestras, junto con predictibilidad negativa de overnight para el primer medio-hora y positiva para el último medio-hora. Ese patrón intradía por subventanas no equivale a un fill de apertura ni a un gap-fill genérico.
- Branch y Ma (2012), “Overnight Return, the Invisible Hand Behind Intraday Returns?”, *Journal of Applied Finance* 22(2), 90–100, [registro SSRN](https://ssrn.com/abstract=2294017), reportan relación negativa entre retornos overnight e intradía en acciones. La explicación de market makers es una interpretación propuesta, no una causalidad demostrada ni una regla transferible a futuros/OTC.

Estos trabajos son motivación y evidencia específica de sus muestras, definiciones y costos. No confirman los datos locales ni un edge de apertura, gap continuation o gap-fill.

## Riesgos y controles de falsación

| Riesgo | Cómo puede crear una pauta aparente | Control/falsación exigida |
|---|---|---|
| Definición de close/open | Settlement, última transacción, subasta oficial, primer tick, primera barra o cierre de broker dan gaps diferentes. | Predefinir fuente/venue y reglas de precio; auditar timestamps y comparar con referencia oficial. Registrar por separado settlement y close de sesión. Si el signo depende de una convención elegida tras ver los datos, no pasa. |
| Fill en el precio que define la señal | La señal requiere conocer el opening price, pero se supone ejecutada al mismo precio que la fija. En subasta, orden y precio de apertura se determinan simultáneamente. | Probar ejecución en la primera cotización/intervalo realmente disponible después de observar el gap, con bid/ask, latencia y slippage. El retorno de cierre anterior a apertura es no negociable durante ese tramo; no atribuirlo a la estrategia que entra después. |
| Overnight premium vs reversión de gap | Una prima media positiva de cierre-a-apertura puede coexistir con reversión después de gaps grandes. La media incondicional no determina la respuesta condicional al tamaño/dirección del gap. | Mantener hipótesis separadas: prima overnight incondicional, continuación condicional y reversal condicional. Definir cortes por tamaño antes del análisis y corregir selección múltiple. Si el edge solo aparece al mezclar preguntas, reformular. |
| Overnight cash/ETF frente a futuros | El índice cash no negocia por la noche; ETF, futuro y underlying tienen basis, carry, dividendos, expiración y horarios distintos. | Usar mismo instrumento para señal y fill cuando sea posible; si se contrasta otro, registrar basis, contrato, financiación, dividendos y desfase horario. No tratar el movimiento del índice como fill del futuro. |
| Feed y sesión del broker | Vela de día del broker puede terminar por timezone de servidor; CFD puede pausar o ensanchar spread a distinta hora; historial puede ocultar ticks sin cotización. | Conservar timestamp fuente y timezone, calendario de exchange/broker y offsets históricos; comparar feed primario con fuente oficial. Si solo aparece en velas agregadas o datos rellenados, marcar `NO CONFIRMADO`. |
| DST, festivos y fin de semana | Cambio horario desplaza aperturas; cierres parciales y feriados alargan el gap. Lunes/festivo genera una exposición distinta de la noche regular. | Usar calendario histórico versionado y zona IANA/venue; etiquetar días por duración de cierre y excluir/separar cierres extraordinarios según regla predefinida. No agrupar fines de semana con gaps ordinarios. |
| Contrato continuo y rollover | Ajuste back-adjusted, empalme de series o cambio de contrato puede parecer gap/reversal, especialmente alrededor de vencimientos. | Conservar contratos individuales y fijar roll usando solo información disponible entonces. Atribuir el gap a precio del contrato negociado; comparar con serie continua solo como diagnóstico. |
| Bid-ask bounce y subasta | Open/close transaccional puede estar al bid o ask, y spread/impacto suele ser mayor cerca de apertura. Un midpoint o último precio no representa fill. | Calcular señal/PnL con quotes ejecutables y costos variables por hora/tamaño; analizar trades vs mid como sensibilidad. Si el efecto desaparece neto de costos, descartar como edge ejecutable. |
| Noticias y eventos | Macro, resultados, anuncios corporativos o eventos de fin de semana mueven a la vez gap, volatilidad y reversión. | Registrar calendario de eventos disponible en ese momento; definir de antemano si son parte del mecanismo o controles. No excluir retrospectivamente las pérdidas de noticias. |
| Sobreajuste y selección | Probar muchos umbrales de gap, horarios, días, filtros de volatilidad, stops, activos y ventanas selecciona por azar un “gap-fill”. | Congelar predicción, métrica primaria y universo de ensayos; corregir múltiples pruebas y conservar holdout cronológico. Mantener resultados fallidos. Si solo sobrevive el ganador no corregido, no pasa. |
| Dependencia y regímenes | Gaps agrupados en crisis o fines de semana no son observaciones iid; unas pocas aperturas dominan el promedio y las pérdidas de cola pueden ser grandes. | Inferencia por bloques/eventos, reportar episodios independientes, distribución condicional y peores gaps; evaluar ventanas predefinidas. Si la conclusión depende de pocos eventos, dejar pendiente o descartar según potencia/riesgo. |

## Evidencia que falsaría o dejaría pendiente una ficha

Descartar o reformular si: (1) no existe definición reproducible de cierre, apertura y sesión; (2) para operar se necesita un fill anterior al momento en que se conoce el gap; (3) el resultado desaparece al usar bid/ask, costos de apertura y una latencia realista; (4) la relación condicional se confunde con la media overnight incondicional; (5) una serie continua o timezone crea el salto; (6) el signo no persiste en holdout temporal o solo aparece tras probar numerosos umbrales; o (7) cola/riesgo/regímenes no caben en los límites definidos. Si faltan quotes, calendario o cobertura, mantener `data_pending`, no declararlo edge ausente ni presente.

Aplicar los gates comunes de [`../../GATES.md`](../../GATES.md). No se ejecutaron pruebas para ES, NQ, WTIFS, USDJPY, BTCUSD, BTCJPY u otros instrumentos del repositorio.
