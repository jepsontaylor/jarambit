"""Regressions for the PR #49 review: ingest->worker contract, worker resume identity,
shard-independent frame seeds, and the production flat-lay pose."""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

MKT = Path(__file__).resolve().parents[1]
REPO = MKT.parents[2]
sys.path.insert(0, str(MKT))
sys.path.insert(0, str(REPO))

import farm  # noqa: E402
import plan  # noqa: E402
from conftest import run_worker, smoke_request  # noqa: E402
from ops.render.marketing import ingest as ingest_mod  # noqa: E402

FIXTURES = MKT / "fixtures"


def _ingest(tmp_path, name, register=None, monkeypatch=None):
    if register:
        monkeypatch.setitem(ingest_mod.plan_mod.KNOWN_SOURCES, ingest_mod.sha256(FIXTURES / name), register)
    b = ingest_mod.ingest(FIXTURES / name, tmp_path / "ing")
    mesh = tmp_path / "ing" / "mesh"
    return b, {"bundle": str(mesh / "bundle.json"), "regions": str(mesh / "regions.json")}


@pytest.mark.parametrize("register", [None, {"model": "FIXTURE MODEL", "name": "tiny.obj",
                                             "reference_mass_g": 1.0, "role": "hero"}])
def test_ingest_keeps_regions_document(tmp_path, monkeypatch, register):
    b, paths = _ingest(tmp_path, "tiny.obj", register, monkeypatch)
    regions = json.loads(Path(paths["regions"]).read_text())
    assert regions.get("schema") == "jarambit.render.regions.v1"
    assert "model" not in regions and "reference_mass_g" not in regions
    if register:
        assert b["source"]["model"] == "FIXTURE MODEL"
    else:
        assert "model" not in b["source"]


def test_ingest_to_worker_contract_registered_source(blender, tmp_path, monkeypatch):
    _, paths = _ingest(tmp_path, "tiny_knife.stl", {"model": "FIXTURE MODEL", "name": "tiny_knife.stl",
                                              "reference_mass_g": 1.0, "role": "hero"}, monkeypatch)
    req = smoke_request(paths, str(tmp_path / "out"), n_frames=1)
    p, res = run_worker(blender, req, str(tmp_path / "req.json"))
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    assert res["source"]["model"] == "FIXTURE MODEL"


def test_worker_resume_bound_to_plan_and_profile(blender, tiny_bundle, tmp_path):
    out = str(tmp_path / "out")
    a = smoke_request(tiny_bundle, out, n_frames=1, plan_key="plan-A")
    a["shot"]["frames"][0]["seed"] = 111
    p, ra = run_worker(blender, a, str(tmp_path / "a.json"))
    assert p.returncode == 0, p.stderr[-2000:]
    assert ra["frames"][0]["seed"] == 111  # the request's planned seed is used as-is
    p, ra2 = run_worker(blender, a, str(tmp_path / "a2.json"))
    assert ra2["frames"][0].get("resumed") is True
    b = smoke_request(tiny_bundle, out, n_frames=1, plan_key="plan-B")
    b["shot"]["frames"][0]["seed"] = 222
    b["profile"]["res"] = [320, 180]
    b["profile"]["spp_max"] = 16
    p, rb = run_worker(blender, b, str(tmp_path / "b.json"))
    assert p.returncode == 0, p.stderr[-2000:]
    fr = rb["frames"][0]
    assert not fr.get("resumed")
    assert fr["seed"] == 222 and fr["spp"] == 16 and fr["sha256"] != ra["frames"][0]["sha256"]


def _bundle():
    return {"schema": "jarambit.render.mesh.v1",
            "source": {"path": "fixture.stl", "format": "stl", "sha256": "a" * 64, "units": "mm"},
            "unit_scale_to_m": 0.001, "n_vertices": 8, "n_triangles": 12,
            "bbox_m": [[-0.05, -0.002, -0.02], [0.05, 0.002, 0.02]],
            "normal_policy": "split_crease30_weighted", "npz_sha256": "b" * 64}


def test_frame_seed_independent_of_shard_boundaries():
    resolved = plan.resolve(_bundle(), profiles=("smoke",))
    turn = next(s for s in resolved["shots"] if s["id"] == "turntable")
    planned = {f["index"]: f["seed"] for f in turn["frames"]}
    r1 = farm.build_request(resolved, turn, turn["frames"][0:8], "smoke", "/tmp/o", "b.json", "r.json")
    r2 = farm.build_request(resolved, turn, turn["frames"][4:8], "smoke", "/tmp/o", "b.json", "r.json")
    s1 = {f["index"]: f["seed"] for f in r1["shot"]["frames"]}
    s2 = {f["index"]: f["seed"] for f in r2["shot"]["frames"]}
    assert s1[7] == s2[7] == planned[7]
    assert all(s1[i] == planned[i] for i in s1)


def test_flat_lay_pose_reaches_the_worker_request():
    resolved = plan.resolve(_bundle(), profiles=("smoke",))
    flat = next(s for s in resolved["shots"] if s["id"] == "flat_lay")
    assert flat["pose"] == "lay_flat"
    req = farm.build_request(resolved, flat, flat["frames"], "smoke", "/tmp/o", "b.json", "r.json")
    assert req["shot"]["pose"] == "lay_flat"
    # framing is fit against the posed geometry: an upright XZ blade seen from +Z is edge-on
    pts = plan.bbox_corners(_bundle()["bbox_m"])
    spec = dict(next(s for s in plan.STILLS if s["id"] == "flat_lay"))
    as_is = plan._resolve_still({**spec, "pose": "as_is"}, pts, "k", "smoke", ("smoke",), [0, 0, 0], None)
    assert flat["framing"]["distance_m"] != as_is["framing"]["distance_m"]
    assert np.allclose(np.asarray(plan.POSES["lay_flat"]),
                       np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]]))


def test_pose_changes_plan_key_and_invalidates_completed_output(tmp_path):
    spec = dict(next(s for s in plan.STILLS if s["id"] == "flat_lay"))
    a = plan.resolve(_bundle(), profiles=("smoke",), stills=[{**spec, "pose": "as_is"}], use_external_framing=False)
    b = plan.resolve(_bundle(), profiles=("smoke",), stills=[{**spec, "pose": "lay_flat"}], use_external_framing=False)
    assert a["plan_key"] != b["plan_key"]
    dest = str(tmp_path / "dest")
    jobs = farm.prepare_jobs(a, dest, "b.json", "r.json")
    job = next(j for j in jobs if j["shot_id"] == "flat_lay")
    png = os.path.join(job["out_dir"], "flat_lay_0000.png")
    Path(png).write_bytes(b"x" * 64)
    farm.write_receipt(job["out_dir"], 0, png, "h", "u", 1, 1.0, a["plan_key"])
    assert next(j for j in farm.prepare_jobs(a, dest, "b.json", "r.json") if j["shot_id"] == "flat_lay")["status"] == "skip"
    assert next(j for j in farm.prepare_jobs(b, dest, "b.json", "r.json") if j["shot_id"] == "flat_lay")["status"] == "pending"


def _lookdev_args(bundle, out):
    from types import SimpleNamespace
    return SimpleNamespace(bundle=bundle["bundle"], regions=bundle["regions"], finish_override=None, rig_override=None,
                           accents=None, res=[160, 90], spp=8, spp_min=0, threshold=0.05, device="CPU", hdri="off",
                           out=out)


def test_lookdev_changed_mesh_does_not_resume(blender, tiny_bundle, tmp_path):
    import _stl_bundle
    import lookdev
    shots = json.load(open(MKT / "presets" / "shots_default.json"))
    shot = next(s for s in shots["stills"] if s["id"] == "hero_3q")
    b_dir = tmp_path / "meshB"
    bb, rb = _stl_bundle.build(tiny_bundle["stl"], str(b_dir / "mesh"), pose="upright", units="in")
    mesh_b = {"bundle": bb, "regions": rb}
    out = str(tmp_path / "ld")
    ra = lookdev.build_request(shot, shots["defaults"], _lookdev_args(tiny_bundle, out), "x")
    ra["plan_key"] = lookdev.lookdev_key(ra, "lookdev")
    p, res_a = run_worker(blender, ra, str(tmp_path / "a.json"))
    assert p.returncode == 0, p.stderr[-2000:]
    p, res_a2 = run_worker(blender, ra, str(tmp_path / "a2.json"))
    assert res_a2["frames"][0].get("resumed") is True  # identical inputs still resume
    rb_ = lookdev.build_request(shot, shots["defaults"], _lookdev_args(mesh_b, out), "x")
    rb_["plan_key"] = lookdev.lookdev_key(rb_, "lookdev")
    assert rb_["plan_key"] != ra["plan_key"]
    # even with the same (tag-style) key, the worker receipt identity binds the mesh inputs
    rb_["plan_key"] = ra["plan_key"]
    p, res_b = run_worker(blender, rb_, str(tmp_path / "b.json"))
    assert p.returncode == 0, p.stderr[-2000:]
    assert not res_b["frames"][0].get("resumed")
    assert res_b["frames"][0]["sha256"] != res_a["frames"][0]["sha256"]
