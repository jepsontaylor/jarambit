#!/usr/bin/env python3
"""PR-0.29.4: every `*.manifest.json` under the given roots (default: docs/) must match the repository:
the figure and every input exist and their sha256 equal the manifest; the generating script exists.
Swapping an STL / plate JSON / PNG without regenerating the manifest fails. Also: a figure with
`require_manifest` listed in ops/ci/figures_required.txt must have a manifest.
usage: verify_figures.py [root ...]"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'ops', 'wave_figures'))
from figlib import sha256_file  # noqa: E402


def check_manifest(path, base=ROOT):
    errs = []
    m = json.load(open(path))
    for k in ('figure', 'figure_sha256', 'inputs', 'script'):
        if k not in m: errs.append(f'{path}: missing key {k}')
    if errs: return errs
    def chk(relp, want, what):
        p = os.path.join(base, relp)
        if not os.path.exists(p): errs.append(f'{path}: {what} {relp} missing'); return
        got = sha256_file(p)
        if got != want: errs.append(f'{path}: {what} {relp} sha256 {got[:12]} != manifest {want[:12]} (regenerate the figure + manifest)')
    chk(m['figure'], m['figure_sha256'], 'figure')
    for relp, sha in sorted(m['inputs'].items()): chk(relp, sha, 'input')
    if not os.path.exists(os.path.join(base, m['script'])): errs.append(f"{path}: script {m['script']} missing")
    if not m['inputs']: errs.append(f'{path}: no inputs recorded')
    return errs


def main(roots, base=ROOT):
    errs, n = [], 0
    for r in roots:
        for d, _, fs in os.walk(os.path.join(base, r)):
            for f in sorted(fs):
                if f.endswith('.manifest.json'):
                    n += 1; errs += check_manifest(os.path.join(d, f), base)
    req = os.path.join(base, 'ops', 'ci', 'figures_required.txt')
    if os.path.exists(req):
        for line in open(req):
            line = line.split('#')[0].strip()
            if line and not os.path.exists(os.path.join(base, line + '.manifest.json')): errs.append(f'{line}: required figure has no manifest')
    for e in errs: print('ERROR:', e)
    print(f'verify_figures: {n} manifest(s), {len(errs)} error(s)')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['docs']))
