"""
Reusable EDA utilities for financial time series (OHLCV data).
Provides functions for:
- Loading data from MongoDB
- Resampling to multiple timeframes
- Computing statistics (Hurst, ACF, etc.)
- Generating detailed plots with dark theme
- Full timeframe analysis with system recommendation
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.patches import Rectangle, FancyBboxPatch
from scipy.stats import norm, linregress, jarque_bera
from statsmodels.tsa.stattools import acf
import textwrap
import warnings
from pymongo import MongoClient

warnings.filterwarnings('ignore')

# ============================================================================
# STYLE CONSTANTS
# ============================================================================

BLUE = '#5468ff'
ROW_HIGHLIGHT = '#1f3d2e'
BADGE_BG = '#262933'
BADGE_ORANGE_BG = '#3d2f16'
BG = '#15171c'
PANEL_BG = '#1b1e26'
GRID = '#2a2d37'
TEXT = '#e8e9ec'
SUBTEXT = '#9aa0ab'
GREEN = '#34d399'
RED = '#f0555a'
ORANGE = '#f5a524'
WHITE_LN = '#d7d9df'

HEAT_RED = '#7a3a3d'
HEAT_NEUTRAL = '#3a3f4b'
HEAT_CMAP = LinearSegmentedColormap.from_list('perf_heat', [HEAT_RED, HEAT_NEUTRAL, GREEN])

# ============================================================================
# STYLE HELPERS
# ============================================================================

def _dark_fig(figsize):
    """Create a matplotlib figure with dark background."""
    fig = plt.figure(figsize=figsize, facecolor=BG)
    return fig

def _rounded_rect(ax, xy, width, height, color, radius=0.012, zorder=1, alpha=1.0):
    """Draw a rounded rectangle in axes coordinates."""
    box = FancyBboxPatch(
        xy, width, height,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=0, facecolor=color, alpha=alpha, zorder=zorder,
        transform=ax.transAxes, clip_on=False
    )
    ax.add_patch(box)
    return box

def _flat_rect(ax, xy, width, height, color, zorder=1, alpha=1.0):
    """Draw a flat rectangle in axes coordinates."""
    rect = Rectangle(xy, width, height, linewidth=0, facecolor=color,
                     alpha=alpha, zorder=zorder, transform=ax.transAxes, clip_on=False)
    ax.add_patch(rect)
    return rect

def _badge_color(level):
    """Return background and text colors for a badge based on level."""
    level = str(level).lower()
    if level in ('high', 'yes'):
        return (ROW_HIGHLIGHT, GREEN)
    elif level == 'medium':
        return (BADGE_ORANGE_BG, ORANGE)
    else:
        return (BADGE_BG, SUBTEXT)

def _style_ax(ax, title=None, xlabel=None, ylabel=None):
    """Apply dark style to an axis and add titles."""
    ax.set_facecolor(PANEL_BG)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=SUBTEXT, labelsize=9)
    if title:
        ax.set_title(title, color=TEXT, fontweight='bold', fontsize=12, loc='left', pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, color=SUBTEXT, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=SUBTEXT, fontsize=9)
    return ax

# ============================================================================
# STATISTICAL FUNCTIONS
# ============================================================================

def compute_hurst(price_series, max_lag=100):
    """
    Calculate the Hurst exponent for a price series.
    Returns np.nan if calculation fails.
    """
    lags = range(2, max_lag)
    tau = []
    for lag in lags:
        pp = np.subtract(price_series[lag:], price_series[:-lag])
        std = np.std(pp)
        if std == 0:
            continue
        mean = np.mean(pp)
        dev = pp - mean
        cumsum_dev = np.cumsum(dev)
        r = np.max(cumsum_dev) - np.min(cumsum_dev)
        tau.append(r / std)
    lags = np.array(lags[:len(tau)])
    tau = np.array(tau)
    if len(tau) < 3:
        return np.nan
    hurst = np.polyfit(np.log(lags), np.log(tau), 1)[0]
    return hurst

def compute_acf(series, nlags=40):
    """Compute autocorrelation function up to nlags."""
    return acf(series, nlags=nlags, fft=False)

# ============================================================================
# PLOTTING FUNCTIONS
# ============================================================================

def plot_distribution_detailed(df, ret_col='ret', name=''):
    """
    Plot return histogram with normal curve overlay and ±3σ marks.
    Returns fitted mean and standard deviation.
    """
    ret = df[ret_col].dropna() * 100
    fig = _dark_fig((12, 5))
    ax = fig.add_subplot(111)
    _style_ax(ax, title=f'Your returns (bars) vs Ideal Normal (line) - {name}',
              xlabel='Return (%)', ylabel='Density')

    n, bins, patches = ax.hist(ret, bins=100, density=True, alpha=0.75,
                                color=GREEN, edgecolor=BG, linewidth=0.4)

    mu, std = norm.fit(ret)
    xmin, xmax = ret.min(), ret.max()
    x = np.linspace(xmin, xmax, 200)
    p = norm.pdf(x, mu, std)
    ax.plot(x, p, color=WHITE_LN, linewidth=1.6, linestyle=(0, (4, 3)),
            label=f'Normal (μ={mu:.2f}, σ={std:.2f})')

    ax.axvspan(xmin, mu - 3 * std, alpha=0.18, color=RED, zorder=0)
    ax.axvspan(mu + 3 * std, xmax, alpha=0.18, color=RED, zorder=0)
    ax.axvline(x=mu - 3 * std, color=ORANGE, linestyle='--', linewidth=1.2, alpha=0.9, label='-3σ')
    ax.axvline(x=mu + 3 * std, color=ORANGE, linestyle='--', linewidth=1.2, alpha=0.9, label='+3σ')

    ax.legend(frameon=False, labelcolor=SUBTEXT, fontsize=9, loc='upper right')

    ax.text(0.02, 0.95, f'σ = {std:.2f}%', transform=ax.transAxes, fontsize=10,
            color=TEXT, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor=PANEL_BG, edgecolor=GRID, alpha=0.95))

    fig.text(0.5, 0.01,
              'What it is for: sizing real risk. Fat tails + negative skew '
              'mean your stop and your sizing need to account for violent drops.',
              ha='center', fontsize=9.5, style='italic', color=SUBTEXT)

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    plt.show()
    return mu, std

def plot_volatility_detailed(df, ret_col='ret', window=20, name=''):
    """
    Plot historical vs recent volatility and daily returns.
    Returns (vol_hist, vol_recent, ratio).
    """
    ret = df[ret_col].dropna()
    vol_daily = ret.rolling(window).std() * 100
    vol_hist = ret.std() * 100
    vol_recent = ret.tail(window).std() * 100

    fig = _dark_fig((14, 9))
    ax1 = fig.add_subplot(2, 1, 1)
    ax2 = fig.add_subplot(2, 1, 2, sharex=ax1)

    _style_ax(ax1, title=f'Volatility over time - {name}', ylabel='Daily volatility (%)')
    ax1.plot(vol_daily.index, vol_daily, color=GREEN, linewidth=1.4)
    ax1.axhline(y=vol_hist, color=RED, linestyle='--', linewidth=1.2, alpha=0.85,
                label=f'Historical: {vol_hist:.2f}%')
    ax1.axhline(y=vol_recent, color=WHITE_LN, linestyle='--', linewidth=1.2, alpha=0.9,
                label=f'Recent: {vol_recent:.2f}%')
    ax1.legend(frameon=False, labelcolor=SUBTEXT, fontsize=9, loc='upper left')

    _style_ax(ax2, title='Daily returns over time (green up · red down)', ylabel='Return (%)')
    ret_pct = ret * 100
    colors = [GREEN if x > 0 else RED for x in ret_pct]
    ax2.bar(ret_pct.index, ret_pct, color=colors, alpha=0.85, width=0.8, linewidth=0)
    ax2.axhline(y=0, color=SUBTEXT, linewidth=0.6)

    max_ret = ret_pct.max()
    min_ret = ret_pct.min()
    ax2.text(0.01, 0.95, f'+{max_ret:.1f}%', transform=ax2.transAxes, fontsize=10,
              color=GREEN, fontweight='bold', va='top')
    ax2.text(0.01, 0.05, f'{min_ret:.1f}%', transform=ax2.transAxes, fontsize=10,
              color=RED, fontweight='bold', va='bottom')

    fig.text(0.5, 0.01,
              'What it is for: adjusting position size (less during turbulent periods) '
              'and filtering entries based on the volatility regime.',
              ha='center', fontsize=9.5, style='italic', color=SUBTEXT)

    fig.tight_layout(rect=[0, 0.04, 1, 1])
    plt.show()
    return vol_hist, vol_recent, (vol_recent / vol_hist if vol_hist > 0 else 0)

def plot_acf_detailed(df, ret_col='ret', nlags=40, name=''):
    """
    Plot autocorrelation bar chart and scatter of today vs yesterday returns.
    Returns the ACF array.
    """
    ret = df[ret_col].dropna()
    acf_vals = compute_acf(ret, nlags=nlags)
    ci = 1.96 / np.sqrt(len(ret))

    fig = _dark_fig((14, 5.5))
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(1, 2, 2)

    selected_lags = [l for l in [1, 2, 3, 5, 10, 20] if l < len(acf_vals)]
    vals = [acf_vals[l] for l in selected_lags]
    x_pos = np.arange(len(selected_lags))

    ax1.set_facecolor(PANEL_BG)
    ax1.grid(False)
    ax1.set_title('LAG MEMORY BY LAG (HEIGHT = STRENGTH · SIGN = DIRECTION)',
                   color=SUBTEXT, fontsize=9.5, loc='left', pad=14)
    ax1.axhspan(-ci, ci, color=SUBTEXT, alpha=0.12, zorder=0)
    ax1.axhline(y=0, color=GRID, linewidth=1)
    bar_colors = [GREEN if v > 0 else RED for v in vals]
    bars = ax1.bar(x_pos, vals, color=bar_colors, alpha=0.85, width=0.55, linewidth=0, zorder=2)
    for xp, v in zip(x_pos, vals):
        offset = 0.003 if v >= 0 else -0.003
        ax1.text(xp, v + offset, f'{v:.3f}', ha='center',
                  va='bottom' if v >= 0 else 'top', fontsize=8.5, color=TEXT, fontweight='bold')
    ymax = max(0.04, max(abs(v) for v in vals) * 1.4)
    ax1.set_ylim(-ymax, ymax)
    ax1.set_yticks([-ymax, 0, ymax])
    ax1.set_yticklabels([f'{-ymax:+.3f}', '0', f'{ymax:+.3f}'], color=SUBTEXT, fontsize=9)
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels([str(l) for l in selected_lags], color=SUBTEXT, fontsize=9)
    for spine in ax1.spines.values():
        spine.set_visible(False)
    ax1.tick_params(length=0)

    handles = [
        plt.Line2D([0], [0], marker='s', color='none', markerfacecolor=GREEN, markersize=9,
                    label='Momentum repeats'),
        plt.Line2D([0], [0], marker='s', color='none', markerfacecolor=RED, markersize=9,
                    label='Inverted (reversal)'),
        plt.Line2D([0], [0], marker='s', color='none', markerfacecolor=SUBTEXT, markersize=9,
                    label='Noise zone'),
    ]
    ax1.legend(handles=handles, loc='upper center', bbox_to_anchor=(0.5, -0.12),
               ncol=3, frameon=False, labelcolor=SUBTEXT, fontsize=8.5, handletextpad=0.4,
               columnspacing=1.2)

    ret_shift = ret.shift(1).dropna()
    ret_today = ret.loc[ret_shift.index]
    same_dir = (np.sign(ret_shift) * np.sign(ret_today)) >= 0
    point_colors = np.where(same_dir, GREEN, RED)

    ax2.set_facecolor(PANEL_BG)
    ax2.grid(False)
    ax2.set_title("Today's return (Y) vs Yesterday (X)",
                   color=SUBTEXT, fontsize=9.5, loc='left', pad=14)
    ax2.scatter(ret_shift * 100, ret_today * 100, c=point_colors, alpha=0.45, s=14, linewidths=0, zorder=2)

    try:
        slope, intercept, r_value, p_value, std_err = linregress(ret_shift, ret_today)
        x_vals = np.linspace(ret_shift.min(), ret_shift.max(), 100)
        y_vals = slope * x_vals + intercept
        ax2.plot(x_vals * 100, y_vals * 100, color=WHITE_LN, linewidth=1.5, alpha=0.85, zorder=3)
    except Exception:
        pass

    ax2.axhline(y=0, color=GRID, linewidth=0.4, zorder=1)
    ax2.axvline(x=0, color=GRID, linewidth=0.4, zorder=1)
    ax2.set_box_aspect(1)
    ax2.set_xticks([])
    ax2.set_yticks([])
    for spine in ax2.spines.values():
        spine.set_visible(True)
        spine.set_color(GRID)
        spine.set_linewidth(1)

    ax2.text(0.02, 0.97, 'today', transform=ax2.transAxes, color=SUBTEXT, fontsize=9, va='top', ha='left')
    ax2.text(0.02, 0.02, 'yesterday -', transform=ax2.transAxes, color=SUBTEXT, fontsize=9, va='bottom', ha='left')
    ax2.text(0.98, 0.02, 'yesterday +', transform=ax2.transAxes, color=SUBTEXT, fontsize=9, va='bottom', ha='right')

    handles2 = [
        plt.Line2D([0], [0], marker='o', color='none', markerfacecolor=GREEN, markersize=8,
                    label='Followed yesterday direction'),
        plt.Line2D([0], [0], marker='o', color='none', markerfacecolor=RED, markersize=8,
                    label='Inverted direction'),
    ]
    ax2.legend(handles=handles2, loc='upper center', bbox_to_anchor=(0.5, -0.06),
               ncol=2, frameon=False, labelcolor=SUBTEXT, fontsize=8.5, handletextpad=0.4,
               columnspacing=1.4)

    fig.text(0.5, 0.01,
            'Every point is a day. The line summarizes the cloud: sloping up = momentum, sloping down = reversal, flat = random.',
              ha='center', fontsize=9.5, style='italic', color=SUBTEXT)

    fig.tight_layout(rect=[0, 0.08, 1, 1])
    plt.show()
    return acf_vals

def plot_seasonality_detailed(df, ret_col='ret', name=''):
    """
    Analyze and plot seasonality by day of week, month, and hour (if intraday).
    Returns (day_means, month_means, hour_means).
    """
    ret = df[ret_col].dropna() * 100
    df_temp = df.loc[ret.index].copy()
    df_temp['ret_pct'] = ret

    # Detect if data is intraday
    is_intraday = False
    if len(df_temp.index) > 2:
        typical_delta = pd.Series(df_temp.index).diff().median()
        is_intraday = pd.notna(typical_delta) and typical_delta < pd.Timedelta('1 day')

    if is_intraday:
        # Compound daily returns
        daily_factor = (1 + df_temp['ret_pct'] / 100).groupby(df_temp.index.date).prod()
        daily_ret = (daily_factor - 1) * 100
        daily_ret.index = pd.to_datetime(daily_ret.index)
        seasonal_df = pd.DataFrame({'ret_pct': daily_ret})
    else:
        seasonal_df = df_temp.copy()

    seasonal_df['year'] = seasonal_df.index.year
    seasonal_df['month'] = seasonal_df.index.month
    seasonal_df['dayofweek'] = seasonal_df.index.dayofweek

    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    day_means = seasonal_df.groupby('dayofweek')['ret_pct'].mean()
    month_means = seasonal_df.groupby('month')['ret_pct'].mean()

    best_day = day_means.idxmax()
    worst_day = day_means.idxmin()
    best_month = month_means.idxmax()
    worst_month = month_means.idxmin()

    # Heatmap: compounded return by year and month
    def _compound(x):
        return ((1 + x / 100).prod() - 1) * 100

    pivot = seasonal_df.groupby(['year', 'month'])['ret_pct'].apply(_compound).unstack('month')
    pivot = pivot.reindex(columns=range(1, 13))

    # Hourly averages (if intraday)
    hour_means = None
    if is_intraday:
        df_temp['hour'] = df_temp.index.hour
        hour_means = df_temp.groupby('hour')['ret_pct'].mean()

    n_years = len(pivot.index)
    LEFT, RIGHT, TOP, BOTTOM = 0.055, 0.985, 0.90, 0.115

    fig = _dark_fig((13, max(6.8, 2.6 + 0.36 * n_years)))
    gs = fig.add_gridspec(3, 2, height_ratios=[0.12, 0.12, max(4, n_years * 0.36)],
                           hspace=0.55, wspace=0.13, width_ratios=[1.65, 1])
    fig.subplots_adjust(left=LEFT, right=RIGHT, top=TOP, bottom=BOTTOM)

    # Best / worst day
    ax_h1 = fig.add_subplot(gs[0, :])
    ax_h1.axis('off')
    ax_h1.set_xlim(0, 1)
    ax_h1.text(0.0, 0.5, 'Best / worst day:', color=SUBTEXT, fontsize=10.5,
               fontweight='bold', va='center', ha='left', transform=ax_h1.transAxes)
    ax_h1.text(0.155, 0.5, f'{day_names[best_day]}  {day_means[best_day]:+.2f}%',
               color=GREEN, fontsize=10.5, fontweight='bold', va='center', ha='left',
               transform=ax_h1.transAxes)
    ax_h1.text(0.275, 0.5, f'{day_names[worst_day]}  {day_means[worst_day]:+.2f}%',
               color=RED, fontsize=10.5, fontweight='bold', va='center', ha='left',
               transform=ax_h1.transAxes)

    # Best / worst month
    ax_h2 = fig.add_subplot(gs[1, :])
    ax_h2.axis('off')
    ax_h2.set_xlim(0, 1)
    ax_h2.text(0.0, 0.5, 'Best / worst month:', color=SUBTEXT, fontsize=10.5,
               fontweight='bold', va='center', ha='left', transform=ax_h2.transAxes)
    ax_h2.text(0.155, 0.5, f'{month_names[best_month - 1]}  {month_means[best_month]:+.2f}%',
               color=GREEN, fontsize=10.5, fontweight='bold', va='center', ha='left',
               transform=ax_h2.transAxes)
    ax_h2.text(0.275, 0.5, f'{month_names[worst_month - 1]}  {month_means[worst_month]:+.2f}%',
               color=RED, fontsize=10.5, fontweight='bold', va='center', ha='left',
               transform=ax_h2.transAxes)

    # Heatmap
    ax_hm = fig.add_subplot(gs[2, 0])
    data = pivot.values.astype(float)
    finite = data[np.isfinite(data)]
    vmax = max(np.abs(finite).max(), 1e-9) if finite.size else 1e-9
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    cmap = LinearSegmentedColormap.from_list('perf_heat_local', [HEAT_RED, HEAT_NEUTRAL, GREEN])
    NO_DATA = '#3c3f47'
    cmap.set_bad(color=NO_DATA)
    masked = np.ma.masked_invalid(data)

    ax_hm.imshow(masked, cmap=cmap, norm=norm, aspect='auto',
                 extent=(-0.5, 11.5, n_years - 0.5, -0.5))

    # Cell labels
    cell_fontsize = float(np.clip(230 / max(n_years, 10), 5.8, 8.2))
    for r in range(n_years):
        for c in range(12):
            v = data[r, c]
            if not np.isfinite(v):
                continue
            rgba = cmap(norm(v))
            luminance = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
            txt_color = '#0c0e12' if luminance > 0.62 else '#eef0f2'
            ax_hm.text(c, r, f'{v:+.2f}', ha='center', va='center',
                       fontsize=cell_fontsize, color=txt_color, fontweight='medium',
                       zorder=3)

    ax_hm.set_title('HEATMAP · RETURN BY MONTH AND YEAR (%)', color=SUBTEXT,
                     fontsize=9.5, loc='left', pad=10, fontweight='bold')
    ax_hm.set_xlim(-0.5, 11.5)
    ax_hm.set_ylim(n_years - 0.5, -0.5)
    ax_hm.set_xticks(range(12))
    ax_hm.set_xticklabels(month_names, color=SUBTEXT, fontsize=8.5)
    ax_hm.xaxis.set_ticks_position('top')
    ax_hm.xaxis.set_label_position('top')
    ax_hm.set_yticks(range(n_years))
    ax_hm.set_yticklabels(pivot.index, color=SUBTEXT, fontsize=8.3, ha='right')
    ax_hm.set_xticks(np.arange(-0.5, 12, 1), minor=True)
    ax_hm.set_yticks(np.arange(-0.5, n_years, 1), minor=True)
    ax_hm.grid(which='minor', color=BG, linewidth=1.6)
    ax_hm.tick_params(which='both', length=0, pad=6)
    for spine in ax_hm.spines.values():
        spine.set_visible(False)

    # Hourly average bar chart
    ax_hr = fig.add_subplot(gs[2, 1])
    ax_hr.set_facecolor(PANEL_BG)
    for spine in ax_hr.spines.values():
        spine.set_visible(False)
    ax_hr.set_title('AVERAGE RETURN BY HOUR (%)', color=SUBTEXT, fontsize=9.5,
                     loc='left', pad=10, fontweight='bold')
    if hour_means is not None:
        hours_to_plot = [h for h in hour_means.index if 6 <= h <= 22]
        vals = [hour_means[h] for h in hours_to_plot]
        colors = [GREEN if v > 0 else RED for v in vals]
        x_pos = np.arange(len(hours_to_plot))
        ax_hr.bar(x_pos, vals, color=colors, width=0.55, linewidth=0, zorder=2)
        ax_hr.axhline(y=0, color=SUBTEXT, linewidth=0.5, alpha=0.7, zorder=1)
        tick_idx = [i for i, h in enumerate(hours_to_plot) if h % 3 == 0]
        ax_hr.set_xlim(-0.7, len(hours_to_plot) - 0.3)
        ax_hr.set_xticks(tick_idx)
        ax_hr.set_xticklabels([f'{hours_to_plot[i]}h' for i in tick_idx],
                              color=SUBTEXT, fontsize=8.5)
        ax_hr.set_yticks([])
        ax_hr.tick_params(length=0, pad=6)
    else:
        ax_hr.set_xticks([])
        ax_hr.set_yticks([])
        ax_hr.text(0.5, 0.5, 'No intraday data', color=SUBTEXT, fontsize=9,
                   ha='center', va='center', transform=ax_hr.transAxes)

    fig.text(LEFT, BOTTOM - 0.045,
              'Green = tends to perform well; red = tends to perform poorly.',
              fontsize=8.5, color=SUBTEXT, ha='left', va='center')
    fig.text(0.5, BOTTOM - 0.08,
              'What it is for: finding calendar biases to exploit them (trade on '
              'good days) or avoid them (skip the bad ones).',
              ha='center', va='center', fontsize=9.5, style='italic', color=SUBTEXT)

    fig.suptitle(f'Patterns - {name}' if name else 'Patterns',
                 color=GREEN, fontsize=13.5, fontweight='bold', x=LEFT, ha='left', y=0.965)

    plt.show()
    return day_means, month_means, hour_means

def plot_extreme_events_detailed(df, ret_col='ret', top_n=12, name=''):
    """
    Plot extreme events (largest up/down moves) and display statistics.
    Returns (top_up, top_down) as Series.
    """
    ret_all = df[ret_col].dropna() * 100
    n_total = len(ret_all)

    biggest_up = ret_all.max()
    biggest_up_date = ret_all.idxmax()
    biggest_down = ret_all.min()
    biggest_down_date = ret_all.idxmin()

    mu = ret_all.mean()
    sigma = ret_all.std()
    shock_mask = (ret_all - mu).abs() > 3 * sigma
    n_shock = int(shock_mask.sum())
    pct_shock = (n_shock / n_total * 100) if n_total > 0 else 0.0

    half = max(top_n // 2, 1)
    top_up = ret_all.nlargest(half)
    top_down = ret_all.nsmallest(half)
    extremes = pd.concat([top_up, top_down]).sort_values()

    fig = _dark_fig((11, 8.8))
    gs = fig.add_gridspec(4, 1,
                           height_ratios=[0.5, 1.25, 0.14, max(3.6, len(extremes) * 0.34)],
                           hspace=0.55)
    fig.subplots_adjust(left=0.065, right=0.97, top=0.95, bottom=0.075)

    # Header
    ax_title = fig.add_subplot(gs[0])
    ax_title.axis('off')
    ax_title.set_xlim(0, 1)
    ax_title.text(0.0, 0.9, 'Events', color=GREEN, fontsize=16, fontweight='bold',
                  ha='left', va='top', transform=ax_title.transAxes)
    ax_title.text(0.0, 0.42, 'REACTION?', color=SUBTEXT, fontsize=9, fontweight='bold',
                  ha='left', va='top', transform=ax_title.transAxes)
    header_txt = (f'The most extreme moves in {name}\'s history' if name
                  else 'The most extreme moves in the history')
    ax_title.text(0.0, 0.02,
                  header_txt + ' — the worst-case scenario your system has to survive '
                  'without blowing up.',
                  color=TEXT, fontsize=9.8, ha='left', va='top',
                  transform=ax_title.transAxes, wrap=True)

    # Stats rows
    ax_stats = fig.add_subplot(gs[1])
    ax_stats.axis('off')
    ax_stats.set_xlim(0, 1)
    rows = [
        ('Biggest up', f'+{biggest_up:.1f}%  ·  {biggest_up_date:%Y-%m-%d}', GREEN),
        ('Biggest down', f'{biggest_down:.1f}%  ·  {biggest_down_date:%Y-%m-%d}', RED),
        ('Shock days (>3σ)', f'{n_shock:,} of {n_total:,} returns · {pct_shock:.2f}%', TEXT),
    ]
    y0, dy = 0.82, 0.36
    for i, (label, value, color) in enumerate(rows):
        y = y0 - i * dy
        ax_stats.text(0.0, y, label, color=SUBTEXT, fontsize=10.5, ha='left', va='center',
                      transform=ax_stats.transAxes)
        ax_stats.text(1.0, y, value, color=color, fontsize=11.5, fontweight='bold',
                      ha='right', va='center', transform=ax_stats.transAxes)
        if i < len(rows) - 1:
            ax_stats.axhline(y=y - dy / 2, xmin=0, xmax=1, color=GRID, linewidth=0.8)

    # Section label
    ax_label = fig.add_subplot(gs[2])
    ax_label.axis('off')
    ax_label.set_xlim(0, 1)
    ax_label.text(0.0, 0.5, f'THE {len(extremes)} MOST EXTREME DAYS', color=SUBTEXT,
                  fontsize=9.5, fontweight='bold', ha='left', va='center',
                  transform=ax_label.transAxes)

    # Bar chart
    ax = fig.add_subplot(gs[3])
    ax.set_facecolor(PANEL_BG)
    colors = [GREEN if x > 0 else RED for x in extremes.values]
    ax.barh(range(len(extremes)), extremes.values, color=colors, alpha=0.9,
            linewidth=0, height=0.62)
    ax.axvline(x=0, color=SUBTEXT, linewidth=0.6)
    ax.set_yticks(range(len(extremes)))
    ax.set_yticklabels([d.strftime('%Y-%m-%d') for d in extremes.index],
                       color=SUBTEXT, fontsize=9)
    ax.set_xticks([])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    xmax = extremes.abs().max()
    ax.set_xlim(-xmax * 1.28, xmax * 1.28)
    for i, (date, val) in enumerate(extremes.items()):
        ax.text(val + (xmax * 0.04 if val > 0 else -xmax * 0.04), i, f'{val:+.1f}%',
                verticalalignment='center', fontsize=8.7, fontweight='bold',
                color=TEXT, ha='left' if val > 0 else 'right')

    fig.text(0.065, 0.04,
              "Each bar is one of the asset's most brutal days. They tend to coincide "
              "with news or crises — your strategy has to survive these days.",
              fontsize=8.8, color=SUBTEXT, ha='left')
    fig.text(0.065, 0.012,
              'What it is for: designing your stop and sizing to withstand the worst '
              'days without blowing up the account.',
              fontsize=8.8, color=GREEN, ha='left', style='italic', fontweight='bold')

    plt.show()
    return top_up, top_down

def plot_system_recommendation_detailed(mr_pct, trend_pct, acf1, arch, day_means, month_means,
                                         pct_extreme, event, name=''):
    """
    Generate a visual panel with system recommendation (mean reversion vs trending)
    and a condition table.
    Returns (rec, rec_explore).
    """
    if mr_pct > trend_pct + 10:
        rec = "MEAN REVERSION"
        rec_explore = "fade / reversal"
    elif trend_pct > mr_pct + 10:
        rec = "TRENDING"
        rec_explore = "momentum / breakout"
    else:
        rec = f"MIXED (MR: {mr_pct:.0f}%, Trend: {trend_pct:.0f}%)"
        rec_explore = "a combination of both"

    vol_reg = "high" if arch > 0.3 else "low"
    day_std = day_means.std() if len(day_means) > 0 else 0
    month_std = month_means.std() if len(month_means) > 0 else 0
    seasonal_level = "high" if (day_std > 0.1 or month_std > 0.1) else "low"

    rows = [
        {'condition': 'Autocorrelation positive', 'explore': 'trend / momentum',
         'kind': 'bar', 'value': trend_pct, 'highlight': acf1 > 0.05},
        {'condition': 'Autocorrelation negative', 'explore': 'mean reversion',
         'kind': 'bar', 'value': mr_pct, 'highlight': acf1 < -0.05},
        {'condition': 'Volatility regimes', 'explore': 'volatility expansion',
         'kind': 'badge', 'value': vol_reg, 'highlight': vol_reg == 'high'},
        {'condition': 'Seasonal patterns', 'explore': 'seasonal systems',
         'kind': 'badge', 'value': seasonal_level, 'highlight': seasonal_level == 'high'},
        {'condition': 'Response to events', 'explore': 'event-driven',
         'kind': 'badge', 'value': event, 'highlight': event == 'high'},
    ]

    fig = _dark_fig((11, 7.4))
    ax = fig.add_subplot(111)
    ax.axis('off')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    _flat_rect(ax, (0.0, 0.0), 1.0, 1.0, PANEL_BG, zorder=0)

    PAD_X = 0.035

    # Title
    ax.text(PAD_X, 0.955, 'From behavior to ', color=TEXT, fontsize=16, fontweight='bold',
            ha='left', va='top', transform=ax.transAxes)
    ax.text(PAD_X + 0.205, 0.955, 'system.', color=GREEN, fontsize=16, fontweight='bold',
            style='italic', ha='left', va='top', transform=ax.transAxes)
    ax.text(PAD_X, 0.905, "It doesn't hand you a ready-made strategy — it tells you which "
                           "direction to explore.",
            color=SUBTEXT, fontsize=9, ha='left', va='top', transform=ax.transAxes)

    # Split bar
    label_y = 0.815
    ax.text(PAD_X, label_y, 'Mean reversion', color=GREEN, fontsize=9.5, fontweight='bold',
            ha='left', va='center', transform=ax.transAxes)
    ax.text(1 - PAD_X, label_y, 'Trending', color=BLUE, fontsize=9.5, fontweight='bold',
            ha='right', va='center', transform=ax.transAxes)

    bar_h = 0.058
    bar_top = 0.79
    bar_w = 1 - 2 * PAD_X
    mr_w = bar_w * (mr_pct / 100)
    trend_w = bar_w - mr_w

    _flat_rect(ax, (PAD_X, bar_top - bar_h), mr_w, bar_h, GREEN, zorder=2)
    _flat_rect(ax, (PAD_X + mr_w, bar_top - bar_h), trend_w, bar_h, BLUE, zorder=2)
    ax.text(PAD_X + mr_w / 2, bar_top - bar_h / 2, f'{mr_pct:.0f}%', color=BG, fontsize=10,
            fontweight='bold', ha='center', va='center', transform=ax.transAxes, zorder=3)
    ax.text(PAD_X + mr_w + trend_w / 2, bar_top - bar_h / 2, f'{trend_pct:.0f}%', color=TEXT,
            fontsize=10, fontweight='bold', ha='center', va='center', transform=ax.transAxes, zorder=3)

    # Recommendation sentence
    sent_y = bar_top - bar_h - 0.075
    ax.text(PAD_X, sent_y, 'This asset is more likely ', color=TEXT, fontsize=11,
            ha='left', va='center', transform=ax.transAxes)
    ax.text(PAD_X + 0.205, sent_y, f'{rec}', color=TEXT, fontsize=11, fontweight='bold',
            ha='left', va='center', transform=ax.transAxes)
    ax.text(PAD_X + 0.205 + 0.012 * len(rec), sent_y, ' → explore ', color=TEXT, fontsize=11,
            ha='left', va='center', transform=ax.transAxes)
    explore_x = PAD_X + 0.205 + 0.012 * len(rec) + 0.105
    ax.text(explore_x, sent_y, f'{rec_explore}.', color=GREEN, fontsize=11, fontweight='bold',
            ha='left', va='center', transform=ax.transAxes)

    # Table
    table_top = sent_y - 0.075
    ax.text(PAD_X, table_top, 'IF THE ASSET SHOWS…', color=SUBTEXT, fontsize=8.3,
            fontweight='bold', ha='left', va='center', transform=ax.transAxes)
    ax.text(0.40, table_top, 'EXPLORE…', color=SUBTEXT, fontsize=8.3, fontweight='bold',
            ha='left', va='center', transform=ax.transAxes)
    ax.text(0.72, table_top, 'IN THIS ASSET', color=SUBTEXT, fontsize=8.3, fontweight='bold',
            ha='left', va='center', transform=ax.transAxes)
    ax.axhline(y=table_top - 0.028, xmin=0.015, xmax=0.985, color=GRID, linewidth=0.8)

    row_top = table_top - 0.055
    row_h = 0.115
    value_bar_x = 0.72
    value_bar_w = 0.16

    for i, row in enumerate(rows):
        ytop = row_top - i * row_h
        ybottom = ytop - row_h * 0.86
        ycenter = (ytop + ybottom) / 2

        if row['highlight']:
            _rounded_rect(ax, (0.012, ybottom - 0.006), 0.976, (ytop - ybottom) + 0.012,
                          ROW_HIGHLIGHT, radius=0.01, zorder=1)

        ax.text(PAD_X, ycenter, row['condition'], color=TEXT, fontsize=9.6,
                ha='left', va='center', transform=ax.transAxes, zorder=2)
        ax.text(0.40, ycenter, f"→ {row['explore']}",
                color=GREEN if row['highlight'] else SUBTEXT, fontsize=9.3,
                fontweight='bold' if row['highlight'] else 'normal',
                ha='left', va='center', transform=ax.transAxes, zorder=2)

        if row['kind'] == 'bar':
            _rounded_rect(ax, (value_bar_x, ycenter - 0.014), value_bar_w, 0.028,
                          GRID, radius=0.01, zorder=2)
            fill_w = value_bar_w * (row['value'] / 100)
            _rounded_rect(ax, (value_bar_x, ycenter - 0.014), max(fill_w, 0.004), 0.028,
                          GREEN, radius=0.01, zorder=3)
            ax.text(value_bar_x + value_bar_w + 0.025, ycenter, f"{row['value']:.0f}%",
                    color=TEXT, fontsize=9, ha='left', va='center',
                    transform=ax.transAxes, zorder=3)
        else:
            bg_c, text_c = _badge_color(row['value'])
            badge_w = 0.08
            badge_x = value_bar_x + 0.02
            _rounded_rect(ax, (badge_x, ycenter - 0.02), badge_w, 0.04,
                          bg_c, radius=0.02, zorder=2)
            ax.text(badge_x + badge_w / 2, ycenter, str(row['value']),
                    color=text_c, fontsize=8.7, fontweight='bold', ha='center', va='center',
                    transform=ax.transAxes, zorder=3)

    plt.show()
    return rec, rec_explore

def plot_glossary_detailed(mean_ret, vol_ann, skew, skew_label, kurt, kurt_label, normal,
                            acf1, hurst, clustering, seasonal, n_extreme, pct_extreme, name=''):
    """
    Generate a glossary panel with definitions and values for each metric.
    """
    items = [
        ('Mean Return',
         'How much it goes up or down on average per period. If positive, the price has '
         'an upward drift (long-term trend).',
         f'{mean_ret:.2f}%'),
        ('Annualized Volatility',
         'How much the price swings, annualized. Used to compare risk across different assets.',
         f'{vol_ann:.1f}%'),
        ('Skewness',
         f"Which side the surprises lean toward. {'Negative' if skew < 0 else 'Positive'} means "
         f"{'down' if skew < 0 else 'up'} moves are more violent than "
         f"{'up' if skew < 0 else 'down'} moves.",
         f'{skew:.2f} ({skew_label})'),
        ('Excess Kurtosis',
         f"How frequent extreme events are. {'High' if kurt > 3 else 'Low'} = "
         f"{'more' if kurt > 3 else 'fewer'} shocks than a normal distribution would predict.",
         f'{kurt:.2f} ({kurt_label})'),
        ('Normality (Jarque-Bera)',
         'Test if returns follow a normal distribution. In markets, they almost never do.',
         f'{normal}'),
        ('Autocorrelation',
         f"Whether today's return resembles yesterday's. {'Positive' if acf1 > 0 else 'Negative'} "
         f"means {'persistence (momentum)' if acf1 > 0 else 'reversal (mean reversion)'}.",
         f'Lag 1: {acf1:.3f}'),
        ('Hurst Exponent',
         f"Measures price memory. {'>0.5' if hurst > 0.5 else '<0.5' if hurst < 0.5 else '~0.5'} = "
         f"{'trending' if hurst > 0.5 else 'reverting' if hurst < 0.5 else 'random walk (no memory)'}.",
         f'{hurst:.3f}'),
        ('Volatility Clustering',
         'Calm and turmoil come in waves: a volatile day tends to be followed by another '
         'volatile day (ARCH effect).',
         f'{clustering}'),
        ('Seasonality',
         'Whether certain days, months, or hours consistently yield different returns '
         '(e.g., the "Monday effect").',
         f"{'Yes' if seasonal == 'high' else 'Low'}"),
        ('Extreme Events',
         'The largest moves in history. Measure the surprise risk your system must withstand.',
         f'{n_extreme} days >3σ ({pct_extreme:.1f}%)'),
    ]

    n_cols = 3
    n_rows = int(np.ceil(len(items) / n_cols))

    fig = _dark_fig((11, 2.1 + n_rows * 1.55))
    ax = fig.add_subplot(111)
    ax.axis('off')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    _flat_rect(ax, (0.0, 0.0), 1.0, 1.0, PANEL_BG, zorder=0)

    PAD_X = 0.035
    ax.text(PAD_X, 0.95, 'Glossary', color=GREEN, fontsize=15, fontweight='bold',
            ha='left', va='top', transform=ax.transAxes)
    ax.text(PAD_X, 0.895, 'WHAT EACH NUMBER MEANS', color=SUBTEXT, fontsize=8.3,
            fontweight='bold', ha='left', va='top', transform=ax.transAxes)

    grid_top = 0.83
    grid_bottom = 0.02
    col_w = (1 - 2 * PAD_X) / n_cols
    row_h = (grid_top - grid_bottom) / n_rows

    for idx, (title, desc, value) in enumerate(items):
        col = idx % n_cols
        row = idx // n_cols
        x = PAD_X + col * col_w
        y_top = grid_top - row * row_h

        ax.text(x, y_top, title, color=TEXT, fontsize=10, fontweight='bold',
                ha='left', va='top', transform=ax.transAxes)

        wrapped = textwrap.fill(desc, width=40)
        ax.text(x, y_top - 0.075, wrapped, color=SUBTEXT, fontsize=8.3,
                ha='left', va='top', transform=ax.transAxes, linespacing=1.5)

        ax.text(x, y_top - row_h * 0.72, f'→ {value}', color=GREEN, fontsize=9,
                fontweight='bold', ha='left', va='top', transform=ax.transAxes)

    plt.show()

# ============================================================================
# MAIN ANALYSIS FUNCTION
# ============================================================================

def analyze_timeframe_detailed(df, name):
    """
    Run full analysis for a DataFrame with OHLCV columns.
    Prints results, generates plots, and returns a dict with key metrics.
    """
    print(f"\n{'='*70}")
    print(f"COMPLETE ANALYSIS: {name}")
    print(f"{'='*70}")
    print(f"Bars: {len(df)}")
    print(f"Period: {df.index.min()} → {df.index.max()}")

    df = df.copy()
    df['ret'] = df['close'].pct_change()
    df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
    ret = df['ret'].dropna()

    print("\n" + "="*70)
    print("SHORT-TERM BEHAVIOR          LONG-TERM DRIFT (TREND)")
    print("="*70)

    hurst = compute_hurst(df['close'].values, max_lag=min(100, len(df)//2))
    if not np.isnan(hurst):
        if hurst < 0.45:
            cp = "MEAN REVERSION"
        elif hurst > 0.55:
            cp = "TRENDING"
        else:
            cp = "RANDOM WALK"
        print(f"{cp}")
        print(f"Hurst {hurst:.2f}")
    else:
        print("Hurst not available")

    precio_inicial = df['close'].iloc[0]
    precio_final = df['close'].iloc[-1]
    años = (df.index.max() - df.index.min()).days / 365.25
    cagr = ((precio_final / precio_inicial) ** (1 / años) - 1) * 100 if años > 0 else 0
    mean_ret_annual = cagr

    if mean_ret_annual > 2:
        deriva = "BULLISH"
    elif mean_ret_annual < -2:
        deriva = "BEARISH"
    else:
        deriva = "NEUTRAL"
    print(f"{deriva}")
    print(f"~{mean_ret_annual:.1f}%/year (mean return)")

    print("\n" + "="*70)
    print("DISTRIBUTION")
    print("TAILS?")
    print("="*70)

    ret_pct = ret * 100
    mean_ret = ret_pct.mean()

    df_daily = df.resample('D').agg({'close': 'last'}).dropna()
    df_daily['log_ret'] = np.log(df_daily['close'] / df_daily['close'].shift(1))
    daily_log_ret = df_daily['log_ret'].dropna()
    vol_ann = daily_log_ret.std() * np.sqrt(252) * 100 if len(daily_log_ret) > 0 else np.nan

    skew = ret_pct.skew()
    kurt = ret_pct.kurtosis()
    jb_stat, jb_p = jarque_bera(ret_pct)
    normal = "NOT normal" if jb_p < 0.05 else "Normal"
    three_sigma = 3 * ret.std() * 100
    extreme_days = ret_pct[np.abs(ret_pct) > three_sigma]
    pct_extreme = len(extreme_days) / len(ret_pct) * 100

    if skew > 0.1:
        skew_label = "right tail"
    elif skew < -0.1:
        skew_label = "left tail"
    else:
        skew_label = "symmetric"

    if kurt > 3:
        kurt_label = "fat tails"
    elif kurt < -1:
        kurt_label = "thin tails"
    else:
        kurt_label = "normal"

    print(f"Mean return: {mean_ret:.2f}%")
    print(f"Annualized volatility: {vol_ann:.1f}%")
    print(f"Skewness: {skew:.2f} ({skew_label})")
    print(f"Excess Kurtosis: {kurt:.2f} ({kurt_label})")
    print(f"Normality: {normal}")
    print(f"Extreme days (>3σ): {len(extreme_days)} ({pct_extreme:.1f}%)")

    mu_fit, std_fit = plot_distribution_detailed(df, 'ret', name)

    print("\n" + "="*70)
    print("VOLATILITY")
    print("REGIMES?")
    print("="*70)

    vol_hist = ret.std() * 100
    vol_recent = ret.tail(20).std() * 100
    ratio = vol_recent / vol_hist if vol_hist > 0 else 0
    vol_sq = ret**2
    arch_lag1 = vol_sq.autocorr(lag=1) if len(vol_sq) > 1 else np.nan
    clustering = "low" if arch_lag1 < 0.2 else "moderate" if arch_lag1 < 0.4 else "strong"

    print(f"Recent vs Mean vol: {ratio:.2f}x")
    print(f"Recent volatility (daily): {vol_recent:.2f}%")
    print(f"Historical volatility (daily): {vol_hist:.2f}%")
    print(f"Comes in waves? {clustering}")

    vol_hist_val, vol_recent_val, ratio_val = plot_volatility_detailed(df, 'ret', 20, name)

    print("\n" + "="*70)
    print("AUTOCORRELATION · MEMORY")
    print("PERSISTENCE?")
    print("="*70)

    acf_vals = compute_acf(ret, nlags=40)
    for lag in [1, 5, 20]:
        if lag < len(acf_vals):
            val = acf_vals[lag]
            interpret = "reverts" if val < 0 else "persists" if val > 0.05 else "~0"
            print(f"Lag {lag} · vs {'yesterday' if lag==1 else f'{lag} days ago'}: {val:.2f} {interpret}")

    acf_vals = plot_acf_detailed(df, 'ret', 40, name)

    print("\n" + "="*70)
    print("PATTERNS")
    print("SEASONALITY?")
    print("="*70)

    day_means, month_means, hour_means = plot_seasonality_detailed(df, 'ret', name)

    day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    print("\nAverage return by day of week (Mon-Fri, %):")
    for i in range(5):
        if i in day_means.index:
            print(f"{day_names[i]}: {day_means[i]:.2f}%")

    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    print("\nAverage return by month (%):")
    for i, val in month_means.items():
        print(f"{month_names[i-1]}: {val:.2f}%")

    if hour_means is not None:
        print("\nAverage return by hour (6:00-22:00, %):")
        for h in range(6, 23):
            if h in hour_means.index:
                print(f"{h:02d}:00: {hour_means[h]:.2f}%")

    print("\n" + "="*70)
    print("EXTREME EVENTS")
    print("REACTION?")
    print("="*70)

    top_up, top_down = plot_extreme_events_detailed(df, 'ret', 12, name)

    print(f"Biggest up: +{top_up.max():.1f}%")
    print(f"Biggest down: {top_down.min():.1f}%")
    print(f"Shock days (>3σ): {len(extreme_days)} of {len(ret):,} returns · {pct_extreme:.2f}%")

    print("\nTop 12 up days:")
    for date, val in top_up.items():
        print(f"+{val:.1f}% - {date.strftime('%Y-%m-%d')}")

    print("\nTop 12 down days:")
    for date, val in top_down.items():
        print(f"{val:.1f}% - {date.strftime('%Y-%m-%d')}")

    print("\n" + "="*70)
    print("FROM BEHAVIOR TO SYSTEM")
    print("="*70)

    score_mr = 0
    score_trend = 0

    if not np.isnan(hurst):
        if hurst < 0.45:
            score_mr += 40
        elif hurst > 0.55:
            score_trend += 40
        else:
            score_mr += 20
            score_trend += 20

    acf1 = acf_vals[1] if len(acf_vals) > 1 else 0
    if acf1 < -0.05:
        score_mr += 30
    elif acf1 > 0.05:
        score_trend += 30
    else:
        score_mr += 15
        score_trend += 15

    arch = arch_lag1 if not np.isnan(arch_lag1) else 0
    if arch > 0.3:
        score_trend += 15
    elif arch < 0.15:
        score_mr += 15
    else:
        score_mr += 7.5
        score_trend += 7.5

    if skew < -0.5 and kurt > 3:
        score_mr += 15
    elif skew > 0.5 and kurt > 3:
        score_trend += 15
    else:
        score_mr += 7.5
        score_trend += 7.5

    total = score_mr + score_trend
    if total > 0:
        mr_pct = (score_mr / total) * 100
        trend_pct = (score_trend / total) * 100
    else:
        mr_pct = 50
        trend_pct = 50

    print(f"Mean reversion: {mr_pct:.0f}%")
    print(f"Trending: {trend_pct:.0f}%")

    if mr_pct > trend_pct + 10:
        rec = "MEAN REVERSION"
        rec_explore = "fade / reversal"
    elif trend_pct > mr_pct + 10:
        rec = "TRENDING"
        rec_explore = "momentum / breakout"
    else:
        rec = f"MIXED (MR: {mr_pct:.0f}%, Trend: {trend_pct:.0f}%)"
        rec_explore = "a combination of both"

    print(f"\nThis asset is more likely {rec} → explore {rec_explore}.")

    print("\n" + "-"*50)
    print("If the asset shows...\tExplore...\tIn this asset")
    print("-"*50)

    acf_label = "positive" if acf1 > 0.05 else "negative" if acf1 < -0.05 else "neutral"
    acf_pct = f"{mr_pct:.0f}%" if acf1 < -0.05 else f"{trend_pct:.0f}%" if acf1 > 0.05 else "~0%"
    print(f"Autocorrelation {acf_label}\t→ {'trend / momentum' if acf1 > 0 else 'mean reversion' if acf1 < 0 else 'random'}\t{acf_pct}")

    vol_reg = "high" if arch > 0.3 else "low"
    print(f"Volatility regimes\t→ volatility expansion\t{vol_reg}")

    day_std = day_means.std() if len(day_means) > 0 else 0
    month_std = month_means.std() if len(month_means) > 0 else 0
    seasonal = "high" if (day_std > 0.1 or month_std > 0.1) else "low"
    print(f"Seasonal patterns\t→ seasonal systems\t{seasonal}")

    event = "high" if pct_extreme > 2 else "low" if pct_extreme < 0.5 else "medium"
    print(f"Response to events\t→ event-driven\t{event}")

    # Visual panel: "From behavior to system."
    plot_system_recommendation_detailed(mr_pct, trend_pct, acf1, arch, day_means, month_means,
                                         pct_extreme, event, name)

    print("\n" + "="*70)
    print("GLOSSARY")
    print("WHAT EACH NUMBER MEANS")
    print("="*70)

    print(f"""
Mean Return
How much it goes up or down on average per period. If positive, the price has an upward drift (long-term trend).
→ {mean_ret:.2f}%

Annualized Volatility
How much the price swings, annualized. Used to compare risk across different assets.
→ {vol_ann:.1f}%

Skewness
Which side the surprises lean toward. {'Negative' if skew < 0 else 'Positive'} means {'down' if skew < 0 else 'up'} moves are more violent than {'up' if skew < 0 else 'down'} moves.
→ {skew:.2f} ({skew_label})

Excess Kurtosis
How frequent extreme events are. {'High' if kurt > 3 else 'Low'} = {'more' if kurt > 3 else 'fewer'} shocks than a normal distribution would predict.
→ {kurt:.2f} ({kurt_label})

Normality (Jarque-Bera)
Test if returns follow a normal distribution. In markets, they almost never do.
→ {normal}

Autocorrelation
Whether today's return resembles yesterday's. {'Positive' if acf1 > 0 else 'Negative'} means {'persistence (momentum)' if acf1 > 0 else 'reversal (mean reversion)'}.
→ Lag 1: {acf1:.3f}

Hurst Exponent
Measures price memory. {'>0.5' if hurst > 0.5 else '<0.5' if hurst < 0.5 else '~0.5'} = {'trending' if hurst > 0.5 else 'reverting' if hurst < 0.5 else 'random walk (no memory)'}.
→ {hurst:.3f}

Volatility Clustering
Calm and turmoil come in waves: a volatile day tends to be followed by another volatile day (ARCH effect).
→ {clustering}

Seasonality
Whether certain days, months, or hours consistently yield different returns (e.g., the "Monday effect").
→ {'Yes' if seasonal == 'high' else 'Low'}

Extreme Events
The largest moves in history. Measure the surprise risk your system must withstand.
→ {len(extreme_days)} days >3σ ({pct_extreme:.1f}%)
""")

    # Visual panel: "Glossary"
    plot_glossary_detailed(mean_ret, vol_ann, skew, skew_label, kurt, kurt_label, normal,
                            acf1, hurst, clustering, seasonal, len(extreme_days), pct_extreme, name)

    print(f"\n{'='*70}\n")

    return {
        'name': name,
        'mean_ret': mean_ret,
        'vol_ann': vol_ann,
        'skew': skew,
        'kurt': kurt,
        'normal': normal,
        'pct_extreme': pct_extreme,
        'hurst': hurst,
        'mr_pct': mr_pct,
        'trend_pct': trend_pct,
        'acf1': acf1,
        'arch': arch_lag1,
        'seasonal': seasonal,
        'event': event
    }

# ============================================================================
# DATA LOADING AND RESAMPLING HELPERS
# ============================================================================

def load_data_from_mongo(collection_name, uri_env='MONGODB_URI_FUTURES_3',
                         db_name_env='MONGODB_DB', default_db='market_data',
                         date_field='timestamp'):
    """
    Load OHLCV data from MongoDB and return a DataFrame with datetime index.
    """
    uri = os.environ.get(uri_env)
    if not uri:
        raise ValueError(f"Environment variable {uri_env} not set")
    client = MongoClient(uri)
    db_name = os.getenv(db_name_env, default_db)
    db = client[db_name]
    collection = db[collection_name]

    projection = {'_id': 0, date_field: 1, 'open': 1, 'high': 1, 'low': 1, 'close': 1, 'volume': 1}
    cursor = collection.find({}, projection)
    df = pd.DataFrame(list(cursor))
    if df.empty:
        raise ValueError("No data found in collection")
    df['time'] = pd.to_datetime(df[date_field])
    df.set_index('time', inplace=True)
    df.drop(columns=[date_field], inplace=True)
    df.sort_index(inplace=True)
    return df

def resample_timeframes(df, frequencies=None):
    """
    Resample OHLCV DataFrame to multiple frequencies.
    Returns a dict {name: resampled_df}.
    """
    if frequencies is None:
        frequencies = {'15min': '15min', '1H': 'h', '4H': '4h', '1D': 'D'}
    result = {}
    for name, freq in frequencies.items():
        resampled = df.resample(freq).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        result[name] = resampled
    return result


# ============================================================================
# BACKTESTING AND OPTIMIZATION UTILITIES (for strategy development)
# ============================================================================

def compute_rsi(data, period=2):
    """Compute RSI for a given period."""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_atr(df, period=14):
    """Compute Average True Range for a DataFrame with OHLC."""
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

def prepare_data(df, entry_threshold, rsi_threshold, atr_stop, atr_target,
                 time_stop_hour=15, time_stop_minute=50):
    """
    Prepare data with indicators and entry signals for the ES 15min Mean Reversion strategy.
    """
    df = df.copy()
    df['close_pct_change'] = df['close'].pct_change() * 100
    df['volume_ma20'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma20']
    df['rsi2'] = compute_rsi(df['close'], period=2)
    df['atr'] = compute_atr(df, period=14)
    
    df['hour'] = df.index.hour
    df['minute'] = df.index.minute
    df['dayofweek'] = df.index.dayofweek  # Monday=0, Sunday=6
    
    # Entry signals (long and short)
    df['long_entry'] = (df['close_pct_change'] < -entry_threshold) & (df['rsi2'] < rsi_threshold) & (df['volume_ratio'] > 1.2) & (df['hour'] >= 9) & (df['hour'] <= 15) & (df['dayofweek'].isin([1,2,3,4]))
    df['short_entry'] = (df['close_pct_change'] > entry_threshold) & (df['rsi2'] > (100 - rsi_threshold)) & (df['volume_ratio'] > 1.2) & (df['hour'] >= 9) & (df['hour'] <= 15) & (df['dayofweek'].isin([1,2,3,4]))
    
    return df

def run_backtest(df, stop_multiplier, target_multiplier, time_hour=15, time_min=50):
    """
    Run backtest with ATR-based stops and time stop.
    Returns DataFrame with trades and P&L.
    """
    trades = []
    position = None
    entry_price = None
    entry_time = None
    entry_type = None
    atr_value = None
    
    for idx, row in df.iterrows():
        if position is not None:
            # Time stop
            if idx.hour > time_hour or (idx.hour == time_hour and idx.minute >= time_min):
                exit_price = row['close']
                exit_time = idx
                reason = 'time_stop'
                trade = {
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'type': entry_type,
                    'reason': reason
                }
                trades.append(trade)
                position = None
                continue
            
            if atr_value is None:
                break
            
            stop_dist = atr_value * stop_multiplier
            target_dist = atr_value * target_multiplier
            
            if entry_type == 'long':
                if row['low'] <= entry_price - stop_dist:
                    exit_price = entry_price - stop_dist
                    reason = 'stop_loss'
                elif row['high'] >= entry_price + target_dist:
                    exit_price = entry_price + target_dist
                    reason = 'take_profit'
                else:
                    continue
            else:  # short
                if row['high'] >= entry_price + stop_dist:
                    exit_price = entry_price + stop_dist
                    reason = 'stop_loss'
                elif row['low'] <= entry_price - target_dist:
                    exit_price = entry_price - target_dist
                    reason = 'take_profit'
                else:
                    continue
            
            exit_time = idx
            trade = {
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'type': entry_type,
                'reason': reason
            }
            trades.append(trade)
            position = None
            continue
        
        # Check for new entries
        if row['long_entry']:
            position = 'long'
            entry_price = row['close']
            entry_time = idx
            entry_type = 'long'
            atr_value = row['atr']
        elif row['short_entry']:
            position = 'short'
            entry_price = row['close']
            entry_time = idx
            entry_type = 'short'
            atr_value = row['atr']
    
    trades_df = pd.DataFrame(trades)
    if len(trades_df) == 0:
        return trades_df
    
    trades_df['pnl'] = np.where(trades_df['type'] == 'long',
                               (trades_df['exit_price'] - trades_df['entry_price']) / trades_df['entry_price'] * 100,
                               (trades_df['entry_price'] - trades_df['exit_price']) / trades_df['entry_price'] * 100)
    trades_df['win'] = trades_df['pnl'] > 0
    
    return trades_df

def compute_metrics(trades_df, cost_per_trade=0.0, contracts=1):
    """
    Compute key performance metrics from a trades DataFrame.
    
    Parameters:
    -----------
    trades_df : DataFrame
        DataFrame with columns: pnl, win, entry_price, exit_price, type
    cost_per_trade : float, optional (default=0.0)
        Total cost per trade in dollars (commission + slippage) per contract
    contracts : int, optional (default=1)
        Number of contracts per trade
    
    Returns:
    --------
    dict: num_trades, win_rate, avg_win, avg_loss, profit_factor,
          expectancy, total_pnl, sharpe, max_drawdown
    """
    if len(trades_df) == 0:
        return {
            'num_trades': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'expectancy': 0,
            'total_pnl': 0,
            'sharpe': 0,
            'max_drawdown': 0
        }
    
    trades_df = trades_df.copy()
    
    # Apply costs - convert dollars to percentage using entry_price
    if cost_per_trade > 0 and 'entry_price' in trades_df.columns:
        total_cost = cost_per_trade * contracts
        cost_pct = (total_cost / trades_df['entry_price']) * 100
        trades_df['pnl'] = trades_df['pnl'] - cost_pct
        trades_df['win'] = trades_df['pnl'] > 0
    
    wins = trades_df[trades_df['win']]
    losses = trades_df[~trades_df['win']]
    
    win_rate = len(wins) / len(trades_df) * 100
    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
    profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else np.inf
    expectancy = trades_df['pnl'].mean()
    total_pnl = trades_df['pnl'].sum()
    
    # Sharpe ratio (annualized)
    returns = trades_df['pnl'] / 100  # decimal returns
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    
    # Maximum drawdown
    cumulative = trades_df['pnl'].cumsum()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / 100  # decimal
    max_drawdown = drawdown.min() * 100  # percentage
    
    return {
        'num_trades': len(trades_df),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'total_pnl': total_pnl,
        'sharpe': sharpe,
        'max_drawdown': max_drawdown
    }

def optimize_sequential(df, entry_thresholds, rsi_thresholds, stop_multipliers, target_multipliers,
                        time_hour=15, time_min=50, cost_per_trade=0.0):
    """
    Perform sequential optimization on in-sample data.
    Returns dict with optimal parameters.
    """
    best_params = {}
    print("\n" + "="*70)
    print("SEQUENTIAL OPTIMIZATION")
    print("="*70)
    
    # Step 1: Entry threshold
    print("\nStep 1: Optimizing Entry Threshold")
    threshold_results = []
    for threshold in entry_thresholds:
        df_prep = prepare_data(df, threshold, 20, 2.0, 3.0)
        trades = run_backtest(df_prep, 2.0, 3.0, time_hour, time_min)
        metrics = compute_metrics(trades, cost_per_trade)
        threshold_results.append({'threshold': threshold, **metrics})
    threshold_df = pd.DataFrame(threshold_results)
    print(threshold_df[['threshold', 'num_trades', 'win_rate', 'profit_factor', 'expectancy', 'sharpe', 'max_drawdown']].to_string(index=False))
    best_params['entry_threshold'] = threshold_df.loc[threshold_df['profit_factor'].idxmax(), 'threshold']
    print(f"\nBest threshold: {best_params['entry_threshold']}")
    
    # Step 2: RSI
    print("\nStep 2: Optimizing RSI Threshold")
    rsi_results = []
    for rsi in rsi_thresholds:
        df_prep = prepare_data(df, best_params['entry_threshold'], rsi, 2.0, 3.0)
        trades = run_backtest(df_prep, 2.0, 3.0, time_hour, time_min)
        metrics = compute_metrics(trades, cost_per_trade)
        rsi_results.append({'rsi': rsi, **metrics})
    rsi_df = pd.DataFrame(rsi_results)
    print(rsi_df[['rsi', 'num_trades', 'win_rate', 'profit_factor', 'expectancy', 'sharpe', 'max_drawdown']].to_string(index=False))
    best_params['rsi_threshold'] = rsi_df.loc[rsi_df['profit_factor'].idxmax(), 'rsi']
    print(f"\nBest RSI: {best_params['rsi_threshold']}")
    
    # Step 3: ATR stop
    print("\nStep 3: Optimizing ATR Stop Multiplier")
    stop_results = []
    for stop in stop_multipliers:
        df_prep = prepare_data(df, best_params['entry_threshold'], best_params['rsi_threshold'], stop, 3.0)
        trades = run_backtest(df_prep, stop, 3.0, time_hour, time_min)
        metrics = compute_metrics(trades, cost_per_trade)
        stop_results.append({'stop': stop, **metrics})
    stop_df = pd.DataFrame(stop_results)
    print(stop_df[['stop', 'num_trades', 'win_rate', 'profit_factor', 'expectancy', 'sharpe', 'max_drawdown']].to_string(index=False))
    best_params['atr_stop'] = stop_df.loc[stop_df['profit_factor'].idxmax(), 'stop']
    print(f"\nBest ATR stop: {best_params['atr_stop']}")
    
    # Step 4: ATR target
    print("\nStep 4: Optimizing ATR Target Multiplier")
    target_results = []
    for target in target_multipliers:
        df_prep = prepare_data(df, best_params['entry_threshold'], best_params['rsi_threshold'], best_params['atr_stop'], target)
        trades = run_backtest(df_prep, best_params['atr_stop'], target, time_hour, time_min)
        metrics = compute_metrics(trades, cost_per_trade)
        target_results.append({'target': target, **metrics})
    target_df = pd.DataFrame(target_results)
    print(target_df[['target', 'num_trades', 'win_rate', 'profit_factor', 'expectancy', 'sharpe', 'max_drawdown']].to_string(index=False))
    best_params['atr_target'] = target_df.loc[target_df['profit_factor'].idxmax(), 'target']
    print(f"\nBest ATR target: {best_params['atr_target']}")
    
    print("\n" + "="*70)
    print("OPTIMAL PARAMETERS")
    print("="*70)
    for k, v in best_params.items():
        print(f"{k}: {v}")
    
    return best_params

def walk_forward_analysis(df, param_grid, train_years=5, test_years=1,
                          start_year=2009, end_year=2020, cost_per_trade=0.0):
    """
    Perform walk-forward analysis with sequential optimization per cycle.
    Returns DataFrame with results for each OOS period.
    """
    results = []
    years = sorted(df.index.year.unique())
    years = [y for y in years if start_year <= y <= end_year]
    
    for start in range(start_year, end_year - train_years):
        train_start = start
        train_end = start + train_years
        test_start = train_end
        test_end = test_start + test_years
        
        # Filter data
        train_data = df[(df.index.year >= train_start) & (df.index.year < train_end)]
        test_data = df[(df.index.year >= test_start) & (df.index.year < test_end)]
        
        if len(train_data) < 100 or len(test_data) < 10:
            continue
        
        # Optimize on train_data
        best_params = optimize_sequential(
            train_data,
            entry_thresholds=[0.5, 0.7, 1.0],
            rsi_thresholds=[15, 20, 25],
            stop_multipliers=[1.5, 2.0, 2.5],
            target_multipliers=[2.5, 3.0, 3.5],
            cost_per_trade=cost_per_trade
        )
        
        # Test on test_data
        df_prep = prepare_data(
            test_data,
            best_params['entry_threshold'],
            best_params['rsi_threshold'],
            best_params['atr_stop'],
            best_params['atr_target']
        )
        trades = run_backtest(df_prep, best_params['atr_stop'], best_params['atr_target'])
        metrics = compute_metrics(trades, cost_per_trade=cost_per_trade)
        
        results.append({
            'train_start': train_start,
            'train_end': train_end,
            'test_start': test_start,
            'test_end': test_end,
            'pf': metrics['profit_factor'],
            'win_rate': metrics['win_rate'],
            'num_trades': metrics['num_trades'],
            'total_pnl': metrics['total_pnl'],
            'sharpe': metrics['sharpe'],
            'max_dd': metrics['max_drawdown'],
            'params': best_params
        })
    
    return pd.DataFrame(results)

def monte_carlo_bootstrap(trades_df, n_simulations=10000):
    """
    Run Monte Carlo bootstrap simulation on a trades DataFrame.
    Returns dict with percentiles and probability of positive P&L.
    """
    if len(trades_df) == 0:
        return None
    
    pnl_array = trades_df['pnl'].values
    n_trades = len(pnl_array)
    
    mc_final_pnl = []
    mc_max_dd = []
    mc_profit_factor = []
    
    for _ in range(n_simulations):
        sampled = np.random.choice(pnl_array, size=n_trades, replace=True)
        cumulative = np.cumsum(sampled)
        mc_final_pnl.append(cumulative[-1])
        
        running_max = np.maximum.accumulate(cumulative)
        dd = (cumulative - running_max)
        mc_max_dd.append(dd.min())
        
        wins = sampled[sampled > 0]
        losses = sampled[sampled < 0]
        pf = abs(wins.sum() / losses.sum()) if len(losses) > 0 and losses.sum() != 0 else np.inf
        mc_profit_factor.append(pf)
    
    mc_final_pnl = np.array(mc_final_pnl)
    mc_max_dd = np.array(mc_max_dd)
    mc_profit_factor = np.array(mc_profit_factor)
    
    return {
        'p5': np.percentile(mc_final_pnl, 5),
        'p50': np.percentile(mc_final_pnl, 50),
        'p95': np.percentile(mc_final_pnl, 95),
        'p99': np.percentile(mc_final_pnl, 99),
        'prob_positive': np.mean(mc_final_pnl > 0) * 100,
        'dd_p95': np.percentile(mc_max_dd, 95),
        'dd_p99': np.percentile(mc_max_dd, 99),
        'pf_p50': np.percentile(mc_profit_factor, 50),
        'pf_p95': np.percentile(mc_profit_factor, 5),  # worst 5%
    }

def parameter_sensitivity_analysis(df, optimal_params, variations, time_hour=15, time_min=50, cost_per_trade=0.0):
    """
    Perform parameter sensitivity analysis by varying each parameter ±20%.
    Returns a DataFrame with results for each variation.
    """
    results = []
    for param, values in variations.items():
        for val in values:
            params = optimal_params.copy()
            params[param] = val
            
            df_prep = prepare_data(
                df,
                params['entry_threshold'],
                params['rsi_threshold'],
                params['atr_stop'],
                params['atr_target']
            )
            trades = run_backtest(df_prep, params['atr_stop'], params['atr_target'])
            metrics = compute_metrics(trades, cost_per_trade=cost_per_trade)
            
            results.append({
                'param': param,
                'value': val,
                'num_trades': metrics['num_trades'],
                'profit_factor': metrics['profit_factor'],
                'expectancy': metrics['expectancy'],
                'total_pnl': metrics['total_pnl'],
                'max_drawdown': metrics['max_drawdown']
            })
    
    return pd.DataFrame(results)

def plot_equity_curve(trades_df, title='Equity Curve'):
    """Plot equity curve from trades DataFrame."""
    if len(trades_df) == 0:
        print("No trades to plot.")
        return
    
    trades_df = trades_df.copy()
    trades_df['cum_pnl'] = trades_df['pnl'].cumsum()
    
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(trades_df['exit_time'], trades_df['cum_pnl'], color='#2E86C1', linewidth=1.5)
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_title(title, fontweight='bold')
    ax.set_ylabel('Cumulative P&L (%)')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

def plot_trade_distribution(trades_df, title='Trade Distribution'):
    """Plot trade P&L distribution."""
    if len(trades_df) == 0:
        print("No trades to plot.")
        return
    
    colors = ['#2ECC71' if x > 0 else '#E74C3C' for x in trades_df['pnl']]
    
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(range(len(trades_df)), trades_df['pnl'], color=colors, alpha=0.7)
    ax.axhline(y=0, color='black', linewidth=0.5)
    ax.set_title(title, fontweight='bold')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('P&L (%)')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
