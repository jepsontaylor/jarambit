#!/usr/bin/env python3
"""PR-0.28.3: every emitted JSON must parse strictly: unique keys in every object, no NaN/Infinity.
Usage: check_json_strict.py <file-or-dir> [...]  (directories: every *.json inside, non-recursive)."""
import json, pathlib, sys

def _pairs(pairs):
    seen = set()
    for k, _ in pairs:
        if k in seen: raise ValueError(f"duplicate key {k!r}")
        seen.add(k)
    return dict(pairs)

def _const(c): raise ValueError(f"non-finite literal {c}")

def check(path):
    json.loads(pathlib.Path(path).read_text(), object_pairs_hook=_pairs, parse_constant=_const)

files = []
for a in sys.argv[1:]:
    p = pathlib.Path(a); files += sorted(p.glob("*.json")) if p.is_dir() else [p]
if not files: sys.exit("check_json_strict: no JSON files given/found")
bad = 0
for f in files:
    try: check(f)
    except Exception as e: bad += 1; print(f"FAIL {f}: {e}")
print(f"check_json_strict: {len(files)} file(s), {bad} failure(s)")
sys.exit(1 if bad else 0)
