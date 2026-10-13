#!/usr/bin/env python3
"""Lookdev driver (scene lane): shot preset -> request.json -> Blender worker -> finish PNG/JPEG + Q4/Q5.

Not the production planner (plan.py/farm.py own that); this builds INTERFACES-conformant requests
for single stills / short frame lists so materials and rigs can be iterated and timed.

usage: lookdev.py --bundle B/bundle.json --regions B/regions.json --out DIR --shots hero_3q dark_hero
                  [--res 1920 1080] [--spp 512 --spp-min 64 --threshold 0.005] [--device OPTIX|CPU]
                  [--frames N (turntable shots)] [--rig-override NAME] [--finish-override NAME]
GPU etiquette: refuses to start an OPTIX/CUDA run while another process holds >50% VRAM or util.
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import finish  # noqa: E402

PRESETS = os.path.join(HERE, 'presets')


def gpu_busy():
    q = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu',
                        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=20).stdout
    for line in q.strip().splitlines():
        used, total, util = (float(x) for x in line.split(','))
        if used / total > 0.5 or util > 50:
            return f'GPU busy: {used:.0f}/{total:.0f} MiB, util {util:.0f}%'
    return None


def build_request(shot, defaults, args, plan_key, frames=None):
    tt = 'frames' in shot and isinstance(shot['frames'], int)
    if tt:
        n = frames or shot['frames']
        total = shot['frames']
        fl = [{'index': i, 'az': shot.get('az_start', 0) + 360.0 * i / total, 'el': shot['el'], 'distance_m': None,
               'target': shot.get('target')} for i in range(n)]
    else:
        fl = [{'index': 0, 'az': shot['az'], 'el': shot['el'], 'distance_m': None, 'target': shot.get('target')}]
    cam = dict(shot['camera'])
    cam.setdefault('sensor_mm', defaults.get('sensor_mm', 36))
    cam.setdefault('focus_point', 'target')
    req = {'schema': 'jarambit.render.request.v1', 'plan_key': plan_key, 'bundle_path': os.path.abspath(args.bundle),
           'regions_path': os.path.abspath(args.regions) if args.regions else None,
           'finish_preset': args.finish_override or defaults.get('finish_preset', 'finish_ti64'),
           'rig_preset': args.rig_override or shot['rig'], 'accents': args.accents or defaults.get('accents', []),
           'shot': {'id': shot['id'], 'camera': cam, 'frames': fl,
                    'pose': shot.get('pose', defaults.get('pose', 'as_is')),
                    'fill': shot.get('fill', defaults.get('fill')), 'margin': defaults.get('margin', 0.06),
                    'roll_deg': shot.get('roll_deg', 0.0)},
           'profile': {'res': list(args.res), 'spp_max': args.spp, 'spp_min': args.spp_min,
                       'adaptive_threshold': args.threshold, 'denoise': True, 'device': args.device, 'seed': 0,
                       'hdri': args.hdri},
           'out_dir': os.path.abspath(os.path.join(args.out, shot['id']))}
    if shot.get('field_mm'):
        req['shot']['field_mm'] = shot['field_mm']
    return req


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bundle', required=True); ap.add_argument('--regions')
    ap.add_argument('--out', required=True); ap.add_argument('--shots', nargs='+', required=True)
    ap.add_argument('--res', nargs=2, type=int, default=[1920, 1080])
    ap.add_argument('--spp', type=int, default=512); ap.add_argument('--spp-min', type=int, default=64)
    ap.add_argument('--threshold', type=float, default=0.005)
    ap.add_argument('--device', default='OPTIX'); ap.add_argument('--frames', type=int)
    ap.add_argument('--hdri', default='required')
    ap.add_argument('--rig-override'); ap.add_argument('--finish-override'); ap.add_argument('--accents', nargs='*')
    ap.add_argument('--tag', default='lookdev'); ap.add_argument('--force', action='store_true')
    ap.add_argument('--no-finish', action='store_true')
    args = ap.parse_args()
    shots = json.load(open(os.path.join(PRESETS, 'shots_default.json')))
    by_id = {s['id']: s for s in shots['stills'] + shots['turntables']}
    summary = []
    for sid in args.shots:
        if args.device.upper() != 'CPU':
            while True:
                b = gpu_busy()
                if not b:
                    break
                print(f'[lookdev] {b}; waiting 60 s (yield rule)', flush=True)
                time.sleep(60)
        req = build_request(by_id[sid], shots['defaults'], args, f'{args.tag}:{sid}', args.frames)
        os.makedirs(req['out_dir'], exist_ok=True)
        rq = os.path.join(req['out_dir'], 'request.json')
        json.dump(req, open(rq, 'w'), indent=1)
        cmd = [finish.blender_bin(), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '11',
               '-P', os.path.join(HERE, 'blender', 'worker.py'), '--', '--request', rq] + (['--force'] if args.force else [])
        t0 = time.time()
        log = open(os.path.join(req['out_dir'], 'worker.log'), 'w')
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
        res = json.load(open(os.path.join(req['out_dir'], f'{sid}.result.json')))
        if rc != 0 or res['errors']:
            print(f'[lookdev] {sid} FAILED rc={rc} {res["errors"]} (see worker.log)', flush=True)
            sys.exit(1)
        for fr in res['frames']:
            if args.no_finish:
                continue
            stem = fr['raw_exr'][:-len('.raw.exr')]
            png = stem + '.png'
            subprocess.run([sys.executable, os.path.join(HERE, 'finish.py'), 'png', fr['denoised_exr'] or fr['raw_exr'],
                            png, '--jpeg', stem + '.jpg', '--record', stem + '.finish.json'], check=True,
                           stdout=subprocess.DEVNULL)
            st = json.loads(subprocess.run([sys.executable, os.path.join(HERE, 'finish.py'), 'stats', png, '--mask',
                                            fr['passes']['mask']], check=True, capture_output=True, text=True).stdout)
            fr['stats'] = st
        summary.append({'shot': sid, 'wall_s': round(time.time() - t0, 1), 'framing': res['framing'],
                        'frames': [{k: fr.get(k) for k in ('index', 'seconds', 'spp_mean', 'fstop', 'stats')}
                                   for fr in res['frames']]})
        print(json.dumps(summary[-1]), flush=True)
    json.dump(summary, open(os.path.join(args.out, f'summary_{args.tag}.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
