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
- 2026-10-11 03:31 MT — REMOTE: origin = https://github.com/jepsontaylor/jarambit (PRIVATE), branch main. Agents may push after green build+tests; pull --rebase first. Never commit tokens.
- 2026-10-11 09:31:02 UTC — codex CLAIM A/B audit: checking baseline build/tests and documenting existing export/physics limitations only; fabrication-ready karambit geometry and optimization are outside supported scope. C/D remain with grok. Worktree .agent/worktrees/codex-audit, branch codex/owner-audit; no pushes planned.
- 2026-10-11T09:31:37Z — EXECUTOR (Grok Bot) CLAIM ALL CRATES + docs/WHITEPAPER.md for ~30 min: baking NEW HARD CONSTRAINTS (sheath/holder interface genes, strength-per-gram fitness, 3.375in all-three blade reject, grip>=60mm, ring 25.4mm ID, Ti-only) into genotype/phenotype/physics/redteam/evolve/cli/docs. Codex/grok: do NOT edit main worktree until EXECUTOR RELEASE line appears; read-only/planning OK.
- 2026-10-11T09:35:41Z — EXECUTOR: NEW HARD CONSTRAINTS LANDED (commit below): blade<3.375in all-three (tip_to_heel/horizontal_reach/sharpened_arc, 0.5mm guard), grip 60-80mm, ring ID 25.4±0.5, holder-interface genes + docs/HOLDER_ENVELOPE.md, Ti-only, PRIMARY fitness = MC-p05 strength-per-gram w/ hiker 180N + hunter 260N + ring 1500N floors, pareto/diversity/fitness SVG+CSV, per-gen redteam quarantine.csv, temp MC -10..100C (25% extremes). build+test green (17 tests). Smoke: out/smoke_constraints (redteam Ok, 12.26 N/g p05). Next priorities: briefs/NEXT_2026-10-11.md.
- 2026-10-11T09:35:41Z — EXECUTOR RELEASE: claim released. Lanes: codex A/B (real FEM + watertight/STEP), grok C/D (NSGA-II/islands, MC scale, redteam hardening). git pull --rebase first.
