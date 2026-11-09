//+------------------------------------------------------------------+
//|                                       WeeklyMomentum_ETHUSD_Axi.mq5 |
//|                                              Alphaca Capital      |
//+------------------------------------------------------------------+
//========================================================
//  STATUS: IN DEVELOPMENT (pending reconciliation, notebook 04)
//  Strategy ID : WEEKLYMOM.ethusd.cfd.v2_long
//  Vehicle     : Axi ETHUSD CFD (H1, hedging account, long only by default)
//  Version: 1.03   (1.03: InpDiagOpens diagnostic log only, rule untouched; 1.02: notional-per-lot rounding fix, 1 retry/sec; 1.01: InpCapitalBase / InpFixedCapital)
//
//  RULE (frozen, = variants/v2_ethusd_long.yaml / weekly_momentum_engine.py v2)
//   - Everything runs on MT5 SERVER time (Axi = New York + 7 h). No UTC conversion
//     is needed for the rule: the entry slot is Monday 00:00 SERVER time.
//   - Entry : at the OPEN of the Monday 00:00 server H1 candle (first tick).
//   - Signal: at the CLOSE of the candle before the entry (H1 bar 1):
//               mom = close[bar 1] / close[candle before the entry-hour candle
//                     `lookback` days earlier] - 1
//             LONG if mom > 0, SHORT if mom < 0 (InpDirection; v2 = long only).
//             Signal candle and reference candle must exist and be exactly 1 h
//             apart from their anchor (engine: contiguity checks).
//   - Exit  : at the OPEN of the 00:00 server candle `hold` days after the entry day.
//   - No stop, no target, no filters. Spread and swap are paid by the broker.
//   - hold > 7 => consecutive weekly trades OVERLAP by design (hold 11 -> up to 2
//     open at once). Needs a HEDGING account: the EA refuses to start on netting.
//
//  FILES (Common/Files) for reconciliation (notebook 04):
//   - weekly_momentum_log.csv    : one row per entry slot (Monday), NO header, ';'
//                                  date(server);spread_points;decision;reason;mom_ret_pct;lots
//                                  decision = BUY | SELL | SKIP
//   - weekly_momentum_trades.csv : one row per closed trade, WITH header, times in SERVER time
//                                  time_in;time_out;price_in;price_out;lots;profit;swap;commission;reason;source;type
//                                  NOTE: `profit` is NET (deal profit + swap + commission + fee).
//   - weekly_momentum_diag.csv   : ONLY with InpDiagOpens=true. One row per entry/exit, WITH header, ';'
//                                  kind;bar;now;iopen0;iclose1;bid;ask;pre_t;pre_bid;first_t;first_bid;n60
//========================================================
#property copyright "Alphaca Capital"
#property version   "1.03"
#property description "WEEKLY MOMENTUM - ETHUSD CFD (AXI) - REPORTER INTEGRATED"
#property description "Entry: Monday 00:00 server | Signal: 31 d return | Exit: 11 d later (open)"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include "PerformanceReporter.mqh"

//+------------------------------------------------------------------+
//| Enums                                                             |
//+------------------------------------------------------------------+
enum ENUM_SERVER_TZ
{
   TZ_GMT2_GMT3_US_DST = 0,   // GMT+2 winter / GMT+3 US summer (Axi, IC Markets, Pepperstone...)
   TZ_FIXED_OFFSET     = 1    // Fixed offset vs UTC (see InpFixedOffsetUTC)
};

enum ENUM_SPREAD_SRC
{
   SPREAD_SYMBOL = 0,         // SYMBOL_SPREAD at the decision tick (what you actually pay)
   SPREAD_BAR0   = 1          // spread field of the H1 entry bar (what the CSV feed stores)
};

enum ENUM_WM_DIRECTION { WM_LONG_ONLY = 0, WM_BOTH = 1, WM_SHORT_ONLY = 2 };

enum ENUM_WM_BELOW_MIN
{
   WM_BELOW_SKIP    = 0,      // engine below_min_lot="skip": 0 lots = trade not taken
   WM_BELOW_MIN_LOT = 1       // engine below_min_lot="min_lot": trade the minimum lot even if it weighs more
};

enum ENUM_WM_CAPITAL
{
   WM_CAP_EQUITY = 0,         // size on live account equity (compounding)
   WM_CAP_FIXED  = 1          // size on InpFixedCapital (no compounding; reconciliation run)
};

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "====== STRATEGY (FROZEN PARAMETERS - DO NOT MODIFY) ======"
input int               InpLookbackDays     = 31;              // lookback_days
input int               InpHoldDays         = 11;              // hold_days (> 7 => overlapping trades, hedging account)
input ENUM_WM_DIRECTION InpDirection        = WM_LONG_ONLY;    // direction (v2_ethusd_long = long only)
input int               InpEntryDow         = 1;               // entry weekday, MT5 numbering (0 = Sun, 1 = Mon)
input int               InpEntryHour        = 0;               // entry hour, SERVER time
input int               InpExitTolMin       = 5;               // exit later than x min after the scheduled candle = "LATE (gap)"

input group "====== EXECUTION / BROKER TIME ======"
input ENUM_SERVER_TZ    InpServerTZ         = TZ_GMT2_GMT3_US_DST; // Broker server time (sanity check only)
input int               InpFixedOffsetUTC   = 0;               // Only with fixed offset: hours server is ahead of UTC
input ENUM_SPREAD_SRC   InpSpreadSource     = SPREAD_BAR0;     // Spread logged. BAR0 = same field the engine reads (reconciliation)
input double            InpMaxSlippageBps   = 10.0;            // Max slippage on market orders (bps of price)
input int               InpMaxEntryDelayMin = 5;               // Retry window after the entry candle opens; after it the slot is skipped

input group "====== RISK ENGINE ======"
input double            InpFractionCapital  = 0.05;            // Fraction of capital per trade (variant size_fraction)
input ENUM_WM_CAPITAL   InpCapitalBase      = WM_CAP_EQUITY;   // Capital used for sizing (FIXED for the reconciliation run)
input double            InpFixedCapital     = 3500.0;          // Used only with WM_CAP_FIXED
input ENUM_WM_BELOW_MIN InpBelowMinLot      = WM_BELOW_MIN_LOT;// If the fraction does not reach the min lot: trade min lot | skip
input double            InpMaxDailyDD       = 5.0;             // Daily kill switch %
input double            InpMaxTotalDD       = 8.5;             // Total kill switch % (hard limit 9%)

input group "====== EMERGENCY AND MONITORING ======"
input bool              InpEnableDailyKill  = true;            // Enable daily kill switch?
input bool              InpEnableTotalKill  = true;            // Enable total kill switch? (DISABLE it for the reconciliation tester run)
input bool              InpSendPushAlerts   = true;            // Push/email notifications?
input int               InpMagicNumber      = 290403;          // Magic Number (unique per EA)
input bool              InpShowDashboard    = true;            // Show dashboard on chart?
input bool              InpLogFiles         = true;            // Write weekly_momentum_log.csv / _trades.csv (Common/Files)?
input bool              InpDiagOpens        = false;           // RECONCILIATION ONLY: log iOpen/bid/ask/ticks at every entry and exit

input group "====== PERFORMANCE REPORTER ======"
input bool              InpEnableReporter   = true;            // Enable backend reporter?
input string            InpBackendUrl       = "";              // Backend URL (empty = module default)
input string            InpAuthToken        = "";              // Bearer token (empty = module default)
input bool              InpVerboseReporter  = false;           // Reporter debug logs
input int               InpHeartbeatSecs    = 3600;            // Heartbeat interval (seconds)
input int               InpMaxBarsNoTrade   = 840;             // Inactivity alert threshold (H1 bars, 35 days without any open position)

//+------------------------------------------------------------------+
//| Constants / Globals                                               |
//+------------------------------------------------------------------+
#define LOG_FILE    "weekly_momentum_log.csv"
#define TRADES_FILE "weekly_momentum_trades.csv"
#define DIAG_FILE   "weekly_momentum_diag.csv"

const ENUM_TIMEFRAMES WM_TF = PERIOD_H1;

enum WM_EVAL { WM_EVAL_TRADE = 0, WM_EVAL_SKIP = 1, WM_EVAL_RETRY = 2 };

CTrade               g_trade;
CPositionInfo        g_posInfo;
PerformanceReporter* g_reporter = NULL;

datetime             g_lastBarTime;
bool                 g_dailyKillActive;
bool                 g_totalKillActive;
string               g_killReason;

// own equity tracking (kill switches do NOT depend on the reporter)
double               g_peakEquity;
double               g_dayStartEquity;
int                  g_dayKey;
double               g_maxDDHit;

// entry slot state
datetime             g_slotDone    = 0;     // entry candle already resolved (trade opened or skip logged)
datetime             g_retryBar    = 0;     // entry candle of g_retryReason
string               g_retryReason = "";    // last reason of a retry-able failure (logged if the window expires)
double               g_lastMom     = EMPTY_VALUE;   // last computed momentum (dashboard)
datetime             g_lastMomBar  = 0;

// late-exit alerts already sent (position tickets)
ulong                g_lateAlerted[];

// pending decision-log row (written on the next new bar, when the entry bar is closed)
bool                 g_pend = false;
string               g_pDate = "";
string               g_pDec  = "";
string               g_pRsn  = "";
int                  g_pSp   = -1;
datetime             g_pBar  = 0;           // entry bar open time (server time)
double               g_pMom  = EMPTY_VALUE;
double               g_pLots = 0.0;

//+------------------------------------------------------------------+
//| Time helpers                                                      |
//+------------------------------------------------------------------+
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

string TsStr(datetime t)
{
   MqlDateTime s;
   TimeToStruct(t, s);
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d", s.year, s.mon, s.day, s.hour, s.min, s.sec);
}

string IsoDate(datetime t)
{
   MqlDateTime s;
   TimeToStruct(t, s);
   return StringFormat("%04d-%02d-%02d", s.year, s.mon, s.day);
}

// entry-hour:00 SERVER of the day of t
datetime SlotOf(datetime t)
{
   MqlDateTime d; TimeToStruct(t, d);
   d.hour = InpEntryHour; d.min = 0; d.sec = 0;
   return StructToTime(d);
}

bool IsEntrySlot(datetime barTime)
{
   MqlDateTime d; TimeToStruct(barTime, d);
   return (d.day_of_week == InpEntryDow && d.hour == InpEntryHour && d.min == 0);
}

// scheduled exit (server time) of a position opened at 'opened'
datetime ExitTimeOf(datetime opened)
{
   return SlotOf(opened) + (datetime)((long)InpHoldDays * 86400);
}

datetime NextEntrySlot()
{
   datetime now = TimeCurrent();
   datetime t = SlotOf(now);
   for(int k = 0; k < 9; k++)
   {
      MqlDateTime d; TimeToStruct(t, d);
      if(d.day_of_week == InpEntryDow && t > now) return t;
      t += 86400;
   }
   return 0;
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
   if(StringFind(_Symbol, "ETH") != 0)
      Print("WARNING: this EA is built for ETHUSD; current symbol is ", _Symbol);

   if(InpFractionCapital < 0.01 || InpFractionCapital > 10.0)
   {
      Print("Fraction of capital out of range (0.01-10.0)");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpCapitalBase == WM_CAP_FIXED && InpFixedCapital <= 0.0)
   {
      Print("InpFixedCapital must be > 0 with WM_CAP_FIXED");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpLookbackDays < 1 || InpHoldDays < 1 || InpExitTolMin < 0 || InpMaxEntryDelayMin < 0)
   {
      Print("Invalid lookback / hold / tolerances");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpEntryDow < 0 || InpEntryDow > 6 || InpEntryHour < 0 || InpEntryHour > 23)
   {
      Print("Invalid entry weekday / hour");
      return(INIT_PARAMETERS_INCORRECT);
   }

   // hold > 7 days => weekly trades overlap; a netting account would merge them into one position
   ENUM_ACCOUNT_MARGIN_MODE mm = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(InpHoldDays > 7 && mm != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      Print("ERROR: hold > 7 days needs a HEDGING account (overlapping trades). Netting account detected: EA stopped.");
      return(INIT_FAILED);
   }

   SymbolSelect(_Symbol, true);

   // force the H1 history (lookback + margin) to load
   datetime tmp[];
   int want = (InpLookbackDays + 5) * 24;
   int got  = CopyTime(_Symbol, WM_TF, 0, want, tmp);
   if(got < want)
      PrintFormat("WARNING: only %d of %d H1 bars available yet (history may still be syncing)", got, want);

   // each tester run starts with clean reconciliation files (no duplicated dates)
   if(MQLInfoInteger(MQL_TESTER) && InpLogFiles)
   {
      FileDelete(LOG_FILE, FILE_COMMON);
      FileDelete(TRADES_FILE, FILE_COMMON);
      FileDelete(DIAG_FILE, FILE_COMMON);
   }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   g_lastBarTime     = 0;
   g_dailyKillActive = false;
   g_totalKillActive = false;
   g_killReason      = "";
   g_slotDone        = 0;
   g_retryBar        = 0;
   g_retryReason     = "";
   g_lastMom         = EMPTY_VALUE;
   g_lastMomBar      = 0;
   g_pend            = false;
   ArrayResize(g_lateAlerted, 0);

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
         Alert(StringFormat("ALPHACA WeeklyMom: server is UTC%+d but EA is configured for UTC%+d. Check InpServerTZ / InpFixedOffsetUTC.",
                            real, conf));
      else
         PrintFormat("Broker time OK (server = UTC%+d)", real);
   }

   if(InpEnableReporter)
   {
      string strategyName = "ALPHACA_WEEKLYMOM_" + _Symbol;
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

   Print("=== ALPHACA WEEKLY MOMENTUM ETHUSD v1.03 ===");
   Print("Symbol: ", _Symbol, " | Magic: ", InpMagicNumber);
   PrintFormat("Lookback %d d | hold %d d | dir %d | entry dow %d %02d:00 server | size %.1f%% | below-min-lot %s | margin mode %d",
               InpLookbackDays, InpHoldDays, (int)InpDirection, InpEntryDow, InpEntryHour,
               InpFractionCapital * 100.0,
               InpBelowMinLot == WM_BELOW_MIN_LOT ? "min lot" : "skip", (int)mm);
   if(InpCapitalBase == WM_CAP_FIXED)
      PrintFormat("Sizing capital: FIXED %.2f (no compounding)", InpFixedCapital);
   else
      Print("Sizing capital: live EQUITY (compounding)");
   if(InpEnableTotalKill && InpMaxTotalDD < 9.0)
      PrintFormat("NOTE: total kill at %.1f%% sits inside the strategy's historical drawdown at small capital (engine: about -8.8%% intrabar at 3,500). It can halt the EA.",
                  InpMaxTotalDD);

   // capital needed so that the minimum lot does not exceed the target fraction
   double npl = NotionalPerLot(SymbolInfoDouble(_Symbol, SYMBOL_ASK));
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(npl > 0)
      PrintFormat("Notional per lot: %.2f %s | min lot %.4f | min equity for %.1f%% sizing: %.0f %s",
                  npl, AccountInfoString(ACCOUNT_CURRENCY), minLot, InpFractionCapital * 100.0,
                  minLot * npl / InpFractionCapital, AccountInfoString(ACCOUNT_CURRENCY));

   PushAlert("EA STARTED | " + _Symbol);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   FlushPendingLog();                    // last decision row (entry bar may be the last one of a tester run)
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

   if(newBar)
   {
      FlushPendingLog();                 // previous entry bar is now closed: log its stored spread

      if(riskOK && g_reporter != NULL)
         g_reporter.OnBarUpdate(Bars(_Symbol, WM_TF));
   }

   ProcessEntry(riskOK);                 // decides (and logs) every entry slot, also under a kill; retries inside the window

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
// one line per entry slot, whether the EA trades or not.
// NO header. Columns: date;spread_points;decision;reason;mom_ret_pct;lots
void LogDecision(string dateSrv, int spreadPts, string decision, string reason, double mom, double lots)
{
   if(!InpLogFiles) return;
   int h = FileOpen(LOG_FILE, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ';');
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, dateSrv, (spreadPts >= 0 ? IntegerToString(spreadPts) : ""), decision, reason,
             (mom == EMPTY_VALUE ? "" : DoubleToString(mom, 6)), DoubleToString(lots, 2));
   FileClose(h);
}

// Deferred decision row: the spread is read from the CLOSED entry bar (what the CSV stores),
// so the row is written on the next new bar (FlushPendingLog). Falls back to the tick value.
void FlushPendingLog()
{
   if(!g_pend) return;
   g_pend = false;
   int sp = g_pSp;
   if(InpSpreadSource == SPREAD_BAR0)
   {
      MqlRates r[];
      if(CopyRates(_Symbol, WM_TF, g_pBar, 1, r) == 1 && r[0].time == g_pBar)
         sp = (int)r[0].spread;
   }
   LogDecision(g_pDate, sp, g_pDec, g_pRsn, g_pMom, g_pLots);
}

void LogDecisionBar(string dateSrv, int spreadPts, string decision, string reason, datetime entryBar,
                    double mom, double lots)
{
   FlushPendingLog();                    // never lose a previous pending row
   g_pend  = true;
   g_pDate = dateSrv;
   g_pSp   = spreadPts;
   g_pDec  = decision;
   g_pRsn  = reason;
   g_pBar  = entryBar;
   g_pMom  = mom;
   g_pLots = lots;
}

// one line per closed trade (WITH header; times in SERVER time = notebook 04 DEAL_TIME_MODE "mt5_server_ny")
// `profit` is NET: deal profit + swap + commission + fee (see GetClosedDealInfo)
void LogTrade(string reason, double lots, double entryPrice, double exitPrice, double profit,
              double swap, double commission, datetime entryTime, datetime exitTime, bool fromDeals,
              ENUM_POSITION_TYPE ptype)
{
   if(!InpLogFiles) return;
   int h = FileOpen(TRADES_FILE, FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ';');
   if(h == INVALID_HANDLE) return;
   if(FileSize(h) == 0)
      FileWrite(h, "time_in", "time_out", "price_in", "price_out", "lots", "profit", "swap", "commission",
                "reason", "source", "type");
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TsStr(entryTime), TsStr(exitTime),
             DoubleToString(entryPrice, _Digits), DoubleToString(exitPrice, _Digits),
             DoubleToString(lots, 2), DoubleToString(profit, 2),
             DoubleToString(swap, 2), DoubleToString(commission, 2),
             reason, fromDeals ? "deal" : "estimate",
             ptype == POSITION_TYPE_BUY ? "long" : "short");
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
//| Close + report ONE position (shared by time exit and kill switch) |
//+------------------------------------------------------------------+
void ClosePositionAndReport(ulong ticket, string reason)
{
   if(!g_posInfo.SelectByTicket(ticket)) return;
   if(g_posInfo.Symbol() != _Symbol || g_posInfo.Magic() != InpMagicNumber) return;

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
               entryTime, exitTime, fromDeals, ptype);

      if(g_reporter != NULL)
      {
         g_reporter.ReportTradeClosed(ticket, _Symbol,
            entryPrice, exitPrice, volume, profit,
            entryTime, exitTime, commission, ptype);

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

void CloseAllAndReport(string reason)
{
   ulong tickets[];
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() != _Symbol) continue;
      if(g_posInfo.Magic() != InpMagicNumber) continue;
      int n = ArraySize(tickets);
      ArrayResize(tickets, n + 1);
      tickets[n] = g_posInfo.Ticket();
   }
   for(int k = 0; k < ArraySize(tickets); k++)
      ClosePositionAndReport(tickets[k], reason);
}

void EmergencyCloseAll(string reason)
{
   CloseAllAndReport(reason);
}

//+------------------------------------------------------------------+
//| CheckExit - time exit at the open of the candle `hold` days after |
//|   the entry day. Runs on EVERY tick. A failed close is retried on |
//|   the next tick; under an active kill switch every position is    |
//|   closed. Each position has its own exit time (they overlap).     |
//+------------------------------------------------------------------+
bool AlreadyAlerted(ulong ticket)
{
   for(int i = 0; i < ArraySize(g_lateAlerted); i++)
      if(g_lateAlerted[i] == ticket) return true;
   return false;
}

void CheckExit()
{
   if(!HasOpenPosition()) return;

   if(g_dailyKillActive || g_totalKillActive)
   {
      CloseAllAndReport("Kill switch (retry)");
      return;
   }

   datetime barNow = iTime(_Symbol, WM_TF, 0);
   if(barNow == 0) return;

   ulong due[];
   datetime dueExit[];
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() != _Symbol || g_posInfo.Magic() != InpMagicNumber) continue;
      datetime ex = ExitTimeOf((datetime)g_posInfo.Time());
      if(barNow < ex) continue;
      int n = ArraySize(due);
      ArrayResize(due, n + 1);  ArrayResize(dueExit, n + 1);
      due[n] = g_posInfo.Ticket();  dueExit[n] = ex;
   }

   for(int k = 0; k < ArraySize(due); k++)
   {
      // engine rule: the exit candle must exist. A later exit means a data/market gap: the trade does not match
      // the engine -> label it and alert once.
      bool late = ((barNow - dueExit[k]) > InpExitTolMin * 60);
      if(late && !AlreadyAlerted(due[k]))
      {
         int n = ArraySize(g_lateAlerted);
         ArrayResize(g_lateAlerted, n + 1);
         g_lateAlerted[n] = due[k];
         string msg = StringFormat("WeeklyMom LATE EXIT: scheduled %s server, first bar %s server (market/data gap). Check swap and reconciliation.",
                                   TsStr(dueExit[k]), TsStr(barNow));
         Print("WARNING: ", msg);
         PushAlert(msg);
         if(g_reporter != NULL) g_reporter.ReportHealthAlert("LateExit", msg, "high");
      }
      DiagLog("OUT");
      ClosePositionAndReport(due[k], late ? "Time exit LATE (gap)" : "Time exit hold");
   }
}

//+------------------------------------------------------------------+
//| Signal: same definition as the engine's _momentum()               |
//|  - signal candle    = candle immediately before the entry candle  |
//|  - reference candle = candle before the entry-hour candle         |
//|                       `lookback` days earlier (server wall clock) |
//+------------------------------------------------------------------+
WM_EVAL EvaluateSignal(datetime t0, double &mom, int &side, string &reason)
{
   mom = EMPTY_VALUE; side = 0; reason = "";

   if(iTime(_Symbol, WM_TF, 1) != t0 - 3600)
   {
      reason = "no signal bar";
      return WM_EVAL_RETRY;
   }
   datetime anchor = t0 - (datetime)((long)InpLookbackDays * 86400);
   if(iBarShift(_Symbol, WM_TF, anchor, true) < 0)
   {
      reason = "no reference anchor";
      return WM_EVAL_RETRY;
   }
   int ir = iBarShift(_Symbol, WM_TF, anchor - 3600, true);
   if(ir < 0)
   {
      reason = "no reference bar";
      return WM_EVAL_RETRY;
   }
   double c_sig = iClose(_Symbol, WM_TF, 1);
   double c_ref = iClose(_Symbol, WM_TF, ir);
   if(c_sig <= 0 || c_ref <= 0)
   {
      reason = "invalid close";
      return WM_EVAL_RETRY;
   }
   mom = (c_sig / c_ref - 1.0) * 100.0;

   if(mom == 0.0)
   {
      reason = "zero signal";
      return WM_EVAL_SKIP;
   }
   side = (mom > 0.0 ? 1 : -1);
   if(InpDirection == WM_LONG_ONLY && side < 0)
   {
      reason = "mom<0 (long_only)";
      return WM_EVAL_SKIP;
   }
   if(InpDirection == WM_SHORT_ONLY && side > 0)
   {
      reason = "mom>0 (short_only)";
      return WM_EVAL_SKIP;
   }
   reason = "ok";
   return WM_EVAL_TRADE;
}

//+------------------------------------------------------------------+
//| Spread helper                                                     |
//+------------------------------------------------------------------+
// spread (points) at decision time. With SPREAD_BAR0 the logged value is replaced
// by the closed-bar value in FlushPendingLog; this one is only the fallback.
int ReadSpreadPoints()
{
   if(InpSpreadSource == SPREAD_BAR0)
   {
      MqlRates r[];
      if(CopyRates(_Symbol, WM_TF, 0, 1, r) == 1) return (int)r[0].spread;
   }
   return (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
}

//+------------------------------------------------------------------+
//| DiagLog - RECONCILIATION ONLY (InpDiagOpens). One row per entry   |
//|   ("IN") and exit ("OUT"): tester bar open, bid/ask, last tick    |
//|   before the bar and first tick of the bar. Does not touch the    |
//|   rule. Compared with the engine CSV open in notebook 04 (3a).    |
//+------------------------------------------------------------------+
void DiagLog(string kind)
{
   if(!InpDiagOpens) return;
   datetime b0   = iTime(_Symbol, WM_TF, 0);
   ulong    b0ms = (ulong)b0 * 1000;
   MqlTick  tk[];
   int n = CopyTicksRange(_Symbol, tk, COPY_TICKS_INFO, b0ms - 900000, b0ms + 120000);   // -15 min .. +2 min
   double   preBid = 0, firstBid = 0;
   datetime preT = 0, firstT = 0;
   int      n60 = 0;                                  // ticks inside the first 60 s of the bar
   for(int i = 0; i < n; i++)
   {
      if(tk[i].bid <= 0) continue;
      if(tk[i].time_msc < b0ms) { preBid = tk[i].bid; preT = tk[i].time; }          // last tick BEFORE the bar opens
      else
      {
         if(firstT == 0) { firstBid = tk[i].bid; firstT = tk[i].time; }             // first tick OF the bar
         if(tk[i].time_msc < b0ms + 60000) n60++;
      }
   }
   string row = kind + ";" + TsStr(b0) + ";" + TsStr(TimeCurrent()) + ";"
              + DoubleToString(iOpen(_Symbol, WM_TF, 0), _Digits) + ";"
              + DoubleToString(iClose(_Symbol, WM_TF, 1), _Digits) + ";"
              + DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_BID), _Digits) + ";"
              + DoubleToString(SymbolInfoDouble(_Symbol, SYMBOL_ASK), _Digits) + ";"
              + TsStr(preT) + ";" + DoubleToString(preBid, _Digits) + ";"
              + TsStr(firstT) + ";" + DoubleToString(firstBid, _Digits) + ";" + IntegerToString(n60);
   Print("DIAG;", row);
   int h = FileOpen(DIAG_FILE, FILE_READ|FILE_WRITE|FILE_TXT|FILE_COMMON|FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   if(FileSize(h) == 0)
      FileWriteString(h, "kind;bar;now;iopen0;iclose1;bid;ask;pre_t;pre_bid;first_t;first_bid;n60\r\n");
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, row + "\r\n");
   FileClose(h);
}

//+------------------------------------------------------------------+
//| ProcessEntry - every tick, but acts only on an unresolved entry   |
//|   candle. Every entry slot gets exactly one decision row.         |
//|   Retry-able problems (missing data, failed order) are retried on |
//|   every tick until InpMaxEntryDelayMin; then the slot is skipped. |
//+------------------------------------------------------------------+
void FinishSlot(datetime bar, int sp, string decision, string reason, double mom, double lots)
{
   g_slotDone    = bar;
   g_retryReason = "";
   LogDecisionBar(IsoDate(bar), sp, decision, reason, bar, mom, lots);
}

int CountOwnPositions()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() == _Symbol && g_posInfo.Magic() == InpMagicNumber) c++;
   }
   return c;
}

bool HasOpenPosition()
{
   return CountOwnPositions() > 0;
}

// restart safety: a position of this entry slot already exists
bool HasPositionForSlot(datetime slot)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() != _Symbol || g_posInfo.Magic() != InpMagicNumber) continue;
      if(SlotOf((datetime)g_posInfo.Time()) == slot) return true;
   }
   return false;
}

void ProcessEntry(bool riskOK)
{
   datetime bar = iTime(_Symbol, WM_TF, 0);
   if(bar == 0 || !IsEntrySlot(bar) || bar == g_slotDone) return;

   if(HasPositionForSlot(bar))
   {
      g_slotDone = bar;
      return;
   }

   int    delaySec = (int)(TimeCurrent() - bar);
   int    sp       = ReadSpreadPoints();
   double mom      = EMPTY_VALUE;
   string rsn      = "";
   int    side     = 0;
   string dj       = IsoDate(bar);

   if(!riskOK)
   {
      Print("No trade ", dj, ": kill switch active");
      FinishSlot(bar, sp, "SKIP", "kill switch", mom, 0.0);
      return;
   }

   // window expired without a trade: log why
   if(delaySec > InpMaxEntryDelayMin * 60)
   {
      string why = (g_retryBar == bar && g_retryReason != "") ? g_retryReason : "late entry";
      PrintFormat("No trade %s: %s (first resolved %d s after the candle open)", dj, why, delaySec);
      FinishSlot(bar, sp, "SKIP", why, g_lastMomBar == bar ? g_lastMom : EMPTY_VALUE, 0.0);
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("LateEntry", "Weekly entry skipped: " + why, "medium");
      return;
   }

   WM_EVAL ev = EvaluateSignal(bar, mom, side, rsn);
   if(mom != EMPTY_VALUE) { g_lastMom = mom; g_lastMomBar = bar; }

   if(ev == WM_EVAL_SKIP)
   {
      Print("No trade ", dj, ": ", rsn, " | mom ", DoubleToString(mom, 4), "%");
      FinishSlot(bar, sp, "SKIP", rsn, mom, 0.0);
      return;
   }
   if(ev == WM_EVAL_RETRY)
   {
      g_retryBar = bar;  g_retryReason = rsn;
      return;                                       // retried on the next tick inside the window
   }

   // overlap guard: never more than ceil(hold / 7) open trades
   int maxConc = (InpHoldDays + 6) / 7;
   if(CountOwnPositions() >= maxConc)
   {
      PrintFormat("No trade %s: %d positions already open (max %d)", dj, CountOwnPositions(), maxConc);
      FinishSlot(bar, sp, "SKIP", "max concurrent", mom, 0.0);
      return;
   }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0)
   {
      g_retryBar = bar;  g_retryReason = "no quote";
      return;
   }

   // market closed during the first minute of the server day: retry at most once per second
   static datetime s_lastAttempt = 0;
   datetime nowT = TimeCurrent();
   if(g_retryBar == bar && nowT == s_lastAttempt) return;
   s_lastAttempt = nowT;

   string lotsWhy = "";
   double lots = CalculateLots(side, lotsWhy);
   if(lots <= 0)
   {
      FinishSlot(bar, sp, "SKIP", lotsWhy != "" ? lotsWhy : "zero lots", mom, 0.0);
      return;
   }

   // slippage tolerance expressed in bps of price, converted to points
   double px = (side > 0 ? ask : bid);
   ulong dev = (ulong)MathMax(1.0, MathRound(px * InpMaxSlippageBps / 1e4 / _Point));
   g_trade.SetDeviationInPoints(dev);

   string comment = StringFormat("ALPHACA|WEEKLYMOM|%s", dj);
   bool ok = (side > 0 ? g_trade.Buy(lots, _Symbol, 0, 0, 0, comment)
                       : g_trade.Sell(lots, _Symbol, 0, 0, 0, comment));
   uint rc = g_trade.ResultRetcode();

   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED || rc == TRADE_RETCODE_DONE_PARTIAL))
   {
      FinishSlot(bar, sp, side > 0 ? "BUY" : "SELL", "ok", mom, lots);
      DiagLog("IN");
      double spPips = sp * _Point;
      Print("=== ENTRY ", side > 0 ? "LONG" : "SHORT", " | ", dj,
            " | mom ", DoubleToString(mom, 3), "% | Lots=", DoubleToString(lots, 2),
            " @ ", DoubleToString(px, _Digits), " | entry spread=", DoubleToString(spPips, 2), " USD",
            " | exit scheduled ", TsStr(ExitTimeOf(bar)), " server");

      PushAlert(StringFormat("%s %s | WeeklyMom %s | mom %.2f%% | Lots=%.2f",
                             side > 0 ? "BUY" : "SELL", _Symbol, dj, mom, lots));
   }
   else
   {
      Print("ORDER FAILED: ", g_trade.ResultRetcodeDescription(), " (retry until the window closes)");
      g_retryBar = bar;  g_retryReason = StringFormat("order failed rc=%u", rc);
      if(g_reporter != NULL)
         g_reporter.OnOrderRejected("EntryOrder", (int)rc, g_trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Sizing - fixed fraction of capital (notional), lot-step rounding  |
//+------------------------------------------------------------------+
// notional of 1 lot in ACCOUNT currency (OrderCalcProfit works even if tick size/value are 0)
double NotionalPerLot(double price)
{
   if(price <= 0) return 0;

   // large delta on purpose: OrderCalcProfit rounds profit to 2 decimals, so a tiny delta (price*0.0001)
   // overstated the notional per lot by up to ~25% at low prices (ETH < 300) and understated the lots
   double delta  = price * 0.1;
   double profit = 0;
   if(OrderCalcProfit(ORDER_TYPE_BUY, _Symbol, 1.0, price, NormalizeDouble(price + delta, _Digits), profit) && profit > 0)
   {
      double realDelta = NormalizeDouble(price + delta, _Digits) - price;
      if(realDelta > 0) return price / realDelta * profit;
   }

   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickValue <= 0) return 0;
   return price / tickSize * tickValue;
}

double CalculateLots(int side, string &why)
{
   why = "";
   // capital used for sizing: live equity (compounding) or a fixed amount (reconciliation: engine compounding=False)
   double equity  = (InpCapitalBase == WM_CAP_FIXED ? InpFixedCapital : AccountInfoDouble(ACCOUNT_EQUITY));
   double price   = (side > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID));
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   double npl = NotionalPerLot(price);
   if(npl <= 0 || lotStep <= 0)
   {
      Print("Error: tick size/value or lot step invalid - no trade");
      why = "bad symbol specs";
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("TickDataInvalid", "Cannot compute notional per lot", "high");
      return 0;
   }

   double target = equity * InpFractionCapital;
   int    digs   = (int)MathMax(0, MathCeil(-MathLog10(lotStep)));
   double lots   = MathFloor(target / npl / lotStep + 1e-9) * lotStep;
   lots = NormalizeDouble(MathMin(lots, lotMax), digs);

   if(lots < lotMin - 1e-12)
   {
      if(InpBelowMinLot == WM_BELOW_MIN_LOT)
      {
         lots = lotMin;      // engine below_min_lot="min_lot": the trade weighs more than the fraction
         PrintFormat("Min lot forced: %.1f%% of capital (%.2f) < min lot %.4f (weighs %.1f%%)",
                     InpFractionCapital * 100.0, target, lotMin, lotMin * npl / equity * 100.0);
      }
      else
      {
         PrintFormat("No trade: %.1f%% of capital (%.2f) does not reach the min lot %.4f (needs capital >= %.0f)",
                     InpFractionCapital * 100.0, target, lotMin, lotMin * npl / InpFractionCapital);
         why = "below min lot";
         if(g_reporter != NULL)
            g_reporter.ReportHealthAlert("ZeroLots",
               StringFormat("Capital too small for min lot. Needs %.0f", lotMin * npl / InpFractionCapital), "high");
         return 0;
      }
   }

   double marginRequired = 0;
   ENUM_ORDER_TYPE ot = (side > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   if(OrderCalcMargin(ot, _Symbol, lots, price, marginRequired))
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
         if(lots < lotMin)
         {
            why = "no margin";
            return 0;
         }
      }
   }

   return lots;
}

//+------------------------------------------------------------------+
//| IsNewBar (H1)                                                     |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime currentBarTime = iTime(_Symbol, WM_TF, 0);

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
//| UpdateDashboard                                                   |
//+------------------------------------------------------------------+
void UpdateDashboard()
{
   int x = 20, y = 30, lineH = 18;

   DashLabel("ALPHACA_H1", "ALPHACA WEEKLY MOMENTUM v1.03", x, y, clrDodgerBlue, 11);
   y += lineH + 2;
   DashLabel("ALPHACA_H2", StringFormat("%s H1 | %d d lookback | %d d hold | %s", _Symbol, InpLookbackDays, InpHoldDays,
             InpDirection == WM_LONG_ONLY ? "long only" : (InpDirection == WM_BOTH ? "both legs" : "short only")),
             x, y, clrDarkGray, 9);
   y += lineH + 6;

   if(g_dailyKillActive || g_totalKillActive)
   {
      DashLabel("ALPHACA_KILL", "KILL SWITCH ACTIVE", x, y, clrRed, 11);
      y += lineH + 4;
   }
   else
   {
      DashLabel("ALPHACA_KILL", "", x, y, clrBlack, 1);
   }

   datetime nxt = NextEntrySlot();
   if(nxt > 0)
   {
      double hrs = (double)(nxt - TimeCurrent()) / 3600.0;
      DashLabel("ALPHACA_NEXT", StringFormat("Next entry slot: %s server (in %.1fh)", TsStr(nxt), MathMax(0.0, hrs)),
                x, y, clrSilver, 10);
   }
   y += lineH;

   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   string dow[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
   DashLabel("ALPHACA_CAL", StringFormat("Server: %s %02d:%02d | UTC%+d", dow[t.day_of_week], t.hour, t.min,
             ServerOffsetHours(TimeCurrent())), x, y, clrSilver, 10);
   y += lineH;

   if(g_lastMom != EMPTY_VALUE)
      DashLabel("ALPHACA_MOM", StringFormat("Last signal (%s): %+.2f%%", IsoDate(g_lastMomBar), g_lastMom),
                x, y, g_lastMom > 0 ? clrLime : clrOrangeRed, 10);
   else
      DashLabel("ALPHACA_MOM", "Last signal: none yet", x, y, clrGray, 10);
   y += lineH + 6;

   int nPos = 0;
   double pnl = 0.0, lots = 0.0;
   datetime nextExit = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i)) continue;
      if(g_posInfo.Symbol() != _Symbol || g_posInfo.Magic() != InpMagicNumber) continue;
      nPos++;
      lots += g_posInfo.Volume();
      pnl  += g_posInfo.Profit() + g_posInfo.Swap() + g_posInfo.Commission();
      datetime ex = ExitTimeOf((datetime)g_posInfo.Time());
      if(nextExit == 0 || ex < nextExit) nextExit = ex;
   }
   if(nPos > 0)
   {
      double hoursLeft = MathMax(0.0, (double)(nextExit - TimeCurrent()) / 3600.0);
      DashLabel("ALPHACA_POS", StringFormat("%d open | %.2f lots | P&L: %.0f | next exit in %.1fh", nPos, lots, pnl, hoursLeft),
                x, y, pnl >= 0 ? clrLime : clrOrangeRed, 10);
   }
   else
      DashLabel("ALPHACA_POS", "FLAT - Waiting for the next weekly entry", x, y, clrGray, 9);
   y += lineH + 6;

   if(g_reporter != NULL)
   {
      DashLabel("ALPHACA_ST1", StringFormat("Trades: %d | W: %d | L: %d",
                g_reporter.GetTotalTrades(), g_reporter.GetWins(), g_reporter.GetLosses()),
                x, y, clrSilver, 9);
      y += lineH;

      if(g_reporter.GetTotalTrades() > 0)
      {
         double wr = g_reporter.GetWinRate();
         double pf = g_reporter.GetProfitFactor();
         color wrClr = wr >= 50 ? clrLime : (wr >= 40 ? clrYellow : clrOrangeRed);
         DashLabel("ALPHACA_ST2", StringFormat("WR: %.1f%% | PF: %.2f", wr, pf), x, y, wrClr, 9);
         y += lineH;
      }
   }

   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   DashLabel("ALPHACA_EQ", "Equity: " + DoubleToString(eq, 0) + " " + AccountInfoString(ACCOUNT_CURRENCY),
             x, y, clrWhite, 9);
   y += lineH;

   double dailyDD = DailyDD();
   double totalDD = TotalDD();
   color ddClr = clrSilver;
   if(dailyDD > InpMaxDailyDD * 0.7 || totalDD > InpMaxTotalDD * 0.7) ddClr = clrOrangeRed;
   else if(dailyDD > InpMaxDailyDD * 0.5 || totalDD > InpMaxTotalDD * 0.5) ddClr = clrYellow;

   DashLabel("ALPHACA_DD", StringFormat("DD: Day=%.1f%%/%.0f%% | Total=%.1f%%/%.1f%%",
             dailyDD, InpMaxDailyDD, totalDD, InpMaxTotalDD), x, y, ddClr, 9);
   y += lineH;

   DashLabel("ALPHACA_MDD", StringFormat("Max DD hit: %.2f%%", g_maxDDHit),
             x, y, clrDarkGray, 8);
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
//+------------------------------------------------------------------+