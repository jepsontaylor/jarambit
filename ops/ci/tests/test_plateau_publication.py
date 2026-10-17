"""Check publication observations independently of the plotting implementation."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = 'evidence/evolution_plateau/2026-10-17'


def load(name):
    return json.loads((ROOT / name).read_text())


def at(document, pointer):
    for key in pointer.split('/')[1:]:
        key = key.replace('~1', '/').replace('~0', '~')
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


class PlateauPublication(unittest.TestCase):
    def test_every_plotted_value_matches_committed_json(self):
        ledger = load('docs/figures/engineering_gates/plateau_points.json')
        manifest = load('docs/figures/engineering_gates/fig_plateau_history.png.manifest.json')
        documents = {}
        for point in ledger['points']:
            source = point['source']
            with self.subTest(source=source, metric=point['metric']):
                self.assertTrue(source.startswith(SNAPSHOT + '/'))
                self.assertIn(source, manifest['inputs'])
                if source not in documents:
                    committed = subprocess.check_output(['git', 'show', 'HEAD:' + source], cwd=ROOT)
                    self.assertEqual((ROOT / source).read_bytes(), committed)
                    documents[source] = json.loads(committed)
                document = documents[source]
                if 'pointers' in point:
                    values = [at(document, p) for p in point['pointers']]
                    if point['reduction'] == 'distinct values':
                        expected = len(set(values))
                    else:
                        self.assertEqual(point['reduction'], 'count equal')
                        expected = values.count(point['equals'])
                else:
                    expected = at(document, point['pointer'])
                    if point.get('reduction') == 'array length':
                        expected = len(expected)
                self.assertIs(type(point['value']), type(expected))
                self.assertEqual(point['value'], expected)

    def test_partial_snapshots_never_become_completed_waves_or_certificates(self):
        ledger = load('docs/figures/engineering_gates/plateau_points.json')
        expected = {'w298': ('final leaderboard', 6), 'w401c3': ('final leaderboard', 4),
                    'w300': ('partial capture', 0), 'w402c3': ('partial capture', 1)}
        for wave in ledger['waves']:
            name = wave['wave']
            self.assertEqual((wave['snapshot'], wave['captured_assessments']), expected[name])
            self.assertEqual(len(wave['scorecards']), wave['captured_assessments'])
            host = 'xbabe2' if name in {'w298', 'w300'} else 'xbabe3'
            folder = ROOT / SNAPSHOT / host / 'out' / name
            self.assertEqual(sorted(wave['scorecards']), sorted(str(p.relative_to(ROOT))
                for p in folder.glob('by-content/*/*/*_master_scorecard.json')))
            for source in wave['scorecards']:
                score = load(source)
                rs = load(source.replace('_master_scorecard.json', '_rs.json'))
                self.assertFalse(score['weighted_cad_score']['all_engineering_gates_pass'])
                self.assertFalse(rs['all_hard'])
                self.assertEqual({k for k, v in score['weighted_cad_score']['gates'].items() if not v}, {
                    'cert_hiker_180n', 'cert_hunter_260n', 'strict_hunter_260n',
                    'twist_tip_only_1p82nm', 'twist_tip_submodel_strict_1p82nm',
                    'solid_tip_3d_p2_1p82nm'})
        self.assertEqual(sum(w['captured_assessments'] for w in ledger['waves']), 11)
        self.assertIn('not current certificates', ledger['scope'])
