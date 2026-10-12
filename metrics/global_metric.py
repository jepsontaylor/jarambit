"""GLOBAL metric G for jarambit (locked v1, 2026-10-12, Jepson Taylor). Spec: docs/GLOBAL_METRIC.md.

G = w1*tip + w2*spg_n + w3*aes - w4*mass_pen - w5*seq_gap   (dimensionless, higher is better)
  tip      = min(solid_tip_SF, 2.0)            solid C3D tip submodel SF at the max-stress node (828 MPa);
                                               falls back to the plate tip-submodel screen SF -> G marked 'G*' (provisional)
  spg_n    = SPG_cert / 4.0                    certified strength-per-gram (N/g), 4.0 N/g ~ wave10 best
  aes      = aes_score (0..1)                  C.6 automated reference-style conformance score; human sign-off separate
  mass_pen = max(0, mass_g - 77) / 10          penalty above the 74-77 g band top
  seq_gap  = max(0, 1.2 - seq_ratio) / 1.2     failure-sequence hand/blade ratio
G never overrides a hard gate: hard-FAIL designs still get G, but are never promoted on G.

Completeness (v0.28.1, PR-0.28.1): every term is REQUIRED. A missing, null, boolean, non-numeric,
non-finite or out-of-range input is never turned into a number. The record gets status 'INCOMPLETE',
the reasons are listed in terms['missing'], and global_G returns G = None. Deleting an input can
therefore never improve G. 'provisional' (G*) only means "tip came from a screen, not the solid
submodel"; it says nothing about completeness, which is the separate 'status' field.
"""
import math

GLOBAL_METRIC_VERSION = "G1"
W = dict(tip=0.35, spg=0.35, aes=0.20, mass=0.05, seq=0.05)
TIP_KEYS = ('solid_tip_sf_nodal_max', 'plate_tipsub_screen_sf', 'twist_tipzone_sf_strict')
# key -> (lo, hi) inclusive admissible range; outside -> INCOMPLETE (never clipped)
RANGES = {
    'solid_tip_sf_nodal_max': (0.0, 100.0), 'plate_tipsub_screen_sf': (0.0, 100.0), 'twist_tipzone_sf_strict': (0.0, 100.0),
    'spg': (0.0, 100.0), 'aes_score': (0.0, 1.0), 'mass_g': (1.0, 1000.0), 'seq_ratio': (0.0, 100.0),
}
COMPLETE, INCOMPLETE = 'COMPLETE', 'INCOMPLETE'


def _obs(rec, key):
    """Return (value, None) for a valid observation, else (None, reason). Never coerces to 0."""
    if key not in rec:
        return None, f"{key}: missing"
    v = rec[key]
    if v is None:
        return None, f"{key}: null"
    if isinstance(v, bool):
        return None, f"{key}: boolean not allowed"
    if isinstance(v, str):
        try:
            v = float(v.strip())
        except ValueError:
            return None, f"{key}: not a number ({v!r})"
    elif isinstance(v, (int, float)):
        v = float(v)
    else:
        return None, f"{key}: unsupported type {type(v).__name__}"
    if not math.isfinite(v):
        return None, f"{key}: non-finite"
    lo, hi = RANGES[key]
    if not (lo <= v <= hi):
        return None, f"{key}: out of range [{lo}, {hi}] ({v})"
    return v, None


def _f(v):
    """Legacy lenient parser (kept for callers); returns None for anything not a finite number."""
    if isinstance(v, bool):
        return None
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def terms(rec):
    """rec: plate metrics/index dict. Keys: solid_tip_sf_nodal_max | plate_tipsub_screen_sf | twist_tipzone_sf_strict,
    spg, aes_score, mass_g, seq_ratio. Missing terms are None (never 0); see 'status' and 'missing'."""
    missing = []
    tip, tip_src = None, None
    tip_reasons = []
    for k in TIP_KEYS:
        v, why = _obs(rec, k)
        if v is not None:
            tip, tip_src = v, k
            break
        tip_reasons.append(why)
    if tip is None:
        missing.append("tip: " + "; ".join(tip_reasons))
    vals = {}
    for k in ('spg', 'aes_score', 'mass_g', 'seq_ratio'):
        v, why = _obs(rec, k)
        vals[k] = v
        if why:
            missing.append(why)
    status = COMPLETE if not missing else INCOMPLETE
    return dict(
        tip=min(tip, 2.0) if tip is not None else None, tip_source=tip_src, tip_missing=tip is None,
        provisional=tip_src != 'solid_tip_sf_nodal_max',
        spg_n=vals['spg'] / 4.0 if vals['spg'] is not None else None,
        aes=vals['aes_score'],
        mass_pen=max(0.0, vals['mass_g'] - 77.0) / 10.0 if vals['mass_g'] is not None else None,
        seq_gap=max(0.0, 1.2 - vals['seq_ratio']) / 1.2 if vals['seq_ratio'] is not None else None,
        status=status, missing=missing, metric_version=GLOBAL_METRIC_VERSION)


def global_G(rec):
    """Return (G, terms). G is None unless terms['status'] == 'COMPLETE'."""
    t = terms(rec)
    if t['status'] != COMPLETE:
        return None, t
    g = W['tip'] * t['tip'] + W['spg'] * t['spg_n'] + W['aes'] * t['aes'] - W['mass'] * t['mass_pen'] - W['seq'] * t['seq_gap']
    return g, t


def title_tag(rec, version):
    """String every wave FEM plate title must carry: G + mass + version. Uses the validated terms only."""
    g, t = global_G(rec)
    m, _ = _obs(rec, 'mass_g')
    mass_s = f"{m:.1f} g" if m is not None else "mass n/a"
    if g is None:
        return f"G INCOMPLETE ({len(t['missing'])} missing) | {mass_s} | jarambit v{version}"
    star = '*' if t['provisional'] else ''
    return f"G{star} {g:.3f} | {mass_s} | jarambit v{version}"


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
            gs = f"G={g:.4f}{'*' if t['provisional'] else ''}" if g is not None else f"G=INCOMPLETE[{'; '.join(t['missing'])}]"
            m = _f(r.get('mass_g'))
            print(f"{f}\t{r.get('label')}\t{r.get('file')}\t{gs}\tmass={'%.1f' % m if m is not None else 'n/a'}\thard={r.get('w20_hard_pass')}")
