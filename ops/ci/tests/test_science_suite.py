"""T19 paired positive/adverse controls (run: python3 -B -m unittest discover -s ops/ci/tests -p test_science_suite.py -v).

Synthetic software contracts only: neutral placeholder identities and toy files, no product qualification.
Test names test_T19_NN_<control>_* map to frozen case IDs; T19-07/08/09 exercise interfaces whose whole
criteria stay not_run upstream. Mutants are in-memory copies of science_suite with one guard removed.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'ops'/'ci'))
import science_suite as s  # noqa: E402
from assurance.testing.contracts import ContractError, raw_hash, scientific_hash, strict_loads, validate_case  # noqa: E402

EMPTY_HISTORY = {'schema': 1, 'attempts': {}}
TOY_IDS = sorted(['toy_suite.Toy.test_T19_01_positive_toy', 'toy_suite.Toy.test_T19_01_adverse_toy',
                  'toy_suite.Toy.test_T19_07_positive_toy', 'toy_suite.Toy.test_T19_07_adverse_toy',
                  'toy_suite.Toy.test_neutral_extra'])


def toy_digest(label):
    return raw_hash(b'placeholder ' + label.encode())


def toy_transcript(methods, module='toy_suite'):
    """A genuine verbose transcript from this interpreter's unittest runner."""
    cls = type('Toy', (unittest.TestCase,), methods)
    cls.__module__, cls.__qualname__ = module, 'Toy'
    stream = io.StringIO()
    suite = unittest.TestLoader().loadTestsFromTestCase(cls)
    unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return stream.getvalue()


def ok(self):
    pass


def fail(self):
    self.fail('placeholder failure')


def skip(self):
    self.skipTest('placeholder dependency unavailable')


def swap_to_symlink(path, target):
    path.unlink()
    path.symlink_to(target)


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        self.outside = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.outside)


class Catalog(unittest.TestCase):
    def test_catalog_binds_frozen_ten_ids_to_s01_cases(self):
        release = s.load_release_policy(ROOT)
        catalog = s.build_catalog(ROOT)
        self.assertEqual([c['id'] for c in catalog], s.frozen_ids(release))
        self.assertEqual(len(catalog), 10)
        identity = scientific_hash(s.source_identity(ROOT))
        for case in catalog:
            validate_case(case)
            self.assertEqual(case['oracle_sha256'], s.T19_DEFINITIONS[case['id']])
            self.assertEqual(case['input_sha256'], identity)
            self.assertTrue(case['required'])

    def test_catalog_definitions_follow_s00_convention_and_pin(self):
        release = s.load_release_policy(ROOT)
        records = [{'id': cid, 'oracle': 'placeholder ' + cid} for cid in s.T19_DEFINITIONS]
        data = json.dumps({'cases': [{'id': 'T00-01-placeholder'}, *records]}).encode()
        toy = {'software_contracts': {**release['software_contracts'], 'catalog': {'sha256': raw_hash(data)}}}
        derived = s.derive_definitions(data, toy)
        self.assertEqual(derived, {r['id']: raw_hash(json.dumps(r, sort_keys=True, separators=(',', ':')).encode())
                                   for r in records})
        with self.assertRaisesRegex(ContractError, 'frozen catalog mismatch'):
            s.derive_definitions(data + b' ', toy)
        short = json.dumps({'cases': records[:-1]}).encode()
        toy['software_contracts']['catalog'] = {'sha256': raw_hash(short)}
        with self.assertRaisesRegex(ContractError, 'inventory mismatch'):
            s.derive_definitions(short, toy)

    def test_catalog_rejects_release_policy_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for name in ('assurance/testing/policy.json', 'assurance/policies/release-v1.json'):
                (root/name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, root/name)
            self.assertEqual(s.load_release_policy(root), s.load_release_policy(ROOT))
            with (root/'assurance/policies/release-v1.json').open('ab') as output:
                output.write(b'\n')
            with self.assertRaisesRegex(ContractError, 'S01 pin'):
                s.load_release_policy(root)

    def test_catalog_expected_inventory_is_bound_to_suite_source(self):
        catalog, expected = s.source_context(ROOT)
        self.assertEqual(catalog, s.build_catalog(ROOT))
        self.assertIn('test_science_suite.Catalog.test_catalog_expected_inventory_is_bound_to_suite_source', expected)
        self.assertEqual(expected, s.inventory_from_source((ROOT/s.SUITE_TESTS).read_bytes()))
        self.assertEqual(s.source_identity(ROOT)[s.SUITE_TESTS], raw_hash((ROOT/s.SUITE_TESTS).read_bytes()))
        for bad in ([], ['a', 'a'], 'a', None):
            with self.subTest(bad), self.assertRaises(ContractError):
                s.trusted_inventory(bad)


class RequiredSkip(unittest.TestCase):
    EXPECTED = ['toy_suite.Toy.test_a', 'toy_suite.Toy.test_b']

    def test_T19_01_positive_all_expected_tests_pass(self):
        log = toy_transcript({'test_a': ok, 'test_b': ok})
        result = s.collect_unittest(log, self.EXPECTED)
        self.assertEqual(result['execution'], 'passed', result)
        warned = log.replace('test_b) ... ok', 'test_b) ... /toy/x.py:1: ResourceWarning: unclosed file\n  x = 1\nok')
        self.assertNotEqual(warned, log)
        self.assertEqual(s.collect_unittest(warned, self.EXPECTED)['execution'], 'passed')

    def test_T19_01_adverse_skip_missing_or_empty_is_not_green(self):
        cases = {
            'required skip': (toy_transcript({'test_a': ok, 'test_b': skip}), self.EXPECTED),
            'deleted test': (toy_transcript({'test_a': ok}), self.EXPECTED),
            'failure': (toy_transcript({'test_a': ok, 'test_b': fail}), self.EXPECTED),
            'no tests': (toy_transcript({}), self.EXPECTED),
            'empty inventory': (toy_transcript({}), []),
            'duplicate': (toy_transcript({'test_a': ok, 'test_b': ok}).replace(
                'test_b (toy_suite.Toy.test_b)', 'test_a (toy_suite.Toy.test_a)'), self.EXPECTED),
            'extra test': (toy_transcript({'test_a': ok, 'test_b': ok, 'test_c': ok}), self.EXPECTED),
        }
        stream = io.StringIO()
        missing = unittest.TestLoader().loadTestsFromName('toy_missing_dependency_module')
        unittest.TextTestRunner(stream=stream, verbosity=2).run(missing)
        cases['missing dependency'] = (stream.getvalue(), ['toy_missing_dependency_module.Toy.test_a'])
        for name, (log, expected) in cases.items():
            with self.subTest(name):
                self.assertNotEqual(s.collect_unittest(log, expected)['execution'], 'passed')


class PathFilter(unittest.TestCase):
    def test_T19_02_positive_required_workflows_run_for_every_science_path(self):
        for name in ('version-check.yml', 'd1-gates.yml'):
            with self.subTest(name):
                text = (ROOT/'.github/workflows'/name).read_text()
                self.assertIn('pull_request', s.workflow_triggers(text))
                self.assertEqual(s.selection_violations(text), [])
        self.assertTrue(all((ROOT/p).is_file() for p in s.CRITICAL_PROBES), 'probe paths must exist')
        explicit = 'on:\n  pull_request:\n    paths:\n      - "**"\n'
        self.assertEqual(s.selection_violations(explicit), [])

    def test_T19_02_adverse_filtered_or_untriggered_selection_rejected(self):
        ignore = 'on:\n  pull_request:\n    paths-ignore:\n      - "requirements/**"\n      - "**/*.toml"\n'
        self.assertIn('pull_request:requirements/RS-karambit-v2.toml', s.selection_violations(ignore))
        negated = 'on:\n  pull_request:\n    paths: ["**", "!fem_solid/**"]\n'
        self.assertEqual(s.selection_violations(negated), ['pull_request:fem_solid/gci.py'])
        self.assertEqual(s.selection_violations('on:\n  push:\n    branches: [main]\n'),
                         ['pull_request: not triggered'])
        render = (ROOT/'.github/workflows/render-marketing-smoke.yml').read_text()
        self.assertEqual(len(s.selection_violations(render)), len(s.CRITICAL_PROBES))
        for text in ('on:\n  pull_request:\n    paths: ops/**\n', 'on:\n  pull_request:\n    paths: ["ops/[ab]/**"]\n'):
            with self.subTest(text), self.assertRaises(ContractError):
                s.selection_violations(text)

    def test_T19_02_positive_supported_yaml_forms_parse_faithfully(self):
        forms = {
            'on: [push, pull_request]\n': {'push': {}, 'pull_request': {}},
            'on: pull_request  # all pull requests\n': {'pull_request': {}},
            '"on":\n  pull_request: {}\n  workflow_dispatch:\n    inputs:\n      level: {}\n': {'pull_request': {}, 'workflow_dispatch': {}},
            "on:\n  pull_request:\n    types: [opened, synchronize, reopened, labeled]\n    branches:\n      - 'main'\n    paths: ['**', 'docs/a b.md']\n":
                {'pull_request': {'types': ['opened', 'synchronize', 'reopened', 'labeled'], 'branches': ['main'],
                                  'paths': ['**', 'docs/a b.md']}},
        }
        for text, parsed in forms.items():
            with self.subTest(text):
                self.assertEqual(s.workflow_triggers(text), parsed)
                self.assertEqual(s.selection_violations(text), [])
        block = 'on:\n  pull_request:\n    paths:\n      - "README.md"\n'
        self.assertEqual(len(s.selection_violations(block)), len(s.CRITICAL_PROBES))

    def test_T19_02_adverse_unsupported_forms_refuse_and_restrictions_report(self):
        refused = {
            'inline trigger mapping': 'on:\n  pull_request: {paths: ["README.md"]}\n',
            'flow on mapping': 'on: {pull_request: {paths: ["README.md"]}}\n',
            'quoted filter key': "on:\n  pull_request:\n    'paths': [\"README.md\"]\n",
            'unknown trigger key': 'on:\n  pull_request:\n    pathz: ["README.md"]\n',
            'anchor': 'on:\n  pull_request:\n    paths: &docs ["README.md"]\n',
            'alias item': 'on:\n  pull_request:\n    paths:\n      - *docs\n',
            'nested flow': 'on:\n  pull_request:\n    paths: [["README.md"]]\n',
            'duplicate key': 'on:\n  pull_request:\n    paths: ["**"]\n    paths: ["README.md"]\n',
            'yaml 1.1 true key': 'true:\n  pull_request:\n',
            'empty list': 'on:\n  pull_request:\n    paths:\n  push:\n',
        }
        for name, text in refused.items():
            with self.subTest(name), self.assertRaises(ContractError):
                s.selection_violations(text)
        self.assertEqual(s.selection_violations('on:\n  pull_request:\n    types: [labeled]\n'),
                         ['pull_request: types exclude opened,reopened,synchronize'])
        self.assertEqual(s.selection_violations('on:\n  pull_request:\n    branches: ["release/**"]\n'),
                         ['pull_request: branches exclude main'])
        self.assertEqual(s.selection_violations('on:\n  pull_request:\n    branches-ignore: [main]\n'),
                         ['pull_request: branches-ignore excludes main'])

    def test_T19_02_positive_cli_workflows_on_real_required_files(self):
        out = io.StringIO()
        paths = [str(ROOT/'.github/workflows/version-check.yml'), str(ROOT/'.github/workflows/d1-gates.yml')]
        with contextlib.redirect_stdout(out):
            self.assertEqual(s.main(['workflows', *paths]), 0)
        self.assertEqual(json.loads(out.getvalue()), {p: [] for p in paths})

    def test_T19_02_adverse_cli_workflows_inline_filter_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'inline.yml'
            path.write_text('on:\n  pull_request: {paths: ["README.md"]}\n')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(s.main(['workflows', str(path)]), 1)
            self.assertEqual(json.loads(out.getvalue())['support'], 'error')


class CapabilityOmission(unittest.TestCase):
    POLICY = {'capabilities': {'toy_method': {'required_case_ids': ['TX-01-a', 'TX-02-b']},
                               'toy_model': {'required_case_ids': ['TY-01-a']}}}

    def gate(self, capabilities, passed=('TX-01-a', 'TX-02-b')):
        return s.capability_gate({'schema': 1, 'capabilities': capabilities}, self.POLICY, passed)

    def enabled(self, proof=('TX-01-a', 'TX-02-b')):
        return {'state': 'enabled', 'reason': None, 'claims': ['toy-claim'], 'proof': list(proof)}

    def disabled(self):
        return {'state': 'disabled', 'reason': 'placeholder capability not activated', 'claims': [], 'proof': []}

    def test_T19_03_positive_executed_inventory_and_visible_disabled_branch(self):
        result = self.gate({'toy_method': self.enabled(), 'toy_model': self.disabled()})
        self.assertEqual(result['capabilities']['toy_method']['status'], 'software_contracts_executed')
        self.assertEqual(result['capabilities']['toy_model'], {'status': 'disabled',
                                                              'reason': 'placeholder capability not activated'})
        self.assertEqual(result['incomplete'], [])
        self.assertIsNone(result['physical_qualification'])
        release = {'software_contracts': {'gate_policy_reference': {'sha256': raw_hash(json.dumps(self.POLICY).encode())}}}
        self.assertEqual(s.load_gate_policy(json.dumps(self.POLICY).encode(), release), self.POLICY)

    def test_T19_03_adverse_omitted_or_unexecuted_capability_incomplete(self):
        self.assertEqual(self.gate({'toy_method': self.enabled(['TX-01-a']), 'toy_model': self.disabled()})
                         ['incomplete'], ['toy_method'])
        self.assertEqual(self.gate({'toy_method': self.enabled(), 'toy_model': self.disabled()}, ['TX-01-a'])
                         ['incomplete'], ['toy_method'])
        self.assertEqual(self.gate({'toy_method': self.enabled()})['incomplete'], ['toy_model'])
        rejected = {
            'disabled with claims': {'toy_model': {**self.disabled(), 'claims': ['toy-claim']}},
            'disabled without reason': {'toy_model': {**self.disabled(), 'reason': None}},
            'enabled without claims': {'toy_method': {**self.enabled(), 'claims': []}},
            'proof outside inventory': {'toy_method': self.enabled(['TX-01-a', 'TX-02-b', 'TY-01-a'])},
            'unknown capability': {'toy_other': self.disabled()},
            'unknown state': {'toy_model': {**self.disabled(), 'state': 'auto'}},
        }
        for name, capabilities in rejected.items():
            with self.subTest(name), self.assertRaises(ContractError):
                self.gate(capabilities)
        release = {'software_contracts': {'gate_policy_reference': {'sha256': toy_digest('other policy')}}}
        with self.assertRaisesRegex(ContractError, 'gate policy mismatch'):
            s.load_gate_policy(json.dumps(self.POLICY).encode(), release)


class RunnerEscape(Workspace):
    TOUCH = [['/usr/bin/touch', {'path': 'output'}]]

    def record(self, **changes):
        (self.root/'work').mkdir(exist_ok=True)
        return {'argv': ['/usr/bin/touch', str(self.root/'work/out.json')], 'cwd': 'work',
                'env': {'PYTHONDONTWRITEBYTECODE': '1'}, 'outputs': ['work/out.json'], **changes}

    def test_T19_04_positive_owned_argv_validated_never_executed(self):
        result = s.check_command(self.record(), self.root, self.TOUCH)
        self.assertFalse(result['executed'])
        self.assertEqual(result['outputs'], [str(self.root/'work/out.json')])
        self.assertFalse((self.root/'work/out.json').exists())

    def test_T19_04_adverse_shell_traversal_and_symlink_escapes_rejected(self):
        (self.root/'link').symlink_to(self.outside, target_is_directory=True)
        admitted = self.TOUCH + [['/bin/bash', '-c', 'touch x'], ['/usr/bin/python3', '-c', 'print(1)']]
        rejected = {
            'shell string': {'argv': 'touch x; touch y'},
            'shell program': {'argv': ['/bin/bash', '-c', 'touch x']},
            'inline code': {'argv': ['/usr/bin/python3', '-c', 'print(1)']},
            'not allowlisted': {'argv': ['/usr/bin/rm', 'x']},
            'traversal': {'outputs': ['work/../../out.json']},
            'absolute': {'outputs': ['/etc/placeholder']},
            'symlink': {'outputs': ['link/out.json']},
            'cwd escape': {'cwd': '..'},
            'environment': {'env': {'LD_PRELOAD': '/toy.so'}},
        }
        for name, change in rejected.items():
            with self.subTest(name), self.assertRaises(ContractError):
                s.check_command(self.record(**change), self.root, admitted)
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_T19_04_positive_admitted_template_binds_inputs_options_and_spaced_paths(self):
        (self.root/'work dir').mkdir()
        (self.root/'work dir/in put.py').write_text('# placeholder script\n')
        admitted = [['/usr/bin/python3', '-B', {'path': 'input'}, '--out', {'path': 'output'}]]
        record = {'argv': ['/usr/bin/python3', '-B', 'in put.py', '--out', str(self.root/'work dir/out file.json')],
                  'cwd': 'work dir', 'env': {}, 'outputs': ['work dir/out file.json']}
        result = s.check_command(record, self.root, admitted)
        self.assertEqual((result['template'], result['inputs'], result['executed']),
                         (0, [str(self.root/'work dir/in put.py')], False))

    def test_T19_04_adverse_argv_paths_must_match_admitted_scope_and_outputs(self):
        (self.root/'work').mkdir()
        (self.root/'work/script.py').write_text('# placeholder script\n')
        (self.root/'linked').symlink_to(self.outside, target_is_directory=True)
        script = [['/usr/bin/python3', '-B', {'path': 'input'}, {'path': 'output'}]]
        base = {'cwd': 'work', 'env': {}, 'outputs': ['work/out.json']}
        rejected = {
            'argv output outside root': (self.TOUCH, ['/usr/bin/touch', str(self.outside/'escaped.json')]),
            'undeclared in-root output': (self.TOUCH, ['/usr/bin/touch', str(self.root/'work/other.json')]),
            'relative traversal': (self.TOUCH, ['/usr/bin/touch', '../../escaped.json']),
            'symlinked argv path': (self.TOUCH, ['/usr/bin/touch', str(self.root/'linked/out.json')]),
            'input outside root': (script, ['/usr/bin/python3', '-B', str(self.outside/'script.py'), 'out.json']),
            'missing input': (script, ['/usr/bin/python3', '-B', 'absent.py', 'out.json']),
            'literal option differs': (script, ['/usr/bin/python3', '-O', 'script.py', 'out.json']),
            'program-name allowlist': ({'/usr/bin/touch'}, ['/usr/bin/touch', str(self.root/'work/out.json')]),
        }
        for name, (admitted, argv) in rejected.items():
            with self.subTest(name), self.assertRaises(ContractError):
                s.check_command({**base, 'argv': argv}, self.root, admitted)
        self.assertEqual(s.check_command({**base, 'argv': ['/usr/bin/python3', '-B', 'script.py', 'out.json']},
                                         self.root, script)['executed'], False)
        self.assertEqual(list(self.outside.iterdir()), [])


class UploadMissing(Workspace):
    def attempt(self, **changes):
        (self.root/'out.json').write_bytes(b'{"placeholder": 1}\n')
        (self.root/'raw.log').write_bytes(b'placeholder raw log\n')
        artifacts = {'out.json': {'sha256': raw_hash(b'{"placeholder": 1}\n'), 'bytes': 19}}
        return {'complete': True, 'timed_out': False, 'exit_code': 0, 'artifacts': artifacts, 'raw_failure': [],
                **changes}

    def test_T19_05_positive_complete_bound_uploads(self):
        self.assertEqual(s.check_uploads(self.attempt(), self.root, 1024),
                         {'status': 'complete', 'problems': [], 'retained_raw_failure': []})

    def test_T19_05_adverse_missing_corrupt_oversized_or_timeout_incomplete(self):
        attempt = self.attempt()
        (self.root/'out.json').unlink()
        self.assertEqual(s.check_uploads(attempt, self.root, 1024)['problems'], ['missing upload: out.json'])
        attempt = self.attempt()
        (self.root/'out.json').write_bytes(b'{"placeholder": 2}\n')
        self.assertEqual(s.check_uploads(attempt, self.root, 1024)['problems'], ['corrupt upload: out.json'])
        self.assertEqual(s.check_uploads(self.attempt(), self.root, 8)['problems'], ['oversized upload: out.json'])
        result = s.check_uploads(self.attempt(timed_out=True, exit_code=None, raw_failure=['raw.log']), self.root, 1024)
        self.assertEqual((result['status'], result['retained_raw_failure']), ('incomplete', ['raw.log']))
        self.assertTrue((self.root/'raw.log').is_file())
        self.assertEqual(s.check_uploads(self.attempt(raw_failure=['gone.log']), self.root, 1024)['status'], 'incomplete')
        self.assertEqual(s.check_uploads(self.attempt(artifacts={}), self.root, 1024)['status'], 'incomplete')
        with self.assertRaises(ContractError):
            s.check_uploads(self.attempt(artifacts={'../out.json': {'sha256': toy_digest('x'), 'bytes': 1}}),
                            self.root, 1024)

    def test_T19_05_positive_descriptor_read_of_owned_nested_regular_file(self):
        (self.root/'sub').mkdir()
        body = b'neutral toy bytes\n'
        (self.root/'sub/owned.raw').write_bytes(body)
        self.assertEqual(s.read_owned(self.root, 'sub/owned.raw', 64), body)
        attempt = {'complete': True, 'timed_out': False, 'exit_code': 0, 'raw_failure': [],
                   'artifacts': {'sub/owned.raw': {'sha256': raw_hash(body), 'bytes': len(body)}}}
        self.assertEqual(s.check_uploads(attempt, self.root, 64)['status'], 'complete')

    def test_T19_05_adverse_replaced_symlinked_or_special_uploads_refused(self):
        body = b'neutral toy bytes\n'
        (self.outside/'same.raw').write_bytes(body)
        (self.outside/'dir').mkdir()
        (self.outside/'dir/owned.raw').write_bytes(body)

        def attempt(name):
            return {'complete': True, 'timed_out': False, 'exit_code': 0, 'raw_failure': [],
                    'artifacts': {name: {'sha256': raw_hash(body), 'bytes': len(body)}}}
        (self.root/'owned.raw').write_bytes(body)
        swap_to_symlink(self.root/'owned.raw', self.outside/'same.raw')
        self.assertEqual(s.check_uploads(attempt('owned.raw'), self.root, 64)['status'], 'incomplete')
        (self.root/'parent').symlink_to(self.outside/'dir', target_is_directory=True)
        self.assertEqual(s.check_uploads(attempt('parent/owned.raw'), self.root, 64)['status'], 'incomplete')
        os.mkfifo(self.root/'pipe.raw')
        self.assertEqual(s.check_uploads(attempt('pipe.raw'), self.root, 64)['status'], 'incomplete')
        (self.root/'raced.raw').write_bytes(body)
        original = s._read_fd

        def swap_during_read(fd, limit):
            data = original(fd, limit)
            swap_to_symlink(self.root/'raced.raw', self.outside/'same.raw')
            return data
        with mock.patch.object(s, '_read_fd', swap_during_read):
            result = s.check_uploads(attempt('raced.raw'), self.root, 64)
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue(result['problems'][0].startswith('unsafe upload: raced.raw'), result)


class FreshVsReuse(unittest.TestCase):
    CURRENT = toy_digest('current input')
    HISTORY = {'attempt-000': {'input_sha256': toy_digest('current input'), 'artifacts': {'log': toy_digest('failed log')},
                               'outcome': 'failed'},
               'attempt-001': {'input_sha256': toy_digest('current input'), 'artifacts': {'log': toy_digest('old log')},
                               'outcome': 'passed'}}

    def run_record(self, **changes):
        return {'mode': 'fresh', 'attempt_id': 'attempt-002', 'input_sha256': self.CURRENT,
                'artifacts': {'log': toy_digest('new log')}, 'reused_from': None, **changes}

    def reuse(self, **changes):
        return self.run_record(**{'mode': 'reuse', 'attempt_id': 'attempt-003', 'artifacts': {'log': toy_digest('old log')},
                                  'reused_from': {'attempt_id': 'attempt-001', 'scope': 'unchanged placeholder inputs'},
                                  **changes})

    def test_T19_06_positive_fresh_and_scoped_reuse_labeled(self):
        fresh = s.classify_run(self.run_record(), self.CURRENT, self.HISTORY)
        self.assertEqual(fresh, {'mode': 'fresh', 'counts_as_fresh_execution': True})
        reused = s.classify_run(self.reuse(), self.CURRENT, self.HISTORY)
        self.assertEqual((reused['mode'], reused['counts_as_fresh_execution']), ('reuse', False))
        history = {'schema': 1, 'attempts': self.HISTORY}
        self.assertEqual(s.validate_history(history, scientific_hash(history)), self.HISTORY)
        self.assertEqual(s.validate_history(EMPTY_HISTORY, scientific_hash(EMPTY_HISTORY)), {})

    def test_T19_06_adverse_historical_evidence_claimed_fresh_rejected(self):
        rejected = {
            'relabeled attempt': self.run_record(attempt_id='attempt-001'),
            'copied artifact': self.run_record(artifacts={'log': toy_digest('old log')}),
            'copied failed artifact': self.run_record(artifacts={'log': toy_digest('failed log')}),
            'other input': self.run_record(input_sha256=toy_digest('other input')),
            'fresh naming source': self.run_record(reused_from={'attempt_id': 'attempt-001', 'scope': 'x'}),
            'incompatible reuse': self.reuse(input_sha256=toy_digest('other input')),
            'unscoped reuse': self.reuse(reused_from={'attempt_id': 'attempt-001', 'scope': ''}),
            'unknown source': self.reuse(reused_from={'attempt_id': 'attempt-404', 'scope': 'x'}),
            'changed artifacts': self.reuse(artifacts={'log': toy_digest('new log')}),
        }
        for name, record in rejected.items():
            with self.subTest(name), self.assertRaises(ContractError):
                s.classify_run(record, self.CURRENT, self.HISTORY)
        history = {'schema': 1, 'attempts': self.HISTORY}
        flagged = {'schema': 1, 'attempts': self.HISTORY, 'complete': True}
        bad_outcome = {'schema': 1, 'attempts': {'attempt-001': {**self.HISTORY['attempt-001'], 'outcome': 'healthy'}}}
        for name, (record, pin) in {'pin mismatch': (history, toy_digest('other pin')),
                                    'self-reported complete flag': (flagged, scientific_hash(flagged)),
                                    'unknown outcome': (bad_outcome, scientific_hash(bad_outcome))}.items():
            with self.subTest(name), self.assertRaises(ContractError):
                s.validate_history(record, pin)


class DossierInterface(unittest.TestCase):
    def views(self):
        identity = {'candidate': toy_digest('candidate'), 'material': toy_digest('material'),
                    'mesh': toy_digest('mesh'), 'requirements': toy_digest('requirements'), 'cases': ['TX-01-a']}
        return {name: {'identity': dict(identity), 'claims': {'toy-claim': 'pass', 'toy-lab': 'incomplete'}}
                for name in ('cli_json', 'table', 'render_manifest')}

    def test_T19_07_positive_consistent_views_reconstruct(self):
        result = s.reconstruct_dossier(self.views(), {'toy-claim': ['TX-01-a']}, ['TX-01-a'])
        self.assertEqual(result, {'integrity': 'reconstructed', 'mismatches': [], 'release_authorized': False})

    def test_T19_07_adverse_identity_claim_or_proof_mismatch_fails(self):
        views = self.views()
        views['render_manifest']['identity']['material'] = toy_digest('other material')
        self.assertEqual(s.reconstruct_dossier(views, {'toy-claim': ['TX-01-a']}, ['TX-01-a'])['integrity'], 'failed')
        views = self.views()
        views['table']['claims']['toy-lab'] = 'pass'
        self.assertEqual(s.reconstruct_dossier(views, {'toy-claim': ['TX-01-a']}, ['TX-01-a'])['integrity'], 'failed')
        self.assertEqual(s.reconstruct_dossier(self.views(), {'toy-claim': ['TX-01-a']}, [])['integrity'], 'failed')
        views = self.views()
        views['table']['claims']['toy-lab'] = 'healthy'
        for bad in (views, {'cli_json': self.views()['cli_json']}):
            with self.assertRaises(ContractError):
                s.reconstruct_dossier(bad, {}, [])


class RenderFinishInterface(unittest.TestCase):
    FINISH = {'color': 'placeholder-grey', 'coating_thickness_um': 1.0}

    def material(self, **source):
        entry = {'value': 1.0, 'source': {'kind': 'measured_record', 'sha256': toy_digest('record'), **source}}
        return {'structural': {'yield_strength': entry}, 'finish': dict(self.FINISH)}

    def test_T19_08_positive_structural_values_from_measured_sources(self):
        result = s.check_material_sources(self.material())
        self.assertEqual((result['status'], result['structural_qualification']), ('sources_bound', None))

    def test_T19_08_adverse_finish_metadata_transfer_rejected(self):
        self.assertEqual(s.check_material_sources(self.material(kind='render_finish'))['status'], 'rejected')
        transfer = self.material(sha256=scientific_hash(self.FINISH))
        self.assertEqual(s.check_material_sources(transfer)['status'], 'rejected')
        named = self.material()
        named['finish']['yield_strength'] = 1.0
        self.assertEqual(s.check_material_sources(named)['status'], 'rejected')
        nonfinite = self.material()
        nonfinite['structural']['yield_strength']['value'] = float('nan')
        with self.assertRaises(ContractError):
            s.check_material_sources(nonfinite)


class ProtectiveInterface(unittest.TestCase):
    def evidence(self, **changes):
        records = {name: {'status': 'pass', 'sha256': toy_digest(name)} for name in s.SHEATH_RECORDS}
        return {'existing_tests': 'passed', 'scalar': {'status': 'pass'}, 'records': records, **changes}

    def test_T19_09_positive_complete_records_still_need_review(self):
        result = s.protective_claim(self.evidence())
        self.assertEqual((result['status'], result['promotion'], result['scalar_substitutes']),
                         ('records_complete', 'review_required', False))

    def test_T19_09_adverse_scalar_cannot_fill_missing_directional_records(self):
        evidence = self.evidence()
        del evidence['records']['directional_retention']
        self.assertEqual(s.protective_claim(evidence)['missing'], ['directional_retention'])
        evidence = self.evidence()
        evidence['records']['unseated']['status'] = 'unknown'
        self.assertEqual(s.protective_claim(evidence)['promotion'], 'blocked')
        self.assertEqual(s.protective_claim(self.evidence(existing_tests='not_run'))['missing'], ['existing sheath tests'])
        evidence = self.evidence()
        evidence['records']['scalar_retention'] = {'status': 'pass', 'sha256': toy_digest('scalar')}
        with self.assertRaises(ContractError):
            s.protective_claim(evidence)


class FinalPolicy(unittest.TestCase):
    def final(self):
        return json.loads(json.dumps(s.load_release_policy(ROOT)['final_release']))

    def satisfied(self, final):
        return {g['id']: {'status': 'satisfied', 'receipt_sha256': toy_digest(g['id'])} for g in final['gates']}

    def test_T19_10_positive_all_gates_or_owner_amendment_without_release_authority(self):
        final = self.final()
        result = s.final_policy(final, self.satisfied(final))
        self.assertEqual(result['release_class'], 'final_policy_gates_satisfied')
        self.assertFalse(result['release_authorized'])
        gate = final['gates'][0]['id']
        evidence = self.satisfied(final)
        del evidence[gate]
        final['amendments'] = [{'gate': gate, 'owner_authorization_sha256': toy_digest('owner'), 'scope': 'placeholder'}]
        self.assertEqual(s.final_policy(final, evidence)['release_class'], 'final_policy_gates_satisfied')

    def test_T19_10_adverse_missing_gate_is_scoped_rc_and_no_self_waiver(self):
        final = self.final()
        result = s.final_policy(final, {})
        self.assertEqual(result['release_class'], 'scoped_rc_only')
        self.assertEqual(result['unresolved_gates'], [g['id'] for g in final['gates']])
        evidence = self.satisfied(final)
        evidence[final['gates'][-1]['id']]['status'] = 'pending'
        self.assertEqual(s.final_policy(final, evidence)['release_class'], 'scoped_rc_only')
        gate = final['gates'][0]['id']
        waived = dict(final, amendments=[{'gate': gate, 'owner_authorization_sha256': None, 'scope': 'self'}])
        forced = self.satisfied(final)
        forced[gate] = {'status': 'satisfied', 'receipt_sha256': toy_digest('x'), 'force': True}
        for name, (policy, evidence) in {'self waiver': (waived, {}), 'forced green': (final, forced),
                                         'unbound gate': (final, {gate: {'status': 'satisfied', 'receipt_sha256': None}}),
                                         'unknown gate': (final, {'placeholder-gate': {}}),
                                         'self authorization': (dict(final, authorization='worker'), {})}.items():
            with self.subTest(name), self.assertRaises(ContractError):
                s.final_policy(policy, evidence)


class Collector(Workspace):
    PIN = scientific_hash(EMPTY_HISTORY)

    def transcript(self, adverse=ok, extra=True):
        methods = {'test_T19_01_positive_toy': ok, 'test_T19_01_adverse_toy': adverse,
                   'test_T19_07_positive_toy': ok, 'test_T19_07_adverse_toy': ok}
        if extra:
            methods['test_neutral_extra'] = ok
        return toy_transcript(methods).encode()

    def catalog(self):
        return s.build_catalog(ROOT)

    def publish(self, log, name='attempt', attempt_id='placeholder-attempt', history=EMPTY_HISTORY, pin=PIN):
        attempt = self.root/name
        s.publish_attempt(attempt, self.catalog(), log, ['python3', '-B', '-m', 'unittest'], 0, attempt_id,
                          TOY_IDS, history, pin)
        return attempt

    def collect(self, attempt, history=EMPTY_HISTORY, pin=PIN, expected=TOY_IDS):
        return s.collect(self.catalog(), attempt, expected, history, pin)

    def forge_pass(self, attempt, case_id):
        path = attempt/(case_id + '.json')
        forged = strict_loads(path.read_bytes(), s.LIMITS)
        forged.update(execution='passed', finding='rejected_within_scope', exit_code=0, reason=None,
                      controls={'positive': 'passed', 'adverse': 'passed'},
                      counts={'expected': 2, 'passed': 2, 'failed': 0, 'error': 0, 'not_run': 0})
        path.unlink()
        path.write_text(json.dumps(forged))

    def history_with(self, log, attempt_id='placeholder-old', outcome='passed'):
        history = {'schema': 1, 'attempts': {attempt_id: {'input_sha256': self.catalog()[0]['input_sha256'],
                                                          'artifacts': {s.LOG: raw_hash(log)}, 'outcome': outcome}}}
        return history, scientific_hash(history)

    def test_collector_derives_passes_from_transcript_and_keeps_denominator(self):
        attempt = self.publish(self.transcript())
        result = self.collect(attempt)
        self.assertEqual((result['denominator'], result['expected_tests']), (10, len(TOY_IDS)))
        self.assertEqual(result['execution']['T19-01-required_skip'], 'passed')
        self.assertEqual(result['execution']['T19-07-dossier_mismatch'], 'not_run')
        self.assertEqual((result['support'], len(result['missing'])), ('incomplete', 9))
        self.assertEqual(result['upstream_not_run'], sorted(s.UPSTREAM))
        self.assertEqual((result['release_authorized'], result['product_qualification']), (False, None))
        receipt = strict_loads((attempt/'T19-07-dossier_mismatch.json').read_bytes(), s.LIMITS)
        self.assertEqual(receipt['controls'], {'positive': 'not_run', 'adverse': 'not_run'})
        with self.assertRaisesRegex(ContractError, 'fresh attempt'):
            self.publish(self.transcript())

    def test_collector_rejects_failed_tampered_deleted_or_forged_receipts(self):
        attempt = self.publish(self.transcript(adverse=fail))
        self.assertEqual(self.collect(attempt)['execution']['T19-01-required_skip'], 'failed')
        shutil.rmtree(attempt)
        attempt = self.publish(self.transcript())
        (attempt/'T19-01-required_skip.json').unlink()
        self.assertIn('T19-01-required_skip', self.collect(attempt)['missing'])
        shutil.rmtree(attempt)
        attempt = self.publish(self.transcript())
        os.chmod(attempt/s.LOG, 0o644)
        with (attempt/s.LOG).open('ab') as output:
            output.write(b'\n')
        with self.assertRaisesRegex(ContractError, 'artifact integrity'):
            self.collect(attempt)
        for case_id in ('T19-02-path_filter', 'T19-08-render_finish_metadata'):
            shutil.rmtree(attempt)
            attempt = self.publish(self.transcript())
            self.forge_pass(attempt, case_id)
            with self.subTest(case_id), self.assertRaises(ContractError):
                self.collect(attempt)

    def test_T19_01_positive_trusted_inventory_complete_transcript_end_to_end(self):
        attempt = self.publish(self.transcript())
        context = strict_loads((attempt/s.CONTEXT).read_bytes(), s.LIMITS)
        self.assertEqual((context['expected_inventory'], context['expected_inventory_sha256']),
                         (TOY_IDS, scientific_hash(TOY_IDS)))
        self.assertEqual(self.collect(attempt)['execution']['T19-01-required_skip'], 'passed')

    def test_T19_01_adverse_removed_expected_test_stays_incomplete_in_publisher_and_collector(self):
        partial = self.transcript(extra=False)
        self.assertIn(b'Ran 4 tests', partial)
        attempt = self.publish(partial)
        receipt = strict_loads((attempt/'T19-01-required_skip.json').read_bytes(), s.LIMITS)
        self.assertEqual(receipt['execution'], 'error')
        result = self.collect(attempt)
        self.assertEqual((result['execution']['T19-01-required_skip'], result['support']), ('error', 'incomplete'))
        self.forge_pass(attempt, 'T19-01-required_skip')
        with self.assertRaisesRegex(ContractError, 'not supported by transcript'):
            self.collect(attempt)
        with self.assertRaisesRegex(ContractError, 'trusted expected inventory'):
            self.collect(self.publish(self.transcript(), name='other'), expected=TOY_IDS[:-1])
        with self.assertRaisesRegex(ContractError, 'trusted expected test inventory'):
            s.publish_attempt(self.root/'none', self.catalog(), partial, ['python3'], 0, 'placeholder-none', None,
                              EMPTY_HISTORY, self.PIN)

    def test_T19_06_positive_pinned_history_first_run_and_prior_failure_retained(self):
        self.assertEqual(self.collect(self.publish(self.transcript()))['freshness'], 'caller_pinned_history')
        old = self.transcript(adverse=fail)
        history, pin = self.history_with(old, outcome='failed')
        result = self.collect(self.publish(self.transcript(), name='retry', attempt_id='placeholder-retry',
                                           history=history, pin=pin), history=history, pin=pin)
        self.assertEqual(result['execution']['T19-06-fresh_vs_reuse'], 'not_run')
        self.assertNotIn('T19-01-required_skip', result['missing'])

    def test_T19_06_adverse_unavailable_or_historical_transcript_not_fresh(self):
        log = self.transcript()
        attempt = self.publish(log, name='unavailable', history=None, pin=None)
        self.assertEqual(strict_loads((attempt/'T19-01-required_skip.json').read_bytes(), s.LIMITS)['execution'], 'error')
        result = self.collect(attempt, history=None, pin=None)
        self.assertEqual((result['freshness'], result['support']), ('history_unavailable', 'incomplete'))
        healthy = self.publish(log, name='healthy')
        result = self.collect(healthy, history=None, pin=None)
        self.assertIn('T19-01-required_skip', result['missing'])
        history, pin = self.history_with(log)
        relabeled = self.publish(log, name='relabeled', attempt_id='placeholder-new', history=history, pin=pin)
        receipt = strict_loads((relabeled/'T19-01-required_skip.json').read_bytes(), s.LIMITS)
        self.assertEqual(receipt['execution'], 'error')
        self.assertIn('historical artifact bytes claimed fresh', receipt['reason'])
        self.forge_pass(relabeled, 'T19-01-required_skip')
        with self.assertRaises(ContractError):
            self.collect(relabeled, history=history, pin=pin)
        with self.assertRaisesRegex(ContractError, 'different history'):
            self.collect(healthy, history=history, pin=pin)
        with self.assertRaisesRegex(ContractError, 'caller pin'):
            self.publish(log, name='badpin', history=history, pin=self.PIN)

    def test_T19_05_adverse_collector_reads_refuse_replaced_receipt_and_raced_transcript(self):
        attempt = self.publish(self.transcript())
        copy = self.outside/'receipt.json'
        copy.write_bytes((attempt/'T19-01-required_skip.json').read_bytes())
        swap_to_symlink(attempt/'T19-01-required_skip.json', copy)
        with self.assertRaises(ContractError):
            self.collect(attempt)
        attempt = self.publish(self.transcript(), name='raced')
        (self.outside/'suite.log').write_bytes((attempt/s.LOG).read_bytes())
        inode = os.stat(attempt/s.LOG).st_ino
        original, swapped = s._read_fd, []

        def swap_during_read(fd, limit):
            data = original(fd, limit)
            if os.fstat(fd).st_ino == inode and not swapped:
                swap_to_symlink(attempt/s.LOG, self.outside/'suite.log')
                swapped.append(True)
            return data
        with mock.patch.object(s, '_read_fd', swap_during_read), self.assertRaisesRegex(ContractError, 'changed during read'):
            self.collect(attempt)
        self.assertEqual(swapped, [True])

    def test_T19_05_positive_collector_reads_owned_regular_files(self):
        attempt = self.publish(self.transcript())
        self.assertEqual(self.collect(attempt)['support'], 'incomplete')
        self.assertTrue(all(not (attempt/name).is_symlink() for name in os.listdir(attempt)))

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(s, 'source_context', lambda: (self.catalog(), TOY_IDS)):
            code = s.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_T19_06_positive_cli_publish_and_check_with_pinned_history(self):
        log, history = self.root/'suite input.log', self.root/'history.json'
        log.write_bytes(self.transcript())
        history.write_text(json.dumps(EMPTY_HISTORY))
        common = ['--history', str(history), '--history-sha256', self.PIN]
        code, published = self.run_cli('publish', '--attempt', str(self.root/'cli'), '--log', str(log),
                                       '--attempt-id', 'placeholder-cli', '--exit-code', '0',
                                       '--argv-json', '["python3", "-B", "-m", "unittest"]', *common)
        self.assertEqual((code, published['support'], published['execution']['T19-01-required_skip']),
                         (1, 'incomplete', 'passed'))
        code, checked = self.run_cli('check', '--receipts', str(self.root/'cli'), *common)
        self.assertEqual((code, checked), (1, published))

    def test_T19_06_adverse_cli_history_unavailable_or_missing_is_not_green(self):
        log = self.root/'suite.log'
        log.write_bytes(self.transcript())
        code, result = self.run_cli('publish', '--attempt', str(self.root/'cli'), '--log', str(log),
                                    '--attempt-id', 'placeholder-cli', '--exit-code', '0',
                                    '--argv-json', '["python3"]', '--history-unavailable')
        self.assertEqual((code, result['freshness'], result['execution']['T19-01-required_skip']),
                         (1, 'history_unavailable', 'error'))
        code, result = self.run_cli('check', '--receipts', str(self.root/'cli'), '--history-unavailable',
                                    '--history-sha256', self.PIN)
        self.assertEqual((code, result['support']), (1, 'error'))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            s.main(['check', '--receipts', str(self.root/'cli')])
        symlinked = self.root/'history-link.json'
        (self.outside/'history.json').write_text(json.dumps(EMPTY_HISTORY))
        symlinked.symlink_to(self.outside/'history.json')
        code, result = self.run_cli('check', '--receipts', str(self.root/'cli'), '--history', str(symlinked),
                                    '--history-sha256', self.PIN)
        self.assertEqual((code, result['support']), (1, 'error'))

    def test_T19_01_adverse_cli_publish_partial_transcript_is_error(self):
        log = self.root/'partial.log'
        log.write_bytes(self.transcript(extra=False))
        history = self.root/'history.json'
        history.write_text(json.dumps(EMPTY_HISTORY))
        code, result = self.run_cli('publish', '--attempt', str(self.root/'cli'), '--log', str(log),
                                    '--attempt-id', 'placeholder-cli', '--exit-code', '0', '--argv-json', '["python3"]',
                                    '--history', str(history), '--history-sha256', self.PIN)
        self.assertEqual((code, result['execution']['T19-01-required_skip']), (1, 'error'))

    def test_collector_cli_inventory_is_the_source_bound_suite(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(s.main(['inventory']), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result['expected_inventory'], s.source_context(ROOT)[1])
        self.assertEqual(result['sha256'], scientific_hash(result['expected_inventory']))


MUTANTS = {
    'publisher inventory from transcript': (
        "    parsed = collect_unittest(log.decode('utf-8'), expected)\n",
        "    parsed = collect_unittest(log.decode('utf-8'), sorted({m.group(2) for m in START.finditer(log.decode('utf-8'))}))\n",
        ['Collector.test_T19_01_adverse_removed_expected_test_stays_incomplete_in_publisher_and_collector']),
    'collector inventory from transcript': (
        "        parsed = collect_unittest(artifacts[LOG].decode('utf-8'), expected)\n",
        "        parsed = collect_unittest(artifacts[LOG].decode('utf-8'), sorted({m.group(2) for m in START.finditer(artifacts[LOG].decode('utf-8'))}))\n",
        ['Collector.test_T19_01_adverse_removed_expected_test_stays_incomplete_in_publisher_and_collector']),
    'publisher treats unavailable history as fresh': (
        "        freshness = 'attempt history unavailable; freshness unproven'\n", "        freshness = None\n",
        ['Collector.test_T19_06_adverse_unavailable_or_historical_transcript_not_fresh']),
    'historical bytes accepted as fresh': (
        "        require(not old_hashes & set(run['artifacts'].values()), 'historical artifact bytes claimed fresh')\n",
        "        pass\n", ['FreshVsReuse.test_T19_06_adverse_historical_evidence_claimed_fresh_rejected']),
    'collector credits without history': (
        "        if attempts is None:\n            continue\n",
        "        if attempts is None:\n            credited.add(record['case_id'])\n            continue\n",
        ['Collector.test_T19_06_adverse_unavailable_or_historical_transcript_not_fresh']),
    'path read follows symlinks': (
        '    """Bytes of root/path; any symlink component, non-regular file, size or identity change refuses."""\n',
        '    """Bytes of root/path; any symlink component, non-regular file, size or identity change refuses."""\n'
        '    return (Path(root) / path).read_bytes()\n',
        ['UploadMissing.test_T19_05_adverse_replaced_symlinked_or_special_uploads_refused']),
    'read identity not rechecked': (
        "        if not _identity(after) == _identity(opened) == _identity(named) or len(data) != opened.st_size:\n",
        "        if False:\n", ['UploadMissing.test_T19_05_adverse_replaced_symlinked_or_special_uploads_refused']),
    'absolute argv path not rooted': (
        "        raise ContractError('argv path escapes owned root: ' + value)\n", "        return Path(value)\n",
        ['RunnerEscape.test_T19_04_adverse_argv_paths_must_match_admitted_scope_and_outputs']),
    'argv outputs not bound to declared outputs': (
        "        require(sorted(map(str, bound['output'])) == sorted(map(str, declared)),\n"
        "                'argv outputs do not match declared outputs')\n", "        pass\n",
        ['RunnerEscape.test_T19_04_adverse_argv_paths_must_match_admitted_scope_and_outputs']),
    'inline trigger mapping ignored': (
        "            require(value in (None, '{}', 'null', '~'), 'unsupported inline trigger value: ' + line.strip())\n",
        "            pass\n", ['PathFilter.test_T19_02_adverse_unsupported_forms_refuse_and_restrictions_report']),
    'quoted filter key skipped': (
        "        require(match is not None, 'unsupported trigger filter syntax: ' + line.strip())\n",
        "        if match is None:\n            continue\n",
        ['PathFilter.test_T19_02_adverse_unsupported_forms_refuse_and_restrictions_report']),
}


class Mutants(unittest.TestCase):
    def test_guard_removal_mutants_are_killed(self):
        """Each mutant runs only the control that must kill it, keeping the suite cheap inside version-check."""
        source = (ROOT/'ops/ci/science_suite.py').read_text()
        here = sys.modules[__name__]
        for name, (old, new, targets) in MUTANTS.items():
            with self.subTest(name):
                self.assertEqual(source.count(old), 1, name)
                module = types.ModuleType('science_suite_mutant')
                module.__file__ = str(ROOT/'ops/ci/science_suite.py')
                saved = list(sys.path)
                try:
                    exec(compile(source.replace(old, new), module.__file__ + ' [mutant]', 'exec'), module.__dict__)
                finally:
                    sys.path[:] = saved
                suite = unittest.TestSuite(unittest.TestLoader().loadTestsFromName(target, here) for target in targets)
                with mock.patch.object(here, 's', module):
                    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
                self.assertTrue(result.failures or result.errors, name + ' survived')


if __name__ == '__main__':
    unittest.main()
