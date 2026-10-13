"""Verified region overrides for host Python or Blender (only NumPy required)."""
import hashlib
import json
from pathlib import Path

import numpy as np


def apply_region_overrides(mesh, regions_path, npz_sha256):
    """Return a new mesh mapping with v2 appearance attributes applied.

    Worker integration calls this immediately after loading regions.json,
    before posing the part or computing region targets. The base NPZ stays
    byte-identical and its embedded v1 labels remain available for old runs.
    """
    path = Path(regions_path)
    info = json.loads(path.read_text())
    if not info.get("attribute_overrides"):
        return mesh
    if info.get("base_npz_sha256") != npz_sha256:
        raise ValueError("region overrides belong to a different mesh NPZ")
    updated = dict(mesh)
    shapes = {"region_id": (len(mesh["F"]),), "tangent": (len(mesh["F"]), 3)}
    dtypes = {"region_id": np.dtype("uint8"), "tangent": np.dtype("float32")}
    for name, spec in info["attribute_overrides"].items():
        if name not in shapes:
            raise ValueError(f"unsupported region override: {name}")
        target = (path.parent / spec["path"]).resolve()
        if target.parent != path.parent.resolve():
            raise ValueError("region override must be a sibling file")
        if hashlib.sha256(target.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError(f"region override sha256 mismatch: {name}")
        value = np.load(target, allow_pickle=False)
        if value.shape != shapes[name] or value.dtype != dtypes[name] or not np.isfinite(value).all():
            raise ValueError(f"invalid region override array: {name}")
        updated[name] = value
    labels = updated["region_id"]
    if labels.max() > 6 or hashlib.sha256(labels.tobytes()).hexdigest() != info["labels_sha256"]:
        raise ValueError("region labels hash or label range mismatch")
    if not np.allclose(np.linalg.norm(updated["tangent"], axis=1), 1, atol=1e-6):
        raise ValueError("region tangent is not unit length")
    return updated
