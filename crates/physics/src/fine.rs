//! Detailed plate model (the "converged plate"): quality-constrained Delaunay mesh (spade,
//! min angle 25 deg, max-area refinement) on the full outline + ring hole, numerically-built
//! Batoz DKT for bending (dofs w, w_x, w_y) and CST for membrane, RCM ordering and a skyline
//! Cholesky. Units mm / N / MPa.
//!
//! Why this exists (2026-10-11, Jepson): the coarse `fem` plate meshes only the decimated
//! boundary (no interior nodes, sliver ears) and overstated lateral capacity ~2.3x against a
//! refined plate on the wave5 winner. This module is mesh-convergent (see
//! `docs/CALIBRATION.md` and `jarambit fem-verify`) and is the strength level the calibrated
//! search uses. Load cases follow `ops/wave_figures/make_wave_figs.py`:
//!   lateral: ring hole clamped, out-of-plane tip load on a 2 mm patch;
//!   pry:     ring hole clamped, in-plane tip load perpendicular to the ricasso->tip chord (T6);
//!   twist:   ring hole clamped, unit moment about the chord axis at the tip (proxy, no floor);
//!   ring:    ricasso band seated, uniform -y traction on the ring hole (T6, consistent load).
//! In-plane cases use quadratic T6 membrane elements on the same mesh; peaks are nodal averages.
//! Peak stress excludes element centroids within 4 mm of the tip (St-Venant zone of the patch).
//! Blade elements (centroid y >= -0.5) carry the serration section-loss factor, as the beam
//! surrogate and the wave plates do.
use jarambit_genotype::limits;
use jarambit_phenotype::{dist_to_poly, point_in_poly, Phenotype};
use spade::{AngleLimit, ConstrainedDelaunayTriangulation, Point2, RefinementParameters, Triangulation};
use super::Material;

pub type P2 = (f64, f64);
pub const NU: f64 = 0.34;
/// Search mesh: max triangle area (mm^2) used inside the calibrated search.
pub const SEARCH_AREA: f64 = 2.0;
/// Verification mesh: max triangle area (mm^2) for reported winners (finest convergence level).
pub const VERIFY_AREA: f64 = 0.25;
pub const TIP_PATCH_MM: f64 = 2.0;
pub const TIP_EXCL_MM: f64 = 4.0;

#[derive(Clone, Debug)]
pub struct Mesh { pub xy: Vec<P2>, pub tris: Vec<[usize; 3]>, pub on_outer: Vec<bool>, pub on_hole: Vec<bool> }

/// Drop near-duplicate points; split edges longer than `hmax`.
pub fn resample(poly: &[P2], hmax: f64) -> Vec<P2> { resample_m(poly, hmax, 1) }

/// As `resample`, and split every edge into at least `m` pieces (refines small features with level).
pub fn resample_m(poly: &[P2], hmax: f64, m: usize) -> Vec<P2> {
    let mut clean: Vec<P2> = Vec::with_capacity(poly.len());
    for &q in poly {
        if clean.last().map_or(true, |l: &P2| (l.0 - q.0).hypot(l.1 - q.1) > 1e-3) { clean.push(q); }
    }
    while clean.len() > 2 {
        let (a, b) = (clean[0], *clean.last().unwrap());
        if (a.0 - b.0).hypot(a.1 - b.1) <= 1e-3 { clean.pop(); } else { break; }
    }
    let n = clean.len();
    let mut out = Vec::with_capacity(n * 2);
    for i in 0..n {
        let (a, b) = (clean[i], clean[(i + 1) % n]);
        let l = (b.0 - a.0).hypot(b.1 - a.1);
        let k = ((l / hmax).ceil() as usize).max(m).max(1);
        for j in 0..k { let t = j as f64 / k as f64; out.push((a.0 + t * (b.0 - a.0), a.1 + t * (b.1 - a.1))); }
    }
    out
}

/// Quality CDT mesh of `outer` minus `holes`. Boundary segments are split to <= ~1.5 sqrt(max_area).
pub fn mesh_domain(outer: &[P2], holes: &[Vec<P2>], max_area: f64) -> Option<Mesh> { mesh_domain_pts(outer, holes, &[], max_area) }

/// As `mesh_domain`, plus fixed interior points (load points in the verification problems).
pub fn mesh_domain_pts(outer: &[P2], holes: &[Vec<P2>], pts: &[P2], max_area: f64) -> Option<Mesh> {
    let hb = (1.5 * max_area.sqrt()).max(0.05);
    // small boundary features (fillets, serration gullets) refine with the level too
    let m = (1.0 / max_area.sqrt()).ceil().max(1.0) as usize;
    let o = resample_m(outer, hb, m);
    let hs: Vec<Vec<P2>> = holes.iter().map(|h| resample_m(h, hb, m)).collect();
    let mut cdt: ConstrainedDelaunayTriangulation<Point2<f64>> = ConstrainedDelaunayTriangulation::new();
    for ring in std::iter::once(&o).chain(hs.iter()) {
        let mut hv = Vec::with_capacity(ring.len());
        for &(x, y) in ring { hv.push(cdt.insert(Point2::new(x, y)).ok()?); }
        for i in 0..hv.len() {
            let (a, b) = (hv[i], hv[(i + 1) % hv.len()]);
            if a == b { continue; }
            if !cdt.can_add_constraint(a, b) { return None; }
            cdt.add_constraint(a, b);
        }
    }
    for &(x, y) in pts { cdt.insert(Point2::new(x, y)).ok()?; }
    let params = RefinementParameters::<f64>::new()
        .with_max_allowed_area(max_area)
        .with_angle_limit(AngleLimit::from_deg(25.0))
        .with_max_additional_vertices(400_000)
        .exclude_outer_faces(true);
    let res = cdt.refine(params);
    let excluded: std::collections::HashSet<usize> = res.excluded_faces.iter().map(|f| f.index()).collect();
    let mut idx = vec![usize::MAX; cdt.num_vertices()];
    let mut xy = Vec::new();
    let mut tris = Vec::new();
    for f in cdt.inner_faces() {
        if excluded.contains(&f.fix().index()) { continue; }
        let vs = f.vertices();
        let p: Vec<P2> = vs.iter().map(|v| { let q = v.position(); (q.x, q.y) }).collect();
        let c = ((p[0].0 + p[1].0 + p[2].0) / 3.0, (p[0].1 + p[1].1 + p[2].1) / 3.0);
        if !point_in_poly(c, &o) || hs.iter().any(|h| point_in_poly(c, h)) { continue; }
        let mut t = [0usize; 3];
        for (k, v) in vs.iter().enumerate() {
            let vi = v.fix().index();
            if idx[vi] == usize::MAX { idx[vi] = xy.len(); xy.push(p[k]); }
            t[k] = idx[vi];
        }
        let a2 = (p[1].0 - p[0].0) * (p[2].1 - p[0].1) - (p[2].0 - p[0].0) * (p[1].1 - p[0].1);
        if a2.abs() < 1e-12 { continue; }
        if a2 < 0.0 { t.swap(1, 2); }
        tris.push(t);
    }
    if tris.is_empty() { return None; }
    let tol = 1e-6;
    let on_outer = xy.iter().map(|&q| dist_to_poly(q, &o) < tol).collect();
    let on_hole = xy.iter().map(|&q| hs.iter().any(|h| dist_to_poly(q, h) < tol)).collect();
    Some(Mesh { xy, tris, on_outer, on_hole })
}

// ---------------- elements ----------------
pub fn c_plane(e: f64, nu: f64) -> [[f64; 3]; 3] {
    let k = e / (1.0 - nu * nu);
    [[k, k * nu, 0.0], [k * nu, k, 0.0], [0.0, 0.0, k * (1.0 - nu) / 2.0]]
}

fn a2_of(xs: &[f64; 3], ys: &[f64; 3]) -> f64 { (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0]) }

/// CST strain-displacement (3x6), dofs (u0,v0,u1,v1,u2,v2).
fn cst_b(xs: &[f64; 3], ys: &[f64; 3], a2: f64) -> [[f64; 6]; 3] {
    let mut b = [[0.0; 6]; 3];
    for j in 0..3 {
        let nx = (ys[(j + 1) % 3] - ys[(j + 2) % 3]) / a2;
        let ny = (xs[(j + 2) % 3] - xs[(j + 1) % 3]) / a2;
        b[0][2 * j] = nx; b[1][2 * j + 1] = ny; b[2][2 * j] = ny; b[2][2 * j + 1] = nx;
    }
    b
}

/// Batoz DKT built from its definition: quadratic rotation fields at 3 corners + 3 midsides,
/// Kirchhoff at the midsides (cubic w along the edge, linear normal slope). Rows: beta_x at the
/// 6 nodes, then beta_y. Dofs per corner (w, w_x, w_y).
fn dkt_t(xs: &[f64; 3], ys: &[f64; 3]) -> [[f64; 9]; 12] {
    let mut t = [[0.0; 9]; 12];
    for i in 0..3 { t[i][3 * i + 1] = 1.0; t[6 + i][3 * i + 2] = 1.0; }
    for (m, (i, j)) in [(3usize, (1usize, 2usize)), (4, (2, 0)), (5, (0, 1))] {
        let (dx, dy) = (xs[j] - xs[i], ys[j] - ys[i]);
        let l = dx.hypot(dy);
        let (c, s) = (dx / l, dy / l);
        let mut ws = [0.0; 9];
        let mut wn = [0.0; 9];
        ws[3 * i] = -1.5 / l; ws[3 * j] = 1.5 / l;
        for k in [i, j] {
            ws[3 * k + 1] += -0.25 * c; ws[3 * k + 2] += -0.25 * s;
            wn[3 * k + 1] += -0.5 * s; wn[3 * k + 2] += 0.5 * c;
        }
        for q in 0..9 { t[m][q] = c * ws[q] - s * wn[q]; t[6 + m][q] = s * ws[q] + c * wn[q]; }
    }
    t
}

fn dkt_b(xs: &[f64; 3], ys: &[f64; 3], a2: f64, t: &[[f64; 9]; 12], l: [f64; 3]) -> [[f64; 9]; 3] {
    let bq: [f64; 3] = std::array::from_fn(|i| (ys[(i + 1) % 3] - ys[(i + 2) % 3]) / a2);
    let cq: [f64; 3] = std::array::from_fn(|i| (xs[(i + 2) % 3] - xs[(i + 1) % 3]) / a2);
    let dn = |d: &[f64; 3]| -> [f64; 6] {
        [(4.0 * l[0] - 1.0) * d[0], (4.0 * l[1] - 1.0) * d[1], (4.0 * l[2] - 1.0) * d[2],
         4.0 * (l[1] * d[2] + l[2] * d[1]), 4.0 * (l[2] * d[0] + l[0] * d[2]), 4.0 * (l[0] * d[1] + l[1] * d[0])]
    };
    let (nx, ny) = (dn(&bq), dn(&cq));
    let mut b = [[0.0; 9]; 3];
    for q in 0..9 {
        let (mut bx_x, mut by_y, mut bx_y, mut by_x) = (0.0, 0.0, 0.0, 0.0);
        for k in 0..6 {
            bx_x += nx[k] * t[k][q]; by_y += ny[k] * t[6 + k][q];
            bx_y += ny[k] * t[k][q]; by_x += nx[k] * t[6 + k][q];
        }
        b[0][q] = bx_x; b[1][q] = by_y; b[2][q] = bx_y + by_x;
    }
    b
}

const GP: [[f64; 3]; 3] = [[2.0 / 3.0, 1.0 / 6.0, 1.0 / 6.0], [1.0 / 6.0, 2.0 / 3.0, 1.0 / 6.0], [1.0 / 6.0, 1.0 / 6.0, 2.0 / 3.0]];

fn btcb<const M: usize>(b: &[[f64; M]; 3], c: &[[f64; 3]; 3], s: f64, k: &mut [[f64; M]; M]) {
    let mut cb = [[0.0; M]; 3];
    for i in 0..3 { for j in 0..M { cb[i][j] = c[i][0] * b[0][j] + c[i][1] * b[1][j] + c[i][2] * b[2][j]; } }
    for i in 0..M { for j in 0..M { k[i][j] += s * (b[0][i] * cb[0][j] + b[1][i] * cb[1][j] + b[2][i] * cb[2][j]); } }
}

/// Linear field through the 3 Gauss points (L = 2/3, 1/6, 1/6 ...) evaluated at the corners:
/// a_i = 2 f_i - (f_0 + f_1 + f_2) / 3.
pub fn corners(g: &[[f64; 3]; 3]) -> [[f64; 3]; 3] {
    let mut out = [[0.0; 3]; 3];
    for c in 0..3 { let s = (g[0][c] + g[1][c] + g[2][c]) / 3.0; for i in 0..3 { out[i][c] = 2.0 * g[i][c] - s; } }
    out
}

pub fn von_mises(s: [f64; 3]) -> f64 { (s[0] * s[0] - s[0] * s[1] + s[1] * s[1] + 3.0 * s[2] * s[2]).max(0.0).sqrt() }

// ---------------- sparse skyline solver ----------------
/// Reverse Cuthill-McKee node order.
fn rcm(n: usize, tris: &[[usize; 3]]) -> Vec<usize> {
    let mut adj: Vec<Vec<usize>> = vec![Vec::new(); n];
    for t in tris { for a in 0..3 { for b in 0..3 { if a != b { adj[t[a]].push(t[b]); } } } }
    for a in adj.iter_mut() { a.sort_unstable(); a.dedup(); }
    let mut order = Vec::with_capacity(n);
    let mut seen = vec![false; n];
    loop {
        let Some(mut start) = (0..n).filter(|&i| !seen[i]).min_by_key(|&i| adj[i].len()) else { break };
        // pseudo-peripheral: two BFS sweeps
        for _ in 0..2 {
            let mut lvl = vec![usize::MAX; n];
            let mut q = std::collections::VecDeque::from([start]);
            lvl[start] = 0;
            let mut last = start;
            while let Some(u) = q.pop_front() {
                last = u;
                for &v in &adj[u] { if !seen[v] && lvl[v] == usize::MAX { lvl[v] = lvl[u] + 1; q.push_back(v); } }
            }
            start = last;
        }
        let mut q = std::collections::VecDeque::from([start]);
        seen[start] = true;
        while let Some(u) = q.pop_front() {
            order.push(u);
            let mut nb: Vec<usize> = adj[u].iter().copied().filter(|&v| !seen[v]).collect();
            nb.sort_by_key(|&v| adj[v].len());
            for v in nb { seen[v] = true; q.push_back(v); }
        }
    }
    order.reverse();
    order
}

struct Skyline { n: usize, first: Vec<usize>, start: Vec<usize>, a: Vec<f64> }
impl Skyline {
    fn new(n: usize, first: Vec<usize>) -> Self {
        let mut start = vec![0; n + 1];
        for i in 0..n { start[i + 1] = start[i] + (i - first[i] + 1); }
        let a = vec![0.0; start[n]];
        Skyline { n, first, start, a }
    }
    #[inline] fn add(&mut self, i: usize, j: usize, v: f64) {
        let (i, j) = if i >= j { (i, j) } else { (j, i) };
        let k = self.start[i] + (j - self.first[i]);
        self.a[k] += v;
    }
    fn factor(&mut self) -> bool {
        let mut scale = 0.0f64;
        for i in 0..self.n { scale = scale.max(self.a[self.start[i] + i - self.first[i]].abs()); }
        let tol = (scale * 1e-13).max(1e-300);
        for i in 0..self.n {
            let fi = self.first[i];
            let si = self.start[i];
            for j in fi..=i {
                let fj = self.first[j];
                let sj = self.start[j];
                let k0 = fi.max(fj);
                let mut s = self.a[si + j - fi];
                // dot of row i and row j over columns k0..j
                let ri = &self.a[si + k0 - fi..si + j - fi];
                let rj = &self.a[sj + k0 - fj..sj + j - fj];
                let mut acc = 0.0;
                for (x, y) in ri.iter().zip(rj) { acc += x * y; }
                s -= acc;
                if j == i {
                    if !(s > tol) { return false; }
                    self.a[si + i - fi] = s.sqrt();
                } else {
                    self.a[si + j - fi] = s / self.a[sj + j - fj];
                }
            }
        }
        true
    }
    fn solve(&self, b: &mut [f64]) {
        for i in 0..self.n {
            let fi = self.first[i]; let si = self.start[i];
            let mut s = b[i];
            for k in fi..i { s -= self.a[si + k - fi] * b[k]; }
            b[i] = s / self.a[si + i - fi];
        }
        for i in (0..self.n).rev() {
            let fi = self.first[i]; let si = self.start[i];
            b[i] /= self.a[si + i - fi];
            let bi = b[i];
            for k in fi..i { b[k] -= self.a[si + k - fi] * bi; }
        }
    }
}

/// Assembled plate (5 dofs / node: u, v, w, w_x, w_y).
/// `te`: optional per-element thickness (mm, same order as `mesh.tris`); empty = uniform `t`.
/// Added 2026-10-11 for the crescent thickness field (pockets, lattice, fullers, distal taper).
pub struct Plate { pub mesh: Mesh, pub t: f64, pub cmat: [[f64; 3]; 3], perm: Vec<usize>, pub te: Vec<f64> }

pub struct System { sky: Skyline, map: Vec<isize> }

impl Plate {
    pub fn new(mesh: Mesh, t: f64, e_mpa: f64, nu: f64) -> Self {
        let perm = rcm(mesh.xy.len(), &mesh.tris);
        Plate { mesh, t, cmat: c_plane(e_mpa, nu), perm, te: Vec::new() }
    }
    /// Per-element thickness field (len = tris). Uniform-t results are unchanged when not called.
    pub fn with_thickness(mut self, te: Vec<f64>) -> Self { assert_eq!(te.len(), self.mesh.tris.len()); self.te = te; self }
    /// Thickness of element `e`.
    pub fn t_of(&self, e: usize) -> f64 { self.te.get(e).copied().unwrap_or(self.t) }
    pub fn n(&self) -> usize { self.mesh.xy.len() }

    /// Assemble and factor with the dofs in `fixed` (len n*5) removed.
    pub fn system(&self, fixed: &[bool]) -> Option<System> {
        let n = self.n();
        let mut map = vec![-1isize; n * 5];
        let mut nf = 0usize;
        for &node in &self.perm { for c in 0..5 { if !fixed[node * 5 + c] { map[node * 5 + c] = nf as isize; nf += 1; } } }
        if nf == 0 { return None; }
        let mut first: Vec<usize> = (0..nf).collect();
        for tri in &self.mesh.tris {
            let ids: Vec<usize> = tri.iter().flat_map(|&nd| (0..5).map(move |c| nd * 5 + c)).filter_map(|d| (map[d] >= 0).then(|| map[d] as usize)).collect();
            if let Some(&mn) = ids.iter().min() { for &i in &ids { first[i] = first[i].min(mn); } }
        }
        let mut sky = Skyline::new(nf, first);
        let c = self.cmat;
        for (e, tri) in self.mesh.tris.iter().enumerate() {
            let t = self.t_of(e);
            let xs = [self.mesh.xy[tri[0]].0, self.mesh.xy[tri[1]].0, self.mesh.xy[tri[2]].0];
            let ys = [self.mesh.xy[tri[0]].1, self.mesh.xy[tri[1]].1, self.mesh.xy[tri[2]].1];
            let a2 = a2_of(&xs, &ys);
            let area = 0.5 * a2.abs();
            let bm = cst_b(&xs, &ys, a2);
            let mut km = [[0.0; 6]; 6];
            btcb(&bm, &c, t * area, &mut km);
            let tt = dkt_t(&xs, &ys);
            let mut kb = [[0.0; 9]; 9];
            for l in GP { let bb = dkt_b(&xs, &ys, a2, &tt, l); btcb(&bb, &c, area / 3.0 * t * t * t / 12.0, &mut kb); }
            let idm: [isize; 6] = std::array::from_fn(|q| map[tri[q / 2] * 5 + q % 2]);
            let idb: [isize; 9] = std::array::from_fn(|q| map[tri[q / 3] * 5 + 2 + q % 3]);
            for a in 0..6 { if idm[a] < 0 { continue; } for b in 0..=a { if idm[b] >= 0 { sky.add(idm[a] as usize, idm[b] as usize, km[a][b]); } } }
            for a in 0..9 { if idb[a] < 0 { continue; } for b in 0..=a { if idb[b] >= 0 { sky.add(idb[a] as usize, idb[b] as usize, kb[a][b]); } } }
        }
        // add() orders (i, j) itself; each local pair b <= a is added once.
        if !sky.factor() { return None; }
        Some(System { sky, map })
    }

    /// Solve for a full load vector (len n*5); returns full displacement (fixed dofs = 0).
    pub fn solve(&self, sys: &System, f: &[f64]) -> Vec<f64> {
        let nf = sys.sky.n;
        let mut b = vec![0.0; nf];
        for (d, &g) in sys.map.iter().enumerate() { if g >= 0 { b[g as usize] += f[d]; } }
        sys.sky.solve(&mut b);
        let mut u = vec![0.0; f.len()];
        for (d, &g) in sys.map.iter().enumerate() { if g >= 0 { u[d] = b[g as usize]; } }
        u
    }

    /// Per-element (membrane vm, bending surface vm = max over the 3 corners, extrapolated from
    /// the Gauss points; DKT curvature is linear in the element so this is exact). MPa per unit load.
    pub fn stresses(&self, u: &[f64]) -> (Vec<f64>, Vec<f64>) {
        let mut sm = Vec::with_capacity(self.mesh.tris.len());
        let mut sb = Vec::with_capacity(self.mesh.tris.len());
        for (e, tri) in self.mesh.tris.iter().enumerate() {
            let (s_m, s_b) = self.elem_stress_t(tri, u, self.t_of(e));
            sm.push(von_mises(s_m));
            sb.push(corners(&s_b).iter().map(|s| von_mises(*s)).fold(0.0, f64::max));
        }
        (sm, sb)
    }

    /// Membrane stress and bending surface stress at the 3 Gauss points.
    pub fn elem_stress(&self, tri: &[usize; 3], u: &[f64]) -> ([f64; 3], [[f64; 3]; 3]) { self.elem_stress_t(tri, u, self.t) }

    /// As `elem_stress` with an explicit element thickness (bending surface stress = E k t/2).
    pub fn elem_stress_t(&self, tri: &[usize; 3], u: &[f64], t_e: f64) -> ([f64; 3], [[f64; 3]; 3]) {
        let xs = [self.mesh.xy[tri[0]].0, self.mesh.xy[tri[1]].0, self.mesh.xy[tri[2]].0];
        let ys = [self.mesh.xy[tri[0]].1, self.mesh.xy[tri[1]].1, self.mesh.xy[tri[2]].1];
        let a2 = a2_of(&xs, &ys);
        let c = &self.cmat;
        let um: [f64; 6] = std::array::from_fn(|q| u[tri[q / 2] * 5 + q % 2]);
        let ub: [f64; 9] = std::array::from_fn(|q| u[tri[q / 3] * 5 + 2 + q % 3]);
        let bm = cst_b(&xs, &ys, a2);
        let mut e = [0.0; 3];
        for r in 0..3 { for q in 0..6 { e[r] += bm[r][q] * um[q]; } }
        let s_m = [c[0][0] * e[0] + c[0][1] * e[1], c[1][0] * e[0] + c[1][1] * e[1], c[2][2] * e[2]];
        let tt = dkt_t(&xs, &ys);
        let mut s_b = [[0.0; 3]; 3];
        for (g, l) in GP.iter().enumerate() {
            let bb = dkt_b(&xs, &ys, a2, &tt, *l);
            let mut k = [0.0; 3];
            for r in 0..3 { for q in 0..9 { k[r] += bb[r][q] * ub[q]; } }
            let h = t_e * 0.5;
            s_b[g] = [h * (c[0][0] * k[0] + c[0][1] * k[1]), h * (c[1][0] * k[0] + c[1][1] * k[1]), h * c[2][2] * k[2]];
        }
        (s_m, s_b)
    }

    /// Area-weighted nodal average of the CST membrane stress; returns per-node stress vector.
    pub fn nodal_membrane(&self, u: &[f64]) -> Vec<[f64; 3]> {
        let n = self.n();
        let mut acc = vec![[0.0; 3]; n];
        let mut w = vec![0.0; n];
        for (e, tri) in self.mesh.tris.iter().enumerate() {
            let (s, _) = self.elem_stress(tri, u);
            let a = self.area(e);
            for &v in tri { for c in 0..3 { acc[v][c] += a * s[c]; } w[v] += a; }
        }
        for i in 0..n { if w[i] > 0.0 { for c in 0..3 { acc[i][c] /= w[i]; } } }
        acc
    }

    pub fn centroid(&self, e: usize) -> P2 {
        let t = self.mesh.tris[e];
        let p = |i: usize| self.mesh.xy[t[i]];
        ((p(0).0 + p(1).0 + p(2).0) / 3.0, (p(0).1 + p(1).1 + p(2).1) / 3.0)
    }
    pub fn area(&self, e: usize) -> f64 {
        let t = self.mesh.tris[e];
        let xs = [self.mesh.xy[t[0]].0, self.mesh.xy[t[1]].0, self.mesh.xy[t[2]].0];
        let ys = [self.mesh.xy[t[0]].1, self.mesh.xy[t[1]].1, self.mesh.xy[t[2]].1];
        0.5 * a2_of(&xs, &ys).abs()
    }
}

// ---------------- knife load cases ----------------
#[derive(Clone, Debug, Default)]
pub struct FineCaps {
    /// Capacity (N) at yield(temp) — lateral is the 180/260 N floor case.
    pub lateral_n: f64,
    pub pry_n: f64,
    /// N*mm about the chord axis (proxy, no floor).
    pub twist_nmm: f64,
    pub ring_pull_n: f64,
    /// Peak-stress element centroid for the lateral case and a region label.
    pub lateral_at: P2,
    pub lateral_region: &'static str,
    pub ring_at: P2,
    pub nodes: usize,
    pub tris: usize,
    pub max_area: f64,
}

/// Per-element field (MPa per unit load) for heatmaps.
pub struct Fields {
    pub plate: Plate, pub lateral: Vec<f64>, pub twist: Vec<f64>, pub pry: Vec<f64>, pub ring: Vec<f64>,
    pub excl: Vec<bool>, pub excl_ring: Vec<bool>, pub blade: Vec<bool>, pub tip: P2,
    /// Membrane peaks from area-weighted nodal averaging (CST is constant per element), MPa per
    /// unit load, and where: (value, node position). Used for the pry and ring-pull capacities.
    pub pry_nodal: (f64, P2), pub ring_nodal: (f64, P2),
}

pub fn region(p: &Phenotype, q: P2) -> &'static str {
    let y_sh = -p.ricasso_len;
    let y_neck = y_sh - p.grip_len;
    if q.1 >= -0.5 { "blade" }
    else if q.1 >= y_sh - 0.5 { "ricasso" }
    else if (q.0 - p.ring_center.0).hypot(q.1 - p.ring_center.1) <= p.ring_outer_r + 0.5 && q.1 < y_neck + 3.0 { "ring" }
    else if q.1 <= y_neck + 15.0 { "grip-ring neck" }
    else { "grip" }
}

pub fn fields(p: &Phenotype, m: &Material, ser: (f64, f64), max_area: f64) -> Option<Fields> {
    let mesh = mesh_domain(&p.outline, &[p.ring_hole.clone()], max_area)?;
    let plate = Plate::new(mesh, p.thickness.max(0.2), m.e_gpa * 1000.0, NU);
    let xy = &plate.mesh.xy;
    let n = xy.len();
    let ne = plate.mesh.tris.len();
    let h = limits::BLADE_H_MM;
    let he = (h - ser.0 - ser.1).max(1.0);
    let lat_k = h / he;
    let in_k = lat_k * lat_k;
    let ric: Vec<bool> = xy.iter().map(|q| q.1 <= 0.8 && q.1 >= -p.ricasso_len - 0.8).collect();
    let nric = ric.iter().filter(|&&b| b).count();
    if nric < 2 { return None; }
    let hc = { let (mut x, mut y) = (0.0, 0.0); for i in 0..n { if ric[i] { x += xy[i].0; y += xy[i].1; } } (x / nric as f64, y / nric as f64) };
    let tipi = (0..n).filter(|&i| plate.mesh.on_outer[i]).min_by(|&a, &b| {
        let da = (xy[a].0 - p.blade.tip.0).hypot(xy[a].1 - p.blade.tip.1);
        let db = (xy[b].0 - p.blade.tip.0).hypot(xy[b].1 - p.blade.tip.1);
        da.partial_cmp(&db).unwrap()
    })?;
    let tp = xy[tipi];
    let d = |i: usize| (xy[i].0 - tp.0).hypot(xy[i].1 - tp.1);
    let patch: Vec<usize> = (0..n).filter(|&i| d(i) <= TIP_PATCH_MM && (plate.mesh.on_outer[i] || d(i) <= 1.0)).collect();
    let k = patch.len().max(1) as f64;
    let dl = (tp.0 - hc.0).hypot(tp.1 - hc.1).max(1e-9);
    let dvec = ((tp.0 - hc.0) / dl, (tp.1 - hc.1) / dl);
    let nvec = (-dvec.1, dvec.0);
    let cen: Vec<P2> = (0..ne).map(|e| plate.centroid(e)).collect();
    let excl: Vec<bool> = cen.iter().map(|c| (c.0 - tp.0).hypot(c.1 - tp.1) < TIP_EXCL_MM).collect();
    let blade: Vec<bool> = cen.iter().map(|c| c.1 >= -0.5).collect();

    let mut fix_ring = vec![false; n * 5];
    let mut nh = 0;
    for i in 0..n { if plate.mesh.on_hole[i] { nh += 1; for c in 0..5 { fix_ring[i * 5 + c] = true; } } }
    if nh < 3 { return None; }
    let sys = plate.system(&fix_ring)?;
    let mut f_lat = vec![0.0; n * 5];
    let mut f_tw = vec![0.0; n * 5];
    for &i in &patch {
        f_lat[i * 5 + 2] = 1.0 / k;
        f_tw[i * 5 + 3] = nvec.0 / k; f_tw[i * 5 + 4] = nvec.1 / k;
    }
    let (_, sb) = plate.stresses(&plate.solve(&sys, &f_lat));
    let lateral: Vec<f64> = (0..ne).map(|e| if blade[e] { sb[e] * lat_k } else { sb[e] }).collect();
    let (_, sb) = plate.stresses(&plate.solve(&sys, &f_tw));
    let twist: Vec<f64> = (0..ne).map(|e| if blade[e] { sb[e] * lat_k } else { sb[e] }).collect();
    drop(sys);
    // ---- in-plane cases on quadratic (T6) membrane elements ----
    let t6 = T6::new(&plate.mesh, plate.t, m.e_gpa * 1000.0, NU);
    let n6 = t6.n();
    let on_hole6: Vec<bool> = (0..n6).map(|i| i < n && plate.mesh.on_hole[i] || i >= n && dist_to_poly(t6.xy[i], &p.ring_hole) < 1e-6).collect();
    let ric6: Vec<bool> = t6.xy.iter().map(|q| q.1 <= 0.8 && q.1 >= -p.ricasso_len - 0.8).collect();
    let mut fx = vec![false; n6 * 2];
    for i in 0..n6 { if on_hole6[i] { fx[i * 2] = true; fx[i * 2 + 1] = true; } }
    let sys6 = t6.system(&fx)?;
    let mut f_pr = vec![0.0; n6 * 2];
    for &i in &patch { f_pr[i * 2] = nvec.0 / k; f_pr[i * 2 + 1] = nvec.1 / k; }
    let u_pr = t6.solve(&sys6, &f_pr);
    let cvm = t6.centroid_vm(&u_pr);
    let pry: Vec<f64> = (0..ne).map(|e| if blade[e] { cvm[e] * in_k } else { cvm[e] }).collect();
    let nod_pr = t6.nodal_stress(&u_pr);
    drop(sys6);
    let mut fx = vec![false; n6 * 2];
    for i in 0..n6 { if ric6[i] { fx[i * 2] = true; fx[i * 2 + 1] = true; } }
    let sys6 = t6.system(&fx)?;
    let mut f_ring = vec![0.0; n6 * 2];
    let per = t6.edge_traction(&|i| on_hole6[i], (0.0, -1.0), &mut f_ring);
    if per <= 0.0 { return None; }
    for v in f_ring.iter_mut() { *v /= per; }
    let u_ring = t6.solve(&sys6, &f_ring);
    let sm = t6.centroid_vm(&u_ring);
    let nod_ring = t6.nodal_stress(&u_ring);
    // ring pull: also drop the St-Venant zone (3 mm) next to the seated ricasso band, where the
    // rigid clamp meets the free edge (a support singularity, not part of the design).
    let y_clamp = -p.ricasso_len - 0.8 - 3.0;
    let excl_ring: Vec<bool> = cen.iter().zip(&excl).map(|(c, &e)| e || c.1 > y_clamp).collect();
    let near_tip = |q: P2| (q.0 - tp.0).hypot(q.1 - tp.1) < TIP_EXCL_MM;
    let mut pry_nodal = (0.0, tp);
    let mut ring_nodal = (0.0, tp);
    for i in 0..n6 {
        let q = t6.xy[i];
        if near_tip(q) { continue; }
        let kb = if q.1 >= -0.5 { in_k } else { 1.0 };
        let v = von_mises(nod_pr[i]) * kb;
        if v > pry_nodal.0 { pry_nodal = (v, q); }
        if q.1 <= y_clamp && !ric6[i] { let v = von_mises(nod_ring[i]); if v > ring_nodal.0 { ring_nodal = (v, q); } }
    }
    Some(Fields { plate, lateral, twist, pry, ring: sm, excl, excl_ring, blade, tip: tp, pry_nodal, ring_nodal })
}

fn peak(v: &[f64], excl: &[bool]) -> (f64, usize) {
    let mut best = (0.0, 0);
    for (e, &s) in v.iter().enumerate() { if !excl[e] && s.is_finite() && s > best.0 { best = (s, e); } }
    best
}

/// Detailed-plate capacities at `temp_c` (yield derate only), mesh max area `max_area` mm^2.
pub fn capacities(p: &Phenotype, m: &Material, temp_c: f64, ser: (f64, f64), max_area: f64) -> Option<FineCaps> {
    let f = fields(p, m, ser, max_area)?;
    Some(caps_from(&f, p, m, temp_c, max_area))
}

pub fn caps_from(f: &Fields, p: &Phenotype, m: &Material, temp_c: f64, max_area: f64) -> FineCaps {
    let sy = m.yield_at(temp_c).max(1.0);
    let (sl, el) = peak(&f.lateral, &f.excl);
    let (st, _) = peak(&f.twist, &f.excl);
    let sp = f.pry_nodal.0;
    let sr = f.ring_nodal.0;
    let at = f.plate.centroid(el);
    FineCaps {
        lateral_n: sy / sl.max(1e-12), pry_n: sy / sp.max(1e-12), twist_nmm: sy / st.max(1e-12), ring_pull_n: sy / sr.max(1e-12),
        lateral_at: at, lateral_region: region(p, at), ring_at: f.ring_nodal.1,
        nodes: f.plate.n(), tris: f.plate.mesh.tris.len(), max_area,
    }
}

/// Scale capacities to another temperature (linear elastic: only yield changes).
pub fn at_temp(c: &FineCaps, m: &Material, from_c: f64, to_c: f64) -> FineCaps {
    let k = m.yield_at(to_c) / m.yield_at(from_c);
    FineCaps { lateral_n: c.lateral_n * k, pry_n: c.pry_n * k, twist_nmm: c.twist_nmm * k, ring_pull_n: c.ring_pull_n * k, ..c.clone() }
}

// ---------------- quadratic membrane (T6) ----------------
/// 6-node quadratic membrane triangles on a `Mesh` (midside nodes added on every edge).
/// Stress is linear in the element, so peaks at fillets and holes converge O(h^2) instead of the
/// CST's O(h). Used for the in-plane cases (pry, ring pull). Dofs (u, v) per node.
pub struct T6 { pub xy: Vec<P2>, pub tris: Vec<[usize; 6]>, pub n_corner: usize, pub t: f64, pub cmat: [[f64; 3]; 3], perm: Vec<usize>, pub te: Vec<f64> }
pub struct T6System { sky: Skyline, map: Vec<isize> }

const T6_GP: [([f64; 3], f64); 3] = [([2.0 / 3.0, 1.0 / 6.0, 1.0 / 6.0], 1.0 / 3.0), ([1.0 / 6.0, 2.0 / 3.0, 1.0 / 6.0], 1.0 / 3.0), ([1.0 / 6.0, 1.0 / 6.0, 2.0 / 3.0], 1.0 / 3.0)];
const T6_NODES_L: [[f64; 3]; 6] = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [0.5, 0.5, 0.0], [0.0, 0.5, 0.5], [0.5, 0.0, 0.5]];

impl T6 {
    pub fn new(mesh: &Mesh, t: f64, e_mpa: f64, nu: f64) -> Self {
        let n = mesh.xy.len();
        let mut xy = mesh.xy.clone();
        let mut mid: std::collections::HashMap<(usize, usize), usize> = std::collections::HashMap::new();
        let mut tris = Vec::with_capacity(mesh.tris.len());
        for t3 in &mesh.tris {
            let mut m = [0usize; 3];
            for (k, (a, b)) in [(t3[0], t3[1]), (t3[1], t3[2]), (t3[2], t3[0])].into_iter().enumerate() {
                let key = (a.min(b), a.max(b));
                m[k] = *mid.entry(key).or_insert_with(|| { xy.push(((xy[a].0 + xy[b].0) / 2.0, (xy[a].1 + xy[b].1) / 2.0)); xy.len() - 1 });
            }
            tris.push([t3[0], t3[1], t3[2], m[0], m[1], m[2]]);
        }
        let adj6: Vec<[usize; 3]> = tris.iter().flat_map(|t| [[t[0], t[3], t[5]], [t[3], t[1], t[4]], [t[5], t[4], t[2]], [t[3], t[4], t[5]]]).collect();
        let perm = rcm(xy.len(), &adj6);
        T6 { xy, tris, n_corner: n, t, cmat: c_plane(e_mpa, nu), perm, te: Vec::new() }
    }
    /// Per-element membrane thickness (len = tris); empty = uniform `t`.
    pub fn with_thickness(mut self, te: Vec<f64>) -> Self { assert_eq!(te.len(), self.tris.len()); self.te = te; self }
    pub fn n(&self) -> usize { self.xy.len() }

    fn grads(&self, e: usize) -> ([f64; 3], [f64; 3], f64) {
        let t = &self.tris[e];
        let xs = [self.xy[t[0]].0, self.xy[t[1]].0, self.xy[t[2]].0];
        let ys = [self.xy[t[0]].1, self.xy[t[1]].1, self.xy[t[2]].1];
        let a2 = a2_of(&xs, &ys);
        let b: [f64; 3] = std::array::from_fn(|i| (ys[(i + 1) % 3] - ys[(i + 2) % 3]) / a2);
        let c: [f64; 3] = std::array::from_fn(|i| (xs[(i + 2) % 3] - xs[(i + 1) % 3]) / a2);
        (b, c, a2)
    }

    /// Strain-displacement (3 x 12) at area coordinates `l`.
    fn bmat(b: &[f64; 3], c: &[f64; 3], l: &[f64; 3]) -> [[f64; 12]; 3] {
        let mut dx = [0.0; 6];
        let mut dy = [0.0; 6];
        for i in 0..3 { dx[i] = (4.0 * l[i] - 1.0) * b[i]; dy[i] = (4.0 * l[i] - 1.0) * c[i]; }
        for (k, (i, j)) in [(3usize, (0usize, 1usize)), (4, (1, 2)), (5, (2, 0))] {
            dx[k] = 4.0 * (l[i] * b[j] + l[j] * b[i]);
            dy[k] = 4.0 * (l[i] * c[j] + l[j] * c[i]);
        }
        let mut bm = [[0.0; 12]; 3];
        for k in 0..6 { bm[0][2 * k] = dx[k]; bm[1][2 * k + 1] = dy[k]; bm[2][2 * k] = dy[k]; bm[2][2 * k + 1] = dx[k]; }
        bm
    }

    pub fn system(&self, fixed: &[bool]) -> Option<T6System> {
        let n = self.n();
        let mut map = vec![-1isize; n * 2];
        let mut nf = 0usize;
        for &node in &self.perm { for c in 0..2 { if !fixed[node * 2 + c] { map[node * 2 + c] = nf as isize; nf += 1; } } }
        if nf == 0 { return None; }
        let mut first: Vec<usize> = (0..nf).collect();
        for t in &self.tris {
            let ids: Vec<usize> = t.iter().flat_map(|&nd| (0..2).map(move |c| nd * 2 + c)).filter_map(|d| (map[d] >= 0).then(|| map[d] as usize)).collect();
            if let Some(&mn) = ids.iter().min() { for &i in &ids { first[i] = first[i].min(mn); } }
        }
        let mut sky = Skyline::new(nf, first);
        for (e, t) in self.tris.iter().enumerate() {
            let (b, c, a2) = self.grads(e);
            let area = 0.5 * a2.abs();
            let mut k = [[0.0; 12]; 12];
            for (l, w) in T6_GP { let bm = Self::bmat(&b, &c, &l); btcb(&bm, &self.cmat, w * area * self.te.get(e).copied().unwrap_or(self.t), &mut k); }
            let id: [isize; 12] = std::array::from_fn(|q| map[t[q / 2] * 2 + q % 2]);
            for a in 0..12 { if id[a] < 0 { continue; } for bb in 0..=a { if id[bb] >= 0 { sky.add(id[a] as usize, id[bb] as usize, k[a][bb]); } } }
        }
        if !sky.factor() { return None; }
        Some(T6System { sky, map })
    }

    pub fn solve(&self, sys: &T6System, f: &[f64]) -> Vec<f64> {
        let mut b = vec![0.0; sys.sky.n];
        for (d, &g) in sys.map.iter().enumerate() { if g >= 0 { b[g as usize] += f[d]; } }
        sys.sky.solve(&mut b);
        let mut u = vec![0.0; f.len()];
        for (d, &g) in sys.map.iter().enumerate() { if g >= 0 { u[d] = b[g as usize]; } }
        u
    }

    /// Area-weighted nodal average of the element nodal stresses (all 6 nodes).
    pub fn nodal_stress(&self, u: &[f64]) -> Vec<[f64; 3]> {
        let n = self.n();
        let mut acc = vec![[0.0; 3]; n];
        let mut w = vec![0.0; n];
        let c = &self.cmat;
        for (e, t) in self.tris.iter().enumerate() {
            let (b, cc, a2) = self.grads(e);
            let area = 0.5 * a2.abs();
            let ue: [f64; 12] = std::array::from_fn(|q| u[t[q / 2] * 2 + q % 2]);
            for (k, l) in T6_NODES_L.iter().enumerate() {
                let bm = Self::bmat(&b, &cc, l);
                let mut eps = [0.0; 3];
                for r in 0..3 { for q in 0..12 { eps[r] += bm[r][q] * ue[q]; } }
                let s = [c[0][0] * eps[0] + c[0][1] * eps[1], c[1][0] * eps[0] + c[1][1] * eps[1], c[2][2] * eps[2]];
                for r in 0..3 { acc[t[k]][r] += area * s[r]; }
                w[t[k]] += area;
            }
        }
        for i in 0..n { if w[i] > 0.0 { for r in 0..3 { acc[i][r] /= w[i]; } } }
        acc
    }

    /// Element stress at its centroid (for heatmaps).
    pub fn centroid_vm(&self, u: &[f64]) -> Vec<f64> {
        let c = &self.cmat;
        (0..self.tris.len()).map(|e| {
            let t = &self.tris[e];
            let (b, cc, _) = self.grads(e);
            let ue: [f64; 12] = std::array::from_fn(|q| u[t[q / 2] * 2 + q % 2]);
            let bm = Self::bmat(&b, &cc, &[1.0 / 3.0; 3]);
            let mut eps = [0.0; 3];
            for r in 0..3 { for q in 0..12 { eps[r] += bm[r][q] * ue[q]; } }
            von_mises([c[0][0] * eps[0] + c[0][1] * eps[1], c[1][0] * eps[0] + c[1][1] * eps[1], c[2][2] * eps[2]])
        }).collect()
    }

    /// Consistent load for a uniform traction (force per length, direction `dir`) on the boundary
    /// edges whose two corner nodes satisfy `on`. Returns total edge length loaded.
    pub fn edge_traction(&self, on: &dyn Fn(usize) -> bool, q: (f64, f64), f: &mut [f64]) -> f64 {
        let mut count: std::collections::HashMap<(usize, usize), (usize, usize)> = std::collections::HashMap::new();
        for t in &self.tris {
            for (a, b, m) in [(t[0], t[1], t[3]), (t[1], t[2], t[4]), (t[2], t[0], t[5])] {
                let e = count.entry((a.min(b), a.max(b))).or_insert((0, m));
                e.0 += 1;
            }
        }
        let mut total = 0.0;
        for (&(a, b), &(k, m)) in &count {
            if k != 1 || !on(a) || !on(b) { continue; }
            let l = (self.xy[a].0 - self.xy[b].0).hypot(self.xy[a].1 - self.xy[b].1);
            total += l;
            for (node, wgt) in [(a, 1.0 / 6.0), (b, 1.0 / 6.0), (m, 4.0 / 6.0)] {
                f[node * 2] += q.0 * l * wgt; f[node * 2 + 1] += q.1 * l * wgt;
            }
        }
        total
    }
}
