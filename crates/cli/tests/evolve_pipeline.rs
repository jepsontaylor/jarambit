//! Exercise the public command path: unavailable independent solvers cannot produce a certificate.
use std::{path::PathBuf, process::Command};
#[test]
fn top_k_cli_keeps_an_unavailable_runtime_unverified() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let unique = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let out = root
        .join("target/evolve-process-controls")
        .join(unique.to_string());
    let result = Command::new(env!("CARGO_BIN_EXE_jarambit"))
        .args([
            "auto-evolve",
            "--rounds",
            "1",
            "--candidates-per-round",
            "1",
            "--top-k-certify",
            "1",
            "--threads",
            "1",
            "--seed",
            "17",
            "--seeds",
            "evidence/rs_v2/w283_ultrarunner/w283_p14_c01_genome.csv",
            "--prefix",
            "runtime_control",
            "--out-dir",
        ])
        .arg(&out)
        .current_dir(&root)
        .env(
            "JARAMBIT_SOLVER_PYTHON",
            "/missing/independent-solver-python",
        )
        .output()
        .unwrap();
    assert!(!result.status.success());
    std::fs::write(out.join("command_stdout.txt"), &result.stdout).unwrap();
    std::fs::write(out.join("command_stderr.txt"), &result.stderr).unwrap();
    let report: serde_json::Value = serde_json::from_slice(
        &std::fs::read(out.join("leaderboard.json")).expect("attempt report even when unverified"),
    )
    .unwrap();
    assert_eq!(report["qualified_count"], 0);
    assert!(report["champion"].is_null());
    assert_eq!(report["designs"].as_array().unwrap().len(), 0);
    let errors = report["unverified"].as_array().unwrap();
    assert_eq!(errors.len(), 1);
    assert_eq!(errors[0]["status"], "unverified");
    assert!(errors[0]["reason"]
        .as_str()
        .unwrap()
        .contains("independent certification"));
    assert!(out.join("round_00_births.json").is_file());
}
