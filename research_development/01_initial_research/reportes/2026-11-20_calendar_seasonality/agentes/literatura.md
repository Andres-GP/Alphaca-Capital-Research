# Literatura y mecanismo · Estacionalidad y calendario

**Corte de literatura:** 2017-12-31.  
**Estado para Alphaca:** los archivos proporcionados no documentan una prueba local ni confirman un efecto de calendario. Los hallazgos siguientes pertenecen a las muestras e instrumentos de los estudios citados.

## Mecanismo y predicciones falsables

Para una pauta de día de semana en acciones de EE. UU., el fin de semana puede cambiar la distribución de noticias y el intervalo sin negociación. También pueden influir los horarios de liquidación, la microestructura de apertura y el momento en que se publican noticias. Son explicaciones posibles, no causas demostradas para los datos de Alphaca.

De esas explicaciones surgen pruebas separables:

- **Tiempo calendario frente a tiempo de negociación:** fijar por adelantado si se mide viernes-cierre a lunes-cierre, viernes-cierre a lunes-apertura o lunes durante la sesión. Comparar las predicciones de cada hipótesis.
- **Acumulación de noticias:** separar el retorno de fin de semana del retorno intradía del lunes; contrastar el patrón con timestamps de anuncios disponibles entonces.
- **Liquidación y microestructura:** examinar si el diferencial se concentra en apertura o en ciertos intervalos, y si persiste con precios ejecutables y costos variables por horario.
- **Estabilidad:** fijar ventanas cronológicas fuera de muestra. Un diferencial histórico de medias no implica que se mantenga ni que pueda negociarse hoy.

## Trabajos académicos anteriores a 2018

- **Kenneth R. French (1980), “Stock Returns and the Weekend Effect.”** En retornos diarios del portafolio S&P Composite entre 1953 y 1977, reporta retornos medios de lunes significativamente negativos en cada uno de cinco subperiodos. Los datos no encajan con claridad con las hipótesis simples de tiempo calendario y tiempo negociado que compara. [DOI y artículo de Elsevier](https://doi.org/10.1016/0304-405X(80)90021-5). Este resultado motiva una prueba, pero no establece un mecanismo causal ni evidencia para otro periodo, instrumento o feed.

- **Josef Lakonishok y Maurice Levi (1982), “Weekend Effects on Stock Returns: A Note.”** El artículo examina explicaciones institucionales del efecto de fin de semana, entre ellas la liquidación. [DOI y artículo de Wiley](https://doi.org/10.1111/j.1540-6261.1982.tb02231.x). Sirve para formular una hipótesis estructural; no basta para atribuir un patrón observado en otros datos al sistema de liquidación.

- **Lawrence Harris (1986), “A Transaction Data Study of Weekly and Intradaily Patterns in Stock Returns.”** Con datos de transacciones, encuentra que el retorno negativo de lunes se distribuye de manera distinta según el tamaño de las empresas: para las grandes aparece entre el cierre del viernes y la apertura del lunes; para las pequeñas, principalmente durante la sesión del lunes. También reporta diferencias entre días en los primeros 45 minutos. [DOI y copia del artículo](https://doi.org/10.1016/0304-405X(86)90044-9). El trabajo respalda separar intervalos y horarios; no valida rentabilidad neta en otro mercado.

- **Josef Lakonishok y Seymour Smidt (1988), “Are Seasonal Anomalies Real? A Ninety-Year Perspective.”** Con 90 años de datos diarios del Dow Jones, reportan patrones persistentes alrededor del cambio de semana, mes y año, y de los feriados. [DOI y artículo de Oxford Academic](https://doi.org/10.1093/rfs/1.4.403). La muestra larga permite estudiar persistencia histórica, pero no certifica una regla actual ni su ejecución.

- **Ronen A. Ariel (1987), “A Monthly Effect in Stock Returns.”** Reporta que, en la muestra estudiada, el retorno medio de acciones era positivo principalmente en días inmediatamente anteriores y durante la primera mitad de los meses calendario, e indistinguible de cero en la segunda mitad. [DOI y artículo de Elsevier](https://doi.org/10.1016/0304-405X(87)90066-3). Es una pauta distinta del efecto semanal y no debe mezclarse con ella ni extrapolarse a otros activos.

- **Ryan Sullivan, Allan Timmermann y Halbert White (1999), “Data-Snooping, Technical Trading Rule Performance, and the Bootstrap.”** Aplican White’s Reality Check al universo de reglas técnicas evaluadas para cuantificar el sesgo de búsqueda. [DOI y artículo de Wiley](https://doi.org/10.1111/0022-1082.00163). No es evidencia de un efecto calendario concreto, pero sí fundamenta corregir por la familia completa de variantes exploradas.

## Límites de inferencia y preguntas abiertas

La evidencia citada estudia principalmente acciones y períodos históricos específicos. No demuestra que un patrón se traslade a ETF, futuros, FX, CFDs o cripto, ni que sobreviva a cambios de horario, mercado, feed y costos. En particular, una vela diaria del proveedor puede no coincidir con la sesión del venue; asignar mal la fecha o mezclar retornos overnight e intradía puede alterar la pauta medida.

Para Alphaca quedan abiertas estas preguntas:

1. ¿Qué benchmark e instrumento se analizarán, y cuál será su fuente primaria de precios?
2. ¿Qué sesión, zona horaria, reglas DST y calendario oficial definirán cada fecha?
3. ¿La predicción se refiere al retorno viernes-cierre a lunes-apertura, al lunes intradía o al cierre-a-cierre?
4. ¿El patrón se mantiene fuera de muestra, después de registrar y corregir el universo de días, ventanas y mercados probados?
5. ¿Persiste con precios ejecutables, cobertura verificada y costos del instrumento?

Hasta fijar esas definiciones y probar los datos, la pauta sigue siendo una hipótesis; la literatura no constituye evidencia de un edge propio.