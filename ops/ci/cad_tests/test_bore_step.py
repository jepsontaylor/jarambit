"""Real STEP read-back controls derived solely from the committed genome export.
The bore-only fragments are regression fixtures, never candidate designs.
"""
import json
from pathlib import Path
import time
import unittest
from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Compound
from OCP.BRep import BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Torus
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf, gp_Vec
from ops.ci.verify_genome_export import inspect_step

class RealBoreReadback(unittest.TestCase):
    def test_translated_step_tori_keep_minor_radius_but_fail_mesh_agreement(self):
        root=Path(__file__).resolve().parents[3]
        fixture=root/'evidence/evolve_certifiable/controls/legal_genome'
        out=root/'target/bore-readback-controls'/str(time.time_ns());out.mkdir(parents=True)
        reader=STEPControl_Reader();reader.ReadFile(str(fixture/'control.step'));reader.TransferRoots()
        compound=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(compound)
        explorer=TopExp_Explorer(reader.OneShape(),TopAbs_FACE)
        while explorer.More():
            face=TopoDS.Face_s(explorer.Current())
            if BRepAdaptor_Surface(face).GetType()==GeomAbs_Torus:builder.Add(compound,face)
            explorer.Next()
        transform=gp_Trsf();transform.SetTranslation(gp_Vec(0,0,.25))
        results=[]
        for name,shape in [('original',compound),('displaced',BRepBuilderAPI_Transform(compound,transform,True).Shape())]:
            path=out/(name+'.step');writer=STEPControl_Writer();writer.Transfer(shape,STEPControl_AsIs);writer.Write(str(path))
            result=inspect_step(path,fixture/'control_surface.json');results.append(result)
            (out/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
        good,bad=results
        self.assertTrue(good['bore_geometry_matches_mesh'],good.get('bore_validation_error'))
        self.assertTrue(bad['bore_rolls_on_both_faces'])
        self.assertTrue(all(bad['full_circle_coverage'].values()))
        self.assertAlmostEqual(good['bore_edge_radius_mm'],bad['bore_edge_radius_mm'],places=9)
        self.assertFalse(bad['bore_geometry_matches_mesh'])
