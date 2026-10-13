import json, pathlib, subprocess, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[3]

class T1T2(unittest.TestCase):
    def test_json_current(self):
        r = subprocess.run([sys.executable, str(ROOT / "ops/calibration/t1_t2.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_forty_designs_and_reported_sigma(self):
        d = json.loads((ROOT / "docs/calibration/t1_t2.json").read_text())
        self.assertEqual(d["n_designs"], 40)
        for c in ["lat_rob", "ring_rob", "pry20"]:
            self.assertLessEqual(d["cases"][c]["sigma"], 0.07, c)
        # twist misses the bar; documented in docs/calibration/t1_t2.md and gated only at T2
        self.assertFalse(d["cases"]["twist_joint"]["pass_sigma"])
        self.assertIn("gated only on T2", (ROOT / "docs/calibration/t1_t2.md").read_text())

    def test_rs_v2_published_mass_soft(self):
        t = (ROOT / "requirements/RS-karambit-v2.toml").read_text()
        self.assertIn('id = "RS-karambit-v2"', t)
        self.assertIn("mass SOFT", t)
        for k in ["twist_nmm = 16200.0", "tip_inplane_n = 1000.0", "spine_n = 3427.0", "ringback_n", "ring_bearing_w_min_mm = 10.0", "ring_edge_r_min_mm = 1.5"]:
            self.assertIn(k, t)

if __name__ == "__main__":
    unittest.main()
