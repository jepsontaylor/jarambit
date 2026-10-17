"""Software controls; physical CAD/solver observations are separate committed evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ops.ci.evaluate_cad_candidate import validate_solid_artifacts, independent_runtime

class EvolveCertification(unittest.TestCase):
    def fixture(self,folder):
        for suffix,data in [('solid_mesh.npz',b'exact synthetic mesh'),
                            ('skfem_raw.json',json.dumps({'solver':{'converged':True},'solid':{'SF_solid_nodal_max':1.2,'SF_solid_nodal_avg':1.3}}).encode()),
                            ('dolfinx_raw.json',json.dumps({'SF_nodal_max':1.201,'SF_nodal_avg':1.301}).encode())]:
            (folder/f'control_{suffix}').write_bytes(data)
        record={'stored_solid':{'SF_skfem_nodal_max':1.2,'SF_skfem_nodal_avg':1.3,'SF_nodal_max':1.201,'SF_nodal_avg':1.301},
                'dolfinx_cross_check':{'SF_nodal_max':1.201,'SF_nodal_avg':1.301}}
        for suffix,key in [('solid_mesh.npz','mesh_sha256'),('skfem_raw.json','skfem_raw_sha256'),('dolfinx_raw.json','dolfinx_raw_sha256')]:
            record[key]=hashlib.sha256((folder/f'control_{suffix}').read_bytes()).hexdigest()
        return record

    def test_raw_observations_are_read_in_addition_to_their_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);good=self.fixture(folder);self.assertTrue(validate_solid_artifacts(good,folder,'control'))
            for field in ['SF_skfem_nodal_max','SF_nodal_max']:
                fake=copy.deepcopy(good);fake['stored_solid'][field]=9.0
                self.assertFalse(validate_solid_artifacts(fake,folder,'control'))
            (folder/'control_solid_mesh.npz').write_bytes(b'changed mesh')
            self.assertFalse(validate_solid_artifacts(good,folder,'control'))

    def test_nonconverged_primary_never_certifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);good=self.fixture(folder)
            path=folder/'control_skfem_raw.json';raw=json.loads(path.read_text());raw['solver']['converged']=False;path.write_text(json.dumps(raw))
            good['skfem_raw_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertFalse(validate_solid_artifacts(good,folder,'control'))

    def test_unavailable_independent_runtime_is_an_error(self):
        with patch('ops.ci.evaluate_cad_candidate.subprocess.check_output',side_effect=[json.dumps({'site_packages':'/site'}),FileNotFoundError('docker')]):
            with self.assertRaisesRegex(RuntimeError,'unverified'):
                independent_runtime()

    def test_refinement_preserves_the_actual_thin_cad_skin(self):
        import numpy as np
        from fem_solid.export_surface import load_surface,refine
        surface={'schema':'jarambit.export_surface.v1','verts':[[0,0,.06],[1,0,.10],[0,1,.20]],'tris':[[0,1,2]]}
        xy,tris,heights=load_surface(surface)
        points,triangles,cut,fine=refine(xy,tris,np.array([True,True,False]),heights)
        np.testing.assert_array_equal(fine[:3],[.12,.20,.40])
        np.testing.assert_allclose(fine[3:],[.16,.30,.26],rtol=0,atol=1e-15)
        self.assertEqual(len(triangles),4)
        bad=copy.deepcopy(surface);bad['verts'][0][2]=-0.06
        with self.assertRaises(ValueError):load_surface(bad)

    def test_requirement_and_bound_snapshot_is_unchanged(self):
        import ast,re
        root=Path(__file__).resolve().parents[3]
        proof=json.loads((root/'evidence/evolve_certifiable/unchanged_limits.json').read_text())
        for name,sha in proof['unchanged_files'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),sha,name)
        for name,item in proof['existing_public_constants_unchanged'].items():
            values=dict(re.findall(r'pub const\s+(\w+)\s*:[^=]+?=\s*([^;]+);',(root/name).read_text()))
            for key,value in item['values'].items():self.assertEqual(values[key],value,f'{name}:{key}')
        tree=ast.parse((root/'ops/ci/evaluate_cad_candidate.py').read_text())
        for name,sha in proof['unchanged_cad_gate_blocks'].items():
            if name=='compute_weighted_cad_score':node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            else:node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
            self.assertEqual(hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest(),sha,name)
