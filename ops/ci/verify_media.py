#!/usr/bin/env python3
"""Verify docs/media/*.manifest.json (ops/render): output exists with the recorded sha256, size within budget, every input
sha256 still matches (regenerate with ops/render/turntable.py when an input changes). Exit 1 on any error."""
import glob, hashlib, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAX_BYTES = 15 * 1024 * 1024
errs = []
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
mans = sorted(glob.glob(os.path.join(ROOT, 'docs/media/**/*.manifest.json'), recursive=True))
for m in mans:
    d = json.load(open(m)); out = os.path.join(ROOT, d['output'])
    if not os.path.exists(out): errs.append(f'{m}: missing {d["output"]}'); continue
    if sha(out) != d['output_sha256']: errs.append(f'{d["output"]}: sha256 != manifest')
    if os.path.getsize(out) > MAX_BYTES: errs.append(f'{d["output"]}: {os.path.getsize(out)} bytes > budget {MAX_BYTES}')
    for rel, h in d['inputs'].items():
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p) or sha(p) != h: errs.append(f'{d["output"]}: input {rel} changed or missing (regenerate)')
for e in errs: print('ERROR:', e)
print(f'verify_media: {len(mans)} manifest(s), {len(errs)} error(s)')
sys.exit(1 if errs or not mans else 0)
