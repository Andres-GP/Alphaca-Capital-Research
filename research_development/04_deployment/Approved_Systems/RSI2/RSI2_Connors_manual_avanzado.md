# RSI 2 · Connors

**ESTRATEGIA #1 · MANUAL AVANZADO**

Cómo la construimos y cómo la validamos. Ocho pruebas, contadas para que las entiendas y las puedas repetir.

Etiquetas: QQQ · 1999–2026 | 285 operaciones | 5 bps por lado | Motor: Sentinel · Método: TIS | Un solo motor para todo

## Las ocho pruebas de un vistazo

| Prueba | Pregunta | Estado |
|---|---|---|
| AED del Nasdaq | ¿revierte de verdad? | OK |
| Fase 1 · Backtest | dentro y fuera de muestra | OK |
| Fase 2 · Walk-forward | año a año, reglas fijas | OK |
| Fase 3 · Zonas robustas | mapa 2D + superficie de robustez | OK |
| Fase 4 · Monte Carlo | barajar las operaciones | OK |
| Fase 5 · Estrés | tratarla mal a propósito | OK |
| Test del mono | ¿le ganamos al azar? | OK |
| Desgaste del edge | ¿sigue viva? | OK |

---

## 2 · EL MÉTODO TIS

### Una estrategia es una línea de producción

Entra una premisa por un lado. Sale una estrategia validada por el otro. Ocho estaciones, siempre en el mismo orden: cada una te protege del error de la siguiente. Así pasó el RSI 2 por cada una.

#### 01 · CORE LOGIC — Hipótesis

Empieza con una hipótesis y su lógica. Antes de tocar un dato, tienes que saber por qué debería funcionar; si no sabes por qué gana, no sabrás cuándo dejará de hacerlo.

**En el RSI 2:** Sobreventa de dos días dentro de una tendencia alcista → rebote. Está en la ficha.

#### 02 · EDGE ESTRUCTURAL — AED · validación

Explora los datos antes de asumir nada: ¿rápido o lento? ¿revierte o continúa? ¿cuándo es volátil? Construir sin AED es asumir.

**En el RSI 2:** ¿Revierte el Nasdaq tras caídas rápidas? Sí: 0,4 % de media a 3 días tras la señal, frente a 0,1 % un día cualquiera. Abajo, con gráficos.

#### 03 · EL CÓDIGO — Reglas

Escribe reglas fijas, sin ajustar por activo. Que quepan en una página. Cada página de más es otra forma de engañarte: menos es más.

**En el RSI 2:** Cuatro reglas fijas, sin ajustar por activo. El mismo código en el motor y en el robot.

#### 04 · IS / OOS — Backtesting

Separa construcción y validación, y valida en lo desconocido con costes reales. Después pregúntate si ganas al azar (test del mono).

**En el RSI 2:** 27 años partidos en 70/30, 5 bps por lado. Fase 1, Fase 2 (walk-forward) y test del mono, abajo.

#### 05 · + ROBUSTEZ — Optimización

No busques el número perfecto: mueve los parámetros alrededor de los elegidos y comprueba que el vecindario entero gana. Quita lo que no aporta.

**En el RSI 2:** No se optimiza. Mapa 2D, superficie de robustez giratoria y 180 combinaciones en la Fase 3, abajo.

#### 06 · GESTIÓN DEL RIESGO — Sizing / RM

Decide con honestidad: acepta lo que el sistema hace y lo que no. Un número más grande no es mejor si sube el riesgo. Elige por perfil.

**En el RSI 2:** Monte Carlo, estrés y varios niveles de tamaño (1 %, 2 %, 100 %, 1:2). Fases 4 y 5, abajo; los niveles, en la ficha.

#### 07 · PRIMERAS ENTRADAS LIVE — Incubación

Antes de confiar, míralo operar en real con poco. Las primeras operaciones reales son la última prueba, no la primera.

**En el RSI 2:** El robot opera en cuenta real desde junio de 2026. Las primeras operaciones se publicarán cuando haya muestra.

#### 08 · PRODUCCIÓN — Deploy live

El robot tiene que hacer exactamente lo que dice el papel, con cortacircuitos por si algo falla. Nada se cambia en caliente.

**En el RSI 2:** EA de MetaTrader 5 sobre NDX, servidor 24/7, cortacircuitos −3 % / −8 % y alertas. Reconciliado con el Strategy Tester: 40/40 operaciones coinciden.

<!--blue-->
> Cada estación lleva su principio (lo que vale para cualquier sistema) y lo que se hizo en el RSI 2. Las estaciones 02, 04, 05 y 06 se pueden medir: abajo están las pruebas, y todas siguen el mismo guion. Los criterios se escriben antes de correr nada y no se tocan según el resultado.

---

## ESTACIÓN 02 · AED — ¿De verdad revierte el Nasdaq 100?

**Estado: SUPERADA**

#### La pregunta

Antes de construir nada: ¿qué hace el Nasdaq en los días siguientes a una caída brusca? ¿Y cuánto pesa la tendencia de fondo?

#### Cómo lo hacemos

1. Tomamos todos los días de 27 años y miramos el retorno a 1, 2, 3, 5 y 10 días.
2. Separamos cuatro grupos: cualquier día, días sobre la SMA 200, días con RSI(2) < 15 sobre la SMA 200 (nuestra señal) y la misma señal por debajo.
3. Medimos además si el Nasdaq revierte (autocorrelación, rachas de caídas) y cómo cambia su volatilidad.

#### El criterio (fijado antes)

No hay criterio numérico: es exploración. Si la señal no destacara sobre un día cualquiera, la hipótesis moriría aquí.

<!--amber-->
> Es como mirar el historial de un jugador antes de ficharlo: no te fías del talento que te cuentan, miras qué ha hecho en cada situación.

- **+0,38 %** — retorno medio a 3 días tras la señal · sobre la SMA 200
- **+0,14 %** — retorno medio a 3 días cualesquiera · todos los días
- **59 %** — rebotes: las señales suben a 3 días
- **74 %** — del tiempo sobre la SMA 200 · solo ahí operamos
- **22** — señales al año de media, con tendencia a favor

### Qué hace el Nasdaq después de una sobreventa extrema

Gráfico (barras): barra verde > gris: el momento de entrada aporta · roja alta pero menos fiable: la tendencia compra consistencia.

Retorno medio del Nasdaq 100 (QQQ) a 1, 2, 3, 5 y 10 días según el punto de partida. Verde: nuestra señal (RSI(2) < 15 sobre la SMA 200). Rojo: la misma sobreventa pero por debajo de la SMA 200.

| Punto de partida | Días | 1 D | 2 D | 3 D | 5 D | 10 D |
|---|---|---|---|---|---|---|
| Todos los días | 6731 | +0,05 % · 54 % ↑ | +0,09 % · 56 % ↑ | +0,14 % · 57 % ↑ | +0,23 % · 57 % ↑ | +0,45 % · 59 % ↑ |
| Días sobre la SMA 200 | 4979 | +0,05 % · 56 % ↑ | +0,11 % · 57 % ↑ | +0,16 % · 58 % ↑ | +0,27 % · 59 % ↑ | +0,54 % · 61 % ↑ |
| RSI(2) < 15 sobre la SMA 200 (nuestra señal) | 609 | +0,20 % · 59 % ↑ | +0,27 % · 57 % ↑ | +0,38 % · 59 % ↑ | +0,59 % · 62 % ↑ | +0,97 % · 63 % ↑ |
| RSI(2) < 15 bajo la SMA 200 | 428 | +0,40 % · 55 % ↑ | +0,48 % · 54 % ↑ | +0,53 % · 52 % ↑ | +0,65 % · 56 % ↑ | +0,64 % · 51 % ↑ |

<!--blue-->
> **Lo que dice:** Un día cualquiera el Nasdaq sube de media 0,14 % en tres días. Tras una sobreventa extrema con la tendencia a favor sube 0,38 %, y el 59 % de las veces. La misma sobreventa por debajo de la SMA 200 sube de media algo parecido (0,53 %) pero solo el 52 % de las veces y con sustos mucho mayores: sin tendencia, el rebote es una moneda al aire. El filtro no compra rentabilidad media, compra consistencia.

### ¿Tiende o revierte? Autocorrelación de los retornos diarios

Gráfico izquierdo: autocorrelación de los retornos diarios (barra roja a 1 día = lo que hoy cae tiende a subir mañana, reversión). Gráfico derecho: ¿cuánto rebota tras varias caídas seguidas? Retorno medio en los 3 días siguientes: cuanto más cae seguido, más rebota.

Izquierda: autocorrelación de los retornos diarios (negativa = lo que cae hoy tiende a subir mañana). Derecha: retorno medio a 3 días después de 1, 2, 3 y 4 días seguidos de caída, con el precio sobre la SMA 200.

<!--blue-->
> **Reversión, no continuación:** la autocorrelación a un día es −5,8 %. Después de 3 días seguidos de caída sobre la SMA 200, el rebote medio a 3 días es 0,37 %. El RSI de 2 períodos es solo una forma compacta de medir exactamente eso.

### Régimen de tendencia y volatilidad

Gráfico superior: régimen de tendencia: el 74 % del tiempo el precio está sobre la SMA 200. En rojo, el 26 % restante: por debajo de la media la estrategia no opera, y ahí están 2000–2002, 2008 y 2022.

Gráfico inferior: volatilidad diaria (ATR como % del precio): se multiplica por 4 en las crisis. Por eso el tamaño de posición se calcula con el ATR y no con un porcentaje fijo.

Arriba: cierre de QQQ y SMA 200; en rojo, los tramos por debajo, donde la estrategia no opera. Abajo: el ATR(14) como porcentaje del precio, la volatilidad diaria que usa el robot para dimensionar.

### Colas gordas: por qué el tamaño se decide con el ATR

Gráfico: los días extremos ocurren mucho más de lo que dice la campana normal. Por eso el tamaño mira la volatilidad reciente y por eso no hay apalancamiento por defecto. Anotaciones del gráfico: días con caída ≥ 5 %: 57 reales frente a 18 que predecía la campana. Un día del −12,0 % ocurriría, según la campana, una vez cada 3.705 millones de años. Ocurrió.

Cuántos días hubo con cada retorno (escala logarítmica para que se vean los extremos) frente a lo que predeciría una campana normal con la misma media y desviación. Las colas reales están muy por encima de la curva azul: los días extremos ocurren mucho más de lo que dice la teoría.

| Retornos diarios de QQQ | Valor |
|---|---|
| Media diaria | +0,048 % |
| Desviación típica diaria | 1,68 % |
| Días positivos | 54 % |
| Mejor / peor día | +16,8 % / −12,0 % |
| Asimetría · curtosis | 0,24 · 7,53 (una campana normal tiene curtosis 0) |
| ATR(14) / precio · media (mín – máx) | 2,05 % (0,58 % – 8,76 %) |

<!--amber-->
> **Qué es una cola gorda y por qué importa:** si los retornos diarios siguieran una campana normal, un día del −12,0 % sería prácticamente imposible. Ocurrió, y no una vez. La curtosis de 7,53 (una campana tiene 0) mide exactamente eso: cuánto más gordas son las colas que las de la teoría. Consecuencia práctica: la volatilidad cambia de golpe y por eso el robot calcula el tamaño de cada operación con el ATR de los últimos 14 días, no con un porcentaje fijo. Cuando el mercado se pone nervioso, la posición se encoge sola antes de que llegue el susto.

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> El Nasdaq revierte a corto plazo y lo hace con consistencia solo cuando la tendencia de fondo es alcista. La hipótesis no es una opinión: está en los datos antes de escribir una sola regla. Si algún día estos números cambian, la estrategia deja de tener sentido y lo veremos aquí.

---

## FASE 1 · Backtest dentro y fuera de muestra

**Estado: SUPERADA**

#### La pregunta

Con las reglas ya escritas, ¿gana dinero en datos que nunca vio, y no depende de un golpe de suerte?

#### Cómo lo hacemos

1. Partimos la historia en dos por número de velas: el 70 % para construir y el 30 % final, guardado sin mirar.
2. Corremos las reglas fijas con 5 bps por lado de coste en cada operación.
3. Miramos solo el tramo guardado: si la estrategia se hubiera ajustado al pasado, ahí se desmoronaría.

#### El criterio (fijado antes)

Fuera de muestra: Profit Factor ≥ 1,3 · al menos 30 operaciones · drawdown menor del 20 % · Profit Factor sin la mejor operación > 1.

<!--amber-->
> Es un examen con las preguntas que no viste al estudiar. Aprobar el examen que ya conocías no vale nada.

| | Construcción (IS) | Validación (OOS) | Todo |
|---|---|---|---|
| Periodo | 21 dic 1999 → 12 sep 2018 | 13 sep 2018 → 28 sep 2026 | 27 años |
| Operaciones | 192 | 93 | 285 |
| Profit Factor | 1,73 | 2,66 | 1,99 |
| Profit Factor sin la mejor operación | 1,64 | 2,51 | 1,92 |
| CAGR (100 % capital) | 4,5 % | 9,1 % | 5,9 % |
| Drawdown máx. operación a operación | −13,8 % | −8,1 % | −13,8 % |
| Drawdown máx. día a día | −27,2 % | −11,9 % | −27,2 % |
| Aciertos | 66 % | 80 % | 71 % |
| Retorno medio por operación | 0,46 % | 0,78 % | 0,57 % |
| Mejor / peor operación | 10,5 % / −13,8 % | 6,7 % / −8,1 % | 10,5 % / −13,8 % |
| Tiempo en mercado | 26 % | 26 % | 26 % |

- ✓ PF fuera de muestra ≥ 1,3 → 2,66
- ✓ ≥ 30 operaciones fuera de muestra → 93
- ✓ Drawdown fuera de muestra < 20 % → −8,1 %
- ✓ PF sin la mejor operación > 1 → 2,51

<!--amber-->
> **Dos cifras de drawdown, y no se contradicen.** "Operación a operación" solo actualiza el capital cuando se cierra cada operación: es el criterio de la prueba. "Día a día" valora la posición abierta cada noche: es la cifra que sentirías en la cuenta y la que usamos en la ficha. La segunda siempre es igual o peor.

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> La estrategia gana en ocho años que no vio, con costes, y no depende de una sola operación afortunada. Que la validación salga mejor que la construcción no es mérito nuestro: 2019–2026 ha sido un mercado muy favorable a comprar caídas en el Nasdaq. Lo que importa es que no se degrada. Los años malos existen y están en la sección 3, mes a mes.

---

## FASE 2 · Walk-forward: un examen sorpresa cada año

**Estado: SUPERADA**

#### La pregunta

¿Lo que rinde en el pasado reciente se parece a lo que rinde después? ¿O vive de dos o tres años buenos?

#### Cómo lo hacemos

1. Para cada año natural, tomamos los tres años anteriores como referencia (construcción) y ese año como examen (validación).
2. Rodamos la ventana desde 2003 hasta el último año completo, siempre con las mismas reglas.
3. Comparamos el retorno del año examinado con la media de los tres previos, y contamos cuántos años salen positivos.

#### El criterio (fijado antes)

Eficiencia (retorno medio validado ÷ retorno medio previo) ≥ 0,50 · al menos el 60 % de los años positivos · ningún año completo con drawdown ≥ 20 %.

<!--amber-->
> Un profesor que cada año pone un examen nuevo y compara con los tres cursos anteriores. Si el alumno solo aprobara el examen que ya sabía, aquí se nota.

Gráfico: Walk-forward con reglas fijas — cada año validado contra los 3 anteriores. Leyenda: barras = año validado (OOS, reglas fijas); línea = media anual de los 3 años previos (IS).

Barras: retorno de cada año validado con las reglas fijas. Línea: media anual de los 3 años previos. Verde/rojo: año positivo/negativo.

- ✓ Eficiencia ≥ 0,50 → 1,16
- ✓ ≥ 60 % de años positivos → 65 % (15 de 23)
- ✓ Ningún año con drawdown ≥ 20 % → peor: −8,1 %

| Año | Operaciones | Retorno del año | Profit Factor | Drawdown |
|---|---|---|---|---|
| 2003 | 12 | +29,5 % | 263,51 | −0,1 % |
| 2004 | 9 | −2,2 % | 0,77 | −3,9 % |
| 2005 | 15 | −0,1 % | 0,99 | −3,6 % |
| 2006 | 10 | +3,8 % | 1,59 | −5,3 % |
| 2007 | 14 | +22,1 % | 6,46 | −2,8 % |
| 2008 | 2 | −0,5 % | 0,00 | −0,5 % |
| 2009 | 10 | +3,4 % | 1,48 | −5,0 % |
| 2010 | 9 | −4,6 % | 0,51 | −7,8 % |
| 2011 | 14 | −0,0 % | 1,03 | −7,1 % |
| 2012 | 12 | +8,3 % | 2,12 | −4,7 % |
| 2013 | 15 | +17,1 % | 18,80 | −0,9 % |
| 2014 | 14 | +4,9 % | 1,86 | −3,9 % |
| 2015 | 14 | +7,6 % | 3,06 | −1,9 % |
| 2016 | 9 | −5,0 % | 0,53 | −3,8 % |
| 2017 | 14 | +10,5 % | 6,33 | −1,3 % |
| 2018 | 9 | −6,4 % | 0,58 | −7,3 % |
| 2019 | 10 | +4,2 % | 1,68 | −3,4 % |
| 2020 | 9 | +20,2 % | 9,42 | −2,2 % |
| 2021 | 13 | +6,6 % | 2,11 | −4,9 % |
| 2022 | 2 | −0,7 % | 0,68 | −2,2 % |
| 2023 | 15 | +18,1 % | 5,79 | −2,7 % |
| 2024 | 18 | +14,9 % | 2,44 | −8,1 % |
| 2025 | 10 | +5,4 % | 1,87 | −6,6 % |

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> Como las reglas no se optimizan, este walk-forward es honesto por construcción: no hay nada que reajustar cada año. Una eficiencia de 1,16 dice que los años examinados rinden, de media, más que los tres previos que los anticipaban. Los años rojos existen (8 de 23) y son pequeños: ninguno pasó del −6,4 %.

---

## FASE 3 · Zonas robustas: ¿depende de un número exacto?

**Estado: SUPERADA**

#### La pregunta

¿El resultado depende de haber acertado un número concreto (15, 200) o aguanta todo el vecindario? Es la prueba que separa un sistema real de una curva bonita ajustada al pasado.

#### Cómo lo hacemos

1. Mapa 2D: movemos el umbral del RSI (5 a 30) y el periodo de la media (100 a 300), con salida y costes fijos. 30 celdas, solo en construcción.
2. Superficie de robustez: la misma rejilla en tres dimensiones (RSI × SMA × Profit Factor), giratoria, para ver si la regla está en una meseta; y las 30 combinaciones ordenadas con y sin el doble de costes.
3. Después repetimos las 30 celdas para tres salidas distintas y dos niveles de coste: 180 combinaciones.

#### El criterio (fijado antes)

Meseta 3×3 con PF ≥ 1,3 y más de 30 operaciones por celda · ningún vecino cae más del 30 % respecto al centro · como referencia, la mayoría de las 180 combinaciones superan PF 1,3.

<!--amber-->
> Un buen restaurante no depende de que el cocinero titular esté ese día. Si con cualquier cocinero de la casa la comida sigue siendo buena, el mérito es de la cocina. Y si solo ganas apostando al 17 exacto, era suerte.

### El mapa 2D: umbral del RSI × periodo de la media

Gráfico: Zonas robustas — Profit Factor en construcción (IS) al mover los dos parámetros. Cada celda muestra el PF y N (número de operaciones). La configuración que opera es RSI < 15 con SMA 200 (PF 1,73 · N=192).

| | SMA 100 | SMA 150 | SMA 200 | SMA 250 | SMA 300 |
|---|---|---|---|---|---|
| RSI < 5 | 2,43 (N=58) | 2,61 (N=71) | 2,27 (N=76) | 2,51 (N=82) | 3,88 (N=83) |
| RSI < 10 | 1,89 (N=120) | 1,80 (N=138) | 1,84 (N=142) | 2,11 (N=148) | 2,53 (N=148) |
| RSI < 15 | 1,56 (N=176) | 1,70 (N=192) | **1,73 (N=192)** | 1,81 (N=197) | 1,90 (N=199) |
| RSI < 20 | 1,48 (N=216) | 1,43 (N=232) | 1,57 (N=234) | 1,66 (N=240) | 1,75 (N=237) |
| RSI < 25 | 1,38 (N=246) | 1,22 (N=263) | 1,40 (N=260) | 1,44 (N=263) | 1,50 (N=261) |
| RSI < 30 | 1,26 (N=270) | 1,18 (N=293) | 1,30 (N=283) | 1,34 (N=290) | 1,42 (N=287) |

Profit Factor en construcción para las 30 combinaciones, con salida y costes fijos. El recuadro (aquí en negrita) es la configuración que opera (RSI < 15, SMA 200). N es el número de operaciones de cada celda. Cuanto más verde, mejor; lo que buscamos es que el recuadro esté rodeado de verde, no que sea la celda más oscura.

- ✓ Meseta 3×3: las 9 celdas alrededor de la elegida superan PF 1,3 con más de 30 operaciones
- ✓ Anti-acantilado: ningún vecino cae más del 30 % respecto al centro → peor caída 17 %
- ✓ 90 % de las 30 celdas superan PF 1,3

<!--blue-->
> La mejor celda del mapa es RSI < 5 con SMA 300 (PF 3,88). No la elegimos: tiene menos operaciones y elegir el pico del mapa es exactamente el error que esta prueba quiere evitar. Nos quedamos en el centro de la meseta.

### La superficie de robustez: gírala tú

La misma rejilla vista como una superficie, como en el optimizador de MultiCharts: altura y color son el Profit Factor, y el punto negro es la configuración que opera. Lo que buscamos es que esté en una meseta, con vecinos parecidos, no en un pico aislado. Con los botones ves las seis combinaciones de salida y coste; al pasar el cursor por cada celda ves también su drawdown.

Botones del gráfico interactivo: Dos velas verdes · 5 bps | Dos velas verdes · 10 bps | Cierre > MA(5) · 5 bps | Cierre > MA(5) · 10 bps | RSI(2) > 70 · 5 bps | RSI(2) > 70 · 10 bps.

Ejes del gráfico 3D: umbral del RSI(2) (< 5 a < 30), periodo de la SMA (100 a 300) y Profit Factor (IS). Etiqueta: «la que opera».

Gírala con el ratón, haz zoom con la rueda y pasa el cursor por cada celda. Altura y color son el Profit Factor en construcción: verde alto, rojo cerca de 1. Lo que buscamos es que el punto negro (la configuración que opera) esté en una zona verde y llana, rodeado de vecinos parecidos, no en un pico aislado. Los botones cambian la salida y el coste: la forma de la superficie apenas cambia, y eso es lo que buscamos.

### Las 30 combinaciones, de mejor a peor, con y sin el doble de coste

Gráfico: las 30 combinaciones ordenadas de mejor a peor: barras con 5 bps por lado · línea con el doble de costes. Leyenda: PF con 5 bps por lado; PF con 10 bps por lado; la que opera. Línea de referencia: criterio 1,3.

Cada combinación es una barra (Profit Factor con 5 bps por lado) y la línea naranja es la misma combinación con 10 bps; la barra negra es la que opera. Todas siguen por encima del criterio de 1,3 aun con el doble de coste.

### Tres salidas y dos costes: 180 combinaciones

Si la estrategia dependiera de *nuestra* salida o de costes bajos, aquí se vería.

Gráfico: Los seis mapas: Profit Factor en construcción para 180 combinaciones (tres salidas × dos costes). Todos con la misma escala de color (1,0 a 5,0). Filas: RSI < 5 a RSI < 30. Columnas: SMA 100, 150, 200, 250, 300.

#### Salida: Dos velas verdes · coste 5 bps por lado

| | SMA 100 | SMA 150 | SMA 200 | SMA 250 | SMA 300 |
|---|---|---|---|---|---|
| RSI < 5 | 2,43 | 2,61 | 2,27 | 2,51 | 3,88 |
| RSI < 10 | 1,89 | 1,80 | 1,84 | 2,11 | 2,53 |
| RSI < 15 | 1,56 | 1,70 | **1,73** | 1,81 | 1,90 |
| RSI < 20 | 1,48 | 1,43 | 1,57 | 1,66 | 1,75 |
| RSI < 25 | 1,38 | 1,22 | 1,40 | 1,44 | 1,50 |
| RSI < 30 | 1,26 | 1,18 | 1,30 | 1,34 | 1,42 |

#### Salida: Dos velas verdes · coste 10 bps por lado

| | SMA 100 | SMA 150 | SMA 200 | SMA 250 | SMA 300 |
|---|---|---|---|---|---|
| RSI < 5 | 2,20 | 2,36 | 2,05 | 2,29 | 3,51 |
| RSI < 10 | 1,71 | 1,62 | 1,65 | 1,90 | 2,26 |
| RSI < 15 | 1,40 | 1,52 | 1,54 | 1,61 | 1,68 |
| RSI < 20 | 1,32 | 1,27 | 1,40 | 1,48 | 1,54 |
| RSI < 25 | 1,23 | 1,09 | 1,25 | 1,20 | 1,33 |
| RSI < 30 | 1,13 | 1,06 | 1,16 | 1,20 | 1,26 |

#### Salida: Cierre > MA(5) · coste 5 bps por lado

| | SMA 100 | SMA 150 | SMA 200 | SMA 250 | SMA 300 |
|---|---|---|---|---|---|
| RSI < 5 | 4,10 | 4,19 | 2,39 | 2,79 | 3,25 |
| RSI < 10 | 2,37 | 2,11 | 2,02 | 2,17 | 2,24 |
| RSI < 15 | 1,68 | 1,76 | 1,75 | 1,85 | 1,80 |
| RSI < 20 | 1,47 | 1,43 | 1,50 | 1,65 | 1,53 |
| RSI < 25 | 1,43 | 1,30 | 1,41 | 1,53 | 1,52 |
| RSI < 30 | 1,33 | 1,20 | 1,25 | 1,36 | 1,39 |

#### Salida: Cierre > MA(5) · coste 10 bps por lado

| | SMA 100 | SMA 150 | SMA 200 | SMA 250 | SMA 300 |
|---|---|---|---|---|---|
| RSI < 5 | 3,38 | 3,56 | 2,08 | 2,43 | 2,85 |
| RSI < 10 | 2,04 | 1,83 | 1,75 | 1,88 | 1,94 |
| RSI < 15 | 1,47 | 1,54 | 1,52 | 1,59 | 1,55 |
| RSI < 20 | 1,27 | 1,24 | 1,30 | 1,43 | 1,33 |
| RSI < 25 | 1,24 | 1,12 | 1,22 | 1,32 | 1,31 |
| RSI < 30 | 1,16 | 1,04 | 1,08 | 1,18 | 1,20 |

#### Salida: RSI(2) > 70 · coste 5 bps por lado

| | SMA 100 | SMA 150 | SMA 200 | SMA 250 | SMA 300 |
|---|---|---|---|---|---|
| RSI < 5 | 5,15 | 4,36 | 2,93 | 3,24 | 3,48 |
| RSI < 10 | 2,94 | 2,48 | 2,35 | 2,53 | 2,60 |
| RSI < 15 | 1,97 | 2,19 | 2,26 | 2,26 | 2,18 |
| RSI < 20 | 1,61 | 1,66 | 1,79 | 1,89 | 1,77 |
| RSI < 25 | 1,51 | 1,43 | 1,53 | 1,63 | 1,61 |
| RSI < 30 | 1,34 | 1,30 | 1,31 | 1,39 | 1,43 |

#### Salida: RSI(2) > 70 · coste 10 bps por lado

| | SMA 100 | SMA 150 | SMA 200 | SMA 250 | SMA 300 |
|---|---|---|---|---|---|
| RSI < 5 | 4,46 | 3,90 | 2,64 | 2,94 | 3,17 |
| RSI < 10 | 2,61 | 2,21 | 2,11 | 2,27 | 2,33 |
| RSI < 15 | 1,75 | 1,94 | 2,00 | 2,00 | 1,93 |
| RSI < 20 | 1,42 | 1,46 | 1,58 | 1,66 | 1,56 |
| RSI < 25 | 1,34 | 1,26 | 1,34 | 1,43 | 1,41 |
| RSI < 30 | 1,18 | 1,15 | 1,15 | 1,25 | 1,23 |

Seis mapas con la misma escala de color. Arriba, costes de 5 bps por lado; abajo, 10 bps. Columnas: salida a dos velas verdes (la nuestra), salida al cruzar la media de 5 (la del libro) y salida cuando el RSI(2) supera 70. El recuadro es la configuración que opera.

- **180** — combinaciones probadas · RSI × SMA × salida × coste
- **82 %** — superan PF 1,3 · el criterio de la Fase 1
- **100 %** — son rentables · Profit Factor por encima de 1
- **1,04 · 1,61 · 5,15** — mínimo · mediana · máximo Profit Factor

### ¿Cuántas combinaciones ganan? 82 % superan PF 1,3 · 100 % son rentables

Gráfico (histograma): eje X = Profit Factor (IS), de 1 a 5; eje Y = combinaciones. Líneas: criterio 1,3 (roja) y configuración que opera · 1,73 (negra).

Distribución del Profit Factor de las 180 combinaciones. La línea negra es la configuración que opera; la roja, el criterio mínimo.

| Dimensión | Valor | PF medio (IS) |
|---|---|---|
| Salida | Dos velas verdes | 1,70 |
| Salida | Cierre > MA(5) | 1,79 |
| Salida | RSI(2) > 70 | 2,08 |
| Coste por lado | 5 bps | 1,98 |
| Coste por lado | 10 bps | 1,74 |

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> La configuración que opera está en el percentil 57 de las 180 combinaciones: ni la mejor ni la peor, en el centro de una superficie suave donde casi todo gana. Doblar los costes baja el PF medio de 1,98 a 1,74 y no cambia la conclusión. Las tres salidas funcionan; la nuestra no es un número mágico. Esto es lo que permite decir que el edge es del activo, no de los parámetros: mañana, con parámetros ligeramente distintos, seguirá funcionando.

---

## FASE 4 · Monte Carlo: barajar las operaciones

**Estado: SUPERADA**

#### La pregunta

Las 285 operaciones ocurrieron en un orden concreto. ¿Y si hubieran venido en otro? ¿Cuánto del resultado es el orden y cuánto es la estrategia?

#### Cómo lo hacemos

1. Reordenamos las operaciones reales 10.000 veces al azar, en bloques de 5 para conservar las rachas.
2. Dibujamos los caminos posibles y, para cada uno, calculamos el retorno total y la peor caída.
3. Miramos el 5 % de escenarios más desfavorables y el peor de todos: ahí es donde se esconde el riesgo real.

#### El criterio (fijado antes)

Evaluado con el tamaño que opera el robot (1 % de riesgo por ATR): retorno total del 5 % peor de escenarios > 0 · drawdown del 5 % peor de escenarios < 25 % · probabilidad de perder la mitad del capital < 5 %. El 100 % del capital se muestra como referencia.

<!--amber-->
> Barajar las cartas de una partida ya jugada: las cartas son las mismas, pero el orden cambia cuánto sufres antes de ganar.

Gráfico: 10.000 reordenaciones de las 285 operaciones reales · 400 dibujadas · bandas: 5–95 % y 25–75 % de todas. Leyenda: un camino posible; mediana de todos; el camino real; el camino con el peor drawdown. Etiquetas: real · 4,7×; mediana · 4,7×; peor drawdown · −41 %. Gráficos inferiores: retorno total de cada camino y drawdown máximo de cada camino.

Arriba: 10.000 caminos posibles con las mismas operaciones en distinto orden (400 dibujados en gris, bandas de todos). El camino real en negro, la mediana en verde y en rojo el camino con el peor drawdown de los 10.000. Abajo: retorno total y drawdown máximo de cada camino, con el 5 % peor y el peor absoluto marcados.

- **−15,9 %** — drawdown mediano de los caminos
- **−25,2 %** — drawdown del 5 % peor · criterio: mejor que −25 %
- **−41,1 %** — el peor de todos · 1 camino entre 10.000
- **+367 %** — retorno mediano de los caminos
- **+15 %** — el peor retorno, aun así positivo

#### Criterio · con el tamaño del robot (1 % de riesgo por ATR)

- ✓ Retorno del 5 % peor de escenarios > 0 → +40 %
- ✓ Drawdown del 5 % peor de escenarios < 25 % → −8,7 %
- ✓ Probabilidad de perder la mitad del capital < 5 % → 0,0 %

#### Referencia · con el 100 % del capital

- ✓ Retorno del 5 % peor de escenarios > 0 → +154 %
- ✗ Drawdown del 5 % peor de escenarios < 25 % → −25,2 % (el 5,4 % de escenarios lo supera)
- ✓ Probabilidad de perder la mitad del capital < 5 % → 0,0 %

| | 100 % capital | 1 % de riesgo (ATR) |
|---|---|---|
| Retorno total · p5 / mediana / p95 | 154 % / 367 % / 757 % | 40 % / 70 % / 106 % |
| Drawdown máximo · p5 / mediana / p95 | −25,2 % / −15,9 % / −10,8 % | −8,7 % / −5,2 % / −3,4 % |
| Escenarios con drawdown > 25 % | 5,4 % | 0,0 % |
| Probabilidad de ruina (−50 %) | 0,0 % | 0,0 % |

<!--amber-->
> **Lectura honesta:** con el 100 % del capital, uno de cada 18 escenarios habría pasado por una caída mayor del 25 %, y el 5 % peor queda en −25,2 %: justo en el límite. Por eso el criterio se evalúa con el tamaño que de verdad va a mercado, el del robot, donde el riesgo queda muy lejos del límite. Si vas con todo el capital, esta es la cifra que tienes que aceptar antes.

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> El drawdown que viste en el backtest (−27,2 %) fue uno de los posibles. La mediana de los 10.000 caminos es −15,9 %, el 5 % peor llega a −25,2 % y el peor de todos a −41,1 %: eso es lo que tienes que estar dispuesto a aguantar si vas con todo el capital. Fíjate en que ni siquiera el peor camino termina en pérdidas (+15 %): el orden cambia cuánto sufres, no si ganas. No es una comparación contra el azar ni una predicción; es una medida de cuánto puede doler el camino.

---

## FASE 5 · Estrés: tratarla mal a propósito

**Estado: SUPERADA**

#### La pregunta

¿Sigue ganando si los costes se disparan, si le quitamos sus mejores años, o en los peores mercados de la historia reciente?

#### Cómo lo hacemos

1. Doblamos los costes (10 bps por lado) en el periodo de validación.
2. Quitamos los dos mejores años de validación y miramos qué queda.
3. La corremos en 2000–2002, 2008 y 2022, los tres mercados bajistas del periodo.

#### El criterio (fijado antes)

Profit Factor ≥ 1,1 con costes dobles y sin los dos mejores años. Los regímenes bajistas se muestran; si hay menos de 30 operaciones, no se evalúan.

<!--amber-->
> Antes de comprar un coche usado lo llevas a un mecánico que busca fallos a propósito. Si sale bien de ahí, te fías.

| Escenario | Operaciones | Profit Factor | Retorno | Veredicto |
|---|---|---|---|---|
| Costes ×2 (10 bps por lado) · validación | 93 | 2,39 | 83,8 % | Supera |
| Sin los dos mejores años (2020, 2023) · validación | 69 | 1,97 | 42,0 % | Supera |
| Estallido puntocom · 2000–2002 | 8 | 1,26 | 2,7 % | Muestra insuficiente |
| Crisis financiera · 2008 | 2 | 0,00 | −0,5 % | Muestra insuficiente |
| Mercado bajista · 2022 | 2 | 0,68 | −0,7 % | Muestra insuficiente |

- ✓ Con el doble de costes → PF 2,39
- ✓ Sin los dos mejores años → PF 1,97

<!--blue-->
> Los años bajistas se pasan casi enteros sin operar: con el precio por debajo de la media de 200 no hay señales. En 2008 y 2022 hubo dos operaciones en cada uno, perdedoras y pequeñas. No es un fallo del sistema, es su diseño: el filtro hace su trabajo y el coste es no ganar nada en esos años. Con dos operaciones no se puede evaluar un Profit Factor, así que lo dejamos como "muestra insuficiente" en vez de disfrazarlo.

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> Con el doble de costes el Profit Factor baja de 2,66 a 2,39: el edge no vive de una ejecución perfecta. Sin sus dos mejores años sigue en 1,97: no depende de un par de rachas. Y en los mercados bajistas hace lo que promete: apartarse. Lo que no hace es ganar en ellos, y eso hay que saberlo antes de operarla.

---

## PRUEBA EXTRA · El test del mono: ¿le ganamos al azar?

**Estado: SUPERADA**

#### La pregunta

En un mercado que sube, entrar en cualquier momento gana algo. ¿Aporta algo el momento exacto de entrada, o es el filtro de tendencia el que hace todo el trabajo?

#### Cómo lo hacemos

1. 2.000 monos entran en días aleatorios, pero solo con el precio sobre la SMA 200.
2. Cada mono hace el mismo número de operaciones, con la misma distribución de duraciones y los mismos costes.
3. Comparamos el Profit Factor, el retorno y el drawdown de la estrategia con los de los monos.

#### El criterio (fijado antes)

La estrategia tiene que superar al menos al 95 % de los monos en Profit Factor.

<!--amber-->
> Si le ganas a 2.000 monos que apuestan al azar con tus mismas condiciones, no fue suerte. Si no, era el mercado, no tú.

Gráfico izquierdo: 250 monos entrando al azar (gris) frente a la estrategia (verde). Etiquetas: estrategia · 4,7×; mono mediano · 1,5×. Gráfico derecho: Profit Factor de los 2.000 monos. Etiquetas: estrategia · PF 1,99 supera al 100,0 % de los monos; mono mediano · 1,21.

Izquierda: la curva de capital de 250 monos, el mono mediano (morado discontinuo) y la de la estrategia (verde), operación a operación. Derecha: distribución del Profit Factor de los 2.000 monos, con la curva de densidad; la línea verde es la estrategia.

- **1,99** — PF de la estrategia · periodo completo
- **1,21** — PF del mono mediano · misma tendencia, entrada al azar
- **100,0 %** — monos superados en Profit Factor
- **99,9 %** — monos superados en retorno total
- **99,3 %** — monos superados en drawdown (menor)

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> El mono mediano, entrando al azar dentro de la misma tendencia, consigue un Profit Factor de 1,21: el filtro de la SMA 200 ya da algo. La estrategia consigue 1,99 y bate al 100,0 % de los monos. La diferencia entre las dos cifras es exactamente lo que aporta el RSI(2): el momento de entrada importa.

---

## 3 · DRAWDOWNS Y DESGASTE DEL EDGE

### Lo que se siente por el camino, y si sigue vivo

Dos preguntas que no salen en la mayoría de backtests y que deciden si un sistema se puede operar de verdad.

## PRUEBA EXTRA · Drawdowns: lo que se siente por el camino

**Estado: SUPERADA**

#### La pregunta

¿Cuánto y durante cuánto tiempo va a estar la cuenta por debajo de su máximo? ¿Cuántos meses y años cierran en rojo? Es lo que hace abandonar a la gente, no el retorno final.

#### Cómo lo hacemos

1. Construimos la curva de capital día a día, valorando la posición abierta cada noche, y la cerramos mes a mes y año a año.
2. Identificamos cada caída desde un máximo hasta su recuperación: cuánto cayó y cuántos días tardó en volver, y las agrupamos por profundidad.
3. Contamos meses y años positivos y negativos, con foco en los últimos diez años.

#### El criterio (fijado antes)

Informativa: no hay umbral. Lo que se exige (drawdown < 20 % fuera de muestra) ya está en la Fase 1. Aquí se trata de que sepas cómo es el camino antes de recorrerlo.

<!--amber-->
> El retorno final es el destino; el drawdown es el viaje. Nadie abandona por el destino: abandonan en el kilómetro 30 del viaje.

### Las caídas, una a una y por tamaño

Gráfico: curva submarina — cuánto tiempo pasa la cuenta por debajo de su máximo (100 % capital).

Curva submarina con el 100 % del capital: cuánto está la cuenta por debajo de su máximo en cada momento. La línea punteada separa construcción y validación.

- **95** — caídas desde máximos · 27 años
- **95** — recuperadas · todas
- **93 días** — recuperación media · de cada caída
- **−27,2 %** — la más profunda · 2000
- **4,6 años** — la más larga · hasta recuperar

Gráfico (barras): las 95 caídas desde máximos, agrupadas por profundidad, con cuánto tardaron en recuperarse (100 % capital).

Las 95 caídas agrupadas por profundidad: cuántas hubo de cada tamaño, qué porcentaje del total son, y cuánto tardaron en recuperarse de media y como máximo. Casi todas son pequeñas y cortas; las que duelen son pocas, pero largas.

| Profundidad | Caídas | % del total | Recuperación media | Recuperación máxima |
|---|---|---|---|---|
| 0 – 2 % | 58 | 61 % | 10 días | 45 días |
| 2 – 5 % | 18 | 19 % | 48 días | 263 días |
| 5 – 10 % | 14 | 15 % | 208 días | 615 días |
| 10 – 15 % | 2 | 2 % | 429 días | 725 días |
| > 15 % | 3 | 3 % | 1205 días | 1675 días |

### Mes a mes, año a año

- **152 / 74** — meses positivos / negativos · 95 meses sin operar
- **7** — años negativos · de 27 · 2004, 2005, 2008, 2010, 2016, 2018, 2022
- **2** — años negativos en los últimos 10 · 2018, 2022 · desde 2017
- **−15,6 %** — peor mes · 30 abr 2000
- **9,8 %** — mejor mes · 100 % capital

Gráfico (mapa de calor): retorno mes a mes con el 100 % del capital · 152 meses positivos, 74 negativos, 95 sin operar (en blanco). A la derecha de cada año: retorno del año y meses ↑ / ↓.

Retorno de cada mes con el 100 % del capital (verde positivo, rojo negativo, vacío sin operaciones). A la derecha, el retorno del año y cuántos meses cerraron arriba y abajo. Así se ve de verdad lo que es operar esto: muchos meses planos, rachas de meses rojos pequeños y unos pocos meses que hacen el año.

| Año | Retorno | Meses ↑ | Meses ↓ | Peor mes | Mejor mes |
|---|---|---|---|---|---|
| 2017 | +11,3 % | 11 | 0 | +0,0 % | +2,6 % |
| 2018 | −3,5 % | 4 | 6 | −7,3 % | +3,1 % |
| 2019 | +4,2 % | 3 | 4 | −2,8 % | +5,0 % |
| 2020 | +20,2 % | 9 | 2 | −7,3 % | +8,9 % |
| 2021 | +7,2 % | 8 | 3 | −1,4 % | +2,6 % |
| 2022 | −0,7 % | 1 | 1 | −1,1 % | +0,3 % |
| 2023 | +18,1 % | 9 | 2 | −3,2 % | +8,3 % |
| 2024 | +14,0 % | 8 | 4 | −5,3 % | +5,9 % |
| 2025 | +8,3 % | 7 | 2 | −3,8 % | +9,8 % |
| 2026 | +12,0 % | 6 | 2 | −1,3 % | +5,3 % |

### Las cinco peores

| Inicio | Fondo | Recuperada | Profundidad | Duración |
|---|---|---|---|---|
| 3 abr 2000 | 14 abr 2000 | 12 ago 2003 | −27,2 % | 1226 días |
| 7 dic 2015 | 27 jun 2016 | 21 nov 2017 | −16,1 % | 715 días |
| 2 ene 2008 | 2 jul 2010 | 3 ago 2012 | −16,1 % | 1675 días |
| 2 ago 2018 | 3 jun 2019 | 27 jul 2020 | −12,4 % | 725 días |
| 27 jun 2024 | 5 ago 2024 | 7 nov 2024 | −10,5 % | 133 días |

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> De 27 años, 7 cerraron en negativo (2004, 2005, 2008, 2010, 2016, 2018, 2022); en los últimos diez, 2. Pero 74 meses de 226 operados cerraron en rojo: casi la mitad. Todas las caídas se recuperaron, y la más larga tardó 4,6 años (2 ene 2008 → 3 ago 2012). Eso, con el 100 % del capital: con el tamaño por ATR del robot la caída más profunda de toda la historia fue −6,7 %, a cambio de un retorno de 2,1 % anual frente a 5,9 %. Ganar con esta estrategia es, sobre todo, saber esperar sin tocar nada.

---

## PRUEBA EXTRA · Desgaste del edge: ¿sigue viva?

**Estado: SUPERADA**

#### La pregunta

Las estrategias publicadas en libros suelen dejar de funcionar cuando todo el mundo las conoce. ¿Le está pasando a esta?

#### Cómo lo hacemos

1. Calculamos el Profit Factor de las últimas 40 operaciones en cada momento, y lo seguimos a lo largo de los 27 años: si el edge se gastara, esa línea bajaría hacia 1 y se quedaría ahí.
2. Contamos las operaciones de cada año: si la señal dejara de aparecer, también sería una forma de morir.
3. Comparamos la media del periodo de construcción con los tres últimos años completos.

#### El criterio (fijado antes)

El Profit Factor de los tres últimos años completos no caiga más de un 20 % respecto al periodo de construcción.

<!--amber-->
> Un edge es como una mina: tarde o temprano se agota. La pregunta no es si se agotará, sino si ya empezó. Por ahora, no.

Gráfico: ¿Se desgasta el edge? Profit Factor móvil: si la línea baja hacia 1 y se queda, el edge estaría muriendo. Eje Y: Profit Factor de las últimas 40 operaciones. Referencias: criterio 1,3; por debajo de 1 el sistema pierde; zona «fuera de muestra →». Gráfico inferior: frecuencia: verde = año con PF > 1, rojo = año perdedor. Sin barra = año sin operaciones (precio bajo la SMA 200).

Arriba: Profit Factor móvil de las últimas 40 operaciones. Por encima de 1 (línea roja) se gana; 1,3 (línea discontinua) es el criterio de la Fase 1. Las zonas rojas son rachas de 40 operaciones perdedoras en conjunto: existen, y siempre volvieron. Abajo: operaciones por año; sin barra es un año sin señales, con el precio bajo la SMA 200.

| | Construcción (media por año) | Últimos 3 años completos (2023–2025) |
|---|---|---|
| Operaciones por año | 11,4 | 14,3 |
| Retorno medio por operación | 0,47 % | 0,91 % |
| Profit Factor | 1,76 | 3,06 |

<!--green-->
> **QUÉ SIGNIFICA PARA TI**
>
> Frecuencia, retorno por operación y Profit Factor se mantienen o mejoran: el Profit Factor de los tres últimos años completos es 3,06 frente a 1,76 en construcción. Esto describe el pasado reciente, no garantiza el futuro: por eso lo seguimos midiendo cada año y esta página se regenera con los datos nuevos.

---

## 4 · CONCLUSIÓN Y GLOSARIO

### Lo que las ocho pruebas permiten afirmar

**✓ Lo que las pruebas dicen**

- El Nasdaq revierte a corto plazo tras caídas bruscas, y con consistencia solo sobre la SMA 200 (AED).
- Las reglas ganan en 27 años, con costes, y en ocho años que no vieron (Fase 1).
- Rinden año a año, no por dos rachas (Fase 2), y no dependen de un número exacto (Fase 3).
- El riesgo del camino está medido: −25,2 % en el 5 % peor de 10.000 caminos con todo el capital, −41,1 % en el peor (Fase 4).
- Aguanta costes dobles y quitarle sus mejores años (Fase 5), y bate al 100,0 % de las entradas al azar (mono).
- Casi la mitad de los meses operados cierran en rojo y las caídas largas existen: el edge se cobra en paciencia.
- No hay señales de desgaste hasta hoy, y esta página se regenera con los datos nuevos para seguir vigilándolo.
- El robot hace lo que dice el papel: el Strategy Tester de MetaTrader 5 coincide con el motor en 40 de 40 entradas y salidas (21 feb 2024 → 14 sep 2026).

### Glosario

**RSI** — Relative Strength Index. Mide la fuerza de las subidas frente a las bajadas recientes, de 0 a 100. Con 2 períodos reacciona en dos días.

**SMA 200** — Media móvil simple de los últimos 200 cierres. El filtro de tendencia más usado del mundo.

**Profit Factor (PF)** — Dinero ganado dividido por dinero perdido. Por encima de 1 el sistema gana; 2 significa que gana el doble de lo que pierde.

**PF sin la mejor operación** — El mismo cálculo quitando la mejor operación. Si se hunde, el resultado depende de un golpe de suerte.

**CAGR** — Tasa de crecimiento anual compuesto: el retorno anual equivalente.

**Drawdown** — Caída desde el último máximo de capital. El máximo drawdown es la caída más profunda de la serie.

**Dentro / fuera de muestra (IS / OOS)** — Datos usados para construir la regla / datos guardados para comprobarla una vez fijada.

**Walk-forward** — Validar cada tramo de tiempo contra el tramo anterior, rodando hacia delante.

**Zonas robustas** — Mover los parámetros alrededor de los elegidos y comprobar que el vecindario entero gana, no solo una celda.

**Monte Carlo (block bootstrap)** — Reordenar las operaciones miles de veces, en bloques, para ver el abanico de resultados que el azar del orden permitía.

**Test del mono** — Comparar la estrategia con entradas al azar bajo las mismas condiciones. Si no le gana al mono, no hay habilidad.

**Edge decay** — Desgaste del edge: cuando una ventaja publicada deja de funcionar porque todos la operan.

**Expectancy** — Retorno medio por operación, ganadoras y perdedoras incluidas.

**ATR** — Average True Range: cuánto se mueve el precio al día, de media. La vara de la volatilidad con la que el robot decide el tamaño.

**Slippage** — Diferencia entre el precio de la señal y el precio al que de verdad se ejecuta.

**Puntos básicos (bps)** — Centésimas de 1 %. 5 bps = 0,05 %.

---

## Documentación: con qué se hizo todo

### Datos — Norgate + Darwinex

- **Norgate Data:** QQQ diario con retorno total (splits y dividendos incluidos), la misma fuente que usamos en Sentinel para todo. 21 dic 1999 → 28 sep 2026 · 6.732 velas tras el calentamiento de la SMA 200.
- **Darwinex:** velas diarias del propio bróker (CFD NDX) para el contraste, y sus specs reales para los costes.
- Los datos de Norgate tienen licencia y no se redistribuyen: el repositorio trae un descargador de Yahoo Finance para reproducirlo con cifras casi idénticas.

### Partición — 70 % construcción · 30 % validación

- Por número de velas, en orden cronológico.
- Construcción: 21 dic 1999 → 12 sep 2018 (192 operaciones).
- Validación: 13 sep 2018 → 28 sep 2026 (93 operaciones). Ninguna operación cruza la frontera.

### Costes — 10 puntos básicos ida y vuelta

- Compra: apertura × 1,0005. Venta: apertura × 0,9995.
- Comisión 0; el spread va dentro del slippage.
- En Darwinex el coste medio real del CFD es ≈ 8 bps por operación (spread + swap). La prueba de estrés lo dobla.

### Motor — Sentinel · un solo código para todo

Backtest, cinco fases, test del mono, desgaste y drawdowns salen del mismo motor y del mismo dataset. Ninguna cifra de esta guía se escribió a mano.

```
python descargar_datos.py
python motor/rsi2_motor.py
python motor/construir_html.py
```

### Bibliografía — Fuentes

- Connors & Alvarez (2008), *Short Term Trading Strategies That Work*
- Connors & Alvarez (2009), *High Probability ETF Trading*
- StockCharts ChartSchool: RSI(2) · QuantifiedStrategies: RSI 2 strategy

### Reconciliación MT5 — Cerrada · 40/40 operaciones

El Strategy Tester de MetaTrader 5 (Darwinex, 100 % ticks reales) y el motor dan las mismas fechas de entrada y de salida en las 40 operaciones de la ventana ejecutable 21 feb 2024 → 14 sep 2026. PF 2,12, aciertos 80 %. Las diferencias de precio de entrada son el spread del bróker.

### Reproducir — Research reproducible

Descarga los datos, ejecuta el motor y revisa por tu cuenta las pruebas y resultados de validación de la estrategia. Enlace: Ir al repositorio →

### Contraste con los datos del bróker

| | QQQ (ETF) · validación | NDX CFD del bróker · validación |
|---|---|---|
| Periodo | 13 sep 2018 → 28 sep 2026 | 30 mar 2021 → 31 jul 2026 |
| Operaciones | 93 | 67 |
| Profit Factor | 2,66 | 3,95 |
| CAGR (100 % capital) | 9,1 % | 12,8 % |
| Drawdown día a día | −11,9 % | −8,7 % |
| Aciertos | 80 % | 76 % |

<!--blue-->
> Mismo motor, mismas reglas, sobre las velas diarias del propio bróker. El comportamiento se mantiene en el instrumento que opera el robot. Los datos del bróker no se redistribuyen (son suyos); el motor acepta cualquier CSV diario exportado de MetaTrader.
