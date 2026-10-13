"""SWITCHBACK pro-hero stills: art-directed, QA-gated, deterministic. Blender 4.2 / Cycles OptiX.
blender -b -P pro_hero.py -- --prep DIR --out DIR [--shots a,b] [--res 4k|8k] [--spp N] [--cfg shots.json]
Inputs come from prep.py (normal-repaired mesh, art mapping, signature placements). Outputs per shot:
  <shot>_<res>.exr     32-bit float multilayer master, ZIP (lossless): Combined, Normal, Depth, IndexOB, AOV sig
  <shot>_<res>.png     16-bit RGB, AgX view transform applied (display-referred sRGB)
  <shot>_<res>.qa.json per-shot QA (lights out of frame incl. floor mirror, signature in frame & unoccluded,
                       signature glyph-on-flat margin, clipping)."""
import json, math, os, sys, hashlib, time
HERE = os.path.dirname(os.path.abspath(__file__))
MK = os.path.join(HERE, '..', 'marketing')
sys.path.insert(0, os.path.join(MK, 'blender')); sys.path.insert(0, HERE)
from runtime import ensure_memcap, GIB
ensure_memcap(blender=True)   # Establish the hard cap before reading user-supplied inputs.

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
A = dict(zip(argv[::2], argv[1::2]))
PREP = os.path.expanduser(A['--prep']); OUT = os.path.expanduser(A['--out']); os.makedirs(OUT, exist_ok=True)
CFG = json.load(open(A.get('--cfg', os.path.join(HERE, 'shots.json'))))
RES = A.get('--res', '4k'); RX, RY = CFG['resolutions'][RES]
SPP = int(A.get('--spp', CFG['spp']))
THREADS = ensure_memcap(fixed_bytes=2 * GIB + RX * RY * 256, blender=True)
import bpy, numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
import scene, lights, materials
import prep as P   # sig_uv shared with the layout solver
import qa as Q
MAN = json.load(open(os.path.join(PREP, 'prep.json')))
LOOK = CFG['look']

scene.reset()
d = dict(np.load(os.path.join(PREP, 'mesh.npz')))
part = scene.build_part(d)
V = d['V']; lo, hi = V.min(0), V.max(0); D = float(np.linalg.norm(hi - lo))
labels = json.load(open(os.path.join(PREP, 'regions.json')))['labels']


def mk(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); return m, nt, nt.nodes.new, nt.links.new


def math_node(N, L, op, a, b=None):
    n = N('ShaderNodeMath'); n.operation = op
    for i, x in enumerate((a, b)):
        if x is None: continue
        if isinstance(x, (int, float)): n.inputs[i].default_value = float(x)
        else: L(x, n.inputs[i])
    return n.outputs[0]


def mix_rgb(N, L, f, a, b):
    mx = N('ShaderNodeMix'); mx.data_type = 'RGBA'; L(f, mx.inputs['Factor'])
    for idx, x in ((6, a), (7, b)):
        if isinstance(x, tuple): mx.inputs[idx].default_value = x
        else: L(x, mx.inputs[idx])
    return mx.outputs[2]


def mix_f(N, L, f, a, b):
    mx = N('ShaderNodeMix'); mx.data_type = 'FLOAT'; L(f, mx.inputs['Factor'])
    for idx, x in ((2, a), (3, b)):
        if isinstance(x, (int, float)): mx.inputs[idx].default_value = float(x)
        else: L(x, mx.inputs[idx])
    return mx.outputs[0]


def obj_xyz(N, L):
    tc = N('ShaderNodeTexCoord'); s = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Object'], s.inputs[0]); return s


def side_select(N, L):
    """back = 1 where the TRUE normal points +Y (object space); face = 1 on broad faces (|n.y| > 0.9)."""
    geo = N('ShaderNodeNewGeometry'); vt = N('ShaderNodeVectorTransform')
    vt.vector_type = 'NORMAL'; vt.convert_from = 'WORLD'; vt.convert_to = 'OBJECT'
    L(geo.outputs['True Normal'], vt.inputs[0]); s = N('ShaderNodeSeparateXYZ'); L(vt.outputs[0], s.inputs[0])
    back = math_node(N, L, 'GREATER_THAN', s.outputs['Y'], 0.0)
    ab = math_node(N, L, 'ABSOLUTE', s.outputs['Y'])
    fr = N('ShaderNodeMapRange'); L(ab, fr.inputs['Value']); fr.inputs['From Min'].default_value = 0.80
    fr.inputs['From Max'].default_value = 0.92
    return back, fr.outputs['Result']


def art_uv(N, L, xyz):
    a = MAN['art']
    u = math_node(N, L, 'MULTIPLY_ADD', xyz.outputs['X'], 1.0 / a['width_m']); u.node.inputs[2].default_value = -a['x0_m'] / a['width_m']
    v = math_node(N, L, 'MULTIPLY_ADD', xyz.outputs['Z'], 1.0 / a['height_m']); v.node.inputs[2].default_value = 0.5 - a['z_mid_m'] / a['height_m']
    c = N('ShaderNodeCombineXYZ'); L(u, c.inputs['X']); L(v, c.inputs['Y']); return c.outputs[0]


def sig_mask(N, L, xyz, side, mask_path=None):
    """Same transform as prep.sig_uv; ink px window -> mask uv."""
    S = MAN['signature']; p = S['placements'][side]
    L_m, H_m = p['len_mm'] * 1e-3, p['h_mm'] * 1e-3
    cx, cz = p['center_xz_m']; th = math.radians(p['angle_deg']); c, s_ = math.cos(th), math.sin(th)
    sx = -1.0 if side == 'back' else 1.0
    dx = math_node(N, L, 'ADD', xyz.outputs['X'], -cx); dx = math_node(N, L, 'MULTIPLY', dx, sx)
    dz = math_node(N, L, 'ADD', xyz.outputs['Z'], -cz)
    su = math_node(N, L, 'ADD', math_node(N, L, 'MULTIPLY', dx, c / L_m), math_node(N, L, 'MULTIPLY', dz, s_ / L_m))
    su = math_node(N, L, 'ADD', su, 0.5)
    tv = math_node(N, L, 'ADD', math_node(N, L, 'MULTIPLY', dx, -s_ / H_m), math_node(N, L, 'MULTIPLY', dz, c / H_m))
    tv = math_node(N, L, 'ADD', tv, 0.5)
    W_px, H_px = S['mask_px']; x0, y0, x1, y1 = S['ink_px']
    # ink window -> full mask uv (v from bottom)
    U = math_node(N, L, 'MULTIPLY_ADD', su, (x1 - x0) / W_px); U.node.inputs[2].default_value = x0 / W_px
    Vv = math_node(N, L, 'MULTIPLY_ADD', tv, (y1 - y0) / H_px); Vv.node.inputs[2].default_value = (H_px - y1) / H_px
    cmb = N('ShaderNodeCombineXYZ'); L(U, cmb.inputs['X']); L(Vv, cmb.inputs['Y'])
    t = N('ShaderNodeTexImage'); t.image = bpy.data.images.load(mask_path or S['mask'], check_existing=True)
    t.image.colorspace_settings.name = 'Non-Color'; t.extension = 'CLIP'; t.interpolation = 'Cubic'
    L(cmb.outputs[0], t.inputs['Vector']); return t.outputs['Color']


def art_material():
    m, nt, N, L = mk('pro_art_metal')
    out = N('ShaderNodeOutputMaterial', ); out.target = 'CYCLES'
    xyz = obj_xyz(N, L); back, face = side_select(N, L)
    tex = N('ShaderNodeTexImage'); tex.image = bpy.data.images.load(MAN['art']['path'], check_existing=True)
    tex.image.colorspace_settings.name = 'sRGB'; tex.interpolation = 'Cubic'; tex.extension = 'EXTEND'
    L(art_uv(N, L, xyz), tex.inputs['Vector'])
    # thin-film-like view-angle hue drift (anodized Ti look): hue += k * (1 - facing)
    lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    hue = math_node(N, L, 'MULTIPLY_ADD', lw.outputs['Facing'], LOOK['hue_shift']); hue.node.inputs[2].default_value = 0.5
    hsv = N('ShaderNodeHueSaturation'); L(hue, hsv.inputs['Hue']); L(tex.outputs['Color'], hsv.inputs['Color'])
    hsv.inputs['Saturation'].default_value = LOOK['sat']; hsv.inputs['Value'].default_value = LOOK['val']
    # deep blacks -> polished dark Ti
    bw = N('ShaderNodeRGBToBW'); L(tex.outputs['Color'], bw.inputs[0])
    k = N('ShaderNodeMapRange'); L(bw.outputs[0], k.inputs['Value']); k.inputs['From Min'].default_value = LOOK['black_lo']
    k.inputs['From Max'].default_value = LOOK['black_hi']
    col = mix_rgb(N, L, k.outputs['Result'], tuple(LOOK['dark_ti']) + (1,), hsv.outputs[0])
    col = mix_rgb(N, L, face, tuple(LOOK['wall_ti']) + (1,), col)             # side walls: dark polished Ti band
    metal = mix_f(N, L, k.outputs['Result'], LOOK['black_metallic'], LOOK['art_metallic'])
    sig = mix_f(N, L, back, sig_mask(N, L, xyz, 'front'), sig_mask(N, L, xyz, 'back'))
    sig = math_node(N, L, 'MULTIPLY', sig, face)
    bs = N('ShaderNodeBsdfPrincipled')
    L(col, bs.inputs['Base Color']); L(metal, bs.inputs['Metallic'])
    bs.inputs['Roughness'].default_value = LOOK['art_rough']
    L(col, bs.inputs['Specular Tint'])
    bs.inputs['Coat Weight'].default_value = LOOK['coat']; bs.inputs['Coat Roughness'].default_value = LOOK['coat_rough']
    bs.inputs['Thin Film Thickness'].default_value = LOOK['film_nm']; bs.inputs['Thin Film IOR'].default_value = 2.3
    L(protect_signature(N, L, sig, bs.outputs[0]), out.inputs['Surface'])
    aov = N('ShaderNodeOutputAOV'); aov.aov_name = 'sig'; L(sig, aov.inputs['Value'])
    return m


def ti_material():
    m, nt, N, L = mk('pro_ground_ti'); out = N('ShaderNodeOutputMaterial'); bs = N('ShaderNodeBsdfPrincipled')
    G_ = CFG['protected']   # design-wide ground-Ti look (#53: identical in every finish)
    bs.inputs['Base Color'].default_value = (*G_['grind_rgb'], 1); bs.inputs['Metallic'].default_value = 1
    bs.inputs['Roughness'].default_value = G_['grind_roughness']
    for key in ('Coat Weight', 'Thin Film Thickness', 'Anisotropic', 'Emission Strength'):
        bs.inputs[key].default_value = 0
    L(bs.outputs[0], out.inputs['Surface'])
    aov = N('ShaderNodeOutputAOV'); aov.aov_name = 'sig'; aov.inputs['Value'].default_value = 0.0
    return m


def protect_signature(N, L, sig, finish):
    """The maker mark is its own protected region: one design-wide glossy BLACK ink (dielectric), independent of
    every finish knob (#53/#55). Values come from CFG['protected']['mark']; missing keys are a hard failure."""
    M = CFG['protected']['mark']
    bare = N('ShaderNodeBsdfPrincipled'); bare.name = 'protected_laser_etched_ti'   # node name pinned by #53 tests
    bare.inputs['Base Color'].default_value = (*M['base_rgb'], 1)
    bare.inputs['Metallic'].default_value = M['metallic']
    bare.inputs['Roughness'].default_value = M['roughness']
    bare.inputs['IOR'].default_value = M['ior']
    bare.inputs['Specular IOR Level'].default_value = M['specular_ior_level']   # clearcoat-like gloss without Coat
    for key in ('Coat Weight', 'Thin Film Thickness', 'Anisotropic', 'Emission Strength'):
        bare.inputs[key].default_value = 0
    mix = N('ShaderNodeMixShader')
    # Any ink coverage is protected, including antialiased stroke boundaries.
    L(math_node(N, L, 'GREATER_THAN', sig, 0.0), mix.inputs[0])
    L(finish, mix.inputs[1]); L(bare.outputs[0], mix.inputs[2])
    return mix.outputs[0]


def lut_image(name, rows):
    im = bpy.data.images.new(name, len(rows), 1, float_buffer=True)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels = [c for rgb in rows for c in (*rgb, 1.0)]; return im


def flame_material():
    """Heat-anodized Ti flame: oxide thickness d(s) along the arc (ring end -> tip), interference colour
    baked into the conductor F0 (Base Color) and F82 tint (Specular Tint) by anodize.film_metal."""
    F = CFG['flame']; lut = json.load(open(os.path.join(HERE, F['lut'])))
    m, nt, N, L = mk('pro_flame_heat'); out = N('ShaderNodeOutputMaterial')
    xyz = obj_xyz(N, L); back, face = side_select(N, L)
    x0, x1 = float(lo[0]), float(hi[0])
    s = math_node(N, L, 'MULTIPLY_ADD', xyz.outputs['X'], 1.0 / (x1 - x0)); s.node.inputs[2].default_value = -x0 / (x1 - x0)
    # gentle flame licks: thickness also rises toward the spine/edge (z) a little
    lick = math_node(N, L, 'MULTIPLY', math_node(N, L, 'SINE', math_node(N, L, 'MULTIPLY', xyz.outputs['Z'], F['lick_freq'])), F['lick_amp'])
    s = math_node(N, L, 'ADD', s, lick)
    d0, d1 = F['d_start_nm'], F['d_end_nm']; ld0, ld1 = lut['d_nm'][0], lut['d_nm'][-1]
    # s -> d -> lut u
    dn = math_node(N, L, 'MULTIPLY_ADD', s, (d1 - d0) / (ld1 - ld0)); dn.node.inputs[2].default_value = (d0 - ld0) / (ld1 - ld0)
    dn = math_node(N, L, 'MINIMUM', math_node(N, L, 'MAXIMUM', dn, 0.0), 1.0)
    cmb = N('ShaderNodeCombineXYZ'); L(dn, cmb.inputs['X']); cmb.inputs['Y'].default_value = 0.5
    def lut_tex(name, rows):
        t = N('ShaderNodeTexImage'); t.image = lut_image(name, rows); t.interpolation = 'Linear'; t.extension = 'EXTEND'
        L(cmb.outputs[0], t.inputs['Vector']); return t.outputs['Color']
    f0 = lut_tex('lut_f0', lut['f0']); f82 = lut_tex('lut_f82', lut['f82'])
    outer = mix_f(N, L, back, sig_mask(N, L, xyz, 'front'), sig_mask(N, L, xyz, 'back'))
    outer = math_node(N, L, 'MULTIPLY', outer, face)
    inner_p = F.get('sig_inner_mask')
    if inner_p:   # gold = inner glyph; keyline = outer - inner (thin dark polished Ti outline for contrast)
        ip = os.path.join(HERE, '..', 'brand', 'signature', inner_p)
        sig = mix_f(N, L, back, sig_mask(N, L, xyz, 'front', ip), sig_mask(N, L, xyz, 'back', ip))
        sig = math_node(N, L, 'MULTIPLY', sig, face)
        key = math_node(N, L, 'MAXIMUM', math_node(N, L, 'SUBTRACT', outer, sig), 0.0)
    else:
        sig, key = outer, None
    bs = N('ShaderNodeBsdfPrincipled'); bs.inputs['Metallic'].default_value = 1.0
    if key is not None:
        kc = tuple(F['keyline_rgb']) + (1,)
        f0 = mix_rgb(N, L, key, f0, kc); f82 = mix_rgb(N, L, key, f82, kc)
    L(f0, bs.inputs['Base Color']); L(f82, bs.inputs['Specular Tint'])
    rough = mix_f(N, L, face, F.get('wall_rough', F['rough']), F['rough'])
    if key is not None: rough = mix_f(N, L, key, rough, F['keyline_rough'])
    L(rough, bs.inputs['Roughness'])
    # clearcoat only on the anodized broad faces: not on the inlaid mark/keyline (it washed the gold to cream)
    # and not on walls/recesses (its white reflection blew out the serrations)
    coat = math_node(N, L, 'MULTIPLY', math_node(N, L, 'MULTIPLY', face, math_node(N, L, 'SUBTRACT', 1.0, outer)), F['coat'])
    L(coat, bs.inputs['Coat Weight']); bs.inputs['Coat Roughness'].default_value = F['coat_rough']
    if F.get('aniso'):   # satin brush along the blade arc: tangent circles about the plate normal (Y)
        # tangent = Y x (p - C), C far off the part (brush_center_m): gentle arcs, no singularity on the part.
        # (Radial tangents about the object origin had a pole on the handle flat -> an anisotropic streak line.)
        tc_ = N('ShaderNodeTexCoord'); sub = N('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'
        sub.inputs[1].default_value = tuple(F.get('brush_center_m', [0.0, 0.0, 0.30]))
        crs = N('ShaderNodeVectorMath'); crs.operation = 'CROSS_PRODUCT'; crs.inputs[0].default_value = (0, 1, 0)
        nrm = N('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'
        L(tc_.outputs['Object'], sub.inputs[0]); L(sub.outputs[0], crs.inputs[1]); L(crs.outputs[0], nrm.inputs[0])
        vt = N('ShaderNodeVectorTransform'); vt.vector_type = 'VECTOR'; vt.convert_from = 'OBJECT'; vt.convert_to = 'WORLD'
        L(nrm.outputs[0], vt.inputs[0]); L(vt.outputs[0], bs.inputs['Tangent']); L(math_node(N, L, 'MULTIPLY', face, F['aniso']), bs.inputs['Anisotropic'])
    L(protect_signature(N, L, outer, bs.outputs[0]), out.inputs['Surface'])
    aov = N('ShaderNodeOutputAOV'); aov.aov_name = 'sig'; L(outer, aov.inputs['Value'])
    return m


FINISH = A.get('--finish', CFG.get('finish', 'art'))
if FINISH in CFG.get('finishes', {}):   # named anodize variants ride the thin-film path with overrides
    CFG['flame'] = {**CFG['flame'], **CFG['finishes'][FINISH]}
FILM_PATH = FINISH == 'flame' or FINISH in CFG.get('finishes', {})
if FILM_PATH:
    LOOK['exposure'] = CFG['flame'].get('exposure_ev', LOOK['exposure']); LOOK.update(CFG['flame'].get('look', {}))
    ART_M = flame_material(); TI_M = ti_material()
else:
    ART_M, TI_M = art_material(), ti_material()
for i in range(len(labels)):
    lab = labels[str(i)]
    part.data.materials.append(TI_M if lab in ('bevel', 'edge_apex', 'serration') else ART_M)
part.data.update()

sc = bpy.context.scene
vl = sc.view_layers[0]; a = vl.aovs.add(); a.name = 'sig'; a.type = 'VALUE'
vl.use_pass_normal = vl.use_pass_z = vl.use_pass_object_index = True
rig = json.load(open(os.path.join(MK, 'presets', 'rig_dark_arc_key.json')))
rig['lights'] = rig['lights'] + CFG['extra_lights'] + (CFG['flame'].get('extra_lights', []) if FILM_PATH else [])
_AN = json.load(open(A['--anim'])) if '--anim' in A else {}
FILM_LIGHTS = [L_['name'] for L_ in _AN.get('film_lights', [])]   # off by default; a shot turns them on (enable_lights)
rig['lights'] = rig['lights'] + _AN.get('film_lights', [])
rig['backdrop']['material'].update(CFG.get('floor', {}))
if FILM_PATH:   # named anodize finishes (e.g. satin_blue) get the same floor / light_ev overrides as flame
    rig['backdrop']['material'].update(CFG['flame'].get('floor', {}))
    for Lc in rig['lights']:
        Lc['ev'] = Lc.get('ev', 0.0) + CFG['flame'].get('light_ev', {}).get(Lc['name'], 0.0)
z_floor = float(lo[2])
scene.build_backdrop(rig['backdrop'], D, z_floor, materials.floor_material(rig['backdrop']['material']))

def soften_floor(fc):
    """Owner 2026-10-13: floor reflection ~45 % darker, soft falloff, gentle distance fade (dark + reflective kept)."""
    if not fc: return
    for m in bpy.data.materials:
        if not m.use_nodes: continue
        nt = m.node_tree; P = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED']
        if not P or 'floor' not in m.name.lower() and 'backdrop' not in m.name.lower(): continue
        p = P[0]
        p.inputs['Specular IOR Level'].default_value = fc.get('spec_level', 0.28)
        p.inputs['Coat Weight'].default_value = fc.get('coat', 0.08)
        p.inputs['Base Color'].default_value = (*fc.get('tint', [0.002, 0.002, 0.0025]), 1)
        tc = nt.nodes.new('ShaderNodeTexCoord'); vl = nt.nodes.new('ShaderNodeVectorMath'); vl.operation = 'LENGTH'
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = fc.get('fade_m', [0.06, 0.30])
        mr.inputs['To Min'].default_value = fc.get('roughness', 0.10); mr.inputs['To Max'].default_value = fc.get('rough_far', 0.30)
        nt.links.new(tc.outputs['Object'], vl.inputs[0]); nt.links.new(vl.outputs['Value'], mr.inputs['Value'])
        nt.links.new(mr.outputs['Result'], p.inputs['Roughness'])
        print('floor softened', m.name)
soften_floor(CFG.get('floor_soft'))
hdri = scene.find_hdri(rig['world']['hdri']['file'], rig['world']['hdri']['sha256'],
                       ['~/jarambit_render_scratch/hdri', os.path.join(MK, 'hdri')])
rig['world'].update(CFG.get('world', {}))
scene.build_world(rig['world'], hdri)
light_rec = lights.build(rig, D, np.zeros(3), exposure_scale=2.0 ** (rig['exposure_ev'] + CFG['ev']))
BASE_ENERGY = {o.name: o.data.energy for o in sc.objects if o.type == 'LIGHT'}
BASE_EXPOSURE = None


def apply_shot_light(sh):
    """Per-shot light energy (EV) + exposure for authored film sections (e.g. the brighter science spin).
    Lights in FILM_LIGHTS are dark unless the shot lists them in enable_lights."""
    for n, e0 in BASE_ENERGY.items():
        on = n not in FILM_LIGHTS or n in sh.get('enable_lights', [])
        ev = sh.get('light_ev_all', 0.0) + sh.get('light_ev', {}).get(n, 0.0)
        sc.objects[n].data.energy = e0 * (2.0 ** ev) * (1.0 if on else 0.0)
    if not SCI:
        sc.view_settings.exposure = LOOK['exposure'] + sh.get('exposure_ev_add', 0.0)

r = sc.render; r.engine = 'CYCLES'; r.resolution_x, r.resolution_y, r.resolution_percentage = RX, RY, 100
r.threads_mode = 'FIXED'; r.threads = THREADS
scene.gpu_devices('OPTIX'); cy = sc.cycles; cy.device = 'GPU'
cy.samples = SPP; cy.use_adaptive_sampling = True; cy.adaptive_threshold = CFG['adaptive_threshold']
cy.adaptive_min_samples = min(SPP, 64)
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'; cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
cy.denoising_prefilter = 'ACCURATE'; cy.denoising_quality = 'HIGH'
cy.glossy_bounces = 12; cy.max_bounces = 16; cy.sample_clamp_indirect = 10; cy.blur_glossy = 0.2
cy.use_animated_seed = False; cy.seed = 0
r.use_persistent_data = True; r.film_transparent = False; r.dither_intensity = 1.0  # applied in the float->16-bit PNG conversion
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = LOOK['agx_look']
sc.view_settings.exposure = LOOK['exposure']
sc.sequencer_colorspace_settings.name = 'sRGB'

# compositor: AOV + index straight to lossless PNG16 for QA
sc.use_nodes = True; ct = sc.node_tree; ct.nodes.clear()
rl = ct.nodes.new('CompositorNodeRLayers'); comp = ct.nodes.new('CompositorNodeComposite')
ct.links.new(rl.outputs['Image'], comp.inputs['Image'])
fo = ct.nodes.new('CompositorNodeOutputFile'); fo.base_path = OUT
fo.format.file_format = 'PNG'; fo.format.color_depth = '16'; fo.format.color_mode = 'BW'
fo.file_slots[0].path = 'qa_sig_'; ct.links.new(rl.outputs['sig'], fo.inputs[0])
fo.file_slots.new('qa_idx_'); div = ct.nodes.new('CompositorNodeMath'); div.operation = 'DIVIDE'
div.inputs[1].default_value = 2.0; ct.links.new(rl.outputs['IndexOB'], div.inputs[0]); ct.links.new(div.outputs[0], fo.inputs[1])

cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 36.0; cd.clip_start = 0.002; cd.clip_end = 50

# ---------- signature sample points on the mesh (glyph + margin ring), for mesh + frame QA
dg = bpy.context.evaluated_depsgraph_get()
sig_img = bpy.data.images.load(MAN['signature']['mask'], check_existing=True)
mw, mh = sig_img.size; px = np.array(sig_img.pixels[:], np.float32).reshape(mh, mw, -1)[::-1, :, 0]  # row 0 = top
x0, y0, x1, y1 = MAN['signature']['ink_px']
ink = px[y0:y1, x0:x1] > 0.5
rng = np.random.default_rng(1234)
iy, ix = np.nonzero(ink[::8, ::8]); iy, ix = iy * 8, ix * 8
pick = rng.choice(len(iy), size=min(1500, len(iy)), replace=False); iy, ix = iy[pick], ix[pick]
sig_pts = {}; mesh_qa = {}
fnz = P.edgeqa.face_normals(V, d['F']); flat_lbl = {k for k, v in labels.items() if v in ('body', 'pad', 'ring', 'spine')}


def surf_hit(x, z, side):
    """Ray along +-Y onto the part (object space == world space, part un-rotated at this point)."""
    sgn = -1 if side == 'front' else 1
    ok, loc, nrm, fi = part.ray_cast(Vector((x, sgn * 0.05, z)), Vector((0, -sgn, 0)))
    return ok, loc, nrm, fi


for side, p in MAN['signature']['placements'].items():
    Lm, Hm = p['len_mm'] * 1e-3, p['h_mm'] * 1e-3
    th = math.radians(p['angle_deg']); c, s_ = math.cos(th), math.sin(th); sx = -1 if side == 'back' else 1
    su = (ix + 0.5) / ink.shape[1] - 0.5; tv = 0.5 - (iy + 0.5) / ink.shape[0]
    pu, pv = su * Lm, tv * Hm
    dx = pu * c - pv * s_; dz = pu * s_ + pv * c
    X = p['center_xz_m'][0] + sx * dx; Z = p['center_xz_m'][1] + dz
    margin = MAN['config']['margin_mm'] * 1e-3
    pts, bad = [], 0
    for x, z in zip(X, Z):
        ok, loc, nrm, fi = surf_hit(x, z, side)
        good = ok and labels[str(part.data.polygons[fi].material_index)] in ('body', 'pad', 'ring', 'spine') and abs(nrm.y) > 0.95
        for a_ in np.linspace(0, 2 * math.pi, 8, endpoint=False):     # margin ring
            ok2, l2, n2, f2 = surf_hit(x + margin * math.cos(a_), z + margin * math.sin(a_), side)
            good = good and ok2 and abs(n2.y) > 0.95 and labels[str(part.data.polygons[f2].material_index)] in ('body', 'pad', 'ring', 'spine')
        bad += (not good); pts.append(tuple(loc) if ok else None)
    sig_pts[side] = [q for q in pts if q is not None]
    mesh_qa[side] = {'samples': len(pts), 'off_flat_or_margin': int(bad), 'margin_mm': margin * 1e3, 'pass': bad == 0}
print('SIGMESHQA', json.dumps(mesh_qa), flush=True)


def place_camera(sh):
    part.rotation_euler = (0, 0, math.radians(sh.get('part_rot_deg', 0)))
    dg.update()
    cd.lens = sh['focal_mm']
    el, az = math.radians(sh['el']), math.radians(sh['az'])
    dirv = np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
    tgt = np.array(resolve_target(sh['target']))
    # fit: the requested frame-width fraction of the target set (whole part / signature / point+radius)
    pts = fit_points(sh)
    lo_d, hi_d = 0.02, 5.0
    for _ in range(50):
        dist = 0.5 * (lo_d + hi_d)
        cam.location = Vector((tgt + dist * dirv).tolist())
        cam.rotation_euler = Vector((-dirv).tolist()).to_track_quat('-Z', 'Y').to_euler()
        if sh.get('roll_deg'): cam.rotation_euler.rotate_axis('Z', math.radians(sh['roll_deg']))
        dg.update()
        uv = np.array([world_to_camera_view(sc, cam, Vector(q))[:2] for q in pts])
        span = max((uv[:, 0].max() - uv[:, 0].min()) / sh['fill'], (uv[:, 1].max() - uv[:, 1].min()) / sh.get('fill_v', 0.86))
        if span > 1: lo_d = dist
        else: hi_d = dist
    # recentre: shift target so the fit set is centred (+ optional offset)
    uvc = 0.5 * (uv.min(0) + uv.max(0)) - 0.5 + np.array(sh.get('offset_uv', [0, 0]))
    cam_m = cam.matrix_world.to_3x3()
    w_img = 2 * dist * math.tan(0.5 * cd.angle_x)
    shift = np.array(cam_m @ Vector((uvc[0] * w_img, uvc[1] * w_img * RY / RX, 0)))
    cam.location = Vector((np.array(cam.location) + shift).tolist()); dg.update()
    cd.dof.use_dof = sh.get('fstop', 0) > 0
    if cd.dof.use_dof:
        ft = resolve_target(sh.get('focus', sh['target']))
        cd.dof.focus_distance = float((Vector(ft) - cam.location).length); cd.dof.aperture_fstop = sh['fstop']
    return dist


def world_pts(local_pts):
    M = part.matrix_world
    return [tuple(M @ Vector(q)) for q in local_pts]


def resolve_target(t):
    if t == 'part':
        return list(np.array(part.matrix_world @ Vector(((lo + hi) / 2).tolist())))
    if t in ('sig_front', 'sig_back'):
        return list(np.mean(world_pts(sig_pts[t[4:]]), 0))
    if isinstance(t, dict) and 'edge' in t:   # point on cutting edge nearest sig
        return list(part.matrix_world @ Vector(t['edge']))
    return list(part.matrix_world @ Vector(t))


def fit_points(sh):
    f = sh.get('fit', 'part')
    if f == 'part':
        bb = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        if 'fit_rot_range' in sh:   # constant framing over a rock/turntable: union of corners over the range
            from mathutils import Matrix
            out = []
            for a_ in np.linspace(*sh['fit_rot_range'], 9):
                Mz = Matrix.Rotation(math.radians(a_), 4, 'Z')
                out += [tuple(Mz @ Vector(q)) for q in bb]
            return out
        return world_pts(bb)
    if f in ('sig_front', 'sig_back'):
        return world_pts(sig_pts[f[4:]])
    if isinstance(f, dict):   # box around a point
        c = np.array(f['center']); h = f['half_m']
        return world_pts([tuple(c + np.array(o) * h) for o in [(1, 0, 1), (-1, 0, -1), (1, 0, -1), (-1, 0, 1)]])
    raise ValueError(f)


def light_corners():
    pts = []
    for ob in sc.objects:
        if ob.type != 'LIGHT': continue
        ld = ob.data; sx_ = getattr(ld, 'size', 0.05) / 2; sy_ = (getattr(ld, 'size_y', ld.size) if ld.type == 'AREA' else sx_ * 2) / 2
        for a_ in np.linspace(-1, 1, 7):          # whole emitter surface, not only its corners
            for b_ in np.linspace(-1, 1, 7):
                pts.append((ob.name, ob.matrix_world @ Vector((a_ * sx_, b_ * sy_, 0))))
    return pts


def qa_lights():
    """Every emitter corner and its floor-mirror image must project outside the frame (6 % guard)."""
    hits = []
    for name, w in light_corners():
        for q in (w, Vector((w.x, w.y, 2 * z_floor - w.z))):
            c = world_to_camera_view(sc, cam, q)
            if c.z > 0 and -0.06 < c.x < 1.06 and -0.06 < c.y < 1.06:
                hits.append(name)
    return {'emitters_in_frame': sorted(set(hits)), 'pass': not hits}


def aim_mirror_lights(sh):
    """Reflector lights flagged mirror_flat sit on the mirror direction of the broad face (normal -Y of
    the visible side, rotated with the part) so the polished flats reflect them; offset_deg nudges it."""
    tgt = Vector(((lo + hi) / 2).tolist()); tgt = part.matrix_world @ tgt
    for Lc in rig['lights']:
        if not Lc.get('mirror_flat'): continue
        ob = sc.objects[Lc['name']]
        n = part.matrix_world.to_3x3() @ Vector((0, 1 if facing_side(sh) == 'back' else -1, 0)); n.normalize()
        v = (cam.location - tgt).normalized()
        r_ = 2 * n.dot(v) * n - v
        el_off, az_off = [math.radians(x) for x in Lc.get('offset_deg', [0, 0])]
        r_ = __import__('mathutils').Matrix.Rotation(az_off, 3, 'Z') @ r_
        r_.z += math.sin(el_off); r_.normalize()
        ob.location = tgt + r_ * Lc['dist_D'] * D
        ob.rotation_euler = (tgt - ob.location).to_track_quat('-Z', 'Y').to_euler()
    dg.update()


def clear_lights(max_steps=40, step_deg=3.0):
    """Deterministic fix-up: any emitter (or its floor mirror) inside the frame is raised in elevation
    about the part centre, keeping its aim, until clear. Returns the per-light adjustments."""
    tgt = Vector(((lo + hi) / 2).tolist()); adj = {}
    for _ in range(max_steps):
        bad = qa_lights()['emitters_in_frame']
        if not bad: break
        for name in bad:
            ob = sc.objects[name]; v = ob.location - tgt
            r_ = v.length; az_ = math.atan2(v.y, v.x); el_ = math.asin(max(-1, min(1, v.z / r_)))
            el_ = min(el_ + math.radians(step_deg), math.radians(85))
            ob.location = tgt + r_ * Vector((math.cos(el_) * math.cos(az_), math.cos(el_) * math.sin(az_), math.sin(el_)))
            ob.rotation_euler = (tgt - ob.location).to_track_quat('-Z', 'Y').to_euler()
            adj[name] = round(math.degrees(el_), 2)
        dg.update()
    return adj


BASE_LIGHTS = {o.name: (o.location.copy(), o.rotation_euler.copy()) for o in sc.objects if o.type == 'LIGHT'}


def reset_lights():
    for n, (l_, r_) in BASE_LIGHTS.items():
        sc.objects[n].location = l_; sc.objects[n].rotation_euler = r_
    dg.update()


def facing_side(sh):
    """'front'/'back' as authored; 'auto' (turntable / macro scans) = the broad face turned toward the camera."""
    if sh.get('sig_side') != 'auto': return sh['sig_side']
    n = part.matrix_world.to_3x3() @ Vector((0, -1, 0)); n.normalize()
    c = Vector(resolve_target('part')); return 'front' if n.dot((cam.location - c).normalized()) >= 0 else 'back'


def qa_sig_visible(sh, grazing_cos=0.30):
    """Signature QA wherever the signature is visible (#53 + owner 10:45). For each side whose face is presented
    to the camera (cos > grazing_cos) and that has ANY glyph sample in frame, every sample must be in frame and
    unoccluded (no cropped or half-hidden mark). Fully off-frame or grazing/back-facing marks are recorded, not failed."""
    if sh.get('sig_side') != 'auto': return qa_sig_frame(sh['sig_side'])
    out = {'side': 'auto', 'sides': {}, 'pass': True}
    for side, ny in (('front', -1), ('back', 1)):
        n = part.matrix_world.to_3x3() @ Vector((0, ny, 0)); n.normalize()
        ctr = Vector(np.mean(world_pts(sig_pts[side]), 0).tolist()); cosv = n.dot((cam.location - ctr).normalized())
        if cosv <= grazing_cos:
            out['sides'][side] = {'presented': False, 'cos': round(cosv, 3), 'pass': True}; continue
        inside = sum(1 for q in world_pts(sig_pts[side])
                     if (lambda c: 0.0 < c.x < 1.0 and 0.0 < c.y < 1.0 and c.z > 0)(world_to_camera_view(sc, cam, Vector(q))))
        if inside == 0:
            out['sides'][side] = {'presented': True, 'in_frame': 0, 'cos': round(cosv, 3), 'pass': True}; continue
        q_ = qa_sig_frame(side); q_.update(presented=True, cos=round(cosv, 3))
        if q_['out_of_frame'] == q_['samples']: q_.update({'pass': True, 'note': 'only edge-guard samples in frame'})
        out['sides'][side] = q_
        out['pass'] = out['pass'] and q_['pass']
    return out


def qa_sig_frame(side):
    """All glyph samples inside the image (1 % guard) and unoccluded (camera ray hits the same point)."""
    out_f, occl = 0, 0
    pts = world_pts(sig_pts[side])
    for q in pts:
        q = Vector(q); c = world_to_camera_view(sc, cam, q)
        if not (0.01 < c.x < 0.99 and 0.01 < c.y < 0.99 and c.z > 0): out_f += 1; continue
        dirv = (q - cam.location); dist = dirv.length; dirv.normalize()
        hit, loc, nrm, idx, ob, _ = sc.ray_cast(dg, cam.location, dirv, distance=dist + 1e-3)
        if not hit or (loc - q).length > 2e-4 or nrm.dot(dirv) > 0: occl += 1
    return {'side': side, 'samples': len(pts), 'out_of_frame': out_f, 'occluded_or_backfacing': occl,
            'pass': out_f == 0 and occl == 0}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def r6(v):
    # 1e-5 quantisation (10 um / 1e-5 rad): declared tolerance so float32 decomposition noise doesn't alter the state hash
    return [round(float(x), 5) + 0.0 for x in v]


def physical_state():
    """Every physical control as resolved in the worker (director books: plan -> worker -> receipt)."""
    st = {'camera': {'matrix': [r6(row) for row in cam.matrix_world], 'lens_mm': cd.lens, 'sensor_mm': cd.sensor_width,
                     'dof': cd.dof.use_dof, 'focus_m': round(cd.dof.focus_distance, 6), 'fstop': cd.dof.aperture_fstop,
                     'motion_blur': sc.render.use_motion_blur},
          'part': {'matrix': [r6(row) for row in part.matrix_world]},
          'lights': {o.name: {'matrix': [r6(row) for row in o.matrix_world], 'energy': round(o.data.energy, 6),
                              'size': round(getattr(o.data, 'size', 0), 6), 'size_y': round(getattr(o.data, 'size_y', 0), 6)}
                     for o in sorted((o for o in sc.objects if o.type == 'LIGHT'), key=lambda o: o.name)},
          'floor': rig['backdrop'], 'world': rig['world'].get('strength'), 'res': [RX, RY]}
    return st, hashlib.sha256(json.dumps(st, sort_keys=True).encode()).hexdigest()


MATERIAL_STATE = {'finish': None, 'look': LOOK, 'flame': CFG.get('flame'), 'prep_sig': MAN['signature']['placements'],
                  'art_sha256': MAN['art']['sha256']}
CODE_ID = {'pro_hero_sha256': sha(os.path.abspath(__file__)), 'cfg_sha256': hashlib.sha256(json.dumps(CFG, sort_keys=True).encode()).hexdigest(),
           'prep_sha256': sha(os.path.join(PREP, 'prep.json')), 'source': MAN['source']}
sc.render.use_motion_blur = False   # stills/animatic: no shutter blending of states (books: disable blur unless subframes are evaluated)


def apply_fault(kind):
    """Deliberate faults (books: gates must fail on them)."""
    if kind == 'light_in_frame':
        ob = next(o for o in sc.objects if o.type == 'LIGHT')
        tgt = Vector(((lo + hi) / 2).tolist()); ob.location = tgt + (cam.location - tgt) * 0.5 + Vector((0, 0, 0.0))
        ob.location = tgt + Vector((0, 0.6 * (hi[1] - lo[1]) + 0.02, 0.01))   # just behind the part: in frame
    elif kind == 'sig_off_flat':
        for side in sig_pts: sig_pts[side] = [(x + 0.03, y, z) for (x, y, z) in sig_pts[side]]
        for side in mesh_qa: mesh_qa[side]['pass'] = False; mesh_qa[side]['fault'] = 'sig_off_flat'
    dg.update()


def image_pixels(png, raw=False):
    """Copy pixels without a Python-float list; release Blender's buffer even on errors.
    raw=True reads data passes (object index / AOV) without the sRGB->linear decode (0.5 stays 0.5)."""
    im = bpy.data.images.load(png)
    if raw: im.colorspace_settings.name = 'Non-Color'
    try:
        values = np.empty(len(im.pixels), np.float32)
        im.pixels.foreach_get(values)
        return values.reshape(RY, RX, -1)
    finally:
        bpy.data.images.remove(im)


def frame_qa_image(png, tag):
    """Whole-frame review aid: clipped fraction over the WHOLE frame and the largest clipped blob."""
    a_ = image_pixels(png)[:, :, :3]
    if not np.isfinite(a_).all():
        return {'pass': False, 'error': 'non-finite frame pixels'}
    clip = a_.max(2) >= 0.995
    frac = float(clip.mean())
    # largest 4-connected clipped component (cheap flood on a downsample)
    small = clip[::4, ::4]; seen = np.zeros_like(small); best = 0
    for y0, x0 in zip(*np.nonzero(small)):
        if seen[y0, x0]: continue
        stack = [(y0, x0)]; seen[y0, x0] = 1; n = 0
        while stack:
            y, x = stack.pop(); n += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < small.shape[0] and 0 <= xx < small.shape[1] and small[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = 1; stack.append((yy, xx))
        best = max(best, n)
    blob = best * 16 / (RX * RY)
    lim = CFG.get('white_patch_limit', 0.0015)
    return {'frame_clipped_frac': round(frac, 6), 'largest_white_blob_frac': round(blob, 6), 'limit': lim,
            'pass': blob <= lim}


def lerp_shot(S, f):
    """Shot state at absolute frame f: keys interpolate with smoothstep (absolute time, shard-safe)."""
    a, b = S['start'], S['end']; t = (f - S['frames'][0]) / max(1, S['frames'][1] - 1 - S['frames'][0])
    if S['common'].get('ease', 'smooth') == 'smooth': t = t * t * (3 - 2 * t)
    sh = dict(S['common'])
    if 'rot_table_deg' in sh:   # authored per-frame turntable angle (broadside-eased science spin)
        sh['part_rot_deg'] = sh.pop('rot_table_deg')[f - S['frames'][0]]
    for k in set(a) | set(b):
        va, vb = a.get(k, b.get(k)), b.get(k, a.get(k))
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            sh[k] = va + (vb - va) * t
        elif isinstance(va, list) and isinstance(vb, list) and len(va) == len(vb) and all(isinstance(x, (int, float)) for x in va + vb):
            sh[k] = [x + (y - x) * t for x, y in zip(va, vb)]   # moving target point (macro scans)
        elif isinstance(va, dict) and isinstance(vb, dict) and 'center' in va:
            sh[k] = {**va, 'center': [x + (y - x) * t for x, y in zip(va['center'], vb['center'])],
                     'half_m': va['half_m'] + (vb['half_m'] - va['half_m']) * t}
        else:
            sh[k] = va
    return sh


def run_animation():
    AN = json.load(open(A['--anim'])); step = int(A.get('--step', 1))
    lt0 = {n: (l_.copy(), r_.copy()) for n, (l_, r_) in BASE_LIGHTS.items()}
    r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '16'; r.image_settings.color_mode = 'RGB'
    want = set(int(x) for x in A['--frames'].split(',')) if '--frames' in A else None
    if '--frame_range' in A:   # a:b (end-exclusive), e.g. only the science section for the wire/heat passes
        a0, b0 = map(int, A['--frame_range'].split(':')); want = set(range(a0, b0))
    DRY = A.get('--dry') == '1'
    header = {'schema': 'jarambit.render.pro.anim_qa.v1', 'fps': AN['fps'], 'film': AN.get('title'), 'finish': FINISH,
              'code': CODE_ID, 'material_state_sha256': hashlib.sha256(json.dumps({**MATERIAL_STATE, 'finish': FINISH}, sort_keys=True, default=str).encode()).hexdigest(),
              'fault': A.get('--fault'), 'release_ready': False,
              'release_note': 'human creative + presentation sign-off required; C.10a = design candidate, not certified'}
    path = os.path.join(OUT, A.get('--receipt', 'anim_qa.json'))
    with Q.AnimationReceipt(path, header, dry=DRY) as receipt:
        for S in AN['shots']:
            fr = range(S['frames'][0], S['frames'][1], step) if want is None else sorted(x for x in want if S['frames'][0] <= x < S['frames'][1])
            for f in fr:
                sh = lerp_shot(S, f)
                reset_lights()
                if 'light_rot_deg' in sh:   # authored lighting arc: whole rig rotates about Z, part fixed
                    Rz = __import__('mathutils').Matrix.Rotation(math.radians(sh['light_rot_deg']), 4, 'Z')
                    from mathutils import Matrix
                    for n, (l_, r_) in lt0.items():
                        sc.objects[n].matrix_world = Rz @ Matrix.LocRotScale(l_, r_.to_quaternion(), Vector((1, 1, 1)))
                    dg.update()
                place_camera(sh); aim_mirror_lights(sh); adj = clear_lights()
                G = globals()   # film-only hooks (absent in the #53 unit-test worker env -> no-ops)
                if 'apply_shot_light' in G: apply_shot_light(sh)
                if G.get('SCI'):
                    fem_ob.matrix_world = part.matrix_world.copy(); cd.dof.use_dof = False; sci_select(sh)
                if 'fo' in G: fo.file_slots[0].path = f'qa_sig_f{f:05d}_'; fo.file_slots[1].path = f'qa_idx_f{f:05d}_'
                if A.get('--fault'): apply_fault(A['--fault'])
                ql = qa_lights(); qs = qa_sig_visible(sh) if sh.get('sig_side') == 'auto' else qa_sig_frame(sh['sig_side'])
                st, h = physical_state()
                rec = {'frame': f, 'shot': S['name'], 'lights_pass': ql.get('pass'), 'raised': adj, 'sig': qs,
                       'edge_sharpness': MAN.get('edge_qa'),
                       'sig_mesh_pass': all(Q.passed(mesh_qa.get(s)) for s in ('front', 'back')),
                       'physical_state_sha256': h, 'state': st}
                if not Q.pre_render_pass(MAN.get('edge_qa'), ql, qs, mesh_qa):
                    rec['status'] = 'FAIL_PRE_RENDER'; receipt.add(rec)
                    print('QAFAIL', json.dumps(rec), flush=True); return 1
                if not DRY:
                    r.filepath = os.path.join(OUT, f'f{f:05d}.png')
                    if A.get('--resume') == '1' and os.path.isfile(r.filepath) and os.path.getsize(r.filepath) > 0:
                        rec['resumed'] = True   # same state hash path; image QA re-run on the existing frame below
                    else:
                        bpy.ops.render.render(write_still=True)
                    try:
                        rec['image'] = frame_qa_image(r.filepath, f) if not globals().get('SCI') else {'pass': True, 'note': 'science plate (emission data view, composited inside the knife mask only): white-blob gate n/a, same as stills'}
                    except Exception as e:
                        rec['image'] = {'pass': False, 'error': str(e)}
                ok = Q.frame_pass(rec, dry=DRY)
                rec['status'] = ('QA_DRY' if DRY else 'RENDERED') if ok else 'FAIL_POST_RENDER'
                receipt.add(rec)
                if not ok:
                    print('QAFAIL', json.dumps(rec), flush=True); return 1
    return 0 if receipt.all_pass else 1

# ---------- science shots (real solver mesh + von Mises; see fem_asset.py). Same shot camera as the photoreal pass.
INFERNO = [(0.0, (0.0015, 0.0005, 0.0139)), (0.125, (0.0828, 0.0448, 0.2203)), (0.25, (0.2582, 0.0386, 0.4065)),
           (0.375, (0.4163, 0.0904, 0.4329)), (0.5, (0.5783, 0.148, 0.4044)), (0.625, (0.7357, 0.2161, 0.3302)),
           (0.75, (0.8650, 0.3168, 0.2261)), (0.875, (0.9545, 0.4686, 0.0998)), (1.0, (0.9884, 0.9984, 0.6449))]
SCI = None
SCI_GAIN = 1.0


def sci_select(sh):
    """Per-shot load case for the turntable data section: the heat material reads attribute vm_<case>."""
    if SCI and SCI['mode'] == 'heat':
        sci_attr.attribute_name = 'vm_' + sh.get('sci_case', SCI['case'])


if '--sci' in A:
    _z = np.load(A['--sci']); SCI = {'case': A['--sci_case'], 'mode': A['--sci_mode'], 'Sy': float(A['--sci_vmax'])}   # Sy from the design manifest (jr_film)
    SCI_GAIN = float(A.get('--sci_gain', 1.0))   # emission gain; overlay legend is drawn with the SAME gain (jr_film passes both)
    lin = lambda c: tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)   # ramp stops are sRGB
    me = bpy.data.meshes.new('fem_rc4'); me.from_pydata(_z['V'].astype(float).tolist(), [], _z['F'].tolist()); me.update()
    for k_ in _z.files:
        if k_.startswith('vm_'):
            at = me.attributes.new(k_, 'FLOAT', 'FACE'); at.data.foreach_set('value', _z[k_].astype(np.float32))
    if 'vm_' + SCI['case'] not in _z.files: raise SystemExit(f"--sci_case {SCI['case']}: no vm_{SCI['case']} in {A['--sci']}")
    fem_ob = bpy.data.objects.new('fem_rc4', me); sc.collection.objects.link(fem_ob); fem_ob.hide_viewport = True   # keep QA raycasts on the part
    m_, nt_, N_, L_ = mk('fem_' + SCI['mode']); o_ = N_('ShaderNodeOutputMaterial'); em = N_('ShaderNodeEmission')
    # glints: an additive clear dielectric gloss over the data emission (white specular only, lit by the rig),
    # so the spinning knife still throws light; hue of the field is untouched where there is no glint.
    gl = N_('ShaderNodeBsdfGlossy'); gl.inputs['Color'].default_value = (1, 1, 1, 1); gl.inputs['Roughness'].default_value = float(A.get('--sci_gloss_rough', 0.18))
    fr = N_('ShaderNodeFresnel'); fr.inputs['IOR'].default_value = 1.5
    gmul = N_('ShaderNodeMixShader'); hold = N_('ShaderNodeEmission'); hold.inputs['Strength'].default_value = 0.0   # 'nothing' closure
    add = N_('ShaderNodeAddShader')
    sglint = float(A.get('--sci_glint', 0.0))
    if SCI['mode'] == 'heat':
        sci_attr = a_ = N_('ShaderNodeAttribute'); a_.attribute_type = 'GEOMETRY'; a_.attribute_name = 'vm_' + SCI['case']
        mr_ = N_('ShaderNodeMapRange'); mr_.inputs['From Max'].default_value = SCI['Sy']
        cr = N_('ShaderNodeValToRGB'); el = cr.color_ramp.elements
        el[0].position, el[0].color = INFERNO[0][0], (*lin(INFERNO[0][1]), 1); el[1].position, el[1].color = INFERNO[-1][0], (*lin(INFERNO[-1][1]), 1)
        for p_, c_ in INFERNO[1:-1]:
            e_ = el.new(p_); e_.color = (*lin(c_), 1)
        L_(a_.outputs['Fac'], mr_.inputs['Value']); L_(mr_.outputs['Result'], cr.inputs['Fac']); L_(cr.outputs['Color'], em.inputs['Color'])
        em.inputs['Strength'].default_value = SCI_GAIN
    else:   # tet-mesh wireframe: surface triangles of the solver mesh, thin bright lines over a dark ghost
        wf = N_('ShaderNodeWireframe'); wf.use_pixel_size = True; wf.inputs['Size'].default_value = float(A.get('--sci_wire_px', 0.6))
        mix = N_('ShaderNodeMixRGB'); mix.inputs['Color1'].default_value = (0.010, 0.016, 0.030, 1)
        mix.inputs['Color2'].default_value = tuple(json.loads(A.get('--sci_wire_rgb', '[0.10, 0.30, 0.75]'))) + (1,)
        L_(wf.outputs['Fac'], mix.inputs['Fac']); L_(mix.outputs['Color'], em.inputs['Color']); em.inputs['Strength'].default_value = SCI_GAIN
    if sglint > 0:
        L_(fr.outputs['Fac'], gmul.inputs[0]); L_(hold.outputs[0], gmul.inputs[1]); L_(gl.outputs[0], gmul.inputs[2])
        sc_ = N_('ShaderNodeMixShader'); sc_.inputs[0].default_value = sglint; L_(hold.outputs[0], sc_.inputs[1]); L_(gmul.outputs[0], sc_.inputs[2])
        L_(em.outputs[0], add.inputs[0]); L_(sc_.outputs[0], add.inputs[1]); L_(add.outputs[0], o_.inputs['Surface'])
    else:
        L_(em.outputs[0], o_.inputs['Surface'])
    me.materials.append(m_)
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0.0
    part.hide_render = True


def run_stills():
    only = set(A['--shots'].split(',')) if '--shots' in A else None
    selected, failed = 0, 0
    for sh in CFG['shots']:
        if FILM_PATH: sh = {**sh, **CFG['flame'].get('shot_overrides', {}).get(sh['name'], {})}
        if only and sh['name'] not in only: continue
        if RES not in sh.get('res', ['4k']): continue
        selected += 1
        reset_lights()
        dist = place_camera(sh)
        aim_mirror_lights(sh)
        tag = f"{sh['name']}_{RES}" + ('' if FINISH == 'art' else '_' + FINISH)
        if globals().get('SCI'):
            tag += f"_sci_{SCI['case']}_{SCI['mode']}"; fem_ob.matrix_world = part.matrix_world.copy()
            cd.dof.use_dof = False   # data plates stay crisp (same camera pose/lens, so still pixel-registered)
        light_adj = clear_lights()
        ql = qa_lights(); ql['raised_el_deg'] = light_adj; qs = qa_sig_frame(sh['sig_side'])
        qa = {'shot': tag, 'lights': ql, 'signature_frame': qs, 'signature_mesh': mesh_qa,
              'edge_sharpness': MAN.get('edge_qa')}
        if not Q.pre_render_pass(MAN.get('edge_qa'), ql, qs, mesh_qa):
            failed += 1
            qa.update(status='FAIL_PRE_RENDER', all_pass=False)
            json.dump(qa, open(os.path.join(OUT, tag + '.qa.json'), 'w'), indent=1)
            print('QAFAIL', json.dumps(qa), flush=True); continue
        sc.frame_set(1)
        t0 = time.time()
        fo.file_slots[0].path = f'qa_sig_{tag}_'; fo.file_slots[1].path = f'qa_idx_{tag}_'
        r.image_settings.file_format = 'OPEN_EXR_MULTILAYER'; r.image_settings.color_depth = '32'
        r.image_settings.exr_codec = 'ZIP'
        exr = os.path.join(OUT, tag + '.exr'); r.filepath = exr
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images['Render Result']
        s2 = sc.render.image_settings; s2.file_format = 'PNG'; s2.color_depth = '16'; s2.color_mode = 'RGB'; s2.compression = 15
        png = os.path.join(OUT, tag + '.png'); img.save_render(png, scene=sc)
        try:
            px_ = image_pixels(png)[:, :, :3]
            idx = image_pixels(os.path.join(OUT, f'qa_idx_{tag}_0001.png'), raw=True)[:, :, 0]
            partm = (idx > 0.4) & (idx < 0.6)
            if not partm.any() or not np.isfinite(px_).all():
                raise ValueError('missing part mask or non-finite pixels')
            clip = float((px_[partm].max(1) >= 0.995).mean())
            qa['clipping'] = {'part_px_clipped_frac': round(clip, 5), 'limit': CFG.get('clip_limit', 0.002), 'pass': clip <= CFG.get('clip_limit', 0.002)}
        except Exception as e:
            qa['clipping'] = {'pass': False, 'error': str(e)}
        try:
            qa['image'] = frame_qa_image(png, tag) if not globals().get('SCI') else {'pass': True, 'note': 'science plate (emission data view): white-blob gate n/a'}
            if globals().get('SCI'): qa['science'] = {**SCI, 'colormap': 'inferno (perceptually uniform)', 'vmin_MPa': 0.0, 'vmax_MPa': SCI['Sy'], 'fem': A['--sci'], 'fem_sha256': sha(A['--sci'])}
        except Exception as e:
            qa['image'] = {'pass': False, 'error': str(e)}
        st_, h_ = physical_state()
        ok = Q.still_pass(qa)
        failed += int(not ok)
        qa.update({'physical_state_sha256': h_, 'code': CODE_ID, 'release_ready': False, 'label': MAN['source'].get('status_label') or 'design candidate, not certified'})
        qa.update({'status': 'RENDERED' if ok else 'FAIL_POST_RENDER', 'all_pass': ok,
                   'render_s': round(time.time() - t0, 1), 'spp': SPP, 'res': [RX, RY],
                   'camera': {'focal_mm': cd.lens, 'sensor_mm': 36, 'fstop': cd.dof.aperture_fstop if cd.dof.use_dof else None,
                              'loc': list(cam.location), 'rot': list(cam.rotation_euler), 'dist_m': dist},
                   'shot_spec': sh, 'view': {'transform': 'AgX', 'look': LOOK['agx_look'], 'exposure': LOOK['exposure']},
                   'exr': exr, 'exr_sha256': sha(exr), 'png': png, 'png_sha256': sha(png)})
        json.dump(qa, open(os.path.join(OUT, tag + '.qa.json'), 'w'), indent=1)
        print('WROTE' if ok else 'QAFAIL', png, flush=True)
    ok = bool(selected and not failed)
    json.dump({'schema': 'jarambit.render.pro.run.v1', 'prep_sha256': sha(os.path.join(PREP, 'prep.json')),
               'cfg': CFG, 'lights': light_rec, 'blender': bpy.app.version_string, 'all_pass': ok},
              open(os.path.join(OUT, f'run_{RES}.json'), 'w'), indent=1, default=str)
    return 0 if ok else 1


raise SystemExit(run_animation() if '--anim' in A else run_stills())
