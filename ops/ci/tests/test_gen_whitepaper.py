import atexit, json, os, shutil, subprocess, sys, unittest
import tempfile
_TMP_DIR = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _TMP_DIR, ignore_errors=True)
MAN_TMP = os.path.join(_TMP_DIR, 'x')
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

    def test_page1_hero_figures_and_gate_margins(self):
        wp = open(os.path.join(ROOT, 'docs/WHITEPAPER.md'), encoding='utf-8').read()
        intro_idx = wp.index('## I. Introduction')
        page1 = wp[:intro_idx]
        self.assertIn('figures/whitepaper/fig_why_this_matters.png', page1)
        self.assertIn('figures/whitepaper/fig_w279_gate_margins.png', page1)
        self.assertIn('figures/whitepaper/fig_web_studio.png', page1)
        self.assertNotIn('media/g3_tip+00_t60_tt3_turntable.gif', page1)
        self.assertNotIn('figures/whitepaper/wave27_g3_tip+00_t60_tt3_STEP_3D.png', page1)
        ev = json.load(open(os.path.join(ROOT, 'evidence/rs_v2/w283_ultrarunner/w283_p14_c01_cad_eval.json'), encoding='utf-8'))
        bat = json.load(open(os.path.join(ROOT, 'evidence/cad_battery/w283_p14_c01.json'), encoding='utf-8'))
        em = ev['engineering_metrics']
        self.assertIn(f'{em["mass_g"]:.3f} g', page1)
        self.assertIn(f'{em["mass_3d_g"]:.3f} g', page1)
        self.assertIn(f'{bat["global_fitness"]["G"]:.6f}', page1)
        self.assertIn(f'+{ev["weighted_cad_score"]["W_CAD"]:.4f}', page1)
        for figure in ('fig_readme_mass_vs_wave', 'fig_why_this_matters', 'fig_w279_gate_margins', 'fig_web_studio'):
            manifest = json.load(open(os.path.join(ROOT, f'docs/figures/whitepaper/{figure}.png.manifest.json')))
            self.assertIn('evidence/rs_v2/w283_ultrarunner/w283_p14_c01_cad_eval.json', manifest['inputs'])
            self.assertIn('evidence/cad_battery/w283_p14_c01.json', manifest['inputs'])

    def test_components_cover_four_parts(self):
        c = json.load(open(os.path.join(ROOT, 'docs/figures/components/components.json')))
        self.assertEqual([x['component'] for x in c['components']], ['ring', 'grip_spine', 'blade', 'tip'])
        self.assertAlmostEqual(sum(x['area_share'] for x in c['components']), 1.0, places=6)

    def test_components_reject_mismatched_rsv2(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'ops/render/components.py'), '--stl', os.path.join(ROOT, 'evidence/wave27/g3_tip+00_t60_tt3.stl'),
                            '--d1', os.path.join(ROOT, 'evidence/wave27/g3_tip+00_t60_tt3_D1.json'), '--rsv2', os.path.join(ROOT, 'evidence/rs_v2/w271b_11772.json'),
                            '--out', os.path.join(os.path.dirname(MAN_TMP), 'mm')], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn('is not the D1 design', r.stderr)

    def test_components_reject_legacy_padded_genome(self):
        import csv
        sys.path.insert(0, os.path.join(ROOT, 'ops', 'render'))
        import components
        d1 = json.load(open(os.path.join(ROOT, 'evidence/wave27/g3_tip+00_t60_tt3_D1.json')))
        rs = json.load(open(os.path.join(ROOT, 'evidence/rs_v2/g3_tip+00_t60_tt3.json')))
        self.assertTrue(components.same_design(d1, rs)[0])
        rows = list(csv.reader(open(os.path.join(ROOT, rs['genome']))))
        leg = os.path.join(os.path.dirname(MAN_TMP), 'legacy.csv')
        with open(leg, 'w', newline='') as fh:
            w = csv.writer(fh); w.writerow(rows[0][:90] + ['material']); w.writerow(rows[1][:90] + [rows[1][-1]])
        self.assertFalse(components.same_design(d1, dict(rs, genome=leg))[0], 'legacy 90-gene CSV must not match')
        self.assertFalse(components.same_design(d1, dict(rs, mass_g=rs['mass_g'] + 3.0))[0], 'mass mismatch must not match')

    def test_tip_reports_locked_gate_values(self):
        c = json.load(open(os.path.join(ROOT, 'docs/figures/components/components.json')))
        tip = [x for x in c['components'] if x['component'] == 'tip'][0]['rs_v2']
        self.assertIn('twist_tipzone_sf_strict', tip); self.assertIn('solid_tip_sf', tip); self.assertNotIn('twist_tipzone_sf', tip)

    def test_caption_fits(self):
        try:
            from PIL import ImageFont
            f = ImageFont.truetype('DejaVuSans.ttf', 30)
        except (ImportError, OSError):
            self.skipTest('font unavailable')
        sys.path.insert(0, os.path.join(ROOT, 'ops', 'render'))
        import components
        for t in components.TITLE.values():
            self.assertLess(1000 + 40 + f.getlength(t), 2000, t)


if __name__ == '__main__':
    unittest.main()
