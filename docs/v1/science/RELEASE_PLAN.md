# Jarambit 1.0 — Evidence-bound evolutionary science

Status: worker-ready release plan; implementation has not started. Study baseline: `97af59cf14299af583b344aeaefb4594d089465a`. Author of this planning supplement: Codex, prepared for Jepson Taylor. Planning date: 2026-10-13, America/Denver.

This supplements `docs/v1/JARAMBIT_V1_ENGINEERING_SPEC.md` and `docs/v1/jarambit_v1_roadmap.json`; it does not silently replace their decisions, completed milestones, or release gates. Read `FINDINGS.md`, `INPUT_COVERAGE.md`, `WORK_PACKETS.json`, and `WORKTREE_RUNBOOK.md` alongside this file. All repository paths below are relative to an isolated worker checkout on xbabe2. The integration root is proposed as `/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration`.

The subsequent ten test proposals are integrated in [tests/TEST_UPGRADE_PLAN.md](tests/TEST_UPGRADE_PLAN.md): twenty T00–T19 acceptance work units, 178 planned challenge groups, mandatory contract checks, and conditional physical/research studies. [tests/TEST_WORK_PACKETS.json](tests/TEST_WORK_PACKETS.json) assigns them to the existing S owners; [tests/CI_GATE_POLICY.json](tests/CI_GATE_POLICY.json) preserves all nineteen original regressions and inherited final-release obligations. A T unit is part of its S owner's work, not permission for another broad writer. The follow-up source comparison uses checked-out main bae2a3d; later origin/main was observed at 7042f19. Historical audit counts remain source97af results. S00 must reconcile current refs before execution.

## 1. Release decision and scope

The major advance should be a system that can establish which evolutionary conclusions survive numerical verification, independent reevaluation, manufacturing variation, and physical comparison. More generations, more objectives, and more detailed pictures do not independently establish greater accuracy.

Target **1.0.0**, with `1.0.0-rc.1` and later RCs for software/science review. Major-version reasons: explicit evidence contracts; requirement-content identities; versioned evaluation and archive semantics; a resumable current search engine; and reproducible experiment interfaces. Keep current `docs/VERSION` unchanged while this is only a planning branch.

Do not call the final release complete by weakening the existing master-plan §19 physical/manufacturing gates. An RC can document outstanding laboratory evidence. Final 1.0.0 requires either satisfying the inherited gates or an explicit owner-approved, recorded amendment to the release scope. Software release eligibility, numerical candidate eligibility, human review, and manufacturing authorization remain separate decisions. None automatically implies another.

### Objective

Make every published quantitative claim traceable to an exact subject, requirement revision, evaluator, observable, uncertainty method, and evidence state. Make scientific comparisons reproducible under equal budgets and independent seeds. Improve search quality only when a frozen experiment demonstrates the benefit; preserve informative negative results.

### Non-goals

- Do not change approved loads, geometric requirements, soft mass policy, or candidate-specific hard mass limits to make results pass.
- Do not invent new weapon, tissue, penetration, or animal-encounter objectives. The project remains a hiking/utility engineering study.
- Do not design a new blade, prescribe strengthening geometry, or prescribe coating deposition recipes in this increment. New representation algorithms are first verified on benign structural fixtures.
- Do not promise a feasible 70 g design, a universal fatigue life, a coating strength multiplier, a 90× solver acceleration, or statistical reliability unsupported by representative evidence.
- Do not contact manufacturers, laboratories, raters, or other external parties; prepare concrete specifications for subsequent owner-directed work.
- Do not migrate to Ray, CUDA, NSGA-III, a GNN, or a new geometry family solely because the old roadmap listed them.
- Do not alter live render/sheath work, drained-host policy, existing screen sessions, historical evidence, or unrelated jobs.

### Assumptions and dependencies

1. xbabe2 `/home/ubuntu/jarambit` is the authoritative operational checkout; GitHub is the source for published history. The frozen study SHA above must be rechecked against current `origin/main` before execution.
2. `COORD.md` is the operational agent standard. Its latest entries supersede older lane allocations. The existing executor owns roadmap PR opening and merge sequencing; workers hand back tested commits. The new user request authorizes this planning lane, not taking over another worker's branch.
3. Wrought stock/machining is the default physical qualification route because the current screening data refer to annealed plate. Additive manufacturing, if selected, receives a separate material/process qualification campaign. No transfer is inferred from the alloy name.
4. Current C.10a B-rep artifacts and legacy/crescent genome artifacts are different subject types. A native CAD subject adapter is required; a fabricated genome identity is forbidden.
5. Rust 1.85.1, Cargo.lock, existing Python environments, and available reference solver images are the starting reproducibility boundary. Record actual versions and image digests; do not install or upgrade shared environments during worker runs.
6. No physical testing was performed for this plan. Material passports, lab protocols, and data-import tests can be implemented now; measured allowables cannot.
7. Full physical qualification depends on representative lots/specimens, calibrated instruments, licensed standards where required, independent review, and owner-arranged facilities. Those lead times are outside code-worker estimates.

### Completion criteria

- All twelve supplied files have hashed provenance and an explicit adopted/modified/deferred disposition. Ten similar reviews are not ten independent scientific validations.
- No invalid, empty, stale, reopened, superseded, mismatched, or incomplete required evidence can produce a current PASS in any registered consumer.
- Known-negative D1 fixtures retain their locked decisions. Existing G1 remains versioned and unchanged; deleting a required observation yields incomplete status.
- The current crescent engine has deterministic checkpoint/resume, complete event/counter accounting, and explicit separation of exploratory, feasible, and certified archives.
- Benchmarks distinguish elapsed time, CPU time, cache hits, failed attempts, and fresh evaluations. Algorithm comparisons use a frozen evaluator and budgets, grouped data splits, independent runs, and preregistered analysis.
- Every final candidate is reevaluated with independent holdout scenarios and the appropriate reference tier; no surrogate or scalar search score grants release approval.
- Manufacturing/material/inspection/handling evidence satisfies its declared scope; unknowns remain visible. Existing §19 final-release gates are reconciled and satisfied or explicitly amended by the owner.
- Final handoff includes exact tested commit, source/input hashes, commands and exit codes, evidence manifests, historical status changes, migration/rollback instructions, and outstanding owner decisions.

### Stop conditions

Stop the affected packet, retain logs, and report a typed blocked dependency if: its write scope overlaps an active claim; required source artifacts or reference environments are unavailable; a known-negative becomes positive without an approved requirement change; an uncertainty policy is undefined near a decision boundary; a model is outside its applicability domain; hash identity changes mid-run; resource admission fails; logging/checkpoint durability fails; or results require unmeasured material data. Independent packets can continue. Never resolve these by expanding numerical tolerances, changing standards labels, dropping failed samples, or editing historical records in place.

## 2. Read-first order and protected zones

Every fresh worker reads this ordered list before touching code:

1. `/home/ubuntu/jarambit/COORD.md` — first hard rules and newest ownership/release-train entries; inspect current status/worktrees/screens.
2. This plan, `WORKTREE_RUNBOOK.md`, and the assigned packet in `WORK_PACKETS.json`.
3. `docs/v1/JARAMBIT_V1_ENGINEERING_SPEC.md`, including its final mass-policy addendum; `docs/v1/jarambit_v1_roadmap.json`; `docs/v1/FEEDBACK_SYNTHESIS.md`.
4. `requirements/RS-karambit-v1.toml`, `requirements/RS-karambit-v2.toml`, `requirements/RS-sheath-runner-v1.toml`; then `designs/switchback/C10a/README.md` and `ops/render/pro/fem_cases.json`.
5. `crates/evidence/src/lib.rs`, `crates/evidence/tests/log.rs`, `crates/crescent/src/record.rs`, `crates/crescent/tests/evidence_lineage.rs`.
6. `crates/crescent/src/qd.rs`, `crates/cli/src/crescent.rs`, `crates/evolve/src/lib.rs`, `crates/evolve/tests/replay.rs`, `crates/monte_carlo/src/lib.rs`.
7. `fem_solid/gci.py`, `gci_report.py`, `convergence.py`, `solve_dolfinx.py`, `run_tip.py`, `fem_solid/tests/`; `crates/crescent/src/fem.rs`; `crates/physics/src/verify.rs` and its fail-closed tests.
8. `crates/cli/src/bench.rs`, `ops/bench/run.py`, `bench/fixed_1k/README.md`, `docs/calibration/t1_t2.md`, `docs/perf/baseline_0.31.1.md`.
9. `ops/ci/check_claims.py`, `rs_verdicts.py`, generators, `.github/workflows/`, `ops/render/pro/design_manifest.py`; `docs/sheath/SHEATH_V1_PLAN.md`.
10. Packet-specific sources and existing tests. Validate paths with `rg --files`; proposed paths in this plan may not yet exist.

Protected zones: `/home/ubuntu/jarambit` main checkout; all existing `.agent/worktrees/*`; `/home/ubuntu/jarambit_render*`; `/home/ubuntu/hiking-karambit*`; existing `out/*`, published `designs/*/cad`, drawings, `evidence/wave27`, existing `evidence/fem_solid`, `bench/fixed_1k/genomes.csv`, its SHA256SUMS, and reference-style constants. Inspect these read-only. A historical correction creates a new record and supersession/review event. Generated README/STATUS/whitepaper blocks and figure/media manifests are edited through their generators, by the integration owner only. A path beginning `assurance/`, `experiments/science_v1/`, `materials/`, `evidence/qualification/`, or `crates/core/` below is proposed until its packet creates it.

Global conflict paths: `Cargo.toml`, `Cargo.lock`, `docs/VERSION`, `README.md`, `STATUS.md`, `docs/WHITEPAPER.md`, existing roadmap files, `COORD.md`, `crates/cli/src/main.rs`, and workflow YAML. One integrator owns them. No worker edits those concurrently. Render consumer changes wait for the existing render lane to release its claim and reconcile #64/#65 work; do not cherry-pick from a dirty render checkout.

## 3. Required architecture contracts

Extend the existing evidence crate. Do not introduce a competing truth engine or copy GCI arithmetic into a second wrapper. Keep existing event logs readable; add explicit schema-version adapters. Byte hashes prove identity, not physical applicability.

### Identity and observations

Create `crates/evidence/src/identity.rs`, `assurance.rs`, and `assurance/schemas/`. A qualified observation binds:

```rust
pub struct EvidenceIdentity {
    pub schema_version: u32,
    pub subject: SubjectRef,           // exact genome bits OR native CAD hash OR specimen ID
    pub requirements: ContentRef,      // ID, revision, full SHA-256; inherited hashes too
    pub material_state: StateRef,      // identified state or explicit unknown
    pub model: ContentRef,
    pub evaluator: ContentRef,         // source/build/dependency/config identities
    pub observable: ObservableSpec,    // quantity, units, frame, region, recovery method
    pub dependencies: Vec<ContentRef>,
}
pub struct EvidenceState {
    pub execution: ExecutionState,
    pub numerical: NumericalState,
    pub validation: ValidationState,
    pub review: ReviewState,
}
```

These are design sketches, not compile-ready definitions. Packet S01 supplies exact enums/schema/tests. Numerical validity, physical validation, review, and requirement verdict are orthogonal. `Outcome::Incomplete` remains the compatibility mapping for missing, invalid, unresolved, or inapplicable required evidence, with reason codes retained. An invalid calculation is not a measured physical failure. A scoped FAIL is different from an invalid input.

Finite numeric construction must reject booleans on Python ingest, NaN/Infinity, overflow in reductions, ambiguous units, duplicate keys/IDs, unknown enum values, and missing mandatory metadata. Typed not-applicable requires a reason and a criterion that permits it. Do not let `not_applicable` bypass a mandatory gate. Hash raw bytes for preservation and a documented canonical representation for semantic identity; publish the canonicalization version. Store unknown provenance as unknown, never guessed.

Uncertainty is a list of components with kind, method, domain, covariance/dependence assumptions, and coverage interpretation: discretization estimate, iterative error, measurement uncertainty, sampling uncertainty, input variability, model discrepancy. GCI is not automatically a confidence interval. Do not automatically root-sum-square correlated components or interpret non-overlapping error bars as a universal significance test.

### Claim resolution and revocation

Create `ClaimRecord`, `ExpectedInventory`, and append-only `ReviewEvent` with `supersedes`/`reopens` links. Resolve dependencies as a graph with cycle, duplicate, missing-artifact, content-mismatch, and applicability checks. A numerical value may remain unchanged while its status becomes unresolved. An aggregate PASS requires a nonempty expected set and every required criterion observed, applicable, valid, and met. Optional display-only values do not block unrelated claims; record-only criteria never become hard gates by accident.

```text
resolve_claim(claim, expected_inventory, registry):
  validate identities, dependency closure, required coverage, review state
  retain original observations and invalidity reasons
  evaluate only applicable criteria using unrounded values
  emit scoped verdict + publication eligibility + separate release authorization
```

W84 is the permanent revocation fixture: reopening C.10a V3 must withdraw all dependent current converged-PASS claims without discarding its historical solver number. A structured correction replaces the V4 hard-coded comparison exception. Cosmetic finish parameters cannot enter structural material fields. Every registered document, plate, drawing caption, film manifest, and release table consumes the same resolved claim state. A metadata change must invalidate the relevant artifact cache key.

### Requirement policy

Requirements content, inheritance, and hard/soft/record-only roles are immutable within an experiment. Create a candidate registry and an explicit crosswalk from C.9/C.10 study criteria to RS criteria: same name is not sufficient; load, fixture, material, temperature/knockdown, geometry state, observable, and threshold must match. Otherwise mark the relationship unmapped and reevaluate. Preserve C.10a's documented study-specific `<70 g` limit separately from RS-v2's soft 80/70 g search targets. Do not silently create RS-v3; a semantic change requires a recorded owner decision and new identity.

## 4. Implementation phases and ordered packets

Each packet below has a separate branch/worktree, tests, and receipt. Machine-readable dependencies/write scopes appear in `WORK_PACKETS.json`. Wave boundaries and shared-file integration are enforced in the runbook.

### Phase 0 — Freeze truth and settle interfaces

**S00 — Release reconciliation and campaign freeze.** Owner: integrator. Read all files listed above, then prepare `docs/v1/science/ROADMAP_AMENDMENT.md`, `assurance/policies/release-v1.json`, and `experiments/science_v1/baseline_manifest.json`. Classify each old roadmap item as implemented, partial, missing, superseded, or exploratory using actual source/tests. Never infer completion from a PR title or minor version. Record current live claims, exact origin/main, the #65 dependency, and resource leases. Pin the baseline engine, source/lock/toolchain/requirements/seed hashes, numerical settings, objective definitions, and descriptor IDs. Freeze interfaces for S01/S02/S04/S05 before dispatch.

Amendment proposals needing explicit owner disposition: final 1.0 gate expectations; any retirement of previous numerical speed/algorithm/cost/aesthetic targets; any new hard mass policy; and physical manufacturing route. These decisions do not block pure software-integrity fixes. Old 404-hour estimate is historical, not a current commitment.

Exit: no conflicting claims, source inventory complete, current/historical candidate distinction explicit, and amendment decisions represented as pending rather than implicitly approved.

### Phase 1 — Remove false scientific passes

**S01 — Typed identity and assurance core.** Own `crates/evidence/src/{lib,identity,assurance}.rs`, `crates/evidence/tests/assurance_contract.rs`, `assurance/schemas/*`, and `assurance/policies/evidence-v1.json`. Extend `RunManifest` with content-bound source/build/lock/config/evaluator/requirements/subject identities, separating deterministic scientific identity from host/threads/runtime metadata. Implement checked observation construction, state and dependency resolver, strict ingest, and v1-read/v2-write adapters. Retain existing `Obs`, `Outcome`, JEV1 read behavior and crash tests. Reject unknown or insufficient legacy provenance for current qualification while allowing historical display. Test identity mutation, duplicate input, cycles, reopened dependencies, failed serialization, empty expected coverage, and schema round trips. Exit: negative fixtures cannot manufacture PASS; existing event/log tests pass.

**S02 — GCI and fresh-computation contract.** Own `fem_solid/gci.py`, `gci_report.py`, `convergence.py`, `run_tip.py`, their tests, and new `assurance/numerical/gci_inventory.json`. Keep raw historical evidence read-only. Return structured classifications: admissible estimate, unresolved oscillation, nonpositive order/nonconvergence, stagnation/roundoff, invalid input, insufficient evidence. Validate finite scalars, positive safety factor, `r>1`, refinement metadata, compatible observable/region definitions, and normalization. A valid fitted order is necessary; a three-point fit alone does not prove an asymptotic regime. Separate fit admissibility from additional asymptotic evidence, using a fourth level or an independently justified verification history when required.

Use `math.expm1(p*math.log(r))` for the extrapolation denominator where appropriate and tolerance checks tied to output precision; do not clip/absolute-value negative GCI into a pass. A zero/near-zero reference permits an explicitly declared absolute-error method or unresolved status. Identical fine levels remain unresolved unless independent exactness is established. Oscillatory heuristics may be displayed but cannot satisfy the ordinary GCI gate. Validate that SF interval denominators are meaningful; do not publish negative/infinite bands.

Refactor reporter into pure `build_report(records, expected)` plus guarded CLI. Missing/extra/duplicate records and empty inventories are nonpassing. Replace filename-existence reuse in `convergence.level()` with a complete input/config/code/image/observable hash and attempt-specific atomic outputs. Require successful fresh execution, full outputs and hashes; failed subprocesses cannot inherit older files. Make strict JSON serialization reject nonfinite values. Import every symbolic regression from `docs/v1/science/inputs/NUMERICAL_AND_EVIDENCE_REGRESSION_CASES.json`, including positive controls and near-degenerate cases. Exit: all invalid supplied fixtures fail closed; historical reclassification report identifies oscillatory `w271b_11772` without claiming its physical design fails.

**S03 — Report/claim integrity.** Own `ops/ci/check_claims.py`, `rs_verdicts.py`, generator adapters, `ops/ci/tests/test_claim_integrity.py`, `test_requirement_identity.py`, and `assurance/reporting/*`. Replace substring verdict comparison with exact canonical comparison, keeping surrounding editorial text outside the generated block. Reject nonfinite/boolean numerical values in verdict input. Require expected coverage before thresholding; missing promotion evidence remains incomplete. Add candidate registry and explicit study crosswalk inputs. Generate root current-candidate status and historical scope text from that registry. Plan integration-only regeneration of README/STATUS/WHITEPAPER/TECHNOLOGY_MAP/fem docs; no worker edits generated outputs independently. Add mutation tests for wrong candidate, changed requirement contents, changed hard/soft role, stale headings, appended contradictory PASS, missing physical evidence, and reopened W84 status. Exit: registered prose consumers agree with resolved evidence, including known negatives.

**S04 — Monte Carlo correctness and honest probability semantics.** Own `crates/monte_carlo/src/lib.rs`, new `stats.rs`/`scenario.rs`, MC tests, and `crates/evolve/src/lib.rs` MC call sites. Keep CLI integration with the integrator. Introduce `try_run_cols -> Result<SampleSummary<K>, SampleError>`; compatibility wrappers must not silently return favorable defaults. Reject `n=0`, nonfinite samples and aggregates, missing worker results, and invalid configuration. Record attempted/completed/valid/invalid/model-failed/numerically-failed counts, sample IDs, error reasons, and declared quantile convention. Preserve deterministic `(seed, sample_index)` streams and thread stability. Use overflow-resistant mean reduction and still reject impossible/unrepresentable aggregates.

Joint requirement outcomes must be computed from each original row before marginal sorting. Keep representative-population simulations, epistemic scenario sets, and deliberately weighted stress tests distinct. Marginal p05 values cannot be assembled into a fictional simultaneous specimen. Separate scenario streams for search, calibration, and final audit; common random numbers may reduce comparison noise only for paired experiments, and independent final audit streams remain mandatory. Introduce correlated/hierarchical lot uncertainty only with sourced parameters and validity checks; an independence assumption stays explicit if data are absent.

Retire legacy `CutMedia` lookups as already requested in old PR-0.32.3; preserve historical decode/read adapters with a model-retired label. Do not replace them with unvalidated physical “impact” predictions. Add generic utility scenario IDs and keep discovery scenarios distinct from prevalence estimates. Tests: NaN/±Inf at every column location, finite-sum overflow, zero count, worker panic/error, shuffle invariance, correlated rows with known joint truth, thread counts 1/2/4, and bit-stable valid baseline streams. Exit: no invalid reduction grants statistical credit and every probability statement names its distribution/event/sample unit/confidence interpretation.

### Phase 2 — Make evolutionary science reproducible

**S05 — Search and archive semantics.** Own `crates/crescent/src/qd.rs`, `record.rs`, `tests/search_contract.rs`, and `experiments/science_v1/contracts/*`. Unify explicit precheck, search-feasible, reference-certified, and release-eligible predicates; avoid vague `legal` reuse. Keep exploratory infeasible individuals if useful, in a separate archive. Only fully observed search-feasible records enter the feasible QD archive; certified archives require reference evidence. Existing RS-v1 search scope remains named until an approved evaluator policy activates another scope. Search feasibility is not RS-v2 promotion.

Replace context-dependent stored `fit` comparison with `archive_quality()` excluding novelty and migration/population context. Novelty stays an exploration signal with descriptor/context ID. Define stable tie-breaking (quality, unique phenotype hash, candidate ID), finite descriptor checks, duplicate-genome/phenotype accounting, fixed scaling, clipping/out-of-range policy, and versioned QD cells. Retain old descriptor versions for replay. Fitness and phenotype quality use full precision; rounded `RecJson` is presentation output only. Confirm every hard constraint is tested independently, exploratory failures cannot occupy feasible/certified cells, and novelty-context changes alone cannot replace an elite. Detect `pop=0`, empty seed sets, k=0 novelty, migrant bounds, all-infeasible populations, and nonfinite evaluator output before selection. Exit: archive transitions and counts derive from durable events; property fixtures expose the old legal/feasible mismatch and verify the new policy.

**S06 — Current-engine checkpoint and durable logging.** Starts after S05; same qd write scope means no concurrent editing. Own `crates/crescent/src/checkpoint.rs`, `qd.rs`, evidence-lineage/checkpoint tests; request CLI hookup from integrator. Crescent is the active engine and currently has no checkpoint implementation equivalent to legacy replay. Save RNG streams, next candidate/event IDs, generation barrier, islands, archive cells/quality, novelty memory, descriptors, full-precision observations, scientific manifest identity, and counters. Preserve IEEE-754 bits where exact replay is required. Validate body checksum and metadata, not merely a stored manifest string.

Use temporary-file write, flush/fsync, atomic rename, and directory fsync where supported. Define event-log/checkpoint recovery ordering and last durable event sequence. Avoid duplicates after resume; attempt events can be retried, accepted observations must be idempotent. A changed evaluator/requirements/seed/operator/descriptor/config refuses resume; explicit fork records its parent and reevaluates stale observations. A runtime thread change is permitted only where demonstrated trajectory-invariant. Distinguish same-host bitwise replay from cross-hardware numerical equivalence. Qualification runs cannot silently disable logging; exploratory runs may continue only with an explicit non-publishable state.

Tests: stops at generations 3/7/12 for three seeds, resume across 1/4 workers, killed writes/torn tails, disk-full/log errors, corrupt checksum, incompatible manifest, stale source, and deliberate fork. Retain legacy replay suite. Exit: uninterrupted and resumed scientific state/event accounting match; durability failure cannot produce a publishable campaign.

**S07 — Observable semantics and elementary verification.** Own `crates/physics/src/verify.rs`, new invariance tests, `fem_solid/solve_dolfinx.py`, generic solid tests, and `assurance/numerical/observable_catalog.json`. Wait for S02 before editing shared solid sources. Correct DG interpolation vs L2 projection metadata without changing values merely to match prose. Define quadrature, nodal averaging, discontinuous interpolation, maxima/region masks, tensor frames, units and recovery order. Test constant, varying and discontinuous tensor fields; `vm(mean(tensor))` is different from `mean(vm(tensor))`.

Run generic beam/plate/coupon fixtures for load scaling, superposition, rigid translations/rotations (including loads/supports/material axes), consistent unit conversion, node/element permutation, reaction force/moment balance, strain-energy/external-work relation under stated assumptions, degenerate/inverted/disconnected elements, missing boundary tags, insufficient constraints, and supported MPI partition changes. Inspect existing rotation/theory coverage first; do not add duplicate tests. Tolerances are benchmark-specific and preregistered. Measure iterative residual separately from discretization error. Stress singularities need a predeclared finite observable/region or unresolved peak status; no smoothing to make a hotspot pass. Exit: independent invariants verified and invalid problems return diagnostics.

**S08 — Evaluation-tier bindings and native CAD adapter.** Integrator-owned integration of `crates/crescent/src/fem.rs`, `crates/cli/src/bench.rs`, `crates/cli/src/crescent.rs`, new `assurance/adapters/*`, and certified-evidence tests. `solid_tip_sf()` must require correct genome/CAD, requirements, material, load/mesh/extraction identities, admissible convergence, and current review state. Finite SF alone is insufficient. Preserve the existing exact-genome binder.

Return a `CertifiedEvaluation` whose per-case observations reference their actual governing mesh and field. Current `certify()` takes minima across two meshes but returns first-mesh fields and second-mesh counts; attach the right source to each scalar and visualization rather than pretending one mesh owns every value. Add per-case refinement agreement/ambiguity status and identity-preserving cache keys. Tag the calibration tiers precisely: current documentation's T2 is fine **plate certification**, while other roadmap text uses T2 for a **solid** solver. Adopt names such as `plate.search.v1`, `plate.cert.v1`, `solid.reference.v1` and retain aliases for historical records.

Create a native-CAD subject adapter for C.10a and imported study evidence. Inventory raw solver files/scripts/environments from external stores, export content-addressed manifests and a replay recipe, and mark missing dependencies incomplete. Do not alter external stores or claim source available merely because summarized JSON is committed. Exit: every scalar/field/evidence association is checked; no automatic transfer between B-rep studies and genomes or between plate/solid tiers.

**S09 — Benchmark and experiment harness.** Own `ops/bench/run.py`, new `ops/bench/science.py`, `experiments/science_v1/{protocol,baselines,splits,seeds}.json`, tests and `docs/results/science_v1/*`. S08 owns Rust bench edits; serialize or hand back a narrow interface request. Preserve fixed_1k byte-for-byte, and add a second declared stratified corpus including failures, near-boundary cases, fresh families, and benign generality fixtures. Mark the existing 40-of-80 calibration selection explicitly; record exclusions and never represent it as an unbiased population sample.

Current “core_s” is per-design elapsed time summed across threads. Measure process/thread CPU-time separately and report wall, CPU-s, peak RSS per isolated subprocess, queue/compile/mesh/assembly/factorization/solve/postprocess times, attempts, valid results, failures, cache hits, unique phenotypes and fresh reference solves. Replace rounded scalar-sum checksum with candidate-keyed hashes or per-observable comparisons. Record requested vs actual count/threads and hardware/affinity/lease. Reject missing records or changed success masks even if sums agree. Keep the current solver-parity policy until an independently justified amendment; never loosen it just to switch skyline to faer.

Scientific experiment design:

1. Freeze evaluator/requirements/scenario/metric/descriptor identities, initial seed populations, normalization and HV reference point before runs. Separate tuning, calibration, algorithm comparison, and final holdout datasets.
2. Compare current crescent GA, random/LHS baseline, constrained NSGA-II, and a fixed-quality MAP-Elites baseline on the **same** representation and evaluation budget. Do not compare legacy 20/22-gene NSGA-II against 128-gene crescent and attribute representation differences to algorithm quality.
3. Use benign analytical/MOO fixtures first (DTLZ/ZDT and constrained fixtures), then the frozen engineering evaluator. NSGA-III/CVT-MAP-Elites/CMA-ES are ablation candidates, not mandatory replacements.
4. Pilot 3 seeds × 2,000 attempts to measure variance/cost. Plan 10 or more independent run seeds for the main comparison, with 10,000 fresh reference-search evaluations per arm as an initial budget; fix the final sample size/budget after a preregistered pilot analysis. Population members and generations within one run are not independent replicates.
5. Run primary matched evaluation-budget comparisons and separate matched CPU/wall-budget comparisons. Count random audits, local refinement, retries, failed solves and surrogate-label generation; report training/tuning costs separately and lifetime compute too.
6. Report certified feasible yield, time/evaluations to first feasible target, feasible HV/IGD+ where reference sets exist, QD coverage/quality with fixed cells, unique phenotype yield, failure/invalid rate, and rank reversals across tiers. Plot anytime/ECDF results; not best-of-wave anecdotes.
7. Use paired seeds/initial conditions where meaningful, run-level uncertainty intervals and effect sizes, preregistered comparisons and multiplicity policy. Hypervolume zero/baseline-zero, differing archive grids, censored unsuccessful runs, and unmatched reference points require explicit handling. An arbitrary HV ratio or p-value alone is insufficient.
8. Finalist reevaluation uses independent seeds/scenario sets and reference tiers, including diverse archive samples and low-ranked/random controls to detect selection bias and surrogate blind spots. Repeatedly reused holdouts become development data and need a new final audit set.

Harness/fixture exit: one-command reconstruction of tables from immutable receipts. Main shared-evaluator comparison runs wait for S10 algorithm adapters and an exact integrated head; S09 harness code and S10 Rust adapters can be built concurrently because their write scopes are disjoint. Experiment exit: enough evidence to keep, replace, or reject each tested algorithm. The old “1.3× HV” is a hypothesis, not a result workers may force. A well-supported negative algorithm result does not itself disqualify the evidence infrastructure; inherited final-release targets still need owner reconciliation.

### Phase 3 — Learn only inside demonstrated applicability

**S10 — Minimal part-agnostic interfaces, algorithm adapters, and capability cards.** Own proposed `crates/core/{Cargo.toml,src/*}`, `crates/core/tests/*`, `docs/v1/science/capabilities/*`; workspace registration is integrator-owned. Keep evidence crate as a dependency; do not move/rewrite it. Define `SubjectAdapter`, `Evaluator`, `RequirementPolicy`, `DescriptorSpec` and `EvaluationBudget` with explicit error/state types. Adapt existing crescent behind a thin integration wrapper after tests pass; preserve decisions. Implement generic random/LHS, constrained NSGA-II and fixed-quality MAP-Elites adapters in `crates/core/src/search/{random,nsga2,map_elites}.rs` on the same evaluator, representation, initial population and budget interface. Reuse verified dominance/crowding behavior from legacy code through a generic implementation, without importing its distinct genome or evaluator. Define `dominates`, `nondominated_sort`, `crowding`, `select_survivors`, `archive_insert` and deterministic tie rules; test known fronts, independently expected crowding extremes, constraints, budget exhaustion, ties and invalid values. Optional NSGA-III/CVT/CMA-ES are separate experiment revisions after these baselines, with fresh prerequisite proofs rather than a combined untested rewrite.

Validate generality on a benign bracket/coupon adapter. Native CAD remains a separate input representation. Inventory current representation reachability, quantization, topology, export validity, repair bias, and unrepresentable requirements. Do not infer impossible search-space feasibility from a finite unsuccessful campaign, nor guaranteed connectivity from a coarse raster alone. New geometry representations and topology-optimization operators require separate owner-scoped packets after the core contract is proven. Exit: no part-specific imports in core, equivalent baseline decisions through the adapter, generic algorithm fixture correctness, and S09 comparison adapters ready.

**S11 — Multi-fidelity surrogate and experiment selection.** Own `surrogate/science_v1/*`, data/model cards, split/audit tests, `experiments/science_v1/surrogate_protocol.json`. Depends on S07–S10 evidence and harness. Start with simple calibrated regressors/GP or tree baselines; add a GNN only when independent comparison justifies complexity. Split by ancestry/root seed, near-duplicate phenotype, family, lot and campaign time; retain separate calibration and audit sets. Prevent descendant/mesh-resolution leakage. Track false-feasible classifications and threshold calibration, not only MAPE; values near zero invalidate naive percentage metrics.

Predictions include uncertainty and OOD flags; insufficient support routes to the reference evaluator. Surrogate output cannot issue a qualified PASS. Use a preregistered exploration/reference audit allocation, initially at least 10% random/stratified audit with its cost charged to budget, and audit rejected proposals too. Adapt this rate only through logged experiment revisions. Conformal intervals require justified calibration/test assumptions; adaptive optimizer queries and new geometry families do not inherit an exchangeability guarantee. Report coverage with sampling uncertainty and by relevant groups, not only a convenient global 90% average. Freeze model snapshots for qualification comparisons.

Train/validate fidelity discrepancies by case and geometry domain; current twist residual 10.8% fails the project's 7% bar and cannot be hidden in a universal factor. An uncertainty reduction scheduler may choose the next generic coupon measurement/reference evaluation by expected information gain or decision relevance, but recommendations remain hypotheses until measured. Exit: surrogate improves reference-verified utility per compute on held-out runs without increased false confidence; otherwise retain reference-only mode.

**S12 — Performance, caching and resilient workers.** Own proposed `ops/science_workers/*`, `crates/core/src/cache.rs`, `fem_solid/perf/*`, perf tests and receipts. Wait for S10/S11 scope releases. Profile first; preserve the validated CPU reference. Factorization reuse is permitted only for identical operator/material/mesh/BC matrices; load-only changes can share multiple RHS. Parallelize across candidates under resource admission. A content key includes phenotype/genome representation, evaluator source/config/dependencies, mesh, material/load/observable identities; derived verdict caching also includes requirements/review dependencies. Separate raw-solve reuse from reevaluation of changed requirements. No cache entry can bypass reopened review or be accepted from a failed attempt.

Use local workers and file/SQLite job contracts before adding a distributed framework. Add Ray/MPI/GPU only if measured bottlenecks and fault needs justify them. GPU/mixed precision stays optional until per-case parity, residual, error-budget and decision-equivalence tests pass; speed cannot consume an unacknowledged safety margin. Test worker loss/retry, duplicated completion, partial artifacts, stale leases, out-of-memory, disk-full, dependency change, and canceled job. Measure actual peak memory, matrix/preconditioner size and end-to-end times; do not derive stream concurrency from matrix storage alone. Exit: equal scientific results, reliable recovery, bounded resources, and measured speed gain. Old 15-second GPU/50k-hour targets stay unproven hypotheses until benchmarked.

### Phase 4 — Establish physical truth and material applicability

These software packets can progress while owner-arranged experiments are pending. They do not fabricate measurements.

**S13 — Material/measurement passport and lab pipeline.** Own `materials/states/*`, `assurance/laboratory/*`, `assurance/schemas/{material_state,specimen,test_plan}.schema.json`, laboratory tests, and `docs/validation/science_v1/PROTOCOL.md`. Coordinate schema ownership with S01; schema extensions start only after S01 release. Identify grade/product form/lot/orientation/process/thermal and finishing histories/coating batch/exposure state, with property source classes measured/supplier minimum/literature typical/fitted/assumed. Material-state IDs change when relevant history changes. Unknowns block process-specific validation, not historical display.

Define raw immutable data intake, calibration IDs, method/edition/applicability/deviations, specimen/batch/lot independence, units/timestamps/channel identity, registration transforms and uncertainty, clipping/truncation/exclusions, operator notes and reduction version. Test duplicate specimens, reused measurements, swapped channels/units, missing calibration, non-monotonic timestamps, corrupted exports, invalid method conditions, forged physical evidence from a simulation, and unsupported property transfer. Predictions and analysis criteria must be frozen before blind observations are unsealed. Validation locations use the same sensor averaging region, not a convenient numerical peak. Measure fixture compliance/alignment independently. Report numerical, measurement, input and model-discrepancy uncertainty separately.

Wrought qualification uses representative process witnesses plus untreated controls; additive qualification, if chosen, adds build/feedstock/powder history/orientation/defect/surface/postprocess identities and independent evidence. Neither is approved by alloy name. Existing fatigue remains screening-only until applicable fatigue initiation/growth/fracture evidence exists; preserve runouts as right-censored data and invalid/conditional toughness status. Do not invent an infinite endurance limit or interpret the empirical 99% correction as product survival probability. The supplied 5% stiffness/10% strain suggestions are pilot planning values, not universal gates; set decision-specific error budgets before data collection.

Exit: synthetic laboratory imports fail closed, raw-to-report reduction is reproducible, calibration/validation sets are disjoint, and actual received data have an explicit tested domain. Three coupons from the old roadmap are a pilot, not a high-reliability demonstration.

**S14 — Geometry, inspection, surfaces and protective handling.** Own new `assurance/qualification/*`, `docs/validation/science_v1/{INSPECTION,SURFACES,HANDLING}.md`, qualification tests and new `evidence/qualification/*`. Existing sheath/CAD source is read-only unless its owner provides a separate scoped handoff. Define CAD/mesh/physical-object identities and local geometry comparison; volume/mass agreement cannot replace local/topological verification. Track registration uncertainty and remesh mapping. Element IDs are not permanent physical surface IDs.

Prepare blinded inspection-capability studies with independently characterized reference indications; record false negatives, false positives, operator/settings/surface effects and coverage. Resolution/voxel size alone is not probability of detection. “No indication within demonstrated capability” must not become “defect-free.” Finished mass records distinguish CAD estimate/density assumption, measured bare/finished part, and carried assembly; bind the included configuration and uncertainty to the applicable requirement. Conversion coatings must not double-count converted substrate plus an entirely added film.

Surface qualification uses non-sharp, identified coupons; untreated, sham/process-only, and coated groups; independent lots/batches, randomized/blinded order; fresh/aged/worn/combined conditions; and both abrasion→exposure and exposure→abrasion where relevant. Predeclare functional benefit and unacceptable degradation separately. Retain adverse results, delamination/debris, substrate changes, chemistry/thickness/topography/continuity and method uncertainty. A favorable hardness/color/corrosion observation gives no unrelated bulk-strength credit. Check method scope: conventional ASTM C1624 scratch testing is not directly appropriate below 0.1 μm and does not measure intrinsic interfacial bond energy. Do not convert salt-fog hours to field years without independent applicable correlation.

Protective-system assessment uses inert replicas for human handling and guarded fixtures/surrogates for hazardous states. Cover false seating/interrupted insertion, contamination and drainage, retention/mounting after aging, carry damage/concealed exposure, snagging/entrapment, burrs/fragments/finish shedding, and recognizable retirement conditions. A ring SF, retention force, or elastic contact result cannot certify injury prevention or puncture resistance. Record every unresolved endpoint separately and preserve the existing sheath plan's incomplete states.

Chemistry research stays a non-gating research track: characterized coupon → specific hypothesis → validated atomistic/continuum method → held-out measurable observable → bounded effective description. Potential element coverage, a nanometer mesh, or an attractive trajectory is insufficient validation. Distinguish repassivation, barrier recovery, film cohesion and substrate structural repair. No research output populates production strength fields without applicable independent measurements. Exit: each claimed endpoint has matched evidence; lack of support stays visible.

### Phase 5 — Integrate consumers, prove reproducibility, release

**S15 — Render/figure consumer integration.** Owner: existing render lane after explicit scope release. Own only `ops/render/pro/design_manifest.py`, `fem_cases.json` metadata migration, corresponding tests, and common claim-reader adapters. Coordinate with S03 and integrator. Missing certification becomes unknown; no `of record` default. Expected gate completeness is validated independently of README parsing, and V4 corrections use superseding evidence instead of an exception. Use resolved claim state in captions, badges, raw-field overlays and manifests. Maintain signature/mark/raw-grind/resource/host-drain invariants already enforced by render work. Regression: delete V3/V6/V7 certification, delete a mandatory gate, reopen W84, change source/units/field method, replace camera/finish, stale cached manifest. No mutation grants scientific credit. This packet does not rerun a film farm merely to change science metadata. Exit: all registered media consumers reflect the same evidence decision; artifact cache identities include relevant status.

**S16 — Independent reconstruction and major release.** Integrator plus independent reviewer. Run the complete relevant gates on the exact integrated head, then reconstruct a small campaign and its report from an empty output/cache directory. Reproduce legacy checkpoint tests and current-engine restart tests; recompute generic reference fixtures rather than only parsing committed JSON. Archive historical claim-status diff, model/requirement migrations, per-packet receipts, unresolved findings and reviewer decisions. Reconcile old §19 criteria and new assurance criteria explicitly. A scientifically negative campaign is published as such; finite searches do not prove general infeasibility.

Version work belongs here: synchronize intentional package/release versions through workspace metadata, `docs/VERSION`, WHITEPAPER header, RELEASES, generated STATUS and tag checks; review any crates intentionally using independent versions. Current crates/workspace say 0.1.0 while scientific docs say 0.31.0; do not silently confuse either with 1.0.0. Test prerelease as well as final semver tags. Publish migrations for schema/log/checkpoint/descriptor/objective IDs. G1 stays frozen; any new reporting metric is separate and cannot repair a failed gate.

RC gate: verified software/evidence/scientific experiment interfaces, truthful outstanding physical evidence, exact-head review and green required CI. Final gate: inherited physical/manufacturing/generalization/aesthetic requirements satisfied or explicitly amended by the owner, all required evidence current, review and authorization recorded. The executor opens/sequences one PR at a time. Workers do not merge, tag or manufacture approval. Exit: signed release manifest and replay bundle, plus explicit deployment/manufacturing state.

## 5. Validation commands and required artifacts

Commands are invoked through local `rtk proxy ssh xbabe2 '...'` as documented in the runbook; xbabe2 has no `rtk` executable. Every heavy command runs inside its own admitted cgroup with private target/output paths. Set `CARGO_BUILD_JOBS=4` initially (never above repo cap 16), `JARAMBIT_MAX_THREADS=4`, native math pools 1, nice 19, and CPU-only. Resource admission can expand a claimed lane later; 48 is a whole-host project cap, not a per-worker entitlement.

Existing gates:

```bash
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && cargo test --release --locked --workspace'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && cargo clippy --release --locked -p jarambit -- -A clippy::all -D clippy::disallowed_methods'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && python3 -m unittest discover -s fem_solid/tests -v'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && python3 -m unittest discover -s metrics/tests -t . -v'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && python3 -m unittest discover -s ops/ci/tests -v'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && python3 ops/ci/check_claims.py'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && python3 ops/ci/gen_readme.py --check'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && python3 ops/ci/gen_status.py --check'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && python3 ops/ci/gen_whitepaper.py --check'
rtk proxy ssh xbabe2 'cd "$SCIENTIFIC_WORKTREE" && python3 ops/ci/version_check.py'
```

`SCIENTIFIC_WORKTREE` must be supplied inside the remote environment; these are command shapes, not ready-to-run commands with an unset variable. The runbook gives concrete checkout paths and a launcher that records resolved argv/environment. Do not run a naked command outside that launcher for heavy work.

Known-negative fresh D1 check:

```bash
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration && D1_PLATES=1 "$CARGO_TARGET_DIR/release/jarambit" crescent-d1 --genomes w14c03=docs/d1/wave15_16_collect/wave14_c03_genome.csv --threads 2 --out .agent/science-checks/d1'
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration && python3 ops/ci/d1_smoke.py .agent/science-checks/d1'
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration && python3 ops/ci/check_json_strict.py .agent/science-checks/d1'
```

Proposed gates created by packets (not currently available): `cargo test --release --locked -p jarambit-evidence --test assurance_contract`; `cargo test --release --locked -p jarambit-crescent --test search_contract`; `cargo test --release --locked -p jarambit-crescent --test checkpoint_replay`; `python3 -m unittest discover -s assurance/tests -v`; `python3 ops/bench/science.py --protocol experiments/science_v1/protocol.json --out <fresh-run-dir>`; `python3 assurance/reporting/check_release.py --manifest <release.json> --strict`. Do not claim these pass before implementation.

Fresh expensive reference recomputation is a separate tier. Existing `FEM_SOLID_REGRESS=1 python3 -m unittest discover -s fem_solid/tests -v` needs the pinned solid environment, roughly 25 minutes and an admitted CPU/memory budget. DOLFINx generic verification follows `fem_solid/README.md`/Dockerfile and pins image digest and math libraries; no runtime opportunistic dependency install. Log actual solver execution, not only record parsing. Keep unavailability/skips visible; required release cases cannot be hidden in a green skipped suite.

Render adapter changes additionally require `/home/ubuntu/jarambit_render/venv-cad/bin/python -m pytest -q ops/render/marketing/tests ops/render/pro/tests` in an owned capped screen after lane release, plus the tools doctor and actual cap/user-bus validation. Use current workflow commands and exact-head evidence; the existing #65 user-bus issue is a real integration dependency.

Each run produces `manifest.json`, `commands.json`, `status.json`, `stdout/stderr` logs, result inventory, `hashes.json`, validity/coverage report, counters, and `receipt.json`. Each experiment produces the frozen protocol, seed/split manifest, all run-level results including failures, anytime data, analysis script/version, uncertainty/effect-size tables, and reconstruction command. Each laboratory campaign produces frozen predictions/protocol, material/specimen/instrument passports, immutable raw files, reductions, exclusions/censoring, comparison report and explicit applicability. Final release adds migration notes, historical reclassification diff, source/artifact inventory, independent review receipt and authorization state.

Failure interpretation: nonzero command is failure, not missing data to discard; missing tool is unavailable, not pass; source/hash drift is stale; solver divergence is numerical-invalid; insufficient required evidence is incomplete; failed physical criterion is scoped fail; outside domain is inapplicable. A parsed stored report is not a new computation. A positive simulated margin is not a measured property.

## 6. Resource plan, duration, and first dispatch

Initial observed xbabe2 state: 128 logical CPUs, 125 GiB RAM, load roughly 68–81, root disk 91% used with about 728 GB free, and many unrelated screens. These are a dated snapshot, not ongoing reservations. Start at **one heavy lane at a time, four CPU slots and 8 GiB per baseline lane**; allow lightweight planning/contract work in disjoint scopes. Larger solid/reference jobs can use up to 32 GiB only after admission. No GPU reservation, xbabe1 remains drained, xbabe3 is optional and needs fresh ownership/capacity checks. Limit each packet's outputs to 5 GB, with smaller log/summary targets; retain raw evidence by manifest rather than hoarding duplicate checkpoints.

First execution order: S00 → S01. Then parallel scopes S02 (solid arithmetic) / S04 (MC+legacy) / S05 (crescent selection), each with its own test process and only one heavy build at a time. S03 follows the agreed assurance interface. S06 follows S05; S07 follows S02; S08 integrates their interfaces serially. S09/S10 follow the baseline contracts, then S11/S12. S13 can proceed after S01 schema release while search work continues; S14 after S13. S15 waits on active render owner release. S16 is the final serial integration and independent review. All parallel packets have disjoint write sets; interfaces and shared-file edits flow through integrator.

Planning ranges, not promises: Phase 0 about 1–2 engineering days; Phase 1 about 5–10 person-days; Phase 2 about 8–15; Phase 3 about 10–20 depending on which hypotheses survive benchmarks; Phase 4 software/protocols about 5–10 plus separately arranged laboratory time; Phase 5 about 3–5 plus external review. With at most three disjoint workers, resource admission and serial integration remain the limiting factor. Re-estimate after S00 and the S09 pilot. Do not place physical completion on a fabricated calendar date.

## 7. Primary research basis

These sources guide the method, not claims of compliance or promised gains:

- [NASA-STD-7009](https://standards.nasa.gov/standard/nasa/nasa-std-7009) and [ASME V&V 10](https://www.asme.org/codes-standards/find-codes-standards/standard-for-verification-and-validation-in-computational-solid-mechanics): credibility requires explicit intended use and separate verification/validation/uncertainty evidence.
- [MAP-Elites original paper](https://arxiv.org/abs/1504.04909): motivates measuring diversity and quality across fixed descriptors instead of declaring one winner sufficient.
- [Surrogate-assisted illumination](https://arxiv.org/abs/1806.05865): motivates testing data-efficient exploration, with this project's additional reference-evaluation and applicability gates.
- [COCO performance assessment](https://numbbo.github.io/coco-doc/perf-assessment/): supports anytime, target-attainment/runtime analysis alongside final quality metrics.
- [Conformal prediction under covariate shift](https://papers.neurips.cc/paper_files/paper/2019/hash/8fb21ee7a2207526da55a679f0332de2-Abstract.html): motivates recording assumptions and shift handling rather than promising universal coverage on adaptive search proposals.
- [NIST AM fatigue/fracture program](https://www.nist.gov/programs-projects/additive-manufacturing-fatigue-and-fracture): supports keeping process/defect/surface-dependent manufacturing evidence separate.
- [ASTM C1624 official scope](https://store.astm.org/c1624-22.html): supports the thin-film method-applicability check. Full methods/current editions remain a laboratory responsibility.

No external source establishes current Jarambit product qualification. Scientific success includes exposing unsupported claims and rejecting unhelpful algorithms or surface hypotheses.
