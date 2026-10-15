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

LIVE = (
    'c10a', 'c93', 'c92',
    'g3', 'w271b_11772', 'w271b_11860', 'w271c_11522',
    'w272_s2902_c01', 'w273_s2904_c01', 'w273_s2903_c04',
)
GENOMES = (
    'g3', 'w271b_11772', 'w271b_11860', 'w271c_11522',
    'w272_s2902_c01', 'w273_s2904_c01', 'w273_s2903_c04',
)


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
            dolfinx_case = next(case for case in record['cases'] if case['id'] == 'build.dolfinx')
            self.assertEqual(dolfinx_case['status'], 'pass')

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
            'g3': {'n_tet': 739584, 'n_dof': 3169395, 'ksp_its': 74, 'sf': 1.6003, 'rerun': False, 'G': 1.0036274369238576},
            'w271b_11772': {'n_tet': 603648, 'n_dof': 2590443, 'ksp_its': 85, 'sf': 0.8337, 'rerun': False, 'G': 0.7505798795492734},
            'w271b_11860': {'n_tet': 76560, 'n_dof': 351297, 'ksp_its': 54, 'sf': 0.814, 'rerun': True, 'G': 0.7216545740786019},
            'w271c_11522': {'n_tet': 80160, 'n_dof': 367767, 'ksp_its': 57, 'sf': 1.033, 'rerun': True, 'G': 0.7597240123135478},
            'w272_s2902_c01': {'n_tet': 71952, 'n_dof': 330453, 'ksp_its': 52, 'sf': 0.875, 'rerun': True, 'G': 0.7523889572632168},
            'w273_s2904_c01': {'n_tet': 71952, 'n_dof': 330453, 'ksp_its': 52, 'sf': 0.875, 'rerun': True, 'G': 0.7602536724290332},
            'w273_s2903_c04': {'n_tet': 71952, 'n_dof': 330453, 'ksp_its': 51, 'sf': 0.875, 'rerun': True, 'G': 0.7509316126056635},
        }
        for name, want in expected.items():
            tip = next(case for case in self.records[name]['cases'] if case['id'] == 'solid.tip')
            self.assertEqual(tip['status'], 'pass')
            self.assertEqual(tip['detail']['solve_rerun'], want['rerun'])
            self.assertEqual(tip['detail']['n_tet'], want['n_tet'])
            self.assertEqual(tip['detail']['n_dof'], want['n_dof'])
            self.assertEqual(tip['detail']['ksp_its'], want['ksp_its'])
            self.assertEqual(tip['g_inputs']['solid_tip_sf_nodal_max'], want['sf'])
            self.assertNotIn('plate_tipsub_screen_sf', self.records[name]['global_fitness']['inputs'])
            self.assertEqual(self.records[name]['global_fitness']['status'], 'COMPLETE')
            self.assertAlmostEqual(self.records[name]['global_fitness']['G'], want['G'], places=12)
            self.assertEqual(self.records[name]['solver_run_count'], 1)
        c10a_tip = next(case for case in self.records['c10a']['cases'] if case['id'] == 'solid.tip')
        self.assertEqual(c10a_tip['status'], 'pass')
        self.assertEqual(c10a_tip['detail']['n_tet'], 80496)
        self.assertEqual(c10a_tip['detail']['n_dof'], 372357)
        self.assertEqual(c10a_tip['detail']['ksp_its'], 125)
        self.assertEqual(c10a_tip['g_inputs']['solid_tip_sf_nodal_max'], 0.2101)
        self.assertEqual(self.records['c10a']['solver_run_count'], 1)
        for name in ('c93', 'c92', 'c10c'):
            tip = next(case for case in self.records[name]['cases'] if case['id'] == 'solid.tip')
            self.assertNotEqual(tip['status'], 'pass')
            self.assertNotIn('solid_tip_sf_nodal_max', self.records[name]['global_fitness']['inputs'])
        for name in ('c92', 'c93'):
            tip = next(case for case in self.records[name]['cases'] if case['id'] == 'solid.tip')
            self.assertEqual(tip['status'], 'blocked')
            self.assertFalse(tip['detail']['entered_as_solver_run'])
            self.assertIn('n_dof', tip['detail']['missing_fields'])
            self.assertIn('ksp_its', tip['detail']['missing_fields'])

    def test_stored_solid_tip_without_ksp_its_stays_incomplete_and_out_of_g(self):
        from unittest.mock import patch
        from ops.ci import cad_battery
        real_load = cad_battery._load

        def load_without_ksp(rel):
            doc = real_load(rel)
            if rel == 'evidence/cad_battery/tip_mesh/w271b_11860.json' and doc:
                doc = json.loads(json.dumps(doc))
                doc['stored_solid']['ksp_its'] = None
            return doc

        with patch('ops.ci.cad_battery._load', side_effect=load_without_ksp):
            rec = build_subject('w271b_11860', 'a' * 40, {'analytic': 'pass', 'gci': 'pass', 'claims': 'pass'})
        tip = next(case for case in rec['cases'] if case['id'] == 'solid.tip')
        self.assertEqual(tip['status'], 'incomplete')
        self.assertEqual(tip['reason'], 'missing ksp_its')
        self.assertEqual(tip['detail']['missing'], ['ksp_its'])
        self.assertIsNone(tip['detail']['ksp_its'])
        self.assertFalse(tip['detail']['entered_as_solver_run'])
        self.assertNotIn('g_inputs', tip)
        self.assertEqual(rec['solver_run_count'], 0)
        self.assertIsNone(rec['global_fitness']['G'])
        self.assertEqual(rec['global_fitness']['status'], 'INCOMPLETE')
        self.assertNotIn('solid_tip_sf_nodal_max', rec['global_fitness']['inputs'])

    def test_negative_fallbacks_for_dolfinx_side_a4_and_c10a_tip(self):
        from unittest.mock import patch
        from ops.ci import cad_battery
        real_load = cad_battery._load

        def load_without_side_and_c10a(rel):
            if rel in ('evidence/cad_battery/side/g3_a4.json', 'evidence/cad_battery/side/c10a_solid_tip.json'):
                return None
            return real_load(rel)

        with patch('ops.ci.cad_battery._load', side_effect=load_without_side_and_c10a):
            g3_rec = build_subject('g3', 'a' * 40, {'analytic': 'pass', 'gci': 'pass', 'claims': 'pass', 'dolfinx': 'blocked'})
            c10a_rec = build_subject('c10a', 'a' * 40, {'dolfinx': 'blocked'}, measure=False)
        d_case = next(row for row in g3_rec['cases'] if row['id'] == 'build.dolfinx')
        self.assertEqual(d_case['status'], 'blocked')
        self.assertEqual(d_case['reason'], 'ModuleNotFoundError: No module named dolfinx')
        a4 = next(row for row in g3_rec['cases'] if row['id'] == 'side.a4')
        self.assertEqual(a4['status'], 'incomplete')
        self.assertEqual(a4['reason'], 'run_b default BC is the certified model')
        self.assertEqual(a4['detail']['buckling_eigenvalue'], 'absent')
        self.assertFalse(a4['detail']['partial_solver_edit'])
        c10a_tip = next(row for row in c10a_rec['cases'] if row['id'] == 'solid.tip')
        self.assertEqual(c10a_tip['status'], 'blocked')
        self.assertEqual(c10a_tip['detail']['inventory_solver_runs'], 0)

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
        for name in ('c10a', 'c93', 'c92'):
            for case_id in ('side.a1', 'side.a2', 'side.a3'):
                case = next(row for row in self.records[name]['cases'] if row['id'] == case_id)
                self.assertNotEqual(case['status'], 'pass')
                self.assertNotIn('3e419ac1', json.dumps(case))
        for name in ('w271b_11772', 'w271b_11860', 'w271c_11522', 'w272_s2902_c01', 'w273_s2904_c01', 'w273_s2903_c04'):
            for case_id in ('side.a1', 'side.a2', 'side.a3'):
                case = next(row for row in self.records[name]['cases'] if row['id'] == case_id)
                self.assertEqual(case['status'], 'pass')
                self.assertNotIn('3e419ac1', json.dumps(case))
                self.assertIn(name, case['evidence_path'])
        for name, want_status in (
            ('g3', 'pass'),
            ('w271b_11772', 'fail'),
            ('w271b_11860', 'fail'),
            ('w271c_11522', 'pass'),
            ('w272_s2902_c01', 'fail'),
            ('w273_s2904_c01', 'pass'),
            ('w273_s2903_c04', 'fail'),
        ):
            gci = next(row for row in self.records[name]['cases'] if row['id'] == 'plate.gci')
            self.assertEqual(gci['status'], want_status)
            self.assertIn(name, gci['evidence_path'])
        seq = next(row for row in self.records['w271b_11772']['cases'] if row['id'] == 'plate.seq')
        self.assertEqual(seq['status'], 'fail')
        self.assertEqual(seq['detail']['seq_ratio'], 0.8823392882835103)
        for name in GENOMES:
            a4 = next(row for row in self.records[name]['cases'] if row['id'] == 'side.a4')
            self.assertEqual(a4['status'], 'pass')
            self.assertFalse(a4['detail']['partial_solver_edit'])
            self.assertFalse(a4['detail']['changes_seq_ratio'])
            self.assertGreaterEqual(a4['detail']['buckling_eigenvalue'], 1.2)

    def test_dolfinx_cross_check_covers_all_seven_genomes_within_two_percent(self):
        cross = json.loads((ROOT / 'evidence' / 'cad_battery' / 'dolfinx_cross_check.json').read_text(encoding='utf-8'))
        self.assertTrue(cross['all_within_2pct'])
        for name in GENOMES:
            row = cross['subjects'][name]
            self.assertEqual(row['status'], 'pass')
            self.assertTrue(row['within_2pct'])
            self.assertLessEqual(row['rel_err_nodal_max'], 0.02)
            self.assertLessEqual(row['rel_err_nodal_avg'], 0.02)
            self.assertGreater(row['dolfinx']['ksp_its'], 0)

    def test_side_a4_reports_cover_all_seven_genomes_without_certified_solver_edit(self):
        for name in GENOMES:
            side_a4 = json.loads((ROOT / 'evidence' / 'cad_battery' / 'side' / f'{name}_a4.json').read_text(encoding='utf-8'))
            self.assertEqual(side_a4['status'], 'pass')
            self.assertFalse(side_a4['partial_solver_edit'])
            self.assertFalse(side_a4['changes_seq_ratio'])
            self.assertGreaterEqual(side_a4['buckling_eigenvalue'], 1.2)
            self.assertGreater(side_a4['supported_seq_ratio'], side_a4['certified_seq_ratio'])

    def test_c10a_step_solid_tip_and_w272_w273_g1_eval_are_cross_checked(self):
        c10a_side = json.loads((ROOT / 'evidence' / 'cad_battery' / 'side' / 'c10a_solid_tip.json').read_text(encoding='utf-8'))
        self.assertEqual(c10a_side['subject'], 'c10a')
        self.assertGreater(c10a_side['n_tet'], 10000)
        self.assertGreater(c10a_side['n_dof'], 50000)
        self.assertGreater(c10a_side['ksp_its'], 0)
        self.assertTrue(c10a_side['dolfinx_cross_check']['within_2pct'])
        self.assertLessEqual(c10a_side['dolfinx_cross_check']['rel_err_nodal_max'], 0.02)

        for rel in (
            'evidence/rs_v2/w272_xbabe3/w272_s2902_c01_g1_eval.json',
            'evidence/rs_v2/w273_xbabe3/w273_s2904_c01_g1_eval.json',
            'evidence/rs_v2/w273_xbabe3/w273_s2903_c04_g1_eval.json',
        ):
            ev = json.loads((ROOT / rel).read_text(encoding='utf-8'))
            self.assertEqual(ev['terms']['status'], 'COMPLETE')
            self.assertFalse(ev['terms']['provisional'])
            self.assertTrue(ev['dolfinx_cross_check']['within_2pct'])
            self.assertLessEqual(ev['dolfinx_cross_check']['rel_err_nodal_max'], 0.02)
        seeds_lines = (ROOT / 'evidence' / 'rs_v2' / 'w272_xbabe3' / 'w273_seeds.csv').read_text(encoding='utf-8').strip().splitlines()
        self.assertEqual(len(seeds_lines), 17)


