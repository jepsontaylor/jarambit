#!/usr/bin/env python3
"""Automatic blade / coat masks for any jarambit CAD mesh bundle (host Python: numpy + PIL).

Zones per face (uint8):  0 COAT (finish allowed)  1 BLADE_FLAT  2 BEVEL  3 EDGE_APEX  4 SERRATION
Zones 1-4 are the "blade side" and are NEVER coated.

Edge-zone sources (both are always computed; labels win when present and they agree):
  labels    : region_id from regions.json/NPZ (bevel, edge_apex, serration)  -- ddc9a30 B-rep labels
  geometric : thin-section apex (all 3 vertices within apex_band of the stock mid-plane) +
              grind faces (normal tilted bevel_min..bevel_max deg from the blade-plane normal) that
              are connected to an apex face (handle chamfers never reach the mid-plane -> excluded)
Blade flats: 2-D footprint test in the blade plane: a non-edge face is blade if, along the local
cross-blade direction, edge-zone pixels lie on BOTH sides within max_flat_mm through solid material
(i.e. it is sandwiched between the two grinds), then a guard band (guard_mm) is grown around the
edge zone so the coating line stops short of the grind shoulder.
Also writes per-vertex arc parameters  s in [0,1] (ring/butt -> tip along the knife's centre curve)
and t in [-1,1] (signed across-width) so finishes can follow the arc.
Validation fails loudly (exit 3) unless every check passes (or --allow-warn).
"""
import argparse, hashlib, json, os, sys
import numpy as np
from PIL import Image, ImageDraw

LABELS = ['body', 'bevel', 'edge_apex', 'serration', 'ring', 'pad', 'spine']
ZONE_NAMES = ['coat', 'blade_flat', 'bevel', 'edge_apex', 'serration']
EDGE_LABEL_ZONE = {'bevel': 2, 'edge_apex': 3, 'serration': 4}
ZONE_RGB = [(70, 150, 255), (255, 210, 40), (255, 120, 30), (255, 0, 60), (220, 40, 200)]


def load_mesh(bundle_path, regions_path=None):
    b = json.load(open(bundle_path))
    d = os.path.dirname(os.path.abspath(bundle_path))
    npz = np.load(os.path.join(d, b.get('npz', 'mesh.npz')))
    mesh = {k: npz[k] for k in npz.files}
    labels_src = 'none'
    if 'region_id' in mesh:
        labels_src = 'npz'
    if regions_path and os.path.isfile(regions_path):
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from region_io import apply_region_overrides
            m2 = apply_region_overrides(mesh, regions_path, b.get('npz_sha256'))
            if m2 is not mesh:
                labels_src = 'regions_v2_override'
            mesh = m2
        except ImportError:
            pass
        rj = json.load(open(regions_path))
        names = rj.get('labels')
        if names:
            mesh['_label_names'] = [names[str(i)] for i in range(len(names))]
    mesh.setdefault('_label_names', LABELS)
    return b, mesh, labels_src


def plane_frame(V):
    c = V.mean(0)
    w, ax = np.linalg.eigh(np.cov((V - c).T))
    n = ax[:, 0]                      # thinnest axis = blade-plane normal
    u = ax[:, 2]                      # longest axis
    v = np.cross(n, u)
    return c, u, v, n


def face_adjacency(F):
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    fid = np.tile(np.arange(len(F)), 3)
    e.sort(1)
    key = e[:, 0].astype(np.int64) * (F.max() + 1) + e[:, 1]
    o = np.argsort(key)
    k, f = key[o], fid[o]
    same = k[1:] == k[:-1]
    return f[:-1][same], f[1:][same]


def components(mask, a, b):
    """connected components of faces in mask (union-find over shared edges)."""
    par = np.arange(len(mask))
    sel = mask[a] & mask[b]
    a, b = a[sel], b[sel]
    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for i, j in zip(a, b):
        ri, rj = find(i), find(j)
        if ri != rj:
            par[ri] = rj
    return np.array([find(i) for i in range(len(mask))])


def geometric_edge(V, F, fn, c, n, p):
    h = (V - c) @ n
    mid = np.median(h)
    thin_v = np.abs(h - mid) < p['apex_band_mm'] * 1e-3
    apex = thin_v[F].all(1)
    tilt = np.degrees(np.arccos(np.clip(np.abs(fn @ n), 0, 1)))
    cand = ((tilt > p['bevel_min_deg']) & (tilt < p['bevel_max_deg'])) | apex
    a, b = face_adjacency(F)
    comp = components(cand, a, b)
    keep = np.isin(comp, np.unique(comp[apex])) & cand
    return keep, apex


def raster(P2, F, sel, lo, res_m, shape):
    im = Image.new('L', shape, 0)
    d = ImageDraw.Draw(im)
    q = (P2 - lo) / res_m
    for f in np.nonzero(sel)[0]:
        t = q[F[f]]
        d.polygon([tuple(t[0]), tuple(t[1]), tuple(t[2])], fill=255)
    return np.asarray(im) > 0          # [row=v, col=u]


def sandwiched(E, S, max_px):
    """pixel is blade-flat if, scanning +v and -v (columns), it hits edge pixels within max_px
    while staying inside solid S."""
    H, W = E.shape
    up = np.full((H, W), 10 ** 6); dn = np.full((H, W), 10 ** 6)
    cur = np.full(W, 10 ** 6)
    for r in range(H):
        cur = np.where(E[r], 0, np.where(S[r], cur + 1, 10 ** 6)); up[r] = cur
    cur = np.full(W, 10 ** 6)
    for r in range(H - 1, -1, -1):
        cur = np.where(E[r], 0, np.where(S[r], cur + 1, 10 ** 6)); dn[r] = cur
    return (up <= max_px) & (dn <= max_px) & S


def dilate(M, r):
    from PIL import ImageFilter
    im = Image.fromarray((M * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1))
    return np.asarray(im) > 0


def arc_params(V, P2, S, lo, res_m, s0_hint):
    H, W = S.shape
    cols = np.nonzero(S.any(0))[0]
    zc = np.array([np.nonzero(S[:, j])[0].mean() for j in cols])
    hw = np.array([(np.ptp(np.nonzero(S[:, j])[0]) + 1) / 2 for j in cols])
    k = 15
    zc = np.convolve(np.pad(zc, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
    hw = np.convolve(np.pad(hw, k, mode='edge'), np.ones(2 * k + 1) / (2 * k + 1), 'valid')
    poly = np.stack([cols + 0.5, zc + 0.5], 1) * res_m + lo
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(poly, axis=0), axis=1))]
    s = seg / seg[-1]
    if s0_hint is not None and np.linalg.norm(poly[-1] - s0_hint) < np.linalg.norm(poly[0] - s0_hint):
        s = 1 - s
    # nearest polyline sample per vertex (chunked)
    sv = np.empty(len(P2)); tv = np.empty(len(P2))
    for i in range(0, len(P2), 4096):
        q = P2[i:i + 4096]
        d = ((q[:, None, :] - poly[None]) ** 2).sum(-1)
        j = d.argmin(1)
        sv[i:i + 4096] = s[j]
        tv[i:i + 4096] = (q[:, 1] - poly[j, 1]) / np.maximum(hw[j] * res_m, 1e-6)
    return sv, np.clip(tv, -1.5, 1.5), float(seg[-1])


def compute(bundle_path, regions_path=None, out_dir='.', params=None, allow_warn=False):
    p = {'apex_band_mm': 0.3, 'bevel_min_deg': 8.0, 'bevel_max_deg': 80.0, 'raster_mm': 0.1,
         'max_flat_mm': 30.0, 'guard_mm': 0.6, 'wall_mm': 0.6, 'tip_guard_mm': 6.0, 'tip_check_mm': 10.0, 'blade_frac_range': [0.12, 0.65]}
    p.update(params or {})
    os.makedirs(out_dir, exist_ok=True)
    bundle, mesh, labels_src = load_mesh(bundle_path, regions_path)
    V = np.asarray(mesh['V'], float); F = np.asarray(mesh['F'], np.int64)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    area = np.linalg.norm(fn, axis=1) / 2
    fn /= np.maximum(2 * area, 1e-300)[:, None]
    c, u, v, n = plane_frame(V)
    P2 = np.stack([(V - c) @ u, (V - c) @ v], 1)
    geo_edge, geo_apex = geometric_edge(V, F, fn, c, n, p)
    names = mesh['_label_names']
    zone = np.zeros(len(F), np.uint8)
    method = 'geometric'
    label_iou = None
    if 'region_id' in mesh and any(k in names for k in EDGE_LABEL_ZONE):
        rid = np.asarray(mesh['region_id'])
        lab_edge = np.zeros(len(F), bool)
        for lab, z in EDGE_LABEL_ZONE.items():
            if lab in names:
                m = rid == names.index(lab); zone[m] = z; lab_edge |= m
        inter = area[lab_edge & geo_edge].sum(); uni = area[lab_edge | geo_edge].sum()
        label_iou = float(inter / max(uni, 1e-30))
        method = 'labels'
        if label_iou < 0.5:
            method = 'labels_disagree'
    apex_label_cov = None
    if method != 'labels':
        zone[:] = 0; zone[geo_edge] = 2; zone[geo_apex] = 3
    else:
        # safety union: geometric grind/apex faces the labels missed are made bare too (err toward bare)
        apex_label_cov = float(area[geo_apex & (zone >= 2)].sum() / max(area[geo_apex].sum(), 1e-30))
        zone[(zone == 0) & geo_edge] = 2
        zone[(zone == 0) & geo_apex] = 3
    edge = zone >= 2
    # footprint raster
    lo = P2.min(0) - 1e-3; hi = P2.max(0) + 1e-3
    r = p['raster_mm'] * 1e-3
    shape = (int((hi[0] - lo[0]) / r) + 1, int((hi[1] - lo[1]) / r) + 1)
    S = raster(P2, F, np.ones(len(F), bool), lo, r, shape)
    E = raster(P2, F, edge, lo, r, shape)
    B = sandwiched(E, S, int(p['max_flat_mm'] / p['raster_mm']))
    B |= dilate(E, int(round(p['guard_mm'] / p['raster_mm']))) & S
    B &= ~E
    # face lookup (centroid pixel) for non-edge faces
    cen2 = P2[F].mean(1)
    ij = np.clip(((cen2 - lo) / r).astype(int), 0, np.array(shape) - 1)
    flat = B[ij[:, 1], ij[:, 0]] & ~edge
    # only faces lying on the blade flats or walls between grinds; never pad/ring labels
    if method == 'labels':
        rid = np.asarray(mesh['region_id'])
        for lab in ('ring', 'pad'):
            if lab in names:
                flat &= rid != names.index(lab)
    zone[flat] = 1
    # perimeter walls / spine / point faces lying on the blade outline (sandwich test cannot see them:
    # their centroids sit ON the outline). Any non-pad/ring face whose centroid lies within wall_mm of the
    # blade footprint and whose normal is near-perpendicular to the blade plane is bare (bevel finish).
    tilt = np.degrees(np.arccos(np.clip(np.abs(fn @ n), 0, 1)))
    Bfoot = dilate(B | E, max(1, int(round(p['wall_mm'] / p['raster_mm'])))) 
    wall = (zone == 0) & (tilt > p['bevel_max_deg'] - 10) & Bfoot[ij[:, 1], ij[:, 0]]
    if 'region_id' in mesh:
        rid = np.asarray(mesh['region_id'])
        for lab in ('ring', 'pad'):
            if lab in names:
                wall &= rid != names.index(lab)
    zone[wall] = 2
    hint = None
    if 'region_id' in mesh and 'ring' in names and (np.asarray(mesh['region_id']) == names.index('ring')).any():
        rid = np.asarray(mesh['region_id'])
        hint = cen2[rid == names.index('ring')].mean(0)
    else:  # butt = end farthest from the edge zone centroid
        ec = cen2[edge].mean(0) if edge.any() else cen2.mean(0)
        ends = [P2[P2[:, 0].argmin()], P2[P2[:, 0].argmax()]]
        hint = max(ends, key=lambda e: np.linalg.norm(e - ec))
    sv, tv, arc_len = arc_params(V, P2, S, lo, r, hint)
    # point guard: everything within tip_guard_mm (3-D) of the point is bare, whatever the labels say
    tip = V[np.argmax(sv)]
    cen3 = V[F].mean(1)
    near_tip = np.linalg.norm(cen3 - tip, axis=1) < p['tip_guard_mm'] * 1e-3
    tip_forced = int(((zone == 0) & near_tip).sum())
    zone[(zone == 0) & near_tip] = 2
    blade = zone > 0
    # ---------------- validation
    tot = area.sum()
    frac = {z: float(area[zone == i].sum() / tot) for i, z in enumerate(ZONE_NAMES)}
    blade_frac = 1 - frac['coat']
    side = np.sign(fn @ n)
    checks = {
        'edge_zone_nonempty': bool(edge.any()),
        'blade_frac_in_range': p['blade_frac_range'][0] <= blade_frac <= p['blade_frac_range'][1],
        'all_thin_apex_in_blade': bool(blade[geo_apex].all()) if geo_apex.any() else False,
        'flats_both_sides': bool(area[(zone == 1) & (side > 0.9)].sum() > 0 and area[(zone == 1) & (side < -0.9)].sum() > 0),
        'coat_area_ok': frac['coat'] > 0.2,
        'tip_region_bare': bool((zone[np.linalg.norm(cen3 - tip, axis=1) < p['tip_check_mm'] * 1e-3] > 0).all()),
        'labels_agree_geometry': (label_iou is None) or label_iou >= 0.5,
    }
    warnings = [] if (apex_label_cov is None or apex_label_cov >= 0.9) else [
        f'labels cover only {apex_label_cov:.0%} of thin-section apex faces; geometric faces unioned into blade (bare)']
    ok = all(checks.values())
    rep = {'schema': 'jarambit.finish.blade_mask.v1', 'bundle': os.path.abspath(bundle_path),
           'npz_sha256': bundle.get('npz_sha256'), 'regions': regions_path, 'labels_source': labels_src,
           'method': method, 'label_vs_geometric_edge_iou': label_iou, 'thin_apex_area_covered_by_labels': apex_label_cov, 'area_frac': frac,
           'blade_frac': blade_frac, 'tip_point_m': tip.tolist(), 'tip_faces_forced_bare': tip_forced, 'wall_faces_bare': int(wall.sum()), 'arc_length_mm': arc_len * 1e3, 'params': p, 'checks': checks, 'warnings': warnings, 'ok': ok}
    zpath = os.path.join(out_dir, 'finish_masks.npz')
    np.savez_compressed(zpath, zone=zone, s=sv.astype(np.float32), t=tv.astype(np.float32))
    rep['masks_npz'] = zpath
    rep['masks_sha256'] = hashlib.sha256(open(zpath, 'rb').read()).hexdigest()
    debug_png(P2, F, fn, n, zone, lo, r, shape, sv, os.path.join(out_dir, 'blade_mask_2d.png'), rep)
    json.dump(rep, open(os.path.join(out_dir, 'blade_mask.json'), 'w'), indent=1)
    print(json.dumps({k: rep[k] for k in ('method', 'label_vs_geometric_edge_iou', 'blade_frac', 'checks', 'ok')}))
    if not ok and not allow_warn:
        sys.stderr.write(f'BLADE MASK VALIDATION FAILED: {[k for k, v in checks.items() if not v]}\n')
        sys.exit(3)
    return rep


def debug_png(P2, F, fn, n, zone, lo, r, shape, sv, path, rep):
    from PIL import ImageFont
    rows = []
    side = fn @ n
    for name, sel in (('front (+n)', side > 0.1), ('back (-n)', side < -0.1)):
        im = Image.new('RGB', shape, (20, 22, 28)); d = ImageDraw.Draw(im)
        q = (P2 - lo) / r
        order = np.nonzero(sel)[0]
        for f in order:
            t = q[F[f]]
            d.polygon([tuple(t[0]), tuple(t[1]), tuple(t[2])], fill=ZONE_RGB[zone[f]])
        im = im.transpose(Image.FLIP_TOP_BOTTOM)
        if name.startswith('back'):
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        ImageDraw.Draw(im).text((10, 10), name, fill=(255, 255, 255))
        rows.append(im)
    # arc param s
    im = Image.new('RGB', shape, (20, 22, 28)); d = ImageDraw.Draw(im); q = (P2 - lo) / r
    for f in np.nonzero(side > 0.1)[0]:
        t = q[F[f]]; s = sv[F[f]].mean()
        d.polygon([tuple(t[0]), tuple(t[1]), tuple(t[2])], fill=(int(255 * s), 60, int(255 * (1 - s))))
    im = im.transpose(Image.FLIP_TOP_BOTTOM); ImageDraw.Draw(im).text((10, 10), 'arc parameter s (blue=0 butt, red=1 tip)', fill=(255, 255, 255))
    rows.append(im)
    W, H = shape
    sheet = Image.new('RGB', (W, H * 3 + 60), (12, 12, 14))
    for i, im in enumerate(rows):
        sheet.paste(im, (0, i * H))
    d = ImageDraw.Draw(sheet)
    x = 10
    for zn, rgb in zip(ZONE_NAMES, ZONE_RGB):
        d.rectangle([x, 3 * H + 15, x + 20, 3 * H + 35], fill=rgb)
        d.text((x + 26, 3 * H + 20), zn + (' (COATED)' if zn == 'coat' else ' (bare)'), fill=(230, 230, 230)); x += 260
    d.text((x, 3 * H + 20), f"method={rep['method']} blade={rep['blade_frac']:.1%} iou={rep['label_vs_geometric_edge_iou']} ok={rep['ok']}", fill=(230, 230, 230))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bundle', required=True); ap.add_argument('--regions'); ap.add_argument('--out', required=True)
    ap.add_argument('--allow-warn', action='store_true'); ap.add_argument('--force-geometric', action='store_true')
    a = ap.parse_args()
    if a.force_geometric:
        global EDGE_LABEL_ZONE
        EDGE_LABEL_ZONE = {}
    compute(a.bundle, a.regions, a.out, allow_warn=a.allow_warn)


if __name__ == '__main__':
    main()
