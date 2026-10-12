# Feedback synthesis — 6 reviews of jarambit @727b28b (author: Jepson Taylor)

FB1 = 72238e2a, FB2 = 81673801, FB3 = 826d3a13, FB4 = be6b3ecf, FB5 = a6e35505, FB6 = 4c2f05b7. "Verified" means checked against the code (see the spec §2 for path:line). PR ids refer to `jarambit_v1_roadmap.json`.

| # | Idea | Files | Verified? | Decision | Reason / PR |
|---|---|---|---|---|---|
| 1 | Scope every PASS to a named, versioned requirement set; split search handling / report eligibility / product approval | all | yes | **KEEP** | P0; PR-0.28.2 |
| 2 | G1 missing → 0 must become INCOMPLETE; separate the provisional flag from completeness | all | yes | **KEEP** | P0; PR-0.28.1 |
| 3 | `title_tag` re-parses raw mass (TypeError) | FB4, FB5 | yes | **KEEP** | PR-0.28.1 |
| 4 | README "plate by default" vs CLI opt-in | FB1, FB4–6 | yes | **KEEP** | PR-0.28.2 |
| 5 | Absent FEM → default zeros in JSON/CSV | FB3, FB4, FB6 | yes | **KEEP** | PR-0.28.3 |
| 6 | Duplicate `pry20` key; scalar NaN unguarded; use typed serialization | FB2, FB4, FB6 | yes | **KEEP** | PR-0.28.3 |
| 7 | QD CSV header `cell_hausdorff` is actually mass | FB2 | yes (comment wrong too) | **KEEP** | PR-0.28.3 |
| 8 | Theory gate fails open (missing/NaN) | FB5 | yes | **KEEP** | PR-0.28.4 |
| 9 | `err_vs_extrap` mislabelled | FB5 | yes | **KEEP** | PR-0.28.4 |
| 10 | Pin toolchain/actions; separate compatibility CI from reproduction CI | FB2–FB4 | yes | **KEEP** | PR-0.28.5 |
| 11 | One generated current-status view; mark GAPS/Appendix A historical | FB2–FB6 | yes | **KEEP** | PR-0.28.5 |
| 12 | Append-only event log with parents/op/migration; lineage unknown ≠ inferred | all | yes (no parents in `Rec`) | **KEEP** | PR-0.29.1 |
| 13 | Honest counters (appearances vs fresh evals vs solver calls) | FB1, FB2, FB4, FB6 | yes | **KEEP** | PR-0.29.1 |
| 14 | Checkpoint lossless, bound to the manifest, refuse incompatible/missing resume, explicit fork | all | yes | **KEEP** | PR-0.29.2 |
| 15 | Stream history; write the genotype in quarantine; terminal snapshot | FB1, FB5, FB6 | yes | **KEEP** | PR-0.29.3 |
| 16 | "Feasible mean" uses −100 not `feasible()` | FB1 | yes | **KEEP** | PR-0.29.3 |
| 17 | Figure manifests; captions/badges from data; hero STL-vs-STEP label | all | yes | **KEEP** | PR-0.29.4 |
| 18 | Hard-coded aesthetic PASS badge | FB4, FB6 | yes | **KEEP** | PR-0.29.4 |
| 19 | Declare per-figure normalization/clipping | FB6 | partial | **KEEP** | PR-0.29.4 |
| 20 | `certify` mixes meshes; attach mesh id per scalar/field; check two-level agreement | FB3, FB5 | yes | **KEEP** | §7 T1c, PR-0.31.2 |
| 21 | Novelty-context drift in archive replacement | FB2, FB3, FB5 | yes | **KEEP** (fix by design) | context-free elite quality, PR-0.34.1 |
| 22 | Distinguish byte vs semantic artifact identity (`HashMap` order) | FB3, FB5 | risk | **KEEP** | sorted maps, PR-0.33.3 |
| 23 | Rename aesthetic → "reference-style conformance"; run a blinded human preference study | all | yes | **KEEP + EXTEND** | learned BT model, PR-0.37.1/2 |
| 24 | Publish a representation capability card (2.5D, priors) | FB2, FB5, FB6 | yes | **KEEP** | spec §5 table; doc in PR-0.33.1 |
| 25 | MC media lookup ≠ impact simulation; don't call it robust strike | all | yes | **KEEP → RETIRE strike MC** | owner scope; PR-0.32.3 + adversarial loads v0.36 |
| 26 | Discovery sets ≠ prevalence estimates | FB2, FB3, FB5 | n/a | **KEEP** | §8 rule; PR-0.36.2 |
| 27 | Per-run algorithm/objective/metric IDs (two engines exist) | all | yes | **KEEP** | RunManifest, PR-0.29.1 |
| 28 | "Reject, never penalise" wording is false | FB1 | yes | **KEEP** | PR-0.28.2 wording |
| 29 | Calibration 258 rows are correlated; grouped splits for any ML | FB3, FB5, FB6 | partial | **KEEP** | PR-0.35.3 split manifest |
| 30 | Data cards / problems-evals-events-artifacts-splits tables | FB3, FB5 | n/a | **KEEP (light)** | evidence crate + data card |
| 31 | NASA-STD-7009-style credibility framing (verification vs validation) | FB2, FB4, FB5 | n/a | **KEEP** | §7.1 + coupon tests |
| 32 | Counsel review of public disclosure; utility draft ≠ design patent; no design provisional; AI inventorship log | all | yes | **KEEP (urgent, non-engineering)** | spec §17; HumanDecision events |
| 33 | Benchmark with a fixed-workload accounting manifest (attempts, failures, cache, hardware) | all | n/a | **KEEP** | PR-0.31.1 |
| 34 | Don't recommend a worker pool/threads as if they were missing | all | yes | **KEEP** (as a constraint) | HPC plan targets the solver + distribution instead |
| 35 | Refuse to advise on strength/material/manufacturing/HPC | all | n/a | **REJECT** | out of step with the owner's utility-structure scope; covered in spec §6–§7, §14–§15 |
| 36 | Generality only via a separate *non-structural* thermal/enclosure demo | FB3–FB6 | n/a | **MODIFY** | Ti bracket structural demo shares core (PR-1.0.2); thermal demo deferred |
| 37 | Make the paper's contribution "evidence-contract layer detects unsupported claims" (fault-injection study) | FB3, FB4, FB5, FB6 | n/a | **DEFER** | good secondary paper after v0.29; not on the v1 critical path |
| 38 | Avoid microservices; keep modules in-process | FB2 | n/a | **KEEP (partially)** | in-process evidence; Ray only for distribution |
| 39 | Don't add search complexity before evidence gates | FB2, FB5 | n/a | **KEEP (sequencing)** | v0.28–0.29 before v0.34 |
| 40 | Preserve existing strengths: thread-stable MC seeds, tmp+rename ckpt, known-negative CI, not-promoted language | all | yes | **KEEP** | invariants in every PR |
| 41 | Controlled, matched-budget comparisons with independent seeds, not best-per-wave tables | FB2–FB6 | n/a | **KEEP** | PR-0.34.3 |
| 42 | Score context IDs for contextual (novelty) scores | FB2, FB5 | n/a | **KEEP** | ArchiveChanged.quality_ctx |
| 43 | Interpolated animation frames must be labelled | FB1, FB2, FB5 | n/a | **KEEP** | spec §13 morph reel watermark |
| 44 | IEEE venue/acceptance claims are unwarranted | FB4, FB5, FB6 | n/a | **KEEP** | no venue claims in docs |
| 45 | Earlier independent diffusion/thermal dataset is not Jarambit evidence | FB3, FB5, FB6 | n/a | **KEEP** | never cite as jarambit data |

**Not raised by any review but adopted:** out-of-repo solid tip solver (P0, PR-0.30.1); fatigue and baton cases (PR-0.31.3); the 2.5D mass-floor arithmetic for 70 g (spec §0/§5); RTX 3090 FP64 limits on GPU solver choice (spec §14); seq "soft" in the docs vs hard in `legal()`.
