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

fn hypot(p: (f64, f64)) -> f64 { p.0.hypot(p.1) }

/// Radial std-dev (mm) of outline points on the inner and outer sharpened edges.
fn edge_ripple(g: &Genotype, p: &Phenotype) -> (f64, f64) {
    let mid = g.curve_radius;
    let inner = band_ripple(&p.outline, g.r_in() - 0.3, mid - 0.4);
    let outer = band_ripple(&p.outline, mid + 0.4, g.r_out() + 0.3);
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
    #[test] fn rejects_smooth_edge_even_if_tooth_count_lies() {
        let g = Genotype::random(&mut Rng(31));
        let mut p = Phenotype::from_genotype(&g);
        let mid = g.curve_radius;
        for q in p.outline.iter_mut() {
            let r = hypot(*q);
            if q.1 > -1.0 && r > mid + 0.4 && r < g.r_out() + 0.5 { *q = (g.r_out() * q.0 / r, g.r_out() * q.1 / r); }
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
