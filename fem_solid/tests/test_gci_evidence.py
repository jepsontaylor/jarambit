"""T01 reporter/inventory/history controls. Raw historical bytes are never qualified or changed."""
from dataclasses import asdict, replace
import hashlib
import importlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import sys
import types
import unittest
from fem_solid.gci import compute_gci, FitStatus
from fem_solid.gci_report import build_report, ExpectedRecord, Record, reclassify_history, sf_band
from fem_solid.tests.test_gci import analytic, levels

ROOT = Path(__file__).resolve().parents[2]


def fixture(identifier='d1', error=None):
    estimate = analytic()
    if error is not None: estimate = replace(estimate, gci_fine=error)
    return Record(identifier, estimate, 2.0), ExpectedRecord(identifier, levels()[0].observable)


class GCIEvidence(unittest.TestCase):
    def positive(self):
        record, expected = fixture()
        report = build_report([record], [expected])
        self.assertTrue(report['ordinary_gci_supported'])
        self.assertEqual(report['numerical_verification'], 'not_established')
        self.assertEqual(report['physical_validation'], 'not_performed')
        return record, expected

    def test_T01_12_threshold_edge(self):
        for value in (math.nextafter(.03, 0), .03):
            record, expected = fixture(error=value)
            self.assertTrue(build_report([record], [expected])['ordinary_gci_supported'])
        for value in (math.nextafter(.03, 1), -.5, math.nan, math.inf, -math.inf, True):
            record, expected = fixture(error=value)
            self.assertFalse(build_report([record], [expected])['ordinary_gci_supported'])
        self.assertEqual(f'{math.nextafter(.03, 1)*100:.2f}', '3.00')
        record, expected = self.positive()
        for estimate in (replace(record.estimate, p=-1), replace(record.estimate, p=math.inf),
                         replace(record.estimate, method_id='absolute_error.v1'),
                         replace(record.estimate, fit_status=FitStatus.OSCILLATORY, monotone=False),
                         compute_gci(100.5, 102, 108, 2)):
            self.assertFalse(build_report([replace(record, estimate=estimate)], [expected])['ordinary_gci_supported'])

    def test_T01_13_negative_error_band(self):
        record, expected = self.positive()
        band = sf_band(2.0, record.estimate.gci_fine)
        self.assertLess(band['lo'], 2); self.assertGreater(band['hi'], 2)
        self.assertFalse(compute_gci(100.5, 102, 108, 2, -1.25).admitted)
        for value in (-.01, -.5, 1, 2, math.nan, math.inf, True):
            with self.assertRaises((ValueError, OverflowError)): sf_band(2, value)
            self.assertFalse(build_report([replace(record, estimate=replace(record.estimate, gci_fine=value))], [expected])['ordinary_gci_supported'])
        for base in (0, -1, math.nan, math.inf, True, '2'):
            self.assertFalse(build_report([replace(record, sf_base=base)], [expected])['ordinary_gci_supported'])

    def test_T01_14_inventory_empty(self):
        one, a = self.positive(); two, b = fixture('d2')
        self.assertTrue(build_report([one, two], [a, b])['ordinary_gci_supported'])
        for records, expected in [([], []), ([], [a]), ([one], [a, b]), ([one, one], [a]),
                                  ([one, two], [a]), ([two], [a]), ([one], [a, a]),
                                  ([one, replace(two, estimate=replace(two.estimate, gci_fine=-.5))], [a, b])]:
            self.assertFalse(build_report(records, expected)['ordinary_gci_supported'])
        wrong = replace(a, observable=replace(a.observable, region='wrong-region'))
        self.assertFalse(build_report([one], [wrong])['ordinary_gci_supported'])

    def test_history_preserved_and_oscillatory_records_reclassified(self):
        inventory = json.loads((ROOT/'assurance/numerical/gci_inventory.json').read_text())
        pinned = inventory['raw_history_sha256']
        self.assertEqual(len(pinned), 6)
        for path, checksum in pinned.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), checksum)
        paths = [ROOT/p for p in pinned if p.endswith('_gci.json')]
        report = reclassify_history(paths)
        self.assertEqual(len(report['rows']), 5); self.assertFalse(report['ordinary_gci_supported'])
        rows = {r['id']: r for r in report['rows']}
        target = rows['w271b_11772']
        self.assertEqual(target['raw_sha256'], 'bb306086ed3f7301b61cceb96050f788b93fa93d082db87f70e1402eefd04140')
        field = target['observables']['vm_nodal_max_MPa']
        self.assertEqual(field['reason'], 'oscillatory_legacy_record')
        self.assertEqual(field['legacy_raw']['gci_fine'], .004841252613419533)
        avg = rows['g3_tip+00_t60_tt0']['observables']['vm_nodal_avg_MPa']
        self.assertEqual(avg['reason'], 'oscillatory_legacy_record')
        self.assertEqual(avg['legacy_raw']['gci_fine'], .009813947351058897)
        self.assertTrue(all(r['physical_design_verdict'] is None for r in report['rows']))
        for path, checksum in pinned.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), checksum)

    def test_typed_report_ids_have_structured_unicode_refusal(self):
        surrogate = json.loads('"\\ud800"')
        for side in ('record', 'expected'):
            with self.subTest(side=side):
                record, expected = fixture('设计-é')
                positive = build_report([record], [expected])
                self.assertEqual(positive['status'], 'PASS')
                self.assertTrue(positive['ordinary_gci_supported'])
                json.dumps(positive, allow_nan=False, ensure_ascii=False).encode('utf-8')
                if side == 'record': record = replace(record, id=surrogate)
                else: expected = replace(expected, id=surrogate)
                refused = build_report([record], [expected])
                self.assertEqual(refused['status'], 'UNVERIFIED')
                self.assertFalse(refused['ordinary_gci_supported'])
                self.assertEqual(refused['rows'], [])
                self.assertEqual(refused['reasons'], ['invalid_unicode_identity'])
                self.assertEqual(refused['numerical_verification'], 'not_established')
                self.assertEqual(refused['physical_validation'], 'not_performed')
                serialized = json.dumps(refused, allow_nan=False, ensure_ascii=False)
                serialized.encode('utf-8'); self.assertNotIn(surrogate, serialized)

    def test_historical_shape_refusals_preserve_complete_cli_batches(self):
        pinned = json.loads((ROOT/'assurance/numerical/gci_inventory.json').read_text())['raw_history_sha256']
        valid = [ROOT/p for p in pinned if p.endswith('_gci.json')]
        self.assertEqual(len(valid), 5)
        positive = reclassify_history(valid)
        self.assertEqual(len(positive['rows']), 5)
        self.assertFalse(positive['ordinary_gci_supported'])
        self.assertTrue(all('observables' in row and 'reason' not in row for row in positive['rows']))
        for row, path in zip(positive['rows'], valid):
            self.assertEqual(row['source'], str(path))
            self.assertEqual(row['raw_sha256'], pinned[path.relative_to(ROOT).as_posix()])
            self.assertIsNone(row['physical_design_verdict'])
        cases = []
        for name in ('vm_nodal_max_MPa', 'vm_nodal_avg_MPa'):
            for kind, value in (('array', []), ('scalar', 1.0), ('null', None), ('missing', None)):
                old = {'design': 'malformed-history', 'vm_nodal_max_MPa': {}, 'vm_nodal_avg_MPa': {}}
                if kind == 'missing': del old[name]
                else: old[name] = value
                reason = 'missing_historical_observable' if kind == 'missing' else 'invalid_historical_observables'
                cases.append((name+'-'+kind, old, reason))
        cases += [('root-array', [], 'invalid_historical_root'),
                  ('root-scalar', 1.0, 'invalid_historical_root'),
                  ('root-null', None, 'invalid_historical_root')]
        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory)/'malformed-history.json'
            for name, old, reason in cases:
                raw = (json.dumps(old, allow_nan=False)+'\n').encode(); malformed.write_bytes(raw)
                for position in (0, 3, 5):
                    with self.subTest(shape=name, position=position):
                        paths = list(valid); paths.insert(position, malformed)
                        report = reclassify_history(paths)
                        self.assertEqual(len(report['rows']), 6)
                        self.assertFalse(report['ordinary_gci_supported'])
                        self.assertIsNone(report['physical_design_verdict'])
                        bad = report['rows'][position]
                        self.assertEqual(bad['status'], 'UNVERIFIED')
                        self.assertEqual(bad['reason'], 'invalid_historical_record:'+reason)
                        self.assertEqual(bad['raw_sha256'], hashlib.sha256(raw).hexdigest())
                        self.assertEqual(bad['source'], str(malformed))
                        self.assertNotIn('observables', bad)
                        self.assertIsNone(bad['physical_design_verdict'])
                        self.assertEqual([row for i, row in enumerate(report['rows']) if i != position], positive['rows'])
                        argv = [sys.executable, str(ROOT/'fem_solid/gci_report.py'), '--historical', *map(str, paths)]
                        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=10)
                        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                        self.assertNotIn('Traceback', result.stderr)
                        self.assertEqual(json.loads(result.stdout), report)
                        json.dumps(report, allow_nan=False, ensure_ascii=False).encode('utf-8')
                        self.assertEqual(malformed.read_bytes(), raw)
        for path, checksum in pinned.items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), checksum)
    def test_import_has_no_generated_doc_writes(self):
        path = ROOT/'docs/calibration/solid_gci.md'; before = path.read_bytes()
        result = subprocess.run([sys.executable, '-c', 'import fem_solid.gci_report'], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(result.stdout, '')
        self.assertEqual(path.read_bytes(), before)

    def test_cli_uses_explicit_nonempty_inventory_and_typed_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = json.loads((ROOT/'assurance/numerical/gci_inventory.json').read_text())
            policy['expected_designs'] = ['d1']
            inventory = root/'inventory.json'; inventory.write_text(json.dumps(policy))
            record = root/'record.json'
            data = {'schema': 2, 'id': 'd1', 'values': [100.5, 102, 108], 'r': 2, 'fs': 1.25,
                    'levels': [asdict(x) for x in levels()], 'sf_base': 2}
            record.write_text(json.dumps(data))
            argv = [sys.executable, str(ROOT/'fem_solid/gci_report.py'), '--records', str(record), '--inventory', str(inventory)]
            valid = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            self.assertEqual(valid.returncode, 0, valid.stdout+valid.stderr)
            self.assertEqual(json.loads(valid.stdout)['physical_validation'], 'not_performed')
            data['values'] = [10, 12, 13]; record.write_text(json.dumps(data))
            invalid = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            self.assertEqual(invalid.returncode, 1); self.assertFalse(json.loads(invalid.stdout)['ordinary_gci_supported'])
            policy['expected_designs'] = []; inventory.write_text(json.dumps(policy))
            invalid = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            self.assertEqual(invalid.returncode, 1)

    def test_report_guard_mutants_are_killed(self):
        import fem_solid.gci_report as module
        source = Path(module.__file__).read_text()
        mutations = [
            ('bare_threshold', '    for record in records:\n',
             "    for record in records:\n        if record.estimate.gci_fine <= THRESHOLD: return {'ordinary_gci_supported': True}\n"),
            ('empty', 'and bool(expected)', ''),
        ]
        for name, before, after in mutations:
            self.assertEqual(source.count(before), 1)
            mutant = types.ModuleType('s02_report_mutant_'+name); mutant.__file__ = module.__file__
            sys.modules[mutant.__name__] = mutant
            try:
                exec(source.replace(before, after), vars(mutant))
                if name == 'empty':
                    self.assertFalse(build_report([], [])['ordinary_gci_supported'])
                    with self.assertRaises(AssertionError):
                        self.assertFalse(mutant.build_report([], [])['ordinary_gci_supported'])
                else:
                    estimate = replace(analytic(), fit_status=FitStatus.OSCILLATORY, monotone=False, p=None, gci_fine=.01875)
                    record, expected = Record('d1', estimate, 2), ExpectedRecord('d1', levels()[0].observable)
                    self.assertFalse(build_report([record], [expected])['ordinary_gci_supported'])
                    forged = mutant.Record('d1', estimate, 2); wanted = mutant.ExpectedRecord('d1', levels()[0].observable)
                    with self.assertRaises(AssertionError):
                        self.assertFalse(mutant.build_report([forged], [wanted])['ordinary_gci_supported'])
            finally: del sys.modules[mutant.__name__]


if __name__ == '__main__':
    unittest.main()
