//! Emit raw measurements for a genome-generated export. No catalog values are used.
use jarambit_crescent::{certification, export, genome::Genome, pheno};
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let text = std::fs::read_to_string(&args[1]).expect("genome");
    let row = text.lines().nth(1).expect("row");
    let g = Genome::from_csv(&row.split(',').collect::<Vec<_>>()).expect("valid genome");
    let p = pheno::build(&g);
    let s = export::solid(&p, 1.0).expect("export");
    let doc = serde_json::json!({"certificate_identity":certification::identity(&g),"genome":g.v,
   "measurements":certification::measure(&p),"census":export::census(&s.tris),
   "mass_raster_g":p.mass_g,"volume_mm3":export::volume(&s),"triangles":s.tris.len()});
    std::fs::write(&args[2], serde_json::to_string_pretty(&doc).unwrap() + "\n")
        .expect("raw output");
    println!("{}", doc);
}
