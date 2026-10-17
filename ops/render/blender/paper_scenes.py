"""Actual-STL Cycles plates for the paper; run through render_paper.py.

Surface colors are either an illustrative finish or the explicitly identified retained
plate FEM envelope. No stress field, displacement, fillet or manufactured part is invented.
"""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
SUBJECT = 'w282_p14_c01'
BASE = ROOT / 'evidence/rs_v2/w282_ultrarunner'
STL = BASE / (SUBJECT + '.stl')
D1 = BASE / (SUBJECT + '_D1.json')
OVERLAY = None
SCENES = {
    'cad_watertight_and_single_solid': ('01 / Exported topology', 'One closed solid · mass parity ≤ 1%', 'mesh'),
    'geometric_and_holder_gates': ('02 / Manufacturing & holder', '200 × 100 mm plan envelope · 9 mm stack', 'holder'),
    'karambit_ring_and_curved_claw': ('03 / Ring & curved outline', 'Ring ID 25.4 ± 0.5 mm · hook drop ≥ 25 mm', 'ring'),
    'c6_aesthetic_floor': ('04 / C.6 shape constraints', 'Reference distances, curvature, groove & grip checks', 'beauty'),
    'cert_hiker_180n': ('05 / Hiker lateral load', 'Ring clamped · out-of-plane tip load 180 N', 'lateral'),
    'cert_hunter_260n': ('06 / Hunter lateral load', 'Ring clamped · out-of-plane tip load 260 N', 'lateral'),
    'strict_hunter_260n': ('07 / Strict lateral mesh', '260 N floor · 0.0625 mm² maximum triangle area', 'lateral'),
    'cert_ring_pull_1500n': ('08 / Ring pull', '1,500 N bore traction · seated guard / ricasso band', 'pull'),
    'twist_body_1p82nm': ('09 / Body chord torsion', '1.82 N·m · body peak more than 15 mm from tip', 'torque'),
    'twist_tip_only_1p82nm': ('10 / Tip-loaded chord torsion', '1.82 N·m · 4 mm load-patch exclusion', 'torque'),
    'twist_tip_submodel_strict_1p82nm': ('11 / Strict tip annulus', '1.82 N·m · stress region 4–15 mm behind tip', 'tip'),
    'solid_tip_3d_p2_1p82nm': ('12 / Quadratic solid tip', '30 mm local submodel · independent P2 elasticity', 'tip'),
    'side_a4_buckling_and_support': ('13 / Compliant support & buckling', 'Bore springs + grip foundation · λcr ≥ 1', 'support'),
    'failure_sequence_1p2': ('14 / Failure sequence', 'Hand / blade yield-onset load ratio ≥ 1.20', 'sequence'),
    'plate_gci_valid_3level': ('15 / Mesh convergence', 'Three distinct meshes · identical observable', 'mesh'),
    'dolfinx_cross_check_2pct': ('16 / Independent solver comparison', 'scikit-fem versus DOLFINx · relative error ≤ 2%', 'tip'),
    'hero_oblique': ('JARAMBIT / Titanium study', 'w282_p14_c01 · historical screen record', 'hero'),
    'hero_reverse': ('JARAMBIT / Reverse face', 'Actual exported STL · illustrative anodized finish', 'reverse'),
    'hero_section': ('JARAMBIT / Ring & section', 'Illustrative sizing gauge · actual mesh cut at z = 0', 'section'),
}


def material(name, color, metallic=0., roughness=.4):
    m = bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    bsdf=m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Metallic'].default_value=metallic
    bsdf.inputs['Roughness'].default_value=roughness
    return m


def emission(name, color):
    m=material(name,color);bsdf=m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Emission Color'].default_value=(*color,1)
    bsdf.inputs['Emission Strength'].default_value=1
    return m


def stl_triangles(path):
    raw=path.read_bytes()
    if raw.startswith(b'solid ') and b'vertex ' in raw[:1024]:
        import re
        return np.asarray(re.findall(rb'vertex\s+(\S+)\s+(\S+)\s+(\S+)',raw),float).reshape(-1,3,3)
    n=struct.unpack_from('<I',raw,80)[0]
    dt=np.dtype([('normal','<f4',(3,)),('v','<f4',(3,3)),('attr','<u2')])
    return np.frombuffer(raw,dtype=dt,count=n,offset=84)['v'].astype(float)


def mesh_obj(name, vertices, faces, mat):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def line(name, pts, mat, radius=.00055):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.bevel_depth=radius;curve.bevel_resolution=3
    spl=curve.splines.new('POLY');spl.points.add(len(pts)-1)
    for p,q in zip(spl.points,pts):p.co=(*q,1)
    obj=bpy.data.objects.new(name,curve);bpy.context.collection.objects.link(obj);obj.data.materials.append(mat)
    return obj


def arrow(a,b,mat,r=.001):
    a,b=Vector(a),Vector(b);d=b-a;u=d.normalized()
    line('Load direction',[a,b-u*.006],mat,r*.45)
    bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=r*2.4,radius2=0,depth=.007,location=b-u*.0035)
    ob=bpy.context.object;ob.rotation_euler=d.to_track_quat('Z','Y').to_euler();ob.data.materials.append(mat)


def circle(center,radius,mat,z=.008,start=0,end=2*math.pi):
    return line('Reference circle',[(center[0]+radius*math.cos(t),center[1]+radius*math.sin(t),z) for t in np.linspace(start,end,100)],mat)


def label(camera,body,x,y,size,mat):
    factor=.03/.35 if camera.data.type=='PERSP' else 1.
    font=bpy.data.curves.new('Caption','FONT');font.body=body;font.size=size;font.space_character=1.05
    ob=bpy.data.objects.new('Caption',font);OVERLAY.collection.objects.link(ob)
    ob.parent=camera;ob.location=(x*factor,y*factor,-.03);ob.scale=(factor,factor,factor);ob.data.materials.append(mat)
    # Camera-facing labels are graphic annotations; they do not cast shadows onto the CAD.
    ob.visible_shadow=False


def light(name,loc,energy,size,color,target):
    bpy.ops.object.light_add(type='AREA',location=loc);ob=bpy.context.object;ob.name=name
    ob.data.energy=energy;ob.data.shape='DISK';ob.data.size=size;ob.data.color=color
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()


def plate_field(d,mat):
    mesh=d['mesh'];xy=np.asarray(mesh['xy']);tris=np.asarray(mesh['tris'])
    te=np.asarray(mesh['te']);values=np.asarray(mesh['env_vm'])
    # Display on the retained element mesh, above the CAD. Heights are actual per-element
    # thicknesses. Geometry is not deformed. Fixed scale 0..828 MPa, matching figlib.
    verts=[];faces=[]
    for i,tri in enumerate(tris):
        verts.extend([(xy[k,0]*.001,xy[k,1]*.001,te[i]*.0005+.00035) for k in tri]);faces.append((3*i,3*i+1,3*i+2))
    ob=mesh_obj('Retained D1 envelope',verts,faces,mat)
    # A declared blue-cyan-yellow-red transfer function, not material or surface temperature.
    ramps=np.array([[.04,.08,.35],[0,.45,.7],[.08,.7,.6],[.95,.8,.12],[.8,.08,.05]])
    attr=ob.data.color_attributes.new(name='von_mises',type='FLOAT_COLOR',domain='CORNER')
    for i,v in enumerate(values):
        t=np.clip(v/828.,0,1)*4;j=min(int(t),3);color=ramps[j]*(1-(t-j))+ramps[j+1]*(t-j)
        for k in range(3):attr.data[3*i+k].color=(*color,1)
    m=bpy.data.materials.new('D1 measured plate envelope / 0..828 MPa');m.use_nodes=True
    nt=m.node_tree;bs=nt.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.65
    v=nt.nodes.new('ShaderNodeVertexColor');v.layer_name='von_mises';nt.links.new(v.outputs['Color'],bs.inputs['Base Color'])
    ob.data.materials.clear();ob.data.materials.append(m)


def main():
    global OVERLAY
    p=argparse.ArgumentParser();p.add_argument('--scene',choices=SCENES,required=True);p.add_argument('--output',required=True)
    p.add_argument('--samples',type=int,default=48);p.add_argument('--width',type=int,default=1600)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    title,subtitle,mode=SCENES[args.scene];d=json.loads(D1.read_text())
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=args.samples
    s.cycles.use_denoising=True;s.cycles.seed=42;s.render.threads_mode='FIXED';s.render.threads=4
    s.render.resolution_x=args.width;s.render.resolution_y=1000;s.render.resolution_percentage=100
    s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.compression=85
    s.view_settings.view_transform='AgX';s.world.use_nodes=True
    s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.04,.05,.07,1)
    s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.15
    s.unit_settings.system='METRIC';s.unit_settings.length_unit='MILLIMETERS'
    dark=mode in ('hero','reverse','section')
    ti=material('Titanium / illustrative finish',(.43,.47,.52),.88,.26)
    if mode=='reverse':ti=material('Anodized titanium / illustrative only',(.16,.11,.34),.8,.25)
    orange=material('Load / force annotation',(.95,.20,.055),.2,.3)
    teal=material('Fixture / reference annotation',(.015,.42,.44),.1,.35)
    ink=emission('Caption ink',(.8,.85,.9) if dark else (.025,.055,.075))
    accent=emission('Caption accent',(.95,.38,.14) if dark else (.55,.12,.04))
    tri=stl_triangles(STL)*.001;vertices,indices=np.unique(tri.reshape(-1,3),axis=0,return_inverse=True)
    ob=mesh_obj('Actual committed '+SUBJECT,vertices.tolist(),indices.reshape(-1,3).tolist(),ti)
    center=(vertices.min(axis=0)+vertices.max(axis=0))/2;target=Vector((center[0],center[1],0))
    tip=Vector((d['outline'][np.argmax(np.asarray(d['outline'])[:,0])][0]*.001,
                d['outline'][np.argmax(np.asarray(d['outline'])[:,0])][1]*.001,0))
    # Select actual planform tip used by the saved outline; no geometry is remodeled.
    if mode=='reverse':
        # Move the camera underneath; preserve the input vertex positions.
        camera_pos=target+Vector((.035,.13,-.29));floor_z=.018
    else:camera_pos=target+Vector((.035,-.145,.31));floor_z=-.014
    if mode=='section':
        import bmesh
        bm=bmesh.new();bm.from_mesh(ob.data)
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-9,
                              plane_co=(0,0,0),plane_no=(0,0,1),clear_outer=True,clear_inner=False)
        bm.to_mesh(ob.data);bm.free()
    floor=material('Studio backdrop',(.012,.02,.032) if dark else (.72,.73,.70),.05,.5)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(target.x,target.y,floor_z));bpy.context.object.data.materials.append(floor)
    bpy.ops.object.camera_add(location=camera_pos);cam=bpy.context.object;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';cam.data.ortho_scale=.285;s.camera=cam
    # Orthographic technical plates stay sharp; hero uses perspective depth of field.
    if dark and mode!='section':
        cam.data.type='PERSP';cam.data.lens=44;cam.data.dof.use_dof=True;cam.data.dof.focus_distance=(target-cam.location).length;cam.data.dof.aperture_fstop=11
    # Composite typography separately so studio depth of field cannot blur or hide labels.
    OVERLAY=bpy.data.scenes.new('Graphic annotations');OVERLAY.render.engine='CYCLES'
    OVERLAY.cycles.samples=1;OVERLAY.render.film_transparent=True
    OVERLAY.render.resolution_x=args.width;OVERLAY.render.resolution_y=1000
    OVERLAY.render.resolution_percentage=100;OVERLAY.world=s.world
    overlay_cam=cam.copy();overlay_cam.data=cam.data.copy();overlay_cam.data.dof.use_dof=False;overlay_cam.data.clip_start=.001
    OVERLAY.collection.objects.link(overlay_cam);OVERLAY.camera=overlay_cam
    s.use_nodes=True;nt=s.node_tree;nt.nodes.clear()
    bg=nt.nodes.new('CompositorNodeRLayers');bg.scene=s
    fg=nt.nodes.new('CompositorNodeRLayers');fg.scene=OVERLAY
    over=nt.nodes.new('CompositorNodeAlphaOver');nt.links.new(bg.outputs['Image'],over.inputs[1]);nt.links.new(fg.outputs['Image'],over.inputs[2])
    nt.links.new(over.outputs['Image'],nt.nodes.new('CompositorNodeComposite').inputs['Image'])
    light('Large cool key',target+Vector((-.08,-.08,.26)),1.4,.23,(.82,.91,1),target)
    light('Warm rim strip',target+Vector((.08,.12,.15)),1.8,.16,(1,.79,.58),target)
    light('Soft fill',target+Vector((.12,-.06,.12)),.48,.12,(.7,.83,1),target)
    if mode=='reverse':light('Underside key',target+Vector((-.06,.06,-.24)),1.5,.23,(.82,.91,1),target)
    if mode in ('lateral','pull','sequence'):
        plate_field(d,ti)
        label(cam,'Historical D1 plate envelope · 0–828 MPa · 260 N / 1.82 N·m / 1500 N',-.119,-.052,.0028,ink)
        # Fixed transfer-function legend, linear in MPa.
        colors=[(.04,.08,.35),(0,.45,.7),(.08,.7,.6),(.95,.8,.12),(.8,.08,.05)]
        for i,c in enumerate(colors):label(cam,'━━━━',-.118+i*.011,-.058,.003,emission('Scale '+str(i),c))
        label(cam,'0                          828 MPa',-.118,-.064,.0025,ink)
    else:label(cam,'Load / geometry illustration · no computed stress field shown',-.119,-.057,.003,ink)
    if mode=='lateral':
        circle((0,0),.014,teal)
        arrow(tip+Vector((0,0,.038)),tip+Vector((0,0,.004)),orange)
    if mode=='pull':
        arrow((-.043,0,.01),(-.015,0,.01),orange)
        for x in np.linspace(.077,.098,5):line('Seated band',[(x,-.008,.005),(x,.008,.005)],teal)
    if mode in ('torque','tip'):
        circle((tip.x-.01,tip.y),.014,orange,z=.015,start=.4,end=5.6)
        a=Vector((tip.x-.01+.014*math.cos(5.5),tip.y+.014*math.sin(5.5),.015))
        b=Vector((tip.x-.01+.014*math.cos(5.85),tip.y+.014*math.sin(5.85),.015));arrow(a,b,orange,r=.0007)
        circle((0,0),.014,teal)
    if mode in ('ring','section'):
        # A declared 22 mm sizing gauge, not a human hand or an ergonomic validation.
        bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=.011,depth=.04,location=(0,0,-.003))
        bpy.context.object.data.materials.append(material('22 mm sizing gauge',(.03,.35,.38),.45,.28))
        label(cam,'22 mm sizing gauge · illustrative fit; no comfort validation',-.119,-.046,.003,ink)
    if mode=='support':
        for x in np.linspace(.03,.075,8):
            line('Winkler spring',[(x,-.004,-.002),(x+.001,-.004,-.006),(x-.001,-.004,-.009),(x,-.004,-.012)],teal,.0003)
        for a in np.linspace(0,2*math.pi,9)[:-1]:arrow((.025*math.cos(a),.025*math.sin(a),.01),(.014*math.cos(a),.014*math.sin(a),.01),teal,.00055)
    if mode=='holder':
        line('200 × 100 mm envelope',[(-.018,-.054,.008),(.182,-.054,.008),(.182,.046,.008),(-.018,.046,.008),(-.018,-.054,.008)],teal)
        arrow((.095,-.067,.009),(.095,-.042,.009),orange)
        label(cam,'Envelope / pop-in illustration; holder surface not exported',-.119,-.046,.003,ink)
    if mode=='mesh':
        mesh=d['mesh'];xy=np.asarray(mesh['xy'])*.001
        # Decimated edge display is explicitly an illustration of the retained cert mesh.
        edges=set()
        for t in mesh['tris'][::12]:
            for a,b in [(t[0],t[1]),(t[1],t[2]),(t[2],t[0])]:edges.add(tuple(sorted((a,b))))
        for a,b in edges:line('Retained mesh edge',[(xy[a,0],xy[a,1],.006),(xy[b,0],xy[b,1],.006)],teal,.000055)
        label(cam,'Retained certification mesh · sparse edge display; no synthetic refinement',-.119,-.046,.0028,ink)
    if mode=='sequence':
        x=.102;line('Zone boundary',[(x,-.04,.01),(x,.035,.01)],orange,.0005)
    label(cam,'J A R A M B I T     /     ENGINEERING ATLAS',-.119,.067,.0033,ink)
    label(cam,title,-.119,.057,.0052,ink);label(cam,subtitle,-.119,.048,.0033,ink)
    label(cam,'HISTORICAL w282 · NO CURRENTLY CERTIFIED ALL-GATES WINNER',-.119,-.073,.0031,accent)
    s.render.filepath=args.output;bpy.ops.render.render(write_still=True)


if __name__=='__main__':main()
