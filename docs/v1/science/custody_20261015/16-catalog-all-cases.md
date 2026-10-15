Status: DONE-PASS
Subject: Exactly 178 unique frozen-catalog IDs; separate custody execution index
Date: 2026-10-15T07:05:10.442633+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [execution-index.json](execution-index.json), SHA-256 `8527efb3b41aa049a6a2166d3743c29a90863cc117190d8b5a8e686cc26bc0ac`
- [evidence/T18-decision-records.json](evidence/T18-decision-records.json), SHA-256 `93f0ec6a36c947b213ff2971efb1a261837539e09606a218962714778d3c03de`
- [evidence/CI-owner-evidence.json](evidence/CI-owner-evidence.json), SHA-256 `779fedcb8f53c2f5a5ddf94072beb1bbc38ed9746ba8ffb7a947f56aad7e8240`
- [evidence/required-workflows-disposition.json](evidence/required-workflows-disposition.json), SHA-256 `a1331d774a4d3b3fe6ca642a8578a6efa42dee59b4615c714c9355395119fef0`
- [evidence/planning-validation.json](evidence/planning-validation.json), SHA-256 `d3aaf95526dcdd97d62348635d79ae421b2fbfb25fc653f5a92dd1c48c83b939`

Numbers: DONE-PASS=18, executed=11, BLOCKED=149. The 11 executed rows preserve frozen T01 history. The 18 DONE-PASS dispositions comprise 11 existing T00 generic publication reconciliations and seven completed T18 decision records. T18 research software was not executed. The other 149 rows have an explicit input, ownership, admission or infrastructure blocker and a case-specific resume trigger.

The machine index retains each oracle, implementation path/presence, test names where found, original catalog status, receipt/reference/hash, scientific limitation and qualification boundary. T07 generic schema publication is acknowledged separately while physical rows remain blocked. Historical controller 49/108 and publication24 are existing records, distinct from the frozen 178-case planning statuses; this execution changes none of those counters. There are zero new product tests, solves, accepted groups or qualification claims.

T03 requires new root admission; T04 needs S05/S06 ownership and a lane; T06 needs its missing statistics controls plus source refreeze in an admitted lane; T19 has existing implementations but needs full exact-source collection/upstream evidence. Main CI is red on unchanged b35 because the explicit xbabe3 Cargo cache lacks index/config.json. Existing owner135 evidence and raw log are retained; no competing repair or wrapper patch was attempted. Both pinned workflow equivalents remain unrun here because lane/compute admission is absent. No push occurred.

| ID | Disposition | Owner | Evidence / missing input |
|---|---|---|---|
| T00-01-inventory_delete | DONE-PASS | 12 / S00,S01 | [T00-01-inventory_delete.json](evidence/retained/T00/cases/T00-01-inventory_delete.json) |
| T00-02-inventory_duplicate | DONE-PASS | 12 / S00,S01 | [T00-02-inventory_duplicate.json](evidence/retained/T00/cases/T00-02-inventory_duplicate.json) |
| T00-03-optional_skip | DONE-PASS | 12 / S00,S01 | [T00-03-optional_skip.json](evidence/retained/T00/cases/T00-03-optional_skip.json) |
| T00-04-strict_json | DONE-PASS | 12 / S00,S01 | [T00-04-strict_json.json](evidence/retained/T00/cases/T00-04-strict_json.json) |
| T00-05-receipt_tamper | DONE-PASS | 12 / S00,S01 | [T00-05-receipt_tamper.json](evidence/retained/T00/cases/T00-05-receipt_tamper.json) |
| T00-06-receipt_crash | DONE-PASS | 12 / S00,S01 | [T00-06-receipt_crash.json](evidence/retained/T00/cases/T00-06-receipt_crash.json) |
| T00-07-schema_bounds | DONE-PASS | 12 / S00,S01 | [T00-07-schema_bounds.json](evidence/retained/T00/cases/T00-07-schema_bounds.json) |
| T00-08-controls_missing | DONE-PASS | 12 / S00,S01 | [T00-08-controls_missing.json](evidence/retained/T00/cases/T00-08-controls_missing.json) |
| T00-09-finding_vs_execution | DONE-PASS | 12 / S00,S01 | [T00-09-finding_vs_execution.json](evidence/retained/T00/cases/T00-09-finding_vs_execution.json) |
| T00-10-claim_mutant | DONE-PASS | 12 / S00,S01 | [T00-10-claim_mutant.json](evidence/retained/T00/cases/T00-10-claim_mutant.json) |
| T00-11-standard_scope | DONE-PASS | 12 / S00,S01 | [T00-11-standard_scope.json](evidence/retained/T00/cases/T00-11-standard_scope.json) |
| T01-01-analytic_order | executed | 10 / S02 | [T01-01-analytic_order.json](evidence/retained/T01/cases/T01-01-analytic_order.json) |
| T01-02-divergent_order | executed | 10 / S02 | [T01-02-divergent_order.json](evidence/retained/T01/cases/T01-02-divergent_order.json) |
| T01-03-zero_order | executed | 10 / S02 | [T01-03-zero_order.json](evidence/retained/T01/cases/T01-03-zero_order.json) |
| T01-04-plateau | executed | 10 / S02 | [T01-04-plateau.json](evidence/retained/T01/cases/T01-04-plateau.json) |
| T01-05-oscillatory | executed | 10 / S02 | [T01-05-oscillatory.json](evidence/retained/T01/cases/T01-05-oscillatory.json) |
| T01-06-exact_equal | executed | 10 / S02 | [T01-06-exact_equal.json](evidence/retained/T01/cases/T01-06-exact_equal.json) |
| T01-07-invalid_ratio | executed | 10 / S02 | [T01-07-invalid_ratio.json](evidence/retained/T01/cases/T01-07-invalid_ratio.json) |
| T01-08-zero_reference | executed | 10 / S02 | [T01-08-zero_reference.json](evidence/retained/T01/cases/T01-08-zero_reference.json) |
| T01-09-precision_floor | executed | 10 / S02 | [T01-09-precision_floor.json](evidence/retained/T01/cases/T01-09-precision_floor.json) |
| T01-10-mesh_sequence | executed | 10 / S02 | [T01-10-mesh_sequence.json](evidence/retained/T01/cases/T01-10-mesh_sequence.json) |
| T01-11-observable_identity | executed | 10 / S02 | [T01-11-observable_identity.json](evidence/retained/T01/cases/T01-11-observable_identity.json) |
| T01-12-threshold_edge | BLOCKED | 10 / S02 | [T01-12-threshold_edge.json](evidence/retained/T01/cases/T01-12-threshold_edge.json); owned eligible lane, current-source receipt/CI attribution; thin allowed-path entrypoint |
| T01-13-negative_error_band | BLOCKED | 10 / S02 | [T01-13-negative_error_band.json](evidence/retained/T01/cases/T01-13-negative_error_band.json); owned eligible lane, current-source receipt/CI attribution; thin allowed-path entrypoint |
| T01-14-inventory_empty | BLOCKED | 10 / S02 | [T01-14-inventory_empty.json](evidence/retained/T01/cases/T01-14-inventory_empty.json); owned eligible lane, current-source receipt/CI attribution; thin allowed-path entrypoint |
| T01-15-stale_noop | BLOCKED | 10 / S02 | [T01-15-stale_noop.json](evidence/retained/T01/cases/T01-15-stale_noop.json); owned eligible lane, current-source receipt/CI attribution; thin allowed-path entrypoint |
| T01-16-cache_identity | BLOCKED | 10 / S02 | [T01-16-cache_identity.json](evidence/retained/T01/cases/T01-16-cache_identity.json); owned eligible lane, current-source receipt/CI attribution; thin allowed-path entrypoint |
| T01-17-partial_atomic | BLOCKED | 10 / S02 | [T01-17-partial_atomic.json](evidence/retained/T01/cases/T01-17-partial_atomic.json); owned eligible lane, current-source receipt/CI attribution; thin allowed-path entrypoint |
| T01-18-peak_singularity | BLOCKED | 10 / S02 | [T01-18-peak_singularity.json](evidence/retained/T01/cases/T01-18-peak_singularity.json); owned eligible lane, current-source receipt/CI attribution |
| T02-01-contradictory_block | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-02-missing_reopened | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-03-wrong_candidate | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-04-requirement_content | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-05-wrong_physics | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-06-revoked_review | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-07-presentation_noise | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-08-nonfinite_scalar | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-09-mass_scope | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-10-physical_missing | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-11-g1_delete | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T02-12-truthful_negative | BLOCKED | 12 / S03 | [claims-admission-disposition.json](evidence/claims-admission-disposition.json); genuine independent B/C/D runtime caller admission; allowed clean reference for unaided recheck |
| T03-01-empty_count | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-02-quantile_boundary | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-03-finite_reduction | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-04-invalid_sample | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-05-worker_panic | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-06-joint_correlation | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-07-independence_control | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-08-thread_replay | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-09-population_shift | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T03-10-media_retirement | BLOCKED | 16 / S04 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); new valid root admission against exact source/frozen oracles and an owned eligible lane |
| T04-01-all_infeasible | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-02-legal_vs_feasible | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-03-partial_nonfinite | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-04-novelty_context | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-05-ties_duplicates | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-06-invalid_config | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-07-checkpoint_matrix | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-08-checkpoint_corrupt | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-09-resume_identity | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-10-durability_boundary | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-11-duplicate_resume | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T04-12-lineage_orphan | BLOCKED | 16 / S05,S06 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible source lane and S05/S06 scope release; search_contract.rs absent at product reference |
| T05-01-linear_scaling | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-02-rigid_transform | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-03-unit_consistency | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-04-analytic_balance | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-05-bc_failure | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-06-mesh_failure | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-07-field_semantics | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-08-localized_peak | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-09-certificate_field | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-10-native_binding | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-11-calibration_failures | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T05-12-tier_collision | BLOCKED | 11 / S07,S08 | [T05-holder-blocker.json](evidence/T05-holder-blocker.json); jarambit_claude screen exit, clean explicit S07 handoff, eligible admitted lane |
| T06-01-cpu_accounting | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-02-workload_collision | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-03-equal_budget | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-04-related_split | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-05-session_shortcut | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-06-preprocessing_leak | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-07-single_specimen | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-08-uncertainty_censor | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-09-null_benchmark | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T06-10-surrogate_gate | BLOCKED | 16 / S09,S11 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible assurance lane; test_statistics.py absent at product reference |
| T07-01-specimen_identity | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); real named specimen/lot/form passport and raw observation |
| T07-02-unapproved_transfer | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual specimen transfer record with independent approval boundary |
| T07-03-history_prefix | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual timestamped observation bound to its validated history prefix |
| T07-04-clock_segments | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); timestamped history with clock segments and discontinuity evidence |
| T07-05-raw_calibration | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); raw instrument acquisition and valid calibration identities |
| T07-06-lab_reduction | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); raw laboratory measurements and independently reproducible reduction |
| T07-07-finished_mass | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); weighed finished specimen mass, distinct from CAD mass |
| T07-08-frame_unit | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured frame/orientation and calibrated units |
| T07-09-censored_zero | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual censoring/detection limits or legitimate measured-zero observation |
| T07-10-chemistry_scope | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured chemistry/oxygen on the named material lot |
| T07-11-measurement_lineage | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured observation with complete acquisition/preparation lineage |
| T07-12-interpretation_unknown | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); real observation with explicit unknown interpretation preserved |
| T07-13-historical_adapter | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual historical laboratory record with an evidence-preserving adapter |
| T08-01-bounded_download | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); acquisition/scan objects with bounded transfer, hashes and download evidence |
| T08-02-units_metadata | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); scan acquisition metadata with calibrated units/scale |
| T08-03-registration_truth | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); scan registration and independent fiducial/registration truth |
| T08-04-orientation_symmetry | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured orientation/symmetry controls and registration uncertainty |
| T08-05-matched_slip_missing | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); matched acquisition/slip observations with missingness documented |
| T08-06-group_acquisition | BLOCKED | 13 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); grouped acquisition objects with specimen/session identities |
| T09-01-latent_collision | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent manufacturing-lot observations exposing latent collisions |
| T09-02-sufficient_null | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent lot data and a sufficiently powered null control |
| T09-03-matching_bias | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent lot data with matching-bias controls |
| T09-04-early_irreversible | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); lot-linked timestamped early/irreversible observations |
| T09-05-lot_confirmation | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent second-lot confirmation data |
| T09-06-low_power_null | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent lot data, power/uncertainty and inconclusive-null controls |
| T10-01-same_marginals_graph | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured microstructure graph with equal-marginal comparison objects |
| T10-02-physical_rotation | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured graph and physical-rotation reference |
| T10-03-shuffle_control | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured graph with independently defined shuffle controls |
| T10-04-resolution_boundary | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured graph with resolution/segmentation sensitivity evidence |
| T10-05-chemistry_organization | BLOCKED | 16 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured film chemistry/spatial organization and named substrate |
| T11-01-sequence_controls | BLOCKED | 13 / S13,S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); timestamped actual load history and sequence controls |
| T11-02-order_null | BLOCKED | 13 / S13,S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual load-order history with predeclared null comparison |
| T11-03-order_positive | BLOCKED | 13 / S13,S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual load-order history with predeclared positive comparison |
| T11-04-cycle_time_clock | BLOCKED | 13 / S13,S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual cycle/time history and calibrated clock segments |
| T11-05-hold_redistribution | BLOCKED | 13 / S13,S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual hold history and measured redistribution |
| T11-06-acceleration_mode | BLOCKED | 13 / S13,S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual acceleration history with demonstrated mode identity |
| T11-07-competing_censor | BLOCKED | 13 / S13,S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual competing-event history and censoring records |
| T12-01-observation_arms | BLOCKED | 14 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured observation/preparation arms on a named filmed coupon |
| T12-02-created_erased | BLOCKED | 14 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured created/erased effects with preparation controls |
| T12-03-drift_only | BLOCKED | 14 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured instrument drift and sham/reference arm |
| T12-04-true_nuisance | BLOCKED | 14 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured true-signal/nuisance controls |
| T12-05-prep_transfer | BLOCKED | 14 / S13 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured preparation-transfer arms with substrate identity |
| T13-01-process_vs_film | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured film plus sham deposition/process control |
| T13-02-coupling_null | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured exposure arms allowing additive, null, synergy and antagonism |
| T13-03-topology_average | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured connected-defect topology independent of mean thickness/fraction |
| T13-04-segmentation_bias | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured surface segmentation/resolution controls chosen independently of outcomes |
| T13-05-balance_reservoir | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured mass balance including debris/solution reservoirs and collection completeness |
| T13-06-charge_not_loss | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured charge and separately measured mechanical/material loss |
| T13-07-barrier_vs_structure | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured barrier and structural damage/recovery observations |
| T14-01-truth_independent | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent defect truth and qualified inspection record |
| T14-02-silent_damage | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent silent-damage truth and inspection record |
| T14-03-healthy_nuisance | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); qualified healthy/nuisance inspection controls |
| T14-04-instrument_nonlinearity | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); calibrated inspection instrument with nonlinearity controls and defect truth |
| T14-05-lot_session_holdout | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent inspection lot/session holdouts |
| T14-06-pod_prevalence | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); qualified POD/prevalence data and independent defect truth |
| T14-07-blind_zone | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independently known blind-zone defects and qualified inspection records |
| T14-08-warning_censor | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual warning/censoring observations with qualified inspection truth |
| T14-09-shared_sensor_bias | BLOCKED | 13 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); independent sensor-bias controls and defect truth |
| T15-01-strain_vs_damage | BLOCKED | 16 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); real witness/sensor record with separate strain and damage reference |
| T15-02-witness_invalid | BLOCKED | 16 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual invalid-witness record and independent reference |
| T15-03-shared_selftest | BLOCKED | 16 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); real sensor self-test with an independent shared-bias reference |
| T15-04-warning_persistence | BLOCKED | 16 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual warning-persistence history and reference damage observations |
| T15-05-reader_environment | BLOCKED | 16 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); actual reader/environment controls on a named sensor/witness |
| T15-06-mass_coupling | BLOCKED | 16 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); weighed witness/sensor and measured mass-coupling reference |
| T16-01-closure_false_heal | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured film/defect closure and independent persistent-damage reference |
| T16-02-recovery_positive | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured recovery and predeclared positive/sham controls |
| T16-03-failure_migration | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured failure-migration observations and unchanged substrate identity |
| T16-04-isotope_exchange | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured isotope ratios on a named substrate/film with exchange controls |
| T16-05-source_ambiguity | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured isotope ratios and independent source-discrimination reference |
| T16-06-nanoscale_transfer | BLOCKED | 14 / S14 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); measured nanoscale film evidence and explicit transfer-domain reference |
| T17-01-model_domain | BLOCKED | 09,16 / S11 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); same-geometry solver pair plus qualified mechanism/phase/charge/reactivity domain evidence |
| T17-02-transition_error | BLOCKED | 09,16 / S11 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); same-geometry solver pair plus independent transition/barrier/force reference |
| T17-03-ensemble_shared_bias | BLOCKED | 09,16 / S11 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); same-geometry solver pair plus independent shared-bias/discrepancy reference |
| T17-04-rate_sensitivity | BLOCKED | 09,16 / S11 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); required solver-pair context and predeclared rate-sensitivity reference; no measured Ti-rate inference |
| T17-05-time_bridge | BLOCKED | 09,16 / S11 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); same-geometry solver pair plus a valid kinetic/time-bridge reference |
| T17-06-holdout_reference | BLOCKED | 09,16 / S11 | [physical-evidence-scope.json](evidence/physical-evidence-scope.json); same-geometry solver pair plus independent unused holdout and reference uncertainty |
| T18-01-mixed_none_models | DONE-PASS | 16 / S10,S11 | [T18-decision-records.json](evidence/T18-decision-records.json); decision memo only, research software not run |
| T18-02-nonidentifiable | DONE-PASS | 16 / S10,S11 | [T18-decision-records.json](evidence/T18-decision-records.json); decision memo only, research software not run |
| T18-03-audit_independent | DONE-PASS | 16 / S10,S11 | [T18-decision-records.json](evidence/T18-decision-records.json); decision memo only, research software not run |
| T18-04-budget_menu | DONE-PASS | 16 / S10,S11 | [T18-decision-records.json](evidence/T18-decision-records.json); decision memo only, research software not run |
| T18-05-strategy_comparison | DONE-PASS | 16 / S10,S11 | [T18-decision-records.json](evidence/T18-decision-records.json); decision memo only, research software not run |
| T18-06-failed_acquisition | DONE-PASS | 16 / S10,S11 | [T18-decision-records.json](evidence/T18-decision-records.json); decision memo only, research software not run |
| T18-07-authority_boundary | DONE-PASS | 16 / S10,S11 | [T18-decision-records.json](evidence/T18-decision-records.json); decision memo only, research software not run |
| T19-01-required_skip | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-02-path_filter | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-03-capability_omission | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-04-runner_escape | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-05-upload_missing | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-06-fresh_vs_reuse | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-07-dossier_mismatch | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-08-render_finish_metadata | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-09-protective_interface | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |
| T19-10-final_policy | BLOCKED | 16 / S16 | [remaining-software-implementation.json](evidence/remaining-software-implementation.json); owned eligible lane and exact-source full collector/required upstream execution; main CI cache prerequisite is red under its existing owner |

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.
