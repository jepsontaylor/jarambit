//! PR-0.31.1: frozen benchmark workload (bench/fixed_1k) and timing for the two FEM tiers.
//! T1 = search evaluation (`qd::evaluate`, plate FEM at the search mesh), T1c = certification (`fem::certify`).
//! Each design is timed on one thread; `threads` workers share the list, so per-core seconds = sum of per-design times / n.
use jarambit_crescent::{fem, genome::Genome, pheno, qd};
use jarambit_genotype::Rng;
use std::time::Instant;

/// Deterministic workload: `n` genomes = seeds (as given) then mutation chains from them (Rng(seed)).
pub fn make(seeds: &str, n: usize, seed: u64, out: &str) -> bool {
    let base = crate::crescent::load_seeds(seeds, 1000);
    if base.is_empty() { eprintln!("bench-make: no seeds in {seeds}"); return false; }
    let mut r = Rng(seed); let mut gs: Vec<Genome> = base.clone();
    while gs.len() < n { let p = &base[(r.f64() * base.len() as f64) as usize % base.len()]; let mut g = p.clone();
        for _ in 0..1 + (r.f64() * 3.0) as usize { g = g.mutate(&mut r, 0.08); } gs.push(g); }
    gs.truncate(n);
    let mut s = Genome::csv_header() + "\n"; for g in &gs { s += &g.csv_row(); s.push('\n'); }
    std::fs::create_dir_all(std::path::Path::new(out).parent().unwrap_or(std::path::Path::new("."))).ok();
    std::fs::write(out, s).is_ok()
}

/// Time `tier` ("search" | "cert") over the first `n` genomes with `threads` workers. Prints one JSON line.
pub fn run(genomes: &str, tier: &str, n: usize, threads: usize, area: f64) -> bool {
    let gs: Vec<Genome> = crate::crescent::load_seeds(genomes, usize::MAX).into_iter().take(n).collect();
    if gs.is_empty() { eprintln!("bench: no genomes in {genomes}"); return false; }
    let th = threads.max(1); let t0 = Instant::now();
    let res: Vec<(f64, f64, bool)> = std::thread::scope(|s| {
        let hs: Vec<_> = (0..th).map(|t| { let gs = &gs; s.spawn(move || gs.iter().enumerate().filter(|(i, _)| i % th == t).map(|(i, g)| {
            let t1 = Instant::now();
            let (chk, ok) = match tier {
                "cert" => { let p = pheno::build(g); match fem::certify(&p) { Some((f, _)) => (f.lat_rob + f.ring_rob, true), None => (0.0, false) } }
                _ => { let r = qd::evaluate(g, i, 0, area); match &r.fem { Some(f) => (f.lat_rob + f.ring_rob, true), None => (r.mass_g, false) } }
            };
            if std::env::var_os("JARAMBIT_BENCH_DUMP").is_some() { eprintln!("design {i} {chk:.17e}"); }
            (t1.elapsed().as_secs_f64(), chk, ok) }).collect::<Vec<_>>()) }).collect();
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect() });
    let wall = t0.elapsed().as_secs_f64();
    let per: Vec<f64> = res.iter().map(|x| x.0).collect(); let fem_n = res.iter().filter(|x| x.2).count();
    let mut sorted = per.clone(); sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let checksum: f64 = res.iter().map(|x| x.1).sum();
    println!("{}", serde_json::json!({"tier": tier, "n": gs.len(), "threads": th, "fem_evaluated": fem_n, "wall_s": wall,
        "core_s_per_design_mean": per.iter().sum::<f64>() / per.len() as f64, "core_s_per_design_p50": sorted[sorted.len() / 2],
        "core_s_per_design_p95": sorted[(sorted.len() * 95 / 100).min(sorted.len() - 1)], "checksum": checksum}));
    true
}

/// PR-0.31.3: T1 (search: `qd::evaluate`, search mesh + bias) vs T2 (certification: `fem::certify`) per load case on the
/// first `n` fixed_1k genomes at 0, stride, 2*stride, ... that evaluate in both tiers (illegal genomes have no T1 FEM), plus the RS-karambit-v2 human-max / fatigue / ring-bearing values. Writes a CSV.
pub fn calib_t1t2(genomes: &str, n: usize, stride: usize, threads: usize, area: f64, out: &str) -> bool {
    let gs: Vec<Genome> = crate::crescent::load_seeds(genomes, usize::MAX).into_iter().step_by(stride.max(1)).take(2 * n).collect();
    if gs.is_empty() { return false; }
    let th = threads.max(1); let next = std::sync::atomic::AtomicUsize::new(0);
    let mut rows: Vec<(usize, String)> = std::thread::scope(|s| {
        let hs: Vec<_> = (0..th).map(|_| s.spawn(|| { let mut v = Vec::new(); loop {
            let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed); if i >= gs.len() { break v; }
            let g = &gs[i]; let r = qd::evaluate(g, i, 0, area); let p = pheno::build(g);
            let (Some(t1), Some((t2, _))) = (r.fem.clone(), fem::certify(&p)) else { continue };
            let (bw, band) = fem::ring_bearing(&p);
            v.push((i, format!("{i},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.3},{:.4},{:.4},{:.4},{:.4},{:.4},{:.4},{:.3},{:.3},{:.3}",
                p.mass_g, t1.lat_rob, t2.lat_rob, t1.ring_rob, t2.ring_rob, t1.twist_joint_nmm, t2.twist_joint_nmm, t1.pry20, t2.pry20,
                t2.hm_spine_n, t2.hm_twist_sf, t2.hm_tip_inplane_sf, t2.hm_spine_sf, t2.hm_ringback_sf, t2.fat_sf, t2.seq_ratio, bw, band, p.t)));
        } })).collect();
        hs.into_iter().flat_map(|h| h.join().unwrap()).collect() });
    rows.sort_by_key(|r| r.0); rows.truncate(n);
    let mut s = String::from("idx,mass_g,t1_lat_rob,t2_lat_rob,t1_ring_rob,t2_ring_rob,t1_twist_joint,t2_twist_joint,t1_pry20,t2_pry20,t2_hm_spine_n,hm_twist_sf,hm_tip_inplane_sf,hm_spine_sf,hm_ringback_sf,fat_sf,seq_ratio,ring_bearing_w_mm,ring_band_mm,t_mm\n");
    for r in &rows { s += &r.1; s.push('\n'); }
    eprintln!("calib-t1t2: {} / {} designs with both tiers", rows.len(), gs.len());
    std::fs::write(out, s).is_ok()
}

/// v0.32: RS-karambit-v2 verdicts for named designs (certification tier). `genomes` = comma list of `label=path.csv`
/// (one genome per file, as D1 fixtures). Writes one JSON per design to `out_dir/<label>.json`.
/// Gate status for RS-karambit-v2 records: an unobserved gate is "unverified" and never counts as met.
fn gate(v: Option<bool>) -> &'static str { match v { Some(true) => "pass", Some(false) => "fail", None => "unverified" } }

/// True only when every gate was observed and met (a missing observation can never pass).
fn all_met(g: &[Option<bool>]) -> bool { !g.is_empty() && g.iter().all(|v| *v == Some(true)) }

/// Content-keyed solid evidence: the genome/model identity, bound CSV and GCI payload hash
/// must agree, and the recorded distinct solvers must meet the original 2% bound.
fn solid_tip_sf(solid_dir: &str, _label: &str, g: &Genome) -> Option<(f64, String)> {
    let key=jarambit_crescent::certification::identity(g);
    let b: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(format!("{solid_dir}/bindings.json")).ok()?).ok()?;
    let e = &b[&key];
    if !jarambit_crescent::certification::bound(e,&key){return None;}
    let bound = crate::crescent::load_seeds(e["genome"].as_str()?, 1).into_iter().next()?;
    if bound != *g { return None; }
    let path = e["gci"].as_str()?.to_string();
    let bytes=std::fs::read(&path).ok()?;
    if e["gci_sha256"].as_str()!=Some(jarambit_crescent::battery::sha256_bytes(&bytes).as_str()){return None;}
    let j: serde_json::Value=serde_json::from_slice(&bytes).ok()?;
    if !jarambit_crescent::certification::bound(&j,&key) { return None; }
    if !jarambit_crescent::certification::bound(&j["solid_record"],&key) {return None;}
    let genome_sha=jarambit_crescent::battery::sha256_file(std::path::Path::new(e["genome"].as_str()?))?;
    if j["solid_record"]["genome_sha256"].as_str()!=Some(genome_sha.as_str()){return None;}
    if jarambit_crescent::certification::independent_pass(&j["solid_record"])!=Some(true){return None;}
    let sf=j["SF_nodal_max"]["fine"].as_f64()?;
    if Some(sf)!=j["solid_record"]["stored_solid"]["SF_nodal_max"].as_f64(){return None;}
    Some((sf,path))
}

/// RS-karambit-v2 evaluation of named genomes (`label=path,...`). Every hard gate of the set, including the ones
/// inherited from RS-karambit-v1 (screen: solid tip SF, twist floor body AND strict 0.0625 mm^2 tip submodel;
/// promotion: strict 0.0625 mm^2 hunter lateral), is observed or reported "unverified"; `all_hard` is true only if
/// every gate is observed and met. Errors (no genome spec, unreadable genome, failed solve, unwritable output) exit 1.
pub fn rs_v2_eval(genomes: &str, out_dir: &str, solid_dir: &str) -> bool {
    let specs: Vec<&str> = genomes.split(',').map(str::trim).filter(|s| !s.is_empty()).collect();
    if specs.is_empty() { eprintln!("rs-v2-eval: no genomes given (use --genomes label=path[,label=path...])"); return false; }
    if let Err(e) = std::fs::create_dir_all(out_dir) { eprintln!("rs-v2-eval: cannot create {out_dir}: {e}"); return false; }
    let mut ok = true; let mut n = 0;
    for spec in specs {
        let Some((label, path)) = spec.split_once('=').filter(|(l, p)| !l.is_empty() && !p.is_empty()) else { eprintln!("rs-v2-eval: bad spec '{spec}' (want label=path)"); ok = false; continue };
        let Some(g) = crate::crescent::load_seeds(path, 1).into_iter().next() else { eprintln!("rs-v2-eval: no genome in {path}"); ok = false; continue };
        let p = pheno::build(&g); let r = qd::evaluate(&g, 0, 0, 2.0);
        let Some((f, _)) = fem::certify(&p) else { eprintln!("rs-v2-eval: {label}: certification failed"); ok = false; continue };
        let m = jarambit_physics::material(g.mat);
        let strict = fem::run_unbiased(&p, 0.0625);
        if strict.is_none() { eprintln!("rs-v2-eval: {label}: strict 0.0625 mm^2 solve failed (gates reported unverified)"); }
        let strict_lat = strict.as_ref().map(|s| s.lat20 * fem::joint_k(m, g.t_joint(), 2));
        let strict_tz = strict.as_ref().map(|s| s.twist_tipzone_sf);
        let solid = solid_tip_sf(solid_dir, label, &g);
        let (bw, band) = fem::ring_bearing(&p);
        let hunter = jarambit_physics::floors::HUNTER_LATERAL_N;
        let measured=jarambit_crescent::certification::measure(&p);
        let s2=measured.point.as_ref().map(|x|(x.pass,x.t_0p25_mm,x.t_1p00_mm,x.t_2p00_mm,x.taper_lower_bound_mm,x.monotonic));
        let gates = [
            ("aesthetic_and_geometric", Some(r.aes.pass && r.rejects.is_empty())),
            ("floors_828_joint", Some(f.floors_ok)),
            ("twist_floor_body_and_tipsub_strict", strict_tz.map(|tz| fem::twist_floor_ok(f.twist_body_sf, tz))),
            ("solid_tip_sf", solid.as_ref().map(|(sf, _)| *sf >= 1.0)),
            ("strict_hunter_lateral", strict_lat.map(|l| l >= hunter)),
            ("seq_hard", Some(f.seq_ratio >= fem::SEQ_TARGET)),
            ("human_max", Some(fem::rs_v2_human_max_pass(&f, &p))),
            ("fatigue", Some(fem::rs_v2_fatigue_pass(&f))),
            // Gate S (owner 2026-10-13): S1+S3 from the grind law; S2 (sharp point) verified on the 3D B-rep when rs_v2 is active.
            ("gate_s_sharp_law", measured.sharpness.as_ref().map(|s|s.pass)),
            ("gate_s_tip_point_brep", s2.map(|x| x.0)),
        ];
        let all_hard = all_met(&gates.iter().map(|(_, v)| *v).collect::<Vec<_>>());
        let unverified: Vec<&str> = gates.iter().filter(|(_, v)| v.is_none()).map(|(k, _)| *k).collect();
        let screen = [0usize, 1, 2, 3].iter().map(|&i| gates[i].1).fold(Some(true), |a, b| match (a, b) { (Some(false), _) | (_, Some(false)) => Some(false), (None, _) | (_, None) => None, _ => Some(true) });
        let groups: serde_json::Map<String, serde_json::Value> = gates.iter().map(|(k, v)| (k.to_string(), serde_json::json!(gate(*v)))).collect();
        let mut j = serde_json::json!({"certificate_identity":jarambit_crescent::certification::identity(&g), "export_measurements":measured, "label": label, "genome": path, "requirement_set": "RS-karambit-v2", "tier": "T2 certification (fem::certify) + strict 0.0625 mm^2 + solid tip evidence",
            "mass_g": p.mass_g, "t_mm": p.t, "aes_pass": r.aes.pass, "rejects": r.rejects, "floors_ok": f.floors_ok,
            "lat_rob_n": f.lat_rob, "ring_rob_n": f.ring_rob, "twist_body_sf": f.twist_body_sf, "twist_tipzone_sf": f.twist_tipzone_sf,
            "strict_lat_rob_0p0625_n": strict_lat, "twist_tipzone_sf_strict": strict_tz,
            "solid_tip_sf": solid.as_ref().map(|s| s.0), "solid_tip_source": solid.as_ref().map(|s| s.1.clone()),
            "solid_tip_note": "content identity, exact genome, payload hash and independently measured solid record must agree; absent or mismatched = unverified",
            "seq_ratio": f.seq_ratio, "hm_twist_sf": f.hm_twist_sf, "hm_tip_inplane_sf": f.hm_tip_inplane_sf, "hm_tip_inplane_record_only": fem::HM_TIP_INPLANE_RECORD_ONLY, "hm_spine_sf": f.hm_spine_sf,
            "hm_ringback_sf": f.hm_ringback_sf, "fat_sf": f.fat_sf, "ring_bearing_w_mm": bw, "ring_band_mm": band,
            "gates": groups, "screen": gate(screen), "unverified": unverified, "all_hard": all_hard,
            "groups": {"screen_plate": screen == Some(true), "seq_hard": f.seq_ratio >= fem::SEQ_TARGET, "human_max": fem::rs_v2_human_max_pass(&f, &p),
                       "fatigue": fem::rs_v2_fatigue_pass(&f)}});
        if let Some((s2_ok, t025, t100, t200, taper_lower_bound_mm, mono)) = s2 {
            j["gate_s_point_profile"] = serde_json::json!({
                "pass": s2_ok,
                "t_0p25_mm": t025,
                "t_1p00_mm": t100,
                "t_2p00_mm": t200,
                "taper_mm": measured.point.as_ref().and_then(|p|p.taper_mm),
                "taper_lower_bound_mm": taper_lower_bound_mm,
                "monotonic": mono,
            });
        }
        let out = format!("{out_dir}/{label}.json");
        match std::fs::write(&out, serde_json::to_string_pretty(&j).unwrap() + "\n") { Ok(()) => n += 1, Err(e) => { eprintln!("rs-v2-eval: cannot write {out}: {e}"); ok = false; } }
        println!("{label}: all_hard={all_hard} unverified={unverified:?}");
    }
    if n == 0 { eprintln!("rs-v2-eval: no design evaluated"); return false; }
    ok
}

#[cfg(test)]
mod rs_v2_tests {
    use super::*;

    #[test]
    fn missing_or_failed_gate_never_passes() {
        assert!(all_met(&[Some(true), Some(true)]));
        assert!(!all_met(&[Some(true), None]), "unverified (e.g. no solid tip evidence) must not pass");
        assert!(!all_met(&[Some(true), Some(false)]), "strict / solid failure must fail");
        assert!(!all_met(&[]));
        assert_eq!(gate(None), "unverified");
        assert_eq!(gate(Some(false)), "fail");
    }

    fn repo(rel: &str) -> String { format!("{}/../../{rel}", env!("CARGO_MANIFEST_DIR")) }

    #[test]
    fn solid_evidence_bound_to_genome() {
        let g3 = crate::crescent::load_seeds(&repo("evidence/rs_v2/genomes/g3_tip+00_t60_tt3.csv"), 1).remove(0);
        let w = crate::crescent::load_seeds(&repo("evidence/rs_v2/genomes/w271b_11772_genome.csv"), 1).remove(0);
        let d = std::env::temp_dir().join(format!("rsv2_solid_{}", std::process::id()));
        std::fs::create_dir_all(&d).unwrap(); let ds = d.to_str().unwrap();
        assert!(solid_tip_sf(ds, "g3", &g3).is_none(), "no bindings -> unverified");
        let key=jarambit_crescent::certification::identity(&g3);
        let gci = d.join("g3_gci.json");
        let genome_sha=jarambit_crescent::battery::sha256_file(std::path::Path::new(&repo("evidence/rs_v2/genomes/g3_tip+00_t60_tt3.csv"))).unwrap();
        let mut proof=serde_json::json!({"certificate_identity":key,"design":"g3","SF_nodal_max":{"fine":1.6},"solid_record":{"certificate_identity":key,"genome_sha256":genome_sha,"mesh_sha256":"a".repeat(64),"stored_solid":{"NL":4,"NSUB":1,"SF_nodal_max":1.6,"SF_nodal_avg":1.7,"SF_skfem_nodal_max":1.6,"SF_skfem_nodal_avg":1.7},"dolfinx_cross_check":{"status":"verified","primary_solver":"skfem_p2","independent_solver":"dolfinx_v0.9.0","mesh_sha256":"a".repeat(64),"SF_nodal_max":1.6,"SF_nodal_avg":1.7}}});
        std::fs::write(&gci,proof.to_string()).unwrap();let sha=jarambit_crescent::battery::sha256_file(&gci).unwrap();
        let bind = serde_json::json!({key.clone(): {"certificate_identity":key,"gci_sha256":sha,"gci": gci, "genome": repo("evidence/rs_v2/genomes/g3_tip+00_t60_tt3.csv")}});
        std::fs::write(d.join("bindings.json"), bind.to_string()).unwrap();
        assert_eq!(solid_tip_sf(ds, "g3", &g3).map(|x| x.0), Some(1.6));
        assert!(solid_tip_sf(ds, "g3", &w).is_none(), "same label, different genome must be unverified");
        assert_eq!(solid_tip_sf(ds,"x",&g3).map(|x|x.0),Some(1.6),"same content may be relabeled");
        proof["solid_record"]["certificate_identity"]=serde_json::json!("another-genome-model");
        std::fs::write(&gci,proof.to_string()).unwrap();
        let mut wrong=bind.clone();wrong[&key]["gci_sha256"]=serde_json::json!(jarambit_crescent::battery::sha256_file(&gci).unwrap());
        std::fs::write(d.join("bindings.json"),wrong.to_string()).unwrap();
        assert!(solid_tip_sf(ds,"g3",&g3).is_none(),"outer keys cannot launder another solver record");
        std::fs::write(&gci,"{\"SF_nodal_max\":{\"fine\":99.0}}").unwrap();
        assert!(solid_tip_sf(ds,"g3",&g3).is_none(),"edited payload cannot retain an old content binding");
        std::fs::remove_dir_all(&d).ok();
    }

    #[test]
    fn committed_bindings_resolve() {
        let dir = repo("evidence/fem_solid/gci");
        let b: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(format!("{dir}/bindings.json")).unwrap()).unwrap();
        for (label, e) in b.as_object().unwrap().iter().filter(|(k, _)| !k.starts_with('_')) {
            let g = crate::crescent::load_seeds(&repo(e["genome"].as_str().unwrap()), 1).remove(0);
            let j: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(repo(e["gci"].as_str().unwrap())).unwrap()).unwrap();
            assert_eq!(j["design"].as_str(), Some(label.as_str()));
            assert!(g.v.iter().all(|x| x.is_finite()), "{label}: bound genome must load");
        }
    }

    #[test]
    fn empty_or_bad_specs_fail() {
        let out = std::env::temp_dir().join(format!("rsv2_out_{}", std::process::id()));
        let o = out.to_str().unwrap();
        assert!(!rs_v2_eval("", o, "evidence/fem_solid/gci"));
        assert!(!rs_v2_eval(",", o, "evidence/fem_solid/gci"));
        assert!(!rs_v2_eval("onlylabel", o, "evidence/fem_solid/gci"));
        assert!(!rs_v2_eval("x=/nonexistent/genome.csv", o, "evidence/fem_solid/gci"));
        std::fs::remove_dir_all(&out).ok();
    }
}
