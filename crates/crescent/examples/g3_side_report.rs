//! Side report for g3. Reads the plate fields `report_fields` already computes.
//! Does not change `seq_ratio`, a gate, or fitness. Writes one JSON file.
use jarambit_crescent::c6_ref;
use jarambit_crescent::fem::{self, Fem, Fields};
use jarambit_crescent::genome::Genome;
use jarambit_crescent::pheno;
use jarambit_physics::fine::TIP_EXCL_MM;
use jarambit_physics::floors;
use std::env;
use std::fs;
use std::process::ExitCode;

const MODULI: [f64; 3] = [10.0, 20.0, 30.0];
const EXCL: [f64; 2] = [TIP_EXCL_MM, 15.0];
const DK: [f64; 3] = [2.0, 4.0, 6.0];
const NECK_BAND_MM: f64 = 8.0;
const LOCAL_AREA_MM2: f64 = 10.0;
const COMMITTED_SEQ: f64 = 0.9590825616164743;

fn main() -> ExitCode {
    let mut args = env::args().skip(1);
    let Some(genome) = args.next() else { eprintln!("usage: g3_side_report GENOME.csv OUT.json"); return ExitCode::from(2); };
    let Some(out) = args.next() else { eprintln!("usage: g3_side_report GENOME.csv OUT.json"); return ExitCode::from(2); };
    let Ok(txt) = fs::read_to_string(&genome) else { eprintln!("cannot read {genome}"); return ExitCode::from(1); };
    let mut lines = txt.lines();
    let Some(hdr) = lines.next() else { eprintln!("empty genome"); return ExitCode::from(1); };
    let cols: Vec<&str> = hdr.split(',').collect();
    let Some(off) = cols.iter().position(|c| *c == "cp00") else { eprintln!("no cp00 column"); return ExitCode::from(1); };
    let Some(row) = lines.next() else { eprintln!("no data row"); return ExitCode::from(1); };
    let fields: Vec<&str> = row.split(',').collect();
    let Some(g) = Genome::from_csv(&fields[off.min(fields.len())..]) else { eprintln!("genome parse failed"); return ExitCode::from(1); };
    let p = pheno::build(&g);
    let area = fem::CERT_AREAS[0];
    let Some((f, fl)) = fem::report_fields(&p, area) else { eprintln!("solve failed"); return ExitCode::from(1); };
    let check = fem::run_unbiased(&p, area);
    let seq_matches_unbiased = check.as_ref().map(|c| (c.seq_ratio - f.seq_ratio).abs() < 1e-12).unwrap_or(false);
    if !seq_matches_unbiased { eprintln!("seq_ratio from report_fields disagrees with run_unbiased"); return ExitCode::from(1); }

    let r_bore = p.ring_id / 2.0;
    let r_od = p.ring_od / 2.0;
    let g0 = r_bore + c6_ref::RING_GROOVE_RIM;
    let g1 = r_od - c6_ref::RING_GROOVE_RIM;
    let heel_x = p.heel.0;
    let tip = p.tip;
    let n = fl.tris.len();
    if fl.lat.len() != n || fl.twist.len() != n || fl.pry.len() != n || fl.ring.len() != n || fl.te.len() != n {
        eprintln!("field length mismatch");
        return ExitCode::from(1);
    }
    let mut cen = Vec::with_capacity(n);
    let mut area_e = Vec::with_capacity(n);
    let mut zone = Vec::with_capacity(n);
    for tri in &fl.tris {
        let (a, b, c) = (fl.xy[tri[0]], fl.xy[tri[1]], fl.xy[tri[2]]);
        let q = ((a.0 + b.0 + c.0) / 3.0, (a.1 + b.1 + c.1) / 3.0);
        let ar = 0.5 * ((b.0 - a.0) * (c.1 - a.1) - (b.1 - a.1) * (c.0 - a.0)).abs();
        let r = q.0.hypot(q.1);
        let z = if r >= r_bore && r < g0 { "bore_rim" }
            else if r >= g0 && r <= g1 { "groove" }
            else if r > r_od && r <= r_od + NECK_BAND_MM && q.0 > 0.0 && q.0 < heel_x { "neck" }
            else if q.0 >= heel_x { "blade" }
            else { "other" };
        cen.push(q);
        area_e.push(ar);
        zone.push(z);
    }

    let cases = [("lateral", fl.lat.as_slice()), ("chord_twist", fl.twist.as_slice()), ("pry", fl.pry.as_slice()), ("ring_pull", fl.ring.as_slice())];
    let mut case_json = serde_json::Map::new();
    for (name, sig) in cases {
        let mut by_excl = serde_json::Map::new();
        for &ex in &EXCL {
            by_excl.insert(format!("{ex}"), exclusion_report(sig, &cen, &area_e, &zone, &tip, ex, r_bore, g0, g1));
        }
        case_json.insert(name.into(), serde_json::Value::Object(by_excl));
    }

    let flaw = flaw_map(&fl, &area_e, &zone);
    let case_val = serde_json::Value::Object(case_json.clone());
    let loads = load_split(&f, &case_val);
    let doc = serde_json::json!({
        "schema": "jarambit.side_report.a1a3.v1",
        "role": "side report. seq_ratio, gates, and fitness are unchanged",
        "genome": genome,
        "mesh_max_area_mm2": area,
        "search_bias": "none",
        "n_elem": n,
        "n_node": fl.xy.len(),
        "mass_g": p.mass_g,
        "heel_x_mm": heel_x,
        "tip_xy_mm": [tip.0, tip.1],
        "ring_id_mm": p.ring_id,
        "ring_od_mm": p.ring_od,
        "groove_radii_mm": [g0, g1],
        "groove_depth_per_face_mm": c6_ref::RING_GROOVE_D,
        "zone_rules": {
            "bore_rim": "centroid radius in [bore radius, bore radius + 1.6 mm)",
            "groove": "centroid radius in [bore radius + 1.6 mm, outer radius - 1.6 mm]",
            "neck": format!("centroid outside the ring OD by at most {NECK_BAND_MM} mm, x > 0, and x < heel"),
            "blade": "centroid x >= heel, and not already bore, groove, or neck",
            "other": "everything else",
            "priority": "bore_rim, groove, neck, blade, other"
        },
        "seq_ratio_this_mesh": f.seq_ratio,
        "seq_case_this_mesh": f.seq_case,
        "seq_matches_run_unbiased": seq_matches_unbiased,
        "committed_g3_seq_ratio": COMMITTED_SEQ,
        "committed_seq_note": "evidence/rs_v2/g3_tip+00_t60_tt3.json seq_ratio is fem::certify, the minimum of 0.25 mm^2 and 0.125 mm^2. This file is the 0.25 mm^2 field only.",
        "stress_unit": "von Mises, MPa per unit load. Lateral and chord twist are plate bending surface stress. Pry and ring pull are in-plane centroid stress.",
        "weibull_note": "A_eff = sum area * (sigma/sigma_global_max)^m over non-excluded elements. m is a sensitivity, not a fit. Shares use all non-excluded elements.",
        "local_concentration_rule": format!("reporter label only: area within 90% of the global peak < {LOCAL_AREA_MM2} mm^2. Not a material length."),
        "cases": case_json,
        "load_split": loads,
        "flaw_map": flaw
    });
    if let Some(parent) = std::path::Path::new(&out).parent() { fs::create_dir_all(parent).ok(); }
    if fs::write(&out, serde_json::to_string_pretty(&doc).unwrap() + "\n").is_err() {
        eprintln!("cannot write {out}");
        return ExitCode::from(1);
    }
    println!("wrote {out}");
    println!("seq_ratio_0.25={:.6} case={} committed={COMMITTED_SEQ:.6}", f.seq_ratio, f.seq_case);
    ExitCode::SUCCESS
}

fn exclusion_report(sig: &[f64], cen: &[(f64, f64)], area_e: &[f64], zone: &[&str], tip: &(f64, f64), excl: f64, r_bore: f64, g0: f64, g1: f64) -> serde_json::Value {
    let keep: Vec<bool> = cen.iter().enumerate().map(|(i, q)| {
        let d = (q.0 - tip.0).hypot(q.1 - tip.1);
        d >= excl && sig[i].is_finite() && sig[i] > 0.0 && area_e[i] > 0.0
    }).collect();
    let mut gmax = 0.0;
    let mut ipeak = 0usize;
    for (i, &s) in sig.iter().enumerate() {
        if keep[i] && s > gmax { gmax = s; ipeak = i; }
    }
    let names = ["bore_rim", "groove", "neck", "blade", "other"];
    let mut zones = serde_json::Map::new();
    let mut aeff_tot = [0.0; 3];
    let mut per: Vec<([f64; 3], f64, f64, f64)> = Vec::new();
    for name in names {
        let mut peak: f64 = 0.0;
        let mut area: f64 = 0.0;
        let mut a90: f64 = 0.0;
        let mut aeff = [0.0; 3];
        for i in 0..sig.len() {
            if !keep[i] || zone[i] != name { continue; }
            let s = sig[i];
            peak = peak.max(s);
            area += area_e[i];
            if gmax > 0.0 && s >= 0.9 * gmax { a90 += area_e[i]; }
            if gmax > 0.0 {
                let u = s / gmax;
                for (k, &m) in MODULI.iter().enumerate() {
                    let w = area_e[i] * u.powf(m);
                    aeff[k] += w;
                    aeff_tot[k] += w;
                }
            }
        }
        per.push((aeff, peak, area, a90));
        let _ = name;
    }
    for (i, name) in names.iter().enumerate() {
        let (aeff, peak, area, a90) = per[i];
        let mut share = serde_json::Map::new();
        let mut ae = serde_json::Map::new();
        for (k, &m) in MODULI.iter().enumerate() {
            ae.insert(format!("{m}"), serde_json::json!(aeff[k]));
            let sh = if aeff_tot[k] > 0.0 { aeff[k] / aeff_tot[k] } else { 0.0 };
            share.insert(format!("{m}"), serde_json::json!(sh));
        }
        zones.insert((*name).into(), serde_json::json!({
            "peak_mpa_per_unit": peak,
            "area_mm2": area,
            "area_within_90pct_of_global_peak_mm2": a90,
            "a_eff_mm2": ae,
            "share_of_a_eff": share
        }));
    }
    if gmax <= 0.0 {
        return serde_json::json!({"tip_exclusion_mm": excl, "global_peak_mpa_per_unit": 0.0, "zones": {}});
    }
    let q = cen[ipeak];
    let r = q.0.hypot(q.1);
    let dist_bore = r - r_bore;
    let dist_groove = if r < g0 { g0 - r } else if r > g1 { r - g1 } else { 0.0 };
    serde_json::json!({
        "tip_exclusion_mm": excl,
        "global_peak_mpa_per_unit": gmax,
        "peak_xy_mm": [q.0, q.1],
        "peak_radius_mm": r,
        "peak_distance_outside_bore_mm": dist_bore,
        "peak_distance_to_groove_annulus_mm": dist_groove,
        "peak_zone": zone[ipeak],
        "zones": zones
    })
}

fn flaw_map(fl: &Fields, area_e: &[f64], zone: &[&str]) -> serde_json::Value {
    // Code L7: lateral 0..180 N, R = 0. Range equals the peak stress at 180 N.
    let load = fem::fatigue::CYCLIC_LATERAL_N;
    let names = ["bore_rim", "groove", "neck", "blade", "other"];
    let mut zones = serde_json::Map::new();
    for name in names {
        let mut hot = 0.0;
        let mut hot_i = None;
        let mut n = 0usize;
        for i in 0..fl.lat.len() {
            if zone[i] != name { continue; }
            n += 1;
            let s = fl.lat[i] * load;
            if s.is_finite() && s > hot { hot = s; hot_i = Some(i); }
        }
        let mut allow = serde_json::Map::new();
        let mut below_40um = serde_json::Map::new();
        let mut below_10um = serde_json::Map::new();
        for &dk in &DK {
            let a = a_allow_mm(dk, hot);
            allow.insert(format!("{dk}"), serde_json::json!(a));
            let mut n40 = 0usize;
            let mut n10 = 0usize;
            let mut area40 = 0.0;
            for i in 0..fl.lat.len() {
                if zone[i] != name { continue; }
                let s = fl.lat[i] * load;
                if !s.is_finite() || s <= 0.0 { continue; }
                let ai = a_allow_mm(dk, s);
                if ai < 0.040 { n40 += 1; area40 += area_e[i]; }
                if ai < 0.010 { n10 += 1; }
            }
            below_40um.insert(format!("{dk}"), serde_json::json!({"n_elem": n40, "area_mm2": area40}));
            below_10um.insert(format!("{dk}"), serde_json::json!(n10));
        }
        zones.insert(name.into(), serde_json::json!({
            "n_elem": n,
            "hottest_delta_sigma_mpa": hot,
            "hottest_xy_mm": hot_i.map(|i| {
                let t = &fl.tris[i];
                let (a, b, c) = (fl.xy[t[0]], fl.xy[t[1]], fl.xy[t[2]]);
                [(a.0 + b.0 + c.0) / 3.0, (a.1 + b.1 + c.1) / 3.0]
            }),
            "a_allow_at_hottest_mm": allow,
            "elements_with_a_allow_below_0.040_mm": below_40um,
            "n_elem_with_a_allow_below_0.010_mm": below_10um
        }));
    }
    serde_json::json!({
        "basis": "code L7, lateral 0 to 180 N, R = 0. Delta sigma = 180 * lateral MPa-per-newton. Not spec L7.",
        "formula": "a = (1/pi) * (DeltaK_th / (1.12 * Delta_sigma))^2, metres, reported in mm",
        "geometry_factor": 1.12,
        "delta_k_th_mpa_sqrt_m": DK,
        "delta_k_note": "sensitivity range, not a measured threshold for this lot",
        "not_a_drawing_zone": true,
        "not_the_additive_manufacturing_murakami_curve": true,
        "zones": zones
    })
}

fn a_allow_mm(dk_mpa_sqrt_m: f64, dsig_mpa: f64) -> f64 {
    if dsig_mpa <= 0.0 { return f64::INFINITY; }
    let a_m = (1.0 / std::f64::consts::PI) * (dk_mpa_sqrt_m / (1.12 * dsig_mpa)).powi(2);
    a_m * 1000.0
}

fn area90_of(cases: &serde_json::Value, name: &str) -> Option<f64> {
    let zones = cases.get(name)?.get("4")?.get("zones")?;
    let mut s = 0.0;
    let mut any = false;
    for z in ["bore_rim", "groove", "neck", "blade", "other"] {
        if let Some(v) = zones.get(z).and_then(|x| x.get("area_within_90pct_of_global_peak_mm2")).and_then(|x| x.as_f64()) {
            s += v;
            any = true;
        }
    }
    if any { Some(s) } else { None }
}

fn load_split(f: &Fem, cases: &serde_json::Value) -> serde_json::Value {
    let row = |case: &str, direction: &str, load: f64, unit: &str, load_name: &str, requirement: f64, published_sf: f64, area90: Option<f64>| {
        let indicator = if direction == "one_directional" { serde_json::json!(2.0 * load) } else { serde_json::Value::Null };
        let label = match area90 {
            Some(a) if a < LOCAL_AREA_MM2 => "local_concentration",
            Some(_) => "spread",
            None => "field_not_kept",
        };
        serde_json::json!({
            "case": case,
            "direction": direction,
            "why": match case {
                "spine" => "distributed in-plane traction on the spine, toward the edge, ring held",
                "ring_pull" => "bore traction, grip band seated",
                "ring_back" => "static equivalent on the outer ring back, grip band seated. The 3000 N requirement already includes the provisional factor 2",
                "lateral" | "chord_twist" | "pry" => "tip load that reverses in use",
                "tip_inplane" => "in-plane tip load, record only, not a human-max gate",
                _ => ""
            },
            "first_yield_load": load,
            "first_yield_load_field": load_name,
            "unit": unit,
            "requirement": requirement,
            "published_safety_factor": published_sf,
            "shakedown_upper_indicator_twice_first_yield": indicator,
            "collapse_load": null,
            "shakedown_note": "twice this first-yield load. Elastic-perfectly plastic upper indicator on a monotonic yield. Not a safety factor. Null when the load reverses. Collapse stays null. This row is the plate model of the genome on the command line, not a B-rep V3 result. committed_g3_seq_ratio is g3's certify value and is not this mesh's sequence.",
            "area_within_90pct_of_global_peak_mm2_exclusion_4mm": area90,
            "peak_class": label
        })
    };
    serde_json::json!([
        row("lateral", "reversing", f.lat20, "N", "lat20, plate peak to 828 MPa", floors::HUNTER_LATERAL_N, f.sf_hunter, area90_of(cases, "lateral")),
        row("chord_twist", "reversing", f.hm_twist_nmm, "N*mm", "hm_twist_nmm, joint and 3D factor", fem::hm::TWIST_NMM, f.hm_twist_sf, area90_of(cases, "chord_twist")),
        row("pry", "reversing", f.pry20, "N", "pry20, in-plane peak to 828 MPa", floors::HUNTER_LATERAL_N, f.pry20 / floors::HUNTER_LATERAL_N, area90_of(cases, "pry")),
        row("ring_pull", "one_directional", f.ring20, "N", "ring20, plate peak to 828 MPa, before the joint factor", floors::RING_PULL_N, f.sf_ring, area90_of(cases, "ring_pull")),
        row("spine", "one_directional", f.hm_spine_n, "N", "hm_spine_n", fem::hm::SPINE_N, f.hm_spine_sf, None),
        row("ring_back", "one_directional", f.hm_ringback_n, "N", "hm_ringback_n", fem::hm::RINGBACK_N, f.hm_ringback_sf, None),
        row("tip_inplane", "one_directional", f.hm_tip_inplane_n, "N", "hm_tip_inplane_n", fem::hm::TIP_INPLANE_N, f.hm_tip_inplane_sf, None)
    ])
}
