//! PR-0.28.3: emitted record JSON is strict (unique keys, no NaN), and a missing FEM result is
//! null + `fem_status`, never zeros. Cases: rejected-before-FEM, FEM failed, complete, NaN scalar.
use jarambit_crescent::{qd, record, Genome};
use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use std::fmt;

/// Deserialises any JSON value, failing on a duplicate key in any object (serde_json alone keeps the last).
struct Strict;
impl<'de> Deserialize<'de> for Strict {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = Strict;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result { f.write_str("json") }
            fn visit_bool<E>(self, _: bool) -> Result<Strict, E> { Ok(Strict) }
            fn visit_i64<E>(self, _: i64) -> Result<Strict, E> { Ok(Strict) }
            fn visit_u64<E>(self, _: u64) -> Result<Strict, E> { Ok(Strict) }
            fn visit_f64<E: de::Error>(self, x: f64) -> Result<Strict, E> { if x.is_finite() { Ok(Strict) } else { Err(E::custom("non-finite")) } }
            fn visit_str<E>(self, _: &str) -> Result<Strict, E> { Ok(Strict) }
            fn visit_unit<E>(self) -> Result<Strict, E> { Ok(Strict) }
            fn visit_seq<A: SeqAccess<'de>>(self, mut a: A) -> Result<Strict, A::Error> { while a.next_element::<Strict>()?.is_some() {} Ok(Strict) }
            fn visit_map<A: MapAccess<'de>>(self, mut a: A) -> Result<Strict, A::Error> {
                let mut seen = std::collections::HashSet::new();
                while let Some(k) = a.next_key::<String>()? { if !seen.insert(k.clone()) { return Err(de::Error::custom(format!("duplicate key {k}"))); } a.next_value::<Strict>()?; }
                Ok(Strict)
            }
        }
        d.deserialize_any(V)
    }
}
fn strict(s: &str) -> Result<(), String> { serde_json::from_str::<Strict>(s).map(|_| ()).map_err(|e| e.to_string()) }
fn val(s: &str) -> serde_json::Value { serde_json::from_str(s).unwrap() }
const FEM_KEYS: [&str; 18] = ["lat20", "lat_rob", "ring20", "ring_rob", "pry20", "twist20_nmm", "sf_hiker", "sf_hunter", "sf_ring", "floors_ok", "lat_at",
    "seq_ratio", "seq_case", "twist_tip_sf", "twist_tip_joint3d_nmm", "twist_tip_peak_tipdist", "twist_body_sf", "twist_tipzone_sf"];

fn base() -> qd::Rec {
    let txt = include_str!("../../../docs/d1/wave15_16_collect/wave14_c03_genome.csv");
    let row: Vec<&str> = txt.lines().nth(1).unwrap().split(',').collect();
    let g = Genome::from_csv(&row).expect("w14c03 genome");
    let r = qd::evaluate(&g, 7, 0, 4.0); assert!(r.aes.pass && r.rejects.is_empty() && r.fem.is_some(), "w14c03 should reach FEM: {:?} {:?}", r.aes.fails, r.rejects); r }

#[test]
fn duplicate_checker_works() {
    assert!(strict(r#"{"a":1,"b":{"c":2}}"#).is_ok());
    assert!(strict(r#"{"pry20":1,"pry20":1}"#).is_err());
    assert!(strict(r#"{"a":{"x":1,"x":2}}"#).is_err());
}

#[test]
fn record_cases() {
    let r = base();
    // complete
    let s = record::rec_json(&r); strict(&s).unwrap(); let v = val(&s);
    assert_eq!(v["fem_status"], "complete");
    assert_eq!(s.matches("\"pry20\"").count(), 1, "pry20 must appear once");
    for k in FEM_KEYS { assert!(!v[k].is_null(), "{k} null on a complete record"); }
    // rejected before FEM
    let mut x = r.clone(); x.rejects = vec!["blade \"short\" (3.1 in)".into()]; x.fem = None;
    let s = record::rec_json(&x); strict(&s).unwrap(); let v = val(&s);
    assert_eq!(v["fem_status"], "not_evaluated"); assert_eq!(v["legal"], false); assert!(v["spg"].is_null());
    for k in FEM_KEYS { assert!(v[k].is_null(), "{k} must be null when FEM not evaluated, got {}", v[k]); }
    assert_eq!(v["rejects"][0], "blade \"short\" (3.1 in)");
    // FEM attempted but failed
    let mut x = r.clone(); x.fem = None;
    let v = val(&record::rec_json(&x)); assert_eq!(v["fem_status"], "failed");
    for k in FEM_KEYS { assert!(v[k].is_null()); }
    // NaN scalar
    let mut x = r.clone(); if let Some(f) = x.fem.as_mut() { f.lat_rob = f64::NAN; f.twist_tipzone_sf = f64::INFINITY; } x.novelty = f64::NAN;
    let s = record::rec_json(&x); strict(&s).unwrap(); let v = val(&s);
    assert_eq!(v["fem_status"], "incomplete"); assert!(v["lat_rob"].is_null()); assert!(v["twist_tipzone_sf"].is_null()); assert!(v["novelty"].is_null());
    assert!(!v["ring_rob"].is_null());
}
