#!/usr/bin/env python3
"""Version consistency check (jarambit). Exit 1 on mismatch.
- docs/VERSION must be semver (X.Y.Z or X.Y.Z-pre).
- docs/WHITEPAPER.md header must contain 'Version <VERSION>'.
- On a tag ref vX.Y.Z (GITHUB_REF=refs/tags/v...): VERSION == tag and no pre-release suffix.
- On release/* branches: VERSION must not be -dev.
Other refs (main, PRs, exec/*) only check the first two, so d1-gates is never affected."""
import os, re, sys
root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
v = open(os.path.join(root, 'docs', 'VERSION')).read().strip()
errs = []
if not re.fullmatch(r'\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?', v):
    errs.append(f'docs/VERSION {v!r} is not semver')
head = open(os.path.join(root, 'docs', 'WHITEPAPER.md')).read()[:2000]
if f'Version {v}' not in head:
    errs.append(f'WHITEPAPER header lacks "Version {v}"')
ref = os.environ.get('GITHUB_REF', '')
if ref.startswith('refs/tags/v'):
    tag = ref[len('refs/tags/v'):]
    if re.fullmatch(r'\d+\.\d+\.\d+', tag):  # only strict semver tags (legacy v0.1.0-g3neckrail is exempt)
        if tag != v: errs.append(f'tag v{tag} != docs/VERSION {v}')
if ref.startswith('refs/heads/release/') and '-dev' in v:
    errs.append(f'release branch with -dev VERSION {v}')
print(f'VERSION={v} ref={ref or "(local)"}')
for e in errs: print('ERROR:', e)
sys.exit(1 if errs else 0)
