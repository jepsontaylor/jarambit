# SHEATH v1 — engineering plan: automatic hard-sheath CAD, draw-force scoring and optimisation for jarambit knives

Author: Jepson Taylor (plan drafted by the Grok Bot executor, 2026-10-13). Status: **PLAN + first execution slice (PR-S1)**.
Branch `feat/sheath-v1`. Machine-readable roadmap: [`SHEATH_V1_ROADMAP.json`](SHEATH_V1_ROADMAP.json).

> Scope guard (COORD hard rules): SWITCHBACK-class titanium hiking/utility karambit only. The sheath is protective carry
> equipment. No combat/tactical framing. **SWITCHBACK is always fixed-sheath carry — never a ring-dangle.**
> Evidence levels are never mixed: `analytic_proxy` < `uncalibrated_fea` < `calibrated_prediction` < `physical_measurement`.
> **Nothing in this document or in `evidence/sheath/` is a physical measurement.** A target is never reported as a result.

---

## 0. Executive summary

* **Goal.** From any knife in the current CAD format (B-rep STEP + reference STL, or a crescent genome → `Pheno`), generate a
  closed hard sheath automatically, prove a collision-free draw path, predict the draw (unsheath) and insertion force curves,
  propagate tolerance/temperature/friction/wear uncertainty, and score it with a **two-sided** retention objective that plugs
  into evolution and the render pipeline.
* **Concept chosen for v1.** One-piece **PA12 (MJF/SLS) closed shell** (two faces + full-height rim band, open only along a
  computed mouth line), retention by **twin U-slot click-tabs** (one per face) whose bumps drop into the knife's closed guard hole
  from both sides, **straight-line draw along a computed direction** (C.9.3: 140° in the part frame, i.e. up-and-back toward the
  ring), mount = two-point strap/belt interface (Tek-Lok-class hole pair) on the rim band. Kydex thermoform and injection-moulded
  PA12/PA6-GF are tracked as manufacturing variants of the same geometry.
* **Draw-force window (key decision, §5).** nominal **30 N**, new-sheath acceptance **22–40 N**, whole-life envelope
  (−20…+60 °C, wet/grit, 1000 cycles) **15–50 N**, insertion **≤ 45 N**. This is lower than both source docs (50–70 N and 40–60 N);
  the justification is that (a) the inertial demand of running is ≤ ~4 N even at 2× the measured sacral peak, so retention margin is
  already ≥ 4× at 15 N, (b) an emergency one-handed draw through the finger ring should not need a full-arm yank, and a high peak
  that releases abruptly drives the hand (and blade) toward the body, and (c) snag/impact security is better bought with **directional
  retention** (the knife can only leave along one path; every other direction is a wall) than with a larger scalar force.
* **Historical first result (C.9.3; superseded, no feasibility credit):** the original unapproved-annotation run reported path search over 377 candidate paths → 53
  feasible; chosen straight draw at 140°; shell 22.9 g CAD (PA12 MJF), **27.1 g incl. 4 g mount allowance**; tab k = 28.5 N/mm analytic vs
  26.2 N/mm Morley-plate FEM (−7.8 %); per-side interference 0.61 mm; **predicted draw 30.8 N (28.4 N with FEM k), insertion 36.7 N**,
  tab root strain 1.5 % (allow 4 %); Monte Carlo (20k) p05/p50/p95 = **16.6 / 28.8 / 46.2 N**, 95.0 % inside the life window,
  78.5 % of new-condition samples inside 22–40 N; min swept edge-to-wall clearance 0.80 mm, sharp-edge rim ≥ 3.8 mm, sharpened edge
  ≥ 8.2 mm behind the mouth, no sharp edge passes over a detent. Running SF (nominal) 9.2 at the 5.1 g sacral peak; **fall/jump case
  (25 g, assumed) SF 1.9 nominal but only 1.0 at p05 → open risk R1**. These numbers are historical diagnostics;
  the regenerated `evidence/sheath/c93_v1/` is an explicit no-annotation rejection fixture with `INCOMPLETE`, null geometry
  and zero fitness. Current annotated comparison runs are in `c93_v12/` and `c10a_v12/`, also INCOMPLETE pending directional CAD.

---

## 1. Synthesis of the two source documents

Both documents were written against repo commit `0dbf908` and SWITCHBACK **C.9.2**; main now carries **C.9.3 rc3** (same envelope,
jimping change only, 66.773 g) and this plan uses C.9.3.

### 1.1 Common themes (adopted)

| # | Theme (both docs) | How v1 adopts it |
|---|---|---|
| T1 | The existing holder retention is a proxy (`F_ins = 6.6·wall³·detent`, `F_draw = 0.55 F_ins`, 1.5–45 N) and must not be silently re-tuned | New package `sheath/`; legacy `crates/redteam` holder rule untouched; new requirement set `RS-sheath-runner-v1` (PR-S2) |
| T2 | Generate the cavity from the **withdrawal path**, not by offsetting the seated knife (hooked blade traps) | `generate.build2d`: cavity = ⋃ₛ T(s)K ∩ D ⊕ clearance; path is searched, `path_infeasible` is a first-class result |
| T3 | Check the **whole motion**, not frames | v1: 1–2 mm/° sweep sampling of the planar sweep + buffered union (conservative); PR-S4: adaptive bound on max point motion |
| T4 | Separate **protection** (stiff shell) from **retention** (compliant tunable element) | Rim band + panels protect; U-slot click-tabs are the only compliant parts; tab L/b/wall/undercut/angles are genes |
| T5 | Report a **force–displacement curve**, work, release travel — not one number | `draw_curve.csv`, `curve_peak_n`, `draw_work_j` |
| T6 | Use full geometry (scallops/jimping), treat **both edges + tip** as hazards | Ingest detects sharpened boundary by through-thickness probe (≤ 1 mm at 0.6 mm inward) + 6 mm tip zone |
| T7 | Reuse the evidence system (`Obs`, scoped `Verdict`, `NotEvaluated`) | metrics carry `evidence_level` and per-group verdicts; puncture/mount/physical = `NOT_EVALUATED` |
| T8 | Nylon first; carbon only after measured complete-case mass | PA12 MJF baseline; Kydex/IM variants share geometry |
| T9 | Mass budget ≈ 18–28 g case; sub-70 g **kit** is impossible with a 66.8 g knife | v1 27.1 g incl. mount; kit ≈ 94 g; knife target remains knife-only |
| T10 | Elastic contact sims cannot prove puncture resistance | Puncture/cut-through stays physical (§8.4); geometry gives only rim/clearance margins |
| T11 | Renders show engineering results, labelled kinematic vs FEA vs measured | §10 |
| T12 | CLI must dispatch `sheath` exactly, never fall through to evolution | PR-S3 |

### 1.2 Where I disagree, and why

| Doc position | My position | Reason |
|---|---|---|
| Draw target 60 N (50–70 N) [doc A]; 50 N (40–60 N) [doc B] | **30 N nominal, 22–40 new, 15–50 life** | §5: inertial demand ≤ 4 N in running; a 1-finger-through-ring emergency draw should not require ≈ 6 kgf; high-peak snap releases are a self-injury mechanism; security vs snag is better achieved by directional retention + path geometry. The high numbers in both docs are not derived from a load case. |
| Secondary keeper / locked running mode [both] | **Not in v1 baseline**; kept as variant V-K for R1 (hard falls) | Jepson's requirement is a fast one-handed draw from a fixed sheath while running. A keeper adds a second action. We first quantify fall/jump demand with an IMU on the sheath (M6) and only add a keeper if the measured shock case needs it. |
| Replaceable retention insert as separate part [both] | **Integral click-tabs** in production; replaceable insert only for the prototype tuning kit | Cheap China manufacture favours one part, no assembly; tab geometry is a cheap gene; MJF lets us print 6–10 tab variants per build. |
| First FEA must be nonlinear finite-sliding contact (CalculiX) [both] | **Analytic + verified Kirchhoff-plate FEM first**, CalculiX contact in M3 as the calibration rung | The compliant element is a short cantilever plate; its stiffness is the dominant unknown and plate FEM verifies it (−7.8 % vs beam). Contact FEA is still required for ramp friction, nonlinearity and snap dynamics, but should not gate the first optimiser loop. |
| Don't latch into the small hole automatically [doc A] | **Detect it automatically, mark `review_required`** | The guard hole is the only closed full-thickness feature in the covered zone on C.9.3; a reviewer still signs off (interface `review_status`). If no admissible hole exists the generator reports `NOT_EVALUATED`. |
| Drain behind a baffle on the side [doc B] | Agree, but **the open mouth slot + U-slot kerfs already drain**; a tip drain is forbidden | Water exits through the 0.8 mm kerfs and the mouth; a baffled low-point drain is added in PR-S4 only if wet-retention tests show pooling. |
| C.9.2 as input | **C.9.3** | Current RC on main (#47). |
| Rotation/compound draw paths are needed for the hooked blade [doc A/B suggest families] | Search both; **straight translation won on C.9.3** | 377-candidate search: straight paths at 130–160° give 4.65–5.4k mm² outline vs ≥ 6.1k mm² for the best rotations; straight draws are also easier to learn and to make repeatable one-handed. |
| Gmsh as the mesher | Gmsh **blocked on xbabe2** (pip wheel needs `libGLU.so.1`, not installed; installing system packages on the shared box is an owner decision). v1 meshes 2-D with `triangle`; 3-D tet meshing waits for libGLU or the dolfinx container. | Environment fact. |

---

## 2. Requirements (draft `RS-sheath-runner-v1`, lands in PR-S2)

Hard (H) gates fail a design; soft (S) items enter the fitness. Every number is a design target unless marked as a measured value.

| ID | Requirement | Target | Type | Basis |
|---|---|---|---|---|
| R-COV-1 | Every sharpened boundary sample + 6 mm tip zone lies inside the sheath | 100 % | H | T6 |
| R-COV-2 | Seated sharpened edge depth behind the mouth line | ≥ 6 mm | H | ASSUMPTION; a 5 mm gap mouth excludes the IEC 61032 test finger (Ø 12 mm), depth stops fingertip pulp reaching the edge |
| R-CLR-1 | Min swept edge-to-wall in-plane clearance over the whole draw | ≥ 0.3 mm (design 0.8) | H | tolerance stack §4.3 |
| R-CLR-2 | Face clearance per side | 0.15–0.40 mm | S | rattle vs stick |
| R-RIM-1 | Solid rim band outboard of every seated sharp edge | ≥ 2.0 mm (design 3.0) | H | cut-through proxy; physical test §8.4 |
| R-DRW-1 | Draw peak, new, 23 °C dry | 22–40 N (target 30) | H | §5 |
| R-DRW-2 | Draw peak, any conditioned state (MC) | P(15–50 N) ≥ 95 % | H | §5 |
| R-INS-1 | Insertion peak | ≤ 45 N | H | one-handed re-sheath |
| R-STR-1 | Tab root strain at full deflection | ≤ ½ ε_allow (PA12 ε_allow ≈ 4 %) | H | Covestro snap-fit guide practice of designing at ½ permissible strain |
| R-SET-1 | Draw-force loss after 1000 cycles | ≤ 25 % | H | wear model + test |
| R-RET-1 | Inertial SF along draw axis at 2× sacral running peak (10.2 g) | ≥ 2.0 at MC p05 | H | MSSE sacral 5.13 g |
| R-RET-2 | Shock (fall/jump landing) SF at p05 | ≥ 1.0 (case value pending M6) | H (provisional) | ASSUMPTION 25 g |
| R-RAT-1 | Rattle: free play along any axis in seated state | ≤ 0.3 mm | S | §7.3 |
| R-PATH-1 | Draw direction usable one-handed with index finger in ring | angle to body-plane & torso ≤ TBD from fit trials | S | M5 |
| R-MASS-1 | Shell + mount | ≤ 30 g (stretch 22 g) | S | T9 |
| R-MFG-1 | Single moulded/printed part; min wall ≥ 1.0 mm; min slot ≥ 0.5 mm (MJF) ; draft ≥ 1° for IM variant | — | H for chosen process | DFM §9 |
| R-MNT-1 | Mount proof load in draw direction | ≥ 3× life-max draw = 150 N, no slip/crack | H | doc A used 3×; scaled to our window |
| R-TMP-1 | Function −20…+60 °C | draw stays in life window | H | §6 MC |
| R-DRN-1 | No standing water pocket after 30 s inverted-to-carry drip | ≤ 0.2 g retained | S | test |

---

## 3. Architecture and repository layout

```
sheath/                      # core tech (Python, offline CAD + FEM; CI-safe pure-python model)
  model.py                   # materials, Bayer/Covestro snap equations, plate/beam k, window, fitness, retention cases
  ingest.py                  # STEP/STL -> KnifeInterfaceV1 (planform, holes, ring, tip, sharp runs, thickness probe, hashes)
  generate.py                # SheathParams, draw-path sweep, cavity/outline, edge margins, mass, CadQuery 3-D solid + click-tabs
  fem_plate.py               # Morley Kirchhoff-plate FEM (scikit-fem) for panel / click-tab stiffness + closed forms
  run.py                     # end-to-end: ingest -> path search (multiprocess) -> retention design search -> FEM check -> MC -> CAD
  tests/                     # pytest: analytic, FEM, runner failure paths and solver evidence gates
docs/sheath/                 # this plan + roadmap json
evidence/sheath/c93_v1/      # no-annotation rejection fixture, null geometry/zero credit, SHA256SUMS
evidence/sheath/{c93,c10a}_v12/  # proposed-ramp diagnostics; directional CAD INCOMPLETE
evidence/sheath/ccx_tab_v1/  # independent ramp benchmark and hashed solver inputs/histories
requirements/RS-sheath-runner-v1.toml      (PR-S2)
crates/sheath/               (PR-S3)  Rust fitness/window/analytic + Verdicts; `jarambit sheath ...` CLI
fem_sheath/                  (PR-S5)  CalculiX/dolfinx contact decks for insert→seat→draw
```

Rust-first rule: the hot path of evolution (fitness of a candidate given metrics, analytic retention) moves to `crates/sheath`
(PR-S3). CadQuery/OCC geometry and FEM stay offline Python workers, exactly like `fem_solid/`.

Environment (xbabe2): `~/jarambit_render/venv-sheath` (Python 3.12, cadquery 2.8.0 / OCP 7.9.3, scikit-fem 12.0.2, shapely 2.2,
triangle 20250106, trimesh 5.1.1, numpy 2.5, scipy 1.18). Heavy runs detached in tmux, ≤ 48 threads on xbabe2, prefer xbabe3.

---

## 4. Geometry pipeline

### 4.1 KnifeInterfaceV1 (ingest)
* Source lock: STEP + STL SHA256 (C.9.3 STEP `3a818183…e919`, identical in `inputs/switchback_C9.3/` and `designs/switchback/C9.3/cad/`).
* B-rep volume/mass from OCC (C.9.3: 15 072.8 mm³ → 66.773 g @ 4.43 g/cm³, 1 solid — matches README 66.773 g).
* Planform = union of +z facets; holes with centroid/area; ring = largest hole; tip = boundary point farthest from ring.
* **Sharp edge detection**: boundary sampled every 0.5 mm, thickness ray-cast 0.6 mm inward; sharp if < 1.0 mm. C.9.3: 143.5 mm
  flagged in two runs (spine-side 70.5 mm, inner/concave 73 mm) + tip zone. Because the blade is now required sharp (~0 edge width)
  this probe is robust; serration/jimping that is full-thickness is not flagged (correct: jimping is not a cutting edge).
* `review_status = AUTO` until a human signs the annotation (doc A/B requirement).
* Crescent adapter (PR-S4b): fill the same interface from `Pheno.outline` (not `macro_outline`), `holes`, `edge_in`, `edge_sp`, `tip`, `t`.

### 4.2 Draw path and cavity
* Path families: rigid translation T(s) = s·d̂ (d at 10° steps, 120–240°), rotation about centre c (grid 60–180 × −10–120 mm, both senses).
* Mouth: line through (mouth_x, mid-thickness) normal to the initial mouth-point velocity; D = region behind it.
* Cavity C = (⋃ₛ T(s)K ∩ D) ⊕ c_edge ; outline O = C ⊕ rim ∩ D ; feasibility: knife fully leaves D before the sweep limit and O does
  not enter the grip keep-out (x < 60 mm ⇒ ≥ 60 mm of grip + ring exposed).
* Ranking: hard gates (all sharp inside, mouth depth ≥ 6 mm) then min outline area (∝ mass).
* Result C.9.3: straight at 140°, outline 4 662 mm², mouth opening ≈ 34 mm (by area method) along the diagonal mouth line.

### 4.3 Clearance and tolerance stack (design values; ASSUMPTIONS until process capability data)
| Item | Nominal | σ / band | Note |
|---|---|---|---|
| MJF PA12 wall | 1.0–2.0 mm gene | σ 0.10 mm | assumption; HP quotes dimensional accuracy class, to be measured on our printer/vendor |
| Bump height | gene | σ 0.05 mm | |
| Face clearance c_face | 0.25 mm | σ 0.05 mm | |
| Knife thickness (Ti grind) | from STEP | σ 0.03 mm | machinist pack tolerance to confirm |
| In-plane edge clearance c_edge | 0.8 mm | — | ≥ 3σ of print + 0.3 mm |
| Thermal: PA12 CTE ≈ 1e-4 /K vs Ti ≈ 9e-6 /K | −20…+60 °C | Δ ≈ ±0.4 mm over 100 mm | in-plane clearance must cover cold shrink at the tip pocket (PR-S4 check) |

### 4.4 3-D solid
Extruded outline (height t_knife + 2c_face + 2·wall) minus extruded cavity (open past the mouth), U-slot kerfs through each panel,
spherical-cap bumps on the tab inner faces. STEP + STL exported; CAD mass 22.94 g vs 2-D estimate 23.05 g (0.5 %).
PR-S4 adds: variable gap following the knife thickness map (mass −15–25 % expected), mouth lead-in chamfer, mount bosses, fillets,
drain, draft, and a true 3-D continuous collision check against the STL.

---

## 5. Draw (unsheath) force target window — justification

**Two-sided objective.** Too low → knife leaves the sheath under running vibration, impacts, inverted carry, falls. Too high → slow or
failed emergency draw, abrupt release toward the body, high insertion force (re-sheathing is when most self-cuts happen).

### 5.1 Lower side (retention demand)
Knife mass m = 66.77 g (B-rep). Quasi-static demand along the draw axis F = m·a (detent natural frequency, √(k/m) with k ≈ 50 N/mm
→ ≈ 140 Hz ≫ stride frequency ≈ 1.4–1.6 Hz and its low harmonics, so quasi-static is reasonable for the running case; it is NOT
reasonable for short shocks → M6 dynamic model).

| Case | a (g) along draw axis | m·a (N) | SF at 15 N (life floor) | SF at 30 N (target) | Source |
|---|---|---|---|---|---|
| Inverted static | 1 | 0.65 | 23 | 46 | — |
| Running, sacral peak | 5.13 | 3.36 | 4.5 | 8.9 | Peak sacral accel 5.13 ± 1.17 g, elite female runners, 14 km/h (MSSE abstract, ref [5]) |
| Running ×2 margin | 10.2 | 6.7 | 2.2 | 4.5 | margin on [5] (heavier runners, downhill, trail) |
| Fall / jump landing | 25 (ASSUMED) | 16.4 | 0.9 | 1.8 | **assumption** — measure (M6) |

So any sheath meeting the life floor (15 N) is safe for running vibration with ≥ 2× margin; the governing lower-side case is the
**shock** case, whose magnitude we do not yet know. That is why the floor is set at 15 N (≥ 2× running ×2) and why R1 is open.

### 5.2 Upper side (draw ergonomics)
* Draw is one-handed, index finger through the 25.4 mm ring, pulling along the computed path. The pull is resisted by the finger
  flexors through the ring and by the grip. No source with a validated "max acceptable emergency draw force" for knives was found;
  values are therefore **ASSUMPTIONS to be measured in M5** (n ≥ 10 users, gloved/ungloved, wet, cold; time-to-draw and
  force-at-release via instrumented sheath).
* 40 N (≈ 4.1 kgf) as the new-sheath ceiling keeps the draw a deliberate "click" rather than a yank, and bounds the release
  energy: with ~0.07 J of draw work (v1 curve), the hand overshoot after release stays small; at 60–70 N peaks the stored work and
  overshoot roughly double.
* Insertion ≤ 45 N: re-sheathing without looking requires controllable, low force (the hand is near the edge).

### 5.3 Window
nominal **30 N**; new **22–40 N**; life **15–50 N** (P ≥ 95 % in MC); insertion **≤ 45 N**. Score: piecewise-linear desirability,
1 at 30 N, 0.5 at 22/40 N, 0 at 15/50 N (`model.window_score`).

### 5.4 What could change the window
M5 user trials (upper side) and M6 sheath-mounted IMU recordings of running, jumping, falls (lower side). If measured shock demand
at p05 exceeds the 15 N floor, prefer (in order): directional geometry (deeper hook-over), dual detent, a second retention feature on
the guard lobe, and only then a keeper (variant V-K).

---

## 6. Retention mechanism and draw-force models

### 6.1 Mechanism v1
Twin U-slot click-tabs (one per face), bump on the free end, bump enters the closed 6 mm guard hole (C.9.3 at (85, −15)) from both
sides. Release requires both tabs to deflect by the per-side interference i = h_bump − c_face − (t_gap − t_local)/2 (C.9.3: t_gap 4.5 mm
max covered thickness, t_local 3.62 mm at the hole rim ⇒ i = 0.61 mm at h = 1.30 mm).

### 6.2 Analytic (analytic_proxy)
Tab stiffness at the bump (lever a = L − 2 mm): k = 3 (E/(1−ν²)) (b h³/12) / a³. Transverse force P = k i. Axial force over a ramp
of angle α with friction μ (Covestro/Bayer snap-fit guide [1]): W = P (μ + tan α)/(1 − μ tan α); insertion uses α_in, draw uses the
return angle α_out; two tabs ⇒ ×2. Strain ε = 1.5 h i / a² (guide Table 1, uniform cantilever).
Verification: guide worked example (P 32.5 N, μ 0.6, α 30° → 58.5 N) reproduced in `tests/test_model.py`.

### 6.3 FEM (uncalibrated_fea)
Morley Kirchhoff-plate element (scikit-fem), patch load over the bump disc.
* Verification: clamped circular plate with central patch load vs closed form w₀ = P/(16πD)(a² + r₀² ln(r₀/a) − ¾ r₀²)
  (Timoshenko & Woinowsky-Krieger [6], via reciprocity of the centre-load solution) — passes < 3 %.
* Tab: rectangle clamped at root vs plate-beam formula — passes < 15 % (Kirchhoff plate vs 1-D beam; 2-D effects).
* C.9.3 tab (L 13, b 9, h 2.0): FEM 26.47 → 26.23 N/mm (refinement 0.15 → 0.05 mm²; −0.9 %), analytic 28.45 (FEM −7.8 %).
* Solid (un-slotted) panel at the hole: 325.7 / 325.9 / 327.7 N/mm (3 levels) — ≈ 12× too stiff for a tunable click: a bump on the
  solid panel would need ≈ 0.05 mm interference for 30 N, far below print tolerance. **This is why tabs are mandatory.**

### 6.4 Draw curve
Bump track q(s) = T(s)⁻¹(bump) through the knife; local knife thickness under the bump by ray cast; per-side interference and the
local climb slope give the axial force via §6.2 (friction-only where the slope is ≤ 0). Current diagnostic curves are in
`evidence/sheath/c93_v12/draw_curve.csv` and `c10a_v12/draw_curve.csv`; the initial unapproved-annotation curve was withdrawn.
Limitations: quasi-static, rigid knife, no rate/viscoelastic effects, ramp angle taken from the climb slope capped at α_out.
The proposed ramp model differs from the exported spherical cap, so these curves do not validate retention feasibility.

### 6.5 Contact FEA (M3, calibrated rung)
CalculiX (node-to-surface large-sliding contact, NLGEOM) or dolfinx contact on the tab + knife-rigid body: insert → seat → dwell →
draw → unload, residual set. Mesh/increment convergence < 5 % on peak and work. Acceptance: analytic/plate model within ±15 % of
contact FEA on the nominal; if not, the analytic model is re-fitted (calibration factor recorded, never silently).

---

## 7. Uncertainty, temperature, wear, vibration

### 7.1 Monte Carlo (v1, 20 000 samples, in `run.py`)
Wall σ 0.10, bump σ 0.05, c_face σ 0.05, knife t σ 0.03, tab L σ 0.10 (mm); μ ~ U(0.20, 0.45) (dry → wet/grit; PA on steel
0.25–0.30 ×1.5 per guide Table 3 [1] is inside); wear ~ U(0, 0.10) mm bump height (ASSUMPTION for 1000 cycles); E multiplier
{1.25 @ −20 °C, 1.0, 0.70 @ +60 °C} w.p. {0.2, 0.6, 0.2} (ASSUMPTION pending DMA). C.9.3: p05/p50/p95 16.6/28.8/46.2 N; P(life) = 0.950;
P(new 22–40 N | new, 23 °C) = 0.785. Dominant variance: μ (≈ ±25 %), E(T) (−30/+25 %), interference tolerance (±0.07 mm on 0.61 mm).

### 7.2 Wear over cycles (M6)
Archard-type bump wear h_w = K·P·s/H per cycle with K from pin-on-disc of PA12 vs Ti-6Al-4V (to be measured; no trusted literature
value adopted); grit case with ISO 12103-1 A2 fine test dust; creep/stress relaxation of a seated tab (seated state has zero tab
deflection by design — the bump sits in the hole — so long-term creep under storage is minimal; this is a deliberate advantage of the
hole detent over friction-fit sheaths).

### 7.3 Vibration / rattle model (M6)
2-DOF base-excited model (knife in sheath, sheath on mount compliance) with piecewise detent force (−F_draw, gap, +contact) driven
by measured sacral/hip acceleration traces (public datasets or our own IMU) and a 0.5–200 Hz random-vibration profile per MIL-STD-810H
Method 514.8 [8] for transport. Outputs: unseat probability per km, peak relative displacement, impact count (rattle proxy),
noise proxy. Shock: half-sine pulses 5–50 g, 2–11 ms (MIL-STD-810H 516.8 [8] style) + IMU-recorded landings. Retention SF is then
computed on the dynamic response, not m·a.

---

## 8. Validation plan

### 8.1 Numerical ladder
1. Closed forms (done): snap equation, clamped plate, cantilever plate.
2. Mesh convergence per run (done for tab and solid panel; < 1 % at finest).
3. Contact FEA vs analytic (M3, ±15 %).
4. MC convergence: p05 stable to ±0.3 N between 10k and 20k samples (M2 check).
5. Physical correlation (M5): predicted vs measured peak within ±20 % on ≥ 3 tab variants; calibration fit on 2, held-out validation on 1.

### 8.2 Physical draw/insert test protocol (M5)
* Specimens: MJF PA12 (vendor A), 3 builds × 6 tab variants (L ±2 mm, h_bump ±0.2 mm), n = 3 each; plus 2 Kydex 100 thermoformed (2.0 mm).
* Knife: **blunt dimensionally-faithful dummy** (Ti or Al, edges radiused 0.3 mm) for force curves; real sharp knife only in a guarded jig.
* Rig: universal tester or motorised stand + calibrated load cell (≤ ±0.5 % FS), knife driven along the computed draw direction via a
  ring pin; sheath clamped through its real mount holes to a strap-compliance fixture. Speeds 50 mm/min (quasi-static) and 500 mm/min
  (draw-like) — ASSUMPTION, plus a hand-draw instrumented run.
* Record: full F–x, peak insert/draw, work, release travel, residual set (bump height by micrometer), mass, dims (CMM/calipers).
* Conditioning: 23 °C/50 % RH 48 h; −20 °C 4 h; +60 °C 4 h; wet (soak 1 h, drain 30 s); grit (ISO 12103-1 A2 dusted); 1000 cycles at
  0.5 Hz with force measurement at 1, 10, 100, 500, 1000.
* Friction: ASTM D1894-style sled μ for PA12 on Ti (dry/wet) to replace the U(0.20, 0.45) assumption.
* Flexural modulus vs temperature: ISO 178 / ASTM D790 bars from the same build, at −20/23/60 °C.

### 8.3 Retention-in-use tests (M6)
Sheath-mounted IMU + knife-mounted IMU, treadmill 10–16 km/h, trail downhill, 30 cm drop-jumps, controlled falls onto a crash mat
(fixture-held, not on a person with a real blade), 500 km cumulative running per variant; inverted shaking 10 min; MIL-STD-810H 514.8
random vibration (packaged) and 516.8 transit drop 1.22 m (packaged).

### 8.4 Edge-protection / cut-through tests (physical only)
Real sharp C.9.3 in a guarded jig: (a) lateral edge-into-rim push to 100 N (ASSUMED proof load) at 3 locations, (b) drop of the
sheathed knife 1.5 m onto concrete, tip-down / edge-down, 5×, (c) 1000 draw cycles with real edge then inspect for kerf depth.
Pass: no edge/tip exposure, kerf depth < 50 % of rim. The rim ≥ 2 mm gate is only a proxy until these exist.

### 8.5 Mount tests
Pull 150 N (3× 50 N life-max) along draw axis and 90° to it, 10 s, no crack/slip; 10k cycles at 50 N; strap and belt (38/50 mm) fixtures.

---

## 9. Manufacturing (cheap in China) — variants on one geometry

| Variant | Process | Notes / DFM gates |
|---|---|---|
| **V-MJF (baseline)** | HP MJF PA12 | No tooling; tabs/kerfs print as-is; min slot 0.5–0.8 mm; low-volume unit cost; dye black; tumble to remove powder from kerfs |
| V-SLS | EOS PA2200 SLS | same geometry; ρ 0.93 vs 1.01 → −8 % mass |
| V-IM | Injection-moulded PA12 or PA6-GF15 | 2-plate tool if mouth/kerfs aligned to pull direction; draft ≥ 1°; uniform walls; tab kerfs by side-shutoff; highest volume / lowest piece price, tooling cost to quote (no figures claimed here) |
| V-KYD | Kydex 100 thermoform 2.0 mm, two halves riveted/eyeleted | buck auto-generated from cavity (PR-S10); tabs replaced by formed detent dimple into the guard hole; heavier (ρ 1.35); cold impact toughness falls sharply (manufacturer data cited in Cliff Stamp's cold review [7]) |
| V-K | any + keeper | only if R1 needs it |

Supplier quotes are explicitly out of scope (COORD: do not contact manufacturers).

---

## 10. Fitness function and integration with evolution and rendering

### 10.1 Sheath fitness (implemented in `sheath/model.py::fitness`, Rust port PR-S3)
Hard gates (score = 0 if any): missing approved source-bound annotations or dependent CAD evidence, path infeasible,
sharp outside sheath, mouth depth < 6 mm, swept clearance < 0.3 mm, rim < 2 mm, tip reserve < 1 mm,
insertion > 50 N, tab strain > ε_allow, P(life window) < 95 %, P(new window) < 80 %, failed strength screen,
or p05 retention SF below the configured 2.0 floor at the 15 g design shock (including missing/nonfinite SF).
The p05 floor uses the source-bound knife mass during both candidate selection and final scoring.
After every hard gate passes, score = 1 / (1 + mass/30 g + cost_proxy). Proposed-ramp diagnostics receive zero
overall feasibility credit while the exported spherical bump differs from the directional retention geometry.

### 10.2 Sheath optimiser (PR-S7)
Genes (~15): mouth_x, path dir/centre, c_face, c_edge, rim, wall, tab L/b/h_bump, α_in/α_out, kerf, mount spacing, gap-map offset.
Two levels: (1) per-knife sheath optimisation (CMA-ES or NSGA-II mass vs P(life)) with analytic+plate k (≈ 30 s per knife on 40
cores today; the retention sub-search is 38 556 analytic evaluations); (2) contact-FEA re-scoring of the Pareto finalists.

### 10.3 Paired knife+sheath evolution
Knife fitness is unchanged (historical comparability). A separate **paired-system** score = knife score × sheath gate pass, with
sheath score as a secondary objective, computed for the knife shortlist only (sheath generation is too expensive for every genome).
Interface features that make a good sheath (a closed full-thickness hole in the guard zone, a straight-ish exit direction) become
soft knife objectives only after owner approval.

### 10.4 Render pipeline
Add sheath STEP/STL + hashes to the render manifest; one common assembly transform; outputs: sheath alone, seated assembly,
section through the tab, exploded view, **kinematic unsheath animation along the computed path (label: "kinematic")**, and a
synchronised draw-curve overlay (label: "analytic/uncalibrated FEA prediction" until M5). Never disable the knife source-hash guard.
Queued after the render/release PRs (COORD).

---

## 11. Red team

| # | Attack | Status / mitigation |
|---|---|---|
| R1 | Fall/jump shock | OPEN: the configured p05 SF>=2 floor at assumed 15 g now gates search and final scoring, but force/SF values describe proposed ramps rather than the exported spherical cap. Directional CAD, contact validation and M6 IMU confirmation remain |
| R2 | μ dominates variance; wet/grit could push > 50 N or < 15 N | MC covers U(0.2,0.45); measure (ASTM D1894); consider low-μ PTFE-filled PA or a return angle with lower μ sensitivity |
| R3 | Sharp edges near the wall during draw | RESOLVED (geometric): ±2° direction + ±2° rotation wobble swept into the cavity; c_edge 1.3 → min edge clearance 1.91 mm over all wobble poses (C.10a) |
| R4 | Guard hole detent is a single point — rocking/rattle about it | 2-D planar sheath + tight face clearance; rattle model M6 |
| R5 | Kirchhoff plate ignores bump contact stiffness, ramp geometry, large deflection | Contact FEA M3; tab strain is only 1.5 % so linearity is plausible |
| R6 | Planform from z-projection hides undercuts in a non-planar knife | Current knives are planar plates; ingest asserts the bbox z-range ≤ 12 mm and flags non-planar parts (PR-S4) |
| R7 | Sharp detection threshold could miss a thick-ground secondary bevel | Tip zone always hazard; reviewer sign-off; threshold sweep test |
| R8 | Diagonal mouth (34 mm opening) also covers part of the handle top (x 76–92 mm) | Grip keep-out keeps ≥ 60 mm exposed; owner check on hand fit (M5) |
| R9 | Thermal mismatch: PA12 shrinks ≈ 0.6 mm more than Ti over 80 K at 100 mm → tip pocket could bind cold | PR-S4 explicit cold-shrink clearance check at the tip pocket |
| R10 | Optimiser games the window with fragile designs (e.g. max bump height at a search bound) | MITIGATED: approved source-bound annotations, dependent-CAD completeness, p05 strength floor and existing fitness gates receive no mass compensation. Diagnostic candidate bounds are reported; directional CAD and held-out physical validation still required |
| R11 | Mass 27 g dominated by the large planar envelope; variable gap could save 15–25 % | PR-S4 |
| R12 | Emergency draw ergonomics unknown (direction 140°, force 30 N) | M5 user trials gate any "fast draw" claim |
| R13 | Gmsh unavailable → no 3-D tet FEM of the full shell yet | Owner decision: apt install libglu1-mesa on xbabe2, or run in the dolfinx container |
| R14 | Evidence confusion (predictions mistaken for results) | evidence_level + verdicts in every metrics.json; plan labels; render labels |

---

## 12. Milestones (details and PR list in the roadmap JSON)

| M | Name | Exit criteria |
|---|---|---|
| M0 | Plan + scaffold (this PR-S1) | plan/roadmap merged; C.9.3 end-to-end run reproducible; tests green |
| M1 | Requirements + Rust scoring + CLI | RS-sheath-runner-v1; crates/sheath; `jarambit sheath run` exact dispatch; CI unittest job |
| M2 | Geometry v2 | variable gap, mount, drain, mouth chamfer, 3-D continuous collision, crescent adapter, cold-shrink check |
| M3 | Contact FEA | CalculiX/dolfinx insert→draw; convergence; analytic within ±15 % or recalibrated |
| M4 | Optimiser | per-knife CMA-ES/NSGA-II; Pareto; xbabe3 batch; paired-system score |
| M5 | Prototype + bench | 6 tab variants × 3, force curves, μ, E(T); calibrated_prediction; user draw trials |
| M6 | Field + dynamics | IMU running/jump/fall data; dynamic retention model; wear 1000 cycles; edge cut tests |
| M7 | Render + release | sheath in render manifest, unsheath animation, docs; manufacturing pack (MJF + IM DFM + Kydex buck) |

---

## 13. References (real sources; values used are marked where they are guide/typical data)
1. Covestro (formerly Bayer MaterialScience), *Snap-Fit Joints for Plastics — A Design Guide* — mating/separation force
   W = P(μ+tanα)/(1−μ tanα), cantilever deflection/strain tables, friction Table 3, worked example. https://solutions.covestro.com/-/media/covestro/solution-center/brands/downloads/imported/1557218421.pdf (mirror: https://fab.cba.mit.edu/classes/S62.12/people/vernelle.noel/Plastic_Snap_fit_design.pdf)
2. EOS, *PA 2200* material data (laser-sintered part density 0.93 g/cm³, tensile modulus ~1650 MPa; EOS states typical values are not design allowables). https://store.eos.info/collections/polymer-powders/products/pa-2200-polyamide-12
3. HP, *HP 3D High Reusability PA 12* datasheet (part density ~1.01 g/cm³, tensile modulus ~1800 MPa XY) — values to be re-verified against the current datasheet revision.
4. SEKISUI KYDEX, *KYDEX 100* technical data (specific gravity 1.35). https://kydex.com/technical-resources/kydex-100/
5. "Peak Impact Accelerations in Elite Female Runners …", *Medicine & Science in Sports & Exercise* (abstract): sacral 5.13 ± 1.17 g, tibial 10.6–11.6 g at 14 km/h. https://www.ovid.com/jnls/acsm-msse/fulltext/10.1249/01.mss.0001057684.78716.32
6. S. Timoshenko, S. Woinowsky-Krieger, *Theory of Plates and Shells*, 2nd ed., McGraw-Hill, 1959 — clamped circular plate, central load.
7. C. Stamp, *Review: Kydex when Cold* (informal test; quotes manufacturer data that impact toughness drops > 10× sub-zero). https://cliffstamp.beyondt01micron.com/knives/reviews/kydex_cold.html
8. U.S. DoD, *MIL-STD-810H*, Method 514.8 (Vibration) and Method 516.8 (Shock, incl. transit drop).
9. ISO 12103-1 (A2 fine test dust); ASTM D1894 (coefficient of friction of plastic film/sheeting — method adapted); ISO 178 / ASTM D790 (flexural properties); IEC 61032 (test probes, test finger).
10. CadQuery import/export docs https://cadquery.readthedocs.io/en/latest/importexport.html ; Gmsh manual https://gmsh.info/doc/texinfo/ ; CalculiX https://www.dhondt.de/ ; scikit-fem (Morley element) https://scikit-fem.readthedocs.io/

Assumptions are labelled ASSUMPTION in the text; each has a closing milestone in the roadmap.

## v1.1 — Reviews 3–4 synthesis (2026-10-13)
**What we adopted:**
- Integral tabs for production, plus a swappable collar module for tuning (+0.67 g).
- Ring-actuated positive catch, recommended but pending M5 one-handed draw-time trials. The cost is ~0–0.13 s: HPTC 2018 measured 1.84 s for Level II vs 1.71 s for Level I. Pull-only stays the fallback.
- RS-sheath-runner-v1. The legacy proxy stays unchanged; it is inadequate because its 9 mm rule gives a max of ~9.6 N.
- KnifeInterface v1 with INCOMPLETE semantics.
- edge_sp and spine are never safe. The annotation file is PROPOSED, and Jepson must confirm the hook-back land.
- Swept cavity with ±2° wobble, a seating stop on the choil lobe, and 1.5 mm design tip reserve.
- Physical test matrix as specified in the reviews; Kydex is the fast comparator.
- Render labelling: kinematic preview vs solver-derived animation.

**What we rejected:**
- The 50–80 N window. The 5th-percentile female index-on-ring capacity is ~24 N, against a median of 59.5±21.4 N (Int J Ind Ergon 2010).
- New window: 35 N target, 28–45 N new, 20–55 N life, insertion ≤50 N.
- Lower bound: 15 g design shock (assumption: 2× the 7.5 g jump peak, PMC4101685), requiring SF ≥ 2 at p05.

**Calibration:**
- Bench coupons will measure Ti vs PA12 friction (ASTM D1894: dry/wet/ISO 12103-1 A2 grit) and E(T) (ISO 178). These narrow the μ and E priors in the Monte Carlo.

**C.9.3 v1.1 results:**
- Mass: 24.97 g shell; 29.1 g including mount.
- Draw: 34.2 N nominal. Monte Carlo p05/p50/p95 = 21.7/33.2/49.0 N.
- Window probability: 0.963 for the life window, 0.758 for the new window. The new-window gate (0.80) FAILS.
- Containment: minimum edge clearance 1.41 mm under wobble (R3 improved); tip reserve 2.8 mm.

**Open items:**
- CalculiX contact benchmark: the N2S master/slave roles were swapped so the convex knife corner is now the slave, but neither μ case converges yet. The FEM status is INCOMPLETE, so the draw window rests on analytic + plate-FEA results only.
- The drop-edge screen has a spurious FAIL: the mouth is counted as a wall.
- Puncture: elastic contact cannot prove cut-through resistance, so a guarded physical test is mandatory.


## v1.2 — review correction (2026-10-13, C.10a rc4 release candidate)
**Knife.** C.10a rc4 (`designs/switchback/C10a/cad/switchback_revC10a_ground.step`, sha 441cfabc284efd63…, true-sharp 0.15 mm apex, 64.84 g) is a release candidate; C.9.3 is retained for comparison. Rule: every cutting edge is sharp (~0 edge width) — only explicitly non-cutting geometry may be a land.
**Hook back = SHARP** (determined from drawings 01/02/04 + STATUS_C10A_RC.md): the outer convex back is the continuation of the spine edge to the point; C.9.3 only had a modelled tip-zone flat that C.10a removes. It is now an annotation `declared_sharp` region and is no longer a bumper land. Retention/bearing lands: guard-hole rim (closed hole) and choil lobe only. Annotation review: delegated by Jepson 2026-10-13 (revocable).

**CalculiX tab benchmark (ccx 2.21, docker jarambit-sheath:s1).** Node-to-surface failed: chatter of the knife corner between master facets (μ=0 stalled at t=0.075; earlier 204 N spike was a corner poking through the slave face). Fix: SURFACE TO SURFACE large-sliding penalty contact, filleted knife corner r 0.3 mm, increment 0.002–0.005. Penalty-insensitive (K 9 000 vs 90 000 N/mm³: 7.98 vs 8.05 N). 4-mesh ladder (μ 0.3): 13.98 / 13.92 / 13.85 / 13.77 N per tab, last-two change 0.53 % (< 5 % gate). Reconciliation with the ~22 N hand calc: plain Bayer 21.9 N assumes the ramp keeps its angle; the tab end rotates θ = 1.5 i/a = 8.4°, so α_eff = 26.6° → 16.3 N (rotation-corrected Bayer). ccx / corrected = 0.844 (μ 0: 0.91); residual from load-point offset and bump compliance. `run.py` now applies the rotation correction × 0.844 to draw, insertion and MC (evidence `evidence/sheath/ccx_tab_v1`). Still uncalibrated_fea until coupon bench (M5).

**Directional bump CAD remains INCOMPLETE.** The previous land-first 100% and drop-edge MARGINAL results assumed
a bump radius of 2.690341 mm with 0.3 mm hole clearance, directional ramps within ±20° and non-camming lateral flanks.
Both actual CAD paths instead export a spherical cap with a 1.6 mm base radius; at height 1.7 mm its maximum projected
radius is 1.602941 mm, leaving about 1.3874 mm radial clearance in the reviewed guard hole. Ramp angles and cam sectors
have no effect on that solid. The previous containment result is withdrawn. First-contact land fraction/margin,
edge-drop and rattle are now null/INCOMPLETE, and proposed-ramp force/MC/SF values cannot establish feasibility.
Implement and validate the directional geometry before rerunning these dependent screens; guarded physical drop/cut
testing remains required. The exported spherical cap is retained for diagnosis.

**Friction split + wall cap.** New (23 °C, unworn, clean dry) μ U(0.20,0.32) ASSUMED; life (dry/wet/grit, 5000 cycles) μ U(0.20,0.45). Wall search 1.0–2.8 mm.

**Regenerated results (PR #56, 20k MC; force values are proposed-ramp diagnostics).**

| | C.10a rc4 (release candidate) | C.9.3 |
|---|---|---|
| mass incl. 4 g mount | 38.34 g | 38.44 g |
| diagnostic tab parameters | wall 2.8, L 18.0, b 7.0, undercut 1.95, alpha_out 30.0 | wall 2.8, L 18.0, b 7.0, undercut 1.95, alpha_out 30.0 |
| draw / insertion (diagnostic) | 35.1 / 35.1 N | 35.1 / 35.1 N |
| MC life p05/p50/p95 (diagnostic) | 23.8 / 34.5 / 48.3 N | 23.8 / 34.5 / 48.3 N |
| P(new) / P(life) (diagnostic) | 0.851 / 0.985 | 0.851 / 0.985 |
| min edge clearance / rim / mouth depth / tip reserve | 1.91 / 4.91 / 6.98 / 3.30 mm | 1.91 / 4.91 / 8.24 / 3.30 mm |
| actual spherical-cap radial clearance | 1.359 mm | 1.359 mm |
| land-first / edge-drop / rattle / force validation | INCOMPLETE | INCOMPLETE |
| retention SF p05 @15 g (diagnostic) | 2.50 | 2.42 |
| fitness | INCOMPLETE, infeasible, 0 | INCOMPLETE, infeasible, 0 |

The track curve is uncorrected; the rotation/CalculiX correction applies only to scalar/MC predictions.
Neither curve validates the spherical export. All independent screen values remain preliminary diagnostics.
Regeneration ran under memcap 32G at nice 19, CPU only with four workers. The handed-back v12b scratch snapshot was untouched.
Solver decks/histories and all committed comparison artifacts are covered by SHA256SUMS.
