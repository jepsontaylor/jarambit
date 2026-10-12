//! NSGA-II with optional island migration.
//! PRIMARY fitness stays MC-p05 strength-per-gram (N/g) subject to the firm floors
//! (hiker 180 N, hunter 260 N, ring pull 1500 N).
//! Secondary objectives (mass, blade-first cut margin) shape the front; the logged
//! Pareto view remains nominal strength vs mass. Red-team gate on every candidate
//! and every MC sample. Checkpoint is one text file, overwritten each generation.
//!
//! `Config.fem` (CLI: `JARAMBIT_FEM=1`) sets that nominal strength from one
//! Kirchhoff plate solve at 20 °C. The sample loop stays the beam surrogate and
//! supplies the knockdown. A missed plate mesh is infeasible. Floors are unchanged.
use jarambit_genotype::{Genotype, Rng, TiGrade};
use jarambit_monte_carlo::{cut_margin, media_sample, run_cols};
use jarambit_phenotype::Phenotype;
use jarambit_physics::{calib, evaluate, fine, floors, material, plate_capacities, primary_fitness, Eval};
use jarambit_physics::fine::FineCaps;

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
    /// Nominal plate strength, with the surrogate Monte Carlo knockdown.
    /// Do not resume a surrogate checkpoint with this set: the stored scores
    /// would mix the two models.
    pub fem: bool,
    /// CALIBRATED search (2026-10-11): detailed plate (`physics::fine`, converged mesh family)
    /// solved per candidate at SEARCH_AREA, divided by the measured mesh bias, times the
    /// surrogate MC p05/nominal knockdown; floors must also hold at 100 C nominal. Overrides `fem`.
    pub fine: bool,
    /// Legal starting genomes. Each island's initial population gets these plus mutants of them
    /// (up to half the population); the rest stay random. Not promoted: they are re-scored.
    pub seeds: Vec<Genotype>,
    /// PR-0.29.2: resume from a checkpoint written under a DIFFERENT manifest (explicit fork; the new manifest
    /// records the parent manifest sha). Without it a manifest mismatch refuses to resume.
    pub fork: bool,
    /// Stop after this many completed generations (checkpoint written), as if interrupted. Test / ops hook.
    pub stop_after: Option<usize>,
}

impl Config {
    pub fn new(pop: usize, gens: usize, mc_samples: usize, threads: usize, seed: u64) -> Self {
        Self { pop, gens, mc_samples, threads, seed, islands: 1, migrate_every: 5, checkpoint: None, resume: false, fem: false, fine: false, seeds: Vec::new(), fork: false, stop_after: None }
    }
}

/// Nominal (20 C, no tolerance) evaluation incl. red-team verdict.
pub fn nominal(g: &Genotype) -> (Phenotype, Result<(), Vec<jarambit_redteam::Reject>>, Eval) {
    let p = Phenotype::from_genotype(g);
    let rt = jarambit_redteam::check(g, &p);
    let e = evaluate(&p, g.edge_angle_deg, (g.serr_inner.depth, g.serr_outer.depth), material(g.material), 20.0);
    (p, rt, e)
}

/// One MC sample's columns: surrogate primary fitness, cut margin, sharpness,
/// surrogate lateral strength (N), surrogate ring pull (N).
fn sample_metrics(h: &Genotype, r: &mut Rng) -> [f64; 5] {
    let mut p = Phenotype::from_genotype(h);
    if jarambit_redteam::check(h, &p).is_err() { return [-1e3, -1.0, 0.0, 0.0, 0.0]; }
    p.thickness = jarambit_monte_carlo::thickness_sample(h, r);
    let env = jarambit_monte_carlo::env_sample(r);
    let e = evaluate(&p, h.edge_angle_deg, (h.serr_inner.depth, h.serr_outer.depth), material(h.material), env.temp_c);
    let margin = cut_margin(e.blade_lat_n, e.inplane_n, e.sharpness, e.serration_score, media_sample(r));
    // column 0 (surrogate-only score) uses the calibrated surrogate so it cannot overstate the
    // detailed plate (physics::calib); columns 3-4 feed ratios, where the factor cancels.
    [primary_fitness(&calib::calibrated_surrogate(&e)), margin, e.sharpness, e.strength_n, e.ring_pull_n]
}

fn knocked(level: f64, nom: f64, p05: f64) -> f64 { level * (p05 / nom.max(1e-9)) }

/// Nominal plate capacities must clear the firm floors before a candidate is feasible.
fn plate_nominal_floors(plate_s: f64, plate_ring: f64) -> bool {
    plate_s >= floors::HIKER_LATERAL_N && plate_s >= floors::HUNTER_LATERAL_N && plate_ring >= floors::RING_PULL_N
}

/// Robust plate estimate: plate level × (surrogate p05 / surrogate nominal).
/// The ratio carries tolerance and temperature. It is not a scale factor that
/// forces the plate to agree with the beam.
fn robust_plate_eval(e: &Eval, plate_s: f64, plate_ring: f64, s_p05: f64, r_p05: f64) -> Eval {
    let mut pe = e.clone();
    let s_hat = knocked(plate_s, e.strength_n, s_p05);
    let r_hat = knocked(plate_ring, e.ring_pull_n, r_p05);
    pe.strength_n = s_hat;
    pe.ring_pull_n = r_hat;
    pe.hiker_ok = s_hat >= floors::HIKER_LATERAL_N;
    pe.hunter_ok = s_hat >= floors::HUNTER_LATERAL_N;
    pe.ring_ok = r_hat >= floors::RING_PULL_N;
    pe.strength_per_gram = s_hat / pe.mass_g.max(1e-6);
    pe
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
    /// PR-0.29.3: true for the terminal snapshot (final populations after the last generation).
    pub terminal: bool,
}

/// Mean primary fitness over `feasible()` individuals only; None if there are none (PR-0.29.3; the CLI used a
/// `fit > -100` filter, which counted graded infeasible designs).
pub fn feasible_mean(pop: &[Indiv]) -> Option<f64> {
    let v: Vec<f64> = pop.iter().filter(|i| i.feasible()).map(|i| i.fit).collect();
    if v.is_empty() { None } else { Some(v.iter().sum::<f64>() / v.len() as f64) }
}

/// Stable 16-hex-digit identity of a genotype (SHA-256 of its exact f64 bits + material), for quarantine / logs.
pub fn genotype_hash(g: &Genotype) -> String { jarambit_evidence::hex(&sha2_256(genes_hex(g).as_bytes())[..8]) }

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

fn evaluate_one(g: Genotype, sample_seed: u64, mc: usize, threads: usize, q: &mut Vec<(Genotype, String)>, fem: bool) -> Indiv {
    let (p, rt, e) = nominal(&g);
    let crazy = !e.mass_g.is_finite() || !(5.0..=250.0).contains(&e.mass_g);
    if let Err(v) = &rt { q.push((g.clone(), format!("{v:?}"))); }
    else if crazy { q.push((g.clone(), format!("crazy phenotype mass {:.2} g", e.mass_g))); }
    let cols = run_cols(&g, mc, threads, sample_seed, sample_metrics);
    if !fem {
        let fit = if rt.is_err() || crazy { -1e3 } else { cols[0].p05 };
        return Indiv { g, fit, mean: cols[0].mean, strength_n: e.strength_n, mass_g: e.mass_g, floors_ok: e.floors_ok() && rt.is_ok() && !crazy, cut_p05: cols[1].p05, sharp_p05: cols[2].p05 };
    }
    if rt.is_err() || crazy {
        return Indiv { g, fit: -1e3, mean: cols[0].mean, strength_n: e.strength_n, mass_g: e.mass_g, floors_ok: false, cut_p05: cols[1].p05, sharp_p05: cols[2].p05 };
    }
    let Some(c) = plate_capacities(&p, material(g.material), 20.0, (g.serr_inner.depth, g.serr_outer.depth)) else {
        q.push((g.clone(), "plate mesh miss".into()));
        return Indiv { g, fit: -1e3, mean: cols[0].mean, strength_n: 0.0, mass_g: e.mass_g, floors_ok: false, cut_p05: cols[1].p05, sharp_p05: cols[2].p05 };
    };
    let ps = c.blade_lat_n.min(c.grip_lat_n);
    let pe = robust_plate_eval(&e, ps, c.ring_pull_n, cols[3].p05, cols[4].p05);
    Indiv {
        g, fit: primary_fitness(&pe), mean: cols[0].mean, strength_n: ps, mass_g: e.mass_g,
        floors_ok: plate_nominal_floors(ps, c.ring_pull_n), cut_p05: cols[1].p05, sharp_p05: cols[2].p05,
    }
}

/// Calibrated robust capacities from a detailed-plate solve: (lateral, ring) in N, each the min of
/// the MC-knocked 20 C level and the 100 C nominal level, after dividing by the mesh bias.
pub fn calibrated_levels(c: &FineCaps, e: &Eval, s_p05: f64, r_p05: f64, m: &jarambit_physics::Material) -> (f64, f64) {
    let lat20 = c.lateral_n / calib::MESH_BIAS_LAT_MAX;
    let ring20 = c.ring_pull_n / calib::MESH_BIAS_RING_MAX;
    let hot = m.yield_at(100.0) / m.yield_at(20.0);
    let lat = knocked(lat20, e.strength_n, s_p05).min(lat20 * hot);
    let ring = knocked(ring20, e.ring_pull_n, r_p05).min(ring20 * hot);
    (lat, ring)
}

/// Firm floors on calibrated levels: lateral >= 180 AND >= 260 N, ring >= 1500 N.
pub fn calibrated_floors_ok(lat: f64, ring: f64) -> bool {
    lat >= floors::HIKER_LATERAL_N && lat >= floors::HUNTER_LATERAL_N && ring >= floors::RING_PULL_N
}

fn evaluate_fine(g: Genotype, sample_seed: u64, mc: usize, threads: usize, q: &mut Vec<(Genotype, String)>, caps: Option<FineCaps>) -> Indiv {
    let (p, rt, e) = nominal(&g);
    let crazy = !e.mass_g.is_finite() || !(5.0..=250.0).contains(&e.mass_g);
    if let Err(v) = &rt { q.push((g.clone(), format!("{v:?}"))); }
    else if crazy { q.push((g.clone(), format!("crazy phenotype mass {:.2} g", e.mass_g))); }
    let cols = run_cols(&g, mc, threads, sample_seed, sample_metrics);
    let bad = |g: Genotype, fit: f64| Indiv { g, fit, mean: cols[0].mean, strength_n: 0.0, mass_g: e.mass_g, floors_ok: false, cut_p05: cols[1].p05, sharp_p05: cols[2].p05 };
    if let Err(v) = &rt {
        // short-blade-only rejects are shaped by the shortfall so the search can climb into the
        // legal (>= 3.375 in on all three) region; they stay infeasible and are never winners.
        let fit = if jarambit_redteam::only_blade_short(v) { -50.0 - jarambit_redteam::blade_shortfall_mm(&p) } else { -1e3 };
        return bad(g, fit);
    }
    if crazy { return bad(g, -1e3); }
    let Some(c) = caps else { q.push((g.clone(), "detailed plate mesh miss".into())); return bad(g, -1e3); };
    let (lat, ring) = calibrated_levels(&c, &e, cols[3].p05, cols[4].p05, material(g.material));
    let ok = calibrated_floors_ok(lat, ring);
    let fit = if ok { lat / e.mass_g.max(1e-6) } else {
        // graded: nominal-hot deficit + robust deficit + share of MC draws the red team rejects
        let m = material(g.material);
        let hot = m.yield_at(100.0) / m.yield_at(20.0);
        let (lh, rh) = (c.lateral_n / calib::MESH_BIAS_LAT_MAX * hot, c.ring_pull_n / calib::MESH_BIAS_RING_MAX * hot);
        let d = |l: f64, r: f64| (1.0 - l / floors::HUNTER_LATERAL_N).max(0.0) + (1.0 - r / floors::RING_PULL_N).max(0.0);
        let rej = (-cols[0].mean / 1e3).clamp(0.0, 1.0);
        -1.0 - 5.0 * d(lh, rh) - 5.0 * d(lat, ring) - 10.0 * rej
    };
    Indiv { g, fit, mean: cols[0].mean, strength_n: lat, mass_g: e.mass_g, floors_ok: ok, cut_p05: cols[1].p05, sharp_p05: cols[2].p05 }
}

/// Evaluate a batch. In calibrated (`fine`) mode the detailed-plate solves run in parallel first
/// (`threads` workers, red-team-clean candidates only), then the MC knockdown per candidate.
fn eval_batch(items: Vec<(Genotype, u64)>, cfg: &Config, q: &mut Vec<(Genotype, String)>) -> Vec<Indiv> {
    if !cfg.fine {
        return items.into_iter().map(|(g, s)| evaluate_one(g, s, cfg.mc_samples, cfg.threads, q, cfg.fem)).collect();
    }
    let n = items.len();
    let next = std::sync::atomic::AtomicUsize::new(0);
    let caps: Vec<std::sync::Mutex<Option<FineCaps>>> = (0..n).map(|_| std::sync::Mutex::new(None)).collect();
    std::thread::scope(|s| {
        for _ in 0..cfg.threads.max(1).min(n.max(1)) {
            s.spawn(|| loop {
                let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                if i >= n { break; }
                let g = &items[i].0;
                let p = Phenotype::from_genotype(g);
                if jarambit_redteam::check(g, &p).is_err() { continue; }
                let c = fine::capacities(&p, material(g.material), 20.0, (g.serr_inner.depth, g.serr_outer.depth), fine::SEARCH_AREA);
                *caps[i].lock().unwrap() = c;
            });
        }
    });
    items.into_iter().zip(caps).map(|((g, s), c)| evaluate_fine(g, s, cfg.mc_samples, cfg.threads, q, c.into_inner().unwrap())).collect()
}

fn parse_genes(csv: &str) -> Result<Genotype, String> {
    let cols: Vec<&str> = csv.split(',').collect();
    // 22 = current (blade_angle_deg at index 20); 21 = legacy pre-knob checkpoint (un-raked blade).
    // 25 = current (neck genes 21-23); 22 = pre-neck (blade angle at 20); 21 = pre-knob.
    let n = match cols.len() { 21 => 20, 22 => 21, 25 => 24, k => return Err(format!("gene columns {k}")) };
    let mut v = vec![0.0; n];
    for i in 0..n { v[i] = cols[i].parse().map_err(|_| format!("gene {i}"))?; }
    let mat = match cols[n] {
        "Ti-3Al-2.5V" => TiGrade::Ti3Al2_5V,
        "Ti-6Al-4V" => TiGrade::Ti6Al4V,
        other => return Err(format!("material {other}")),
    };
    Ok(Genotype::from_vec(&v, mat))
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

// ---- PR-0.29.2: lossless checkpoint (every f64 as its IEEE-754 bits in hex) bound to the run manifest ----

/// The run manifest of the legacy NSGA-II search. Every field that changes the trajectory is in it; `threads`
/// is not (results are thread-count stable). Resume refuses a checkpoint whose manifest sha differs.
pub fn manifest(cfg: &Config) -> jarambit_evidence::RunManifest {
    let seeds: Vec<String> = cfg.seeds.iter().map(genes_hex).collect();
    use jarambit_evidence::RunManifest;
    RunManifest::new("evolve", cfg.seed, "legacy-floors-180-260-1500")
        .param("pop", cfg.pop).param("gens", cfg.gens).param("mc_samples", cfg.mc_samples).param("islands", cfg.islands.max(1))
        .param("migrate_every", cfg.migrate_every).param("fem", cfg.fem).param("fine", cfg.fine)
        .param("seeds_sha256", jarambit_evidence::hex(&sha2_256(seeds.join("\n").as_bytes())))
        .param("floors_n", format!("{}/{}/{}", floors::HIKER_LATERAL_N, floors::HUNTER_LATERAL_N, floors::RING_PULL_N))
        .param("calib_mesh_bias", format!("{}/{}", calib::MESH_BIAS_LAT_MAX, calib::MESH_BIAS_RING_MAX))
        .param("search_area", fine::SEARCH_AREA)
}
fn sha2_256(b: &[u8]) -> Vec<u8> { use sha2::Digest; sha2::Sha256::digest(b).to_vec() }

fn hx(x: f64) -> String { format!("{:016x}", x.to_bits()) }
fn unhx(s: &str) -> Result<f64, String> { u64::from_str_radix(s, 16).map(f64::from_bits).map_err(|_| format!("bad f64 bits {s:?}")) }
fn genes_hex(g: &Genotype) -> String { let mut v: Vec<String> = g.to_vec().iter().map(|x| hx(*x)).collect(); v.push(g.material.name().into()); v.join(",") }
fn parse_genes_hex(s: &str) -> Result<Genotype, String> {
    let cols: Vec<&str> = s.split(',').collect(); let n = cols.len().checked_sub(1).ok_or("genes")?;
    let v: Vec<f64> = cols[..n].iter().map(|c| unhx(c)).collect::<Result<_, _>>()?;
    let mat = match cols[n] { "Ti-3Al-2.5V" => TiGrade::Ti3Al2_5V, "Ti-6Al-4V" => TiGrade::Ti6Al4V, o => return Err(format!("material {o}")) };
    let g = Genotype::from_vec(&v, mat);
    if g.to_vec().iter().map(|x| x.to_bits()).ne(v.iter().map(|x| x.to_bits())) { return Err("genome does not round-trip bit-exactly".into()); }
    Ok(g)
}
fn indiv_hex(i: &Indiv) -> String {
    format!("{} {} {} {} {} {} {} {}", hx(i.fit), hx(i.mean), hx(i.strength_n), hx(i.mass_g), if i.floors_ok { 1 } else { 0 }, hx(i.cut_p05), hx(i.sharp_p05), genes_hex(&i.g))
}
fn parse_indiv_hex(line: &str) -> Result<Indiv, String> {
    let f: Vec<&str> = line.splitn(8, ' ').collect(); if f.len() != 8 { return Err(format!("indiv fields {}", f.len())); }
    Ok(Indiv { fit: unhx(f[0])?, mean: unhx(f[1])?, strength_n: unhx(f[2])?, mass_g: unhx(f[3])?, floors_ok: match f[4] { "1" => true, "0" => false, o => return Err(format!("floors {o}")) },
        cut_p05: unhx(f[5])?, sharp_p05: unhx(f[6])?, g: parse_genes_hex(f[7])? })
}

fn save_ckpt(path: &str, next_gen: usize, man: &jarambit_evidence::RunManifest, islands: &[Island], archive: &[Indiv]) {
    let mut s = String::new();
    s.push_str("jarambit-ckpt 2\n");
    s.push_str(&format!("manifest_sha256 {}\n", man.sha256()));
    s.push_str(&format!("manifest {}\n", man.canonical_json()));
    s.push_str(&format!("next_gen {next_gen}\n"));
    s.push_str(&format!("islands {}\n", islands.len()));
    for (i, isl) in islands.iter().enumerate() {
        s.push_str(&format!("island {i} rng {:016x} n {}\n", isl.rng.0, isl.pop.len()));
        for ind in &isl.pop { s.push_str(&indiv_hex(ind)); s.push('\n'); }
    }
    s.push_str(&format!("archive {}\n", archive.len()));
    for ind in archive { s.push_str(&indiv_hex(ind)); s.push('\n'); }
    s.push_str("end\n");
    if let Some(dir) = std::path::Path::new(path).parent() { let _ = std::fs::create_dir_all(dir); }
    let tmp = format!("{path}.tmp");
    { use std::io::Write; let mut f = std::fs::File::create(&tmp).unwrap_or_else(|e| panic!("checkpoint write {tmp}: {e}"));
      f.write_all(s.as_bytes()).and_then(|_| f.sync_all()).unwrap_or_else(|e| panic!("checkpoint write {tmp}: {e}")); }
    std::fs::rename(&tmp, path).unwrap_or_else(|e| panic!("checkpoint rename {path}: {e}"));
}

struct Loaded { next_gen: usize, manifest_sha: String, manifest_json: String, islands: Vec<Island>, archive: Vec<Indiv> }

fn kv<'a>(l: Option<&'a str>, key: &str) -> Result<&'a str, String> {
    let l = l.ok_or_else(|| format!("missing {key}"))?; l.strip_prefix(key).and_then(|r| r.strip_prefix(' ')).ok_or_else(|| format!("expected {key}, got {l:?}"))
}

fn load_ckpt(path: &str) -> Result<Loaded, String> {
    let text = std::fs::read_to_string(path).map_err(|e| format!("{path}: {e}"))?;
    let mut lines = text.lines();
    match lines.next() { Some("jarambit-ckpt 2") => {}, Some("jarambit-ckpt 1") => return Err("checkpoint format 1 is lossy (rounded decimals) and has no manifest; resume refused (use --fork to start from its best genomes via --seed-ckpt)".into()), m => return Err(format!("bad magic {m:?}")) }
    let manifest_sha = kv(lines.next(), "manifest_sha256")?.to_string();
    let manifest_json = kv(lines.next(), "manifest")?.to_string();
    let next_gen: usize = kv(lines.next(), "next_gen")?.parse().map_err(|_| "next_gen")?;
    let nisl: usize = kv(lines.next(), "islands")?.parse().map_err(|_| "islands")?;
    let mut islands = Vec::with_capacity(nisl);
    for i in 0..nisl {
        let hdr = lines.next().ok_or("island header")?;
        let p: Vec<&str> = hdr.split(' ').collect();
        if p.len() != 6 || p[0] != "island" || p[1] != i.to_string() || p[2] != "rng" || p[4] != "n" { return Err(format!("island header {hdr}")); }
        let rng = Rng(u64::from_str_radix(p[3], 16).map_err(|_| "rng")?);
        let n: usize = p[5].parse().map_err(|_| "pop n")?;
        let mut pop = Vec::with_capacity(n);
        for _ in 0..n { pop.push(parse_indiv_hex(lines.next().ok_or("truncated population")?)?); }
        islands.push(Island { rng, pop });
    }
    let an: usize = kv(lines.next(), "archive")?.parse().map_err(|_| "archive n")?;
    let mut archive = Vec::with_capacity(an);
    for _ in 0..an { archive.push(parse_indiv_hex(lines.next().ok_or("truncated archive")?)?); }
    if lines.next() != Some("end") { return Err("checkpoint not terminated (torn write?)".into()); }
    Ok(Loaded { next_gen, manifest_sha, manifest_json, islands, archive })
}

/// Highest-fitness genotype in the saved island populations (format 2, or the legacy lossy format 1).
pub fn checkpoint_best(path: &str) -> Result<Genotype, String> {
    let pop: Vec<Indiv> = match load_ckpt(path) {
        Ok(l) => l.islands.into_iter().flat_map(|i| i.pop).collect(),
        Err(e) if e.contains("format 1") => load_ckpt_v1_pop(path)?,
        Err(e) => return Err(e),
    };
    pop.iter().max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).map(|i| i.g.clone()).ok_or_else(|| "empty checkpoint".into())
}

/// Legacy format-1 reader: populations only (for seeding / best-genome extraction, never for resume).
fn load_ckpt_v1_pop(path: &str) -> Result<Vec<Indiv>, String> {
    let text = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut lines = text.lines().filter(|l| !l.is_empty()).skip(1);
    let _next = lines.next(); let nisl: usize = lines.next().ok_or("islands")?.split_whitespace().nth(1).ok_or("islands")?.parse().map_err(|_| "islands")?;
    let _seed = lines.next(); let _mig = lines.next();
    let mut out = Vec::new();
    for _ in 0..nisl { let hdr = lines.next().ok_or("island header")?; let n: usize = hdr.split_whitespace().nth(5).ok_or("n")?.parse().map_err(|_| "n")?;
        for _ in 0..n { out.push(parse_indiv(lines.next().ok_or("truncated population")?)?); } }
    Ok(out)
}

/// Run the search; panics on a refused resume (see [`try_run`]).
pub fn run(cfg: &Config, log: impl FnMut(&GenStats)) -> (Indiv, Vec<Indiv>) { try_run(cfg, log).unwrap_or_else(|e| panic!("{e}")) }

/// Run the search. Resume (PR-0.29.2) is lossless and manifest-bound: `resume` with no checkpoint, a torn or
/// legacy checkpoint, or a manifest mismatch (without `fork`) is an error, never a silent fresh start.
pub fn try_run(cfg: &Config, mut log: impl FnMut(&GenStats)) -> Result<(Indiv, Vec<Indiv>), String> {
    let n_islands = cfg.islands.max(1);
    let pop_n = cfg.pop.max(2);
    let mut man = manifest(cfg);
    let mut q = Vec::new();
    let mut archive: Vec<Indiv> = Vec::new();
    let mut start = 0usize;
    let mut islands: Vec<Island> = if cfg.resume || cfg.fork {
        let path = cfg.checkpoint.as_deref().ok_or("resume requested but no checkpoint path configured")?;
        if !std::path::Path::new(path).exists() { return Err(format!("resume requested but checkpoint {path} does not exist")); }
        let loaded = load_ckpt(path).map_err(|e| format!("resume {path}: {e}"))?;
        if loaded.manifest_sha != man.sha256() {
            if !cfg.fork { return Err(format!("resume {path}: manifest mismatch (checkpoint {} != run {}); refusing. Checkpoint manifest: {}; this run: {}. Use --fork to branch deliberately.",
                &loaded.manifest_sha[..12], &man.sha256()[..12], loaded.manifest_json, man.canonical_json())); }
            man = man.param("forked_from_manifest_sha256", loaded.manifest_sha.clone()).param("forked_at_gen", loaded.next_gen);
        }
        if loaded.islands.len() != n_islands { return Err(format!("checkpoint has {} islands, config asks for {n_islands}", loaded.islands.len())); }
        start = loaded.next_gen;
        archive = loaded.archive;
        loaded.islands
    } else { Vec::new() };
    if islands.is_empty() {
        islands = (0..n_islands).map(|i| {
            let mut rng = Rng(cfg.seed.wrapping_add((i as u64 + 1).wrapping_mul(0x9E37_79B9_7F4A_7C15)));
            let n_seed = if cfg.seeds.is_empty() { 0 } else { pop_n / 2 };
            let items: Vec<(Genotype, u64)> = (0..pop_n).map(|k| {
                let g = if k < n_seed {
                    let base = &cfg.seeds[k % cfg.seeds.len()];
                    if k < cfg.seeds.len() { let mut b = base.clone(); b.clamp(); b } else { base.mutate(&mut rng, 0.06) }
                } else { Genotype::random(&mut rng) };
                let s = rng.next_u64();
                (g, s)
            }).collect();
            let pop = eval_batch(items, cfg, &mut q);
            Island { rng, pop }
        }).collect();
        archive.extend(islands.iter().flat_map(|isl| isl.pop.iter().cloned()));
    }
    let mut stopped = false;
    for gen in start..cfg.gens {
        let mut combined: Vec<Indiv> = islands.iter().flat_map(|isl| isl.pop.iter().cloned()).collect();
        combined.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap_or(std::cmp::Ordering::Equal));
        let rejected = q.len();
        log(&GenStats { gen, pop: &combined, diversity: diversity(&combined), rejected, quarantine: std::mem::take(&mut q), terminal: false });
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
            let mut items: Vec<(Genotype, u64)> = Vec::with_capacity(isl.pop.len());
            while items.len() < isl.pop.len() {
                let g = if isl.rng.f64() < 0.1 { Genotype::random(&mut isl.rng) }
                else {
                    let ia = tournament(&isl.pop, &rank, &crowd, &mut isl.rng);
                    let ib = tournament(&isl.pop, &rank, &crowd, &mut isl.rng);
                    isl.pop[ia].g.crossover(&isl.pop[ib].g, &mut isl.rng).mutate(&mut isl.rng, sigma)
                };
                let s = isl.rng.next_u64();
                items.push((g, s));
            }
            let kids = eval_batch(items, cfg, &mut q);
            archive.extend(kids.iter().cloned());
            let mut both = std::mem::take(&mut isl.pop);
            both.extend(kids);
            let keep = pop_n.min(both.len()).max(2);
            isl.pop = truncate(both, keep);
        }
        if let Some(path) = &cfg.checkpoint { save_ckpt(path, gen + 1, &man, &islands, &archive); }
        if cfg.stop_after == Some(gen + 1) { stopped = true; break; }
    }
    // terminal snapshot: the final populations (the returned best is always in it); not emitted when interrupted
    if !stopped {
    let mut combined: Vec<Indiv> = islands.iter().flat_map(|isl| isl.pop.iter().cloned()).collect();
    combined.sort_by(|a, b| b.fit.partial_cmp(&a.fit).unwrap_or(std::cmp::Ordering::Equal));
    log(&GenStats { gen: cfg.gens, pop: &combined, diversity: diversity(&combined), rejected: q.len(), quarantine: std::mem::take(&mut q), terminal: true });
    }
    let best = islands.iter().flat_map(|isl| isl.pop.iter()).max_by(|a, b| a.fit.partial_cmp(&b.fit).unwrap_or(std::cmp::Ordering::Equal)).unwrap().clone();
    Ok((best, pareto(&archive)))
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
        let best_g = checkpoint_best(path).unwrap();
        assert_eq!(best_g.to_vec().len(), 24);
        assert_eq!(loaded.next_gen, 2);
        assert_eq!(loaded.islands.len(), 2);
        assert!(!loaded.islands[0].pop.is_empty());
        cfg.gens = 3;
        cfg.resume = true;
        assert!(try_run(&cfg, |_| {}).unwrap_err().contains("manifest mismatch"), "changing gens must refuse a plain resume");
        cfg.fork = true;
        let (best2, _) = run(&cfg, |_| {});
        assert!(best2.fit.is_finite());
        let _ = std::fs::remove_file(path);
    }

    fn eval_at(strength: f64, ring: f64, mass: f64) -> Eval {
        Eval {
            mass_g: mass, strength_n: strength, blade_lat_n: strength, grip_lat_n: strength,
            ring_pull_n: ring, inplane_n: strength, strength_per_gram: strength / mass,
            hiker_ok: true, hunter_ok: true, ring_ok: true, safety_factor: 1.0,
            sharpness: 0.5, serration_score: 0.5, ergonomics: 0.5,
        }
    }

    #[test]
    fn fem_knockdown_keeps_firm_floors() {
        let e = eval_at(800.0, 4000.0, 40.0);
        let pe = robust_plate_eval(&e, 400.0, 2000.0, 720.0, 3600.0);
        assert!(pe.floors_ok());
        let fit = primary_fitness(&pe);
        assert!((fit - 9.0).abs() < 1e-9, "{fit}");
        let pe2 = robust_plate_eval(&e, 400.0, 2000.0, 400.0, 2000.0);
        assert!(!pe2.floors_ok());
        assert!(primary_fitness(&pe2) < 0.0);
        assert!(plate_nominal_floors(260.0, 1500.0));
        assert!(!plate_nominal_floors(180.0, 1500.0));
        assert!(!plate_nominal_floors(260.0, 1499.0));
        assert!(!plate_nominal_floors(259.0, 1500.0));
        assert_eq!(floors::HIKER_LATERAL_N, 180.0);
        assert_eq!(floors::HUNTER_LATERAL_N, 260.0);
        assert_eq!(floors::RING_PULL_N, 1500.0);
    }

    #[test]
    fn fem_candidate_stores_plate_strength() {
        let g = Genotype::random(&mut Rng(11));
        let mut q = Vec::new();
        let ind = evaluate_one(g.clone(), 3, 8, 2, &mut q, true);
        let p = Phenotype::from_genotype(&g);
        if jarambit_redteam::check(&g, &p).is_err() {
            // Blade-length floor (2026-10-11): red-team rejects never reach the plate and score -1e3.
            // Plate-path coverage returns once the phenotype can meet all-three >= 86.225 mm.
            assert_eq!(ind.fit, -1.0e3);
            assert!(!ind.floors_ok);
            assert!(q.iter().any(|(_, w)| w.contains("BladeTooShort")), "{q:?}");
            return;
        }
        match plate_capacities(&p, material(g.material), 20.0, (g.serr_inner.depth, g.serr_outer.depth)) {
            Some(c) => {
                let ps = c.blade_lat_n.min(c.grip_lat_n);
                assert!((ind.strength_n - ps).abs() < 1e-6, "{} vs {ps}", ind.strength_n);
                assert!(ind.fit.is_finite());
            }
            None => {
                assert_eq!(ind.fit, -1.0e3);
                assert!(q.iter().any(|(_, w)| w.contains("plate")));
            }
        }
    }
}
