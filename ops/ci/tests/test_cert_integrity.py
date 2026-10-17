import copy
import unittest
from ops.ci.evaluate_cad_candidate import solid_evidence_matches, independent_agreement

class CertificateIntegrity(unittest.TestCase):
    def record(self):
        return {'certificate_identity':'key','genome_sha256':'genome','d1_sha256':'d1','mesh_sha256':'a'*64,
                'stored_solid':{'NL':4,'NSUB':1,'SF_skfem_nodal_max':1.6,'SF_skfem_nodal_avg':1.7},
                'dolfinx_cross_check':{'status':'verified','primary_solver':'skfem_p2',
                    'independent_solver':'dolfinx_v0.9.0','mesh_sha256':'a'*64,
                    'SF_nodal_max':1.61,'SF_nodal_avg':1.71}}
    def test_only_content_bound_independent_evidence_is_reused(self):
        good=self.record()
        self.assertTrue(solid_evidence_matches(good,'genome','d1','key'))
        for field in ['certificate_identity','genome_sha256','d1_sha256']:
            stale=copy.deepcopy(good);stale[field]='old'
            self.assertFalse(solid_evidence_matches(stale,'genome','d1','key'),field)
        for field in ['status','primary_solver','independent_solver','mesh_sha256']:
            missing=copy.deepcopy(good);missing['dolfinx_cross_check'].pop(field)
            self.assertFalse(solid_evidence_matches(missing,'genome','d1','key'),field)
        fake=copy.deepcopy(good);fake['dolfinx_cross_check']={'within_2pct':True,'rel_err_nodal_max':0.0}
        self.assertFalse(solid_evidence_matches(fake,'genome','d1','key'))
    def test_coarse_and_nonfinite_observations_cannot_be_reused(self):
        for value in [None,True,float('nan'),float('inf')]:
            bad=self.record();bad['stored_solid']['SF_skfem_nodal_max']=value
            self.assertFalse(solid_evidence_matches(bad,'genome','d1','key'))
        bad=self.record();bad['stored_solid']['NSUB']=0
        self.assertFalse(solid_evidence_matches(bad,'genome','d1','key'))

    def test_agreement_is_derived_not_trusted_from_cached_boolean(self):
        bad=self.record();bad['dolfinx_cross_check'].update(SF_nodal_max=2.0,within_2pct=True,rel_err_nodal_max=0.0)
        self.assertFalse(independent_agreement(bad)['within_2pct'])
        self.assertAlmostEqual(independent_agreement(bad)['rel_err_nodal_max'],0.2)

    def test_python_battery_never_reuses_a_catalog_label(self):
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from ops.ci.cad_battery import evaluate_genome_pipeline
        with tempfile.TemporaryDirectory() as tmp, \
             patch('ops.ci.evaluate_cad_candidate.evaluate_candidate', return_value={'certificate_identity':'fresh-hash'}) as evaluate, \
             patch('ops.ci.cad_battery.evaluated_genome_spec', return_value={'genome':'edited.csv'}) as spec, \
             patch('ops.ci.cad_battery.build_subject', return_value={'subject':'w283_p14_c01'}) as build:
            out = Path(tmp)
            (out/'w283_p14_c01.json').write_text('{"all_hard":true,"certificate_identity":"stale"}')
            result=evaluate_genome_pipeline('w283_p14_c01=edited.csv','a'*40,{},out)
            self.assertEqual(result['certificate_identity'],'fresh-hash')
            self.assertEqual(evaluate.call_args.args[1].name,'edited.csv')
            self.assertEqual(build.call_args.kwargs['custom_spec'],{'genome':'edited.csv'})

    def test_corrected_documents_and_independent_raw_artifacts(self):
        import hashlib, json
        from pathlib import Path
        from ops.ci.gen_cert_integrity import render
        root=Path(__file__).resolve().parents[3]
        path=root/'docs/ENGINEERING_GATES_AND_EVOLUTION.md'
        self.assertEqual(render(path.read_text()),path.read_text())
        for sid in ['w283_p14_c01','w283_p10_c02']:
            folder=root/'evidence/cert_integrity/recertified'/sid
            solid=json.loads((folder/f'{sid}_solid_tip.json').read_text())
            for suffix,key in [('solid_mesh.npz','mesh_sha256'),('skfem_raw.json','skfem_raw_sha256'),('dolfinx_raw.json','dolfinx_raw_sha256')]:
                self.assertEqual(hashlib.sha256((folder/f'{sid}_{suffix}').read_bytes()).hexdigest(),solid[key])
            d1=folder/f'{sid}_D1.json';genome=folder/f'{sid}_genome.csv'
            self.assertTrue(solid_evidence_matches(solid,hashlib.sha256(genome.read_bytes()).hexdigest(),hashlib.sha256(d1.read_bytes()).hexdigest(),solid['certificate_identity']))
            rs=json.loads((folder/f'{sid}_rs.json').read_text())
            self.assertFalse(rs['all_hard'])
            self.assertEqual(rs['export_measurements']['bore_edge_radius_mm'],0.0)
            self.assertFalse(rs['export_measurements']['point']['monotonic'])
