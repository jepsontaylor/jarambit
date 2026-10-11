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
        let tip = (r_mid * a1.cos() + 6.0 * a1.sin(), r_mid * a1.sin() - 6.0 * a1.cos());

        // --- blade metrics (unserrated centreline of each sharpened edge) ---
        let heel_o = (-r_out, 0.0); let heel_i = (-r_in, 0.0);
        let end_o = (r_out * a1.cos(), r_out * a1.sin()); let end_i = (r_in * a1.cos(), r_in * a1.sin());
        let arc_o = r_out * sweep + dist(end_o, tip);
        let arc_i = r_in * sweep + dist(end_i, tip);
        let mut xs: Vec<f64> = vec![tip.0];
        let mut ys: Vec<f64> = vec![tip.1];
        for i in 0..=256 { let a = a0 + (a1 - a0) * i as f64 / 256.0; xs.push(r_out * a.cos()); ys.push(r_out * a.sin()); }
        let xmax = xs.iter().cloned().fold(f64::MIN, f64::max);
        let ymax = ys.iter().cloned().fold(f64::MIN, f64::max);
        let blade = BladeMetrics {
            tip_to_heel: dist(tip, heel_o).max(dist(tip, heel_i)),
            horizontal_reach: xmax - (-r_out),
            sharpened_arc: arc_o.max(arc_i), sharpened_arc_outer: arc_o, sharpened_arc_inner: arc_i,
            vertical_rise: ymax.max(0.0), sweep_deg: sweep.to_degrees(),
        };

        // --- ricasso / shoulders / grip / detent / ring ---
        let h = &g.holder;
        let hx0 = -r_out; let hx1 = -r_in; let xm = (hx0 + hx1) / 2.0;
        let hw = g.handle_w(); let hxl = xm - hw / 2.0; let hxr = xm + hw / 2.0;
        let y_sh = -h.ricasso_len;                       // guard / shoulder line
        let y_neck = y_sh - g.grip_len;                   // ring neck
        let ring_r_out = g.ring_id / 2.0 + g.ring_wall;
        let al = (-(hw / 2.0) / ring_r_out).acos();       // left handle side meets ring (upper-left)
        let ar = ((hw / 2.0) / ring_r_out).acos();        // right side (upper-right)
        let ring_c = (xm, y_neck - ring_r_out * al.sin());
        let y_det = y_sh - h.detent_pos * g.grip_len; let dd = h.detent_depth;

        let mut outline: Vec<P2> = Vec::new();
        outline.push((hx0, 0.0)); outline.push((hx0, y_sh));            // ricasso land, left
        outline.push((hxl, y_sh));                                        // left shoulder
        outline.push((hxl, y_det + 1.5 * dd)); outline.push((hxl + dd, y_det)); outline.push((hxl, y_det - 1.5 * dd)); // detent V
        // ring outer circle starts/ends exactly at (hxl, y_neck)/(hxr, y_neck)
        for i in 0..=72 { let a = al + (2.0 * PI + ar - al) * i as f64 / 72.0; outline.push((ring_c.0 + ring_r_out * a.cos(), ring_c.1 + ring_r_out * a.sin())); }
        outline.push((hxr, y_sh));           // right grip side
        outline.push((hx1, y_sh)); outline.push((hx1, 0.0));              // right shoulder + ricasso land
        outline.extend(inner.iter().skip(1));                             // concave serrated edge heel->tip
        outline.push(tip);
        outline.extend(outer.iter().rev().take(outer.len() - 1));         // convex serrated edge tip->heel
        let ring_hole: Vec<P2> = (0..64).map(|i| { let a = -2.0 * PI * i as f64 / 64.0; (ring_c.0 + g.ring_id / 2.0 * a.cos(), ring_c.1 + g.ring_id / 2.0 * a.sin()) }).collect();

        let pw = g.brand_pad_w; let pl = g.brand_pad_l;
        let py = y_neck + 3.0 + pl / 2.0;
        let brand_pad = [(xm - pw / 2.0, py - pl / 2.0), (xm + pw / 2.0, py - pl / 2.0), (xm + pw / 2.0, py + pl / 2.0), (xm - pw / 2.0, py + pl / 2.0)];
        let (mut lo, mut hi) = ((f64::MAX, f64::MAX), (f64::MIN, f64::MIN));
        for p in &outline { lo.0 = lo.0.min(p.0); lo.1 = lo.1.min(p.1); hi.0 = hi.0.max(p.0); hi.1 = hi.1.max(p.1); }
        Phenotype { outline, ring_hole, thickness: g.thickness, brand_pad, inner_teeth: ti, outer_teeth: to,
            ring_center: ring_c, ring_outer_r: ring_r_out, ring_id: g.ring_id, blade, grip_len: y_sh - y_neck,
            handle_w: hw, ricasso_len: h.ricasso_len, shoulder_w: h.shoulder_w, detent: (y_det, dd), bbox: (lo, hi) }
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
