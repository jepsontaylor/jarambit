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
    'w274_s2905_c01', 'w275_s2909_c01', 'w276_s2913_c01', 'w277_s2919_c01',
    'w278_s2922_c01',
)
GENOMES = (
    'g3', 'w271b_11772', 'w271b_11860', 'w271c_11522',
    'w272_s2902_c01', 'w273_s2904_c01', 'w273_s2903_c04',
    'w274_s2905_c01', 'w275_s2909_c01', 'w276_s2913_c01', 'w277_s2919_c01',
    'w278_s2922_c01',
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
            'w274_s2905_c01': {'n_tet': 90384, 'n_dof': 413613, 'ksp_its': 61, 'sf': 1.304, 'rerun': True, 'G': 0.7700579410566811},
            'w275_s2909_c01': {'n_tet': 90384, 'n_dof': 413613, 'ksp_its': 61, 'sf': 1.2967, 'rerun': True, 'G': 0.8015439464550428},
            'w276_s2913_c01': {'n_tet': 90384, 'n_dof': 413613, 'ksp_its': 61, 'sf': 1.3393, 'rerun': True, 'G': 0.8322600494582232},
            'w277_s2919_c01': {'n_tet': 90384, 'n_dof': 413613, 'ksp_its': 61, 'sf': 1.3393, 'rerun': True, 'G': 0.8347854224687924},
            'w278_s2922_c01': {'n_tet': 91008, 'n_dof': 416583, 'ksp_its': 73, 'sf': 1.3819, 'rerun': True, 'G': 0.8618220969105294},
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
        for name in ('w271b_11772', 'w271b_11860', 'w271c_11522', 'w272_s2902_c01', 'w273_s2904_c01', 'w273_s2903_c04', 'w274_s2905_c01', 'w275_s2909_c01', 'w276_s2913_c01', 'w277_s2919_c01', 'w278_s2922_c01'):
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
            ('w274_s2905_c01', 'fail'),
            ('w275_s2909_c01', 'fail'),
            ('w276_s2913_c01', 'fail'),
            ('w277_s2919_c01', 'fail'),
            ('w278_s2922_c01', 'fail'),
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

    def test_dolfinx_cross_check_covers_all_eight_genomes_within_two_percent(self):
        cross = json.loads((ROOT / 'evidence' / 'cad_battery' / 'dolfinx_cross_check.json').read_text(encoding='utf-8'))
        self.assertTrue(cross['all_within_2pct'])
        for name in GENOMES:
            row = cross['subjects'][name]
            self.assertEqual(row['status'], 'pass')
            self.assertTrue(row['within_2pct'])
            self.assertLessEqual(row['rel_err_nodal_max'], 0.02)
            self.assertLessEqual(row['rel_err_nodal_avg'], 0.02)
            self.assertGreater(row['dolfinx']['ksp_its'], 0)

    def test_side_a4_reports_cover_all_eight_genomes_without_certified_solver_edit(self):
        for name in GENOMES:
            a4_case = next(row for row in self.records[name]['cases'] if row['id'] == 'side.a4')
            side_a4 = json.loads((ROOT / a4_case['evidence_path']).read_text(encoding='utf-8'))
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

    def test_w274_ultrarunner_karambit_all_gates_and_weightings(self):
        from ops.ci.evaluate_cad_candidate import compute_weighted_cad_score
        ev274 = json.loads((ROOT / 'evidence' / 'rs_v2' / 'w274_calibrated' / 'w274_s2905_c01_cad_eval.json').read_text(encoding='utf-8'))
        ev275 = json.loads((ROOT / 'evidence' / 'rs_v2' / 'w275_ultrarunner' / 'w275_s2909_c01_cad_eval.json').read_text(encoding='utf-8'))
        ev276 = json.loads((ROOT / 'evidence' / 'rs_v2' / 'w276_ultrarunner' / 'w276_s2913_c01_cad_eval.json').read_text(encoding='utf-8'))
        ev277 = json.loads((ROOT / 'evidence' / 'rs_v2' / 'w277_ultrarunner' / 'w277_s2919_c01_cad_eval.json').read_text(encoding='utf-8'))
        ev278 = json.loads((ROOT / 'evidence' / 'rs_v2' / 'w278_ultrarunner' / 'w278_s2922_c01_cad_eval.json').read_text(encoding='utf-8'))
        for ev in (ev274, ev275, ev276, ev277, ev278):
            w = ev['weighted_cad_score']
            self.assertEqual(w['metric'], 'W_CAD_v2_ultrarunner_karambit')
            self.assertTrue(w['all_engineering_gates_pass'])
            self.assertTrue(ev['engineering_metrics']['promote_eligible'])
            self.assertTrue(ev['karambit_archetype']['karambit_valid'])
            self.assertTrue(ev['cad']['watertight_exact'])
            self.assertEqual(ev['global_fitness_G1']['status'], 'COMPLETE')
            self.assertGreater(w['W_CAD'], 1.4)
            self.assertAlmostEqual(sum(w['weights'].values()), 1.0, places=6)
            self.assertEqual(w['weights']['w_mass'], 0.70)

        # Verify strict progression: w278_s2922_c01 (78.58 g) < w277_s2919_c01 (79.509 g) < w276_s2913_c01 (79.995 g) < w275_s2909_c01 (81.774 g) < w274_s2905_c01 (84.98 g)
        self.assertLess(ev275['engineering_metrics']['mass_g'], ev274['engineering_metrics']['mass_g'])
        self.assertGreater(ev275['weighted_cad_score']['W_CAD'], ev274['weighted_cad_score']['W_CAD'])
        self.assertGreater(ev275['global_fitness_G1']['G'], ev274['global_fitness_G1']['G'])
        self.assertLess(ev276['engineering_metrics']['mass_g'], 80.0)
        self.assertLess(ev276['engineering_metrics']['mass_g'], ev275['engineering_metrics']['mass_g'])
        self.assertGreater(ev276['weighted_cad_score']['W_CAD'], ev275['weighted_cad_score']['W_CAD'])
        self.assertGreater(ev276['global_fitness_G1']['G'], ev275['global_fitness_G1']['G'])
        self.assertLess(ev277['engineering_metrics']['mass_g'], ev276['engineering_metrics']['mass_g'])
        self.assertLess(ev277['cad']['mass_3d_g'], 80.0)
        self.assertGreater(ev277['weighted_cad_score']['W_CAD'], ev276['weighted_cad_score']['W_CAD'])
        self.assertGreater(ev277['global_fitness_G1']['G'], ev276['global_fitness_G1']['G'])
        self.assertGreater(ev277['engineering_metrics']['seq_ratio_cert'], ev276['engineering_metrics']['seq_ratio_cert'])
        self.assertLess(ev278['engineering_metrics']['mass_g'], ev277['engineering_metrics']['mass_g'])
        self.assertLess(ev278['cad']['mass_3d_g'], 79.0)
        self.assertGreater(ev278['weighted_cad_score']['W_CAD'], ev277['weighted_cad_score']['W_CAD'])
        self.assertGreater(ev278['global_fitness_G1']['G'], ev277['global_fitness_G1']['G'])
        self.assertGreaterEqual(ev278['engineering_metrics']['strict_lat_rob_0p0625_n'], 273.0)
        self.assertGreater(ev278['engineering_metrics']['seq_ratio_cert'], ev277['engineering_metrics']['seq_ratio_cert'])
        self.assertGreater(ev278['engineering_metrics']['twist_tipzone_sf_strict'], ev277['engineering_metrics']['twist_tipzone_sf_strict'])

        # Verify that 1 g of mass savings beats excess strength above the +8% survival knee
        w = ev276['weighted_cad_score']
        gates_summary = {'gates': dict(w['gates']), 'shortfalls': dict(w['shortfalls'])}
        base_metrics = {
            'mass_g': 80.0,
            'strict_lat_rob_0p0625_n': 260.0 * 1.08,
            'solid_tip_sf_nodal_max': 1.20,
            'twist_tipzone_sf_strict': 1.08,
            'seq_ratio': 1.25,
            'fat_sf': 0.80,
            'aes_score': 0.45,
            'buckling_eigenvalue': 10.0,
            'hook_drop_mm': 41.9,
            'inside_concave': 1.0,
            'spine_convex': 0.93,
        }
        lighter_at_knee = compute_weighted_cad_score(gates_summary, base_metrics)
        heavier_overbuilt = compute_weighted_cad_score(
            gates_summary,
            {
                **base_metrics,
                'mass_g': 81.0,
                'strict_lat_rob_0p0625_n': 260.0 * 1.50,
                'solid_tip_sf_nodal_max': 1.80,
                'twist_tipzone_sf_strict': 1.50,
            },
        )
        self.assertGreater(lighter_at_knee['W_CAD'], heavier_overbuilt['W_CAD'])

    def test_engineering_gates_paper_and_manifest_figures_are_present_and_valid(self):
        from ops.ci import verify_figures
        paper = ROOT / 'docs' / 'ENGINEERING_GATES_AND_EVOLUTION.md'
        self.assertTrue(paper.is_file())
        text = paper.read_text(encoding='utf-8')
        for cid in CASE_IDS:
            self.assertIn(f'`{cid}`', text)
        for fig_rel in (
            'docs/figures/engineering_gates/fig1_evolutionary_trajectories.png',
            'docs/figures/engineering_gates/fig2_cad_battery_matrix_and_gci.png',
            'docs/figures/engineering_gates/fig3_cad_and_fem_gallery.png',
        ):
            self.assertTrue((ROOT / fig_rel).is_file())
            manifest = ROOT / f'{fig_rel}.manifest.json'
            self.assertTrue(manifest.is_file())
            self.assertEqual(verify_figures.check_manifest(str(manifest), str(ROOT)), [])

    def test_jarambit_cad_battery_env_does_not_recurse(self):
        from pathlib import Path
        import shutil
        import tempfile
        from unittest import mock
        from ops.ci.cad_battery import _child_env, evaluate_genome_pipeline

        old = os.environ.get('JARAMBIT_CAD_BATTERY')
        try:
            os.environ['JARAMBIT_CAD_BATTERY'] = '1'
            env = _child_env(D1_PLATES='1')
            self.assertNotIn('JARAMBIT_CAD_BATTERY', env)
            self.assertEqual(env.get('JARAMBIT_CAD_BATTERY_DEPTH'), '1')
            self.assertEqual(env.get('D1_PLATES'), '1')

            with tempfile.TemporaryDirectory() as tmp:
                out_dir = Path(tmp) / 'battery_out'
                work_dir = out_dir / '_battery_work'
                work_dir.mkdir(parents=True, exist_ok=True)
                label = 'norecurse_probe'
                src_dir = ROOT / 'evidence' / 'rs_v2' / 'w275_ultrarunner'
                shutil.copyfile(src_dir / 'w275_s2909_c01_rs.json', work_dir / f'{label}_rs.json')
                shutil.copyfile(src_dir / 'w275_s2909_c01_a1a3.json', work_dir / f'{label}_a1a3.json')
                shutil.copyfile(src_dir / 'w275_s2909_c01_plate_gci.json', work_dir / f'{label}_plate_gci.json')

                d1_calls = []
                real_run = subprocess.run

                def spy_run(cmd, *args, **kwargs):
                    if len(cmd) >= 2 and cmd[1] == 'crescent-d1':
                        d1_calls.append(dict(kwargs.get('env') or {}))
                        out_idx = cmd.index('--out') + 1
                        shutil.copyfile(
                            src_dir / 'w275_s2909_c01_D1.json',
                            Path(cmd[out_idx]) / f'{label}_D1.json',
                        )
                        return subprocess.CompletedProcess(cmd, 0, '', '')
                    return real_run(cmd, *args, **kwargs)

                jarambit_bin = ROOT / 'target/release/jarambit'
                orig_is_file = Path.is_file

                def fake_is_file(p):
                    if p == jarambit_bin:
                        return True
                    return orig_is_file(p)

                with mock.patch.object(Path, 'is_file', fake_is_file), \
                     mock.patch('subprocess.run', side_effect=spy_run):
                    rec = evaluate_genome_pipeline(
                        f'{label}={src_dir / "w275_s2909_c01_genome.csv"}',
                        '0' * 40,
                        {'analytic': 'pass', 'gci': 'pass', 'claims': 'pass', 'dolfinx': 'pass'},
                        out_dir,
                    )
                self.assertEqual(len(d1_calls), 1)
                self.assertNotIn('JARAMBIT_CAD_BATTERY', d1_calls[0])
                self.assertEqual(d1_calls[0].get('JARAMBIT_CAD_BATTERY_DEPTH'), '1')
                self.assertEqual(rec['subject'], label)
                self.assertTrue((out_dir / f'{label}.json').is_file())
        finally:
            if old is None:
                os.environ.pop('JARAMBIT_CAD_BATTERY', None)
            else:
                os.environ['JARAMBIT_CAD_BATTERY'] = old


if __name__ == '__main__':
    unittest.main()


