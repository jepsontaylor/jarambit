# evolve/ — Search

**Role directory (map only).** The code lives in the Cargo workspace; this directory exists so the top-level tree reads as the technology stack. Crates were NOT renamed (that would break `cargo` paths, CI and the live wave worktrees). See `TECHNOLOGY_MAP.md`.

| | |
|---|---|
| Code | crates/evolve (NSGA-II, islands, migration, checkpoint/resume), crates/crescent/src/qd.rs (novelty, MAP-Elites/QD bins, diversity) |
| Inputs | population, fitness from physics/MC |
| Outputs | history.csv, pareto.csv, all_evals.json, plates.txt (designs to plate) |
| Hard gates | primary fitness = MC-p05 SPG subject to floors; hard gates are rejections; novelty/diversity are secondary objectives only |
| Feeds GLOBAL metric G | Selects candidates; G ranks the plated set per wave (best-G plate goes to WHITEPAPER). G is not (yet) the in-loop fitness — hot path untouched. |

Spec of G: `docs/GLOBAL_METRIC.md`. Author: Jepson Taylor.
