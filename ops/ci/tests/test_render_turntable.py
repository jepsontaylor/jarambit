import json, os, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class Turntable(unittest.TestCase):
    def test_verify_media_passes(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'ops/ci/verify_media.py')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_small_render_and_manifest(self):
        try:
            import PIL, numpy  # noqa: F401
        except ImportError:
            self.skipTest('Pillow/numpy not installed')
        import shutil
        if not shutil.which('ffmpeg'):
            self.skipTest('ffmpeg not installed')
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 't.gif')
            subprocess.run([sys.executable, os.path.join(ROOT, 'ops/render/turntable.py'), '--stl', os.path.join(ROOT, 'evidence/wave27/g3_tip+00_t60_tt3.stl'),
                            '--color', 'x', '--out', out, '--frames', '3', '--width', '320', '--height', '180', '--gif-width', '320'], check=True, capture_output=True)
            m = json.load(open(out + '.manifest.json'))
            self.assertEqual(m['frames'], 3); self.assertEqual(m['size'], [320, 180]); self.assertTrue(m['lossy'])

    def test_fem_without_d1_is_rejected(self):
        for extra in ([], ['--color', 'fem']):
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'ops/render/turntable.py'), '--stl', os.path.join(ROOT, 'evidence/wave27/g3_tip+00_t60_tt3.stl'),
                                '--out', os.path.join(tempfile.gettempdir(), 'never.gif'), '--frames', '2'] + extra, capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0); self.assertIn('requires --d1', r.stderr)

    def test_whole_part_in_frame_every_angle(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest('numpy not installed')
        sys.path.insert(0, os.path.join(ROOT, 'ops/render'))
        import turntable as tt
        man = json.load(open(os.path.join(ROOT, 'docs/media/g3_tip+00_t60_tt3_turntable.gif.manifest.json')))
        W, H = man['size']; n = man['frames']
        v = tt.load_stl(os.path.join(ROOT, 'evidence/wave27/g3_tip+00_t60_tt3.stl'))
        angles = [360.0 * k / n for k in range(n)]
        cam = tt.fit(v, angles, W, H)
        for ang in angles:
            x0, y0, x1, y1 = tt.screen_bounds(v, ang, cam)
            self.assertGreaterEqual(x0, tt.BOX[0] * W - 1e-6, ang); self.assertLessEqual(x1, tt.BOX[2] * W + 1e-6, ang)
            self.assertGreaterEqual(y0, tt.BOX[1] * H - 1e-6, ang); self.assertLessEqual(y1, tt.BOX[3] * H + 1e-6, ang)

if __name__ == '__main__':
    unittest.main()
