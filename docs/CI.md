# CI: `d1-gates` (.github/workflows/d1-gates.yml)

Runs on every pull request, on pushes to `main`, and on manual dispatch. One job on `ubuntu-latest` (45 min timeout).

1. `cargo test --release --workspace`: every unit test in all crates. That includes the crescent D1 P0/P1 tests (St-Venant alpha, chord-torsion vs couple, joint factor, genome CSV round-trip, C.6 groove) and the owner-lock tests below.
2. `cargo test --release -p jarambit-crescent d1_lock`: the D1 OWNER-LOCK gate-definition tests (`crates/crescent/src/tests.rs`):
   - screening yield 828 MPa; floors hiker 180 / hunter 260 / ring 1500 N; JOINT thin+hot factor = product.
   - blade >= 3.375 in (+0.5 mm guard) on all three measures; each measure is rejected on its own when short.
   - C.6 is the default aesthetic anchor; a ring-face groove < 2 mm fails aesthetic.
   - twist floor 1.82 N*m: body AND tip submodel, each one gates alone; seq >= 1.2; mass 74-77 g (< 80 g); full `promote_eligible` truth table.
3. D1 smoke: `jarambit crescent-d1` on the committed wave14_c03 genome, then `ops/ci/d1_smoke.py`. It requires:
   - the report header states 828 MPa, 1.82 N*m, 180/260/1500 N, blade 3.375 all three, C.6, body AND tip submodel.
   - wave14_c03 reproduces its reference verdict: C.6 PASS, gates ok, blade_min >= 3.375, PASS @828 joint (cert 280.2 / strict 269.8 N, +/- 5), twist body PASS, tip submodel < 1 so twist floor FAIL, and NOT promote-eligible.
   - every row's promote flag equals a recompute from the CSV with the locked thresholds.

CI does NOT run evolve or wave searches, and it does not certify new designs. Promotion still needs human aesthetic sign-off.
Loosening any D1 gate makes this workflow fail. Doing so is an explicit owner decision.
