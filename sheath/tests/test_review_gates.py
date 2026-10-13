"""Runner-level failures and evidence gates from PR #56's independent review."""
import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from shapely.geometry import box

from sheath import ccx_tab as C, generate as G, interface as I, model as M, run as R, strength as S
from sheath.tests.test_interface import crescent


@pytest.fixture
def runner(monkeypatch, tmp_path):
    """Exercise actual annotation loading, interface validation and runner dispatch."""
    f = I.from_pheno(crescent())
    polygon = box(-20, -10, 120, 80)
    raw = {key: f[key] for key in ("frame", "planform", "holes", "ring", "tip")}
    raw.update(source={"step_sha256": "a" * 64}, t_max_mm=4.5,
               brep={"mass_g_ti64": 60.0}, sharp_runs=f["sharp_regions"])
    raw["ring"] = {"centroid": [0, 0], "eq_radius_mm": 12.7}
    monkeypatch.setattr("sheath.ingest.ingest", lambda *args: (raw, None, polygon))
    monkeypatch.setattr(I, "tessellation_error", lambda *args: {"max": 0.0})
    monkeypatch.setattr(R, "safe_workers", lambda *args: 1)
    annotation = {"source_sha256": "a" * 64,
                  "review": {"approved": True, "reviewer": "owner", "date": "2026-10-13"},
                  "seating_lands": [{"name": "approved stop", "x_range": [100, 120]}],
                  "retention_lands": [{"hole_centroid": [90, 10]}], "bumper_lands": []}
    path = tmp_path / "annotations.json"
    out = tmp_path / "result"
    def invoke(ann, extra=()):
        path.write_text(json.dumps(ann))
        monkeypatch.setattr(sys, "argv", ["sheath.run", "--step", "knife.step", "--stl", "knife.stl",
                                        "--out", str(out), "--annotations", str(path), *extra])
        R.main()
        return json.loads((out / "metrics.json").read_text())
    return annotation, path, out, invoke


@pytest.mark.parametrize("case", ["wrong_hash", "unapproved", "truthy_approval", "missing_reviewer"])
def test_runner_rejects_annotations_before_geometry(runner, monkeypatch, case):
    ann, _, _, invoke = runner
    if case == "wrong_hash": ann["source_sha256"] = "b" * 64
    if case == "unapproved": ann["review"]["approved"] = False
    if case == "truthy_approval": ann["review"]["approved"] = "yes"
    if case == "missing_reviewer": del ann["review"]["reviewer"]
    search = Mock(side_effect=AssertionError("rejected lands reached search"))
    cad = Mock(side_effect=AssertionError("rejected lands reached CAD"))
    monkeypatch.setattr(R, "search_path", search)
    monkeypatch.setattr(G, "solid3d_full", cad)
    result = invoke(ann)
    assert result["status"] == "INCOMPLETE"
    assert result["path_feasible"] is None
    assert result["fitness"]["feasible"] is False and result["fitness"]["score"] == 0
    search.assert_not_called(); cad.assert_not_called()


def test_runner_consumes_validated_object_without_reloading_file(runner, monkeypatch):
    ann, path, _, invoke = runner
    expected = copy.deepcopy(ann["seating_lands"][0])
    def search(*args):
        # The file changes after approval; the runner must retain the approved snapshot.
        path.write_text(json.dumps({"seating_lands": [{"name": "rejected raw land", "x_range": [0, 10]}]}))
        return [(G.SheathParams(), True, 100, 10)], 1
    monkeypatch.setattr(R, "search_path", search)
    def build(*args, **kwargs):
        assert kwargs["seating_land"] == expected
        raise RuntimeError("approved snapshot reached geometry")
    monkeypatch.setattr(G, "build2d", build)
    with pytest.raises(RuntimeError, match="approved snapshot"):
        invoke(ann)


def test_runner_rejects_explicitly_incomplete_ccx(runner, monkeypatch, tmp_path):
    ann, _, _, invoke = runner
    ccx = tmp_path / "ccx.json"
    ccx.write_text(json.dumps({"status": "INCOMPLETE", "ccx_over_bayer_rot": 0.844}))
    search = Mock(side_effect=AssertionError("invalid correction reached search"))
    monkeypatch.setattr(R, "search_path", search)
    result = invoke(ann, ("--ccx", str(ccx)))
    assert result["status"] == "INCOMPLETE" and result["fitness"]["score"] == 0
    assert result["incomplete_evidence"] == ["ccx_calibration"]
    search.assert_not_called()


def test_workers_obey_inherited_memory_cap(monkeypatch):
    root = "/sys/fs/cgroup"
    files = {"/proc/self/cgroup": "0::/parent/child\n",
             root + "/parent/child/memory.max": "max",
             root + "/parent/memory.max": str(32 << 30),
             root + "/parent/memory.current": str(4 << 30), root + "/memory.max": "max"}
    def read(path, *args, **kwargs):
        if str(path) not in files: raise FileNotFoundError(str(path))
        return files[str(path)]
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(R.os, "cpu_count", lambda: 96)
    monkeypatch.setattr(R.os, "sched_getaffinity", lambda _: set(range(96)))
    monkeypatch.setattr(R, "_avail_gb", lambda: 1000)
    assert R._cgroup_limit_gb() == 28
    assert R.safe_workers() == 7
    assert R.safe_workers(40) == 7


def test_workers_obey_host_ceiling(monkeypatch):
    monkeypatch.setattr(R.os, "cpu_count", lambda: 96)
    monkeypatch.setattr(R.os, "sched_getaffinity", lambda _: set(range(96)))
    monkeypatch.setattr(R, "_avail_gb", lambda: 1000)
    monkeypatch.setattr(R, "_cgroup_limit_gb", lambda: None)
    assert R.safe_workers(96) == 16


@pytest.mark.parametrize("requested", [0, -1])
def test_workers_reject_nonpositive_requests(requested):
    with pytest.raises(ValueError, match="positive integer"):
        R.safe_workers(requested)


def test_spherical_cad_cannot_claim_directional_land():
    p = G.SheathParams(detent_undercut=1.7)
    evidence = G.bump_evidence(p, 2.990341)
    assert evidence["max_projected_radius_mm"] == pytest.approx(1.60294117647)
    assert evidence["projected_radial_clearance_mm"] > 1.38
    screen = S.first_contact_screen(box(-10, -10, 10, 10), box(-12, -12, 12, 12),
                                    np.array([[10, 0]]), np.array([[0, 0]]), hole_land=evidence)
    assert screen["status"] == "INCOMPLETE"
    assert screen["frac_land_first"] is None and screen["worst"] is None


@pytest.mark.parametrize("retention", ["tab", "collar"])
def test_bump_evidence_matches_both_exported_cad_paths(retention):
    cq = pytest.importorskip("cadquery")
    p = G.SheathParams(retention=retention, detent_undercut=1.7, tab_L=16, wall=2)
    g = {"outline": box(-30, -20, 30, 20), "cavity": box(-25, -15, 25, 15),
         "D": box(-100, -100, 100, 100), "n": np.array([1.0, 0.0])}
    solids = G.solid3d_full(g, p, 4.5, (0, 0))
    parts = solids.values() if isinstance(solids, dict) else [solids]
    gap = 4.5 + 2 * p.c_face
    interior = cq.Workplane("XY").box(10, 10, gap - 0.002)
    intersections = [part.intersect(interior).val() for part in parts]
    bumps = [shape for shape in intersections if shape.Volume() > 1e-6]
    width = max(shape.BoundingBox().xlen for shape in bumps)
    assert width / 2 == pytest.approx(G.bump_evidence(p, 2.990341)["max_projected_radius_mm"], abs=1e-5)


@pytest.mark.parametrize("sf", [None, {}, {"design_shock": None}, math.nan, math.inf, -math.inf, True, 1.999])
def test_p05_floor_rejects_missing_nonfinite_or_weak_search_and_final_evidence(sf):
    good = {"annotation_status": "APPROVED", "path_feasible": True, "min_edge_clearance_mm": 1,
            "rim_min_mm": 3, "insert_n": 30, "strain_est": 0.01, "p_in_life_window": 0.97,
            "p_in_new_window": 0.9, "draw_n": 35, "mass_g": 20, "retention_sf_p05": sf}
    fitness = M.fitness(good)
    assert fitness["feasible"] is False and fitness["score"] == 0
    assert R._retention_rank({"score": 1}, {"retention_sf_p05": sf, "p_life": 1, "p_new": 1}, 1) is None


def test_heavy_knife_fails_retention_floor_and_exact_floor_passes():
    sf = M.inertial_sf(23.3128585, 200, M.RETENTION_CASES["design_shock"])
    assert sf < 0.8 and not M.retention_floor_pass(sf)
    assert R._retention_rank({"score": 1}, {"retention_sf_p05": sf, "p_life": 1, "p_new": 1}, 1) is None
    assert M.retention_floor_pass({"design_shock": M.RETENTION_SF_MIN})


def history(terminal=1.0, peak=14):
    return "".join(f"total force (fx,fy,fz) for set KDRV and time {t}\n {peak} 0 0\n" for t in (0.1, terminal))


def fake_solver(monkeypatch, mode):
    def run(args, **kwargs):
        if args[-1] == "-v": return subprocess.CompletedProcess(args, 0, "This is Version 2.21\n", "")
        job = Path(kwargs["cwd"]) / args[-1]
        rc = 1 if mode == "failed" else 0
        dat = job.with_suffix(".dat")
        if mode != "absent":
            peak = 30 if mode == "unconverged" and job.name == "tab_l4" else 14
            dat.write_text(history(0.2 if mode == "partial" else 1.0, peak))
            if mode == "stale": os.utime(dat, ns=(1, 1))
        return subprocess.CompletedProcess(args, rc, "fake solver", "")
    monkeypatch.setattr(C.subprocess, "run", run)


@pytest.mark.parametrize("mode", ["failed", "partial", "stale", "absent", "unconverged"])
def test_ccx_refuses_failed_partial_stale_or_unconverged_factors(tmp_path, monkeypatch, mode):
    # A complete old root-level .dat must never rescue a failed fresh run.
    stale = tmp_path / "tab_l3.dat"; stale.write_text(history())
    fake_solver(monkeypatch, mode)
    record = C.run(str(tmp_path), levels=(3, 4))
    assert record["status"] == "INCOMPLETE" and record["ccx_over_bayer_rot"] is None
    assert stale.read_text() == history()
    with pytest.raises(ValueError, match="INCOMPLETE"):
        C.load_correction(tmp_path / "ccx_tab.json")


def test_ccx_correction_is_bound_to_complete_solver_artifacts(tmp_path, monkeypatch):
    fake_solver(monkeypatch, "complete")
    record = C.run(str(tmp_path), levels=(3, 4))
    path = tmp_path / "ccx_tab.json"
    factor, _ = C.load_correction(path)
    assert record["status"] == "COMPLETE" and factor > 0
    dat = tmp_path / record["levels"][-1]["artifacts"]["dat"]["path"]
    dat.write_text(history(0.2))
    # Even updating a digest cannot turn a truncated force history into completion.
    record["levels"][-1]["artifacts"]["dat"]["sha256"] = C._sha(dat)
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="partial"):
        C.load_correction(path)


def test_ccx_consumer_rejects_forged_success_on_failed_level(tmp_path, monkeypatch):
    fake_solver(monkeypatch, "failed")
    record = C.run(str(tmp_path), levels=(3, 4))
    record["status"] = "COMPLETE"
    path = tmp_path / "ccx_tab.json"; path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="failed, partial or stale"):
        C.load_correction(path)
