# Genome evolution and independent certification

Run from a source checkout with the pinned Rust toolchain, Docker, and a Python environment containing NumPy, SciPy, scikit-fem, PyAMG and cadquery-ocp. The DOLFINx runtime is `ghcr.io/fenics/dolfinx/dolfinx@sha256:628f40dd62c7f37962ccadc5a745f23d52c56b2ac3ad9b9b6a86c567c07aa27b`; pull it before starting a wave. The evaluator records its resolved image ID and uses that exact image for the solve.

```bash
export JARAMBIT_SOLVER_PYTHON=/path/to/solver-environment/bin/python
./evolve.sh --rounds 2 --candidates-per-round 12 --top-k-certify 2 \
  --threads 4 --seed 20261017 --out-dir out/my-wave
```

`jarambit auto-evolve` accepts the same flags. `--top-k-certify` accepts an optional count; `--certify-top N` remains an alias. The wrapper builds the executable and the export, convergence and support probes. A direct CLI invocation also checks their Cargo fingerprints. `--seeds` selects comma-separated evolved genome CSVs; invalid seed input fails without importing an external CAD design.

The coarse FEM screen ranks valid genomes by structural shortfalls, with mass as a tie-breaker. It retains failing designs for improvement. Occasional broader mutations explore stock thickness and the existing continuous-rail architecture within the unchanged gene bounds. Each round records all generated genome rows and the provisional screen observations. The top-k assessment runs the standard `score_cad.py` / `evaluate_cad_candidate.py` path automatically.

The export constructs cutting faces from the existing apex and edge-angle genes, including the serrated boundaries. The integral bore collar uses the existing radial ring-wall gene: roll radius is `ring_wall / 4`, straight axial bearing is `2 * ring_wall`, and a planar land joins the roll to the body. STEP contains analytic toroidal rolls on both faces and a cylindrical bearing, along with a proper representation context and millimetre units. The STL is a tessellation of those circular surfaces. The measured radius is obtained from the actual exported geometry, and the standard evaluator independently reads and validates the STEP with OpenCascade. These are geometry changes; no ring-width strength or fatigue multiplier is applied.

The saved CAD top surface, with full-precision vertex heights, supplies the solid-tip submodel. Refinement interpolates those facets instead of sampling the display thickness raster. Scikit-fem P2 and DOLFINx solve the same saved fine mesh, with the existing load, support, refinement and comparison settings. Both raw observations, primary convergence data, DOLFINx settings, mesh, export surface, STEP/STL and runtime identity are retained. A missing runtime or failed solve remains unverified.

Each attempt lives under `by-content/<certificate_identity>/attempt-<id>/`. The identity includes exact genome bits, numerical sources, requirements and the active geometry context. Labels identify files; they cannot authorize reuse. Catalog solid-tip results also require matching genome/model and D1 bindings, exact raw hashes, agreement derived from both raw observations, and the required solver metadata.

`leaderboard.json` distinguishes completed assessments, unverified attempts and qualified designs. A completed assessment may fail physical gates. `champion` is null when nothing qualifies. Qualification requires all engineering gates and the complete RS-v2 `all_hard` verdict; the battery pass count alone does not establish it. A successful process exit means the requested assessments completed; inspect `qualified_count` for qualification. An unavailable independent assessment causes a nonzero exit and a retained unverified report.

Requirements, thresholds and genome bounds are unchanged. Existing catalog JSONs remain historical observations for their recorded model; they are not re-issued for this changed geometry. Live catalog scoring withholds incompatible solid-tip evidence. See [committed pipeline evidence](../evidence/evolve_certifiable/) for the automatic run and the separate legal-genome geometry controls.

## Phenotype changes and owner decision

**Collar construction rule: AWAITING OWNER SIGN-OFF.** The existing ring-wall gene now determines straight bearing `2 * wall` and bore-edge roll radius `wall / 4`; the maximum collar thickness is `2.5 * wall`, beyond the blade stock. This is an explicit phenotype construction change, counted in exported volume/mass and FEM thickness. It is not owner approval of this collar or a qualified design. The local plate approximation in this thick region also requires engineering scrutiny.

The RS-v2 phenotype also removed the artificial `0.895 mm` cutting-edge floor, the hard-coded radial tip-thickness law and its painted bisector cells, and the `w_bore=10.20 mm` override. Actual apex/angle genes and the exported surfaces now determine these measurements. Requirement thresholds and genome bounds remain unchanged.

Install the host solver environment from `fem_solid/requirements.txt` (including NumPy 1.26.4 and cadquery-ocp). The independent container uses its own NumPy, DOLFINx and PETSc; only the host's pinned SciPy wheel is supplied for recovery utilities, after the container's default import paths. Assessment inputs are mounted read-only and sidecar output has a separate writable directory.

Validation-policy changes invalidate earlier certificate identities. Retained solve evidence is a historical observation of its recorded kernel, not a newly issued certificate. The additive export-regeneration ledger in the evidence manifest checks current STEP/STL bytes and surface JSON; the geometric payload is also compared against the retained historical export. No large evidence files have been removed. A measured historical failure does not become a current qualified design.

A full Stage-2 solve can take tens of minutes per candidate; top-k assessments are sequential. Use a small top-k while exploring, and inspect the retained runtime and convergence logs for actual throughput.
