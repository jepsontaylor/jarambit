//! PR-0.31.2: cap-free fitness. Strength floors are hard; among feasible designs lighter wins.
use jarambit_crescent::{aesthetic::Aes, fem::Fem, genome::Genome, pheno::{Blade, NREM}, qd};

fn rec(mass: f64, lat: f64, ring: f64, seq: f64, body: f64, tip: f64) -> qd::Rec {
    let fem = Fem { lat_rob: lat, ring_rob: ring, floors_ok: lat >= 260.0 && ring >= 1500.0, seq_ratio: seq, twist_body_sf: body, twist_tipzone_sf: tip, ..Default::default() };
    qd::Rec { id: 1, gen: 0, g: Genome::c6_seed(5.7), mass_g: mass, blank_g: mass * 1.3, t: 5.8, blade: Blade::default(), grip: 70.0, aes: Aes { score: 0.7, pass: true, ..Default::default() },
        rejects: vec![], spg: lat / mass, fem: Some(fem), novelty: 0.0, fit: 0.0, desc: [0.0; qd::DESC_N], holder_lw: (0.0, 0.0, 0.0), removed: [0.0; NREM],
        min_web: 2.0, n_win: 0, win_area: 0.0, n_perf: 0, perf_area: 0.0, parents: vec![], op: "eval", op_version: 0 }
}
fn ok(m: f64) -> qd::Rec { rec(m, 290.0, 1700.0, 1.3, 1.1, 1.1) }

#[test]
fn lighter_infeasible_never_beats_heavier_feasible() {
    let heavy = qd::fitness(&ok(95.0));
    assert!(qd::feasible(&ok(95.0)) && heavy > 0.0);
    for m in [40.0, 55.0, 65.0, 72.0, 80.0] {
        for bad in [rec(m, 250.0, 1700.0, 1.3, 1.1, 1.1), rec(m, 290.0, 1400.0, 1.3, 1.1, 1.1), rec(m, 290.0, 1700.0, 1.19, 1.1, 1.1),
                    rec(m, 290.0, 1700.0, 1.3, 0.99, 1.1), rec(m, 290.0, 1700.0, 1.3, 1.1, 0.95)] {
            let f = qd::fitness(&bad);
            assert!(!qd::feasible(&bad) && f < 0.0 && f < heavy, "m {m}: infeasible {f} must rank below feasible {heavy}");
        }
        let mut aes_fail = ok(m); aes_fail.aes.pass = false; assert!(qd::fitness(&aes_fail) < heavy);
        let mut gate = ok(m); gate.rejects = vec!["jimping".into()]; assert!(qd::fitness(&gate) < heavy);
    }
}

#[test]
fn lighter_feasible_beats_heavier_and_no_cap_cliff() {
    let ms = [95.0, 84.8, 80.0, 76.0, 72.0, 70.0, 66.0, 60.0];
    for w in ms.windows(2) { assert!(qd::fitness(&ok(w[1])) > qd::fitness(&ok(w[0])), "{} g should beat {} g", w[1], w[0]); }
    // smooth: no cliff at the old 72/76/80 caps
    for c in [72.0, 76.0, 80.0] { let d = qd::fitness(&ok(c - 0.1)) - qd::fitness(&ok(c + 0.1)); assert!(d > 0.0 && d < 0.01, "cliff at {c}: {d}"); }
    // diminishing returns below 70 g
    let above = qd::fitness(&ok(70.0)) - qd::fitness(&ok(75.0)); let below = qd::fitness(&ok(65.0)) - qd::fitness(&ok(70.0));
    assert!(below < 0.5 * above, "below-knee gain {below} vs above {above}");
}

#[test]
fn graded_violation_and_margin_bonus() {
    assert!(qd::fitness(&rec(75.0, 290.0, 1700.0, 1.3, 1.1, 0.9)) > qd::fitness(&rec(75.0, 290.0, 1700.0, 1.3, 1.1, 0.7)));
    assert!(qd::fitness(&rec(75.0, 255.0, 1700.0, 1.3, 1.1, 1.1)) > qd::fitness(&rec(75.0, 200.0, 1700.0, 1.3, 1.1, 1.1)));
    // same mass: margin above the floor is rewarded; on the edge is feasible but lower
    let edge = rec(75.0, 260.0, 1500.0, 1.2, 1.0, 1.0); assert!(qd::feasible(&edge));
    assert!(qd::fitness(&ok(75.0)) > qd::fitness(&edge));
    // margin bonus is small: it cannot buy more than ~3 g
    assert!(qd::fitness(&edge) > qd::fitness(&rec(79.0, 400.0, 3000.0, 2.0, 2.0, 2.0)));
}

#[test]
fn strong_soft_mass_penalty_above_80g() {
    assert_eq!(qd::mass_over_penalty(79.0), 0.0);
    // over-target designs stay feasible (> every infeasible) but lose clearly more than the bonuses (<= 0.07)
    let gap = qd::fitness(&ok(80.0)) - qd::fitness(&ok(90.0));
    assert!(gap > 0.2, "80 vs 90 g gap {gap}");
    assert!(qd::fitness(&ok(110.0)) > 0.0);
}
