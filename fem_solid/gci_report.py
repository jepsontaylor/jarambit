"""Pure ordinary-GCI admission and read-only historical reclassification; CLI writes stdout."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from assurance.testing.contracts import ContractError, finite, raw_hash, require, strict_loads, unique_ids
from fem_solid.gci import Estimate, FitStatus, METHOD, Observable, Level, MeshRef, compute_gci, validate_sequence

LIMITS = {'max_bytes': 1048576, 'max_depth': 64, 'max_nodes': 100000}
THRESHOLD = 0.03


@dataclass(frozen=True)
class ExpectedRecord:
    id: str
    observable: Observable


@dataclass(frozen=True)
class Record:
    id: str
    estimate: Estimate
    sf_base: float


def sf_band(base, relative_error):
    base, error = finite(base), finite(relative_error)
    require(base > 0 and 0 <= error < 1, 'invalid_sf_band')
    lo, hi = finite(base/(1+error)), finite(base/(1-error))
    require(0 < lo <= base <= hi, 'invalid_sf_band')
    return {'fine': base, 'lo': lo, 'hi': hi}


def build_report(records, expected):
    """Expected scope is supplied by the trusted caller, never discovered from output files."""
    rows, reasons = [], []
    try:
        require(type(expected) in (list, tuple) and bool(expected), 'empty_expected_inventory')
        require(all(isinstance(x, ExpectedRecord) and isinstance(x.observable, Observable) for x in expected), 'invalid_expected_inventory')
        require(type(records) in (list, tuple) and all(isinstance(x, Record) for x in records), 'invalid_records')
        try:
            unique_ids(x.id for x in expected)
            unique_ids(x.id for x in records)
        except UnicodeError as error:
            raise ContractError('invalid_unicode_identity') from error
        wanted = {x.id: x for x in expected}
        require({x.id for x in records} == set(wanted), 'missing_or_extra_record')
    except (ContractError, TypeError) as error:
        return {'status': 'UNVERIFIED', 'ordinary_gci_supported': False, 'rows': [],
                'reasons': [str(error)], 'numerical_verification': 'not_established',
                'physical_validation': 'not_performed'}
    for record in records:
        try:
            est = record.estimate
            require(isinstance(est, Estimate) and est.method_id == METHOD, 'unsupported_method')
            require(est.fit_status == FitStatus.VALID and est.monotone is True and
                    est.sequence_valid is True and est.observable_valid is True, 'inadmissible_fit_or_metadata')
            require(finite(est.p) > 0, 'invalid_order'); finite(est.f_ext)
            require(len(est.levels) == 3, 'missing_levels')
            ratio = finite(est.levels[1].h)/finite(est.levels[0].h)
            require(validate_sequence(est.levels, ratio) is None, 'invalid_sequence')
            require(est.levels[0].observable == wanted[record.id].observable, 'expected_observable_mismatch')
            error = finite(est.gci_fine)
            require(0 <= error <= THRESHOLD, 'relative_gci_outside_threshold')
            band = sf_band(record.sf_base, error)
            rows.append({'id': record.id, 'status': 'supported_within_scope', 'gci_fine': error,
                         'SF': band, 'estimate': est.to_dict()})
        except (ContractError, AttributeError, TypeError, OverflowError, ZeroDivisionError) as error:
            reasons.append(record.id+':'+str(error))
            rows.append({'id': record.id, 'status': 'UNVERIFIED', 'reason': str(error)})
    return {'status': 'PASS' if not reasons else 'UNVERIFIED', 'ordinary_gci_supported': not reasons,
            'rows': rows, 'reasons': reasons, 'numerical_verification': 'not_established',
            'physical_validation': 'not_performed', 'scope': 'relative-GCI software admission only'}


def reclassify_history(paths):
    """No old bytes are changed or retroactively granted new execution/physical status."""
    rows = []
    for path in paths:
        raw = Path(path).read_bytes()
        row = {'source': str(path), 'raw_sha256': raw_hash(raw), 'status': 'UNVERIFIED',
               'physical_design_verdict': None}
        try:
            old = strict_loads(raw, LIMITS)
            require(type(old) is dict, 'invalid_historical_root')
            require(all(name in old for name in ('vm_nodal_max_MPa', 'vm_nodal_avg_MPa')),
                    'missing_historical_observable')
            require(all(type(old[name]) is dict for name in ('vm_nodal_max_MPa', 'vm_nodal_avg_MPa')),
                    'invalid_historical_observables')
            row['id'] = old['design']
            row['observables'] = {}
            for name in ('vm_nodal_max_MPa', 'vm_nodal_avg_MPa'):
                field = old[name]
                reason = 'oscillatory_legacy_record' if field.get('monotone') is not True or field.get('p') is None else 'historical_mesh_observable_execution_binding_missing'
                row['observables'][name] = {'legacy_raw': field, 'status': 'UNVERIFIED', 'reason': reason}
        except (ContractError, KeyError, TypeError) as error:
            row['reason'] = 'invalid_historical_record:'+str(error)
        rows.append(row)
    return {'scope': 'historical reclassification only', 'rows': rows,
            'ordinary_gci_supported': False, 'physical_design_verdict': None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--historical', nargs='+')
    inputs.add_argument('--records', nargs='+')
    parser.add_argument('--inventory')
    args = parser.parse_args(argv)
    try:
        if args.historical:
            result = reclassify_history(args.historical)
        else:
            require(args.inventory is not None, 'explicit_inventory_required')
            policy = strict_loads(Path(args.inventory).read_bytes(), LIMITS)
            require(policy['schema'] == 2 and type(policy['schema']) is int and
                    policy['method_id'] == METHOD and finite(policy['threshold']) == THRESHOLD, 'unsupported_inventory_policy')
            observable = Observable(**policy['observable'])
            expected = [ExpectedRecord(name, observable) for name in policy['expected_designs']]
            records = []
            for path in args.records:
                raw = strict_loads(Path(path).read_bytes(), LIMITS)
                require(set(raw) == {'schema', 'id', 'values', 'r', 'fs', 'levels', 'sf_base'} and
                        type(raw['schema']) is int and raw['schema'] == 2, 'unsupported_record')
                require(type(raw['values']) is list and len(raw['values']) == 3 and
                        type(raw['levels']) is list and len(raw['levels']) == 3, 'three_levels_required')
                sequence = []
                for level in raw['levels']:
                    require(set(level) == {'mesh', 'h', 'observable', 'refinement'}, 'invalid_level_fields')
                    sequence.append(Level(MeshRef(**level['mesh']), level['h'], Observable(**level['observable']), level['refinement']))
                estimate = compute_gci(*raw['values'], raw['r'], raw['fs'], levels=tuple(sequence))
                records.append(Record(raw['id'], estimate, raw['sf_base']))
            result = build_report(records, expected)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ContractError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'UNVERIFIED', 'reason': str(error)}))
        return 1
    return 0 if args.historical or result['ordinary_gci_supported'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
