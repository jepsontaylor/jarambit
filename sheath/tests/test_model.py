"""Analytic retention model (pure python, CI)."""
import math, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from sheath import model as M


class Snap(unittest.TestCase):
    def test_bayer_worked_example(self):
        # Covestro/Bayer guide example: P = 32.5 N, mu = 0.6, a = 30 deg -> W ~ 58.5 N (factor read from Fig. 18 = 1.8)
        self.assertAlmostEqual(M.snap_axial(32.5, 0.6, 30.0) / 32.5, (0.6 + math.tan(math.radians(30))) / (1 - 0.6 * math.tan(math.radians(30))))
        self.assertLess(abs(M.snap_axial(32.5, 0.6, 30.0) - 58.5), 1.5)

    def test_self_locking(self):
        self.assertTrue(math.isinf(M.snap_axial(10, 0.5, 70.0)))   # 0.5*tan70 > 1

    def test_cantilever(self):
        self.assertAlmostEqual(M.cantilever_k(2000, 10, 2, 20), 3 * 2000 * (10 * 8 / 12) / 8000)


class Window(unittest.TestCase):
    def test_two_sided(self):
        w = M.WINDOW
        self.assertEqual(M.window_score(w.target), 1.0)
        self.assertAlmostEqual(M.window_score(w.lo_new), 0.5); self.assertAlmostEqual(M.window_score(w.hi_new), 0.5)
        self.assertEqual(M.window_score(w.lo_life - 1), 0.0); self.assertEqual(M.window_score(w.hi_life + 1), 0.0)
        self.assertEqual(M.window_score(float("nan")), 0.0)
        # monotone up then down
        xs = [w.lo_life + 0.5 * i for i in range(int((w.hi_life - w.lo_life) * 2))]
        ys = [M.window_score(x) for x in xs]
        k = ys.index(max(ys))
        self.assertTrue(all(a <= b + 1e-12 for a, b in zip(ys[:k], ys[1:k + 1])))
        self.assertTrue(all(a >= b - 1e-12 for a, b in zip(ys[k:], ys[k + 1:])))

    def test_lower_bound_covers_design_shock(self):
        # 20 N life floor vs 66.8 g knife at the 15 g design shock -> SF >= 2
        self.assertGreaterEqual(M.inertial_sf(M.WINDOW.lo_life, 66.8, M.RETENTION_CASES["design_shock"]), 2.0)

    def test_fitness_lexicographic(self):
        ok = {"path_feasible": True, "min_edge_clearance_mm": 1, "rim_min_mm": 3, "insert_n": 30, "strain_est": 0.01,
              "p_in_life_window": 0.97, "p_in_new_window": 0.9, "draw_n": 35}
        light_bad = dict(ok, mass_g=5.0, rim_min_mm=1.0)
        heavy_ok = dict(ok, mass_g=40.0)
        self.assertEqual(M.fitness(light_bad)["score"], 0.0)
        self.assertGreater(M.fitness(heavy_ok)["score"], 0.0)
        self.assertGreater(M.fitness(dict(ok, mass_g=20))["score"], M.fitness(heavy_ok)["score"])


class Units(unittest.TestCase):
    def test_density_tonne_mm3(self):
        self.assertAlmostEqual(M.density_t_per_mm3(930.0), 9.30e-10, delta=1e-15)

    def test_legacy_proxy_documented(self):
        wmax, fd = M.legacy_holder_proxy(2.0, 1.2, 6.0)
        self.assertAlmostEqual(wmax, 1.3)
        self.assertAlmostEqual(fd, 0.55 * 6.6 * 1.3 ** 3 * 1.2)   # ~9.57 N: cannot reach any v1.1 window
        self.assertLess(fd, M.WINDOW.lo_life)

    def test_energy_proxy_thickness_sensitivity(self):
        k0 = M.energy_proxy_tab_k(1650, 8, 1.6, 10)
        self.assertAlmostEqual(M.energy_proxy_tab_k(1650, 8, 1.6 * 0.9, 10) / k0, 0.729, places=6)
        self.assertAlmostEqual(M.energy_proxy_tab_k(1650, 8, 1.6 * 1.1, 10) / k0, 1.331, places=6)
        self.assertAlmostEqual(k0, M.cantilever_k(1650, 8, 1.6, 10))

    def test_fitness_gates(self):
        f = M.fitness({"path_feasible": False, "draw_n": 30})
        self.assertEqual(f["score"], 0.0); self.assertIn("path_infeasible", f["gates"])


if __name__ == "__main__":
    unittest.main()
