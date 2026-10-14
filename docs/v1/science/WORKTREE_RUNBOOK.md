# Worktree, screen, and handoff runbook

The plan is ready for execution; only the planning worktree and an owned baseline-audit screen were created during this study. Do not interpret proposed packet worktrees as already running agents. No PR, merge, release tag, physical experiment, or large evolution campaign was launched.

The [test upgrade supplement](tests/TEST_UPGRADE_PLAN.md) adds internal T00–T19 acceptance work to existing S owners. Use its declared disjoint scopes and phase limits in addition to this runbook. T04's S05/S06 shared writer stays sequential; T05's S08 binding phase waits for parent completion; T08 waits for T06. Required contracts and inherited nineteen regressions remain mandatory when research branches are deferred. The planning branch's frozen audit remains historical; new execution starts from reconciled current origin/main.

## 1. Current owned artifacts

- Host: xbabe2, SSH alias already works with batch authentication.
- Base: `97af59cf14299af583b344aeaefb4594d089465a`.
- Planning branch: `codex/science-v1-plan`.
- Planning worktree: `/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-plan`.
- Owned screen: `jr_v1_science_audit` (session exits when audit finishes).
- Audit scratch: that worktree's `.agent/science-v1-study/`.
- Private Cargo target: that worktree's `target/science-audit/`.
- Local review package: `/Users/bentaylor/Documents/ChatGPT/jarambit/docs/v1/science/`.

Keep the planning worktree until the executor has collected its documentation commit. Use ordinary remote Git commands to manage these SSH-host worktrees; Codex's local managed-worktree tools target the local Mac checkout, not xbabe2. Do not archive unrelated worktrees or reuse their build/output directories.

## 2. Preflight and ownership

All shell commands from the Mac start with `rtk`. xbabe2 has no rtk binary; `rtk proxy ssh` transports the remote commands without altering scientific output.

```bash
rtk proxy ssh -o BatchMode=yes xbabe2 'git -C /home/ubuntu/jarambit status --short --branch'
rtk proxy ssh -o BatchMode=yes xbabe2 'git -C /home/ubuntu/jarambit worktree list --porcelain'
rtk proxy ssh -o BatchMode=yes xbabe2 'screen -ls'
rtk proxy ssh -o BatchMode=yes xbabe2 'head -22 /home/ubuntu/jarambit/COORD.md; tail -30 /home/ubuntu/jarambit/COORD.md'
rtk proxy ssh -o BatchMode=yes xbabe2 'uptime; free -h; df -h /; nproc'
rtk proxy ssh -o BatchMode=yes xbabe2 'git -C /home/ubuntu/jarambit fetch origin; git -C /home/ubuntu/jarambit rev-parse origin/main'
```

These are inspection commands, not an instruction to clean/reset/pull main. Main had uncommitted COORD changes and a lock file at study start. Preserve them. Record the new exact base and its difference from the frozen study SHA; reevaluate any findings affected by intervening changes. Inspect any applicable new AGENTS.md before proceeding.

Claim a packet before editing. `COORD.md` latest instruction requires changes through the executor's PR flow. Put a scoped CLAIM in the isolated branch and packet receipt; hand that append-only entry to the executor. Never modify the shared dirty COORD file or send prompts/keystrokes into another worker's screen. PR opening and merge order remain with the existing executor, one PR at a time. Review uses the exact proposed head; prior green checks do not carry over after changes.

Claim shape:

```text
<UTC time> — SCIENCE Sxx CLAIM: owner <name>, branch <branch>, base <full SHA>,
worktree <absolute path>, allowlist <exact paths>, forbidden <shared paths>,
resource lease <CPU/RAM/GPU/expiry>, test plan <commands>, handoff <receipt path>.
```

## 3. Create integration and packet worktrees

Run only when names are absent and the ownership preflight is clear. Existing branch/worktree collision is a stop condition; inspect and reuse only if it belongs to this task. Never force-remove a checkout.

```bash
rtk proxy ssh xbabe2 'git -C /home/ubuntu/jarambit worktree add /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration -b codex/science-v1-integration origin/main'
rtk proxy ssh xbabe2 'git -C /home/ubuntu/jarambit worktree add /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s01 -b codex/science-v1-s01 codex/science-v1-integration'
```

Collect the plan into integration through an explicit reviewed documentation cherry-pick; compare the actual paths of that commit first. Worker S01 starts only after S00 interfaces/requirements policy are ready. Downstream workers start from the **integrated dependency commit**, not from a stale initial base. Example after S01 integration:

```bash
rtk proxy ssh xbabe2 'git -C /home/ubuntu/jarambit worktree add /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s02 -b codex/science-v1-s02 codex/science-v1-integration'
rtk proxy ssh xbabe2 'git -C /home/ubuntu/jarambit worktree add /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s04 -b codex/science-v1-s04 codex/science-v1-integration'
rtk proxy ssh xbabe2 'git -C /home/ubuntu/jarambit worktree add /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s05 -b codex/science-v1-s05 codex/science-v1-integration'
```

No speculative downstream worktree forest is needed. Create just the next dependency-ready wave; retain accepted commits/receipts before cleanup. Existing Git worktrees under main are not scratch space for this release.

## 4. Screen and resource admission

Start one heavy lane, initially four CPU slots, eight GiB RAM, no swap, nice 19, and native math pools of one. CARGO_BUILD_JOBS stays <=16 and project-wide xbabe2 evolution threads <=48; these caps do not authorize multiplying them across workers. Account for existing jobs before adding any concurrency. No GPU claim was obtained. xbabe1 stays drained. Optional xbabe3 requires fresh reachability/ownership/resource admission.

Validate user-bus access before launching a cap; the current render train has a known bus-environment integration defect. The user-bus socket was `/run/user/1000/bus` in this study. Derive UID/socket fresh rather than assuming 1000 forever.

```bash
rtk proxy ssh xbabe2 'env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus /home/ubuntu/bin/memcap 8G -- /usr/bin/true'
```

If this fails, keep the cap requirement and repair/record the environment; do not continue uncapped. A packet launch uses lowercase `screen -dmS` so the launcher returns immediately. Uppercase `-DmS` stays attached to the process lifetime and may keep SSH waiting.

The following concrete S01 example assumes its worker has created `.agent/science-s01/run_gate.py`, a Python process that executes its immutable job manifest with `subprocess.run(argv, shell=False)`, writes attempt-specific logs/receipt, and returns nonzero on any failed required command. The script itself is part of the packet's scratch orchestration, not a scientific evaluator. Inspect the manifest before launch. For an immediately runnable single gate, use:

```bash
rtk proxy ssh xbabe2 'cd /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s01 && mkdir -p .agent/science-s01 && screen -dmS jr_v1_s01_gate env PATH=/home/ubuntu/.cargo/bin:/home/ubuntu/bin:/usr/local/bin:/usr/bin:/bin XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus CARGO_BUILD_JOBS=4 CARGO_TARGET_DIR=/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s01/target/science-s01 JARAMBIT_MAX_THREADS=4 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/ubuntu/bin/memcap 8G -- nice -n 19 taskset -c 0-3 /bin/bash -c '\''cargo test --release --locked -p jarambit-evidence > .agent/science-s01/test.log 2>&1; rc=$?; printf "%s\n" "$rc" > .agent/science-s01/exit_code; exit "$rc"'\'''
```

CPU 0–3 here are an affinity bound, not exclusive reserved cores. Use the admitted CPU set when a lease allocates a different set. Receipt must include actual affinity/cgroup MemoryMax/MemorySwapMax, source/lock/toolchain/config hashes, command argv/environment, timestamps, exit code and output hashes. PATH and native math settings are operational metadata. Credentials are excluded from receipts.

Monitor own logs and status; screen disappearance is not proof of success:

```bash
rtk proxy ssh xbabe2 'screen -ls | rg "jr_v1_"'
rtk proxy ssh xbabe2 'tail -30 /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s01/.agent/science-s01/test.log'
rtk proxy ssh xbabe2 'cat /home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s01/.agent/science-s01/exit_code'
```

For the study screen, substitute `codex-science-v1-plan/.agent/science-v1-study/receipt.json` and its named log files. Write an explicit FAILED receipt if launcher/script dies before producing one. Do not infer success from an old DONE marker; every run uses a fresh attempt directory and rejects reuse by name.

If shared load/memory/disk pressure rises, stop admitting new work and checkpoint/pause only this task's owned jobs. Never kill/renice other processes. Stop only an owned screen after verifying its owner, argv, cgroup and output path; retain its logs. Keep per-packet output under 5 GB and do not remove raw scientific evidence to disguise failures. Source/data/control files are not janitor targets.

## 5. Disjoint execution waves

| Wave | Ready packets | Write separation / gate |
|---|---|---|
| 0 | S00, then S01 | Integrator freezes interfaces first; evidence/schema owner finishes before consumers. |
| 1 | S02 / S04 / S05 | fem_solid arithmetic vs MC+legacy evolve vs crescent qd/record. Only one heavy build initially; source scopes disjoint. |
| 2 | S03 / S06 / S07 / S13 | Report scripts vs current-engine replay vs elementary solver verification vs new material/lab pipeline. S06 waits S05; S07 waits S02; S13 waits schema release. Maximum three workers, no overlapping active write claims. |
| 3 | S08 | Serial CLI/FEM/integration owner. No parallel qd/record/CLI refactor. |
| 4 | S09 / S10 / S14 | Experiment scripts/results vs new core interfaces vs new qualification protocols; S14 follows S13. No worker registers crates/edits workspace files. |
| 5 | S11, then S12 | Evidence/splits ready; model and cache interface scopes released before performance changes. |
| Media | S15 | Existing render lane release required; integrate common claim reader and current render fixes. |
| Final | S16 | Exact-head integration, independent reconstruction/review, physical evidence and release gate reconciliation. |

No parallel packet may widen its allowlist without releasing its claim and getting an updated assignment. A test exposing another module's defect becomes an interface request, not an unannounced cross-scope edit. `WORK_PACKETS.json` scopes are contractual, not suggestions.

## 6. Packet receipts and integration

Required status states: planned, claimed, running, failed, dependency_blocked, ready_for_review, accepted, released. READY requires tests completed, no running writers, clean source status, exact tested commit, and a complete receipt. A running process or a green old test is not READY.

Receipt shape:

```json
{
  "schema": "jarambit.packet.receipt.v1",
  "packet": "S01",
  "owner": "assigned worker",
  "base_commit": "full hash",
  "tested_commit": "full hash",
  "worktree": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-s01",
  "scientific_input_hashes": {},
  "commands": [],
  "artifacts": [],
  "historical_status_changes": [],
  "remaining_dependencies": [],
  "status": "ready_for_review"
}
```

Place operational files in private `.agent/science-Sxx/<attempt>/`; commit small approved scientific records only in new evidence areas. Never commit credentials, caches, raw giant binaries or private host state. Save raw data in an owner-approved immutable store with hashes; preserve unsuccessful results too.

Worker verifies its diff against allowlist, commits exact paths, then reports exact SHA/receipt to the integrator through the authorized coordination channel. This plan does not authorize sending messages to unrelated Codex chats. Integrator checks dependencies, reviews code, cherry-picks exact commits, resolves shared-file changes serially, and reruns affected gates. Any changed source invalidates exact-head tests; rebase/cherry-pick receipts identify the final integrated SHA.

COORD updates preserve all earlier entries. No blanket `git add -A`, no force push, no main reset, no unstaged user edits bundled into a packet. The existing executor owns PR opening/review sequencing. Release tags and publication follow a concrete reviewed release manifest and owner authorization.

## 7. Cleanup and restart

Archive accepted packet commit, receipt and output manifest before removing its owned screen/worktree. Keep plan branch and small receipts. Avoid deleting ignored scientific outputs without separately preserving required evidence. The Mac's copied review package remains clickable even though xbabe2 paths are remote.

Restart packet from its integrated dependency SHA, validate input hashes, create a new attempt directory, and resume only through the manifest-bound checkpoint contract. Source/evaluator/requirements/descriptor changes require an explicit fork and reevaluation. Unsupported old logs/checkpoints remain historical; migration cannot manufacture missing identities or ancestry.

## 8. Final handoff checklist

- Exact tested and integrated commit; clean diff within ownership; all required command exit codes and actual skips.
- Frozen requirement/scenario/evaluator/observable/material identities; current candidate and historical mappings.
- Fresh reference reconstruction and current-engine replay; comparison protocol, all run results, failures and uncertainty.
- Historical claim-status changes, W84/V4 disposition, migration/rollback commands, and current unknowns.
- Physical test/inspection/handling scope and independent review; no inferred manufacturing approval.
- Resource/screen/worktree inventory with no orphaned owned jobs; no changes to other workers.
- READY handoff to the existing executor; one PR at a time and exact-head independent review.
