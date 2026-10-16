//! Native Rust Side-Report A4 solver (`jarambit.side_report.a4.v1`):
//! 5-DOF CST + Batoz DKT plate stiffness with radial/tangential/flange bore-pin bearing springs
//! + Winkler grip pad foundation + `faer` sparse Cholesky + K-orthogonal Lanczos buckling eigensolver.
//!
//! Matches `ops/ci/side_a4.py` while leaving `crates/crescent/src/fem.rs` (`run_b` default ring-hole
//! clamp) untouched (`partial_solver_edit = false`).

use faer::dyn_stack::{MemBuffer, MemStack};
use faer::sparse::linalg::cholesky as ch;
use faer::sparse::{SparseColMat, Triplet};

pub const E_MPA: f64 = 113_800.0;
pub const NU: f64 = 0.34;
pub const BORE_RADIAL_K: f64 = 50_000.0;
pub const BORE_TANGENTIAL_K: f64 = 5_000.0;
pub const BORE_FLANGE_K: f64 = 100_000.0;
pub const GRIP_FOUNDATION_K: f64 = 200.0;

#[derive(Clone, Debug)]
pub struct SideA4Input {
    pub subject: String,
    pub genome: String,
    pub genome_sha256: String,
    pub d1_sha256: String,
    pub xy: Vec<(f64, f64)>,
    pub tris: Vec<[usize; 3]>,
    pub te: Vec<f64>,
    pub ring_id_mm: f64,
    pub ring_od_mm: f64,
    pub heel_x_mm: f64,
    pub tip_xy_mm: (f64, f64),
    pub certified_seq_ratio: f64,
}

#[derive(Clone, Debug)]
pub struct SideA4Result {
    pub subject: String,
    pub status: &'static str,
    pub genome: String,
    pub genome_sha256: String,
    pub d1_sha256: String,
    pub mesh_max_area_mm2: f64,
    pub n_elem: usize,
    pub n_node: usize,
    pub n_bore_nodes: usize,
    pub n_grip_nodes: usize,
    pub buckling_eigenvalue: f64,
    pub buckling_critical_load_n: f64,
    pub supported_blade_peak_mpa_per_n: f64,
    pub supported_hand_peak_mpa_per_n: f64,
    pub supported_seq_ratio: f64,
    pub certified_seq_ratio: f64,
    pub supported_vs_certified_seq_delta: f64,
}

struct ElemData {
    tri: [usize; 3],
    area: f64,
    t: f64,
    b_grad: [f64; 3],
    c_grad: [f64; 3],
    bm: [[f64; 6]; 3],
    bb_list: [[[f64; 9]; 3]; 3],
}

fn c_plane(e: f64, nu: f64) -> [[f64; 3]; 3] {
    let k = e / (1.0 - nu * nu);
    [
        [k, k * nu, 0.0],
        [k * nu, k, 0.0],
        [0.0, 0.0, k * (1.0 - nu) * 0.5],
    ]
}

fn dkt_bb(
    xs: [f64; 3],
    ys: [f64; 3],
    a2: f64,
    xi: f64,
    eta: f64,
) -> [[f64; 9]; 3] {
    let xe = [xs[2] - xs[1], xs[0] - xs[2], xs[1] - xs[0]];
    let ye = [ys[2] - ys[1], ys[0] - ys[2], ys[1] - ys[0]];
    let mut p = [0.0; 3];
    let mut q = [0.0; 3];
    let mut r = [0.0; 3];
    let mut tv = [0.0; 3];
    for i in 0..3 {
        let l2 = (xe[i] * xe[i] + ye[i] * ye[i]).max(1e-18);
        p[i] = -6.0 * xe[i] / l2;
        q[i] = 3.0 * xe[i] * ye[i] / l2;
        r[i] = 3.0 * ye[i] * ye[i] / l2;
        tv[i] = -6.0 * ye[i] / l2;
    }
    let a = 1.0 - 2.0 * xi;
    let c = 1.0 - 2.0 * eta;
    let hx_xi = [
        p[2] * a + (p[1] - p[2]) * eta,
        q[2] * a - (q[1] + q[2]) * eta,
        -4.0 + 6.0 * (xi + eta) + r[2] * a - eta * (r[1] + r[2]),
        -p[2] * a + eta * (p[0] + p[2]),
        q[2] * a - eta * (q[2] - q[0]),
        -2.0 + 6.0 * xi + r[2] * a + eta * (r[0] - r[2]),
        -eta * (p[1] + p[0]),
        eta * (q[0] - q[1]),
        -eta * (r[1] - r[0]),
    ];
    let hy_xi = [
        tv[2] * a + (tv[1] - tv[2]) * eta,
        1.0 + r[2] * a - (r[1] + r[2]) * eta,
        -q[2] * a + eta * (q[1] + q[2]),
        -tv[2] * a + eta * (tv[0] + tv[2]),
        -1.0 + r[2] * a + eta * (r[0] - r[2]),
        q[2] * a - eta * (q[0] - q[2]),
        -eta * (tv[0] + tv[1]),
        eta * (r[0] - r[1]),
        -eta * (q[0] - q[1]),
    ];
    let hx_eta = [
        -p[1] * c - xi * (p[2] - p[1]),
        q[1] * c - xi * (q[1] + q[2]),
        -4.0 + 6.0 * (xi + eta) + r[1] * c - xi * (r[1] + r[2]),
        xi * (p[0] + p[2]),
        xi * (q[0] - q[2]),
        -xi * (r[2] - r[0]),
        p[1] * c - xi * (p[0] + p[1]),
        q[1] * c + xi * (q[0] - q[1]),
        -2.0 + 6.0 * eta + r[1] * c + xi * (r[0] - r[1]),
    ];
    let hy_eta = [
        -tv[1] * c - xi * (tv[2] - tv[1]),
        1.0 + r[1] * c - xi * (r[1] + r[2]),
        -q[1] * c + xi * (q[1] + q[2]),
        xi * (tv[0] + tv[2]),
        xi * (r[0] - r[2]),
        -xi * (q[0] - q[2]),
        tv[1] * c - xi * (tv[0] + tv[1]),
        -1.0 + r[1] * c + xi * (r[0] - r[1]),
        -q[1] * c - xi * (q[0] - q[1]),
    ];
    let mut bb = [[0.0; 9]; 3];
    for j in 0..9 {
        bb[0][j] = (ye[1] * hx_xi[j] + ye[2] * hx_eta[j]) / a2;
        bb[1][j] = (-xe[1] * hy_xi[j] - xe[2] * hy_eta[j]) / a2;
        bb[2][j] = (-xe[1] * hx_xi[j] - xe[2] * hx_eta[j] + ye[1] * hy_xi[j] + ye[2] * hy_eta[j]) / a2;
    }
    bb
}

#[inline]
fn add_lower_triplet(
    triplets: &mut Vec<Triplet<usize, usize, f64>>,
    dmax: &mut [f64],
    i: usize,
    j: usize,
    v: f64,
) {
    let (r, c) = if i >= j { (i, j) } else { (j, i) };
    if r == c {
        dmax[r] += v;
    }
    triplets.push(Triplet::new(r, c, v));
}

pub fn solve_side_a4(input: &SideA4Input) -> Option<SideA4Result> {
    let n_node = input.xy.len();
    let n_elem = input.tris.len();
    if n_node < 3 || n_elem == 0 || input.te.len() != n_elem {
        return None;
    }
    let n_dof = n_node * 5;
    let cmat = c_plane(E_MPA, NU);

    let mut elems = Vec::with_capacity(n_elem);
    let mut nodal_area = vec![0.0f64; n_node];
    let mut triplets = Vec::with_capacity(n_elem * 66 + n_node * 8);
    let mut dmax = vec![0.0f64; n_dof];

    let gp = [
        (1.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0),
        (2.0 / 3.0, 1.0 / 6.0, 1.0 / 3.0),
        (1.0 / 6.0, 2.0 / 3.0, 1.0 / 3.0),
    ];

    for (e_idx, raw_tri) in input.tris.iter().enumerate() {
        let mut tri = *raw_tri;
        let mut p0 = input.xy[tri[0]];
        let mut p1 = input.xy[tri[1]];
        let mut p2 = input.xy[tri[2]];
        let mut a2 = (p1.0 - p0.0) * (p2.1 - p0.1) - (p2.0 - p0.0) * (p1.1 - p0.1);
        if a2 < 0.0 {
            tri.swap(1, 2);
            p0 = input.xy[tri[0]];
            p1 = input.xy[tri[1]];
            p2 = input.xy[tri[2]];
            a2 = -a2;
        }
        let area = 0.5 * a2.abs();
        if area < 1e-12 {
            continue;
        }
        let t = input.te[e_idx];
        for &nd in &tri {
            nodal_area[nd] += area / 3.0;
        }

        let b0 = (p1.1 - p2.1) / a2;
        let b1 = (p2.1 - p0.1) / a2;
        let b2 = (p0.1 - p1.1) / a2;
        let c0 = (p2.0 - p1.0) / a2;
        let c1 = (p0.0 - p2.0) / a2;
        let c2 = (p1.0 - p0.0) / a2;

        let b_grad = [b0, b1, b2];
        let c_grad = [c0, c1, c2];
        let mut bm = [[0.0f64; 6]; 3];
        for a in 0..3 {
            bm[0][2 * a] = b_grad[a];
            bm[1][2 * a + 1] = c_grad[a];
            bm[2][2 * a] = c_grad[a];
            bm[2][2 * a + 1] = b_grad[a];
        }

        // Km = Bm^T C Bm * (t * area)
        let mut c_bm = [[0.0f64; 6]; 3];
        for i in 0..3 {
            for j in 0..6 {
                c_bm[i][j] = cmat[i][0] * bm[0][j] + cmat[i][1] * bm[1][j] + cmat[i][2] * bm[2][j];
            }
        }
        let scale_m = t * area;
        let mut km = [[0.0f64; 6]; 6];
        for i in 0..6 {
            for j in 0..=i {
                km[i][j] = scale_m * (bm[0][i] * c_bm[0][j] + bm[1][i] * c_bm[1][j] + bm[2][i] * c_bm[2][j]);
            }
        }

        let xs = [p0.0, p1.0, p2.0];
        let ys = [p0.1, p1.1, p2.1];
        let mut bb_list = [[[0.0f64; 9]; 3]; 3];
        let mut kb = [[0.0f64; 9]; 9];
        for (q_idx, &(xi, eta, w)) in gp.iter().enumerate() {
            let bb = dkt_bb(xs, ys, a2, xi, eta);
            bb_list[q_idx] = bb;
            let mut c_bb = [[0.0f64; 9]; 3];
            for i in 0..3 {
                for j in 0..9 {
                    c_bb[i][j] = cmat[i][0] * bb[0][j] + cmat[i][1] * bb[1][j] + cmat[i][2] * bb[2][j];
                }
            }
            let scale_b = w * area * (t * t * t) / 12.0;
            for i in 0..9 {
                for j in 0..=i {
                    kb[i][j] += scale_b * (bb[0][i] * c_bb[0][j] + bb[1][i] * c_bb[1][j] + bb[2][i] * c_bb[2][j]);
                }
            }
        }

        let idm = [
            tri[0] * 5,
            tri[0] * 5 + 1,
            tri[1] * 5,
            tri[1] * 5 + 1,
            tri[2] * 5,
            tri[2] * 5 + 1,
        ];
        for i in 0..6 {
            for j in 0..=i {
                add_lower_triplet(&mut triplets, &mut dmax, idm[i], idm[j], km[i][j]);
            }
        }

        let idb = [
            tri[0] * 5 + 2,
            tri[0] * 5 + 3,
            tri[0] * 5 + 4,
            tri[1] * 5 + 2,
            tri[1] * 5 + 3,
            tri[1] * 5 + 4,
            tri[2] * 5 + 2,
            tri[2] * 5 + 3,
            tri[2] * 5 + 4,
        ];
        for i in 0..9 {
            for j in 0..=i {
                add_lower_triplet(&mut triplets, &mut dmax, idb[i], idb[j], kb[i][j]);
            }
        }

        elems.push(ElemData {
            tri,
            area,
            t,
            b_grad,
            c_grad,
            bm,
            bb_list,
        });
    }

    let ring_id_r = input.ring_id_mm * 0.5;
    let ring_od_r = input.ring_od_mm * 0.5;
    let heel_x = input.heel_x_mm;
    let radii: Vec<f64> = input.xy.iter().map(|&(x, y)| x.hypot(y)).collect();
    let mut bore_nodes: Vec<usize> = (0..n_node)
        .filter(|&nd| (radii[nd] - ring_id_r).abs() <= 0.35)
        .collect();
    if bore_nodes.is_empty() {
        let min_r = radii.iter().copied().fold(f64::INFINITY, f64::min);
        bore_nodes = (0..n_node).filter(|&nd| (radii[nd] - min_r).abs() <= 0.5).collect();
    }
    let grip_nodes: Vec<usize> = (0..n_node)
        .filter(|&nd| input.xy[nd].0 >= ring_od_r && input.xy[nd].0 < heel_x)
        .collect();

    for &nd in &bore_nodes {
        let r = radii[nd].max(1e-9);
        let rx = input.xy[nd].0 / r;
        let ry = input.xy[nd].1 / r;
        let tx = -ry;
        let ty = rx;
        let kxx = BORE_RADIAL_K * rx * rx + BORE_TANGENTIAL_K * tx * tx;
        let kyy = BORE_RADIAL_K * ry * ry + BORE_TANGENTIAL_K * ty * ty;
        let kxy = (BORE_RADIAL_K - BORE_TANGENTIAL_K) * rx * ry;
        let u_dof = nd * 5;
        let v_dof = nd * 5 + 1;
        let w_dof = nd * 5 + 2;
        let thx_dof = nd * 5 + 3;
        let thy_dof = nd * 5 + 4;
        add_lower_triplet(&mut triplets, &mut dmax, u_dof, u_dof, kxx);
        add_lower_triplet(&mut triplets, &mut dmax, v_dof, u_dof, kxy);
        add_lower_triplet(&mut triplets, &mut dmax, v_dof, v_dof, kyy);
        add_lower_triplet(&mut triplets, &mut dmax, w_dof, w_dof, BORE_FLANGE_K);
        add_lower_triplet(&mut triplets, &mut dmax, thx_dof, thx_dof, BORE_FLANGE_K * 4.0);
        add_lower_triplet(&mut triplets, &mut dmax, thy_dof, thy_dof, BORE_FLANGE_K * 4.0);
    }

    for &nd in &grip_nodes {
        let kw = GRIP_FOUNDATION_K * nodal_area[nd].max(1e-3);
        let u_dof = nd * 5;
        let v_dof = nd * 5 + 1;
        let w_dof = nd * 5 + 2;
        let thx_dof = nd * 5 + 3;
        let thy_dof = nd * 5 + 4;
        add_lower_triplet(&mut triplets, &mut dmax, u_dof, u_dof, kw * 0.25);
        add_lower_triplet(&mut triplets, &mut dmax, v_dof, v_dof, kw * 0.25);
        add_lower_triplet(&mut triplets, &mut dmax, w_dof, w_dof, kw);
        add_lower_triplet(&mut triplets, &mut dmax, thx_dof, thx_dof, kw * 2.0);
        add_lower_triplet(&mut triplets, &mut dmax, thy_dof, thy_dof, kw * 2.0);
    }

    // Factor K_support with faer sparse Cholesky
    let k_mat = SparseColMat::<usize, f64>::try_new_from_triplets(n_dof, n_dof, &triplets).ok()?;
    let sym = ch::factorize_symbolic_cholesky(
        k_mat.symbolic(),
        faer::Side::Lower,
        Default::default(),
        Default::default(),
    )
    .ok()?;
    let tol = (dmax.iter().fold(0.0f64, |m, d| m.max(d.abs())) * 1e-13).max(1e-300);
    let reg = faer::linalg::cholesky::llt::factor::LltRegularization {
        dynamic_regularization_delta: 1e300,
        dynamic_regularization_epsilon: tol,
    };
    let mut l_vals = vec![0.0f64; sym.len_val()];
    let par = faer::Par::Seq;
    let mut factor_buf =
        MemBuffer::try_new(sym.factorize_numeric_llt_scratch::<f64>(par, Default::default())).ok()?;
    sym.factorize_numeric_llt::<f64>(
        &mut l_vals,
        k_mat.as_ref(),
        faer::Side::Lower,
        reg,
        par,
        MemStack::new(&mut factor_buf),
        Default::default(),
    )
    .ok()?;
    let llt = ch::LltRef::new(&sym, &l_vals);

    // Tip patch nodes (within 2.0 mm of tip_xy_mm)
    let tip_xy = input.tip_xy_mm;
    let mut tip_nodes: Vec<usize> = (0..n_node)
        .filter(|&nd| (input.xy[nd].0 - tip_xy.0).hypot(input.xy[nd].1 - tip_xy.1) <= 2.0)
        .collect();
    if tip_nodes.is_empty() {
        let nearest = (0..n_node).min_by(|&a, &b| {
            let da = (input.xy[a].0 - tip_xy.0).hypot(input.xy[a].1 - tip_xy.1);
            let db = (input.xy[b].0 - tip_xy.0).hypot(input.xy[b].1 - tip_xy.1);
            da.partial_cmp(&db).unwrap_or(std::cmp::Ordering::Equal)
        })?;
        tip_nodes.push(nearest);
    }

    // Solve both u_lat (col 0) and u_inplane (col 1) in one multi-RHS call
    let tip_norm = tip_xy.0.hypot(tip_xy.1).max(1e-9);
    let d_vec = (-tip_xy.0 / tip_norm, -tip_xy.1 / tip_norm);
    let n_tip = tip_nodes.len() as f64;
    let mut rhs = vec![0.0f64; n_dof * 2];
    for &nd in &tip_nodes {
        rhs[nd * 5 + 2] = 1.0 / n_tip;
        rhs[n_dof + nd * 5] = 260.0 * d_vec.0 / n_tip;
        rhs[n_dof + nd * 5 + 1] = 260.0 * d_vec.1 / n_tip;
    }
    let mut solve_buf = MemBuffer::new(sym.solve_in_place_scratch::<f64>(2, par));
    llt.solve_in_place_with_conj(
        faer::Conj::No,
        faer::MatMut::from_column_major_slice_mut(&mut rhs, n_dof, 2),
        par,
        MemStack::new(&mut solve_buf),
    );
    let (u_lat, u_inplane) = rhs.split_at(n_dof);

    // Compute bending von Mises per element under unit lateral load and build element G matrices
    let mut blade_peak = 0.0f64;
    let mut hand_peak = 0.0f64;
    let mut g_elems: Vec<([usize; 3], [[f64; 3]; 3])> = Vec::with_capacity(elems.len());

    for el in &elems {
        let mut ub = [0.0f64; 9];
        let mut um = [0.0f64; 6];
        for a in 0..3 {
            ub[3 * a] = u_lat[el.tri[a] * 5 + 2];
            ub[3 * a + 1] = u_lat[el.tri[a] * 5 + 3];
            ub[3 * a + 2] = u_lat[el.tri[a] * 5 + 4];
            um[2 * a] = u_inplane[el.tri[a] * 5];
            um[2 * a + 1] = u_inplane[el.tri[a] * 5 + 1];
        }
        let mut vm_e = 0.0f64;
        let half_t = el.t * 0.5;
        for bb in &el.bb_list {
            let mut kap = [0.0f64; 3];
            for r in 0..3 {
                for q in 0..9 {
                    kap[r] += bb[r][q] * ub[q];
                }
            }
            let s0 = (cmat[0][0] * kap[0] + cmat[0][1] * kap[1]) * half_t;
            let s1 = (cmat[1][0] * kap[0] + cmat[1][1] * kap[1]) * half_t;
            let s2 = cmat[2][2] * kap[2] * half_t;
            let vm = (s0 * s0 - s0 * s1 + s1 * s1 + 3.0 * s2 * s2).max(0.0).sqrt();
            vm_e = vm_e.max(vm);
        }

        let cx = (input.xy[el.tri[0]].0 + input.xy[el.tri[1]].0 + input.xy[el.tri[2]].0) / 3.0;
        let cy = (input.xy[el.tri[0]].1 + input.xy[el.tri[1]].1 + input.xy[el.tri[2]].1) / 3.0;
        let c_dist_tip = (cx - tip_xy.0).hypot(cy - tip_xy.1);
        if c_dist_tip >= 15.0 {
            if cx >= heel_x {
                blade_peak = blade_peak.max(vm_e);
            } else {
                hand_peak = hand_peak.max(vm_e);
            }
        }

        // Membrane stress under 260 N compressive in-plane tip load
        let mut eps = [0.0f64; 3];
        for r in 0..3 {
            for q in 0..6 {
                eps[r] += el.bm[r][q] * um[q];
            }
        }
        let sxx = cmat[0][0] * eps[0] + cmat[0][1] * eps[1];
        let syy = cmat[1][0] * eps[0] + cmat[1][1] * eps[1];
        let txy = cmat[2][2] * eps[2];
        let s_mean = 0.5 * (sxx + syy);
        let s_rad = (0.5 * (sxx - syy)).hypot(txy);
        let s_comp = (-(s_mean - s_rad)).max(1e-3);
        let scale_g = s_comp * el.t * el.area;
        let mut g_loc = [[0.0f64; 3]; 3];
        for i in 0..3 {
            for j in 0..3 {
                g_loc[i][j] = scale_g * (el.b_grad[i] * el.b_grad[j] + el.c_grad[i] * el.c_grad[j]);
            }
        }
        let w_dofs = [el.tri[0] * 5 + 2, el.tri[1] * 5 + 2, el.tri[2] * 5 + 2];
        g_elems.push((w_dofs, g_loc));
    }

    let supported_seq_ratio = blade_peak / hand_peak.max(1e-12);

    // Solve largest eigenvalue mu_max of K_support^{-1} G_mat via K-orthogonal Lanczos
    // Operator T(x) = K_support^{-1} (G_mat * x) is self-adjoint in <u, v>_K = u^T K_support v.
    let apply_g = |x: &[f64], out: &mut [f64]| {
        out.fill(0.0);
        for &(w_dofs, ref g_loc) in &g_elems {
            let x0 = x[w_dofs[0]];
            let x1 = x[w_dofs[1]];
            let x2 = x[w_dofs[2]];
            out[w_dofs[0]] += g_loc[0][0] * x0 + g_loc[0][1] * x1 + g_loc[0][2] * x2;
            out[w_dofs[1]] += g_loc[1][0] * x0 + g_loc[1][1] * x1 + g_loc[1][2] * x2;
            out[w_dofs[2]] += g_loc[2][0] * x0 + g_loc[2][1] * x1 + g_loc[2][2] * x2;
        }
    };

    let mut solve_1_buf = MemBuffer::new(sym.solve_in_place_scratch::<f64>(1, par));
    // Deterministic starting vector on w DOFs, mapped into range(T) so <q0, q0>_K = q0^T p0 is known
    let mut seed = vec![0.0f64; n_dof];
    let mut state = 1729u64;
    for nd in 0..n_node {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1442695040888963407);
        let u = ((state >> 11) as f64) * (1.0 / ((1u64 << 53) as f64)) - 0.5;
        seed[nd * 5 + 2] = u;
    }
    let mut p0 = vec![0.0f64; n_dof];
    apply_g(&seed, &mut p0);
    let mut q0 = p0.clone();
    llt.solve_in_place_with_conj(
        faer::Conj::No,
        faer::MatMut::from_column_major_slice_mut(&mut q0, n_dof, 1),
        par,
        MemStack::new(&mut solve_1_buf),
    );
    let norm0 = dot(&q0, &p0).max(1e-30).sqrt();
    for v in &mut q0 {
        *v /= norm0;
    }
    for v in &mut p0 {
        *v /= norm0;
    }

    let max_steps = 32usize;
    let mut q_basis: Vec<Vec<f64>> = Vec::with_capacity(max_steps);
    let mut p_basis: Vec<Vec<f64>> = Vec::with_capacity(max_steps);
    q_basis.push(q0);
    p_basis.push(p0);

    let mut alpha = Vec::with_capacity(max_steps);
    let mut beta = Vec::with_capacity(max_steps);

    for j in 0..max_steps {
        let mut r = vec![0.0f64; n_dof];
        apply_g(&q_basis[j], &mut r);
        let mut w = r.clone();
        llt.solve_in_place_with_conj(
            faer::Conj::No,
            faer::MatMut::from_column_major_slice_mut(&mut w, n_dof, 1),
            par,
            MemStack::new(&mut solve_1_buf),
        );
        // Rayleigh coefficient alpha_j = <q_j, w>_K = q_j^T r
        let aj = dot(&q_basis[j], &r);
        alpha.push(aj);

        // Two-pass Gram-Schmidt in K-inner product against all previous basis vectors
        for _pass in 0..2 {
            for i in 0..=j {
                let hij = dot(&q_basis[i], &r);
                if hij != 0.0 {
                    for (wk, &qik) in w.iter_mut().zip(&q_basis[i]) {
                        *wk -= hij * qik;
                    }
                    for (rk, &pik) in r.iter_mut().zip(&p_basis[i]) {
                        *rk -= hij * pik;
                    }
                }
            }
        }

        let bj_sq = dot(&w, &r);
        if bj_sq <= 1e-28 || j + 1 == max_steps {
            break;
        }
        let bj = bj_sq.sqrt();
        beta.push(bj);
        for v in &mut w {
            *v /= bj;
        }
        for v in &mut r {
            *v /= bj;
        }
        q_basis.push(w);
        p_basis.push(r);
    }

    let mu_max = largest_tridiagonal_eigenvalue(&alpha, &beta).max(1e-15);
    let lambda_cr = 1.0 / mu_max;
    let status = if lambda_cr > 0.0 && supported_seq_ratio >= input.certified_seq_ratio {
        "pass"
    } else {
        "fail"
    };

    Some(SideA4Result {
        subject: input.subject.clone(),
        status,
        genome: input.genome.clone(),
        genome_sha256: input.genome_sha256.clone(),
        d1_sha256: input.d1_sha256.clone(),
        mesh_max_area_mm2: 0.25,
        n_elem,
        n_node,
        n_bore_nodes: bore_nodes.len(),
        n_grip_nodes: grip_nodes.len(),
        buckling_eigenvalue: lambda_cr,
        buckling_critical_load_n: 260.0 * lambda_cr,
        supported_blade_peak_mpa_per_n: blade_peak,
        supported_hand_peak_mpa_per_n: hand_peak,
        supported_seq_ratio,
        certified_seq_ratio: input.certified_seq_ratio,
        supported_vs_certified_seq_delta: supported_seq_ratio - input.certified_seq_ratio,
    })
}

#[inline]
fn dot(a: &[f64], b: &[f64]) -> f64 {
    let mut s = 0.0f64;
    for (&x, &y) in a.iter().zip(b) {
        s += x * y;
    }
    s
}

/// Largest eigenvalue of symmetric tridiagonal matrix with diagonal `alpha` and off-diagonal `beta`
/// via bisection on Sturm sequence + Rayleigh-quotient power polish.
fn largest_tridiagonal_eigenvalue(alpha: &[f64], beta: &[f64]) -> f64 {
    let m = alpha.len();
    if m == 0 {
        return 0.0;
    }
    if m == 1 {
        return alpha[0];
    }
    // Gershgorin upper bound; lower bound = 0.0 since T is positive semi-definite
    let mut hi = 0.0f64;
    for i in 0..m {
        let left = if i > 0 { beta[i - 1].abs() } else { 0.0 };
        let right = if i < beta.len() { beta[i].abs() } else { 0.0 };
        hi = hi.max(alpha[i] + left + right);
    }
    let mut lo = 0.0f64;
    // Sturm sequence count of eigenvalues > x
    let count_gt = |x: f64| -> usize {
        let mut gt = 0usize;
        let mut d = alpha[0] - x;
        if d > 0.0 {
            gt += 1;
        }
        for i in 1..m {
            let b2 = beta[i - 1] * beta[i - 1];
            let denom = if d.abs() < 1e-30 {
                if d >= 0.0 { 1e-30 } else { -1e-30 }
            } else {
                d
            };
            d = (alpha[i] - x) - b2 / denom;
            if d > 0.0 {
                gt += 1;
            }
        }
        gt
    };
    for _ in 0..80 {
        let mid = 0.5 * (lo + hi);
        if count_gt(mid) >= 1 {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    0.5 * (lo + hi)
}
