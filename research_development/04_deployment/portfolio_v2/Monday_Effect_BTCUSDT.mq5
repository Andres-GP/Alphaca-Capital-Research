//+------------------------------------------------------------------+
//|                          TIS_BTC_Lunes_v3.mq5                     |
//|                          Alphaca Capital                          |
//+------------------------------------------------------------------+
//========================================================
//  STATUS: DEMO (ready for forward testing)
//  Version: 1.20  |  Last update: 2026-10-20
//========================================================
#property copyright "Alphaca Capital"
#property version   "1.20"
#property description "BTC MONDAY EFFECT v3 - REPORTER INTEGRATED"
#property description "Entry: Monday 00:00 UTC if ATR(48)% >= P30 of last year + not first Monday"
#property description "Exit: Tuesday 00:00 UTC (24 H1 bars), no stop, no take profit"

//  Rule (UTC; the EA converts the server time):
//   - Signal bar: the H1 bar closing at Monday 00:00 UTC (Sunday 23:00 bar).
//   - Volatility filter: Wilder ATR(48)/price in % >= percentile 30 of the last 8,760 bars.
//   - Calendar filter: first Monday of the month (day 1-7) is skipped.
//   - Entry: market buy at the open of the Monday 00:00 UTC bar.
//   - Exit: market close at the open of the Tuesday 00:00 UTC bar (24 bars later).
//   - Size: InpCapitalFraction of equity (40 %), unleveraged. Position size is the only risk control.
//  Python parity (monday_effect_engine): Wilder ATR, pandas-style percentile, DST-aware server time,
//  fill mode by symbol, never forces the minimum lot, time exit.

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include "PerformanceReporter.mqh"

// server time: automatic US-DST schedule or a fixed offset
enum ENUM_SERVER_TIME
{
   SERVER_GMT2_GMT3_US_DST = 0,   // GMT+2 winter / GMT+3 US summer (Axi, IC Markets, Pepperstone...)
   SERVER_FIXED_OFFSET     = 1    // Fixed offset (Exness = 0)
};

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "====== STRATEGY (VALIDATED - DO NOT MODIFY) ======"
input int      InpATRPeriod         = 48;      // ATR period in H1 bars (Wilder, as the engine)
input int      InpPercentileWindow  = 8760;    // H1 bars for the percentile (one year)
input int      InpPercentileMinBars = 500;     // minimum bars for the percentile (engine min_periods)
input double   InpMinPercentile     = 30.0;    // permit if ATR% is above this percentile
input bool     InpSkipFirstMonday   = true;    // skip the first Monday of the month (day 1-7)
input int      InpHoldHours         = 24;      // time exit: hours after the entry bar

input group "====== BROKER SERVER TIME ======"
input ENUM_SERVER_TIME InpTimeMode  = SERVER_GMT2_GMT3_US_DST; // broker server time
input int      InpFixedOffsetUTC    = 0;       // only with "Fixed offset": hours the server is ahead of UTC

input group "====== RISK ENGINE ======"
input double   InpCapitalFraction   = 0.40;    // fraction of equity per trade (0.40 = 40 %)
input double   InpMaxDailyDD        = 6.0;     // Daily kill switch % (SET TO THE ACCOUNT RULES)
input double   InpMaxTotalDD        = 30.0;    // Total kill switch % (SET TO THE ACCOUNT RULES)
input int      InpDeviationPoints   = 1000;    // max slippage in points (BTC needs a wide value)

input group "====== EMERGENCY AND MONITORING ======"
input bool     InpEnableDailyKill   = true;    // Enable daily kill switch?
input bool     InpEnableTotalKill   = true;    // Enable total kill switch?
input bool     InpSendPushAlerts    = true;    // Push/email notifications?
input long     InpMagicNumber       = 290301;  // Magic Number (unique per EA)
input bool     InpShowDashboard     = true;    // Show dashboard on chart?

input group "====== PERFORMANCE REPORTER ======"
input bool     InpEnableReporter    = true;    // Enable backend reporter?
input string   InpBackendUrl        = "";      // Backend URL (empty = module default)
input string   InpAuthToken         = "";      // Bearer token (empty = module default)
input bool     InpVerboseReporter   = false;   // Reporter debug logs
input int      InpHeartbeatSecs     = 3600;    // Heartbeat interval (seconds)
input int      InpMaxBarsNoTrade    = 1344;    // Inactivity alert threshold in H1 bars (1344 = 8 weeks: calm weeks do not trade)

//+------------------------------------------------------------------+
//| Globals                                                           |
//+------------------------------------------------------------------+
CTrade               g_trade;
CPositionInfo        g_posInfo;
PerformanceReporter* g_reporter = NULL;

datetime             g_lastBarTime;
bool                 g_dailyKillActive;
bool                 g_totalKillActive;
datetime             g_dailyKillDay;
string               g_killReason;

// last permit evaluation (cached; used by the entry and the dashboard)
bool                 g_permitOK;
double               g_atrPct;
double               g_pctl;

//+------------------------------------------------------------------+
//| Server time -> UTC                                                |
//+------------------------------------------------------------------+
// n-th Sunday of a month (00:00 UTC of that day)
datetime NthSunday(int year, int month, int n)
{
   MqlDateTime d; ZeroMemory(d);
   d.year = year; d.mon = month; d.day = 1;
   datetime first = StructToTime(d);
   MqlDateTime f; TimeToStruct(first, f);
   int add = (7 - f.day_of_week) % 7;                           // days until the first Sunday
   return first + (add + 7 * (n - 1)) * 86400;
}

// US daylight saving: 2nd Sunday of March (07:00 UTC) to 1st Sunday of November (06:00 UTC)
bool USSummer(datetime utc)
{
   MqlDateTime u; TimeToStruct(utc, u);
   datetime ini = NthSunday(u.year, 3, 2)  + 7 * 3600;
   datetime fin = NthSunday(u.year, 11, 1) + 6 * 3600;
   return (utc >= ini && utc < fin);
}

// hours the server is ahead of UTC at that moment
int OffsetHours(datetime server)
{
   if(InpTimeMode == SERVER_FIXED_OFFSET) return InpFixedOffsetUTC;
   return USSummer(server - 2 * 3600) ? 3 : 2;
}

datetime ToUTC(datetime server) { return server - OffsetHours(server) * 3600; }

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   if(PeriodSeconds(_Period) != 3600)
   {
      Print("This EA must run on an H1 chart");
      return(INIT_FAILED);
   }
   if(InpCapitalFraction < 0.05 || InpCapitalFraction > 1.0)
   {
      Print("Capital fraction out of range (0.05-1.0). Values above 1.0 would leverage the strategy.");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpMinPercentile < 0 || InpMinPercentile > 100)
   {
      Print("Percentile out of range (0-100)");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(Bars(_Symbol, PERIOD_H1) < InpATRPeriod + InpPercentileMinBars)
   {
      Print("ERROR: insufficient H1 history (", Bars(_Symbol, PERIOD_H1),
            " bars). At least ", InpATRPeriod + InpPercentileMinBars, " required.");
      return(INIT_FAILED);
   }
   if(Bars(_Symbol, PERIOD_H1) < InpPercentileWindow)
      Print("WARNING: less than one year of H1 history; the percentile uses fewer bars than the backtest.");

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);                     // fill mode accepted by the broker
   g_trade.SetDeviationInPoints(InpDeviationPoints);

   g_lastBarTime     = 0;
   g_dailyKillActive = false;
   g_totalKillActive = false;
   g_dailyKillDay    = 0;
   g_killReason      = "";
   g_permitOK        = false;
   g_atrPct          = 0;
   g_pctl            = -1;

   // live/demo: check that the configured server time matches the real one
   if(!MQLInfoInteger(MQL_TESTER))
   {
      int real = (int)MathRound((double)(TimeTradeServer() - TimeGMT()) / 3600.0);
      int conf = OffsetHours(TimeTradeServer());
      if(real != conf)
         Alert(StringFormat("TIS BTC Monday: server is at UTC%+d but the EA is configured for UTC%+d. Check InpTimeMode / InpFixedOffsetUTC.", real, conf));
      else
         PrintFormat("TIS BTC Monday: server time OK (UTC%+d)", real);
   }

   if(!InpEnableReporter && (InpEnableDailyKill || InpEnableTotalKill))
      Print("WARNING: kill switches read their drawdown from the reporter; with the reporter disabled they do not act.");

   if(InpEnableReporter)
   {
      string strategyName = "TIS_BTC_LUNES_" + _Symbol;
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

   Print("=== TIS BTC MONDAY v1.20 ===");
   Print("Symbol: ", _Symbol, " | Magic: ", InpMagicNumber);
   Print("Entry: Mon 00:00 UTC | ATR(", InpATRPeriod, ")% >= P", DoubleToString(InpMinPercentile, 0),
         " | skip first Monday=", InpSkipFirstMonday, " | Size ", DoubleToString(InpCapitalFraction * 100, 0), "%");

   if(g_reporter != NULL && InpSendPushAlerts)
      g_reporter.SendAlert("EA STARTED | " + _Symbol);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
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

   bool riskOK = RiskEngine();

   if(riskOK && IsNewBar())
   {
      datetime barOpen = iTime(_Symbol, PERIOD_H1, 0);
      MqlDateTime t; TimeToStruct(ToUTC(barOpen), t);           // UTC time of the bar that just opened
      bool monday00 = (t.day_of_week == 1 && t.hour == 0);

      // the percentile is only needed on Monday 00:00 UTC (and for the live dashboard)
      if(monday00 || (InpShowDashboard && !MQLInfoInteger(MQL_TESTER)))
         EvaluatePermit();

      if(g_reporter != NULL)
         g_reporter.OnBarUpdate(Bars(_Symbol, PERIOD_H1));

      if(HasOpenPosition()) CheckExit(barOpen);
      else if(monday00)     CheckEntry(t);
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

   datetime now   = TimeCurrent();
   datetime today = (datetime)(now - now % 86400);

   // the daily kill only lasts until the next server day (the total kill is permanent)
   if(g_dailyKillActive && today > g_dailyKillDay)
   {
      g_dailyKillActive = false;
      Print("Daily kill switch reset (new day)");
   }

   double dailyDD = g_reporter.GetDailyDD();
   double totalDD = g_reporter.GetTotalDD();

   if(InpEnableDailyKill)
   {
      if(dailyDD >= InpMaxDailyDD && !g_dailyKillActive)
      {
         g_dailyKillActive = true;
         g_dailyKillDay    = today;
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
   if(HasOpenPosition())
      ClosePosition(reason);
}

//+------------------------------------------------------------------+
//| Permit: Wilder ATR% of the last CLOSED bar and its percentile     |
//|   ATR = RMA(TR, 48) seeded with the first TR (pandas ewm alpha=1/48, adjust=False)
//|   pct = rolling(8760, min_periods=500).rank(pct=True): includes the current bar, ties averaged
//+------------------------------------------------------------------+
bool Permit(double &atrPct, double &pctl)
{
   atrPct = 0; pctl = -1;
   int want = InpPercentileWindow + 1000;                       // 1,000 extra bars so the RMA converges
   MqlRates r[];
   ArraySetAsSeries(r, false);                                  // r[0] = oldest
   int got = CopyRates(_Symbol, PERIOD_H1, 1, want, r);         // from the last CLOSED bar backwards
   if(got < InpATRPeriod + InpPercentileMinBars) return false;

   double ap[]; ArrayResize(ap, got);
   double rma = 0;
   for(int i = 0; i < got; i++)
   {
      double tr = r[i].high - r[i].low;
      if(i > 0) tr = MathMax(tr, MathMax(MathAbs(r[i].high - r[i-1].close), MathAbs(r[i].low - r[i-1].close)));
      rma = (i == 0) ? tr : rma + (tr - rma) / InpATRPeriod;
      ap[i] = (i >= InpATRPeriod - 1) ? rma / r[i].close * 100.0 : -1.0;
   }
   atrPct = ap[got - 1];

   int from = MathMax(InpATRPeriod - 1, got - InpPercentileWindow);
   int n = 0, lower = 0, equal = 0;
   for(int i = from; i < got; i++)
   {
      n++;
      if(ap[i] < atrPct) lower++;
      else if(ap[i] == atrPct) equal++;                         // includes the bar itself
   }
   if(n < InpPercentileMinBars) return false;
   pctl = 100.0 * (lower + (equal + 1) / 2.0) / n;
   return pctl >= InpMinPercentile;
}

void EvaluatePermit()
{
   g_permitOK = Permit(g_atrPct, g_pctl);
}

//+------------------------------------------------------------------+
//| CheckEntry - Monday 00:00 UTC                                     |
//+------------------------------------------------------------------+
void CheckEntry(const MqlDateTime &t)
{
   if(InpSkipFirstMonday && t.day <= 7)
   {
      Print("No trade: first Monday of the month");
      return;
   }

   if(!g_permitOK)
   {
      if(g_pctl < 0) Print("No permit: not enough history for the percentile");
      else PrintFormat("No permit: ATR%% %.3f = percentile %.1f (< %.0f)", g_atrPct, g_pctl, InpMinPercentile);
      return;
   }

   double lots = CalculateLots();
   if(lots <= 0) return;

   string comment = "TIS|MONDAY|v3";
   if(g_trade.Buy(lots, _Symbol, 0, 0, 0, comment))
   {
      PrintFormat("=== ENTRY LONG Mon 00:00 UTC | ATR%% %.3f = pctl %.1f | Lots=%.4f",
                  g_atrPct, g_pctl, lots);

      if(g_reporter != NULL && InpSendPushAlerts)
         g_reporter.SendAlert(StringFormat("BUY %s | ATR%%=%.3f P%.0f | Lots=%.4f",
                              _Symbol, g_atrPct, g_pctl, lots));
   }
   else
   {
      Print("BUY FAILED: ", g_trade.ResultRetcodeDescription());
      if(g_reporter != NULL)
         g_reporter.OnOrderRejected("EntryBuy", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| CheckExit - time exit                                             |
//|  at the open of the bar HoldHours after the entry bar (Tuesday 00:00 UTC);
//|  if that bar is missing it closes on the next one instead of waiting a week
//+------------------------------------------------------------------+
void CheckExit(datetime barOpen)
{
   if(!SelectOwnPosition()) return;

   datetime opened   = g_posInfo.Time();
   datetime entryBar = (datetime)((long)opened - (long)opened % 3600);
   if(barOpen < entryBar + InpHoldHours * 3600) return;

   ClosePosition("Time exit Tue 00:00 UTC");
}

//+------------------------------------------------------------------+
//| ClosePosition - closes and reports to the backend                 |
//+------------------------------------------------------------------+
void ClosePosition(string reason)
{
   if(!SelectOwnPosition()) return;

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
      string result = (profit >= 0) ? "WIN" : "LOSS";
      Print("CLOSED [", reason, "]: Ticket #", ticket, " | ", result, " | P&L=$", DoubleToString(profit, 2));

      if(g_reporter != NULL)
      {
         g_reporter.ReportTradeClosed(ticket, _Symbol,
            entryPrice, exitPrice, volume, profit,
            entryTime, TimeCurrent(), commission, ptype);

         if(InpSendPushAlerts)
            g_reporter.SendAlert(StringFormat("%s EXIT %s | $%.0f | WR=%.0f%% | PF=%.2f",
                                 result, _Symbol, profit,
                                 g_reporter.GetWinRate(), g_reporter.GetProfitFactor()));
      }
   }
   else
   {
      Print("CLOSE FAILED: ", g_trade.ResultRetcodeDescription());
      if(g_reporter != NULL)
         g_reporter.OnOrderRejected("Close", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| CalculateLots - fraction of equity, never forces the minimum lot  |
//+------------------------------------------------------------------+
double CalculateLots()
{
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double price    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double contract = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double step     = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   if(price <= 0 || contract <= 0 || step <= 0)
   {
      Print("Error: price, contract size or volume step = 0");
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("TickDataInvalid",
            StringFormat("price=%.2f contract=%.4f step=%.4f", price, contract, step), "high");
      return 0;
   }

   double lots = MathFloor(equity * InpCapitalFraction / (price * contract) / step) * step;
   int    digs = (int)MathMax(0, MathCeil(-MathLog10(step)));
   lots = NormalizeDouble(MathMin(lots, lotMax), digs);

   if(lots < lotMin)
   {
      string msg = StringFormat("%.0f%% of equity (%.2f) is below the minimum lot %.4f - no trade",
                                InpCapitalFraction * 100, equity * InpCapitalFraction, lotMin);
      Print(msg);
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("ZeroLots", msg, "high");
      return 0;
   }

   // margin guard (as in the RSI2 EA): reduce, but never below the minimum lot
   double marginRequired = 0;
   if(OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lots, price, marginRequired))
   {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      if(marginRequired > freeMargin * 0.8)
      {
         double reduction = (freeMargin * 0.8) / marginRequired;
         double lotsBefore = lots;
         lots = NormalizeDouble(MathFloor((lots * reduction) / step) * step, digs);
         if(lots < lotMin)
         {
            Print("No trade: free margin does not allow the minimum lot");
            if(g_reporter != NULL)
               g_reporter.ReportHealthAlert("ZeroLots", "Free margin below the minimum lot", "high");
            return 0;
         }
         Print("Margin adjusted - Lots=", DoubleToString(lots, digs));
         if(g_reporter != NULL)
            g_reporter.ReportHealthAlert("ReducedSize",
               StringFormat("Lots reduced from %.4f to %.4f", lotsBefore, lots), "medium");
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
// selects this EA's position into g_posInfo
bool SelectOwnPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() == _Symbol && g_posInfo.Magic() == InpMagicNumber)
         return true;
   }
   return false;
}

bool HasOpenPosition()
{
   return SelectOwnPosition();
}

//+------------------------------------------------------------------+
//| UpdateDashboard                                                   |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   int x = 20, y = 30, lineH = 18;

   DashLabel("TIS_H1", "TIS BTC MONDAY v1.20", x, y, clrDodgerBlue, 11);
   y += lineH + 2;
   DashLabel("TIS_H2", _Symbol + " H1 | Mon 00:00 UTC -> Tue 00:00 UTC", x, y, clrDarkGray, 9);
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

   DashLabel("TIS_UTC", StringFormat("Server UTC%+d | UTC now: %s", OffsetHours(TimeCurrent()),
             TimeToString(ToUTC(TimeCurrent()), TIME_DATE | TIME_MINUTES)), x, y, clrSilver, 9);
   y += lineH;

   if(g_pctl >= 0)
   {
      bool ok = (g_pctl >= InpMinPercentile);
      DashLabel("TIS_PER", StringFormat("ATR(%d)%%: %.3f | P%.1f (min P%.0f) %s", InpATRPeriod, g_atrPct, g_pctl,
                InpMinPercentile, ok ? "<< PERMIT" : "NO PERMIT"),
                x, y, ok ? clrLime : clrOrangeRed, 10);
   }
   else
   {
      DashLabel("TIS_PER", "Permit: waiting for the first evaluation", x, y, clrGray, 9);
   }
   y += lineH;

   MqlDateTime tu; TimeToStruct(ToUTC(TimeCurrent()), tu);
   bool firstMonday = (tu.day_of_week == 1 && tu.day <= 7);
   if(InpSkipFirstMonday && firstMonday)
      DashLabel("TIS_CAL", "Calendar: FIRST MONDAY - skipped", x, y, clrOrangeRed, 9);
   else
      DashLabel("TIS_CAL", "Calendar: OK", x, y, clrSilver, 9);
   y += lineH + 6;

   if(SelectOwnPosition())
   {
      double pnl   = g_posInfo.Profit() + g_posInfo.Swap() + g_posInfo.Commission();
      double hours = (double)(TimeCurrent() - g_posInfo.Time()) / 3600.0;
      DashLabel("TIS_POS", StringFormat("LONG %.4f lots | P&L: $%.0f | %.1f/%dh", g_posInfo.Volume(), pnl, hours, InpHoldHours),
                x, y, pnl >= 0 ? clrLime : clrOrangeRed, 10);
   }
   else
   {
      DashLabel("TIS_POS", "FLAT - Waiting for Monday 00:00 UTC", x, y, clrGray, 9);
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