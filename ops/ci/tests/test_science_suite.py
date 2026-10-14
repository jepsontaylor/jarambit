"""T19 paired positive/adverse controls (run: python3 -B -m unittest discover -s ops/ci/tests -p test_science_suite.py -v).

Synthetic software contracts only: neutral placeholder identities and toy files, no product qualification.
Test names test_T19_NN_<control>_* map to frozen case IDs; T19-07/08/09 exercise interfaces whose whole
criteria stay not_run upstream.
"""
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'ops'/'ci'))
import science_suite as s  # noqa: E402
from assurance.testing.contracts import ContractError, raw_hash, scientific_hash, strict_loads, validate_case  # noqa: E402


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


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)


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
            root = Path(temporary)
            for name in ('assurance/testing/policy.json', 'assurance/policies/release-v1.json'):
                (root/name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, root/name)
            self.assertEqual(s.load_release_policy(root), s.load_release_policy(ROOT))
            with (root/'assurance/policies/release-v1.json').open('ab') as output:
                output.write(b'\n')
            with self.assertRaisesRegex(ContractError, 'S01 pin'):
                s.load_release_policy(root)


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
    def record(self, **changes):
        (self.root/'work').mkdir(exist_ok=True)
        return {'argv': ['/usr/bin/touch', str(self.root/'executed')], 'cwd': 'work',
                'env': {'PYTHONDONTWRITEBYTECODE': '1'}, 'outputs': ['work/out.json'], **changes}

    def test_T19_04_positive_owned_argv_validated_never_executed(self):
        result = s.check_command(self.record(), self.root, {'/usr/bin/touch'})
        self.assertFalse(result['executed'])
        self.assertEqual(result['outputs'], [str(self.root/'work/out.json')])
        self.assertFalse((self.root/'executed').exists())

    def test_T19_04_adverse_shell_traversal_and_symlink_escapes_rejected(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, outside)
        (self.root/'link').symlink_to(outside, target_is_directory=True)
        programs = {'/usr/bin/touch', '/bin/bash', '/usr/bin/python3'}
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
                s.check_command(self.record(**change), self.root, programs)
        self.assertEqual(list(outside.iterdir()), [])


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


class FreshVsReuse(unittest.TestCase):
    CURRENT = toy_digest('current input')
    HISTORY = {'attempt-001': {'input_sha256': toy_digest('current input'), 'artifacts': {'log': toy_digest('old log')}}}

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

    def test_T19_06_adverse_historical_evidence_claimed_fresh_rejected(self):
        rejected = {
            'relabeled attempt': self.run_record(attempt_id='attempt-001'),
            'copied artifact': self.run_record(artifacts={'log': toy_digest('old log')}),
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
    def transcript(self, adverse=ok):
        return toy_transcript({'test_T19_01_positive_toy': ok, 'test_T19_01_adverse_toy': adverse,
                               'test_T19_07_positive_toy': ok, 'test_T19_07_adverse_toy': ok}).encode()

    def publish(self, log):
        attempt = self.root/'attempt'
        s.publish_attempt(attempt, s.build_catalog(ROOT), log, ['python3', '-B', '-m', 'unittest'],
                          0, 'placeholder-attempt')
        return attempt

    def test_collector_derives_passes_from_transcript_and_keeps_denominator(self):
        attempt = self.publish(self.transcript())
        result = s.collect(s.build_catalog(ROOT), attempt)
        self.assertEqual(result['denominator'], 10)
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
        self.assertEqual(s.collect(s.build_catalog(ROOT), attempt)['execution']['T19-01-required_skip'], 'failed')
        shutil.rmtree(attempt)
        attempt = self.publish(self.transcript())
        (attempt/'T19-01-required_skip.json').unlink()
        self.assertIn('T19-01-required_skip', s.collect(s.build_catalog(ROOT), attempt)['missing'])
        shutil.rmtree(attempt)
        attempt = self.publish(self.transcript())
        os.chmod(attempt/'suite.log', 0o644)
        with (attempt/'suite.log').open('ab') as output:
            output.write(b'\n')
        with self.assertRaisesRegex(ContractError, 'artifact integrity'):
            s.collect(s.build_catalog(ROOT), attempt)
        for case_id in ('T19-02-path_filter', 'T19-08-render_finish_metadata'):
            shutil.rmtree(attempt)
            attempt = self.publish(self.transcript())
            path = attempt/(case_id + '.json')
            forged = strict_loads(path.read_bytes(), s.LIMITS)
            forged.update(execution='passed', finding='rejected_within_scope', exit_code=0, reason=None,
                          controls={'positive': 'passed', 'adverse': 'passed'},
                          counts={'expected': 2, 'passed': 2, 'failed': 0, 'error': 0, 'not_run': 0})
            path.unlink()
            path.write_text(json.dumps(forged))
            with self.subTest(case_id), self.assertRaises(ContractError):
                s.collect(s.build_catalog(ROOT), attempt)


if __name__ == '__main__':
    unittest.main()
