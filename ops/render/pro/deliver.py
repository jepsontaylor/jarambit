"""Deliverables from rendered stills: 16-bit PNG (lossless master copy), 8-bit RGB PNG for chat (< 25 MB,
blue-noise-like dither), 100 % signature crop (16-bit PNG, from the `sig` AOV bbox), small JPG thumbnail.
python deliver.py RENDER_DIR OUT_DIR"""
import glob, json, os, sys, hashlib
import numpy as np
from PIL import Image
import cv2

src, dst = sys.argv[1:3]; os.makedirs(dst, exist_ok=True)
rng = np.random.default_rng(20261013)


def blue_noise(h, w):
    """High-passed white noise (Gaussian difference) normalised to a uniform +-0.5 LSB distribution."""
    n = rng.random((h, w)).astype(np.float32)
    hp = n - cv2.GaussianBlur(n, (0, 0), 1.2)
    r = hp.ravel().argsort().argsort().reshape(h, w).astype(np.float32) / (h * w)
    return r - 0.5


sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
man = []
for qa_p in sorted(glob.glob(os.path.join(src, '*.qa.json'))):
    qa = json.load(open(qa_p))
    if qa.get('status') != 'RENDERED': continue
    tag = qa['shot']; png = qa['png']
    im16 = cv2.imread(png, cv2.IMREAD_UNCHANGED)[:, :, ::-1].astype(np.float32)   # RGB, 0..65535
    out16 = os.path.join(dst, tag + '_16bit.png'); cv2.imwrite(out16, im16[:, :, ::-1].astype(np.uint16))
    h, w = im16.shape[:2]
    v8 = im16 / 257.0 + blue_noise(h, w)[:, :, None]
    im8 = np.clip(np.round(v8), 0, 255).astype(np.uint8)
    out8 = os.path.join(dst, tag + '_8bit.png'); Image.fromarray(im8).save(out8, optimize=True)
    if os.path.getsize(out8) > 25e6:   # 8K: halve with Lanczos for the chat copy
        Image.fromarray(im8).resize((w // 2, h // 2), Image.LANCZOS).save(out8, optimize=True)
    Image.fromarray(im8).resize((640, int(640 * h / w)), Image.LANCZOS).save(os.path.join(dst, tag + '_thumb.jpg'), quality=92)
    rec = {'shot': tag, 'png16': out16, 'png8': out8, 'png8_mb': round(os.path.getsize(out8) / 1e6, 2), 'qa': qa_p}
    sig = glob.glob(os.path.join(src, f'qa_sig_{tag}_*.png'))
    if sig:
        m = cv2.imread(sig[0], cv2.IMREAD_UNCHANGED).astype(np.float32); m = m / m.max() if m.max() else m
        ys, xs = np.where(m > 0.2)
        if len(ys):
            pad = int(0.15 * max(xs.ptp(), ys.ptp())) + 16
            y0, y1 = max(0, ys.min() - pad), min(h, ys.max() + pad); x0, x1 = max(0, xs.min() - pad), min(w, xs.max() + pad)
            touches = ys.min() <= 1 or xs.min() <= 1 or ys.max() >= h - 2 or xs.max() >= w - 2
            crop = os.path.join(dst, tag + '_sigcrop100.png')
            cv2.imwrite(crop, im16[y0:y1, x0:x1, ::-1].astype(np.uint16))
            rec.update(sigcrop=crop, sig_bbox_px=[int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                       sig_aov_touches_border=bool(touches))
    rec['png16_sha256'] = sha(out16)
    man.append(rec); print(json.dumps(rec))
json.dump(man, open(os.path.join(dst, 'deliverables.json'), 'w'), indent=1)
