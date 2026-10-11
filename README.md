# jarambit

Rust workspace for intelligence-designed + Monte Carlo evolution of **SWITCHBACK-class titanium hiking/utility karambits**.

Invariants (red-team enforced): fixed blade · finger ring · curved blade · double-edged, both edges serrated · 0.1 mm thickness precision · flat brand pad · single connected solid.

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
Outputs: `history.csv`, `best.stl`, `best.step`, `results.md`.

Coordination: see `COORD.md`. Paper: `docs/WHITEPAPER.md`.
