"""Pro-hero geometry + layout prep (host Python: numpy, cv2; no bpy). Works for any ingested CAD bundle.

1. Normal repair (render-only, positions untouched): CAD outlines exported as polylines give side walls
   made of many planar B-rep strips (C.9.3: 1398 planes, median 4.9 deg between neighbours). Analytic
   per-face normals then reflect as stepped boxy bands. Wall corners (|n.y|<0.5) get the angle-weighted
   average of adjacent wall face normals within a crease angle (default 25 deg); real corners stay hard.
   Broad faces, bevels and analytic surfaces keep the B-rep analytic normals.
2. Edge-sharpness QA (edgeqa.edge_width).
3. Art mapping: planar XZ, art width = art_scale x part length, same world mapping on both faces
   (through-print), v centred on the part.
4. Signature placement per side: the largest signature (ink footprint + margin) that fits entirely on
   flat broad-face pixels (no bevel/edge/serration/wall within margin) AND on dark art, with the left
   end as close as possible to the blade start (bevel min x). Back side is laid out unmirrored as seen
   from +Y.
python prep.py BUNDLE_DIR OUT_DIR ART.png SIGMASK.png [config.json]"""
import json, math, os, sys, hashlib
import numpy as np
try:
    import cv2
except ImportError:  # Blender only needs sig_uv / edgeqa
    cv2 = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgeqa

DEF = {'crease_deg': 25.0, 'wall_ny': 0.5, 'res_mm': 0.1, 'margin_mm': 1.5, 'dark_lum': 0.10,
       'dark_blur_mm': 0.6, 'dark_cover_min': 0.995, 'art_scale': 1.0, 'art_u0': 0.12,
       'angles_deg': list(range(-14, 15, 2)), 'sig_h_max_mm': 16.0, 'sig_h_min_mm': 5.0,
       'flat_regions': ['body', 'pad', 'ring', 'spine'], 'edge_limit_mm': 0.20,
       'blade_start_tol_mm': 60.0}


def smooth_wall_normals(V, F, N, crease_deg, wall_ny):
    fn = edgeqa.face_normals(V, F)
    area = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    wall = np.abs(fn[:, 1]) < wall_ny
    c = math.cos(math.radians(crease_deg))
    N = N.copy()
    tri = np.where(wall)[0]
    corners_v = F[tri].ravel(); corners_t = np.repeat(tri, 3); corners_k = np.tile([0, 1, 2], len(tri))
    order = np.argsort(corners_v, kind='stable'); cv_, ct, ck = corners_v[order], corners_t[order], corners_k[order]
    starts = np.r_[0, np.where(np.diff(cv_))[0] + 1, len(cv_)]
    changed = 0
    for s, e in zip(starts[:-1], starts[1:]):
        ts = ct[s:e]
        if len(ts) < 2: continue
        fns = fn[ts]; w = area[ts]
        dots = fns @ fns.T
        for j in range(len(ts)):
            m = dots[j] > c
            n = (fns[m] * w[m, None]).sum(0); n /= np.linalg.norm(n) + 1e-30
            N[ts[j], ck[s + j]] = n; changed += 1
    return N, int(changed), wall


def sig_uv(dx, dz, ang_deg, L, H, side):
    """Shared with the Blender shader: world offset (dx, dz) from centre -> signature (s, t) in [0,1],
    t up, reading left->right as seen from that side (front from -Y: right=+X; back from +Y: right=-X)."""
    if side == 'back':
        dx = -dx
    c, s_ = math.cos(math.radians(ang_deg)), math.sin(math.radians(ang_deg))
    return (dx * c + dz * s_) / L + 0.5, (-dx * s_ + dz * c) / H + 0.5


def sig_kernel(ink, h_mm, aspect, ang, side, res_mm, mpx):
    """Footprint (ink + margin) on the layout grid (rows = z ascending), centred at n//2."""
    L, H = h_mm * aspect, h_mm
    R = 0.5 * math.hypot(L, H) / res_mm + mpx + 2
    n = int(2 * R) | 1
    g = (np.arange(n) - n // 2) * res_mm
    DX, DZ = np.meshgrid(g, g)
    su, tv = sig_uv(DX, DZ, ang, L, H, side)
    ih, iw = ink.shape
    k = cv2.remap(ink, (su * iw).astype(np.float32), ((1 - tv) * ih).astype(np.float32), cv2.INTER_LINEAR, borderValue=0)
    k = (k > 40).astype(np.uint8)
    return cv2.dilate(k, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * mpx + 1, 2 * mpx + 1)))


def raster(V, F, sel, res, lo, shape, edges=False):
    img = np.zeros(shape, np.uint8)
    P = ((V[:, [0, 2]] - lo) / res).astype(np.float32)
    pts = np.round(P[F[sel]] * 16).astype(np.int32)
    cv2.fillPoly(img, list(pts), 255, lineType=cv2.LINE_8, shift=4)
    if edges:   # slivers thinner than a pixel still mark their pixels
        cv2.polylines(img, list(pts), True, 255, 1, lineType=cv2.LINE_8, shift=4)
    return img


def main():
    bdir, out, art_p, sig_p = sys.argv[1:5]
    cfg = dict(DEF); cfg.update(json.load(open(sys.argv[5])) if len(sys.argv) > 5 else {})
    os.makedirs(out, exist_ok=True)
    d = np.load(os.path.join(bdir, 'mesh.npz')); bundle = json.load(open(os.path.join(bdir, 'bundle.json')))
    labels = json.load(open(os.path.join(bdir, 'regions.json')))['labels']
    V, F, R = d['V'], d['F'], d['region_id']
    N2, nchg, wall = smooth_wall_normals(V, F, d['N_corner'], cfg['crease_deg'], cfg['wall_ny'])
    np.savez_compressed(os.path.join(out, 'mesh.npz'), **{k: d[k] for k in d.files if k != 'N_corner'}, N_corner=N2)
    # pre/post facet metric: max normal step between wall neighbours sharing an edge (shading discontinuity)
    eq = edgeqa.edge_width(V, F, R, labels, cfg['edge_limit_mm'])
    # ---------- layout grid
    res = cfg['res_mm'] * 1e-3
    lo = V[:, [0, 2]].min(0) - 3e-3; hi = V[:, [0, 2]].max(0) + 3e-3
    shape = (int(math.ceil((hi[1] - lo[1]) / res)), int(math.ceil((hi[0] - lo[0]) / res)))  # rows=z, cols=x
    fn = edgeqa.face_normals(V, F)
    lab_id = {v: int(k) for k, v in labels.items()}
    flat_ids = [lab_id[n] for n in cfg['flat_regions'] if n in lab_id]
    cut_ids = [lab_id[n] for n in ('bevel', 'edge_apex', 'serration') if n in lab_id]
    Lx = float(V[:, 0].max() - V[:, 0].min())
    art = cv2.imread(art_p, cv2.IMREAD_UNCHANGED); art = art.astype(np.float32) / (65535.0 if art.dtype == np.uint16 else 255.0)
    aH, aW = art.shape[:2]
    art_w = cfg['art_scale'] * Lx; art_h = art_w * aH / aW
    x_art0 = float(V[:, 0].min()) - cfg['art_u0'] * art_w; z_mid = float((V[:, 2].min() + V[:, 2].max()) / 2)
    # art luminance resampled on the grid
    xs = lo[0] + (np.arange(shape[1]) + 0.5) * res; zs = lo[1] + (np.arange(shape[0]) + 0.5) * res
    u = (xs - x_art0) / art_w; v = (zs - z_mid) / art_h + 0.5
    mapx = np.clip(u * aW - 0.5, 0, aW - 1).astype(np.float32); mapy = np.clip((1 - v) * aH - 0.5, 0, aH - 1).astype(np.float32)
    lum_full = cv2.cvtColor(art[:, :, :3], cv2.COLOR_BGR2GRAY)
    lum = cv2.remap(lum_full, *np.meshgrid(mapx, mapy), cv2.INTER_LINEAR)
    k = max(1, int(cfg['dark_blur_mm'] / cfg['res_mm']))
    lum_b = cv2.dilate(lum, np.ones((2 * k + 1, 2 * k + 1), np.uint8))   # any bright pixel nearby disqualifies
    sig = cv2.imread(sig_p, cv2.IMREAD_GRAYSCALE)
    ys_, xs_ = np.where(sig > 127); sx0, sx1, sy0, sy1 = xs_.min(), xs_.max() + 1, ys_.min(), ys_.max() + 1
    ink = sig[sy0:sy1, sx0:sx1]; ink_aspect = (sx1 - sx0) / (sy1 - sy0)
    bevel_x0 = float(V[F[np.isin(R, cut_ids)]][:, :, 0].min()) if cut_ids else float(V[:, 0].min())
    placements = {}
    debug = {}
    for side, sgn in (('front', -1), ('back', 1)):
        face = np.isin(R, flat_ids) & (fn[:, 1] * sgn > 0.95)
        bad = ~face & (np.abs(fn[:, 1]) > 0.0)   # every other triangle facing anywhere (walls, bevels, edges)
        flat = raster(V, F, face, res, lo, shape)
        other = raster(V, F, bad & (fn[:, 1] * sgn > -0.2), res, lo, shape, edges=True)  # same-side non-flat + walls
        ok = (flat > 0) & (other == 0)
        dark = lum_b < cfg['dark_lum']
        allowed = (ok & dark).astype(np.uint8)
        mpx = int(math.ceil((cfg['margin_mm'] + 0.3) / cfg['res_mm']))   # +0.3 mm raster guard
        best = None
        h = cfg['sig_h_max_mm']
        while h >= cfg['sig_h_min_mm'] and best is None:
            hp = h / cfg['res_mm']; wp = hp * ink_aspect
            for ang in cfg['angles_deg']:
                kr = sig_kernel(ink, h, ink_aspect, ang, side, cfg['res_mm'], mpx)
                fit = cv2.erode(allowed, kr, anchor=(kr.shape[1] // 2, kr.shape[0] // 2), borderValue=0)
                cand = np.argwhere(fit > 0)
                if not len(cand): continue
                cx_m = lo[0] + (cand[:, 1] + 0.5) * res
                xk = np.where(kr.any(0))[0]
                left = cx_m + (xk.min() - kr.shape[1] // 2) * res
                lean = left - bevel_x0 if side == 'front' else left - bevel_x0
                i = int(np.argmin(np.abs(lean)))
                if abs(lean[i]) > cfg['blade_start_tol_mm'] * 1e-3: continue
                c = cand[i]
                rec = {'h_mm': round(h, 3), 'len_mm': round(h * ink_aspect, 3), 'angle_deg': ang,
                       'center_xz_m': [round(float(lo[0] + (c[1] + 0.5) * res), 6),
                                       round(float(lo[1] + (c[0] + 0.5) * res), 6)],
                       'left_end_from_blade_start_mm': round(float(lean[i]) * 1e3, 2)}
                if best is None or abs(rec['left_end_from_blade_start_mm']) < abs(best['left_end_from_blade_start_mm']):
                    best = rec
            h -= 0.25
        if best is None:
            raise SystemExit(f'no signature placement on {side}: relax dark_lum/margin or art offset')
        best['margin_mm'] = cfg['margin_mm']; best['on'] = 'flat broad face, dark art (blurred-dilated lum < %.2f)' % cfg['dark_lum']
        placements[side] = best
        dbg = np.dstack([ok * 120, dark * 120, flat // 3]).astype(np.uint8)
        debug[side] = dbg
    # NB rows of grid are z ascending; flip for viewing
    for s, im in debug.items():
        cv2.imwrite(os.path.join(out, f'layout_{s}.png'), im[::-1])
    sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
    man = {'schema': 'jarambit.render.pro.prep.v1', 'source': bundle['source'], 'bundle_npz_sha256': bundle['npz_sha256'],
           'out_npz_sha256': sha(os.path.join(out, 'mesh.npz')), 'config': cfg,
           'normal_repair': {'policy': 'render-only wall-normal smoothing; positions untouched',
                             'crease_deg': cfg['crease_deg'], 'wall_corners_changed': nchg},
           'edge_qa': eq,
           'art': {'path': art_p, 'sha256': sha(art_p), 'size_px': [aW, aH], 'width_m': art_w, 'height_m': art_h,
                   'x0_m': x_art0, 'z_mid_m': z_mid, 'mapping': 'planar XZ, same world mapping both faces'},
           'signature': {'mask': sig_p, 'mask_sha256': sha(sig_p), 'ink_px': [int(sx0), int(sy0), int(sx1), int(sy1)],
                         'mask_px': [int(sig.shape[1]), int(sig.shape[0])], 'ink_aspect': ink_aspect,
                         'bevel_start_x_m': bevel_x0, 'placements': placements}}
    json.dump(man, open(os.path.join(out, 'prep.json'), 'w'), indent=1)
    print(json.dumps({'edge': eq, 'sig': placements, 'walls': nchg}, indent=1))


if __name__ == '__main__':
    main()
