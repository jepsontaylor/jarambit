use jarambit_evolve::{nominal, run, Config, Indiv};
use jarambit_genotype::{limits, Genotype};
use std::fmt::Write;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let arg = |k: &str, d: usize| a.iter().position(|x| x == k).and_then(|i| a.get(i + 1)).and_then(|v| v.parse().ok()).unwrap_or(d);
    let threads = arg("--threads", 16).min(48); // shared box cap
    let cfg = Config { pop: arg("--pop", 32), gens: arg("--gens", 5), mc_samples: arg("--mc", 256), threads, seed: arg("--seed", 42) as u64 };
    let out = a.iter().position(|x| x == "--out").and_then(|i| a.get(i + 1)).cloned().unwrap_or("out".into());
    std::fs::create_dir_all(&out).unwrap();
    let mut rows = vec![];
    let mut csv = format!("gen,best_p05_spg,pop_mean_p05,diversity,rejected_in_gen,best_strength_n,best_mass_g,{}\n", Genotype::CSV_HEADER);
    let mut qcsv = String::from("gen,reasons\n");
    let mut raw: Vec<(f64, f64)> = vec![];
    let (best, front) = run(&cfg, |s| {
        let b = &s.pop[0];
        let feas: Vec<f64> = s.pop.iter().map(|i| i.fit).filter(|f| *f > -1e2).collect();
        let mean = if feas.is_empty() { f64::NAN } else { feas.iter().sum::<f64>() / feas.len() as f64 };
        for i in s.pop { raw.push((s.gen as f64, i.fit.max(-20.0))); }
        println!("gen {:3}  best p05 spg {:.3} N/g  S={:.0}N m={:.1}g  div={:.3}  rejected={}  t={:.1}mm grip={:.1}", s.gen, b.fit, b.strength_n, b.mass_g, s.diversity, s.rejected, b.g.thickness, b.g.grip_len);
        rows.push((s.gen, b.fit, mean, s.diversity));
        let _ = writeln!(csv, "{},{:.5},{:.5},{:.4},{},{:.1},{:.2},{}", s.gen, b.fit, mean, s.diversity, s.rejected, b.strength_n, b.mass_g, b.g.to_csv_row());
        for (_, why) in &s.quarantine { let _ = writeln!(qcsv, "{},\"{}\"", s.gen, why.replace('"', "'")); }
    });
    let (p, rt, e) = nominal(&best.g);
    println!("final p05 spg {:.3} N/g  redteam={:?}  floors_ok={}  mass={:.1}g  S={:.0}N  blade tip-heel/reach/arc = {:.1}/{:.1}/{:.1} mm (limit {:.3})",
        best.fit, rt, e.floors_ok(), e.mass_g, e.strength_n, p.blade.tip_to_heel, p.blade.horizontal_reach, p.blade.sharpened_arc, limits::BLADE_LIMIT_MM);
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
    let _ = writeln!(rep, "# Best design constraint report\n\nredteam: {rt:?}\nmaterial: {}\nthickness: {:.1} mm\nmass: {:.2} g\ngoverning strength: {:.1} N (blade {:.1} / grip {:.1}); ring pull {:.0} N\nstrength-per-gram: {:.3} N/g (MC p05 {:.3})\nfloors: hiker={} hunter={} ring={}\n",
        best.g.material.name(), p.thickness, e.mass_g, e.strength_n, e.blade_lat_n, e.grip_lat_n, e.ring_pull_n, e.strength_per_gram, best.fit, e.hiker_ok, e.hunter_ok, e.ring_ok);
    let _ = writeln!(rep, "blade (limit {:.3} mm, guard {:.1}): tip_to_heel {:.2} | horizontal_reach {:.2} | sharpened_arc {:.2} (outer {:.2}, inner {:.2}) | sweep {:.1} deg",
        limits::BLADE_LIMIT_MM, limits::BLADE_GUARD_MM, p.blade.tip_to_heel, p.blade.horizontal_reach, p.blade.sharpened_arc, p.blade.sharpened_arc_outer, p.blade.sharpened_arc_inner, p.blade.sweep_deg);
    let _ = writeln!(rep, "grip (ring-neck to guard): {:.2} mm\nring ID: {:.2} mm\nholder: ricasso land {:.1} mm, shoulder {:.2} mm/side, detent {:.2} mm @ {:.0}% grip, friction {:.1} mm, drain {:.1} mm, shell {:.2} mm",
        p.grip_len, p.ring_id, best.g.holder.ricasso_len, best.g.holder.shoulder_w, best.g.holder.detent_depth, best.g.holder.detent_pos * 100.0, best.g.holder.friction_len, best.g.holder.drain_d, best.g.holder.holder_wall);
    w("best_report.md", rep);
}
