//! Export a watertight STEP + STL for one genome CSV (cp00.. header). Usage: export_step <genome.csv> <out_prefix> <label>
use jarambit_crescent::{export, genome::Genome, pheno};
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let txt = std::fs::read_to_string(&a[1]).expect("read genome");
    let mut l = txt.lines(); let h: Vec<&str> = l.next().unwrap().split(",").collect();
    let off = h.iter().position(|c| *c == "cp00").expect("cp00");
    let f: Vec<&str> = l.next().unwrap().split(",").collect();
    let g = Genome::from_csv(&f[off..]).expect("genome parse");
    let p=pheno::build(&g);
    let s = export::solid(&p, 1.0).expect("solid");
    let (once, more, dmax) = export::census(&s.tris);
    std::fs::write(format!("{}.step", a[2]), export::step(&s, &a[3])).unwrap();
    std::fs::write(format!("{}.stl", a[2]), export::stl(&s, &a[3])).unwrap();
    let mut surface=export::surface_json(&s);surface["tip"]=serde_json::json!(p.tip);surface["rs_v2"]=serde_json::json!(p.rs_v2);
    surface["certificate_identity"]=serde_json::json!(jarambit_crescent::certification::identity(&g));
    std::fs::write(format!("{}_surface.json", a[2]), serde_json::to_string(&surface).unwrap()+"\n").unwrap();
    println!("boundary {once} nonmanifold {more} dmax {dmax} volume {:.9} mm3", export::volume(&s));
}
