"""Maker's mark / signature as its own zone (zone 5 'mark') -- host numpy, generic per CAD.

Sources, all tried, all recorded:
  labels   : region label names matching mark|logo|signature|engrav|etch  -> zone-5 faces
  geometry : engraved text = MANY small recessed components on a main side flat (>= min_glyphs
             components, recess depth 0.02-0.6 mm, total < 3 % of that flat).  Two decorative grooves
             are not a mark.
  decal    : the render lane's automatic signature placement (marketing/signature.py, or the module
             named by $JARAMBIT_SIGNATURE_MODULE).  A decal is sub-face, so it is a shader mask that the
             Blender side overlays on top of EVERY slot (coat AND bare) as the final node.
validate(): fails if a source exists but the output has no mark, or if any mark face is coatable.
"""
import importlib.util
import os
import re

import numpy as np

MARK_RE = re.compile(r'mark|logo|signature|engrav|etch', re.I)
ZONE_MARK = 5


def _sig_module():
    cands = [os.environ.get('JARAMBIT_SIGNATURE_MODULE', ''),
             os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'signature.py')]
    for p in cands:
        if p and os.path.isfile(p):
            spec = importlib.util.spec_from_file_location('jarambit_signature', p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m, p
    return None, None


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x


def geometric_marks(V, F, fn, area, n, components, adjacency, p):
    h = (V[F].mean(1) - V.mean(0)) @ n
    side = fn @ n
    out = np.zeros(len(F), bool)
    for sgn in (1, -1):
        flat = sgn * side > np.cos(np.radians(2.0))
        if not flat.any():
            continue
        # main flat = most-area plane offset (0.05 mm bins)
        b = np.round(h[flat] / 5e-5).astype(int)
        vals, inv = np.unique(b, return_inverse=True)
        main = vals[np.argmax(np.bincount(inv, weights=area[flat]))] * 5e-5
        depth = sgn * (main - h)                       # >0 = below the main flat (recessed)
        cand = flat & (depth > p['mark_depth_mm'][0] * 1e-3) & (depth < p['mark_depth_mm'][1] * 1e-3)
        if not cand.any():
            continue
        comp = components(cand, *adjacency)
        ids, cnt = np.unique(comp[cand], return_counts=True)
        small = [i for i in ids if area[comp == i].sum() < p['mark_glyph_max_mm2'] * 1e-6]
        main_area = area[flat & (np.abs(depth) < 5e-5)].sum()
        sel = np.isin(comp, small) & cand
        if len(small) >= p['mark_min_glyphs'] and area[sel].sum() < 0.03 * main_area:
            out |= sel
    return out


def detect(mesh, zone, V, F, fn, area, n, components, adjacency, p):
    """mutates zone (zone 5 for mark faces); returns report dict."""
    names = mesh.get('_label_names', [])
    rep = {'sources': [], 'label_faces': 0, 'geometry_faces': 0, 'decal': None}
    src_faces = np.zeros(len(F), bool)
    if 'region_id' in mesh:
        rid = np.asarray(mesh['region_id'])
        for i, nm in enumerate(names):
            if MARK_RE.search(nm):
                src_faces |= rid == i
        if src_faces.any():
            rep['sources'].append('labels'); rep['label_faces'] = int(src_faces.sum())
    if p.get('mark_geometry', True):
        g = geometric_marks(V, F, fn, area, n, components, adjacency, p) & ~src_faces
        if g.any():
            rep['sources'].append('geometry'); rep['geometry_faces'] = int(g.sum())
            src_faces |= g
    zone[src_faces] = ZONE_MARK
    rep['source_faces_mask'] = src_faces
    mod, path = _sig_module()
    if mod is not None and p.get('mark_decal', True):
        try:
            r = mod.place(V, F, {'sides': p.get('mark_sides', ['hero', 'back'])})
            pls = [pl for pl in r['placements'] if pl.get('ok')]
            rep['decal'] = {'module': path, 'asset': _jsonable(r.get('asset')), 'params': _jsonable(r.get('params')),
                            'placements': _jsonable(pls), 'requested': len(r['placements'])}
            rep['sources'].append('decal')
        except Exception as e:  # a broken module must not silently drop the mark
            rep['decal'] = {'module': path, 'error': repr(e), 'placements': [], 'requested': 1}
            rep['sources'].append('decal')
    return rep


def validate(rep, zone):
    """True iff every mark source survives into the output and no mark face is coatable."""
    src = rep['source_faces_mask']
    faces_ok = bool((zone[src] == ZONE_MARK).all()) if src.any() else True
    decal_ok = True
    if rep.get('decal') is not None:
        d = rep['decal']
        decal_ok = (not d.get('error')) and len(d.get('placements', [])) >= 1
    present = bool(src.any()) or bool(rep.get('decal') and rep['decal'].get('placements'))
    exists = bool(rep['sources'])
    return {'mark_faces_bare': faces_ok, 'mark_decal_placed': decal_ok,
            'mark_present_if_in_source': (present or not exists)}
