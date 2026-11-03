"""
convert_axi_h1.py · Alphaca Capital
Convierte el export H1 de MT5 (hora del servidor Axi) a UTC para monday_effect_engine,
RECORTA el tramo inicial que no es horario (velas diarias) y imprime un resumen corto.

Uso:
    python convert_axi_h1.py BTC-JPY_H1.csv btcjpy_h1_utc.csv

Regla de hora (igual que el EA): servidor = UTC+3 en horario de verano de EE. UU., UTC+2 el resto.
Verano EE. UU.: 2.o domingo de marzo 07:00 UTC -> 1.er domingo de noviembre 06:00 UTC.
"""
import sys
import pandas as pd

src, dst = sys.argv[1], sys.argv[2]
H1 = pd.Timedelta(hours=1)

raw = pd.read_csv(src, sep=None, engine="python")
raw.columns = [str(c).strip().strip("<>").lower().replace(" ", "_") for c in raw.columns]

if "date" in raw.columns and "time" in raw.columns:
    t = pd.to_datetime(raw["date"].astype(str) + " " + raw["time"].astype(str))
else:
    tcol = next(c for c in ("datetime", "time", "date", "timestamp") if c in raw.columns)
    t = pd.to_datetime(raw[tcol])

vcol = next((c for c in ("tickvol", "tick_volume", "volume", "vol") if c in raw.columns), None)
df = pd.DataFrame({"server_time": t, "open": raw["open"], "high": raw["high"],
                   "low": raw["low"], "close": raw["close"]})
if vcol:
    df["volume"] = raw[vcol]
df = df.sort_values("server_time").drop_duplicates("server_time").reset_index(drop=True)


def nth_sunday(y, m, n):
    d = pd.Timestamp(y, m, 1)
    return d + pd.Timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))


st = df["server_time"]
approx_utc = st - pd.Timedelta(hours=2)
summer = pd.Series(False, index=df.index)
for y in sorted(set(approx_utc.dt.year)):
    ini = nth_sunday(y, 3, 2) + pd.Timedelta(hours=7)
    fin = nth_sunday(y, 11, 1) + pd.Timedelta(hours=6)
    summer |= (approx_utc >= ini) & (approx_utc < fin)
offset_h = summer.map({True: 3, False: 2})

df.insert(0, "time", st - pd.to_timedelta(offset_h, unit="h"))
full = df.drop(columns="server_time")
n_full = len(full)

# ---- recorte: primer punto desde el que >= 98 % de los siguientes 200 pasos son de exactamente 1 h
ok = (full["time"].diff() == H1).astype(float)
fwd = ok[::-1].rolling(200, min_periods=200).mean()[::-1]
good = fwd[fwd >= 0.98]
if good.empty:
    sys.exit("No encuentro un tramo horario continuo en el archivo.")
start = max(int(good.index[0]) - 1, 0)
out = full.iloc[start:].reset_index(drop=True)
out.to_csv(dst, index=False)

# ---------------- resumen para pegar en el chat
gaps = out["time"].diff().dropna()
bad = gaps[gaps != H1]
first, last = out["time"].iloc[0], out["time"].iloc[-1]
tester_start = (first + pd.Timedelta(days=200)).normalize()
tester_start += pd.Timedelta(days=(7 - tester_start.weekday()) % 7)
mon = (out["time"].dt.dayofweek == 0) & (out["time"].dt.hour == 0)
mon_after = mon & (out["time"] >= tester_start)

print("=== RESUMEN ===")
print("barras en el export:", n_full, "| descartadas (no horarias):", start, "| conservadas:", len(out))
print("primera barra horaria (UTC):", first, "| ultima (UTC):", last)
print("saltos distintos de 1 h tras el recorte:", len(bad))
for i, g in bad.sort_values(ascending=False).head(8).items():
    print("   ", out["time"].iloc[i - 1], "->", out["time"].iloc[i], f"({g})")
print("lunes 00:00 UTC en el tramo horario:", int(mon.sum()), "| desde el inicio sugerido:", int(mon_after.sum()))
print("inicio sugerido del Strategy Tester:", tester_start.date())
print("archivo escrito:", dst)