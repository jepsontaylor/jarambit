from pathlib import Path

import numpy as np
import pytest

from ops.render.marketing.framing import camera_basis, fit, project
from ops.render.marketing.ingest import canonical_pose, load_cad

ROOT = Path(__file__).resolve().parents[4]
CAMERA = {"sensor_mm": 36, "focal_mm": 85, "res": [3840, 2160]}


def test_legacy_fixture_safe_area_36_angles():
    mesh = load_cad(ROOT / "evidence/wave27/g3_tip+00_t60_tt3.stl")
    R, t = canonical_pose(mesh.V, mesh.F)
    V = mesh.V @ R.T + t
    frames = [{"az": a, "el": 15, "roll": 0, "target": [0, 0, 0]} for a in np.arange(0, 360, 10)]
    result = fit(V, CAMERA, frames)
    assert result["pass"]
    assert len(result["per_frame_margin_min"]) == 36
    assert result == fit(V, CAMERA, frames)
    for i, frame in enumerate(frames):
        xy, depth = project(V, CAMERA, frame, result["distance_m"])
        assert xy.min() >= 0.06 - 1e-12
        assert xy.max() <= 0.94 + 1e-12
        assert depth.min() > 0.001
        assert depth.max() < 100
        assert xy[:, 0].max() - xy[:, 0].min() == pytest.approx(result["per_frame_width_fill"][i])
    assert 0.62 <= max(result["per_frame_width_fill"]) <= 0.78


def test_single_frame_fill_matches_fov():
    V = np.array([[x, y, z] for x in (-.05, .05) for y in (-.001, .001) for z in (-.01, .01)])
    frame = {"az": 0, "el": 0, "target": [0, 0, 0]}
    result = fit(V, CAMERA, [frame])
    # Nearest face width / (2*distance*tan(hFOV/2)) == 0.70.
    expected = .001 + .1 / (.70 * (36 / 85))
    assert result["distance_m"] == pytest.approx(expected, rel=1e-10)
    assert result["per_frame_width_fill"][0] == pytest.approx(.7)


@pytest.mark.parametrize("roll", [0, 35, 90, 180])
def test_roll_and_offset_target_safe(roll):
    V = np.array([[x, y, z] for x in (-.02, .02) for y in (-.015, .015) for z in (-.015, .015)]) + [1, 2, 3]
    camera = {**CAMERA, "res": [100, 100]}
    frame = {"az": 0, "el": 25, "roll": roll, "target": [1, 2, 3]}
    result = fit(V, camera, [frame])
    xy, depth = project(V, camera, frame, result["distance_m"])
    assert xy.min() >= .06
    assert xy.max() <= .94
    assert depth.min() > .001


def test_planar_vertices_and_pole_camera():
    V = np.array([[-.05, -.01, 0], [.05, -.01, 0], [.05, .01, 0], [-.05, .01, 0]])
    frame = {"az": 0, "el": 90}
    result = fit(V, CAMERA, [frame])
    xy, _ = project(V, CAMERA, frame, result["distance_m"])
    assert np.isfinite(xy).all()
    assert result["pass"]


def test_impossible_aspect_fill_fails():
    V = np.array([[x, 0, z] for x in (-.001, .001) for z in (-.1, .1)])
    with pytest.raises(ValueError, match="incompatible"):
        fit(V, CAMERA, [{"az": 0, "el": 0}])


@pytest.mark.parametrize("camera", [{**CAMERA, "focal_mm": 0}, {**CAMERA, "sensor_mm": float("nan")},
                                     {**CAMERA, "res": [0, 0]}, {**CAMERA, "clip_near_m": 200}])
def test_bad_camera_fails(camera):
    with pytest.raises(ValueError):
        fit(np.eye(3), camera, [{"az": 0, "el": 0}])


def test_bad_vertices_or_trajectory_fail():
    with pytest.raises(ValueError):
        fit(np.array([[float("nan"), 0, 0]]), CAMERA, [])
    with pytest.raises(ValueError):
        fit(np.eye(3), CAMERA, [{"az": 0, "el": 0, "target": [1, 2]}])
    with pytest.raises(ValueError):
        fit(np.eye(3), CAMERA, [{"az": float("inf"), "el": 0}])
    with pytest.raises(ValueError):
        fit(np.eye(3), CAMERA, [], margin=.6)


def test_camera_basis_matches_documented_convention():
    assert np.array_equal(camera_basis(0, 0), [[1, 0, 0], [0, 0, 1], [0, -1, 0]])
    assert np.allclose(camera_basis(90, 0)[2], [1, 0, 0])
    for az, el, roll in [(0, 90, 0), (25, 35, 55), (240, -10, -20)]:
        basis = camera_basis(az, el, roll)
        assert np.allclose(basis @ basis.T, np.eye(3))
        assert np.linalg.det(basis) == pytest.approx(1)
