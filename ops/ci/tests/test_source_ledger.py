"""Neutral byte-provenance fixtures; no result metrics, solvers or design data."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ops.ci import source_ledger
from ops.ci.publication_inventory import Snapshot


class SourceLedger(unittest.TestCase):
    def setUp(self):
        folder = Path(__file__).resolve().parents[3] / 'target/paper/test-source-ledger'
        folder.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'neutral@example.invalid')
        self.git('config', 'user.name', 'Neutral Fixture')
        self.original = b'neutral source\r\n\x00not JSON\xff'
        (self.root / 'a.bin').write_bytes(self.original)
        (self.root / 'b.txt').write_bytes(b'another neutral source\n')
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root,
                                       stderr=subprocess.PIPE, text=True).strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Neutral source fixture')

    def collect(self, paths=('a.bin', 'b.txt'), revision='HEAD'):
        return source_ledger.collect_sources(self.root, paths, revision)

    def test_committed_byte_identities_are_deterministic(self):
        result = self.collect(('b.txt', 'a.bin'))
        self.assertEqual(result, self.collect())
        self.assertEqual(result['source_commit'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(result['source_mode'], 'committed_git_blobs')
        self.assertEqual(result['sources'][0], {
            'path': 'a.bin', 'size_bytes': len(self.original),
            'sha256': hashlib.sha256(self.original).hexdigest()})

    def test_dirty_copies_cannot_replace_committed_bytes(self):
        expected = self.collect()
        (self.root / 'a.bin').write_bytes(b'uncommitted replacement')
        self.assertEqual(self.collect(), expected)

    def test_missing_committed_source_has_no_runtime_fallback(self):
        (self.root / 'runtime.txt').write_text('only local')
        with self.assertRaisesRegex(ValueError, 'Not committed.*runtime.txt'):
            self.collect(('runtime.txt',))

    def test_local_mode_is_explicitly_unchecked_and_has_no_commit(self):
        (self.root / 'runtime.txt').write_bytes(b'local bytes')
        result = self.collect(('runtime.txt',), revision=None)
        self.assertEqual(result['source_mode'], 'local_files_unchecked_against_git')
        self.assertIsNone(result['source_commit'])
        self.assertEqual(result['sources'][0]['sha256'], hashlib.sha256(b'local bytes').hexdigest())

    def test_ref_move_cannot_mix_committed_sources(self):
        first = self.git('rev-parse', 'HEAD')
        expected = self.collect(revision=first)
        (self.root / 'a.bin').write_bytes(b'new committed bytes')
        self.commit()
        second = self.git('rev-parse', 'HEAD')
        self.git('update-ref', 'refs/heads/source-input', first)
        read = Snapshot.read

        def move_then_read(snapshot, path):
            self.git('update-ref', 'refs/heads/source-input', second)
            return read(snapshot, path)

        with patch.object(Snapshot, 'read', new=move_then_read):
            result = self.collect(revision='refs/heads/source-input')
        self.assertEqual(result, expected)
        self.assertEqual(self.git('rev-parse', 'source-input'), second)

    def test_local_hash_and_length_bind_the_bytes_actually_read(self):
        read = Path.read_bytes

        def replace_after_read(path):
            raw = read(path)
            path.write_bytes(b'changed after the read')
            return raw

        with patch.object(Path, 'read_bytes', new=replace_after_read):
            result = self.collect(('a.bin',), revision=None)
        self.assertEqual(result['sources'][0]['size_bytes'], len(self.original))
        self.assertEqual(result['sources'][0]['sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertNotEqual((self.root / 'a.bin').read_bytes(), self.original)

    def test_invalid_or_duplicate_paths_are_rejected(self):
        for paths in [(), ('a.bin', './a.bin'), ('../outside',), ('/absolute',),
                      ('HEAD:a.bin',), ('a\\b',)]:
            for revision in ('HEAD', None):
                with self.subTest(paths=paths, revision=revision), self.assertRaises(ValueError):
                    self.collect(paths, revision)

    def test_local_symlink_escape_and_directory_are_rejected(self):
        (self.root / 'escape').symlink_to(Path(__file__).resolve())
        for path in ('escape', '.'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.collect((path,), revision=None)

    def test_cli_emits_complete_json_or_no_report_on_failure(self):
        output = io.StringIO()
        with patch.object(source_ledger, 'ROOT', self.root), contextlib.redirect_stdout(output):
            source_ledger.main(['--ref', 'HEAD', 'a.bin'])
        self.assertEqual(json.loads(output.getvalue()), self.collect(('a.bin',)))
        output, error = io.StringIO(), io.StringIO()
        with patch.object(source_ledger, 'ROOT', self.root), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as exited:
            source_ledger.main(['--ref', 'HEAD', 'missing.txt'])
        self.assertEqual(exited.exception.code, 1)
        self.assertEqual(output.getvalue(), '')
        self.assertIn('Not committed', error.getvalue())


if __name__ == '__main__':
    unittest.main()
