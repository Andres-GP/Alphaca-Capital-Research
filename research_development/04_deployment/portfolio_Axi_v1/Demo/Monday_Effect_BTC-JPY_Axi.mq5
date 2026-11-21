//+------------------------------------------------------------------+
//|                          Monday_Effect_BTCJPY.mq5                 |
//|                          Alphaca Capital                          |
//+------------------------------------------------------------------+
//========================================================
//  STATUS: IN DEVELOPMENT (demo forward testing)
//          NOT validated: the BTCJPY plateau / walk-forward gates
//          failed on ~1 year of in-sample data.
//  Strategy ID : MONDAY.btcjpy.cfd.v1
//  Vehicle     : Axi BTCJPY CFD (long only, H1)
//  Version: 1.01  |  Last update: 2026-10-25
//
//  v1.01 changes vs v1.00:
//   - Kill switches no longer depend on the reporter (own equity tracking)
//   - Time exit / kill close is retried on every tick until the position is closed
//   - Entry requires the Sunday 23:00 signal bar to exist (engine parity)
//   - Closed-trade P&L, prices, swap and commission are read from the deal history
//   - monday_log.csv (every Monday decision) and monday_trades.csv (every closed trade)
//     written to the Common/Files folder for reconciliation with the Python engine
//========================================================
#property copyright "Alphaca Capital"
#property version   "1.01"
#property description "MONDAY EFFECT - BTCJPY CFD (AXI) - REPORTER INTEGRATED"
#property description "Entry: Monday 00:00 UTC if ATR(24)% >= 40th percentile of last 8760 H1 bars"
#property description "Filter: skip first Monday of the month | Exit: 24 H1 bars later (Tuesday 00:00 UTC)"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include "PerformanceReporter.mqh"
#include "PerformanceDashboard.mqh"

//+------------------------------------------------------------------+
//| Enums                                                             |
//+------------------------------------------------------------------+
enum ENUM_SERVER_TZ
{
   TZ_GMT2_GMT3_US_DST = 0,   // GMT+2 winter / GMT+3 US summer (Axi, IC Markets, Pepperstone...)
   TZ_FIXED_OFFSET     = 1    // Fixed offset vs UTC (see InpFixedOffsetUTC)
};

enum ENUM_ATR_METHOD
{
   ATR_SMA    = 0,            // Simple mean of TR (engine default, = MT5 iATR)
   ATR_WILDER = 1             // Wilder RMA (= TradingView ta.atr)
};

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "====== STRATEGY (FROZEN PARAMETERS - DO NOT MODIFY) ======"
input int             InpATRPeriod       = 24;           // ATR period (H1 bars)
input ENUM_ATR_METHOD InpATRMethod       = ATR_SMA;      // ATR method (must match research engine atr_method)
input double          InpATRPercentile   = 40.0;         // Min ATR% percentile to trade (atr_pctl)
input int             InpPctlWindow      = 8760;         // Percentile window in H1 bars (1 year)
input int             InpMinBarsPctl     = 4380;         // Min valid bars for the percentile (pctl_min_bars)
input bool            InpSkipFirstMonday = true;         // Skip first Monday of the month (day 1-7)
input int             InpHoldHours       = 24;           // Time exit: H1 bars after the entry bar

input group "====== EXECUTION / BROKER TIME ======"
input ENUM_SERVER_TZ  InpServerTZ        = TZ_GMT2_GMT3_US_DST; // Broker server time
input int             InpFixedOffsetUTC  = 0;            // Only with fixed offset: hours server is ahead of UTC
input double          InpMaxSpreadBps    = 30.0;         // Skip entry if spread > x bps (research assumes 5.5 bps/side)
input double          InpMaxSlippageBps  = 20.0;         // Max slippage on market orders (bps of price)
input int             InpMaxEntryDelayMin= 15;           // Skip entry if first tick of the Monday bar arrives later than x min

input group "====== RISK ENGINE ======"
input double          InpFractionCapital = 0.20;         // Fraction of equity per trade (0.20 = 20%, unleveraged)
input double          InpMaxDailyDD      = 5.0;          // Daily kill switch %
input double          InpMaxTotalDD      = 8.5;          // Total kill switch % (hard limit 9%)

input group "====== EMERGENCY AND MONITORING ======"
input bool            InpEnableDailyKill = true;         // Enable daily kill switch?
input bool            InpEnableTotalKill = true;         // Enable total kill switch?
input bool            InpSendPushAlerts  = true;         // Push/email notifications?
input int             InpMagicNumber     = 290401;       // Magic Number (unique per EA)
input bool            InpShowDashboard   = true;         // Show dashboard on chart?
input bool            InpLogFiles        = true;         // Write monday_log.csv / monday_trades.csv (Common/Files)?

input group "====== PERFORMANCE REPORTER ======"
input bool            InpEnableReporter  = true;         // Enable backend reporter?
input string          InpBackendUrl      = "";           // Backend URL (empty = module default)
input string          InpAuthToken       = "";           // Required backend API key
input bool            InpVerboseReporter = false;        // Reporter debug logs
input int             InpHeartbeatSecs   = 3600;         // Heartbeat interval (seconds)
input int             InpMaxBarsNoTrade  = 720;          // Inactivity alert threshold (H1 bars, ~4 weeks)

//+------------------------------------------------------------------+
//| Globals                                                           |
//+------------------------------------------------------------------+
CTrade               g_trade;
CPositionInfo        g_posInfo;
PerformanceReporter* g_reporter = NULL;
PerformanceDashboard g_dashboard;

datetime             g_lastBarTime;
bool                 g_dailyKillActive;
bool                 g_totalKillActive;
string               g_killReason;

// own equity tracking (kill switches do NOT depend on the reporter)
double               g_peakEquity;
double               g_dayStartEquity;
int                  g_dayKey;
double               g_maxDDHit;

// filter cache (refreshed once per new H1 bar)
bool                 g_filterOK;        // filter could be computed (enough history)
double               g_atrPct;          // ATR% of last closed bar
double               g_atrRank;         // share of window strictly below g_atrPct (0..1)
bool                 g_atrPermit;       // g_atrRank >= InpATRPercentile/100

//+------------------------------------------------------------------+
//| Server time -> UTC                                                |
//+------------------------------------------------------------------+
// n-th Sunday of a month (00:00 of that day)
datetime NthSunday(int year, int month, int n)
{
   MqlDateTime d; ZeroMemory(d);
   d.year = year; d.mon = month; d.day = 1;
   datetime first = StructToTime(d);
   MqlDateTime f; TimeToStruct(first, f);
   int add = (7 - f.day_of_week) % 7;
   return first + (add + 7 * (n - 1)) * 86400;
}

// US DST: 2nd Sunday of March (07:00 UTC) to 1st Sunday of November (06:00 UTC)
bool IsUSSummer(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc, u);
   datetime ini = NthSunday(u.year, 3, 2)  + 7 * 3600;
   datetime fin = NthSunday(u.year, 11, 1) + 6 * 3600;
   return (utc >= ini && utc < fin);
}

int ServerOffsetHours(datetime server)
{
   if(InpServerTZ == TZ_FIXED_OFFSET) return InpFixedOffsetUTC;
   return IsUSSummer(server - 2 * 3600) ? 3 : 2;
}

datetime ServerToUTC(datetime server) { return server - ServerOffsetHours(server) * 3600; }

// "YYYY-MM-DD HH:MM" in UTC from a server timestamp
string UtcStr(datetime server)
{
   MqlDateTime t;
   TimeToStruct(ServerToUTC(server), t);
   return StringFormat("%04d-%02d-%02d %02d:%02d", t.year, t.mon, t.day, t.hour, t.min);
}

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   if(PeriodSeconds(_Period) != 3600)
   {
      Print("ERROR: this EA must run on an H1 chart");
      return(INIT_FAILED);
   }
   if(InpFractionCapital < 0.01 || InpFractionCapital > 1.0)
   {
      Print("Fraction of capital out of range (0.01-1.0)");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpATRPercentile < 0.0 || InpATRPercentile > 100.0)
   {
      Print("ATR percentile out of range (0-100)");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpATRPeriod < 2 || InpHoldHours < 1 || InpPctlWindow < InpMinBarsPctl)
   {
      Print("Invalid ATR / hold / percentile window parameters");
      return(INIT_PARAMETERS_INCORRECT);
   }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   g_lastBarTime     = 0;
   g_dailyKillActive = false;
   g_totalKillActive = false;
   g_killReason      = "";
   g_filterOK        = false;
   g_atrPct          = 0;
   g_atrRank         = -1;
   g_atrPermit       = false;

   double eq0        = AccountInfoDouble(ACCOUNT_EQUITY);
   g_peakEquity      = eq0;
   g_dayStartEquity  = eq0;
   g_dayKey          = DayKeyOf(TimeCurrent());
   g_maxDDHit        = 0;

   // live/demo: verify configured broker time matches the real server time
   if(!MQLInfoInteger(MQL_TESTER))
   {
      int real = (int)MathRound((double)(TimeTradeServer() - TimeGMT()) / 3600.0);
      int conf = ServerOffsetHours(TimeTradeServer());
      if(real != conf)
         Alert(StringFormat("ALPHACA Monday: server is UTC%+d but EA is configured for UTC%+d. Check InpServerTZ / InpFixedOffsetUTC.",
                            real, conf));
      else
         PrintFormat("Broker time OK (server = UTC%+d)", real);
   }

   if(InpEnableReporter)
   {
      string strategyName = "ALPHACA_MONDAY_" + _Symbol;
      g_reporter = new PerformanceReporter(
         InpBackendUrl, InpAuthToken,
         strategyName, _Symbol, "H1", 100, "demo"
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
   else
      Print("Reporter disabled (kill switches still active: they use the EA's own equity tracking)");

   Print("=== ALPHACA MONDAY EFFECT v1.01 ===");
   Print("Symbol: ", _Symbol, " | Magic: ", InpMagicNumber);
   PrintFormat("Entry: Mon 00:00 UTC | ATR(%d)%% >= P%.0f of %d bars | skip 1st Monday: %s | hold %dh | size %.0f%%",
               InpATRPeriod, InpATRPercentile, InpPctlWindow, InpSkipFirstMonday ? "yes" : "no",
               InpHoldHours, InpFractionCapital * 100.0);

   // capital needed so that the minimum lot does not exceed the target fraction
   double npl = NotionalPerLot(SymbolInfoDouble(_Symbol, SYMBOL_ASK));
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(npl > 0)
      PrintFormat("Notional per lot: %.2f %s | min lot %.4f | min equity for %.0f%% sizing: %.0f %s",
                  npl, AccountInfoString(ACCOUNT_CURRENCY), minLot, InpFractionCapital * 100.0,
                  minLot * npl / InpFractionCapital, AccountInfoString(ACCOUNT_CURRENCY));

   PushAlert("EA STARTED | " + _Symbol);

   if(InpShowDashboard) UpdateDashboard();

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(InpShowDashboard) ObjectsDeleteAll(0, "ALPHACA_");

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
            " | MaxDD: ", DoubleToString(g_maxDDHit, 2), "%");

      PushAlert("EA STOPPED | Trades: " + IntegerToString(g_reporter.GetTotalTrades()));

      delete g_reporter;
      g_reporter = NULL;
   }
}

//+------------------------------------------------------------------+
//| OnTimer - heartbeat                                               |
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

   UpdateRiskState();
   bool riskOK = RiskEngine();

   CheckExit();                          // ALWAYS runs: time exit, and retry of any failed close (also under a kill)
   bool newBar = IsNewBar();

   if(riskOK && newBar)
   {
      if(g_reporter != NULL)
         g_reporter.OnBarUpdate(Bars(_Symbol, PERIOD_H1));

      RefreshFilter();
      if(!HasOpenPosition()) CheckEntry();
   }

   if(InpShowDashboard)
      UpdateDashboard();
}

//+------------------------------------------------------------------+
//| Alerts                                                            |
//+------------------------------------------------------------------+
void PushAlert(string msg)
{
   if(!InpSendPushAlerts) return;
   if(g_reporter != NULL) g_reporter.SendAlert(msg);
   else                   SendNotification(msg);
}

//+------------------------------------------------------------------+
//| Own risk tracking (does not depend on the reporter)               |
//+------------------------------------------------------------------+
int DayKeyOf(datetime dt)
{
   MqlDateTime s;
   TimeToStruct(dt, s);
   return s.year * 10000 + s.mon * 100 + s.day;
}

double DailyDD()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_dayStartEquity <= 0) return 0.0;
   return (g_dayStartEquity - eq) / g_dayStartEquity * 100.0;
}

double TotalDD()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_peakEquity <= 0) return 0.0;
   return (g_peakEquity - eq) / g_peakEquity * 100.0;
}

void UpdateRiskState()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq > g_peakEquity) g_peakEquity = eq;

   int key = DayKeyOf(TimeCurrent());
   if(key != g_dayKey)
   {
      g_dayKey         = key;
      g_dayStartEquity = eq;
      if(g_dailyKillActive)
      {
         g_dailyKillActive = false;
         Print("Daily kill switch reset (new day)");
      }
   }

   double dd = TotalDD();
   if(dd > g_maxDDHit) g_maxDDHit = dd;
}

//+------------------------------------------------------------------+
//| Risk Engine                                                       |
//|   returns false while a kill switch is active                     |
//|   (total kill stays until the EA is re-attached)                  |
//+------------------------------------------------------------------+
bool RiskEngine()
{
   double dailyDD = DailyDD();
   double totalDD = TotalDD();

   if(InpEnableDailyKill)
   {
      if(!g_dailyKillActive && dailyDD >= InpMaxDailyDD)
      {
         g_dailyKillActive = true;
         g_killReason = StringFormat("DAILY KILL: -%.2f%% (limit %.1f%%)", dailyDD, InpMaxDailyDD);
         Print(g_killReason);
         PushAlert(g_killReason);
         if(g_reporter != NULL) g_reporter.ReportHealthAlert("KillSwitch", g_killReason, "critical");
         EmergencyCloseAll("Daily Kill");
      }
      if(g_dailyKillActive) return false;
   }

   if(InpEnableTotalKill)
   {
      if(!g_totalKillActive && totalDD >= InpMaxTotalDD)
      {
         g_totalKillActive = true;
         g_killReason = StringFormat("TOTAL KILL: -%.2f%% (limit %.1f%%) - EA HALTED",
                                     totalDD, InpMaxTotalDD);
         Print(g_killReason);
         PushAlert(g_killReason);
         if(g_reporter != NULL) g_reporter.ReportHealthAlert("KillSwitch", g_killReason, "critical");
         EmergencyCloseAll("Total Kill");
      }
      if(g_totalKillActive) return false;
   }

   return true;
}

//+------------------------------------------------------------------+
//| File logs (Common/Files) for reconciliation with the Python engine|
//+------------------------------------------------------------------+
// one line per Monday 00:00 UTC bar, whether the EA trades or not
void LogMonday(string decision, string reason)
{
   if(!InpLogFiles) return;
   int h = FileOpen("monday_log.csv", FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ';');
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, UtcStr(iTime(_Symbol, PERIOD_H1, 0)),
             DoubleToString(g_atrPct, 6), DoubleToString(g_atrRank, 6), decision, reason);
   FileClose(h);
}

// one line per closed trade (times in UTC)
void LogTrade(string reason, double lots, double entryPrice, double exitPrice, double profit,
              double swap, double commission, datetime entryTime, datetime exitTime, bool fromDeals)
{
   if(!InpLogFiles) return;
   int h = FileOpen("monday_trades.csv", FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ';');
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, UtcStr(entryTime), UtcStr(exitTime),
             DoubleToString(entryPrice, _Digits), DoubleToString(exitPrice, _Digits),
             DoubleToString(lots, 2), DoubleToString(profit, 2),
             DoubleToString(swap, 2), DoubleToString(commission, 2),
             reason, fromDeals ? "deal" : "estimate");
   FileClose(h);
}

//+------------------------------------------------------------------+
//| Real numbers of a closed position from the deal history           |
//+------------------------------------------------------------------+
bool GetClosedDealInfo(long posId, double &entryPrice, double &exitPrice, double &volume,
                       double &netProfit, double &commission, double &swap,
                       datetime &entryTime, datetime &exitTime)
{
   if(!HistorySelectByPosition((ulong)posId)) return false;
   int n = HistoryDealsTotal();
   if(n < 2) return false;

   double   ep = 0, xp = 0, vol = 0, net = 0, com = 0, sw = 0;
   datetime et = 0, xt = 0;
   bool     gotIn = false, gotOut = false;

   for(int k = 0; k < n; k++)
   {
      ulong tk = HistoryDealGetTicket(k);
      if(tk == 0) continue;

      long   entryType = HistoryDealGetInteger(tk, DEAL_ENTRY);
      double dcom      = HistoryDealGetDouble(tk, DEAL_COMMISSION);
      double dsw       = HistoryDealGetDouble(tk, DEAL_SWAP);

      net += HistoryDealGetDouble(tk, DEAL_PROFIT) + dsw + dcom + HistoryDealGetDouble(tk, DEAL_FEE);
      com += dcom;
      sw  += dsw;

      if(entryType == DEAL_ENTRY_IN)
      {
         ep    = HistoryDealGetDouble(tk, DEAL_PRICE);
         et    = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
         vol   = HistoryDealGetDouble(tk, DEAL_VOLUME);
         gotIn = true;
      }
      else if(entryType == DEAL_ENTRY_OUT || entryType == DEAL_ENTRY_OUT_BY)
      {
         xp     = HistoryDealGetDouble(tk, DEAL_PRICE);
         xt     = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
         gotOut = true;
      }
   }

   if(!(gotIn && gotOut)) return false;

   entryPrice = ep;  exitPrice  = xp;  volume = vol;
   netProfit  = net; commission = com; swap   = sw;
   entryTime  = et;  exitTime   = xt;
   return true;
}

//+------------------------------------------------------------------+
//| Close + report (shared by time exit and kill switches)            |
//+------------------------------------------------------------------+
void CloseAllAndReport(string reason)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() != _Symbol) continue;
      if(g_posInfo.Magic() != InpMagicNumber) continue;

      ulong  ticket = g_posInfo.Ticket();
      long   posId  = g_posInfo.Identifier();
      ENUM_POSITION_TYPE ptype = g_posInfo.PositionType();

      // estimates (used only if the deal history is not available yet)
      double   entryPrice = g_posInfo.PriceOpen();
      double   exitPrice  = g_posInfo.PriceCurrent();
      double   volume     = g_posInfo.Volume();
      double   commission = g_posInfo.Commission();
      double   swap       = g_posInfo.Swap();
      double   profit     = g_posInfo.Profit() + swap + commission;
      datetime entryTime  = (datetime)g_posInfo.Time();
      datetime exitTime   = TimeCurrent();

      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double spreadBps = (bid > 0) ? (ask - bid) / bid * 1e4 : 0;

      if(g_trade.PositionClose(ticket))
      {
         bool fromDeals = GetClosedDealInfo(posId, entryPrice, exitPrice, volume, profit,
                                            commission, swap, entryTime, exitTime);

         string result = (profit >= 0) ? "WIN" : "LOSS";
         Print("=== CLOSED [", reason, "] #", ticket, " | ", result,
               " | P&L=", DoubleToString(profit, 2), " ", AccountInfoString(ACCOUNT_CURRENCY),
               " | swap=", DoubleToString(swap, 2),
               " | exit spread=", DoubleToString(spreadBps, 1), " bps",
               fromDeals ? " | (from deals)" : " | (estimate: deals not available yet)");

         LogTrade(reason, volume, entryPrice, exitPrice, profit, swap, commission,
                  entryTime, exitTime, fromDeals);

         if(g_reporter != NULL)
         {
            g_reporter.ReportTradeClosed(ticket, _Symbol,
               entryPrice, exitPrice, volume, profit,
               entryTime, exitTime, commission, ptype, swap);

            PushAlert(StringFormat("%s EXIT %s | %.0f | WR=%.0f%% | PF=%.2f",
                                   result, _Symbol, profit,
                                   g_reporter.GetWinRate(), g_reporter.GetProfitFactor()));
         }
      }
      else
      {
         Print("CLOSE FAILED [", reason, "]: ", g_trade.ResultRetcodeDescription(), " (will retry on the next tick)");
         if(g_reporter != NULL)
            g_reporter.OnOrderRejected("Close:" + reason,
               g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
}

void EmergencyCloseAll(string reason)
{
   CloseAllAndReport(reason);
}

//+------------------------------------------------------------------+
//| CheckExit - time exit: HoldHours after the entry bar              |
//|   Runs on EVERY tick. If a close fails it is retried next tick,   |
//|   and under an active kill switch any open position is closed.    |
//+------------------------------------------------------------------+
void CheckExit()
{
   datetime opened = 0;
   if(!GetPositionOpenTime(opened)) return;

   if(g_dailyKillActive || g_totalKillActive)
   {
      CloseAllAndReport("Kill switch (retry)");
      return;
   }

   datetime barNow   = iTime(_Symbol, PERIOD_H1, 0);
   datetime entryBar = (datetime)((long)opened - (long)opened % 3600);

   // if the exact bar is missing, closes on the next available one instead of waiting a week
   if(barNow >= entryBar + (datetime)InpHoldHours * 3600)
      CloseAllAndReport("Time exit Tue 00:00 UTC");
}

//+------------------------------------------------------------------+
//| CheckEntry                                                        |
//+------------------------------------------------------------------+
void CheckEntry()
{
   datetime barTime = iTime(_Symbol, PERIOD_H1, 0);
   if(barTime == 0) return;

   MqlDateTime t;
   TimeToStruct(ServerToUTC(barTime), t);
   bool monday00 = (t.day_of_week == 1 && t.hour == 0);
   if(!monday00) return;

   // engine parity: the Sunday 23:00 signal bar must exist (exactly 1 h before)
   if(iTime(_Symbol, PERIOD_H1, 1) != barTime - 3600)
   {
      Print("No trade: Sunday 23:00 signal bar is missing");
      LogMonday("SKIP", "no signal bar");
      return;
   }

   if(InpSkipFirstMonday && t.day <= 7)
   {
      Print("No trade: first Monday of the month");
      LogMonday("SKIP", "first monday");
      return;
   }

   if(!g_filterOK)
   {
      Print("No trade: not enough H1 history for the percentile (sync history / check InpMinBarsPctl)");
      LogMonday("SKIP", "no history");
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("NoHistory", "ATR percentile could not be computed", "high");
      return;
   }
   if(!g_atrPermit)
   {
      PrintFormat("No trade: ATR%% %.3f = percentile %.1f (< %.0f)",
                  g_atrPct, g_atrRank * 100.0, InpATRPercentile);
      LogMonday("SKIP", "atr low");
      return;
   }

   if((TimeCurrent() - barTime) > InpMaxEntryDelayMin * 60)
   {
      PrintFormat("No trade: first tick of the Monday bar arrived %d s late", (int)(TimeCurrent() - barTime));
      LogMonday("SKIP", "late entry");
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("LateEntry", "Monday bar first tick too late, entry skipped", "medium");
      return;
   }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0)
   {
      LogMonday("SKIP", "no quote");
      return;
   }
   double spreadBps = (ask - bid) / bid * 1e4;
   if(spreadBps > InpMaxSpreadBps)
   {
      PrintFormat("No trade: spread %.1f bps > limit %.1f bps", spreadBps, InpMaxSpreadBps);
      LogMonday("SKIP", "wide spread");
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("WideSpread",
            StringFormat("spread=%.1f bps limit=%.1f bps", spreadBps, InpMaxSpreadBps), "high");
      return;
   }

   double lots = CalculateLots();
   if(lots <= 0)
   {
      LogMonday("SKIP", "zero lots");
      return;
   }

   // slippage tolerance expressed in bps of price, converted to points
   ulong dev = (ulong)MathMax(1.0, MathRound(ask * InpMaxSlippageBps / 1e4 / _Point));
   g_trade.SetDeviationInPoints(dev);

   string comment = StringFormat("ALPHACA|MON|ATR=%.3f|P=%.0f", g_atrPct, g_atrRank * 100.0);
   string signalId = "";
   if(g_reporter != NULL)
      signalId = g_reporter.ReportSignalIntent("entry", _Symbol, "long", ask, lots);

   if(g_trade.Buy(lots, _Symbol, 0, 0, 0, comment))
   {
      if(g_reporter != NULL)
      {
         uint rc = g_trade.ResultRetcode();
         g_reporter.ReportExecutionUpdate(signalId,
            rc == TRADE_RETCODE_DONE_PARTIAL ? "partial" : rc == TRADE_RETCODE_PLACED ? "submitted" : "filled",
            g_trade.ResultVolume(), g_trade.ResultPrice());
      }
      LogMonday("BUY", "ok");
      Print("=== ENTRY LONG | ATR%=", DoubleToString(g_atrPct, 3),
            " | P=", DoubleToString(g_atrRank * 100.0, 1),
            " | Lots=", DoubleToString(lots, 2), " @ ", DoubleToString(ask, _Digits),
            " | entry spread=", DoubleToString(spreadBps, 1), " bps");

      PushAlert(StringFormat("BUY %s | ATR=%.3f P%.0f | Lots=%.2f | spread %.1f bps",
                             _Symbol, g_atrPct, g_atrRank * 100.0, lots, spreadBps));
   }
   else
   {
      Print("BUY FAILED: ", g_trade.ResultRetcodeDescription());
      LogMonday("SKIP", "buy failed");
      if(g_reporter != NULL)
      {
         g_reporter.ReportExecutionUpdate(signalId, "rejected", 0, 0, g_trade.ResultRetcodeDescription());
         g_reporter.OnOrderRejected("EntryBuy", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
//| Volatility filter (parity with monday_effect_engine.prepare)      |
//|   ATR% = ATR(len) / close * 100 on the last CLOSED H1 bar         |
//|   rank = share of the last InpPctlWindow ATR% values (signal bar  |
//|          included) strictly below the signal ATR%                 |
//|   permit = rank >= InpATRPercentile / 100                         |
//+------------------------------------------------------------------+
void RefreshFilter()
{
   g_filterOK  = ComputeFilter(g_atrPct, g_atrRank);
   g_atrPermit = g_filterOK && (g_atrRank >= InpATRPercentile / 100.0);
}

bool ComputeFilter(double &atrPct, double &rank)
{
   atrPct = 0; rank = -1;

   int want = InpPctlWindow + 1000;                       // extra bars so a Wilder RMA converges
   MqlRates r[];
   ArraySetAsSeries(r, false);                            // r[0] = oldest
   int got = CopyRates(_Symbol, PERIOD_H1, 1, want, r);   // from the last CLOSED bar backwards
   if(got < InpATRPeriod + InpMinBarsPctl) return false;

   double ap[], tr[];
   ArrayResize(ap, got);
   ArrayResize(tr, got);

   double rma = 0, sum = 0;
   for(int i = 0; i < got; i++)
   {
      double x = r[i].high - r[i].low;
      if(i > 0)
         x = MathMax(x, MathMax(MathAbs(r[i].high - r[i-1].close), MathAbs(r[i].low - r[i-1].close)));
      tr[i] = x;

      if(InpATRMethod == ATR_SMA)
      {
         sum += x;
         if(i >= InpATRPeriod) sum -= tr[i - InpATRPeriod];
         ap[i] = (i >= InpATRPeriod - 1) ? (sum / InpATRPeriod) / r[i].close * 100.0 : -1.0;
      }
      else
      {
         rma   = (i == 0) ? x : rma + (x - rma) / InpATRPeriod;   // pandas ewm(alpha=1/n, adjust=False)
         ap[i] = (i >= InpATRPeriod - 1) ? rma / r[i].close * 100.0 : -1.0;
      }
   }

   atrPct = ap[got - 1];
   int from = MathMax(InpATRPeriod - 1, got - InpPctlWindow);
   int n = 0, below = 0;
   for(int i = from; i < got; i++)
   {
      n++;
      if(ap[i] < atrPct) below++;
   }
   if(n < InpMinBarsPctl) return false;

   rank = (double)below / n;
   return true;
}

//+------------------------------------------------------------------+
//| Sizing - fixed fraction of equity, unleveraged                    |
//+------------------------------------------------------------------+
// notional of 1 lot in ACCOUNT currency (handles JPY-quoted CFD on a USD account via tick value)
double NotionalPerLot(double price)
{
   if(price <= 0) return 0;

   // 1) OrderCalcProfit: profit in ACCOUNT currency of 1 lot for a small up-move.
   //    Works even if the broker exposes tick size / tick value as 0 (Axi BTC-JPY shows 0 in the spec).
   double delta  = price * 0.0001;
   double profit = 0;
   if(OrderCalcProfit(ORDER_TYPE_BUY, _Symbol, 1.0, price, NormalizeDouble(price + delta, _Digits), profit) && profit > 0)
   {
      double realDelta = NormalizeDouble(price + delta, _Digits) - price;
      if(realDelta > 0) return price / realDelta * profit;
   }

   // 2) fallback: tick data
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0) return 0;
   return price / tickSize * tickValue;
}

double CalculateLots()
{
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   double ask     = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   double npl = NotionalPerLot(ask);
   if(npl <= 0 || lotStep <= 0)
   {
      Print("Error: tick size/value or lot step invalid - no trade");
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("TickDataInvalid", "Cannot compute notional per lot", "high");
      return 0;
   }

   double target = equity * InpFractionCapital;
   int    digs   = (int)MathMax(0, MathCeil(-MathLog10(lotStep)));
   double lots   = MathFloor(target / npl / lotStep + 1e-9) * lotStep;
   lots = NormalizeDouble(MathMin(lots, lotMax), digs);

   // never force the minimum lot: it would exceed the validated fraction
   if(lots < lotMin)
   {
      PrintFormat("No trade: %.0f%% of equity (%.2f) does not reach the min lot %.4f (needs equity >= %.0f)",
                  InpFractionCapital * 100.0, target, lotMin, lotMin * npl / InpFractionCapital);
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("ZeroLots",
            StringFormat("Equity too small for min lot. Needs %.0f", lotMin * npl / InpFractionCapital), "high");
      return 0;
   }

   double marginRequired = 0;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lots, ask, marginRequired))
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      if(marginRequired > freeMargin * 0.8)
      {
         double lotsBefore = lots;
         lots = NormalizeDouble(MathFloor(lots * (freeMargin * 0.8 / marginRequired) / lotStep) * lotStep, digs);
         Print("Margin adjusted - Lots=", DoubleToString(lots, 2));
         if(g_reporter != NULL)
            g_reporter.ReportHealthAlert("ReducedSize",
               StringFormat("Lots reduced from %.2f to %.2f", lotsBefore, lots), "medium");
         if(lots < lotMin) return 0;
      }
   }

   return lots;
}

//+------------------------------------------------------------------+
//| IsNewBar                                                          |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_H1, 0);

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
//| Position helpers                                                  |
//+------------------------------------------------------------------+
bool GetPositionOpenTime(datetime &opened)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(g_posInfo.SelectByIndex(i))
         if(g_posInfo.Symbol() == _Symbol && g_posInfo.Magic() == InpMagicNumber)
         {
            opened = (datetime)g_posInfo.Time();
            return true;
         }
   }
   return false;
}

bool HasOpenPosition()
{
   datetime tmp;
   return GetPositionOpenTime(tmp);
}

//+------------------------------------------------------------------+
//| UpdateDashboard                                                   |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   string state = (g_dailyKillActive || g_totalKillActive) ? "KILL SWITCH ACTIVE" : "STRATEGY ACTIVE";
   color stateColor = (g_dailyKillActive || g_totalKillActive) ? clrOrangeRed : clrLime;
   string reporterState = !InpEnableReporter ? "Reporter: OFF" : StringLen(InpAuthToken) == 0 ? "Reporter: ON | API key missing" : "Reporter: ON | credentials configured";
   string atr = g_filterOK
      ? StringFormat("ATR(%d)%% %.3f | percentile %.0f / %.0f | %s", InpATRPeriod, g_atrPct, g_atrRank * 100.0, InpATRPercentile, g_atrPermit ? "PASS" : "BLOCK")
      : "ATR filter: waiting for history";
   MqlDateTime utc;
   TimeToStruct(ServerToUTC(TimeCurrent()), utc);
   string dow[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
   bool firstMon = (utc.day_of_week == 1 && utc.day <= 7);
   string clock = StringFormat("UTC: %s %02d:%02d%s", dow[utc.day_of_week], utc.hour, utc.min,
      (InpSkipFirstMonday && firstMon) ? " | first Monday skipped" : "");

   int nPos = 0;
   double lots = 0.0, pnl = 0.0;
   double hoursLeft = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i) || g_posInfo.Symbol() != _Symbol || g_posInfo.Magic() != InpMagicNumber) continue;
      nPos++;
      lots += g_posInfo.Volume();
      pnl += g_posInfo.Profit() + g_posInfo.Swap() + g_posInfo.Commission();
      datetime opened = (datetime)g_posInfo.Time();
      datetime exitAt = (datetime)((long)opened - (long)opened % 3600) + (datetime)InpHoldHours * 3600;
      hoursLeft = MathMax(hoursLeft, MathMax(0.0, (double)(exitAt - TimeCurrent()) / 3600.0));
   }
   string position = nPos > 0
      ? StringFormat("Position: %d open | %.2f lots | P&L %.2f | exit in %.1fh", nPos, lots, pnl, hoursLeft)
      : "Position: flat | waiting for Monday signal";

   string tradeCount = g_reporter != NULL
      ? StringFormat("Closed trades: %d | wins %d | losses %d", g_reporter.GetTotalTrades(), g_reporter.GetWins(), g_reporter.GetLosses())
      : "Closed trades: unavailable | reporter off";
   string tradeQuality = g_reporter != NULL
      ? StringFormat("Win rate: %.1f%% | profit factor: %.2f", g_reporter.GetWinRate(), g_reporter.GetProfitFactor())
      : "";
   double dailyDD = DailyDD(), totalDD = TotalDD();
   color ddColor = (dailyDD >= InpMaxDailyDD * 0.7 || totalDD >= InpMaxTotalDD * 0.7) ? clrOrangeRed
      : (dailyDD >= InpMaxDailyDD * 0.5 || totalDD >= InpMaxTotalDD * 0.5) ? clrYellow : clrSilver;
   g_dashboard.Update("ALPHACA | MONDAY EFFECT", _Symbol + " | H1 | long only",
      state, stateColor, reporterState,
      atr, g_atrPermit ? clrLime : clrYellow, clock, clrSilver, "", clrSilver,
      position, nPos > 0 && pnl < 0 ? clrOrangeRed : clrWhite,
      tradeCount, tradeQuality,
      StringFormat("Equity: %.2f %s", AccountInfoDouble(ACCOUNT_EQUITY), AccountInfoString(ACCOUNT_CURRENCY)),
      StringFormat("Drawdown: day %.2f%% / %.1f%% | total %.2f%% / %.1f%%", dailyDD, InpMaxDailyDD, totalDD, InpMaxTotalDD), ddColor,
      StringFormat("Maximum drawdown observed: %.2f%%", g_maxDDHit));
}

//+------------------------------------------------------------------+
//| Dashboard update                                                   |
//+------------------------------------------------------------------+
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
