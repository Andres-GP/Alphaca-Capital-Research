# MR_MeanReversion_ES_15min - Rejection Report

## 1. System Overview

- **Name**: MR_MeanReversion_ES_15min
- **Instrument**: ES (E-mini S&P 500)
- **Timeframe**: 15 minutes
- **Strategy Type**: Mean Reversion
- **Development Period**: [Fecha de inicio] - [Fecha de fin]

## 2. Final Parameters

| Parameter       | Value                  |
| --------------- | ---------------------- |
| entry_threshold | 1.0%                   |
| rsi_threshold   | 14                     |
| atr_stop        | 1.4x                   |
| atr_target      | 3.0x                   |
| time_stop       | 3:50 PM NY             |
| cost_per_trade  | $10.25 (1 contract ES) |

## 3. Out-of-Sample Performance (2020-2026)

| Metric        | Value     |
| ------------- | --------- |
| Total Trades  | 41        |
| Win Rate      | 39.02%    |
| Profit Factor | 0.97 ❌   |
| Total P&L     | -0.81% ❌ |
| Sharpe Ratio  | -0.21 ❌  |
| Max Drawdown  | -7.04% ✅ |

## 4. Robustness Tests Summary

| Test                           | Result                                    | Status |
| ------------------------------ | ----------------------------------------- | ------ |
| Walk-Forward                   | Inconsistent (PF 0.00 in multiple cycles) | ❌     |
| Parameter Sensitivity          | PF range 0.45                             | ✅     |
| Stress Tests (Bear 2022)       | PF 0.36                                   | ❌     |
| Stress Tests (Rally 2023-2024) | PF 0.00                                   | ❌     |
| Monte Carlo (Realistic Costs)  | PF 0.45                                   | ❌     |

## 5. Reasons for Rejection

1. **Profit Factor < 1.3** (0.97 in OOS) - Not profitable after realistic costs.
2. **Failed Stress Tests** - Strategy does not survive Bear Market 2022 (PF 0.36) or Rally 2023-2024 (PF 0.00).
3. **Failed Walk-Forward** - Performance is inconsistent across market regimes.
4. **Failed Monte Carlo** - With realistic costs, probability of positive P&L is only 1.41% in pessimistic scenario.
5. **Cost sensitivity** - The edge is too small to cover realistic commissions ($10.25 per trade).

## 6. Root Cause Analysis

The strategy has a real but very small edge. The average win is 1.60% and average loss is -1.06%. With a win rate of 39%, the gross expectancy is:
