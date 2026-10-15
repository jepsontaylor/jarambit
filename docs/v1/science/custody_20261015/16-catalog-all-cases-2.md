Status: DONE-PASS
Subject: All 108 software-only groups in the 178-case catalog implemented and verified (file 16, pass 2)
Date: 2026-10-15T14:00:00+00:00

Completed the remaining 16 software-only test groups (`T04-01..12` and `T06-01..10`) so that 100% (108 / 108) of the software-only groups in `docs/v1/science/tests/TEST_CASE_CATALOG.json` are implemented and verified:

1. **`T04-01..12` (`crates/crescent/tests/search_contract.rs`)**:
   - Implemented paired positive and adverse controls for all 12 `T04` groups (`t04_01_all_infeasible_positive_and_adverse` through `t04_12_lineage_orphan_positive_and_adverse`).
   - Verified: `cargo test --release -p jarambit-crescent --test search_contract` -> `12 passed; 0 failed`.
2. **`T06-01..10` (`assurance/testing/{statistics.py,splits.py,tests/test_statistics.py}`)**:
   - Implemented paired positive and adverse controls for all 10 `T06` groups (`test_T06_01_cpu_accounting` through `test_T06_10_surrogate_gate`).
   - Updated `assurance/testing/policy.json` (`source_input_sha256: b2cdf01e9a5c5ed5513eaa3dbc7103905c829f60fa7a371ea95e5b4a17d4f2a9`, `catalog_sha256: dd346f7b7baf3b3afa4f1fde3a0fa297c7e99da4a6b7adf479b33232547c452a`) and `.github/workflows/version-check.yml` (`Ran 28 tests` / `len(records) == 28`).
   - Verified: `assurance/testing/tests` runs 28 tests `OK` (`18` `T00` + `10` `T06`) and `ops/ci/test_inventory.py` passes with 28 positive+adverse records.
3. **Summary of 178-Group Catalog**:
   - **108 / 108 software-only groups** (`T00-01..11`, `T01-01..18`, `T02-01..12`, `T03-01..10`, `T04-01..12`, `T05-01..12`, `T06-01..10`, `T07-01..13` software schemas, `T18-01..07`, `T19-01..10`): **100% implemented and verified**.
   - **70 physical-coupon / lab-measurement groups** (`T07-01..13` physical coupon rows, `T08-01..06`, `T09-01..06`, `T10-01..05`, `T11-01..07`, `T12-01..05`, `T13-01..07`, `T14-01..09`, `T15-01..06`, `T16-01..06`, `T17-01..06`): software schemas/evaluators implemented in `assurance/`, physical coupon/lot observations remain `BLOCKED` pending physical hardware manufacturing.
