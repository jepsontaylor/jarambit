"""Data-driven kinetic typography + persistent badge, composited over finished frames (pixel-crisp, never rendered
into the 3D plate). Every string comes from the design manifest (design_manifest.py); this module formats only.

Layout QA: the union of every drawn box (text, accent rules, colour bar, badge) must stay >= margin px from the
knife silhouette and from the signature (both derived from the frame's own plates). A layout that cannot be
placed is a hard failure, not a squeezed caption."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

INTER = '/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf'
FALLBACK = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
INFERNO = [(0.0, (0.0015, 0.0005, 0.0139)), (0.125, (0.0828, 0.0448, 0.2203)), (0.25, (0.2582, 0.0386, 0.4065)),
           (0.375, (0.4163, 0.0904, 0.4329)), (0.5, (0.5783, 0.148, 0.4044)), (0.625, (0.7357, 0.2161, 0.3302)),
           (0.75, (0.8650, 0.3168, 0.2261)), (0.875, (0.9545, 0.4686, 0.0998)), (1.0, (0.9884, 0.9984, 0.6449))]
ACCENT = (120, 190, 255)


def font(px, weight=300, path=INTER):
    try:
        f = ImageFont.truetype(path, int(px))
        try:
            f.set_variation_by_axes([min(32, max(14, px)), weight])
        except Exception:
            pass
        return f
    except OSError:
        return ImageFont.truetype(FALLBACK, int(px))


def ease(x):
    x = min(1.0, max(0.0, x)); return 1 - (1 - x) ** 3


def tracked(d, xy, text, f, fill, track):
    """Draw tracked-out caps; returns the bbox."""
    x, y = xy; x0 = x; top = bot = None
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        bb = d.textbbox((x, y), ch, font=f)
        top = bb[1] if top is None else min(top, bb[1]); bot = bb[3] if bot is None else max(bot, bb[3])
        x += d.textlength(ch, font=f) + track
    return [x0, top if top is not None else y, x - track, bot if bot is not None else y]


def text_width(d, text, f, track):
    return sum(d.textlength(ch, font=f) for ch in text) + track * max(0, len(text) - 1)


def fmt_num(v, ref):
    """Format a ticking counter with the same decimals as its final value string."""
    dec = len(ref.split('.')[1]) if '.' in ref else 0
    return f'{v:,.{dec}f}' if dec == 0 else f'{v:.{dec}f}'


def num_str(v):
    return f'{v:,.0f}' if abs(v - round(v)) < 1e-9 and v >= 100 else (f'{v:g}' if v < 100 else f'{v:,.0f}')


class Layout:
    def __init__(self, size):
        self.W, self.H = size; self.s = self.H / 1080.0; self.boxes = []

    def add(self, b, pad=0):
        self.boxes.append([int(b[0]) - pad, int(b[1]) - pad, int(b[2]) + pad, int(b[3]) + pad])


def draw_badge(d, lay, man, alpha=1.0, corner='tl'):
    s = lay.s; f = font(17 * s, 400); a = int(235 * alpha)
    text = man['badge'].upper()
    w = text_width(d, text, f, 2.2 * s)
    x = int(48 * s) if corner in ('tl', 'bl') else int(lay.W - 48 * s - w)
    y = int(40 * s) if corner in ('tl', 'tr') else int(lay.H - 58 * s)
    bb = tracked(d, (x, y), text, f, (235, 238, 245, a), 2.2 * s); lay.add(bb, int(6 * s))
    d.line([x, bb[3] + int(8 * s), x + int(36 * s), bb[3] + int(8 * s)], fill=ACCENT + (a,), width=max(1, int(2 * s)))
    return bb


def draw_science(d, lay, man, shot, t, anchor):
    """t = seconds since the data card starts. Line 1 (test · load) slides in, the accent rule draws on, then the
    counters tick to the manifest values, then the verdict lands."""
    s = lay.s; x, y = anchor
    f1 = font(40 * s, 250); f2 = font(30 * s, 300); f3 = font(30 * s, 300); fv = font(30 * s, 600)
    tr1, tr2 = 7.0 * s, 4.0 * s
    load = shot['load']; l1 = f"{shot['test']} · {num_str(load['value'])} {load['unit']}"
    a1 = ease(t / 0.45)
    bb1 = tracked(d, (x + int((1 - a1) * 24 * s), y), l1, f1, (250, 250, 252, int(255 * a1)), tr1); lay.add(bb1, int(8 * s))
    yl = bb1[3] + int(18 * s); wl = text_width(d, l1, f1, tr1)
    rule = ease((t - 0.25) / 0.6)
    if rule > 0:
        d.line([x, yl, x + int(wl * rule), yl], fill=ACCENT + (255,), width=max(1, int(2 * s)))
    lay.add([x, yl - 2, x + wl, yl + 2], int(4 * s))
    # PEAK counter
    y2 = yl + int(22 * s); a2 = ease((t - 0.6) / 0.3); k2 = ease((t - 0.6) / 1.1)
    peak = shot['peak_vm_MPa']; ps = f'{peak:.0f}'
    l2 = f"PEAK σvM {fmt_num(peak * k2, ps)} MPa"
    bb2 = tracked(d, (x, y2), l2, f2, (225, 230, 240, int(255 * a2)), tr2)
    lay.add([x, bb2[1], x + text_width(d, f"PEAK σvM {ps} MPa", f2, tr2), bb2[3]], int(8 * s))
    # SF counter + verdict
    y3 = bb2[3] + int(16 * s); a3 = ease((t - 1.1) / 0.3); k3 = ease((t - 1.1) / 1.1)
    sfs = f"{shot['SF']:.3f}"; l3 = f"SAFETY FACTOR {fmt_num(shot['SF'] * k3, sfs)}"
    bb3 = tracked(d, (x, y3), l3, f3, (225, 230, 240, int(255 * a3)), tr2)
    full3 = text_width(d, f"SAFETY FACTOR {sfs}", f3, tr2)
    av = ease((t - 2.25) / 0.35)
    vx = x + int(full3 + 22 * s)
    verdict = shot['verdict']; col = (120, 230, 160) if verdict == 'PASS' else (255, 110, 100)
    if av > 0:
        bbv = tracked(d, (vx, y3), '· ' + verdict, fv, col + (int(255 * av),), tr2)
    lay.add([x, bb3[1], vx + text_width(d, '· ' + verdict, fv, tr2), bb3[3]], int(8 * s))
    # small provenance line (manifest label, gate, Sy)
    f4 = font(15 * s, 400); a4 = ease((t - 2.4) / 0.4)
    l4 = (f"{man['label']} · solver output · gate ≥ {shot['gate_SF']:.3f} · Sy {man['Sy_MPa']:.0f} MPa · {man['status_note']}").upper()
    bb4 = tracked(d, (x, bb3[3] + int(22 * s)), l4, f4, (170, 178, 194, int(255 * a4)), 1.6 * s); lay.add(bb4, int(6 * s))
    return [x, y, max(bb1[2], bb4[2], vx), bb4[3]]


def cmap(t):
    xs = [p for p, _ in INFERNO]; cs = np.array([c for _, c in INFERNO])
    return np.stack([np.interp(t, xs, cs[:, k]) for k in range(3)], -1)


def draw_colorbar(ov, d, lay, man, shot, alpha, x_right):
    s = lay.s; a = int(255 * alpha); sy = man['Sy_MPa']
    bw, bh = int(14 * s), int(360 * s); bx = int(x_right - bw); by = int((lay.H - bh) / 2)
    t = np.linspace(1, 0, bh)[:, None].repeat(bw, 1); bar = (cmap(t) * 255).astype(np.uint8)
    ov.alpha_composite(Image.fromarray(np.dstack([bar, np.full(bar.shape[:2], a, np.uint8)]), 'RGBA'), (bx, by))
    f = font(14 * s, 400)
    ticks = [0, 200, 400, 600, sy]
    for v in ticks:
        yy = by + int((1 - v / sy) * (bh - 1))
        d.line([bx - int(6 * s), yy, bx, yy], fill=(220, 224, 234, a))
        lab = f'{v:.0f}' + (' YIELD' if v == sy else '')
        w = text_width(d, lab, f, 1.2 * s); tracked(d, (bx - int(10 * s) - w, yy - int(8 * s)), lab, f, (220, 224, 234, a), 1.2 * s)
    tracked(d, (bx - int(4 * s), by - int(30 * s)), 'MPa', f, (235, 238, 245, a), 1.2 * s)
    lay.add([bx - int(80 * s), by - int(34 * s), bx + bw, by + bh + int(8 * s)], int(6 * s))


def draw_colorbar_h(ov, d, lay, man, shot, alpha):
    """Horizontal scale, top-right: for wide framings where a vertical bar would cross the knife."""
    s = lay.s; a = int(255 * alpha); sy = man['Sy_MPa']
    bw, bh = int(320 * s), int(10 * s); bx = int(lay.W - 64 * s - bw); by = int(84 * s)
    t = np.linspace(0, 1, bw)[None, :].repeat(bh, 0); bar = (cmap(t) * 255).astype(np.uint8)
    ov.alpha_composite(Image.fromarray(np.dstack([bar, np.full(bar.shape[:2], a, np.uint8)]), 'RGBA'), (bx, by))
    f = font(14 * s, 400)
    for v in [v for v in (0, 200, 400, 600) if sy - v > 0.2 * sy] + [sy]:
        xx = bx + int(v / sy * (bw - 1)); d.line([xx, by + bh, xx, by + bh + int(6 * s)], fill=(220, 224, 234, a))
        lab = f'{v:.0f}' + (' YIELD' if v == sy else ''); w = text_width(d, lab, f, 1.2 * s)
        tracked(d, (min(xx - w // 2, bx + bw - w) if v == sy else xx - w // 2, by + bh + int(10 * s)), lab, f, (220, 224, 234, a), 1.2 * s)
    tracked(d, (bx, by - int(26 * s)), 'VON MISES  MPa', f, (235, 238, 245, a), 1.2 * s)
    lay.add([bx - int(20 * s), by - int(30 * s), bx + bw + int(4 * s), by + bh + int(30 * s)], int(6 * s))


def knife_mask(real_rgb, sig_mask=None, thr=0.06):
    L = real_rgb[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    m = L > thr
    return m, (sig_mask > 0.5) if sig_mask is not None else np.zeros_like(m)


def qa_layout(lay, knife, sig, margin_px):
    """Every overlay box must keep margin_px from the knife and the signature (dilated masks)."""
    import cv2
    k = cv2.dilate(knife.astype(np.uint8), np.ones((2 * margin_px + 1, 2 * margin_px + 1), np.uint8)) > 0
    sg = cv2.dilate(sig.astype(np.uint8), np.ones((2 * margin_px + 1, 2 * margin_px + 1), np.uint8)) > 0
    hits = []
    for b in lay.boxes:
        x0, y0, x1, y1 = max(0, b[0]), max(0, b[1]), min(lay.W, b[2]), min(lay.H, b[3])
        if x1 <= x0 or y1 <= y0:
            hits.append({'box': b, 'why': 'off-frame'}); continue
        if b[0] < 0 or b[1] < 0 or b[2] > lay.W or b[3] > lay.H:
            hits.append({'box': b, 'why': 'clipped by frame'})
        if k[y0:y1, x0:x1].any(): hits.append({'box': b, 'why': 'knife'})
        if sg[y0:y1, x0:x1].any(): hits.append({'box': b, 'why': 'signature'})
    return {'boxes': len(lay.boxes), 'margin_px': margin_px, 'hits': hits, 'pass': not hits}


def compose(frame, man, real_rgb, sig_mask, shot=None, t=None, heat_alpha=0.0, margin_mm_px=24, badge=True,
            corner_pref=('tl', 'tr', 'bl', 'br')):
    """frame: float RGB [0,1]. Tries anchors in order; returns (rgb, qa). Raises if nothing fits."""
    H, W = frame.shape[:2]; knife, sig = knife_mask(real_rgb, sig_mask)
    tries = []
    combos = [c if isinstance(c, tuple) else (c, cb) for c in corner_pref for cb in (('r', 'l', 'm', 'h') if not isinstance(c, tuple) else (None,))]
    combos = list(dict.fromkeys(combos))
    for corner, cbk in combos:
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); lay = Layout((W, H))
        if badge:
            draw_badge(d, lay, man, 1.0, {'tl': 'bl', 'tr': 'bl', 'bl': 'tl', 'br': 'tl'}[corner] if shot else 'bl')
        if shot is not None:
            s = lay.s
            ax = int(64 * s) if corner in ('tl', 'bl') else int(W * 0.56)
            ay = int(120 * s) if corner in ('tl', 'tr') else int(H - 300 * s)
            draw_science(d, lay, man, shot, t, (ax, ay))
            if heat_alpha > 0:
                (lambda: draw_colorbar_h(ov, d, lay, man, shot, heat_alpha)) () if cbk == 'h' else draw_colorbar(ov, d, lay, man, shot, heat_alpha, {'r': W - int(70 * s), 'l': int(150 * s), 'm': int(W * 0.5)}[cbk])
        q = qa_layout(lay, knife, sig, margin_mm_px); q['corner'] = corner; q['layout'] = (corner, cbk)
        tries.append(q)
        if q['pass']:
            base = Image.fromarray((np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8)).convert('RGBA'); base.alpha_composite(ov)
            return np.asarray(base.convert('RGB')).astype(np.float32) / 255.0, q
    raise SystemExit('overlay: FAIL: no layout keeps text clear of knife/signature: ' + str([(q['corner'], q['hits'][:2]) for q in tries]))
