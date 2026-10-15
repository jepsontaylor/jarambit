"""T06-01..10 positive and adverse control groups for benchmark integrity, statistics, leakage, and surrogates."""
import math
import resource
import subprocess
import sys
import time
import unittest
from assurance.testing import contracts as c
from assurance.testing import splits as sp
from assurance.testing import statistics as st


def _sample_record(idx, spec, lot, root, traj, session='S1', operator='OP1', label=0, feature=1.0):
    return {
        'record_id': f'rec-{idx}',
        'specimen_id': spec,
        'parent_stock_lot': lot,
        'lineage_root_id': root,
        'trajectory_id': traj,
        'raw_sha256': c.raw_hash(f'raw-{idx}-{spec}-{traj}'.encode()),
        'session_id': session,
        'operator_id': operator,
        'label': label,
        'feature': feature,
    }


class StatisticsContracts(unittest.TestCase):
    def test_T06_01_cpu_accounting(self):
        # Measure an owned child subprocess with distinct wall, parent CPU, and child CPU
        r_self_0 = resource.getrusage(resource.RUSAGE_SELF)
        r_child_0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        t0 = time.monotonic()
        subprocess.run([sys.executable, '-c', 'sum(i*i for i in range(25000))'], check=True)
        wall = max(1e-6, time.monotonic() - t0)
        r_self_1 = resource.getrusage(resource.RUSAGE_SELF)
        r_child_1 = resource.getrusage(resource.RUSAGE_CHILDREN)

        parent_cpu = max(0.0, (r_self_1.ru_utime - r_self_0.ru_utime) + (r_self_1.ru_stime - r_self_0.ru_stime))
        child_cpu = max(0.0, (r_child_1.ru_utime - r_child_0.ru_utime) + (r_child_1.ru_stime - r_child_0.ru_stime))
        rss_kb = max(float(r_self_1.ru_maxrss), float(r_child_1.ru_maxrss), 1.0)

        valid_rec = {
            'wall_seconds': wall,
            'parent_cpu_seconds': parent_cpu,
            'child_cpu_seconds': child_cpu,
            'total_cpu_core_seconds': parent_cpu + child_cpu,
            'max_rss_kb': rss_kb,
            'threads_requested': 4,
            'accounting_basis': 'rusage_parent_plus_children',
        }
        out = st.validate_cpu_accounting(valid_rec)
        self.assertAlmostEqual(out['total_cpu_core_seconds'], parent_cpu + child_cpu)

        # Adverse control 1: wall * threads labeled as total_cpu_core_seconds
        bad_wall_mult = dict(valid_rec, total_cpu_core_seconds=wall * 4.0 + 0.5)
        with self.assertRaisesRegex(c.ContractError, 'parent_cpu_seconds \\+ child_cpu_seconds'):
            st.validate_cpu_accounting(bad_wall_mult)

        # Adverse control 2: explicit wall_time_sum basis
        bad_basis = dict(valid_rec, accounting_basis='wall_time_sum')
        with self.assertRaisesRegex(c.ContractError, 'accounting basis'):
            st.validate_cpu_accounting(bad_basis)

    def test_T06_02_workload_collision(self):
        # Collision pair with identical rounded sums (1.000) and identical overall exact sum (1.0008),
        # but different individual genome rows.
        w_a = [[0.1004, 0.2004], [0.3000, 0.4000]]
        w_b = [[0.1000, 0.2000], [0.3004, 0.4004]]
        self.assertEqual(round(sum( sum(r) for r in w_a ), 3), round(sum( sum(r) for r in w_b ), 3))
        self.assertAlmostEqual(sum(sum(r) for r in w_a), sum(sum(r) for r in w_b), places=12)

        # Positive control: identical ordered workload matches
        h_a = st.verify_workload_parity(w_a, [list(r) for r in w_a])
        self.assertEqual(len(h_a), 64)

        # Adverse control 1: rounded-sum collision pair rejected
        with self.assertRaisesRegex(c.ContractError, 'workload_identity_mismatch'):
            st.verify_workload_parity(w_a, w_b)

        # Adverse control 2: reordered rows rejected
        with self.assertRaisesRegex(c.ContractError, 'workload_identity_mismatch'):
            st.verify_workload_parity(w_a, list(reversed(w_a)))

    def test_T06_03_equal_budget(self):
        base_arm = {
            'evaluator_sha256': 'a' * 64,
            'representation_id': 'crescent-128-v2',
            'objective_id': 'qd-capfree-v1',
            'seed_schedule_sha256': 'b' * 64,
            'total_budget_units': 120.0,
            'counts': {'attempted': 100, 'succeeded': 85, 'failed': 10, 'cached': 5, 'confirmations': 2},
            'costs': {'eval_unit_cost': 1.0, 'confirmation_unit_cost': 10.0, 'total_cost_units': 120.0},
        }
        other_arm = {
            **base_arm,
            'counts': {'attempted': 100, 'succeeded': 92, 'failed': 3, 'cached': 5, 'confirmations': 2},
            'costs': {'eval_unit_cost': 1.0, 'confirmation_unit_cost': 10.0, 'total_cost_units': 120.0},
        }
        # Positive control: equal total budget and complete accounting even with different failure rates
        res = st.validate_equal_budget_comparison(base_arm, other_arm)
        self.assertEqual(res['status'], 'valid_equal_budget')

        # Adverse control 1: counting only succeeded evaluations in total_cost_units (ignoring failed/confirmations)
        survivor_only = {
            **other_arm,
            'costs': {'eval_unit_cost': 1.0, 'confirmation_unit_cost': 10.0, 'total_cost_units': 92.0},
        }
        with self.assertRaisesRegex(c.ContractError, 'omits failed/cached/confirmation'):
            st.validate_equal_budget_comparison(base_arm, survivor_only)

        # Adverse control 2: unequal representation or evaluator across arms
        diff_rep = {**other_arm, 'representation_id': 'repaired-crescent-v3'}
        with self.assertRaisesRegex(c.ContractError, 'unequal benchmark representation_id'):
            st.validate_equal_budget_comparison(base_arm, diff_rep)

    def test_T06_04_related_split(self):
        train = [
            _sample_record(1, 'spec-A1', 'lot-1', 'lineage-1', 'traj-1'),
            _sample_record(2, 'spec-A2', 'lot-2', 'lineage-2', 'traj-2'),
        ]
        holdout = [
            _sample_record(3, 'spec-B1', 'lot-3', 'lineage-3', 'traj-3'),
            _sample_record(4, 'spec-B2', 'lot-4', 'lineage-4', 'traj-4'),
        ]
        # Positive control: completely disjoint specimens, lots, lineages, trajectories
        self.assertEqual(sp.validate_group_split(train, holdout)['status'], 'disjoint_lineage_split')

        # Adverse 1: sibling genome sharing lineage_root_id across splits
        bad_sibling = [_sample_record(5, 'spec-C1', 'lot-5', 'lineage-1', 'traj-5')]
        with self.assertRaisesRegex(c.ContractError, 'group_split_leakage:lineage_root_id'):
            sp.validate_group_split(train, bad_sibling)

        # Adverse 2: same parent_stock_lot across splits
        bad_lot = [_sample_record(6, 'spec-C2', 'lot-2', 'lineage-6', 'traj-6')]
        with self.assertRaisesRegex(c.ContractError, 'group_split_leakage:parent_stock_lot'):
            sp.validate_group_split(train, bad_lot)

        # Adverse 3: missing group ID treated as error, never singleton
        missing_group = [{**holdout[0], 'parent_stock_lot': ''}]
        with self.assertRaisesRegex(c.ContractError, 'missing_lineage_or_group_id'):
            sp.validate_group_split(train, missing_group)

    def test_T06_05_session_shortcut(self):
        # Confounded training set: session S1 has only label 0, session S2 has only label 1
        train = [
            _sample_record(1, 'spec-1', 'lot-1', 'lin-1', 'tr-1', session='S1', operator='OP1', label=0),
            _sample_record(2, 'spec-2', 'lot-2', 'lin-2', 'tr-2', session='S2', operator='OP2', label=1),
        ]
        # Holdout swaps session-to-label pairing (nuisance holdout)
        holdout = [
            _sample_record(3, 'spec-3', 'lot-3', 'lin-3', 'tr-3', session='S1', operator='OP1', label=1),
            _sample_record(4, 'spec-4', 'lot-4', 'lin-4', 'tr-4', session='S2', operator='OP2', label=0),
        ]
        # Positive control: genuine damage predictor tracks true state on nuisance-swapped holdout
        good_preds = {'rec-3': 1, 'rec-4': 0}
        self.assertEqual(sp.validate_nuisance_holdout(train, holdout, good_preds)['status'],
                         'nuisance_holdout_verified')

        # Adverse control: session-shortcut predictor predicts S1->0, S2->1 and is rejected
        shortcut_preds = {'rec-3': 0, 'rec-4': 1}
        with self.assertRaisesRegex(c.ContractError, 'session_or_operator_shortcut_detected'):
            sp.validate_nuisance_holdout(train, holdout, shortcut_preds)

    def test_T06_06_preprocessing_leak(self):
        train = [
            _sample_record(1, 'spec-1', 'lot-1', 'lin-1', 'tr-1', feature=10.0),
            _sample_record(2, 'spec-2', 'lot-2', 'lin-2', 'tr-2', feature=20.0),
        ]
        holdout = [
            _sample_record(3, 'spec-3', 'lot-3', 'lin-3', 'tr-3', feature=100.0),
        ]
        train_ids = ['rec-1', 'rec-2']
        valid_proto = {
            'fitted_on_record_ids': train_ids,
            'fitted_on_sha256': c.scientific_hash(train_ids),
            'holdout_sealed': True,
            'holdout_open_count': 1,
            'fit_step_index': 1,
            'eval_step_index': 2,
            'norm_mean': 15.0,
            'norm_std': 5.0,
        }
        self.assertEqual(sp.validate_preprocessing_fit(valid_proto, train, holdout)['status'],
                         'train_only_preprocessing_verified')

        # Adverse 1: normalization mean/std computed on pooled train+holdout (mean=43.333...)
        pooled_vals = [10.0, 20.0, 100.0]
        p_mean = sum(pooled_vals) / 3.0
        p_std = math.sqrt(sum((x - p_mean) ** 2 for x in pooled_vals) / 3.0)
        leaked_stats = {**valid_proto, 'norm_mean': p_mean, 'norm_std': p_std}
        with self.assertRaisesRegex(c.ContractError, 'preprocessing_statistics_leaked_from_holdout'):
            sp.validate_preprocessing_fit(leaked_stats, train, holdout)

        # Adverse 2: holdout record ID included in fitted_on_record_ids
        leaked_ids = {**valid_proto, 'fitted_on_record_ids': ['rec-1', 'rec-2', 'rec-3']}
        with self.assertRaisesRegex(c.ContractError, 'preprocessing_fit_includes_holdout_records'):
            sp.validate_preprocessing_fit(leaked_ids, train, holdout)

    def test_T06_07_single_specimen(self):
        # 500 grains/scans all from one Ti-7Al specimen
        single_spec_records = [
            {'grain_id': i, 'specimen_id': 'Ti7Al-spec-01', 'material_lot': 'lot-Ti7Al-A', 'alloy': 'Ti-7Al'}
            for i in range(500)
        ]
        # Positive control: method benchmark claim is permitted with effective_n_specimens=1 and no product qualification
        res = st.evaluate_dataset_qualification_scope(single_spec_records, 'method_benchmark_only')
        self.assertEqual(res['effective_n_specimens'], 1)
        self.assertEqual(res['effective_n_lots'], 1)
        self.assertIsNone(res['product_qualification'])

        # Adverse control: attempting to pass multi_lot_production_gate with 500 grains from 1 specimen
        with self.assertRaisesRegex(c.ContractError, 'single_specimen_or_insufficient_lots'):
            st.evaluate_dataset_qualification_scope(single_spec_records, 'multi_lot_production_gate')

    def test_T06_08_uncertainty_censor(self):
        # Exact binomial 95% upper miss bound for n=30 with 0 misses is 1 - 0.05^(1/30) ~= 9.50%, never < 1%
        ub30 = st.binomial_upper_miss_bound(30, 0, alpha=0.05)
        self.assertAlmostEqual(ub30, 1.0 - (0.05 ** (1.0 / 30.0)), places=12)
        self.assertGreater(ub30, 0.09)

        # Empty stratum returns inconclusive
        self.assertEqual(st.summarize_clustered_stratum([])['status'], 'inconclusive_empty_stratum')

        # Clustered observations with right-censoring preserved
        clustered = [
            {'specimen_id': 'S1', 'censoring': 'exact', 'value': 120.0},
            {'specimen_id': 'S1', 'censoring': 'exact', 'value': 124.0},
            {'specimen_id': 'S2', 'censoring': 'right_censored', 'lower_bound': 150.0, 'upper_bound': None},
            {'specimen_id': 'S3', 'censoring': 'exact', 'value': 110.0},
        ]
        summary = st.summarize_clustered_stratum(clustered, declared_total_count=4)
        self.assertEqual(summary['n_clusters'], 3)
        self.assertEqual(summary['censored_count'], 1)

        # Adverse 1: dropping the censored observation from the 4 declared records
        with self.assertRaisesRegex(c.ContractError, 'censored_or_missed_observation_dropped'):
            st.summarize_clustered_stratum(clustered[:3], declared_total_count=4)

        # Adverse 2: inflating independent sample count by claiming 4 sub-scans are 4 independent specimens
        inflated = [{**r, 'claimed_independent_n': 4} for r in clustered]
        with self.assertRaisesRegex(c.ContractError, 'independent_count_inflation'):
            st.summarize_clustered_stratum(inflated, declared_total_count=4)

    def test_T06_09_null_benchmark(self):
        baseline = [1.12, 1.15, 1.10, 1.14, 1.13]
        candidate_null = [1.11, 1.15, 1.11, 1.13, 1.12]

        # Positive control: null/slightly negative benchmark executes cleanly and reports rejected/inconclusive
        report = st.evaluate_benchmark_comparison(baseline, candidate_null, min_effect=0.02, expected_seeds=5)
        self.assertEqual(report['execution'], 'passed')
        self.assertIn(report['finding'], ('rejected_within_scope', 'inconclusive'))
        self.assertLessEqual(report['mean_effect'], 0.0)

        # Adverse control 1: forcing a superiority claim on a null/negative benchmark
        with self.assertRaisesRegex(c.ContractError, 'unsupported_superiority_claim'):
            st.evaluate_benchmark_comparison(baseline, candidate_null, min_effect=0.02,
                                             claimed_verdict='superior', expected_seeds=5)

        # Adverse control 2: dropping unfavorable seeds
        with self.assertRaisesRegex(c.ContractError, 'cherry_picked_or_dropped_benchmark_seeds'):
            st.evaluate_benchmark_comparison(baseline[:3], candidate_null[:3], expected_seeds=5)

    def test_T06_10_surrogate_gate(self):
        # Near-threshold / OOD / shared-bias ensemble without high-tier confirmation must abstain
        near_thresh = {
            'evaluator_tier': 'beam_surrogate',
            'predicted_margin': 0.01,
            'uncertainty_band': 0.05,
            'ood_score': 0.85,
            'ood_limit': 0.50,
            'ensemble_bias_groups': [' architecture-A ', ' architecture-A '],
            'copied_into_certified_field': False,
            'high_tier_confirmation': None,
            'claimed_qualification': 'abstain_require_high_tier_confirmation',
        }
        res = st.validate_surrogate_candidate_gate(near_thresh)
        self.assertEqual(res['status'], 'abstain_require_high_tier_confirmation')
        self.assertFalse(res['certified'])

        # Adverse 1: copying a surrogate score into a certified field
        copied = {**near_thresh, 'copied_into_certified_field': True}
        with self.assertRaisesRegex(c.ContractError, 'surrogate_cannot_certify_product_field'):
            st.validate_surrogate_candidate_gate(copied)

        # Adverse 2: claiming qualification on an OOD / near-threshold / shared-bias surrogate without confirmation
        claimed = {**near_thresh, 'claimed_qualification': 'certified_pass'}
        with self.assertRaisesRegex(c.ContractError, 'unconfirmed_ood_or_near_threshold'):
            st.validate_surrogate_candidate_gate(claimed)

        # Positive control with independent higher-tier (T2_solid) confirmation
        confirmed = {
            **near_thresh,
            'predicted_margin': 0.25,
            'ood_score': 0.20,
            'ensemble_bias_groups': ['arch-A', 'arch-B'],
            'high_tier_confirmation': {'tier': 'T2_solid', 'passed': True},
        }
        res_ok = st.validate_surrogate_candidate_gate(confirmed)
        self.assertEqual(res_ok['status'], 'confirmed_by_high_tier')
        self.assertTrue(res_ok['certified'])


if __name__ == '__main__':
    unittest.main()
