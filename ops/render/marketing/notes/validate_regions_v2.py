"""Read-only production-region gate: immutable NPZ, annotated patch IoU, rerun labels."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from ops.render.marketing.ingest import sha256
from ops.render.marketing.region_io import apply_region_overrides
from ops.render.marketing import regions


def patch_iou(V, F, face_id, labels, oracle):
    _, areas, _ = regions.triangle_geometry(V, F)
    truth = np.full(len(F), 255, np.uint8)
    for spec in oracle["patches"].values():
        mask = np.isin(face_id, spec["face_ids"])
        if not mask.any() or set(spec["face_ids"]) - set(face_id.tolist()):
            raise ValueError("annotated B-rep face IDs missing")
        if np.any(truth[mask] != 255):
            raise ValueError("overlapping oracle patches")
        truth[mask] = spec["label"]
    scope = truth != 255
    scores = {}
    for key in sorted(set(truth[scope].tolist())):
        intersection = scope & (truth == key) & (labels == key)
        union = scope & ((truth == key) | (labels == key))
        scores[regions.LABELS[key]] = float(areas[intersection].sum() / areas[union].sum())
    return scores


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    args = parser.parse_args()
    before = {p.name: sha256(p) for p in args.base.iterdir() if p.is_file()}
    assert (args.base / "mesh.npz").read_bytes() == (args.v2 / "mesh.npz").read_bytes()
    assert (args.base / "bundle.json").read_bytes() == (args.v2 / "bundle.json").read_bytes()
    with np.load(args.base / "mesh.npz", allow_pickle=False) as archive:
        base = {k: archive[k] for k in archive.files}
    applied = apply_region_overrides(base, args.v2 / "regions.json", before["mesh.npz"])
    for key in ["V", "F", "N_corner", "face_id", "uv"]:
        assert applied[key] is base[key]
    info = json.loads((args.v2 / "regions.json").read_text())
    oracle = json.loads((Path(__file__).parents[1] / "fixtures/c9_2_regions.expected.json").read_text())
    bundle = json.loads((args.base / "bundle.json").read_text())
    assert bundle["source"]["sha256"] == oracle["source_sha256"]
    assert before["mesh.npz"] == oracle["base_npz_sha256"]
    scores = patch_iou(base["V"], base["F"], base["face_id"], applied["region_id"], oracle)
    assert min(scores.values()) >= .95, scores
    faces = {int(k): v for k, v in json.loads((args.v2 / "brep_faces.json").read_text()).items()}
    repeated, tangent, _, repeated_info = regions.classify_brep(base["V"], base["F"], base["face_id"], faces, base["N_corner"])
    assert np.array_equal(repeated, applied["region_id"])
    assert np.array_equal(tangent, applied["tangent"])
    assert repeated_info["labels_sha256"] == info["labels_sha256"]
    assert hashlib.sha256(applied["region_id"].tobytes()).hexdigest() == info["labels_sha256"]
    for name in ["bevel", "ring", "edge_apex", "serration"]:
        assert info["area_mm2"][name] > 0
    assert before == {p.name: sha256(p) for p in args.base.iterdir() if p.is_file()}
    receipt = {"pass": True, "npz_byte_identical": True, "bundle_byte_identical": True,
        "production_files_sha256": before, "production_unchanged": True,
        "annotated_patch_iou": scores, "iou_threshold": .95,
        "oracle_sha256": sha256(Path(__file__).parents[1] / "fixtures/c9_2_regions.expected.json"),
        "labels_sha256": info["labels_sha256"], "deterministic_labels_and_tangent": True,
        "area_mm2": info["area_mm2"], "art_review": "pending"}
    (args.v2 / "validation.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
