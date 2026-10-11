use crate::aesthetic::{self, *};
use crate::c5_ref as c4;
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
    eprintln!("seed Hausdorff vs C.5 {h:.3} mm; blade {:?}; grip {:.2}", p.blade, p.grip_len);
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

#[test]
fn c6_groove_on_seed_and_lighter_than_c5() {
    let g = crate::genome::Genome::c6_seed(5.7);
    let p = crate::pheno::build(&g);
    assert!((p.groove_w - 3.1).abs() < 1e-6, "groove width {}", p.groove_w);
    // C.6 nominal annulus 14.3-17.4 = 308.7 mm^2 per face, minus the part the crescent body does not cover
    assert!(p.groove_area > 200.0 && p.groove_area < 320.0, "groove area {}", p.groove_area);
    let a = crate::aesthetic::evaluate(&g, &p);
    assert!(a.pass, "C.6 seed must pass its own aesthetic floor: {:?}", a.fails);
    let dm = p.groove_area * 1.2 * 4.43e-3;
    assert!(dm > 1.0 && dm < 1.7, "groove mass {dm}");
}


// ---------------- D1: chord-torsion fixture vs bending couple + rectangular-strip benchmark ----------------
/// Strip L x b x t along unit direction d (angle th), clamped at s = 0, unit-magnitude slope load at s = L
/// along `load_dir`. Returns the max bending-surface von Mises over the mid-span window |s - L/2| <= b/2.
fn strip_peak(l: f64, b: f64, t: f64, th: f64, load_dir: P2, area: f64) -> f64 {
    use jarambit_physics::fine;
    let (d, n) = ((th.cos(), th.sin()), (-th.sin(), th.cos()));
    let at = |s: f64, w: f64| (s * d.0 + w * n.0, s * d.1 + w * n.1);
    let outer = vec![at(0.0, -b / 2.0), at(l, -b / 2.0), at(l, b / 2.0), at(0.0, b / 2.0)];
    let mesh = fine::mesh_domain(&outer, &[], area).unwrap();
    let plate = fine::Plate::new(mesh, t, 113_800.0, fine::NU);
    let xy = plate.mesh.xy.clone(); let nn = xy.len();
    let s_of = |q: P2| q.0 * d.0 + q.1 * d.1;
    let mut fix = vec![false; nn * 5];
    for i in 0..nn { if s_of(xy[i]).abs() < 1e-6 { for c in 0..5 { fix[i * 5 + c] = true; } } }
    let end: Vec<usize> = (0..nn).filter(|&i| (s_of(xy[i]) - l).abs() < 1e-6).collect();
    let k = end.len() as f64;
    let mut f = vec![0.0; nn * 5];
    for &i in &end { f[i * 5 + 3] = load_dir.0 / k; f[i * 5 + 4] = load_dir.1 / k; }
    let sys = plate.system(&fix).unwrap();
    let (_, sb) = plate.stresses(&plate.solve(&sys, &f));
    (0..plate.mesh.tris.len()).filter(|&e| (s_of(plate.centroid(e)) - l / 2.0).abs() <= b / 2.0).map(|e| sb[e]).fold(0.0, f64::max)
}

#[test] fn d1_st_venant_alpha_matches_table() {
    use crate::fem::alpha_rect;
    // Timoshenko & Goodier / Roark: alpha (tau_max = T / (alpha b t^2)) for b/t = 1, 2, 3, 4, 10, inf
    for (r, a) in [(1.0, 0.208), (2.0, 0.246), (3.0, 0.267), (4.0, 0.282), (10.0, 0.312), (1e6, 0.3333)] {
        let got = alpha_rect(r); eprintln!("alpha(b/t={r}) = {got:.4} (table {a})");
        assert!((got - a).abs() / a < 0.01, "alpha({r}) {got} vs {a}");
    }
}

/// The knife fixture's load convention (slope dofs w_x, w_y): load along n = (-d_y, d_x) is a TORQUE about d
/// (thin-strip St-Venant 3T/(b t^2) shear, von Mises sqrt(3) x); load along d is a BENDING couple (6M/(b t^2)).
/// Pre-D1 crescent used d -> its "twist" was a bending couple. Strip at 30 deg exercises both slope dofs.
#[test] fn d1_chord_torsion_vs_bending_couple_strip() {
    let (l, b, th) = (200.0, 20.0, 30f64.to_radians());
    let (d, n) = ((th.cos(), th.sin()), (-th.sin(), th.cos()));
    for t in [2.0, 5.0, 6.6667] {
        let tor = strip_peak(l, b, t, th, n, 1.0); let ben = strip_peak(l, b, t, th, d, 1.0);
        let thin = 3f64.sqrt() * 3.0 / (b * t * t); let bend = 6.0 / (b * t * t);
        let s3d = 3f64.sqrt() / (crate::fem::alpha_rect(b / t) * b * t * t);
        eprintln!("strip b/t {:.1}: torsion load plate {tor:.5} vs thin-strip {thin:.5} (ratio {:.3}); 3D St-Venant {s3d:.5} (3D/plate {:.3}); couple load plate {ben:.5} vs 6M/bt^2 {bend:.5} (ratio {:.3})",
            b / t, tor / thin, s3d / tor, ben / bend);
        assert!((tor / thin - 1.0).abs() < 0.06, "torsion load is not St-Venant torsion: {}", tor / thin);
        assert!((ben / bend - 1.0).abs() < 0.06, "couple load is not beam bending: {}", ben / bend);
        // the two loads are different physics (vm ratio sqrt(3)*3 / 6 = 0.866 in the thin limit)
        assert!((tor / ben - 0.866).abs() < 0.06);
        // 3D correction factor used by the knife fixture reproduces the exact 3D peak from the plate peak
        assert!((tor * crate::fem::torsion_3d_factor(b / t) / s3d - 1.0).abs() < 0.06);
    }
}

/// Knife fixture: the corrected chord-torsion capacity differs from the pre-D1 couple, and the D1 fields are sane.
#[test] fn d1_knife_fixture_reports_torsion_and_couple() {
    let p = build(&Genome::c6_seed(5.7));
    let f = crate::fem::run_unbiased(&p, 1.0).expect("fem");
    eprintln!("C.6 seed t5.7 @1.0 mm^2: chord torsion {:.0} N*mm (3D k {:.3}, b {:.1} mm, t {:.2} mm, at {:?}), pre-D1 couple {:.0} N*mm, joint+3D {:.0} N*mm SF {:.3}; seq {:.2} ({})",
        f.twist20_nmm, f.twist_kc, f.twist_b_mm, f.twist_t_mm, f.twist_at, f.couple20_nmm, f.twist_joint_nmm, f.twist_sf, f.seq_ratio, f.seq_case);
    assert!(f.twist20_nmm.is_finite() && f.couple20_nmm.is_finite() && f.twist_kc >= 1.0 && f.twist_b_mm > 0.5);
    assert!((f.twist20_nmm / f.couple20_nmm - 1.0).abs() > 0.02, "torsion and couple must be different load cases");
}

#[test] fn d1_joint_factor_is_product() {
    let m = &jarambit_physics::TI_6AL_4V; let t = 5.6;
    let jk = crate::fem::joint_k(m, t, 2); let thin = ((t - 0.1) / t).powi(2); let hot = m.yield_at(100.0) / m.yield_at(20.0);
    assert!((jk - thin * hot).abs() < 1e-12 && jk < thin.min(hot));
    assert!((m.yield_mpa - 828.0).abs() < 1e-9, "screening yield must be 828 MPa (TIMET min), not rounded");
}

#[test] fn d1_genome_csv_roundtrip_is_exact() {
    let mut r = Rng(99); let g = Genome::c6_seed(5.7).mutate(&mut r, 0.2);
    let row = g.csv_row(); let f: Vec<&str> = row.split(',').collect();
    let h = Genome::from_csv(&f).unwrap();
    assert!(g.v.iter().zip(&h.v).all(|(a, b)| a.to_bits() == b.to_bits()), "genome CSV must round-trip bit-exactly");
}

// ---------------- D1 P1 continuous-rail layer ----------------
#[test]
fn p1_layer_off_for_legacy_and_seed() {
    let g = Genome::c6_seed(5.7);
    assert!(!g.p1() || crate::genome::p1_env());
    if !g.p1() { for k in 0..5 { assert_eq!(g.v[K0 + k], g.v[T]); } assert_eq!(g.t_joint(), g.v[T]); }
}
#[test]
fn p1_clamps_through_features_off_and_knots_set_stock() {
    let mut g = Genome::c6_seed(5.8);
    g.v[PERF_D] = 5.0; g.v[PERF_ZL] = 1.0; g.v[PERF_ZH] = 1.0; g.v[WIN_N] = 4.0; g.v[ISO_D] = 1.2; g.v[ISO_ZB] = 1.0; g.v[LAT_D] = 1.0; g.v[LAT_H] = 1.0;
    g.v[P1_ON] = 1.0; g.v[K_N] = 3.0; g.v[K0] = 5.9; g.v[K0 + 1] = 5.5; g.v[K0 + 2] = 5.4; g.v[POCKET_D] = 0.9; g.v[POCKET_R] = 1.0; g.v[FUL_D] = 1.1;
    g.clamp();
    assert!(g.p1());
    for i in [PERF_D, PERF_ZL, PERF_ZH, WIN_N, ISO_D, ISO_ZB, LAT_D, LAT_H, RELIEF_D, FLUTE, RFL_D, TEX_MODE] { assert_eq!(g.v[i], 0.0, "gene {i}"); }
    assert!(g.v[POCKET_D] <= P1_POCKET_MAX + 1e-12 && g.v[POCKET_R] >= P1_RUNOUT_MIN - 1e-12 && g.v[FUL_D] <= P1_POCKET_MAX + 1e-12);
    // thickest knot is lifted to the stock T (5.8); profile shape kept
    let kmax = (0..3).map(|k| g.v[K0 + k]).fold(0.0, f64::max); assert!((kmax - 5.8).abs() < 1e-9, "kmax {kmax}");
    assert!((g.t_joint() - 5.4).abs() < 1e-9, "t_joint {}", g.t_joint());
    let p = crate::pheno::build(&g);
    assert_eq!(p.n_perf, 0); assert_eq!(p.n_win, 0);
    assert!((p.t_joint - g.t_joint()).abs() < 1e-12);
    // no parent SF map in unit tests -> no pockets anywhere (conservative default)
    if crate::pheno::sfmap().is_none() { assert_eq!(p.pocket_area, 0.0); }
    // knot field: neck thicker than the mid-handle knot, all >= 5.3 - groove; the field never exceeds the stock
    // neck band just outside the ring OD: thickest raster cell there sits on the first knot segment (~5.8 -> 5.5)
    let fd = &p.field; let mut neck = 0.0f64;
    for j in 0..fd.ny { for i in 0..fd.nx { let v = fd.th[j * fd.nx + i]; if v.is_nan() { continue; }
        let x = fd.x0 + (i as f64 + 0.5) * fd.g; if x >= p.ring_od / 2.0 + 1.0 && x <= p.ring_od / 2.0 + 4.0 { neck = neck.max(v as f64); } } }
    assert!(neck > 5.6 && neck <= 5.8 + 1e-6, "neck {neck}");
    let mx = p.field.th.iter().filter(|v| !v.is_nan()).fold(0.0f32, |a, &b| a.max(b)); assert!(mx as f64 <= 5.8 + 1e-6);
    // same genome with P1 off keeps the single-stock field (heavier)
    let mut h = g.clone(); h.v[P1_ON] = 0.0; h.clamp();
    if !h.p1() { let q = crate::pheno::build(&h); assert!(q.mass_g > p.mass_g, "single stock {:.2} vs knots {:.2}", q.mass_g, p.mass_g); }
}
#[test]
fn p1_genome_csv_roundtrip_is_exact() {
    let mut g = Genome::c6_seed(5.7); g.v[P1_ON] = 1.0; g.v[K_N] = 4.37; g.v[K0 + 1] = 5.4123456789012345; g.v[RAIL_W] = 4.123456789; g.clamp();
    let row = g.csv_row(); let f: Vec<&str> = row.split(',').collect();
    let h = Genome::from_csv(&f).unwrap(); assert_eq!(h.v, g.v);
}
