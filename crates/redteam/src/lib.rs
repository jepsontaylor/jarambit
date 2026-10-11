//! Red-team gate: reject anything that is not a recognizable, connected, curved, double-edged,
//! double-serrated SWITCHBACK titanium hiking/utility karambit that pops into the assumed holder,
//! or that violates the hard blade-length / grip / ring constraints. Never weaken these rules.
use jarambit_genotype::{bounds, limits, Genotype};
use jarambit_phenotype::{dist_to_poly, self_intersects, shoelace, Phenotype};
pub use jarambit_phenotype::point_in_poly;

/// Assumed fixed-blade holder envelope (docs/HOLDER_ENVELOPE.md).
pub mod holder {
    pub const MAX_KNIFE_W_MM: f64 = 100.0;   // across the holder (x span)
    pub const MAX_KNIFE_H_MM: f64 = 200.0;   // overall length (y span)
    pub const MAX_STACK_MM: f64 = 9.0;       // knife t + 2 shell walls + 2 x 0.2 clearance
    pub const CLEARANCE_MM: f64 = 0.2;
    pub const MIN_EXPOSED_GRIP_MM: f64 = 30.0; // grip + ring left outside the holder for draw
    pub const MAX_DETENT_FRAC_OF_HW: f64 = 0.15;
}

#[derive(Debug, Clone, PartialEq)]
pub enum Reject {
    NotCurved, NoFingerRing, NotDoubleSerrated, Disconnected, ThicknessPrecision, NonTitanium,
    /// Rev C.2 all-three policy: any one of tip_to_heel / horizontal_reach / sharpened_arc >= limit.
    BladeTooLong { measure: &'static str, mm: f64 },
    GripOutOfBand(f64),
    RingIdOutOfSpec(f64),
    BrandPad(String),
    Holder(String),
    NotKarambit(String),
    UnsafeGeometry(String),
}

pub fn check(g: &Genotype, p: &Phenotype) -> Result<(), Vec<Reject>> {
    let mut r = vec![];
    let lim = limits::BLADE_LIMIT_MM - limits::BLADE_GUARD_MM;
    // ---- hard blade-length policy: ALL THREE measures must be under the limit ----
    for (name, v) in [("tip_to_heel", p.blade.tip_to_heel), ("horizontal_reach", p.blade.horizontal_reach), ("sharpened_arc", p.blade.sharpened_arc)] {
        if !(v < lim) { r.push(Reject::BladeTooLong { measure: name, mm: v }); }
    }
    // ---- curved, recognizable karambit ----
    if !(p.blade.sweep_deg >= limits::MIN_SWEEP_DEG) || g.curve_radius > bounds::CURVE_RADIUS.1 { r.push(Reject::NotCurved); }
    if p.blade.vertical_rise <= limits::BLADE_H_MM { r.push(Reject::NotKarambit("blade does not rise over the grip line".into())); }
    if !(p.ring_center.1 < -p.ricasso_len - p.grip_len) { r.push(Reject::NotKarambit("ring not at end of grip".into())); }
    // ---- grip & ring ----
    if !(p.grip_len >= limits::GRIP_MIN_MM - 1e-9 && p.grip_len <= limits::GRIP_MAX_MM + 1e-9) { r.push(Reject::GripOutOfBand(p.grip_len)); }
    if !((p.ring_id - limits::RING_ID_MM).abs() <= limits::RING_ID_TOL_MM + 1e-9) { r.push(Reject::RingIdOutOfSpec(p.ring_id)); }
    if p.ring_hole.len() < 16 { r.push(Reject::NoFingerRing); }
    // ---- double edge, both serrated ----
    if p.inner_teeth < 3 || p.outer_teeth < 3 || !(g.serr_inner.depth > 0.0) || !(g.serr_outer.depth > 0.0) { r.push(Reject::NotDoubleSerrated); }
    // ---- single connected solid, genus 1 ----
    let inside = p.ring_hole.iter().all(|&q| point_in_poly(q, &p.outline));
    let wall_ok = p.ring_hole.iter().map(|&q| dist_to_poly(q, &p.outline)).fold(f64::MAX, f64::min) >= 3.0;
    if !inside || !wall_ok || shoelace(&p.outline).abs() <= shoelace(&p.ring_hole).abs() || self_intersects(&p.outline) { r.push(Reject::Disconnected); }
    // ---- material / precision / safety ----
    if !g.material.is_titanium() { r.push(Reject::NonTitanium); }
    if ((g.thickness * 10.0).round() - g.thickness * 10.0).abs() > 1e-9 { r.push(Reject::ThicknessPrecision); }
    if g.ring_wall < 4.0 { r.push(Reject::UnsafeGeometry("ring wall < 4 mm".into())); }
    if g.thickness < 2.5 { r.push(Reject::UnsafeGeometry("stock < 2.5 mm".into())); }
    if !(g.edge_angle_deg >= 14.0) { r.push(Reject::UnsafeGeometry("edge < 14 deg/side (Ti edge roll)".into())); }
    // ---- flat brand pad: inside grip, clear of detent and ring ----
    let bp = &p.brand_pad; let (pw, pl) = (bp[1].0 - bp[0].0, bp[2].1 - bp[1].1);
    if pw < limits::BRAND_PAD_MIN.0 - 1e-9 || pl < limits::BRAND_PAD_MIN.1 - 1e-9 { r.push(Reject::BrandPad(format!("too small {pw:.1}x{pl:.1}"))); }
    if bp.iter().any(|&q| !point_in_poly(q, &p.outline)) || pw > p.handle_w - 1.0 { r.push(Reject::BrandPad("not inside grip".into())); }
    if bp[2].1 > p.detent.0 - 1.5 * p.detent.1 - 1.0 { r.push(Reject::BrandPad("overlaps holder detent".into())); }
    // ---- sheath / fixed-blade holder pop-in interface ----
    let h = &g.holder;
    if h.shoulder_w < bounds::SHOULDER_W.0 - 1e-9 { r.push(Reject::Holder("no positive-stop shoulder".into())); }
    if h.ricasso_len < bounds::RICASSO_LEN.0 - 1e-9 { r.push(Reject::Holder("thickness land too short".into())); }
    if h.detent_depth < bounds::DETENT_DEPTH.0 - 1e-9 || h.detent_depth > holder::MAX_DETENT_FRAC_OF_HW * p.handle_w { r.push(Reject::Holder(format!("detent depth {:.2} out of pop-in window", h.detent_depth))); }
    if h.detent_pos * g.grip_len > h.friction_len { r.push(Reject::Holder("detent outside friction-face zone".into())); }
    if g.grip_len - h.friction_len < holder::MIN_EXPOSED_GRIP_MM - 1e-9 { r.push(Reject::Holder("holder covers too much grip to draw".into())); }
    if h.drain_d < bounds::HOLDER_DRAIN_D.0 - 1e-9 { r.push(Reject::Holder("holder drain too small".into())); }
    let ((x0, y0), (x1, y1)) = p.bbox;
    if x1 - x0 > holder::MAX_KNIFE_W_MM || y1 - y0 > holder::MAX_KNIFE_H_MM { r.push(Reject::Holder(format!("outside holder envelope {:.0}x{:.0}", x1 - x0, y1 - y0))); }
    if g.thickness + 2.0 * h.holder_wall + 2.0 * holder::CLEARANCE_MM > holder::MAX_STACK_MM { r.push(Reject::Holder("holder stack too thick".into())); }
    if r.is_empty() { Ok(()) } else { Err(r) }
}


#[cfg(test)]
mod tests {
    use super::*;
    use jarambit_genotype::{Rng, TiGrade};
    fn has(g: &Genotype, f: impl Fn(&Reject) -> bool) -> bool { let p = Phenotype::from_genotype(g); check(g, &p).err().map(|v| v.iter().any(|x| f(x))).unwrap_or(false) }
    #[test] fn random_designs_pass_gate() {
        let mut r = Rng(7); let mut bad = 0;
        for _ in 0..2000 { let g = Genotype::random(&mut r); let p = Phenotype::from_genotype(&g); if let Err(e) = check(&g, &p) { bad += 1; if bad < 5 { eprintln!("{e:?}"); } } }
        assert_eq!(bad, 0, "repaired random designs should all pass");
    }
    #[test] fn rejects_straight() { let mut g = Genotype::random(&mut Rng(9)); g.sweep_override_deg = Some(10.0); assert!(has(&g, |x| *x == Reject::NotCurved)); }
    #[test] fn rejects_single_serrated() { let mut g = Genotype::random(&mut Rng(9)); g.serr_outer.depth = 0.0; assert!(has(&g, |x| *x == Reject::NotDoubleSerrated)); }
    #[test] fn rejects_disconnected() {
        let g = Genotype::random(&mut Rng(11)); let mut p = Phenotype::from_genotype(&g);
        for q in p.ring_hole.iter_mut() { q.0 += 500.0; }
        assert!(check(&g, &p).unwrap_err().contains(&Reject::Disconnected));
    }
    #[test] fn rejects_long_blade_each_measure() {
        // bypass clamp: long arc at large radius -> sharpened arc & tip-to-heel over 85.725 mm
        let mut g = Genotype::random(&mut Rng(13)); g.blade_arc_len = 110.0; g.curve_radius = 45.0;
        let p = Phenotype::from_genotype(&g);
        let e = check(&g, &p).unwrap_err();
        assert!(e.iter().any(|x| matches!(x, Reject::BladeTooLong { measure: "sharpened_arc", .. })), "{e:?}");
        assert!(e.iter().any(|x| matches!(x, Reject::BladeTooLong { measure: "tip_to_heel", .. })), "{e:?}");
        // wide sweep at large radius: horizontal reach over the limit
        let mut g = Genotype::random(&mut Rng(14)); g.curve_radius = 45.0; g.sweep_override_deg = Some(170.0);
        let p = Phenotype::from_genotype(&g); let e = check(&g, &p).unwrap_err();
        assert!(e.iter().any(|x| matches!(x, Reject::BladeTooLong { measure: "horizontal_reach", .. })), "{e:?} {:?}", p.blade);
    }
    #[test] fn rejects_any_single_measure_over() {
        // all-three policy: being under on arc but over on reach still rejects (and vice versa)
        let mut r = Rng(17);
        for _ in 0..3000 {
            let mut g = Genotype::random(&mut r); g.blade_arc_len = r.range(70.0, 115.0); g.curve_radius = r.range(28.0, 60.0);
            let p = Phenotype::from_genotype(&g); let lim = limits::BLADE_LIMIT_MM - limits::BLADE_GUARD_MM;
            let any_over = p.blade.tip_to_heel >= lim || p.blade.horizontal_reach >= lim || p.blade.sharpened_arc >= lim;
            let rej = check(&g, &p).err().map(|v| v.iter().any(|x| matches!(x, Reject::BladeTooLong { .. }))).unwrap_or(false);
            assert_eq!(any_over, rej);
        }
    }
    #[test] fn rejects_short_grip() { let mut g = Genotype::random(&mut Rng(19)); g.grip_len = 55.0; assert!(has(&g, |x| matches!(x, Reject::GripOutOfBand(_)))); }
    #[test] fn rejects_wrong_ring() { let mut g = Genotype::random(&mut Rng(21)); g.ring_id = 22.0; assert!(has(&g, |x| matches!(x, Reject::RingIdOutOfSpec(_)))); }
    #[test] fn rejects_bad_holder_iface() {
        let mut g = Genotype::random(&mut Rng(23)); g.holder.shoulder_w = 0.0; assert!(has(&g, |x| matches!(x, Reject::Holder(_))));
        let mut g = Genotype::random(&mut Rng(24)); g.holder.detent_depth = 0.1; assert!(has(&g, |x| matches!(x, Reject::Holder(_))));
        let mut g = Genotype::random(&mut Rng(25)); g.holder.friction_len = g.grip_len; assert!(has(&g, |x| matches!(x, Reject::Holder(_))));
    }
    #[test] fn rejects_imprecise_thickness() { let mut g = Genotype::random(&mut Rng(27)); g.thickness = 3.05; assert!(has(&g, |x| *x == Reject::ThicknessPrecision)); }
    #[test] fn titanium_only() { assert!(TiGrade::Ti6Al4V.is_titanium() && TiGrade::Ti3Al2_5V.is_titanium()); }
}
