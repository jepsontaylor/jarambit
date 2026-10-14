# Jarambit 1.0 science planning package

Read [RELEASE_PLAN.md](RELEASE_PLAN.md) first: objective, release policy, seventeen implementation packets, contracts, validation, resource limits, and physical/scientific gates.

The new [test upgrade plan](tests/TEST_UPGRADE_PLAN.md) integrates all ten test documents with the original twelve sources: **20 acceptance work units and 178 planned challenge groups**. [Test package index](tests/README.md) links the case catalog, input dispositions, conditional research gates, source checks and executor handoff. These are proposed tests, not executed-test counts. T units remain inside existing S ownership; required software checks and inherited physical gates precede any new capability claim.

- [FINDINGS.md](FINDINGS.md): 21 source/record/probe findings, their limits, and existing work to retain.
- [INPUT_COVERAGE.md](INPUT_COVERAGE.md): explicit disposition of all twelve supplied files.
- [WORK_PACKETS.json](WORK_PACKETS.json): dependency DAG, exact allowed paths, steps, acceptance, resource defaults, and all 19 supplied regression mappings.
- [WORKTREE_RUNBOOK.md](WORKTREE_RUNBOOK.md): xbabe2 worktrees/screens, ownership, admission, receipts, integration, restart and cleanup.
- [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json): hashes for all twelve inputs and 48 selected baseline source files.
- [STUDY_RECEIPT.json](STUDY_RECEIPT.json): commands, exit codes, timings, test counts and artifact hashes.
- [study/probes.json](study/probes.json): executed numerical/reporting probe results.
- [inputs/NUMERICAL_AND_EVIDENCE_REGRESSION_CASES.json](inputs/NUMERICAL_AND_EVIDENCE_REGRESSION_CASES.json): unchanged proposed fixtures supplied by the user.

Frozen source: `97af59cf14299af583b344aeaefb4594d089465a`. Planning branch on xbabe2: `codex/science-v1-plan`, worktree `/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-plan`.

Baseline execution: Rust **111 passed, 0 failed, 1 existing ignored**; Python solid/metric suites **23 passed, 1 skipped**; baseline claim checker, fresh D1 known-negative and strict JSON checks passed. Expensive solid recomputation and physical testing were not performed. Isolated negative probes still demonstrate defects despite the passing baseline suites.

`study/run_study.py` is the archived script used on the frozen checkout, with its original absolute worktree path. It intentionally refuses a different HEAD. Use a clean checkout of the frozen source for reproduction; it is not a general worker launcher. Full raw test logs and small D1 output remain in the owned remote scratch, with hashes in the receipt. The input files moved during study to `/Users/bentaylor/Downloads/scratch/jarambi/`; both original and recovered locations are recorded.

Status: plan complete, implementation not dispatched. No version bump, PR, merge, tag, manufacturing authorization or change to live main source was made. An independent executor must reconcile pending owner release-policy amendments and current lane ownership before starting packets.
