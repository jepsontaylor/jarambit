"""Independent inspection of the actual genome-generated STEP, including both analytic bore rolls."""
from __future__ import annotations
from pathlib import Path


def inspect_step(path: Path) -> dict:
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Torus
    reader=STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone or reader.NbRootsForTransfer()!=1:
        raise ValueError('exported STEP has no unique transferable CAD root')
    reader.TransferRoots();shape=reader.OneShape()
    if shape.IsNull():raise ValueError('exported STEP is empty')
    valid=bool(BRepCheck_Analyzer(shape).IsValid())
    solids=0;explorer=TopExp_Explorer(shape,TopAbs_SOLID)
    while explorer.More():solids+=1;explorer.Next()
    faces=[];explorer=TopExp_Explorer(shape,TopAbs_FACE)
    while explorer.More():
        surface=BRepAdaptor_Surface(TopoDS.Face_s(explorer.Current()))
        if surface.GetType()==GeomAbs_Torus:
            torus=surface.Torus();axis=torus.Axis();position=torus.Location()
            faces.append({'minor_radius_mm':float(torus.MinorRadius()),
                          'major_radius_mm':float(torus.MajorRadius()),'center_z_mm':float(position.Z()),
                          'axis_z':float(axis.Direction().Z())})
        explorer.Next()
    both_faces=bool(any(f['center_z_mm']>0 for f in faces) and any(f['center_z_mm']<0 for f in faces))
    radius=min((f['minor_radius_mm'] for f in faces),default=None)
    return {'reader':'OpenCascade STEP reader + BRepCheck_Analyzer','valid':valid,'solids':solids,
            'bore_rolls_on_both_faces':both_faces,'bore_edge_radius_mm':radius,'toroidal_faces':faces}
