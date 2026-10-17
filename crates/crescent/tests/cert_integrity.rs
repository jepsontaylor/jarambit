//! Adverse cases from #75–#81. These assert measurement/provenance, not released score constants.
use jarambit_crescent::{
    battery, certification as cert, export, fem,
    genome::{Genome, EDGE_TH},
    pheno,
};
use serde_json::json;
use std::path::PathBuf;
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}
fn record() -> Genome {
    let text = std::fs::read_to_string(
        root().join("evidence/rs_v2/w283_ultrarunner/w283_p14_c01_genome.csv"),
    )
    .unwrap();
    let row: Vec<_> = text.lines().nth(1).unwrap().split(',').collect();
    Genome::from_csv(&row).unwrap()
}
#[test]
fn plate_and_export_use_actual_thickness_not_the_thicker_machining_base() {
    let p = pheno::build(&record());
    let f = &p.field;
    let k = (0..f.th.len())
        .find(|&i| {
            f.th[i].is_finite() && f.base[i].is_finite() && (f.th[i] - f.base[i]).abs() > 0.5
        })
        .unwrap();
    let q = (
        f.x0 + (k % f.nx) as f64 * f.g + 0.5 * f.g,
        f.y0 + (k / f.nx) as f64 * f.g + 0.5 * f.g,
    );
    assert_eq!(f.at_plate(q, true), f.at(q));
    let s = export::solid(&p, 1.0).unwrap();
    for &(x, y, z) in &s.verts {
        assert!((z.abs()*2.0-export::thickness_at(&p,(x,y))).abs()<1e-8, "circular fillet/export surface mismatch at {x},{y}: mesh={} law={}",z.abs()*2.0,export::thickness_at(&p,(x,y)));
    }
    let (_, fl) = fem::report_fields(&p, 4.0).unwrap();
    for (tr, &te) in fl.tris.iter().zip(&fl.te) {
        let (a, b, c) = (fl.xy[tr[0]], fl.xy[tr[1]], fl.xy[tr[2]]);
        let cen = ((a.0 + b.0 + c.0) / 3.0, (a.1 + b.1 + c.1) / 3.0);
        let qs = [
            cen,
            ((a.0 + cen.0) / 2.0, (a.1 + cen.1) / 2.0),
            ((b.0 + cen.0) / 2.0, (b.1 + cen.1) / 2.0),
            ((c.0 + cen.0) / 2.0, (c.1 + cen.1) / 2.0),
        ];
        let expected = qs.iter().map(|&q| export::thickness_at(&p, q)).sum::<f64>() / 4.0;
        assert_eq!(te, expected);
    }
}
#[test]
fn rs_mode_does_not_create_ring_width_strength_or_fatigue_credits() {
    let p=pheno::build(&record());
    let a=fem::run_unbiased(&p,4.0).unwrap();
    assert_eq!(a.hm_twist_nmm,a.twist_joint_nmm);
    let material=jarambit_physics::material(p.mat);
    let expected=fem::fatigue::goodman_sf(material.yield_at(20.0)*fem::fatigue::CYCLIC_LATERAL_N/a.lat_rob,p.t_joint);
    assert!((a.fat_sf-expected).abs()<1e-12,"fatigue must use the uncredited actual lateral stress");

}
#[test]
fn thin_gene_cannot_pass_a_blunt_export_and_wide_bore_does_not_prove_radius() {
    let g = record();
    assert!(g.v[EDGE_TH] <= 0.2);
    let p = pheno::build(&g);
    let mut blunt=export::solid(&p,1.0).unwrap();
    for v in &mut blunt.verts {v.2*=10.0;}
    let sharp=cert::sharpness(&blunt,&p).unwrap();
    assert!(sharp.max_apex_mm>0.89);assert!(!sharp.pass);
    let radius=cert::measure(&p).bore_edge_radius_mm.unwrap();
    assert!(radius<fem::hm::RING_EDGE_R_MIN_MM);
    let f = fem::Fem {
        hm_twist_sf: 2.0,
        hm_spine_sf: 2.0,
        hm_ringback_sf: 2.0,
        ..Default::default()
    };
    assert!(fem::ring_bearing(&p).0 >= 10.0);
    assert!(!fem::rs_v2_human_max_pass(&f, &p));
}
fn strip(profile: &[(f64, f64)]) -> export::Solid {
    let mut verts = vec![];
    let mut tris = vec![];
    for &(x, t) in profile {
        verts.extend([
            (x, -1.0, t / 2.0),
            (x, 1.0, t / 2.0),
            (x, -1.0, -t / 2.0),
            (x, 1.0, -t / 2.0),
        ]);
    }
    for i in 0..profile.len() - 1 {
        let a = 4 * i;
        let b = a + 4;
        tris.extend([
            [a, b, b + 1],
            [a, b + 1, a + 1],
            [a + 2, b + 3, b + 2],
            [a + 2, a + 3, b + 3],
            [a, a + 2, b + 2],
            [a, b + 2, b],
            [a + 1, b + 3, a + 3],
            [a + 1, b + 1, b + 3],
        ]);
    }
    let b = 4 * (profile.len() - 1);
    tris.extend([[0, 1, 3], [0, 3, 2], [b, b + 2, b + 3], [b, b + 3, b + 1]]);
    export::Solid { verts, tris, bore: None }
}
#[test]
fn brep_point_measures_intersections_and_rejects_reversals_after_five_mm() {
    let good = strip(&[
        (0.0, 0.15),
        (0.25, 0.25),
        (1.0, 0.5),
        (2.0, 0.8),
        (5.0, 2.0),
        (7.0, 3.0),
        (10.0, 4.0),
    ]);
    let p = cert::point_profile(&good, (0.0, 0.0), (1.0, 0.0), 4.0).unwrap();
    assert!(p.pass);
    assert!(p.monotonic);
    assert!((p.t_1p00_mm - 0.5).abs() < 1e-12);
    let bad = strip(&[
        (0.0, 0.15),
        (0.25, 0.25),
        (1.0, 0.5),
        (2.0, 0.8),
        (5.0, 2.0),
        (7.0, 3.0),
        (10.0, 2.5),
    ]);
    let p = cert::point_profile(&bad, (0.0, 0.0), (1.0, 0.0), 4.0).unwrap();
    assert!(!p.monotonic);
    assert!(!p.pass);
    let small_reversal = strip(&[
        (0.0, 0.15),
        (0.25, 0.25),
        (1.0, 0.5),
        (1.5, 0.49),
        (2.0, 0.8),
        (5.0, 2.0),
        (10.0, 4.0),
    ]);
    assert!(
        !cert::point_profile(&small_reversal, (0.0, 0.0), (1.0, 0.0), 4.0)
            .unwrap()
            .monotonic,
        "no 0.05 mm monotonicity waiver"
    );
    let early = strip(&[
        (0.0, 0.15),
        (0.25, 0.25),
        (1.0, 0.5),
        (2.0, 0.8),
        (4.0, 4.0),
        (10.0, 4.0),
    ]);
    assert!(
        !cert::point_profile(&early, (0.0, 0.0), (1.0, 0.0), 4.0)
            .unwrap()
            .pass
    );
}
fn independent() -> serde_json::Value {
    json!({"mesh_sha256":"a".repeat(64),"stored_solid":{"NL":4,"NSUB":1,"SF_nodal_max":1.61,"SF_nodal_avg":1.71,"SF_skfem_nodal_max":1.6,"SF_skfem_nodal_avg":1.7},"dolfinx_cross_check":{"status":"verified","primary_solver":"skfem_p2","independent_solver":"dolfinx_v0.9.0","mesh_sha256":"a".repeat(64),"SF_nodal_max":1.61,"SF_nodal_avg":1.71,"within_2pct":true}})
}
#[test]
fn native_or_missing_independent_solver_never_becomes_a_pass() {
    let fake = json!({"stored_solid":{"SF_skfem_nodal_max":1.5},"dolfinx_cross_check":{"container":"native_rust_tet10_faer","SF_nodal_max":1.5,"rel_err_nodal_max":0.0,"within_2pct":true}});
    assert_eq!(cert::independent_pass(&fake), None);
    let mut real = independent();
    assert_eq!(cert::independent_pass(&real), Some(true));
    real["dolfinx_cross_check"]["SF_nodal_max"] = json!(2.0);
    real["stored_solid"]["SF_nodal_max"] = json!(2.0);
    assert_eq!(
        cert::independent_pass(&real),
        Some(false),
        "do not trust within_2pct flag"
    );
    real["dolfinx_cross_check"]["independent_solver"] = json!("native_rust");
    assert_eq!(cert::independent_pass(&real), None);
}
#[test]
fn evidence_identity_changes_with_genome_and_never_with_display_label() {
    let g = record();
    let old = cert::identity(&g);
    let mut changed = g.clone();
    changed.v[EDGE_TH] = 0.49;
    assert_ne!(old, cert::identity(&changed));
    assert!(cert::bound(
        &json!({"subject":"another label","certificate_identity":old}),
        &cert::identity(&g)
    ));
    assert!(!cert::bound(
        &json!({"subject":"w283_p14_c01","certificate_identity":old}),
        &cert::identity(&changed)
    ));
}
#[test]
fn stale_catalog_and_adjacent_records_cannot_certify_an_edited_genome() {
    let g0 = record();
    let mut g = g0.clone();
    g.v[EDGE_TH] = 0.49;
    let out = root().join(format!(
        "target/cert_integrity_tests/stale_{}",
        std::process::id()
    ));
    std::fs::create_dir_all(&out).unwrap();
    let csv = out.join("w283_p14_c01_genome.csv");
    std::fs::write(&csv, format!("{}\n{}\n", Genome::csv_header(), g.csv_row())).unwrap();
    let poison = json!({"certificate_identity":cert::identity(&g0),"metrics":{"mass_g":999.0},"all_hard":true});
    for suffix in ["D1", "rs", "solid_tip", "plate_gci", "a4"] {
        std::fs::write(
            out.join(format!("w283_p14_c01_{suffix}.json")),
            poison.to_string(),
        )
        .unwrap();
    }
    let (ev, spec) =
        battery::evaluate_genome_candidate_native(&root(), "w283_p14_c01", &csv, &out).unwrap();
    assert_eq!(ev["certificate_identity"], cert::identity(&g));
    assert!(
        (ev["engineering_metrics"]["mass_g"].as_f64().unwrap() - pheno::build(&g).mass_g).abs()
            < 1e-9
    );
    assert_eq!(
        ev["weighted_cad_score"]["all_engineering_gates_pass"],
        false
    );
    assert!(ev["engineering_metrics"]["solid_tip_sf_nodal_max"].is_null());
    let rs: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(spec.rs).unwrap()).unwrap();
    assert_eq!(rs["all_hard"], false);
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(
            &std::fs::read_to_string(out.join("w283_p14_c01_D1.json")).unwrap()
        )
        .unwrap(),
        poison
    );
}

#[test]
fn previous_model_certificates_never_bind_to_the_new_surface_model() {
    for sid in ["w283_p14_c01", "w283_p10_c02"] {
        let dir = root().join("evidence/rs_v2/w283_ultrarunner");
        let csv = std::fs::read_to_string(dir.join(format!("{sid}_genome.csv"))).unwrap();
        let genome =
            Genome::from_csv(&csv.lines().nth(1).unwrap().split(',').collect::<Vec<_>>()).unwrap();
        let rs: serde_json::Value =
            serde_json::from_slice(&std::fs::read(dir.join(format!("{sid}_rs.json"))).unwrap())
                .unwrap();
        assert!(
            !cert::bound(&rs, &cert::identity(&genome)),
            "old physical model replayed as a new surface certificate: {sid}"
        );
        assert_eq!(rs["all_hard"], false);
        assert_eq!(rs["gates"]["gate_s_sharp_law"], "fail");
        assert_eq!(rs["gates"]["gate_s_tip_point_brep"], "fail");
    }
}

#[test]
fn exported_edge_measurement_can_accept_a_thin_flat_edge_and_reject_a_blunt_one() {
    let mut p = pheno::build(&record());
    p.outline = vec![(0.0, -1.0), (10.0, -1.0), (10.0, 1.0), (0.0, 1.0)];
    p.edge_in = vec![(1.0, -1.0), (9.0, -1.0)];
    p.edge_sp = vec![(9.0, 1.0), (1.0, 1.0)];
    let good = strip(&[
        (0.0, 0.15),
        (1.0, 0.15),
        (5.0, 0.15),
        (9.0, 0.15),
        (10.0, 0.15),
    ]);
    let measured = cert::sharpness(&good, &p).unwrap();
    assert!(measured.complete && measured.pass);
    assert!((measured.max_apex_mm - 0.15).abs() < 1e-12);
    let bad = strip(&[
        (0.0, 0.35),
        (1.0, 0.35),
        (5.0, 0.35),
        (9.0, 0.35),
        (10.0, 0.35),
    ]);
    assert!(!cert::sharpness(&bad, &p).unwrap().pass);
}

#[test]
fn sub_csv_precision_genome_changes_have_distinct_content_keys() {
    let g = record();
    let mut other = g.clone();
    other.v[EDGE_TH] += 1e-9;
    assert_eq!(
        format!("{:.6}", g.v[EDGE_TH]),
        format!("{:.6}", other.v[EDGE_TH]),
        "rounded displays can hide the difference"
    );
    assert_ne!(
        cert::identity(&g),
        cert::identity(&other),
        "identity must bind exact IEEE-754 bits"
    );
}


#[test]
fn bevel_face_entering_the_edge_band_is_measured_even_with_distant_vertices() {
    // Synthetic measurement control only, not an added design or certificate.
    let mut p=pheno::build(&record());
    p.edge_in=vec![(0.45,-1.0),(0.55,-1.0)];p.edge_sp=vec![(9.45,1.0),(9.55,1.0)];
    let mut s=strip(&[(0.,0.12),(0.45,0.12),(0.55,0.12),(1.,0.12),(9.45,0.12),(9.55,0.12),(10.,0.12)]);
    assert!(cert::sharpness(&s,&p).unwrap().pass);
    let start=s.verts.len();s.verts.extend([(0.,-0.95,0.06),(1.,-0.95,0.06),(0.5,0.95,2.06)]);s.tris.push([start,start+1,start+2]);
    // The steep face is only 0.05 mm from the edge; all three vertices are more than 0.4 mm away.
    let measured=cert::sharpness(&s,&p).unwrap();assert!(!measured.pass);assert!(measured.max_half_angle_deg>25.);
}

/// A local collar change may change stresses; it must not add a separate RS strength multiplier.
#[test]
fn bore_local_perturbation_does_not_credit_twist_or_spine_capacity() {
    use jarambit_crescent::geom::{densify, dist, dp_closed, norm, sub, Nn};
    use jarambit_physics::{fine, material};
    let base=pheno::build(&record());
    assert!(base.rs_v2);
    let mut widths=Vec::new();
    for extra in [0.,2.] {
        let mut p=base.clone();
        // Software perturbation: leave the planform/holes/load path fixed, alter only the local collar.
        p.ring_od+=extra;
        widths.push(fem::ring_bearing(&p).0);
        let (f,fields)=fem::report_fields(&p,4.).unwrap();
        let mt=material(p.mat);
        let twist=f.twist20_nmm*fem::joint_k(&mt,p.t_joint,2)/f.twist_kc;
        assert!((f.hm_twist_nmm-twist).abs()<1e-10*twist);
        let outer=dp_closed(&p.outline,0.03);
        let holes:Vec<_>=p.holes.iter().map(|h|dp_closed(h,0.02)).collect();
        let mesh=fine::mesh_domain(&outer,&holes,4.).unwrap();
        assert_eq!(mesh.xy,fields.xy);assert_eq!(mesh.tris,fields.tris);
        let n=mesh.xy.len();let rr=p.ring_id/2.;
        let ring:Vec<_>=mesh.xy.iter().enumerate().map(|(i,q)|mesh.on_hole[i]&&(q.0.hypot(q.1)-rr).abs()<0.05).collect();
        let tip=*mesh.xy.iter().enumerate().filter(|(i,_)|mesh.on_outer[*i])
            .min_by(|(_,a),(_,b)|dist(**a,p.tip).total_cmp(&dist(**b,p.tip))).unwrap().1;
        let t6=fine::T6::new(&mesh,p.t,mt.e_gpa*1000.,fine::NU).with_thickness(fields.te);
        let mut ring6=vec![false;t6.xy.len()];ring6[..n].copy_from_slice(&ring);
        for t in &t6.tris {for (a,b,m) in [(t[0],t[1],t[3]),(t[1],t[2],t[4]),(t[2],t[0],t[5])] {
            ring6[m]=ring[a]&&ring[b]&&(t6.xy[m].0.hypot(t6.xy[m].1)-rr).abs()<0.05;
        }}
        let fixed:Vec<_>=ring6.iter().flat_map(|b|[*b,*b]).collect();
        let system=t6.system(&fixed).unwrap();
        let nn=Nn::new(&densify(&p.edge_sp,0.25,false),2.);
        let on_sp=|i:usize|i<n&&mesh.on_outer[i]&&nn.nearest(mesh.xy[i],1.)<0.6&&dist(mesh.xy[i],tip)>fine::TIP_EXCL_MM;
        let mean=|v:&Vec<(f64,f64)>|(v.iter().map(|q|q.0).sum::<f64>()/v.len() as f64,v.iter().map(|q|q.1).sum::<f64>()/v.len() as f64);
        let mut load=vec![0.;t6.xy.len()*2];
        let length=t6.edge_traction(&on_sp,norm(sub(mean(&p.edge_in),mean(&p.edge_sp))),&mut load);
        assert!(length>0.);for v in &mut load {*v/=length;}
        let stresses=t6.nodal_stress(&t6.solve(&system,&load));
        let peak=stresses.iter().enumerate().filter(|(i,_)|dist(t6.xy[*i],tip)>=fine::TIP_EXCL_MM)
            .map(|(_,s)|fine::von_mises(*s)).fold(0.,f64::max);
        let raw=mt.yield_at(20.)/peak*fem::joint_k(&mt,p.t_joint,1);
        assert!((f.hm_spine_n-raw).abs()<1e-10*raw,"bearing {} mm created spine credit",widths.last().unwrap());
        assert!((f.hm_spine_sf-raw/fem::hm::SPINE_N).abs()<1e-10);
    }
    assert!(widths[1]>widths[0]);
}
