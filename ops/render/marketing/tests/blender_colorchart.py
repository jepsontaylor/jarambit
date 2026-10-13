"""Blender-side Q6 fixture: render the 24 ColorChecker patches through Cycles to a scene-linear EXR.

Patches are emission-only planes (linear sRGB/Rec.709 values of the reference chart) seen by an
orthographic camera, so the render is exact up to sampling; the EXR then goes through finish.py
like any production frame. Also writes, with Blender's own colour management, a PNG of the same
EXR so the finish.py OCIO path can be compared against Blender (AgX parity).

blender -b --factory-startup -P blender_colorchart.py -- OUT_DIR
"""
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import finish  # noqa: E402

out = sys.argv[sys.argv.index('--') + 1]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 16
sc.cycles.use_denoising = False
sc.render.threads_mode = 'FIXED'
sc.render.threads = 8
sc.render.resolution_x, sc.render.resolution_y = 600, 400
sc.render.film_transparent = False
sc.render.filter_size = 0.01
lin = finish.srgb_to_linear(np.asarray(finish.COLORCHECKER_SRGB8) / 255.0)
# extra HDR/overrange gray patches exercise the AgX shoulder in the parity check
for i, c in enumerate(lin):
    r, col = divmod(i, 6)
    me = bpy.data.meshes.new(f'p{i}')
    x0, y0 = col * 100 + 5, (3 - r) * 100 + 5
    me.from_pydata([(x0, y0, 0), (x0 + 90, y0, 0), (x0 + 90, y0 + 90, 0), (x0, y0 + 90, 0)], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new(f'm{i}')
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial')
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*c, 1)
    e.inputs['Strength'].default_value = 1.0
    nt.links.new(e.outputs[0], o.inputs[0])
    me.materials.append(mat)
    ob = bpy.data.objects.new(f'p{i}', me)
    sc.collection.objects.link(ob)
w = bpy.data.worlds.new('w')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.18, 0.18, 0.18, 1)
cd = bpy.data.cameras.new('c')
cd.type = 'ORTHO'
cd.ortho_scale = 600
cam = bpy.data.objects.new('c', cd)
cam.location = (300, 200, 100)
sc.collection.objects.link(cam)
sc.camera = cam
sc.render.image_settings.file_format = 'OPEN_EXR'
sc.render.image_settings.color_depth = '32'
sc.render.filepath = os.path.join(out, 'chart.exr')
bpy.ops.render.render(write_still=True)

# Blender-native display encode of a test EXR (AgX + look) for the parity check
ramp = np.zeros((64, 256, 4), np.float32)
ramp[..., 3] = 1
x = np.geomspace(1e-4, 64.0, 256, dtype=np.float32)
ramp[:16, :, :3] = x[None, :, None]
ramp[16:32, :, 0] = x
ramp[32:48, :, 1] = x
ramp[48:, :, 2] = x
img = bpy.data.images.new('ramp', 256, 64, alpha=True, float_buffer=True)
img.pixels.foreach_set(ramp.ravel())
img.filepath_raw = os.path.join(out, 'ramp.exr')
img.file_format = 'OPEN_EXR'
img.save()
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'
sc.view_settings.exposure = 0
sc.view_settings.gamma = 1
sc.display_settings.display_device = 'sRGB'
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_depth = '16'
sc.render.image_settings.color_mode = 'RGB'
img2 = bpy.data.images.load(os.path.join(out, 'ramp.exr'))
img2.save_render(os.path.join(out, 'ramp_blender_agx.png'), scene=sc)
print('COLORCHART_OK')
