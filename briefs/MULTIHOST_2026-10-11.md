# MULTI-HOST compute plan (owner directive via executor, 2026-10-11 ~10:25Z) — READ

Jepson: use ALL spare CPU on xbabe1 + xbabe2 + xbabe3 for MC + NSGA-II/island GA; FEM stays with grok on xbabe2.
GPUs: NOT used (all three idle; flywheel may claim them any time). Never kill/renice/SIGSTOP anyone else's PIDs.

## Hosts (inventory 10:15Z)
| host | access | cores | baseline load | RAM free | jarambit allocation |
|---|---|---|---|---|---|
| xbabe2 | ssh -p 6969 (this box) | 128 (64C/128T 3995WX) | ~12 (jopedime/tabpfn/agents) | ~44 GB avail | 6 procs x 16 thr (islands A, seeds 1001-1006; ~77 cores actually used) + grok FEM/cargo (CARGO_BUILD_JOBS=16) |
| xbabe3 | ssh -p 6970 | 128 | ~0.3 (+3 qemu CI VMs, -smp 8 each) | ~89 GB | 7 x 16 (islands B 2001-2003,2007 @ mc 10k; LARGE MC 2004-2006 @ mc 50k; ~93 cores used) |
| xbabe1 | from xbabe2: `ssh xbabe1` (LAN 192.168.68.86) | 128 | ~1 (chrome renderers) | ~42 GB | 7 x 16 (MC batch C, seeds 3001-3007; ~92 cores used) |

Thread cap: xbabe2 raised 48 -> 64 for jarambit MC (nice 19); xbabe1/xbabe3 up to 96 total. Set per process with
`JARAMBIT_MAX_THREADS=<n> --threads <n>` (branch grokbot/multihost, commit a9e62a8; default cap still 48).

## Why many 16-thread processes instead of one 120-thread process
Measured on xbabe2: one process was FLAT in wall time from 8 -> 64 threads (glibc malloc: sys 120 s vs user 36 s at 32 thr,
from per-sample Phenotype allocation + per-candidate thread spawn). mimalloc fixed most of it (t=32 2.2 s vs 5.9 s);
>32 thr/process still regresses (sys time from per-candidate thread spawn). So: 16 thr/process, many processes = partitioned islands.
Follow-up for lane C (grok): persistent worker pool in monte_carlo::run_cols (spawn once, reuse) and/or reuse Phenotype buffers -> lets one process scale past 32.

## Contention / safety
- JopeDime cpu_safety_guard runs on ALL THREE hosts: SIGSTOPs the JopeDime campaign when 30 s host CPU avg >= 88 %, resumes <= 80 %.
  We must stay under it, so each host also runs `ops/yield_guard.sh` (screen `jarambit_yield_guard`): pauses ONLY our jarambit
  binaries at >= 82 % host CPU, resumes at <= 72 %. Log: ~/jarambit_yield.log.
- All jarambit jobs run nice 19. Outputs small (<5 MB each).

## Run mh1 (started ~10:23Z)
`ops/multihost_launch.sh <tag> mh1 16 "<seed:mc> ..."` -> 60 gens, pop 48/island, 2 islands/proc, migrate every 5, checkpointed (`--resume` supported).
Outputs: xbabe2 /home/ubuntu/jarambit/out/mh1/xbabe2_s*; xbabe3 & xbabe1 ~/jarambit/out/mh1/<host>_s*.
Collect to xbabe2: `rsync -a xbabe3:jarambit/out/mh1/ out/mh1/` style (from xbabe2: xbabe1 via `ssh xbabe1`; xbabe3 via -p 6970 public addr or LAN), then merge pareto.csv across all 14 island groups (non-dominated filter on strength_n vs mass_g, keep p05_spg primary).
Cross-host migration is NOT wired yet (islands are independent across hosts); next step: periodic exchange of best genotypes via checkpoint files.

Strength floors FIRM: hiker 180 N / hunter 260 N / ring pull 1500 N. Utility/hiking only. No manufacturers/external contact.

## Status 10:24Z
Host CPU 30s avg (JopeDime guard state): xbabe3 69%, xbabe2 64%, xbabe1 71% — all under 82/88; no pauses. GPUs untouched (0%, 1-9 MiB). ETA: mc10k procs ~25 min for 60 gens; mc50k (xbabe3 2004-2006) ~2 h.

## mh2 (after FEM, do not kill mh1)
`grokbot/multihost` (a9e62a8: thread cap + mimalloc) is on main. Plate FEM is a Kirchhoff check, not a per-sample solve. mh2 sets `JARAMBIT_FEM=1` on the same launch script: one nominal 20 °C plate solve per candidate, beam-surrogate MC knockdown, floors still 180/260/1500 N. `monte_carlo::run_cols` reuses a process-lifetime worker pool. Launch a host only after that host's mh1 binaries have exited, so the 82% yield guard does not SIGSTOP mh1. Same seed map as mh1. Remote trees were copied without `.git`; update them by rsync of source, then a small release build. Do not restart mh1.
