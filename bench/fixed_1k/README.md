# fixed_1k — frozen T1/T1c accounting workload (PR-0.31.1)

1,000 frozen crescent genomes (`genomes.csv`) + `MANIFEST.toml` + `SHA256SUMS`. Do not regenerate after freeze; bump the id if the set must change.
Built from the wave16 D1 collect seeds + c6_repair pass genomes, padded by 1–3 mutation steps (sigma 0.08) from `Rng(31)`:

    jarambit bench-make --seeds "$(ls docs/d1/wave15_16_collect/wave16_c*_genome.csv | tr '\n' ,)docs/lattice/rescore_c6_repair/c6_pass_genomes.csv" --n 1000 --seed 31 --out bench/fixed_1k/genomes.csv

Timing: `python3 ops/bench/run.py` (×3 reps per tier; per-design core-s, wall, peak RSS, failures; fails on a checksum change). Baseline: `docs/perf/baseline_0.31.1.md`.
