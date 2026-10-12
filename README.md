<div align="center">

# 🗡️ jarambit

### Intelligence-designed titanium utility karambits — evolved, FEM-verified, Monte-Carlo-robust

[![version](https://img.shields.io/badge/version-v0.27.0-ff6f00?style=for-the-badge)](https://github.com/jepsontaylor/jarambit/releases/tag/v0.27.0)
[![G1](https://img.shields.io/badge/G1-0.9805-7b1fa2?style=for-the-badge)](docs/GLOBAL_METRIC.md)
[![mass](https://img.shields.io/badge/mass-84.80%20g-00897b?style=for-the-badge)](docs/PROVISIONAL.md)
[![tip×SPG](https://img.shields.io/badge/tip%C3%97SPG-6.362-1565c0?style=for-the-badge)](docs/WHITEPAPER.md)
[![status](https://img.shields.io/badge/status-engineering%20provisional%20%C2%B7%20not%20promoted-c62828?style=for-the-badge)](docs/PROVISIONAL.md)

**Provisional `g3_tip+00_t60_tt3` — G1 0.9805 · 84.80 g · tip SF 1.534 × SPG 4.147 = 6.362 · ring 25.46 mm · Ti-6Al-4V 6.0 mm · all hard gates PASS**

📄 [White paper](docs/WHITEPAPER.md) · ⚖️ [Patent draft (not filed)](docs/PATENT_DRAFT.md) · 📦 [Release v0.27.0](https://github.com/jepsontaylor/jarambit/releases/tag/v0.27.0) · 🗺️ [Technology map](TECHNOLOGY_MAP.md)

<img src="docs/figures/whitepaper/wave27_g3_tip+00_t60_tt3_STEP_3D.png" width="88%" alt="3D CAD render of g3_tip+00_t60_tt3 (watertight STEP)"/>

<img src="docs/figures/whitepaper/wave27_g3_tip+00_t60_tt3_W27HARDPASS_SPG4p15_wgt84p8g_D1_FEM_metrics.png" width="88%" alt="wave27 D1 FEM colormap + metrics plate for g3_tip+00_t60_tt3"/>

*Top: watertight STEP solid (colour = position along the blade). Bottom: D1 plate-FEM stress colormap + metrics, solid-tip submodel SF 1.534.*

</div>

---

| | |
|---|---|
| 🧬 **Genotype** | 40 outline control points + ~100 feature genes (stock/tip law, rails, ring channels), red-team validators reject — never penalise |
| 🧊 **Phenotype** | outline + thickness field → watertight STL + `MANIFOLD_SOLID_BREP` STEP |
| 🔥 **FEM** | DKT plate screen (828 MPa joint, thin+hot) + 92k-tet solid tip submodel |
| 🎲 **Monte Carlo** | tolerances × −10…100 °C × cut media, p05 strength-per-gram |
| 🧭 **Evolution** | NSGA-II islands, novelty, graft arms; one locked GLOBAL metric **G1** across waves |

> No design is promoted to manufacturing. 828 MPa is a provisional screening yield; seq ≥ 1.2 is still soft; human aesthetic sign-off pending.

## Engine

Rust workspace for intelligence-designed + Monte Carlo evolution of **SWITCHBACK-class titanium hiking/utility karambits**.

Invariants (red-team enforced, see docs/WHITEPAPER.md §III-A): blade **≥ 3.375 in (85.725 mm, +0.5 mm guard) on tip-to-heel AND horizontal reach AND sharpened-edge arc; sharpened edge ≤ 4.0 in** · grip ≥ 60 mm (60–80) · finger ring 25.4 mm ID · curved blade · double-edged, both edges serrated · single connected solid · flat brand pad · 0.1 mm thickness precision · titanium only · sheath/holder pop-in interface (docs/HOLDER_ENVELOPE.md).

**Fitness = MC-p05 strength-per-gram (N/g) subject to hiker + hunter strength floors** — not strength alone.

**Version:** see `docs/VERSION` (0.27.0). **Map:** `TECHNOLOGY_MAP.md`. **Global metric:** `docs/GLOBAL_METRIC.md`. **Status:** `STATUS.md`.

## Crates
| crate | role |
|---|---|
| `genotype` | 20-gene vector + titanium grade, bounds, mutate/crossover, deterministic RNG |
| `phenotype` | outline and ring → watertight STL and faceted `MANIFOLD_SOLID_BREP` STEP |
| `physics` | beam surrogate for Monte Carlo; Kirchhoff plate (DKT + membrane) as a separate check |
| `monte_carlo` | exact-n tolerance cloud, thread-stable seeds, cut-media mix, p05 |
| `evolve` | NSGA-II with islands, migration, checkpoint/resume; primary objective is p05 strength-per-gram |
| `redteam` | hooked planform, double serrations, connected solid, holder insertion/draw, blade limits |
| `docs` | report tables for `docs/WHITEPAPER.md` |
| `cli` | `jarambit` binary |

## Run
```bash
cargo build --release
./target/release/jarambit --gens 20 --pop 16 --islands 4 --mc 10000 --threads 16 --seed 42 --out out/nsga20
cargo test --release
```
`--threads` is capped by `JARAMBIT_MAX_THREADS` (default 48). `--pop` is per island. `--resume` continues from `{out}/checkpoint.txt`.

Outputs: `history.csv`, `pareto.csv/svg`, `diversity.svg`, `fitness.svg`, `quarantine.csv`, `best.stl/step/svg`, `best_report.md`, `results.md`, `checkpoint.txt`. The report's strength is the beam surrogate; `plate FEM` is one 20 °C solve of the winner. The search uses that plate level by default (`JARAMBIT_FEM=0` keeps the uncalibrated beam surrogate). The sample loop stays the beam model and only supplies the knockdown. Do not `--resume` a surrogate checkpoint with plate fitness, or the reverse.

A 60-generation multi-host search (`mh1`, 20 island pairs, 10k or 50k samples) was started on 2026-10-11. See `briefs/MULTIHOST_2026-10-11.md` and `COORD.md` before launching another large run on the same hosts.

Coordination: see `COORD.md`. Paper: `docs/WHITEPAPER.md`.
