//! Monte Carlo over manufacturing tolerance + load uncertainty. Parallel via std::thread.
use jarambit_genotype::{Genotype, Rng};

/// Perturb a genotype by CNC/waterjet tolerances (thickness +-0.05 mm, profile +-0.1 mm).
pub fn perturb(g: &Genotype, r: &mut Rng) -> Genotype {
    let mut h = g.clone();
    h.thickness += r.normal() * 0.05;
    h.curve_radius += r.normal() * 0.1;
    h.ring_wall += r.normal() * 0.1;
    h.edge_angle_deg += r.normal() * 0.5;
    h.serr_inner.depth += r.normal() * 0.05; h.serr_outer.depth += r.normal() * 0.05;
    h.clamp(); h
}

/// Run `n` samples of f(sample, rng) across `threads`; returns (mean, p05).
pub fn run<F>(g: &Genotype, n: usize, threads: usize, seed: u64, f: F) -> (f64, f64)
where F: Fn(&Genotype, &mut Rng) -> f64 + Sync {
    let threads = threads.max(1);
    let per = n.div_ceil(threads);
    let mut all: Vec<f64> = std::thread::scope(|s| {
        let hs: Vec<_> = (0..threads).map(|t| { let f = &f; s.spawn(move || {
            let mut r = Rng(seed ^ (t as u64).wrapping_mul(0x9E37_79B9));
            (0..per).map(|_| { let h = perturb(g, &mut r); f(&h, &mut r) }).collect::<Vec<_>>()
        })}).collect();
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect()
    });
    all.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mean = all.iter().sum::<f64>() / all.len() as f64;
    (mean, all[all.len() / 20])
}
