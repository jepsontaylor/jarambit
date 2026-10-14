"""Operator-bound generic caller controls; synthetic fixture authority only.

The admitted launcher supplies a freshly built Rust bridge and its observed
hash. Source snapshots and provider streams remain in a new owned test output.
These unit approvals do not establish real-candidate B/C/D qualification.
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
import uuid
from unittest.mock import patch

from assurance.reporting import blocks, claims
from assurance.testing.contracts import raw_hash, scientific_hash
from ops.ci import claim_admission, rs_verdicts

ROOT = Path(__file__).resolve().parents[3]
REGISTRATION = {'candidate_id': 'fixture-A', 'claim_id': 'claim-a',
                'mass_scope': 'RS-v2_soft80_70_targets', 'requested_class': 'software_contract'}
SOURCE_PATHS = ('Cargo.lock', 'rust-toolchain.toml', 'crates/evidence/Cargo.toml',
                'crates/evidence/src/lib.rs', 'crates/evidence/src/identity.rs',
                'crates/evidence/src/assurance.rs', 'crates/evidence/examples/claim_report.rs',
                'assurance/registry/trusted-bootstrap.v1.json',
                'assurance/reporting/claims.py', 'assurance/reporting/blocks.py',
                'ops/ci/rs_verdicts.py', 'ops/ci/check_claims.py', 'ops/ci/claim_admission.py',
                'assurance/testing/contracts.py', 'metrics/global_metric.py')


def wire(value):
    return (blocks.canonical_body(value) + '\n').encode('utf-8')


class OperatorAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get('JARAMBIT_SCIENCE_CLAIM_UNIT_BIN')
        expected = os.environ.get('JARAMBIT_SCIENCE_CLAIM_UNIT_BINARY_SHA256')
        output = os.environ.get('JARAMBIT_SCIENCE_CLAIM_UNIT_OUTPUT')
        if not binary or not expected or not output:
            raise RuntimeError('admitted Rust bridge/hash/owned output required; never skipped')
        cls.binary = Path(binary)
        if raw_hash(cls.binary.read_bytes()) != expected:
            raise RuntimeError('admitted Rust unit binary changed')
        cls.output = Path(output)
        if not cls.output.is_absolute():
            raise RuntimeError('absolute owned unit output required')
        corpus = claims.decode(claims.read_bounded(ROOT/'assurance/registry/t02_fixtures.json', corpus=True), corpus=True)
        cls.fixed = next(row for row in corpus['original_controls'] if row['id'] == 'exact-subject-current-role')

    def setUp(self):
        self.directory = self.output/(self._testMethodName+'-'+uuid.uuid4().hex)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.installed = self.directory/'claim_report'
        shutil.copyfile(self.binary, self.installed)
        self.installed.chmod(0o700)
        # Preserved byte-identical source snapshots make mutation controls safe
        # for the production checkout. They are explicitly unit-only D inputs.
        sources = {}
        for name in SOURCE_PATHS:
            target = self.directory/'source-snapshot'/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target)
            sources[str(target)] = raw_hash(target.read_bytes())
        source_sha = scientific_hash({'files': sources, 'absences': []})
        recipe = {'schema': 1, 'stage': 'source_bound_build', 'source_closure_sha256': source_sha,
                  'source_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                  'build_argv': ['/home/ubuntu/.rustup/toolchains/1.85.1-x86_64-unknown-linux-gnu/bin/cargo',
                                 'build', '--release', '--offline', '--locked', '--jobs', '1',
                                 '-p', 'jarambit-evidence', '--example', 'claim_report', '--message-format=json'],
                  'build_environment': {'CARGO_INCREMENTAL': '0', 'CARGO_BUILD_JOBS': '1'},
                  'compiler_files': {str(p): raw_hash(p.read_bytes()) for p in [Path('/home/ubuntu/.rustup/toolchains/1.85.1-x86_64-unknown-linux-gnu/bin/rustc')]},
                  'dependency_files': {str(ROOT/'Cargo.lock'): raw_hash((ROOT/'Cargo.lock').read_bytes())}}
        self.recipe = self.directory/'build-recipe.json'
        self.recipe.write_bytes(wire(recipe))
        files = self.fixed['files_utf8']
        request = files['request'].encode('utf-8')
        authority = claims.decode(files['authority'].encode('utf-8'))
        pin = claims.decode(files['caller_pin'].encode('utf-8'))
        self.registry = self.directory/'registry.json'
        self.registry.write_bytes((ROOT/'assurance/registry/current.v1.json').read_bytes())
        self.policy = self.directory/'reporting-policy.json'
        self.policy.write_bytes((ROOT/'assurance/registry/reporting-policy.v1.json').read_bytes())
        self.bootstrap = self.directory/'bootstrap.json'
        self.bootstrap.write_bytes((ROOT/'assurance/registry/trusted-bootstrap.v1.json').read_bytes())
        binary_sha = raw_hash(self.installed.read_bytes())
        authority['roots']['resolver_source_build_recipe'] = {'raw_utf8': self.recipe.read_text(), 'raw_sha256': raw_hash(self.recipe.read_bytes())}
        authority['roots']['actual_build'] = {'stage': 'runtime_admitted', 'source_closure_sha256': source_sha, 'binary_sha256': binary_sha}
        self.request = self.directory/'request.json'; self.request.write_bytes(request)
        self.authority = self.directory/'authority.json'; self.authority.write_bytes(wire(authority))
        pin.update(stage='runtime_admitted', authority_raw_sha256=raw_hash(self.authority.read_bytes()),
                   source_build_recipe_raw_sha256=raw_hash(self.recipe.read_bytes()),
                   actual_resolver_source_closure_sha256=source_sha, actual_resolver_binary_sha256=binary_sha)
        requirements = {}
        for i, record in enumerate(authority['approved_requirements']):
            path = self.directory/f'requirement-{i}.toml'; path.write_text(record['raw_utf8'])
            requirements[str(path)] = raw_hash(path.read_bytes())
        data = {'schema': 1, 'pin': pin, 'binary_path': str(self.installed), 'source_files': sources,
                'source_absences': [], 'registry_path': str(self.registry), 'policy_path': str(self.policy),
                'bootstrap_path': str(self.bootstrap), 'source_build_recipe_path': str(self.recipe),
                'requirement_files': requirements, 'output_dir': str(self.directory/'provider-streams')}
        self.approval = wire(data)
        self.expected_sha = raw_hash(self.approval)  # trusted unit operator, before any submitted mutation
        (self.directory/'operator-admission.json').write_bytes(self.approval)
        self.context = self.context_for(self.approval)
        _, _, _, descriptor = claims.admission_binding(request, self.authority.read_bytes(), self.context.caller)
        # Keep the literal scientific/mass/metric oracle from the sealed corpus;
        # rematerialize only its explicitly allowed runtime identity fields.
        expected_report = claims.decode(files['expected_canonical_body'].encode('utf-8'))
        expected_report.update(schema='jarambit.claim_report.v2', binding_stage='runtime_admitted',
                               input_sha256=scientific_hash(descriptor), resolver_source_sha256=source_sha,
                               resolver_binary_sha256=binary_sha)
        self.document = self.directory/'document.md'
        self.document.write_text(blocks.write_block('claim-a', expected_report)+'\n')

    def context_for(self, raw, *, approved_sha=None, registration=None):
        return claim_admission.context_from_operator_approval(
            raw, approved_sha256=self.expected_sha if approved_sha is None else approved_sha,
            approved_registration=REGISTRATION if registration is None else registration,
            request_path=self.request, authority_path=self.authority)

    def run_checker(self, context, root=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = claim_admission.main(['--root', str(root or self.directory)], context=context)
        path = self.directory/('checker-'+uuid.uuid4().hex+'.txt')
        path.write_text(output.getvalue())
        return code, output.getvalue()

    def healthy(self):
        self.assertEqual(self.run_checker(self.context)[0], 0)
        resolution = self.context.last_resolution.output
        self.assertEqual(resolution['verdict'], self.fixed['expected_provider']['Resolution']['verdict'])
        self.assertFalse(resolution['release_authorized'])
        self.assertEqual(self.context.last_report['physical_validation'], 'not_performed')
        self.assertIsNone(self.context.last_report['product_qualification'])

    def refused_after_mutation(self, reason):
        code, output = self.run_checker(self.context)
        self.assertEqual(code, 2, output); self.assertIn(reason, output)
        self.assertIsNone(self.context.last_resolution); self.assertIsNone(self.context.last_report)

    def test_healthy_actual_bridge_and_literal_oracle(self):
        self.healthy()

    def test_missing_context_does_not_borrow_global_or_environment(self):
        self.healthy()
        with patch.object(rs_verdicts, '_DEFAULT_CONTEXT', self.context), patch.dict(os.environ, {'JARAMBIT_CALLER_ADMISSION': str(self.directory/'operator-admission.json')}):
            code, output = self.run_checker(None)
        self.assertEqual(code, 2); self.assertIn('independent_caller_admission_unavailable', output)

    def test_independent_approval_hash_required(self):
        self.healthy()
        with self.assertRaisesRegex(claims.Refusal, 'caller_approval_bytes_mismatch'):
            self.context_for(self.approval, approved_sha='0'*64)

    def test_independent_registration_required(self):
        self.healthy()
        with self.assertRaisesRegex(claims.Refusal, 'caller_registration_mismatch'):
            self.context_for(self.approval, registration={**REGISTRATION, 'candidate_id': 'C10a'})

    def test_self_rehashed_submitted_admission_cannot_change_registration(self):
        self.healthy()
        data = claims.decode(self.approval); data['pin']['registration']['candidate_id'] = 'C10a'
        changed = wire(data)
        with self.assertRaisesRegex(claims.Refusal, 'caller_approval_bytes_mismatch'):
            self.context_for(changed)
        with self.assertRaisesRegex(claims.Refusal, 'caller_registration_mismatch'):
            self.context_for(changed, approved_sha=raw_hash(changed))

    def test_stale_source_snapshot_withdraws_prior_result(self):
        self.healthy()
        path = Path(next(iter(self.context.caller.data['source_files'])))
        path.write_bytes(path.read_bytes()+b'\n# changed unit snapshot\n')
        self.refused_after_mutation('admitted_source_or_requirement_changed')

    def test_changed_binary_withdraws_prior_result(self):
        self.healthy(); self.installed.write_bytes(self.installed.read_bytes()+b'changed-unit-binary')
        self.refused_after_mutation('admitted_root_or_binary_changed')

    def test_missing_binary_withdraws_prior_result(self):
        self.healthy(); self.installed.rename(self.directory/'preserved-missing-binary')
        self.refused_after_mutation('missing_admitted_input')

    def test_changed_policy_root_withdraws_prior_result(self):
        self.healthy(); self.policy.write_bytes(self.policy.read_bytes()+b'\n')
        self.refused_after_mutation('admitted_root_or_binary_changed')

    def test_changed_build_recipe_withdraws_prior_result(self):
        self.healthy(); self.recipe.write_bytes(self.recipe.read_bytes()+b'\n')
        self.refused_after_mutation('admitted_root_or_binary_changed')

    def test_changed_authority_cannot_self_approve(self):
        self.healthy()
        value = claims.decode(self.authority.read_bytes()); value['bootstrap_id'] = 'unapproved-entry'
        self.authority.write_bytes(wire(value))
        self.refused_after_mutation('untrusted_authority_root')

    def test_document_root_does_not_select_authority_or_candidate(self):
        self.healthy(); other = self.directory/'submitted-documents'; other.mkdir()
        report = copy.deepcopy(self.context.last_report); report['candidate_id'] = 'C10a'
        (other/'document.md').write_text(blocks.write_block('claim-a', report)+'\n')
        self.assertEqual(self.run_checker(self.context, other)[0], 1)
        self.assertEqual(self.context.last_report['candidate_id'], 'fixture-A')

    def test_cli_override_refused_without_reusing_resolution(self):
        self.healthy()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            claim_admission.main(['--resolver-binary', str(self.installed)], context=self.context)
        self.assertEqual(raised.exception.code, 2); self.assertIsNone(self.context.last_resolution)

    def test_unknown_context_cannot_select_provider(self):
        self.healthy()
        code, output = self.run_checker({'authority': str(self.authority)})
        self.assertEqual(code, 2); self.assertIn('independent_caller_admission_required', output)
