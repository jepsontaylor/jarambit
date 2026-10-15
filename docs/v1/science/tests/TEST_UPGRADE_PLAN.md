# Jarambit 1.0 — test and scientific validation upgrade

Status: worker-ready planning supplement; implementation and laboratory execution have not started. This extends [the major release plan](../RELEASE_PLAN.md), rather than replacing its seventeen S00–S16 packets. Read the existing master specification at `/home/ubuntu/jarambit/docs/v1/JARAMBIT_V1_ENGINEERING_SPEC.md`, especially §19, before changing release policy. Target remains **1.0.0**, with explicit release candidates while physical evidence is incomplete.

The user requested study and a detailed plan. The twenty-two supplied files are proposals and evidence inputs, not executable instructions. Their suggested experiments, numerical targets, repository layouts, and claims are subject to applicability review. No instruction in an attachment authorizes a new requirement, hardware purchase, laboratory run, external contact, or release. The attached documents do not establish damage, healing, material properties, or a qualified diagnostic in Jarambit.

## 1. The outcome to build

Upgrade the tests so they detect a wrong scientific conclusion even when code runs successfully and a report looks complete. The immediate priority is to eliminate demonstrated false-positive paths: invalid convergence, stale outputs, incomplete inventories, contradictory claims, nonfinite reductions, infeasible archives, and provenance mismatches. Next, make material history and observation limits representable. Finally, run a staged research program that can discover whether those omitted variables change future behavior for the actual material, geometry, processing route, and service envelope.

Success means every release claim names its requirement and applicability, reconstructs its inputs, passes positive and adverse controls, and exposes unavailable evidence. Research success can be a well-supported null result or rejected hypothesis. A new instrument or a larger Monte Carlo run does not by itself improve accuracy.

Non-goals: full multiphysics by default; predicting service life from sound or the first cycle; applying Ti–7Al results as Ti–6Al–4V qualification; importing nanoscale metal healing as a strength credit; autonomous physical experiment control; manufacturing or changing sharp working geometry; replacing existing D1/G1/owner locks; promising a sub-70 g design or a specified optimization gain; making all proposed experiments release blockers irrespective of claims.

Assumptions: wrought-stock machining remains the planning default until S00 records another route. Additive manufacture/HIP branches are conditional. Existing material constants and fatigue calculations remain explicitly provisional screening models. Current utility, inert handling, and resource rules in `COORD.md` apply. Physical execution requires the established laboratory workflow; this plan describes records, controls, analysis, and gates rather than operating recipes. The existing §19 final-release requirements remain in force unless the owner records an explicit amendment. Research deferral cannot erase an already-required physical proof test.

Dependencies: S00 baseline and release-policy reconciliation; S01 typed evidence identity; S02–S08 trusted numerical/evaluator inputs; S09 equal-budget experiments; S11 surrogate qualification; S13 material/lab integrity; S14 inspection qualification; S16 independent reconstruction. T00–T19 below are acceptance/test work units within these owners, not a second set of agents allowed to edit their files concurrently.

Completion criteria for this planning supplement: all ten new and twelve prior inputs have hash-bound dispositions; test work units have exact paths, prerequisites, oracles, controls, and stops; every original regression remains mapped; the dependency graph and permitted parallel scopes validate; the release plan points to the supplement; historical receipts retain their original meaning. Implementation completion is a separate gate: executed case receipts, independently reviewed claim matrix, exact-head CI, and the physical evidence required by the reconciled policy.

Stop a worker when its path conflicts with live ownership, an input/source hash changes unexpectedly, an oracle becomes circular, a required case disappears, a known-negative becomes positive without a requirement decision, the run exceeds admission/output limits, a tool mutates historical evidence, or applicability cannot be established. Record the blocked claim and continue unrelated work. Do not invent missing measurements, silently relax tolerances, rerun until a desired outcome appears, or replace a failed run's receipt.

## 2. Evidence studied and what still needs confirmation

The original audit froze `97af59cf14299af583b344aeaefb4594d089465a`; its executable baseline remains [STUDY_RECEIPT.json](../STUDY_RECEIPT.json). It passed 111 Rust tests with one existing ignored test, and 23 Python tests with one slow-test skip, yet adverse probes reproduced false-positive GCI/report/claim behavior. Those counts are historical baseline results, not results of the proposed new suite.

A follow-up comparison against checked-out main `bae2a3dac3e3962a37f3058439220bb933ad6f67` found 47 of the 48 previously selected source files unchanged. The changed file was the marketing smoke workflow; intervening changes include render tests that must be retained. Live coordination subsequently records #66 merging at `7042f199ad1a9c9e924b7aa68d514e8ea5123567`; distinguish that reported merge from the checked-out main SHA. S00 must resolve current refs and audit any later change before dispatch. No full current-main suite was rerun for this docs-only supplement.

[INPUT_COVERAGE.md](INPUT_COVERAGE.md) groups repeated proposals and records every source. [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) preserves the twenty-two input hashes and the follow-up source comparison. [LITERATURE_LEDGER.json](LITERATURE_LEDGER.json) separates primary sources actually checked from citations merely extracted from the proposals. Do not interpret the number of citations as the number of verified studies.

Primary-source checks support limited research directions:

- A 2022 study connects first-cycle localized slip to fatigue strength within its studied crystalline materials. Use this to motivate early-change measurements, not a universal individual-part lifetime estimator. [Science abstract](https://pubmed.ncbi.nlm.nih.gov/36048948/).
- A 2026 Ti–6Al–4V study reports early grain-boundary deformation and fracture under its specific microstructure and loading. It motivates testing spatial neighborhoods; it does not diagnose the current stock. [Primary paper](https://www.nature.com/articles/s43246-026-01102-3).
- The 2026 Ti–7Al multimodal dataset supports comparing surface observations with bulk slip information. It is a method benchmark with one specimen, not multiple independent production lots or Ti–6Al–4V validation. [Dataset article](https://www.nature.com/articles/s41597-026-08241-9), [Dryad data](https://datadryad.org/dataset/doi:10.5061/dryad.sj3tx96g8).
- NIST's 2026 nonlinear-acoustic study used two AM CoCrMo specimens. Its material and defect mechanisms differ from this project's default route; no acoustic threshold transfers directly. [NIST primary-study record](https://www.nist.gov/publications/acoustic-nonlinearity-and-loss-associated-unbonded-interfaces-and-dislocations).
- Preparation-induced hydrogen artifacts depend on material and preparation route; the cited study's CP-Ti and Ti6246 results must not be generalized to every Ti–6Al–4V preparation. [Primary preparation study](https://www.nature.com/articles/s41467-019-08752-7).
- Acceleration needs the relevant failure mechanism to remain comparable; different mechanisms can have different factors. An accelerated endpoint alone cannot establish service years. [NIST reliability handbook](https://www.itl.nist.gov/div898/handbook/apr/section1/apr14.htm).
- Reported metal crack healing is at nanoscale under specific conditions; later cracking and environmental limits remain relevant. It provides no bulk titanium-in-air recovery credit. [Original paper](https://www.nature.com/articles/s41586-023-06223-0), [research laboratory account](https://newsreleases.sandia.gov/healing_metals/).
- Atomistic average-error metrics can conceal important off-distribution errors. Specific model families show systematic energy/force softening in particular benchmarks. Qualify the actual potential and process, not a model category. [Error-metric study](https://www.nature.com/articles/s41524-023-01123-3), [softening study](https://www.nature.com/articles/s41524-024-01500-6).
- Geometry-dependent pore populations and active model-discrepancy learning are research leads. The referenced preprints do not establish Jarambit production equivalence or an autonomous laboratory's success. [Porosity study](https://arxiv.org/abs/2411.03401), [model-discrepancy study](https://arxiv.org/abs/2502.05372).

All design recommendations below are planning judgments, not conclusions demonstrated by those papers. Unchecked coating, isotope, electrochemical, and sensor citations must be reviewed by the assigned specialist before importing quantitative assumptions.

## 3. Read first, scope, and release classification

Every worker starts in this order:

1. `/home/ubuntu/jarambit/COORD.md` and the newest ownership entries; inspect rather than alter other screens.
2. `/home/ubuntu/jarambit/docs/v1/JARAMBIT_V1_ENGINEERING_SPEC.md`, `/home/ubuntu/jarambit/docs/v1/jarambit_v1_roadmap.json`, current requirement TOMLs, and the S00 amendment when written.
3. The worker's checkout of `docs/v1/science/RELEASE_PLAN.md`, `WORKTREE_RUNBOOK.md`, `FINDINGS.md`, and this document.
4. `TEST_WORK_PACKETS.json`, `TEST_CASE_CATALOG.json`, and this worker's T section; then the specific existing source/test files listed there.
5. Prior baseline/probe receipts and the supplied nineteen regression cases. Read raw evidence without changing it.

Paths in this plan are repository-relative unless explicitly absolute. The execution root is the assigned `/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-<owner>/`. New proposed paths are labeled **create**; they are not claimed to exist. Runtime changes stay with the S owner. Do not let a test worker fix a different owner's implementation or change an expected value merely to pass.

Keep Rust in the evaluator/search hot path. Python modules proposed here are offline test, import, record-checking and scientific analysis tools following the repository's existing CI/FEM/reporting pattern; they do not become a production material/evaluator shortcut. S01's typed Rust evidence resolver remains authoritative for eligibility. Validate cross-language interpretation and hash binding against its frozen wire contract before importing any offline artifact.

Forbidden/shared zones: live main `COORD.md` and its lock; another worktree, screen, scratch directory, or process; historical `evidence/wave27/**` and `evidence/fem_solid/**`; fixed benchmark genomes/hashes; current native CAD and render bundles; generated README/STATUS/WHITEPAPER; root Cargo files, versions, CLI entrypoint, and workflows except the integrator. New synthetic fixtures are clearly labeled synthetic and stored away from qualification evidence. Screens are persistence for owned jobs, not authority to send another worker keystrokes.

| Class | Required behavior | Release effect |
|---|---|---|
| D: deterministic software contract | Synthetic adverse/positive cases, independent or mathematical oracle, strict receipts | T00–T07 contract portions and T19 required for software RC; applicable capability contracts also required |
| N: numerical verification | Analytic/metamorphic plus fresh solver evidence, mesh/observable identity | Required for any numerical qualification claim; stored-record tests alone do not satisfy it |
| P: physical validation | Actual material/route/geometry, preregistered lab protocol, independent specimen/lot analysis | Existing §19 final gates remain; additional capabilities require their own physical support |
| R: research | Feasibility pilot, frozen hypothesis, controls, holdout confirmation | May be deferred with no associated claim; null/inconclusive/rejected results retained |

T08–T18 are selectively activated. Their importer, analysis, missing-data, and claim-boundary contracts become mandatory whenever their code or capability is shipped. Physical branches become mandatory only for claims they support or existing policy obligations. A disabled research feature is explicitly absent, not an unexecuted green test. No research result can waive a numerical or manufacturing gate.

## 4. Contracts that all new tests must share

### 4.1 Case inventory and outcome semantics

T00 creates a versioned expected inventory, independent of discovered output files. Each case has stable ID, owner, input hash, oracle version, evidence class, applicability, tier, negative and positive controls, and expected artifact. Inventory changes are reviewed as requirement changes when they alter a claim's support. Duplicate IDs, unknown schema versions, missing required cases, duplicate receipts, extra unsupported PASS claims, or absent controls are nonpassing. Optional cases require a machine-readable reason and a claim that they cannot support.

Separate **test execution** (`passed`, `failed`, `error`, `not_run`) from **scientific finding** (`supported_within_scope`, `rejected_within_scope`, `inconclusive`, `not_applicable`). A test can pass by correctly rejecting a false scientific claim. A correctly executed experiment with a null result is not a CI failure. A missing instrument is an unavailable result, not a failed biological/material hypothesis and not evidence of safety.

Do not add more verdict meanings to every historical record. Preserve `Obs`, `Outcome`, JEV1 reads, and historical adapters in S01. New envelopes carry execution and finding separately, then resolve to existing claim-level Pass/Fail/Incomplete. Historical data that cannot meet a new schema stays readable with its original scope and cannot silently qualify a new claim.

### 4.2 Separate material, history, observation, and interpretation

T07 extends S13 with four identities rather than one vague material fingerprint:

```text
SpecimenIdentity = material_lot + process_route + heat_treatment + geometry_hash
                + surface_process + parent_stock + chain_of_custody
ExposureHistory = ordered events with start/end UTC, monotonic elapsed time,
                  load/environment trace hashes, interruptions, and missing intervals
Observation = specimen + history_prefix_hash + time + location/ROI + method
              + raw_hash + calibration + units/frame + preparation + uncertainty
Interpretation = observation_ids + model/version + applicability + review + finding
```

Candidate state features may include residual strain/stress, microstructure/neighborhood summaries, chemical state, surface connectivity, defect populations, and instrument-specific signals. They are optional measured features with explicit unknowns, not invented constitutive state variables. Do not infer local atomic order from bulk composition or internal damage from a surface photograph. Observation uncertainty and model discrepancy are distinct from specimen variability.

Create schemas with strict finite numeric values, unit/dimension enums, uncertainty type, censored/limit-of-detection fields, coordinate transforms with handedness, calibration validity interval, preparation/intervention IDs, measurement population, lineage, and raw acquisition hash. Preserve raw sensor values and transformations; never convert a nondetection to zero. Missing/invalid observation produces `unable_to_determine` for a diagnostic interpretation. A legitimate measured zero remains a value.

Include event ordering, load-rate/dwell/rest clocks, time-zone conversion, temperature drift, operator/session, and duration uncertainty. Permit overlapping independently logged exposure/measurement intervals; reject impossible timestamp order or an unsupported exact time. A monotonic clock reset requires a segment and uncertainty, not fabricated continuity. History prefix binding prevents a post-exposure measurement being treated as pre-exposure data.

### 4.3 Oracles, controls, and independence

Use exact finite arithmetic or a small enumerated population for reducers; analytic relations and tensor transformations for solvers; independently specified manifest/claim rules for reporting; hidden synthetic generators with fixed truth for algorithm contracts; and blinded, independently measured reference outcomes for physical studies. Synthetic truth tests analysis mechanics and cannot validate the generator's realism. Two codes using the same assumptions are parity evidence, not independent physical validation.

Every new test family includes a valid positive control, its deliberately broken counterpart, and a null/control case where appropriate. Run focused mutation tests on dangerous claim paths: weaken the GCI validity check, remove one expected case, drop identity binding, accept a nonfinite sample, or change `unknown` into healthy. Required mutants must be killed. Avoid a global coverage percentage or thousands of tests that only repeat serialization implementation.

### 4.4 Statistical safeguards

Define the estimand, smallest meaningful effect, confidence level, nuisance factors, primary endpoint, missingness policy, and multiplicity handling before confirmation. Pilot data estimates variability and feasibility; it may train/calibrate a model but is excluded from its confirmatory holdout. Determine confirmatory specimen and lot counts from pilot variance, clustering, effect size, and required confidence. Do not declare an arbitrary small sample count sufficient. Fields, grains, cycles, repeated scans, and multiple images from one specimen are correlated measurements, not independent lots.

Split by specimen and parent stock/lot, then session/operator when they are plausible shortcuts. Duplicate or derived images, repeated material states, relatives, and calibration trajectories stay in one split. Fit normalization, segmentation thresholds, imputation, feature selection, and decision thresholds on training/calibration only. A sealed test set can be opened once; changes create a new version and a fresh challenge. For within-specimen longitudinal comparisons use paired/blocked analysis, not an independence assumption.

Distinguish aleatoric variability, finite-sample/parameter uncertainty, and structural model discrepancy. More samples only reduce Monte Carlo sampling error under the stated population model. Sensitivity to alternate plausible populations and correlations remains visible. Report interval widths and subgroup support, not only pooled accuracy or average error.

For example, zero misses among `n` independent relevant damaged specimens gives one-sided 95% upper miss bound `1 - 0.05^(1/n)` under a binomial model. With `n=30` it is about 9.5%, not proof of a 1% miss rate. Clustering or uncertain truth invalidates the simple independent calculation; use the preregistered hierarchical/cluster method. Implement an exact/binomial reference control and a correlated counterexample. Do not invent a 95% POD threshold before S00/S14 policy defines the damage class and decision requirement.

### 4.5 Inspection and warning semantics

Estimate `P(no alarm | relevant damage, stated conditions)` and `P(alarm | no relevant damage, stated conditions)` separately. Population-level silent degradation `P(relevant damage and no alarm)` additionally needs a credible prevalence model; do not infer it from an artificially balanced case set. Specify damage class, size/location, accessibility, material/finish, environmental envelope, reference-truth uncertainty, and reader/instrument conditions.

Diagnostic outcomes are `changed`, `no_change_detected_within_scope`, or `unable_to_determine`. Never expose universal `safe`, `healed`, or `remaining_life` from an unqualified signal. Invalid calibration, detached/faded/blocked witness, lost baseline, ambiguous registration, or untested region returns unknown. Joint sensors sharing fixture, temperature, prep, or model errors are not independent confirmation.

Warning margin is measured against a lab-defined stopping endpoint. Preserve no-alarm failures as misses; do not drop them from lead-time statistics. With sampled observations, alarm and endpoint times are intervals. Report distribution/quantiles, false alarms, unreadable cases, late warnings, and uncertainty, alongside baseline visual inspection. A warning that disappears after unloading does not demonstrate damage reversal.

## 5. Ordered implementation work units

The machine-readable [TEST_WORK_PACKETS.json](TEST_WORK_PACKETS.json) contains IDs, dependencies, scopes, case IDs, validation commands, and receipts. [TEST_CASE_CATALOG.json](TEST_CASE_CATALOG.json) expands the named cases. The following instructions give the implementation order and hard parts. All new modules and test files are **proposed creates** unless listed as existing. Keep each S-owner change reviewable; split runtime/schema/tests into sequential PRs under the existing <=800 changed-LOC guidance, excluding fixtures. Do not create one enormous PR for the whole table.

An S packet closes after its own required core phase, not after a successor's phase of a shared T unit. S05's T04 search checks close before S06 checkpoint work; S07's T05 numerical checks close before S08 bindings; T00 gates S01, while S00 only freezes policy. Conditional research runs after base S13/S14 interfaces close and gates S16 if its capability is claimed. Do not make S13 closure depend on a research review requiring completed S14, or create any similar predecessor/successor cycle. The S and T DAGs express different layers; T phase receipts name the exact owning S files. The parent packet JSON includes the added paths in its actual allowlist and records their exact ownership.

### T00 — inventory, strict records, independent control harness

Parent owners S00/S01; complete after their interface freeze and before any T implementation. Read `crates/evidence/src/lib.rs`, `crates/evidence/tests/log.rs`, `metrics/global_metric.py`, `metrics/tests/test_global_metric.py`, `ops/ci/check_json_strict.py`, and the supplied regression JSON.

Create `assurance/testing/{__init__.py,contracts.py,catalog.py,receipt.py,policy.json}`, `assurance/testing/tests/test_contracts.py`, `assurance/schemas/{test_case,study_record,observation_record,qualification_result}.v1.json`, and `ops/ci/test_inventory.py`. The integrator adds their imports/registration; this unit does not edit root requirements or workflows.

1. Freeze the catalog into the S00 policy with schema/input/oracle hashes. Implement `validate_case`, `validate_receipt`, `resolve_inventory`, and `resolve_claim_support`; each accepts explicit data, not implicit filesystem state.
2. Implement strict JSON ingestion rejecting duplicate keys, bool-as-number, NaN/infinity, malformed numbers, oversized/deep payloads, and unknown status tokens. Resource limits are policy fields and tested at their boundary. Preserve non-English specimen IDs and reject ambiguous normalization collisions rather than rewriting identity. Use cross-language fixtures for key ordering, Unicode, large integer IDs, exponent formatting, signed zero and full-precision thresholds under S01's declared canonical wire version. Raw-file and canonical scientific hashes have different roles; semantically equivalent parsed JSON does not automatically have identical bytes. A Python serializer must not invent an incompatible canonicalization or change Rust eligibility semantics.
3. Require hashes, execution exit/timeout state, executed command arguments, controls, evidence class, and applicable expected IDs. Receipts are atomically published only after artifact hashes and result counts reconcile. A crash produces an incomplete attempt, not an empty pass.
4. Add control mutants for missing inventory, dropped nonfinite rejection, broken identity, and unknown-to-healthy conversions. Mutations run in disposable fixture copies, never source/history edits. Store which mutation was killed and the expected failure reason.
5. Test required vs optional coverage, duplicate/reordered cases, absent positive controls, tampered raw hashes, unknown schema, corrupt receipt, and correct rejection of a known-invalid scientific claim. The inherited named-standard scope regression is a mandatory generic contract here: use a clearly synthetic standard descriptor to challenge wrong edition/method/specimen applicability, then S14 integrates actual verified standard descriptors. It stays required even when new diagnostic research is deferred. A valid negative scientific finding must still yield a passing execution test.

Validate `python3 -m unittest discover -s assurance/testing/tests -v`, then `python3 ops/ci/test_inventory.py --catalog <frozen-catalog> --receipts <attempt-dir> --policy <frozen-policy>`. These commands become available only after this implementation. Acceptance: expected coverage cannot increase when evidence is deleted; all dangerous mutants are killed; unavailable required cases resolve incomplete; original G1/D1 semantics survive. No new physical evidence label is synthesized.

### T01 — numerical convergence, freshness, and historical reclassification

Owner S02 after S01/T00. Read `fem_solid/gci.py:gci`, `gci_report.py` (currently executes at import), `convergence.py:level/main`, `run_tip.py:main`, `tests/test_gci.py`, `tests/test_gci_evidence.py`, and old adverse probes. Edit only S02's files and create `fem_solid/tests/test_fresh_attempts.py`, with the existing owner allowlist extended first.

1. Refactor a pure `compute_gci`/`build_report` interface with explicit level convention, dimensions, refinement metric, observable, and inventory. Preserve a versioned historical adapter rather than retroactively assigning new status to raw historical bytes.
2. Construct an analytic family `f(h)=f_exact+C*h^p` for known positive `p`, a deliberately divergent family, a plateau, and an alternating family. Declare coarse/mid/fine order explicitly; do not port old `f1/f2/f3` names without checking their convention. Equal-ratio textbook fixtures do not prove the current coupled triangulation/layer refinement is a uniform asymptotic sequence.
3. Cover negative/zero/nonfinite order, `r<=1`, zero reference, exact equal values, almost-equal values near numerical precision, oscillation, wrong level order, duplicate meshes, unit or region mismatch, malformed fields, threshold neighbors, mixed valid/invalid design inventory, and empty reports. Equal values alone are not evidence of asymptotic convergence; classify as undetermined unless independently supported by a defined special case. No negative GCI can pass a positive threshold.
4. For nonuniform/anisotropic refinements, require an approved effective refinement definition or return unsupported; do not insert `r=2` because layer counts doubled. For a peak singularity, characterize mesh sensitivity and physical regularization; a global norm convergence cannot certify a local unbounded maximum.
5. Change fresh execution to content-bound, attempt-unique output directories. Preexisting result + failing/no-op subprocess, wrong material/region/mesh hash, nonzero exit with valid-looking JSON, missing completion marker, partial manifest, disk-full/rename failure, and concurrent same-key attempts must not masquerade as a fresh solve. Include a positive compatible cache hit, explicitly labeled reuse rather than execution.
6. Generate a new reclassification report from unchanged historical records, including the archived oscillatory case. Publish invalid/undetermined statuses separately from physical failure. The report must not rewrite the old evidence or claim a new physical result.

Validate the Python solid suite without enabling expensive solves; run targeted fixtures first. Numerical lane separately runs fresh analytic verification and an admitted solid regression. Acceptance: valid analytic family reproduces the independently computed p/GCI within documented tolerance; every adverse case resolves nonpassing with reason; required coverage is complete; stale files cannot satisfy a new execution claim.

### T02 — claim mutations and requirement binding

Owner S03 after T00/T01/S03 interfaces. Read `ops/ci/check_claims.py:check_block`, `rs_verdicts.py:verdict`, `metrics/global_metric.py`, current C10a/C9.3 status records and requirement TOMLs. Edit S03 tests `ops/ci/tests/test_claim_integrity.py`, `test_requirement_identity.py`; runtime fixes remain S03. Render-consumer mutations belong to S15/T19 after its live lane releases ownership.

Build temporary repo-like fixture roots with one canonical requirement/claim registry. Exercise missing V4, reopened V3, stale candidate heading, scoped FAIL plus appended scoped PASS, markdown/HTML/comment noise, duplicate generated blocks, identical RS-id with changed TOML content, wrong candidate, wrong material/observable/geometry hash, old reviewer approval after dependency change, missing physical validation, negative safety factor, nonfinite/boolean values, and records-only mass targets presented as hard qualification.

The oracle is the declared registry and exact canonical generated verdict block, not substring search against the same output. Compare parsed claims to expected requirements; presentation format tests remain separate. Positive control: complete bound evidence plus canonical block passes. Negative scientific control: known D1 failure produces a truthful report with passing report-integrity execution. Check G1 completeness/zero cases and the legacy historical adapter. No deletion of an input may strengthen a claim.

Validate focused claim tests, the existing claim checker, metric tests, and generated-output check mode. The integrator reviews proposed generated diffs. Acceptance: every unsupported promotion mutation fails integrity while correctly scoped negative/incomplete statements remain usable. `of record`, file existence, or an old certificate cannot mean currently qualified.

### T03 — Monte Carlo, population assumptions, and joint events

Owner S04 after T00/S01. Read `crates/monte_carlo/src/lib.rs:run_cols/run/pct_index/mix_seed`, `crates/evolve/src/lib.rs`, and its replay tests. Implement tests under `crates/monte_carlo/tests/{checked_reduction,joint_scenarios,population_sensitivity}.rs`; S04 owns `try_run_cols`, `stats.rs`, and `scenario.rs` changes.

1. Use small enumerated columns and rational/compensated reference sums. Test n=0, n=1, boundary sample counts, odd sizes, negative/zero valid observables, huge finite overflow, cancellation, extreme dynamic range, worker panic, one invalid column, invalid sample identity, duplicates, and missing workers. A rejected sample stays in requested/executed/valid/invalid counts; never silently condition on survivors.
2. Specify quantile convention by example and immutable schema version. Verify mean, tails, counts, and error propagation against an independent sorted reference. Do not test only the same helper twice.
3. Evaluate sample-level joint success before marginal sorting. Enumerate a four-state counterexample with identical marginal success fractions but different joint success. Include independence and correlated positive controls. Scenario correlation is physical/model data, not an extra arbitrary RNG correlation knob without provenance.
4. Preserve indexed random streams across 1/2/4 workers and batch order, explicitly distinguish exact same-build replay from cross-platform numeric tolerance. A stochastic distribution test uses predeclared finite seeds and a conservative false-rejection budget; no flaky single-p-value gate.
5. Add labeled measured/assumed/bounded/unknown population scenarios. Test a model-discrepancy case where two plausible distributions predict different risks despite increasing n. The output must display assumption dependence, not a narrower universal failure probability. Extreme-load discovery sets are not a service-population sample.
6. Test the retirement adapter for historical CutMedia records; active utility evaluations must not invoke the retired lookup. Preserve legacy read/replay scope, and do not equate removing a token with scientific replacement.

Validate `cargo test --release -p jarambit-monte-carlo` (confirmed from `crates/monte_carlo/Cargo.toml`), plus affected evolve replay. Acceptance: zero samples cannot become one; no invalid sorting; joint truth preserved; counts reconcile; Monte Carlo error and population uncertainty remain distinct.

### T04 — search, lineage, checkpoint, and crash boundaries

Owner S05 followed by S06; never run both writers against `crates/crescent/src/qd.rs`. Read `qd.rs:feasible/fitness/qd_cell/run_with/run_islands_with`, existing crescent tests, `crates/evolve/tests/replay.rs`, and `crates/evidence/tests/log.rs`. Create/update S05 `search_contract.rs`, then S06 `checkpoint_replay.rs` and `evidence_lineage.rs`.

Use a cheap deterministic `EvalFn` with planted feasible/infeasible/failed records; this checks selection logic without expensive FEM. Cover all-infeasible population, legal-but-not-feasible record, partial FEM, nonfinite descriptors/fitness, duplicate genotype versus separate birth identity, descriptor boundary, out-of-domain descriptor, deterministic ties, empty population, invalid island/migration configuration, and novelty-only context changes. A contextual novelty score can guide exploration but cannot replace a context-free elite without a quality improvement.

For replay, compare uninterrupted and resumed runs at 3 seeds × generations 3/7/12 using exact scientific state, counters, RNG bytes, archive, and lineage. Runtime timestamps/RSS need not match. Test interruption before/after event flush and checkpoint rename, torn/corrupt/missing checkpoint, changed evaluator/material/requirements/operator/descriptor hashes, disk-full log flush, duplicate resume, and explicit fork creating a new run identity. Qualified publication stops on logging/durability failure even if exploratory computation continues with a recorded incomplete status.

Fault injection targets only child processes created by this unit in its own worktree; never kill a shared farm/node/screen. Capture the injected boundary and last durable frame. Acceptance: no orphan elite, missing parent, duplicate accepted evaluation, or certified archive contamination; replay matches; incompatible resume is rejected. Existing legacy replay tests remain.

### T05 — solver, fields, transformations, and tier bindings

Owner S07, with S08 integration after S07 hands back. Read `crates/physics/src/verify.rs:theory_gate/cantilever`, `fem_solid/solve_dolfinx.py:solve`, `fem_solid/tests/verify_analytic.py`, `crates/crescent/src/fem.rs:certify/Fields`, and `crates/cli/src/bench.rs` exact-genome binder. Edit S07 `invariance.rs`, `test_representation_invariants.py`, `test_field_semantics.py`; S08 owns `certified_bindings.rs` and consumers.

1. Retain analytic beam/torsion/hole tests and add load scaling in linear elasticity, rigid translation, physical rotation of geometry/loads/constraints, and unit-consistent rescaling. Rotate tensors as tensors; do not expect individual components to remain unchanged. Scalar invariants should remain stable within mesh/interpolation tolerance. Scaling geometry while leaving loads unchanged is a different physical problem, not an invariance.
2. Validate force/moment balance and work/energy consistency under the solver's actual BC model. Include bad clamp/traction tags, unsupported/near-singular systems, inverted/degenerate/disconnected elements, solver nonconvergence, invalid E/nu, and finite-looking fallback outputs. Near-nullspace treatment does not replace physical restraints or compatible loads.
3. Pin the observable contract: element/DG/node/projection, interpolation order, stress reduction, ROI boundary definition, sample location, and unit. Verify a controlled stress field and a localized planted peak; global mean/L2 agreement cannot validate a local minimum SF. Current DG interpolation must not be called an L2 projection without implementing and verifying it. Preserve both raw local field and aggregation derivation.
4. Enforce certificate-field identity. A scalar from fine mesh B must not be shown on coarse mesh A; mixed minima require per-observable references or separate records, not an invented single field. Test wrong mesh/step/region/element order/geometry/case/material and absent mesh fingerprint. Exact genome binder remains necessary but insufficient for native B-rep claims.
5. Compare T1 plate, fine plate, solid, and native CAD per named case. Successful-only calibration selection is forbidden; failures remain in denominators and applicability tables. Tier labels include solver/model identity, so two incompatible uses of T2 cannot collide.

Validate fast contract suites; schedule analytic/solid runs separately in the numerical lane. Acceptance: transformations and independent theory match predeclared tolerances; bad bindings are incomplete; all expected cases present; local extreme errors stay visible. No arbitrary tolerance tightening that exceeds solver/mesh/reference accuracy.

### T06 — benchmark integrity, statistics, and leakage tests

Owners S09 then S11 consumers. Read `ops/bench/run.py`, `ops/calibration/t1_t2.py`, fixed-1k manifest, `docs/calibration/t1_t2.json`, and S09 protocol. Create `assurance/testing/{statistics.py,splits.py}` and their unit tests after T00 closes; add S09 `ops/bench/tests/test_science_protocol.py`. S11 owns surrogate integrations and tests after the helper interface is frozen.

Test CPU accounting with a synthetic subprocess whose wall, child CPU, parent CPU, and RSS are independently measured; do not call summed wall time core-seconds. Verify exact genome/order hashes instead of rounded sum checksums; use a collision pair with identical rounded sums and different rows. Capture cold/warm/cache/failed work separately. Budget includes attempted evaluations and expensive confirmations, not just successful calls. Compare optimization algorithms with identical evaluator/representation/objectives, common seed schedule, and preregistered total budget; do not force equal accepted evaluations when algorithms fail differently.

Create split fixtures with repeated images, same parent stock, sibling genomes, one specimen's time series, session/operator shortcuts, and train-only preprocessing. Leakage rejection needs stable group IDs and lineage hashes; a missing group is unknown rather than a unique singleton. Include a one-specimen public dataset whose valid method exercise cannot pass a multi-lot-generalization gate. Test intervals, censored observations, cluster resampling, multiple comparisons, negative/null optimization results, and zero-variance/empty strata handling.

S11 adds frozen calibration/holdout tests for interval coverage, threshold-near errors, false-feasible candidates, OOD abstention, domain shift, ensemble agreement with shared bias, and unavailable labels. Every finalist requires independent higher-tier confirmation; surrogate confidence cannot replace it. Do not assert a promised optimization gain or target MAPE as an observed result.

Retain the parent S10 core/evaluator and algorithm reference tests before attributing an equal-budget gain: shared trait/representation/objective bindings, rejected decoder output, deterministic ties, constrained dominance on a hand-enumerated front, hypervolume against a small independent exact calculation, and a planted weak/optimum evaluator. These remain S10-owned `crates/core/tests/*` acceptance, not a second T06 writer. Representation or repair changes require decode/connectivity/physical-measure checks under the existing S10 protocol; algorithm changes cannot borrow a better representation for only one method. S12 similarly retains identity-bound cache and owned-worker fault/retry accounting tests; increasing worker count cannot hide dropped or duplicated evaluations. T19 collects those parent receipts before a performance/reliability claim.

Acceptance: reordered/missing/genome-colliding work fails workload identity; leakage fixtures fail; negative scientific results report honestly; widening model uncertainty does not perversely strengthen certification. Validate helpers and bench tests before expensive trials.

### T07 — laboratory, history, and observation schema contracts

Owner S13 after T00/S01. Read S13 schemas, `materials/states/*` when created, existing laboratory protocol, and current material assumptions. Create `assurance/laboratory/{records.py,history.py,observation.py}`, `assurance/schemas/{exposure_history,measurement_intervention}.v1.json`, and `assurance/tests/test_history_observation.py`; extend `test_laboratory.py` and the S13 specimen/material schemas through this same owner.

Implement `validate_specimen`, `validate_history`, `bind_observation`, and `validate_intervention`. Tests include reused specimen ID from another lot, absent processing route, changed process/surface invalidating a prior qualification, uncertain/preparation-induced chemistry, unmatched raw acquisition, wrong history prefix, future calibration, wrong coordinate frame, censored nondetection, legitimate zero, incompatible uncertainty type, invalid time conversion, interrupted trace, instrument drift, duplicated scan, and missing operator/session grouping. Add an independent reducer oracle for known raw load/strain/mass traces, including baseline drift, unit conversion, missing segments and runout censoring. Verify finished part/carrier/assembly mass as separate measured configurations with uncertainty; never substitute bare-part mass for finished assembly. Recorded chemistry is distinct from inferred local organization; unknown microstructure must remain unknown.

New fields must support dry imports and synthetic contracts without a laboratory. This schema support is mandatory for 1.0's data integrity; it is not proof that history affects the current material. A material property update requires a reviewed dataset and scope, not a schema field. Validate `python3 -m unittest discover -s assurance/tests -p 'test_*laboratory*.py' -v` plus `test_history_observation.py` and T00 contracts. Acceptance: raw/processed/interpreted records stay traceable; unavailable observations cannot become healthy; correct censored data imports; historical incomplete records stay readable.

### T08 — bounded public multimodal benchmark

Owner S13 research adapter after T06/T07. Create `research/science_v1/multimodal/{dataset_card.json,import_ti7al.py,registration.py,protocol.json,tests/test_import_registration.py}` and `docs/validation/science_v1/MULTIMODAL_METHOD.md`. No dataset archive enters Git or the committed evidence namespace.

The checked Dryad deposit is about 156.92 GB. Small 2D EBSD and DCT reconstruction files can exercise schemas, grain IDs, coordinate transforms, and surface/bulk registration. They do **not** contain the matched DIC slip measurements needed to reproduce the full slip-analysis claim. The topotomography archive alone is about 2.24 GB compressed; expansion plus scratch may exceed the per-packet 5 GB limit. Inspect archive listings and expanded sizes before download/decompression; choose a hash-pinned bounded subset only if public granular access permits it. Otherwise mark full reproduction unavailable and seek an approved separate data budget through the executor. Do not scrape around access limits or pretend a partial subset is the full benchmark. No data were downloaded for this plan. [Deposit metadata](https://datadryad.org/dataset/doi:10.5061/dryad.sj3tx96g8).

1. Freeze DOI/version/license/citation and allowed file list. Preserve article early-version status and README differences in the dataset card. Resolve ambiguous units from authoritative metadata; never guess a physical unit from a column name. Record the importer environment and exact NumPy/HDF5/TIFF reader versions used in the approved environment; synthetic contracts must run without downloading public data. If required readers are absent, report dependency-unavailable rather than silently drop a modality. The worker proposes a pinned dependency file in its own multimodal scope for integration review; it does not install a new solver stack or modify shared dependencies.
2. Build a synthetic tiny HDF5/EBSD/TIFF-style fixture with known transforms, orientation convention, grain identity, slip direction and missing grain. Qualify conventions, quaternions/crystal symmetry, degrees/radians, mirrored frames, confidence masks, and inaccessible regions before public analysis.
3. Apply registration with measured uncertainty and no hand-picked corrective transforms from held-out outcomes. Record observable location and loaded/unloaded state; surface residual slip and in-load bulk measurements are different observables.
4. If matched data fit the budget, reproduce only the prespecified method-level contrast with missing/unobserved grains visible. All repeated acquisitions/grains share specimen group; no production-lot accuracy claim. If they do not fit, deliver an importer/registration test only.

Acceptance: synthetic transformations and false matches rejected; acquisition completeness explicit; single-specimen method exercise cannot satisfy material qualification; download/expanded-size caps hold. A full scientific reproduction is a separate receipt from metadata/importer PASS.

### T09 — hidden-state collisions and early irreversibility

Owner S13 research study after T06/T07 and feasible metrology pilot. Create `research/science_v1/state/{protocol.json,analysis.py,tests/test_state_collision.py}`, `docs/validation/science_v1/HIDDEN_STATE.md`. Inputs are approved coupon records; no direct physical control.

Preregister candidate summaries: geometry/composition only; plus present dimensions/stiffness/appearance; plus history; plus measured microstructure/residual-state features. Choose future endpoints and the smallest meaningful difference before history matching. Split by parent stock/lot. Match or block nuisance variables and record unmatched specimens. Selecting only survivors or post-history lookalikes can induce selection bias; prespecify matching before seeing future outcomes and report excluded paths. A failed match is not evidence that a state is sufficient.

Compare distinct documented histories that fall inside the same apparent-state uncertainty band. Include unexposed/sham, reversible-load, and deliberately informative hidden-state synthetic controls. Test whether history/features improve held-out future prediction or explain a prespecified difference, with paired/cluster uncertainty. Use early irreversible strain/local slip only if independently measured and calibrated; do not turn a visible slip trace into a crack label or an individual life estimate. Time after unloading and measurement perturbation are part of the protocol.

Implement an offline synthetic benchmark where two latent states share observed averages but have different futures, plus a true-sufficient-summary null generator. The analysis must detect omitted state in the former and avoid asserting it in the latter. Confirmatory physical study is powered after the pilot; a small null result is inconclusive, not proof of Markov sufficiency. Output scope/uncertainty and the next falsifier, not a universal state model.

Acceptance: preregistration frozen, independent held-out lots/specimens, selection/observer confounding audited, calibrated feature limits, and all exclusions/censoring reported. Proceed to new constitutive variables only after confirmation; until then history is an evidence feature, not a strength penalty/bonus.

### T10 — spatial neighborhoods, orientation, and chemistry organization

Owner S13 research after T08 conventions and T09 pilot design. Create `research/science_v1/neighborhood/{graph.py,features.py,analysis.py,protocol.json,tests/test_neighborhood.py}`, `docs/validation/science_v1/MICROSTRUCTURE.md`.

Start with histogram/bulk baseline vs explicit spatial graph. Record orientation convention, phase, grain-volume weighting, neighborhood rule, resolution and boundary uncertainty; account for ROI truncation and surface-versus-bulk sampling. Build synthetic graphs with identical marginals but different topology, physically rotated equivalent graphs, symmetry-equivalent orientations, and registration perturbations. Graph shuffling preserves declared marginals as a statistical control; it does not represent a manufactured specimen. Test edges and correlations deliberately, not an arbitrary graph-neural model first.

For chemistry, compare certificates and actual phase/local-state measurements only when the measurement route can resolve them. Do not infer oxygen location, clustering or interstitial state from total wt%. Match chemistry while varying verified organization when feasible; otherwise keep the unresolved feature unknown. Early grain-boundary/plasticity hypotheses require the actual relevant microstructure, loading, and uncertainty, not merely a Ti label.

Hold out specimens/lots, not individual grains, for material-generalization claims. Report error by boundary/orientation class and interior/free-surface location. Acceptance: topology adds held-out information beyond histogram/nuisance baselines or a valid scoped null is reported; gains disappear under outcome-preserving nonsense controls when appropriate; no small-grain counts inflated into independent specimens. Stop on unresolved orientation convention or insufficient 3D observability.

### T11 — sequence, dwell, competing clocks, and acceleration

Owner S13 research; S14 reviews service relevance. Create `research/science_v1/history/{protocol.json,analysis.py,tests/test_sequence_clocks.py}`, `docs/validation/science_v1/HISTORY_ORDER.md` and `ACCELERATION.md`.

Plan exposure arms A→B, B→A, A-only, B-only, unexposed and handling/sham with matched total exposure, elapsed time, rest, temperature, fixtures, and observation schedule. Define A/B through the approved lab's benign coupon protocols; this plan supplies no operating recipe. Include intermediate measurements, crossovers only where their carryover is interpretable, random assignment and lot blocking. Comparing two sequences while both their clock durations and observation frequency differ cannot isolate order.

Separate equal-cycle and equal-time comparisons across rate/dwell conditions. Record measured local strain/temperature and environment when available; constant external load does not imply constant local stress. Include a synthetic additive/order-independent null and a history-dependent positive generator. A null order effect is valid and should not trigger a more flexible model by default.

Acceleration qualification compares mechanisms, initiation location, microstructure/surface state, reference observations, and outcome distribution across stress cells. Keep mode-specific factors; a shifted endpoint with changed failure mode is marked nontransferable. No single Arrhenius/time factor, extrapolated service years, or fixed Miner rule becomes accepted from fit alone. Preserve competing failure modes, surviving units and right/interval-censored endpoints. Frequency-induced heating and chemical exposure duration are explicit nuisance/mediating variables.

Acceptance: protocol distinguishes event order from total exposure and sampling; invalid acceleration counterexamples rejected; physical applicability and minimum evidence recorded. Stop extrapolation when mechanism invariance is unsupported. Continue descriptive scoped results.

### T12 — observer effects and preparation artifacts

Owner S13 research after T07; disjoint analysis scope. Create `research/science_v1/observer/{protocol.json,analysis.py,tests/test_observer_effect.py}`, `docs/validation/science_v1/OBSERVER_EFFECTS.md`.

Plan frequent-observation vs sparse/endpoint groups, prep-only/sham controls, matched storage/handling, random session/operator assignment, and an independent route where technically available. Preserve measurement intensity, exposure dose or duration metadata, vacuum/air/liquid differences, beam history, FIB/sputtering/sectioning, cleaning, and transfer. Observation can change the specimen; environmental removal can also remove a mechanism. Record both possibilities rather than labeling all anomalies artifacts.

The offline challenge separates real material change, measurement-created change, measurement-erased change, baseline drift, and no effect. Test an instrument correction learned on training data; no post-hoc subtracting all inconvenient drift. Preparation sensitivity reports its material-specific applicability. The cited hydrogen-artifact work cannot establish current Ti–6Al–4V artifacts without direct evidence.

Acceptance: nuisance-only synthetic changes are not diagnosed as damage, true changes under validated nuisance bounds stay detectable, unsupported bounds yield unknown, and observation schedule is part of the record. Preparation effects and uncertainty are visible even if an independent route is unavailable. Stop causal claims on unseparated preparation/exposure confounding.

### T13 — surface/interface history, topology, and material accounting

Owner S14 research after T07/T11/T12 interfaces; keep its ongoing `SURFACES.md` writer separate and deliver `docs/validation/science_v1/SURFACE_HISTORY.md`. Create `research/science_v1/surfaces/{protocol.json,topology.py,balance.py,analysis.py,tests/test_surface_history.py}`.

Use controlled coupon records to distinguish film deposition/process effect, barrier recovery, substrate damage, deformation, wear, electrochemical response, and debris evolution. Plan single-exposure and coupled/ordered arms plus sham process; controls must allow antagonism, additive behavior, synergy, and no measurable interaction. Do not hard-code synergy. Fixed friction/film lifetime assumptions remain models until history evidence contradicts them.

Compare film defect fraction/thickness averages with connectivity, largest connected region and local recovery-time distributions at declared resolution. Test synthetic maps with same mean and different connectivity, pixel-scale noise, threshold choice, inaccessible region, and registration shift. Select segmentation parameters before endpoint comparison; a result sensitive to resolution becomes uncertainty, not a discovered universal percolation threshold. Local images do not establish whole-part barrier integrity.

Balance substrate/film/debris/solution measurements with blank, recovery, contamination and uncertainty records. Elemental loss from mechanical wear is not necessarily Faradaic charge. Test exact synthetic conservation, missing reservoir, uncertain collection efficiency, baseline/substrate oxidation, and unit mismatch. Isotope tracing is T16's optional specialist analysis; atomic exchange alone does not establish growth/healing.

Acceptance: missing reservoirs prevent a complete balance claim; barrier recovery cannot imply mechanical restoration; no film/process effect is assigned without its control; surface thresholds stay scope-bound. No new coating, deposited edge material, or manufacturing alteration is executed by software workers.

### T14 — inspection blind zones and external acoustic diagnostics

Owner S14 after T00/T06/T07/T12. Create `research/science_v1/inspection/{protocol.json,acoustic.py,observability.py,analysis.py,tests/test_observability.py}`, `assurance/qualification/inspection.py` through the same owner, and `docs/validation/science_v1/ACOUSTIC_INSPECTION.md`. `INSPECTION.md` remains S14's canonical requirement integration.

1. Define relevant damage classes and reference truth with uncertainty; preserve undetermined truth rather than assign healthy. Reference methods have resolution, access, and preparation limits. Never define true damage using the candidate acoustic/witness signal itself.
2. Compare visual/current inspection to external nonlinear response and any independently justified complementary method. External excitation has no permanent added mass but still may change material state, so T12 controls apply. Calibrate fixture/support, excitation amplitude/waveform, instrument harmonic distortion, gain/saturation, contact coupling, temperature, geometry, operator and session. Include healthy specimens with nuisance changes, unchanged damaged specimens with fixture changes, blinded negatives and meaningful positives.
3. Fit features/thresholds on training/calibration, freeze before whole-lot/session holdout. Include identity-shortcut challenge where a classifier can learn specimen/session instead of damage. Linear frequency, damping and nonlinear features are separate observations, not interchangeable proof.
4. Report conditional POD/miss/false-call rates and uncertainty by damage location/class, finish and nuisance envelope; inaccessible zones remain unknown. Add geometric inspectability maps only as qualified observations, not new optimization rewards before validation. Shared-nuisance multisensor agreement cannot make unknown truth known.
5. Compare warning margin against lab-defined endpoint using interval-censored times; retain missed/no-alarm and unreadable records. Report single-sensor and combined system performance, with explicit shared failure cases. Removing missed failures must make the analysis contract fail.

Acceptance: damaged-but-silent and healthy-but-changed fixtures handled correctly; invalid calibration returns unknown; no safe/life output; reference truth and test prevalence explicit; sample size supports the claim or it remains inconclusive. A named standard-compliance claim also binds the verified standard edition, method, specimen and scope; an out-of-scope coating test cannot qualify it. Instrument repeatability alone cannot qualify a damage diagnostic.

### T15 — optical witness, self-test, persistence, and mass accounting

Owner S14 research after T14/T13. Create `research/science_v1/witness/{protocol.json,decoder.py,analysis.py,tests/test_witness.py}`, `docs/validation/science_v1/DAMAGE_WITNESS.md`. Initial scope is an inert polymer carrier/coupon, not a new finish on working metal.

Compare damage signal vs reversible strain/exposure signal, sham/reference patch, and independent witness validity. A self-test or reference channel must have specified failure modes; two nearby dyes with shared fading/delamination are not independent confirmation. Test active-region fading, reference fading, missing patch, blocked view, bleaching, delamination, dirt/wetness/light/color-camera variance, reader error, wear, and valid zero signal. Invalid witness returns unknown, never healthy. A witness reports its own exposure until mechanical coupling to component damage is validated.

Define warning persistence after unloading, rest, washing and apparent barrier recovery. Preserve previous alarms/history; fading signal must not erase a prior alarm. Test interval-censored margin, late/no alarm, false positives, and comparisons with baseline visual inspection. Calibrate damage threshold against independent reference and whole-lot/reader holdout. Added mass, dimensions, attachment durability, maintenance, and interference with inspection are measured; no inferred strength benefit.

Acceptance: self-test/shared-failure cases fail closed; persistent warning/history works; strain-only control is not classified as component damage; mass budget and readability evidence complete. No physical deployment or working-edge coating is part of this plan.

### T16 — recovery discrimination, failure migration, and optional isotope forensics

Owner S14 research after T12/T13; independent files `research/science_v1/recovery/{claims.py,balance.py,analysis.py,protocol.json,tests/test_recovery_claims.py}` and `docs/validation/science_v1/RECOVERY_CLAIMS.md`.

Represent appearance, surface barrier/electrical response, contact/closure, cohesive rebonding, recovered function, and stability under subsequent history as separate claims. A photograph of closure, lower current, restored resonance or repassivation supports only its measured observable. Require independent mechanical and structural evidence plus applicable subsequent-condition controls before stronger claims. Null recovery and renewed failure at another site remain outcomes; preserve initiation site/mode, internal vs external damage, surviving units, and competing risks. A new failure mode cannot disappear from totals because the original location improved.

Optional isotope analysis is a specialist protocol to distinguish original, environment, processing and preparation sources with blanks, unlabeled/labeled controls, exchange/mixing/recovery models and chain of custody. This plan provides no chemical preparation instructions. Test synthetic conservation, source ambiguity, isotope exchange without net growth, instrument cross-contamination, uncertain reservoir recovery, and preparation-introduced species. Insufficient source identifiability yields unresolved, not a preferred causal story.

Acceptance: every false-healing fixture rejected at the appropriate claim level; genuine scoped recovery positive control can pass only its supported level; migration is accounted; no bulk titanium strength credit derives from nanoscale literature. Isotope branch may be deferred independently of recovery-claim software tests.

### T17 — atomistic qualification and time-scale bridge

Owner S11 research specialist; no production FEM/material changes. Create `research/science_v1/atomistic/{model_card.json,challenge_manifest.json,qualification.py,kinetics.py,tests/test_qualification.py}`, `docs/validation/science_v1/ATOMISTIC_BOUNDARY.md`.

First determine whether an atomic model is actually needed for a decision left unresolved by cheaper observations. Freeze potential/model/data hashes, elements, phases, defects, surfaces/interfaces, electronic/charge/environment assumptions, temperature/time domain, training provenance, and reference uncertainty. A classical potential lacking reactive/electrochemical degrees of freedom cannot qualify repassivation merely by containing Ti/O symbols.

Test stable configurations and mechanism-specific transitions: energy/force directions, unstable paths/barriers, defect/phase ordering, surface/undercoordinated environments, crack/contact mechanism only within supported domain. Use independent reference labels with convergence and holdout families; DFT reference error and experiment disagreement remain explicit. Ensemble agreement with shared training/model bias is a deliberate negative control. No one-shot fine-tuning on a failed holdout followed by reusing that holdout as confirmation.

Kinetics records require barrier, prefactor, model assumptions and uncertainty; distinguish nanosecond MD observations from service durations. As a mathematical sensitivity control, at 300 K, a 0.1 eV barrier difference with identical prefactor changes the rate by `exp(0.1/(k_B*300)) ≈ 48`. This is not a measured Ti reaction rate or a validated Arrhenius model. Reject a lifetime bridge lacking mechanism/rate validation. Do not infer absence of rare events from a short simulation without a quantified detection opportunity.

Acceptance: domain mismatch and shared-bias controls rejected; barriers and time uncertainty exposed; a qualified model supports only its named mechanism; no automatic strength bonus or release evidence upgrade. Expensive calculations require separate resource admission and specialist readiness; GPU/DFT installation is not authorized by a test-plan task.

### T18 — mechanism discrimination and an offline falsification agent

Owner S11/S10 interface consumer after T06/T07/T09 and protocol freeze. Create `research/science_v1/falsification/{hypotheses.json,experiments.json,policy.py,runner.py,tests/test_falsification.py}`, `docs/validation/science_v1/FALSIFICATION.md`.

Start offline with a finite menu of already approved synthetic/data-analysis experiments. A hypothesis record names assumptions, measured predictions, discriminating interventions, falsifiers, applicability, observation uncertainty, parameter budget, and dependencies. Mechanisms may coexist; include explicit mixtures and `none_of_the_supported_models`. Keep parameter complexity/model discrepancy visible so a flexible hypothesis cannot fit every outcome by default.

The challenge generator includes latent material change, instrument drift, preparation artifact, nonidentifiable explanations, shared-bias ensembles, missing mechanism and a null case. Fixed audit measurements are withheld from the chooser; the agent cannot select all of its own evidence. Choose expected discrimination/value of information under current uncertainty and total cost, then compare to fixed DOE and random strategies under the same total acquisition/analysis budget. Synthetic gains are not physical gains.

Test deterministic seeds, cost ledger exhaustion, inaccessible experiment, no informative action, contradictory evidence, priors inconsistent with reality, hypothesis revocation, leakage from sealed truth, failed/no-result acquisitions, and unsupported domain. A correct result may be uncertainty or no model fits. Do not reward fitting speed, number of experiments, or a stronger optimistic prediction.

Acceptance: preregistered challenge outcomes and independent holdout audit; honest unresolved/none-fits cases; complete receipts and replay; no ability to change requirements, scientific thresholds, material constants, physical controls, or external systems. Physical closed-loop work is a separate later authorization, not implicit in this offline implementation.

### T19 — suite admission, capability gates, and independent reconstruction

Integrator S16 after required T00–T07; collect conditional capability results under frozen policy. Read latest COORD, all receipts, existing `.github/workflows/d1-gates.yml`, `version-check.yml`, current marketing smoke workflow, `docs/CI.md`, and S00 release amendment. Create `ops/ci/{science_suite.py,tests/test_science_suite.py}`, `.github/workflows/science-contracts.yml`, optional `science-numerical.yml`, and integrate `assurance/reporting/check_release.py` and `docs/CI.md` through the single owner.

1. Register exact tier inventories and capability-to-evidence requirements. Runtime capability manifest cannot enable an untested feature by omission. A critical path-filter change cannot skip science tests; edits to requirements/schema/solver/evidence/claims trigger all dependent contracts. No matching tests, import error, or missing dependencies returns error/incomplete, never pass.
2. Use checked argv commands with allowlisted cwd/env/output roots, timeouts, and owned-child cleanup. Never execute shell strings from an untrusted receipt or dataset. Add path traversal, symlink escape, oversized output and incomplete upload tests. This is scoped runner integrity, not a new generalized sandbox project.
3. T0 per-PR runs deterministic/evidence/analysis contracts and existing Rust/G1/D1 gates. T1 admitted numerical workflow runs analytic/metamorphic/fresh solver checks. T2 lab pipeline validates signed/hash-bound uploaded records without operating instruments. T3 research runs on explicit capability activation and data budget. Store separate statuses and denominators; a green T0 cannot imply T1/T2/T3 were performed.
4. Required numerical/lab capability unavailable is incomplete. Optional unclaimed branch disabled has a reason and no associated release claim. Exact-head review/CI is required after every merge/rebase; artifact hash equality can justify reuse of an unchanged historical result only with its scope and compatibility, not as a fresh execution receipt.
5. Reconstruct the release dossier in a clean worktree from immutable inputs and policy. Compare candidate/material/mesh/requirements/case IDs across all generated tables, CLI JSON, metrics, and render manifests. Missing V4/G1/lab proof cannot become PASS in marketing. Render finish metadata must never populate structural material properties. Preserve owner art-review/dark-QA/sheath gates separately, including existing unseated/interrupted and directional retention/handling evidence: a favorable scalar sheath calculation cannot fill unperformed directional checks. The renderer's green suite is not science certification.
6. Resolve docs/Cargo versions under S16 only; no version bump per test worker. Final 1.0.0 cannot quietly bypass §19. If required lab evidence is not available, produce an explicitly scoped RC and unresolved gate table, not a final release tag.

Acceptance: independently rebuilt dossier and checks on the final source/policy hashes; dangerous suite/claim mutations fail; all mandatory/activated expected cases have receipts; every missing capability is visible; current merge-train policy respected. No PR/tag/merge/push is performed by the planning task.

## 6. Deployment of worktrees, screens, and validation

Reuse the owned planning worktree for this documentation supplement. Implementation starts only through S00's executor. Create each execution worktree from the reconciled current origin/main, not the historical audit source or planning branch. Preserve historical receipts. T units sharing an S owner are sequential on that owner's branch unless an explicit narrow disjoint scope is recorded. The testing supplement introduces no authority to send prompts to unrelated screens.

Initial permitted disjoint test waves after prerequisites: T01/T03/T07; then T02/T04/T05's S07 portion; then T06/T12. After T06/T07, T08/T09/T17 have disjoint scopes if their research admission gates are satisfied. T05's S08 binding integration waits for S04/S05/S06/S07 completion; T04's S05 and S06 writers are sequential. These are available concurrency groups, not instructions to ignore parent dependencies. Research analysis modules can run in separate worktrees after shared schemas/protocols are frozen; schema edits always return to the schema owner. Maximum three workers, one admitted heavy four-CPU/eight-GiB lane initially. Cheap source/doc work may continue while a heavy owned job runs. Do not infer spare capacity from 128 cores alone; live host load, other jobs, memory and COORD admission govern.

Every shell command issued from the local desktop is prefixed with `rtk`, per global instructions. Remote commands inside `rtk proxy ssh xbabe2 '...'` need not call unavailable remote rtk. The following are templates to execute only after S00 reserves the paths and substitutes a real source SHA. The shell syntax is part of planning validation; it is not a claim these commands ran.

```bash
rtk proxy ssh xbabe2 'git -C /home/ubuntu/jarambit worktree list --porcelain'
rtk proxy ssh xbabe2 'screen -ls'
rtk proxy ssh xbabe2 'git -C /home/ubuntu/jarambit worktree add -b codex/science-v1-s02 /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s02 origin/main'
```

Integrator writes an owned `run-tests.sh` using the current verified environment and runs it through the existing host wrapper `/home/ubuntu/bin/memcap 8G --` with the verified user-bus environment from `WORKTREE_RUNBOOK.md`. Use cgroup/affinity admission from that runbook rather than inventing resource flags. `nice` alone is not a CPU/memory cap. Export `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `CARGO_BUILD_JOBS=4`, `JARAMBIT_MAX_THREADS=4` and a worktree-private `CARGO_TARGET_DIR`. No aggregate project run may exceed current COORD limits (48 threads, cargo jobs <=16, output <5 GB); the smaller packet caps apply initially. Do not start another build if the shared aggregate would exceed them.

```bash
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s02 && screen -dmS jr_v1_s02_tests bash .agent/science-s02/run-tests.sh'
rtk proxy ssh xbabe2 'tail -n 40 /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s02/.agent/science-s02/attempt-001/run.log'
```

The owned launcher must print source/toolchain/image/policy hashes before running, flush a stage marker after each command, trap child failure, and create a terminal receipt even on timeout or resource failure. Do not poll or send keystrokes to another owner's screen. Report meaningful stage completion/failure and unresolved claims, not a stream of unchanged tail output. Stop only owned children on a packet abort; never kill a host or shared node.

Existing baseline commands to preserve, after admission and with private targets/output directories:

```bash
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s02 && python3 -m unittest discover -s fem_solid/tests -v'
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s03 && python3 -m unittest discover -s metrics/tests -t . -v'
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s03 && python3 ops/ci/check_claims.py'
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration && cargo test --release --workspace'
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration && cargo clippy --release -p jarambit -- -A clippy::all -D clippy::disallowed_methods'
```

T1 numerical lane uses the pinned dolfinx environment/image: `python3 fem_solid/tests/verify_analytic.py` and `FEM_SOLID_REGRESS=1 python3 -m unittest discover -s fem_solid/tests -p test_tip_regression.py -v`. These are existing scripts but expensive/dependency-bound, and their actual elapsed time/memory must be measured. Existing regression target SF=1.534 ±0.005 and n_dof=422955 is a historical reproducibility check, not a new convergence or physical-validation threshold. If observable/solver semantics intentionally change, retain old historical check through its adapter and define a reviewed new reference; never overwrite the old expected values without explanation.

Fresh D1 smoke remains the known-negative anchor with owned outputs: build `jarambit`, execute `crescent-d1 --genomes w14c03=docs/d1/wave15_16_collect/wave14_c03_genome.csv --threads 2 --out <fresh-attempt>/d1`, then `ops/ci/d1_smoke.py` and `check_json_strict.py` on that output. Requirement/evaluator changes that affect it stop for reconciliation. Existing render suites continue with their owner's admitted environment; don't restore the old timeout or override #66 during science integration.

Failure interpretation: assertion failure means violated contract; import/tool missing means unavailable execution; timeout/resource failure means infrastructure incomplete; fresh solver failure means absent numerical support; mismatch against a historical result means investigate identity/observable/solver change; physical null result means analyze within its confidence; an unresolved hypothesis means no stronger claim. Retrying infrastructure failure may be appropriate with a new attempt receipt. Retrying to discard unfavorable scientific data is forbidden.

## 7. Receipts, release gates, and handoff

Write `.agent/science-<S-owner>/<attempt>/receipt.json` with `source_sha`, parent source, dirty diff hash (or clean), policy/catalog/oracle hashes, source-input hashes, specimen/lot/history/acquisition IDs when applicable, environment, pinned dependencies, resource admission, exact argv/cwd, stage times, exit/timeout, expected/executed/passed/failed/error/not-run counts, control/mutant results, artifact sizes/hashes, reuse-vs-fresh status, and unresolved claims. Source SHA is not the later receipt commit SHA; state both when handing back. Include raw logs and immutable results, a compact findings table, and no confidential/sensitive environment dump.

Physical data adds chain of custody, preregistration hash/time, randomization/blinding and deviations, calibration/raw files, excluded/missing/censored records, pilot vs confirmation separation, analysis code hash, specimen/lot counts, effects/intervals, reference-truth limits, reviewer and revocation dependency. Signing/review records establish provenance, not scientific validity by themselves. Large raw data resides in approved immutable storage with verified retrieval and budget, not a Git fixture.

Before READY, each worker proves its diff matches the allowed paths, reads latest COORD, reports exact tested source and hand-back commit, all commands/results, killed mutants, implemented case IDs, unresolved/skipped IDs, limitations, resource use and artifact paths. Report changes to hypotheses even when rejected. Append a branch-local CLAIM/RESULT/RELEASE record without modifying live main. The executor alone sequences PRs and integrates shared files.

Release gate ledger must show:

1. Existing D1/G1/RS and theory gates retained; required numerical cases verified with appropriate fresh evidence.
2. All mandatory software test inventory and capability contracts complete; no required skip/ignored case mislabeled as green. Existing unrelated ignored test is listed with its owner/status rather than silently removed.
3. Candidate/genome/native CAD/material/mesh/observable/load/requirements identities agree; no cross-design or cross-tier certificate borrowing.
4. Active material/lab claims meet route/population/observation/uncertainty scope; missing physical proof remains incomplete and blocks final release as policy requires.
5. Any acoustic/witness/history/atomistic/agent claim has its specific qualification; deferred research has no positive feature claim or strength credit.
6. Independently reconstructed exact-head dossier and current CI/review, version reconciliation to 1.0.0, and owner review of amended release policy. A proposal cannot amend policy by itself.

Priority order for execution is T00, then demonstrated software defects T01–T05, benchmark/leakage and material/observation contracts T06–T07, then T19 integration. The first research investment should be T09/T11/T12 together as a bounded coupon study: apparent-state collisions, history-order/clock controls, and observation controls. T08/T10 can support method development where data and registration are adequate. T14 external diagnostics follows reference-truth/observer qualification; T15/T16/T17/T18 advance only if a cheap pilot establishes decision value. Keep independent physical §19 proof validation on its existing path throughout; it is not replaced by exploratory studies.

This sequence makes 1.0 more accurate immediately while allowing the science to falsify its assumptions. It does not pretend that every proposed mechanism occurs, every sensor works, or every model can be made sufficient.
