use jarambit_crescent::{aesthetic, gates, genome::Genome, pheno};
use serde_json::{json, Value};
fn main() {
    let arg = std::env::args().nth(1).unwrap();
    let births: Value = serde_json::from_slice(&std::fs::read(arg).unwrap()).unwrap();
    let rows: Vec<_> = births["genomes"].as_array().unwrap().iter().enumerate().filter(|(_, b)| b["family"] == "control").map(|(i,b)| {
        let csv = b["row"].as_str().unwrap();
        let g = Genome::from_csv(&csv.split(',').collect::<Vec<_>>()).unwrap();
        let p = pheno::build(&g);
        let a = aesthetic::evaluate(&g, &p);
        json!({"birth_index": i, "aesthetic_pass": a.pass, "aesthetic_failures": a.fails, "geometry_rejects": gates::check(&g, &p)})
    }).collect();
    println!("{}", serde_json::to_string_pretty(&json!({"source_commit": "9d6416005458acafb045ab78adfb069203862eb4", "scope": "geometry/aesthetic probe only; no FEM or certification", "observations": rows})).unwrap());
}
