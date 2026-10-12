"""PR-0.30.1b: run_tip.py refuses missing / misnamed inputs before solving."""
import os, subprocess, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN = os.path.join(ROOT, 'fem_solid', 'run_tip.py')


class Inputs(unittest.TestCase):
    def run_(self, *a): return subprocess.run([sys.executable, RUN, *a], capture_output=True, text=True)

    def test_empty_d1_arg(self):
        r = self.run_('', '/tmp/x.json', '30', '4', '1', '2.0'); self.assertEqual(r.returncode, 2); self.assertIn('missing input', r.stderr)

    def test_missing_file(self):
        r = self.run_('/nonexistent/a_D1.json', '/tmp/x.json'); self.assertEqual(r.returncode, 2)

    def test_too_few_args(self):
        self.assertEqual(self.run_().returncode, 2)


if __name__ == '__main__':
    unittest.main()
