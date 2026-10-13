"""Science-shot asset: real C.10a rc4 solver mesh + von Mises fields -> render-frame surface (no bpy).

Inputs are the solver's own artefacts (copied verbatim, hashes recorded): gmsh 2.2 tet mesh and the per-tet
von Mises arrays saved by the solve. Each result file stores tet centroids; they are checked against the
mesh (max |dc| must be < 1e-3 mm) so values cannot be attached to the wrong elements.
Loads are scaled linearly (static linear-elastic solves) to the sourced case loads exactly as the analysis
did (scale factors read from the result JSONs); SF = Sy / vM with Sy = 828 MPa (spec of record).
The CAD->render pose is the ingest bundle's pose (same STEP frame), so the FEM surface lands on the render
mesh (render->FEM node distance p99 0.40 mm, max 0.54 mm on rc4 = tet size).
python3 fem_asset.py FEMDIR BUNDLE_JSON OUT.npz"""
import hashlib, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_msh import read_msh22

SY = 828.0
CASES = {   # board SF = converged gate value of record (W79 STATUS_C10A_RC / W82 board); field = global g2h solve
    'V3': {'title': 'V3 spine strike 3427 N', 'npz': 'b1_c10ar_g2h_vm.npz', 'key': 'vm', 'json': 'b1_c10ar_g2h_zones.json',
           'scale_from': ('r_800N', None), 'board_SF': 1.584, 'gate': 1.575,
           'board_note': 'converged ladder 1.652/1.588/1.584 outside support (r0.2)'},
    'V6': {'title': 'V6 pry 13.7 N·m', 'npz': 'c10ar_g2h_plate_grip_sig.npz', 'key': 'vm_a1_40N', 'json': 'w79_results_c10ar_g2h.json',
           'board_SF': 1.578, 'gate': 1.575, 'board_note': 'jimping submodel a1 1.578 (governor)'},
    'V7': {'title': 'V1/V7 twist 16.2 N·m', 'npz': 'glob_c10ar_g2hsoft_vm.npz', 'key': 'vm', 'json': 'glob_c10ar_g2hsoft_zones.json',
           'board_SF': 1.616, 'gate': 1.575, 'board_note': 'V7 handle-nose 1.616; V1 tip strip 1.768'},
}


def sha16(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]


def scale_for(case, d):
    if case == 'V3':
        return float(d['scale_to_sourced'])                       # 3427/800
    if case == 'V6':
        return float(d['V6_pry']['cases']['a1_40N']['13.7Nm']['scale'])
    if case == 'V7':
        return float(d['scale'])                                  # 6 -> 16.2 N·m


def main():
    fem, bundle_p, out = sys.argv[1:4]
    P, T = read_msh22(os.path.join(fem, 'c10ar_g2h.msh'))
    cen = P[T].mean(1)
    b = json.load(open(bundle_p)); R = np.array(b['pose']['R']); t = np.array(b['pose']['t'])
    # boundary faces (each belongs to exactly one tet) with outward orientation
    loc = np.array([[1, 2, 3], [0, 3, 2], [0, 1, 3], [0, 2, 1]])
    Fall = T[:, loc].reshape(-1, 3); owner = np.repeat(np.arange(len(T)), 4)
    key = np.sort(Fall, 1); _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    bnd = cnt[inv.ravel()] == 1
    Fb, own = Fall[bnd], owner[bnd]
    # orient outward: normal should point away from the owning tet centroid
    p0 = P[Fb[:, 0]]; n = np.cross(P[Fb[:, 1]] - p0, P[Fb[:, 2]] - p0)
    flip = (n * (p0 - cen[own])).sum(1) < 0; Fb[flip] = Fb[flip][:, ::-1]
    used = np.unique(Fb); remap = -np.ones(len(P), np.int64); remap[used] = np.arange(len(used))
    Vs = (P[used] * 1e-3) @ R.T + t; Fs = remap[Fb]
    rec = {'schema': 'jarambit.render.pro.fem_asset.v1', 'label': 'Rev C.10a rc4', 'Sy_MPa': SY,
           'mesh': {'file': 'c10ar_g2h.msh', 'sha16': sha16(os.path.join(fem, 'c10ar_g2h.msh')), 'n_nodes': int(len(P)),
                    'n_tet': int(len(T)), 'surface_tris': int(len(Fs)), 'surface_nodes': int(len(Vs))},
           'pose': 'bundle.json pose (CAD STEP frame -> render)', 'cases': {}}
    arrays = {'V': Vs.astype(np.float32), 'F': Fs.astype(np.int32)}
    for cid, c in CASES.items():
        z = np.load(os.path.join(fem, c['npz'])); j = json.load(open(os.path.join(fem, c['json'])))
        dc = float(np.abs(z['c'].T - cen).max())
        assert dc < 1e-3, f'{cid}: result centroids do not match mesh ({dc} mm)'
        s = scale_for(cid, j); vm = z[c['key']].astype(np.float64) * s
        arrays['vm_' + cid] = vm[own].astype(np.float32)          # element value on its boundary face
        i = int(np.argmax(vm))
        rec['cases'][cid] = {**{k: v for k, v in c.items() if k not in ('scale_from',)}, 'result_sha16': sha16(os.path.join(fem, c['npz'])),
                             'centroid_match_mm': dc, 'load_scale': s, 'vm_max_MPa': round(float(vm.max()), 1),
                             'SF_global_field': round(SY / float(vm.max()), 3), 'peak_cad_mm': [round(float(x), 2) for x in cen[i]],
                             'surface_vm_max_MPa': round(float(vm[own].max()), 1),
                             'verdict': 'PASS' if c['board_SF'] >= c['gate'] else 'FAIL'}
    np.savez_compressed(out, **arrays)
    json.dump(rec, open(out.replace('.npz', '.json'), 'w'), indent=1)
    print(json.dumps(rec['cases'], indent=1)[:2500])


if __name__ == '__main__':
    main()
