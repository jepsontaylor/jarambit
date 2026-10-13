"""TEMPORARY STL -> mesh bundle (+ regions) writer for the scene tests and lookdev only.

The real producer is Codex's ingest.py/regions.py (render/codex-cad-mesh). This stand-in writes the
frozen INTERFACES schema (jarambit.render.mesh.v1 / jarambit.render.regions.v1) so the Blender worker
can be exercised before that branch lands. Positions are never moved (weld keeps the first
occurrence bit-for-bit, then one rigid pose transform). Region labels are a crude normal/height
heuristic, method="heuristic_tmp".

usage: python3 _stl_bundle.py STL OUT_DIR [--pose upright|flat] [--units mm]
"""
import argparse, hashlib, json, os, re, struct, sys

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

LABELS = {0: 'body', 1: 'bevel', 2: 'edge_apex', 3: 'serration', 4: 'ring', 5: 'pad', 6: 'spine'}


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read_stl(p):
    raw = open(p, 'rb').read()
    if len(raw) >= 84:
        n = struct.unpack('<I', raw[80:84])[0]
        if 84 + 50 * n == len(raw):
            a = np.frombuffer(raw, np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]), n, 84)
            tri = a['v'].astype(np.float64)
            if not np.isfinite(tri).all():
                raise ValueError('non-finite vertex')
            return tri
    txt = raw.decode('ascii', 'strict')
    tri = np.array(re.findall(r'vertex\s+(\S+)\s+(\S+)\s+(\S+)', txt), np.float64)
    if len(tri) == 0 or len(tri) % 3 or not np.isfinite(tri).all():
        raise ValueError('malformed/truncated ascii stl')
    return tri.reshape(-1, 3, 3)


def weld(tri):
    P = tri.reshape(-1, 3)
    tol = 1e-6 * float(np.linalg.norm(np.ptp(P, 0)))
    key = np.round(P / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    V = P[first]
    F = inv.reshape(-1, 3).astype(np.int32)
    keep = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    return V, F[keep]


def face_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    a = np.linalg.norm(n, axis=1)
    return n / np.maximum(a, 1e-300)[:, None], 0.5 * a


def split_normals(V, F, fn, area, crease_deg=30.0):
    """Per-corner normals: area-weighted average of incident faces within crease_deg of the corner face."""
    m = len(F)
    cos_c = np.cos(np.radians(crease_deg))
    corner_v = F.reshape(-1)
    corner_f = np.repeat(np.arange(m), 3)
    order = np.argsort(corner_v, kind='stable')
    cv, cf = corner_v[order], corner_f[order]
    starts = np.flatnonzero(np.r_[True, cv[1:] != cv[:-1]])
    ends = np.r_[starts[1:], len(cv)]
    N = np.zeros((m * 3, 3))
    for s, e in zip(starts, ends):
        faces = cf[s:e]
        nf = fn[faces]
        w = (nf @ nf.T >= cos_c) * area[faces][None, :]
        acc = w @ nf
        acc /= np.maximum(np.linalg.norm(acc, axis=1), 1e-300)[:, None]
        N[order[s:e]] = acc
    return N.reshape(m, 3, 3).astype(np.float32)


def grind_band(cen_src_mm, grind_law):
    """True where a centroid (source plan mm) lies inside a ground band of grind_law.json (+0.4 mm)."""
    from scipy.spatial import cKDTree
    g = json.load(open(grind_law))
    inside = np.zeros(len(cen_src_mm), bool)
    for e in g['edges']:
        s = np.asarray(e['samples'], float)
        d, i = cKDTree(s[:, :2]).query(cen_src_mm[:, :2])
        inside |= d <= s[i, 4] + 0.4
    return inside


def regions(V, F, fn, area, plane_n, band=None):
    m = len(F)
    c = np.abs(fn @ plane_n)
    tilt = np.degrees(np.arccos(np.clip(c, 0, 1)))
    rid = np.zeros(m, np.uint8)
    tilted = (tilt >= 12) & (tilt < 75)
    rid[tilted if band is None else tilted & band] = 1
    wall = tilt >= 75
    # edge adjacency
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    ef = np.tile(np.arange(m), 3)
    e.sort(1)
    key = e[:, 0].astype(np.int64) * (len(V) + 1) + e[:, 1]
    o = np.argsort(key, kind='stable'); ks = key[o]
    same = np.flatnonzero(ks[1:] == ks[:-1])
    a, b = ef[o][same], ef[o][same + 1]
    # local wall height along the blade normal
    h = np.ptp(V[F] @ plane_n, axis=1)
    near_bevel = np.zeros(m, bool)
    for x, y in ((a, b), (b, a)):
        near_bevel[x[rid[y] == 1]] = True
    apex = wall & (h < 1.6e-3) & near_bevel
    if band is not None:
        apex &= band
    # grow apex one ring along thin walls so the land strip is continuous
    for _ in range(2):
        g = np.zeros(m, bool)
        for x, y in ((a, b), (b, a)):
            g[x[apex[y]]] = True
        apex |= g & wall & (h < 1.6e-3) & (band if band is not None else True)
    rid[apex] = 2
    # wall components: ring bore = full-height loop whose normals point inward
    ww = wall & ~apex
    sel = ww[a] & ww[b]
    G = coo_matrix((np.ones(sel.sum()), (a[sel], b[sel])), shape=(m, m))
    ncomp, lab = connected_components(G, directed=False)
    cen = V[F].mean(1)
    rid[ww] = 6
    for k in np.unique(lab[ww]):
        idx = np.flatnonzero((lab == k) & ww)
        if len(idx) < 8:
            continue
        cc = np.average(cen[idx], axis=0, weights=area[idx])
        r = cen[idx] - cc
        r -= np.outer(r @ plane_n, plane_n)
        inward = np.average(np.sign(np.einsum('ij,ij->i', fn[idx], r)), weights=area[idx]) < -0.6
        rad = np.median(np.linalg.norm(r, axis=1))
        if inward and np.median(h[idx]) > 2e-3 and 4e-3 < rad < 40e-3:
            rid[idx] = 4
    return rid


def tangents(V, F, fn, rid, plane_n):
    g = fn - np.outer(fn @ plane_n, plane_n)  # in-plane tilt direction (toward the edge on a bevel)
    t = g - (np.einsum('ij,ij->i', g, fn))[:, None] * fn
    circ = np.cross(plane_n[None, :], fn)
    use_circ = np.isin(rid, [4, 6]) | (np.linalg.norm(t, axis=1) < 1e-6)
    t[use_circ] = circ[use_circ]
    bad = np.linalg.norm(t, axis=1) < 1e-6
    x = np.array([1.0, 0, 0])
    t[bad] = x - (fn[bad] @ x)[:, None] * fn[bad]
    return (t / np.maximum(np.linalg.norm(t, axis=1), 1e-300)[:, None]).astype(np.float32)


def build(stl, out, pose='upright', units='mm', grind_law=None):
    os.makedirs(out, exist_ok=True)
    tri = read_stl(stl)
    scale = {'mm': 1e-3, 'm': 1.0, 'in': 0.0254}[units]
    V, F = weld(tri)
    V = V * scale
    c = (V.min(0) + V.max(0)) / 2
    w, vec = np.linalg.eigh(np.cov((V - V.mean(0)).T))
    nrm = vec[:, 0]
    if pose == 'upright':  # blade plane normal -> -Y (faces the az=0 camera), long axis X, Z up
        long_ax = vec[:, 2]
        # keep the source senses deterministic (ring left, source +Z face toward the camera)
        long_ax = long_ax * (1 if long_ax[np.argmax(np.abs(long_ax))] > 0 else -1)
        nrm = nrm * (1 if nrm[np.argmax(np.abs(nrm))] > 0 else -1)
        R = np.stack([long_ax, -nrm, np.cross(long_ax, -nrm)])
    else:
        R = np.eye(3)
    t = -(R @ c)
    V = V @ R.T + t
    fn, area = face_normals(V, F)
    plane_n = np.array([0.0, -1.0, 0.0]) if pose == 'upright' else np.array([0.0, 0.0, 1.0])
    Nc = split_normals(V, F, fn, area, 30.0)
    band = None
    if grind_law:
        band = grind_band(((V[F].mean(1) - t) @ R) * 1e3, grind_law)  # source frame, mm
    rid = regions(V, F, fn, area, plane_n, band)
    tan = tangents(V, F, fn, rid, plane_n)
    npz = os.path.join(out, 'mesh.npz')
    np.savez(npz, V=V, F=F, N_corner=Nc, face_id=np.zeros(len(F), np.int32), region_id=rid, tangent=tan,
             uv=np.zeros((len(F), 3, 2), np.float32))
    bundle = {'schema': 'jarambit.render.mesh.v1',
              'source': {'path': os.path.abspath(stl), 'format': 'stl', 'sha256': sha256(stl), 'units': units},
              'unit_scale_to_m': scale, 'n_vertices': int(len(V)), 'n_triangles': int(len(F)),
              'bbox_m': [V.min(0).tolist(), V.max(0).tolist()],
              'pose': {'R': R.tolist(), 't': t.tolist()}, 'normal_policy': 'split_crease30_weighted',
              'npz_sha256': sha256(npz), 'producer': 'tests/_stl_bundle.py (temporary stand-in)'}
    json.dump(bundle, open(os.path.join(out, 'bundle.json'), 'w'), indent=1)
    areas = {LABELS[k]: float(area[rid == k].sum() * 1e6) for k in LABELS}
    reg = {'schema': 'jarambit.render.regions.v1', 'labels': {str(k): v for k, v in LABELS.items()},
           'method': 'heuristic_tmp', 'params': {'flank_deg': 12, 'bevel_deg': [12, 75], 'apex_wall_h_mm': 1.6,
                                                 'grind_law': os.path.abspath(grind_law) if grind_law else None},
           'area_mm2': areas, 'labels_sha256': hashlib.sha256(rid.tobytes()).hexdigest()}
    json.dump(reg, open(os.path.join(out, 'regions.json'), 'w'), indent=1)
    return os.path.join(out, 'bundle.json'), os.path.join(out, 'regions.json')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stl'); ap.add_argument('out')
    ap.add_argument('--pose', default='upright', choices=['upright', 'flat'])
    ap.add_argument('--units', default='mm')
    ap.add_argument('--grind-law', help='*_grind_law.json: restrict bevel/edge_apex to the ground bands')
    a = ap.parse_args()
    b, r = build(a.stl, a.out, a.pose, a.units, a.grind_law)
    print(json.dumps(json.load(open(r))['area_mm2']))
