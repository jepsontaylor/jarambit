"""Science-shot asset: real C.10a rc4 solver mesh + von Mises fields -> render-frame surface (no bpy).

Inputs are the solver's own artefacts (copied verbatim, hashes recorded): gmsh 2.2 tet mesh and the per-tet
von Mises arrays saved by the solve. Each result file stores tet centroids; they are checked against the
mesh (max |dc| must be < 1e-3 mm) so values cannot be attached to the wrong elements.
Loads are scaled linearly (static linear-elastic solves) to the sourced case loads exactly as the analysis
did (scale factors read from the result JSONs); SF = Sy / vM with Sy read from the design manifest (spec of record).
The CAD->render pose is the ingest bundle's pose (same STEP frame), so the FEM surface lands on the render
mesh (render->FEM node distance p99 0.40 mm, max 0.54 mm on rc4 = tet size).
python3 fem_asset.py FEMDIR BUNDLE_JSON DESIGN_MANIFEST.json OUT.npz  (every case, file, scale key and Sy from the manifest)"""
import hashlib, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_msh import read_msh22

def sha16(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]


def fail(msg):
    raise SystemExit(f'fem_asset: FAIL: {msg}')


def main():
    fem, bundle_p, man_p, out = sys.argv[1:5]
    man = json.load(open(man_p)); SY = float(man['Sy_MPa'])
    mesh_p = os.path.join(fem, man['fem']['mesh']['file'])
    if hashlib.sha256(open(mesh_p, 'rb').read()).hexdigest() != man['fem']['mesh']['sha256']: fail(f'{mesh_p} sha != manifest')
    P, T = read_msh22(mesh_p)
    cen = P[T].mean(1)
    b = json.load(open(bundle_p)); R = np.array(b['pose']['R']); t = np.array(b['pose']['t'])
    if not b['source']['sha256'] == man['step']['sha256']: fail('render bundle STEP sha != manifest STEP sha')
    loc = np.array([[1, 2, 3], [0, 3, 2], [0, 1, 3], [0, 2, 1]])
    Fall = T[:, loc].reshape(-1, 3); owner = np.repeat(np.arange(len(T)), 4)
    key = np.sort(Fall, 1); _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    bnd = cnt[inv.ravel()] == 1
    Fb, own = Fall[bnd], owner[bnd]
    p0 = P[Fb[:, 0]]; n = np.cross(P[Fb[:, 1]] - p0, P[Fb[:, 2]] - p0)
    flip = (n * (p0 - cen[own])).sum(1) < 0; Fb[flip] = Fb[flip][:, ::-1]
    used = np.unique(Fb); remap = -np.ones(len(P), np.int64); remap[used] = np.arange(len(used))
    Vs = (P[used] * 1e-3) @ R.T + t; Fs = remap[Fb]
    rec = {'schema': 'jarambit.render.pro.fem_asset.v2', 'label': man['label'], 'Sy_MPa': SY, 'manifest_sha256': man['manifest_sha256'],
           'mesh': {'file': man['fem']['mesh']['file'], 'sha16': man['fem']['mesh']['sha256'][:16], 'n_nodes': int(len(P)),
                    'n_tet': int(len(T)), 'surface_tris': int(len(Fs)), 'surface_nodes': int(len(Vs))},
           'pose': 'bundle.json pose (CAD STEP frame -> render)', 'cases': {}}
    arrays = {'V': Vs.astype(np.float32), 'F': Fs.astype(np.int32)}
    for shot in man['science']:
        cid, fc = shot['gate'], shot['fem_case']
        for k, f in shot['fem'].items():
            if hashlib.sha256(open(os.path.join(fem, f['file']), 'rb').read()).hexdigest() != f['sha256']: fail(f'{f["file"]} sha != manifest')
        z = np.load(os.path.join(fem, fc['npz'])); j = json.load(open(os.path.join(fem, fc['scale_json'])))
        if fc.get('mesh') and fc['mesh'] != man['fem']['mesh']['file']:
            # solved on its own mesh: check the result against THAT mesh, then carry each display face's value from the
            # nearest case-mesh tet centroid (same CAD frame); the transfer distance is recorded
            from scipy.spatial import cKDTree
            P2, T2 = read_msh22(os.path.join(fem, fc['mesh'])); cen2 = P2[T2].mean(1)
            dc = float(np.abs(z['c'].T - cen2).max())
            if dc >= 1e-3: fail(f'{cid}: result centroids do not match case mesh {fc["mesh"]} ({dc} mm)')
            fcen = P[Fb].mean(1); dist, nn = cKDTree(cen2).query(fcen)
            s_ = j
            for k in fc['scale_key']: s_ = s_[k]
            vm2 = z[fc['key']].astype(np.float64) * float(s_)
            arrays['vm_' + cid] = vm2[nn].astype(np.float32)
            i = int(np.argmax(vm2))
            rec['cases'][cid] = {'load_scale': float(s_), 'centroid_match_mm': dc, 'case_mesh': fc['mesh'],
                                 'transfer_nn_mm': {'p50': round(float(np.median(dist)), 3), 'p99': round(float(np.percentile(dist, 99)), 3)},
                                 'field_vm_max_MPa': round(float(vm2.max()), 1), 'field_SF_global': round(SY / float(vm2.max()), 3),
                                 'peak_cad_mm': [round(float(x), 2) for x in cen2[i]], 'result_sha16': shot['fem']['result']['sha256'][:16]}
            continue
        dc = float(np.abs(z['c'].T - cen).max())
        if dc >= 1e-3: fail(f'{cid}: result centroids do not match mesh ({dc} mm)')
        s = j
        for k in fc['scale_key']:
            if not isinstance(s, dict) or k not in s: fail(f'{cid}: scale key {fc["scale_key"]} missing in {fc["scale_json"]}')
            s = s[k]
        s = float(s); vm = z[fc['key']].astype(np.float64) * s
        arrays['vm_' + cid] = vm[own].astype(np.float32)
        i = int(np.argmax(vm))
        rec['cases'][cid] = {'load_scale': s, 'centroid_match_mm': dc, 'field_vm_max_MPa': round(float(vm.max()), 1),
                             'field_SF_global': round(SY / float(vm.max()), 3), 'peak_cad_mm': [round(float(x), 2) for x in cen[i]],
                             'result_sha16': shot['fem']['result']['sha256'][:16]}
    np.savez_compressed(out, **arrays)
    json.dump(rec, open(out.replace('.npz', '.json'), 'w'), indent=1)
    print(json.dumps(rec['cases'], indent=1))


if __name__ == '__main__':
    main()
