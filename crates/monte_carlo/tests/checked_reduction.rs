//! T03-01 through T03-05 and the T03-08 planner. No process-global pool and no 1/2/4 spawn.
use jarambit_monte_carlo::{
    admit_threads, legacy_sample_count, mix_seed, plan_ranges, quantile_index, reduce_rows, run_serial_double,
    CheckedError, Finding, MIX_SEED_0, MIX_SEED_1, MIX_SEED_2, MIX_SEED_3, Observation, Ratio, Row, SerialInject,
    ThreadRequest,
};

fn finite(id: u64, v: f64) -> Row { Row { id, value: Observation::Finite(v) } }
fn model(id: u64) -> Row { Row { id, value: Observation::Model } }

fn rows_of(values: &[f64]) -> Vec<Row> {
    values.iter().enumerate().map(|(i, v)| finite(i as u64, *v)).collect()
}

#[test]
fn zero_samples_is_rejected_explicitly() {
    let err = reduce_rows(0, &[]).unwrap_err();
    assert_eq!(err, CheckedError::EmptySample);
    let (legacy_n, label) = legacy_sample_count(0);
    assert_eq!(legacy_n, 1);
    assert_eq!(label, "legacy_unqualified");
    let ok = reduce_rows(1, &[finite(0, 4.0)]).unwrap();
    assert!(ok.statistical_credit);
    assert_eq!(ok.mean_ratio.unwrap().text(), "4/1");
    assert_eq!(ok.p05_index, Some(0));
    assert_eq!(ok.p95_index, Some(0));
    assert_eq!(ok.finding, Finding::SupportedWithinScope);
}

#[test]
fn quantile_boundaries_match_historical_floor_ratio() {
    let a = reduce_rows(20, &rows_of(&(0..20).map(|v| v as f64).collect::<Vec<_>>())).unwrap();
    assert_eq!(a.mean_ratio.unwrap().text(), "19/2");
    assert_eq!(a.p05_index, Some(1));
    assert_eq!(a.p05, Some(1.0));
    assert_eq!(a.p95_index, Some(19));
    assert_eq!(a.p95, Some(19.0));
    let b = reduce_rows(21, &rows_of(&(0..21).map(|v| v as f64).collect::<Vec<_>>())).unwrap();
    assert_eq!(b.mean_ratio.unwrap().text(), "10/1");
    assert_eq!(b.p95_index, Some(19));
    assert_eq!(b.p95, Some(19.0));
    let c = reduce_rows(3, &rows_of(&[10.0, 20.0, 30.0])).unwrap();
    assert_eq!((c.p05, c.p95, c.mean_ratio.unwrap().text()), (Some(10.0), Some(30.0), "20/1".to_string()));
    let d = reduce_rows(3, &rows_of(&[-2.0, 0.0, 2.0])).unwrap();
    assert_eq!((d.p05, d.p95, d.mean_ratio.unwrap().text()), (Some(-2.0), Some(2.0), "0/1".to_string()));
    let e = reduce_rows(4, &rows_of(&[1.0, 2.0, 3.0, 4.0])).unwrap();
    assert_eq!(e.mean_ratio.unwrap().text(), "5/2");
    assert_eq!(quantile_index(194176253407468965, 95, 100), Err(CheckedError::QuantileOverflow));
    assert_eq!(quantile_index(3689348814741910324, 5, 100), Err(CheckedError::QuantileOverflow));
    assert_eq!(quantile_index(194176253407468964, 95, 100).unwrap(), 184467440737095515);
    let p05 = quantile_index(194176253407468964, 5, 100).unwrap();
    assert_eq!(p05, 9708812670373448);
    println!("S04_CASE id=T03-02-fit-p05 index={p05}");
}

#[test]
fn finite_reduction_matches_exact_hex_on_every_order() {
    let two53 = (1u64 << 53) as f64;
    let orders = [[two53, 1.0, -two53], [1.0, two53, -two53], [-two53, two53, 1.0]];
    for order in orders {
        let s = reduce_rows(3, &rows_of(&order)).unwrap();
        assert_eq!(s.sum.unwrap().to_bits(), 1.0f64.to_bits());
        assert_eq!(s.mean.unwrap().to_bits(), (1.0f64 / 3.0).to_bits());
        assert!(s.statistical_credit);
    }
    let tiny = (-100f64).exp2();
    let big = (50f64).exp2();
    let dynamic = [[tiny, big, -big], [big, tiny, -big], [big, -big, tiny]];
    for order in dynamic {
        let s = reduce_rows(3, &rows_of(&order)).unwrap();
        assert_eq!(s.sum.unwrap().to_bits(), tiny.to_bits());
        assert_eq!(s.mean.unwrap().to_bits(), (tiny / 3.0).to_bits());
    }
    let blow = reduce_rows(2, &rows_of(&[f64::MAX, f64::MAX])).unwrap();
    assert_eq!(blow.aggregate_error, Some(CheckedError::UnrepresentableAggregate));
    assert_eq!((blow.valid, blow.invalid, blow.statistical_credit), (2, 0, false));
    assert!(blow.mean.is_none() && blow.p05.is_none());
}

#[test]
fn nonfinite_monte_carlo_sample_is_not_sorted_as_equal() {
    let nan = reduce_rows(3, &rows_of(&[1.0, f64::NAN, 3.0])).unwrap();
    assert_eq!((nan.attempted, nan.valid, nan.invalid, nan.numerically_failed), (3, 2, 1, 1));
    assert!(!nan.statistical_credit && nan.p05.is_none() && nan.mean.is_none());
    for values in [[f64::INFINITY, 1.0, 2.0], [1.0, f64::INFINITY, 2.0], [1.0, 2.0, f64::NEG_INFINITY]] {
        let s = reduce_rows(3, &rows_of(&values)).unwrap();
        assert_eq!((s.valid, s.invalid, s.numerically_failed, s.statistical_credit), (2, 1, 1, false));
        assert!(s.p05.is_none());
    }
    let all = reduce_rows(2, &rows_of(&[f64::NAN, f64::NAN])).unwrap();
    assert_eq!((all.valid, all.invalid), (0, 2));
    assert_ne!(legacy_sample_count(2).0, 1);
    let forward = [finite(0, 1.0), model(1), finite(2, f64::NAN)];
    let mut reversed = forward.clone();
    reversed.reverse();
    let a = reduce_rows(3, &forward).unwrap();
    let b = reduce_rows(3, &reversed).unwrap();
    assert_eq!((a.valid, a.invalid, a.model_failed, a.numerically_failed, a.p05_index), (1, 2, 1, 1, None));
    assert_eq!((b.valid, b.invalid, b.model_failed, b.numerically_failed, b.p05_index), (a.valid, a.invalid, a.model_failed, a.numerically_failed, a.p05_index));
    println!("S04_CASE id=T03-04-reorder valid={} invalid={} model={} numerical={} p05=absent", b.valid, b.invalid, b.model_failed, b.numerically_failed);
}

#[test]
fn invalid_sample_counts_are_preserved() {
    let faults = reduce_rows(3, &[model(0), model(1), model(2)]).unwrap();
    assert_eq!((faults.model_failed, faults.numerically_failed, faults.statistical_credit), (3, 0, false));
    let mixed = reduce_rows(4, &[finite(0, 1.0), model(1), finite(2, f64::NAN), finite(3, -2.0)]).unwrap();
    assert_eq!((mixed.attempted, mixed.valid, mixed.invalid, mixed.model_failed, mixed.numerically_failed), (4, 2, 2, 1, 1));
    assert_eq!(reduce_rows(3, &[finite(0, 1.0), finite(1, 2.0), finite(1, 3.0)]), Err(CheckedError::DuplicateSampleId));
    assert_eq!(reduce_rows(3, &[finite(0, 1.0), finite(2, 3.0)]), Err(CheckedError::Incomplete));
    let sentinel = reduce_rows(2, &rows_of(&[-1000.0, -1000.0])).unwrap();
    assert_eq!((sentinel.valid, sentinel.invalid, sentinel.model_failed, sentinel.numerically_failed), (2, 0, 0, 0));
    assert!(sentinel.statistical_credit);
    assert_eq!(sentinel.mean_ratio.unwrap().text(), "-1000/1");
    assert_eq!((sentinel.p05_index, sentinel.p95_index, sentinel.p05, sentinel.p95), (Some(0), Some(1), Some(-1000.0), Some(-1000.0)));
    assert_eq!(sentinel.finding, Finding::SupportedWithinScope);
    let zero = reduce_rows(2, &rows_of(&[0.0, -0.0])).unwrap();
    assert!(zero.statistical_credit);
    assert_eq!(zero.mean_ratio.unwrap().text(), "0/1");
}

#[test]
fn serial_double_counts_panic_and_keeps_the_positive() {
    assert_eq!(plan_ranges(5, 2), vec![(0, 3), (3, 5)]);
    let late = run_serial_double(&[1.0, 2.0, 3.0, 4.0, 5.0], 2, SerialInject { panic_at: Some(3), ..SerialInject::default() });
    assert_eq!((late.completed, late.missing, late.error, late.respawns, late.foreign_kills), (3, 2, Some(CheckedError::WorkerPanic), 0, 0));
    assert!(late.summary.is_none() && !late.statistical_credit);
    let early = run_serial_double(&[1.0, 2.0, 3.0, 4.0, 5.0], 2, SerialInject { panic_before_first_chunk: true, ..SerialInject::default() });
    assert_eq!((early.completed, early.missing, early.error), (0, 5, Some(CheckedError::WorkerPanic)));
    let lost = run_serial_double(&[1.0, 2.0, 3.0, 4.0, 5.0], 2, SerialInject { lose_worker: true, ..SerialInject::default() });
    assert_eq!(lost.error, Some(CheckedError::WorkerLost));
    assert_eq!((lost.respawns, lost.foreign_kills), (0, 0));
    let ok = run_serial_double(&[1.0, 2.0, 3.0, 4.0, 5.0], 1, SerialInject::default());
    let s = ok.summary.unwrap();
    assert!(s.statistical_credit);
    assert_eq!(s.mean_ratio.unwrap().text(), "3/1");
    assert_eq!((s.p05, s.p95), (Some(1.0), Some(5.0)));
    assert_eq!((s.p05_index, s.p95_index), (Some(0), Some(4)));
    let reversed_ok = run_serial_double(&[1.0, 2.0, 3.0, 4.0, 5.0], 2, SerialInject { reverse_chunks: true, ..SerialInject::default() });
    assert_eq!(reversed_ok.completed, 5);
    assert!(reversed_ok.statistical_credit);
    assert!(reversed_ok.error.is_none());
    let reversed = run_serial_double(&[1.0, 2.0, 3.0, 4.0, 5.0], 2, SerialInject { panic_at: Some(3), reverse_chunks: true, panic_before_first_chunk: false, ..SerialInject::default() });
    assert_eq!((reversed.completed, reversed.missing, reversed.error, reversed.respawns, reversed.foreign_kills), (0, 5, Some(CheckedError::WorkerPanic), 0, 0));
    assert!(reversed.summary.is_none() && !reversed.statistical_credit);
    assert_ne!((reversed.completed, reversed.missing), (late.completed, late.missing));
    assert!(!early.statistical_credit && early.error == Some(CheckedError::WorkerPanic));
    println!("S04_CASE id=T03-05-index p05_index={} p95_index={}", s.p05_index.unwrap(), s.p95_index.unwrap());
    println!("S04_CASE id=T03-05-reverse completed={} missing={} forward_completed={} forward_missing={} early_completed={} credit=0 respawns=0 foreign_kills=0", reversed.completed, reversed.missing, late.completed, late.missing, early.completed);
}

#[test]
fn thread_admission_and_planner_do_not_spawn() {
    let legacy = admit_threads(ThreadRequest::Legacy(7), 1, 4000).unwrap();
    assert_eq!((legacy.actual, legacy.label), (Some(1), "legacy_capped_max"));
    assert_eq!(admit_threads(ThreadRequest::Legacy(8), 1, 10_000).unwrap().actual, Some(1));
    assert_eq!(admit_threads(ThreadRequest::Legacy(0), 4, 8).unwrap().actual, Some(1));
    assert_eq!(admit_threads(ThreadRequest::Exact(0), 4, 8), Err(CheckedError::InvalidConfig));
    assert_eq!(admit_threads(ThreadRequest::Exact(4), 1, 8), Err(CheckedError::ThreadBudget));
    let exact = admit_threads(ThreadRequest::Exact(4), 4, 8).unwrap();
    assert_eq!((exact.actual, exact.label), (Some(4), "exact"));
    for n in [1usize, 2, 3] {
        assert_eq!(admit_threads(ThreadRequest::Exact(4), 4, n), Err(CheckedError::InvalidConfig));
    }
    assert_eq!(admit_threads(ThreadRequest::Exact(4), 4, 0).unwrap().actual, Some(4));
    assert_eq!(plan_ranges(8, 1), vec![(0, 8)]);
    assert_eq!(plan_ranges(8, 2), vec![(0, 4), (4, 8)]);
    assert_eq!(plan_ranges(8, 4), vec![(0, 2), (2, 4), (4, 6), (6, 8)]);
    assert_eq!(MIX_SEED_0, 0x9E37_79B9_7F4A_7C15);
    assert_eq!(MIX_SEED_1, 0xD1B5_4A32_D192_ED03);
    assert_eq!(MIX_SEED_2, 0xBF58_476D_1CE4_E5B9);
    assert_eq!(MIX_SEED_3, 0x94D0_49BB_1331_11EB);
    assert_eq!(mix_seed(99, 3), mix_seed(99, 3));
}

#[test]
fn exact_ratio_stops_at_the_half_open_i128_bound() {
    let two127 = (1u128 << 127) as f64;
    let upper = reduce_rows(1, &[finite(0, two127)]).unwrap();
    assert!(upper.statistical_credit);
    assert!(upper.mean_ratio.is_none());
    assert_eq!(upper.mean, Some(two127));
    assert_eq!(upper.sum, Some(two127));
    assert_eq!(upper.finding, Finding::SupportedWithinScope);
    let cancel = reduce_rows(3, &[finite(0, -two127), finite(1, -two127), finite(2, two127)]).unwrap();
    assert!(cancel.statistical_credit);
    assert!(cancel.mean_ratio.is_none());
    assert_eq!(cancel.sum, Some(-two127));
    assert!(cancel.mean.unwrap().is_finite());
    assert!(cancel.p05.is_some() && cancel.p95.is_some());
    let two126 = (1u128 << 126) as f64;
    let overflow = reduce_rows(2, &[finite(0, two126), finite(1, two126)]).unwrap();
    assert!(overflow.statistical_credit);
    assert!(overflow.mean_ratio.is_none());
    assert_eq!(overflow.sum, Some(two127));
    let ordinary = reduce_rows(3, &rows_of(&[-2.0, 0.0, 2.0])).unwrap();
    assert_eq!(ordinary.mean_ratio.unwrap().text(), "0/1");
    let sentinel = reduce_rows(1, &[finite(0, -1000.0)]).unwrap();
    assert_eq!(sentinel.mean_ratio.unwrap().text(), "-1000/1");
    let endpoint = reduce_rows(1, &[finite(0, -two127)]).unwrap();
    assert_eq!(endpoint.mean_ratio.unwrap().num, i128::MIN);
    assert_eq!(endpoint.mean_ratio.unwrap().den, 1);
}

#[test]
fn huge_cancellation_keeps_the_exact_power_of_two() {
    let b = f64::from_bits(0x7fe0_0000_0000_0000);
    let sum_bits = 0x7fe0_0000_0000_0000u64;
    let mean_bits = 0x7fc5_5555_5555_5555u64;
    assert_eq!(b.to_bits(), sum_bits);
    assert_eq!((b / 3.0).to_bits(), mean_bits);
    let positive = [[b, b, -b], [b, -b, b], [-b, b, b]];
    for order in positive {
        let s = reduce_rows(3, &rows_of(&order)).unwrap();
        assert_eq!((s.valid, s.invalid, s.numerically_failed, s.model_failed), (3, 0, 0, 0));
        assert!(s.statistical_credit && s.mean_ratio.is_none() && s.aggregate_error.is_none());
        assert_eq!(s.sum.unwrap().to_bits(), sum_bits);
        assert_eq!(s.mean.unwrap().to_bits(), mean_bits);
    }
    assert_eq!((-b / 3.0).to_bits(), 0xffc5_5555_5555_5555u64);
    let negative = [[-b, -b, b], [-b, b, -b], [b, -b, -b]];
    for order in negative {
        let s = reduce_rows(3, &rows_of(&order)).unwrap();
        assert_eq!((s.valid, s.invalid, s.numerically_failed, s.model_failed), (3, 0, 0, 0));
        assert!(s.statistical_credit && s.mean_ratio.is_none() && s.aggregate_error.is_none());
        assert_eq!(s.sum.unwrap().to_bits(), (-b).to_bits());
        assert_eq!(s.mean.unwrap().to_bits(), 0xffc5_5555_5555_5555u64);
    }
    let unit = f64::from_bits(1);
    let tiny = reduce_rows(1, &rows_of(&[unit])).unwrap();
    assert!(tiny.statistical_credit && tiny.aggregate_error.is_none());
    assert_eq!(tiny.sum.unwrap().to_bits(), 1);
    assert_eq!(tiny.mean.unwrap().to_bits(), 1);
    let restored = reduce_rows(3, &rows_of(&[f64::MAX, f64::MAX, -f64::MAX])).unwrap();
    assert!(restored.statistical_credit && restored.mean_ratio.is_none() && restored.aggregate_error.is_none());
    assert_eq!(restored.sum.unwrap().to_bits(), f64::MAX.to_bits());
}

#[test]
fn ratio_rejects_a_zero_denominator() {
    assert_eq!(Ratio::reduced(1, 0), Err(CheckedError::InvalidConfig));
    assert_eq!(Ratio::reduced(0, 0), Err(CheckedError::InvalidConfig));
    assert_eq!(Ratio::reduced(2, 4).unwrap().text(), "1/2");
    assert_eq!(Ratio::reduced(i128::MIN, 1).unwrap().num, i128::MIN);
}
