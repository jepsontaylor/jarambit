"""Physical camera: 36 mm sensor (horizontal fit), focal/f-stop/focus from the request shot."""
import math

import bpy
from mathutils import Matrix

import rigmath


def build(cam_spec, clip=(0.001, 100.0)):
    cd = bpy.data.cameras.new('cam')
    cd.lens = float(cam_spec['focal_mm'])
    cd.sensor_width = float(cam_spec.get('sensor_mm', 36.0))
    cd.sensor_fit = 'HORIZONTAL'
    cd.clip_start, cd.clip_end = clip
    cd.dof.aperture_blades = int(cam_spec.get('blades', 9))
    cd.dof.aperture_rotation = math.radians(10)
    ob = bpy.data.objects.new('cam', cd)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.scene.camera = ob
    return ob


def place(cam_ob, cam_pos, target, roll_deg=0.0):
    right, up, back = rigmath.look_at_basis(cam_pos, target, roll_deg)
    M = Matrix(((right[0], up[0], back[0], cam_pos[0]),
                (right[1], up[1], back[1], cam_pos[1]),
                (right[2], up[2], back[2], cam_pos[2]),
                (0, 0, 0, 1)))
    cam_ob.matrix_world = M


def set_dof(cam_ob, focus_dist, fstop):
    d = cam_ob.data.dof
    if fstop is None or fstop <= 0:
        d.use_dof = False
        return
    d.use_dof = True
    d.focus_distance = float(focus_dist)
    d.aperture_fstop = float(fstop)
