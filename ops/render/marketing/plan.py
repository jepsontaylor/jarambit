"""Deterministic render plan.

plan_key = sha256(canonical JSON of the inputs). Frame seeds are
sha256(plan_key + ":" + frame_index) truncated to a signed 31-bit integer.
One camera distance per shot is solved on the worst frame of that shot's
trajectory so a turntable keeps a constant scale.

Camera frame (recorded as camera_frame = "z_up_az0_minus_y"), matched to the
Codex framing note: Z is up, the blade plane is XZ, the broad-face normal is -Y.
Azimuth 0 places the camera on -Y. Azimuth 90 places it on +X. Elevation is
above the XY plane. profile_flat is face-on at az 0, el 0.
"""
import importlib.util
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from canon import canonical_bytes, sha256_bytes, sha256_json

SCHEMA = "jarambit.render.plan.v1"
INPUT_SCHEMA = "jarambit.render.plan.inputs.v1"
CAMERA_FRAME = "z_up_az0_minus_y"
MARGIN = 0.06
HERO_FILL = (0.62, 0.78)
# Owner lock 2026-10-13: MAJOR-release hero stills and turntable use C.10a rc4.
# Previous C.9.2/C.9.3 hashes remain accepted for their existing render plans.
# The earlier scratch bundle under ~/jarambit_render_scratch/hero is superseded.
C93_STEP_SHA256 = "3a818183bcb5b9a9093da947e00414ed29aa9bfebbb614046b8fb0b16dcbe919"
C93_STL_SHA256 = "1aeda17eba396bcec7380ac27f7d20886d64d234f70ad8d3d0cc57aaf63d74ca"
C92_STEP_SHA256 = "2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307"
C92_STL_SHA256 = "10b8c41f80b898c255cc090a349559722258f87f8af849ce9a605e14d762e847"
# C.10a rc4 source pins match designs/switchback/C10a/SHA256SUMS on main.
# Release candidate, not the design of record; V2 tip strength is record-only.
C10A_STEP_SHA256 = "441cfabc284efd632b69b169816bd1242088508d95dd93839dcea419e582dbe7"
C10A_STL_SHA256 = "0bcadad61bff550d9c527266e183440e8242c3a0222b9a89755cdc682b214411"
C10A_STEP_PATH = os.path.abspath(os.path.join(_HERE, "../../../designs/switchback/C10a/cad/switchback_revC10a_ground.step"))
C10A_STL_PATH = os.path.abspath(os.path.join(_HERE, "../../../designs/switchback/C10a/cad/switchback_revC10a_ground.stl"))
HERO_STEP_SHA256, HERO_STL_SHA256 = C10A_STEP_SHA256, C10A_STL_SHA256
HERO_SOURCE_SHA256 = frozenset({HERO_STEP_SHA256, HERO_STL_SHA256, C93_STEP_SHA256, C93_STL_SHA256, C92_STEP_SHA256, C92_STL_SHA256})
HERO_STEP_PATH = C10A_STEP_PATH
HERO_STL_PATH = C10A_STL_PATH
# Source registry: the model name, file name and reference mass for each pinned CAD hash.
# Ingest, package and QA read model names from here keyed by the actual source sha256 (from
# --cad / the plan's bundle), so nothing downstream hardcodes a revision. A new hero (e.g. a
# sharpened Rev C.10) is one entry here plus HERO_STEP/STL_* above.
KNOWN_SOURCES = {
    C93_STEP_SHA256: {"model": "SWITCHBACK Rev C.9.3", "name": "switchback_revC9_3_ground.step",
                       "reference_mass_g": 66.773, "role": "previous"},
    C93_STL_SHA256: {"model": "SWITCHBACK Rev C.9.3", "name": "switchback_revC9_3_ground.stl",
                      "reference_mass_g": 66.773, "role": "previous"},
    C92_STEP_SHA256: {"model": "SWITCHBACK Rev C.9.2", "name": "switchback_revC9_2_ground.step",
                      "reference_mass_g": 66.764, "role": "previous"},
    C10A_STEP_SHA256: {"model": "SWITCHBACK Rev C.10a", "name": "switchback_revC10a_ground.step",
                       "reference_mass_g": 64.841, "role": "hero",
                       "status_label": "release candidate rc4, not the design of record"},
    C10A_STL_SHA256: {"model": "SWITCHBACK Rev C.10a", "name": "switchback_revC10a_ground.stl",
                      "reference_mass_g": 64.841, "role": "hero",
                      "status_label": "release candidate rc4, not the design of record"},
    C92_STL_SHA256: {"model": "SWITCHBACK Rev C.9.2", "name": "switchback_revC9_2_ground.stl",
                     "reference_mass_g": 66.764, "role": "previous"},
}
HERO_MODEL = KNOWN_SOURCES[HERO_STEP_SHA256]["model"]


def source_info(sha256):
    """Registry entry for a source sha256, or None for an unpinned/unknown source."""
    return KNOWN_SOURCES.get(sha256)


def pinned_sha_for_name(name):
    """sha256 pinned to a known hero/previous file name (case-insensitive), else None."""
    low = os.path.basename(str(name or "")).lower()
    for sha, info in KNOWN_SOURCES.items():
        if info["name"].lower() == low:
            return sha
    return None


# Replaced for every hero still and the turntable. Smoke provenance only.
RETIRED_G3_SHA256 = "04404820cf8385f5e34a42ef9d39a79aecda8eb88895c78aa21f4e3a92fe28c5"
RETIRED_G3_STL = "g3_tip+00_t60_tt3.stl"
SENSOR_MM = 36.0
NEAR_CLIP_M = 0.001

# Cycles knobs from the marketing plan. They travel in the resolved plan.
# The worker request copies only the frozen profile fields.
CYCLES = {
    "max_bounces": 12,
    "glossy_bounces": 8,
    "clamp_indirect": 10,
    "light_tree": True,
}

PROFILES = {
    # Q1 on a 3090 was 54 s median at this budget. 0.005 / 1024 spp did not
    # converge on the bead-blast bump and ran about 160 s per 4K frame.
    "final_4k": {
        "res": [3840, 2160],
        "spp_max": 512,
        "spp_min": 64,
        "adaptive_threshold": 0.02,
        "auto_tile": False,
        "denoise": True,
        "device": "OPTIX",
    },
    "native_1080": {
        "res": [1920, 1080],
        "spp_max": 256,
        "spp_min": 32,
        "adaptive_threshold": 0.01,
        "denoise": True,
        "device": "OPTIX",
    },
    "preview": {
        "res": [640, 360],
        "spp_max": 64,
        "spp_min": 16,
        "adaptive_threshold": 0.02,
        "denoise": True,
        "device": "OPTIX",
    },
    "smoke": {
        "res": [160, 90],
        "spp_max": 8,
        "spp_min": 8,
        "adaptive_threshold": 0.05,
        "denoise": False,
        "device": "CPU",
    },
}

# fill_axis "width": hero band is on frame width. "max": the larger projected side.
STILLS = [
    {"id": "hero_3q", "rig_preset": "rig_studio_softbox", "az": 35.0, "el": 20.0,
     "focal_mm": 85.0, "fstop": 8.0, "hero": True, "fill_axis": "width"},
    {"id": "profile_flat", "rig_preset": "rig_studio_softbox", "az": 0.0, "el": 0.0,
     "focal_mm": 200.0, "fstop": 8.0, "hero": False, "fill_axis": "max"},
    {"id": "spine_top", "rig_preset": "rig_studio_softbox", "az": 0.0, "el": 75.0,
     "focal_mm": 85.0, "fstop": 8.0, "hero": False, "fill_axis": "max"},
    {"id": "edge_macro", "rig_preset": "rig_studio_softbox", "az": 35.0, "el": 15.0,
     "focal_mm": 135.0, "fstop": 2.8, "hero": False, "fill_axis": "max"},
    {"id": "ring_detail", "rig_preset": "rig_studio_softbox", "az": 180.0, "el": 15.0,
     "focal_mm": 135.0, "fstop": 2.8, "hero": False, "fill_axis": "max"},
    {"id": "dark_hero", "rig_preset": "rig_dark_strip", "az": 35.0, "el": 8.0,
     "focal_mm": 85.0, "fstop": 5.6, "hero": True, "fill_axis": "width"},
    {"id": "white_ecom", "rig_preset": "rig_product_white", "az": 0.0, "el": 0.0,
     "focal_mm": 85.0, "fstop": 8.0, "hero": True, "fill_axis": "width"},
    {"id": "flat_lay", "rig_preset": "rig_studio_softbox", "az": 0.0, "el": 90.0,
     "focal_mm": 85.0, "fstop": 8.0, "hero": False, "fill_axis": "max", "pose": "lay_flat"},
]

TURNTABLE = {
    "id": "turntable",
    # Art direction 2026-10-13 (Jepson): fixed arc key outside the view, dark glossy floor.
    "rig_preset": "rig_dark_arc_key",
    "el": 15.0,
    "focal_mm": 85.0,
    "fstop": 8.0,
    "frames": 240,
    "fps": 30,
    "hero": True,
    "fill_axis": "width",
}

TURNTABLE_DARK = {
    "id": "turntable_dark",
    "rig_preset": "rig_dark_arc_key",
    "el": 15.0,
    "focal_mm": 85.0,
    "fstop": 5.6,
    "frames": 240,
    "fps": 30,
    "hero": True,
    "fill_axis": "width",
}


class PlanError(RuntimeError):
    pass


def assert_hero_source(sha256):
    """Refuse a production render whose CAD is not SWITCHBACK Rev C.9.3 (C.9.2 still accepted)."""
    if sha256 not in HERO_SOURCE_SHA256:
        raise PlanError(
            "hero stills and the turntable require SWITCHBACK Rev C.9.3 (or C.9.2) "
            f"(step {HERO_STEP_SHA256} or stl {HERO_STL_SHA256}); got {sha256}"
        )


def retired_g3(sha256, path=""):
    """True for the replaced evidence/wave27 g3 STL, by hash or file name."""
    if sha256 == RETIRED_G3_SHA256:
        return True
    return os.path.basename(path or "") == RETIRED_G3_STL


def is_hero_delivery(path, role=None):
    """A still or turntable delivery of the hero model, not a fixture note."""
    role_l = (role or "").lower()
    if role_l in {"poster", "still", "turntable", "hero"}:
        return True
    base = os.path.basename(path or "").lower()
    stem = base.split(".", 1)[0]
    ids = [shot["id"] for shot in STILLS]
    ids.extend(("turntable", "turntable_dark"))
    return any(stem == shot_id or stem.startswith(shot_id + "_") for shot_id in ids)


def qfloat(value, places=6):
    return float(f"{float(value):.{places}f}")


def frame_seed(plan_key: str, index: int) -> int:
    digest = sha256_bytes(f"{plan_key}:{int(index)}".encode("utf-8"))
    return int(digest[:8], 16) & 0x7FFFFFFF


def camera_basis(az_deg, el_deg, roll_deg=0.0):
    """Rows are camera right, up, and back. back points from the target toward the camera."""
    az, el, roll = np.radians([float(az_deg), float(el_deg), float(roll_deg)])
    back = np.array([np.sin(az) * np.cos(el), -np.cos(az) * np.cos(el), np.sin(el)], float)
    right = np.array([np.cos(az), np.sin(az), 0.0], float)
    up = np.cross(back, right)
    rolled_right = np.cos(roll) * right + np.sin(roll) * up
    rolled_up = -np.sin(roll) * right + np.cos(roll) * up
    return np.vstack([rolled_right, rolled_up, back])


def camera_position(distance_m, az_deg, el_deg, target):
    back = camera_basis(az_deg, el_deg)[2]
    return np.asarray(target, float) + float(distance_m) * back


def project_uv(points, cam_pos, target, sensor_w_mm, sensor_h_mm, focal_mm, az_deg, el_deg, roll_deg=0.0):
    """u, v in 0..1 and depth. Depth is along the view, positive in front of the camera."""
    basis = camera_basis(az_deg, el_deg, roll_deg)
    q = (np.asarray(points, float) - np.asarray(target, float)) @ basis.T
    depth = float(np.linalg.norm(np.asarray(cam_pos, float) - np.asarray(target, float))) - q[:, 2]
    x = q[:, 0]
    y = q[:, 1]
    return x, y, depth


def bbox_corners(bbox_m):
    (x0, y0, z0), (x1, y1, z1) = bbox_m
    pts = [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    return np.asarray(pts, float)


def _frame_measures(points, dist, frame, sensor_w, sensor_h, focal):
    target = np.asarray(frame.get("target") or [0.0, 0.0, 0.0], float)
    cam = camera_position(dist, frame["az"], frame["el"], target)
    x, y, z = project_uv(
        points, cam, target, sensor_w, sensor_h, focal,
        frame["az"], frame["el"], frame.get("roll", 0.0),
    )
    if np.any(z <= NEAR_CLIP_M):
        return None
    u = 0.5 + (focal * (x / z)) / sensor_w
    v = 0.5 + (focal * (y / z)) / sensor_h
    umin, umax = float(u.min()), float(u.max())
    vmin, vmax = float(v.min()), float(v.max())
    margin = min(umin, vmin, 1.0 - umax, 1.0 - vmax)
    return {
        "fill_w": umax - umin,
        "fill_h": vmax - vmin,
        "margin_min": margin,
    }


def _controlling(measures, axis):
    if axis == "width":
        return measures["fill_w"]
    if axis == "height":
        return measures["fill_h"]
    return max(measures["fill_w"], measures["fill_h"])


def fit(V, camera, trajectory, fill=None, margin=MARGIN, fill_axis="width"):
    """Match framing.fit. Distance is constant across the trajectory.

    The solved fill is the worst frame's controlling axis (default: frame width).
    Margin is the minimum over every frame. pass is false when the safe area
    cannot hold the requested fill band.
    """
    points = np.asarray(V, float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) == 0:
        raise PlanError("fit expects V as (n,3)")
    if not np.isfinite(points).all():
        raise PlanError("fit got a non-finite vertex")
    fill = list(fill if fill is not None else HERO_FILL)
    if len(fill) != 2 or fill[0] <= 0 or fill[1] < fill[0] or fill[1] >= 1:
        raise PlanError(f"fill band {fill} is not usable")
    focal = float(camera["focal_mm"])
    sensor_w = float(camera["sensor_mm"])
    res_w, res_h = camera["res"]
    if res_w <= 0 or res_h <= 0:
        raise PlanError("camera res must be positive")
    sensor_h = sensor_w * (float(res_h) / float(res_w))
    target_fill = 0.5 * (float(fill[0]) + float(fill[1]))
    margin = float(margin)

    def worst(dist):
        best = None
        min_margin = 1.0
        for frame in trajectory:
            got = _frame_measures(points, dist, frame, sensor_w, sensor_h, focal)
            if got is None:
                return None
            control = _controlling(got, fill_axis)
            if best is None or control > best:
                best = control
            min_margin = min(min_margin, got["margin_min"])
        return best, min_margin

    # Bracket: lo is too close (fill above target), hi is far enough.
    hi = 0.25
    bracket = None
    for _ in range(40):
        got = worst(hi)
        if got is not None and got[0] <= target_fill:
            bracket = got
            break
        hi *= 1.7
    if bracket is None:
        return {"distance_m": None, "per_frame_margin_min": 0.0, "pass": False,
                "fill_worst": None, "reason": "no distance puts the hull in the fill band"}
    lo = hi / 64.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        got = worst(mid)
        if got is None or got[0] > target_fill:
            lo = mid
        else:
            hi = mid
    dist = qfloat(hi, 6)
    got = worst(dist)
    if got is None:
        return {"distance_m": dist, "per_frame_margin_min": 0.0, "pass": False,
                "fill_worst": None, "reason": "quantized distance crosses the near clip"}
    # A centered object at the fill target has margin (1-fill)/2. If the hull
    # is off-center, push the camera out until the margin holds, then recheck the band.
    if got[1] < margin:
        for _ in range(48):
            dist = qfloat(dist * 1.03, 6)
            got = worst(dist)
            if got is None:
                break
            if got[1] >= margin:
                break
    passed = (
        got is not None
        and got[1] + 1e-9 >= margin
        and float(fill[0]) - 1e-4 <= got[0] <= float(fill[1]) + 1e-4
    )
    return {
        "distance_m": dist,
        "per_frame_margin_min": qfloat(got[1], 6) if got else 0.0,
        "fill_worst": qfloat(got[0], 6) if got else None,
        "pass": bool(passed),
    }


def _load_external_fit():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "framing.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("jarambit_marketing_framing", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, "fit", None)
    if not callable(fn):
        raise PlanError("framing.py has no fit()")
    return fn


def _quantize_bbox(bbox_m):
    return [[qfloat(v, 6) for v in corner] for corner in bbox_m]


def _bundle_digest(bundle):
    required = ("schema", "source", "bbox_m", "normal_policy", "unit_scale_to_m", "n_vertices", "n_triangles")
    missing = [key for key in required if key not in bundle]
    if missing:
        raise PlanError(f"bundle missing {missing}")
    source = bundle["source"]
    if "sha256" not in source:
        raise PlanError("bundle source.sha256 is required")
    return {
        "schema": bundle["schema"],
        "source_sha256": source["sha256"],
        "npz_sha256": bundle.get("npz_sha256"),
        "bbox_m": _quantize_bbox(bundle["bbox_m"]),
        "normal_policy": bundle["normal_policy"],
        "unit_scale_to_m": qfloat(bundle["unit_scale_to_m"], 9),
        "n_vertices": int(bundle["n_vertices"]),
        "n_triangles": int(bundle["n_triangles"]),
    }


def _shot_spec(raw):
    keep = ("id", "rig_preset", "focal_mm", "fstop", "hero", "fill_axis", "kind")
    spec = {key: raw[key] for key in keep if key in raw}
    for key in ("az", "el", "frames", "fps"):
        if key in raw:
            spec[key] = raw[key]
    # the part pose changes the rendered image, so it is part of the plan key (normalized)
    spec["pose"] = raw.get("pose") or "as_is"
    return spec


def resolve(bundle, regions_sha256=None, finish_preset="finish_ti64", accents=None,
            profiles=None, include_dark_turntable=False, vertices=None,
            stills=None, use_external_framing=True):
    """Return the resolved plan dict. Raises PlanError when framing fails."""
    digest = _bundle_digest(bundle)
    profiles = list(profiles or ("final_4k", "native_1080"))
    unknown = [name for name in profiles if name not in PROFILES]
    if unknown:
        raise PlanError(f"unknown profile {unknown}")
    stills = list(stills if stills is not None else STILLS)
    turntables = [TURNTABLE]
    if include_dark_turntable:
        turntables.append(TURNTABLE_DARK)
    regions_sha = regions_sha256 or "missing"
    shot_specs = [_shot_spec(dict(s, kind="still")) for s in stills]
    shot_specs += [_shot_spec(dict(s, kind="turntable")) for s in turntables]
    # Framing aspect is 16:9 for every shipped profile, so one distance serves all of them.
    frame_profile = "final_4k" if "final_4k" in profiles else profiles[0]
    key_doc = {
        "schema": INPUT_SCHEMA,
        "accents": list(accents or []),
        "bundle": digest,
        "camera_frame": CAMERA_FRAME,
        "cycles": CYCLES,
        "fill": list(HERO_FILL),
        "finish_preset": finish_preset,
        "frame_profile": frame_profile,
        "include_dark_turntable": bool(include_dark_turntable),
        "margin": MARGIN,
        "profiles": profiles,
        "profile_bodies": {name: PROFILES[name] for name in profiles},
        "regions_sha256": regions_sha,
        "shot_specs": shot_specs,
    }
    plan_key = sha256_json(key_doc)
    points = np.asarray(vertices, float) if vertices is not None else bbox_corners(digest["bbox_m"])
    external = _load_external_fit() if use_external_framing else None
    focus = [0.0, 0.0, 0.0]
    resolved_shots = []
    for spec in stills:
        resolved_shots.append(_resolve_still(spec, points, plan_key, frame_profile, profiles, focus, external))
    for spec in turntables:
        resolved_shots.append(_resolve_turntable(spec, points, plan_key, frame_profile, focus, external))
    plan = {
        "schema": SCHEMA,
        "plan_key": plan_key,
        "camera_frame": CAMERA_FRAME,
        "finish_preset": finish_preset,
        "accents": list(accents or []),
        "regions_sha256": regions_sha,
        "bundle": digest,
        "cycles": CYCLES,
        "profiles": {name: PROFILES[name] for name in profiles},
        "stage_keys": {
            "inputs": plan_key,
            "shots": sha256_bytes(canonical_bytes(shot_specs)),
        },
        "shots": resolved_shots,
        "product": "SWITCHBACK-class titanium hiking/utility karambit",
        "appearance": "appearance_assumed",
    }
    return plan


def _margin_scalar(value):
    if isinstance(value, (list, tuple)):
        return min(value) if value else None
    return value


def _fill_scalar(got):
    if got.get("fill_worst") is not None:
        return got["fill_worst"]
    widths = got.get("per_frame_width_fill")
    if widths:
        return max(widths)
    return None


def _call_fit(external, points, camera, trajectory, fill_axis):
    try:
        if external is not None:
            got = external(points, camera, trajectory, list(HERO_FILL), MARGIN)
        else:
            got = fit(points, camera, trajectory, HERO_FILL, MARGIN, fill_axis=fill_axis)
    except (ValueError, PlanError) as exc:
        raise PlanError(f"framing failed: {exc}") from exc
    if not got.get("pass"):
        raise PlanError(f"framing failed for trajectory: {got}")
    if got.get("distance_m") is None:
        raise PlanError("framing returned no distance")
    # Codex returns per-frame margins as a list. The plan records the minimum.
    got = dict(got)
    got["per_frame_margin_min"] = _margin_scalar(got.get("per_frame_margin_min"))
    got["fill_worst"] = _fill_scalar(got)
    return got


def _camera_dict(focal_mm, fstop, focus):
    return {
        "focal_mm": qfloat(focal_mm, 4),
        "fstop": qfloat(fstop, 4),
        "focus_point": [qfloat(v, 6) for v in focus],
        "sensor_mm": SENSOR_MM,
    }


# Part poses applied by the worker before framing (must equal blender/worker.py POSES).
POSES = {
    "as_is": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "lay_flat": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    "stand_up": ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
}


def _resolve_still(spec, points, plan_key, frame_profile, profiles, focus, external):
    pose = spec.get("pose", "as_is")
    if pose not in POSES:
        raise PlanError(f"unknown pose {pose!r}")
    # fit against the posed geometry the worker will actually render
    points = np.asarray(points, float) @ np.asarray(POSES[pose]).T
    res = PROFILES[frame_profile]["res"]
    camera = {"focal_mm": spec["focal_mm"], "sensor_mm": SENSOR_MM, "res": res}
    trajectory = [{
        "index": 0, "az": spec["az"], "el": spec["el"], "roll": 0.0, "target": focus,
    }]
    framed = _call_fit(external, points, camera, trajectory, spec.get("fill_axis", "width"))
    distance = qfloat(framed["distance_m"], 6)
    still_profiles = [name for name in profiles if name in ("final_4k", "native_1080", "preview", "smoke")]
    return {
        "id": spec["id"],
        "kind": "still",
        "pose": pose,
        "hero": bool(spec.get("hero")),
        "rig_preset": spec["rig_preset"],
        "fps": None,
        "profiles": still_profiles,
        "camera": _camera_dict(spec["focal_mm"], spec["fstop"], focus),
        "framing": {
            "distance_m": distance,
            "per_frame_margin_min": framed.get("per_frame_margin_min"),
            "fill_worst": framed.get("fill_worst"),
            "pass": True,
        },
        "frames": [{
            "index": 0,
            "az": qfloat(spec["az"], 4),
            "el": qfloat(spec["el"], 4),
            "roll": 0.0,
            "distance_m": distance,
            "target": [qfloat(v, 6) for v in focus],
            "seed": frame_seed(plan_key, 0),
        }],
    }


def _resolve_turntable(spec, points, plan_key, frame_profile, focus, external):
    count = int(spec["frames"])
    if count < 2:
        raise PlanError("turntable needs at least 2 frames")
    res = PROFILES[frame_profile]["res"]
    camera = {"focal_mm": spec["focal_mm"], "sensor_mm": SENSOR_MM, "res": res}
    # index count is not rendered: frame N would repeat frame 0.
    trajectory = []
    for index in range(count):
        trajectory.append({
            "index": index,
            "az": qfloat(360.0 * index / count, 4),
            "el": qfloat(spec["el"], 4),
            "roll": 0.0,
            "target": focus,
        })
    framed = _call_fit(external, points, camera, trajectory, spec.get("fill_axis", "width"))
    distance = qfloat(framed["distance_m"], 6)
    frames = []
    for frame in trajectory:
        frames.append({
            "index": frame["index"],
            "az": frame["az"],
            "el": frame["el"],
            "roll": 0.0,
            "distance_m": distance,
            "target": [qfloat(v, 6) for v in focus],
            "seed": frame_seed(plan_key, frame["index"]),
        })
    return {
        "id": spec["id"],
        "kind": "turntable",
        "hero": bool(spec.get("hero")),
        "rig_preset": spec["rig_preset"],
        "fps": int(spec["fps"]),
        "profiles": [frame_profile],
        "camera": _camera_dict(spec["focal_mm"], spec["fstop"], focus),
        "framing": {
            "distance_m": distance,
            "per_frame_margin_min": framed.get("per_frame_margin_min"),
            "fill_worst": framed.get("fill_worst"),
            "pass": True,
        },
        "frames": frames,
    }


def dumps(plan) -> bytes:
    """Byte image used for the determinism comparison. Not the plan key."""
    return canonical_bytes(plan) + b"\n"
