//! Detailed plate FEM on the crescent with the per-element thickness field
//! (physics::fine DKT bending + CST/T6 membrane; same element code as the calibrated search).
//! Load cases (crescent frame, ring at origin):
//!   lateral: ring-hole edge clamped, out-of-plane tip load on a 2 mm patch (180/260 N floors);
//!   twist:   ring clamped, TORQUE about the ring->tip chord (D1 fix: slope-dof load along the in-plane
//!            normal n = (-d_y, d_x); the pre-D1 load along d was a BENDING couple about n, kept as
//!            `couple20_nmm` for the record). Proposed first-yield floor 1.82 N*m (TWIST_FLOOR_NMM),
//!            joint thin+hot, with the St-Venant 3D thick-section correction at the peak section;
//!   pry:     ring clamped, in-plane tip load perpendicular to the chord (T6, no floor);
//!   ring:    guard/ricasso band x in [76, 100]+dx seated, -x traction on the ring hole (1500 N floor).
//! Robust level (D1) = JOINT realisation 20 C capacity x (stock -0.1 mm) x (100 C yield) / search-mesh bias
//! (product, not the pre-D1 min of the two); screening yield 828 MPa (physics::TI_6AL_4V, TIMET min);
//! winners are re-judged by `certify` (min over 0.25 and 0.125 mm^2, no bias).
use crate::geom::*;
use crate::pheno::*;
use jarambit_physics::{fine, floors, material};

#[derive(Clone, Debug, Default)]
pub struct Fem {
    pub lat20: f64, pub pry20: f64, pub twist20_nmm: f64, pub ring20: f64,
    pub lat_rob: f64, pub ring_rob: f64, pub sf_hiker: f64, pub sf_hunter: f64, pub sf_ring: f64,
    pub lat_at: P2, pub ring_at: P2, pub nodes: usize, pub tris: usize, pub floors_ok: bool,
    /// D1: pre-D1 "twist" load (bending couple about the in-plane normal), N*mm at 20 C first yield.
    pub couple20_nmm: f64,
    /// D1: St-Venant 3D/plate stress factor at the chord-torsion peak section (>= 1), section width b
    /// (mm, along n through the peak) and local thickness there.
    pub twist_kc: f64, pub twist_b_mm: f64, pub twist_t_mm: f64, pub twist_at: P2,
    /// D1: joint thin+hot, 3D-corrected chord-torsion first-yield capacity (N*mm) and SF vs 1.82 N*m.
    pub twist_joint_nmm: f64, pub twist_sf: f64,
    /// D1 failure-sequence proxy: min over lateral / chord-torsion / pry of
    /// (hand-zone yield-onset load) / (blade-zone yield-onset load); target >= 1.2.
    pub seq_ratio: f64, pub seq_case: &'static str,
    /// D1 tip-locality of the chord-torsion peak: distance of the peak from the tip (mm), and the joint
    /// (no 3D factor) first-yield torque if the peak search excludes 15 mm around the tip ("body"), and
    /// if it is restricted to the hand side x < heel.x - 3 mm ("hand").
    pub twist_tipdist: f64, pub twist_body_joint_nmm: f64, pub twist_hand_joint_nmm: f64,
    /// D1 P1 two-fixture twist report (Jepson pending tip vs body+submodel; default hard evaluation on finalists
    /// = the tip-loaded `twist_sf`): BODY = same 1.82 N*m tip torque, peak searched > 15 mm from the tip, St-Venant
    /// 3D factor at the body peak section; TIP SUBMODEL = peak restricted to the 4..15 mm tip annulus with its own
    /// 3D factor (taken from the strict 0.0625 mm^2 solve in crescent-d1 / certification).
    pub twist_body_kc: f64, pub twist_body_sf: f64, pub twist_tipzone_kc: f64, pub twist_tipzone_joint_nmm: f64, pub twist_tipzone_sf: f64,
}

pub struct Fields { pub xy: Vec<P2>, pub tris: Vec<[usize; 3]>, pub te: Vec<f64>, pub env_vm: Vec<f64>, pub sf: Vec<f64>,
    pub lat: Vec<f64>, pub pry: Vec<f64>, pub ring: Vec<f64>, pub twist: Vec<f64> }

/// Pre-D1 advisory design torque (180 N x 7 mm). Superseded by TWIST_FLOOR_NMM; kept for old reports.
pub const TWIST_DESIGN_NMM: f64 = 180.0 * 7.0;
/// D1 proposed chord-torsion first-yield floor (N*mm), joint thin+hot, 3D-corrected.
pub const TWIST_FLOOR_NMM: f64 = 1820.0;
/// D1 failure-sequence target: hand-adjacent onset >= 1.2 x blade-zone onset.
pub const SEQ_TARGET: f64 = 1.2;
/// OWNER LOCK (Jepson, 2026-10-11 14:52 MT): twist floor = BODY torsion AND TIP SUBMODEL, both at 1.82 N*m chord
/// torsion (joint thin+hot, 828, St-Venant 3D), SF >= 1 each. Tip-only SF is always reported alongside (not the gate).
pub fn twist_floor_ok(body_sf: f64, tipzone_sf_strict: f64) -> bool { body_sf >= 1.0 && tipzone_sf_strict >= 1.0 }
/// Requirement set these constants implement (requirements/RS-karambit-v1.toml). Every published verdict names it.
pub const REQUIREMENT_SET_ID: &str = "RS-karambit-v1";
/// Mass is SOFT (Jepson decision 2026-10-12, supersedes the 2026-10-11 owner lock): not a promotion gate. It is a
/// strong penalty in G / a ranking target: first get under MASS_TARGET_G, then toward MASS_STRETCH_G. The 74-77 g band
/// is still reported for continuity.
pub const MASS_BAND: (f64, f64) = (74.0, 77.0); pub const MASS_TARGET_G: f64 = 80.0; pub const MASS_STRETCH_G: f64 = 70.0;
/// OWNER LOCK promote-eligibility (still needs human aesthetic sign-off; never auto-promoted):
/// aesthetic C.6 + every hard gate (blade >= 3.375 in on all three measures, ...) + 828 joint floors at certification
/// + hunter >= 260 at strict 0.0625 + seq >= 1.2 + twist body AND tip submodel >= 1.82 N*m + mass in 74-77 g and < 80 g.
#[allow(clippy::too_many_arguments)]
/// Promote-eligible (structural + aesthetic floor; mass is soft and NOT part of it). Human aesthetic sign-off still required.
pub fn promote_eligible(aes_pass: bool, gates_ok: bool, floors_ok: bool, strict_lat: f64, seq: f64, body_sf: f64, tipzone_sf: f64) -> bool {
    aes_pass && gates_ok && floors_ok && strict_lat >= floors::HUNTER_LATERAL_N && seq >= SEQ_TARGET && twist_floor_ok(body_sf, tipzone_sf)
}

/// D1 JOINT robustness factor: (stock -0.1 mm)^p x yield(100 C)/yield(20 C), both at once
/// (p = 2 for bending/torsion surface stress, 1 for membrane). Replaces min(thin, hot).
pub fn joint_k(m: &jarambit_physics::Material, t: f64, p: i32) -> f64 { ((t - 0.1) / t).powi(p) * m.yield_at(100.0) / m.yield_at(20.0) }

/// St-Venant torsion of a b x t rectangle (b >= t), exact 3D-elasticity series:
/// tau_max = T / (alpha b t^2); alpha = k1 / k with k1 = (1/3)(1 - 192/pi^5 (t/b) sum tanh(n pi b/2t)/n^5),
/// k = 1 - 8/pi^2 sum 1/(n^2 cosh(n pi b / 2t)), n odd.
pub fn alpha_rect(r: f64) -> f64 {
    let r = r.max(1.0); let pi = std::f64::consts::PI;
    let (mut s1, mut s2) = (0.0, 0.0);
    for i in 0..60 { let n = (2 * i + 1) as f64; s1 += (n * pi * r / 2.0).tanh() / n.powi(5); s2 += 1.0 / (n * n * (n * pi * r / 2.0).cosh()); }
    let k1 = (1.0 - 192.0 / pi.powi(5) / r * s1) / 3.0; let k = 1.0 - 8.0 / (pi * pi) * s2;
    k1 / k
}
/// Kirchhoff plate (thin-strip) surface stress 3T/(b t^2) -> 3D peak: multiply plate stress by this (>= 1).
pub fn torsion_3d_factor(r: f64) -> f64 { (1.0 / 3.0) / alpha_rect(r) }
/// Crescent-specific search-mesh bias, MEASURED by `jarambit crescent-conv` (out/crescent_conv):
/// detailed plate at the 2 mm^2 search level over the 0.125 mm^2 reference on 25 distinct aesthetic
/// passers (legal winners + a stride of the run): lateral max 1.105, ring max 1.073 (ground edges + hawkbill tip are more mesh-sensitive
/// than the flat jarambit calibration of 1.070 / 1.062). Rounded up.
pub const SEARCH_BIAS_LAT: f64 = 1.11;
pub const SEARCH_BIAS_RING: f64 = 1.08;
/// Certification levels: capacity = MIN over these two converged levels (no bias applied).
pub const CERT_AREAS: [f64; 2] = [0.25, 0.125];

pub fn run(p: &Pheno, max_area: f64, keep: bool) -> Option<(Fem, Option<Fields>)> { run_b(p, max_area, keep, search_bias().0, search_bias().1) }

/// Search-mesh bias actually applied: crescent default (1.11 / 1.08) unless JARAMBIT_SEARCH_BIAS_LAT /
/// _RING override it (machined-lattice calibration, out/wave7_conv: lateral 2.0/ref up to 1.28).
pub fn search_bias() -> (f64, f64) {
    static B: std::sync::OnceLock<(f64, f64)> = std::sync::OnceLock::new();
    *B.get_or_init(|| {
        let e = |k: &str, d: f64| std::env::var(k).ok().and_then(|v| v.parse::<f64>().ok()).filter(|x| *x >= 1.0).unwrap_or(d);
        (e("JARAMBIT_SEARCH_BIAS_LAT", SEARCH_BIAS_LAT), e("JARAMBIT_SEARCH_BIAS_RING", SEARCH_BIAS_RING)) })
}

/// Unbiased capacities at one mesh level (refinement studies beyond certification).
pub fn run_unbiased(p: &Pheno, max_area: f64) -> Option<Fem> { run_b(p, max_area, false, 1.0, 1.0).map(|x| x.0) }

/// Certified capacities: min over CERT_AREAS of the 20 C capacities, robust factors applied, no
/// mesh bias (these are the reference levels). Fields (for plates) come from the 0.25 mm^2 level.
pub fn certify(p: &Pheno) -> Option<(Fem, Fields)> {
    let (a, fa) = run_b(p, CERT_AREAS[0], true, 1.0, 1.0)?;
    let (b, _) = run_b(p, CERT_AREAS[1], false, 1.0, 1.0)?;
    let m = material(p.mat);
    let gov = if a.lat20 <= b.lat20 { &a } else { &b };
    let lat20 = a.lat20.min(b.lat20); let ring20 = a.ring20.min(b.ring20);
    let lat_rob = lat20 * joint_k(&m, p.t_joint, 2); let ring_rob = ring20 * joint_k(&m, p.t_joint, 1);
    let tg = if a.twist_joint_nmm <= b.twist_joint_nmm { &a } else { &b };
    let f = Fem { lat20, pry20: a.pry20.min(b.pry20), twist20_nmm: a.twist20_nmm.min(b.twist20_nmm), ring20, lat_rob, ring_rob,
        couple20_nmm: a.couple20_nmm.min(b.couple20_nmm), twist_kc: tg.twist_kc, twist_b_mm: tg.twist_b_mm, twist_t_mm: tg.twist_t_mm, twist_at: tg.twist_at,
        twist_joint_nmm: tg.twist_joint_nmm, twist_sf: tg.twist_sf,
        twist_body_kc: if a.twist_body_sf <= b.twist_body_sf { a.twist_body_kc } else { b.twist_body_kc }, twist_body_sf: a.twist_body_sf.min(b.twist_body_sf),
        twist_tipzone_kc: if a.twist_tipzone_sf <= b.twist_tipzone_sf { a.twist_tipzone_kc } else { b.twist_tipzone_kc }, twist_tipzone_joint_nmm: a.twist_tipzone_joint_nmm.min(b.twist_tipzone_joint_nmm), twist_tipzone_sf: a.twist_tipzone_sf.min(b.twist_tipzone_sf),
        twist_tipdist: tg.twist_tipdist, twist_body_joint_nmm: a.twist_body_joint_nmm.min(b.twist_body_joint_nmm), twist_hand_joint_nmm: a.twist_hand_joint_nmm.min(b.twist_hand_joint_nmm),
        seq_ratio: if a.seq_ratio <= b.seq_ratio { a.seq_ratio } else { b.seq_ratio }, seq_case: if a.seq_ratio <= b.seq_ratio { a.seq_case } else { b.seq_case },
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
    // dofs per node (u, v, w, w_x, w_y): a torque T about the unit chord d does work T*phi with
    // grad w = phi*(-d_y, d_x) = phi*n, so the consistent slope load is T*n (D1 fix). Load along d = bending couple.
    let mut f_lat = vec![0.0; n * 5]; let mut f_tw = vec![0.0; n * 5]; let mut f_cp = vec![0.0; n * 5];
    for &i in &patch { f_lat[i * 5 + 2] = 1.0 / k; f_tw[i * 5 + 3] = nvec.0 / k; f_tw[i * 5 + 4] = nvec.1 / k;
        f_cp[i * 5 + 3] = dvec.0 / k; f_cp[i * 5 + 4] = dvec.1 / k; }
    let (_, lat) = plate.stresses(&plate.solve(&sys, &f_lat));
    let (_, twist) = plate.stresses(&plate.solve(&sys, &f_tw));
    let (_, couple) = plate.stresses(&plate.solve(&sys, &f_cp));
    drop(sys);
    let peak = |v: &[f64], ex: &[bool]| { let mut b = (0.0, 0usize); for (e, &s) in v.iter().enumerate() { if !ex[e] && s.is_finite() && s > b.0 { b = (s, e); } } b };
    let (sl, el) = peak(&lat, &excl); let (st, et_e) = peak(&twist, &excl); let (sc, _) = peak(&couple, &excl);
    // section through the twist peak along n (inside the outline, outside every hole) -> St-Venant 3D factor
    let inside = |q: P2| point_in_poly(q, &outer) && !holes.iter().any(|h| point_in_poly(q, h));
    let walk = |s: f64| { let mut d = 0.0; while d < 60.0 && inside((cen[et_e].0 + s * (d + 0.05) * nvec.0, cen[et_e].1 + s * (d + 0.05) * nvec.1)) { d += 0.05; } d };
    let kc_at = |e: usize| { let w = |s: f64| { let mut d = 0.0; while d < 60.0 && inside((cen[e].0 + s * (d + 0.05) * nvec.0, cen[e].1 + s * (d + 0.05) * nvec.1)) { d += 0.05; } d };
        let b = w(1.0) + w(-1.0); let t = te[e]; torsion_3d_factor(b.max(t) / b.min(t).max(1e-6)) };
    let tw_b = walk(1.0) + walk(-1.0); let tw_t = te[et_e];
    let tw_kc = torsion_3d_factor(tw_b.max(tw_t) / tw_b.min(tw_t).max(1e-6));
    let excl15: Vec<bool> = cen.iter().map(|c| dist(*c, tp) < 15.0).collect();
    let tipzone_ex: Vec<bool> = cen.iter().map(|c| { let d = dist(*c, tp); d < fine::TIP_EXCL_MM || d >= 15.0 }).collect();
    let hand_ex: Vec<bool> = cen.iter().map(|c| c.0 >= p.heel.0 - 3.0).collect();
    let (st_body, e_body) = peak(&twist, &excl15); let (st_hand, _) = peak(&twist, &hand_ex); let (st_tz, e_tz) = peak(&twist, &tipzone_ex);
    let (kc_body, kc_tz) = (kc_at(e_body), kc_at(e_tz));
    let mt = material(p.mat); let jk2 = joint_k(&mt, p.t_joint, 2);
    let body_j3 = mt.yield_at(20.0) / st_body.max(1e-12) * jk2 / kc_body; let tz_j3 = mt.yield_at(20.0) / st_tz.max(1e-12) * jk2 / kc_tz;
    // failure-sequence proxy: blade zone = x >= heel.x (sharpened blade), hand zone = x < heel.x - 3 mm
    let zone_pk = |v: &[f64]| { let (mut hb, mut bb) = (0.0f64, 0.0f64); for e in 0..ne { if excl[e] || !v[e].is_finite() { continue; }
        if cen[e].0 >= p.heel.0 { bb = bb.max(v[e]); } else if cen[e].0 < p.heel.0 - 3.0 { hb = hb.max(v[e]); } } (hb, bb) };
    let mut seq = (f64::INFINITY, "none");
    for (v, nm) in [(&lat, "lateral"), (&twist, "chord-torsion")] { let (hb, bb) = zone_pk(v); if hb > 0.0 && bb > 0.0 { let r = bb / hb; if r < seq.0 { seq = (r, nm); } } }
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
    // pry hand/blade split on the T6 nodal field
    let (mut ph, mut pb) = (0.0f64, 0.0f64);
    for i in 0..n6 { let q = t6.xy[i]; if dist(q, tp) < fine::TIP_EXCL_MM { continue; } let v = fine::von_mises(nod_pr[i]);
        if q.0 >= p.heel.0 { pb = pb.max(v); } else if q.0 < p.heel.0 - 3.0 && !ring6[i] { ph = ph.max(v); } }
    if ph > 0.0 && pb > 0.0 && pb / ph < seq.0 { seq = (pb / ph, "pry"); }
    let sy20 = m.yield_at(20.0);
    let lat20 = sy20 / sl.max(1e-12); let ring20 = sy20 / ring_pk.0.max(1e-12);
    let lat_rob = lat20 * joint_k(&m, p.t_joint, 2) / bias_lat;
    let ring_rob = ring20 * joint_k(&m, p.t_joint, 1) / bias_ring;
    let twist20 = sy20 / st.max(1e-12); let tw_joint = twist20 * joint_k(&m, p.t_joint, 2) / tw_kc;
    let f = Fem { lat20, pry20: sy20 / pry_pk.max(1e-12), twist20_nmm: twist20, ring20, lat_rob, ring_rob,
        couple20_nmm: sy20 / sc.max(1e-12), twist_kc: tw_kc, twist_b_mm: tw_b, twist_t_mm: tw_t, twist_at: cen[et_e],
        twist_joint_nmm: tw_joint, twist_sf: tw_joint / TWIST_FLOOR_NMM, seq_ratio: seq.0, seq_case: seq.1,
        twist_tipdist: dist(cen[et_e], tp), twist_body_joint_nmm: sy20 / st_body.max(1e-12) * joint_k(&m, p.t_joint, 2),
        twist_hand_joint_nmm: sy20 / st_hand.max(1e-12) * joint_k(&m, p.t_joint, 2),
        twist_body_kc: kc_body, twist_body_sf: body_j3 / TWIST_FLOOR_NMM, twist_tipzone_kc: kc_tz, twist_tipzone_joint_nmm: tz_j3, twist_tipzone_sf: tz_j3 / TWIST_FLOOR_NMM,
        sf_hiker: lat_rob / floors::HIKER_LATERAL_N, sf_hunter: lat_rob / floors::HUNTER_LATERAL_N, sf_ring: ring_rob / floors::RING_PULL_N,
        lat_at: cen[el], ring_at: ring_pk.1, nodes: n, tris: ne,
        floors_ok: lat_rob >= floors::HIKER_LATERAL_N && lat_rob >= floors::HUNTER_LATERAL_N && ring_rob >= floors::RING_PULL_N };
    let fields = if keep {
        let sy100 = m.yield_at(100.0) * ((p.t_joint - 0.1) / p.t_joint).powi(2);
        let ring_c: Vec<f64> = (0..ne).map(|e| if cen[e].0 >= sx0 - 3.0 { 0.0 } else { ring[e] }).collect();
        let env: Vec<f64> = (0..ne).map(|e| if excl[e] { 0.0 } else {
            (lat[e] * floors::HUNTER_LATERAL_N).max(twist[e] * TWIST_FLOOR_NMM * tw_kc).max(pry[e] * floors::HUNTER_LATERAL_N).max(ring_c[e] * floors::RING_PULL_N) }).collect();
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

#[cfg(test)]
mod rs_karambit_v1 {
    use super::*;
    const RS: &str = include_str!("../../../requirements/RS-karambit-v1.toml");
    fn val(key: &str) -> String {
        RS.lines().map(|l| l.split('#').next().unwrap().trim()).find(|l| l.starts_with(&format!("{key} ")) || l.starts_with(&format!("{key}=")))
            .unwrap_or_else(|| panic!("{key} missing in RS toml")).split_once('=').unwrap().1.trim().to_string()
    }
    fn num(key: &str) -> f64 { val(key).parse().unwrap_or_else(|_| panic!("{key} not a number")) }
    fn pair(key: &str) -> (f64, f64) {
        let v = val(key); let v = v.trim_matches(|c| c == '[' || c == ']');
        let mut it = v.split(',').map(|x| x.trim().parse::<f64>().unwrap()); (it.next().unwrap(), it.next().unwrap())
    }
    #[test]
    fn rs_karambit_v1_matches_code() {
        assert_eq!(val("id"), format!("\"{REQUIREMENT_SET_ID}\""));
        assert_eq!(num("seq_target"), SEQ_TARGET);
        assert_eq!(num("twist_floor_nmm"), TWIST_FLOOR_NMM);
        assert_eq!(num("mass_target_g"), MASS_TARGET_G); assert_eq!(num("mass_stretch_g"), MASS_STRETCH_G);
        assert_eq!(pair("mass_band_g"), MASS_BAND);
        assert_eq!(num("hiker_lateral_n"), floors::HIKER_LATERAL_N);
        assert_eq!(num("hunter_lateral_n"), floors::HUNTER_LATERAL_N);
        assert_eq!(num("ring_pull_n"), floors::RING_PULL_N);
        assert!((num("blade_limit_mm") - jarambit_genotype::limits::BLADE_LIMIT_MM).abs() < 1e-9);
    }
}
