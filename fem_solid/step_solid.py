"""Direct B-rep STEP/STL 3D tip submodel P2 tetrahedral solver for native CAD subjects (e.g. SWITCHBACK Rev C.10a).

Hashes the pinned STEP and STL assets, extracts the tip submodel within R_CUT = 30 mm of the tip from the B-rep outline
and 3D surface Z-envelope, constructs a 4-layer subdivided P2 tetrahedral mesh, solves the 1.82 N*m chord-torsion problem
with skfem + pyamg, and optionally dumps the exact submodel .npz for independent FEniCSx/dolfinx cross-checking.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
import numpy as np
import scipy.sparse as sp
from scipy.spatial import Delaunay, cKDTree


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_binary_stl_vertices(stl_path: Path) -> np.ndarray:
    raw = stl_path.read_bytes()
    n_tri = struct.unpack("<I", raw[80:84])[0]
    dt = np.dtype([("normal", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    records = np.frombuffer(raw, dtype=dt, count=n_tri, offset=84)
    return records["v"].reshape(-1, 3).astype(np.float64)


def _point_in_poly(pts: np.ndarray, poly: np.ndarray) -> np.ndarray:
    x = pts[:, 0][:, None]
    y = pts[:, 1][:, None]
    a = poly
    b = np.roll(a, -1, axis=0)
    cond = ((a[:, 1] > y) != (b[:, 1] > y)) & (
        x < (b[:, 0] - a[:, 0]) * (y - a[:, 1]) / (b[:, 1] - a[:, 1] + 1e-300) + a[:, 0]
    )
    return (cond.sum(axis=1) % 2) == 1


def _tets_of_prism(v):
    v = list(v)
    i0 = int(np.argmin(v))
    rot = {
        0: [0, 1, 2, 3, 4, 5],
        1: [1, 2, 0, 4, 5, 3],
        2: [2, 0, 1, 5, 3, 4],
        3: [3, 5, 4, 0, 2, 1],
        4: [4, 3, 5, 1, 0, 2],
        5: [5, 4, 3, 2, 1, 0],
    }[i0]
    w = [v[r] for r in rot]
    if min(w[1], w[5]) < min(w[2], w[4]):
        return [(w[0], w[1], w[2], w[5]), (w[0], w[1], w[5], w[4]), (w[0], w[4], w[5], w[3])]
    return [(w[0], w[1], w[2], w[4]), (w[0], w[4], w[2], w[5]), (w[0], w[4], w[5], w[3])]


def solve_c10a_tip(r_cut: float = 30.0, nl: int = 4, nsub: int = 1, dump_npz: str | None = None) -> dict:
    t0 = time.time()
    step_path = ROOT / "designs" / "switchback" / "C10a" / "cad" / "switchback_revC10a_ground.step"
    stl_path = ROOT / "designs" / "switchback" / "C10a" / "cad" / "switchback_revC10a_ground.stl"
    outline_path = ROOT / "designs" / "switchback" / "C10a" / "data" / "outline_c10a.json"

    step_sha = _sha256(step_path)
    stl_sha = _sha256(stl_path)
    outline_data = json.loads(outline_path.read_text(encoding="utf-8"))

    outer_raw = np.asarray(outline_data["exterior"], dtype=float)
    tipo = np.asarray(outline_data["tip"], dtype=float)
    t_joint = float(outline_data.get("T_TIP", 4.5))

    T_NMM, E, NU, SY20 = 1820.0, 113.8e3, 0.34, 828.0
    JK2 = ((t_joint - 0.1) / t_joint) ** 2 * (1.0 - 0.0011 * 80.0)
    SALLOW = SY20 * JK2

    dvec = tipo / np.linalg.norm(tipo)
    nvec = np.array([-dvec[1], dvec[0]])

    # Densify boundary segments near the tip to <= 0.45 mm spacing
    pts_list = []
    for i in range(len(outer_raw)):
        p0, p1 = outer_raw[i], outer_raw[(i + 1) % len(outer_raw)]
        if min(np.linalg.norm(p0 - tipo), np.linalg.norm(p1 - tipo)) <= (r_cut + 5.0):
            seg_len = float(np.linalg.norm(p1 - p0))
            n_seg = max(1, int(math.ceil(seg_len / 0.45)))
            for k in range(n_seg):
                pts_list.append(p0 + (k / n_seg) * (p1 - p0))
    b_dense = np.asarray(pts_list, dtype=float)
    b_pts = b_dense[np.linalg.norm(b_dense - tipo, axis=1) <= (r_cut + 2.0)]

    # Build 2D Delaunay mesh inside outer polygon within R_CUT + 2 mm of tip, then filter to R_CUT
    bbox_min = tipo - (r_cut + 2.0)
    bbox_max = tipo + (r_cut + 2.0)
    gx, gy = np.meshgrid(
        np.arange(bbox_min[0], bbox_max[0], 0.55),
        np.arange(bbox_min[1], bbox_max[1], 0.55),
    )
    grid_pts = np.c_[gx.ravel(), gy.ravel()]
    grid_pts = grid_pts[_point_in_poly(grid_pts, outer_raw)]

    # Filter interior points too close to boundary vertices
    b_tree = cKDTree(b_pts)
    keep_grid = b_tree.query(grid_pts)[0] > 0.28
    all_2d = np.vstack([b_pts, grid_pts[keep_grid]])

    tri = Delaunay(all_2d)
    tris = tri.simplices
    cen = all_2d[tris].mean(axis=1)
    v2 = all_2d[tris]
    e1 = v2[:, 1] - v2[:, 0]
    e2 = v2[:, 2] - v2[:, 0]
    area2 = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    inside_mask = _point_in_poly(cen, outer_raw) & (area2 >= 0.03)
    tris = tris[inside_mask]
    cen = cen[inside_mask]
    dc = np.linalg.norm(cen - tipo, axis=1)
    keep = dc <= r_cut
    from scipy.sparse.csgraph import connected_components
    ki = np.where(keep)[0]
    kt0 = tris[ki]
    rows_ = np.repeat(np.arange(len(ki)), 3)
    G_adj = sp.csr_matrix((np.ones(len(rows_)), (rows_, kt0.ravel())), shape=(len(ki), len(all_2d)))
    _, lab = connected_components((G_adj @ G_adj.T).tocsr(), directed=False)
    tri_tip = int(np.argmin(np.linalg.norm(cen[ki] - tipo, axis=1)))
    keep[:] = False
    keep[ki[lab == lab[tri_tip]]] = True

    dropped = np.unique(tris[~keep])
    cutmask = np.zeros(len(all_2d), dtype=bool)
    cutmask[dropped] = True

    kt = tris[keep]
    used = np.unique(kt)
    rm = -np.ones(len(all_2d), dtype=int)
    rm[used] = np.arange(len(used))
    P2d = all_2d[used]
    T2d = rm[kt]
    cut2d = cutmask[used]

    for _ in range(nsub):
        edges = {}
        newp = list(P2d)
        newcut = list(cut2d)
        NT = []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in edges:
                edges[k] = len(newp)
                newp.append((P2d[a] + P2d[b]) / 2.0)
                newcut.append(bool(cut2d[a] and cut2d[b]))
            return edges[k]

        for a, b, c in T2d:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            NT += [(a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca)]
        P2d = np.asarray(newp, dtype=float)
        T2d = np.asarray(NT, dtype=int)
        cut2d = np.asarray(newcut, dtype=bool)

    dn = np.linalg.norm(P2d - tipo, axis=1)
    cut2d &= dn > (r_cut - 4.0)

    # Interpolate local B-rep thickness directly from the upper 3D STL surface in the tip disk
    from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
    stl_v = _load_binary_stl_vertices(stl_path)
    stl_near = stl_v[(np.linalg.norm(stl_v[:, :2] - tipo, axis=1) <= (r_cut + 5.0)) & (stl_v[:, 2] >= -1e-4)]
    xy_round = np.round(stl_near[:, :2], 3)
    _, inv = np.unique(xy_round, axis=0, return_inverse=True)
    uxy = np.zeros((inv.max() + 1, 2), dtype=float)
    uz = np.zeros(inv.max() + 1, dtype=float)
    np.maximum.at(uz, inv, stl_near[:, 2])
    for idx_i in range(len(inv)):
        uxy[inv[idx_i]] = stl_near[idx_i, :2]
    lin_interp = LinearNDInterpolator(uxy, 2.0 * uz)
    near_interp = NearestNDInterpolator(uxy, 2.0 * uz)
    hh_raw = lin_interp(P2d)
    nan_mask = np.isnan(hh_raw)
    if nan_mask.any():
        hh_raw[nan_mask] = near_interp(P2d[nan_mask])
    hh = np.clip(hh_raw, 0.15, t_joint)

    N2 = len(P2d)
    pts = np.vstack([np.c_[P2d, (k / nl - 0.5) * hh] for k in range(nl + 1)])
    TT = []
    for k in range(nl):
        for a, b, c in T2d:
            TT += _tets_of_prism((a + k * N2, b + k * N2, c + k * N2, a + (k + 1) * N2, b + (k + 1) * N2, c + (k + 1) * N2))
    TT = np.asarray(TT, dtype=int)
    v = pts[TT]
    vol = np.einsum("ij,ij->i", np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), v[:, 3] - v[:, 0])
    TT[vol < 0] = TT[vol < 0][:, [0, 2, 1, 3]]

    from skfem import Basis, ElementTetP2, ElementVector, MeshTet, asm
    from skfem.helpers import eye, sym_grad, trace
    from skfem.models.elasticity import lame_parameters, linear_elasticity
    import scipy.sparse.linalg as spla

    mesh = MeshTet(pts.T.copy(), TT.T.copy())
    e = ElementVector(ElementTetP2())
    ib = Basis(mesh, e, intorder=2)
    lam, mu = lame_parameters(E, NU)
    K = asm(linear_elasticity(lam, mu), ib).tocsr()

    pv = mesh.p.T
    vert = np.arange(mesh.p.shape[1])
    PATCH = 2.0
    pat = vert[np.linalg.norm(pv[:, :2] - tipo, axis=1) <= PATCH]
    r = pv[pat, :2] - pv[pat, :2].mean(0)
    s = r @ nvec
    q = r @ dvec
    A = np.vstack([np.ones(len(pat)), s, q])
    Fz = A.T @ np.linalg.solve(A @ A.T, np.array([0.0, T_NMM, 0.0]))
    fvec = np.zeros(ib.N)
    fvec[ib.nodal_dofs[2, pat]] = Fz

    cutxy = P2d[cut2d]
    tr = cKDTree(cutxy)
    fixed_v = np.where(cut2d[np.arange(mesh.p.shape[1]) % N2])[0]
    fixdofs = set(ib.nodal_dofs[:, fixed_v].ravel().tolist())
    ed = mesh.edges
    both = np.isin(ed[0], fixed_v) & np.isin(ed[1], fixed_v)
    fixdofs |= set(ib.edge_dofs[:, np.where(both)[0]].ravel().tolist())
    fixdofs = np.array(sorted(fixdofs))
    free = np.setdiff1d(np.arange(ib.N), fixdofs)

    if dump_npz:
        np.savez_compressed(
            dump_npz,
            pts=pv,
            tets=mesh.t.T,
            fixed_v=fixed_v,
            edges_fixed=ed[:, both].T,
            pat=pat,
            Fz=Fz,
            tipo=tipo,
            cutxy=cutxy,
            sallow=SALLOW,
            E=E,
            nu=NU,
        )

    import pyamg

    Kff = K[free][:, free]
    B = np.zeros((ib.N, 6))
    xd = ib.doflocs
    B[0::3, 0] = 1
    B[1::3, 1] = 1
    B[2::3, 2] = 1
    B[0::3, 3] = -xd[1, 0::3]
    B[1::3, 3] = xd[0, 1::3]
    B[1::3, 4] = -xd[2, 1::3]
    B[2::3, 4] = xd[1, 2::3]
    B[0::3, 5] = xd[2, 0::3]
    B[2::3, 5] = -xd[0, 2::3]
    ml = pyamg.smoothed_aggregation_solver(Kff, B=B[free], max_coarse=3000)
    rr = []
    u = np.zeros(ib.N)
    u[free] = ml.solve(fvec[free], tol=1e-10, accel="cg", maxiter=3000, residuals=rr)
    ksp_its = len(rr) - 1
    rel_res = float(np.linalg.norm(Kff @ u[free] - fvec[free]) / np.linalg.norm(fvec[free]))

    Xr = np.array([[0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], float)
    Wr = np.ones(4) / 24.0
    bv = Basis(mesh, e, quadrature=(Xr, Wr))
    ui = bv.interpolate(u)
    eps = sym_grad(ui)
    sg = 2.0 * mu * eps + lam * eye(trace(eps), 3)
    vm = np.sqrt(
        0.5 * ((sg[0, 0] - sg[1, 1]) ** 2 + (sg[1, 1] - sg[2, 2]) ** 2 + (sg[2, 2] - sg[0, 0]) ** 2)
        + 3.0 * (sg[0, 1] ** 2 + sg[1, 2] ** 2 + sg[0, 2] ** 2)
    )
    nv = mesh.p.shape[1]
    acc = np.zeros(nv)
    cnt = np.zeros(nv)
    mx = np.zeros(nv)
    for k in range(4):
        np.add.at(acc, mesh.t[k], vm[:, k])
        np.add.at(cnt, mesh.t[k], 1)
        np.maximum.at(mx, mesh.t[k], vm[:, k])
    avg = acc / np.maximum(cnt, 1)
    dv = np.linalg.norm(pv[:, :2] - tipo, axis=1)
    dcut = tr.query(pv[:, :2])[0]
    s_ = (dv >= 4.0) & (dv < 15.0) & (dcut > 3.0)
    i_avg = int(np.where(s_)[0][np.argmax(avg[s_])])
    i_max = int(np.where(s_)[0][np.argmax(mx[s_])])

    return {
        "schema": "jarambit.native_step_solid_tip.v1",
        "subject": "c10a",
        "step_path": "designs/switchback/C10a/cad/switchback_revC10a_ground.step",
        "step_sha256": step_sha,
        "stl_path": "designs/switchback/C10a/cad/switchback_revC10a_ground.stl",
        "stl_sha256": stl_sha,
        "solver": "fem_solid/step_solid.py (skfem ElementTetP2 + pyamg smoothed_aggregation_solver CG)",
        "T_Nmm": T_NMM,
        "sallow_joint_MPa": round(SALLOW, 2),
        "n_tet": int(len(TT)),
        "n_dof": int(ib.N),
        "ksp_its": int(ksp_its),
        "rel_res": rel_res,
        "R_CUT": r_cut,
        "NL": nl,
        "NSUB": nsub,
        "nodal_avg_peak": {"MPa": round(float(avg[i_avg]), 1), "at": pv[i_avg].round(2).tolist(), "dist": round(float(dv[i_avg]), 2)},
        "nodal_max_peak": {"MPa": round(float(mx[i_max]), 1), "at": pv[i_max].round(2).tolist(), "dist": round(float(dv[i_max]), 2)},
        "SF_nodal_avg": round(float(SALLOW / avg[i_avg]), 4),
        "SF_nodal_max": round(float(SALLOW / mx[i_max]), 4),
        "wall_s": round(time.time() - t0, 2),
    }


if __name__ == "__main__":
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "evidence" / "cad_battery" / "side" / "c10a_solid_tip.json"
    dump = os.environ.get("DUMP_MESH")
    res = solve_c10a_tip(dump_npz=dump)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=2, sort_keys=True))
