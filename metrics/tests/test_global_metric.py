"""PR-0.28.1: G1 completeness contract. Run: python3 -m unittest discover -s metrics/tests -v"""
import glob, json, math, os, random, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'metrics'))
import global_metric as gm  # noqa: E402

FIX = os.path.join(HERE, 'fixtures')
REQ = ['solid_tip_sf_nodal_max', 'spg', 'aes_score', 'mass_g', 'seq_ratio']
COMPLETE = dict(solid_tip_sf_nodal_max=1.5, spg=4.0, aes_score=0.6, mass_g=80.0, seq_ratio=0.9)
BAD = {'missing': None, 'null': None, 'nan': float('nan'), 'inf': float('inf'), 'bool': True,
       'malformed': 'abc', 'out_of_range': -5.0}


def _load(p):
    with open(p) as fh:
        return json.load(fh)


def legacy_G(rec):
    """Verbatim G1 arithmetic from v0.27.0 (727b28b) for complete records."""
    def f(v):
        try:
            v = float(v)
            return v if math.isfinite(v) else None
        except (TypeError, ValueError):
            return None
    tip = f(rec.get('solid_tip_sf_nodal_max'))
    if tip is None:
        tip = f(rec.get('plate_tipsub_screen_sf'))
    if tip is None:
        tip = f(rec.get('twist_tipzone_sf_strict'))
    return (0.35 * min(tip, 2.0) + 0.35 * rec['spg'] / 4.0 + 0.20 * rec['aes_score']
            - 0.05 * max(0.0, rec['mass_g'] - 77.0) / 10.0 - 0.05 * max(0.0, 1.2 - rec['seq_ratio']) / 1.2)


class Completeness(unittest.TestCase):
    def test_complete_smoke_matches_ci_value(self):
        g, t = gm.global_G(COMPLETE)
        self.assertEqual(t['status'], 'COMPLETE')
        self.assertAlmostEqual(g, 0.9675, delta=1e-9)
        self.assertFalse(t['provisional'])

    def test_35_bad_input_cases_are_incomplete(self):
        n = 0
        for key in REQ:
            for kind, val in BAD.items():
                rec = dict(COMPLETE)
                if kind == 'missing':
                    del rec[key]
                else:
                    rec[key] = val
                if kind == 'out_of_range' and key == 'aes_score':
                    rec[key] = 1.7
                if key == 'solid_tip_sf_nodal_max':  # ensure no fallback hides the defect
                    rec.pop('plate_tipsub_screen_sf', None)
                g, t = gm.global_G(rec)
                with self.subTest(key=key, kind=kind):
                    self.assertIsNone(g)
                    self.assertEqual(t['status'], 'INCOMPLETE')
                    self.assertTrue(t['missing'])
                    tag = gm.title_tag(rec, '0.0.0')  # must never raise
                    self.assertIn('INCOMPLETE', tag)
                n += 1
        self.assertEqual(n, 35)

    def test_empty_record(self):
        g, t = gm.global_G({})
        self.assertIsNone(g)
        self.assertEqual(len(t['missing']), 5)

    def test_tip_only_record_is_incomplete_not_unstarred_complete(self):
        g, t = gm.global_G({'solid_tip_sf_nodal_max': 1.5})
        self.assertIsNone(g)
        self.assertEqual(t['status'], 'INCOMPLETE')

    def test_genuine_zero_is_a_value(self):
        rec = dict(COMPLETE, seq_ratio=0.0, aes_score=0.0)
        g, t = gm.global_G(rec)
        self.assertEqual(t['status'], 'COMPLETE')
        self.assertAlmostEqual(g, legacy_G(rec), delta=1e-12)

    def test_numeric_strings_accepted(self):
        rec = {k: str(v) for k, v in COMPLETE.items()}
        g, _ = gm.global_G(rec)
        self.assertAlmostEqual(g, 0.9675, delta=1e-9)

    def test_screen_fallback_is_provisional_and_complete(self):
        rec = dict(COMPLETE); del rec['solid_tip_sf_nodal_max']; rec['plate_tipsub_screen_sf'] = 1.5
        g, t = gm.global_G(rec)
        self.assertTrue(t['provisional'])
        self.assertEqual(t['status'], 'COMPLETE')
        self.assertIn('G* ', gm.title_tag(rec, '0.0.0'))

    def test_deleting_input_never_increases_G_property(self):
        rng = random.Random(28_1)
        for _ in range(1000):
            rec = dict(solid_tip_sf_nodal_max=rng.uniform(0.5, 2.5), spg=rng.uniform(2, 5), aes_score=rng.random(),
                       mass_g=rng.uniform(60, 100), seq_ratio=rng.uniform(0.5, 1.5))
            g0, _ = gm.global_G(rec)
            self.assertIsNotNone(g0)
            for k in REQ:
                r = dict(rec); del r[k]
                g1, t1 = gm.global_G(r)
                self.assertIsNone(g1, k)  # incomplete -> unrankable, never a higher number

    def test_fixture_files(self):
        exp = _load(os.path.join(FIX, 'expected.json'))
        for name, want in exp.items():
            rec = _load(os.path.join(FIX, name))
            g, t = gm.global_G(rec)
            with self.subTest(fixture=name):
                self.assertEqual(t['status'], want['status'])
                if want['G'] is None:
                    self.assertIsNone(g)
                else:
                    self.assertAlmostEqual(g, want['G'], delta=1e-9)


class Golden(unittest.TestCase):
    def test_wave27_indices_match_legacy_to_1e9(self):
        files = sorted(glob.glob(os.path.join(ROOT, 'docs', 'wave27_diversity', '*', '*_D1_index.json')))
        self.assertTrue(files)
        n = 0
        for f in files:
            for r in _load(f):
                g, t = gm.global_G(r)
                self.assertEqual(t['status'], 'COMPLETE', r.get('label'))
                self.assertAlmostEqual(g, legacy_G(r), delta=1e-9)
                n += 1
        self.assertEqual(n, 42)

    def test_global_metric_md_table_rows(self):
        # docs/GLOBAL_METRIC.md best-G-per-wave rows (3-dp published values)
        rows = [  # (tip, solid?, spg, aes, mass, seq, G)
            (1.164, True, 3.994, 0.673, 83.4, 0.926, 0.848), (1.107, True, 3.839, 0.710, 85.9, 0.891, 0.808),
            (1.345, True, 3.853, 0.636, 83.9, 0.831, 0.885), (1.425, True, 3.996, 0.629, 84.6, 0.916, 0.925),
            (1.527, True, 4.070, 0.645, 85.6, 0.952, 0.966), (1.527, True, 3.726, 0.648, 82.0, 0.879, 0.952),
            (1.594, True, 3.859, 0.593, 81.8, 0.888, 0.977), (1.636, False, 3.747, 0.591, 81.9, 0.842, 0.979)]
        for tip, solid, spg, aes, m, seq, G in rows:
            rec = dict(spg=spg, aes_score=aes, mass_g=m, seq_ratio=seq)
            rec['solid_tip_sf_nodal_max' if solid else 'plate_tipsub_screen_sf'] = tip
            g, t = gm.global_G(rec)
            self.assertAlmostEqual(g, G, delta=1.5e-3)  # inputs published at 3-4 dp
            self.assertEqual(t['provisional'], not solid)
        # wave26 row has no aes -> must be INCOMPLETE, not a number
        g, t = gm.global_G(dict(solid_tip_sf_nodal_max=1.525, spg=4.158, mass_g=84.6, seq_ratio=0.959))
        self.assertIsNone(g)

    def test_provisional_design(self):
        rows = _load(os.path.join(ROOT, 'docs', 'wave27_diversity', 'plates', 'wave27_D1_index.json'))
        r = next(x for x in rows if x['label'] == 'g3_tip+00_t60_tt3_D1')
        g, t = gm.global_G(r)
        self.assertAlmostEqual(g, 0.98042, delta=5e-5)
        self.assertFalse(t['provisional'])


if __name__ == '__main__':
    unittest.main()
