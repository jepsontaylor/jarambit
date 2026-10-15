Status: BLOCKED
Subject: Measured film; coating and isotope rows
Date: 2026-10-15T06:58:24.338923+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/physical-evidence-scope.json](evidence/physical-evidence-scope.json), SHA-256 `b33e41bed3908e98df981133b769386c6b53bdc6e0bbaed124862afcebf475c8`
- [evidence/source-files/docs/v1/science/tests/TEST_CASE_CATALOG.json](evidence/source-files/docs/v1/science/tests/TEST_CASE_CATALOG.json), SHA-256 `5746f3325bec2d62eb6c9e2f50184991c46e250bc9e3c76a2effcfbc8915a524`

Numbers: no measured film in the supplied record. No film thickness, chemistry, sham, adhesion or environmental observation is present. The canonical untracked idea essays (file18), recipes and renders are not observations. Isotope ratios are absent; isotope rows remain proposed. The FEM mesh was not used as an atomic model and structural scores receive no coating credit.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.

Missing input / resume condition: Named substrate lot, measured calibrated film thickness and chemistry (instrument/raw spectrum hash), actual logged processing, a sham control and relevant adhesion/environment evidence for each claim. Isotope claims also require measured isotope ratios. Keep coating observations out of fitness/G1/hard gates.
