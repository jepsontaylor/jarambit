# COORD.md — jarambit shared coordination board

Agents: `jarambit_codex` (Codex) and `jarambit_grok` (Grok), screens on xbabe2.
Append-only log at bottom. Claim a lane before editing; keep claims short-lived.

## Hard rules
- SWITCHBACK-class **titanium hiking/utility karambit ONLY**. Not a combat/tactical design; no combat framing anywhere (code, docs, commit msgs).
- Invariants (enforced by `crates/redteam`, never weaken): fixed blade; finger ring; **curved** blade (no straight); **double-edged with BOTH edges serrated**; thickness quantised to 0.1 mm; flat brand pad on handle; single **connected** solid (genus-1: exactly one hole = ring).
- Rust-first. No Python in the hot path (Python OK only for offline plotting).
- Do NOT contact manufacturers or any external party. Do NOT push secrets.
- Shared box: xbabe2 has flywheel/JopeDime/tabpfn jobs. **Never kill or renice others' processes.** Cap `--threads` ≤ 48 on xbabe2; use `CARGO_BUILD_JOBS=16`. Single RTX 3090 is currently idle but may be claimed by flywheel — any GPU work must be optional and yield. xbabe3 (port 6970, 128 cores, idle 3090) is spare compute.
- Disk: / is 87% full (~970 GB free). Keep outputs < 5 GB; no checkpoint hoarding.

## Lanes
| Lane | Owner | Scope |
|---|---|---|
| A geometry | codex | phenotype: true B-rep/STEP (truck crate), real tip/handle blending, edge bevel geometry, STL caps (triangulate with earcut) |
| B physics | codex | physics: 2D/3D linear-elastic FEM (tet/tri mesh), tip-load + ring-load cases, Ti-6Al-4V, edge-retention proxy |
| C MC/evolve | grok | monte_carlo + evolve: tolerance MC at scale, NSGA-II multi-objective, checkpointed runs, xbabe3 offload |
| D redteam/docs | grok | redteam rules + adversarial tests; docs/WHITEPAPER.md (IEEE 6–8 pp), README, figures |

## Log
- 2026-10-11 03:4x MT — scaffold by Grok Bot executor: 8-crate workspace compiles (`cargo build --release` OK), stub MC + genotype→outline→STL/STEP-stub + 4-gen evolve smoke run passes redteam.
