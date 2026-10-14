"""Freeze the eleven S01-owned T00 cases from the S00 release policy."""
import ast
from pathlib import Path
import sys
from .contracts import ContractError, digest, raw_hash, require, scientific_hash, validate_case


def source_bundle(root):
    """Freeze executable local imports and initializer presence, excluding generated policy.

    Static local imports are limited to assurance and the inventory CLI/package parents.
    Python/stdlib/jsonschema runtime identities are separate; this is no hostile-code sandbox.
    """
    root = Path(root).absolute()
    paths = ['Cargo.lock', 'rust-toolchain.toml', 'crates/evidence/Cargo.toml',
             'crates/evidence/src/lib.rs', 'crates/evidence/src/identity.rs', 'crates/evidence/src/assurance.rs',
             'crates/evidence/tests/assurance_contract.rs', 'ops/ci/test_inventory.py',
             'assurance/policies/evidence-v1.json', 'assurance/schemas/evidence.v2.json',
             'assurance/schemas/test_case.v1.json', 'assurance/schemas/study_record.v1.json',
             'assurance/schemas/observation_record.v1.json', 'assurance/schemas/qualification_result.v1.json']
    # The schema control reads the complete shipped schema inventory. New
    # record schemas must withdraw old receipts when their bytes change, too.
    paths.extend(path.relative_to(root).as_posix()
                 for path in (root/'assurance/schemas').glob('*.json'))
    python_paths = {'ops/ci/test_inventory.py'}
    require((root/'assurance').is_dir(), 'assurance source root missing')
    for path in (root/'assurance').rglob('*'):
        require(not path.is_symlink(), 'symlink in local source closure')
        require(path.suffix not in ('.so', '.pyd', '.pth') and
                (path.suffix != '.pyc' or '__pycache__' in path.parts), 'unsupported local executable input')
        if path.suffix == '.py' and path.is_file(): python_paths.add(path.relative_to(root).as_posix())
    initializers = set()
    for name in python_paths:
        parent = Path(name).parent
        while parent != Path('.'):
            initializers.add((parent/'__init__.py').as_posix()); parent = parent.parent
    # External package initializers execute before CLI imports, even when previously absent.
    python_paths.update(name for name in initializers if (root/name).is_file())
    paths = sorted(set(paths) | python_paths | initializers)
    for name in paths:
        path = root/name
        require(path.resolve().is_relative_to(root.resolve()) and
                not any(parent.is_symlink() for parent in [path, *path.parents]), 'symlink/import escape')
        require(path.is_file() or name in initializers and not path.exists(), 'local input missing or unsupported')
    for name in sorted(python_paths):
        try: tree = ast.parse((root/name).read_bytes(), filename=name)
        except (SyntaxError, UnicodeError) as error: raise ContractError('invalid local Python source: '+name) from error
        package = list(Path(name).parent.parts)
        for node in ast.walk(tree):
            require(not isinstance(node, ast.Call) or not (
                isinstance(node.func, ast.Name) and node.func.id == '__import__' or
                isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module'), 'unsupported dynamic import')
            if isinstance(node, ast.Import): modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                require(node.level <= len(package), 'relative import escape')
                base = package[:len(package)-node.level+1] if node.level else []
                module = '.'.join(base + (node.module.split('.') if node.module else []))
                modules = [module]
                if (root/Path(*module.split('.'))).is_dir():
                    modules += [module+'.'+alias.name for alias in node.names
                                if (root/Path(*module.split('.'))/(alias.name+'.py')).is_file()]
            else: continue
            for module in modules:
                top = module.split('.')[0]; local = root/Path(*module.split('.'))
                if (root/top).exists() or (root/(top+'.py')).exists():
                    require(top == 'assurance' and (local.is_dir() or (local.with_suffix('.py')).is_file()) or
                            (local.with_suffix('.py')).relative_to(root).as_posix() in python_paths or
                            module in ('ops', 'ops.ci'), 'unsupported local import: '+module)
                else:
                    require(top in sys.stdlib_module_names or top == 'jsonschema', 'unsupported external import: '+module)
    return {name: raw_hash((root/name).read_bytes()) if (root/name).is_file() else None for name in paths}


def build_catalog(release_policy, input_sha256):
    digest(input_sha256)
    records = release_policy['software_contracts']['T00_frozen']
    require(len(records) == 11, 'all eleven T00 groups required')
    catalog = []
    for record in records:
        case = {'schema': 1, 'id': record['id'], 'required': True,
                'evidence_class': 'deterministic_contract', 'input_sha256': input_sha256,
                'oracle_sha256': record['definition_sha256'], 'controls': ['positive', 'adverse'],
                'disabled_reason': None, 'claim_enabled': True}
        catalog.append(validate_case(case))
    return catalog


def bind_policy(catalog, limits):
    return {'schema': 1, 'canonical_wire': 'jarambit.science.canonical.v1',
            'catalog_sha256': scientific_hash(catalog), **limits,
            'authority': 'offline software support only; Rust resolves product claims'}
