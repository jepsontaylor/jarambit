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

    def test_showcase_install_quickstart_and_claim_admission(self):
        t = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
        for section in (
            '## Install',
            '## Quick start',
            'docs/ENGINEERING_GATES_AND_EVOLUTION.md',
            'docs/figures/engineering_gates/fig1_evolutionary_trajectories.png',
            'docs/figures/engineering_gates/fig2_cad_battery_matrix_and_gci.png',
            'docs/figures/engineering_gates/fig3_cad_and_fem_gallery.png',
            '### 12-Subject × 18-Evaluator CAD Battery & Multi-Wave Progression',
            '`w274_s2905_c01`',
            '### 178-Group (356-Control) Scientific Assurance Catalog',
        ):
            self.assertIn(section, t)
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from ops.ci import claim_admission
        self.assertEqual(claim_admission.public_document_check(ROOT), [])


if __name__ == '__main__':
    unittest.main()
