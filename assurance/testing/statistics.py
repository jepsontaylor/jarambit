"""T06 statistical, CPU accounting, workload identity, equal-budget, and surrogate gate contracts."""
import math
from .contracts import ContractError, finite, require, scientific_hash


def validate_cpu_accounting(record):
    """T06-01: Report measured parent/child CPU and wall quantities separately; reject wall-sum core-seconds."""
    require(isinstance(record, dict), 'CPU accounting record must be an object')
    for key in ('wall_seconds', 'parent_cpu_seconds', 'child_cpu_seconds',
                'total_cpu_core_seconds', 'max_rss_kb', 'threads_requested'):
        require(key in record, f'missing CPU accounting field: {key}')
    wall = finite(record['wall_seconds'])
    parent_cpu = finite(record['parent_cpu_seconds'])
    child_cpu = finite(record['child_cpu_seconds'])
    total_cpu = finite(record['total_cpu_core_seconds'])
    rss = finite(record['max_rss_kb'])
    threads = record['threads_requested']
    require(isinstance(threads, int) and not isinstance(threads, bool) and threads >= 1,
            'threads_requested must be a positive integer')
    require(wall > 0.0 and parent_cpu >= 0.0 and child_cpu >= 0.0 and total_cpu >= 0.0 and rss > 0.0,
            'CPU and memory quantities must be non-negative (wall and RSS positive)')
    basis = record.get('accounting_basis', 'rusage_parent_plus_children')
    require(basis == 'rusage_parent_plus_children',
            f'unsupported or wall-conflated CPU accounting basis: {basis}')
    expected_cpu = parent_cpu + child_cpu
    require(math.isclose(total_cpu, expected_cpu, rel_tol=1e-9, abs_tol=1e-9),
            'total_cpu_core_seconds must equal measured parent_cpu_seconds + child_cpu_seconds')
    return {
        'wall_seconds': wall,
        'parent_cpu_seconds': parent_cpu,
        'child_cpu_seconds': child_cpu,
        'total_cpu_core_seconds': total_cpu,
        'max_rss_kb': rss,
        'threads_requested': threads,
    }


def workload_identity(genomes):
    """T06-02: Exact ordered content hash over finite genome rows; rounded-sum checksums are rejected."""
    require(isinstance(genomes, list) and len(genomes) > 0, 'workload must be a non-empty list of genomes')
    canonical_rows = []
    for idx, row in enumerate(genomes):
        require(isinstance(row, list) and len(row) > 0, f'genome row {idx} must be a non-empty list')
        canonical_rows.append([finite(val) for val in row])
    return scientific_hash({'schema': 'jarambit.workload.v1', 'count': len(canonical_rows), 'rows': canonical_rows})


def verify_workload_parity(genomes_a, genomes_b):
    """Reject workloads that only match under rounded sums or row permutations."""
    hash_a = workload_identity(genomes_a)
    hash_b = workload_identity(genomes_b)
    require(hash_a == hash_b, 'workload_identity_mismatch')
    return hash_a


def validate_equal_budget_comparison(arm_a, arm_b):
    """T06-03: Common total budget, evaluator, representation, objective, seed schedule, and complete accounting."""
    for label, arm in (('arm_a', arm_a), ('arm_b', arm_b)):
        require(isinstance(arm, dict), f'{label} must be an object')
        for field in ('evaluator_sha256', 'representation_id', 'objective_id',
                      'seed_schedule_sha256', 'total_budget_units', 'counts', 'costs'):
            require(field in arm, f'{label} missing {field}')
        counts = arm['counts']
        costs = arm['costs']
        require(isinstance(counts, dict) and isinstance(costs, dict), f'{label} counts/costs must be objects')
        for k in ('attempted', 'succeeded', 'failed', 'cached', 'confirmations'):
            v = counts.get(k)
            require(isinstance(v, int) and not isinstance(v, bool) and v >= 0, f'{label}.counts.{k} invalid')
        require(counts['attempted'] > 0, f'{label} must attempt at least one evaluation')
        require(counts['attempted'] == counts['succeeded'] + counts['failed'] + counts['cached'],
                f'{label} evaluation counts do not reconcile (attempted != succeeded + failed + cached)')
        unit_cost = finite(costs.get('eval_unit_cost', 0.0))
        confirm_cost = finite(costs.get('confirmation_unit_cost', 0.0))
        reported_total = finite(costs.get('total_cost_units', -1.0))
        require(unit_cost > 0.0 and confirm_cost >= 0.0, f'{label} unit costs must be positive')
        # Budget includes all attempted (succeeded + failed + cached) evaluations plus expensive confirmations.
        expected_cost = counts['attempted'] * unit_cost + counts['confirmations'] * confirm_cost
        require(math.isclose(reported_total, expected_cost, rel_tol=1e-9, abs_tol=1e-9),
                f'{label} total_cost_units omits failed/cached/confirmation work')
        budget = finite(arm['total_budget_units'])
        require(reported_total <= budget + 1e-9, f'{label} exceeded preregistered total budget')

    for shared in ('evaluator_sha256', 'representation_id', 'objective_id',
                   'seed_schedule_sha256', 'total_budget_units'):
        require(arm_a[shared] == arm_b[shared], f'unequal benchmark {shared} across methods')
    return {'status': 'valid_equal_budget', 'total_budget_units': finite(arm_a['total_budget_units'])}


def evaluate_dataset_qualification_scope(records, requested_claim):
    """T06-07: Single-specimen or wrong-alloy datasets cannot pass multi-lot or Ti-6Al-4V qualification gates."""
    require(isinstance(records, list) and len(records) > 0, 'records must be a non-empty list')
    specimens = set()
    lots = set()
    alloys = set()
    for r in records:
        require(isinstance(r, dict), 'record must be an object')
        spec = r.get('specimen_id')
        lot = r.get('material_lot')
        alloy = r.get('alloy')
        require(isinstance(spec, str) and spec.strip(), 'missing specimen_id')
        require(isinstance(lot, str) and lot.strip(), 'missing material_lot')
        require(isinstance(alloy, str) and alloy.strip(), 'missing alloy')
        specimens.add(spec.strip())
        lots.add(lot.strip())
        alloys.add(alloy.strip())
    n_spec = len(specimens)
    n_lots = len(lots)
    if requested_claim == 'method_benchmark_only':
        return {
            'scope': 'method_benchmark_only',
            'effective_n_specimens': n_spec,
            'effective_n_lots': n_lots,
            'sub_observations': len(records),
            'product_qualification': None,
        }
    if requested_claim == 'multi_lot_production_gate':
        require(n_lots >= 3 and n_spec >= 3, 'single_specimen_or_insufficient_lots_for_production_gate')
        require(alloys == {'Ti-6Al-4V'}, 'non_ti6al4v_alloy_cannot_qualify_production_gate')
        return {
            'scope': 'multi_lot_production_gate',
            'effective_n_specimens': n_spec,
            'effective_n_lots': n_lots,
            'sub_observations': len(records),
            'product_qualification': 'eligible_for_review',
        }
    raise ContractError(f'unknown requested_claim: {requested_claim}')


def binomial_upper_miss_bound(n_independent, misses, alpha=0.05):
    """T06-08: Exact one-sided (1-alpha) upper bound on miss probability for zero misses, or Clopper-Pearson."""
    require(isinstance(n_independent, int) and not isinstance(n_independent, bool) and n_independent >= 1,
            'n_independent must be >= 1')
    require(isinstance(misses, int) and not isinstance(misses, bool) and 0 <= misses <= n_independent,
            'invalid miss count')
    alpha = finite(alpha)
    require(0.0 < alpha < 1.0, 'alpha must be in (0, 1)')
    if misses == 0:
        return 1.0 - (alpha ** (1.0 / n_independent))
    if misses == n_independent:
        return 1.0
    # Bisection on regularized binomial cumulative sum P(X <= misses | n, p) = alpha
    lo, hi = 0.0, 1.0
    for _ in range(64):
        mid = 0.5 * (lo + hi)
        cdf = sum(math.comb(n_independent, k) * (mid ** k) * ((1.0 - mid) ** (n_independent - k))
                  for k in range(misses + 1))
        if cdf > alpha:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def summarize_clustered_stratum(records, declared_total_count=None, alpha=0.05):
    """T06-08: Handle empty, zero-variance, censored, and clustered observations without count inflation."""
    require(isinstance(records, list), 'stratum records must be a list')
    if declared_total_count is not None:
        require(len(records) == declared_total_count, 'censored_or_missed_observation_dropped')
    if len(records) == 0:
        return {'status': 'inconclusive_empty_stratum', 'n_clusters': 0, 'n_observations': 0, 'interval': None}
    clusters = set()
    values = []
    censored_count = 0
    for r in records:
        require(isinstance(r, dict), 'observation must be an object')
        cid = r.get('specimen_id')
        require(isinstance(cid, str) and cid.strip(), 'missing cluster/specimen_id')
        clusters.add(cid.strip())
        censor = r.get('censoring', 'exact')
        require(censor in ('exact', 'right_censored', 'interval_censored'), f'invalid censoring: {censor}')
        if censor != 'exact':
            censored_count += 1
            lo = finite(r['lower_bound'])
            hi = finite(r['upper_bound']) if r.get('upper_bound') is not None else float('inf')
            require(lo >= 0.0 and hi >= lo, 'invalid censored interval bounds')
            values.append(lo)
        else:
            values.append(finite(r['value']))
    n_clusters = len(clusters)
    # Effective independent sample size is bounded by cluster count, never inflated by sub-scans.
    if r_claimed := records[0].get('claimed_independent_n'):
        require(r_claimed <= n_clusters, 'independent_count_inflation_from_clustered_scans')
    mean_val = sum(values) / len(values)
    var_val = sum((v - mean_val) ** 2 for v in values) / max(1, len(values) - 1) if len(values) > 1 else 0.0
    if var_val == 0.0 or n_clusters < 2:
        return {
            'status': 'zero_variance_or_single_cluster_unqualified',
            'n_clusters': n_clusters,
            'n_observations': len(records),
            'censored_count': censored_count,
            'upper_miss_bound_95': binomial_upper_miss_bound(n_clusters, 0, alpha=alpha),
            'interval': None,
        }
    se_cluster = math.sqrt(var_val / n_clusters)
    half_width = 1.96 * se_cluster
    return {
        'status': 'bounded_with_uncertainty',
        'n_clusters': n_clusters,
        'n_observations': len(records),
        'censored_count': censored_count,
        'mean_lower_bound': mean_val,
        'interval': (mean_val - half_width, mean_val + half_width),
    }


def evaluate_benchmark_comparison(baseline_scores, candidate_scores, min_effect=0.05,
                                  claimed_verdict=None, expected_seeds=None):
    """T06-09: Honest effect and confidence interval reporting for null or negative optimization benchmarks."""
    require(isinstance(baseline_scores, list) and isinstance(candidate_scores, list), 'scores must be lists')
    require(len(baseline_scores) == len(candidate_scores) and len(baseline_scores) >= 3,
            'paired benchmark requires >= 3 matched seeds')
    if expected_seeds is not None:
        require(len(baseline_scores) == expected_seeds, 'cherry_picked_or_dropped_benchmark_seeds')
    diffs = [finite(c) - finite(b) for b, c in zip(baseline_scores, candidate_scores)]
    n = len(diffs)
    mean_diff = sum(diffs) / n
    var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var_diff / n)
    # 95% normal/t-conservative interval (using 2.262 for small n <= 10, else 1.96)
    crit = 2.262 if n <= 10 else 1.96
    ci_low, ci_high = mean_diff - crit * se, mean_diff + crit * se
    if ci_low >= finite(min_effect):
        finding = 'supported_within_scope'
    elif ci_high <= 0.0:
        finding = 'rejected_within_scope'
    else:
        finding = 'inconclusive'
    if claimed_verdict == 'superior':
        require(finding == 'supported_within_scope', 'unsupported_superiority_claim_on_null_or_negative_result')
    return {
        'execution': 'passed',
        'finding': finding,
        'mean_effect': mean_diff,
        'ci_95': (ci_low, ci_high),
        'n_seeds': n,
    }


def validate_surrogate_candidate_gate(candidate):
    """T06-10: Near-threshold, OOD, or shared-bias surrogate ensembles must abstain and require high-tier confirmation."""
    require(isinstance(candidate, dict), 'candidate record must be an object')
    tier = candidate.get('evaluator_tier')
    pred_margin = finite(candidate['predicted_margin'])
    uncertainty = finite(candidate['uncertainty_band'])
    ood_score = finite(candidate['ood_score'])
    ood_limit = finite(candidate['ood_limit'])
    require(uncertainty >= 0.0 and ood_score >= 0.0 and ood_limit > 0.0, 'invalid uncertainty or OOD bounds')

    ensemble_bias_groups = candidate.get('ensemble_bias_groups', [])
    require(isinstance(ensemble_bias_groups, list) and len(ensemble_bias_groups) > 0,
            'ensemble_bias_groups required')
    shared_bias = len(set(ensemble_bias_groups)) == 1 and len(ensemble_bias_groups) > 1

    # Surrogate values can never populate a certified product field directly.
    require(not candidate.get('copied_into_certified_field', False),
            'surrogate_cannot_certify_product_field')
    require(tier in ('T0_surrogate', 'beam_surrogate'), f'unexpected surrogate tier: {tier}')

    high_tier = candidate.get('high_tier_confirmation')
    if ood_score > ood_limit or abs(pred_margin) <= uncertainty or shared_bias:
        if high_tier is None:
            require(candidate.get('claimed_qualification') in (None, 'abstain_require_high_tier_confirmation'),
                    'unconfirmed_ood_or_near_threshold_or_shared_bias_surrogate_claimed_qualified')
            return {'status': 'abstain_require_high_tier_confirmation', 'certified': False}

    require(isinstance(high_tier, dict), 'finalist requires independent higher-tier confirmation record')
    require(high_tier.get('tier') in ('T1_plate', 'T2_solid') and high_tier.get('passed') is True,
            'high_tier_confirmation_failed_or_invalid')
    return {
        'status': 'confirmed_by_high_tier',
        'confirmed_tier': high_tier['tier'],
        'certified': True,
    }
