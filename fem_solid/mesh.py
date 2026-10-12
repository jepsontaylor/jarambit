#!/usr/bin/env python3
"""gmsh tet10 meshes (PR-0.30.2) -> dolfinx (mesh, facet tags). Runs in ghcr.io/fenics/dolfinx/dolfinx:v0.9.0 (gmsh 4.13.1).
- bar(a, L, h): square a x a bar along z; tags 1 = z=0 face, 2 = z=L face.
- plate_hole(W, H, t, r, h_far, h_hole): symmetric eighth of a plate with a central through hole (see docstring).
- step(path, h, tag_fn): faceted STEP (OCC import, healed) meshed whole-part; tag_fn(gmsh, surfaces) -> {tag: [surface ids]}.
Every mesh is second order (tet10) unless order=1."""
import gmsh
from mpi4py import MPI
from dolfinx.io import gmshio


def _finish(order, phys, vol_tags, gdim=3):
    for tag, surfs in phys.items(): gmsh.model.addPhysicalGroup(2, surfs, tag)
    gmsh.model.addPhysicalGroup(3, vol_tags, 100)
    gmsh.model.mesh.generate(3)
    if order == 2: gmsh.model.mesh.setOrder(2)
    msh, ct, ft = gmshio.model_to_mesh(gmsh.model, MPI.COMM_WORLD, 0, gdim=gdim)[:3]
    gmsh.finalize(); return msh, ft


def _init(name):
    if gmsh.isInitialized(): gmsh.finalize()
    gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0); gmsh.model.add(name)


def _faces_at(axis, val, tol=1e-6):
    out = []
    for dim, s in gmsh.model.getEntities(2):
        b = gmsh.model.getBoundingBox(dim, s)
        if abs(b[axis] - val) < tol and abs(b[axis + 3] - val) < tol: out.append(s)
    return out


def bar(a, L, h, order=2):
    _init("bar"); v = gmsh.model.occ.addBox(-a / 2, -a / 2, 0, a, a, L); gmsh.model.occ.synchronize()
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", h)
    return _finish(order, {1: _faces_at(2, 0.0), 2: _faces_at(2, L)}, [v])


def plate_hole(W, H, t, r, h_far, h_hole, order=2):
    """Quarter plate x in [0, W/2], y in [0, H/2], half thickness z in [0, t/2] (three symmetry planes).
    Tags: 1 = x=0 (sym ux), 2 = x=W/2 (load), 3 = y=0 (sym uy), 4 = z=0 mid-plane (sym uz)."""
    _init("plate"); occ = gmsh.model.occ
    box = occ.addBox(0, 0, 0, W / 2, H / 2, t / 2); cyl = occ.addCylinder(0, 0, -1, 0, 0, t + 2, r)
    vol, _ = occ.cut([(3, box)], [(3, cyl)]); occ.synchronize()
    planes = _faces_at(0, 0) + _faces_at(0, W / 2) + _faces_at(1, 0) + _faces_at(1, H / 2) + _faces_at(2, 0) + _faces_at(2, t / 2)
    hole = [s for _, s in gmsh.model.getEntities(2) if s not in planes]
    f = gmsh.model.mesh.field
    dist = f.add("Distance"); f.setNumbers(dist, "SurfacesList", hole)
    th = f.add("Threshold"); f.setNumber(th, "InField", dist); f.setNumber(th, "SizeMin", h_hole); f.setNumber(th, "SizeMax", h_far)
    f.setNumber(th, "DistMin", 0.2 * r); f.setNumber(th, "DistMax", 3 * r); f.setAsBackgroundMesh(th)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0); gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    return _finish(order, {1: _faces_at(0, 0.0), 2: _faces_at(0, W / 2), 3: _faces_at(1, 0.0), 4: _faces_at(2, 0.0)}, [v for _, v in vol])


def step(path, h, tag_fn, order=2, h_min=None):
    _init("step"); gmsh.option.setNumber("Geometry.OCCFixDegenerated", 1); gmsh.option.setNumber("Geometry.OCCSewFaces", 1)
    gmsh.model.occ.importShapes(path); gmsh.model.occ.healShapes(); gmsh.model.occ.synchronize()
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", h)
    if h_min: gmsh.option.setNumber("Mesh.CharacteristicLengthMin", h_min)
    vols = [v for _, v in gmsh.model.getEntities(3)]
    if not vols:  # faceted STEP exported as a closed shell: sew the faces into a surface loop and fill it
        surfs = [s_ for _, s_ in gmsh.model.getEntities(2)]
        loop = gmsh.model.occ.addSurfaceLoop(surfs, sewing=True); vols = [gmsh.model.occ.addVolume([loop])]
        gmsh.model.occ.synchronize()
    if not vols: raise RuntimeError(f"{path}: no solid volume after import/heal (faceted STEP not closed?)")
    return _finish(order, tag_fn(gmsh, [s for _, s in gmsh.model.getEntities(2)]), vols)


def stl(path, h, tag_fn=lambda g, surfs: {}, order=2, angle_deg=40.0):
    """Closed triangulated STL (the faceted twin of the exported STEP) -> tet10. The STL triangles are kept as the
    boundary (no reparametrisation), a volume is filled and meshed with max size h (gmsh STL->volume recipe)."""
    _init("stl"); gmsh.merge(path); gmsh.model.mesh.removeDuplicateNodes()
    surfs = [s_ for _, s_ in gmsh.model.getEntities(2)]
    loop = gmsh.model.geo.addSurfaceLoop(surfs); vol = gmsh.model.geo.addVolume([loop]); gmsh.model.geo.synchronize()
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", h)
    return _finish(order, tag_fn(gmsh, surfs), [vol])
