"""Lighting rigs (presets/rig_*.json). Sizes/distances are multiples of the object diagonal D.

Light positions are given around the camera axis (az 0 = camera side, +az camera-right, el up) and
stay fixed to the world for the whole shot, so a turntable moves reflections across the part.
`aim: "mirror"` places a light on the mirror direction of a region's mean normal as seen from the
camera at the shot's first frame (moves the light, never the normals).
"""
import math

import bpy
import numpy as np
from mathutils import Vector

import rigmath


def _point_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def _emission_nodes(light, kelvin, strength=1.0):
    light.use_nodes = True
    nt = light.node_tree
    em = nt.nodes['Emission']
    em.inputs['Strength'].default_value = strength
    if kelvin:
        bb = nt.nodes.new('ShaderNodeBlackbody')
        bb.inputs['Temperature'].default_value = float(kelvin)
        nt.links.new(bb.outputs['Color'], em.inputs['Color'])


def mirror_position(region_pts, region_nrm, cam_pos, dist, normal_filter=None, offset_deg=(0.0, 0.0)):
    """Light/card position on the mirror direction of a region's mean normal seen from the camera.
    normal_filter: None | 'toward_camera' | 'up' | 'down' (subset of the region's triangles);
    offset_deg: (d_az, d_el) rotation of the mirror direction, to place a gradient edge or strip
    beside the exact reflection."""
    pts, nrm = np.asarray(region_pts), np.asarray(region_nrm)
    v_all = cam_pos - pts
    v_all /= np.linalg.norm(v_all, axis=1)[:, None]
    facing = np.einsum('ij,ij->i', nrm, v_all) > 0.05
    sel = facing.copy()
    if normal_filter == 'toward_camera':
        sel &= np.einsum('ij,ij->i', nrm, v_all) > 0.5
    elif normal_filter == 'up':
        sel &= nrm[:, 2] > 0.15
    elif normal_filter == 'down':
        sel &= nrm[:, 2] < -0.15
    if not sel.any():
        sel = facing if facing.any() else np.ones(len(nrm), bool)
    p = pts[sel].mean(0)
    n = nrm[sel].sum(0); n /= np.linalg.norm(n)
    v = cam_pos - p; v /= np.linalg.norm(v)
    r = 2 * (n @ v) * n - v
    daz, del_ = offset_deg
    if daz or del_:
        az = np.degrees(np.arctan2(r[0], -r[1])) + daz
        el = np.degrees(np.arcsin(np.clip(r[2], -1, 1))) + del_
        r = rigmath.cam_dir(az, el)
    return p + dist * r, p


def _placement(L, D, t, mirror_ctx):
    dist = L['dist_D'] * D
    if L.get('aim') == 'mirror' and mirror_ctx is not None:
        pts, nrm = mirror_ctx['regions'][L['region']]
        return mirror_position(pts, nrm, mirror_ctx['cam_pos'], dist, L.get('normal_filter'),
                               tuple(L.get('offset_deg', (0.0, 0.0))))
    pos = t + rigmath.light_position(L['az'], L['el'], dist)
    return pos, t + np.asarray(L.get('aim_offset_D', [0, 0, 0]), float) * D


def _card(L, name, D, t, mirror_ctx=None):
    """Flag/bounce card: a camera-invisible plane (black flag or white bounce) that metal reflects."""
    w, h = L['size_D'][0] * D / 2, L['size_D'][1] * D / 2
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w, -h, 0), (w, -h, 0), (w, h, 0), (-w, h, 0)], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    p = mat.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (*L.get('color', [0.005, 0.005, 0.005]), 1)
    p.inputs['Roughness'].default_value = 1.0
    p.inputs['Specular IOR Level'].default_value = 0.0
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    pos, aim_at = _placement(L, D, t, mirror_ctx)
    ob.location = Vector(pos.tolist())
    _point_at(ob, aim_at.tolist())
    ob.visible_camera = False
    ob.visible_shadow = bool(L.get('cast_shadow', False))
    return {'name': name, 'type': 'CARD', 'color': L.get('color', [0.005] * 3), 'pos_m': [round(x, 5) for x in pos]}


def arc_segments(L):
    """Expand an ARC light into world-fixed strip segments along an arc over the camera.

    The arc runs from camera-right (az_from, +az) to camera-left (az_to, -az), rising from el_side
    at the ends to el_top over the camera axis: el(s) = el_side + (el_top - el_side) * sin(pi * s).
    Each segment is a long thin AREA strip aimed at the target, its long side along the arc tangent.
    Returns plain dicts (name, az, el, size_D, roll_deg-free tangent) so host tests need no bpy."""
    n = int(L.get('segments', 9))
    a0, a1 = float(L.get('az_from', 75.0)), float(L.get('az_to', -75.0))
    e_side, e_top = float(L.get('el_side', 35.0)), float(L.get('el_top', 60.0))
    out = []
    for i in range(n):
        s0, s1, sm = i / n, (i + 1) / n, (i + 0.5) / n
        p0 = rigmath.cam_dir(a0 + (a1 - a0) * s0, e_side + (e_top - e_side) * math.sin(math.pi * s0))
        p1 = rigmath.cam_dir(a0 + (a1 - a0) * s1, e_side + (e_top - e_side) * math.sin(math.pi * s1))
        az = a0 + (a1 - a0) * sm
        el = e_side + (e_top - e_side) * math.sin(math.pi * sm)
        chord = float(np.linalg.norm(p1 - p0))  # unit-sphere chord, scaled by dist below
        out.append({'name': f"{L.get('name', 'arc')}_{i:02d}", 'az': az, 'el': el,
                    'tangent': (p1 - p0) / max(chord, 1e-9), 'len_unit': chord})
    return out


def emitter_corners(L, D, t=np.zeros(3)):
    """World-space corner points of every emitter in a light spec (for the frustum check)."""
    dist = L['dist_D'] * D
    pts = []
    if L.get('type') == 'ARC':
        w = L.get('width_D', 0.25) * D / 2
        for seg in arc_segments(L):
            c = t + rigmath.light_position(seg['az'], seg['el'], dist)
            tan = seg['tangent']
            nrm = (t - c) / np.linalg.norm(t - c)
            side = np.cross(nrm, tan); side /= np.linalg.norm(side)
            h = seg['len_unit'] * dist / 2 * 1.02
            pts += [c + a * h * tan + b * w * side for a in (-1, 1) for b in (-1, 1)]
        return np.array(pts)
    if L.get('aim') == 'mirror':
        return None  # resolved at build time; checked from the built objects
    c = t + rigmath.light_position(L['az'], L['el'], dist)
    r = 0.5 * max(L.get('size_D', [0.1, 0.1])) * D
    return np.array([c + r * np.array(d) for d in
                     [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]])


def _arc(L, D, t, exposure_scale):
    """Curved strip softbox: ARC -> N AREA strips. power_W is the TOTAL for the arc."""
    segs = arc_segments(L)
    dist = L['dist_D'] * D
    total = float(L['power_W']) * (D / 0.2) ** 2 * exposure_scale * 2.0 ** float(L.get('ev', 0.0))
    rec = []
    for seg in segs:
        ld = bpy.data.lights.new(seg['name'], 'AREA')
        ld.energy = total / len(segs)
        ld.shape = 'RECTANGLE'
        ld.size = L.get('width_D', 0.25) * D          # local X: across the strip
        ld.size_y = seg['len_unit'] * dist * 1.02     # local Y: along the arc (slight overlap, no gaps)
        if 'spread_deg' in L:
            ld.spread = math.radians(L['spread_deg'])
        _emission_nodes(ld, L.get('kelvin', 6500))
        ob = bpy.data.objects.new(seg['name'], ld)
        bpy.context.scene.collection.objects.link(ob)
        pos = t + rigmath.light_position(seg['az'], seg['el'], dist)
        ob.location = Vector(pos.tolist())
        fwd = Vector((t - pos).tolist()).normalized()       # light emits along local -Z
        tan = Vector(seg['tangent'].tolist())
        ob.rotation_euler = fwd.to_track_quat('-Z', 'Y').to_euler()
        # roll so local +Y follows the arc tangent
        y_now = ob.rotation_euler.to_matrix() @ Vector((0, 1, 0))
        tan_p = (tan - tan.dot(fwd) * fwd).normalized()
        ang = y_now.angle(tan_p)
        if y_now.cross(tan_p).dot(-fwd) < 0:
            ang = -ang
        ob.rotation_euler.rotate_axis('Z', ang)
        _hide_from_camera(ob)
        rec.append({'name': seg['name'], 'type': 'AREA(ARC)', 'power_W': round(total / len(segs), 4),
                    'pos_m': [round(x, 5) for x in pos], 'kelvin': L.get('kelvin', 6500)})
    return rec


def _hide_from_camera(ob):
    """Art direction 2026-10-13: emitters are never seen by camera rays (they still light the part
    and show in its glossy reflections). Not overridable per rig."""
    ob.visible_camera = False
    ob.visible_transmission = False


def build(rig, D, target_world, exposure_scale=1.0, mirror_ctx=None):
    """Create the rig's lights. Power is `power_W` x (D / 0.2 m)^2 x exposure_scale (2^exposure_ev).
    Returns a manifest record (resolved positions/powers)."""
    rec = []
    t = np.asarray(target_world, float)
    for i, L in enumerate(rig['lights']):
        name = L.get('name', f'light{i}')
        kind = L.get('type', 'AREA')
        if kind == 'CARD':
            rec.append(_card(L, name, D, t, mirror_ctx))
            continue
        if kind == 'ARC':
            rec.extend(_arc(L, D, t, exposure_scale))
            continue
        ld = bpy.data.lights.new(name, kind)
        power = float(L['power_W']) * (D / 0.2) ** 2 * exposure_scale * 2.0 ** float(L.get('ev', 0.0))
        ld.energy = power
        if kind == 'AREA':
            ld.shape = L.get('shape', 'RECTANGLE')
            ld.size = L['size_D'][0] * D
            ld.size_y = L['size_D'][1] * D
            if 'spread_deg' in L:
                ld.spread = math.radians(L['spread_deg'])
        elif kind in ('POINT', 'SPOT'):
            ld.shadow_soft_size = L.get('radius_D', 0.05) * D
        _emission_nodes(ld, L.get('kelvin', 6500))
        ob = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(ob)
        pos, aim_at = _placement(L, D, t, mirror_ctx)
        ob.location = Vector(pos.tolist())
        _point_at(ob, aim_at.tolist())
        if 'roll_deg' in L:
            ob.rotation_euler.rotate_axis('Z', math.radians(L['roll_deg']))
        _hide_from_camera(ob)
        rec.append({'name': name, 'type': kind, 'power_W': round(power, 4), 'pos_m': [round(x, 5) for x in pos],
                    'kelvin': L.get('kelvin', 6500)})
    return rec
