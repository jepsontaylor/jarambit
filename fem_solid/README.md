# fem_solid — solid tip submodel (PR-0.30.1)

Brought into the repo from the out-of-repo wave18–27 tool (`~/jarambit_tools/w18tip` on xbabe2; script
`docs/wave18_controlled/tip3d/tip_solid.py` on branch `exec/wave27-diversity` @ f954a58). Structural screening only.

**What it computes.** Chord-torsion safety factor at 1.82 N·m in the 4–15 mm tip zone of one D1 design. It uses P2 tets
(scikit-fem), built by extruding the D1 plate mesh within `R_CUT` of the tip to ±th/2 using the thickness raster.
The cut boundary is clamped. The load is a pure chord torque applied by minimum-norm z-forces within `PATCH` mm of the tip.
Ti-6Al-4V: E 113.8 GPa, ν 0.34, σy 828 MPa (provisional), with the same JOINT thin+hot factor as crescent-d1. The solver is
pyamg smoothed-aggregation preconditioned CG. It reports nodal-max, nodal-avg and element-mean von Mises SF.

**Environment.** `pip install -r fem_solid/requirements.txt` (scikit-fem 12.0.2 = the vendored copy byte-for-byte, pyamg 5.3.0).

**Run.** `python3 fem_solid/run_tip.py <design>_D1.json out.json [R_CUT=30] [NLAYER=4] [NSUB=1] [PATCH=2.0]`.
`<design>_grind_law.json` must sit beside the D1 JSON. A D1 JSON with mesh/field comes from `jarambit crescent-d1` with `D1_PLATES=1`.
It writes `out.json.manifest.json` containing input/script sha256, library versions, parameters, n_dof, n_tet, wall time and SF.

**Evidence.** `evidence/wave27/*_solid.json` holds 24 wave27 results. The g3_tip+00_t60_tt3 D1 + grind-law inputs are kept as the regression fixture.

**Tests.** `python3 -m unittest discover -s fem_solid/tests`. The fast evidence checks run in CI. `FEM_SOLID_REGRESS=1` re-runs the
reference (about 25 min at 4 threads) and needs SF_solid_nodal_max 1.534 ± 0.005 and n_dof 422 955.

## Reference solver (PR-0.30.2)
`mesh.py` builds gmsh tet10 meshes and hands them to dolfinx. It covers verification geometries, faceted STEP (OCC import + heal) and
the faceted STL twin. The wave27 STEP imports as an unsewable shell, so the whole-part mesh uses the STL; its volume gives 84.86 g against 84.80 g reported.
`solve_dolfinx.py` is linear elasticity with P2 on tet10, solved by PETSc CG + GAMG with a rigid-body near-nullspace. Environment: `fem_solid/Dockerfile`
(dolfinx 0.9.0, gmsh 4.13.1, scipy 1.18.1), built and run on xbabe3.
Verification (`evidence/fem_solid/verify_0.30.2.json`, checked in CI):
- Saint-Venant square-bar torsion: twist rate within 0.25 % of exact.
- Kirsch 3D (thin strip, d/W 0.1): Kt within 0.73 % of Heywood.
- dolfinx vs skfem on the identical g3 tip submodel: SF_nodal_max 1.5341 vs 1.534 (6.5e-5).
Whole-part L1–L5 load cases on the tet10 mesh are not wired up yet (next: PR-0.30.3 convergence/GCI).
