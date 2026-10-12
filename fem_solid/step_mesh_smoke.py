#!/usr/bin/env python3
"""Whole-part tet10 mesh with gmsh (PR-0.30.2 smoke). usage: step_mesh_smoke.py part.(step|stl) h_mm
Prints volume count, tet10 cell count, dofs (P2 vector) and the meshed volume (mm^3); exits 1 if no solid volume."""
import json, sys, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mesh as M
from dolfinx import fem
import ufl
t0 = time.time()
path = sys.argv[1]
msh, ft = (M.stl if path.lower().endswith(".stl") else M.step)(path, float(sys.argv[2]), lambda g, surfs: {})
vol = fem.assemble_scalar(fem.form(1.0 * ufl.dx(domain=msh)))
V = fem.functionspace(msh, ("Lagrange", 2, (3,)))
print(json.dumps(dict(step=sys.argv[1], h_mm=float(sys.argv[2]), n_tet10=msh.topology.index_map(3).size_global, n_dof=V.dofmap.index_map.size_global * 3,
                      volume_mm3=round(vol, 1), wall_s=round(time.time() - t0, 1))))
