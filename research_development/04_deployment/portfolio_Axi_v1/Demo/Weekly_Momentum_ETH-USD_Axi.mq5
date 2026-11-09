//+------------------------------------------------------------------+
//| WeeklyMomentum_ETHUSD.mq5                                        |
//| Weekly time-series momentum, Axi ETHUSD CFD (MT5, hedging)       |
//|                                                                  |
//| Mirror of weekly_momentum_engine.py (v2) for variant             |
//| v2_ethusd_long: lookback 31 d / hold 11 d / long only.           |
//|                                                                  |
//| RULE (all on MT5 SERVER time, Axi = New York + 7 h):             |
//|  - Entry slot: every Monday 00:00 server, at the OPEN of that    |
//|    H1 candle (first tick of the candle).                         |
//|  - Signal at the CLOSE of the candle before the entry (H1 bar 1):|
//|      mom = close[bar 1] / close[candle before the entry candle   |
//|            of `lookback` days earlier] - 1                       |
//|    LONG if mom > 0, SHORT if mom < 0 (direction input).          |
//|  - Exit at the OPEN of the 00:00 server candle `hold` days after |
//|    the entry day. No stop, no target, no filters.                |
//|  - hold > 7 => consecutive weekly trades OVERLAP by design (max  |
//|    ceil(hold/7) open at once): needs a HEDGING account.          |
//|  - Spread / swap: paid by the broker (engine models the same).   |
//|                                                                  |
//| LOGS (FILE_COMMON, for notebook 04 reconciliation):              |
//|  - InpLogFile   : one row per entry slot, NO header, sep ';'     |
//|      date;spread_points;decision;reason;mom_ret_pct;lots;price   |
//|      decision = BUY | SELL | SKIP                                |
//|  - InpDealsFile : one row per closed trade, WITH header, sep ';' |
//|      time_in;time_out;price_in;price_out;type;lots;profit;swap;  |
//|      commission   (times in MT5 SERVER time)                     |
//+------------------------------------------------------------------+
#property copyright "Alphaca Capital"
#property version   "1.00"
#property description "Weekly Momentum ETHUSD (v2_ethusd_long): 31d lookback / 11d hold / long only"

#include <Trade\Trade.mqh>

enum ENUM_WM_DIRECTION { WM_LONG_ONLY = 0, WM_BOTH = 1, WM_SHORT_ONLY = 2 };
enum ENUM_WM_BELOW_MIN { WM_BELOW_SKIP = 0, WM_BELOW_MIN_LOT = 1 };
enum ENUM_WM_CAPITAL   { WM_CAP_EQUITY = 0, WM_CAP_BALANCE = 1, WM_CAP_FIXED = 2 };

input group "Rule (frozen by the research: do not re-tune)"
input int               InpLookbackDays      = 31;            // lookback_days
input int               InpHoldDays          = 11;            // hold_days
input ENUM_WM_DIRECTION InpDirection         = WM_LONG_ONLY;  // direction (v2_ethusd_long = long only)
input int               InpEntryDow          = 1;             // entry weekday, MT5 numbering (0=Sun, 1=Mon)
input int               InpEntryHour         = 0;             // entry hour, SERVER time
input int               InpMaxEntryDelaySec  = 3600;          // retry window after the candle open (max 3600)

input group "Sizing (engine: size_fraction, lot_step, min_lot, below_min_lot)"
input double            InpSizeFraction      = 0.05;          // fraction of capital per trade (notional)
input ENUM_WM_CAPITAL   InpCapitalBase       = WM_CAP_EQUITY; // capital used for sizing
input double            InpFixedCapital      = 3500.0;        // used only with WM_CAP_FIXED (no compounding)
input ENUM_WM_BELOW_MIN InpBelowMinLot       = WM_BELOW_MIN_LOT; // if fraction < min lot: skip | trade min lot
input double            InpFixedLots         = 0.0;           // >0 overrides the sizing (tests only)
input double            InpQuoteToAccount    = 1.0;           // price -> account currency (ETHUSD / USD account = 1)

input group "Execution"
input long              InpMagic             = 20260107;
input int               InpDeviationPoints   = 100;
input string            InpComment           = "WM_ETH";

input group "Logs for reconciliation (Common\\Files)"
input bool              InpWriteLogs         = true;
input string            InpLogFile           = "weekly_momentum_log.csv";
input string            InpDealsFile         = "weekly_momentum_trades.csv";

//--- constants / state
const ENUM_TIMEFRAMES WM_TF = PERIOD_H1;
CTrade   g_trade;
datetime g_decided_slot = 0;       // entry candle already resolved (trade opened or final skip logged)
string   g_last_reason  = "";

enum WM_EVAL { WM_EVAL_TRADE = 0, WM_EVAL_SKIP = 1, WM_EVAL_RETRY = 2 };

//+------------------------------------------------------------------+
//| helpers                                                          |
//+------------------------------------------------------------------+
string IsoDate(const datetime t)
{
   MqlDateTime d; TimeToStruct(t, d);
   return StringFormat("%04d-%02d-%02d", d.year, d.mon, d.day);
}

string IsoTime(const datetime t)
{
   MqlDateTime d; TimeToStruct(t, d);
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d", d.year, d.mon, d.day, d.hour, d.min, d.sec);
}

// 00:00 (InpEntryHour:00) server of the day of t
datetime SlotOf(const datetime t)
{
   MqlDateTime d; TimeToStruct(t, d);
   d.hour = InpEntryHour; d.min = 0; d.sec = 0;
   return StructToTime(d);
}

bool IsEntrySlot(const datetime bar_time)
{
   MqlDateTime d; TimeToStruct(bar_time, d);
   return (d.day_of_week == InpEntryDow && d.hour == InpEntryHour && d.min == 0);
}

void AppendLine(const string file, const string line, const string header = "")
{
   if(!InpWriteLogs) return;
   int h = FileOpen(file, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON |
                          FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE)
   {
      PrintFormat("WM: cannot open %s (err %d)", file, GetLastError());
      return;
   }
   if(FileSize(h) == 0 && header != "")
      FileWriteString(h, header + "\n");
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, line + "\n");
   FileClose(h);
}

void LogDecision(const datetime slot, const string decision, const string reason,
                 const double mom, const double lots, const double price)
{
   string line = StringFormat("%s;%d;%s;%s;%s;%s;%s",
                              IsoDate(slot),
                              (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD),
                              decision, reason,
                              (mom == EMPTY_VALUE ? "" : DoubleToString(mom, 6)),
                              DoubleToString(lots, 2),
                              (price > 0 ? DoubleToString(price, _Digits) : ""));
   AppendLine(InpLogFile, line);
   PrintFormat("WM: %s | %s | %s | mom %s%% | lots %.2f", IsoDate(slot), decision, reason,
               (mom == EMPTY_VALUE ? "n/a" : DoubleToString(mom, 4)), lots);
}

bool HasPositionForSlot(const datetime slot)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(SlotOf((datetime)PositionGetInteger(POSITION_TIME)) == slot) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| signal: same definition as the engine's _momentum()              |
//|  - signal candle = candle immediately before the entry candle    |
//|  - reference     = candle before the entry-hour candle `lookback`|
//|                    days earlier (both must exist and be 1 h)     |
//+------------------------------------------------------------------+
WM_EVAL EvaluateSignal(const datetime t0, double &mom, int &side, string &reason)
{
   mom = EMPTY_VALUE; side = 0; reason = "";

   // signal candle: contiguous (exactly 1 h before the entry candle)
   if(iTime(_Symbol, WM_TF, 1) != t0 - 3600)
   {
      reason = "no signal bar";
      return WM_EVAL_RETRY;
   }
   // anchor = entry-hour candle `lookback` days earlier (server wall clock, DST-free by construction)
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
//| lots: same as the engine's lot_size()                            |
//+------------------------------------------------------------------+
double ComputeLots(const double price, string &reason)
{
   double vmin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double csize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(vstep <= 0 || csize <= 0 || price <= 0 || InpQuoteToAccount <= 0)
   {
      reason = "bad symbol specs";
      return 0.0;
   }
   if(InpFixedLots > 0.0)
      return MathMin(vmax, MathMax(vmin, NormalizeDouble(MathFloor(InpFixedLots / vstep + 1e-9) * vstep, 8)));

   double capital = AccountInfoDouble(ACCOUNT_EQUITY);
   if(InpCapitalBase == WM_CAP_BALANCE) capital = AccountInfoDouble(ACCOUNT_BALANCE);
   if(InpCapitalBase == WM_CAP_FIXED)   capital = InpFixedCapital;
   if(capital <= 0)
   {
      reason = "no capital";
      return 0.0;
   }

   double raw  = capital * InpSizeFraction / (price * InpQuoteToAccount * csize);
   double lots = NormalizeDouble(MathFloor(raw / vstep + 1e-9) * vstep, 8);
   if(lots < vmin - 1e-12)
   {
      if(InpBelowMinLot == WM_BELOW_MIN_LOT) return vmin;
      reason = "below min lot";
      return 0.0;
   }
   return MathMin(lots, vmax);
}

//+------------------------------------------------------------------+
//| entry                                                            |
//+------------------------------------------------------------------+
// returns true when the order was accepted
bool OpenTrade(const int side, const double mom, string &reason, double &lots_out, double &price_out)
{
   lots_out = 0.0; price_out = 0.0;
   double price = (side > 0 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID));
   double lots  = ComputeLots(price, reason);
   if(lots <= 0.0)
   {
      if(reason == "") reason = "zero lots";
      return false;
   }
   ENUM_ORDER_TYPE ot = (side > 0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   double margin = 0.0;
   if(!OrderCalcMargin(ot, _Symbol, lots, price, margin) || margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
   {
      reason = "no margin";
      return false;
   }
   bool ok = (side > 0 ? g_trade.Buy(lots, _Symbol, 0.0, 0.0, 0.0, InpComment)
                       : g_trade.Sell(lots, _Symbol, 0.0, 0.0, 0.0, InpComment));
   uint rc = g_trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED && rc != TRADE_RETCODE_DONE_PARTIAL))
   {
      reason = StringFormat("order failed rc=%u", rc);
      return false;
   }
   lots_out  = lots;
   price_out = g_trade.ResultPrice();
   if(price_out <= 0) price_out = price;
   return true;
}

void TryEntry(const datetime t0)
{
   double mom; int side; string reason;
   WM_EVAL ev = EvaluateSignal(t0, mom, side, reason);
   double lots = 0.0, px = 0.0;

   if(ev == WM_EVAL_SKIP)
   {
      LogDecision(t0, "SKIP", reason, mom, 0.0, 0.0);
      g_decided_slot = t0;
      return;
   }

   if(ev == WM_EVAL_TRADE)
   {
      if(OpenTrade(side, mom, reason, lots, px))
      {
         LogDecision(t0, (side > 0 ? "BUY" : "SELL"), "ok", mom, lots, px);
         g_decided_slot = t0;
         return;
      }
      // order / margin / lots problem: fall through to the retry logic
   }

   // RETRY (missing data or failed order): keep trying until the window ends, then log the final skip
   g_last_reason = reason;
   int delay = (int)(TimeCurrent() - t0);
   if(delay > MathMin(InpMaxEntryDelaySec, 3600) - 1)
   {
      LogDecision(t0, "SKIP", reason, mom, 0.0, 0.0);
      g_decided_slot = t0;
   }
}

//+------------------------------------------------------------------+
//| exit: `hold` days after the entry-day slot, at the first tick    |
//+------------------------------------------------------------------+
void ManageExits()
{
   datetime now = TimeCurrent();
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      datetime exit_t = SlotOf((datetime)PositionGetInteger(POSITION_TIME)) + (datetime)((long)InpHoldDays * 86400);
      if(now >= exit_t)
      {
         if(!g_trade.PositionClose(tk))
            PrintFormat("WM: close failed ticket %I64u rc=%u (%s)", tk, g_trade.ResultRetcode(), g_trade.ResultRetcodeDescription());
      }
   }
}

//+------------------------------------------------------------------+
//| events                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   if(InpLookbackDays < 1 || InpHoldDays < 1 || InpSizeFraction <= 0.0)
   {
      Print("WM: invalid inputs (lookback / hold / size fraction).");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpEntryDow < 0 || InpEntryDow > 6 || InpEntryHour < 0 || InpEntryHour > 23)
   {
      Print("WM: invalid entry weekday / hour.");
      return INIT_PARAMETERS_INCORRECT;
   }

   // hold > 7 days => weekly trades overlap; a netting account would merge them into one position
   ENUM_ACCOUNT_MARGIN_MODE mm = (ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE);
   if(InpHoldDays > 7 && mm != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      Print("WM: hold > 7 days needs a HEDGING account (overlapping trades). Netting account detected: EA stopped.");
      return INIT_FAILED;
   }

   SymbolSelect(_Symbol, true);
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpDeviationPoints);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   // force the H1 history (lookback + margin) to load
   datetime tmp[];
   int want = (InpLookbackDays + 5) * 24;
   int got = CopyTime(_Symbol, WM_TF, 0, want, tmp);
   if(got < want)
      PrintFormat("WM: only %d of %d H1 bars available yet (history may still be syncing).", got, want);

   if(MQLInfoInteger(MQL_TESTER))
   {
      FileDelete(InpLogFile, FILE_COMMON);
      FileDelete(InpDealsFile, FILE_COMMON);
   }

   PrintFormat("WM: %s | lookback %d d | hold %d d | dir %d | size %.1f%% | entry dow %d %02d:00 server | account margin mode %d",
               _Symbol, InpLookbackDays, InpHoldDays, (int)InpDirection, 100.0 * InpSizeFraction,
               InpEntryDow, InpEntryHour, (int)mm);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   ManageExits();

   datetime t0 = iTime(_Symbol, WM_TF, 0);          // open time of the current H1 candle
   if(t0 == 0) return;
   if(!IsEntrySlot(t0)) return;
   if(g_decided_slot == t0) return;

   // restart safety: already in the market for this slot
   if(HasPositionForSlot(t0))
   {
      g_decided_slot = t0;
      return;
   }
   TryEntry(t0);
}

// deals export: one row per closed position (server time, as MT5 reports it)
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(!InpWriteLogs || trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY) return;

   ulong pid = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   if(!HistorySelectByPosition(pid)) return;

   datetime t_in = 0, t_out = 0;
   double p_in = 0, p_out = 0, vol = 0, profit = 0, swap = 0, comm = 0;
   string typ = "";
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
   {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      long de = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(de == DEAL_ENTRY_IN)
      {
         t_in = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         p_in = HistoryDealGetDouble(d, DEAL_PRICE);
         vol  = HistoryDealGetDouble(d, DEAL_VOLUME);
         typ  = ((ENUM_DEAL_TYPE)HistoryDealGetInteger(d, DEAL_TYPE) == DEAL_TYPE_BUY ? "long" : "short");
         comm += HistoryDealGetDouble(d, DEAL_COMMISSION);
      }
      else if(de == DEAL_ENTRY_OUT || de == DEAL_ENTRY_OUT_BY)
      {
         t_out  = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         p_out  = HistoryDealGetDouble(d, DEAL_PRICE);
         profit += HistoryDealGetDouble(d, DEAL_PROFIT);
         swap   += HistoryDealGetDouble(d, DEAL_SWAP);
         comm   += HistoryDealGetDouble(d, DEAL_COMMISSION);
      }
   }
   if(t_in == 0 || t_out == 0) return;

   string line = StringFormat("%s;%s;%s;%s;%s;%s;%s;%s;%s",
                              IsoTime(t_in), IsoTime(t_out),
                              DoubleToString(p_in, _Digits), DoubleToString(p_out, _Digits),
                              typ, DoubleToString(vol, 2),
                              DoubleToString(profit, 2), DoubleToString(swap, 2), DoubleToString(comm, 2));
   AppendLine(InpDealsFile, line, "time_in;time_out;price_in;price_out;type;lots;profit;swap;commission");
}
//+------------------------------------------------------------------+
