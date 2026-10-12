# genotype/ — Encoding + validators

**Role directory (map only).** The code lives in the Cargo workspace; this directory exists so the top-level tree reads as the technology stack. Crates were NOT renamed (that would break `cargo` paths, CI and the live wave worktrees). See `TECHNOLOGY_MAP.md`.

| | |
|---|---|
| Code | crates/genotype (20-gene + grade, limits/bounds), crates/crescent/src/{genome,gates,c4_ref,c5_ref,c6_ref}.rs (crescent genotype, D1 owner-lock gates), crates/redteam (red-team reject gate) |
| Inputs | genome CSV / gene vector + Ti grade |
| Outputs | validated Genotype or a reject reason (quarantine.csv) |
| Hard gates | ring ID 25.4 ± 0.5 mm (≥ 25.4 nominal) · blade ≥ 3.375 in (85.725 mm) on tip-to-heel, horizontal reach and sharpened arc · sharpened edge ≤ 4.0 in · grip 60–80 mm · single connected solid · Ti only · 0.1 mm stock · no stick-figure priors (crescent C.6 anchor). Rejections, never penalties. |
| Feeds GLOBAL metric G | Gatekeeper only: a rejected genome never gets a G. Every term of G is evaluated on a validator-legal genome. |

Spec of G: `docs/GLOBAL_METRIC.md`. Author: Jepson Taylor.
