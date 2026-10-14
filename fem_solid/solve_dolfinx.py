#!/usr/bin/env python3
"""Reference linear-elastic solver (PR-0.30.2, S07 field/model contracts): dolfinx 0.9 + PETSc CG/GAMG (rigid-body
near-nullspace), P2 vector field on tet10 (or P2 on linear tets). Used inside the pinned container ghcr.io/fenics/dolfinx/dolfinx:v0.9.0.
API: solve(mesh, facet_tags, E, nu, clamp_tags, tractions={tag: callable(x)->(3,N)}, sym_tags=None, rtol=1e-10, order=2, *,
units=("mm", "N", "MPa"), max_it=5000, options_prefix=None) -> (u, vm, sig, info): four entries. u is the P<order> displacement;
vm is von Mises *interpolated* (not L2-projected, not nodally smoothed) into Discontinuous Lagrange(order-1) at that element's
interpolation points (observable dg_vm_interpolation.v1, descriptor in info["observable"]); sig is the UFL stress closure; info
keeps n_dof/ksp_its/ksp_reason/assemble_s/solve_s and adds model, units, realized solver settings and balance diagnostics.
Invalid or unsupported input raises ModelError (typed reason) before any result exists; there is no finite fallback."""
import contextlib, hashlib, itertools, json, math, numbers, time, uuid, weakref
import numpy as np
from mpi4py import MPI
from petsc4py import PETSc
import basix, ufl
from dolfinx import fem, mesh as dmesh
from dolfinx.fem.petsc import assemble_matrix, assemble_vector, apply_lifting, set_bc

MODEL_ID = "dolfinx3d_isotropic_linear_elasticity.cg_gamg.v1"
DG_VM = "dg_vm_interpolation.v1"
DG_COMPONENTS = "dg_cauchy_component_interpolation.v1"
RECOVERY = {"max": "incident_cell_vertex_max.v1", "mean": "incident_cell_vertex_unweighted_mean.v1"}
UNIT_SYSTEMS = {("mm", "N", "MPa"), ("m", "N", "Pa")}  # coherent: stress = force / length^2
FRAME = "cartesian_xyz_right_handed"
WHOLE_DOMAIN = {"id": "whole_domain"}
TIP_ROI = {"id": "tip_annulus_roi.v1", "tip_distance": {"min_inclusive": 4.0, "max_exclusive": 15.0},
           "cut_distance": {"min_exclusive": 3.0}, "units": "mm", "empty": "refused"}
SOLVER_DEFAULTS = {"mg_levels_ksp_type": "chebyshev", "mg_levels_pc_type": "jacobi", "pc_gamg_coarse_eq_limit": 1000}
KSP_ATOL, KSP_DIVTOL, KSP_MAX_IT = 1e-50, 1e4, 5000
BALANCE_ABS, BALANCE_REL = 1e-10, 1e-8  # frozen: |a + b| <= abs (declared N / N*length) + rel * max(|a|, |b|)
REFERENCE_TOL = 1e-12
COMPONENTS = (("xx", 0, 0), ("yy", 1, 1), ("zz", 2, 2), ("xy", 0, 1), ("yz", 1, 2), ("zx", 2, 0))
CONTENT_HASH = "sha256(json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False))"
_ATTEMPT = uuid.uuid4().hex[:12]
_CALLS = itertools.count()
_LIVE_OWNERS = weakref.WeakSet()


class ModelError(ValueError):
    """Typed refusal: `reason` is a stable code, `detail` free text, `info` any diagnostics recorded before refusing."""
    def __init__(self, reason, detail="", info=None):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason, self.detail, self.info = reason, detail, info


def _require(ok, reason, detail=""):
    if not ok: raise ModelError(reason, detail)


def _real(x):
    return isinstance(x, numbers.Real) and not isinstance(x, bool) and math.isfinite(float(x))


def _integer(x):
    return isinstance(x, numbers.Integral) and not isinstance(x, bool)


def _content_sha256(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _get(obj, name):
    """Provider attribute that is a method in some dolfinx releases and a property in others; absent -> typed refusal."""
    try: v = getattr(obj, name)
    except AttributeError as e: raise ModelError("unsupported_provider_api", f"{type(obj).__name__}.{name}") from e
    return v() if callable(v) else v


def _basix_element(V):
    try: return V.ufl_element().basix_element
    except AttributeError as e: raise ModelError("unsupported_provider_api", "ufl_element().basix_element") from e


def interpolation_points(V):
    return np.asarray(_get(V.element, "interpolation_points"), dtype=np.float64)


# ---------------- model, mesh and unit validation ----------------

def validate_units(units):
    _require(type(units) in (tuple, list) and tuple(units) in UNIT_SYSTEMS, "incoherent_units",
             f"{units!r}; supported {sorted(UNIT_SYSTEMS)} (stress = force / length^2)")
    return {"length": units[0], "force": units[1], "stress": units[2], "moment": f"{units[1]}*{units[0]}", "energy": f"{units[1]}*{units[0]}"}


def lame(E, nu):
    _require(_real(E) and E > 0, "invalid_material", f"E={E!r} must be finite and > 0")
    _require(_real(nu) and -1 < nu < 0.5, "invalid_material", f"nu={nu!r} must be finite in (-1, 0.5)")
    lam, mu = E * nu / ((1 + nu) * (1 - 2 * nu)), E / (2 * (1 + nu))
    _require(math.isfinite(lam) and math.isfinite(mu), "invalid_material", "non-finite Lame coefficients")
    return lam, mu


def elastic_stress(E, nu):
    """(eps, sig) UFL closures for isotropic linear elasticity; validates E, nu first."""
    lam, mu = lame(E, nu)
    eps = lambda w: ufl.sym(ufl.grad(w))
    return eps, (lambda w: 2 * mu * eps(w) + lam * ufl.tr(eps(w)) * ufl.Identity(3))


def von_mises(s):
    dev = s - ufl.tr(s) / 3 * ufl.Identity(3)
    return ufl.sqrt(1.5 * ufl.inner(dev, dev))


def validate_order(order):
    _require(_integer(order) and order >= 1, "invalid_order", f"order={order!r} must be an integer >= 1")
    _require(order in (1, 2), "unsupported_order", f"order={order} is not a validated solution order (1 or 2)")
    return int(order)


def _coordinate_degree(msh):
    try: k = int(msh.geometry.cmap.degree)
    except AttributeError as e: raise ModelError("unsupported_provider_api", "geometry.cmap.degree") from e
    _require(k in (1, 2), "unsupported_coordinate_order", f"coordinate degree {k}; only tet4 (1) and tet10 (2) are supported")
    return k


def _check_tet_mesh(msh):
    """Cheap structural gate run before any indexing: serial, 3D tetrahedra, coordinate degree 1 or 2."""
    _require(msh.comm.size == 1, "unsupported_mesh", "serial meshes only")
    _require(msh.topology.dim == 3 and msh.geometry.dim == 3, "unsupported_mesh", "3D solids only")
    _require(msh.topology.cell_type == dmesh.CellType.tetrahedron, "unsupported_mesh", f"{msh.topology.cell_type}")
    return _coordinate_degree(msh)


def _vertex_nodes(msh):
    """Geometry node of every topological vertex through the geometry entity map (entity-to-cell links created first)."""
    msh.topology.create_connectivity(0, 3)
    n = msh.topology.index_map(0).size_local
    return dmesh.entities_to_geometry(msh, 0, np.arange(n, dtype=np.int32)).reshape(-1)


def mesh_identity(msh):
    """Raw-byte SHA256 of geometry x (float64 LE), geometry dofmap and cell-vertex links (int64 LE) plus counts."""
    k = _check_tet_mesh(msh)
    c2v = msh.topology.connectivity(3, 0)
    h = hashlib.sha256()
    for a in (np.ascontiguousarray(msh.geometry.x, dtype="<f8"), np.ascontiguousarray(msh.geometry.dofmap, dtype="<i8"),
              np.ascontiguousarray(c2v.array, dtype="<i8"), np.ascontiguousarray(c2v.offsets, dtype="<i8")):
        h.update(str(a.shape).encode()); h.update(a.tobytes())
    return {"sha256": h.hexdigest(), "algorithm": "sha256(shape|bytes of x<f8, geometry dofmap<i8, c2v array<i8, offsets<i8)",
            "coordinate_degree": k, "cells": int(msh.topology.index_map(3).size_local),
            "vertices": int(msh.topology.index_map(0).size_local), "geometry_nodes": int(msh.geometry.x.shape[0])}


def validate_mesh(msh):
    """Serial, finite, connected tet4/tet10 solid with strictly positive Jacobian at the reference vertices, centroid and
    degree-2 quadrature points of every cell. A negative determinant of the constructed map is an inverted cell; sampling
    is not a proof for every curved-element point."""
    k = _check_tet_mesh(msh)
    x = msh.geometry.x
    _require(np.isfinite(x).all(), "nonfinite_geometry")
    ncell = msh.topology.index_map(3).size_local
    _require(ncell > 0, "unsupported_mesh", "no cells")
    qp, _ = basix.make_quadrature(basix.CellType.tetrahedron, 2)
    pts = np.vstack([basix.geometry(basix.CellType.tetrahedron), [[0.25, 0.25, 0.25]], qp]).astype(np.float64)
    cells = np.arange(ncell, dtype=np.int32)
    det = fem.Expression(ufl.JacobianDeterminant(msh), pts).eval(msh, cells).reshape(ncell, -1)
    c2v = msh.topology.connectivity(3, 0).array.reshape(ncell, 4)
    vx = x[_vertex_nodes(msh)]
    edge = np.max([np.linalg.norm(vx[c2v[:, i]] - vx[c2v[:, j]], axis=1) for i in range(4) for j in range(i + 1, 4)], axis=0)
    tol = REFERENCE_TOL * edge ** 3
    bad = np.flatnonzero((det <= -tol[:, None]).any(axis=1))
    _require(bad.size == 0, "inverted_cell", f"{bad.size} cells with negative Jacobian, first {bad[:5].tolist()}")
    bad = np.flatnonzero((np.abs(det) <= tol[:, None]).any(axis=1) | ~np.isfinite(det).all(axis=1))
    _require(bad.size == 0, "degenerate_cell", f"{bad.size} cells with zero/non-finite Jacobian, first {bad[:5].tolist()}")
    msh.topology.create_connectivity(2, 3)
    f2c = msh.topology.connectivity(2, 3)
    off = np.asarray(f2c.offsets)
    inner = np.flatnonzero(np.diff(off) == 2)
    pairs = np.asarray(f2c.array)[off[inner][:, None] + np.arange(2)]
    label = np.arange(ncell)
    while True:  # facet-adjacency components by min-label propagation
        new = label.copy()
        np.minimum.at(new, pairs[:, 0], label[pairs[:, 1]]); np.minimum.at(new, pairs[:, 1], label[pairs[:, 0]])
        if np.array_equal(new, label): break
        label = new
    n_comp = np.unique(label).size
    _require(n_comp == 1, "disconnected_mesh", f"{n_comp} facet-connected components; one connected solid required")
    return {"coordinate_degree": k, "cells": int(ncell), "min_jacobian": float(det.min()), "components": 1}


def _tag_geometry(msh, ft, tag, what):
    _require(_integer(tag), "missing_tag", f"{what} tag {tag!r} is not an integer")
    facets = ft.find(tag)
    _require(facets.size > 0, "missing_tag", f"{what} tag {tag} has no facets")
    msh.topology.create_connectivity(2, 3); msh.topology.create_connectivity(3, 2)
    nodes = np.unique(dmesh.entities_to_geometry(msh, msh.topology.dim - 1, facets.astype(np.int32)).reshape(-1))
    return facets, msh.geometry.x[nodes]


def _rigid_rows(x, comps):
    """Rows of the 6 rigid modes (3 translations, rotations about x, y, z) restricted to constrained components."""
    X, Y, Z = np.asarray(x, dtype=np.float64).T
    o, l = np.zeros_like(X), np.ones_like(X)
    modes = np.array([[l, o, o], [o, l, o], [o, o, l], [o, -Z, Y], [Z, o, -X], [-Y, X, o]])  # (mode, component, point)
    return np.concatenate([modes[:, c, :].T for c in comps])


def validate_model(msh, ft, E, nu, clamp_tags, tractions, sym_tags, rtol, order, units, max_it=KSP_MAX_IT):
    """Every check S07 requires before construction of Lame coefficients, spaces or forms. Returns the validated model."""
    unit = validate_units(units)
    lam, mu = lame(E, nu)
    order = validate_order(order)
    _require(_real(rtol) and 0 < rtol < 1, "invalid_rtol", f"rtol={rtol!r} must be finite in (0, 1)")
    _require(_integer(max_it) and max_it >= 0, "invalid_max_it", f"max_it={max_it!r}")
    geo = validate_mesh(msh)
    _require(getattr(ft, "dim", None) == msh.topology.dim - 1, "missing_tag", "facet tags of dimension tdim-1 required")
    _require(type(tractions) is dict and type(clamp_tags) in (list, tuple), "invalid_traction", "tractions dict / clamp list")
    sym_tags = sym_tags or {}
    _require(type(sym_tags) is dict, "invalid_symmetry_component", "sym_tags must be a dict {tag: component}")
    center, scale = msh.geometry.x.mean(axis=0), float(np.ptp(msh.geometry.x, axis=0).max())
    restrained = []
    for tag in sorted(set(clamp_tags)):  # duplicate compatible zero clamps are deduplicated, not conflicting
        _, x = _tag_geometry(msh, ft, tag, "clamp"); restrained.append(_rigid_rows((x - center) / scale, (0, 1, 2)))
    for tag, comp in sym_tags.items():
        _require(_integer(comp) and 0 <= comp <= 2, "invalid_symmetry_component", f"tag {tag}: component {comp!r}")
        _, x = _tag_geometry(msh, ft, tag, "symmetry"); restrained.append(_rigid_rows((x - center) / scale, (int(comp),)))
    for tag, f in tractions.items():
        _, x = _tag_geometry(msh, ft, tag, "traction")
        _require(callable(f), "invalid_traction", f"tag {tag}: not callable")
        val = np.asarray(f(np.ascontiguousarray(x.T)), dtype=np.float64)
        _require(val.shape == (3, x.shape[0]), "invalid_traction", f"tag {tag}: shape {val.shape}, need (3, {x.shape[0]})")
        _require(np.isfinite(val).all(), "invalid_traction", f"tag {tag}: non-finite traction")
    rank = 0
    if restrained:
        s = np.linalg.svd(np.vstack(restrained), compute_uv=False)
        rank = int((s > 1e-10 * s[0]).sum()) if s[0] > 0 else 0
    _require(rank == 6, "insufficient_restraint", f"essential BCs restrain {rank} of 6 rigid modes; pure-traction/mechanism models are unsupported")
    return {"units": unit, "material": {"E": float(E), "nu": float(nu), "lambda": lam, "mu": mu}, "order": order,
            "rtol": float(rtol), "max_it": int(max_it), "mesh": geo, "clamp_tags": sorted({int(t) for t in clamp_tags}),
            "sym_tags": {str(int(t)): int(c) for t, c in sym_tags.items()}, "traction_tags": sorted(int(t) for t in tractions),
            "rigid_restraint_rank": rank}


# ---------------- solver settings, options ownership, rigid-mode owners ----------------

class RigidModeOwner:
    """Owns the Functions whose arrays back the near-nullspace vectors; keep it alive until the KSP, matrix and
    nullspace are destroyed. Replaces the old process-global _KEEP list."""
    def __init__(self, V, functions):
        self.V, self.functions = V, tuple(functions)
        _LIVE_OWNERS.add(self)


def live_rigid_mode_owners():
    return len(_LIVE_OWNERS)


def rigid_mode_owner(V):
    """(nullspace, owner): 6 rigid-body modes (3 translations, 3 rotations) as the GAMG near-nullspace."""
    x = V.tabulate_dof_coordinates()  # one row per block (node)
    X, Y, Z = x[:, 0], x[:, 1], x[:, 2]
    cols = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (-Y, X, 0 * X), (0 * X, -Z, Y), (Z, 0 * X, -X)]
    fs = []
    for c in cols:
        f = fem.Function(V); a = f.x.array.reshape(-1, 3)
        for k in range(3): a[:, k] = c[k]
        f.x.scatter_forward(); fs.append(f)
    from dolfinx.la import orthonormalize
    orthonormalize([f.x for f in fs])
    return PETSc.NullSpace().create(vectors=[f.x.petsc_vec for f in fs]), RigidModeOwner(V, fs)


def _check_prefix(prefix):
    _require(type(prefix) is str and prefix[:1].isalpha() and prefix.endswith("_") and prefix.replace("_", "").isalnum(),
             "invalid_options_prefix", repr(prefix))
    return prefix


@contextlib.contextmanager
def owned_options(prefix, defaults):
    """Set `defaults` under the call-owned options prefix; restore overwritten keys and delete new ones on exit."""
    opts, saved = PETSc.Options(), {}
    try:
        for k, v in defaults.items():
            key = prefix + k
            saved[key] = opts.getString(key) if opts.hasName(key) else None
            opts[key] = v
        yield
    finally:
        for key, old in saved.items():
            if old is None: opts.delValue(key)
            else: opts[key] = old


def provider_identity():
    import dolfinx, mpi4py, petsc4py
    mods = {"dolfinx": dolfinx, "basix": basix, "ufl": ufl, "petsc4py": petsc4py, "mpi4py": mpi4py, "numpy": np}
    return {"versions": {k: str(getattr(m, "__version__", None)) for k, m in mods.items()},
            "dolfinx_git": str(getattr(dolfinx, "git_commit_hash", None)), "petsc": ".".join(map(str, PETSc.Sys.getVersion())),
            "scalar": str(np.dtype(PETSc.ScalarType)), "petsc_int": str(np.dtype(PETSc.IntType)),
            "mpi_library": MPI.Get_library_version().strip().splitlines()[0], "module_files": {k: getattr(m, "__file__", None) for k, m in mods.items()}}


def realized_solver_contract(ksp, *, expected, provider, effective_options):
    """Read what PETSc actually realized (after setFromOptions and the final explicit tolerances) and refuse anything but
    the expected settings before solving. Only then is the cg_gamg model identity emitted."""
    rtol, atol, divtol, max_it = ksp.getTolerances()
    actual = {"ksp_type": ksp.getType(), "pc_type": ksp.getPC().getType(), "rtol": float(rtol), "atol": float(atol),
              "divtol": float(divtol), "max_it": int(max_it), "prefix": ksp.getOptionsPrefix()}
    bad = {k: (actual.get(k), v) for k, v in {**expected, "ksp_type": "cg", "pc_type": "gamg"}.items() if actual.get(k) != v}
    if bad: raise ModelError("unsupported_solver_configuration", f"actual vs expected {bad}", info={"actual": actual})
    eff = {str(k): str(v) for k, v in sorted(effective_options.items())}
    return {**actual, "model": MODEL_ID, "effective_options": eff, "effective_options_sha256": _content_sha256(eff), "provider": provider}


def krylov_solve(A, b, x, comm, *, rtol, max_it=KSP_MAX_IT, options_prefix=None, defaults=None):
    """Shared CG/GAMG solve: call-owned prefix and default options, setFromOptions, final explicit tolerances, realized
    settings check, solve, reason>0. Options are restored and the KSP destroyed in all cases. Returns (settings, stats)."""
    prefix = _check_prefix(options_prefix or f"s07_{_ATTEMPT}_{next(_CALLS)}_")
    defaults = SOLVER_DEFAULTS if defaults is None else defaults
    expected = {"ksp_type": "cg", "pc_type": "gamg", "rtol": float(rtol), "atol": KSP_ATOL, "divtol": KSP_DIVTOL, "max_it": int(max_it), "prefix": prefix}
    ksp = PETSc.KSP().create(comm)
    try:
        with owned_options(prefix, defaults):
            ksp.setOptionsPrefix(prefix); ksp.setOperators(A); ksp.setType("cg"); ksp.getPC().setType("gamg")
            ksp.setFromOptions(); ksp.setTolerances(rtol=rtol, atol=KSP_ATOL, divtol=KSP_DIVTOL, max_it=max_it)
            eff = {k: v for k, v in PETSc.Options().getAll().items() if k.startswith(prefix)}
            settings = realized_solver_contract(ksp, expected=expected, provider=provider_identity(), effective_options=eff)
            ksp.solve(b, x)
            stats = {"ksp_its": int(ksp.getIterationNumber()), "ksp_reason": int(ksp.getConvergedReason()),
                     "ksp_residual_norm": float(ksp.getResidualNorm()), "ksp_norm_type": int(ksp.getNormType())}
    finally:
        ksp.destroy()
    if stats["ksp_reason"] <= 0: raise ModelError("ksp_not_converged", f"{stats}", info={"settings": settings, **stats})
    return settings, stats


# ---------------- field extraction, descriptors, association and recovery ----------------

def _dg_space(msh, order):
    order = validate_order(order)
    _check_tet_mesh(msh)
    return fem.functionspace(msh, ("Discontinuous Lagrange", order - 1))


def _context(units, frame, region):
    unit = validate_units(units)
    _require(frame == FRAME, "unsupported_frame", f"{frame!r}; only {FRAME}")
    _require(type(region) is dict and type(region.get("id")) is str and region["id"], "invalid_region", repr(region))
    _content_sha256(region)
    return unit, region


def field_descriptor(f, *, operator, quantity, formula, units, frame, region):
    """Descriptor whose basis, sampling, map and mesh entries are derived from the actual Function, not from a label."""
    unit, region = _context(units, frame, region)
    V = f.function_space
    e = _basix_element(V)
    pts = interpolation_points(V)
    body = {"operator": operator, "quantity": quantity, "formula": formula,
            "basis": {"family": str(e.family.name), "discontinuous": bool(e.discontinuous), "degree": int(e.degree),
                      "cell": str(e.cell_type.name), "value_shape": list(f.ufl_shape), "block_size": int(V.dofmap.bs)},
            "sampling": {"kind": "cell_interpolation_points", "reference_points": pts.round(15).tolist(),
                         "interpolation_ident": bool(_get(V.element, "interpolation_ident")), "dofs_per_cell": int(V.dofmap.cell_dofs(0).size)},
            "map": {"reference_to_physical": "Lagrange coordinate element", "coordinate_degree": _coordinate_degree(V.mesh)},
            "units": unit["stress"], "unit_system": [unit["length"], unit["force"], unit["stress"]], "frame": frame, "region": region,
            "mesh": mesh_identity(V.mesh), "not": ["l2_projection", "nodal_smoothing", "volume_weighting"], "content_hash": CONTENT_HASH}
    sha = _content_sha256(body)
    return {**body, "content_sha256": sha, "gci_observable": {"id": f"{operator}@{sha[:16]}", "units": unit["stress"],
            "region": region["id"], "projection": operator, "metric": quantity}}


def dg_von_mises(msh, stress, order, *, units, frame, region):
    """Interpolate (not L2-project) von Mises of the UFL Cauchy tensor `stress` into scalar Discontinuous Lagrange(order-1)
    at the element's interpolation points. Returns (vmh, descriptor)."""
    W = _dg_space(msh, order)
    vmh = fem.Function(W)
    vmh.interpolate(fem.Expression(von_mises(stress), interpolation_points(W)))
    return vmh, field_descriptor(vmh, operator=DG_VM, quantity="von_mises_stress", formula="sqrt(3/2 dev(s):dev(s))",
                                 units=units, frame=frame, region=region)


def dg_stress_components(msh, stress, order, *, units, frame, region):
    """Six signed Cartesian Cauchy components interpolated into scalar DG(order-1); ({name: Function}, descriptor)."""
    W = _dg_space(msh, order)
    out = {}
    for name, a, b in COMPONENTS:
        f = fem.Function(W); f.interpolate(fem.Expression(stress[a, b], interpolation_points(W))); out[name] = f
    return out, field_descriptor(out["xx"], operator=DG_COMPONENTS, quantity="cauchy_stress_component",
                                 formula="s[a,b] for xx,yy,zz,xy,yz,zx (one shared W)", units=units, frame=frame, region=region)


_STATIC = ("operator", "quantity", "formula", "basis", "units", "unit_system", "frame", "region")
_DERIVED = ("sampling", "map", "mesh", "not", "content_hash")


def validate_observable_contract(f, descriptor, expected_descriptor):
    """Bind a producer descriptor to the actual Function and to a trusted expected contract (never derived from the output).
    Generic labels (e.g. {"tier": "T2"}) or relabelled operators are refused."""
    for name, d, keys in (("descriptor", descriptor, _STATIC + _DERIVED + ("content_sha256",)), ("expected", expected_descriptor, _STATIC)):
        _require(type(d) is dict and all(k in d for k in keys), "incomplete_observable_contract",
                 f"{name} lacks {[k for k in keys if type(d) is not dict or k not in d]}")
    _require(expected_descriptor["operator"] in (DG_VM, DG_COMPONENTS), "unsupported_operator", f"{expected_descriptor['operator']!r} is not produced here")
    body = {k: v for k, v in descriptor.items() if k not in ("content_sha256", "gci_observable")}
    _require(_content_sha256(body) == descriptor["content_sha256"], "descriptor_tampered", "content hash mismatch")
    actual = field_descriptor(f, operator=descriptor["operator"], quantity=descriptor["quantity"], formula=descriptor["formula"],
                              units=descriptor["unit_system"], frame=descriptor["frame"], region=descriptor["region"])
    bad = [k for k in _STATIC + _DERIVED if actual[k] != descriptor[k]]
    _require(not bad, "descriptor_mismatch", f"descriptor disagrees with the actual Function on {bad}")
    bad = [k for k in _STATIC if descriptor[k] != expected_descriptor[k]]
    _require(not bad, "descriptor_mismatch", f"descriptor disagrees with the trusted expected contract on {bad}")
    return descriptor


def geometry_vertex_association(msh, f, *, reference_tolerance=REFERENCE_TOL):
    """Exact (W dof, cell, local vertex, topological vertex, geometry node, input node) bijection for a scalar DG1 field:
    Basix interpolation points matched to reference vertices, cell-to-vertex topology, and the geometry entity map (never the
    first geometry dofmap columns), cross-checked against W's tabulated dof coordinates."""
    _check_tet_mesh(msh)  # unsupported coordinate order refuses before any indexing
    V = f.function_space
    _require(V.mesh is msh, "field_mesh_mismatch", "Function lives on a different mesh")
    e = _basix_element(V)
    _require(e.family == basix.ElementFamily.P and e.discontinuous and e.degree == 1 and f.ufl_shape == () and V.dofmap.bs == 1,
             "unsupported_field", f"vertex association needs scalar DG1, got family={e.family.name} discontinuous={e.discontinuous} degree={e.degree} shape={f.ufl_shape}")
    pts, ref = interpolation_points(V), basix.geometry(basix.CellType.tetrahedron)
    _require(pts.shape == (4, 3) and bool(_get(V.element, "interpolation_ident")), "absent_sample_map", "DG1 samples are not identity point evaluations")
    dist = np.abs(pts[:, None, :] - ref[None, :, :]).max(axis=2)
    local = dist.argmin(axis=1)
    _require(np.sort(local).tolist() == [0, 1, 2, 3] and (dist[np.arange(4), local] <= reference_tolerance).all(),
             "absent_sample_map", "interpolation points are not the reference vertices")
    ncell = msh.topology.index_map(3).size_local
    c2v = msh.topology.connectivity(3, 0).array.reshape(ncell, 4)
    dofs = np.asarray(V.dofmap.list).reshape(ncell, 4)
    vert = c2v[:, local]  # dof k sits at reference vertex local[k]
    geo = _vertex_nodes(msh)
    x = msh.geometry.x
    dofx = V.tabulate_dof_coordinates()
    scale = max(float(np.ptp(x, axis=0).max()), 1.0)
    _require(np.abs(dofx[dofs] - x[geo[vert]]).max() <= reference_tolerance * scale * 1e3, "absent_sample_map",
             "W dof coordinates disagree with geometry vertex coordinates")
    return {"cells": ncell, "dofs": dofs, "vertex": vert, "geometry_node": geo, "input_node": np.asarray(msh.geometry.input_global_indices)[geo],
            "coordinates": x[geo], "local_vertex_of_dof": local}


def recover_vertex_vm(msh, f, operator, *, descriptor, expected_descriptor, input_nodes=None):
    """Incident-cell scalar reduction of a validated scalar DG1 field at topological vertices: 'max' or unweighted 'mean'
    (no tensor averaging, no volume weighting, not L2). Optional `input_nodes` selects outputs by input node ID and refuses
    any node without an incident cell instead of padding it with zero."""
    _require(operator in RECOVERY, "unsupported_recovery", f"{operator!r}; supported {sorted(RECOVERY)}")
    validate_observable_contract(f, descriptor, expected_descriptor)
    a = geometry_vertex_association(msh, f)
    val = f.x.array
    _require(np.isfinite(val).all(), "nonfinite_field", f"{int((~np.isfinite(val)).sum())} non-finite samples")
    nv = a["geometry_node"].size
    cnt = np.zeros(nv); acc = np.zeros(nv); mx = np.full(nv, -np.inf)
    for k in range(4):
        np.add.at(cnt, a["vertex"][:, k], 1); np.add.at(acc, a["vertex"][:, k], val[a["dofs"][:, k]])
        np.maximum.at(mx, a["vertex"][:, k], val[a["dofs"][:, k]])
    _require((cnt > 0).all(), "orphan_vertex", f"{int((cnt == 0).sum())} vertices without incident cells")
    out = mx if operator == "max" else acc / cnt
    sel = np.arange(nv)
    if input_nodes is not None:
        where = {int(n): i for i, n in enumerate(a["input_node"])}
        missing = [int(n) for n in input_nodes if int(n) not in where]
        _require(not missing, "orphan_vertex", f"input nodes {missing} have no incident cell")
        sel = np.array([where[int(n)] for n in input_nodes], dtype=np.int64)
    return {"operator": RECOVERY[operator], "values": out[sel], "incidence": cnt[sel].astype(int), "vertex": sel,
            "input_node": a["input_node"][sel], "coordinates": a["coordinates"][sel], "field": descriptor["gci_observable"]}


def tip_roi_mask(tip_distance, cut_distance):
    """Current tip ROI (mm): 4 <= tip distance < 15 and cut distance > 3."""
    d, c = np.asarray(tip_distance, dtype=np.float64), np.asarray(cut_distance, dtype=np.float64)
    _require(np.isfinite(d).all() and np.isfinite(c).all() and d.shape == c.shape, "invalid_region", "ROI distances")
    return (d >= TIP_ROI["tip_distance"]["min_inclusive"]) & (d < TIP_ROI["tip_distance"]["max_exclusive"]) & (c > TIP_ROI["cut_distance"]["min_exclusive"])


def region_extreme(values, mask):
    """Maximum over a required region; an empty region is refused (no fmax=0 / SF=inf substitute)."""
    v, m = np.asarray(values, dtype=np.float64), np.asarray(mask, dtype=bool)
    _require(v.shape == m.shape, "invalid_region", "mask shape")
    _require(m.any(), "empty_region", "required ROI selects no samples")
    _require(np.isfinite(v[m]).all(), "nonfinite_field", "non-finite value in ROI")
    return float(v[m].max())


# ---------------- loads, reactions and energy ----------------

def supplied_load_resultant(msh, ft, tractions):
    """Force and moment about the origin integrated from the supplied traction callables on their own quadratic DG space,
    independently of the RHS assembled for the solve."""
    Q = fem.functionspace(msh, ("Discontinuous Lagrange", 2, (3,)))
    ds = ufl.Measure("ds", domain=msh, subdomain_data=ft)
    xs = ufl.SpatialCoordinate(msh)
    force, moment = np.zeros(3), np.zeros(3)
    for tag, f in tractions.items():
        t = fem.Function(Q); t.interpolate(f)
        m = ufl.cross(xs, t)
        for c in range(3):
            force[c] += fem.assemble_scalar(fem.form(t[c] * ds(tag)))
            moment[c] += fem.assemble_scalar(fem.form(m[c] * ds(tag)))
    return {"force": force.tolist(), "moment_about_origin": moment.tolist()}


def _within(a, b):
    return bool(abs(a + b) <= BALANCE_ABS + BALANCE_REL * max(abs(a), abs(b)))


def balance_diagnostics(V, af, Lf, bcs, uh, eps, sig, applied):
    """Free residual, restrained reactions, balance and W = 2U from the *unconstrained* A0, b0 (never BC-modified rows)."""
    A0 = assemble_matrix(af); A0.assemble()
    b0 = assemble_vector(Lf); b0.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE)
    r = b0.duplicate(); A0.mult(uh.x.petsc_vec, r); r.axpy(-1.0, b0)
    m = fem.Function(V); m.x.array[:] = 1.0; set_bc(m.x.petsc_vec, bcs)
    fixed = (m.x.array == 0.0).reshape(-1, 3)
    rr, bb = r.getArray().copy().reshape(-1, 3), b0.getArray().copy().reshape(-1, 3)
    react = np.where(fixed, rr, 0.0)
    x = V.tabulate_dof_coordinates()
    reaction, reaction_moment = react.sum(axis=0), np.cross(x, react).sum(axis=0)
    r_free, b_free = float(np.linalg.norm(rr[~fixed])), float(np.linalg.norm(bb[~fixed]))
    work, two_u = float(b0.dot(uh.x.petsc_vec)), float(2 * fem.assemble_scalar(fem.form(0.5 * ufl.inner(sig(uh), eps(uh)) * ufl.dx)))
    for o in (A0, b0, r): o.destroy()
    out = {"free_residual_l2": r_free, "free_rhs_l2": b_free, "free_residual_ratio": r_free / b_free if b_free > 0 else None,
           "free_residual_ok": bool(r_free <= BALANCE_ABS + BALANCE_REL * b_free),
           "reaction_force": reaction.tolist(), "reaction_moment_about_origin": reaction_moment.tolist(),
           "applied_force": applied["force"], "applied_moment_about_origin": applied["moment_about_origin"],
           "work": work, "two_strain_energy": two_u, "strain_energy": two_u / 2,
           "work_equals_two_energy": bool(abs(work - two_u) <= BALANCE_ABS + BALANCE_REL * max(abs(work), abs(two_u)))}
    out["force_balance"] = [_within(p, q) for p, q in zip(applied["force"], out["reaction_force"])]
    out["moment_balance"] = [_within(p, q) for p, q in zip(applied["moment_about_origin"], out["reaction_moment_about_origin"])]
    out["balance_ok"] = bool(all(out["force_balance"]) and all(out["moment_balance"]) and out["free_residual_ok"] and out["work_equals_two_energy"])
    return out


def solve(msh, ft, E, nu, clamp_tags, tractions, sym_tags=None, rtol=1e-10, order=2, *, units=("mm", "N", "MPa"),
          max_it=KSP_MAX_IT, options_prefix=None):
    """sym_tags: {facet tag: component} -> u[component] = 0 on that facet set (symmetry planes). Homogeneous essential BCs only."""
    t0 = time.time()
    model = validate_model(msh, ft, E, nu, clamp_tags, tractions, sym_tags, rtol, order, units, max_it)
    V = fem.functionspace(msh, ("Lagrange", order, (3,)))
    eps, sig = elastic_stress(E, nu)
    u, v = ufl.TrialFunction(V), ufl.TestFunction(V)
    ds = ufl.Measure("ds", domain=msh, subdomain_data=ft)
    a = ufl.inner(sig(u), eps(v)) * ufl.dx
    L = ufl.inner(fem.Constant(msh, np.zeros(3)), v) * ufl.dx
    for tag, f in tractions.items():
        tf = fem.Function(V); tf.interpolate(f); L = L + ufl.inner(tf, v) * ds(tag)
    fdim = msh.topology.dim - 1
    bcs = []
    for tag in model["clamp_tags"]:
        dofs = fem.locate_dofs_topological(V, fdim, ft.find(tag))
        bcs.append(fem.dirichletbc(np.zeros(3), dofs, V))
    for tag, comp in (sym_tags or {}).items():
        Vc, _ = V.sub(comp).collapse()
        dofs = fem.locate_dofs_topological((V.sub(comp), Vc), fdim, ft.find(tag))
        z = fem.Function(Vc); bcs.append(fem.dirichletbc(z, dofs, V.sub(comp)))
    af, Lf = fem.form(a), fem.form(L)
    A = assemble_matrix(af, bcs=bcs); A.assemble()
    b = assemble_vector(Lf); apply_lifting(b, [af], bcs=[bcs]); b.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE); set_bc(b, bcs)
    ns, owner = rigid_mode_owner(V)
    uh = fem.Function(V)
    try:
        A.setNearNullSpace(ns)
        t1 = time.time()
        settings, stats = krylov_solve(A, b, uh.x.petsc_vec, msh.comm, rtol=rtol, max_it=max_it, options_prefix=options_prefix)
        uh.x.scatter_forward()
    finally:  # the owner outlives every PETSc object that references its vectors
        A.destroy(); b.destroy(); ns.destroy(); del owner
    t2 = time.time()
    _require(np.isfinite(uh.x.array).all(), "nonfinite_result", "displacement")
    vmh, observable = dg_von_mises(msh, sig(uh), order, units=units, frame=FRAME, region=WHOLE_DOMAIN)
    _require(np.isfinite(vmh.x.array).all(), "nonfinite_result", "von Mises")
    diagnostics = balance_diagnostics(V, af, Lf, bcs, uh, eps, sig, supplied_load_resultant(msh, ft, tractions))
    info = dict(n_dof=V.dofmap.index_map.size_global * 3, ksp_its=stats["ksp_its"], ksp_reason=stats["ksp_reason"],
                assemble_s=round(t1 - t0, 2), solve_s=round(t2 - t1, 2), model=MODEL_ID, units=model["units"],
                validated_model=model, solver={**settings, **stats}, observable=observable, diagnostics=diagnostics)
    return uh, vmh, sig, info
