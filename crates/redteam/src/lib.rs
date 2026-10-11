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
    /// Pop-in window for a gloved one-handed seat (N). Covers the legal gene box
    /// plus the MC wall/detent tolerance; crazy shells fall outside.
    pub const INSERT_N: (f64, f64) = (3.0, 80.0);
    /// Draw window (N): stays seated on the trail, comes out one-handed.
    pub const DRAW_N: (f64, f64) = (1.5, 45.0);
}

/// Insertion and draw force proxy for the holder retention nub.
/// Kydex-like shell, E = 2.2 GPa, nub tab width 12 mm, snap length 10 mm:
/// `F_ins = 3 E I δ / L³ = 6.6 · wall³ · detent` (N when lengths are mm).
/// Draw is the return stroke, taken as 0.55× insertion (shallower ramp).
#[derive(Clone, Copy, Debug)]
pub struct HolderForces { pub insertion_n: f64, pub draw_n: f64 }
pub fn holder_forces(wall_mm: f64, detent_mm: f64) -> HolderForces {
    let ins = 6.6 * wall_mm.max(0.0).powi(3) * detent_mm.max(0.0);
    HolderForces { insertion_n: ins, draw_n: 0.55 * ins }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Reject {
    NotCurved, NoFingerRing, NotDoubleSerrated, Disconnected, ThicknessPrecision, NonTitanium,
    /// All-three FLOOR (Jepson 2026-10-11): any one of tip_to_heel / horizontal_reach /
    /// sharpened_arc below `limits::BLADE_FLOOR_MM` (85.725 mm + 0.5 mm guard).
    BladeTooShort { measure: &'static str, mm: f64 },
    /// Sharpened-edge arc above `limits::BLADE_EDGE_MAX_MM` (4.0 in = 101.6 mm).
    BladeEdgeTooLong(f64),
    GripOutOfBand(f64),
    RingIdOutOfSpec(f64),
    BrandPad(String),
    Holder(String),
    NotKarambit(String),
    UnsafeGeometry(String),
}

/// True when every reject is a short-blade quarantine and there is at least one.
pub fn only_blade_short(errs: &[Reject]) -> bool {
    !errs.is_empty() && errs.iter().all(|e| matches!(e, Reject::BladeTooShort { .. }))
}

/// Sum of how far each blade measure sits under 3.375 in. Zero when all three clear it.
pub fn blade_shortfall_mm(p: &Phenotype) -> f64 {
    let need = limits::BLADE_FLOOR_MM;
    (need - p.blade.tip_to_heel).max(0.0) + (need - p.blade.horizontal_reach).max(0.0) + (need - p.blade.sharpened_arc).max(0.0)
}

pub fn check(g: &Genotype, p: &Phenotype) -> Result<(), Vec<Reject>> {
    let mut r = vec![];
    // ---- hard blade-length policy: ALL THREE measures must be AT LEAST 3.375 in (+0.5 mm guard) ----
    r.extend(blade_length_rejects(&p.blade));
    // ---- curved, recognizable karambit ----
    if !(p.blade.sweep_deg >= limits::MIN_SWEEP_DEG) || g.curve_radius > bounds::CURVE_RADIUS.1 { r.push(Reject::NotCurved); }
    if p.blade.vertical_rise <= limits::BLADE_H_MM { r.push(Reject::NotKarambit("blade does not rise over the grip line".into())); }
    if !(p.ring_center.1 < -p.ricasso_len - p.grip_len) { r.push(Reject::NotKarambit("ring not at end of grip".into())); }
    // ---- grip & ring ----
    if !(p.grip_len >= limits::GRIP_MIN_MM - 1e-9 && p.grip_len <= limits::GRIP_MAX_MM + 1e-9) { r.push(Reject::GripOutOfBand(p.grip_len)); }
    if !((p.ring_id - limits::RING_ID_MM).abs() <= limits::RING_ID_TOL_MM + 1e-9) { r.push(Reject::RingIdOutOfSpec(p.ring_id)); }
    if p.ring_hole.len() < 16 { r.push(Reject::NoFingerRing); }
    // ---- double edge, both serrated (gene counts AND geometric ripple on each edge) ----
    let (in_rip, out_rip) = edge_ripple(g, p);
    if p.inner_teeth < 3 || p.outer_teeth < 3 || !(g.serr_inner.depth > 0.0) || !(g.serr_outer.depth > 0.0)
        || in_rip < 0.05 || out_rip < 0.05 { r.push(Reject::NotDoubleSerrated); }
    // ---- recognisable hook: blade planform leaves the grip axis ----
    if geom_reach(&p.outline) < 8.0 { r.push(Reject::NotKarambit("blade does not hook away from the grip axis".into())); }
    // ---- single connected solid, genus 1 ----
    let inside = p.ring_hole.iter().all(|&q| point_in_poly(q, &p.outline));
    let wall_ok = p.ring_hole.iter().map(|&q| dist_to_poly(q, &p.outline)).fold(f64::MAX, f64::min) >= 3.0;
    // Grip sides are single segments up to ~80 mm. A real gap (broken loop) is much longer.
    let spiked = max_edge(&p.outline) > 150.0 || max_edge(&p.ring_hole) > 15.0;
    if !inside || !wall_ok || spiked || shoelace(&p.outline).abs() <= shoelace(&p.ring_hole).abs()
        || self_intersects(&p.outline) || self_intersects(&p.ring_hole) { r.push(Reject::Disconnected); }
    // ---- material / precision / safety ----
    if !g.material.is_titanium() { r.push(Reject::NonTitanium); }
    if ((g.thickness * 10.0).round() - g.thickness * 10.0).abs() > 1e-9 { r.push(Reject::ThicknessPrecision); }
    if g.ring_wall < 4.0 { r.push(Reject::UnsafeGeometry("ring wall < 4 mm".into())); }
    if g.thickness < 2.5 { r.push(Reject::UnsafeGeometry("stock < 2.5 mm".into())); }
    if !(g.edge_angle_deg >= 14.0) { r.push(Reject::UnsafeGeometry("edge < 14 deg/side (Ti edge roll)".into())); }
    // ---- flat brand pad: inside grip, clear of detent and ring ----
    let bp = &p.brand_pad; let (pw, pl) = (bp[1].0 - bp[0].0, bp[2].1 - bp[1].1);
    let axis_flat = (bp[0].1 - bp[1].1).abs() < 1e-6 && (bp[3].1 - bp[2].1).abs() < 1e-6
        && (bp[0].0 - bp[3].0).abs() < 1e-6 && (bp[1].0 - bp[2].0).abs() < 1e-6 && pw > 0.0 && pl > 0.0;
    if !axis_flat { r.push(Reject::BrandPad("not a flat axis-aligned pad".into())); }
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
    let hf = holder_forces(h.holder_wall, h.detent_depth);
    if !(hf.insertion_n >= holder::INSERT_N.0 && hf.insertion_n <= holder::INSERT_N.1) {
        r.push(Reject::Holder(format!("insertion force {:.1} N outside {:.0}–{:.0} N", hf.insertion_n, holder::INSERT_N.0, holder::INSERT_N.1)));
    }
    if !(hf.draw_n >= holder::DRAW_N.0 && hf.draw_n <= holder::DRAW_N.1) {
        r.push(Reject::Holder(format!("draw force {:.1} N outside {:.0}–{:.0} N", hf.draw_n, holder::DRAW_N.0, holder::DRAW_N.1)));
    }
    let ((x0, y0), (x1, y1)) = p.bbox;
    if x1 - x0 > holder::MAX_KNIFE_W_MM || y1 - y0 > holder::MAX_KNIFE_H_MM { r.push(Reject::Holder(format!("outside holder envelope {:.0}x{:.0}", x1 - x0, y1 - y0))); }
    if g.thickness + 2.0 * h.holder_wall + 2.0 * holder::CLEARANCE_MM > holder::MAX_STACK_MM { r.push(Reject::Holder("holder stack too thick".into())); }
    if r.is_empty() { Ok(()) } else { Err(r) }
}

/// Blade-length gate on its own (also used by quarantine/report tooling).
/// Rejects if ANY of tip_to_heel / horizontal_reach / sharpened_arc < BLADE_FLOOR_MM (86.225 mm)
/// or the sharpened-edge arc > BLADE_EDGE_MAX_MM (101.6 mm). NaN fails.
pub fn blade_length_rejects(b: &jarambit_phenotype::BladeMetrics) -> Vec<Reject> {
    let mut r = vec![];
    let floor = limits::BLADE_FLOOR_MM;
    for (name, v) in [("tip_to_heel", b.tip_to_heel), ("horizontal_reach", b.horizontal_reach), ("sharpened_arc", b.sharpened_arc)] {
        if !(v >= floor) { r.push(Reject::BladeTooShort { measure: name, mm: v }); }
    }
    if !(b.sharpened_arc <= limits::BLADE_EDGE_MAX_MM) { r.push(Reject::BladeEdgeTooLong(b.sharpened_arc)); }
    r
}

/// True for the blade-length rejects (floor or 4.0 in edge cap).
pub fn is_blade_len(x: &Reject) -> bool { matches!(x, Reject::BladeTooShort { .. } | Reject::BladeEdgeTooLong(_)) }

fn hypot(p: (f64, f64)) -> f64 { p.0.hypot(p.1) }

/// Radial std-dev (mm) of outline points on the inner and outer sharpened edges.
/// Measured in the un-raked blade frame (`Phenotype::to_blade_local`) so the blade-angle knob
/// does not hide or fake serrations; grip/ricasso points land below y = -2 there and are skipped.
fn edge_ripple(g: &Genotype, p: &Phenotype) -> (f64, f64) {
    let mid = g.curve_radius;
    let local: Vec<(f64, f64)> = p.outline.iter().map(|&q| p.to_blade_local(q)).collect();
    let inner = band_ripple(&local, g.r_in() - 0.3, mid - 0.4);
    let outer = band_ripple(&local, mid + 0.4, g.r_out() + 0.3);
    (inner, outer)
}

fn band_ripple(outline: &[(f64, f64)], lo: f64, hi: f64) -> f64 {
    let rs: Vec<f64> = outline.iter().filter_map(|p| {
        if p.1 <= -2.0 { return None; }
        let r = hypot(*p);
        if r >= lo && r <= hi { Some(r) } else { None }
    }).collect();
    if rs.len() < 8 { return 0.0; }
    let mean = rs.iter().sum::<f64>() / rs.len() as f64;
    (rs.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / rs.len() as f64).sqrt()
}

/// Horizontal extent (mm) of the blade planform above the guard line.
fn geom_reach(outline: &[(f64, f64)]) -> f64 {
    let mut lo = f64::MAX;
    let mut hi = f64::MIN;
    let mut n = 0usize;
    for p in outline {
        if p.1 > -0.5 { lo = lo.min(p.0); hi = hi.max(p.0); n += 1; }
    }
    if n < 3 { 0.0 } else { hi - lo }
}

fn max_edge(p: &[(f64, f64)]) -> f64 {
    if p.len() < 2 { return f64::MAX; }
    let mut m = 0.0f64;
    for i in 0..p.len() {
        let a = p[i]; let b = p[(i + 1) % p.len()];
        m = m.max(hypot((a.0 - b.0, a.1 - b.1)));
    }
    m
}


#[cfg(test)]
mod tests {
    use super::*;
    use jarambit_genotype::{Rng, TiGrade};
    fn has(g: &Genotype, f: impl Fn(&Reject) -> bool) -> bool { let p = Phenotype::from_genotype(g); check(g, &p).err().map(|v| v.iter().any(|x| f(x))).unwrap_or(false) }
    #[test] fn random_designs_pass_every_non_blade_gate() {
        // Every repaired random design must pass all gates except the blade-length floor and the
        // holder envelope width (a long raked blade can overrun the frozen 100 mm holder; that is a
        // real reject the search must steer around, not a repair bug).
        let mut r = Rng(7); let mut bad = 0;
        for _ in 0..2000 { let g = Genotype::random(&mut r); let p = Phenotype::from_genotype(&g);
            if let Err(e) = check(&g, &p) { let e: Vec<_> = e.into_iter().filter(|x| !is_blade_len(x) && !matches!(x, Reject::Holder(s) if s.starts_with("outside holder envelope"))).collect();
                if !e.is_empty() { bad += 1; if bad < 5 { eprintln!("{e:?}"); } } } }
        assert_eq!(bad, 0, "repaired random designs should pass every non-blade gate");
    }
    #[test] fn random_designs_meet_edge_arc_window() {
        // the 72 mm cap is gone: repaired genes put the sharpened arc inside [86.225, 101.6] mm
        let mut r = Rng(8);
        for _ in 0..2000 { let g = Genotype::random(&mut r); let a = Phenotype::from_genotype(&g).blade.sharpened_arc;
            assert!(a >= limits::BLADE_FLOOR_MM && a <= limits::BLADE_EDGE_MAX_MM, "arc {a}"); }
    }
    fn metrics(tth: f64, reach: f64, arc: f64) -> jarambit_phenotype::BladeMetrics {
        jarambit_phenotype::BladeMetrics { tip_to_heel: tth, horizontal_reach: reach, sharpened_arc: arc, sharpened_arc_outer: arc, sharpened_arc_inner: arc - 10.0, vertical_rise: 40.0, sweep_deg: 90.0, ..Default::default() }
    }
    const IN: f64 = 25.4;
    #[test] fn switchback_381in_blade_passes() {
        // SWITCHBACK-like: 3.81 in sharpened edge, tip-heel 3.50 in, horizontal reach 3.40 in -> all >= 3.375 in
        let b = metrics(3.50 * IN, 3.40 * IN, 3.81 * IN);
        assert!(blade_length_rejects(&b).is_empty(), "{:?}", blade_length_rejects(&b));
        // and through the full gate: blade metrics are the ONLY thing that changes vs a non-blade-clean design
        let g = switchback_genome(); let mut p = Phenotype::from_genotype(&g); p.blade = b;
        assert_eq!(check(&g, &p), Ok(()));
    }
    #[test] fn stub_44mm_blade_fails_all_three() {
        // mh1-era stub (tip 44 / reach 33 / arc 54.5 mm) -> rejected on every measure
        let e = blade_length_rejects(&metrics(44.0, 33.0, 54.5));
        for m in ["tip_to_heel", "horizontal_reach", "sharpened_arc"] {
            assert!(e.iter().any(|x| matches!(x, Reject::BladeTooShort { measure, .. } if *measure == m)), "{m} {e:?}");
        }
        // real phenotype with the old 45 mm arc gene (bypass clamp) is rejected by check()
        let mut g = Genotype::random(&mut Rng(13)); g.blade_arc_len = 45.0; g.curve_radius = 30.0;
        let p = Phenotype::from_genotype(&g); assert!(p.blade.tip_to_heel < 50.0, "{:?}", p.blade);
        let e = check(&g, &p).unwrap_err();
        assert_eq!(e.iter().filter(|x| matches!(x, Reject::BladeTooShort { .. })).count(), 3, "{e:?}");
    }
    #[test] fn rejects_any_single_measure_under_floor() {
        let ok = (3.50 * IN, 3.40 * IN, 3.81 * IN);
        for (i, m) in ["tip_to_heel", "horizontal_reach", "sharpened_arc"].iter().enumerate() {
            for v in [44.0, 85.0, 85.725, 86.2] { // 85.725..86.225 sits inside the 0.5 mm guard -> still rejected
                let mut x = [ok.0, ok.1, ok.2]; x[i] = v;
                let e = blade_length_rejects(&metrics(x[0], x[1], x[2]));
                assert_eq!(e, vec![Reject::BladeTooShort { measure: m, mm: v }], "{m}={v}");
            }
            let mut x = [ok.0, ok.1, ok.2]; x[i] = limits::BLADE_FLOOR_MM;
            assert!(blade_length_rejects(&metrics(x[0], x[1], x[2])).is_empty(), "exactly at floor passes");
        }
        assert!(blade_length_rejects(&metrics(ok.0, ok.1, f64::NAN)).iter().any(|x| matches!(x, Reject::BladeTooShort { .. })));
    }
    #[test] fn rejects_edge_arc_over_4in() {
        let e = blade_length_rejects(&metrics(3.5 * IN, 3.4 * IN, 4.05 * IN));
        assert_eq!(e, vec![Reject::BladeEdgeTooLong(4.05 * IN)]);
        assert!(blade_length_rejects(&metrics(3.5 * IN, 3.4 * IN, limits::BLADE_EDGE_MAX_MM)).is_empty());
    }
    #[test] fn floor_constants() {
        assert!((limits::BLADE_LIMIT_MM - 85.725).abs() < 1e-9);
        assert!((limits::BLADE_FLOOR_MM - 86.225).abs() < 1e-9);
        assert!((limits::BLADE_EDGE_MAX_MM - 101.6).abs() < 1e-9);
    }
    /// SWITCHBACK-like genome found with the blade-angle + hawkbill-sweep knobs (3.81 in class edge).
    pub(crate) fn switchback_genome() -> Genotype {
        let mut g = Genotype::random(&mut Rng(9));
        g.blade_arc_len = SB_ARC; g.curve_radius = SB_RADIUS; g.blade_angle_deg = SB_ANGLE; g.ring_wall = 4.5;
        g.clamp(); g
    }
    // arc gene 87.55 -> 96.77 mm (3.81 in) sharpened edge; radius clamps to the 56 deg sweep limit.
    const SB_ARC: f64 = 87.55; const SB_RADIUS: f64 = 90.0; const SB_ANGLE: f64 = 13.0;
    #[test] fn switchback_genotype_passes_all_three_and_full_gate() {
        // Real phenotype (not injected metrics): ~3.81 in sharpened edge, tip-heel and horizontal
        // reach both >= 86.225 mm simultaneously, edge <= 101.6 mm, and every other gate passes.
        let g = switchback_genome(); let p = Phenotype::from_genotype(&g); let b = &p.blade;
        eprintln!("switchback genome: {b:?} bbox {:?}", p.bbox);
        assert!(b.horizontal_reach >= limits::BLADE_FLOOR_MM, "reach {}", b.horizontal_reach);
        assert!(b.sharpened_arc >= limits::BLADE_FLOOR_MM && b.sharpened_arc <= limits::BLADE_EDGE_MAX_MM, "arc {}", b.sharpened_arc);
        assert!(b.tip_to_heel >= limits::BLADE_FLOOR_MM, "tip-heel {}", b.tip_to_heel);
        assert!((b.sharpened_arc / IN - 3.81).abs() < 0.08, "3.81 in class edge, got {:.3} in", b.sharpened_arc / IN);
        assert!(b.sweep_deg >= limits::MIN_SWEEP_DEG && b.rake_deg > 0.0);
        assert_eq!(check(&g, &p), Ok(()));
    }
    #[test] fn stub_44mm_genotype_fails_all_three_even_with_knob() {
        // mh1-era 44 mm stub through the real phenotype at every blade angle: always rejected on all three.
        for a in [-5.0, 0.0, 10.0, 25.0] {
            let mut g = Genotype::random(&mut Rng(13)); g.blade_arc_len = 45.0; g.curve_radius = 30.0; g.blade_angle_deg = a;
            let p = Phenotype::from_genotype(&g); assert!(p.blade.tip_to_heel < 50.0, "{:?}", p.blade);
            let e = check(&g, &p).unwrap_err();
            assert_eq!(e.iter().filter(|x| matches!(x, Reject::BladeTooShort { .. })).count(), 3, "angle {a}: {e:?}");
        }
    }
    #[test] fn knob_makes_all_three_floor_reachable() {
        // Replaces the old canary: with the blade-angle knob the phenotype CAN put all three measures
        // over the floor with the edge <= 4.0 in, and some of those designs clear every gate.
        let (mut all3, mut legal) = (0, 0);
        for i in 0..=30 { for j in 0..=12 { for k in 0..=6 {
            let mut g = Genotype::random(&mut Rng(51)); g.ring_wall = 4.2;
            g.curve_radius = 45.0 + i as f64; g.blade_arc_len = 86.0 + 0.5 * j as f64; g.blade_angle_deg = -5.0 + 5.0 * k as f64;
            g.clamp();
            let p = Phenotype::from_genotype(&g);
            if blade_length_rejects(&p.blade).is_empty() { all3 += 1; if check(&g, &p).is_ok() { legal += 1; } }
        } } }
        assert!(all3 > 0 && legal > 0, "all-three {all3} fully legal {legal}");
    }
    #[test] fn legacy_unraked_genome_is_unchanged() {
        // The knob only rakes forward: a legacy genome (angle = LEGACY) gets zero rake.
        let mut g = Genotype::random(&mut Rng(5)); g.blade_angle_deg = jarambit_genotype::LEGACY_BLADE_ANGLE_DEG;
        let p = Phenotype::from_genotype(&g);
        assert!(p.blade.rake_deg.abs() < 1e-12 && p.blade_rot == 0.0);
        let q = (12.3, -4.5); let r = p.from_blade_local(p.to_blade_local(q));
        assert!((q.0 - r.0).abs() < 1e-9 && (q.1 - r.1).abs() < 1e-9);
    }
    #[test] fn rejects_straight() { let mut g = Genotype::random(&mut Rng(9)); g.sweep_override_deg = Some(10.0); assert!(has(&g, |x| *x == Reject::NotCurved)); }
    #[test] fn rejects_single_serrated() { let mut g = Genotype::random(&mut Rng(9)); g.serr_outer.depth = 0.0; assert!(has(&g, |x| *x == Reject::NotDoubleSerrated)); }
    #[test] fn rejects_disconnected() {
        let g = Genotype::random(&mut Rng(11)); let mut p = Phenotype::from_genotype(&g);
        for q in p.ring_hole.iter_mut() { q.0 += 500.0; }
        assert!(check(&g, &p).unwrap_err().contains(&Reject::Disconnected));
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
    #[test] fn rejects_smooth_edge_even_if_tooth_count_lies() {
        let g = Genotype::random(&mut Rng(31));
        let mut p = Phenotype::from_genotype(&g);
        let mid = g.curve_radius;
        let pc = p.clone();
        for q in p.outline.iter_mut() {
            let l = pc.to_blade_local(*q);
            let r = hypot(l);
            if l.1 > -1.0 && r > mid + 0.4 && r < g.r_out() + 0.5 { *q = pc.from_blade_local((g.r_out() * l.0 / r, g.r_out() * l.1 / r)); }
        }
        let e = check(&g, &p).unwrap_err();
        assert!(e.iter().any(|x| *x == Reject::NotDoubleSerrated), "{e:?}");
    }
    #[test] fn rejects_straight_planform_even_if_metrics_lie() {
        let g = Genotype::random(&mut Rng(33));
        let mut p = Phenotype::from_genotype(&g);
        let heel_x = p.outline.iter().filter(|q| q.1.abs() < 0.2).map(|q| q.0).fold(0.0, f64::min);
        for q in p.outline.iter_mut() { if q.1 > -0.5 { q.0 = heel_x; } }
        p.blade.sweep_deg = 90.0;
        p.blade.vertical_rise = 40.0;
        p.blade.tip_to_heel = 40.0;
        p.blade.horizontal_reach = 20.0;
        p.blade.sharpened_arc = 50.0;
        let e = check(&g, &p).unwrap_err();
        assert!(e.iter().any(|x| matches!(x, Reject::NotKarambit(_))), "{e:?}");
    }
    #[test] fn rejects_spiked_outline() {
        let g = Genotype::random(&mut Rng(35));
        let mut p = Phenotype::from_genotype(&g);
        p.outline[0].0 += 400.0;
        assert!(check(&g, &p).unwrap_err().contains(&Reject::Disconnected));
    }
    #[test] fn rejects_tiny_brand_pad_and_skewed_pad() {
        let mut g = Genotype::random(&mut Rng(37));
        g.brand_pad_w = 2.0; g.brand_pad_l = 2.0;
        assert!(has(&g, |x| matches!(x, Reject::BrandPad(_))));
        let g = Genotype::random(&mut Rng(38));
        let mut p = Phenotype::from_genotype(&g);
        p.brand_pad[1].1 += 3.0;
        assert!(check(&g, &p).unwrap_err().iter().any(|x| matches!(x, Reject::BrandPad(_))));
    }
    #[test] fn rejects_holder_force_outside_window() {
        let mut soft = Genotype::random(&mut Rng(41));
        soft.holder.holder_wall = 0.45;
        let e = check(&soft, &Phenotype::from_genotype(&soft)).unwrap_err();
        assert!(e.iter().any(|x| matches!(x, Reject::Holder(s) if s.contains("insertion force"))), "{e:?}");
        let mut stiff = Genotype::random(&mut Rng(42));
        stiff.holder.holder_wall = 3.2;
        stiff.holder.detent_depth = 1.2;
        stiff.thickness = 2.5; // keep the stack check from being the only failure mode
        let e = check(&stiff, &Phenotype::from_genotype(&stiff)).unwrap_err();
        assert!(e.iter().any(|x| matches!(x, Reject::Holder(s) if s.contains("insertion force") || s.contains("draw force"))), "{e:?}");
    }
    #[test] fn in_spec_holder_forces_sit_in_window() {
        let mut r = Rng(43);
        for _ in 0..500 {
            let g = Genotype::random(&mut r);
            let f = holder_forces(g.holder.holder_wall, g.holder.detent_depth);
            assert!(f.insertion_n >= holder::INSERT_N.0 && f.insertion_n <= holder::INSERT_N.1, "{f:?} wall {} detent {}", g.holder.holder_wall, g.holder.detent_depth);
            assert!(f.draw_n >= holder::DRAW_N.0 && f.draw_n <= holder::DRAW_N.1, "{f:?}");
            assert!(f.draw_n < f.insertion_n);
        }
    }
    #[test] fn new_gates_spare_the_tolerance_cloud() {
        // Boundary genes (ring ID, edge angle, ring wall, detent) already fail in the tails.
        // The geometric serration, hook, brand-pad and holder-force gates must not add to that.
        let mut r = Rng(47);
        let mut novel = 0;
        let mut n = 0;
        for _ in 0..40 {
            let g = Genotype::random(&mut r);
            for i in 0..40 {
                let mut rng = jarambit_genotype::Rng(1000 + i);
                let h = jarambit_monte_carlo::perturb(&g, &mut rng);
                let p = Phenotype::from_genotype(&h);
                n += 1;
                if let Err(e) = check(&h, &p) {
                    let hit = e.iter().any(|x| match x {
                        Reject::NotDoubleSerrated | Reject::NotKarambit(_) | Reject::Disconnected | Reject::BrandPad(_) => true,
                        Reject::Holder(s) if s.contains("force") => true,
                        _ => false,
                    });
                    if hit { novel += 1; }
                }
            }
        }
        let rate = novel as f64 / n as f64;
        assert!(rate < 0.01, "new gates rejected {novel}/{n} ({rate}) tolerance samples");
    }
}

