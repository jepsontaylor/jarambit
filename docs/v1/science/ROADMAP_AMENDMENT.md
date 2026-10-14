# Science v1 baseline reconciliation

This records S00's software baseline and proposed interfaces. It grants no release,
manufacturing, or physical qualification. The master specification and its §19
gates remain in force, including the recorded mass-policy addendum. Pending owner
decisions are explicit in [release policy](../../../assurance/policies/release-v1.json).

## Current source, ownership, and candidate

The frozen source is post-revert main `b81aa99d43cc56b9338969f76e3214785fa7559a`.
PR #68 removed C.10c by owner decision. Both C.10c branches remain untouched.
C.10c is archived diagnostic material and is excluded from current qualification.
C.10a rc4 is the native CAD comparison baseline. Its STEP and STL, data records,
requirements, source, evaluator, scenarios, objectives, descriptors, material
assumptions, and seeds have full SHA-256 pins in the
[baseline manifest](../../../experiments/science_v1/baseline_manifest.json).

C.10a's reported 64.841 g and fitness 2.673 are historical study values. They are
not freshly evaluated RS-karambit-v2 observations. Its genome binding is absent;
V3 certification is reopened by W84 and V4 remains incompletely converged. Native
study SF≥1.575 / mass<70 g criteria differ from RS-v2. No copied genome, carried
ratio, or different mesh can bridge that gap. Current RS qualification is INCOMPLETE.

The live queue was empty at freeze after #68. The existing executor/steward owns
the one-PR slot and merge sequence. Integration owns S00 followed by S01/T00.
The CAD lane owns disjoint `ops/science_tests/native_cad` files; its local diagnostic
commit `dd020b9` has coordinator changes requested. No native adapter, generated
report, render, or live COORD/lock write is taken over by this cut.

## Old roadmap reconciled with actual source

The old roadmap describes v0.27 and a 404-hour estimate. Neither its version labels
nor completed PR titles are evidence of today's acceptance criteria. Of the planning
audit's 48 selected files, 47 are byte-identical on this baseline. The marketing
smoke workflow changed through the protected-metal/memory-cap train. Existing
render/sheath protections and the 20-minute smoke timeout are retained.

| Old work items | Current implementation | Remaining criterion / owner |
|---|---|---|
| 0.28.1 | Implemented: G1 complete inputs, genuine zero, bool/nonfinite rejection, golden/deletion tests | Keep G1 frozen; native CAD lacks its complete inputs |
| 0.28.2 | Partial: RS registry and scoped verdicts exist; mass is soft | Exact claim blocks and current registry remain S03 |
| 0.28.3 | Implemented: typed null FEM/serialization and mass-bin header | Preserve existing records/tests |
| 0.28.4 | Implemented: expected theory inventory rejects missing/nonfinite checks | Preserve theory coverage |
| 0.28.5 | Partial: pinned compiler/actions and generated status exist | Current/historical candidate reconciliation remains S03 |
| 0.29.1 | Partial: event frames, lineage, migration and fresh/appearance counters exist | Scientific content identity S01; durable qualification S06 |
| 0.29.2 | Partial: lossless manifest-bound legacy replay exists | Crescent checkpoint/recovery absent; S06 |
| 0.29.3 | Implemented legacy streaming/feasible-mean/terminal snapshot contracts | Keep legacy tests; do not describe these as absent |
| 0.29.4 | Partial: figure hashes, captions and manifests exist | Current dependency/review state in consumers S03/S15 |
| 0.30.1 | Implemented reference submodel source, input guards and opt-in historical regression | Fresh expensive reproduction not performed in S00 |
| 0.30.2 | Partial: solid mesher/reference solver and verification records exist | Exact solver-image digest and fresh numerical admission unresolved |
| 0.30.3 | Partial: GCI arithmetic, records/report exist | Invalid order, plateau, oscillation, empty inventory and stale reuse S02 |
| 0.31.1 | Partial: frozen workload and benchmark harness exist | Actual CPU/RSS/keyed parity accounting S09 |
| 0.31.2 | Partial: sparse solver/parity code and work stealing exist; skyline remains default | Faer certification drift exceeds locked 1e-9; no new speed result; mesh bindings S08 |
| 0.31.3 | Partial: human-max, fatigue screening and calibration implemented | Twist residual 10.8% exceeds 7%; physical allowables absent |
| 0.32.1–2 | Missing generic core/plugin interfaces | Minimal adapter S10; do not move the evidence crate |
| 0.32.3 | Missing retirement: legacy CutMedia still exists | Active retirement with historical reads S04 |
| 0.33.1–2 | Partial: current thickness/machining/pocket/isogrid representation exists | Proposed generic skeleton/SDF/DFM/cost acceptance unproven |
| 0.33.3–4 | Partial: native C.10a B-rep/ring exists outside genome pipeline; faceted preview remains | No automated native/genome equivalence; S08 identity adapter |
| 0.34.1–2 | Partial: legacy NSGA-II and crescent scalar GA/archive/islands exist | Context-free feasible archive S05; shared-evaluator algorithms S10 |
| 0.34.3 | Missing equal-budget, same-representation scientific comparison | Harness S09; negative results retained |
| 0.35.1–3 | Unimplemented/unqualified distributed cache, GPU reference and surrogate targets | S11/S12 only after evidence and measured need |
| 0.36.1–2 | Unimplemented adversarial-load discovery / qualified probability basket | No replacement physical prediction inferred from retired lookup |
| 0.37.1 | Partial: C6 reference-style/aesthetic checks exist | Learned preference and claimed accuracy not established |
| 0.37.2–3 | Human preference/RFQ qualification missing; patent-view rendering exists | Owner-arranged studies/quotes; no external contact by this lane |
| 0.38.1–2 | Native low-mass study records exist; standard-pipeline campaign/complete RS verdict missing | No all-hard native promotion from reported fitness |
| 1.0.1–2 | Physical proof/coupon evidence and generic bracket release missing | §19 remains required; S13/S14/S16 and owner/lab holds |

Source paths and hashes in the baseline distinguish implemented code from numerical
verification and physical validation. Historical evidence is preserved unchanged.

## Frozen S01/T00 interface

Extend `jarambit-evidence`; its resolver remains authoritative. Preserve `Obs`,
`Outcome`, JEV1 framing/events and legacy manifest hashes for historical reads.
New qualified writes bind subject (genome bits, native CAD hash, or specimen),
full requirement content/inheritance, source/build/dependencies/config/evaluator,
scenario/objective/descriptor/material, and observable quantity/unit/frame/region/
recovery. Missing or unknown qualification provenance maps to INCOMPLETE.
Host, threads, timing and memory are separate runtime metadata.

Execution, numerical validity, physical validation, review, and criterion verdict
remain separate. Strict finite observations cannot synthesize physical validation.
Expected required coverage is explicit and nonempty. Dependency resolution rejects
cycles, duplicate IDs, missing/mismatched content, stale/superseded observations,
and reopened/revoked review. Delete any required support: eligibility cannot improve.
Record-only and optional criteria retain their declared roles. An applicable valid
adverse observation can FAIL; an invalid calculation is INCOMPLETE.

The new canonical wire is `jarambit.science.canonical.v1`, distinct from raw SHA-256
and legacy manifest JSON. Encode parsed JSON as concatenated UTF-8 tokens: null `n`,
boolean `t`/`f`, string `s<byte-length>:<bytes>`, nonnegative integer `u<decimal>;`,
negative integer `i<decimal>;`, finite binary64 `d<16 lowercase hex bits>;`, array
`a<count>:` followed by values, object `o<count>:` followed by encoded key/value
pairs in UTF-8 key order. Integer domain is signed i64 through unsigned u64.
Float exponent spellings share IEEE bits; signed zero remains distinct. Unicode
is preserved, with normalization collisions rejected at identity ingress. Do not
coerce booleans, numeric strings, unknown enums or oversized/deep payloads.
Cross-language parity/control fixtures in S01/T00 must verify this exact contract.

T00's eleven frozen case IDs/oracle-definition hashes and the inherited nineteen
regression mappings are in the release policy. S00 closes its policy/inventory
freeze before S01 implements those controls; later research does not create a
predecessor cycle. Execution `passed/failed/error/not_run` is separate from finding
`supported_within_scope/rejected_within_scope/inconclusive/not_applicable`.
Required unavailable evidence stays incomplete. Disabled research carries no claim.

## Release holds and next work

All seven master §19 gates remain required. The recorded mass addendum controls
promotion semantics; it does not erase the distinct ≤75 g verified-design release
goal. No owner amendment of physical, performance, algorithm, cost, preference,
or generality obligations is inferred. Wrought machining is a planning default,
not a qualified lot/process state. No finish modifies structural material properties.

The next owned phase is S01/T00 identity, strict observations, dependency/review
revocation, expected coverage, historical adapters and positive/adverse/control
tests. S02/S03/S08 numerical/binding gaps and actual lab proof remain visible.
See [active todos](ACTIVE_TODOS.md). No version change occurs in this cut.
