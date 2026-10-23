ESTRATEGIA #1 · REVERSIÓN A LA MEDIA · NASDAQ 100

RSI 2 · Connors

Compra el miedo de corto plazo dentro de una tendencia alcista. Y sal en cuanto el
precio respira.

Reversión a la
media

Nasdaq 100 · QQQ /
NDX

Velas diarias

Solo largos

Automatizada · EA MT5

27 años de datos

MOTOR USADO

Sentinel

MÉTODO

TIS

FUENTE DE DATOS

REPLÍCALO TÚ

Darwinex +
Yahoo Finance

Repositorio abierto:
datos, motor y código
→

Números fuera de muestra

7 sep 2018 → 21 sep 2026 · datos que la estrategia nunca vio · 100 % del capital por operación · costes incluidos

2,68

Profit Factor
ganado ÷ perdido

9,2 %

Retorno anual
CAGR

80 %

Aciertos
operaciones ganadoras

93

Operaciones
12 al año · 287 en 27 años

−11,7 %

Peor caída
drawdown día a día

+0,79 %

Por operación
retorno medio neto

■ 100 % del capital (reinvirtiendo)   ■ 10.000 $ fijos por operación (sin reinvertir)   ■ 1 % de riesgo · ATR×2 (el robot)   ■ 2 % de
riesgo · ATR×2   ■ Apalancado 1:2 (200 %)
Curva de capital desde 1999, escala logarítmica. La zona sombreada es el periodo fuera de muestra: la estrategia se diseñó sin ver
esos datos.

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 1

1 · FICHA TÉCNICA

Las reglas, sin letra pequeña

Cuatro reglas y cuatro parámetros. Todo se decide al cierre de la vela diaria y se ejecuta en la apertura del día
siguiente: es lo que puede hacer de verdad un robot, o tú con una orden a la apertura.

Regla 1
FILTRO

Solo con la tendencia de fondo a favor
El cierre del día tiene que estar por encima de la media simple de 200 sesiones. Si no, no hay
operación posible: en mercados bajistas la estrategia se queda fuera.

tendencia_ok = cierre[t] > media_simple(cierre, 200)[t]

Regla 2
ENTRAD
A

Sobreventa extrema de dos días
Si al cierre el RSI de 2 períodos está por debajo de 15 (y el filtro se cumple), compramos en la
apertura del día siguiente.

senal_compra = tendencia_ok y rsi(cierre, 2)[t] < 15
si senal_compra:  comprar en apertura[t+1]

Regla 3
SALIDA

Dos velas verdes seguidas
Cuando el precio encadena dos días con cierre por encima de su apertura, el rebote ya ha
ocurrido. Vendemos en la apertura del día siguiente.

verde[t] = cierre[t] > apertura[t]
senal_venta = verde[t] y verde[t−1]
si senal_venta:  vender en apertura[t+1]

Regla 4
SIN
STOP

No hay stop de precio
La protección es el filtro de tendencia y la duración corta de cada operación (5,1 días de media).
Los stops fijos, en índices, empeoran esta estrategia: Connors lo midió y nosotros también.

stop_loss = ninguno   # el tamaño de posición es la gestión del riesgo (ver sección 5)

TIMEFRAME

ACTIVO

DIRECCIÓN

COSTES

D1
Una vela por sesión. Se
mira una vez al día, al
cierre de Nueva York.

Nasdaq 100
QQQ (ETF) o NDX / US100
(CFD del índice). La señal
es la misma.

Solo largos
Nunca vendemos en corto.
El corto no es el espejo del
largo en índices.

velas = diarias
evaluar_al =
 cierre[t]
ejecutar_en =
 apertura[t+1]

activo = 'QQQ' |
 'NDX'
fuente_backtest =
 QQQ
 diario ajustado

direccion = LONG
posiciones_
 simultaneas = 1

10 bps
En el backtest: 5 puntos
básicos por lado, comisión
0. En Darwinex (QQQ, leído
del terminal el 22 sep
2026): spread 3 puntos ≈
0,4 bps, swap −5,5 %
anual, comisión 0 (incluida
en el spread).

precio_compra =
 apertura × 1,0005
precio_venta =
 apertura × 0,9995

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 2

2 · LA HIPÓTESIS

Por qué debería funcionar

Antes de tocar un dato hay que saber por qué una idea debería ganar. Si no sabes por qué gana, tampoco
sabrás cuándo dejará de hacerlo.

HIPÓTESIS

Cuando un índice en tendencia alcista sufre dos o tres
días de ventas bruscas, el miedo de corto plazo exagera
la caída. El precio tiende a volver a su sitio en pocos
días.

El RSI de 2 períodos mide esa sobreventa de muy corto plazo. La media de 200 días nos dice si la tendencia de
fondo sigue intacta. Compramos solo cuando pasan las dos cosas a la vez, y salimos en cuanto el precio muestra
dos días seguidos de compras. No adivinamos suelos: aprovechamos un comportamiento repetido del mercado.

1

2

3

Qué explota

Por qué existe

Cuándo falla

La reversión a la media de corto plazo
en índices de acciones: tras caídas
rápidas, el rebote es más probable que
la continuación.

Stops que saltan en cadena, gestores
que reducen riesgo a la vez y un miedo
que se agota en dos o tres sesiones.
Después, el flujo comprador de fondo
vuelve.

Cuando la tendencia de fondo se
rompe de verdad (2008, 2022). Por eso
el filtro de la media de 200: por debajo,
la estrategia simplemente no opera.

3 · EL ORIGEN

De dónde viene la idea

No la inventamos nosotros. La publicaron Larry Connors y Cesar Alvarez; nosotros la adaptamos y la validamos
con el método TIS.

Short
Term
Trading
Strategie
s That
Work

Short Term Trading Strategies That
Work (2008)
Larry Connors y Cesar Alvarez. Aquí aparece por
primera vez el RSI de 2 períodos como señal de
sobreventa extrema, con el filtro de la media de 200 y
la salida por la media de 5. → Ver el libro

Lo que cambiamos nosotros

Entrar antes (RSI(2) < 15 en vez de ≤ 5) y salir con
dos velas verdes en vez de al cruzar la media de 5.
Resultado: 287 operaciones frente a 109, capital
final 5,7× frente a 1,9×, con un Profit Factor
parecido. Más oportunidades, misma calidad por
operación.

High Pro
bability
ETF
Trading

High Probability ETF Trading (2009)
Los mismos autores aplican la idea a ETFs con varias
variantes (R3, RSI 25/75, RSI 10/6). → Ver el libro

RSI(2) · C
hartScho
ol

Lecturas gratuitas
La regla original explicada en StockCharts
(ChartSchool) y una revisión moderna con backtests
en QuantifiedStrategies.

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 3

4 · EL CAMINO

Así se ven las operaciones

Las operaciones de un año completo sobre el precio de QQQ. Triángulo verde: compra en la apertura tras la señal. Triángulo rojo:
venta en la apertura tras dos velas verdes. La línea discontinua es la media de 200 días.

Dos operaciones reales del periodo fuera de muestra, vela a vela, con el panel del RSI(2) debajo como lo verías en MetaTrader: la
zona verde es la banda de compra (por debajo de 15). La vela sombreada es la de la señal. Se compra en la apertura siguiente, se
esperan dos velas verdes seguidas y se vende en la apertura posterior. El porcentaje es el movimiento del precio; en el título se
traduce a lo que supone para el capital con cada tamaño.

El RSI 2 tradicional frente al nuestro

La regla del libro entra con RSI(2) ≤ 5 y sale al cerrar por encima de la media de 5. La nuestra entra antes (RSI < 15) y
sale con dos velas verdes. Mismos datos, mismos costes, mismo filtro, mismo periodo completo (1999–2026).

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 4

5 · RIESGO Y TAMAÑO

La misma señal, cuatro formas de
apostar

La señal es una. Lo que cambia es cuánto capital pones en cada operación. Elige por tu perfil, no por la cifra
más grande: las cuatro curvas tienen exactamente las mismas operaciones.

Conservador
1 % de riesgo por operación · lo que hace el robot

Intermedio
2 % de riesgo por operación

2,7 %

5,3 %

retorno anual fuera de muestra

retorno anual fuera de muestra

Peor caída

−4,7 %

Peor caída

Capital final · 27 años

1,78×

Capital final · 27 años

Capital en juego (media)

37 %

Capital en juego (media)

−9,2 %

2,98×

72 %

Cortacircuitos

−3 % día · −8 %

Cómo

doble riesgo

Decidido
100 % del capital en cada operación

9,2 %

retorno anual fuera de muestra

Arriesgado
apalancamiento 1:2 · 200 % del capital

17,8 %

retorno anual fuera de muestra

Peor caída

−11,7 %

Peor caída

Capital final · 27 años

5,74×

Capital final · 27 años

Capital en juego

Cómo

100 %

Capital en juego

sin apalancar

Peor caída histórica

−22,9 %

28,28×

200 % (CFD)

−33,5 %

Sobre el nivel arriesgado: solo es posible con CFD (el ETF no se apalanca). Duplica el retorno y duplica las caídas: la peor
histórica pasa del −17,7 % al −33,5 %, y encima pagas swap por el doble de nominal. Si no aguantas ver un tercio del capital
desaparecer sin cambiar nada, no es tu nivel.

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 5

Las cuatro curvas con las mismas operaciones. Abajo, la caída desde máximos de cada una. Escala logarítmica: la misma distancia
vertical es el mismo porcentaje.

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 6

Qué calcula el ATR

El rango verdadero de un día es lo más grande de tres cosas: la altura de la vela (máximo – mínimo), la distancia del
máximo al cierre anterior, o la del mínimo al cierre anterior. Así cuenta también los huecos de apertura. El ATR(14) es la
media de los últimos 14 rangos: cuánto se mueve el activo en un día normal.

A la izquierda, las 14 velas anteriores a la última señal del backtest; la barra naranja junto a cada vela es su rango verdadero
(incluye el hueco respecto al cierre anterior cuando lo hay). A la derecha, esos 14 rangos y su media: el ATR.

Cómo se aplica el ATR (lo que hace el robot antes de cada compra)

El robot no pone un stop en el mercado: usa un stop virtual a 2 × ATR solo para calcular cuántas unidades comprar, de
forma que si el precio cayera esa distancia perderías el 1 % del capital. Ejemplo con la última operación real del backtest
y 10.000 € de capital:

PASO 1 · RIESGO

PASO 2 · STOP VIRTUAL

PASO 3 · UNIDADES

PASO 4 · POSICIÓN

10.000 € × 1 %

2 × ATR(14) = 2 × 9,01

100 € ÷ 18,01 $

5,6 × 716,04 $

100 €

18,01 $

5,6

3.975 €

Lo máximo que aceptas
perder si el precio recorre
el stop virtual.

Distancia de precio que
equivale a “la operación ha
salido mal”.

Acciones de QQQ (o
contratos equivalentes del
CFD).

El 40 % del capital en esta
operación. Con más
volatilidad, menos.

Si el precio cae más de 2 × ATR, el robot no cierra: sigue esperando las dos velas verdes. El stop es virtual porque, medido, cerrar
por precio empeora la estrategia. En 27 años, con este tamaño, la peor caída fue del −6,7 % y los cortacircuitos del −8 % nunca
habrían saltado.

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 7

6 · DÓNDE OPERARLA

Qué necesitas y cómo es un día

Pensada para el Nasdaq 100 en velas diarias. Da igual si lo operas como ETF (QQQ) o como CFD del índice (NDX
/ US100): la señal es la misma. Tres formas de hacerlo, de más a menos automática.

RECOMENDADA

SEMIAUTOMÁTICA

MANUAL

Con el robot
(cid:127) MetaTrader 5 con un bróker que
ofrezca el Nasdaq 100 como CFD
en gráfico diario.

(cid:127) Nuestra referencia: Darwinex

sobre NDX, en un servidor 24/7.
Lo hace todo: señal, tamaño por
ATR, cortacircuitos y avisos al
móvil.

Con alertas de
TradingView
(cid:127) El indicador en Pine Script marca

la señal y te avisa al cierre.

(cid:127) Tú pones la orden de compra a la
apertura en tu bróker (ETF o CFD).
Ideal si no quieres un servidor
pero sí disciplina.

A mano, cinco minutos
al día
(cid:127) Al cierre miras dos números:

¿cierre por encima de la SMA 200?
¿RSI(2) por debajo de 15?
(cid:127) Si sí, orden de compra a la
apertura del día siguiente.

(cid:127) Cada tarde compruebas si hubo

dos velas verdes.

(cid:127) Solo recomendable si estás

aprendiendo y quieres entender
la ejecución. Recuerda que tu
objetivo es escalar y despegarte
de la pantalla.

Un día en la vida de la estrategia

Cierre de Nueva
York

22:00 h en España

¿Cierre > SMA
200?

si no, no hay nada que
hacer

¿RSI(2) < 15?

sobreventa extrema

Compra a la
apertura

15:30 h del día siguiente

Dos velas verdes →
vendes

a la apertura siguiente ·
5,1 días de media

ETF o CFD: lo que cambia

QQQ (ETF)
(cid:127) Cobra dividendos (el backtest los incluye).
(cid:127) Sin swap nocturno; comisión del bróker por operación.
(cid:127) Sin apalancamiento: el nivel “Decidido” es el máximo.

NDX / US100 (CFD)
(cid:127) No paga dividendos; el bróker cobra swap por cada

noche en posición.

(cid:127) Con 5,1 días de media por operación el efecto es

pequeño, pero existe.

(cid:127) Permite apalancar: no lo hagas por encima del nivel que

elegiste.

Lo que cuesta un CFD, de media, en Darwinex (specs del QQQ leídas del terminal el 22 sep 2026): spread 3 puntos ≈ 0,4 bps
por operación · swap −5,5 % anual ≈ 1,5 bps por noche, que con 5,1 noches de media son 7,7 bps · comisión 0 (incluida en el
spread). Total medio: ≈ 8 bps por operación, frente a los 10 bps que asume el backtest. El CFD del índice (NDX) tiene el mismo
swap anual; su spread lo ves en tu terminal.

Comprobado en el instrumento real: mismo motor, mismas reglas, sobre las velas diarias del propio bróker para el CFD del
Nasdaq 100 (2009–2026): 67 operaciones fuera de muestra, Profit Factor 3,95, peor caída −8,7 %.

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 8

(cid:127)
(cid:127)
7 · CÓDIGO

La señal en 12 líneas

Python · lo que hace el motor por dentro

sma200 = close.rolling(200).mean()
rsi2   = rsi_wilder(close, 2)
verde  = close > open                      # vela verde: cierra por encima de su apertura

for i in range(2, len(df)):
    if not en_posicion:
        if rsi2[i-1] < 15 and close[i-1] > sma200[i-1]:      # señal al cierre de ayer
            precio_entrada = open[i] * (1 + 0.0005)           # compra en la apertura de hoy
            en_posicion = True
    else:
        if verde[i-1] and verde[i-2]:                         # dos velas verdes seguidas
            precio_salida = open[i] * (1 - 0.0005)            # venta en la apertura de hoy
            en_posicion = False

Expert Advisor completo · MetaTrader 5

TIS_RSI2_MeanReversion_FINAL.mq5 · v2.01 · MQL5 · Darwinex

//+------------------------------------------------------------------+
//|                          TIS_RSI2_MeanReversion_FINAL.mq5        |
//|                          Trade It Simple SENTINEL 2026            |
//|                          Fondo Sistematico Multiestrategia        |
//+------------------------------------------------------------------+
//========================================================
//  STATUS: LIVE (desplegado en producción)
// Entorno: MetaTrader 5 / Darwinex | ejecución automatizada
//  Version: 2.01  |  Last update: 2026-06-24
//========================================================
#property copyright "Trade It Simple 2026"
#property link      "https://www.tradeitsimplesolutions.com/"
#property version   "2.01"
#property description "RSI(2) MEAN REVERSION - VERSION DEFINITIVA"
#property description "Entry: RSI(2) < 15 + Close > SMA(200)"
#property description "Exit: 2 velas verdes consecutivas"
#property description "Risk Engine + Darwinex Zero Ready"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

input group "====== ESTRATEGIA (VALIDADO - NO MODIFICAR) ======"
input int      InpRSIPeriod       = 2;           // Periodo RSI
input int      InpRSIThreshold    = 15;          // Umbral RSI entrada
input int      InpSMATrend        = 200;         // SMA Filtro de Tendencia

input group "====== MOTOR DE RIESGO ======"
input double   InpRiskPercent     = 1.0;         // % Riesgo por operacion
input double   InpMaxDailyDD      = 3.0;         // Kill switch diario %
input double   InpMaxTotalDD      = 8.0;         // Kill switch total % (D-Score)
input bool     InpUseATRSizing    = true;        // Position sizing por ATR?
input int      InpATRPeriod       = 14;          // Periodo ATR
input double   InpATRMultiple     = 2.0;         // Multiplicador ATR (virtual stop)

input group "====== EMERGENCIA Y MONITOREO ======"
input bool     InpEnableDailyKill  = true;       // Activar kill switch diario?
input bool     InpEnableTotalKill  = true;       // Activar kill switch total?
input bool     InpSendPushAlerts   = true;       // Notificaciones push?
input bool     InpSendEmailAlerts  = false;      // Alertas email?
input int      InpMagicNumber      = 100001;     // Magic Number (unico por EA)
input bool     InpShowDashboard    = true;       // Dashboard en chart?

CTrade         g_trade;
CPositionInfo  g_posInfo;

int            g_handleRSI;
int            g_handleSMA;
int            g_handleATR;

double         g_rsiBuffer[];
double         g_smaBuffer[];
double         g_atrBuffer[];

double         g_dayStartEquity;
double         g_peakEquity;
datetime       g_lastBarTime;
bool           g_dailyKillActive;
bool           g_totalKillActive;
string         g_killReason;

int            g_totalTrades;
int            g_wins;

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 9

int            g_losses;
double         g_grossProfit;
double         g_grossLoss;
double         g_maxDrawdownHit;

int OnInit()
{
   if(InpRSIThreshold < 5 || InpRSIThreshold > 30)
   {
      Print("RSI Threshold fuera de rango razonable (5-30)");
      return(INIT_PARAMETERS_INCORRECT);
   }

   if(InpRiskPercent < 0.1 || InpRiskPercent > 5.0)
   {
      Print("Risk % fuera de rango seguro (0.1-5.0)");
      return(INIT_PARAMETERS_INCORRECT);
   }

   g_handleRSI = iRSI(_Symbol, PERIOD_D1, InpRSIPeriod, PRICE_CLOSE);
   g_handleSMA = iMA(_Symbol, PERIOD_D1, InpSMATrend, 0, MODE_SMA, PRICE_CLOSE);
   g_handleATR = iATR(_Symbol, PERIOD_D1, InpATRPeriod);

   if(g_handleRSI == INVALID_HANDLE || g_handleSMA == INVALID_HANDLE || g_handleATR == INVALID_HANDLE)
   {
      Print("Error creando indicadores");
      return(INIT_FAILED);
   }

   ArraySetAsSeries(g_rsiBuffer, true);
   ArraySetAsSeries(g_smaBuffer, true);
   ArraySetAsSeries(g_atrBuffer, true);

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(30);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);

   g_dayStartEquity  = AccountInfoDouble(ACCOUNT_EQUITY);
   g_peakEquity      = AccountInfoDouble(ACCOUNT_EQUITY);
   g_lastBarTime     = 0;
   g_dailyKillActive = false;
   g_totalKillActive = false;
   g_killReason      = "";
   g_maxDrawdownHit  = 0;

   g_totalTrades = 0;
   g_wins        = 0;
   g_losses      = 0;
   g_grossProfit = 0;
   g_grossLoss   = 0;

   Print("=== TIS RSI(2) MEAN REVERSION FINAL ===");
   Print("Simbolo: ", _Symbol);
   Print("Entrada: RSI(", InpRSIPeriod, ") < ", InpRSIThreshold, " + Close > SMA(", InpSMATrend, ")");
   Print("Salida: 2 Velas Verdes Consecutivas");
   Print("Riesgo: ", DoubleToString(InpRiskPercent, 1), "% por trade | ATRx", DoubleToString(InpATRMultiple, 1));
   Print("Kill Daily: ", InpMaxDailyDD, "% | Kill Total: ", InpMaxTotalDD, "%");
   Print("Magic: ", InpMagicNumber);

   Alert_TIS("EA INICIADO | " + _Symbol + " | RSI(" + IntegerToString(InpRSIPeriod) + ")<" +
             IntegerToString(InpRSIThreshold) + " | Exit: 2 Velas Verdes");

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(g_handleRSI != INVALID_HANDLE) IndicatorRelease(g_handleRSI);
   if(g_handleSMA != INVALID_HANDLE) IndicatorRelease(g_handleSMA);
   if(g_handleATR != INVALID_HANDLE) IndicatorRelease(g_handleATR);

   if(InpShowDashboard) ObjectsDeleteAll(0, "TIS_");

   Print("=== EA DETENIDO ===");
   Print("Trades: ", g_totalTrades, " | Wins: ", g_wins, " | Losses: ", g_losses);
   if(g_totalTrades > 0)
   {
      double wr = (double)g_wins / g_totalTrades * 100;
      Print("Win Rate: ", DoubleToString(wr, 1), "%");
      if(g_grossLoss > 0)
         Print("Profit Factor: ", DoubleToString(g_grossProfit / g_grossLoss, 2));
      Print("Max DD Hit: ", DoubleToString(g_maxDrawdownHit, 2), "%");
   }

   Alert_TIS("EA DETENIDO | Trades: " + IntegerToString(g_totalTrades) +
             " | W:" + IntegerToString(g_wins) + " L:" + IntegerToString(g_losses));
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//| FIX v2.01: El dashboard ahora se refresca en CADA tick para que |
//| refleje la posicion real en vivo. La logica de entrada/salida    |
//| sigue evaluandose solo al abrir una nueva vela diaria (sin cambio)|
//+------------------------------------------------------------------+
void OnTick()
{
   // El motor de riesgo (kill switch) se evalua en cada tick

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 10

   bool riskOK = RiskEngine();

   // Entrada/Salida: solo en vela diaria nueva (comportamiento original)
   if(riskOK && IsNewBar() && UpdateIndicators())
   {
      if(HasOpenPosition())
         CheckExit();

      if(!HasOpenPosition())
         CheckEntry();
   }

   // Dashboard: SIEMPRE, para reflejar la posicion real intradia
   if(InpShowDashboard)
      UpdateDashboard();
}

bool RiskEngine()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   if(equity > g_peakEquity)
      g_peakEquity = equity;

   MqlDateTime dt;
   TimeCurrent(dt);
   static int lastDay = -1;

   if(dt.day != lastDay)
   {
      lastDay = dt.day;
      g_dayStartEquity  = AccountInfoDouble(ACCOUNT_EQUITY);
      g_dailyKillActive = false;
      if(StringFind(g_killReason, "DIARIO") >= 0)
         g_killReason = "";
   }

   if(InpEnableDailyKill && g_dayStartEquity > 0)
   {
      double dailyDD = (g_dayStartEquity - equity) / g_dayStartEquity * 100.0;

      if(dailyDD >= InpMaxDailyDD && !g_dailyKillActive)
      {
         g_dailyKillActive = true;
         g_killReason = StringFormat("KILL DIARIO: -%.2f%% (limite %.1f%%)", dailyDD, InpMaxDailyDD);
         Print(g_killReason);
         Alert_TIS(g_killReason);
         EmergencyCloseAll("Kill Diario");
         return false;
      }

      if(g_dailyKillActive)
         return false;
   }

   if(InpEnableTotalKill && g_peakEquity > 0)
   {
      double totalDD = (g_peakEquity - equity) / g_peakEquity * 100.0;

      if(totalDD > g_maxDrawdownHit)
         g_maxDrawdownHit = totalDD;

      if(totalDD >= InpMaxTotalDD && !g_totalKillActive)
      {
         g_totalKillActive = true;
         g_killReason = StringFormat("KILL TOTAL: -%.2f%% (limite %.1f%%) - EA DETENIDO", totalDD, InpMaxTotalDD);
         Print(g_killReason);
         Alert_TIS(g_killReason);
         EmergencyCloseAll("Kill Total");
         return false;
      }

      if(g_totalKillActive)
         return false;
   }

   return true;
}

void EmergencyCloseAll(string reason)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(g_posInfo.SelectByIndex(i))
      {
         if(g_posInfo.Symbol() == _Symbol && g_posInfo.Magic() == InpMagicNumber)
         {
            if(g_trade.PositionClose(g_posInfo.Ticket()))
               Print("CERRADA [", reason, "]: Ticket #", g_posInfo.Ticket());
            else
               Print("Error cerrando: ", g_trade.ResultRetcodeDescription());
         }
      }
   }
}

void CheckEntry()

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 11

{
   double close1 = iClose(_Symbol, PERIOD_D1, 1);

   if(close1 <= g_smaBuffer[1])
      return;

   if(g_rsiBuffer[1] >= InpRSIThreshold)
      return;

   double lots = CalculateLots();
   if(lots <= 0)
   {
      Print("Lot size = 0 - insuficiente margen o error calculo");
      return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   string comment = StringFormat("TIS|RSI=%.0f|2GRN", g_rsiBuffer[1]);

   if(g_trade.Buy(lots, _Symbol, ask, 0, 0, comment))
   {
      g_totalTrades++;

      Print("=== ENTRY LONG - Trade #", g_totalTrades, " ===");
      Print("RSI(2) = ", DoubleToString(g_rsiBuffer[1], 1), " < ", InpRSIThreshold);
      Print("Close  = ", DoubleToString(close1, 2), " > SMA(200) = ", DoubleToString(g_smaBuffer[1], 2));
      Print("ATR    = ", DoubleToString(g_atrBuffer[1], 2));
      Print("Lots   = ", DoubleToString(lots, 2), " @ ", DoubleToString(ask, 2));
      Print("Exit: Esperando 2 velas verdes consecutivas");

      Alert_TIS(StringFormat("BUY %s | RSI=%.0f | Lots=%.2f | Esperando 2 velas verdes",
                _Symbol, g_rsiBuffer[1], lots));
   }
   else
   {
      Print("BUY FAILED: ", g_trade.ResultRetcodeDescription());
   }
}

void CheckExit()
{
   double close1 = iClose(_Symbol, PERIOD_D1, 1);
   double open1  = iOpen(_Symbol, PERIOD_D1, 1);
   double close2 = iClose(_Symbol, PERIOD_D1, 2);
   double open2  = iOpen(_Symbol, PERIOD_D1, 2);

   bool bar1_green = (close1 > open1);
   bool bar2_green = (close2 > open2);

   if(bar1_green && bar2_green)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(!g_posInfo.SelectByIndex(i)) continue;
         if(g_posInfo.Symbol() != _Symbol) continue;
         if(g_posInfo.Magic() != InpMagicNumber) continue;
         if(g_posInfo.PositionType() != POSITION_TYPE_BUY) continue;

         double profit = g_posInfo.Profit() + g_posInfo.Swap() + g_posInfo.Commission();

         if(g_trade.PositionClose(g_posInfo.Ticket()))
         {
            if(profit >= 0)
            {
               g_wins++;
               g_grossProfit += profit;
            }
            else
            {
               g_losses++;
               g_grossLoss += MathAbs(profit);
            }

            double wr = g_totalTrades > 0 ? (double)g_wins / g_totalTrades * 100.0 : 0;
            double pf = g_grossLoss > 0 ? g_grossProfit / g_grossLoss : 99.99;
            string result = profit >= 0 ? "WIN" : "LOSS";

            Print("=== EXIT - 2 Velas Verdes - ", result, " ===");
            Print("P&L: $", DoubleToString(profit, 2));
            Print("Stats: ", g_wins, "W / ", g_losses, "L");
            Print("WR: ", DoubleToString(wr, 1), "% | PF: ", DoubleToString(pf, 2));

            Alert_TIS(StringFormat("%s EXIT %s | $%.0f | WR=%.0f%% | PF=%.2f | #%d",
                      result, _Symbol, profit, wr, pf, g_totalTrades));
         }
         else
         {
            Print("CLOSE FAILED: ", g_trade.ResultRetcodeDescription());
         }
      }
   }
}

double CalculateLots()
{
   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * InpRiskPercent / 100.0;

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 12

   double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double lotStep    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   if(tickSize == 0 || tickValue == 0)
   {
      Print("Error: Tick size o value = 0");
      return lotMin;
   }

   double stopDistance;
   if(InpUseATRSizing && g_atrBuffer[1] > 0)
      stopDistance = g_atrBuffer[1] * InpATRMultiple;
   else
      stopDistance = SymbolInfoDouble(_Symbol, SYMBOL_ASK) * 0.02;

   double stopTicks = stopDistance / tickSize;
   double lots = 0;

   if(stopTicks > 0 && tickValue > 0)
      lots = riskAmount / (stopTicks * tickValue);

   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(lots, lotMin);
   lots = MathMin(lots, lotMax);

   double marginRequired;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lots, SymbolInfoDouble(_Symbol, SYMBOL_ASK), marginRequired))
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      if(marginRequired > freeMargin * 0.8)
      {
         double reduction = (freeMargin * 0.8) / marginRequired;
         lots = MathFloor((lots * reduction) / lotStep) * lotStep;
         lots = MathMax(lots, lotMin);
         Print("Margen ajustado - Lots=", DoubleToString(lots, 2));
      }
   }

   return lots;
}

bool IsNewBar()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_D1, 0);
   if(currentBarTime == g_lastBarTime)
      return false;
   g_lastBarTime = currentBarTime;
   return true;
}

bool UpdateIndicators()
{
   if(CopyBuffer(g_handleRSI, 0, 0, 5, g_rsiBuffer) < 5) return false;
   if(CopyBuffer(g_handleSMA, 0, 0, 5, g_smaBuffer) < 5) return false;
   if(CopyBuffer(g_handleATR, 0, 0, 5, g_atrBuffer) < 5) return false;
   return true;
}

bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(g_posInfo.SelectByIndex(i))
         if(g_posInfo.Symbol() == _Symbol && g_posInfo.Magic() == InpMagicNumber)
            return true;
   }
   return false;
}

int CountPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(g_posInfo.SelectByIndex(i))
         if(g_posInfo.Symbol() == _Symbol && g_posInfo.Magic() == InpMagicNumber)
            count++;
   }
   return count;
}

void Alert_TIS(string message)
{
   if(InpSendPushAlerts)  SendNotification(message);
   if(InpSendEmailAlerts) SendMail("TIS RSI2 FINAL", message);
}

void UpdateDashboard()
{
   // FIX v2.01: proteccion: no dibujar hasta que los indicadores tengan datos
   if(ArraySize(g_rsiBuffer) < 2 || ArraySize(g_smaBuffer) < 2) return;

   int x = 20, y = 30;
   int lineH = 18;

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 13

   DashLabel("TIS_H1", "TIS RSI(2) FINAL v2.01", x, y, clrDodgerBlue, 11);
   y += lineH + 2;
   DashLabel("TIS_H2", _Symbol + " D1 | Exit: 2 Velas Verdes", x, y, clrDarkGray, 9);
   y += lineH + 6;

   if(g_dailyKillActive || g_totalKillActive)
   {
      DashLabel("TIS_KILL", "KILL SWITCH ACTIVO - NO OPERA", x, y, clrRed, 11);
      y += lineH + 4;
   }
   else
   {
      DashLabel("TIS_KILL", "", x, y, clrBlack, 1);
   }

   double rsiVal = g_rsiBuffer[1];
   bool rsiSignal = (rsiVal < InpRSIThreshold);
   string rsiStr = StringFormat("RSI(2): %.1f %s", rsiVal, rsiSignal ? "<< SENAL" : "");
   DashLabel("TIS_RSI", rsiStr, x, y, rsiSignal ? clrLime : clrSilver, 10);
   y += lineH;

   double closeNow = iClose(_Symbol, PERIOD_D1, 0);
   bool aboveSMA = (closeNow > g_smaBuffer[0]);
   DashLabel("TIS_TRD", "SMA(200): " + (aboveSMA ? "ABOVE OK" : "BELOW X"),
             x, y, aboveSMA ? clrLime : clrOrangeRed, 10);
   y += lineH;

   double c1 = iClose(_Symbol, PERIOD_D1, 1);
   double o1 = iOpen(_Symbol, PERIOD_D1, 1);
   double c0 = iClose(_Symbol, PERIOD_D1, 0);
   double o0 = iOpen(_Symbol, PERIOD_D1, 0);
   int greens = 0;
   if(c1 > o1) greens++;
   if(c0 > o0) greens++;

   if(HasOpenPosition())
   {
      DashLabel("TIS_GRN", StringFormat("Velas verdes: %d/2 %s", greens, greens >= 2 ? "-> EXIT" : ""),
                x, y, greens >= 2 ? clrLime : clrYellow, 10);
   }
   else
   {
      DashLabel("TIS_GRN", "Sin posicion abierta", x, y, clrDarkGray, 9);
   }
   y += lineH + 6;

   if(HasOpenPosition())
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(g_posInfo.SelectByIndex(i) && g_posInfo.Symbol() == _Symbol && g_posInfo.Magic() == InpMagicNumber)
         {
            double pnl = g_posInfo.Profit() + g_posInfo.Swap() + g_posInfo.Commission();
            color pnlClr = pnl >= 0 ? clrLime : clrOrangeRed;
            DashLabel("TIS_POS", StringFormat("LONG %.2f lots | P&L: $%.0f", g_posInfo.Volume(), pnl),
                      x, y, pnlClr, 10);
            break;
         }
      }
   }
   else
   {
      DashLabel("TIS_POS", "FLAT - Esperando senal", x, y, clrGray, 9);
   }
   y += lineH + 6;

   DashLabel("TIS_ST1", StringFormat("Trades: %d | W: %d | L: %d",
             g_totalTrades, g_wins, g_losses), x, y, clrSilver, 9);
   y += lineH;

   if(g_totalTrades > 0)
   {
      double wr = (double)g_wins / g_totalTrades * 100;
      double pf = g_grossLoss > 0 ? g_grossProfit / g_grossLoss : 0;
      color wrClr = wr >= 60 ? clrLime : (wr >= 50 ? clrYellow : clrOrangeRed);
      DashLabel("TIS_ST2", StringFormat("WR: %.1f%% | PF: %.2f", wr, pf), x, y, wrClr, 9);
      y += lineH;
   }

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double dailyDD = g_dayStartEquity > 0 ? (g_dayStartEquity - eq) / g_dayStartEquity * 100 : 0;
   double totalDD = g_peakEquity > 0 ? (g_peakEquity - eq) / g_peakEquity * 100 : 0;

   DashLabel("TIS_EQ", "Equity: $" + DoubleToString(eq, 0), x, y, clrWhite, 9);
   y += lineH;

   color ddClr = clrSilver;
   if(dailyDD > InpMaxDailyDD * 0.7 || totalDD > InpMaxTotalDD * 0.7) ddClr = clrOrangeRed;
   else if(dailyDD > InpMaxDailyDD * 0.5 || totalDD > InpMaxTotalDD * 0.5) ddClr = clrYellow;

   DashLabel("TIS_DD", StringFormat("DD: Day=%.1f%%/%.0f%% | Total=%.1f%%/%.0f%%",
             dailyDD, InpMaxDailyDD, totalDD, InpMaxTotalDD), x, y, ddClr, 9);
   y += lineH;

   DashLabel("TIS_MDD", StringFormat("Max DD hit: %.2f%%", g_maxDrawdownHit), x, y, clrDarkGray, 8);
}
void DashLabel(string name, string text, int x, int y, color clr, int fontSize)

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 14

{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   }
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
}

double OnTester()
{
   double profit = TesterStatistics(STAT_PROFIT);
   double maxDD  = TesterStatistics(STAT_EQUITY_DD_RELATIVE);
   int    trades = (int)TesterStatistics(STAT_TRADES);

   if(maxDD == 0) return 0;

   double score = profit / maxDD;

   if(trades < 20)
      score *= (double)trades / 20.0;

   return score;
}

Trade It Simple · Estrategia #1 · RSI 2 · Connors

Pág. 15

