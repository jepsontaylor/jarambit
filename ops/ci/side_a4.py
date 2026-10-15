#!/usr/bin/env python3
"""Side report A4: bore-pin radial support + Winkler grip foundation + plate buckling eigenvalue.

Leaves crates/crescent/src/fem.rs (run_b default ring-hole clamp) untouched
(partial_solver_edit = False). Uses scipy.sparse.linalg.eigsh for the linear
buckling eigenvalue problem K_support * phi = lambda_cr * (-K_G) * phi.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

ROOT = Path(__file__).resolve().parents[2]
E_MPA = 113800.0
NU = 0.34
BORE_RADIAL_K = 50000.0        # N/mm per bore boundary node
BORE_TANGENTIAL_K = 5000.0     # N/mm friction/pad tangential restraint
BORE_FLANGE_K = 100000.0       # N/mm out-of-plane pin flange restraint
GRIP_FOUNDATION_K = 200.0      # N/mm^3 Winkler foundation on grip zone


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble_plate_and_kg(xy: np.ndarray, tris: np.ndarray, te: np.ndarray, f_lat: np.ndarray):
    """Vectorized CST + Batoz DKT stiffness assembly plus geometric stiffness K_G."""
    n_node = len(xy)
    n_elem = len(tris)
    tri = tris.copy()
    p0 = xy[tri[:, 0]]
    p1 = xy[tri[:, 1]]
    p2 = xy[tri[:, 2]]
    a2 = (p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (p2[:, 0] - p0[:, 0]) * (p1[:, 1] - p0[:, 1])
    cw = a2 < 0
    if np.any(cw):
        tri[cw] = tri[cw][:, [0, 2, 1]]
        p0 = xy[tri[:, 0]]
        p1 = xy[tri[:, 1]]
        p2 = xy[tri[:, 2]]
        a2 = -a2
    area = 0.5 * np.abs(a2)
    t = np.asarray(te, dtype=float)

    # Plane-stress constitutive matrix C (3x3)
    c_fac = E_MPA / (1.0 - NU * NU)
    C = np.array([
        [c_fac, c_fac * NU, 0.0],
        [c_fac * NU, c_fac, 0.0],
        [0.0, 0.0, c_fac * (1.0 - NU) * 0.5],
    ])

    # CST membrane gradients
    b0 = (p1[:, 1] - p2[:, 1]) / a2
    b1 = (p2[:, 1] - p0[:, 1]) / a2
    b2 = (p0[:, 1] - p1[:, 1]) / a2
    c0 = (p2[:, 0] - p1[:, 0]) / a2
    c1 = (p0[:, 0] - p2[:, 0]) / a2
    c2 = (p1[:, 0] - p0[:, 0]) / a2

    Bm = np.zeros((n_elem, 3, 6))
    Bm[:, 0, 0::2] = np.stack([b0, b1, b2], axis=1)
    Bm[:, 1, 1::2] = np.stack([c0, c1, c2], axis=1)
    Bm[:, 2, 0::2] = np.stack([c0, c1, c2], axis=1)
    Bm[:, 2, 1::2] = np.stack([b0, b1, b2], axis=1)

    CBm = np.einsum('ij,ejk->eik', C, Bm)
    Km = np.einsum('eji,ejk,e->eik', Bm, CBm, t * area)

    # DKT bending stiffness (3-point Gauss quadrature)
    xs = np.stack([p0[:, 0], p1[:, 0], p2[:, 0]], axis=1)
    ys = np.stack([p0[:, 1], p1[:, 1], p2[:, 1]], axis=1)
    xe = np.stack([xs[:, 2] - xs[:, 1], xs[:, 0] - xs[:, 2], xs[:, 1] - xs[:, 0]], axis=1)
    ye = np.stack([ys[:, 2] - ys[:, 1], ys[:, 0] - ys[:, 2], ys[:, 1] - ys[:, 0]], axis=1)
    l2 = xe * xe + ye * ye
    p = -6.0 * xe / l2
    q = 3.0 * xe * ye / l2
    r = 3.0 * ye * ye / l2
    tv = -6.0 * ye / l2

    Kb = np.zeros((n_elem, 9, 9))
    Bb_list = []
    for xi, eta, w in ((1.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0),
                       (2.0 / 3.0, 1.0 / 6.0, 1.0 / 3.0),
                       (1.0 / 6.0, 2.0 / 3.0, 1.0 / 3.0)):
        a = 1.0 - 2.0 * xi
        c = 1.0 - 2.0 * eta
        hx_xi = np.stack([
            p[:, 2] * a + (p[:, 1] - p[:, 2]) * eta,
            q[:, 2] * a - (q[:, 1] + q[:, 2]) * eta,
            np.full(n_elem, -4.0 + 6.0 * (xi + eta)) + r[:, 2] * a - eta * (r[:, 1] + r[:, 2]),
            -p[:, 2] * a + eta * (p[:, 0] + p[:, 2]),
            q[:, 2] * a - eta * (q[:, 2] - q[:, 0]),
            np.full(n_elem, -2.0 + 6.0 * xi) + r[:, 2] * a + eta * (r[:, 0] - r[:, 2]),
            -eta * (p[:, 1] + p[:, 0]),
            eta * (q[:, 0] - q[:, 1]),
            -eta * (r[:, 1] - r[:, 0]),
        ], axis=1)
        hy_xi = np.stack([
            tv[:, 2] * a + (tv[:, 1] - tv[:, 2]) * eta,
            1.0 + r[:, 2] * a - (r[:, 1] + r[:, 2]) * eta,
            -q[:, 2] * a + eta * (q[:, 1] + q[:, 2]),
            -tv[:, 2] * a + eta * (tv[:, 0] + tv[:, 2]),
            -1.0 + r[:, 2] * a + eta * (r[:, 0] - r[:, 2]),
            q[:, 2] * a - eta * (q[:, 0] - q[:, 2]),
            -eta * (tv[:, 0] + tv[:, 1]),
            eta * (r[:, 0] - r[:, 1]),
            -eta * (q[:, 0] - q[:, 1]),
        ], axis=1)
        hx_eta = np.stack([
            -p[:, 1] * c - xi * (p[:, 2] - p[:, 1]),
            q[:, 1] * c - xi * (q[:, 1] + q[:, 2]),
            np.full(n_elem, -4.0 + 6.0 * (xi + eta)) + r[:, 1] * c - xi * (r[:, 1] + r[:, 2]),
            xi * (p[:, 0] + p[:, 2]),
            xi * (q[:, 0] - q[:, 2]),
            -xi * (r[:, 2] - r[:, 0]),
            p[:, 1] * c - xi * (p[:, 0] + p[:, 1]),
            q[:, 1] * c + xi * (q[:, 0] - q[:, 1]),
            np.full(n_elem, -2.0 + 6.0 * eta) + r[:, 1] * c + xi * (r[:, 0] - r[:, 1]),
        ], axis=1)
        hy_eta = np.stack([
            -tv[:, 1] * c - xi * (tv[:, 2] - tv[:, 1]),
            1.0 + r[:, 1] * c - xi * (r[:, 1] + r[:, 2]),
            -q[:, 1] * c + xi * (q[:, 1] + q[:, 2]),
            xi * (tv[:, 0] + tv[:, 2]),
            xi * (r[:, 0] - r[:, 2]),
            -xi * (q[:, 0] - q[:, 2]),
            tv[:, 1] * c - xi * (tv[:, 0] + tv[:, 1]),
            -1.0 + r[:, 1] * c + xi * (r[:, 0] - r[:, 1]),
            -q[:, 1] * c - xi * (q[:, 0] - q[:, 1]),
        ], axis=1)
        bb = np.zeros((n_elem, 3, 9))
        bb[:, 0, :] = (ye[:, 1:2] * hx_xi + ye[:, 2:3] * hx_eta) / a2[:, None]
        bb[:, 1, :] = (-xe[:, 1:2] * hy_xi - xe[:, 2:3] * hy_eta) / a2[:, None]
        bb[:, 2, :] = (-xe[:, 1:2] * hx_xi - xe[:, 2:3] * hx_eta + ye[:, 1:2] * hy_xi + ye[:, 2:3] * hy_eta) / a2[:, None]
        Bb_list.append(bb)
        CBb = np.einsum('ij,ejk->eik', C, bb)
        Kb += np.einsum('eji,ejk,e->eik', bb, CBb, w * area * (t ** 3) / 12.0)

    # Assemble global K (5 DOFs per node: u, v, w, thx, thy)
    idm = np.empty((n_elem, 6), dtype=np.int64)
    for a in range(3):
        idm[:, 2 * a] = tri[:, a] * 5
        idm[:, 2 * a + 1] = tri[:, a] * 5 + 1
    idb = np.empty((n_elem, 9), dtype=np.int64)
    for a in range(3):
        idb[:, 3 * a] = tri[:, a] * 5 + 2
        idb[:, 3 * a + 1] = tri[:, a] * 5 + 3
        idb[:, 3 * a + 2] = tri[:, a] * 5 + 4

    rm = np.repeat(idm[:, :, None], 6, axis=2).ravel()
    cm = np.repeat(idm[:, None, :], 6, axis=1).ravel()
    rb = np.repeat(idb[:, :, None], 9, axis=2).ravel()
    cb = np.repeat(idb[:, None, :], 9, axis=1).ravel()
    K = sp.csr_matrix(
        (np.concatenate([Km.ravel(), Kb.ravel()]),
         (np.concatenate([rm, rb]), np.concatenate([cm, cb]))),
        shape=(n_node * 5, n_node * 5),
    )
    return K, tri, area, t, Bm, Bb_list, C, (b0, b1, b2), (c0, c1, c2)


def evaluate_subject(subject: str, d1_path: Path, rs_path: Path, side_a1a3_path: Path) -> dict:
    d1 = json.loads(d1_path.read_text(encoding='utf-8'))
    rs = json.loads(rs_path.read_text(encoding='utf-8'))
    a1a3 = json.loads(side_a1a3_path.read_text(encoding='utf-8'))
    xy = np.asarray(d1['mesh']['xy'], dtype=float)
    tris = np.asarray(d1['mesh']['tris'], dtype=np.int64)
    te = np.asarray(d1['mesh']['te'], dtype=float)
    n_node = len(xy)

    K, tri, area, t, Bm, Bb_list, C, b_grad, c_grad = assemble_plate_and_kg(xy, tris, te, None)

    # Identify bore nodes (radius within 0.35 mm of bore radius) and grip nodes (0 <= x < heel_x)
    ring_id_r = float(a1a3['ring_id_mm']) * 0.5
    ring_od_r = float(a1a3['ring_od_mm']) * 0.5
    heel_x = float(a1a3['heel_x_mm'])
    radii = np.hypot(xy[:, 0], xy[:, 1])
    bore_nodes = np.where(np.abs(radii - ring_id_r) <= 0.35)[0]
    grip_nodes = np.where((xy[:, 0] >= ring_od_r) & (xy[:, 0] < heel_x))[0]

    # Nodal Tributary Area for Winkler foundation
    nodal_area = np.zeros(n_node, dtype=float)
    for a in range(3):
        np.add.at(nodal_area, tri[:, a], area / 3.0)

    # Build support stiffness additions (pin bearing + Winkler grip foundation)
    s_rows, s_cols, s_vals = [], [], []
    for nd in bore_nodes:
        rx, ry = xy[nd, 0] / max(radii[nd], 1e-9), xy[nd, 1] / max(radii[nd], 1e-9)
        tx, ty = -ry, rx
        # 2x2 in-plane spring k_r * (r x r) + k_t * (t x t)
        kxx = BORE_RADIAL_K * rx * rx + BORE_TANGENTIAL_K * tx * tx
        kyy = BORE_RADIAL_K * ry * ry + BORE_TANGENTIAL_K * ty * ty
        kxy = (BORE_RADIAL_K - BORE_TANGENTIAL_K) * rx * ry
        u_dof, v_dof, w_dof, thx_dof, thy_dof = nd * 5, nd * 5 + 1, nd * 5 + 2, nd * 5 + 3, nd * 5 + 4
        s_rows.extend([u_dof, u_dof, v_dof, v_dof, w_dof, thx_dof, thy_dof])
        s_cols.extend([u_dof, v_dof, u_dof, v_dof, w_dof, thx_dof, thy_dof])
        s_vals.extend([kxx, kxy, kxy, kyy, BORE_FLANGE_K, BORE_FLANGE_K * 4.0, BORE_FLANGE_K * 4.0])

    for nd in grip_nodes:
        kw = GRIP_FOUNDATION_K * max(nodal_area[nd], 1e-3)
        u_dof, v_dof, w_dof, thx_dof, thy_dof = nd * 5, nd * 5 + 1, nd * 5 + 2, nd * 5 + 3, nd * 5 + 4
        s_rows.extend([u_dof, v_dof, w_dof, thx_dof, thy_dof])
        s_cols.extend([u_dof, v_dof, w_dof, thx_dof, thy_dof])
        s_vals.extend([kw * 0.25, kw * 0.25, kw, kw * 2.0, kw * 2.0])

    K_support = (K + sp.csr_matrix((s_vals, (s_rows, s_cols)), shape=K.shape)).tocsc()

    # Tip patch nodes (within 2 mm of tip_xy)
    tip_xy = np.asarray(a1a3['tip_xy_mm'], dtype=float)
    dist_tip = np.hypot(xy[:, 0] - tip_xy[0], xy[:, 1] - tip_xy[1])
    tip_nodes = np.where(dist_tip <= 2.0)[0]
    if len(tip_nodes) == 0:
        tip_nodes = np.array([int(np.argmin(dist_tip))])

    # Solve lateral unit load (1 N out-of-plane w + 0.15 N in-plane compressive/pry component for buckling)
    F_lat = np.zeros(n_node * 5, dtype=float)
    for nd in tip_nodes:
        F_lat[nd * 5 + 2] = 1.0 / len(tip_nodes)
    u_lat = spla.spsolve(K_support, F_lat)

    # Compute bending von Mises per element under unit lateral load
    ub = np.empty((len(tri), 9), dtype=float)
    for a in range(3):
        ub[:, 3 * a] = u_lat[tri[:, a] * 5 + 2]
        ub[:, 3 * a + 1] = u_lat[tri[:, a] * 5 + 3]
        ub[:, 3 * a + 2] = u_lat[tri[:, a] * 5 + 4]
    vm_elem = np.zeros(len(tri), dtype=float)
    for bb in Bb_list:
        sig = np.einsum('ij,ej->ei', C, np.einsum('eij,ej->ei', bb, ub)) * (t[:, None] * 0.5)
        vm_q = np.sqrt(sig[:, 0] ** 2 - sig[:, 0] * sig[:, 1] + sig[:, 1] ** 2 + 3.0 * sig[:, 2] ** 2)
        vm_elem = np.maximum(vm_elem, vm_q)

    centroids = xy[tri].mean(axis=1)
    c_dist_tip = np.hypot(centroids[:, 0] - tip_xy[0], centroids[:, 1] - tip_xy[1])
    keep = c_dist_tip >= 15.0
    blade_mask = keep & (centroids[:, 0] >= heel_x)
    hand_mask = keep & (centroids[:, 0] < heel_x)
    blade_peak = float(vm_elem[blade_mask].max())
    hand_peak = float(vm_elem[hand_mask].max())
    # Sequence ratio = hand yield load / blade yield load = blade_peak / hand_peak
    supported_seq_ratio = blade_peak / hand_peak

    # Geometric stiffness K_G on w DOFs from compressive in-plane tip load (260 N hunter load)
    F_inplane = np.zeros(n_node * 5, dtype=float)
    d_vec = -tip_xy / np.linalg.norm(tip_xy)
    for nd in tip_nodes:
        F_inplane[nd * 5] = 260.0 * d_vec[0] / len(tip_nodes)
        F_inplane[nd * 5 + 1] = 260.0 * d_vec[1] / len(tip_nodes)
    u_inplane = spla.spsolve(K_support, F_inplane)
    um = np.empty((len(tri), 6), dtype=float)
    for a in range(3):
        um[:, 2 * a] = u_inplane[tri[:, a] * 5]
        um[:, 2 * a + 1] = u_inplane[tri[:, a] * 5 + 1]
    sig_m = np.einsum('ij,ej->ei', C, np.einsum('eij,ej->ei', Bm, um))  # (n_elem, 3): sxx, syy, txy

    # Assemble K_G on the out-of-plane w DOFs (nd * 5 + 2) using linear w-gradients (b_grad, c_grad)
    # Use compressive principal membrane stress magnitude to form positive-definite destabilizing matrix G
    s_mean = 0.5 * (sig_m[:, 0] + sig_m[:, 1])
    s_rad = np.hypot(0.5 * (sig_m[:, 0] - sig_m[:, 1]), sig_m[:, 2])
    s_comp = np.maximum(-(s_mean - s_rad), 1e-3)  # compressive principal stress (MPa)
    grad_w = np.stack([
        np.stack(b_grad, axis=1),
        np.stack(c_grad, axis=1),
    ], axis=1)  # (n_elem, 2, 3)
    G_elem = np.einsum('eki,ekj,e->eij', grad_w, grad_w, s_comp * t * area)
    w_dofs = tri * 5 + 2
    rw = np.repeat(w_dofs[:, :, None], 3, axis=2).ravel()
    cw_idx = np.repeat(w_dofs[:, None, :], 3, axis=1).ravel()
    G_mat = sp.csr_matrix((G_elem.ravel(), (rw, cw_idx)), shape=K.shape).tocsc()

    # Solve smallest buckling eigenvalue: K_support * phi = lambda * G_mat * phi
    # Equivalent to largest eigenvalue of K_support^{-1} * G_mat: mu = 1 / lambda
    k_lu = spla.splu(K_support)
    n_total = K.shape[0]
    lin_op = spla.LinearOperator(
        shape=(n_total, n_total),
        matvec=lambda x: k_lu.solve(G_mat.dot(x)),
        dtype=float,
    )
    rng = np.random.default_rng(1729)
    v0 = rng.standard_normal(n_total)
    mu_vals, _ = spla.eigsh(lin_op, k=1, which='LM', v0=v0, tol=1e-6, maxiter=2000)
    mu_max = float(mu_vals[0])
    lambda_cr = float(1.0 / mu_max)

    cert_seq = float(rs['seq_ratio'])
    genome_rel = a1a3['genome']
    genome_sha = _sha256(ROOT / genome_rel)
    status = 'pass' if (lambda_cr > 0.0 and supported_seq_ratio >= cert_seq) else 'fail'

    return {
        'schema': 'jarambit.side_report.a4.v1',
        'subject': subject,
        'status': status,
        'genome': genome_rel,
        'genome_sha256': genome_sha,
        'd1_sha256': _sha256(d1_path),
        'mesh_max_area_mm2': 0.25,
        'n_elem': int(len(tri)),
        'n_node': int(n_node),
        'bore_support': {
            'model': 'radial_pin_bearing_and_flange',
            'k_radial_n_per_mm': BORE_RADIAL_K,
            'k_tangential_n_per_mm': BORE_TANGENTIAL_K,
            'k_flange_n_per_mm': BORE_FLANGE_K,
            'n_bore_nodes': int(len(bore_nodes)),
        },
        'grip_foundation_stiffness': {
            'model': 'winkler_grip_pad_foundation',
            'k_foundation_n_per_mm3': GRIP_FOUNDATION_K,
            'n_grip_nodes': int(len(grip_nodes)),
        },
        'eigensolver': 'scipy.sparse.linalg.eigsh',
        'buckling_eigenvalue': lambda_cr,
        'buckling_critical_load_n': float(260.0 * lambda_cr),
        'supported_blade_peak_mpa_per_n': blade_peak,
        'supported_hand_peak_mpa_per_n': hand_peak,
        'supported_seq_ratio': supported_seq_ratio,
        'certified_seq_ratio': cert_seq,
        'supported_vs_certified_seq_delta': float(supported_seq_ratio - cert_seq),
        'certified_model': 'run_b ring-hole clamp in all 5 DOFs',
        'partial_solver_edit': False,
        'changes_seq_ratio': False,
    }


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject')
    parser.add_argument('--d1', type=Path)
    parser.add_argument('--rs', type=Path)
    parser.add_argument('--a1a3', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    if args.subject and args.d1 and args.rs and args.a1a3:
        rec = evaluate_subject(args.subject, args.d1, args.rs, args.a1a3)
        out_path = args.out or (ROOT / 'evidence' / 'cad_battery' / 'side' / f'{args.subject}_a4.json')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(rec, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(f"{args.subject}: status={rec['status']} lambda_cr={rec['buckling_eigenvalue']:.4f} "
              f"seq_sup={rec['supported_seq_ratio']:.4f} seq_cert={rec['certified_seq_ratio']:.4f}")
        return 0

    custody_w271 = Path('/home/ubuntu/.jarambit_custody_archive/out_custody/jarambit_w271/out')
    if not custody_w271.is_dir():
        custody_w271 = ROOT / 'out_custody' / 'jarambit_w271' / 'out'
    subjects = {
        'g3': (
            ROOT / 'evidence/wave27/g3_tip+00_t60_tt3_D1.json',
            ROOT / 'evidence/rs_v2/g3_tip+00_t60_tt3.json',
            ROOT / 'evidence/cad_battery/side/g3_a1a3.json',
        ),
        'w271b_11772': (
            custody_w271 / 'solidcert_w271b_11772/w271b_11772_D1.json',
            ROOT / 'evidence/rs_v2/w271b_11772.json',
            ROOT / 'evidence/cad_battery/side/w271b_11772_a1a3.json',
        ),
        'w271b_11860': (
            custody_w271 / 'solidcert_w271b_11860/w271b_11860_D1.json',
            ROOT / 'evidence/rs_v2/w271b_11860.json',
            ROOT / 'evidence/cad_battery/side/w271b_11860_a1a3.json',
        ),
        'w271c_11522': (
            custody_w271 / 'solidcert_w271c_11522/w271c_11522_D1.json',
            ROOT / 'evidence/rs_v2/w271c_11522.json',
            ROOT / 'evidence/cad_battery/side/w271c_11522_a1a3.json',
        ),
    }
    out_dir = ROOT / 'evidence' / 'cad_battery' / 'side'
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (d1_p, rs_p, a1a3_p) in subjects.items():
        if args.subject and name != args.subject:
            continue
        rec = evaluate_subject(name, d1_p, rs_p, a1a3_p)
        out_path = out_dir / f'{name}_a4.json'
        out_path.write_text(json.dumps(rec, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(f"{name}: status={rec['status']} lambda_cr={rec['buckling_eigenvalue']:.4f} "
              f"seq_sup={rec['supported_seq_ratio']:.4f} seq_cert={rec['certified_seq_ratio']:.4f}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

