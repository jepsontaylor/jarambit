//! SWITCHBACK Rev C.6 reference (hiking-karambit/revC6_outline.json + switchback_revC6_*.step, 2026-10-11).
//! Rev C.6 (adopted by Jepson as owner): C.5 outline, holes, jimping, flutes, stock, tip and heel UNCHANGED;
//! adds a TWO-SIDED ring-face racetrack groove: annulus concentric with the finger-ring bore,
//! r = r_bore + 1.6 .. r_OD - 1.6 (C.6 nominal 14.3-17.4 mm), 0.6 mm deep per face (web t - 1.2),
//! R0.5 floor-corner fillet (B-rep only; the 0.25 mm raster ignores it, like gen.py). Both faces carry
//! the channel, so a contrast anodize can sit in it on either side (WHITEPAPER IX-C patent callout).
//! Everything else is re-exported from `c5_ref`. Aesthetic anchor of the crescent genotype from wave13 on.
#![allow(clippy::all)]
pub use crate::c5_ref::*;
pub const REV: &str = "C.6";
/// Groove depth per face (mm).
pub const RING_GROOVE_D: f64 = 0.6;
/// Full-thickness rim kept at the bore AND at the ring OD (mm).
pub const RING_GROOVE_RIM: f64 = 1.6;
/// Floor-corner fillet (B-rep).
pub const RING_GROOVE_FILLET: f64 = 0.5;
/// Narrowest groove the C.6 look accepts (Ø2 mm ball/flat end mill; C.6 nominal 3.1 mm).
pub const RING_GROOVE_MIN_W: f64 = 2.0;
/// C.6 nominal radii (ring ID 25.4, wall 6.3).
pub const RING_GROOVE_R: (f64, f64) = (14.3, 17.4);
/// Anchor in force: C.6 by default; JARAMBIT_ANCHOR=C5 rebuilds the C.5 phenotype (no groove) for A/B studies.
pub fn active() -> bool {
    static A: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *A.get_or_init(|| !matches!(std::env::var("JARAMBIT_ANCHOR").as_deref(), Ok("C5") | Ok("C.5")))
}
pub fn rev() -> &'static str { if active() { REV } else { crate::c5_ref::REV } }
