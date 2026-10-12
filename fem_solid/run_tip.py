#!/usr/bin/env python3
"""Run the solid tip submodel and write a run manifest next to the result (PR-0.30.1).
usage: run_tip.py D1.json OUT.json [R_CUT=30] [NLAYER=4] [NSUB=1] [PATCH=2.0]
Needs <design>_grind_law.json beside D1.json. Writes OUT.json (from tip_solid.py) and OUT.json.manifest.json:
sha256 of the inputs and the script, library versions, parameters, n_dof, n_tet, wall time, SF values."""
import hashlib, json, os, platform, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def versions():
    out = {'python': platform.python_version()}
    for mod in ('skfem', 'pyamg', 'numpy', 'scipy'):
        try: out[mod] = __import__(mod).__version__
        except Exception as e: out[mod] = f'unavailable: {e.__class__.__name__}'
    return out

def main(a):
    if len(a) < 2: print(__doc__, file=sys.stderr); return 2
    d1, out = a[0], a[1]; rc, nl, nsub, patch = (a[2:3] or ['30'])[0], (a[3:4] or ['4'])[0], (a[4:5] or ['1'])[0], (a[5:6] or ['2.0'])[0]
    gl = d1.replace('_D1.json', '_grind_law.json'); script = os.path.join(HERE, 'tip_solid.py')
    for need in (d1, gl):  # fail before solving, with a clear message (PR-0.30.1b)
        if not d1.endswith('_D1.json') or not os.path.isfile(need):
            print(f'run_tip: missing input {need!r} (need <design>_D1.json from crescent-d1 D1_PLATES=1 and <design>_grind_law.json beside it)', file=sys.stderr); return 2
    t0 = time.time()
    rc_ = subprocess.call([sys.executable, script, d1, rc, nl, nsub, out], env={**os.environ, 'PATCH': patch})
    wall = time.time() - t0
    if rc_ != 0: print(f'tip_solid failed rc={rc_}', file=sys.stderr); return rc_
    s = json.load(open(out))['solid']
    man = {'schema': 1, 'script_sha256': sha(script), 'inputs': {os.path.basename(d1): sha(d1), os.path.basename(gl): sha(gl)},
           'params': {'R_CUT': float(rc), 'NLAYER': int(nl), 'NSUB': int(nsub), 'PATCH_mm': float(patch), 'T_Nmm': 1820.0},
           'versions': versions(), 'host': platform.node(), 'n_dof': s['n_dof'], 'n_tet': s['n_tet'],
           'wall_s_total': round(wall, 1), 'wall_s_solver': s.get('wall_s'),
           'SF_solid_nodal_max': s['SF_solid_nodal_max'], 'SF_solid_nodal_avg': s['SF_solid_nodal_avg'], 'SF_solid_elem_mean': s['SF_solid_elem_mean']}
    json.dump(man, open(out + '.manifest.json', 'w'), indent=1, sort_keys=True)
    print(json.dumps({k: man[k] for k in ('n_dof', 'wall_s_total', 'SF_solid_nodal_max')}))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
