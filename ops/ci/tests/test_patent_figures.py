import json, os, re, subprocess, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MAN = os.path.join(ROOT, 'docs/patent/figures/figures.json')


class PatentFigures(unittest.TestCase):
    def test_verify(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'ops/render/patent/figures.py'), '--verify', MAN], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_draft_cites_every_figure_and_numeral(self):
        man = json.load(open(MAN)); draft = open(os.path.join(ROOT, 'docs/PATENT_DRAFT.md'), encoding='utf-8').read()
        for rel in man['figures']:
            self.assertIn(os.path.relpath(os.path.join(ROOT, rel), os.path.join(ROOT, 'docs')), draft)
        for num in man['reference_numerals']:
            self.assertRegex(draft, rf'\| {num} \|')
        self.assertEqual(len(man['figures']), 8)

    def test_draft_status_is_scoped(self):
        draft = open(os.path.join(ROOT, 'docs/PATENT_DRAFT.md'), encoding='utf-8').read()
        self.assertNotRegex(draft, r'passes all hard gates|passed every hard gate|meets the RS-karambit-v1 screen in simulation')
        self.assertIn('RS-karambit-v2', draft); self.assertIn('archived v0.27', draft); self.assertIn('fails** the inherited RS-karambit-v1 screen', draft)

    def test_views_fit_and_numerals_anchor_features(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('numpy not installed')
        sys.path.insert(0, os.path.join(ROOT, 'ops', 'render', 'patent'))
        import figures as F
        man = json.load(open(MAN)); stl = [k for k in man['inputs'] if k.endswith('.stl')][0]
        v = np.array(re.findall(r'vertex\s+(\S+)\s+(\S+)\s+(\S+)', open(os.path.join(ROOT, stl)).read()), float).reshape(-1, 3, 3)
        for t, _, R in F.VIEWS:
            x0, y0, x1, y1 = F.screen_bounds(v, R)
            self.assertGreaterEqual(x0, 0, t); self.assertLessEqual(x1, F.W, t); self.assertGreaterEqual(y0, 0, t); self.assertLessEqual(y1, F.H, t)
        d1 = json.load(open(os.path.join(ROOT, [k for k in man['inputs'] if k.endswith('_D1.json')][0])))
        tip = man['numeral_anchors_mm']['40']; t0 = d1['outline'][0]
        self.assertLess(((tip[0] - t0[0]) ** 2 + (tip[1] - t0[1]) ** 2) ** 0.5, 0.5)
        a, b = man['taper_mm']; self.assertTrue(a < man['numeral_anchors_mm']['50'][0] < b)


if __name__ == '__main__':
    unittest.main()
