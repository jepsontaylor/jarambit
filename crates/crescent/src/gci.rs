//! Checked relative 3-mesh Grid Convergence Index (Roache GCI) in native Rust
//! (`fem_solid/gci.py`, `METHOD = "relative_gci.v2"`), plus in-process 3-level
//! (`0.25, 1.0, 4.0 mm^2`) plate GCI evaluation.

use crate::{aesthetic, fem, genome::Genome, pheno};
use jarambit_evidence::identity::{is_hash, unique_ids, ContentRef};
use jarambit_physics::{floors, material};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

pub const METHOD: &str = "relative_gci.v2";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum FitStatus {
    #[serde(rename = "admissible_estimate")]
    Valid,
    #[serde(rename = "invalid_input")]
    Invalid,
    #[serde(rename = "unresolved")]
    Unresolved,
    #[serde(rename = "precision_limited")]
    Precision,
    #[serde(rename = "oscillatory")]
    Oscillatory,
    #[serde(rename = "nonpositive_order")]
    Nonpositive,
    #[serde(rename = "unsupported_sequence")]
    Unsupported,
}

impl FitStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Valid => "admissible_estimate",
            Self::Invalid => "invalid_input",
            Self::Unresolved => "unresolved",
            Self::Precision => "precision_limited",
            Self::Oscillatory => "oscillatory",
            Self::Nonpositive => "nonpositive_order",
            Self::Unsupported => "unsupported_sequence",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct MeshRef {
    pub id: String,
    pub revision: String,
    pub sha256: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Observable {
    pub id: String,
    pub units: String,
    pub region: String,
    pub projection: String,
    pub metric: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Level {
    pub mesh: MeshRef,
    pub h: f64,
    pub observable: Observable,
    pub refinement: String,
}

impl Level {
    pub fn new(mesh: MeshRef, h: f64, observable: Observable) -> Self {
        Self {
            mesh,
            h,
            observable,
            refinement: "uniform_h".to_string(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Estimate {
    pub fit_status: FitStatus,
    pub reason: String,
    pub p: Option<f64>,
    pub f_ext: Option<f64>,
    pub gci_fine: Option<f64>,
    pub monotone: bool,
    pub sequence_valid: bool,
    pub observable_valid: bool,
    pub method_id: String,
    pub asymptotic_validation: String,
    pub levels: Vec<Level>,
}

/// IEEE-754 unit in the last place (`math.ulp(x)` parity).
pub fn ulp(x: f64) -> f64 {
    if !x.is_finite() {
        return f64::NAN;
    }
    let ax = x.abs();
    if ax == 0.0 {
        return f64::from_bits(1);
    }
    if ax == f64::MAX {
        return ax - f64::from_bits(ax.to_bits() - 1);
    }
    f64::from_bits(ax.to_bits() + 1) - ax
}

pub fn validate_sequence(levels: &[Level], r: f64) -> Option<&'static str> {
    if levels.len() != 3 {
        return Some("three_ordered_levels_required");
    }
    if !r.is_finite() || r <= 1.0 {
        return Some("invalid_refinement_ratio");
    }
    if unique_ids(levels.iter().map(|x| x.mesh.id.as_str())).is_err() {
        return Some("invalid_mesh_sequence");
    }
    for x in levels {
        if unique_ids([x.mesh.revision.as_str()]).is_err() || !is_hash(&x.mesh.sha256) {
            return Some("invalid_mesh_sequence");
        }
        for field in [
            x.observable.id.as_str(),
            x.observable.units.as_str(),
            x.observable.region.as_str(),
            x.observable.projection.as_str(),
            x.observable.metric.as_str(),
        ] {
            if unique_ids([field]).is_err() {
                return Some("invalid_mesh_sequence");
            }
        }
    }
    let shas: std::collections::BTreeSet<&str> =
        levels.iter().map(|x| x.mesh.sha256.as_str()).collect();
    if shas.len() != 3 {
        return Some("duplicate_mesh_content");
    }
    let h: Vec<f64> = levels.iter().map(|x| x.h).collect();
    if h.iter().any(|v| !v.is_finite()) {
        return Some("invalid_mesh_sequence");
    }
    if !(0.0 < h[0] && h[0] < h[1] && h[1] < h[2]) {
        return Some("invalid_level_order");
    }
    if levels.iter().any(|x| x.refinement != "uniform_h") {
        return Some("unsupported_refinement");
    }
    if h[1] / h[0] != r || h[2] / h[1] != r {
        return Some("nonuniform_refinement");
    }
    if levels[1..].iter().any(|x| x.observable != levels[0].observable) {
        return Some("observable_mismatch");
    }
    None
}

impl Estimate {
    fn base(status: FitStatus, reason: &str, levels: Option<&[Level]>) -> Self {
        Self {
            fit_status: status,
            reason: reason.to_string(),
            p: None,
            f_ext: None,
            gci_fine: None,
            monotone: false,
            sequence_valid: levels.is_some(),
            observable_valid: levels.is_some(),
            method_id: METHOD.to_string(),
            asymptotic_validation: "not_established".to_string(),
            levels: levels.map(|l| l.to_vec()).unwrap_or_default(),
        }
    }

    pub fn relative_error_available(&self) -> bool {
        let (Some(p), Some(f_ext), Some(err)) = (self.p, self.f_ext, self.gci_fine) else {
            return false;
        };
        p.is_finite()
            && f_ext.is_finite()
            && err.is_finite()
            && self.method_id == METHOD
            && self.fit_status == FitStatus::Valid
            && self.monotone
            && p > 0.0
            && err >= 0.0
    }

    pub fn admitted(&self) -> bool {
        if !(self.relative_error_available() && self.sequence_valid && self.observable_valid) {
            return false;
        }
        if self.levels.len() != 3 || !self.levels[0].h.is_finite() || self.levels[0].h == 0.0 {
            return false;
        }
        let r = self.levels[1].h / self.levels[0].h;
        validate_sequence(&self.levels, r).is_none()
    }

    pub fn to_json(&self) -> Value {
        json!({
            "admitted": self.admitted(),
            "asymptotic_validation": self.asymptotic_validation,
            "f_ext": self.f_ext,
            "fit_status": self.fit_status.as_str(),
            "gci_fine": self.gci_fine,
            "levels": self.levels,
            "method_id": self.method_id,
            "monotone": self.monotone,
            "observable_valid": self.observable_valid,
            "p": self.p,
            "reason": self.reason,
            "relative_error_available": self.relative_error_available(),
            "sequence_valid": self.sequence_valid,
        })
    }
}

/// Compute checked relative GCI from `(f1, f2, f3)` (finest, middle, coarse).
pub fn compute_gci(
    f1: f64,
    f2: f64,
    f3: f64,
    r: f64,
    fs: f64,
    levels: Option<&[Level]>,
) -> Estimate {
    if ![f1, f2, f3, r, fs].iter().all(|v| v.is_finite()) {
        return Estimate::base(FitStatus::Invalid, "nonfinite_or_invalid_scalar", None);
    }
    if r <= 1.0 || fs <= 0.0 {
        return Estimate::base(FitStatus::Invalid, "invalid_ratio_or_safety_factor", None);
    }
    if let Some(lv) = levels {
        if let Some(reason) = validate_sequence(lv, r) {
            return Estimate::base(FitStatus::Unsupported, reason, None);
        }
    }
    let e21 = f2 - f1;
    let e32 = f3 - f2;
    if !e21.is_finite() || !e32.is_finite() {
        return Estimate::base(FitStatus::Invalid, "nonfinite_difference", levels);
    }
    if e21 == 0.0 && e32 == 0.0 {
        return Estimate::base(FitStatus::Unresolved, "all_levels_equal", levels);
    }
    if e21 == 0.0 {
        return Estimate::base(FitStatus::Unresolved, "fine_pair_plateau", levels);
    }
    if e32 == 0.0 {
        return Estimate::base(FitStatus::Unresolved, "coarse_pair_plateau", levels);
    }
    for (a, b, diff) in [(f1, f2, e21), (f2, f3, e32)] {
        if diff.abs() <= 16.0 * ulp(a).max(ulp(b)) {
            return Estimate::base(FitStatus::Precision, "pair_at_precision_floor", levels);
        }
    }
    if f1 == 0.0 {
        return Estimate::base(FitStatus::Unresolved, "zero_reference_quantity", levels);
    }
    if (e21 < 0.0) != (e32 < 0.0) {
        return Estimate::base(FitStatus::Oscillatory, "oscillatory_sequence", levels);
    }
    let quotient = (e32 / e21).abs();
    if !quotient.is_finite() || quotient == 0.0 {
        return Estimate::base(FitStatus::Invalid, "unrepresentable_difference_ratio", levels);
    }
    let p = quotient.ln() / r.ln();
    if !p.is_finite() {
        return Estimate::base(FitStatus::Invalid, "nonfinite_observed_order", levels);
    }
    if p <= 0.0 {
        let mut est = Estimate::base(FitStatus::Nonpositive, "nonpositive_observed_order", levels);
        est.p = Some(p);
        est.monotone = true;
        return est;
    }
    let denominator = (p * r.ln()).exp_m1();
    if !denominator.is_finite() || denominator <= 0.0 {
        let mut est = Estimate::base(
            FitStatus::Unresolved,
            "invalid_extrapolation_denominator",
            levels,
        );
        est.p = Some(p);
        est.monotone = true;
        return est;
    }
    let extrapolated = f1 - e21 / denominator;
    let error = fs * (e21 / f1).abs() / denominator;
    if !extrapolated.is_finite() || !error.is_finite() || error < 0.0 {
        let mut est = Estimate::base(
            FitStatus::Unresolved,
            "unrepresentable_error_estimate",
            levels,
        );
        est.p = Some(p);
        est.monotone = true;
        return est;
    }
    if error == 0.0 {
        let mut est = Estimate::base(FitStatus::Precision, "relative_error_underflow", levels);
        est.p = Some(p);
        est.monotone = true;
        return est;
    }
    let mut est = Estimate::base(
        FitStatus::Valid,
        if levels.is_none() {
            "arithmetic_only"
        } else {
            "checked_relative_estimate"
        },
        levels,
    );
    est.p = Some(p);
    est.f_ext = Some(extrapolated);
    est.gci_fine = Some(error);
    est.monotone = true;
    est
}

fn sha256_hex(bytes: &[u8]) -> String {
    ContentRef::from_bytes("x", "rev1", bytes).sha256
}

fn mesh_hash(xy: &[(f64, f64)], tris: &[[usize; 3]], te: &[f64]) -> String {
    let mut buf = Vec::with_capacity(xy.len() * 16 + tris.len() * 24 + te.len() * 8);
    for &(x, y) in xy {
        buf.extend_from_slice(&x.to_le_bytes());
        buf.extend_from_slice(&y.to_le_bytes());
    }
    for &[a, b, c] in tris {
        buf.extend_from_slice(&(a as u64).to_le_bytes());
        buf.extend_from_slice(&(b as u64).to_le_bytes());
        buf.extend_from_slice(&(c as u64).to_le_bytes());
    }
    for &t in te {
        buf.extend_from_slice(&t.to_le_bytes());
    }
    sha256_hex(&buf)
}

/// Run the 3-level (`0.25, 1.0, 4.0 mm^2` -> `h = 0.5, 1.0, 2.0 mm`, `r = 2.0`) plate GCI
/// evaluation in-process and return the complete `jarambit.plate_gci.v1` JSON document.
pub fn run_plate_gci_3level(
    subject: &str,
    genome_rel: &str,
    genome_sha256: &str,
    g: &Genome,
) -> Option<Value> {
    let p = pheno::build(g);
    let m = material(p.mat);
    let jk2 = fem::joint_k(m, p.t_joint, 2);

    let levels_spec = [(0.25f64, 0.5f64), (1.0f64, 1.0f64), (4.0f64, 2.0f64)];
    let mut levels_raw = Vec::with_capacity(3);
    let mut seq_vals = [0.0f64; 3];
    let mut sf_vals = [0.0f64; 3];
    let mut l_seq = Vec::with_capacity(3);
    let mut l_sf = Vec::with_capacity(3);

    let obs_seq = Observable {
        id: "plate_seq_ratio".into(),
        metric: "seq_ratio".into(),
        region: "blade_vs_ring_neck".into(),
        projection: "plate_cst_dkt".into(),
        units: "ratio".into(),
    };
    let obs_sf = Observable {
        id: "plate_sf_hunter".into(),
        metric: "sf_hunter".into(),
        region: "blade_outside_4mm".into(),
        projection: "plate_cst_dkt".into(),
        units: "ratio".into(),
    };

    for (idx, (max_area, h_mm)) in levels_spec.into_iter().enumerate() {
        let (f, fl) = fem::report_fields(&p, max_area)?;
        let m_sha = mesh_hash(&fl.xy, &fl.tris, &fl.te);
        let sf_hunter = (f.lat20 * jk2) / floors::HUNTER_LATERAL_N;
        seq_vals[idx] = f.seq_ratio;
        sf_vals[idx] = sf_hunter;
        levels_raw.push(json!({
            "h_mm": h_mm,
            "lat20_n": f.lat20,
            "max_area_mm2": max_area,
            "mesh_sha256": m_sha,
            "n_elem": fl.tris.len(),
            "n_node": fl.xy.len(),
            "seq_ratio": f.seq_ratio,
            "sf_hunter": sf_hunter,
        }));
        let m_ref = MeshRef {
            id: format!("{subject}_area_{max_area}"),
            revision: "rev1".into(),
            sha256: m_sha,
        };
        l_seq.push(Level::new(m_ref.clone(), h_mm, obs_seq.clone()));
        l_sf.push(Level::new(m_ref, h_mm, obs_sf.clone()));
    }

    let aes = aesthetic::evaluate(g, &p);
    let seq_res = compute_gci(seq_vals[0], seq_vals[1], seq_vals[2], 2.0, 1.25, Some(&l_seq)).to_json();
    let sf_res = compute_gci(sf_vals[0], sf_vals[1], sf_vals[2], 2.0, 1.25, Some(&l_sf)).to_json();

    Some(json!({
        "schema": "jarambit.plate_gci.v1",
        "subject": subject,
        "genome": genome_rel,
        "genome_sha256": genome_sha256,
        "karambit": {
            "ring_id_mm": p.ring_id,
            "ring_wall_mm": g.v[crate::genome::RING_WALL],
            "groove_w_mm": p.groove_w,
            "groove_area_mm2": p.groove_area,
            "hook_drop_mm": aes.hook_drop,
            "inside_concave": aes.inside_concave,
            "spine_convex": aes.spine_convex,
            "seat_depth_mm": aes.seat_depth,
            "lobe_prom_mm": aes.lobe_prom,
            "teeth_in": p.teeth_in,
            "teeth_sp": p.teeth_sp,
            "tip_to_heel_mm": p.blade.tip_to_heel,
            "horizontal_reach_mm": p.blade.horizontal_reach,
            "sharpened_arc_mm": p.blade.sharpened_arc,
            "grip_len_mm": p.grip_len,
            "aes_score": aes.score,
            "aes_pass": aes.pass,
        },
        "primary_observable": "seq_ratio",
        "refinement_ratio_r": 2.0,
        "levels_fine_to_coarse": levels_raw,
        "seq_ratio_gci": seq_res,
        "sf_hunter_gci": sf_res,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn demo_levels() -> Vec<Level> {
        let obs = Observable {
            id: "seq".into(),
            units: "ratio".into(),
            region: "blade".into(),
            projection: "plate".into(),
            metric: "seq_ratio".into(),
        };
        vec![
            Level::new(
                MeshRef {
                    id: "m1".into(),
                    revision: "r1".into(),
                    sha256: "a".repeat(64),
                },
                0.5,
                obs.clone(),
            ),
            Level::new(
                MeshRef {
                    id: "m2".into(),
                    revision: "r1".into(),
                    sha256: "b".repeat(64),
                },
                1.0,
                obs.clone(),
            ),
            Level::new(
                MeshRef {
                    id: "m3".into(),
                    revision: "r1".into(),
                    sha256: "c".repeat(64),
                },
                2.0,
                obs,
            ),
        ]
    }

    #[test]
    fn gci_admits_monotone_positive_order_sequence() {
        let lv = demo_levels();
        let est = compute_gci(1.20, 1.22, 1.26, 2.0, 1.25, Some(&lv));
        assert_eq!(est.fit_status, FitStatus::Valid);
        assert!(est.admitted());
        assert!((est.p.unwrap() - 1.0).abs() < 1e-12);
        assert!((est.f_ext.unwrap() - 1.18).abs() < 1e-12);
    }

    #[test]
    fn gci_detects_oscillatory_and_precision_floor() {
        let lv = demo_levels();
        let osc = compute_gci(1.20, 1.18, 1.21, 2.0, 1.25, Some(&lv));
        assert_eq!(osc.fit_status, FitStatus::Oscillatory);
        assert!(!osc.admitted());

        let prec = compute_gci(1.0, 1.0 + ulp(1.0), 1.0 + 4.0 * ulp(1.0), 2.0, 1.25, Some(&lv));
        assert_eq!(prec.fit_status, FitStatus::Precision);
        assert!(!prec.admitted());
    }
}
