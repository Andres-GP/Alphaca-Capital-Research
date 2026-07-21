using System;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript.Indicators;

namespace NinjaTrader.NinjaScript.Strategies
{
    public class MGC_VolumeSpikeShort : Strategy
    {
        private double zThreshold = 3.0;
        private int holdBars = 10;
        private double minATR;      
        private double stopMultiple = 1.0;
        private int periodVol = 20;

        private SMA smaVolume;
        private ATR atr;

        private bool pendingSignal = false;
        private int signalBarIdx = -1;
        private double entryStopPrice = 0;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "MGC Volume Spike Short (overfitted) – z=3.0, hold=10, ATR p70, stop=1.0";
                Name = "MGC_VolumeSpikeShort";
                Calculate = Calculate.OnBarClose; 
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                BarsRequiredToTrade = 30;
                minATR = 1.5;   
            }
            else if (State == State.DataLoaded)
            {
                smaVolume = SMA(Volume, periodVol);
                atr = ATR(14);
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
                    pendingSignal = false;
                }
                return;
            }

            if (pendingSignal && CurrentBar == signalBarIdx + 1)
            {
                double entryPrice = Open[0];
                EnterLong(2, "VolShort");
                SetStopLoss("VolShort", CalculationMode.Price, entryStopPrice, false);
                pendingSignal = false;
                return;
            }
            else if (pendingSignal && CurrentBar > signalBarIdx + 1)
            {
                // Señal caducada
                pendingSignal = false;
            }

            double volMean = smaVolume[0];
            double volStd = StdDev(Volume, periodVol)[0];
            double volZ = (Volume[0] - volMean) / volStd;

            if (volZ > zThreshold && atr[0] >= minATR)
            {
                pendingSignal = true;
                signalBarIdx = CurrentBar;
                entryStopPrice = Open[0] + stopMultiple * atr[0];
            }
        }
    }
}
