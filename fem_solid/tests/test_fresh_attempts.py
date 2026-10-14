"""T01 fresh/cache/atomic software controls. Every executor is an explicit test double."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest import mock

from assurance.testing.contracts import ContractError, raw_hash, scientific_hash
from fem_solid import convergence, run_tip
from fem_solid.run_tip import Identity, bound_identity, fresh_attempt, load_completed, parameters, reuse
from fem_solid.tests.test_gci import levels


def identity():
    return Identity(*[raw_hash(str(i).encode()) if i != 3 else 'sha256:'+raw_hash(b'image') for i in range(7)])


def complete(argv, output, completion, request):
    raw = (json.dumps({'schema': 2, 'attempt_id': request['attempt_id'], 'identity': request['identity'],
                       'data': {'marker': 'synthetic_mock', 'vm_nodal_max_MPa': 100.5,
                                'vm_nodal_avg_MPa': 80, 'sallow_MPa': 157.5}})+'\n').encode()
    output.write_bytes(raw)
    completion.write_text(json.dumps({'schema': 1, 'attempt_id': request['attempt_id'],
        'identity_sha256': scientific_hash(request['identity']), 'output_sha256': raw_hash(raw), 'exit_code': 0}))
    return 0


def inputs(root, nl='4', nsub='1'):
    d1 = root/'fixture_D1.json'; gl = root/'fixture_grind_law.json'
    d1.write_text('{}'); gl.write_text('{}')
    ref = bound_identity(d1, parameters('30', nl, nsub, '2.0'), 'sha256:'+raw_hash(b'image'),
                         raw_hash(b'mesh'), raw_hash(b'material'), scientific_hash(asdict(levels()[0].observable)))
    return d1, ref


class FreshAttempts(unittest.TestCase):
    def positive(self, root):
        calls = []
        def execute(*args): calls.append(args[0]); return complete(*args)
        result = fresh_attempt(root, identity(), ['mock-solver', 'fixture'], execute)
        self.assertEqual(len(calls), 1); self.assertTrue(result['execution']['fresh'])
        self.assertEqual(result['numerical_finding'], 'not_run')
        self.assertEqual(result['physical_validation'], 'not_performed')
        self.assertEqual(load_completed(result['directory'], identity())['data']['marker'], 'synthetic_mock')
        return result

    def test_T01_15_stale_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.positive(root/'positive')
            d1, ref = inputs(root); old = root/'L14.json'; old.write_text('old valid-looking result')
            result = convergence.level(d1, root, 1, 4, identity=ref, execute=complete)
            self.assertTrue(result['execution']['invoked']); self.assertEqual(old.read_text(), 'old valid-looking result')
            for execute in (lambda *args: 0, lambda *args: 7):
                with self.assertRaises((OSError, ContractError)):
                    convergence.level(d1, root, 1, 4, identity=ref, execute=execute)
            out = root/'OUT.json'; out.write_text('old result')
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(run_tip.main([str(d1), str(out)], identity=ref, execute=lambda *a: 0), 1)
            self.assertEqual(out.read_text(), 'old result')
            capture = io.StringIO()
            with redirect_stdout(capture), redirect_stderr(io.StringIO()):
                self.assertEqual(run_tip.main([str(d1), str(out)], identity=ref, execute=complete), 0)
            self.assertEqual(json.loads(capture.getvalue())['numerical_finding'], 'not_run')
            self.assertEqual(out.read_text(), 'old result')  # successful new attempt never overwrites it
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(run_tip.main([str(d1), str(out)]), 3)  # no implicit real provider
            def nonzero(*args): complete(*args); return 1
            with self.assertRaisesRegex(ContractError, 'nonzero'):
                fresh_attempt(root/'nonzero', identity(), ['mock'], nonzero)

    def test_T01_16_cache_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.positive(Path(directory)); target = Path(result['directory'])
            hit = reuse(target, identity())
            self.assertEqual(hit['mode'], 'reuse'); self.assertFalse(hit['execution']['fresh']); self.assertFalse(hit['execution']['invoked'])
            for key in asdict(identity()):
                value = 'sha256:'+raw_hash(b'changed') if key == 'image_digest' else raw_hash(b'changed')
                with self.assertRaisesRegex(ContractError, 'cache_identity'):
                    reuse(target, replace(identity(), **{key: value}))
            with self.assertRaisesRegex(ContractError, 'image_digest'):
                reuse(target, replace(identity(), image_digest='image:latest'))
            raw = json.loads((target/'result.json').read_text()); raw['data']['marker'] = 'tampered'
            (target/'result.json').write_text(json.dumps(raw))
            with self.assertRaisesRegex(ContractError, 'hash_mismatch'): reuse(target, identity())

    def test_T01_17_partial_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.positive(root/'positive')
            def missing(*args):
                complete(*args); args[2].unlink(); return 0
            with self.assertRaises((OSError, ContractError)): fresh_attempt(root/'missing', identity(), ['mock'], missing)
            for artifact in ('manifest.json', 'COMPLETED.json'):
                original = run_tip.atomic_json
                def fault(path, value):
                    if Path(path).name == artifact: raise OSError('injected disk-full/atomic-publication interruption')
                    return original(path, value)
                base = root/artifact
                with mock.patch('fem_solid.run_tip.atomic_json', side_effect=fault):
                    with self.assertRaises(OSError): fresh_attempt(base, identity(), ['mock'], complete)
                attempt = next(base.glob('attempt-*'))
                self.assertFalse((attempt/'COMPLETED.json').exists())
                self.assertTrue((attempt/'failure.json').is_file())
                with self.assertRaises(ContractError): reuse(attempt, identity())
            # Schedule two same-key requests at an identical reserved attempt id. Real mkdir/link/fsync remain active.
            ready, loser_done = threading.Event(), threading.Event()
            def wait_execute(*args):
                ready.set(); self.assertTrue(loser_done.wait(5)); return complete(*args)
            collision = root/'collision'
            with mock.patch('fem_solid.run_tip.uuid.uuid4', return_value=types.SimpleNamespace(hex='a'*32)):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(fresh_attempt, collision, identity(), ['mock'], wait_execute)
                    self.assertTrue(ready.wait(5))
                    second = pool.submit(fresh_attempt, collision, identity(), ['mock'], complete)
                    try:
                        with self.assertRaises(FileExistsError): second.result(timeout=5)
                    finally: loser_done.set()
                    winner = first.result(timeout=5)
            self.assertTrue(Path(winner['directory'], 'COMPLETED.json').is_file())
            self.assertEqual(len(list(collision.glob('attempt-*'))), 1)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(fresh_attempt, root/'independent', identity(), ['mock'], complete) for _ in range(2)]
                outcomes = [future.result(timeout=10) for future in futures]
            self.assertNotEqual(outcomes[0]['directory'], outcomes[1]['directory'])
            for value in outcomes: load_completed(value['directory'], identity())

    def test_completion_schema_identity_and_source_mutations_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.positive(root/'positive')
            for name in ('attempt', 'identity', 'completion', 'unknown', 'boolean'):
                def changed(argv, output, completion, request):
                    complete(argv, output, completion, request)
                    if name == 'completion':
                        value = json.loads(completion.read_text()); value['output_sha256'] = '0'*64; completion.write_text(json.dumps(value))
                    else:
                        value = json.loads(output.read_text())
                        if name == 'attempt': value['attempt_id'] = 'old'
                        elif name == 'identity': value['identity']['material'] = '0'*64
                        elif name == 'unknown': value['unknown'] = True
                        else: value['schema'] = True
                        output.write_text(json.dumps(value))
                    return 0
                with self.assertRaises(ContractError): fresh_attempt(root/name, identity(), ['mock'], changed)
            d1, ref = inputs(root)
            def change_input(*args):
                complete(*args); d1.write_text('{"changed":true}'); return 0
            with self.assertRaisesRegex(ContractError, 'inputs_changed'):
                convergence.level(d1, root, 1, 4, identity=ref, execute=change_input)

    def test_convergence_requires_separate_observable_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); d1, _ = inputs(root); sequence = levels()
            refs = [bound_identity(d1, parameters('30', str(nl), str(ns), '2.0'), 'sha256:'+raw_hash(b'image'),
                    meta.mesh.sha256, raw_hash(b'material'), scientific_hash(asdict(meta.observable)))
                    for (ns, nl), meta in zip(convergence.LEVELS, reversed(sequence))]
            values = iter((108.0, 102.0, 100.5))
            def execute(argv, output, completion, request):
                complete(argv, output, completion, request); value = json.loads(output.read_text())
                value['data']['vm_nodal_max_MPa'] = next(values)
                output.write_text(json.dumps(value)); mark = json.loads(completion.read_text())
                mark['output_sha256'] = raw_hash(output.read_bytes()); completion.write_text(json.dumps(mark)); return 0
            result = convergence.main(d1, root, identities=refs, sequence=sequence, execute=execute)
            self.assertTrue(result['findings']['vm_nodal_max_MPa']['admitted'])
            self.assertEqual(result['findings']['vm_nodal_avg_MPa']['status'], 'unsupported_observable_binding')
            self.assertEqual(result['numerical_verification'], 'not_run')
            bad = list(refs); bad[0] = replace(bad[0], observable=raw_hash(b'wrong-observable'))
            with self.assertRaisesRegex(ContractError, 'observable_identity'):
                convergence.main(d1, root, identities=bad, sequence=sequence, execute=complete)

    def test_directory_fsync_failure_never_commits_and_keeps_partial_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.positive(root/'positive')
            linked, failed = False, False
            real_link, real_fsync = run_tip.os.link, run_tip.os.fsync
            def linking(source, target):
                nonlocal linked
                result = real_link(source, target)
                if Path(target).name == 'COMPLETED.json': linked = True
                return result
            def syncing(fd):
                nonlocal failed
                if linked and not failed:
                    failed = True; raise OSError('injected directory durability failure')
                return real_fsync(fd)
            with mock.patch('fem_solid.run_tip.os.link', side_effect=linking), mock.patch('fem_solid.run_tip.os.fsync', side_effect=syncing):
                with self.assertRaises(OSError):
                    fresh_attempt(root/'fault', identity(), ['mock'], complete)
            attempt = next((root/'fault').glob('attempt-*'))
            self.assertFalse((attempt/'COMPLETED.json').exists())
            self.assertTrue(list(attempt.glob('COMPLETED.json.pending.*')))
            self.assertTrue((attempt/'result.json').is_file())
            with self.assertRaises(ContractError): reuse(attempt, identity())

    def test_stale_guard_mutant_is_killed(self):
        source = Path(run_tip.__file__).read_text()
        old = "        require(type(code) is int and code == 0, 'nonzero_or_invalid_execution_exit')"
        self.assertEqual(source.count(old), 1)
        injected = old+"\n        if code == 0: return {'execution': {'fresh': True}, 'numerical_finding': 'not_run'}"
        module = types.ModuleType('s02_stale_mutant'); module.__file__ = run_tip.__file__
        import sys
        sys.modules[module.__name__] = module
        try:
            exec(source.replace(old, injected), vars(module))
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(OSError): fresh_attempt(root/'original', identity(), ['mock'], lambda *a: 0)
                wrong = module.Identity(**asdict(identity()))
                with self.assertRaises(AssertionError):
                    result = module.fresh_attempt(root/'mutant', wrong, ['mock'], lambda *a: 0)
                    self.assertFalse(result['execution']['fresh'])
        finally: del sys.modules[module.__name__]


if __name__ == '__main__':
    unittest.main()
