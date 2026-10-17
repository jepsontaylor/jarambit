# v1.0.0 certificate integrity correction

The original Wave 283 all-hard and 16-gate qualification claims are retracted (#75–#81). No requirement thresholds or genome bounds were relaxed, and neither input genome was changed. See `unchanged-requirements.json` for exact hashes and the source-constant comparison.

`v1.0.0-retracted/` preserves the exact previously committed release certificates and their source-commit/hash manifest. Those documents are invalid qualification evidence; they are retained solely for audit.

`recertified/w283_p14_c01/` and `recertified/w283_p10_c02/` contain the corrected D1/RS/CAD evaluations, exact 3D solver meshes, raw scikit-fem and DOLFINx observations and exported CAD. Each current result carries a canonical genome/model content identity. The solid record additionally hashes its input D1, genome, exact mesh and both raw solver outputs. Its independent comparison recomputes the original 2% limit from the distinct solver observations.

FEM uses the same post-removal thickness law and physical thickness floor as the export. Human-max and fatigue stresses receive no ring-width strength multiplier. Edge apex/angle and the full 0–10 mm tip profile are measured by vertical intersections with the faceted export; monotonicity checks every surface breakpoint. An absent full-thickness crossing is a measured lower bound, never an invented exact taper length. `export_measurements.point.taper_mm` is the exact crossing when observed (otherwise null); `taper_lower_bound_mm` is the measured bound. Both profile representations carry a separate `taper_lower_bound_mm`; an unobserved exact crossing stays null. An unfilleted bore reports zero radius; a radius that cannot be established remains unverified and cannot pass.

The native Rust solid solve remains a coarse screen. It supplies no independent DOLFINx result, no zero-error assertion and no certified solid input to G1. The full pipeline actually runs scikit-fem P2 at NL=4, NSUB=1 and the pinned DOLFINx v0.9.0 container on the identical saved mesh. A solver execution error fails the pipeline; a measured failure remains a failure.

Reproduce after building the CLI and the export_step, plate_gci_probe and g3_side_report examples:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python3 -B ops/ci/evaluate_cad_candidate.py \
  --label w283_p14_c01 \
  --genome evidence/rs_v2/w283_ultrarunner/w283_p14_c01_genome.csv \
  --out-dir target/recertification/w283_p14_c01
```

Repeat with `w283_p10_c02`. The Python interpreter for scikit-fem and the independent container are configured by the existing standard pipeline. Exact committed numbers are in each `*_cad_eval.json` and `*_rs.json`; generated README/STATUS/engineering tables summarize them. No manufacturing promotion follows from these numerical results.


The final identity regime hashes the material and every exact IEEE-754 genome bit, so binding does not depend on display formatting. `identity-upgrade.json` records the metadata-only migration: all numerical sources, measurement code, requirements, exact genomes, D1 inputs and raw observations were checked unchanged. The original solver records are retained verbatim as `*_observed_solid_tip.json`; the re-issued bindings explicitly set `solve_rerun = false` and retain the observed identity. The current RS verdict was run again against the stronger embedded-identity and genome checks. No additional solid solve is claimed by this migration. `ops/ci/upgrade_cert_identity.py` refuses numerical/source/input drift; an identity upgrade cannot substitute evidence from another genome or changed physics.
