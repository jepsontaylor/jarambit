#!/usr/bin/env python3
"""360° turntable GIF of a design STL (ops/render, v0.32 release push). Deterministic software renderer:
numpy projection + Lambert/specular shading + painter's order drawn with Pillow (no GPU, runs headless on any host),
then ffmpeg palettegen/paletteuse (sierra2_4a dithering) -> lossy web GIF. Writes <out>.manifest.json with input
sha256s, parameters, frame count, size and the output sha256 (CI: ops/ci/verify_media.py).

usage: turntable.py --stl STL [--d1 D1.json --color fem|x] --out docs/media/X.gif [--frames 72 --fps 24 --width 1920 --height 1080]
--color fem: per-facet colour = D1 certified envelope SF field (nearest plate element in plan), viridis-like map, red < 1.
--color x:   shading colour = position along the blade (no physical meaning)."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load_stl(p):
    v = np.array(re.findall(r'vertex\s+(\S+)\s+(\S+)\s+(\S+)', open(p).read()), float).reshape(-1, 3, 3)
    return v


def cmap(t):
    # compact perceptual ramp (dark blue -> teal -> yellow), t in [0,1]
    k = np.array([[0.13, 0.11, 0.35], [0.12, 0.40, 0.55], [0.13, 0.63, 0.53], [0.47, 0.82, 0.32], [0.99, 0.91, 0.14]])
    t = np.clip(t, 0, 1) * (len(k) - 1); i = np.minimum(t.astype(int), len(k) - 2); f = (t - i)[:, None]
    return k[i] * (1 - f) + k[i + 1] * f


def facet_colors(v, mode, d1):
    if mode == 'fem' and d1:
        m = json.load(open(d1))['mesh']; xy = np.array(m['xy']); tr = np.array(m['tris']); sf = np.array(m['sf'], float)
        cen = xy[tr].mean(1); fc = v[:, :, :2].mean(1)
        # nearest plate element by plan position (chunked brute force; ~1e4 x 3e4)
        idx = np.empty(len(fc), int)
        for s in range(0, len(fc), 512):
            d = ((fc[s:s + 512, None, :] - cen[None]) ** 2).sum(-1); idx[s:s + 512] = d.argmin(1)
        val = np.clip(sf[idx], 0, 3)
        c = cmap((val - 1.0) / 2.0); c[val < 1.0] = [0.85, 0.15, 0.12]
        return c, {'field': 'D1 certified envelope SF (100 C, joint)', 'range': [1.0, 3.0], 'below_1': 'red'}
    x = v[:, :, 0].mean(1)
    return cmap((x - x.min()) / np.ptp(x)), {'field': 'x position (shading only, no physical meaning)'}


def render(v, col, ang, W, H, title, legend=None):
    c0 = v.reshape(-1, 3).mean(0); p = v - c0
    a = np.radians(ang); tilt = np.radians(-38)
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, np.cos(tilt), -np.sin(tilt)], [0, np.sin(tilt), np.cos(tilt)]])
    q = p @ (Rx @ Rz).T  # camera looks along -y' ... use x right, z up, y depth
    n = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
    Ld = np.array([-0.35, -0.6, 0.72]); Ld /= np.linalg.norm(Ld)
    lam = np.abs(n @ Ld); spec = np.abs(n[:, 1]) ** 24
    shade = np.clip(col * (0.28 + 0.72 * lam)[:, None] + 0.35 * spec[:, None], 0, 1)
    ext = np.ptp(p.reshape(-1, 3)[:, :2], 0).max() * 1.12
    s = min(W, H * 1.6) / ext
    X = W / 2 + q[:, :, 0] * s; Y = H * 0.54 - q[:, :, 2] * s
    order = np.argsort(q[:, :, 1].mean(1))[::-1]  # far (large y) first
    img = Image.new('RGB', (W, H), (13, 17, 23)); dr = ImageDraw.Draw(img)
    rgb = (shade * 255).astype(np.uint8)
    for i in order:
        dr.polygon([(X[i, 0], Y[i, 0]), (X[i, 1], Y[i, 1]), (X[i, 2], Y[i, 2])], fill=tuple(rgb[i]))
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', max(18, H // 40))
    except OSError:
        font = ImageFont.load_default()
    dr.text((W * 0.03, H * 0.04), title, fill=(230, 237, 243), font=font)
    if legend:
        x0, y0, bw, bh = int(W * 0.03), int(H * 0.86), int(W * 0.22), int(H * 0.025)
        ramp = (cmap(np.linspace(0, 1, bw)) * 255).astype(np.uint8)
        for i in range(bw): dr.line([(x0 + i, y0), (x0 + i, y0 + bh)], fill=tuple(ramp[i]))
        dr.rectangle([x0 - int(W * 0.02), y0, x0 - int(W * 0.008), y0 + bh], fill=(217, 38, 31))
        dr.text((x0, y0 + bh + 6), legend, fill=(200, 208, 216), font=font)
    return img


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--stl', required=True); ap.add_argument('--d1'); ap.add_argument('--color', choices=['fem', 'x'], default='fem')
    ap.add_argument('--out', required=True); ap.add_argument('--frames', type=int, default=72); ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--width', type=int, default=1920); ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--gif-width', type=int, default=1920, help='output GIF width (height keeps aspect)')
    ap.add_argument('--colors', type=int, default=128); ap.add_argument('--title', default='')
    a = ap.parse_args(argv)
    v = load_stl(a.stl); col, cinfo = facet_colors(v, a.color, a.d1)
    tmp = tempfile.mkdtemp(prefix='turntable_')
    try:
        for k in range(a.frames):
            render(v, col, 360.0 * k / a.frames, a.width, a.height, a.title, 'red: SF < 1   SF 1 -> 3 (D1 envelope, 100 C)' if a.color == 'fem' else None).save(os.path.join(tmp, f'f{k:04d}.png'))
        ff = shutil.which('ffmpeg') or sys.exit('ffmpeg required')
        vf = f'fps={a.fps},scale={a.gif_width}:-1:flags=lanczos'
        subprocess.run([ff, '-v', 'error', '-y', '-framerate', str(a.fps), '-i', os.path.join(tmp, 'f%04d.png'),
                        '-vf', f'{vf},palettegen=max_colors={a.colors}:stats_mode=diff', os.path.join(tmp, 'pal.png')], check=True)
        subprocess.run([ff, '-v', 'error', '-y', '-framerate', str(a.fps), '-i', os.path.join(tmp, 'f%04d.png'), '-i', os.path.join(tmp, 'pal.png'),
                        '-lavfi', f'{vf}[x];[x][1:v]paletteuse=dither=sierra2_4a:diff_mode=rectangle', '-loop', '0', a.out], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    w, h = Image.open(a.out).size
    rel = lambda p: os.path.relpath(os.path.abspath(p), ROOT)
    man = {'schema': 1, 'script': 'ops/render/turntable.py', 'output': rel(a.out), 'output_sha256': sha(a.out), 'figure': rel(a.out), 'figure_sha256': sha(a.out), 'bytes': os.path.getsize(a.out),
           'size': [w, h], 'frames': a.frames, 'fps': a.fps, 'degrees': 360, 'palette_colors': a.colors, 'dither': 'sierra2_4a', 'lossy': True,
           'color': a.color, 'color_info': cinfo, 'inputs': {rel(p): sha(p) for p in [a.stl] + ([a.d1] if a.d1 and a.color == 'fem' else [])}}
    json.dump(man, open(a.out + '.manifest.json', 'w'), indent=1, sort_keys=True); open(a.out + '.manifest.json', 'a').write('\n')
    print(json.dumps({k: man[k] for k in ('output', 'bytes', 'size', 'frames')}))


if __name__ == '__main__':
    main()
