import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ops.render.marketing.ingest import canonical_pose, load_cad, split_normals
from ops.render.marketing import regions

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ROOT = Path(__file__).resolve().parents[4]


def posed(name):
    mesh = load_cad(name)
    R, t = canonical_pose(mesh.V, mesh.F)
    return mesh, mesh.V @ R.T + t


def test_chamfer_iou_and_finish_field():
    mesh, V = posed(FIXTURES / "cube_bevel.step")
    labels, tangent, uv, info = regions.classify(V, mesh.F, mesh.face_id, mesh.surface_types)
    truth = json.loads((FIXTURES / "cube_bevel.expected.json").read_text())["chamfer_face_ids"]
    expected = np.isin(mesh.face_id, truth)
    actual = labels == 1
    _, areas, _ = regions.triangle_geometry(V, mesh.F)
    iou = areas[expected & actual].sum() / areas[expected | actual].sum()
    assert iou >= 0.95
    assert info["method"] == "brep"
    # Each chamfer is a trapezoid: average perimeter lengths are 59 and 39 mm.
    assert info["area_mm2"]["bevel"] == pytest.approx(2 * (2 * 59 + 2 * 39) * np.sqrt(2))
    assert uv.shape == (len(mesh.F), 3, 2)
    normals, _, _ = regions.triangle_geometry(V, mesh.F)
    assert np.allclose(np.einsum("ij,ij->i", tangent, normals), 0, atol=1e-6)


def test_tag_priority_and_unknown_rejected():
    mesh, V = posed(FIXTURES / "cube_bevel.step")
    tags = {str(fid): "ring" for fid in set(mesh.face_id.tolist())}
    labels, _, _, info = regions.classify(V, mesh.F, mesh.face_id, mesh.surface_types, tags)
    assert np.all(labels == 4)
    assert info["method"] == "tags"
    with pytest.raises(ValueError, match="unknown"):
        regions.classify(V, mesh.F, mesh.face_id, tags={"9999": "bevel"})
    with pytest.raises(ValueError, match="unknown"):
        regions.classify(V, mesh.F, mesh.face_id, tags={"0": "other"})


def test_legacy_fixture_labels_deterministic_and_grind_coverage():
    mesh, V = posed(ROOT / "evidence/wave27/g3_tip+00_t60_tt3.stl")
    before = V.copy()
    result = regions.classify(V, mesh.F)
    again = regions.classify(V, mesh.F)
    labels, tangent, uv, info = result
    assert np.array_equal(V, before)
    for a, b in zip(result[:3], again[:3]):
        assert np.array_equal(a, b)
    assert info == again[3]
    assert info["labels_sha256"] == hashlib.sha256(labels.tobytes()).hexdigest()
    assert info["area_mm2"]["ring"] > 400
    assert info["diagnostics"]["ring_center_m"][0] < 0
    # The real source has five holes. Do not silently repair it to the plan's
    # genus-one assumption or hide its topology in the receipt.
    assert info["diagnostics"]["euler_characteristic"] == -8
    assert info["diagnostics"]["projected_loops"] == 6
    assert not info["diagnostics"]["genus_one_assumption_met"]
    law = json.loads((ROOT / "evidence/wave27/g3_tip+00_t60_tt3_grind_law.json").read_text())
    reference = 0
    for edge in law["edges"]:
        s = np.asarray(edge["samples"])
        ds = np.linalg.norm(np.diff(s[:, :2], axis=0), axis=1)
        width = (s[:-1, 4] + s[1:, 4]) / 2
        reference += 2 * np.sum(ds * width) / np.cos(np.radians(edge["half_angle_deg"]))
    actual = sum(info["area_mm2"][name] for name in ("bevel", "edge_apex", "serration"))
    assert abs(actual / reference - 1) <= 0.15
    normals, _, _ = regions.triangle_geometry(V, mesh.F)
    assert np.allclose(np.linalg.norm(tangent, axis=1), 1, atol=1e-6)
    assert np.allclose(np.einsum("ij,ij->i", normals, tangent), 0, atol=1e-6)


def test_topology_seam_weld_never_moves_vertices():
    V = np.array([[0, 0, 0], [.01, 0, 0], [0, .01, 0],
                  [0, 0, 1e-9], [0, .01, 1e-9], [-.01, 0, 0]])
    F = np.array([[0, 1, 2], [3, 4, 5]])
    original = V.copy()
    analysis = regions.topology(V, F)
    assert np.array_equal(V, original)
    assert len(analysis["V"]) == 4
    assert len(analysis["pairs"]) == 1
    N = split_normals(V, F, analysis)
    assert N.shape == (2, 3, 3)
    assert np.array_equal(V, original)


def test_crease_preserves_cube_normals():
    mesh = load_cad(FIXTURES / "tiny.obj")
    normal, _, _ = regions.triangle_geometry(mesh.V, mesh.F)
    N = split_normals(mesh.V, mesh.F, regions.topology(mesh.V, mesh.F))
    assert np.allclose(N, normal[:, None], atol=1e-6)


def test_serration_fft_requires_periodic_curvature():
    n = 512
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    smooth = np.column_stack([np.cos(theta), np.sin(theta)]) * .03
    serrated = smooth * (1 + .03 * np.cos(theta * 24))[:, None]
    assert not regions._serration_segments(smooth)[0]
    segments, metrics = regions._serration_segments(serrated)
    assert segments
    assert metrics["fft_cycles"] == 24


def test_outline_distance_uses_segments():
    poly = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    distance, nearest, _ = regions.outline_distance(np.array([[5, 1], [11, 5]]), poly)
    assert np.array_equal(distance, [1, 1])
    assert np.array_equal(nearest, [[5, 0], [10, 5]])
