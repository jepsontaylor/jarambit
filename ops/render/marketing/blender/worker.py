"""Blender worker: request.json (jarambit.render.request.v1) -> raw/denoised EXR + passes + result.json.

blender -b --factory-startup --disable-autoexec --python-exit-code 11 \
    -P ops/render/marketing/blender/worker.py -- --request R.json [--force] [--threads 16]

Per frame (written atomically, tmp dir -> os.replace) into out_dir:
  <shot>_<idx>.raw.exr       scene-linear RGBA half, no denoise (kept)
  <shot>_<idx>.denoised.exr  OIDN (albedo+normal guides) copy, if profile.denoise
  <shot>_<idx>.normal.exr / .depth.exr / .mask.exr   passes (mask = antialiased product id mask)
  <shot>_<idx>.receipt.json  host, device, gpu uuid, seed, spp, seconds, sha256 of every file
A rerun skips frames whose receipt still verifies (resume), unless --force.

Request extensions (optional, all recorded in result.json):
  shot.pose: "as_is" | "lay_flat" (rx -90: blade plane faces +Z) | "stand_up" (rx +90)
  shot.roll_deg, shot.fill [lo,hi], shot.margin, shot.field_mm (macro: distance from field width)
  shot.camera.dof_policy: "whole_object" (f-stop raised until CoC <= 1.5 px over the part) | "fixed"
  frames[].target / camera.focus_point: [x,y,z] canonical m | null (bbox centre) | "auto:<region>"
  frames[].distance_m: null -> fallback auto-framing (rigmath.fit_distance)
  profile.hdri: "required" (default) | "optional" | "off";  profile.bounces/clamp_indirect/threads
"""
import argparse
import glob
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import cameras  # noqa: E402
import lights  # noqa: E402
import materials  # noqa: E402
import rigmath  # noqa: E402
import scene  # noqa: E402

PRESETS = os.path.join(os.path.dirname(HERE), 'presets')
HDRI_SEARCH = [os.environ.get('JARAMBIT_HDRI_DIR', ''), '~/jarambit_render_scratch/hdri',
               os.path.join(os.path.dirname(HERE), 'hdri')]
POSES = {'as_is': np.eye(3),
         'lay_flat': np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]]),
         'stand_up': np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])}


def preset(name_or_path):
    p = name_or_path
    if not os.path.isfile(p):
        p = os.path.join(PRESETS, name_or_path if name_or_path.endswith('.json') else name_or_path + '.json')
    d = json.load(open(p))
    return d, os.path.abspath(p), scene.sha256(p)


def emitter_corners_world(ob):
    """World corner points of a Blender light object (AREA: its rectangle/disc box; else a small cube)."""
    from mathutils import Vector as _V
    ld = ob.data
    M = ob.matrix_world
    if ld.type == 'AREA':
        sx = ld.size / 2
        sy = (ld.size_y if ld.shape in ('RECTANGLE', 'ELLIPSE') else ld.size) / 2
        loc = [(-sx, -sy, 0), (sx, -sy, 0), (sx, sy, 0), (-sx, sy, 0)]
    else:
        r = max(getattr(ld, 'shadow_soft_size', 0.0), 1e-3)
        loc = [(a * r, b * r, c * r) for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)]
    return np.array([list(M @ _V(p)) for p in loc])


def check_emitters_out_of_frame(frames, pivot, focal, sensor, res, z_floor, mirror_floor=True):
    """Every light must stay out of every frame, directly and as its mirror image in the floor plane
    (a glossy floor reflects it). Camera rays never see emitters anyway (visible_camera off); this
    guards the art direction against reflections and against a rig that drifts into shot."""
    bpy.context.view_layer.update()
    viol = []
    cams = []
    for f in frames:
        cam_pos, t = rigmath.frame_camera(pivot, f['target'], f['az'], f['el'], f['distance_m'])
        cams.append((f['index'], cam_pos, t, f['roll']))
    n = 0
    for ob in bpy.context.scene.objects:
        if ob.type != 'LIGHT':
            continue
        n += 1
        P = emitter_corners_world(ob)
        sets = [('direct', P)]
        if mirror_floor:
            Pm = P.copy(); Pm[:, 2] = 2 * z_floor - Pm[:, 2]
            sets.append(('floor_mirror', Pm))
        for kind, Q in sets:
            for idx, cam_pos, t, roll in cams:
                if rigmath.segment_hits_frame(Q, cam_pos, t, focal, sensor, res, roll):
                    viol.append({'light': ob.name, 'kind': kind, 'frame': idx})
                    break
    return {'lights_checked': n, 'frames_checked': len(cams), 'violations': viol}


def atomic_json(path, obj):
    tmp = path + f'.tmp{os.getpid()}'
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def gpu_uuid():
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=uuid', '--format=csv,noheader'], capture_output=True,
                             text=True, timeout=20).stdout.split()
        return out[0] if out else None
    except Exception:
        return None


def exr_stats(path):
    import OpenImageIO as oiio
    a = oiio.ImageInput.open(path)
    px = a.read_image(format='float')
    a.close()
    px = np.asarray(px)[..., 0]
    return float(px.mean()), float(np.percentile(px, 95))


def resolve_point(p, pivot, label_pts):
    if p is None:
        return np.asarray(pivot, float), 'bbox_center'
    if isinstance(p, str) and p.startswith('auto:'):
        # 'auto:a,b,...' tries each source in order; 'thin_edge' = vertices within 0.3 mm of the blade
        # mid-plane (only the sharpened apex reaches it on a flat-stock part; independent of labels)
        pts, lab = None, None
        for lab in p.split(':', 1)[1].split(','):
            pts = label_pts.get(lab)
            if pts is not None and len(pts):
                break
        if pts is None or not len(pts):
            raise ValueError(f'auto target {p!r}: no candidate points')
        # inner-most point of the region within its 50-90 % length band (the concave cutting edge of a
        # crescent sits closer to the part centre than the convex spine)
        x = pts[:, 0]
        cand = pts[(x >= np.quantile(x, 0.5)) & (x <= np.quantile(x, 0.9))]
        k = np.argmin(np.linalg.norm(cand - pivot, axis=1))
        return cand[k], f'auto:{lab}@innermost_x50-90%'
    return np.asarray(p, float), 'given'


def frame_identity(req, f, prof, res, seed):
    """What a resumable frame must match: plan, shot, frame, resolution, sample budget, seed."""
    return {'plan_key': req['plan_key'], 'shot_id': req['shot']['id'], 'index': int(f['index']),
            'res': [int(res[0]), int(res[1])], 'spp': int(prof['spp_max']), 'seed': int(seed)}


def planned_seed(req, f, prof):
    """The resolved plan's per-frame seed (carried in the request), independent of sharding.
    Requests without it (old lookdev) fall back to the plan_key/index formula with no shard input."""
    if f.get('seed') is not None:
        return int(f['seed'])
    return rigmath.frame_seed(req['plan_key'], f['index'], prof.get('seed', 0))


def verify_receipt(rp, identity=None):
    try:
        r = json.load(open(rp))
        if identity is not None and r.get('identity') != identity:
            return None  # another plan/frame/profile: rerender, never resume
        for k, (path, sha) in r['files'].items():
            if not os.path.isfile(path) or scene.sha256(path) != sha:
                return None
        return r
    except Exception:
        return None


def run(req, force=False, threads=16):
    t_start = time.time()
    if req.get('schema') != 'jarambit.render.request.v1':
        raise ValueError(f'unsupported request schema {req.get("schema")!r}')
    out_dir = os.path.abspath(req['out_dir'])
    os.makedirs(out_dir, exist_ok=True)
    shot, prof, cam_spec = req['shot'], req['profile'], req['shot']['camera']
    sid = shot['id']
    sc = scene.reset()
    bundle, mesh = scene.load_bundle(req['bundle_path'])
    regions = json.load(open(req['regions_path'])) if req.get('regions_path') else None
    if regions and regions.get('schema') != 'jarambit.render.regions.v1':
        raise ValueError('unsupported regions schema')
    pose_name = shot.get('pose', 'as_is')
    Rp = POSES[pose_name]
    mesh = dict(mesh)
    mesh['V'] = mesh['V'] @ Rp.T
    mesh['N_corner'] = (mesh['N_corner'].reshape(-1, 3) @ Rp.T).reshape(mesh['N_corner'].shape)
    mesh['tangent'] = mesh['tangent'] @ Rp.T
    V, F = mesh['V'], mesh['F']
    lo, hi = V.min(0), V.max(0)
    pivot = (lo + hi) / 2
    D = float(np.linalg.norm(hi - lo))
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1), 1e-300)[:, None]
    cen = V[F].mean(1)
    rid = np.asarray(mesh['region_id'])
    label_pts = {lab: cen[rid == i] for i, lab in enumerate(materials.LABELS)}
    label_nrm = {lab: fn[rid == i] for i, lab in enumerate(materials.LABELS)}
    _, _, axes = rigmath.principal_axes(V)
    mid = (V - V.mean(0)) @ axes[:, 0]
    label_pts['thin_edge'] = V[np.abs(mid - np.median(mid)) < 0.3e-3]

    finish, finish_path, finish_sha = preset(req['finish_preset'])
    rig, rig_path, rig_sha = preset(req['rig_preset'])
    devices = scene.setup_render(prof, threads=prof.get('threads', threads))

    part = scene.build_part(mesh)
    tt = scene.build_turntable(part, pivot)
    mat_rec = materials.assign(part, finish, req.get('accents', []))

    # frames: resolve targets and distances
    frames = []
    for f in shot['frames']:
        tgt, tsrc = resolve_point(f.get('target'), pivot, label_pts)
        frames.append({'index': int(f['index']), 'az': float(f['az']), 'el': float(f['el']),
                       'roll': float(shot.get('roll_deg', 0.0)), 'target': tgt, 'target_src': tsrc,
                       'distance_m': f.get('distance_m'), 'seed': f.get('seed')})
    res = prof['res']
    focal, sensor = float(cam_spec['focal_mm']), float(cam_spec.get('sensor_mm', 36.0))
    framing = {'source': 'request'}
    if any(f['distance_m'] is None for f in frames):
        if shot.get('field_mm'):
            d = float(shot['field_mm']) * 1e-3 * focal / sensor
            framing = {'source': 'field_mm', 'field_mm': shot['field_mm']}
        else:
            d, rep = rigmath.fit_distance(V, pivot, frames, focal, sensor, res, tuple(shot.get('fill', (0.62, 0.78))),
                                          shot.get('margin', 0.06))
            framing = {'source': 'worker_fallback_fit', **rep}
        for f in frames:
            if f['distance_m'] is None:
                f['distance_m'] = d
    # measured framing for every frame (Q3 evidence)
    Vs = V[:: max(1, len(V) // 4000)]
    mins, fills = [], []
    near, far = np.inf, 0.0
    for f in frames:
        cam_pos, t = rigmath.frame_camera(pivot, f['target'], f['az'], f['el'], f['distance_m'])
        u, v, z = rigmath.project(rigmath.frame_points(Vs, pivot, f['az']), cam_pos, t, focal, sensor, res, f['roll'])
        mins.append(float(min(u.min(), 1 - u.max(), v.min(), 1 - v.max())))
        fills.append(float(u.max() - u.min()))
        near, far = min(near, z.min()), max(far, z.max())
    framing.update({'margin_min': min(mins), 'fill_min': min(fills), 'fill_max': max(fills),
                    'distance_m': sorted({round(f['distance_m'], 6) for f in frames})})

    # world, backdrop, lights (fixed for the shot, computed from frame 0)
    z_floor = float(lo[2] - pivot[2]) - rig['backdrop'].get('gap_D', 0.0) * D
    bd_mat = materials.floor_material(rig['backdrop']['material'])
    scene.build_backdrop(rig['backdrop'], D, z_floor, bd_mat)
    hdri_mode = prof.get('hdri', 'required')
    hdri_path, hdri_rec = None, None
    w = rig['world']
    if w.get('hdri') and hdri_mode != 'off':
        hdri_path = scene.find_hdri(w['hdri']['file'], w['hdri'].get('sha256'), [p for p in HDRI_SEARCH if p])
        if hdri_path is None and hdri_mode == 'required':
            raise FileNotFoundError(f'HDRI {w["hdri"]["file"]} not found in {HDRI_SEARCH} (profile.hdri=required)')
        if hdri_path:
            hdri_rec = {'path': hdri_path, 'sha256': w['hdri'].get('sha256'), 'source': w['hdri'].get('source')}
    exposure_scale = 2.0 ** float(rig.get('exposure_ev', 0.0))  # scales every emitter (lights + world)
    scene.build_world(w, hdri_path, exposure_scale)
    f0 = frames[0]
    cam_pos0, t0 = rigmath.frame_camera(pivot, f0['target'], f0['az'], f0['el'], f0['distance_m'])
    R0 = rigmath.rot_z(-f0['az'])
    mctx = {'cam_pos': cam_pos0,
            'regions': {k: ((label_pts[k] - pivot) @ R0.T, label_nrm[k] @ R0.T) for k in label_nrm if len(label_nrm[k])}}
    light_rec = lights.build(rig, D, np.zeros(3), exposure_scale, mctx)
    emitter_check = check_emitters_out_of_frame(frames, pivot, focal, sensor, res, z_floor,
                                                rig.get('backdrop', {}).get('type') != 'none')
    if emitter_check['violations'] and not rig.get('allow_emitter_in_frame', False):
        raise RuntimeError(f'emitter visible in frame (direct or floor mirror): {emitter_check["violations"]}')

    cam = cameras.build(cam_spec)
    dof_policy = cam_spec.get('dof_policy', 'whole_object')
    fstop_req = cam_spec.get('fstop')
    focus_pt = cam_spec.get('focus_point', 'target')

    tmp_root = os.path.join(out_dir, f'.tmp_{sid}_{os.getpid()}')
    shutil.rmtree(tmp_root, ignore_errors=True)
    os.makedirs(tmp_root)
    scene.setup_compositor(tmp_root, denoise=bool(prof.get('denoise', True)))
    sc.frame_current = 0
    uuid = gpu_uuid() if prof.get('device', 'CPU').upper() != 'CPU' else None
    host = socket.gethostname()
    results = []
    for f in frames:
        stem = os.path.join(out_dir, f'{sid}_{f["index"]:04d}')
        rp = stem + '.receipt.json'
        seed = planned_seed(req, f, prof)
        ident = frame_identity(req, f, prof, res, seed)
        if not force:
            r = verify_receipt(rp, ident)
            if r:
                results.append({**r['frame'], 'resumed': True})
                continue
        cam_pos, t = rigmath.frame_camera(pivot, f['target'], f['az'], f['el'], f['distance_m'])
        tt.rotation_euler = (0.0, 0.0, np.radians(-f['az']))
        cameras.place(cam, cam_pos, t, f['roll'])
        if focus_pt == 'target' or focus_pt is None:
            fp_world = t
        else:
            fp, _ = resolve_point(focus_pt, pivot, label_pts)
            fp_world = rigmath.rot_z(-f['az']) @ (fp - pivot)
        focus_dist = float(np.dot(cam_pos - fp_world, rigmath.look_at_basis(cam_pos, t)[2]))
        fstop = fstop_req
        if fstop_req and dof_policy == 'whole_object':
            fstop = rigmath.auto_fstop(near, far, focus_dist, focal, sensor, res[0], fmin=float(fstop_req))
        cameras.set_dof(cam, focus_dist, fstop)
        sc.cycles.seed = seed
        for p in glob.glob(os.path.join(tmp_root, '*')):
            os.remove(p)
        t1 = time.time()
        bpy.ops.render.render(write_still=False)
        secs = time.time() - t1
        files = {}
        for key, ext in (('raw', 'raw'), ('den', 'denoised'), ('normal', 'normal'), ('depth', 'depth'),
                         ('mask', 'mask'), ('spp', 'spp')):
            src = glob.glob(os.path.join(tmp_root, f'{key}_*.exr'))
            if not src:
                continue
            dst = f'{stem}.{ext}.exr'
            os.replace(src[0], dst)
            files[ext] = dst
        if 'raw' not in files:
            raise RuntimeError(f'frame {f["index"]}: compositor wrote no raw EXR')
        # Cycles stores the sample-count pass normalised by the sample budget
        spp_mean, spp_p95 = (x * int(prof['spp_max']) for x in exr_stats(files.pop('spp')))
        os.remove(f'{stem}.spp.exr')
        shas = {k: scene.sha256(p) for k, p in files.items()}
        fr = {'index': f['index'], 'raw_exr': files['raw'], 'denoised_exr': files.get('denoised'),
              'passes': {k: files.get(k) for k in ('normal', 'depth', 'mask')},
              'spp': int(prof['spp_max']), 'spp_mean': round(spp_mean, 2), 'spp_p95': round(spp_p95, 1),
              'seconds': round(secs, 3), 'device': prof.get('device', 'CPU').upper(), 'gpu_uuid': uuid,
              'sha256': shas['raw'], 'sha256_all': shas, 'seed': seed, 'az': f['az'], 'el': f['el'],
              'distance_m': f['distance_m'], 'fstop': fstop, 'focus_m': round(focus_dist, 5)}
        atomic_json(rp, {'host': host, 'frame': fr, 'files': {k: [p, shas[k]] for k, p in files.items()},
                         'plan_key': req['plan_key'], 'identity': ident, 'time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        results.append(fr)
        print(f'[worker] {sid} frame {f["index"]} {secs:.1f}s spp_mean {spp_mean:.0f}', flush=True)
    shutil.rmtree(tmp_root, ignore_errors=True)
    return {'schema': 'jarambit.render.result.v1', 'frames': results, 'blender_version': bpy.app.version_string,
            'errors': [], 'plan_key': req['plan_key'], 'shot_id': sid, 'host': host, 'devices': devices,
            'platform': platform.platform(),
            'source': bundle.get('source'), 'npz_sha256': bundle.get('npz_sha256'),
            'normal_policy': bundle.get('normal_policy'), 'pose': pose_name, 'pivot_m': pivot.tolist(), 'D_m': D,
            'regions_method': regions.get('method') if regions else None,
            'finish': {'path': finish_path, 'sha256': finish_sha, 'assignment': mat_rec,
                       'appearance_assumed': True, 'accents': req.get('accents', [])},
            'rig': {'path': rig_path, 'sha256': rig_sha, 'lights': light_rec, 'hdri': hdri_rec,
                    'artistic_visibility': bool(rig['world'].get('glossy_only', False)),
                    'exposure_ev': rig.get('exposure_ev', 0.0), 'emitter_check': emitter_check},
            'camera': {'focal_mm': focal, 'sensor_mm': sensor, 'dof_policy': dof_policy, 'fstop_request': fstop_req},
            'framing': framing, 'wall_seconds': round(time.time() - t_start, 2)}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--request', required=True)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--threads', type=int, default=16)
    a = ap.parse_args(argv)
    req = json.load(open(a.request))
    out_dir = os.path.abspath(req.get('out_dir', '.'))
    os.makedirs(out_dir, exist_ok=True)
    res_path = os.path.join(out_dir, f'{req.get("shot", {}).get("id", "shot")}.result.json')
    try:
        result = run(req, a.force, a.threads)
        atomic_json(res_path, result)
        print(f'[worker] OK {res_path}', flush=True)
    except Exception as e:
        traceback.print_exc()
        atomic_json(res_path, {'schema': 'jarambit.render.result.v1', 'frames': [], 'errors': [repr(e)],
                               'blender_version': bpy.app.version_string})
        sys.stdout.flush()
        os._exit(11)


if __name__ == '__main__':
    main()
