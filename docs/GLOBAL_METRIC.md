# GLOBAL METRIC G (version G1, locked 2026-10-12) — author Jepson Taylor

One scalar to compare designs across waves. **G never overrides a hard gate**: a hard-FAIL design still gets a G (so plates are comparable) but is never promoted on G. Promotion still requires all D1/W2x hard gates + human aesthetic sign-off. g3_neckrail is NOT promoted; 828 MPa stays provisional.

## Definition
```
G = w1·tip + w2·spg_n + w3·aes − w4·mass_pen − w5·seq_gap
```
| term | definition | source key | weight |
|---|---|---|---|
| tip (solid_tip_SF) | min(SF of solid C3D tip submodel at max-stress node, 2.0) at 828 MPa | `solid_tip_sf_nodal_max` | w1 = 0.35 |
| spg_n (SPG) | certified strength-per-gram (N/g) / 4.0 | `spg` | w2 = 0.35 |
| aes (aes_spine) | C.6 automated aesthetic score 0…1 (spine/outline vs anchor) | `aes_score` | w3 = 0.20 |
| mass_pen | max(0, mass_g − 77) / 10 (above the 74–77 g band) | `mass_g` | w4 = 0.05 |
| seq_soft_gap | max(0, 1.2 − seq_ratio) / 1.2 — failure sequence hand/blade, **soft until ≥ 1.2** | `seq_ratio` | w5 = 0.05 |

Rationale: tip and SPG are the two engineering objectives the waves have been fighting over (wave20–27), equal weight; tip is capped at 2.0 so over-built tips don't buy G. Aesthetics is real but secondary (human sign-off is a separate gate). Mass and sequence are small penalties because mass already sits in SPG and seq is soft; when seq becomes a hard gate, w5 is retired (→ G2).

**Provisional `G*`:** when no solid tip submodel exists yet, `tip` uses the plate tip-submodel screen SF (`plate_tipsub_screen_sf`, else `twist_tipzone_sf_strict`) and the title shows `G*`.

## Completeness (v0.28.1)
All five terms are required. Missing, null, boolean, non-numeric, non-finite or out-of-range (aes outside 0..1, mass outside 1..1000 g, negative SF/SPG/seq) inputs make the record **INCOMPLETE**: `G = None`, reasons in `terms['missing']`, plate title `G INCOMPLETE (n missing)`. A missing value is never treated as 0, so deleting an input can never improve G. `G*` (provisional) is independent of completeness. Tests: `metrics/tests/test_global_metric.py`.

## Plate title contract
Every wave FEM plate title ends with `| G <g> | <mass> g | jarambit v<VERSION>` (VERSION from `docs/VERSION`).
Implementation: `metrics/global_metric.py::title_tag`, called in `ops/wave_figures/make_d1_plate.py` (also writes `G`, `G_terms`, `version` into `<wave>_D1_index.json`).

## Best-G per wave (hard-PASS designs, computed from existing plate indices)
| wave | design | G | SF_tip (solid) | SPG N/g | aes | mass g | seq |
|---|---|---|---|---|---|---|---|
| wave20 | c11_fit_D1 HARD PASS | 0.848 | 1.164 | 3.994 | 0.673 | 83.4 | 0.926 |
| wave21 | c08_fit_D1 HARD PASS | 0.808 | 1.107 | 3.839 | 0.710 | 85.9 | 0.891 |
| wave22 | c03_fit_D1 HARD PASS | 0.885 | 1.345 | 3.853 | 0.636 | 83.9 | 0.831 |
| wave23 | c02_fit_D1 HARD PASS | 0.925 | 1.425 | 3.996 | 0.629 | 84.6 | 0.916 |
| wave24 | c02_fit_D1 HARD PASS | 0.966 | 1.527 | 4.070 | 0.645 | 85.6 | 0.952 |
| wave25 | c01_fit_D1 HARD PASS | 0.952 | 1.527 | 3.726 | 0.648 | 82.0 | 0.879 |
| wave26 | ctl_g3_ref (solid table only, no plates yet — w26_resume live) | pending | 1.525 | 4.158 | — | 84.6 | 0.959 |
| wave27e | g3t58_S05_rw-05_D1 HARD PASS | 0.977 | 1.594 | 3.859 | 0.593 | 81.8 | 0.888 |
| wave27b | a0_S08_dr+05_D1 HARD FAIL | 0.979* | n/a (screen 1.636) | 3.747 | 0.591 | 81.9 | 0.842 |

Changing weights = new metric version (G2) + RELEASES entry; never silently.
