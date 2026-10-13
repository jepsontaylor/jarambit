"""Maker's mark: automatic placement of Jepson Taylor's signature on any CAD mesh (numpy only).

Runs on the host and inside Blender's bundled Python (no scipy / PIL). Deterministic: the same
mesh + params give byte-identical placement JSON.

Algorithm (label-agnostic, so a new CAD such as Rev C.10 just works):
  1. Thin axis = smallest PCA axis of the vertices (Y in the canonical frame: blade plane XZ).
     Hero side = the face whose outward normal points at the az-0 camera (-Y); 'back' = +Y.
  2. Flat region = triangles with normal within `flat_deg` of the side normal, grouped by plane
     offset (0.05 mm bins); the plane with the largest area is the main side face. Bevels, grind,
     edge apex, serrations, jimping, ring bore and holes are not coplanar with it, so they are
     excluded automatically.
  3. Rasterize that plane at `grid_mm`, erode by `margin_mm` (>= 1.5 mm from every edge, bevel
     line, hole and jimping notch).
  4. Region principal axis (2D PCA of the eroded region). For angles principal + offsets, find the
     largest inscribed rectangle of the signature aspect (binary search on height, integral image).
     Largest area wins; ties -> smaller |offset|, then smaller angle.
  5. Size = min(fill * largest, max_width_mm); centre = centre of the largest rectangle.
     Orientation: text 'up' vector v = n x u must have +Z (readable, not upside-down, from the
     camera on that side).
"""
from __future__ import annotations

import hashlib
import json
import math
import os

import numpy as np

SCHEMA = "jarambit.render.signature.v1"
HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.normpath(os.path.join(HERE, "..", "brand", "signature"))
# Maker's mark asset. DEFAULT = NeverHuman (owner 2026-10-13 11:15).
ASSET_MASK = os.path.join(ASSET_DIR, "neverhuman_mask_4096.png")
ASSET_SVG = os.path.join(ASSET_DIR, "neverhuman.svg")
INK_FRACTION = 0.0689  # mean of the mask PNG: ink pixels / bbox pixels
ASPECT = 4096.0 / 1009.0
ASPECT_W_PX = 4096.0
VARIANTS = os.path.join(ASSET_DIR, "variants_neverhuman.json")
# --- Previous mark: Jepson T (v2, bold). Kept, not deleted. To re-enable it, comment out the five
# --- NeverHuman lines above and uncomment these (assets are still in ops/render/brand/signature/):
# ASSET_MASK = os.path.join(ASSET_DIR, "jepson_t_mask_4096.png")
# ASSET_SVG = os.path.join(ASSET_DIR, "jepson_t.svg")
# INK_FRACTION = 0.0579
# ASPECT = 4096.0 / 1345.0
# VARIANTS = os.path.join(ASSET_DIR, "variants.json")
_VCACHE = {}


def _variant(p, width_m):
    """Thinnest-acceptable stroke-weight variant of the mask for a final width (None = base)."""
    v = json.load(open(VARIANTS))["variants"]
    names = sorted(v)
    pick = names[0]
    if width_m is not None:
        for nm in names:
            pick = nm
            if v[nm]["stroke_px_p1_p5_p50"][1] * width_m / ASPECT_W_PX >= p["min_stroke_mm"] * 1e-3:
                break
    rec = dict(v[pick], name=pick)
    if pick not in _VCACHE:
        shp = rec["occ_shape"]
        _VCACHE[pick] = np.unpackbits(np.load(os.path.join(ASSET_DIR, rec["occ"])), axis=1)[:, :shp[1]].astype(bool)
    rec["occ_arr"] = _VCACHE[pick]
    rec["mask"] = os.path.join(ASSET_DIR, rec["mask"])
    return rec


def _kernel(occ, kw):
    """Ink occupancy resampled to kw px wide (block-any, conservative), rows flipped to grid +y=up."""
    kh = max(1, int(round(kw / ASPECT)))
    H, W = occ.shape
    S = np.pad(occ.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    r0 = np.floor(np.arange(kh) * H / kh).astype(int); r1 = np.maximum(np.ceil((np.arange(kh) + 1) * H / kh).astype(int), r0 + 1)
    c0 = np.floor(np.arange(kw) * W / kw).astype(int); c1 = np.maximum(np.ceil((np.arange(kw) + 1) * W / kw).astype(int), c0 + 1)
    K = (S[r1][:, c1] - S[r0][:, c1] - S[r1][:, c0] + S[r0][:, c0]) > 0
    return K[::-1]


def _ink_positions(out_f, out_shape, K):
    H, W = out_shape
    kh, kw = K.shape
    if kh > H or kw > W:
        return None
    Kp = np.zeros((H, W)); Kp[:kh, :kw] = K
    corr = np.fft.irfft2(out_f * np.conj(np.fft.rfft2(Kp)), s=(H, W))
    ok = corr[:H - kh + 1, :W - kw + 1] < 0.5
    return ok if ok.any() else None


def _ink_fit(Er, occ, w_rect, fill):
    """Largest width (px) at which the ink silhouette fits inside Er, then the placement at
    fill * that width nearest the centroid of feasible positions. Returns (W_max, W_final, centre_px)."""
    out = ~Er
    out_f = np.fft.rfft2(out.astype(float))
    lo, hi = max(1, int(w_rect)), Er.shape[1]
    if _ink_positions(out_f, out.shape, _kernel(occ, lo)) is None:
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _ink_positions(out_f, out.shape, _kernel(occ, mid)) is not None:
            lo = mid
        else:
            hi = mid - 1
    W_max = lo
    wf = max(1, int(fill * W_max))
    K = _kernel(occ, wf)
    ok = _ink_positions(out_f, out.shape, K)
    ys, xs = np.nonzero(ok)
    cy, cx = ys.mean(), xs.mean()
    k = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))
    return W_max, wf, np.array([xs[k] + K.shape[1] / 2.0, ys[k] + K.shape[0] / 2.0])  # width / height of the mask PNG (ink bbox + 12 px pad @ source scale)

DEFAULTS = {
    "sides": ["hero"],            # "hero", "back" or both
    "margin_mm": 1.25,           # 1.0-1.5 mm band; ink (not bbox) keeps this clearance
    "grid_mm": 0.2,
    "flat_deg": 2.0,
    "fill": 0.95,
    "max_width_mm": None,         # no cap: as large as the flat allows
    "fit": "ink",                 # "ink": the traced ink silhouette must fit (hugs the slanted script);
                                  # "bbox": its bounding rectangle must fit (conservative)
    "min_stroke_mm": 0.15,        # thinnest stroke (p5 of the stroke-width distribution) at final scale
    "min_height_mm": 2.0,
    "angle_offsets_deg": [0, -2.5, 2.5, -5, 5, -7.5, 7.5, -10, 10, -12.5, 12.5, -15, 15, -17.5, 17.5,
                          -20, 20, -22.5, 22.5, -25, 25, -30, 30],
    # finish of the mark (black-marked Ti: matte, no specular)
    "base_color_lin": [0.012, 0.012, 0.013],
    "roughness": 0.9,
    "specular_ior_level": 0.0,
    "depth_tol_mm": 0.25,
    "planes_considered": 4,
    "max_grid_px": 1600,          # raster cap per plane (longest side); grid coarsens beyond it
}


def _face_normals(V, F):
    c = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    a = np.linalg.norm(c, axis=1)
    return c / np.maximum(a, 1e-300)[:, None], a / 2


def thin_axis(V):
    X = V - V.mean(0)
    w, U = np.linalg.eigh(X.T @ X)
    ax = U[:, 0]
    k = int(np.argmax(np.abs(ax)))
    e = np.zeros(3); e[k] = 1.0
    if abs(ax[k]) > 0.98:  # snap to the canonical axis when it is one (deterministic sign)
        return e
    return ax * np.sign(ax[k])


def side_normal(V, side):
    t = thin_axis(V)
    # canonical: az-0 camera on -Y -> hero face normal is -t (t snapped to +Y)
    return -t if side == "hero" else t


def plane_basis(n):
    """In-plane (x_axis, y_axis) with y = up (+Z projected) so that x = y x n... right-handed for a
    viewer on the +n side: right x up = n."""
    up = np.array([0.0, 0.0, 1.0])
    up = up - n * np.dot(up, n)
    if np.linalg.norm(up) < 1e-6:
        up = np.array([0.0, 1.0, 0.0]) - n * n[1]
    up /= np.linalg.norm(up)
    right = np.cross(up, n)
    return right, up


def _raster_triangles(P2, F, lo, grid, shape):
    """P2 (V,2) in-plane coords, F triangles -> bool mask (H,W), pixel centres."""
    H, W = shape
    m = np.zeros((H, W), bool)
    T = (P2[F] - lo) / grid - 0.5  # pixel-index space
    for t in T:
        x0, y0 = np.floor(t.min(0)).astype(int)
        x1, y1 = np.ceil(t.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, W - 1), min(y1, H - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        a, b, c = t
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / d
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / d
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l1 + l2 <= 1 + 1e-9)
        m[ys[inside], xs[inside]] = True
    return m


def _close(mask, r):
    """Close sub-pixel tessellation cracks (dilate then erode by r px, square)."""
    if r <= 0:
        return mask
    return _erode_sq(_dilate_sq(mask, r), r)


def _box(mask, r):
    S = np.pad(mask.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    H, W = mask.shape
    y0 = np.clip(np.arange(H) - r, 0, H); y1 = np.clip(np.arange(H) + r + 1, 0, H)
    x0 = np.clip(np.arange(W) - r, 0, W); x1 = np.clip(np.arange(W) + r + 1, 0, W)
    return S[y1][:, x1] - S[y0][:, x1] - S[y1][:, x0] + S[y0][:, x0]


def _dilate_sq(mask, r):
    return _box(mask, r) > 0


def _erode_sq(mask, r):
    return _box(mask, r) == (2 * r + 1) ** 2


def erode_disk(mask, r):
    """Erode by a disk of radius r px (FFT convolution of the complement)."""
    if r <= 0:
        return mask.copy()
    p = int(math.ceil(r)) + 1
    out = ~np.pad(mask, p, constant_values=False)
    H, W = out.shape
    yy, xx = np.mgrid[-p:p + 1, -p:p + 1]
    disk = (xx * xx + yy * yy <= r * r).astype(float)
    k = np.zeros((H, W)); k[:disk.shape[0], :disk.shape[1]] = disk
    conv = np.fft.irfft2(np.fft.rfft2(out.astype(float)) * np.fft.rfft2(k), s=(H, W))
    conv = np.roll(conv, (-p, -p), axis=(0, 1))
    return (conv < 0.5)[p:-p, p:-p]


def _rotate_mask(mask, ang, lo, grid):
    """Resample mask into a frame rotated by ang (rad). Returns (mask_r, lo_r, R) where rotated
    coords q = R^T p (p in plane coords)."""
    H, W = mask.shape
    ys, xs = np.nonzero(mask)
    pts = lo + (np.column_stack([xs, ys]) + 0.5) * grid
    c, s = math.cos(ang), math.sin(ang)
    R = np.array([[c, -s], [s, c]])
    q = pts @ R
    lo_r = q.min(0) - 2 * grid
    hi_r = q.max(0) + 2 * grid
    Wr, Hr = (np.ceil((hi_r - lo_r) / grid)).astype(int)
    gy, gx = np.mgrid[0:Hr, 0:Wr]
    Q = lo_r + (np.column_stack([gx.ravel(), gy.ravel()]) + 0.5) * grid
    Pb = Q @ R.T
    ix = np.floor((Pb[:, 0] - lo[0]) / grid).astype(int)
    iy = np.floor((Pb[:, 1] - lo[1]) / grid).astype(int)
    ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
    out = np.zeros(Hr * Wr, bool)
    out[ok] = mask[iy[ok], ix[ok]]
    return out.reshape(Hr, Wr), lo_r, R


def largest_rect(E, aspect):
    """Largest axis-aligned rectangle w = aspect*h (px) fully inside E. Returns (h, w, cy, cx)
    (centre in px, float) or None. Among fitting positions picks the one nearest their centroid."""
    S = np.pad(E.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    H, W = E.shape

    def fits(h):
        w = int(round(aspect * h))
        if h > H or w > W or h < 1:
            return None
        A = S[h:, w:] - S[:-h, w:] - S[h:, :-w] + S[:-h, :-w]
        ok = A == h * w
        return ok if ok.any() else None

    lo, hi = 1, H
    best = None
    if fits(1) is None:
        return None
    while lo <= hi:
        mid = (lo + hi) // 2
        if fits(mid) is not None:
            best = mid; lo = mid + 1
        else:
            hi = mid - 1
    h = best
    w = int(round(aspect * h))
    ok = fits(h)
    ys, xs = np.nonzero(ok)
    cy, cx = ys.mean(), xs.mean()
    k = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))
    return h, w, ys[k] + h / 2.0, xs[k] + w / 2.0


def place_side(V, F, side, p=None):
    p = {**DEFAULTS, **(p or {})}
    V = np.asarray(V, float); F = np.asarray(F, np.int64)
    n = side_normal(V, side)
    fn, area = _face_normals(V, F)
    cosd = math.cos(math.radians(p["flat_deg"]))
    flat = fn @ n > cosd
    if not flat.any():
        return {"side": side, "ok": False, "reason": "no flat faces facing this side"}
    fl_ids = np.flatnonzero(flat)
    off = V[F[fl_ids]].mean(1) @ n
    # cluster coplanar faces: sort by offset, split where the gap exceeds 0.02 mm
    order = np.argsort(off, kind="stable")
    cut = np.flatnonzero(np.diff(off[order]) > 2e-5) + 1
    groups = [order[g] for g in np.split(np.arange(len(order)), cut)]
    groups.sort(key=lambda g: (-float(area[fl_ids[g]].sum()), float(off[g].mean())))
    best = None
    for gi, g in enumerate(groups[:int(p["planes_considered"])]):
        sel = fl_ids[g]
        plane_area = float(area[sel].sum())
        if best is not None and plane_area < best["_rect_area"]:
            break  # a plane smaller than the best rectangle cannot beat it
        r = _best_on_plane(V, F, sel, n, float(np.average(off[g], weights=area[sel])), p)
        if r is None:
            continue
        r["plane_rank_by_area"] = gi
        r["plane_area_mm2"] = round(plane_area * 1e6, 2)
        r["flat_faces"] = int(len(sel))
        if best is None or r["_rect_area"] > best["_rect_area"] + 1e-12:
            best = r
    if best is None:
        return {"side": side, "ok": False, "reason": "no rectangle fits on any flat plane"}
    best.pop("_rect_area")
    return {"side": side, **best}


def _best_on_plane(V, F, sel, n, plane_off, p):
    right, up = plane_basis(n)
    P2 = np.column_stack([V @ right, V @ up])
    grid = p["grid_mm"] * 1e-3
    ext = float((P2[np.unique(F[sel])].max(0) - P2[np.unique(F[sel])].min(0)).max())
    # Bound the raster: a mis-scaled (e.g. inch-as-mm) or very large flat would otherwise blow the
    # grid up quadratically (FFT erosion x 23 angles x 2 passes). Real parts (<=~300 mm) keep grid_mm.
    max_px = int(p.get("max_grid_px", 1600))
    if ext / grid > max_px:
        grid = ext / max_px
    grid_mm = grid * 1e3
    lo = P2[np.unique(F[sel])].min(0) - 3 * grid
    hi = P2[np.unique(F[sel])].max(0) + 3 * grid
    W, H = (np.ceil((hi - lo) / grid)).astype(int)
    mask = _raster_triangles(P2, F[sel], lo, grid, (H, W))
    mask = _close(mask, 1)
    E = erode_disk(mask, p["margin_mm"] / grid_mm)
    if not E.any():
        return None
    ys, xs = np.nonzero(E)
    pts = np.column_stack([xs, ys]).astype(float)
    pts -= pts.mean(0)
    w_, U = np.linalg.eigh(pts.T @ pts)
    pa = U[:, 1]
    if pa[0] < 0:
        pa = -pa
    pca_deg = math.degrees(math.atan2(pa[1], pa[0]))
    angles = [round(pca_deg + o, 6) for o in p["angle_offsets_deg"]]
    angles = [a for a in angles if math.cos(math.radians(a)) > 0.2]  # stays upright from this side
    variant = _variant(p, None)
    best = None
    for _pass in range(2):  # pass 2 refits with the stroke-weight variant chosen in pass 1
        cands = []
        for ang_deg in angles:
            Er, lo_r, R = _rotate_mask(E, math.radians(ang_deg), lo, grid)
            r = largest_rect(Er, ASPECT)
            if r is None:
                continue
            h, w, cy, cx = r
            fit = None
            if p["fit"] == "ink":
                fit = _ink_fit(Er, variant["occ_arr"], w, p["fill"])
            if fit is None:
                wf = int(p["fill"] * w)
                c_px = np.array([cx, cy])
                W_max = w
            else:
                W_max, wf, c_px = fit
            q = lo_r + c_px * grid
            cands.append((-W_max, abs(ang_deg - pca_deg), ang_deg, W_max, wf, R @ q, w, h))
        if not cands:
            return None
        cands.sort(key=lambda c: (c[0], c[1], c[2]))
        _, _, ang_deg, W_max, wf, c2, rw, rh = cands[0]
        width = wf * grid
        if p.get("max_width_mm"):
            width = min(width, p["max_width_mm"] * 1e-3)
        nv = _variant(p, width)
        if nv["name"] == variant["name"]:
            break
        variant = nv
    w_max_m, h_max_m = rw * grid, rh * grid
    height = width / ASPECT
    if height < p["min_height_mm"] * 1e-3:
        return None
    a = math.radians(ang_deg)
    u = math.cos(a) * right + math.sin(a) * up
    v = np.cross(n, u)
    assert v[2] >= -1e-9
    centre = right * c2[0] + up * c2[1] + n * plane_off
    stroke_mm = variant["stroke_px_p1_p5_p50"][1] * width / ASPECT_W_PX * 1e3
    if p.get("debug_png"):
        _debug(p["debug_png"], mask, E, lo, grid, right, up, centre, u, v, width, height, variant["occ_arr"])
    return {
        "ok": True, "_rect_area": W_max * grid * (W_max * grid / ASPECT),
        "fit": p["fit"], "fit_max_width_mm": round(W_max * grid * 1e3, 3), "fill": p["fill"],
        "mask": variant["mask"], "mask_variant": variant["name"], "ink_fraction": variant["ink_fraction"],
        "min_stroke_mm_p5": round(stroke_mm, 4), "min_stroke_mm_required": p["min_stroke_mm"],
        "normal": _r(n), "plane_offset_m": round(plane_off, 7),
        "center_m": _r(centre), "u_axis": _r(u), "v_axis": _r(v),
        "width_m": round(width, 7), "height_m": round(height, 7),
        "rotation_deg": round(math.degrees(math.atan2(np.dot(u, up), np.dot(u, right))), 4),
        "principal_axis_deg": round(pca_deg, 4), "angle_offset_deg": round(ang_deg - pca_deg, 4),
        "largest_rect_mm": [round(w_max_m * 1e3, 3), round(h_max_m * 1e3, 3)],
        "margin_mm": p["margin_mm"],
    }


def _debug(path, mask, E, lo, grid, right, up, centre, u, v, width, height, occ=None):
    from PIL import Image, ImageDraw
    img = np.zeros(mask.shape + (3,), np.uint8)
    img[mask] = (90, 90, 100); img[E] = (150, 200, 150)
    im = Image.fromarray(img[::-1].copy())
    d = ImageDraw.Draw(im)
    H = mask.shape[0]
    def px(pt):
        q = np.array([pt @ right, pt @ up]); x, y = (q - lo) / grid
        return (x, H - y)
    cs = [centre + su * u * width / 2 + sv * v * height / 2 for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    d.polygon([px(c) for c in cs], outline=(255, 40, 40))
    d.line([px(centre), px(centre + v * height / 2)], fill=(255, 255, 0))
    if occ is not None:
        ys, xs = np.nonzero(occ[::2, ::2])
        hh, ww = occ[::2, ::2].shape
        for y, x in zip(ys, xs):
            pt = centre + (x / ww - 0.5) * width * u + (0.5 - y / hh) * height * v
            d.point(px(pt), fill=(0, 0, 0))
    im.save(path)


def _r(v):
    return [round(float(x), 7) for x in v]


def asset_record():
    rec = {"mask": ASSET_MASK, "svg": ASSET_SVG, "aspect": ASPECT}
    for k in ("mask", "svg"):
        if os.path.isfile(rec[k]):
            rec[k + "_sha256"] = hashlib.sha256(open(rec[k], "rb").read()).hexdigest()
    return rec


def place(V, F, params=None):
    p = {**DEFAULTS, **(params or {})}
    sides = p["sides"] if isinstance(p["sides"], list) else [p["sides"]]
    out = {"schema": SCHEMA, "asset": asset_record(),
           "params": {k: p[k] for k in sorted(p)},
           "placements": [place_side(V, F, s, p) for s in sides]}
    return out


def transform(placement, Rp):
    """Apply a pose rotation (3x3, as in worker POSES) to a placement in-place copy."""
    q = dict(placement)
    for k in ("normal", "center_m", "u_axis", "v_axis"):
        if k in q:
            q[k] = _r(np.asarray(Rp) @ np.asarray(q[k]))
    return q


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="place the maker's mark on a mesh bundle")
    ap.add_argument("--bundle", required=True, help="bundle.json (mesh.npz next to it) or an .npz")
    ap.add_argument("--sides", default="hero")
    ap.add_argument("--out")
    ap.add_argument("--debug-png", help="prefix for per-side region/rect debug images")
    a = ap.parse_args(argv)
    npz = a.bundle if a.bundle.endswith(".npz") else os.path.join(os.path.dirname(os.path.abspath(a.bundle)), "mesh.npz")
    z = np.load(npz)
    res = {"schema": SCHEMA, "placements": []}
    prm = {"sides": a.sides.split(",")}
    res = place(z["V"], z["F"], prm)
    if a.debug_png:
        for sd in prm["sides"]:
            place_side(z["V"], z["F"], sd, {"debug_png": f"{a.debug_png}_{sd}.png"})
    s = json.dumps(res, indent=1, sort_keys=True)
    if a.out:
        open(a.out, "w").write(s + "\n")
    print(s)


if __name__ == "__main__":
    main()
