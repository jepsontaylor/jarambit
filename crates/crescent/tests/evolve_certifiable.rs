//! Physical controls for genome-driven export; these are tests, not catalog design certificates.
use jarambit_crescent::{
    certification, export,
    genome::{self, Genome},
    pheno,
};
fn parent() -> Genome {
    let data = include_str!("../../../evidence/rs_v2/w283_ultrarunner/w283_p14_c01_genome.csv");
    Genome::from_csv(&data.lines().nth(1).unwrap().split(',').collect::<Vec<_>>()).unwrap()
}
fn control() -> Genome {
    let mut g = parent();
    g.v[genome::EDGE_TH] = 0.12;
    g.v[genome::EA_IN] = 14.;
    g.v[genome::EA_SP] = 14.;
    g.v[genome::RING_WALL] = 6.3;
    g.clamp();
    g
}
#[test]
fn existing_genome_domain_can_export_a_sharp_edge_and_real_bore_roll() {
    let g = control();
    assert_eq!(g.v[genome::EDGE_TH], 0.12);
    let b = genome::bounds();
    for i in [genome::EA_IN, genome::EA_SP, genome::RING_WALL] {
        assert!((b[i].0..=b[i].1).contains(&g.v[i]));
    }
    let p = pheno::build(&g);
    let s = export::solid(&p, 1.).unwrap();
    assert_eq!(export::census(&s.tris), (0, 0, 1));
    assert!(export::volume(&s) > 0.);
    let sharp = certification::sharpness(&s, &p).unwrap();
    assert!(sharp.complete && sharp.pass, "{sharp:?}");
    let r = certification::bore_radius(&s, &p).unwrap();
    assert!(r >= 1.5);
    assert!((r - 1.575).abs() < 1e-8);
    let step = export::step(&s, "genome_control");
    assert!(step.contains("TOROIDAL_SURFACE("));
    assert!(step.contains("SHAPE_DEFINITION_REPRESENTATION("));
    assert!(step.contains("SI_UNIT(.MILLI.,.METRE.)"));
    // Changing a claimed radius cannot alter what the actual exported vertices measure.
    let mut changed = s.clone();
    changed.bore.as_mut().unwrap().radius = 99.;
    assert_eq!(
        certification::bore_radius(&s, &p),
        certification::bore_radius(&changed, &p)
    );
}
#[test]
fn measured_geometry_rejects_a_blunt_edge_and_a_broken_bore_profile() {
    let p = pheno::build(&control());
    let mut s = export::solid(&p, 1.).unwrap();
    for v in &mut s.verts {
        v.2 *= 10.;
    }
    assert!(!certification::sharpness(&s, &p).unwrap().pass);
    let mut s = export::solid(&p, 1.).unwrap();
    let row = s.bore.as_ref().unwrap().profiles[0];
    s.verts[row[4]].2 += 0.5;
    assert!(certification::bore_radius(&s, &p).is_none());
}
#[test]
fn source_surface_is_the_actual_cad_skin_and_export_is_deterministic() {
    let p = pheno::build(&control());
    let a = export::solid(&p, 1.).unwrap();
    let b = export::solid(&p, 1.).unwrap();
    assert_eq!(a.verts, b.verts);
    assert_eq!(a.tris, b.tris);
    assert_eq!(export::step(&a, "control"), export::step(&b, "control"));
    let surface = export::surface_json(&a);
    let verts = surface["verts"].as_array().unwrap();
    for tr in surface["tris"].as_array().unwrap() {
        for index in tr.as_array().unwrap() {
            let i = index.as_u64().unwrap() as usize;
            assert_eq!(verts[i][2].as_f64().unwrap(), a.verts[i].2);
            assert!(a.verts[i].2 > 0.);
        }
    }
    for &(x, y, z) in a.verts.iter().filter(|v| v.2 > 0.) {
        assert!((2. * z - export::thickness_at(&p, (x, y))).abs() < 1e-8);
    }
}
#[test]
fn exact_segment_index_matches_brute_force_distance() {
    use jarambit_crescent::geom::{seg_dist, Segments};
    let edge = vec![(0., 0.), (3., 1.), (4., -2.), (9., -1.)];
    let index = Segments::new(&edge);
    for x in -4..15 {
        for y in -6..6 {
            let q = (x as f64 * 0.7, y as f64 * 0.9);
            let expected = edge
                .windows(2)
                .map(|w| seg_dist(q, w[0], w[1]))
                .fold(f64::INFINITY, f64::min);
            assert!((index.nearest(q, 20.) - expected).abs() < 1e-12);
            if expected > 0.2 {
                assert!(index.nearest(q, 0.2).is_infinite());
            }
        }
    }
}

#[test]
fn incomplete_or_locally_undersized_bore_roll_never_passes() {
    let p=pheno::build(&control());
    let s=export::solid(&p,1.).unwrap();
    let mut one_face=s.clone();
    for v in &mut one_face.verts {if v.2<0. {v.2=-6.3;}}
    assert!(certification::bore_radius(&one_face,&p).map_or(true,|r|r<1.5));
    let mut local=s.clone();
    // Rebuild a single actual meridian with a smaller circular roll, preserving its bore contact.
    let r=p.ring_id/2.;let theta=0.;
    for v in &mut local.verts {
        if v.1.atan2(v.0).abs()<1e-8 && v.0.hypot(v.1)<=r+1.575+1e-8 {
            let phi=((v.0.hypot(v.1)-r)/1.575).clamp(0.,1.);
            let angle=(1.-phi).acos();let rho=r+1.3*(1.-angle.cos());
            v.0=rho;v.1=theta;v.2=v.2.signum()*(6.3+1.3*angle.sin());
        }
    }
    assert!(certification::bore_radius(&local,&p).map_or(true,|r|r<1.5));
}
