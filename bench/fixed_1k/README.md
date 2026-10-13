# fixed_1k — frozen T1/T1c accounting workload (PR-0.31.1)

1,000 frozen crescent genomes (`genomes.csv`, 128 floats/row) + this manifest.
Run via `ops/bench/run.py` (×3 reps). Reports wall, CPU-s, peak RSS, failures.
Do not regenerate after freeze; bump id if the set must change.
