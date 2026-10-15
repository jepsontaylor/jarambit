//! Three-mesh plate GCI probe (max_area = [0.25, 1.0, 4.0] mm^2 -> h = [0.5, 1.0, 2.0] mm, r = 2.0).
//! Usage: cargo run --release -p jarambit-crescent --example plate_gci_probe -- <genome.csv> <out_raw.json>
use jarambit_crescent::{fem, genome::Genome, geom, pheno};
use jarambit_evidence::identity::ContentRef;
use jarambit_physics::{fine, floors, material};
use std::{env, fs, process::ExitCode};

fn sha256_hex(bytes: &[u8]) -> String {
    ContentRef::from_bytes("x", "rev1", bytes).sha256
}

fn mesh_hash(xy: &[(f64, f64)], tris: &[[usize; 3]], te: &[f64]) -> String {
    let mut buf = Vec::with_capacity(xy.len() * 16 + tris.len() * 24 + te.len() * 8);
    for &(x, y) in xy {
        buf.extend_from_slice(&x.to_le_bytes());
        buf.extend_from_slice(&y.to_le_bytes());
    }
    for &[a, b, c] in tris {
        buf.extend_from_slice(&(a as u64).to_le_bytes());
        buf.extend_from_slice(&(b as u64).to_le_bytes());
        buf.extend_from_slice(&(c as u64).to_le_bytes());
    }
    for &t in te {
        buf.extend_from_slice(&t.to_le_bytes());
    }
    sha256_hex(&buf)
}

fn main() -> ExitCode {
    let mut args = env::args().skip(1);
    let Some(genome_path) = args.next() else {
        eprintln!("usage: plate_gci_probe GENOME.csv OUT_RAW.json");
        return ExitCode::from(2);
    };
    let Some(out_path) = args.next() else {
        eprintln!("usage: plate_gci_probe GENOME.csv OUT_RAW.json");
        return ExitCode::from(2);
    };
    let Ok(raw_bytes) = fs::read(&genome_path) else {
        eprintln!("cannot read {genome_path}");
        return ExitCode::from(1);
    };
    let genome_sha256 = sha256_hex(&raw_bytes);
    let txt = String::from_utf8_lossy(&raw_bytes);
    let mut lines = txt.lines();
    let Some(hdr) = lines.next() else {
        eprintln!("empty genome");
        return ExitCode::from(1);
    };
    let cols: Vec<&str> = hdr.split(',').collect();
    let Some(off) = cols.iter().position(|c| *c == "cp00") else {
        eprintln!("no cp00 column");
        return ExitCode::from(1);
    };
    let Some(row) = lines.next() else {
        eprintln!("no data row");
        return ExitCode::from(1);
    };
    let fields: Vec<&str> = row.split(',').collect();
    let Some(g) = Genome::from_csv(&fields[off.min(fields.len())..]) else {
        eprintln!("genome parse failed");
        return ExitCode::from(1);
    };
    let p = pheno::build(&g);
    let m = material(p.mat);
    let jk2 = fem::joint_k(&m, p.t_joint, 2);
    let outer = geom::dp_closed(&p.outline, 0.03);
    let holes: Vec<Vec<(f64, f64)>> = p.holes.iter().map(|h| geom::dp_closed(h, 0.02)).collect();

    let levels_spec = [(0.25f64, 0.5f64), (1.0f64, 1.0f64), (4.0f64, 2.0f64)];
    let mut levels = Vec::new();
    for (max_area, h_mm) in levels_spec {
        let Some((f, fl)) = fem::report_fields(&p, max_area) else {
            eprintln!("report_fields failed at {max_area}");
            return ExitCode::from(1);
        };
        let Some(mesh) = fine::mesh_domain(&outer, &holes, max_area) else {
            eprintln!("mesh_domain failed at {max_area}");
            return ExitCode::from(1);
        };
        let m_sha = mesh_hash(&mesh.xy, &mesh.tris, &fl.te);
        let sf_hunter = (f.lat20 * jk2) / floors::HUNTER_LATERAL_N;
        levels.push(serde_json::json!({
            "h_mm": h_mm,
            "lat20_n": f.lat20,
            "max_area_mm2": max_area,
            "mesh_sha256": m_sha,
            "n_elem": fl.tris.len(),
            "n_node": fl.xy.len(),
            "seq_ratio": f.seq_ratio,
            "sf_hunter": sf_hunter,
        }));
    }
    let out_doc = serde_json::json!({
        "genome": genome_path,
        "genome_sha256": genome_sha256,
        "levels_fine_to_coarse": levels,
    });
    if let Some(parent) = std::path::Path::new(&out_path).parent() {
        fs::create_dir_all(parent).ok();
    }
    fs::write(&out_path, serde_json::to_string_pretty(&out_doc).unwrap() + "\n").unwrap();
    ExitCode::SUCCESS
}
