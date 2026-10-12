//! PR-0.28.3: serde-typed evaluation record (`all_evals.json`, plate `metrics`, report lines).
//! A missing FEM result is `null` plus `fem_status`, never a silent `Fem::default()` zero; every
//! non-finite scalar is `null`; keys are unique (the duplicate `pry20` of the hand-formatted record is gone).
use crate::fem::Fem;
use crate::genome::*;
use crate::qd::{self, Rec};
use serde::Serialize;

/// Why the FEM block is (or is not) populated.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FemStatus {
    /// Rejected by the aesthetic floor or a hard gate before FEM ran: every FEM metric is null.
    NotEvaluated,
    /// FEM was attempted (aesthetic + gates passed) but returned no result (mesh/solve failure).
    Failed,
    /// FEM ran but at least one reported scalar is non-finite (those are null).
    Incomplete,
    /// FEM ran and every reported scalar is finite.
    Complete,
}

/// Round to `d` decimals; non-finite -> None (serialised as null).
pub fn fin(x: f64, d: i32) -> Option<f64> { if x.is_finite() { let k = 10f64.powi(d); Some((x * k).round() / k) } else { None } }

#[derive(Debug, Serialize)]
pub struct FemJson {
    pub lat20: Option<f64>, pub lat_rob: Option<f64>, pub ring20: Option<f64>, pub ring_rob: Option<f64>, pub pry20: Option<f64>, pub twist20_nmm: Option<f64>,
    pub sf_hiker: Option<f64>, pub sf_hunter: Option<f64>, pub sf_ring: Option<f64>, pub floors_ok: bool, pub lat_at: [Option<f64>; 2],
    pub seq_ratio: Option<f64>, pub seq_case: String, pub twist_tip_sf: Option<f64>, pub twist_tip_joint3d_nmm: Option<f64>, pub twist_tip_peak_tipdist: Option<f64>,
    pub twist_body_sf: Option<f64>, pub twist_tipzone_sf: Option<f64>,
}
impl FemJson {
    pub fn from_fem(f: &Fem) -> Self {
        FemJson { lat20: fin(f.lat20, 1), lat_rob: fin(f.lat_rob, 1), ring20: fin(f.ring20, 1), ring_rob: fin(f.ring_rob, 1), pry20: fin(f.pry20, 1), twist20_nmm: fin(f.twist20_nmm, 1),
            sf_hiker: fin(f.sf_hiker, 3), sf_hunter: fin(f.sf_hunter, 3), sf_ring: fin(f.sf_ring, 3), floors_ok: f.floors_ok, lat_at: [fin(f.lat_at.0, 2), fin(f.lat_at.1, 2)],
            seq_ratio: fin(f.seq_ratio, 3), seq_case: f.seq_case.to_string(), twist_tip_sf: fin(f.twist_sf, 3), twist_tip_joint3d_nmm: fin(f.twist_joint_nmm, 0),
            twist_tip_peak_tipdist: fin(f.twist_tipdist, 1), twist_body_sf: fin(f.twist_body_sf, 3), twist_tipzone_sf: fin(f.twist_tipzone_sf, 3) }
    }
    fn all_finite(f: &Fem) -> bool {
        [f.lat20, f.lat_rob, f.ring20, f.ring_rob, f.pry20, f.twist20_nmm, f.sf_hiker, f.sf_hunter, f.sf_ring, f.lat_at.0, f.lat_at.1, f.seq_ratio, f.twist_sf,
         f.twist_joint_nmm, f.twist_tipdist, f.twist_body_sf, f.twist_tipzone_sf].iter().all(|x| x.is_finite())
    }
}

/// One evaluation. Flat key layout kept compatible with the pre-0.28.3 readers (FEM metrics at top level).
#[derive(Debug, Serialize)]
pub struct RecJson {
    pub id: usize, pub gen: usize, pub fit: Option<f64>, pub spg: Option<f64>, pub mass_g: Option<f64>, pub blank_g: Option<f64>, pub t: Option<f64>, pub material: String,
    pub tip_to_heel: Option<f64>, pub horizontal_reach: Option<f64>, pub arc_in: Option<f64>, pub arc_sp: Option<f64>, pub grip: Option<f64>,
    pub aes_score: Option<f64>, pub aes_pass: bool, pub hausdorff: Option<f64>, pub emd: Option<f64>, pub straight_mm: Option<f64>, pub min_blend_r: Option<f64>, pub novelty: Option<f64>,
    pub fem_status: FemStatus,
    #[serde(flatten)] pub fem: FemFlat,
    pub holder_box: [Option<f64>; 3], pub removed_mm3: Vec<Option<f64>>, pub min_web: Option<f64>, pub n_win: usize, pub win_area: Option<f64>, pub n_perf: usize, pub perf_area: Option<f64>,
    pub relief_frac: Option<f64>, pub rejects: Vec<String>, pub aes_fails: Vec<String>, pub legal: bool, pub t_joint: Option<f64>, pub p1: bool,
    pub rail_w: Option<f64>, pub neck_l: Option<f64>, pub pocket_d: Option<f64>, pub pocket_r: Option<f64>, pub knots: Vec<Option<f64>>,
    /// PR-0.29.1 lineage
    pub parents: Vec<usize>, pub op: String, pub op_version: u32,
}

/// FEM metrics flattened into the record; every field null when there is no FEM result.
#[derive(Debug, Default, Serialize)]
pub struct FemFlat {
    pub lat20: Option<f64>, pub lat_rob: Option<f64>, pub ring20: Option<f64>, pub ring_rob: Option<f64>, pub pry20: Option<f64>, pub twist20_nmm: Option<f64>,
    pub sf_hiker: Option<f64>, pub sf_hunter: Option<f64>, pub sf_ring: Option<f64>, pub floors_ok: Option<bool>, pub lat_at: Option<[Option<f64>; 2]>,
    pub seq_ratio: Option<f64>, pub seq_case: Option<String>, pub twist_tip_sf: Option<f64>, pub twist_tip_joint3d_nmm: Option<f64>, pub twist_tip_peak_tipdist: Option<f64>,
    pub twist_body_sf: Option<f64>, pub twist_tipzone_sf: Option<f64>,
}
impl From<FemJson> for FemFlat {
    fn from(f: FemJson) -> Self {
        FemFlat { lat20: f.lat20, lat_rob: f.lat_rob, ring20: f.ring20, ring_rob: f.ring_rob, pry20: f.pry20, twist20_nmm: f.twist20_nmm, sf_hiker: f.sf_hiker, sf_hunter: f.sf_hunter,
            sf_ring: f.sf_ring, floors_ok: Some(f.floors_ok), lat_at: Some(f.lat_at), seq_ratio: f.seq_ratio, seq_case: Some(f.seq_case), twist_tip_sf: f.twist_tip_sf,
            twist_tip_joint3d_nmm: f.twist_tip_joint3d_nmm, twist_tip_peak_tipdist: f.twist_tip_peak_tipdist, twist_body_sf: f.twist_body_sf, twist_tipzone_sf: f.twist_tipzone_sf }
    }
}

pub fn fem_status(r: &Rec) -> FemStatus {
    match &r.fem {
        None if r.aes.pass && r.rejects.is_empty() => FemStatus::Failed,
        None => FemStatus::NotEvaluated,
        Some(f) if FemJson::all_finite(f) => FemStatus::Complete,
        Some(_) => FemStatus::Incomplete,
    }
}

impl RecJson {
    pub fn from_rec(r: &Rec) -> Self {
        let fem = r.fem.as_ref().map(|f| FemFlat::from(FemJson::from_fem(f))).unwrap_or_else(FemFlat::default);
        let has_fem = r.fem.is_some();
        RecJson {
            id: r.id, gen: r.gen, fit: fin(r.fit, 5), spg: if has_fem { fin(r.spg, 5) } else { None }, mass_g: fin(r.mass_g, 3), blank_g: fin(r.blank_g, 3), t: fin(r.t, 1),
            material: r.g.mat.name().to_string(), tip_to_heel: fin(r.blade.tip_to_heel, 3), horizontal_reach: fin(r.blade.horizontal_reach, 3), arc_in: fin(r.blade.arc_in, 3),
            arc_sp: fin(r.blade.arc_sp, 3), grip: fin(r.grip, 2), aes_score: fin(r.aes.score, 4), aes_pass: r.aes.pass, hausdorff: fin(r.aes.hausdorff, 3), emd: fin(r.aes.emd, 4),
            straight_mm: fin(r.aes.straight_mm, 2), min_blend_r: fin(r.aes.min_concave_r, 2), novelty: fin(r.novelty, 4), fem_status: fem_status(r), fem,
            holder_box: [fin(r.holder_lw.0, 1), fin(r.holder_lw.1, 1), fin(r.holder_lw.2, 1)], removed_mm3: r.removed.iter().map(|&x| fin(x, 4)).collect(),
            min_web: fin(r.min_web, 2), n_win: r.n_win, win_area: fin(r.win_area, 2), n_perf: r.n_perf, perf_area: fin(r.perf_area, 2), relief_frac: fin(qd::relief_frac(r), 5),
            rejects: r.rejects.clone(), aes_fails: r.aes.fails.clone(), legal: r.legal(), t_joint: fin(r.g.t_joint(), 3), p1: r.g.p1(),
            rail_w: fin(r.g.v[RAIL_W], 2), neck_l: fin(r.g.v[NECK_L], 2), pocket_d: fin(r.g.v[POCKET_D], 3), pocket_r: fin(r.g.v[POCKET_R], 2),
            knots: (0..if r.g.p1() { r.g.k_n() } else { 1 }).map(|k| fin(r.g.v[K0 + k], 4)).collect(),
            parents: r.parents.clone(), op: r.op.to_string(), op_version: r.op_version,
        }
    }
}

/// Strict JSON for one record (serde_json: unique keys, no NaN/inf, proper string escaping).
pub fn rec_json(r: &Rec) -> String { serde_json::to_string(&RecJson::from_rec(r)).expect("RecJson serialises") }

/// Optional FEM scalar for CSV cells: empty when there is no FEM result or the value is non-finite.
pub fn csv_opt(f: Option<&Fem>, get: impl Fn(&Fem) -> f64, d: usize) -> String {
    match f.map(get) { Some(x) if x.is_finite() => format!("{x:.d$}"), _ => String::new() }
}
