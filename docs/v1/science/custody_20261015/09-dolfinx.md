Status: BLOCKED
Subject: Independent dolfinx comparison; all subjects
Date: 2026-10-15T06:58:24.328583+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/dependencies.json](evidence/dependencies.json), SHA-256 `b19c4c671fe966c4195646f56c0abf0671eb233f89b3bc03b5c787a9fc81b554`
- [evidence/input-search.json](evidence/input-search.json), SHA-256 `6652d01b1c6fb4da31a81b209f3619071bd9e3d2ab15e16f3f7e2511797c56cc`

Numbers: zero new comparisons and zero primary solver-run credit. All eight local interpreter probes for dolfinx fail with ModuleNotFoundError; xbabe3 system Python also fails. Exact interpreter paths, argv and exceptions are retained once in the shared evidence. The historical g3 dolfinx citation is not an available runtime. No module installation or S07 script copy occurred. Tool-executed status is BLOCKED; numerical agreement is not evaluated.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.

Missing input / resume condition: An existing permitted dolfinx runtime, own bound geometry, admitted lane, and predeclared tolerance; record independent size/iterations and comparison finding separately. Keep primary G1 input and solver_run_count unchanged.
