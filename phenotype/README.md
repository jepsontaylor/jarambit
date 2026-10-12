# phenotype/ — Geometry → CAD

**Role directory (map only).** The code lives in the Cargo workspace; this directory exists so the top-level tree reads as the technology stack. Crates were NOT renamed (that would break `cargo` paths, CI and the live wave worktrees). See `TECHNOLOGY_MAP.md`.

| | |
|---|---|
| Code | crates/phenotype (outline → watertight STL + faceted MANIFOLD_SOLID_BREP STEP; mesh.rs), crates/crescent/src/{pheno,geom,export}.rs (crescent outline, grinds, tip outline, stock thickness, brand pad, STEP export) |
| Inputs | validated Genotype |
| Outputs | outline polygon (mm), *.step, *.stl, *_genome.csv, mass (g) |
| Hard gates | watertight + single shell; grind law per edge; tip outline inside stock; 0.1 mm stock quantisation; holder envelope (docs/HOLDER_ENVELOPE.md, +1 mm) |
| Feeds GLOBAL metric G | mass_g → mass_pen term; outline → aes term (C.6 aesthetic score); STEP/STL is figure (a) in every WHITEPAPER callout. |

Spec of G: `docs/GLOBAL_METRIC.md`. Author: Jepson Taylor.
