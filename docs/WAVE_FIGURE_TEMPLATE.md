# Per-wave FEM metrics plate — standard template

Owner directive (Jepson Taylor, 2026-10-11): **one high-resolution plate per research wave**, same layout every wave, produced retroactively for all completed waves and for each new wave as it lands.

## File naming and location
- Primary: `out/mh1/heatmaps/wave{N}_FEM_metrics.png` (≥300 dpi; current renderer writes 320 dpi, 4800×3072 px) + `wave{N}_FEM_metrics.pdf` (vector, heatmap rasterised).
- Supplementary load-case sheet (same title): `wave{N}_best_SPG{fit}_wgt{mass}g_loadcases.{png,pdf}` — `.` → `p`, minus → `m` (e.g. `wave4_best_SPG14p85_wgt33p4g_loadcases.png`).
- Sub-batches (island groups) of a wave: `out/mh1/heatmaps/mh1_groups/wave{N}-{group}_FEM_metrics.{png,pdf}`.
- Machine-readable index: `out/mh1/heatmaps/index.json` (fitness, mass, blade inches, gate flags, capacities at −10/20/100 °C, min SF, calibrated flag, file list).

## Wave numbering (retroactive)
| N | run dir | note |
|---|---|---|
| 0 | out/smoke | pre-constraint scaffold — no outline/report artifact, **not rendered** |
| 1 | out/smoke_constraints | first constrained evolve |
| 2 | out/bench10k | MC 10k benchmark |
| 3 | out/fem_smoke | plate-FEM-in-loop smoke (JARAMBIT_FEM=1) |
| 4 | out/mh1 (17 mc10k groups) | plate = best p05 across groups; per-group plates in mh1_groups/ |
| 5+ | next wave (mh1 mc50k s2004-2006, mh2, …) | append here |

## Which design goes on the plate
1. Preferred: top-fitness design that passes **blade ≥ 3.375 in (85.725 mm) on all three** of tip_to_heel / horizontal_reach / sharpened_arc **and** floors hiker 180 N / hunter 260 N / ring 1500 N **after FEM calibration** → badge "FEM-CALIBRATED".
2. If none: top-fitness design that passes the hard geometric gates (red-team Ok) → badge **"FEM-UNCALIBRATED"**, plus **"QUARANTINED: blade < 3.375 in"** if it fails the blade rule and **"floors … on plate: FAIL"** if the plate check misses a floor. Never hide a failing gate.

## Layout (15 × 9.6 in landscape)
- **Title**: `Wave {N} — {label} | Fitness {x.xxx} N/g | Est. weight {yy.y} g` (fitness = MC-p05 strength-per-gram, or robust plate N/g for FEM-in-loop waves; weight = phenotype area × stock × ρ).
- **Subtitle**: FEM model + calibration status + load envelope.
- **Badge row**: calibration · blade-length gate · hard geometric gates · floors on plate.
- **Panel 1** von Mises heatmap: per-element envelope (max over load cases at their design loads), turbo colormap, MPa.
- **Panel 2** safety-factor heatmap: SF = σy(100 °C)/σvm envelope, RdYlGn 0–4, min-SF element marked (×).
- **Panel 3** metrics table: blade tip-heel / horizontal reach / edge arc in **inches (mm)** with ≥3.375 in PASS/FAIL; grip mm; ring ID mm; stock/material; weight (+geometry cross-check); fitness; beam surrogate S and repo fem.rs plate value; plate capacities and hiker/hunter/ring SF at −10/+20/+100 °C; twist and tip-pry SF; temperature notes.
- **Panel 4** Pareto inset: surrogate S vs mass for that wave's front, this design starred; grey = all quarantined.
- Footer: source dir, author Jepson Taylor, generator.

## Load cases (current, FEM-uncalibrated)
| case | BC | load |
|---|---|---|
| tip lateral | ring-hole edge clamped | 260 N out-of-plane at tip (hunter floor; hiker SF = cap/180) |
| tip twist | ring-hole edge clamped | 1.26 N·m about tip chord axis (180 N × 7 mm half-height; proxy, not a floor) |
| tip pry | ring-hole edge clamped | 260 N in-plane, ⟂ to ricasso→tip chord |
| ring pull | ricasso band seated | 1500 N on ring-hole edge (−y) |
Peaks exclude elements within 4 mm of the tip load patch (St-Venant). Blade stresses carry the serration knock-down h/h_eff (lateral, twist) and (h/h_eff)² (pry), as in fem.rs. Yield: Ti-6Al-4V 880 MPa, Ti-3Al-2.5V 620 MPa at 20 °C, linear derate (−0.11 / −0.12 %/°C).

## Solver
`ops/wave_figures/plate_fem.py` — offline Python, plotting only (not in the search loop). Flat Kirchhoff plate, CST membrane + DKT bending, refined `triangle` mesh (q30, ≤0.6 mm²). DKT is built numerically from the Batoz 1980 definition (`Plate2`); patch-verified on unstructured meshes: cantilever deflection 0.98–1.00 and stress 1.00–1.03 of beam theory; uniform tension 0.99. The closed-form `dkt_b` port of fem.rs passes on the structured right-triangle test mesh but **fails on unstructured meshes (deflection ≈0.06–0.7 % of beam)** in this port — grok to check fem.rs with an unstructured-mesh unit test.
Run: `python ops/wave_figures/make_wave_figs.py <repo_root>` (needs numpy, scipy, matplotlib, triangle, shapely).

## Calibration hand-off
When grok's fem.rs per-element export + MC↔FEM calibration land, the renderer switches the source of panels 1–2 to that export and the badge to FEM-CALIBRATED; the template does not change.
