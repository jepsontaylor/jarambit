# sheath/ — SWITCHBACK hard fixed-carry sheath generator + draw-force scoring (v1)

Plan: [`../docs/sheath/SHEATH_V1_PLAN.md`](../docs/sheath/SHEATH_V1_PLAN.md). Evidence: `../evidence/sheath/c93_v1/`.
The exported bump is a spherical cap. Directional cam sectors and non-camming flanks are proposed geometry;
containment, edge-drop, rattle and retention-force feasibility are **INCOMPLETE**, with zero fitness credit.
Force curves and Monte Carlo values are proposed-ramp diagnostics (analytic_proxy + uncalibrated FEA).
The independent CalculiX ramp benchmark does not validate the exported spherical cap.

```
~/bin/memcap 32G nice -n 19 python -m sheath.run \
  --step designs/switchback/C9.3/cad/switchback_revC9_3_ground.step \
  --stl designs/switchback/C9.3/cad/switchback_revC9_3_ground.stl \
  --annotations designs/switchback/C9.3/sheath/knife_interface_annotations.json \
  --ccx evidence/sheath/ccx_tab_v1/ccx_tab.json --out OUT
~/bin/memcap 32G nice -n 19 python -m pytest sheath/tests -q -rs
```
Omit `--workers` to use the safe default, bounded by affinity, available memory and all inherited cgroup caps.
Annotations must be approved and bound to the STEP hash. Missing/rejected annotations stop the runner before search.
The configured p05 SF floor (2 at 15 g) gates both candidate selection and final scoring.
CalculiX corrections require successful, complete, fresh histories, matching input/output hashes and <=5% convergence.
Deps (xbabe2 venv `~/jarambit_render/venv-sheath`): cadquery 2.8, scikit-fem 12, shapely 2.2, triangle, trimesh, numpy, scipy, matplotlib.
