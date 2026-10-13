#!/usr/bin/env python3
"""Spectral thin-film interference LUT for anodic TiO2 on titanium (host numpy, no data files).

Blender 4.2's Principled thin film only acts on dielectrics, not the metallic lobe, so titanium
anodizing is computed here: Airy reflectance of an air | TiO2 film (thickness d) | Ti substrate stack at
normal incidence, integrated over 380-780 nm with CIE-1931 CMFs (Wyman-Sloan-Shirley 2013 analytic fit)
under a 6504 K illuminant, -> linear Rec.709 F0.  The shader looks the LUT up at d*cos(theta_t) (Snell
in the film) so hue shifts toward thinner-film colours at grazing view, as real anodized Ti does.
d = 0 is rescaled per channel to the house Ti-6Al-4V F0 (presets/finish_ti64.json) for continuity.

python3 thinfilm.py --lut out.npy --chart chart.png
"""
import argparse, json
import numpy as np

DMAX_NM = 480.0
N_LUT = 1024
# Ti complex IOR (approx. Johnson & Christy 1974), lambda nm -> n, k
TI = np.array([[400, 1.86, 2.71], [450, 2.06, 2.98], [500, 2.28, 3.20], [550, 2.54, 3.43],
               [600, 2.78, 3.47], [650, 2.98, 3.50], [700, 3.15, 3.56], [780, 3.38, 3.68]])
TI64_F0 = np.array([0.542, 0.497, 0.449])


def tio2_n(lam_nm):
    """amorphous/anatase anodic TiO2, Cauchy fit n(550) ~ 2.33, weak UV-edge absorption."""
    l = lam_nm * 1e-3
    return 2.17 + 0.048 / l ** 2 + 1j * 0.004 * np.exp(-(lam_nm - 380) / 40)


def g(l, mu, s1, s2):
    s = np.where(l < mu, s1, s2)
    return np.exp(-0.5 * ((l - mu) / s) ** 2)


def cmf(l):
    x = 1.056 * g(l, 599.8, 37.9, 31.0) + 0.362 * g(l, 442.0, 16.0, 26.7) - 0.065 * g(l, 501.1, 20.4, 26.2)
    y = 0.821 * g(l, 568.8, 46.9, 40.5) + 0.286 * g(l, 530.9, 16.3, 31.1)
    z = 1.217 * g(l, 437.0, 11.8, 36.0) + 0.681 * g(l, 459.0, 26.0, 13.8)
    return np.stack([x, y, z], 1)


def planck(l, T=6504.0):
    lm = l * 1e-9
    return 1 / (lm ** 5 * (np.exp(1.4388e-2 / (lm * T)) - 1))


XYZ2RGB = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])


def reflectance(d_nm, lam):
    n0 = 1.0
    n1 = tio2_n(lam)
    n2 = np.interp(lam, TI[:, 0], TI[:, 1]) + 1j * np.interp(lam, TI[:, 0], TI[:, 2])
    r01 = (n0 - n1) / (n0 + n1); r12 = (n1 - n2) / (n1 + n2)
    delta = 2 * np.pi * n1[None] * d_nm[:, None] / lam[None]
    e = np.exp(2j * delta)
    r = (r01 + r12 * e) / (1 + r01 * r12 * e)
    return np.abs(r) ** 2


def lut(n=N_LUT, dmax=DMAX_NM):
    lam = np.arange(380, 781, 2.0)
    w = cmf(lam) * planck(lam)[:, None]
    d = np.linspace(0, dmax, n)
    R = reflectance(d, lam)                      # [n, L]
    xyz = R @ w
    white = np.ones(len(lam)) @ w
    rgb = xyz @ XYZ2RGB.T
    rgbw = white @ XYZ2RGB.T
    rgb = rgb / rgbw                              # equal-energy reflector -> neutral
    rgb = np.clip(rgb, 0.0, None)
    rgb *= TI64_F0 / rgb[0]                       # house Ti F0 at d=0
    return d, np.clip(rgb, 0, 1)


def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)


def chart(path, d, rgb, marks=None):
    from PIL import Image, ImageDraw
    W, H = len(d), 160
    a = (srgb(rgb * 1.25) * 255).astype(np.uint8)       # +exposure ~ lit appearance
    im = Image.fromarray(np.repeat(a[None], H, 0)).resize((1440, H))
    dr = ImageDraw.Draw(im)
    for t in range(0, int(d[-1]) + 1, 20):
        x = int(t / d[-1] * 1439)
        dr.line([x, H - 25, x, H], fill=(0, 0, 0)); dr.text((x + 2, H - 22), str(t), fill=(0, 0, 0))
    for name, t in (marks or {}).items():
        x = int(t / d[-1] * 1439); dr.line([x, 0, x, 40], fill=(255, 255, 255)); dr.text((x + 2, 2), name, fill=(255, 255, 255))
    im.save(path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--lut'); ap.add_argument('--chart'); ap.add_argument('--marks')
    a = ap.parse_args()
    d, rgb = lut()
    if a.lut:
        np.save(a.lut, rgb.astype(np.float32))
    if a.chart:
        chart(a.chart, d, rgb, json.loads(a.marks) if a.marks else None)
