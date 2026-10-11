//! SWITCHBACK-class titanium hiking/utility karambit genotype.
//! All lengths in millimetres; thickness quantised to 0.1 mm.

/// Deterministic SplitMix64 RNG (no external deps, reproducible MC).
#[derive(Clone, Debug)]
pub struct Rng(pub u64);
impl Rng {
    pub fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }
    pub fn f64(&mut self) -> f64 { (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64 }
    pub fn range(&mut self, lo: f64, hi: f64) -> f64 { lo + (hi - lo) * self.f64() }
    pub fn normal(&mut self) -> f64 {
        let u1 = self.f64().max(1e-12); let u2 = self.f64();
        (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
    }
}

/// Parameter bounds (min, max). Encodes the hard design envelope.
pub mod bounds {
    pub const BLADE_ARC_LEN: (f64, f64) = (45.0, 75.0);     // mm along curve
    pub const CURVE_RADIUS: (f64, f64) = (28.0, 60.0);      // mm, must be curved
    pub const SWEEP_DEG: (f64, f64) = (55.0, 110.0);        // arc sweep
    pub const THICKNESS: (f64, f64) = (2.5, 4.5);           // spine stock, mm
    pub const EDGE_ANGLE_DEG: (f64, f64) = (14.0, 22.0);    // per side; Ti practical
    pub const SERR_PITCH: (f64, f64) = (2.5, 6.0);          // mm
    pub const SERR_DEPTH: (f64, f64) = (0.4, 1.5);          // mm
    pub const RING_ID: (f64, f64) = (22.0, 28.0);           // finger ring inner dia
    pub const RING_WALL: (f64, f64) = (4.0, 8.0);
    pub const HANDLE_LEN: (f64, f64) = (75.0, 105.0);
    pub const BRAND_PAD_W: (f64, f64) = (12.0, 22.0);       // flat pad
    pub const BRAND_PAD_L: (f64, f64) = (18.0, 35.0);
}

#[derive(Clone, Debug, PartialEq)]
pub struct Genotype {
    pub blade_arc_len: f64,
    pub curve_radius: f64,
    pub sweep_deg: f64,
    pub thickness: f64,
    pub edge_angle_deg: f64,
    /// Inner (concave) edge serration — required.
    pub serr_inner: Serration,
    /// Outer (convex) edge serration — required (double-edged, both serrated).
    pub serr_outer: Serration,
    pub ring_id: f64,
    pub ring_wall: f64,
    pub handle_len: f64,
    pub brand_pad_w: f64,
    pub brand_pad_l: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Serration { pub pitch: f64, pub depth: f64 }

pub fn q01(x: f64) -> f64 { (x * 10.0).round() / 10.0 }

impl Genotype {
    pub fn random(r: &mut Rng) -> Self {
        use bounds::*;
        let s = |r: &mut Rng| Serration { pitch: r.range(SERR_PITCH.0, SERR_PITCH.1), depth: r.range(SERR_DEPTH.0, SERR_DEPTH.1) };
        let mut g = Genotype {
            blade_arc_len: r.range(BLADE_ARC_LEN.0, BLADE_ARC_LEN.1),
            curve_radius: r.range(CURVE_RADIUS.0, CURVE_RADIUS.1),
            sweep_deg: r.range(SWEEP_DEG.0, SWEEP_DEG.1),
            thickness: r.range(THICKNESS.0, THICKNESS.1),
            edge_angle_deg: r.range(EDGE_ANGLE_DEG.0, EDGE_ANGLE_DEG.1),
            serr_inner: s(r), serr_outer: s(r),
            ring_id: r.range(RING_ID.0, RING_ID.1),
            ring_wall: r.range(RING_WALL.0, RING_WALL.1),
            handle_len: r.range(HANDLE_LEN.0, HANDLE_LEN.1),
            brand_pad_w: r.range(BRAND_PAD_W.0, BRAND_PAD_W.1),
            brand_pad_l: r.range(BRAND_PAD_L.0, BRAND_PAD_L.1),
        };
        g.clamp(); g
    }
    pub fn clamp(&mut self) {
        use bounds::*;
        let c = |v: &mut f64, b: (f64, f64)| *v = v.clamp(b.0, b.1);
        c(&mut self.blade_arc_len, BLADE_ARC_LEN); c(&mut self.curve_radius, CURVE_RADIUS);
        c(&mut self.sweep_deg, SWEEP_DEG); c(&mut self.thickness, THICKNESS);
        self.thickness = q01(self.thickness);
        c(&mut self.edge_angle_deg, EDGE_ANGLE_DEG);
        for s in [&mut self.serr_inner, &mut self.serr_outer] {
            c(&mut s.pitch, SERR_PITCH); c(&mut s.depth, SERR_DEPTH);
            s.depth = s.depth.min(self.thickness * 0.45).min(s.pitch * 0.5);
        }
        c(&mut self.ring_id, RING_ID); c(&mut self.ring_wall, RING_WALL);
        c(&mut self.handle_len, HANDLE_LEN); c(&mut self.brand_pad_w, BRAND_PAD_W);
        c(&mut self.brand_pad_l, BRAND_PAD_L);
    }
    pub fn mutate(&self, r: &mut Rng, sigma: f64) -> Self {
        let mut g = self.clone();
        let mut m = |v: &mut f64, span: f64| *v += r.normal() * sigma * span;
        m(&mut g.blade_arc_len, 30.0); m(&mut g.curve_radius, 32.0); m(&mut g.sweep_deg, 55.0);
        m(&mut g.thickness, 2.0); m(&mut g.edge_angle_deg, 8.0);
        m(&mut g.serr_inner.pitch, 3.5); m(&mut g.serr_inner.depth, 1.1);
        m(&mut g.serr_outer.pitch, 3.5); m(&mut g.serr_outer.depth, 1.1);
        m(&mut g.ring_id, 6.0); m(&mut g.ring_wall, 4.0); m(&mut g.handle_len, 30.0);
        m(&mut g.brand_pad_w, 10.0); m(&mut g.brand_pad_l, 17.0);
        g.clamp(); g
    }
    pub fn crossover(&self, o: &Self, r: &mut Rng) -> Self {
        let mut p = |a: f64, b: f64| if r.f64() < 0.5 { a } else { b };
        let mut g = Genotype {
            blade_arc_len: p(self.blade_arc_len, o.blade_arc_len),
            curve_radius: p(self.curve_radius, o.curve_radius),
            sweep_deg: p(self.sweep_deg, o.sweep_deg),
            thickness: p(self.thickness, o.thickness),
            edge_angle_deg: p(self.edge_angle_deg, o.edge_angle_deg),
            serr_inner: Serration { pitch: p(self.serr_inner.pitch, o.serr_inner.pitch), depth: p(self.serr_inner.depth, o.serr_inner.depth) },
            serr_outer: Serration { pitch: p(self.serr_outer.pitch, o.serr_outer.pitch), depth: p(self.serr_outer.depth, o.serr_outer.depth) },
            ring_id: p(self.ring_id, o.ring_id), ring_wall: p(self.ring_wall, o.ring_wall),
            handle_len: p(self.handle_len, o.handle_len),
            brand_pad_w: p(self.brand_pad_w, o.brand_pad_w), brand_pad_l: p(self.brand_pad_l, o.brand_pad_l),
        };
        g.clamp(); g
    }
    pub fn to_csv_row(&self) -> String {
        format!("{:.2},{:.2},{:.2},{:.1},{:.2},{:.2},{:.2},{:.2},{:.2},{:.2},{:.2},{:.2},{:.2},{:.2}",
            self.blade_arc_len, self.curve_radius, self.sweep_deg, self.thickness, self.edge_angle_deg,
            self.serr_inner.pitch, self.serr_inner.depth, self.serr_outer.pitch, self.serr_outer.depth,
            self.ring_id, self.ring_wall, self.handle_len, self.brand_pad_w, self.brand_pad_l)
    }
    pub const CSV_HEADER: &'static str = "blade_arc_len,curve_radius,sweep_deg,thickness,edge_angle_deg,serr_in_pitch,serr_in_depth,serr_out_pitch,serr_out_depth,ring_id,ring_wall,handle_len,brand_pad_w,brand_pad_l";
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn thickness_quantised() {
        let mut r = Rng(1);
        for _ in 0..1000 { let g = Genotype::random(&mut r); assert!((g.thickness * 10.0 - (g.thickness * 10.0).round()).abs() < 1e-9); }
    }
}
