//! Monte Carlo over manufacturing tolerance + environment. Parallel via std::thread.
use jarambit_genotype::{Genotype, Rng};

/// Perturb a genotype by CNC/waterjet tolerances (thickness +-0.05 mm, profile +-0.1 mm).
/// NOTE: no clamp/repair here except thickness re-quantisation (stock is bought at 0.1 mm),
/// so tolerance excursions can push a design over the hard limits and get rejected.
pub fn perturb(g: &Genotype, r: &mut Rng) -> Genotype {
    let mut h = g.clone();
    h.curve_radius += r.normal() * 0.1;
    h.blade_arc_len += r.normal() * 0.15;
    h.ring_wall += r.normal() * 0.1;
    h.ring_id += r.normal() * 0.05;
    h.grip_len += r.normal() * 0.1;
    h.edge_angle_deg += r.normal() * 0.5;
    h.serr_inner.depth = (h.serr_inner.depth + r.normal() * 0.05).max(0.05);
    h.serr_outer.depth = (h.serr_outer.depth + r.normal() * 0.05).max(0.05);
    h.holder.detent_depth += r.normal() * 0.05;
    h.holder.shoulder_w += r.normal() * 0.05;
    h
}

/// Thickness as-machined (surface grind tolerance) — used by physics, not by the precision gate.
pub fn thickness_sample(g: &Genotype, r: &mut Rng) -> f64 { g.thickness + r.normal() * 0.03 }

/// Environment sample: temperature -10..100 C with 25% of samples at the extremes.
#[derive(Clone, Copy, Debug)]
pub struct Env { pub temp_c: f64 }
pub fn env_sample(r: &mut Rng) -> Env {
    let u = r.f64();
    let temp_c = if u < 0.125 { -10.0 } else if u < 0.25 { 100.0 } else { r.range(-10.0, 100.0) };
    Env { temp_c }
}

/// Run `n` samples of f(sample, rng) across `threads`; returns (mean, p05).
pub fn run<F>(g: &Genotype, n: usize, threads: usize, seed: u64, f: F) -> (f64, f64)
where F: Fn(&Genotype, &mut Rng) -> f64 + Sync {
    let threads = threads.max(1).min(n.max(1));
    let per = n.div_ceil(threads);
    let mut all: Vec<f64> = std::thread::scope(|s| {
        let hs: Vec<_> = (0..threads).map(|t| { let f = &f; s.spawn(move || {
            let mut r = Rng(seed ^ (t as u64 + 1).wrapping_mul(0x9E37_79B9_7F4A_7C15));
            (0..per).map(|_| { let h = perturb(g, &mut r); f(&h, &mut r) }).collect::<Vec<_>>()
        })}).collect();
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect()
    });
    all.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mean = all.iter().sum::<f64>() / all.len() as f64;
    (mean, all[all.len() / 20])
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn extremes_fraction() {
        let mut r = Rng(1); let n = 20000;
        let ext = (0..n).filter(|_| { let e = env_sample(&mut r); e.temp_c == -10.0 || e.temp_c == 100.0 }).count();
        let f = ext as f64 / n as f64; assert!((f - 0.25).abs() < 0.02, "{f}");
    }
}
