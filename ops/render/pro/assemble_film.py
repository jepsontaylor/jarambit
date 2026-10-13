"""Assemble the v2 cut: photoreal film frames + registered solver-mesh / von Mises passes for the data turntable,
typewriter data card, and the weight badge on EVERY frame, with per-frame text QA. 16-bit in, 16-bit PNG out.

python3 assemble_film.py FILM_DIR WIRE_DIR HEAT_DIR DESIGN_MANIFEST FILM_JSON RECIPE OUT_SEQ ASSEMBLY_JSON [--size WxH]"""
import json, os, sys
import cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlay


def fail(m):
    raise SystemExit(f'assemble_film: FAIL: {m}')


def rd(p, size):
    if not os.path.isfile(p): fail(f'missing {p}')
    a = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if a is None: fail(f'unreadable {p}')
    a = a[..., :3][..., ::-1].astype(np.float32) / (65535.0 if a.dtype == np.uint16 else 255.0)
    return cv2.resize(a, size, interpolation=cv2.INTER_AREA) if (a.shape[1], a.shape[0]) != size else a


def rd_mask(p, size, lo, hi):
    if not os.path.isfile(p): fail(f'missing QA pass {p}')
    a = cv2.imread(p, cv2.IMREAD_UNCHANGED).astype(np.float32)
    a = a / (65535.0 if a.max() > 255 else 255.0)
    if a.ndim == 3: a = a[..., 0]
    a = cv2.resize(a, size, interpolation=cv2.INTER_NEAREST)
    return (a > lo) & (a < hi)


def sm(x):
    x = np.clip(x, 0.0, 1.0); return x * x * (3 - 2 * x)


def main():
    a = sys.argv[1:]
    film, wire, heat, man_p, film_p, rec_p, out, asm_p = a[:8]
    man = json.load(open(man_p)); F = json.load(open(film_p)); R = json.load(open(rec_p))
    size = tuple(map(int, a[a.index('--size') + 1].split('x'))) if '--size' in a else tuple(R['size'])
    fps = F['fps']; TL = F['science_timeline_s']; gain = float(R.get('sci_gain', 1.0))
    sci_by_gate = {s['gate']: s for s in man['science']}
    os.makedirs(out, exist_ok=True)
    real_p = lambda f: os.path.join(film, f'f{f:05d}.png')
    sig_p = lambda d, f: os.path.join(d, f'qa_sig_f{f:05d}_0001.png')
    idx_p = lambda d, f: os.path.join(d, f'qa_idx_f{f:05d}_0001.png')
    log = {'schema': 'jarambit.render.pro.assembly.v2', 'manifest_sha256': man['manifest_sha256'], 'stamp': man['stamp'],
           'film': F['title'], 'fps': fps, 'size': list(size), 'sci_gain': gain, 'shots': [], 'frames_qa': []}
    for S in F['shots']:
        f0, f1 = S['frames']; sci = S['common'].get('science'); g = S['common'].get('sci_case')
        shot = sci_by_gate.get(g) if sci else None
        if sci and shot is None: fail(f'{S["name"]}: manifest has no data shot {g}')
        # lock layouts per shot from the union of the knife / signature masks over the shot
        samp = sorted(set(list(range(f0, f1, 6)) + [f1 - 1]))
        Ku = np.zeros(size[::-1], bool); Su = np.zeros(size[::-1], bool)
        for f in samp:
            Ku |= rd_mask(idx_p(film, f), size, 0.4, 0.6); Su |= rd_mask(sig_p(film, f), size, 0.5, 2.0)
        blank = np.zeros(size[::-1] + (3,), np.float32)
        badge_corner, backing, card_layout = None, 0.0, None
        for bc in ('bl', 'br', 'tl', 'tr'):
            try:
                _, q = overlay.compose_v2(blank, man, np.zeros_like(Ku), Su, badge_corner=bc)
                badge_corner = bc; break
            except SystemExit:
                continue
        if badge_corner is None: fail(f'{S["name"]}: the weight badge cannot avoid the signature in any corner')
        bx0, by0, bx1, by1 = q['badge_box']
        if Ku[max(0, by0):by1, max(0, bx0):bx1].any(): backing = 0.55   # macro frames: badge over metal -> dark plate
        if sci:
            cues = TL['cues']
            _, q = overlay.compose_v2(blank, man, Ku, Su, card=(shot, 99.0, cues, 1.0), heat_alpha=1.0, gain=gain,
                                      badge_corner=badge_corner, badge_backing=backing)
            card_layout = tuple(q['layout'])
        log['shots'].append({'name': S['name'], 'frames': [f0, f1], 'badge_corner': badge_corner, 'badge_backing': backing,
                             'card_layout': card_layout, 'data': (shot['gate'] if shot else None)})
        for f in range(f0, f1):
            real = rd(real_p(f), size); K = rd_mask(idx_p(film, f), size, 0.4, 0.6); Sg = rd_mask(sig_p(film, f), size, 0.5, 2.0)
            card = None; ha = 0.0; img = real
            if sci:
                t = (f - f0) / fps
                w_wire = sm((t - TL['real_to_wire'][0]) / (TL['real_to_wire'][1] - TL['real_to_wire'][0]))
                w_heat = sm((t - TL['wire_to_heat'][0]) / (TL['wire_to_heat'][1] - TL['wire_to_heat'][0]))
                w_back = sm((t - TL['heat_to_real'][0]) / (TL['heat_to_real'][1] - TL['heat_to_real'][0]))
                W_ = rd(os.path.join(wire, f'f{f:05d}.png'), size) if w_wire > 0 and w_back < 1 else None
                H_ = rd(os.path.join(heat, f'f{f:05d}.png'), size) if w_heat > 0 and w_back < 1 else None
                data = real if W_ is None else real * (1 - w_wire) + W_ * w_wire
                if H_ is not None: data = data * (1 - w_heat) + H_ * w_heat
                img = data * (1 - w_back) + real * w_back
                ha = w_heat * (1 - w_back)
                fade = 1.0 - sm((t - TL['text_fade'][0]) / (TL['text_fade'][1] - TL['text_fade'][0]))
                card = (shot, t, TL['cues'], fade) if fade > 0 else None
            o, q = overlay.compose_v2(img, man, K, Sg, card=card, heat_alpha=ha, gain=gain, layout=card_layout,
                                      badge_corner=badge_corner, badge_backing=backing)
            q16 = (np.clip(o, 0, 1) * 65535 + 0.5).astype(np.uint16)[..., ::-1]
            cv2.imwrite(os.path.join(out, f'f{f:05d}.png'), q16)
            log['frames_qa'].append({'frame': f, 'shot': S['name'], 'badge_present': q['badge_present'], 'badge_box': q['badge_box'],
                                     'sig_px': int(Sg.sum()), 'pass': q['pass'], 'hits': q['hits']})
        print('assembled', S['name'], flush=True)
    log['frames'] = len(log['frames_qa'])
    log['text_qa_pass'] = all(x['pass'] and x['badge_present'] for x in log['frames_qa'])
    json.dump(log, open(asm_p, 'w'), indent=1, ensure_ascii=False)
    if not log['text_qa_pass']: fail('per-frame text QA failed')
    print('ASSEMBLED', log['frames'])


if __name__ == '__main__':
    main()
