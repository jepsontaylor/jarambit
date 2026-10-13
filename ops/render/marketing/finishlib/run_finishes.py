#!/usr/bin/env python3
"""ONE command: CAD/mesh + finish list -> blade/coat masks (validated) -> hero renders -> contact sheet.

  python3 finishlib/run_finishes.py --bundle MESH/bundle.json [--regions MESH/regions.json] \
      --out OUT --finishes all|id1 id2 ... [--res 1920 1080] [--spp 256] [--shot hero_3q]
  python3 finishlib/run_finishes.py --cad part.step --out OUT ...     # runs ingest.py first

Outputs (OUT/):
  masks/finish_masks.npz, masks/blade_mask.json, masks/blade_mask_2d.png   (fails with exit 3 if bad)
  tf_lut.npy, thinfilm_chart.png
  <finish>/<shot>/<shot>_0000.{png,jpg,...}   one hero render per finish, same camera/rig as hero_3q
  mask_debug/<shot>/...   zone false-colour render from the hero camera
  blade_mask_debug.jpg    3-D zone render + 2-D front/back footprint
  contact_sheet.jpg, run_summary.json
Camera, rig and framing come verbatim from presets/shots_default.json via lookdev.build_request.
"""
import argparse, json, os, subprocess, sys, time

# hero_3q camera is always reused; only the rig/backdrop changes. dark = dark_hero's reflective black base
MARK_PL = []
BACKDROPS = {'dark': 'rig_dark_strip', 'studio': None}
HERE = os.path.dirname(os.path.abspath(__file__))
MKT = os.path.dirname(HERE)
sys.path.insert(0, MKT); sys.path.insert(0, HERE)
import finish  # noqa: E402
import lookdev  # noqa: E402
import blade_mask  # noqa: E402
import thinfilm  # noqa: E402


def load_library(path):
    txt = open(path).read()
    if path.endswith(('.yaml', '.yml')):
        import yaml
        lib = yaml.safe_load(txt)
    else:
        lib = json.loads(txt)
    bare = lib.pop('_bare_specs', {})
    for k, v in lib.items():
        v['id'] = k
        if v.get('type') != 'mask_debug' and not v.get('layers'):
            raise ValueError(f'finish {k}: needs layers')
    return lib, bare


def render(entry, args, masks, lut_path, arc_m, out_root, bare_specs=None):
    shots = json.load(open(os.path.join(MKT, 'presets', 'shots_default.json')))
    by_id = {s['id']: s for s in shots['stills']}
    ns = argparse.Namespace(bundle=args.bundle, regions=args.regions, out=os.path.join(out_root, entry['id']),
                            finish_override=None, rig_override=BACKDROPS[args.backdrop], accents=None, res=args.res, spp=args.spp, spp_min=args.spp_min,
                            threshold=args.threshold, no_adaptive=False, device=args.device, hdri='required')
    req = lookdev.build_request(by_id[args.shot], shots['defaults'], ns, f'finishlib:{entry["id"]}:{args.shot}')
    req['finish_library'] = {'entry': entry, 'masks_npz': masks, 'lut_npy': lut_path,
                             'lut_dmax_nm': thinfilm.DMAX_NM, 'arc_length_m': arc_m,
                             'bare_specs': bare_specs or {}, 'mark_placements': MARK_PL, 'coat_boost': not args.no_coat_boost}
    req['profile']['threads'] = args.threads
    os.makedirs(req['out_dir'], exist_ok=True)
    rq = os.path.join(req['out_dir'], 'request.json')
    json.dump(req, open(rq, 'w'), indent=1)
    cmd = (['nice', '-n', '15'] if args.device.upper() == 'CPU' else []) + [finish.blender_bin(), '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '11',
           '-P', os.path.join(MKT, 'blender', 'worker.py'), '--', '--request', rq, '--force']
    if args.device.upper() != 'CPU':
        while (b := lookdev.gpu_busy()):
            print(f'[finishlib] {b}; waiting 60 s (yield rule)', flush=True); time.sleep(60)
    t0 = time.time()
    with open(os.path.join(req['out_dir'], 'worker.log'), 'w') as log:
        if args.device.upper() != 'CPU':
            with lookdev.GpuLock():
                rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
        else:
            rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT).returncode
    sid = args.shot
    res = json.load(open(os.path.join(req['out_dir'], f'{sid}.result.json')))
    if rc != 0 or res['errors']:
        raise RuntimeError(f'{entry["id"]}: worker failed rc={rc} {res.get("errors")} ({req["out_dir"]}/worker.log)')
    fr = res['frames'][0]
    stem = fr['raw_exr'][:-len('.raw.exr')]
    subprocess.run([sys.executable, os.path.join(MKT, 'finish.py'), 'png', fr['denoised_exr'] or fr['raw_exr'],
                    stem + '.png', '--jpeg', stem + '.jpg', '--record', stem + '.finish.json'], check=True,
                   stdout=subprocess.DEVNULL)
    return {'id': entry['id'], 'label': entry.get('label', entry['id']), 'jpg': stem + '.jpg', 'png': stem + '.png',
            'seconds': round(time.time() - t0, 1), 'rig': req['rig_preset'], 'assignment': res['finish']['assignment']}


def mark_closeups(results, out, mask_debug_png):
    """crop every finish at the mark: bbox of the green mark pixels in the zone-debug render."""
    import numpy as np
    from PIL import Image, ImageDraw
    a = np.asarray(Image.open(mask_debug_png).convert('RGB')).astype(int)
    g = (a[..., 1] > 150) & (a[..., 0] < 90) & (a[..., 2] < 110)
    if g.sum() < 20:
        raise RuntimeError('mark not visible in the zone-debug render from the hero camera')
    ys, xs = np.nonzero(g)
    x0, x1, y0, y1 = np.percentile(xs, 1), np.percentile(xs, 99), np.percentile(ys, 1), np.percentile(ys, 99)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w = max(x1 - x0, (y1 - y0) * 2.2) * 1.35
    box = (int(cx - w / 2), int(cy - w / 4.4), int(cx + w / 2), int(cy + w / 4.4))
    crops = []
    for r in results:
        c = Image.open(r['png']).convert('RGB').crop(box).resize((720, 360), Image.LANCZOS)
        ImageDraw.Draw(c).text((6, 6), r['id'], fill=(255, 255, 255)); crops.append(c)
    rows = (len(crops) + 2) // 3
    sheet = Image.new('RGB', (720 * 3, 360 * rows), (10, 10, 10))
    for i, c in enumerate(crops):
        sheet.paste(c, ((i % 3) * 720, (i // 3) * 360))
    sheet.save(os.path.join(out, 'signature_closeups.jpg'), quality=92)


def tip_closeups(results, out, box_frac=0.12):
    """tip crop per finish: tip = right-most product-mask pixel (mask.exr pass, excludes reflection)."""
    import numpy as np
    from PIL import Image, ImageDraw
    crops = []
    for r in results:
        mexr = r['png'][:-len('.png')] + '.mask.exr'
        npy = mexr + '.npy'
        subprocess.run([sys.executable, os.path.join(MKT, 'finish.py'), 'npy', mexr, npy], check=True,
                       stdout=subprocess.DEVNULL)
        m = np.load(npy); m = m[..., 0] if m.ndim == 3 else m
        os.remove(npy)
        ys, xs = np.nonzero(m > 0.5)
        k = np.argmax(xs); cx, cy = xs[k], ys[k]
        im = Image.open(r['jpg']).convert('RGB')
        h = int(im.width * box_frac)
        x0, y0 = max(0, cx - int(h * 0.8)), max(0, cy - h // 3)
        c = im.crop((x0, y0, x0 + h, y0 + h)).resize((360, 360), Image.LANCZOS)
        ImageDraw.Draw(c).text((6, 6), r['id'], fill=(255, 255, 255))
        crops.append(c)
    W = 360 * min(5, len(crops)); rows = (len(crops) + 4) // 5
    sheet = Image.new('RGB', (W, 360 * rows), (10, 10, 10))
    for i, c in enumerate(crops):
        sheet.paste(c, ((i % 5) * 360, (i // 5) * 360))
    sheet.save(os.path.join(out, 'tip_closeups.jpg'), quality=92)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--bundle'); src.add_argument('--cad', help='STEP/STL -> ingest.py first')
    ap.add_argument('--regions'); ap.add_argument('--out', required=True)
    ap.add_argument('--library', default=os.path.join(HERE, 'finishes.yaml'))
    ap.add_argument('--finishes', nargs='+', default=['all'])
    ap.add_argument('--shot', default='hero_3q')
    ap.add_argument('--res', nargs=2, type=int, default=[1920, 1080])
    ap.add_argument('--spp', type=int, default=256); ap.add_argument('--spp-min', type=int, default=32)
    ap.add_argument('--threshold', type=float, default=0.02)
    ap.add_argument('--device', default='OPTIX', help='OPTIX (waits for idle GPU + flock) or CPU (niced)')
    ap.add_argument('--threads', type=int, default=48)
    ap.add_argument('--no-coat-boost', action='store_true', help='disable albedo-aware coat exposure boost')
    ap.add_argument('--backdrop', choices=list(BACKDROPS), default='dark',
                    help='dark (default): glossy black base with reflection (rig_dark_strip); studio: original grey softbox')
    ap.add_argument('--masks-only', action='store_true'); ap.add_argument('--allow-mask-warn', action='store_true')
    ap.add_argument('--no-mask-render', action='store_true')
    args = ap.parse_args()
    # Contain mask + render RAM: re-exec under ~/bin/memcap 32G (no-swap cgroup) unless already inside one.
    if os.environ.get('JARAMBIT_FINISHLIB_MEMCAP') != '1':
        memcap = os.path.expanduser('~/bin/memcap')
        if os.path.isfile(memcap) and os.access(memcap, os.X_OK):
            env = os.environ.copy()
            env['JARAMBIT_FINISHLIB_MEMCAP'] = '1'
            raise SystemExit(subprocess.call([memcap, '32G', '--', sys.executable, *sys.argv], env=env))
        else:
            print('[finishlib] WARNING: ~/bin/memcap missing; continuing without cgroup MemoryMax', flush=True)
    out = os.path.abspath(args.out); os.makedirs(out, exist_ok=True)
    if args.cad:
        py = os.environ.get('JARAMBIT_CAD_PYTHON', sys.executable)
        mdir = os.path.join(out, 'mesh')
        subprocess.run([py, os.path.join(MKT, 'ingest.py'), args.cad, '--out', mdir], check=True)
        args.bundle = os.path.join(mdir, 'bundle.json')
        if not args.regions and os.path.isfile(os.path.join(mdir, 'regions.json')):
            args.regions = os.path.join(mdir, 'regions.json')
    if not args.regions:
        cand = os.path.join(os.path.dirname(os.path.abspath(args.bundle)), 'regions.json')
        args.regions = cand if os.path.isfile(cand) else None
    # 1. masks (fail loudly)
    rep = blade_mask.compute(args.bundle, args.regions, os.path.join(out, 'masks'), allow_warn=args.allow_mask_warn)
    global MARK_PL
    MARK_PL = ((rep.get('mark') or {}).get('decal') or {}).get('placements') or []
    # 2. thin-film LUT
    d, rgb = thinfilm.lut()
    lut_path = os.path.join(out, 'tf_lut.npy')
    import numpy as np
    np.save(lut_path, rgb.astype(np.float32))
    thinfilm.chart(os.path.join(out, 'thinfilm_chart.png'), d, rgb,
                   {'bronze': 24, 'purple': 38, 'blue': 50, 'lt blue': 68, 'gold': 115, 'magenta': 142, 'teal': 180})
    if args.masks_only:
        return
    lib, bare_specs = load_library(args.library)
    ids = list(lib) if args.finishes == ['all'] else args.finishes
    arc_m = rep['arc_length_mm'] * 1e-3
    results = []
    if not args.no_mask_render:
        md = render({'id': 'mask_debug', 'type': 'mask_debug', 'label': 'blade mask debug'}, args,
                    rep['masks_npz'], lut_path, arc_m, out)
        from PIL import Image, ImageDraw
        a = Image.open(md['jpg']).convert('RGB'); b = Image.open(os.path.join(out, 'masks', 'blade_mask_2d.png')).convert('RGB')
        b = b.resize((a.width, round(b.height * a.width / b.width)))
        sheet = Image.new('RGB', (a.width, a.height + b.height), (12, 12, 14)); sheet.paste(a, (0, 0)); sheet.paste(b, (0, a.height))
        ImageDraw.Draw(sheet).text((20, 20), 'BLADE MASK DEBUG  blue = coated | yellow blade flat, orange bevel, red apex, magenta serration = BARE  '
                                   f"method={rep['method']} blade={rep['blade_frac']:.1%} checks_ok={rep['ok']}", fill=(255, 255, 255))
        sheet.save(os.path.join(out, 'blade_mask_debug.jpg'), quality=90)
    lib_bad = [f for f in ids if f not in lib]
    if lib_bad:
        raise SystemExit(f'unknown finishes {lib_bad}; library has {list(lib)}')
    for fid in ids:
        e = dict(lib[fid]); print(f'[finishlib] render {fid}', flush=True)
        results.append(render(e, args, rep['masks_npz'], lut_path, arc_m, out, bare_specs))
        print(f'[finishlib] {fid} done {results[-1]["seconds"]} s', flush=True)
    finish.contact_sheet(os.path.join(out, 'contact_sheet.jpg'), [r['jpg'] for r in results], cols=3, width=960,
                         labels=[f"{r['id']}: {r['label']}  (coat +{r['assignment'].get('coat_boost_ev', 0):.2f} EV)" for r in results])
    tip_closeups(results, out)
    if MARK_PL and not args.no_mask_render:
        mark_closeups(results, out, md['png'])
    json.dump({'mask': rep, 'results': results, 'args': vars(args)}, open(os.path.join(out, 'run_summary.json'), 'w'), indent=1)
    print(os.path.join(out, 'contact_sheet.jpg'))


if __name__ == '__main__':
    main()
