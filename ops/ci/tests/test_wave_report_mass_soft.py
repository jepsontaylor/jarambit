"""PR-0.30.0a: make_wave_report.py must not treat mass as a gate (Jepson decision, PR-0.28.3b).
Source-level checks (the report needs numpy/matplotlib, which the version-check runner does not install)."""
import ast, os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SRC = open(os.path.join(ROOT, 'ops', 'wave_reports', 'make_wave_report.py')).read()


class MassSoft(unittest.TestCase):
    def test_no_mass_gate_in_overall(self):
        for bad in ("G['mass_band", "G['mass_cap", '74.0 <= d[\'mass_g\'] <= 77.0'):
            self.assertNotIn(bad, SRC)

    def test_mass_soft_labels(self):
        tree = ast.parse(SRC); ns = {'NV': 'NOT VERIFIED', 'MASS_TARGET_G': 80.0, 'MASS_STRETCH_G': 70.0}
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'mass_soft')
        exec(compile(ast.Module([fn], []), 'mass_soft', 'exec'), ns)
        self.assertEqual(ns['mass_soft'](84.8), 'over 80 g target (G penalty)')
        self.assertEqual(ns['mass_soft'](76.0), 'target met (<80 g)')
        self.assertEqual(ns['mass_soft'](69.9), 'stretch met (<70 g)')
        self.assertEqual(ns['mass_soft'](None), 'NOT VERIFIED')


if __name__ == '__main__':
    unittest.main()
