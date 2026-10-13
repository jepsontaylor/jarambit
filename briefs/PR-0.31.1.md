# PR-0.31.1 — criterion benches + bench/fixed_1k + accounting

Depends on: PR-0.30.3 (merged, v0.30.0 on main). Owner host: xbabe3.

## Scope
- `crates/physics/benches/*` — criterion: T1 search (`evaluate`) + T1c cert (`fine::capacities`, max_area 2.0)
- `bench/fixed_1k/**` — 1000 frozen crescent genomes + MANIFEST.toml
- `ops/bench/run.py` — ×3 accounting (wall, CPU-s, peak RSS, failures, cache hits)

## Success
- Baseline numbers recorded for T1 search and T1c cert (×3 reps) on xbabe3
- Bench manifest committed; genomes frozen (do not regenerate)

## Rules
- Pull/rebase on `pr-0.31.1-bench` from origin/main; one PR at a time; no stacking
- Keep flywheel/JopeDime/Dope screens alone; nice -n 19; threads ≤ 48
- cargo test --release green before push; open PR when green; neverhumanbot approve + jepsontaylor squash-merge
