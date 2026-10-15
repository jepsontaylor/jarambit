"""T06 split, lineage grouping, session shortcut, and preprocessing leakage contracts."""
import math
from .contracts import ContractError, finite, require, scientific_hash


def _extract_groups(records, split_name):
    require(isinstance(records, list) and len(records) > 0, f'{split_name} must be a non-empty list')
    groups = {
        'specimen_id': set(),
        'parent_stock_lot': set(),
        'lineage_root_id': set(),
        'trajectory_id': set(),
        'raw_sha256': set(),
        'record_id': set(),
    }
    for idx, rec in enumerate(records):
        require(isinstance(rec, dict), f'{split_name}[{idx}] must be an object')
        for key in groups:
            val = rec.get(key)
            # Missing group ID is rejected rather than treated as a unique singleton.
            require(isinstance(val, str) and val.strip(),
                    f'missing_lineage_or_group_id:{split_name}[{idx}].{key}')
            groups[key].add(val.strip())
    return groups


def validate_group_split(train_records, holdout_records):
    """T06-04: Reject any specimen, parent stock/lot, sibling lineage, trajectory, or raw frame overlap."""
    train_g = _extract_groups(train_records, 'train')
    holdout_g = _extract_groups(holdout_records, 'holdout')
    for key in ('specimen_id', 'parent_stock_lot', 'lineage_root_id', 'trajectory_id', 'raw_sha256', 'record_id'):
        overlap = sorted(train_g[key] & holdout_g[key])
        require(not overlap, f'group_split_leakage:{key}:{overlap[0] if overlap else ""}')
    return {
        'status': 'disjoint_lineage_split',
        'train_specimens': len(train_g['specimen_id']),
        'holdout_specimens': len(holdout_g['specimen_id']),
    }


def validate_nuisance_holdout(train_records, holdout_records, predictions):
    """T06-05: Detect operator/session identity shortcuts and require nuisance-swapped holdout stability."""
    validate_group_split(train_records, holdout_records)
    require(isinstance(predictions, dict) and len(predictions) == len(holdout_records),
            'predictions must map every holdout record_id to a predicted label')

    # Check if operator_id or session_id is perfectly confounded with label in training
    for nuisance_key in ('session_id', 'operator_id'):
        by_val = {}
        for r in train_records:
            nv = r.get(nuisance_key)
            lbl = r.get('label')
            require(isinstance(nv, str) and nv.strip() and isinstance(lbl, int),
                    f'missing {nuisance_key} or label in training')
            by_val.setdefault(nv.strip(), set()).add(lbl)
        # If every session/operator in training only ever saw a single class label, flag confounding
        if len(by_val) >= 2 and all(len(labels) == 1 for labels in by_val.values()):
            train_map = {nv: next(iter(labels)) for nv, labels in by_val.items()}
        else:
            train_map = {}

        # Evaluate on holdout (where session/operator assignment is swapped or novel)
        correct = 0
        follows_shortcut = 0
        for r in holdout_records:
            rid = r['record_id']
            require(rid in predictions, f'missing prediction for {rid}')
            pred = predictions[rid]
            if pred == r['label']:
                correct += 1
            nv = r.get(nuisance_key, '').strip()
            if nv in train_map and pred == train_map[nv]:
                follows_shortcut += 1
        if train_map and follows_shortcut == len(holdout_records) and correct < len(holdout_records):
            raise ContractError(f'session_or_operator_shortcut_detected:{nuisance_key}')

    accuracy = sum(1 for r in holdout_records if predictions[r['record_id']] == r['label']) / len(holdout_records)
    require(accuracy >= 0.75, 'nuisance_holdout_accuracy_below_gate')
    return {'status': 'nuisance_holdout_verified', 'accuracy': accuracy}


def validate_preprocessing_fit(protocol, train_records, holdout_records):
    """T06-06: Normalization, segmentation, and decision thresholds must be fit strictly on training data."""
    validate_group_split(train_records, holdout_records)
    require(isinstance(protocol, dict), 'preprocessing protocol must be an object')
    train_ids = sorted(r['record_id'] for r in train_records)
    holdout_ids = {r['record_id'] for r in holdout_records}
    fitted_ids = protocol.get('fitted_on_record_ids')
    require(isinstance(fitted_ids, list) and len(fitted_ids) > 0, 'fitted_on_record_ids required')
    require(not (set(fitted_ids) & holdout_ids), 'preprocessing_fit_includes_holdout_records')
    require(sorted(fitted_ids) == train_ids, 'fitted_on_record_ids_mismatch')
    require(protocol.get('fitted_on_sha256') == scientific_hash(train_ids), 'fitted_on_sha256_mismatch')
    require(protocol.get('holdout_sealed') is True and protocol.get('holdout_open_count') == 1,
            'holdout_seal_or_reuse_violation')
    require(protocol.get('fit_step_index', 0) < protocol.get('eval_step_index', 0),
            'threshold_or_preprocessing_fit_after_holdout_eval')

    # Verify reported normalization mean/std match train-only values rather than pooled train+holdout
    train_vals = [finite(r['feature']) for r in train_records]
    expected_mean = sum(train_vals) / len(train_vals)
    expected_std = math.sqrt(sum((x - expected_mean) ** 2 for x in train_vals) / len(train_vals))
    rep_mean = finite(protocol['norm_mean'])
    rep_std = finite(protocol['norm_std'])
    require(math.isclose(rep_mean, expected_mean, rel_tol=1e-9, abs_tol=1e-9) and
            math.isclose(rep_std, expected_std, rel_tol=1e-9, abs_tol=1e-9),
            'preprocessing_statistics_leaked_from_holdout')
    return {'status': 'train_only_preprocessing_verified', 'norm_mean': rep_mean, 'norm_std': rep_std}
