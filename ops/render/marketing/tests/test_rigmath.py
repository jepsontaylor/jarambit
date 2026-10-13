"""Pure scene math (no Blender): camera convention shared with framing.py, seeds, fallback fit, DoF."""
import numpy as np

import rigmath


def test_camera_convention_matches_codex_framing():
    # az=0 camera on -Y, az=90 camera on +X, el above the XY plane (COORD RENDER-codex 04:38Z)
    assert np.allclose(rigmath.cam_dir(0, 0), [0, -1, 0])
    assert np.allclose(rigmath.cam_dir(90, 0), [1, 0, 0])
    assert np.allclose(rigmath.cam_dir(0, 90), [0, 0, 1], atol=1e-12)


def test_turntable_equivalence():
    """Rotating the part by -az with the camera at az 0 == orbiting the camera to az."""
    rng = np.random.default_rng(0)
    V = rng.normal(size=(50, 3))
    pivot = V.mean(0)
    for az in (0, 35, 123, 270):
        cam, t = rigmath.frame_camera(pivot, pivot, az, 20, 3.0)
        u, v, z = rigmath.project(rigmath.frame_points(V, pivot, az), cam, t, 85, 36, (1920, 1080))
        cam2 = pivot + 3.0 * rigmath.cam_dir(az, 20)
        u2, v2, z2 = rigmath.project(V, cam2, pivot, 85, 36, (1920, 1080))
        assert np.allclose(u, u2) and np.allclose(v, v2) and np.allclose(z, z2)


def test_seed_deterministic_and_distinct():
    a = [rigmath.frame_seed('k', i) for i in range(240)]
    assert a == [rigmath.frame_seed('k', i) for i in range(240)]
    assert len(set(a)) == 240 and all(0 <= s < 2 ** 31 for s in a)
    assert rigmath.frame_seed('k2', 0) != a[0]


def test_fallback_fit_keeps_margin_over_36_angles():
    rng = np.random.default_rng(1)
    V = rng.uniform([-0.1, -0.003, -0.03], [0.1, 0.003, 0.03], size=(4000, 3))
    pivot = (V.min(0) + V.max(0)) / 2
    frames = [{'az': a, 'el': 15, 'target': pivot} for a in np.arange(0, 360, 10)]
    d, rep = rigmath.fit_distance(V, pivot, frames, 85, 36, (3840, 2160))
    assert rep['margin_ok'] and rep['margin_min'] >= 0.06 and rep['fill_max'] <= 0.78 + 1e-9
    for f in frames:
        u0, u1, v0, v1, zmin = rigmath.frame_extent(V, pivot, pivot, f['az'], 15, d, 85, 36, (3840, 2160))
        assert min(u0, 1 - u1, v0, 1 - v1) >= 0.06 - 1e-9 and zmin > 0


def test_auto_fstop_monotone():
    a = rigmath.auto_fstop(0.5, 0.7, 0.6, 85, 36, 1920)
    b = rigmath.auto_fstop(0.5, 0.7, 0.6, 85, 36, 3840)
    c = rigmath.auto_fstop(0.59, 0.61, 0.6, 85, 36, 1920)
    assert 4.0 <= c <= a <= b <= 22.0
