"""Edge-sharpness QA from the render mesh (any CAD). A 'land' triangle is a near-vertical wall triangle
(|n.y|<0.3, blade plane XZ) none of whose vertices touches a flat broad face (|n.y|>0.98), i.e. it
sits between two ground bevels (cutting edge / tip) rather than on a spine/ring wall. Its Y span is the
local edge width. FAIL if the p99 land width exceeds the limit (default 0.20 mm)."""
import numpy as np


def face_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    return n / (np.linalg.norm(n, axis=1, keepdims=True) + 1e-30)


def edge_width(V, F, region_id=None, labels=None, limit_mm=0.20):
    n = face_normals(V, F); ay = np.abs(n[:, 1])
    flat_v = np.zeros(len(V), bool); flat_v[F[ay > 0.98].ravel()] = True
    bev_v = np.zeros(len(V), bool); bev_v[F[(ay > 0.3) & (ay <= 0.98)].ravel()] = True
    wall = ay < 0.3
    land = wall & ~flat_v[F].any(1) & bev_v[F].any(1)
    if region_id is not None:   # prefer the region tagger: walls touching cutting-edge regions
        cut = np.isin(region_id, [int(k) for k, v in labels.items() if v in ('bevel', 'edge_apex', 'serration')])
        cv = np.zeros(len(V), bool); cv[F[cut & ~wall].ravel()] = True
        land = (ay < 0.3) & cv[F].all(1)
    span = np.ptp(V[F][:, :, 1], axis=1) * 1e3
    w = span[land]
    mx = float(w.max()) if len(w) else 0.0
    loc = V[F[land][np.argmax(w)]].mean(0).tolist() if len(w) else None
    return {'limit_mm': limit_mm, 'land_tris': int(land.sum()), 'max_mm': round(mx, 4),
            'p95_mm': round(float(np.percentile(w, 95)), 4) if len(w) else 0.0,
            'p99_mm': round(float(np.percentile(w, 99)), 4) if len(w) else 0.0,
            'worst_xyz_m': loc, 'criterion': 'p99 land width <= limit (max reported; isolated bevel-run-out tris)',
            'pass': bool(len(w) and np.percentile(w, 99) <= limit_mm)}


if __name__ == '__main__':
    import sys, json
    for p in sys.argv[1:]:
        import os
        d = np.load(p); lab = json.load(open(os.path.join(os.path.dirname(p), 'regions.json')))['labels']
        print(p, json.dumps(edge_width(d['V'], d['F'], d['region_id'], lab)))
