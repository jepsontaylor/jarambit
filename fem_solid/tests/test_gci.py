"""PR-0.30.3: GCI arithmetic against a manufactured second-order sequence and an oscillatory one."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gci import gci


class GCI(unittest.TestCase):
    def test_second_order(self):
        f = lambda h: 100.0 + 8.0 * h ** 2
        g = gci(f(0.25), f(0.5), f(1.0), 2.0)
        self.assertAlmostEqual(g['p'], 2.0, places=9); self.assertAlmostEqual(g['f_ext'], 100.0, places=9)
        self.assertAlmostEqual(g['gci_fine'], 1.25 * abs((f(0.25) - f(0.5)) / f(0.25)) / 3.0, places=12)

    def test_oscillatory_flagged(self):
        g = gci(100.0, 101.0, 99.5, 2.0); self.assertFalse(g['monotone']); self.assertIsNone(g['p'])


if __name__ == '__main__':
    unittest.main()
