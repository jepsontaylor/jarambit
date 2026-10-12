//! PR-0.29.3: feasible-only mean, terminal snapshot contains the returned best, genotype hash.
use jarambit_evolve::{feasible_mean, genotype_hash, try_run, Config, Indiv};
use jarambit_genotype::{Genotype, Rng};

fn ind(fit: f64, floors: bool, seed: u64) -> Indiv { Indiv { g: Genotype::random(&mut Rng(seed)), fit, mean: fit, strength_n: 300.0, mass_g: 40.0, floors_ok: floors, cut_p05: 0.1, sharp_p05: 0.5 } }

#[test]
fn mixed_population_mean_is_over_feasible_only() {
    // feasible = floors_ok && fit > 0. Graded infeasible scores (-1 .. -60) used to enter the CLI mean (filter fit > -100).
    let pop = vec![ind(8.0, true, 1), ind(6.0, true, 2), ind(-1.5, false, 3), ind(-55.0, false, 4), ind(-1000.0, false, 5), ind(3.0, false, 6), ind(-0.0, true, 7)];
    assert_eq!(feasible_mean(&pop), Some(7.0));
    assert_eq!(feasible_mean(&pop[2..6]), None);
}

#[test]
fn final_best_is_in_terminal_snapshot_and_hash_is_stable() {
    let mut c = Config::new(6, 4, 8, 2, 77); c.islands = 2;
    let mut snaps: Vec<(usize, bool, Vec<String>)> = Vec::new();
    let (best, _) = try_run(&c, |s| snaps.push((s.gen, s.terminal, s.pop.iter().map(|i| genotype_hash(&i.g)).collect()))).unwrap();
    let last = snaps.last().unwrap();
    assert!(last.1, "last snapshot must be terminal"); assert_eq!(last.0, 4);
    assert_eq!(snaps.iter().filter(|s| s.1).count(), 1);
    assert!(last.2.contains(&genotype_hash(&best.g)), "returned best missing from the terminal snapshot");
    assert_eq!(genotype_hash(&best.g), genotype_hash(&best.g.clone())); assert_eq!(genotype_hash(&best.g).len(), 16);
}
