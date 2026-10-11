//! Coarse Kirchhoff plate on the ear-cut profile.
//! Discrete Kirchhoff triangle (DKT) for lateral bending, constant-strain
//! triangle for in-plane and ring pull. One flat shell, thickness = stock.
//! Batoz, Bathe, Ho, IJNME 15(12), 1980. Serration is not in the mesh;
//! blade section loss scales that stress the way the beam surrogate does.
//!
//! Linear tets through the thickness lock in bending (a 4-layer cantilever
//! still sat at ~7% of beam stress). The plate element is the coarse model
//! that actually bends. It is a check on a design, not the Monte Carlo loop:
//! a dense factor of a few hundred dofs is milliseconds, and 10k samples cannot
//! carry that. `JARAMBIT_FEM=1` takes one nominal plate solve per candidate as
//! the strength level. The sample loop stays the beam surrogate and only
//! supplies the tolerance and temperature knockdown.
use jarambit_genotype::limits;
use jarambit_phenotype::{triangulate, Phenotype};
use super::Material;

#[derive(Clone, Copy, Debug)]
pub struct Caps {
    pub blade_lat_n: f64,
    pub grip_lat_n: f64,
    pub inplane_n: f64,
    pub ring_pull_n: f64,
    pub nodes: usize,
    pub free_dofs: usize,
}

const NU: f64 = 0.34;
/// Plate mesh gates. Dense Cholesky on 800 dofs is ~1.7e8 flop (tens of ms), still one nominal
/// solve per candidate, never per MC sample.
pub const MAX_NODES: usize = 160;
pub const MAX_TRIS: usize = 320;
pub const MAX_FREE_DOFS: usize = 800;

pub fn capacities(p: &Phenotype, m: &Material, temp_c: f64, ser: (f64, f64)) -> Option<Caps> {
    let outer = decimate_outline(&p.outline, p.ricasso_len, p.blade.tip);
    let hole = sample_n(&p.ring_hole, 12);
    let (outer, hole, tris) = triangulate(&outer, &hole)?;
    // Caps raised 2026-10-11 (blade floor 444a74d + blade-angle knob 152ad95): long raked blades
    // decimate to ~83-120 nodes. Old 80-node / 140-tri / 420-dof gates returned None on them.
    if tris.is_empty() || tris.len() > MAX_TRIS { return None; }
    let n_out = outer.len();
    let xy: Vec<(f64, f64)> = outer.iter().copied().chain(hole.iter().copied()).collect();
    if xy.len() < 8 || xy.len() > MAX_NODES { return None; }
    let t = p.thickness.max(0.2);
    let sy = m.yield_at(temp_c).max(1.0);
    let ee = m.e_gpa * 1000.0;
    let h = limits::BLADE_H_MM;
    let he = (h - ser.0 - ser.1).max(1.0);
    let lat_k = h / he;
    let in_k = (h / he).powi(2);

    // Load at the real blade tip (nearest outline node). With the blade-angle knob the highest
    // point is mid-arc, not the tip, so the old max-y pick would shorten the lever.
    let tip = (0..n_out).min_by(|&i, &j| hypot(xy[i], p.blade.tip).partial_cmp(&hypot(xy[j], p.blade.tip)).unwrap())?;
    let ring = |i: usize| i >= n_out;
    let ricasso = |i: usize| {
        let y = xy[i].1;
        y <= 0.8 && y >= -p.ricasso_len - 0.8
    };
    if (n_out..xy.len()).filter(|&i| ring(i)).count() < 3 { return None; }
    if (0..xy.len()).filter(|&i| ricasso(i)).count() < 2 { return None; }

    let mut hx = 0.0;
    let mut hy = 0.0;
    let mut hn = 0.0;
    for i in 0..xy.len() {
        if ricasso(i) { hx += xy[i].0; hy += xy[i].1; hn += 1.0; }
    }
    let (hx, hy) = (hx / hn, hy / hn);
    let mut dx = xy[tip].0 - hx;
    let mut dy = xy[tip].1 - hy;
    let dl = dx.hypot(dy).max(1e-6);
    dx /= dl;
    dy /= dl;

    // In the hand, the finger ring is the support and the tip carries lateral
    // and in-plane load, so the moment runs through the grip and the blade.
    // Ring pull is the other way: the guard/ricasso is seated and the ring is loaded.
    let mut hand = vec![[0.0; 5]; xy.len()];
    hand[tip][2] = 1.0;
    let mut plane = vec![[0.0; 5]; xy.len()];
    plane[tip][0] = dx;
    plane[tip][1] = dy;
    let (u_hand, map, nf) = solve_plate(&xy, &tris, &ring, &[hand, plane], t, ee, NU)?;
    let mut pull = vec![[0.0; 5]; xy.len()];
    let s = 1.0 / (xy.len() - n_out) as f64;
    for i in n_out..xy.len() { pull[i][1] = -s; }
    let (u_pull, map_pull, _) = solve_plate(&xy, &tris, &ricasso, &[pull], t, ee, NU)?;

    let (bb, bg, _, _) = vm_split(&xy, &tris, &map, &u_hand[0], t, ee, NU);
    let (_, _, mb, mg) = vm_split(&xy, &tris, &map, &u_hand[1], t, ee, NU);
    let (_, _, rb, rg) = vm_split(&xy, &tris, &map_pull, &u_pull[0], t, ee, NU);
    let cap = |vm: f64| sy / vm.max(1e-12);
    let blade_lat_n = cap(bb * lat_k);
    let grip_lat_n = cap(bg);
    let inplane_n = cap((mb * in_k).max(mg));
    let ring_pull_n = cap(rb.max(rg));
    if ![blade_lat_n, grip_lat_n, inplane_n, ring_pull_n].iter().all(|v| v.is_finite() && *v > 0.0) {
        return None;
    }
    Some(Caps { blade_lat_n, grip_lat_n, inplane_n, ring_pull_n, nodes: xy.len(), free_dofs: nf })
}

fn solve_plate(
    xy: &[(f64, f64)],
    tris: &[[usize; 3]],
    fixed: &dyn Fn(usize) -> bool,
    loads: &[Vec<[f64; 5]>],
    t: f64,
    ee: f64,
    nu: f64,
) -> Option<(Vec<Vec<f64>>, Vec<isize>, usize)> {
    let nn = xy.len();
    let mut map = vec![-1isize; nn * 5];
    let mut nf = 0isize;
    for i in 0..nn {
        if fixed(i) { continue; }
        for c in 0..5 { map[i * 5 + c] = nf; nf += 1; }
    }
    let nf = nf as usize;
    if nf < 5 || nf > MAX_FREE_DOFS { return None; }
    let cmat = c_plane(ee, nu);
    let mut k = vec![0.0; nf * nf];
    for tri in tris {
        let xs = [xy[tri[0]].0, xy[tri[1]].0, xy[tri[2]].0];
        let ys = [xy[tri[0]].1, xy[tri[1]].1, xy[tri[2]].1];
        let a2 = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0]);
        let area = a2.abs() * 0.5;
        if area < 1e-8 { continue; }
        let bm = cst_b(xs, ys, a2)?;
        let km = btc_b(6, &bm, &cmat, t * area);
        let mut idm = [0isize; 6];
        for (a, &node) in tri.iter().enumerate() {
            idm[a * 2] = map[node * 5];
            idm[a * 2 + 1] = map[node * 5 + 1];
        }
        scatter(&mut k, nf, &idm, &km);
        // Interior 3-point rule, exact for the quadratic DKT energy. Weights sum to 1.
        for (xi, eta, w) in [(1.0 / 6.0, 1.0 / 6.0, 1.0 / 3.0), (2.0 / 3.0, 1.0 / 6.0, 1.0 / 3.0), (1.0 / 6.0, 2.0 / 3.0, 1.0 / 3.0)] {
            let bb = dkt_b(xs, ys, a2, xi, eta)?;
            let kb = btc_b(9, &bb, &cmat, w * area * t * t * t / 12.0);
            let mut idb = [0isize; 9];
            for (a, &node) in tri.iter().enumerate() {
                idb[a * 3] = map[node * 5 + 2];
                idb[a * 3 + 1] = map[node * 5 + 3];
                idb[a * 3 + 2] = map[node * 5 + 4];
            }
            scatter(&mut k, nf, &idb, &kb);
        }
    }
    if !factor(&mut k, nf) { return None; }
    let mut out = Vec::with_capacity(loads.len());
    for load in loads {
        let mut rhs = vec![0.0; nf];
        for i in 0..nn {
            for c in 0..5 {
                let g = map[i * 5 + c];
                if g >= 0 { rhs[g as usize] += load[i][c]; }
            }
        }
        solve_with(&k, nf, &mut rhs);
        out.push(rhs);
    }
    Some((out, map, nf))
}

/// Peak bending and membrane von Mises (MPa per 1 N), split at the guard line y = -0.5.
fn vm_split(xy: &[(f64, f64)], tris: &[[usize; 3]], map: &[isize], u: &[f64], t: f64, ee: f64, nu: f64) -> (f64, f64, f64, f64) {
    let cmat = c_plane(ee, nu);
    let mut bb = 0.0f64;
    let mut bg = 0.0f64;
    let mut mb = 0.0f64;
    let mut mg = 0.0f64;
    for tri in tris {
        let xs = [xy[tri[0]].0, xy[tri[1]].0, xy[tri[2]].0];
        let ys = [xy[tri[0]].1, xy[tri[1]].1, xy[tri[2]].1];
        let a2 = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0]);
        if a2.abs() < 1e-8 { continue; }
        let cy = (ys[0] + ys[1] + ys[2]) / 3.0;
        let blade = cy >= -0.5;
        let mut um = [0.0; 6];
        let mut ub = [0.0; 9];
        for (a, &node) in tri.iter().enumerate() {
            for c in 0..2 {
                let g = map[node * 5 + c];
                if g >= 0 { um[a * 2 + c] = u[g as usize]; }
            }
            for c in 0..3 {
                let g = map[node * 5 + 2 + c];
                if g >= 0 { ub[a * 3 + c] = u[g as usize]; }
            }
        }
        if let Some(bm) = cst_b(xs, ys, a2) {
            let vm = von_mises(stress3(&bm, &cmat, &um));
            if blade { mb = mb.max(vm); } else { mg = mg.max(vm); }
        }
        for (xi, eta) in [(1.0 / 6.0, 1.0 / 6.0), (2.0 / 3.0, 1.0 / 6.0), (1.0 / 6.0, 2.0 / 3.0)] {
            if let Some(bbm) = dkt_b(xs, ys, a2, xi, eta) {
                // σ = (t/2) C κ, with κ = B u and M = (t^3/12) C κ.
                let mut s = stress3(&bbm, &cmat, &ub);
                for v in &mut s { *v *= t * 0.5; }
                let vm = von_mises(s);
                if blade { bb = bb.max(vm); } else { bg = bg.max(vm); }
            }
        }
    }
    if bb == 0.0 { bb = bg; }
    if bg == 0.0 { bg = bb; }
    if mb == 0.0 { mb = mg; }
    if mg == 0.0 { mg = mb; }
    (bb, bg, mb, mg)
}

fn c_plane(e: f64, nu: f64) -> [[f64; 3]; 3] {
    let k = e / (1.0 - nu * nu);
    [[k, k * nu, 0.0], [k * nu, k, 0.0], [0.0, 0.0, k * (1.0 - nu) / 2.0]]
}

fn cst_b(xs: [f64; 3], ys: [f64; 3], a2: f64) -> Option<[[f64; 9]; 3]> {
    if a2.abs() < 1e-12 { return None; }
    let mut b = [[0.0; 9]; 3];
    for j in 0..3 {
        let nx = (ys[(j + 1) % 3] - ys[(j + 2) % 3]) / a2;
        let ny = (xs[(j + 2) % 3] - xs[(j + 1) % 3]) / a2;
        b[0][2 * j] = nx;
        b[1][2 * j + 1] = ny;
        b[2][2 * j] = ny;
        b[2][2 * j + 1] = nx;
    }
    Some(b)
}

/// DKT curvature-displacement matrix at area coordinates (ξ, η) = (L2, L3).
fn dkt_b(xs: [f64; 3], ys: [f64; 3], a2: f64, xi: f64, eta: f64) -> Option<[[f64; 9]; 3]> {
    if a2.abs() < 1e-12 { return None; }
    let mut xe = [0.0; 3];
    let mut ye = [0.0; 3];
    for i in 0..3 {
        xe[i] = xs[(i + 2) % 3] - xs[(i + 1) % 3];
        ye[i] = ys[(i + 2) % 3] - ys[(i + 1) % 3];
    }
    let mut p = [0.0; 3];
    let mut q = [0.0; 3];
    let mut r = [0.0; 3];
    let mut tv = [0.0; 3];
    for i in 0..3 {
        let l2 = xe[i] * xe[i] + ye[i] * ye[i];
        if l2 < 1e-12 { return None; }
        p[i] = -6.0 * xe[i] / l2;
        q[i] = 3.0 * xe[i] * ye[i] / l2;
        r[i] = 3.0 * ye[i] * ye[i] / l2;
        tv[i] = -6.0 * ye[i] / l2;
    }
    let hx_xi = [
        p[2] * (1.0 - 2.0 * xi) + (p[1] - p[2]) * eta,
        q[2] * (1.0 - 2.0 * xi) - (q[1] + q[2]) * eta,
        -4.0 + 6.0 * (xi + eta) + r[2] * (1.0 - 2.0 * xi) - eta * (r[1] + r[2]),
        -p[2] * (1.0 - 2.0 * xi) + eta * (p[0] + p[2]),
        q[2] * (1.0 - 2.0 * xi) - eta * (q[2] - q[0]),
        -2.0 + 6.0 * xi + r[2] * (1.0 - 2.0 * xi) + eta * (r[0] - r[2]),
        -eta * (p[1] + p[0]),
        eta * (q[0] - q[1]),
        -eta * (r[1] - r[0]),
    ];
    let hy_xi = [
        tv[2] * (1.0 - 2.0 * xi) + (tv[1] - tv[2]) * eta,
        1.0 + r[2] * (1.0 - 2.0 * xi) - (r[1] + r[2]) * eta,
        -q[2] * (1.0 - 2.0 * xi) + eta * (q[1] + q[2]),
        -tv[2] * (1.0 - 2.0 * xi) + eta * (tv[0] + tv[2]),
        -1.0 + r[2] * (1.0 - 2.0 * xi) + eta * (r[0] - r[2]),
        q[2] * (1.0 - 2.0 * xi) - eta * (q[0] - q[2]),
        -eta * (tv[0] + tv[1]),
        eta * (r[0] - r[1]),
        -eta * (q[0] - q[1]),
    ];
    let hx_eta = [
        -p[1] * (1.0 - 2.0 * eta) - xi * (p[2] - p[1]),
        q[1] * (1.0 - 2.0 * eta) - xi * (q[1] + q[2]),
        -4.0 + 6.0 * (xi + eta) + r[1] * (1.0 - 2.0 * eta) - xi * (r[1] + r[2]),
        xi * (p[0] + p[2]),
        xi * (q[0] - q[2]),
        -xi * (r[2] - r[0]),
        p[1] * (1.0 - 2.0 * eta) - xi * (p[0] + p[1]),
        q[1] * (1.0 - 2.0 * eta) + xi * (q[0] - q[1]),
        -2.0 + 6.0 * eta + r[1] * (1.0 - 2.0 * eta) + xi * (r[0] - r[1]),
    ];
    let hy_eta = [
        -tv[1] * (1.0 - 2.0 * eta) - xi * (tv[2] - tv[1]),
        1.0 + r[1] * (1.0 - 2.0 * eta) - xi * (r[1] + r[2]),
        -q[1] * (1.0 - 2.0 * eta) + xi * (q[1] + q[2]),
        xi * (tv[0] + tv[2]),
        xi * (r[0] - r[2]),
        -xi * (q[0] - q[2]),
        tv[1] * (1.0 - 2.0 * eta) - xi * (tv[0] + tv[1]),
        -1.0 + r[1] * (1.0 - 2.0 * eta) + xi * (r[0] - r[1]),
        -q[1] * (1.0 - 2.0 * eta) - xi * (q[0] - q[1]),
    ];
    let mut b = [[0.0; 9]; 3];
    for j in 0..9 {
        b[0][j] = (ye[1] * hx_xi[j] + ye[2] * hx_eta[j]) / a2;
        b[1][j] = (-xe[1] * hy_xi[j] - xe[2] * hy_eta[j]) / a2;
        b[2][j] = (-xe[1] * hx_xi[j] - xe[2] * hx_eta[j] + ye[1] * hy_xi[j] + ye[2] * hy_eta[j]) / a2;
    }
    Some(b)
}

fn btc_b(m: usize, b: &[[f64; 9]; 3], c: &[[f64; 3]; 3], scale: f64) -> Vec<f64> {
    let mut cb = vec![0.0; 3 * m];
    for i in 0..3 {
        for j in 0..m {
            let mut s = 0.0;
            for k in 0..3 { s += c[i][k] * b[k][j]; }
            cb[i * m + j] = s;
        }
    }
    let mut k = vec![0.0; m * m];
    for i in 0..m {
        for j in i..m {
            let mut s = 0.0;
            for a in 0..3 { s += b[a][i] * cb[a * m + j]; }
            k[i * m + j] = s * scale;
            k[j * m + i] = k[i * m + j];
        }
    }
    k
}

fn stress3(b: &[[f64; 9]; 3], c: &[[f64; 3]; 3], u: &[f64]) -> [f64; 3] {
    let mut strain = [0.0; 3];
    for a in 0..3 {
        for i in 0..u.len() { strain[a] += b[a][i] * u[i]; }
    }
    let mut s = [0.0; 3];
    for a in 0..3 {
        for k in 0..3 { s[a] += c[a][k] * strain[k]; }
    }
    s
}

fn von_mises(s: [f64; 3]) -> f64 {
    (s[0] * s[0] - s[0] * s[1] + s[1] * s[1] + 3.0 * s[2] * s[2]).sqrt()
}

fn scatter(glob: &mut [f64], n: usize, id: &[isize], loc: &[f64]) {
    let m = id.len();
    for a in 0..m {
        if id[a] < 0 { continue; }
        let ia = id[a] as usize;
        for b in 0..m {
            if id[b] < 0 { continue; }
            glob[ia * n + id[b] as usize] += loc[a * m + b];
        }
    }
}

fn factor(a: &mut [f64], n: usize) -> bool {
    let mut scale = 0.0f64;
    for i in 0..n { scale = scale.max(a[i * n + i].abs()); }
    let tol = (scale * 1e-14).max(1e-18);
    for i in 0..n {
        for j in 0..=i {
            let mut s = a[i * n + j];
            for k in 0..j { s -= a[i * n + k] * a[j * n + k]; }
            if i == j {
                if s <= tol { return false; }
                a[i * n + j] = s.sqrt();
            } else {
                a[i * n + j] = s / a[j * n + j];
            }
        }
    }
    true
}

fn solve_with(l: &[f64], n: usize, b: &mut [f64]) {
    for i in 0..n {
        let mut s = b[i];
        for k in 0..i { s -= l[i * n + k] * b[k]; }
        b[i] = s / l[i * n + i];
    }
    for i in (0..n).rev() {
        let mut s = b[i];
        for k in i + 1..n { s -= l[k * n + i] * b[k]; }
        b[i] = s / l[i * n + i];
    }
}

fn decimate_outline(poly: &[P2], ricasso: f64, tip_pt: P2) -> Vec<P2> {
    let n = poly.len();
    if n <= 36 { return poly.to_vec(); }
    let tip = poly.iter().enumerate().min_by(|(_, a), (_, b)| hypot(**a, tip_pt).partial_cmp(&hypot(**b, tip_pt)).unwrap_or(std::cmp::Ordering::Equal)).unwrap().0;
    let mut keep = vec![false; n];
    keep[tip] = true;
    for i in 0..n {
        let y = poly[i].1;
        if y <= 0.8 && y >= -ricasso - 0.8 { keep[i] = true; }
        let ang = turn(poly[(i + n - 1) % n], poly[i], poly[(i + 1) % n]).abs();
        if ang > 0.7 { keep[i] = true; }
    }
    let mut out = Vec::new();
    let mut last_i = None;
    for i in 0..n {
        let far = last_i.map(|j: usize| hypot(poly[j], poly[i]) >= 6.0).unwrap_or(true);
        if keep[i] || far {
            out.push(poly[i]);
            last_i = Some(i);
        }
    }
    if out.len() < 12 { poly.iter().step_by((n / 24).max(1)).copied().collect() } else { out }
}

fn sample_n(poly: &[P2], n: usize) -> Vec<P2> {
    if poly.len() <= n { return poly.to_vec(); }
    (0..n).map(|i| poly[i * poly.len() / n]).collect()
}

fn hypot(a: P2, b: P2) -> f64 { (a.0 - b.0).hypot(a.1 - b.1) }
fn turn(a: P2, b: P2, c: P2) -> f64 {
    let u = (b.0 - a.0, b.1 - a.1);
    let v = (c.0 - b.0, c.1 - b.1);
    let cr = u.0 * v.1 - u.1 * v.0;
    let dt = u.0 * v.0 + u.1 * v.1;
    cr.atan2(dt)
}
type P2 = (f64, f64);

#[cfg(test)]
mod tests {
    use super::*;

    fn rect(nx: usize, ny: usize, len: f64, width: f64) -> (Vec<(f64, f64)>, Vec<[usize; 3]>) {
        let npx = nx + 1;
        let mut xy = Vec::new();
        for iy in 0..=ny {
            for ix in 0..=nx {
                xy.push((width * ix as f64 / nx as f64, len * iy as f64 / ny as f64));
            }
        }
        let mut tris = Vec::new();
        for iy in 0..ny {
            for ix in 0..nx {
                let i00 = iy * npx + ix;
                let i10 = i00 + 1;
                let i01 = i00 + npx;
                let i11 = i01 + 1;
                tris.push([i00, i10, i11]);
                tris.push([i00, i11, i01]);
            }
        }
        (xy, tris)
    }

    /// Straight cantilever, ν = 0, against the beam formulas.
    /// δ = F L^3 / (3 E I), σ = 6 F L / (b t^2).
    #[test]
    fn cantilever_matches_beam() {
        let (len, width, t) = (50.0, 14.0, 3.0);
        let (xy, tris) = rect(8, 2, len, width);
        let fixed = |i: usize| xy[i].1 < 1e-9;
        let tips: Vec<usize> = (0..xy.len()).filter(|&i| (xy[i].1 - len).abs() < 1e-8).collect();
        let mut load = vec![[0.0; 5]; xy.len()];
        let s = 1.0 / tips.len() as f64;
        for i in &tips { load[*i][2] = s; }
        let ee = 113_800.0;
        let (us, map, _) = solve_plate(&xy, &tris, &fixed, &[load], t, ee, 0.0).expect("factor");
        let mut uz = 0.0;
        for i in &tips {
            let g = map[i * 5 + 2];
            assert!(g >= 0);
            uz += us[0][g as usize];
        }
        uz /= tips.len() as f64;
        let i_sec = width * t * t * t / 12.0;
        let uz_beam = len * len * len / (3.0 * ee * i_sec);
        let (vb, _, _, _) = vm_split(&xy, &tris, &map, &us[0], t, ee, 0.0);
        let vm_beam = 6.0 * len / (width * t * t);
        let ru = uz / uz_beam;
        let rv = vb / vm_beam;
        assert!(uz > 0.0, "tip moved against the load {uz}");
        assert!(ru > 0.7 && ru < 1.35, "uz/beam {ru} vm/beam {rv}");
        assert!(rv > 0.5 && rv < 1.8, "vm/beam {rv} uz/beam {ru}");
    }

    /// Uniform tension. σ = F / (width · t). Catches a bad membrane B or a missing thickness.
    #[test]
    fn membrane_patch_matches_bar() {
        let (len, width, t) = (10.0, 8.0, 4.0);
        let (xy, tris) = rect(4, 2, len, width);
        let fixed = |i: usize| xy[i].1 < 1e-9;
        let tips: Vec<usize> = (0..xy.len()).filter(|&i| (xy[i].1 - len).abs() < 1e-8).collect();
        let mut load = vec![[0.0; 5]; xy.len()];
        let s = 1.0 / tips.len() as f64;
        for i in &tips { load[*i][1] = s; }
        let ee = 113_800.0;
        let (us, map, _) = solve_plate(&xy, &tris, &fixed, &[load], t, ee, 0.0).expect("factor");
        let (_, _, mb, _) = vm_split(&xy, &tris, &map, &us[0], t, ee, 0.0);
        let exact = 1.0 / (width * t);
        let ratio = mb / exact;
        assert!(ratio > 0.7 && ratio < 1.4, "vm/exact {ratio} vm {mb} exact {exact}");
    }

    /// Long blades (all-three floor) and the raked SWITCHBACK-like genome must mesh and solve.
    #[test]
    fn long_raked_blades_mesh_and_solve() {
        use jarambit_genotype::{bounds, Genotype, Rng};
        use jarambit_phenotype::Phenotype;
        let m = &super::super::TI_6AL_4V;
        let mut r = Rng(77);
        let mut max_nodes = 0;
        for i in 0..40 {
            let mut g = Genotype::random(&mut r);
            g.blade_arc_len = bounds::BLADE_ARC_LEN.1 - 0.2 * (i % 10) as f64;
            g.curve_radius = 40.0 + 1.25 * i as f64;
            g.clamp();
            let p = Phenotype::from_genotype(&g);
            let c = capacities(&p, m, 20.0, (g.serr_inner.depth, g.serr_outer.depth)).unwrap_or_else(|| panic!("no mesh for {:?}", p.blade));
            assert!(c.blade_lat_n.is_finite() && c.blade_lat_n > 0.0 && c.ring_pull_n > 0.0);
            max_nodes = max_nodes.max(c.nodes);
        }
        assert!(max_nodes > 80, "long blades should exceed the old 80-node cap ({max_nodes})");
        let mut g = Genotype::random(&mut Rng(9));
        g.blade_arc_len = 87.55; g.curve_radius = 90.0; g.blade_angle_deg = 13.0; g.ring_wall = 4.5; g.clamp();
        let p = Phenotype::from_genotype(&g);
        assert!(capacities(&p, m, 20.0, (g.serr_inner.depth, g.serr_outer.depth)).is_some());
    }

    /// Ring pull vs net section σ = F / (2 · wall · t), two walls sharing the load.
    /// The surrogate uses sy · wall · t (one wall). Coarse mesh peak may sit a few times above the average.
    #[test]
    fn ring_pull_is_net_section_order() {
        use jarambit_genotype::{Genotype, Rng};
        use jarambit_phenotype::Phenotype;
        let mut r = Rng(11);
        let mut ratios = Vec::new();
        for _ in 0..8 {
            let g = Genotype::random(&mut r);
            let p = Phenotype::from_genotype(&g);
            let m = &super::super::TI_6AL_4V;
            let c = capacities(&p, m, 20.0, (g.serr_inner.depth, g.serr_outer.depth)).expect("mesh");
            let wall = p.ring_outer_r - p.ring_id / 2.0;
            let net = m.yield_at(20.0) * 2.0 * wall * p.thickness;
            ratios.push(c.ring_pull_n / net);
        }
        ratios.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let med = ratios[ratios.len() / 2];
        assert!(med > 0.15 && med < 4.0, "median plate/net-section {med} ratios {ratios:?}");
    }
}
