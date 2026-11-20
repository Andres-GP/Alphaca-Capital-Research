# Literatura y mecanismo · Momentum y tendencia

**Corte de literatura:** publicaciones hasta el 31-12-2017.  
**Estado para Alphaca:** revisión bibliográfica, no prueba empírica. No se han verificado aquí los contratos, la procedencia ni la cobertura de los datos locales; no hay resultados propios ni un edge confirmado.

## Mecanismo y distinciones

El **momentum de serie temporal (TSMOM)** toma una posición según el signo del retorno pasado del mismo activo. El **momentum transversal** compra activos que superaron a otros y vende los rezagados. Las dos pautas están relacionadas, pero no son intercambiables: difieren en la señal y en los datos necesarios para evaluarlas.

Una explicación posible para la continuación de plazo intermedio es la incorporación gradual de información o el ajuste escalonado de posiciones ante límites de riesgo y capital. En horizontes largos, la sobrerreacción, los cambios de régimen o la reversión podrían debilitar o invertir la pauta. La evidencia descrita abajo es compatible con algunos de estos mecanismos, pero no demuestra que sean la causa ni que apliquen a los instrumentos del proyecto.

## Trabajos académicos anteriores a 2018

- **Moskowitz, Tobias J.; Yao Hua Ooi; Lasse Heje Pedersen (2012), “Time Series Momentum”.** Estudian futuros de índices bursátiles, divisas, materias primas y bonos. Reportan persistencia de retornos entre uno y doce meses y reversión parcial en horizontes más largos en los instrumentos de su estudio. Es evidencia pertinente para formular una hipótesis de TSMOM en futuros; no confirma la pauta en un contrato, feed o estrategia local. [*Journal of Financial Economics*, 104(2), 228–250](https://doi.org/10.1016/j.jfineco.2011.11.003). citeturn0search0

- **Hurst, Brian; Yao Hua Ooi; Lasse Heje Pedersen (2017), “A Century of Evidence on Trend-Following Investing”.** Presentan un análisis histórico de seguimiento de tendencia en mercados globales desde 1880 con una base construida a partir de distintas fuentes. El resultado motiva estudiar la pauta en distintos periodos y clases de activos, pero la longitud histórica no garantiza series homogéneas ni precios directamente ejecutables en el mercado objetivo. [*The Journal of Portfolio Management*, 44(1), 15–29](https://doi.org/10.3905/jpm.2017.44.1.015). citeturn2search3

- **Brock, William; Josef Lakonishok; Blake LeBaron (1992), “Simple Technical Trading Rules and the Stochastic Properties of Stock Returns”.** Evalúan reglas de media móvil y ruptura de rango sobre el Dow Jones Industrial Average entre 1897 y 1986, comparándolas mediante bootstrap con varios modelos nulos. Sus resultados corresponden a esas reglas, índice y periodo; no establecen rentabilidad neta actual ni un mecanismo causal general. [*The Journal of Finance*, 47(5), 1731–1764](https://doi.org/10.1111/j.1540-6261.1992.tb04681.x). citeturn0search1

- **Jegadeesh, Narasimhan; Sheridan Titman (1993), “Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency”.** Documentan retornos positivos para estrategias transversales de compra de ganadores y venta de perdedores con periodos de tenencia de 3 a 12 meses; parte del rendimiento anormal del primer año se disipa en los dos siguientes. Es evidencia sobre acciones y rankings relativos, no una prueba de TSMOM en futuros. [*The Journal of Finance*, 48(1), 65–91](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x). citeturn1search0

- **Hong, Harrison; Terence Lim; Jeremy C. Stein (2000), “Bad News Travels Slowly: Size, Analyst Coverage, and the Profitability of Momentum Strategies”.** En acciones, encuentran mayor rentabilidad de momentum entre empresas con menor cobertura de analistas, manteniendo constante el tamaño, y un efecto más marcado entre las acciones perdedoras. El hallazgo es consistente con difusión gradual de información específica; no demuestra ese mecanismo en futuros o CFDs. [*The Journal of Finance*, 55(1), 265–295](https://doi.org/10.1111/0022-1082.00206). citeturn2search0

- **Daniel, Kent; Tobias J. Moskowitz (2016), “Momentum Crashes”.** Documentan episodios de pérdidas infrecuentes y persistentes en estrategias de momentum y encuentran que aparecen asociados a estados de pánico, caídas previas del mercado, volatilidad elevada y rebotes. Es una cautela para medir pérdidas y dependencia del régimen; no permite anticipar el comportamiento de los instrumentos locales sin probarlo. [*Journal of Financial Economics*, 122(2), 221–247](https://doi.org/10.1016/j.jfineco.2015.12.002). citeturn1search12

## Predicciones falsables para una prueba posterior

Estas son preguntas de investigación, no resultados ni parámetros aprobados:

1. **Continuación TSMOM:** en contratos y venues definidos antes del análisis, ¿el signo del retorno total pasado de 12 meses predice retornos del mismo signo durante los siguientes 1–12 meses? Medir por separado cada horizonte, frente a un benchmark predefinido y antes y después de costos ejecutables.
2. **Continuación y reversión:** ¿la relación entre el retorno pasado y el futuro es positiva a horizontes intermedios y se debilita o invierte a horizontes mayores, dentro del mismo instrumento y feed?
3. **Mecanismo informativo:** si hay medidas comparables de flujo de información o restricciones de posicionamiento, ¿la predictibilidad es mayor donde la información se incorpora más lentamente o el ajuste de posiciones parece más escalonado? Si no se pueden medir esos factores, el mecanismo queda sin identificar.
4. **Régimen y pérdidas:** ¿las pérdidas se concentran en periodos de rebote, alta volatilidad o cambio de tendencia? Definir los regímenes de antemano y reportar también los episodios adversos.

## Límites de inferencia y preguntas abiertas

Los resultados publicados varían en mercado, periodo, frecuencia, definición de retorno y construcción de la cartera. La evidencia de acciones no confirma una pauta en futuros; la evidencia en futuros no confirma una pauta en CFDs, ETF, criptoactivos ni barras intradía. Una base histórica larga tampoco garantiza cobertura sin huecos o ejecución replicable.

Para evaluar la ficha local de TSMOM siguen abiertas preguntas esenciales: ¿qué contrato y venue representa cada símbolo?, ¿cuál es la fuente y cobertura efectiva del historial?, ¿cómo se definirá el retorno total y el rollover?, ¿qué precios y costos corresponden a una ejecución posible? También deben fijarse de antemano el universo, los horizontes, la métrica primaria y el periodo de validación, y tratar correctamente las ventanas solapadas, la dependencia temporal y la selección entre múltiples variantes.

Hasta resolver esas cuestiones y aplicar los gates del proyecto, la hipótesis permanece **no probada**.