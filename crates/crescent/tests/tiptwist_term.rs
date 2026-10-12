//! PR-0.30.1c: JARAMBIT_TIPTWIST_GATE makes the twist floor constraint-dominated for non-P1 genomes.
use jarambit_crescent::{aesthetic::Aes, fem::Fem, genome::Genome, pheno::{Blade, NREM}, qd};

fn rec(mass: f64, lat: f64, body: f64, tip: f64) -> qd::Rec {
    let fem = Fem { lat_rob: lat, ring_rob: 2000.0, floors_ok: true, seq_ratio: 2.0, twist_body_sf: body, twist_tipzone_sf: tip, ..Default::default() };
    let g = Genome::c6_seed(5.7); assert!(!g.p1());
    qd::Rec { id: 1, gen: 0, g, mass_g: mass, blank_g: mass * 1.3, t: 5.8, blade: Blade::default(), grip: 70.0, aes: Aes { score: 0.7, pass: true, ..Default::default() },
        rejects: vec![], spg: lat / mass, fem: Some(fem), novelty: 0.0, fit: 0.0, desc: [0.0; qd::DESC_N], holder_lw: (0.0, 0.0, 0.0), removed: [0.0; NREM],
        min_web: 2.0, n_win: 0, win_area: 0.0, n_perf: 0, perf_area: 0.0, parents: vec![], op: "eval", op_version: 0 }
}

#[test]
fn off_by_default_matches_legacy() {
    let thin_tip = rec(73.0, 280.0, 2.9, 0.7);
    assert!(qd::fitness_opt(&thin_tip, false) > 0.0, "legacy: tip twist not in non-P1 fitness");
}

#[test]
fn tip_twist_dominates_mass_and_spg() {
    let light_thin_tip = rec(73.0, 300.0, 2.9, 0.7);   // lighter + higher SPG, tip SF 0.7
    let heavy_ok_tip = rec(84.0, 280.0, 4.4, 1.2);     // heavier, tip SF 1.2
    let (a, b) = (qd::fitness_opt(&light_thin_tip, true), qd::fitness_opt(&heavy_ok_tip, true));
    assert!(a < -0.1 && a > -1.0, "graded constraint band, got {a}");
    assert!(b > 0.0 && b > a, "a design meeting the twist floor must outrank any that misses it ({b} vs {a})");
    // graded: closer to the floor ranks higher
    assert!(qd::fitness_opt(&rec(73.0, 300.0, 2.9, 0.9), true) > a);
}
