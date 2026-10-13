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


def test_mark_validate_logic():
    import mark
    zone = np.zeros(10, np.uint8)
    src = np.zeros(10, bool); src[3:5] = True
    rep = {'sources': ['labels'], 'source_faces_mask': src, 'decal': None}
    assert not mark.validate(rep, zone)['mark_faces_bare']          # mark faces left coatable -> fail
    zone[3:5] = 5
    assert all(mark.validate(rep, zone).values())
    rep2 = {'sources': ['decal'], 'source_faces_mask': np.zeros(10, bool),
            'decal': {'placements': [], 'requested': 2}}
    v = mark.validate(rep2, zone)
    assert not v['mark_decal_placed'] and not v['mark_present_if_in_source']   # decal dropped -> fail


@pytest.mark.skipif(not os.path.isfile(os.path.join(B, 'bundle.json')), reason='no C.9.2 bundle')
def test_c92_label_mark_becomes_zone5(tmp_path):
    """a CAD label named 'logo' must become zone 5 (bare mark), never coat."""
    import json, shutil
    d = np.load(os.path.join(B, 'mesh.npz')); m = {k: d[k] for k in d.files}
    rj = json.load(open(os.path.join(B, 'regions.json')))
    rid = m['region_id'].copy()
    body = np.nonzero(rid == 0)[0][:200]
    rid[body] = 7; m['region_id'] = rid
    rj['labels']['7'] = 'logo'
    src = tmp_path / 'mesh'; src.mkdir()
    np.savez(src / 'mesh.npz', **m)
    shutil.copy(os.path.join(B, 'bundle.json'), src / 'bundle.json')
    json.dump(rj, open(src / 'regions.json', 'w'))
    rep = blade_mask.compute(str(src / 'bundle.json'), str(src / 'regions.json'), str(tmp_path / 'o'), allow_warn=True)
    z = np.load(rep['masks_npz'])['zone']
    assert (z[body] == 5).all() and rep['checks']['mark_faces_bare'] and 'labels' in rep['mark']['sources']


def test_raster_rejects_huge_extent(tmp_path):
    """100x scaled mesh must fail closed before allocating multi-hundred-GiB distance maps."""
    import json
    import numpy as np
    import blade_mask
    V = np.array([[0, 0, 0], [1, 0, 0], [0, 0.3, 0], [0.2, 0.1, 0.002]], float) * 100.0
    F = np.array([[0, 1, 2], [0, 2, 3]], np.int32)
    np.savez(tmp_path / "mesh.npz", V=V, F=F)
    (tmp_path / "bundle.json").write_text(json.dumps({"npz": "mesh.npz", "npz_sha256": "x"}))
    out = tmp_path / "masks"
    out.mkdir()
    # Force the hard reject: tiny budget + huge max_grid so coarsening still exceeds bytes.
    raised = False
    try:
        blade_mask.compute(
            str(tmp_path / "bundle.json"), None, str(out), allow_warn=True,
            params={"max_grid_px": 200000, "max_raster_bytes": 8 * 1024 * 1024, "raster_mm": 0.1},
        )
    except ValueError as e:
        raised = any(k in str(e).lower() for k in ("raster", "budget", "gib"))
        assert raised, e
    assert raised
