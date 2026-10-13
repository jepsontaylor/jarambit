#!/usr/bin/env python3
"""Finishing: scene-linear EXR -> one OCIO display transform -> 16-bit sRGB PNG (+ JPEG web copy),
plus the mask-aware image metrics that qa.py consumes (Q4 clipping, Q5 crushed blacks, Q7 noise,
Q8 flicker/fireflies, Q9 loop seam) and the colour helpers for Q6 (sRGB <-> Lab, CIEDE2000).

Display transform: Blender 4.2's bundled OCIO config, display 'sRGB', view 'AgX', look
'AgX - Medium High Contrast' (one view, recorded). Resizing happens in linear light (OIIO lanczos3)
before the display transform. Exposure (EV) is applied in linear light before the view.

OpenImageIO/PyOpenColorIO come from Blender's bundled Python; when this file runs under a host
Python without them, the CLI re-executes itself with Blender's Python (found via $JARAMBIT_BLENDER
or ~/opt/blender-4.2*/). The numpy-only metric functions import fine anywhere.

usage:
  finish.py png  IN.exr OUT.png [--size 1920x1080] [--jpeg OUT.jpg --quality 92] [--view AgX]
                 [--look "AgX - Medium High Contrast"] [--exposure 0] [--record OUT.json]
  finish.py stats IMG.png --mask MASK.exr [--json]
  finish.py contact OUT.jpg IMG1.png IMG2.png ... [--cols 3 --width 640]
  finish.py npy IMG OUT.npy
"""
import argparse
import glob
import hashlib
import json
import os
import sys

import numpy as np

VIEW = 'AgX'
LOOK = 'AgX - Medium High Contrast'
DISPLAY = 'sRGB'
SCENE_LINEAR = 'Linear Rec.709'


# ---------------------------------------------------------------- toolchain discovery
def blender_dir():
    env = os.environ.get('JARAMBIT_BLENDER')
    if env:
        d = env if os.path.isdir(env) else os.path.dirname(env)
        if os.path.isfile(os.path.join(d, 'blender')):
            return d
        raise FileNotFoundError(f'JARAMBIT_BLENDER={env} has no blender binary')
    c = sorted(glob.glob(os.path.expanduser('~/opt/blender-4.2*/blender')))
    if not c:
        raise FileNotFoundError('Blender 4.2 LTS not found (set JARAMBIT_BLENDER or install to ~/opt/blender-4.2*/)')
    return os.path.dirname(c[-1])


def blender_bin():
    return os.path.join(blender_dir(), 'blender')


def blender_python():
    c = sorted(glob.glob(os.path.join(blender_dir(), '*', 'python', 'bin', 'python3*')))
    c = [p for p in c if os.path.basename(p) != 'python3-config']
    if not c:
        raise FileNotFoundError('Blender bundled python not found')
    return c[-1]


def ocio_config_path():
    c = glob.glob(os.path.join(blender_dir(), '*', 'datafiles', 'colormanagement', 'config.ocio'))
    if not c:
        raise FileNotFoundError('Blender OCIO config not found')
    return c[0]


def have_oiio():
    try:
        import OpenImageIO  # noqa: F401
        import PyOpenColorIO  # noqa: F401
        return True
    except ImportError:
        return False


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- image I/O + display (needs OIIO/OCIO)
def read_image(path):
    import OpenImageIO as oiio
    inp = oiio.ImageInput.open(path)
    if inp is None:
        raise IOError(f'cannot open {path}: {oiio.geterror()}')
    spec = inp.spec()
    px = np.asarray(inp.read_image(format='float'), np.float32).reshape(spec.height, spec.width, spec.nchannels)
    inp.close()
    return px


def resize_linear(img, w, h):
    """Lanczos3 resize in linear light (OIIO)."""
    import OpenImageIO as oiio
    src = oiio.ImageBuf(np.ascontiguousarray(img, np.float32))
    roi = oiio.ROI(0, w, 0, h, 0, 1, 0, img.shape[2])
    dst = oiio.ImageBufAlgo.resize(src, filtername='lanczos3', roi=roi)
    return np.asarray(dst.get_pixels(oiio.FLOAT), np.float32).reshape(h, w, img.shape[2])


def processor(view=VIEW, look=LOOK, display=DISPLAY):
    import PyOpenColorIO as ocio
    cfg = ocio.Config.CreateFromFile(ocio_config_path())
    t = ocio.DisplayViewTransform(src=SCENE_LINEAR, display=display, view=view)
    pipe = ocio.LegacyViewingPipeline()
    pipe.setDisplayViewTransform(t)
    if look:
        pipe.setLooksOverrideEnabled(True)
        pipe.setLooksOverride(look)
    return pipe.getProcessor(cfg).getDefaultCPUProcessor()


def to_display(rgb_lin, view=VIEW, look=LOOK, exposure_ev=0.0):
    """Scene-linear Rec.709 (H,W,3) -> display-referred sRGB-encoded floats in [0,1]."""
    a = np.ascontiguousarray(rgb_lin[..., :3], np.float32) * np.float32(2.0 ** exposure_ev)
    flat = a.reshape(-1, 3).copy()
    processor(view, look).applyRGB(flat)
    return np.clip(flat.reshape(a.shape), 0.0, 1.0)


def write_image(path, disp, bits=16, quality=92):
    import OpenImageIO as oiio
    h, w, c = disp.shape
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        arr = np.round(disp * 255).astype(np.uint8)
        spec = oiio.ImageSpec(w, h, c, oiio.UINT8)
        spec.attribute('Compression', f'jpeg:{int(quality)}')
    elif bits == 16:
        arr = np.round(disp * 65535).astype(np.uint16)
        spec = oiio.ImageSpec(w, h, c, oiio.UINT16)
    else:
        arr = np.round(disp * 255).astype(np.uint8)
        spec = oiio.ImageSpec(w, h, c, oiio.UINT8)
    spec.attribute('oiio:ColorSpace', 'sRGB')
    tmp = path + '.tmp' + ext
    out = oiio.ImageOutput.create(tmp)
    if out is None or not out.open(tmp, spec):
        raise IOError(f'cannot write {path}: {oiio.geterror()}')
    out.write_image(np.ascontiguousarray(arr))
    out.close()
    os.replace(tmp, path)
    return path


def finish_exr(exr, png, size=None, jpeg=None, quality=92, view=VIEW, look=LOOK, exposure_ev=0.0):
    img = read_image(exr)
    rgb = img[..., :3]
    if size and (rgb.shape[1], rgb.shape[0]) != tuple(size):
        rgb = resize_linear(rgb, *size)
    disp = to_display(rgb, view, look, exposure_ev)
    write_image(png, disp, 16)
    rec = {'in': exr, 'in_sha256': sha256(exr), 'png': png, 'png_sha256': sha256(png),
           'size': [int(disp.shape[1]), int(disp.shape[0])], 'display': DISPLAY, 'view': view, 'look': look,
           'exposure_ev': exposure_ev, 'resize': 'oiio lanczos3 (linear light)' if size else None}
    if jpeg:
        write_image(jpeg, disp, quality=quality)
        rec.update({'jpeg': jpeg, 'jpeg_sha256': sha256(jpeg), 'jpeg_quality': quality})
    return rec, disp


# ---------------------------------------------------------------- metrics (numpy only)
def to_u8(disp):
    d = np.asarray(disp, np.float64)
    if d.dtype.kind in 'ui' or d.max() > 1.0 + 1e-6:
        d = d / (65535.0 if d.max() > 255 else 255.0)
    return np.round(np.clip(d, 0, 1) * 255).astype(np.uint8)


def mask_stats(disp, mask, thr=0.5):
    """Q4/Q5 on the product mask: fraction of masked pixels with any channel at 255 (clip) and at 0
    (crush), measured on the 8-bit display encoding."""
    u8 = to_u8(disp)[..., :3]
    m = np.asarray(mask, np.float64)
    if m.ndim == 3:
        m = m[..., 0]
    if m.shape != u8.shape[:2]:
        raise ValueError(f'mask {m.shape} vs image {u8.shape[:2]}')
    sel = m > thr
    n = int(sel.sum())
    out = {'mask_px': n, 'mask_frac': n / sel.size}
    if n == 0:
        out.update({'clip_frac': None, 'crush_frac': None})
        return out
    px = u8[sel]
    out['clip_frac'] = float((px == 255).any(1).mean())
    out['crush_frac'] = float((px == 0).any(1).mean())
    bg = u8[~sel]
    out['bg_clip_frac'] = float((bg == 255).any(1).mean()) if len(bg) else None
    out['bg_crush_frac'] = float((bg == 0).all(1).mean()) if len(bg) else None
    lum = px.astype(np.float64) @ [0.2126, 0.7152, 0.0722]
    out['product_luma_p01_p50_p99'] = [float(np.percentile(lum, q)) for q in (1, 50, 99)]
    return out


def q4_q5(stats, specular_apex=False, allow_bg_black=False):
    clip_lim = 0.002 if specular_apex else 0.0005
    return {'Q4': 'PASS' if stats['clip_frac'] is not None and stats['clip_frac'] <= clip_lim else 'FAIL',
            'Q4_limit': clip_lim,
            'Q5': 'PASS' if stats['crush_frac'] is not None and stats['crush_frac'] <= 0.005 else 'FAIL',
            'Q5_limit': 0.005}


def highpass_residual(img, box=5):
    """Q7: std of (img - box blur) / mean on a flat patch (luminance)."""
    y = np.asarray(img, np.float64)
    if y.ndim == 3:
        y = y[..., :3] @ [0.2126, 0.7152, 0.0722]
    k = box
    p = np.pad(y, k // 2, mode='reflect')
    c = np.cumsum(np.cumsum(p, 0), 1)
    c = np.pad(c, ((1, 0), (1, 0)))
    blur = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)
    r = y - blur
    return float(r.std() / max(y.mean(), 1e-12))


def _median3(y):
    p = np.pad(y, 1, mode='edge')
    st = np.stack([p[i:i + y.shape[0], j:j + y.shape[1]] for i in range(3) for j in range(3)])
    return np.median(st, 0)


def fireflies(img, factor=8.0, floor=1e-3):
    """Q8: count of pixels brighter than factor x their 3x3 local median (luminance)."""
    y = np.asarray(img, np.float64)
    if y.ndim == 3:
        y = y[..., :3] @ [0.2126, 0.7152, 0.0722]
    med = _median3(y)
    return int((y > factor * np.maximum(med, floor)).sum())


def flicker(frames, region_mask):
    """Q8: std/mean of mean luminance of a static region across consecutive frames."""
    m = np.asarray(region_mask) > 0.5
    v = []
    for f in frames:
        y = np.asarray(f, np.float64)
        if y.ndim == 3:
            y = y[..., :3] @ [0.2126, 0.7152, 0.0722]
        v.append(y[m].mean())
    v = np.asarray(v)
    return float(v.std() / max(v.mean(), 1e-12))


def ssim(a, b, L=1.0):
    """Global-window SSIM on luminance (enough for seam/regression checks)."""
    def lum(x):
        x = np.asarray(x, np.float64)
        return x[..., :3] @ [0.2126, 0.7152, 0.0722] if x.ndim == 3 else x
    x, y = lum(a), lum(b)
    c1, c2 = (0.01 * L) ** 2, (0.03 * L) ** 2
    mx, my = x.mean(), y.mean()
    vx, vy, cov = x.var(), y.var(), ((x - mx) * (y - my)).mean()
    return float((2 * mx * my + c1) * (2 * cov + c2) / ((mx * mx + my * my + c1) * (vx + vy + c2)))


# ---------------------------------------------------------------- colour (Q6)
def srgb_to_linear(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0, None)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


M_RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                      [0.0193339, 0.1191920, 0.9503041]])
WHITE_D65 = np.array([0.95047, 1.0, 1.08883])


def srgb_to_lab(rgb):
    xyz = srgb_to_linear(rgb) @ M_RGB2XYZ.T / WHITE_D65
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def delta_e2000(lab1, lab2):
    L1, a1, b1 = np.moveaxis(np.asarray(lab1, np.float64), -1, 0)
    L2, a2, b2 = np.moveaxis(np.asarray(lab2, np.float64), -1, 0)
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh) / 2)
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    hs = h1p + h2p
    hbp = np.where(C1p * C2p == 0, hs,
                   np.where(np.abs(h1p - h2p) <= 180, hs / 2, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2)))
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dth = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dth)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


# X-Rite ColorChecker Classic (post-2014 formulation), widely published sRGB D65 8-bit values.
COLORCHECKER_SRGB8 = [
    (115, 82, 68), (194, 150, 130), (98, 122, 157), (87, 108, 67), (133, 128, 177), (103, 189, 170),
    (214, 126, 44), (80, 91, 166), (193, 90, 99), (94, 60, 108), (157, 188, 64), (224, 163, 46),
    (56, 61, 150), (70, 148, 73), (175, 54, 60), (231, 199, 31), (187, 86, 149), (8, 133, 161),
    (243, 243, 242), (200, 200, 200), (160, 160, 160), (122, 122, 121), (85, 85, 85), (52, 52, 52)]


# ---------------------------------------------------------------- contact sheet
def contact_sheet(out, images, cols=3, width=640, labels=None):
    from PIL import Image, ImageDraw
    tiles = []
    for p in images:
        im = Image.open(p)
        if im.mode not in ('RGB', 'RGBA'):
            im = Image.fromarray(to_u8(np.asarray(im)))
        im = im.convert('RGB')
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        tiles.append(im)
    th = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * width, rows * (th + 22)), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(tiles):
        x, y = (i % cols) * width, (i // cols) * (th + 22)
        sheet.paste(t, (x, y))
        d.text((x + 6, y + th + 4), (labels or [os.path.basename(p) for p in images])[i], fill=(220, 220, 220))
    sheet.save(out, quality=88)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('png')
    p.add_argument('exr'); p.add_argument('png')
    p.add_argument('--size'); p.add_argument('--jpeg'); p.add_argument('--quality', type=int, default=92)
    p.add_argument('--view', default=VIEW); p.add_argument('--look', default=LOOK)
    p.add_argument('--exposure', type=float, default=0.0); p.add_argument('--record')
    s = sp.add_parser('stats')
    s.add_argument('img'); s.add_argument('--mask', required=True); s.add_argument('--apex', action='store_true')
    n = sp.add_parser('npy', help='dump any image (EXR/PNG16) as float32 .npy (exact, for tests)')
    n.add_argument('img'); n.add_argument('npy')
    c = sp.add_parser('contact')
    c.add_argument('out'); c.add_argument('images', nargs='+')
    c.add_argument('--cols', type=int, default=3); c.add_argument('--width', type=int, default=640)
    a = ap.parse_args(argv)
    if a.cmd in ('png', 'stats', 'npy') and not have_oiio():
        os.execv(blender_python(), [blender_python(), '-I', os.path.abspath(__file__)] + (argv or sys.argv[1:]))
    if a.cmd == 'png':
        size = tuple(int(x) for x in a.size.lower().split('x')) if a.size else None
        rec, _ = finish_exr(a.exr, a.png, size, a.jpeg, a.quality, a.view, a.look or None, a.exposure)
        if a.record:
            json.dump(rec, open(a.record, 'w'), indent=1)
        print(json.dumps(rec))
    elif a.cmd == 'stats':
        img = read_image(a.img)
        mask = read_image(a.mask)[..., 0]
        st = mask_stats(img, mask)
        st.update(q4_q5(st, a.apex))
        print(json.dumps(st))
    elif a.cmd == 'npy':
        np.save(a.npy, read_image(a.img))
    elif a.cmd == 'contact':
        print(contact_sheet(a.out, a.images, a.cols, a.width))


if __name__ == '__main__':
    main()
