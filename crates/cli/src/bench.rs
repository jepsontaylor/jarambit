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
            if std::env::var_os("JARAMBIT_BENCH_DUMP").is_some() { eprintln!("design {i} {chk:.17e}"); }
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

/// PR-0.31.3: T1 (search: `qd::evaluate`, search mesh + bias) vs T2 (certification: `fem::certify`) per load case on the
/// first `n` fixed_1k genomes at 0, stride, 2*stride, ... that evaluate in both tiers (illegal genomes have no T1 FEM), plus the RS-karambit-v2 human-max / fatigue / ring-bearing values. Writes a CSV.
pub fn calib_t1t2(genomes: &str, n: usize, stride: usize, threads: usize, area: f64, out: &str) -> bool {
    let gs: Vec<Genome> = crate::crescent::load_seeds(genomes, usize::MAX).into_iter().step_by(stride.max(1)).take(2 * n).collect();
    if gs.is_empty() { return false; }
    let th = threads.max(1); let next = std::sync::atomic::AtomicUsize::new(0);
    let mut rows: Vec<(usize, String)> = std::thread::scope(|s| {
        let hs: Vec<_> = (0..th).map(|_| s.spawn(|| { let mut v = Vec::new(); loop {
            let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed); if i >= gs.len() { break v; }
            let g = &gs[i]; let r = qd::evaluate(g, i, 0, area); let p = pheno::build(g);
            let (Some(t1), Some((t2, _))) = (r.fem.clone(), fem::certify(&p)) else { continue };
            let (bw, band) = fem::ring_bearing(&p);
            v.push((i, format!("{i},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.3},{:.3},{:.3}",
                p.mass_g, t1.lat_rob, t2.lat_rob, t1.ring_rob, t2.ring_rob, t1.twist_joint_nmm, t2.twist_joint_nmm, t1.pry20, t2.pry20,
                t2.hm_spine_n, t2.hm_twist_sf, t2.hm_tip_inplane_sf, t2.hm_spine_sf, t2.hm_ringback_sf, t2.fat_sf, t2.seq_ratio, bw, band, p.t)));
        } })).collect();
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect() });
    rows.sort_by_key(|r| r.0); rows.truncate(n);
    let mut s = String::from("idx,mass_g,t1_lat_rob,t2_lat_rob,t1_ring_rob,t2_ring_rob,t1_twist_joint,t2_twist_joint,t1_pry20,t2_pry20,t2_hm_spine_n,hm_twist_sf,hm_tip_inplane_sf,hm_spine_sf,hm_ringback_sf,fat_sf,seq_ratio,ring_bearing_w_mm,ring_band_mm,t_mm\n");
    for r in &rows { s += &r.1; s.push('\n'); }
    eprintln!("calib-t1t2: {} / {} designs with both tiers", rows.len(), gs.len());
    std::fs::write(out, s).is_ok()
}
