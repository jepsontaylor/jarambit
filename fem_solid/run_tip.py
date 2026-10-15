"""Identity-bound fresh-attempt software contracts. No default solver execution is admitted."""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from assurance.testing.contracts import ContractError, digest, finite, require, scientific_hash, strict_loads

LIMITS = {'max_bytes': 1048576, 'max_depth': 64, 'max_nodes': 100000}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def versions():
    return {'python': platform.python_version(), 'solver': 'not_run; no provider admitted'}


@dataclass(frozen=True)
class Identity:
    input: str
    code: str
    config: str
    image_digest: str
    mesh: str
    material: str
    observable: str

    def check(self):
        for key, value in asdict(self).items():
            if key == 'image_digest':
                require(type(value) is str and value.startswith('sha256:'), 'immutable_image_digest_required')
                digest(value[7:])
            else: digest(value)
        return self

    def to_dict(self):
        self.check(); return asdict(self)


def atomic_bytes(path, data):
    """No-clobber durable link; failures retain this invocation's unique partial evidence."""
    path = Path(path)
    temp = path.with_name(path.name+'.pending.'+uuid.uuid4().hex)
    linked = False
    try:
        with temp.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.link(temp, path); linked = True
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        temp.unlink()
    except Exception:
        if linked and temp.exists() and path.exists() and temp.stat().st_ino == path.stat().st_ino:
            path.unlink()
        raise


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2, allow_nan=False)+'\n').encode())


def document(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'missing_or_symlink_artifact')
    return strict_loads(path.read_bytes(), LIMITS)


def verify_output(output, completion, request):
    require(set(output) == {'schema', 'attempt_id', 'identity', 'data'} and
            type(output['schema']) is int and output['schema'] == 2 and type(output['data']) is dict, 'invalid_output_schema')
    require(output['attempt_id'] == request['attempt_id'] and output['identity'] == request['identity'], 'output_identity_mismatch')
    Identity(**output['identity']).check()
    require(set(completion) == {'schema', 'attempt_id', 'identity_sha256', 'output_sha256', 'exit_code'} and
            type(completion['schema']) is int and completion['schema'] == 1 and
            type(completion['exit_code']) is int and completion['exit_code'] == 0, 'invalid_completion')
    require(completion['attempt_id'] == request['attempt_id'] and
            completion['identity_sha256'] == scientific_hash(request['identity']), 'completion_identity_mismatch')


def load_completed(directory, identity):
    identity.check(); directory = Path(directory)
    require(not (directory/'failure.json').exists(), 'failed_attempt_not_reusable')
    publication = document(directory/'COMPLETED.json')
    require(set(publication) == {'schema', 'attempt_id', 'output_sha256', 'manifest_sha256'} and
            type(publication['schema']) is int and publication['schema'] == 1, 'invalid_publication')
    request = document(directory/'request.json')
    manifest = document(directory/'manifest.json'); output = document(directory/'result.json')
    require(set(request) == {'schema', 'attempt_id', 'identity', 'argv'} and
            type(request['schema']) is int and request['schema'] == 1, 'invalid_request')
    require(set(manifest) == {'schema', 'attempt_id', 'identity', 'argv', 'exit_code',
                             'execution_kind', 'output_sha256', 'wall_s'}, 'invalid_manifest_fields')
    completion = document(directory/'completion.pending.json')
    verify_output(output, completion, request)
    require(output['identity'] == identity.to_dict() and request['identity'] == identity.to_dict(), 'cache_identity_mismatch')
    require(manifest['schema'] == 2 and type(manifest['schema']) is int and
            manifest['attempt_id'] == request['attempt_id'] == publication['attempt_id'] and
            manifest['identity'] == identity.to_dict() and manifest['argv'] == request['argv'] and
            type(manifest['exit_code']) is int and manifest['exit_code'] == 0 and
            manifest['execution_kind'] == 'mock', 'invalid_execution_manifest')
    output_sha = sha(directory/'result.json')
    require(publication['output_sha256'] == completion['output_sha256'] == manifest['output_sha256'] == output_sha and
            publication['manifest_sha256'] == sha(directory/'manifest.json'), 'published_artifact_hash_mismatch')
    return output


def reuse(directory, identity):
    output = load_completed(directory, identity)
    return {'mode': 'reuse', 'execution': {'kind': 'mock', 'invoked': False, 'fresh': False},
            'numerical_finding': 'not_run', 'physical_validation': 'not_performed',
            'directory': str(directory), 'identity': identity.to_dict(), 'data': output['data']}


def fresh_attempt(root, identity, argv, execute, *, verify_inputs=None):
    """The injected callback is a software test double, never evidence of a numerical solve."""
    identity.check()
    require(callable(execute), 'fresh_solver_execution_not_admitted')
    require(type(argv) is list and bool(argv) and all(type(x) is str and bool(x) for x in argv), 'invalid_invocation')
    root = Path(root)
    missing = []; parent = root
    while not parent.exists(): missing.append(parent); parent = parent.parent
    root.mkdir(parents=True, exist_ok=True)
    for created in reversed(missing):
        fd = os.open(created.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    attempt_id = uuid.uuid4().hex
    directory = root/('attempt-'+attempt_id); directory.mkdir()
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    temporary = directory/'result.pending.json'; completion_path = directory/'completion.pending.json'
    actual_argv = list(argv)+[str(temporary)]
    request = {'schema': 1, 'attempt_id': attempt_id, 'identity': identity.to_dict(), 'argv': actual_argv}
    atomic_json(directory/'request.json', request); request_sha = sha(directory/'request.json')
    started = time.time()
    committed = False
    try:
        code = execute(list(actual_argv), temporary, completion_path, document(directory/'request.json'))
        require(type(code) is int and code == 0, 'nonzero_or_invalid_execution_exit')
        require(sha(directory/'request.json') == request_sha, 'request_changed_during_execution')
        raw = temporary.read_bytes(); output = document(temporary); completion = document(completion_path)
        verify_output(output, completion, request)
        require(completion['output_sha256'] == hashlib.sha256(raw).hexdigest(), 'completion_output_hash_mismatch')
        if verify_inputs is not None: require(verify_inputs(), 'inputs_changed_during_execution')
        manifest = {'schema': 2, 'attempt_id': attempt_id, 'identity': identity.to_dict(),
                    'argv': actual_argv, 'exit_code': code, 'execution_kind': 'mock',
                    'output_sha256': hashlib.sha256(raw).hexdigest(), 'wall_s': time.time()-started}
        atomic_bytes(directory/'result.json', raw)
        atomic_json(directory/'manifest.json', manifest)
        atomic_json(directory/'COMPLETED.json', {'schema': 1, 'attempt_id': attempt_id,
                    'output_sha256': sha(directory/'result.json'), 'manifest_sha256': sha(directory/'manifest.json')})
        committed = True
        load_completed(directory, identity)
    except (OSError, ContractError, ValueError, TypeError, KeyError) as error:
        if committed: (directory/'COMPLETED.json').unlink()
        try: atomic_json(directory/'failure.json', {'status': 'incomplete', 'reason': str(error), 'execution_kind': 'mock'})
        except OSError: pass  # original partial files remain even if a failure record cannot be written
        raise
    return {'mode': 'fresh_mock', 'execution': {'kind': 'mock', 'invoked': True, 'fresh': True},
            'numerical_finding': 'not_run', 'physical_validation': 'not_performed',
            'directory': str(directory), 'identity': identity.to_dict(), 'data': output['data']}


def code_identity():
    paths = {str(p.relative_to(ROOT)) for p in (ROOT/'fem_solid').rglob('*.py')}
    paths.update(['fem_solid/__init__.py', 'fem_solid/tests/__init__.py', 'assurance/__init__.py',
                  'assurance/testing/__init__.py', 'assurance/testing/contracts.py'])
    for name in paths:
        path = ROOT/name
        require(not path.is_symlink() and path.resolve().is_relative_to(ROOT), 'unsupported_code_import_escape')
    return scientific_hash({name: sha(ROOT/name) if (ROOT/name).is_file() else None for name in sorted(paths)})


def parameters(rc='30', nl='4', nsub='1', patch='2.0'):
    require(all(type(value) in (str, int, float) for value in (rc, nl, nsub, patch)), 'invalid_parameter_type')
    values = {'R_CUT': finite(float(rc)), 'NLAYER': int(nl), 'NSUB': int(nsub),
              'PATCH_mm': finite(float(patch)), 'T_Nmm': 1820.0}
    require(values['R_CUT'] > 0 and values['NLAYER'] > 0 and values['NSUB'] >= 0 and values['PATCH_mm'] > 0, 'invalid_parameters')
    require(values['NLAYER'] == finite(float(nl)) and values['NSUB'] == finite(float(nsub)), 'integer_resolution_required')
    return values


def bound_identity(d1, config, image_digest, mesh, material, observable):
    d1 = Path(d1); gl = d1.with_name(d1.name.replace('_D1.json', '_grind_law.json'))
    require(d1.name.endswith('_D1.json') and d1.is_file() and gl.is_file(), 'missing input')
    return Identity(scientific_hash({d1.name: sha(d1), gl.name: sha(gl)}), code_identity(),
                    scientific_hash(config), image_digest, mesh, material, observable).check()


def execute_level(d1, out, rc, nl, nsub, patch, *, identity, execute):
    config = parameters(rc, nl, nsub, patch)
    require(isinstance(identity, Identity), 'explicit_identity_required')
    current = lambda: bound_identity(d1, config, identity.image_digest, identity.mesh, identity.material, identity.observable)
    require(identity == current(), 'input_code_config_identity_mismatch')
    argv = [sys.executable, str(ROOT/'fem_solid/tip_solid.py'), str(d1), str(rc), str(nl), str(nsub)]
    return fresh_attempt(out, identity, argv, execute, verify_inputs=lambda: identity == current())


def main(args, *, identity=None, execute=None):
    if len(args) < 2: print(__doc__, file=sys.stderr); return 2
    d1, out = args[:2]
    gl = d1.replace('_D1.json', '_grind_law.json')
    for need in (d1, gl):
        if not d1.endswith('_D1.json') or not Path(need).is_file():
            print('run_tip: missing input '+repr(need)+' (need <design>_D1.json and <design>_grind_law.json)', file=sys.stderr); return 2
    rc, nl, nsub, patch = (args[2:3] or ['30'])[0], (args[3:4] or ['4'])[0], (args[4:5] or ['1'])[0], (args[5:6] or ['2.0'])[0]
    if execute is None:
        print('run_tip: fresh solver execution not admitted; existing OUT is preserved', file=sys.stderr); return 3
    try:
        result = execute_level(d1, str(out)+'.attempts', rc, nl, nsub, patch, identity=identity, execute=execute)
    except (OSError, ContractError, ValueError, TypeError) as error:
        print('run_tip: '+str(error), file=sys.stderr); return 1
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
