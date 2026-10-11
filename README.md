# jarambit

Rust workspace for intelligence-designed + Monte Carlo evolution of **SWITCHBACK-class titanium hiking/utility karambits**.

Invariants (red-team enforced, see docs/WHITEPAPER.md §III-A): blade **≥ 3.375 in (85.725 mm, +0.5 mm guard) on tip-to-heel AND horizontal reach AND sharpened-edge arc; sharpened edge ≤ 4.0 in** · grip ≥ 60 mm (60–80) · finger ring 25.4 mm ID · curved blade · double-edged, both edges serrated · single connected solid · flat brand pad · 0.1 mm thickness precision · titanium only · sheath/holder pop-in interface (docs/HOLDER_ENVELOPE.md).

**Fitness = MC-p05 strength-per-gram (N/g) subject to hiker + hunter strength floors** — not strength alone.

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
