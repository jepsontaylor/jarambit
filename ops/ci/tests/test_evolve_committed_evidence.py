"""Check retained real observations; these tests do not claim to rerun either solver."""
import hashlib
import json
from pathlib import Path
import unittest

from ops.ci.evaluate_cad_candidate import validate_solid_artifacts


class CommittedEvolutionEvidence(unittest.TestCase):
    def test_automatic_run_retains_both_real_solver_observations_on_one_mesh(self):
        root = Path(__file__).resolve().parents[3]
        manifest = json.loads((root/'evidence/evolve_certifiable/manifest.json').read_text())
        for name, sha in manifest['files'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(), sha, name)
        run = manifest['automatic']
        assets = run['artifacts']
        read = lambda key: json.loads((root/assets[key]).read_text())
        solid = read('solid_tip')
        folder = (root/assets['solid_tip']).parent
        self.assertTrue(validate_solid_artifacts(solid, folder, run['label']))
        mesh_sha = hashlib.sha256((root/assets['mesh']).read_bytes()).hexdigest()
        side = read('dolfinx_sidecar')
        self.assertEqual(set(side['inputs'].values()), {mesh_sha})
        self.assertEqual(side['legacy_stdout'], read('dolfinx_raw'))
        self.assertGreater(side['solver']['ksp_its'], 0)
        self.assertGreater(side['solver']['ksp_reason'], 0)
        self.assertTrue(read('skfem_raw')['solver']['converged'])
        for primary, other in [('SF_skfem_nodal_max', 'SF_nodal_max'),
                               ('SF_skfem_nodal_avg', 'SF_nodal_avg')]:
            a, b = solid['stored_solid'][primary], solid['stored_solid'][other]
            self.assertLessEqual(abs(a-b)/b, .02)
        leaderboard = read('leaderboard')
        self.assertEqual(leaderboard['qualified_count'], 0)
        self.assertIsNone(leaderboard['champion'])
        self.assertFalse(read('rs')['all_hard'])
