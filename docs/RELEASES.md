# RELEASES / CHANGELOG — jarambit (author Jepson Taylor)

Policy: major wave N ⇒ `0.N.0`, git tag `v0.N.0`, entry here, WHITEPAPER header bump. Sub-experiments (Wave N.1, N.2 …) ⇒ `docs/WAVE_LOG.md` only (no bump, no tag). `-dev` while a wave is flying; the tag is cut only when that wave's pack (plates + solids) lands.

## 0.27.0-dev — 2026-10-12 (current, NOT tagged)
- Repo reorganisation: `TECHNOLOGY_MAP.md`, role dirs (`genotype/ phenotype/ fem/ monte_carlo/ evolve/ metrics/ cli/`) with READMEs pointing into unchanged `crates/`; README per crate; `ops/README.md`, `docs/README.md`.
- GLOBAL metric G1 locked (`docs/GLOBAL_METRIC.md`, `metrics/global_metric.py`); wired into `ops/wave_figures/make_d1_plate.py` plate titles (G + mass g + version) and index JSON.
- WHITEPAPER restructured into technology callouts with CAD + FEM figures + metrics + version (waves 20–25 filled; 26/27 placeholders).
- Versioning: `docs/VERSION`, this file, `docs/WAVE_LOG.md`; CI `version-check` workflow.
- No solver/hot-path changes. Nothing promoted.

## Planned: v0.27.0 — when the wave27 pack lands (solids complete)
Checklist: set `docs/VERSION` to `0.27.0`; WHITEPAPER header `Version 0.27.0 — <date>`; fill wave26/27 placeholders; add entry here; `git tag -a v0.27.0 -m "wave27 pack"`; push tag (CI version-check verifies VERSION == tag == paper header).

## v0.1.0-g3neckrail — 2026-10-11 (existing tag)
Frozen g3_neckrail paper on branch `release/v0.1.0` (`docs/WHITEPAPER_g3_neckrail.md`). Provisional; not promoted.

## Retro-assigned (no tags): wave N ↔ 0.N.0 for waves 1–26 — see `docs/WAVE_LOG.md`.
