import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import toolchain


class MissingFfmpeg(unittest.TestCase):
    def test_missing_binary_reports_not_ok(self):
        r = toolchain.probe_ffmpeg("definitely-not-ffmpeg-xyz")
        self.assertFalse(r["ok"]); self.assertFalse(r["zscale"]); self.assertEqual(r["version_line"], "")


if __name__ == "__main__":
    unittest.main()
