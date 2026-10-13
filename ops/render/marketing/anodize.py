"""Generate finish presets for the Ti anodize family: presets/finish_ti64_anodize_<color>.json.

    python3 ops/render/marketing/anodize.py            # (re)write all, deterministic
    python3 ops/render/marketing/anodize.py --check    # fail if any generated file is stale
"""
import copy
import json
import math
import os
import sys

# Ti optical constants (Johnson & Christy 1974, smoothed) and anodic TiO2 film index (~2.4, mild dispersion)
_TI = [(400, 1.95, 2.60), (450, 2.10, 2.85), (500, 2.30, 3.15), (550, 2.54, 3.43), (600, 2.75, 3.62),
       (650, 2.90, 3.76), (700, 3.05, 3.90)]
_M_XYZ_TO_LIN_SRGB = [[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]]


def _interp(tab, lam, k):
    for (l0, *a), (l1, *b) in zip(tab, tab[1:]):
        if l0 <= lam <= l1:
            t = (lam - l0) / (l1 - l0)
            return a[k] + t * (b[k] - a[k])
    return tab[0][1 + k] if lam < tab[0][0] else tab[-1][1 + k]


def _cie(lam):
    """Wyman, Sloan & Shirley 2013 multi-lobe fit of the CIE 1931 2-deg observer."""
    def g(x, mu, s1, s2):
        s = s1 if x < mu else s2
        return math.exp(-0.5 * ((x - mu) / s) ** 2)
    x = 1.056 * g(lam, 599.8, 37.9, 31.0) + 0.362 * g(lam, 442.0, 16.0, 26.7) - 0.065 * g(lam, 501.1, 20.4, 26.2)
    y = 0.821 * g(lam, 568.8, 46.9, 40.5) + 0.286 * g(lam, 530.9, 16.3, 31.1)
    z = 1.217 * g(lam, 437.0, 11.8, 36.0) + 0.681 * g(lam, 459.0, 26.0, 13.8)
    return x, y, z


def film_reflectance(lam, d_nm, theta_deg=0.0, n_film=2.4):
    """Unpolarized reflectance of air / TiO2 (d) / Ti at wavelength lam (nm)."""
    n0 = 1.0
    n2 = complex(_interp(_TI, lam, 0), _interp(_TI, lam, 1))
    s0 = math.sin(math.radians(theta_deg))
    c0 = math.cos(math.radians(theta_deg))
    c1 = (1 - (n0 * s0 / n_film) ** 2) ** 0.5
    import cmath
    c2 = cmath.sqrt(1 - (n0 * s0 / n2) ** 2)
    R = 0.0
    for pol in ("s", "p"):
        if pol == "s":
            r01 = (n0 * c0 - n_film * c1) / (n0 * c0 + n_film * c1)
            r12 = (n_film * c1 - n2 * c2) / (n_film * c1 + n2 * c2)
        else:
            r01 = (n_film * c0 - n0 * c1) / (n_film * c0 + n0 * c1)
            r12 = (n2 * c1 - n_film * c2) / (n2 * c1 + n_film * c2)
        ph = cmath.exp(2j * 2 * math.pi * n_film * d_nm * c1 / lam)
        r = (r01 + r12 * ph) / (1 + r01 * r12 * ph)
        R += abs(r) ** 2 / 2
    return R


def film_rgb(d_nm, theta_deg=0.0):
    """Linear-sRGB reflectance (D65-normalised, equal-energy approx) of the film stack."""
    X = Y = Z = N = 0.0
    for lam in range(400, 701, 5):
        x, y, z = _cie(lam)
        R = film_reflectance(lam, d_nm, theta_deg)
        X += x * R; Y += y * R; Z += z * R; N += y
    X, Y, Z = X / N, Y / N, Z / N
    rgb = [sum(m * v for m, v in zip(row, (X, Y, Z))) for row in _M_XYZ_TO_LIN_SRGB]
    # white-balance so a perfect (R=1) reflector maps to (1,1,1)
    W = [sum(m * v for m, v in zip(row, [sum(_cie(l)[i] for l in range(400, 701, 5)) / N for i in range(3)]))
         for row in _M_XYZ_TO_LIN_SRGB]
    return [max(0.0, min(1.0, c / w)) for c, w in zip(rgb, W)]


def film_metal(d_nm):
    """Blender 4.2 Principled metallic params (F0 base colour + F82 tint) for the film stack.
    Blender 4.2's Thin Film input does not act on metals, so the interference colour is baked into
    the conductor's F0/F82 from this thin-film model."""
    f0 = film_rgb(d_nm, 0.0)
    f82 = film_rgb(d_nm, 82.0)
    cos82 = math.cos(math.radians(82.0))
    schlick = [f + (1 - f) * (1 - cos82) ** 5 for f in f0]
    tint = [max(0.0, min(1.0, a / s)) for a, s in zip(f82, schlick)]
    return {"base_color_lin": [round(c, 4) for c in f0], "f82_tint": [round(c, 4) for c in tint]}

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(HERE, "presets")


def build(family, base, color):
    spec = family["colors"][color]
    out = copy.deepcopy(base)
    out["name"] = f"finish_ti64_anodize_{color}"
    out["family"] = {"name": family["name"], "color": color, **{k: v for k, v in spec.items()}}
    fin = f"anodize_{color}"
    kind = spec.get("kind", "anodize")
    if kind == "raw":
        fspec = copy.deepcopy(base["finishes"][spec["finish"]])
    elif kind == "coating":
        fspec = dict(family["film_base"], roughness=spec["roughness"])
        out["region_metal"] = {r: {"base_color_lin": spec["base_color_lin"], "f82_tint": spec["base_color_lin"]}
                               for r in family["anodized_regions"]}
    else:
        fspec = dict(family["film_base"])
        fspec["film_thickness_nm"] = float(spec["thin_film_nm"])  # documentation; colour is in region_metal
        out["region_metal"] = {r: film_metal(float(spec["thin_film_nm"])) for r in family["anodized_regions"]}
    out["finishes"][fin] = fspec
    for r in family["anodized_regions"]:
        out["default_assignment"][r] = fin
    out["note"] = base["note"] + " " + family["note"]
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    family = json.load(open(os.path.join(PRESETS, "anodize_family.json")))
    base = json.load(open(os.path.join(PRESETS, family["base"] + ".json")))
    stale = []
    for color in sorted(family["colors"]):
        path = os.path.join(PRESETS, f"finish_ti64_anodize_{color}.json")
        text = json.dumps(build(family, base, color), indent=1, sort_keys=True) + "\n"
        if "--check" in argv:
            if not os.path.isfile(path) or open(path).read() != text:
                stale.append(path)
            continue
        open(path, "w").write(text)
    if stale:
        print("stale:", stale)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
