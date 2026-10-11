use crate::aesthetic::{self, *};
use crate::c4_ref as c4;
use crate::genome::*;
use crate::geom::*;
use crate::pheno::*;
use jarambit_genotype::Rng;

fn c4_stock_genome() -> Genome {
    // Rev C.4 as built: 3.175 mm Gr5, tip 2.6, taper from x=130, grinds 6.0 / 5.0 mm wide, 0.6 mm flutes,
    // spine sharpened from its C.4 start. Bypasses clamp() on purpose (C.4 stock < crescent floor).
    let mut g = Genome::c4_seed(5.7);
    g.v[T] = 3.175; g.v[T_TIP] = 2.6; g.v[TAPER_X0] = 130.0; g.v[SPINE_OFF] = 0.0;
    g.v[EA_IN] = ((3.175 - 0.5) / 2.0 / 6.0f64).atan().to_degrees(); g.v[EA_SP] = ((3.175 - 0.5) / 2.0 / 5.0f64).atan().to_degrees();
    g
}

#[test] fn seed_reproduces_c4_silhouette_and_blade() {
    let p = build(&Genome::c4_seed(5.7));
    let h = hausdorff(&densify(&p.outline, 0.25, true), &densify(&c4::EXTERIOR, 0.25, true));
    eprintln!("seed Hausdorff vs C.4 {h:.3} mm; blade {:?}; grip {:.2}", p.blade, p.grip_len);
    assert!(h < 1.5, "seed Hausdorff {h}");
    assert!((p.blade.tip_to_heel - 96.655).abs() < 1.0 && (p.blade.horizontal_reach - 87.005).abs() < 0.5 && (p.blade.arc_in - 101.17).abs() < 1.0, "{:?}", p.blade);
    assert!((p.grip_len - 60.5).abs() < 0.6, "grip {}", p.grip_len);
}

#[test] fn c4_stock_mass_matches_c4_record() {
    let g = c4_stock_genome(); let p = build(&g);
    eprintln!("C.4 at 3.175 mm: finished {:.2} g (C.4 record 48.3 g gen.py / 48.47 g B-rep), blank {:.2} g (56.3), area {:.0} mm2 (4003.6)", p.mass_g, p.blank_g, p.area_mm2);
    assert!((p.blank_g - 56.3).abs() / 56.3 < 0.04, "blank {}", p.blank_g);
    assert!((p.mass_g - 48.3).abs() / 48.3 < 0.06, "finished {}", p.mass_g);
}

#[test] fn seed_passes_aesthetic_floor() {
    let g = Genome::c4_seed(5.7); let p = build(&g); let a = aesthetic::evaluate(&g, &p);
    eprintln!("seed aesthetic {a:?}");
    assert!(a.pass, "{:?}", a.fails);
}

/// The legacy stick figure (straight grip rails + annular blade + ring) must FAIL the floor.
#[test] fn stick_figure_fails_aesthetic_floor() {
    use jarambit_phenotype::Phenotype;
    let rf = reference();
    for seed in [1u64, 2, 3] {
        let mut g = jarambit_genotype::Genotype::random(&mut Rng(seed)); g.blade_arc_len = 87.55; g.curve_radius = 90.0; g.blade_angle_deg = 13.0; g.clamp();
        let s = Phenotype::from_genotype(&g);
        let rc = s.ring_center;
        for mirror in [1.0, -1.0] {
            // grip axis -> +x, ring centre -> origin
            let o: Vec<P2> = s.outline.iter().map(|q| (q.1 - rc.1, mirror * (q.0 - rc.0))).collect();
            let tip = (s.blade.tip.1 - rc.1, mirror * (s.blade.tip.0 - rc.0));
            let h = hausdorff(&densify(&o, 0.25, true), &rf.c4_dense);
            let (hist, straight, _) = shape_stats(&o, tip);
            let e = emd(&hist, &rf.hist);
            eprintln!("stick figure seed {seed} mirror {mirror}: H {h:.1} mm, EMD {e:.3}, straight {straight:.1} mm (C.4 {:.1})", rf.straight);
            assert!(h > HAUSDORFF_MAX_MM && (straight > rf.straight + STRAIGHT_SLACK_MM || e > EMD_MAX));
        }
    }
}

/// Not stick-figure restrictive: GA-style random walks from the C.4 seed (5 envelope mutations)
/// mostly stay aesthetic passers while spreading in silhouette AND in the 3-D descriptor space.
/// Uniform white noise over the whole envelope is reported (it is mostly rejected, by design).
#[test] fn envelope_is_expressive_but_bounded() {
    let mut r = Rng(77); let (mut pass, mut n) = (0, 0); let mut hs = Vec::new(); let mut ds = Vec::new();
    let seed = Genome::c4_seed(5.7);
    for _ in 0..120 { let mut g = seed.clone(); for _ in 0..5 { g = g.mutate(&mut r, 0.15); }
        let p = build(&g); let a = aesthetic::evaluate(&g, &p);
        n += 1; if a.pass { pass += 1; hs.push(a.hausdorff); ds.push(crate::qd::descriptor(&g, &p)); } }
    let spread = ds.iter().flat_map(|a| ds.iter().map(move |b| a.iter().zip(b).map(|(x, y)| (x - y).powi(2)).sum::<f64>().sqrt())).fold(0.0, f64::max);
    let hmax = hs.iter().cloned().fold(0.0, f64::max);
    let (mut wp, mut wn) = (0, 0); for _ in 0..40 { let g = Genome::random_in_envelope(&mut r); let p = build(&g); wn += 1; if aesthetic::evaluate(&g, &p).pass { wp += 1; } }
    eprintln!("walks: aesthetic pass {pass}/{n}, Hausdorff max {hmax:.2} mm, descriptor spread {spread:.2}; white-noise envelope pass {wp}/{wn}");
    assert!(pass * 2 >= n, "envelope too tight: {pass}/{n}");
    assert!(hmax > 1.5 && spread > 0.5, "not expressive: H {hmax} spread {spread}");
    assert!(hs.iter().all(|h| *h <= HAUSDORFF_MAX_MM));
}

#[test] fn seed_solid_is_watertight() {
    let p = build(&Genome::c4_seed(5.7));
    let s = crate::export::solid(&p, 4.0).expect("mesh");
    let (once, more, dmax) = crate::export::census(&s.tris);
    let v = crate::export::volume(&s);
    eprintln!("solid tris {} once {once} more {more} dir_max {dmax} vol {:.0} mm3 (raster {:.0})", s.tris.len(), v, p.mass_g / 4.43 * 1000.0);
    assert_eq!((once, more, dmax), (0, 0, 1));
    let st = crate::export::step(&s, "seed"); assert!(st.contains("MANIFOLD_SOLID_BREP") && st.contains("CLOSED_SHELL"));
}

#[test] fn uniform_thickness_field_matches_uniform_plate() {
    use jarambit_physics::fine;
    let p = build(&Genome::c4_seed(5.7));
    let m = fine::mesh_domain(&dp_closed(&p.outline, 0.05), &[dp_closed(&p.holes[0], 0.05)], 8.0).unwrap();
    let ne = m.tris.len();
    let a = fine::Plate::new(m.clone(), 5.0, 113800.0, 0.34);
    let b = fine::Plate::new(m, 5.0, 113800.0, 0.34).with_thickness(vec![5.0; ne]);
    let n = a.n(); let fix: Vec<bool> = (0..n * 5).map(|d| a.mesh.on_hole[d / 5]).collect();
    let mut f = vec![0.0; n * 5]; f[(0..n).filter(|&i| a.mesh.on_outer[i]).last().unwrap() * 5 + 2] = 1.0;
    let (sa, sb) = (a.stresses(&a.solve(&a.system(&fix).unwrap(), &f)).1, b.stresses(&b.solve(&b.system(&fix).unwrap(), &f)).1);
    let d = sa.iter().zip(&sb).map(|(x, y)| (x - y).abs() / x.abs().max(1e-9)).fold(0.0, f64::max);
    assert!(d < 1e-9, "max rel diff {d}");
}

#[test] fn seed_fem_runs() {
    let p = build(&Genome::c4_seed(5.7));
    let (f, _) = crate::fem::run(&p, 4.0, false).expect("fem");
    eprintln!("seed FEM (coarse 4 mm2): {f:?} mass {:.1} g", p.mass_g);
    assert!(f.lat20 > 0.0 && f.ring20 > 0.0);
}

#[test] fn machining_layer_keeps_web_floor_and_is_watertight() {
    let mut g = Genome::c4_seed(6.0);
    g.v[ISO_D] = 1.6; g.v[ISO_ZB] = 1.0; g.v[ISO_ZL] = 1.0; g.v[ISO_XB] = 0.6; g.v[RFL_D] = 2.0; g.v[RFL_W] = 0.7; g.v[RFL_ARC] = 240.0;
    g.v[PERF_D] = 4.0; g.v[PERF_ZL] = 1.0; g.v[WIN_N] = 5.0; g.v[EA_IN] = 22.0; g.v[EA_SP] = 22.0; g.clamp();
    let p = build(&g);
    assert!(p.removed[5] > 50.0 && p.removed[6] > 50.0, "isogrid / ring flute inactive: {:?}", p.removed);
    assert!(p.min_web >= (0.3 * p.t).max(1.5) - 1e-6, "web floor violated: {}", p.min_web);
    let s = crate::export::solid(&p, 2.0).expect("solid");
    let (once, more, _) = crate::export::census(&s.tris);
    assert_eq!((once, more), (0, 0), "not watertight");
    let mut go = g.clone(); go.v[ISO_D] = 0.0; go.v[RFL_D] = 0.0; go.v[PERF_D] = 0.0; go.v[WIN_N] = 0.0; let off = build(&go);
    assert!(p.mass_g < off.mass_g - 1.0, "machining removed no mass");
}

#[test] fn legacy_rows_load_with_machining_off() {
    let g = Genome::c4_seed(5.7);
    let mut row: Vec<String> = g.v[..NG_LEGACY].iter().map(|x| format!("{x:.4}")).collect(); row.push("Ti-6Al-4V".into());
    let f: Vec<&str> = row.iter().map(|s| s.as_str()).collect();
    let h = Genome::from_csv(&f).expect("legacy row");
    assert_eq!(h.v.len(), NG); assert_eq!(&h.v[NG_LEGACY..], &MACHINING_OFF[..]);
    assert!((build(&h).mass_g - build(&g).mass_g).abs() < 1e-6);
}
