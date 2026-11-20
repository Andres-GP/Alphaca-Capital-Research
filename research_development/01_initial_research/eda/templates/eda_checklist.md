# Checklist de EDA

- [ ] Mercado, venue, tipo de instrumento, símbolo y granularidad identificados.
- [ ] Fuente primaria del broker registrada; fallback separado y justificado.
- [ ] Inicio/fin observados y cobertura contra el calendario esperado calculados.
- [ ] Zona horaria, horario de sesión, DST y rollover documentados.
- [ ] Huecos, duplicados, barras fuera de sesión y valores inválidos cuantificados.
- [ ] Ajustes corporativos/rollover y convenciones de precio descritos si aplican.
- [ ] Spreads, comisiones, swaps y slippage disponibles o marcados como faltantes.
- [ ] No se interpolaron huecos; cualquier transformación queda registrada.
- [ ] Gráficos conservan unidades, etiquetas y fechas legibles.
- [ ] EDA no se presenta como backtest ni como confirmación de edge.

## Metadatos del dataset

```yaml
dataset: "<id>"
instrument: "<symbol/venue/product>"
origin_type: "broker | dukascopy | other"
origin_name: "<provider>"
frequency: "<bar/tick interval>"
timezone: "<IANA zone or UTC>"
start: "YYYY-MM-DD"
end: "YYYY-MM-DD"
expected_observations: null
observed_observations: null
coverage_pct: null
gaps: []
expected_feed_differences: []
transformations: []
status: "unverified"
```
