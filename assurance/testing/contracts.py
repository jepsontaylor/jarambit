"""Strict records and software-test support; no independent product truth engine."""
import hashlib
import json
import math
import struct
import unicodedata


class ContractError(ValueError):
    pass


EXECUTIONS = {'passed', 'failed', 'error', 'not_run'}
FINDINGS = {'supported_within_scope', 'rejected_within_scope', 'inconclusive', 'not_applicable'}
CLASSES = {'deterministic_contract', 'numerical_verification', 'physical_validation', 'research'}


def require(condition, reason):
    if not condition:
        raise ContractError(reason)


def finite(value):
    require(type(value) in (int, float), 'numeric type; booleans/strings forbidden')
    try:
        require(math.isfinite(value), 'nonfinite number')
    except OverflowError as error:
        raise ContractError('numeric overflow') from error
    if type(value) is int:
        require(int(float(value)) == value, 'inexact integer scalar')
    return float(value)


def identifier(value):
    require(type(value) is str and value.strip() and len(value.encode('utf-8')) <= 512,
            'invalid identity')
    require(not any(unicodedata.category(c) == 'Cc' for c in value), 'control in identity')
    return value


def unique_ids(values):
    require(unicodedata.unidata_version == '15.0.0', 'unsupported Unicode data profile')
    seen = set()
    for value in values:
        identifier(value)
        normalized = unicodedata.normalize('NFC', value)
        require(normalized not in seen, 'duplicate or normalization-colliding identity')
        seen.add(normalized)


def unique_keys(values):
    """General JSON keys are not domain IDs: preserve empty/control/long valid UTF-8 keys."""
    require(unicodedata.unidata_version == '15.0.0', 'unsupported Unicode data profile')
    seen = set()
    for value in values:
        require(type(value) is str, 'string key required')
        value.encode('utf-8')
        normalized = unicodedata.normalize('NFC', value)
        require(normalized not in seen, 'duplicate or normalization-colliding key')
        seen.add(normalized)


def digest(value):
    require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value),
            'invalid SHA-256')
    return value


def raw_hash(data):
    require(type(data) is bytes, 'raw bytes required')
    return hashlib.sha256(data).hexdigest()


def canonical_wire(value):
    """Frozen Rust wire; integer tokens retain u64/i64 identity, floats retain IEEE bits."""
    if value is None:
        return b'n'
    if type(value) is bool:
        return b't' if value else b'f'
    if type(value) is str:
        data = value.encode('utf-8')
        return b's' + str(len(data)).encode() + b':' + data
    if type(value) is int:
        require(-(1 << 63) <= value < (1 << 64), 'integer out of range')
        return (b'u' if value >= 0 else b'i') + str(value).encode() + b';'
    if type(value) is float:
        finite(value)
        return b'd' + struct.pack('>d', value).hex().encode() + b';'
    if type(value) is list:
        return b'a' + str(len(value)).encode() + b':' + b''.join(canonical_wire(x) for x in value)
    if type(value) is dict:
        require(all(type(k) is str for k in value), 'string keys required')
        unique_keys(value)
        return b'o' + str(len(value)).encode() + b':' + b''.join(
            canonical_wire(k) + canonical_wire(value[k]) for k in sorted(value, key=lambda k: k.encode('utf-8')))
    raise ContractError('unsupported canonical type')


def scientific_hash(value):
    return raw_hash(canonical_wire(value))


def strict_loads(data, policy):
    require(type(data) in (bytes, str), 'JSON bytes/text required')
    require(len(data) <= policy['max_bytes'], 'payload too large')
    try:
        if type(data) is str:
            raw = data.encode('utf-8')
        else:
            raw = data
        require(len(raw) <= policy['max_bytes'], 'payload too large')
        text = raw.decode('utf-8', errors='strict')
    except UnicodeError as error:
        raise ContractError('invalid UTF-8 or Unicode scalar') from error

    def pairs(items):
        unique_keys(k for k, _ in items)
        return dict(items)

    def integer(token):
        if token == '-0':
            return -0.0
        value = int(token)
        require(-(1 << 63) <= value < (1 << 64), 'integer out of range')
        return value

    def floating(token):
        value = finite(float(token))
        mantissa = token.lower().split('e')[0]
        require(value != 0 or not any(c in '123456789' for c in mantissa), 'number underflow')
        return value

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_int=integer,
                           parse_float=floating, parse_constant=lambda token: finite(float(token)))
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise ContractError(str(error)) from error
    nodes = 0

    def walk(v, depth):
        nonlocal nodes
        nodes += 1
        require(depth <= policy['max_depth'] and nodes <= policy['max_nodes'], 'payload bounds')
        if type(v) is float:
            finite(v)
        if type(v) is str:
            try:
                v.encode('utf-8')
            except UnicodeError as error:
                raise ContractError('invalid Unicode scalar') from error
        if type(v) in (dict, list):
            for item in (v.values() if type(v) is dict else v):
                walk(item, depth + 1)

    walk(value, 0)
    return value


def fields(record, expected):
    require(type(record) is dict and set(record) == set(expected), 'unknown or missing fields')


def validate_case(case):
    fields(case, ['schema', 'id', 'required', 'evidence_class', 'input_sha256', 'oracle_sha256',
                  'controls', 'disabled_reason', 'claim_enabled'])
    require(type(case['schema']) is int and case['schema'] == 1, 'unknown case schema')
    identifier(case['id'])
    require(type(case['required']) is bool and type(case['claim_enabled']) is bool, 'boolean policy fields required')
    require(case['evidence_class'] in CLASSES, 'unknown evidence class')
    digest(case['input_sha256']); digest(case['oracle_sha256'])
    require(type(case['controls']) is list and set(case['controls']) == {'positive', 'adverse'}
            and len(case['controls']) == 2, 'paired controls required')
    if not case['required'] and not case['claim_enabled']:
        identifier(case['disabled_reason'])
    return case


def validate_standard_scope(observation, descriptor):
    """Method applicability is distinct from compliance; S14 owns actual standard evidence."""
    fields(descriptor, ['standard', 'edition', 'method', 'specimens', 'source_sha256'])
    fields(observation, ['standard', 'edition', 'method', 'specimen'])
    digest(descriptor['source_sha256'])
    require(type(descriptor['specimens']) is list and descriptor['specimens'], 'standard scope missing')
    unique_ids(descriptor['specimens'])
    for name in ['standard', 'edition', 'method']:
        identifier(descriptor[name])
        require(observation[name] == descriptor[name], 'standard edition/method mismatch')
    require(observation['specimen'] in descriptor['specimens'], 'standard specimen scope mismatch')
    return {'applicability': 'matched', 'physical_compliance': None}


def validate_receipt(receipt, case, artifacts):
    validate_case(case)
    fields(receipt, ['schema', 'case_id', 'input_sha256', 'oracle_sha256', 'execution', 'finding',
                     'argv', 'exit_code', 'timed_out', 'complete', 'controls', 'artifacts', 'counts', 'reason'])
    require(type(receipt['schema']) is int and receipt['schema'] == 1, 'unknown receipt schema')
    require(receipt['case_id'] == case['id'], 'case identity mismatch')
    require(receipt['input_sha256'] == case['input_sha256'] and receipt['oracle_sha256'] == case['oracle_sha256'],
            'input/oracle identity mismatch')
    require(receipt['execution'] in EXECUTIONS and receipt['finding'] in FINDINGS, 'unknown status')
    require(type(receipt['complete']) is bool and receipt['complete'], 'incomplete attempt')
    require(type(receipt['timed_out']) is bool, 'timeout flag required')
    require(type(receipt['argv']) is list and receipt['argv'] and all(type(a) is str and a for a in receipt['argv']),
            'executed argv required')
    require(type(receipt['artifacts']) is dict and receipt['artifacts'], 'artifact inventory required')
    for name, expected in receipt['artifacts'].items():
        digest(expected)
        require(name in artifacts and raw_hash(artifacts[name]) == expected, 'artifact integrity mismatch')
    fields(receipt['counts'], ['expected', 'passed', 'failed', 'error', 'not_run'])
    counts = receipt['counts']
    require(all(type(v) is int and v >= 0 for v in counts.values()), 'invalid result counts')
    require(counts['expected'] > 0 and counts['expected'] == sum(counts[k] for k in EXECUTIONS),
            'result counts do not reconcile')
    require(counts['expected'] == len(case['controls']), 'control count inventory mismatch')
    if receipt['execution'] == 'not_run':
        require(receipt['exit_code'] is None and receipt['reason'], 'unavailable reason required')
        require(receipt['finding'] == 'not_applicable' and counts['not_run'] == counts['expected'],
                'unexecuted finding')
    else:
        require(type(receipt['exit_code']) is int, 'exit code required')
        if receipt['execution'] == 'passed':
            require(receipt['exit_code'] == 0 and not receipt['timed_out'], 'failed execution claimed pass')
            require(counts['passed'] == counts['expected'], 'passed execution missing results')
            require(type(receipt['controls']) is dict and set(receipt['controls']) == set(case['controls'])
                    and all(s == 'passed' for s in receipt['controls'].values()), 'controls missing or failed')
    return receipt


def resolve_inventory(catalog, receipts, artifacts, policy):
    require(type(catalog) is list and catalog, 'expected catalog required')
    require(scientific_hash(catalog) == policy['catalog_sha256'], 'frozen catalog mismatch')
    for case in catalog:
        validate_case(case)
    unique_ids(c['id'] for c in catalog)
    unique_ids(r['case_id'] for r in receipts)
    expected = {c['id']: c for c in catalog}
    supplied = {r['case_id']: r for r in receipts}
    require(set(supplied) <= set(expected), 'unsupported extra receipt')
    missing, unavailable, findings = [], [], {}
    for cid, case in expected.items():
        if cid not in supplied:
            if case['required'] or case['claim_enabled']:
                missing.append(cid)
            continue
        receipt = validate_receipt(supplied[cid], case, artifacts)
        findings[cid] = receipt['finding']
        if receipt['execution'] != 'passed':
            if case['required'] or case['claim_enabled']:
                missing.append(cid)
            else:
                require(case['disabled_reason'] and receipt['reason'], 'disabled branch reason missing')
                unavailable.append(cid)
    require(any(c['required'] for c in catalog), 'no required coverage')
    return {'schema': 1, 'support': 'incomplete' if missing else 'complete', 'missing': sorted(missing),
            'optional_unavailable': sorted(unavailable), 'findings': findings,
            'expected_ids': sorted(expected), 'product_qualification': None}


def resolve_claim_support(claim, catalog, receipts, artifacts, policy):
    """Only software execution support. Numeric/physical verdicts must come from Rust."""
    fields(claim, ['schema', 'kind', 'case_ids'])
    require(claim['schema'] == 1 and type(claim['schema']) is int, 'unknown claim schema')
    require(claim['kind'] == 'software_contract', 'product qualification requires Rust evidence resolver')
    inventory = resolve_inventory(catalog, receipts, artifacts, policy)
    unique_ids(claim['case_ids'])
    require(claim['case_ids'] and set(claim['case_ids']) <= set(inventory['expected_ids']), 'claim inventory mismatch')
    missing = set(inventory['missing']) | set(inventory['optional_unavailable'])
    return {'support': 'incomplete' if missing.intersection(claim['case_ids']) else 'complete',
            'product_qualification': None, 'release_authorized': False}
