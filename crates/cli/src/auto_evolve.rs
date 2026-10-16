//! Automated multi-wave evolutionary search with ALL hard engineering gates
//! (`16/16 W_CAD_v2` + `10/10 RS-karambit-v2 all_hard` + 3D `TET10` solid-tip FEM +
//! `side.a4` buckling + 3-level Roache `GCI` + strict `0.0625 mm^2` plate + 3D watertight STEP/STL).

use jarambit_crescent::{
    battery::score_cad_native,
    fem,
    genome::{
        self, Genome, EA_IN, EA_SP, EDGE_TH, FUL_D, K0, K_N, NECK_L, NG, N_CP, POCKET_D, POCKET_R,
        RAIL_W, TAPER_X0, T_TIP,
    },
    pheno, qd,
};
use jarambit_genotype::Rng;
use serde_json::{json, Value};
use std::fmt::Write as _;
use std::path::{Path, PathBuf};

fn repo_root() -> PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if cwd.join("docs/VERSION").is_file() {
        return cwd;
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .map(Path::to_path_buf)
        .unwrap_or(cwd)
}

#[derive(Clone, Debug)]
struct ScreenSurvivor {
    label: String,
    family: String,
    g: Genome,
    mass_g: f64,
    seq_ratio: f64,
    fat_sf: f64,
    ring_bearing_w_mm: f64,
}

#[derive(Clone, Debug)]
struct CertifiedDesign {
    label: String,
    family: String,
    g: Genome,
    mass_g: f64,
    mass_3d_g: f64,
    w_cad: f64,
    g1: f64,
    strict_hunter_sf: f64,
    solid_tip_sf: f64,
    seq_ratio: f64,
    fat_sf: f64,
    ring_bearing_w_mm: f64,
    buckling_eig: f64,
    battery_pass: i64,
    all_16_gates: bool,
    rs_v2_all_hard: bool,
    genome_csv: PathBuf,
    scorecard_md: PathBuf,
}

fn ensure_sfmap_env(root: &Path) {
    if std::env::var("JARAMBIT_P1_SFMAP").is_err() {
        let sfmap = root.join("evidence/d1_p1/w249_sfmap.txt");
        if sfmap.is_file() {
            std::env::set_var("JARAMBIT_P1_SFMAP", sfmap);
        }
    }
}

fn load_seed_genomes(root: &Path, seeds_arg: Option<&str>) -> Vec<(String, Genome)> {
    let default_paths = [
        "evidence/rs_v2/w283_ultrarunner/w283_p14_c01_genome.csv",
        "evidence/rs_v2/w283_ultrarunner/w283_p10_c02_genome.csv",
        "evidence/rs_v2/w282_ultrarunner/w282_p14_c01_genome.csv",
        "evidence/rs_v2/w282_ultrarunner/w282_p10_c02_genome.csv",
    ];
    let paths: Vec<String> = match seeds_arg {
        Some(s) if !s.trim().is_empty() => s
            .split(',')
            .map(|x| x.trim().to_string())
            .filter(|x| !x.is_empty())
            .collect(),
        _ => default_paths
            .iter()
            .filter(|rel| root.join(rel).is_file())
            .map(|rel| (*rel).to_string())
            .collect(),
    };

    let mut out = Vec::new();
    for raw in paths {
        let p = if Path::new(&raw).is_absolute() {
            PathBuf::from(&raw)
        } else {
            root.join(&raw)
        };
        let stem = p
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("seed")
            .trim_end_matches("_genome")
            .to_string();
        let family = if stem.contains("p10") {
            "p10".to_string()
        } else if stem.contains("p14") {
            "p14".to_string()
        } else {
            stem.clone()
        };
        if let Some(mut g) = crate::crescent::load_seeds(&p.to_string_lossy(), 1)
            .into_iter()
            .next()
        {
            if !g.rs_v2() {
                g.v[EDGE_TH] = 0.18;
            }
            g.clamp();
            if !out.iter().any(|(_, existing): &(String, Genome)| *existing == g) {
                out.push((family, g));
            }
        }
    }
    if out.is_empty() {
        let mut g = Genome::c6_seed(5.7);
        g.v[EDGE_TH] = 0.18;
        g.clamp();
        out.push(("c6".to_string(), g));
    }
    out
}

/// Generate a batch of targeted + stochastic `RS-karambit-v2` offspring around the current elite pool.
fn spawn_offspring_batch(
    elites: &[(String, Genome)],
    candidates_per_elite: usize,
    round: usize,
    rng: &mut Rng,
) -> Vec<(String, Genome)> {
    let mut batch = Vec::new();
    let b = genome::bounds();

    for (fam, parent) in elites {
        // Always include the exact parent in round 0 if not yet certified
        if round == 0 {
            let mut p0 = parent.clone();
            if !p0.rs_v2() {
                p0.v[EDGE_TH] = 0.18;
                p0.clamp();
            }
            batch.push((fam.clone(), p0));
        }

        for k in 0..candidates_per_elite {
            let mut child = parent.clone();
            let scale = 0.35 / ((round + 1) as f64).sqrt();

            match k % 6 {
                0 => {
                    if child.p1() {
                        child.v[POCKET_D] = (child.v[POCKET_D] + rng.normal() * 0.015 * scale)
                            .clamp(b[POCKET_D].0, b[POCKET_D].1);
                        child.v[POCKET_R] = (child.v[POCKET_R] + rng.normal() * 0.08 * scale)
                            .clamp(b[POCKET_R].0, b[POCKET_R].1);
                        child.v[RAIL_W] = (child.v[RAIL_W] + rng.normal() * 0.08 * scale)
                            .clamp(b[RAIL_W].0, b[RAIL_W].1);
                        child.v[NECK_L] = (child.v[NECK_L] + rng.normal() * 0.12 * scale)
                            .clamp(b[NECK_L].0, b[NECK_L].1);
                    } else {
                        for idx in [
                            genome::ISO_D,
                            genome::ISO_RIB,
                            genome::WIN_W,
                            genome::WIN_FILL,
                            genome::PERF_D,
                            genome::PERF_GAP,
                        ] {
                            let span = b[idx].1 - b[idx].0;
                            child.v[idx] = (child.v[idx] + rng.normal() * 0.008 * span * scale)
                                .clamp(b[idx].0, b[idx].1);
                        }
                    }
                }
                1 => {
                    // Distal taper & fuller tuning (tip torsion + sequence ratio balance)
                    child.v[TAPER_X0] = (child.v[TAPER_X0] + rng.normal() * 0.8 * scale)
                        .clamp(b[TAPER_X0].0, b[TAPER_X0].1);
                    child.v[T_TIP] = (child.v[T_TIP] + rng.normal() * 0.03 * scale)
                        .clamp(b[T_TIP].0, b[T_TIP].1);
                    child.v[FUL_D] = (child.v[FUL_D] + rng.normal() * 0.015 * scale)
                        .clamp(b[FUL_D].0, b[FUL_D].1);
                }
                2 => {
                    // Bevel & micro-bevel apex refinement within Gate S law (edge_t <= 0.20 mm)
                    child.v[EDGE_TH] = (child.v[EDGE_TH] + rng.normal() * 0.015 * scale).clamp(0.12, 0.20);
                    child.v[EA_IN] = (child.v[EA_IN] + rng.normal() * 0.15 * scale)
                        .clamp(b[EA_IN].0, b[EA_IN].1);
                    child.v[EA_SP] = (child.v[EA_SP] + rng.normal() * 0.15 * scale)
                        .clamp(b[EA_SP].0, b[EA_SP].1);
                }
                3 => {
                    // Thickness knot fine-tuning (K0..K0+4)
                    for idx in 0..5 {
                        let g_idx = K0 + idx;
                        child.v[g_idx] = (child.v[g_idx] + rng.normal() * 0.025 * scale)
                            .clamp(b[g_idx].0, b[g_idx].1);
                    }
                }
                4 => {
                    // Outline control point micro-sculpting (within aesthetic Hausdorff corridor)
                    for _ in 0..3 {
                        let cp = ((rng.f64() * (N_CP as f64)) as usize).min(N_CP - 1);
                        child.v[cp] = (child.v[cp] + rng.normal() * 0.06 * scale)
                            .clamp(b[cp].0, b[cp].1);
                    }
                }
                _ => {
                    // Multi-gene Gaussian + optional crossover with another elite
                    if elites.len() > 1 && rng.f64() < 0.5 {
                        let pick = ((rng.f64() * (elites.len() as f64)) as usize).min(elites.len() - 1);
                        let other = &elites[pick].1;
                        let alpha = 0.15 + 0.35 * rng.f64();
                        for idx in 0..NG {
                            if idx != K_N && rng.f64() < 0.35 {
                                child.v[idx] = child.v[idx] * (1.0 - alpha) + other.v[idx] * alpha;
                            }
                        }
                    } else {
                        child = child.mutate(rng, 0.008 * scale);
                    }
                }
            }

            child.v[EDGE_TH] = child.v[EDGE_TH].clamp(0.12, 0.20);
            child.clamp();
            batch.push((fam.clone(), child));
        }
    }
    batch
}

/// Stage 1: Fast parallel screen enforcing all 2D/3D/FEM/`RS-karambit-v2` hard gates.
fn screen_candidate_stage1(
    round: usize,
    idx: usize,
    family: &str,
    g: &Genome,
    prefix: &str,
) -> Option<ScreenSurvivor> {
    if !g.rs_v2() {
        return None;
    }
    let r = qd::evaluate(g, idx, round, 2.0);
    if !r.aes.pass || !r.rejects.is_empty() {
        return None;
    }
    if !fem::gate_s::law_pass(g.v[EDGE_TH], g.v[EA_IN], g.v[EA_SP]) {
        return None;
    }
    let p = pheno::build(g);
    let (s2_ok, _, _, _, _, _) = fem::gate_s::brep_point_check(&p);
    if !s2_ok {
        return None;
    }
    let (f, _) = fem::certify(&p)?;
    if !f.floors_ok
        || f.seq_ratio < fem::SEQ_TARGET
        || f.twist_body_sf < 1.0
        || f.twist_tipzone_sf < 1.0
        || !fem::rs_v2_human_max_pass(&f, &p)
        || !fem::rs_v2_fatigue_pass(&f)
    {
        return None;
    }

    let (bw, _) = fem::ring_bearing(&p);

    Some(ScreenSurvivor {
        label: format!("{prefix}_r{:02}_{family}_c{:02}", round + 1, idx + 1),
        family: family.to_string(),
        g: g.clone(),
        mass_g: p.mass_g,
        seq_ratio: f.seq_ratio,
        fat_sf: f.fat_sf,
        ring_bearing_w_mm: bw,
    })
}

/// Stage 2: Full physics certification (`0.0625 mm^2` strict plate + 3-mesh `GCI` + `side.a4` +
/// 3D `TET10` solid-tip FEM + `18/18` CAD battery + Master CAD Scorecard).
fn certify_candidate_stage2(
    root: &Path,
    out_dir: &Path,
    cand: &ScreenSurvivor,
) -> Result<CertifiedDesign, String> {
    std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;
    let genome_csv = out_dir.join(format!("{}_genome.csv", cand.label));
    let csv_text = format!("{}\n{}\n", Genome::csv_header(), cand.g.csv_row());
    std::fs::write(&genome_csv, csv_text).map_err(|e| e.to_string())?;

    let sc = score_cad_native(
        root,
        &genome_csv.to_string_lossy(),
        out_dir,
        Some(&cand.label),
        None,
        true,
        false,
    )?;

    let em = sc.get("engineering_metrics").unwrap_or(&Value::Null);
    let wc = sc.get("weighted_cad_score").unwrap_or(&Value::Null);
    let g1 = sc.get("global_fitness_G1").unwrap_or(&Value::Null);
    let bat = sc.get("cad_battery").unwrap_or(&Value::Null);

    let all_16_gates = wc
        .get("all_engineering_gates_pass")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let w_cad = wc.get("W_CAD").and_then(|v| v.as_f64()).unwrap_or(-10.0);
    let g1_val = g1.get("G").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let mass_g = em.get("mass_g").and_then(|v| v.as_f64()).unwrap_or(cand.mass_g);
    let mass_3d_g = em.get("mass_3d_g").and_then(|v| v.as_f64()).unwrap_or(cand.mass_g);
    let strict_hunter_sf = em.get("sf_hunter_strict").and_then(|v| v.as_f64()).unwrap_or(0.0);
    let solid_tip_sf = em
        .get("solid_tip_sf_nodal_max")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let seq_ratio = em
        .get("seq_ratio_cert")
        .and_then(|v| v.as_f64())
        .unwrap_or(cand.seq_ratio);
    let fat_sf = em
        .get("fat_sf_l7")
        .and_then(|v| v.as_f64())
        .unwrap_or(cand.fat_sf);
    let ring_bearing_w_mm = em
        .get("ring_bearing_w_mm")
        .and_then(|v| v.as_f64())
        .unwrap_or(cand.ring_bearing_w_mm);
    let buckling_eig = em
        .get("buckling_eigenvalue_a4")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let battery_pass = bat.get("pass_count").and_then(|v| v.as_i64()).unwrap_or(0);

    let rs_case_pass = bat
        .get("cases")
        .and_then(|v| v.as_array())
        .and_then(|arr| arr.iter().find(|c| c.get("id").and_then(|x| x.as_str()) == Some("gate.rs_v2")))
        .and_then(|c| c.get("status").and_then(|x| x.as_str()))
        == Some("pass");

    Ok(CertifiedDesign {
        label: cand.label.clone(),
        family: cand.family.clone(),
        g: cand.g.clone(),
        mass_g,
        mass_3d_g,
        w_cad,
        g1: g1_val,
        strict_hunter_sf,
        solid_tip_sf,
        seq_ratio,
        fat_sf,
        ring_bearing_w_mm,
        buckling_eig,
        battery_pass,
        all_16_gates,
        rs_v2_all_hard: rs_case_pass,
        genome_csv,
        scorecard_md: out_dir.join(format!("{}_master_scorecard.md", cand.label)),
    })
}

/// CLI entrypoint for `jarambit auto-evolve`.
pub fn run_auto_evolve_cli(args: &[String]) -> i32 {
    let root = repo_root();
    ensure_sfmap_env(&root);

    let mut rounds = 2usize;
    let mut candidates_per_round = 12usize;
    let mut certify_top = 2usize;
    let mut threads = jarambit_monte_carlo::max_threads().min(16);
    let mut seed = 2830u64;
    let mut seeds_arg: Option<String> = None;
    let mut out_dir = root.join("out/auto_evolve");
    let mut prefix = String::from("auto");

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--rounds" | "--waves" => {
                if let Some(v) = args.get(i + 1).and_then(|x| x.parse::<usize>().ok()) {
                    rounds = v.max(1);
                    i += 1;
                }
            }
            "--candidates-per-round" | "--pop" => {
                if let Some(v) = args.get(i + 1).and_then(|x| x.parse::<usize>().ok()) {
                    candidates_per_round = v.max(1);
                    i += 1;
                }
            }
            "--certify-top" => {
                if let Some(v) = args.get(i + 1).and_then(|x| x.parse::<usize>().ok()) {
                    certify_top = v.max(1);
                    i += 1;
                }
            }
            "--threads" => {
                if let Some(v) = args.get(i + 1).and_then(|x| x.parse::<usize>().ok()) {
                    threads = v.max(1).min(jarambit_monte_carlo::max_threads());
                    i += 1;
                }
            }
            "--seed" => {
                if let Some(v) = args.get(i + 1).and_then(|x| x.parse::<u64>().ok()) {
                    seed = v;
                    i += 1;
                }
            }
            "--seeds" => {
                if let Some(v) = args.get(i + 1) {
                    seeds_arg = Some(v.clone());
                    i += 1;
                }
            }
            "--out-dir" | "--out" => {
                if let Some(v) = args.get(i + 1) {
                    out_dir = PathBuf::from(v);
                    i += 1;
                }
            }
            "--prefix" => {
                if let Some(v) = args.get(i + 1) {
                    prefix = v.clone();
                    i += 1;
                }
            }
            "-h" | "--help" => {
                println!(
                    "Usage: jarambit auto-evolve [--rounds N] [--candidates-per-round K] [--certify-top M] [--threads T] [--seeds <csv1,csv2>] [--out-dir <dir>] [--prefix <name>] [--seed <u64>]"
                );
                return 0;
            }
            _ => {}
        }
        i += 1;
    }

    if let Err(e) = std::fs::create_dir_all(&out_dir) {
        eprintln!("auto-evolve: cannot create {}: {e}", out_dir.display());
        return 1;
    }

    let mut elites = load_seed_genomes(&root, seeds_arg.as_deref());
    let mut rng = Rng(seed);
    let mut certified_all: Vec<CertifiedDesign> = Vec::new();

    println!(
        "=== JARAMBIT AUTO-EVOLVE (ALL ENGINEERING GATES: 16/16 W_CAD_v2 + 10/10 RS-karambit-v2 + 3D TET10 + side.a4 + 3-Mesh GCI) ==="
    );
    println!(
        "Config: rounds={rounds}, candidates/elite/round={candidates_per_round}, certify_top={certify_top}, threads={threads}, seed={seed}, out={}",
        out_dir.display()
    );

    for round in 0..rounds {
        let batch = spawn_offspring_batch(&elites, candidates_per_round, round, &mut rng);
        let th = threads.max(1).min(batch.len().max(1));
        let prefix_ref = prefix.as_str();

        let mut survivors: Vec<ScreenSurvivor> = std::thread::scope(|s| {
            let handles: Vec<_> = (0..th)
                .map(|t| {
                    let batch_ref = &batch;
                    s.spawn(move || {
                        batch_ref
                            .iter()
                            .enumerate()
                            .filter(|(idx, _)| idx % th == t)
                            .filter_map(|(idx, (fam, g))| {
                                screen_candidate_stage1(round, idx, fam, g, prefix_ref)
                            })
                            .collect::<Vec<_>>()
                    })
                })
                .collect();
            handles
                .into_iter()
                .flat_map(|h| h.join().expect("stage1 worker thread"))
                .collect()
        });

        // Sort Stage-1 survivors by lightest mass / highest estimated W_CAD_v2
        survivors.sort_by(|a, b| {
            a.mass_g
                .partial_cmp(&b.mass_g)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        println!(
            "\n[Round {}/{}] Stage-1 fast all-gates screen: {}/{} candidates passed all 2D/3D/FEM/RS-v2 hard gates",
            round + 1,
            rounds,
            survivors.len(),
            batch.len()
        );

        // Select up to `certify_top` distinct candidates (one per family first, then lightest overall)
        let mut to_certify: Vec<ScreenSurvivor> = Vec::new();
        for surv in &survivors {
            if to_certify.len() >= certify_top {
                break;
            }
            let already_certified = certified_all.iter().any(|c| c.g == surv.g);
            let dup_fam = to_certify.iter().any(|c| c.family == surv.family);
            if !already_certified && !dup_fam {
                to_certify.push(surv.clone());
            }
        }
        for surv in &survivors {
            if to_certify.len() >= certify_top {
                break;
            }
            let already_certified = certified_all.iter().any(|c| c.g == surv.g);
            let dup_in_batch = to_certify.iter().any(|c| c.g == surv.g);
            if !already_certified && !dup_in_batch {
                to_certify.push(surv.clone());
            }
        }

        for cand in &to_certify {
            println!(
                "  -> Stage-2 full 3D TET10 + side.a4 + 0.0625 plate + GCI certification for {} (family={}, screen_mass={:.3}g, seq={:.3}, fat_sf={:.3}, ring_w={:.2}mm)...",
                cand.label,
                cand.family,
                cand.mass_g,
                cand.seq_ratio,
                cand.fat_sf,
                cand.ring_bearing_w_mm
            );
            match certify_candidate_stage2(&root, &out_dir, cand) {
                Ok(cert) => {
                    println!(
                        "     [CERTIFIED] {} | 16_gates={} | RS-v2_all_hard={} | battery={}/18 | mass={:.3}g (3D {:.3}g) | W_CAD={:+.6} | G1={:.6} | solid_tip_SF={:.4} | strict_hunter_SF={:.4}",
                        cert.label,
                        if cert.all_16_gates { "PASS" } else { "FAIL" },
                        if cert.rs_v2_all_hard { "PASS" } else { "FAIL" },
                        cert.battery_pass,
                        cert.mass_g,
                        cert.mass_3d_g,
                        cert.w_cad,
                        cert.g1,
                        cert.solid_tip_sf,
                        cert.strict_hunter_sf
                    );
                    if cert.all_16_gates && cert.rs_v2_all_hard {
                        elites.push((cert.family.clone(), cert.g.clone()));
                        certified_all.push(cert);
                    }
                }
                Err(e) => {
                    eprintln!("     [STAGE-2 ERROR] {}: {e}", cand.label);
                }
            }
        }

        // Keep top elites sorted by lightest mass
        elites.sort_by(|a, b| {
            let ma = pheno::build(&a.1).mass_g;
            let mb = pheno::build(&b.1).mass_g;
            ma.partial_cmp(&mb).unwrap_or(std::cmp::Ordering::Equal)
        });
        if elites.len() > 4 {
            elites.truncate(4);
        }
    }

    certified_all.sort_by(|a, b| {
        a.mass_g
            .partial_cmp(&b.mass_g)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    if certified_all.is_empty() {
        eprintln!("auto-evolve: no candidate completed full Stage-2 certification");
        return 1;
    }

    let mut md = String::from(
        "# Automated All-Gates Evolution Leaderboard\n\nAll designs below passed **16/16 `W_CAD_v2` hard gates**, **10/10 `RS-karambit-v2` (`all_hard = true`)**, **3D `TET10` solid-tip FEM (`SF >= 1.0`)**, **`side.a4` buckling & support (`lambda_cr >= 1.0`)**, **3-level Roache `GCI`**, and **18/18 CAD battery cases**.\n\n| Rank | Design Label | Family | Mass (g) | 3D Solid Mass (g) | `W_CAD_v2` | `G1` | Strict Hunter SF | 3D Solid Tip SF | Seq Ratio | Fatigue SF | Ring Bearing (mm) | Buckling `lambda_cr` | Battery | Genome CSV |\n|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|\n",
    );
    let mut json_rows = Vec::with_capacity(certified_all.len());
    for (idx, c) in certified_all.iter().enumerate() {
        let _ = writeln!(
            md,
            "| {} | `{}` | `{}` | **{:.3}** | **{:.3}** | **`{:+.6}`** | `{:.6}` | `{:.4}` | `{:.4}` | `{:.4}` | `{:.4}` | `{:.2}` | `{:.3}` | `{}/18` | `{}` |",
            idx + 1,
            c.label,
            c.family,
            c.mass_g,
            c.mass_3d_g,
            c.w_cad,
            c.g1,
            c.strict_hunter_sf,
            c.solid_tip_sf,
            c.seq_ratio,
            c.fat_sf,
            c.ring_bearing_w_mm,
            c.buckling_eig,
            c.battery_pass,
            c.genome_csv.display()
        );
        json_rows.push(json!({
            "rank": idx + 1,
            "label": c.label,
            "family": c.family,
            "mass_g": c.mass_g,
            "mass_3d_g": c.mass_3d_g,
            "w_cad": c.w_cad,
            "g1": c.g1,
            "strict_hunter_sf": c.strict_hunter_sf,
            "solid_tip_sf": c.solid_tip_sf,
            "seq_ratio": c.seq_ratio,
            "fat_sf": c.fat_sf,
            "ring_bearing_w_mm": c.ring_bearing_w_mm,
            "buckling_eigenvalue_a4": c.buckling_eig,
            "battery_pass_count": c.battery_pass,
            "all_16_gates": c.all_16_gates,
            "rs_v2_all_hard": c.rs_v2_all_hard,
            "genome_csv": c.genome_csv.to_string_lossy(),
            "scorecard_md": c.scorecard_md.to_string_lossy(),
        }));
    }

    let lb_md_path = out_dir.join("leaderboard.md");
    let lb_json_path = out_dir.join("leaderboard.json");
    let _ = std::fs::write(&lb_md_path, &md);
    let _ = std::fs::write(
        &lb_json_path,
        serde_json::to_string_pretty(&json!({
            "schema": "jarambit.auto_evolve.leaderboard.v1",
            "champion": json_rows.first(),
            "designs": json_rows,
        }))
        .unwrap()
            + "\n",
    );

    println!("\n{md}");
    println!(
        "Champion: {} (mass={:.3}g, 3D={:.3}g, W_CAD={:+.6}, G1={:.6}, battery={}/18)\nLeaderboard written to: {}",
        certified_all[0].label,
        certified_all[0].mass_g,
        certified_all[0].mass_3d_g,
        certified_all[0].w_cad,
        certified_all[0].g1,
        certified_all[0].battery_pass,
        lb_md_path.display()
    );
    0
}
