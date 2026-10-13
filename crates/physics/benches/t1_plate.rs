//! PR-0.31.1: criterion benches for T1 search (`evaluate`) and T1c cert (`fine::capacities`).
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use jarambit_genotype::{Genotype, Rng, TiGrade};
use jarambit_phenotype::Phenotype;
use jarambit_physics::{evaluate, fine, material};

fn sample_pheno(seed: u64) -> Phenotype {
    let mut r = Rng(seed);
    let g = Genotype::random(&mut r);
    Phenotype::from_genotype(&g)
}

fn bench_t1_search(c: &mut Criterion) {
    let p = sample_pheno(42);
    let m = material(TiGrade::Ti6Al4V);
    c.bench_function("t1_search_evaluate", |b| {
        b.iter(|| evaluate(black_box(&p), 16.0, (0.4, 0.4), m, 20.0))
    });
}

fn bench_t1c_cert(c: &mut Criterion) {
    let p = sample_pheno(42);
    let m = material(TiGrade::Ti6Al4V);
    c.bench_function("t1c_fine_capacities_area2", |b| {
        b.iter(|| fine::capacities(black_box(&p), m, 20.0, (0.4, 0.4), 2.0))
    });
}

criterion_group!(benches, bench_t1_search, bench_t1c_cert);
criterion_main!(benches);
