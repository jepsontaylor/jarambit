"""Director-book gate tests for the pro pipeline (run on the GPU host; no renders, --dry state only).
1. Absolute-state / partition: the same absolute frames resolved in one contiguous pass and in irregular,
   reversed-order shards must give identical physical-state hashes.
2. Deliberate faults must FAIL: a light placed in frame; a signature moved off the flat.
python director_gates.py PREP_DIR FILM.json OUT_DIR [--finish flame]"""
import json, os, subprocess, sys, random
prep, film, out = sys.argv[1:4]; extra = sys.argv[4:]
B = os.path.expanduser('~/opt/blender-4.2.23-linux-x64/blender'); HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(out, exist_ok=True)
F = json.load(open(film)); allf = [f for S in F['shots'] for f in range(S['frames'][0], S['frames'][1], 37)]


def run(name, frames, fault=None):
    cmd = [B, '-b', '-P', os.path.join(HERE, 'pro_hero.py'), '--', '--prep', prep, '--out', out, '--res', 'preview',
           '--anim', film, '--dry', '1', '--frames', ','.join(map(str, frames)), '--receipt', name + '.json'] + extra
    if fault: cmd += ['--fault', fault]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return json.load(open(os.path.join(out, name + '.json')))


res = {}
full = run('contiguous', allf)
h_full = {x['frame']: x['physical_state_sha256'] for x in full['frames']}
rnd = random.Random(870); shuffled = allf[:]; rnd.shuffle(shuffled)
shards = [shuffled[i::3] for i in range(3)]
h_sh = {}
for i, sh in enumerate(shards):
    for x in run(f'shard{i}', sh[::-1])['frames']: h_sh[x['frame']] = x['physical_state_sha256']
mism = [f for f in allf if h_full.get(f) != h_sh.get(f)]
res['absolute_state_partition'] = {'frames': len(allf), 'mismatches': mism, 'pass': not mism and len(h_sh) == len(allf)}
res['contiguous_all_pass'] = full['all_pass']
for fault in ('light_in_frame', 'sig_off_flat'):
    r = run('fault_' + fault, allf[:4], fault)
    res['fault_' + fault] = {'gate_failed_as_required': not r['all_pass'], 'pass': not r['all_pass']}
res['all_pass'] = all(v['pass'] for k, v in res.items() if isinstance(v, dict))
json.dump(res, open(os.path.join(out, 'director_gates.json'), 'w'), indent=1); print(json.dumps(res, indent=1))
