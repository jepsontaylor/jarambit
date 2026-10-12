"""PR-0.30.1 regression for the solid tip submodel on the wave27 engineering provisional g3_tip+00_t60_tt3.
Fast (always): the committed evidence records SF_solid_nodal_max 1.534 and n_dof 422955, and every wave27 solid JSON parses.
Slow (FEM_SOLID_REGRESS=1; about 25 min, 4 threads, needs requirements.txt): re-run must reproduce 1.534 +/- 0.005 and n_dof 422955."""
import glob, json, os, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EV = os.path.join(ROOT, 'evidence', 'wave27')
REF = os.path.join(EV, 'g3_tip+00_t60_tt3_solid.json')


class Evidence(unittest.TestCase):
    def test_reference_values(self):
        s = json.loads(open(REF).read())['solid']
        self.assertEqual(s['n_dof'], 422955); self.assertEqual(s['n_tet'], 92448)
        self.assertAlmostEqual(s['SF_solid_nodal_max'], 1.534, places=3)

    def test_all_solids_parse(self):
        fs = sorted(glob.glob(os.path.join(EV, '*_solid.json'))); self.assertEqual(len(fs), 24)
        for f in fs:
            s = json.load(open(f))['solid']
            for k in ('SF_solid_nodal_max', 'SF_solid_nodal_avg', 'n_dof'): self.assertIn(k, s, f)


@unittest.skipUnless(os.environ.get('FEM_SOLID_REGRESS') == '1', 'slow: set FEM_SOLID_REGRESS=1')
class Rerun(unittest.TestCase):
    def test_reproduces(self):
        out = os.path.join(tempfile.mkdtemp(), 'g3_solid.json')
        rc = subprocess.call([sys.executable, os.path.join(ROOT, 'fem_solid', 'run_tip.py'), os.path.join(EV, 'g3_tip+00_t60_tt3_D1.json'), out, '30', '4', '1', '2.0'])
        self.assertEqual(rc, 0)
        m = json.load(open(out + '.manifest.json'))
        self.assertEqual(m['n_dof'], 422955)
        self.assertLessEqual(abs(m['SF_solid_nodal_max'] - 1.534), 0.005)


if __name__ == '__main__':
    unittest.main()
