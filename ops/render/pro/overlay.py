"""Data-driven kinetic typography + persistent badge, composited over finished frames (pixel-crisp, never rendered
into the 3D plate). Every string comes from the design manifest (design_manifest.py); this module formats only.

Layout QA: the union of every drawn box (text, accent rules, colour bar, badge) must stay >= margin px from the
knife silhouette and from the signature (both derived from the frame's own plates). A layout that cannot be
placed is a hard failure, not a squeezed caption."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import os
INTER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'Inter-VariableFont_opsz,wght.ttf')  # vendored, OFL-1.1
INFERNO = [(0.0, (0.0015, 0.0005, 0.0139)), (0.125, (0.0828, 0.0448, 0.2203)), (0.25, (0.2582, 0.0386, 0.4065)),
           (0.375, (0.4163, 0.0904, 0.4329)), (0.5, (0.5783, 0.148, 0.4044)), (0.625, (0.7357, 0.2161, 0.3302)),
           (0.75, (0.8650, 0.3168, 0.2261)), (0.875, (0.9545, 0.4686, 0.0998)), (1.0, (0.9884, 0.9984, 0.6449))]
ACCENT = (120, 190, 255)


def font(px, weight=300, path=INTER):
    if not os.path.isfile(path):
        raise SystemExit(f'overlay: FAIL: font {path} missing (no silent fallback: the type is part of the look)')
    f = ImageFont.truetype(path, int(px))
    f.set_variation_by_axes([min(32, max(14, px)), weight])   # opsz, wght
    return f


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


def cmap_gain(t, gain=1.0):
    """Legend colours exactly as the heat plate renders them: inferno stops are sRGB, the plate interpolates them
    in LINEAR light, multiplies by the emission gain, and the Standard view transform encodes back to sRGB."""
    if gain == 1.0 and False: return cmap(t)
    xs = [p for p, _ in INFERNO]; cs = np.array([c for _, c in INFERNO])
    lin = np.where(cs > 0.04045, ((cs + 0.055) / 1.055) ** 2.4, cs / 12.92)
    v = np.stack([np.interp(t, xs, lin[:, k]) for k in range(3)], -1) * gain; v = np.clip(v, 0, 1)
    return np.where(v > 0.0031308, 1.055 * v ** (1 / 2.4) - 0.055, 12.92 * v)


def cmap(t):
    xs = [p for p, _ in INFERNO]; cs = np.array([c for _, c in INFERNO])
    return np.stack([np.interp(t, xs, cs[:, k]) for k in range(3)], -1)


def draw_colorbar(ov, d, lay, man, shot, alpha, x_right, gain=1.0):
    s = lay.s; a = int(255 * alpha); sy = man['Sy_MPa']
    bw, bh = int(14 * s), int(360 * s); bx = int(x_right - bw); by = int((lay.H - bh) / 2)
    t = np.linspace(1, 0, bh)[:, None].repeat(bw, 1); bar = (cmap_gain(t, gain) * 255).astype(np.uint8)
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


def draw_colorbar_h(ov, d, lay, man, shot, alpha, gain=1.0, right=True):
    """Horizontal scale, top-right: for wide framings where a vertical bar would cross the knife."""
    s = lay.s; a = int(255 * alpha); sy = man['Sy_MPa']
    bw, bh = int(320 * s), int(10 * s); bx = int(lay.W - 64 * s - bw) if right else int(64 * s); by = int(84 * s)
    t = np.linspace(0, 1, bw)[None, :].repeat(bh, 0); bar = (cmap_gain(t, gain) * 255).astype(np.uint8)
    ov.alpha_composite(Image.fromarray(np.dstack([bar, np.full(bar.shape[:2], a, np.uint8)]), 'RGBA'), (bx, by))
    f = font(14 * s, 400)
    for v in [v for v in (0, 200, 400, 600) if sy - v > 0.3 * sy] + [sy]:
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
            corner_pref=('tl', 'tr', 'bl', 'br'), knife=None):
    """frame: float RGB [0,1]. Tries anchors in order; returns (rgb, qa). Raises if nothing fits.
    knife: optional precomputed bool mask (object-index pass or a per-shot union); else luminance of real_rgb."""
    H, W = frame.shape[:2]; k_l, sig = knife_mask(real_rgb, sig_mask); knife = k_l if knife is None else knife
    tries = []
    combos = [c if isinstance(c, tuple) else (c, cb) for c in corner_pref for cb in ((('r', 'l', 'm', 'h') if shot is not None else (None,)) if not isinstance(c, tuple) else (None,))]
    combos = list(dict.fromkeys(combos))
    for corner, cbk in combos:
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); lay = Layout((W, H))
        if badge:
            draw_badge(d, lay, man, 1.0, {'tl': 'bl', 'tr': 'bl', 'bl': 'tl', 'br': 'tl'}[corner] if shot else {'tl': 'bl', 'tr': 'tl', 'bl': 'tr', 'br': 'br'}[corner])
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


# ======================================================================================================
# v2 (owner 10:45): typewriter reveal + a large weight badge on EVERY frame.
# ======================================================================================================
import random, zlib

COMMON = {'THE', 'OF', 'AND', 'SF', 'PEAK', 'SAFETY', 'FACTOR', 'SPINE', 'STRIKE', 'PASS', 'SOLVER', 'MESH', 'TETS',
          'NODES', 'PRY', 'TWIST', 'HANDLE', 'REV', 'GATE'}


def type_schedule(text, seed_extra=''):
    """Reveal time (s, from the line's start) of every character: a deterministic model of a fast human typist.
    ~60-90 ms/char with jitter, longer pause after a space / separator, a slight burst inside common words,
    numbers a bit slower, rare micro-hesitations. Seeded from the text so every render is identical."""
    rng = random.Random(zlib.crc32((text + '|' + seed_extra).encode()))
    words = []; cur = ''
    for ch in text:   # word membership per char
        cur = cur + ch if ch.isalnum() else ''
        words.append(cur)
    out, t = [], 0.0
    toks = text.replace('·', ' ').split()
    common_chars = set()
    pos = 0
    for tok in text.split(' '):
        if tok.strip('·,').upper() in COMMON: common_chars.update(range(pos, pos + len(tok)))
        pos += len(tok) + 1
    for i, ch in enumerate(text):
        dt = rng.uniform(0.060, 0.090)
        if ch.isdigit() or ch in '.,':
            dt *= 1.28
        if i in common_chars:
            dt *= 0.72
        prev = text[i - 1] if i else ''
        if prev == ' ':
            dt += rng.uniform(0.06, 0.11)
        if prev == '·' or ch == '·':
            dt += rng.uniform(0.10, 0.16)
        if rng.random() < 0.05:
            dt += rng.uniform(0.05, 0.12)
        t += dt if i else 0.0
        out.append(t)
    return out


def draw_typed(d, xy, text, f, fill, track, t, s, cursor_hold=1.0):
    """Draw the typed prefix at time t (s since the line started). Newest glyph gets a ~45 ms key-strike settle
    (drops in 2 px + brief brightness); a block cursor sits after the last glyph (solid while typing, blinks
    after, gone cursor_hold s after the line completes). Returns (bbox of the FULL line, done_time)."""
    sched = type_schedule(text); x0, y = xy
    full = [x0, y, x0 + int(text_width(d, text, f, track)), y + int(f.size * 1.05)]
    if t < 0: return full, sched[-1]
    x = x0; last_x = x0; n_vis = sum(1 for tt in sched if tt <= t)
    for i, ch in enumerate(text[:n_vis]):
        age = t - sched[i]; k = max(0.0, 1.0 - age / 0.045)
        col = tuple(min(255, int(c * (1 + 0.18 * k))) for c in fill[:3]) + (fill[3],)
        d.text((x, y + int(2 * s * k)), ch, font=f, fill=col)
        x += d.textlength(ch, font=f) + track; last_x = x
    done = sched[-1]; typing = n_vis < len(text)
    show = typing or (t - done) < cursor_hold
    blink_on = typing or int((t - done) / 0.53) % 2 == 0
    if show and blink_on:
        asc, desc = f.getmetrics(); cw = max(2, int(f.size * 0.55))
        d.rectangle([last_x + int(2 * s), y + int(asc * 0.18), last_x + int(2 * s) + cw, y + asc], fill=fill[:3] + (int(fill[3] * 0.85),))
    full[2] = max(full[2], x0 + int(text_width(d, text, f, track)) + int(f.size * 0.7))
    return full, done


def weight_badge(d, lay, man, corner='bl', backing=None):
    """Large, always-on weight badge: '64.8 g' (unit prominent) + version line. Strings from the manifest."""
    s = lay.s
    mass = f"{man['mass_g']:.1f}"; unit = 'g'
    fN = font(64 * s, 300); fU = font(64 * s, 500); fL = font(16 * s, 400)
    sub = f"{man['family']} {man['label']} · {man['material']} Ti".upper()
    wN = text_width(d, mass, fN, 1.0 * s); wU = text_width(d, unit, fU, 1.0 * s); wL = text_width(d, sub, fL, 2.4 * s)
    W_ = max(wN + int(12 * s) + wU, wL); H_ = int(64 * s * 1.22) + int(22 * s)
    x = int(52 * s) if corner in ('tl', 'bl') else int(lay.W - 52 * s - W_)
    y = int(44 * s) if corner in ('tl', 'tr') else int(lay.H - 52 * s - H_)
    box = [int(x - 18 * s), int(y - 12 * s), int(x + W_ + 18 * s), int(y + H_ + 12 * s)]
    if backing:
        d.rounded_rectangle(box, radius=int(10 * s), fill=(6, 8, 12, int(255 * backing)))
    tracked(d, (x, y), mass, fN, (248, 249, 252, 255), 1.0 * s)
    tracked(d, (x + wN + int(12 * s), y), unit, fU, ACCENT + (255,), 1.0 * s)
    tracked(d, (x + 2, y + int(64 * s * 1.22)), sub, fL, (205, 212, 226, 240), 2.4 * s)
    lay.add(box, 0)
    return box


def science_lines(man, shot):
    """(start_s, role, text) for one data turntable. Start times are keyed to the visuals (see timeline):
    the load at the photoreal open, the mesh line when the solver mesh fades in, PEAK / SF when the field does."""
    load = shot['load']; mesh = man['fem']['mesh']
    need_keys = [k for k in ('nodes', 'tets') if k not in mesh]
    if need_keys: raise SystemExit(f'overlay: FAIL: manifest fem.mesh lacks {need_keys}')
    return [
        ('load', f"{shot['test']} · {num_str(load['value'])} {load['unit']}"),
        ('mesh', f"MESH · {mesh['tets']:,} TETS"),
        *([('peak', f"PEAK σvM {shot['peak_vm_MPa']:.0f} MPa"), ('sf', f"SF {shot['SF']:.3f} · {shot['verdict']}")]
          if shot.get('certification', {}).get('status', 'of record') == 'of record' else
          [('peak', f"PEAK σvM {shot['solver_peak_vm_MPa']:.0f} MPa*"),
           ('sf', f"SF {shot['solver_SF']:.2f}* · OPEN")]),
        ('prov', (f"{man['label']} · solver output · gate SF ≥ {shot['gate_SF']:.3f} · Sy {man['Sy_MPa']:.0f} MPa · {man['status_note']}").upper()
                 if shot.get('certification', {}).get('status', 'of record') == 'of record' else
                 (f"{man['label']} · *solver value · cert. {shot['certification']['status']} ({shot['certification'].get('ref', '')}) · Sy {man['Sy_MPa']:.0f} MPa").upper())]


def draw_science_typed(d, lay, man, shot, t, anchor, cues, fade=1.0):
    s = lay.s; x, y = anchor; a = int(255 * fade)
    L = dict((r, txt) for r, txt in science_lines(man, shot))
    spec = {'load': (font(40 * s, 250), 6.0 * s, (250, 250, 252)), 'mesh': (font(20 * s, 350), 3.2 * s, (150, 200, 255)),
            'peak': (font(30 * s, 300), 4.0 * s, (235, 238, 245)), 'sf': (font(30 * s, 300), 4.0 * s, (235, 238, 245)),
            'prov': (font(14 * s, 400), 1.6 * s, (170, 178, 194))}
    yy = y; boxes = []
    for role in ('load', 'mesh', 'peak', 'sf', 'prov'):
        f, tr, col = spec[role]; txt = L[role]
        if role == 'sf' and shot['verdict'] == 'FAIL': col = (255, 120, 110)
        if role == 'sf' and shot['verdict'] not in ('PASS', 'FAIL'): col = (240, 200, 120)   # open / unresolved: amber, no pass claim
        if role == 'prov':
            k = ease((t - cues['prov']) / 0.5); bb = tracked(d, (x, yy), txt, f, col + (int(a * k),), tr) if k > 0 else [x, yy, x + int(text_width(d, txt, f, tr)), yy + f.size]
            bb = [x, yy, x + int(text_width(d, txt, f, tr)), yy + int(f.size * 1.05)]; done = 0
        else:
            bb, done = draw_typed(d, (x, yy), txt, f, col + (a,), tr, t - cues[role], s)
        lay.add(bb, int(6 * s)); boxes.append(bb)
        if role == 'load':   # accent rule draws on after the line completes
            yl = bb[3] + int(14 * s); k = ease((t - cues['load'] - done) / 0.5)
            if k > 0: d.line([x, yl, x + int((bb[2] - x - f.size * 0.7) * k), yl], fill=ACCENT + (a,), width=max(1, int(2 * s)))
            lay.add([x, yl - 2, bb[2], yl + 2], int(4 * s)); yy = yl + int(18 * s)
        else:
            yy = bb[3] + int({'mesh': 14, 'peak': 10, 'sf': 18, 'prov': 0}[role] * s)
    return boxes


def compose_v2(frame, man, knife, sig, card=None, heat_alpha=0.0, gain=1.0, margin_px=24, layout=None,
               badge_corner='bl', badge_backing=0.0):
    """frame float RGB; knife/sig bool masks for THIS frame. card = (shot, t, cues, fade) or None.
    The weight badge is drawn on every frame. Text QA:
      * badge: present (inside frame) and >= margin from the signature (it may sit over the knife on macro frames,
        on a dark backing plate, but never over the mark);
      * card + scale: >= margin from knife and signature.
    layout = (corner, colorbar) locks the card layout for a whole shot. Returns (rgb, qa); raises if nothing fits."""
    H, W = frame.shape[:2]
    import cv2
    dil = lambda m: cv2.dilate(m.astype(np.uint8), np.ones((2 * margin_px + 1, 2 * margin_px + 1), np.uint8)) > 0
    K, S = dil(knife), dil(sig)
    corners = [layout] if layout else [(c, cb) for c in ('tl', 'tr') for cb in ('h', 'r', 'l')]
    tries = []
    for corner, cbk in corners:
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov); lay = Layout((W, H))
        bcorner = badge_corner
        bbox = weight_badge(d, lay, man, bcorner, badge_backing)
        hits = []
        x0, y0, x1, y1 = bbox
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H: hits.append({'what': 'badge', 'why': 'clipped by frame'})
        if S[max(0, y0):y1, max(0, x0):x1].any(): hits.append({'what': 'badge', 'why': 'signature'})
        nb = len(lay.boxes); over_knife = []
        if card is not None:
            shot, t, cues, fade = card; s = lay.s
            ax = int(64 * s) if corner == 'tl' else int(W * 0.52); ay = int(56 * s)
            draw_science_typed(d, lay, man, shot, t, (ax, ay), cues, fade)
            if heat_alpha > 0:
                if cbk == 'h': draw_colorbar_h(ov, d, lay, man, shot, heat_alpha * fade, gain=gain, right=(corner == 'tl'))
                else: draw_colorbar(ov, d, lay, man, shot, heat_alpha * fade, {'r': W - int(70 * s), 'l': int(150 * s)}[cbk], gain=gain)
            for b in lay.boxes[nb:]:
                bx0, by0, bx1, by1 = max(0, b[0]), max(0, b[1]), min(W, b[2]), min(H, b[3])
                if b[0] < 0 or b[1] < 0 or b[2] > W or b[3] > H: hits.append({'what': 'card', 'box': b, 'why': 'clipped by frame'})
                if bx1 > bx0 and by1 > by0:
                    if K[by0:by1, bx0:bx1].any(): over_knife.append(b)   # spin: knife sweeps the card -> dark backing plate (never over the mark)
                    if S[by0:by1, bx0:bx1].any(): hits.append({'what': 'card', 'box': b, 'why': 'signature'})
                    if bbox[0] < bx1 and bx0 < bbox[2] and bbox[1] < by1 and by0 < bbox[3]: hits.append({'what': 'card', 'box': b, 'why': 'badge'})
        q = {'badge_present': True, 'badge_box': bbox, 'hits': hits, 'pass': not hits, 'layout': (corner, cbk), 'margin_px': margin_px,
             'card_backing': len(over_knife)}
        if over_knife and not hits:
            pad = int(8 * lay.s); bx = (min(b[0] for b in lay.boxes[nb:]) - pad, min(b[1] for b in lay.boxes[nb:]) - pad,
                                     max(b[2] for b in lay.boxes[nb:]) + pad, max(b[3] for b in lay.boxes[nb:]) + pad)
            bk = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(bk).rounded_rectangle(bx, radius=int(10 * lay.s), fill=(6, 8, 12, 150))
            if S[max(0, bx[1]):bx[3], max(0, bx[0]):bx[2]].any(): hits.append({'what': 'card_backing', 'box': bx, 'why': 'signature'}); q['pass'] = False
            else: ov = Image.alpha_composite(bk, ov)
        tries.append(q)
        if q['pass']:
            o = np.asarray(ov).astype(np.float32) / 255.0; al = o[..., 3:4]
            out = frame[..., :3] * (1 - al) + o[..., :3] * al   # float (16-bit-safe) 'over' in display space
            return out, q
    raise SystemExit('overlay: FAIL (v2): ' + json.dumps([(q['layout'], q['hits'][:3]) for q in tries]))


import json
