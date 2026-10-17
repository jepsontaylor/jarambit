"""Check published observations against evidence, without reusing plot reductions."""
import json
from pathlib import Path
import statistics
import unittest

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    return json.loads((ROOT / name).read_text())


def at(document, pointer):
    for key in pointer.split('/')[1:]:
        key = key.replace('~1', '/').replace('~0', '~')
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


class PaperObservations(unittest.TestCase):
    def test_every_new_plotted_value_reduces_actual_evidence(self):
        ledger = load('docs/figures/engineering_gates/certifiable_points.json')
        manifest = load('docs/figures/engineering_gates/fig_certifiable_pipeline.png.manifest.json')
        for point in ledger['points']:
            with self.subTest(point=point):
                self.assertIn(point['source'], manifest['inputs'])
                self.assertTrue(point['source'].startswith('evidence/'))
                document = load(point['source'])
                if 'pointers' in point:
                    values = [at(document, p) for p in point['pointers']]
                    expected = len(set(values)) if point['reduction']=='distinct content identities' else statistics.median(values)
                else:
                    expected = at(document, point['pointer'])
                    if point.get('reduction')=='array length':expected = len(expected)
                self.assertIs(type(point['value']), type(expected))
                self.assertEqual(point['value'], expected)
                if 'plotted_ratio' in point:
                    self.assertEqual(point['plotted_ratio'], expected/point['divisor'])

    def test_atlas_is_the_assessed_failure_with_exact_gate_verdicts(self):
        proof = load('evidence/evolve_certifiable/manifest.json')['automatic']
        artifacts = proof['artifacts']
        board = load(artifacts['leaderboard'])
        score = load(artifacts['scorecard'])
        gates = score['weighted_cad_score']['gates']
        self.assertIsNone(board['champion'])
        self.assertEqual(board['qualified_count'], 0)
        self.assertFalse(load(artifacts['rs'])['all_hard'])
        for scene in list(gates)+['hero_oblique', 'hero_reverse', 'hero_section']:
            manifest = load('docs/figures/whitepaper/blender/'+scene+'.webp.manifest.json')
            extra = manifest['extra']
            with self.subTest(scene=scene):
                self.assertEqual(extra['subject'], proof['label'])
                self.assertEqual(extra['certificate_identity'], proof['certificate_identity'])
                self.assertEqual(extra['gate_verdict'], gates.get(scene))
                self.assertEqual(extra['qualified_count'], 0)
                self.assertFalse(extra['rs_v2_all_hard'])
                self.assertIn('not qualified', extra['status'])
                self.assertIn('champion=null', extra['status'])
                text=' '.join(c['text'] for c in extra['captions'])
                self.assertIn('ASSESSED EXAMPLE', text)
                self.assertIn('CHAMPION = NULL', text)
                if scene in gates:
                    self.assertIn('W_CAD_v2 gate: '+('PASS' if gates[scene] else 'FAIL'), text)
                for key in ['stl', 'd1', 'scorecard', 'rs', 'leaderboard']:
                    self.assertIn(artifacts[key], manifest['inputs'])


if __name__ == '__main__':unittest.main()
