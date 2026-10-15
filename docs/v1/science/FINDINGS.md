# Frozen-baseline findings

Baseline: `97af59cf14299af583b344aeaefb4594d089465a`, xbabe2. These findings describe this revision, not later main or every candidate. `reproduced` means an isolated probe executed the actual code; `source-confirmed` means inspected implementation; `recorded` means committed documentation/evidence, without a fresh physical or expensive solid reproduction.

## Priority findings

| ID | Priority / evidence | Finding and exact source | Consequence / packet |
|---|---|---|---|
| F01 | P0, reproduced | `fem_solid/gci.py:10`: `(10,12,13,2)` returns order −1 and GCI −0.5; `(10,10,100,2)` returns infinite order and zero GCI; zero-order/refinement/reference cases raise division errors. | Numeric threshold cannot establish admissibility. S02. |
| F02 | P0, reproduced | `fem_solid/gci_report.py:13`: empty glob initializes `ok=True`; isolated reporter exits zero with “all 0 designs meet.” | Missing inventory becomes apparent success. S02/S03. |
| F03 | P0, recorded and source-confirmed | `evidence/fem_solid/gci/w271b_11772_gci.json`: coarse/mid/fine stress 862.08/876.42/875.29 MPa, `monotone=false`, `p=null`, heuristic GCI 0.0048412526. Reporter and `fem_solid/tests/test_gci_evidence.py:11` check only the upper threshold. | An actual oscillatory record is included in the all-five GCI claim. Reclassify convergence evidence, not physical performance. S02. |
| F04 | P0, source-confirmed | `fem_solid/convergence.py:15`: existing `L<nsub><nl>.json` reused by filename existence; no source/input/observable/config identity check. | Old solve can satisfy a new convergence request. S02. |
| F05 | P0, source-confirmed | `crates/cli/src/bench.rs`, `solid_tip_sf()`: exact genome/design binding exists, but only reads finest SF; ignores GCI classification and full evidence provenance. | Strong existing identity check must be extended to validity and applicability. S08. |
| F06 | P0, source-confirmed | `ops/render/pro/design_manifest.py:102,122,127`: gate comparison skips absent JSON keys and V4; missing certification defaults to `of record`, allowing threshold PASS and “converged.” | Missing metadata can improve status. Existing render ownership must release before change. S15. |
| F07 | P0, recorded | `README.md:37` identifies C.9.3 current; C10a README says current rc4 and C.9.3 superseded. `ops/render/pro/fem_cases.json` reopens V3 under W84; C10a V4 is not fully converged. | Generate current status and propagate reopened evidence. S03/S15. No inference of physical failure. |
| F08 | P0, reproduced local contract | `ops/ci/check_claims.py:65`: expected verdict checked as substring. Synthetic correct FAIL plus contradictory scoped PASS is accepted by `check_block()`. | Exact/canonical agreement needed. This probe does not establish a complete CI bypass. S03. |
| F09 | P1, source-confirmed | `crates/monte_carlo/src/lib.rs:145,186–188`: zero count coerced to one; incomparable values sort as equal; naive sum can overflow; marginal tails computed separately. | Reject invalid data and preserve per-sample joint truth. No evidence that a specific past candidate contained NaN. S04. |
| F10 | P1, source-confirmed | `crates/evidence/src/lib.rs`, `RunManifest`: sorted params and SHA exist, but source commit, requirement-content hash, mesh/material/model/observable identities are not mandatory. Legacy manifest records knobs/constants, not full source identity. | Manifest binding is useful but incomplete for cross-revision qualification. S01/S08. |
| F11 | P1, source-confirmed | `crates/crescent/src/qd.rs:28,94,206,278`: `legal()` applies seq/twist only for P1; `feasible()` applies them to all. Archive admission uses `legal()`; replacement compares stored fitness including contextual novelty. | Exploratory/legal/feasible/certified archives need explicit policies; context changes can distort replacement. S05. |
| F12 | P1, source-confirmed | Legacy `crates/evolve/tests/replay.rs` has lossless resume. Current `qd.rs` has no comparable checkpoint API. `crates/cli/src/crescent.rs:13` can disable evidence logging and continue; history/all-record output remains mostly terminal. | Current engine needs durable replay and non-publishable failure state. S06. |
| F13 | P1, source-confirmed | `crates/crescent/src/fem.rs:192`: certification minima combine meshes; fields come from first mesh and counts from second. `fem_solid/solve_dolfinx.py:66–69`: L2/nodal comment describes DG interpolation. | Bind each scalar and field to actual mesh/extraction semantics. Does not itself prove computed stress wrong. S07/S08. |
| F14 | P1, source-confirmed | `crates/cli/src/bench.rs:41` labels sums of per-design elapsed time “core_s”; `ops/bench/run.py` compares checksum rounded to six decimals and uses cumulative child high-water RSS. | True CPU-time and per-case parity/memory accounting required. S09. |
| F15 | P1, recorded | `docs/calibration/t1_t2.md`: 40 of 80 sampled designs selected because both tiers evaluated; twist residual σ 10.8%, max residual 39.1%; project threshold 7%. | Conditional calibration and OOD checks; no universal scalar correction. S09/S11. |
| F16 | P1, source-confirmed | Current calibration calls fine plate certification “T2”; old master ladder calls tet10 solid “T2.” | Use evaluator IDs and physical formulations, not tier number alone. S08. |
| F17 | P1, recorded | RS-v2 mass targets are soft; C.10a study states `<70 g` hard and uses different loads/thresholds. Native B-rep is not a crescent genome. | Crosswalk/evidence adapter must preserve both contexts. S03/S08. |
| F18 | P1, recorded | Material model uses provisional annealed-plate properties; fatigue is Marin/Goodman screening. Candidate documentation says nothing machined/physically tested. | Physical validation, process passports, uncertainty and inspection capability remain required. S13/S14. |
| F19 | P1, source-confirmed | `CutMedia` still includes Muscle/Bone/Gel despite old roadmap retirement item. | Preserve historical read compatibility; retire unsupported lookup from active scientific claims. S04. |
| F20 | P2, source-confirmed | `docs/VERSION=0.31.0`; Cargo workspace/package versions remain 0.1.0; old roadmap uses v0.32 for core while live v0.32 train includes substantial rendering/CAD work. | Version names/PR labels do not prove architectural milestones completed. S00/S16. |
| F21 | P2, recorded/uncertain | External C.10 solver stores and source dependencies are not all in the review text snapshot. | Inventory before claiming complete reproducibility; do not invent external hashes or input history. S08. |

## Existing work to retain

- Typed null/missing FEM observations, strict JSON checks, scoped verdicts, G1 completeness tests, exact genome binding, expected theory-check coverage, and known-negative D1 fixture.
- Parent/operator/migration events, fsync-per-generation evidence frames, corrupt/torn-tail handling, and event-derived fresh-versus-appearance counters.
- Legacy bit-preserving manifest-bound checkpoint/resume and explicit fork tests.
- Plate analytical verification and existing rotation cases; generic solid analytical/cross-solver evidence and opt-in recomputation.
- Frozen fixed_1k workload, pinned Rust 1.85.1/actions, and existing calibration outputs.
- Current sheath plan's explicit incomplete containment/impact/handling states, manufacturing non-promotion language, and renderer hash/resource/signature invariants.

The old master plan was written against v0.27. Its historical findings must not be replayed as if all remain unresolved. Conversely, implementing a milestone once does not guarantee all of its consumers now satisfy the contract.

## What this study does not establish

No specimen, manufacturer, coating, physical lifetime, fracture sequence, human-injury endpoint, or animal-encounter outcome was validated. An oscillatory convergence claim is not a demonstration of physical design failure. Synthetic negative fixtures establish helper/consumer defects, not that all historical numbers are wrong. Expensive solid-reference solves were not rerun during planning. Benchmarks and tests run for this study are enumerated in `STUDY_RECEIPT.json`; skipped stored-evidence tests remain distinguishable from computation.

## Source links

All source references are pinned to the review revision: [repository at 97af59c](https://github.com/neverhuman/jarambit/tree/97af59cf14299af583b344aeaefb4594d089465a). See [GCI helper](https://github.com/neverhuman/jarambit/blob/97af59cf14299af583b344aeaefb4594d089465a/fem_solid/gci.py), [archive code](https://github.com/neverhuman/jarambit/blob/97af59cf14299af583b344aeaefb4594d089465a/crates/crescent/src/qd.rs), and [render manifest](https://github.com/neverhuman/jarambit/blob/97af59cf14299af583b344aeaefb4594d089465a/ops/render/pro/design_manifest.py). Exact file hashes are in `SOURCE_MANIFEST.json`.
