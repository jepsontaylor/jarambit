"""Panel stiffness at the detent by Kirchhoff-plate FEM (Morley element, scikit-fem) — uncalibrated_fea.

Domain = cavity planform (the thin panel spans the cavity; the full-height rim band is treated as a clamp),
clamped on every cavity boundary edge except the open mouth (free). Load = P spread over the detent bump disc.
Verification: clamped circular plate vs Timoshenko/Roark closed form (tests/test_fem_plate.py).
"""
import math
import numpy as np


def mesh_polygon(poly, max_area=0.6, refine_at=None, r_ref=4.0, a_ref=0.05):
    import triangle as tr
    from skfem import MeshTri
    poly = poly.simplify(0.05)
    ext = np.array(poly.exterior.coords)[:-1]
    n = len(ext)
    verts, segs = list(ext), [[i, (i + 1) % n] for i in range(n)]
    A = dict(vertices=np.array(verts), segments=np.array(segs))
    if refine_at is not None:
        B = tr.triangulate(A, "pq30a%g" % max_area)
        # second pass: refine near the bump
        B = tr.triangulate(dict(vertices=B["vertices"], segments=B.get("segments", A["segments"]), triangles=B["triangles"],
                                triangle_max_area=np.array([a_ref if np.hypot(*(B["vertices"][t].mean(0) - refine_at)) < r_ref else max_area
                                                            for t in B["triangles"]])), "rpq30a")
    else:
        B = tr.triangulate(A, "pq30a%g" % max_area)
    return MeshTri(B["vertices"].T.copy(), B["triangles"].T.copy())


def plate_stiffness(poly, load_xy, E_mpa, t_mm, nu=0.38, r0=2.0, free_line=None, max_area=0.6, clamp_fn=None):
    """Return (k N/mm, w_max mm per N, n_dof). free_line=(m, n) marks mouth facets free: |(x-m).n| < 0.05."""
    from skfem import Basis, ElementTriMorley, BilinearForm, LinearForm, asm, solve, condense
    from skfem.helpers import dd, ddot, trace, eye
    m = mesh_polygon(poly, max_area=max_area, refine_at=load_xy, r_ref=max(3 * r0, 4.0), a_ref=min(0.05, max_area / 6))
    basis = Basis(m, ElementTriMorley())

    @BilinearForm
    def a(u, v, w):
        def C(T):
            return E_mpa / (1 + nu) * (T + nu / (1 - nu) * eye(trace(T), 2))
        return t_mm ** 3 / 12.0 * ddot(C(dd(u)), dd(v))

    cx, cy = load_xy
    q = 1.0 / (math.pi * r0 ** 2)

    @LinearForm
    def f(v, w):
        x, y = w.x
        return q * ((x - cx) ** 2 + (y - cy) ** 2 < r0 ** 2) * v

    K = asm(a, basis); F = asm(f, basis)
    facets = m.boundary_facets()
    if free_line is not None:
        mm, nn = free_line
        mid = m.p[:, m.facets[:, facets]].mean(axis=1)
        d = np.abs((mid[0] - mm[0]) * nn[0] + (mid[1] - mm[1]) * nn[1])
        facets = facets[d > 0.3]
    if clamp_fn is not None:
        mid = m.p[:, m.facets[:, facets]].mean(axis=1)
        facets = facets[np.array([bool(clamp_fn(x, y)) for x, y in mid.T])]
    D = basis.get_dofs(facets).all()
    u = solve(*condense(K, F, D=D))
    from skfem import ElementTriP0
    Ptot = float(asm(LinearForm(lambda v, w: q * (((w.x[0] - cx) ** 2 + (w.x[1] - cy) ** 2) < r0 ** 2) * (1.0 + 0 * v)),
                     Basis(m, ElementTriP0())).sum())
    # deflection at load centre: average vertex value within r0/2
    pv = u[basis.nodal_dofs[0]]
    rr = np.hypot(m.p[0] - cx, m.p[1] - cy)
    near = rr < max(r0 * 0.5, 0.3)
    w0 = float(np.mean(pv[near]) if near.any() else pv[np.argmin(rr)]) / Ptot
    return 1.0 / w0, w0, basis.N, m


def roark_clamped_patch_w(E, t, nu, a, r0, P=1.0):
    """Clamped circular plate, P uniform over a central disc of radius r0: centre deflection.
    Obtained by Maxwell reciprocity from the clamped centre-point-load solution w(r) = P/(16 pi D) [a^2 - r^2 + 2 r^2 ln(r/a)]
    (Timoshenko & Woinowsky-Krieger, Theory of Plates and Shells, 2nd ed., §19) averaged over the disc:
        w0 = P/(16 pi D) (a^2 + r0^2 ln(r0/a) - 3 r0^2 / 4)."""
    D = E * t ** 3 / (12 * (1 - nu ** 2))
    return P / (16 * math.pi * D) * (a ** 2 + r0 ** 2 * math.log(r0 / a) - 0.75 * r0 ** 2)
