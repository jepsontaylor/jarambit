"""PR-0.30.3: committed GCI evidence meets the roadmap bar (3-level GCI <= 3 % on governing sigma_vm, 5 designs)."""
import glob, json, os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GCIEvidence(unittest.TestCase):
    def test_five_designs_within_3pct(self):
        fs = sorted(glob.glob(os.path.join(ROOT, 'evidence', 'fem_solid', 'gci', '*_gci.json'))); self.assertGreaterEqual(len(fs), 5)
        for f in fs:
            d = json.loads(open(f).read()); self.assertEqual(len(d['levels']), 3, f)
            self.assertLessEqual(d['vm_nodal_max_MPa']['gci_fine'], 0.03, f)
            dofs = [x['n_dof'] for x in d['levels']]; self.assertEqual(dofs, sorted(dofs), f)


if __name__ == '__main__':
    unittest.main()
