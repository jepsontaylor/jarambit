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

pub const DESC_N: usize = 16;

#[derive(Clone, Debug)]
pub struct Rec {
    pub id: usize, pub gen: usize, pub g: Genome,
    pub mass_g: f64, pub blank_g: f64, pub t: f64, pub blade: Blade, pub grip: f64,
    pub aes: Aes, pub rejects: Vec<String>, pub fem: Option<Fem>,
    pub spg: f64, pub novelty: f64, pub fit: f64, pub desc: [f64; DESC_N], pub holder_lw: (f64, f64, f64),
    pub removed: [f64; NREM], pub min_web: f64, pub n_win: usize, pub win_area: f64, pub n_perf: usize, pub perf_area: f64,
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
     (cv * 2.0).min(1.0), (g.v[DROP] + 4.0) / 8.0,
     // internal machining layer (wave7+): isogrid pockets, pierced-fuller windows, ring flute
     (p.removed[5] / blank * 8.0).min(1.0), (p.win_area / p.area_mm2.max(1.0) * 12.0).min(1.0), (p.removed[6] / blank * 25.0).min(1.0), (p.perf_area / p.area_mm2.max(1.0) * 12.0).min(1.0)]
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
        spg, novelty: 0.0, fit: 0.0, desc, holder_lw: (l, w, ang), removed: p.removed, min_web: p.min_web, n_win: p.n_win, win_area: p.win_area, n_perf: p.n_perf, perf_area: p.perf_area }
}

fn d2(a: &[f64; DESC_N], b: &[f64; DESC_N]) -> f64 { a.iter().zip(b).map(|(x, y)| (x - y).powi(2)).sum::<f64>().sqrt() }

/// Novelty among aesthetic passers only: mean distance to the k nearest passers (archive + pop).
pub fn novelty(d: &[f64; DESC_N], others: &[[f64; DESC_N]], k: usize) -> f64 {
    let mut v: Vec<f64> = others.iter().map(|o| d2(d, o)).filter(|x| *x > 1e-12).collect();
    if v.is_empty() { return 0.0; }
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let k = k.min(v.len()); v[..k].iter().sum::<f64>() / k as f64
}

/// Optional finished-mass target (g) for the sub-80 g lane: JARAMBIT_MASS_CAP. It is a TARGET, not a
/// relaxed constraint: designs over it stay LEGAL (all hard items hold) but rank below every design
/// that is legal AND under the cap. Unset => original wave6 fitness.
pub fn mass_cap() -> Option<f64> {
    static C: std::sync::OnceLock<Option<f64>> = std::sync::OnceLock::new();
    *C.get_or_init(|| std::env::var("JARAMBIT_MASS_CAP").ok().and_then(|v| v.parse::<f64>().ok()).filter(|c| *c > 20.0))
}
pub fn under_cap(r: &Rec) -> bool { mass_cap().map_or(true, |c| r.mass_g < c) }

pub fn fitness(r: &Rec) -> f64 {
    if !r.aes.pass { return -200.0 - r.aes.fails.len() as f64 - r.aes.hausdorff; }
    if !r.rejects.is_empty() { return -100.0 - r.rejects.len() as f64; }
    let excess = mass_cap().map_or(0.0, |c| (r.mass_g / c - 1.0).max(0.0));
    match &r.fem { None => -50.0,
        Some(f) if !f.floors_ok => -1.0 - 10.0 * ((1.0 - f.lat_rob / 260.0).max(0.0) + (1.0 - f.ring_rob / 1500.0).max(0.0)) - 10.0 * excess,
        Some(_) if excess > 0.0 || !under_cap(r) => -0.5 - 10.0 * excess,
        Some(_) => r.spg * r.aes.score * (1.0 + r.novelty) }
}

/// Total machined volume removed / blank volume: 3-D relief + lattice + fuller + flutes + texture +
/// isogrid + ring flute + pierced-fuller windows (window area x stock).
pub fn relief_frac(r: &Rec) -> f64 { let blank = (r.blank_g / jarambit_physics::material(r.g.mat).density * 1000.0).max(1.0);
    (r.removed.iter().sum::<f64>() + (r.win_area + r.perf_area) * r.t) / blank }
/// MAP-Elites cell: (3-D relief volume fraction bin, Hausdorff-to-C.4 bin). Relief bins are
/// graded for the measured range (0.5-6.5 % of the blank) so the 3-D axis actually resolves.
/// wave7+: archive cell = (machined-removal fraction bin, finished-mass bin of 2 g from 72 to 90 g).
pub fn qd_cell(r: &Rec) -> (usize, usize) {
    const RB: [f64; 10] = [0.005, 0.01, 0.02, 0.03, 0.045, 0.065, 0.09, 0.12, 0.16, 0.21];
    let f = relief_frac(r);
    (RB.iter().filter(|&&b| f >= b).count(), (((r.mass_g - 72.0) / 2.0).floor().max(0.0) as usize).min(10))
}

pub struct RunCfg { pub pop: usize, pub gens: usize, pub threads: usize, pub seed: u64, pub fem_area: f64, pub t_seed: f64 }

/// Island GA + MAP-Elites/novelty for the internal-machining lane.
pub struct IslandCfg { pub base: RunCfg, pub islands: usize, pub migrate_every: usize, pub migrants: usize, pub seeds: Vec<Genome>, pub kick_frac: f64 }

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


/// Island GA (ring migration) with a SHARED novelty memory and MAP-Elites archive. Islands differ in
/// mutation pressure (exploit .. explore). Seeds: certified crescents + C.4; a `kick_frac` share of
/// each initial island gets the internal-machining layer switched on at random.
pub fn run_islands(cfg: &IslandCfg, mut log: impl FnMut(&str), mut snap: impl FnMut(usize, &[Rec], &std::collections::BTreeMap<(usize, usize), Rec>)) -> RunOut {
    let b = &cfg.base; let k = cfg.islands.max(1);
    let mut rng = Rng(b.seed);
    let mut seeds = cfg.seeds.clone(); if seeds.is_empty() { seeds.push(Genome::c4_seed(b.t_seed)); }
    let mut next_id = 0usize;
    let mut init: Vec<(Genome, usize)> = Vec::new();
    for isl in 0..k { for j in 0..b.pop {
        let s = &seeds[(isl + j) % seeds.len()];
        let g = if j < seeds.len().min(4) { s.clone() } else if rng.f64() < cfg.kick_frac { s.machining_kick(&mut rng).mutate(&mut rng, 0.05) } else { s.mutate(&mut rng, if j % 4 == 0 { 0.2 } else { 0.08 }) };
        init.push((g, next_id)); next_id += 1; } }
    let ev = eval_batch(init, 0, b);
    let mut pops: Vec<Vec<Rec>> = ev.chunks(b.pop).map(|c| c.to_vec()).collect();
    let sig: Vec<f64> = (0..k).map(|i| 0.05 + 0.12 * i as f64 / (k.max(2) - 1) as f64).collect();
    let mut all: Vec<Rec> = Vec::new();
    let mut nov_mem: Vec<[f64; DESC_N]> = Vec::new();
    let mut archive: std::collections::BTreeMap<(usize, usize), Rec> = std::collections::BTreeMap::new();
    let mut history = vec!["gen,island,evals,aesthetic_pass,legal,legal_under_cap,best_fit,best_spg,best_mass_g,best_aes,best_nov,archive_cells,min_legal_mass_g,mean_relief_frac_pass".to_string()];
    for gen in 0..=b.gens {
        let mut ctx = nov_mem.clone();
        for p in &pops { ctx.extend(p.iter().filter(|r| r.aes.pass).map(|r| r.desc)); }
        for p in pops.iter_mut() { for r in p.iter_mut() { r.novelty = if r.aes.pass { novelty(&r.desc, &ctx, 5) } else { 0.0 }; r.fit = fitness(r); } }
        for (isl, p) in pops.iter().enumerate() {
            for r in p.iter() { if r.gen == gen || gen == 0 { if r.aes.pass { nov_mem.push(r.desc); } all.push(r.clone()); }
                if r.legal() { let c = qd_cell(r); if archive.get(&c).map_or(true, |e| r.fit > e.fit) { archive.insert(c, r.clone()); } } }
            let np = p.iter().filter(|r| r.aes.pass).count(); let nl = p.iter().filter(|r| r.legal()).count(); let nu = p.iter().filter(|r| r.legal() && under_cap(r)).count();
            let best = p.iter().max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap()).unwrap();
            let mlm = p.iter().filter(|r| r.legal()).map(|r| r.mass_g).fold(f64::NAN, f64::min);
            let mrf = { let v: Vec<f64> = p.iter().filter(|r| r.aes.pass).map(relief_frac).collect(); v.iter().sum::<f64>() / v.len().max(1) as f64 };
            let line = format!("{gen},{isl},{},{np},{nl},{nu},{:.4},{:.4},{:.2},{:.3},{:.3},{},{:.2},{:.4}", p.len(), best.fit, best.spg, best.mass_g, best.aes.score, best.novelty, archive.len(), mlm, mrf);
            log(&line); history.push(line);
        }
        if nov_mem.len() > 6000 { let d = nov_mem.len() - 6000; nov_mem.drain(..d); }
        snap(gen, &all, &archive);
        if gen == b.gens { break; }
        // ---- migration (ring): best `migrants` of island i replace the worst of island i+1 ----
        if k > 1 && cfg.migrate_every > 0 && gen > 0 && gen % cfg.migrate_every == 0 {
            let best: Vec<Vec<Rec>> = pops.iter().map(|p| { let mut s = p.clone(); s.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap()); s.into_iter().take(cfg.migrants).collect() }).collect();
            for i in 0..k { let to = (i + 1) % k; let p = &mut pops[to]; p.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap());
                let n = p.len(); for (j, m) in best[i].iter().enumerate() { if j < n { p[n - 1 - j] = m.clone(); } } }
        }
        let arch: Vec<Genome> = archive.values().map(|r| r.g.clone()).collect();
        let mut kids: Vec<(Genome, usize)> = Vec::new(); let mut keep: Vec<Vec<Rec>> = Vec::new();
        for (isl, p) in pops.iter().enumerate() {
            let mut sorted = p.clone(); sorted.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap());
            let ne = 3usize.min(sorted.len());
            keep.push(sorted.iter().take(ne).cloned().collect());
            let tour = |rng: &mut Rng| { let a = &sorted[(rng.f64() * sorted.len() as f64) as usize]; let c = &sorted[(rng.f64() * sorted.len() as f64) as usize]; if a.fit >= c.fit { a.g.clone() } else { c.g.clone() } };
            for _ in 0..b.pop - ne {
                let pa = if !arch.is_empty() && rng.f64() < 0.3 { arch[(rng.f64() * arch.len() as f64) as usize].clone() } else { tour(&mut rng) };
                let mut child = if rng.f64() < 0.5 { let pb = tour(&mut rng); pa.crossover(&pb, &mut rng).mutate(&mut rng, sig[isl] * 0.6) } else { pa.mutate(&mut rng, sig[isl]) };
                if rng.f64() < 0.04 { child = child.machining_kick(&mut rng); }
                kids.push((child, next_id)); next_id += 1;
            }
        }
        let ev = eval_batch(kids, gen + 1, b);
        let mut it = ev.into_iter();
        for (isl, p) in pops.iter_mut().enumerate() { let mut np = keep[isl].clone(); while np.len() < b.pop { if let Some(r) = it.next() { np.push(r); } else { break; } } *p = np; }
    }
    RunOut { all, archive, history }
}
