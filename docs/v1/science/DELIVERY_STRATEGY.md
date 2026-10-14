# Single PR delivery strategy

This is a versioned snapshot of the owner's delivery decision on 2026-10-14.
The [current goal and execution plan](MASTER_GOAL.md) records the scoped work,
remaining findings and acceptance criteria. The older [baseline reconciliation](ROADMAP_AMENDMENT.md)
and [S00 dependency snapshot](ACTIVE_TODOS.md) retain their historical scope;
the delivery decision here supersedes their earlier phase-PR sequencing.

## One aggregate draft

All eligible work accumulates in [draft PR #72](https://github.com/neverhuman/jarambit/pull/72)
on `codex/science-v1-foundation-publication-cd31377`. The integration lane is the
sole writer of that branch and its existing publication checkout. Other workers
keep disjoint source leases and export completed local commits with exact source,
test and review receipts. Queueing work is distinct from an actual acknowledgement.

CI runs asynchronously. A pending or red earlier CI run does not prevent eligible
implementation or a coherent forward push to this draft. Superseded CI runs may
be cancelled by the scoped concurrency rule for this owned PR only. Required tests,
conditions, resource limits and missing-evidence refusal remain unchanged.

Current-head required checks, eligible independent review and all final release
gates still block the designated steward's merge. Published source, passing test
executions, locally accepted groups and merged release work are separate states.
No worker grants acceptance from its own labels or test counts.

## Forward publication and ownership

1. Preserve the released source packets, original authors, fixed oracles and old
   receipts. Integrate only the leased paths of a ready packet; keep real failures
   and held criteria visible.
2. Fetch current main and verify the clean owned branch, sole open draft and exact
   remote head before each push. Reconcile changes on the aggregate branch without
   rewriting published history or other workers' branches.
3. Publish a coherent milestone with a normal forward push to the same draft.
   Record commit and blob mappings, source identity, actual validation, remaining
   findings and an immutable handoff. Update the same PR description.
4. Run only admitted checks through the merged bounded wrapper. Ordinary small
   software checks use 2 GiB, one CPU, no swap, native pools one and nice 19. The
   separate heavy slot uses four CPUs and 8 GiB. Reuse each checkout's target and
   private output directories; retain failed attempts.
5. Check in every 15 minutes and at milestones through the lane's atomic state.
   The controller maintains the live board and accepts groups from actual receipts
   and independent closure. Keep the dirty primary checkout and COORD lock, other
   workers, their branches and their evidence intact.

## Acceptance remains scoped

The software denominator remains 108 groups across T00–T07 and T19; the 70
unactivated research groups are separate. The current goal snapshot records
29 locally accepted groups on their original exact sources. An aggregate source
change needs the applicable fresh identities, controls and review before those
results can qualify that new source. A missing required capability remains incomplete.

D1/G1/RS known-negative behavior, native identity binding, physical/laboratory,
art and owner obligations, and engineering specification section 19 remain in
force. Software publication or a passing rejection test does not qualify a
physical design. Final 1.0 completion requires the actual remaining evidence and
authorizations; no final release or manufacturing promotion is implied here.
