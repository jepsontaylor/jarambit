//! Genotype -> 2D outline polygon (mm) -> watertight extrusion (STL + faceted STEP).
//! Frame: blade arc centre at origin; blade heel at angle PI (x = -r), blade sweeps up/over;
//! ricasso (holder thickness lands) below y = 0, shoulders step in to the grip, grip runs
//! down -y to the ring neck, finger ring below.
use jarambit_genotype::{limits, Genotype};
use std::f64::consts::PI;
mod mesh;
pub use mesh::{edge_census, triangulate, SolidMesh};

pub type P2 = (f64, f64);

/// The three SWITCHBACK Rev C.2 blade-length measures plus context (all mm / deg).
#[derive(Clone, Debug, Default)]
pub struct BladeMetrics {
    /// Straight-line distance from tip to the farther edge heel (start of sharpening).
    pub tip_to_heel: f64,
    /// Horizontal (perpendicular-to-grip-axis) extent of the blade, heel to farthest point.
    pub horizontal_reach: f64,
    /// Longest sharpened-edge arc (max of outer/convex and inner/concave edge), heel to tip, unserrated centreline.
    pub sharpened_arc: f64,
    pub sharpened_arc_outer: f64,
    pub sharpened_arc_inner: f64,
    /// Vertical rise of blade above the guard line (logged, not limited).
    pub vertical_rise: f64,
    pub sweep_deg: f64,
    /// Heel->tip chord elevation above the horizontal after rake (deg). The blade-angle knob.
    pub chord_angle_deg: f64,
    /// Forward rake actually applied about the inner heel (deg, >= 0).
    pub rake_deg: f64,
    /// Blade tip point (global frame, mm).
    pub tip: (f64, f64),
}
impl BladeMetrics {
    pub fn max_measure(&self) -> f64 { self.tip_to_heel.max(self.horizontal_reach).max(self.sharpened_arc) }
}

#[derive(Clone, Debug)]
pub struct Phenotype {
    /// Outer boundary of the single solid profile.
    pub outline: Vec<P2>,
    /// Finger ring hole. Exactly one hole => genus-1 connected solid.
    pub ring_hole: Vec<P2>,
    pub thickness: f64,
    pub brand_pad: [P2; 4],
    pub inner_teeth: usize,
    pub outer_teeth: usize,
    pub ring_center: P2,
    pub ring_outer_r: f64,
    pub ring_id: f64,
    pub blade: BladeMetrics,
    /// Grip measured ring-neck to guard (shoulder), mm.
    pub grip_len: f64,
    pub handle_w: f64,
    pub ricasso_len: f64,
    pub shoulder_w: f64,
    /// (y position, depth) of holder retention detent on the grip.
    pub detent: (f64, f64),
    /// Bounding box (min, max).
    pub bbox: (P2, P2),
    /// Blade rake: the blade (arc centred on the origin in its local frame) is rotated by
    /// `blade_rot` rad (CCW +, so forward rake is negative) about `blade_pivot` (the inner heel).
    pub blade_pivot: P2,
    pub blade_rot: f64,
}

fn serrated_arc(r: f64, a0: f64, a1: f64, pitch: f64, depth: f64, inward: bool) -> (Vec<P2>, usize) {
    let len = (a1 - a0).abs() * r;
    let teeth = (len / pitch).floor().max(1.0) as usize;
    let n = teeth * 8;
    let mut v = Vec::with_capacity(n + 1);
    for i in 0..=n {
        let t = i as f64 / n as f64;
        let a = a0 + (a1 - a0) * t;
        let d = depth * (t * teeth as f64 * PI).sin().abs();
        let rr = if inward { r + d } else { r - d };
        v.push((rr * a.cos(), rr * a.sin()));
    }
    (v, teeth)
}

fn dist(a: P2, b: P2) -> f64 { ((a.0 - b.0).powi(2) + (a.1 - b.1).powi(2)).sqrt() }

impl Phenotype {
    pub fn from_genotype(g: &Genotype) -> Self {
        let sweep = g.sweep_deg().to_radians();
        let (r_out, r_in, r_mid) = (g.r_out(), g.r_in(), g.curve_radius);
        let a0 = PI; let a1 = PI - sweep;
        let (outer, to) = serrated_arc(r_out, a0, a1, g.serr_outer.pitch, g.serr_outer.depth, false);
        let (inner, ti) = serrated_arc(r_in, a0, a1, g.serr_inner.pitch, g.serr_inner.depth, true);
        let tip0 = (r_mid * a1.cos() + 6.0 * a1.sin(), r_mid * a1.sin() - 6.0 * a1.cos());

        // --- blade angle knob: rake the whole blade FORWARD about the inner heel so the
        // heel->tip chord sits at g.blade_angle_deg above the guard line. Never rakes backward
        // (that would fold the outer heel into the ricasso), so legacy genomes are unchanged.
        let pivot = (-r_in, 0.0);
        let chord0 = (tip0.1).atan2(tip0.0 + r_out);
        let rot = (g.blade_angle_deg.to_radians() - chord0).min(0.0);
        let (cr, sr) = (rot.cos(), rot.sin());
        let rt = |q: P2| { let (x, y) = (q.0 - pivot.0, q.1 - pivot.1); (pivot.0 + cr * x - sr * y, pivot.1 + sr * x + cr * y) };
        let outer: Vec<P2> = outer.into_iter().map(rt).collect();
        let inner: Vec<P2> = inner.into_iter().map(rt).collect();
        let tip = rt(tip0);

        // --- blade metrics (unserrated centreline of each sharpened edge) ---
        let heel_o = rt((-r_out, 0.0)); let heel_i = (-r_in, 0.0);
        let end_o = rt((r_out * a1.cos(), r_out * a1.sin())); let end_i = rt((r_in * a1.cos(), r_in * a1.sin()));
        let arc_o = r_out * sweep + dist(end_o, tip);
        let arc_i = r_in * sweep + dist(end_i, tip);
        let mut xs: Vec<f64> = vec![tip.0];
        let mut ys: Vec<f64> = vec![tip.1];
        for i in 0..=256 { let a = a0 + (a1 - a0) * i as f64 / 256.0;
            for r in [r_out, r_in] { let q = rt((r * a.cos(), r * a.sin())); xs.push(q.0); ys.push(q.1); } }
        let xmax = xs.iter().cloned().fold(f64::MIN, f64::max);
        let ymax = ys.iter().cloned().fold(f64::MIN, f64::max);
        let blade = BladeMetrics {
            tip_to_heel: dist(tip, heel_o).max(dist(tip, heel_i)),
            // measured from the spine/ricasso line at the heel (x = -r_out), as before the knob
            horizontal_reach: xmax - (-r_out),
            sharpened_arc: arc_o.max(arc_i), sharpened_arc_outer: arc_o, sharpened_arc_inner: arc_i,
            vertical_rise: ymax.max(0.0), sweep_deg: sweep.to_degrees(),
            chord_angle_deg: (tip.1 - heel_o.1).atan2(tip.0 - heel_o.0).to_degrees(),
            rake_deg: -rot.to_degrees(), tip,
        };

        // --- ricasso / shoulders / grip / detent / ring ---
        let h = &g.holder;
        let hx0 = -r_out; let hx1 = -r_in; let xm = (hx0 + hx1) / 2.0;
        let hw = g.handle_w(); let hxl = xm - hw / 2.0; let hxr = xm + hw / 2.0;
        let y_sh = -h.ricasso_len;                       // guard / shoulder line
        let y_neck = y_sh - g.grip_len;                   // ring neck
        let ring_r_out = g.ring_id / 2.0 + g.ring_wall;
        let al = (-(hw / 2.0) / ring_r_out).acos();       // left handle side meets ring (upper-left)
        let ring_c = (xm, y_neck - ring_r_out * al.sin());
        let y_det = y_sh - h.detent_pos * g.grip_len; let dd = h.detent_depth;
        // grip-ring neck: optional taper (flare) + tangent fillet into the ring OD (left side,
        // mirrored about x = xm for the right side). Legacy genomes: sharp corner at (hxl, y_neck).
        let (neck_l, al2) = neck_flank(xm, hw, y_neck, ring_c, ring_r_out, g.neck_flare, g.neck_flare_len, g.neck_fillet_r);
        let ar2 = PI - al2;

        let mut outline: Vec<P2> = Vec::new();
        outline.push((hx0, 0.0)); outline.push((hx0, y_sh));            // ricasso land, left
        outline.push((hxl, y_sh));                                        // left shoulder
        outline.push((hxl, y_det + 1.5 * dd)); outline.push((hxl + dd, y_det)); outline.push((hxl, y_det - 1.5 * dd)); // detent V
        outline.extend(neck_l.iter().copied());                           // neck flank / fillet, left (top -> ring)
        for i in 1..144 { let a = al2 + (2.0 * PI + ar2 - al2) * i as f64 / 144.0; outline.push((ring_c.0 + ring_r_out * a.cos(), ring_c.1 + ring_r_out * a.sin())); }
        outline.extend(neck_l.iter().rev().map(|q| (2.0 * xm - q.0, q.1)));  // mirrored, ring -> top
        outline.push((hxr, y_sh));           // right grip side
        outline.push((hx1, y_sh)); outline.push((hx1, 0.0));              // right shoulder + ricasso land
        outline.extend(inner.iter().skip(1));                             // concave serrated edge heel->tip
        outline.push(tip);
        outline.extend(outer.iter().rev().take(outer.len() - 1));         // convex serrated edge tip->heel
        let outline = round_concave(&outline, limits::MIN_INSIDE_RADIUS_MM);
        let ring_hole: Vec<P2> = (0..128).map(|i| { let a = -2.0 * PI * i as f64 / 128.0; (ring_c.0 + g.ring_id / 2.0 * a.cos(), ring_c.1 + g.ring_id / 2.0 * a.sin()) }).collect();

        let pw = g.brand_pad_w; let pl = g.brand_pad_l;
        let py = y_neck + 3.0 + pl / 2.0;
        let brand_pad = [(xm - pw / 2.0, py - pl / 2.0), (xm + pw / 2.0, py - pl / 2.0), (xm + pw / 2.0, py + pl / 2.0), (xm - pw / 2.0, py + pl / 2.0)];
        let (mut lo, mut hi) = ((f64::MAX, f64::MAX), (f64::MIN, f64::MIN));
        for p in &outline { lo.0 = lo.0.min(p.0); lo.1 = lo.1.min(p.1); hi.0 = hi.0.max(p.0); hi.1 = hi.1.max(p.1); }
        Phenotype { outline, ring_hole, thickness: g.thickness, brand_pad, inner_teeth: ti, outer_teeth: to,
            ring_center: ring_c, ring_outer_r: ring_r_out, ring_id: g.ring_id, blade, grip_len: y_sh - y_neck,
            handle_w: hw, ricasso_len: h.ricasso_len, shoulder_w: h.shoulder_w, detent: (y_det, dd), bbox: (lo, hi),
            blade_pivot: pivot, blade_rot: rot }
    }

    /// Map a global point into the un-raked blade frame (arc centred on the origin).
    pub fn to_blade_local(&self, q: P2) -> P2 {
        let (c, s) = (self.blade_rot.cos(), self.blade_rot.sin());
        let (x, y) = (q.0 - self.blade_pivot.0, q.1 - self.blade_pivot.1);
        (self.blade_pivot.0 + c * x + s * y, self.blade_pivot.1 - s * x + c * y)
    }
    /// Inverse of `to_blade_local`.
    pub fn from_blade_local(&self, q: P2) -> P2 {
        let (c, s) = (self.blade_rot.cos(), self.blade_rot.sin());
        let (x, y) = (q.0 - self.blade_pivot.0, q.1 - self.blade_pivot.1);
        (self.blade_pivot.0 + c * x - s * y, self.blade_pivot.1 + s * x + c * y)
    }

    pub fn area_mm2(&self) -> f64 { shoelace(&self.outline).abs() - shoelace(&self.ring_hole).abs() }
    pub fn mass_g(&self, density_g_cm3: f64) -> f64 { self.area_mm2() * self.thickness * density_g_cm3 / 1000.0 }

    /// Watertight extrusion: ear-cut caps plus side walls. See `mesh`.
    pub fn to_ascii_stl(&self, name: &str) -> String { mesh::stl_string(self, name) }

    /// Closed faceted MANIFOLD_SOLID_BREP (AP214 planar faces), same mesh as the STL.
    pub fn to_step(&self, name: &str) -> String { mesh::step_string(self, name) }

    /// Historical name. Emits the B-rep solid, not a polyline stub.
    pub fn to_step_stub(&self, name: &str) -> String { self.to_step(name) }

    /// Outline as SVG path (for docs figures).
    pub fn to_svg(&self) -> String {
        let ((x0, y0), (x1, y1)) = self.bbox; let pad = 5.0;
        let path = |p: &[P2]| { let mut s = String::new(); for (i, q) in p.iter().enumerate() { s.push_str(&format!("{}{:.2},{:.2} ", if i == 0 { "M" } else { "L" }, q.0, -q.1)); } s.push('Z'); s };
        let bp = self.brand_pad.to_vec();
        format!("<svg xmlns='http://www.w3.org/2000/svg' viewBox='{:.1} {:.1} {:.1} {:.1}' width='400'><path d='{} {}' fill='#9aa' fill-rule='evenodd' stroke='#333' stroke-width='0.3'/><path d='{}' fill='none' stroke='#c33' stroke-width='0.3'/></svg>",
            x0 - pad, -y1 - pad, x1 - x0 + 2.0 * pad, y1 - y0 + 2.0 * pad, path(&self.outline), path(&self.ring_hole), path(&bp))
    }
}

/// Round every concave corner (turn > 15 deg against the polygon's orientation) with a tangent arc
/// of radius `r`, shrunk so each tangent length stays <= 0.45 of both adjacent edges.
pub fn round_concave(poly: &[P2], r: f64) -> Vec<P2> {
    let n = poly.len();
    if n < 4 || r <= 0.0 { return poly.to_vec(); }
    let orient = shoelace(poly).signum();
    let mut out = Vec::with_capacity(n * 2);
    for i in 0..n {
        let (a, b, c) = (poly[(i + n - 1) % n], poly[i], poly[(i + 1) % n]);
        let (l1, l2) = (dist(a, b), dist(b, c));
        if l1 < 1e-9 || l2 < 1e-9 { out.push(b); continue; }
        let u = ((b.0 - a.0) / l1, (b.1 - a.1) / l1);
        let v = ((c.0 - b.0) / l2, (c.1 - b.1) / l2);
        let cr = u.0 * v.1 - u.1 * v.0;
        let phi = cr.atan2(u.0 * v.0 + u.1 * v.1).abs();
        if cr * orient >= 0.0 || phi < 15f64.to_radians() || phi > 175f64.to_radians() { out.push(b); continue; }
        let tl = (r * (phi / 2.0).tan()).min(0.45 * l1.min(l2));
        let re = tl / (phi / 2.0).tan();
        let t1 = (b.0 - u.0 * tl, b.1 - u.1 * tl);
        let sg = cr.signum();
        let nrm = (-u.1 * sg, u.0 * sg);
        let o = (t1.0 + nrm.0 * re, t1.1 + nrm.1 * re);
        let th1 = (t1.1 - o.1).atan2(t1.0 - o.0);
        let k = ((phi / 5f64.to_radians()).ceil() as usize).max(3);
        for j in 0..=k { let th = th1 + sg * phi * j as f64 / k as f64; out.push((o.0 + re * th.cos(), o.1 + re * th.sin())); }
    }
    out
}

/// Left grip-ring neck flank from the top of the taper down to the ring OD, ending ON the ring
/// circle, plus the polar angle (about the ring centre) of that end point. Material is to the +x
/// side of the flank. `flare` widens the flank linearly over `flare_len` above the neck; `fillet`
/// rounds the flank->ring corner with a circle tangent to both (shrunk until it fits).
fn neck_flank(xm: f64, hw: f64, y_neck: f64, c: P2, rr: f64, flare: f64, flare_len: f64, fillet: f64) -> (Vec<P2>, f64) {
    let hxl = xm - hw / 2.0;
    let mut pts: Vec<P2> = Vec::new();
    // flank line through A with unit direction d (downward), inward normal n (+x side)
    let (a, d) = if flare > 1e-9 && hw / 2.0 + flare < 0.9 * rr {
        // taper ends ON the ring OD at half-width hw/2 + flare, and starts flare_len above that
        let alf = (-(hw / 2.0 + flare) / rr).acos();
        let b = (xm - (hw / 2.0 + flare), c.1 + rr * alf.sin());
        let a = (hxl, b.1 + flare_len);
        let l = (b.0 - a.0).hypot(b.1 - a.1);
        pts.push(a);
        (a, ((b.0 - a.0) / l, (b.1 - a.1) / l))
    } else { ((hxl, y_neck + flare_len), (0.0, -1.0)) };
    let n = (-d.1, d.0); // rotate d by +90 deg: for d = (0,-1) gives (1, 0) = +x (material side)
    let line_hit = |off: f64, rad: f64| -> Option<f64> {
        // smallest s >= 0 with |a + off*n + s d - c| = rad
        let p = (a.0 + off * n.0 - c.0, a.1 + off * n.1 - c.1);
        let bq = p.0 * d.0 + p.1 * d.1;
        let cq = p.0 * p.0 + p.1 * p.1 - rad * rad;
        let disc = bq * bq - cq;
        if disc < 0.0 { return None; }
        let s = -bq - disc.sqrt();
        (s >= -1e-9).then_some(s.max(0.0))
    };
    let mut rf = fillet.max(0.0);
    while rf > 0.05 {
        if let Some(s) = line_hit(-rf, rr + rf) {
            let o = (a.0 - rf * n.0 + s * d.0, a.1 - rf * n.1 + s * d.1);
            let t1 = (a.0 + s * d.0, a.1 + s * d.1);
            let (ox, oy) = (o.0 - c.0, o.1 - c.1);
            let lo = ox.hypot(oy);
            let t2 = (c.0 + rr * ox / lo, c.1 + rr * oy / lo);
            // the fillet must stay on the left half and above the ring centre
            if t2.0 < xm && t2.1 > c.1 && t1.1 <= a.1 + 1e-9 {
                let th1 = (t1.1 - o.1).atan2(t1.0 - o.0);
                let mut th2 = (t2.1 - o.1).atan2(t2.0 - o.0);
                while th2 - th1 > PI { th2 -= 2.0 * PI; }
                while th1 - th2 > PI { th2 += 2.0 * PI; }
                let k = (((th2 - th1).abs() * rf) / 0.5).ceil().max(4.0) as usize;
                for i in 0..=k { let th = th1 + (th2 - th1) * i as f64 / k as f64; pts.push((o.0 + rf * th.cos(), o.1 + rf * th.sin())); }
                return (pts, oy.atan2(ox));
            }
        }
        rf *= 0.8;
    }
    // sharp corner: flank meets the ring OD
    let s = line_hit(0.0, rr).unwrap_or(0.0);
    let j = (a.0 + s * d.0, a.1 + s * d.1);
    pts.push(j);
    (pts, (j.1 - c.1).atan2(j.0 - c.0))
}

pub fn shoelace(p: &[P2]) -> f64 {
    let mut a = 0.0;
    for i in 0..p.len() { let (x0, y0) = p[i]; let (x1, y1) = p[(i + 1) % p.len()]; a += x0 * y1 - x1 * y0; }
    a / 2.0
}

pub fn point_in_poly(q: P2, poly: &[P2]) -> bool {
    let mut c = false; let n = poly.len(); let mut j = n - 1;
    for i in 0..n {
        let (xi, yi) = poly[i]; let (xj, yj) = poly[j];
        if ((yi > q.1) != (yj > q.1)) && (q.0 < (xj - xi) * (q.1 - yi) / (yj - yi) + xi) { c = !c; }
        j = i;
    }
    c
}

/// True if any two non-adjacent edges of the polygon cross (self-intersection).
pub fn self_intersects(p: &[P2]) -> bool {
    let n = p.len();
    let cross = |o: P2, a: P2, b: P2| (a.0 - o.0) * (b.1 - o.1) - (a.1 - o.1) * (b.0 - o.0);
    let seg = |a: P2, b: P2, c: P2, d: P2| { let d1 = cross(c, d, a); let d2 = cross(c, d, b); let d3 = cross(a, b, c); let d4 = cross(a, b, d); (d1 * d2 < -1e-9) && (d3 * d4 < -1e-9) };
    // bounding-box prefilter keeps this ~O(n^2) but fast for n ~ 500
    for i in 0..n { let (a, b) = (p[i], p[(i + 1) % n]);
        for j in (i + 2)..n { if i == 0 && j == n - 1 { continue; }
            let (c, d) = (p[j], p[(j + 1) % n]);
            if a.0.max(b.0) < c.0.min(d.0) || c.0.max(d.0) < a.0.min(b.0) || a.1.max(b.1) < c.1.min(d.1) || c.1.max(d.1) < a.1.min(b.1) { continue; }
            if seg(a, b, c, d) { return true; } } }
    false
}

/// Minimum distance from point to polygon boundary.
pub fn dist_to_poly(q: P2, p: &[P2]) -> f64 {
    let n = p.len(); let mut best = f64::MAX;
    for i in 0..n { let (a, b) = (p[i], p[(i + 1) % n]);
        let (dx, dy) = (b.0 - a.0, b.1 - a.1); let l2 = dx * dx + dy * dy;
        let t = if l2 > 0.0 { (((q.0 - a.0) * dx + (q.1 - a.1) * dy) / l2).clamp(0.0, 1.0) } else { 0.0 };
        best = best.min(dist(q, (a.0 + t * dx, a.1 + t * dy))); }
    best
}

#[allow(dead_code)]
fn _limits_used() -> f64 { limits::BLADE_LIMIT_MM }
