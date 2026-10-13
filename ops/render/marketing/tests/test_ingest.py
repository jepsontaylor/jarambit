import json
import os
import importlib.util
from pathlib import Path
import struct

import numpy as np
import pytest
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir
from OCP.gp import gp_Ax2

from ops.render.marketing.ingest import HERO_NAME, HERO_SHA256, HERO_STL_NAME, HERO_STL_SHA256, LEGACY_FIXTURE_SHA256, canonical_pose, ingest, load_cad, sha256
from ops.render.marketing import regions

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize("name,count", [("cube_bevel.step", 28), ("tiny.obj", 12), ("tiny_knife.stl", None)])
def test_bundle_contract_and_determinism(name, count, tmp_path):
    a = ingest(FIXTURES / name, tmp_path / "a")
    b = ingest(FIXTURES / name, tmp_path / "b")
    assert a == b
    assert (tmp_path / "a/mesh/bundle.json").read_bytes() == (tmp_path / "b/mesh/bundle.json").read_bytes()
    assert (tmp_path / "a/mesh/mesh.npz").read_bytes() == (tmp_path / "b/mesh/mesh.npz").read_bytes()
    assert a["schema"] == "jarambit.render.mesh.v1"
    assert a["source"]["sha256"] == sha256(FIXTURES / name)
    assert a["npz_sha256"] == sha256(tmp_path / "a/mesh/mesh.npz")
    with np.load(tmp_path / "a/mesh/mesh.npz", allow_pickle=False) as z:
        n, m = a["n_vertices"], a["n_triangles"]
        if count is not None:
            assert m == count
        for key, dtype, shape in [("V", "float64", (n, 3)), ("F", "int32", (m, 3)),
                                  ("N_corner", "float32", (m, 3, 3)), ("face_id", "int32", (m,)),
                                  ("region_id", "uint8", (m,)), ("tangent", "float32", (m, 3)),
                                  ("uv", "float32", (m, 3, 2))]:
            assert z[key].dtype == np.dtype(dtype)
            assert z[key].shape == shape
            assert np.isfinite(z[key]).all()
        assert np.allclose(np.linalg.norm(z["N_corner"], axis=2), 1, atol=1e-6)
        assert np.allclose(np.linalg.norm(z["tangent"], axis=1), 1, atol=1e-6)
        R, t = np.asarray(a["pose"]["R"]), np.asarray(a["pose"]["t"])
        original = load_cad(FIXTURES / name)
        assert np.allclose((z["V"] - t) @ R, original.V, atol=1e-15)


def test_pipeline_peer_loader_import(monkeypatch):
    path = Path(__file__).parents[1] / "ingest.py"
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location("marketing_ingest", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.HERO_SHA256 == HERO_SHA256
    assert callable(module.main)


def test_step_analytic_normals_and_units():
    mesh = load_cad(FIXTURES / "cube_bevel.step", validated_brep=True)
    assert mesh.source_units == "mm"
    assert np.allclose(np.ptp(mesh.V, axis=0), [.06, .04, .006])
    normals, _, _ = regions.triangle_geometry(mesh.V, mesh.F)
    assert np.allclose(mesh.N_corner, normals[:, None], atol=1e-12)
    assert set(mesh.surface_types) == {"plane"}
    with pytest.raises(ValueError, match="header"):
        load_cad(FIXTURES / "cube_bevel.step", units="m")


def test_curved_step_bore_and_analytic_normals(tmp_path):
    box = BRepPrimAPI_MakeBox(60, 40, 6).Shape()
    bore = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(15, 20, 0), gp_Dir(0, 0, 1)), 8, 6).Shape()
    shape = BRepAlgoAPI_Cut(box, bore).Shape()
    path = tmp_path / "bore.step"
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    assert writer.Write(str(path)) == IFSelect_RetDone
    mesh = load_cad(path, validated_brep=True)
    assert "cylinder" in mesh.surface_types
    normal, _, _ = regions.triangle_geometry(mesh.V, mesh.F)
    # Corner normals lie on the analytic cylinder, with the correct inward
    # bore orientation, rather than matching a flat tessellation face.
    curved = mesh.surface_types == "cylinder"
    radial = mesh.V[mesh.F[curved]] - [.015, .02, 0]
    radial[:, :, 2] = 0
    radial /= np.linalg.norm(radial, axis=2)[:, :, None]
    assert np.allclose(mesh.N_corner[curved], -radial, atol=1e-8)
    assert not np.allclose(mesh.N_corner[curved], normal[curved, None])
    R, t = canonical_pose(mesh.V, mesh.F)
    labels, _, _, info = regions.classify(mesh.V @ R.T + t, mesh.F, mesh.face_id, mesh.surface_types)
    assert np.any(labels == 4)
    assert info["diagnostics"]["genus_one_assumption_met"]


def test_step_header_metres_are_converted(tmp_path):
    step = (FIXTURES / "cube_bevel.step").read_text()
    # Change all header length units to metres without changing numeric geometry.
    assert "SI_UNIT(.MILLI.,.METRE.)" in step
    path = tmp_path / "metres.stp"
    path.write_text(step.replace("SI_UNIT(.MILLI.,.METRE.)", "SI_UNIT($,.METRE.)"))
    mesh = load_cad(path)
    assert mesh.source_units == "m"
    assert mesh.unit_scale_to_m == 1.0
    assert np.allclose(np.ptp(mesh.V, axis=0), [60, 40, 6])


def test_validated_brep_rejects_open_shell_and_mesh(tmp_path):
    face = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 0, 2, 0, 2).Face()
    writer = STEPControl_Writer()
    writer.Transfer(face, STEPControl_AsIs)
    path = tmp_path / "open.step"
    assert writer.Write(str(path)) == IFSelect_RetDone
    with pytest.raises(ValueError, match="valid closed B-rep"):
        load_cad(path, validated_brep=True)
    with pytest.raises(ValueError, match="no mesh fallback"):
        load_cad(FIXTURES / "tiny.obj", validated_brep=True)


def test_mesh_units():
    mm = load_cad(FIXTURES / "tiny.obj")
    inches = load_cad(FIXTURES / "tiny.obj", units="in")
    assert np.allclose(inches.V, mm.V * 25.4)


def test_binary_stl_solid_header(tmp_path):
    dtype = np.dtype([("normal", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attribute", "<u2")])
    data = np.zeros(1, dtype=dtype)
    data["normal"] = [0, 0, 1]
    data["v"] = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    path = tmp_path / "solid_header.stl"
    path.write_bytes(b"solid is a legal binary header".ljust(80, b" ") + struct.pack("<I", 1) + data.tobytes())
    mesh = load_cad(path)
    assert np.array_equal(mesh.V, data["v"].astype(np.float64).reshape(-1, 3) * 0.001)
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises((ValueError, UnicodeError)):
        load_cad(path)


@pytest.mark.parametrize("content", ["solid bad\nendsolid bad\n", "solid x\nfacet normal 0 0 1\n",
    "solid x\nfacet normal 0 0 nan\n", "solid x\nfacet normal 0 0 1\nouter loop\nvertex nan 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid x\n",
    "solid x\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nvertex 0 0 1\nendloop\nendfacet\nendsolid x\n"])
def test_malformed_ascii_stl(content, tmp_path):
    path = tmp_path / "bad.stl"
    path.write_text(content)
    with pytest.raises(ValueError):
        load_cad(path)


@pytest.mark.parametrize("content", ["v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n",
    "v nan 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", "v 0 0 0\nf 0 1 1\n",
    "v 0 0 0\nv 0 0 0\nv 0 0 0\nf 1 2 3\n"])
def test_malformed_obj(content, tmp_path):
    path = tmp_path / "bad.obj"
    path.write_text(content)
    with pytest.raises((ValueError, IndexError)):
        load_cad(path)


def test_ply_and_negative_obj_indices(tmp_path):
    path = tmp_path / "tiny.ply"
    path.write_text("ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nelement face 1\nproperty list uchar int vertex_indices\nend_header\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n")
    mesh = load_cad(path)
    assert len(mesh.F) == 1
    obj = tmp_path / "negative.obj"
    obj.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n")
    assert np.array_equal(load_cad(obj).F, mesh.F)
    path.write_text(path.read_text().replace("element face 1", "element face 999999999"))
    with pytest.raises(ValueError, match="limit"):
        load_cad(path)


def test_concave_obj_preserves_polygon_area_and_face_id(tmp_path):
    path = tmp_path / "concave.obj"
    path.write_text("v 0 0 0\nv 3 0 0\nv 3 3 0\nv 2 1 0\nv 0 3 0\nf 1 2 3 4 5\n")
    mesh = load_cad(path)
    _, area, _ = regions.triangle_geometry(mesh.V, mesh.F)
    assert len(mesh.F) == 3
    assert np.sum(area) == pytest.approx(6e-6)
    assert np.array_equal(mesh.face_id, [0, 0, 0])
    assert np.array_equal(mesh.V, np.array([[0, 0, 0], [3, 0, 0], [3, 3, 0], [2, 1, 0], [0, 3, 0]]) * .001)


def test_limits_and_hash(tmp_path):
    with pytest.raises(ValueError, match="limit|bounds"):
        load_cad(FIXTURES / "tiny_knife.stl", max_triangles=1)
    with pytest.raises(ValueError, match="byte limit"):
        load_cad(FIXTURES / "tiny.obj", max_file_bytes=1)
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_cad(FIXTURES / "tiny.obj", expected_sha256="0" * 64)
    for name in (HERO_NAME, HERO_STL_NAME):
        renamed = tmp_path / name
        renamed.write_bytes((FIXTURES / "tiny_knife.stl").read_bytes())
        with pytest.raises(ValueError, match="sha256 mismatch"):
            load_cad(renamed)
        with pytest.raises(ValueError, match="owner-pinned"):
            load_cad(renamed, expected_sha256=sha256(renamed))
    from ops.render.marketing import plan as plan_mod
    assert HERO_SHA256 == plan_mod.HERO_STEP_SHA256 and HERO_STL_SHA256 == plan_mod.HERO_STL_SHA256
    assert HERO_NAME == os.path.basename(plan_mod.HERO_STEP_PATH)
    # every registry file name is pinned to its hash, incl. the previous C.9.2 RC
    for sha, info in plan_mod.KNOWN_SOURCES.items():
        assert plan_mod.pinned_sha_for_name(info["name"]) == sha
        renamed = tmp_path / info["name"]
        renamed.write_bytes((FIXTURES / "tiny_knife.stl").read_bytes())
        with pytest.raises(ValueError, match="sha256 mismatch"):
            load_cad(renamed)


def test_pose_override_and_tags(tmp_path):
    pose = tmp_path / "pose.json"
    pose.write_text(json.dumps({"R": np.eye(3).tolist(), "t": [1, 2, 3]}))
    tags = tmp_path / "tags.json"
    tags.write_text(json.dumps({"faces": {"0": "bevel"}}))
    result = ingest(FIXTURES / "tiny.obj", tmp_path / "bundle", pose=pose, tags_path=tags)
    with np.load(tmp_path / "bundle/mesh/mesh.npz") as z:
        assert z["region_id"][0] == 1
        assert np.array_equal(z["V"], load_cad(FIXTURES / "tiny.obj").V + [1, 2, 3])
    assert result["source"]["regions_sidecar"]["sha256"] == sha256(tags)
    pose.write_text(json.dumps({"R": (np.eye(3) * 2).tolist(), "t": [0, 0, 0]}))
    with pytest.raises(ValueError, match="rigid"):
        ingest(FIXTURES / "tiny.obj", tmp_path / "bad", pose=pose)


def test_pca_degeneracy_and_source_order():
    V = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], dtype=float)
    F = np.array([[0, 4, 6], [0, 6, 2], [1, 3, 7], [1, 7, 5],
                  [0, 1, 5], [0, 5, 4], [2, 6, 7], [2, 7, 3],
                  [0, 2, 3], [0, 3, 1], [4, 5, 7], [4, 7, 6]])
    a, _ = canonical_pose(V, F)
    b, _ = canonical_pose(V[::-1], 7 - F)
    assert np.allclose(a, [[1, 0, 0], [0, 0, -1], [0, 1, 0]])
    assert np.allclose(a, b)


def test_pca_is_independent_of_surface_tessellation_density():
    mesh = load_cad(FIXTURES / "tiny.obj")
    a = canonical_pose(mesh.V, mesh.F)
    tri = mesh.V[mesh.F[0]]
    V = np.vstack([mesh.V, tri.mean(axis=0)])
    i, j, k = mesh.F[0]
    center = len(V) - 1
    F = np.vstack([mesh.F[1:], [i, j, center], [j, k, center], [k, i, center]])
    b = canonical_pose(V, F)
    assert np.allclose(a[0], b[0], atol=1e-12)
    assert np.allclose(a[1], b[1], atol=1e-12)


def test_legacy_fixture_source_hash_geometry_and_ring_left():
    path = ROOT / "evidence/wave27/g3_tip+00_t60_tt3.stl"
    assert sha256(path) == LEGACY_FIXTURE_SHA256
    mesh = load_cad(path)
    before = mesh.V.copy()
    R, t = canonical_pose(mesh.V, mesh.F)
    posed = mesh.V @ R.T + t
    assert np.array_equal(mesh.V, before)
    assert np.allclose((posed - t) @ R, before, atol=1e-15)
    planar = posed @ regions.plane_frame(posed).T
    normals, _, _ = regions.triangle_geometry(planar, mesh.F)
    ring = regions.ring_loop(regions.projected_loops(planar, mesh.F, normals))
    assert ring[:, 0].mean() < 0
    assert np.var(posed, axis=0).argmin() == 1
