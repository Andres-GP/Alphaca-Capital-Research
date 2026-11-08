"""
patch_sanity_hold_aware.py

Makes section 6 (sanity) of notebook 01 aware of hold_days. Three checks were hard-coded for a 7-day hold and
FAIL for the configured candidate (lookback 31 / hold 11 / long_only):
  - "no overlap": with hold > 7 consecutive weekly trades overlap BY DESIGN. Now: no overlap when hold <= 7;
    when hold > 7 the check is that the number of simultaneously open trades never exceeds ceil(hold / 7).
  - "6-8 rollovers": now hold-1 .. hold+1 (identical to 6-8 when hold = 7).
  - prints updated accordingly.
With hold = 7 every check behaves exactly as before. Works on the original or on the long_only-patched notebook.

Usage: python patch_sanity_hold_aware.py 01_Weekly_Momentum_Hypothesis_Definition.ipynb [out.ipynb]
"""
from __future__ import annotations
import json, sys
from pathlib import Path

LOCATOR = "SANITY CHECKS & REPRODUCIBILITY"


def replace_once(src, old, new, what):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"[{what}] expected the text exactly once, found {n}. Nothing was written.")
    return src.replace(old, new)


def patch(src: str) -> str:
    src = replace_once(src,
        '''    if prev_end is not None and et < prev_end:
        violations.append(f"trade {idx_}: overlaps the previous trade")
    prev_end = xt
''',
        '''    if HOLD <= 7 and prev_end is not None and et < prev_end:
        violations.append(f"trade {idx_}: overlaps the previous trade")
    prev_end = xt
# hold > 7: trades overlap by design; what must hold is the maximum number of simultaneously open trades
_i0, _i1 = trades_all["i_ent"].to_numpy(int), trades_all["i_sal"].to_numpy(int)
MAX_CONC = -(-HOLD // 7)                                   # ceil(HOLD / 7)
conc = np.array([int(((_i0 <= a) & (a < _i1)).sum()) for a in _i0]) if len(_i0) else np.array([0])
if conc.max() > MAX_CONC:
    violations.append(f"up to {int(conc.max())} trades open at once, expected at most {MAX_CONC} for a {HOLD}-day hold")
''', "overlap")
    src = replace_once(src,
        '''{HOLD} d hold, no overlap ({len(trades_all)} trades).")''',
        '''{HOLD} d hold, {'no overlap' if HOLD <= 7 else f'at most {MAX_CONC} concurrent trades (max seen {int(conc.max())})'} ({len(trades_all)} trades).")''',
        "print 1")
    src = replace_once(src,
        '''(a normal week crosses 7 rollovers).")''',
        '''(a {HOLD}-day hold crosses {HOLD} rollovers).")''', "print 4")
    src = replace_once(src,
        '''check("6. Sanity", "Swap is charged: every trade crosses 6-8 rollovers", trades_all["n_rolls"].between(6, 8).all(),''',
        '''check("6. Sanity", f"Swap is charged: every trade crosses {HOLD - 1}-{HOLD + 1} rollovers", trades_all["n_rolls"].between(HOLD - 1, HOLD + 1).all(),''',
        "rollovers")
    return src


def src_of(c):
    s = c["source"]
    return "".join(s) if isinstance(s, list) else s


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else path.with_name(path.stem + "_sanity.ipynb")
    nb = json.loads(path.read_text(encoding="utf-8"))
    hits = [i for i, c in enumerate(nb["cells"]) if c["cell_type"] == "code" and LOCATOR in src_of(c)]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one sanity cell, found {len(hits)}. Nothing was written.")
    new = patch(src_of(nb["cells"][hits[0]]))
    compile(new, "<patched sanity>", "exec")
    nb["cells"][hits[0]]["source"] = new.splitlines(keepends=True)
    for c in nb["cells"]:
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"patched sanity cell #{hits[0]} -> {out}\nRestart the kernel and run all.")
