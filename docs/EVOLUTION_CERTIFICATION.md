# Genome evolution and independent certification

Run from a source checkout with the pinned Rust toolchain, Docker, and a Python environment containing NumPy, SciPy, scikit-fem, PyAMG and cadquery-ocp. The DOLFINx runtime is `ghcr.io/fenics/dolfinx/dolfinx:v0.9.0`; pull it before starting a wave. The evaluator records its resolved image ID and uses that exact image for the solve.

```bash
export JARAMBIT_SOLVER_PYTHON=/path/to/solver-environment/bin/python
./evolve.sh --rounds 2 --candidates-per-round 12 --top-k-certify 2 \
  --threads 4 --seed 20261017 --out-dir out/my-wave
```

`jarambit auto-evolve` accepts the same flags. `--top-k-certify` accepts an optional count; `--certify-top N` remains an alias. The wrapper builds the executable and the export, convergence and support probes. A direct CLI invocation also checks their Cargo fingerprints. `--seeds` selects comma-separated evolved genome CSVs; invalid seed input fails without importing an external CAD design.

The coarse FEM screen ranks valid genomes by structural shortfalls, with mass as a tie-breaker. It retains failing designs for improvement. Each round records all generated genome rows and the provisional screen observations. The top-k assessment runs the standard `score_cad.py` / `evaluate_cad_candidate.py` path automatically.

The export constructs cutting faces from the existing apex and edge-angle genes, including the serrated boundaries. The integral bore collar uses the existing radial ring-wall gene: roll radius is `ring_wall / 4`, straight axial bearing is `2 * ring_wall`, and a planar land joins the roll to the body. STEP contains analytic toroidal rolls on both faces and a cylindrical bearing, along with a proper representation context and millimetre units. The STL is a tessellation of those circular surfaces. The measured radius is obtained from the actual exported geometry, and the standard evaluator independently reads and validates the STEP with OpenCascade. These are geometry changes; no ring-width strength or fatigue multiplier is applied.

The saved CAD top surface, with full-precision vertex heights, supplies the solid-tip submodel. Refinement interpolates those facets instead of sampling the display thickness raster. Scikit-fem P2 and DOLFINx solve the same saved fine mesh, with the existing load, support, refinement and comparison settings. Both raw observations, primary convergence data, DOLFINx settings, mesh, export surface, STEP/STL and runtime identity are retained. A missing runtime or failed solve remains unverified.

Each attempt lives under `by-content/<certificate_identity>/attempt-<id>/`. The identity includes exact genome bits, numerical sources, requirements and the active geometry context. Labels identify files; they cannot authorize reuse. Catalog solid-tip results also require matching genome/model and D1 bindings, exact raw hashes, agreement derived from both raw observations, and the required solver metadata.

`leaderboard.json` distinguishes completed assessments, unverified attempts and qualified designs. A completed assessment may fail physical gates. `champion` is null when nothing qualifies. Qualification requires all engineering gates and the complete RS-v2 `all_hard` verdict; the battery pass count alone does not establish it. A successful process exit means the requested assessments completed; inspect `qualified_count` for qualification. An unavailable independent assessment causes a nonzero exit and a retained unverified report.

Requirements, thresholds and genome bounds are unchanged. Existing catalog JSONs remain historical observations for their recorded model; they are not re-issued for this changed geometry. Live catalog scoring withholds incompatible solid-tip evidence. See [committed pipeline evidence](../evidence/evolve_certifiable/) for the automatic run and the separate legal-genome geometry controls.
