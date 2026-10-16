//! Locked Global Fitness metric `G1` (`docs/GLOBAL_METRIC.md`, `metrics/global_metric.py`).
//!
//! ```text
//! G = 0.35 * tip + 0.35 * spg_n + 0.20 * aes - 0.05 * mass_pen - 0.05 * seq_gap
//!   tip      = min(solid_tip_SF, 2.0)
//!   spg_n    = spg / 4.0
//!   aes      = aes_score (0..1)
//!   mass_pen = max(0, mass_g - 77) / 10
//!   seq_gap  = max(0, 1.2 - seq_ratio) / 1.2
//! ```
//!
//! Completeness contract (PR-0.28.1): every term is REQUIRED. A missing, null, boolean,
//! non-numeric, non-finite, or out-of-range input is never coerced to 0; the record gets
//! status `"INCOMPLETE"`, the reasons are listed in `missing`, and `global_g` returns `None`.
//! Deleting an input can therefore never improve `G`.

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

pub const GLOBAL_METRIC_VERSION: &str = "G1";
pub const COMPLETE: &str = "COMPLETE";
pub const INCOMPLETE: &str = "INCOMPLETE";

pub const W_TIP: f64 = 0.35;
pub const W_SPG: f64 = 0.35;
pub const W_AES: f64 = 0.20;
pub const W_MASS: f64 = 0.05;
pub const W_SEQ: f64 = 0.05;

pub const TIP_KEYS: [&str; 3] = [
    "solid_tip_sf_nodal_max",
    "plate_tipsub_screen_sf",
    "twist_tipzone_sf_strict",
];

fn range_for(key: &str) -> Option<(f64, f64)> {
    match key {
        "solid_tip_sf_nodal_max" | "plate_tipsub_screen_sf" | "twist_tipzone_sf_strict" => {
            Some((0.0, 100.0))
        }
        "spg" => Some((0.0, 100.0)),
        "aes_score" => Some((0.0, 1.0)),
        "mass_g" => Some((1.0, 1000.0)),
        "seq_ratio" => Some((0.0, 100.0)),
        _ => None,
    }
}

/// Validate a single observation from a JSON map without coercing missing/invalid values.
pub fn obs(rec: &Map<String, Value>, key: &str) -> Result<f64, String> {
    let Some(v) = rec.get(key) else {
        return Err(format!("{key}: missing"));
    };
    let num = match v {
        Value::Null => return Err(format!("{key}: null")),
        Value::Bool(_) => return Err(format!("{key}: boolean not allowed")),
        Value::Number(n) => {
            let Some(f) = n.as_f64() else {
                return Err(format!("{key}: non-finite"));
            };
            f
        }
        Value::String(s) => match s.trim().parse::<f64>() {
            Ok(f) => f,
            Err(_) => return Err(format!("{key}: not a number ({s:?})")),
        },
        Value::Array(_) => return Err(format!("{key}: unsupported type list")),
        Value::Object(_) => return Err(format!("{key}: unsupported type dict")),
    };
    if !num.is_finite() {
        return Err(format!("{key}: non-finite"));
    }
    let (lo, hi) = range_for(key).ok_or_else(|| format!("{key}: unknown key"))?;
    if !(lo <= num && num <= hi) {
        return Err(format!("{key}: out of range [{lo:.1}, {hi:.1}] ({num})"));
    }
    Ok(num)
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct G1Terms {
    pub tip: Option<f64>,
    pub tip_source: Option<String>,
    pub tip_missing: bool,
    pub provisional: bool,
    pub spg_n: Option<f64>,
    pub aes: Option<f64>,
    pub mass_pen: Option<f64>,
    pub seq_gap: Option<f64>,
    pub status: String,
    pub missing: Vec<String>,
    pub metric_version: String,
}

/// Evaluate all 5 terms of `G1` from a JSON map of inputs.
pub fn terms(rec: &Map<String, Value>) -> G1Terms {
    let mut missing = Vec::new();
    let mut tip: Option<f64> = None;
    let mut tip_src: Option<String> = None;
    let mut tip_reasons = Vec::new();

    for &k in &TIP_KEYS {
        match obs(rec, k) {
            Ok(v) => {
                tip = Some(v);
                tip_src = Some(k.to_string());
                break;
            }
            Err(why) => tip_reasons.push(why),
        }
    }
    if tip.is_none() {
        missing.push(format!("tip: {}", tip_reasons.join("; ")));
    }

    let spg = match obs(rec, "spg") {
        Ok(v) => Some(v),
        Err(why) => {
            missing.push(why);
            None
        }
    };
    let aes = match obs(rec, "aes_score") {
        Ok(v) => Some(v),
        Err(why) => {
            missing.push(why);
            None
        }
    };
    let mass_g = match obs(rec, "mass_g") {
        Ok(v) => Some(v),
        Err(why) => {
            missing.push(why);
            None
        }
    };
    let seq_ratio = match obs(rec, "seq_ratio") {
        Ok(v) => Some(v),
        Err(why) => {
            missing.push(why);
            None
        }
    };

    let status = if missing.is_empty() {
        COMPLETE.to_string()
    } else {
        INCOMPLETE.to_string()
    };

    G1Terms {
        tip: tip.map(|t| t.min(2.0)),
        provisional: tip_src.as_deref() != Some("solid_tip_sf_nodal_max"),
        tip_missing: tip.is_none(),
        tip_source: tip_src,
        spg_n: spg.map(|s| s / 4.0),
        aes,
        mass_pen: mass_g.map(|m| (m - 77.0).max(0.0) / 10.0),
        seq_gap: seq_ratio.map(|s| (1.2 - s).max(0.0) / 1.2),
        status,
        missing,
        metric_version: GLOBAL_METRIC_VERSION.to_string(),
    }
}

/// Compute `(G, terms)`. Returns `G = None` unless `terms.status == "COMPLETE"`.
pub fn global_g(rec: &Map<String, Value>) -> (Option<f64>, G1Terms) {
    let t = terms(rec);
    if t.status != COMPLETE {
        return (None, t);
    }
    let g = W_TIP * t.tip.unwrap()
        + W_SPG * t.spg_n.unwrap()
        + W_AES * t.aes.unwrap()
        - W_MASS * t.mass_pen.unwrap()
        - W_SEQ * t.seq_gap.unwrap();
    (Some(g), t)
}

/// Format the canonical plate/battery title tag (`G 0.878 | 75.6 g | jarambit v0.32.9`).
pub fn title_tag(rec: &Map<String, Value>, version: &str) -> String {
    let (g, t) = global_g(rec);
    let mass_s = match obs(rec, "mass_g") {
        Ok(m) => format!("{m:.1} g"),
        Err(_) => "mass n/a".to_string(),
    };
    match g {
        None => format!(
            "G INCOMPLETE ({} missing) | {mass_s} | jarambit v{version}",
            t.missing.len()
        ),
        Some(val) => {
            let star = if t.provisional { "*" } else { "" };
            format!("G{star} {val:.3} | {mass_s} | jarambit v{version}")
        }
    }
}

/// Assemble the `global_fitness` block used in `jarambit.cad_battery.subject.v1`.
pub fn assemble_g(inputs: &Map<String, Value>, version: &str) -> Value {
    let (val, t) = global_g(inputs);
    serde_json::json!({
        "metric": GLOBAL_METRIC_VERSION,
        "inputs": inputs,
        "G": val,
        "status": t.status,
        "provisional": if val.is_some() { Value::Bool(t.provisional) } else { Value::Null },
        "missing": t.missing,
        "title": title_tag(inputs, version),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn g1_exact_parity_with_python_reference() {
        let mut m = Map::new();
        m.insert("solid_tip_sf_nodal_max".into(), json!(1.5));
        m.insert("spg".into(), json!(4.0));
        m.insert("aes_score".into(), json!(0.6));
        m.insert("mass_g".into(), json!(80.0));
        m.insert("seq_ratio".into(), json!(0.9));
        let (g, t) = global_g(&m);
        assert_eq!(t.status, COMPLETE);
        assert!(!t.provisional);
        assert!((g.unwrap() - 0.9675).abs() < 1e-12);
        assert_eq!(title_tag(&m, "0.32.9"), "G 0.967 | 80.0 g | jarambit v0.32.9");
    }

    #[test]
    fn g1_rejects_missing_boolean_null_and_out_of_range_inputs() {
        let mut m = Map::new();
        m.insert("solid_tip_sf_nodal_max".into(), json!(true));
        m.insert("spg".into(), json!(null));
        m.insert("aes_score".into(), json!(1.5));
        m.insert("mass_g".into(), json!(75.568));
        let (g, t) = global_g(&m);
        assert!(g.is_none());
        assert_eq!(t.status, INCOMPLETE);
        assert_eq!(t.missing.len(), 4);
    }
}
