import numpy as np
import pandas as pd

def sharpe_ratio(returns, risk_free=0.0, periods_per_year=252):
    excess = returns - risk_free / periods_per_year
    if len(excess) < 2:
        return 0.0
    return np.sqrt(periods_per_year) * excess.mean() / excess.std() if excess.std() != 0 else 0.0

def max_drawdown(equity_curve):
    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return drawdown.min()

def calmar_ratio(returns, equity_curve, periods_per_year=252):
    sharpe = sharpe_ratio(returns, periods_per_year=periods_per_year)
    dd = abs(max_drawdown(equity_curve))
    return sharpe / dd if dd != 0 else 0.0

def win_rate(trades):
    wins = trades[trades > 0].count()
    total = trades.count()
    return wins / total if total > 0 else 0.0