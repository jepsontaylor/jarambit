"""Science-shot compositor: photoreal -> solver tet-mesh wire (wipe) -> von Mises heat map (dissolve) -> photoreal,
with the data card (overlay.py) and the persistent badge. All plates come from pro_hero.py with the SAME shot camera
(photoreal; --sci GATE --sci_mode wire|heat), so transitions are pixel-registered. Every number is read from the
design manifest; a missing plate/mask/manifest key is a hard failure.
python3 compose_sci.py PLATE_DIR DESIGN_MANIFEST.json OUT_DIR [--res hd] [--finish satin_blue] [--fps 30]
       [--size 1920x1080] [--extra 05_macro_signature:2.0]"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlay


def fail(msg):
    raise SystemExit(f'compose_sci: FAIL: {msg}')


def load(p, size):
    if not os.path.isfile(p): fail(f'missing plate {p}')
    im = Image.open(p).convert('RGB')
    if im.size != size: im = im.resize(size, Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def load_mask(p, size, lo, hi):
    if not os.path.isfile(p): fail(f'missing QA pass {p}')
    a = np.asarray(Image.open(p).convert('F').resize(size, Image.NEAREST)) / (65535.0 if Image.open(p).mode.startswith('I') else 255.0)
    return (a > lo) & (a < hi)


def sm(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)


def plate_paths(plates, sh, res, fin, gate=None):
    tag = f'{sh}_{res}_{fin}'
    d = {'real': os.path.join(plates, tag + '.png'), 'idx': os.path.join(plates, f'qa_idx_{tag}_0001.png'),
         'sig': os.path.join(plates, f'qa_sig_{tag}_0001.png')}
    if gate:
        d['wire'] = os.path.join(plates, f'{tag}_sci_{gate}_wire.png'); d['heat'] = os.path.join(plates, f'{tag}_sci_{gate}_heat.png')
    return d


def science_sequence(plates, man, shot, size, fps, res='hd', fin='satin_blue', timing=None):
    """Yield (frame float RGB, text-QA) for one data shot: photoreal -> wipe to the solver tet wire -> dissolve to the
    von Mises field (card + scale animate in) -> back to photoreal. One text layout is locked per shot."""
    W, H = size; g, sh = shot['gate'], shot['shot']; P = plate_paths(plates, sh, res, fin, g)
    tm = {'real_in': 1.0, 'wipe': 1.0, 'wire': 0.8, 'dissolve': 1.0, 'heat': 2.8, 'back': 1.0, 'real_out': 0.5, **(timing or {})}
    real, wire, heat = load(P['real'], size), load(P['wire'], size), load(P['heat'], size)
    knife = load_mask(P['idx'], size, 0.4, 0.6); sig = load_mask(P['sig'], size, 0.5, 2.0)
    _, q0 = overlay.compose(heat, man, real, sig, shot, 99.0, 1.0, knife=knife); L = [q0['layout']]
    def C(img, card_t=None, ha=0.0):
        return overlay.compose(img, man, real, sig, shot if card_t is not None else None, card_t, ha,
                               corner_pref=L if card_t is not None else ('tl', 'tr', 'bl', 'br'), knife=knife)
    T = lambda k: int(round(tm[k] * fps)); x = np.linspace(0, 1, W)[None, :, None]
    for i in range(T('real_in')): yield C(real)
    for i in range(T('wipe')):
        p = sm((i + 1) / T('wipe')); m = sm(np.clip((p * 1.25 - x) / 0.25, 0, 1)); yield C(real * (1 - m) + wire * m)
    for i in range(T('wire')): yield C(wire)
    for i in range(T('dissolve')):
        p = sm((i + 1) / T('dissolve')); yield C(wire * (1 - p) + heat * p, i / fps, p)
    t0 = T('dissolve') / fps
    for i in range(T('heat')): yield C(heat, t0 + i / fps, 1.0)
    t1 = t0 + T('heat') / fps
    for i in range(T('back')):
        p = sm((i + 1) / T('back')); base = heat * (1 - p) + real * p
        withc, q = C(base, t1 + i / fps, 1.0 - p); noc, _ = C(base)
        yield withc * (1 - p) + noc * p, q
    for i in range(T('real_out')): yield C(real)


def save(img, path):
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def main():
    a = sys.argv[1:]
    plates, man_p, out = a[0], a[1], a[2]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    res = opt('--res', 'hd'); fin = opt('--finish', 'satin_blue'); fps = int(opt('--fps', '30'))
    W, H = map(int, opt('--size', '1920x1080').split('x')); size = (W, H)
    man = json.load(open(man_p))
    for k in ('badge', 'label', 'Sy_MPa', 'science', 'stamp'):
        if k not in man: fail(f'manifest missing {k}')
    os.makedirs(os.path.join(out, 'frames'), exist_ok=True)
    log = {'schema': 'jarambit.render.pro.science_cut.v2', 'manifest_sha256': man['manifest_sha256'], 'stamp': man['stamp'],
           'fps': fps, 'size': [W, H], 'shots': [], 'text_qa': []}; n = 0
    for shot in man['science']:
        seq0 = n; frames = []
        for img, q in science_sequence(plates, man, shot, size, fps, res, fin):
            save(img, os.path.join(out, 'frames', f'f{n:05d}.png')); frames.append(img) if len(frames) < 1 else None
            log['text_qa'].append({'frame': n, 'pass': q['pass'], 'corner': q.get('corner'), 'hits': q['hits']}); n += 1
            if n - seq0 == int(round(7.2 * fps)): save(img, os.path.join(out, f'{man["stamp"]}_{shot["gate"]}_{shot["shot"]}_heat_card.png'))
            if n - seq0 == int(round(2.5 * fps)): save(img, os.path.join(out, f'{man["stamp"]}_{shot["gate"]}_{shot["shot"]}_wire.png'))
        log['shots'].append({'gate': shot['gate'], 'shot': shot['shot'], 'frames': [seq0, n], 'test': shot['test'], 'SF': shot['SF'], 'verdict': shot['verdict']})
    log['frames'] = n; log['text_qa_pass'] = all(x['pass'] for x in log['text_qa'])
    json.dump(log, open(os.path.join(out, f'{man["stamp"]}_science_cut.json'), 'w'), indent=1, ensure_ascii=False)
    if not log['text_qa_pass']: fail('text QA failed')
    print('WROTE', out, n)


if __name__ == '__main__':
    main()
