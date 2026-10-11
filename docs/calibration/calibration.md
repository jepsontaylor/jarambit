# MC <-> FEM calibration (jarambit calib)

Reference = detailed plate at the verification mesh (max area 0.25 mm^2, the finest converged level in `out/fem_verify/report.md`). 20 C. Lateral = governing tip-lateral capacity (the 180/260 N floor case); ring = ring-pull capacity.

| ratio | stats |
|---|---|
| beam surrogate / detailed plate, lateral (MC overstatement) | n=258 min 0.979 p05 1.088 median 1.796 p95 2.952 max 3.065 |
| beam surrogate / detailed plate, lateral, filleted necks (r > 1 mm) | n=111 min 0.979 p05 1.043 median 1.247 p95 1.599 max 1.783 |
| coarse plate (fem.rs) / detailed plate, lateral | n=258 min 0.099 p05 0.422 median 1.199 p95 1.667 max 1.874 |
| search mesh / verify mesh, lateral (mesh bias in the loop) | n=258 min 0.924 p05 0.951 median 0.994 p95 1.024 max 1.070 |
| search mesh / verify mesh, lateral, filleted necks | n=111 min 0.924 p05 0.956 median 0.996 p95 1.033 max 1.056 |
| beam surrogate / detailed plate, ring pull | n=258 min 1.487 p05 1.745 median 6.311 p95 7.911 max 8.449 |
| search mesh / verify mesh, ring pull | n=258 min 0.991 p05 1.000 median 1.017 p95 1.032 max 1.062 |

Designs: wave5 winner, mh1 group winners (pre-blade-fix, legacy sharp neck), 120 red-team-legal random genomes, each also with its neck genes zeroed (sharp corner). Per-design rows: `calibration.csv`.
