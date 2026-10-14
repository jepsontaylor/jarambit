"""T00 positive/adverse control groups. No numerical/physical product qualification."""
import copy
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
import threading
import tempfile
import unittest
import unicodedata
from unittest import mock
from assurance.testing import contracts as c
from assurance.testing.catalog import bind_policy, build_catalog, source_bundle
from assurance.testing.receipt import publish_receipt

ROOT = Path(__file__).resolve().parents[3]
LIMITS = {'max_bytes': 1048576, 'max_depth': 64, 'max_nodes': 100000}


def case(identifier='fixture', required=True, enabled=True):
    return {'schema': 1, 'id': identifier, 'required': required, 'claim_enabled': enabled,
            'evidence_class': 'deterministic_contract', 'input_sha256': c.raw_hash(b'fixture input'),
            'oracle_sha256': c.raw_hash(b'independent fixture oracle'), 'controls': ['positive', 'adverse'],
            'disabled_reason': None if required or enabled else 'unclaimed fixture capability disabled'}


def receipt(case):
    return {'schema': 1, 'case_id': case['id'], 'input_sha256': case['input_sha256'],
            'oracle_sha256': case['oracle_sha256'], 'execution': 'passed',
            'finding': 'rejected_within_scope', 'argv': ['python3', '-m', 'unittest'],
            'exit_code': 0, 'timed_out': False, 'complete': True,
            'controls': {'positive': 'passed', 'adverse': 'passed'},
            'artifacts': {'result': c.raw_hash(b'actual fixture result')},
            'counts': {'expected': 2, 'passed': 2, 'failed': 0, 'error': 0, 'not_run': 0}, 'reason': None}


ARTIFACTS = {'result': b'actual fixture result'}


class Contracts(unittest.TestCase):
    def supported(self, catalog, receipts):
        return c.resolve_inventory(catalog, receipts, ARTIFACTS, bind_policy(catalog, LIMITS))

    def test_T00_01_inventory_delete(self):
        catalog = [case('A'), case('B')]; receipts = [receipt(x) for x in catalog]
        policy = bind_policy(catalog, LIMITS)
        self.assertEqual(self.supported(catalog, receipts)['support'], 'complete')
        self.assertEqual(self.supported(catalog, receipts[:1])['missing'], ['B'])
        with self.assertRaisesRegex(c.ContractError, 'frozen catalog'):
            c.resolve_inventory(catalog[:1], receipts[:1], ARTIFACTS, policy)
        with self.assertRaises(c.ContractError):
            self.supported([], [])

    def test_T00_02_inventory_duplicate(self):
        catalog = [case('A'), case('B')]; receipts = [receipt(x) for x in catalog]
        self.assertEqual(self.supported(catalog, receipts), self.supported(catalog[::-1], receipts[::-1]))
        for cases, recs in [(catalog + [catalog[0]], receipts), (catalog, receipts + [receipts[0]])]:
            with self.assertRaisesRegex(c.ContractError, 'duplicate'):
                self.supported(cases, recs)
        with self.assertRaisesRegex(c.ContractError, 'extra'):
            self.supported(catalog, receipts + [receipt(case('unsupported'))])

    def test_T00_03_optional_skip(self):
        catalog = [case('required'), case('disabled', False, False)]
        optional = receipt(catalog[1]); optional.update(execution='not_run', finding='not_applicable', exit_code=None,
                                                      reason='fixture tool unavailable', controls={})
        optional['counts'].update(passed=0, not_run=2)
        out = self.supported(catalog, [receipt(catalog[0]), optional])
        self.assertEqual(out['support'], 'complete'); self.assertEqual(out['optional_unavailable'], ['disabled'])
        catalog[1]['required'] = True
        self.assertEqual(self.supported(catalog, [receipt(catalog[0]), optional])['missing'], ['disabled'])

    def test_T00_04_strict_json(self):
        self.assertEqual(c.strict_loads('{"zero":0,"sample":"试样-é"}'.encode(), LIMITS), {'zero': 0, 'sample': '试样-é'})
        for raw in ['{"a":1,"a":2}', 'NaN', 'Infinity', '1e999', '1e-999', '[1,]', '{"a":1} 2', '18446744073709551616']:
            with self.subTest(raw=raw), self.assertRaises(c.ContractError):
                c.strict_loads(raw, LIMITS)
        for invalid in [True, False, None, '1.2', float('nan'), float('inf'), 10**400, 9007199254740993]:
            with self.subTest(value=str(invalid)), self.assertRaises(c.ContractError):
                c.finite(invalid)
        self.assertEqual(c.finite(0), 0.0)

    def test_T00_05_receipt_tamper(self):
        cs = case(); rec = receipt(cs)
        self.assertIs(c.validate_receipt(rec, cs, ARTIFACTS), rec)
        with self.assertRaisesRegex(c.ContractError, 'integrity'):
            c.validate_receipt(rec, cs, {'result': b'tampered'})
        rec['input_sha256'] = '0'*64
        with self.assertRaisesRegex(c.ContractError, 'identity'):
            c.validate_receipt(rec, cs, ARTIFACTS)

    def test_T00_06_receipt_crash(self):
        cs = case(); rec = receipt(cs)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'receipt.json'
            with mock.patch('assurance.testing.receipt.os.link', side_effect=OSError('owned publication fault')):
                with self.assertRaises(OSError):
                    publish_receipt(path, rec, cs, ARTIFACTS)
            self.assertFalse(path.exists()); self.assertEqual(self.supported([cs], [])['support'], 'incomplete')
            self.assertTrue(list(Path(directory).glob('*.pending.*')))
            durable = Path(directory)/'durability'/'receipt.json'
            with mock.patch('assurance.testing.receipt.os.fsync', side_effect=[None, OSError('owned directory sync fault')]):
                with self.assertRaises(OSError):
                    publish_receipt(durable, rec, cs, ARTIFACTS)
            self.assertFalse(durable.exists())
            self.assertTrue(list(durable.parent.glob('*.pending.*')))
            # Retry is a new attempt directory, never an overwrite of the interrupted evidence.
            path = Path(directory)/'retry'/'receipt.json'
            publish_receipt(path, rec, cs, ARTIFACTS)
            self.assertEqual(json.loads(path.read_text()), rec)
            with self.assertRaisesRegex(c.ContractError, 'immutable'):
                publish_receipt(path, rec, cs, ARTIFACTS)
        rec['complete'] = False
        with self.assertRaisesRegex(c.ContractError, 'incomplete'):
            c.validate_receipt(rec, cs, ARTIFACTS)
        rec['complete'] = True; rec['timed_out'] = True
        with self.assertRaisesRegex(c.ContractError, 'claimed pass'):
            c.validate_receipt(rec, cs, ARTIFACTS)

    def test_T00_07_schema_bounds(self):
        small = {'max_bytes': 8, 'max_depth': 2, 'max_nodes': 3}
        self.assertEqual(c.strict_loads('0'+' '*7, small), 0)
        self.assertEqual(c.strict_loads('[[0]]', small), [[0]])
        for raw in ['0'+' '*8, '[[[0]]]', '[0,0,0]']:
            with self.assertRaises(c.ContractError):
                c.strict_loads(raw, small)
        c.unique_ids(['试样-é'])
        with self.assertRaisesRegex(c.ContractError, 'normalization'):
            c.unique_ids(['é', 'e\u0301'])
        for key, value in [('schema', 99), ('schema', True), ('evidence_class', 'healthy')]:
            bad = case(); bad[key] = value
            with self.assertRaises(c.ContractError):
                c.validate_case(bad)

    def test_same_pid_publishers_preserve_one_durable_winner(self):
        cs = case(); rec = receipt(cs)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'receipt.json'
            barrier = threading.Barrier(2); linked = threading.Event(); loser_done = threading.Event()
            original_exists, original_open, original_link = Path.exists, Path.open, os.link
            checked, temporaries, outcomes = set(), {}, {}
            lock = threading.Lock()

            def exists(path):
                value = original_exists(path); name = threading.current_thread().name
                with lock:
                    first = path == target and name in ('winner', 'loser') and name not in checked
                    if first: checked.add(name)
                if first:
                    self.assertFalse(value); barrier.wait(5)
                return value

            def opening(path, *args, **kwargs):
                name = threading.current_thread().name
                if '.pending.' in path.name and args and args[0] == 'xb':
                    temporaries[name] = path
                    if name == 'loser': self.assertTrue(linked.wait(5))
                return original_open(path, *args, **kwargs)

            def linking(source, destination):
                result = original_link(source, destination)  # real atomic filesystem operation
                if threading.current_thread().name == 'winner':
                    linked.set(); self.assertTrue(loser_done.wait(5))
                return result

            def worker(name):
                try: outcomes[name] = publish_receipt(target, rec, cs, ARTIFACTS)
                except Exception as error: outcomes[name] = error
                finally:
                    if name == 'loser': loser_done.set()

            with mock.patch('assurance.testing.receipt.Path.exists', exists), \
                 mock.patch('assurance.testing.receipt.Path.open', opening), \
                 mock.patch('assurance.testing.receipt.os.link', linking):
                threads = [threading.Thread(target=worker, args=(name,), name=name) for name in ('winner', 'loser')]
                for thread in threads: thread.start()
                for thread in threads: thread.join(10)
                self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(outcomes['winner'], target)
            self.assertIsInstance(outcomes['loser'], FileExistsError)
            self.assertNotEqual(temporaries['winner'], temporaries['loser'])
            self.assertEqual(json.loads(target.read_text()), rec)
            self.assertFalse(temporaries['winner'].exists())
            self.assertTrue(temporaries['loser'].exists())  # independent incomplete attempt retained
            before = target.read_bytes()
            with self.assertRaises(c.ContractError): publish_receipt(target, rec, cs, ARTIFACTS)
            self.assertEqual(target.read_bytes(), before)
            # Same PID, independent destinations: both real publications succeed.
            outcomes.clear()
            def separate(name): outcomes[name] = publish_receipt(Path(directory)/(name+'.json'), rec, cs, ARTIFACTS)
            threads = [threading.Thread(target=separate, args=(name,)) for name in ('one', 'two')]
            for thread in threads: thread.start()
            for thread in threads: thread.join(10)
            self.assertEqual(set(outcomes), {'one', 'two'})
            for path in outcomes.values(): self.assertEqual(json.loads(path.read_text()), rec)

    def test_closed_review_receipt_and_event_schemas(self):
        import jsonschema
        schema = json.loads((ROOT/'assurance/schemas/evidence.v2.json').read_text())
        record = {'schema': 1, 'sequence': 1, 'observation': 'fixture', 'observation_sha256': 'a'*64,
                  'action': 'approved', 'reviewer': 'independent-fixture',
                  'scope': {'requirement_set': 'RS-fixture', 'group': 'numerical-fixture'}}
        validator = jsonschema.Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/review_receipt'})
        validator.validate(record)
        for bad in [{**record, 'unknown': True}, {**record, 'schema': 99}, {**record, 'sequence': 0},
                    {**record, 'sequence': True}, {**record, 'action': 'unreviewed'},
                    {**record, 'scope': {**record['scope'], 'unknown': True}}]:
            self.assertTrue(list(validator.iter_errors(bad)))
        event = {k: v for k, v in record.items() if k != 'schema'}
        event['receipt'] = {'id': 'review-fixture', 'revision': '1', 'sha256': 'b'*64}
        validator = jsonschema.Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/review_event'})
        validator.validate(event)
        for field in event:
            bad = dict(event); del bad[field]
            self.assertTrue(list(validator.iter_errors(bad)))

    def test_T00_08_controls_missing(self):
        cs = case(); rec = receipt(cs); c.validate_receipt(rec, cs, ARTIFACTS)
        for change in ['positive', 'adverse']:
            bad = copy.deepcopy(rec); del bad['controls'][change]
            with self.assertRaisesRegex(c.ContractError, 'controls'):
                c.validate_receipt(bad, cs, ARTIFACTS)
        bad = copy.deepcopy(rec); bad['counts']['passed'] = 1
        with self.assertRaisesRegex(c.ContractError, 'counts'):
            c.validate_receipt(bad, cs, ARTIFACTS)

    def test_T00_09_finding_vs_execution(self):
        cs = case(); rec = receipt(cs)
        for finding in ['supported_within_scope', 'rejected_within_scope', 'inconclusive']:
            rec['finding'] = finding
            self.assertEqual(self.supported([cs], [rec])['support'], 'complete')
            claim = {'schema': 1, 'kind': 'software_contract', 'case_ids': [cs['id']]}
            support = c.resolve_claim_support(claim, [cs], [rec], ARTIFACTS, bind_policy([cs], LIMITS))
            self.assertIsNone(support['product_qualification']); self.assertFalse(support['release_authorized'])
        rec['finding'] = 'healthy'
        with self.assertRaisesRegex(c.ContractError, 'status'):
            self.supported([cs], [rec])
        with self.assertRaisesRegex(c.ContractError, 'Rust'):
            c.resolve_claim_support({'schema': 1, 'kind': 'physical_validation', 'case_ids': [cs['id']]},
                                    [cs], [receipt(cs)], ARTIFACTS, bind_policy([cs], LIMITS))

    def test_T00_10_claim_mutant(self):
        # Execute disposable copies of actual guards; source/history remain untouched.
        source = Path(c.__file__).read_text()
        challenges = [
            ('catalog', "require(scientific_hash(catalog) == policy['catalog_sha256'], 'frozen catalog mismatch')", lambda n: n['resolve_inventory']([case('A')], [receipt(case('A'))], ARTIFACTS, bind_policy([case('A'), case('B')], LIMITS))),
            ('finite', "require(math.isfinite(value), 'nonfinite number')", lambda n: n['finite'](float('nan'))),
            ('identity', "require(name in artifacts and raw_hash(artifacts[name]) == expected, 'artifact integrity mismatch')", lambda n: n['validate_receipt'](receipt(case()), case(), {'result': b'tampered'})),
            ('unknown', "require(receipt['execution'] in EXECUTIONS and receipt['finding'] in FINDINGS, 'unknown status')", lambda n: n['validate_receipt']({**receipt(case()), 'finding': 'healthy'}, case(), ARTIFACTS)),
        ]
        for name, guard, probe in challenges:
            self.assertEqual(source.count(guard), 1)
            # Original oracle rejects the challenge; dropping its guard admits it and must be detected.
            with self.assertRaises(c.ContractError):
                probe(vars(c))
            namespace = {'__name__': 'owned_disposable_mutant'}
            exec(compile(source.replace(guard, 'pass # owned control mutant'), '<owned-mutant>', 'exec'), namespace)
            # The same rejection oracle fails on the mutant: the injected bypass is killed.
            with self.assertRaises(AssertionError, msg=name):
                with self.assertRaises(c.ContractError):
                    probe(namespace)

    def test_T00_11_standard_scope(self):
        expected = {'standard': 'SYNTHETIC-INERT-COUPON', 'edition': 'fixture-2026', 'method': 'fixture-method', 'specimen': 'inert-coupon'}
        descriptor = {k: v for k, v in expected.items() if k != 'specimen'}
        descriptor.update(specimens=['inert-coupon'], source_sha256=c.raw_hash(b'synthetic descriptor'))
        self.assertIsNone(c.validate_standard_scope(dict(expected), descriptor)['physical_compliance'])
        for key in expected:
            bad = dict(expected); bad[key] = 'out-of-scope'
            with self.assertRaisesRegex(c.ContractError, 'mismatch'):
                c.validate_standard_scope(bad, descriptor)
        with self.assertRaises(c.ContractError):
            c.validate_standard_scope(expected, {**descriptor, 'source_sha256': None})

    def test_rust_wire_parity(self):
        self.assertEqual(unicodedata.unidata_version, '15.0.0', 'Unsupported Unicode data profile; no normalization fallback')
        binary = os.environ.get('JARAMBIT_SCIENCE_WIRE_BIN')
        self.assertTrue(binary and Path(binary).is_file(), 'Rust wire control binary unavailable; error, never skipped')
        fixtures = [b'{"b":1e0,"a":18446744073709551615,"zero":-0}',
                    '{"α":"试样-é","value":1.5749999999999998}'.encode(),
                    b'[1.7976931348623157e308,5e-324,-9223372036854775808,0.0,-0.0]',
                    json.dumps({'': '试样', '\u0000': 'control key', 'x'*513: 'long key'}, ensure_ascii=False).encode()]
        with tempfile.TemporaryDirectory() as directory:
            for i, raw in enumerate(fixtures):
                path = Path(directory)/f'wire-{i}.json'; path.write_bytes(raw)
                command = [binary, '--exact', 'wire_probe', '--nocapture', '--test-threads=1']
                p = subprocess.run(command, env={**os.environ, 'JARAMBIT_SCIENCE_WIRE_INPUT': str(path)},
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0, p.stderr)
                match = re.search(r'SCIENCE_WIRE_HEX=([0-9a-f]+)', p.stdout)
                self.assertIsNotNone(match, p.stdout)
                self.assertEqual(match.group(1), c.canonical_wire(c.strict_loads(raw, LIMITS)).hex())
            for i, raw in enumerate(['{"é":1,"e\\u0301":2}'.encode(), b'{"a":1,"a":2}', b'1e999', b'1e-999', b'"\\ud800"']):
                path = Path(directory)/f'invalid-{i}.json'; path.write_bytes(raw)
                with self.assertRaises(c.ContractError):
                    c.strict_loads(raw, LIMITS)
                p = subprocess.run([binary, '--exact', 'wire_probe', '--nocapture', '--test-threads=1'],
                                   env={**os.environ, 'JARAMBIT_SCIENCE_WIRE_INPUT': str(path)}, capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0)
                self.assertIn('SCIENCE_WIRE_ERROR=', p.stdout)
            text = '{"a":1,"sample":"试样-é"}'
            for i, raw in enumerate([text.encode('utf-8-sig'), text.encode('utf-16-le'), text.encode('utf-16-be'),
                                     text.encode('utf-32-le'), text.encode('utf-32-be')]):
                path = Path(directory)/f'encoding-{i}.json'; path.write_bytes(raw)
                with self.assertRaises(c.ContractError):
                    c.strict_loads(raw, LIMITS)
                p = subprocess.run([binary, '--exact', 'wire_probe', '--nocapture', '--test-threads=1'],
                                   env={**os.environ, 'JARAMBIT_SCIENCE_WIRE_INPUT': str(path)}, capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0)
                self.assertIn('SCIENCE_WIRE_ERROR=', p.stdout)
            with self.assertRaises(c.ContractError):
                c.strict_loads('"\ud800"', LIMITS)

    def test_frozen_catalog_and_receipt_schema(self):
        policy = json.loads((ROOT/'assurance/policies/release-v1.json').read_text())
        catalog = build_catalog(policy, c.raw_hash(Path(__file__).read_bytes()))
        self.assertEqual(len(catalog), 11)
        self.assertIn('T00-11-standard_scope', {case['id'] for case in catalog})
        for change in [('schema', 99), ('exit_code', 1), ('exit_code', True), ('counts', {'expected': 4, 'passed': 4, 'failed': 0, 'error': 0, 'not_run': 0})]:
            bad = receipt(case()); bad[change[0]] = change[1]
            with self.assertRaises(c.ContractError):
                c.validate_receipt(bad, case(), ARTIFACTS)

    def test_inventory_cli_rejects_empty_and_source_tamper(self):
        from ops.ci.test_inventory import check
        policy_path = ROOT/'assurance/testing/policy.json'
        self.assertTrue(policy_path.is_file(), 'Frozen runtime policy unavailable, never a passing skip')
        policy = json.loads(policy_path.read_text())
        release = json.loads((ROOT/'assurance/policies/release-v1.json').read_text())
        catalog = build_catalog(release, policy['source_input_sha256'])
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory); catalog_path = parent/'catalog.json'; catalog_path.write_text(json.dumps(catalog))
            empty = parent/'receipts'; empty.mkdir()
            self.assertEqual(check(catalog_path, empty, policy_path)['support'], 'incomplete')
            forged = dict(policy); forged['source_input_sha256'] = '0'*64
            forged_path = parent/'policy.json'; forged_path.write_text(json.dumps(forged))
            with self.assertRaisesRegex(c.ContractError, 'source/input'):
                check(catalog_path, empty, forged_path)

    def test_schemas_are_closed_and_actual_case_roundtrip(self):
        import jsonschema
        schemas = list((ROOT/'assurance/schemas').glob('*.json'))
        core = {'evidence.v2.json', 'observation_record.v1.json',
                'qualification_result.v1.json', 'study_record.v1.json', 'test_case.v1.json'}
        records = {'exposure_history.v1.json', 'material_state.v1.json',
                   'measurement_intervention.v1.json', 'specimen.v1.json', 'test_plan.v1.json'}
        self.assertEqual({path.name for path in schemas}, core | records)
        for path in schemas:
            jsonschema.Draft202012Validator.check_schema(json.loads(path.read_text()))
        schema = json.loads((ROOT/'assurance/schemas/test_case.v1.json').read_text())
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(case())
        for bad in [{**case(), 'unknown': True}, {**case(), 'schema': 99}, {**case(), 'required': 1}]:
            self.assertTrue(list(validator.iter_errors(bad)))

    def test_executable_initializers_and_new_import_inputs_withdraw_old_receipts(self):
        from ops.ci.test_inventory import check
        frozen = source_bundle(ROOT)
        policy = json.loads((ROOT/'assurance/testing/policy.json').read_text())
        self.assertEqual(frozen, policy['source_bundle'])
        self.assertEqual(c.scientific_hash(frozen), policy['source_input_sha256'])
        release = json.loads((ROOT/'assurance/policies/release-v1.json').read_text())
        catalog = build_catalog(release, policy['source_input_sha256'])
        guard = b'\nfrom assurance.testing import contracts\ncontracts.finite = lambda value: float(value)\n'
        with tempfile.TemporaryDirectory() as directory:
            def fixture(name):
                root = Path(directory)/name
                for path in set(frozen) | {'assurance/testing/policy.json', 'assurance/policies/release-v1.json'}:
                    source = ROOT/path
                    if source.is_file():
                        dest = root/path; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, dest)
                self.assertEqual(source_bundle(root), frozen)
                (root/'catalog.json').write_text(json.dumps(catalog))
                records = root/'receipts'; records.mkdir(); (records/'result').write_bytes(ARTIFACTS['result'])
                for cs in catalog: (records/(cs['id']+'.json')).write_text(json.dumps(receipt(cs)))
                with mock.patch('ops.ci.test_inventory.ROOT', root):
                    self.assertEqual(check(root/'catalog.json', records, root/'assurance/testing/policy.json')['support'], 'complete')
                return root

            # Exercise real imports after existing and previously absent initializers alter a guard.
            for i, initializer in enumerate(['assurance/testing/__init__.py', 'assurance/__init__.py',
                                              'assurance/testing/tests/__init__.py', 'ops/__init__.py', 'ops/ci/__init__.py']):
                root = fixture(str(i)); target = root/initializer
                target.write_bytes((target.read_bytes() if target.exists() else b'') + guard)
                self.assertNotEqual(source_bundle(root), frozen)
                script = '''from assurance.testing import contracts
import assurance.testing.tests
from ops.ci.test_inventory import check
from pathlib import Path
assert contracts.finite(True) == 1.0
try:
    check(Path('catalog.json'), Path('receipts'), Path('assurance/testing/policy.json'))
except contracts.ContractError as error:
    assert 'source/input' in str(error), error
else:
    raise AssertionError('old receipt inventory admitted after runtime mutation')
'''
                run = subprocess.run([sys.executable, '-c', script], cwd=root, capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
            root = fixture('new-module')
            (root/'assurance/testing/new_input.py').write_text('value = 1\n')
            self.assertNotEqual(source_bundle(root), frozen)
            with mock.patch('ops.ci.test_inventory.ROOT', root), self.assertRaisesRegex(c.ContractError, 'source/input'):
                check(root/'catalog.json', root/'receipts', root/'assurance/testing/policy.json')
            # Valid schema metadata edits still change a real test input. The
            # healthy copied inventory passes in fixture(); old receipts cannot
            # qualify any changed record schema, even if it remains valid JSON.
            for name in ['exposure_history.v1.json', 'material_state.v1.json',
                         'measurement_intervention.v1.json', 'specimen.v1.json', 'test_plan.v1.json']:
                root = fixture('schema-'+name)
                target = root/'assurance/schemas'/name
                schema = json.loads(target.read_bytes())
                schema['$comment'] = 'owned schema-identity adverse control'
                target.write_text(json.dumps(schema))
                self.assertNotEqual(source_bundle(root), frozen)
                with mock.patch('ops.ci.test_inventory.ROOT', root), self.assertRaisesRegex(c.ContractError, 'source/input'):
                    check(root/'catalog.json', root/'receipts', root/'assurance/testing/policy.json')
            root = fixture('escape')
            (root/'assurance/testing/escape.py').symlink_to(ROOT/'assurance/testing/contracts.py')
            with self.assertRaisesRegex(c.ContractError, 'symlink'): source_bundle(root)
            root = fixture('unsupported')
            (root/'assurance/testing/unsupported.py').write_text('from ops.render import pro_hero\n')
            with self.assertRaisesRegex(c.ContractError, 'unsupported local import'): source_bundle(root)


if __name__ == '__main__':
    unittest.main()
