#!/usr/bin/env python3
"""One battery record per CAD subject, with locked global fitness G1 beside it.

Search fitness is not read and not written. A missing G input is omitted.
A derived ratio is not counted as a solver run. C.10c is cited from its pin
and is not restored.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from metrics.global_metric import global_G, title_tag  # noqa: E402

SCHEMA = 'jarambit.cad_battery.subject.v1'
CASE_IDS = (
    'build.analytic', 'build.gci_contracts', 'build.claims', 'build.dolfinx',
    'geom.unit', 'geom.one_solid', 'geom.mass', 'geom.pin',
    'plate.loads', 'plate.seq', 'plate.l7', 'plate.gci',
    'side.a1', 'side.a2', 'side.a3', 'side.a4',
    'solid.tip', 'gate.rs_v2',
)
# Which case supplied a G key. Deleting the key marks a passing source incomplete.
G_SOURCE = {
    'solid_tip_sf_nodal_max': 'solid.tip',
    'plate_tipsub_screen_sf': 'plate.loads',
    'spg': 'plate.loads',
    'aes_score': 'gate.rs_v2',
    'mass_g': 'geom.mass',
    'seq_ratio': 'plate.seq',
}
SIDE_REPORT = Path('/home/ubuntu/jarambit_review_custody/disposition-20261014/report-a1/g3_a1a3.json')
SIDE_SHA = '3e419ac1cbd2576b9b2f92296862d937e763abe27cc2a065c4937ff6ec4a85f9'
SOLVER_FIELDS = ('n_tet', 'n_dof', 'ksp_its')


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load(rel):
    path = ROOT / rel
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def _case(case_id, kind, status, *, solver, geometry_sha256, source_commit,
          evidence_path, reason=None, detail=None, g_inputs=None):
    if status not in ('pass', 'fail', 'incomplete', 'blocked'):
        raise ValueError(f'bad status {status}')
    if kind not in ('solver_run', 'derived', 'gate', 'fitness', 'software_contract'):
        raise ValueError(f'bad kind {kind}')
    row = {
        'id': case_id, 'kind': kind, 'status': status, 'solver': solver,
        'geometry_sha256': geometry_sha256, 'source_commit': source_commit,
        'evidence_path': evidence_path, 'fresh_this_lane': False,
    }
    if reason:
        row['reason'] = reason
    if detail:
        row['detail'] = detail
    if g_inputs:
        row['g_inputs'] = g_inputs
    return row


def pass_count(cases):
    return sum(case['status'] == 'pass' for case in cases)


def solver_run_count(cases):
    """Completed solver runs only. Derived ratios, G, and search fitness are not included."""
    return sum(case['kind'] == 'solver_run' and case['status'] == 'pass' for case in cases)


def assemble_g(inputs, version):
    """Call the locked G1 function. ``inputs`` must already omit missing keys."""
    value, terms = global_G(dict(inputs))
    return {
        'metric': 'G1',
        'inputs': dict(inputs),
        'G': value,
        'status': terms['status'],
        'provisional': terms['provisional'] if value is not None else None,
        'missing': list(terms['missing']),
        'title': title_tag(dict(inputs), version),
    }


def without_key(record, key, version):
    """Drop one measured input. G must not rise and the pass count must not rise."""
    inputs = dict(record['global_fitness']['inputs'])
    inputs.pop(key, None)
    cases = [dict(case) for case in record['cases']]
    source = G_SOURCE.get(key)
    if source:
        for case in cases:
            if case['id'] == source and case['status'] == 'pass':
                case['status'] = 'incomplete'
                case['reason'] = 'input deleted'
                case.pop('g_inputs', None)
    fitness = assemble_g(inputs, version)
    return {**record, 'cases': cases, 'global_fitness': fitness, 'pass_count': pass_count(cases)}


def _shared_build(commit, probes):
    analytic = probes.get('analytic', 'incomplete')
    gci = probes.get('gci', 'incomplete')
    claims = probes.get('claims', 'incomplete')
    rows = [
        _case('build.analytic', 'software_contract', analytic, solver='analytic',
              geometry_sha256=None, source_commit=commit,
              evidence_path='crates/physics/tests/invariance.rs',
              reason=None if analytic == 'pass' else 'not executed in this record'),
        _case('build.gci_contracts', 'software_contract', gci, solver='gci',
              geometry_sha256=None, source_commit=commit,
              evidence_path='fem_solid/tests/test_gci.py',
              reason=None if gci == 'pass' else 'not executed in this record'),
        _case('build.claims', 'software_contract', claims, solver=None,
              geometry_sha256=None, source_commit=commit,
              evidence_path='ops/ci/check_claims.py',
              reason=None if claims == 'pass' else 'not executed in this record',
              detail={'expected_unaided_exit': 2, 'reason': 'independent_caller_admission_unavailable'} if claims == 'pass' else None),
        _case('build.dolfinx', 'software_contract', 'blocked', solver='solid_dolfinx',
              geometry_sha256=None, source_commit=commit, evidence_path=None,
              reason='ModuleNotFoundError: No module named dolfinx',
              detail={'interpreter': 'system and venv-cad', 'modules_on_default_discovery': False}),
    ]
    return {row['id']: row for row in rows}


def _native_geometry(name):
    from ops.science_tests.native_cad.evaluate import evaluate_subject
    return evaluate_subject(name)


def _geom_cases(spec, commit, geometry):
    sha = spec.get('step_sha256')
    if geometry is None:
        blocked = _case('geom.unit', 'gate', 'blocked', solver=None, geometry_sha256=sha,
                        source_commit=commit, evidence_path=spec.get('step'), reason='no mesh bound')
        return {case_id: {**blocked, 'id': case_id} for case_id in
                ('geom.unit', 'geom.one_solid', 'geom.mass', 'geom.pin')}
    step, mass = geometry['step'], geometry['mass']
    unit_ok = step.get('units') == 'mm' and step.get('units_source') == 'step_declaration'
    solid_ok = step.get('valid') is True and step.get('solids') == 1
    mass_status = 'pass'
    mass_reason = None
    if mass['step_vs_readme']['status'] != 'PASS' or mass['stl_vs_readme']['status'] == 'FAIL':
        mass_status = 'fail'
        mass_reason = 'readme mass disagrees or stl mass failed'
    if mass['stl_vs_readme']['status'] == 'UNAVAILABLE':
        mass_status = 'fail'
        mass_reason = 'stl mass unavailable'
    if not geometry['stl'].get('watertight_exact'):
        mass_status = 'fail'
        mass_reason = 'stl is not watertight'
    measured = mass.get('step_g')
    g_mass = {'mass_g': measured} if isinstance(measured, (int, float)) and not isinstance(measured, bool) else None
    return {
        'geom.unit': _case('geom.unit', 'gate', 'pass' if unit_ok else 'fail', solver=None,
                           geometry_sha256=sha, source_commit=commit, evidence_path=spec['step'],
                           detail={'units': step.get('units'), 'units_source': step.get('units_source')}),
        'geom.one_solid': _case('geom.one_solid', 'gate', 'pass' if solid_ok else 'fail', solver=None,
                                geometry_sha256=sha, source_commit=commit, evidence_path=spec['step'],
                                detail={'solids': step.get('solids')}),
        'geom.mass': _case('geom.mass', 'derived', mass_status, solver=None, geometry_sha256=sha,
                           source_commit=commit, evidence_path=spec['step'], reason=mass_reason,
                           detail={'step_g': measured, 'readme_g': mass.get('readme_g'),
                                   'stl_g': mass.get('stl_g'),
                                   'step_vs_readme': mass.get('step_vs_readme'),
                                   'stl_vs_readme': mass.get('stl_vs_readme')},
                           g_inputs=g_mass),
        'geom.pin': _case('geom.pin', 'software_contract', 'pass' if geometry.get('identity_ok') else 'fail',
                          solver=None, geometry_sha256=sha, source_commit=commit, evidence_path=spec['step'],
                          detail={'candidate_status': geometry.get('candidate_status'),
                                  'product_pass': False}),
    }


def _blocked_plate(spec, commit, sha, reason):
    rows = {}
    for case_id in ('plate.loads', 'plate.seq', 'plate.l7', 'plate.gci', 'side.a1', 'side.a2', 'side.a3', 'side.a4'):
        rows[case_id] = _case(case_id, 'derived', 'blocked', solver='plate_cst_dkt',
                              geometry_sha256=sha, source_commit=commit,
                              evidence_path=spec.get('step'), reason=reason)
    rows['solid.tip'] = _case('solid.tip', 'solver_run', 'blocked', solver='solid_dolfinx',
                              geometry_sha256=sha, source_commit=commit, evidence_path=None,
                              reason='no solid tip bound to this B-rep')
    rows['gate.rs_v2'] = _case('gate.rs_v2', 'gate', 'blocked', solver=None, geometry_sha256=sha,
                               source_commit=commit, evidence_path=None,
                               reason='B-rep is not an RS-karambit-v2 genome')
    return rows


def _sf(value, limit):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return {'value_n_or_sf': value, 'compared_with': limit}


def _genome_cases(spec, commit, rs, d1, sha):
    path = spec['rs']
    loads = {
        'hiker_lateral_n': _sf(rs.get('lat_rob_n'), 180),
        'hunter_lateral_n': _sf(rs.get('lat_rob_n'), 260),
        'ring_pull_n': _sf(rs.get('ring_rob_n'), 1500),
        'chord_twist_human_max_sf': _sf(rs.get('hm_twist_sf'), 16200),
        'spine_sf': _sf(rs.get('hm_spine_sf'), 3427),
        'ring_back_sf': _sf(rs.get('hm_ringback_sf'), 3000),
        'tip_inplane_sf_record_only': _sf(rs.get('hm_tip_inplane_sf'), 1000),
        'pry': None,
    }
    hard_fail = any(isinstance(item, dict) and item.get('value_n_or_sf', 1) < 1
                    for key, item in loads.items() if key in ('chord_twist_human_max_sf', 'spine_sf'))
    metrics = (d1 or {}).get('metrics') or {}
    g_loads = {}
    if isinstance(metrics.get('spg'), (int, float)) and not isinstance(metrics.get('spg'), bool):
        g_loads['spg'] = metrics['spg']
    # plate_tipsub_screen_sf is included only when that exact key was stored.
    if isinstance(metrics.get('plate_tipsub_screen_sf'), (int, float)):
        g_loads['plate_tipsub_screen_sf'] = metrics['plate_tipsub_screen_sf']
    plate_loads = _case('plate.loads', 'derived', 'fail' if hard_fail else 'incomplete',
                        solver='plate_cst_dkt', geometry_sha256=sha, source_commit=commit,
                        evidence_path=path, detail={'loads': loads, 'note': 'derived from the certify record'},
                        g_inputs=g_loads or None,
                        reason=None if hard_fail else 'pry safety factor is not in the certify record')
    seq = rs.get('seq_ratio')
    seq_ran = isinstance(seq, (int, float)) and not isinstance(seq, bool)
    plate_seq = _case('plate.seq', 'gate', 'fail' if seq_ran and seq < 1.2 else ('incomplete' if not seq_ran else 'pass'),
                      solver='plate_cst_dkt', geometry_sha256=sha, source_commit=commit, evidence_path=path,
                      detail={'seq_ratio': seq, 'seq_target': 1.2, 'side_report_seq_ratio': spec.get('side_seq')},
                      g_inputs={'seq_ratio': seq} if seq_ran else None,
                      reason='below 1.2' if seq_ran and seq < 1.2 else None)
    fat = rs.get('fat_sf')
    plate_l7 = _case('plate.l7', 'derived', 'fail' if isinstance(fat, float) and fat < 1 else 'incomplete',
                     solver='plate_cst_dkt', geometry_sha256=sha, source_commit=commit, evidence_path=path,
                     detail={'label': 'screening', 'not': 'spec §7.3 L7', 'fat_sf': fat, 'cycles': '1e7', 'load': '0..180 N'})
    plate_gci = _case('plate.gci', 'derived', 'incomplete', solver='plate_cst_dkt', geometry_sha256=sha,
                      source_commit=commit, evidence_path=path, reason='no three-mesh plate family stored')
    rows = {
        'plate.loads': plate_loads, 'plate.seq': plate_seq, 'plate.l7': plate_l7, 'plate.gci': plate_gci,
    }
    rows.update(_side_cases(spec, commit, sha))
    rows['solid.tip'] = _solid_tip(spec, commit, rs, sha)
    aes = metrics.get('aes_score')
    g_aes = {'aes_score': aes} if isinstance(aes, (int, float)) and not isinstance(aes, bool) else None
    rows['gate.rs_v2'] = _case('gate.rs_v2', 'gate', 'fail' if rs.get('all_hard') is False else 'incomplete',
                               solver=None, geometry_sha256=sha, source_commit=commit, evidence_path=path,
                               detail={'gates': rs.get('gates'), 'all_hard': rs.get('all_hard')},
                               g_inputs=g_aes, reason='does not pass every hard gate')
    mass = rs.get('mass_g')
    g_mass = {'mass_g': mass} if isinstance(mass, (int, float)) and not isinstance(mass, bool) else None
    rows['geom.unit'] = _case('geom.unit', 'gate', 'blocked', solver=None, geometry_sha256=sha,
                              source_commit=commit, evidence_path=spec['genome'], reason='no step bound')
    rows['geom.one_solid'] = _case('geom.one_solid', 'gate', 'blocked', solver=None, geometry_sha256=sha,
                                   source_commit=commit, evidence_path=spec['genome'], reason='no step bound')
    rows['geom.mass'] = _case('geom.mass', 'derived', 'pass' if g_mass else 'incomplete', solver='plate_cst_dkt',
                              geometry_sha256=sha, source_commit=commit, evidence_path=path,
                              detail={'plate_mass_g': mass, 'note': 'fem::certify mass, not a STEP'},
                              g_inputs=g_mass)
    rows['geom.pin'] = _case('geom.pin', 'software_contract', 'blocked', solver=None, geometry_sha256=sha,
                             source_commit=commit, evidence_path=spec['genome'], reason='genome is not a native CAD pin')
    return rows


def _side_cases(spec, commit, sha):
    rows = {}
    if spec.get('side_path') and spec.get('side_sha'):
        detail = {'sha256': spec['side_sha'], 'mesh_mm2': 0.25, 'changes_seq_ratio': False}
        for case_id in ('side.a1', 'side.a2', 'side.a3'):
            rows[case_id] = _case(case_id, 'derived', 'pass', solver='plate_cst_dkt', geometry_sha256=sha,
                                  source_commit=commit, evidence_path=spec['side_path'], detail=detail)
    else:
        for case_id in ('side.a1', 'side.a2', 'side.a3'):
            rows[case_id] = _case(case_id, 'derived', 'incomplete', solver='plate_cst_dkt',
                                  geometry_sha256=sha, source_commit=commit, evidence_path=None,
                                  reason='not inherited from another subject')
    rows['side.a4'] = _case('side.a4', 'derived', 'incomplete', solver='plate_cst_dkt', geometry_sha256=sha,
                            source_commit=commit, evidence_path=None, reason='support variants and buckling not run')
    return rows


def _solid_tip(spec, commit, rs, sha):
    source = rs.get('solid_tip_source')
    payload = _load(source) if source else None
    if not payload:
        return _case('solid.tip', 'solver_run', 'incomplete', solver='solid_dolfinx', geometry_sha256=sha,
                     source_commit=commit, evidence_path=source, reason='no solid tip bound to this genome')
    levels = payload.get('levels') or []
    finest = levels[-1] if levels else {}
    missing = [name for name in SOLVER_FIELDS if name not in finest]
    detail = {'SF_nodal_max_historical': (payload.get('SF_nodal_max') or {}).get('fine'),
              'present': [name for name in SOLVER_FIELDS if name in finest], 'missing': missing,
              'copied_from_another_genome': False}
    # n_tet is required. A historical SF without it is not a solver_run success and is not a G input.
    return _case('solid.tip', 'solver_run', 'incomplete', solver='solid_dolfinx', geometry_sha256=sha,
                 source_commit=commit, evidence_path=source, reason='missing ' + ', '.join(missing), detail=detail)


def _g_from_cases(cases):
    inputs = {}
    for case in cases:
        for key, value in (case.get('g_inputs') or {}).items():
            if key not in inputs and value is not None:
                inputs[key] = value
    # Tip from the solid key only when that case is a completed solver run.
    solid = next(case for case in cases if case['id'] == 'solid.tip')
    if solid['status'] != 'pass' or solid['kind'] != 'solver_run':
        inputs.pop('solid_tip_sf_nodal_max', None)
    seq = next(case for case in cases if case['id'] == 'plate.seq')
    if seq['status'] == 'blocked':
        inputs.pop('seq_ratio', None)
    return inputs


def subject_catalog():
    side = None
    side_seq = None
    if SIDE_REPORT.is_file() and _sha256(SIDE_REPORT) == SIDE_SHA:
        side = str(SIDE_REPORT)
        payload = json.loads(SIDE_REPORT.read_text(encoding='utf-8'))
        side_seq = payload.get('seq_ratio_this_mesh')
    native = {
        'c10a': 'C10a', 'c93': 'C93', 'c92': 'C92', 'c10c': 'C10c',
    }
    genomes = {
        'g3': {
            'rs': 'evidence/rs_v2/g3_tip+00_t60_tt3.json',
            'd1': 'evidence/wave27/g3_tip+00_t60_tt3_D1.json',
            'genome': 'evidence/rs_v2/genomes/g3_tip+00_t60_tt3.csv',
            'side_path': side, 'side_sha': SIDE_SHA if side else None, 'side_seq': side_seq,
        },
        'w271b_11772': {
            'rs': 'evidence/rs_v2/w271b_11772.json', 'd1': None,
            'genome': 'evidence/rs_v2/genomes/w271b_11772_genome.csv',
        },
        'w271b_11860': {
            'rs': 'evidence/rs_v2/w271b_11860.json', 'd1': None,
            'genome': 'evidence/rs_v2/genomes/w271b_11860_genome.csv',
        },
        'w271c_11522': {
            'rs': 'evidence/rs_v2/w271c_11522.json', 'd1': None,
            'genome': 'evidence/rs_v2/genomes/w271c_11522.csv',
        },
    }
    return native, genomes


def build_subject(subject_id, commit, probes, *, geometry=None, measure=False):
    from ops.science_tests.native_cad.pins import SUBJECTS
    native, genomes = subject_catalog()
    version = (ROOT / 'docs' / 'VERSION').read_text(encoding='utf-8').strip()
    shared = _shared_build(commit, probes)
    if subject_id in native:
        name = native[subject_id]
        spec = dict(SUBJECTS[name])
        spec['step_sha256'] = spec['step_sha256']
        if measure and geometry is None:
            geometry = _native_geometry(name)
        sha = spec['step_sha256']
        cases = dict(shared)
        cases.update(_geom_cases(spec, commit, geometry))
        if geometry is None:
            cases.update(_blocked_plate(spec, commit, sha, 'no mesh bound'))
        else:
            # A native identity check is not a plate mesh.
            cases.update(_blocked_plate(spec, commit, sha, 'no mesh bound'))
            # geom cases already set; blocked_plate must not overwrite them.
            # _blocked_plate does not include geom.*, so this is safe.
        role = 'archived_not_on_main' if spec.get('archived') else 'native_cad'
    elif subject_id in genomes:
        spec = genomes[subject_id]
        rs = _load(spec['rs'])
        if rs is None:
            raise FileNotFoundError(spec['rs'])
        d1 = _load(spec['d1']) if spec.get('d1') else None
        sha = _sha256(ROOT / spec['genome'])
        cases = dict(shared)
        cases.update(_genome_cases(spec, commit, rs, d1, sha))
        role = 'genome'
    else:
        raise KeyError(subject_id)
    ordered = [cases[case_id] for case_id in CASE_IDS]
    if [case['id'] for case in ordered] != list(CASE_IDS):
        raise RuntimeError('case id set drifted')
    inputs = _g_from_cases(ordered)
    record = {
        'schema': SCHEMA,
        'subject': subject_id,
        'role': role,
        'source_commit': commit,
        'cases': ordered,
        'pass_count': pass_count(ordered),
        'solver_run_count': solver_run_count(ordered),
        'solver_run_objects': sum(case['kind'] == 'solver_run' for case in ordered),
        'global_fitness': assemble_g(inputs, version),
        'search_fitness': 'unchanged',
    }
    return record


def synthetic_complete(version='0.31.0'):
    """A fixture with one finite G, used to prove deletion cannot raise it."""
    commit = '0' * 40
    inputs = {'solid_tip_sf_nodal_max': 1.5, 'spg': 4.0, 'aes_score': 0.6, 'mass_g': 80.0, 'seq_ratio': 0.9}
    cases = []
    for case_id in CASE_IDS:
        g_inputs = None
        status = 'incomplete'
        if case_id == 'solid.tip':
            status, g_inputs = 'pass', {'solid_tip_sf_nodal_max': inputs['solid_tip_sf_nodal_max']}
        elif case_id == 'plate.loads':
            status, g_inputs = 'pass', {'spg': inputs['spg']}
        elif case_id == 'gate.rs_v2':
            status, g_inputs = 'pass', {'aes_score': inputs['aes_score']}
        elif case_id == 'geom.mass':
            status, g_inputs = 'pass', {'mass_g': inputs['mass_g']}
        elif case_id == 'plate.seq':
            status, g_inputs = 'pass', {'seq_ratio': inputs['seq_ratio']}
        cases.append(_case(case_id, 'solver_run' if case_id == 'solid.tip' else 'derived', status,
                           solver='fixture', geometry_sha256=None, source_commit=commit,
                           evidence_path=None, g_inputs=g_inputs))
    return {
        'schema': SCHEMA, 'subject': 'fixture', 'role': 'fixture', 'source_commit': commit,
        'cases': cases, 'pass_count': pass_count(cases), 'solver_run_count': solver_run_count(cases),
        'global_fitness': assemble_g(inputs, version), 'search_fitness': 'unchanged',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subject')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'evidence' / 'cad_battery')
    parser.add_argument('--commit', default=None)
    parser.add_argument('--analytic', choices=('pass', 'fail', 'incomplete'), default='incomplete')
    parser.add_argument('--gci', choices=('pass', 'fail', 'incomplete'), default='incomplete')
    parser.add_argument('--claims', choices=('pass', 'fail', 'incomplete'), default='incomplete')
    parser.add_argument('--measure-native', action='store_true')
    args = parser.parse_args(argv)
    commit = args.commit
    if commit is None:
        import subprocess
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    probes = {'analytic': args.analytic, 'gci': args.gci, 'claims': args.claims}
    native, genomes = subject_catalog()
    wanted = [args.subject] if args.subject else list(native) + list(genomes)
    if not args.subject and not args.all:
        parser.error('pass --subject or --all')
    args.out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for subject_id in wanted:
        record = build_subject(subject_id, commit, probes, measure=args.measure_native)
        path = args.out_dir / f'{subject_id}.json'
        path.write_text(json.dumps(record, indent=1, sort_keys=False) + '\n', encoding='utf-8')
        written.append(str(path.relative_to(ROOT)))
        print(f"{subject_id} pass={record['pass_count']} solver_runs={record['solver_run_count']} "
              f"G={record['global_fitness']['status']}")
    manifest = {
        'schema': 'jarambit.cad_battery.manifest.v1',
        'metric': 'G1',
        'case_ids': list(CASE_IDS),
        'subjects': wanted,
        'source_commit': commit,
        'search_fitness': 'unchanged',
        'files': written,
    }
    (args.out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
