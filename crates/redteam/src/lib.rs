//! Red-team gate: reject anything that is not a recognizable, connected,
//! curved, double-edged, double-serrated SWITCHBACK utility karambit.
use jarambit_genotype::Genotype;
use jarambit_phenotype::{shoelace, Phenotype};

#[derive(Debug, Clone, PartialEq)]
pub enum Reject { NotCurved, NoFingerRing, NotDoubleSerrated, Disconnected, UnsafeGeometry(String), ThicknessPrecision }

pub fn check(g: &Genotype, p: &Phenotype) -> Result<(), Vec<Reject>> {
    let mut r = vec![];
    if g.sweep_deg < 55.0 || g.curve_radius > 60.0 { r.push(Reject::NotCurved); }
    if p.ring_hole.len() < 16 || g.ring_id < 22.0 { r.push(Reject::NoFingerRing); }
    if p.inner_teeth < 3 || p.outer_teeth < 3 || g.serr_inner.depth <= 0.0 || g.serr_outer.depth <= 0.0 { r.push(Reject::NotDoubleSerrated); }
    // connectivity: one outer boundary, one hole fully inside it, positive net area
    let inside = p.ring_hole.iter().all(|&q| point_in_poly(q, &p.outline));
    if !inside || shoelace(&p.outline).abs() <= shoelace(&p.ring_hole).abs() { r.push(Reject::Disconnected); }
    if g.ring_wall < 4.0 { r.push(Reject::UnsafeGeometry("ring wall < 4 mm".into())); }
    if g.thickness < 2.5 { r.push(Reject::UnsafeGeometry("stock < 2.5 mm".into())); }
    if ((g.thickness * 10.0).round() - g.thickness * 10.0).abs() > 1e-9 { r.push(Reject::ThicknessPrecision); }
    if r.is_empty() { Ok(()) } else { Err(r) }
}

pub fn point_in_poly(q: (f64, f64), poly: &[(f64, f64)]) -> bool {
    let mut c = false; let n = poly.len(); let mut j = n - 1;
    for i in 0..n {
        let (xi, yi) = poly[i]; let (xj, yj) = poly[j];
        if ((yi > q.1) != (yj > q.1)) && (q.0 < (xj - xi) * (q.1 - yi) / (yj - yi) + xi) { c = !c; }
        j = i;
    }
    c
}

#[cfg(test)]
mod tests {
    use super::*;
    use jarambit_genotype::Rng;
    #[test] fn random_designs_pass_gate() {
        let mut r = Rng(7);
        for _ in 0..200 { let g = Genotype::random(&mut r); let p = Phenotype::from_genotype(&g); assert!(check(&g, &p).is_ok(), "{:?}", check(&g, &p)); }
    }
    #[test] fn rejects_straight_and_single_serrated() {
        let mut r = Rng(9);
        let mut g = Genotype::random(&mut r); g.sweep_deg = 10.0; // bypass clamp: straight-ish
        let p = Phenotype::from_genotype(&g);
        assert!(check(&g, &p).unwrap_err().contains(&Reject::NotCurved));
        let mut g2 = Genotype::random(&mut r); g2.serr_outer.depth = 0.0;
        let p2 = Phenotype::from_genotype(&g2);
        assert!(check(&g2, &p2).unwrap_err().contains(&Reject::NotDoubleSerrated));
    }
    #[test] fn rejects_disconnected() {
        let mut r = Rng(11);
        let g = Genotype::random(&mut r); let mut p = Phenotype::from_genotype(&g);
        for q in p.ring_hole.iter_mut() { q.0 += 500.0; } // hole outside body
        assert!(check(&g, &p).unwrap_err().contains(&Reject::Disconnected));
    }
}
