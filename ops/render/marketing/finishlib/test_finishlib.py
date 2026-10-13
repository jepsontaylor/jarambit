"""pytest finishlib/test_finishlib.py  (host python; uses the production C.9.2 bundle if present)"""
import os, sys
import numpy as np
import pytest
sys.path.insert(0, os.path.dirname(__file__))
import blade_mask, thinfilm

B = os.path.expanduser('~/jarambit_render_scratch/c92_ready/mesh')


def test_thinfilm_lut_orders():
    d, rgb = thinfilm.lut(481)
    at = lambda nm: rgb[int(nm)]
    assert np.allclose(at(0), thinfilm.TI64_F0, atol=1e-6)
    b = at(24); assert b[0] > b[1] > b[2]                 # bronze
    bl = at(50); assert bl[2] > bl[0] and bl[2] > bl[1]   # royal blue
    go = at(120); assert go[0] > go[2] and go[1] > go[2]  # gold


@pytest.mark.skipif(not os.path.isfile(os.path.join(B, 'bundle.json')), reason='no C.9.2 bundle')
@pytest.mark.parametrize('geometric', [False, True])
def test_c92_blade_mask(tmp_path, geometric):
    old = dict(blade_mask.EDGE_LABEL_ZONE)
    if geometric:
        blade_mask.EDGE_LABEL_ZONE.clear()
    try:
        rep = blade_mask.compute(os.path.join(B, 'bundle.json'), os.path.join(B, 'regions.json'), str(tmp_path))
    finally:
        blade_mask.EDGE_LABEL_ZONE.update(old)
    assert rep['ok'] and 0.25 < rep['blade_frac'] < 0.45
    z = np.load(rep['masks_npz'])
    assert z['s'].min() >= 0 and z['s'].max() <= 1


@pytest.mark.skipif(not os.path.isfile(os.path.join(B, 'bundle.json')), reason='no C.9.2 bundle')
def test_tip_always_bare_even_with_bad_labels(tmp_path):
    """regression: C.9.2 point faces were labelled 'spine' -> zone coat -> tip rendered dark.
    Relabel everything within 12 mm of the point as coat-able 'body'/'spine': tip must stay bare."""
    import json, shutil
    d = np.load(os.path.join(B, 'mesh.npz'))
    m = {k: d[k] for k in d.files}
    V, F = m['V'], m['F']
    tip = V[np.argmax(V[:, 0])]
    near = np.linalg.norm(V[F].mean(1) - tip, axis=1) < 12e-3
    rid = m['region_id'].copy(); rid[near] = np.where(np.arange(near.sum()) % 2, 0, 6).astype(rid.dtype)
    m['region_id'] = rid
    src = tmp_path / 'mesh'; src.mkdir()
    np.savez(src / 'mesh.npz', **m)
    shutil.copy(os.path.join(B, 'bundle.json'), src / 'bundle.json')
    shutil.copy(os.path.join(B, 'regions.json'), src / 'regions.json')
    rep = blade_mask.compute(str(src / 'bundle.json'), str(src / 'regions.json'), str(tmp_path / 'out'), allow_warn=True)
    z = np.load(rep['masks_npz'])['zone']
    tp = np.array(rep['tip_point_m'])
    within = np.linalg.norm(V[F].mean(1) - tp, axis=1) < rep['params']['tip_check_mm'] * 1e-3
    assert rep['checks']['tip_region_bare'] and (z[within] > 0).all()
