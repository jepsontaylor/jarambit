//! Paired joint outcomes, population-shift accounting, and retired cut-media lookup.
//! Joint pass is `value > 0` on the original row. Columns are not sorted before pairing.
use crate::stats::{CheckedError, Ratio};

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Pair {
    pub id: u64,
    pub a: f64,
    pub b: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Count {
    pub passes: u64,
    pub n: u64,
}

impl Count {
    pub fn text(self) -> String {
        format!("{}/{}", self.passes, self.n)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct JointEstimate {
    pub joint: Count,
    pub marginal_a: Count,
    pub marginal_b: Count,
    /// Marginal product. This is `assumed_independent` and does not replace `joint`.
    pub product: Ratio,
    pub product_label: &'static str,
}

fn pass(x: f64) -> bool {
    x > 0.0
}

/// Position-aligned pairs. A second column whose ids are a permutation is
/// [`CheckedError::MismatchedSampleId`] and publishes no joint. A nonfinite
/// value on either side is [`CheckedError::NonFiniteInput`] and publishes no
/// joint, marginal, or product. [`joint_columns`] uses this same check.
pub fn paired_joint(rows: &[Pair]) -> Result<JointEstimate, CheckedError> {
    let n = rows.len() as u64;
    if n == 0 {
        return Err(CheckedError::EmptySample);
    }
    let mut seen = Vec::with_capacity(rows.len());
    let mut joint = 0u64;
    let mut ma = 0u64;
    let mut mb = 0u64;
    for row in rows {
        if !row.a.is_finite() || !row.b.is_finite() {
            return Err(CheckedError::NonFiniteInput);
        }
        if seen.contains(&row.id) {
            return Err(CheckedError::DuplicateSampleId);
        }
        seen.push(row.id);
        if pass(row.a) {
            ma += 1;
        }
        if pass(row.b) {
            mb += 1;
        }
        if pass(row.a) && pass(row.b) {
            joint += 1;
        }
    }
    Ok(JointEstimate {
        joint: Count { passes: joint, n },
        marginal_a: Count { passes: ma, n },
        marginal_b: Count { passes: mb, n },
        product: Ratio::reduced((ma as i128) * (mb as i128), n * n),
        product_label: "assumed_independent",
    })
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ColumnSample {
    pub id: u64,
    pub value: f64,
}

pub fn joint_columns(a: &[ColumnSample], b: &[ColumnSample]) -> Result<JointEstimate, CheckedError> {
    if a.len() != b.len() || a.is_empty() {
        return Err(CheckedError::MismatchedSampleId);
    }
    let mut rows = Vec::with_capacity(a.len());
    for (left, right) in a.iter().zip(b.iter()) {
        if left.id != right.id {
            return Err(CheckedError::MismatchedSampleId);
        }
        rows.push(Pair { id: left.id, a: left.value, b: right.value });
    }
    paired_joint(&rows)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Shift {
    pub service: Ratio,
    pub discovery: Ratio,
    pub gap: Ratio,
    pub label: &'static str,
    pub mc_error: u64,
}

/// Service `k/(10k)`, discovery `5k/(10k)`, gap `2/5`. The pooled `3/10` is not the service rate.
/// A fully enumerated finite list has Monte Carlo error 0 and does not erase the gap.
/// Zero and a `10k` or `5k` overflow return [`CheckedError::InvalidConfig`] before a ratio
/// is constructed. [`Ratio::reduced`] still requires a positive denominator.
pub fn population_shift(k: u64) -> Result<Shift, CheckedError> {
    if k == 0 {
        return Err(CheckedError::InvalidConfig);
    }
    let den = k.checked_mul(10).ok_or(CheckedError::InvalidConfig)?;
    let discovered = k.checked_mul(5).ok_or(CheckedError::InvalidConfig)?;
    Ok(Shift {
        service: Ratio::reduced(k as i128, den),
        discovery: Ratio::reduced(i128::from(discovered), den),
        gap: Ratio::reduced(2, 5),
        label: "assumed_model_population_discrepancy",
        mc_error: 0,
    })
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct AuditIds {
    pub search: u64,
    pub calibration: u64,
    pub final_audit: u64,
}

/// Distinct stream ids only. This does not prove statistical independence.
pub fn check_audit_ids(ids: AuditIds) -> Result<(), CheckedError> {
    if ids.search == ids.calibration || ids.search == ids.final_audit || ids.calibration == ids.final_audit {
        Err(CheckedError::AuditStreamNotIndependent)
    } else {
        Ok(())
    }
}

/// Common random numbers are a different role from [`AuditIds::final_audit`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CommonRandomNumbers {
    pub stream: u64,
}

pub fn accept_sourced_correlation(sourced: bool) -> Result<(), CheckedError> {
    if sourced { Ok(()) } else { Err(CheckedError::UnsourcedCorrelation) }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct HistoricalMedium {
    pub work: f64,
    pub lead: f64,
    pub edge: f64,
    pub label: &'static str,
}

pub fn historical_medium(token: &str) -> Option<HistoricalMedium> {
    let (work, lead, edge) = match token {
        "wood" => (100.0, 0.35, 0.35),
        "cord" => (70.0, 0.85, 0.55),
        "hide" => (45.0, 0.90, 0.50),
        "muscle" => (90.0, 0.70, 0.55),
        "bone" => (160.0, 0.20, 0.25),
        "gel" => (60.0, 0.50, 0.30),
        _ => return None,
    };
    Some(HistoricalMedium { work, lead, edge, label: "model_retired" })
}

/// Current populations do not draw a cut medium. This does not call `media_sample` or `cut_margin`.
pub fn active_cut_medium() -> Result<HistoricalMedium, CheckedError> {
    Err(CheckedError::RetiredLookup)
}
