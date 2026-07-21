// MES_Gap_006_Hold15_NoTimeFilter.cs
using System;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Strategies;

namespace NinjaTrader.NinjaScript.Strategies
{
    public class MES_Gap_006_Hold15_NoTimeFilter : Strategy
    {
        private double gapThreshold = 0.00006;   // 0.006%
        private int holdMinutes = 15;
        private int contracts = 3;               // ajusta según tu riesgo
        private int entryBar = -1;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "MES: Long when intraday gap < -0.006%, exit after 15 min. NO time filter (24/7).";
                Name = "MES_Gap_006_Hold15_NoTimeFilter";
                Calculate = Calculate.OnBarClose;
                BarsRequiredToTrade = 1;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;

            // Sin ningún filtro de horario
            double gap = (Open[0] - Close[1]) / Close[1];

            if (gap < -gapThreshold && Position.MarketPosition == MarketPosition.Flat)
            {
                EnterLong(contracts, "GapLong");
                entryBar = CurrentBar;
            }

            if (Position.MarketPosition == MarketPosition.Long && CurrentBar >= entryBar + holdMinutes)
            {
                ExitLong(contracts, "GapExit", "GapLong");
            }
        }
    }
}
