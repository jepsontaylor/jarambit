"""Bounded report wires and an explicit caller-admitted Rust provider boundary.

This module validates identities and presentation. It never evaluates scientific
thresholds and never obtains approval from a document, payload or environment.
"""
from dataclasses import dataclass
import copy
import datetime
import json
import os
from pathlib import Path
import subprocess
import uuid

from assurance.testing.contracts import ContractError, digest, finite, identifier, raw_hash, scientific_hash, strict_loads
from .blocks import LIMITS, canonical_body

REQUEST_KEYS = {'schema', 'claim', 'expected', 'artifacts', 'observations', 'reviews'}
AUTHORITY_KEYS = {'schema', 'bootstrap_id', 'provider', 'approved_inventory', 'approved_requirements', 'approved_reviews', 'roots', 'report_context'}
CONTEXT_KEYS = {'candidate_id', 'trusted_candidate_id', 'subject_sha256', 'current_registry', 'requested_evidence_class', 'physical_validation', 'mass_scope', 'G1'}
REPORT_KEYS = {'schema', 'binding_stage', 'candidate_id', 'claim_id', 'group', 'input_sha256', 'mass', 'metrics', 'physical_validation', 'policy_sha256', 'product_qualification', 'publication_eligible', 'registry_sha256', 'release_authorized', 'requirement_refs', 'resolver_binary_sha256', 'resolver_source_sha256', 'software_support', 'subject_id', 'subject_sha256', 'verdict'}
BINDING_KEYS = {'request_raw_sha256', 'authority_raw_sha256', 'compiled_trust_dataset_raw_sha256', 'trusted_entry_raw_sha256', 'registry_raw_sha256', 'reporting_policy_raw_sha256', 'resolver_source_build_recipe_raw_sha256', 'actual_resolver_source_closure_sha256', 'actual_resolver_binary_sha256'}
PIN_KEYS = {'schema', 'stage', 'bootstrap_id', 'approved_inventory_reference', 'approved_review_refs_and_scopes', 'approved_trust_entry_raw_sha256', 'authority_raw_sha256', 'compiled_trust_dataset_raw_sha256', 'policy_raw_sha256', 'registration', 'registry_raw_sha256', 'requirements_raw_sha256', 'runtime_admission', 'source_build_recipe_raw_sha256', 'actual_resolver_source_closure_sha256', 'actual_resolver_binary_sha256'}
ADMISSION_KEYS = {'schema', 'pin', 'binary_path', 'source_files', 'source_absences', 'registry_path', 'policy_path', 'bootstrap_path', 'source_build_recipe_path', 'requirement_files', 'output_dir'}
BUILD_RECIPE_KEYS = {'schema', 'stage', 'source_closure_sha256', 'source_head', 'build_argv', 'build_environment', 'compiler_files', 'dependency_files'}
CORPUS_LIMITS = {**LIMITS, 'max_bytes': 8_388_608}
_CALLER_TOKEN = object()


class Refusal(ValueError):
    def __init__(self, reason):
        self.reason = str(reason)
        super().__init__(self.reason)


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def closed(value, keys, reason, optional=()):
    require(type(value) is dict and set(value) <= keys | set(optional) and keys <= set(value), reason)
    return value


def decode(raw, *, corpus=False):
    try:
        return strict_loads(raw, CORPUS_LIMITS if corpus else LIMITS)
    except (ContractError, UnicodeError, OverflowError, RecursionError) as error:
        raise Refusal(f'strict_wire: {error}') from error


def read_bounded(path, *, corpus=False):
    limit = CORPUS_LIMITS['max_bytes'] if corpus else LIMITS['max_bytes']
    try:
        with Path(path).open('rb') as f:
            raw = f.read(limit + 1)
    except OSError as error:
        raise Refusal(f'missing_input: {error}') from error
    require(len(raw) <= limit, 'payload_too_large')
    return raw


def raw_file_hash(path):
    import hashlib
    h = hashlib.sha256()
    try:
        with Path(path).open('rb') as f:
            for part in iter(lambda: f.read(1 << 20), b''):
                h.update(part)
    except OSError as error:
        raise Refusal(f'missing_admitted_input: {error}') from error
    return h.hexdigest()


def content_reference(value):
    closed(value, {'id', 'revision', 'sha256'}, 'invalid_content_reference')
    try:
        identifier(value['id']); identifier(value['revision']); digest(value['sha256'])
    except (ContractError, UnicodeError) as error:
        raise Refusal('invalid_content_reference') from error
    return value


def raw_root(value):
    closed(value, {'raw_utf8', 'raw_sha256'}, 'invalid_raw_root')
    require(type(value['raw_utf8']) is str, 'invalid_raw_root')
    try:
        raw = value['raw_utf8'].encode('utf-8')
        require(raw_hash(raw) == digest(value['raw_sha256']), 'raw_root_hash_mismatch')
    except (ContractError, UnicodeError) as error:
        raise Refusal('invalid_raw_root') from error
    decode(raw)
    return raw


def validate_request(value):
    closed(value, REQUEST_KEYS, 'unknown_request_field')
    require(type(value['schema']) is int and value['schema'] == 2, 'request_schema')
    for key in ['artifacts', 'observations', 'reviews']:
        require(type(value[key]) is list, 'request_array_required')
    for artifact in value['artifacts']:
        closed(artifact, {'reference', 'bytes_utf8', 'kind'}, 'artifact_wire')
        content_reference(artifact['reference'])
        require(type(artifact['bytes_utf8']) is str and artifact['kind'] in ['source', 'solver_output', 'acquisition', 'synthetic'], 'artifact_wire')
    # Nested scientific structs are parsed by accepted S01 Rust deny_unknown_fields.
    require(type(value['claim']) is dict and type(value['expected']) is dict, 'request_claim_inventory')
    return value


def validate_registry(value):
    closed(value, {'schema', 'revision', 'candidates', 'candidate_subjects', 'current_by_scope', 'class'}, 'registry_wire')
    require(type(value['schema']) is int and value['schema'] == 1 and type(value['revision']) is int and value['revision'] > 0, 'registry_schema')
    require(type(value['class']) is str and value['class'], 'registry_class')
    for key in ['candidates', 'candidate_subjects', 'current_by_scope']:
        require(type(value[key]) is dict and value[key], 'registry_wire')
        for name, item in value[key].items():
            identifier(name)
            if key == 'candidate_subjects':digest(item)
            else:identifier(item)
    require(set(value['candidate_subjects']) <= set(value['candidates']) and set(value['current_by_scope'].values()) <= set(value['candidate_subjects']), 'registry_subject_registration')
    return value


def validate_build_recipe(value, source_sha256):
    closed(value, BUILD_RECIPE_KEYS, 'unbuilt_source_or_binary')
    require(type(value['schema']) is int and value['schema'] == 1 and value['stage'] == 'source_bound_build', 'unbuilt_source_or_binary')
    require(value['source_closure_sha256'] == source_sha256, 'build_source_identity_mismatch')
    require(type(value['source_head']) is str and len(value['source_head']) == 40 and all(c in '0123456789abcdef' for c in value['source_head']), 'build_source_head')
    require(type(value['build_argv']) is list and value['build_argv'] and all(type(x) is str and x for x in value['build_argv']), 'build_argv_required')
    require(type(value['build_environment']) is dict and value['build_environment'] and all(type(k) is str and (v is None or type(v) is str) for k,v in value['build_environment'].items()), 'build_environment_required')
    for key in ['compiler_files','dependency_files']:
        require(type(value[key]) is dict and value[key], 'build_dependency_closure_required')
        for path, sha in value[key].items():require(Path(path).is_absolute(), 'admitted_path_required');digest(sha)
    return value


def validate_authority(value):
    closed(value, AUTHORITY_KEYS, 'unknown_authority_field')
    require(type(value['schema']) is int and value['schema'] == 2, 'authority_schema')
    identifier(value['bootstrap_id'])
    require(value['provider'] == 'explicit_local_synthetic_fixture_trust_not_external_authentication', 'untrusted_authority_root')
    require(type(value['approved_requirements']) is list and type(value['approved_reviews']) is list, 'authority_arrays')
    for x in [value['approved_inventory'], *value['approved_requirements']]:
        closed(x, {'reference', 'raw_utf8'}, 'authority_raw_record')
        content_reference(x['reference']); require(type(x['raw_utf8']) is str, 'authority_raw_record')
    for x in value['approved_reviews']:
        closed(x, {'reference', 'approved_reviewer', 'approved_scope', 'raw_utf8'}, 'authority_review_record')
        content_reference(x['reference']); identifier(x['approved_reviewer'])
        closed(x['approved_scope'], {'group', 'requirement_set'}, 'authority_review_scope')
        require(type(x['raw_utf8']) is str, 'authority_review_record')
    roots = closed(value['roots'], {'registry', 'reporting_policy', 'resolver_source_build_recipe', 'actual_build'}, 'authority_roots')
    for key in ['registry', 'reporting_policy', 'resolver_source_build_recipe']:
        raw_root(roots[key])
    closed(roots['actual_build'], {'stage', 'source_closure_sha256', 'binary_sha256'}, 'actual_build_wire')
    context = closed(value['report_context'], CONTEXT_KEYS, 'report_context_wire', {'historical_D1'})
    for key in ['candidate_id', 'trusted_candidate_id', 'requested_evidence_class', 'physical_validation', 'mass_scope']:
        identifier(context[key])
    digest(context['subject_sha256'])
    require(type(context['current_registry']) is dict and type(context['G1']) is dict, 'report_context_wire')
    require(set(context['G1']) <= {'solid_tip_sf_nodal_max', 'plate_tipsub_screen_sf', 'twist_tipzone_sf_strict', 'spg', 'aes_score', 'mass_g', 'seq_ratio'}, 'metric_context_keys')
    if 'historical_D1' in context:
        closed(context['historical_D1'], {'label', 'strict_lateral_N', 'strict_tip_sf', 'seq_ratio', 'promote_eligible', 'scope'}, 'historical_context_wire')
    return value


class TrustedCaller:
    """Opaque out-of-band D. The expected bytes/registration are caller authority.

    A JSON file cannot approve itself. CLI/env/document roots never call this
    constructor with expectations discovered from the submitted data.
    """
    def __init__(self, token, raw):
        require(token is _CALLER_TOKEN, 'caller_approval_required')
        self.__raw = bytes(raw)

    @classmethod
    def from_approved_bytes(cls, raw, approved_raw_sha256, approved_registration):
        require(type(raw) is bytes and raw_hash(raw) == digest(approved_raw_sha256), 'caller_approval_bytes_mismatch')
        data = closed(decode(raw), ADMISSION_KEYS, 'caller_admission_wire')
        pin = closed(data['pin'], PIN_KEYS, 'caller_pin_wire')
        require(data['schema'] == 1 and type(data['schema']) is int, 'caller_admission_schema')
        require(pin['stage'] == 'runtime_admitted' and pin['schema'] == 1 and type(pin['schema']) is int, 'unbuilt_source_or_binary')
        registration = closed(pin['registration'], {'candidate_id', 'claim_id', 'mass_scope', 'requested_class'}, 'registration_wire')
        require(registration == approved_registration, 'caller_registration_mismatch')
        for value in registration.values(): identifier(value)
        for key in ['actual_resolver_source_closure_sha256', 'actual_resolver_binary_sha256', 'authority_raw_sha256', 'registry_raw_sha256', 'policy_raw_sha256', 'compiled_trust_dataset_raw_sha256', 'approved_trust_entry_raw_sha256', 'source_build_recipe_raw_sha256']:
            digest(pin[key])
        require(type(data['source_files']) is dict and data['source_files'], 'source_closure_missing')
        require(type(data['source_absences']) is list and all(type(p) is str for p in data['source_absences']), 'source_absences_wire')
        require(type(data['requirement_files']) is dict and data['requirement_files'], 'requirements_closure_missing')
        for values in [data['source_files'], data['requirement_files']]:
            for path, sha in values.items():
                identifier(path); digest(sha)
                require(Path(path).is_absolute(), 'admitted_path_required')
        require(all(Path(p).is_absolute() for p in data['source_absences']), 'admitted_path_required')
        for key in ['binary_path', 'registry_path', 'policy_path', 'bootstrap_path', 'source_build_recipe_path', 'output_dir']:
            require(type(data[key]) is str and Path(data[key]).is_absolute(), 'admitted_path_required')
        require(scientific_hash({'files': data['source_files'], 'absences': data['source_absences']}) == pin['actual_resolver_source_closure_sha256'], 'source_closure_identity_mismatch')
        return cls(_CALLER_TOKEN, raw)

    @property
    def data(self):
        return decode(self.__raw)

    @property
    def raw_sha256(self):
        return raw_hash(self.__raw)

    def verify_current(self):
        data = self.data; pin = data['pin']
        for path, sha in {**data['source_files'], **data['requirement_files']}.items():
            require(raw_file_hash(path) == sha, 'admitted_source_or_requirement_changed')
        for path in data['source_absences']:
            require(not Path(path).exists() and not Path(path).is_symlink(), 'admitted_initializer_or_config_added')
        for key, sha in [('binary_path', 'actual_resolver_binary_sha256'), ('registry_path', 'registry_raw_sha256'), ('policy_path', 'policy_raw_sha256'), ('bootstrap_path', 'compiled_trust_dataset_raw_sha256'), ('source_build_recipe_path', 'source_build_recipe_raw_sha256')]:
            require(raw_file_hash(data[key]) == pin[sha], 'admitted_root_or_binary_changed')
        return data


def admission_binding(request_raw, authority_raw, caller):
    require(type(caller) is TrustedCaller, 'caller_approval_required')
    data = caller.verify_current(); pin = data['pin']
    request = validate_request(decode(request_raw)); authority = validate_authority(decode(authority_raw))
    require(raw_hash(authority_raw) == pin['authority_raw_sha256'], 'untrusted_authority_root')
    require(authority['bootstrap_id'] == pin['bootstrap_id'], 'untrusted_authority_root')
    for key, expected in [('registry', 'registry_raw_sha256'), ('reporting_policy', 'policy_raw_sha256'), ('resolver_source_build_recipe', 'source_build_recipe_raw_sha256')]:
        require(authority['roots'][key]['raw_sha256'] == pin[expected], 'untrusted_policy_root' if key == 'reporting_policy' else 'untrusted_authority_root')
    build = authority['roots']['actual_build']
    require(build == {'stage': 'runtime_admitted', 'source_closure_sha256': pin['actual_resolver_source_closure_sha256'], 'binary_sha256': pin['actual_resolver_binary_sha256']}, 'unbuilt_or_untrusted_binary')
    validate_build_recipe(decode(raw_root(authority['roots']['resolver_source_build_recipe'])), pin['actual_resolver_source_closure_sha256'])
    require(request['claim']['id'] == pin['registration']['claim_id'], 'claim_registration_mismatch')
    bootstrap = decode(read_bounded(data['bootstrap_path'], corpus=True), corpus=True)
    entry = bootstrap['entries'].get(authority['bootstrap_id'])
    require(entry is not None, 'untrusted_authority_root')
    entry_sha = raw_hash((canonical_body(entry) + '\n').encode('utf-8'))
    require(entry_sha == pin['approved_trust_entry_raw_sha256'], 'untrusted_authority_root')
    for key in ['approved_inventory', 'approved_requirements', 'approved_reviews']:
        require(authority[key] == entry[key], 'untrusted_authority_root')
    binding = {'request_raw_sha256': raw_hash(request_raw), 'authority_raw_sha256': raw_hash(authority_raw), 'compiled_trust_dataset_raw_sha256': pin['compiled_trust_dataset_raw_sha256'], 'trusted_entry_raw_sha256': entry_sha, 'registry_raw_sha256': pin['registry_raw_sha256'], 'reporting_policy_raw_sha256': pin['policy_raw_sha256'], 'resolver_source_build_recipe_raw_sha256': pin['source_build_recipe_raw_sha256'], 'actual_resolver_source_closure_sha256': pin['actual_resolver_source_closure_sha256'], 'actual_resolver_binary_sha256': pin['actual_resolver_binary_sha256']}
    descriptor = {'schema': 2, 'binding_stage': 'runtime_admitted', **binding, 'trusted_caller_pin_raw_sha256': caller.raw_sha256, 'registration': pin['registration'], 'approved_inventory_reference': pin['approved_inventory_reference'], 'approved_review_refs_and_scopes': pin['approved_review_refs_and_scopes'], 'approved_requirement_refs': [x['reference'] for x in authority['approved_requirements']], 'report_context': authority['report_context'], 'source_files': data['source_files'], 'source_absences': data['source_absences'], 'requirement_files': data['requirement_files']}
    return request, authority, binding, descriptor


def validate_output(value, binding, claim_id):
    require(type(value) is dict, 'provider_output_wire')
    if value.get('kind') == 'refused':
        closed(value, {'schema', 'kind', 'reason'}, 'unknown_provider_output_field')
        require(type(value['schema']) is int and value['schema'] == 1 and type(value['reason']) is str and value['reason'], 'provider_output_wire')
        raise Refusal(value['reason'])
    closed(value, {'schema', 'kind', 'claim_id', 'verdict', 'publication_eligible', 'release_authorized', 'input_binding'}, 'unknown_provider_output_field')
    require(type(value['schema']) is int and value['schema'] == 1 and value['kind'] == 'resolved' and value['claim_id'] == claim_id, 'provider_output_wire')
    closed(value['input_binding'], BINDING_KEYS, 'provider_input_binding_wire')
    require(value['input_binding'] == binding, 'provider_input_identity_mismatch')
    verdict = value['verdict']; outcome = verdict.get('outcome') if type(verdict) is dict else None
    keys = {'requirement_set', 'group', 'outcome'}
    if outcome == 'fail': keys.add('reasons')
    elif outcome == 'incomplete': keys.add('missing')
    require(outcome in {'pass', 'fail', 'incomplete'}, 'provider_verdict_wire')
    closed(verdict, keys, 'provider_verdict_wire')
    for key in ['requirement_set', 'group']:identifier(verdict[key])
    if outcome != 'pass':
        reasons = verdict['reasons' if outcome == 'fail' else 'missing']
        require(type(reasons) is list and reasons and all(type(x) is str and x for x in reasons), 'provider_verdict_wire')
    require(type(value['publication_eligible']) is bool and value['publication_eligible'] == (outcome == 'pass'), 'provider_eligibility_wire')
    require(value['release_authorized'] is False, 'unapproved_release')
    return value


@dataclass(frozen=True)
class ProviderResult:
    output_raw: bytes
    input_sha256: str
    descriptor_raw: bytes
    execution_raw: bytes

    @property
    def output(self): return decode(self.output_raw)


def _immutable_stream(path, raw):
    with path.open('xb') as f:f.write(raw); f.flush(); os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)


def resolve_provider(request_path, authority_path, caller):
    request_raw = read_bounded(request_path); authority_raw = read_bounded(authority_path)
    request, authority, binding, descriptor = admission_binding(request_raw, authority_raw, caller)
    # Actual accepted Rust resolver, never an extracted or Python threshold stand-in.
    argv = [caller.data['binary_path'], str(Path(request_path).resolve()), str(Path(authority_path).resolve())]
    attempt=Path(caller.data['output_dir'])/('provider-'+uuid.uuid4().hex)
    attempt.mkdir(parents=True,exist_ok=False)
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    execution={'argv':argv,'cwd':os.getcwd(),'started_utc':started,'caller_raw_sha256':caller.raw_sha256,'input_sha256':scientific_hash(descriptor),'source_binary_binding':binding}
    _immutable_stream(attempt/'admission.json',(canonical_body(execution)+'\n').encode())
    try:
        with (attempt/'stdout.log').open('xb') as out, (attempt/'stderr.log').open('xb') as err:
            child = subprocess.run(argv, stdout=out, stderr=err, timeout=60, check=False)
            out.flush();os.fsync(out.fileno());err.flush();os.fsync(err.fileno())
    except (OSError, subprocess.TimeoutExpired) as error:
        execution.update(ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),execution='error',error=str(error),complete=False)
        execution['preserved_raw_streams']={name:raw_file_hash(attempt/name) for name in ['stdout.log','stderr.log'] if (attempt/name).is_file()}
        _immutable_stream(attempt/'failed.json',(canonical_body(execution)+'\n').encode())
        raise Refusal(f'provider_execution_error: {error}') from error
    with (attempt/'stdout.log').open('rb') as f:raw=f.read(LIMITS['max_bytes']+1)
    with (attempt/'stderr.log').open('rb') as f:stderr=f.read(LIMITS['max_bytes']+1)
    execution.update(ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit_code=child.returncode,stdout_sha256=raw_hash(raw),stderr_sha256=raw_hash(stderr))
    try:
        require(len(raw) <= LIMITS['max_bytes'] and len(stderr) <= LIMITS['max_bytes'], 'provider_output_limit')
        caller.verify_current()
        require(read_bounded(request_path) == request_raw and read_bounded(authority_path) == authority_raw, 'provider_input_changed')
        value = decode(raw)
        if child.returncode != 0:
            if child.returncode == 2 and type(value) is dict and value.get('kind') == 'refused':
                validate_output(value, binding, request['claim']['id'])
            raise Refusal(f'provider_failed:{child.returncode}')
        validate_output(value, binding, request['claim']['id'])
        require(value['verdict']['requirement_set'] == request['claim']['requirement_set'] and value['verdict']['group'] == request['claim']['group'], 'provider_scope_mismatch')
    except Exception as error:
        execution.update(execution='refused',reason=str(error),complete=False)
        _immutable_stream(attempt/'failed.json',(canonical_body(execution)+'\n').encode())
        raise
    execution.update(execution='resolved',complete=True,scientific_publication=False)
    terminal=(canonical_body(execution)+'\n').encode()
    _immutable_stream(attempt/'completion.json',terminal)
    return ProviderResult(raw, scientific_hash(descriptor), canonical_body(descriptor).encode('utf-8'),terminal)


def scope_errors(context, registry, registration):
    errors = []
    candidate = registration['candidate_id']
    if context['candidate_id'] != candidate or context['trusted_candidate_id'] != candidate or context['subject_sha256'] != registry['candidate_subjects'].get(candidate):
        errors.append('candidate_subject_mismatch')
    if context['requested_evidence_class'] != registration['requested_class'] or context['physical_validation'] != 'not_performed':
        errors.append('physical_validation_missing')
    if context['mass_scope'] != registration['mass_scope']:
        errors.append('mass_role_scope_upgrade')
    if context['current_registry'] != registry['candidates']:
        errors.append('current_registry_mismatch')
    return errors


def canonical_report(result, context, registry, requirements, caller, checked_metrics, checked_mass_value):
    """Checked metric values enter from ops; the Rust Verdict is copied unchanged."""
    require(type(result) is ProviderResult and type(caller) is TrustedCaller, 'actual_provider_result_required')
    pin = caller.data['pin']; registration = pin['registration']
    require(not scope_errors(context, registry, registration), 'requested_scope_refused')
    subject_id = registry['current_by_scope'].get(result.output['verdict']['group'])
    require(subject_id == registration['candidate_id'], 'subject_registration_mismatch')
    require(type(checked_metrics) is dict and set(checked_metrics) == {'G1'}, 'checked_metric_required')
    metric = closed(checked_metrics['G1'], {'status', 'value', 'scope', 'missing'}, 'checked_metric_wire')
    require(metric['scope'] == 'report_only' and metric['status'] in ['COMPLETE', 'INCOMPLETE'], 'checked_metric_wire')
    require(type(metric['missing']) is list and all(type(x) is str for x in metric['missing']), 'checked_metric_wire')
    if metric['status'] == 'COMPLETE':finite(metric['value']); require(not metric['missing'], 'checked_metric_wire')
    else:require(metric['value'] is None and metric['missing'], 'checked_metric_wire')
    mass = checked_mass_value
    if mass is not None:mass = finite(mass)
    out = result.output
    report = {'schema': 'jarambit.claim_report.v2', 'binding_stage': 'runtime_admitted', 'candidate_id': registration['candidate_id'], 'claim_id': out['claim_id'], 'group': out['verdict']['group'], 'input_sha256': result.input_sha256, 'mass': {'value_g': mass, 'role': 'record_only', 'scope': registration['mass_scope'], 'target_g': 80.0, 'stretch_g': 70.0}, 'metrics': copy.deepcopy(checked_metrics), 'physical_validation': 'not_performed', 'policy_sha256': pin['policy_raw_sha256'], 'product_qualification': None, 'publication_eligible': out['publication_eligible'], 'registry_sha256': pin['registry_raw_sha256'], 'release_authorized': out['release_authorized'], 'requirement_refs': copy.deepcopy(requirements), 'resolver_binary_sha256': pin['actual_resolver_binary_sha256'], 'resolver_source_sha256': pin['actual_resolver_source_closure_sha256'], 'software_support': 'incomplete' if out['verdict']['outcome'] == 'incomplete' else 'complete', 'subject_id': subject_id, 'subject_sha256': registry['candidate_subjects'][subject_id], 'verdict': copy.deepcopy(out['verdict'])}
    closed(report, REPORT_KEYS, 'report_keys')
    return report


def cache_record(result, report):
    require(result.output['verdict']['outcome'] == 'pass' and report['software_support'] == 'complete' and report['metrics']['G1']['status'] == 'COMPLETE', 'incomplete_result_not_cacheable')
    require(report['input_sha256'] == result.input_sha256 and report['verdict'] == result.output['verdict'], 'cache_report_provider_mismatch')
    return {'schema': 1, 'complete': True, 'input_sha256': result.input_sha256, 'provider': result.output, 'report': copy.deepcopy(report)}


def checked_cache(record, expected_input_sha256, expected_report, expected_binding):
    closed(record, {'schema', 'complete', 'input_sha256', 'provider', 'report'}, 'cache_wire')
    require(type(record['schema']) is int and record['schema'] == 1, 'cache_schema')
    require(record['complete'] is True, 'incomplete_cache_completion')
    require(record['input_sha256'] == expected_input_sha256, 'cache_input_identity_mismatch')
    validate_output(record['provider'], expected_binding, expected_report['claim_id'])
    require(canonical_body(record['report']) == canonical_body(expected_report), 'cache_report_mismatch')
    require(record['provider']['verdict'] == record['report']['verdict'], 'cache_report_provider_mismatch')
    require(record['provider']['verdict']['outcome'] == 'pass' and record['report']['software_support'] == 'complete' and record['report']['metrics']['G1']['status'] == 'COMPLETE', 'incomplete_result_not_cacheable')
    return copy.deepcopy(record['report'])
