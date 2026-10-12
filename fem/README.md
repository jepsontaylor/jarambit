# fem/ — Finite-element verification

**Role directory (map only).** The code lives in the Cargo workspace; this directory exists so the top-level tree reads as the technology stack. Crates were NOT renamed (that would break `cargo` paths, CI and the live wave worktrees). See `TECHNOLOGY_MAP.md`.

| | |
|---|---|
| Code | crates/physics (beam surrogate, DKT+membrane plate fem.rs, fine.rs, calib.rs, verify.rs), crates/crescent/src/fem.rs (D1 plate screen, solid C3D tip submodel, twist body+tip), crates/cli/src/fem_smoke.rs |
| Inputs | phenotype outline/thickness field, load cases |
| Outputs | von Mises fields, SF maps, capacities (N), plate JSON (mesh xy/tris/env_vm/sf), *_solid.json |
| Hard gates | yield 828 MPa (provisional joint thin+hot screen) · lateral hiker 180 N / hunter 260 N (aim 286) at cert min(0.25,0.125 mm²) AND strict 0.0625 mm² · chord torsion 1.82 N·m (tip-only default hard; body + tip-submodel) · ring pull 1500 N · failure sequence hand/blade ≥ 1.2 (SOFT until met) · solid tip SF ≥ 1.0 · mesh: 4 mm tip-load zone excluded on plate, solid submodel resolves it; convergence per docs/calibration/knife_convergence.csv |
| Feeds GLOBAL metric G | solid_tip_SF → tip term (w1); SPG(cert) → spg term (w2); seq_ratio → seq_gap (w5). |

Spec of G: `docs/GLOBAL_METRIC.md`. Author: Jepson Taylor.
