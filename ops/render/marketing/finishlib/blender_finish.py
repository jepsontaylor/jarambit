"""Blender side of the finish library: per-face zone masks -> materials (Cycles, Blender 4.2).

Called from blender/worker.py when request['finish_library'] is present:
  {"entry": {...one library entry...}, "masks_npz": ".../finish_masks.npz", "lut_npy": ".../tf_lut.npy",
   "lut_dmax_nm": 480}
Zone 0 (coat) gets the library finish; zones 1-4 (blade flat, bevel, apex, serration) ALWAYS get the
bare house steel/Ti finishes from the base preset -- there is no code path that puts a coat on them.
"""
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'blender'))
import materials  # noqa: E402
from materials import G, _bump_chain  # noqa: E402

ZONES = ['coat', 'blade_flat', 'bevel', 'edge_apex', 'serration']
BARE_DEFAULT = {'blade_flat': 'blade_stonewash_fine', 'bevel': 'satin_bevel', 'edge_apex': 'edge_highlight',
                'serration': 'serration'}
ZONE_RGB = [(0.05, 0.25, 1.0), (1.0, 0.65, 0.02), (1.0, 0.2, 0.01), (1.0, 0.0, 0.05), (0.7, 0.02, 0.6)]


# ------------------------------------------------------------------ small helpers
def lerp(g, a, b, t):
    m = g.n('ShaderNodeMix', data_type='FLOAT')
    for sock, v in ((m.inputs[0], t), (m.inputs[2], a), (m.inputs[3], b)):
        _set(g, sock, v)
    return m.outputs[0]


def lerp_rgb(g, a, b, t):
    m = g.n('ShaderNodeMix', data_type='RGBA')
    _set(g, m.inputs[0], t)
    _set(g, m.inputs[6], a)
    _set(g, m.inputs[7], b)
    return m.outputs[2]


def _set(g, sock, v):
    if isinstance(v, (int, float)):
        sock.default_value = float(v)
    elif isinstance(v, (tuple, list)):
        sock.default_value = tuple(v) + ((1.0,) if len(v) == 3 and len(sock.default_value) == 4 else ())
    else:
        g.link(v, sock)


def clamp01(g, x):
    m = g.n('ShaderNodeClamp')
    _set(g, m.inputs['Value'], x)
    return m.outputs[0]


def maprange(g, x, a, b, c=0.0, d=1.0, smooth=False):
    m = g.n('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP' if smooth else 'LINEAR', clamp=True)
    _set(g, m.inputs['Value'], x)
    m.inputs['From Min'].default_value, m.inputs['From Max'].default_value = a, b
    m.inputs['To Min'].default_value, m.inputs['To Max'].default_value = c, d
    return m.outputs['Result']


def ramp(g, x, stops, interp='LINEAR', scale=1.0):
    """scalar piecewise map via ColorRamp (grey values = y/scale)."""
    cr = g.n('ShaderNodeValToRGB')
    cr.color_ramp.interpolation = interp
    el = cr.color_ramp.elements
    while len(el) > 1:
        el.remove(el[-1])
    for i, (px, y) in enumerate(stops):
        e = el[0] if i == 0 else el.new(float(px))
        e.position = float(px)
        v = float(y) / scale
        e.color = (v, v, v, 1.0)
    _set(g, cr.inputs['Fac'], x)
    return g.math('MULTIPLY', cr.outputs['Color'], scale)


def attr(g, name):
    a = g.n('ShaderNodeAttribute', attribute_name=name, attribute_type='GEOMETRY')
    return a.outputs['Fac']


def noise(g, vec, scale, detail=4.0, rough=0.55, distortion=0.0, dims='3D', w=None):
    nz = g.n('ShaderNodeTexNoise', noise_dimensions=dims, in_Scale=scale, in_Detail=detail,
             in_Roughness=rough, in_Distortion=distortion)
    g.link(vec, nz.inputs['Vector'])
    return nz.outputs['Fac']


# ------------------------------------------------------------------ pattern -> p in [0,1]
def pattern(g, pat, P, s, t, arc_m):
    kind = pat.get('kind', 'none')
    seedv = g.n('ShaderNodeVectorMath', operation='ADD')
    g.link(P, seedv.inputs[0]); seedv.inputs[1].default_value = (pat.get('seed', 0) * 0.37,) * 3
    Pv = seedv.outputs[0]
    warp = 0.0
    if pat.get('warp', 0):
        warp = g.math('MULTIPLY', g.math('SUBTRACT', noise(g, Pv, 1.0 / pat.get('warp_scale_mm', 12) * 1e3, 3.0), 0.5),
                      pat['warp'])
    if kind == 'none':
        return None
    if kind == 'gradient':
        base = s if pat.get('axis', 's') == 's' else maprange(g, t, -1, 1)
        return clamp01(g, g.math('ADD', base, warp) if warp else base)
    if kind == 'heat_bands':
        # torch spot at s=centre; colour order follows distance from the hot spot (thicker film = hotter)
        dist = g.math('ABSOLUTE', g.math('SUBTRACT', g.math('ADD', s, warp) if warp else s, pat.get('centre', 0.5)))
        return clamp01(g, g.math('DIVIDE', dist, pat.get('width', 0.5)))
    if kind in ('timascus', 'tiger_stripe'):
        # bands laid across the knife's arc: coordinate = arc length (m) + distorted 3-D noise
        along = g.math('MULTIPLY', s, arc_m)
        cmb = g.n('ShaderNodeCombineXYZ')
        g.link(along, cmb.inputs['X'])
        g.link(g.math('MULTIPLY', t, pat.get('t_mix_mm', 6.0) * 1e-3), cmb.inputs['Y'])
        sep = g.n('ShaderNodeSeparateXYZ'); g.link(Pv, sep.inputs['Vector'])
        g.link(sep.outputs['Y'], cmb.inputs['Z'])
        wv = g.n('ShaderNodeTexWave', wave_type='BANDS', bands_direction='X', wave_profile='SIN',
                 in_Scale=1.0 / (pat.get('period_mm', 8.0) * 1e-3), in_Distortion=pat.get('distortion', 8.0),
                 in_Detail=pat.get('detail', 3.0), in_Detail_Scale=pat.get('detail_scale', 1.5),
                 in_Detail_Roughness=0.6)
        g.link(cmb.outputs['Vector'], wv.inputs['Vector'])
        p = wv.outputs['Fac']
        if kind == 'tiger_stripe':
            th = pat.get('threshold', 0.55)
            return maprange(g, p, th - pat.get('feather', 0.04), th + pat.get('feather', 0.04), smooth=True)
        if pat.get('layers'):  # discrete Timascus layers: quantise with soft steps
            n = int(pat['layers'])
            q = g.math('FLOOR', g.math('MULTIPLY', p, n))
            fr = maprange(g, g.math('FRACT', g.math('MULTIPLY', p, n)), 0.85, 1.0, smooth=True)
            return clamp01(g, g.math('DIVIDE', g.math('ADD', q, fr), n))
        return p
    if kind == 'oil_slick':
        sc = 1.0 / (pat.get('scale_mm', 14.0) * 1e-3)
        return clamp01(g, maprange(g, noise(g, Pv, sc, 5.0, 0.6, pat.get('distortion', 2.5)), 0.25, 0.75))
    if kind == 'acid_etch':
        sc = 1.0 / (pat.get('scale_mm', 2.0) * 1e-3)
        nz = noise(g, Pv, sc, 8.0, 0.7, pat.get('distortion', 0.6))
        th = pat.get('threshold', 0.52)
        return maprange(g, nz, th - 0.03, th + 0.03, smooth=True)
    raise ValueError(f'unknown pattern kind {kind!r}')


# ------------------------------------------------------------------ micro surface
def micro_surface(g, spec, P, normal):
    """returns (normal, roughness_offset_socket_or_0)"""
    micro = spec.get('micro', 'none')
    if micro == 'bead_blast':
        sc = 1.0 / (spec.get('grain_um', 40) * 1e-6)
        vor = g.n('ShaderNodeTexVoronoi', feature='F1', in_Scale=sc, in_Randomness=1.0)
        g.link(P, vor.inputs['Vector'])
        normal = _bump_chain(g, vor.outputs['Distance'], spec.get('bump', 0.04), 1e-5, normal)
        return normal, g.math('MULTIPLY', g.math('SUBTRACT', noise(g, P, 250.0, 3.0), 0.5), 0.08)
    if micro == 'stonewash':
        hsum = None
        for i, s_mm in enumerate((0.5, 1.5, 4.0)):
            mp = g.n('ShaderNodeMapping', vector_type='POINT')
            mp.inputs['Rotation'].default_value = (0.7 * i + 0.3, 1.1 * i, 2.3 * i + 0.5)
            mp.inputs['Scale'].default_value = (1.0, 1.0, 6.0)
            g.link(P, mp.inputs['Vector'])
            vor = g.n('ShaderNodeTexVoronoi', feature='DISTANCE_TO_EDGE', in_Scale=1.0 / (s_mm * 1e-3))
            g.link(mp.outputs['Vector'], vor.inputs['Vector'])
            line = g.math('LESS_THAN', vor.outputs['Distance'], 0.02)
            hsum = line if hsum is None else g.math('ADD', hsum, line)
        normal = _bump_chain(g, g.math('MULTIPLY', hsum, -1.0), spec.get('bump', 0.02), 2e-5, normal)
        return normal, g.math('MULTIPLY', g.math('SUBTRACT', noise(g, P, 330.0, 4.0), 0.5), 0.12)
    if micro == 'satin_lines':
        tan = g.n('ShaderNodeAttribute', attribute_name='finish_tangent', attribute_type='GEOMETRY').outputs['Vector']
        along = g.math('DOT_PRODUCT', P, tan, vector=True)
        acr = g.math('DOT_PRODUCT', P, g.math('CROSS_PRODUCT', tan, (0.0, 1.0, 0.0), vector=True), vector=True)
        cmb = g.n('ShaderNodeCombineXYZ')
        g.link(g.math('MULTIPLY', acr, 1.0 / 15e-6), cmb.inputs['X'])
        g.link(g.math('MULTIPLY', along, 1.0 / (15e-6 * spec.get('stretch', 200))), cmb.inputs['Y'])
        normal = _bump_chain(g, noise(g, cmb.outputs['Vector'], 1.0, 4.0, dims='2D'), spec.get('bump', 0.03), 5e-6, normal)
        return normal, 0.0
    return normal, 0.0


# ------------------------------------------------------------------ the coat material
def thinfilm_color(g, thickness, lut_img, dmax, film_n=2.33):
    """F0 colour from the spectral LUT at d*cos(theta_t)."""
    geo = g.n('ShaderNodeNewGeometry')
    cos_i = g.math('ABSOLUTE', g.math('DOT_PRODUCT', geo.outputs['Normal'], geo.outputs['Incoming'], vector=True))
    sin2 = g.math('SUBTRACT', 1.0, g.math('MULTIPLY', cos_i, cos_i))
    cos_t = g.math('SQRT', g.math('SUBTRACT', 1.0, g.math('DIVIDE', sin2, film_n * film_n)))
    u = g.math('DIVIDE', g.math('MULTIPLY', thickness, cos_t), dmax)
    cmb = g.n('ShaderNodeCombineXYZ', in_Y=0.5)
    g.link(clamp01(g, u), cmb.inputs['X'])
    tex = g.n('ShaderNodeTexImage', interpolation='Linear', extension='EXTEND')
    tex.image = lut_img
    g.link(cmb.outputs['Vector'], tex.inputs['Vector'])
    return tex.outputs['Color']


def layer_params(g, L, p, lut_img, dmax, metal):
    """one layer spec -> dict of sockets/values: color, metallic, rough, ior, tint"""
    out = {'metallic': float(L.get('metallic', 1.0)), 'rough': float(L.get('roughness', 0.3)),
           'ior': float(L.get('ior', 1.5)), 'tint': tuple(L.get('f82', (1.0, 1.0, 1.0))), 'film': None}
    film = L.get('film')
    if film:
        if 'stops' in film:
            th = ramp(g, p if p is not None else 0.0, film['stops'], film.get('interp', 'LINEAR'), scale=dmax)
        else:
            th = float(film['nm'])
        if film.get('jitter_nm'):  # anodize current-density non-uniformity: +-few nm mottling
            th = g.math('ADD', th, g.math('MULTIPLY', g.math('SUBTRACT', noise(g, g.n('ShaderNodeTexCoord').outputs['Object'],
                                                                                  1.0 / 0.006, 3.0), 0.5), 2 * film['jitter_nm']))
        out['film'] = th
        out['tint'] = (0.92, 0.92, 0.92)
    else:
        out['color'] = tuple(L.get('base_color_lin', metal['base_color_lin']))
    return out


def build_coat(spec, metal, lut_img, dmax, arc_m, edge_break_m):
    mat = bpy.data.materials.new('coat:' + spec['id'])
    g = G(mat)
    out = g.n('ShaderNodeOutputMaterial', target='CYCLES')
    bsdf = g.n('ShaderNodeBsdfPrincipled', distribution='MULTI_GGX')
    g.link(bsdf.outputs['BSDF'], out.inputs['Surface'])
    tc = g.n('ShaderNodeTexCoord'); P = tc.outputs['Object']
    s, t = attr(g, 'finish_s'), attr(g, 'finish_t')
    p = pattern(g, spec.get('pattern', {'kind': 'none'}), P, s, t, arc_m)
    layers = spec['layers']
    L0 = layer_params(g, layers[0], p, lut_img, dmax, metal)
    if len(layers) > 1:
        L1 = layer_params(g, layers[1], p, lut_img, dmax, metal)
        m = ramp(g, p, spec.get('mix_stops', [[0, 0], [1, 1]])) if p is not None else 0.0
    else:
        L1, m = None, 0.0

    # edge wear: convex edges (Bevel normal deviates from smooth normal) burnished back to bare Ti
    wear = None
    ew = spec.get('edge_wear')
    geo = g.n('ShaderNodeNewGeometry')
    if ew and ew.get('amount', 0) > 0:
        bev = g.n('ShaderNodeBevel', samples=8, in_Radius=ew.get('width_mm', 0.35) * 1e-3)
        d = g.math('SUBTRACT', 1.0, g.math('DOT_PRODUCT', bev.outputs['Normal'], geo.outputs['Normal'], vector=True))
        e = maprange(g, d, ew.get('lo', 0.01), ew.get('hi', 0.08), smooth=True)
        brk = maprange(g, noise(g, P, 1.0 / 0.0015, 6.0, 0.7), 0.35, 0.65, smooth=True)
        wear = clamp01(g, g.math('MULTIPLY', g.math('MULTIPLY', e, brk), ew['amount']))

    def colour_of(Lp):
        if Lp['film'] is not None:
            return thinfilm_color(g, Lp['film'], lut_img, dmax, spec.get('film_n', 2.33))
        return Lp['color']

    c0 = colour_of(L0)
    col = lerp_rgb(g, c0, colour_of(L1), m) if L1 else c0
    met = lerp(g, L0['metallic'], L1['metallic'], m) if L1 else L0['metallic']
    rgh = lerp(g, L0['rough'], L1['rough'], m) if L1 else L0['rough']
    ior = lerp(g, L0['ior'], L1['ior'], m) if L1 else L0['ior']
    tint = lerp_rgb(g, L0['tint'], L1['tint'], m) if L1 else L0['tint']
    if wear is not None:
        col = lerp_rgb(g, col, tuple(metal['base_color_lin']), wear)
        met = lerp(g, met, 1.0, wear)
        rgh = lerp(g, rgh, ew.get('worn_roughness', 0.18), wear)
        tint = lerp_rgb(g, tint, tuple(metal['f82_tint']), wear)
    # cavity: local AO darkens & roughens recesses (oxide/grime build-up in slots, ring grooves)
    cav = spec.get('cavity')
    if cav and cav.get('amount', 0) > 0:
        ao = g.n('ShaderNodeAmbientOcclusion', only_local=True, samples=8, in_Distance=cav.get('distance_mm', 1.5) * 1e-3)
        c = g.math('MULTIPLY', g.math('SUBTRACT', 1.0, ao.outputs['AO']), cav['amount'])
        col = lerp_rgb(g, col, (0.0, 0.0, 0.0), clamp01(g, g.math('MULTIPLY', c, 0.6)))
        rgh = g.math('ADD', rgh, g.math('MULTIPLY', c, 0.25))
    # micro surface + shading-only edge break
    normal = None
    if edge_break_m:
        normal = g.n('ShaderNodeBevel', samples=4, in_Radius=edge_break_m).outputs['Normal']
    normal, droff = micro_surface(g, spec, P, normal)
    if droff:
        rgh = g.math('ADD', rgh, droff)
    if spec.get('roughness_var'):
        rgh = g.math('ADD', rgh, g.math('MULTIPLY', g.math('SUBTRACT', noise(g, P, 1.0 / 0.01, 3.0), 0.5), 2 * spec['roughness_var']))
    if normal is not None:
        g.link(normal, bsdf.inputs['Normal'])
    _set(g, bsdf.inputs['Base Color'], col)
    _set(g, bsdf.inputs['Metallic'], met)
    _set(g, bsdf.inputs['Roughness'], clamp01(g, rgh) if not isinstance(rgh, float) else rgh)
    _set(g, bsdf.inputs['IOR'], ior)
    _set(g, bsdf.inputs['Specular Tint'], tint)
    if spec.get('anisotropy'):
        bsdf.inputs['Anisotropic'].default_value = float(spec['anisotropy'])
        _, tw = materials._tangent_world(g)
        g.link(tw, bsdf.inputs['Tangent'])
    coat = spec.get('clearcoat')
    if coat:
        bsdf.inputs['Coat Weight'].default_value = float(coat.get('weight', 1.0))
        bsdf.inputs['Coat Roughness'].default_value = float(coat.get('roughness', 0.05))
        bsdf.inputs['Coat IOR'].default_value = float(coat.get('ior', 1.5))
    return mat


def debug_material(i):
    mat = bpy.data.materials.new(f'maskdbg:{ZONES[i]}')
    g = G(mat)
    out = g.n('ShaderNodeOutputMaterial', target='CYCLES')
    b = g.n('ShaderNodeBsdfPrincipled')
    g.link(b.outputs['BSDF'], out.inputs['Surface'])
    b.inputs['Base Color'].default_value = (*ZONE_RGB[i], 1.0)
    b.inputs['Roughness'].default_value = 0.55
    return mat


def apply(obj, lib, base_finish):
    z = np.load(lib['masks_npz'])
    zone, s, t = z['zone'].astype(np.int32), z['s'], z['t']
    me = obj.data
    if len(zone) != len(me.polygons) or len(s) != len(me.vertices):
        raise ValueError('finish masks do not match this mesh (face/vertex count) -- rerun blade_mask')
    for name, arr in (('finish_s', s), ('finish_t', t)):
        a = me.attributes.new(name, 'FLOAT', 'POINT')
        a.data.foreach_set('value', arr.astype(np.float32))
    me.update()
    spec = lib['entry']
    me.materials.clear()
    rec = {}
    if spec.get('type') == 'mask_debug':
        for i in range(len(ZONES)):
            me.materials.append(debug_material(i)); rec[ZONES[i]] = 'mask_debug'
        return _set_zones(me, zone, rec)
    lut = np.load(lib['lut_npy']).astype(np.float32)
    img = bpy.data.images.new('tf_lut', width=len(lut), height=1, float_buffer=True, alpha=False)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(np.concatenate([lut, np.ones((len(lut), 1), np.float32)], 1).ravel())
    metal = base_finish['metal']
    eb = base_finish.get('edge_break_mm', 0.0) * 1e-3
    me.materials.append(build_coat(spec, metal, img, float(lib.get('lut_dmax_nm', 480.0)),
                                   float(lib.get('arc_length_m', 0.2)), eb))
    rec['coat'] = spec['id']
    bare = dict(BARE_DEFAULT, **spec.get('bare', {}))
    specs = dict(base_finish['finishes'], **lib.get('bare_specs', {}))
    for zn in ZONES[1:]:
        fname = bare[zn]
        if specs[fname].get('thin_film_nm') or specs[fname].get('layers'):
            raise ValueError(f'bare blade zone {zn} may not use a coated finish ({fname})')
        me.materials.append(materials.build_finish(f'{zn}:{fname}', specs[fname], metal, eb))
        rec[zn] = fname
    return _set_zones(me, zone, rec)


def _set_zones(me, zone, rec):
    """material_index = zone, set AFTER slots exist, then read back: fail loudly on any mismatch."""
    me.polygons.foreach_set('material_index', zone)
    me.update()
    chk = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('material_index', chk)
    if not np.array_equal(chk, zone) or len(me.materials) != len(ZONES):
        raise RuntimeError('zone -> material_index assignment failed; refusing to render (blade could be coated)')
    rec['zone_face_counts'] = {ZONES[i]: int((chk == i).sum()) for i in range(len(ZONES))}
    return rec
