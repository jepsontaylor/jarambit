//! One-shot plate capacities and watertight re-export. Not a search.
use jarambit_evolve::checkpoint_best;
use jarambit_genotype::{limits, Genotype, Rng};
use jarambit_phenotype::{edge_census, Phenotype};
use jarambit_physics::{evaluate, floors, material, plate_capacities, PlateCaps};
use std::fmt::Write;
use std::path::{Path, PathBuf};

struct Row {
    name: String,
    tip: f64,
    reach: f64,
    arc: f64,
    mass_g: f64,
    gov: [f64; 3],
    ring: [f64; 3],
    ratio20: f64,
    boundary: usize,
    nonmanifold: usize,
    step_ok: bool,
    solved: bool,
}

fn plate_at(p: &Phenotype, g: &Genotype, temp: f64) -> Option<PlateCaps> {
    plate_capacities(p, material(g.material), temp, (g.serr_inner.depth, g.serr_outer.depth))
}

fn gov(c: &PlateCaps) -> f64 { c.blade_lat_n.min(c.grip_lat_n) }

fn floors_at(g: f64, ring: f64) -> bool {
    g >= floors::HIKER_LATERAL_N && g >= floors::HUNTER_LATERAL_N && ring >= floors::RING_PULL_N
}

fn blade_long_enough(tip: f64, reach: f64, arc: f64) -> bool {
    tip >= limits::BLADE_LIMIT_MM && reach >= limits::BLADE_LIMIT_MM && arc >= limits::BLADE_LIMIT_MM
}

fn survey(name: &str, g: &Genotype, export_dir: Option<&Path>) -> Row {
    let p = Phenotype::from_genotype(g);
    let temps = [-10.0, 20.0, 100.0];
    let mut caps = [None, None, None];
    for (i, t) in temps.iter().enumerate() { caps[i] = plate_at(&p, g, *t); }
    let solved = caps.iter().all(|c| c.is_some());
    let govs = [
        caps[0].as_ref().map(gov).unwrap_or(f64::NAN),
        caps[1].as_ref().map(gov).unwrap_or(f64::NAN),
        caps[2].as_ref().map(gov).unwrap_or(f64::NAN),
    ];
    let rings = [
        caps[0].as_ref().map(|c| c.ring_pull_n).unwrap_or(f64::NAN),
        caps[1].as_ref().map(|c| c.ring_pull_n).unwrap_or(f64::NAN),
        caps[2].as_ref().map(|c| c.ring_pull_n).unwrap_or(f64::NAN),
    ];
    let surr = evaluate(&p, g.edge_angle_deg, (g.serr_inner.depth, g.serr_outer.depth), material(g.material), 20.0);
    let ratio20 = govs[1] / surr.strength_n.max(1e-9);
    let mesh = p.solid_mesh();
    let (boundary, nonmanifold) = match &mesh {
        Some(m) => {
            let (once, _, more, dir_max) = edge_census(&m.tris);
            (once, more + usize::from(dir_max > 1))
        }
        None => (usize::MAX, usize::MAX),
    };
    let step = p.to_step("switchback_best");
    let step_ok = step.contains("MANIFOLD_SOLID_BREP") && step.contains("CLOSED_SHELL") && !step.contains("POLYLINE");
    if let Some(dir) = export_dir {
        let _ = std::fs::create_dir_all(dir);
        let _ = std::fs::write(dir.join("best.stl"), p.to_ascii_stl("switchback_best"));
        let _ = std::fs::write(dir.join("best.step"), step);
    }
    Row {
        name: name.into(), tip: p.blade.tip_to_heel, reach: p.blade.horizontal_reach, arc: p.blade.sharpened_arc,
        mass_g: surr.mass_g, gov: govs, ring: rings, ratio20, boundary, nonmanifold, step_ok, solved,
    }
}

fn row_export_ok(r: &Row) -> bool { r.solved && r.boundary == 0 && r.nonmanifold == 0 && r.step_ok }

fn fmt_pass(ok: bool) -> &'static str { if ok { "PASS" } else { "FAIL" } }

/// Plate smoke on mh1 checkpoints plus 20 random designs. Returns true when every
/// surveyed design solves and re-exports a watertight B-rep. Floor and blade-length
/// verdicts are written either way; they do not change this flag.
pub fn run(out: &str, mh1_root: &str) -> bool {
    let _ = std::fs::create_dir_all(out);
    let mut dirs: Vec<PathBuf> = std::fs::read_dir(mh1_root).into_iter().flatten().flatten()
        .map(|e| e.path())
        .filter(|p| p.join("checkpoint.txt").is_file())
        .collect();
    dirs.sort();
    let mut rows = Vec::new();
    for dir in &dirs {
        let name = dir.file_name().and_then(|s| s.to_str()).unwrap_or("run").to_string();
        match checkpoint_best(&dir.join("checkpoint.txt").to_string_lossy()) {
            Ok(g) => rows.push(survey(&name, &g, Some(dir))),
            Err(e) => rows.push(Row {
                name: format!("{name} ({e})"), tip: f64::NAN, reach: f64::NAN, arc: f64::NAN, mass_g: f64::NAN,
                gov: [f64::NAN; 3], ring: [f64::NAN; 3], ratio20: f64::NAN, boundary: usize::MAX, nonmanifold: usize::MAX,
                step_ok: false, solved: false,
            }),
        }
    }
    let n_win = rows.len();
    let mut rng = Rng(11);
    for i in 0..20 {
        let g = Genotype::random(&mut rng);
        let dest = Path::new(out).join(format!("random_{i:02}"));
        rows.push(survey(&format!("random_{i:02}"), &g, Some(&dest)));
    }
    let win = &rows[..n_win];
    let export_ok = !win.is_empty() && rows.iter().all(row_export_ok);
    let floors_ok = !win.is_empty() && win.iter().all(|r| r.solved && floors_at(r.gov[0], r.ring[0]) && floors_at(r.gov[1], r.ring[1]) && floors_at(r.gov[2], r.ring[2]));
    let blade_ok = win.iter().any(|r| blade_long_enough(r.tip, r.reach, r.arc));
    let mut md = String::new();
    let _ = writeln!(md, "# FEM smoke\n");
    let _ = writeln!(md, "Re-export uses the current watertight STL and faceted MANIFOLD_SOLID_BREP writer. Plate caps are one coarse Kirchhoff solve at each temperature. Floors are hiker {} N, hunter {} N, ring pull {} N. A blade is long enough only when tip-to-heel, horizontal reach, and sharpened arc are all at least {:.3} mm. The max-length reject and the gene bounds were not changed.",
        floors::HIKER_LATERAL_N, floors::HUNTER_LATERAL_N, floors::RING_PULL_N, limits::BLADE_LIMIT_MM);
    let _ = writeln!(md, "\n## Verdict\n");
    let _ = writeln!(md, "- Export (watertight STL, 0 boundary, 0 non-manifold, STEP B-rep, plate solved at -10/20/100 C): {} ({}/{} designs)", fmt_pass(export_ok), rows.iter().filter(|r| row_export_ok(r)).count(), rows.len());
    let _ = writeln!(md, "- Plate floors at all three temperatures, mh1 group winners: {} ({}/{})", fmt_pass(floors_ok), win.iter().filter(|r| r.solved && floors_at(r.gov[0], r.ring[0]) && floors_at(r.gov[1], r.ring[1]) && floors_at(r.gov[2], r.ring[2])).count(), n_win);
    let _ = writeln!(md, "- Blade length at least {:.3} mm on all three measures, mh1 group winners: {} ({}/{})", limits::BLADE_LIMIT_MM, fmt_pass(blade_ok), win.iter().filter(|r| blade_long_enough(r.tip, r.reach, r.arc)).count(), n_win);
    let _ = writeln!(md, "- Mergeable winners: {}", if floors_ok && blade_ok { "see rows" } else { "none" });
    let _ = writeln!(md, "\n## Designs\n");
    let _ = writeln!(md, "| name | mass g | plate N -10/20/100 | ring N @20 | plate/surrogate @20 | boundary | step | floors | blade mm tip/reach/arc |");
    let _ = writeln!(md, "|---|---:|---|---:|---:|---:|---|---|---|");
    for r in &rows {
        let fl = r.solved && floors_at(r.gov[0], r.ring[0]) && floors_at(r.gov[1], r.ring[1]) && floors_at(r.gov[2], r.ring[2]);
        let _ = writeln!(md, "| {} | {:.1} | {:.0}/{:.0}/{:.0} | {:.0} | {:.3} | {} | {} | {} | {:.1}/{:.1}/{:.1} |",
            r.name, r.mass_g, r.gov[0], r.gov[1], r.gov[2], r.ring[1], r.ratio20, r.boundary, fmt_pass(r.step_ok), fmt_pass(fl), r.tip, r.reach, r.arc);
    }
    let _ = writeln!(md, "\nRandom designs are seed 11, drawn in order, and are not search winners. Group rows are the max-fitness individual in each checkpoint, re-exported over `best.stl` and `best.step`.");
    let path = Path::new(out).join("summary.md");
    std::fs::write(&path, &md).unwrap_or_else(|e| panic!("write {}: {e}", path.display()));
    print!("{md}");
    export_ok
}
