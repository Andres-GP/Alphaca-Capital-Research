//+------------------------------------------------------------------+
//|                                          Gotobi_USDJPY_Darwinex.mq5   |
//|                                              Alphaca Capital      |
//+------------------------------------------------------------------+
//========================================================
//  STATUS: IN DEVELOPMENT (Darwinex port of the Axi EA; pending reconciliation, notebook 04)
//  Strategy ID : GOTOBI.usdjpy.cfd.v1  (variant v2_darwinex_usdjpy)
//  Vehicle     : Darwinex USDJPY (long only, M5)
//  Version: 1.04  |  Last update: 2026-11-04
//
//  CHANGES v1.04 (Darwinex port of Axi v1.03; TRADING LOGIC UNCHANGED)
//   1. Log files carry a prefix (InpFilePrefix, default "dwx_"): Common/Files is shared by every
//      MT5 terminal of the machine, so the Axi EA and this one would otherwise write to the same
//      gotobi_log.csv / gotobi_trades.csv (and a tester run would delete the live ones).
//      The calendar file is read-only and shared (UTC times, same for any broker).
//   2. Reporter strategy name "ALPHACA_GOTOBI_DWX_<symbol>" and a different magic number,
//      so the backend does not merge Axi and Darwinex.
//   3. Start-up prints the margin per lot and the implied leverage (Darwinex symbol uses
//      "Forex No Leverage" calculation: check that the margin rate allows the configured fraction).
//   4. Darwinex charges 2.5 USD/lot per deal: it is already inside 'profit' / 'commission'
//      of gotobi_trades.csv (deal history). The engine side of notebook 04 must use
//      commission_bps_per_side = 0.25 (variant v2_darwinex_usdjpy).
//
//  CHANGES v1.03
//   1. Decision log spread = spread of the CLOSED entry M5 bar (what the CSV feed stores).
//      v1.02 read the forming bar on its first tick, which differs from the stored bar
//      spread whenever the spread moves inside the bar (winter, 30 min after rollover).
//      The log row is now written on the next new bar (FlushPendingLog; also in OnDeinit).
//      Trading logic is unchanged: no decision depends on this value (no spread filter).
//
//  CHANGES v1.02
//   1. InpNoTradeDates now takes FULL JST dates "YYYY-MM-DD" (default "2023-12-25").
//      In v1.01 it was "MM-DD" and would have skipped EVERY 25-Dec (e.g. Fri 2026-12-25,
//      a real Gotobi day), while the engine only loses 2023-12-25 (no exit bar in the feed).
//      Entries that are not full dates are ignored and a warning is printed at start-up.
//
//  CHANGES v1.01 (reconciliation fixes)
//   1. InpNoTradeDates: calendar exception. On 25-Dec-2023 the feed
//      had no bar for the 09:55 JST exit (engine: "no exit bar" -> no trade) but the EA
//      entered, stayed open ~24 h through the Christmas gap and paid swap.
//      Entry is skipped on those dates (reason "calendar exception").
//   2. InpSpreadSource default = SPREAD_BAR0: the engine uses the spread stored in the
//      entry M5 bar, so the log must read the same field (SYMBOL_SPREAD at the tick
//      can differ from the bar value).
//   3. A time exit that fires later than InpEntryTolMin after the scheduled exit is
//      labelled "Time exit LATE (gap)" and raises an alert (it should never happen).
//
//  RULE (frozen, = variants/v1_axi_usdjpy.yaml / gotobi_engine.py)
//   - Gotobi days (Japan): 5, 10, 15, 20, 25 and the last day of the month.
//     If not a Japanese bank business day -> previous business day.
//     The dates are NOT computed here: they are read from the calendar
//     exported by the engine (eng.export_calendar -> gotobi_calendar_ea.csv).
//   - Entry: BUY at the open of the 07:30 JST M5 bar (= 22:30 UTC previous day)
//   - Exit : SELL at the open of the 09:55 JST M5 bar (= 00:55 UTC, Tokyo fixing)
//   - No stop, no target. Never crosses a rollover (swap = 0).
//
//  FILES (Common/Files) for reconciliation (notebook 04), names prefixed with InpFilePrefix:
//   - <prefix>gotobi_log.csv    : one row per Gotobi date, NO header, ';' separated
//                         date(JST);spread_points;decision;reason
//   - <prefix>gotobi_trades.csv : one row per closed trade, WITH header, times in SERVER time
//                         time_in;time_out;price_in;price_out;lots;profit;swap;commission;reason;source
//   - gotobi_calendar_ea.csv : INPUT. Export it with the engine and copy it to Common/Files.
//========================================================
#property copyright "Alphaca Capital"
#property version   "1.04"
#property description "GOTOBI EFFECT - USDJPY (DARWINEX) - REPORTER INTEGRATED"
#property description "Entry: 07:30 JST (22:30 UTC) on Gotobi days | Exit: 09:55 JST (00:55 UTC)"
#property description "Calendar: gotobi_calendar_ea.csv exported by gotobi_engine (Common/Files)"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include "PerformanceReporter.mqh"
#include "PerformanceDashboard.mqh"

//+------------------------------------------------------------------+
//| Enums                                                             |
//+------------------------------------------------------------------+
enum ENUM_SERVER_TZ
{
   TZ_GMT2_GMT3_US_DST = 0,   // GMT+2 winter / GMT+3 US summer (Axi, Darwinex, IC Markets, Pepperstone...)
   TZ_FIXED_OFFSET     = 1    // Fixed offset vs UTC (see InpFixedOffsetUTC)
};

enum ENUM_SPREAD_SRC
{
   SPREAD_SYMBOL = 0,         // SYMBOL_SPREAD at the decision tick (what you actually pay)
   SPREAD_BAR0   = 1          // spread field of the M5 entry bar (what the CSV feed stores)
};

//+------------------------------------------------------------------+
//| Inputs                                                            |
//+------------------------------------------------------------------+
input group "====== STRATEGY (FROZEN PARAMETERS - DO NOT MODIFY) ======"
input string          InpCalendarFile    = "gotobi_calendar_ea.csv"; // Calendar exported by the engine (Common/Files)
input int             InpEntryTolMin     = 5;            // Entry/exit bar tolerance in minutes (engine max_delay_min)
input int             InpHoldBars        = 29;           // Fallback exit: M5 bars after the entry bar (only if calendar has no exit)
input int             InpCalendarWarnDays= 30;           // Alert when the calendar covers fewer than x days ahead
input string          InpNoTradeDates    = "2023-12-25"; // Calendar exceptions, FULL JST dates "YYYY-MM-DD,YYYY-MM-DD": market closed/gapped, no entry

input group "====== EXECUTION / BROKER TIME ======"
input ENUM_SERVER_TZ  InpServerTZ        = TZ_GMT2_GMT3_US_DST; // Broker server time (Darwinex: same rule, verified on the CSV)
input int             InpFixedOffsetUTC  = 0;            // Only with fixed offset: hours server is ahead of UTC
input double          InpMaxSpreadPips   = 0.0;          // 0 = NO FILTER (frozen in v1). >0: skip if spread (pips) x InpSpreadCapScale > x
input double          InpSpreadCapScale  = 1.0;          // 1.0 live and on the Darwinex feed (no Axi-equivalent scaling needed)
input ENUM_SPREAD_SRC InpSpreadSource    = SPREAD_BAR0;  // Spread logged / filtered. BAR0 = same field the engine reads (reconciliation)
input double          InpMaxSlippageBps  = 5.0;          // Max slippage on market orders (bps of price)
input int             InpMaxEntryDelayMin= 2;            // Skip entry if first tick of the entry bar arrives later than x min

input group "====== RISK ENGINE ======"
input double          InpFractionCapital = 0.30;         // Fraction of equity per trade (2.50 = 250% notional, leveraged, variant size_fraction)
input double          InpMaxDailyDD      = 5.0;          // Daily kill switch %  (REVIEW for Darwinex: Axi Select numbers)
input double          InpMaxTotalDD      = 8.5;          // Total kill switch % (hard limit 9% = Axi Select; define the Darwinex limit)

input group "====== EMERGENCY AND MONITORING ======"
input bool            InpEnableDailyKill = true;         // Enable daily kill switch?
input bool            InpEnableTotalKill = true;         // Enable total kill switch?
input bool            InpSendPushAlerts  = true;         // Push/email notifications?
input int             InpMagicNumber     = 290412;       // Magic Number (unique per EA; Axi uses 290402)
input bool            InpShowDashboard   = true;         // Show dashboard on chart?
input bool            InpLogFiles        = true;         // Write <prefix>gotobi_log.csv / <prefix>gotobi_trades.csv (Common/Files)?
input string          InpFilePrefix      = "dwx_";       // Prefix of the log files (Common/Files is shared by every terminal of the PC)

input group "====== PERFORMANCE REPORTER ======"
input bool            InpEnableReporter  = true;         // Enable backend reporter?
input string          InpBackendUrl      = "";           // Backend URL (empty = module default)
input string          InpAuthToken       = "";           // Required backend API key
input bool            InpVerboseReporter = false;        // Reporter debug logs
input int             InpHeartbeatSecs   = 3600;         // Heartbeat interval (seconds)
input int             InpMaxBarsNoTrade  = 4608;         // Inactivity alert threshold (M5 bars, ~16 days; Gotobi gaps are <= ~10 days)

//+------------------------------------------------------------------+
//| Constants / Globals                                               |
//+------------------------------------------------------------------+
string LogFileName()    { return InpFilePrefix + "gotobi_log.csv"; }
string TradesFileName() { return InpFilePrefix + "gotobi_trades.csv"; }

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

// Gotobi calendar (one row per Gotobi date, ascending)
int                  g_calN = 0;
string               g_calDate[];        // JST date "YYYY-MM-DD"
string               g_calLabel[];       // 5, 10, ..., EOM
bool                 g_calShifted[];
datetime             g_calEntryUtc[];    // 22:30 UTC of the previous day
datetime             g_calExitUtc[];     // 00:55 UTC
int                  g_calPtr = 0;       // next row not yet decided

// exit time cache of the open position
datetime             g_posOpenCached = 0;
datetime             g_posExitUtc    = 0;
datetime             g_lateAlertFor  = 0; // position (open time) already alerted for a late exit

// pending decision-log row (written on the next new bar, when the entry bar is closed)
bool                 g_pend = false;
string               g_pDate = "";
string               g_pDec  = "";
string               g_pRsn  = "";
int                  g_pSp   = -1;
datetime             g_pBar  = 0;         // entry bar open time (server time)

//+------------------------------------------------------------------+
//| Server time -> UTC (same US DST rule as the engine)               |
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

datetime ServerToUTC(datetime server) { return server - ServerOffsetHours(server) * 3600; }

string TsStr(datetime t)
{
   MqlDateTime s;
   TimeToStruct(t, s);
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d", s.year, s.mon, s.day, s.hour, s.min, s.sec);
}

string UtcStr(datetime server) { return TsStr(ServerToUTC(server)); }

double PipSize() { return (_Digits == 3 || _Digits == 5) ? _Point * 10.0 : _Point; }

//+------------------------------------------------------------------+
//| Calendar exceptions (InpNoTradeDates, FULL "YYYY-MM-DD" JST date) |
//+------------------------------------------------------------------+
bool IsExcludedDate(string dateJst)
{
   if(StringLen(InpNoTradeDates) == 0 || StringLen(dateJst) < 10) return false;
   string d10 = StringSubstr(dateJst, 0, 10);
   string parts[];
   int n = StringSplit(InpNoTradeDates, ',', parts);
   for(int i = 0; i < n; i++)
   {
      string p = parts[i];
      StringTrimLeft(p);
      StringTrimRight(p);
      if(p == d10) return true;
   }
   return false;
}

// start-up check: every exception must be a full date (a bare "MM-DD" is ignored, never a yearly rule)
void ValidateNoTradeDates()
{
   if(StringLen(InpNoTradeDates) == 0) return;
   string parts[];
   int n = StringSplit(InpNoTradeDates, ',', parts);
   for(int i = 0; i < n; i++)
   {
      string p = parts[i];
      StringTrimLeft(p);
      StringTrimRight(p);
      if(StringLen(p) != 10 || StringGetCharacter(p, 4) != '-' || StringGetCharacter(p, 7) != '-')
         PrintFormat("WARNING: InpNoTradeDates entry '%s' is not a full date YYYY-MM-DD: IGNORED", p);
   }
}

//+------------------------------------------------------------------+
//| Calendar loading                                                  |
//|   header: date_jst;label;shifted;entry_utc;exit_utc;              |
//|           entry_server;exit_server   (eng.export_calendar)        |
//+------------------------------------------------------------------+
datetime ParseTs(string s)
{
   StringReplace(s, "-", ".");
   return StringToTime(s);
}

bool LoadCalendar()
{
   g_calN = 0;
   ArrayResize(g_calDate, 0);  ArrayResize(g_calLabel, 0);   ArrayResize(g_calShifted, 0);
   ArrayResize(g_calEntryUtc, 0); ArrayResize(g_calExitUtc, 0);

   int h = FileOpen(InpCalendarFile, FILE_READ|FILE_CSV|FILE_COMMON|FILE_ANSI, ';');
   if(h == INVALID_HANDLE)
   {
      PrintFormat("CALENDAR ERROR: cannot open '%s' in Common/Files (err %d). Export it with eng.export_calendar() and copy it there.",
                  InpCalendarFile, GetLastError());
      return false;
   }

   for(int k = 0; k < 7 && !FileIsEnding(h); k++) FileReadString(h);   // header

   while(!FileIsEnding(h))
   {
      string d    = FileReadString(h);
      string lab  = FileReadString(h);
      string sh   = FileReadString(h);
      string ein  = FileReadString(h);
      string eout = FileReadString(h);
      string sin_ = FileReadString(h);   // entry_server (unused: UTC is the reference)
      string sout = FileReadString(h);   // exit_server  (unused)
      if(StringLen(d) < 10 || StringLen(ein) < 16 || StringLen(eout) < 16) continue;

      datetime tin = ParseTs(ein), tout = ParseTs(eout);
      if(tin == 0 || tout == 0 || tout <= tin) continue;

      int n = g_calN + 1;
      ArrayResize(g_calDate, n);  ArrayResize(g_calLabel, n);   ArrayResize(g_calShifted, n);
      ArrayResize(g_calEntryUtc, n); ArrayResize(g_calExitUtc, n);
      g_calDate[g_calN]     = d;
      g_calLabel[g_calN]    = lab;
      g_calShifted[g_calN]  = (StringToInteger(sh) != 0);
      g_calEntryUtc[g_calN] = tin;
      g_calExitUtc[g_calN]  = tout;
      g_calN = n;
   }
   FileClose(h);

   if(g_calN == 0)
   {
      Print("CALENDAR ERROR: no valid rows in ", InpCalendarFile);
      return false;
   }
   for(int i = 1; i < g_calN; i++)
      if(g_calEntryUtc[i] <= g_calEntryUtc[i - 1])
      {
         Print("CALENDAR ERROR: rows must be strictly ascending (row ", i + 1, ")");
         return false;
      }

   PrintFormat("Calendar loaded: %d Gotobi dates | %s -> %s (UTC entry)",
               g_calN, TsStr(g_calEntryUtc[0]), TsStr(g_calEntryUtc[g_calN - 1]));
   return true;
}

// first calendar row whose entry window has not yet closed at 'nowUtc'
int FirstPendingRow(datetime nowUtc)
{
   int p = 0;
   while(p < g_calN && g_calEntryUtc[p] + InpEntryTolMin * 60 < nowUtc) p++;
   return p;
}

// exit time (UTC) of the position opened at 'openUtc': first calendar exit after the open
datetime ExitUtcFor(datetime openUtc)
{
   for(int i = 0; i < g_calN; i++)
      if(g_calExitUtc[i] > openUtc && g_calEntryUtc[i] <= openUtc + 3600)
         return g_calExitUtc[i];
   return 0;
}

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   if(PeriodSeconds(_Period) != 300)
   {
      Print("ERROR: this EA must run on an M5 chart");
      return(INIT_FAILED);
   }
   if(StringFind(_Symbol, "USDJPY") != 0)
      Print("WARNING: this EA is built for USDJPY; current symbol is ", _Symbol);

   if(InpFractionCapital < 0.01 || InpFractionCapital > 10.0)
   {
      Print("Fraction of capital out of range (0.01-10.0)");
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpEntryTolMin < 0 || InpHoldBars < 1)
   {
      Print("Invalid entry tolerance / hold bars");
      return(INIT_PARAMETERS_INCORRECT);
   }

   if(!LoadCalendar())
      return(INIT_FAILED);

   ValidateNoTradeDates();

   // each tester run starts with clean reconciliation files (no duplicated dates)
   // (only THIS EA's prefixed files: the Axi EA's logs are not touched)
   if(MQLInfoInteger(MQL_TESTER) && InpLogFiles)
   {
      FileDelete(LogFileName(), FILE_COMMON);
      FileDelete(TradesFileName(), FILE_COMMON);
   }

   g_trade.SetExpertMagicNumber(InpMagicNumber);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   g_lastBarTime     = 0;
   g_dailyKillActive = false;
   g_totalKillActive = false;
   g_killReason      = "";
   g_posOpenCached   = 0;
   g_posExitUtc      = 0;
   g_lateAlertFor    = 0;
   g_pend            = false;

   double eq0        = AccountInfoDouble(ACCOUNT_EQUITY);
   g_peakEquity      = eq0;
   g_dayStartEquity  = eq0;
   g_dayKey          = DayKeyOf(TimeCurrent());
   g_maxDDHit        = 0;

   g_calPtr = FirstPendingRow(ServerToUTC(TimeCurrent()));

   // live/demo: verify configured broker time matches the real server time
   if(!MQLInfoInteger(MQL_TESTER))
   {
      int real = (int)MathRound((double)(TimeTradeServer() - TimeGMT()) / 3600.0);
      int conf = ServerOffsetHours(TimeTradeServer());
      if(real != conf)
         Alert(StringFormat("ALPHACA Gotobi: server is UTC%+d but EA is configured for UTC%+d. Check InpServerTZ / InpFixedOffsetUTC.",
                            real, conf));
      else
         PrintFormat("Broker time OK (server = UTC%+d)", real);
   }

   if(InpEnableReporter)
   {
      string strategyName = "ALPHACA_GOTOBI_DWX_" + _Symbol;
      g_reporter = new PerformanceReporter(
         InpBackendUrl, InpAuthToken,
         strategyName, _Symbol, "M5", 100, "demo"
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

   Print("=== ALPHACA GOTOBI USDJPY DARWINEX v1.04 ===");
   Print("Symbol: ", _Symbol, " | Magic: ", InpMagicNumber, " | Log prefix: '", InpFilePrefix, "'");
   PrintFormat("Entry: 07:30 JST (22:30 UTC) | Exit: 09:55 JST (00:55 UTC) | size %.0f%% | spread cap %s | next row %d/%d",
               InpFractionCapital * 100.0,
               InpMaxSpreadPips > 0 ? StringFormat("%.1f pips", InpMaxSpreadPips) : "none",
               g_calPtr + 1, g_calN);
   if(StringLen(InpNoTradeDates) > 0)
      Print("Calendar exceptions (no entry on these JST dates): ", InpNoTradeDates);

   // capital needed so that the minimum lot does not exceed the target fraction
   double askInit = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double npl = NotionalPerLot(askInit);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(npl > 0)
   {
      PrintFormat("Notional per lot: %.2f %s | min lot %.4f | min equity for %.0f%% sizing: %.0f %s",
                  npl, AccountInfoString(ACCOUNT_CURRENCY), minLot, InpFractionCapital * 100.0,
                  minLot * npl / InpFractionCapital, AccountInfoString(ACCOUNT_CURRENCY));

      // Darwinex: calculation mode "Forex No Leverage" -> check the real margin per lot (implied leverage)
      double mrg = 0;
      if(askInit > 0 && OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, 1.0, askInit, mrg) && mrg > 0)
         PrintFormat("Margin per lot: %.2f %s (implied leverage ~1:%.1f). Needed margin at the configured fraction: %.1f%% of equity",
                     mrg, AccountInfoString(ACCOUNT_CURRENCY), npl / mrg, InpFractionCapital * mrg / npl * 100.0);
   }

   CheckCalendarHorizon();
   PushAlert("EA STARTED | " + _Symbol);

   if(InpShowDashboard) UpdateDashboard();

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
         g_reporter.OnBarUpdate(Bars(_Symbol, PERIOD_M5));

      ProcessCalendar(riskOK);           // decides (and logs) every Gotobi date, also under a kill
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
      CheckCalendarHorizon();
   }

   double dd = TotalDD();
   if(dd > g_maxDDHit) g_maxDDHit = dd;
}

//+------------------------------------------------------------------+
//| Calendar horizon: alert before the exported calendar runs out     |
//+------------------------------------------------------------------+
void CheckCalendarHorizon()
{
   if(MQLInfoInteger(MQL_TESTER) || g_calN == 0) return;
   datetime nowUtc = ServerToUTC(TimeCurrent());
   int daysLeft = (int)((g_calExitUtc[g_calN - 1] - nowUtc) / 86400);
   if(daysLeft >= InpCalendarWarnDays) return;

   string msg = StringFormat("Gotobi calendar covers only %d more days. Re-export gotobi_calendar_ea.csv", daysLeft);
   Print("WARNING: ", msg);
   PushAlert(msg);
   if(g_reporter != NULL) g_reporter.ReportHealthAlert("CalendarExpiring", msg, "high");
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
// one line per Gotobi date, whether the EA trades or not.
// NO header. Columns = notebook 04 LOG_COLS: date;spread_points;decision;reason
void LogDecision(string dateJst, int spreadPts, string decision, string reason)
{
   if(!InpLogFiles) return;
   int h = FileOpen(LogFileName(), FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ';');
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, dateJst, (spreadPts >= 0 ? IntegerToString(spreadPts) : ""), decision, reason);
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
      if(CopyRates(_Symbol, PERIOD_M5, g_pBar, 1, r) == 1 && r[0].time == g_pBar)
         sp = (int)r[0].spread;
   }
   LogDecision(g_pDate, sp, g_pDec, g_pRsn);
}

void LogDecisionBar(string dateJst, int spreadPts, string decision, string reason, datetime entryBar)
{
   FlushPendingLog();                    // never lose a previous pending row
   g_pend  = true;
   g_pDate = dateJst;
   g_pSp   = spreadPts;
   g_pDec  = decision;
   g_pRsn  = reason;
   g_pBar  = entryBar;
}

// one line per closed trade (WITH header; times in SERVER time = notebook 04 DEAL_TIME_MODE "mt5_server_ny")
void LogTrade(string reason, double lots, double entryPrice, double exitPrice, double profit,
              double swap, double commission, datetime entryTime, datetime exitTime, bool fromDeals)
{
   if(!InpLogFiles) return;
   int h = FileOpen(TradesFileName(), FILE_READ|FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI, ';');
   if(h == INVALID_HANDLE) return;
   if(FileSize(h) == 0)
      FileWrite(h, "time_in", "time_out", "price_in", "price_out", "lots", "profit", "swap", "commission", "reason", "source");
   FileSeek(h, 0, SEEK_END);
   FileWrite(h, TsStr(entryTime), TsStr(exitTime),
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
               " | commission=", DoubleToString(commission, 2),
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
//| CheckExit - time exit at the open of the 09:55 JST bar (00:55 UTC)|
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

   // exit time of this position (cached: recomputed only when the position changes)
   if(opened != g_posOpenCached)
   {
      g_posOpenCached = opened;
      g_posExitUtc    = ExitUtcFor(ServerToUTC(opened));
      if(g_posExitUtc == 0)
      {
         // calendar has no exit for this position: fall back to N bars after the entry bar
         datetime entryBar = (datetime)((long)opened - (long)opened % 300);
         g_posExitUtc = ServerToUTC(entryBar) + (datetime)InpHoldBars * 300;
         Print("WARNING: no calendar exit for this position, using entry bar + ", InpHoldBars, " bars");
      }
   }

   datetime barNowUtc = ServerToUTC(iTime(_Symbol, PERIOD_M5, 0));
   // if the exact bar is missing, closes on the next available one
   if(barNowUtc >= g_posExitUtc)
   {
      // engine rule: the exit bar must exist within max_delay_min. A later exit means a data/market gap:
      // the trade does not match the engine (and may have crossed a rollover) -> label it and alert once.
      bool late = ((barNowUtc - g_posExitUtc) > InpEntryTolMin * 60);
      if(late && g_lateAlertFor != opened)
      {
         g_lateAlertFor = opened;
         string msg = StringFormat("Gotobi LATE EXIT: scheduled %s UTC, first bar %s UTC (market/data gap). Check swap and reconciliation.",
                                   TsStr(g_posExitUtc), TsStr(barNowUtc));
         Print("WARNING: ", msg);
         PushAlert(msg);
         if(g_reporter != NULL) g_reporter.ReportHealthAlert("LateExit", msg, "high");
      }
      CloseAllAndReport(late ? "Time exit LATE (gap)" : "Time exit 09:55 JST");
   }
}

//+------------------------------------------------------------------+
//| ProcessCalendar - on every new M5 bar                             |
//|   Every Gotobi date gets exactly one decision row in the log.     |
//|   Engine parity: entry bar = first bar >= entry time within       |
//|   InpEntryTolMin, otherwise "no entry bar".                       |
//+------------------------------------------------------------------+
void ProcessCalendar(bool riskOK)
{
   datetime barTime = iTime(_Symbol, PERIOD_M5, 0);
   if(barTime == 0) return;
   datetime barUtc = ServerToUTC(barTime);

   while(g_calPtr < g_calN)
   {
      int row = g_calPtr;
      if(barUtc < g_calEntryUtc[row]) break;                           // not yet

      g_calPtr++;
      if(barUtc - g_calEntryUtc[row] > InpEntryTolMin * 60)            // window missed (data gap / EA offline)
      {
         Print("No trade ", g_calDate[row], ": no entry bar within tolerance");
         LogDecision(g_calDate[row], -1, "SKIP", "no entry bar");
         continue;
      }

      DecideEntry(row, barTime, riskOK);
      break;
   }
}

//+------------------------------------------------------------------+
//| Spread helpers                                                    |
//+------------------------------------------------------------------+
// spread (points) at decision time. With SPREAD_BAR0 the logged value is replaced
// by the closed-bar value in FlushPendingLog; this one is only the fallback.
int ReadSpreadPoints()
{
   if(InpSpreadSource == SPREAD_BAR0)
   {
      MqlRates r[];
      if(CopyRates(_Symbol, PERIOD_M5, 0, 1, r) == 1) return (int)r[0].spread;
   }
   return (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
}

//+------------------------------------------------------------------+
//| DecideEntry                                                       |
//+------------------------------------------------------------------+
void DecideEntry(int row, datetime barTime, bool riskOK)
{
   string dj  = g_calDate[row];
   string lab = g_calLabel[row];
   int    sp  = ReadSpreadPoints();
   double spPips = sp * _Point / PipSize();

   if(!riskOK)
   {
      Print("No trade ", dj, ": kill switch active");
      LogDecisionBar(dj, sp, "SKIP", "kill switch", barTime);
      return;
   }

   if(HasOpenPosition())
   {
      Print("No trade ", dj, ": a position is still open");
      LogDecisionBar(dj, sp, "SKIP", "position open", barTime);
      return;
   }

   if(IsExcludedDate(dj))
   {
      Print("No trade ", dj, ": calendar exception (InpNoTradeDates = ", InpNoTradeDates, ")");
      LogDecisionBar(dj, sp, "SKIP", "calendar exception", barTime);
      return;
   }

   if((TimeCurrent() - barTime) > InpMaxEntryDelayMin * 60)
   {
      PrintFormat("No trade %s: first tick of the entry bar arrived %d s late", dj, (int)(TimeCurrent() - barTime));
      LogDecisionBar(dj, sp, "SKIP", "late entry", barTime);
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("LateEntry", "Gotobi entry bar first tick too late, entry skipped", "medium");
      return;
   }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid <= 0 || ask <= 0)
   {
      LogDecisionBar(dj, sp, "SKIP", "no quote", barTime);
      return;
   }

   if(InpMaxSpreadPips > 0.0 && spPips * InpSpreadCapScale > InpMaxSpreadPips)
   {
      PrintFormat("No trade %s: spread %.2f pips (x%.2f) > cap %.2f pips", dj, spPips, InpSpreadCapScale, InpMaxSpreadPips);
      LogDecisionBar(dj, sp, "SKIP", "spread wide", barTime);
      if(g_reporter != NULL)
         g_reporter.ReportHealthAlert("WideSpread",
            StringFormat("spread=%.2f pips cap=%.2f pips", spPips * InpSpreadCapScale, InpMaxSpreadPips), "high");
      return;
   }

   double lots = CalculateLots();
   if(lots <= 0)
   {
      LogDecisionBar(dj, sp, "SKIP", "zero lots", barTime);
      return;
   }

   // slippage tolerance expressed in bps of price, converted to points
   ulong dev = (ulong)MathMax(1.0, MathRound(ask * InpMaxSlippageBps / 1e4 / _Point));
   g_trade.SetDeviationInPoints(dev);

   string comment = StringFormat("ALPHACA|GOTOBI|%s", lab);
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
      LogDecisionBar(dj, sp, "BUY", "ok", barTime);
      Print("=== ENTRY LONG | ", dj, " (", lab, g_calShifted[row] ? ", shifted" : "", ")",
            " | Lots=", DoubleToString(lots, 2), " @ ", DoubleToString(ask, _Digits),
            " | entry spread=", DoubleToString(spPips, 2), " pips");

      PushAlert(StringFormat("BUY %s | Gotobi %s | Lots=%.2f | spread %.2f pips",
                             _Symbol, lab, lots, spPips));
   }
   else
   {
      Print("BUY FAILED: ", g_trade.ResultRetcodeDescription());
      LogDecisionBar(dj, sp, "SKIP", "buy failed", barTime);
      if(g_reporter != NULL)
      {
         g_reporter.ReportExecutionUpdate(signalId, "rejected", 0, 0, g_trade.ResultRetcodeDescription());
         g_reporter.OnOrderRejected("EntryBuy", g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
//| Sizing - fixed fraction of equity (notional), integer lots        |
//+------------------------------------------------------------------+
// notional of 1 lot in ACCOUNT currency (OrderCalcProfit works even if tick size/value are 0)
double NotionalPerLot(double price)
{
   if(price <= 0) return 0;

   double delta  = price * 0.0001;
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
//| IsNewBar (M5)                                                     |
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime currentBarTime = iTime(_Symbol, PERIOD_M5, 0);

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
   datetime nowUtc = ServerToUTC(TimeCurrent());
   MqlDateTime utc;
   TimeToStruct(nowUtc, utc);
   string dow[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
   string nextEntry = g_calPtr < g_calN
      ? StringFormat("Next Gotobi: %s (%s%s) | in %.1fh", g_calDate[g_calPtr], g_calLabel[g_calPtr], g_calShifted[g_calPtr] ? ", shifted" : "", MathMax(0.0, (double)(g_calEntryUtc[g_calPtr] - nowUtc) / 3600.0))
      : "Calendar exhausted | re-export calendar";
   string clock = StringFormat("UTC: %s %02d:%02d | server UTC%+d", dow[utc.day_of_week], utc.hour, utc.min, ServerOffsetHours(TimeCurrent()));

   int nPos = 0;
   double lots = 0.0, pnl = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_posInfo.SelectByIndex(i) || g_posInfo.Symbol() != _Symbol || g_posInfo.Magic() != InpMagicNumber) continue;
      nPos++;
      lots += g_posInfo.Volume();
      pnl += g_posInfo.Profit() + g_posInfo.Swap() + g_posInfo.Commission();
   }
   double hoursLeft = g_posExitUtc > 0 ? MathMax(0.0, (double)(g_posExitUtc - nowUtc) / 3600.0) : 0.0;
   string position = nPos > 0
      ? StringFormat("Position: %d open | %.2f lots | P&L %.2f | exit in %.1fh", nPos, lots, pnl, hoursLeft)
      : "Position: flat | waiting for next calendar entry";
   double spreadPips = 0.0;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(bid > 0 && ask > bid) spreadPips = (ask - bid) / PipSize();
   string spread = (bid > 0 && ask > bid)
      ? StringFormat("Current spread: %.2f pips | cap %.2f", spreadPips, InpMaxSpreadPips)
      : "Current spread: unavailable";
   string tradeCount = g_reporter != NULL
      ? StringFormat("Closed trades: %d | wins %d | losses %d", g_reporter.GetTotalTrades(), g_reporter.GetWins(), g_reporter.GetLosses())
      : "Closed trades: unavailable | reporter off";
   string tradeQuality = g_reporter != NULL
      ? StringFormat("Win rate: %.1f%% | profit factor: %.2f", g_reporter.GetWinRate(), g_reporter.GetProfitFactor())
      : "";
   double dailyDD = DailyDD(), totalDD = TotalDD();
   color ddColor = (dailyDD >= InpMaxDailyDD * 0.7 || totalDD >= InpMaxTotalDD * 0.7) ? clrOrangeRed
      : (dailyDD >= InpMaxDailyDD * 0.5 || totalDD >= InpMaxTotalDD * 0.5) ? clrYellow : clrSilver;
   g_dashboard.Update("ALPHACA | GOTOBI DARWINEX", _Symbol + " | M5 | long only",
      state, stateColor, reporterState,
      nextEntry, g_calPtr < g_calN ? clrSilver : clrOrangeRed, clock, clrSilver, spread, clrSilver,
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
