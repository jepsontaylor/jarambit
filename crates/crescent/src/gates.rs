//! Hard constraint + manufacturability gate for the crescent lane (never weakened silently).
use crate::genome::*;
use crate::geom::*;
use crate::pheno::*;
use jarambit_redteam::{holder, holder_forces};

pub const LIGAMENT_MIN_MM: f64 = 3.0;
pub const RING_WALL_MIN_MM: f64 = 4.5;
pub const LAND_MIN_MM2: f64 = 40.0;

/// Smallest (length, width) planform box over orientations -30..30 deg (0.5 deg) that fits
/// the frozen 200 x 100 mm holder envelope, if any. (OWNER DECISION: oriented, not grip-axis.)
pub fn holder_fit(outline: &[P2]) -> (bool, f64, f64, f64) {
    let mut best = (false, f64::MAX, f64::MAX, 0.0);
    for k in 0..=120 { let a = (-30.0 + 0.5 * k as f64).to_radians(); let (c, s) = (a.cos(), a.sin());
        let (mut x0, mut x1, mut y0, mut y1) = (f64::MAX, f64::MIN, f64::MAX, f64::MIN);
        for q in outline { let u = c * q.0 - s * q.1; let v = s * q.0 + c * q.1; x0 = x0.min(u); x1 = x1.max(u); y0 = y0.min(v); y1 = y1.max(v); }
        let (l, w) = (x1 - x0, y1 - y0);
        let fit = l <= holder::MAX_KNIFE_H_MM && w <= holder::MAX_KNIFE_W_MM;
        let score = (l / holder::MAX_KNIFE_H_MM).max(w / holder::MAX_KNIFE_W_MM);
        if (fit && !best.0) || (fit == best.0 && score < (best.1 / holder::MAX_KNIFE_H_MM).max(best.2 / holder::MAX_KNIFE_W_MM)) { best = (fit, l, w, a.to_degrees()); }
    }
    best
}

pub fn check(g: &Genome, p: &Pheno) -> Vec<String> {
    let mut r = p.fails.clone();
    let b = &p.blade;
    for (n, v) in [("tip_to_heel", b.tip_to_heel), ("horizontal_reach", b.horizontal_reach), ("sharpened_arc", b.sharpened_arc)] {
        if !(v >= FLOOR_MM) { r.push(format!("BladeTooShort {n} {v:.2} < {FLOOR_MM:.3} mm")); } }
    if !(b.arc_in <= CAP_MM) { r.push(format!("BladeEdgeTooLong inside {:.2} > 101.6", b.arc_in)); }
    if !(b.arc_sp <= CAP_MM) { r.push(format!("BladeEdgeTooLong spine {:.2} > 101.6", b.arc_sp)); }
    if !(p.grip_len >= 60.0 && p.grip_len <= 80.0) { r.push(format!("GripOutOfBand {:.1}", p.grip_len)); }
    if !((p.ring_id - 25.4).abs() <= 0.5 + 1e-9) { r.push(format!("RingIdOutOfSpec {:.2}", p.ring_id)); }
    if p.teeth_in < 3 || p.teeth_sp < 3 || p.ripple_in < 0.05 || p.ripple_sp < 0.05 { r.push("NotDoubleSerrated".into()); }
    if !p.mat.is_titanium() { r.push("NonTitanium".into()); }
    if ((p.t * 10.0).round() - p.t * 10.0).abs() > 1e-9 || p.t < T_MIN - 1e-9 || p.t > 6.0 + 1e-9 { r.push(format!("Stock {:.2} outside 5.3-6.0 / 0.1 mm", p.t)); }
    if g.v[EA_IN] < 14.0 || g.v[EA_SP] < 14.0 { r.push("UnsafeGeometry edge < 14 deg/side".into()); }
    // ---- connected single solid: holes inside, ligaments, no self-intersection ----
    if self_intersects(&p.outline) { r.push("Disconnected: self-intersecting outline".into()); }
    for (h, name) in p.holes.iter().zip(&p.hole_names) {
        if !h.iter().all(|&q| point_in_poly(q, &p.outline)) { r.push(format!("Disconnected: {name} breaks the outline")); continue; }
        let lig = min_ring_dist(h, &p.outline);
        let need = if *name == "ring" { RING_WALL_MIN_MM } else { LIGAMENT_MIN_MM };
        if lig < need { r.push(format!("Ligament {name}-outline {lig:.2} < {need} mm")); }
    }
    for i in 0..p.holes.len() { for j in i + 1..p.holes.len() {
        let d = min_ring_dist(&p.holes[i], &p.holes[j]);
        if d < LIGAMENT_MIN_MM { r.push(format!("Ligament {}-{} {d:.2} < {LIGAMENT_MIN_MM} mm", p.hole_names[i], p.hole_names[j])); } } }
    // ---- sheath pop-in (frozen holder model, crescent interface) ----
    let wall = g.v[WALL]; let det = g.v[DETENT];
    if p.t + 2.0 * wall + 2.0 * holder::CLEARANCE_MM > holder::MAX_STACK_MM + 1e-9 { r.push("Holder stack too thick".into()); }
    let hf = holder_forces(wall, det);
    if !(hf.insertion_n >= holder::INSERT_N.0 && hf.insertion_n <= holder::INSERT_N.1) { r.push(format!("Holder insertion {:.1} N", hf.insertion_n)); }
    if !(hf.draw_n >= holder::DRAW_N.0 && hf.draw_n <= holder::DRAW_N.1) { r.push(format!("Holder draw {:.1} N", hf.draw_n)); }
    if !p.hole_names.contains(&"cairn") || g.v[CAIRN] < 4.0 { r.push("Holder: no cairn retention hole".into()); }
    if p.land_full_mm2 < LAND_MIN_MM2 { r.push(format!("Holder friction land {:.0} mm2 < {LAND_MIN_MM2}", p.land_full_mm2)); }
    let (fit, l, w, _) = holder_fit(&p.outline);
    if !fit { r.push(format!("Holder envelope: best oriented box {l:.1} x {w:.1} > 200 x 100")); }
    // ---- brand pad on a flat ----
    let pad_in = p.pad.iter().all(|&q| point_in_poly(q, &p.outline) && !p.holes.iter().any(|h| point_in_poly(q, h)));
    let pad_clear = min_ring_dist(&densify(&p.pad, 0.5, true), &p.outline) >= 1.0 && p.holes.iter().all(|h| min_ring_dist(&densify(&p.pad, 0.5, true), h) >= 1.0);
    if !(pad_in && pad_clear && p.pad_flat) { r.push("BrandPad not on a clear flat".into()); }
    if !(p.mass_g.is_finite() && p.mass_g > 20.0 && p.mass_g < 200.0) { r.push(format!("crazy mass {:.1}", p.mass_g)); }
    r
}
