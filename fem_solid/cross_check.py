#!/usr/bin/env python3
"""Solve the exact tip submodel of tip_solid.py (DUMP_MESH npz) with the dolfinx/PETSc-GAMG reference solver and compare
the tip SF metrics (PR-0.30.2). Same geometry, same P2 field, same clamp and point loads, same vertex von Mises recovery, so the
two solvers must agree to within 2 %. usage (container): cross_check.py dump.npz [skfem_solid.json | -]"""
import json, sys
import numpy as np
from mpi4py import MPI
import basix.ufl, ufl
from dolfinx import fem, mesh as dmesh
from dolfinx.fem.petsc import assemble_matrix, assemble_vector, apply_lifting, set_bc
from petsc4py import PETSc
from scipy.spatial import cKDTree
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import solve_dolfinx as S

d = np.load(sys.argv[1]); ref = json.load(open(sys.argv[2]))['solid'] if len(sys.argv) > 2 and sys.argv[2] != '-' else None
pts, tets = d['pts'], d['tets'].astype(np.int64); E, nu, sallow = float(d['E']), float(d['nu']), float(d['sallow'])
cel = basix.ufl.element("Lagrange", "tetrahedron", 1, shape=(3,))
msh = dmesh.create_mesh(MPI.COMM_WORLD, tets, pts, ufl.Mesh(cel))
V = fem.functionspace(msh, ("Lagrange", 2, (3,)))
lam = E * nu / ((1 + nu) * (1 - 2 * nu)); mu = E / (2 * (1 + nu))
eps = lambda w: ufl.sym(ufl.grad(w)); sig = lambda w: 2 * mu * eps(w) + lam * ufl.tr(eps(w)) * ufl.Identity(3)
u, v = ufl.TrialFunction(V), ufl.TestFunction(V)
a = fem.form(ufl.inner(sig(u), eps(v)) * ufl.dx)
# clamp: fixed vertices + midpoints of edges whose two ends are fixed (exactly the skfem dof set)
fx = pts[d['fixed_v']]; ef = d['edges_fixed']; fx = np.vstack([fx, 0.5 * (pts[ef[:, 0]] + pts[ef[:, 1]])]); tr = cKDTree(fx)
dofs = fem.locate_dofs_geometrical(V, lambda X: tr.query(X.T)[0] < 1e-7)
bc = fem.dirichletbc(np.zeros(3), dofs, V)
A = assemble_matrix(a, bcs=[bc]); A.assemble()
b = assemble_vector(fem.form(ufl.inner(fem.Constant(msh, np.zeros(3)), v) * ufl.dx))
# point loads Fz at the patch vertices
Vz, zmap = V.sub(2).collapse(); xz = Vz.tabulate_dof_coordinates(); tz = cKDTree(xz)
dist, idx = tz.query(pts[d['pat']]); assert dist.max() < 1e-7
arr = b.getArray(); arr[np.asarray(zmap)[idx]] += d['Fz']; b.setArray(arr)
apply_lifting(b, [a], bcs=[[bc]]); set_bc(b, [bc])
A.setNearNullSpace(S.rigid_modes(V))
ksp = PETSc.KSP().create(msh.comm); ksp.setOperators(A); ksp.setType("cg"); ksp.getPC().setType("gamg")
o = PETSc.Options(); o["mg_levels_ksp_type"] = "chebyshev"; o["mg_levels_pc_type"] = "jacobi"; ksp.setFromOptions(); ksp.setTolerances(rtol=1e-10, max_it=5000)
uh = fem.Function(V); ksp.solve(b, uh.x.petsc_vec); uh.x.scatter_forward(); assert ksp.getConvergedReason() > 0
s = sig(uh); dev = s - ufl.tr(s) / 3 * ufl.Identity(3); vm = ufl.sqrt(1.5 * ufl.inner(dev, dev))
W = fem.functionspace(msh, ("Discontinuous Lagrange", 1)); vmh = fem.Function(W); vmh.interpolate(fem.Expression(vm, W.element.interpolation_points()))
# per-vertex max / mean over incident cells (DG1 dofs sit at cell vertices) -- same recovery as tip_solid
cells = msh.geometry.dofmap; X = msh.geometry.x; Wd = W.dofmap.list; val = vmh.x.array
nv = X.shape[0]; mx = np.zeros(nv); acc = np.zeros(nv); cnt = np.zeros(nv)
for k in range(4):
    np.maximum.at(mx, cells[:, k], val[Wd[:, k]]); np.add.at(acc, cells[:, k], val[Wd[:, k]]); np.add.at(cnt, cells[:, k], 1)
avg = acc / np.maximum(cnt, 1)
dv = np.linalg.norm(X[:, :2] - d['tipo'], axis=1); dcut = cKDTree(d['cutxy']).query(X[:, :2])[0]
z = (dv >= 4) & (dv < 15) & (dcut > 3.0)
out = dict(n_dof=V.dofmap.index_map.size_global * 3, ksp_its=ksp.getIterationNumber(),
           SF_nodal_max=round(sallow / mx[z].max(), 4), SF_nodal_avg=round(sallow / avg[z].max(), 4),
           vm_nodal_max_MPa=round(float(mx[z].max()), 2), vm_nodal_avg_MPa=round(float(avg[z].max()), 2), sallow_MPa=round(sallow, 2))
if ref is None: print(json.dumps(out, indent=1)); sys.exit(0)
out.update(ref_SF_nodal_max=ref['SF_solid_nodal_max'], ref_SF_nodal_avg=ref['SF_solid_nodal_avg'], ref_n_dof=ref['n_dof'])
out['rel_err_nodal_max'] = abs(out['SF_nodal_max'] / out['ref_SF_nodal_max'] - 1); out['rel_err_nodal_avg'] = abs(out['SF_nodal_avg'] / out['ref_SF_nodal_avg'] - 1)
print(json.dumps(out, indent=1)); sys.exit(0 if max(out['rel_err_nodal_max'], out['rel_err_nodal_avg']) <= 0.02 else 1)
