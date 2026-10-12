#!/usr/bin/env python3
"""Reference linear-elastic solver (PR-0.30.2): dolfinx 0.9 + PETSc CG/GAMG (rigid-body near-nullspace), P2 vector field on
tet10 (or P2 on linear tets). Used inside the pinned container ghcr.io/fenics/dolfinx/dolfinx:v0.9.0.
API: solve(mesh, facet_tags, E, nu, clamp_tags, tractions={tag: callable(x)->(3,N)}, point_dirichlet=None) -> (u, vm_nodal, info)."""
import time
import numpy as np
from mpi4py import MPI
from petsc4py import PETSc
import ufl
from dolfinx import fem, mesh as dmesh
from dolfinx.fem.petsc import assemble_matrix, assemble_vector, apply_lifting, set_bc


_KEEP = []  # keep the Functions that own the near-nullspace vectors alive for the solve


def rigid_modes(V):
    """6 rigid-body modes (3 translations, 3 rotations) as the GAMG near-nullspace."""
    x = V.tabulate_dof_coordinates()  # one row per block (node)
    X, Y, Z = x[:, 0], x[:, 1], x[:, 2]
    cols = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (-Y, X, 0 * X), (0 * X, -Z, Y), (Z, 0 * X, -X)]
    fs = []
    for c in cols:
        f = fem.Function(V); a = f.x.array.reshape(-1, 3)
        for k in range(3): a[:, k] = c[k]
        f.x.scatter_forward(); fs.append(f)
    _KEEP.append(fs)
    from dolfinx.la import orthonormalize
    orthonormalize([f.x for f in fs])
    vecs = [f.x.petsc_vec for f in fs]
    return PETSc.NullSpace().create(vectors=vecs)


def solve(msh, ft, E, nu, clamp_tags, tractions, sym_tags=None, rtol=1e-10, order=2):
    """sym_tags: {facet tag: component} -> u[component] = 0 on that facet set (symmetry planes)."""
    t0 = time.time()
    V = fem.functionspace(msh, ("Lagrange", order, (3,)))
    lam = E * nu / ((1 + nu) * (1 - 2 * nu)); mu = E / (2 * (1 + nu))
    eps = lambda w: ufl.sym(ufl.grad(w))
    sig = lambda w: 2 * mu * eps(w) + lam * ufl.tr(eps(w)) * ufl.Identity(3)
    u, v = ufl.TrialFunction(V), ufl.TestFunction(V)
    ds = ufl.Measure("ds", domain=msh, subdomain_data=ft)
    a = ufl.inner(sig(u), eps(v)) * ufl.dx
    L = ufl.inner(fem.Constant(msh, np.zeros(3)), v) * ufl.dx
    for tag, f in tractions.items():
        tf = fem.Function(V); tf.interpolate(f); L = L + ufl.inner(tf, v) * ds(tag)
    fdim = msh.topology.dim - 1
    bcs = []
    for tag in clamp_tags:
        dofs = fem.locate_dofs_topological(V, fdim, ft.find(tag))
        bcs.append(fem.dirichletbc(np.zeros(3), dofs, V))
    for tag, comp in (sym_tags or {}).items():
        Vc, _ = V.sub(comp).collapse()
        dofs = fem.locate_dofs_topological((V.sub(comp), Vc), fdim, ft.find(tag))
        z = fem.Function(Vc); bcs.append(fem.dirichletbc(z, dofs, V.sub(comp)))
    af, Lf = fem.form(a), fem.form(L)
    A = assemble_matrix(af, bcs=bcs); A.assemble()
    b = assemble_vector(Lf); apply_lifting(b, [af], bcs=[bcs]); b.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE); set_bc(b, bcs)
    A.setNearNullSpace(rigid_modes(V))
    ksp = PETSc.KSP().create(msh.comm); ksp.setOperators(A); ksp.setType("cg")
    pc = ksp.getPC(); pc.setType("gamg")
    opts = PETSc.Options(); opts["mg_levels_ksp_type"] = "chebyshev"; opts["mg_levels_pc_type"] = "jacobi"; opts["pc_gamg_coarse_eq_limit"] = 1000
    ksp.setFromOptions(); ksp.setTolerances(rtol=rtol, max_it=5000)
    uh = fem.Function(V); t1 = time.time(); ksp.solve(b, uh.x.petsc_vec); uh.x.scatter_forward()
    its, reason = ksp.getIterationNumber(), ksp.getConvergedReason()
    # nodal von Mises: L2-project deviatoric stress onto P1 (order-1 nodal), plus DG(order-1) element-wise for max
    s = sig(uh) - ufl.tr(sig(uh)) / 3 * ufl.Identity(3); vm = ufl.sqrt(1.5 * ufl.inner(s, s))
    W = fem.functionspace(msh, ("Discontinuous Lagrange", order - 1))
    vmh = fem.Function(W); vmh.interpolate(fem.Expression(vm, W.element.interpolation_points()))
    info = dict(n_dof=V.dofmap.index_map.size_global * 3, ksp_its=its, ksp_reason=int(reason), assemble_s=round(t1 - t0, 2), solve_s=round(time.time() - t1, 2))
    if reason <= 0: raise RuntimeError(f"KSP did not converge: {info}")
    return uh, vmh, sig, info
