//! Surrogate physics (stub for FEM): beam bending at blade root, edge sharpness proxy,
//! ring safety margin. Ti-6Al-4V defaults.
use jarambit_phenotype::Phenotype;

pub struct Material { pub density: f64, pub yield_mpa: f64, pub e_gpa: f64 }
pub const TI_6AL_4V: Material = Material { density: 4.43, yield_mpa: 880.0, e_gpa: 113.8 };

#[derive(Debug, Clone)]
pub struct Eval { pub mass_g: f64, pub root_stress_mpa: f64, pub safety_factor: f64, pub sharpness: f64, pub serration_score: f64, pub ergonomics: f64 }

/// load_n: lateral utility load at tip (e.g. 150 N prying/cutting cord).
pub fn evaluate(p: &Phenotype, edge_angle_deg: f64, arc_len: f64, load_n: f64, m: &Material) -> Eval {
    let t = p.thickness; let h = 14.0; // nominal blade height
    // lateral bending about thin axis: sigma = M c / I, I = h t^3 /12
    let i = h * t.powi(3) / 12.0;
    let moment = load_n * arc_len * 0.6;
    let sigma = moment * (t / 2.0) / i;
    let sf = m.yield_mpa / sigma;
    // sharpness proxy: lower included angle sharper, but Ti edge rolls below ~14deg/side
    let sharp = (1.0 - (edge_angle_deg - 14.0) / 8.0).clamp(0.0, 1.0) * (1.0 - (-((edge_angle_deg - 12.0).max(0.0))).exp() * 0.5);
    let serr = ((p.inner_teeth.min(p.outer_teeth) as f64) / 20.0).min(1.0);
    let ergo = (1.0 - ((p.ring_outer_r - 18.0).abs() / 10.0)).clamp(0.0, 1.0);
    Eval { mass_g: p.mass_g(m.density), root_stress_mpa: sigma, safety_factor: sf, sharpness: sharp, serration_score: serr, ergonomics: ergo }
}
