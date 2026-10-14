"""S07 / T05 actual-operator representation invariants for fem_solid.solve_dolfinx (T05-01..06 and the T05-12 producer).

Every control calls the real dolfinx/PETSc operator on the unit-mm cube mesh.bar(1, 1, 0.5, order=2): E 1000 MPa, nu 0,
tag 1 (z=0) homogeneous clamp, tag 2 (z=1) traction. Oracles are independent rationals or the linear-operator relation
between genuine solves; adverse controls change the actual input or reduction and must be detected. A missing provider is a
required-capability ERROR raised by every operator class, never a skip. Run from the repository root."""
import gc, hashlib, json, math, os, sys, unittest
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
try:
    from petsc4py import PETSc
    import ufl
    from mpi4py import MPI
    from dolfinx import fem, geometry, mesh as dmesh
    from dolfinx.fem.petsc import assemble_matrix, assemble_vector, apply_lifting, set_bc
    from fem_solid import mesh as M, solve_dolfinx as S
    PROVIDER_ERROR = None
except ImportError as error:
    PROVIDER_ERROR = error

E, NU, YIELD = 1000.0, 0.0, 828.0
REL, ABS = 1e-8, 1e-10  # frozen before execution, in each quantity's declared unit
MM, SI = ("mm", "N", "MPa"), ("m", "N", "Pa")
F, G, FG = (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0)
CATALOG = json.load(open(os.path.join(ROOT, "assurance", "numerical", "observable_catalog.json")))
EXPECTED = {o["key"]: o["descriptor"] for o in CATALOG["observables"]}


def close(a, b, abs_tol=ABS, rel=REL):
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= abs_tol + rel * max(abs(a), abs(b))


def mismatches(got, want, abs_tol=ABS):
    got, want = np.asarray(got, dtype=float).ravel(), np.asarray(want, dtype=float).ravel()
    assert got.shape == want.shape, "association lengths differ"
    return [int(i) for i in range(got.size) if not close(got[i], want[i], abs_tol)]


def record(row, **kv):
    print("T05 " + json.dumps({"row": row, **kv}, sort_keys=True, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


def traction(v):
    return lambda x: np.vstack([v[0] + 0 * x[0], v[1] + 0 * x[0], v[2] + 0 * x[0]])


def probe(msh, f, pts):
    pts = np.asarray(pts, dtype=np.float64)
    tree = geometry.bb_tree(msh, msh.topology.dim)
    cells = geometry.compute_colliding_cells(msh, geometry.compute_collisions_points(tree, pts), pts)
    return f.eval(pts, [cells.links(i)[0] for i in range(len(pts))])


def cube(scale=1.0):
    return M.bar(scale, scale, 0.5 * scale, order=2)


def run(msh, ft, load, *, units=MM, e_mod=E, clamp=(1,), **kw):
    """One genuine solve plus its signed stress components on the solver's own DG(order-1) space."""
    uh, vmh, sig, info = S.solve(msh, ft, e_mod, NU, list(clamp), {2: load if callable(load) else traction(load)}, units=units, **kw)
    comps, cdesc = S.dg_stress_components(msh, sig(uh), kw.get("order", 2), units=units, frame=S.FRAME, region=S.WHOLE_DOMAIN)
    return {"uh": uh, "vmh": vmh, "sig": sig, "info": info, "comps": comps, "cdesc": cdesc}


def tensor_at(r, pt):
    s = {k: float(probe(r["uh"].function_space.mesh, f, [pt])[0][0]) for k, f in r["comps"].items()}
    return np.array([[s["xx"], s["xy"], s["zx"]], [s["xy"], s["yy"], s["yz"]], [s["zx"], s["yz"], s["zz"]]])


def same_association(a, b):
    """Two solves may only be compared array-wise after their V and W dof layouts are shown identical."""
    for f, g in ((a["uh"], b["uh"]), (a["comps"]["xx"], b["comps"]["xx"])):
        V, W = f.function_space, g.function_space
        if not (np.array_equal(V.tabulate_dof_coordinates(), W.tabulate_dof_coordinates()) and np.array_equal(V.dofmap.list, W.dofmap.list)):
            return False
    return True


def additivity(fg, f, g):
    bad = {"u": mismatches(fg["uh"].x.array, f["uh"].x.array + g["uh"].x.array)}
    for k in fg["comps"]: bad["sigma_" + k] = mismatches(fg["comps"][k].x.array, f["comps"][k].x.array + g["comps"][k].x.array)
    return {k: v for k, v in bad.items() if v}


def balance_against(r, applied):
    """Balance of a solve's reactions against an independently supplied load identity (not the solve's own input)."""
    d = r["info"]["diagnostics"]
    force = [abs(p + q) <= ABS + REL * max(abs(p), abs(q)) for p, q in zip(applied["force"], d["reaction_force"])]
    moment = [abs(p + q) <= ABS + REL * max(abs(p), abs(q)) for p, q in zip(applied["moment_about_origin"], d["reaction_moment_about_origin"])]
    return force, moment


class Operator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PROVIDER_ERROR is not None:
            raise RuntimeError(f"required T05 operator capability missing (incomplete, not skipped): {PROVIDER_ERROR!r}")
        cls.msh, cls.ft = cube()  # built once and reused by every solve in the class

    def assertRefused(self, reason, fn, *a, **kw):
        with self.assertRaises(S.ModelError) as cm: fn(*a, **kw)
        self.assertEqual(cm.exception.reason, reason, str(cm.exception))
        return cm.exception

    def healthy(self, r, row, load):
        info, d = r["info"], r["info"]["diagnostics"]
        self.assertGreater(info["ksp_reason"], 0); self.assertTrue(np.isfinite(r["uh"].x.array).all())
        self.assertTrue(all(np.isfinite(f.x.array).all() for f in r["comps"].values()))
        self.assertTrue(d["free_residual_ok"] and d["work_equals_two_energy"] and d["balance_ok"], d)
        record(row, load=load, ksp_its=info["ksp_its"], ksp_reason=info["ksp_reason"], ksp_residual=info["solver"]["ksp_residual_norm"], diagnostics=d)


class LinearScaling(Operator):
    def axial(self, k):
        r = run(self.msh, self.ft, (0.0, 0.0, float(k)))
        top = [0.0, 0.0, 1.0]
        return r, {"u_top": float(probe(self.msh, r["uh"], [top])[0][2]), "s_zz": tensor_at(r, top)[2, 2],
                   "vm_max": float(r["vmh"].x.array.max()), "energy": r["info"]["diagnostics"]["strain_energy"]}

    @staticmethod
    def scaling_violations(a, b):
        why = [k for k, want in (("u1", 1 / 1000), ("u2", 1 / 500), ("s1", 1.0), ("s2", 2.0)) if not close({"u1": a["u_top"], "u2": b["u_top"], "s1": a["s_zz"], "s2": b["s_zz"]}[k], want)]
        if not close(b["energy"], 4 * a["energy"]): why.append("energy x4")
        if not (close(YIELD / a["vm_max"], 828.0) and close(YIELD / b["vm_max"], 414.0)): why.append("SF 828/414")
        return why

    def test_t05_01_positive_axial_scaling(self):
        (r1, a), (r2, b) = self.axial(1), self.axial(2)
        self.assertTrue(same_association(r1, r2))
        self.assertEqual(mismatches(r2["uh"].x.array, 2 * r1["uh"].x.array), [])
        for k in r1["comps"]: self.assertEqual(mismatches(r2["comps"][k].x.array, 2 * r1["comps"][k].x.array), [], k)
        self.assertEqual(self.scaling_violations(a, b), [])
        self.assertTrue(close(a["energy"], 1 / 2000))
        record("01-positive", load1=a, load2=b)

    def test_t05_01_adverse_dropped_multiplier(self):
        (_, a), (_, b) = self.axial(1), self.axial(2)
        mutant = {**b, "s_zz": a["s_zz"], "vm_max": a["vm_max"]}  # report load-1 stress while solving load 2
        why = self.scaling_violations(a, mutant)
        self.assertIn("s2", why); self.assertIn("SF 828/414", why)
        self.assertEqual(self.scaling_violations(a, b), [])  # the healthy pair still passes: not reject-all
        record("01-adverse", detected=why)

    def three(self, mutate=None):
        out = {}
        for name, vec in (("F", F), ("G", G), ("F+G", FG)):
            call = traction(vec) if mutate is None else mutate(traction(vec))
            out[name] = run(self.msh, self.ft, call, rtol=1e-10, order=2)
        return out

    def test_t05_01_rev33_solid_positive(self):
        r = self.three()
        oracle = {"F": ([0, 0, 1], [0, 0, 0]), "G": ([1, 0, 0], [0, 1, 0]), "F+G": ([1, 0, 1], [0, 1, 0])}
        for name, x in r.items():
            self.healthy(x, "01-rev33-solid_dolfinx-positive", name)
            d = x["info"]["diagnostics"]
            self.assertEqual(mismatches(d["applied_force"], oracle[name][0]), [], name)
            self.assertEqual(mismatches(d["applied_moment_about_origin"], oracle[name][1]), [], name)
            self.assertTrue(same_association(x, r["F"]))
        self.assertEqual(additivity(r["F+G"], r["F"], r["G"]), {})
        self.assertGreater(np.abs(r["G"]["uh"].x.array).max(), 1e-6)  # the transverse load genuinely responds

    def test_t05_01_rev33_solid_adverse(self):
        def drop_g_on_mixed(call):  # proposed mutant at the traction input seam: omit G only when F and G coexist
            def mutated(x):
                v = np.array(call(x), dtype=np.float64)
                if np.any(v[0] != 0) and np.any(v[2] != 0): v[0] = 0.0
                return v
            return mutated
        healthy, mutant = self.three(), self.three(drop_g_on_mixed)
        for name in ("F", "G"):  # axes are untouched by the mutant
            self.assertEqual(mismatches(mutant[name]["uh"].x.array, healthy[name]["uh"].x.array), [], name)
        for vec, name in ((tuple(2 * c for c in F), "F"), (tuple(2 * c for c in G), "G")):
            double = run(self.msh, self.ft, drop_g_on_mixed(traction(vec)))
            self.assertEqual(mismatches(double["uh"].x.array, 2 * mutant[name]["uh"].x.array), [], "doubling " + name)
        broken = additivity(mutant["F+G"], mutant["F"], mutant["G"])
        self.assertIn("u", broken); self.assertTrue(any(k.startswith("sigma_") for k in broken))
        submitted = S.supplied_load_resultant(self.msh, self.ft, {2: traction(FG)})  # identity stays F+G
        self.assertEqual(mismatches(submitted["force"], [1, 0, 1]), [])
        force, moment = balance_against(mutant["F+G"], submitted)
        self.assertFalse(force[0], "omitted G must break x force balance against the submitted F+G load")
        self.assertFalse(moment[1])
        self.assertTrue(mutant["F+G"]["info"]["diagnostics"]["balance_ok"], "self-reported input hides the omission; only the submitted identity exposes it")
        record("01-rev33-solid_dolfinx-adverse", additivity_broken=sorted(broken), force_balance=force, moment_balance=moment)


class RigidTransform(Operator):
    Q = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], dtype=np.float64)
    T = np.array([7.0, -3.0, 2.0])

    def moved(self, load):
        msh, ft = cube()
        msh.geometry.x[:] = msh.geometry.x @ self.Q.T + self.T  # geometry, tags and probes move together
        return msh, run(msh, ft, load)

    def test_t05_02_positive(self):
        base = run(self.msh, self.ft, F)
        msh, r = self.moved(tuple(self.Q @ np.array(F)))
        top, top_new = np.array([0.0, 0.0, 1.0]), self.Q @ np.array([0.0, 0.0, 1.0]) + self.T
        u = probe(msh, r["uh"], [top_new])[0]
        s, s0 = tensor_at(r, top_new), tensor_at(base, top)
        self.assertEqual(mismatches(u, [1 / 1000, 0, 0]), [])
        self.assertEqual(mismatches(s, [[1, 0, 0], [0, 0, 0], [0, 0, 0]]), [])
        self.assertEqual(mismatches(s, self.Q @ s0 @ self.Q.T), [])
        self.assertTrue(close(YIELD / float(r["vmh"].x.array.max()), 828.0))
        self.assertTrue(r["info"]["diagnostics"]["balance_ok"])
        record("02-positive", u=u, sigma=s, sigma_original=s0)

    def test_t05_02_adverse(self):
        msh, r = self.moved(F)  # rotated geometry and restraints, traction vector not rotated
        top_new = self.Q @ np.array([0.0, 0.0, 1.0]) + self.T
        u, s = probe(msh, r["uh"], [top_new])[0], tensor_at(r, top_new)
        self.assertTrue(mismatches(u, [1 / 1000, 0, 0]) or mismatches(s, [[1, 0, 0], [0, 0, 0], [0, 0, 0]]))
        record("02-adverse", u=u, sigma=s, meaning="different load/model, not an invariance or physical failure")


class Units(Operator):
    def test_t05_03_positive(self):
        mm = run(self.msh, self.ft, F)
        msh, ft = cube(1e-3)
        si = run(msh, ft, (0.0, 0.0, 1e6), units=SI, e_mod=1e9)
        u_mm, u_m = probe(self.msh, mm["uh"], [[0, 0, 1.0]])[0][2], probe(msh, si["uh"], [[0, 0, 1e-3]])[0][2]
        s_mm, s_pa = tensor_at(mm, [0, 0, 1.0])[2, 2], tensor_at(si, [0, 0, 1e-3])[2, 2]
        d_mm, d_si = mm["info"]["diagnostics"], si["info"]["diagnostics"]
        self.assertTrue(close(u_mm, 1 / 1000) and close(u_m, 1e-6) and close(s_mm, 1.0) and close(s_pa, 1e6))
        self.assertTrue(close(1e3 * u_m, u_mm) and close(1e-6 * s_pa, s_mm), "same physics in mm/N/MPa and m/N/Pa")
        self.assertTrue(close(d_si["applied_force"][2], 1.0) and close(d_si["strain_energy"], 1 / 2000000) and close(1e3 * d_si["strain_energy"], d_mm["strain_energy"]))
        self.assertTrue(close(828e6 / float(si["vmh"].x.array.max()), 828.0))
        self.assertEqual(si["info"]["units"]["stress"], "Pa"); self.assertEqual(si["info"]["observable"]["units"], "Pa")
        S.validate_observable_contract(si["vmh"], si["info"]["observable"], EXPECTED["dg_vm_interpolation.v1/P2-DG1/m"])
        record("03-positive", u_mm=u_mm, u_m=u_m, s_MPa=s_mm, s_Pa=s_pa)

    def test_t05_03_adverse(self):
        e = self.assertRefused("incoherent_units", S.solve, self.msh, self.ft, E, NU, [1], {2: traction(F)}, units=("m", "N", "MPa"))
        record("03-adverse", refused=e.reason)

    def test_t05_03_changed_physics(self):
        msh, ft = cube(1000.0)  # geometry x1000 with unchanged numeric material/load: a different physical model
        r = run(msh, ft, F)
        u = probe(msh, r["uh"], [[0, 0, 1000.0]])[0][2]
        self.assertTrue(close(u, 1.0) and close(r["info"]["diagnostics"]["applied_force"][2], 1e6))
        self.assertFalse(close(u, 1 / 1000) or close(r["info"]["diagnostics"]["applied_force"][2], 1.0), "must not pass as invariance")
        record("03-changed-physics", u=u, force=r["info"]["diagnostics"]["applied_force"])


class Balance(Operator):
    def test_t05_04_positive(self):
        r = run(self.msh, self.ft, F)
        d = r["info"]["diagnostics"]
        self.assertEqual(mismatches(d["applied_force"], [0, 0, 1]), []); self.assertEqual(mismatches(d["reaction_force"], [0, 0, -1]), [])
        self.assertEqual(mismatches(np.add(d["applied_force"], d["reaction_force"]), [0, 0, 0]), [])
        self.assertEqual(mismatches(np.add(d["applied_moment_about_origin"], d["reaction_moment_about_origin"]), [0, 0, 0]), [])
        self.assertTrue(close(d["strain_energy"], 1 / 2000) and close(d["work"], 1 / 1000) and d["work_equals_two_energy"])
        record("04-positive", diagnostics=d)

    def test_t05_04_adverse(self):
        r = run(self.msh, self.ft, F)
        V, uh = r["uh"].function_space, r["uh"]
        eps, sig = S.elastic_stress(E, NU)
        u, v = ufl.TrialFunction(V), ufl.TestFunction(V)
        ds = ufl.Measure("ds", domain=self.msh, subdomain_data=self.ft)
        tf = fem.Function(V); tf.interpolate(traction(F))
        af, Lf = fem.form(ufl.inner(sig(u), eps(v)) * ufl.dx), fem.form(ufl.inner(tf, v) * ds(2))
        bcs = [fem.dirichletbc(np.zeros(3), fem.locate_dofs_topological(V, 2, self.ft.find(1)), V)]
        A = assemble_matrix(af, bcs=bcs); A.assemble()  # mutant: BC-modified identity rows
        b = assemble_vector(Lf); apply_lifting(b, [af], bcs=[bcs]); b.ghostUpdate(addv=PETSc.InsertMode.ADD, mode=PETSc.ScatterMode.REVERSE); set_bc(b, bcs)
        res = b.duplicate(); A.mult(uh.x.petsc_vec, res); res.axpy(-1.0, b)
        m = fem.Function(V); m.x.array[:] = 1.0; set_bc(m.x.petsc_vec, bcs)
        fixed = (m.x.array == 0.0).reshape(-1, 3)
        r_bc = np.where(fixed, res.getArray().copy().reshape(-1, 3), 0.0).sum(axis=0)
        for o in (A, b, res): o.destroy()
        applied = r["info"]["diagnostics"]["applied_force"]
        self.assertNotEqual(mismatches(np.add(applied, r_bc), [0, 0, 0]), [], "BC-modified rows cannot supply reactions")
        self.assertNotEqual(mismatches(np.add([0, 0, 0], r["info"]["diagnostics"]["reaction_force"]), [0, 0, 0]), [], "discarded load term")
        self.assertEqual(mismatches(np.add(applied, r["info"]["diagnostics"]["reaction_force"]), [0, 0, 0]), [])
        record("04-adverse", bc_modified_reaction=r_bc, unconstrained_reaction=r["info"]["diagnostics"]["reaction_force"])


class BoundaryConditions(Operator):
    def test_t05_05_positive(self):
        r = run(self.msh, self.ft, F, clamp=(1, 1))  # duplicate compatible zero clamps are accepted
        self.healthy(r, "05-positive", "F")
        self.assertEqual(r["info"]["validated_model"]["rigid_restraint_rank"], 6)
        self.assertTrue(close(probe(self.msh, r["uh"], [[0, 0, 1.0]])[0][2], 1 / 1000))

    def test_t05_05_adverse(self):
        record("05-adverse", refused=self.assertRefused("missing_tag", S.solve, self.msh, self.ft, E, NU, [999], {2: traction(F)}).detail)

    def test_t05_05_singular(self):
        record("05-singular", refused=self.assertRefused("insufficient_restraint", S.solve, self.msh, self.ft, E, NU, [], {2: traction(F)}, sym_tags={}).detail)

    def test_t05_05_load_and_symmetry(self):
        good = {2: traction(F)}
        table = [("1", "traction unknown tag999", "missing_tag", dict(tractions={999: traction(F)})),
                 ("2", "traction shape(2,N)", "invalid_traction", dict(tractions={2: lambda x: np.vstack([0 * x[0], 0 * x[0]])})),
                 ("3", "traction NaN", "invalid_traction", dict(tractions={2: lambda x: np.vstack([0 * x[0], 0 * x[0], np.nan + 0 * x[0]])})),
                 ("4", "symmetry component3", "invalid_symmetry_component", dict(sym_tags={1: 3})),
                 ("5", "nonfinite rtol", "invalid_rtol", dict(rtol=float("nan"))),
                 ("6", "rtol0", "invalid_rtol", dict(rtol=0.0)),
                 ("7", "rtol1", "invalid_rtol", dict(rtol=1.0))]
        for row, literal, reason, kw in table:
            with self.subTest(row=row, literal=literal):
                kw = {"tractions": good, **kw}
                e = self.assertRefused(reason, S.solve, self.msh, self.ft, E, NU, [1], kw.pop("tractions"), **kw)
                record(f"05-load-and-symmetry/original/{row}", literal=literal, refused=e.reason, detail=e.detail)

    def test_t05_05_nonconvergence(self):
        e = self.assertRefused("ksp_not_converged", S.solve, self.msh, self.ft, E, NU, [1], {2: traction(F)}, max_it=0)
        self.assertLessEqual(e.info["ksp_reason"], 0)
        self.assertEqual(e.info["settings"]["max_it"], 0)
        record("05-nonconvergence", ksp_reason=e.info["ksp_reason"], ksp_its=e.info["ksp_its"])

    def test_t05_05_lifetime(self):
        self.assertFalse(hasattr(S, "_KEEP"), "no process-global retained owner list")
        for i in range(1, 21):
            with self.subTest(row=str(i)):
                uh, vmh, sig, info = S.solve(self.msh, self.ft, E, NU, [1], {2: traction(F)})
                u = float(probe(self.msh, uh, [[0, 0, 1.0]])[0][2])
                del uh, vmh, sig; gc.collect()
                live = S.live_rigid_mode_owners()
                self.assertTrue(close(u, 1 / 1000) and info["ksp_reason"] > 0)
                self.assertEqual(live, 0, "rigid-mode owners are local to each solve")
                record(f"05-lifetime/original/{i}", u_top=u, live_owners=live)


def tet_mesh(vertices, cells):
    import basix.ufl
    return dmesh.create_mesh(MPI.COMM_WORLD, np.asarray(cells, dtype=np.int64), np.asarray(vertices, dtype=np.float64),
                             ufl.Mesh(basix.ufl.element("Lagrange", "tetrahedron", 1, shape=(3,))))


TET = [[-1, 0, 0], [1, 0, 0], [-1, 1, 0], [-1, 0, 1]]


class MeshAndMaterial(Operator):
    def test_t05_06_positive(self):
        self.healthy(run(self.msh, self.ft, F), "06-positive", "F")
        for cell in ([0, 1, 2, 3], [1, 2, 0, 3]):  # an even (legal) reordering keeps the orientation
            self.assertGreater(S.validate_mesh(tet_mesh(TET, [cell]))["min_jacobian"], 0)

    def test_t05_06_adverse(self):
        msh = tet_mesh(TET, [[0, 1, 2, 3]])
        S.validate_mesh(msh)
        msh.geometry.x[:, 0] *= -1.0  # reflect geometry only; topology/reference map association fixed
        record("06-adverse", refused=self.assertRefused("inverted_cell", S.validate_mesh, msh).detail)

    def test_t05_06_degenerate(self):
        verts = [TET[0], TET[1], TET[2], TET[0]]
        try:
            msh = tet_mesh(verts, [[0, 1, 2, 3]])
        except Exception as error:  # constructor refusal is an acceptable, recorded failure stage
            record("06-degenerate", stage="constructor", error=repr(error)); return
        record("06-degenerate", stage="validator", refused=self.assertRefused("degenerate_cell", S.validate_mesh, msh).detail)

    def test_t05_06_disconnected(self):
        box = dmesh.create_box(MPI.COMM_WORLD, [[0, 0, 0], [1, 1, 1]], [1, 1, 1], dmesh.CellType.tetrahedron)
        x, c = box.geometry.x.copy(), box.geometry.dofmap.copy()
        msh = tet_mesh(np.vstack([x, x + [3.0, 0, 0]]), np.vstack([c, c + x.shape[0]]))
        msh.topology.create_connectivity(2, 3)
        tags = []
        for tag, z in ((1, 0.0), (2, 1.0)):
            f = dmesh.locate_entities_boundary(msh, 2, lambda p, z=z: np.isclose(p[2], z)); tags.append((f, np.full(f.size, tag, dtype=np.int32)))
        f = np.concatenate([t[0] for t in tags]); order = np.argsort(f)
        ft = dmesh.meshtags(msh, 2, f[order], np.concatenate([t[1] for t in tags])[order])
        record("06-disconnected", refused=self.assertRefused("disconnected_mesh", S.solve, msh, ft, E, NU, [1], {2: traction(F)}).detail)

    def test_t05_06_material_order(self):
        table = [("1", "E0", dict(E=0.0), "invalid_material"), ("2", "E-1", dict(E=-1.0), "invalid_material"),
                 ("3", "E NaN", dict(E=float("nan")), "invalid_material"), ("4", "E Infinity", dict(E=float("inf")), "invalid_material"),
                 ("5", "nu-1", dict(nu=-1.0), "invalid_material"), ("6", "nu0.5", dict(nu=0.5), "invalid_material"),
                 ("7", "nu NaN", dict(nu=float("nan")), "invalid_material"), ("8", "order0", dict(order=0), "invalid_order"),
                 ("9", "order-1", dict(order=-1), "invalid_order"), ("10", "order1.5", dict(order=1.5), "invalid_order"),
                 ("11", "orderTrue", dict(order=True), "invalid_order"), ("12", "order3 unsupported", dict(order=3), "unsupported_order")]
        for row, literal, kw, reason in table:
            with self.subTest(row=row, literal=literal):
                args = {"E": E, "nu": NU, "order": 2, **kw}
                e = self.assertRefused(reason, S.solve, self.msh, self.ft, args["E"], args["nu"], [1], {2: traction(F)}, order=args["order"])
                record(f"06-material-order/original/{row}", literal=literal, refused=e.reason, detail=e.detail)

    def test_t05_06_order1(self):
        r = run(self.msh, self.ft, F, order=1)
        desc = r["info"]["observable"]
        self.assertEqual(desc["basis"]["degree"], 0)
        S.validate_observable_contract(r["vmh"], desc, EXPECTED["dg_vm_interpolation.v1/P1-DG0/mm"])
        self.assertEqual(mismatches(r["vmh"].x.array, np.ones_like(r["vmh"].x.array)), [])
        e = self.assertRefused("unsupported_field", S.recover_vertex_vm, self.msh, r["vmh"], "max", descriptor=desc,
                               expected_descriptor=EXPECTED["dg_vm_interpolation.v1/P1-DG0/mm"])
        record("06-order1", vm=float(r["vmh"].x.array.max()), recovery_refused=e.reason)


class RealizedSolver(Operator):
    def options(self):
        return dict(PETSc.Options().getAll())

    def test_t05_12_rev_realized_default(self):
        r = run(self.msh, self.ft, F)
        s = r["info"]["solver"]
        self.assertEqual((s["ksp_type"], s["pc_type"], s["rtol"], s["atol"], s["divtol"], s["max_it"], s["model"]),
                         ("cg", "gamg", 1e-10, 1e-50, 1e4, 5000, "dolfinx3d_isotropic_linear_elasticity.cg_gamg.v1"))
        p = s["prefix"]
        self.assertTrue(p.startswith("s07_"))
        self.assertEqual({k: s["effective_options"].get(p + k) for k in ("mg_levels_ksp_type", "mg_levels_pc_type", "pc_gamg_coarse_eq_limit")},
                         {"mg_levels_ksp_type": "chebyshev", "mg_levels_pc_type": "jacobi", "pc_gamg_coarse_eq_limit": "1000"})
        eff = json.dumps(s["effective_options"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self.assertEqual(hashlib.sha256(eff.encode()).hexdigest(), s["effective_options_sha256"])
        self.assertTrue(s["provider"]["petsc"] and s["provider"]["versions"]["dolfinx"])
        record("12-rev-realized-default", solver=s)

    def test_t05_12_rev_options_restored(self):
        before = self.options()
        r = run(self.msh, self.ft, F)
        self.assertEqual(self.options(), before, "caller options database unchanged")
        self.assertEqual((r["info"]["solver"]["ksp_type"], r["info"]["solver"]["pc_type"]), ("cg", "gamg"))
        record("12-rev-options-restored", prefix=r["info"]["solver"]["prefix"])

    def override(self, row, key, value):
        before, prefix = self.options(), f"s07test_{key}_"
        opts = PETSc.Options()
        opts[prefix + key] = value
        try:
            e = self.assertRefused("unsupported_solver_configuration", S.solve, self.msh, self.ft, E, NU, [1], {2: traction(F)}, options_prefix=prefix)
            self.assertEqual(e.info["actual"][key], value)
        finally:
            opts.delValue(prefix + key)
        self.assertEqual(self.options(), before)
        after = run(self.msh, self.ft, F)  # a subsequent default call succeeds
        self.assertEqual((after["info"]["solver"]["ksp_type"], after["info"]["solver"]["pc_type"]), ("cg", "gamg"))
        record(row, actual=e.info["actual"], refused=e.reason)

    def test_t05_12_rev_ksp_override(self):
        self.override("12-rev-KSP-override", "ksp_type", "gmres")

    def test_t05_12_rev_pc_override(self):
        self.override("12-rev-PC-override", "pc_type", "jacobi")

    def test_t05_12_rev_false_default(self):
        A = PETSc.Mat().createAIJ([2, 2], nnz=1, comm=MPI.COMM_SELF)
        for i in range(2): A.setValue(i, i, 1.0)
        A.assemble()
        ksp = PETSc.KSP().create(MPI.COMM_SELF)
        try:
            ksp.setOperators(A); ksp.setType("gmres"); ksp.getPC().setType("jacobi")
            ksp.setTolerances(rtol=1e-10, atol=1e-50, divtol=1e4, max_it=5000)
            expected = {"ksp_type": "gmres", "pc_type": "jacobi", "rtol": 1e-10, "atol": 1e-50, "divtol": 1e4, "max_it": 5000}
            e = self.assertRefused("unsupported_solver_configuration", S.realized_solver_contract, ksp, expected=expected, provider={}, effective_options={})
        finally:
            ksp.destroy(); A.destroy()
        record("12-rev-false-default", actual=e.info["actual"], emitted_model=None)

    def test_t05_12_producer_adverse_generic_tier(self):
        r = run(self.msh, self.ft, F)
        exp = EXPECTED["dg_vm_interpolation.v1/P2-DG1/mm"]
        a = self.assertRefused("incomplete_observable_contract", S.validate_observable_contract, r["vmh"], {"tier": "T2"}, exp)
        b = self.assertRefused("incomplete_observable_contract", S.validate_observable_contract, r["vmh"], r["info"]["observable"], {"tier": "T2"})
        S.validate_observable_contract(r["vmh"], r["info"]["observable"], exp)
        record("12-producer-adverse", descriptor_refused=a.detail, expected_refused=b.detail)


if __name__ == "__main__":
    unittest.main()
