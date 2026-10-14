# Science v1 execution todos

Integration assignment: S00 → S01/T00, after the R0029/sheath safe handoff.
Controller owns the operational board; workers update their own atomic lane state
and append events every 15 minutes and at milestones. Queued work is not running;
completion requires exact-source receipts. This document is a versioned scope and
dependency snapshot, not an automatic live success claim.

Planning reference: `codex/science-v1-plan` commit
`75bc76b01d403ebaf44e6980f38adc050ddd5233`, files `docs/v1/science/RELEASE_PLAN.md`,
`WORK_PACKETS.json`, `tests/TEST_UPGRADE_PLAN.md`, `tests/TEST_WORK_PACKETS.json`.
Their full content pins are in the baseline manifest; implementation brings only
the reviewed interface slices it needs into main. Large planning catalogs describe
proposed cases and do not count as executed tests.

## Ordered work and acceptance

| Todo | Prerequisites | Done criterion / acceptance overlay |
|---|---|---|
| S00 | none | Exact source/RS/evaluator/scenario/objective/descriptor/material/CAD pins; reconciled roadmap/queue/ownership; retained §19; immutable baseline receipt |
| S01 | S00 core freeze | Strict observations/identity; required coverage; dependency/review revocation; no invalid/legacy/physical-label false PASS; all 11 T00 controls with receipts |
| S02 | S01 | Admissible GCI; fresh attempts; empty/stale/nonfinite/oscillatory cases nonpassing; 18 T01 groups |
| S03 | S01,S02 | Exact scoped generated claims, requirement roles/content and current registry; 12 T02 groups |
| S04 | S01 | Checked MC counts/reduction, joint sample truth, retired lookup adapter; 10 T03 groups |
| S05 | S01 | Feasible archive and context-free replacement; owned search phase of T04 |
| S06 | S01,S05 | Durable crescent restart/identity/counters; owned checkpoint phase of T04; 12 groups total |
| S07 | S01,S02 | Declared field extraction matches code and generic numerical invariants; owned numerical phase of T05 |
| S08 | S02–S07 | Exact per-case mesh/field/CAD/evaluator binding; native adapter without invented genome; binding phase of T05; 12 groups total |
| S09 | S08 | CPU/budget/keyed parity, frozen splits/analysis, reproducible tables; core T06 phase |
| S10 | S08 | Minimal generic interfaces and algorithms; equivalent baseline decisions; benign reference fixtures |
| S11 | S07,S09,S10 | Scoped/OOD surrogate with independent audits; no qualified surrogate PASS; T06 consumer and conditional T17/T18 |
| S12 | S10,S11 | Complete cache identities and retry accounting; equal decisions and measured bounded performance |
| S13 | S01 | Strict material/lab/history/calibration identity; no fabricated data or unapproved transfer; 13 T07 groups; conditional T08–T12 |
| S14 | S13 | Scoped metrology/inspection/surface/inert handling; no mass/scan/finish-to-strength shortcuts; conditional T11,T13–T16 |
| S15 | S03,S08,render release | Claim state in media; missing/reopened dependencies unknown; protected metal/resources retained |
| S16 | S00–S15 | Exact-head independent reconstruction/review/CI; all inherited/activated gates or explicit recorded owner amendment; 10 T19 groups |

T00–T07 plus T19 mandatory software inventory has 108 planned groups. T08–T18
adds 70 conditional research groups. Those numbers describe inventory, not tests
run. Shipped research import/analysis/capability contracts become mandatory;
disabled research requires a reason and supports no positive claim. Actual
physical requirements retain their existing release effect.

## Candidate and operational holds

C.10a rc4 is comparison baseline; RS/native evaluator binding is incomplete.
C.10c was removed by #68 and remains archived diagnostic-only. No geometry repair,
genome reconstruction, re-optimization, ratio transfer, or candidate promotion is
part of this dispatch. W84/V3 and incomplete V4 convergence remain visible.

The existing steward owns one PR at a time. Local work/commits may proceed within
owned paths; an empty queue does not transfer ownership of the merge slot. Every
PR/rebase needs current-base source checks and fresh eligible independent review.
This lane never self-approves, merges, modifies another branch, or changes versions.

One admitted heavy lane: four CPUs, 8 GiB RAM, no swap, native pools one, CPU only,
private reused target/output, <5 GB output. Preserve dirty live main COORD/lock,
other worktrees and render/sheath jobs. No external contact or physical controls.

Every READY receipt names base/tested/head SHA, exact argv and exit counts,
input/policy/oracle hashes, controls/mutants, missing evidence and artifact hashes.
A passing rejection test does not physically qualify a product. Final 1.0.0 holds
remain the master §19 gates recorded in release-v1 policy and the amendment.
