"""67-control T02 runner, activated only by an independently approved runtime D.

The trusted launcher calls configure_runtime before unittest discovery. Missing
admission is an error, never a skip or synthetic success. This file does not
build a resolver, install dependencies, generate public docs or derive goldens.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from assurance.reporting import blocks, claims
from assurance.testing.contracts import raw_hash, scientific_hash, validate_case, validate_receipt
from assurance.testing.receipt import publish_receipt
from ops.ci import check_claims, rs_verdicts

_RUNTIME = None
_CORPUS = None
RUNTIME_FIELDS = {'schema', 'binding_stage', 'input_sha256', 'registry_sha256', 'policy_sha256', 'resolver_binary_sha256', 'resolver_source_sha256'}
ROW_KEYS = {'caller_admission_utf8', 'approved_caller_sha256', 'approved_registration', 'request_path', 'authority_path', 'document_path', 'expected_report_path', 'expected_report_sha256', 'expected_input_sha256', 'output_dir'}
ROW_OPTIONAL = {'cache_path', 'cache_sha256', 'invocation', 'mutated_output_path', 'mutated_output_sha256'}


def corpus():
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = claims.decode(claims.read_bounded(ROOT/'assurance/registry/t02_fixtures.json', corpus=True), corpus=True)
    return copy.deepcopy(_CORPUS)


def configure_runtime(raw, approved_manifest_sha256):
    """Only an independent trusted launcher supplies the expected admission hash."""
    global _RUNTIME
    claims.require(type(raw) is bytes and raw_hash(raw) == approved_manifest_sha256, 'test_runtime_approval_bytes_mismatch')
    table = claims.closed(claims.decode(raw, corpus=True), {'schema', 'source_head', 'fixture_raw_sha256', 'rows', 'catalog', 'policy', 'output_dir'}, 'test_runtime_wire')
    claims.require(type(table['schema']) is int and table['schema'] == 1, 'test_runtime_schema')
    claims.require(raw_hash((ROOT/'assurance/registry/t02_fixtures.json').read_bytes()) == table['fixture_raw_sha256'], 'fixed_fixture_changed')
    fixed = corpus()
    ids = {r['id'] for r in fixed['original_controls']} | {r['fixed_metadata']['id'] for r in fixed['supplemental_controls']} | {r['fixed_metadata']['id'] for r in fixed['subject_auxiliary_controls']}
    claims.require(type(table['rows']) is dict and set(table['rows']) == ids and len(ids) == 67, 'test_runtime_control_inventory')
    claims.require(type(table['catalog']) is list and len(table['catalog']) == 12, 't02_catalog_required')
    for case in table['catalog']:validate_case(case)
    claims.require(scientific_hash(table['catalog']) == table['policy']['catalog_sha256'], 'test_runtime_catalog_identity')
    claims.require({c['id'] for c in table['catalog']} == {r['group'] for r in fixed['original_controls']}, 't02_group_inventory')
    for name, row in table['rows'].items():
        claims.closed(row, ROW_KEYS, 'test_runtime_row', ROW_OPTIONAL)
        for key in ['request_path', 'authority_path', 'document_path', 'expected_report_path', 'output_dir']:
            claims.require(type(row[key]) is str and Path(row[key]).is_absolute() and Path(row[key]).is_relative_to(Path(table['output_dir'])), 'owned_runtime_path')
    _RUNTIME = bytes(raw)


def runtime():
    if _RUNTIME is None:
        raise RuntimeError('independent B/C/D runtime admission required; T02 not_run')
    return claims.decode(_RUNTIME, corpus=True)


def context_for(control_id):
    row = runtime()['rows'][control_id]
    caller = claims.TrustedCaller.from_approved_bytes(row['caller_admission_utf8'].encode('utf-8'), row['approved_caller_sha256'], row['approved_registration'])
    return rs_verdicts.ReportingContext(caller, row['request_path'], row['authority_path'])


def immutable(path, value):
    """Per-control raw evidence is exclusive; completion/paired receipt comes later."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if type(value) is bytes else (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n').encode()
    with path.open('xb') as f:f.write(raw); f.flush(); os.fsync(f.fileno())
    directory = os.open(path.parent, os.O_RDONLY); os.fsync(directory); os.close(directory)
    return raw_hash(raw)


def current_expected(row, fixed_report):
    raw = claims.read_bounded(row['expected_report_path'])
    claims.require(raw_hash(raw) == row['expected_report_sha256'], 'independent_oracle_bytes_changed')
    report = claims.decode(raw)
    claims.closed(report, claims.REPORT_KEYS, 'runtime_expected_report_keys')
    # Only runtime identity fields are rematerialized; all scientific/document
    # subject/metric/mass/oracle values stay exactly frozen before implementation.
    claims.require({k:v for k,v in report.items() if k not in RUNTIME_FIELDS} == {k:v for k,v in fixed_report.items() if k not in RUNTIME_FIELDS}, 'runtime_oracle_changed')
    claims.require(report['schema'] == 'jarambit.claim_report.v2' and report['binding_stage'] == 'runtime_admitted' and report['input_sha256'] == row['expected_input_sha256'], 'runtime_oracle_stage')
    return report


def direct_bridge(control_id):
    row = runtime()['rows'][control_id]; context = context_for(control_id)
    context.caller.verify_current()
    argv = [context.caller.data['binary_path'], row['request_path'], row['authority_path']]
    child = subprocess.run(argv, capture_output=True, timeout=60, check=False)
    claims.require(len(child.stdout) <= claims.LIMITS['max_bytes'] and len(child.stderr) <= claims.LIMITS['max_bytes'], 'test_output_limit')
    context.caller.verify_current()
    output = claims.decode(child.stdout)
    immutable(Path(row['output_dir'])/'bridge.stdout', child.stdout)
    immutable(Path(row['output_dir'])/'bridge.stderr', child.stderr)
    immutable(Path(row['output_dir'])/'bridge-terminal.json', {'argv':argv,'cwd':os.getcwd(),'exit':child.returncode,'stdout_sha256':raw_hash(child.stdout),'stderr_sha256':raw_hash(child.stderr),'actual_binary_sha256':context.caller.data['pin']['actual_resolver_binary_sha256']})
    return child.returncode, output


def publish_paired_group(group, row_results):
    """Called by the admitted finalizer after both test modules finish.

    Supplemental rows and the three subject auxiliaries belong in their approved
    parent bucket tables. Parent method ok never stands in for a child result.
    """
    data = runtime();case = next(c for c in data['catalog'] if c['id'] == group)
    claims.require(set(row_results) == {'positive','adverse'}, 'paired_buckets_required')
    wanted=corpus()['paired_group_subcontrols'][group]
    claims.require(all(len(row_results[b])==len(wanted[b]) and {r['id'] for r in row_results[b]}==set(wanted[b]) for b in wanted), 'exact_child_inventory_required')
    claims.require(all(type(v) is list and v and all(r['execution']=='passed' and r['comparison_passed'] is True for r in v) for v in row_results.values()), 'child_control_missing_or_failed')
    artifact = (json.dumps(row_results,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
    artifacts = {'subcontrols.json':artifact}
    receipt = {'schema':1,'case_id':group,'input_sha256':case['input_sha256'],'oracle_sha256':case['oracle_sha256'],'execution':'passed','finding':'supported_within_scope','argv':sys.argv,'exit_code':0,'timed_out':False,'complete':True,'controls':{'positive':'passed','adverse':'passed'},'artifacts':{'subcontrols.json':raw_hash(artifact)},'counts':{'expected':2,'passed':2,'failed':0,'error':0,'not_run':0},'reason':None}
    validate_receipt(receipt,case,artifacts)
    path=Path(data['output_dir'])/'receipts'/group
    immutable(path/'subcontrols.json',artifact)
    publish_receipt(path/'receipt.json',receipt,case,artifacts)
    return receipt


class ClaimIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime()  # Explicit unavailable-admission error; never skipped to PASS.

    def run_control(self, fixed):
        ident=fixed['id']; row=runtime()['rows'][ident];context=context_for(ident)
        outdir=Path(row['output_dir'])
        try:
            code, output=direct_bridge(ident)
            expected=fixed['expected_provider']
            self.assertEqual(code,expected['exit_code'])
            if expected['Resolution'] is None:
                self.assertEqual(output['kind'],'refused')
                self.assertEqual(set(output),{'schema','kind','reason'})
                self.assertEqual(output['reason'],expected['refusal_reason'])
            else:
                self.assertEqual(output['kind'],'resolved')
                self.assertEqual({k:output[k] for k in ['verdict','publication_eligible','release_authorized']},expected['Resolution'])
                if fixed['scope']['disposition']=='admitted':
                    independently_expected=current_expected(row,fixed['fixed_metadata']['literal_expected_report'])
                    actual=context.report_for('claim-a')
                    self.assertEqual(blocks.canonical_body(actual),blocks.canonical_body(independently_expected))
                    if actual['metrics']['G1']['status']=='COMPLETE':
                        reference=79/100 if actual['mass']['value_g']==84 else 33/40
                        self.assertAlmostEqual(actual['metrics']['G1']['value'],reference,delta=1e-15)
                        self.assertEqual(actual['metrics']['G1']['value'].hex(),'0x1.947ae147ae146p-1' if actual['mass']['value_g']==84 else '0x1.a666666666665p-1')
            document=claims.read_bounded(row['document_path'])
            result=check_claims.check_document(document,context)
            self.assertEqual(result.exit_code,fixed['expected_checker_exit'])
            if expected['Resolution'] is None:self.assertIsNone(result.provider)
            else:
                self.assertIsNotNone(result.provider)
                self.assertEqual({k:result.provider.output[k] for k in ['verdict','publication_eligible','release_authorized']},expected['Resolution'])
            observed={'id':ident,'execution':'passed','comparison_passed':True,'bridge_exit':code,'checker_exit':result.exit_code,'provider':output,'document_errors':result.violations,'input_sha256':row['expected_input_sha256'],'frozen_provider_oracle':expected,'exact_document_sha256':raw_hash(document),'scientific_publication':False}
            immutable(outdir/'control-comparison.json',observed)
            return observed
        except Exception as error:
            immutable(outdir/'control-failed.json',{'id':ident,'execution':'failed','error_type':type(error).__name__,'error':str(error),'scientific_publication':False})
            raise

    def group(self, group):
        rows=[r for r in corpus()['original_controls'] if r['group']==group]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(control=row['id']):self.run_control(row)

    def test_T02_01_contradictory_block(self):self.group('T02-01-contradictory_block')
    def test_T02_02_missing_reopened(self):self.group('T02-02-missing_reopened')

    def test_T02_03_wrong_candidate(self):
        self.group('T02-03-wrong_candidate')
        fixed=corpus()
        for aux in fixed['subject_auxiliary_controls']:
            meta=aux['fixed_metadata'];row=runtime()['rows'][meta['id']]
            with self.subTest(control=meta['id']):
                context=context_for(meta['id'])
                document=claims.read_bounded(row['document_path'])
                result=check_claims.check_document(document,context)
                self.assertEqual(result.exit_code,meta['expected_document_integrity_exit'])
                self.assertEqual(result.provider.output['verdict'],meta['expected_provider']['Resolution']['verdict'])
                immutable(Path(row['output_dir'])/'control-comparison.json',{'id':meta['id'],'execution':'passed','comparison_passed':True,'checker_exit':result.exit_code,'document_sha256':raw_hash(document),'provider':result.provider.output})

    def test_T02_04_requirement_content(self):self.group('T02-04-requirement_content')
    def test_T02_05_wrong_physics(self):self.group('T02-05-wrong_physics')
    def test_T02_06_revoked_review(self):self.group('T02-06-revoked_review')
    def test_T02_07_presentation_noise(self):self.group('T02-07-presentation_noise')
    def test_T02_08_nonfinite_scalar(self):self.group('T02-08-nonfinite_scalar')
    def test_T02_09_mass_scope(self):self.group('T02-09-mass_scope')
    def test_T02_10_physical_missing(self):self.group('T02-10-physical_missing')
    def test_T02_11_g1_delete(self):self.group('T02-11-g1_delete')
    def test_T02_12_truthful_negative(self):self.group('T02-12-truthful_negative')

    def test_requirement_hash_mismatch_rejects_claim(self):
        row=runtime()['rows']['same-RS-id-changed-TOML-content']
        context=context_for('same-RS-id-changed-TOML-content')
        report=context.report_for('claim-a')
        self.assertEqual(report['verdict']['missing'],['artifact_identity_mismatch'])
        self.assertFalse(report['publication_eligible'])
        self.assertEqual(check_claims.check_document(claims.read_bounded(row['document_path']),context).exit_code,1)

    def test_superseded_candidate_cannot_become_current_from_stale_heading(self):
        row=runtime()['rows']['stale-C10c-current-heading'];context=context_for('stale-C10c-current-heading')
        result=check_claims.check_document(claims.read_bounded(row['document_path']),context)
        self.assertEqual(result.exit_code,1)
        self.assertTrue(any('current candidate C10c' in e for e in result.violations))
        self.assertEqual(result.provider.output['verdict']['outcome'],'pass')

    def test_subject_guard_mutant_and_all52_sensitivity_documents(self):
        fixed=corpus();rows={r['id']:r for r in fixed['original_controls']}
        for diagnostic in fixed['subject_sensitivity_diagnostics']:
            path=diagnostic['path'];ident=Path(path).parts[-2]
            self.assertIn(ident,rows)
            context=context_for(ident);report=context.report_for('claim-a')
            old=diagnostic['document_utf8']
            # Admitted materializer preserves each diagnostic and replaces only
            # stage/root identity tokens, using independently approved metadata.
            for key in RUNTIME_FIELDS:
                oldvalue=rows[ident]['fixed_metadata']['literal_expected_report'][key]
                old=old.replace(json.dumps(key)+':'+json.dumps(oldvalue,separators=(',',':')),json.dumps(key)+':'+json.dumps(report[key],separators=(',',':')))
            result=check_claims.check_document(old,context)
            self.assertEqual(result.exit_code,1)
            if Path(path).name in {'deleted.md', 'changed.md'}:
                def ignore_subject(block,claim_id,expected):
                    actual=claims.decode(block.body.encode());want=copy.deepcopy(expected)
                    actual.pop('subject_id',None);want.pop('subject_id',None)
                    if actual!=want:raise blocks.BlockError('other body mismatch')
                with patch.object(blocks,'check_exact_block',ignore_subject):
                    self.assertEqual(check_claims.check_document(old,context).exit_code,0)
                # The original fixed adverse still fails without the mutant.
                self.assertEqual(check_claims.check_document(old,context).exit_code,1)


if __name__=='__main__':unittest.main()
