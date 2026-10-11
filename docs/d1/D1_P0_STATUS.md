# D1 review gaps: P0 status (jarambit, SWITCHBACK-class titanium hiking/utility karambit)

Owner: Jepson Taylor. Executor: Grok Bot, 2026-10-11 (America/Denver). Branch `exec/d1`, worktree xbabe2 `~/jarambit/.agent/worktrees/exec-d1`.
CPU only (nice 19). Flywheel GPUs were not touched. wave15 (xbabe2) and wave16 (xbabe3) ran to completion under the pre-D1 rules. Their collector/plates were NOT run by D1; they were left alone.
**Nothing is promoted.** Every design below still needs Jepson's aesthetic sign-off, and none of them passes everything anyway.

Re-screen command: `jarambit crescent-d1 --genomes name=path,... --out out/d1_p0` (`crates/cli/src/crescent.rs::d1`).
Raw output: `out/d1_p0/d1_rescreen.{md,csv}` and `out/d1_w15w16/` (committed under `docs/d1/`).

## Baseline rules used in D1
- Screening yield **828 MPa**, provisional (TIMET Ti-6Al-4V Gr5 annealed minimum, 120 ksi). The previous value was 880 MPa typical, so the knockdown is 0.941. 828 MPa is **not** rounded to 830.
- Robustness is now **JOINT thin+hot**: `F = F20 x ((t-0.1)/t)^2 x yield(100C)/yield(20C)` for bending, and `^1` for the ring membrane. This is a product. It replaces `min(f_T, f_t)` in `fem::run_b`, `fem::certify`, the strict check, `refine` and `rescore`.
- Certification is min(0.25, 0.125 mm^2) with no bias. Strict is 0.0625 mm^2. Floors stay hiker 180 / hunter 260 / ring 1500 N. PASS means all three at certification **and** hunter at strict.
- C.6 SWITCHBACK thin stock (3.175 mm; ground STEP 46.93 g) is a **REFERENCE** only. Its rows are labelled REF and are never ranked against evolved parts.

## 1) Crescent twist: chord torsion vs bending couple (P0-1)
**Bug confirmed and fixed.** The plate DOFs are (u, v, w, w_x, w_y). A torque T about the unit chord d does work through grad w = phi*(-d_y, d_x), so the consistent slope load is **T*n** with n = (-d_y, d_x).
The pre-D1 crescent loaded along **d**. That is a **bending couple** about the in-plane normal, not chord torsion. (The legacy `physics::fine` jarambit path already used n correctly.)
The old load is kept as `couple20_nmm` for the record only.

Unit tests (`crates/crescent/src/tests.rs`, all PASS):
- `d1_st_venant_alpha_matches_table`: the exact 3D-elasticity St-Venant series alpha(b/t) matches the table values 0.208/0.246/0.267/0.282/0.312/0.333 within 1 %.
- `d1_chord_torsion_vs_bending_couple_strip`: rectangular strip 200 x 20 mm at 30 deg, clamped at one end, with the load at the other end.
  - The n-load gives thin-strip torsion 3T/(bt^2): plate/theory = **1.000** at b/t = 10, 4 and 3.
  - The d-load gives beam bending 6M/(bt^2): ratio **1.000**.
  - Plate-to-3D St-Venant factor: **1.067** (b/t 10), **1.183** (b/t 4), **1.247** (b/t 3). The Kirchhoff plate is unconservative for thick sections, so the knife fixture now multiplies by the 3D factor at the peak section (b measured along n through the peak).
- `d1_knife_fixture_reports_torsion_and_couple`: torsion and couple are distinct load cases on the knife (C.6 seed: 419 vs 650 N·mm at 20 C).
- `d1_joint_factor_is_product`, `d1_genome_csv_roundtrip_is_exact`: PASS.

Proposed floor: 1.82 N·m = 1820 N·mm first yield in the chord-torsion fixture, joint thin+hot with the 3D correction. Fixture: ring bore clamped, torque at the 2 mm tip patch, peak search outside 4 mm of the tip.

| design | chord-torsion plate @20C N·mm | 3D k (b/t) | joint+3D N·mm | **SF vs 1.82 N·m** | peak dist from tip | body (>15 mm from tip) joint N·mm (SF) | hand side joint N·mm | pre-D1 couple "twist" SF |
|---|---|---|---|---|---|---|---|---|
| wave14_c03 | 1286 | 1.167 (4.4) | 970 | **0.53 FAIL** | 4.2 mm | 6214 (3.41) | 24702 | 1.05 |
| wave13_c01 | 1069 | 1.153 (4.7) | 816 | **0.45 FAIL** | 4.1 mm | 5270 (2.90) | 31779 | 0.92 |
| wave13_c07 | 1117 | 1.148 (4.9) | 867 | **0.48 FAIL** | 4.1 mm | 6012 (3.30) | 27403 | 0.90 |
| wave14_c01 | 1328 | 1.153 (4.7) | 1014 | **0.56 FAIL** | 4.1 mm | 6577 (3.61) | 23499 | 1.17 |
| REF C.6 thin 3.175 (reference only) | 414 | 1.108 | 320 | 0.18 | 4.1 mm | 1990 (1.09) | 10205 | 0.34 |

**Result: FAIL on the tip-patch fixture for every design (SF 0.45 to 0.56).** In every case the peak sits on the thin ground tip right at the 4 mm exclusion boundary. This is first yield of the tip itself under a torque applied at the tip.
Away from the tip (>15 mm) the same torque gives **SF 2.9 to 3.6 (PASS)**. The hand side is SF > 12.
**Owner decision needed:** which fixture the 1.82 N·m floor applies to (tip-local, or body/neck with a tip submodel). Until then the floor is advisory and is not gated in evolve.
The old "C.6 twist SF 1.41" is not reproduced by this fixture. In this fixture the pre-D1 couple SF for the C.6 thin reference is 0.34. Treat the 1.41 number as a different fixture.

## 2) Yield allowable (P0-2)
`physics::TI_6AL_4V.yield_mpa = 828.0`. `TI64_YIELD_TYPICAL_MPA = 880.0` is kept for the record. The knockdown is documented in `docs/CALIBRATION.md` §7.
All workspace tests stay green at 828 (64 pre-existing + D1 tests).

## 3) Joint robustness re-screen at 828 MPa (P0-3)
| design | mass g | t | joint lat N (cert) | SF hiker (180) | SF hunter (260) | joint ring N | SF ring (1500) | strict 0.0625 joint lat (SF hunter) | **828 joint** | pre-D1 880/min lat (SF hunter) |
|---|---|---|---|---|---|---|---|---|---|---|
| **wave14_c03** | 76.95 | 5.8 | 280.2 | 1.557 | 1.078 | 12913 | 8.61 | 269.8 (1.038) | **PASS** (thin: +3.8 % at strict) | 308.3 (1.186) |
| **wave13_c01** | 74.37 | 5.6 | 234.4 | 1.302 | **0.902** | 12521 | 8.35 | 248.6 (0.956) | **FAIL** | 258.3 (0.993) |
| wave13_c07 | 74.03 | 5.5 | 237.4 | 1.319 | 0.913 | 12585 | 8.39 | 214.5 (0.825) | FAIL | 261.8 (1.007) |
| wave14_c01 | 76.38 | 5.8 | 269.2 | 1.496 | 1.035 | 14275 | 9.52 | 260.3 (1.001) | PASS (0.1 % margin at strict) | 296.2 (1.139) |
| wave15_c01 (pre-D1 certified) | 71.65 | 5.7 | 252.6 | 1.403 | 0.971 | 11885 | 7.92 | 243.9 (0.938) | FAIL | 278.1 (1.070) |
| wave15_c02 | 71.82 | 5.7 | 228.5 | 1.269 | 0.879 | 12422 | 8.28 | 242.0 (0.931) | FAIL | 251.6 (0.968) |
| wave15_c03 | 71.51 | 5.6 | 241.6 | 1.342 | 0.929 | 12500 | 8.33 | 233.9 (0.900) | FAIL | 266.1 (1.024) |
| wave16_c01 (pre-D1 certified) | 71.66 | 5.8 | 262.7 | 1.459 | 1.010 | 12754 | 8.50 | 246.5 (0.948) | FAIL (strict) | 289.1 (1.112) |
| REF C.6 thin 3.175 (reference only) | 48.34 | 3.2 | 54.8 | 0.305 | 0.211 | 9776 | 6.52 | 54.3 | n/a (reference) | 62.1 |

Hiker and ring pass everywhere. Hunter (260 N) is the binding floor.

**Reproducibility finding (blocks trust in the old records).** Rebuilding wave13_c01 from its on-disk genome CSV gives the same geometry (holes and mass to 0.01 g). Under the **old** rules it now certifies at 258.3 N, not the recorded 292.5 N. The 18:02 binary that ran wave13 gives the same 258.3 N, so this is not a code change.
The lateral peak moved from the ring neck (13.0, 0.1) to a perforation ligament at (98.8, 2.6). The genome CSV was written at 4 decimals (`{:.4}`), and a through-perforation ligament is mesh- and position-sensitive.
- Fixed: `Genome::csv_row` now writes full round-trip precision, with a bit-exact test.
- All earlier on-disk genomes are only 4-decimal approximations of the certified designs.
- wave14_c03 reproduces within +2 %, with the same peak location at the ring neck.
- wave15 also shows many search-legal designs failing certification (search-to-cert gap on perf ligaments).

## 4) Grind export (P0-4)
- **Gap:** the STEP is a faceted MANIFOLD_SOLID_BREP of the raster thickness field. It is **not** a machining release, and it does not carry the evolved grind law. It is also not the SWITCHBACK fixed grind bands.
- **Implemented (real):** `export::grind_law_json`. Per sharpened edge it writes the half-angle, the edge thickness et, and the edge curve C(s) at 0.25 mm. It also gives the inward normal N(s), the grind width w(s) = (base(x) - et)/(2 tan theta) with the taper law base(x), and the land (grind-to-flat runout) line.
- **Geometry:** each grind face is the analytic ruled surface S(s,u) = C(s) + u (N(s), tan theta). Files: `docs/d1/wave14_c03_grind_law.json`, `wave13_c01_grind_law.json`. wave14_c03 values: inner 17.58 deg, spine 20.81 deg, et 0.771 mm, t 5.8 tapering to t_tip 3.246 mm.
- **Stub:** an analytic STEP B-rep is not implemented. It needs a B_SPLINE_SURFACE_WITH_KNOTS of degree (3,1) per grind face, trimmed ADVANCED_FACE at the land curve and the taper plane, planar flats, and side walls. ETA ~1 working day (6 to 8 h) including a STEP validator round-trip. Until then, CAM must use the grind-law JSON plus the flat outline, not the faceted STEP.

## P1/P2 status (after P0)
- (5) Seed genome is on disk. **wave14_c03**: `docs/lattice/wave14_c6_through/wave14_c03_fit_genome.csv` (4-dec, reproduces). STEP: xbabe2 `~/jarambit/.agent/worktrees/exec-lattice/out/wave14_c6_through/wave14_c03_fit.step` (13.4 MB faceted, md5 ff3400741e36c07acfb63a7e4c65a58f; not in git). wave13_c01 stays the lighter control, but it **fails** 828 joint (SF hunter 0.90).
- (8) The failure-sequence proxy is **real** (`Fem::seq_ratio`): hand-zone onset over blade-zone onset, min over lateral, chord torsion and pry.
  - Result: **FAIL** for every evolved design (0.83 to 0.97, lateral governs; target ≥1.2). The hand side yields before the blade zone under the lateral overload, at the ring neck or the perf ligament near the ricasso.
  - This is the main argument for the continuous full-thickness neck and rails.
- (9) Status of each item:
  - tip exclusion: measured, not solved. The torsion peak always sits at the 4 mm exclusion edge, so a tip submodel is needed. **Stub.**
  - ring peel: **stub** (only ring pull 1500 N exists).
  - fatigue: **stub**.
  - pry: real in-plane T6 capacity, no floor. It feeds the seq proxy.
- (6, 7) Not started. Plan and ETA are in the answers below.
- P2: novelty, machining fraction and feasibility typing were not changed in this pass. The holder orientation is still open. No new certified finalist, so no new heatmaps or WAVE plates.

## Answers for My_Running_knife
**(a) Twist unit test.** All D1 tests PASS. The strip benchmark reproduces thin-strip torsion and beam bending at 1.000. Plate-to-3D St-Venant factor is 1.07 / 1.18 / 1.25 at b/t 10 / 4 / 3. The pre-D1 crescent "twist" was a bending couple, now fixed.
On the corrected fixture (joint, 828, 3D) against the 1.82 N·m floor:
- wave14_c03: **SF 0.53 FAIL** (970 N·mm)
- wave13_c01: **SF 0.45 FAIL** (816 N·mm)
The peak is on the ground tip, 4 mm from the point. Body (>15 mm from tip) SF is 3.4 / 2.9. The fixture definition needs an owner decision.

**(b) 828 MPa joint re-screen.**
- wave14_c03, 76.95 g: joint lateral 280.2 N, SF hiker 1.557 / hunter 1.078 / ring 8.61. Strict 269.8 N (1.038). **PASS**, thin margin, below the 286 N +10 % aim.
- wave13_c01, 74.37 g: 234.4 N, SF 1.302 / **0.902** / 8.35. Strict 248.6 N. **FAIL**. Its on-disk genome also fails the old rules (258 N vs the recorded 292 N), a reproducibility issue now fixed for new runs.

**(c) wave14_c03 genome and STEP.** Genome: yes, `docs/lattice/wave14_c6_through/wave14_c03_fit_genome.csv` (git, branch exec/lattice and exec/d1), plus the exec-lattice `out/` copy. STEP: xbabe2 `~/jarambit/.agent/worktrees/exec-lattice/out/wave14_c6_through/wave14_c03_fit.step` (faceted, not a machining release). Grind law: `docs/d1/wave14_c03_grind_law.json`.

**(d) First continuous-rail rebuild.**
Plan:
1. Rail mask genes: a full-thickness band of at least w_rail from the outline, ring OD to heel, plus a full-thickness neck. No through-perfs and no isogrid by default. Selective shallow pockets (≤0.6 mm per face, R≥3 runouts) only where the parent's SF map is >2.
2. Thickness field: 3 to 5 centreline knots instead of one stock knob.
3. Gates: 828 joint, hunter ≥260 hard with a 286 N aim, seq ratio ≥1.2, strict 0.0625, full-precision genomes, body twist ≥1.82 N·m once the fixture is decided.
4. Run: seed from wave14_c03 with the wave13_c01 control. wave17 on xbabe3, 40 threads nice 19, 8x48x160.

ETA: about 2.5 to 3 h of code, then about 1.5 h of run plus 20 min of certification and plates. First certified continuous-rail candidates come about 4.5 to 5 h after P1 starts. If P1 starts now (about 15:00 MT Oct 11), that is about 19:30 to 20:00 MT. Then plates go to Jepson for aesthetic sign-off. No promotion before that.

## Blockers / owner decisions
1. Chord-torsion floor fixture: is 1.82 N·m applied at the tip (all designs fail, SF ~0.5) or as body torsion with a separate tip submodel (all pass, SF ~3)?
2. 828 MPa provisional: the cert/MTR value for the actual plate lot is needed to finalise it.
3. Pre-D1 records (waves 7 to 16) are 4-decimal genomes certified under 880/min with the couple "twist". Do not cite them without a `crescent-d1` re-screen. wave15/16 tops all FAIL at 828 joint.
4. No evolved design meets the seq ≥1.2 failure-sequence proxy yet.
