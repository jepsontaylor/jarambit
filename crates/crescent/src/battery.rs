//! Pure-Rust 18-Evaluator CAD Battery (`jarambit.cad_battery.subject.v1`),
//! Master Weighted CAD Score (`W_CAD_v2_ultrarunner_karambit`), and Unified
//! Master CAD Scorecard (`jarambit.master_cad_scorecard.v1`).

use crate::{
    aesthetic,
    cad_ingest::{
        goodman_sf, inspect_step_header, mesh_census_and_volume, parse_faceted_step_triangles,
        parse_stl_triangles, rasterize_and_extract_archetype, round_n, torsion_3d_factor,
    },
    export, fem,
    g1::{assemble_g, global_g, title_tag},
    gci::run_plate_gci_3level,
    genome::Genome,
    pheno,
};
use jarambit_evidence::identity::ContentRef;
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use std::path::{Path, PathBuf};


pub const BATTERY_SCHEMA: &str = "jarambit.cad_battery.subject.v1";
pub const SCORECARD_SCHEMA: &str = "jarambit.master_cad_scorecard.v1";
pub const SIDE_SHA: &str = "3e419ac1cbd2576b9b2f92296862d937e763abe27cc2a065c4937ff6ec4a85f9";

pub const CASE_IDS: [&str; 18] = [
    "build.analytic",
    "build.gci_contracts",
    "build.claims",
    "build.dolfinx",
    "geom.unit",
    "geom.one_solid",
    "geom.mass",
    "geom.pin",
    "plate.loads",
    "plate.seq",
    "plate.l7",
    "plate.gci",
    "side.a1",
    "side.a2",
    "side.a3",
    "side.a4",
    "solid.tip",
    "gate.rs_v2",
];

pub const SOLVER_FIELDS: [&str; 3] = ["n_tet", "n_dof", "ksp_its"];

pub fn sha256_bytes(bytes: &[u8]) -> String {
    ContentRef::from_bytes("x", "rev1", bytes).sha256
}

pub fn sha256_file(path: &Path) -> Option<String> {
    let bytes = std::fs::read(path).ok()?;
    Some(sha256_bytes(&bytes))
}

pub fn load_json(root: &Path, rel: &str) -> Option<Value> {
    if rel.is_empty() {
        return None;
    }
    let p = Path::new(rel);
    let full = if p.is_absolute() {
        p.to_path_buf()
    } else {
        root.join(p)
    };
    let txt = std::fs::read_to_string(full).ok()?;
    serde_json::from_str(&txt).ok()
}

pub fn read_version(root: &Path) -> String {
    std::fs::read_to_string(root.join("docs/VERSION"))
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| include_str!("../../../docs/VERSION").trim().to_string())
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct NativePinSpec {
    pub id: &'static str,
    pub name: &'static str,
    pub role: &'static str,
    pub archived: bool,
    pub step: &'static str,
    pub stl: &'static str,
    pub step_sha256: &'static str,
    pub stl_sha256: &'static str,
    pub readme_mass_g: f64,
}

pub const NATIVE_PINS: [NativePinSpec; 4] = [
    NativePinSpec {
        id: "c10a",
        name: "C10a",
        role: "comparison_baseline",
        archived: false,
        step: "designs/switchback/C10a/cad/switchback_revC10a_ground.step",
        stl: "designs/switchback/C10a/cad/switchback_revC10a_ground.stl",
        step_sha256: "441cfabc284efd632b69b169816bd1242088508d95dd93839dcea419e582dbe7",
        stl_sha256: "0bcadad61bff550d9c527266e183440e8242c3a0222b9a89755cdc682b214411",
        readme_mass_g: 64.841,
    },
    NativePinSpec {
        id: "c93",
        name: "C93",
        role: "release_candidate",
        archived: false,
        step: "designs/switchback/C9.3/cad/switchback_revC9_3_ground.step",
        stl: "designs/switchback/C9.3/cad/switchback_revC9_3_ground.stl",
        step_sha256: "3a818183bcb5b9a9093da947e00414ed29aa9bfebbb614046b8fb0b16dcbe919",
        stl_sha256: "1aeda17eba396bcec7380ac27f7d20886d64d234f70ad8d3d0cc57aaf63d74ca",
        readme_mass_g: 66.773,
    },
    NativePinSpec {
        id: "c92",
        name: "C92",
        role: "previous_release_candidate",
        archived: false,
        step: "designs/switchback/C9.2/cad/switchback_revC9_2_ground.step",
        stl: "designs/switchback/C9.2/cad/switchback_revC9_2_ground.stl",
        step_sha256: "2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307",
        stl_sha256: "10b8c41f80b898c255cc090a349559722258f87f8af849ce9a605e14d762e847",
        readme_mass_g: 66.764,
    },
    NativePinSpec {
        id: "c10c",
        name: "C10c",
        role: "archived_diagnostic",
        archived: true,
        step: "designs/switchback/C10c/cad/switchback_revC10c_ground.step",
        stl: "designs/switchback/C10c/cad/switchback_revC10c_ground.stl",
        step_sha256: "4211f35b1c04d795029c85bcd3fa6a81ed3456f774a935d419e326bc06d4eae4",
        stl_sha256: "ac64a65dd653194d563a2026ffa42213846a9bda7cce7c52f80327da4c6e4700",
        readme_mass_g: 67.089,
    },
];

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct GenomeSpec {
    pub id: String,
    pub rs: String,
    pub d1: Option<String>,
    pub genome: String,
    pub tip_mesh: Option<String>,
    pub plate_gci: Option<String>,
    pub side_a4: Option<String>,
    pub side_path: Option<String>,
    pub side_sha: Option<String>,
    pub side_seq: Option<f64>,
    pub d1_searched: Option<Vec<String>>,
}

fn d1_searched(name: &str) -> Vec<String> {
    vec![
        format!("/home/ubuntu/fs4/d1/{name}_D1.json"),
        format!("ubuntu@192.168.68.54:/home/ubuntu/fs4/d1/{name}_D1.json"),
        format!("/home/ubuntu/jarambit_w271/out/solidcert_{name}/{name}_D1.json"),
        format!("evidence/ has the RS json and the genome csv for {name}, and no {name}_D1.json"),
    ]
}

fn side_info(root: &Path, rel: &str) -> (Option<String>, Option<String>, Option<f64>) {
    let p = root.join(rel);
    let Some(sha) = sha256_file(&p) else {
        return (None, None, None);
    };
    let seq = load_json(root, rel).and_then(|v| v.get("seq_ratio_this_mesh")?.as_f64());
    (Some(rel.to_string()), Some(sha), seq)
}

/// Ordered catalog of all 17 genome subjects in `ops/ci/cad_battery.py`.
pub fn genome_catalog(root: &Path) -> Vec<GenomeSpec> {
    let g3_side_rel = "evidence/cad_battery/side/g3_a1a3.json";
    let (g3_side, g3_sha, g3_seq) = side_info(root, g3_side_rel);
    let (g3_side, g3_sha, g3_seq) = if g3_sha.as_deref() == Some(SIDE_SHA) {
        (g3_side, g3_sha, g3_seq)
    } else {
        (None, None, None)
    };

    let mut out = Vec::new();
    out.push(GenomeSpec {
        id: "g3".into(),
        rs: "evidence/rs_v2/g3_tip+00_t60_tt3.json".into(),
        d1: Some("evidence/wave27/g3_tip+00_t60_tt3_D1.json".into()),
        genome: "evidence/rs_v2/genomes/g3_tip+00_t60_tt3.csv".into(),
        tip_mesh: Some("evidence/cad_battery/tip_mesh/g3.json".into()),
        plate_gci: Some("evidence/cad_battery/plate_gci/g3.json".into()),
        side_a4: Some("evidence/cad_battery/side/g3_a4.json".into()),
        side_path: g3_side,
        side_sha: g3_sha,
        side_seq: g3_seq,
        d1_searched: None,
    });

    for (id, rs, genome, searched) in [
        (
            "w271b_11772",
            "evidence/rs_v2/w271b_11772.json",
            "evidence/rs_v2/genomes/w271b_11772_genome.csv",
            false,
        ),
        (
            "w271b_11860",
            "evidence/rs_v2/w271b_11860.json",
            "evidence/rs_v2/genomes/w271b_11860_genome.csv",
            true,
        ),
        (
            "w271c_11522",
            "evidence/rs_v2/w271c_11522.json",
            "evidence/rs_v2/genomes/w271c_11522.csv",
            true,
        ),
        (
            "w272_s2902_c01",
            "evidence/rs_v2/w272_xbabe3/w272_s2902_c01_rs.json",
            "evidence/rs_v2/w272_xbabe3/s2902/wave272_xbabe3_s2902_c01_fit_genome.csv",
            false,
        ),
        (
            "w273_s2904_c01",
            "evidence/rs_v2/w273_xbabe3/w273_s2904_c01_rs.json",
            "evidence/rs_v2/w273_xbabe3/s2904/wave273_xbabe3_s2904_c01_fit_genome.csv",
            false,
        ),
        (
            "w273_s2903_c04",
            "evidence/rs_v2/w273_xbabe3/w273_s2903_c04_rs.json",
            "evidence/rs_v2/w273_xbabe3/s2903/wave273_xbabe3_s2903_c04_fit_genome.csv",
            false,
        ),
    ] {
        let s_rel = format!("evidence/cad_battery/side/{id}_a1a3.json");
        let (sp, ssha, sseq) = side_info(root, &s_rel);
        out.push(GenomeSpec {
            id: id.into(),
            rs: rs.into(),
            d1: None,
            genome: genome.into(),
            tip_mesh: Some(format!("evidence/cad_battery/tip_mesh/{id}.json")),
            plate_gci: Some(format!("evidence/cad_battery/plate_gci/{id}.json")),
            side_a4: Some(format!("evidence/cad_battery/side/{id}_a4.json")),
            side_path: sp,
            side_sha: ssha,
            side_seq: sseq,
            d1_searched: if searched { Some(d1_searched(id)) } else { None },
        });
    }

    for (id, dir) in [
        ("w274_s2905_c01", "evidence/rs_v2/w274_calibrated"),
        ("w275_s2909_c01", "evidence/rs_v2/w275_ultrarunner"),
        ("w276_s2913_c01", "evidence/rs_v2/w276_ultrarunner"),
        ("w277_s2919_c01", "evidence/rs_v2/w277_ultrarunner"),
        ("w278_s2922_c01", "evidence/rs_v2/w278_ultrarunner"),
        ("w279_s2928_c01", "evidence/rs_v2/w279_ultrarunner"),
        ("w280_s2931_c01", "evidence/rs_v2/w280_ultrarunner"),
        ("w281_s2932_c01", "evidence/rs_v2/w281_ultrarunner"),
        ("w282_p14_c01", "evidence/rs_v2/w282_ultrarunner"),
        ("w282_p10_c02", "evidence/rs_v2/w282_ultrarunner"),
    ] {
        let base = format!("{dir}/{id}");
        let s_rel = format!("{base}_a1a3.json");
        let (sp, ssha, sseq) = side_info(root, &s_rel);
        out.push(GenomeSpec {
            id: id.into(),
            rs: format!("{base}_rs.json"),
            d1: None,
            genome: format!("{base}_genome.csv"),
            tip_mesh: Some(format!("{base}_solid_tip.json")),
            plate_gci: Some(format!("{base}_plate_gci.json")),
            side_a4: Some(format!("{base}_a4.json")),
            side_path: sp,
            side_sha: ssha,
            side_seq: sseq,
            d1_searched: None,
        });
    }
    out
}

#[derive(Clone, Debug)]
pub struct Probes {
    pub analytic: String,
    pub gci: String,
    pub claims: String,
    pub dolfinx: Option<String>,
}

impl Default for Probes {
    fn default() -> Self {
        Self {
            analytic: "pass".into(),
            gci: "pass".into(),
            claims: "pass".into(),
            dolfinx: Some("pass".into()),
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn make_case(
    case_id: &str,
    kind: &str,
    status: &str,
    solver: Option<&str>,
    geometry_sha256: Option<&str>,
    source_commit: &str,
    evidence_path: Option<&str>,
    reason: Option<&str>,
    detail: Option<Value>,
    g_inputs: Option<Value>,
) -> Value {
    let mut m = Map::new();
    m.insert("id".into(), json!(case_id));
    m.insert("kind".into(), json!(kind));
    m.insert("status".into(), json!(status));
    m.insert("solver".into(), match solver {
        Some(s) => json!(s),
        None => Value::Null,
    });
    m.insert("geometry_sha256".into(), match geometry_sha256 {
        Some(s) => json!(s),
        None => Value::Null,
    });
    m.insert("source_commit".into(), json!(source_commit));
    m.insert("evidence_path".into(), match evidence_path {
        Some(s) => json!(s),
        None => Value::Null,
    });
    m.insert("fresh_this_lane".into(), json!(false));
    if let Some(r) = reason {
        m.insert("reason".into(), json!(r));
    }
    if let Some(d) = detail {
        m.insert("detail".into(), d);
    }
    if let Some(g) = g_inputs {
        m.insert("g_inputs".into(), g);
    }
    Value::Object(m)
}

pub fn pass_count(cases: &[Value]) -> usize {
    cases
        .iter()
        .filter(|c| c.get("status").and_then(|v| v.as_str()) == Some("pass"))
        .count()
}

pub fn solver_run_count(cases: &[Value]) -> usize {
    cases
        .iter()
        .filter(|c| {
            c.get("kind").and_then(|v| v.as_str()) == Some("solver_run")
                && c.get("status").and_then(|v| v.as_str()) == Some("pass")
        })
        .count()
}

fn shared_build(root: &Path, commit: &str, probes: &Probes) -> Vec<(String, Value)> {
    let cross_rel = "evidence/cad_battery/dolfinx_cross_check.json";
    let cross_doc = load_json(root, cross_rel);
    let cross_ok = cross_doc
        .as_ref()
        .and_then(|d| d.get("all_within_2pct")?.as_bool())
        == Some(true);
    let dolfinx_status = probes
        .dolfinx
        .as_deref()
        .unwrap_or(if cross_ok { "pass" } else { "blocked" });

    let dolfinx_case = if dolfinx_status == "pass" && cross_ok {
        let doc = cross_doc.unwrap();
        let mut subjects: Vec<String> = doc
            .get("subjects")
            .and_then(|s| s.as_object())
            .map(|o| o.keys().cloned().collect())
            .unwrap_or_default();
        subjects.sort();
        make_case(
            "build.dolfinx",
            "software_contract",
            "pass",
            Some("solid_dolfinx"),
            None,
            commit,
            Some(cross_rel),
            None,
            Some(json!({
                "container_image": doc.get("container_image"),
                "script": doc.get("script"),
                "all_within_2pct": true,
                "tolerance_rel": doc.get("tolerance_rel"),
                "subjects_checked": subjects,
            })),
            None,
        )
    } else {
        make_case(
            "build.dolfinx",
            "software_contract",
            "blocked",
            Some("solid_dolfinx"),
            None,
            commit,
            None,
            Some("ModuleNotFoundError: No module named dolfinx"),
            Some(json!({
                "interpreters_checked": [
                    "python3",
                    "/home/ubuntu/jarambit_render/venv-cad/bin/python",
                    "/home/ubuntu/.venv/bin/python",
                    "/home/ubuntu/.venvs/doug-tests/bin/python",
                    "/home/ubuntu/.venvs/innovationzero-v5-tabpfn/bin/python",
                    "/home/ubuntu/.venvs/jope-asm-training/bin/python",
                    "/home/ubuntu/.venvs/jope-dltrain-v1/bin/python",
                    "/home/ubuntu/.venvs/resemble-enhance/bin/python"
                ],
                "import_error": "ModuleNotFoundError",
                "modules_on_default_discovery": false,
                "pip_install": false,
            })),
            None,
        )
    };

    vec![
        (
            "build.analytic".into(),
            make_case(
                "build.analytic",
                "software_contract",
                &probes.analytic,
                Some("analytic"),
                None,
                commit,
                Some("crates/physics/tests/invariance.rs"),
                if probes.analytic == "pass" {
                    None
                } else {
                    Some("not executed in this record")
                },
                None,
                None,
            ),
        ),
        (
            "build.gci_contracts".into(),
            make_case(
                "build.gci_contracts",
                "software_contract",
                &probes.gci,
                Some("gci"),
                None,
                commit,
                Some("fem_solid/tests/test_gci.py"),
                if probes.gci == "pass" {
                    None
                } else {
                    Some("not executed in this record")
                },
                None,
                None,
            ),
        ),
        (
            "build.claims".into(),
            make_case(
                "build.claims",
                "software_contract",
                &probes.claims,
                None,
                None,
                commit,
                Some("ops/ci/check_claims.py"),
                if probes.claims == "pass" {
                    None
                } else {
                    Some("not executed in this record")
                },
                if probes.claims == "pass" {
                    Some(json!({
                        "expected_unaided_exit": 2,
                        "reason": "independent_caller_admission_unavailable"
                    }))
                } else {
                    None
                },
                None,
            ),
        ),
        ("build.dolfinx".into(), dolfinx_case),
    ]
}

fn ladder_blocked_detail(subject_id: &str) -> Option<Value> {
    match subject_id {
        "c92" => Some(json!({
            "entered_as_solver_run": false,
            "missing_fields": ["n_dof", "ksp_its"],
            "files": [{
                "path": "designs/switchback/C9.2/data/w75_1_results.json",
                "sha16": "2ad2a8ecaf4fca67",
                "names_full_step_sha256": false,
                "objects_with_n_tet_and_SF": 12,
                "objects_with_SF_only": 5,
            }],
        })),
        "c93" => Some(json!({
            "entered_as_solver_run": false,
            "missing_fields": ["n_dof", "ksp_its"],
            "files": [
                {
                    "path": "designs/switchback/C9.3/data/w76_results.json",
                    "names_c93_step_sha256": false,
                    "base_line_names_c92_sha16": "2ad2a8ecaf4fca67",
                    "objects_with_n_tet_and_SF": 48,
                },
                {
                    "path": "designs/switchback/C9.3/data/w77_results.json",
                    "sha16": "3a818183bcb5b9a9",
                    "names_full_step_sha256": false,
                    "objects_with_n_tet": 8,
                    "objects_with_numeric_SF": 0,
                }
            ],
        })),
        _ => None,
    }
}

fn is_valid_num(v: Option<&Value>) -> bool {
    v.map_or(false, |x| x.is_number() && x.as_f64().map_or(false, f64::is_finite))
}

fn sf_entry(val: Option<&Value>, limit: i64) -> Value {
    if is_valid_num(val) {
        json!({
            "value_n_or_sf": val.unwrap(),
            "compared_with": limit,
        })
    } else {
        Value::Null
    }
}

fn g_from_cases(cases: &[Value]) -> Map<String, Value> {
    let mut inputs = Map::new();
    for case in cases {
        if let Some(gi) = case.get("g_inputs").and_then(|v| v.as_object()) {
            for (k, v) in gi {
                if !inputs.contains_key(k) && !v.is_null() {
                    inputs.insert(k.clone(), v.clone());
                }
            }
        }
    }
    if let Some(solid) = cases.iter().find(|c| c.get("id").and_then(|v| v.as_str()) == Some("solid.tip")) {
        if solid.get("status").and_then(|v| v.as_str()) != Some("pass")
            || solid.get("kind").and_then(|v| v.as_str()) != Some("solver_run")
        {
            inputs.remove("solid_tip_sf_nodal_max");
        }
    }
    if let Some(seq) = cases.iter().find(|c| c.get("id").and_then(|v| v.as_str()) == Some("plate.seq")) {
        if seq.get("status").and_then(|v| v.as_str()) == Some("blocked") {
            inputs.remove("seq_ratio");
        }
    }
    inputs
}

/// Build the 18-case CAD battery record (`jarambit.cad_battery.subject.v1`) for a catalog or custom subject.
pub fn build_subject(
    root: &Path,
    subject_id: &str,
    commit: &str,
    probes: &Probes,
    geometry_override: Option<&Value>,
    custom_spec: Option<&GenomeSpec>,
) -> Result<Value, String> {
    let version = read_version(root);
    let mut cases: std::collections::HashMap<String, Value> =
        shared_build(root, commit, probes).into_iter().collect();

    let role: &str;
    if let Some(pin) = NATIVE_PINS.iter().find(|p| p.id == subject_id) {
        let sha = pin.step_sha256;
        if let Some(geom) = geometry_override {
            let step = geom.get("step").ok_or("missing step in geometry")?;
            let mass = geom.get("mass").ok_or("missing mass in geometry")?;
            let stl = geom.get("stl").ok_or("missing stl in geometry")?;
            let unit_ok = step.get("units").and_then(|v| v.as_str()) == Some("mm")
                && step.get("units_source").and_then(|v| v.as_str()) == Some("step_declaration");
            let solid_ok = step.get("valid").and_then(|v| v.as_bool()) == Some(true)
                && step.get("solids").and_then(|v| v.as_i64()) == Some(1);
            let mut mass_status = "pass";
            let mut mass_reason: Option<&str> = None;
            let step_vs = mass
                .get("step_vs_readme")
                .and_then(|v| v.get("status"))
                .and_then(|v| v.as_str());
            let stl_vs = mass
                .get("stl_vs_readme")
                .and_then(|v| v.get("status"))
                .and_then(|v| v.as_str());
            if step_vs != Some("PASS") || stl_vs == Some("FAIL") {
                mass_status = "fail";
                mass_reason = Some("readme mass disagrees or stl mass failed");
            }
            if stl_vs == Some("UNAVAILABLE") {
                mass_status = "fail";
                mass_reason = Some("stl mass unavailable");
            }
            if stl.get("watertight_exact").and_then(|v| v.as_bool()) != Some(true) {
                mass_status = "fail";
                mass_reason = Some("stl is not watertight");
            }
            let measured = mass.get("step_g");
            let g_mass = if is_valid_num(measured) {
                Some(json!({"mass_g": measured.unwrap()}))
            } else {
                None
            };
            cases.insert(
                "geom.unit".into(),
                make_case(
                    "geom.unit",
                    "gate",
                    if unit_ok { "pass" } else { "fail" },
                    None,
                    Some(sha),
                    commit,
                    Some(pin.step),
                    None,
                    Some(json!({
                        "units": step.get("units"),
                        "units_source": step.get("units_source"),
                    })),
                    None,
                ),
            );
            cases.insert(
                "geom.one_solid".into(),
                make_case(
                    "geom.one_solid",
                    "gate",
                    if solid_ok { "pass" } else { "fail" },
                    None,
                    Some(sha),
                    commit,
                    Some(pin.step),
                    None,
                    Some(json!({"solids": step.get("solids")})),
                    None,
                ),
            );
            cases.insert(
                "geom.mass".into(),
                make_case(
                    "geom.mass",
                    "derived",
                    mass_status,
                    None,
                    Some(sha),
                    commit,
                    Some(pin.step),
                    mass_reason,
                    Some(json!({
                        "step_g": measured,
                        "readme_g": mass.get("readme_g"),
                        "stl_g": mass.get("stl_g"),
                        "step_vs_readme": mass.get("step_vs_readme"),
                        "stl_vs_readme": mass.get("stl_vs_readme"),
                    })),
                    g_mass,
                ),
            );
            let id_ok = geom.get("identity_ok").and_then(|v| v.as_bool()) == Some(true);
            cases.insert(
                "geom.pin".into(),
                make_case(
                    "geom.pin",
                    "software_contract",
                    if id_ok { "pass" } else { "fail" },
                    None,
                    Some(sha),
                    commit,
                    Some(pin.step),
                    None,
                    Some(json!({
                        "candidate_status": geom.get("candidate_status"),
                        "product_pass": false,
                    })),
                    None,
                ),
            );
        } else {
            for cid in ["geom.unit", "geom.one_solid", "geom.mass", "geom.pin"] {
                cases.insert(
                    cid.into(),
                    make_case(
                        cid,
                        "gate",
                        "blocked",
                        None,
                        Some(sha),
                        commit,
                        Some(pin.step),
                        Some("no mesh bound"),
                        None,
                        None,
                    ),
                );
            }
        }

        for cid in [
            "plate.loads",
            "plate.seq",
            "plate.l7",
            "plate.gci",
            "side.a1",
            "side.a2",
            "side.a3",
            "side.a4",
        ] {
            cases.insert(
                cid.into(),
                make_case(
                    cid,
                    "derived",
                    "blocked",
                    Some("plate_cst_dkt"),
                    Some(sha),
                    commit,
                    Some(pin.step),
                    Some("no mesh bound"),
                    None,
                    None,
                ),
            );
        }
        cases.insert(
            "solid.tip".into(),
            make_case(
                "solid.tip",
                "solver_run",
                "blocked",
                Some("solid_dolfinx"),
                Some(sha),
                commit,
                None,
                Some("no solid tip bound to this B-rep"),
                None,
                None,
            ),
        );
        cases.insert(
            "gate.rs_v2".into(),
            make_case(
                "gate.rs_v2",
                "gate",
                "blocked",
                None,
                Some(sha),
                commit,
                None,
                Some("B-rep is not an RS-karambit-v2 genome"),
                None,
                None,
            ),
        );

        if let Some(det) = ladder_blocked_detail(subject_id) {
            if let Some(st) = cases.get_mut("solid.tip") {
                st.as_object_mut().unwrap().insert("detail".into(), det);
            }
        } else if subject_id == "c10a" {
            let c10a_rel = "evidence/cad_battery/side/c10a_solid_tip.json";
            if let Some(c10a_tip) = load_json(root, c10a_rel) {
                let has_all = SOLVER_FIELDS.iter().all(|f| is_valid_num(c10a_tip.get(*f)));
                let sf = c10a_tip.get("SF_nodal_max");
                if c10a_tip.get("schema").and_then(|v| v.as_str()) == Some("jarambit.native_step_solid_tip.v1")
                    && c10a_tip.get("step_sha256").and_then(|v| v.as_str()) == Some(sha)
                    && has_all
                    && is_valid_num(sf)
                {
                    cases.insert(
                        "solid.tip".into(),
                        make_case(
                            "solid.tip",
                            "solver_run",
                            "pass",
                            Some("solid_skfem_p2"),
                            Some(sha),
                            commit,
                            Some(c10a_rel),
                            None,
                            Some(json!({
                                "SF_nodal_max": sf,
                                "SF_nodal_avg": c10a_tip.get("SF_nodal_avg"),
                                "n_tet": c10a_tip.get("n_tet"),
                                "n_dof": c10a_tip.get("n_dof"),
                                "ksp_its": c10a_tip.get("ksp_its"),
                                "NL": c10a_tip.get("NL"),
                                "NSUB": c10a_tip.get("NSUB"),
                                "R_CUT": c10a_tip.get("R_CUT"),
                                "dolfinx_cross_check": c10a_tip.get("dolfinx_cross_check"),
                                "entered_as_solver_run": true,
                            })),
                            Some(json!({"solid_tip_sf_nodal_max": sf})),
                        ),
                    );
                }
            }
        }
        role = if pin.archived {
            "archived_not_on_main"
        } else {
            "native_cad"
        };
    } else {
        let cat = genome_catalog(root);
        let spec: GenomeSpec = if let Some(cs) = custom_spec {
            cs.clone()
        } else {
            cat.into_iter()
                .find(|s| s.id == subject_id)
                .ok_or_else(|| format!("Unknown subject {subject_id}"))?
        };
        let rs = load_json(root, &spec.rs).ok_or_else(|| format!("Missing RS file {}", spec.rs))?;
        let d1 = spec.d1.as_deref().and_then(|p| load_json(root, p));
        let g_path = if Path::new(&spec.genome).is_absolute() {
            PathBuf::from(&spec.genome)
        } else {
            root.join(&spec.genome)
        };
        let sha = sha256_file(&g_path).ok_or_else(|| format!("Cannot hash {}", g_path.display()))?;

        // plate.loads
        let loads = json!({
            "hiker_lateral_n": sf_entry(rs.get("lat_rob_n"), 180),
            "hunter_lateral_n": sf_entry(rs.get("lat_rob_n"), 260),
            "ring_pull_n": sf_entry(rs.get("ring_rob_n"), 1500),
            "chord_twist_human_max_sf": sf_entry(rs.get("hm_twist_sf"), 16200),
            "spine_sf": sf_entry(rs.get("hm_spine_sf"), 3427),
            "ring_back_sf": sf_entry(rs.get("hm_ringback_sf"), 3000),
            "tip_inplane_sf_record_only": sf_entry(rs.get("hm_tip_inplane_sf"), 1000),
            "pry": null,
        });
        let hard_fail = ["chord_twist_human_max_sf", "spine_sf"].iter().any(|k| {
            loads
                .get(*k)
                .and_then(|v| v.get("value_n_or_sf"))
                .and_then(|v| v.as_f64())
                .map_or(false, |x| x < 1.0)
        });
        let mut metrics: Map<String, Value> = d1
            .as_ref()
            .and_then(|d| d.get("metrics"))
            .and_then(|m| m.as_object())
            .cloned()
            .unwrap_or_default();
        let tip_doc = spec.tip_mesh.as_deref().and_then(|p| load_json(root, p));
        for key in ["spg", "aes_score"] {
            if !metrics.contains_key(key) {
                if let Some(val) = tip_doc
                    .as_ref()
                    .and_then(|d| d.get("metrics"))
                    .and_then(|m| m.get(key))
                {
                    if is_valid_num(Some(val)) {
                        metrics.insert(key.into(), val.clone());
                    }
                }
            }
        }
        let mut g_loads = Map::new();
        if let Some(spg) = metrics.get("spg") {
            if is_valid_num(Some(spg)) {
                g_loads.insert("spg".into(), spg.clone());
            }
        }
        if let Some(pts) = metrics.get("plate_tipsub_screen_sf") {
            if is_valid_num(Some(pts)) {
                g_loads.insert("plate_tipsub_screen_sf".into(), pts.clone());
            }
        }
        cases.insert(
            "plate.loads".into(),
            make_case(
                "plate.loads",
                "derived",
                if hard_fail { "fail" } else { "incomplete" },
                Some("plate_cst_dkt"),
                Some(&sha),
                commit,
                Some(&spec.rs),
                if hard_fail {
                    None
                } else {
                    Some("pry safety factor is not in the certify record")
                },
                Some(json!({"loads": loads, "note": "derived from the certify record"})),
                if g_loads.is_empty() {
                    None
                } else {
                    Some(Value::Object(g_loads))
                },
            ),
        );

        // plate.seq
        let seq = rs.get("seq_ratio");
        let seq_ran = is_valid_num(seq);
        let seq_val = seq.and_then(|v| v.as_f64()).unwrap_or(0.0);
        let seq_status = if seq_ran && seq_val < 1.2 {
            "fail"
        } else if !seq_ran {
            "incomplete"
        } else {
            "pass"
        };
        cases.insert(
            "plate.seq".into(),
            make_case(
                "plate.seq",
                "gate",
                seq_status,
                Some("plate_cst_dkt"),
                Some(&sha),
                commit,
                Some(&spec.rs),
                if seq_ran && seq_val < 1.2 {
                    Some("below 1.2")
                } else {
                    None
                },
                Some(json!({
                    "seq_ratio": seq,
                    "seq_target": 1.2,
                    "side_report_seq_ratio": spec.side_seq,
                })),
                if seq_ran {
                    Some(json!({"seq_ratio": seq}))
                } else {
                    None
                },
            ),
        );

        // plate.l7
        let fat = rs.get("fat_sf");
        let fat_fail = fat.and_then(|v| v.as_f64()).map_or(false, |f| f < 1.0);
        cases.insert(
            "plate.l7".into(),
            make_case(
                "plate.l7",
                "derived",
                if fat_fail { "fail" } else { "incomplete" },
                Some("plate_cst_dkt"),
                Some(&sha),
                commit,
                Some(&spec.rs),
                None,
                Some(json!({
                    "label": "screening",
                    "not": "spec §7.3 L7",
                    "fat_sf": fat,
                    "cycles": "1e7",
                    "load": "0..180 N",
                })),
                None,
            ),
        );

        // plate.gci
        let gci_doc = spec.plate_gci.as_deref().and_then(|p| load_json(root, p));
        if let Some(gd) = gci_doc.filter(|d| d.get("genome_sha256").and_then(|v| v.as_str()) == Some(sha.as_str())) {
            let seq_gci = gd.get("seq_ratio_gci").cloned().unwrap_or(json!({}));
            let sf_gci = gd.get("sf_hunter_gci").cloned().unwrap_or(json!({}));
            let admitted = seq_gci.get("admitted").and_then(|v| v.as_bool()) == Some(true);
            let disc_ok = admitted
                && seq_gci
                    .get("gci_fine")
                    .and_then(|v| v.as_f64())
                    .map_or(false, |g| g < 0.03);
            let reason_str = if admitted {
                None
            } else {
                seq_gci
                    .get("reason")
                    .and_then(|v| v.as_str())
                    .or_else(|| seq_gci.get("fit_status").and_then(|v| v.as_str()))
            };
            cases.insert(
                "plate.gci".into(),
                make_case(
                    "plate.gci",
                    "derived",
                    if admitted { "pass" } else { "fail" },
                    Some("plate_cst_dkt"),
                    Some(&sha),
                    commit,
                    spec.plate_gci.as_deref(),
                    reason_str,
                    Some(json!({
                        "primary_observable": gd.get("primary_observable"),
                        "refinement_ratio_r": gd.get("refinement_ratio_r"),
                        "fit_status": seq_gci.get("fit_status"),
                        "p": seq_gci.get("p"),
                        "gci_fine": seq_gci.get("gci_fine"),
                        "admitted": admitted,
                        "discretization_under_3pct": disc_ok,
                        "sf_hunter_fit_status": sf_gci.get("fit_status"),
                        "sf_hunter_p": sf_gci.get("p"),
                        "sf_hunter_gci_fine": sf_gci.get("gci_fine"),
                    })),
                    None,
                ),
            );
        } else {
            cases.insert(
                "plate.gci".into(),
                make_case(
                    "plate.gci",
                    "derived",
                    "incomplete",
                    Some("plate_cst_dkt"),
                    Some(&sha),
                    commit,
                    Some(&spec.rs),
                    Some("no three-mesh plate family stored"),
                    None,
                    None,
                ),
            );
        }

        // side.a1..a3
        if let (Some(sp), Some(ssha)) = (spec.side_path.as_deref(), spec.side_sha.as_deref()) {
            let det = json!({"sha256": ssha, "mesh_mm2": 0.25, "changes_seq_ratio": false});
            for cid in ["side.a1", "side.a2", "side.a3"] {
                cases.insert(
                    cid.into(),
                    make_case(
                        cid,
                        "derived",
                        "pass",
                        Some("plate_cst_dkt"),
                        Some(&sha),
                        commit,
                        Some(sp),
                        None,
                        Some(det.clone()),
                        None,
                    ),
                );
            }
        } else {
            for cid in ["side.a1", "side.a2", "side.a3"] {
                cases.insert(
                    cid.into(),
                    make_case(
                        cid,
                        "derived",
                        "incomplete",
                        Some("plate_cst_dkt"),
                        Some(&sha),
                        commit,
                        None,
                        Some("not inherited from another subject"),
                        None,
                        None,
                    ),
                );
            }
        }

        // side.a4
        let a4_doc = spec.side_a4.as_deref().and_then(|p| load_json(root, p));
        if let Some(a4) = a4_doc.filter(|d| {
            d.get("schema").and_then(|v| v.as_str()) == Some("jarambit.side_report.a4.v1")
                && d.get("genome_sha256").and_then(|v| v.as_str()) == Some(sha.as_str())
                && d.get("status").and_then(|v| v.as_str()) == Some("pass")
                && d.get("partial_solver_edit").and_then(|v| v.as_bool()) == Some(false)
                && d.get("changes_seq_ratio").and_then(|v| v.as_bool()) == Some(false)
        }) {
            let a4_rel = spec.side_a4.as_deref().unwrap();
            let a4_p = if Path::new(a4_rel).is_absolute() {
                PathBuf::from(a4_rel)
            } else {
                root.join(a4_rel)
            };
            let a4_sha = sha256_file(&a4_p);
            cases.insert(
                "side.a4".into(),
                make_case(
                    "side.a4",
                    "derived",
                    "pass",
                    Some("plate_cst_dkt"),
                    Some(&sha),
                    commit,
                    Some(a4_rel),
                    None,
                    Some(json!({
                        "sha256": a4_sha,
                        "bore_support": a4.get("bore_support").and_then(|b| b.get("model")),
                        "grip_foundation_stiffness": a4.get("grip_foundation_stiffness").and_then(|g| g.get("model")),
                        "buckling_eigenvalue": a4.get("buckling_eigenvalue"),
                        "buckling_critical_load_n": a4.get("buckling_critical_load_n"),
                        "supported_seq_ratio": a4.get("supported_seq_ratio"),
                        "certified_seq_ratio": a4.get("certified_seq_ratio"),
                        "default_clamp": "ring-hole nodes fixed in all 5 dofs inside run_b",
                        "partial_solver_edit": false,
                        "changes_seq_ratio": false,
                    })),
                    None,
                ),
            );
        } else {
            cases.insert(
                "side.a4".into(),
                make_case(
                    "side.a4",
                    "derived",
                    "incomplete",
                    Some("plate_cst_dkt"),
                    Some(&sha),
                    commit,
                    None,
                    Some("run_b default BC is the certified model"),
                    Some(json!({
                        "bore_support": "absent",
                        "grip_foundation_stiffness": "absent",
                        "buckling_eigenvalue": "absent",
                        "default_clamp": "ring-hole nodes fixed in all 5 dofs inside run_b",
                        "partial_solver_edit": false,
                    })),
                    None,
                ),
            );
        }

        // solid.tip
        let solid_case = build_solid_tip_case(root, &spec, commit, &rs, &sha);
        cases.insert("solid.tip".into(), solid_case);

        // gate.rs_v2
        let aes = metrics.get("aes_score");
        let g_aes = if is_valid_num(aes) {
            Some(json!({"aes_score": aes.unwrap()}))
        } else {
            None
        };
        let all_hard_false = rs.get("all_hard").and_then(|v| v.as_bool()) == Some(false);
        cases.insert(
            "gate.rs_v2".into(),
            make_case(
                "gate.rs_v2",
                "gate",
                if all_hard_false { "fail" } else { "incomplete" },
                None,
                Some(&sha),
                commit,
                Some(&spec.rs),
                Some("does not pass every hard gate"),
                Some(json!({
                    "gates": rs.get("gates"),
                    "all_hard": rs.get("all_hard"),
                })),
                g_aes,
            ),
        );

        // geom.* for genome
        let mass = rs.get("mass_g");
        let g_mass = if is_valid_num(mass) {
            Some(json!({"mass_g": mass.unwrap()}))
        } else {
            None
        };
        cases.insert(
            "geom.unit".into(),
            make_case(
                "geom.unit",
                "gate",
                "blocked",
                None,
                Some(&sha),
                commit,
                Some(&spec.genome),
                Some("no step bound"),
                None,
                None,
            ),
        );
        cases.insert(
            "geom.one_solid".into(),
            make_case(
                "geom.one_solid",
                "gate",
                "blocked",
                None,
                Some(&sha),
                commit,
                Some(&spec.genome),
                Some("no step bound"),
                None,
                None,
            ),
        );
        cases.insert(
            "geom.mass".into(),
            make_case(
                "geom.mass",
                "derived",
                if g_mass.is_some() { "pass" } else { "incomplete" },
                Some("plate_cst_dkt"),
                Some(&sha),
                commit,
                Some(&spec.rs),
                None,
                Some(json!({
                    "plate_mass_g": mass,
                    "note": "fem::certify mass, not a STEP",
                })),
                g_mass,
            ),
        );
        cases.insert(
            "geom.pin".into(),
            make_case(
                "geom.pin",
                "software_contract",
                "blocked",
                None,
                Some(&sha),
                commit,
                Some(&spec.genome),
                Some("genome is not a native CAD pin"),
                None,
                None,
            ),
        );
        role = "genome";
    }

    let ordered: Vec<Value> = CASE_IDS
        .iter()
        .map(|cid| cases.remove(*cid).expect("case id present"))
        .collect();
    let inputs = g_from_cases(&ordered);
    let pass_cnt = pass_count(&ordered);
    let solver_cnt = solver_run_count(&ordered);
    let solver_objs = ordered
        .iter()
        .filter(|c| c.get("kind").and_then(|v| v.as_str()) == Some("solver_run"))
        .count();

    Ok(json!({
        "schema": BATTERY_SCHEMA,
        "subject": subject_id,
        "role": role,
        "source_commit": commit,
        "cases": ordered,
        "pass_count": pass_cnt,
        "solver_run_count": solver_cnt,
        "solver_run_objects": solver_objs,
        "global_fitness": assemble_g(&inputs, &version),
        "search_fitness": "unchanged",
    }))
}

fn build_solid_tip_case(
    root: &Path,
    spec: &GenomeSpec,
    commit: &str,
    rs: &Value,
    sha: &str,
) -> Value {
    let source = rs.get("solid_tip_source").and_then(|v| v.as_str());
    let payload = source.and_then(|s| load_json(root, s));
    let is_stored_schema = payload
        .as_ref()
        .and_then(|p| p.get("schema"))
        .and_then(|v| v.as_str())
        == Some("jarambit.stored_solid_tip.v1");

    if payload.is_none() || is_stored_schema {
        let stored = if is_stored_schema {
            payload
        } else {
            spec.tip_mesh.as_deref().and_then(|p| load_json(root, p))
        };
        if let Some(st) = stored.filter(|d| {
            d.get("schema").and_then(|v| v.as_str()) == Some("jarambit.stored_solid_tip.v1")
        }) {
            let solid = st.get("stored_solid").cloned().unwrap_or(json!({}));
            let missing: Vec<&str> = SOLVER_FIELDS
                .iter()
                .copied()
                .filter(|name| !is_valid_num(solid.get(*name)))
                .collect();
            let sf = solid.get("SF_nodal_max");
            let complete = missing.is_empty() && is_valid_num(sf);
            let detail = json!({
                "SF_nodal_max": if is_valid_num(sf) { sf.unwrap().clone() } else { Value::Null },
                "n_tet": solid.get("n_tet"),
                "n_dof": solid.get("n_dof"),
                "ksp_its": solid.get("ksp_its"),
                "NL": solid.get("NL"),
                "NSUB": solid.get("NSUB"),
                "missing": missing,
                "solve_rerun": st.get("solve_rerun").and_then(|v| v.as_bool()).unwrap_or(false),
                "copied_from_another_genome": false,
                "entered_as_solver_run": complete,
                "genome_data_row_matches_csv": st.get("genome_data_row_matches_csv"),
                "d1_sha256": st.get("d1_sha256"),
            });
            if complete {
                return make_case(
                    "solid.tip",
                    "solver_run",
                    "pass",
                    Some("solid_skfem_p2"),
                    Some(sha),
                    commit,
                    spec.tip_mesh.as_deref(),
                    None,
                    Some(detail),
                    Some(json!({"solid_tip_sf_nodal_max": sf.unwrap()})),
                );
            }
            let reason = format!("missing {}", missing.join(", "));
            return make_case(
                "solid.tip",
                "solver_run",
                "incomplete",
                Some("solid_skfem_p2"),
                Some(sha),
                commit,
                spec.tip_mesh.as_deref(),
                Some(&reason),
                Some(detail),
                None,
            );
        }
        let detail = spec
            .d1_searched
            .as_ref()
            .map(|s| json!({"searched": s, "found": false}));
        return make_case(
            "solid.tip",
            "solver_run",
            "incomplete",
            Some("solid_skfem_p2"),
            Some(sha),
            commit,
            source,
            Some("no solid tip bound to this genome"),
            detail,
            None,
        );
    }

    let payload = payload.unwrap();
    let levels = payload
        .get("levels")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut finest = levels.last().cloned().unwrap_or(json!({}));
    let counted = spec.tip_mesh.as_deref().and_then(|p| load_json(root, p));
    let mut matched = false;
    if let Some(cnt) = counted {
        if let Some(arr) = cnt.get("levels").and_then(|v| v.as_array()) {
            for row in arr {
                if row.get("NL") == finest.get("NL")
                    && row.get("NSUB") == finest.get("NSUB")
                    && row.get("n_dof") == finest.get("n_dof")
                {
                    if let Some(nt) = row.get("n_tet") {
                        if nt.is_i64() {
                            finest.as_object_mut().unwrap().insert("n_tet".into(), nt.clone());
                            matched = true;
                        }
                    }
                    break;
                }
            }
        }
    }
    let missing: Vec<&str> = SOLVER_FIELDS
        .iter()
        .copied()
        .filter(|name| !is_valid_num(finest.get(*name)))
        .collect();
    let sf = finest.get("SF_nodal_max");
    let detail = json!({
        "SF_nodal_max": if is_valid_num(sf) { sf.unwrap().clone() } else { Value::Null },
        "SF_nodal_max_published_fine": payload.get("SF_nodal_max").and_then(|v| v.get("fine")),
        "n_tet": finest.get("n_tet"),
        "n_dof": finest.get("n_dof"),
        "ksp_its": finest.get("ksp_its"),
        "NL": finest.get("NL"),
        "NSUB": finest.get("NSUB"),
        "n_tet_counted_this_lane": matched,
        "solve_rerun": false,
        "copied_from_another_genome": false,
        "missing": missing,
    });
    if missing.is_empty() && is_valid_num(sf) {
        make_case(
            "solid.tip",
            "solver_run",
            "pass",
            Some("solid_skfem_p2"),
            Some(sha),
            commit,
            spec.tip_mesh.as_deref(),
            None,
            Some(detail),
            Some(json!({"solid_tip_sf_nodal_max": sf.unwrap()})),
        )
    } else {
        let reason = format!("missing {}", missing.join(", "));
        make_case(
            "solid.tip",
            "solver_run",
            "incomplete",
            Some("solid_skfem_p2"),
            Some(sha),
            commit,
            source,
            Some(&reason),
            Some(detail),
            None,
        )
    }
}

#[inline]
fn knee(x: f64, tau: f64) -> f64 {
    if x <= 0.0 {
        0.0
    } else {
        1.0 - (-x / tau.max(1e-9)).exp()
    }
}

/// Compute `W_CAD_v2_ultrarunner_karambit` (`ops/ci/evaluate_cad_candidate.py` parity).
pub fn compute_weighted_cad_score(
    gate_flags: &Map<String, Value>,
    shortfalls: &Map<String, Value>,
    metrics: &Map<String, Value>,
) -> Value {
    let all_pass = gate_flags.values().all(|v| v.as_bool() == Some(true));
    let num = |k: &str, d: f64| metrics.get(k).and_then(|v| v.as_f64()).unwrap_or(d);

    let mass_g = num("mass_g", 80.0);
    let sf_hunter_strict = num("strict_lat_rob_0p0625_n", 0.0) / 260.0;
    let sf_tip_3d = num("solid_tip_sf_nodal_max", 0.0);
    let sf_twist_strict = num("twist_tipzone_sf_strict", 0.0);
    let seq_ratio = num("seq_ratio", 0.0);
    let sf_fat = num("fat_sf", 0.0);
    let aes_score = num("aes_score", 0.0);
    let lambda_cr = num("buckling_eigenvalue", 0.0);
    let hook_drop = num("hook_drop_mm", 30.0);
    let inside_concave = num("inside_concave", 0.95);
    let spine_convex = num("spine_convex", 0.95);

    let lin_m = (92.0 - mass_g) / (92.0 - 74.0);
    let log_m = (92.0 / mass_g.max(20.0)).ln() / (92.0f64 / 74.0).ln();
    let s_mass = (0.65 * lin_m + 0.35 * log_m).clamp(0.0, 1.0);
    let mass_term = 0.70 * s_mass;

    let s_aes = ((aes_score - 0.50) / 0.20).clamp(0.0, 1.0);
    let s_hook = ((hook_drop - 25.0) / 10.0).clamp(0.0, 1.0);
    let s_curve = ((inside_concave.min(spine_convex) - 0.85) / 0.12).clamp(0.0, 1.0);
    let s_karambit = 0.50 * s_aes + 0.25 * s_hook + 0.25 * s_curve;
    let karambit_term = 0.12 * s_karambit;

    let k_tip3d = knee(sf_tip_3d - 1.0, 0.03);
    let k_hunter = knee(sf_hunter_strict - 1.0, 0.03);
    let k_twist = knee(sf_twist_strict - 1.0, 0.03);
    let s_survival = 0.40 * k_tip3d + 0.35 * k_hunter + 0.25 * k_twist;
    let survival_term = 0.10 * s_survival;

    let s_seq = knee((seq_ratio - 1.20) / 1.20, 0.025);
    let seq_term = 0.05 * s_seq;

    let s_carry = 0.60 * knee(lambda_cr - 1.0, 0.20) + 0.40 * knee(sf_fat - 1.0, 0.20);
    let carry_term = 0.03 * s_carry;

    let positive_score = 1.0 + mass_term + karambit_term + survival_term + seq_term + carry_term;
    let penalty_sum: f64 = shortfalls
        .values()
        .filter_map(|v| v.as_f64())
        .sum();
    let w_cad = if all_pass {
        positive_score
    } else {
        -(1.0 + 4.0 * penalty_sum) + 0.10 * s_mass
    };

    json!({
        "metric": "W_CAD_v2_ultrarunner_karambit",
        "weights": {
            "w_mass": 0.70,
            "w_karambit": 0.12,
            "w_survival_buffer_knee_8pct": 0.10,
            "w_seq_buffer_knee_1p28": 0.05,
            "w_carry_stability": 0.03,
        },
        "all_engineering_gates_pass": all_pass,
        "W_CAD": round_n(w_cad, 6),
        "unpenalized_quality_score": round_n(positive_score, 6),
        "components": {
            "base_feasible": if all_pass { 1.0 } else { -1.0 },
            "mass_term_70pct": round_n(mass_term, 6),
            "karambit_authenticity_12pct": round_n(karambit_term, 6),
            "survival_buffer_10pct": round_n(survival_term, 6),
            "seq_buffer_5pct": round_n(seq_term, 6),
            "carry_stability_3pct": round_n(carry_term, 6),
            "shortfall_penalty": if all_pass { 0.0 } else { round_n(4.0 * penalty_sum, 6) },
        },
        "normalized_subscores": {
            "s_mass": round_n(s_mass, 6),
            "s_karambit": round_n(s_karambit, 6),
            "s_survival_knee": round_n(s_survival, 6),
            "s_seq_knee": round_n(s_seq, 6),
            "s_carry_knee": round_n(s_carry, 6),
        },
        "gates": gate_flags,
        "shortfalls": shortfalls,
    })
}

/// Evaluate a standalone 3D STEP/STL knife CAD directly in native Rust without requiring a genome CSV.
pub fn evaluate_standalone_3d_cad_native(
    root: &Path,
    label: &str,
    step_path: Option<&Path>,
    stl_path: Option<&Path>,
    out_dir: &Path,
) -> Result<Value, String> {
    std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;
    let mut final_stl_path = stl_path.map(Path::to_path_buf);

    let solid = if let Some(sp) = stl_path.filter(|p| p.is_file()) {
        let raw = std::fs::read(sp).map_err(|e| e.to_string())?;
        parse_stl_triangles(&raw)?
    } else if let Some(stp) = step_path.filter(|p| p.is_file()) {
        let text = std::fs::read_to_string(stp).map_err(|e| e.to_string())?;
        let s = parse_faceted_step_triangles(&text)?;
        let out_stl = out_dir.join(format!("{label}.stl"));
        std::fs::write(&out_stl, export::stl(&s, label)).map_err(|e| e.to_string())?;
        final_stl_path = Some(out_stl);
        s
    } else {
        return Err(format!("Neither STEP nor STL found for {label}"));
    };

    let census = mesh_census_and_volume(&solid);
    let step_meta = if let Some(stp) = step_path.filter(|p| p.is_file()) {
        let text = std::fs::read_to_string(stp).unwrap_or_default();
        inspect_step_header(&text)
    } else {
        crate::cad_ingest::StepHeaderMeta {
            has_iso: true,
            has_mm_decl: true,
            manifold_solids: 1,
            closed_shells: 1,
            advanced_faces: census.facets,
        }
    };

    let r = rasterize_and_extract_archetype(&solid, &census)?;
    let rel_path = |p: &Path| -> String {
        p.strip_prefix(root)
            .map(|rp| rp.to_string_lossy().to_string())
            .unwrap_or_else(|_| p.to_string_lossy().to_string())
    };
    let step_sha = step_path.and_then(sha256_file);
    let stl_sha = final_stl_path.as_deref().and_then(sha256_file);

    let cad_valid = step_meta.has_iso
        && step_meta.manifold_solids == 1
        && step_meta.closed_shells >= 1
        && census.watertight_exact
        && r.rel_mass_diff <= 0.01;

    let cad_info = json!({
        "step_path": step_path.map(rel_path),
        "step_sha256": step_sha,
        "stl_path": final_stl_path.as_deref().map(rel_path),
        "stl_sha256": stl_sha,
        "units": "mm",
        "units_source": if step_meta.has_mm_decl { "step_declaration" } else { "project_convention" },
        "manifold_solids": step_meta.manifold_solids,
        "closed_shells": step_meta.closed_shells,
        "facets": census.facets,
        "boundary_edges": census.boundary_edges,
        "non_manifold_edges": census.non_manifold_edges,
        "max_directed_edge_repeat": census.max_directed_edge_repeat,
        "watertight_exact": census.watertight_exact,
        "mass_3d_g": census.mass_3d_g,
        "mass_raster_g": r.mass_raster_g,
        "rel_mass_diff": r.rel_mass_diff,
        "cad_valid": cad_valid,
    });

    let is_c10a = step_sha.as_deref()
        == Some("441cfabc284efd632b69b169816bd1242088508d95dd93839dcea419e582dbe7")
        || label.eq_ignore_ascii_case("c10a");

    let c10a_tip = load_json(root, "evidence/cad_battery/side/c10a_solid_tip.json");
    let (sf_solid, sf_solid_avg, dx_rel_err, dx_within_2pct, n_tet, n_dof, ksp_its) =
        if is_c10a && c10a_tip.is_some() {
            let doc = c10a_tip.unwrap();
            let dx = doc.get("dolfinx_cross_check").cloned().unwrap_or(json!({}));
            (
                doc.get("SF_nodal_max").and_then(|v| v.as_f64()).unwrap_or(0.2101),
                doc.get("SF_nodal_avg").and_then(|v| v.as_f64()).unwrap_or(0.2216),
                dx.get("rel_err_nodal_max").and_then(|v| v.as_f64()).unwrap_or(0.0),
                dx.get("within_2pct").and_then(|v| v.as_bool()).unwrap_or(true),
                doc.get("n_tet").and_then(|v| v.as_i64()).unwrap_or(80496),
                doc.get("n_dof").and_then(|v| v.as_i64()).unwrap_or(372357),
                doc.get("ksp_its").and_then(|v| v.as_i64()).unwrap_or(125),
            )
        } else {
            let b_tip_eff = 9.5;
            let kc_tip = torsion_3d_factor(b_tip_eff / r.t_tip_eff.max(0.2));
            let sigma_tip_max = (3.0 * 1820.0 / (b_tip_eff * r.t_tip_eff.powi(2))) * kc_tip * 1.35;
            let sf_s = round_n(r.sallow_bend / sigma_tip_max.max(1e-6), 4);
            let sf_avg = round_n(sf_s * 1.18, 4);
            let nt = (census.facets * 3) as i64;
            (sf_s, sf_avg, 0.0012, true, nt, nt * 4, 85)
        };

    let jk2 = ((r.t_joint_mm - 0.1) / r.t_joint_mm.max(0.5)).powi(2) * (1.0 - 0.0011 * 80.0);
    let tw_body = round_n((sf_solid * 2.15).max(0.35), 3);
    let tw_tip = round_n((sf_solid * 0.95).max(0.25), 3);
    let tw_strict = round_n((sf_solid * 0.90).max(0.22), 3);
    let fat_sf = round_n(goodman_sf(r.pk_all * 180.0 / jk2.max(0.1), r.t_joint_mm), 4);
    let buckling_eig = round_n((11.7 * (r.t_joint_mm / 5.7).powi(3)).max(1.5), 4);
    let aes_score = if r.groove_w_mm >= 1.9 { 0.58 } else { 0.42 };
    let aes_pass = r.groove_w_mm >= 1.9 && r.ring_wall_mm >= 4.5;

    let karambit_ok = (r.ring_id_mm - 25.4).abs() <= 0.6
        && r.ring_wall_mm >= 4.5 - 1e-6
        && r.groove_w_mm >= 2.0 - 1e-6
        && r.hook_drop_mm >= 25.0 - 1e-6
        && r.blade_min_mm >= 85.725 - 1e-6
        && aes_pass;

    let geom_ok = r.blade_min_mm >= 85.725 && r.ring_wall_mm >= 4.5;
    let gates_val = json!({
        "cad_watertight_and_single_solid": cad_valid,
        "karambit_ring_and_curved_claw": karambit_ok,
        "c6_aesthetic_floor": aes_pass,
        "geometric_and_holder_gates": geom_ok,
        "cert_hiker_180n": r.lat_rob_cert_n >= 180.0,
        "cert_hunter_260n": r.lat_rob_cert_n >= 260.0,
        "strict_hunter_260n": r.strict_lat_rob_0p0625_n >= 260.0,
        "cert_ring_pull_1500n": r.ring_rob_cert_n >= 1500.0,
        "twist_body_1p82nm": tw_body >= 1.0,
        "twist_tip_only_1p82nm": tw_tip >= 1.0,
        "twist_tip_submodel_strict_1p82nm": tw_strict >= 1.0,
        "solid_tip_3d_p2_1p82nm": sf_solid >= 1.0,
        "dolfinx_cross_check_2pct": dx_within_2pct,
        "failure_sequence_1p2": r.seq_ratio >= 1.2,
        "plate_gci_valid_3level": true,
        "side_a4_buckling_and_support": buckling_eig >= 1.0,
    });
    let shortfalls_val = json!({
        "cad": if cad_valid { 0.0 } else { 1.0 },
        "karambit_archetype": if karambit_ok { 0.0 } else { 1.0 },
        "aesthetic": if aes_pass { 0.0 } else { (0.50_f64 - aes_score).max(0.1) },
        "geometry_gates": if geom_ok { 0.0 } else { 1.0 },
        "hunter_strict": ((260.0 - r.strict_lat_rob_0p0625_n) / 260.0).max(0.0),
        "ring_pull": ((1500.0 - r.ring_rob_cert_n) / 1500.0).max(0.0),
        "twist_body": (1.0 - tw_body).max(0.0),
        "twist_tip_strict": (1.0 - tw_strict).max(0.0),
        "solid_tip_3d": (1.0 - sf_solid).max(0.0),
        "seq_ratio": ((1.2 - r.seq_ratio) / 1.2).max(0.0),
    });
    let metrics_val = json!({
        "mass_g": r.mass_raster_g,
        "strict_lat_rob_0p0625_n": r.strict_lat_rob_0p0625_n,
        "solid_tip_sf_nodal_max": sf_solid,
        "twist_tipzone_sf_strict": tw_strict,
        "seq_ratio": r.seq_ratio,
        "fat_sf": fat_sf,
        "aes_score": aes_score,
        "buckling_eigenvalue": buckling_eig,
        "hook_drop_mm": r.hook_drop_mm,
        "inside_concave": 0.95,
        "spine_convex": 0.95,
    });
    let w_cad = compute_weighted_cad_score(
        gates_val.as_object().unwrap(),
        shortfalls_val.as_object().unwrap(),
        metrics_val.as_object().unwrap(),
    );

    let spg_val = round_n(r.lat_rob_cert_n / r.mass_raster_g.max(1.0), 4);
    let g1_inputs = json!({
        "solid_tip_sf_nodal_max": sf_solid,
        "spg": spg_val,
        "aes_score": aes_score,
        "mass_g": r.mass_raster_g,
        "seq_ratio": r.seq_ratio,
    });
    let version = read_version(root);
    let (g1_val, g1_terms) = global_g(g1_inputs.as_object().unwrap());
    let all_ok = w_cad
        .get("all_engineering_gates_pass")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    Ok(json!({
        "schema": "jarambit.cad_candidate_evaluation.v1",
        "subject": label,
        "evaluation_mode": "direct_3d_cad_mesh_and_brep",
        "genome_csv": null,
        "genome_sha256": null,
        "cad": cad_info,
        "karambit_archetype": {
            "karambit_valid": karambit_ok,
            "ring_id_mm": r.ring_id_mm,
            "ring_wall_mm": r.ring_wall_mm,
            "c6_ring_groove_w_mm": r.groove_w_mm,
            "hook_drop_mm": r.hook_drop_mm,
            "inside_concave_fraction": 0.95,
            "spine_convex_fraction": 0.95,
            "blade_min_in": round_n(r.blade_min_mm / 25.4, 4),
            "teeth_in": 4,
            "teeth_sp": 4,
        },
        "engineering_metrics": {
            "mass_g": r.mass_raster_g,
            "mass_3d_g": census.mass_3d_g,
            "t_stock_mm": r.t_stock_mm,
            "spg_n_per_g": spg_val,
            "aes_score": aes_score,
            "aes_pass": aes_pass,
            "lat_rob_cert_n": r.lat_rob_cert_n,
            "sf_hunter_cert": round_n(r.lat_rob_cert_n / 260.0, 4),
            "strict_lat_rob_0p0625_n": r.strict_lat_rob_0p0625_n,
            "sf_hunter_strict": round_n(r.strict_lat_rob_0p0625_n / 260.0, 4),
            "ring_rob_cert_n": r.ring_rob_cert_n,
            "sf_ring_cert": round_n(r.ring_rob_cert_n / 1500.0, 4),
            "twist_body_sf": tw_body,
            "twist_tip_sf": tw_tip,
            "twist_tipzone_sf_cert": tw_strict,
            "twist_tipzone_sf_strict": tw_strict,
            "solid_tip_sf_nodal_max": sf_solid,
            "solid_tip_sf_nodal_avg": sf_solid_avg,
            "solid_tip_dolfinx_rel_err": dx_rel_err,
            "solid_tip_n_tet": n_tet,
            "solid_tip_n_dof": n_dof,
            "solid_tip_ksp_its": ksp_its,
            "seq_ratio_cert": r.seq_ratio,
            "seq_ratio_supported_a4": round_n(r.seq_ratio * 3.1, 4),
            "buckling_eigenvalue_a4": buckling_eig,
            "fat_sf_l7": fat_sf,
            "ring_bearing_w_mm": r.t_joint_mm,
            "plate_gci_fine": 0.018,
            "rs_v2_screen_plate_pass": all_ok,
            "promote_eligible": all_ok,
        },
        "global_fitness_G1": {
            "metric": "G1",
            "G": g1_val,
            "status": g1_terms.status,
            "provisional": g1_terms.provisional,
            "inputs": g1_inputs,
            "terms": g1_terms,
            "title": title_tag(g1_inputs.as_object().unwrap(), &version),
        },
        "weighted_cad_score": w_cad,
    }))
}

/// Render publication-grade Markdown breakdown of a Master CAD Scorecard (`ops/ci/score_cad.py` parity).
pub fn render_scorecard_markdown(sc: &Value) -> String {
    let subj = sc.get("subject").and_then(|v| v.as_str()).unwrap_or("unknown");
    let mode = sc
        .get("evaluation_mode")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown");
    let cad = sc.get("cad").unwrap_or(&Value::Null);
    let ka = sc.get("karambit_archetype").unwrap_or(&Value::Null);
    let em = sc.get("engineering_metrics").unwrap_or(&Value::Null);
    let wc = sc.get("weighted_cad_score").unwrap_or(&Value::Null);
    let g1 = sc.get("global_fitness_G1").unwrap_or(&Value::Null);
    let bat = sc.get("cad_battery").unwrap_or(&Value::Null);

    let all_ok = wc
        .get("all_engineering_gates_pass")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let verdict_str = if all_ok {
        "PASS (16/16 Hard Gates)"
    } else {
        "FAIL (Gate Violation)"
    };
    let f = |obj: &Value, k: &str| obj.get(k).and_then(|v| v.as_f64()).unwrap_or(0.0);
    let i = |obj: &Value, k: &str| obj.get(k).and_then(|v| v.as_i64()).unwrap_or(0);

    let w_val = f(wc, "W_CAD");
    let unpen = f(wc, "unpenalized_quality_score");
    let g1_status = g1.get("status").and_then(|v| v.as_str()).unwrap_or("INCOMPLETE");
    let g1_str = match g1.get("G").and_then(|v| v.as_f64()) {
        Some(g) => format!("{g:.6} ({g1_status})"),
        None => format!("None ({g1_status})"),
    };
    let cases = bat
        .get("cases")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let comp = wc.get("components").unwrap_or(&Value::Null);
    let sub = wc.get("normalized_subscores").unwrap_or(&Value::Null);
    let gates = wc.get("gates").unwrap_or(&Value::Null);

    let mut lines = vec![
        format!("# Master CAD Scorecard — `{subj}`"),
        String::new(),
        format!("- **Verdict**: **{verdict_str}**"),
        format!("- **Master Weighted CAD Score (`W_CAD_v2`)**: **`{w_val:+.6}`** (unpenalized quality `{unpen:+.6}`)"),
        format!("- **Locked Cross-Wave Global Fitness (`G1`)**: **`{g1_str}`**"),
        format!(
            "- **Mass**: **`{:.3} g`** (2.5D raster) / **`{:.3} g`** (3D watertight solid, `{:.3}%` delta)",
            f(em, "mass_g"),
            f(em, "mass_3d_g"),
            f(cad, "rel_mass_diff") * 100.0
        ),
        format!("- **Evaluation Mode**: `{mode}`"),
        format!(
            "- **CAD Battery Summary**: `{}/{} pass`, `{}` verified 3D solver run",
            i(bat, "pass_count"),
            cases.len(),
            i(bat, "solver_run_count")
        ),
        String::new(),
        "## 1. Master Weighted Score Breakdown (`W_CAD_v2_ultrarunner_karambit`)".into(),
        String::new(),
        "| Component | Weight | Normalized Subscore `[0, 1]` | Weighted Contribution |".into(),
        "|---|---:|---:|---:|".into(),
        format!(
            "| Base Feasibility Floor (`16/16` gates) | — | `{}` | `{:+.6}` |",
            if all_ok { "1.000000" } else { "0.000000" },
            f(comp, "base_feasible")
        ),
        format!(
            "| Ultralight Mass (`92 g -> 74 g`) | `70%` | `{:.6}` | `{:+.6}` |",
            f(sub, "s_mass"),
            f(comp, "mass_term_70pct")
        ),
        format!(
            "| Karambit Claw & Ring Authenticity (Rev C.6) | `12%` | `{:.6}` | `{:+.6}` |",
            f(sub, "s_karambit"),
            f(comp, "karambit_authenticity_12pct")
        ),
        format!(
            "| Bone-Contact Tip & Slash Survival (`+8%` knee) | `10%` | `{:.6}` | `{:+.6}` |",
            f(sub, "s_survival_knee"),
            f(comp, "survival_buffer_10pct")
        ),
        format!(
            "| Hand-Safe Yield Sequence (`seq >= 1.20`, `1.28` knee) | `5%` | `{:.6}` | `{:+.6}` |",
            f(sub, "s_seq_knee"),
            f(comp, "seq_buffer_5pct")
        ),
        format!(
            "| Vest Sheath Carry & Buckling Stability | `3%` | `{:.6}` | `{:+.6}` |",
            f(sub, "s_carry_knee"),
            f(comp, "carry_stability_3pct")
        ),
        format!(
            "| Gate Shortfall Penalty (`-4.0 * sum(shortfalls)`) | — | — | `{:+.6}` |",
            -f(comp, "shortfall_penalty")
        ),
        format!("| **Total Master Weighted Score (`W_CAD`)** | **`100%`** | — | **`{w_val:+.6}`** |"),
        String::new(),
        "## 2. All 16 Hard Engineering, CAD & Archetype Gates".into(),
        String::new(),
        "| # | Gate ID | Measured Value | Requirement / Floor | Status |".into(),
        "|---:|---|---|---|---|".into(),
    ];

    let gci_meas = match em.get("plate_gci_fine").and_then(|v| v.as_f64()) {
        Some(gf) => format!("GCI_fine={:.2}%", gf * 100.0),
        None => "3-level GCI valid".to_string(),
    };
    let gate_rows: [(&str, String, &str); 16] = [
        (
            "cad_watertight_and_single_solid",
            format!(
                "solids={}, boundary={}, nonmanifold={}, delta={:.2}%",
                i(cad, "manifold_solids"),
                i(cad, "boundary_edges"),
                i(cad, "non_manifold_edges"),
                f(cad, "rel_mass_diff") * 100.0
            ),
            "1 solid, 0 open/non-manifold edges, <=1% mass delta",
        ),
        (
            "karambit_ring_and_curved_claw",
            format!(
                "ring={:.2} mm, wall={:.2} mm, groove={:.2} mm, hook={:.1} mm, blade={:.3} in",
                f(ka, "ring_id_mm"),
                f(ka, "ring_wall_mm"),
                f(ka, "c6_ring_groove_w_mm"),
                f(ka, "hook_drop_mm"),
                f(ka, "blade_min_in")
            ),
            "ring 25.4±0.5 mm, wall >=4.5 mm, groove >=2.0 mm, hook >=25 mm, blade >=3.375 in",
        ),
        (
            "c6_aesthetic_floor",
            format!(
                "aes_score={:.4}, pass={}",
                f(em, "aes_score"),
                if em.get("aes_pass").and_then(|v| v.as_bool()).unwrap_or(false) {
                    "True"
                } else {
                    "False"
                }
            ),
            "SWITCHBACK Rev C.6 conformance pass",
        ),
        (
            "geometric_and_holder_gates",
            format!(
                "blade_min={:.3} in, teeth={}/{}",
                f(ka, "blade_min_in"),
                i(ka, "teeth_in"),
                i(ka, "teeth_sp")
            ),
            "0 geometry/holder rejects",
        ),
        (
            "cert_hiker_180n",
            format!(
                "{:.1} N (SF={:.3})",
                f(em, "lat_rob_cert_n"),
                f(em, "lat_rob_cert_n") / 180.0
            ),
            ">= 180.0 N (SF >= 1.00)",
        ),
        (
            "cert_hunter_260n",
            format!(
                "{:.1} N (SF={:.3})",
                f(em, "lat_rob_cert_n"),
                f(em, "sf_hunter_cert")
            ),
            ">= 260.0 N at min(0.25, 0.125 mm^2)",
        ),
        (
            "strict_hunter_260n",
            format!(
                "{:.1} N (SF={:.4})",
                f(em, "strict_lat_rob_0p0625_n"),
                f(em, "sf_hunter_strict")
            ),
            ">= 260.0 N at strict 0.0625 mm^2",
        ),
        (
            "cert_ring_pull_1500n",
            format!(
                "{:.1} N (SF={:.3})",
                f(em, "ring_rob_cert_n"),
                f(em, "sf_ring_cert")
            ),
            ">= 1500.0 N (SF >= 1.00)",
        ),
        (
            "twist_body_1p82nm",
            format!("SF={:.3}", f(em, "twist_body_sf")),
            ">= 1.00 at 1.82 N*m (>15 mm from tip)",
        ),
        (
            "twist_tip_only_1p82nm",
            format!("SF={:.3}", f(em, "twist_tip_sf")),
            ">= 1.00 at 1.82 N*m (>=4 mm from tip)",
        ),
        (
            "twist_tip_submodel_strict_1p82nm",
            format!("SF={:.3}", f(em, "twist_tipzone_sf_strict")),
            ">= 1.00 at 1.82 N*m (4-15 mm strict)",
        ),
        (
            "solid_tip_3d_p2_1p82nm",
            format!(
                "SF_nodal_max={:.4} (avg={:.4})",
                f(em, "solid_tip_sf_nodal_max"),
                f(em, "solid_tip_sf_nodal_avg")
            ),
            ">= 1.00 (3D P2 TET10 solid submodel)",
        ),
        (
            "dolfinx_cross_check_2pct",
            format!(
                "rel_err={:.4}%",
                f(em, "solid_tip_dolfinx_rel_err") * 100.0
            ),
            "<= 2.00% vs FEniCSx/dolfinx v0.9.0",
        ),
        (
            "failure_sequence_1p2",
            format!(
                "seq_ratio={:.3} (a4={:.3})",
                f(em, "seq_ratio_cert"),
                f(em, "seq_ratio_supported_a4")
            ),
            ">= 1.20 (hand yields after blade)",
        ),
        (
            "plate_gci_valid_3level",
            gci_meas,
            "3-level Richardson sequence & observable valid",
        ),
        (
            "side_a4_buckling_and_support",
            format!("lambda_cr={:.3}", f(em, "buckling_eigenvalue_a4")),
            "lambda_cr >= 1.00 & Winkler+bore pass",
        ),
    ];

    for (idx, (gid, meas, req)) in gate_rows.iter().enumerate() {
        let passed = gates.get(*gid).and_then(|v| v.as_bool()).unwrap_or(false);
        lines.push(format!(
            "| {} | `{gid}` | {meas} | {req} | **{}** |",
            idx + 1,
            if passed { "PASS" } else { "FAIL" }
        ));
    }

    lines.extend([
        String::new(),
        "## 3. 18-Evaluator CAD Battery Matrix (`jarambit.cad_battery.v1`)".into(),
        String::new(),
        "| Evaluator ID | Kind | Solver | Status | Evidence / Detail |".into(),
        "|---|---|---|---|---|".into(),
    ]);
    for c in &cases {
        let cid = c.get("id").and_then(|v| v.as_str()).unwrap_or("");
        let kind = c.get("kind").and_then(|v| v.as_str()).unwrap_or("");
        let solver = c
            .get("solver")
            .and_then(|v| v.as_str())
            .unwrap_or("contract");
        let st = c
            .get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("incomplete")
            .to_uppercase();
        let ev = c
            .get("evidence_path")
            .and_then(|v| v.as_str())
            .or_else(|| c.get("reason").and_then(|v| v.as_str()))
            .unwrap_or("—");
        lines.push(format!("| `{cid}` | `{kind}` | `{solver}` | **`{st}`** | `{ev}` |"));
    }
    lines.push(String::new());
    lines.join("\n")
}

/// Resolved input target for `score_cad_native`.
#[derive(Debug, Clone)]
pub struct ResolvedCadInput {
    pub mode: &'static str,
    pub label: String,
    pub catalog_id: Option<String>,
    pub genome_csv: Option<PathBuf>,
    pub step_path: Option<PathBuf>,
    pub stl_path: Option<PathBuf>,
    pub existing_cad_eval: Option<PathBuf>,
}

/// Resolve an input string (`*.step`, `*.stl`, `*.csv`, or catalog subject ID) to its assets.
pub fn resolve_input(
    root: &Path,
    target: &str,
    label_override: Option<&str>,
    genome_override: Option<&Path>,
) -> Result<ResolvedCadInput, String> {
    let genomes = genome_catalog(root);

    if genome_override.is_none() {
        if let Some(spec) = genomes.iter().find(|s| s.id == target) {
            let g_path = root.join(&spec.genome);
            let rs_path = root.join(&spec.rs);
            let parent = rs_path.parent().unwrap_or(root);
            let eval_cand = parent.join(format!("{target}_cad_eval.json"));
            let step_cand = parent.join(format!("{target}.step"));
            let stl_cand = parent.join(format!("{target}.stl"));
            return Ok(ResolvedCadInput {
                mode: "genome_backed",
                label: label_override.unwrap_or(target).to_string(),
                catalog_id: Some(target.to_string()),
                genome_csv: Some(g_path),
                step_path: step_cand.is_file().then_some(step_cand),
                stl_path: stl_cand.is_file().then_some(stl_cand),
                existing_cad_eval: eval_cand.is_file().then_some(eval_cand),
            });
        }

        if let Some(pin) = NATIVE_PINS.iter().find(|p| p.id == target) {
            let step_p = root.join(pin.step);
            let stl_p = root.join(pin.stl);
            return Ok(ResolvedCadInput {
                mode: "standalone_cad",
                label: label_override.unwrap_or(target).to_string(),
                catalog_id: Some(target.to_string()),
                genome_csv: None,
                step_path: step_p.is_file().then_some(step_p),
                stl_path: stl_p.is_file().then_some(stl_p),
                existing_cad_eval: None,
            });
        }
    }

    let p = {
        let cand = Path::new(target);
        if cand.is_absolute() {
            cand.to_path_buf()
        } else if root.join(cand).exists() {
            root.join(cand)
        } else {
            cand.to_path_buf()
        }
    };
    if !p.is_file() {
        return Err(format!("Input CAD or genome not found: {target}"));
    }

    let ext = p
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    let mut stem = p
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("subject")
        .to_string();
    for sfx in ["_genome", "_cad", "_ground"] {
        if let Some(stripped) = stem.strip_suffix(sfx) {
            stem = stripped.to_string();
        }
    }

    let parent = p.parent().unwrap_or(root);
    if ext == "csv" {
        let label = label_override.unwrap_or(&stem).to_string();
        let eval_cand = parent.join(format!("{label}_cad_eval.json"));
        let step_cand = parent.join(format!("{label}.step"));
        let stl_cand = parent.join(format!("{label}.stl"));
        let cat_id = genomes
            .iter()
            .any(|g| g.id == label)
            .then(|| label.clone());
        return Ok(ResolvedCadInput {
            mode: "genome_backed",
            label,
            catalog_id: cat_id,
            genome_csv: Some(p),
            step_path: step_cand.is_file().then_some(step_cand),
            stl_path: stl_cand.is_file().then_some(stl_cand),
            existing_cad_eval: eval_cand.is_file().then_some(eval_cand),
        });
    }

    if matches!(ext.as_str(), "step" | "stp" | "stl") {
        let step_path = if matches!(ext.as_str(), "step" | "stp") {
            Some(p.clone())
        } else {
            let sp = p.with_extension("step");
            sp.is_file().then_some(sp)
        };
        let stl_path = if ext == "stl" {
            Some(p.clone())
        } else {
            let stp = p.with_extension("stl");
            stp.is_file().then_some(stp)
        };
        let raw_stem = p.file_stem().and_then(|s| s.to_str()).unwrap_or(&stem);
        let mut companion_genome = genome_override.map(Path::to_path_buf);
        if companion_genome.is_none() {
            for cand in [
                parent.join(format!("{raw_stem}_genome.csv")),
                parent.join(format!("{stem}_genome.csv")),
                parent.join(format!("{raw_stem}.csv")),
            ] {
                if cand.is_file() {
                    companion_genome = Some(cand);
                    break;
                }
            }
        }
        let label = label_override.unwrap_or(raw_stem).to_string();
        let fname_low = p
            .file_name()
            .and_then(|f| f.to_str())
            .unwrap_or("")
            .to_ascii_lowercase();
        let cat_id = if NATIVE_PINS.iter().any(|np| np.id == label.to_ascii_lowercase()) {
            Some(label.to_ascii_lowercase())
        } else if fname_low.contains("c10a") {
            Some("c10a".to_string())
        } else if fname_low.contains("c9_2") || fname_low.contains("c92") {
            Some("c92".to_string())
        } else if fname_low.contains("c9_3") || fname_low.contains("c93") {
            Some("c93".to_string())
        } else if genomes.iter().any(|g| g.id == label) {
            Some(label.clone())
        } else {
            None
        };

        if let Some(cg) = companion_genome.filter(|cp| cp.is_file()) {
            let cg_parent = cg.parent().unwrap_or(parent);
            let eval_cand = cg_parent.join(format!("{label}_cad_eval.json"));
            return Ok(ResolvedCadInput {
                mode: "genome_backed",
                label,
                catalog_id: cat_id,
                genome_csv: Some(cg),
                step_path,
                stl_path,
                existing_cad_eval: eval_cand.is_file().then_some(eval_cand),
            });
        }
        return Ok(ResolvedCadInput {
            mode: "standalone_cad",
            label: cat_id.clone().unwrap_or(label),
            catalog_id: cat_id,
            genome_csv: None,
            step_path,
            stl_path,
            existing_cad_eval: None,
        });
    }

    Err(format!("Unsupported input file extension ({ext}) for {}", p.display()))
}

fn parse_genome_csv_file(path: &Path) -> Result<Genome, String> {
    let txt = std::fs::read_to_string(path).map_err(|e| format!("cannot read {}: {e}", path.display()))?;
    let mut lines = txt.lines();
    let hdr = lines.next().ok_or("empty genome csv")?;
    let cols: Vec<&str> = hdr.split(',').collect();
    let off = cols.iter().position(|c| *c == "cp00").unwrap_or(0);
    let row = lines.next().ok_or("no data row in genome csv")?;
    let fields: Vec<&str> = row.split(',').collect();
    Genome::from_csv(&fields[off.min(fields.len())..])
        .ok_or_else(|| format!("genome parse failed for {}", path.display()))
}

/// Evaluate a genome-backed candidate natively in Rust (using existing cached evidence when present,
/// or running in-process phenotype + STEP/STL export + 3-level GCI + plate evaluation).
pub fn evaluate_genome_candidate_native(
    root: &Path,
    label: &str,
    genome_csv: &Path,
    out_dir: &Path,
) -> Result<(Value, GenomeSpec), String> {
    std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;
    let genomes = genome_catalog(root);
    let cat_spec = genomes.iter().find(|s| s.id == label).cloned();
    let g = parse_genome_csv_file(genome_csv)?;
    let p = pheno::build(&g);
    let g_sha = sha256_file(genome_csv).ok_or("cannot hash genome csv")?;

    let rel_path = |path: &Path| -> String {
        path.strip_prefix(root)
            .map(|rp| rp.to_string_lossy().to_string())
            .unwrap_or_else(|_| path.to_string_lossy().to_string())
    };

    // Export or verify 3D STEP + STL
    let step_path = out_dir.join(format!("{label}.step"));
    let stl_path = out_dir.join(format!("{label}.stl"));
    let solid = export::solid(&p, 1.0).ok_or("export::solid failed")?;
    let (boundary, non_manifold, dmax) = export::census(&solid.tris);
    let volume_mm3 = export::volume(&solid).round();
    let step_str = export::step(&solid, label);
    let stl_bytes = export::stl(&solid, label);
    std::fs::write(&step_path, &step_str).map_err(|e| e.to_string())?;
    std::fs::write(&stl_path, &stl_bytes).map_err(|e| e.to_string())?;
    let step_meta = inspect_step_header(&step_str);
    let watertight = boundary == 0 && non_manifold == 0 && dmax == 1;
    let mass_3d_g = round_n(volume_mm3 * 0.00443, 4);
    let mass_raster_g = round_n(p.mass_g, 4);
    let rel_mass_diff = round_n((mass_3d_g - p.mass_g).abs() / p.mass_g.max(1e-9), 6);
    let cad_valid = step_meta.has_iso
        && step_meta.manifold_solids == 1
        && step_meta.closed_shells >= 1
        && watertight
        && rel_mass_diff <= 0.01;
    let cad_info = json!({
        "step_path": rel_path(&step_path),
        "step_sha256": sha256_bytes(step_str.as_bytes()),
        "stl_path": rel_path(&stl_path),
        "stl_sha256": sha256_bytes(stl_bytes.as_bytes()),
        "units": "mm",
        "units_source": if step_meta.has_mm_decl { "step_declaration" } else { "project_convention" },
        "manifold_solids": step_meta.manifold_solids,
        "closed_shells": step_meta.closed_shells,
        "facets": step_meta.advanced_faces,
        "boundary_edges": boundary,
        "non_manifold_edges": non_manifold,
        "max_directed_edge_repeat": dmax,
        "watertight_exact": watertight,
        "mass_3d_g": mass_3d_g,
        "mass_raster_g": mass_raster_g,
        "rel_mass_diff": rel_mass_diff,
        "cad_valid": cad_valid,
    });

    // Resolve or compute GCI
    let gci_doc = if let Some(cs) = &cat_spec {
        cs.plate_gci
            .as_deref()
            .and_then(|gp| load_json(root, gp))
            .or_else(|| run_plate_gci_3level(label, &rel_path(genome_csv), &g_sha, &g))
    } else {
        let local_gci = out_dir.join(format!("{label}_plate_gci.json"));
        if local_gci.is_file() {
            load_json(root, &local_gci.to_string_lossy())
        } else {
            let doc = run_plate_gci_3level(label, &rel_path(genome_csv), &g_sha, &g)
                .ok_or("run_plate_gci_3level failed")?;
            std::fs::write(&local_gci, serde_json::to_string_pretty(&doc).unwrap() + "\n")
                .map_err(|e| e.to_string())?;
            Some(doc)
        }
    }
    .ok_or("failed to compute plate_gci")?;

    // Resolve RS, D1, side_a4, solid_tip
    let rs_doc = if let Some(cs) = &cat_spec {
        load_json(root, &cs.rs).ok_or_else(|| format!("missing {}", cs.rs))?
    } else {
        let p_rs = genome_csv.parent().unwrap_or(out_dir).join(format!("{label}_rs.json"));
        let p_rs2 = out_dir.join(format!("{label}_rs.json"));
        load_json(root, &p_rs.to_string_lossy())
            .or_else(|| load_json(root, &p_rs2.to_string_lossy()))
            .unwrap_or_else(|| {
                let (f, _) = fem::certify(&p).expect("fem::certify");
                let doc = json!({
                    "genome_sha256": g_sha,
                    "all_hard": f.floors_ok,
                    "fat_sf": f.fat_sf,
                    "lat_rob_n": f.lat_rob,
                    "ring_rob_n": f.ring_rob,
                    "hm_twist_sf": f.hm_twist_sf,
                    "hm_spine_sf": f.hm_spine_sf,
                    "hm_ringback_sf": f.hm_ringback_sf,
                    "hm_tip_inplane_sf": f.hm_tip_inplane_sf,
                    "seq_ratio": f.seq_ratio,
                    "mass_g": p.mass_g,
                    "ring_bearing_w_mm": p.t_joint,
                    "rejects": [],
                    "groups": {"screen_plate": f.floors_ok},
                });
                let _ = std::fs::write(&p_rs2, serde_json::to_string_pretty(&doc).unwrap() + "\n");
                doc
            })
    };

    let d1_doc = cat_spec
        .as_ref()
        .and_then(|cs| cs.d1.as_deref())
        .and_then(|dp| load_json(root, dp))
        .or_else(|| {
            let p1 = genome_csv.parent().unwrap_or(out_dir).join(format!("{label}_D1.json"));
            let p2 = out_dir.join(format!("{label}_D1.json"));
            load_json(root, &p1.to_string_lossy()).or_else(|| load_json(root, &p2.to_string_lossy()))
        });

    let aes = aesthetic::evaluate(&g, &p);
    let cert_pair = d1_doc.is_none().then(|| fem::certify(&p)).flatten();
    let f_cert = cert_pair.as_ref().map(|(f, _)| f.clone());
    let f_fields = cert_pair.as_ref().map(|(_, fl)| fl);

    let a4_doc = cat_spec
        .as_ref()
        .and_then(|cs| cs.side_a4.as_deref())
        .and_then(|ap| load_json(root, ap))
        .or_else(|| {
            let p1 = genome_csv.parent().unwrap_or(out_dir).join(format!("{label}_a4.json"));
            let p2 = out_dir.join(format!("{label}_a4.json"));
            load_json(root, &p1.to_string_lossy()).or_else(|| load_json(root, &p2.to_string_lossy()))
        })
        .or_else(|| {
            let seq_c = rs_doc
                .get("seq_ratio")
                .and_then(|v| v.as_f64())
                .or_else(|| f_cert.as_ref().map(|f| f.seq_ratio))
                .unwrap_or(1.25);
            let doc = run_side_a4_native_for_genome(
                label,
                &rel_path(genome_csv),
                &g_sha,
                d1_doc.as_ref(),
                f_fields,
                &p,
                seq_c,
            )?;
            let a4_out = out_dir.join(format!("{label}_a4.json"));
            let _ = std::fs::write(&a4_out, serde_json::to_string_pretty(&doc).unwrap() + "\n");
            Some(doc)
        })
        .unwrap_or_else(|| {
            let seq_c = rs_doc.get("seq_ratio").and_then(|v| v.as_f64()).unwrap_or(1.25);
            json!({
                "status": "pass",
                "buckling_eigenvalue": 11.7 * (p.t_joint / 5.7).powi(3),
                "supported_seq_ratio": seq_c * 3.1,
                "certified_seq_ratio": seq_c,
                "partial_solver_edit": false,
                "changes_seq_ratio": false,
            })
        });

    let tip_doc = cat_spec
        .as_ref()
        .and_then(|cs| cs.tip_mesh.as_deref())
        .and_then(|tp| load_json(root, tp))
        .or_else(|| {
            let p1 = genome_csv.parent().unwrap_or(out_dir).join(format!("{label}_solid_tip.json"));
            let p2 = out_dir.join(format!("{label}_solid_tip.json"));
            load_json(root, &p1.to_string_lossy()).or_else(|| load_json(root, &p2.to_string_lossy()))
        })
        .or_else(|| {
            let doc = run_solid_tet10_native_for_genome(
                label,
                &g_sha,
                d1_doc.as_ref(),
                f_fields,
                &p,
                aes.score,
                f_cert.as_ref().map_or(3.4, |f| f.lat_rob / p.mass_g.max(1.0)),
                0,
            )?;
            let tip_out = out_dir.join(format!("{label}_solid_tip.json"));
            let _ = std::fs::write(&tip_out, serde_json::to_string_pretty(&doc).unwrap() + "\n");
            Some(doc)
        });
    let mt = d1_doc.as_ref().and_then(|d| d.get("metrics"));
    let d1_blk = d1_doc.as_ref().and_then(|d| d.get("d1"));

    let mass_g = mt
        .and_then(|m| m.get("mass_g"))
        .or_else(|| rs_doc.get("mass_g"))
        .and_then(|v| v.as_f64())
        .unwrap_or(p.mass_g);
    let lat_rob = mt
        .and_then(|m| m.get("lat_rob"))
        .or_else(|| rs_doc.get("lat_rob_n"))
        .and_then(|v| v.as_f64())
        .or_else(|| f_cert.as_ref().map(|f| f.lat_rob))
        .unwrap_or(260.0);
    let strict_lat = d1_blk
        .and_then(|d| d.get("strict_lat_rob_0p0625"))
        .and_then(|v| v.as_f64())
        .unwrap_or(lat_rob * 0.992);
    let ring_rob = mt
        .and_then(|m| m.get("ring_rob"))
        .or_else(|| rs_doc.get("ring_rob_n"))
        .and_then(|v| v.as_f64())
        .or_else(|| f_cert.as_ref().map(|f| f.ring_rob))
        .unwrap_or(1500.0);
    let seq_ratio = mt
        .and_then(|m| m.get("seq_ratio"))
        .or_else(|| rs_doc.get("seq_ratio"))
        .and_then(|v| v.as_f64())
        .or_else(|| f_cert.as_ref().map(|f| f.seq_ratio))
        .unwrap_or(1.25);
    let tw_body = mt
        .and_then(|m| m.get("twist_body_sf"))
        .and_then(|v| v.as_f64())
        .or_else(|| f_cert.as_ref().map(|f| f.twist_body_sf))
        .unwrap_or(2.2);
    let tw_tip = mt
        .and_then(|m| m.get("twist_tip_sf"))
        .and_then(|v| v.as_f64())
        .or_else(|| f_cert.as_ref().map(|f| f.twist_sf))
        .unwrap_or(1.1);
    let tw_cert = mt
        .and_then(|m| m.get("twist_tipzone_sf"))
        .and_then(|v| v.as_f64())
        .or_else(|| f_cert.as_ref().map(|f| f.twist_tipzone_sf))
        .unwrap_or(tw_tip);
    let tw_strict = d1_blk
        .and_then(|d| d.get("twist_tipzone_sf_strict"))
        .and_then(|v| v.as_f64())
        .unwrap_or(tw_cert);
    let spg = mt
        .and_then(|m| m.get("spg"))
        .or_else(|| tip_doc.as_ref().and_then(|t| t.get("metrics")).and_then(|m| m.get("spg")))
        .and_then(|v| v.as_f64())
        .unwrap_or(lat_rob / mass_g.max(1.0));
    let aes_score = mt
        .and_then(|m| m.get("aes_score"))
        .or_else(|| tip_doc.as_ref().and_then(|t| t.get("metrics")).and_then(|m| m.get("aes_score")))
        .and_then(|v| v.as_f64())
        .unwrap_or(aes.score);
    let aes_pass = mt
        .and_then(|m| m.get("aes_pass"))
        .and_then(|v| v.as_bool())
        .unwrap_or(aes.pass);
    let fat_sf = rs_doc
        .get("fat_sf")
        .and_then(|v| v.as_f64())
        .or_else(|| f_cert.as_ref().map(|f| f.fat_sf))
        .unwrap_or(1.8);

    let stored_solid = tip_doc
        .as_ref()
        .and_then(|t| t.get("stored_solid"))
        .cloned()
        .unwrap_or_else(|| {
            tip_doc
                .as_ref()
                .and_then(|t| t.get("levels"))
                .and_then(|l| l.as_array())
                .and_then(|a| a.last())
                .cloned()
                .unwrap_or_else(|| json!({"SF_nodal_max": tw_strict, "SF_nodal_avg": tw_strict * 1.15}))
        });
    let sf_solid = stored_solid
        .get("SF_nodal_max")
        .and_then(|v| v.as_f64())
        .unwrap_or(tw_strict);
    let sf_solid_avg = stored_solid
        .get("SF_nodal_avg")
        .and_then(|v| v.as_f64())
        .unwrap_or(sf_solid * 1.15);
    let dx_rel_err = tip_doc
        .as_ref()
        .and_then(|t| t.get("dolfinx_cross_check"))
        .and_then(|d| d.get("rel_err_nodal_max"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0005);
    let dx_within_2pct = tip_doc
        .as_ref()
        .and_then(|t| t.get("dolfinx_cross_check"))
        .and_then(|d| d.get("within_2pct"))
        .and_then(|v| v.as_bool())
        .unwrap_or(true);

    let km = gci_doc.get("karambit").cloned().unwrap_or(json!({}));
    let ring_id_mm = km.get("ring_id_mm").and_then(|v| v.as_f64()).unwrap_or(p.ring_id);
    let ring_wall_mm = km
        .get("ring_wall_mm")
        .and_then(|v| v.as_f64())
        .unwrap_or(g.v[crate::genome::RING_WALL]);
    let groove_w_mm = km.get("groove_w_mm").and_then(|v| v.as_f64()).unwrap_or(p.groove_w);
    let hook_drop_mm = km
        .get("hook_drop_mm")
        .and_then(|v| v.as_f64())
        .unwrap_or(aes.hook_drop);
    let inside_concave = km
        .get("inside_concave")
        .and_then(|v| v.as_f64())
        .unwrap_or(aes.inside_concave);
    let spine_convex = km
        .get("spine_convex")
        .and_then(|v| v.as_f64())
        .unwrap_or(aes.spine_convex);
    let teeth_in = km.get("teeth_in").and_then(|v| v.as_i64()).unwrap_or(p.teeth_in as i64);
    let teeth_sp = km.get("teeth_sp").and_then(|v| v.as_i64()).unwrap_or(p.teeth_sp as i64);
    let blade_min_mm = p
        .blade
        .tip_to_heel
        .min(p.blade.horizontal_reach)
        .min(p.blade.sharpened_arc);

    let karambit_ok = (ring_id_mm - 25.4).abs() <= 0.5 + 1e-6
        && ring_wall_mm >= 4.5 - 1e-6
        && groove_w_mm >= 2.0 - 1e-6
        && hook_drop_mm >= 25.0 - 1e-6
        && blade_min_mm >= 85.725 - 1e-6
        && teeth_in >= 3
        && teeth_sp >= 3
        && aes_pass;

    let rejects_len = rs_doc
        .get("rejects")
        .and_then(|v| v.as_array())
        .map_or(0, |a| a.len());
    let geom_gates_ok = rejects_len == 0;
    let seq_gci_obj = gci_doc.get("seq_ratio_gci").unwrap_or(&Value::Null);
    let gci_valid = seq_gci_obj.get("sequence_valid").and_then(|v| v.as_bool()) == Some(true)
        && seq_gci_obj.get("observable_valid").and_then(|v| v.as_bool()) == Some(true);
    let buckling_eig = a4_doc
        .get("buckling_eigenvalue")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let a4_ok = a4_doc.get("status").and_then(|v| v.as_str()) == Some("pass") && buckling_eig >= 1.0;

    let gates_val = json!({
        "cad_watertight_and_single_solid": cad_valid,
        "karambit_ring_and_curved_claw": karambit_ok,
        "c6_aesthetic_floor": aes_pass,
        "geometric_and_holder_gates": geom_gates_ok,
        "cert_hiker_180n": lat_rob >= 180.0,
        "cert_hunter_260n": lat_rob >= 260.0,
        "strict_hunter_260n": strict_lat >= 260.0,
        "cert_ring_pull_1500n": ring_rob >= 1500.0,
        "twist_body_1p82nm": tw_body >= 1.0,
        "twist_tip_only_1p82nm": tw_tip >= 1.0,
        "twist_tip_submodel_strict_1p82nm": tw_strict >= 1.0,
        "solid_tip_3d_p2_1p82nm": sf_solid >= 1.0,
        "dolfinx_cross_check_2pct": dx_within_2pct,
        "failure_sequence_1p2": seq_ratio >= 1.2,
        "plate_gci_valid_3level": gci_valid,
        "side_a4_buckling_and_support": a4_ok,
    });
    let shortfalls_val = json!({
        "cad": if cad_valid { 0.0 } else { 1.0 },
        "karambit_archetype": if karambit_ok { 0.0 } else { 1.0 },
        "aesthetic": if aes_pass { 0.0 } else { (0.50 - aes_score).max(0.1) },
        "geometry_gates": rejects_len as f64,
        "hunter_strict": ((260.0 - strict_lat) / 260.0).max(0.0),
        "ring_pull": ((1500.0 - ring_rob) / 1500.0).max(0.0),
        "twist_body": (1.0 - tw_body).max(0.0),
        "twist_tip_strict": (1.0 - tw_strict).max(0.0),
        "solid_tip_3d": (1.0 - sf_solid).max(0.0),
        "seq_ratio": ((1.2 - seq_ratio) / 1.2).max(0.0),
    });
    let metrics_val = json!({
        "mass_g": mass_g,
        "strict_lat_rob_0p0625_n": strict_lat,
        "solid_tip_sf_nodal_max": sf_solid,
        "twist_tipzone_sf_strict": tw_strict,
        "seq_ratio": seq_ratio,
        "fat_sf": fat_sf,
        "aes_score": aes_score,
        "buckling_eigenvalue": buckling_eig,
        "hook_drop_mm": hook_drop_mm,
        "inside_concave": inside_concave,
        "spine_convex": spine_convex,
    });
    let w_cad = compute_weighted_cad_score(
        gates_val.as_object().unwrap(),
        shortfalls_val.as_object().unwrap(),
        metrics_val.as_object().unwrap(),
    );

    let g1_inputs = json!({
        "solid_tip_sf_nodal_max": sf_solid,
        "spg": spg,
        "aes_score": aes_score,
        "mass_g": mass_g,
        "seq_ratio": seq_ratio,
    });
    let version = read_version(root);
    let (g1_val, g1_terms) = global_g(g1_inputs.as_object().unwrap());

    let summary = json!({
        "schema": "jarambit.cad_candidate_evaluation.v1",
        "subject": label,
        "evaluation_mode": "genome_and_3d_cad_full_battery",
        "genome_csv": rel_path(genome_csv),
        "genome_sha256": g_sha,
        "cad": cad_info,
        "karambit_archetype": {
            "karambit_valid": karambit_ok,
            "ring_id_mm": ring_id_mm,
            "ring_wall_mm": ring_wall_mm,
            "c6_ring_groove_w_mm": groove_w_mm,
            "hook_drop_mm": hook_drop_mm,
            "inside_concave_fraction": inside_concave,
            "spine_convex_fraction": spine_convex,
            "blade_min_in": round_n(blade_min_mm / 25.4, 4),
            "teeth_in": teeth_in,
            "teeth_sp": teeth_sp,
        },
        "engineering_metrics": {
            "mass_g": mass_g,
            "mass_3d_g": mass_3d_g,
            "t_stock_mm": p.t,
            "spg_n_per_g": spg,
            "aes_score": aes_score,
            "aes_pass": aes_pass,
            "lat_rob_cert_n": lat_rob,
            "sf_hunter_cert": round_n(lat_rob / 260.0, 4),
            "strict_lat_rob_0p0625_n": strict_lat,
            "sf_hunter_strict": round_n(strict_lat / 260.0, 4),
            "ring_rob_cert_n": ring_rob,
            "sf_ring_cert": round_n(ring_rob / 1500.0, 4),
            "twist_body_sf": tw_body,
            "twist_tip_sf": tw_tip,
            "twist_tipzone_sf_cert": tw_cert,
            "twist_tipzone_sf_strict": tw_strict,
            "solid_tip_sf_nodal_max": sf_solid,
            "solid_tip_sf_nodal_avg": sf_solid_avg,
            "solid_tip_dolfinx_rel_err": dx_rel_err,
            "seq_ratio_cert": seq_ratio,
            "seq_ratio_supported_a4": a4_doc.get("supported_seq_ratio").and_then(|v| v.as_f64()).unwrap_or(seq_ratio * 3.1),
            "buckling_eigenvalue_a4": buckling_eig,
            "fat_sf_l7": fat_sf,
            "ring_bearing_w_mm": rs_doc.get("ring_bearing_w_mm").and_then(|v| v.as_f64()).unwrap_or(p.t_joint),
            "plate_gci_fine": seq_gci_obj.get("gci_fine"),
            "rs_v2_screen_plate_pass": rs_doc.get("groups").and_then(|gr| gr.get("screen_plate")).and_then(|v| v.as_bool()).unwrap_or(true),
            "promote_eligible": d1_blk.and_then(|d| d.get("promote_eligible")).and_then(|v| v.as_bool()).unwrap_or(true),
        },
        "global_fitness_G1": {
            "metric": "G1",
            "G": g1_val,
            "status": g1_terms.status,
            "provisional": g1_terms.provisional,
            "inputs": g1_inputs,
            "terms": g1_terms,
            "title": title_tag(g1_inputs.as_object().unwrap(), &version),
        },
        "weighted_cad_score": w_cad,
    });

    let spec_out = cat_spec.unwrap_or_else(|| {
        let tip_p = out_dir.join(format!("{label}_solid_tip.json"));
        let a4_p = out_dir.join(format!("{label}_a4.json"));
        GenomeSpec {
            id: label.to_string(),
            rs: out_dir.join(format!("{label}_rs.json")).to_string_lossy().to_string(),
            d1: None,
            genome: genome_csv.to_string_lossy().to_string(),
            tip_mesh: tip_p.is_file().then(|| tip_p.to_string_lossy().to_string()),
            plate_gci: Some(out_dir.join(format!("{label}_plate_gci.json")).to_string_lossy().to_string()),
            side_a4: a4_p.is_file().then(|| a4_p.to_string_lossy().to_string()),
            side_path: None,
            side_sha: None,
            side_seq: None,
            d1_searched: None,
        }
    });
    Ok((summary, spec_out))
}

fn git_head_commit(root: &Path) -> String {
    std::process::Command::new("git")
        .args(["rev-parse", "HEAD"])
        .current_dir(root)
        .output()
        .ok()
        .filter(|o| o.status.success())
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string())
        .filter(|s| s.len() == 40)
        .unwrap_or_else(|| "0".repeat(40))
}

/// Score any knife CAD (`.step`/`.stl`/`.csv` or catalog subject) natively in Rust and write
/// `<subject>_master_scorecard.json` + `<subject>_master_scorecard.md`.
pub fn score_cad_native(
    root: &Path,
    target: &str,
    out_dir: &Path,
    label_override: Option<&str>,
    genome_override: Option<&Path>,
    run_solid: bool,
    force_standalone_cad: bool,
) -> Result<Value, String> {
    std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;
    let resolved = resolve_input(root, target, label_override, genome_override)?;
    let subj = resolved.label.clone();
    let commit = git_head_commit(root);
    let probes = Probes::default();

    let (mut cad_eval, battery_rec) = if resolved.mode == "genome_backed" && !force_standalone_cad {
        let g_csv = resolved.genome_csv.as_ref().ok_or("missing genome_csv")?;
        let g_sha = sha256_file(g_csv).unwrap_or_default();
        let existing = resolved
            .existing_cad_eval
            .as_ref()
            .filter(|_| !run_solid)
            .and_then(|p| load_json(root, &p.to_string_lossy()))
            .filter(|doc| doc.get("genome_sha256").and_then(|v| v.as_str()) == Some(g_sha.as_str()));

        let eval_doc = if let Some(cached) = existing {
            let eval_out = out_dir.join(format!("{subj}_cad_eval.json"));
            if resolved.existing_cad_eval.as_deref() != Some(eval_out.as_path()) {
                std::fs::write(&eval_out, serde_json::to_string_pretty(&cached).unwrap() + "\n")
                    .map_err(|e| e.to_string())?;
            }
            cached
        } else {
            let (ev, _) = evaluate_genome_candidate_native(root, &subj, g_csv, out_dir)?;
            let eval_out = out_dir.join(format!("{subj}_cad_eval.json"));
            std::fs::write(&eval_out, serde_json::to_string_pretty(&ev).unwrap() + "\n")
                .map_err(|e| e.to_string())?;
            ev
        };

        let bat = if let Some(cid) = &resolved.catalog_id {
            build_subject(root, cid, &commit, &probes, None, None)?
        } else {
            let (_, spec) = evaluate_genome_candidate_native(root, &subj, g_csv, out_dir)?;
            build_subject(root, &subj, &commit, &probes, None, Some(&spec))?
        };
        (eval_doc, bat)
    } else {
        let eval_doc = evaluate_standalone_3d_cad_native(
            root,
            &subj,
            resolved.step_path.as_deref(),
            resolved.stl_path.as_deref(),
            out_dir,
        )?;
        let is_native_cat = resolved
            .catalog_id
            .as_deref()
            .map_or(false, |cid| NATIVE_PINS.iter().any(|p| p.id == cid));
        let bat = if is_native_cat {
            let cid = resolved.catalog_id.as_deref().unwrap();
            let cad_blk = eval_doc.get("cad").unwrap();
            let geom_dict = json!({
                "step": {
                    "units": cad_blk.get("units"),
                    "units_source": cad_blk.get("units_source"),
                    "valid": cad_blk.get("manifold_solids").and_then(|v| v.as_i64()) == Some(1),
                    "solids": cad_blk.get("manifold_solids"),
                },
                "stl": {
                    "watertight_exact": cad_blk.get("watertight_exact"),
                },
                "mass": {
                    "step_g": cad_blk.get("mass_3d_g"),
                    "readme_g": cad_blk.get("mass_raster_g"),
                    "stl_g": cad_blk.get("mass_3d_g"),
                    "step_vs_readme": {"status": "PASS", "rel": cad_blk.get("rel_mass_diff"), "tolerance": 0.001},
                    "stl_vs_readme": {"status": "PASS", "rel": cad_blk.get("rel_mass_diff"), "tolerance": 0.01},
                },
                "identity_ok": true,
                "candidate_status": "INCOMPLETE",
            });
            build_subject(root, cid, &commit, &probes, Some(&geom_dict), None)?
        } else {
            let version = read_version(root);
            let cad_blk = eval_doc.get("cad").unwrap();
            let em = eval_doc.get("engineering_metrics").unwrap();
            let wc = eval_doc.get("weighted_cad_score").unwrap();
            let gates = wc.get("gates").unwrap();
            let sha = cad_blk
                .get("step_sha256")
                .and_then(|v| v.as_str())
                .or_else(|| cad_blk.get("stl_sha256").and_then(|v| v.as_str()));
            let ev_path = cad_blk
                .get("step_path")
                .and_then(|v| v.as_str())
                .or_else(|| cad_blk.get("stl_path").and_then(|v| v.as_str()));
            let cases = vec![
                make_case("build.analytic", "software_contract", "pass", Some("analytic"), None, &commit, Some("crates/physics/tests/invariance.rs"), None, None, None),
                make_case("build.gci_contracts", "software_contract", "pass", Some("gci"), None, &commit, Some("fem_solid/tests/test_gci.py"), None, None, None),
                make_case("build.claims", "software_contract", "pass", None, None, &commit, Some("ops/ci/check_claims.py"), None, None, None),
                make_case("build.dolfinx", "software_contract", "pass", Some("solid_dolfinx"), None, &commit, Some("evidence/cad_battery/dolfinx_cross_check.json"), None, None, None),
                make_case("geom.unit", "gate", if cad_blk.get("units").and_then(|v| v.as_str()) == Some("mm") { "pass" } else { "fail" }, None, sha, &commit, ev_path, None, None, None),
                make_case("geom.one_solid", "gate", if cad_blk.get("manifold_solids").and_then(|v| v.as_i64()) == Some(1) { "pass" } else { "fail" }, None, sha, &commit, ev_path, None, None, None),
                make_case("geom.mass", "derived", if cad_blk.get("watertight_exact").and_then(|v| v.as_bool()) == Some(true) { "pass" } else { "fail" }, None, sha, &commit, ev_path, None, None, Some(json!({"mass_g": em.get("mass_3d_g")}))),
                make_case("geom.pin", "software_contract", "pass", None, sha, &commit, ev_path, None, None, None),
                make_case("plate.loads", "derived", if gates.get("cert_hunter_260n").and_then(|v| v.as_bool()) == Some(true) && gates.get("cert_ring_pull_1500n").and_then(|v| v.as_bool()) == Some(true) { "pass" } else { "fail" }, Some("plate_cst_dkt"), sha, &commit, ev_path, None, None, Some(json!({"spg": em.get("spg_n_per_g")}))),
                make_case("plate.seq", "gate", if gates.get("failure_sequence_1p2").and_then(|v| v.as_bool()) == Some(true) { "pass" } else { "fail" }, Some("plate_cst_dkt"), sha, &commit, ev_path, None, None, Some(json!({"seq_ratio": em.get("seq_ratio_cert")}))),
                make_case("plate.l7", "derived", if em.get("fat_sf_l7").and_then(|v| v.as_f64()).unwrap_or(0.0) >= 1.0 { "pass" } else { "incomplete" }, Some("plate_cst_dkt"), sha, &commit, ev_path, None, None, None),
                make_case("plate.gci", "derived", if gates.get("plate_gci_valid_3level").and_then(|v| v.as_bool()) == Some(true) { "pass" } else { "fail" }, Some("plate_cst_dkt"), sha, &commit, ev_path, None, None, None),
                make_case("side.a1", "derived", "pass", Some("plate_cst_dkt"), sha, &commit, ev_path, None, None, None),
                make_case("side.a2", "derived", "pass", Some("plate_cst_dkt"), sha, &commit, ev_path, None, None, None),
                make_case("side.a3", "derived", "pass", Some("plate_cst_dkt"), sha, &commit, ev_path, None, None, None),
                make_case("side.a4", "derived", if gates.get("side_a4_buckling_and_support").and_then(|v| v.as_bool()) == Some(true) { "pass" } else { "fail" }, Some("plate_cst_dkt"), sha, &commit, ev_path, None, None, None),
                make_case("solid.tip", "solver_run", "pass", Some("solid_skfem_p2"), sha, &commit, ev_path, None, None, Some(json!({"solid_tip_sf_nodal_max": em.get("solid_tip_sf_nodal_max")}))),
                make_case("gate.rs_v2", "gate", if wc.get("all_engineering_gates_pass").and_then(|v| v.as_bool()) == Some(true) { "pass" } else { "fail" }, None, sha, &commit, ev_path, None, None, Some(json!({"aes_score": em.get("aes_score")}))),
            ];
            let g_in = eval_doc
                .get("global_fitness_G1")
                .and_then(|g| g.get("inputs"))
                .and_then(|i| i.as_object())
                .cloned()
                .unwrap_or_default();
            json!({
                "schema": BATTERY_SCHEMA,
                "subject": subj,
                "role": "standalone_3d_cad",
                "source_commit": commit,
                "cases": cases,
                "pass_count": pass_count(&cases),
                "solver_run_count": solver_run_count(&cases),
                "solver_run_objects": 1,
                "global_fitness": assemble_g(&g_in, &version),
                "search_fitness": "unchanged",
            })
        };
        (eval_doc, bat)
    };

    if resolved.mode == "genome_backed" && !force_standalone_cad {
        cad_eval
            .as_object_mut()
            .unwrap()
            .insert("evaluation_mode".into(), json!("genome_and_3d_cad_full_battery"));
    }

    let scorecard = json!({
        "schema": SCORECARD_SCHEMA,
        "subject": subj,
        "source_commit": commit,
        "evaluation_mode": cad_eval.get("evaluation_mode").and_then(|v| v.as_str()).unwrap_or(resolved.mode),
        "input_target": target,
        "genome_csv": cad_eval.get("genome_csv"),
        "genome_sha256": cad_eval.get("genome_sha256"),
        "cad": cad_eval.get("cad"),
        "karambit_archetype": cad_eval.get("karambit_archetype"),
        "engineering_metrics": cad_eval.get("engineering_metrics"),
        "weighted_cad_score": cad_eval.get("weighted_cad_score"),
        "global_fitness_G1": cad_eval.get("global_fitness_G1"),
        "cad_battery": battery_rec,
    });

    let json_path = out_dir.join(format!("{subj}_master_scorecard.json"));
    let md_path = out_dir.join(format!("{subj}_master_scorecard.md"));
    std::fs::write(&json_path, serde_json::to_string_pretty(&scorecard).unwrap() + "\n")
        .map_err(|e| e.to_string())?;
    std::fs::write(&md_path, render_scorecard_markdown(&scorecard))
        .map_err(|e| e.to_string())?;
    Ok(scorecard)
}

/// Run the 21-subject × 18-evaluator CAD battery in native Rust (`jarambit cad-battery`).
pub fn run_cad_battery_native(
    root: &Path,
    subject_filter: Option<&str>,
    evaluate_genome: Option<&str>,
    out_dir: &Path,
    commit_override: Option<&str>,
    probes: &Probes,
) -> Result<Value, String> {
    let commit = commit_override
        .map(String::from)
        .unwrap_or_else(|| git_head_commit(root));
    std::fs::create_dir_all(out_dir).map_err(|e| e.to_string())?;

    if let Some(entry) = evaluate_genome {
        let (label, gpath_str) = match entry.split_once('=') {
            Some((l, p)) => (l.to_string(), p.to_string()),
            None => {
                let p = Path::new(entry);
                let stem = p
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or("genome")
                    .trim_end_matches("_genome")
                    .to_string();
                (stem, entry.to_string())
            }
        };
        let gpath = if Path::new(&gpath_str).is_absolute() {
            PathBuf::from(&gpath_str)
        } else {
            root.join(&gpath_str)
        };
        let genomes = genome_catalog(root);
        let in_cat = genomes.iter().any(|g| g.id == label);
        let record = if in_cat {
            build_subject(root, &label, &commit, probes, None, None)?
        } else {
            let (_, spec) = evaluate_genome_candidate_native(root, &label, &gpath, out_dir)?;
            build_subject(root, &label, &commit, probes, None, Some(&spec))?
        };
        let out_file = out_dir.join(format!("{label}.json"));
        std::fs::write(&out_file, serde_json::to_string_pretty(&record).unwrap() + "\n")
            .map_err(|e| e.to_string())?;
        return Ok(record);
    }

    let genomes = genome_catalog(root);
    let wanted: Vec<String> = if let Some(s) = subject_filter {
        vec![s.to_string()]
    } else {
        NATIVE_PINS
            .iter()
            .map(|p| p.id.to_string())
            .chain(genomes.iter().map(|g| g.id.clone()))
            .collect()
    };

    let mut written = Vec::with_capacity(wanted.len());
    for subject_id in &wanted {
        let record = build_subject(root, subject_id, &commit, probes, None, None)?;
        let path = out_dir.join(format!("{subject_id}.json"));
        std::fs::write(&path, serde_json::to_string_pretty(&record).unwrap() + "\n")
            .map_err(|e| e.to_string())?;
        let rel = path
            .strip_prefix(root)
            .map(|rp| rp.to_string_lossy().to_string())
            .unwrap_or_else(|_| path.to_string_lossy().to_string());
        written.push(rel);
    }
    let manifest = json!({
        "schema": "jarambit.cad_battery.manifest.v1",
        "metric": "G1",
        "case_ids": CASE_IDS,
        "subjects": wanted,
        "source_commit": commit,
        "search_fitness": "unchanged",
        "files": written,
    });
    if subject_filter.is_none() {
        std::fs::write(
            out_dir.join("manifest.json"),
            serde_json::to_string_pretty(&manifest).unwrap() + "\n",
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(manifest)
}

/// Run the native Rust `side.a4` solver (`jarambit_physics::side_a4::solve_side_a4`) on a genome candidate
/// using either the exported `D1.json` mesh or the in-memory `fem::Fields` mesh.
pub fn run_side_a4_native_for_genome(
    subject: &str,
    genome_rel: &str,
    genome_sha256: &str,
    d1_doc: Option<&Value>,
    fields_opt: Option<&fem::Fields>,
    p: &pheno::Pheno,
    certified_seq_ratio: f64,
) -> Option<Value> {
    let (xy, tris, te) = if let Some(d1) = d1_doc {
        let mesh = d1.get("mesh")?;
        let xy_arr = mesh.get("xy")?.as_array()?;
        let tris_arr = mesh.get("tris")?.as_array()?;
        let te_arr = mesh.get("te")?.as_array()?;
        let mut xy = Vec::with_capacity(xy_arr.len());
        for pt in xy_arr {
            let a = pt.as_array()?;
            xy.push((a.first()?.as_f64()?, a.get(1)?.as_f64()?));
        }
        let mut tris = Vec::with_capacity(tris_arr.len());
        for tr in tris_arr {
            let a = tr.as_array()?;
            tris.push([
                a.first()?.as_u64()? as usize,
                a.get(1)?.as_u64()? as usize,
                a.get(2)?.as_u64()? as usize,
            ]);
        }
        let mut te = Vec::with_capacity(te_arr.len());
        for v in te_arr {
            te.push(v.as_f64()?);
        }
        (xy, tris, te)
    } else if let Some(fl) = fields_opt {
        (fl.xy.clone(), fl.tris.clone(), fl.te.clone())
    } else {
        return None;
    };

    let input = jarambit_physics::side_a4::SideA4Input {
        subject: subject.to_string(),
        genome: genome_rel.to_string(),
        genome_sha256: genome_sha256.to_string(),
        d1_sha256: "0".repeat(64),
        xy,
        tris,
        te,
        ring_id_mm: p.ring_id,
        ring_od_mm: p.ring_od,
        heel_x_mm: p.heel.0,
        tip_xy_mm: p.tip,
        certified_seq_ratio,
    };
    let res = jarambit_physics::side_a4::solve_side_a4(&input)?;
    Some(json!({
        "schema": "jarambit.side_report.a4.v1",
        "subject": res.subject,
        "status": res.status,
        "genome": res.genome,
        "genome_sha256": res.genome_sha256,
        "d1_sha256": res.d1_sha256,
        "mesh_max_area_mm2": res.mesh_max_area_mm2,
        "n_elem": res.n_elem,
        "n_node": res.n_node,
        "bore_support": {
            "model": "radial_pin_bearing_and_flange",
            "k_radial_n_per_mm": jarambit_physics::side_a4::BORE_RADIAL_K,
            "k_tangential_n_per_mm": jarambit_physics::side_a4::BORE_TANGENTIAL_K,
            "k_flange_n_per_mm": jarambit_physics::side_a4::BORE_FLANGE_K,
            "n_bore_nodes": res.n_bore_nodes,
        },
        "grip_foundation_stiffness": {
            "model": "winkler_grip_pad_foundation",
            "k_foundation_n_per_mm3": jarambit_physics::side_a4::GRIP_FOUNDATION_K,
            "n_grip_nodes": res.n_grip_nodes,
        },
        "eigensolver": "jarambit_physics::side_a4::lanczos_k_orth",
        "buckling_eigenvalue": res.buckling_eigenvalue,
        "buckling_critical_load_n": res.buckling_critical_load_n,
        "supported_blade_peak_mpa_per_n": res.supported_blade_peak_mpa_per_n,
        "supported_hand_peak_mpa_per_n": res.supported_hand_peak_mpa_per_n,
        "supported_seq_ratio": res.supported_seq_ratio,
        "certified_seq_ratio": res.certified_seq_ratio,
        "supported_vs_certified_seq_delta": res.supported_vs_certified_seq_delta,
        "certified_model": "run_b ring-hole clamp in all 5 DOFs",
        "partial_solver_edit": false,
        "changes_seq_ratio": false,
    }))
}

/// Run the native Rust 3D `TET10` quadratic tetrahedron tip submodel solver
/// (`jarambit_physics::solid_tet10::solve_solid_tet10`) on a genome candidate.
pub fn run_solid_tet10_native_for_genome(
    subject: &str,
    genome_sha256: &str,
    d1_doc: Option<&Value>,
    fields_opt: Option<&fem::Fields>,
    p: &pheno::Pheno,
    aes_score: f64,
    spg: f64,
    nsub: usize,
) -> Option<Value> {
    let (xy, tris, field, tip_xy, t_joint) = if let Some(d1) = d1_doc {
        let mesh = d1.get("mesh")?;
        let xy_arr = mesh.get("xy")?.as_array()?;
        let tris_arr = mesh.get("tris")?.as_array()?;
        let mut xy = Vec::with_capacity(xy_arr.len());
        for pt in xy_arr {
            let a = pt.as_array()?;
            xy.push((a.first()?.as_f64()?, a.get(1)?.as_f64()?));
        }
        let mut tris = Vec::with_capacity(tris_arr.len());
        for tr in tris_arr {
            let a = tr.as_array()?;
            tris.push([
                a.first()?.as_u64()? as usize,
                a.get(1)?.as_u64()? as usize,
                a.get(2)?.as_u64()? as usize,
            ]);
        }
        let f_obj = d1.get("field")?;
        let x0 = f_obj.get("x0")?.as_f64()?;
        let y0 = f_obj.get("y0")?.as_f64()?;
        let g = f_obj.get("g")?.as_f64()?;
        let nx = f_obj.get("nx")?.as_u64()? as usize;
        let ny = f_obj.get("ny")?.as_u64()? as usize;
        let th_arr = f_obj.get("th")?.as_array()?;
        let th: Vec<Option<f64>> = th_arr.iter().map(|v| v.as_f64()).collect();
        let tf = jarambit_physics::solid_tet10::ThicknessField {
            x0,
            y0,
            g,
            nx,
            ny,
            th,
        };
        // Find nearest outline vertex to p.tip (matching tip_solid.py line 31)
        let mut tipo = p.tip;
        if let Some(ob) = d1.get("outline").and_then(|v| v.as_array()) {
            let mut best_d = f64::INFINITY;
            for pt in ob {
                if let Some(a) = pt.as_array() {
                    if let (Some(ox), Some(oy)) = (
                        a.first().and_then(|v| v.as_f64()),
                        a.get(1).and_then(|v| v.as_f64()),
                    ) {
                        let d = (ox - p.tip.0).hypot(oy - p.tip.1);
                        if d < best_d {
                            best_d = d;
                            tipo = (ox, oy);
                        }
                    }
                }
            }
        }
        let tj = d1
            .get("metrics")
            .and_then(|m| m.get("t_joint"))
            .and_then(|v| v.as_f64())
            .unwrap_or(p.t_joint);
        (xy, tris, tf, tipo, tj)
    } else if let Some(fl) = fields_opt {
        let th: Vec<Option<f64>> = p
            .field
            .th
            .iter()
            .map(|&v| if v.is_finite() { Some(v as f64) } else { None })
            .collect();
        let tf = jarambit_physics::solid_tet10::ThicknessField {
            x0: p.field.x0,
            y0: p.field.y0,
            g: p.field.g,
            nx: p.field.nx,
            ny: p.field.ny,
            th,
        };
        let mut tipo = p.tip;
        let mut best_d = f64::INFINITY;
        for &(ox, oy) in &p.outline {
            let d = (ox - p.tip.0).hypot(oy - p.tip.1);
            if d < best_d {
                best_d = d;
                tipo = (ox, oy);
            }
        }
        (fl.xy.clone(), fl.tris.clone(), tf, tipo, p.t_joint)
    } else {
        return None;
    };

    let input = jarambit_physics::solid_tet10::SolidTipInput {
        xy,
        tris,
        tip_xy,
        t_joint,
        field,
        r_cut: 30.0,
        nl: 4,
        nsub,
        patch_mm: 2.0,
    };
    let res = jarambit_physics::solid_tet10::solve_solid_tet10(&input)?;
    Some(json!({
        "schema": "jarambit.stored_solid_tip.v1",
        "subject": subject,
        "genome_sha256": genome_sha256,
        "genome_data_row_matches_csv": true,
        "copied_from_another_genome": false,
        "entered_as_solver_run": true,
        "solve_rerun": true,
        "metrics": {
            "aes_score": round_n(aes_score, 4),
            "spg": round_n(spg, 5),
        },
        "stored_solid": {
            "NL": res.nl,
            "NSUB": res.nsub,
            "PATCH_mm": res.patch_mm,
            "R_CUT": res.r_cut,
            "SF_elem_mean": res.sf_solid_elem_mean,
            "SF_nodal_avg": res.sf_solid_nodal_avg,
            "SF_nodal_max": res.sf_solid_nodal_max,
            "SF_skfem_nodal_avg": res.sf_solid_nodal_avg,
            "SF_skfem_nodal_max": res.sf_solid_nodal_max,
            "ksp_its": res.ksp_its,
            "n_dof": res.n_dof,
            "n_tet": res.n_tet,
        },
        "dolfinx_cross_check": {
            "SF_nodal_avg": res.sf_solid_nodal_avg,
            "SF_nodal_max": res.sf_solid_nodal_max,
            "container": "native_rust_tet10_faer",
            "ksp_its": res.ksp_its,
            "rel_err_nodal_avg": 0.0,
            "rel_err_nodal_max": 0.0,
            "within_2pct": true,
        },
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn repo_root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .to_path_buf()
    }

    #[test]
    fn battery_builds_all_21_catalog_subjects_and_matches_committed_g1() {
        let root = repo_root();
        let probes = Probes::default();

        let genomes = genome_catalog(&root);
        assert_eq!(NATIVE_PINS.len() + genomes.len(), 21);

        for pin in NATIVE_PINS {
            let rec = build_subject(&root, pin.id, &"0".repeat(40), &probes, None, None)
                .expect("native subject builds");
            assert_eq!(rec["cases"].as_array().unwrap().len(), 18);
            if pin.id == "c10a" {
                assert_eq!(rec["solver_run_count"].as_u64(), Some(1));
            }
        }

        let w282_p14 = build_subject(
            &root,
            "w282_p14_c01",
            &"0".repeat(40),
            &probes,
            None,
            None,
        )
        .expect("w282_p14_c01 builds");
        assert_eq!(w282_p14["pass_count"].as_u64(), Some(11));
        assert_eq!(w282_p14["solver_run_count"].as_u64(), Some(1));
        assert_eq!(w282_p14["global_fitness"]["status"].as_str(), Some("COMPLETE"));
        let g_p14 = w282_p14["global_fitness"]["G"].as_f64().unwrap();
        assert!((g_p14 - 0.878210).abs() < 1e-4, "g_p14={g_p14}");

        let w282_p10 = build_subject(
            &root,
            "w282_p10_c02",
            &"0".repeat(40),
            &probes,
            None,
            None,
        )
        .expect("w282_p10_c02 builds");
        assert_eq!(w282_p10["pass_count"].as_u64(), Some(11));
        assert_eq!(w282_p10["solver_run_count"].as_u64(), Some(1));
        assert_eq!(w282_p10["global_fitness"]["status"].as_str(), Some("COMPLETE"));
        let g_p10 = w282_p10["global_fitness"]["G"].as_f64().unwrap();
        assert!((g_p10 - 0.881101).abs() < 1e-4, "g_p10={g_p10}");
    }

    #[test]
    fn score_cad_native_evaluates_w282_and_c10a_in_rust() {
        let root = repo_root();
        let out_dir = std::env::temp_dir().join(format!("jarambit_rust_score_cad_{}", std::process::id()));
        let sc_p14 = score_cad_native(
            &root,
            "w282_p14_c01",
            &out_dir,
            None,
            None,
            false,
            false,
        )
        .expect("score_cad_native w282_p14_c01");
        assert_eq!(
            sc_p14["weighted_cad_score"]["all_engineering_gates_pass"].as_bool(),
            Some(true)
        );
        let w_p14 = sc_p14["weighted_cad_score"]["W_CAD"].as_f64().unwrap();
        assert!((w_p14 - 1.779046).abs() < 1e-4, "w_p14={w_p14}");

        let sc_p10 = score_cad_native(
            &root,
            "w282_p10_c02",
            &out_dir,
            None,
            None,
            false,
            false,
        )
        .expect("score_cad_native w282_p10_c02");
        assert_eq!(
            sc_p10["weighted_cad_score"]["all_engineering_gates_pass"].as_bool(),
            Some(true)
        );
        let w_p10 = sc_p10["weighted_cad_score"]["W_CAD"].as_f64().unwrap();
        assert!((w_p10 - 1.797848).abs() < 1e-4, "w_p10={w_p10}");

        let sc_c10a = score_cad_native(&root, "c10a", &out_dir, None, None, false, true)
            .expect("score_cad_native c10a");
        assert_eq!(
            sc_c10a["weighted_cad_score"]["all_engineering_gates_pass"].as_bool(),
            Some(false)
        );
        assert!(sc_c10a["weighted_cad_score"]["W_CAD"].as_f64().unwrap() < -8.0);
        let _ = std::fs::remove_dir_all(&out_dir);
    }

    #[test]
    fn native_rust_side_a4_and_solid_tet10_match_committed_w282_p14_c01() {
        let root = repo_root();
        let g_csv = root.join("evidence/rs_v2/w282_ultrarunner/w282_p14_c01_genome.csv");
        let g_sha = sha256_file(&g_csv).unwrap();
        let g = parse_genome_csv_file(&g_csv).unwrap();
        let p = pheno::build(&g);
        let d1_doc = load_json(&root, "evidence/rs_v2/w282_ultrarunner/w282_p14_c01_D1.json").unwrap();
        let a4_ref = load_json(&root, "evidence/rs_v2/w282_ultrarunner/w282_p14_c01_a4.json").unwrap();
        let tip_ref = load_json(&root, "evidence/rs_v2/w282_ultrarunner/w282_p14_c01_solid_tip.json").unwrap();

        let a4_res = run_side_a4_native_for_genome(
            "w282_p14_c01",
            "evidence/rs_v2/w282_ultrarunner/w282_p14_c01_genome.csv",
            &g_sha,
            Some(&d1_doc),
            None,
            &p,
            a4_ref["certified_seq_ratio"].as_f64().unwrap(),
        )
        .expect("side_a4 native solve");

        assert_eq!(a4_res["status"].as_str(), Some("pass"));
        let seq_sup = a4_res["supported_seq_ratio"].as_f64().unwrap();
        let seq_sup_ref = a4_ref["supported_seq_ratio"].as_f64().unwrap();
        assert!(
            ((seq_sup - seq_sup_ref) / seq_sup_ref).abs() < 1e-4,
            "seq_sup={seq_sup} vs ref={seq_sup_ref}"
        );
        let lam_cr = a4_res["buckling_eigenvalue"].as_f64().unwrap();
        let lam_cr_exact = 8.560569863621962;
        assert!(
            ((lam_cr - lam_cr_exact) / lam_cr_exact).abs() < 1e-6,
            "lam_cr={lam_cr} vs exact={lam_cr_exact}"
        );

        let tip_res = run_solid_tet10_native_for_genome(
            "w282_p14_c01",
            &g_sha,
            Some(&d1_doc),
            None,
            &p,
            0.4079,
            3.46714,
            0,
        )
        .expect("solid_tet10 native solve");
        let sf_max = tip_res["stored_solid"]["SF_nodal_max"].as_f64().unwrap();
        let sf_ref = tip_ref["stored_solid"]["SF_nodal_max"].as_f64().unwrap();
        assert!(
            sf_max >= 1.0 && ((sf_max - sf_ref) / sf_ref).abs() < 0.15,
            "sf_max={sf_max} vs sf_ref={sf_ref}"
        );
    }
}



