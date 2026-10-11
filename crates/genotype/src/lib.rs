//! SWITCHBACK-class titanium hiking/utility karambit genotype.
//! All lengths in millimetres; thickness quantised to 0.1 mm.
//!
//! HARD CONSTRAINTS (see docs/WHITEPAPER.md §III-A and crates/redteam):
//! * blade >= 3.375 in (85.725 mm) on ALL THREE measures: tip-to-heel, horizontal reach,
//!   sharpened-edge arc (Jepson 2026-10-11 all-three FLOOR; any one below floor => reject;
//!   0.5 mm guard => design floor 86.225 mm), and sharpened edge arc <= 4.0 in (101.6 mm);
//! * grip (ring-neck to guard/shoulder) >= 60 mm, usable band 60-80 mm;
//! * finger ring ID 25.4 mm (+/-0.5 mm);
//! * curved (never straight), double-edged with BOTH edges serrated;
//! * single connected solid (genus 1, ring = only hole); flat brand pad;
//! * 0.1 mm thickness precision; titanium only; hiking/utility use only;
//! * sheath/fixed-blade holder interface genes (shoulders, thickness lands, retention detent,
//!   holder drain) — holder envelope assumptions in docs/HOLDER_ENVELOPE.md.

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

/// Hard limits shared by genotype repair, red-team gate and docs. Never weaken.
pub mod limits {
    /// 3.375 in in mm: a MINIMUM. Tip-to-heel, horizontal reach AND sharpened-edge arc must
    /// each be >= this (owner requirement, Jepson 2026-10-11; replaces the old "< 3.375 in" max rule).
    pub const BLADE_LIMIT_MM: f64 = 3.375 * 25.4; // 85.725
    /// Design guard band ABOVE the floor so CNC/waterjet tolerance cannot drop a part under it.
    pub const BLADE_GUARD_MM: f64 = 0.5;
    /// Effective design floor applied by the red-team gate (85.725 + 0.5 = 86.225 mm).
    pub const BLADE_FLOOR_MM: f64 = BLADE_LIMIT_MM + BLADE_GUARD_MM;
    /// Upper cap on the sharpened-edge arc: 4.0 in.
    pub const BLADE_EDGE_MAX_MM: f64 = 4.0 * 25.4; // 101.6
    /// Grip floor: ring-neck to guard (shoulder) length.
    pub const GRIP_MIN_MM: f64 = 60.0;
    pub const GRIP_MAX_MM: f64 = 80.0;
    /// Finger ring inner diameter (1.000 in) and allowed deviation.
    pub const RING_ID_MM: f64 = 25.4;
    pub const RING_ID_TOL_MM: f64 = 0.5;
    /// Minimum arc sweep for the blade to count as curved (karambit talon).
    pub const MIN_SWEEP_DEG: f64 = 55.0;
    pub const MAX_SWEEP_DEG: f64 = 140.0;
    /// Nominal blade height (edge-to-edge) used by phenotype & physics.
    pub const BLADE_H_MM: f64 = 14.0;
    /// Brand pad must be at least this flat area (mm x mm).
    pub const BRAND_PAD_MIN: (f64, f64) = (6.0, 12.0);
}

/// Parameter bounds (min, max). Encodes the hard design envelope.
pub mod bounds {
    /// Outer-arc gene (mm). Phenotype adds a fixed ~9.22 mm tip run (hypot(BLADE_H/2, 6)), so
    /// sharpened_arc = gene + 9.22 spans ~86.3..101.5 mm: inside [BLADE_FLOOR_MM, BLADE_EDGE_MAX_MM].
    /// (Old 45..72 mm cap removed 2026-10-11: it made every design < 3.375 in.)
    pub const BLADE_ARC_LEN: (f64, f64) = (77.1, 92.3);
    pub const CURVE_RADIUS: (f64, f64) = (28.0, 45.0);      // mid-blade radius, mm (curved)
    pub const THICKNESS: (f64, f64) = (2.5, 4.5);           // stock, mm, 0.1 mm quantum
    pub const EDGE_ANGLE_DEG: (f64, f64) = (14.0, 22.0);    // per side; Ti practical
    pub const SERR_PITCH: (f64, f64) = (2.5, 6.0);          // mm
    pub const SERR_DEPTH: (f64, f64) = (0.4, 1.5);          // mm
    pub const RING_ID: (f64, f64) = (24.9, 25.9);           // 25.4 +/- 0.5
    pub const RING_WALL: (f64, f64) = (4.0, 8.0);
    pub const GRIP_LEN: (f64, f64) = (60.0, 80.0);          // ring-neck to guard
    pub const BRAND_PAD_W: (f64, f64) = (6.0, 11.0);        // flat pad on handle face
    pub const BRAND_PAD_L: (f64, f64) = (12.0, 30.0);
    // --- sheath / fixed-blade holder interface ---
    pub const RICASSO_LEN: (f64, f64) = (5.0, 15.0);        // unsharpened flat thickness lands
    pub const SHOULDER_W: (f64, f64) = (0.8, 2.5);          // per-side tang/ricasso step (positive stop)
    pub const DETENT_DEPTH: (f64, f64) = (0.4, 1.2);        // retention notch for holder nub
    pub const DETENT_POS: (f64, f64) = (0.10, 0.45);        // fraction of grip from shoulder
    pub const FRICTION_LEN: (f64, f64) = (8.0, 30.0);       // holder friction-face contact on grip
    pub const HOLDER_DRAIN_D: (f64, f64) = (3.0, 6.0);      // holder tip-pocket drain dia
    pub const HOLDER_WALL: (f64, f64) = (1.2, 2.0);         // holder shell (Kydex-like) thickness
}

/// Titanium only (hiking/utility). No steels, no other alloys.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TiGrade { Ti6Al4V, Ti3Al2_5V }
impl TiGrade {
    pub fn name(&self) -> &'static str { match self { TiGrade::Ti6Al4V => "Ti-6Al-4V", TiGrade::Ti3Al2_5V => "Ti-3Al-2.5V" } }
    pub fn is_titanium(&self) -> bool { self.name().starts_with("Ti-") }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Serration { pub pitch: f64, pub depth: f64 }

/// Sheath / fixed-blade holder interface genes.
#[derive(Clone, Debug, PartialEq)]
pub struct HolderIface {
    pub ricasso_len: f64,
    pub shoulder_w: f64,
    pub detent_depth: f64,
    pub detent_pos: f64,
    pub friction_len: f64,
    pub drain_d: f64,
    pub holder_wall: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Genotype {
    pub blade_arc_len: f64,
    pub curve_radius: f64,
    pub thickness: f64,
    pub edge_angle_deg: f64,
    /// Inner (concave) edge serration — required.
    pub serr_inner: Serration,
    /// Outer (convex) edge serration — required (double-edged, both serrated).
    pub serr_outer: Serration,
    pub ring_id: f64,
    pub ring_wall: f64,
    /// Ring-neck to guard (shoulder) length.
    pub grip_len: f64,
    pub brand_pad_w: f64,
    pub brand_pad_l: f64,
    pub holder: HolderIface,
    pub material: TiGrade,
    /// Raw sweep override for adversarial tests; None = derived from arc/radius.
    pub sweep_override_deg: Option<f64>,
}

fn h_repair(h: &mut HolderIface, grip: f64) {
    let fmax = (grip - 30.0).min(bounds::FRICTION_LEN.1);
    h.friction_len = h.friction_len.max(h.detent_pos * grip + 3.0).min(fmax);
    if h.detent_pos * grip > h.friction_len - 3.0 { h.detent_pos = ((h.friction_len - 3.0) / grip).max(bounds::DETENT_POS.0); }
}

pub fn q01(x: f64) -> f64 { (x * 10.0).round() / 10.0 }

impl Genotype {
    pub fn r_out(&self) -> f64 { self.curve_radius + limits::BLADE_H_MM / 2.0 }
    pub fn r_in(&self) -> f64 { self.curve_radius - limits::BLADE_H_MM / 2.0 }
    /// Blade sweep (deg), derived so the outer sharpened arc equals blade_arc_len.
    pub fn sweep_deg(&self) -> f64 { self.sweep_override_deg.unwrap_or((self.blade_arc_len / self.r_out()).to_degrees()) }
    pub fn handle_w(&self) -> f64 { limits::BLADE_H_MM - 2.0 * self.holder.shoulder_w }

    pub fn random(r: &mut Rng) -> Self {
        use bounds::*;
        let s = |r: &mut Rng| Serration { pitch: r.range(SERR_PITCH.0, SERR_PITCH.1), depth: r.range(SERR_DEPTH.0, SERR_DEPTH.1) };
        let mut g = Genotype {
            blade_arc_len: r.range(BLADE_ARC_LEN.0, BLADE_ARC_LEN.1),
            curve_radius: r.range(CURVE_RADIUS.0, CURVE_RADIUS.1),
            thickness: r.range(THICKNESS.0, THICKNESS.1),
            edge_angle_deg: r.range(EDGE_ANGLE_DEG.0, EDGE_ANGLE_DEG.1),
            serr_inner: s(r), serr_outer: s(r),
            ring_id: r.range(RING_ID.0, RING_ID.1),
            ring_wall: r.range(RING_WALL.0, RING_WALL.1),
            grip_len: r.range(GRIP_LEN.0, GRIP_LEN.1),
            brand_pad_w: r.range(BRAND_PAD_W.0, BRAND_PAD_W.1),
            brand_pad_l: r.range(BRAND_PAD_L.0, BRAND_PAD_L.1),
            holder: HolderIface {
                ricasso_len: r.range(RICASSO_LEN.0, RICASSO_LEN.1),
                shoulder_w: r.range(SHOULDER_W.0, SHOULDER_W.1),
                detent_depth: r.range(DETENT_DEPTH.0, DETENT_DEPTH.1),
                detent_pos: r.range(DETENT_POS.0, DETENT_POS.1),
                friction_len: r.range(FRICTION_LEN.0, FRICTION_LEN.1),
                drain_d: r.range(HOLDER_DRAIN_D.0, HOLDER_DRAIN_D.1),
                holder_wall: r.range(HOLDER_WALL.0, HOLDER_WALL.1),
            },
            material: if r.f64() < 0.5 { TiGrade::Ti6Al4V } else { TiGrade::Ti3Al2_5V },
            sweep_override_deg: None,
        };
        g.clamp(); g
    }

    /// Clamp to bounds and repair coupled constraints (curvature, quantisation).
    pub fn clamp(&mut self) {
        use bounds::*;
        let c = |v: &mut f64, b: (f64, f64)| *v = if v.is_finite() { v.clamp(b.0, b.1) } else { b.0 };
        c(&mut self.blade_arc_len, BLADE_ARC_LEN); c(&mut self.curve_radius, CURVE_RADIUS);
        // curvature repair: sweep must be >= MIN_SWEEP => r_out <= arc / min_sweep
        let r_out_max = self.blade_arc_len / (limits::MIN_SWEEP_DEG + 1.0).to_radians(); // 1 deg margin for tolerance MC
        let r_out_min = self.blade_arc_len / limits::MAX_SWEEP_DEG.to_radians();
        let half_h = limits::BLADE_H_MM / 2.0;
        self.curve_radius = self.curve_radius.min(r_out_max - half_h).max(r_out_min - half_h).clamp(CURVE_RADIUS.0, CURVE_RADIUS.1);
        c(&mut self.thickness, THICKNESS);
        self.thickness = q01(self.thickness);
        c(&mut self.edge_angle_deg, EDGE_ANGLE_DEG);
        let t = self.thickness;
        for s in [&mut self.serr_inner, &mut self.serr_outer] {
            c(&mut s.pitch, SERR_PITCH); c(&mut s.depth, SERR_DEPTH);
            s.depth = s.depth.min(t * 0.45).min(s.pitch * 0.5);
        }
        c(&mut self.ring_id, RING_ID); c(&mut self.ring_wall, RING_WALL);
        c(&mut self.grip_len, GRIP_LEN);
        let h = &mut self.holder;
        c(&mut h.ricasso_len, RICASSO_LEN); c(&mut h.shoulder_w, SHOULDER_W);
        c(&mut h.detent_depth, DETENT_DEPTH); c(&mut h.detent_pos, DETENT_POS);
        c(&mut h.friction_len, FRICTION_LEN); c(&mut h.drain_d, HOLDER_DRAIN_D);
        c(&mut h.holder_wall, HOLDER_WALL);
        // holder pop-in: detent must sit inside the friction-face zone; >= 30 mm of grip + ring stay exposed
        h_repair(&mut self.holder, self.grip_len);
        let hw = self.handle_w();
        c(&mut self.brand_pad_w, BRAND_PAD_W); c(&mut self.brand_pad_l, BRAND_PAD_L);
        self.brand_pad_w = self.brand_pad_w.min(hw - 2.0 * self.holder.detent_depth - 1.0).max(limits::BRAND_PAD_MIN.0);
        // brand pad lives in the lower half of the grip, below the detent
        let room = self.grip_len * (1.0 - self.holder.detent_pos) - 6.0;
        self.brand_pad_l = self.brand_pad_l.min(room).max(limits::BRAND_PAD_MIN.1);
    }

    pub fn mutate(&self, r: &mut Rng, sigma: f64) -> Self {
        let mut g = self.clone();
        let mut m = |v: &mut f64, span: f64| *v += r.normal() * sigma * span;
        m(&mut g.blade_arc_len, 27.0); m(&mut g.curve_radius, 17.0);
        m(&mut g.thickness, 2.0); m(&mut g.edge_angle_deg, 8.0);
        m(&mut g.serr_inner.pitch, 3.5); m(&mut g.serr_inner.depth, 1.1);
        m(&mut g.serr_outer.pitch, 3.5); m(&mut g.serr_outer.depth, 1.1);
        m(&mut g.ring_id, 1.0); m(&mut g.ring_wall, 4.0); m(&mut g.grip_len, 20.0);
        m(&mut g.brand_pad_w, 5.0); m(&mut g.brand_pad_l, 18.0);
        m(&mut g.holder.ricasso_len, 10.0); m(&mut g.holder.shoulder_w, 1.7);
        m(&mut g.holder.detent_depth, 0.8); m(&mut g.holder.detent_pos, 0.35);
        m(&mut g.holder.friction_len, 22.0); m(&mut g.holder.drain_d, 3.0); m(&mut g.holder.holder_wall, 0.8);
        if r.f64() < sigma * 0.5 { g.material = if g.material == TiGrade::Ti6Al4V { TiGrade::Ti3Al2_5V } else { TiGrade::Ti6Al4V }; }
        g.clamp(); g
    }

    pub fn crossover(&self, o: &Self, r: &mut Rng) -> Self {
        let a = self.to_vec(); let b = o.to_vec();
        let v: Vec<f64> = a.iter().zip(&b).map(|(x, y)| if r.f64() < 0.5 { *x } else { *y }).collect();
        let mut g = Self::from_vec(&v, if r.f64() < 0.5 { self.material } else { o.material });
        g.clamp(); g
    }

    /// Continuous genes as a vector (for diversity metrics / crossover). Order = CSV_HEADER minus material.
    pub fn to_vec(&self) -> Vec<f64> {
        let h = &self.holder;
        vec![self.blade_arc_len, self.curve_radius, self.thickness, self.edge_angle_deg,
             self.serr_inner.pitch, self.serr_inner.depth, self.serr_outer.pitch, self.serr_outer.depth,
             self.ring_id, self.ring_wall, self.grip_len, self.brand_pad_w, self.brand_pad_l,
             h.ricasso_len, h.shoulder_w, h.detent_depth, h.detent_pos, h.friction_len, h.drain_d, h.holder_wall]
    }
    pub fn from_vec(v: &[f64], material: TiGrade) -> Self {
        Genotype {
            blade_arc_len: v[0], curve_radius: v[1], thickness: v[2], edge_angle_deg: v[3],
            serr_inner: Serration { pitch: v[4], depth: v[5] }, serr_outer: Serration { pitch: v[6], depth: v[7] },
            ring_id: v[8], ring_wall: v[9], grip_len: v[10], brand_pad_w: v[11], brand_pad_l: v[12],
            holder: HolderIface { ricasso_len: v[13], shoulder_w: v[14], detent_depth: v[15], detent_pos: v[16], friction_len: v[17], drain_d: v[18], holder_wall: v[19] },
            material, sweep_override_deg: None,
        }
    }
    /// Span of each gene's bounds (same order as to_vec), for normalised distances.
    pub fn spans() -> Vec<f64> {
        use bounds::*;
        [BLADE_ARC_LEN, CURVE_RADIUS, THICKNESS, EDGE_ANGLE_DEG, SERR_PITCH, SERR_DEPTH, SERR_PITCH, SERR_DEPTH,
         RING_ID, RING_WALL, GRIP_LEN, BRAND_PAD_W, BRAND_PAD_L, RICASSO_LEN, SHOULDER_W, DETENT_DEPTH, DETENT_POS,
         FRICTION_LEN, HOLDER_DRAIN_D, HOLDER_WALL].iter().map(|b| b.1 - b.0).collect()
    }
    pub fn distance(&self, o: &Self) -> f64 {
        let s = Self::spans();
        let d: f64 = self.to_vec().iter().zip(o.to_vec()).zip(&s).map(|((a, b), sp)| ((a - b) / sp).powi(2)).sum();
        (d / s.len() as f64).sqrt() + if self.material != o.material { 0.05 } else { 0.0 }
    }

    pub fn to_csv_row(&self) -> String {
        let v = self.to_vec();
        let mut s: Vec<String> = v.iter().enumerate().map(|(i, x)| if i == 2 { format!("{x:.1}") } else { format!("{x:.3}") }).collect();
        s.push(self.material.name().into());
        s.join(",")
    }
    pub const CSV_HEADER: &'static str = "blade_arc_len,curve_radius,thickness,edge_angle_deg,serr_in_pitch,serr_in_depth,serr_out_pitch,serr_out_depth,ring_id,ring_wall,grip_len,brand_pad_w,brand_pad_l,ricasso_len,shoulder_w,detent_depth,detent_pos,friction_len,holder_drain_d,holder_wall,material";
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn thickness_quantised() {
        let mut r = Rng(1);
        for _ in 0..1000 { let g = Genotype::random(&mut r); assert!((g.thickness * 10.0 - (g.thickness * 10.0).round()).abs() < 1e-9); }
    }
    #[test] fn repair_keeps_curved_and_in_spec() {
        let mut r = Rng(2);
        for _ in 0..2000 {
            let g = Genotype::random(&mut r).mutate(&mut r, 0.5);
            assert!(g.sweep_deg() >= limits::MIN_SWEEP_DEG - 1e-6, "sweep {}", g.sweep_deg());
            assert!(g.grip_len >= limits::GRIP_MIN_MM);
            assert!((g.ring_id - limits::RING_ID_MM).abs() <= limits::RING_ID_TOL_MM + 1e-9);
            assert!(g.material.is_titanium());
        }
    }
    #[test] fn csv_columns_match() {
        let g = Genotype::random(&mut Rng(3));
        assert_eq!(g.to_csv_row().split(',').count(), Genotype::CSV_HEADER.split(',').count());
    }
}
