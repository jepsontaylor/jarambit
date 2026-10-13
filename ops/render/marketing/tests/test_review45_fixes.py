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


def _bundle(tmp_path, sha, npz="n" * 64, name="b.json"):
    doc = {"schema": 1, "source": {"sha256": sha}, "bbox_m": [[0, 0, 0], [1, 1, 1]], "normal_policy": "x",
           "unit_scale_to_m": 0.001, "n_vertices": 3, "n_triangles": 1, "npz_sha256": npz}
    p = tmp_path / name
    p.write_text(json.dumps(doc))
    return str(p)


# 1: supplied bundle/regions must match the plan
def test_bundle_mismatch_rejected(tmp_path):
    plan = {"bundle": {"source_sha256": "a" * 64, "npz_sha256": "n" * 64}, "regions_sha256": "missing"}
    assert pipeline.bundle_mismatch(plan, _bundle(tmp_path, "a" * 64), None) is None
    assert "source_sha256" in pipeline.bundle_mismatch(plan, _bundle(tmp_path, "b" * 64, name="g3.json"), None)
    assert "npz_sha256" in pipeline.bundle_mismatch(plan, _bundle(tmp_path, "a" * 64, npz="m" * 64, name="o.json"), None)
    assert "not found" in pipeline.bundle_mismatch(plan, str(tmp_path / "nope.json"), None)


def test_regions_mismatch_rejected(tmp_path):
    r = tmp_path / "regions.json"
    r.write_text("{}")
    good = canon.sha256_file(str(r))
    plan = {"bundle": {"source_sha256": "a" * 64, "npz_sha256": "n" * 64}, "regions_sha256": good}
    b = _bundle(tmp_path, "a" * 64)
    assert pipeline.bundle_mismatch(plan, b, str(r)) is None
    assert "no regions" in pipeline.bundle_mismatch(plan, b, None)
    r.write_text('{"x":1}')
    assert "regions sha256" in pipeline.bundle_mismatch(plan, b, str(r))


# 2: resume records are bound to the plan
def test_old_plan_receipt_not_resumed(tmp_path):
    out = str(tmp_path / "shots" / "turntable" / "final_4k")
    os.makedirs(out)
    png = os.path.join(out, "turntable_0000.png")
    Path(png).write_bytes(b"png")
    farm.claim_out_dir(out, "old")
    farm.write_receipt(out, 0, png, "h", "u", 1, 1.0, "old")
    assert farm.frame_done(out, 0, "turntable", "old")
    assert not farm.frame_done(out, 0, "turntable", "new")
    farm.claim_out_dir(out, "new")
    assert not farm.frame_done(out, 0, "turntable", "new")
    assert os.path.isdir(os.path.join(out, "stale_old"))
    marker = os.path.join(out, "turntable_0000.png.done.json")
    Path(marker).write_text(json.dumps({"png": png, "png_sha256": canon.sha256_file(png), "plan_key": "old"}))
    assert not farm.frame_done(out, 0, "turntable", "new")


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
