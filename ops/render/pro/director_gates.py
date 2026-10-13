"""Absolute-state partition and deliberate-fault gates. Any unsuccessful gate exits nonzero.
python director_gates.py PREP_DIR FILM.json OUT_DIR [--finish flame]
"""
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile

try:
    from . import qa, runtime
except ImportError:
    import qa, runtime


def normal_pass(receipt, frames, returncode):
    if not isinstance(receipt, dict):
        return False
    rows = receipt.get('frames', [])
    return (returncode == 0 and receipt.get('all_pass') is True and receipt.get('render_ready') is True
            and not receipt.get('fault') and isinstance(rows, list) and bool(frames)
            and len(rows) == len(frames) and all(isinstance(r, dict) for r in rows)
            and {r.get('frame') for r in rows} == set(frames)
            and all(qa.frame_pass(r, dry=True) and r.get('physical_state_sha256') for r in rows))


def fault_pass(receipt, frames, returncode, fault):
    if not isinstance(receipt, dict):
        return False
    rows = receipt.get('frames', [])
    if not (returncode != 0 and receipt.get('fault') == fault and receipt.get('all_pass') is False
            and receipt.get('render_ready') is False and isinstance(rows, list) and rows
            and all(isinstance(r, dict) and r.get('frame') in frames and qa.passed(r.get('edge_sharpness'))
                    and isinstance(r.get('lights_pass'), bool) and isinstance(r.get('sig_mesh_pass'), bool)
                    and isinstance(r.get('sig'), dict) and isinstance(r['sig'].get('pass'), bool)
                    and r.get('physical_state_sha256') for r in rows)):
        return False
    if fault == 'light_in_frame':
        return any(r.get('lights_pass') is False for r in rows)
    return any(r.get('sig_mesh_pass') is False or r.get('sig', {}).get('pass') is False for r in rows)


def main(argv=None):
    runtime.ensure_memcap()
    args = sys.argv[1:] if argv is None else argv
    prep, film, out = args[:3]; extra = args[3:]
    B = os.path.expanduser('~/opt/blender-4.2.23-linux-x64/blender')
    here = Path(__file__).resolve().parent
    os.makedirs(out, exist_ok=True)
    # Never accept a previous invocation's receipt after a failed child process.
    evidence = tempfile.mkdtemp(prefix='director-', dir=out)
    F = json.load(open(film))
    allf = [f for S in F['shots'] for f in range(S['frames'][0], S['frames'][1], 37)]
    res = {'all_pass': False}

    def run(name, frames, fault=None):
        threads = runtime.safe_workers()
        cmd = [B, '-b', '--threads', str(threads), '--python-exit-code', '1', '-P', str(here / 'pro_hero.py'), '--',
               '--prep', prep, '--out', evidence, '--res', 'preview', '--anim', film, '--dry', '1',
               '--frames', ','.join(map(str, frames)), '--receipt', name + '.json', *extra]
        if fault:
            cmd += ['--fault', fault]
        with open(os.path.join(evidence, name + '.log'), 'w') as log:
            proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        receipt = json.load(open(os.path.join(evidence, name + '.json')))
        return receipt, proc.returncode

    try:
        if not allf or len(set(allf)) != len(allf):
            raise ValueError('director film must have nonempty, nonoverlapping frame ranges')
        full, rc = run('contiguous', allf)
        full_ok = normal_pass(full, allf, rc)
        h_full = {x['frame']: x['physical_state_sha256'] for x in full.get('frames', [])}
        rnd = random.Random(870); shuffled = allf[:]; rnd.shuffle(shuffled)
        h_sh = {}; shards_ok = True
        for i, sh in enumerate([shuffled[i::3] for i in range(3)]):
            if not sh:
                continue
            shard, rc = run(f'shard{i}', sh[::-1])
            shards_ok = normal_pass(shard, sh, rc) and shards_ok
            for x in shard.get('frames', []):
                h_sh[x['frame']] = x['physical_state_sha256']
        mism = [f for f in allf if h_full.get(f) != h_sh.get(f)]
        partition_ok = not mism and set(h_full) == set(h_sh) == set(allf)
        res['absolute_state_partition'] = {'frames': len(allf), 'mismatches': mism, 'pass': partition_ok}
        res['contiguous_all_pass'] = full_ok
        res['shards_all_pass'] = shards_ok
        faults_ok = True
        for fault in ('light_in_frame', 'sig_off_flat'):
            receipt, rc = run('fault_' + fault, allf[:4], fault)
            ok = fault_pass(receipt, allf[:4], rc, fault)
            res['fault_' + fault] = {'gate_failed_as_required': ok, 'pass': ok}
            faults_ok = faults_ok and ok
        res['all_pass'] = bool(full_ok and shards_ok and partition_ok and faults_ok)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        res['error'] = str(e)
    res['evidence_dir'] = evidence
    json.dump(res, open(os.path.join(out, 'director_gates.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))
    return 0 if res['all_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
