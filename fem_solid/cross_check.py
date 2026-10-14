#!/usr/bin/env python3
"""Solve the exact tip submodel of tip_solid.py (DUMP_MESH npz) with the dolfinx/PETSc-GAMG reference solver and compare
the tip SF metrics (PR-0.30.2). Same geometry, same P2 field, same clamp and point loads, same vertex von Mises recovery, so the
two solvers must agree to within 2 %. usage (container): cross_check.py dump.npz [skfem_solid.json | -]
S07: the solve, VM extraction, incident-cell recovery and ROI use the shared solve_dolfinx seams (realized CG/GAMG settings,
local rigid-mode owner, dg_von_mises, recover_vertex_vm, tip_roi_mask); stdout keys and rounding are unchanged. With
CROSS_CHECK_SIDECAR=<new path> the realized settings, descriptors and input hashes are also written there (no-clobber)."""
import hashlib, json, os, sys
import numpy as np
from mpi4py import MPI
import basix.ufl, ufl
from dolfinx import fem, mesh as dmesh
from dolfinx.fem.petsc import assemble_matrix, assemble_vector, apply_lifting, set_bc
from scipy.spatial import cKDTree
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import solve_dolfinx as S

CATALOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assurance', 'numerical', 'observable_catalog.json')
EXPECTED = next(o['descriptor'] for o in json.load(open(CATALOG))['observables'] if o['key'] == 'dg_vm_interpolation.v1/P2-DG1/mm')
LEGACY_OPTIONS = {"mg_levels_ksp_type": "chebyshev", "mg_levels_pc_type": "jacobi"}  # this script never set pc_gamg_coarse_eq_limit

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
ns, owner = S.rigid_mode_owner(V)  # local owner outlives the matrix/nullspace/KSP that reference its vectors
A.setNearNullSpace(ns)
uh = fem.Function(V)
settings, stats = S.krylov_solve(A, b, uh.x.petsc_vec, msh.comm, rtol=1e-10, max_it=5000, defaults=LEGACY_OPTIONS)  # raises unless reason > 0
uh.x.scatter_forward(); A.destroy(); b.destroy(); ns.destroy(); del owner
vmh, desc = S.dg_von_mises(msh, sig(uh), 2, units=("mm", "N", "MPa"), frame=S.FRAME, region=S.WHOLE_DOMAIN)
# per-vertex max / unweighted mean over incident cells (DG1 dofs sit at cell vertices) -- same recovery as tip_solid
rec = {op: S.recover_vertex_vm(msh, vmh, op, descriptor=desc, expected_descriptor=EXPECTED) for op in ("max", "mean")}
X = rec["max"]["coordinates"]
dv = np.linalg.norm(X[:, :2] - d['tipo'], axis=1); dcut = cKDTree(d['cutxy']).query(X[:, :2])[0]
z = S.tip_roi_mask(dv, dcut)
mx, avg = S.region_extreme(rec["max"]["values"], z), S.region_extreme(rec["mean"]["values"], z)
out = dict(n_dof=V.dofmap.index_map.size_global * 3, ksp_its=stats["ksp_its"],
           SF_nodal_max=round(sallow / mx, 4), SF_nodal_avg=round(sallow / avg, 4),
           vm_nodal_max_MPa=round(mx, 2), vm_nodal_avg_MPa=round(avg, 2), sallow_MPa=round(sallow, 2))
side = os.environ.get('CROSS_CHECK_SIDECAR')
if side:
    data = json.dumps({"schema": "jarambit.fem_solid.cross_check_sidecar.v1", "argv": sys.argv,
                       "inputs": {p: hashlib.sha256(open(p, 'rb').read()).hexdigest() for p in sys.argv[1:3] if p != '-'},
                       "solver": {**settings, **stats}, "observable": desc, "recovery": [rec["max"]["operator"], rec["mean"]["operator"]],
                       "roi": S.TIP_ROI, "roi_vertices": int(z.sum()), "legacy_stdout": out}, indent=1, allow_nan=False).encode()
    fd = os.open(side, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try: os.write(fd, data); os.fsync(fd)
    finally: os.close(fd)
if ref is None: print(json.dumps(out, indent=1)); sys.exit(0)
out.update(ref_SF_nodal_max=ref['SF_solid_nodal_max'], ref_SF_nodal_avg=ref['SF_solid_nodal_avg'], ref_n_dof=ref['n_dof'])
out['rel_err_nodal_max'] = abs(out['SF_nodal_max'] / out['ref_SF_nodal_max'] - 1); out['rel_err_nodal_avg'] = abs(out['SF_nodal_avg'] / out['ref_SF_nodal_avg'] - 1)
print(json.dumps(out, indent=1)); sys.exit(0 if max(out['rel_err_nodal_max'], out['rel_err_nodal_avg']) <= 0.02 else 1)
