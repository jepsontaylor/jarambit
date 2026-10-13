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
    T = lambda s: int(round(s * fps)); n = 0
    log = {'schema': 'jarambit.render.pro.science_cut.v2', 'manifest_sha256': man['manifest_sha256'], 'stamp': man['stamp'],
           'fps': fps, 'size': [W, H], 'shots': [], 'text_qa': []}

    def emit(img, qa):
        nonlocal n
        Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, 'frames', f'f{n:05d}.png'))
        log['text_qa'].append({'frame': n, 'pass': qa['pass'], 'corner': qa.get('corner'), 'hits': qa['hits']}); n += 1

    for shot in man['science']:
        g, sh = shot['gate'], shot['shot']; tag = f'{sh}_{res}_{fin}'
        real = load(os.path.join(plates, tag + '.png'), size)
        wire = load(os.path.join(plates, f'{tag}_sci_{g}_wire.png'), size)
        heat = load(os.path.join(plates, f'{tag}_sci_{g}_heat.png'), size)
        knife = load_mask(os.path.join(plates, f'qa_idx_{tag}_0001.png'), size, 0.4, 0.6)
        sig = load_mask(os.path.join(plates, f'qa_sig_{tag}_0001.png'), size, 0.5, 2.0)
        realK = np.dstack([knife * 1.0] * 3)   # overlay.knife_mask thresholds luminance: hand it the object pass
        # lock one layout per shot at full extent (card complete + colorbar) so text never jumps between frames
        _, q0 = overlay.compose(heat, man, realK, sig, shot, 99.0, 1.0); L = [q0['layout']]
        C = lambda img, card_t=None, ha=0.0: overlay.compose(img, man, realK, sig, shot if card_t is not None else None, card_t, ha, corner_pref=L)
        x = np.linspace(0, 1, W)[None, :, None]; seq0 = n
        for i in range(T(1.0)): emit(*C(real))
        for i in range(T(1.0)):
            p = sm((i + 1) / T(1.0)); m = sm(np.clip((p * 1.25 - x) / 0.25, 0, 1)); emit(*C(real * (1 - m) + wire * m))
        for i in range(T(0.8)): emit(*C(wire))
        for i in range(T(1.0)):
            p = sm((i + 1) / T(1.0)); emit(*C(wire * (1 - p) + heat * p, i / fps, p))
        t0 = T(1.0) / fps
        for i in range(T(2.8)): emit(*C(heat, t0 + i / fps, 1.0))
        for i in range(T(1.0)):
            p = sm((i + 1) / T(1.0)); base = heat * (1 - p) + real * p
            withc, q = C(base, t0 + T(2.8) / fps + i / fps, 1.0 - p); noc, _ = C(base)
            emit(withc * (1 - p) + noc * p, q)
        for i in range(T(0.5)): emit(*C(real))
        # review stills
        st, q = C(heat, 9.0, 1.0); Image.fromarray((st * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, f'{man["stamp"]}_{g}_{sh}_heat_card.png'))
        st, q = C(wire); Image.fromarray((st * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, f'{man["stamp"]}_{g}_{sh}_wire.png'))
        log['shots'].append({'gate': g, 'shot': sh, 'frames': [seq0, n], 'test': shot['test'], 'SF': shot['SF'], 'verdict': shot['verdict']})
    for ex in [e for e in opt('--extra', '').split(',') if e]:
        sh, dur = ex.split(':'); tag = f'{sh}_{res}_{fin}'
        real = load(os.path.join(plates, tag + '.png'), size)
        knife = load_mask(os.path.join(plates, f'qa_idx_{tag}_0001.png'), size, 0.4, 0.6)
        sig = load_mask(os.path.join(plates, f'qa_sig_{tag}_0001.png'), size, 0.5, 2.0)
        seq0 = n
        try:
            img, q = overlay.compose(real, man, np.dstack([knife * 1.0] * 3), sig)
        except SystemExit as e:   # macro fills the frame: badge is skipped for this shot and recorded, not forced
            img, q = real, {'pass': True, 'corner': None, 'hits': [], 'note': f'badge omitted: {e}'}
        for i in range(T(float(dur))): emit(img, q)
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, f'{man["stamp"]}_{sh}.png'))
        log['shots'].append({'shot': sh, 'frames': [seq0, n], 'badge_note': q.get('note')})
    log['frames'] = n; log['text_qa_pass'] = all(x['pass'] for x in log['text_qa'])
    json.dump(log, open(os.path.join(out, f'{man["stamp"]}_science_cut.json'), 'w'), indent=1, ensure_ascii=False)
    if not log['text_qa_pass']: fail('text QA failed')
    mp4 = os.path.join(out, f'{man["stamp"]}_science_preview_{W}x{H}.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', os.path.join(out, 'frames', 'f%05d.png'),
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4], check=True)
    print('WROTE', mp4, n)


if __name__ == '__main__':
    main()
