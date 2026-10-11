#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc; // per-thread heaps: glibc malloc spent ~75% in kernel at >8 MC threads

use jarambit_evolve::{nominal, run, Config, Indiv};
use jarambit_genotype::{limits, Genotype};
use jarambit_physics::{material, plate_capacities};
use std::fmt::Write;
mod fem_smoke;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if a.iter().any(|s| s == "fem-smoke") {
        let out = a.iter().position(|x| x == "--out").and_then(|i| a.get(i + 1)).cloned().unwrap_or_else(|| "out/fem_smoke".into());
        let mh1 = a.iter().position(|x| x == "--mh1").and_then(|i| a.get(i + 1)).cloned().unwrap_or_else(|| "out/mh1".into());
        let ok = fem_smoke::run(&out, &mh1);
        std::process::exit(if ok { 0 } else { 1 });
    }
    let arg = |k: &str, d: usize| a.iter().position(|x| x == k).and_then(|i| a.get(i + 1)).and_then(|v| v.parse().ok()).unwrap_or(d);
    let threads = arg("--threads", 16).min(jarambit_monte_carlo::max_threads()); // per-host cap: JARAMBIT_MAX_THREADS (default 48)
    let out = a.iter().position(|x| x == "--out").and_then(|i| a.get(i + 1)).cloned().unwrap_or("out".into());
    std::fs::create_dir_all(&out).unwrap();
    let mut cfg = Config::new(arg("--pop", 32), arg("--gens", 5), arg("--mc", 256), threads, arg("--seed", 42) as u64);
    cfg.islands = arg("--islands", 1).max(1);
    cfg.migrate_every = arg("--migrate", 5);
    cfg.checkpoint = Some(format!("{out}/checkpoint.txt"));
    cfg.resume = a.iter().any(|x| x == "--resume");
    cfg.fem = std::env::var("JARAMBIT_FEM").ok().as_deref() == Some("1");
    let hist_path = format!("{out}/history.csv");
    let q_path = format!("{out}/quarantine.csv");
    let mut rows = vec![];
    let mut csv = if cfg.resume && std::path::Path::new(&hist_path).exists() { std::fs::read_to_string(&hist_path).unwrap() }
        else { format!("gen,best_p05_spg,pop_mean_p05,diversity,rejected_in_gen,best_strength_n,best_mass_g,best_cut_p05,best_sharp_p05,{}\n", Genotype::CSV_HEADER) };
    let mut qcsv = if cfg.resume && std::path::Path::new(&q_path).exists() { std::fs::read_to_string(&q_path).unwrap() } else { String::from("gen,reasons\n") };
    let mut raw: Vec<(f64, f64)> = vec![];
    let (best, front) = run(&cfg, |s| {
        let b = &s.pop[0];
        let feas: Vec<f64> = s.pop.iter().map(|i| i.fit).filter(|f| *f > -1e2).collect();
        let mean = if feas.is_empty() { f64::NAN } else { feas.iter().sum::<f64>() / feas.len() as f64 };
        for i in s.pop { raw.push((s.gen as f64, i.fit.max(-20.0))); }
        println!("gen {:3}  best p05 spg {:.3} N/g  cut {:.3}  sharp {:.2}  S={:.0}N m={:.1}g  div={:.3}  rejected={}  islands={}  t={:.1}mm grip={:.1}", s.gen, b.fit, b.cut_p05, b.sharp_p05, b.strength_n, b.mass_g, s.diversity, s.rejected, cfg.islands, b.g.thickness, b.g.grip_len);
        rows.push((s.gen, b.fit, mean, s.diversity));
        let _ = writeln!(csv, "{},{:.5},{:.5},{:.4},{},{:.1},{:.2},{:.4},{:.4},{}", s.gen, b.fit, mean, s.diversity, s.rejected, b.strength_n, b.mass_g, b.cut_p05, b.sharp_p05, b.g.to_csv_row());
        for (_, why) in &s.quarantine { let _ = writeln!(qcsv, "{},\"{}\"", s.gen, why.replace('"', "'")); }
    });
    let (p, rt, e) = nominal(&best.g);
    let hf = jarambit_redteam::holder_forces(best.g.holder.holder_wall, best.g.holder.detent_depth);
    let plate = plate_capacities(&p, material(best.g.material), 20.0, (best.g.serr_inner.depth, best.g.serr_outer.depth));
    let plate_s = plate.as_ref().map(|c| c.blade_lat_n.min(c.grip_lat_n)).unwrap_or(f64::NAN);
    let logged_s = if cfg.fem { best.strength_n } else { e.strength_n };
    println!("final p05 spg {:.3} N/g  cut {:.3}  redteam={:?}  floors_ok={}  mass={:.1}g  S={:.0}N  plate={:.0}N  insert/draw {:.1}/{:.1} N  blade tip-heel/reach/arc = {:.1}/{:.1}/{:.1} mm (limit {:.3})",
        best.fit, best.cut_p05, rt, best.floors_ok, e.mass_g, logged_s, plate_s, hf.insertion_n, hf.draw_n, p.blade.tip_to_heel, p.blade.horizontal_reach, p.blade.sharpened_arc, limits::BLADE_LIMIT_MM);
    let w = |f: &str, s: String| std::fs::write(format!("{out}/{f}"), s).unwrap();
    w("history.csv", csv); w("quarantine.csv", qcsv);
    let mut pc = format!("strength_n,mass_g,spg,p05_spg,{}\n", Genotype::CSV_HEADER);
    let mut fr: Vec<&Indiv> = front.iter().collect(); fr.sort_by(|a, b| a.mass_g.partial_cmp(&b.mass_g).unwrap());
    for i in &fr { let _ = writeln!(pc, "{:.1},{:.2},{:.3},{:.3},{}", i.strength_n, i.mass_g, i.strength_n / i.mass_g, i.fit, i.g.to_csv_row()); }
    w("pareto.csv", pc);
    w("pareto.svg", jarambit_docs::svg_plot("Pareto: strength vs mass (feasible, red-team clean)", "mass (g)", "governing lateral strength (N)",
        &[("Pareto front", fr.iter().map(|i| (i.mass_g, i.strength_n)).collect(), true)]));
    w("diversity.svg", jarambit_docs::svg_plot("Population diversity", "generation", "mean pairwise normalised gene distance", &[("diversity", rows.iter().map(|r| (r.0 as f64, r.3)).collect(), false)]));
    w("fitness.svg", jarambit_docs::svg_plot("Fitness (p05 strength-per-gram, N/g)", "generation", "N/g", &[
        ("best", rows.iter().map(|r| (r.0 as f64, r.1)).collect(), false), ("pop mean (feasible)", rows.iter().map(|r| (r.0 as f64, r.2)).collect(), false), ("raw individuals", raw, true)]));
    w("best.stl", p.to_ascii_stl("switchback_best"));
    w("best.step", p.to_step_stub("switchback_best"));
    w("best.svg", p.to_svg());
    w("results.md", jarambit_docs::results_table(&rows));
    let mut rep = String::new();
    let score = if cfg.fem { format!("nominal plate {:.1} N; robust plate {:.3} N/g", best.strength_n, best.fit) }
        else { format!("surrogate {:.1} N; MC p05 {:.3} N/g", e.strength_n, best.fit) };
    let _ = writeln!(rep, "# Best design constraint report\n\nredteam: {rt:?}\nmaterial: {}\nthickness: {:.1} mm\nmass: {:.2} g\nbeam surrogate: {:.1} N (blade {:.1} / grip {:.1}); ring pull {:.0} N; {:.3} N/g\nsearch score: {score}\nfloors (surrogate nominal): hiker={} hunter={} ring={}\n",
        best.g.material.name(), p.thickness, e.mass_g, e.strength_n, e.blade_lat_n, e.grip_lat_n, e.ring_pull_n, e.strength_per_gram, e.hiker_ok, e.hunter_ok, e.ring_ok);
    let _ = writeln!(rep, "blade (limit {:.3} mm, guard {:.1}): tip_to_heel {:.2} | horizontal_reach {:.2} | sharpened_arc {:.2} (outer {:.2}, inner {:.2}) | sweep {:.1} deg",
        limits::BLADE_LIMIT_MM, limits::BLADE_GUARD_MM, p.blade.tip_to_heel, p.blade.horizontal_reach, p.blade.sharpened_arc, p.blade.sharpened_arc_outer, p.blade.sharpened_arc_inner, p.blade.sweep_deg);
    let model = if cfg.fem {
        "fitness model: nominal Kirchhoff plate at 20 C, times the beam-surrogate Monte Carlo knockdown (tolerance and temperature). The plate is not solved inside each sample. Floors 180/260/1500 N apply to that robust plate estimate. Logged strength is the nominal plate."
    } else {
        "fitness model: beam surrogate (Monte Carlo). Plate check is one Kirchhoff solve at 20 C, not inside the sample loop."
    };
    let _ = writeln!(rep, "grip (ring-neck to guard): {:.2} mm\nring ID: {:.2} mm\nholder: ricasso land {:.1} mm, shoulder {:.2} mm/side, detent {:.2} mm @ {:.0}% grip, friction {:.1} mm, drain {:.1} mm, shell {:.2} mm\nholder forces (proxy): insertion {:.1} N, draw {:.1} N\nMC p05 cut margin {:.3}  p05 sharpness {:.3}\nsearch: NSGA-II, {} island(s), {} samples/candidate\n{model}",
        p.grip_len, p.ring_id, best.g.holder.ricasso_len, best.g.holder.shoulder_w, best.g.holder.detent_depth, best.g.holder.detent_pos * 100.0, best.g.holder.friction_len, best.g.holder.drain_d, best.g.holder.holder_wall,
        hf.insertion_n, hf.draw_n, best.cut_p05, best.sharp_p05, cfg.islands, cfg.mc_samples);
    match &plate {
        Some(c) => { let _ = writeln!(rep, "plate FEM: lateral {:.1} N (blade {:.1} / grip {:.1}), in-plane {:.0} N, ring pull {:.0} N, {} nodes / {} free dofs",
            c.blade_lat_n.min(c.grip_lat_n), c.blade_lat_n, c.grip_lat_n, c.inplane_n, c.ring_pull_n, c.nodes, c.free_dofs); }
        None => { let _ = writeln!(rep, "plate FEM: mesh did not solve"); }
    }
    w("best_report.md", rep);
}
