"""Scene assembly inside Blender: mesh bundle -> object, backdrop, world, Cycles settings, compositor.

Runs only under Blender's bundled Python (bpy). Geometry is taken from mesh.npz verbatim; shading
normals come from N_corner (custom split normals), regions -> material slots, finish tangent ->
face attribute 'finish_tangent'.
"""
import hashlib
import json
import math
import os

import bpy
import numpy as np


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def load_bundle(bundle_path, verify=True):
    b = json.load(open(bundle_path))
    if b.get('schema') != 'jarambit.render.mesh.v1':
        raise ValueError(f'unsupported bundle schema {b.get("schema")!r}')
    npz = os.path.join(os.path.dirname(os.path.abspath(bundle_path)), 'mesh.npz')
    if verify and b.get('npz_sha256') and sha256(npz) != b['npz_sha256']:
        raise ValueError('mesh.npz sha256 mismatch vs bundle.json')
    z = np.load(npz)
    d = {k: z[k] for k in z.files}
    for k in ('V', 'F', 'N_corner', 'region_id', 'tangent'):
        if k not in d:
            raise ValueError(f'mesh.npz missing {k}')
    if not np.isfinite(d['V']).all():
        raise ValueError('non-finite vertices in bundle')
    return b, d


def build_part(mesh_np, name='part'):
    V = np.asarray(mesh_np['V'], np.float64)
    F = np.asarray(mesh_np['F'], np.int64)
    m = len(F)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', V.astype(np.float32).ravel())
    me.loops.add(3 * m)
    me.loops.foreach_set('vertex_index', F.astype(np.int32).ravel())
    me.polygons.add(m)
    me.polygons.foreach_set('loop_start', np.arange(0, 3 * m, 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set('use_smooth', np.ones(m, bool))
    me.polygons.foreach_set('material_index', np.asarray(mesh_np['region_id'], np.int32))
    me.normals_split_custom_set(np.asarray(mesh_np['N_corner'], np.float64).reshape(-1, 3).tolist())
    at = me.attributes.new('finish_tangent', 'FLOAT_VECTOR', 'FACE')
    at.data.foreach_set('vector', np.asarray(mesh_np['tangent'], np.float32).ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.pass_index = 1
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build_turntable(part, pivot):
    tt = bpy.data.objects.new('turntable', None)
    bpy.context.scene.collection.objects.link(tt)
    part.parent = tt
    part.location = tuple(-np.asarray(pivot, float))
    return tt


def _sweep_mesh(width, depth_front, depth_back, radius, height, z0, seg=24):
    prof = [(-depth_front, z0)]
    prof.append((depth_back - radius, z0))
    for i in range(1, seg + 1):
        a = (math.pi / 2) * i / seg
        prof.append((depth_back - radius + radius * math.sin(a), z0 + radius - radius * math.cos(a)))
    prof.append((depth_back, z0 + height))
    verts, faces = [], []
    for x in (-width / 2, width / 2):
        verts += [(x, y, z) for y, z in prof]
    n = len(prof)
    faces = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    me = bpy.data.meshes.new('backdrop')
    me.from_pydata(verts, [], faces)
    me.polygons.foreach_set('use_smooth', [True] * len(faces))
    me.update()
    return me


def build_backdrop(spec, D, z_floor, mat):
    kind = spec['type']
    if kind == 'none':
        return None
    if kind == 'sweep':
        me = _sweep_mesh(spec['width_D'] * D, spec['front_D'] * D, spec['back_D'] * D, spec['radius_D'] * D,
                         spec['height_D'] * D, z_floor)
    elif kind == 'plane':
        s = spec['size_D'] * D / 2
        me = bpy.data.meshes.new('backdrop')
        me.from_pydata([(-s, -s, z_floor), (s, -s, z_floor), (s, s, z_floor), (-s, s, z_floor)], [], [(0, 1, 2, 3)])
    else:
        raise ValueError(f'unknown backdrop type {kind!r}')
    ob = bpy.data.objects.new('backdrop', me)
    ob.data.materials.append(mat)
    ob.pass_index = 2
    if spec.get('shadow_catcher'):
        ob.is_shadow_catcher = True
    bpy.context.scene.collection.objects.link(ob)
    return ob


def find_hdri(name, sha_expected, search):
    for d in search:
        p = os.path.join(os.path.expanduser(d), name)
        if os.path.isfile(p):
            got = sha256(p)
            if sha_expected and got != sha_expected:
                raise ValueError(f'HDRI {p} sha256 {got} != pinned {sha_expected}')
            return p
    return None


def build_world(spec, hdri_path, scale=1.0):
    """World = background colour for camera rays; HDRI (if any) for the rest (or glossy rays only)."""
    w = bpy.data.worlds.new('world')
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg_cam = nt.nodes.new('ShaderNodeBackground')
    bg_cam.inputs['Color'].default_value = (*spec.get('camera_color', [0, 0, 0]), 1)
    bg_cam.inputs['Strength'].default_value = scale
    if not hdri_path:
        bg_cam2 = nt.nodes.new('ShaderNodeBackground')
        bg_cam2.inputs['Color'].default_value = (*spec.get('fallback_color', [0.05, 0.05, 0.05]), 1)
        bg_cam2.inputs['Strength'].default_value = scale
        env_out = bg_cam2.outputs['Background']
    else:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Rotation'].default_value = (0, 0, math.radians(spec.get('rotation_deg', 0.0)))
        env = nt.nodes.new('ShaderNodeTexEnvironment')
        env.image = bpy.data.images.load(hdri_path, check_existing=True)
        env.interpolation = 'Cubic'
        nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
        bg = nt.nodes.new('ShaderNodeBackground')
        bg.inputs['Strength'].default_value = spec.get('strength', 1.0) * scale
        nt.links.new(env.outputs['Color'], bg.inputs['Color'])
        env_out = bg.outputs['Background']
        if spec.get('glossy_only'):
            lp = nt.nodes.new('ShaderNodeLightPath')
            black = nt.nodes.new('ShaderNodeBackground')
            black.inputs['Color'].default_value = (0, 0, 0, 1)
            mix = nt.nodes.new('ShaderNodeMixShader')
            nt.links.new(lp.outputs['Is Glossy Ray'], mix.inputs['Fac'])
            nt.links.new(black.outputs['Background'], mix.inputs[1])
            nt.links.new(env_out, mix.inputs[2])
            env_out = mix.outputs['Shader']
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(env_out, mix.inputs[1])
    nt.links.new(bg_cam.outputs['Background'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return w


def gpu_devices(kind):
    """Enable only `kind` (OPTIX/CUDA) devices; returns their names. Raises if none (never falls back)."""
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = kind
    prefs.get_devices()
    on = []
    for d in prefs.devices:
        d.use = d.type == kind
        if d.use:
            on.append(d.name)
    if not on:
        raise RuntimeError(f'no {kind} device available; refusing to fall back to CPU')
    return on


def setup_render(profile, threads=16):
    sc = bpy.context.scene
    r = sc.render
    r.engine = 'CYCLES'
    w, h = profile['res']
    r.resolution_x, r.resolution_y, r.resolution_percentage = int(w), int(h), 100
    r.threads_mode = 'FIXED'
    r.threads = int(threads)
    r.use_persistent_data = True
    r.film_transparent = bool(profile.get('film_transparent', False))
    c = sc.cycles
    dev = profile.get('device', 'CPU').upper()
    devices = ['CPU']
    if dev in ('OPTIX', 'CUDA'):
        devices = gpu_devices(dev)
        c.device = 'GPU'
    elif dev == 'CPU':
        c.device = 'CPU'
    else:
        raise ValueError(f'unknown device {dev}')
    c.samples = int(profile['spp_max'])
    c.use_adaptive_sampling = bool(profile.get('adaptive', True))  # False for the fixed-spp Q7 reference
    c.adaptive_min_samples = int(profile.get('spp_min', 0))
    c.adaptive_threshold = float(profile.get('adaptive_threshold', 0.01))
    b = profile.get('bounces', {})
    c.max_bounces = b.get('max', 12)
    c.glossy_bounces = b.get('glossy', 8)
    c.diffuse_bounces = b.get('diffuse', 4)
    c.transmission_bounces = b.get('transmission', 8)
    c.transparent_max_bounces = b.get('transparent', 8)
    c.sample_clamp_direct = float(profile.get('clamp_direct', 0.0))
    c.sample_clamp_indirect = float(profile.get('clamp_indirect', 10.0))
    c.blur_glossy = float(profile.get('filter_glossy', 0.5))
    c.use_light_tree = True
    # one 4K tile fits easily in 24 GB; tiling cost ~30 % at 4K in lookdev (Q1)
    c.use_auto_tile = bool(profile.get('auto_tile', False))
    c.use_denoising = False  # raw stays raw; the denoised copy is made in the compositor
    c.use_animated_seed = False
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    vl = sc.view_layers[0]
    vl.use_pass_normal = True
    vl.use_pass_z = True
    vl.use_pass_object_index = True
    vl.cycles.denoising_store_passes = bool(profile.get('denoise', True))
    vl.cycles.pass_debug_sample_count = True
    return devices


def setup_compositor(tmpdir, denoise=True, codec='ZIP'):
    """File outputs into tmpdir: raw.exr (RGBA half), den.exr (RGBA half, OIDN with albedo+normal),
    normal.exr, depth.exr (float), mask.exr (antialiased product id mask), spp.exr (sample count)."""
    sc = bpy.context.scene
    sc.use_nodes = True
    nt = sc.node_tree
    nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers')

    def fout(sub, sock, depth='16', mode='RGBA'):
        o = nt.nodes.new('CompositorNodeOutputFile')
        o.base_path = tmpdir
        o.format.file_format = 'OPEN_EXR'
        o.format.color_depth = depth
        o.format.exr_codec = codec
        o.format.color_mode = mode
        o.file_slots[0].path = sub + '_'
        nt.links.new(sock, o.inputs[0])
        return o

    fout('raw', rl.outputs['Image'])
    if denoise:
        dn = nt.nodes.new('CompositorNodeDenoise')
        dn.prefilter = 'ACCURATE'
        dn.use_hdr = True
        nt.links.new(rl.outputs['Image'], dn.inputs['Image'])
        nt.links.new(rl.outputs['Denoising Normal'], dn.inputs['Normal'])
        nt.links.new(rl.outputs['Denoising Albedo'], dn.inputs['Albedo'])
        fout('den', dn.outputs['Image'])
    fout('normal', rl.outputs['Normal'], mode='RGB')
    fout('depth', rl.outputs['Depth'], depth='32', mode='RGB')
    idm = nt.nodes.new('CompositorNodeIDMask')
    idm.index = 1
    idm.use_antialiasing = True
    nt.links.new(rl.outputs['IndexOB'], idm.inputs['ID value'])
    fout('mask', idm.outputs['Alpha'], mode='RGB')
    fout('spp', rl.outputs['Debug Sample Count'], depth='32', mode='RGB')
    comp = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(rl.outputs['Image'], comp.inputs['Image'])
