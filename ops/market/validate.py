#!/usr/bin/env python3
"""Validate evidence coverage, units, comparison eligibility and frozen CAD pins."""
import csv
import hashlib
import json
import math
import pathlib
import re
import unittest
from build import DATA, MINIMUM_IN, PALETTE, ROOT, dimension, parse_facts, stats, weight


class MarketDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads((DATA/'census.json').read_text())
        cls.byid={r['id']:r for r in cls.rows}
        cls.benchmark=json.loads((DATA/'benchmark.json').read_text())

    def test_all_supplied_rows_have_exactly_one_disposition(self):
        expected=set()
        for m in json.loads((DATA/'input_manifest.json').read_text()):
            path=DATA/'raw'/m['filename']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),m['sha256'])
            with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),m['rows'])
            expected.update(f'{path.name}:{i}' for i in range(2,len(rows)+2))
        observed=[ref for r in self.rows for ref in r['input_refs'] if not ref.startswith('discovered_models.json:')]
        self.assertEqual(set(observed),expected)
        self.assertEqual(len(observed),len(expected))

    def test_units_and_fractional_lengths(self):
        for raw,expected in [('3.375"',3.375),('4-1/8"',4.125),('4-3/4"',4.75),('86.1 mm',86.1/25.4),('9.7 cm',97/25.4)]:
            self.assertAlmostEqual(dimension(raw),expected)
        self.assertEqual(parse_facts('Blade Length (inches) | 3.5')['blade_length_in'],3.5)
        self.assertAlmostEqual(weight('1.8 oz.'),51.03,places=2)
        self.assertEqual(weight('2.51 oz. (71.2 g)'),71.2)
        self.assertIsNone(weight('not published'))
        self.assertIsNone(dimension('3" - 3.49"'))

    def test_navigation_badges_cannot_override_actual_material(self):
        facts=parse_facts('AUS-8 Blade Steel category\nBlade Steel: AUS 8 Stainless Steel\nBlade Length: 3.375"\nWeight: 4.10 oz.')
        self.assertEqual(facts['blade_grade'],'AUS-8')
        self.assertEqual(facts['blade_length_in'],MINIMUM_IN)

    def test_minimum_is_inclusive_and_unknowns_do_not_become_zero(self):
        self.assertTrue(self.byid['united-cutlery-m48-steel-titan']['qualified'])
        for r in self.rows:
            if r['qualified']:self.assertGreaterEqual(r['blade_length_in'],MINIMUM_IN)
            if r['weight_g'] is not None:self.assertGreater(r['weight_g'],0)
            for f in ('blade_length_in','cutting_edge_in','weight_g','weight_with_sheath_g'):
                self.assertTrue(r[f] is None or math.isfinite(r[f]))

    def test_conflicted_lengths_and_set_weights_stay_out_of_plot(self):
        for key in ('hightron-cyroclaw','medford-burung','united-cutlery-m48-liberator-falcon','emerson-super-karambit'):
            self.assertFalse(self.byid[key]['plot_eligible'])
        self.assertIsNone(self.byid['black-legion-set-karambit']['weight_g'])
        self.assertFalse(self.byid['schwartz-spartan']['plot_eligible'])
        self.assertFalse(self.byid['terry-renner-playmates-tactical-hawkbill-karambit']['plot_eligible'])
        for r in self.rows:
            if 'knifecountryusa.com' in r['source_url']:
                self.assertFalse(r['plot_eligible'])

    def test_titanium_coatings_do_not_change_blade_material(self):
        self.assertEqual(self.byid['lotar-kharma-gen-3x']['material_family'],'Stainless steel')
        self.assertEqual(self.byid['hightron-cyroclaw']['material_family'],'Stainless steel')
        self.assertEqual(self.byid['mick-strider-custom']['material_family'],'Titanium / Ti composite')
        self.assertEqual(self.byid['cold-steel-fgx-karambit']['material_family'],'Polymer / nonmetal')

    def test_summary_denominators_and_weight_scope_reconcile(self):
        summary=stats(self.rows,self.benchmark)
        self.assertEqual(summary,json.loads((DATA/'summary.json').read_text()))
        weighted=[r for r in self.rows if r['plot_eligible']]
        self.assertEqual(len(weighted),sum(summary['material_weight_counts'].values()))
        self.assertEqual(summary['plotted_entries']+summary['qualified_missing_comparable_weight'],summary['qualified_entries'])
        for r in weighted:
            self.assertIn(r['material_family'],PALETTE)
            self.assertEqual(r['weight_verification'],'current_source')
            self.assertIn(r['weight_basis'],('explicit_knife_only','published_knife_spec'))

    def test_lighter_comparator_is_disclosed(self):
        row=self.byid['hoback-talim__titanium-alloy-unspecified']
        self.assertTrue(row['plot_eligible'])
        self.assertEqual(row['weight_g'],51.03)
        self.assertLess(row['weight_g'],self.benchmark['primary']['mass_g'])

    def test_shared_category_url_never_merges_distinct_products(self):
        garra=self.byid['blackhawk-garra']
        stinger=self.byid['united-cutlery-cia-stinger-iii']
        self.assertEqual(garra['model'],'BLACKHAWK Garra')
        self.assertEqual(stinger['model'],'United Cutlery CIA Stinger III')
        self.assertEqual(stinger['weight_g'],75.98)
        self.assertEqual(garra['weight_g'],133.24)
        self.assertTrue(stinger['plot_eligible'])

    def test_curated_decisions_target_existing_records(self):
        self.assertFalse(set(json.loads((DATA/'curation.json').read_text()))-set(self.byid))

    def test_csv_matches_json(self):
        with (DATA/'census.csv').open(newline='') as stream:rows=list(csv.DictReader(stream))
        self.assertEqual(len(rows),len(self.rows))
        for j,c in zip(self.rows,rows):
            self.assertEqual(j['id'],c['id'])
            self.assertEqual(c['weight_g'],'') if j['weight_g'] is None else self.assertEqual(float(c['weight_g']),j['weight_g'])

    def test_benchmark_matches_repository_evidence_when_available(self):
        bm=self.benchmark['primary']
        path=ROOT/bm['mass_source']
        if path.exists():
            mass=json.loads(path.read_text())
            self.assertEqual(mass['mass_g_Gr5'],bm['mass_g'])
        path=ROOT/bm['length_source']
        if path.exists():
            lengths=json.loads(path.read_text())['blade_length_mm']
            self.assertEqual(lengths['tip_to_heel_straight_mm'],bm['blade_length_mm'])
            self.assertEqual(lengths['horizontal_projection_mm'],bm['horizontal_projection_mm'])
        self.assertAlmostEqual(bm['blade_length_mm']/25.4,bm['blade_length_in'],places=10)


if __name__=='__main__':unittest.main(verbosity=2)
