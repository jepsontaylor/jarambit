import json, os, re, subprocess, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


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

    def test_record_badges_generated_from_committed_json(self):
        from ops.ci import gen_readme
        rec_subj, rec_eval, rec_bat = gen_readme.current_record()
        self.assertEqual(rec_subj, 'w282_p14_c01')
        self.assertFalse(gen_readme.js('evidence/rs_v2/w283_ultrarunner/w283_p14_c01_cad_eval.json')['weighted_cad_score']['all_engineering_gates_pass'])
        em = rec_eval['engineering_metrics']
        wsc = rec_eval['weighted_cad_score']
        g1 = rec_bat['global_fitness']['G']
        self.assertAlmostEqual(em['mass_g'], 75.568, places=3)
        self.assertAlmostEqual(em['mass_3d_g'], 75.323, places=3)
        self.assertAlmostEqual(g1, gen_readme.js('evidence/cad_battery/w282_p14_c01.json')['global_fitness']['G'])

        t = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
        head_match = re.search(r'<!-- GEN:HEAD:BEGIN -->\n(.*?)\n<!-- GEN:HEAD:END -->', t, re.S)
        self.assertIsNotNone(head_match)
        head_block = head_match.group(1)
        self.assertIn(f'historical%20record-{rec_subj.replace("_", "__")}', head_block)
        self.assertIn(f'mass-{em["mass_g"]:.3f}%20g%20%28{em["mass_3d_g"]:.3f}%20g%203D%29', head_block)
        self.assertIn(f'G1-{g1:.6f}', head_block)
        self.assertIn(f'W__CAD-%2B{wsc["W_CAD"]:.4f}', head_block)
        # Ensure stale Wave-27 badges are never emitted in GEN:HEAD
        self.assertNotIn('mass-84.80%20g', head_block)
        self.assertNotIn('G1-0.9804', head_block)

    def test_short_readme_hero_plot_install_quickstart_and_claim_admission(self):
        t = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()
        for section in (
            'docs/figures/whitepaper/fig_readme_mass_vs_wave.png',
            'docs/figures/whitepaper/fig_web_studio.png',
            '## What it is',
            '## Install',
            '## Quick start',
            'docs/WHITEPAPER.md',
            'docs/ENGINEERING_GATES_AND_EVOLUTION.md',
            '`w283_p14_c01`',
            '`w283_p10_c02`',
            '`w282_p14_c01`',
            '`w282_p10_c02`',
            '`w281_s2932_c01`',
            '`w280_s2931_c01`',
            '`w279_s2928_c01`',
            '`w278_s2922_c01`',
            '`w277_s2919_c01`',
            '`w276_s2913_c01`',
            '`w275_s2909_c01`',
            '`w274_s2905_c01`',
        ):
            self.assertIn(section, t)
        # Hero figure must appear near the top before Install, Quick start, and Market weight comparison
        idx_hero = t.index('docs/figures/whitepaper/fig_readme_mass_vs_wave.png')
        idx_install = t.index('## Install')
        idx_quick = t.index('## Quick start')
        idx_market = t.index('## Market weight comparison')
        self.assertLess(idx_hero, idx_install)
        self.assertLess(idx_install, idx_quick)
        self.assertLess(idx_quick, idx_market)
        from ops.ci import claim_admission
        self.assertEqual(claim_admission.public_document_check(ROOT), [])

    def test_every_battery_and_pareto_number_traces_to_committed_json(self):
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
        from collections import Counter
        from ops.ci import gen_readme
        counts = Counter(c['status'] for s in gen_readme.BATTERY_SUBJECTS
                         for c in gen_readme.js(f'evidence/cad_battery/{s}.json')['cases'])
        self.assertEqual(n_subj, len(gen_readme.BATTERY_SUBJECTS))
        self.assertEqual((np_, nf_, nb_, ni_), tuple(counts[k] for k in ('pass', 'fail', 'blocked', 'incomplete')))
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
            ('w279_s2928_c01', 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_rs.json'),
            ('w280_s2931_c01', 'evidence/rs_v2/w280_ultrarunner/w280_s2931_c01_rs.json'),
            ('w281_s2932_c01', 'evidence/rs_v2/w281_ultrarunner/w281_s2932_c01_rs.json'),
            ('w282_p10_c02', 'evidence/rs_v2/w282_ultrarunner/w282_p10_c02_rs.json'),
            ('w282_p14_c01', 'evidence/rs_v2/w282_ultrarunner/w282_p14_c01_rs.json'),
            ('w283_p10_c02', 'evidence/rs_v2/w283_ultrarunner/w283_p10_c02_rs.json'),
            ('w283_p14_c01', 'evidence/rs_v2/w283_ultrarunner/w283_p14_c01_rs.json'),
        ):
            with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
                r = json.load(fh)
            self.assertIn(f'{r["fat_sf"]:.4f}', eg, f'missing fat_sf for {name}')
            self.assertIn(f'{r["ring_bearing_w_mm"]:.2f}', eg, f'missing ring_bearing_w_mm for {name}')


if __name__ == '__main__':
    unittest.main()
