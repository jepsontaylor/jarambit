//! Evaluation record, novelty (k-NN in a 3-D-feature descriptor space, aesthetic passers only),
//! MAP-Elites archive, and the GA loop.  Fitness = SPG x aesthetic x (1 + novelty) for designs
//! that pass the aesthetic floor, every hard gate and the 180/260/1500 N floors; graded negative
//! penalties otherwise (never winners).
use crate::aesthetic::{self, Aes};
use crate::fem::{self, Fem};
use crate::gates;
use crate::genome::*;
use crate::pheno::*;
use jarambit_genotype::Rng;

pub const DESC_N: usize = 12;

#[derive(Clone, Debug)]
pub struct Rec {
    pub id: usize, pub gen: usize, pub g: Genome,
    pub mass_g: f64, pub blank_g: f64, pub t: f64, pub blade: Blade, pub grip: f64,
    pub aes: Aes, pub rejects: Vec<String>, pub fem: Option<Fem>,
    pub spg: f64, pub novelty: f64, pub fit: f64, pub desc: [f64; DESC_N], pub holder_lw: (f64, f64, f64),
    pub removed: [f64; 5], pub min_web: f64,
}
impl Rec {
    pub fn aesthetic_pass(&self) -> bool { self.aes.pass }
    pub fn legal(&self) -> bool { self.rejects.is_empty() && self.fem.as_ref().map_or(false, |f| f.floors_ok) }
}

pub fn descriptor(g: &Genome, p: &Pheno) -> [f64; DESC_N] {
    let blank = (p.area_mm2 * p.t).max(1.0);
    let zone = |r: std::ops::RangeInclusive<usize>| { let v: Vec<f64> = r.clone().map(|i| g.v[i] / cp_delta(i).max(1e-9)).collect(); 0.5 + 0.5 * v.iter().sum::<f64>() / v.len() as f64 };
    let th: Vec<f64> = p.field.th.iter().filter(|v| !v.is_nan()).map(|&v| v as f64).collect();
    let mean = th.iter().sum::<f64>() / th.len().max(1) as f64;
    let cv = (th.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / th.len().max(1) as f64).sqrt() / mean.max(1e-9);
    let holes_area: f64 = p.holes.iter().skip(1).map(|h| crate::geom::signed_area(h).abs()).sum();
    [(p.removed[0] / blank * 10.0).min(1.0), (p.removed[1] / blank * 10.0).min(1.0), (p.removed[2] / blank * 20.0).min(1.0),
     (p.removed[3] / blank * 20.0).min(1.0), if g.v[TEX_MODE] >= 0.5 { g.v[TEX_D] / 0.4 } else { 0.0 },
     (holes_area / p.area_mm2.max(1.0) * 5.0).min(1.0), zone(1..=7), zone(9..=13), zone(14..=18), zone(30..=35),
     (cv * 2.0).min(1.0), (g.v[DROP] + 4.0) / 8.0]
}

pub fn evaluate(g: &Genome, id: usize, gen: usize, fem_area: f64) -> Rec {
    let p = build(g);
    let aes = aesthetic::evaluate(g, &p);
    let rejects = gates::check(g, &p);
    let (_, l, w, ang) = gates::holder_fit(&p.outline);
    let desc = descriptor(g, &p);
    let fem = if aes.pass && rejects.is_empty() { fem::run(&p, fem_area, false).map(|x| x.0) } else { None };
    let spg = fem.as_ref().map_or(0.0, |f| f.lat_rob / p.mass_g);
    Rec { id, gen, g: g.clone(), mass_g: p.mass_g, blank_g: p.blank_g, t: p.t, blade: p.blade.clone(), grip: p.grip_len, aes, rejects, fem,
        spg, novelty: 0.0, fit: 0.0, desc, holder_lw: (l, w, ang), removed: p.removed, min_web: p.min_web }
}

fn d2(a: &[f64; DESC_N], b: &[f64; DESC_N]) -> f64 { a.iter().zip(b).map(|(x, y)| (x - y).powi(2)).sum::<f64>().sqrt() }

/// Novelty among aesthetic passers only: mean distance to the k nearest passers (archive + pop).
pub fn novelty(d: &[f64; DESC_N], others: &[[f64; DESC_N]], k: usize) -> f64 {
    let mut v: Vec<f64> = others.iter().map(|o| d2(d, o)).filter(|x| *x > 1e-12).collect();
    if v.is_empty() { return 0.0; }
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let k = k.min(v.len()); v[..k].iter().sum::<f64>() / k as f64
}

pub fn fitness(r: &Rec) -> f64 {
    if !r.aes.pass { return -200.0 - r.aes.fails.len() as f64 - r.aes.hausdorff; }
    if !r.rejects.is_empty() { return -100.0 - r.rejects.len() as f64; }
    match &r.fem { None => -50.0,
        Some(f) if !f.floors_ok => -1.0 - 10.0 * ((1.0 - f.lat_rob / 260.0).max(0.0) + (1.0 - f.ring_rob / 1500.0).max(0.0)),
        Some(_) => r.spg * r.aes.score * (1.0 + r.novelty) }
}

/// Total 3-D feature volume removed / blank volume (relief + lattice + fuller + flutes).
pub fn relief_frac(r: &Rec) -> f64 { r.desc[0] / 10.0 + r.desc[1] / 10.0 + r.desc[2] / 20.0 + r.desc[3] / 20.0 }
/// MAP-Elites cell: (3-D relief volume fraction bin, Hausdorff-to-C.4 bin). Relief bins are
/// graded for the measured range (0.5-6.5 % of the blank) so the 3-D axis actually resolves.
pub fn qd_cell(r: &Rec) -> (usize, usize) {
    const RB: [f64; 7] = [0.005, 0.01, 0.015, 0.02, 0.03, 0.045, 0.065];
    let f = relief_frac(r);
    (RB.iter().filter(|&&b| f >= b).count(), ((r.aes.hausdorff / aesthetic::HAUSDORFF_MAX_MM * 6.0).floor() as usize).min(5))
}

pub struct RunCfg { pub pop: usize, pub gens: usize, pub threads: usize, pub seed: u64, pub fem_area: f64, pub t_seed: f64 }

pub fn eval_batch(gs: Vec<(Genome, usize)>, gen: usize, cfg: &RunCfg) -> Vec<Rec> {
    let n = gs.len(); let th = cfg.threads.max(1).min(n.max(1));
    let chunks: Vec<Vec<(Genome, usize)>> = (0..th).map(|t| gs.iter().enumerate().filter(|(i, _)| i % th == t).map(|(_, x)| x.clone()).collect()).collect();
    let mut out: Vec<Rec> = std::thread::scope(|s| {
        let hs: Vec<_> = chunks.into_iter().map(|c| s.spawn(move || c.into_iter().map(|(g, id)| evaluate(&g, id, gen, cfg.fem_area)).collect::<Vec<_>>())).collect();
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect()
    });
    out.sort_by_key(|r| r.id); out
}

pub struct RunOut { pub all: Vec<Rec>, pub archive: std::collections::BTreeMap<(usize, usize), Rec>, pub history: Vec<String> }

pub fn run(cfg: &RunCfg, mut log: impl FnMut(&str)) -> RunOut {
    let mut rng = Rng(cfg.seed);
    let seed = Genome::c4_seed(cfg.t_seed);
    let mut next_id = 0usize;
    let mut init = vec![(seed.clone(), { next_id += 1; next_id - 1 })];
    while init.len() < cfg.pop { let s = if init.len() % 4 == 0 { 0.25 } else { 0.08 }; init.push((seed.mutate(&mut rng, s), { next_id += 1; next_id - 1 })); }
    let mut pop = eval_batch(init, 0, cfg);
    let mut all: Vec<Rec> = Vec::new();
    let mut nov_mem: Vec<[f64; DESC_N]> = Vec::new();
    let mut archive: std::collections::BTreeMap<(usize, usize), Rec> = std::collections::BTreeMap::new();
    let mut history = vec!["gen,evals,aesthetic_pass,legal,best_fit,best_spg,best_mass_g,best_aes,best_nov,archive_cells,mean_hausdorff_pass".to_string()];
    for gen in 0..=cfg.gens {
        // novelty among aesthetic passers only (archive memory + current passers)
        let pass_desc: Vec<[f64; DESC_N]> = pop.iter().filter(|r| r.aes.pass).map(|r| r.desc).collect();
        let mut ctx = nov_mem.clone(); ctx.extend(pass_desc.iter().copied());
        for r in pop.iter_mut() { r.novelty = if r.aes.pass { novelty(&r.desc, &ctx, 5) } else { 0.0 }; r.fit = fitness(r); }
        for r in pop.iter() { if r.aes.pass { nov_mem.push(r.desc); }
            if r.legal() { let c = qd_cell(r); if archive.get(&c).map_or(true, |e| r.fit > e.fit) { archive.insert(c, r.clone()); } } }
        if nov_mem.len() > 4000 { let k = nov_mem.len() - 4000; nov_mem.drain(..k); }
        all.extend(pop.iter().cloned());
        let np = pop.iter().filter(|r| r.aes.pass).count(); let nl = pop.iter().filter(|r| r.legal()).count();
        let best = pop.iter().max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap()).unwrap();
        let mh = { let v: Vec<f64> = pop.iter().filter(|r| r.aes.pass).map(|r| r.aes.hausdorff).collect(); v.iter().sum::<f64>() / v.len().max(1) as f64 };
        let line = format!("{gen},{},{np},{nl},{:.4},{:.4},{:.2},{:.3},{:.3},{},{:.2}", pop.len(), best.fit, best.spg, best.mass_g, best.aes.score, best.novelty, archive.len(), mh);
        log(&line); history.push(line);
        if gen == cfg.gens { break; }
        // ---- next generation: elitism + tournament + crossover + envelope mutation + archive draws ----
        let mut sorted = pop.clone(); sorted.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap());
        let mut kids: Vec<(Genome, usize)> = Vec::new();
        let elites: Vec<Genome> = sorted.iter().take(4).map(|r| r.g.clone()).collect();
        let arch: Vec<Genome> = archive.values().map(|r| r.g.clone()).collect();
        let tour = |rng: &mut Rng| { let a = &sorted[(rng.f64() * sorted.len() as f64) as usize]; let b = &sorted[(rng.f64() * sorted.len() as f64) as usize]; if a.fit >= b.fit { a.g.clone() } else { b.g.clone() } };
        while kids.len() < cfg.pop - elites.len() {
            let pa = if !arch.is_empty() && rng.f64() < 0.25 { arch[(rng.f64() * arch.len() as f64) as usize].clone() } else { tour(&mut rng) };
            let child = if rng.f64() < 0.5 { let pb = tour(&mut rng); pa.crossover(&pb, &mut rng).mutate(&mut rng, 0.06) } else { pa.mutate(&mut rng, 0.1) };
            kids.push((child, { next_id += 1; next_id - 1 }));
        }
        let mut newpop: Vec<Rec> = sorted.into_iter().take(elites.len()).map(|mut r| { r.gen = gen + 1; r }).collect();
        newpop.extend(eval_batch(kids, gen + 1, cfg));
        pop = newpop;
    }
    RunOut { all, archive, history }
}
