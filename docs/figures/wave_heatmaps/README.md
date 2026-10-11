# Per-wave FEM plates (wave 1-4) — FEM-UNCALIBRATED, PRE-BLADE-FIX

Copied from `out/mh1/heatmaps/` (box copy kept there) on 2026-10-11. Rendered by `ops/wave_figures/make_wave_figs.py`
per `docs/WAVE_FIGURE_TEMPLATE.md` from an offline Python port of fem.rs DKT+CST on a refined mesh.

- **FEM-UNCALIBRATED**: no per-element export from fem.rs and no MC<->FEM calibration yet.
- **PRE-BLADE-FIX / QUARANTINED**: every design shown was evolved under the inverted blade rule
  (fixed in 444a74d); all have ~44 mm tip-to-heel and are under 3.375 in on all three measures. None is a winner.
- Hunter 260 N floor fails on the plate for every wave. Floors stay 180 / 260 / 1500 N.

## Wave 5 — first LEGAL-blade winner (post-fix, 2026-10-11) — FEM-UNCALIBRATED

`wave5_FEM_metrics.{png,pdf}`, `wave5_best_SPG7p04_wgt48p9g_loadcases.{png,pdf}`; source `out/smoke_legal_blade`
(short smoke: pop 64, 2 islands, 15 gens, MC 512, JARAMBIT_FEM=1, seed 4242; binary at b46c774 =
blade-angle knob 152ad95 + FEM caps). Rendered with `WAVE_TIP=far ops/wave_figures/make_wave5_legal.py`
(tip = farthest blade node from the ricasso; the max-y pick lands mid-arc on raked blades).

- Blade: tip-heel 89.6 mm (3.526 in) / reach 88.8 mm (3.496 in) / edge 100.7 mm (3.964 in): all three >= 86.225 mm, edge <= 101.6 mm. Red-team Ok.
- Search score (repo fem.rs coarse plate, 70 nodes): 385 N lateral, robust 7.045 N/g, 48.9 g, Ti-6Al-4V 4.5 mm.
- **Offline refined plate (6657 tris) disagrees: lateral 171/166/151 N at -10/20/100 C => hiker 180 FAIL, hunter 260 FAIL**; ring pull 5.9-6.7 kN PASS. Min SF@100 C 0.58 at the grip/ring neck.
  The coarse repo plate is ~2.3x unconservative here; mesh convergence + MC<->FEM calibration still owed before any promotion.
- mh1 10k/50k outputs remain tagged PRE-BLADE-FIX (out/mh1/PRE_BLADE_FIX.md).
