"""Perspective camera fit in metres, with one distance for the entire trajectory.

Z is world up. At az=0 the camera is on -Y; az=90 is +X. Elevation
is above XY. Angles and roll are degrees. Sensor width uses horizontal fit,
square pixels; sensor height follows the resolution aspect ratio.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.spatial import ConvexHull, QhullError


def camera_basis(az: float, el: float, roll: float = 0) -> np.ndarray:
    angles = np.asarray([az, el, roll], dtype=float)
    if not np.isfinite(angles).all():
        raise ValueError("camera angles must be finite")
    a, e, r = np.radians(angles)
    back = np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])
    right = np.array([math.cos(a), math.sin(a), 0.0])
    up = np.cross(back, right)
    return np.array([math.cos(r) * right + math.sin(r) * up,
                     -math.sin(r) * right + math.cos(r) * up, back])


def _camera(camera: dict) -> tuple[float, float, float, float]:
    sensor, focal = float(camera["sensor_mm"]), float(camera["focal_mm"])
    w, h = camera["res"]
    near, far = float(camera.get("clip_near_m", 0.001)), float(camera.get("clip_far_m", 100))
    if not np.isfinite([sensor, focal, w, h, near, far]).all() or min(sensor, focal, w, h, near) <= 0 or far <= near:
        raise ValueError("invalid camera dimensions or clipping planes")
    return sensor / (2 * focal), sensor * h / (2 * focal * w), near, far


def project(V: np.ndarray, camera: dict, frame: dict, distance_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Return normalized screen coordinates (bottom-left origin) and depth."""
    tx, ty, _, _ = _camera(camera)
    target = np.asarray(frame.get("target", [0, 0, 0]), dtype=float)
    if target.shape != (3,) or not np.isfinite(target).all() or not np.isfinite(distance_m) or distance_m <= 0:
        raise ValueError("invalid camera target or distance")
    q = (np.asarray(V) - target) @ camera_basis(frame["az"], frame["el"], frame.get("roll", 0)).T
    depth = distance_m - q[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        xy = 0.5 + q[:, :2] / (2 * depth[:, None] * [tx, ty])
    return xy, depth


def fit(V, camera: dict, trajectory: list[dict], fill=(0.62, 0.78), margin=0.06) -> dict:
    """Fit all hull vertices by bisection over all supplied frames.

    The *largest* width along the trajectory must be in the requested fill
    interval. A thin object viewed end-on cannot fill 62% at a constant
    distance; per-frame widths are returned so callers can see that variation.
    Impossible fill/safe-area combinations raise ValueError.
    """
    V = np.asarray(V, dtype=float)
    if V.ndim != 2 or V.shape[1] != 3 or len(V) < 3 or not np.isfinite(V).all() or np.ptp(V, axis=0).max() == 0:
        raise ValueError("V must contain finite, non-coincident 3D vertices")
    if not trajectory or not 0 <= margin < 0.5 or not 0 < fill[0] <= fill[1] <= 1 - 2 * margin:
        raise ValueError("invalid trajectory, fill, or safe margin")
    try:
        hull = V[ConvexHull(V).vertices]
    except QhullError:  # planar CAD is valid; all vertices still give an exact bound
        hull = V
    _, _, near, far = _camera(camera)
    span = float(np.linalg.norm(np.ptp(V, axis=0)))
    # Validate targets/angles before the solve.
    for frame in trajectory:
        project(hull, camera, frame, span + near)

    def measure(d):
        margins, widths, depth_ranges = [], [], []
        for frame in trajectory:
            xy, depth = project(hull, camera, frame, d)
            lo, hi = xy.min(axis=0), xy.max(axis=0)
            margins.append(float(min(*lo, *(1 - hi))))
            widths.append(float(hi[0] - lo[0]))
            depth_ranges.append((float(depth.min()), float(depth.max())))
        return margins, widths, depth_ranges

    target_fill = sum(fill) / 2

    def fits(d):
        margins, widths, depths = measure(d)
        return (all(a > near for a, _ in depths) and min(margins) >= margin
                and max(widths) <= target_fill)

    lo, hi = near, max(span, near * 2)
    while not fits(hi):
        hi *= 2
        if hi > far * 2:
            raise ValueError("cannot frame the trajectory within the camera clipping range")
    for _ in range(64):
        mid = (lo + hi) / 2
        if fits(mid):
            hi = mid
        else:
            lo = mid
    d = hi * (1 + 1e-12)  # preserve the safe-area inequality after JSON round-trip
    margins, widths, depths = measure(d)
    if max(widths) < fill[0] - 1e-9 or any(b >= far for _, b in depths):
        raise ValueError("requested width fill is incompatible with safe margins or clipping range")
    return {"distance_m": d, "per_frame_margin_min": margins,
            "per_frame_width_fill": widths, "pass": True,
            "fill_policy": "maximum_width_over_trajectory", "clip_near_m": near, "clip_far_m": far}
