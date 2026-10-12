"""Shared figure helpers (PR-0.29.4). Pure Python (no matplotlib import) so CI can unit-test them.
- Badges and captions are DERIVED from observations; nothing is hard-coded to PASS.
- Colour normalisation is shared and declared (written into every figure manifest).
- Every rendered figure gets `<figure>.manifest.json` (sha256 of every input + the output), checked by
  ops/ci/verify_figures.py so a swapped STL / plate JSON / PNG without a manifest update fails CI."""
import hashlib, json, math, os

GREEN, RED, GREY = '#2a7', '#c22', '#888'
# Declared, shared colour scales (NOT per-plate percentiles): plates are comparable across waves.
NORMS = {
    'von_mises_mpa': {'vmin': 0.0, 'vmax': 828.0, 'cmap': 'turbo', 'note': 'fixed 0..828 MPa (screening yield); clipped above'},
    'safety_factor': {'vmin': 0.0, 'vmax': 4.0, 'cmap': 'RdYlGn', 'note': 'fixed 0..4; clipped'},
    'step3d_x_mm': {'vmin': None, 'vmax': None, 'cmap': 'plasma', 'note': 'shading only (x position); no physical meaning'},
}
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def tri(v):
    """PASS / FAIL / INCOMPLETE from a bool-or-missing observation."""
    return 'PASS' if v is True else ('FAIL' if v is False else 'INCOMPLETE')


def badge_colour(state):
    return {'PASS': GREEN, 'FAIL': RED}.get(state, GREY)


def aes_badge(m, rev):
    """Aesthetic-floor badge from the record (was hard-coded 'PASS' in make_d1_plate.py)."""
    st = tri(m.get('aes_pass'))
    det = []
    if _num(m.get('hausdorff')): det.append('H %.2f mm' % m['hausdorff'])
    if _num(m.get('emd')): det.append('EMD %.3f' % m['emd'])
    if _num(m.get('aes_score')): det.append('A %.3f' % m['aes_score'])
    fails = m.get('aes_fails') or []
    txt = 'AESTHETIC FLOOR (%s): %s\n%s' % (rev, st, ' · '.join(det) if det else 'no aesthetic observations')
    if st == 'FAIL' and fails: txt += '\n' + '; '.join(fails)[:60]
    return txt, badge_colour(st)


def hero_caption(obs, version):
    """3D hero caption from observations. Says 'faceted STL preview' unless a STEP validation observation exists."""
    label = obs.get('label', '?')
    step = obs.get('step_validation') or {}
    kind = 'validated STEP (%s)' % step.get('tool', '?') if step.get('valid') is True else 'faceted STL preview (STEP not validated)'
    parts = []
    g = obs.get('G1')
    parts.append('G1 %.4f' % g if _num(g) else 'G1 INCOMPLETE')
    tip, spg = obs.get('solid_tip_sf_nodal_max'), obs.get('spg')
    if _num(tip) and _num(spg): parts.append('tip×SPG %.3f' % (tip * spg))
    if _num(obs.get('mass_g')): parts.append('%.2f g' % obs['mass_g'])
    if _num(obs.get('ring_id_mm')): parts.append('ring %.2f mm' % obs['ring_id_mm'])
    return 'jarambit v%s — %s (%s)\n%s' % (version, label, kind, ' · '.join(parts))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(os.path.abspath(p), ROOT)


def write_manifest(figure, inputs, script, norms=(), extra=None):
    """Write `<figure>.manifest.json`: sha256 of each input and of the figure, the generating script, declared norms."""
    man = {'schema': 1, 'figure': rel(figure), 'figure_sha256': sha256_file(figure), 'script': rel(script),
           'inputs': {rel(p): sha256_file(p) for p in inputs}, 'norms': {k: NORMS[k] for k in norms}}
    if extra: man['extra'] = extra
    with open(figure + '.manifest.json', 'w') as fh:
        json.dump(man, fh, indent=1, sort_keys=True); fh.write('\n')
    return man
