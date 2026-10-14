"""S07 / T05 field-semantics controls on actual dolfinx Functions (T05-02 association, T05-07, T05-08, T05-09 producer) and
the S07 observable catalog / phase registration.

Manufactured fields are interpolated exactly (P2 displacement, DG0/DG1 tensors) and pass through the production
dg_von_mises / validate_observable_contract / geometry_vertex_association / recover_vertex_vm path. Expected descriptors
come from the trusted catalog, never from the output. Operator classes raise a required-capability ERROR when the provider
is missing (never a skip); the Catalog class needs only the standard library and the accepted assurance package."""
import ast, hashlib, json, math, os, re, sys, unittest
from fractions import Fraction
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from assurance.testing.catalog import bind_policy
from assurance.testing.contracts import scientific_hash, unique_ids, validate_case
try:
    import basix, basix.ufl, ufl
    from mpi4py import MPI
    from dolfinx import fem, geometry, mesh as dmesh
    from dolfinx.fem.petsc import assemble_matrix
    from fem_solid import solve_dolfinx as S
    PROVIDER_ERROR = None
except ImportError as error:
    PROVIDER_ERROR = error

E, NU, YIELD = 1000.0, 0.0, 828.0
MM = ("mm", "N", "MPa")
FIELD_REL, FIELD_ABS = 1e-9, 1e-10  # frozen manufactured-field tolerance (MPa)
NORM_REL, NORM_ABS = 1e-9, 1e-12    # frozen spatial-norm tolerance
CATALOG_PATH = os.path.join(ROOT, "assurance", "numerical", "observable_catalog.json")
CATALOG = json.load(open(CATALOG_PATH))
EXPECTED = {o["key"]: o["descriptor"] for o in CATALOG["observables"]}
VM_DG1, VM_DG0 = EXPECTED["dg_vm_interpolation.v1/P2-DG1/mm"], EXPECTED["dg_vm_interpolation.v1/P1-DG0/mm"]
TET = [[-1, 0, 0], [1, 0, 0], [-1, 1, 0], [-1, 0, 1]]
NEW_TO_OLD, OLD_TO_NEW, REMAPPED_CELL = [2, 0, 3, 1], [1, 3, 0, 2], [1, 3, 0, 2]


def close(a, b, rel=FIELD_REL, abs_tol=FIELD_ABS):
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= abs_tol + rel * max(abs(a), abs(b))


def allclose(got, want, **kw):
    got, want = np.asarray(got, dtype=float).ravel(), np.asarray(want, dtype=float).ravel()
    return got.shape == want.shape and all(close(a, b, **kw) for a, b in zip(got, want))


def record(row, **kv):
    print("T05 " + json.dumps({"row": row, **kv}, sort_keys=True, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


def laundered(descriptor, **changes):
    """Relabel a descriptor and re-seal its content hash, i.e. the strongest metadata-only laundering."""
    body = {k: v for k, v in descriptor.items() if k not in ("content_sha256", "gci_observable")}
    body.update(changes)
    sha = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return {**body, "content_sha256": sha}


def lagrange_mesh(vertices, cells, degree=1):
    """Mesh from vertex rows and cells; for degree > 1 each cell's extra nodes are the Basix equispaced reference points
    pushed through that cell's affine map (single-cell meshes only)."""
    vertices, cells = np.asarray(vertices, dtype=np.float64), np.asarray(cells, dtype=np.int64)
    variant = basix.LagrangeVariant.equispaced
    cel = basix.ufl.element("Lagrange", "tetrahedron", degree, lagrange_variant=variant, shape=(3,))
    if degree == 1:
        return dmesh.create_mesh(MPI.COMM_WORLD, cells, vertices, ufl.Mesh(cel))
    assert cells.shape[0] == 1
    ref = basix.create_element(basix.ElementFamily.P, basix.CellType.tetrahedron, degree, variant).points
    p = vertices[cells[0]]
    nodes = p[0] + ref @ (p[1:] - p[0])
    x = np.vstack([vertices, nodes[4:]])
    cell = np.concatenate([cells[0], np.arange(len(vertices), len(vertices) + len(nodes) - 4)])[None, :]
    return dmesh.create_mesh(MPI.COMM_WORLD, cell, x, ufl.Mesh(cel))


def probe(msh, f, pts):
    pts = np.asarray(pts, dtype=np.float64)
    tree = geometry.bb_tree(msh, msh.topology.dim)
    cells = geometry.compute_colliding_cells(msh, geometry.compute_collisions_points(tree, pts), pts)
    return f.eval(pts, [cells.links(i)[0] for i in range(len(pts))])


def manufactured_vm(msh, ux):
    """Exact P2 displacement (ux(x), 0, 0) -> production stress closure -> production DG1 von Mises interpolation."""
    V = fem.functionspace(msh, ("Lagrange", 2, (3,)))
    uh = fem.Function(V); uh.interpolate(lambda x: np.vstack([ux(x[0]), 0 * x[0], 0 * x[0]]))
    _, sig = S.elastic_stress(E, NU)
    vmh, desc = S.dg_von_mises(msh, sig(uh), 2, units=MM, frame=S.FRAME, region=S.WHOLE_DOMAIN)
    return uh, sig, vmh, desc


def pointwise_vm(msh, sig, uh, ref_point):
    return float(fem.Expression(S.von_mises(sig(uh)), np.array([ref_point], dtype=np.float64)).eval(msh, np.array([0], dtype=np.int32)).ravel()[0])


class Operator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PROVIDER_ERROR is not None:
            raise RuntimeError(f"required T05 operator capability missing (incomplete, not skipped): {PROVIDER_ERROR!r}")

    def assertRefused(self, reason, fn, *a, **kw):
        with self.assertRaises(S.ModelError) as cm: fn(*a, **kw)
        self.assertEqual(cm.exception.reason, reason, str(cm.exception))
        return cm.exception

    def vertex_vm(self, msh, vmh, desc, nodes, op="max", expected=VM_DG1):
        return S.recover_vertex_vm(msh, vmh, op, descriptor=desc, expected_descriptor=expected, input_nodes=nodes)


X_PLUS_2 = lambda x: (x * x / 2 + 2 * x) / E  # sigma_xx = x + 2, VM |x + 2|


class Association(Operator):
    def remapped(self, degree, ux=X_PLUS_2):
        out = {}
        for name, verts, cell in (("original", TET, [0, 1, 2, 3]), ("remapped", [TET[o] for o in NEW_TO_OLD], REMAPPED_CELL)):
            msh = lagrange_mesh(verts, [cell], degree)
            uh, sig, vmh, desc = manufactured_vm(msh, ux)
            S.validate_observable_contract(vmh, desc, VM_DG1)
            rec = self.vertex_vm(msh, vmh, desc, [0, 1, 2, 3])
            out[name] = {"msh": msh, "vm": rec["values"], "rec": rec, "centroid_dg": float(probe(msh, vmh, [[-0.5, 0.25, 0.25]])[0][0]),
                         "centroid_point": pointwise_vm(msh, sig, uh, [0.25, 0.25, 0.25]), "identity": desc["mesh"]}
        return out

    def check_valid(self, row, degree):
        r = self.remapped(degree)
        self.assertTrue(allclose(r["original"]["vm"], [1, 3, 1, 1]))
        self.assertTrue(allclose(r["remapped"]["vm"], [1, 1, 1, 3]))
        self.assertTrue(allclose(np.asarray(r["remapped"]["vm"])[OLD_TO_NEW], [1, 3, 1, 1]), "inverse remap recovers the original order")
        for k in r: self.assertTrue(close(r[k]["centroid_dg"], 1.5) and close(r[k]["centroid_point"], 1.5))
        record(row, **{k: {"vm": v["vm"], "centroid_dg": v["centroid_dg"], "centroid_point": v["centroid_point"], "mesh": v["identity"]} for k, v in r.items()})
        return r

    def test_t05_02_rev_valid_tet4(self):
        r = self.check_valid("02-rev-valid-tet4", 1)
        self.assertEqual((r["remapped"]["identity"]["geometry_nodes"], r["remapped"]["identity"]["vertices"]), (4, 4))

    def test_t05_02_rev_valid_tet10(self):
        r = self.check_valid("02-rev-valid-tet10", 2)
        ident = r["remapped"]["identity"]
        self.assertEqual((ident["coordinate_degree"], ident["geometry_nodes"], ident["vertices"]), (2, 10, 4))
        self.assertEqual(len(r["remapped"]["rec"]["values"]), 4, "mid-side geometry nodes are not vertex outputs")

    def test_t05_02_rev_constant_retained(self):
        r = self.remapped(1, lambda x: 2 * x / E)
        for k in r: self.assertTrue(allclose(r[k]["vm"], [2, 2, 2, 2]) and close(r[k]["centroid_dg"], 2.0))
        record("02-rev-constant-retained", **{k: v["vm"] for k, v in r.items()})

    def test_t05_02_rev_wrong_map(self):
        r = self.remapped(1)
        wrong = np.asarray(r["original"]["vm"])  # mutant: unremapped samples paired with the new topology
        bad = [i for i in range(4) if not close(wrong[i], [1, 1, 1, 3][i])]
        self.assertEqual(bad, [1, 3])
        self.assertTrue(allclose(r["remapped"]["vm"], [1, 1, 1, 3]))
        record("02-rev-wrong-map", mutant=wrong, detected_at=bad)

    def test_t05_02_rev_reject_all_remaps(self):
        r = self.remapped(1)  # a reject-all producer would raise here; the nonconstant remap must succeed exactly
        self.assertTrue(allclose(np.asarray(r["remapped"]["vm"])[OLD_TO_NEW], r["original"]["vm"]))
        record("02-rev-reject-all-remaps", accepted=True)

    def test_t05_02_rev_unsupported_geometry3(self):
        msh = lagrange_mesh(TET, [[0, 1, 2, 3]], 3)
        f = fem.Function(fem.functionspace(msh, ("Discontinuous Lagrange", 1)))
        e = self.assertRefused("unsupported_coordinate_order", S.geometry_vertex_association, msh, f)
        self.assertRefused("unsupported_coordinate_order", S.validate_mesh, msh)
        self.assertRefused("unsupported_coordinate_order", S.dg_von_mises, msh, ufl.Identity(3), 2, units=MM, frame=S.FRAME, region=S.WHOLE_DOMAIN)
        record("02-rev-unsupported-geometry3", refused=e.reason, stage="before indexing")


class FieldSemantics(Operator):
    def tet(self, ux):
        msh = lagrange_mesh(TET, [[0, 1, 2, 3]], 1)
        uh, sig, vmh, desc = manufactured_vm(msh, ux)
        return msh, uh, sig, vmh, desc

    def test_t05_07_positive(self):
        msh, uh, sig, vmh, desc = self.tet(lambda x: x * x / (2 * E))  # sigma_xx = x, VM |x|
        S.validate_observable_contract(vmh, desc, VM_DG1)
        vm = self.vertex_vm(msh, vmh, desc, [0, 1, 2, 3])["values"]
        dg_c, point_c = float(probe(msh, vmh, [[-0.5, 0.25, 0.25]])[0][0]), pointwise_vm(msh, sig, uh, [0.25, 0.25, 0.25])
        self.assertTrue(allclose(vm, [1, 1, 1, 1]) and close(dg_c, 1.0) and close(point_c, 0.5))
        self.assertEqual(desc["operator"], "dg_vm_interpolation.v1"); self.assertIn("l2_projection", desc["not"])
        msh2, _, _, vmc, descc = self.tet(lambda x: 2 * x / E)
        self.assertTrue(allclose(vmc.x.array, np.full(vmc.x.array.shape, 2.0)))
        record("07-positive", vertex_vm=vm, dg1_centroid=dg_c, pointwise_centroid=point_c, constant=vmc.x.array)

    def test_t05_07_adverse(self):
        msh, uh, sig, vmh, desc = self.tet(lambda x: x * x / (2 * E))
        table = [("1", "L2_projection", dict(operator="L2_projection")),
                 ("2", "continuous_P1_nodal_VM", dict(operator="continuous_P1_nodal_VM", basis={**desc["basis"], "discontinuous": False}))]
        for row, literal, change in table:
            with self.subTest(row=row, literal=literal):
                fake = laundered(desc, **change)
                a = self.assertRefused("descriptor_mismatch", S.validate_observable_contract, vmh, fake, VM_DG1)
                b = self.assertRefused("unsupported_operator", S.validate_observable_contract, vmh, fake, laundered(VM_DG1, **change))
                record(f"07-adverse/original/{row}", literal=literal, refused=[a.detail, b.detail],
                       inherited_regression="interpolated_field_is_not_labeled_as_l2_projection")

    INC_VERTS = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, -3]]
    INC_CELLS = [[0, 1, 2, 3], [0, 2, 1, 4]]

    def incidence(self):
        msh = lagrange_mesh(self.INC_VERTS, self.INC_CELLS, 1)
        T = fem.Function(fem.functionspace(msh, ("Discontinuous Lagrange", 0, (3, 3))))
        inputs = np.asarray(msh.geometry.input_global_indices)[np.asarray(msh.geometry.dofmap)]
        sxx = {}
        for c in range(inputs.shape[0]):  # identify each dolfinx cell by its input vertex 3 (cell 0) or 4 (cell 1)
            value = 1.0 if 3 in inputs[c] else -3.0
            T.x.array.reshape(-1, 9)[T.function_space.dofmap.cell_dofs(c)[0], 0] = value; sxx[c] = value
        vmh, desc = S.dg_von_mises(msh, T, 2, units=MM, frame=S.FRAME, region=S.WHOLE_DOMAIN)
        q0 = fem.functionspace(msh, ("Discontinuous Lagrange", 0))
        vol = fem.assemble_vector(fem.form(ufl.TestFunction(q0) * ufl.dx)).array
        vol = {c: vol[q0.dofmap.cell_dofs(c)[0]] for c in sxx}
        return msh, vmh, desc, sxx, vol

    def test_t05_07_rev_signed_incidence(self):
        msh, vmh, desc, sxx, vol = self.incidence()
        mean = self.vertex_vm(msh, vmh, desc, [0, 1, 2, 3, 4], "mean")
        mx = self.vertex_vm(msh, vmh, desc, [0, 1, 2, 3, 4], "max")
        self.assertTrue(allclose(mean["values"], [2, 2, 2, 1, 3]) and allclose(mx["values"], [3, 3, 3, 1, 3]))
        self.assertEqual(mean["incidence"].tolist(), [2, 2, 2, 1, 1])
        self.assertEqual(sorted(round(6 * v) for v in vol.values()), [1, 3])  # volumes 1/6 and 1/2
        record("07-rev-signed-incidence", mean=mean["values"], max=mx["values"], operator=[mean["operator"], mx["operator"]])

    def test_t05_07_rev_tensor_first(self):
        msh, vmh, desc, sxx, vol = self.incidence()
        mutant = abs(sum(sxx.values()) / len(sxx))  # average signed tensors at a shared vertex, then VM
        production = self.vertex_vm(msh, vmh, desc, [0], "mean")["values"][0]
        self.assertTrue(close(production, 2.0)); self.assertTrue(close(mutant, 1.0)); self.assertFalse(close(mutant, 2.0))
        record("07-rev-tensor-first", production=production, mutant=mutant)

    def test_t05_07_rev_volume_weighted(self):
        msh, vmh, desc, sxx, vol = self.incidence()
        mutant = sum(vol[c] * abs(sxx[c]) for c in sxx) / sum(vol.values())  # volume-weighted scalar VM
        tensor_weighted = abs(sum(vol[c] * sxx[c] for c in sxx) / sum(vol.values()))
        production = self.vertex_vm(msh, vmh, desc, [0], "mean")["values"][0]
        self.assertTrue(close(production, 2.0) and close(mutant, 2.5) and close(tensor_weighted, 2.0)); self.assertFalse(close(mutant, 2.0))
        record("07-rev-volume-weighted", production=production, mutant=mutant, vm_weighted_tensor_mean=tensor_weighted)

    def test_t05_07_unsupported_recovery(self):
        msh, uh, sig, vmh, desc = self.tet(lambda x: x * x / (2 * E))
        dg0, d0 = S.dg_von_mises(msh, sig(uh), 1, units=MM, frame=S.FRAME, region=S.WHOLE_DOMAIN)
        W2 = fem.functionspace(msh, ("Discontinuous Lagrange", 2))
        dg2 = fem.Function(W2); dg2.interpolate(fem.Expression(S.von_mises(sig(uh)), S.interpolation_points(W2)))
        d2 = S.field_descriptor(dg2, operator=S.DG_VM, quantity=desc["quantity"], formula=desc["formula"], units=MM, frame=S.FRAME, region=S.WHOLE_DOMAIN)
        other = lagrange_mesh(TET, [[0, 1, 2, 3]], 1)
        nan = fem.Function(vmh.function_space); nan.x.array[:] = vmh.x.array; nan.x.array[0] = np.nan
        orphan = lagrange_mesh(TET + [[5.0, 5.0, 5.0]], [[0, 1, 2, 3]], 1)  # input node 4 is referenced by no cell
        _, _, vmo, do = manufactured_vm(orphan, lambda x: x * x / (2 * E))
        no_map = {k: v for k, v in desc.items() if k != "sampling"}
        table = [("1", 0, "unsupported_field", lambda: S.recover_vertex_vm(msh, dg0, "max", descriptor=d0, expected_descriptor=VM_DG0)),
                 ("2", 2, "unsupported_field", lambda: S.recover_vertex_vm(msh, dg2, "max", descriptor=d2, expected_descriptor={k: d2[k] for k in VM_DG1})),
                 ("3", "mismatched mesh Function", "field_mesh_mismatch", lambda: S.recover_vertex_vm(other, vmh, "max", descriptor=desc, expected_descriptor=VM_DG1)),
                 ("4", "absent sample map", "incomplete_observable_contract", lambda: S.recover_vertex_vm(msh, vmh, "max", descriptor=no_map, expected_descriptor=VM_DG1)),
                 ("5", "nonfinite VM", "nonfinite_field", lambda: S.recover_vertex_vm(msh, nan, "max", descriptor=desc, expected_descriptor=VM_DG1)),
                 ("6", "orphan unreferenced nodes", "orphan_vertex", lambda: self.vertex_vm(orphan, vmo, do, [0, 1, 2, 3, 4]))]
        for row, literal, reason, call in table:
            with self.subTest(row=row, literal=literal):
                e = self.assertRefused(reason, call)
                record(f"07-unsupported-recovery/original/{row}", literal=literal, refused=e.reason, detail=e.detail)
        healthy = self.vertex_vm(orphan, vmo, do, [0, 1, 2, 3])["values"]
        self.assertTrue(allclose(healthy, [1, 1, 1, 1]), "referenced nodes still recover; no zero padding")


class LocalizedPeak(Operator):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        msh = dmesh.create_box(MPI.COMM_WORLD, [[0, 0, 0], [1, 1, 1]], [10, 10, 10], dmesh.CellType.tetrahedron)
        T = fem.Function(fem.functionspace(msh, ("Discontinuous Lagrange", 1, (3, 3))))
        T.x.array.reshape(-1, 9)[:, 0] = 1.0
        T.x.array.reshape(-1, 9)[T.function_space.dofmap.cell_dofs(0)[0], 0] = 3.0  # one cell-vertex sample of cell 0
        vmh, desc = S.dg_von_mises(msh, T, 2, units=MM, frame=S.FRAME, region=S.WHOLE_DOMAIN)
        W = vmh.function_space
        base = fem.Function(W); base.x.array[:] = 1.0
        delta = fem.Function(W); delta.x.array[:] = vmh.x.array - base.x.array
        cls.msh, cls.vmh, cls.desc, cls.W, cls.base, cls.delta = msh, vmh, desc, W, base, delta

    def spatial(self):
        dx = ufl.dx(metadata={"quadrature_degree": 2})
        num = fem.assemble_scalar(fem.form(ufl.inner(self.delta, self.delta) * dx))
        return num / fem.assemble_scalar(fem.form(ufl.inner(self.base, self.base) * dx)), num

    def test_t05_08_rev_discrete_norm(self):
        d = self.delta.x.array
        self.assertEqual(d.size, 24000)
        sq = float(np.dot(d, d) / np.dot(self.base.x.array, self.base.x.array))
        self.assertTrue(close(sq, 1 / 6000, NORM_REL, NORM_ABS))
        record("08-rev-discrete-norm", identity="discrete_nodal_relative_l2.v1", squared=sq)

    def test_t05_08_rev_spatial_integral(self):
        sq, num = self.spatial()
        self.assertTrue(close(sq, 1 / 15000, NORM_REL, NORM_ABS) and close(num, 1 / 15000, NORM_REL, NORM_ABS))
        record("08-rev-spatial-integral", identity="spatial_fe_relative_l2.v1", squared=sq)

    def test_t05_08_rev_mass_matrix(self):
        u, v = ufl.TrialFunction(self.W), ufl.TestFunction(self.W)
        M = assemble_matrix(fem.form(u * v * ufl.dx)); M.assemble()
        dofs = self.W.dofmap.cell_dofs(0)
        block = np.array([[M.getValue(int(i), int(j)) for j in dofs] for i in dofs]); M.destroy()
        V = 1 / 6000
        self.assertTrue(allclose(np.diag(block), [V / 10] * 4, rel=NORM_REL, abs_tol=NORM_ABS))
        self.assertTrue(allclose(block[~np.eye(4, dtype=bool)], [V / 20] * 12, rel=NORM_REL, abs_tol=NORM_ABS))
        delta = self.delta.x.array[dofs]
        self.assertEqual(sorted(delta.tolist()), [0.0, 0.0, 0.0, 2.0])
        self.assertTrue(close(float(delta @ block @ delta), 1 / 15000, NORM_REL, NORM_ABS))
        record("08-rev-mass-matrix", block=block, delta=delta)

    def test_t05_08_positive(self):
        vals = self.vmh.x.array
        mean = Fraction(float(vals.sum())).limit_denominator(10 ** 6) / vals.size
        peak = self.vertex_vm(self.msh, self.vmh, self.desc, None)["values"].max()
        self.assertEqual(mean, Fraction(12001, 12000)); self.assertTrue(close(peak, 3.0) and close(YIELD / peak, 276.0))
        self.assertTrue(close(YIELD / float(np.median(vals)), 828.0))
        self.assertLess(math.sqrt(1 / 6000), 0.02); self.assertLess(math.sqrt(self.spatial()[0]), 0.02)
        record("08-positive", mean=str(mean), peak=peak, sf_local=YIELD / peak)

    def test_t05_08_adverse(self):
        peak = self.vertex_vm(self.msh, self.vmh, self.desc, None)["values"].max()
        mutant = float(self.vmh.x.array.mean())  # global mean reported as the governing stress
        self.assertFalse(close(mutant, 3.0) or close(YIELD / mutant, 276.0)); self.assertTrue(close(peak, 3.0))
        record("08-adverse", mutant=mutant, peak=peak)

    def test_t05_08_rev_array_as_spatial(self):
        reported = float(np.dot(self.delta.x.array, self.delta.x.array) / self.delta.x.array.size)
        self.assertFalse(close(reported, 1 / 15000, NORM_REL, NORM_ABS))
        self.assertTrue(close(abs(reported - self.spatial()[0]), 1 / 10000, NORM_REL, NORM_ABS))
        record("08-rev-array-as-spatial", reported=reported, spatial=self.spatial()[0])

    def test_t05_08_rev_mean_as_extreme(self):
        reported = float(self.vmh.x.array.mean())
        self.assertFalse(close(reported, 3.0) or close(YIELD / reported, 276.0))
        record("08-rev-mean-as-extreme", reported=reported, required_max=3, required_SF=276)

    def test_t05_08_roi_boundary(self):
        eps = math.nextafter(3.0, math.inf)
        table = [("1", 4.0, 3.0, False), ("2", 4.0, eps, True), ("3", 15.0, 3.0, False), ("4", 15.0, eps, False)]
        for row, d, c, inside in table:
            with self.subTest(row=row):
                got = bool(S.tip_roi_mask([d], [c])[0])
                self.assertEqual(got, inside)
                record(f"08-ROI-boundary/original/{row}", tip_distance=d, cut_distance=c, included=got)
        with self.subTest(row="5"):
            mask = S.tip_roi_mask([1.0, 20.0], [5.0, 5.0])
            e = self.assertRefused("empty_region", S.region_extreme, [3.0, 3.0], mask)
            record("08-ROI-boundary/original/5", refused=e.reason)


class Producer(Operator):
    def setUp(self):
        self.msh = lagrange_mesh(TET, [[0, 1, 2, 3]], 1)
        self.uh, self.sig, self.vmh, self.desc = manufactured_vm(self.msh, lambda x: x * x / (2 * E))

    def test_t05_09_producer_positive(self):
        with self.subTest(row="1"):
            d = S.validate_observable_contract(self.vmh, self.desc, VM_DG1)
            pts = np.asarray(d["sampling"]["reference_points"])
            self.assertEqual((d["basis"]["degree"], d["basis"]["discontinuous"]), (1, True))
            self.assertTrue(allclose(np.sort(pts, axis=0), np.sort(basix.geometry(basix.CellType.tetrahedron), axis=0)))
            h = hashlib.sha256()
            for a in (np.ascontiguousarray(self.msh.geometry.x, dtype="<f8"), np.ascontiguousarray(self.msh.geometry.dofmap, dtype="<i8"),
                      np.ascontiguousarray(self.msh.topology.connectivity(3, 0).array, dtype="<i8"), np.ascontiguousarray(self.msh.topology.connectivity(3, 0).offsets, dtype="<i8")):
                h.update(str(a.shape).encode()); h.update(a.tobytes())
            self.assertEqual(d["mesh"]["sha256"], h.hexdigest())
            self.assertFalse(any("certificate" in k for k in d), "the S07 producer issues no S08 certificate")
            record("09-producer-positive/original/1", actual_DG=d["basis"]["degree"], observable=d["gci_observable"])

    def test_t05_09_producer_adverse(self):
        dg0, d0 = S.dg_von_mises(self.msh, self.sig(self.uh), 1, units=MM, frame=S.FRAME, region=S.WHOLE_DOMAIN)
        W2 = fem.functionspace(self.msh, ("Discontinuous Lagrange", 2))
        dg2 = fem.Function(W2); dg2.interpolate(fem.Expression(S.von_mises(self.sig(self.uh)), S.interpolation_points(W2)))
        d2 = S.field_descriptor(dg2, operator=S.DG_VM, quantity=self.desc["quantity"], formula=self.desc["formula"], units=MM, frame=S.FRAME, region=S.WHOLE_DOMAIN)
        other = lagrange_mesh(TET, [[0, 1, 2, 3]], 1)
        table = [("1", 0, "descriptor_mismatch", lambda: S.validate_observable_contract(dg0, d0, VM_DG1)),
                 ("2", 2, "descriptor_mismatch", lambda: S.validate_observable_contract(dg2, d2, VM_DG1)),
                 ("mesh", "different mesh than Function", "field_mesh_mismatch",
                  lambda: S.recover_vertex_vm(other, self.vmh, "max", descriptor=self.desc, expected_descriptor=VM_DG1))]
        for row, literal, reason, call in table:
            with self.subTest(row=row, literal=literal):
                e = self.assertRefused(reason, call)
                record(f"09-producer-adverse/original/{row}", literal=literal, refused=e.reason, detail=e.detail)


class Catalog(unittest.TestCase):
    """Host-runnable binding of the catalog to accepted S01 hashing/case schema and to the test sources it names."""

    def test_descriptor_hashes(self):
        for o in CATALOG["observables"] + CATALOG["regions"]:
            self.assertEqual(scientific_hash(o["descriptor"]), o["descriptor_sha256"], o["key"])
        for m in CATALOG["models"]:
            self.assertEqual(scientific_hash({k: v for k, v in m.items() if k != "sha256"}), m["sha256"], m["id"])
        self.assertFalse(CATALOG["models"][-1]["identity"], "T2 is a display label, not an identity")
        keys = [o["key"] for o in CATALOG["observables"]]
        unique_ids(keys)
        for k in ("dg_vm_interpolation.v1/P2-DG1/mm", "incident_cell_vertex_max.v1", "incident_cell_vertex_unweighted_mean.v1",
                  "legacy_vertex_sample_element_mean.v1", "pointwise_centroid_vm.v1", "cauchy_stress_tensor.v1",
                  "discrete_nodal_relative_l2.v1", "spatial_fe_relative_l2.v1"):
            self.assertIn(k, keys)

    def test_s07_phase_registration(self):
        ph = CATALOG["s07_phase"]
        cases = ph["cases"]
        for c in cases: validate_case(c)
        unique_ids(c["id"] for c in cases)
        self.assertEqual([c["id"] for c in cases], ["T05-0%d-%s" % (i, n) for i, n in enumerate(
            ["linear_scaling", "rigid_transform", "unit_consistency", "analytic_balance", "bc_failure", "mesh_failure",
             "field_semantics", "localized_peak", "certificate_field"], 1)] + ["T05-12-tier_collision"])
        policy = bind_policy(cases, {"max_bytes": 1048576, "max_depth": 64, "max_nodes": 100000})
        self.assertEqual(policy["catalog_sha256"], ph["cases_sha256"])
        self.assertEqual(scientific_hash(cases), ph["cases_sha256"])
        by_case = {}
        for b in ph["buckets"]: by_case.setdefault(b["case"], []).append(b)
        for c in cases:
            bs = by_case[c["id"]]
            ins, ors = {}, {}
            for b in bs:
                ins[b["bucket"]], ors[b["bucket"]] = b["input_ref"], b["oracle_ref"]
                for r in b["rows"]:
                    if "input_ref" in r: ins[r["id"]], ors[r["id"]] = r["input_ref"], r["oracle_ref"]
            self.assertEqual((scientific_hash(ins), scientific_hash(ors)), (c["input_sha256"], c["oracle_sha256"]), c["id"])
            self.assertEqual({b["schema_bucket"] for b in bs}, {"positive", "adverse"}, c["id"])
        self.assertEqual((len(ph["buckets"]), sum(len(b["rows"]) for b in ph["buckets"])), (44, 107))
        self.assertFalse({b["bucket"] for b in ph["buckets"]} & set(ph["S08_held_buckets"]))
        providers = [p for b in ph["buckets"] for r in b["rows"] for p in r.get("providers", [])]
        self.assertEqual(sorted(p["provider"] for p in providers), sorted(["solid_dolfinx", "rust_Plate", "rust_T6"] * 2))

    def test_named_tests_exist(self):
        sources = {}
        for path in ("fem_solid/tests/test_representation_invariants.py", "fem_solid/tests/test_field_semantics.py"):
            tree = ast.parse(open(os.path.join(ROOT, path)).read())
            sources[path] = {f"{c.name}.{f.name}" for c in tree.body if isinstance(c, ast.ClassDef) for f in c.body if isinstance(f, ast.FunctionDef)}
        rust = set(re.findall(r"#\[test\]\s*fn\s+(\w+)", open(os.path.join(ROOT, "crates/physics/tests/invariance.rs")).read()))
        names = [t for b in CATALOG["s07_phase"]["buckets"] for t in b["tests"]]
        names += [r["test"] for b in CATALOG["s07_phase"]["buckets"] for r in b["rows"] if r["test"]]
        names += [p["test"] for b in CATALOG["s07_phase"]["buckets"] for r in b["rows"] for p in r.get("providers", [])]
        names.append(CATALOG["inherited_regression"]["interpolated_field_is_not_labeled_as_l2_projection"]["test"])
        for name in names:
            path, test = name.split("::")
            self.assertIn(test, rust if path.endswith(".rs") else sources[path], name)
        for b in CATALOG["s07_phase"]["buckets"]:
            self.assertTrue(b["tests"] or all(r["test"] or r.get("providers") for r in b["rows"]) and b["rows"], b["bucket"])


if __name__ == "__main__":
    unittest.main()
