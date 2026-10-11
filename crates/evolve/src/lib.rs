//! NSGA-II with optional island migration.
//! PRIMARY fitness stays MC-p05 strength-per-gram (N/g) subject to hiker+hunter floors.
//! Secondary objectives (mass, blade-first cut margin) shape the front; the logged
//! Pareto view remains nominal strength vs mass. Red-team gate on every candidate
//! and every MC sample. Checkpoint is one text file, overwritten each generation.
use jarambit_genotype::{Genotype, Rng, TiGrade};
use jarambit_monte_carlo::{cut_margin, media_sample, run_cols};
use jarambit_phenotype::Phenotype;
use jarambit_physics::{evaluate, material, primary_fitness, Eval};

pub struct Config {
    pub pop: usize,
    pub gens: usize,
    pub mc_samples: usize,
    pub threads: usize,
    pub seed: u64,
    /// Independent NSGA-II populations. `1` is a single population.
    pub islands: usize,
    /// Ring-migrate the primary-best individual every this many generations. `0` disables.
    pub migrate_every: usize,
    /// Overwritten each completed generation. Also the resume source.
    pub checkpoint: Option<String>,
    pub resume: bool,
}

impl Config {
    pub fn new(pop: usize, gens: usize, mc_samples: usize, threads: usize, seed: u64) -> Self {
        Self { pop, gens, mc_samples, threads, seed, islands: 1, migrate_every: 5, checkpoint: None, resume: false }
    }
}

/// Nominal (20 C, no tolerance) evaluation incl. red-team verdict.
pub fn nominal(g: &Genotype) -> (Phenotype, Result<(), Vec<jarambit_redteam::Reject>>, Eval) {
    let p = Phenotype::from_genotype(g);
    let rt = jarambit_redteam::check(g, &p);
    let e = evaluate(&p, g.edge_angle_deg, (g.serr_inner.depth, g.serr_outer.depth), material(g.material), 20.0);
    (p, rt, e)
}

/// One MC sample's objective columns: primary fitness, blade-first cut margin, sharpness.
fn sample_metrics(h: &Genotype, r: &mut Rng) -> [f64; 3] {
    let mut p = Phenotype::from_genotype(h);
    if jarambit_redteam::check(h, &p).is_err() { return [-1e3, -1.0, 0.0]; }
    p.thickness = jarambit_monte_carlo::thickness_sample(h, r);
    let env = jarambit_monte_carlo::env_sample(r);
    let e = evaluate(&p, h.edge_angle_deg, (h.serr_inner.depth, h.serr_outer.depth), material(h.material), env.temp_c);
    let margin = cut_margin(e.blade_lat_n, e.inplane_n, e.sharpness, e.serration_score, media_sample(r));
    [primary_fitness(&e), margin, e.sharpness]
}

/// One MC sample: red-team reject => -1e3 (dominates p05), else primary fitness at sampled temp/thickness.
pub fn fitness_sample(h: &Genotype, r: &mut Rng) -> f64 { sample_metrics(h, r)[0] }

#[derive(Clone, Debug)]
pub struct Indiv {
    pub g: Genotype,
    pub fit: f64,
    pub mean: f64,
    pub strength_n: f64,
    pub mass_g: f64,
    pub floors_ok: bool,
    pub cut_p05: f64,
    pub sharp_p05: f64,
}
impl Indiv {
    /// Floor-feasible and red-team-clean on the nominal geometry, with a positive robust score.
    pub fn feasible(&self) -> bool { self.floors_ok && self.fit > 0.0 }
}

pub struct GenStats<'a> {
    pub gen: usize,
    pub pop: &'a [Indiv],
    pub diversity: f64,
    pub rejected: usize,
    pub quarantine: Vec<(Genotype, String)>,
}

pub fn diversity(pop: &[Indiv]) -> f64 {
    let n = pop.len(); if n < 2 { return 0.0; }
    let mut s = 0.0; let mut c = 0;
    for i in 0..n { for j in (i + 1)..n { s += pop[i].g.distance(&pop[j].g); c += 1; } }
    s / c as f64
}

/// Non-dominated set: maximise strength, minimise mass, among floor-feasible red-team-clean designs.
pub fn pareto(arch: &[Indiv]) -> Vec<Indiv> {
    let f: Vec<&Indiv> = arch.iter().filter(|a| a.feasible()).collect();
    f.iter().filter(|a| !f.iter().any(|b| b.strength_n >= a.strength_n && b.mass_g <= a.mass_g && (b.strength_n > a.strength_n || b.mass_g < a.mass_g)))
        .map(|a| (*a).clone()).collect()
}

fn obj(i: &Indiv, k: usize) -> f64 {
    match k { 0 => i.fit, 1 => i.mass_g, _ => i.cut_p05 }
}

/// Constraint domination: any feasible design dominates any infeasible one.
/// Feasible: max fit, min mass, max cut margin. Infeasible: less-negative primary penalty wins.
pub fn dominates(a: &Indiv, b: &Indiv) -> bool {
    let (fa, fb) = (a.feasible(), b.feasible());
    if fa != fb { return fa; }
    if !fa { return a.fit > b.fit + 1e-9; }
    let ge = a.fit >= b.fit - 1e-9 && a.mass_g <= b.mass_g + 1e-9 && a.cut_p05 >= b.cut_p05 - 1e-9;
    let gt = a.fit > b.fit + 1e-9 || a.mass_g < b.mass_g - 1e-9 || a.cut_p05 > b.cut_p05 + 1e-9;
    ge && gt
}

fn nondominated_sort(pop: &[Indiv]) -> Vec<Vec<usize>> {
    let n = pop.len();
    let mut n_p = vec![0usize; n];
    let mut beats: Vec<Vec<usize>> = vec![Vec::new(); n];
    let mut fronts: Vec<Vec<usize>> = vec![Vec::new()];
    for i in 0..n {
        for j in 0..n {
            if i == j { continue; }
            if dominates(&pop[i], &pop[j]) { beats[i].push(j); }
            else if dominates(&pop[j], &pop[i]) { n_p[i] += 1; }
        }
        if n_p[i] == 0 { fronts[0].push(i); }
    }
    let mut f = 0;
    while !fronts[f].is_empty() {
        let mut next = Vec::new();
        for &i in &fronts[f] {
            for &j in &beats[i] {
                n_p[j] -= 1;
                if n_p[j] == 0 { next.push(j); }
            }
        }
        f += 1;
        fronts.push(next);
    }
    fronts.pop();
    fronts
}

fn crowding(front: &[usize], pop: &[Indiv]) -> Vec<f64> {
    let m = front.len();
    if m <= 2 { return vec![f64::INFINITY; m]; }
    let mut cd = vec![0.0; m];
    for k in 0..3 {
        let mut order: Vec<usize> = (0..m).collect();
        order.sort_by(|&a, &b| obj(&pop[front[a]], k).partial_cmp(&obj(&pop[front[b]], k)).unwrap_or(std::cmp::Ordering::Equal));
        cd[order[0]] = f64::INFINITY;
        cd[order[m - 1]] = f64::INFINITY;
        let lo = obj(&pop[front[order[0]]], k);
        let hi = obj(&pop[front[order[m - 1]]], k);
        let span = (hi - lo).abs().max(1e-12);
        for t in 1..m - 1 {
            let prev = obj(&pop[front[order[t - 1]]], k);
            let next = obj(&pop[front[order[t + 1]]], k);
            cd[order[t]] += (next - prev).abs() / span;
        }
    }
    cd
}

fn rank_crowd(pop: &[Indiv]) -> (Vec<usize>, Vec<f64>) {
    let fronts = nondominated_sort(pop);
    let mut rank = vec![usize::MAX; pop.len()];
    let mut crowd = vec![0.0; pop.len()];
    for (r, front) in fronts.iter().enumerate() {
        let cd = crowding(front, pop);
        for (k, &i) in front.iter().enumerate() { rank[i] = r; crowd[i] = cd[k]; }
    }
    (rank, crowd)
}

/// Keep `n` individuals. Extremes of each objective sit on the first front and have
/// infinite crowding, so the primary-best design is not dropped when it is unique.
pub fn truncate(pop: Vec<Indiv>, n: usize) -> Vec<Indiv> {
    if pop.len() <= n { return pop; }
    let fronts = nondominated_sort(&pop);
    let mut chosen = Vec::with_capacity(n);
    for front in &fronts {
        if chosen.len() + front.len() <= n { chosen.extend(front.iter().copied()); }
        else {
            let cd = crowding(front, &pop);
            let mut order: Vec<usize> = (0..front.len()).collect();
            order.sort_by(|&a, &b| cd[b].partial_cmp(&cd[a]).unwrap_or(std::cmp::Ordering::Equal));
            let need = n - chosen.len();
            chosen.extend(order.into_iter().take(need).map(|i| front[i]));
            break;
        }
    }
    let mut keep = vec![false; pop.len()];
    for i in chosen { keep[i] = true; }
    pop.into_iter().enumerate().filter_map(|(i, ind)| keep[i].then_some(ind)).collect()
}

fn tournament(pop: &[Indiv], rank: &[usize], crowd: &[f64], r: &mut Rng) -> usize {
    let n = pop.len();
    let at = |r: &mut Rng| { let x = (r.f64() * n as f64) as usize; if x >= n { n - 1 } else { x } };
    let i = at(r); let j = at(r);
    if rank[i] < rank[j] { i }
    else if rank[j] < rank[i] { j }
    else if crowd[i] >= crowd[j] { i } else { j }
}

struct Island { rng: Rng, pop: Vec<Indiv> }

fn evaluate_one(g: Genotype, sample_seed: u64, mc: usize, threads: usize, q: &mut Vec<(Genotype, String)>) -> Indiv {
    let (_, rt, e) = nominal(&g);
    let crazy = !e.mass_g.is_finite() || !(5.0..=250.0).contains(&e.mass_g);
    if let Err(v) = &rt { q.push((g.clone(), format!("{v:?}"))); }
    else if crazy { q.push((g.clone(), format!("crazy phenotype mass {:.2} g", e.mass_g))); }
    let cols = run_cols(&g, mc, threads, sample_seed, sample_metrics);
    let fit = if rt.is_err() || crazy { -1e3 } else { cols[0].p05 };
    Indiv { g, fit, mean: cols[0].mean, strength_n: e.strength_n, mass_g: e.mass_g, floors_ok: e.floors_ok() && rt.is_ok() && !crazy, cut_p05: cols[1].p05, sharp_p05: cols[2].p05 }
}

fn genes_exact(g: &Genotype) -> String {
    let v = g.to_vec();
    let mut s: Vec<String> = v.iter().enumerate().map(|(i, x)| if i == 2 { format!("{x:.1}") } else { format!("{x:.8}") }).collect();
    s.push(g.material.name().into());
    s.join(",")
}

fn parse_genes(csv: &str) -> Result<Genotype, String> {
    let cols: Vec<&str> = csv.split(',').collect();
    if cols.len() != 21 { return Err(format!("gene columns {}", cols.len())); }
    let mut v = [0.0; 20];
    for i in 0..20 { v[i] = cols[i].parse().map_err(|_| format!("gene {i}"))?; }
    let mat = match cols[20] {
        "Ti-3Al-2.5V" => TiGrade::Ti3Al2_5V,
        "Ti-6Al-4V" => TiGrade::Ti6Al4V,
        other => return Err(format!("material {other}")),
    };
    Ok(Genotype::from_vec(&v, mat))
}

fn indiv_line(ind: &Indiv) -> String {
    format!("{:.6} {:.6} {:.4} {:.4} {} {:.6} {:.6} {}",
        ind.fit, ind.mean, ind.strength_n, ind.mass_g, if ind.floors_ok { 1 } else { 0 }, ind.cut_p05, ind.sharp_p05, genes_exact(&ind.g))
}

fn parse_indiv(line: &str) -> Result<Indiv, String> {
    let mut it = line.splitn(8, char::is_whitespace);
    let num = |s: Option<&str>| s.ok_or("short indiv")?.parse::<f64>().map_err(|_| "num".to_string());
    let fit = num(it.next())?;
    let mean = num(it.next())?;
    let strength_n = num(it.next())?;
    let mass_g = num(it.next())?;
    let floors_ok = it.next().ok_or("floors")? == "1";
    let cut_p05 = num(it.next())?;
    let sharp_p05 = num(it.next())?;
    let g = parse_genes(it.next().ok_or("genes")?)?;
    Ok(Indiv { g, fit, mean, strength_n, mass_g, floors_ok, cut_p05, sharp_p05 })
}

fn save_ckpt(path: &str, next_gen: usize, cfg: &Config, islands: &[Island], archive: &[Indiv]) {
    let mut s = String::new();
    s.push_str("jarambit-ckpt 1\n");
    s.push_str(&format!("next_gen {next_gen}\n"));
    s.push_str(&format!("islands {}\n", islands.len()));
    s.push_str(&format!("seed {}\n", cfg.seed));
    s.push_str(&format!("migrate_every {}\n", cfg.migrate_every));
    for (i, isl) in islands.iter().enumerate() {
        s.push_str(&format!("island {i} rng {} n {}\n", isl.rng.0, isl.pop.len()));
        for ind in &isl.pop { s.push_str(&indiv_line(ind)); s.push('\n'); }
    }
    s.push_str(&format!("archive {}\n", archive.len()));
    for ind in archive { s.push_str(&indiv_line(ind)); s.push('\n'); }
    if let Some(dir) = std::path::Path::new(path).parent() { let _ = std::fs::create_dir_all(dir); }
    let tmp = format!("{path}.tmp");
    std::fs::write(&tmp, &s).unwrap_or_else(|e| panic!("checkpoint write {tmp}: {e}"));
    std::fs::rename(&tmp, path).unwrap_or_else(|e| panic!("checkpoint rename {path}: {e}"));
}

struct Loaded { next_gen: usize, islands: Vec<Island>, archive: Vec<Indiv> }

fn load_ckpt(path: &str) -> Result<Loaded, String> {
    let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut lines = text.lines().filter(|l| !l.is_empty());
    let magic = lines.next().ok_or("empty checkpoint")?;
    if magic != "jarambit-ckpt 1" { return Err(format!("bad magic {magic}")); }
    let next_gen: usize = lines.next().ok_or("next_gen")?.split_whitespace().nth(1).ok_or("next_gen")?.parse().map_err(|_| "next_gen")?;
    let nisl: usize = lines.next().ok_or("islands")?.split_whitespace().nth(1).ok_or("islands")?.parse().map_err(|_| "islands")?;
    let _seed = lines.next();
    let _mig = lines.next();
    let mut islands = Vec::with_capacity(nisl);
    for _ in 0..nisl {
        let hdr = lines.next().ok_or("island header")?;
        let p: Vec<&str> = hdr.split_whitespace().collect();
        if p.len() != 6 || p[0] != "island" || p[2] != "rng" || p[4] != "n" { return Err(format!("island header {hdr}")); }
        let rng = Rng(p[3].parse().map_err(|_| "rng")?);
        let n: usize = p[5].parse().map_err(|_| "pop n")?;
        let mut pop = Vec::with_capacity(n);
        for _ in 0..n { pop.push(parse_indiv(lines.next().ok_or("truncated population")?)?); }
        islands.push(Island { rng, pop });
    }
    let an: usize = lines.next().ok_or("archive")?.split_whitespace().nth(1).ok_or("archive n")?.parse().map_err(|_| "archive n")?;
    let mut archive = Vec::with_capacity(an);
    for _ in 0..an { archive.push(parse_indiv(lines.next().ok_or("truncated archive")?)?); }
    Ok(Loaded { next_gen, islands, archive })
}

pub fn run(cfg: &Config, mut log: impl FnMut(&GenStats)) -> (Indiv, Vec<Indiv>) {
    let n_islands = cfg.islands.max(1);
    let pop_n = cfg.pop.max(2);
    let mut q = Vec::new();
    let mut archive: Vec<Indiv> = Vec::new();
    let mut start = 0usize;
    let mut islands: Vec<Island> = if cfg.resume {
        if let Some(path) = cfg.checkpoint.as_deref().filter(|p| std::path::Path::new(p).exists()) {
            let loaded = load_ckpt(path).unwrap_or_else(|e| panic!("resume {path}: {e}"));
            if loaded.islands.len() != n_islands { panic!("checkpoint has {} islands, config asks for {n_islands}", loaded.islands.len()); }
            if loaded.next_gen > start { start = loaded.next_gen; }
            archive = loaded.archive;
            loaded.islands
        } else { Vec::new() }
    } else { Vec::new() };
    if islands.is_empty() {
        islands = (0..n_islands).map(|i| {
            let mut rng = Rng(cfg.seed.wrapping_add((i as u64 + 1).wrapping_mul(0x9E37_79B9_7F4A_7C15)));
            let pop = (0..pop_n).map(|_| {
                let g = Genotype::random(&mut rng);
                let s = rng.next_u64();
                evaluate_one(g, s, cfg.mc_samples, cfg.threads, &mut q)
            }).collect();
            Island { rng, pop }
        }).collect();
        archive.extend(islands.iter().flat_map(|isl| isl.pop.iter().cloned()));
    }
    for gen in start..cfg.gens {
        let mut combined: Vec<Indiv> = islands.iter().flat_map(|isl| isl.pop.iter().cloned()).collect();
        combined.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap_or(std::cmp::Ordering::Equal));
        let rejected = q.len();
        log(&GenStats { gen, pop: &combined, diversity: diversity(&combined), rejected, quarantine: std::mem::take(&mut q) });
        if n_islands > 1 && cfg.migrate_every > 0 && gen > 0 && gen % cfg.migrate_every == 0 {
            let migrants: Vec<Indiv> = islands.iter().map(|isl| {
                isl.pop.iter().max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).unwrap().clone()
            }).collect();
            for i in 0..n_islands {
                let dst_i = (i + 1) % n_islands;
                let worst = islands[dst_i].pop.iter().enumerate().min_by(|(_, a), (_, b)| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).map(|(k, _)| k);
                if let Some(w) = worst {
                    if migrants[i].fit > islands[dst_i].pop[w].fit { islands[dst_i].pop[w] = migrants[i].clone(); }
                }
            }
        }
        let sigma = 0.10 * (1.0 - gen as f64 / (cfg.gens.max(1) as f64)) + 0.02;
        for isl in islands.iter_mut() {
            let (rank, crowd) = rank_crowd(&isl.pop);
            let mut kids = Vec::with_capacity(isl.pop.len());
            while kids.len() < isl.pop.len() {
                let g = if isl.rng.f64() < 0.1 { Genotype::random(&mut isl.rng) }
                else {
                    let ia = tournament(&isl.pop, &rank, &crowd, &mut isl.rng);
                    let ib = tournament(&isl.pop, &rank, &crowd, &mut isl.rng);
                    isl.pop[ia].g.crossover(&isl.pop[ib].g, &mut isl.rng).mutate(&mut isl.rng, sigma)
                };
                let s = isl.rng.next_u64();
                kids.push(evaluate_one(g, s, cfg.mc_samples, cfg.threads, &mut q));
            }
            archive.extend(kids.iter().cloned());
            let mut both = std::mem::take(&mut isl.pop);
            both.extend(kids);
            let keep = pop_n.min(both.len()).max(2);
            isl.pop = truncate(both, keep);
        }
        if let Some(path) = &cfg.checkpoint { save_ckpt(path, gen + 1, cfg, &islands, &archive); }
    }
    let best = islands.iter().flat_map(|isl| isl.pop.iter()).max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).unwrap().clone();
    (best, pareto(&archive))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bare(fit: f64, mass: f64, cut: f64, floors: bool) -> Indiv {
        let g = Genotype::random(&mut Rng(1));
        Indiv { g, fit, mean: fit, strength_n: fit.max(0.0) * mass, mass_g: mass, floors_ok: floors, cut_p05: cut, sharp_p05: 0.5 }
    }

    #[test] fn feasible_dominates_infeasible_and_front_keeps_extremes() {
        let good = bare(10.0, 30.0, 0.2, true);
        let heavy = bare(9.0, 40.0, 0.4, true);
        let bad = bare(-3.0, 20.0, 0.9, false);
        assert!(dominates(&good, &bad));
        assert!(!dominates(&bad, &good));
        assert!(!dominates(&good, &heavy) && !dominates(&heavy, &good));
        let pop = vec![good, heavy.clone(), bad, bare(8.0, 25.0, 0.1, true), bare(7.0, 50.0, 0.0, true)];
        let kept = truncate(pop, 2);
        assert_eq!(kept.len(), 2);
        assert!(kept.iter().any(|i| (i.fit - 10.0).abs() < 1e-9), "unique primary best is an objective extreme");
    }

    #[test] fn checkpoint_roundtrip_and_short_search() {
        let path = "out/ckpt_evolve_test.txt";
        let _ = std::fs::create_dir_all("out");
        let mut cfg = Config::new(4, 2, 16, 2, 12345);
        cfg.islands = 2;
        cfg.migrate_every = 1;
        cfg.checkpoint = Some(path.into());
        let (best, front) = run(&cfg, |_| {});
        assert!(best.fit.is_finite());
        assert!(front.iter().all(|i| i.feasible()));
        if best.feasible() {
            let (p, rt, _) = nominal(&best.g);
            assert!(rt.is_ok(), "{rt:?} teeth {}/{}", p.inner_teeth, p.outer_teeth);
        }
        let loaded = load_ckpt(path).unwrap();
        assert_eq!(loaded.next_gen, 2);
        assert_eq!(loaded.islands.len(), 2);
        assert!(!loaded.islands[0].pop.is_empty());
        cfg.gens = 3;
        cfg.resume = true;
        let (best2, _) = run(&cfg, |_| {});
        assert!(best2.fit.is_finite());
        let _ = std::fs::remove_file(path);
    }
}
