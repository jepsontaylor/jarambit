"""Resolved plans are byte-identical, and the farm shards, yields and resumes."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import farm
import plan


def bundle():
    return {
        "schema": "jarambit.render.mesh.v1",
        "source": {"path": "fixture.stl", "format": "stl", "sha256": "a" * 64, "units": "mm"},
        "unit_scale_to_m": 0.001,
        "n_vertices": 8,
        "n_triangles": 12,
        "bbox_m": [[-0.05, -0.002, -0.02], [0.05, 0.002, 0.02]],
        "normal_policy": "split_crease30_weighted",
        "npz_sha256": "b" * 64,
    }


def test_hero_source_pin_rejects_a_superseded_cad():
    plan.assert_hero_source(plan.HERO_STEP_SHA256)
    plan.assert_hero_source(plan.HERO_STL_SHA256)
    try:
        plan.assert_hero_source("a" * 64)
    except plan.PlanError as exc:
        assert "C.9.2" in str(exc)
        return
    raise AssertionError("a superseded source hash was accepted")


def test_final_4k_uses_the_measured_sample_budget():
    profile = plan.PROFILES["final_4k"]
    assert profile["spp_max"] == 512
    assert profile["spp_min"] == 64
    assert profile["adaptive_threshold"] == 0.02
    assert profile["auto_tile"] is False
    resolved = plan.resolve(bundle(), profiles=("final_4k",))
    turn = next(shot for shot in resolved["shots"] if shot["id"] == "turntable")
    request = farm.build_request(
        resolved, turn, turn["frames"][:1], "final_4k", "/tmp/out", "mesh.npz", "regions.json",
    )
    assert request["profile"]["spp_max"] == 512
    assert request["profile"]["spp_min"] == 64
    assert request["profile"]["adaptive_threshold"] == 0.02
    assert request["profile"]["auto_tile"] is False


def test_purge_passes_waits_for_the_png(tmp_path):
    raw = tmp_path / "turntable_0000.raw.exr"
    depth = tmp_path / "turntable_0000.depth.exr"
    normal = tmp_path / "turntable_0000.normal.exr"
    denoised = tmp_path / "turntable_0000.denoised.exr"
    for path in (raw, depth, normal, denoised):
        path.write_bytes(b"exr")
    assert farm.purge_passes(str(tmp_path)) == []
    assert raw.exists()
    (tmp_path / "turntable_0000.png").write_bytes(b"png")
    removed = farm.purge_passes(str(tmp_path))
    assert raw.exists() is False and depth.exists() is False and normal.exists() is False
    assert denoised.exists() is True
    assert len(removed) == 3


def test_pick_host_skips_a_busy_or_yielding_gpu():
    states = [
        {"name": "xbabe1", "reachable": True, "yield": False},
        {"name": "xbabe3", "reachable": True, "yield": True},
        {"name": "xbabe2", "reachable": True, "yield": False},
    ]
    assert farm.pick_host(states, [])["name"] == "xbabe1"
    assert farm.pick_host(states, ["xbabe1"])["name"] == "xbabe2"
    assert farm.pick_host(
        [{"name": "xbabe3", "reachable": True, "yield": True}], [],
    ) is None


def test_azimuth_zero_is_on_minus_y():
    origin = [0.0, 0.0, 0.0]
    front = plan.camera_position(2.0, 0.0, 0.0, origin)
    side = plan.camera_position(2.0, 90.0, 0.0, origin)
    assert front[1] < 0 and abs(front[0]) < 1e-9 and abs(front[2]) < 1e-9
    assert side[0] > 0 and abs(side[1]) < 1e-9


def test_resolve_is_byte_identical():
    first = plan.dumps(plan.resolve(bundle()))
    second = plan.dumps(plan.resolve(bundle()))
    assert first == second
    assert json.loads(first)["plan_key"] == json.loads(second)["plan_key"]


def test_finish_changes_the_plan_key():
    base = plan.resolve(bundle(), finish_preset="bead_blast")
    other = plan.resolve(bundle(), finish_preset="stonewash")
    assert base["plan_key"] != other["plan_key"]


def test_turntable_loop_and_seeds():
    resolved = plan.resolve(bundle())
    turn = next(shot for shot in resolved["shots"] if shot["id"] == "turntable")
    frames = turn["frames"]
    assert len(frames) == 240
    assert [frame["index"] for frame in frames] == list(range(240))
    assert frames[0]["az"] == 0.0
    assert frames[239]["az"] == 358.5
    assert all(frame["distance_m"] == frames[0]["distance_m"] for frame in frames)
    assert all(frame["seed"] == plan.frame_seed(resolved["plan_key"], frame["index"]) for frame in frames)
    assert turn["framing"]["pass"] is True
    assert turn["framing"]["per_frame_margin_min"] >= 0.06
    assert 0.62 <= turn["framing"]["fill_worst"] <= 0.78


def test_every_shot_frames_inside_the_safe_area():
    resolved = plan.resolve(bundle())
    ids = [shot["id"] for shot in resolved["shots"]]
    assert ids[:8] == [spec["id"] for spec in plan.STILLS]
    assert "turntable_dark" not in ids
    for shot in resolved["shots"]:
        assert shot["framing"]["pass"] is True
        assert shot["framing"]["per_frame_margin_min"] >= 0.06
        if shot["hero"]:
            assert 0.62 <= shot["framing"]["fill_worst"] <= 0.78


def test_dark_turntable_is_opt_in_and_still_deterministic():
    resolved = plan.resolve(bundle(), include_dark_turntable=True)
    assert any(shot["id"] == "turntable_dark" for shot in resolved["shots"])
    assert plan.dumps(resolved) == plan.dumps(plan.resolve(bundle(), include_dark_turntable=True))


def test_shards_are_contiguous_eights():
    assert farm.shard_indices(240) == [list(range(i, i + 8)) for i in range(0, 240, 8)]
    assert farm.shard_indices(20) == [list(range(0, 8)), list(range(8, 16)), list(range(16, 20))]
    assert farm.shard_indices(0) == []


def test_yield_rule():
    assert farm.should_yield(80, 0, 100, True)
    assert farm.should_yield(10, 60, 100, True)
    assert not farm.should_yield(90, 90, 100, False)
    assert not farm.should_yield(10, 10, 100, True)
    busy = farm.parse_nvidia_query("89, 6712, 24576", "2117, python3, 6702 MiB\n", our_pids=[])
    assert busy["yield"] is True
    ours = farm.parse_nvidia_query("90, 4000, 24576", "9, blender, 4000 MiB\n", our_pids=[9])
    assert ours["yield"] is False


def test_request_matches_the_frozen_schema():
    resolved = plan.resolve(bundle(), profiles=("smoke",))
    shot = resolved["shots"][0]
    request = farm.build_request(resolved, shot, shot["frames"], "smoke", "/tmp/out", "mesh.npz", "regions.json")
    assert request["schema"] == "jarambit.render.request.v1"
    assert set(request) == {
        "schema", "plan_key", "bundle_path", "regions_path", "finish_preset", "rig_preset",
        "accents", "shot", "profile", "out_dir",
    }
    assert set(request["shot"]["frames"][0]) == {"index", "az", "el", "distance_m", "target", "seed"}
    assert set(request["profile"]) == {
        "res", "spp_max", "spp_min", "adaptive_threshold", "denoise", "device", "seed",
        "auto_tile",
    }
    assert request["profile"]["auto_tile"] is False
    assert request["profile"]["device"] == "CPU"
    assert request["profile"]["res"] == [160, 90]


def test_receipt_resume_skips_a_verified_shard(tmp_path):
    resolved = plan.resolve(bundle(), profiles=("smoke",))
    dest = tmp_path / "scratch"
    hosts = [{"name": "xbabe2", "ssh": None}]
    jobs = farm.prepare_jobs(resolved, str(dest), "mesh.npz", "regions.json", hosts)
    assert jobs
    assert all(job["status"] == "pending" for job in jobs)
    job = jobs[0]
    for index in job["frames"]:
        artifact = tmp_path / f"frame_{index}.bin"
        artifact.write_bytes(b"raw-frame")
        farm.write_receipt(job["out_dir"], index, str(artifact), "xbabe2", "GPU-test", 8, 0.2, resolved["plan_key"])
    again = farm.prepare_jobs(resolved, str(dest), "mesh.npz", "regions.json", hosts)
    match = next(item for item in again if item["request_path"] == job["request_path"])
    assert match["status"] == "skip"
    artifact = Path(job["out_dir"]).parent
    # A flipped byte invalidates the receipt.
    target = tmp_path / "frame_0.bin"
    target.write_bytes(b"raw-frame-tampered")
    assert farm.frame_done(job["out_dir"], 0) is False
    assert artifact is not None


def test_assign_skips_a_yielding_host():
    jobs = [{"status": "pending", "host": None}, {"status": "skip", "host": None}, {"status": "pending", "host": None}]
    states = [
        {"name": "xbabe2", "reachable": True, "yield": True},
        {"name": "xbabe3", "reachable": True, "yield": False},
    ]
    farm.assign_hosts(jobs, states)
    assert jobs[0]["host"] == "xbabe3"
    assert jobs[1]["status"] == "skip"
    assert jobs[2]["host"] == "xbabe3"
    blocked = [{"status": "pending", "host": None}]
    farm.assign_hosts(blocked, [{"name": "xbabe2", "reachable": True, "yield": True}])
    assert blocked[0]["status"] == "yield"


def test_gpu_lock_is_exclusive():
    first = farm.acquire_gpu_lock("unitgrokplan", blocking=False)
    assert first is not None
    second = farm.acquire_gpu_lock("unitgrokplan", blocking=False)
    assert second is None
    farm.release_gpu_lock(first)
    third = farm.acquire_gpu_lock("unitgrokplan", blocking=False)
    assert third is not None
    farm.release_gpu_lock(third)


def test_remote_request_keeps_the_schema_and_moves_under_scratch():
    resolved = plan.resolve(bundle(), profiles=("smoke",))
    shot = resolved["shots"][0]
    request = farm.build_request(resolved, shot, shot["frames"], "smoke", "/local/shots/hero/smoke", "mesh/bundle.npz", "mesh/regions.json")
    updated = farm.rewrite_request(request, "/home/ubuntu/jarambit_render_scratch/abc", "mesh/bundle.npz", "mesh/regions.json")
    assert updated["schema"] == request["schema"]
    assert updated["bundle_path"].endswith("/inputs/bundle.npz")
    assert updated["regions_path"].endswith("/inputs/regions.json")
    assert updated["out_dir"].startswith("/home/ubuntu/jarambit_render_scratch/abc/shots/")
    assert set(updated["shot"]["frames"][0]) == {"index", "az", "el", "distance_m", "target", "seed"}


def test_launch_shell_starts_a_new_session(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, check, capture_output, text):
        seen["cmd"] = cmd
        return type("P", (), {"stdout": "999\n", "returncode": 0})()

    monkeypatch.setattr(farm.subprocess, "run", fake_run)
    pid = farm.launch_shell(["nice", "-n", "10", "blender"], str(tmp_path / "shard.log"), ssh_host="xbabe1")
    assert pid == "999"
    script = seen["cmd"][-1]
    assert script.startswith("setsid nohup ")
    assert "< /dev/null" in script
    assert seen["cmd"][0] == "ssh"


def test_remote_sync_ships_signature_brand(tmp_path, monkeypatch):
    code = tmp_path / "ops" / "render" / "marketing"
    code.mkdir(parents=True)
    brand = tmp_path / "ops" / "render" / "brand" / "signature"
    brand.mkdir(parents=True)
    (brand / "variants.json").write_text("{}\n")
    hdri = tmp_path / "studio.hdr"
    hdri.write_bytes(b"hdr")
    runs = []

    def fake_ssh(*_args, **_kwargs):
        return type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def fake_run(argv, check=False):
        runs.append(tuple(argv))
        return type("P", (), {"returncode": 0})()

    monkeypatch.setattr(farm, "_ssh", fake_ssh)
    monkeypatch.setattr(farm, "push_files", lambda *_a, **_k: None)
    monkeypatch.setattr(farm.subprocess, "run", fake_run)
    farm.sync_render_tree(
        "xbabe1", str(code), "/scratch/plan",
        str(tmp_path / "bundle.json"), str(tmp_path / "mesh.npz"),
        str(tmp_path / "regions.json"), str(hdri),
    )
    brand_rsync = [argv for argv in runs if argv[0] == "rsync" and argv[-1].endswith("/brand/")]
    assert brand_rsync == [(
        "rsync", "-a", str(tmp_path / "ops" / "render" / "brand") + "/",
        "xbabe1:/scratch/plan/brand/",
    )]
    code_rsync = [argv for argv in runs if argv[0] == "rsync" and "--delete" in argv]
    assert code_rsync and code_rsync[0][-1] == "xbabe1:/scratch/plan/code/"
    bare = tmp_path / "bare_marketing"
    bare.mkdir()
    with pytest.raises(OSError, match="signature assets missing"):
        farm.sync_render_tree(
            "xbabe1", str(bare), "/scratch/plan",
            str(tmp_path / "bundle.json"), str(tmp_path / "mesh.npz"),
            str(tmp_path / "regions.json"), str(hdri),
        )


def test_remote_stage_keeps_the_worker_filename(tmp_path):
    staged = farm.stage_remote_request(
        str(tmp_path), "xbabe1", "turntable_final_4k_000.json",
        {"schema": "jarambit.render.request.v1"},
    )
    assert os.path.basename(staged) == "turntable_final_4k_000.json"
    assert "remote_" not in os.path.basename(staged)
    assert staged.endswith(os.path.join("staged", "xbabe1", "turntable_final_4k_000.json"))


def test_gpu_lock_wrapper_execs_blender_in_place():
    argv = farm.wrap_gpu_lock(["nice", "-n", "10", "blender"], "GPU-test")
    script = argv[2]
    assert script.count("exec ") == 2
    assert "GPU_LOCK_BUSY" in script
    assert "exec nice -n 10 blender" in script


def test_adopt_running_keeps_the_live_shard():
    jobs = [{
        "status": "pending",
        "request_path": "/r/turntable_final_4k_002.json",
        "shot_id": "turntable",
        "profile": "final_4k",
        "shard": 2,
    }]
    found = farm.adopt_running(
        jobs, {"turntable_final_4k_002.json": "420693"}, "xbabe2", None, "/logs",
    )
    assert found == ["turntable_final_4k_002.json"]
    assert jobs[0]["status"] == "launched"
    assert jobs[0]["pid"] == "420693"
    assert jobs[0]["host"] == "xbabe2"
    assert jobs[0]["log"].endswith("turntable_final_4k_002.log")


def test_host_slot_stays_closed_while_blender_is_up():
    state = {"name": "xbabe3", "reachable": True, "yield": False}
    assert farm.host_slot_free(state, [], blender_present=True) is False
    assert farm.host_slot_free(state, [], blender_present=False) is True
    assert farm.host_slot_free(state, ["xbabe3"], blender_present=False) is False
    yielding = {"name": "xbabe2", "reachable": True, "yield": True}
    assert farm.host_slot_free(yielding, [], blender_present=False) is False


def test_qa_reads_frame_seconds_and_framing():
    import qa
    seconds = qa.seconds_from_receipts([{"frame": {"seconds": 40.0}}, {"frame": {}}])
    assert seconds == [40.0]
    rows = qa.framing_rows({
        "shots": [{
            "id": "turntable",
            "hero": True,
            "framing": {"per_frame_margin_min": [0.2, 0.1], "fill_worst": 0.7, "pass": True},
        }],
    })
    assert rows[0]["margin_min"] == 0.1
    assert rows[0]["fill_worst"] == 0.7
    assert rows[0]["hero"] is True


def test_blender_argv_pins_threads_and_factory_startup():
    argv = farm.blender_argv("/opt/blender", "/work/worker.py", "/work/request.json")
    text = " ".join(argv)
    assert "--factory-startup" in argv
    assert "--disable-autoexec" in argv
    assert "--threads" in argv and "16" in argv
    assert "OMP_NUM_THREADS=16" in text
    assert argv[0] == "nice"
