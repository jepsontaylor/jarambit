"""Public ingest regressions for rigid poses of the pinned C.10a STEP."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ops.render.marketing.ingest import main as ingest_main, sha256

ROOT = Path(__file__).resolve().parents[4]
STEP = ROOT / "designs/switchback/C10a/cad/switchback_revC10a_ground.step"
NOTES = Path(__file__).resolve().parents[1] / "notes"


def load_bundle(directory):
    with np.load(directory / "mesh/mesh.npz", allow_pickle=False) as archive:
        mesh = {key: archive[key] for key in archive.files}
    bundle = json.loads((directory / "mesh/bundle.json").read_text())
    regions = json.loads((directory / "mesh/regions.json").read_text())
    return mesh, bundle, regions


@pytest.fixture(scope="module")
def canonical_bundle(tmp_path_factory):
    published = json.loads((NOTES / "C10A_validation.json").read_text())
    assert STEP.is_file(), "required pinned STEP missing"
    assert sha256(STEP) == published["source"]["sha256"]
    out = tmp_path_factory.mktemp("canonical-c10a")
    ingest_main([str(STEP), "--out", str(out), "--validated-brep"])
    mesh, bundle, regions = load_bundle(out)
    assert bundle["npz_sha256"] == published["outputs"]["mesh.npz"]
    assert hashlib.sha256(mesh["region_id"].tobytes()).hexdigest() == published["labels_sha256"]
    for name in ("bevel", "edge_apex", "serration", "ring"):
        assert regions["area_mm2"][name] > 0
    return mesh, bundle, regions


@pytest.mark.parametrize("pose_name", ["identity", "rotZ180", "rotZ90", "arbitrary"])
def test_ingest_rigid_pose_preserves_published_regions(canonical_bundle, tmp_path, pose_name):
    canonical, baseline, baseline_regions = canonical_bundle
    base_R, base_t = np.asarray(baseline["pose"]["R"]), np.asarray(baseline["pose"]["t"])
    translation = np.zeros(3)
    if pose_name == "identity":
        R, t = np.eye(3), np.zeros(3)
    else:
        if pose_name == "rotZ180":
            Q = np.diag([-1, -1, 1])
        elif pose_name == "rotZ90":
            Q = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
        else:
            # Proper rotation about an oblique axis, plus a nonzero translation.
            axis = np.array([1, 2, 3], dtype=float) / np.sqrt(14)
            x, y, z = axis
            cross = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
            angle = np.radians(73)
            Q = np.eye(3) * np.cos(angle) + (1 - np.cos(angle)) * np.outer(axis, axis) + np.sin(angle) * cross
            translation = np.array([.127, -.081, .044])
        R, t = Q @ base_R, Q @ base_t + translation
    pose_path = tmp_path / "pose.json"
    pose_path.write_text(json.dumps({"R": R.tolist(), "t": t.tolist()}))
    out = tmp_path / "posed"
    ingest_main([str(STEP), "--out", str(out), "--validated-brep", "--pose", str(pose_path)])
    actual, bundle, info = load_bundle(out)
    assert np.array_equal(actual["region_id"], canonical["region_id"])
    assert info["labels_sha256"] == baseline_regions["labels_sha256"]
    for name, area in baseline_regions["area_mm2"].items():
        assert info["area_mm2"][name] == pytest.approx(area, rel=1e-12, abs=1e-8)
    # Pose overrides still transform the geometry and analytic shading normals.
    source_V = (canonical["V"] - base_t) @ base_R
    assert np.allclose(actual["V"], source_V @ R.T + t, atol=1e-14, rtol=0)
    assert np.array_equal(actual["F"], canonical["F"])
    assert np.array_equal(actual["face_id"], canonical["face_id"])
    assert np.allclose(actual["N_corner"], canonical["N_corner"] @ base_R @ R.T, atol=2e-7, rtol=0)
    assert bundle["pose"] == {"R": R.tolist(), "t": t.tolist()}
