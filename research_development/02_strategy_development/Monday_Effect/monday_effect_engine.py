"""
monday_effect_engine.py  ·  02_strategy_development/MondayEffect/monday_effect_engine.py

Motor del edge BTC · Efecto Lunes (velas de 1 h, UTC). Misma forma de API que rsi2_engine
para que los notebooks 01/02/03 sigan el mismo patron:

    load_data / prepare / run_monday_backtest / daily_returns / trade_mtm_paths /
    walk_forward_fixed / set_engine_defaults / ENGINE_DEFAULTS

Regla (v3):
  - Senal al CIERRE de la vela de las 23:00 UTC del domingo; compra en la APERTURA del lunes 00:00.
  - Filtro de volatilidad: ATR(atr_len) en % del precio >= percentil `atr_pctl` de su ultimo ano
    (pctl_window velas). Aqui se mide como RANGO: share de la ventana estrictamente por debajo de hoy
    (atr_rank) >= atr_pctl/100. Equivale al percentil salvo por la interpolacion de np.percentile.
  - Filtro de calendario: no se opera el primer lunes del mes (dia <= 7).
  - Salida por tiempo: apertura de `hold_bars` velas despues (24 -> martes 00:00). Sin stop ni target.
  - Costes: cost_bps_per_side por lado (14 = Binance spot). Para CFD: spread/slippage por lado +
    financing_bps_per_night por cada rollover (rollover_hour_utc) cruzado mientras se mantiene.

Convenciones:
  - trades['pnl'] esta en % con el 100 % del capital (igual que utils.compute_metrics).
  - trades['pnl_frac'] = pnl * size_fraction (el tamano real del robot, 40 %).
  - Los indicadores se precalculan en prepare() sobre TODO el historico; luego se puede cortar
    df en IS/OOS sin perder el calentamiento del percentil (igual que hace rsi2_engine con la SMA).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
H1 = pd.Timedelta(hours=1)

ENGINE_DEFAULTS = dict(
    data_source="csv_hourly",
    csv_path="../../../data/binance/BTCUSDT_1h.csv",
    atr_len=48,
    pctl_window=8760,          # 1 ano de velas horarias
    pctl_min_bars=4380,        # calentamiento minimo del percentil (medio ano). Ajustable
    entry_dow=0,               # 0 = lunes
    entry_hour=0,              # UTC
    hold_bars=24,
    skip_first_monday=True,
    cost_bps_per_side=14.0,    # Binance spot: comision + spread + slippage
    financing_bps_per_night=0.0,
    rollover_hour_utc=22,      # solo cuenta si financing_bps_per_night > 0
    size_fraction=0.40,
)


def set_engine_defaults(**kw):
    for k, v in kw.items():
        if k not in ENGINE_DEFAULTS:
            raise KeyError(f"'{k}' no es un engine_default valido. Validos: {sorted(ENGINE_DEFAULTS)}")
        ENGINE_DEFAULTS[k] = v


def _cfg(name, value):
    return ENGINE_DEFAULTS[name] if value is None else value


# ------------------------------------------------------------------ datos
def _find_csv(csv_path) -> Path:
    p = Path(csv_path)
    if p.is_absolute():
        if p.is_file():
            return p
        raise FileNotFoundError(p)
    tail = Path(*[s for s in p.parts if s != ".."])
    cwd = Path.cwd().resolve()
    cands = [cwd / p, _HERE / p]
    cands += [b / tail for b in (cwd, *cwd.parents, _HERE, *_HERE.parents)]
    for c in cands:
        if c.is_file():
            return c.resolve()
    raise FileNotFoundError(f"No encontre '{csv_path}'. Probe desde cwd={cwd} y desde {_HERE}.")


def load_data(ticker=None, start=None, end=None, source=None, csv_path=None):
    """CSV horario -> DataFrame OHLCV con indice UTC naive (nombre 'time')."""
    source = source or ENGINE_DEFAULTS["data_source"]
    if source != "csv_hourly":
        raise ValueError("Este motor solo usa CSV horario (csv_hourly); no hay Yahoo.")
    path = _find_csv(csv_path or ENGINE_DEFAULTS["csv_path"])
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
    tcol = next((c for c in ("open_time", "timestamp", "time", "datetime", "date", "open_timestamp")
                 if c in raw.columns), None)
    if tcol is None:
        raise KeyError(f"Sin columna de tiempo. Columnas: {list(raw.columns)}")
    t = raw[tcol]
    if pd.api.types.is_numeric_dtype(t):
        m = float(t.iloc[0])
        unit = "us" if m > 1e15 else "ms" if m > 1e11 else "s"
        idx = pd.to_datetime(t, unit=unit, utc=True)
    else:
        idx = pd.to_datetime(t, utc=True)
    need = ["open", "high", "low", "close"]
    miss = [c for c in need if c not in raw.columns]
    if miss:
        raise KeyError(f"Faltan columnas {miss}. Columnas: {list(raw.columns)}")
    cols = need + (["volume"] if "volume" in raw.columns else [])
    df = raw[cols].astype(float)
    df.index = pd.DatetimeIndex(idx).tz_convert(None)
    df.index.name = "time"
    df = df[~df.index.duplicated(keep="first")].sort_index()
    if start is not None:
        df = df[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    gaps = int((df.index.to_series().diff().dropna() != H1).sum())
    if gaps:
        print(f"WARNING: {gaps} saltos distintos de 1 h en el indice (huecos). Los lunes con hueco se descartan.")
    return df


# ------------------------------------------------------------------ indicadores
def _atr_pct(df, atr_len):
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(atr_len).mean() / df["close"] * 100.0


def _entry_positions(index, dow, hour):
    """Posiciones de las velas de entrada (lunes 00:00 UTC) cuya vela anterior es contigua (1 h)."""
    m = (index.dayofweek == dow) & (index.hour == hour) & (index.minute == 0)
    pos = np.flatnonzero(m)
    pos = pos[pos >= 1]
    if len(pos) == 0:
        return pos
    return pos[np.asarray((index[pos] - index[pos - 1]) == H1)]


def prepare(df, atr_len=None, pctl_window=None, pctl_min_bars=None, entry_dow=None, entry_hour=None):
    """
    Anade: atr_pct, ret24 (% de las ultimas 24 velas) y, SOLO en las velas de entrada (entry_ok=True,
    con la vela de senal contigua): atr_sig / ret24_sig (valores de la vela de senal, para poder cortar df
    justo en un lunes sin perder la operacion) y atr_rank (
    share de la ventana de `pctl_window` velas previas, hasta la vela de senal incluida, que queda
    estrictamente por debajo del ATR% de la vela de senal).
    """
    atr_len, pctl_window = _cfg("atr_len", atr_len), _cfg("pctl_window", pctl_window)
    pctl_min_bars = _cfg("pctl_min_bars", pctl_min_bars)
    entry_dow, entry_hour = _cfg("entry_dow", entry_dow), _cfg("entry_hour", entry_hour)
    d = df.copy()
    d["atr_pct"] = _atr_pct(d, atr_len)
    d["ret24"] = d["close"].pct_change(24) * 100.0
    a = d["atr_pct"].to_numpy(float)
    r24 = d["ret24"].to_numpy(float)
    rank = np.full(len(d), np.nan)
    atr_sig, r24_sig = np.full(len(d), np.nan), np.full(len(d), np.nan)
    entry_ok = np.zeros(len(d), bool)
    for i in _entry_positions(d.index, entry_dow, entry_hour):
        s = i - 1  # vela de senal (cierre del domingo 23:00)
        entry_ok[i], atr_sig[i], r24_sig[i] = True, a[s], r24[s]
        if np.isnan(a[s]):
            continue
        w = a[max(0, s - pctl_window + 1): s + 1]
        w = w[~np.isnan(w)]
        if len(w) < pctl_min_bars:
            continue
        rank[i] = float((w < a[s]).mean())
    d["atr_rank"], d["atr_sig"], d["ret24_sig"], d["entry_ok"] = rank, atr_sig, r24_sig, entry_ok
    d.attrs.update(atr_len=atr_len, pctl_window=pctl_window, entry_dow=entry_dow, entry_hour=entry_hour)
    return d


def _pick(df, key, value):
    have = df.attrs.get(key)
    if value is not None and have is not None and have != value:
        raise ValueError(f"df fue preparado con {key}={have} pero pediste {key}={value}: vuelve a llamar prepare().")
    return value if value is not None else (have if have is not None else ENGINE_DEFAULTS[key])


def _rollovers(t0, t1, hour):
    first = t0.normalize() + pd.Timedelta(hours=hour)
    if first <= t0:
        first += pd.Timedelta(days=1)
    return 0 if first > t1 else int((t1 - first) / pd.Timedelta(days=1)) + 1


# ------------------------------------------------------------------ backtest
TRADE_COLS = ["entry_time", "exit_time", "entry_price", "exit_price", "type", "pnl", "win", "bars",
              "i_ent", "i_sal", "atr_pct", "atr_rank", "pnl_frac"]


def run_monday_backtest(df, atr_pctl=30.0, vol_mode="pctl", atr_band=None, max_abs_ret24_pct=None,
                        atr_len=None, skip_first_monday=None, entry_dow=None, entry_hour=None,
                        hold_bars=None, cost_bps_per_side=None, financing_bps_per_night=None,
                        rollover_hour_utc=None, size_fraction=None):
    """
    vol_mode: 'pctl' (v3: atr_rank >= atr_pctl/100) | 'band' (v1: atr_band=(lo, hi) en ATR%) | 'none'.
    Lunes desnudo = vol_mode='none', skip_first_monday=False.
    max_abs_ret24_pct: filtro opcional de la v1 (|retorno de las 24 velas previas a la senal| <= x %).
    """
    if "atr_rank" not in df.columns:
        raise ValueError("Llama primero a prepare(df).")
    _pick(df, "atr_len", atr_len)
    _pick(df, "entry_dow", entry_dow), _pick(df, "entry_hour", entry_hour)   # solo valida contra prepare()
    hold = int(_cfg("hold_bars", hold_bars))
    skip1 = _cfg("skip_first_monday", skip_first_monday)
    cost = _cfg("cost_bps_per_side", cost_bps_per_side) / 1e4
    fin_bps = _cfg("financing_bps_per_night", financing_bps_per_night)
    roll_h = _cfg("rollover_hour_utc", rollover_hour_utc)
    frac = _cfg("size_fraction", size_fraction)
    if vol_mode not in ("pctl", "band", "none"):
        raise ValueError("vol_mode debe ser 'pctl', 'band' o 'none'")

    idx, n = df.index, len(df)
    o = df["open"].to_numpy(float)
    rank, atr, r24 = (df[c].to_numpy(float) for c in ("atr_rank", "atr_sig", "ret24_sig"))
    rows = []
    for i in np.flatnonzero(df["entry_ok"].to_numpy(bool)):
        j = i + hold
        if j >= n or (idx[j] - idx[i]) != hold * H1:
            continue
        if skip1 and idx[i].day <= 7:
            continue
        if vol_mode == "pctl" and (np.isnan(rank[i]) or rank[i] < atr_pctl / 100.0):
            continue
        if vol_mode == "band":
            lo, hi = atr_band
            if np.isnan(atr[i]) or not (lo <= atr[i] <= hi):
                continue
        if max_abs_ret24_pct is not None and (np.isnan(r24[i]) or abs(r24[i]) > max_abs_ret24_pct):
            continue
        entry, exit_ = o[i] * (1 + cost), o[j] * (1 - cost)
        nights = _rollovers(idx[i], idx[j], roll_h) if fin_bps else 0
        pnl = (exit_ / entry - 1) * 100.0 - nights * fin_bps / 100.0
        rows.append(dict(entry_time=idx[i], exit_time=idx[j], entry_price=entry, exit_price=exit_,
                         type="long", pnl=pnl, win=pnl > 0, bars=hold, i_ent=int(i), i_sal=int(j),
                         atr_pct=atr[i], atr_rank=rank[i], pnl_frac=pnl * frac))
    return pd.DataFrame(rows, columns=TRADE_COLS)


# ------------------------------------------------------------------ retornos (MTM)
def _size(sizing):
    if isinstance(sizing, (int, float)):
        return float(sizing)
    if sizing == "capital":
        return 1.0
    if sizing == "fraction":
        return float(ENGINE_DEFAULTS["size_fraction"])
    raise ValueError("sizing debe ser 'capital', 'fraction' o un numero (fraccion del capital)")


def trade_mtm_paths(df, trades, sizing="fraction"):
    """Una serie de retornos por operacion (pasos horarios, ya escalados al tamano). Una por fila de trades."""
    s, c, out = _size(sizing), df["close"].to_numpy(float), []
    for r in trades.itertuples():
        i, j = int(r.i_ent), int(r.i_sal)
        fin = (r.exit_price / r.entry_price - 1.0) - r.pnl / 100.0   # financing total (fraccion)
        p = np.empty(j - i + 1)
        p[0] = c[i] / r.entry_price - 1.0
        p[1:j - i] = c[i + 1:j] / c[i:j - 1] - 1.0
        p[j - i] = r.exit_price / c[j - 1] - 1.0
        p[-1] -= fin
        out.append(s * p)
    return out


def daily_returns(price_df, trades, sizing="fraction"):
    """Retorno MTM por dia UTC (0 en dias sin posicion). Paso final de la salida va al dia de la ultima vela."""
    lr = np.zeros(len(price_df))
    if len(trades):
        for (i, j), p in zip(trades[["i_ent", "i_sal"]].to_numpy(int), trade_mtm_paths(price_df, trades, sizing)):
            l, m = np.log1p(p), j - i
            lr[i:j] += l[:m]
            lr[j - 1] += l[m]
    s = pd.Series(lr, index=price_df.index).groupby(price_df.index.normalize()).sum()
    return np.expm1(s)


def walk_forward_fixed(df, rules, is_years=3, sizing="fraction"):
    """
    Reglas fijas (sin reajustar): para cada ano Y con `is_years` anos completos previos, compara el
    retorno anualizado del IS con el retorno del ano Y (OOS). El primer ano de los datos se considera
    parcial y no entra como IS. Devuelve year, ret_is_anual, ret_oos, mdd_oos, n_oos.
    """
    trades = run_monday_backtest(df, **rules)
    daily = daily_returns(df, trades, sizing)
    years = sorted(set(daily.index.year))
    ty = pd.to_datetime(trades["entry_time"]).dt.year if len(trades) else pd.Series(dtype=int)
    rows = []
    for y in years:
        is_ys = list(range(y - is_years, y))
        if y - is_years <= years[0] or not all(k in years for k in is_ys):
            continue
        tot_is = (1 + daily[daily.index.year.isin(is_ys)]).prod()
        eq = (1 + daily[daily.index.year == y]).cumprod()
        rows.append(dict(year=y, ret_is_anual=tot_is ** (1 / is_years) - 1, ret_oos=float(eq.iloc[-1] - 1),
                         mdd_oos=float((eq / eq.cummax() - 1).min()), n_oos=int((ty == y).sum())))
    return pd.DataFrame(rows)