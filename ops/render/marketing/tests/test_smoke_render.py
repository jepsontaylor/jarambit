"""Smoke: tiny knife, 160x90 CPU 8 spp, 4 turntable frames -> raw/denoised EXR + passes + receipts ->
AgX PNG -> MP4 -> full decode. Also resume (receipts) and Q12 rerun determinism."""
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

from conftest import MKT, read_img, run_worker, smoke_request

FINISH = os.path.join(MKT, 'finish.py')


def finish_png(exr, png):
    subprocess.run([sys.executable, FINISH, 'png', exr, png], check=True, capture_output=True)
    return read_img(png, os.path.dirname(png))


def test_smoke_render_resume_determinism_mp4(blender, ffmpeg, tiny_bundle, tmp_path):
    out = str(tmp_path / 'out')
    req = smoke_request(tiny_bundle, out)
    t0 = time.time()
    p, res = run_worker(blender, req, str(tmp_path / 'req.json'))
    wall = time.time() - t0
    assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-3000:]
    assert res['errors'] == []
    assert wall < 60, f'smoke render took {wall:.1f}s (budget 60 s)'
    assert [f['index'] for f in res['frames']] == [0, 1, 2, 3]
    assert res['blender_version'].startswith('4.2')
    assert res['source']['sha256'] and res['npz_sha256']
    assert res['finish']['appearance_assumed'] is True
    assert res['framing']['margin_min'] >= 0.06 - 1e-6
    assert 0.62 <= res['framing']['fill_max'] <= 0.78 + 1e-6
    pngs = []
    for f in res['frames']:
        for k in ('raw_exr', 'denoised_exr'):
            assert os.path.isfile(f[k])
        for k in ('normal', 'depth', 'mask'):
            assert os.path.isfile(f['passes'][k])
        rec = json.load(open(f['raw_exr'].replace('.raw.exr', '.receipt.json')))
        assert rec['frame']['sha256'] == f['sha256']
        assert f['device'] == 'CPU' and f['spp'] == 8
        png = f['raw_exr'].replace('.raw.exr', '.png')
        img = finish_png(f['denoised_exr'], png)
        assert img.shape == (90, 160, 3)
        pngs.append(png)
    # the part is in frame: product mask covers a sane fraction
    st = json.loads(subprocess.run([sys.executable, FINISH, 'stats', pngs[0], '--mask', res['frames'][0]['passes']['mask']],
                                   check=True, capture_output=True, text=True).stdout)
    assert 0.02 < st['mask_frac'] < 0.6, st

    # resume: every receipt verifies -> nothing re-rendered
    p2, res2 = run_worker(blender, req, str(tmp_path / 'req.json'))
    assert p2.returncode == 0 and all(f.get('resumed') for f in res2['frames'])

    # Q12: forced rerun is pixel-identical within 1/255 (fixed per-frame seeds)
    out_b = str(tmp_path / 'out_b')
    req_b = dict(req, out_dir=out_b)
    p3, res3 = run_worker(blender, req_b, str(tmp_path / 'req_b.json'), ['--force'])
    assert p3.returncode == 0
    for fa, fb in zip(res['frames'], res3['frames']):
        assert fa['seed'] == fb['seed']
        a = finish_png(fa['denoised_exr'], str(tmp_path / 'a.png'))
        b = finish_png(fb['denoised_exr'], str(tmp_path / 'b.png'))
        assert np.abs(a - b).mean() <= 1 / 255

    # MP4 (bt709 tv range via zscale) + full decode with exact frame count
    mp4 = str(tmp_path / 'smoke.mp4')
    pat = os.path.join(out, 'smoke_%04d.png')
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-framerate', '30', '-i', pat, '-vf',
                    'zscale=matrixin=input:min=gbr:m=709:r=limited:t=709:p=709,format=yuv420p,scale=160:90',
                    '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709',
                    '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv', '-movflags', '+faststart', mp4],
                   check=True)
    pr = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                                    'stream=nb_read_frames,color_space,color_primaries,color_transfer,color_range',
                                    '-of', 'json', mp4], check=True, capture_output=True, text=True).stdout)['streams'][0]
    assert int(pr['nb_read_frames']) == 4
    assert pr['color_space'] == 'bt709' and pr['color_range'] == 'tv'
    subprocess.run([ffmpeg, '-v', 'error', '-i', mp4, '-f', 'null', '-'], check=True)


def test_missing_bundle_fails_loudly(blender, tiny_bundle, tmp_path):
    req = smoke_request(tiny_bundle, str(tmp_path / 'o'), n_frames=1)
    req['bundle_path'] = str(tmp_path / 'nope' / 'bundle.json')
    p, res = run_worker(blender, req, str(tmp_path / 'r.json'))
    assert p.returncode == 11 and res['errors'] and res['frames'] == []


def test_required_hdri_missing_fails(blender, tiny_bundle, tmp_path, monkeypatch):
    req = smoke_request(tiny_bundle, str(tmp_path / 'o'), n_frames=1)
    rig = json.load(open(os.path.join(MKT, 'presets', 'rig_dark_strip.json')))
    rig['world']['hdri'] = {'file': 'definitely_missing_hdri.hdr', 'sha256': '0' * 64}
    rp = tmp_path / 'rig.json'
    rp.write_text(json.dumps(rig))
    req['rig_preset'] = str(rp)
    req['profile']['hdri'] = 'required'
    p, res = run_worker(blender, req, str(tmp_path / 'r.json'))
    assert p.returncode == 11 and 'HDRI' in res['errors'][0]


def test_optix_request_without_gpu_never_falls_back(blender, tiny_bundle, tmp_path):
    """device OPTIX either renders on an OptiX device or fails; it must not silently use the CPU."""
    req = smoke_request(tiny_bundle, str(tmp_path / 'o'), n_frames=1)
    req['profile']['device'] = 'OPTIX'
    if shutil.which('nvidia-smi') and subprocess.run(['nvidia-smi', '-L'], capture_output=True).returncode == 0:
        return  # covered by the GPU lookdev runs (kernel compile is too slow for CI)
    p, res = run_worker(blender, req, str(tmp_path / 'r.json'))
    assert p.returncode == 11 and 'OPTIX' in res['errors'][0]
