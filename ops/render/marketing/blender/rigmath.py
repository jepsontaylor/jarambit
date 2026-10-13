"""Pure-numpy scene math shared by the Blender worker and the host tests (no bpy import).

Conventions (documented in notes/LOOKDEV.md, used by worker.py):
  * World frame = mesh-bundle canonical frame, meters, +Z up.
  * A frame's (az, el) is the camera direction relative to the object. The worker realises it as a
    turntable: the object rotates by -az about the world +Z axis through the pivot, the camera sits
    at azimuth 0 (on -Y, looking +Y) at elevation el. Lights and floor are fixed to the world, so
    reflections travel across the part during a turntable.
  * dir(az, el) = (cos el * sin az, -cos el * cos az, sin el) is the unit vector target -> camera in
    the object (canonical) frame.
"""
import hashlib
import math

import numpy as np


def cam_dir(az_deg, el_deg):
    a, e = math.radians(az_deg), math.radians(el_deg)
    return np.array([math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e)])


def rot_z(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def look_at_basis(cam_pos, target, roll_deg=0.0):
    """Camera basis (right, up, back) with back = normalize(cam - target); world +Z is up."""
    back = np.asarray(cam_pos, float) - np.asarray(target, float)
    back /= np.linalg.norm(back)
    up0 = np.array([0.0, 0.0, 1.0]) if abs(back[2]) < 0.999 else np.array([0.0, 1.0, 0.0])
    right = np.cross(up0, back); right /= np.linalg.norm(right)
    up = np.cross(back, right)
    if roll_deg:
        r = math.radians(roll_deg)
        right, up = right * math.cos(r) + up * math.sin(r), -right * math.sin(r) + up * math.cos(r)
    return right, up, back


def project(P, cam_pos, target, focal_mm, sensor_mm, res, roll_deg=0.0):
    """Project world points -> normalized frame coords u,v in [0,1] (u right, v up) and depth.
    Sensor fit is horizontal (sensor_mm is the frame width), as Blender's AUTO fit for w >= h."""
    right, up, back = look_at_basis(cam_pos, target, roll_deg)
    d = np.asarray(P, float) - np.asarray(cam_pos, float)
    z = -(d @ back)
    x = d @ right; y = d @ up
    w, h = res
    half_w = sensor_mm / (2.0 * focal_mm)
    half_h = half_w * h / w
    u = 0.5 + 0.5 * (x / z) / half_w
    v = 0.5 + 0.5 * (y / z) / half_h
    return u, v, z


def frame_points(V, pivot, az):
    """Object points (canonical) -> world under the turntable rotation for azimuth az."""
    return (np.asarray(V) - pivot) @ rot_z(-az).T


def frame_camera(pivot, target, az, el, distance):
    """World camera position and world target for a frame (camera stays at azimuth 0)."""
    t = rot_z(-az) @ (np.asarray(target, float) - pivot)
    return t + distance * cam_dir(0.0, el), t


def frame_extent(V, pivot, target, az, el, distance, focal_mm, sensor_mm, res, roll=0.0):
    cam, t = frame_camera(pivot, target, az, el, distance)
    u, v, z = project(frame_points(V, pivot, az), cam, t, focal_mm, sensor_mm, res, roll)
    return u.min(), u.max(), v.min(), v.max(), z.min()


def fit_distance(V, pivot, frames, focal_mm, sensor_mm, res, fill=(0.62, 0.78), margin=0.06, iters=60):
    """Fallback auto-framing (the farm normally supplies distance_m from framing.py).
    One distance for the whole trajectory: the widest frame fills `fill[1]` of the width at most and
    every frame keeps `margin` on every side. Returns (distance, report)."""
    Vs = np.asarray(V, float)
    if len(Vs) > 4000:  # hull subsample is enough for framing; deterministic stride
        Vs = Vs[:: max(1, len(Vs) // 4000)]
    diag = float(np.linalg.norm(np.ptp(Vs, 0)))

    def worst(d):
        wmax, mmin = 0.0, 1.0
        for f in frames:
            u0, u1, v0, v1, zmin = frame_extent(Vs, pivot, f['target'], f['az'], f['el'], d,
                                                focal_mm, sensor_mm, res, f.get('roll', 0.0))
            if zmin <= 0:
                return 9.0, -1.0
            wmax = max(wmax, u1 - u0)
            mmin = min(mmin, u0, 1 - u1, v0, 1 - v1)
        return wmax, mmin

    lo, hi = diag * 0.05, diag * 200.0
    for _ in range(iters):  # smallest distance with width <= fill_hi and margin >= margin
        mid = math.sqrt(lo * hi)
        w, m = worst(mid)
        if w <= fill[1] and m >= margin:
            hi = mid
        else:
            lo = mid
    w, m = worst(hi)
    return float(hi), {'fill_max': float(w), 'margin_min': float(m), 'fill_ok': bool(fill[0] <= w <= fill[1]),
                       'margin_ok': bool(m >= margin)}


def auto_fstop(depth_near, depth_far, focus_dist, focal_mm, sensor_mm, res_w, max_coc_px=1.5, fmin=4.0, fmax=22.0):
    """Smallest f-number >= fmin so the circle of confusion at both depth extremes is <= max_coc_px
    (thin-lens). Used for whole-object shots so the full knife reads sharp."""
    f = focal_mm / 1000.0
    coc_lim = max_coc_px * (sensor_mm / 1000.0) / res_w

    def coc(N):
        A = f / N
        return max(A * abs(d - focus_dist) / d * f / (focus_dist - f) for d in (depth_near, depth_far))

    N = fmin
    while N < fmax and coc(N) > coc_lim:
        N *= 2 ** (1 / 6)
    return round(min(N, fmax), 2)


def frame_seed(plan_key, index, base_seed=0):
    h = hashlib.sha256(f'{plan_key}:{int(index)}:{int(base_seed)}'.encode()).hexdigest()
    return int(h[:8], 16) & 0x7FFFFFFF


def light_position(az_deg, el_deg, dist):
    """Rig lights are specified around the camera axis: az 0 = camera side, +az toward camera-right."""
    return dist * cam_dir(az_deg, el_deg)


def principal_axes(V):
    c = V.mean(0)
    w, vec = np.linalg.eigh(np.cov((V - c).T))
    return c, w, vec  # ascending variance; vec[:, 0] = blade-plane normal for a flat part


def points_in_frame(P, cam_pos, target, focal_mm, sensor_mm, res, roll_deg=0.0, margin=0.02):
    """Boolean mask: which world points land inside the frame (plus `margin` of frame size) in front
    of the camera. Used to prove no emitter (or its floor mirror image) is ever in shot."""
    P = np.atleast_2d(np.asarray(P, float))
    u, v, z = project(P, cam_pos, target, focal_mm, sensor_mm, res, roll_deg)
    return (z > 0) & (u > -margin) & (u < 1 + margin) & (v > -margin) & (v < 1 + margin)


def segment_hits_frame(P, cam_pos, target, focal_mm, sensor_mm, res, roll_deg=0.0, margin=0.02, steps=16):
    """Densify the convex hull edges between consecutive corner quads so a big emitter that spans the
    frame with all corners outside is still caught."""
    P = np.atleast_2d(np.asarray(P, float))
    pts = [P]
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            s = np.linspace(0, 1, steps)[:, None]
            pts.append(P[i] + s * (P[j] - P[i]))
    Q = np.vstack(pts)
    return bool(points_in_frame(Q, cam_pos, target, focal_mm, sensor_mm, res, roll_deg, margin).any())
