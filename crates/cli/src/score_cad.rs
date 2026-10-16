//! Pure-Rust CLI handlers for `jarambit score-cad` and `jarambit cad-battery`.
//!
//! Evaluates any 3D `.step` / `.stl` CAD, `.csv` 128-gene genome, or catalog subject ID
//! natively in Rust through the 16 hard engineering gates, 18-case CAD battery, `G1`, and
//! `W_CAD_v2_ultrarunner_karambit`.

use jarambit_crescent::battery::{export_web_data_native, run_cad_battery_native, score_cad_native, Probes};
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

/// Execute `jarambit score-cad [args...]` natively in Rust.
pub fn run_score_cad_cli(args: &[String]) -> i32 {
    let mut input: Option<String> = None;
    let mut cad: Option<String> = None;
    let mut genome: Option<PathBuf> = None;
    let mut subject: Option<String> = None;
    let mut label: Option<String> = None;
    let mut out_dir = PathBuf::from("/tmp/jarambit_score_cad");
    let mut run_solid = true;
    let mut force_standalone_cad = false;

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--cad" => {
                if let Some(v) = args.get(i + 1) {
                    cad = Some(v.clone());
                    i += 1;
                }
            }
            "--genome" => {
                if let Some(v) = args.get(i + 1) {
                    genome = Some(PathBuf::from(v));
                    i += 1;
                }
            }
            "--subject" => {
                if let Some(v) = args.get(i + 1) {
                    subject = Some(v.clone());
                    i += 1;
                }
            }
            "--label" => {
                if let Some(v) = args.get(i + 1) {
                    label = Some(v.clone());
                    i += 1;
                }
            }
            "--out-dir" => {
                if let Some(v) = args.get(i + 1) {
                    out_dir = PathBuf::from(v);
                    i += 1;
                }
            }
            "--no-run-solid" => {
                run_solid = false;
            }
            "--force-standalone-cad" => {
                force_standalone_cad = true;
            }
            "-h" | "--help" => {
                println!(
                    "Usage: jarambit score-cad [<input>] [--cad <path>] [--genome <csv>] [--subject <id>] [--label <lbl>] [--out-dir <dir>] [--no-run-solid] [--force-standalone-cad]"
                );
                return 0;
            }
            arg if !arg.starts_with('-') && input.is_none() => {
                input = Some(arg.to_string());
            }
            _ => {}
        }
        i += 1;
    }

    let has_pos_or_cad = input.is_some() || cad.is_some();
    let target = input
        .or(cad)
        .or_else(|| genome.as_ref().map(|p| p.to_string_lossy().to_string()))
        .or(subject);
    let Some(target) = target else {
        eprintln!("score-cad: Provide a CAD file (.step/.stl), genome (.csv), or --subject <id>");
        return 2;
    };

    let root = repo_root();
    let genome_override = if has_pos_or_cad {
        genome.as_deref()
    } else {
        None
    };

    match score_cad_native(
        &root,
        &target,
        &out_dir,
        label.as_deref(),
        genome_override,
        run_solid,
        force_standalone_cad,
    ) {
        Ok(sc) => {
            let subj = sc.get("subject").and_then(|v| v.as_str()).unwrap_or(&target);
            let mode = sc
                .get("evaluation_mode")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown");
            let em = sc.get("engineering_metrics").unwrap_or(&serde_json::Value::Null);
            let wc = sc.get("weighted_cad_score").unwrap_or(&serde_json::Value::Null);
            let g1 = sc.get("global_fitness_G1").unwrap_or(&serde_json::Value::Null);
            let bat = sc.get("cad_battery").unwrap_or(&serde_json::Value::Null);
            let mass_g = em.get("mass_g").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let mass_3d = em.get("mass_3d_g").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let all_ok = wc
                .get("all_engineering_gates_pass")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            let w_val = wc.get("W_CAD").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let g1_status = g1.get("status").and_then(|v| v.as_str()).unwrap_or("INCOMPLETE");
            let g1_val = match g1.get("G").and_then(|v| v.as_f64()) {
                Some(g) => format!("{g:.6}"),
                None => "INCOMPLETE".to_string(),
            };
            let pass_cnt = bat.get("pass_count").and_then(|v| v.as_i64()).unwrap_or(0);
            let total_cases = bat
                .get("cases")
                .and_then(|v| v.as_array())
                .map_or(18, |a| a.len());
            println!(
                "[{subj}] mode={mode} mass={mass_g:.3}g (3D {mass_3d:.3}g) gates_16={} W_CAD={w_val:+.6} G1={g1_val} ({g1_status}) battery={pass_cnt}/{total_cases} pass",
                if all_ok { "PASS" } else { "FAIL" }
            );
            0
        }
        Err(e) => {
            eprintln!("score-cad error: {e}");
            1
        }
    }
}

/// Execute `jarambit cad-battery [args...]` natively in Rust.
pub fn run_cad_battery_cli(args: &[String]) -> i32 {
    let root = repo_root();
    let mut subject: Option<String> = None;
    let mut all = false;
    let mut evaluate_genome: Option<String> = None;
    let mut out_dir = root.join("evidence/cad_battery");
    let mut commit: Option<String> = None;
    let mut probes = Probes {
        analytic: "incomplete".to_string(),
        gci: "incomplete".to_string(),
        claims: "incomplete".to_string(),
        dolfinx: None,
    };

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--subject" => {
                if let Some(v) = args.get(i + 1) {
                    subject = Some(v.clone());
                    i += 1;
                }
            }
            "--all" => {
                all = true;
            }
            "--evaluate-genome" => {
                if let Some(v) = args.get(i + 1) {
                    evaluate_genome = Some(v.clone());
                    i += 1;
                }
            }
            "--out-dir" => {
                if let Some(v) = args.get(i + 1) {
                    out_dir = PathBuf::from(v);
                    i += 1;
                }
            }
            "--commit" => {
                if let Some(v) = args.get(i + 1) {
                    commit = Some(v.clone());
                    i += 1;
                }
            }
            "--analytic" => {
                if let Some(v) = args.get(i + 1) {
                    probes.analytic = v.clone();
                    i += 1;
                }
            }
            "--gci" => {
                if let Some(v) = args.get(i + 1) {
                    probes.gci = v.clone();
                    i += 1;
                }
            }
            "--claims" => {
                if let Some(v) = args.get(i + 1) {
                    probes.claims = v.clone();
                    i += 1;
                }
            }
            "--dolfinx" => {
                if let Some(v) = args.get(i + 1) {
                    probes.dolfinx = Some(v.clone());
                    i += 1;
                }
            }
            "-h" | "--help" => {
                println!(
                    "Usage: jarambit cad-battery [--all | --subject <id> | --evaluate-genome <lbl>=<csv>] [--out-dir <dir>] [--analytic pass|fail|incomplete] [--gci pass|fail|incomplete] [--claims pass|fail|incomplete] [--dolfinx pass|fail|incomplete|blocked]"
                );
                return 0;
            }
            _ => {}
        }
        i += 1;
    }

    if subject.is_none() && !all && evaluate_genome.is_none() {
        eprintln!("cad-battery: pass --subject, --all, or --evaluate-genome");
        return 2;
    }

    match run_cad_battery_native(
        &root,
        subject.as_deref(),
        evaluate_genome.as_deref(),
        &out_dir,
        commit.as_deref(),
        &probes,
    ) {
        Ok(res) => {
            if evaluate_genome.is_some() {
                let subj = res.get("subject").and_then(|v| v.as_str()).unwrap_or("genome");
                let p_cnt = res.get("pass_count").and_then(|v| v.as_i64()).unwrap_or(0);
                let s_cnt = res.get("solver_run_count").and_then(|v| v.as_i64()).unwrap_or(0);
                let gf = res.get("global_fitness").unwrap_or(&serde_json::Value::Null);
                let st = gf.get("status").and_then(|v| v.as_str()).unwrap_or("INCOMPLETE");
                let g_v = gf.get("G");
                println!("{subj} pass={p_cnt} solver_runs={s_cnt} G={st} ({g_v:?})");
            } else if let Some(subs) = res.get("subjects").and_then(|v| v.as_array()) {
                println!(
                    "cad-battery: evaluated {} subject(s) -> {}",
                    subs.len(),
                    out_dir.display()
                );
            }
            0
        }
        Err(e) => {
            eprintln!("cad-battery error: {e}");
            1
        }
    }
}

/// Execute `jarambit export-web-data [--out-dir <dir>]` natively in Rust.
pub fn run_export_web_data_cli(args: &[String]) -> i32 {
    let root = repo_root();
    let mut out_dir = root.join("web/public/data");
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--out-dir" => {
                if let Some(v) = args.get(i + 1) {
                    out_dir = PathBuf::from(v);
                    i += 1;
                }
            }
            "-h" | "--help" => {
                println!("Usage: jarambit export-web-data [--out-dir <dir>]");
                return 0;
            }
            _ => {}
        }
        i += 1;
    }
    match export_web_data_native(&root, &out_dir) {
        Ok(bundle) => {
            let n_sub = bundle
                .get("subjects")
                .and_then(|v| v.as_array())
                .map_or(0, |a| a.len());
            println!(
                "export-web-data: exported {n_sub} subjects + featured scorecards + STL meshes -> {}",
                out_dir.display()
            );
            0
        }
        Err(e) => {
            eprintln!("export-web-data error: {e}");
            1
        }
    }
}

