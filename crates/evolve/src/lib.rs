//! (mu+lambda) evolution, PRIMARY fitness = MC-p05 strength-per-gram (N/g) subject to hiker+hunter
//! floors; red-team gate on every candidate and every MC sample; per-generation stats, Pareto
//! archive (strength vs mass), diversity, and quarantine of rejected phenotypes.
//! NSGA-II / island GA = grok lane C (keep the primary scalar + floors when replacing this).
use jarambit_genotype::{Genotype, Rng};
use jarambit_phenotype::Phenotype;
use jarambit_physics::{evaluate, material, primary_fitness, Eval};

pub struct Config { pub pop: usize, pub gens: usize, pub mc_samples: usize, pub threads: usize, pub seed: u64 }

/// Nominal (20 C, no tolerance) evaluation incl. red-team verdict.
pub fn nominal(g: &Genotype) -> (Phenotype, Result<(), Vec<jarambit_redteam::Reject>>, Eval) {
    let p = Phenotype::from_genotype(g);
    let rt = jarambit_redteam::check(g, &p);
    let e = evaluate(&p, g.edge_angle_deg, (g.serr_inner.depth, g.serr_outer.depth), material(g.material), 20.0);
    (p, rt, e)
}

/// One MC sample: red-team reject => -1e3 (dominates p05), else primary fitness at sampled temp/thickness.
pub fn fitness_sample(h: &Genotype, r: &mut Rng) -> f64 {
    let mut p = Phenotype::from_genotype(h);
    if jarambit_redteam::check(h, &p).is_err() { return -1e3; }
    p.thickness = jarambit_monte_carlo::thickness_sample(h, r);
    let env = jarambit_monte_carlo::env_sample(r);
    let e = evaluate(&p, h.edge_angle_deg, (h.serr_inner.depth, h.serr_outer.depth), material(h.material), env.temp_c);
    primary_fitness(&e)
}

#[derive(Clone, Debug)]
pub struct Indiv { pub g: Genotype, pub fit: f64, pub mean: f64, pub strength_n: f64, pub mass_g: f64, pub floors_ok: bool }

pub struct GenStats<'a> { pub gen: usize, pub pop: &'a [Indiv], pub diversity: f64, pub rejected: usize, pub quarantine: Vec<(Genotype, String)> }

pub fn diversity(pop: &[Indiv]) -> f64 {
    let n = pop.len(); if n < 2 { return 0.0; }
    let mut s = 0.0; let mut c = 0;
    for i in 0..n { for j in (i + 1)..n { s += pop[i].g.distance(&pop[j].g); c += 1; } }
    s / c as f64
}

/// Non-dominated set: maximise strength, minimise mass, among floor-feasible red-team-clean designs.
pub fn pareto(arch: &[Indiv]) -> Vec<Indiv> {
    let f: Vec<&Indiv> = arch.iter().filter(|a| a.floors_ok && a.fit > 0.0).collect();
    f.iter().filter(|a| !f.iter().any(|b| b.strength_n >= a.strength_n && b.mass_g <= a.mass_g && (b.strength_n > a.strength_n || b.mass_g < a.mass_g)))
        .map(|a| (*a).clone()).collect()
}

pub fn run(cfg: &Config, mut log: impl FnMut(&GenStats)) -> (Indiv, Vec<Indiv>) {
    let mut r = Rng(cfg.seed);
    let mut archive: Vec<Indiv> = vec![];
    let eval = |g: Genotype, s: u64, q: &mut Vec<(Genotype, String)>| -> Indiv {
        let (_, rt, e) = nominal(&g);
        if let Err(v) = &rt { q.push((g.clone(), format!("{v:?}"))); }
        let (mean, p05) = jarambit_monte_carlo::run(&g, cfg.mc_samples, cfg.threads, s, fitness_sample);
        let fit = if rt.is_err() { -1e3 } else { p05 };
        Indiv { g, fit, mean, strength_n: e.strength_n, mass_g: e.mass_g, floors_ok: e.floors_ok() && rt.is_ok() }
    };
    let mut q = vec![];
    let mut pop: Vec<Indiv> = (0..cfg.pop).map(|i| { let g = Genotype::random(&mut r); eval(g, i as u64 + 1, &mut q) }).collect();
    archive.extend(pop.iter().cloned());
    for gen in 0..cfg.gens {
        pop.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap());
        let rejected = q.len();
        log(&GenStats { gen, pop: &pop, diversity: diversity(&pop), rejected, quarantine: std::mem::take(&mut q) });
        let elite = (cfg.pop / 4).max(2);
        let mut kids = vec![];
        while kids.len() < cfg.pop - elite {
            // tournament on top half + diversity injection 10%
            let pick = |r: &mut Rng| { let a = (r.f64() * (cfg.pop / 2).max(2) as f64) as usize; let b = (r.f64() * (cfg.pop / 2).max(2) as f64) as usize; a.min(b) };
            let c = if r.f64() < 0.1 { Genotype::random(&mut r) } else {
                let (ia, ib) = (pick(&mut r), pick(&mut r));
                pop[ia].g.crossover(&pop[ib].g, &mut r).mutate(&mut r, 0.08)
            };
            let s = r.next_u64(); kids.push(eval(c, s, &mut q));
        }
        archive.extend(kids.iter().cloned());
        pop.truncate(elite); pop.extend(kids);
    }
    pop.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap());
    let front = pareto(&archive);
    (pop.swap_remove(0), front)
}
