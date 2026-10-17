"""Neutral document controls: packaging provenance, no engineering assessment."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ops.render.paper import build_pdf

ROOT = Path(__file__).resolve().parents[3]
NAME = 'ENGINEERING_GATES_AND_EVOLUTION'


class PdfProvenance(unittest.TestCase):
    def setUp(self):
        folder = ROOT/'target/paper/test-pdf-provenance'
        folder.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.head = 'a'*40
        docs = self.root/'docs';docs.mkdir()
        self.source = docs/(NAME+'.md')
        self.source.write_text('# Neutral report\n\nA software packaging control.\n')
        (docs/'VERSION').write_text('1.0.0\n')
        self.here = self.root/'ops/render/paper';self.here.mkdir(parents=True)
        for name in ('build_pdf.py', 'publication.lua', 'header.tex'):
            (self.here/name).write_text('neutral software fixture\n')

    def run_build(self, mutation=None):
        def capture(command, **kwargs):
            if command[:3] == ['git', 'rev-parse', 'HEAD']:return self.head+'\n'
            if command[:2] == ['git', 'show']:return '1792195200\n'
            return 'neutral tool version\n'

        def render(command, **kwargs):
            # Deliberately no LaTeX/Blender/solver execution or physical data.
            Path(command[command.index('-o')+1]).write_bytes(b'neutral PDF packaging control')
            if mutation:mutation()
            return subprocess.CompletedProcess(command, 0)

        with patch.object(build_pdf, 'ROOT', self.root), \
             patch.object(build_pdf, 'HERE', self.here), \
             patch.object(build_pdf, '__file__', str(self.here/'build_pdf.py')), \
             patch.dict('sys.modules', {'PIL':None, 'matplotlib':None}), \
             patch.object(build_pdf.subprocess, 'check_output', side_effect=capture), \
             patch.object(build_pdf.subprocess, 'run', side_effect=render):
            build_pdf.build(NAME)

    def test_unchanged_document_manifest_binds_consumed_bytes(self):
        image = self.root/'docs/neutral.png';image.write_bytes(b'neutral image software control')
        with self.source.open('a') as f:
            f.write('\n![Neutral placeholder](neutral.png)\n\n![Repeated placeholder](neutral.png)\n')
        original = self.source.read_bytes()
        self.run_build()
        manifest = json.loads((self.root/'target/paper'/(NAME+'.pdf.manifest.json')).read_text())
        expected = hashlib.sha256(original).hexdigest()
        self.assertEqual(manifest['source_sha256'], expected)
        self.assertEqual(manifest['inputs']['docs/'+NAME+'.md'], expected)
        self.assertEqual(manifest['inputs']['docs/neutral.png'],
                         hashlib.sha256(image.read_bytes()).hexdigest())
        snapshots = list((self.root/'target/paper/images').glob('neutral-*.png'))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_bytes(), image.read_bytes())

    def test_source_substitution_during_render_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_build(lambda:self.source.write_text('# Different neutral report\n'))
        self.assertFalse((self.root/'target/paper'/(NAME+'.pdf.manifest.json')).exists())

    def test_render_support_substitution_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_build(lambda:(self.here/'header.tex').write_text('changed neutral support\n'))
        self.assertFalse((self.root/'target/paper'/(NAME+'.pdf.manifest.json')).exists())

    def test_image_substitution_is_rejected(self):
        image = self.root/'docs/neutral.png';image.write_bytes(b'neutral image software control')
        with self.source.open('a') as f:f.write('\n![Neutral placeholder](neutral.png)\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_build(lambda:image.write_bytes(b'changed neutral image'))
        self.assertFalse((self.root/'target/paper'/(NAME+'.pdf.manifest.json')).exists())

    def test_version_substitution_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_build(lambda:(self.root/'docs/VERSION').write_text('2.0.0\n'))
        self.assertFalse((self.root/'target/paper'/(NAME+'.pdf.manifest.json')).exists())

    def test_checkout_change_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.run_build(lambda:setattr(self, 'head', 'b'*40))
        self.assertFalse((self.root/'target/paper'/(NAME+'.pdf.manifest.json')).exists())

    def test_image_change_between_repeated_references_is_rejected(self):
        image = self.root/'docs/neutral.png';image.write_bytes(b'neutral image software control')
        with self.source.open('a') as f:
            f.write('\n![First placeholder](neutral.png)\n\n![Repeated placeholder](neutral.png)\n')
        capture = build_pdf.capture
        reads = 0

        def capture_then_change(path, inputs):
            nonlocal reads
            raw = capture(path, inputs)
            if path == image:
                reads += 1
                if reads == 1:image.write_bytes(b'changed neutral image')
            return raw

        with patch.object(build_pdf, 'capture', side_effect=capture_then_change):
            with self.assertRaisesRegex(ValueError, 'changed'):
                self.run_build()
        self.assertFalse((self.root/'target/paper'/(NAME+'.pdf.manifest.json')).exists())


if __name__ == '__main__':unittest.main()
