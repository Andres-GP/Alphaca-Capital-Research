using System;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript.Indicators;

namespace NinjaTrader.NinjaScript.Strategies
{
    public class MCL_VolumeSpikeShort_Simple_NoTimeFilter : Strategy
    {
        private double volumeRatio = 2.0;    
        private int holdBars = 20;
        private int periodVol = 20;

        private SMA smaVolume;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "MCL Volume Spike Short (simplificado, sin filtro horario) – volumen > 2*media, salida 20 min, sin stop";
                Name = "MCL_VolumeSpikeShort_Simple_NoTimeFilter";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                BarsRequiredToTrade = 30;
            }
            else if (State == State.DataLoaded)
            {
                smaVolume = SMA(Volume, periodVol);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade + periodVol)
                return;


            if (Position.MarketPosition != MarketPosition.Flat)
            {
                if (BarsSinceEntryExecution() >= holdBars)
                {
                    ExitShort();
                }
                return;
            }

            if (Volume[0] > volumeRatio * smaVolume[0])
            {
                EnterShort(2, "VolShort");
            }
        }
    }
}