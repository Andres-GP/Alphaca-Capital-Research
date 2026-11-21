//+------------------------------------------------------------------+
//|                          RSI2_MeanReversion.mq5        |
//|                          Alphaca Capital                          |
//+------------------------------------------------------------------+
//========================================================
//  STATUS: DEMO (ready for forward testing)
//  Version: 3.11  |  Last update: 2026-10-02
//========================================================
#property copyright "Alphaca Capital"
#property version   "3.11"
#property description "RSI(2) MEAN REVERSION - REPORTER INTEGRATED"
#property description "Entry: RSI(2) < 20 + Close > SMA(230)"
#property description "Exit: 2 consecutive green candles"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include "PerformanceReporter.mqh"

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "====== STRATEGY (VALIDATED - DO NOT MODIFY) ======"
input int      InpRSIPeriod       = 2;           // RSI period
input int      InpRSIThreshold    = 20;          // RSI entry threshold
input int      InpSMATrend        = 230;         // SMA trend filter period

input group "====== RISK ENGINE ======"
input double   InpRiskPercent     = 0.33;         // Risk % per trade
input double   InpMaxDailyDD      = 3.0;         // Daily kill switch %
input double   InpMaxTotalDD      = 8.0;         // Total kill switch % (D-Score)
input bool     InpUseATRSizing    = true;        // Position sizing by ATR?
input int      InpATRPeriod       = 14;          // ATR period
input double   InpATRMultiple     = 2.0;         // ATR multiplier (virtual stop)

input group "====== EMERGENCY AND MONITORING ======"
input bool     InpEnableDailyKill  = true;       // Enable daily kill switch?
input bool     InpEnableTotalKill  = true;       // Enable total kill switch?
input bool     InpSendPushAlerts   = true;       // Push/email notifications?
input int      InpMagicNumber      = 100001;     // Magic Number (unique per EA)
input bool     InpShowDashboard    = true;       // Show dashboard on chart?

input group "====== PERFORMANCE REPORTER ======"
input bool     InpEnableReporter   = true;       // Enable backend reporter?
input string   InpBackendUrl       = "";         // Backend URL (empty = module default)
input string   InpAuthToken        = "";         // Required backend API key
input bool     InpVerboseReporter  = false;      // Reporter debug logs
input int      InpHeartbeatSecs    = 3600;       // Heartbeat interval (seconds)
input int      InpMaxBarsNoTrade   = 50;         // Inactivity alert threshold

//+------------------------------------------------------------------+
//| Globals                                                           |
//+------------------------------------------------------------------+
CTrade               g_trade;
CPositionInfo        g_posInfo;
PerformanceReporter* g_reporter = NULL;

int                  g_handleRSI;
int                  g_handleSMA;
int                  g_handleATR;

double               g_rsiBuffer[];
double               g_smaBuffer[];
double               g_atrBuffer[];

datetime             g_lastBarTime;
bool                 g_dailyKillActive;
bool                 g_totalKillActive;
string               g_killReason;

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpRSIThreshold < 5 || InpRSIThreshold > 30)
   {
      Print("RSI Threshold out of reasonable range (5-30)");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpRiskPercent < 0.1 || InpRiskPercent > 5.0)
   {
      Print("Risk % out of safe range (0.1-5.0)");
      return(INIT_PARAMETERS_INCORRECT);
   }

   if(Bars(_Symbol, PERIOD_D1) < InpSMATrend + 10)
   {
      Print("ERROR: insufficient D1 history (", Bars(_Symbol, PERIOD_D1),
            " bars). At least ", InpSMATrend + 10, " required.");
      return(INIT_FAILED);
   }

   g_handleRSI = iRSI(_Symbol, PERIOD_D1, InpRSIPeriod, PRICE_CLOSE);
   g_handleSMA = iMA (_Symbol, PERIOD_D1, InpSMATrend, 0, MODE_SMA, PRICE_CLOSE);
   g_handleATR = iATR(_Symbol, PERIOD_D1, InpATRPeriod);

   if(g_handleRSI == INVALID_HANDLE || g_handleSMA == INVALID_HANDLE || g_handleATR == INVALID_HANDLE)
   {
      Print("Error creating indicators");
      return(INIT_FAILED);
   }

   ArraySetAsSeries(g_rsiBuffer, true);
   ArraySetAsSeries(g_smaBuffer, true);
   ArraySetAsSeries(g_atrBuffer, true);

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(30);

   g_lastBarTime     = 0;
   g_dailyKillActive = false;
   g_totalKillActive = false;
   g_killReason      = "";

   if(InpEnableReporter)
   {
      string strategyName = "TIS_RSI2_" + _Symbol;
      g_reporter = new PerformanceReporter(
         InpBackendUrl, InpAuthToken,
         strategyName, _Symbol, "D1", 100, "demo"
      );

      if(CheckPointer(g_reporter) == POINTER_INVALID)
      {
         Print("[FATAL] Failed to instantiate PerformanceReporter");
         return(INIT_FAILED);
      }

      g_reporter.SetVerbose(InpVerboseReporter);
      g_reporter.SetMaxBarsWithoutTrade(InpMaxBarsNoTrade);

      g_reporter.ReportStrategyStarted();
      g_reporter.ReportCapital(AccountInfoDouble(ACCOUNT_EQUITY),
                               AccountInfoString(ACCOUNT_CURRENCY));

      EventSetTimer(InpHeartbeatSecs);
      Print("Reporter active | strategy_id=", g_reporter.GetStrategyId());
   }

   Print("=== TIS RSI(2) v3.11 ===");
   Print("Symbol: ", _Symbol, " | Magic: ", InpMagicNumber);
   Print("Entry: RSI(", InpRSIPeriod, ") < ", InpRSIThreshold, " + Close > SMA(", InpSMATrend, ")");

   if(g_reporter != NULL && InpSendPushAlerts)
      g_reporter.SendAlert("EA STARTED | " + _Symbol);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_handleRSI != INVALID_HANDLE) IndicatorRelease(g_handleRSI);
   if(g_handleSMA != INVALID_HANDLE) IndicatorRelease(g_handleSMA);
   if(g_handleATR != INVALID_HANDLE) IndicatorRelease(g_handleATR);

   EventKillTimer();
   if(InpShowDashboard) ObjectsDeleteAll(0, "TIS_");

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
//| OnTimer — heartbeat                                               |
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
   if(g_reporter != NULL)
      g_reporter.UpdateEquity();

   bool riskOK = RiskEngine();

   if(riskOK && IsNewBar() && UpdateIndicators())
   {
      if(g_reporter != NULL)
         g_reporter.OnBarUpdate(Bars(_Symbol, PERIOD_D1));

      if(HasOpenPosition()) CheckExit();
      if(!HasOpenPosition()) CheckEntry();
   }

   if(InpShowDashboard)
      UpdateDashboard();
}

//+------------------------------------------------------------------+
//| Risk Engine                                                       |
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
//| Emergency close all                                               |
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
      double   swap       = g_posInfo.Swap();
      double   profit     = g_posInfo.Profit() + swap + commission;
      datetime entryTime  = (datetime)g_posInfo.Time();
      ENUM_POSITION_TYPE ptype = g_posInfo.PositionType();

      if(g_trade.PositionClose(ticket))
      {
         Print("CLOSED [", reason, "]: Ticket #", ticket);
         if(g_reporter != NULL)
            g_reporter.ReportTradeClosed(ticket, _Symbol,
               entryPrice, exitPrice, volume, profit,
               entryTime, TimeCurrent(), commission, ptype, swap);
      }
      else
      {
         Print("Close error: ", g_trade.ResultRetcodeDescription());
         if(g_reporter != NULL)
            g_reporter.OnOrderRejected("EmergencyClose",
               g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
//| CheckEntry                                                        |
//+------------------------------------------------------------------+
void CheckEntry()
{
   double close1 = iClose(_Symbol, PERIOD_D1, 1);

   if(close1 <= g_smaBuffer[1]) return;
   if(g_rsiBuffer[1] >= InpRSIThreshold) return;

   double lots = CalculateLots();
   if(lots <= 0)
   {
      Print("Lot size = 0");
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("ZeroLots", "CalculateLots returned <= 0", "high");
      return;
   }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   string comment = StringFormat("TIS|RSI=%.0f|2GRN", g_rsiBuffer[1]);

   if(g_trade.Buy(lots, _Symbol, ask, 0, 0, comment))
   {
      Print("=== ENTRY LONG | RSI=", DoubleToString(g_rsiBuffer[1], 1),
            " | Lots=", DoubleToString(lots, 2), " @ ", DoubleToString(ask, _Digits));

      if(g_reporter != NULL && InpSendPushAlerts)
         g_reporter.SendAlert(StringFormat("BUY %s | RSI=%.0f | Lots=%.2f",
                              _Symbol, g_rsiBuffer[1], lots));
   }
   else
   {
      Print("BUY FAILED: ", g_trade.ResultRetcodeDescription());
      if(g_reporter != NULL)
         g_reporter.OnOrderRejected("EntryBuy", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| CheckExit — 2 consecutive green candles                           |
//+------------------------------------------------------------------+
void CheckExit()
{
   double close1 = iClose(_Symbol, PERIOD_D1, 1);
   double open1  = iOpen (_Symbol, PERIOD_D1, 1);
   double close2 = iClose(_Symbol, PERIOD_D1, 2);
   double open2  = iOpen (_Symbol, PERIOD_D1, 2);

   if(!((close1 > open1) && (close2 > open2))) return;

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
      double   swap       = g_posInfo.Swap();
      double   profit     = g_posInfo.Profit() + swap + commission;
      datetime entryTime  = (datetime)g_posInfo.Time();

      if(g_trade.PositionClose(ticket))
      {
         if(g_reporter != NULL)
         {
            g_reporter.ReportTradeClosed(ticket, _Symbol,
               entryPrice, exitPrice, volume, profit,
               entryTime, TimeCurrent(), commission, POSITION_TYPE_BUY, swap);

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
//| CalculateLots — ATR-based sizing                                  |
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
            StringFormat("tick_size=%.5f tick_value=%.5f", tickSize, tickValue), "high");
      return lotMin;
   }

   double stopDistance;
   if(InpUseATRSizing && g_atrBuffer[1] > 0)
      stopDistance = g_atrBuffer[1] * InpATRMultiple;
   else
      stopDistance = SymbolInfoDouble(_Symbol, SYMBOL_ASK) * 0.02;

   double stopTicks = stopDistance / tickSize;
   double lots = (stopTicks > 0 && tickValue > 0)
      ? riskAmount / (stopTicks * tickValue)
      : 0;

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
               StringFormat("Lots reduced from %.2f to %.2f", lotsBefore, lots), "medium");
      }
   }

   return lots;
}

//+------------------------------------------------------------------+
//| IsNewBar                                                          |
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
   if(CopyBuffer(g_handleRSI, 0, 0, 5, g_rsiBuffer) < 5) return false;
   if(CopyBuffer(g_handleSMA, 0, 0, 5, g_smaBuffer) < 5) return false;
   if(CopyBuffer(g_handleATR, 0, 0, 5, g_atrBuffer) < 5) return false;
   return true;
}

//+------------------------------------------------------------------+
//| HasOpenPosition                                                   |
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
//| UpdateDashboard                                                   |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   if(ArraySize(g_rsiBuffer) < 2 || ArraySize(g_smaBuffer) < 2) return;

   int x = 20, y = 30, lineH = 18;

   DashLabel("TIS_H1", "TIS RSI(2) v3.11", x, y, clrDodgerBlue, 11);
   y += lineH + 2;
   DashLabel("TIS_H2", _Symbol + " D1 | Exit: 2 Green Candles", x, y, clrDarkGray, 9);
   y += lineH + 6;

   if(g_dailyKillActive || g_totalKillActive)
   {
      DashLabel("TIS_KILL", "KILL SWITCH ACTIVE", x, y, clrRed, 11);
      y += lineH + 4;
   }
   else
   {
      DashLabel("TIS_KILL", "", x, y, clrBlack, 1);
   }

   double rsiVal = g_rsiBuffer[1];
   bool rsiSignal = (rsiVal < InpRSIThreshold);
   DashLabel("TIS_RSI", StringFormat("RSI(2): %.1f %s", rsiVal, rsiSignal ? "<< SIGNAL" : ""),
             x, y, rsiSignal ? clrLime : clrSilver, 10);
   y += lineH;

   double closeNow = iClose(_Symbol, PERIOD_D1, 0);
   bool aboveSMA = (closeNow > g_smaBuffer[0]);
   DashLabel("TIS_TRD", StringFormat("SMA(%d): ", InpSMATrend) + (aboveSMA ? "ABOVE OK" : "BELOW X"),
             x, y, aboveSMA ? clrLime : clrOrangeRed, 10);
   y += lineH;

   double c1 = iClose(_Symbol, PERIOD_D1, 1);
   double o1 = iOpen (_Symbol, PERIOD_D1, 1);
   double c0 = iClose(_Symbol, PERIOD_D1, 0);
   double o0 = iOpen (_Symbol, PERIOD_D1, 0);
   int greens = ((c1 > o1) ? 1 : 0) + ((c0 > o0) ? 1 : 0);

   if(HasOpenPosition())
      DashLabel("TIS_GRN", StringFormat("Green candles: %d/2 %s", greens, greens >= 2 ? "-> EXIT" : ""),
                x, y, greens >= 2 ? clrLime : clrYellow, 10);
   else
      DashLabel("TIS_GRN", "No open position", x, y, clrDarkGray, 9);
   y += lineH + 6;

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
//| DashLabel helper                                                  |
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
//| OnTester                                                          |
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
