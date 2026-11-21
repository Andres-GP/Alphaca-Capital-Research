//+------------------------------------------------------------------+
//|                                              PerformanceReporter.mqh |
//|                   Reporting + monitoring layer for MT5 strategies |
//|                   v3.20 — Clean version                            |
//+------------------------------------------------------------------+
#property copyright "Alphaca Capital"
#property version   "3.20"

//+------------------------------------------------------------------+
//| Centralized defaults — override per strategy if needed            |
//+------------------------------------------------------------------+
#define DEFAULT_BACKEND_URL "https://performance-monitor-backend-prod.onrender.com"

//+------------------------------------------------------------------+
//| Class that handles monitoring AND communication with the backend  |
//+------------------------------------------------------------------+
class PerformanceReporter
{
private:
   //--- Backend configuration
   string            m_backendUrl;
   string            m_authToken;
   string            m_strategyId;
   string            m_strategyName;
   string            m_instrument;
   string            m_timeframe;
   string            m_platform;
   int               m_sizing;
   string            m_dataType;
   bool              m_verbose;

   //--- Reporter state
   bool              m_startReported;
   int               m_barsWithoutTrade;
   bool              m_inactivityAlertSent;
   int               m_maxBarsWithoutTrade;
   bool              m_enableInactivityAlert;

   //--- Monitoring state
   int               m_totalTrades;
   int               m_wins;
   int               m_losses;
   double            m_grossProfit;
   double            m_grossLoss;
   double            m_dayStartEquity;
   double            m_peakEquity;
   double            m_maxDrawdownHit;
   int               m_lastDayKey;

   //--- Internal methods
   void              SendPostRequest(string endpoint, string jsonPayload);
   string            FormatISODate(datetime dt);
   int               BuildDayKey(datetime dt);

public:
                     PerformanceReporter(string backendUrl, string authToken, string strategyName, string instrument, string timeframe, int sizing, string dataType);
                    ~PerformanceReporter();

   //--- Backend communication
   void              ReportStrategyStarted();
   string            ReportSignalIntent(string signalKey, string symbol, string direction, double referencePrice, double volume);
   void              ReportExecutionUpdate(string signalId, string status, double filledVolume, double fillPrice, string reason = "");
   void              ReportTradeClosed(ulong ticket, string symbol, double entryPrice, double exitPrice, double volume, double profit, datetime entryTime, datetime exitTime, double commission, ENUM_POSITION_TYPE positionType, double swap = 0.0);
   void              ReportHealthAlert(string problemType, string details, string severity = "high");
   void              ReportCapital(double capital, string currency = "USD");
   void              SendHeartbeat();
   void              OnBarUpdate(int barsTotal);
   void              OnOrderRejected(string orderName, int errorCode, string comment);

   //--- Equity and drawdown monitoring (call on every tick)
   void              UpdateEquity();

   //--- Push/email alerts
   void              SendAlert(string message);

   //--- Getters
   int               GetTotalTrades()    const { return m_totalTrades; }
   int               GetWins()           const { return m_wins; }
   int               GetLosses()         const { return m_losses; }
   double            GetMaxDrawdownHit() const { return m_maxDrawdownHit; }
   double            GetWinRate()        const;
   double            GetProfitFactor()   const;
   double            GetDailyDD()        const;
   double            GetTotalDD()        const;
   string            GetStrategyId()     const { return m_strategyId; }

   //--- Configuration
   void              SetMaxBarsWithoutTrade(int bars) { m_maxBarsWithoutTrade = bars; }
   void              EnableInactivityAlert(bool enable) { m_enableInactivityAlert = enable; }
   void              SetVerbose(bool verbose) { m_verbose = verbose; }
};

//+------------------------------------------------------------------+
//| Constructor                                                       |
//+------------------------------------------------------------------+
PerformanceReporter::PerformanceReporter(string backendUrl, string authToken, string strategyName, string instrument, string timeframe, int sizing, string dataType)
   : m_strategyName(strategyName),
     m_instrument(instrument),
     m_timeframe(timeframe),
     m_sizing(sizing),
     m_dataType(dataType),
     m_startReported(false),
     m_barsWithoutTrade(0),
     m_inactivityAlertSent(false),
     m_maxBarsWithoutTrade(50),
     m_enableInactivityAlert(true),
     m_verbose(false),
     m_totalTrades(0),
     m_wins(0),
     m_losses(0),
     m_grossProfit(0.0),
     m_grossLoss(0.0),
     m_dayStartEquity(0.0),
     m_peakEquity(0.0),
     m_maxDrawdownHit(0.0),
     m_lastDayKey(0)
{
   m_backendUrl = (backendUrl == "") ? DEFAULT_BACKEND_URL : backendUrl;
   m_authToken  = authToken;

   m_platform   = "MT5";
   m_strategyId = strategyName + "_" + instrument + "_" + timeframe;

   m_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   m_peakEquity     = m_dayStartEquity;

   m_lastDayKey = BuildDayKey(TimeCurrent());
}

//+------------------------------------------------------------------+
//| Destructor                                                        |
//+------------------------------------------------------------------+
PerformanceReporter::~PerformanceReporter()
{
}

//+------------------------------------------------------------------+
//| Helper: ISO 8601 date format                                      |
//+------------------------------------------------------------------+
string PerformanceReporter::FormatISODate(datetime dt)
{
   MqlDateTime dtStruct;
   TimeToStruct(dt, dtStruct);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02dZ",
                       dtStruct.year, dtStruct.mon, dtStruct.day,
                       dtStruct.hour, dtStruct.min, dtStruct.sec);
}

//+------------------------------------------------------------------+
//| Helper: build day key YYYYMMDD                                    |
//+------------------------------------------------------------------+
int PerformanceReporter::BuildDayKey(datetime dt)
{
   MqlDateTime s;
   TimeToStruct(dt, s);
   return s.year * 10000 + s.mon * 100 + s.day;
}

//+------------------------------------------------------------------+
//| Send POST request to the backend                                  |
//+------------------------------------------------------------------+
void PerformanceReporter::SendPostRequest(string endpoint, string jsonPayload)
{
   if(StringLen(m_authToken) == 0)
   {
      if(m_verbose) Print("[ERROR] Backend API key is required; configure InpAuthToken");
      return;
   }

   string url = m_backendUrl + endpoint;
   string headers = "Content-Type: application/json\r\nAuthorization: Bearer " + m_authToken + "\r\n";
   char postData[];
   char resultData[];
   string resultHeaders;

   int dataSize = StringToCharArray(jsonPayload, postData) - 1;
   if(dataSize < 0)
   {
      if(m_verbose) Print("[ERROR] Invalid JSON payload for ", endpoint);
      return;
   }

   ResetLastError();
   int res = WebRequest("POST", url, headers, 5000, postData, resultData, resultHeaders);

   if(res == -1)
   {
      if(m_verbose) Print("[ERROR] WebRequest failed on ", endpoint, " | err=", GetLastError());
      return;
   }

   if(res < 200 || res >= 300)
   {
      if(m_verbose) Print("[ERROR] POST ", endpoint, " -> HTTP ", res, " | ", CharArrayToString(resultData));
      return;
   }

   if(m_verbose) Print("[OK] POST ", endpoint, " -> HTTP ", res);
}

//+------------------------------------------------------------------+
//| Report strategy started                                           |
//+------------------------------------------------------------------+
void PerformanceReporter::ReportStrategyStarted()
{
   if(m_startReported) return;
   m_startReported = true;

   string payload = StringFormat(
      "{"
      "\"strategy_id\":\"%s\","
      "\"name\":\"%s\","
      "\"instrument\":\"%s\","
      "\"instrument_type\":\"CFD\","
      "\"timeframe\":\"%s\","
      "\"data_type\":\"%s\","
      "\"platform\":\"%s\","
      "\"sizing\":%d,"
      "\"start_date\":\"%s\","
      "\"state\":\"Running\""
      "}",
      m_strategyId, m_strategyName, m_instrument,
      m_timeframe, m_dataType, m_platform,
      m_sizing, FormatISODate(TimeCurrent())
   );
   SendPostRequest("/strategies/start", payload);
}

//+------------------------------------------------------------------+
//| Record the reference price and requested size before an entry     |
//+------------------------------------------------------------------+
string PerformanceReporter::ReportSignalIntent(string signalKey, string symbol, string direction, double referencePrice, double volume)
{
   datetime now = TimeCurrent();
   string signalId = StringFormat("%s_%d_%s", m_strategyId, (int)now, signalKey);
   string payload = StringFormat(
      "{\"event_type\":\"signal_intent\",\"payload\":{\"strategy_id\":\"%s\",\"signal_id\":\"%s\",\"symbol\":\"%s\",\"direction\":\"%s\",\"reference_price\":%.8f,\"volume\":%.4f,\"timestamp\":\"%s\"}}",
      m_strategyId, signalId, symbol, direction, referencePrice, volume, FormatISODate(now)
   );
   SendPostRequest("/monitor/events", payload);
   return signalId;
}

//+------------------------------------------------------------------+
//| Record the broker outcome for a previously reported signal       |
//+------------------------------------------------------------------+
void PerformanceReporter::ReportExecutionUpdate(string signalId, string status, double filledVolume, double fillPrice, string reason = "")
{
   StringReplace(reason, "\\", "\\\\");
   StringReplace(reason, "\"", "\\\"");
   StringReplace(reason, "\r", " ");
   StringReplace(reason, "\n", " ");
   string fillPriceJson = (fillPrice > 0) ? DoubleToString(fillPrice, 8) : "null";
   string payload = StringFormat(
      "{\"event_type\":\"execution_update\",\"payload\":{\"strategy_id\":\"%s\",\"signal_id\":\"%s\",\"status\":\"%s\",\"filled_volume\":%.4f,\"fill_price\":%s,\"reason\":\"%s\",\"timestamp\":\"%s\"}}",
      m_strategyId, signalId, status, filledVolume, fillPriceJson, reason, FormatISODate(TimeCurrent())
   );
   SendPostRequest("/monitor/events", payload);
}

//+------------------------------------------------------------------+
//| Report a closed trade — also updates internal counters            |
//+------------------------------------------------------------------+
void PerformanceReporter::ReportTradeClosed(
   ulong ticket, string symbol,
   double entryPrice, double exitPrice, double volume,
   double profit, datetime entryTime, datetime exitTime,
   double commission, ENUM_POSITION_TYPE positionType, double swap)
{
   m_totalTrades++;
   if(profit >= 0) { m_wins++; m_grossProfit += profit; }
   else            { m_losses++; m_grossLoss += MathAbs(profit); }

   double quantity = volume;
   string entryTimeStr = FormatISODate(entryTime);
   string exitTimeStr  = FormatISODate(exitTime);
   string direction = (positionType == POSITION_TYPE_BUY) ? "Long" : "Short";

   double calculatedPnl = (direction == "Long")
      ? (exitPrice - entryPrice) * quantity
      : (entryPrice - exitPrice) * quantity;
   if(profit == 0.0) profit = calculatedPnl;

   string payload = StringFormat(
      "{"
      "\"strategy_id\":\"%s\","
      "\"instrument\":\"%s\","
      "\"entry_time\":\"%s\","
      "\"exit_time\":\"%s\","
      "\"quantity\":%.2f,"
      "\"entry_price\":%.5f,"
      "\"exit_price\":%.5f,"
      "\"pnl\":%.8f,"
      "\"direction\":\"%s\","
      "\"cost\":%.2f,"
      "\"commission\":%.2f,"
      "\"swap\":%.2f,"
      "\"currency\":\"%s\""
      "}",
      m_strategyId, symbol,
      entryTimeStr, exitTimeStr,
      quantity, entryPrice, exitPrice,
      profit, direction, commission, commission, swap,
      AccountInfoString(ACCOUNT_CURRENCY)
   );
   SendPostRequest("/trades", payload);
}

//+------------------------------------------------------------------+
//| Report a health alert                                             |
//+------------------------------------------------------------------+
void PerformanceReporter::ReportHealthAlert(string problemType, string details, string severity = "high")
{
   string payload = StringFormat(
      "{"
      "\"strategy_id\":\"%s\","
      "\"timestamp\":\"%s\","
      "\"problem_type\":\"%s\","
      "\"details\":\"%s\","
      "\"severity\":\"%s\""
      "}",
      m_strategyId, FormatISODate(TimeCurrent()),
      problemType, details, severity
   );
   SendPostRequest("/alerts", payload);
}

//+------------------------------------------------------------------+
//| Report account capital                                            |
//+------------------------------------------------------------------+
void PerformanceReporter::ReportCapital(double capital, string currency = "USD")
{
   string payload = StringFormat(
      "{"
      "\"strategy_id\":\"%s\","
      "\"account_type\":\"%s\","
      "\"capital\":%.2f,"
      "\"currency\":\"%s\""
      "}",
      m_strategyId,
      (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO) ? "demo" : "real",
      capital, currency
   );
   SendPostRequest("/capital/report", payload);
}

//+------------------------------------------------------------------+
//| Send heartbeat to backend                                         |
//+------------------------------------------------------------------+
void PerformanceReporter::SendHeartbeat()
{
   if(!m_startReported) return;
   string payload = StringFormat("{\"strategy_id\":\"%s\"}", m_strategyId);
   SendPostRequest("/heartbeat", payload);

   string equityEvent = StringFormat(
      "{\"event_type\":\"equity\",\"payload\":{\"strategy_id\":\"%s\",\"equity\":%.2f,\"currency\":\"%s\",\"ts\":\"%s\"}}",
      m_strategyId, AccountInfoDouble(ACCOUNT_EQUITY),
      AccountInfoString(ACCOUNT_CURRENCY), FormatISODate(TimeCurrent())
   );
   SendPostRequest("/monitor/events", equityEvent);
}

//+------------------------------------------------------------------+
//| Inactivity monitoring — call on every new bar                     |
//+------------------------------------------------------------------+
void PerformanceReporter::OnBarUpdate(int barsTotal)
{
   if(!m_enableInactivityAlert || m_maxBarsWithoutTrade <= 0) return;

   if(PositionsTotal() > 0)
   {
      m_barsWithoutTrade = 0;
      m_inactivityAlertSent = false;
      return;
   }

   m_barsWithoutTrade++;
   if(m_barsWithoutTrade >= m_maxBarsWithoutTrade && !m_inactivityAlertSent)
   {
      ReportHealthAlert("Inactive strategy",
         StringFormat("No trade generated in the last %d bars.", m_maxBarsWithoutTrade),
         "medium");
      m_inactivityAlertSent = true;
   }
}

//+------------------------------------------------------------------+
//| Report rejected order                                             |
//+------------------------------------------------------------------+
void PerformanceReporter::OnOrderRejected(string orderName, int errorCode, string comment)
{
   ReportHealthAlert("Order rejected",
      StringFormat("Order %s rejected. Error: %d, Comment: %s", orderName, errorCode, comment),
      "high");
}

//+------------------------------------------------------------------+
//| Update equity, peak, daily baseline, max DD. Call on every tick   |
//+------------------------------------------------------------------+
void PerformanceReporter::UpdateEquity()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   if(equity > m_peakEquity)
      m_peakEquity = equity;

   datetime now = TimeCurrent();
   int todayKey = BuildDayKey(now);
   if(todayKey != m_lastDayKey)
   {
      m_lastDayKey = todayKey;
      m_dayStartEquity = equity;
   }

   if(m_peakEquity > 0)
   {
      double totalDD = (m_peakEquity - equity) / m_peakEquity * 100.0;
      if(totalDD > m_maxDrawdownHit)
         m_maxDrawdownHit = totalDD;
   }
}

//+------------------------------------------------------------------+
//| Send push + email alert                                           |
//+------------------------------------------------------------------+
void PerformanceReporter::SendAlert(string message)
{
   SendNotification(message);
   SendMail("Alphaca Capital Strategy Alert", message);
}

//+------------------------------------------------------------------+
//| Computed getters                                                  |
//+------------------------------------------------------------------+
double PerformanceReporter::GetWinRate() const
{
   if(m_totalTrades == 0) return 0.0;
   return (double)m_wins / m_totalTrades * 100.0;
}

double PerformanceReporter::GetProfitFactor() const
{
   if(m_grossLoss <= 0) return (m_grossProfit > 0) ? 99.99 : 0.0;
   return m_grossProfit / m_grossLoss;
}

double PerformanceReporter::GetDailyDD() const
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(m_dayStartEquity <= 0) return 0.0;
   return (m_dayStartEquity - eq) / m_dayStartEquity * 100.0;
}

double PerformanceReporter::GetTotalDD() const
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(m_peakEquity <= 0) return 0.0;
   return (m_peakEquity - eq) / m_peakEquity * 100.0;
}

//+------------------------------------------------------------------+
