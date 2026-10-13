import hashlib, os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
D = os.path.join(ROOT, 'designs/switchback/C9.2')


class SwitchbackC92(unittest.TestCase):
    def test_sha256sums(self):
        for line in open(os.path.join(D, 'SHA256SUMS')):
            h, rel = line.split(None, 1); rel = rel.strip()
            if rel.startswith('release-asset/'):
                continue  # published as a GitHub release asset, not in git
            with self.subTest(rel=rel):
                self.assertEqual(hashlib.sha256(open(os.path.join(D, rel), 'rb').read()).hexdigest(), h)

    def test_status_is_release_candidate(self):
        t = open(os.path.join(D, 'README.md'), encoding='utf-8').read()
        self.assertIn('RELEASE CANDIDATE', t); self.assertIn('NOT the design of record', t)
        self.assertIn('not** a jarambit RS-karambit-v2 verdict', t)
        top = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
        self.assertRegex(top, r'C\.9\.2.*release candidate.*not.*design of record')


if __name__ == '__main__':
    unittest.main()
