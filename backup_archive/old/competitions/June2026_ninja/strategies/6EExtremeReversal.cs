using System;
using NinjaTrader.Cbi;

namespace NinjaTrader.NinjaScript.Strategies
{
    public class H1_Competition_Final_NoTimeFilter : Strategy
    {
        private double moveThreshold = 0.00015;
        private int holdBars = 7;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "H1 Final (0.015% / 7min) - sin filtro horario";
                Name = "SixEExtremeReversal";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                BarsRequiredToTrade = 10;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 2) return;

            if (Position.MarketPosition != MarketPosition.Flat)
            {
                if (BarsSinceEntryExecution() >= holdBars)
                {
                    if (Position.MarketPosition == MarketPosition.Long) ExitLong();
                    else ExitShort();
                }
                return;
            }

            double prevRet = (Close[1] - Close[2]) / Close[2];
            double currRet = (Close[0] - Close[1]) / Close[1];

            if (Math.Abs(prevRet) < moveThreshold) return;
            if (!((prevRet > 0 && currRet < 0) || (prevRet < 0 && currRet > 0))) return;

            if (prevRet < 0)
                EnterLong(2, "RevLong");
            else
                EnterShort(2, "RevShort");
        }
    }
}