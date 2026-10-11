//! MC <-> FEM calibration constants, MEASURED 2026-10-11 by `jarambit calib` (out/calib,
//! docs/CALIBRATION.md): 258 designs (wave5 winner, 17 mh1 group winners, 120 red-team-legal
//! random genomes, each also with a sharp neck). Reference = detailed plate (`fine`) at
//! VERIFY_AREA = 0.25 mm^2, converged per `jarambit fem-verify`. 20 C.
//!
//! The beam surrogate overstates the detailed plate's lateral capacity by a median 1.80x
//! (p95 2.95x, max 3.07x); the wave5 winner itself was 2.3-3.2x depending on the plate used.
//! The calibrated search does NOT trust the surrogate level: it solves the detailed plate per
//! candidate (FEM-in-loop) and uses the surrogate Monte Carlo only for the p05/nominal ratio.
//! Any surrogate-only score must be divided by the MAX factor below so it cannot overstate.
use super::Eval;

/// beam-surrogate lateral / detailed-plate lateral
pub const SURR_OVER_PLATE_LAT_MEDIAN: f64 = 1.796;
pub const SURR_OVER_PLATE_LAT_P95: f64 = 2.952;
pub const SURR_OVER_PLATE_LAT_MAX: f64 = 3.065;
/// beam-surrogate ring pull / detailed-plate ring pull
pub const SURR_OVER_PLATE_RING_MEDIAN: f64 = 6.311;
pub const SURR_OVER_PLATE_RING_MAX: f64 = 8.449;
/// coarse plate (`fem`, boundary-only mesh) lateral / detailed plate
pub const COARSE_OVER_PLATE_LAT_MEDIAN: f64 = 1.199;
pub const COARSE_OVER_PLATE_LAT_MAX: f64 = 1.874;
/// detailed plate at SEARCH_AREA (2 mm^2) / at VERIFY_AREA: the search divides by the max
/// so the in-loop mesh cannot overstate either.
pub const MESH_BIAS_LAT_MAX: f64 = 1.070;
pub const MESH_BIAS_RING_MAX: f64 = 1.062;

/// Surrogate evaluation scaled so it never exceeds the detailed plate on the calibration set
/// (divide by the max observed overstatement). Floors re-evaluated on the scaled numbers.
pub fn calibrated_surrogate(e: &Eval) -> Eval {
    let mut c = e.clone();
    let k = SURR_OVER_PLATE_LAT_MAX;
    c.strength_n /= k; c.blade_lat_n /= k; c.grip_lat_n /= k;
    c.ring_pull_n /= SURR_OVER_PLATE_RING_MAX;
    c.strength_per_gram = c.strength_n / c.mass_g.max(1e-6);
    c.hiker_ok = c.strength_n >= super::floors::HIKER_LATERAL_N;
    c.hunter_ok = c.strength_n >= super::floors::HUNTER_LATERAL_N;
    c.ring_ok = c.ring_pull_n >= super::floors::RING_PULL_N;
    c
}
