//! Native Rust 3D 10-node quadratic tetrahedron (`TET10` / `ElementTetP2`) linear elasticity solver
//! for the 30 mm karambit blade-tip submodel (`jarambit.stored_solid_tip.v1`).
//!
//! Matches `fem_solid/tip_solid.py` and `fem_solid/step_solid.py`:
//! - Extracts the connected 2D triangle component within `R_CUT` (30 mm) of the blade tip
//! - Evaluates local thickness `th(x, y)` from the thickness raster (nearest-valid EDT fill + bilinear)
//! - Optionally applies `NSUB` uniform 1->4 2D triangle midpoint subdivisions
//! - Extrudes into `NL` (4) symmetric layers `z in [-th/2, +th/2]`, splitting each prism into 3 tets
//! - Builds the P2 (`TET10`) 10-node quadratic tetrahedron mesh (4 corners + 6 edge midpoints)
//! - Applies the minimum-norm pure chord-torsion load (`T = 1820 N*mm`) on vertices within `PATCH_mm` (2 mm)
//! - Clamps all corner and edge-midpoint DOFs on the `R_CUT` cut boundary
//! - Solves `K_ff u_f = f_f` via `faer` sparse Cholesky (or 3x3 Block-Jacobi PCG for large systems)
//! - Recovers 3D von Mises stresses at the 4 reference vertices of each `TET10` element and computes
//!   `SF_nodal_avg`, `SF_nodal_max`, and `SF_elem_mean` in the `[4, 15) mm` tip annulus (`d_cut > 3 mm`).

use std::collections::{HashMap, VecDeque};
use faer::dyn_stack::{MemBuffer, MemStack};
use faer::sparse::linalg::cholesky as ch;
use faer::sparse::{SparseColMat, Triplet};

pub const T_NMM: f64 = 1820.0;
pub const E_MPA: f64 = 113_800.0;
pub const NU: f64 = 0.34;
pub const SY20_MPA: f64 = 828.0;

#[derive(Clone, Debug)]
pub struct ThicknessField {
    pub x0: f64,
    pub y0: f64,
    pub g: f64,
    pub nx: usize,
    pub ny: usize,
    /// Row-major `ny * nx` thickness values (`None` or `NaN` outside outline).
    pub th: Vec<Option<f64>>,
}

impl ThicknessField {
    /// Nearest-valid Euclidean fill of `None` cells + bilinear interpolation matching
    /// `scipy.ndimage.distance_transform_edt` + `scipy.ndimage.map_coordinates(..., order=1, mode="nearest")`.
    pub fn prepare_filled(&self) -> FilledThicknessField {
        let nx = self.nx;
        let ny = self.ny;
        let mut filled = vec![0.0f64; ny * nx];
        // For each row y, precompute nearest valid x in that row (or usize::MAX if row has no valid cells)
        let mut row_valid: Vec<Vec<usize>> = Vec::with_capacity(ny);
        let mut non_empty_rows: Vec<usize> = Vec::with_capacity(ny);
        for y in 0..ny {
            let mut vr = Vec::new();
            for x in 0..nx {
                if let Some(v) = self.th[y * nx + x] {
                    if v.is_finite() {
                        filled[y * nx + x] = v;
                        vr.push(x);
                    }
                }
            }
            if !vr.is_empty() {
                non_empty_rows.push(y);
            }
            row_valid.push(vr);
        }

        if !non_empty_rows.is_empty() {
            for y in 0..ny {
                for x in 0..nx {
                    if self.th[y * nx + x].map_or(false, |v| v.is_finite()) {
                        continue;
                    }
                    let mut best_d2 = usize::MAX;
                    let mut best_val = 2.0f64;
                    // Search rows outward from y
                    let pos = non_empty_rows.partition_point(|&ry| ry < y);
                    let mut left = pos;
                    let mut right = pos;
                    loop {
                        let mut progressed = false;
                        if right < non_empty_rows.len() {
                            let ry = non_empty_rows[right];
                            let dy = ry.abs_diff(y);
                            if dy * dy < best_d2 {
                                progressed = true;
                                let vr = &row_valid[ry];
                                let xp = vr.partition_point(|&rx| rx < x);
                                for &cand_x in vr.get(xp).into_iter().chain(xp.checked_sub(1).and_then(|i| vr.get(i))) {
                                    let dx = cand_x.abs_diff(x);
                                    let d2 = dx * dx + dy * dy;
                                    if d2 < best_d2 {
                                        best_d2 = d2;
                                        best_val = filled[ry * nx + cand_x];
                                    }
                                }
                                right += 1;
                            }
                        }
                        if left > 0 {
                            let ry = non_empty_rows[left - 1];
                            let dy = ry.abs_diff(y);
                            if dy * dy < best_d2 {
                                progressed = true;
                                let vr = &row_valid[ry];
                                let xp = vr.partition_point(|&rx| rx < x);
                                for &cand_x in vr.get(xp).into_iter().chain(xp.checked_sub(1).and_then(|i| vr.get(i))) {
                                    let dx = cand_x.abs_diff(x);
                                    let d2 = dx * dx + dy * dy;
                                    if d2 < best_d2 {
                                        best_d2 = d2;
                                        best_val = filled[ry * nx + cand_x];
                                    }
                                }
                                left -= 1;
                            }
                        }
                        if !progressed {
                            break;
                        }
                    }
                    filled[y * nx + x] = best_val;
                }
            }
        }

        FilledThicknessField {
            x0: self.x0,
            y0: self.y0,
            g: self.g,
            nx,
            ny,
            thf: filled,
        }
    }
}

pub struct FilledThicknessField {
    pub x0: f64,
    pub y0: f64,
    pub g: f64,
    pub nx: usize,
    pub ny: usize,
    pub thf: Vec<f64>,
}

impl FilledThicknessField {
    #[inline]
    pub fn sample(&self, x: f64, y: f64) -> f64 {
        if self.nx == 0 || self.ny == 0 {
            return 2.0;
        }
        let gx = ((x - self.x0) / self.g - 0.5).clamp(0.0, (self.nx - 1) as f64);
        let gy = ((y - self.y0) / self.g - 0.5).clamp(0.0, (self.ny - 1) as f64);
        let x0 = gx.floor() as usize;
        let y0 = gy.floor() as usize;
        let x1 = (x0 + 1).min(self.nx - 1);
        let y1 = (y0 + 1).min(self.ny - 1);
        let wx = gx - (x0 as f64);
        let wy = gy - (y0 as f64);
        let v00 = self.thf[y0 * self.nx + x0];
        let v01 = self.thf[y0 * self.nx + x1];
        let v10 = self.thf[y1 * self.nx + x0];
        let v11 = self.thf[y1 * self.nx + x1];
        (1.0 - wy) * ((1.0 - wx) * v00 + wx * v01) + wy * ((1.0 - wx) * v10 + wx * v11)
    }
}

#[derive(Clone, Debug)]
pub struct SolidTipInput {
    pub xy: Vec<(f64, f64)>,
    pub tris: Vec<[usize; 3]>,
    pub tip_xy: (f64, f64),
    pub t_joint: f64,
    pub field: ThicknessField,
    pub r_cut: f64,
    pub nl: usize,
    pub nsub: usize,
    pub patch_mm: f64,
}

#[derive(Clone, Debug)]
pub struct SolidTipPeak {
    pub mpa: f64,
    pub at: [f64; 3],
    pub dist: f64,
}

#[derive(Clone, Debug)]
pub struct SolidTipResult {
    pub patch_mm: f64,
    pub n_tet: usize,
    pub n_dof: usize,
    pub r_cut: f64,
    pub nl: usize,
    pub nsub: usize,
    pub sallow_joint_mpa: f64,
    pub jk2: f64,
    pub nodal_avg_peak: SolidTipPeak,
    pub nodal_max_peak: SolidTipPeak,
    pub elem_mean_peak_mpa: f64,
    pub elem_mean_peak_at: [f64; 3],
    pub sf_solid_nodal_avg: f64,
    pub sf_solid_nodal_max: f64,
    pub sf_solid_elem_mean: f64,
    pub ksp_its: usize,
    pub rel_res: f64,
}

fn tets_of_prism(v: [usize; 6]) -> [[usize; 4]; 3] {
    let mut i0 = 0usize;
    for i in 1..6 {
        if v[i] < v[i0] {
            i0 = i;
        }
    }
    let rot: [usize; 6] = match i0 {
        0 => [0, 1, 2, 3, 4, 5],
        1 => [1, 2, 0, 4, 5, 3],
        2 => [2, 0, 1, 5, 3, 4],
        3 => [3, 5, 4, 0, 2, 1],
        4 => [4, 3, 5, 1, 0, 2],
        _ => [5, 4, 3, 2, 1, 0],
    };
    let w = [v[rot[0]], v[rot[1]], v[rot[2]], v[rot[3]], v[rot[4]], v[rot[5]]];
    if w[1].min(w[5]) < w[2].min(w[4]) {
        [
            [w[0], w[1], w[2], w[5]],
            [w[0], w[1], w[5], w[4]],
            [w[0], w[4], w[5], w[3]],
        ]
    } else {
        [
            [w[0], w[1], w[2], w[4]],
            [w[0], w[4], w[2], w[5]],
            [w[0], w[4], w[5], w[3]],
        ]
    }
}

/// Derivatives dN_p / dL_a (10 x 4) at barycentric coordinates `l = [L0, L1, L2, L3]`.
/// Node ordering:
/// - 0..4: corners 0, 1, 2, 3
/// - 4..10: edges (0,1), (0,2), (0,3), (1,2), (1,3), (2,3)
#[inline]
fn tet10_dn_dl(l: [f64; 4]) -> [[f64; 4]; 10] {
    let mut dn = [[0.0f64; 4]; 10];
    for a in 0..4 {
        dn[a][a] = 4.0 * l[a] - 1.0;
    }
    let edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)];
    for (k, &(i, j)) in edges.iter().enumerate() {
        dn[4 + k][i] = 4.0 * l[j];
        dn[4 + k][j] = 4.0 * l[i];
    }
    dn
}

/// Computes `grad_l` (4 x 3: `[dL_a/dx, dL_a/dy, dL_a/dz]`) and volume `V` for a 4-corner tetrahedron.
#[inline]
fn tet_grad_l(p: [[f64; 3]; 4]) -> Option<([[f64; 3]; 4], f64)> {
    let j11 = p[1][0] - p[0][0];
    let j12 = p[2][0] - p[0][0];
    let j13 = p[3][0] - p[0][0];
    let j21 = p[1][1] - p[0][1];
    let j22 = p[2][1] - p[0][1];
    let j23 = p[3][1] - p[0][1];
    let j31 = p[1][2] - p[0][2];
    let j32 = p[2][2] - p[0][2];
    let j33 = p[3][2] - p[0][2];

    let c11 = j22 * j33 - j23 * j32;
    let c12 = -(j21 * j33 - j23 * j31);
    let c13 = j21 * j32 - j22 * j31;
    let det = j11 * c11 + j12 * c12 + j13 * c13;
    if det <= 1e-14 {
        return None;
    }
    let inv_det = 1.0 / det;
    let c21 = -(j12 * j33 - j13 * j32);
    let c22 = j11 * j33 - j13 * j31;
    let c23 = -(j11 * j32 - j12 * j31);
    let c31 = j12 * j23 - j13 * j22;
    let c32 = -(j11 * j23 - j13 * j21);
    let c33 = j11 * j22 - j12 * j21;

    // grad L_1, grad L_2, grad L_3 are rows of J^{-1} = cols of Cof(J) / det
    let g1 = [c11 * inv_det, c21 * inv_det, c31 * inv_det];
    let g2 = [c12 * inv_det, c22 * inv_det, c32 * inv_det];
    let g3 = [c13 * inv_det, c23 * inv_det, c33 * inv_det];
    let g0 = [-(g1[0] + g2[0] + g3[0]), -(g1[1] + g2[1] + g3[1]), -(g1[2] + g2[2] + g3[2])];
    Some(([g0, g1, g2, g3], det / 6.0))
}

pub fn solve_solid_tet10(input: &SolidTipInput) -> Option<SolidTipResult> {
    let n_xy = input.xy.len();
    let n_tris = input.tris.len();
    if n_xy < 3 || n_tris == 0 || input.nl == 0 {
        return None;
    }

    let tipo = input.tip_xy;
    let tip_norm = tipo.0.hypot(tipo.1).max(1e-9);
    let dvec = (tipo.0 / tip_norm, tipo.1 / tip_norm);
    let nvec = (-dvec.1, dvec.0);

    let cen: Vec<(f64, f64)> = input
        .tris
        .iter()
        .map(|t| {
            (
                (input.xy[t[0]].0 + input.xy[t[1]].0 + input.xy[t[2]].0) / 3.0,
                (input.xy[t[0]].1 + input.xy[t[1]].1 + input.xy[t[2]].1) / 3.0,
            )
        })
        .collect();
    let dc: Vec<f64> = cen.iter().map(|c| (c.0 - tipo.0).hypot(c.1 - tipo.1)).collect();
    let ki: Vec<usize> = (0..n_tris).filter(|&i| dc[i] <= input.r_cut).collect();
    if ki.is_empty() {
        return None;
    }

    // Connected component of kept triangles containing the triangle nearest `tipo`
    let mut vert_to_ki: HashMap<usize, Vec<usize>> = HashMap::new();
    for (local_idx, &tri_idx) in ki.iter().enumerate() {
        for &v in &input.tris[tri_idx] {
            vert_to_ki.entry(v).or_default().push(local_idx);
        }
    }
    let tri_tip_local = (0..ki.len()).min_by(|&a, &b| {
        dc[ki[a]]
            .partial_cmp(&dc[ki[b]])
            .unwrap_or(std::cmp::Ordering::Equal)
    })?;
    let mut visited = vec![false; ki.len()];
    let mut queue = VecDeque::new();
    visited[tri_tip_local] = true;
    queue.push_back(tri_tip_local);
    while let Some(cur) = queue.pop_front() {
        for &v in &input.tris[ki[cur]] {
            if let Some(nbrs) = vert_to_ki.get(&v) {
                for &nxt in nbrs {
                    if !visited[nxt] {
                        visited[nxt] = true;
                        queue.push_back(nxt);
                    }
                }
            }
        }
    }

    let mut keep = vec![false; n_tris];
    for (local_idx, &tri_idx) in ki.iter().enumerate() {
        if visited[local_idx] {
            keep[tri_idx] = true;
        }
    }

    let mut cutmask = vec![false; n_xy];
    for (tri_idx, t) in input.tris.iter().enumerate() {
        if !keep[tri_idx] {
            for &v in t {
                cutmask[v] = true;
            }
        }
    }

    let mut used: Vec<usize> = input
        .tris
        .iter()
        .enumerate()
        .filter(|&(i, _)| keep[i])
        .flat_map(|(_, t)| [t[0], t[1], t[2]])
        .collect();
    used.sort_unstable();
    used.dedup();
    let mut rm = vec![usize::MAX; n_xy];
    for (new_idx, &old_idx) in used.iter().enumerate() {
        rm[old_idx] = new_idx;
    }

    let mut p2d: Vec<(f64, f64)> = used.iter().map(|&i| input.xy[i]).collect();
    let mut t2d: Vec<[usize; 3]> = input
        .tris
        .iter()
        .enumerate()
        .filter(|&(i, _)| keep[i])
        .map(|(_, t)| [rm[t[0]], rm[t[1]], rm[t[2]]])
        .collect();
    let mut cut2d: Vec<bool> = used.iter().map(|&i| cutmask[i]).collect();

    // Uniform 1->4 triangle subdivision
    for _ in 0..input.nsub {
        let mut edges: HashMap<(usize, usize), usize> = HashMap::new();
        let mut nt = Vec::with_capacity(t2d.len() * 4);
        let mut mid = |a: usize, b: usize, p2d: &mut Vec<(f64, f64)>, cut2d: &mut Vec<bool>| -> usize {
            let k = (a.min(b), a.max(b));
            if let Some(&idx) = edges.get(&k) {
                idx
            } else {
                let idx = p2d.len();
                p2d.push(((p2d[a].0 + p2d[b].0) * 0.5, (p2d[a].1 + p2d[b].1) * 0.5));
                let is_cut = cut2d[a] && cut2d[b];
                cut2d.push(is_cut);
                edges.insert(k, idx);
                idx
            }
        };
        for &[a, b, c] in &t2d {
            let ab = mid(a, b, &mut p2d, &mut cut2d);
            let bc = mid(b, c, &mut p2d, &mut cut2d);
            let ca = mid(c, a, &mut p2d, &mut cut2d);
            nt.push([a, ab, ca]);
            nt.push([ab, b, bc]);
            nt.push([ca, bc, c]);
            nt.push([ab, bc, ca]);
        }
        t2d = nt;
    }

    let dn: Vec<f64> = p2d.iter().map(|p| (p.0 - tipo.0).hypot(p.1 - tipo.1)).collect();
    for i in 0..cut2d.len() {
        cut2d[i] = cut2d[i] && dn[i] > (input.r_cut - 4.0);
    }
    if !cut2d.iter().any(|&c| c) {
        // Fallback if R_CUT encompasses the entire mesh: clamp nodes furthest from tip
        let max_dn = dn.iter().copied().fold(0.0f64, f64::max);
        for i in 0..cut2d.len() {
            if dn[i] >= max_dn - 2.0 {
                cut2d[i] = true;
            }
        }
    }

    let filled_field = input.field.prepare_filled();
    let hh: Vec<f64> = p2d
        .iter()
        .map(|&(x, y)| filled_field.sample(x, y).max(0.15))
        .collect();
    let n2 = p2d.len();
    let nl = input.nl;
    let n_vert = (nl + 1) * n2;
    let mut pts = Vec::with_capacity(n_vert);
    for k in 0..=nl {
        let z_frac = (k as f64) / (nl as f64) - 0.5;
        for i in 0..n2 {
            pts.push([p2d[i].0, p2d[i].1, z_frac * hh[i]]);
        }
    }

    let mut tets = Vec::with_capacity(nl * t2d.len() * 3);
    for k in 0..nl {
        let off0 = k * n2;
        let off1 = (k + 1) * n2;
        for &[a, b, c] in &t2d {
            let prism = [off0 + a, off0 + b, off0 + c, off1 + a, off1 + b, off1 + c];
            for mut tet in tets_of_prism(prism) {
                let p0 = pts[tet[0]];
                let p1 = pts[tet[1]];
                let p2 = pts[tet[2]];
                let p3 = pts[tet[3]];
                let ux = p1[0] - p0[0];
                let uy = p1[1] - p0[1];
                let uz = p1[2] - p0[2];
                let vx = p2[0] - p0[0];
                let vy = p2[1] - p0[1];
                let vz = p2[2] - p0[2];
                let wx = p3[0] - p0[0];
                let wy = p3[1] - p0[1];
                let wz = p3[2] - p0[2];
                let vol6 = (uy * vz - uz * vy) * wx + (uz * vx - ux * vz) * wy + (ux * vy - uy * vx) * wz;
                if vol6 < 0.0 {
                    tet.swap(1, 2);
                }
                tets.push(tet);
            }
        }
    }

    // Build TET10 edge table
    let edge_pairs = [(0usize, 1usize), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)];
    let mut edge_map: HashMap<(usize, usize), usize> = HashMap::with_capacity(tets.len() * 2);
    let mut edges: Vec<(usize, usize)> = Vec::with_capacity(tets.len() * 2);
    let mut tet10_nodes: Vec<[usize; 10]> = Vec::with_capacity(tets.len());

    for tet in &tets {
        let mut nodes = [0usize; 10];
        nodes[0] = tet[0];
        nodes[1] = tet[1];
        nodes[2] = tet[2];
        nodes[3] = tet[3];
        for (k, &(i, j)) in edge_pairs.iter().enumerate() {
            let u = tet[i].min(tet[j]);
            let v = tet[i].max(tet[j]);
            let eid = *edge_map.entry((u, v)).or_insert_with(|| {
                let id = edges.len();
                edges.push((u, v));
                id
            });
            nodes[4 + k] = n_vert + eid;
        }
        tet10_nodes.push(nodes);
    }

    let n_nodes_p2 = n_vert + edges.len();
    let n_dof = 3 * n_nodes_p2;

    // Clamped P2 nodes
    let mut fixed_node = vec![false; n_nodes_p2];
    for v in 0..n_vert {
        if cut2d[v % n2] {
            fixed_node[v] = true;
        }
    }
    for (eid, &(u, v)) in edges.iter().enumerate() {
        if fixed_node[u] && fixed_node[v] {
            fixed_node[n_vert + eid] = true;
        }
    }

    let mut dof_map = vec![-1isize; n_dof];
    let mut n_free = 0usize;
    for nd in 0..n_nodes_p2 {
        if !fixed_node[nd] {
            for c in 0..3 {
                dof_map[3 * nd + c] = n_free as isize;
                n_free += 1;
            }
        }
    }
    if n_free == 0 {
        return None;
    }

    // Load vector: pure chord torque T_NMM on vertices within patch_mm of tipo
    let pat: Vec<usize> = (0..n_vert)
        .filter(|&v| (pts[v][0] - tipo.0).hypot(pts[v][1] - tipo.1) <= input.patch_mm)
        .collect();
    if pat.len() < 3 {
        return None;
    }
    let mut mean_x = 0.0f64;
    let mut mean_y = 0.0f64;
    for &v in &pat {
        mean_x += pts[v][0];
        mean_y += pts[v][1];
    }
    mean_x /= pat.len() as f64;
    mean_y /= pat.len() as f64;

    let mut s_vec = Vec::with_capacity(pat.len());
    let mut q_vec = Vec::with_capacity(pat.len());
    let mut aat = [[0.0f64; 3]; 3];
    for &v in &pat {
        let rx = pts[v][0] - mean_x;
        let ry = pts[v][1] - mean_y;
        let s = rx * nvec.0 + ry * nvec.1;
        let q = rx * dvec.0 + ry * dvec.1;
        s_vec.push(s);
        q_vec.push(q);
        let col = [1.0, s, q];
        for r in 0..3 {
            for c in 0..3 {
                aat[r][c] += col[r] * col[c];
            }
        }
    }
    let lam_rhs = solve_3x3(aat, [0.0, T_NMM, 0.0])?;
    let mut f_free = vec![0.0f64; n_free];
    for (idx, &v) in pat.iter().enumerate() {
        let fz = lam_rhs[0] + lam_rhs[1] * s_vec[idx] + lam_rhs[2] * q_vec[idx];
        let gdof = dof_map[3 * v + 2];
        if gdof >= 0 {
            f_free[gdof as usize] += fz;
        }
    }

    // Precompute reference 4-point degree-2 quadrature weights W^{(p, r)}_{ab} = (1/4) sum_q dN_p/dL_a(q) dN_r/dL_b(q)
    let alpha = (5.0 + 3.0 * 5.0f64.sqrt()) / 20.0;
    let beta = (5.0 - 5.0f64.sqrt()) / 20.0;
    let q_pts = [
        [alpha, beta, beta, beta],
        [beta, alpha, beta, beta],
        [beta, beta, alpha, beta],
        [beta, beta, beta, alpha],
    ];
    let q_dn: [[[f64; 4]; 10]; 4] = std::array::from_fn(|q| tet10_dn_dl(q_pts[q]));
    let mut w_ref = [[[[0.0f64; 4]; 4]; 10]; 10];
    for p in 0..10 {
        for r in 0..=p {
            for q in 0..4 {
                for a in 0..4 {
                    for b in 0..4 {
                        w_ref[p][r][a][b] += 0.25 * q_dn[q][p][a] * q_dn[q][r][b];
                    }
                }
            }
        }
    }

    let lam = E_MPA * NU / ((1.0 + NU) * (1.0 - 2.0 * NU));
    let mu = E_MPA / (2.0 * (1.0 + NU));

    // Assemble lower-triangle triplets of K_ff
    let mut triplets: Vec<Triplet<usize, usize, f64>> = Vec::with_capacity(tets.len() * 180);
    let mut dmax = vec![0.0f64; n_free];

    for nodes in &tet10_nodes {
        let p_tet = [pts[nodes[0]], pts[nodes[1]], pts[nodes[2]], pts[nodes[3]]];
        let Some((grad_l, vol)) = tet_grad_l(p_tet) else {
            continue;
        };
        for p in 0..10 {
            let gp = [
                dof_map[3 * nodes[p]],
                dof_map[3 * nodes[p] + 1],
                dof_map[3 * nodes[p] + 2],
            ];
            if gp[0] < 0 {
                continue;
            }
            for r in 0..=p {
                let gr = [
                    dof_map[3 * nodes[r]],
                    dof_map[3 * nodes[r] + 1],
                    dof_map[3 * nodes[r] + 2],
                ];
                if gr[0] < 0 {
                    continue;
                }
                // M_{ij} = vol * sum_{a,b} grad_l[a][i] * w_ref[p][r][a][b] * grad_l[b][j]
                let mut tmp = [[0.0f64; 3]; 4];
                for a in 0..4 {
                    for j in 0..3 {
                        tmp[a][j] = w_ref[p][r][a][0] * grad_l[0][j]
                            + w_ref[p][r][a][1] * grad_l[1][j]
                            + w_ref[p][r][a][2] * grad_l[2][j]
                            + w_ref[p][r][a][3] * grad_l[3][j];
                    }
                }
                let mut m_blk = [[0.0f64; 3]; 3];
                for i in 0..3 {
                    for j in 0..3 {
                        m_blk[i][j] = vol
                            * (grad_l[0][i] * tmp[0][j]
                                + grad_l[1][i] * tmp[1][j]
                                + grad_l[2][i] * tmp[2][j]
                                + grad_l[3][i] * tmp[3][j]);
                    }
                }
                let tr_m = m_blk[0][0] + m_blk[1][1] + m_blk[2][2];
                for i in 0..3 {
                    let j_end = if p == r { i + 1 } else { 3 };
                    for j in 0..j_end {
                        let mut kij = lam * m_blk[i][j] + mu * m_blk[j][i];
                        if i == j {
                            kij += mu * tr_m;
                        }
                        let row = (gp[i] as usize).max(gr[j] as usize);
                        let col = (gp[i] as usize).min(gr[j] as usize);
                        if row == col {
                            dmax[row] += kij;
                        }
                        triplets.push(Triplet::new(row, col, kij));
                    }
                }
            }
        }
    }

    let k_mat = SparseColMat::<usize, f64>::try_new_from_triplets(n_free, n_free, &triplets).ok()?;
    drop(triplets);

    // Solve K_ff * u_free = f_free using faer supernodal Cholesky if small enough, else Block-Jacobi PCG
    let (u_free, ksp_its, rel_res) = solve_spd_system(&k_mat, &dmax, &f_free)?;

    let mut u_full = vec![0.0f64; n_dof];
    for (d, &g) in dof_map.iter().enumerate() {
        if g >= 0 {
            u_full[d] = u_free[g as usize];
        }
    }

    // Recover 3D von Mises stresses at the 4 corner vertices of each TET10 element
    let corner_l = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ];
    let corner_dn: [[[f64; 4]; 10]; 4] = std::array::from_fn(|c| tet10_dn_dl(corner_l[c]));

    let mut acc = vec![0.0f64; n_vert];
    let mut cnt = vec![0usize; n_vert];
    let mut mx = vec![0.0f64; n_vert];
    let mut elem_mean_peak_mpa = 0.0f64;
    let mut elem_mean_peak_at = [0.0f64; 3];

    for nodes in &tet10_nodes {
        let p_tet = [pts[nodes[0]], pts[nodes[1]], pts[nodes[2]], pts[nodes[3]]];
        let Some((grad_l, _)) = tet_grad_l(p_tet) else {
            continue;
        };
        let mut vm_sum = 0.0f64;
        for c_idx in 0..4 {
            // du_i / dx_j at corner c_idx
            let mut dudx = [[0.0f64; 3]; 3];
            for p in 0..10 {
                let dn_l = &corner_dn[c_idx][p];
                let gx = dn_l[0] * grad_l[0][0]
                    + dn_l[1] * grad_l[1][0]
                    + dn_l[2] * grad_l[2][0]
                    + dn_l[3] * grad_l[3][0];
                let gy = dn_l[0] * grad_l[0][1]
                    + dn_l[1] * grad_l[1][1]
                    + dn_l[2] * grad_l[2][1]
                    + dn_l[3] * grad_l[3][1];
                let gz = dn_l[0] * grad_l[0][2]
                    + dn_l[1] * grad_l[1][2]
                    + dn_l[2] * grad_l[2][2]
                    + dn_l[3] * grad_l[3][2];
                let ux = u_full[3 * nodes[p]];
                let uy = u_full[3 * nodes[p] + 1];
                let uz = u_full[3 * nodes[p] + 2];
                dudx[0][0] += ux * gx;
                dudx[0][1] += ux * gy;
                dudx[0][2] += ux * gz;
                dudx[1][0] += uy * gx;
                dudx[1][1] += uy * gy;
                dudx[1][2] += uy * gz;
                dudx[2][0] += uz * gx;
                dudx[2][1] += uz * gy;
                dudx[2][2] += uz * gz;
            }
            let exx = dudx[0][0];
            let eyy = dudx[1][1];
            let ezz = dudx[2][2];
            let exy = 0.5 * (dudx[0][1] + dudx[1][0]);
            let eyz = 0.5 * (dudx[1][2] + dudx[2][1]);
            let exz = 0.5 * (dudx[0][2] + dudx[2][0]);
            let tr = exx + eyy + ezz;
            let sxx = 2.0 * mu * exx + lam * tr;
            let syy = 2.0 * mu * eyy + lam * tr;
            let szz = 2.0 * mu * ezz + lam * tr;
            let sxy = 2.0 * mu * exy;
            let syz = 2.0 * mu * eyz;
            let sxz = 2.0 * mu * exz;
            let vm = (0.5 * ((sxx - syy).powi(2) + (syy - szz).powi(2) + (szz - sxx).powi(2))
                + 3.0 * (sxy * sxy + syz * syz + sxz * sxz))
                .max(0.0)
                .sqrt();
            let v_corner = nodes[c_idx];
            acc[v_corner] += vm;
            cnt[v_corner] += 1;
            mx[v_corner] = mx[v_corner].max(vm);
            vm_sum += vm;
        }
        let vm_mean = vm_sum * 0.25;
        let cx = 0.25 * (p_tet[0][0] + p_tet[1][0] + p_tet[2][0] + p_tet[3][0]);
        let cy = 0.25 * (p_tet[0][1] + p_tet[1][1] + p_tet[2][1] + p_tet[3][1]);
        let cz = 0.25 * (p_tet[0][2] + p_tet[1][2] + p_tet[2][2] + p_tet[3][2]);
        let dcc = (cx - tipo.0).hypot(cy - tipo.1);
        if (4.0..15.0).contains(&dcc) && vm_mean > elem_mean_peak_mpa {
            elem_mean_peak_mpa = vm_mean;
            elem_mean_peak_at = [(cx * 100.0).round() / 100.0, (cy * 100.0).round() / 100.0, (cz * 100.0).round() / 100.0];
        }
    }

    let cutxy: Vec<(f64, f64)> = (0..n2).filter(|&i| cut2d[i]).map(|i| p2d[i]).collect();
    let mut best_avg_idx = 0usize;
    let mut best_avg_val = 0.0f64;
    let mut best_max_idx = 0usize;
    let mut best_max_val = 0.0f64;

    for v in 0..n_vert {
        let dv = (pts[v][0] - tipo.0).hypot(pts[v][1] - tipo.1);
        if !(4.0..15.0).contains(&dv) {
            continue;
        }
        let dcut = cutxy
            .iter()
            .map(|&(cx, cy)| (pts[v][0] - cx).hypot(pts[v][1] - cy))
            .fold(f64::INFINITY, f64::min);
        if dcut <= 3.0 {
            continue;
        }
        let avg_v = acc[v] / (cnt[v].max(1) as f64);
        if avg_v > best_avg_val {
            best_avg_val = avg_v;
            best_avg_idx = v;
        }
        if mx[v] > best_max_val {
            best_max_val = mx[v];
            best_max_idx = v;
        }
    }

    let tj = input.t_joint.max(0.2);
    let jk2 = ((tj - 0.1) / tj).powi(2) * (1.0 - 0.0011 * 80.0);
    let sallow = SY20_MPA * jk2;

    let avg_mpa_round = (best_avg_val * 10.0).round() / 10.0;
    let max_mpa_round = (best_max_val * 10.0).round() / 10.0;
    let elem_mpa_round = (elem_mean_peak_mpa * 10.0).round() / 10.0;

    let round2 = |v: f64| (v * 100.0).round() / 100.0;
    let round3 = |v: f64| (v * 1000.0).round() / 1000.0;

    let nodal_avg_peak = SolidTipPeak {
        mpa: avg_mpa_round,
        at: [
            round2(pts[best_avg_idx][0]),
            round2(pts[best_avg_idx][1]),
            round2(pts[best_avg_idx][2]),
        ],
        dist: round2((pts[best_avg_idx][0] - tipo.0).hypot(pts[best_avg_idx][1] - tipo.1)),
    };
    let nodal_max_peak = SolidTipPeak {
        mpa: max_mpa_round,
        at: [
            round2(pts[best_max_idx][0]),
            round2(pts[best_max_idx][1]),
            round2(pts[best_max_idx][2]),
        ],
        dist: round2((pts[best_max_idx][0] - tipo.0).hypot(pts[best_max_idx][1] - tipo.1)),
    };

    Some(SolidTipResult {
        patch_mm: input.patch_mm,
        n_tet: tets.len(),
        n_dof,
        r_cut: input.r_cut,
        nl,
        nsub: input.nsub,
        sallow_joint_mpa: (sallow * 10.0).round() / 10.0,
        jk2: (jk2 * 10000.0).round() / 10000.0,
        nodal_avg_peak,
        nodal_max_peak,
        elem_mean_peak_mpa: elem_mpa_round,
        elem_mean_peak_at,
        sf_solid_nodal_avg: round3(sallow / avg_mpa_round.max(1e-9)),
        sf_solid_nodal_max: round3(sallow / max_mpa_round.max(1e-9)),
        sf_solid_elem_mean: round3(sallow / elem_mean_peak_mpa.max(1e-9)),
        ksp_its,
        rel_res,
    })
}

fn solve_3x3(a: [[f64; 3]; 3], b: [f64; 3]) -> Option<[f64; 3]> {
    let mut m = [
        [a[0][0], a[0][1], a[0][2], b[0]],
        [a[1][0], a[1][1], a[1][2], b[1]],
        [a[2][0], a[2][1], a[2][2], b[2]],
    ];
    for i in 0..3 {
        let mut piv = i;
        for r in (i + 1)..3 {
            if m[r][i].abs() > m[piv][i].abs() {
                piv = r;
            }
        }
        if m[piv][i].abs() < 1e-14 {
            return None;
        }
        m.swap(i, piv);
        let div = m[i][i];
        for c in i..4 {
            m[i][c] /= div;
        }
        for r in 0..3 {
            if r != i {
                let f = m[r][i];
                for c in i..4 {
                    m[r][c] -= f * m[i][c];
                }
            }
        }
    }
    Some([m[0][3], m[1][3], m[2][3]])
}

fn solve_spd_system(
    k_mat: &SparseColMat<usize, f64>,
    dmax: &[f64],
    f_free: &[f64],
) -> Option<(Vec<f64>, usize, f64)> {
    let n = f_free.len();
    // Try direct faer sparse Cholesky first (very fast on thin 4-layer extruded meshes)
    if let Ok(sym) = ch::factorize_symbolic_cholesky(
        k_mat.symbolic(),
        faer::Side::Lower,
        Default::default(),
        Default::default(),
    ) {
        let tol = (dmax.iter().fold(0.0f64, |m, d| m.max(d.abs())) * 1e-13).max(1e-300);
        let reg = faer::linalg::cholesky::llt::factor::LltRegularization {
            dynamic_regularization_delta: 1e300,
            dynamic_regularization_epsilon: tol,
        };
        let par = faer::Par::Seq;
        if let Ok(mut buf) = MemBuffer::try_new(sym.factorize_numeric_llt_scratch::<f64>(par, Default::default())) {
            let mut l_vals = vec![0.0f64; sym.len_val()];
            if sym
                .factorize_numeric_llt::<f64>(
                    &mut l_vals,
                    k_mat.as_ref(),
                    faer::Side::Lower,
                    reg,
                    par,
                    MemStack::new(&mut buf),
                    Default::default(),
                )
                .is_ok()
            {
                let llt = ch::LltRef::new(&sym, &l_vals);
                let mut u = f_free.to_vec();
                let mut solve_buf = MemBuffer::new(sym.solve_in_place_scratch::<f64>(1, par));
                llt.solve_in_place_with_conj(
                    faer::Conj::No,
                    faer::MatMut::from_column_major_slice_mut(&mut u, n, 1),
                    par,
                    MemStack::new(&mut solve_buf),
                );
                let mut r = f_free.to_vec();
                sym_spmv_sub(k_mat, &u, &mut r);
                let rel_res = norm2(&r) / norm2(f_free).max(1e-30);
                return Some((u, 1, rel_res));
            }
        }
    }

    // Fallback: Jacobi-preconditioned Conjugate Gradient
    let mut inv_diag = vec![1.0f64; n];
    for (i, &d) in dmax.iter().enumerate() {
        inv_diag[i] = if d.abs() > 1e-15 { 1.0 / d } else { 1.0 };
    }
    let mut u = vec![0.0f64; n];
    let mut r = f_free.to_vec();
    let mut z: Vec<f64> = r.iter().zip(&inv_diag).map(|(&ri, &di)| ri * di).collect();
    let mut p = z.clone();
    let mut ap = vec![0.0f64; n];
    let mut rz = dot(&r, &z);
    let rhs_norm = norm2(f_free).max(1e-30);
    let mut its = 0usize;
    for it in 1..=4000 {
        its = it;
        sym_spmv(k_mat, &p, &mut ap);
        let pap = dot(&p, &ap).max(1e-30);
        let alpha = rz / pap;
        for i in 0..n {
            u[i] += alpha * p[i];
            r[i] -= alpha * ap[i];
        }
        let rel = norm2(&r) / rhs_norm;
        if rel <= 1e-8 {
            return Some((u, its, rel));
        }
        for i in 0..n {
            z[i] = r[i] * inv_diag[i];
        }
        let rz_new = dot(&r, &z);
        let beta = rz_new / rz.max(1e-30);
        for i in 0..n {
            p[i] = z[i] + beta * p[i];
        }
        rz = rz_new;
    }
    let rel = norm2(&r) / rhs_norm;
    Some((u, its, rel))
}

fn sym_spmv(a: &SparseColMat<usize, f64>, x: &[f64], y: &mut [f64]) {
    y.fill(0.0);
    let cp = a.symbolic().col_ptr();
    let ri = a.symbolic().row_idx();
    let val = a.val();
    for j in 0..x.len() {
        let xj = x[j];
        for idx in cp[j]..cp[j + 1] {
            let i = ri[idx];
            let v = val[idx];
            y[i] += v * xj;
            if i != j {
                y[j] += v * x[i];
            }
        }
    }
}

fn sym_spmv_sub(a: &SparseColMat<usize, f64>, x: &[f64], r: &mut [f64]) {
    let cp = a.symbolic().col_ptr();
    let ri = a.symbolic().row_idx();
    let val = a.val();
    for j in 0..x.len() {
        let xj = x[j];
        for idx in cp[j]..cp[j + 1] {
            let i = ri[idx];
            let v = val[idx];
            r[i] -= v * xj;
            if i != j {
                r[j] -= v * x[i];
            }
        }
    }
}

#[inline]
fn dot(a: &[f64], b: &[f64]) -> f64 {
    let mut s = 0.0f64;
    for (&x, &y) in a.iter().zip(b) {
        s += x * y;
    }
    s
}

#[inline]
fn norm2(a: &[f64]) -> f64 {
    dot(a, a).sqrt()
}
