"""Morley plate stiffness vs closed form (skipped when scikit-fem/triangle/shapely are absent)."""
import math, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    import skfem, triangle, shapely  # noqa
    HAVE = True
except Exception:
    HAVE = False


@unittest.skipUnless(HAVE, "scikit-fem/triangle/shapely not installed")
class Plate(unittest.TestCase):
    def test_clamped_circle_patch(self):
        from shapely.geometry import Point
        from sheath.fem_plate import plate_stiffness, roark_clamped_patch_w
        E, t, nu, a, r0 = 1800.0, 1.6, 0.38, 15.0, 2.0
        k, w, ndof, _ = plate_stiffness(Point(0, 0).buffer(a, 128), (0.0, 0.0), E, t, nu, r0=r0, max_area=0.4)
        ref = roark_clamped_patch_w(E, t, nu, a, r0)
        self.assertLess(abs(w / ref - 1), 0.03, (w, ref))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAVE, "scikit-fem/triangle/shapely not installed")
class Tab(unittest.TestCase):
    def test_tab_plate_vs_beam(self):
        """Wide click-tab: Morley plate clamped on the root edge vs plate-corrected cantilever 3 (E/(1-nu^2)) I / L^3."""
        from shapely.geometry import box
        from sheath.fem_plate import plate_stiffness
        from sheath.model import tab_k
        E, t, L, b = 1800.0, 1.6, 10.0, 7.0
        k, _, _, _ = plate_stiffness(box(0, 0, L, b), (L - 1.0, b / 2), E, t, r0=1.0, max_area=0.08, clamp_fn=lambda x, y: x < 1e-6)
        # load centroid at L-1 => beam stiffness at that point
        kb = tab_k(E, b, t, L - 1.0)
        self.assertLess(abs(k / kb - 1), 0.15, (k, kb))
