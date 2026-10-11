//! Detailed plate FEM on the crescent with the per-element thickness field
//! (physics::fine DKT bending + CST/T6 membrane; same element code as the calibrated search).
//! Load cases (crescent frame, ring at origin):
//!   lateral: ring-hole edge clamped, out-of-plane tip load on a 2 mm patch (180/260 N floors);
//!   twist:   ring clamped, moment about the ring->tip chord (proxy, no floor);
//!   pry:     ring clamped, in-plane tip load perpendicular to the chord (T6, no floor);
//!   ring:    guard/ricasso band x in [76, 100]+dx seated, -x traction on the ring hole (1500 N floor).
//! Robust level = min(20 C with -0.1 mm stock tolerance, 100 C yield) / crescent search-mesh bias;
//! winners are re-judged by `certify` (min over 0.25 and 0.125 mm^2, no bias).
use crate::geom::*;
use crate::pheno::*;
use jarambit_physics::{fine, floors, material};

#[derive(Clone, Debug, Default)]
pub struct Fem {
    pub lat20: f64, pub pry20: f64, pub twist20_nmm: f64, pub ring20: f64,
    pub lat_rob: f64, pub ring_rob: f64, pub sf_hiker: f64, pub sf_hunter: f64, pub sf_ring: f64,
    pub lat_at: P2, pub ring_at: P2, pub nodes: usize, pub tris: usize, pub floors_ok: bool,
}

pub struct Fields { pub xy: Vec<P2>, pub tris: Vec<[usize; 3]>, pub te: Vec<f64>, pub env_vm: Vec<f64>, pub sf: Vec<f64>,
    pub lat: Vec<f64>, pub pry: Vec<f64>, pub ring: Vec<f64>, pub twist: Vec<f64> }

pub const TWIST_DESIGN_NMM: f64 = 180.0 * 7.0;
/// Crescent-specific search-mesh bias, MEASURED by `jarambit crescent-conv` (out/crescent_conv):
/// detailed plate at the 2 mm^2 search level over the 0.125 mm^2 reference on 25 distinct aesthetic
/// passers (legal winners + a stride of the run): lateral max 1.105, ring max 1.073 (ground edges + hawkbill tip are more mesh-sensitive
/// than the flat jarambit calibration of 1.070 / 1.062). Rounded up.
pub const SEARCH_BIAS_LAT: f64 = 1.11;
pub const SEARCH_BIAS_RING: f64 = 1.08;
/// Certification levels: capacity = MIN over these two converged levels (no bias applied).
pub const CERT_AREAS: [f64; 2] = [0.25, 0.125];

pub fn run(p: &Pheno, max_area: f64, keep: bool) -> Option<(Fem, Option<Fields>)> { run_b(p, max_area, keep, SEARCH_BIAS_LAT, SEARCH_BIAS_RING) }

/// Certified capacities: min over CERT_AREAS of the 20 C capacities, robust factors applied, no
/// mesh bias (these are the reference levels). Fields (for plates) come from the 0.25 mm^2 level.
pub fn certify(p: &Pheno) -> Option<(Fem, Fields)> {
    let (a, fa) = run_b(p, CERT_AREAS[0], true, 1.0, 1.0)?;
    let (b, _) = run_b(p, CERT_AREAS[1], false, 1.0, 1.0)?;
    let m = material(p.mat); let sy20 = m.yield_at(20.0); let hot = m.yield_at(100.0) / sy20;
    let (tk, tk1) = (((p.t - 0.1) / p.t).powi(2), (p.t - 0.1) / p.t);
    let gov = if a.lat20 <= b.lat20 { &a } else { &b };
    let lat20 = a.lat20.min(b.lat20); let ring20 = a.ring20.min(b.ring20);
    let lat_rob = (lat20 * tk).min(lat20 * hot); let ring_rob = (ring20 * tk1).min(ring20 * hot);
    let f = Fem { lat20, pry20: a.pry20.min(b.pry20), twist20_nmm: a.twist20_nmm.min(b.twist20_nmm), ring20, lat_rob, ring_rob,
        sf_hiker: lat_rob / floors::HIKER_LATERAL_N, sf_hunter: lat_rob / floors::HUNTER_LATERAL_N, sf_ring: ring_rob / floors::RING_PULL_N,
        lat_at: gov.lat_at, ring_at: if a.ring20 <= b.ring20 { a.ring_at } else { b.ring_at }, nodes: b.nodes, tris: b.tris,
        floors_ok: lat_rob >= floors::HIKER_LATERAL_N && lat_rob >= floors::HUNTER_LATERAL_N && ring_rob >= floors::RING_PULL_N };
    Some((f, fa?))
}

fn run_b(p: &Pheno, max_area: f64, keep: bool, bias_lat: f64, bias_ring: f64) -> Option<(Fem, Option<Fields>)> {
    let m = material(p.mat);
    let outer = dp_closed(&p.outline, 0.03);
    let holes: Vec<Vec<P2>> = p.holes.iter().map(|h| dp_closed(h, 0.02)).collect();
    let mesh = fine::mesh_domain(&outer, &holes, max_area)?;
    let te: Vec<f64> = mesh.tris.iter().map(|t| {
        let (a, b, c) = (mesh.xy[t[0]], mesh.xy[t[1]], mesh.xy[t[2]]);
        let cen = ((a.0 + b.0 + c.0) / 3.0, (a.1 + b.1 + c.1) / 3.0);
        let pts = [cen, ((a.0 + cen.0) / 2.0, (a.1 + cen.1) / 2.0), ((b.0 + cen.0) / 2.0, (b.1 + cen.1) / 2.0), ((c.0 + cen.0) / 2.0, (c.1 + cen.1) / 2.0)];
        (pts.iter().map(|&q| p.field.at(q)).sum::<f64>() / 4.0).max(0.3)
    }).collect();
    let e_mpa = m.e_gpa * 1000.0;
    let plate = fine::Plate::new(mesh, p.t, e_mpa, fine::NU).with_thickness(te.clone());
    let xy = plate.mesh.xy.clone(); let n = xy.len(); let ne = plate.mesh.tris.len();
    let rr = p.ring_id / 2.0;
    let ring_node: Vec<bool> = (0..n).map(|i| plate.mesh.on_hole[i] && (xy[i].0.hypot(xy[i].1) - rr).abs() < 0.05).collect();
    if ring_node.iter().filter(|&&b| b).count() < 8 { return None; }
    let tipi = (0..n).filter(|&i| plate.mesh.on_outer[i]).min_by(|&a, &b| dist(xy[a], p.tip).partial_cmp(&dist(xy[b], p.tip)).unwrap())?;
    let tp = xy[tipi];
    let patch: Vec<usize> = (0..n).filter(|&i| dist(xy[i], tp) <= fine::TIP_PATCH_MM && (plate.mesh.on_outer[i] || dist(xy[i], tp) <= 1.0)).collect();
    let k = patch.len().max(1) as f64;
    let dvec = norm(tp); let nvec = (-dvec.1, dvec.0);
    let cen: Vec<P2> = (0..ne).map(|e| plate.centroid(e)).collect();
    let excl: Vec<bool> = cen.iter().map(|c| dist(*c, tp) < fine::TIP_EXCL_MM).collect();
    let mut fix = vec![false; n * 5];
    for i in 0..n { if ring_node[i] { for c in 0..5 { fix[i * 5 + c] = true; } } }
    let sys = plate.system(&fix)?;
    let mut f_lat = vec![0.0; n * 5]; let mut f_tw = vec![0.0; n * 5];
    for &i in &patch { f_lat[i * 5 + 2] = 1.0 / k; f_tw[i * 5 + 3] = dvec.0 / k; f_tw[i * 5 + 4] = dvec.1 / k; }
    let (_, lat) = plate.stresses(&plate.solve(&sys, &f_lat));
    let (_, twist) = plate.stresses(&plate.solve(&sys, &f_tw));
    drop(sys);
    let peak = |v: &[f64], ex: &[bool]| { let mut b = (0.0, 0usize); for (e, &s) in v.iter().enumerate() { if !ex[e] && s.is_finite() && s > b.0 { b = (s, e); } } b };
    let (sl, el) = peak(&lat, &excl); let (st, _) = peak(&twist, &excl);
    // ---- in-plane (T6) ----
    let t6 = fine::T6::new(&plate.mesh, p.t, e_mpa, fine::NU).with_thickness(te.clone());
    let n6 = t6.n();
    let ring6: Vec<bool> = (0..n6).map(|i| if i < n { ring_node[i] } else { (t6.xy[i].0.hypot(t6.xy[i].1) - rr).abs() < 0.05 && seg_on_ring(&t6, i, &ring_node) }).collect();
    let mut fx = vec![false; n6 * 2];
    for i in 0..n6 { if ring6[i] { fx[i * 2] = true; fx[i * 2 + 1] = true; } }
    let sys6 = t6.system(&fx)?;
    let mut f_pr = vec![0.0; n6 * 2];
    for &i in &patch { f_pr[i * 2] = nvec.0 / k; f_pr[i * 2 + 1] = nvec.1 / k; }
    let u_pr = t6.solve(&sys6, &f_pr);
    let pry = t6.centroid_vm(&u_pr); let nod_pr = t6.nodal_stress(&u_pr);
    drop(sys6);
    let (sx0, sx1) = (76.0 + p.dx, 100.0 + p.dx);
    let seat: Vec<bool> = t6.xy.iter().map(|q| q.0 >= sx0 && q.0 <= sx1).collect();
    let mut fx = vec![false; n6 * 2];
    for i in 0..n6 { if seat[i] { fx[i * 2] = true; fx[i * 2 + 1] = true; } }
    let sys6 = t6.system(&fx)?;
    let mut f_ring = vec![0.0; n6 * 2];
    let per = t6.edge_traction(&|i| ring6[i], (-1.0, 0.0), &mut f_ring);
    if per <= 0.0 { return None; }
    for v in f_ring.iter_mut() { *v /= per; }
    let u_ring = t6.solve(&sys6, &f_ring);
    let ring = t6.centroid_vm(&u_ring); let nod_ring = t6.nodal_stress(&u_ring);
    let mut pry_pk = 0.0f64; let mut ring_pk = (0.0f64, (0.0, 0.0));
    for i in 0..n6 { let q = t6.xy[i]; if dist(q, tp) < fine::TIP_EXCL_MM { continue; }
        pry_pk = pry_pk.max(fine::von_mises(nod_pr[i]));
        if q.0 < sx0 - 3.0 { let v = fine::von_mises(nod_ring[i]); if v > ring_pk.0 { ring_pk = (v, q); } } }
    let sy20 = m.yield_at(20.0); let hot = m.yield_at(100.0) / sy20;
    let tk = ((p.t - 0.1) / p.t).powi(2); let tk1 = (p.t - 0.1) / p.t;
    let lat20 = sy20 / sl.max(1e-12); let ring20 = sy20 / ring_pk.0.max(1e-12);
    let lat_rob = (lat20 * tk).min(lat20 * hot) / bias_lat;
    let ring_rob = (ring20 * tk1).min(ring20 * hot) / bias_ring;
    let f = Fem { lat20, pry20: sy20 / pry_pk.max(1e-12), twist20_nmm: sy20 / st.max(1e-12), ring20, lat_rob, ring_rob,
        sf_hiker: lat_rob / floors::HIKER_LATERAL_N, sf_hunter: lat_rob / floors::HUNTER_LATERAL_N, sf_ring: ring_rob / floors::RING_PULL_N,
        lat_at: cen[el], ring_at: ring_pk.1, nodes: n, tris: ne,
        floors_ok: lat_rob >= floors::HIKER_LATERAL_N && lat_rob >= floors::HUNTER_LATERAL_N && ring_rob >= floors::RING_PULL_N };
    let fields = if keep {
        let sy100 = m.yield_at(100.0);
        let ring_c: Vec<f64> = (0..ne).map(|e| if cen[e].0 >= sx0 - 3.0 { 0.0 } else { ring[e] }).collect();
        let env: Vec<f64> = (0..ne).map(|e| if excl[e] { 0.0 } else {
            (lat[e] * floors::HUNTER_LATERAL_N).max(twist[e] * TWIST_DESIGN_NMM).max(pry[e] * floors::HUNTER_LATERAL_N).max(ring_c[e] * floors::RING_PULL_N) }).collect();
        let sf = env.iter().map(|v| if *v > 0.0 { sy100 / v } else { 10.0 }).collect();
        Some(Fields { xy: xy.clone(), tris: plate.mesh.tris.clone(), te, env_vm: env, sf, lat, pry, ring: ring_c, twist })
    } else { None };
    Some((f, fields))
}

fn seg_on_ring(t6: &fine::T6, i: usize, ring_node: &[bool]) -> bool {
    // a midside node is on the ring hole only if both corners of its edge are ring nodes
    for t in &t6.tris { for (a, b, m) in [(t[0], t[1], t[3]), (t[1], t[2], t[4]), (t[2], t[0], t[5])] {
        if m == i { return ring_node[a] && ring_node[b]; } } }
    false
}
