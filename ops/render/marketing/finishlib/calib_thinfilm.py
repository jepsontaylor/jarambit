"""Blender: thin-film thickness swatch chart on Ti (Principled metallic + thin film), 1 row of spheres.
blender -b --factory-startup -P calib_thinfilm.py -- OUT.png [ior]"""
import sys, bpy, math
argv = sys.argv[sys.argv.index('--') + 1:]
out = argv[0]; ior = float(argv[1]) if len(argv) > 1 else 2.3
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 64
sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = 1800, 260
sc.view_settings.view_transform = 'AgX'
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.8, 0.8, 0.8, 1); w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
ths = list(range(0, 361, 20))
for i, th in enumerate(ths):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, location=(i - len(ths) / 2, 0, 0), segments=48, ring_count=24)
    o = bpy.context.object; bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new(f't{th}'); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Metallic'].default_value = float(argv[2]) if len(argv)>2 else 1; b.inputs['Base Color'].default_value = (0.542, 0.497, 0.449, 1)
    b.inputs['Specular Tint'].default_value = (0.62, 0.59, 0.56, 1); b.inputs['Roughness'].default_value = 0.25
    b.inputs['Thin Film Thickness'].default_value = th; b.inputs['Thin Film IOR'].default_value = ior
    o.data.materials.append(m)
    bpy.ops.object.text_add(location=(i - len(ths) / 2 - 0.3, -0.5, -0.75)); t = bpy.context.object; t.data.body = str(th); t.scale = (0.25,) * 3
    t.rotation_euler = (math.pi / 2, 0, 0)
cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = len(ths) + 0.5; cam.location = (-0.5, -10, 0); cam.rotation_euler = (math.pi / 2, 0, 0)
L = bpy.data.objects.new('l', bpy.data.lights.new('l', 'AREA')); L.data.energy = 3000; L.data.size = 6
L.location = (0, -6, 5); L.rotation_euler = (math.radians(50), 0, 0); sc.collection.objects.link(L)
sc.render.filepath = out; bpy.ops.render.render(write_still=True)
