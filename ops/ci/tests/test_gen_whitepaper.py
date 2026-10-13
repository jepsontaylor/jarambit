import json, os, subprocess, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'ops', 'ci'))


class GenWhitepaper(unittest.TestCase):
    def test_check_passes(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'ops/ci/gen_whitepaper.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_status_is_honest(self):
        import gen_whitepaper as g
        n = sum(d['all_hard'] for d in g.rsv2())
        s = g.status()
        self.assertIn(f'{n} of', s)
        if n == 0:
            self.assertIn('not v1.0.0', s)

    def test_components_cover_four_parts(self):
        c = json.load(open(os.path.join(ROOT, 'docs/figures/components/components.json')))
        self.assertEqual([x['component'] for x in c['components']], ['ring', 'grip_spine', 'blade', 'tip'])
        self.assertAlmostEqual(sum(x['area_share'] for x in c['components']), 1.0, places=6)


if __name__ == '__main__':
    unittest.main()
