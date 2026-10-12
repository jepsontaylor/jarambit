# cli/ — Entry point

**Role directory (map only).** The code lives in the Cargo workspace; this directory exists so the top-level tree reads as the technology stack. Crates were NOT renamed (that would break `cargo` paths, CI and the live wave worktrees). See `TECHNOLOGY_MAP.md`.

| | |
|---|---|
| Code | crates/cli → binary `jarambit` (main.rs, crescent.rs: crescent-evolve / crescent-d1, calib.rs, fem_smoke.rs) |
| Inputs | CLI flags, genome CSVs |
| Outputs | out/<run>/ artefacts consumed by ops/wave_figures |
| Hard gates | CI smoke: crescent-d1 on wave14_c03 reference (ops/ci/d1_smoke.py) |
| Feeds GLOBAL metric G | Produces the plate JSONs that metrics/global_metric.py scores. |

Spec of G: `docs/GLOBAL_METRIC.md`. Author: Jepson Taylor.
