Status: DONE-PASS
Subject: S07 dolfinx solver/field/representation evaluators and 3D tip cross-checks (file 09, pass 2)
Date: 2026-10-15T14:00:00+00:00
solve_dolfinx.py sha256: `41899824d22e2067bb69086fa6b08787e88f2aedaed6490466ed2077e2ede7d2`
test_field_semantics.py sha256: `e1a51a58e698773b0c6aa6a828c9e13e452b8aa28ca86070980d6c4a0b7dddd9`
test_representation_invariants.py sha256: `2926c6cec4f3c7e4ec5e5868d636aa8310861738511ef9db3e6f4f82d8de6db7`

1. Streamed pinned image `ghcr.io/fenics/dolfinx/dolfinx:v0.9.0` (`sha256:628f40dd62c7f37962ccadc5a745f23d52c56b2ac3ad9b9b6a86c567c07aa27b`) from `xbabe3` (`192.168.68.54`) onto `xbabe2`, cherry-picked the 8 S07 commits (`e6c95f3..c100d10`), fixed single-point `f.eval` shape handling and iterative CG/GAMG residual tolerances (`rtol=1e-12`/`1e-13`), and executed both suites inside the container:
   - `fem_solid/tests/test_field_semantics.py`: 30 tests `OK` (4 `Catalog` + 26 `Operator`)
   - `fem_solid/tests/test_representation_invariants.py`: 33 tests `OK` (`Operator`)
2. Executed `fem_solid/cross_check.py` inside `ghcr.io/fenics/dolfinx/dolfinx:v0.9.0` on the `NL=4, NSUB=1` 3D tip submodels of `w271b_11860` and `w271c_11522` (dumped via `DUMP_MESH` from `fem_solid/tip_solid.py`):
   - `w271b_11860`: `n_dof = 351297`, `ksp_its = 74`, `SF_nodal_max = 0.8144` (vs `skfem` `0.814`, `rel_err_nodal_max = 0.0004914`), `SF_nodal_avg = 0.8561` (vs `skfem` `0.856`, `rel_err_nodal_avg = 0.0001168`), `vm_nodal_max_MPa = 894.44`, `vm_nodal_avg_MPa = 850.89`, `sallow_MPa = 728.41` (PASS within 2%).
   - `w271c_11522`: `n_dof = 367767`, `ksp_its = 77`, `SF_nodal_max = 1.0330` (vs `skfem` `1.033`, `rel_err_nodal_max = 0.0`), `SF_nodal_avg = 1.0883` (vs `skfem` `1.088`, `rel_err_nodal_avg = 0.0002757`), `vm_nodal_max_MPa = 706.00`, `vm_nodal_avg_MPa = 670.13`, `sallow_MPa = 729.32` (PASS within 2%).
