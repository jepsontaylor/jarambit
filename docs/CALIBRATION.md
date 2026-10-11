# MC <-> FEM calibration, mesh convergence and the neck genes

Author: Jepson Taylor. Utility/hiking karambit (SWITCHBACK class) only.

## Why

The wave5 winner was scored by the Monte-Carlo beam surrogate (and the coarse
ear-clipped plate in `fem.rs`) at hunter level. The detailed plate showed it
fails both strength floors: about 166 N lateral at 20 C and 151 N at 100 C,
against floors of 180 and 260 N. **The wave5 winner is not promoted.** This
document covers how the gap was measured and how it was closed.

## 1. Detailed plate solver (`crates/physics/src/fine.rs`)

* Mesh: spade constrained Delaunay with refinement (min angle 25 deg, max
  triangle area A). The boundary is resampled at m = ceil(1/sqrt(A)) splits.
* Bending: Batoz DKT, built numerically. Stress is taken at element corners
  from the linear curvature field (a_i = 2 f_i - mean), not at Gauss points.
* In-plane cases (pry, ring pull): quadratic T6 membrane elements. Peaks are
  area-weighted nodal averages.
* Solver: RCM ordering plus skyline Cholesky.
* Every re-entrant corner of the outline gets a 1.0 mm inside radius
  (`limits::MIN_INSIDE_RADIUS_MM`). A sharp corner has a singular stress and
  no mesh will converge on it. 1 mm is also the practical minimum inside
  radius for waterjet/CNC.
* Load cases match `fem.rs`. Lateral and ring pull are the floor cases. Pry is
  reported only, and twist remains a proxy.

## 2. Theory checks (`crates/physics/src/verify.rs`)

These run on the finest level, A = 0.25 mm^2. Gate: every check under 5 % error.

| check | theory | error |
|---|---|---|
| cantilever tip deflection (unstructured mesh, also rotated 33 deg) | Euler-Bernoulli | 0.00 % |
| cantilever mid-span bending stress (and rotated) | Mc/I | 0.96-0.99 % |
| clamped square plate, point-load deflection | Timoshenko 0.00560 Pa^2/D | 0.28 % |
| clamped square plate, uniform-load deflection | Timoshenko 0.00126 qa^4/D | 0.46 % |
| clamped plate edge von Mises, uniform load | 6*0.0513 qa^2/t^2 * sqrt(1-nu+nu^2) | 2.38 % |
| curved bar inner-fibre stress | Golovin/Winkler | 0.01 % |
| plate-with-hole Kt_gross, d/W = 0.2 | Heywood 3.14 | 1.33 % |

**Theory gate: PASS.** The per-level table is in
`docs/calibration/fem_verify_report.md` and `theory_checks.csv`.

## 3. Knife mesh convergence

Six levels, A = 4, 2, 1, 0.5, 0.25, 0.125 mm^2 (about 1.5k to 20k nodes).
f_ref is the mean of the two finest levels. Gate: all 4 finest levels within
5 % of f_ref, and the search level (A = 2) within 5 %.

| design | lateral f_ref N | 4-finest band | search err | ring pull f_ref N | band | search err |
|---|---|---|---|---|---|---|
| wave5 (smoke_legal_blade winner) | 121.0 | 1.01 % | 2.29 % | 2750 | 2.94 % | 2.33 % |
| mh1_xbabe1_s3001 | 191.0 | 3.97 % | 0.73 % | 2291 | 2.90 % | 3.08 % |
| switchback ref, sharp neck | 30.5 | 1.66 % | 2.15 % | 1052 | 3.92 % | 3.86 % |
| switchback ref, neck fillet 6 + flare 3 | 50.5 | 2.39 % | 2.28 % | 3596 | 1.81 % | 2.22 % |
| wave5 + neck fillet 6 + flare 3 | 219.3 | 0.30 % | 0.15 % | 9195 | 2.35 % | 1.46 % |

**Convergence gate: PASS** on every design for both floor cases. In the
sharp-neck designs the lateral peak sits at the grip-ring neck, which is the
100 C hot spot. Adding the neck fillet and flare moves it to the ricasso
shoulder and raises wave5's lateral capacity by 81 %.

## 4. Calibration factors (`crates/physics/src/calib.rs`, `jarambit calib`)

These cover n = 258 designs at 20 C: the wave5 winner, the mh1 group winners,
and 120 red-team-legal random genomes, each run both with and without its neck
genes. The reference is the detailed plate at A = 0.25.

| ratio | median | p95 | max |
|---|---|---|---|
| **beam surrogate / detailed plate, lateral (the MC overstatement)** | **1.796** | **2.952** | **3.065** |
| same, filleted necks only (n = 111) | 1.247 | 1.599 | 1.783 |
| coarse plate (`fem.rs`) / detailed plate, lateral | 1.199 | 1.667 | 1.874 |
| search mesh (A = 2) / verify mesh, lateral | 0.994 | 1.024 | 1.070 |
| beam surrogate / detailed plate, ring pull | 6.311 | 7.911 | 8.449 |
| search mesh / verify mesh, ring pull | 1.017 | 1.032 | 1.062 |

The surrogate overstates the floor-governing lateral capacity by about 1.8x
for a typical design and up to 3.1x in the worst case. That covers the
roughly 2.3x seen on wave5. A factor this variable cannot safely be used as a
single scalar, so the search does not rely on one. Instead:

* **FEM in the loop** (`--fine` or `JARAMBIT_FINE=1`). Every candidate that
  passes the red-team and limit checks gets a detailed plate solve at
  A = 2 mm^2. Its robust level is
  `min( plate20 / MESH_BIAS_MAX * (MC p05 / MC nominal), plate100 / MESH_BIAS_MAX )`.
  MESH_BIAS_MAX is 1.070 for lateral and 1.062 for ring. The hard floors
  (180 N hiker, 260 N hunter, 1500 N ring pull) apply to this value.
* `calibrated_surrogate()` divides the surrogate by the worst-case factors.
  It is used only for reporting and plotting. It is never a floor check.

## 5. Neck material (genotype genes 21-23)

| gene | range | meaning |
|---|---|---|
| neck_flare | 0-6 mm per side | extra half-width where the grip meets the ring OD |
| neck_flare_len | 6-25 mm | height of the taper up the grip |
| neck_fillet_r | 0-10 mm | tangent fillet between the taper and the ring OD |

Genomes written before these genes existed load as 0 / 15 / 0, which is the
old sharp neck. The taper sits inside the exposed grip below the holder
shoulders, so the holder envelope is unchanged and the red-team still passes.

## 6. Calibrated re-search

Run: `jarambit --fine --seed-ref --seed-ckpt <legal checkpoint> ...`.
Floors 180/260/1500 N are hard on the robust FEM level. The blade must be
>= 3.375 in on tip-heel, reach and arc length, and that is still a rejection
rule. Front members are re-verified at A = 0.25 by `verify_front`, which
writes `calibrated_pareto.md` and the STL/STEP/SVG files.

* **t <= 4.5 mm (the default bound): 0 LEGAL.** Four runs of 50 generations
  each plateaued at a robust lateral of 191-202 N, all pinned at 4.5 mm. The
  hiker floor clears; the 260 N floor does not. With the neck reinforced, the
  peak sits in the grip body, ricasso or blade root. That leaves t^2 as the
  only remaining lever, because the holder fixes the handle width and the
  blade floor fixes the lever arm.
* **Exploratory ceiling `JARAMBIT_T_MAX=6.0`.** The 6.0 mm cap is the most
  the holder stack allows (t + 2*1.2 + 0.4 <= 9.0 mm). The default bounds are
  unchanged. Four runs gave 62 LEGAL front members, starting at t = 5.3 mm.
  Lightest: 56.0 g, t 5.3 mm, SPG robust 4.68 N/g, SF hunter 1.08 at 100 C.
  Best SPG: 64.6 g, t 6.0 mm, SPG robust 5.42 N/g, SF hunter 1.46 at 100 C.
  The merged front is in `docs/calibration/calibrated_pareto.md`.
* For comparison, the uncalibrated wave5 "7.04 N/g" becomes about 2.25 N/g (121 N x 0.91 / 48.9 g) on
  the verification mesh at 100 C. The honest figure for a hunter-legal design
  is 4.7-5.4 N/g at 56-65 g.

Raising the 4.5 mm stock bound is an owner decision. Until that decision is
made, the t > 4.5 front is labelled exploratory.

## Reproduce

```
cargo build --release
./target/release/jarambit fem-verify --out out/fem_verify   # theory + 6-level convergence
./target/release/jarambit calib --out out/calib              # factor table
./target/release/jarambit diag --ckpt out/cal1/s12/checkpoint.txt  # verify-mesh capacity + peak of a checkpoint best
JARAMBIT_T_MAX=6.0 ./target/release/jarambit --fine --seed-ref --seed-ckpt out/cal1/s12/checkpoint.txt --seed-thick 5.6 --pop 48 --gens 40 --mc 1000 --islands 2 --threads 12 --seed 24 --out out/cal_t6/s24
```

## 7. D1 review (2026-10-11): yield allowable, joint robustness, chord torsion

- **Yield allowable (screening):** Ti-6Al-4V `yield_mpa` 880 -> **828 MPa provisional** (TIMET Gr5 annealed MINIMUM 0.2 % yield, 120 ksi). Knock-down 828/880 = **0.941** on every first-yield capacity. Do **not** round to 830 for a marginal PASS. The typical value is kept as `TI64_YIELD_TYPICAL_MPA` for the record only. To be replaced by the mill cert (MTR) value of the actual plate lot.
- **Joint thin+hot realisation:** the robust capacity is now `F20 x ((t-0.1)/t)^p x yield(100 C)/yield(20 C)` (p = 2 for bending/torsion, 1 for the ring membrane). This is the product, replacing the pre-D1 `min(thin, hot)`. At t = 5.8 the joint factor is 0.851, against a pre-D1 min of 0.912. Combined with 828 MPa, robust lateral capacities drop about 12.6 % vs the pre-D1 numbers.
- **Chord torsion:** the crescent "twist" load was a bending couple (slope-dof load along the chord d). It is fixed to n = (-d_y, d_x). St-Venant 3D thick-section factor (exact series):
  - 1.067 at b/t 10, 1.183 at 4, 1.247 at 3 (strip benchmark, plate = thin-strip theory at 1.000);
  - it is applied at the peak section.
- **Proposed floor:** 1.82 N*m (`fem::TWIST_FLOOR_NMM`), advisory until the owner fixes the fixture.
- **Genome CSV precision:** `{:.4}` -> round-trip. The 4-decimal wave13_c01 genome re-certifies at 258 N vs a recorded 292 N.
- Re-screen tool: `jarambit crescent-d1`. Results: `docs/d1/`.
