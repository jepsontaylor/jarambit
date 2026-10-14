#!/usr/bin/env python3
"""T19 science-suite gate: fail-closed checks over frozen T19 cases, receipts and CI evidence.

S01 assurance contracts are the only receipt/catalog trust root. The expected test inventory comes
from the suite source bound into the catalog input identity, and attempt history is pinned by the
caller; neither is inferred from the evidence under review. Files are read through no-follow
descriptors. This module never executes a received argv, never grants product qualification and
never authorizes a release.
"""
import argparse
import ast
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
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
SUITE_TESTS = 'ops/ci/tests/test_science_suite.py'
SOURCES = ('ops/ci/science_suite.py', SUITE_TESTS, 'assurance/testing/policy.json')
CONTEXT = 'context.json'
LOG = 'suite.log'


# Reads: one regular file under an owned root, through no-follow descriptors, identity checked before and after.
class ReadRefused(ContractError):
    def __init__(self, kind, path, detail):
        super().__init__(f'{kind} {path}: {detail}')
        self.kind = kind


_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


def _parts(path):
    require(type(path) is str and path and '\x00' not in path, 'path string required')
    relative = PurePosixPath(path)
    require(not relative.is_absolute() and relative.parts and '..' not in relative.parts, 'path escapes owned root')
    return relative.parts


def _identity(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, stat.S_IFMT(st.st_mode)


def _read_fd(fd, limit):
    chunks, total = [], 0
    while total <= limit:
        chunk = os.read(fd, min(1 << 20, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b''.join(chunks)


def _open_parent(root, parts):
    root = Path(root)
    require(root.is_absolute(), 'owned root must be absolute')
    fds = [os.open(root, _DIR)]
    try:
        for part in parts[:-1]:
            fds.append(os.open(part, _DIR, dir_fd=fds[-1]))
    except OSError:
        for fd in reversed(fds):
            os.close(fd)
        raise
    return fds


def read_owned(root, path, max_bytes):
    """Bytes of root/path; any symlink component, non-regular file, size or identity change refuses."""
    parts = _parts(path)
    try:
        fds = _open_parent(root, parts)
    except OSError as error:
        raise ReadRefused('unsafe', path, error.strerror) from error
    try:
        try:
            before = os.stat(parts[-1], dir_fd=fds[-1], follow_symlinks=False)
        except FileNotFoundError as error:
            raise ReadRefused('missing', path, 'no such file') from error
        if not stat.S_ISREG(before.st_mode):
            raise ReadRefused('unsafe', path, 'not a regular file')
        if before.st_size > max_bytes:
            raise ReadRefused('oversized', path, f'{before.st_size} bytes')
        try:
            fds.append(os.open(parts[-1], _FILE, dir_fd=fds[-1]))
        except OSError as error:
            raise ReadRefused('unsafe', path, error.strerror) from error
        opened = os.fstat(fds[-1])
        if _identity(opened) != _identity(before):
            raise ReadRefused('unsafe', path, 'replaced before read')
        data = _read_fd(fds[-1], max_bytes)
        after = os.fstat(fds[-1])
        try:
            named = os.stat(parts[-1], dir_fd=fds[-2], follow_symlinks=False)
        except FileNotFoundError as error:
            raise ReadRefused('unsafe', path, 'removed during read') from error
        if not _identity(after) == _identity(opened) == _identity(named) or len(data) != opened.st_size:
            raise ReadRefused('unsafe', path, 'changed during read')
        return data
    finally:
        for fd in reversed(fds):
            os.close(fd)


def list_owned(root):
    """Entry names of an owned directory opened without following a symlink."""
    try:
        fd = os.open(Path(root), _DIR)
    except OSError as error:
        raise ReadRefused('unsafe', str(root), error.strerror) from error
    try:
        return sorted(os.listdir(fd))
    finally:
        os.close(fd)


def is_owned_file(root, path):
    try:
        fds = _open_parent(root, _parts(path))
    except OSError:
        return False
    try:
        return stat.S_ISREG(os.stat(_parts(path)[-1], dir_fd=fds[-1], follow_symlinks=False).st_mode)
    except OSError:
        return False
    finally:
        for fd in reversed(fds):
            os.close(fd)


def caller_file(path, max_bytes=LIMITS['max_bytes']):
    """A caller-named input file read without following a final symlink."""
    path = Path(path).absolute()
    return read_owned(path.parent, path.name, max_bytes)


def definition_hash(record):
    return raw_hash(json.dumps(record, sort_keys=True, separators=(',', ':')).encode())


def load_release_policy(root=ROOT):
    root = Path(root).absolute()
    pinned = strict_loads(read_owned(root, 'assurance/testing/policy.json', LIMITS['max_bytes']), LIMITS)
    data = read_owned(root, 'assurance/policies/release-v1.json', LIMITS['max_bytes'])
    require(raw_hash(data) == digest(pinned['release_policy_sha256']), 'release policy differs from the S01 pin')
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


def source_files(root=ROOT):
    root = Path(root).absolute()
    return {name: read_owned(root, name, LIMITS['max_bytes']) for name in SOURCES}


def source_identity(root=ROOT):
    return {name: raw_hash(data) for name, data in source_files(root).items()}


def inventory_from_source(data):
    """Test IDs statically defined in the suite file; generated or inherited tests are not expected."""
    module = PurePosixPath(SUITE_TESTS).stem
    tree = ast.parse(data, filename=SUITE_TESTS)
    ids = sorted(f'{module}.{node.name}.{item.name}' for node in tree.body if isinstance(node, ast.ClassDef)
                 for item in node.body if isinstance(item, ast.FunctionDef) and item.name.startswith('test'))
    require(ids, 'empty expected inventory')
    unique_ids(ids)
    return ids


def build_catalog(root=ROOT, identity=None):
    ids = frozen_ids(load_release_policy(root))
    input_sha256 = scientific_hash(source_identity(root) if identity is None else identity)
    return [validate_case({'schema': 1, 'id': cid, 'required': True, 'evidence_class': 'deterministic_contract',
                           'input_sha256': input_sha256, 'oracle_sha256': T19_DEFINITIONS[cid],
                           'controls': ['positive', 'adverse'], 'disabled_reason': None, 'claim_enabled': True})
            for cid in ids]


def source_context(root=ROOT):
    """Catalog and expected inventory derived from one read of the source bytes bound into the catalog input."""
    files = source_files(root)
    identity = {name: raw_hash(data) for name, data in files.items()}
    return build_catalog(root, identity), inventory_from_source(files[SUITE_TESTS])


def trusted_inventory(expected):
    require(type(expected) is list and expected and all(type(t) is str for t in expected),
            'trusted expected test inventory required')
    unique_ids(expected)
    return sorted(expected)


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
FILTER_KEYS = {'branches', 'branches-ignore', 'tags', 'tags-ignore', 'types', 'paths', 'paths-ignore'}
FILTERED_TRIGGERS = {'pull_request', 'pull_request_target', 'push'}
PR_TYPES = {'opened', 'synchronize', 'reopened'}
BASE_BRANCH = 'main'


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


def _matches(value, patterns):
    """GitHub positive/negated pattern list: the last matching pattern decides."""
    hit = False
    for pattern in patterns:
        negated = pattern.startswith('!')
        if glob_regex(pattern[1:] if negated else pattern).match(value):
            hit = not negated
    return hit


def triggered(path, filters):
    """GitHub path filters for one changed file; later negated `paths` patterns override earlier ones."""
    paths = {k: v for k, v in filters.items() if k in ('paths', 'paths-ignore')}
    require(len(paths) <= 1, 'unsupported filter combination')
    if not paths:
        return True
    kind, patterns = next(iter(paths.items()))
    require(type(patterns) is list and patterns and all(type(p) is str and p for p in patterns), 'empty path filter')
    if kind == 'paths-ignore':
        return not any(glob_regex(p).match(path) for p in patterns)
    return _matches(path, patterns)


def _uncomment(line):
    quote = None
    for k, char in enumerate(line):
        if quote:
            quote = None if char == quote else quote
        elif char in '\'"':
            quote = char
        elif char == '#' and (k == 0 or line[k-1] == ' '):
            return line[:k].rstrip()
    require(quote is None, 'unterminated quoted scalar')
    return line.rstrip()


def _scalar(token):
    token = token.strip()
    require(token, 'empty YAML scalar')
    if token[0] in '\'"':
        require(len(token) >= 2 and token[-1] == token[0], 'unsupported quoted scalar: ' + token)
        inner = token[1:-1]
        require(token[0] == "'" and "'" not in inner or token[0] == '"' and not set(inner) & set('"\\'),
                'unsupported quoted scalar escape: ' + token)
        return inner
    require(token[0] not in '[]{}&*!|>%@`,?:-' and ': ' not in token and not token.endswith(':'),
            'unsupported YAML scalar: ' + token)
    return token


def _flow_sequence(text):
    require(text.startswith('[') and text.endswith(']'), 'unsupported YAML value: ' + text)
    items, current, quote = [], '', None
    for char in text[1:-1]:
        if quote:
            quote = None if char == quote else quote
            current += char
        elif char in '\'"':
            quote = char
            current += char
        elif char in '[]{}':
            raise ContractError('nested flow collections unsupported: ' + text)
        elif char == ',':
            items.append(_scalar(current))
            current = ''
        else:
            current += char
    if current.strip():
        items.append(_scalar(current))
    require(items, 'empty flow sequence: ' + text)
    return items


KEY = re.compile(r'^( *)([A-Za-z_][\w-]*):(?: +(.*))?$')


def _strict_line(line):
    """A top-level or `on:` line without comment; tabs, anchors, aliases, tags and directives refuse."""
    line = _uncomment(line)
    require('\t' not in line, 'tabs unsupported in workflow keys')
    content = line.lstrip()
    require(not content.startswith(('---', '...', '%', '?', '&', '*', '!', '<<', '{', '[')) and ' &' not in line
            and ' *' not in line and ' !' not in line, 'unsupported YAML construct: ' + content)
    return line


def workflow_triggers(text):
    """Trigger -> filters of the top-level `on:` key. Supported forms: `on: name`, `on: [a, b]`, and a block
    mapping of triggers whose filter keys hold block or flow sequences of scalars. Any other form refuses.
    Only top-level keys and the `on:` block are parsed; job bodies are not interpreted."""
    require(type(text) is str, 'workflow text required')
    raw = [line.rstrip() for line in text.splitlines()]
    skip = lambda line: not line.strip() or line.lstrip().startswith('#')
    triggers, seen, k = {}, False, 0
    while k < len(raw):
        line = raw[k]
        k += 1
        if skip(line) or line[0] == ' ':
            continue
        line = _strict_line(line)
        top = re.match(r'^(?:"([^"]*)"|\'([^\']*)\'|([^\'"\s:][^:]*?))\s*:(?:\s+(.*))?$', line)
        require(top is not None, 'unsupported top-level YAML: ' + line)
        name = next(g for g in top.groups()[:3] if g is not None)
        if name not in ('on', 'true'):
            continue
        require(name == 'on' and not seen, 'unsupported or duplicate on key')
        seen = True
        value = top.group(4)
        if value:
            if value.startswith('['):
                names = _flow_sequence(value)
            else:
                require(not value.startswith(('{', '|', '>')), 'unsupported on value: ' + value)
                names = [_scalar(value)]
            for trigger in names:
                require(re.fullmatch(r'[A-Za-z_][\w-]*', trigger) and trigger not in triggers, 'invalid trigger: ' + trigger)
                triggers[trigger] = {}
            continue
        block = []
        while k < len(raw) and (skip(raw[k]) or raw[k][0] == ' '):
            if not skip(raw[k]):
                block.append(_strict_line(raw[k]))
            k += 1
        require(block, 'empty on mapping')
        triggers = _trigger_block(block)
    return triggers


def _trigger_block(block):
    indent = lambda line: len(line) - len(line.lstrip(' '))
    level, triggers, current, deeper, pending = indent(block[0]), {}, None, None, None
    for line in block:
        depth = indent(line)
        if depth == level:
            match = KEY.match(line)
            require(match is not None, 'unsupported trigger syntax: ' + line.strip())
            name, value = match.group(2), match.group(3)
            require(name not in triggers, 'duplicate trigger: ' + name)
            require(value in (None, '{}', 'null', '~'), 'unsupported inline trigger value: ' + line.strip())
            triggers[name], current, deeper, pending = {}, name, None, None
            continue
        require(depth > level and current is not None, 'unsupported indentation: ' + line.strip())
        if current not in FILTERED_TRIGGERS:
            continue  # triggers that cannot select pull requests (inputs, schedules) are not filter-relevant
        if line.lstrip().startswith('- '):
            require(pending is not None and depth > deeper, 'unexpected sequence item: ' + line.strip())
            triggers[current][pending].append(_scalar(line.lstrip()[2:]))
            continue
        match = KEY.match(line)
        require(match is not None, 'unsupported trigger filter syntax: ' + line.strip())
        deeper = depth if deeper is None else deeper
        require(depth == deeper, 'inconsistent filter indentation: ' + line.strip())
        key, value = match.group(2), match.group(3)
        require(key in FILTER_KEYS, 'unrecognized trigger key: ' + key)
        require(key not in triggers[current], 'duplicate trigger key: ' + key)
        triggers[current][key] = _flow_sequence(value) if value else []
        pending = None if value else key
    for name, filters in triggers.items():
        require(all(filters.values()), f'empty filter list under {name}')
    return triggers


def selection_violations(text, probes=CRITICAL_PROBES):
    """A required science workflow must run on every pull request to main touching a science-critical path."""
    triggers = workflow_triggers(text)
    if 'pull_request' not in triggers:
        return ['pull_request: not triggered']
    violations = set()
    for name in ('pull_request', 'pull_request_target'):
        if name not in triggers:
            continue
        filters = triggers[name]
        if 'types' in filters and not PR_TYPES <= set(filters['types']):
            violations.add(f'{name}: types exclude ' + ','.join(sorted(PR_TYPES - set(filters['types']))))
        require(not ('branches' in filters and 'branches-ignore' in filters), 'unsupported filter combination')
        if 'branches' in filters and not _matches(BASE_BRANCH, filters['branches']):
            violations.add(f'{name}: branches exclude {BASE_BRANCH}')
        if 'branches-ignore' in filters and any(glob_regex(p).match(BASE_BRANCH) for p in filters['branches-ignore']):
            violations.add(f'{name}: branches-ignore excludes {BASE_BRANCH}')
        violations.update(f'{name}:{path}' for path in probes if not triggered(path, filters))
    return sorted(violations)


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


# T19-04: received commands are matched against admitted complete argv templates and never executed.
SHELLS = {'sh', 'bash', 'dash', 'zsh', 'env', 'sudo', 'xargs', 'eval'}
ENV_ALLOW = {'PYTHONDONTWRITEBYTECODE', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
             'RAYON_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'CARGO_INCREMENTAL', 'CUDA_VISIBLE_DEVICES', 'LANG', 'TZ'}
PATH_ROLES = {'input', 'output'}


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


def _argv_path(value, root, cwd):
    """An argv path token as an owned path: absolute tokens must lie under root, relative ones under cwd."""
    token = PurePosixPath(value)
    require('..' not in token.parts, 'argv path escapes owned root: ' + value)
    if token.is_absolute():
        for anchor in (PurePosixPath(root), PurePosixPath(Path(root).resolve())):
            if token.is_relative_to(anchor) and token != anchor:
                return owned_path(token.relative_to(anchor).as_posix(), root)
        raise ContractError('argv path escapes owned root: ' + value)
    return owned_path((PurePosixPath(cwd)/token).as_posix(), root)


def _bind_template(template, argv, root, cwd):
    require(type(template) is list and template and type(template[0]) is str, 'malformed admitted template')
    if len(template) != len(argv) or template[0] != argv[0]:
        return None
    bound = {'input': [], 'output': []}
    for token, value in zip(template[1:], argv[1:]):
        if type(token) is str:
            if token != value:
                return None
            continue
        fields(token, ['path'])
        require(token['path'] in PATH_ROLES, 'unknown template path role')
        path = _argv_path(value, root, cwd)
        if token['path'] == 'input':
            require(is_owned_file(root, path.relative_to(root).as_posix()), 'admitted input missing: ' + value)
        bound[token['path']].append(path)
    return bound


def check_command(record, root, admitted):
    """Validate a received command as data. `admitted` is the owner-approved list of complete argv templates:
    literal strings, or {'path': 'input'|'output'} placeholders bound to owned files. Never executes."""
    fields(record, ['argv', 'cwd', 'env', 'outputs'])
    argv = record['argv']
    require(type(argv) is list and argv and all(type(a) is str and a and '\x00' not in a for a in argv),
            'argv list required; shell strings are never executed')
    require(type(admitted) is list and admitted, 'admitted command templates required')
    require(PurePosixPath(argv[0]).name not in SHELLS, 'program not allowlisted')
    require(not (PurePosixPath(argv[0]).name.startswith('python') and '-c' in argv), 'inline code is not executable')
    root = Path(root)
    cwd = owned_path(record['cwd'], root)
    require(cwd.is_dir(), 'cwd missing')
    require(type(record['env']) is dict and set(record['env']) <= ENV_ALLOW and
            all(type(v) is str for v in record['env'].values()), 'environment not allowlisted')
    require(type(record['outputs']) is list and record['outputs'], 'declared outputs required')
    declared = [owned_path(p, root) for p in record['outputs']]
    require(len(set(declared)) == len(declared), 'duplicate declared output')
    for index, template in enumerate(admitted):
        bound = _bind_template(template, argv, root, record['cwd'])
        if bound is None:
            continue
        require(sorted(map(str, bound['output'])) == sorted(map(str, declared)),
                'argv outputs do not match declared outputs')
        return {'argv': argv, 'cwd': str(cwd), 'template': index, 'inputs': [str(p) for p in bound['input']],
                'outputs': [str(p) for p in declared], 'executed': False}
    raise ContractError('command does not match an admitted template')


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
        _parts(name)
        if expected['bytes'] > max_bytes:
            problems.append('oversized upload: ' + name)
            continue
        try:
            data = read_owned(root, name, max_bytes)
        except ReadRefused as error:
            problems.append(f'{error.kind} upload: ' + name if error.kind != 'unsafe' else f'unsafe upload: {name} ({error})')
            continue
        if len(data) != expected['bytes'] or raw_hash(data) != expected['sha256']:
            problems.append('corrupt upload: ' + name)
    for name in attempt['raw_failure']:
        if not is_owned_file(root, name):
            problems.append('raw failure not retained: ' + name)
    return {'status': 'incomplete' if problems else 'complete', 'problems': problems,
            'retained_raw_failure': list(attempt['raw_failure'])}


# T19-06: historical evidence is reuse, never a fresh execution. History is caller-pinned and complete.
HISTORY_OUTCOMES = {'passed', 'failed', 'error', 'not_run', 'incomplete'}


def validate_history(history, history_sha256):
    """A caller-pinned attempt history: {'schema': 1, 'attempts': {id: {input_sha256, artifacts, outcome}}}.
    An empty attempts map is a known first run; unavailable history is None and never reaches here."""
    require(scientific_hash(history) == digest(history_sha256), 'attempt history differs from its caller pin')
    fields(history, ['schema', 'attempts'])
    require(type(history['schema']) is int and history['schema'] == 1, 'unknown history schema')
    require(type(history['attempts']) is dict, 'attempt map required')
    unique_ids(history['attempts'])
    for record in history['attempts'].values():
        fields(record, ['input_sha256', 'artifacts', 'outcome'])
        digest(record['input_sha256'])
        require(type(record['artifacts']) is dict and record['artifacts'], 'historical artifacts required')
        for value in record['artifacts'].values():
            digest(value)
        require(record['outcome'] in HISTORY_OUTCOMES, 'unknown historical outcome')
    return history['attempts']


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


# Collector: S01 receipts from one raw transcript, then an independent re-check against trusted context.
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


def _write_new(directory_fd, name, data):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o444, dir_fd=directory_fd)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def publish_attempt(directory, catalog, log, argv, exit_code, attempt_id, expected, history, history_sha256):
    """Publish one immutable receipt per frozen case; pass/fail derives only from the transcript checked
    against the trusted expected inventory. history=None means unavailable: every executed case is error."""
    directory = Path(directory)
    require(not os.path.lexists(directory), 'fresh attempt directory required')
    require(type(log) is bytes and len(log) <= LIMITS['max_bytes'], 'raw transcript bytes required')
    expected = trusted_inventory(expected)
    parsed = collect_unittest(log.decode('utf-8'), expected)
    input_sha256 = catalog[0]['input_sha256']
    require(all(case['input_sha256'] == input_sha256 for case in catalog), 'catalog input identity differs')
    run = {'mode': 'fresh', 'attempt_id': attempt_id, 'input_sha256': input_sha256,
           'artifacts': {LOG: raw_hash(log)}, 'reused_from': None}
    if history is None:
        identifier(attempt_id)
        require(history_sha256 is None, 'unavailable history cannot carry a pin')
        freshness = 'attempt history unavailable; freshness unproven'
    else:
        attempts = validate_history(history, history_sha256)
        try:
            classify_run(run, input_sha256, attempts)
            freshness = None
        except ContractError as error:
            freshness = 'freshness refused: ' + str(error)
    context = (json.dumps({'schema': 1, 'attempt_id': attempt_id, 'expected_inventory': expected,
                           'expected_inventory_sha256': scientific_hash(expected), 'history_sha256': history_sha256,
                           'history': 'unavailable' if history is None else 'caller_pinned',
                           'freshness_refusal': freshness}, sort_keys=True) + '\n').encode()
    directory.mkdir(parents=True)
    directory_fd = os.open(directory, _DIR)
    try:
        _write_new(directory_fd, LOG, log)
        _write_new(directory_fd, CONTEXT, context)
        for case in catalog:
            tests = case_tests(case['id'], parsed['outcomes'])
            controls = {c: control_state(tests, c) for c in case['controls']}
            record = (json.dumps({'case_id': case['id'], 'run': run, 'tests': tests, 'suite_problems': parsed['problems'],
                                  'expected_inventory_sha256': scientific_hash(expected), 'history_sha256': history_sha256,
                                  'upstream': UPSTREAM.get(case['id'])}, sort_keys=True) + '\n').encode()
            _write_new(directory_fd, case['id'] + '.run.json', record)
            artifacts = {LOG: log, CONTEXT: context, case['id'] + '.run.json': record}
            values = list(controls.values())
            if case['id'] in UPSTREAM or values == ['not_run'] * len(values):
                execution, finding, code = 'not_run', 'not_applicable', None
                controls = {c: 'not_run' for c in case['controls']}  # synthetic outcomes stay in the run record
                reason = UPSTREAM.get(case['id'], 'no executed control for this case')
                counts = {'expected': 2, 'passed': 0, 'failed': 0, 'error': 0, 'not_run': 2}
            else:
                ok = (values == ['passed'] * len(values) and exit_code == 0 and parsed['execution'] == 'passed'
                      and freshness is None)
                execution = 'passed' if ok else 'failed' if 'failed' in values else 'error'
                finding, code = 'rejected_within_scope' if ok else 'inconclusive', exit_code
                reason = None if ok else 'not green: ' + '; '.join(parsed['problems'] + [freshness] * bool(freshness) + values)
                counts = {s: values.count(s) for s in ('passed', 'failed', 'error', 'not_run')}
                counts['expected'] = len(values)
            receipt = {'schema': 1, 'case_id': case['id'], 'input_sha256': case['input_sha256'],
                       'oracle_sha256': case['oracle_sha256'], 'execution': execution, 'finding': finding,
                       'argv': list(argv), 'exit_code': code, 'timed_out': False, 'complete': True,
                       'controls': controls, 'artifacts': {k: raw_hash(v) for k, v in artifacts.items()},
                       'counts': counts, 'reason': reason}
            publish_receipt(directory/(case['id'] + '.json'), receipt, case, artifacts)
    finally:
        os.close(directory_fd)
    return directory


def collect(catalog, directory, expected, history, history_sha256):
    """Resolve frozen receipts through S01 and re-derive every pass from the raw transcript, the trusted
    expected inventory and the caller-pinned history. history=None (unavailable) credits nothing."""
    directory = Path(directory).absolute()
    expected = trusted_inventory(expected)
    attempts = None if history is None else validate_history(history, history_sha256)
    names = list_owned(directory)
    receipts, artifacts = [], {}
    for name in names:
        if not name.endswith('.json') or name.endswith('.run.json') or name == CONTEXT:
            continue
        record = strict_loads(read_owned(directory, name, LIMITS['max_bytes']), LIMITS)
        require(type(record) is dict and type(record.get('artifacts')) is dict, 'receipt object required')
        require(CONTEXT in record['artifacts'] and LOG in record['artifacts'], 'receipt not bound to attempt context')
        receipts.append(record)
        for artifact in record['artifacts']:
            if artifact not in artifacts:
                artifacts[artifact] = read_owned(directory, artifact, LIMITS['max_bytes'])
    inventory = resolve_inventory(catalog, receipts, artifacts, bind_policy(catalog, LIMITS))
    context = strict_loads(artifacts[CONTEXT], LIMITS) if CONTEXT in artifacts else None
    require(context is None or (context['expected_inventory'] == expected
                                and context['expected_inventory_sha256'] == scientific_hash(expected)),
            'attempt inventory differs from the trusted expected inventory')
    execution = {cid: 'not_run' for cid in inventory['expected_ids']}
    credited = set()
    for record in receipts:
        execution[record['case_id']] = record['execution']
        if record['execution'] != 'passed':
            continue
        require(record['case_id'] not in UPSTREAM, 'upstream-dependent case cannot pass in this suite')
        run = strict_loads(artifacts[record['case_id'] + '.run.json'], LIMITS)
        require(run['case_id'] == record['case_id'] and run['run']['input_sha256'] == record['input_sha256']
                and run['expected_inventory_sha256'] == scientific_hash(expected), 'run record identity mismatch')
        require(run['run']['artifacts'][LOG] == raw_hash(artifacts[LOG]), 'transcript identity mismatch')
        parsed = collect_unittest(artifacts[LOG].decode('utf-8'), expected)
        tests = case_tests(record['case_id'], parsed['outcomes'])
        require(parsed['execution'] == 'passed' and tests == run['tests'] and
                all(control_state(tests, c) == 'passed' for c in ('positive', 'adverse')),
                'self-reported pass not supported by transcript')
        if attempts is None:
            continue
        require(run['history_sha256'] == history_sha256, 'attempt bound to a different history')
        classify_run(run['run'], record['input_sha256'], attempts)
        credited.add(record['case_id'])
    missing = sorted(set(inventory['expected_ids']) - credited)
    return {'schema': 1, 'unit': 'T19', 'expected_ids': inventory['expected_ids'],
            'denominator': len(inventory['expected_ids']), 'execution': execution,
            'findings': inventory['findings'], 'support': 'complete' if not missing else 'incomplete', 'missing': missing,
            'freshness': 'history_unavailable' if attempts is None else 'caller_pinned_history',
            'expected_tests': len(expected), 'upstream_not_run': sorted(set(UPSTREAM) & set(missing)),
            'tiers': {'T0_software': 'complete' if not missing else 'incomplete', 'T1_numerical': 'not_run_here',
                      'T2_laboratory': 'not_run_here', 'T3_research': 'not_activated'},
            'release_eligibility': 'not_evaluated_here', 'release_authorized': False, 'product_qualification': None}


def _history_arguments(parser):
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--history', help='caller-pinned complete attempt history JSON')
    group.add_argument('--history-unavailable', action='store_true', help='record that history is unavailable')
    parser.add_argument('--history-sha256', help='scientific hash pin of the history, from the caller')


def _history(args):
    if args.history_unavailable:
        require(args.history_sha256 is None, 'unavailable history cannot carry a pin')
        return None, None
    require(args.history_sha256 is not None, 'history pin required')
    return strict_loads(caller_file(args.history), LIMITS), args.history_sha256


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('catalog')
    commands.add_parser('inventory')
    publish = commands.add_parser('publish')
    publish.add_argument('--attempt', required=True)
    publish.add_argument('--log', required=True)
    publish.add_argument('--attempt-id', required=True)
    publish.add_argument('--exit-code', type=int, required=True)
    publish.add_argument('--argv-json', required=True, help='executed argv as a JSON list')
    _history_arguments(publish)
    check = commands.add_parser('check')
    check.add_argument('--receipts', required=True)
    _history_arguments(check)
    workflows = commands.add_parser('workflows')
    workflows.add_argument('paths', nargs='+')
    args = parser.parse_args(argv)
    try:
        if args.command == 'workflows':
            result = {path: selection_violations(caller_file(path).decode('utf-8')) for path in args.paths}
            ok = not any(result.values())
        else:
            catalog, expected = source_context()
            if args.command == 'catalog':
                result, ok = catalog, True
            elif args.command == 'inventory':
                result, ok = {'expected_inventory': expected, 'sha256': scientific_hash(expected)}, True
            else:
                history, pin = _history(args)
                if args.command == 'publish':
                    publish_attempt(args.attempt, catalog, caller_file(args.log), strict_loads(args.argv_json, LIMITS),
                                    args.exit_code, args.attempt_id, expected, history, pin)
                result = collect(catalog, args.attempt if args.command == 'publish' else args.receipts,
                                 expected, history, pin)
                ok = result['support'] == 'complete'
    except (ContractError, OSError, KeyError, TypeError, UnicodeError, SyntaxError) as error:
        print(json.dumps({'support': 'error', 'reason': str(error), 'release_authorized': False}))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
