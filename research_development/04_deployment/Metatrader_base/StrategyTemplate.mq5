//+------------------------------------------------------------------+
//|                                              StrategyTemplate.mq5|
//|                                              Alphaca Capital     |
//+------------------------------------------------------------------+
//===================================================================
//  TEMPLATE USAGE
//===================================================================
//  1. Copy this file and rename it (e.g., MyStrategy.mq5)
//  2. Update the header block below (name, description, version)
//  3. Fill in the sections marked [STRATEGY-SPECIFIC]:
//       - OnInit        : create indicator handles
//       - UpdateIndicators : copy indicator buffers
//       - CheckEntry    : entry signal logic
//       - CheckExit     : exit signal logic
//       - UpdateDashboard : strategy-specific dashboard lines
//  4. Set a UNIQUE InpMagicNumber (don't collide with other EAs)
//  5. Compile (F7) and test on demo
//
//  Out of the box, this template does NOT trade — CheckEntry and
//  CheckExit return false. All infrastructure (reporter, kill
//  switches, sizing, dashboard) is fully functional so you can
//  validate the pipeline before writing a single line of strategy
//  logic.
//===================================================================
#property copyright "Alphaca Capital"
#property link      "https://www.alphacacapital.com/"
#property version   "1.00"
#property description "Strategy Template - RSI(2)-style infrastructure"
#property description "Copy this file and fill in the STRATEGY-SPECIFIC sections"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include "PerformanceReporter.mqh"

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "====== STRATEGY PARAMETERS ======"
input int      InpFastPeriod      = 10;          // Fast MA period (placeholder)
input int      InpSlowPeriod      = 50;          // Slow MA period (placeholder)
input int      InpTrendPeriod     = 200;         // Trend filter period (placeholder)

input group "====== RISK ENGINE ======"
input double   InpRiskPercent     = 1.0;         // Risk % per trade
input double   InpMaxDailyDD      = 3.0;         // Daily kill switch %
input double   InpMaxTotalDD      = 8.0;         // Total kill switch % (D-Score)
input bool     InpUseATRSizing    = true;        // Position sizing by ATR?
input int      InpATRPeriod       = 14;          // ATR period
input double   InpATRMultiple     = 2.0;         // ATR multiplier (virtual stop)

input group "====== EMERGENCY AND MONITORING ======"
input bool     InpEnableDailyKill  = true;       // Enable daily kill switch?
input bool     InpEnableTotalKill  = true;       // Enable total kill switch?
input bool     InpSendPushAlerts   = true;       // Push/email notifications?
input int      InpMagicNumber      = 100002;     // Magic Number (unique per EA!)
input bool     InpShowDashboard    = true;       // Show dashboard on chart?

input group "====== PERFORMANCE REPORTER ======"
input bool     InpEnableReporter   = true;       // Enable backend reporter?
input string   InpBackendUrl       = "";         // Backend URL (empty = module default)
input string   InpAuthToken        = "";         // Bearer token (empty = module default)
input bool     InpVerboseReporter  = false;      // Reporter debug logs
input int      InpHeartbeatSecs    = 3600;       // Heartbeat interval (seconds)
input int      InpMaxBarsNoTrade   = 50;         // Inactivity alert threshold

//+------------------------------------------------------------------+
//| Globals — infrastructure                                          |
//+------------------------------------------------------------------+
CTrade               g_trade;
CPositionInfo        g_posInfo;
PerformanceReporter* g_reporter = NULL;

datetime             g_lastBarTime;
bool                 g_dailyKillActive;
bool                 g_totalKillActive;
string               g_killReason;

//+------------------------------------------------------------------+
//| Globals — indicators [STRATEGY-SPECIFIC]                          |
//| Replace or extend with the handles and buffers your strategy uses |
//+------------------------------------------------------------------+
int                  g_handleFast;      // Fast MA handle (placeholder)
int                  g_handleSlow;      // Slow MA handle (placeholder)
int                  g_handleTrend;     // Trend filter handle (placeholder)
int                  g_handleATR;       // ATR handle (used by sizing)

double               g_fastBuffer[];    // Fast MA buffer
double               g_slowBuffer[];    // Slow MA buffer
double               g_trendBuffer[];   // Trend MA buffer
double               g_atrBuffer[];     // ATR buffer

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Parameter validation
   if(InpRiskPercent < 0.1 || InpRiskPercent > 5.0)
   {
      Print("Risk % out of safe range (0.1-5.0)");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpFastPeriod >= InpSlowPeriod)
   {
      Print("Fast MA period must be less than slow MA period");
      return(INIT_PARAMETERS_INCORRECT);
   }

   //--- Warm-up check
   int requiredBars = MathMax(InpTrendPeriod, InpSlowPeriod) + 10;
   if(Bars(_Symbol, PERIOD_D1) < requiredBars)
   {
      Print("ERROR: insufficient D1 history (", Bars(_Symbol, PERIOD_D1),
            " bars). At least ", requiredBars, " required.");
      return(INIT_FAILED);
   }

   //--- ==========================================================
   //--- [STRATEGY-SPECIFIC] Create indicator handles
   //--- ==========================================================
   //--- Replace these with the indicators YOUR strategy needs.
   //--- Keep the ATR handle — it's used by the sizing engine.

   g_handleFast  = iMA(_Symbol, PERIOD_D1, InpFastPeriod,  0, MODE_SMA, PRICE_CLOSE);
   g_handleSlow  = iMA(_Symbol, PERIOD_D1, InpSlowPeriod,  0, MODE_SMA, PRICE_CLOSE);
   g_handleTrend = iMA(_Symbol, PERIOD_D1, InpTrendPeriod, 0, MODE_SMA, PRICE_CLOSE);
   g_handleATR   = iATR(_Symbol, PERIOD_D1, InpATRPeriod);

   if(g_handleFast  == INVALID_HANDLE ||
      g_handleSlow  == INVALID_HANDLE ||
      g_handleTrend == INVALID_HANDLE ||
      g_handleATR   == INVALID_HANDLE)
   {
      Print("Error creating indicators");
      return(INIT_FAILED);
   }

   ArraySetAsSeries(g_fastBuffer,  true);
   ArraySetAsSeries(g_slowBuffer,  true);
   ArraySetAsSeries(g_trendBuffer, true);
   ArraySetAsSeries(g_atrBuffer,   true);

   //--- ==========================================================
   //--- Infrastructure setup (do not modify)
   //--- ==========================================================
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(30);

   g_lastBarTime     = 0;
   g_dailyKillActive = false;
   g_totalKillActive = false;
   g_killReason      = "";

   //--- Reporter
   if(InpEnableReporter)
   {
      string strategyName = "Template_" + _Symbol;
      g_reporter = new PerformanceReporter(
         InpBackendUrl, InpAuthToken,
         strategyName, _Symbol, "D1",
         100, "demo"
      );

      if(CheckPointer(g_reporter) == POINTER_INVALID)
      {
         Print("[FATAL] Failed to instantiate PerformanceReporter");
         return(INIT_FAILED);
      }

      g_reporter.SetVerbose(InpVerboseReporter);
      g_reporter.SetMaxBarsWithoutTrade(InpMaxBarsNoTrade);
      g_reporter.EnableInactivityAlert(true);

      g_reporter.ReportStrategyStarted();
      g_reporter.ReportCapital(AccountInfoDouble(ACCOUNT_EQUITY),
                               AccountInfoString(ACCOUNT_CURRENCY));

      EventSetTimer(InpHeartbeatSecs);

      Print("Reporter active | strategy_id=", g_reporter.GetStrategyId());
   }

   //--- Startup log
   Print("=== STRATEGY TEMPLATE v1.00 ===");
   Print("Symbol: ", _Symbol);
   Print("Magic: ", InpMagicNumber);
   Print("Risk: ", DoubleToString(InpRiskPercent, 1), "% per trade | ATRx",
         DoubleToString(InpATRMultiple, 1));
   Print("Kill Daily: ", InpMaxDailyDD, "% | Kill Total: ", InpMaxTotalDD, "%");

   if(g_reporter != NULL && InpSendPushAlerts)
      g_reporter.SendAlert("EA STARTED | " + _Symbol);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   //--- Release indicators
   if(g_handleFast  != INVALID_HANDLE) IndicatorRelease(g_handleFast);
   if(g_handleSlow  != INVALID_HANDLE) IndicatorRelease(g_handleSlow);
   if(g_handleTrend != INVALID_HANDLE) IndicatorRelease(g_handleTrend);
   if(g_handleATR   != INVALID_HANDLE) IndicatorRelease(g_handleATR);

   EventKillTimer();
   if(InpShowDashboard) ObjectsDeleteAll(0, "TIS_");

   //--- Reporter shutdown
   if(g_reporter != NULL)
   {
      g_reporter.ReportHealthAlert("EAStopped",
         StringFormat("EA stopped. Reason: %d", reason), "medium");

      Print("=== EA STOPPED ===");
      Print("Trades: ", g_reporter.GetTotalTrades(),
            " | W: ", g_reporter.GetWins(),
            " | L: ", g_reporter.GetLosses());
      Print("WR: ", DoubleToString(g_reporter.GetWinRate(), 1), "%",
            " | PF: ", DoubleToString(g_reporter.GetProfitFactor(), 2),
            " | MaxDD: ", DoubleToString(g_reporter.GetMaxDrawdownHit(), 2), "%");

      if(InpSendPushAlerts)
         g_reporter.SendAlert("EA STOPPED | Trades: " + IntegerToString(g_reporter.GetTotalTrades()));

      delete g_reporter;
      g_reporter = NULL;
   }
}

//+------------------------------------------------------------------+
//| OnTimer — heartbeat to backend                                    |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(g_reporter != NULL)
      g_reporter.SendHeartbeat();
}

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- Infrastructure: equity monitoring (peak, DD, day change)
   if(g_reporter != NULL)
      g_reporter.UpdateEquity();

   //--- Infrastructure: kill switches (evaluated every tick)
   bool riskOK = RiskEngine();

   //--- Entry/Exit: only on a new D1 bar
   if(riskOK && IsNewBar() && UpdateIndicators())
   {
      if(g_reporter != NULL)
         g_reporter.OnBarUpdate(Bars(_Symbol, PERIOD_D1));

      if(HasOpenPosition())
         CheckExit();

      if(!HasOpenPosition())
         CheckEntry();
   }

   //--- Dashboard
   if(InpShowDashboard)
      UpdateDashboard();
}

//+------------------------------------------------------------------+
//| Risk Engine — kill switches (infrastructure, do not modify)       |
//+------------------------------------------------------------------+
bool RiskEngine()
{
   if(g_reporter == NULL) return true;

   double dailyDD = g_reporter.GetDailyDD();
   double totalDD = g_reporter.GetTotalDD();

   if(InpEnableDailyKill)
   {
      if(dailyDD >= InpMaxDailyDD && !g_dailyKillActive)
      {
         g_dailyKillActive = true;
         g_killReason = StringFormat("DAILY KILL: -%.2f%% (limit %.1f%%)", dailyDD, InpMaxDailyDD);
         Print(g_killReason);
         if(InpSendPushAlerts) g_reporter.SendAlert(g_killReason);
         g_reporter.ReportHealthAlert("KillSwitch", g_killReason, "critical");
         EmergencyCloseAll("Daily Kill");
         return false;
      }
      if(g_dailyKillActive) return false;
   }

   if(InpEnableTotalKill)
   {
      if(totalDD >= InpMaxTotalDD && !g_totalKillActive)
      {
         g_totalKillActive = true;
         g_killReason = StringFormat("TOTAL KILL: -%.2f%% (limit %.1f%%) - EA HALTED",
                                     totalDD, InpMaxTotalDD);
         Print(g_killReason);
         if(InpSendPushAlerts) g_reporter.SendAlert(g_killReason);
         g_reporter.ReportHealthAlert("KillSwitch", g_killReason, "critical");
         EmergencyCloseAll("Total Kill");
         return false;
      }
      if(g_totalKillActive) return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| Close all positions + report each close (infrastructure)          |
//+------------------------------------------------------------------+
void EmergencyCloseAll(string reason)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() != _Symbol) continue;
      if(g_posInfo.Magic() != InpMagicNumber) continue;

      ulong    ticket     = g_posInfo.Ticket();
      double   entryPrice = g_posInfo.PriceOpen();
      double   exitPrice  = g_posInfo.PriceCurrent();
      double   volume     = g_posInfo.Volume();
      double   commission = g_posInfo.Commission();
      double   profit     = g_posInfo.Profit() + g_posInfo.Swap() + commission;
      datetime entryTime  = (datetime)g_posInfo.Time();
      ENUM_POSITION_TYPE ptype = g_posInfo.PositionType();

      if(g_trade.PositionClose(ticket))
      {
         Print("CLOSED [", reason, "]: Ticket #", ticket);
         if(g_reporter != NULL)
         {
            g_reporter.ReportTradeClosed(
               ticket, _Symbol,
               entryPrice, exitPrice, volume,
               profit, entryTime, TimeCurrent(),
               commission, ptype
            );
         }
      }
      else
      {
         Print("Close error: ", g_trade.ResultRetcodeDescription());
         if(g_reporter != NULL)
            g_reporter.OnOrderRejected("EmergencyClose",
                                        g_trade.ResultRetcode(),
                                        g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
//| CheckEntry — entry signal                                         |
//+------------------------------------------------------------------+
void CheckEntry()
{
   //--- ==========================================================
   //--- [STRATEGY-SPECIFIC] ENTRY LOGIC
   //--- ==========================================================
   //--- Replace this section with your strategy's entry conditions.
   //
   //--- Typical structure:
   //---   1. Trend filter check
   //---   2. Entry trigger check
   //---   3. Sanity checks (data valid, buffers populated)
   //---   4. If all pass -> proceed to sizing and order
   //
   //--- Return early (return;) if any condition fails.
   //--- Fall through to the order execution at the bottom.
   //
   //--- The example below is a PLACEHOLDER: long when fast MA is
   //--- above slow MA AND price is above trend MA. Replace entirely.
   //--- ==========================================================

   if(ArraySize(g_fastBuffer) < 2 || ArraySize(g_slowBuffer) < 2 || ArraySize(g_trendBuffer) < 2)
      return;

   double close1 = iClose(_Symbol, PERIOD_D1, 1);

   //--- Trend filter
   if(close1 <= g_trendBuffer[1]) return;

   //--- Entry trigger
   if(g_fastBuffer[1] <= g_slowBuffer[1]) return;

   //--- Optional: signal must differ from previous bar (fresh cross)
   if(g_fastBuffer[2] > g_slowBuffer[2]) return;   // already crossed

   //--- ==========================================================
   //--- Order execution (infrastructure, keep as-is)
   //--- ==========================================================
   double lots = CalculateLots();
   if(lots <= 0)
   {
      Print("Lot size = 0 - insufficient margin or calculation error");
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("ZeroLots", "CalculateLots returned <= 0", "high");
      return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   string comment = "Template|Long";

   if(g_trade.Buy(lots, _Symbol, ask, 0, 0, comment))
   {
      Print("=== ENTRY LONG ===");
      Print("Fast=", DoubleToString(g_fastBuffer[1], 5),
            " Slow=", DoubleToString(g_slowBuffer[1], 5),
            " Trend=", DoubleToString(g_trendBuffer[1], 5));
      Print("ATR=", DoubleToString(g_atrBuffer[1], 5),
            " Lots=", DoubleToString(lots, 2),
            " @ ", DoubleToString(ask, _Digits));

      if(g_reporter != NULL && InpSendPushAlerts)
         g_reporter.SendAlert(StringFormat("BUY %s | Lots=%.2f", _Symbol, lots));
   }
   else
   {
      Print("BUY FAILED: ", g_trade.ResultRetcodeDescription());
      if(g_reporter != NULL)
         g_reporter.OnOrderRejected("EntryBuy", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| CheckExit — exit signal                                           |
//+------------------------------------------------------------------+
void CheckExit()
{
   //--- ==========================================================
   //--- [STRATEGY-SPECIFIC] EXIT LOGIC
   //--- ==========================================================
   //--- Replace this section with your strategy's exit conditions.
   //
   //--- Typical exit types:
   //---   - Trend reversal (MA cross back)
   //---   - Take profit / Stop loss levels
   //---   - Time-based exit (N bars since entry)
   //---   - Signal invalidation (condition that triggered entry fails)
   //
   //--- If the exit condition is met, fall through to close logic.
   //--- Otherwise, return early.
   //
   //--- The example below is a PLACEHOLDER: exit when fast MA
   //--- crosses back below slow MA. Replace entirely.
   //--- ==========================================================

   if(ArraySize(g_fastBuffer) < 3 || ArraySize(g_slowBuffer) < 3)
      return;

   //--- Exit trigger
   if(g_fastBuffer[1] >= g_slowBuffer[1]) return;
   if(g_fastBuffer[2] <= g_slowBuffer[2]) return;   // already crossed

   //--- ==========================================================
   //--- Close logic (infrastructure, keep as-is)
   //--- ==========================================================
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() != _Symbol) continue;
      if(g_posInfo.Magic() != InpMagicNumber) continue;
      if(g_posInfo.PositionType() != POSITION_TYPE_BUY) continue;

      ulong    ticket     = g_posInfo.Ticket();
      double   entryPrice = g_posInfo.PriceOpen();
      double   exitPrice  = g_posInfo.PriceCurrent();
      double   volume     = g_posInfo.Volume();
      double   commission = g_posInfo.Commission();
      double   profit     = g_posInfo.Profit() + g_posInfo.Swap() + commission;
      datetime entryTime  = (datetime)g_posInfo.Time();

      if(g_trade.PositionClose(ticket))
      {
         if(g_reporter != NULL)
         {
            g_reporter.ReportTradeClosed(
               ticket, _Symbol,
               entryPrice, exitPrice, volume,
               profit, entryTime, TimeCurrent(),
               commission, POSITION_TYPE_BUY
            );

            string result = (profit >= 0) ? "WIN" : "LOSS";
            if(InpSendPushAlerts)
               g_reporter.SendAlert(StringFormat("%s EXIT %s | $%.0f | WR=%.0f%% | PF=%.2f",
                                    result, _Symbol, profit,
                                    g_reporter.GetWinRate(), g_reporter.GetProfitFactor()));

            Print("=== EXIT - ", result, " | P&L=$", DoubleToString(profit, 2),
                  " | WR=", DoubleToString(g_reporter.GetWinRate(), 1), "%",
                  " | PF=", DoubleToString(g_reporter.GetProfitFactor(), 2));
         }
      }
      else
      {
         Print("CLOSE FAILED: ", g_trade.ResultRetcodeDescription());
         if(g_reporter != NULL)
            g_reporter.OnOrderRejected("ExitSell", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
//| CalculateLots — ATR-based sizing (infrastructure, do not modify)  |
//+------------------------------------------------------------------+
double CalculateLots()
{
   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * InpRiskPercent / 100.0;

   double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double lotStep    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   if(tickSize == 0 || tickValue == 0)
   {
      Print("Error: Tick size or value = 0");
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("TickDataInvalid",
            StringFormat("tick_size=%.5f tick_value=%.5f", tickSize, tickValue),
            "high");
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

   double marginRequired = 0;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lots,
                     SymbolInfoDouble(_Symbol, SYMBOL_ASK), marginRequired))
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      if(marginRequired > freeMargin * 0.8)
      {
         double reduction = (freeMargin * 0.8) / marginRequired;
         double lotsBefore = lots;
         lots = MathFloor((lots * reduction) / lotStep) * lotStep;
         lots = MathMax(lots, lotMin);
         Print("Margin adjusted - Lots=", DoubleToString(lots, 2));

         if(g_reporter != NULL)
            g_reporter.ReportHealthAlert("ReducedSize",
               StringFormat("Margin insufficient. Lots reduced from %.2f to %.2f", lotsBefore, lots),
               "medium");
      }
   }

   return lots;
}

//+------------------------------------------------------------------+
//| IsNewBar (infrastructure, do not modify)                          |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_D1, 0);

   if(currentBarTime < g_lastBarTime)
   {
      Print("WARNING: timestamp rolled back. Resetting g_lastBarTime.");
      g_lastBarTime = 0;
   }

   if(currentBarTime == g_lastBarTime) return false;

   g_lastBarTime = currentBarTime;
   return true;
}

//+------------------------------------------------------------------+
//| UpdateIndicators                                                  |
//+------------------------------------------------------------------+
bool UpdateIndicators()
{
   //--- ==========================================================
   //--- [STRATEGY-SPECIFIC] Copy indicator buffers
   //--- ==========================================================
   //--- Adjust the handles and buffer sizes to match YOUR indicators.
   //--- Keep the ATR copy — it's used by CalculateLots().

   if(CopyBuffer(g_handleFast,  0, 0, 5, g_fastBuffer)  < 5) return false;
   if(CopyBuffer(g_handleSlow,  0, 0, 5, g_slowBuffer)  < 5) return false;
   if(CopyBuffer(g_handleTrend, 0, 0, 5, g_trendBuffer) < 5) return false;
   if(CopyBuffer(g_handleATR,   0, 0, 5, g_atrBuffer)   < 5) return false;
   return true;
}

//+------------------------------------------------------------------+
//| HasOpenPosition (infrastructure, do not modify)                   |
//+------------------------------------------------------------------+
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

//+------------------------------------------------------------------+
//| UpdateDashboard — infrastructure + strategy-specific lines        |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   if(ArraySize(g_fastBuffer) < 2 || ArraySize(g_slowBuffer) < 2) return;

   int x = 20, y = 30;
   int lineH = 18;

   DashLabel("TIS_H1", "Strategy Template v1.00", x, y, clrDodgerBlue, 11);
   y += lineH + 2;
   DashLabel("TIS_H2", _Symbol + " D1", x, y, clrDarkGray, 9);
   y += lineH + 6;

   //--- Kill switch banner
   if(g_dailyKillActive || g_totalKillActive)
   {
      DashLabel("TIS_KILL", "KILL SWITCH ACTIVE - NOT OPERATING", x, y, clrRed, 11);
      y += lineH + 4;
   }
   else
   {
      DashLabel("TIS_KILL", "", x, y, clrBlack, 1);
   }

   //--- ==========================================================
   //--- [STRATEGY-SPECIFIC] Dashboard lines
   //--- ==========================================================
   //--- Replace with your strategy's key state.
   //--- The example below shows fast/slow MA values and trend filter.

   DashLabel("TIS_FAST", StringFormat("Fast MA: %.5f", g_fastBuffer[1]),
             x, y, clrSilver, 10);
   y += lineH;

   DashLabel("TIS_SLOW", StringFormat("Slow MA: %.5f", g_slowBuffer[1]),
             x, y, clrSilver, 10);
   y += lineH;

   double closeNow = iClose(_Symbol, PERIOD_D1, 0);
   bool aboveTrend = (closeNow > g_trendBuffer[0]);
   DashLabel("TIS_TRD", "Trend: " + (aboveTrend ? "ABOVE OK" : "BELOW X"),
             x, y, aboveTrend ? clrLime : clrOrangeRed, 10);
   y += lineH;

   //--- ==========================================================
   //--- Infrastructure: position + stats (do not modify)
   //--- ==========================================================
   if(HasOpenPosition())
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         if(g_posInfo.SelectByIndex(i) && g_posInfo.Symbol() == _Symbol && g_posInfo.Magic() == InpMagicNumber)
         {
            double pnl = g_posInfo.Profit() + g_posInfo.Swap() + g_posInfo.Commission();
            DashLabel("TIS_POS", StringFormat("LONG %.2f lots | P&L: $%.0f", g_posInfo.Volume(), pnl),
                      x, y, pnl >= 0 ? clrLime : clrOrangeRed, 10);
            break;
         }
      }
   }
   else
   {
      DashLabel("TIS_POS", "FLAT - Waiting for signal", x, y, clrGray, 9);
   }
   y += lineH + 6;

   if(g_reporter != NULL)
   {
      DashLabel("TIS_ST1", StringFormat("Trades: %d | W: %d | L: %d",
                g_reporter.GetTotalTrades(), g_reporter.GetWins(), g_reporter.GetLosses()),
                x, y, clrSilver, 9);
      y += lineH;

      if(g_reporter.GetTotalTrades() > 0)
      {
         double wr = g_reporter.GetWinRate();
         double pf = g_reporter.GetProfitFactor();
         color wrClr = wr >= 60 ? clrLime : (wr >= 50 ? clrYellow : clrOrangeRed);
         DashLabel("TIS_ST2", StringFormat("WR: %.1f%% | PF: %.2f", wr, pf), x, y, wrClr, 9);
         y += lineH;
      }

      double eq = AccountInfoDouble(ACCOUNT_EQUITY);
      DashLabel("TIS_EQ", "Equity: $" + DoubleToString(eq, 0), x, y, clrWhite, 9);
      y += lineH;

      double dailyDD = g_reporter.GetDailyDD();
      double totalDD = g_reporter.GetTotalDD();
      color ddClr = clrSilver;
      if(dailyDD > InpMaxDailyDD * 0.7 || totalDD > InpMaxTotalDD * 0.7) ddClr = clrOrangeRed;
      else if(dailyDD > InpMaxDailyDD * 0.5 || totalDD > InpMaxTotalDD * 0.5) ddClr = clrYellow;

      DashLabel("TIS_DD", StringFormat("DD: Day=%.1f%%/%.0f%% | Total=%.1f%%/%.0f%%",
                dailyDD, InpMaxDailyDD, totalDD, InpMaxTotalDD), x, y, ddClr, 9);
      y += lineH;

      DashLabel("TIS_MDD", StringFormat("Max DD hit: %.2f%%", g_reporter.GetMaxDrawdownHit()),
                x, y, clrDarkGray, 8);
   }
}

//+------------------------------------------------------------------+
//| DashLabel helper (infrastructure, do not modify)                  |
//+------------------------------------------------------------------+
void DashLabel(string name, string text, int x, int y, color clr, int fontSize)
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

//+------------------------------------------------------------------+
//| OnTester (infrastructure, do not modify)                          |
//+------------------------------------------------------------------+
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