//! `jarambit fem-verify` (theory checks + knife mesh convergence) and `jarambit calib`
//! (beam-surrogate / coarse-plate vs converged detailed plate). Writes CSV + markdown.
use jarambit_evolve::checkpoint_best;
use jarambit_genotype::{Genotype, Rng};
use jarambit_phenotype::Phenotype;
use jarambit_physics::{evaluate, fine, material, plate_capacities, verify};
use std::fmt::Write;

pub const LEVELS: [f64; 6] = [4.0, 2.0, 1.0, 0.5, 0.25, 0.125];

fn ser(g: &Genotype) -> (f64, f64) { (g.serr_inner.depth, g.serr_outer.depth) }

/// Richardson extrapolation from the last three levels (area halves => h ratio sqrt 2).
fn richardson(f: &[f64]) -> (f64, f64) {
    let n = f.len();
    let (f1, f2, f3) = (f[n - 3], f[n - 2], f[n - 1]);
    let (d1, d2) = (f2 - f1, f3 - f2);
    if d1.abs() < 1e-12 || d2.abs() < 1e-12 || d1.signum() != d2.signum() || d2.abs() >= d1.abs() { return (f3, f64::NAN); }
    let r = 2f64.sqrt();
    let p = (d1 / d2).ln() / r.ln();
    (f3 + d2 / (r.powf(p) - 1.0), p)
}

pub fn design_set(mh1: &str) -> Vec<(String, Genotype)> {
    let mut v = Vec::new();
    if let Ok(g) = checkpoint_best("out/smoke_legal_blade/checkpoint.txt") { v.push(("wave5_smoke_legal_blade".to_string(), g)); }
    if let Ok(rd) = std::fs::read_dir(mh1) {
        let mut dirs: Vec<_> = rd.flatten().map(|e| e.path()).filter(|p| p.join("checkpoint.txt").exists()).collect();
        dirs.sort();
        for d in dirs { if let Ok(g) = checkpoint_best(d.join("checkpoint.txt").to_str().unwrap()) { v.push((format!("mh1_{}", d.file_name().unwrap().to_string_lossy()), g)); } }
    }
    v
}

pub fn legal_randoms(n: usize, seed: u64) -> Vec<(String, Genotype)> {
    let mut r = Rng(seed);
    let mut v = Vec::new();
    let mut tries = 0usize;
    while v.len() < n && tries < 5_000_000 {
        tries += 1;
        let g = Genotype::random(&mut r);
        let p = Phenotype::from_genotype(&g);
        if jarambit_redteam::check(&g, &p).is_ok() { v.push((format!("legal_rand_{}", v.len()), g)); }
    }
    v
}

fn par_map<T: Sync, R: Send>(items: &[T], threads: usize, f: impl Fn(&T) -> R + Sync) -> Vec<R> {
    let n = items.len();
    let next = std::sync::atomic::AtomicUsize::new(0);
    let out: Vec<std::sync::Mutex<Option<R>>> = (0..n).map(|_| std::sync::Mutex::new(None)).collect();
    std::thread::scope(|s| {
        for _ in 0..threads.max(1).min(n.max(1)) {
            s.spawn(|| loop {
                let i = next.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                if i >= n { break; }
                let r = f(&items[i]);
                *out[i].lock().unwrap() = Some(r);
            });
        }
    });
    out.into_iter().map(|m| m.into_inner().unwrap().unwrap()).collect()
}

pub fn fem_verify(out: &str, mh1: &str, threads: usize) -> bool {
    std::fs::create_dir_all(out).unwrap();
    let mut md = String::from("# Detailed plate FEM verification (jarambit fem-verify)\n\nElement: numerically-built Batoz DKT (bending) + CST (membrane), spade CDT mesh (min angle 25 deg), RCM + skyline Cholesky. Bending stress is the corner value of the linear DKT curvature field; membrane peaks at holes are area-weighted nodal averages.\n\n## 1. Closed-form checks (ratio = model / theory)\n\n| check | max area mm^2 | nodes | model | theory | ratio | err % |\n|---|---|---|---|---|---|---|\n");
    let mut csv = String::from("check,max_area,nodes,model,theory,ratio\n");
    // PR-0.28.4: fail-closed theory gate against verify/expected.toml (compiled in)
    let exp = verify::parse_expected(verify::EXPECTED_TOML);
    let levels: Vec<f64> = exp.as_ref().map(|e| e.levels.clone()).unwrap_or_else(|_| LEVELS[..5].to_vec());
    let mut obs: Vec<verify::Obs> = Vec::new();
    for &a in &levels {
        let mut v: Vec<verify::Check> = Vec::new();
        if let Some(c) = verify::cantilever(a, 0.0) { v.extend(c); }
        if let Some(c) = verify::cantilever(a, 33.0) { for mut k in c { k.name = if k.name.contains("deflection") { "cantilever tip deflection (mesh rotated 33 deg)" } else { "cantilever mid-span stress (mesh rotated 33 deg)" }; v.push(k); } }
        if let Some(c) = verify::clamped_plate(a) { v.extend(c); }
        if let Some(c) = verify::curved_beam(a) { v.push(c); }
        if let Some(c) = verify::hole_kt(a) { v.push(c); }
        for c in &v {
            let err = (c.ratio() - 1.0).abs() * 100.0;
            obs.push(verify::Obs { name: c.name.to_string(), max_area: a, ratio: c.ratio() });
            let _ = writeln!(md, "| {} | {:.3} | {} | {:.5e} | {:.5e} | {:.4} | {:.2} |", c.name, a, c.nodes, c.model, c.theory, c.ratio(), err);
            let _ = writeln!(csv, "\"{}\",{},{},{:.6e},{:.6e},{:.5}", c.name, a, c.nodes, c.model, c.theory, c.ratio());
        }
    }
    let gate = match &exp { Err(e) => Err(vec![e.clone()]), Ok(e) => verify::theory_gate(e, &obs) };
    let theory_ok = gate.is_ok();
    let man = exp.as_ref().map_or("<manifest error>".to_string(), |e| format!("`verify/expected.toml` ({}, {} checks x {} levels, gate levels {:?}, < {} %)", e.id, e.checks.len(), e.levels.len(), e.gate_levels, e.max_err_pct));
    let _ = writeln!(md, "\nTheory gate (fail-closed vs {man}): **{}**\n", if theory_ok { "PASS" } else { "FAIL" });
    if let Err(why) = &gate { for w in why { let _ = writeln!(md, "- FAIL reason: {w}"); eprintln!("theory gate FAIL: {w}"); } let _ = writeln!(md); }
    std::fs::write(format!("{out}/theory_checks.csv"), csv).unwrap();

    // ---- knife mesh convergence ----
    let mut designs = design_set(mh1);
    designs.truncate(2); // wave5 + one mh1 winner
    let mut sb = jarambit_genotype::Genotype::random(&mut Rng(9));
    sb.blade_arc_len = 87.55; sb.curve_radius = 90.0; sb.blade_angle_deg = 13.0; sb.ring_wall = 4.5;
    sb.neck_flare = 0.0; sb.neck_fillet_r = 0.0; sb.clamp();
    designs.push(("switchback_ref_sharp_neck".into(), sb.clone()));
    let mut sbf = sb.clone(); sbf.neck_flare = 3.0; sbf.neck_flare_len = 18.0; sbf.neck_fillet_r = 6.0; sbf.clamp();
    designs.push(("switchback_ref_neck_fillet6_flare3".into(), sbf));
    if let Some((_, w5)) = designs.first().cloned() {
        let mut w5f = w5.clone(); w5f.neck_flare = 3.0; w5f.neck_flare_len = 18.0; w5f.neck_fillet_r = 6.0; w5f.clamp();
        designs.push(("wave5_with_neck_fillet6_flare3".into(), w5f));
    }
    let _ = writeln!(md, "## 2. Knife mesh convergence (20 C capacities, N; levels halve the max triangle area)\n\nSix levels (max triangle area 4 -> 0.125 mm^2). f_ref = mean of the two finest levels; err = |f - f_ref| / f_ref. Gate per case: every one of the 4 finest levels within 5 % of f_ref AND the search level (A = {} mm^2) within 5 %. Richardson extrapolation (h ratio sqrt 2) is shown when the three finest levels are monotone. Lateral and ring pull are floor cases and must pass; pry is reported only.\n", fine::SEARCH_AREA);
    let mut kcsv = String::from("design,case,max_area,nodes,tris,value_n,err_vs_two_finest_mean\n");
    let jobs: Vec<(usize, f64)> = (0..designs.len()).flat_map(|d| LEVELS.iter().map(move |&a| (d, a))).collect();
    let res = par_map(&jobs, threads, |&(d, a)| {
        let g = &designs[d].1;
        let p = Phenotype::from_genotype(g);
        let t0 = std::time::Instant::now();
        let c = fine::capacities(&p, material(g.material), 20.0, ser(g), a);
        (c, t0.elapsed().as_secs_f64())
    });
    let mut conv_ok = true;
    for (d, (name, g)) in designs.iter().enumerate() {
        let rows: Vec<&(Option<fine::FineCaps>, f64)> = jobs.iter().zip(&res).filter(|(j, _)| j.0 == d).map(|(_, r)| r).collect();
        if rows.iter().any(|r| r.0.is_none()) { let _ = writeln!(md, "### {name}\nmesh failed at some level\n"); conv_ok = false; continue; }
        let caps: Vec<&fine::FineCaps> = rows.iter().map(|r| r.0.as_ref().unwrap()).collect();
        let p = Phenotype::from_genotype(g);
        let _ = writeln!(md, "### {name}\n\nt = {:.1} mm, mass {:.2} g, neck flare {:.2} mm/side over {:.1} mm, fillet r {:.2} mm; blade tip-heel/reach/arc {:.1}/{:.1}/{:.1} mm\n", g.thickness, p.mass_g(material(g.material).density), g.neck_flare, g.neck_flare_len, g.neck_fillet_r, p.blade.tip_to_heel, p.blade.horizontal_reach, p.blade.sharpened_arc);
        let _ = writeln!(md, "| case | {} | f_ref (2 finest) | Richardson | max err 4 finest % | search-level err % | gate |", LEVELS.iter().map(|a| format!("A={a}")).collect::<Vec<_>>().join(" | "));
        let _ = writeln!(md, "|---|{}---|---|---|---|---|", "---|".repeat(LEVELS.len()));
        for (case, get) in [("lateral", (|c: &fine::FineCaps| c.lateral_n) as fn(&fine::FineCaps) -> f64), ("pry", |c| c.pry_n), ("ring pull", |c| c.ring_pull_n)] {
            let f: Vec<f64> = caps.iter().map(|c| get(c)).collect();
            let (ext, p_ord) = richardson(&f);
            // Unstructured remeshing makes the sequence non-monotone, so the gate uses the
            // reference f_ref = mean of the two finest levels and the band of the 4 finest levels.
            let nl = f.len();
            let fref = 0.5 * (f[nl - 1] + f[nl - 2]);
            let errs: Vec<f64> = f.iter().map(|v| (v - fref).abs() / fref * 100.0).collect();
            let band4 = errs[nl - 4..].iter().cloned().fold(0.0, f64::max);
            let si = LEVELS.iter().position(|&a| (a - fine::SEARCH_AREA).abs() < 1e-9).unwrap();
            let gate = band4 < 5.0 && errs[si] < 5.0;
            if case != "pry" && !gate { conv_ok = false; }
            let ext_s = if p_ord.is_finite() { format!("{ext:.1} (p={p_ord:.2})") } else { "n/a (non-monotone)".into() };
            let _ = writeln!(md, "| {case} | {} | {:.1} | {ext_s} | {:.2} | {:.2} | {} |", f.iter().map(|v| format!("{v:.1}")).collect::<Vec<_>>().join(" | "), fref, band4, errs[si], if gate { "PASS" } else { "FAIL" });
            for (k, c) in caps.iter().enumerate() { let _ = writeln!(kcsv, "{name},{case},{},{},{},{:.3},{:.5}", LEVELS[k], c.nodes, c.tris, f[k], errs[k] / 100.0); }
        }
        let fin = caps.last().unwrap();
        let _ = writeln!(md, "\nnodes per level: {}; solve s: {}; lateral peak at ({:.1}, {:.1}) = {}; ring-pull peak per level: {}\n",
            caps.iter().map(|c| c.nodes.to_string()).collect::<Vec<_>>().join(", "), rows.iter().map(|r| format!("{:.2}", r.1)).collect::<Vec<_>>().join(", "),
            fin.lateral_at.0, fin.lateral_at.1, fin.lateral_region,
            caps.iter().map(|c| format!("({:.1},{:.1}) {}", c.ring_at.0, c.ring_at.1, jarambit_physics::fine::region(&p, c.ring_at))).collect::<Vec<_>>().join("; "));
    }
    let _ = writeln!(md, "Knife convergence gate (lateral + ring pull on every design): **{}**\n", if conv_ok { "PASS" } else { "FAIL (see rows)" });
    std::fs::write(format!("{out}/knife_convergence.csv"), kcsv).unwrap();
    std::fs::write(format!("{out}/report.md"), md).unwrap();
    theory_ok && conv_ok
}

pub fn calib(out: &str, mh1: &str, threads: usize, n_rand: usize) {
    std::fs::create_dir_all(out).unwrap();
    let mut designs = design_set(mh1);
    let rnd = legal_randoms(n_rand, 20261011);
    for (name, g) in &rnd {
        designs.push((name.clone(), g.clone()));
        let mut l = g.clone(); l.neck_flare = 0.0; l.neck_fillet_r = 0.0; l.clamp();
        designs.push((format!("{name}_sharpneck"), l));
    }
    let res = par_map(&designs, threads, |(_, g)| {
        let p = Phenotype::from_genotype(g);
        let m = material(g.material);
        let e = evaluate(&p, g.edge_angle_deg, ser(g), m, 20.0);
        let coarse = plate_capacities(&p, m, 20.0, ser(g));
        let fs = fine::capacities(&p, m, 20.0, ser(g), fine::SEARCH_AREA);
        let fv = fine::capacities(&p, m, 20.0, ser(g), fine::VERIFY_AREA);
        (e, coarse, fs, fv, p.mass_g(m.density))
    });
    let mut csv = String::from("design,mass_g,thickness,neck_flare,neck_fillet_r,surr_lat_n,surr_ring_n,coarse_lat_n,coarse_ring_n,fine_search_lat_n,fine_search_ring_n,fine_verify_lat_n,fine_verify_ring_n,fine_verify_pry_n,lat_region,surr_over_fine_lat,coarse_over_fine_lat,search_over_verify_lat,surr_over_fine_ring,search_over_verify_ring\n");
    let mut r_sl = vec![]; let mut r_cl = vec![]; let mut r_ml = vec![]; let mut r_sr = vec![]; let mut r_mr = vec![];
    let mut r_sl_fil = vec![]; let mut r_ml_fil = vec![];
    for ((name, g), (e, c, fs, fv, mass)) in designs.iter().zip(&res) {
        let (Some(fs), Some(fv)) = (fs, fv) else { let _ = writeln!(csv, "{name},{mass:.2},{:.1},,,,,,,,,,,,mesh_fail,,,,,", g.thickness); continue; };
        let cl = c.map(|c| c.blade_lat_n.min(c.grip_lat_n)).unwrap_or(f64::NAN);
        let cr = c.map(|c| c.ring_pull_n).unwrap_or(f64::NAN);
        let sl = e.strength_n / fv.lateral_n; let ml = fs.lateral_n / fv.lateral_n;
        let sr = e.ring_pull_n / fv.ring_pull_n; let mr = fs.ring_pull_n / fv.ring_pull_n;
        r_sl.push(sl); r_ml.push(ml); r_sr.push(sr); r_mr.push(mr);
        if cl.is_finite() { r_cl.push(cl / fv.lateral_n); }
        if g.neck_fillet_r > 1.0 { r_sl_fil.push(sl); r_ml_fil.push(ml); }
        let _ = writeln!(csv, "{name},{mass:.2},{:.1},{:.2},{:.2},{:.1},{:.0},{:.1},{:.0},{:.1},{:.0},{:.1},{:.0},{:.0},{},{:.4},{:.4},{:.4},{:.4},{:.4}",
            g.thickness, g.neck_flare, g.neck_fillet_r, e.strength_n, e.ring_pull_n, cl, cr, fs.lateral_n, fs.ring_pull_n, fv.lateral_n, fv.ring_pull_n, fv.pry_n, fv.lateral_region, sl, cl / fv.lateral_n, ml, sr, mr);
    }
    std::fs::write(format!("{out}/calibration.csv"), csv).unwrap();
    let st = |v: &mut Vec<f64>| -> String {
        if v.is_empty() { return "n=0".into(); }
        v.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let q = |f: f64| v[((v.len() - 1) as f64 * f).round() as usize];
        format!("n={} min {:.3} p05 {:.3} median {:.3} p95 {:.3} max {:.3}", v.len(), v[0], q(0.05), q(0.5), q(0.95), v[v.len() - 1])
    };
    let mut md = String::from("# MC <-> FEM calibration (jarambit calib)\n\nReference = detailed plate at the verification mesh (max area ");
    let _ = write!(md, "{} mm^2, the finest converged level in `out/fem_verify/report.md`). 20 C. Lateral = governing tip-lateral capacity (the 180/260 N floor case); ring = ring-pull capacity.\n\n", fine::VERIFY_AREA);
    let _ = writeln!(md, "| ratio | stats |\n|---|---|");
    let _ = writeln!(md, "| beam surrogate / detailed plate, lateral (MC overstatement) | {} |", st(&mut r_sl));
    let _ = writeln!(md, "| beam surrogate / detailed plate, lateral, filleted necks (r > 1 mm) | {} |", st(&mut r_sl_fil));
    let _ = writeln!(md, "| coarse plate (fem.rs) / detailed plate, lateral | {} |", st(&mut r_cl));
    let _ = writeln!(md, "| search mesh / verify mesh, lateral (mesh bias in the loop) | {} |", st(&mut r_ml));
    let _ = writeln!(md, "| search mesh / verify mesh, lateral, filleted necks | {} |", st(&mut r_ml_fil));
    let _ = writeln!(md, "| beam surrogate / detailed plate, ring pull | {} |", st(&mut r_sr));
    let _ = writeln!(md, "| search mesh / verify mesh, ring pull | {} |", st(&mut r_mr));
    let _ = writeln!(md, "\nDesigns: wave5 winner, mh1 group winners (pre-blade-fix, legacy sharp neck), {} red-team-legal random genomes, each also with its neck genes zeroed (sharp corner). Per-design rows: `calibration.csv`.", rnd.len());
    std::fs::write(format!("{out}/calibration.md"), md.clone()).unwrap();
    println!("{md}");
}

/// Re-check a calibrated search front on the VERIFY mesh at -10/20/100 C and export each member.
/// Writes `{out}/calibrated_pareto.csv`, `{out}/calibrated_pareto.md`, `{out}/pareto/*`.
pub fn verify_front(out: &str, front: &[jarambit_evolve::Indiv], threads: usize) -> usize {
    use jarambit_genotype::limits;
    use jarambit_physics::floors;
    let dir = format!("{out}/pareto");
    std::fs::create_dir_all(&dir).unwrap();
    let mut fr: Vec<&jarambit_evolve::Indiv> = front.iter().filter(|i| i.feasible()).collect();
    fr.sort_by(|a, b| a.mass_g.partial_cmp(&b.mass_g).unwrap());
    fr.truncate(40);
    let caps = par_map(&fr, threads, |ind| {
        let p = Phenotype::from_genotype(&ind.g);
        fine::capacities(&p, material(ind.g.material), 20.0, ser(&ind.g), fine::VERIFY_AREA)
    });
    let mut csv = String::from("rank,legal,stl,step,svg,mass_g,spg_search_robust,spg_verify_100C,thickness_mm,material,tip_to_heel_mm,horizontal_reach_mm,sharpened_arc_mm,tip_to_heel_in,horizontal_reach_in,sharpened_arc_in,lat_n_m10C,lat_n_20C,lat_n_100C,ring_n_100C,pry_n_100C,sf_hiker_100C,sf_hunter_100C,sf_ring_100C,sf_min_100C,lat_peak_region,neck_flare_mm,neck_flare_len_mm,neck_fillet_r_mm,grip_mm,search_robust_lat_n\n");
    let mut md = String::from("# Calibrated Pareto (detailed-plate verification)\n\nSearch fitness: detailed plate at 2 mm^2 / mesh bias 1.070, times MC p05/nominal, min with 100 C nominal; floors 180/260/1500 N hard. Verification: detailed plate at 0.25 mm^2 (converged), no knock-down, yield at -10/20/100 C. SF = capacity / floor. LEGAL = red-team clean (blade >= 3.375 in on all three + every gate) AND search-robust floors AND verify-mesh floors at 100 C.\n\n| rank | legal | mass g | SPG robust N/g | SPG verify 100C N/g | t mm | tip-heel / reach / arc mm (in) | lateral -10/20/100 C N | ring 100C N | SF hiker / hunter / ring @100C | peak | neck flare/len/fillet mm | files |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n");
    let mut n_legal = 0;
    for (k, (ind, c)) in fr.iter().zip(&caps).enumerate() {
        let g = &ind.g;
        let p = Phenotype::from_genotype(g);
        let m = material(g.material);
        let rt = jarambit_redteam::check(g, &p);
        let base = format!("{dir}/rank{:02}_m{:.1}g", k, ind.mass_g);
        std::fs::write(format!("{base}.stl"), p.to_ascii_stl("switchback_calibrated")).unwrap();
        std::fs::write(format!("{base}.step"), p.to_step("switchback_calibrated")).unwrap();
        std::fs::write(format!("{base}.svg"), p.to_svg()).unwrap();
        let b = &p.blade;
        let Some(c) = c else { let _ = writeln!(csv, "{k},false,{base}.stl,{base}.step,{base}.svg,{:.2},{:.3},,,,,,,,,,,,,,,,,,,mesh_fail,,,,,", ind.mass_g, ind.fit); continue; };
        let cm = fine::at_temp(c, m, 20.0, -10.0);
        let ch = fine::at_temp(c, m, 20.0, 100.0);
        let sfh = ch.lateral_n / floors::HIKER_LATERAL_N;
        let sfu = ch.lateral_n / floors::HUNTER_LATERAL_N;
        let sfr = ch.ring_pull_n / floors::RING_PULL_N;
        let blade_ok = b.tip_to_heel >= limits::BLADE_LIMIT_MM && b.horizontal_reach >= limits::BLADE_LIMIT_MM && b.sharpened_arc >= limits::BLADE_LIMIT_MM;
        let legal = rt.is_ok() && blade_ok && ind.floors_ok && sfu >= 1.0 && sfh >= 1.0 && sfr >= 1.0;
        if legal { n_legal += 1; }
        let inch = |v: f64| v / 25.4;
        let _ = writeln!(csv, "{k},{legal},{base}.stl,{base}.step,{base}.svg,{:.2},{:.3},{:.3},{:.1},{},{:.2},{:.2},{:.2},{:.3},{:.3},{:.3},{:.1},{:.1},{:.1},{:.0},{:.0},{:.3},{:.3},{:.3},{:.3},{},{:.2},{:.2},{:.2},{:.2},{:.1}",
            ind.mass_g, ind.fit, ch.lateral_n / ind.mass_g, g.thickness, g.material.name(), b.tip_to_heel, b.horizontal_reach, b.sharpened_arc, inch(b.tip_to_heel), inch(b.horizontal_reach), inch(b.sharpened_arc),
            cm.lateral_n, c.lateral_n, ch.lateral_n, ch.ring_pull_n, ch.pry_n, sfh, sfu, sfr, sfh.min(sfu).min(sfr), c.lateral_region, g.neck_flare, g.neck_flare_len, g.neck_fillet_r, p.grip_len, ind.strength_n);
        let _ = writeln!(md, "| {k} | {} | {:.2} | {:.3} | {:.3} | {:.1} | {:.1} / {:.1} / {:.1} ({:.3} / {:.3} / {:.3}) | {:.0} / {:.0} / {:.0} | {:.0} | {:.2} / {:.2} / {:.2} | {} | {:.1} / {:.1} / {:.1} | `{base}.stl` `.step` `.svg` |",
            if legal { "LEGAL" } else { "no" }, ind.mass_g, ind.fit, ch.lateral_n / ind.mass_g, g.thickness, b.tip_to_heel, b.horizontal_reach, b.sharpened_arc, inch(b.tip_to_heel), inch(b.horizontal_reach), inch(b.sharpened_arc),
            cm.lateral_n, c.lateral_n, ch.lateral_n, ch.ring_pull_n, sfh, sfu, sfr, c.lateral_region, g.neck_flare, g.neck_flare_len, g.neck_fillet_r);
    }
    let _ = writeln!(md, "\n{} of {} front members LEGAL on the verification mesh.", n_legal, fr.len());
    std::fs::write(format!("{out}/calibrated_pareto.csv"), csv).unwrap();
    std::fs::write(format!("{out}/calibrated_pareto.md"), md).unwrap();
    n_legal
}
