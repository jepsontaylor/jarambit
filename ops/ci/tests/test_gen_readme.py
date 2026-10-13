import os, re, subprocess, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class GenReadme(unittest.TestCase):
    def test_check_passes(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'ops/ci/gen_readme.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_version_badge_matches_docs_version(self):
        v = open(os.path.join(ROOT, 'docs/VERSION')).read().strip()
        t = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
        self.assertIn(f'releases/tag/v{v}', t)
        self.assertNotIn('jepsontaylor/jarambit/releases', t)
        self.assertNotIn('seq ≥ 1.2 is still soft', t)
        self.assertNotRegex(t, r'watertight STEP')

if __name__ == '__main__':
    unittest.main()
