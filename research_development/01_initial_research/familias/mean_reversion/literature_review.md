# Revisión de literatura · Reversión a la media

**Corte temporal:** evidencia publicada hasta 2017-12-31.  
**Estado:** revisión bibliográfica; no se consultaron datasets del repo ni se ejecutaron backtests. No confirma ningún edge propio.

## Qué significa “reversión” en esta revisión

La reversión de retornos puede describir fenómenos distintos: autocorrelación negativa a corto plazo, reversión de precios a horizontes multianuales, reversal de carteras de ganadores/perdedores, o ganancias contrarian producidas por relaciones entre activos. No son hipótesis intercambiables. Una ficha concreta debe definir señal, horizonte, activo/universo, benchmark y precio de ejecución antes de mirar el resultado.

## Evidencia primaria localizada

### [R1] Retornos contrarian a horizonte multianual y sobrerreacción

Werner F. M. De Bondt y Richard Thaler (1985), “Does the Stock Market Overreact?”, *The Journal of Finance*, 40(3), 793–805. [Wiley / DOI](https://doi.org/10.1111/j.1540-6261.1985.tb05004.x).

Con retornos mensuales CRSP, los autores encuentran resultados consistentes con su hipótesis de sobrerreacción en carteras históricas de ganadores y perdedores; destacan retornos de enero de los perdedores incluso varios años después de formar las carteras.

**Qué sustenta:** estudiar si movimientos extremos pasados de acciones se revierten en el largo plazo es una pregunta empírica motivada por evidencia publicada.  
**Qué no sustenta:** una señal de reversión intradía/diaria, reversión en QQQ u otro instrumento concreto, causalidad psicológica demostrada, fills ejecutables o rentabilidad neta actual. El diseño de cartera y explicaciones alternativas deben revisarse antes de adaptar la señal.

### [R2] Autocorrelación según horizonte y límites de potencia

James M. Poterba y Lawrence H. Summers (1988), “Mean Reversion in Stock Prices: Evidence and Implications”, *Journal of Financial Economics*, 22(1), 27–59. [ScienceDirect / DOI](https://doi.org/10.1016/0304-405X(88)90021-9).

Evalúan componentes transitorios en precios de Estados Unidos y otros 17 países. Sus estimaciones puntuales implican autocorrelación positiva de retornos a corto plazo y negativa a horizontes largos, pero los autores indican que la hipótesis de paseo aleatorio no puede rechazarse a niveles convencionales; también advierten que los tests tienen poca potencia para detectar desviaciones persistentes.

**Qué sustenta:** la relación entre retornos pasados y futuros puede variar de signo con el horizonte, y la incertidumbre estadística importa.  
**Qué no sustenta:** una reversión rentable en horizonte operativo específico ni una estimación suficientemente precisa para escoger parámetros en los activos del repositorio.

### [R3] Evidencia de predictibilidad a varios rezagos

Narasimhan Jegadeesh (1990), “Evidence of Predictable Behavior of Security Returns”, *The Journal of Finance*, 45(3), 881–898. [Wiley / DOI](https://doi.org/10.1111/j.1540-6261.1990.tb05110.x).

El estudio reporta autocorrelación negativa significativa de primer orden en retornos mensuales individuales y autocorrelación positiva significativa en rezagos mayores, particularmente a doce meses, en su muestra de acciones. Esta diferencia de horizonte desaconseja reducir “mean reversion” a una sola pauta.

**Qué sustenta:** estudiar por separado horizontes cortos y largos y permitir efectos opuestos.  
**Qué no sustenta:** que el retorno negativo de primer rezago sea económicamente grande, persistente fuera de muestra o ejecutable tras spread, bid-ask bounce, costos y restricciones de venta corta.

### [R4] Ganancias contrarian no identifican necesariamente sobrerreacción

Andrew W. Lo y A. Craig MacKinlay (1990), “When Are Contrarian Profits Due to Stock Market Overreaction?”, *The Review of Financial Studies*, 3(2), 175–205. [Oxford Academic / DOI](https://doi.org/10.1093/rfs/3.2.175).

Analizan una estrategia contrarian y muestran que puede producir rendimientos esperados positivos cuando algunos activos lideran o rezagan a otros, aun sin autocorrelación negativa en los retornos individuales. Reportan autocorrelación positiva de retornos semanales de cartera y evidencia de que acciones grandes lideran a pequeñas; encuentran evidencia contra la sobrerreacción como única fuente de beneficios contrarian.

**Qué sustenta:** medir autocorrelaciones cruzadas y la construcción del universo, además de autocorrelación propia, antes de atribuir beneficios a reversión.  
**Qué no sustenta:** que una pauta de reversión de un solo activo (por ejemplo QQQ o un CFD) vaya a funcionar ni que beneficios de cartera sean un mecanismo de reversal ejecutable.

## Mecanismos y explicaciones alternativas

- **Sobrerreacción conductual:** noticias o movimientos extremos reciben peso excesivo y luego se corrigen; es una interpretación posible en R1, no una causalidad establecida para todo activo.
- **Presión temporal de liquidez:** ventas/compras forzadas o necesidad transitoria de contrapartida pueden revertir después. Requiere datos y pruebas específicos del mercado; no queda comprobado por los artículos anteriores.
- **Autocorrelación cruzada:** precios de activos relacionados pueden incorporar información en momentos distintos; una regla de cartera contrarian puede capturar esta relación sin que exista reversión propia del activo (R4).
- **Riesgo variable, prima exigida y baja potencia:** lo observado en ventanas largas puede tener explicaciones de riesgo o ser difícil de distinguir de un paseo aleatorio (R2).
- **Microestructura:** bid-ask bounce, cierre/apertura, liquidez y precios mid pueden crear reversión aparente a frecuencias altas. Debe verificarse con quotes/fills del instrumento, no deducirse de evidencia mensual sobre acciones.

## Aplicabilidad preliminar al repositorio

Las EDA nombran QQQ y otros instrumentos, pero el ticker y la notebook no identifican por sí solos proveedor, política de ajustes, venue ni cobertura. R1–R4 tratan principalmente acciones/portafolios de acciones y horizontes mensuales o semanales. Son motivación para formular preguntas en acciones, no evidencia directa sobre QQQ intradía, futuros, CFDs, FX o cripto. Cada mercado requiere su propia ficha y datos del broker/venue; si se propone frecuencia alta, primero probar que los retornos no son un artefacto de cotizaciones y ejecución.

## Preguntas falsables para fichas posteriores

1. Para un activo/universo y frecuencia especificados de antemano, ¿retornos extremos pasados predicen retornos posteriores de signo contrario a un horizonte fijo, netos de bid-ask y costos, frente a un benchmark definido?
2. ¿El resultado cambia de signo entre horizontes cortos y largos como sugieren las diferencias de autocorrelación observadas en R2/R3? Ajustar por la cantidad total de horizontes examinados.
3. En una estrategia de cartera, ¿la rentabilidad se explica por autocorrelación propia o por autocorrelación cruzada/efectos de liderazgo? Descomponer ambos componentes antes de atribuir un mecanismo.
4. ¿La señal sobrevive en datos fuera de muestra con universo point-in-time, incluyendo activos excluidos/descontinuados y reglas de corporate actions?

Estas preguntas no son resultados ni edges aprobados. Cualquier ficha debe documentar muestra, independencia temporal, hipótesis múltiples, costes ejecutables y límites del feed; aplicar los gates comunes de [`../../GATES.md`](../../GATES.md).

## Referencias

Todas las fuentes listadas fueron localizadas en Wiley Online Library, ScienceDirect o Oxford Academic mediante sus DOI; todas se publicaron antes de 2018. Los resúmenes anteriores distinguen los hallazgos reportados de mecanismos que siguen siendo hipótesis.
