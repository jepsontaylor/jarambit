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

    def test_lower_bound_covers_running(self):
        # 15 N life floor vs 66.8 g knife at 10.2 g (2x sacral running peak) -> SF > 2
        self.assertGreater(M.inertial_sf(M.WINDOW.lo_life, 66.8, M.RETENTION_CASES["running_x2_margin"]), 2.0)

    def test_fitness_gates(self):
        f = M.fitness({"path_feasible": False, "draw_n": 30})
        self.assertEqual(f["score"], 0.0); self.assertIn("path_infeasible", f["gates"])


if __name__ == "__main__":
    unittest.main()
