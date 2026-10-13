# Performance baseline (PR-0.31.1)

Workload: `bench/fixed_1k` (1000 frozen genomes, sha256 in `bench/fixed_1k/SHA256SUMS`). Runner: `python3 ops/bench/run.py --threads 8` (3 reps per tier; checksums must match across reps).
Host xbabe3 (128 logical cores), main `ed77d3a` + this PR, skyline Cholesky. Record: `evidence/bench/baseline_0.31.1_xbabe3.json`.

| tier | what is timed | n | core-s / design (median of 3) | rep spread |
|---|---|---|---|---|
| T1 search | `qd::evaluate` (plate FEM at search area 2.0) | 200 | 2.146 | 0.017 |
| T1c cert | `fem::certify` (fine plate + T6 membrane) | 40 | 26.31 | 0.69 |

Core-seconds = wall time of one design on one thread (8 workers share the list). Roadmap target for PR-0.31.2: T1c <= 25 s/core.
