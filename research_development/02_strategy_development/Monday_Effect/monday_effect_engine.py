"""
monday_effect_engine.py  ·  02_strategy_development/MondayEffect/monday_effect_engine.py

Motor del edge BTC · Efecto Lunes (velas de 1 h, UTC). Misma forma de API que rsi2_engine
para que los notebooks 01/02/03 sigan el mismo patron:

    load_data / prepare / run_monday_backtest / daily_returns / trade_mtm_paths /
    walk_forward_fixed / set_engine_defaults / ENGINE_DEFAULTS

Extensiones CFD y riesgo (v3.1):

    apply_cfd_preset / CFD_PRESETS            specs de lote y swap del simbolo (Axi MT5)
    lot_size / min_capital_for_target         tamano real en lotes y capital minimo del lote minimo
    cfd_trade_sizes                           fraccion efectiva por operacion con lotes redondeados
    hourly_returns                            retorno MTM por vela de 1 h (base del drawdown hora a hora)
    annual_returns                            tabla anual reutilizable (retorno, caida, operaciones, parcial, hard limit)
    hard_limit_report                         chequeo de la caida maxima contra el hard limit
    max_fraction_for_limit                    mayor fraccion de capital cuyo historico respeta el hard limit

Novedades v3.2 (TODO es opt-in: con los defaults los resultados son identicos a la v3.1):

    atr_method = "sma" | "wilder"             "sma" = media simple del TR (como iATR de MT5, defecto).
                                              "wilder" = RMA (como ta.atr de TradingView): para reconciliar
                                              con la referencia publicada.
    gap_mode = "rows" | "strict"              "rows" = ATR, ret24 y ventana del percentil cuentan FILAS (defecto).
                                              "strict" = cuentan HORAS: si falta una vela, el ATR queda NaN
                                              durante atr_len horas y la ventana del percentil es de 8760 h reales.
    hourly_worst_returns /                    drawdown INTRAVELA: usa el minimo (low) de cada vela en vez del
    hard_limit_report_intrabar                cierre. Es el chequeo mas honesto contra un hard limit en equity.
    max_fraction_for_limit(intrabar=True)     idem para la fraccion maxima.
    quote_to_account                          factor para pasar el precio de la cotizacion a la divisa de la
                                              cuenta (p. ej. 1/USDJPY si el CSV es BTCJPY en yenes y la cuenta en
                                              USD). Con un CSV en USD y cuenta en USD se deja en 1.0.

Novedades v3.3 (solo load_data; el resto del motor no cambia y los resultados son identicos):

    load_data lee CSV con separador distinto de la coma (coma, tabulador, punto y coma) y avisa con un error
    claro si le pasas el export CRUDO de MetaTrader (cabeceras <DATE> <TIME>, hora del SERVIDOR, no UTC):
    ese archivo hay que convertirlo antes con convert_axi_h1.py. El mensaje de "sin columna de tiempo"
    ahora incluye la ruta del archivo y la columna que habria que renombrar.

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
  - trades['pnl_frac'] = pnl * size_fraction (el tamano real del robot).
  - Los indicadores se precalculan en prepare() sobre TODO el historico; luego se puede cortar
    df en IS/OOS sin perder el calentamiento del percentil (igual que hace rsi2_engine con la SMA).
  - `sizing` acepta 'capital', 'fraction', un numero, o un array/Series con una fraccion por operacion
    (la salida de cfd_trade_sizes).
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
    atr_method="sma",          # "sma" (MT5 iATR) | "wilder" (TradingView ta.atr)
    gap_mode="rows",           # "rows" (cuenta filas) | "strict" (cuenta horas reales; huecos -> NaN)
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
    contract_size=1.0,
    min_lot=0.01,
    lot_step=0.01,
    quote_to_account=1.0,      # precio de la cotizacion -> divisa de la cuenta (1/USDJPY si el CSV esta en JPY)
)

CFD_PRESETS = {
    "axi_btcjpy": dict(contract_size=1.0, min_lot=0.01, lot_step=0.01,
                       financing_bps_per_night=15.0 / 365.0 * 100.0, rollover_hour_utc=22),
    "axi_btcusd": dict(contract_size=1.0, min_lot=0.1, lot_step=0.1,
                       financing_bps_per_night=20.0 / 365.0 * 100.0, rollover_hour_utc=22),
}


def set_engine_defaults(**kw):
    for k, v in kw.items():
        if k not in ENGINE_DEFAULTS:
            raise KeyError(f"'{k}' no es un engine_default valido. Validos: {sorted(ENGINE_DEFAULTS)}")
        ENGINE_DEFAULTS[k] = v


def apply_cfd_preset(name, cost_bps_per_side, quote_to_account=None):
    """Carga lote minimo, paso, tamano de contrato y swap largo del simbolo. El spread por lado se pasa a mano.
    quote_to_account (opcional): factor precio -> divisa de la cuenta (ver cabecera)."""
    if name not in CFD_PRESETS:
        raise KeyError(f"Preset '{name}' no existe. Validos: {sorted(CFD_PRESETS)}")
    extra = {} if quote_to_account is None else dict(quote_to_account=float(quote_to_account))
    set_engine_defaults(**CFD_PRESETS[name], cost_bps_per_side=float(cost_bps_per_side), **extra)
    return {k: ENGINE_DEFAULTS[k] for k in (*CFD_PRESETS[name], "cost_bps_per_side", "quote_to_account")}


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


def _read_csv_any_sep(path: Path) -> pd.DataFrame:
    """Lee el CSV con coma (lo normal). Si sale una sola columna, reintenta detectando el separador
    (tabulador / punto y coma), que es lo que escribe MetaTrader."""
    raw = pd.read_csv(path)
    if raw.shape[1] == 1:
        raw = pd.read_csv(path, sep=None, engine="python")
    return raw


def load_data(ticker=None, start=None, end=None, source=None, csv_path=None):
    """CSV horario -> DataFrame OHLCV con indice UTC naive (nombre 'time')."""
    source = source or ENGINE_DEFAULTS["data_source"]
    if source != "csv_hourly":
        raise ValueError("Este motor solo usa CSV horario (csv_hourly); no hay Yahoo.")
    path = _find_csv(csv_path or ENGINE_DEFAULTS["csv_path"])
    raw = _read_csv_any_sep(path)
    if any(str(c).strip().startswith("<") for c in raw.columns):
        raise ValueError(
            f"'{path.name}' parece el export CRUDO de MetaTrader (cabeceras tipo <DATE> <TIME>): esta en hora del "
            f"SERVIDOR, no en UTC. Convierte primero con convert_axi_h1.py y apunta csv_path al CSV resultante "
            f"(columna 'time' en UTC). Columnas: {list(raw.columns)}")
    raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
    tcol = next((c for c in ("open_time", "timestamp", "time", "datetime", "date", "open_timestamp")
                 if c in raw.columns), None)
    if tcol is None:
        raise KeyError(f"Sin columna de tiempo en '{path}'. Renombra la columna de fechas a 'time' (UTC). "
                       f"Columnas: {list(raw.columns)}")
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
def _atr_pct(df, atr_len, method="sma", strict=False):
    """ATR en % del cierre. method: 'sma' (media simple del TR) o 'wilder' (RMA).
    strict=True: el TR es NaN si falta la vela previa, y el ATR es NaN salvo que las ultimas atr_len
    velas del indice tengan TR valido (pensado para un indice horario regular con NaN en los huecos)."""
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    if strict:
        tr = tr.where(pc.notna())
    if method == "sma":
        atr = tr.rolling(atr_len).mean()
    elif method == "wilder":
        atr = tr.ewm(alpha=1.0 / atr_len, adjust=False, min_periods=atr_len).mean()
    else:
        raise ValueError("atr_method debe ser 'sma' o 'wilder'")
    if strict:
        atr = atr.where(tr.notna().astype(float).rolling(atr_len).min() == 1.0)
    return atr / df["close"] * 100.0


def _entry_positions(index, dow, hour):
    """Posiciones de las velas de entrada (lunes 00:00 UTC) cuya vela anterior es contigua (1 h)."""
    m = (index.dayofweek == dow) & (index.hour == hour) & (index.minute == 0)
    pos = np.flatnonzero(m)
    pos = pos[pos >= 1]
    if len(pos) == 0:
        return pos
    return pos[np.asarray((index[pos] - index[pos - 1]) == H1)]


def prepare(df, atr_len=None, pctl_window=None, pctl_min_bars=None, entry_dow=None, entry_hour=None,
            atr_method=None, gap_mode=None):
    """
    Anade: atr_pct, ret24 (% de las ultimas 24 velas) y, SOLO en las velas de entrada (entry_ok=True,
    con la vela de senal contigua): atr_sig / ret24_sig (valores de la vela de senal, para poder cortar df
    justo en un lunes sin perder la operacion) y atr_rank (share de la ventana de `pctl_window` velas
    previas, hasta la vela de senal incluida, que queda estrictamente por debajo del ATR% de la vela de senal).

    gap_mode='rows' (defecto) cuenta filas; 'strict' cuenta horas reales y deja NaN donde falten velas.
    """
    atr_len, pctl_window = _cfg("atr_len", atr_len), _cfg("pctl_window", pctl_window)
    pctl_min_bars = _cfg("pctl_min_bars", pctl_min_bars)
    entry_dow, entry_hour = _cfg("entry_dow", entry_dow), _cfg("entry_hour", entry_hour)
    atr_method, gap_mode = _cfg("atr_method", atr_method), _cfg("gap_mode", gap_mode)
    if gap_mode not in ("rows", "strict"):
        raise ValueError("gap_mode debe ser 'rows' o 'strict'")
    d = df.copy()
    if gap_mode == "strict":
        full = pd.date_range(d.index[0], d.index[-1], freq=H1)
        gpos = full.get_indexer(d.index)
        if (gpos < 0).any():
            raise ValueError("gap_mode='strict' necesita velas alineadas a la hora en punto.")
        g = d[["open", "high", "low", "close"]].reindex(full)
        a_grid = _atr_pct(g, atr_len, atr_method, strict=True).to_numpy(float)
        r_grid = g["close"].pct_change(24, fill_method=None).to_numpy(float) * 100.0
        d["atr_pct"], d["ret24"] = a_grid[gpos], r_grid[gpos]
    else:
        d["atr_pct"] = _atr_pct(d, atr_len, atr_method)
        d["ret24"] = d["close"].pct_change(24) * 100.0
        a_grid, gpos = d["atr_pct"].to_numpy(float), np.arange(len(d))
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
        gs = gpos[i] - 1  # posicion de la vela de senal en la rejilla (igual a s en modo 'rows')
        w = a_grid[max(0, gs - pctl_window + 1): gs + 1]
        w = w[~np.isnan(w)]
        if len(w) < pctl_min_bars:
            continue
        rank[i] = float((w < a[s]).mean())
    d["atr_rank"], d["atr_sig"], d["ret24_sig"], d["entry_ok"] = rank, atr_sig, r24_sig, entry_ok
    d.attrs.update(atr_len=atr_len, pctl_window=pctl_window, entry_dow=entry_dow, entry_hour=entry_hour,
                   atr_method=atr_method, gap_mode=gap_mode)
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


# ------------------------------------------------------------------ tamano CFD
def lot_size(capital, price, target_fraction=None, contract_size=None, min_lot=None, lot_step=None,
             quote_to_account=None):
    """Lotes que se pueden abrir sin pasar de target_fraction del capital. 0.0 si no llega al lote minimo.
    price * quote_to_account = precio en la divisa de la cuenta."""
    target_fraction = _cfg("size_fraction", target_fraction)
    contract_size = _cfg("contract_size", contract_size)
    min_lot, lot_step = _cfg("min_lot", min_lot), _cfg("lot_step", lot_step)
    fx = float(_cfg("quote_to_account", quote_to_account))
    if capital <= 0 or price <= 0 or fx <= 0:
        return 0.0
    raw = capital * target_fraction / (price * fx * contract_size)
    lots = round(np.floor(raw / lot_step + 1e-9) * lot_step, 8)
    return float(lots) if lots >= min_lot - 1e-12 else 0.0


def min_capital_for_target(price, target_fraction=None, contract_size=None, min_lot=None, quote_to_account=None):
    """Capital minimo (en la divisa de la cuenta) para que el lote minimo no pese mas que target_fraction."""
    target_fraction = _cfg("size_fraction", target_fraction)
    contract_size, min_lot = _cfg("contract_size", contract_size), _cfg("min_lot", min_lot)
    fx = float(_cfg("quote_to_account", quote_to_account))
    return float(min_lot * contract_size * price * fx / target_fraction)


def cfd_trade_sizes(trades, capital, target_fraction=None, contract_size=None, min_lot=None,
                    lot_step=None, compounding=True, quote_to_account=None):
    """
    Una fila por operacion: lotes, nocional (en la divisa de la cuenta) y fraccion efectiva del capital vigente
    al entrar (size_fraction, lista para usar como `sizing`). Con compounding=True el tamano sigue al equity;
    con False se calcula siempre sobre `capital` inicial. Una operacion con 0 lotes no se toma (retorno 0).
    """
    contract_size = _cfg("contract_size", contract_size)
    fx = float(_cfg("quote_to_account", quote_to_account))
    n = len(trades)
    lots, notional, frac_eff, equity_after = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    equity = float(capital)
    for k, r in enumerate(trades.itertuples()):
        base = equity if compounding else float(capital)
        l = lot_size(base, r.entry_price, target_fraction, contract_size, min_lot, lot_step, fx)
        nom = l * contract_size * r.entry_price * fx
        f = nom / equity if equity > 0 else 0.0
        lots[k], notional[k], frac_eff[k] = l, nom, f
        equity *= 1.0 + f * r.pnl / 100.0
        equity_after[k] = equity
    return pd.DataFrame(dict(entry_time=trades["entry_time"].to_numpy(), lots=lots, notional=notional,
                             size_fraction=frac_eff, taken=lots > 0, equity_after=equity_after),
                        index=trades.index)


# ------------------------------------------------------------------ retornos (MTM)
def _size(sizing):
    if isinstance(sizing, (int, float)):
        return float(sizing)
    if sizing == "capital":
        return 1.0
    if sizing == "fraction":
        return float(ENGINE_DEFAULTS["size_fraction"])
    raise ValueError("sizing debe ser 'capital', 'fraction', un numero o un array con una fraccion por operacion")


def _sizes(sizing, n):
    if isinstance(sizing, (np.ndarray, pd.Series, list, tuple)):
        arr = np.asarray(sizing, float)
        if len(arr) != n:
            raise ValueError(f"sizing tiene {len(arr)} elementos y hay {n} operaciones")
        return arr
    return np.full(n, _size(sizing))


def trade_mtm_paths(df, trades, sizing="fraction"):
    """Una serie de retornos por operacion (pasos horarios, ya escalados al tamano). Una por fila de trades."""
    sizes, c, out = _sizes(sizing, len(trades)), df["close"].to_numpy(float), []
    for s, r in zip(sizes, trades.itertuples()):
        i, j = int(r.i_ent), int(r.i_sal)
        fin = (r.exit_price / r.entry_price - 1.0) - r.pnl / 100.0   # financing total (fraccion)
        p = np.empty(j - i + 1)
        p[0] = c[i] / r.entry_price - 1.0
        p[1:j - i] = c[i + 1:j] / c[i:j - 1] - 1.0
        p[j - i] = (r.exit_price - fin * r.entry_price) / c[j - 1] - 1.0
        out.append(s * p)
    return out


def _step_log_returns(price_df, trades, sizing):
    lr = np.zeros(len(price_df))
    if len(trades):
        for (i, j), p in zip(trades[["i_ent", "i_sal"]].to_numpy(int), trade_mtm_paths(price_df, trades, sizing)):
            l, m = np.log1p(p), j - i
            lr[i:j] += l[:m]
            lr[j - 1] += l[m]
    return pd.Series(lr, index=price_df.index)


def hourly_returns(price_df, trades, sizing="fraction"):
    """Retorno MTM por vela de 1 h (0 en velas sin posicion). Base del drawdown hora a hora."""
    return np.expm1(_step_log_returns(price_df, trades, sizing))


def daily_returns(price_df, trades, sizing="fraction"):
    """Retorno MTM por dia UTC (0 en dias sin posicion). Paso final de la salida va al dia de la ultima vela."""
    s = _step_log_returns(price_df, trades, sizing).groupby(price_df.index.normalize()).sum()
    return np.expm1(s)


def hourly_worst_returns(price_df, trades, sizing="fraction"):
    """
    Peor retorno de cada vela de 1 h DENTRO de la vela (posicion larga valorada al minimo `low`), escalado al
    tamano. Cada paso se mide contra el cierre anterior (la primera vela, contra el precio de entrada con coste).
    0 en velas sin posicion. Siempre <= hourly_returns de esa vela (el paso final de salida no entra aqui).
    """
    sizes = _sizes(sizing, len(trades))
    lo, c = price_df["low"].to_numpy(float), price_df["close"].to_numpy(float)
    out = np.zeros(len(price_df))
    for s, r in zip(sizes, trades.itertuples()):
        i, j = int(r.i_ent), int(r.i_sal)
        w = np.empty(j - i)
        w[0] = lo[i] / r.entry_price - 1.0
        if j - i > 1:
            w[1:] = lo[i + 1:j] / c[i:j - 1] - 1.0
        out[i:j] = s * w   # las operaciones no se solapan (24 h dentro de una semana)
    return pd.Series(out, index=price_df.index)


def hard_limit_report_intrabar(price_df, trades, hard_limit, sizing="fraction"):
    """
    Caida maxima del equity contra el hard limit midiendo tambien el minimo intravela (long: low de cada vela).
    Devuelve max_dd (intravela), max_dd_close (solo cierres, como hard_limit_report), passed, headroom y trough_date.
    """
    hard_limit = float(hard_limit)
    hr = hourly_returns(price_df, trades, sizing).fillna(0.0)
    wr = hourly_worst_returns(price_df, trades, sizing)
    eq = (1.0 + hr).cumprod()
    prev_eq = eq.shift(1).fillna(1.0)
    prev_peak = np.maximum(eq.cummax().shift(1).fillna(1.0), 1.0)
    dd_close = eq / np.maximum(eq.cummax(), 1.0) - 1.0
    dd_low = prev_eq * (1.0 + wr) / prev_peak - 1.0
    dd = np.minimum(dd_close, dd_low)
    mdd = float(dd.min()) if len(dd) else 0.0
    return dict(hard_limit=hard_limit, max_dd=mdd, max_dd_close=float(dd_close.min()) if len(dd) else 0.0,
                passed=bool(mdd >= -hard_limit), headroom=float(hard_limit + mdd),
                trough_date=(dd.idxmin() if len(dd) else None))


# ------------------------------------------------------------------ reporte anual y hard limit
ANNUAL_COLS = ["year", "ret", "mdd", "n_trades", "partial", "breach"]


def annual_returns(step_returns, trades=None, hard_limit=None):
    """
    Tabla anual a partir de retornos por paso (hourly_returns o daily_returns). Reutilizable en cualquier
    notebook del repo: no depende del edge. Columnas: year, ret (retorno del ano), mdd (caida maxima dentro
    del ano, partiendo del capital a 1 de enero), n_trades (por ano de entrada), partial (ano con menos de
    358 dias de datos) y breach (mdd peor que -hard_limit; False si hard_limit es None).
    """
    r = pd.Series(step_returns, dtype=float)
    r = r[~r.index.duplicated(keep="first")].sort_index().fillna(0.0)
    if len(r) == 0:
        return pd.DataFrame(columns=ANNUAL_COLS)
    if trades is not None and len(trades):
        counts = pd.to_datetime(trades["entry_time"]).dt.year.value_counts()
    else:
        counts = pd.Series(dtype=int)
    rows = []
    for year, g in r.groupby(r.index.year):
        eq = (1.0 + g).cumprod()
        dd = eq / np.maximum(eq.cummax(), 1.0) - 1.0
        span = (g.index.max().normalize() - g.index.min().normalize()).days + 1
        mdd = float(dd.min())
        rows.append(dict(year=int(year), ret=float(eq.iloc[-1] - 1.0), mdd=mdd,
                         n_trades=int(counts.get(year, 0)), partial=bool(span < 358),
                         breach=bool(hard_limit is not None and mdd < -float(hard_limit))))
    return pd.DataFrame(rows, columns=ANNUAL_COLS)


def hard_limit_report(step_returns, hard_limit):
    """
    Caida maxima del equity (partiendo de 1.0) contra el hard limit. Con hourly_returns es el chequeo
    hora a hora (solo cierres; para incluir el minimo intravela usa hard_limit_report_intrabar). Devuelve
    max_dd (negativo), passed, headroom (hard_limit + max_dd), fechas del pico y del valle, cuantos pasos
    estuvieron por debajo del limite y la primera fecha en que se cruzo.
    """
    hard_limit = float(hard_limit)
    r = pd.Series(step_returns, dtype=float).fillna(0.0)
    if len(r) == 0:
        return dict(hard_limit=hard_limit, max_dd=0.0, passed=True, headroom=hard_limit, peak_date=None,
                    trough_date=None, steps_in_breach=0, first_breach=None)
    eq = (1.0 + r).cumprod()
    peak = np.maximum(eq.cummax(), 1.0)
    dd = eq / peak - 1.0
    trough = dd.idxmin()
    pre = eq.loc[:trough]
    peak_date = pre.idxmax() if pre.max() >= 1.0 else r.index[0]
    breached = dd < -hard_limit
    return dict(hard_limit=hard_limit, max_dd=float(dd.min()), passed=bool(dd.min() >= -hard_limit),
                headroom=float(hard_limit + dd.min()), peak_date=peak_date, trough_date=trough,
                steps_in_breach=int(breached.sum()), first_breach=(dd.index[breached.to_numpy()][0] if breached.any() else None))


def max_fraction_for_limit(price_df, trades, hard_limit, hi=2.0, tol=1e-4, intrabar=False):
    """Mayor fraccion fija del capital por operacion cuyo drawdown hora a hora historico respeta el hard limit.
    intrabar=True usa el minimo intravela (hard_limit_report_intrabar) en vez de solo cierres."""
    def mdd_at(s):
        if intrabar:
            return hard_limit_report_intrabar(price_df, trades, hard_limit, float(s))["max_dd"]
        return hard_limit_report(hourly_returns(price_df, trades, float(s)), hard_limit)["max_dd"]

    if len(trades) == 0 or mdd_at(hi) >= -float(hard_limit):
        return float(hi)
    lo, up = 0.0, float(hi)
    while up - lo > tol:
        mid = (lo + up) / 2.0
        if mdd_at(mid) >= -float(hard_limit):
            lo = mid
        else:
            up = mid
    return float(lo)


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