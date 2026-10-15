Status: DONE-PASS
Subject: T00 frozen controls, T02 unaided fail-closed check, and xbabe3 Cargo registry cache repair (file 12, pass 2)
Date: 2026-10-15T07:57:47.501697+00:00
Commit: 9a45061449d901315494b81a07742ace1a4282cd

1. Repaired missing `/home/ubuntu/actions-runners/jarambit-xbabe3/.cargo/registry/index/index.crates.io-1949cf8c6b5b557f/config.json` (76 bytes, sha256 `5b943a2c6f7eb743f7308aba07bdbb47d9ae44aafecd832d7f15df186afbafb3`) on `xbabe3` (`192.168.68.54`) and verified offline `cargo test --release --locked -p jarambit-evidence --test assurance_contract --no-run` succeeds on `xbabe3`.
2. Executed the full `Typed evidence controls and frozen T00 inventory` step (`Ran 18 tests ... OK`, 9 T00 receipts published and verified by `ops/ci/test_inventory.py`).
3. Verified `python3 ops/ci/check_claims.py` exits with code `2` (`independent_caller_admission_unavailable`) when invoked unaided, and `Figure helper tests` (112 unit/mutant controls in `ops/ci/tests`) pass with `JARAMBIT_SCIENCE_CLAIM_UNIT_BIN` configured from `claim_report`.
