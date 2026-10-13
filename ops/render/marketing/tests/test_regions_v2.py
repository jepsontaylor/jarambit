import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ops.render.marketing.ingest import load_cad
from ops.render.marketing import regions
from ops.render.marketing.region_io import apply_region_overrides
from ops.render.marketing.notes.validate_regions_v2 import patch_iou

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_brep_chamfer_iou_with_analytic_descriptors():
    mesh = load_cad(FIXTURES / "cube_bevel.step", validated_brep=True)
    faces = regions.read_brep_faces(FIXTURES / "cube_bevel.step")
    labels, _, _, info = regions.classify_brep(mesh.V, mesh.F, mesh.face_id, faces, mesh.N_corner)
    truth_ids = json.loads((FIXTURES / "cube_bevel.expected.json").read_text())["chamfer_face_ids"]
    truth = np.isin(mesh.face_id, truth_ids)
    _, area, _ = regions.triangle_geometry(mesh.V, mesh.F)
    assert area[truth & (labels == 1)].sum() / area[truth | (labels == 1)].sum() >= .95
    assert info["revision"] == 2


def test_brep_finite_edge_land_iou():
    # Extruded six-sided cross-section: broad plate, two grinds, 0.5 mm
    # vertical edge land. Face IDs are a construction oracle, not classifier output.
    yz = np.array([[0, .002], [.01, .002], [.015, .00025], [.015, -.00025], [.01, -.002], [0, -.002]])
    V = np.array([[x, y, z] for x in (-.02, .02) for y, z in yz])
    triangles, ids = [], []
    for i in range(6):
        j = (i + 1) % 6
        triangles.extend([[i, i + 6, j + 6], [i, j + 6, j]])
        ids.extend([i, i])
    F, face_id = np.asarray(triangles), np.asarray(ids)
    normal, _, _ = regions.triangle_geometry(V, F)
    faces = {i: {"type": "plane", "axis": normal[2 * i].tolist(), "origin_m": V[F[2 * i, 0]].tolist()} for i in range(6)}
    labels, _, _, _ = regions.classify_brep(V, F, face_id, faces)
    oracle = {"patches": {"bevel": {"label": 1, "face_ids": [1, 3]}, "apex": {"label": 2, "face_ids": [2]},
                            "body": {"label": 0, "face_ids": [0, 4]}}}
    scores = patch_iou(V, F, face_id, labels, oracle)
    assert min(scores.values()) >= .95


def test_brep_ring_ridge_is_not_bevel():
    # An analytic torus patch on the bore axis has a 45-degree slope, the
    # counterexample to treating every oblique triangle as a blade grind.
    V = np.array([[.01, 0, -.002], [.01, .001, -.002], [.01, 0, .002],
                  [.014, 0, .002], [.014, .001, .002], [.0145, 0, .0025],
                  [.04, 0, .002], [.06, 0, .002], [.04, .01, .002]])
    F = np.array([[0, 1, 2], [3, 4, 5], [6, 7, 8]])
    face_id = np.array([0, 1, 2])
    faces = {0: {"type": "cylinder", "axis": [0, 0, 1], "origin_m": [0, 0, 0], "radius_m": .01, "u_span_rad": 2 * np.pi},
             1: {"type": "torus", "axis": [0, 0, 1], "origin_m": [0, 0, .002], "major_radius_m": .014, "minor_radius_m": .0005, "u_span_rad": 2 * np.pi},
             2: {"type": "plane", "axis": [0, 0, 1], "origin_m": [0, 0, .002]}}
    normal, _, _ = regions.triangle_geometry(V, F)
    N = np.repeat(normal[:, None], 3, axis=1)
    N[0] = [-1, 0, 0]  # concave analytic cylinder, inward-facing bore
    labels, _, _, _ = regions.classify_brep(V, F, face_id, faces, N)
    oracle = {"patches": {"ring": {"label": 4, "face_ids": [0, 1]}, "body": {"label": 0, "face_ids": [2]}}}
    assert min(patch_iou(V, F, face_id, labels, oracle).values()) >= .95
    # Exporter tags have final precedence even on analytic ring details.
    tagged, _, _, _ = regions.classify_brep(V, F, face_id, faces, N, tags={"1": "body"})
    assert tagged[1] == 0


def override_files(tmp_path):
    mesh = {"V": np.eye(3), "F": np.array([[0, 1, 2]]), "region_id": np.array([0], np.uint8),
            "tangent": np.array([[1, 0, 0]], np.float32)}
    labels = np.array([4], np.uint8)
    np.save(tmp_path / "region_id.npy", labels)
    record = {"base_npz_sha256": "base", "labels_sha256": hashlib.sha256(labels.tobytes()).hexdigest(),
              "attribute_overrides": {"region_id": {"path": "region_id.npy", "sha256": hashlib.sha256((tmp_path / "region_id.npy").read_bytes()).hexdigest()}}}
    (tmp_path / "regions.json").write_text(json.dumps(record))
    return mesh, record


def test_override_changes_only_appearance_and_preserves_input(tmp_path):
    mesh, _ = override_files(tmp_path)
    result = apply_region_overrides(mesh, tmp_path / "regions.json", "base")
    assert result["region_id"].tolist() == [4]
    assert mesh["region_id"].tolist() == [0]
    assert result["V"] is mesh["V"] and result["F"] is mesh["F"]
    with pytest.raises(ValueError, match="different mesh"):
        apply_region_overrides(mesh, tmp_path / "regions.json", "other")
    (tmp_path / "region_id.npy").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="sha256"):
        apply_region_overrides(mesh, tmp_path / "regions.json", "base")


@pytest.mark.parametrize("name,value", [("region_id", np.array([4, 4], np.uint8)), ("region_id", np.array([4], np.int32)),
                                       ("region_id", np.array([7], np.uint8)), ("V", np.eye(3))])
def test_override_rejects_invalid_arrays_and_geometry_edits(name, value, tmp_path):
    mesh, record = override_files(tmp_path)
    target = tmp_path / (name + ".npy")
    np.save(target, value)
    record["attribute_overrides"] = {name: {"path": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}}
    (tmp_path / "regions.json").write_text(json.dumps(record))
    with pytest.raises(ValueError):
        apply_region_overrides(mesh, tmp_path / "regions.json", "base")


def test_override_rejects_path_escape(tmp_path):
    mesh, record = override_files(tmp_path)
    record["attribute_overrides"]["region_id"]["path"] = "../elsewhere.npy"
    (tmp_path / "regions.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="sibling"):
        apply_region_overrides(mesh, tmp_path / "regions.json", "base")


def test_regions_v2_rejects_production_target_before_writes(tmp_path):
    base = tmp_path / "mesh"
    base.mkdir()
    marker = base / "bundle.json"
    marker.write_text("unchanged")
    with pytest.raises(ValueError, match="new directory"):
        regions.write_regions_v2(marker, base)
    assert marker.read_text() == "unchanged"
