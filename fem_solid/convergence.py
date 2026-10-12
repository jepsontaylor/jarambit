#!/usr/bin/env python3
"""3-level mesh convergence of the tip submodel (PR-0.30.3). Levels refine the plate triangulation (NSUB 0/1/2: h/2 each)
and the through-thickness layers (NL 2/4/8) together, so r = 2. Each level is exported by tip_solid.py (DUMP_MESH,
DUMP_ONLY) on the host venv and solved by cross_check.py in the dolfinx container.
usage: convergence.py D1.json out_dir   -> out_dir/<design>_gci.json (vm nodal-max / nodal-avg, SF, GCI, error bars)"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gci import gci
HERE = os.path.dirname(os.path.abspath(__file__)); LEVELS = [(0, 2), (1, 4), (2, 8)]  # (NSUB, NL), coarse -> fine
IMG = os.environ.get('FEM_SOLID_IMAGE', 'ghcr.io/fenics/dolfinx/dolfinx:v0.9.0'); PY = os.environ.get('FEM_SOLID_PY', sys.executable)


def level(d1, out, nsub, nl):
    npz = os.path.join(out, f'L{nsub}{nl}.npz'); res = npz[:-4] + '.json'
    if not os.path.exists(res):
        env = {**os.environ, 'DUMP_MESH': npz, 'DUMP_ONLY': '1', 'PATCH': '2.0'}
        subprocess.check_call([PY, os.path.join(HERE, 'tip_solid.py'), d1, '30', str(nl), str(nsub), os.path.join(out, 'unused.json')], env=env, stdout=subprocess.DEVNULL)
        root = os.path.dirname(HERE); a = os.path.abspath(out)
        txt = subprocess.check_output(['docker', 'run', '--rm', '-e', 'OMP_NUM_THREADS=8', '-v', f'{root}:/r', '-v', f'{a}:/o', '-w', '/o', IMG, 'sh', '-c',
                                       f'python3 -c "import scipy" 2>/dev/null || pip install -q scipy==1.18.1 >/dev/null 2>&1; python3 /r/fem_solid/cross_check.py /o/{os.path.basename(npz)} -'], text=True)
        open(res, 'w').write(txt[txt.index('{'):]); os.remove(npz)
    return json.load(open(res))


def main(d1, out):
    os.makedirs(out, exist_ok=True); L = [level(d1, out, *lv) for lv in LEVELS]
    rep = dict(design=os.path.basename(d1).replace('_D1.json', ''), levels=[dict(NSUB=a, NL=b, **x) for (a, b), x in zip(LEVELS, L)])
    for k in ('vm_nodal_max_MPa', 'vm_nodal_avg_MPa'):
        f3, f2, f1 = (x[k] for x in L); g = gci(f1, f2, f3, 2.0); rep[k] = dict(fine=f1, **g, band_MPa=f1 * g['gci_fine'])
    s = L[-1]['sallow_MPa']; m = rep['vm_nodal_max_MPa']
    rep['SF_nodal_max'] = dict(fine=round(s / m['fine'], 4), lo=round(s / (m['fine'] * (1 + m['gci_fine'])), 4), hi=round(s / (m['fine'] * (1 - m['gci_fine'])), 4))
    json.dump(rep, open(os.path.join(out, rep['design'] + '_gci.json'), 'w'), indent=1); print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:3])
