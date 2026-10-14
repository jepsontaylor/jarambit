//! T03-06 and T03-07. Pairing uses the sample id on the original row.
use jarambit_monte_carlo::{
    accept_sourced_correlation, check_audit_ids, joint_columns, paired_joint, AuditIds, CheckedError,
    ColumnSample, CommonRandomNumbers, Pair,
};

fn pair(id: u64, a: f64, b: f64) -> Pair { Pair { id, a, b } }

fn j2() -> Vec<Pair> {
    vec![pair(0, 1.0, -1.0), pair(1, 2.0, -2.0), pair(2, -1.0, 1.0), pair(3, -2.0, 2.0)]
}

#[test]
fn joint_requirement_outcomes_preserve_sample_identity() {
    let j1 = paired_joint(&[pair(0, 1.0, 1.0), pair(1, 1.0, 1.0), pair(2, -1.0, -1.0), pair(3, -1.0, -1.0)]).unwrap();
    assert_eq!((j1.joint.text(), j1.marginal_a.text(), j1.product.text(), j1.product_label), ("2/4".into(), "2/4".into(), "1/4".into(), "assumed_independent"));
    let same = paired_joint(&j2()).unwrap();
    assert_eq!((same.joint.text(), same.marginal_a.text(), same.marginal_b.text(), same.product.text()), ("0/4".into(), "2/4".into(), "2/4".into(), "1/4".into()));
    assert_ne!(same.joint.text(), same.product.text());
    let swapped = paired_joint(&[pair(0, -1.0, 1.0), pair(1, -2.0, 2.0), pair(2, 1.0, -1.0), pair(3, 2.0, -2.0)]).unwrap();
    assert_eq!(swapped.joint.text(), "0/4");
    let permuted = paired_joint(&[pair(2, -1.0, 1.0), pair(0, 1.0, -1.0), pair(3, -2.0, 2.0), pair(1, 2.0, -2.0)]).unwrap();
    assert_eq!(permuted.joint.text(), "0/4");
    let a = [ColumnSample { id: 0, value: 1.0 }, ColumnSample { id: 1, value: 2.0 }, ColumnSample { id: 2, value: -1.0 }, ColumnSample { id: 3, value: -2.0 }];
    let b = [ColumnSample { id: 2, value: 1.0 }, ColumnSample { id: 1, value: -2.0 }, ColumnSample { id: 0, value: -1.0 }, ColumnSample { id: 3, value: 2.0 }];
    assert_eq!(joint_columns(&a, &b), Err(CheckedError::MismatchedSampleId));
    let mut sorted_a = [1.0, 2.0, -1.0, -2.0];
    let mut sorted_b = [-1.0, -2.0, 1.0, 2.0];
    sorted_a.sort_by(|x, y| x.partial_cmp(y).unwrap());
    sorted_b.sort_by(|x, y| x.partial_cmp(y).unwrap());
    let mutant = sorted_a.iter().zip(sorted_b.iter()).filter(|(x, y)| **x > 0.0 && **y > 0.0).count();
    assert_eq!(mutant, 2);
    assert_ne!(same.joint.passes, mutant as u64);
}

#[test]
fn four_state_joint_matches_product_and_audit_ids_are_not_reused() {
    let rows = [pair(0, 1.0, 1.0), pair(1, 1.0, -1.0), pair(2, -1.0, 1.0), pair(3, -1.0, -1.0)];
    let est = paired_joint(&rows).unwrap();
    assert_eq!((est.joint.text(), est.product.text()), ("1/4".into(), "1/4".into()));
    assert_eq!(est.product_label, "assumed_independent");
    let j2 = paired_joint(&j2()).unwrap();
    assert_ne!(j2.joint.passes, j2.product.num as u64);
    check_audit_ids(AuditIds { search: 11, calibration: 22, final_audit: 33 }).unwrap();
    assert_eq!(check_audit_ids(AuditIds { search: 11, calibration: 22, final_audit: 11 }), Err(CheckedError::AuditStreamNotIndependent));
    let _crn = CommonRandomNumbers { stream: 11 };
    assert_eq!(accept_sourced_correlation(false), Err(CheckedError::UnsourcedCorrelation));
    accept_sourced_correlation(true).unwrap();
}

#[test]
fn aligned_joint_columns_count_passes_and_crn_does_not_change_them() {
    let a = [
        ColumnSample { id: 0, value: 1.0 },
        ColumnSample { id: 1, value: 1.0 },
        ColumnSample { id: 2, value: -1.0 },
        ColumnSample { id: 3, value: -1.0 },
    ];
    let b = [
        ColumnSample { id: 0, value: 1.0 },
        ColumnSample { id: 1, value: 1.0 },
        ColumnSample { id: 2, value: -1.0 },
        ColumnSample { id: 3, value: -1.0 },
    ];
    let est = joint_columns(&a, &b).unwrap();
    assert_eq!((est.joint.text(), est.marginal_a.text(), est.marginal_b.text(), est.product.text(), est.product_label), ("2/4".into(), "2/4".into(), "2/4".into(), "1/4".into(), "assumed_independent"));
    let j2a = [
        ColumnSample { id: 0, value: 1.0 },
        ColumnSample { id: 1, value: 2.0 },
        ColumnSample { id: 2, value: -1.0 },
        ColumnSample { id: 3, value: -2.0 },
    ];
    let j2b = [
        ColumnSample { id: 0, value: -1.0 },
        ColumnSample { id: 1, value: -2.0 },
        ColumnSample { id: 2, value: 1.0 },
        ColumnSample { id: 3, value: 2.0 },
    ];
    let opposed = joint_columns(&j2a, &j2b).unwrap();
    assert_eq!(opposed.joint.text(), "0/4");
    assert_eq!(opposed.product.text(), "1/4");
    let swapped = joint_columns(&j2b, &j2a).unwrap();
    assert_eq!(swapped.joint.text(), opposed.joint.text());
    let short = [ColumnSample { id: 0, value: 1.0 }];
    assert_eq!(joint_columns(&j2a, &short), Err(CheckedError::MismatchedSampleId));
    assert_eq!(joint_columns(&[], &[]), Err(CheckedError::EmptySample));
    let dup_a = [ColumnSample { id: 0, value: 1.0 }, ColumnSample { id: 0, value: 2.0 }];
    let dup_b = [ColumnSample { id: 0, value: 1.0 }, ColumnSample { id: 0, value: -1.0 }];
    assert_eq!(joint_columns(&dup_a, &dup_b), Err(CheckedError::DuplicateSampleId));
    let ids = AuditIds { search: 11, calibration: 22, final_audit: 33 };
    let crn = CommonRandomNumbers { stream: ids.search };
    assert_eq!(check_audit_ids(ids), Ok(()));
    assert_eq!(check_audit_ids(AuditIds { search: crn.stream, calibration: 22, final_audit: crn.stream }), Err(CheckedError::AuditStreamNotIndependent));
    let again = joint_columns(&a, &b).unwrap();
    assert_eq!(again.joint.passes, est.joint.passes);
    assert_eq!(accept_sourced_correlation(false), Err(CheckedError::UnsourcedCorrelation));
    println!("S04_CASE id=T03-06-joint-columns joint=2/4 marginal_a=2/4 marginal_b=2/4 product=1/4 label=assumed_independent");
    println!("S04_CASE id=T03-07-crn crn_stream={} audit_positive=1 audit_reused=0 joint_unchanged=1 shared_slot=0", crn.stream);
}

#[test]
fn nonfinite_joint_inputs_publish_no_rate() {
    let finite = paired_joint(&[pair(0, 1.0, 2.0), pair(1, -1.0, 2.0)]).unwrap();
    assert_eq!(finite.joint.text(), "1/2");
    assert_eq!(finite.marginal_a.text(), "1/2");
    assert_eq!(finite.marginal_b.text(), "2/2");
    assert_eq!(finite.product.text(), "1/2");
    assert_eq!(finite.product_label, "assumed_independent");
    let failing = paired_joint(&[pair(0, -1.0, -2.0)]).unwrap();
    assert_eq!((failing.joint.text(), failing.marginal_a.text(), failing.marginal_b.text(), failing.product.text()), ("0/1".into(), "0/1".into(), "0/1".into(), "0/1".into()));
    for bad in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        for (a, b) in [(bad, 1.0), (1.0, bad)] {
            assert_eq!(paired_joint(&[pair(0, a, b)]), Err(CheckedError::NonFiniteInput));
        }
        let left = [ColumnSample { id: 0, value: bad }];
        let right = [ColumnSample { id: 0, value: 1.0 }];
        assert_eq!(joint_columns(&left, &right), Err(CheckedError::NonFiniteInput));
        let left = [ColumnSample { id: 0, value: 1.0 }];
        let right = [ColumnSample { id: 0, value: bad }];
        assert_eq!(joint_columns(&left, &right), Err(CheckedError::NonFiniteInput));
    }
}
