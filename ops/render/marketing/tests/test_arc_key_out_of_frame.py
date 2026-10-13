"""Art direction 2026-10-13: the arc key (and its floor mirror image) never enters a turntable frame.

Pure numpy: re-derives the ARC segment centres the same way blender/lights.arc_segments does and
checks them, plus a strip around each, against every turntable camera for a range of object sizes."""
import json
import math
import os

import numpy as np
import pytest

from conftest import MKT
import rigmath

RIG = json.load(open(os.path.join(MKT, 'presets', 'rig_dark_arc_key.json')))


def arc_points(L, D, n_sub=8):
    a0, a1 = L['az_from'], L['az_to']
    e0, e1 = L['el_side'], L['el_top']
    dist = L['dist_D'] * D
    pts = []
    for s in np.linspace(0, 1, L['segments'] * n_sub + 1):
        c = rigmath.light_position(a0 + (a1 - a0) * s, e0 + (e1 - e0) * math.sin(math.pi * s), dist)
        nrm = -c / np.linalg.norm(c)
        side = np.cross(nrm, [0, 0, 1.0])
        side = side / max(np.linalg.norm(side), 1e-9)
        w = L['width_D'] * D / 2
        pts += [c + w * side, c - w * side, c + w * np.cross(nrm, side), c - w * np.cross(nrm, side)]
    return np.array(pts)


@pytest.mark.parametrize('D', [0.05, 0.23, 0.6])
@pytest.mark.parametrize('el', [5.0, 15.0, 25.0])
def test_arc_key_never_in_frame(D, el):
    L = next(L for L in RIG['lights'] if L['type'] == 'ARC')
    P = arc_points(L, D)
    z_floor = -0.15 * D
    Pm = P.copy(); Pm[:, 2] = 2 * z_floor - Pm[:, 2]
    for focal in (50.0, 85.0):
        dist = D * focal / 36.0 * 1.4  # whole object fills about 70 % of the width
        for az in range(0, 360, 15):
            cam, t = rigmath.frame_camera(np.zeros(3), np.zeros(3), az, el, dist)
            for Q in (P, Pm):
                assert not rigmath.points_in_frame(Q, cam, t, focal, 36.0, (1920, 1080)).any()
