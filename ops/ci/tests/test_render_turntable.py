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

if __name__ == '__main__':
    unittest.main()
