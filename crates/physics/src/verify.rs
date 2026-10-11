//! Closed-form checks for the detailed plate (`fine`). Each returns model/theory ratios at one
//! mesh level so `jarambit fem-verify` can tabulate a convergence sequence and the unit tests
//! can gate a mid level. Units mm / N / MPa.
use super::fine::{mesh_domain, mesh_domain_pts, Plate, T6, P2};
use std::f64::consts::PI;

const E: f64 = 113_800.0;

fn rect(x0: f64, y0: f64, w: f64, h: f64, rot_deg: f64) -> Vec<P2> {
    let (c, s) = (rot_deg.to_radians().cos(), rot_deg.to_radians().sin());
    [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)].iter().map(|&(x, y)| (c * x - s * y, s * x + c * y)).collect()
}
fn circle(cx: f64, cy: f64, r: f64, n: usize) -> Vec<P2> {
    (0..n).map(|i| { let a = 2.0 * PI * i as f64 / n as f64; (cx + r * a.cos(), cy + r * a.sin()) }).collect()
}

#[derive(Clone, Debug)]
pub struct Check { pub name: &'static str, pub max_area: f64, pub nodes: usize, pub model: f64, pub theory: f64 }
impl Check { pub fn ratio(&self) -> f64 { self.model / self.theory } }

/// Euler-Bernoulli cantilever (nu = 0) on an unstructured mesh rotated by `rot_deg`.
/// Returns [tip deflection, mid-span bending stress] checks.
pub fn cantilever(max_area: f64, rot_deg: f64) -> Option<[Check; 2]> {
    let (l, b, t) = (60.0, 10.0, 3.0);
    let poly = rect(0.0, 0.0, l, b, rot_deg);
    let mesh = mesh_domain(&poly, &[], max_area)?;
    let (c, s) = (rot_deg.to_radians().cos(), rot_deg.to_radians().sin());
    let local = |q: P2| (c * q.0 + s * q.1, -s * q.0 + c * q.1);
    let pl = Plate::new(mesh, t, E, 0.0);
    let n = pl.n();
    let xl: Vec<P2> = pl.mesh.xy.iter().map(|&q| local(q)).collect();
    let mut fixed = vec![false; n * 5];
    for i in 0..n { if xl[i].0.abs() < 1e-6 { for k in 0..5 { fixed[i * 5 + k] = true; } } }
    let tips: Vec<usize> = (0..n).filter(|&i| (xl[i].0 - l).abs() < 1e-6).collect();
    // consistent edge load: each tip node takes half of each adjacent segment
    let mut ys: Vec<(f64, usize)> = tips.iter().map(|&i| (xl[i].1, i)).collect();
    ys.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let mut f = vec![0.0; n * 5];
    for k in 0..ys.len() {
        let lo = if k > 0 { (ys[k].0 - ys[k - 1].0) / 2.0 } else { 0.0 };
        let hi = if k + 1 < ys.len() { (ys[k + 1].0 - ys[k].0) / 2.0 } else { 0.0 };
        f[ys[k].1 * 5 + 2] = (lo + hi) / b;
    }
    let sys = pl.system(&fixed)?;
    let u = pl.solve(&sys, &f);
    let w: f64 = tips.iter().map(|&i| u[i * 5 + 2]).sum::<f64>() / tips.len() as f64;
    let i_sec = b * t * t * t / 12.0;
    let w_th = l * l * l / (3.0 * E * i_sec);
    let (_, sb) = pl.stresses(&u);
    let (mut num, mut den) = (0.0, 0.0);
    for e in 0..pl.mesh.tris.len() {
        let x = local(pl.centroid(e)).0;
        if x > 0.3 * l && x < 0.7 * l { let a = pl.area(e); num += a * sb[e] / (6.0 * (l - x) / (b * t * t)); den += a; }
    }
    Some([
        Check { name: "cantilever tip deflection", max_area, nodes: n, model: w, theory: w_th },
        Check { name: "cantilever mid-span stress", max_area, nodes: n, model: num / den, theory: 1.0 },
    ])
}

/// Clamped square plate a x a, nu = 0.3 (Timoshenko & Woinowsky-Krieger Tables 35/40):
/// central point load w = 0.00560 P a^2 / D; uniform load w = 0.00126 q a^4 / D,
/// edge-midpoint moment |M| = 0.0513 q a^2. At a clamped edge the along-edge curvature is zero,
/// so sigma = (s, nu s, 0) with s = 6M/t^2 and von Mises = s sqrt(1 - nu + nu^2).
pub fn clamped_plate(max_area: f64) -> Option<[Check; 3]> {
    let (a, t, nu) = (40.0, 2.0, 0.3);
    let poly = rect(-a / 2.0, -a / 2.0, a, a, 0.0);
    let mesh = mesh_domain_pts(&poly, &[], &[(0.0, 0.0)], max_area)?;
    let pl = Plate::new(mesh, t, E, nu);
    let n = pl.n();
    let d = E * t * t * t / (12.0 * (1.0 - nu * nu));
    let mut fixed = vec![false; n * 5];
    for i in 0..n { if pl.mesh.on_outer[i] { for k in 0..5 { fixed[i * 5 + k] = true; } } }
    let sys = pl.system(&fixed)?;
    let ci = (0..n).min_by(|&i, &j| pl.mesh.xy[i].0.hypot(pl.mesh.xy[i].1).partial_cmp(&pl.mesh.xy[j].0.hypot(pl.mesh.xy[j].1)).unwrap())?;
    let mut f = vec![0.0; n * 5];
    f[ci * 5 + 2] = 1.0;
    let u = pl.solve(&sys, &f);
    let wp = u[ci * 5 + 2];
    let mut fq = vec![0.0; n * 5];
    for (e, tri) in pl.mesh.tris.iter().enumerate() { let ar = pl.area(e); for &v in tri { fq[v * 5 + 2] += ar / 3.0; } }
    let uq = pl.solve(&sys, &fq);
    let wq = uq[ci * 5 + 2];
    let (_, sb) = pl.stresses(&uq);
    let smax = sb.iter().cloned().fold(0.0, f64::max);
    Some([
        Check { name: "clamped plate point-load deflection", max_area, nodes: n, model: wp, theory: 0.00560 * a * a / d },
        Check { name: "clamped plate uniform-load deflection", max_area, nodes: n, model: wq, theory: 0.00126 * a.powi(4) / d },
        Check { name: "clamped plate edge von Mises (uniform)", max_area, nodes: n, model: smax, theory: 6.0 * 0.0513 * a * a / (t * t) * (1.0 - nu + nu * nu).sqrt() },
    ])
}

/// Curved bar in pure in-plane bending (Timoshenko & Goodier, Art. 29, Golovin): quarter annulus
/// a = 20, b = 30 mm, clamped at theta = 0, end couple at theta = 90 deg. Peak sigma_theta at r = a.
pub fn curved_beam(max_area: f64) -> Option<Check> {
    let (ra, rb, t, mm) = (20.0, 30.0, 1.0, 1000.0);
    let nseg = ((PI / 2.0 * rb) / (0.6 * max_area.sqrt())).ceil() as usize + 8;
    let mut poly: Vec<P2> = Vec::new();
    for i in 0..=nseg { let th = PI / 2.0 * i as f64 / nseg as f64; poly.push((rb * th.cos(), rb * th.sin())); }
    for i in (0..=nseg).rev() { let th = PI / 2.0 * i as f64 / nseg as f64; poly.push((ra * th.cos(), ra * th.sin())); }
    let mesh = mesh_domain(&poly, &[], max_area)?;
    let pl = T6::new(&mesh, t, E, 0.3);
    let n = pl.n();
    let mut fixed = vec![false; n * 2];
    for i in 0..n { if pl.xy[i].1.abs() < 1e-6 { fixed[i * 2] = true; fixed[i * 2 + 1] = true; } }
    let big_n = (rb * rb - ra * ra).powi(2) - 4.0 * ra * ra * rb * rb * (rb / ra).ln().powi(2);
    let sig = |r: f64| -4.0 * mm / (t * big_n) * (-(ra * ra * rb * rb) / (r * r) * (rb / ra).ln() + rb * rb * (r / rb).ln() + ra * ra * (ra / r).ln() + rb * rb - ra * ra);
    // Golovin end traction sigma_theta(r) on the theta = 90 deg edge (x = 0), consistent T6 load
    // via Simpson weights per edge (exact for the quadratic interpolant).
    let mut f = vec![0.0; n * 2];
    let mut seen = std::collections::HashSet::new();
    for tr in &pl.tris {
        for (a, b, m) in [(tr[0], tr[1], tr[3]), (tr[1], tr[2], tr[4]), (tr[2], tr[0], tr[5])] {
            if pl.xy[a].0.abs() > 1e-6 || pl.xy[b].0.abs() > 1e-6 || !seen.insert((a.min(b), a.max(b))) { continue; }
            let l = (pl.xy[a].1 - pl.xy[b].1).abs();
            for (node, w) in [(a, 1.0 / 6.0), (b, 1.0 / 6.0), (m, 4.0 / 6.0)] { f[node * 2] += -sig(pl.xy[node].1) * t * l * w; }
        }
    }
    let sys = pl.system(&fixed)?;
    let u = pl.solve(&sys, &f);
    let nod = pl.nodal_stress(&u);
    // hoop stress at inner-fibre nodes (r = a) between 35 and 55 deg: mean
    let (mut s, mut cnt) = (0.0, 0.0);
    for i in 0..n {
        let q = pl.xy[i];
        let (r, th) = (q.0.hypot(q.1), q.1.atan2(q.0));
        if (r - ra).abs() > 1e-3 || th < 35f64.to_radians() || th > 55f64.to_radians() { continue; }
        let (cs, sn) = (th.cos(), th.sin());
        s += nod[i][0] * sn * sn + nod[i][1] * cs * cs - 2.0 * nod[i][2] * sn * cs; cnt += 1.0;
    }
    if cnt < 1.0 { return None; }
    let (icpt, slope) = (s / cnt, 0.0);
    Some(Check { name: "curved bar inner-fibre stress (Golovin, T6)", max_area, nodes: n, model: (icpt + slope * ra).abs(), theory: sig(ra).abs() })
}

/// Finite-width strip with a central hole in tension, d/W = 0.2. Heywood: Kt_net = 2 + (1 - d/W)^3,
/// Kt_gross = Kt_net / (1 - d/W) = 3.14 (Peterson's chart 3.14).
pub fn hole_kt(max_area: f64) -> Option<Check> {
    let (w, l, d, t) = (50.0, 200.0, 10.0, 1.0);
    let poly = rect(-l / 2.0, -w / 2.0, l, w, 0.0);
    let nh = ((PI * d) / (0.35 * max_area.sqrt())).ceil().max(32.0) as usize;
    let hole = circle(0.0, 0.0, d / 2.0, nh);
    let mesh = mesh_domain(&poly, &[hole.clone()], max_area)?;
    let pl = T6::new(&mesh, t, E, 0.3);
    let n = pl.n();
    let mut fixed = vec![false; n * 2];
    for i in 0..n { if (pl.xy[i].0 + l / 2.0).abs() < 1e-6 { fixed[i * 2] = true; } }
    let pin = (0..n).filter(|&i| (pl.xy[i].0 + l / 2.0).abs() < 1e-6).min_by(|&a, &b| pl.xy[a].1.abs().partial_cmp(&pl.xy[b].1.abs()).unwrap())?;
    fixed[pin * 2 + 1] = true;
    let s0 = 1.0;
    let mut f = vec![0.0; n * 2];
    pl.edge_traction(&|i| (pl.xy[i].0 - l / 2.0).abs() < 1e-6, (s0 * t, 0.0), &mut f);
    let sys = pl.system(&fixed)?;
    let u = pl.solve(&sys, &f);
    let nod = pl.nodal_stress(&u);
    let peak = (0..n).filter(|&i| (pl.xy[i].0.hypot(pl.xy[i].1) - d / 2.0).abs() < 1e-3).map(|i| nod[i][0]).fold(0.0, f64::max);
    let kt_net = 2.0 + (1.0 - d / w).powi(3);
    Some(Check { name: "hole Kt_gross (Heywood, d/W=0.2, T6)", max_area, nodes: n, model: peak / s0, theory: kt_net / (1.0 - d / w) })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[ignore]
    fn print_levels() {
        for a in [4.0, 2.0, 1.0, 0.5, 0.25] {
            let t0 = std::time::Instant::now();
            let mut v: Vec<Check> = Vec::new();
            if let Some(c) = cantilever(a, 0.0) { v.extend(c); }
            if let Some(c) = cantilever(a, 33.0) { v.extend(c); }
            if let Some(c) = clamped_plate(a) { v.extend(c); }
            if let Some(c) = curved_beam(a) { v.push(c); }
            if let Some(c) = hole_kt(a) { v.push(c); }
            for c in &v { println!("A={a:5.2} n={:6} {:45} model={:.5e} theory={:.5e} ratio={:.4}", c.nodes, c.name, c.model, c.theory, c.ratio()); }
            println!("  ({:.2}s)", t0.elapsed().as_secs_f64());
        }
    }
}
