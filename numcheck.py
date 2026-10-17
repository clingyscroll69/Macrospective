"""Guardrail: every number in a verdict must appear in the evidence pack. Usage: numcheck.py evidence.json verdict.md..."""
import json, re, sys

ev = open(sys.argv[1]).read()
allowed = set()
for tok in re.findall(r"-?\d+(?:\.\d+)?", ev):
    v = float(tok)
    allowed |= {round(v, 4), round(v * 100, 2), round(abs(v), 4), round(abs(v) * 100, 2)}
allowed |= {float(i) for i in range(0, 25)}   # clock hours, section numbers, list ordinals
ok = True
for f in sys.argv[2:]:
    txt = re.sub(r"[A-Za-z_]+\d+(?:_\w+)?", "", open(f).read())   # drop ids like c0_i3, R2
    bad = sorted({t for t in re.findall(r"\d+(?:\.\d+)?", txt) if round(float(t), 4) not in allowed})
    print(("PASS " if not bad else "FAIL ") + f.split("/")[-1], bad)
    ok &= not bad
sys.exit(0 if ok else 1)
