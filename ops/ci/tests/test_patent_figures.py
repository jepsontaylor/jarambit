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
        self.assertNotRegex(draft, r'passes all hard gates')
        self.assertIn('RS-karambit-v2', draft)


if __name__ == '__main__':
    unittest.main()
