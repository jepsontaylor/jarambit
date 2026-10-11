use jarambit_evolve::{run, Config};
use jarambit_genotype::Genotype;
use jarambit_phenotype::Phenotype;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let arg = |k: &str, d: usize| a.iter().position(|x| x == k).and_then(|i| a.get(i + 1)).and_then(|v| v.parse().ok()).unwrap_or(d);
    let threads = arg("--threads", 16);
    let cfg = Config { pop: arg("--pop", 32), gens: arg("--gens", 5), mc_samples: arg("--mc", 256), threads, seed: arg("--seed", 42) as u64, load_n: 150.0 };
    let out = a.iter().position(|x| x == "--out").and_then(|i| a.get(i + 1)).cloned().unwrap_or("out".into());
    std::fs::create_dir_all(&out).unwrap();
    let mut rows = vec![];
    let mut csv = format!("gen,fitness_p05,{}\n", Genotype::CSV_HEADER);
    let (best, f) = run(&cfg, |g, gen, fit| { println!("gen {g:3}  best p05 fitness {fit:.4}  t={:.1}mm edge={:.1}deg", gen.thickness, gen.edge_angle_deg); rows.push((g, fit)); csv.push_str(&format!("{g},{fit:.5},{}\n", gen.to_csv_row())); });
    let p = Phenotype::from_genotype(&best);
    let rt = jarambit_redteam::check(&best, &p);
    println!("final fitness {f:.4}  redteam={:?}  mass={:.1}g  teeth in/out={}/{}", rt, p.mass_g(4.43), p.inner_teeth, p.outer_teeth);
    std::fs::write(format!("{out}/history.csv"), csv).unwrap();
    std::fs::write(format!("{out}/best.stl"), p.to_ascii_stl("switchback_best")).unwrap();
    std::fs::write(format!("{out}/best.step"), p.to_step_stub("switchback_best")).unwrap();
    std::fs::write(format!("{out}/results.md"), jarambit_docs::results_table(&rows)).unwrap();
}
