# docs/ — paper, versioning, logs, calibration

| file | purpose |
|---|---|
| `WHITEPAPER.md` | living paper (author Jepson Taylor), header carries version + date |
| `WHITEPAPER_g3_neckrail.md` | frozen v0.1.0 g3_neckrail paper (branch `release/v0.1.0`, tag `v0.1.0-g3neckrail`) — kept, not superseded |
| `GLOBAL_METRIC.md` | locked definition of G |
| `VERSION` | semver of the research state (`0.27.0-dev`) |
| `RELEASES.md` | changelog per major wave / tag |
| `WAVE_LOG.md` | every wave and sub-experiment (Wave N.1 …) — no bump/tag for sub-experiments |
| `WAVE_FIGURE_TEMPLATE.md` | plate layout contract |
| `CALIBRATION.md`, `calibration/` | FEM calibration + convergence |
| `HOLDER_ENVELOPE.md` | holder/sheath envelope |
| `figures/whitepaper/` | best-G plates + 3D CAD renders used by the paper |

Feeds G: GLOBAL_METRIC.md is the authority; the paper Methods section quotes it.
