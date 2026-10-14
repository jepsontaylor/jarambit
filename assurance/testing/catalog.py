"""Freeze the eleven S01-owned T00 cases from the S00 release policy."""
from pathlib import Path
from .contracts import digest, raw_hash, require, scientific_hash, validate_case


def source_bundle(root):
    """Exact input/evaluator/schema inventory, independent of discovered output files."""
    paths = ['Cargo.lock', 'rust-toolchain.toml', 'crates/evidence/Cargo.toml',
             'crates/evidence/src/lib.rs', 'crates/evidence/src/identity.rs', 'crates/evidence/src/assurance.rs',
             'crates/evidence/tests/assurance_contract.rs', 'assurance/testing/contracts.py',
             'assurance/testing/catalog.py', 'assurance/testing/receipt.py',
             'assurance/testing/tests/test_contracts.py', 'ops/ci/test_inventory.py',
             'assurance/policies/evidence-v1.json', 'assurance/schemas/evidence.v2.json',
             'assurance/schemas/test_case.v1.json', 'assurance/schemas/study_record.v1.json',
             'assurance/schemas/observation_record.v1.json', 'assurance/schemas/qualification_result.v1.json']
    return {p: raw_hash((Path(root)/p).read_bytes()) for p in paths}


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
