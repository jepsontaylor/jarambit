# ops/ — CI, wave reports, packers

| path | purpose |
|---|---|
| `ops/ci/d1_smoke.py` | D1 smoke check used by `.github/workflows/d1-gates.yml` |
| `ops/ci/version_check.py` | VERSION ↔ git tag ↔ WHITEPAPER header consistency (`.github/workflows/version-check.yml`) |
| `ops/wave_figures/make_d1_plate.py` | D1 wave FEM plates — title carries **G + mass g + version** (via `metrics/global_metric.py`) |
| `ops/wave_figures/make_crescent_plate.py`, `make_lattice_plate.py`, `make_wave_figs.py` | legacy/lane plates (not G-wired yet) |
| `ops/wave_reports/` | per-wave report pack (`make_wave_report.py`, hooks, watchers) |
| `ops/multihost_launch.sh`, `start_*.sh`, `yield_guard.sh` | multihost launch + guards |

Inputs: `out/<run>/` from `cli`. Outputs: `docs/wave*_diversity/plates*/`, `docs/wave_reports/`. Feeds G: plates are where G is computed and printed.
- `multihost/`: multi-host crescent wave launcher + certification collector (PR-0.30.0b).
