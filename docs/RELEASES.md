# RELEASES / CHANGELOG — jarambit (author Jepson Taylor)

Policy: major wave N ⇒ `0.N.0`, git tag `v0.N.0`, entry here, WHITEPAPER header bump. Sub-experiments (Wave N.1, N.2 …) ⇒ `docs/WAVE_LOG.md` only (no bump, no tag). `-dev` while a wave is flying; the tag is cut only when that wave's pack (plates + solids) lands.

## Unreleased (v0.28 milestone: truthful status + typed metrics — docs/v1/jarambit_v1_roadmap.json)
- PR-0.28.1: G1 completeness contract. `metrics/global_metric.py` no longer maps missing/null/NaN/inf/bool/malformed/out-of-range inputs to 0: the record is `INCOMPLETE`, `global_G` returns `G=None`, `title_tag` prints `G INCOMPLETE` (never raises). `provisional` (G*) is now only "tip from a screen"; completeness is `terms['status']`. Arithmetic for complete records is unchanged (42 wave27 index records equal the v0.27.0 formula to 1e-9). Tests: `metrics/tests/` (wired into version-check CI). v1 plan docs added under `docs/v1/`.
- Policy note: the v0.28.0 tag is now cut at the close of the v0.28 roadmap milestone (evidence/reporting), superseding the wave-gated rule below.

## v0.27.0 — 2026-10-12 (tagged; wave27 major)
- Wave27 pack landed: tip outline × t_stock 5.8/6.0 × t_tip +0/+0.3 on g3_neckrail + a0_c02fit_ref (24 arms) plus b–e sub-arms. Plates `docs/wave27_diversity/plates/` (+ `plates_e/`), tables `w27_sf.md`/`w27e_sf.md`, solids pointers `docs/wave27_diversity/SOLIDS.md`.
- **Engineering provisional RETITLED → `g3_tip+00_t60_tt3`**: G1 0.9805, solid tip SF 1.534, SPG 4.147, tip×SPG 6.362, 84.80 g, ring 25.46 mm, HARD PASS. Previous `g3_tip+00_t60_tt0` (g3_neckrail, 6.340 @ 84.59 g) is history. **Not promoted to manufacturing.**
- WHITEPAPER v0.27.0: wave27 callout filled (3D CAD `wave27_g3_tip+00_t60_tt3_STEP_3D.png`, FEM plate `wave27_g3_tip+00_t60_tt3_W27HARDPASS_SPG4p15_wgt84p8g_D1_FEM_metrics.png`, G1 table).
- Pareto: no ≤ 82 g @ tip×SPG ≥ 6 HARD PASS on tip arms; mass king remains a0_c02fit_ref class (~81.4 g / ~5.58). seq soft.
- Gate for v0.28.0: G1 > 0.9805 (hard PASS) OR ≤ 82 g @ tip×SPG ≥ 6 hard PASS.

## 0.27.0-dev — 2026-10-12 (superseded by v0.27.0)
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
