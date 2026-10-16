"""Integrity and numerical admission checks for the committed w282 records."""
import csv
import hashlib
import json
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
WAVE = ROOT / 'evidence/rs_v2/w282_ultrarunner'


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Wave282Evidence(unittest.TestCase):
    def test_manifest_binds_every_artifact(self):
        manifest = load(WAVE / 'manifest.json')
        self.assertTrue(manifest['subjects'])
        for name, expected in manifest['files'].items():
            path = (WAVE / name).resolve()
            self.assertTrue(path.is_relative_to(WAVE.resolve()), name)
            self.assertEqual(digest(path), expected, name)

    def test_records_beat_the_committed_reference_without_dropping_gates(self):
        manifest = load(WAVE / 'manifest.json')
        reference = load(ROOT / manifest['reference_eval'])
        baseline = reference['engineering_metrics']
        for subject in manifest['subjects']:
            with self.subTest(subject=subject):
                record = load(WAVE / f'{subject}_cad_eval.json')
                metrics = record['engineering_metrics']
                gates = record['weighted_cad_score']['gates']
                self.assertEqual(set(gates), set(reference['weighted_cad_score']['gates']))
                self.assertTrue(all(gates.values()))
                self.assertLess(metrics['mass_g'], baseline['mass_g'])
                self.assertLess(metrics['mass_3d_g'], baseline['mass_3d_g'])
                self.assertGreaterEqual(metrics['lat_rob_cert_n'], 260)
                self.assertGreaterEqual(metrics['strict_lat_rob_0p0625_n'], 260)
                self.assertGreaterEqual(metrics['ring_rob_cert_n'], 1500)
                self.assertGreaterEqual(metrics['seq_ratio_cert'], 1.20)
                for field in ('twist_tip_sf', 'twist_body_sf', 'twist_tipzone_sf_strict', 'solid_tip_sf_nodal_max'):
                    self.assertGreaterEqual(metrics[field], 1.0, field)
                self.assertTrue(record['cad']['watertight_exact'])
                self.assertEqual(record['cad']['manifold_solids'], 1)
                self.assertLessEqual(record['cad']['rel_mass_diff'], 0.01)
                self.assertEqual(digest(WAVE / f'{subject}.step'), record['cad']['step_sha256'])
                self.assertEqual(digest(WAVE / f'{subject}.stl'), record['cad']['stl_sha256'])

    def test_independent_solid_runs_are_bound_to_the_actual_design(self):
        for subject in load(WAVE / 'manifest.json')['subjects']:
            with self.subTest(subject=subject):
                solid = load(WAVE / f'{subject}_solid_tip.json')
                problem = load(WAVE / f'{subject}_solid_problem.json')
                genome = WAVE / f'{subject}_genome.csv'
                d1 = WAVE / f'{subject}_D1.json'
                self.assertEqual(solid['genome_sha256'], digest(genome))
                self.assertEqual(solid['d1_sha256'], digest(d1))
                with genome.open() as stream:
                    header, row = list(csv.reader(stream))
                document = load(d1)
                self.assertEqual(next(csv.reader([document['genome_header']])), header)
                self.assertEqual(next(csv.reader([document['genome']])), row)
                self.assertTrue(solid['solve_rerun'])
                self.assertFalse(solid['copied_from_another_genome'])
                self.assertTrue(solid['dolfinx_cross_check']['within_2pct'])
                self.assertGreater(solid['stored_solid']['ksp_its'], 0)
                for field in ('rel_err_nodal_max', 'rel_err_nodal_avg'):
                    self.assertLessEqual(solid['dolfinx_cross_check'][field], 0.02)
                self.assertEqual(digest(ROOT / problem['mesh_npz']), problem['mesh_sha256'])
                self.assertEqual(digest(WAVE / f'{subject}_skfem_raw.json'), problem['raw_skfem_sha256'])
                self.assertLessEqual(problem['scikit_fem_relative_residual'], 1e-8)
                with np.load(ROOT / problem['mesh_npz'], allow_pickle=False) as mesh:
                    tets = mesh['tets']
                    edges = np.concatenate([tets[:, pair] for pair in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))])
                    edges = np.unique(np.sort(edges, axis=1), axis=0)
                    self.assertEqual(len(tets), solid['stored_solid']['n_tet'])
                    self.assertEqual(3 * (len(mesh['pts']) + len(edges)), solid['stored_solid']['n_dof'])


if __name__ == '__main__':
    unittest.main()
