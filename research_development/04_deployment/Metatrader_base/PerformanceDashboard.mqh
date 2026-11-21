//+------------------------------------------------------------------+
//| Standard Alphaca MT5 chart monitor                               |
//| Shared visual layout for strategy-specific status and metrics.   |
//+------------------------------------------------------------------+
#property copyright "Alphaca Capital"
#property version   "1.00"

class PerformanceDashboard
{
private:
   string m_prefix;
   int    m_x;
   int    m_y;
   int    m_width;
   int    m_lineHeight;
   uint   m_lastUpdateMs;

   void DrawLabel(string suffix, string text, int y, color textColor, int fontSize)
   {
      string name = m_prefix + suffix;
      if(ObjectFind(0, name) < 0)
      {
         ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
         ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
         ObjectSetInteger(0, name, OBJPROP_BACK, false);
         ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, name, OBJPROP_ZORDER, 1);
      }
      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, m_x + 14);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, name, OBJPROP_COLOR, textColor);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   }

   void DrawContext(string suffix, string text, color textColor, int &y)
   {
      if(StringLen(text) == 0)
      {
         DrawLabel(suffix, "", y, textColor, 1);
         return;
      }
      DrawLabel(suffix, text, y, textColor, 9);
      y += m_lineHeight;
   }

public:
   PerformanceDashboard(string prefix = "ALPHACA_")
   {
      m_prefix = prefix;
      m_x = 12;
      m_y = 22;
      m_width = 560;
      m_lineHeight = 19;
      m_lastUpdateMs = 0;
   }

   void SetPrefix(string prefix)
   {
      m_prefix = prefix;
   }

   void Update(
      string title,
      string subtitle,
      string state, color stateColor,
      string reporterState,
      string context1, color context1Color,
      string context2, color context2Color,
      string context3, color context3Color,
      string position, color positionColor,
      string tradeCount,
      string tradeQuality,
      string equity,
      string drawdown, color drawdownColor,
      string maxDrawdown)
   {
      uint nowMs = GetTickCount();
      if(m_lastUpdateMs != 0 && (uint)(nowMs - m_lastUpdateMs) < 250) return;
      m_lastUpdateMs = nowMs;

      int contentLines = 9;
      if(StringLen(context1) > 0) contentLines++;
      if(StringLen(context2) > 0) contentLines++;
      if(StringLen(context3) > 0) contentLines++;
      if(StringLen(tradeQuality) > 0) contentLines++;

      string panel = m_prefix + "PANEL";
      if(ObjectFind(0, panel) < 0)
      {
         ObjectCreate(0, panel, OBJ_RECTANGLE_LABEL, 0, 0, 0);
         ObjectSetInteger(0, panel, OBJPROP_CORNER, CORNER_LEFT_UPPER);
         ObjectSetInteger(0, panel, OBJPROP_SELECTABLE, false);
         ObjectSetInteger(0, panel, OBJPROP_HIDDEN, true);
         ObjectSetInteger(0, panel, OBJPROP_BACK, false);
      }
      ObjectSetInteger(0, panel, OBJPROP_XDISTANCE, m_x);
      ObjectSetInteger(0, panel, OBJPROP_YDISTANCE, m_y);
      ObjectSetInteger(0, panel, OBJPROP_XSIZE, m_width);
      ObjectSetInteger(0, panel, OBJPROP_YSIZE, 18 + contentLines * m_lineHeight);
      ObjectSetInteger(0, panel, OBJPROP_BGCOLOR, C'20,25,34');
      ObjectSetInteger(0, panel, OBJPROP_COLOR, C'58,68,82');

      int y = m_y + 10;
      DrawLabel("TITLE", title, y, clrDodgerBlue, 11);
      y += m_lineHeight;
      DrawLabel("SUBTITLE", subtitle, y, clrSilver, 9);
      y += m_lineHeight;
      DrawLabel("STATE", state, y, stateColor, 10);
      y += m_lineHeight;
      DrawLabel("REPORTER", reporterState, y, clrSilver, 9);
      y += m_lineHeight;
      DrawContext("CONTEXT_1", context1, context1Color, y);
      DrawContext("CONTEXT_2", context2, context2Color, y);
      DrawContext("CONTEXT_3", context3, context3Color, y);
      DrawLabel("POSITION", position, y, positionColor, 9);
      y += m_lineHeight;
      DrawLabel("TRADES", tradeCount, y, clrSilver, 9);
      y += m_lineHeight;
      if(StringLen(tradeQuality) > 0)
      {
         DrawLabel("TRADE_QUALITY", tradeQuality, y, clrSilver, 9);
         y += m_lineHeight;
      }
      else
         DrawLabel("TRADE_QUALITY", "", y, clrSilver, 1);
      DrawLabel("EQUITY", equity, y, clrWhite, 9);
      y += m_lineHeight;
      DrawLabel("DRAWDOWN", drawdown, y, drawdownColor, 9);
      y += m_lineHeight;
      DrawLabel("MAX_DRAWDOWN", maxDrawdown, y, clrSilver, 8);
      ChartRedraw(0);
   }
};
