"""Battery records keep G1 and the pass count from rising when an input disappears."""
import json
import os
import subprocess
import sys
import unittest

from metrics.global_metric import global_G
from ops.ci.cad_battery import (
    CASE_IDS, ROOT, build_subject, pass_count, synthetic_complete, without_key,
)

LIVE = ('c10a', 'c93', 'c92', 'g3', 'w271b_11772', 'w271b_11860', 'w271c_11522')


class Deletion(unittest.TestCase):
    def test_deleting_a_key_cannot_raise_g_or_the_pass_count(self):
        record = synthetic_complete()
        original = record['global_fitness']['G']
        self.assertAlmostEqual(original, 0.9675, places=9)
        passes = record['pass_count']
        for key in list(record['global_fitness']['inputs']):
            reduced = without_key(record, key, '0.31.0')
            self.assertIsNone(reduced['global_fitness']['G'])
            self.assertLess(reduced['pass_count'], passes)
            self.assertLessEqual(reduced['solver_run_count'], record['solver_run_count'])

    def test_a_blocked_sequence_is_not_a_zero(self):
        record = build_subject('c10a', 'b' * 40, {}, measure=False)
        self.assertNotIn('seq_ratio', record['global_fitness']['inputs'])
        self.assertIsNone(record['global_fitness']['G'])
        self.assertEqual(record['global_fitness']['status'], 'INCOMPLETE')


class Records(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = ROOT / 'evidence' / 'cad_battery'
        cls.records = {}
        for name in LIVE + ('c10c',):
            path = directory / f'{name}.json'
            if not path.is_file():
                raise RuntimeError(f'missing battery record {path}')
            cls.records[name] = json.loads(path.read_text(encoding='utf-8'))

    def test_live_subjects_share_case_ids(self):
        for name, record in self.records.items():
            self.assertEqual([case['id'] for case in record['cases']], list(CASE_IDS))
            self.assertIn(record['global_fitness']['status'], ('COMPLETE', 'INCOMPLETE'))
            if record['global_fitness']['G'] is None:
                self.assertTrue(record['global_fitness']['missing'])
            self.assertEqual(record['search_fitness'], 'unchanged')
            completed = sum(case['kind'] == 'solver_run' and case['status'] == 'pass' for case in record['cases'])
            self.assertEqual(record['solver_run_count'], completed)

    def test_reference_mesh_count_matches_the_stored_solid(self):
        script = ROOT / 'fem_solid' / 'tip_solid.py'
        design = ROOT / 'evidence' / 'wave27' / 'g3_tip+00_t60_tt3_D1.json'
        completed = subprocess.run(
            [sys.executable, '-B', str(script), str(design), '30', '4', '1', '/tmp/g3-count-test.json'],
            cwd=ROOT, capture_output=True, text=True, check=False,
            env={**os.environ, 'COUNT_ONLY': '1', 'OMP_NUM_THREADS': '1'})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        line = next(item for item in completed.stdout.splitlines() if item.startswith('COUNT '))
        counted = json.loads(line.split(' ', 1)[1])
        self.assertEqual((counted['n_tet'], counted['n_dof']), (92448, 422955))

    def test_tip_counts_match_the_stored_solves(self):
        expected = {
            'g3': {'n_tet': 739584, 'n_dof': 3169395, 'ksp_its': 74, 'sf': 1.6003},
            'w271b_11772': {'n_tet': 603648, 'n_dof': 2590443, 'ksp_its': 85, 'sf': 0.8337},
        }
        for name, want in expected.items():
            tip = next(case for case in self.records[name]['cases'] if case['id'] == 'solid.tip')
            self.assertEqual(tip['status'], 'pass')
            self.assertEqual(tip['detail']['solve_rerun'], False)
            self.assertEqual(tip['detail']['n_tet'], want['n_tet'])
            self.assertEqual(tip['detail']['n_dof'], want['n_dof'])
            self.assertEqual(tip['detail']['ksp_its'], want['ksp_its'])
            self.assertEqual(tip['g_inputs']['solid_tip_sf_nodal_max'], want['sf'])
            self.assertNotIn('plate_tipsub_screen_sf', self.records[name]['global_fitness']['inputs'])
            self.assertEqual(self.records[name]['global_fitness']['status'], 'COMPLETE')
            self.assertIsNotNone(self.records[name]['global_fitness']['G'])
        for name in ('c10a', 'c93', 'c92', 'c10c', 'w271b_11860', 'w271c_11522'):
            tip = next(case for case in self.records[name]['cases'] if case['id'] == 'solid.tip')
            self.assertNotEqual(tip['status'], 'pass')
            self.assertNotIn('solid_tip_sf_nodal_max', self.records[name]['global_fitness']['inputs'])

    def test_g3_sequence_stays_failed_and_c10c_is_not_restored(self):
        seq = next(case for case in self.records['g3']['cases'] if case['id'] == 'plate.seq')
        self.assertEqual(seq['status'], 'fail')
        self.assertLess(seq['detail']['seq_ratio'], 1.2)
        self.assertEqual(self.records['c10c']['role'], 'archived_not_on_main')
        present = subprocess.run(
            ['git', 'cat-file', '-e', 'HEAD:designs/switchback/C10c/README.md'],
            cwd=ROOT, capture_output=True)
        self.assertNotEqual(present.returncode, 0)

    def test_recorded_inputs_do_not_rise_when_deleted(self):
        version = (ROOT / 'docs' / 'VERSION').read_text(encoding='utf-8').strip()
        for record in self.records.values():
            original = record['global_fitness']['G']
            passes = pass_count(record['cases'])
            for key in list(record['global_fitness']['inputs']):
                reduced = without_key(record, key, version)
                later = reduced['global_fitness']['G']
                if original is None:
                    self.assertIsNone(later)
                else:
                    self.assertTrue(later is None or later <= original)
                self.assertLessEqual(reduced['pass_count'], passes)
                # The assembled G uses only the keys still present.
                again, _terms = global_G(reduced['global_fitness']['inputs'])
                self.assertEqual(again, later)

    def test_native_subjects_do_not_inherit_g3_areas(self):
        for name in ('c10a', 'c93', 'c92', 'w271b_11772', 'w271b_11860', 'w271c_11522'):
            for case_id in ('side.a1', 'side.a2', 'side.a3'):
                case = next(row for row in self.records[name]['cases'] if row['id'] == case_id)
                self.assertNotEqual(case['status'], 'pass')
                self.assertNotIn('3e419ac1', json.dumps(case))
