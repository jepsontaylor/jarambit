#!/usr/bin/env python3
"""Scoped verdicts under a requirement set (PR-0.28.2). Author: Jepson Taylor.
usage: rs_verdicts.py <D1_index.json> <label>   -> prints the canonical one-line verdict used in README/PROVISIONAL.
Never prints an unscoped PASS: every verdict names the RS id and group."""
import json, os, sys
try:
    import tomllib
except ModuleNotFoundError:  # py<3.11
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from assurance.reporting import claims, blocks  # noqa: E402
from assurance.testing.contracts import finite, scientific_hash  # noqa: E402

_DEFAULT_CONTEXT = None


def install_admitted_context(context):
    """Trusted application/test launcher only; never selected by CLI or env."""
    global _DEFAULT_CONTEXT
    if type(context) is not ReportingContext:
        raise claims.Refusal('independent_caller_admission_required')
    context.caller.verify_current()
    _DEFAULT_CONTEXT = context


def admitted_context():
    if _DEFAULT_CONTEXT is None:
        raise claims.Refusal('independent_caller_admission_unavailable')
    _DEFAULT_CONTEXT.caller.verify_current()
    return _DEFAULT_CONTEXT


def checked_global_metric(record):
    """The one ops adapter for the unchanged locked G1 implementation."""
    from metrics.global_metric import global_G
    value, terms = global_G(record)
    missing = []
    for reason in terms['missing']:
        key = 'solid_tip_sf_nodal_max' if reason.startswith('tip: ') else reason.split(':', 1)[0]
        if key not in missing:
            missing.append(key)
    return {'G1': {'status': terms['status'], 'value': value, 'scope': 'report_only', 'missing': missing}}, list(terms['missing'])


def source_mass(request):
    """Record-only mass from its actual source envelope, independently of G1 deletion."""
    matches = [o for o in request['observations'] if o['identity']['observable']['quantity'] == 'mass']
    if not matches:
        return None
    claims.require(len(matches) == 1, 'ambiguous_mass_observation')
    observation = matches[0]
    claims.require(observation['identity']['observable']['unit'] == 'gram', 'mass_unit_mismatch')
    refs = [a for a in request['artifacts'] if a['reference'] == observation['source']]
    claims.require(len(refs) == 1, 'mass_source_missing')
    source = claims.decode(refs[0]['bytes_utf8'].encode('utf-8'))
    expected = {k: observation[k] for k in ['schema', 'producer', 'value', 'not_applicable_reason', 'origin', 'evidence_class', 'state', 'dependencies', 'uncertainty']}
    expected['identity_sha256'] = scientific_hash(observation['identity'])
    claims.require(source == expected, 'mass_source_binding_mismatch')
    value = observation['value']
    return None if value is None else finite(value)


def admitted_gci_reports(records, expected_inventory):
    """Accepted S02 reporting API; no mock fresh provider or physical promotion."""
    from fem_solid.gci_report import build_report
    return build_report(records, expected_inventory)


def historical_gci_reports(paths):
    """One accepted S02 history adapter; old data never gains fresh qualification."""
    from fem_solid.gci_report import reclassify_history
    return reclassify_history(paths)


def native_candidate_status(candidate):
    state = {'C10a': 'comparison_pipeline_baseline', 'C10c': 'archived'}.get(candidate, 'unregistered')
    return {'candidate': candidate, 'state': state, 'binding': 'incomplete', 'reason': 'native_inventory_provider_unavailable', 'physical_validation': 'not_performed'}


class ReportingContext:
    """One D-admitted provider/context shared by checker and all generators."""
    def __init__(self, caller, request_path, authority_path):
        claims.require(type(caller) is claims.TrustedCaller, 'independent_caller_admission_required')
        self.caller = caller
        self.request_path = os.path.abspath(request_path)
        self.authority_path = os.path.abspath(authority_path)
        self.last_resolution = None
        self.last_report = None
        self.metric_diagnostics = []

    def report_for(self, claim_id):
        self.last_resolution = None; self.last_report = None
        request_raw = claims.read_bounded(self.request_path)
        authority_raw = claims.read_bounded(self.authority_path)
        request, authority, binding, descriptor = claims.admission_binding(request_raw, authority_raw, self.caller)
        claims.require(request['claim']['id'] == claim_id, 'claim_registration_mismatch')
        result = claims.resolve_provider(self.request_path, self.authority_path, self.caller)
        # The provider re-reads paths. Its actual binding must authenticate the
        # complete retained inputs before any report value/cache can consume them.
        claims.validate_output(result.output, binding, claim_id)
        claims.require(result.input_sha256 == scientific_hash(descriptor), 'provider_input_identity_mismatch')
        self.last_resolution = result
        registry = claims.validate_registry(claims.decode(claims.raw_root(authority['roots']['registry'])))
        context = authority['report_context']
        if claims.scope_errors(context, registry, self.caller.data['pin']['registration']):
            raise RequestedScopeError(claims.scope_errors(context, registry, self.caller.data['pin']['registration']))
        metrics, diagnostics = checked_global_metric(context['G1'])
        self.metric_diagnostics = diagnostics
        report = claims.canonical_report(result, context, registry, [r['reference'] for r in authority['approved_requirements']], self.caller, metrics, source_mass(request))
        self.last_report = report
        return report

    def registry(self):
        data = self.caller.verify_current()
        return claims.validate_registry(claims.decode(claims.read_bounded(data['registry_path'])))


class RequestedScopeError(ValueError):
    def __init__(self, reasons):
        self.reasons = list(reasons)
        super().__init__('; '.join(self.reasons))


def claim_block(context=None, claim_id=None):
    context = context if context is not None else admitted_context()
    claim_id = claim_id or context.caller.data['pin']['registration']['claim_id']
    return blocks.write_block(claim_id, context.report_for(claim_id))


def replace_claim_block(text, context):
    """Generator adapter: preserve GEN blocks while reconciling its RS block."""
    import re
    replacement = claim_block(context)
    pattern = re.compile(r'<!-- RS:BEGIN [^\n]* -->\n.*?\n<!-- RS:END -->', re.S)
    matches = list(pattern.finditer(text))
    claims.require(len(matches) <= 1, 'duplicate_generator_claim_blocks')
    return pattern.sub(lambda _: replacement, text) if matches else text.rstrip('\n') + '\n\n' + replacement + '\n'


def load_rs(rs_id='RS-karambit-v1'):
    p = os.path.join(ROOT, 'requirements', f'{rs_id}.toml')
    if tomllib is None:
        raise SystemExit('python >= 3.11 required (tomllib)')
    with open(p, 'rb') as fh:
        return tomllib.load(fh)


def verdict(rec, rs):
    c = rs['constants']
    m, seq = rec.get('mass_g'), rec.get('seq_ratio')
    fails, soft = [], []
    # mass is SOFT since RS v2 (Jepson 2026-10-12): reported as a target, never a promotion failure
    if isinstance(m, (int, float)) and not isinstance(m, bool):
        if m >= c['mass_target_g']:
            soft.append(f"mass {m:.2f} g over {c['mass_target_g']:.0f} g target")
        elif m >= c['mass_stretch_g']:
            soft.append(f"mass {m:.2f} g; stretch target {c['mass_stretch_g']:.0f} g")
    else:
        soft.append('mass missing')
    if not isinstance(seq, (int, float)) or isinstance(seq, bool):
        fails.append('seq missing')
    elif seq < c['seq_target']:
        fails.append(f"seq {seq:.3f} < {c['seq_target']}")
    if (rec.get('d1') or {}).get('strict_ok') is False:
        fails.append('strict hunter lateral')
    if rec.get('twist_floor_ok') is not True:
        fails.append('twist floor')
    screen = rec.get('w20_hard_pass')
    screen_s = 'PASS' if screen is True else ('FAIL' if screen is False else 'INCOMPLETE')
    if screen is not True:
        fails.insert(0, 'screen')
    prom = rec.get('promote_eligible')
    if prom is True and fails:
        raise SystemExit(f"inconsistent record: promote_eligible true but {fails}")
    prom_s = 'PASS' if (prom is True and not fails) else 'FAIL'
    if fails:
        why = f" ({'; '.join(fails)})"
    elif prom_s == 'FAIL':
        why = ' (record promote_eligible not true; recompute under RS v2)'
    else:
        why = ''
    soft_s = f" · soft: {'; '.join(soft)} (G penalty)" if soft else ''
    return f"{rs['id']}: screen {screen_s} · promotion {prom_s}{why}{soft_s} · human aesthetic sign-off pending · not promoted"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or any(a.startswith('--') for a in argv):
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    with open(argv[0]) as fh:
        rows = json.load(fh)
    rec = next((r for r in rows if r.get('label') == argv[1]), None)
    if rec is None:
        raise SystemExit(f'label {argv[1]} not found')
    print(verdict(rec, load_rs()))


if __name__ == '__main__':
    main()
