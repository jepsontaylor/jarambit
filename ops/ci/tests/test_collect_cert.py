"""PR-0.30.0b: collect_cert ranks only rows passing every hard gate; mass is soft (only used for ordering)."""
import os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'ops', 'multihost'))
import collect_cert  # noqa: E402

CSV = "##out/w_h_cap80_s1/certification.csv\nid,mass_g,spg_cert,cert_pass_all,twist_floor_ok_body_and_tipsub\n1,78,3.5,true,true\n2,74,3.6,true,false\n3,84,3.7,true,true\n"


class Collect(unittest.TestCase):
    def test_rank(self):
        r = collect_cert.rank(collect_cert.parse(CSV, 'h'))
        self.assertEqual(r['n_hard'], 2)
        self.assertEqual([x['id'] for x in r['lightest']], ['1', '3'])
        self.assertEqual(r['best_spg'][0]['id'], '3')  # 84 g still eligible: mass is soft


if __name__ == '__main__':
    unittest.main()
