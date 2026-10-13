//! PR-0.31.1: frozen benchmark workload (bench/fixed_1k) and timing for the two FEM tiers.
//! T1 = search evaluation (`qd::evaluate`, plate FEM at the search mesh), T1c = certification (`fem::certify`).
//! Each design is timed on one thread; `threads` workers share the list, so per-core seconds = sum of per-design times / n.
use jarambit_crescent::{fem, genome::Genome, pheno, qd};
use jarambit_genotype::Rng;
use std::time::Instant;

/// Deterministic workload: `n` genomes = seeds (as given) then mutation chains from them (Rng(seed)).
pub fn make(seeds: &str, n: usize, seed: u64, out: &str) -> bool {
    let base = crate::crescent::load_seeds(seeds, 1000);
    if base.is_empty() { eprintln!("bench-make: no seeds in {seeds}"); return false; }
    let mut r = Rng(seed); let mut gs: Vec<Genome> = base.clone();
    while gs.len() < n { let p = &base[(r.f64() * base.len() as f64) as usize % base.len()]; let mut g = p.clone();
        for _ in 0..1 + (r.f64() * 3.0) as usize { g = g.mutate(&mut r, 0.08); } gs.push(g); }
    gs.truncate(n);
    let mut s = Genome::csv_header() + "\n"; for g in &gs { s += &g.csv_row(); s.push('\n'); }
    std::fs::create_dir_all(std::path::Path::new(out).parent().unwrap_or(std::path::Path::new("."))).ok();
    std::fs::write(out, s).is_ok()
}

/// Time `tier` ("search" | "cert") over the first `n` genomes with `threads` workers. Prints one JSON line.
pub fn run(genomes: &str, tier: &str, n: usize, threads: usize, area: f64) -> bool {
    let gs: Vec<Genome> = crate::crescent::load_seeds(genomes, usize::MAX).into_iter().take(n).collect();
    if gs.is_empty() { eprintln!("bench: no genomes in {genomes}"); return false; }
    let th = threads.max(1); let t0 = Instant::now();
    let res: Vec<(f64, f64, bool)> = std::thread::scope(|s| {
        let hs: Vec<_> = (0..th).map(|t| { let gs = &gs; s.spawn(move || gs.iter().enumerate().filter(|(i, _)| i % th == t).map(|(i, g)| {
            let t1 = Instant::now();
            let (chk, ok) = match tier {
                "cert" => { let p = pheno::build(g); match fem::certify(&p) { Some((f, _)) => (f.lat_rob + f.ring_rob, true), None => (0.0, false) } }
                _ => { let r = qd::evaluate(g, i, 0, area); match &r.fem { Some(f) => (f.lat_rob + f.ring_rob, true), None => (r.mass_g, false) } }
            };
            (t1.elapsed().as_secs_f64(), chk, ok) }).collect::<Vec<_>>()) }).collect();
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect() });
    let wall = t0.elapsed().as_secs_f64();
    let per: Vec<f64> = res.iter().map(|x| x.0).collect(); let fem_n = res.iter().filter(|x| x.2).count();
    let mut sorted = per.clone(); sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let checksum: f64 = res.iter().map(|x| x.1).sum();
    println!("{}", serde_json::json!({"tier": tier, "n": gs.len(), "threads": th, "fem_evaluated": fem_n, "wall_s": wall,
        "core_s_per_design_mean": per.iter().sum::<f64>() / per.len() as f64, "core_s_per_design_p50": sorted[sorted.len() / 2],
        "core_s_per_design_p95": sorted[(sorted.len() * 95 / 100).min(sorted.len() - 1)], "checksum": checksum}));
    true
}
