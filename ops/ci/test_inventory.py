#!/usr/bin/env python3
"""Check frozen software-case receipts; never execute their argv or grant product qualification."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from assurance.testing.catalog import build_catalog, source_bundle
from assurance.testing.contracts import ContractError, raw_hash, require, resolve_inventory, scientific_hash, strict_loads


def check(catalog_path, receipts_dir, policy_path):
    limits = {'max_bytes': 1048576, 'max_depth': 64, 'max_nodes': 100000}
    policy = strict_loads(Path(policy_path).read_bytes(), limits)
    require(policy['schema'] == 1 and type(policy['schema']) is int, 'unknown policy schema')
    require(policy['canonical_wire'] == 'jarambit.science.canonical.v1', 'unknown canonical wire')
    release_bytes = (ROOT/'assurance/policies/release-v1.json').read_bytes()
    require(raw_hash(release_bytes) == policy['release_policy_sha256'], 'release policy changed')
    sources = source_bundle(ROOT)
    require(sources == policy['source_bundle'] and scientific_hash(sources) == policy['source_input_sha256'],
            'source/input mismatch; fresh policy/receipts required')
    catalog = strict_loads(Path(catalog_path).read_bytes(), policy)
    expected = build_catalog(strict_loads(release_bytes, limits), policy['source_input_sha256'])
    require(catalog == expected, 'catalog differs from independently frozen T00 inventory')
    receipts = []
    artifacts = {}
    directory = Path(receipts_dir).resolve()
    require(directory.is_dir(), 'receipt directory missing')
    for path in sorted(directory.glob('*.json')):
        record = strict_loads(path.read_bytes(), policy)
        receipts.append(record)
        for name in record.get('artifacts', {}):
            artifact = (directory/name).resolve()
            require(artifact.is_relative_to(directory) and artifact.is_file(), 'artifact outside receipt root or missing')
            artifacts[name] = artifact.read_bytes()
    return resolve_inventory(catalog, receipts, artifacts, policy)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True)
    parser.add_argument('--receipts', required=True)
    parser.add_argument('--policy', required=True)
    args = parser.parse_args(argv)
    try:
        result = check(args.catalog, args.receipts, args.policy)
    except (ContractError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'support': 'error', 'reason': str(error), 'product_qualification': None}, allow_nan=False))
        return 1
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if result['support'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
