//+------------------------------------------------------------------+
//|                                                TestStrategy.mq5  |
//|                   Integration test EA for PerformanceReporter    |
//+------------------------------------------------------------------+
#property copyright "Alphaca Capital"
#property version   "2.11"
#property strict

#include <Trade/Trade.mqh>
#include "PerformanceReporter.mqh"

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "====== BACKEND REPORTER ======"
input string   InpBackendUrl        = "";      // Backend URL (empty = module default)
input string   InpAuthToken         = "";      // Bearer token (empty = module default)
input bool     InpVerboseReporter   = true;    // Reporter debug logs
input int      InpHeartbeatSecs     = 30;      // Heartbeat / trade cycle interval (seconds)
input int      InpMaxBarsNoTrade    = 50;      // Inactivity alert threshold (bars)

input group "====== TEST STRATEGY ======"
input double   InpLotSize           = 0.10;    // Position size (lots)
input int      InpMagicNumber       = 1000001; // Magic Number (unique per EA)
input bool     InpSendPushAlerts    = true;    // Enable push/email alerts
input bool     InpOpenRandomTrades  = true;    // Open random long/short to generate activity

//+------------------------------------------------------------------+
//| Globals                                                           |
//+------------------------------------------------------------------+
CTrade               g_trade;
PerformanceReporter* g_reporter    = NULL;
datetime             g_lastBarTime = 0;

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetDeviationInPoints(10);

   string strategyName = "TestStrategy_" + _Symbol + "_" + EnumToString(Period());

   g_reporter = new PerformanceReporter(
      InpBackendUrl, InpAuthToken,
      strategyName, _Symbol, EnumToString(Period()), 100, "demo"
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

   if(InpSendPushAlerts)
      g_reporter.SendAlert("TEST EA STARTED | " + _Symbol);

   EventSetTimer(InpHeartbeatSecs);
   g_lastBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);

   Print("[INFO] TestStrategy initialized | strategy_id=", g_reporter.GetStrategyId());

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(CheckPointer(g_reporter) == POINTER_INVALID) return;

   g_reporter.ReportHealthAlert("EAStopped",
      StringFormat("TestStrategy stopped. Reason: %d", reason), "medium");

   Print("[INFO] Final stats | Trades: ", g_reporter.GetTotalTrades(),
         " | W: ", g_reporter.GetWins(),
         " | L: ", g_reporter.GetLosses(),
         " | WR: ", DoubleToString(g_reporter.GetWinRate(), 1), "%",
         " | PF: ", DoubleToString(g_reporter.GetProfitFactor(), 2));

   if(InpSendPushAlerts)
      g_reporter.SendAlert("TEST EA STOPPED | Trades: " + IntegerToString(g_reporter.GetTotalTrades()));

   delete g_reporter;
   g_reporter = NULL;
}

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   if(CheckPointer(g_reporter) == POINTER_INVALID) return;

   g_reporter.UpdateEquity();

   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(currentBarTime != g_lastBarTime)
   {
      g_lastBarTime = currentBarTime;
      g_reporter.OnBarUpdate(Bars(_Symbol, PERIOD_CURRENT));
   }
}

//+------------------------------------------------------------------+
//| OnTimer — heartbeat and trade cycle                               |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(CheckPointer(g_reporter) == POINTER_INVALID) return;

   g_reporter.SendHeartbeat();

   if(HasOpenPosition())
   {
      CloseAndReportPosition();
      return;
   }

   if(InpOpenRandomTrades)
      OpenRandomPosition();
}

//+------------------------------------------------------------------+
//| Check if this EA has an open position                             |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Open a random long or short                                       |
//+------------------------------------------------------------------+
void OpenRandomPosition()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask <= 0 || bid <= 0) return;

   bool goLong = (MathRand() % 2 == 0);
   bool success = false;

   if(goLong)
      success = g_trade.Buy(InpLotSize, _Symbol, ask, 0, 0, "TestStrategy|BUY");
   else
      success = g_trade.Sell(InpLotSize, _Symbol, bid, 0, 0, "TestStrategy|SELL");

   if(success)
   {
      Print("[INFO] Opened ", (goLong ? "LONG" : "SHORT"),
            " | ticket=", g_trade.ResultOrder());
   }
   else
   {
      Print("[ERROR] Open failed: ", g_trade.ResultRetcode(), " - ", g_trade.ResultRetcodeDescription());
      g_reporter.OnOrderRejected(goLong ? "OpenBuy" : "OpenSell",
                                  g_trade.ResultRetcode(),
                                  g_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Close the current position and report it                          |
//+------------------------------------------------------------------+
void CloseAndReportPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber) continue;

      double   entryPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double   exitPrice  = PositionGetDouble(POSITION_PRICE_CURRENT);
      double   volume     = PositionGetDouble(POSITION_VOLUME);
      double   commission = PositionGetDouble(POSITION_COMMISSION);
      double   swap       = PositionGetDouble(POSITION_SWAP);
      double   profit     = PositionGetDouble(POSITION_PROFIT) + swap + commission;
      datetime entryTime  = (datetime)PositionGetInteger(POSITION_TIME);
      ENUM_POSITION_TYPE ptype = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

      if(g_trade.PositionClose(ticket))
      {
         Print("[INFO] Closed ticket=", ticket, " | P&L=$", DoubleToString(profit, 2));

         g_reporter.ReportTradeClosed(ticket, _Symbol,
            entryPrice, exitPrice, volume, profit,
            entryTime, TimeCurrent(), commission, ptype);

         if(InpSendPushAlerts)
         {
            string result = (profit >= 0) ? "WIN" : "LOSS";
            g_reporter.SendAlert(StringFormat("%s CLOSE %s | $%.2f | WR=%.0f%% | PF=%.2f",
                                 result, _Symbol, profit,
                                 g_reporter.GetWinRate(), g_reporter.GetProfitFactor()));
         }
      }
      else
      {
         Print("[ERROR] Close failed: ", g_trade.ResultRetcode(), " - ", g_trade.ResultRetcodeDescription());
         g_reporter.OnOrderRejected("ClosePosition",
                                     g_trade.ResultRetcode(),
                                     g_trade.ResultRetcodeDescription());
      }

      break;
   }
}
//+------------------------------------------------------------------+