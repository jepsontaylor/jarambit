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
            '### 16-Subject × 18-Evaluator CAD Battery & Multi-Wave Progression',
            '#### Margin-vs-Mass Pareto Progression',
            '`w278_s2922_c01`',
            '`w277_s2919_c01`',
            '`w276_s2913_c01`',
            '`w275_s2909_c01`',
            '`w274_s2905_c01`',
            '### 178-Group (356-Control) Scientific Assurance Catalog',
        ):
            self.assertIn(section, t)
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from ops.ci import claim_admission
        self.assertEqual(claim_admission.public_document_check(ROOT), [])

    def test_every_battery_and_pareto_number_traces_to_committed_json(self):
        import json
        t = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
        eg = open(os.path.join(ROOT, 'docs/ENGINEERING_GATES_AND_EVOLUTION.md'), encoding='utf-8').read()
        m = re.search(
            r'\*\*Battery total across (\d+) subjects × 18 evaluators \((\d+) cells\):\*\* `(\d+) pass`, `(\d+) fail`, `(\d+) blocked`(?:, `(\d+) incomplete`)?\.',
            t,
        )
        self.assertIsNotNone(m)
        n_subj, n_cells, np_, nf_, nb_, ni_ = (
            int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6) or 0)
        )
        self.assertEqual(n_subj * 18, n_cells)
        self.assertEqual(np_ + nf_ + nb_ + ni_, n_cells)
        # Ensure Table VI-2 in ENGINEERING_GATES_AND_EVOLUTION.md matches committed rs_v2 JSONs
        for name, rel in (
            ('g3_tip+00_t60_tt3', 'evidence/rs_v2/g3_tip+00_t60_tt3.json'),
            ('w271b_11772', 'evidence/rs_v2/w271b_11772.json'),
            ('w271b_11860', 'evidence/rs_v2/w271b_11860.json'),
            ('w271c_11522', 'evidence/rs_v2/w271c_11522.json'),
            ('w272_s2902_c01', 'evidence/rs_v2/w272_xbabe3/w272_s2902_c01_rs.json'),
            ('w273_s2903_c04', 'evidence/rs_v2/w273_xbabe3/w273_s2903_c04_rs.json'),
            ('w273_s2904_c01', 'evidence/rs_v2/w273_xbabe3/w273_s2904_c01_rs.json'),
            ('w274_s2905_c01', 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_rs.json'),
            ('w275_s2909_c01', 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_rs.json'),
            ('w276_s2913_c01', 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_rs.json'),
            ('w277_s2919_c01', 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_rs.json'),
            ('w278_s2922_c01', 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_rs.json'),
        ):
            with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
                r = json.load(fh)
            self.assertIn(f'{r["fat_sf"]:.4f}', eg, f'missing fat_sf for {name}')
            self.assertIn(f'{r["ring_bearing_w_mm"]:.2f}', eg, f'missing ring_bearing_w_mm for {name}')


if __name__ == '__main__':
    unittest.main()

