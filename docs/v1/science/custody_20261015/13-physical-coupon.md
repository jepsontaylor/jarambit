Status: BLOCKED
Subject: Physical coupon and finished part
Date: 2026-10-15T06:58:24.338050+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/physical-evidence-scope.json](evidence/physical-evidence-scope.json), SHA-256 `b33e41bed3908e98df981133b769386c6b53bdc6e0bbaed124862afcebf475c8`
- [evidence/source-files/docs/v1/science/tests/TEST_CASE_CATALOG.json](evidence/source-files/docs/v1/science/tests/TEST_CASE_CATALOG.json), SHA-256 `5746f3325bec2d62eb6c9e2f50184991c46e250bc9e3c76a2effcfbc8915a524`

Numbers: no coupon; no finished-part measurement in the supplied record. Battery results are calculations, and T07 publication supports schema contracts only. Lab B/C/D remain unrun. No strain series or measured mass was synthesized; chemistry is not measured for a real named lot here.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.

Missing input / resume condition: A real coupon with specimen/lot/form identity, measured chemistry/oxygen, dimensions/mass and photo/scan hash; raw load/strain/displacement hashes, valid load-cell/strain-system calibration, model hash, prediction frozen before measurement and residual against a predeclared band. Finished-part mass must be separate from CAD mass. Physical evidence does not itself grant catalog admission.
