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
THREADS = 1
if __name__ == '__main__':
    from runtime import ensure_memcap
    THREADS = ensure_memcap()
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
       'blade_start_tol_mm': 60.0, 'flat_ny': 0.95, 'flat_crease_deg': 4.0, 'flat_seam_limit_deg': 0.05}


def smooth_wall_normals(V, F, N, crease_deg, wall_ny, sel=None):
    fn = edgeqa.face_normals(V, F)
    area = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    wall = (np.abs(fn[:, 1]) < wall_ny) if sel is None else sel
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


def flat_seam_deg(V, F, N, fn, cfg):
    """Shading-seam QA on broad faces: at every vertex shared by same-side broad-face triangles whose face normals
    are within the flat crease, the spread of their corner normals (deg). 0 = continuous shading."""
    out = {'max_deg': 0.0, 'n_vertices': 0, 'worst_xyz_mm': None}
    for sgn in (-1, 1):
        tri = np.where(fn[:, 1] * sgn > cfg['flat_ny'])[0]
        cv_ = F[tri].ravel(); ct = np.repeat(tri, 3); ck = np.tile([0, 1, 2], len(tri))
        o = np.argsort(cv_, kind='stable'); cv_, ct, ck = cv_[o], ct[o], ck[o]
        st = np.r_[0, np.where(np.diff(cv_))[0] + 1, len(cv_)]
        cmin = math.cos(math.radians(cfg['flat_crease_deg']))
        for s_, e in zip(st[:-1], st[1:]):
            if e - s_ < 2: continue
            ts = ct[s_:e]; ns = N[ts, ck[s_:e]]
            if (fn[ts] @ fn[ts].T).min() < cmin: continue        # a real crease meets here: allowed to be hard
            dmin = float(np.clip((ns @ ns.T).min(), -1, 1)); a = math.degrees(math.acos(dmin))
            if a > out['max_deg']:
                out.update(max_deg=round(a, 4), worst_xyz_mm=[round(float(x) * 1e3, 2) for x in V[cv_[s_]]])
            out['n_vertices'] += 1
    return out


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


PINNED_CV2 = '4.12.0'


def main():
    if cv2 is None:
        raise SystemExit("prep.py needs opencv (see ops/render/pro/requirements.txt)")
    if cv2.__version__ != PINNED_CV2 and os.environ.get('PRO_ALLOW_CV2') != '1':
        raise SystemExit(f'opencv {cv2.__version__} != pinned {PINNED_CV2} (placements are cv2-version dependent); see ops/render/pro/requirements.txt')
    cv2.setNumThreads(THREADS)
    bdir, out, art_p, sig_p = sys.argv[1:5]
    cfg = dict(DEF); cfg.update(json.load(open(sys.argv[5])) if len(sys.argv) > 5 else {})
    os.makedirs(out, exist_ok=True)
    d = np.load(os.path.join(bdir, 'mesh.npz')); bundle = json.load(open(os.path.join(bdir, 'bundle.json')))
    labels = json.load(open(os.path.join(bdir, 'regions.json')))['labels']
    V, F, R = d['V'], d['F'], d['region_id']
    N2, nchg, wall = smooth_wall_normals(V, F, d['N_corner'], cfg['crease_deg'], cfg['wall_ny'])
    # Broad-face knees: CAD flats split into planar patches meeting at a few degrees (C.10a handle taper ramp
    # fid 28 | 237 | 457: 2.5 deg kinks) shade as a hard line under satin/anisotropic finishes. Weld the
    # corner normals across sub-crease knees on same-side broad faces (bevels sit far above the crease, stay hard).
    fn0 = edgeqa.face_normals(V, F)
    seam0 = flat_seam_deg(V, F, N2, fn0, cfg)
    for sgn in (-1, 1):
        N2, k, _ = smooth_wall_normals(V, F, N2, cfg['flat_crease_deg'], cfg['wall_ny'], sel=(fn0[:, 1] * sgn > cfg['flat_ny']))
        nchg_flat = k if sgn == -1 else nchg_flat + k
    seam1 = flat_seam_deg(V, F, N2, fn0, cfg)
    if seam1['max_deg'] > cfg['flat_seam_limit_deg']:
        raise SystemExit(f"flat shading-seam QA FAIL: {seam1}")
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
        def try_h(h):
            best = None
            for ang in cfg['angles_deg']:
                kr = sig_kernel(ink, h, ink_aspect, ang, side, cfg['res_mm'], mpx)
                # erosion == (forbidden * kernel) == 0; FFT keeps big glyph kernels O(N log N) (cv2.erode was O(N*K))
                from scipy.signal import fftconvolve
                kb = (kr > 0).astype(np.float32)
                hit = fftconvolve((allowed == 0).astype(np.float32), kb[::-1, ::-1], mode='full')
                oy, ox = kr.shape[0] // 2, kr.shape[1] // 2
                hit = hit[kr.shape[0] - 1 - oy: kr.shape[0] - 1 - oy + allowed.shape[0], kr.shape[1] - 1 - ox: kr.shape[1] - 1 - ox + allowed.shape[1]]
                fit = hit < 0.5   # verified identical to cv2.erode (interior)
                cand = np.argwhere(fit)
                if not len(cand): continue
                cx_m = lo[0] + (cand[:, 1] + 0.5) * res
                xk = np.where(kr.any(0))[0]
                lean = cx_m + (xk.min() - kr.shape[1] // 2) * res - bevel_x0
                i = int(np.argmin(np.abs(lean)))
                if abs(lean[i]) > cfg['blade_start_tol_mm'] * 1e-3: continue
                c = cand[i]
                rec = {'h_mm': round(h, 3), 'len_mm': round(h * ink_aspect, 3), 'angle_deg': ang,
                       'center_xz_m': [round(float(lo[0] + (c[1] + 0.5) * res), 6),
                                       round(float(lo[1] + (c[0] + 0.5) * res), 6)],
                       'left_end_from_blade_start_mm': round(float(lean[i]) * 1e3, 2)}
                if best is None or abs(rec['left_end_from_blade_start_mm']) < abs(best['left_end_from_blade_start_mm']):
                    best = rec
            return best
        # bisection on height (feasibility is monotone in h): largest fitting h to 0.1 mm
        lo_h, hi_h = cfg['sig_h_min_mm'], cfg['sig_h_max_mm']
        best = try_h(hi_h)
        if best is None:
            best = try_h(lo_h)
            while best is not None and hi_h - lo_h > 0.1:
                mid = 0.5 * (lo_h + hi_h); r = try_h(mid)
                if r is None: hi_h = mid
                else: lo_h, best = mid, r
        if best is None:
            raise SystemExit(f'no signature placement on {side}: relax dark_lum/margin or art offset')
        best['margin_mm'] = cfg['margin_mm']; best['on'] = ('flat broad face' + (', dark art (dilated lum < %.2f)' % cfg['dark_lum'] if cfg['dark_lum'] <= 1.0 else ''))
        placements[side] = best
        dbg = np.dstack([ok * 120, dark * 120, flat // 3]).astype(np.uint8)
        debug[side] = dbg
    # NB rows of grid are z ascending; flip for viewing
    for s, im in debug.items():
        cv2.imwrite(os.path.join(out, f'layout_{s}.png'), im[::-1])
    sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
    man = {'schema': 'jarambit.render.pro.prep.v1', 'toolchain': {'numpy': np.__version__, 'cv2': cv2.__version__, 'note': 'placements are cv2-version dependent at the 0.1 mm grid; pin cv2 per toolchain.lock'}, 'source': bundle['source'], 'bundle_npz_sha256': bundle['npz_sha256'],
           'out_npz_sha256': sha(os.path.join(out, 'mesh.npz')), 'config': cfg,
           'normal_repair': {'policy': 'render-only wall-normal smoothing; positions untouched',
                             'crease_deg': cfg['crease_deg'], 'wall_corners_changed': nchg,
                             'flat_crease_deg': cfg['flat_crease_deg'], 'flat_corners_changed': nchg_flat,
                             'flat_seam_qa': {'before': seam0, 'after': seam1, 'limit_deg': cfg['flat_seam_limit_deg'],
                                              'pass': seam1['max_deg'] <= cfg['flat_seam_limit_deg']}},
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
