# Genome pipeline proof

This is an automatic assessment of an offspring, plus a separate legal-genome geometry control. No fully qualified design or new record is claimed.

The automatic run used source commit `e8cb049df7d03c7d3113556812cc140ca99a29c3` and the command recorded in [execution.json](execution.json). The later search-only broader mutation operator does not change the numerical kernel or these genome identities. The complete source closure, executable hash and runtime observations are retained. [manifest.json](manifest.json) hashes every raw artifact. [unchanged_limits.json](unchanged_limits.json) records the unchanged requirements, bounds, gate definitions, public limits and scoring/gate ASTs against base `4cd0f994e80355a898afde6de816f00ca2ebe35a`.

## Automatic offspring

```bash
./evolve.sh --rounds 1 --candidates-per-round 6 --top-k-certify 1 --threads 2 \
  --seed 20261017 --seeds evidence/rs_v2/w283_ultrarunner/w283_p14_c01_genome.csv \
  --prefix cert_pipeline --out-dir evidence/evolve_certifiable/automatic
```

[Birth history](automatic/round_00_births.json) and [provisional screens](automatic/round_00_screen.json) retain every generated genome and its rank. The selected offspring is `cert_pipeline_r01_p14_c02`, content identity `db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e`.

| Observation | Value | Raw source |
|---|---:|---|
| Raster mass | 83.063 g | [scorecard](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_master_scorecard.json) |
| Exported 3D mass | 83.0386 g | [scorecard](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_master_scorecard.json) |
| G1 | 0.463443 | [scorecard](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_master_scorecard.json) |
| W_CAD | -5.570408 | [scorecard](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_master_scorecard.json) |
| Scikit-fem P2 nodal-max SF | 0.669 | [primary raw](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_skfem_raw.json) |
| DOLFINx nodal-max SF | 0.6693 | [independent raw](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_dolfinx_raw.json) |
| Fine mesh tetrahedra | 91008 | [mesh](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_solid_mesh.npz) / [primary raw](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_skfem_raw.json) |
| P2 degrees of freedom | 416583 | [primary raw](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_skfem_raw.json) / [independent raw](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_dolfinx_raw.json) |

The primary solve converged in 152 iterations with relative residual 8.803574037789025e-11. DOLFINx took 158 iterations; its [sidecar](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_dolfinx_sidecar.json) records a positive convergence reason and the hash of the same saved mesh. [Stored observations](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_solid_tip.json) retain both SFs, raw hashes and the comparison. Both solvers ran automatically; no external certificate was copied in.

The [RS-v2 result](automatic/by-content/db5d8e32e99d0b2d8ef6d7c7f9622a0601487c25b80879bbc8be1a502693c55e/attempt-1792206525341070917/cert_pipeline_r01_p14_c02_rs.json) is `all_hard=false` with an empty unverified list. Structural, sharpness, point-profile and bore-radius requirements still fail for this offspring. The [leaderboard](automatic/leaderboard.json) records one completed assessment, zero qualified designs, zero unverified attempts and a null champion. A verified computation is distinct from a qualifying design. The catalog replay regression checks that this matching solid observation is accepted while earlier synthetic adverse controls reject mismatched evidence.

## Separate geometry control

[control_genome.csv](controls/legal_genome/control_genome.csv) uses the existing genes and bounds: EDGE_TH=0.12, both edge half-angles=14 degrees, RING_WALL=6.3 mm. It is a component regression genotype derived from the committed seed, not an evolved winner or a non-genome CAD import.

[Actual export measurements](controls/legal_genome/control_measurements.json) show apex 0.134160883 mm, maximum half-angle 16.444344357 degrees and minimum fitted bore roll radius 1.575000000 mm. The exported edge passes the unchanged sharpness checks. [Independent OpenCascade inspection](controls/legal_genome/control_step_check.json) reads one valid solid with analytic toroidal bore rolls on both faces, radius 1.575 mm. STEP, STL and the exact surface vertices are retained alongside those observations.

This control still fails the unchanged full point-profile monotonicity check. It is not an `all_hard` certificate. It demonstrates that the former edge and bore construction barriers can be removed within the existing genome domain.

## Follow-up policy and regeneration

The stricter STEP read-back and pinned independent runtime change the validation-policy fingerprint. The retained solve observations describe their recorded producer; they are withheld as current catalog certificates. Their geometry is unchanged. The manifest's additive `regeneration` ledger records fresh exporter STEP/STL/surface SHA256 values. STEP/STL match the original files byte-for-byte; surface geometry/topology/tip/mode also match, with a new policy identity. CI regenerates these exports and checks both the SHA256 ledger and the unchanged historical payload. Every original large artifact remains in git; its future retention is an owner decision.
