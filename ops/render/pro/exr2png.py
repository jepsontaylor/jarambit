"""Re-encode a 32-bit EXR master to a 16-bit PNG with the shot's view transform and Blender dither.
blender -b -P exr2png.py -- IN.exr OUT.png LOOK EXPOSURE_EV"""
import sys, bpy
a = sys.argv[sys.argv.index('--') + 1:]
src, dst, look, ev = a[0], a[1], a[2], float(a[3])
sc = bpy.context.scene
sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = look; sc.view_settings.exposure = ev
sc.render.dither_intensity = 1.0
s = sc.render.image_settings; s.file_format = 'PNG'; s.color_depth = '16'; s.color_mode = 'RGB'; s.compression = 15
im = bpy.data.images.load(src)
im.save_render(dst, scene=sc)
print('WROTE', dst)
