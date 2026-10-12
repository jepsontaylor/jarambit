"""PR-0.29.4 figure-integrity tests (run: python3 -m unittest discover -s ops/ci/tests)."""
import json, os, shutil, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'ops', 'wave_figures')); sys.path.insert(0, os.path.join(ROOT, 'ops', 'ci'))
import figlib, verify_figures  # noqa: E402


class Figures(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.d)
        os.makedirs(os.path.join(self.d, 'docs')); os.makedirs(os.path.join(self.d, 'ops'))
        self.stl = os.path.join(self.d, 'docs', 'a.stl'); open(self.stl, 'w').write('solid a\nendsolid a\n')
        self.png = os.path.join(self.d, 'docs', 'a.png'); open(self.png, 'wb').write(b'\x89PNGfake')
        self.scr = os.path.join(self.d, 'ops', 'gen.py'); open(self.scr, 'w').write('#\n')
        old = figlib.ROOT; figlib.ROOT = self.d; self.addCleanup(setattr, figlib, 'ROOT', old)
        figlib.write_manifest(self.png, [self.stl], self.scr, norms=['von_mises_mpa'])

    def test_clean_manifest_passes(self):
        self.assertEqual(verify_figures.main(['docs'], base=self.d), 0)

    def test_swapped_stl_fails(self):
        open(self.stl, 'w').write('solid b\nendsolid b\n')
        self.assertEqual(verify_figures.main(['docs'], base=self.d), 1)

    def test_swapped_png_fails(self):
        open(self.png, 'wb').write(b'other')
        self.assertEqual(verify_figures.main(['docs'], base=self.d), 1)

    def test_manifest_records_declared_norm(self):
        m = json.load(open(self.png + '.manifest.json'))
        self.assertEqual(m['norms']['von_mises_mpa']['vmax'], 828.0)

    def test_aes_badge_is_derived(self):
        txt, col = figlib.aes_badge({'aes_pass': False, 'hausdorff': 3.1, 'aes_fails': ['H>2.5']}, 'C.6')
        self.assertIn('FAIL', txt); self.assertNotIn('PASS', txt); self.assertEqual(col, figlib.RED)
        txt, _ = figlib.aes_badge({}, 'C.6'); self.assertIn('INCOMPLETE', txt)
        txt, col = figlib.aes_badge({'aes_pass': True}, 'C.6'); self.assertIn('PASS', txt); self.assertEqual(col, figlib.GREEN)

    def test_caption_says_faceted_stl_preview(self):
        c = figlib.hero_caption({'label': 'x', 'G1': 0.98, 'mass_g': 84.8}, '0.29.0')
        self.assertIn('faceted STL preview', c); self.assertNotIn('watertight', c.lower())

    def test_repo_figures_verify(self):
        self.assertEqual(verify_figures.main(['docs']), 0)


if __name__ == '__main__':
    unittest.main()
