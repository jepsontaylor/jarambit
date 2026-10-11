# jarambit

Rust workspace for intelligence-designed + Monte Carlo evolution of **SWITCHBACK-class titanium hiking/utility karambits**.

Invariants (red-team enforced, see docs/WHITEPAPER.md §III-A): blade **< 3.375 in on tip-to-heel AND horizontal reach AND sharpened-edge arc** · grip ≥ 60 mm (60–80) · finger ring 25.4 mm ID · curved blade · double-edged, both edges serrated · single connected solid · flat brand pad · 0.1 mm thickness precision · titanium only · sheath/holder pop-in interface (docs/HOLDER_ENVELOPE.md).

**Fitness = MC-p05 strength-per-gram (N/g) subject to hiker + hunter strength floors** — not strength alone.

## Crates
| crate | role |
|---|---|
| `genotype` | 14-gene parameter vector, bounds, mutate/crossover, deterministic RNG |
| `phenotype` | genotype → outline/ring polygon → STL, STEP (stub) |
| `physics` | Ti-6Al-4V surrogate: bending SF, sharpness, serration, ergonomics (FEM TODO) |
| `monte_carlo` | tolerance MC, multithreaded, p05 robust score |
| `evolve` | (μ+λ) evolution with red-team hard constraint |
| `redteam` | rejects non-karambit / disconnected / non-double-serrated / unsafe |
| `docs` | report tables for `docs/WHITEPAPER.md` |
| `cli` | `jarambit` binary |

## Run
```bash
cargo build --release
./target/release/jarambit --gens 20 --pop 64 --mc 512 --threads 32 --out out/run1
cargo test --release
```
Outputs: `history.csv`, `pareto.csv/svg`, `diversity.svg`, `fitness.svg`, `quarantine.csv`, `best.stl/step/svg`, `best_report.md`, `results.md`.

Coordination: see `COORD.md`. Paper: `docs/WHITEPAPER.md`.
