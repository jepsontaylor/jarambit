Status: BLOCKED
Subject: T00 existing publication reconciled; T02 independent runtime unavailable
Date: 2026-10-15T07:01:14.506848+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/T00-attribution.json](evidence/T00-attribution.json), SHA-256 `127c4340746e931b0d38003d205c6b752e8cf156c3cab1625132b3a801c7a01a`
- [evidence/claims-admission-disposition.json](evidence/claims-admission-disposition.json), SHA-256 `7fbd4b073757f5ea38cf1d0de70e45f5280e775e23d567536b0fce6ff9aef92f`
- [evidence/worktree-inventory.json](evidence/worktree-inventory.json), SHA-256 `2d671156d63f3f1107028805e857ebeeed235c2dfeb3be2f7bb31549bc051018`
- [evidence/source-files/assurance/testing/tests/test_contracts.py](evidence/source-files/assurance/testing/tests/test_contracts.py), SHA-256 `ae6d704882685587d37a7f97a59f11adff870151ee8ce821a23a1ea88c1e912a`

Numbers: all 11 T00 case implementations, paired historical receipts and current CI method references are retained. Root publication24 adjudication supports those exact generic groups on b35; no duplicate run or new group credit is claimed. Existing CI 38685211443 ran the required Rust fixture build, Python wire-parity method and frozen inventory step. Its actual checkout is 9e9a2d4c4af5b3ec7f91468a82de6808754420a4; the later root tree binding resolves equivalence to b35, rather than treating the API head as the execution checkout. The 16-pair historical wire record is retained separately. No standalone current CI binary hash artifact was captured; that evidence limitation is preserved, not filled from a different build. No current wire build/inventory rerun occurred in an unowned checkout.

T02: all 12 rows remain not_run. Expected unaided exit is 2 with `independent_caller_admission_unavailable`, also recorded in the historical battery. The requested fresh unaided invocation is itself BLOCKED: there is no allowed clean owned reference. Fresh exit is null, not an invented 2. No TrustedCaller, lab admission or measured zero was fabricated. R125 history-prefix acceptance/refusal oracles stay unchanged. No assurance source changed, so no source closure or T00 pin was moved.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.

Missing input / resume condition: For the unaided recheck, an allowed clean reference. For actual T02, genuine independent B/C/D caller admission and exact-source receipts. The unaided exit-2 check alone never executes T02. Preserve release-v1 and all accepted generic evidence.
