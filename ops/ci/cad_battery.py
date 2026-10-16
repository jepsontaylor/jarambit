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
SIDE_REPORT = ROOT / 'evidence' / 'cad_battery' / 'side' / 'g3_a1a3.json'
SIDE_SHA = '3e419ac1cbd2576b9b2f92296862d937e763abe27cc2a065c4937ff6ec4a85f9'
W271_SIDE = ROOT / 'evidence' / 'cad_battery' / 'side' / 'w271b_11772_a1a3.json'
SOLVER_FIELDS = ('n_tet', 'n_dof', 'ksp_its')
# Stored ladders that name a STEP only by sha16, and that omit n_dof and ksp_its.
# They stay out of solid.tip. The numbers are the object counts read from those files.
LADDER_BLOCKED = {
    'c92': {
        'entered_as_solver_run': False,
        'missing_fields': ['n_dof', 'ksp_its'],
        'files': [{
            'path': 'designs/switchback/C9.2/data/w75_1_results.json',
            'sha16': '2ad2a8ecaf4fca67',
            'names_full_step_sha256': False,
            'objects_with_n_tet_and_SF': 12,
            'objects_with_SF_only': 5,
        }],
    },
    'c93': {
        'entered_as_solver_run': False,
        'missing_fields': ['n_dof', 'ksp_its'],
        'files': [
            {
                'path': 'designs/switchback/C9.3/data/w76_results.json',
                'names_c93_step_sha256': False,
                'base_line_names_c92_sha16': '2ad2a8ecaf4fca67',
                'objects_with_n_tet_and_SF': 48,
            },
            {
                'path': 'designs/switchback/C9.3/data/w77_results.json',
                'sha16': '3a818183bcb5b9a9',
                'names_full_step_sha256': False,
                'objects_with_n_tet': 8,
                'objects_with_numeric_SF': 0,
            },
        ],
    },
}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load(rel):
    if not rel:
        return None
    p = Path(rel)
    path = p if p.is_absolute() else ROOT / p
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
    cross_rel = 'evidence/cad_battery/dolfinx_cross_check.json'
    cross_doc = _load(cross_rel)
    dolfinx = probes.get('dolfinx')
    if dolfinx is None:
        dolfinx = 'pass' if (cross_doc and cross_doc.get('all_within_2pct') is True) else 'blocked'
    if dolfinx == 'pass' and cross_doc and cross_doc.get('all_within_2pct') is True:
        dolfinx_case = _case(
            'build.dolfinx', 'software_contract', 'pass', solver='solid_dolfinx',
            geometry_sha256=None, source_commit=commit,
            evidence_path=cross_rel,
            detail={
                'container_image': cross_doc.get('container_image'),
                'script': cross_doc.get('script'),
                'all_within_2pct': True,
                'tolerance_rel': cross_doc.get('tolerance_rel'),
                'subjects_checked': sorted((cross_doc.get('subjects') or {}).keys()),
            },
        )
    else:
        dolfinx_case = _case(
            'build.dolfinx', 'software_contract', 'blocked', solver='solid_dolfinx',
            geometry_sha256=None, source_commit=commit, evidence_path=None,
            reason='ModuleNotFoundError: No module named dolfinx',
            detail={
                'interpreters_checked': [
                    'python3',
                    '/home/ubuntu/jarambit_render/venv-cad/bin/python',
                    '/home/ubuntu/.venv/bin/python',
                    '/home/ubuntu/.venvs/doug-tests/bin/python',
                    '/home/ubuntu/.venvs/innovationzero-v5-tabpfn/bin/python',
                    '/home/ubuntu/.venvs/jope-asm-training/bin/python',
                    '/home/ubuntu/.venvs/jope-dltrain-v1/bin/python',
                    '/home/ubuntu/.venvs/resemble-enhance/bin/python',
                ],
                'import_error': 'ModuleNotFoundError',
                'modules_on_default_discovery': False,
                'pip_install': False,
            },
        )
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
        dolfinx_case,
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
    metrics = dict((d1 or {}).get('metrics') or {})
    tip_doc = _load(spec.get('tip_mesh')) if spec.get('tip_mesh') else None
    # SPG and aes only. The index plate_tipsub_screen_sf column is the twist
    # tip-zone number on every wave27 row, so it is not copied in as a plate screen.
    for key in ('spg', 'aes_score'):
        value = (tip_doc or {}).get('metrics', {}).get(key)
        if key not in metrics and isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[key] = value
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
    gci_path = spec.get('plate_gci')
    gci_doc = _load(gci_path) if gci_path else None
    if gci_doc and gci_doc.get('genome_sha256') == sha:
        seq_gci = dict(gci_doc.get('seq_ratio_gci') or {})
        sf_gci = dict(gci_doc.get('sf_hunter_gci') or {})
        admitted = bool(seq_gci.get('admitted'))
        plate_gci = _case(
            'plate.gci', 'derived', 'pass' if admitted else 'fail',
            solver='plate_cst_dkt', geometry_sha256=sha, source_commit=commit,
            evidence_path=gci_path,
            reason=None if admitted else (seq_gci.get('reason') or seq_gci.get('fit_status')),
            detail={
                'primary_observable': gci_doc.get('primary_observable'),
                'refinement_ratio_r': gci_doc.get('refinement_ratio_r'),
                'fit_status': seq_gci.get('fit_status'),
                'p': seq_gci.get('p'),
                'gci_fine': seq_gci.get('gci_fine'),
                'admitted': admitted,
                'discretization_under_3pct': bool(admitted and isinstance(seq_gci.get('gci_fine'), float) and seq_gci['gci_fine'] < 0.03),
                'sf_hunter_fit_status': sf_gci.get('fit_status'),
                'sf_hunter_p': sf_gci.get('p'),
                'sf_hunter_gci_fine': sf_gci.get('gci_fine'),
            },
        )
    else:
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
    a4_rel = spec.get('side_a4')
    a4_doc = _load(a4_rel) if a4_rel else None
    if (a4_doc and a4_doc.get('schema') == 'jarambit.side_report.a4.v1'
            and a4_doc.get('genome_sha256') == sha
            and a4_doc.get('status') == 'pass'
            and a4_doc.get('partial_solver_edit') is False
            and a4_doc.get('changes_seq_ratio') is False):
        rows['side.a4'] = _case(
            'side.a4', 'derived', 'pass', solver='plate_cst_dkt', geometry_sha256=sha,
            source_commit=commit, evidence_path=a4_rel,
            detail={
                'sha256': _sha256(ROOT / a4_rel),
                'bore_support': (a4_doc.get('bore_support') or {}).get('model'),
                'grip_foundation_stiffness': (a4_doc.get('grip_foundation_stiffness') or {}).get('model'),
                'buckling_eigenvalue': a4_doc.get('buckling_eigenvalue'),
                'buckling_critical_load_n': a4_doc.get('buckling_critical_load_n'),
                'supported_seq_ratio': a4_doc.get('supported_seq_ratio'),
                'certified_seq_ratio': a4_doc.get('certified_seq_ratio'),
                'default_clamp': 'ring-hole nodes fixed in all 5 dofs inside run_b',
                'partial_solver_edit': False,
                'changes_seq_ratio': False,
            })
    else:
        rows['side.a4'] = _case(
            'side.a4', 'derived', 'incomplete', solver='plate_cst_dkt', geometry_sha256=sha,
            source_commit=commit, evidence_path=None,
            reason='run_b default BC is the certified model',
            detail={
                'bore_support': 'absent',
                'grip_foundation_stiffness': 'absent',
                'buckling_eigenvalue': 'absent',
                'default_clamp': 'ring-hole nodes fixed in all 5 dofs inside run_b',
                'partial_solver_edit': False,
            })
    return rows


def _solid_tip(spec, commit, rs, sha):
    source = rs.get('solid_tip_source')
    payload = _load(source) if source else None
    if not payload or payload.get('schema') == 'jarambit.stored_solid_tip.v1':
        stored = payload if (payload and payload.get('schema') == 'jarambit.stored_solid_tip.v1') else (_load(spec.get('tip_mesh')) if spec.get('tip_mesh') else None)
        if stored and stored.get('schema') == 'jarambit.stored_solid_tip.v1':
            solid = dict(stored.get('stored_solid') or {})
            missing = [name for name in SOLVER_FIELDS
                       if not isinstance(solid.get(name), (int, float)) or isinstance(solid.get(name), bool)]
            sf = solid.get('SF_nodal_max')
            complete = bool(not missing and isinstance(sf, (int, float)) and not isinstance(sf, bool))
            # A stored SF without every solver field stays out of G.
            detail = {
                'SF_nodal_max': sf if isinstance(sf, (int, float)) and not isinstance(sf, bool) else None,
                'n_tet': solid.get('n_tet'), 'n_dof': solid.get('n_dof'), 'ksp_its': solid.get('ksp_its'),
                'NL': solid.get('NL'), 'NSUB': solid.get('NSUB'),
                'missing': missing, 'solve_rerun': bool(stored.get('solve_rerun')),
                'copied_from_another_genome': False, 'entered_as_solver_run': complete,
                'genome_data_row_matches_csv': stored.get('genome_data_row_matches_csv'),
                'd1_sha256': stored.get('d1_sha256'),
            }
            if complete:
                return _case('solid.tip', 'solver_run', 'pass', solver='solid_skfem_p2', geometry_sha256=sha,
                             source_commit=commit, evidence_path=spec.get('tip_mesh'),
                             detail=detail, g_inputs={'solid_tip_sf_nodal_max': sf})
            return _case('solid.tip', 'solver_run', 'incomplete', solver='solid_skfem_p2', geometry_sha256=sha,
                         source_commit=commit, evidence_path=spec.get('tip_mesh'),
                         reason='missing ' + ', '.join(missing), detail=detail)
        searched = spec.get('d1_searched')
        detail = {'searched': list(searched), 'found': False} if searched else None
        return _case('solid.tip', 'solver_run', 'incomplete', solver='solid_skfem_p2', geometry_sha256=sha,
                     source_commit=commit, evidence_path=source, reason='no solid tip bound to this genome',
                     detail=detail)
    levels = payload.get('levels') or []
    finest = dict(levels[-1]) if levels else {}
    counted = _load(spec.get('tip_mesh')) if spec.get('tip_mesh') else None
    matched = None
    if counted:
        for row in counted.get('levels') or []:
            if row.get('NL') == finest.get('NL') and row.get('NSUB') == finest.get('NSUB') and row.get('n_dof') == finest.get('n_dof'):
                matched = row
                break
    if matched and isinstance(matched.get('n_tet'), int):
        finest['n_tet'] = matched['n_tet']
    missing = [name for name in SOLVER_FIELDS if not isinstance(finest.get(name), (int, float)) or isinstance(finest.get(name), bool)]
    sf = finest.get('SF_nodal_max')
    detail = {
        'SF_nodal_max': sf if isinstance(sf, (int, float)) and not isinstance(sf, bool) else None,
        'SF_nodal_max_published_fine': (payload.get('SF_nodal_max') or {}).get('fine'),
        'n_tet': finest.get('n_tet'), 'n_dof': finest.get('n_dof'), 'ksp_its': finest.get('ksp_its'),
        'NL': finest.get('NL'), 'NSUB': finest.get('NSUB'),
        'n_tet_counted_this_lane': bool(matched), 'solve_rerun': False,
        'copied_from_another_genome': False, 'missing': missing,
    }
    # n_tet is required. A historical SF without it is not a solver_run success and is not a G input.
    if not missing and isinstance(sf, (int, float)) and not isinstance(sf, bool):
        return _case('solid.tip', 'solver_run', 'pass', solver='solid_skfem_p2', geometry_sha256=sha,
                     source_commit=commit, evidence_path=spec.get('tip_mesh'),
                     detail=detail, g_inputs={'solid_tip_sf_nodal_max': sf})
    return _case('solid.tip', 'solver_run', 'incomplete', solver='solid_skfem_p2', geometry_sha256=sha,
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


def _d1_searched(name):
    return [
        f'/home/ubuntu/fs4/d1/{name}_D1.json',
        f'ubuntu@192.168.68.54:/home/ubuntu/fs4/d1/{name}_D1.json',
        f'/home/ubuntu/jarambit_w271/out/solidcert_{name}/{name}_D1.json',
        f'evidence/ has the RS json and the genome csv for {name}, and no {name}_D1.json',
    ]


def _repo_side(name):
    rel = f'evidence/cad_battery/side/{name}_a1a3.json'
    path = ROOT / rel
    if not path.is_file():
        return None, None, None
    payload = json.loads(path.read_text(encoding='utf-8'))
    return rel, _sha256(path), payload.get('seq_ratio_this_mesh')


def subject_catalog():
    side = None
    side_seq = None
    if SIDE_REPORT.is_file() and _sha256(SIDE_REPORT) == SIDE_SHA:
        side = str(SIDE_REPORT.relative_to(ROOT))
        payload = json.loads(SIDE_REPORT.read_text(encoding='utf-8'))
        side_seq = payload.get('seq_ratio_this_mesh')
    w11772_side, w11772_sha, w11772_seq = _repo_side('w271b_11772')
    w11860_side, w11860_sha, w11860_seq = _repo_side('w271b_11860')
    w11522_side, w11522_sha, w11522_seq = _repo_side('w271c_11522')
    w272_side, w272_sha, w272_seq = _repo_side('w272_s2902_c01')
    w273_2904_side, w273_2904_sha, w273_2904_seq = _repo_side('w273_s2904_c01')
    w273_2903_side, w273_2903_sha, w273_2903_seq = _repo_side('w273_s2903_c04')
    w274_2905_side = 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_a1a3.json'
    w274_2905_path = ROOT / w274_2905_side
    w274_2905_sha = _sha256(w274_2905_path) if w274_2905_path.is_file() else None
    w274_2905_seq = json.loads(w274_2905_path.read_text(encoding='utf-8')).get('seq_ratio_this_mesh') if w274_2905_path.is_file() else None
    w275_2909_side = 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_a1a3.json'
    w275_2909_path = ROOT / w275_2909_side
    w275_2909_sha = _sha256(w275_2909_path) if w275_2909_path.is_file() else None
    w275_2909_seq = json.loads(w275_2909_path.read_text(encoding='utf-8')).get('seq_ratio_this_mesh') if w275_2909_path.is_file() else None
    w276_2913_side = 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_a1a3.json'
    w276_2913_path = ROOT / w276_2913_side
    w276_2913_sha = _sha256(w276_2913_path) if w276_2913_path.is_file() else None
    w276_2913_seq = json.loads(w276_2913_path.read_text(encoding='utf-8')).get('seq_ratio_this_mesh') if w276_2913_path.is_file() else None
    w277_2919_side = 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_a1a3.json'
    w277_2919_path = ROOT / w277_2919_side
    w277_2919_sha = _sha256(w277_2919_path) if w277_2919_path.is_file() else None
    w277_2919_seq = json.loads(w277_2919_path.read_text(encoding='utf-8')).get('seq_ratio_this_mesh') if w277_2919_path.is_file() else None
    w278_2922_side = 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_a1a3.json'
    w278_2922_path = ROOT / w278_2922_side
    w278_2922_sha = _sha256(w278_2922_path) if w278_2922_path.is_file() else None
    w278_2922_seq = json.loads(w278_2922_path.read_text(encoding='utf-8')).get('seq_ratio_this_mesh') if w278_2922_path.is_file() else None
    w279_2928_side = 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_a1a3.json'
    w279_2928_path = ROOT / w279_2928_side
    w279_2928_sha = _sha256(w279_2928_path) if w279_2928_path.is_file() else None
    w279_2928_seq = json.loads(w279_2928_path.read_text(encoding='utf-8')).get('seq_ratio_this_mesh') if w279_2928_path.is_file() else None
    native = {
        'c10a': 'C10a', 'c93': 'C93', 'c92': 'C92', 'c10c': 'C10c',
    }
    genomes = {
        'g3': {
            'rs': 'evidence/rs_v2/g3_tip+00_t60_tt3.json',
            'd1': 'evidence/wave27/g3_tip+00_t60_tt3_D1.json',
            'genome': 'evidence/rs_v2/genomes/g3_tip+00_t60_tt3.csv',
            'tip_mesh': 'evidence/cad_battery/tip_mesh/g3.json',
            'plate_gci': 'evidence/cad_battery/plate_gci/g3.json',
            'side_a4': 'evidence/cad_battery/side/g3_a4.json',
            'side_path': side, 'side_sha': SIDE_SHA if side else None, 'side_seq': side_seq,
        },
        'w271b_11772': {
            'rs': 'evidence/rs_v2/w271b_11772.json', 'd1': None,
            'genome': 'evidence/rs_v2/genomes/w271b_11772_genome.csv',
            'tip_mesh': 'evidence/cad_battery/tip_mesh/w271b_11772.json',
            'plate_gci': 'evidence/cad_battery/plate_gci/w271b_11772.json',
            'side_a4': 'evidence/cad_battery/side/w271b_11772_a4.json',
            'side_path': w11772_side, 'side_sha': w11772_sha, 'side_seq': w11772_seq,
        },
        'w271b_11860': {
            'rs': 'evidence/rs_v2/w271b_11860.json', 'd1': None,
            'genome': 'evidence/rs_v2/genomes/w271b_11860_genome.csv',
            'tip_mesh': 'evidence/cad_battery/tip_mesh/w271b_11860.json',
            'plate_gci': 'evidence/cad_battery/plate_gci/w271b_11860.json',
            'side_a4': 'evidence/cad_battery/side/w271b_11860_a4.json',
            'side_path': w11860_side, 'side_sha': w11860_sha, 'side_seq': w11860_seq,
            'd1_searched': _d1_searched('w271b_11860'),
        },
        'w271c_11522': {
            'rs': 'evidence/rs_v2/w271c_11522.json', 'd1': None,
            'genome': 'evidence/rs_v2/genomes/w271c_11522.csv',
            'tip_mesh': 'evidence/cad_battery/tip_mesh/w271c_11522.json',
            'plate_gci': 'evidence/cad_battery/plate_gci/w271c_11522.json',
            'side_a4': 'evidence/cad_battery/side/w271c_11522_a4.json',
            'side_path': w11522_side, 'side_sha': w11522_sha, 'side_seq': w11522_seq,
            'd1_searched': _d1_searched('w271c_11522'),
        },
        'w272_s2902_c01': {
            'rs': 'evidence/rs_v2/w272_xbabe3/w272_s2902_c01_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w272_xbabe3/s2902/wave272_xbabe3_s2902_c01_fit_genome.csv',
            'tip_mesh': 'evidence/cad_battery/tip_mesh/w272_s2902_c01.json',
            'plate_gci': 'evidence/cad_battery/plate_gci/w272_s2902_c01.json',
            'side_a4': 'evidence/cad_battery/side/w272_s2902_c01_a4.json',
            'side_path': w272_side, 'side_sha': w272_sha, 'side_seq': w272_seq,
        },
        'w273_s2904_c01': {
            'rs': 'evidence/rs_v2/w273_xbabe3/w273_s2904_c01_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w273_xbabe3/s2904/wave273_xbabe3_s2904_c01_fit_genome.csv',
            'tip_mesh': 'evidence/cad_battery/tip_mesh/w273_s2904_c01.json',
            'plate_gci': 'evidence/cad_battery/plate_gci/w273_s2904_c01.json',
            'side_a4': 'evidence/cad_battery/side/w273_s2904_c01_a4.json',
            'side_path': w273_2904_side, 'side_sha': w273_2904_sha, 'side_seq': w273_2904_seq,
        },
        'w273_s2903_c04': {
            'rs': 'evidence/rs_v2/w273_xbabe3/w273_s2903_c04_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w273_xbabe3/s2903/wave273_xbabe3_s2903_c04_fit_genome.csv',
            'tip_mesh': 'evidence/cad_battery/tip_mesh/w273_s2903_c04.json',
            'plate_gci': 'evidence/cad_battery/plate_gci/w273_s2903_c04.json',
            'side_a4': 'evidence/cad_battery/side/w273_s2903_c04_a4.json',
            'side_path': w273_2903_side, 'side_sha': w273_2903_sha, 'side_seq': w273_2903_seq,
        },
        'w274_s2905_c01': {
            'rs': 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_genome.csv',
            'tip_mesh': 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_solid_tip.json',
            'plate_gci': 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_plate_gci.json',
            'side_a4': 'evidence/rs_v2/w274_calibrated/w274_s2905_c01_a4.json',
            'side_path': w274_2905_side if w274_2905_sha else None,
            'side_sha': w274_2905_sha, 'side_seq': w274_2905_seq,
        },
        'w275_s2909_c01': {
            'rs': 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_genome.csv',
            'tip_mesh': 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_solid_tip.json',
            'plate_gci': 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_plate_gci.json',
            'side_a4': 'evidence/rs_v2/w275_ultrarunner/w275_s2909_c01_a4.json',
            'side_path': w275_2909_side if w275_2909_sha else None,
            'side_sha': w275_2909_sha, 'side_seq': w275_2909_seq,
        },
        'w276_s2913_c01': {
            'rs': 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_genome.csv',
            'tip_mesh': 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_solid_tip.json',
            'plate_gci': 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_plate_gci.json',
            'side_a4': 'evidence/rs_v2/w276_ultrarunner/w276_s2913_c01_a4.json',
            'side_path': w276_2913_side if w276_2913_sha else None,
            'side_sha': w276_2913_sha, 'side_seq': w276_2913_seq,
        },
        'w277_s2919_c01': {
            'rs': 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_genome.csv',
            'tip_mesh': 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_solid_tip.json',
            'plate_gci': 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_plate_gci.json',
            'side_a4': 'evidence/rs_v2/w277_ultrarunner/w277_s2919_c01_a4.json',
            'side_path': w277_2919_side if w277_2919_sha else None,
            'side_sha': w277_2919_sha, 'side_seq': w277_2919_seq,
        },
        'w278_s2922_c01': {
            'rs': 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_genome.csv',
            'tip_mesh': 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_solid_tip.json',
            'plate_gci': 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_plate_gci.json',
            'side_a4': 'evidence/rs_v2/w278_ultrarunner/w278_s2922_c01_a4.json',
            'side_path': w278_2922_side if w278_2922_sha else None,
            'side_sha': w278_2922_sha, 'side_seq': w278_2922_seq,
        },
        'w279_s2928_c01': {
            'rs': 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_rs.json', 'd1': None,
            'genome': 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_genome.csv',
            'tip_mesh': 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_solid_tip.json',
            'plate_gci': 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_plate_gci.json',
            'side_a4': 'evidence/rs_v2/w279_ultrarunner/w279_s2928_c01_a4.json',
            'side_path': w279_2928_side if w279_2928_sha else None,
            'side_sha': w279_2928_sha, 'side_seq': w279_2928_seq,
        },
    }
    return native, genomes


def _child_env(**extra) -> dict:
    import os
    env = {k: v for k, v in os.environ.items() if k != 'JARAMBIT_CAD_BATTERY'}
    env['JARAMBIT_CAD_BATTERY_DEPTH'] = '1'
    env.update(extra)
    return env


def build_subject(subject_id, commit, probes, *, geometry=None, measure=False, custom_spec=None):
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
        if subject_id in LADDER_BLOCKED:
            cases['solid.tip']['detail'] = LADDER_BLOCKED[subject_id]
        elif subject_id == 'c10a':
            c10a_rel = 'evidence/cad_battery/side/c10a_solid_tip.json'
            c10a_tip = _load(c10a_rel)
            missing = [
                f for f in SOLVER_FIELDS
                if not c10a_tip or not isinstance(c10a_tip.get(f), (int, float)) or isinstance(c10a_tip.get(f), bool)
            ]
            sf = (c10a_tip or {}).get('SF_nodal_max')
            if (c10a_tip and c10a_tip.get('schema') == 'jarambit.native_step_solid_tip.v1'
                    and c10a_tip.get('step_sha256') == sha
                    and not missing and isinstance(sf, (int, float)) and not isinstance(sf, bool)):
                cases['solid.tip'] = _case(
                    'solid.tip', 'solver_run', 'pass', solver='solid_skfem_p2',
                    geometry_sha256=sha, source_commit=commit,
                    evidence_path=c10a_rel,
                    detail={
                        'SF_nodal_max': sf,
                        'SF_nodal_avg': c10a_tip.get('SF_nodal_avg'),
                        'n_tet': c10a_tip.get('n_tet'),
                        'n_dof': c10a_tip.get('n_dof'),
                        'ksp_its': c10a_tip.get('ksp_its'),
                        'NL': c10a_tip.get('NL'),
                        'NSUB': c10a_tip.get('NSUB'),
                        'R_CUT': c10a_tip.get('R_CUT'),
                        'dolfinx_cross_check': c10a_tip.get('dolfinx_cross_check'),
                        'entered_as_solver_run': True,
                    },
                    g_inputs={'solid_tip_sf_nodal_max': sf},
                )
            else:
                cases['solid.tip']['detail'] = {
                    'inventory_solver_runs': 0,
                    'cite': 'no file names this STEP sha256 with n_tet, n_dof, ksp_its, and a numeric nodal-max SF',
                }
        role = 'archived_not_on_main' if spec.get('archived') else 'native_cad'
    elif subject_id in genomes or custom_spec is not None:
        spec = custom_spec if custom_spec is not None else genomes[subject_id]
        rs = _load(spec['rs'])
        if rs is None:
            raise FileNotFoundError(spec['rs'])
        d1 = _load(spec['d1']) if spec.get('d1') else None
        g_p = Path(spec['genome'])
        sha = _sha256(g_p if g_p.is_absolute() else ROOT / g_p)
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


def evaluate_genome_pipeline(entry: str, commit: str, probes: dict, out_dir: Path) -> dict:
    """Run the full CAD -> G1 fitness evaluator battery on `<label>=<genome.csv>`."""
    import subprocess
    import tempfile
    from fem_solid.gci import Level, MeshRef, Observable, compute_gci
    from ops.ci.side_a4 import evaluate_subject as eval_side_a4

    if '=' in entry:
        label, gpath_str = entry.split('=', 1)
    else:
        gpath_str = entry
        label = Path(gpath_str).stem.replace('_genome', '')
    gpath = Path(gpath_str)
    if not gpath.is_absolute():
        gpath = ROOT / gpath
    grel = str(gpath.relative_to(ROOT)) if gpath.is_relative_to(ROOT) else str(gpath)

    jarambit_bin = ROOT / 'target/release/jarambit'
    probe_bin = ROOT / 'target/release/examples/plate_gci_probe'
    side_bin = ROOT / 'target/release/examples/g3_side_report'

    _native, genomes = subject_catalog()
    in_catalog = label in genomes
    if in_catalog:
        spec_cat = genomes[label]
        rs_path = ROOT / spec_cat['rs']
        a1a3_path = ROOT / (spec_cat.get('side_path') or f'evidence/cad_battery/side/{label}_a1a3.json')
        gci_path = ROOT / (spec_cat.get('plate_gci') or f'evidence/cad_battery/plate_gci/{label}.json')
        a4_path = ROOT / (spec_cat.get('side_a4') or f'evidence/cad_battery/side/{label}_a4.json')
    else:
        work_dir = out_dir / '_battery_work'
        work_dir.mkdir(parents=True, exist_ok=True)
        rs_path = work_dir / f'{label}_rs.json'
        a1a3_path = work_dir / f'{label}_a1a3.json'
        gci_path = work_dir / f'{label}_plate_gci.json'
        a4_path = work_dir / f'{label}_a4.json'

    if not rs_path.is_file() and jarambit_bin.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [str(jarambit_bin), 'rs-v2-eval', '--genomes', f'{label}={grel}',
                 '--out', tmp, '--solid-dir', str(ROOT / 'evidence/fem_solid/gci')],
                cwd=ROOT, env=_child_env(), check=True,
            )
            rs_path.parent.mkdir(parents=True, exist_ok=True)
            rs_path.write_text((Path(tmp) / f'{label}.json').read_text(encoding='utf-8'), encoding='utf-8')

    if not a1a3_path.is_file() and side_bin.is_file():
        a1a3_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(side_bin), str(gpath), str(a1a3_path)], cwd=ROOT, env=_child_env(), check=True)

    if not gci_path.is_file() and probe_bin.is_file():
        with tempfile.TemporaryDirectory() as tmp:
            raw_p = Path(tmp) / 'raw_gci.json'
            subprocess.run([str(probe_bin), str(gpath), str(raw_p)], cwd=ROOT, env=_child_env(), check=True)
            raw_gci = json.loads(raw_p.read_text(encoding='utf-8'))
            levels_raw = raw_gci['levels_fine_to_coarse']
            obs_seq = Observable(id='plate_seq_ratio', metric='seq_ratio',
                                 region='blade_vs_ring_neck', projection='plate_cst_dkt', units='ratio')
            obs_sf = Observable(id='plate_sf_hunter', metric='sf_hunter',
                                region='blade_outside_4mm', projection='plate_cst_dkt', units='ratio')
            l_seq = [Level(mesh=MeshRef(id=f"{label}_area_{lv['max_area_mm2']}", revision='rev1', sha256=lv['mesh_sha256']),
                           h=float(lv['h_mm']), observable=obs_seq) for lv in levels_raw]
            l_sf = [Level(mesh=MeshRef(id=f"{label}_area_{lv['max_area_mm2']}", revision='rev1', sha256=lv['mesh_sha256']),
                          h=float(lv['h_mm']), observable=obs_sf) for lv in levels_raw]
            seq_res = compute_gci(levels_raw[0]['seq_ratio'], levels_raw[1]['seq_ratio'], levels_raw[2]['seq_ratio'],
                                  r=2.0, levels=l_seq).to_dict()
            sf_res = compute_gci(levels_raw[0]['sf_hunter'], levels_raw[1]['sf_hunter'], levels_raw[2]['sf_hunter'],
                                 r=2.0, levels=l_sf).to_dict()
            gci_doc = {
                'schema': 'jarambit.plate_gci.v1',
                'subject': label,
                'genome': grel,
                'genome_sha256': _sha256(gpath),
                'primary_observable': 'seq_ratio',
                'refinement_ratio_r': 2.0,
                'levels_fine_to_coarse': levels_raw,
                'seq_ratio_gci': seq_res,
                'sf_hunter_gci': sf_res,
            }
            gci_path.parent.mkdir(parents=True, exist_ok=True)
            gci_path.write_text(json.dumps(gci_doc, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    if not a4_path.is_file() and jarambit_bin.is_file() and rs_path.is_file() and a1a3_path.is_file():
        existing_d1 = None
        for cand_d1 in (gpath.parent / f'{label}_D1.json', gpath.parent / f'{label}.json'):
            if cand_d1.is_file():
                try:
                    doc = json.loads(cand_d1.read_text(encoding='utf-8'))
                    if isinstance(doc.get('mesh'), dict) and isinstance(doc.get('metrics'), dict):
                        existing_d1 = cand_d1
                        break
                except Exception:
                    pass
        if existing_d1 is not None:
            a4_rec = eval_side_a4(label, existing_d1, rs_path, a1a3_path)
            a4_path.parent.mkdir(parents=True, exist_ok=True)
            a4_path.write_text(json.dumps(a4_rec, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        else:
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(
                    [str(jarambit_bin), 'crescent-d1', '--genomes', f'{label}={gpath}', '--threads', '4', '--out', tmp],
                    cwd=ROOT, env=_child_env(D1_PLATES='1'), check=True,
                )
                d1_tmp = Path(tmp) / f'{label}_D1.json'
                a4_rec = eval_side_a4(label, d1_tmp, rs_path, a1a3_path)
                a4_path.parent.mkdir(parents=True, exist_ok=True)
                a4_path.write_text(json.dumps(a4_rec, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    custom_spec = None
    if not in_catalog:
        side_seq = json.loads(a1a3_path.read_text(encoding='utf-8')).get('seq_ratio_this_mesh') if a1a3_path.is_file() else None
        custom_spec = {
            'rs': str(rs_path),
            'd1': None,
            'genome': str(gpath),
            'tip_mesh': None,
            'plate_gci': str(gci_path) if gci_path.is_file() else None,
            'side_a4': str(a4_path) if a4_path.is_file() else None,
            'side_path': str(a1a3_path) if a1a3_path.is_file() else None,
            'side_sha': _sha256(a1a3_path) if a1a3_path.is_file() else None,
            'side_seq': side_seq,
        }
    record = build_subject(label, commit, probes, custom_spec=custom_spec)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f'{label}.json').write_text(json.dumps(record, indent=1, sort_keys=False) + '\n', encoding='utf-8')
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
    parser.add_argument('--evaluate-genome', help='Evaluate <label>=<genome.csv> end-to-end through the CAD battery + G1')
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'evidence' / 'cad_battery')
    parser.add_argument('--commit', default=None)
    parser.add_argument('--analytic', choices=('pass', 'fail', 'incomplete'), default='incomplete')
    parser.add_argument('--gci', choices=('pass', 'fail', 'incomplete'), default='incomplete')
    parser.add_argument('--claims', choices=('pass', 'fail', 'incomplete'), default='incomplete')
    parser.add_argument('--dolfinx', choices=('pass', 'fail', 'incomplete', 'blocked'), default=None)
    parser.add_argument('--measure-native', action='store_true')
    args = parser.parse_args(argv)
    commit = args.commit
    if commit is None:
        import subprocess
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    probes = {'analytic': args.analytic, 'gci': args.gci, 'claims': args.claims}
    if args.dolfinx is not None:
        probes['dolfinx'] = args.dolfinx
    if args.evaluate_genome:
        record = evaluate_genome_pipeline(args.evaluate_genome, commit, probes, args.out_dir)
        print(f"{record['subject']} pass={record['pass_count']} solver_runs={record['solver_run_count']} "
              f"G={record['global_fitness']['status']} ({record['global_fitness']['G']})")
        return 0
    native, genomes = subject_catalog()
    wanted = [args.subject] if args.subject else list(native) + list(genomes)
    if not args.subject and not args.all:
        parser.error('pass --subject, --all, or --evaluate-genome')
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
