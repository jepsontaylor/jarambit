# sheath/ — SWITCHBACK hard fixed-carry sheath generator + draw-force scoring (v1)

Plan: [`../docs/sheath/SHEATH_V1_PLAN.md`](../docs/sheath/SHEATH_V1_PLAN.md). Evidence: `../evidence/sheath/c93_v1/`.
All forces are **predictions** (analytic_proxy + uncalibrated Kirchhoff-plate FEA). Nothing here is a measurement.

```
python -m sheath.run --step designs/switchback/C9.3/cad/switchback_revC9_3_ground.step \
                     --stl  designs/switchback/C9.3/cad/switchback_revC9_3_ground.stl --out OUT --workers 40
python -m unittest discover -s sheath/tests -t .     # analytic tests need only stdlib; FEM tests skip without scikit-fem
```
Deps (xbabe2 venv `~/jarambit_render/venv-sheath`): cadquery 2.8, scikit-fem 12, shapely 2.2, triangle, trimesh, numpy, scipy, matplotlib.
