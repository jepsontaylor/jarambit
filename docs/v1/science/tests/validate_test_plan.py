#!/usr/bin/env python3
"""Validate this documentation package; does not execute proposed science tests.

Run from an admitted environment with python3. --input-root can point to the
owned remote archive containing all 22 original source files. Omitting it skips
source-byte rechecks explicitly; manifest and structural checks still run.
"""
import argparse
import datetime
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys


def strict_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key} in {path}")
            result[key] = value
        return result
    def bad_constant(token):
        raise ValueError(f"nonfinite literal {token} in {path}")
    return json.loads(path.read_text(), object_pairs_hook=pairs,
                      parse_constant=bad_constant)


def topological(packets):
    nodes = {p['id']: p for p in packets}
    assert len(nodes) == len(packets), 'duplicate packet ID'
    done, visiting, order = set(), set(), []
    def visit(pid):
        assert pid in nodes, f'unknown dependency {pid}'
        assert pid not in visiting, f'dependency cycle at {pid}'
        if pid in done:
            return
        visiting.add(pid)
        for parent in nodes[pid]['depends_on']:
            visit(parent)
        visiting.remove(pid)
        done.add(pid)
        order.append(pid)
    for pid in nodes:
        visit(pid)
    return order


def overlaps(a, b):
    # Exact files versus recursive directory/glob zones. Deliberately conservative.
    def parts(value):
        prefix = value.split('*', 1)[0]
        return prefix.rstrip('/'), '*' in value or value.endswith('/')
    pa, ra = parts(a)
    pb, rb = parts(b)
    return pa == pb or (ra and pb.startswith(pa + '/')) or (rb and pa.startswith(pb + '/'))


def validate(root, input_root):
    parent = root.parent
    units = strict_load(root/'TEST_WORK_PACKETS.json')
    catalog = strict_load(root/'TEST_CASE_CATALOG.json')
    sources = strict_load(root/'SOURCE_MANIFEST.json')
    gates = strict_load(root/'CI_GATE_POLICY.json')
    master = strict_load(parent/'WORK_PACKETS.json')
    all_json = sorted(root.rglob('*.json'))
    for path in all_json:
        strict_load(path)
    t_order = topological(units['packets'])
    s_order = topological(master['packets'])
    t_by = {p['id']: p for p in units['packets']}
    s_by = {p['id']: p for p in master['packets']}
    assert len(t_by) == 20
    assert len(s_by) == 17
    assert {p['target_version'] for p in (units, catalog, gates)} == {'1.0.0'}
    for p in units['packets']:
        assert set(p['parent_S_owners']) <= set(s_by)
        assert p['write_allowlist'] and p['case_ids']
        assert p['validation_argv_after_implementation']
    cases = {c['id']: c for c in catalog['cases']}
    assert len(cases) == len(catalog['cases']) == catalog['case_group_count'] == 178
    assert master['test_upgrade']['planned_challenge_groups'] == len(cases)
    referenced = [cid for p in units['packets'] for cid in p['case_ids']]
    assert len(referenced) == len(set(referenced)) == len(cases)
    assert set(referenced) == set(cases)
    for cid, case in cases.items():
        p = t_by[case['work_unit']]
        assert cid in p['case_ids']
        assert case['challenge'] and case['oracle'] and case['controls']
        assert case['positive_control_required'] and case['negative_control_required']
        assert any(overlaps(case['allowed_test_path'], allow) for allow in p['write_allowlist'])
    group_pairs = 0
    for group in units['parallel_write_groups']:
        assert len(group) <= units['max_parallel_workers']
        for pid in group:
            assert pid in t_by
            # The declared wave may not contain another member's prerequisite.
            ancestors = set()
            def collect(node):
                for dep in t_by[node]['depends_on']:
                    if dep not in ancestors:
                        ancestors.add(dep)
                        collect(dep)
            collect(pid)
            assert not (ancestors & set(group)), f'dependent parallel group {pid}'
        for a, b in itertools.combinations(group, 2):
            for pa in t_by[a]['write_allowlist']:
                for pb in t_by[b]['write_allowlist']:
                    assert not overlaps(pa, pb), f'write overlap {a}/{b}: {pa}/{pb}'
            group_pairs += 1
    parent_group_pairs = 0
    for group in master['parallel_write_groups']:
        for a, b in itertools.combinations(group, 2):
            for pa in s_by[a]['write_allowlist']:
                for pb in s_by[b]['write_allowlist']:
                    assert not overlaps(pa, pb), f'parent scope overlap {a}/{b}: {pa}/{pb}'
            parent_group_pairs += 1
    # Parent owner assignments are exact scope supplements, not broad extra rights.
    assignments = master['test_upgrade']['ownership_assignments']
    for path, owner in assignments.items():
        assert path in t_by[owner['T']]['write_allowlist']
        assert path in s_by[owner['S']]['test_scope_supplement']
        assert path in s_by[owner['S']]['write_allowlist']
    inherited = catalog['original_regression_test_overlay']
    assert len(inherited) == len(master['regression_mapping']) == 19
    assert set(inherited) == set(master['regression_mapping'])
    assert catalog['original_regression_mapping'] == master['regression_mapping']
    assert set(inherited.values()) <= set(cases)
    required = set(gates['required_software_case_groups'])
    assert len(required) == gates['required_software_group_count']
    assert len(required) == 108
    assert required == {cid for cid, c in cases.items()
                        if c['execution_gate'] == 'mandatory_for_software_rc'}
    assert set(inherited.values()) <= required, 'inherited regression became optional'
    for cap in gates['capabilities'].values():
        assert cap['unit'] in t_by
        assert set(cap['required_case_ids']) == set(t_by[cap['unit']]['case_ids'])
    assert len(sources['inputs']) == 22
    assert len({x['name'] for x in sources['inputs']}) == 22
    hashes = 0
    if input_root:
        for item in sources['inputs']:
            candidates = list(input_root.rglob(item['name']))
            assert len(candidates) == 1, f'input archive not unique: {item["name"]}'
            actual = hashlib.sha256(candidates[0].read_bytes()).hexdigest()
            assert actual == item['sha256'], f'input changed: {item["name"]}'
            hashes += 1
    comparison = sources['selected_source_comparison']['comparison']
    assert len(comparison) == 48
    assert all(x['unchanged'] == (x['old_sha256'] == x['current_sha256']) for x in comparison)
    latest = sources['latest_origin_selected_comparison']['comparison']
    assert len(latest) == 48
    assert {x['path'] for x in latest} == {x['path'] for x in comparison}
    assert all(x['unchanged'] == (x['old_sha256'] == x['current_sha256']) for x in latest)
    assert sum(x['unchanged'] for x in latest) == 47
    links, shell_blocks = 0, 0
    for path in sorted(parent.rglob('*.md')):
        body = path.read_text()
        for target in re.findall(r'\]\(([^\n)]+)\)', body):
            if target.startswith(('http:', 'https:', '#', '/', 'codex:')):
                continue
            target = target.split('#', 1)[0]
            if target:
                assert (path.parent/target).exists(), f'broken Markdown link {path}: {target}'
                links += 1
        if path.parent != root:
            continue
        for shell in re.findall(r'```bash\n(.*?)```', body, flags=re.S):
            completed = subprocess.run(['bash', '-n'], input=shell,
                                       text=True, capture_output=True)
            assert completed.returncode == 0, completed.stderr
            for line in shell.splitlines():
                if line.strip() and not line.lstrip().startswith('#'):
                    assert line.startswith('rtk '), 'desktop command lacks RTK prefix'
            shell_blocks += 1
    return {
        'schema': 'jarambit.test_plan.validation.v1',
        'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status': 'passed',
        'validation_scope': 'planning package only; no proposed tests/solvers/lab runs',
        'work_units': len(t_by), 'parent_packets': len(s_by),
        'planned_challenge_groups': len(cases), 'required_software_groups': len(required),
        'original_regressions_retained': len(inherited),
        'input_manifest_entries': 22, 'source_input_hashes_rechecked': hashes,
        'input_hash_check_status': 'passed' if input_root else 'not_run; provide --input-root',
        'source_comparison_entries': 48,
        'unchanged_selected_sources': sum(x['unchanged'] for x in comparison),
        'T_topological_order': t_order, 'S_topological_order': s_order,
        'dependency_model': 'internal T overlays; two acyclic DAGs and exact parent ownership assignments',
        'disjoint_parallel_group_pairs': group_pairs,
        'disjoint_parent_parallel_group_pairs': parent_group_pairs,
        'local_markdown_links_checked': links, 'bash_blocks_syntax_checked': shell_blocks,
        'strict_json_files_checked': len(all_json)
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = validate(Path(__file__).resolve().parent, args.input_root)
    rendered = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end='')


if __name__ == '__main__':
    main()
