//! `jarambit crescent-smoke`: first aesthetic + novelty smoke run of the C.4-anchored crescent
//! genotype (crates/crescent). Writes history / all-evals / QD archive CSVs, plate JSON for
//! aesthetic-passing designs only, watertight STL + faceted STEP of the top design, report.md.
use jarambit_crescent::{aesthetic, export, fem, gates, genome::*, pheno, qd};
use std::fmt::Write as _;

fn jarr(v: &[(f64, f64)]) -> String { let s: Vec<String> = v.iter().map(|q| format!("[{:.3},{:.3}]", q.0, q.1)).collect(); format!("[{}]", s.join(",")) }
fn jnum(v: &[f64]) -> String { let s: Vec<String> = v.iter().map(|x| if x.is_finite() { format!("{x:.4}") } else { "null".into() }).collect(); format!("[{}]", s.join(",")) }

pub fn rec_metrics(r: &qd::Rec) -> String {
    let f = r.fem.clone().unwrap_or_default();
    format!("{{\"id\":{},\"gen\":{},\"fit\":{:.5},\"spg\":{:.5},\"mass_g\":{:.3},\"blank_g\":{:.3},\"t\":{:.1},\"material\":\"{}\",\"tip_to_heel\":{:.3},\"horizontal_reach\":{:.3},\"arc_in\":{:.3},\"arc_sp\":{:.3},\"grip\":{:.2},\"aes_score\":{:.4},\"aes_pass\":{},\"hausdorff\":{:.3},\"emd\":{:.4},\"straight_mm\":{:.2},\"min_blend_r\":{:.2},\"novelty\":{:.4},\"lat20\":{:.1},\"lat_rob\":{:.1},\"ring20\":{:.1},\"ring_rob\":{:.1},\"pry20\":{:.1},\"twist20_nmm\":{:.1},\"sf_hiker\":{:.3},\"sf_hunter\":{:.3},\"sf_ring\":{:.3},\"floors_ok\":{},\"lat_at\":[{:.2},{:.2}],\"holder_box\":[{:.1},{:.1},{:.1}],\"removed_mm3\":{},\"min_web\":{:.2},\"rejects\":{:?},\"aes_fails\":{:?},\"legal\":{}}}",
        r.id, r.gen, r.fit, r.spg, r.mass_g, r.blank_g, r.t, r.g.mat.name(), r.blade.tip_to_heel, r.blade.horizontal_reach, r.blade.arc_in, r.blade.arc_sp, r.grip,
        r.aes.score, r.aes.pass, r.aes.hausdorff, r.aes.emd, r.aes.straight_mm, r.aes.min_concave_r, r.novelty, f.lat20, f.lat_rob, f.ring20, f.ring_rob, f.pry20, f.twist20_nmm,
        f.sf_hiker, f.sf_hunter, f.sf_ring, f.floors_ok, f.lat_at.0, f.lat_at.1, r.holder_lw.0, r.holder_lw.1, r.holder_lw.2, jnum(&r.removed), r.min_web, r.rejects, r.aes.fails, r.legal())
}

fn plate_json(r: &qd::Rec, label: &str, cert: Option<(fem::Fem, fem::Fields)>) -> Option<String> {
    let p = pheno::build(&r.g);
    let (fm, fl) = match cert { Some(c) => c, None => fem::certify(&p)? };
    let fd = &p.field; let step = 2usize; // 0.5 mm thickness raster for the figure
    let mut th = Vec::new();
    for j in (0..fd.ny).step_by(step) { for i in (0..fd.nx).step_by(step) { th.push(fd.th[j * fd.nx + i] as f64); } }
    let tris: Vec<String> = fl.tris.iter().map(|t| format!("[{},{},{}]", t[0], t[1], t[2])).collect();
    let mut rr = r.clone(); rr.spg = fm.lat_rob / rr.mass_g; rr.fem = Some(fm.clone()); rr.fit = qd::fitness(&rr);
    Some(format!("{{\"label\":\"{label}\",\"metrics\":{},\"fine_area\":\"certified min(0.25, 0.125)\",\"outline\":{},\"holes\":[{}],\"hole_names\":{:?},\"pad\":{},\"c4\":{},\"field\":{{\"x0\":{},\"y0\":{},\"g\":{},\"nx\":{},\"ny\":{},\"th\":{}}},\"mesh\":{{\"xy\":{},\"tris\":[{}],\"te\":{},\"env_vm\":{},\"sf\":{},\"lat\":{},\"pry\":{},\"ring\":{},\"twist\":{}}},\"genome_header\":\"{}\",\"genome\":\"{}\"}}",
        rec_metrics(&rr), jarr(&p.outline), p.holes.iter().map(|h| jarr(h)).collect::<Vec<_>>().join(","), p.hole_names, jarr(&p.pad), jarr(&jarambit_crescent::c4_ref::EXTERIOR),
        fd.x0, fd.y0, fd.g * step as f64, (fd.nx + step - 1) / step, (fd.ny + step - 1) / step, jnum(&th),
        jarr(&fl.xy), tris.join(","), jnum(&fl.te), jnum(&fl.env_vm), jnum(&fl.sf), jnum(&fl.lat), jnum(&fl.pry), jnum(&fl.ring), jnum(&fl.twist), Genome::csv_header(), r.g.csv_row()))
}

pub fn smoke(out: &str, pop: usize, gens: usize, threads: usize, seed: u64, t_seed: f64, fem_area: f64, plate_area: f64) -> bool {
    std::fs::create_dir_all(out).unwrap();
    let mut rep = String::new();
    let _ = writeln!(rep, "# Crescent smoke (C.4-anchored aesthetic genotype) — author Jepson Taylor\n\npop {pop} gens {gens} threads {threads} seed {seed} seed-stock {t_seed} mm, FEM search area {fem_area} mm^2, plates/winners certified at min(0.25, 0.125) mm^2 (plate-area arg {plate_area} unused), T_MAX {:.1}\n", t_max());
    // ---- probe the C.4 seed ----
    let sg = Genome::c4_seed(t_seed); let sp = pheno::build(&sg);
    let sa = aesthetic::evaluate(&sg, &sp); let sr = gates::check(&sg, &sp);
    let sf = fem::run(&sp, fem_area, false).map(|x| x.0);
    let _ = writeln!(rep, "## C.4 seed at {t_seed} mm\nmass {:.2} g (blank {:.2} g), blade {:?}, grip {:.2}\naesthetic {:?}\ngates {:?}\nFEM {:?}\nholder box {:?}\n", sp.mass_g, sp.blank_g, sp.blade, sp.grip_len, sa, sr, sf, gates::holder_fit(&sp.outline));
    eprintln!("seed: mass {:.1} g, aes pass {}, rejects {:?}, fem {:?}", sp.mass_g, sa.pass, sr, sf);
    let cfg = qd::RunCfg { pop, gens, threads, seed, fem_area, t_seed };
    let t0 = std::time::Instant::now();
    let ro = qd::run(&cfg, |l| eprintln!("gen {l}  ({:.0}s)", t0.elapsed().as_secs_f64()));
    std::fs::write(format!("{out}/history.csv"), ro.history.join("\n") + "\n").unwrap();
    let mut all = String::from("[\n"); let mut csv = format!("id,gen,fit,spg,mass_g,aes_pass,aes_score,hausdorff,emd,novelty,lat_rob,ring_rob,sf_hunter,legal,n_rejects,{}\n", Genome::csv_header());
    for (i, r) in ro.all.iter().enumerate() {
        let f = r.fem.clone().unwrap_or_default();
        let _ = writeln!(csv, "{},{},{:.4},{:.4},{:.2},{},{:.4},{:.3},{:.4},{:.4},{:.1},{:.1},{:.3},{},{},{}", r.id, r.gen, r.fit, r.spg, r.mass_g, r.aes.pass, r.aes.score, r.aes.hausdorff, r.aes.emd, r.novelty, f.lat_rob, f.ring_rob, f.sf_hunter, r.legal(), r.rejects.len(), r.g.csv_row());
        all.push_str(&rec_metrics(r)); all.push_str(if i + 1 < ro.all.len() { ",\n" } else { "\n" });
    }
    all.push(']'); std::fs::write(format!("{out}/all_evals.json"), all).unwrap(); std::fs::write(format!("{out}/all_evals.csv"), csv).unwrap();
    let mut ac = String::from("cell_relief,cell_hausdorff,id,gen,fit,spg,mass_g,aes_score,novelty,sf_hunter\n");
    for ((a, b), r) in &ro.archive { let _ = writeln!(ac, "{a},{b},{},{},{:.4},{:.4},{:.2},{:.4},{:.4},{:.3}", r.id, r.gen, r.fit, r.spg, r.mass_g, r.aes.score, r.novelty, r.fem.as_ref().map_or(0.0, |f| f.sf_hunter)); }
    std::fs::write(format!("{out}/qd_archive.csv"), ac).unwrap();
    // ---- reject census ----
    let mut cnt: std::collections::BTreeMap<String, usize> = std::collections::BTreeMap::new();
    for r in &ro.all { for x in r.aes.fails.iter().chain(r.rejects.iter()) { let k: String = x.split(|c: char| c.is_ascii_digit() || c == '(').next().unwrap_or("").trim().to_string(); *cnt.entry(k).or_default() += 1; } }
    let n_all = ro.all.len(); let n_aes = ro.all.iter().filter(|r| r.aes.pass).count(); let n_gate = ro.all.iter().filter(|r| r.aes.pass && r.rejects.is_empty()).count(); let n_leg = ro.all.iter().filter(|r| r.legal()).count();
    let _ = writeln!(rep, "## Census\nevaluations {n_all}; aesthetic passers {n_aes}; aesthetic + all hard gates {n_gate}; LEGAL (also floors 180/260/1500 robust) {n_leg}\n\nreject reasons (count):");
    for (k, v) in &cnt { let _ = writeln!(rep, "- {k}: {v}"); }
    // ---- pick plate designs: aesthetic passers only ----
    let mut cand: Vec<&qd::Rec> = ro.all.iter().filter(|r| r.aes.pass && r.rejects.is_empty() && r.fem.is_some()).collect();
    cand.sort_by(|a, b| { let ka = (a.legal(), a.fit); let kb = (b.legal(), b.fit); kb.partial_cmp(&ka).unwrap() });
    // certify in search-fitness order; a design is plated only if it is still LEGAL at the
    // converged reference levels (min over 0.25 / 0.125 mm^2, no bias). SPG / fitness re-derived.
    let mut picked: Vec<qd::Rec> = Vec::new(); let mut cells = std::collections::HashSet::new();
    let mut certs = Vec::new(); let (mut n_try, mut n_fail) = (0usize, 0usize);
    for r in &cand { if picked.len() >= 3 || n_try >= 40 { break; }
        if picked.iter().any(|p| p.g == r.g) { continue; }
        let cell = qd::qd_cell(r); if cells.contains(&cell) && cand.len() >= 6 { continue; }
        n_try += 1;
        let p = pheno::build(&r.g);
        let Some((cf, fl)) = fem::certify(&p) else { n_fail += 1; continue; };
        if r.legal() && !cf.floors_ok { n_fail += 1; let _ = writeln!(rep, "- certification FAIL id {} (search lat_rob {:.0} -> certified {:.0} N, ring {:.0})", r.id, r.fem.as_ref().unwrap().lat_rob, cf.lat_rob, cf.ring_rob); continue; }
        let mut rr = (*r).clone(); rr.spg = cf.lat_rob / rr.mass_g; rr.fem = Some(cf.clone()); rr.fit = qd::fitness(&rr);
        cells.insert(cell); certs.push((cf, fl)); picked.push(rr);
    }
    let _ = writeln!(rep, "\n## Certification\ncandidates certified {n_try}, rejected at the converged mesh {n_fail}\n\n## Plate designs (aesthetic passers only; certified metrics)");
    let mut plates = Vec::new();
    for (k, (r, c)) in picked.iter().zip(certs.into_iter()).enumerate() {
        let label = format!("crescent_smoke_{}", ["top", "qd2", "qd3"][k]);
        if let Some(j) = plate_json(r, &label, Some(c)) { std::fs::write(format!("{out}/{label}.json"), &j).unwrap(); plates.push(label.clone()); }
        let _ = writeln!(rep, "- {label}: {}", rec_metrics(r));
    }
    // seed reference plate (aesthetic passer by construction) for comparison
    let seed_rec = qd::evaluate(&sg, usize::MAX, 0, fem_area);
    if seed_rec.aes.pass { if let Some(j) = plate_json(&seed_rec, "crescent_c4_seed", None) { std::fs::write(format!("{out}/crescent_c4_seed.json"), j).unwrap(); plates.push("crescent_c4_seed".into()); } }
    // ---- watertight STL + faceted STEP of the top design ----
    if let Some(r) = picked.first() {
        let p = pheno::build(&r.g);
        if let Some(s) = export::solid(&p, 1.0) {
            let (once, more, dmax) = export::census(&s.tris); let v = export::volume(&s);
            std::fs::write(format!("{out}/best.stl"), export::stl(&s, "jarambit_crescent_best")).unwrap();
            std::fs::write(format!("{out}/best.step"), export::step(&s, "jarambit_crescent_best")).unwrap();
            let _ = writeln!(rep, "\n## Export (top design)\nwatertight: boundary edges {once}, non-manifold {more}, max directed-edge repeat {dmax} => {}; solid volume {v:.0} mm^3 = {:.2} g (raster {:.2} g); faces {}", if once == 0 && more == 0 && dmax == 1 { "WATERTIGHT" } else { "NOT WATERTIGHT" }, v * jarambit_physics::material(r.g.mat).density / 1000.0, r.mass_g, s.tris.len());
        }
        std::fs::write(format!("{out}/best_genome.csv"), format!("{}\n{}\n", Genome::csv_header(), r.g.csv_row())).unwrap();
    }
    let _ = writeln!(rep, "\nplates: {:?}\nwall time {:.0} s", plates, t0.elapsed().as_secs_f64());
    std::fs::write(format!("{out}/report.md"), rep).unwrap();
    std::fs::write(format!("{out}/plates.txt"), plates.join("\n") + "\n").unwrap();
    true
}

/// Quick probe: seed gates / aesthetic / FEM at several stocks and tip-reinforcement variants (no GA).
pub fn probe(fem_area: f64) {
    let mut vars: Vec<(String, Genome)> = [5.3, 5.7, 6.0].iter().map(|&t| (format!("seed t{t}"), Genome::c4_seed(t))).collect();
    let mut v = Genome::c4_seed(5.7); v.v[EA_IN] = 22.0; v.v[EA_SP] = 22.0; v.v[EDGE_TH] = 0.9; v.v[T_TIP] = 4.5; vars.push(("ea22 edge0.9 tip4.5".into(), v.clone()));
    for i in [1usize, 2, 3] { v.v[i] = 3.0; } for i in [36usize, 37, 38] { v.v[i] = 2.5; } v.clamp(); vars.push(("+fat tip offsets".into(), v.clone()));
    for (name, g) in vars {
        let t = name.clone(); let p = pheno::build(&g);
        let a = aesthetic::evaluate(&g, &p); let r = gates::check(&g, &p);
        let f = fem::run(&p, fem_area, false).map(|x| x.0);
        println!("t {t}: mass {:.2} blank {:.2} aes {:.3} pass {} H {:.2} rejects {:?}\n  fem {:?}\n  holder {:?} land {:.0} minweb {:.2}", p.mass_g, p.blank_g, a.score, a.pass, a.hausdorff, r, f, gates::holder_fit(&p.outline), p.land_full_mm2, p.min_web);
    }
}

/// Crescent mesh-convergence calibration: detailed plate at the search area vs finer levels on
/// aesthetic passers sampled from a smoke run (all_evals.csv). Ground edges and the hawkbill tip
/// make the crescent more mesh-sensitive than the flat jarambit plate, so it carries its own bias.
pub fn conv(evals_csv: &str, n: usize, threads: usize, out: &str) -> bool {
    let txt = match std::fs::read_to_string(evals_csv) { Ok(t) => t, Err(e) => { eprintln!("{evals_csv}: {e}"); return false; } };
    let mut gs: Vec<(String, Genome)> = vec![("c4_seed".into(), Genome::c4_seed(5.7))];
    let rows: Vec<Vec<&str>> = txt.lines().skip(1).map(|l| l.split(',').collect()).filter(|f: &Vec<&str>| f.len() > 15 && f[5] == "true").collect();
    // legal first (highest fitness), then a stride through the remaining aesthetic passers
    let mut legal: Vec<&Vec<&str>> = rows.iter().filter(|f| f[13] == "true").collect();
    legal.sort_by(|a, b| b[2].parse::<f64>().unwrap_or(-9.0).partial_cmp(&a[2].parse::<f64>().unwrap_or(-9.0)).unwrap());
    let mut seen = std::collections::HashSet::new();
    let mut add = |gs: &mut Vec<(String, Genome)>, f: &Vec<&str>| { if seen.insert(f[15..].join(",")) { if let Some(g) = Genome::from_csv(&f[15..]) { gs.push((format!("id{}", f[0]), g)); } } };
    for f in legal.iter() { if gs.len() > n / 2 { break; } add(&mut gs, f); }
    let stride = (rows.len() / (n - n / 2).max(1)).max(1);
    for f in rows.iter().step_by(stride) { if gs.len() > n { break; } add(&mut gs, f); }
    const LV: [f64; 5] = [2.0, 1.0, 0.5, 0.25, 0.125];
    let res: Vec<(String, Vec<Option<fem::Fem>>)> = std::thread::scope(|s| {
        let chunks: Vec<_> = gs.chunks(gs.len().div_ceil(threads.max(1))).map(|c| s.spawn(move || c.iter().map(|(k, g)| {
            let p = pheno::build(g); (k.clone(), LV.iter().map(|&a| fem::run(&p, a, false).map(|x| x.0)).collect::<Vec<_>>()) }).collect::<Vec<_>>())).collect();
        chunks.into_iter().flat_map(|h| h.join().unwrap()).collect()
    });
    let mut md = format!("# Crescent mesh convergence (detailed plate, 20 C, per-element thickness)\n\nlevels (max triangle area, mm^2): {LV:?}; reference = 0.125 mm^2. ratio = capacity(level) / capacity(0.125).\n\n| design | lat20 @2 | @1 | @0.5 | @0.25 | @0.125 | lat ratio 2/ref | 0.25/ref | ring ratio 2/ref | 0.25/ref | lat_at @ref |\n|---|---|---|---|---|---|---|---|---|---|---|\n");
    let (mut lmax, mut rmax, mut lv, mut rv) = (0.0f64, 0.0f64, 0.0f64, 0.0f64);
    for (k, v) in &res {
        if v.iter().any(|x| x.is_none()) { let _ = writeln!(md, "| {k} | mesh failed | | | | | | | | | |"); continue; }
        let f: Vec<&fem::Fem> = v.iter().map(|x| x.as_ref().unwrap()).collect(); let r = f[4];
        let (l2, l25, r2, r25) = (f[0].lat20 / r.lat20, f[3].lat20 / r.lat20, f[0].ring20 / r.ring20, f[3].ring20 / r.ring20);
        lmax = lmax.max(l2); rmax = rmax.max(r2); lv = lv.max(l25); rv = rv.max(r25);
        let _ = writeln!(md, "| {k} | {:.1} | {:.1} | {:.1} | {:.1} | {:.1} | {l2:.3} | {l25:.3} | {r2:.3} | {r25:.3} | ({:.1}, {:.1}) |", f[0].lat20, f[1].lat20, f[2].lat20, f[3].lat20, r.lat20, r.lat_at.0, r.lat_at.1);
    }
    let _ = writeln!(md, "\nMAX search(2.0)/ref: lateral {lmax:.3}, ring {rmax:.3}. MAX 0.25/ref: lateral {lv:.3}, ring {rv:.3}.");
    println!("{md}");
    std::fs::create_dir_all(out).ok(); std::fs::write(format!("{out}/convergence.md"), md).is_ok()
}
