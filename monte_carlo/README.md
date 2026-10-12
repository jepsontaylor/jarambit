# monte_carlo/ — Robustness over manufacturing + media

**Role directory (map only).** The code lives in the Cargo workspace; this directory exists so the top-level tree reads as the technology stack. Crates were NOT renamed (that would break `cargo` paths, CI and the live wave worktrees). See `TECHNOLOGY_MAP.md`.

| | |
|---|---|
| Code | crates/monte_carlo |
| Inputs | Genotype, seed, n samples |
| Outputs | p05 capacities, strength-per-gram distribution |
| Hard gates | exact-n tolerance cloud (CNC/waterjet), temperature −10…100 °C (yield at 100 °C governs SF maps), heterogeneous cut media mix; thread-count-independent seeding |
| Feeds GLOBAL metric G | SPG is the MC p05 (search level) / certified value (plate) → spg term. |

Spec of G: `docs/GLOBAL_METRIC.md`. Author: Jepson Taylor.
