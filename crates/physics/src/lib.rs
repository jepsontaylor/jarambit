//! Strength model for a titanium hiking/utility karambit.
//! `surrogate` / `evaluate` is the beam section formula used by Monte Carlo.
//! `plate_capacities` is a coarse Kirchhoff plate (DKT + membrane) on the same
//! outline: the check against the surrogate, not the 10k-sample loop.
//! PRIMARY FITNESS = strength-per-gram (N/g) subject to hiker AND hunter floors
//! (see docs/WHITEPAPER.md §III-B). Strength alone is never the objective.
//! Floors are firm (Jepson, 2026-10-11): 180 N / 260 N / 1500 N.
use jarambit_genotype::{limits, TiGrade};
use jarambit_phenotype::Phenotype;
mod fem;
pub mod fine;
pub mod calib;
pub mod verify;
pub use fem::{capacities as plate_capacities, Caps as PlateCaps};

pub struct Material { pub name: &'static str, pub density: f64, pub yield_mpa: f64, pub e_gpa: f64, pub dyield_dt: f64 }
/// D1 (2026-10-11): SCREENING yield = 828 MPa, provisional (TIMET Ti-6Al-4V Grade 5 annealed plate
/// MINIMUM 0.2 % yield, 120 ksi). Was 880 MPa (typical). Knock-down 828/880 = 0.941; never round up
/// to 830 for a marginal pass. See docs/CALIBRATION.md "D1 yield allowable".
pub const TI64_YIELD_TYPICAL_MPA: f64 = 880.0;
pub const TI_6AL_4V: Material = Material { name: "Ti-6Al-4V", density: 4.43, yield_mpa: 828.0, e_gpa: 113.8, dyield_dt: -0.0011 };
pub const TI_3AL_2_5V: Material = Material { name: "Ti-3Al-2.5V", density: 4.48, yield_mpa: 620.0, e_gpa: 100.0, dyield_dt: -0.0012 };
pub fn material(g: TiGrade) -> &'static Material { match g { TiGrade::Ti6Al4V => &TI_6AL_4V, TiGrade::Ti3Al2_5V => &TI_3AL_2_5V } }
impl Material {
    /// Linear yield derate vs temperature (deg C), referenced to 20 C. Valid ~ -10..100 C.
    pub fn yield_at(&self, temp_c: f64) -> f64 { self.yield_mpa * (1.0 + self.dyield_dt * (temp_c - 20.0)) }
}

/// Strength floors (capacity at yield, N, lateral load at tip). Both must hold.
/// CONFIRMED by Jepson 2026-10-11 (firm, not placeholder): hiker 180 N, hunter 260 N, ring pull 1500 N. Rationale in WHITEPAPER §III-B.
pub mod floors {
    /// Hiker: 90 N lateral working load at tip x SF 2.0 (cord/branch/packaging, twisting cut).
    pub const HIKER_LATERAL_N: f64 = 180.0;
    /// Hunter (game processing / field dressing, joint separation): 130 N x SF 2.0.
    pub const HUNTER_LATERAL_N: f64 = 260.0;
    /// Finger-ring pull (drag/hold) capacity floor, both use profiles.
    pub const RING_PULL_N: f64 = 1500.0;
}

#[derive(Debug, Clone)]
pub struct Eval {
    pub mass_g: f64,
    /// Governing lateral strength (N) = min(blade-heel, grip-shoulder) capacity.
    pub strength_n: f64,
    pub blade_lat_n: f64, pub grip_lat_n: f64, pub ring_pull_n: f64, pub inplane_n: f64,
    /// strength_n / mass_g — the PRIMARY scalar.
    pub strength_per_gram: f64,
    pub hiker_ok: bool, pub hunter_ok: bool, pub ring_ok: bool,
    pub safety_factor: f64, pub sharpness: f64, pub serration_score: f64, pub ergonomics: f64,
}
impl Eval { pub fn floors_ok(&self) -> bool { self.hiker_ok && self.hunter_ok && self.ring_ok } }

/// Beam/plate section surrogate. Kept so FEM capacities can be checked against it.
pub fn surrogate(p: &Phenotype, edge_angle_deg: f64, ser_depth: (f64, f64), m: &Material, temp_c: f64) -> Eval {
    let t = p.thickness; let sy = m.yield_at(temp_c);
    let h_eff = (limits::BLADE_H_MM - ser_depth.0 - ser_depth.1).max(1.0);
    let lever_blade = p.blade.tip_to_heel.max(1.0);
    let lever_grip = lever_blade + p.ricasso_len;
    let blade_lat = sy * (h_eff * t * t / 6.0) / lever_blade;
    let kt_detent = 1.0 + 0.6 * (p.detent.1 / 1.2);
    let hw_eff = (p.handle_w - p.detent.1).max(1.0);
    let grip_lat = sy * (hw_eff * t * t / 6.0) / lever_grip / kt_detent;
    let ring_pull = sy * 2.0 * (p.ring_outer_r - p.ring_id / 2.0) * t / 2.0;
    let inplane = sy * (t * h_eff * h_eff / 6.0) / lever_blade;
    let strength = blade_lat.min(grip_lat);
    let mass = p.mass_g(m.density);
    let sharp = (1.0 - (edge_angle_deg - 14.0) / 8.0).clamp(0.0, 1.0);
    let serr = ((p.inner_teeth.min(p.outer_teeth) as f64) / 20.0).min(1.0);
    let ergo = (1.0 - ((p.grip_len - 70.0).abs() / 20.0)).clamp(0.0, 1.0);
    Eval { mass_g: mass, strength_n: strength, blade_lat_n: blade_lat, grip_lat_n: grip_lat, ring_pull_n: ring_pull, inplane_n: inplane,
        strength_per_gram: strength / mass.max(1e-6),
        hiker_ok: strength >= floors::HIKER_LATERAL_N, hunter_ok: strength >= floors::HUNTER_LATERAL_N, ring_ok: ring_pull >= floors::RING_PULL_N,
        safety_factor: strength / floors::HUNTER_LATERAL_N * 2.0, sharpness: sharp, serration_score: serr, ergonomics: ergo }
}

/// Evaluate at temperature `temp_c` (MC samples -10..100 C). `ser_depth` = (inner, outer) serration depth.
/// This is the surrogate. Plate FEM is `plate_capacities`, run on a sample of designs
/// and on the reported winner — not on every Monte Carlo draw.
pub fn evaluate(p: &Phenotype, edge_angle_deg: f64, ser_depth: (f64, f64), m: &Material, temp_c: f64) -> Eval {
    surrogate(p, edge_angle_deg, ser_depth, m, temp_c)
}

/// Primary scalar fitness: strength-per-gram if both floors hold, else a graded penalty (< 0).
pub fn primary_fitness(e: &Eval) -> f64 {
    if e.floors_ok() { e.strength_per_gram }
    else {
        let d = (1.0 - e.strength_n / floors::HUNTER_LATERAL_N).max(0.0) + (1.0 - e.ring_pull_n / floors::RING_PULL_N).max(0.0);
        -1.0 - 10.0 * d
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use jarambit_genotype::{Genotype, Rng};
    #[test] fn thicker_is_stronger_but_heavier() {
        let mut g = Genotype::random(&mut Rng(5)); g.thickness = 3.0; g.clamp();
        let mut g2 = g.clone(); g2.thickness = 4.0; g2.clamp();
        let (p, p2) = (Phenotype::from_genotype(&g), Phenotype::from_genotype(&g2));
        let (e, e2) = (evaluate(&p, 16.0, (0.8, 0.8), &TI_6AL_4V, 20.0), evaluate(&p2, 16.0, (0.8, 0.8), &TI_6AL_4V, 20.0));
        assert!(e2.strength_n > e.strength_n && e2.mass_g > e.mass_g);
    }
    #[test] fn hot_is_weaker() { assert!(TI_6AL_4V.yield_at(100.0) < TI_6AL_4V.yield_at(-10.0)); }
    #[test] fn floors_stay_at_confirmed_values() {
        assert_eq!(floors::HIKER_LATERAL_N, 180.0);
        assert_eq!(floors::HUNTER_LATERAL_N, 260.0);
        assert_eq!(floors::RING_PULL_N, 1500.0);
    }
    #[test] fn fem_tracks_surrogate_order() {
        let mut r = Rng(11);
        let mut ratios = Vec::new();
        let mut missed = 0;
        for _ in 0..20 {
            let g = Genotype::random(&mut r);
            let p = Phenotype::from_genotype(&g);
            let s = surrogate(&p, g.edge_angle_deg, (g.serr_inner.depth, g.serr_outer.depth), &TI_6AL_4V, 20.0);
            let Some(c) = plate_capacities(&p, &TI_6AL_4V, 20.0, (g.serr_inner.depth, g.serr_outer.depth)) else {
                missed += 1;
                continue;
            };
            assert!(c.free_dofs > 0 && c.nodes > 0);
            let fem_s = c.blade_lat_n.min(c.grip_lat_n);
            assert!(fem_s.is_finite() && fem_s > 0.0 && c.ring_pull_n > 0.0, "{fem_s}");
            ratios.push((fem_s / s.strength_n, c.blade_lat_n / s.blade_lat_n, c.grip_lat_n / s.grip_lat_n, c.ring_pull_n / s.ring_pull_n));
        }
        assert!(missed <= 4, "plate mesh missed {missed} of 20");
        let mut lat: Vec<f64> = ratios.iter().map(|r| r.0).collect();
        lat.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let med = lat[lat.len() / 2];
        assert!(med > 0.2 && med < 8.0, "median plate/surrogate lateral {med} ratios {ratios:?}");
    }
}
