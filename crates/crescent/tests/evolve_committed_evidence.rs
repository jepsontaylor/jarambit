//! Replay content bindings of the actual automatic run, without replacing its independent solves.
use jarambit_crescent::{battery, certification, genome::Genome};
use serde_json::Value;
use std::path::{Path, PathBuf};

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn read(root: &Path, path: &str) -> Value {
    serde_json::from_slice(&std::fs::read(root.join(path)).unwrap()).unwrap()
}
fn genome(root: &Path, path: &str) -> Genome {
    let text = std::fs::read_to_string(root.join(path)).unwrap();
    Genome::from_csv(&text.lines().nth(1).unwrap().split(',').collect::<Vec<_>>()).unwrap()
}

#[test]
fn historical_independent_observations_are_withheld_after_validation_policy_changes() {
    let root = root();
    let manifest = read(&root, "evidence/evolve_certifiable/manifest.json");
    let run = &manifest["automatic"];
    let asset = |name: &str| run["artifacts"][name].as_str().unwrap().to_owned();
    let g = genome(&root, &asset("genome"));
    let key = certification::identity(&g);
    assert_ne!(key, manifest["regeneration"]["exports"][1]["certificate_identity"].as_str().unwrap());
    assert_ne!(key, run["certificate_identity"].as_str().unwrap());
    let stored = read(&root, &asset("solid_tip"));
    assert!(!certification::bound(&stored, &key));
    assert_eq!(certification::independent_pass(&stored), Some(true));
    let spec = battery::GenomeSpec {
        id: run["label"].as_str().unwrap().into(),
        genome: asset("genome"),
        rs: asset("rs"),
        d1: Some(asset("d1")),
        tip_mesh: Some(asset("solid_tip")),
        plate_gci: Some(asset("plate_gci")),
        side_a4: Some(asset("a4")),
        ..Default::default()
    };
    let result = battery::build_subject(
        &root,
        &spec.id,
        manifest["numerical_kernel_commit"].as_str().unwrap(),
        &battery::Probes::default(),
        None,
        Some(&spec),
    )
    .unwrap();
    let case = result["cases"]
        .as_array()
        .unwrap()
        .iter()
        .find(|c| c["id"] == "solid.tip")
        .unwrap();
    assert_eq!(case["status"], "incomplete", "{case}");
    assert!(case["reason"].as_str().unwrap().contains("identity"));
    // A verified computation is distinct from a physically qualifying design.
    assert_eq!(run["result"]["qualified_count"], 0);
    assert!(!read(&root, &asset("rs"))["all_hard"].as_bool().unwrap());
}

#[test]
fn historical_geometry_control_and_current_export_identity_are_distinct() {
    let root = root();
    let manifest = read(&root, "evidence/evolve_certifiable/manifest.json");
    let control = &manifest["geometry_control"];
    let g = genome(&root, control["genome"].as_str().unwrap());
    let measurement = read(&root, control["measurements"].as_str().unwrap());
    let current = certification::identity(&g);
    assert_ne!(current, manifest["regeneration"]["exports"][0]["certificate_identity"].as_str().unwrap());
    assert!(!certification::bound(&measurement,&current));
    assert_eq!(measurement["measurements"]["sharpness"]["pass"], true);
    assert!(
        measurement["measurements"]["bore_edge_radius_mm"]
            .as_f64()
            .unwrap()
            >= 1.5
    );
    assert_eq!(measurement["measurements"]["point"]["pass"], false);
    let step = read(&root, control["step_check"].as_str().unwrap());
    assert_eq!(step["valid"], true);
    assert_eq!(step["solids"], 1);
    assert_eq!(step["bore_rolls_on_both_faces"], true);
}
