//! Surrogate physics (FEM verification = codex lane B). Titanium only.
//! Strength model: plate/beam section capacities at the governing sections, with serration and
//! detent notch knock-downs. PRIMARY FITNESS = strength-per-gram (N/g) subject to hiker AND hunter
//! strength floors (see docs/WHITEPAPER.md §III-B). Strength alone is never the objective.
use jarambit_genotype::{limits, TiGrade};
use jarambit_phenotype::Phenotype;

pub struct Material { pub name: &'static str, pub density: f64, pub yield_mpa: f64, pub e_gpa: f64, pub dyield_dt: f64 }
pub const TI_6AL_4V: Material = Material { name: "Ti-6Al-4V", density: 4.43, yield_mpa: 880.0, e_gpa: 113.8, dyield_dt: -0.0011 };
pub const TI_3AL_2_5V: Material = Material { name: "Ti-3Al-2.5V", density: 4.48, yield_mpa: 620.0, e_gpa: 100.0, dyield_dt: -0.0012 };
pub fn material(g: TiGrade) -> &'static Material { match g { TiGrade::Ti6Al4V => &TI_6AL_4V, TiGrade::Ti3Al2_5V => &TI_3AL_2_5V } }
impl Material {
    /// Linear yield derate vs temperature (deg C), referenced to 20 C. Valid ~ -10..100 C.
    pub fn yield_at(&self, temp_c: f64) -> f64 { self.yield_mpa * (1.0 + self.dyield_dt * (temp_c - 20.0)) }
}

/// Strength floors (capacity at yield, N, lateral load at tip). Both must hold. Assumptions in WHITEPAPER §III-B.
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

/// Evaluate at temperature `temp_c` (MC samples -10..100 C). `ser_depth` = (inner, outer) serration depth.
pub fn evaluate(p: &Phenotype, edge_angle_deg: f64, ser_depth: (f64, f64), m: &Material, temp_c: f64) -> Eval {
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
}
