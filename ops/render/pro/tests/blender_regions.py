"""CPU-only independent pixel and image-lifetime regression for issue #53."""
import ast
import copy
import json
import math
import os
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[4]
PRO = ROOT / 'ops/render/pro'
OUT = Path(sys.argv[sys.argv.index('--') + 1])
OUT.mkdir(parents=True, exist_ok=True)
tree = ast.parse((PRO / 'pro_hero.py').read_text())
functions = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[])
begin = next(i for i, n in enumerate(tree.body) if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'FINISH' for t in n.targets))
end = next(i for i, n in enumerate(tree.body[begin:], begin) if isinstance(n, ast.Expr)
           and ast.unparse(n).strip() == 'part.data.update()')
assignments = compile(ast.Module(body=tree.body[begin:end+1], type_ignores=[]), 'material_assignment', 'exec')
cfg = json.loads((PRO / 'shots.json').read_text())
scene = bpy.context.scene
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 8; scene.cycles.seed = 0
scene.cycles.use_denoising = False
scene.render.threads_mode = 'FIXED'; scene.render.threads = 4
scene.render.resolution_x = scene.render.resolution_y = 128; scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'Standard'
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.4, .4, .4, 1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value = 1
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

def png(name, pixels):
    p = OUT / name
    im = bpy.data.images.new(name, 64, 64, float_buffer=True)
    im.pixels = pixels.ravel()
    scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_depth = '16'
    scene.render.image_settings.color_mode = 'RGB'
    im.save_render(str(p), scene=scene)
    bpy.data.images.remove(im)
    return str(p)

art_values = np.tile([.8, .1, .05, 1.], (64, 64, 1))
mask_values = np.zeros((64, 64, 4)); mask_values[:, :, 3] = 1
mask_values[8:56, 8:56, :3] = .25   # Partial ink coverage must also exclude every finish.
mask_values[16:48, 16:48, :3] = 1
art = png('art.png', art_values); mask = png('mask.png', mask_values)
placement = {'len_mm': 40, 'h_mm': 40, 'center_xz_m': [0, 0], 'angle_deg': 0}
man = {'art': {'path': art, 'width_m': .1, 'height_m': .1, 'x0_m': -.05, 'z_mid_m': 0},
       'signature': {'mask': mask, 'mask_px': [64, 64], 'ink_px': [0, 0, 64, 64],
                     'placements': {'front': placement, 'back': placement}}}
verts, faces = [], []
for x0, x1, z0, z1 in [(-.05, .05, -.05, .05), (-.08, -.06, .02, .04),
                       (-.08, -.06, -.01, .01), (-.08, -.06, -.04, -.02)]:
    offset = len(verts)
    verts.extend([(x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1)])
    faces.append(tuple(range(offset, offset+4)))
mesh = bpy.data.meshes.new('regions'); mesh.from_pydata(verts, [], faces); mesh.update()
part = bpy.data.objects.new('regions', mesh); scene.collection.objects.link(part)
for i, poly in enumerate(mesh.polygons):
    poly.material_index = i
camera_data = bpy.data.cameras.new('camera'); camera_data.type = 'ORTHO'; camera_data.ortho_scale = .2
camera = bpy.data.objects.new('camera', camera_data); scene.collection.objects.link(camera)
camera.location = (0, -.5, 0); camera.rotation_euler = (Vector((0, 0, 0))-camera.location).to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera
env = dict(bpy=bpy, np=np, math=math, os=os, json=json, HERE=str(PRO), MAN=man,
           lo=np.array([-.05, -.003, -.05]), hi=np.array([.05, .003, .05]), part=part,
           labels={'0': 'body', '1': 'bevel', '2': 'serration', '3': 'edge_apex'}, RX=64, RY=64)
exec(compile(functions, str(PRO / 'pro_hero.py'), 'exec'), env)
results = []
baseline = None
for finish in ('art', 'flame', 'satin_blue'):
    for override in (False, True):
        config = copy.deepcopy(cfg)
        if override:
            config['look'].update(film_nm=40, coat=1, gold_emit=7, ground_ti=[1, 0, 0], ground_rough=.9)
            config['flame'].update(coat=1, aniso=.9, bevel_flamed=True)
            config['flame']['look'].update(film_nm=40, ground_ti=[1, 0, 0], gold_emit=7)
            config['finishes']['satin_blue'].update(coat=1, aniso=.9, bevel_flamed=True)
        env.update(CFG=config, LOOK=config['look'], A={'--finish': finish})
        part.data.materials.clear()
        exec(assignments, env)
        for i, poly in enumerate(part.data.polygons):
            poly.material_index = i
        protected = part.data.materials[0].node_tree.nodes['protected_laser_etched_ti']
        metallic = protected.inputs['Metallic']
        assert metallic.default_value == 1 and not metallic.is_linked
        properties = {key: {'value': protected.inputs[key].default_value, 'linked': protected.inputs[key].is_linked}
                      for key in ('Coat Weight', 'Thin Film Thickness', 'Anisotropic', 'Emission Strength')}
        assert all(p['value'] == 0 and not p['linked'] for p in properties.values())
        assert all(m.name.startswith('pro_ground_ti') for m in list(part.data.materials)[1:])
        bpy.ops.render.render()
        # Render Result has no public pixel buffer in background Blender; read its lossless master.
        scene.render.image_settings.file_format = 'OPEN_EXR'; scene.render.image_settings.color_depth = '32'
        scene.render.image_settings.color_mode = 'RGBA'
        master = OUT / f'{finish}_{override}.exr'
        bpy.data.images['Render Result'].save_render(str(master), scene=scene)
        rendered = bpy.data.images.load(str(master))
        pixels = np.array(rendered.pixels[:], np.float32).reshape(128, 128, 4)
        bpy.data.images.remove(rendered)
        if baseline is None:
            baseline = pixels.copy()
        mark_error = float(np.max(np.abs(pixels[62:66, 62:66] - baseline[62:66, 62:66])))
        # Stay inside partial ink: a pixel straddling the outer glyph boundary legitimately includes finish.
        fringe_error = float(np.max(np.abs(pixels[56:58, 62:66] - baseline[56:58, 62:66])))
        grind_error = float(np.max(np.abs(pixels[[44, 64, 83], 19] - baseline[[44, 64, 83], 19])))
        results.append({'finish': finish, 'override': override, 'protected_inputs': properties,
                        'mark_metallic': metallic.default_value, 'mark_metallic_linked': metallic.is_linked,
                        'mark_pixel_max_diff': mark_error, 'grind_pixel_max_diff': grind_error,
                        'antialiased_mark_pixel_max_diff': fringe_error,
                        'body_pixel_diff': float(np.max(np.abs(pixels[64, 87] - baseline[64, 87])))})
        assert mark_error < 1e-6 and fringe_error < 1e-6 and grind_error < 1e-6, results[-1]

env['CFG'] = cfg
dark = png('frame.png', np.tile([.02, .02, .02, 1.], (64, 64, 1)))
before = len(bpy.data.images)
for i in range(30):
    assert env['frame_qa_image'](dark, i)['pass']
assert len(bpy.data.images) == before
# A reshape failure must free the image too.
env['RX'] = 65
try:
    env['image_pixels'](dark)
except ValueError:
    pass
else:
    raise AssertionError('bad dimensions unexpectedly accepted')
assert len(bpy.data.images) == before
(OUT / 'result.json').write_text(json.dumps({'finishes': results, 'qa_images_retained': 0}, indent=2))
