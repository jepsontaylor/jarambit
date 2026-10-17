# D1 runner capacity and timeout proposal

Local proposal from main `a8a7de426c4eb171457787c1d8876d58f2355f0f`;
not deployed or benchmarked on the loaded host. This concerns CI scheduling
and elapsed time only.

## Observed execution

Times below come from GitHub job timestamps and Cargo's timestamped logs.
The first cancellation ran the preceding main, `2539448`, rather than `a8a7de4`.
The successful comparison is PR #93, `2d36aa4`, whose tree matches `a8a7de4`.

| Run / attempt | Runner | Compile within workspace step | Workspace step | Job outcome |
| --- | --- | --- | --- | --- |
| [39050537697 / 1](https://github.com/neverhuman/jarambit/actions/runs/39050537697/attempts/1) | jarambit-xbabe3 | 11m09s | 44m25s, incomplete | cancelled at 45 minutes |
| [39055949400 / 1](https://github.com/neverhuman/jarambit/actions/runs/39055949400/attempts/1) | jarambit-xbabe3 | 10m40s | 44m23s, incomplete | cancelled at 45 minutes |
| [39050872320 / 2](https://github.com/neverhuman/jarambit/actions/runs/39050872320/attempts/2) | jarambit-xbabe2 | 3m13s | 25m52s, complete | success, total 30m18s |

Both cancellations happened inside the workspace Cargo step. Clippy, the
explicit owner-lock tests, D1 smoke and export checks were all skipped by the
failed step. On the successful run those four steps took 4s, 55s, 132s and 41s.
All three cache restores reported full matches; workspace crates were still
compiled. The logs do not indicate a missing registry index in these jobs.

The dominant test was
`battery::tests::export_web_data_native_emits_bundle_and_meshes`: about 17m42s
on xbabe2, still unfinished after at least 30m36s and 31m40s on xbabe3.
These lower bounds use its "running for over 60 seconds" log timestamp minus
60 seconds through cancellation, not a claim of its final runtime.
`battery::tests::score_cad_native_evaluates_w282_and_c10a_in_rust` took about
4m33s on xbabe2 versus 15m49s and 9m58s on xbabe3, by the same start-time
inference. Tests overlap under the two-thread harness; do not add their times.
The 38-test library executable never finished in either cancelled job; it
finished in 17m41.60s on xbabe2. Later workspace integration tests were never
reached on xbabe3.

## Resource evidence and limits of attribution

All three logs reported the same actual wrapper enforcement: affinity CPUs
`0,1,2,3`, nice 19, 8 GiB memory, zero swap, and one thread per native pool.
The workspace command already sets `--test-threads=2`; the wrapper also bounds
Cargo build jobs to four. Adding that existing test cap again will not help.

A read-only xbabe3 snapshot at 18:59:15 UTC on 2026-10-17 found nine Blender
processes associated with `~/jr_rc11_x7`, all nice 19, all allowed on CPUs
`0,1,2,3` as well as their SMT siblings `64,65,66,67`. The runner listener had
the same allowed CPU set as those renders. Host load averages were about
87.74 / 82.45 / 67.36. In a one-second sample the four CI CPUs spent about
88–98% of their ticks in nice-priority work, with 0–9% idle.

This shows shared capacity, not CPU reservation. It supports contention as
a contributor but cannot attribute all historical slowdown to the currently
live render processes: those PIDs started after the first cancellation.
No runner, render, wave, affinity, service or process priority was changed.

## Proposed changes and follow-up

The local workflow patch sets a 90-minute overall ceiling and a 75-minute
workspace-step ceiling on exactly `jarambit-xbabe3`. Other runner names retain
a 45-minute workspace ceiling. The overall ceiling must be static because
GitHub permits the `runner` context in step timeout expressions, but not in
job timeout expressions; see the [context availability table](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability).
All later checks remain required. The outer ceiling also applies to other
runners; this patch does not retain their former 45-minute whole-job ceiling.

Bash `time` adds wall/user/system CPU seconds to completed workspace commands
without changing their exit status or test selection. The 75-minute allowance
is provisional headroom, not a measured completion bound or a speedup. It
needs a completed xbabe3 run before adoption can be considered validated.

For predictable throughput, prefer an owner-scheduled CPU reservation rather
than relying on a longer timeout indefinitely. Reserve four physical cores
per concurrent CI slot and exclude both SMT siblings from competing render
and wave workloads. On this host, one possible slot is physical cores whose
logical CPUs are `0–3,64–67`; check topology before applying it. Set the runner
service's inherited allowed CPUs to that slot and keep competing workloads
outside it. The existing wrapper selects four CPUs from inherited affinity
and can keep its current four-CPU, nice-19 and memory limits. Pinning only the
runner does not reserve capacity while other workloads can still use the
same cores. Multiple runner services also need distinct slots.

Do not change active renders or waves to test this proposal. After the owner
schedules the reservation, compare completed same-tree runs with the existing
two-thread harness and the added wall/CPU timings. Revisit timeout headroom
from that evidence. No test is skipped and no engineering threshold, genome
bound or design code changes in this proposal.

## Local validation

`actionlint` and ShellCheck pass. Neutral Cargo stubs exercised the proposed
workspace shell body with exit codes 0 and 37: both statuses propagated,
arguments and the run/attempt-specific temporary directory were preserved,
and wall/user/system timings appeared in both cases. A structural comparison
against `a8a7de4` confirmed that every other workflow control and command is
unchanged. These checks did not compile or run the engineering workspace.

Raw job logs, API metadata, the sanitized host snapshot, a timing summary and
the neutral check receipts are retained locally in
`.agent/worktrees/ci-runner-budget/target/ci-runner-budget/`. They are CI
diagnostics, not design-certification evidence. The live rerun
`39055949400`, attempt 2, was still in its workspace step on
`jarambit-xbabe2-2` when this proposal was prepared; it is not reported green.
