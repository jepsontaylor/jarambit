# Performance baseline (PR-0.31.1)

Workload: `bench/fixed_1k` (1000 frozen genomes, sha256 in `bench/fixed_1k/SHA256SUMS`). Runner: `python3 ops/bench/run.py --threads 8` (3 reps per tier; checksums must match across reps).
Host xbabe3 (128 logical cores), main `ed77d3a` + this PR, skyline Cholesky. Record: `evidence/bench/baseline_0.31.1_xbabe3.json`.

| tier | what is timed | n | core-s / design (median of 3) | rep spread |
|---|---|---|---|---|
| T1 search | `qd::evaluate` (plate FEM at search area 2.0) | 200 | 2.146 | 0.017 |
| T1c cert | `fem::certify` (fine plate + T6 membrane) | 40 | 26.31 | 0.69 |

Core-seconds = wall time of one design on one thread (8 workers share the list). Roadmap target for PR-0.31.2: T1c <= 25 s/core.

## PR-0.31.2: faer supernodal sparse Cholesky (record `evidence/bench/faer_0.31.2_xbabe3.json`)

| tier | skyline (0.31.1) | faer (0.31.2) | speed-up |
|---|---|---|---|
| T1 search | 2.146 | 2.028 | 1.06x (search time is dominated by meshing/phenotype, not the solve) |
| T1c cert | 26.31 | 6.74 | 3.9x (target <= 25 s/core met) |

Parity: unit tests `crates/physics/tests/solver_parity.rs` (plate 3 RHS, T6, mechanism rejection) agree to <= 1e-9 relative. On the workload,
the cert capacity checksum differs by 8.7e-9 relative from `JARAMBIT_SOLVER=skyline` (`evidence/bench/skyline_cert_0.31.2_xbabe3.json`) and the
search checksum by 4.2e-11. The 42 search "failures" are illegal genomes with no FEM, identical to the baseline.

## Issue #32 (PR-0.31.5): mechanism guard fixed, default reverted to skyline

- faer now applies the skyline pivot criterion itself: any LDL pivot <= 1e-13 x max|diag(K)| is replaced by a 1e300 sentinel that the factor check rejects, so partially constrained mechanisms (single clamped node, rigid in-plane rotation) return None for Plate and T6. Regression: `both_backends_reject_partially_constrained_rotation`.
- Checksum drift vs skyline on the 40-design cert workload (`evidence/bench/issue32_drift.json`): max per-design 2.6e-8, sum 8.7e-9. Two iterative-refinement steps do not reduce it (max 2.4e-8), so it is the double-precision floor of these stiffness matrices, not a faer defect; the owner bar is 1e-9.
- Per the owner rule (bar not met) the DEFAULT solver is skyline again; faer is opt-in with `JARAMBIT_SOLVER=faer` (3.9x faster cert). Cert timing reverts to the 0.31.1 baseline (26.3 core-s/design) unless opted in.
