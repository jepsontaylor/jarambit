"""Manifest, SHA256SUMS, QA gates. Upload is not a function here."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import package
import plan
import qa

PIPE = ROOT / "pipeline.py"


def test_stage_verifies_and_rejects_tamper(tmp_path):
    cad = tmp_path / "hero.stl"
    cad.write_bytes(b"solid hiking\n")
    import hashlib
    sha = hashlib.sha256(cad.read_bytes()).hexdigest()
    delivery = tmp_path / "poster.jpg"
    Image.new("RGB", (8, 8), (40, 40, 40)).save(delivery, quality=92)
    root = tmp_path / "stage"
    result = package.stage(
        str(root),
        cad_path=str(cad),
        expected_cad_sha256=sha,
        mesh_bundle_sha256="c" * 64,
        toolchain={"blender": "4.2.23"},
        git_sha="4ec6934",
        plan_key="d" * 64,
        files=[{"src": str(delivery), "dest_name": "hero_3q_1920.jpg", "role": "poster"}],
        normal_policy="split_crease30_weighted",
    )
    assert package.verify_sums(str(root))
    manifest = json.loads(Path(result["manifest"]).read_text())
    assert manifest["schema"] == "jarambit.render.marketing.v1"
    assert manifest["art_review"] == "pending"
    assert manifest["caption"] == package.CAPTION
    assert manifest["source_cad"]["verified"] is True
    assert manifest["source_cad"]["sha256"] == sha
    assert manifest["mesh_bundle_sha256"] == "c" * 64
    assert manifest["git_sha"] == "4ec6934"
    assert package.banned_hits(Path(result["snippet"]).read_text()) == []
    poster = root / "hero_3q_1920.jpg"
    poster.write_bytes(poster.read_bytes() + b"x")
    assert package.verify_sums(str(root)) is False


def test_package_defaults_point_at_c92_and_reject_retired_g3(tmp_path):
    import pipeline
    parser = pipeline.build_parser()
    args = parser.parse_args([
        "package", "--root", "stage", "--bundle-sha", "c" * 64,
        "--plan-key", "d" * 64, "--file", "still.png=hero_3q_1920.jpg:poster",
    ])
    assert args.cad == plan.HERO_STEP_PATH
    assert args.cad_sha == plan.HERO_STEP_SHA256
    poster = tmp_path / "still.png"
    Image.new("RGB", (8, 8), (40, 40, 40)).save(poster, quality=92)
    try:
        package.stage(
            str(tmp_path / "retired"),
            cad_path=str(tmp_path / plan.RETIRED_G3_STL),
            expected_cad_sha256=plan.RETIRED_G3_SHA256,
            mesh_bundle_sha256="c" * 64,
            toolchain={},
            git_sha="abc",
            plan_key="d" * 64,
            files=[{"src": str(poster), "dest_name": "hero_3q_1920.jpg", "role": "poster"}],
        )
    except package.PackageError as exc:
        assert plan.RETIRED_G3_SHA256 in str(exc)
        assert "C.9.2" in str(exc)
    else:
        raise AssertionError("retired g3 sha must not stage a hero still")
    root = tmp_path / "c92"
    result = package.stage(
        str(root),
        mesh_bundle_sha256="c" * 64,
        toolchain={"blender": "4.2.23"},
        git_sha="4ec6934",
        plan_key="d" * 64,
        files=[{"src": str(poster), "dest_name": "hero_3q_1920.jpg", "role": "poster"}],
    )
    manifest = json.loads(Path(result["manifest"]).read_text())
    assert manifest["source_cad"]["path"] == plan.HERO_STEP_PATH
    assert manifest["source_cad"]["sha256"] == plan.HERO_STEP_SHA256
    assert manifest["source_cad"]["verified"] is True
    assert manifest["source_cad"]["model"] == "SWITCHBACK Rev C.9.2"
    assert manifest["source_cad"]["replaces_sha256"] == plan.RETIRED_G3_SHA256


def test_qa_rejects_retired_g3_for_hero_outputs():
    measurements = _passing_measurements()
    measurements["manifest"]["source_cad"]["sha256"] = plan.RETIRED_G3_SHA256
    measurements["manifest"]["outputs"] = [
        {"path": "hero_3q_1920.jpg", "sha256": "c" * 64, "role": "poster"},
    ]
    report = qa.evaluate(measurements)
    assert "Q13" in report["failed"]
    q13 = next(item for item in report["checks"] if item["id"] == "Q13")
    assert plan.RETIRED_G3_SHA256 in q13["detail"]
    assert report["release_blocked"] is True


def test_bad_source_sha_refuses_the_manifest(tmp_path):
    cad = tmp_path / "hero.stl"
    cad.write_bytes(b"bytes")
    try:
        package.stage(
            str(tmp_path / "stage"),
            cad_path=str(cad),
            expected_cad_sha256="0" * 64,
            mesh_bundle_sha256="c" * 64,
            toolchain={},
            git_sha="abc",
            plan_key="d" * 64,
            files=[],
        )
    except package.PackageError as exc:
        assert "sha256" in str(exc)
    else:
        raise AssertionError("unverified CAD must not stage")


def test_raw_purge_stays_inside_the_root(tmp_path):
    root = tmp_path / "stage"
    root.mkdir()
    raw = root / "frame_0000_raw.exr"
    raw.write_bytes(b"exr")
    kept = root / "frame_0000_denoised.exr"
    kept.write_bytes(b"exr")
    removed = package.purge_raw(str(root), [str(raw)], keep_raw=False)
    assert raw.exists() is False
    assert kept.exists() is True
    assert removed
    outside = tmp_path / "secret.exr"
    outside.write_bytes(b"no")
    try:
        package.purge_raw(str(root), [str(outside)])
    except package.PackageError:
        pass
    else:
        raise AssertionError("purge must refuse paths outside the root")
    assert outside.exists()


def test_keep_raw_leaves_files(tmp_path):
    root = tmp_path / "stage"
    root.mkdir()
    raw = root / "a.exr"
    raw.write_bytes(b"exr")
    assert package.purge_raw(str(root), [str(raw)], keep_raw=True) == []
    assert raw.exists()


def _passing_measurements():
    image = np.full((8, 8, 3), 128, np.uint8)
    mask = np.ones((8, 8), bool)
    flat = np.full((8, 8), 0.5)
    manifest = {
        "source_cad": {"sha256": "a" * 64, "verified": True},
        "mesh_bundle_sha256": "b" * 64,
        "toolchain": {"blender": "4.2.23"},
        "git_sha": "4ec6934",
        "outputs": [{"path": "a.png", "sha256": "c" * 64}],
    }
    return {
        "seconds": [12.0, 20.0, 30.0, 40.0],
        "wall_seconds": 1000.0,
        "framing": [{"id": "hero_3q", "hero": True, "margin_min": 0.12, "fill_worst": 0.70, "pass": True}],
        "display": image,
        "mask": mask,
        "delta_e_pairs": [((50.0, 0.0, 0.0), (50.0, 0.0, 0.0))],
        "y_medians": [16.0, 126.0, 235.0],
        "residual": flat,
        "reference": flat,
        "denoised": flat,
        "floor_frames": [flat, flat, flat],
        "loop_frames": [flat, flat, flat],
        "probe": {"frames_decoded": 4, "video": {
            "color_space": "bt709", "color_primaries": "bt709", "color_transfer": "bt709",
            "color_range": "tv", "r_frame_rate": "30/1", "avg_frame_rate": "30/1",
        }},
        "frame_count": 4,
        "faststart": True,
        "decoded": True,
        "sizes": {name: 1000 for name in qa.SIZE_LIMITS},
        "plan_bytes_a": b"same",
        "plan_bytes_b": b"same",
        "manifest": manifest,
        "sums_ok": True,
        "art_review": "pending",
    }


def test_qa_blocks_release_until_a_person_approves():
    report = qa.evaluate(_passing_measurements())
    assert report["failed"] == []
    assert report["checks"][-1]["id"] == "Q14"
    assert report["checks"][-1]["status"] == "PENDING"
    assert report["art_review"] == "pending"
    assert report["release_blocked"] is True
    assert "art_review" in report["release_blocked_reasons"]


def test_missing_measurement_fails_closed():
    report = qa.evaluate({})
    failed = set(report["failed"])
    assert failed >= {f"Q{i}" for i in range(1, 14)}
    assert "Q14" not in failed


def test_clipping_fails_q4():
    image = np.full((4, 4, 3), 255, np.uint8)
    mask = np.ones((4, 4), bool)
    assert qa.check_q4(image, mask)["status"] == "FAIL"


def test_delta_e_known_pair_and_identity():
    assert qa.delta_e2000((50, 0, 0), (50, 0, 0)) == 0.0
    # Sharma, Westland, Cheung sample (Color Research & Application, 2005).
    got = qa.delta_e2000((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485))
    assert abs(got - 2.0425) < 0.001


def test_contact_sheet(tmp_path):
    paths = []
    for index, color in enumerate(((20, 30, 40), (200, 180, 40))):
        path = tmp_path / f"{index}.png"
        Image.new("RGB", (16, 16), color).save(path)
        paths.append(str(path))
    out = qa.contact_sheet(paths, str(tmp_path / "sheet.png"))
    assert out and Path(out).stat().st_size > 0
    assert qa.contact_sheet([], str(tmp_path / "empty.png")) is None


def test_peer_stages_fail_instead_of_skipping():
    for cmd in ("ingest", "finish"):
        proc = subprocess.run([sys.executable, str(PIPE), cmd], capture_output=True, text=True)
        assert proc.returncode == 2
        assert "not" in proc.stderr.lower()
