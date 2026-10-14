"""SWITCHBACK art-wrap hero stills (anodized-Ti printed skin + gold signature) on the R4 dark arc-key rig.
blender -b -P artwrap.py -- --out DIR [--shots a,b] [--spp N] [--pct 100]
Art: planar projection along the blade-plane normal (object XZ), front from -Y, back mirrored through the
mid-plane so it reads correctly from +Y. Side walls (|n.y|<0.5): dark polished anodized Ti band.
Cutting bevel / serration / apex: raw bright Ti."""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
MK = os.path.join(HERE, '..', 'marketing')
sys.path.insert(0, os.path.join(MK, 'blender'))
import bpy, numpy as np
from mathutils import Vector
import scene, lights, materials, cameras, rigmath

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
A = dict(zip(argv[::2], argv[1::2]))
OUT = os.path.expanduser(A.get('--out', '~/jarambit_render_scratch/artwrap'))
MESH = os.path.expanduser(A.get('--mesh', '~/jarambit_render_scratch/hero_C9.3/mesh_v2/mesh/bundle.json'))
ART = os.path.join(HERE, 'psychedelic_wrap_nosig.png')
SIG = os.path.join(HERE, 'signature', 'sig_strokes_pad.png')
KO = os.path.join(HERE, 'signature', 'sig_knockout_pad.png')
SPP = int(A.get('--spp', 192)); PCT = int(A.get('--pct', 100))
CFG = json.load(open(os.path.join(HERE, 'artwrap.json')))
os.makedirs(OUT, exist_ok=True)

scene.reset()
b, d = scene.load_bundle(MESH)
part = scene.build_part(d)
lo, hi = d['V'].min(0), d['V'].max(0); D = float(np.linalg.norm(hi - lo))

def mk(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); return m, nt, nt.nodes.new, nt.links.new

def proj(nt, N, L, xy, axis_u, axis_v, scale_u, scale_v, off_u, off_v):
    """object-space planar UV: u = dot(P-c,axis_u)/scale_u + off_u (P.xz)"""
    tc = N('ShaderNodeTexCoord'); sep = N('ShaderNodeSeparateXYZ'); L(tc.outputs['Object'], sep.inputs[0])
    def lin(ax, sc, off):
        m1 = N('ShaderNodeMath'); m1.operation = 'MULTIPLY_ADD'
        L(sep.outputs['X'], m1.inputs[0]); m1.inputs[1].default_value = ax[0] / sc
        m2 = N('ShaderNodeMath'); m2.operation = 'MULTIPLY_ADD'
        L(sep.outputs['Z'], m2.inputs[0]); m2.inputs[1].default_value = ax[1] / sc
        m2.inputs[2].default_value = off - (xy[0] * ax[0] + xy[1] * ax[1]) / sc
        L(m1.outputs[0], m2.inputs[2]) if False else None
        s = N('ShaderNodeMath'); s.operation = 'ADD'; L(m1.outputs[0], s.inputs[0]); L(m2.outputs[0], s.inputs[1])
        m1.inputs[2].default_value = 0.0
        return s.outputs[0]
    cmb = N('ShaderNodeCombineXYZ')
    L(lin(axis_u, scale_u, off_u), cmb.inputs['X']); L(lin(axis_v, scale_v, off_v), cmb.inputs['Y'])
    return cmb.outputs[0]

def img_node(N, path, ext, cs='sRGB'):
    t = N('ShaderNodeTexImage'); t.image = bpy.data.images.load(path, check_existing=True)
    t.image.colorspace_settings.name = cs; t.extension = ext; t.interpolation = 'Cubic'; return t

C = CFG
art_img = bpy.data.images.load(ART)
W_px, H_px = art_img.size
x0, x1, y0, y1 = C['art_crop_px']            # usable art window (px, top-left origin)
art_h = C['art_height_m']; art_w = art_h * (x1 - x0) / (y1 - y0)
fu, fv = C['art_face_uv']                    # art-face position inside crop (0..1, v from bottom)
cx, cz = C['art_face_xz']
# crop window -> full-image uv
su, ou = (x1 - x0) / W_px, x0 / W_px
sv, ov = (y1 - y0) / H_px, (H_px - y1) / H_px

def side_art(nt, N, L, back):
    s = -1.0 if back else 1.0
    uv = proj(nt, N, L, (cx, cz), (s * su ** 0 * 1.0, 0.0), (0.0, 1.0), art_w, art_h, fu, fv)
    # crop -> full image
    mp = N('ShaderNodeMapping'); mp.vector_type = 'POINT'
    mp.inputs['Scale'].default_value = (su, sv, 1); mp.inputs['Location'].default_value = (ou, ov, 0)
    L(uv, mp.inputs['Vector'])
    t = img_node(N, ART, 'MIRROR'); L(mp.outputs[0], t.inputs['Vector']); return t.outputs['Color']

def side_sig(nt, N, L, back):
    th = math.radians(C['sig_angle_deg']); c, s_ = math.cos(th), math.sin(th)
    if back:
        au, av = (-c, -s_), (-s_, c)   # unmirrored when seen from +Y (screen-right = -X)
    else:
        au, av = (c, s_), (-s_, c)
    Ls, Hs = C['sig_len_m'], C['sig_len_m'] * 1865 / 4616
    if back:   # keep the same 3D span (blade start -> tip): centre stays, text reads L->R from the back
        pass
    uv = proj(nt, N, L, tuple(C['sig_center_xz']), au, av, Ls, Hs, 0.5, 0.5)
    t = img_node(N, SIG, 'CLIP', 'Non-Color'); L(uv, t.inputs['Vector'])
    k = img_node(N, KO, 'CLIP', 'Non-Color'); L(uv, k.inputs['Vector']); return t.outputs['Color'], k.outputs['Color']

def art_material():
    m, nt, N, L = mk('art_anodized')
    out = N('ShaderNodeOutputMaterial')
    # side selector from true normal (object space; part is only rotated about Z so n.y in object space)
    geo = N('ShaderNodeNewGeometry'); vt = N('ShaderNodeVectorTransform')
    vt.vector_type = 'NORMAL'; vt.convert_from = 'WORLD'; vt.convert_to = 'OBJECT'
    L(geo.outputs['True Normal'], vt.inputs[0]); sep = N('ShaderNodeSeparateXYZ'); L(vt.outputs[0], sep.inputs[0])
    back = N('ShaderNodeMath'); back.operation = 'GREATER_THAN'; L(sep.outputs['Y'], back.inputs[0]); back.inputs[1].default_value = 0.0
    ab = N('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; L(sep.outputs['Y'], ab.inputs[0])
    face = N('ShaderNodeMapRange'); L(ab.outputs[0], face.inputs['Value'])
    face.inputs['From Min'].default_value = 0.55; face.inputs['From Max'].default_value = 0.75
    def mixc(f, a, b_):
        mx = N('ShaderNodeMix'); mx.data_type = 'RGBA'; L(f, mx.inputs['Factor'])
        L(a, mx.inputs[6]) if not isinstance(a, tuple) else mx.inputs[6].__setattr__('default_value', a)
        L(b_, mx.inputs[7]) if not isinstance(b_, tuple) else mx.inputs[7].__setattr__('default_value', b_)
        return mx.outputs[2]
    def mixf(f, a, b_):
        mx = N('ShaderNodeMix'); mx.data_type = 'FLOAT'; L(f, mx.inputs['Factor'])
        for i, v in ((2, a), (3, b_)):
            L(v, mx.inputs[i]) if not isinstance(v, float) else mx.inputs[i].__setattr__('default_value', v)
        return mx.outputs[0]
    art = mixc(back.outputs[0], side_art(nt, N, L, False), side_art(nt, N, L, True))
    (sf, kf), (sb, kb) = side_sig(nt, N, L, False), side_sig(nt, N, L, True)
    sig = mixf(back.outputs[0], sf, sb); ko = mixf(back.outputs[0], kf, kb)
    # anodized colour: boost saturation/value, floor black to dark polished Ti
    hsv = N('ShaderNodeHueSaturation'); hsv.inputs['Saturation'].default_value = C['sat']
    hsv.inputs['Value'].default_value = C['val']; L(art, hsv.inputs['Color'])
    dark = tuple(C['dark_ti']) + (1,)
    lum = N('ShaderNodeRGBToBW'); L(art, lum.inputs[0])
    k = N('ShaderNodeMapRange'); L(lum.outputs[0], k.inputs['Value']); k.inputs['From Min'].default_value = 0.0
    k.inputs['From Max'].default_value = 0.06
    anod = mixc(k.outputs['Result'], dark, hsv.outputs[0])
    kof = N('ShaderNodeMath'); kof.operation = 'MULTIPLY'; L(ko, kof.inputs[0]); kof.inputs[1].default_value = C['knockout']
    anod = mixc(kof.outputs[0], anod, dark)
    sides = mixc(face.outputs['Result'], tuple(C['band_ti']) + (1,), anod)
    gold = tuple(C['gold']) + (1,)
    sigf = N('ShaderNodeMath'); sigf.operation = 'MULTIPLY'; L(sig, sigf.inputs[0]); L(face.outputs['Result'], sigf.inputs[1])
    col = mixc(sigf.outputs[0], sides, gold)
    bs = N('ShaderNodeBsdfPrincipled'); L(col, bs.inputs['Base Color'])
    bs.inputs['Metallic'].default_value = 1.0
    L(mixf(sigf.outputs[0], C['rough'], C['gold_rough']), bs.inputs['Roughness'])
    bs.inputs['Coat Weight'].default_value = C['coat']; bs.inputs['Coat Roughness'].default_value = 0.04
    bs.inputs['Coat IOR'].default_value = 1.5
    L(bs.outputs[0], out.inputs['Surface'])
    return m

def raw_ti():
    m, nt, N, L = mk('raw_ti'); out = N('ShaderNodeOutputMaterial'); bs = N('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = tuple(C['raw_ti']) + (1,); bs.inputs['Metallic'].default_value = 1
    bs.inputs['Roughness'].default_value = 0.12; L(bs.outputs[0], out.inputs['Surface']); return m

art_m, ti_m = art_material(), raw_ti()
labels = json.load(open(os.path.join(os.path.dirname(MESH), 'regions.json')))['labels']
for i in range(len(labels)):
    lab = labels[str(i)]
    part.data.materials.append(art_m if lab in ('body', 'ring', 'spine', 'pad') else ti_m)

rig = json.load(open(os.path.join(MK, 'presets', 'rig_dark_arc_key.json')))
rig['lights'] = rig['lights'] + C.get('extra_lights', [])
z_floor = float(lo[2])
scene.build_backdrop(rig['backdrop'], D, z_floor, materials.floor_material(rig['backdrop']['material']))
hdri = scene.find_hdri(rig['world']['hdri']['file'], rig['world']['hdri']['sha256'],
                       ['~/jarambit_render_scratch/hdri', os.path.join(MK, 'hdri')])
scene.build_world(rig['world'], hdri)
lights.build(rig, D, np.zeros(3), exposure_scale=2.0 ** (rig['exposure_ev'] + C.get('ev', 0.0)))

sc = bpy.context.scene; r = sc.render; r.engine = 'CYCLES'
r.resolution_x, r.resolution_y, r.resolution_percentage = 3840, 2160, PCT
scene.gpu_devices('OPTIX'); cy = sc.cycles; cy.device = 'GPU'
cy.samples = SPP; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015
cy.use_denoising = True; cy.denoiser = 'OPENIMAGEDENOISE'
cy.glossy_bounces = 8; cy.max_bounces = 12; cy.sample_clamp_indirect = 10
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'
r.image_settings.file_format = 'PNG'; r.image_settings.color_depth = '16'

cam = cameras.build({'focal_mm': 85, 'sensor_mm': 36}) if False else None
cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
cd.sensor_width = 36; cd.clip_start = 0.005
only = set(A['--shots'].split(',')) if '--shots' in A else None
for sh in C['shots']:
    if only and sh['name'] not in only: continue
    part.rotation_euler = (0, 0, math.radians(sh['part_rot_deg']))
    cd.lens = sh['focal_mm']
    tgt = np.array(sh['target']); el, az = math.radians(sh['el']), math.radians(sh.get('az', 0))
    pos = tgt + sh['dist'] * np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
    cam.location = Vector(pos.tolist())
    cam.rotation_euler = (Vector(tgt.tolist()) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cd.dof.use_dof = sh.get('fstop', 0) > 0
    if cd.dof.use_dof: cd.dof.focus_distance = sh['dist']; cd.dof.aperture_fstop = sh['fstop']
    r.filepath = os.path.join(OUT, sh['name'] + '.png')
    bpy.ops.render.render(write_still=True); print('WROTE', r.filepath, flush=True)
