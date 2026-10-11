# D1 P1 status (jarambit, SWITCHBACK-class titanium hiking/utility karambit)

Owner: Jepson Taylor. Executor: Grok Bot, 2026-10-11 (America/Denver, MT). Branch `exec/d1` (continues from P0 `f3f360d`). Supersedes `D1_P0_STATUS.md`; the P0 science (twist fix, 828 MPa, JOINT thin+hot, grind-law JSON) is unchanged and still described there.
CPU only, nice 19. Flywheel GPUs not touched. **Nothing is promoted.** Every plate still needs Jepson's aesthetic sign-off, and no design passes every D1 gate yet.

## Rules in force (CURRENT D1)
- Ti-6Al-4V screening yield **828 MPa** (provisional, TIMET minimum). Robustness is **JOINT** thin+hot: `((t_j-0.1)/t_j)^2 x yield(100C)/yield(20C)`, with `^1` for the ring. `t_j` is the thinnest knot for P1 genomes and the stock thickness otherwise.
- Certification is min(0.25, 0.125 mm^2) with no bias. The **strict** check is 0.0625 mm^2. Floors are hiker 180 / hunter 260 / ring 1500 N, and the hunter **aim is 286 N** (+10 %).
- **PASS @828 joint** = all three floors at certification **and** hunter at strict.
- **P1 PASS** = PASS @828 joint **and** failure-sequence proxy **>= 1.2** (hard). The proxy is hand-zone over blade-zone yield-onset load, min over lateral / chord-torsion / pry.
- **Twist floor, OWNER LOCKED (Jepson, 14:52 MT):** the hard floor is **body torsion AND tip submodel**, both ≥ 1.82 N·m chord torsion (joint thin+hot, 828, St-Venant 3D). **Tip-only SF is always reported** but is not the gate.
  - **body**: the 1.82 N·m tip torque with the peak searched >15 mm from the tip, using its own 3D factor.
  - **tip submodel**: the peak restricted to the 4–15 mm tip annulus at the strict 0.0625 mesh, using its own 3D factor. This is a refined local check of the tip region. A separately clamped cut model is a stub.
  - **tip-only**: the 2 mm tip patch with the peak outside 4 mm (P0 fixture).
  - Code: `fem::twist_floor_ok(body_sf, tipzone_sf_strict)`.
- **PROMOTE-ELIGIBLE (OWNER LOCK, hard, `fem::promote_eligible`)** requires all of:
  - C.6 aesthetic and every hard gate, including blade ≥ 3.375 in on all three measures;
  - 828 joint floors 180/260/1500 at certification, plus hunter ≥ 260 at strict 0.0625 (aim 286 reported);
  - seq ≥ 1.2;
  - twist body AND tip submodel ≥ 1.82 N·m;
  - mass 74–77 g, under the 80 g cap.
- Promote-eligible is **not** promotion: human aesthetic sign-off is still required, and nothing is auto-promoted.
- New columns: `twist_floor_ok_body_and_tipsub`, `mass_band_74_77`, `blade_min_in`, `promote_eligible_pending_aesthetic_signoff`. They appear in `crescent-d1` and in the wave17 `certification.csv`.

## TRACK A — wave15 / wave16 collected under D1 rules (DONE)
- wave15 (xbabe2) and wave16 (xbabe3) had already finished. The exec/lattice lane had collected and plated them under the **pre-D1** rules (commit `45b7069`).
- This pass re-certified every plated design (wave15 c01–c09, wave16 c01–c16) plus the baselines with `crescent-d1` (828 joint, strict, seq, both twist fixtures). D1 plates were written for **all** of them, failures included.
- Command: `D1_PLATES=1 jarambit crescent-d1 --genomes ... --threads 28 --out out/d1_w15w16_collect`. Plates come from `ops/wave_figures/make_d1_plate.py`.
- Heatmaps: `/workspace/jarambit_heatmaps/wave15_c0N_D1FAIL_*_D1_FEM_metrics.{png,pdf}`, `wave16_c*_D1FAIL_*`, `wave14_c03_*_D1_*`, `wave13_c01_*_D1_*` and `wave1{3,4,5,6}_D1_index.json`. The pre-D1 plates (`wave15_c0N_fit_*`, `wave16_c*_fit_*`) are left in place for the record.
- Caveat: the on-disk genomes are the 4-decimal CSVs written by the pre-D1 binary (see the P0 reproducibility finding). wave16 c01–c16 collapse to essentially one design at 4 decimals.

| design | mass g | t | joint lat N (cert) | SF hunter | strict 0.0625 N (SF) | ring N | PASS @828 joint | aim 286 | tip-only twist SF (reported) | body twist SF | tip-submodel SF | seq ratio | 828+strict+seq |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| wave15_c01 | 71.65 | 5.7 | 252.6 | 0.971 | 243.9 (0.938) | 11885 | FAIL | no | 0.47 FAIL | 1.93 | 0.49 | 0.89 | FAIL |
| wave15_c02 | 71.82 | 5.7 | 228.5 | 0.879 | 242.0 (0.931) | 12422 | FAIL | no | 0.47 FAIL | 2.15 | 0.50 | 0.97 | FAIL |
| wave15_c03 | 71.51 | 5.6 | 241.6 | 0.929 | 233.9 (0.900) | 12500 | FAIL | no | 0.48 FAIL | 2.08 | 0.48 | 0.90 | FAIL |
| wave15_c04 | 71.13 | 5.6 | 237.5 | 0.914 | 226.0 (0.869) | 11905 | FAIL | no | 0.47 FAIL | 2.12 | 0.47 | 0.83 | FAIL |
| wave15_c05 | 71.96 | 5.6 | 245.6 | 0.945 | 240.6 (0.925) | 12481 | FAIL | no | 0.50 FAIL | 2.19 | 0.48 | 0.80 | FAIL |
| wave15_c06 | 71.93 | 5.6 | 241.3 | 0.928 | 236.5 (0.910) | 12079 | FAIL | no | 0.51 FAIL | 2.14 | 0.52 | 0.88 | FAIL |
| wave15_c07 | 71.62 | 5.6 | 252.6 | 0.971 | 222.8 (0.857) | 11971 | FAIL | no | 0.50 FAIL | 2.14 | 0.51 | 0.95 | FAIL |
| wave15_c08 | 71.99 | 5.6 | 243.2 | 0.935 | 239.4 (0.921) | 12229 | FAIL | no | 0.45 FAIL | 2.12 | 0.50 | 0.81 | FAIL |
| wave15_c09 | 70.25 | 5.6 | 237.5 | 0.914 | 227.0 (0.873) | 11661 | FAIL | no | 0.48 FAIL | 2.05 | 0.48 | 0.81 | FAIL |
| wave16_c01..c16 (one design at 4-dec) | 71.66–71.73 | 5.8 | 262.7 | 1.010 | 246.5 (0.948) | 12754 | FAIL (strict) | no | 0.53 FAIL | 2.66 | 0.56 | 0.83–0.86 | FAIL |
| **baseline wave14_c03** | 76.95 | 5.8 | 280.2 | 1.078 | 269.8 (1.038) | 12913 | **PASS** (thin) | no | 0.53 FAIL | 2.78 | 0.58 | 0.84 | FAIL (seq) |
| baseline wave13_c01 | 74.37 | 5.6 | 234.4 | 0.902 | 248.6 (0.956) | 12521 | FAIL | no | 0.45 FAIL | 2.34 | 0.46 | 0.84 | FAIL |

**Verdict:**
- All 25 wave15/16 plates **FAIL** D1. 0 of 25 pass 828 joint + strict.
- Best wave16 (71.7 g) is 1.0 % over hunter at certification but 5.2 % under at strict.
- wave15 is 3–14 % under hunter at strict.
- The 4–7 g they saved against wave14_c03 is not real under D1.
- Every design **fails the locked twist floor**: body passes (SF 1.9–2.8), but the tip submodel fails (SF 0.46–0.58). Tip-only is 0.45–0.53.
- Every design also fails seq (0.80–0.97). Hiker and ring pass everywhere.
- Every design is outside the 74–77 g band except the baselines (wave14_c03 76.95 g, wave13_c01 74.37 g).
- Blade min is 3.42–3.45 in, so the blade gate passes.
- **Promote-eligible: 0 of 27.**
- wave14_c03 remains the only 828-joint PASS, with no aim margin and seq failing.

## TRACK B — D1 P1 continuous-rail rebuild, wave17 (LAUNCHED)
**Code (exec/d1).**
- **Genome:** 128 genes, up from 117. New genes: `p1_on, rail_w, neck_l, pocket_d, pocket_r, k_n, k0..k4`. Pre-P1 rows load with P1 OFF, and the genome CSV stays full precision (round-trip test).
- **P1 ON (`JARAMBIT_P1=1`):**
  - **No** through-perforations, pierced-fuller windows, isogrid, dimple lattice, edge relief, comet flutes, ring flute or machined texture. These are clamped OFF, and a gate rejects any perf/window that slips through.
  - The blade fuller is capped at 0.6 mm per face.
  - The C.6 anchor ring-face groove (0.6 mm per face) stays because it is part of the adopted look.
  - The comet/eye slots must leave a full rail (≥ `rail_w`) to the outline.
- **Rails:**
  - Full thickness (the local knot-field base, no pocketing) within `rail_w` (3–7 mm) of the outline and every hole rim, from the ring OD through the heel.
  - The **neck** is full thickness out to `r_od + neck_l` (4–12 mm).
- **Shallow pockets:**
  - Depth ≤ 0.6 mm per face (`pocket_d`), with a smoothstep runout over ≥ R3 (`pocket_r` 3–6 mm) from rails, neck, grind lines, the holder land, the brand pad and the parent-SF boundary.
  - Pockets go only where the **parent's** certified 100 C envelope SF > 2. The map comes from `ops/d1/make_sfmap.py` and `JARAMBIT_P1_SFMAP`.
  - Parent = wave14_c03 D1 plate. The SF>2 region is 2254 of 3796 mm^2. The wave13_c01-lineage children use the same wave14_c03 map (documented approximation).
  - With no map, there are no pockets.
- **Thickness:**
  - 3–5 centreline knots (`k_n`, `k0..k4`, T_MIN..stock), piecewise-linear from the ring centre to `taper_x0`, then the distal taper. This replaces the single stock knob.
  - Stock is the thickest knot (0.1 mm rule). The holder land and brand pad count as "full" against the local base.
- **Evolve gates:**
  - LEGAL = gates + floors (search level) + **seq ≥ 1.2**. Floors-OK/seq-fail designs get a graded penalty in (−1, −0.1).
  - Fitness = SPG × A × (1+N) × (0.9 + 0.1·clamp((lat−260)/26)), which is the hunter **aim 286**.
  - Mass target 80 g. Certification also runs strict 0.0625; `cert_pass_all` = floors + strict + seq.
  - Floors-OK designs that miss only seq are still certified and plated, labelled FAIL.
  - Tip twist SF is reported, not gated.
- **Tests:** 3 new P1 tests (`p1_*`). The full workspace test log is in xbabe3 `~/jarambit_d1p1/out/p1_tests.log`.
- **Stubs this pass (documented, not implemented):** analytic B-rep grind STEP (the grind-law JSON is real; ETA ~1 day), tip exclusion (clamped-cut tip submodel), ring peel, and fatigue. Pry is real with no floor.

**Run:**
- xbabe3, screen `jarambit_d1p1`, `~/jarambit_d1p1/out/run_wave17.sh`. Binary snapshot: `out/wave17_p1/jarambit_wave17.bin`.
- 8 islands × 48 × 160 gens, 40 threads, nice 19, seed 1717, kick 0.5, cert 16, strict ON.
- Seeds: wave14_c03 (primary) + wave13_c01 (lighter control) + C.6 seed, all clamped to P1. Their perfs/isogrid are removed, which puts the seeds at about 80–82 g.
- **v0** (started 14:43 MT, mass target 80, seq-only P1 gate) was stopped at gen 22 when the owner lock arrived. Archive: `out/wave17_p1_v0/`.
  - It showed seq ≥ 1.2 is reachable (217 seq-legal designs by gen 20), but only at ≥ 84.7 g.
- **v1 (LIVE, started 14:58 MT):**
  - Search legality now also needs twist body AND tip submodel ≥ 1 (search mesh).
  - `JARAMBIT_MASS_CAP=77` (top of the promote band).
  - Seq, twist and mass are traded through one graded product penalty in (−1, −0.1).
  - Certification applies the full owner-locked `promote_eligible`.
- Speed is about 33 s/gen. Search should end about **16:27 MT**, with certification + strict + export about 25 min more.
- **First certified P1 candidates ~16:50 MT; D1 plates ~17:05 MT.** This is inside the original 4.5–5 h window.

## Blockers / owner decisions
1. **Locked twist floor vs the thin ground tip:** every existing design fails the tip submodel (SF ≈ 0.5). Passing needs about 1.4× tip thickness (t_tip up to 4.5 mm is in bounds) and/or steeper grinds near the point. wave17 v1 puts search pressure on this, but it may cost cutting geometry and mass.
2. **seq ≥ 1.2 + 74–77 g may conflict.** In v0, seq-legal designs were all ≥ 84.7 g. If wave17 ends with 0 seq-legal designs, the floors-OK/seq-fail certified designs are plated and labelled FAIL, and the knot/rail genes are reported.
3. 828 MPa stays provisional until the lot MTR value is available.
4. The pre-D1 records (waves 7–16) use 4-decimal genomes. Do not cite them without a `crescent-d1` re-screen.

## Post-run recipe for wave17 (not yet done; matplotlib is broken on xbabe3, so plate on xbabe2)
1. Wait for `EXIT` in xbabe3 `~/jarambit_d1p1/out/wave17_p1.log`.
2. Pipe `out/wave17_p1` (excluding `*.stl` if size matters) from xbabe3 to the xbabe2 worktree `out/wave17_p1`: `ssh xbabe3 'tar c' | ssh xbabe2 'tar x'`.
3. On xbabe2, render the plates: `EVALS=out/wave17_p1/all_evals.json python3 ops/wave_figures/make_d1_plate.py out/wave17_p1 out/wave17_p1/heatmaps wave17 77`.
4. Copy the plates to box `/workspace/jarambit_heatmaps/wave17_*`. Commit `certification.csv`, `report.md`, genomes and the index to `docs/d1/wave17_p1/`, then push exec/d1.
5. Report each finalist from `certification.csv`:
   - `promote_eligible_pending_aesthetic_signoff`, `twist_floor_ok_body_and_tipsub`;
   - tip-only SF (`twist_tip_sf_default_hard`, reported), body SF and tip-submodel SF;
   - seq, strict lateral and mass.
6. Do not promote anything without human aesthetic sign-off.
