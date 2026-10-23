Formación de Trade it Simple
para Trading Sistemático TIS

FAQ - ESTRATEGIA #1: OVERNIGHT
GAP TRADING

25 PREGUNTAS MÁS FRECUENTES

Todas las dudas que te están frenando, resueltas con datos y ejemplos reales

CONCEPTOS FUNDAMENTALES

1. ¿Por qué hay dos estrategias diferentes para gaps?

Respuesta directa: Porque "no todos los gaps son iguales". Los pequeños tienden a
cerrarse (mean reversion), mientras que a partir de 1% la probabilidad de continuación
sube con claridad.

La clave: El mismo patrón visual encierra dos edges distintos si separas por tamaño y
dirección.

2. ¿Cuáles son los dos enfoques exactos?

Respuesta directa:

●  Estrategia A - Mean Reversion (MR): 0.5% a <1% - Operar CONTRA el gap
●  Estrategia B - Trend Following (TF): ≥1% a 4% - Operar A FAVOR del gap

Lógica:

●  MR: En gaps pequeños domina la micro-ineficiencia; el relleno parcial/completo es

frecuente

●  TF: A partir de 1% aumenta la probabilidad de continuación (gap "con sentido")

3. ¿Qué activos puedo usar?

Respuesta directa:

●  Primary: SPY únicamente (simplicidad y liquidez)
●  Expansión: QQQ, IWM tras 2 semanas (más frecuencia)
●  Large caps: Después de 3-4 semanas y cuenta >$50K
●  Requisito: ADV >$1B (volumen diario promedio)

Página 1 de 8

4. ¿Cuál es la ventana de operación?

Respuesta directa: 9:40-11:00 AM EST únicamente. Una sola ventana, sesión regular. NO
se necesita premarket para operar.

Timeframe de confirmación: Gráfico 5 o 15 minutos:

●  5m → más señales, más falsos quiebres
●  15m → menos señales, más sólidas

5. ¿Qué dice la validación estadística?

Respuesta directa: Según SPY 2023-2025, sesión regular:

Gap Size  Fill Rate aprox.  Continuation aprox.

Sesgo
dominante

<0.5%

~67.5%

~47.2%

Mean Reversion

0.5-<1%  ~35.9%

~49.2%

Mean Reversion

≥1-<2%

~28.6%

~50.0%

Trend Following

≥2-<3%

<00.0%

>60%

Trend Following

≥3-<4%

<40.0%

>40.0%

Trend Following

IMPLEMENTACIÓN PRÁCTICA

6. ¿Cómo identifico qué estrategia usar?

Respuesta directa: Mide el gap % al open y clasifica:

●  MR si <1% → Operar CONTRA el gap
●  TF si ≥1% → Operar A FAVOR del gap

Fórmula del gap: Gap % = ((Open - Close anterior) / Close anterior) × 100

7. ¿Cuáles son los triggers exactos para Mean Reversion?

Respuesta directa: Para gaps 0.5% a <1%:

Gap up → SHORT:

1.  Espera el cierre de la vela de apertura (5 o 15m)
2.  Traza el mínimo de esa vela
3.  Si cualquier vela posterior rompe y cierra por debajo de ese mínimo → entra

short inmediatamente tras el cierre

Página 2 de 8

Gap down → LONG:

1.  Espera el cierre de la vela de apertura
2.  Traza el máximo de esa vela
3.  Si cualquier vela posterior rompe y cierra por encima de ese máximo → entra

long tras el cierre

8. ¿Cuáles son los triggers exactos para Trend Following?

Respuesta directa: Para gaps ≥1% a 4%:

Gap up → LONG:

1.  Espera el cierre de la vela de apertura (5 o 15m)
2.  Traza el máximo de esa vela
3.  Si cualquier vela posterior rompe y cierra por encima de ese máximo → entra

long tras el cierre

Gap down → SHORT:

1.  Espera el cierre de la vela de apertura
2.  Traza el mínimo de esa vela
3.  Si cualquier vela posterior rompe y cierra por debajo de ese mínimo → entra

short tras el cierre

9. ¿Cuáles son los objetivos y stops?

Respuesta directa:

Mean Reversion (MR):

●  Target: 50-75% del fill hacia el cierre previo
●  Stop: ATR(5) del día anterior × 0.8-1.2 o detrás del máximo/mínimo de apertura
●  Time exit: Cierre del día si no se alcanzó target

Trend Following (TF):

●  Target: 1.0-2.0× el tamaño del gap (en %) o trailing stop ≈ ATR(5)/3
●  Stop: ATR(5) del día anterior × 1.0-1.5 o bajo/encima del máximo/mínimo de

apertura

●  Multiday: Opcional mantener 1-3 sesiones si cierre permanece a favor

10. ¿Cuándo NO debo operar?

Respuesta directa:

●  Gap <0.5% o >4%
●  Noticias mayores del día(durante sesión)
●  Viernes (opcional evitar por weekend)

Página 3 de 8

●  En MR: gap ya rellenado >50% antes de confirmar
●  En TF: falsa ruptura temprana (wick sin cierre)

Nota importante: Gaps >3-4% son estadísticamente poco probables y ocurren con muy
baja frecuencia. Cuando aparecen, suelen tener justificación fundamental fuerte, por lo que
es mejor evitarlos hasta dominar completamente la estrategia.

Regla de oro: NO te fuerces a operar si no hay condiciones. Si te notas desesperado por
falta de setups, mejor escoge una estrategia con mayor frecuencia o utiliza más activos
(QQQ, IWM) en lugar de forzar operaciones de baja calidad.

REGLAS DE EJECUCIÓN

11. ¿Cuál es el flujo de trabajo diario?

Respuesta directa:

Antes de apertura (rápido, sin operar):

●  Revisar que no haya catalizadores mayores (Fed/earnings/datos macro)

9:30-9:40 AM:

●  Dejar que el mercado marque la apertura
●

Identificar máximo/mínimo de la vela de apertura (5 o 15m)

9:40-11:00 AM (ejecución):

1.  Medir gap % y clasificar: MR si <1% | TF si ≥1%
2.  Confirmar clean news
3.  Aplicar trigger (ruptura + cierre de vela)
4.  Colocar stop y target en el momento de entrada
5.  Registrar en bitácora

12. ¿Qué es el filtro de noticias?

Respuesta directa: Binario: Clean vs Contaminated. Evitar días con Fed/earnings/noticia
mayor si estas se dan durante la sesión.

Clean: Sin catalizador mayor en la jornada Contaminated: Fed, earnings, noticias
corporativas mayores

13. ¿Puedo operar en premarket?

Respuesta directa: NO. El gap se calcula sobre apertura de sesión regular vs cierre previo.
No se necesita premarket para operar.

Página 4 de 8

14. ¿Qué timeframe uso?

Respuesta directa:

Identificación: Diario para métricas

●
●  Ejecución y confirmación: 5-15 min
●  Siempre esperar cierre de la vela de confirmación (no entrar en la misma vela que

rompe)

15. ¿Cómo gestiono el riesgo?

Respuesta directa:

●  Riesgo por trade: 1-2% del capital
●  Fórmula: Riesgo $ = Capital × %Riesgo
●  Stop $/unidad: Precio × (% stop/100) o distancia vía ATR(5)
●  Unidades: Riesgo $ ÷ Stop $/unidad

GESTIÓN DE CAPITAL Y RIESGO

16. ¿Cuál es la progresión recomendada?

Respuesta directa:

●  Semana 1: SPY solo (dominar mecánica)
●  Semana 2: SPY + QQQ + IWM (sube frecuencia)
●  Semana 3+: Large caps selectas si la disciplina es consistente

17. ¿Qué complejidad y tiempo requiere?

Respuesta directa:

●  Complejidad: 2/10 (reglas binarias, dos lógicas claras)
●  Tiempo requerido: 3/10 (ventana corta, monitoreo simple)
●  Frecuencia esperada: MR (0.5-<1%) → Frecuente; TF (≥1%) → Menos frecuente,

mayor recorrido

Gestión de expectativas: Si la frecuencia te parece baja y sientes desesperación por
operar más, tienes dos opciones saludables:

1.  Expandir activos: Agregar QQQ e IWM para más oportunidades
2.  Estrategia complementaria: Buscar una segunda estrategia con mayor frecuencia
3.  NUNCA: Forzar operaciones de baja calidad solo por "hacer algo"

Página 5 de 8

18. ¿Cuáles son los niveles de confianza?

Respuesta directa:

Alta (ejecutar):

●  MR 0.5-<1% sin noticia, confirmación clara (15m)
●  TF 1-2.5% con índice alineado y ruptura limpia con cierre

Media (cautela):

●  0.5% exacto o 1% exacto (zona frontera)
●  Dato macro menor en la jornada

Baja (pasar):

●  3-4% sin claridad de contexto (además, estos gaps son estadísticamente poco

probables y ocurren con muy baja frecuencia)

●  Cualquier ambigüedad de noticia/catalizador

19. ¿Cuándo NO usar cada estrategia?

Respuesta directa:

●  NO usar MR: Si gap ≥1% o hay catalizador claro (noticia mayor)
●  NO usar TF: Si gap <1% (ruido) o existe noticia que invalide el patrón

20. ¿Qué son las fallas típicas?

Respuesta directa:

●  Aplicar MR en ≥1% (continuación probable)
●  Forzar TF en <1% (ruido/whipsaw)
●
●  Mantener overnight sin plan

Ignorar noticias

ADAPTACIONES Y MERCADOS

21. ¿Cómo adaptar por régimen de mercado?

Respuesta directa:

Alta volatilidad (VIX alto): Reducir tamaño; evitar >3% si no hay claridad Baja volatilidad:
MR más "limpio"; TF exige paciencia Mercado bajista: TF en gap down suele funcionar
mejor; MR en gap up con cautela

Página 6 de 8

22. ¿En qué mercados aplica?

Respuesta directa:

ETFs Índice (SPY, QQQ, IWM): MR: más señales (0.5-<1%); TF: menos pero más potentes
(≥1%) Acciones grandes (S&P 500): Mayor riesgo de news idiosincráticas → clean news
estricta Commodities/FX: Adaptar horarios y ATR; misma lógica MR/TF si hay apertura
consolidada

23. ¿Cómo es la lectura operativa de los datos?

Respuesta directa:

●  MR: Mejor en 0.5-<1%, intradía, con targets 50-75% fill
●  TF: Mejor en ≥1%, con múltiplos del gap o hold 1-3 sesiones si cierra a favor
●  ≥2%: Más direccional pero menos frecuente → gestión de riesgo estricta

24. ¿Qué checklist debo usar pre-trade?

Respuesta directa: □ Gap medido (MR <1% | TF ≥1%) □ Noticias revisadas (clean) □
Trigger técnico definido (máx/mín apertura + cierre 5-15m) □ Stop y target fijados □ Riesgo ≤
1-2% del capital □ Evitar viernes (opcional)

25. ¿Cuál es la conclusión principal?

Respuesta directa: Edge dual y ejecutable:

●  MR: 0.5-<1% (intradía, 50-75% fill)
●  TF: ≥1% (intradía por 1-2× gap o hold 1-3 sesiones)

Reglas binarias, poco filtro, timeframe claro (5-15m) y sin premarket.

Gap Trading deja de ser "opinión" cuando lo mides y separas por tamaño de gap. Este plan
convierte un patrón ambiguo en una metodología.

PUNTOS CLAVE PARA RECORDAR

HACES BIEN SI:

●  Clasificas correctamente MR (<1%) vs TF (≥1%)
●  Esperas siempre el cierre de vela para confirmar ruptura
●  Usas ATR para stops en lugar de porcentajes fijos
●  Registras tipo de estrategia y fill % en tu bitácora
●  Adaptas targets según el tipo (50-75% fill vs múltiplos del gap)

Página 7 de 8

ESTÁS FALLANDO SI:

●  Mezclas las estrategias (MR en gaps >1% o TF en gaps <1%)
●  Entras en la misma vela que rompe (sin esperar cierre)
●
●  Mantenes posiciones overnight sin plan específico
●  Operas gaps <0.5% o >4% (recuerda que gaps >3-4% son estadísticamente poco

Ignoras el filtro de noticias durante la sesión

probables y de muy baja frecuencia)

SEÑALES DE ALERTA:

●  Confundes constantemente cuándo usar MR vs TF
●  No puedes identificar máximo/mínimo de vela de apertura
●  Operas fuera de la ventana 9:45-11:00 AM
●  No calculas ATR para stops
●  Buscas gaps todos los días desesperadamente
●  Te fuerzas a operar sin condiciones ideales (si esto pasa, mejor expande a más

activos o busca estrategias complementarias)

Recuerda: La ventaja está en medir el tamaño del gap y aplicar la lógica correcta. Mean
Reversion para pequeños, Trend Following para grandes.

Página 8 de 8

