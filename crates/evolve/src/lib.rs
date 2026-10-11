//! (mu+lambda) evolution with red-team hard constraints and MC-robust fitness.
use jarambit_genotype::{Genotype, Rng};
use jarambit_phenotype::Phenotype;
use jarambit_physics::{evaluate, TI_6AL_4V};

pub struct Config { pub pop: usize, pub gens: usize, pub mc_samples: usize, pub threads: usize, pub seed: u64, pub load_n: f64 }

pub fn fitness_once(g: &Genotype, load_n: f64) -> f64 {
    let p = Phenotype::from_genotype(g);
    if jarambit_redteam::check(g, &p).is_err() { return -1e9; }
    let e = evaluate(&p, g.edge_angle_deg, g.blade_arc_len, load_n, &TI_6AL_4V);
    let sf_term = if e.safety_factor < 2.0 { -10.0 * (2.0 - e.safety_factor) } else { (e.safety_factor - 2.0).min(2.0) * 0.2 };
    3.0 * e.sharpness + 1.5 * e.serration_score + 1.0 * e.ergonomics + sf_term - 0.01 * e.mass_g
}

pub fn run(cfg: &Config, mut log: impl FnMut(usize, &Genotype, f64)) -> (Genotype, f64) {
    let mut r = Rng(cfg.seed);
    let score = |g: &Genotype, s: u64| jarambit_monte_carlo::run(g, cfg.mc_samples, cfg.threads, s, |h, _| fitness_once(h, cfg.load_n)).1;
    let mut pop: Vec<(Genotype, f64)> = (0..cfg.pop).map(|i| { let g = Genotype::random(&mut r); let f = score(&g, i as u64); (g, f) }).collect();
    for gen in 0..cfg.gens {
        pop.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        log(gen, &pop[0].0, pop[0].1);
        let elite = (cfg.pop / 4).max(2);
        let mut kids = vec![];
        while kids.len() < cfg.pop - elite {
            let a = &pop[(r.f64() * elite as f64) as usize].0; let b = &pop[(r.f64() * elite as f64) as usize].0;
            let c = a.crossover(b, &mut r).mutate(&mut r, 0.08);
            let f = score(&c, r.next_u64()); kids.push((c, f));
        }
        pop.truncate(elite); pop.extend(kids);
    }
    pop.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    pop.swap_remove(0)
}
