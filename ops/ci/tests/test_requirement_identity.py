"""The 17 fixed paired caller/authority/wire controls, using the actual provider."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from assurance.reporting import blocks, claims
from assurance.testing.contracts import ContractError
from ops.ci import check_claims, rs_verdicts
from ops.ci.tests import test_claim_integrity as runner


class RequirementIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):runner.runtime()

    def run_control(self, fixed):
        meta=fixed['fixed_metadata'];ident=meta['id'];row=runner.runtime()['rows'][ident]
        context=runner.context_for(ident);expected=meta['independent_oracle']
        outdir=Path(row['output_dir']);observed=None;refusal=None
        try:
            if meta['polarity']=='positive':
                report=context.report_for('claim-a')
                result=context.last_resolution
                self.assertEqual({k:result.output[k] for k in ['verdict','publication_eligible','release_authorized']},expected['Resolution'])
                self.assertEqual(result.input_sha256,row['expected_input_sha256'])
                value=claims.decode(result.output_raw)
                _,_,binding,_=claims.admission_binding(claims.read_bounded(context.request_path),claims.read_bounded(context.authority_path),context.caller)
                self.assertEqual(claims.validate_output(value,binding,'claim-a'),value)
                if meta['family']=='cache':
                    record=claims.cache_record(result,report)
                    self.assertEqual(claims.checked_cache(record,result.input_sha256,report,result.output['input_binding']),report)
                observed={'provider':result.output,'report':report,'input_sha256':result.input_sha256}
            else:
                family=meta['family']
                if family=='binary':
                    # An attempted user-selected binary/authority is rejected by
                    # the real guarded CLI, before it may choose a provider.
                    args=row.get('invocation',['--resolver-binary',str(context.caller.data['binary_path'])])
                    with self.assertRaises(SystemExit) as raised:check_claims.main(args,context=context)
                    self.assertEqual(raised.exception.code,2)
                    self.assertIsNone(context.last_resolution)
                    refusal='untrusted_binary_or_cli_override'
                elif family=='output_wire':
                    context.report_for('claim-a');real=context.last_resolution
                    _,_,binding,_=claims.admission_binding(claims.read_bounded(context.request_path),claims.read_bounded(context.authority_path),context.caller)
                    mutated=copy.deepcopy(real.output);mutated['unexpected_provider_key']=True
                    with self.assertRaises(claims.Refusal) as raised:claims.validate_output(mutated,binding,'claim-a')
                    refusal=raised.exception.reason
                    self.assertEqual(refusal,'unknown_provider_output_field')
                    observed={'actual_valid_provider':real.output,'mutated_transport':mutated,'reusable_mutated_output':False}
                elif family=='cache':
                    report=context.report_for('claim-a');real=context.last_resolution
                    self.assertIn('cache_path',row)
                    raw=claims.read_bounded(row['cache_path'])
                    self.assertEqual(claims.raw_hash(raw),row['cache_sha256'])
                    old=claims.decode(raw)
                    with self.assertRaises(claims.Refusal) as raised:claims.checked_cache(old,real.input_sha256,report,real.output['input_binding'])
                    self.assertEqual(raised.exception.reason,'cache_input_identity_mismatch')
                    refusal=raised.exception.reason
                    observed={'new_actual_provider':real.output,'old_cache_input':old['input_sha256'],'new_input':real.input_sha256,'cache_reusable':False}
                else:
                    with self.assertRaises((claims.Refusal,ContractError)) as raised:context.report_for('claim-a')
                    refusal=str(raised.exception)
                    self.assertEqual(refusal,expected['refusal_reason'])
                    self.assertIsNone(context.last_resolution)
                self.assertEqual(expected['caller_or_bridge_exit'],2)
            record={'id':ident,'execution':'passed','comparison_passed':True,'observed':observed,'refusal':refusal,'frozen_oracle':expected,'reuse_claim':False,'new_scientific_publication':False}
            runner.immutable(outdir/'control-comparison.json',record)
            return record
        except Exception as error:
            runner.immutable(outdir/'control-failed.json',{'id':ident,'execution':'failed','error_type':type(error).__name__,'error':str(error)})
            raise

    def family(self,name):
        for row in runner.corpus()['supplemental_controls']:
            if row['fixed_metadata']['family']==name:
                with self.subTest(control=row['fixed_metadata']['id']):self.run_control(row)

    def test_authority(self):self.family('authority')
    def test_policy(self):self.family('policy')
    def test_binary(self):self.family('binary')
    def test_cache(self):self.family('cache')
    def test_request_wire(self):self.family('request_wire')
    def test_authority_wire(self):self.family('authority_wire')
    def test_output_wire(self):self.family('output_wire')

    def test_cache_rejects_actual_truthful_fail_and_incomplete(self):
        for ident in ['faithful-canonical-FAIL','truthful-reopened-INCOMPLETE']:
            context=runner.context_for(ident);report=context.report_for('claim-a')
            with self.assertRaises(claims.Refusal):claims.cache_record(context.last_resolution,report)

    def test_metric_adapter_uses_real_G1_without_display_rounding(self):
        for ident,bits in [('finite-typed-SF-and-zero-fractions','0x1.a666666666665p-1'),('84g-soft-target-exceeded-not-hard-failure','0x1.947ae147ae146p-1')]:
            context=runner.context_for(ident);report=context.report_for('claim-a')
            self.assertEqual(report['metrics']['G1']['value'].hex(),bits)
        for key in ['solid_tip_sf_nodal_max','spg','aes_score','mass_g','seq_ratio']:
            context=runner.context_for('delete-G1-'+key);report=context.report_for('claim-a')
            self.assertIsNone(report['metrics']['G1']['value'])
            self.assertEqual(report['metrics']['G1']['missing'],[key])
            self.assertTrue(context.metric_diagnostics)
            self.assertEqual(report['verdict']['outcome'],'pass')

    def test_actual_context_generator_adapter_and_legacy_negative(self):
        context=runner.context_for('faithful-negative-and-historical-adapter')
        report=context.report_for('claim-a')
        block=rs_verdicts.claim_block(context)
        self.assertEqual(blocks.parse_blocks(block)[0].body,blocks.canonical_body(report))
        old=runner.corpus()['original_controls']
        row=next(r for r in old if r['id']=='faithful-negative-and-historical-adapter')
        history=row['fixed_metadata']['context']['historical_D1']
        rec={'mass_g':77.0,'seq_ratio':history['seq_ratio'],'d1':{'strict_ok':True},'twist_floor_ok':False,'w20_hard_pass':False,'promote_eligible':False}
        legacy=rs_verdicts.verdict(rec,rs_verdicts.load_rs())
        self.assertIn('promotion FAIL',legacy);self.assertIn('not promoted',legacy)
        self.assertEqual(report['verdict']['outcome'],'fail')
        self.assertFalse(report['publication_eligible']);self.assertFalse(report['release_authorized'])

    def test_policy_and_subject_guard_mutants_keep_independent_oracle(self):
        # The candidate input mutant is opposed to the unchanged checker1 oracle.
        ident='borrow-B-heading-with-A-evidence';row=runner.runtime()['rows'][ident]
        context=runner.context_for(ident);document=claims.read_bounded(row['document_path'])
        self.assertEqual(check_claims.check_document(document,context).exit_code,1)
        # A primitive guard mutant is a diagnostic; it does not modify fixtures
        # or qualify a fake output. It must leave unrelated valid positives.
        context=runner.context_for('exact-subject-current-role')
        report=context.report_for('claim-a')
        good=blocks.write_block('claim-a',report)
        self.assertEqual(check_claims.check_document(good,context).exit_code,0)
        changed=copy.deepcopy(report);changed['subject_id']='fixture-B'
        bad=blocks.write_block('claim-a',changed)
        self.assertEqual(check_claims.check_document(bad,context).exit_code,1)
        with patch.object(blocks,'check_exact_block',lambda *a:None):
            self.assertEqual(check_claims.check_document(bad,context).exit_code,0)
        self.assertEqual(check_claims.check_document(bad,context).exit_code,1)


if __name__=='__main__':unittest.main()
