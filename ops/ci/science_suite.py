#!/usr/bin/env python3
"""T19 science-suite gate: fail-closed checks over frozen T19 cases, receipts and CI evidence.

S01 assurance contracts are the only receipt/catalog trust root. This module never executes a
received argv, never grants product qualification and never authorizes a release.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from assurance.testing.catalog import bind_policy
from assurance.testing.contracts import (ContractError, digest, fields, finite, identifier, raw_hash, require,
                                         resolve_inventory, scientific_hash, strict_loads, unique_ids, validate_case)
from assurance.testing.receipt import publish_receipt

LIMITS = {'max_bytes': 1048576, 'max_depth': 64, 'max_nodes': 100000}
# S00 convention (as T00): sha256 of each frozen TEST_CASE_CATALOG record as compact sorted JSON.
# The catalog's raw SHA-256 is pinned by release-v1.json software_contracts.catalog.
T19_DEFINITIONS = {
    'T19-01-required_skip': 'b3def1f67b44e5f8ce6a2bde9212dcc6921727381793ff3277c10f7147105cab',
    'T19-02-path_filter': 'd831dc72c0a69fbecd74e319bb3130f6533c1a937a0a7632e5ae6a86a14588e8',
    'T19-03-capability_omission': '12416d0ffa6ff203216862f18a433f38fd8eeee292aa23c166a181f342255159',
    'T19-04-runner_escape': 'b3b6e4ce9d9a1c6b8fdc1be8b1aeff408975b36cf3b0cfe145f45d501adf5c7d',
    'T19-05-upload_missing': 'ac5914096a8332e090ecfaf3c715003860957df043b4a8cdf1ca58ba81514873',
    'T19-06-fresh_vs_reuse': '678f90f6211897345b657d927be032725858601889899bf675d742afe8d2ed45',
    'T19-07-dossier_mismatch': 'eff91d7890ab0a9ff8b60cce8e723641004690081615512241e07bdb557c6c33',
    'T19-08-render_finish_metadata': 'bede1c7c8556b2401be51999454e6823cd4f593b7b473626b534e0d11c3d9630',
    'T19-09-protective_interface': 'f1d217afe2a4bf740b0e558a4269f713157cc2ce4c486918a2c7e9a9a70cdb5a',
    'T19-10-final_policy': '1a14e9d84052e66bd367c5492cb3d023ad643cce346bb7610513efb060d76cd2',
}
# Whole criteria needing upstream owners stay not_run even when their synthetic interface tests pass.
UPSTREAM = {
    'T19-07-dossier_mismatch': 'needs real S08/S15 dossier producers and A01/A02 selection/lineage controls',
    'T19-08-render_finish_metadata': 'needs the S15 render-manifest consumer after its owner releases it',
    'T19-09-protective_interface': 'needs admitted existing sheath tests and S14 directional/handling records',
}
SOURCES = ('ops/ci/science_suite.py', 'ops/ci/tests/test_science_suite.py', 'assurance/testing/policy.json')


def definition_hash(record):
    return raw_hash(json.dumps(record, sort_keys=True, separators=(',', ':')).encode())


def load_release_policy(root=ROOT):
    root = Path(root)
    pinned = strict_loads((root/'assurance/testing/policy.json').read_bytes(), LIMITS)['release_policy_sha256']
    data = (root/'assurance/policies/release-v1.json').read_bytes()
    require(raw_hash(data) == digest(pinned), 'release policy differs from the S01 pin')
    return strict_loads(data, LIMITS)


def frozen_ids(release):
    ids = [c for c in release['software_contracts']['required_case_ids'] if c.startswith('T19-')]
    require(ids == list(T19_DEFINITIONS), 'T19 denominator differs from the frozen ten IDs')
    return ids


def derive_definitions(catalog_bytes, release):
    """Re-derive T19 oracle hashes from the frozen catalog file named by the release policy."""
    require(raw_hash(catalog_bytes) == release['software_contracts']['catalog']['sha256'], 'frozen catalog mismatch')
    records = [r for r in strict_loads(catalog_bytes, LIMITS)['cases'] if r['id'].startswith('T19-')]
    unique_ids(r['id'] for r in records)
    require([r['id'] for r in records] == frozen_ids(release), 'catalog T19 inventory mismatch')
    return {r['id']: definition_hash(r) for r in records}


def source_identity(root=ROOT):
    root = Path(root)
    for name in SOURCES:
        require(not any(p.is_symlink() for p in [root/name, *(root/name).parents]), 'symlinked suite source')
    return {name: raw_hash((root/name).read_bytes()) for name in SOURCES}


def build_catalog(root=ROOT):
    ids = frozen_ids(load_release_policy(root))
    input_sha256 = scientific_hash(source_identity(root))
    return [validate_case({'schema': 1, 'id': cid, 'required': True, 'evidence_class': 'deterministic_contract',
                           'input_sha256': input_sha256, 'oracle_sha256': T19_DEFINITIONS[cid],
                           'controls': ['positive', 'adverse'], 'disabled_reason': None, 'claim_enabled': True})
            for cid in ids]


# T19-01: a verbose unittest transcript is green only if every expected test ran once and passed.
START = re.compile(r'^(\w+) \(([\w.]+)\)', re.M)
OUTCOME = re.compile(r"(?:\.\.\. |^)(ok|FAIL|ERROR|skipped(?: .*)?|expected failure|unexpected success)$", re.M)
STATUS = {'ok': 'passed', 'FAIL': 'failed', 'unexpected success': 'failed', 'ERROR': 'error',
          'expected failure': 'not_run'}


def collect_unittest(log, expected):
    require(type(log) is str and type(expected) in (list, set, tuple), 'transcript text and inventory required')
    expected = sorted(expected)
    unique_ids(expected)
    tail = re.search(r'^(?:=|-){70}$', log, re.M)
    body = log[:tail.start()] if tail else log
    starts = list(START.finditer(body))
    outcomes, problems = {}, []
    for k, start in enumerate(starts):
        name, test_id = start.groups()
        segment = body[start.end():starts[k+1].start() if k+1 < len(starts) else len(body)]
        token = OUTCOME.search(segment, segment.find('...')) if '...' in segment else None
        if test_id.split('.')[-1] != name or test_id in outcomes:
            problems.append('duplicate or malformed test record: ' + test_id)
        outcomes[test_id] = STATUS.get(token.group(1), 'not_run') if token else 'error'
    ran = re.findall(r'^Ran (\d+) tests? in \d+\.\d+s$', log, re.M)
    lines = [line for line in log.splitlines() if line.strip()]
    if len(ran) != 1 or int(ran[0]) != len(starts):
        problems.append('missing or inconsistent Ran summary')
    elif int(ran[0]) == 0:
        problems.append('no tests discovered')
    if not lines or lines[-1] != 'OK':
        problems.append('suite summary is not plain OK')
    extra = sorted(set(outcomes) - set(expected))
    if extra:
        problems.append('unexpected test inventory: ' + ', '.join(extra))
    result = {t: outcomes.get(t, 'not_run') for t in expected}
    counts = {s: sum(v == s for v in result.values()) for s in ('passed', 'failed', 'error', 'not_run')}
    counts['expected'] = len(expected)
    if problems or counts['passed'] != len(expected) or not expected:
        execution = 'failed' if counts['failed'] else 'error' if problems or counts['error'] else 'not_run'
    else:
        execution = 'passed'
    return {'execution': execution, 'outcomes': result, 'counts': counts, 'problems': problems}


# T19-02: a science-relevant change can never skip a required workflow through a path filter.
CRITICAL_PROBES = ('requirements/RS-karambit-v2.toml', 'assurance/schemas/evidence.v2.json',
                   'assurance/testing/contracts.py', 'crates/evidence/src/assurance.rs', 'fem_solid/gci.py',
                   'metrics/global_metric.py', 'ops/ci/check_claims.py', 'ops/ci/science_suite.py', 'Cargo.lock')


def glob_regex(pattern):
    require(not set(pattern) & set('[]{}+\\'), 'unsupported glob syntax')
    out, k = '', 0
    while k < len(pattern):
        if pattern.startswith('**/', k):
            out, k = out + '(?:.*/)?', k + 3
        elif pattern.startswith('**', k):
            out, k = out + '.*', k + 2
        elif pattern[k] == '*':
            out, k = out + '[^/]*', k + 1
        elif pattern[k] == '?':
            out, k = out + '[^/]', k + 1
        else:
            out, k = out + re.escape(pattern[k]), k + 1
    return re.compile(out + r'\Z')


def triggered(path, filters):
    """GitHub path filters for one changed file; later negated `paths` patterns override earlier ones."""
    require(set(filters) <= {'paths', 'paths-ignore'} and len(filters) <= 1, 'unsupported filter combination')
    if not filters:
        return True
    kind, patterns = next(iter(filters.items()))
    require(type(patterns) is list and patterns and all(type(p) is str and p for p in patterns), 'empty path filter')
    if kind == 'paths-ignore':
        return not any(glob_regex(p).match(path) for p in patterns)
    hit = False
    for pattern in patterns:
        negated = pattern.startswith('!')
        if glob_regex(pattern[1:] if negated else pattern).match(path):
            hit = not negated
    return hit


def workflow_triggers(text):
    """Trigger -> path filters of the top-level `on:` block; unrecognized filter syntax fails closed."""
    triggers, block, current = {}, False, None
    lines = text.splitlines()
    for k, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip())
        key = re.match(r'^\s*([\w-]+|"on"|\'on\'):(?:\s+(.*?))?\s*$', line)
        if indent == 0:
            block, current = bool(key) and key.group(1).strip('\'"') == 'on', None
            if block and key.group(2):
                triggers.update((name, {}) for name in re.findall(r'[\w-]+', key.group(2).split('#')[0]))
            continue
        if not block or not key:
            continue
        if indent == 2:
            current = key.group(1)
            triggers[current] = {}
            continue
        if key.group(1) not in ('paths', 'paths-ignore'):
            continue
        require(current is not None, 'path filter outside a recognized trigger')
        inline = (key.group(2) or '').split(' #')[0].strip()
        if inline:
            require(inline.startswith('[') and inline.endswith(']'), 'unparsed path filter')
            patterns = [p.strip().strip('\'"') for p in inline[1:-1].split(',') if p.strip()]
        else:
            patterns = []
            for item in lines[k+1:]:
                if not item.strip() or item.lstrip().startswith('#'):
                    continue
                entry = re.match(r'^(\s*)- (.+?)\s*$', item)
                if not entry or len(entry.group(1)) <= indent:
                    break
                patterns.append(entry.group(2).strip('\'"'))
        require(patterns, 'unparsed path filter')
        triggers[current][key.group(1)] = patterns
    return triggers


def selection_violations(text, probes=CRITICAL_PROBES):
    """A required science workflow must run on every pull request touching a science-critical path."""
    triggers = workflow_triggers(text)
    if 'pull_request' not in triggers:
        return ['pull_request: not triggered']
    return sorted({f'{name}:{path}' for name in ('pull_request', 'pull_request_target') if name in triggers
                   for path in probes if not triggered(path, triggers[name])})


# T19-03: an enabled capability needs its exact expected inventory executed; omission is incomplete.
def load_gate_policy(data, release):
    require(raw_hash(data) == release['software_contracts']['gate_policy_reference']['sha256'], 'gate policy mismatch')
    policy = strict_loads(data, LIMITS)
    require(type(policy.get('capabilities')) is dict and policy['capabilities'], 'capability inventory required')
    for spec in policy['capabilities'].values():
        require(type(spec['required_case_ids']) is list and spec['required_case_ids'], 'capability cases required')
        unique_ids(spec['required_case_ids'])
    return policy


def capability_gate(manifest, gate_policy, passed):
    fields(manifest, ['schema', 'capabilities'])
    require(manifest['schema'] == 1 and type(manifest['schema']) is int, 'unknown manifest schema')
    known, declared = gate_policy['capabilities'], manifest['capabilities']
    require(type(declared) is dict and set(declared) <= set(known), 'unknown capability')
    passed = set(passed)
    result = {}
    for name, spec in known.items():
        entry = declared.get(name)
        if entry is None:
            result[name] = {'status': 'incomplete', 'reason': 'capability omitted from manifest'}
            continue
        fields(entry, ['state', 'reason', 'claims', 'proof'])
        require(type(entry['claims']) is list and type(entry['proof']) is list, 'claim/proof lists required')
        unique_ids(entry['claims']); unique_ids(entry['proof'])
        if entry['state'] == 'disabled':
            identifier(entry['reason'])
            require(not entry['claims'] and not entry['proof'], 'disabled capability cannot carry claims or proof')
            result[name] = {'status': 'disabled', 'reason': entry['reason']}
            continue
        require(entry['state'] == 'enabled' and entry['reason'] is None, 'unknown capability state')
        require(entry['claims'], 'enabled capability must name its claims')
        expected = spec['required_case_ids']
        require(set(entry['proof']) <= set(expected), 'proof outside expected inventory')
        missing = [c for c in expected if c not in entry['proof'] or c not in passed]
        result[name] = {'status': 'incomplete' if missing else 'software_contracts_executed', 'missing': missing}
    return {'capabilities': result, 'incomplete': sorted(n for n, r in result.items() if r['status'] == 'incomplete'),
            'physical_qualification': None}


# T19-04: received commands are validated as data and never executed.
SHELLS = {'sh', 'bash', 'dash', 'zsh', 'env', 'sudo', 'xargs', 'eval'}
ENV_ALLOW = {'PYTHONDONTWRITEBYTECODE', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
             'RAYON_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'CARGO_INCREMENTAL', 'CUDA_VISIBLE_DEVICES', 'LANG', 'TZ'}


def owned_path(path, root):
    """Resolve a receipt path inside the owned root; traversal and any symlink component fail."""
    require(type(path) is str and path and '\x00' not in path, 'path string required')
    root = Path(root)
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), 'owned root must be a real directory')
    relative = PurePosixPath(path)
    require(not relative.is_absolute() and '..' not in relative.parts, 'path escapes owned root')
    current = root
    for part in relative.parts:
        current = current/part
        require(not current.is_symlink(), 'symlink escape')
    require(current.resolve().is_relative_to(root.resolve()), 'path escapes owned root')
    return current


def check_command(record, root, programs):
    fields(record, ['argv', 'cwd', 'env', 'outputs'])
    argv = record['argv']
    require(type(argv) is list and argv and all(type(a) is str and a and '\x00' not in a for a in argv),
            'argv list required; shell strings are never executed')
    require(argv[0] in programs and PurePosixPath(argv[0]).name not in SHELLS, 'program not allowlisted')
    require(not (PurePosixPath(argv[0]).name.startswith('python') and '-c' in argv), 'inline code is not executable')
    cwd = owned_path(record['cwd'], root)
    require(cwd.is_dir(), 'cwd missing')
    require(type(record['env']) is dict and set(record['env']) <= ENV_ALLOW and
            all(type(v) is str for v in record['env'].values()), 'environment not allowlisted')
    require(type(record['outputs']) is list and record['outputs'], 'declared outputs required')
    return {'argv': argv, 'cwd': str(cwd), 'outputs': [str(owned_path(p, root)) for p in record['outputs']],
            'executed': False}


# T19-05: missing, corrupt, oversized or timed-out uploads leave the attempt incomplete.
def check_uploads(attempt, root, max_bytes):
    fields(attempt, ['complete', 'timed_out', 'exit_code', 'artifacts', 'raw_failure'])
    problems = []
    if attempt['complete'] is not True or attempt['timed_out'] is not False or attempt['exit_code'] != 0:
        problems.append('attempt did not complete')
    require(type(attempt['artifacts']) is dict and type(attempt['raw_failure']) is list, 'inventories required')
    if not attempt['artifacts']:
        problems.append('empty artifact inventory')
    for name, expected in sorted(attempt['artifacts'].items()):
        fields(expected, ['sha256', 'bytes'])
        digest(expected['sha256'])
        require(type(expected['bytes']) is int and expected['bytes'] >= 0, 'declared size required')
        path = owned_path(name, root)
        if not path.is_file():
            problems.append('missing upload: ' + name)
        elif path.stat().st_size > max_bytes or expected['bytes'] > max_bytes:
            problems.append('oversized upload: ' + name)
        elif path.stat().st_size != expected['bytes'] or raw_hash(path.read_bytes()) != expected['sha256']:
            problems.append('corrupt upload: ' + name)
    for name in attempt['raw_failure']:
        if not owned_path(name, root).is_file():
            problems.append('raw failure not retained: ' + name)
    return {'status': 'incomplete' if problems else 'complete', 'problems': problems,
            'retained_raw_failure': list(attempt['raw_failure'])}


# T19-06: historical evidence is reuse, never a fresh execution.
def classify_run(run, current_input_sha256, history):
    fields(run, ['mode', 'attempt_id', 'input_sha256', 'artifacts', 'reused_from'])
    identifier(run['attempt_id']); digest(run['input_sha256'])
    require(type(run['artifacts']) is dict and run['artifacts'], 'artifact identities required')
    for value in run['artifacts'].values():
        digest(value)
    old_hashes = {h for record in history.values() for h in record['artifacts'].values()}
    if run['mode'] == 'fresh':
        require(run['reused_from'] is None, 'fresh run cannot name a reused source')
        require(run['attempt_id'] not in history, 'historical attempt relabeled fresh')
        require(run['input_sha256'] == current_input_sha256, 'fresh run on different inputs')
        require(not old_hashes & set(run['artifacts'].values()), 'historical artifact bytes claimed fresh')
        return {'mode': 'fresh', 'counts_as_fresh_execution': True}
    require(run['mode'] == 'reuse', 'unknown run mode')
    source = run['reused_from']
    fields(source, ['attempt_id', 'scope'])
    identifier(source['scope'])
    require(source['attempt_id'] in history, 'reused attempt unknown')
    prior = history[source['attempt_id']]
    require(prior['input_sha256'] == run['input_sha256'] == current_input_sha256, 'incompatible reuse')
    require(prior['artifacts'] == run['artifacts'], 'reused artifacts differ from history')
    return {'mode': 'reuse', 'counts_as_fresh_execution': False, 'scope': source['scope'],
            'reused_from': source['attempt_id']}


# T19-07 interface: every dossier view must agree on identities and claim state.
DOSSIER_KEYS = ('candidate', 'material', 'mesh', 'requirements', 'cases')
CLAIM_STATES = {'pass', 'fail', 'incomplete', 'not_run'}


def reconstruct_dossier(views, proofs, passed):
    require(type(views) is dict and len(views) >= 2, 'at least two independent views required')
    passed, mismatches = set(passed), []
    for name, view in sorted(views.items()):
        fields(view, ['identity', 'claims'])
        fields(view['identity'], list(DOSSIER_KEYS))
        for key in DOSSIER_KEYS[:-1]:
            digest(view['identity'][key])
        unique_ids(view['identity']['cases'])
        require(type(view['claims']) is dict and set(view['claims'].values()) <= CLAIM_STATES, 'unknown claim state')
    reference_name = sorted(views)[0]
    reference = views[reference_name]
    for name, view in sorted(views.items()):
        for key in DOSSIER_KEYS:
            if view['identity'][key] != reference['identity'][key]:
                mismatches.append(f'{key}: {name} != {reference_name}')
        if view['claims'] != reference['claims']:
            mismatches.append(f'claims: {name} != {reference_name}')
    for claim, state in sorted(reference['claims'].items()):
        cases = proofs.get(claim)
        if state == 'pass' and (not cases or not set(cases) <= passed):
            mismatches.append('pass without executed proof: ' + claim)
    return {'integrity': 'failed' if mismatches else 'reconstructed', 'mismatches': mismatches,
            'release_authorized': False}


# T19-08 interface: render/finish metadata never populates structural properties.
MEASURED = {'measured_record', 'reference_dataset'}


def check_material_sources(material):
    fields(material, ['structural', 'finish'])
    require(type(material['finish']) is dict and type(material['structural']) is dict, 'material blocks required')
    finish_hash = scientific_hash(material['finish'])
    problems = []
    for name, entry in sorted(material['structural'].items()):
        fields(entry, ['value', 'source'])
        finite(entry['value'])
        fields(entry['source'], ['kind', 'sha256'])
        digest(entry['source']['sha256'])
        if entry['source']['kind'] not in MEASURED or entry['source']['sha256'] == finish_hash:
            problems.append('nonmeasured structural source: ' + name)
        if name in material['finish']:
            problems.append('finish metadata names a structural property: ' + name)
    return {'status': 'rejected' if problems else 'sources_bound', 'problems': problems,
            'structural_qualification': None}


# T19-09 interface: a favorable scalar sheath result cannot fill unperformed directional checks.
SHEATH_RECORDS = ('seated_retention', 'unseated', 'interrupted_insertion', 'directional_retention', 'handling')


def protective_claim(evidence):
    fields(evidence, ['existing_tests', 'scalar', 'records'])
    require(type(evidence['records']) is dict and set(evidence['records']) <= set(SHEATH_RECORDS), 'unknown record')
    missing = [] if evidence['existing_tests'] == 'passed' else ['existing sheath tests']
    for name in SHEATH_RECORDS:
        record = evidence['records'].get(name)
        if record is None:
            missing.append(name)
            continue
        fields(record, ['status', 'sha256'])
        digest(record['sha256'])
        if record['status'] != 'pass':
            missing.append(name)
    return {'status': 'incomplete' if missing else 'records_complete', 'missing': missing,
            'promotion': 'blocked' if missing else 'review_required', 'scalar_substitutes': False}


# T19-10: an unmet required final gate without owner amendment means scoped RC only.
def final_policy(final_release, evidence):
    fields(final_release, ['inherited_section', 'amendments', 'authorization', 'gates'])
    require(final_release['authorization'] == 'owner_required', 'owner authorization required')
    gates = final_release['gates']
    require(type(gates) is list and gates, 'final gates required')
    unique_ids(g['id'] for g in gates)
    require(type(evidence) is dict and set(evidence) <= {g['id'] for g in gates}, 'unknown gate evidence')
    amended = {}
    for amendment in final_release['amendments']:
        fields(amendment, ['gate', 'owner_authorization_sha256', 'scope'])
        digest(amendment['owner_authorization_sha256']); identifier(amendment['scope'])
        amended[amendment['gate']] = amendment['scope']
    unresolved = []
    for gate in gates:
        fields(gate, ['id', 'required', 'text', 'status'])
        record = evidence.get(gate['id'])
        if record is not None:
            fields(record, ['status', 'receipt_sha256'])
            digest(record['receipt_sha256'])
        satisfied = record is not None and record['status'] == 'satisfied'
        if gate['required'] is not False and not satisfied and gate['id'] not in amended:
            unresolved.append(gate['id'])
    return {'release_class': 'scoped_rc_only' if unresolved else 'final_policy_gates_satisfied',
            'unresolved_gates': unresolved, 'amended': amended, 'release_authorized': False}


# Collector: S01 receipts from one raw transcript, then an independent re-check of that transcript.
def case_tests(case_id, outcomes):
    prefix = 'test_' + '_'.join(case_id.split('-')[:2]) + '_'
    return {t: s for t, s in outcomes.items() if t.split('.')[-1].startswith(prefix)}


def control_state(tests, control):
    states = [s for t, s in tests.items() if t.split('.')[-1].split('_')[3:4] == [control]]
    if not states:
        return 'not_run'
    for state in ('failed', 'error', 'not_run'):
        if state in states:
            return state
    return 'passed'


def transcript_ids(text):
    return sorted({m.group(2) for m in START.finditer(text)})


def publish_attempt(directory, catalog, log, argv, exit_code, attempt_id, expected=None, history=None):
    """Publish one immutable receipt per frozen case; pass/fail derives only from the transcript.

    Without an explicit expected test inventory the transcript's own IDs are used; a case whose
    controls are absent from the transcript is then not_run, never passed."""
    directory = Path(directory)
    require(not directory.exists(), 'fresh attempt directory required')
    require(type(log) is bytes, 'raw transcript bytes required')
    text = log.decode('utf-8')
    parsed = collect_unittest(text, transcript_ids(text) if expected is None else expected)
    log_name = 'suite.log'
    for case in catalog:
        tests = case_tests(case['id'], parsed['outcomes'])
        controls = {c: control_state(tests, c) for c in case['controls']}
        run = {'mode': 'fresh', 'attempt_id': attempt_id, 'input_sha256': case['input_sha256'],
               'artifacts': {log_name: raw_hash(log)}, 'reused_from': None}
        classify_run(run, case['input_sha256'], history or {})
        record = (json.dumps({'case_id': case['id'], 'run': run, 'tests': tests, 'suite_problems': parsed['problems'],
                              'upstream': UPSTREAM.get(case['id'])}, sort_keys=True) + '\n').encode()
        artifacts = {log_name: log, case['id'] + '.run.json': record}
        values = list(controls.values())
        if case['id'] in UPSTREAM or values == ['not_run'] * len(values):
            execution, finding, code = 'not_run', 'not_applicable', None
            controls = {c: 'not_run' for c in case['controls']}  # synthetic outcomes stay in the run record
            reason = UPSTREAM.get(case['id'], 'no executed control for this case')
            counts = {'expected': 2, 'passed': 0, 'failed': 0, 'error': 0, 'not_run': 2}
        else:
            ok = values == ['passed'] * len(values) and exit_code == 0 and parsed['execution'] == 'passed'
            execution = 'passed' if ok else 'failed' if 'failed' in values else 'error'
            finding, code = 'rejected_within_scope' if ok else 'inconclusive', exit_code
            reason = None if ok else 'controls or suite not green: ' + '; '.join(parsed['problems'] or values)
            counts = {s: values.count(s) for s in ('passed', 'failed', 'error', 'not_run')}
            counts['expected'] = len(values)
        receipt = {'schema': 1, 'case_id': case['id'], 'input_sha256': case['input_sha256'],
                   'oracle_sha256': case['oracle_sha256'], 'execution': execution, 'finding': finding,
                   'argv': list(argv), 'exit_code': code, 'timed_out': False, 'complete': True,
                   'controls': controls, 'artifacts': {k: raw_hash(v) for k, v in artifacts.items()},
                   'counts': counts, 'reason': reason}
        for name, data in artifacts.items():
            path = directory/name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as output:
                    output.write(data)
        publish_receipt(directory/(case['id'] + '.json'), receipt, case, artifacts)
    return directory


def collect(catalog, directory):
    """Resolve frozen receipts through S01 and re-derive every passed control from the raw transcript."""
    directory = Path(directory).absolute()
    require(directory.is_dir() and not directory.is_symlink(), 'receipt directory missing')
    receipts, artifacts = [], {}
    for path in sorted(directory.glob('*.json')):
        if path.name.endswith('.run.json'):
            continue
        record = strict_loads(owned_path(path.name, directory).read_bytes(), LIMITS)
        require(type(record) is dict, 'receipt object required')
        receipts.append(record)
        for name in record.get('artifacts', {}):
            artifacts[name] = owned_path(name, directory).read_bytes()
    inventory = resolve_inventory(catalog, receipts, artifacts, bind_policy(catalog, LIMITS))
    execution = {cid: 'not_run' for cid in inventory['expected_ids']}
    for record in receipts:
        execution[record['case_id']] = record['execution']
        if record['execution'] != 'passed':
            continue
        require(record['case_id'] not in UPSTREAM, 'upstream-dependent case cannot pass in this suite')
        run = strict_loads(artifacts[record['case_id'] + '.run.json'], LIMITS)
        require(run['case_id'] == record['case_id'] and run['run']['input_sha256'] == record['input_sha256'],
                'run record identity mismatch')
        classify_run(run['run'], record['input_sha256'], {})
        log = artifacts['suite.log'].decode('utf-8')
        require(run['run']['artifacts']['suite.log'] == raw_hash(artifacts['suite.log']), 'transcript identity mismatch')
        parsed = collect_unittest(log, transcript_ids(log))
        tests = case_tests(record['case_id'], parsed['outcomes'])
        require(parsed['execution'] == 'passed' and tests == run['tests'] and
                all(control_state(tests, c) == 'passed' for c in ('positive', 'adverse')),
                'self-reported pass not supported by transcript')
    return {'schema': 1, 'unit': 'T19', 'expected_ids': inventory['expected_ids'],
            'denominator': len(inventory['expected_ids']), 'execution': execution,
            'findings': inventory['findings'], 'support': inventory['support'], 'missing': inventory['missing'],
            'upstream_not_run': sorted(set(UPSTREAM) & set(inventory['missing'])),
            'tiers': {'T0_software': inventory['support'], 'T1_numerical': 'not_run_here',
                      'T2_laboratory': 'not_run_here', 'T3_research': 'not_activated'},
            'release_eligibility': 'not_evaluated_here', 'release_authorized': False, 'product_qualification': None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('catalog')
    publish = commands.add_parser('publish')
    publish.add_argument('--attempt', required=True)
    publish.add_argument('--log', required=True)
    publish.add_argument('--attempt-id', required=True)
    publish.add_argument('--exit-code', type=int, required=True)
    publish.add_argument('--argv-json', required=True, help='executed argv as a JSON list')
    check = commands.add_parser('check')
    check.add_argument('--receipts', required=True)
    workflows = commands.add_parser('workflows')
    workflows.add_argument('paths', nargs='+')
    args = parser.parse_args(argv)
    try:
        catalog = build_catalog()
        if args.command == 'catalog':
            result, ok = catalog, True
        elif args.command == 'publish':
            publish_attempt(args.attempt, catalog, Path(args.log).read_bytes(),
                            strict_loads(args.argv_json, LIMITS), args.exit_code, args.attempt_id)
            result = collect(catalog, args.attempt)
            ok = result['support'] == 'complete'
        elif args.command == 'check':
            result = collect(catalog, args.receipts)
            ok = result['support'] == 'complete'
        else:
            result = {path: selection_violations(Path(path).read_text()) for path in args.paths}
            ok = not any(result.values())
    except (ContractError, OSError, KeyError, TypeError, UnicodeError) as error:
        print(json.dumps({'support': 'error', 'reason': str(error), 'release_authorized': False}))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
