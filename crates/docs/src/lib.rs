//! Docs crate: emits run reports/tables for docs/WHITEPAPER.md.
pub fn results_table(rows: &[(usize, f64)]) -> String {
    let mut s = String::from("| gen | best p05 fitness |\n|---|---|\n");
    for (g, f) in rows { s.push_str(&format!("| {g} | {f:.4} |\n")); }
    s
}
