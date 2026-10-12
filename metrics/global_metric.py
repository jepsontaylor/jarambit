"""GLOBAL metric G for jarambit (locked v1, 2026-10-12, Jepson Taylor). Spec: docs/GLOBAL_METRIC.md.

G = w1*tip + w2*spg_n + w3*aes - w4*mass_pen - w5*seq_gap   (dimensionless, higher is better)
  tip      = min(solid_tip_SF, 2.0)            solid C3D tip submodel SF at the max-stress node (828 MPa);
                                               falls back to the plate tip-submodel screen SF -> G marked 'G*' (provisional)
  spg_n    = SPG_cert / 4.0                    certified strength-per-gram (N/g), 4.0 N/g ~ wave10 best
  aes      = aes_score (0..1)                  C.6 automated aesthetic score (spine/outline); human sign-off still separate
  mass_pen = max(0, mass_g - 77) / 10          penalty above the 74-77 g band top
  seq_gap  = max(0, 1.2 - seq_ratio) / 1.2     failure-sequence hand/blade ratio; SOFT until >= 1.2
G never overrides a hard gate: hard-FAIL designs still get G, but are never promoted on G.
"""
import math

GLOBAL_METRIC_VERSION = "G1"
W = dict(tip=0.35, spg=0.35, aes=0.20, mass=0.05, seq=0.05)


def _f(v):
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def terms(rec):
    """rec: plate metrics/index dict. Keys: solid_tip_sf_nodal_max | plate_tipsub_screen_sf, spg, aes_score, mass_g, seq_ratio."""
    tip = _f(rec.get('solid_tip_sf_nodal_max')); provisional = tip is None
    if tip is None:
        tip = _f(rec.get('plate_tipsub_screen_sf'))
    if tip is None:
        tip = _f(rec.get('twist_tipzone_sf_strict'))
    return dict(tip=min(tip, 2.0) if tip is not None else 0.0, tip_missing=tip is None, provisional=provisional,
                spg_n=(_f(rec.get('spg')) or 0.0) / 4.0, aes=_f(rec.get('aes_score')) or 0.0,
                mass_pen=max(0.0, (_f(rec.get('mass_g')) or 0.0) - 77.0) / 10.0,
                seq_gap=max(0.0, 1.2 - (_f(rec.get('seq_ratio')) or 0.0)) / 1.2)


def global_G(rec):
    t = terms(rec)
    g = W['tip'] * t['tip'] + W['spg'] * t['spg_n'] + W['aes'] * t['aes'] - W['mass'] * t['mass_pen'] - W['seq'] * t['seq_gap']
    return g, t


def title_tag(rec, version):
    """String every wave FEM plate title must carry: G + mass + version."""
    g, t = global_G(rec)
    star = '*' if t['provisional'] else ''
    return f"G{star} {g:.3f} | {float(rec.get('mass_g', float('nan'))):.1f} g | jarambit v{version}"


def read_version(start=None):
    import os
    d = os.path.abspath(start or os.path.dirname(__file__))
    for _ in range(6):
        p = os.path.join(d, 'docs', 'VERSION')
        if os.path.exists(p):
            return open(p).read().strip()
        d = os.path.dirname(d)
    return os.environ.get('JARAMBIT_VERSION', 'unknown')


if __name__ == '__main__':
    import sys, json
    for f in sys.argv[1:]:
        for r in json.load(open(f)):
            g, t = global_G(r)
            print(f"{f}\t{r.get('label')}\t{r.get('file')}\tG={g:.4f}{'*' if t['provisional'] else ''}\tmass={r.get('mass_g'):.1f}\thard={r.get('w20_hard_pass')}")
