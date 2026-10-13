#!/usr/bin/env python3
"""Key-component figures for WHITEPAPER (v0.32 release push, PR-0.32.0c). Author: Jepson Taylor.

For one design (STL + D1 json + RS-karambit-v2 eval json) the plan is partitioned into four key components:
  ring        nodes within R_ring = bore radius + 1.6*ring band of the ring-bore centre
  grip/spine  beyond the ring, up to grip length from the ring edge
  blade       the remaining sharpened curve, excluding the tip zone
  tip         nodes within 12 mm of the tip point (farthest node from the ring centre)
The ring-bore centre is the largest empty circle among the plate nodes in the ring end (grid search).
Per component one figure: (a) shaded 3D CAD view with the component highlighted, (b) plan FEM colormap of the
D1 certified envelope SF (100 C, joint; red < 1) zoomed to the component. Metrics (element SF min/mean,
area share, and the component's RS-karambit-v2 gate values) go to <out>/components.json; the WHITEPAPER table
is generated from that file by ops/ci/gen_whitepaper.py. Numbers are computed, never typed.

usage: components.py --stl S.stl --d1 D1.json --rsv2 evidence/rs_v2/X.json --out docs/figures/components"""
import argparse, hashlib, json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import turntable as tt  # noqa: E402

TIP_R = 12.0
ORDER = ['ring', 'grip_spine', 'blade', 'tip']
TITLE = {'ring': 'Finger ring (10)', 'grip_spine': 'Grip / spine (20)', 'blade': 'Blade, sharpened + serrated edges (30, 32)', 'tip': 'Tip zone (40)'}
GATES = {  # component -> RS-karambit-v2 eval keys (evidence/rs_v2/*.json)
    'ring': ['hm_ringback_sf', 'ring_bearing_w_mm', 'ring_band_mm', 'ring_rob_n'],
    'grip_spine': ['hm_spine_sf', 'twist_body_sf', 'fat_sf'],
    'blade': ['lat_rob_n', 'seq_ratio', 'hm_twist_sf'],
    'tip': ['hm_tip_inplane_sf', 'twist_tipzone_sf_strict', 'solid_tip_sf'],  # strict tip-sub = the locked gate value
}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def font(px):
    try:
        return ImageFont.truetype('DejaVuSans.ttf', px)
    except OSError:
        return ImageFont.load_default()


def ring_centre(xy):
    x0 = xy[:, 0].min(); sel = xy[xy[:, 0] < x0 + 45]
    gx, gy = np.meshgrid(np.linspace(sel[:, 0].min(), sel[:, 0].max(), 90), np.linspace(sel[:, 1].min(), sel[:, 1].max(), 90))
    g = np.c_[gx.ravel(), gy.ravel()]
    d = np.full(len(g), np.inf)
    for s in range(0, len(sel), 2000):
        d = np.minimum(d, np.sqrt(((g[:, None] - sel[None, s:s + 2000]) ** 2).sum(-1)).min(1))
    i = d.argmax(); return g[i], d[i]


def partition(pts, c, r_bore, band, grip, tip):
    r = np.linalg.norm(pts - c, axis=1); R = r_bore + 1.6 * band
    lab = np.where(r <= R, 0, np.where(r <= R + grip, 1, 2))
    lab[np.linalg.norm(pts - tip, axis=1) <= TIP_R] = 3
    return lab


def genome_fields(header, values):
    def num(x):
        try:
            return float(x)
        except ValueError:
            return x.strip()
    return {h.strip(): num(v) for h, v in zip(header, values)}


def same_design(d1, rs):
    """The RS-v2 record must be for exactly the D1 genome: identical gene/material column set (from cp00 on, no
    missing or extra fields, so a legacy CSV padded with defaults cannot match) and equal values, and the same mass."""
    import csv
    h, v = d1['genome_header'].split(','), d1['genome'].split(',')
    a = genome_fields(h[h.index('cp00'):], v[h.index('cp00'):])
    rows = list(csv.reader(open(os.path.join(ROOT, rs['genome']) if not os.path.isabs(rs['genome']) else rs['genome'])))
    if 'cp00' not in rows[0]:
        return False, ['no cp00 column']
    o = rows[0].index('cp00'); b = genome_fields(rows[0][o:], rows[1][o:])
    if set(a) != set(b):
        return False, sorted(set(a) ^ set(b))[:5]
    bad = [k for k in a if a[k] != b[k] and not (isinstance(a[k], float) and isinstance(b[k], float) and abs(a[k] - b[k]) <= 1e-9 * max(1.0, abs(a[k])))]
    if abs(d1['metrics']['mass_g'] - rs['mass_g']) > 0.01:
        bad.append(f'mass {rs["mass_g"]:.3f} g != D1 {d1["metrics"]["mass_g"]:.3f} g')
    return not bad, bad[:5]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--stl', required=True); ap.add_argument('--d1', required=True); ap.add_argument('--rsv2', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--width', type=int, default=2000); ap.add_argument('--height', type=int, default=900)
    a = ap.parse_args(argv)
    d = json.load(open(a.d1)); rs = json.load(open(a.rsv2)); m = d['mesh']; met = d['metrics']
    ok, bad = same_design(d, rs)
    if not ok:
        raise SystemExit(f'components: --rsv2 {a.rsv2} is not the D1 design {d["label"]} (genome fields differ: {bad})')
    stl_label = os.path.basename(a.stl)[:-4]
    if d['label'] not in (stl_label, stl_label + '_D1'):
        raise SystemExit(f'components: --stl {a.stl} does not name the D1 design {d["label"]}')
    xy = np.array(m['xy']); tr = np.array(m['tris']); sf = np.array(m['sf'], float)
    cen = xy[tr].mean(1)
    e1 = xy[tr[:, 1]] - xy[tr[:, 0]]; e2 = xy[tr[:, 2]] - xy[tr[:, 0]]
    a2 = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2
    c, r_bore = ring_centre(xy)
    tip = xy[np.linalg.norm(xy - c, axis=1).argmax()]
    lab = partition(cen, c, r_bore, rs['ring_band_mm'], met['grip'], tip)
    v = tt.load_stl(a.stl); fl = partition(v[:, :, :2].mean(1), c, r_bore, rs['ring_band_mm'], met['grip'], tip)
    os.makedirs(a.out, exist_ok=True)
    W, H = a.width, a.height; half = W // 2
    rel = lambda p: os.path.relpath(os.path.abspath(p), ROOT)
    comps = []
    base = np.array([0.55, 0.57, 0.60]); hi = np.array([0.95, 0.62, 0.20])
    for k, name in enumerate(ORDER):
        img = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(img)
        # (a) 3D CAD view, component highlighted
        col = np.where((fl == k)[:, None], hi, base)
        cam = tt.fit(v, [200.0], half, H)
        sub = tt.render(v, col, 200.0, half, H, '', None, cam)
        sub = Image.eval(sub, lambda p: p)  # dark background kept for contrast
        img.paste(sub, (0, 0))
        pan = Image.new('RGB', (half, H), 'white'); pdr = ImageDraw.Draw(pan)
        # (b) plan FEM colormap zoomed to component
        sel = lab == k; P = cen[sel]
        lo, hi2 = P.min(0) - 4, P.max(0) + 4
        s = min((half - 80) / (hi2[0] - lo[0]), (H - 260) / (hi2[1] - lo[1]))
        ox, oy = 40 - lo[0] * s + ((half - 80) - (hi2[0] - lo[0]) * s) / 2, 80 + hi2[1] * s
        val = np.clip(sf, 0, 3); rgb = tt.cmap((val - 1.0) / 2.0); rgb[val < 1.0] = [0.85, 0.15, 0.12]
        rgb[~sel] = rgb[~sel] * 0.25 + 0.75
        vis = np.all((xy[tr] >= lo - 6) & (xy[tr] <= hi2 + 6), axis=(1, 2))
        for i in np.where(vis)[0]:
            q = xy[tr[i]]; pdr.polygon([(ox + x * s, oy - y * s) for x, y in q], fill=tuple((rgb[i] * 255).astype(int)))
        img.paste(pan, (half, 0))
        f = font(30)
        dr.text((20, 16), '(a) 3D CAD view, component highlighted', fill=(230, 237, 243), font=f)
        dr.text((half + 40, 16), '(b) plan FEM: D1 certified envelope SF (100 C), red < 1', fill=(20, 20, 20), font=f)
        x0, y0, bw = half + 40, H - 70, 360
        ramp = (tt.cmap(np.linspace(0, 1, bw)) * 255).astype(int)
        for i in range(bw): dr.line([(x0 + i, y0), (x0 + i, y0 + 22)], fill=tuple(ramp[i]))
        dr.text((x0 + bw + 14, y0 - 4), 'SF 1 -> 3', fill=(20, 20, 20), font=f)
        dr.rectangle([x0 - 34, y0, x0 - 10, y0 + 22], fill=(217, 38, 31))
        smin = float(sf[sel].min()); smean = float(np.median(sf[sel]))
        dr.text((x0, y0 - 96), TITLE[name], fill=(20, 20, 20), font=f)
        dr.text((x0, y0 - 52), f'min element SF {smin:.3f}', fill=(20, 20, 20), font=f)
        fn = os.path.join(a.out, f'{d["label"]}_{name}.png'); img.save(fn, optimize=True)
        comps.append({'component': name, 'title': TITLE[name], 'figure': rel(fn), 'figure_sha256': sha(fn),
                      'n_elements': int(sel.sum()), 'area_share': float(a2[sel].sum() / a2.sum()),
                      'sf_min': smin, 'sf_median': smean, 'frac_area_sf_below_1': float(a2[sel & (sf < 1)].sum() / a2[sel].sum()),
                      'rs_v2': {g: rs[g] for g in GATES[name]}})
    out = {'schema': 1, 'script': 'ops/render/components.py', 'label': d['label'], 'requirement_set': rs['requirement_set'],
           'partition': {'ring_centre_mm': [float(c[0]), float(c[1])], 'bore_radius_est_mm': float(r_bore), 'tip_mm': [float(tip[0]), float(tip[1])], 'tip_radius_mm': TIP_R, 'grip_mm': met['grip'], 'ring_band_mm': rs['ring_band_mm']},
           'sf_field': 'D1 certified envelope SF (100 C, joint), plate tier', 'mass_g': rs['mass_g'], 'all_hard': rs['all_hard'],
           'inputs': {rel(p): sha(p) for p in (a.stl, a.d1, a.rsv2)}, 'components': comps}
    with open(os.path.join(a.out, 'components.json'), 'w') as fh:
        json.dump(out, fh, indent=1, sort_keys=True); fh.write('\n')
    print(json.dumps({c['component']: round(c['sf_min'], 3) for c in comps}))


if __name__ == '__main__':
    main()
