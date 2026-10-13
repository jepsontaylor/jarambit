"""Q6 colour fidelity + display-transform parity.

1. ColorChecker emission patches -> Cycles -> scene-linear EXR -> finish.py (view Standard, i.e. the
   plain sRGB encode) -> 16-bit PNG: CIEDE2000 vs the reference sRGB values, mean <= 2.0, max <= 4.0.
   (AgX intentionally tone-maps, so absolute chart fidelity is measured on the Standard view.)
2. The same EXR through finish.py's AgX path vs OCIO-AgX applied to the reference linear values:
   mean <= 2.0, max <= 4.0 (render + EXR + finish chain adds no colour error under the production view).
3. finish.py AgX + 'Medium High Contrast' equals Blender's own colour-managed PNG save (<= 1/255).
4. CIEDE2000 implementation against Sharma et al. (2005) reference pairs.
"""
import os
import subprocess
import sys

import numpy as np
import pytest

from conftest import HERE, MKT, read_img

sys.path.insert(0, MKT)
import finish  # noqa: E402

FINISH = os.path.join(MKT, 'finish.py')


@pytest.fixture(scope='module')
def chart(blender, tmp_path_factory):
    d = tmp_path_factory.mktemp('chart')
    p = subprocess.run([blender, '-b', '--factory-startup', '-P', os.path.join(HERE, 'blender_colorchart.py'), '--',
                        str(d)], capture_output=True, text=True, timeout=300)
    assert 'COLORCHART_OK' in p.stdout, p.stdout[-2000:] + p.stderr[-2000:]
    return d


def patch_medians(img):
    out = []
    for i in range(24):
        r, c = divmod(i, 6)
        y, x = r * 100 + 50, c * 100 + 50
        out.append(np.median(img[y - 20:y + 20, x - 20:x + 20, :3].reshape(-1, 3), 0))
    return np.asarray(out)


def finish_to(chart, view, look):
    png = os.path.join(str(chart), f'chart_{view}.png')
    subprocess.run([sys.executable, FINISH, 'png', os.path.join(str(chart), 'chart.exr'), png, '--view', view,
                    '--look', look], check=True, capture_output=True)
    return read_img(png, chart)


def test_q6_colorchecker_standard_view(chart):
    got = patch_medians(finish_to(chart, 'Standard', ''))
    ref = np.asarray(finish.COLORCHECKER_SRGB8) / 255.0
    de = finish.delta_e2000(finish.srgb_to_lab(got), finish.srgb_to_lab(ref))
    assert de.mean() <= 2.0 and de.max() <= 4.0, f'dE2000 mean {de.mean():.3f} max {de.max():.3f}'


def test_q6_colorchecker_agx_chain(chart, blender_py):
    got = patch_medians(finish_to(chart, 'AgX', finish.LOOK))
    lin = finish.srgb_to_linear(np.asarray(finish.COLORCHECKER_SRGB8) / 255.0).astype(np.float32)
    npy = os.path.join(str(chart), 'ref_lin.npy')
    np.save(npy, lin[None])
    out = os.path.join(str(chart), 'ref_agx.npy')
    code = (f'import sys,numpy as np; sys.path.insert(0,{MKT!r}); import finish; '
            f'np.save({out!r}, finish.to_display(np.load({npy!r}), "AgX", finish.LOOK))')
    subprocess.run([blender_py, '-I', '-c', code], check=True)
    ref = np.load(out)[0]
    de = finish.delta_e2000(finish.srgb_to_lab(got), finish.srgb_to_lab(ref))
    assert de.mean() <= 2.0 and de.max() <= 4.0, f'dE2000 mean {de.mean():.3f} max {de.max():.3f}'


def test_agx_matches_blender_colour_management(chart):
    png = os.path.join(str(chart), 'ramp_finish.png')
    subprocess.run([sys.executable, FINISH, 'png', os.path.join(str(chart), 'ramp.exr'), png], check=True,
                   capture_output=True)
    ours = read_img(png, chart)[..., :3]
    blend = read_img(os.path.join(str(chart), 'ramp_blender_agx.png'), chart)[..., :3]
    assert ours.shape == blend.shape
    assert np.abs(ours - blend).max() <= 1.0 / 255, np.abs(ours - blend).max() * 255


def test_ciede2000_sharma_pairs():
    pairs = [((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
             ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
             ((50.0, 2.5, 0.0), (50.0, 0.0, -2.5), 4.3065),
             ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
             ((50.0, 2.5, 0.0), (56.0, -27.0, -3.0), 31.9030),
             ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
             ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
             ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381)]
    for a, b, want in pairs:
        assert abs(float(finish.delta_e2000(np.array(a), np.array(b))) - want) < 1e-3, (a, b, want)
