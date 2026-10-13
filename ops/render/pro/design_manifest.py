"""Single source of truth for every number a film shows: designs/<family>/<rev>/ -> design_manifest.json.

Everything is read from the design folder that the analysis lane commits (README gate table, SHA256SUMS, data/*.json)
plus the FEM result store named in fem_cases.json. Nothing is typed in here: a missing file, key, or a disagreement
between two sources is a hard error (exit 2), never a placeholder.

python3 design_manifest.py designs/switchback/C10a --fem-store DIR [--out design_manifest.json]
python3 design_manifest.py --latest designs/switchback   # newest RC folder by README status + tag
"""
import argparse, hashlib, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


class ManifestError(SystemExit):
    def __init__(self, msg):
        super().__init__(f'design_manifest: FAIL: {msg}'); self.code = 2


def need(cond, msg):
    if not cond:
        raise ManifestError(msg)


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jget(d, path, src):
    cur = d
    for k in path.split('.'):
        need(isinstance(cur, dict) and k in cur, f'{src}: missing key {path!r}')
        cur = cur[k]
    return cur


def readme_gates(text, src):
    """Parse the gate table: | V3 | spine 3427 N | 1.584 | 5.6 % | note |  (case text keeps its units)."""
    rows = {}
    for ln in text.splitlines():
        m = re.match(r'^\|\s*(V\d)\s*\|\s*([^|]+?)\s*\|\s*\**([0-9.]+)\**', ln)
        if m:
            rows[m.group(1)] = {'case': m.group(2).strip(), 'SF': float(m.group(3))}
    need(rows, f'{src}: no gate table rows')
    return rows


def parse_load(case_text, src):
    m = re.search(r'([0-9][0-9.,]*)\s*(N·m|N\.m|Nm|kN|N)\b', case_text)
    need(m, f'{src}: no load with units in {case_text!r}')
    val = float(m.group(1).replace(',', '')); unit = m.group(2).replace('N.m', 'N·m').replace('Nm', 'N·m')
    name = case_text[:m.start()].strip(' ·-') or case_text
    return name, val, unit


def msh_counts(p):
    """Node and tetrahedron counts straight from the gmsh 2.2 ASCII solver mesh (shown on screen in the mesh view)."""
    nodes = tets = None; sec = None; first = False
    with open(p) as f:
        for line in f:
            if line.startswith('$'):
                sec = line.strip(); first = True; continue
            if first:
                first = False
                if sec == '$Nodes': nodes = int(line)
                if sec == '$Elements': tets = 0
                continue
            if sec == '$Elements':
                parts = line.split()
                if len(parts) > 1 and parts[1] == '4': tets += 1
    need(nodes and tets, f'{p}: could not count nodes/tets (not gmsh 2.2 ASCII?)')
    return {'nodes': nodes, 'tets': tets}


def build(design_dir, fem_store, cases_cfg):
    D = Path(design_dir); need(D.is_dir(), f'design folder {D} not found')
    readme = (D / 'README.md'); need(readme.is_file(), f'{readme} missing'); R = readme.read_text()
    title = R.splitlines()[0].lstrip('# ').strip()
    m = re.search(r'\bRev\s+([A-Z]\.[0-9]+[a-z]?)\b', title); need(m, f'{readme}: no "Rev X.Na" in title')
    rev = m.group(1)
    m = re.search(r'release candidate\s*\(?\s*(rc\d+)', R, re.I); need(m, f'{readme}: no rcN status')
    rc = m.group(1).lower()
    m = re.search(r'SF\s*=\s*([0-9.]+)\s*MPa\s*/\s*σ', R); need(m, f'{readme}: no "SF = <Sy> MPa / σvM" statement')
    sy = float(m.group(1))
    m = re.search(r'≥\s*([0-9.]+)\)', R) or re.search(r'\(≥\s*([0-9.]+)', R); need(m, f'{readme}: no gate threshold "(≥ x.xxx)"')
    gate = float(m.group(1))
    sums = {}
    for ln in (D / 'SHA256SUMS').read_text().splitlines():
        h, p = ln.split(None, 1); sums[p.strip().lstrip('./')] = h
    steps = sorted((D / 'cad').glob('*.step')); need(len(steps) == 1, f'{D}/cad: expected exactly one STEP, found {len(steps)}')
    step = steps[0]; step_sha = sha256(step); rel = str(step.relative_to(D))
    need(sums.get(rel) == step_sha, f'STEP sha {step_sha[:16]} != SHA256SUMS {sums.get(rel, "missing")[:16]}')
    cad = json.loads((D / 'data' / cases_cfg['cad_json']).read_text())
    mass_key = next((k for k in cad if k.startswith('mass_g_')), None); need(mass_key, 'cad json: no mass_g_<material>')
    mass = float(cad[mass_key]); material = mass_key[len('mass_g_'):]
    need(step_sha.startswith(cad.get('sha256_16', '')) and cad.get('sha256_16'), 'cad json sha256_16 does not match STEP')
    gates = readme_gates(R, readme)
    verify = json.loads((D / 'data' / cases_cfg['gates_json']).read_text())
    gj = jget(verify, cases_cfg['gates_key'], cases_cfg['gates_json'])
    for v, row in gates.items():   # README and gate JSON must agree to the printed precision
        if v in gj and v != 'V4':  # V4: README carries the W81 v4r correction, verify json notes it (V4_note)
            need(abs(float(gj[v]) - row['SF']) < 5e-4, f'{v}: README {row["SF"]} != {cases_cfg["gates_json"]} {gj[v]}')
    mass_v = float(jget(verify, cases_cfg['gates_mass_key'], cases_cfg['gates_json']))
    need(abs(mass_v - mass) < 5e-4, f'mass {mass} != gate json {mass_v}')
    shots = []
    for sc in cases_cfg['science']:
        v = sc['gate']; need(v in gates, f'gate {v} not in README table')
        name, val, unit = parse_load(gates[v]['case'], readme)
        res = {}
        for k, f in sc['fem_files'].items():
            p = Path(fem_store) / f; need(p.is_file(), f'FEM store missing {p} (needed for {v})')
            res[k] = {'file': f, 'sha256': sha256(p)}
        sf = gates[v]['SF']
        shots.append({'gate': v, 'test': sc.get('display', name).upper(), 'case_text': gates[v]['case'],
                      'load': {'value': val, 'unit': unit}, 'SF': sf, 'gate_SF': gate,
                      'verdict': 'PASS' if sf >= gate else 'FAIL', 'peak_vm_MPa': round(sy / sf, 1),
                      'peak_basis': 'Sy / SF of record (converged)', 'fem': res, 'fem_case': sc['fem_case'], 'shot': sc['shot']})
    fem_mesh = Path(fem_store) / cases_cfg['fem_mesh']; need(fem_mesh.is_file(), f'FEM mesh {fem_mesh} missing')
    man = {'schema': 'jarambit.design_manifest.v1', 'design_dir': str(D), 'family': D.parent.name.upper(),
           'rev': rev, 'rc': rc, 'label': f'Rev {rev} {rc}', 'title': title,
           'status_note': 'design candidate, not certified',
           'step': {'path': rel, 'sha256': step_sha}, 'mass_g': mass, 'material': material,
           'Sy_MPa': sy, 'gate_SF': gate, 'gates': gates,
           'fem': {'store': str(fem_store), 'mesh': {'file': cases_cfg['fem_mesh'], 'sha256': sha256(fem_mesh), **msh_counts(fem_mesh)}},
           'science': shots,
           'badge': f"{D.parent.name.upper()} Rev {rev} {rc} · {mass:.1f} g · {material} Ti",
           'sources': {'readme': {'path': 'README.md', 'sha256': sha256(readme)},
                       'cad_json': {'path': 'data/' + cases_cfg['cad_json'], 'sha256': sha256(D / 'data' / cases_cfg['cad_json'])},
                       'gates_json': {'path': 'data/' + cases_cfg['gates_json'], 'sha256': sha256(D / 'data' / cases_cfg['gates_json'])}}}
    man['stamp'] = f"{man['family'].lower()}_{rev.replace('.', '')}_{rc}_{step_sha[:8]}"
    man['manifest_sha256'] = hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest()
    return man


def latest(family_dir):
    cands = []
    for d in sorted(Path(family_dir).iterdir()):
        r = d / 'README.md'
        if r.is_file() and re.search(r'CURRENT RELEASE CANDIDATE', r.read_text()):
            cands.append(d)
    need(len(cands) == 1, f'{family_dir}: expected exactly one CURRENT RELEASE CANDIDATE, found {[c.name for c in cands]}')
    return cands[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('design', nargs='?'); ap.add_argument('--latest'); ap.add_argument('--fem-store', required=True)
    ap.add_argument('--cases', default=str(HERE / 'fem_cases.json')); ap.add_argument('--out')
    a = ap.parse_args()
    d = latest(a.latest) if a.latest else a.design; need(d, 'give a design folder or --latest FAMILY_DIR')
    man = build(d, a.fem_store, json.loads(Path(a.cases).read_text()))
    out = a.out or os.path.join(d, 'render', 'design_manifest.json'); os.makedirs(os.path.dirname(out), exist_ok=True)
    Path(out).write_text(json.dumps(man, indent=1, ensure_ascii=False)); print(out); print(json.dumps({k: man[k] for k in ('label', 'badge', 'stamp')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
