"""Production CAD gate for the externally staged, pinned hero (plan.HERO_STEP_PATH).

Run from the repo root with the CAD venv:
  python -m ops.render.marketing.notes.validate_cad --out ~/jarambit_render_scratch/hero_C9.2
Missing CAD or OCP fails. This gate is separate from portable fixture tests;
it never substitutes a smoke fixture for the owner-selected hero.
"""
import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import time

import numpy as np

from ops.render.marketing.framing import fit, project
from ops.render.marketing.ingest import HERO_PATH, HERO_SHA256, ingest, load_cad, sha256
from ops.render.marketing import regions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    a = ingest(HERO_PATH, args.out, validated_brep=True)
    b = ingest(HERO_PATH, args.out / "determinism", validated_brep=True)
    assert a == b, "resolved bundle metadata differs between repeated ingests"
    mesh_dir = args.out / "mesh"
    for name in ["mesh.npz", "bundle.json", "regions.json", "regions_debug.png"]:
        assert (mesh_dir / name).read_bytes() == (args.out / "determinism/mesh" / name).read_bytes(), name
    assert a["source"]["sha256"] == HERO_SHA256
    from ops.render.marketing import plan as _plan
    assert a["source"]["model"] == _plan.source_info(HERO_SHA256)["model"]
    assert a["normal_policy"] == "brep_analytic" and a["validated_brep"]
    with np.load(mesh_dir / "mesh.npz", allow_pickle=False) as z:
        V, F, N = z["V"], z["F"], z["N_corner"]
        assert all(np.isfinite(z[name]).all() for name in z.files)
        assert np.allclose(np.linalg.norm(N, axis=2), 1, atol=1e-6)
        source = load_cad(HERO_PATH, validated_brep=True)
        R, t = np.asarray(a["pose"]["R"]), np.asarray(a["pose"]["t"])
        error = float(np.max(abs((V - t) @ R - source.V)))
        assert error < 1e-14 and np.array_equal(F, source.F), "geometry changed"
        assert np.allclose(N, source.N_corner @ R.T, atol=1e-7), "analytic normals changed"
        assert np.allclose(np.linalg.norm(z["tangent"], axis=1), 1, atol=1e-6)
        camera = {"sensor_mm": 36, "focal_mm": 85, "res": [3840, 2160]}
        frames = [{"az": i * 10, "el": 15, "roll": 0, "target": [0, 0, 0]} for i in range(36)]
        framing = fit(V, camera, frames)
        for frame in frames:
            xy, depth = project(V, camera, frame, framing["distance_m"])
            assert xy.min() >= .06 - 1e-12 and xy.max() <= .94 + 1e-12
            assert depth.min() > .001 and depth.max() < 100
        labels, _, _, repeated = regions.classify(V, F, source.face_id, source.surface_types,
                                                  analysis=regions.topology(V, F, 1e-9))
        assert np.array_equal(labels, z["region_id"]), "region rerun differs"
        assert repeated["area_mm2"]["bevel"] > 0 and repeated["area_mm2"]["ring"] > 0
        assert repeated["diagnostics"]["ring_center_m"][0] < 0
        assert repeated["diagnostics"]["boundary_edges"] == 0
        assert repeated["diagnostics"]["nonmanifold_edges"] == 0
    expected = json.loads((Path(__file__).parents[1] / "fixtures/cube_bevel.expected.json").read_text())
    cube = load_cad(Path(__file__).parents[1] / "fixtures/cube_bevel.step", validated_brep=True)
    from ops.render.marketing.ingest import canonical_pose
    cr, ct = canonical_pose(cube.V, cube.F)
    cl, _, _, _ = regions.classify(cube.V @ cr.T + ct, cube.F, cube.face_id, cube.surface_types)
    truth = np.isin(cube.face_id, expected["chamfer_face_ids"])
    _, areas, _ = regions.triangle_geometry(cube.V, cube.F)
    iou = float(areas[truth & (cl == 1)].sum() / areas[truth | (cl == 1)].sum())
    assert iou >= .95
    (mesh_dir / "framing.json").write_text(json.dumps({"camera": camera, "trajectory": frames, **framing}, indent=2, allow_nan=False) + "\n")
    info = json.loads((mesh_dir / "regions.json").read_text())
    receipt = {"schema": "jarambit.render.cad_validation.v1", "pass": True,
        "source": a["source"], "n_vertices": a["n_vertices"], "n_triangles": a["n_triangles"],
        "normal_policy": a["normal_policy"], "validated_brep": True,
        "source_roundtrip_max_abs_error_m": error, "chamfer_iou": iou,
        "identical_repeated_bundle_bytes": True, "identical_repeated_labels": True,
        "labels_sha256": info["labels_sha256"], "area_mm2": info["area_mm2"],
        "topology": {k: info["diagnostics"][k] for k in ["euler_characteristic", "boundary_edges", "nonmanifold_edges", "genus_one_assumption_met"]},
        "framing_36_angles": framing, "art_review": "pending",
        "tools": {"python": platform.python_version(), **{p: version(p) for p in ["cadquery-ocp", "numpy", "trimesh", "scipy", "pillow"]}},
        "git_base_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "outputs": {name: sha256(mesh_dir / name) for name in ["bundle.json", "mesh.npz", "regions.json", "regions_debug.png", "framing.json"]},
        "seconds": round(time.monotonic() - start, 3)}
    (args.out / "cad_validation.json").write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"pass": True, "bundle": str(mesh_dir / "bundle.json"), "npz_sha256": a["npz_sha256"],
                      "chamfer_iou": iou, "minimum_margin": min(framing["per_frame_margin_min"]), "seconds": receipt["seconds"]}))


if __name__ == "__main__":
    main()
