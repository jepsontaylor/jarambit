"""Regression tests for the six PR #45 review findings."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import canon  # noqa: E402
import encode  # noqa: E402
import farm  # noqa: E402
import pipeline  # noqa: E402
import qa  # noqa: E402


def _npz(path, tri=((0, 0, 0), (1, 0, 0), (0, 1, 0))):
    np.savez(path, vertices=np.asarray(tri, float), faces=np.asarray([[0, 1, 2]]))
    return canon.sha256_file(str(path))


def _bundle(tmp_path, sha, npz=None, name="b.json", sub="bundle"):
    d = tmp_path / sub
    d.mkdir(exist_ok=True)
    real = _npz(d / "mesh.npz")
    doc = {"schema": 1, "source": {"sha256": sha}, "bbox_m": [[0, 0, 0], [1, 1, 1]], "normal_policy": "x",
           "unit_scale_to_m": 0.001, "n_vertices": 3, "n_triangles": 1}
    doc["npz_sha256"] = real if npz is None else npz
    if npz == "":
        del doc["npz_sha256"]
    p = d / name
    p.write_text(json.dumps(doc))
    return str(p), real


# 1: supplied bundle, mesh.npz and regions must match the plan
def test_bundle_mismatch_rejected(tmp_path):
    b, real = _bundle(tmp_path, "a" * 64)
    plan = {"bundle": {"source_sha256": "a" * 64, "npz_sha256": real}, "regions_sha256": "missing"}
    assert pipeline.bundle_mismatch(plan, b, None) is None
    g3, _ = _bundle(tmp_path, "b" * 64, sub="g3")
    assert "source_sha256" in pipeline.bundle_mismatch(plan, g3, None)
    assert "not found" in pipeline.bundle_mismatch(plan, str(tmp_path / "nope.json"), None)


def test_npz_digest_required_and_file_hashed(tmp_path):
    b, real = _bundle(tmp_path, "a" * 64)
    plan = {"bundle": {"source_sha256": "a" * 64, "npz_sha256": real}, "regions_sha256": "missing"}
    # mutated mesh.npz behind an unchanged bundle.json
    _npz(Path(b).parent / "mesh.npz", tri=((0, 0, 0), (2, 0, 0), (0, 2, 0)))
    assert "mesh npz sha256" in pipeline.bundle_mismatch(plan, b, None)
    # missing mesh.npz
    os.remove(Path(b).parent / "mesh.npz")
    assert "mesh npz missing" in pipeline.bundle_mismatch(plan, b, None)
    # no NPZ digest in the bundle or the plan
    nb, _ = _bundle(tmp_path, "a" * 64, npz="", sub="nodigest")
    assert "non-empty npz_sha256" in pipeline.bundle_mismatch(
        {"bundle": {"source_sha256": "a" * 64, "npz_sha256": None}, "regions_sha256": "missing"}, nb, None)


def test_regions_mismatch_rejected(tmp_path):
    r = tmp_path / "regions.json"
    r.write_text("{}")
    good = canon.sha256_file(str(r))
    b, real = _bundle(tmp_path, "a" * 64)
    plan = {"bundle": {"source_sha256": "a" * 64, "npz_sha256": real}, "regions_sha256": good}
    assert pipeline.bundle_mismatch(plan, b, str(r)) is None
    assert "no regions" in pipeline.bundle_mismatch(plan, b, None)
    r.write_text('{"x":1}')
    assert "regions sha256" in pipeline.bundle_mismatch(plan, b, str(r))


# 2: resume records are bound to the plan
def test_old_plan_receipt_not_resumed(tmp_path):
    out = str(tmp_path / "shots" / "turntable" / "final_4k")
    os.makedirs(out)
    farm.claim_out_dir(out, "old")
    png = os.path.join(out, "turntable_0000.png")
    Path(png).write_bytes(b"png")
    farm.write_receipt(out, 0, png, "h", "u", 1, 1.0, "old")
    assert farm.frame_done(out, 0, "turntable", "old")
    assert not farm.frame_done(out, 0, "turntable", "new")
    farm.claim_out_dir(out, "new")
    assert not farm.frame_done(out, 0, "turntable", "new")
    assert os.path.isdir(os.path.join(out, "stale_old"))
    assert not os.path.exists(png)  # old artifact archived with its records
    old_png = os.path.join(out, "stale_old", "turntable_0000.png")
    marker = os.path.join(out, "turntable_0000.png.done.json")
    Path(marker).write_text(json.dumps({"png": old_png, "png_sha256": canon.sha256_file(old_png), "plan_key": "old"}))
    assert not farm.frame_done(out, 0, "turntable", "new")


def test_plan_change_archives_old_pngs_finish_mark_resume(tmp_path):
    out = str(tmp_path / "out")
    os.makedirs(out)
    farm.claim_out_dir(out, "old")
    Path(out, "turntable_0000.png").write_bytes(b"OLD" * 20)
    assert farm._mark_pngs(out, "turntable", [0])
    assert farm.frame_done(out, 0, "turntable", "old")
    farm.claim_out_dir(out, "new")
    assert not os.path.exists(os.path.join(out, "turntable_0000.png"))
    Path(out, "turntable_0000.denoised.exr").write_bytes(b"EXR")
    fin = tmp_path / "fin.py"
    fin.write_text("import sys,shutil; open(sys.argv[3],'wb').write(b'NEW'*20)\n")
    ok, err = farm._finish_remote_pngs(None, out, "turntable", [0], str(fin))
    assert ok, err
    assert Path(out, "turntable_0000.png").read_bytes() == b"NEW" * 20
    assert farm._mark_pngs(out, "turntable", [0])
    assert farm.frame_done(out, 0, "turntable", "new")
    assert json.loads(Path(out, "turntable_0000.png.done.json").read_text())["plan_key"] == "new"


def test_frame_identity_checked_in_all_formats(tmp_path):
    out = str(tmp_path / "out")
    os.makedirs(out)
    farm.claim_out_dir(out, "k")
    png1 = Path(out, "turntable_0001.png"); png1.write_bytes(b"P1" * 20)
    Path(out, "turntable_0000.png.done.json").write_text(json.dumps(
        {"png": str(png1), "png_sha256": canon.sha256_file(str(png1)), "index": 1}))
    assert not farm.frame_done(out, 0, "turntable", "k")
    os.remove(os.path.join(out, "turntable_0000.png.done.json"))
    exr = Path(out, "turntable_0001.denoised.exr"); exr.write_bytes(b"E1")
    Path(out, "turntable_0000.receipt.json").write_text(json.dumps(
        {"frame": {"index": 1}, "files": {"denoised": [str(exr), canon.sha256_file(str(exr))]}}))
    assert not farm.frame_done(out, 0, "turntable", "k")
    Path(out, "turntable_0000.receipt.json").write_text(json.dumps(
        {"frame": {"index": 0}, "files": {"denoised": [str(exr), canon.sha256_file(str(exr))]}}))
    assert farm.frame_done(out, 0, "turntable", "k")


# 3: render --execute launches one shard per host, the rest are queued
def test_execute_launches_one_shard_per_host(tmp_path, monkeypatch):
    jobs = [{"shot_id": "turntable", "profile": "final_4k", "shard": i, "frames": [i], "status": "pending",
             "request_path": str(tmp_path / f"r{i}.json"), "out_dir": str(tmp_path), "host": None}
            for i in range(30)]
    for j in jobs:
        Path(j["request_path"]).write_text("{}")
    launched = []
    monkeypatch.setattr(farm, "prepare_jobs", lambda *a, **k: jobs)
    monkeypatch.setattr(farm, "probe_host_gpu", lambda h: {"name": h["name"], "reachable": True, "yield": False,
                                                          "ssh": None, "gpu_uuid": None})
    monkeypatch.setattr(farm, "remote_disk_ok", lambda *a: True)
    monkeypatch.setattr(farm, "launch_shell", lambda argv, log, ssh_host=None: launched.append(argv) or 1)
    w = tmp_path / "worker.py"; w.write_text("")
    b = tmp_path / "blender"; b.write_text("")
    s = farm.render_jobs({"plan_key": "k"}, str(tmp_path), "", "", str(b), str(w),
                         hosts=[{"name": "h1", "ssh": None}], execute=True)
    assert len(launched) == 1 and s["launched"] == 1 and s["queued"] == 29


# 4: Q12 needs the rerun image pair
def test_q12_unverified_without_images():
    r = qa.check_q12(b"same", b"same")
    assert r["status"] == "FAIL"
    a = np.zeros((4, 4)); b = np.zeros((4, 5))
    assert qa.check_q12(b"same", b"same", a, b)["status"] == "FAIL"
    assert qa.check_q12(b"same", b"same", a, a)["status"] == "PASS"


# 5: Q7 normalises by body luminance
def test_q7_zero_mean_residual():
    rng = np.random.default_rng(0)
    body = np.full((64, 64), 0.5)
    res = rng.choice([-0.001, 0.001], size=(64, 64))
    r = qa.check_q7(res, body, body, body_mean=0.5)
    assert r["status"] == "PASS"
    assert abs(r["measured"]["residual_std_over_body"] - 0.002) < 1e-4
    assert qa.check_q7(res * 10, body, body, body_mean=0.5)["status"] == "FAIL"


# 6: GIF concat with a relative frames dir
@pytest.mark.skipif(not encode.FFMPEG or subprocess.run(["which", encode.FFMPEG], capture_output=True).returncode,
                    reason="ffmpeg required")
def test_gif_relative_frames_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("gifframes")
    for i in range(3):
        subprocess.run([encode.FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "color=c=gray:s=16x16", "-frames:v", "1", f"gifframes/f{i}.png"], check=True)
    out = str(tmp_path / "o.gif")
    encode._gif_from_files([f"f{i}.png" for i in range(3)], "gifframes", out, 16, 16, 10)
    assert os.path.getsize(out) > 0


def test_no_npz_override_render_verifies_adjacent_mesh(tmp_path):
    import inspect
    assert "npz_path" not in inspect.signature(pipeline.bundle_mismatch).parameters
    parser_src = inspect.getsource(pipeline)
    render_block = parser_src[parser_src.index('sub.add_parser("render")'):parser_src.index('render.set_defaults')]
    assert "--npz" not in render_block
    b, real = _bundle(tmp_path, "a" * 64)
    plan = {"bundle": {"source_sha256": "a" * 64, "npz_sha256": real}, "regions_sha256": "missing"}
    # a verified copy elsewhere does not help: the adjacent file the worker loads is what counts
    Path(tmp_path, "verified.npz").write_bytes(Path(b).parent.joinpath("mesh.npz").read_bytes())
    _npz(Path(b).parent / "mesh.npz", tri=((0, 0, 0), (3, 0, 0), (0, 3, 0)))
    assert "mesh npz sha256" in pipeline.bundle_mismatch(plan, b, None)
