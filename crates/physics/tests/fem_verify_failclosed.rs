//! PR-0.28.4: fem-verify theory gate is fail-closed against verify/expected.toml.
use jarambit_physics::verify::{parse_expected, theory_gate, Obs, EXPECTED_TOML};

fn committed_obs() -> Vec<Obs> {
    // the committed finite report (docs/calibration/theory_checks.csv): must still PASS
    let txt = include_str!("../../../docs/calibration/theory_checks.csv");
    txt.lines().skip(1).map(|l| { let (name, rest) = l[1..].split_once("\",").unwrap(); let f: Vec<&str> = rest.split(',').collect();
        Obs { name: name.to_string(), max_area: f[0].parse().unwrap(), ratio: f[4].parse().unwrap() } }).collect()
}

#[test]
fn manifest_parses() {
    let e = parse_expected(EXPECTED_TOML).unwrap();
    assert_eq!(e.checks.len(), 9); assert_eq!(e.levels, vec![4.0, 2.0, 1.0, 0.5, 0.25]); assert_eq!(e.gate_levels, vec![0.25]); assert_eq!(e.max_err_pct, 5.0);
    assert!(e.checks.iter().any(|c| c == "hole Kt_gross (Heywood, d/W=0.2, T6)"));
}

#[test]
fn existing_finite_report_passes() {
    let e = parse_expected(EXPECTED_TOML).unwrap(); let o = committed_obs();
    assert_eq!(o.len(), 45); theory_gate(&e, &o).unwrap();
}

#[test]
fn fail_closed_cases() {
    let e = parse_expected(EXPECTED_TOML).unwrap(); let o = committed_obs();
    let mut m = o.clone(); m.retain(|x| !(x.name == "hole Kt_gross (Heywood, d/W=0.2, T6)" && x.max_area == 0.25));
    let r = theory_gate(&e, &m).unwrap_err(); assert!(r.iter().any(|w| w.contains("missing check") && w.contains("hole Kt")), "{r:?}");
    let mut m = o.clone(); m[0].ratio = f64::NAN;
    let r = theory_gate(&e, &m).unwrap_err(); assert!(r.iter().any(|w| w.contains("non-finite")), "{r:?}");
    // NaN at a gate level (the old gate passed it: NaN >= 5.0 is false)
    let mut m = o.clone(); let i = m.iter().position(|x| x.max_area == 0.25).unwrap(); m[i].ratio = f64::NAN;
    assert!(theory_gate(&e, &m).is_err());
    let mut m = o.clone(); m.push(m[3].clone());
    let r = theory_gate(&e, &m).unwrap_err(); assert!(r.iter().any(|w| w.contains("duplicate check")), "{r:?}");
    let r = theory_gate(&e, &[]).unwrap_err(); assert!(r.iter().any(|w| w.contains("all missing")), "{r:?}");
    let mut m = o.clone(); m.push(Obs { name: "made up".into(), max_area: 0.25, ratio: 1.0 }); assert!(theory_gate(&e, &m).is_err());
    let mut m = o.clone(); m.push(Obs { name: o[0].name.clone(), max_area: 0.125, ratio: 1.0 }); assert!(theory_gate(&e, &m).is_err());
    let mut m = o.clone(); let i = m.iter().position(|x| x.max_area == 0.25).unwrap(); m[i].ratio = 1.06;
    let r = theory_gate(&e, &m).unwrap_err(); assert!(r.iter().any(|w| w.contains(">= 5")), "{r:?}");
}

#[test]
fn malformed_manifest_is_error() {
    assert!(parse_expected("").is_err());
    assert!(parse_expected(&EXPECTED_TOML.replace("max_err_pct = 5.0", "max_err_pct = nan")).is_err());
    assert!(parse_expected(&EXPECTED_TOML.replace("gate_levels = [0.25]", "gate_levels = [0.125]")).is_err());
    assert!(parse_expected(&EXPECTED_TOML.replace("  \"cantilever mid-span stress\",\n", "  \"cantilever tip deflection\",\n")).is_err());
    assert!(parse_expected(&EXPECTED_TOML.replace("checks = [", "checks = []\nx = [")).is_err());
}
