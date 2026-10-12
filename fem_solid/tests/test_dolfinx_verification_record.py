"""PR-0.30.2: the recorded reference-solver verification (evidence/fem_solid/verify_0.30.2.json) meets the roadmap bars.
Regenerate in the container: verify_analytic.py (St-Venant torsion + Kirsch 3D, <= 1 %), cross_check.py (dolfinx vs skfem tip
SF on the same submodel, <= 2 %), step_mesh_smoke.py (whole-part tet10 volume vs reported mass)."""
import json, os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REC = json.loads(open(os.path.join(ROOT, 'evidence', 'fem_solid', 'verify_0.30.2.json')).read())


class Record(unittest.TestCase):
    def test_analytic_within_1pct(self):
        cases = {c['case']: c for c in REC['analytic']}
        self.assertEqual(set(cases), {'saint_venant_square_torsion', 'kirsch_3d_heywood'})
        for c in cases.values(): self.assertLessEqual(c['rel_err'], 0.01, c['case'])

    def test_skfem_cross_check_within_2pct(self):
        x = REC['cross_check_skfem']; self.assertEqual(x['n_dof'], 422955)
        self.assertLessEqual(max(x['rel_err_nodal_max'], x['rel_err_nodal_avg']), 0.02)

    def test_whole_part_mesh_mass(self):
        w = REC['whole_part_mesh']; self.assertLessEqual(abs(w['mass_g_at_4.43'] / w['ref_mass_g'] - 1), 0.01)


if __name__ == '__main__':
    unittest.main()
