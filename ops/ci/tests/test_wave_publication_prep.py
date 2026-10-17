"""Publication admission and provenance controls; no new physical observations."""
import copy
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ops.render.blender.rerender import prepare
from ops.render.paper import wave_history
from ops.render.paper.wave_history import build_insertion, collect, generate, read_board

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT/'evidence/evolve_certifiable/automatic/leaderboard.json'
LABEL = 'cert_pipeline_r01_p14_c02'
HISTORY = ROOT/'evidence/evolution_plateau/2026-10-17/xbabe2/out/w298/leaderboard.json'


def at(document, pointer):
    for part in pointer.split('/')[1:]:
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


class WavePublicationPrep(unittest.TestCase):
    def setUp(self):
        folder = ROOT/'target/paper/test-wave-publication';folder.mkdir(parents=True,exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def committed_board_fixture(self):
        # A tiny Git fixture, not a copy of the project. It retains the real
        # committed observations and needs no cached/fetched remote ref in CI.
        path = self.folder/'out/control/leaderboard.json'
        path.parent.mkdir(parents=True)
        path.write_bytes(HISTORY.read_bytes())
        for args in [('init', '-q'), ('add', 'out/control/leaderboard.json'),
                     ('-c','user.name=Publication control','-c','user.email=control@example.invalid',
                      '-c','core.hooksPath=/dev/null','commit','-q','-m','Committed observation fixture'),
                     ('update-ref','refs/remotes/origin/main','HEAD')]:
            subprocess.run(['git',*args],cwd=self.folder,check=True,capture_output=True)
        return path

    def test_failed_assessment_cannot_enter_final_render_mode(self):
        with self.assertRaisesRegex(ValueError, 'NOT-A-WINNER'):
            prepare(LABEL, BOARD, ROOT)
        context = prepare(LABEL, BOARD, ROOT, preview=True)
        self.assertIn('NOT-A-WINNER', context['status'])
        self.assertFalse(context['all_16_gates'])
        self.assertFalse(context['rs_v2_all_hard'])
        for source, sha in context['input_sha256'].items():
            self.assertEqual(hashlib.sha256(Path(source).read_bytes()).hexdigest(), sha)

    def test_uncommitted_history_requires_preview_and_contradictions_fail(self):
        path = self.committed_board_fixture()
        data = json.loads(path.read_text())
        self.assertEqual(read_board(path, self.folder)[0], data)
        # The changed bytes are only on the local branch; origin/main retains
        # the original observation. Publication must not trust HEAD instead.
        path.write_text(json.dumps(data)+'\n')
        subprocess.run(['git','add','.'],cwd=self.folder,check=True)
        subprocess.run(['git','-c','user.name=Publication control','-c','user.email=control@example.invalid',
            '-c','core.hooksPath=/dev/null','commit','-q','-m','Local formatting change'],cwd=self.folder,check=True)
        with self.assertRaisesRegex(ValueError, 'origin/main'):
            read_board(path, self.folder)
        self.assertEqual(read_board(path, self.folder, preview=True)[0], data)
        contradictory = copy.deepcopy(data);contradictory['designs'][0]['qualified'] = True
        path.write_text(json.dumps(contradictory))
        with self.assertRaisesRegex(ValueError, 'qualification flags'):
            read_board(path, self.folder, preview=True)
        unverified = copy.deepcopy(data);unverified['unverified'] = ['control: missing independent solve']
        path.write_text(json.dumps(unverified))
        with self.assertRaisesRegex(ValueError, 'unverified'):
            read_board(path, self.folder, preview=True)

    def test_every_summary_matches_original_board_pointers_without_plotting_packages(self):
        path = self.committed_board_fixture()
        with patch.object(wave_history, 'ROOT', self.folder), patch.dict('sys.modules', {'matplotlib':None, 'cycler':None}):
            ledger = collect([path], self.folder, preview=False)
            self.assertFalse(ledger['preview'])
            for point in ledger['points']:
                original = json.loads((self.folder/point['source']).read_text())
                if 'pointers' in point:
                    values = [at(original, pointer) for pointer in point['pointers']]
                    expected = {'min':min, 'median':statistics.median, 'max':max}[point['reduction']](values)
                else:expected = at(original, point['pointer'])
                self.assertEqual(point['value'], expected)
            snippet = build_insertion(ledger['waves'])
            self.assertIn('champion=null', snippet)
            self.assertIn('not full-population statistics', snippet)
            with self.assertRaisesRegex(ValueError, 'outside the paper'):
                generate([path], self.folder, self.folder/'docs/preview-not-allowed', preview=True)

    def test_render_rejects_a_relabelled_certificate_identity(self):
        path = self.folder/'leaderboard.json'
        data = json.loads(BOARD.read_text())
        data['designs'][0]['certificate_identity'] = '0'*64
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            prepare(LABEL, path, ROOT, preview=True)


if __name__ == '__main__':unittest.main()
