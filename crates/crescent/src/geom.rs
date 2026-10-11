//! Small 2-D geometry kernel for the crescent phenotype (no external deps).
use std::collections::HashMap;
pub type P2 = (f64, f64);

pub fn dist(a: P2, b: P2) -> f64 { (a.0 - b.0).hypot(a.1 - b.1) }
pub fn sub(a: P2, b: P2) -> P2 { (a.0 - b.0, a.1 - b.1) }
pub fn add(a: P2, b: P2) -> P2 { (a.0 + b.0, a.1 + b.1) }
pub fn mul(a: P2, k: f64) -> P2 { (a.0 * k, a.1 * k) }
pub fn norm(a: P2) -> P2 { let l = a.0.hypot(a.1).max(1e-12); (a.0 / l, a.1 / l) }
pub fn cross(a: P2, b: P2) -> f64 { a.0 * b.1 - a.1 * b.0 }

pub fn signed_area(p: &[P2]) -> f64 {
    let n = p.len(); let mut a = 0.0;
    for i in 0..n { let (x0, y0) = p[i]; let (x1, y1) = p[(i + 1) % n]; a += x0 * y1 - x1 * y0; }
    a / 2.0
}

/// Natural cubic spline through `pts` (open chain), chord-length parameter. Returns samples at
/// spacing ~`ds` (mm of parameter = chord length) and the sample index of every input point.
pub fn natural_spline(pts: &[P2], ds: f64) -> (Vec<P2>, Vec<usize>) {
    let n = pts.len();
    let mut t = vec![0.0; n];
    for i in 1..n { t[i] = t[i - 1] + dist(pts[i - 1], pts[i]).max(1e-6); }
    let solve = |y: &[f64]| -> Vec<f64> {
        // second derivatives M, natural ends M0 = Mn = 0 (Thomas algorithm)
        let mut m = vec![0.0; n];
        if n < 3 { return m; }
        let k = n - 2;
        let (mut a, mut b, mut c, mut d) = (vec![0.0; k], vec![0.0; k], vec![0.0; k], vec![0.0; k]);
        for j in 0..k { let i = j + 1;
            let h0 = t[i] - t[i - 1]; let h1 = t[i + 1] - t[i];
            a[j] = h0; b[j] = 2.0 * (h0 + h1); c[j] = h1;
            d[j] = 6.0 * ((y[i + 1] - y[i]) / h1 - (y[i] - y[i - 1]) / h0);
        }
        for j in 1..k { let w = a[j] / b[j - 1]; b[j] -= w * c[j - 1]; d[j] -= w * d[j - 1]; }
        let mut x = vec![0.0; k];
        x[k - 1] = d[k - 1] / b[k - 1];
        for j in (0..k - 1).rev() { x[j] = (d[j] - c[j] * x[j + 1]) / b[j]; }
        for j in 0..k { m[j + 1] = x[j]; }
        m
    };
    let xs: Vec<f64> = pts.iter().map(|p| p.0).collect();
    let ys: Vec<f64> = pts.iter().map(|p| p.1).collect();
    let (mx, my) = (solve(&xs), solve(&ys));
    let ev = |seg: usize, s: f64, y: &[f64], m: &[f64]| {
        let h = t[seg + 1] - t[seg]; let a = (t[seg + 1] - s) / h; let b = (s - t[seg]) / h;
        a * y[seg] + b * y[seg + 1] + ((a * a * a - a) * m[seg] + (b * b * b - b) * m[seg + 1]) * h * h / 6.0
    };
    let total = t[n - 1];
    let ns = ((total / ds).ceil() as usize).max(n * 4);
    let mut out = Vec::with_capacity(ns + 1);
    let mut idx = vec![0usize; n];
    let mut seg = 0usize;
    for k in 0..=ns {
        let s = total * k as f64 / ns as f64;
        while seg + 2 < n && s > t[seg + 1] { seg += 1; }
        out.push((ev(seg, s, &xs, &mx), ev(seg, s, &ys, &my)));
    }
    for i in 0..n { idx[i] = ((t[i] / total) * ns as f64).round() as usize; }
    (out, idx)
}

/// Cumulative arclength of an open polyline.
pub fn cumlen(p: &[P2]) -> Vec<f64> {
    let mut s = vec![0.0; p.len()];
    for i in 1..p.len() { s[i] = s[i - 1] + dist(p[i - 1], p[i]); }
    s
}

/// Uniform arclength resample of a CLOSED polyline at spacing ~ds.
pub fn resample_closed(p: &[P2], ds: f64) -> Vec<P2> {
    let mut q = p.to_vec(); q.push(p[0]);
    let s = cumlen(&q); let total = *s.last().unwrap();
    let n = ((total / ds).round() as usize).max(8);
    let mut out = Vec::with_capacity(n); let mut j = 0;
    for k in 0..n {
        let target = total * k as f64 / n as f64;
        while j + 1 < q.len() - 1 && s[j + 1] < target { j += 1; }
        let l = (s[j + 1] - s[j]).max(1e-12); let u = ((target - s[j]) / l).clamp(0.0, 1.0);
        out.push((q[j].0 + u * (q[j + 1].0 - q[j].0), q[j].1 + u * (q[j + 1].1 - q[j].1)));
    }
    out
}

/// Densify any polyline (closed if `closed`) so no segment exceeds `h`.
pub fn densify(p: &[P2], h: f64, closed: bool) -> Vec<P2> {
    let n = p.len(); let mut out = Vec::with_capacity(n * 2);
    let m = if closed { n } else { n - 1 };
    for i in 0..m { let a = p[i]; let b = p[(i + 1) % n]; let k = ((dist(a, b) / h).ceil() as usize).max(1);
        for j in 0..k { let u = j as f64 / k as f64; out.push((a.0 + u * (b.0 - a.0), a.1 + u * (b.1 - a.1))); } }
    if !closed { out.push(p[n - 1]); }
    out
}

/// Douglas-Peucker on a CLOSED ring (keeps point 0 and the farthest point as anchors).
pub fn dp_closed(p: &[P2], eps: f64) -> Vec<P2> {
    let n = p.len(); if n < 8 { return p.to_vec(); }
    let far = (0..n).max_by(|&a, &b| dist(p[0], p[a]).partial_cmp(&dist(p[0], p[b])).unwrap()).unwrap();
    let mut keep = vec![false; n]; keep[0] = true; keep[far] = true;
    let mut stack = vec![(0usize, far), (far, n)];
    while let Some((a, b)) = stack.pop() {
        if b <= a + 1 { continue; }
        let pa = p[a]; let pb = p[b % n];
        let mut best = (0.0, a);
        for i in a + 1..b { let d = seg_dist(p[i], pa, pb); if d > best.0 { best = (d, i); } }
        if best.0 > eps { keep[best.1] = true; stack.push((a, best.1)); stack.push((best.1, b)); }
    }
    (0..n).filter(|&i| keep[i]).map(|i| p[i]).collect()
}

pub fn seg_dist(q: P2, a: P2, b: P2) -> f64 {
    let (dx, dy) = (b.0 - a.0, b.1 - a.1); let l2 = dx * dx + dy * dy;
    let t = if l2 > 0.0 { (((q.0 - a.0) * dx + (q.1 - a.1) * dy) / l2).clamp(0.0, 1.0) } else { 0.0 };
    dist(q, (a.0 + t * dx, a.1 + t * dy))
}

/// Uniform-grid nearest-point index over a dense point cloud.
pub struct Nn { h: f64, map: HashMap<(i64, i64), Vec<P2>> }
impl Nn {
    pub fn new(pts: &[P2], h: f64) -> Self {
        let mut map: HashMap<(i64, i64), Vec<P2>> = HashMap::new();
        for &q in pts { map.entry(((q.0 / h).floor() as i64, (q.1 / h).floor() as i64)).or_default().push(q); }
        Nn { h, map }
    }
    /// Distance to the nearest point, or INFINITY if none within `rmax`.
    pub fn nearest(&self, q: P2, rmax: f64) -> f64 {
        let (ci, cj) = ((q.0 / self.h).floor() as i64, (q.1 / self.h).floor() as i64);
        let kmax = (rmax / self.h).ceil() as i64 + 1;
        let mut best = f64::INFINITY;
        for k in 0..=kmax {
            if (k as f64 - 1.0) * self.h > best { break; }
            for i in ci - k..=ci + k { for j in cj - k..=cj + k {
                if (i - ci).abs() != k && (j - cj).abs() != k { continue; }
                if let Some(v) = self.map.get(&(i, j)) { for &p in v { let d = dist(p, q); if d < best { best = d; } } }
            } }
        }
        if best <= rmax { best } else { f64::INFINITY }
    }
}

/// Symmetric Hausdorff distance between two point clouds (dense samplings of curves).
pub fn hausdorff(a: &[P2], b: &[P2]) -> f64 {
    let na = Nn::new(a, 2.0); let nb = Nn::new(b, 2.0);
    let ab = a.iter().map(|&q| nb.nearest(q, 400.0)).fold(0.0, f64::max);
    let ba = b.iter().map(|&q| na.nearest(q, 400.0)).fold(0.0, f64::max);
    ab.max(ba)
}

/// Signed Menger curvature at every point of a CLOSED uniformly-sampled ring, neighbours +-k.
/// Positive = turning with the ring orientation (convex for a solid's outer boundary).
pub fn curvature_closed(p: &[P2], k: usize) -> Vec<f64> {
    let n = p.len(); let orient = signed_area(p).signum();
    (0..n).map(|i| {
        let a = p[(i + n - k) % n]; let b = p[i]; let c = p[(i + k) % n];
        let cr = cross(sub(b, a), sub(c, b));
        let den = dist(a, b) * dist(b, c) * dist(a, c);
        if den < 1e-12 { 0.0 } else { orient * 2.0 * cr / den }
    }).collect()
}

pub fn point_in_poly(q: P2, poly: &[P2]) -> bool {
    let mut c = false; let n = poly.len(); let mut j = n - 1;
    for i in 0..n { let (xi, yi) = poly[i]; let (xj, yj) = poly[j];
        if ((yi > q.1) != (yj > q.1)) && (q.0 < (xj - xi) * (q.1 - yi) / (yj - yi) + xi) { c = !c; }
        j = i; }
    c
}

pub fn circle(c: P2, r: f64, n: usize, cw: bool) -> Vec<P2> {
    (0..n).map(|i| { let a = 2.0 * std::f64::consts::PI * i as f64 / n as f64 * if cw { -1.0 } else { 1.0 }; (c.0 + r * a.cos(), c.1 + r * a.sin()) }).collect()
}

pub fn bezier(p: [P2; 4], n: usize) -> Vec<P2> {
    (0..n).map(|i| { let t = i as f64 / (n - 1) as f64; let u = 1.0 - t;
        let w = [u * u * u, 3.0 * u * u * t, 3.0 * u * t * t, t * t * t];
        (w.iter().zip(&p).map(|(w, q)| w * q.0).sum(), w.iter().zip(&p).map(|(w, q)| w * q.1).sum()) }).collect()
}

/// Tapered slot with round ends along centreline `c`, widths w0 -> w1 (exponent 0.8, as gen.py).
pub fn taper_slot(c: &[P2], w0: f64, w1: f64) -> Vec<P2> {
    let n = c.len(); use std::f64::consts::PI;
    let tan: Vec<P2> = (0..n).map(|i| norm(sub(c[(i + 1).min(n - 1)], c[i.saturating_sub(1)]))).collect();
    let nrm: Vec<P2> = tan.iter().map(|t| (-t.1, t.0)).collect();
    let w: Vec<f64> = (0..n).map(|i| (w0 + (w1 - w0) * (i as f64 / (n - 1) as f64).powf(0.8)) / 2.0).collect();
    let mut out = Vec::new();
    for i in 0..n { out.push(add(c[i], mul(nrm[i], w[i]))); }
    let (ce, te, ne, re) = (c[n - 1], tan[n - 1], nrm[n - 1], w[n - 1]);
    for k in 1..24 { let b = PI * k as f64 / 24.0; out.push(add(ce, add(mul(ne, re * b.cos()), mul(te, re * b.sin())))); }
    for i in (0..n).rev() { out.push(sub(c[i], mul(nrm[i], w[i]))); }
    let (c0, t0, n0, r0) = (c[0], tan[0], nrm[0], w[0]);
    for k in 1..24 { let b = PI * k as f64 / 24.0; out.push(add(c0, add(mul(n0, -r0 * b.cos()), mul(t0, -r0 * b.sin())))); }
    out
}

/// Min distance from any point of `a` to the polyline ring `b`.
pub fn min_ring_dist(a: &[P2], b: &[P2]) -> f64 {
    let nb = Nn::new(&densify(b, 0.25, true), 2.0);
    a.iter().map(|&q| nb.nearest(q, 200.0)).fold(f64::INFINITY, f64::min)
}

/// True if any two non-adjacent edges of the CLOSED ring cross (grid-bucketed).
pub fn self_intersects(p: &[P2]) -> bool {
    let n = p.len(); if n < 4 { return false; }
    let h = 2.0;
    let mut map: HashMap<(i64, i64), Vec<usize>> = HashMap::new();
    for i in 0..n { let (a, b) = (p[i], p[(i + 1) % n]);
        let (x0, x1) = ((a.0.min(b.0) / h).floor() as i64, (a.0.max(b.0) / h).floor() as i64);
        let (y0, y1) = ((a.1.min(b.1) / h).floor() as i64, (a.1.max(b.1) / h).floor() as i64);
        for x in x0..=x1 { for y in y0..=y1 { map.entry((x, y)).or_default().push(i); } } }
    let cr = |o: P2, a: P2, b: P2| (a.0 - o.0) * (b.1 - o.1) - (a.1 - o.1) * (b.0 - o.0);
    for v in map.values() { for x in 0..v.len() { for y in x + 1..v.len() {
        let (i, j) = (v[x], v[y]);
        if (i + 1) % n == j || (j + 1) % n == i || i == j { continue; }
        let (a, b, c, d) = (p[i], p[(i + 1) % n], p[j], p[(j + 1) % n]);
        let (d1, d2, d3, d4) = (cr(c, d, a), cr(c, d, b), cr(a, b, c), cr(a, b, d));
        if d1 * d2 < -1e-12 && d3 * d4 < -1e-12 { return true; }
    } } }
    false
}
