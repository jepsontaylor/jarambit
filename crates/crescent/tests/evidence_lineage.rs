//! PR-0.29.1: lineage + counters through the real GA loops with a tiny synthetic evaluator (no FEM).
use jarambit_crescent::{aesthetic::Aes, fem::Fem, genome::Genome, pheno::{Blade, NREM}, qd};
use jarambit_evidence::{Event, VecSink};
use std::collections::HashSet;

/// Deterministic, cheap evaluator: every design is aesthetic-pass + legal; fitness inputs depend on the genome.
fn synth(g: &Genome, id: usize, gen: usize, _area: f64) -> qd::Rec {
    let s: f64 = g.v.iter().enumerate().map(|(i, x)| x * ((i % 7) as f64 + 1.0)).sum::<f64>();
    let m = 75.0 + (s.sin() * 5.0);
    let mut desc = [0.0; qd::DESC_N]; for (k, d) in desc.iter_mut().enumerate() { *d = (s * (k as f64 + 1.0)).sin() * 0.5 + 0.5; }
    let fem = Fem { lat_rob: 300.0 + 20.0 * s.cos(), ring_rob: 2000.0, floors_ok: true, seq_ratio: 2.0, twist_body_sf: 2.0, twist_tipzone_sf: 2.0, ..Default::default() };
    let aes = Aes { score: 0.8, pass: true, ..Default::default() };
    qd::Rec { id, gen, g: g.clone(), mass_g: m, blank_g: m * 1.3, t: 6.0, blade: Blade::default(), grip: 70.0, aes, rejects: vec![], spg: fem.lat_rob / m, fem: Some(fem),
        novelty: 0.0, fit: 0.0, desc, holder_lw: (0.0, 0.0, 0.0), removed: [0.0; NREM], min_web: 2.0, n_win: 0, win_area: 0.0, n_perf: 0, perf_area: 0.0,
        parents: vec![], op: "eval", op_version: 0 }
}

fn check_lineage(ev: &[Event]) -> (u64, u64) {
    let mut seen: HashSet<u64> = HashSet::new(); let (mut fresh, mut app) = (0u64, 0u64); let mut last = (0u64, 0u64);
    for e in ev { match e {
        Event::Eval { id, parents, op, op_version, .. } => {
            assert!(seen.insert(*id), "id {id} born twice"); fresh += 1; app += 1; assert_eq!(*op_version, jarambit_evidence::OP_VERSION);
            if !op.starts_with("seed") { assert!(!parents.is_empty(), "{op} without parents"); }
            for p in parents { assert!(seen.contains(p) || *p == 0, "parent {p} of {id} not yet born"); } }
        Event::Elite { id, .. } => { assert!(seen.contains(id), "elite {id} never born"); app += 1; }
        Event::Migration { ids, .. } => for i in ids { assert!(seen.contains(i)); },
        Event::GenEnd { fresh_evals, appearances, .. } => { assert_eq!((*fresh_evals, *appearances), (fresh, app), "GenEnd counters disagree with events"); last = (fresh, app); }
        _ => {} } }
    last
}

#[test]
fn single_pop_64x40_counters_and_lineage() {
    let cfg = qd::RunCfg { pop: 64, gens: 40, threads: 4, seed: 11, fem_area: 2.0, t_seed: 5.7 };
    let mut sink = VecSink::default();
    let ro = qd::run_with(&cfg, &synth, |_| {}, &mut sink);
    assert_eq!(ro.counters.fresh_evals, 2464, "64 + 40 x (64 - 4 elites)");
    assert_eq!(ro.counters.appearances, 2624, "41 generations x 64");
    assert_eq!(check_lineage(&sink.events), (2464, 2624));
    assert!(matches!(sink.events.last(), Some(Event::RunEnd { fresh_evals: 2464, appearances: 2624 })));
    assert_eq!(sink.gens_closed, 42, "41 generation frames + run end");
    // lineage is also on the records
    assert!(ro.all.iter().filter(|r| r.gen > 0 && r.op != "eval").all(|r| !r.parents.is_empty()));
}

#[test]
fn islands_counters_lineage_migration() {
    let base = qd::RunCfg { pop: 16, gens: 6, threads: 4, seed: 5, fem_area: 2.0, t_seed: 5.7 };
    let cfg = qd::IslandCfg { base, islands: 3, migrate_every: 2, migrants: 2, seeds: vec![Genome::c6_seed(5.7)], kick_frac: 0.2 };
    let mut sink = VecSink::default();
    let ro = qd::run_islands_with(&cfg, &synth, |_| {}, |_, _, _| {}, &mut sink);
    assert_eq!(ro.counters.fresh_evals, 3 * 16 + 6 * 3 * (16 - 3));
    assert_eq!(ro.counters.appearances, 7 * 3 * 16);
    assert_eq!(check_lineage(&sink.events), (ro.counters.fresh_evals, ro.counters.appearances));
    assert!(sink.events.iter().any(|e| matches!(e, Event::Migration { .. })));
}
