//! Requested-n reduction. Tails exist only when every requested sample is a finite
//! observation and the sum is representable. This module does not spawn workers.
use std::cmp::Ordering;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CheckedError {
    EmptySample,
    QuantileOverflow,
    UnrepresentableAggregate,
    DuplicateSampleId,
    Incomplete,
    WorkerPanic,
    WorkerLost,
    InvalidConfig,
    ThreadBudget,
    MismatchedSampleId,
    AuditStreamNotIndependent,
    UnsourcedCorrelation,
    RetiredLookup,
    /// A joint input was NaN or infinite. No rate is published.
    NonFiniteInput,
}

impl CheckedError {
    pub fn name(self) -> &'static str {
        match self {
            Self::EmptySample => "EmptySample",
            Self::QuantileOverflow => "QuantileOverflow",
            Self::UnrepresentableAggregate => "UnrepresentableAggregate",
            Self::DuplicateSampleId => "DuplicateSampleId",
            Self::Incomplete => "Incomplete",
            Self::WorkerPanic => "WorkerPanic",
            Self::WorkerLost => "WorkerLost",
            Self::InvalidConfig => "InvalidConfig",
            Self::ThreadBudget => "ThreadBudget",
            Self::MismatchedSampleId => "MismatchedSampleId",
            Self::AuditStreamNotIndependent => "AuditStreamNotIndependent",
            Self::UnsourcedCorrelation => "UnsourcedCorrelation",
            Self::RetiredLookup => "RetiredLookup",
            Self::NonFiniteInput => "NonFiniteInput",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Finding {
    SupportedWithinScope,
    RejectedWithinScope,
}

/// Reduced `num/den`. Zero denominator is not constructed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Ratio {
    pub num: i128,
    pub den: u64,
}

impl Ratio {
    pub fn reduced(num: i128, den: u64) -> Self {
        debug_assert!(den > 0);
        let g = gcd_u128(num.unsigned_abs(), den as u128);
        Self { num: num / g as i128, den: den / g as u64 }
    }

    pub fn text(self) -> String {
        format!("{}/{}", self.num, self.den)
    }
}

fn gcd_u128(mut a: u128, mut b: u128) -> u128 {
    while b != 0 {
        let t = a % b;
        a = b;
        b = t;
    }
    a
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Observation {
    Finite(f64),
    Model,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Row {
    pub id: u64,
    pub value: Observation,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ColumnSummary {
    pub attempted: u64,
    pub completed: u64,
    pub missing: u64,
    pub valid: u64,
    pub invalid: u64,
    pub model_failed: u64,
    pub numerically_failed: u64,
    pub statistical_credit: bool,
    pub mean_ratio: Option<Ratio>,
    pub mean: Option<f64>,
    pub sum: Option<f64>,
    pub p05_index: Option<u64>,
    pub p95_index: Option<u64>,
    pub p05: Option<f64>,
    pub p95: Option<f64>,
    pub finding: Finding,
    /// Set when every observation was finite but the sum is not a finite f64.
    pub aggregate_error: Option<CheckedError>,
}

/// `floor(n * num / den)` with a checked multiply. Allocates nothing.
pub fn quantile_index(n: u64, num: u64, den: u64) -> Result<u64, CheckedError> {
    if n == 0 || den == 0 {
        return Err(CheckedError::QuantileOverflow);
    }
    let prod = n.checked_mul(num).ok_or(CheckedError::QuantileOverflow)?;
    Ok((prod / den).min(n - 1))
}

fn integer_value(x: f64) -> Option<i128> {
    if !x.is_finite() || x.fract() != 0.0 {
        return None;
    }
    // `i128::MAX as f64` rounds up to 2^127, and `as i128` then saturates back
    // to `i128::MAX`. The positive side is half-open: [-2^127, 2^127).
    let upper = (1u128 << 127) as f64;
    if x < i128::MIN as f64 || x >= upper {
        return None;
    }
    let v = x as i128;
    if v as f64 != x {
        return None;
    }
    Some(v)
}

/// Compensated sum. The acceptance oracle is the exact f64 bits, not this name.
fn compensated_sum(xs: &[f64]) -> f64 {
    let mut sum = 0.0f64;
    let mut c = 0.0f64;
    for &x in xs {
        let t = sum + x;
        if sum.abs() >= x.abs() {
            c += (sum - t) + x;
        } else {
            c += (x - t) + sum;
        }
        sum = t;
    }
    sum + c
}

/// Reduce one column. `requested_n == 0` returns [`CheckedError::EmptySample`] and
/// does not build a sample buffer. Duplicate ids are not collapsed. A missing id
/// is [`CheckedError::Incomplete`] and is not filled with zero.
pub fn reduce_rows(requested_n: u64, rows: &[Row]) -> Result<ColumnSummary, CheckedError> {
    if requested_n == 0 {
        return Err(CheckedError::EmptySample);
    }
    if rows.len() as u64 != requested_n {
        return Err(CheckedError::Incomplete);
    }
    let n = requested_n as usize;
    let mut seen = vec![false; n];
    let mut valid_values = Vec::new();
    let mut valid = 0u64;
    let mut model_failed = 0u64;
    let mut numerically_failed = 0u64;
    for row in rows {
        if row.id >= requested_n {
            return Err(CheckedError::Incomplete);
        }
        let slot = row.id as usize;
        if seen[slot] {
            return Err(CheckedError::DuplicateSampleId);
        }
        seen[slot] = true;
        match row.value {
            Observation::Finite(x) if x.is_finite() => {
                valid += 1;
                valid_values.push(x);
            }
            Observation::Finite(_) => numerically_failed += 1,
            Observation::Model => model_failed += 1,
        }
    }
    if seen.iter().any(|s| !s) {
        return Err(CheckedError::Incomplete);
    }
    let invalid = model_failed + numerically_failed;
    debug_assert_eq!(valid + invalid, requested_n);
    let mut summary = ColumnSummary {
        attempted: requested_n,
        completed: requested_n,
        missing: 0,
        valid,
        invalid,
        model_failed,
        numerically_failed,
        statistical_credit: false,
        mean_ratio: None,
        mean: None,
        sum: None,
        p05_index: None,
        p95_index: None,
        p05: None,
        p95: None,
        finding: Finding::RejectedWithinScope,
        aggregate_error: None,
    };
    if invalid != 0 {
        return Ok(summary);
    }
    let sum = compensated_sum(&valid_values);
    if !sum.is_finite() {
        summary.aggregate_error = Some(CheckedError::UnrepresentableAggregate);
        return Ok(summary);
    }
    let mean = sum / requested_n as f64;
    if !mean.is_finite() {
        summary.aggregate_error = Some(CheckedError::UnrepresentableAggregate);
        return Ok(summary);
    }
    let p05_index = quantile_index(requested_n, 5, 100)?;
    let p95_index = quantile_index(requested_n, 95, 100)?;
    let mut ordered = valid_values;
    ordered.sort_by(|a, b| a.partial_cmp(b).unwrap_or(Ordering::Equal));
    let mut ratio = None;
    if let Some(total) = ordered.iter().try_fold(0i128, |acc, x| integer_value(*x).and_then(|v| acc.checked_add(v))) {
        ratio = Some(Ratio::reduced(total, requested_n));
    }
    summary.statistical_credit = true;
    summary.mean_ratio = ratio;
    summary.mean = Some(mean);
    summary.sum = Some(sum);
    summary.p05_index = Some(p05_index);
    summary.p95_index = Some(p95_index);
    summary.p05 = Some(ordered[p05_index as usize]);
    summary.p95 = Some(ordered[p95_index as usize]);
    summary.finding = Finding::SupportedWithinScope;
    Ok(summary)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ThreadRequest {
    Exact(usize),
    Legacy(usize),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ThreadPlan {
    pub requested: usize,
    pub admitted: usize,
    pub actual: Option<usize>,
    pub label: &'static str,
}

/// Legacy clamps. Exact does not. Exact(0) is [`CheckedError::InvalidConfig`].
/// A request above the admission is [`CheckedError::ThreadBudget`] and wins over
/// the sample-count check. Exact(k) above a nonempty `n` is
/// [`CheckedError::InvalidConfig`] before any worker is planned; `n == 0` is not
/// rewritten here.
pub fn admit_threads(request: ThreadRequest, admitted: usize, n: usize) -> Result<ThreadPlan, CheckedError> {
    match request {
        ThreadRequest::Exact(0) => Err(CheckedError::InvalidConfig),
        ThreadRequest::Exact(k) if k > admitted => Err(CheckedError::ThreadBudget),
        ThreadRequest::Exact(k) if n > 0 && k > n => Err(CheckedError::InvalidConfig),
        ThreadRequest::Exact(k) => Ok(ThreadPlan { requested: k, admitted, actual: Some(k), label: "exact" }),
        ThreadRequest::Legacy(requested) => {
            let actual = requested.max(1).min(admitted).min(n);
            Ok(ThreadPlan { requested, admitted, actual: Some(actual), label: "legacy_capped_max" })
        }
    }
}

pub fn legacy_sample_count(n: usize) -> (usize, &'static str) {
    (n.max(1), "legacy_unqualified")
}

/// Same split as the legacy column runner: the first `n % threads` chunks take one extra.
/// This planner does not spawn a worker. It is not the 1/2/4 replay.
pub fn plan_ranges(n: usize, threads: usize) -> Vec<(usize, usize)> {
    let threads = threads.max(1).min(n.max(1));
    let mut out = Vec::with_capacity(threads);
    let mut start = 0usize;
    for t in 0..threads {
        let count = n / threads + usize::from(t < n % threads);
        out.push((start, start + count));
        start += count;
    }
    out
}

#[derive(Clone, Copy, Debug, Default)]
pub struct SerialInject {
    pub panic_at: Option<u64>,
    pub panic_before_first_chunk: bool,
    pub lose_worker: bool,
}

#[derive(Clone, Debug)]
pub struct SerialOutcome {
    pub attempted: u64,
    pub completed: u64,
    pub missing: u64,
    pub statistical_credit: bool,
    pub summary: Option<ColumnSummary>,
    pub error: Option<CheckedError>,
    pub respawns: u32,
    pub foreign_kills: u32,
}

/// Fixed serial double. A panic or a lost worker publishes no tails and does not respawn.
pub fn run_serial_double(values: &[f64], threads: usize, inject: SerialInject) -> SerialOutcome {
    let attempted = values.len() as u64;
    let fail = |completed, error| SerialOutcome {
        attempted,
        completed,
        missing: attempted - completed,
        statistical_credit: false,
        summary: None,
        error: Some(error),
        respawns: 0,
        foreign_kills: 0,
    };
    if inject.lose_worker {
        return fail(0, CheckedError::WorkerLost);
    }
    if inject.panic_before_first_chunk {
        return fail(0, CheckedError::WorkerPanic);
    }
    let mut completed = 0u64;
    let ranges = if values.is_empty() { Vec::new() } else { plan_ranges(values.len(), threads.max(1)) };
    for (start, end) in ranges {
        for i in start..end {
            if inject.panic_at == Some(i as u64) {
                return fail(completed, CheckedError::WorkerPanic);
            }
            completed += 1;
        }
    }
    let rows: Vec<Row> = values.iter().enumerate().map(|(id, v)| Row { id: id as u64, value: Observation::Finite(*v) }).collect();
    match reduce_rows(attempted, &rows) {
        Ok(summary) => SerialOutcome {
            attempted,
            completed,
            missing: 0,
            statistical_credit: summary.statistical_credit,
            error: summary.aggregate_error,
            summary: Some(summary),
            respawns: 0,
            foreign_kills: 0,
        },
        Err(error) => fail(completed, error),
    }
}
