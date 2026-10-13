"""Ti-6Al-4V finish materials (Cycles, Principled BSDF v2, Blender 4.2 LTS).

Blender 4.2's Principled metal is the F82-tint conductor: Base Color = normal-incidence F0, Specular
Tint = F82 tint. Values come from presets/finish_ti64.json and are literature-based
(appearance_assumed), not a measured coating. Shading-only effects (bump, Bevel-node edge rounding)
never move vertices.
"""
import bpy

LABELS = ['body', 'bevel', 'edge_apex', 'serration', 'ring', 'pad', 'spine']


class G:
    """Tiny node-graph helper."""

    def __init__(self, mat):
        mat.use_nodes = True
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def n(self, kind, **props):
        node = self.nt.nodes.new(kind)
        node.location = (self.x, 0)
        self.x -= 220
        for k, v in props.items():
            if k.startswith('in_'):
                node.inputs[k[3:].replace('_', ' ')].default_value = v
            else:
                setattr(node, k, v)
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=None, vector=False):
        node = self.n('ShaderNodeVectorMath' if vector else 'ShaderNodeMath', operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float, tuple, list)):
                node.inputs[i].default_value = v
            else:
                self.link(v, node.inputs[i])
        return node.outputs[0] if not vector or op not in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else node.outputs['Value']


def _tangent_world(g):
    attr = g.n('ShaderNodeAttribute', attribute_name='finish_tangent', attribute_type='GEOMETRY')
    vt = g.n('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='OBJECT', convert_to='WORLD')
    g.link(attr.outputs['Vector'], vt.inputs['Vector'])
    return attr.outputs['Vector'], vt.outputs['Vector']


def _bump_chain(g, height, strength, distance_m, normal_in=None):
    b = g.n('ShaderNodeBump', in_Strength=strength, in_Distance=distance_m)
    g.link(height, b.inputs['Height'])
    if normal_in is not None:
        g.link(normal_in, b.inputs['Normal'])
    return b.outputs['Normal']


def _edge_break(g, radius_m, samples=4):
    bev = g.n('ShaderNodeBevel', samples=samples, in_Radius=radius_m)
    return bev.outputs['Normal']


def build_finish(name, spec, metal, edge_break_m):
    """One material per region finish spec (dict from finish_ti64.json 'regions')."""
    mat = bpy.data.materials.new(name)
    g = G(mat)
    out = g.n('ShaderNodeOutputMaterial', target='CYCLES')
    bsdf = g.n('ShaderNodeBsdfPrincipled', distribution='MULTI_GGX')
    g.link(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Metallic'].default_value = 1.0
    bsdf.inputs['Base Color'].default_value = (*metal['base_color_lin'], 1.0)
    bsdf.inputs['Specular Tint'].default_value = (*metal['f82_tint'], 1.0)
    rough = float(spec['roughness'])
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Anisotropic'].default_value = float(spec.get('anisotropy', 0.0))
    if spec.get('anisotropy', 0.0) > 0:
        _, t_world = _tangent_world(g)
        g.link(t_world, bsdf.inputs['Tangent'])

    # shading normal: Bevel-node edge rounding (shading only) -> optional micro bump
    radius = spec.get('bevel_radius_mm')
    normal = None
    if radius or edge_break_m:
        normal = _edge_break(g, (radius * 1e-3) if radius else edge_break_m, int(spec.get('bevel_samples', 4)))
    tc = g.n('ShaderNodeTexCoord')
    P = tc.outputs['Object']
    micro = spec.get('micro', 'none')
    rough_sock = None
    if micro == 'bead_blast':
        sc = 1.0 / (spec.get('grain_um', 40) * 1e-6)
        vor = g.n('ShaderNodeTexVoronoi', feature='F1', distance='EUCLIDEAN', in_Scale=sc, in_Randomness=1.0)
        g.link(P, vor.inputs['Vector'])
        nz = g.n('ShaderNodeTexNoise', in_Scale=sc * 0.5, in_Detail=2.0)
        g.link(P, nz.inputs['Vector'])
        h = g.math('ADD', vor.outputs['Distance'], g.math('MULTIPLY', nz.outputs['Fac'], 0.5))
        normal = _bump_chain(g, h, spec.get('bump', 0.04), 1e-5, normal)
        # mm-scale satin mottling of roughness (+-0.04): reads as a real blasted surface, not CG flat
        mot = g.n('ShaderNodeTexNoise', in_Scale=1.0 / 0.004, in_Detail=3.0)
        g.link(P, mot.inputs['Vector'])
        rough_sock = g.math('ADD', g.math('MULTIPLY', g.math('SUBTRACT', mot.outputs['Fac'], 0.5), 0.08), rough)
    elif micro == 'stonewash':
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
        mot = g.n('ShaderNodeTexNoise', in_Scale=1.0 / 0.003, in_Detail=4.0)
        g.link(P, mot.inputs['Vector'])
        lo, hi = spec.get('roughness_range', [0.18, 0.45])
        mr = g.n('ShaderNodeMapRange', in_To_Min=lo, in_To_Max=hi)
        g.link(mot.outputs['Fac'], mr.inputs['Value'])
        mr.inputs['From Min'].default_value = 0.35
        mr.inputs['From Max'].default_value = 0.65
        rough_sock = mr.outputs['Result']
    elif micro == 'satin_lines':
        # fine grind lines along the finish tangent: 1D noise across b = N x T, stretched ~200:1
        t_obj, _ = _tangent_world(g)
        geo = g.n('ShaderNodeNewGeometry')
        nT = g.n('ShaderNodeVectorTransform', vector_type='NORMAL', convert_from='WORLD', convert_to='OBJECT')
        g.link(geo.outputs['Normal'], nT.inputs['Vector'])
        b = g.math('CROSS_PRODUCT', nT.outputs['Vector'], t_obj, vector=True)
        across = g.math('DOT_PRODUCT', P, b, vector=True)
        along = g.math('DOT_PRODUCT', P, t_obj, vector=True)
        cmb = g.n('ShaderNodeCombineXYZ')
        g.link(g.math('MULTIPLY', across, 1.0 / 15e-6), cmb.inputs['X'])
        g.link(g.math('MULTIPLY', along, 1.0 / (15e-6 * spec.get('stretch', 200))), cmb.inputs['Y'])
        nz = g.n('ShaderNodeTexNoise', noise_dimensions='2D', in_Scale=1.0, in_Detail=4.0)
        g.link(cmb.outputs['Vector'], nz.inputs['Vector'])
        normal = _bump_chain(g, nz.outputs['Fac'], spec.get('bump', 0.03), 5e-6, normal)
    if rough_sock is not None:
        g.link(rough_sock, bsdf.inputs['Roughness'])
    if normal is not None:
        g.link(normal, bsdf.inputs['Normal'])
    if 'thin_film_nm' in spec:
        bsdf.inputs['Thin Film Thickness'].default_value = float(spec['thin_film_nm'])
        bsdf.inputs['Thin Film IOR'].default_value = float(spec.get('thin_film_ior', 2.4))
    return mat


def assign(obj, finish, accents=()):
    """Create one material slot per region label (fixed order = region_id) and return a record."""
    metal = finish['metal']
    edge_break_m = finish.get('edge_break_mm', 0.0) * 1e-3
    chosen = dict(finish['default_assignment'])
    for a in accents or ():
        if a not in LABELS:
            raise ValueError(f'unknown accent region {a!r}')
        chosen[a] = finish.get('accent_finish', 'anodized_bronze')
    obj.data.materials.clear()
    rec = {}
    for lab in LABELS:
        fname = chosen[lab]
        spec = finish['finishes'][fname]
        m_lab = {**metal, **finish.get('region_metal', {}).get(lab, {})}
        obj.data.materials.append(build_finish(f'{lab}:{fname}', spec, m_lab, edge_break_m))
        rec[lab] = fname
    return rec


def floor_material(spec):
    mat = bpy.data.materials.new('floor')
    g = G(mat)
    out = g.n('ShaderNodeOutputMaterial', target='CYCLES')
    bsdf = g.n('ShaderNodeBsdfPrincipled')
    g.link(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (*spec['base_color'], 1.0)
    bsdf.inputs['Roughness'].default_value = spec['roughness']
    bsdf.inputs['Coat Weight'].default_value = spec.get('coat', 0.0)
    bsdf.inputs['Coat Roughness'].default_value = spec.get('coat_roughness', 0.03)
    bsdf.inputs['Specular IOR Level'].default_value = spec.get('specular', 0.5)
    return mat


def flat_emission(name, rgb_lin):
    mat = bpy.data.materials.new(name)
    g = G(mat)
    out = g.n('ShaderNodeOutputMaterial', target='CYCLES')
    em = g.n('ShaderNodeEmission', in_Strength=1.0)
    em.inputs['Color'].default_value = (*rgb_lin, 1.0)
    g.link(em.outputs['Emission'], out.inputs['Surface'])
    return mat


# ---------------------------------------------------------------- maker's mark (signature decal)
SIG_AOV = 'sig'


def _sig_mask(g, placements, image, spec):
    """Shader-space mask (0..1) of the signature: planar projection in OBJECT space (rotates with the
    part), clipped to the face plane (+-depth_tol) and to faces whose normal matches the placement."""
    tc = g.n('ShaderNodeTexCoord')
    geo = g.n('ShaderNodeNewGeometry')
    nobj = g.n('ShaderNodeVectorTransform', vector_type='NORMAL', convert_from='WORLD', convert_to='OBJECT')
    g.link(geo.outputs['Normal'], nobj.inputs['Vector'])
    P = tc.outputs['Object']
    total = None
    tol = float(spec.get('depth_tol_mm', 0.25)) * 1e-3
    for pl in placements:
        d = g.math('SUBTRACT', P, tuple(pl['center_m']), vector=True)
        uu = g.math('ADD', g.math('MULTIPLY', g.math('DOT_PRODUCT', d, tuple(pl['u_axis']), vector=True),
                                  1.0 / pl['width_m']), 0.5)
        vv = g.math('ADD', g.math('MULTIPLY', g.math('DOT_PRODUCT', d, tuple(pl['v_axis']), vector=True),
                                  1.0 / pl['height_m']), 0.5)
        cmb = g.n('ShaderNodeCombineXYZ')
        g.link(uu, cmb.inputs['X'])
        g.link(vv, cmb.inputs['Y'])
        tex = g.n('ShaderNodeTexImage', interpolation='Cubic', extension='CLIP')
        img = bpy.data.images.load(pl.get('mask') or image, check_existing=True)
        img.colorspace_settings.name = 'Non-Color'
        tex.image = img
        g.link(cmb.outputs['Vector'], tex.inputs['Vector'])
        # crisp edge: smoothstep 0.3..0.7 on the antialiased mask
        mr = g.n('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        mr.inputs['From Min'].default_value = 0.3
        mr.inputs['From Max'].default_value = 0.7
        g.link(tex.outputs['Color'], mr.inputs['Value'])
        depth = g.math('ABSOLUTE', g.math('DOT_PRODUCT', d, tuple(pl['normal']), vector=True))
        on_plane = g.math('LESS_THAN', depth, tol)
        facing = g.math('GREATER_THAN', g.math('DOT_PRODUCT', nobj.outputs['Vector'], tuple(pl['normal']),
                                               vector=True), 0.9)
        m = g.math('MULTIPLY', g.math('MULTIPLY', mr.outputs['Result'], on_plane), facing)
        total = m if total is None else g.math('MAXIMUM', total, m)
    return total


def apply_signature(obj, placements, mask_path, spec):
    """Mix a matte near-black mark into EVERY material slot of obj, as the final overlay before the
    output node (laser/black-marked Ti: roughness ~0.9, no specular). Also writes the mask to the
    'sig' shader AOV so QA can measure on-screen visibility (camera rays only: occlusion-aware)."""
    placements = [p for p in placements if p.get('ok')]
    if not placements:
        return {'applied': False, 'reason': 'no placement'}
    img = mask_path  # default mask; a placement's own stroke-weight variant wins
    vl = bpy.context.view_layer
    if SIG_AOV not in [a.name for a in vl.aovs]:
        a = vl.aovs.add()
        a.name = SIG_AOV
        a.type = 'VALUE'
    for mat in obj.data.materials:
        nt = mat.node_tree
        out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
        src = out.inputs['Surface'].links[0].from_socket
        g = G.__new__(G)
        g.nt, g.x = nt, -2000
        mask = _sig_mask(g, placements, img, spec)
        mark = g.n('ShaderNodeBsdfPrincipled', distribution='MULTI_GGX')
        mark.inputs['Base Color'].default_value = (*spec['base_color_lin'], 1.0)
        mark.inputs['Metallic'].default_value = 0.0
        mark.inputs['Roughness'].default_value = float(spec['roughness'])
        mark.inputs['Specular IOR Level'].default_value = float(spec['specular_ior_level'])
        mark.inputs['Coat Weight'].default_value = 0.0
        mix = g.n('ShaderNodeMixShader')
        mix.name = mix.label = 'signature_overlay'
        g.link(mask, mix.inputs['Fac'])
        g.link(src, mix.inputs[1])
        g.link(mark.outputs['BSDF'], mix.inputs[2])
        g.link(mix.outputs['Shader'], out.inputs['Surface'])
        aov = g.n('ShaderNodeOutputAOV')
        aov.aov_name = SIG_AOV
        g.link(mask, aov.inputs['Value'])
    return {'applied': True, 'materials': [m.name for m in obj.data.materials], 'mask_image': sorted({p.get('mask') or mask_path for p in placements}),
            'aov': SIG_AOV, 'finish': {k: spec[k] for k in ('base_color_lin', 'roughness', 'specular_ior_level')}}
