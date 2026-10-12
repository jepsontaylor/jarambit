#!/usr/bin/env python3
"""Verification of mesh.py + solve_dolfinx.py against closed-form elasticity (PR-0.30.2). Prints JSON; exit 1 on miss.
1) Saint-Venant torsion, square a x a bar: twist rate theta' = T / (k1 G a^4), k1 = 0.140577 (exact series).
   Load: torque T on z=L face as the St-Venant shear traction of a circular-section approximation (tau = T r / J_polar);
   twist rate measured on the middle third (z in [L/3, 2L/3]), where St-Venant's principle makes end effects negligible.
2) Kirsch 3D: thin plate with hole, remote tension s0 on x faces; peak hoop stress / s0 vs Heywood finite-width
   Kt_gross = (2 + (1 - d/W)^3) / (1 - d/W) at mid-thickness (t/r = 0.2, plane-stress limit)."""
import json, math, sys, time
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 2)[0])
import mesh as M, solve_dolfinx as S
from dolfinx import fem, geometry

E, NU = 113.8e3, 0.34; G = E / (2 * (1 + NU))


def probe(msh, f, pts):
    tree = geometry.bb_tree(msh, msh.topology.dim); cand = geometry.compute_collisions_points(tree, pts)
    cells = geometry.compute_colliding_cells(msh, cand, pts); c = [cells.links(i)[0] for i in range(len(pts))]
    return f.eval(pts, c)


def torsion(h):
    a, L, T = 10.0, 80.0, 1000.0
    msh, ft = M.bar(a, L, h)
    Jp = a ** 4 / 6.0
    trac = lambda x: np.vstack([-T * x[1] / Jp, T * x[0] / Jp, 0 * x[0]])
    uh, _, _, info = S.solve(msh, ft, E, NU, [1], {2: trac})
    z1, z2, r = L / 3, 2 * L / 3, a / 4
    def rot(z):
        p = np.array([[r, 0, z], [0, r, z], [-r, 0, z], [0, -r, z]])
        u = probe(msh, uh, p); return np.mean([u[0, 1] / r, -u[1, 0] / r, -u[2, 1] / r, u[3, 0] / r])
    rate = (rot(z2) - rot(z1)) / (z2 - z1); exact = T / (0.140577 * G * a ** 4)
    return dict(case="saint_venant_square_torsion", h=h, rate=rate, exact=exact, rel_err=abs(rate / exact - 1), **info)


def kirsch(h_hole):
    W, H, t, r, s0 = 200.0, 800.0, 2.0, 10.0, 100.0  # long strip (H = 4W) so the Howland/Heywood strip reference applies
    msh, ft = M.plate_hole(W, H, t, r, h_far=12.0, h_hole=h_hole)
    uh, vmh, sig, info = S.solve(msh, ft, E, NU, [], {2: lambda x: np.vstack([s0 + 0 * x[0], 0 * x[0], 0 * x[0]])}, sym_tags={1: 0, 3: 1, 4: 2})
    return msh, uh, info, s0, W, r, t


def kirsch_eval(h_hole):
    import ufl
    msh, uh, info, s0, W, r, t = kirsch(h_hole)
    lam = E * NU / ((1 + NU) * (1 - 2 * NU)); mu = E / (2 * (1 + NU))
    e = ufl.sym(ufl.grad(uh)); sxx = 2 * mu * e[0, 0] + lam * ufl.tr(e)
    Q = fem.functionspace(msh, ("Discontinuous Lagrange", 1)); sh = fem.Function(Q); sh.interpolate(fem.Expression(sxx, Q.element.interpolation_points()))
    eps_ = 1e-4; p = np.array([[eps_, r + eps_, 1e-4]])  # mid-plane, hole edge at 90 deg
    peak = float(np.mean(probe(msh, sh, p))) / s0
    d_W = 2 * r / W; kt = (2 + (1 - d_W) ** 3) / (1 - d_W)
    return dict(case="kirsch_3d_heywood", h_hole=h_hole, kt_fem=peak, kt_ref=kt, rel_err=abs(peak / kt - 1), **info)


if __name__ == "__main__":
    # rigid-body: Kirsch has no Dirichlet BC -> pure traction problem; pin it via the near-nullspace-only CG is singular,
    # so solve_dolfinx is called with symmetric clamps? (handled below by clamping nothing and relying on compatible load + CG)
    out = [torsion(float(a)) for a in (sys.argv[1:2] or ["1.25"])]
    out.append(kirsch_eval(float(sys.argv[2]) if len(sys.argv) > 2 else 0.4))
    print(json.dumps(out, indent=1)); sys.exit(0 if all(o["rel_err"] <= 0.01 for o in out) else 1)
