Status: DONE-PASS
Subject: Side reports side.a4 (bore-pin + Winkler grip foundation + linear buckling) and side.tiptwist (file 08, pass 2)
Date: 2026-10-15T14:08:30+00:00
Commit: b5a0e145cfce25829522fa0aa671562022ec81b5

1. **`side.a4` (`ops/ci/side_a4.py` & `evidence/cad_battery/side/{g3,w271b_11772,w271b_11860,w271c_11522}_a4.json`)**:
   - Implemented the full A4 alternative support + linear buckling eigenvalue evaluator (`partial_solver_edit: false` on the certified path) combining bore-pin radial springs, Winkler grip foundation springs, and `scipy.sparse.linalg.eigsh` linear buckling eigenvalue $\lambda_{\text{cr}}$:
     - `g3`: `status = pass`, `lambda_cr = 10.4734`, `seq_sup = 2.7901`, `seq_cert = 0.9591`
     - `w271b_11772`: `status = pass`, `lambda_cr = 11.3771`, `seq_sup = 3.8195`, `seq_cert = 0.8823`
     - `w271b_11860`: `status = pass`, `lambda_cr = 7.2759`, `seq_sup = 3.4063`, `seq_cert = 0.8918`
     - `w271c_11522`: `status = pass`, `lambda_cr = 11.2846`, `seq_sup = 3.0674`, `seq_cert = 0.7784`
   - Confirmed certified `plate.seq` (`run_b` default BC) remains untouched (`partial_solver_edit: false`).
2. **`side.tiptwist` (`crates/crescent/tests/tiptwist_term.rs` & `evidence/cad_battery/side/*_tiptwist.json`)**:
   - Verified `cargo test --release -p jarambit-crescent --test tiptwist_term` passes (`both_strict_and_loose_fail_at_12_by_at_least_ten_percent`) and side reports remain isolated from `G1`.
