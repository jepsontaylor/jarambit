"""Shared fixtures for the scene/finish tests. A missing required tool (Blender 4.2, ffmpeg) FAILS."""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MKT = os.path.dirname(HERE)
sys.path.insert(0, MKT)
sys.path.insert(0, os.path.join(MKT, 'blender'))
sys.path.insert(0, HERE)

import finish  # noqa: E402


@pytest.fixture(scope='session')
def blender():
    try:
        b = finish.blender_bin()
    except FileNotFoundError as e:
        pytest.fail(f'required tool missing: {e}')
    v = subprocess.run([b, '-b', '--factory-startup', '--version'], capture_output=True, text=True, timeout=120).stdout
    if 'Blender 4.2' not in v:
        pytest.fail(f'Blender 4.2 LTS required, got: {v.splitlines()[:1]}')
    return b


@pytest.fixture(scope='session')
def blender_py(blender):
    return finish.blender_python()


@pytest.fixture(scope='session')
def ffmpeg():
    p = shutil.which('ffmpeg')
    if not p:
        pytest.fail('required tool missing: ffmpeg')
    return p


def write_tiny_knife(path):
    """60 x 15 x 3 mm flat-stock blade with a V-ground edge (bevel faces + 0.6 mm apex land) as binary STL."""
    sec = np.array([(0, -1.5), (10, -1.5), (15, -0.3), (15, 0.3), (10, 1.5), (0, 1.5)], float)  # (y, z) mm
    nx = 13
    xs = np.linspace(0, 60, nx)
    curve = 6.0 * (xs / 60) ** 2  # gentle crescent: y offset along the length
    rings = [np.c_[np.full(len(sec), x), sec[:, 0] + c, sec[:, 1]] for x, c in zip(xs, curve)]
    tris = []
    n = len(sec)
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            tris += [(a[i], a[j], b[j]), (a[i], b[j], b[i])]
    for r, flip in ((rings[0], True), (rings[-1], False)):
        for i in range(1, n - 1):
            t = (r[0], r[i], r[i + 1])
            tris.append(t[::-1] if flip else t)
    tri = np.asarray(tris, np.float32)
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    # orient outward: centroid of the solid is inside, flip faces pointing inward
    c = tri.reshape(-1, 3).mean(0)
    inward = np.einsum('ij,ij->i', nrm, tri.mean(1) - c) < 0
    tri[inward] = tri[inward][:, ::-1]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nrm /= np.linalg.norm(nrm, axis=1)[:, None]
    rec = np.zeros(len(tri), np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))
    rec['n'], rec['v'] = nrm, tri
    with open(path, 'wb') as f:
        f.write(b'tiny_knife test fixture'.ljust(80, b' '))
        f.write(np.uint32(len(tri)).tobytes())
        f.write(rec.tobytes())
    return path


@pytest.fixture(scope='session')
def tiny_bundle(tmp_path_factory):
    import _stl_bundle
    d = tmp_path_factory.mktemp('tiny')
    stl = write_tiny_knife(str(d / 'tiny_knife.stl'))
    b, r = _stl_bundle.build(stl, str(d / 'mesh'), pose='upright')
    return {'stl': stl, 'bundle': b, 'regions': r, 'dir': str(d)}


def smoke_request(bundle, out_dir, n_frames=4, rig='rig_dark_strip', plan_key='smoke'):
    return {'schema': 'jarambit.render.request.v1', 'plan_key': plan_key, 'bundle_path': bundle['bundle'],
            'regions_path': bundle['regions'], 'finish_preset': 'finish_ti64', 'rig_preset': rig, 'accents': [],
            'shot': {'id': 'smoke', 'camera': {'focal_mm': 85, 'fstop': 5.6, 'sensor_mm': 36, 'focus_point': 'target'},
                     'frames': [{'index': i, 'az': 360.0 * i / n_frames, 'el': 15, 'distance_m': None, 'target': None}
                                for i in range(n_frames)]},
            'profile': {'res': [160, 90], 'spp_max': 8, 'spp_min': 0, 'adaptive_threshold': 0.05, 'denoise': True,
                        'device': 'CPU', 'seed': 0, 'hdri': 'off', 'threads': 8},
            'out_dir': out_dir}


def run_worker(blender, req, req_path, extra=()):
    json.dump(req, open(req_path, 'w'), indent=1)
    cmd = [blender, '-b', '--factory-startup', '--disable-autoexec', '--python-exit-code', '11',
           '-P', os.path.join(MKT, 'blender', 'worker.py'), '--', '--request', req_path, *extra]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    res = json.load(open(os.path.join(req['out_dir'], f'{req["shot"]["id"]}.result.json')))
    return p, res


def read_img(path, tmpdir):
    """Exact float read of EXR/16-bit PNG via finish.py (OIIO); PIL truncates 16-bit RGB PNGs to 8 bits."""
    out = os.path.join(str(tmpdir), os.path.basename(path) + '.npy')
    subprocess.run([sys.executable, os.path.join(MKT, 'finish.py'), 'npy', path, out], check=True, capture_output=True)
    return np.load(out)
