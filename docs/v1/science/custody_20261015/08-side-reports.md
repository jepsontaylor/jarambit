Status: BLOCKED
Subject: 11860/11522/native A1–A3 and all A4; existing g3/11772 preserved
Date: 2026-10-15T06:58:24.327832+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/worktree-inventory.json](evidence/worktree-inventory.json), SHA-256 `2d671156d63f3f1107028805e857ebeeed235c2dfeb3be2f7bb31549bc051018`
- [evidence/side-report-custody.json](evidence/side-report-custody.json), SHA-256 `b5e21a81fb787bbe60cfcf1828435af00021e4cb05a37fc9c5221c44907e9118`
- [evidence/external/home/ubuntu/jarambit_review_custody/disposition-20261014/report-a1/g3_a1a3.json](evidence/external/home/ubuntu/jarambit_review_custody/disposition-20261014/report-a1/g3_a1a3.json), SHA-256 `3e419ac1cbd2576b9b2f92296862d937e763abe27cc2a065c4937ff6ec4a85f9`
- [evidence/source-files/evidence/cad_battery/side/w271b_11772_a1a3.json](evidence/source-files/evidence/cad_battery/side/w271b_11772_a1a3.json), SHA-256 `843f64b9a1ab9270d43a488adcf55b57a68bdefb957513ecc4e9359eae0f8340`
- [evidence/source-files/crates/crescent/examples/g3_side_report.rs](evidence/source-files/crates/crescent/examples/g3_side_report.rs), SHA-256 `1b51f9a9c09c9c7c94faa171b50e267051ba3df0a6af6873ffe0ff543e57c93f`

Existing numbers and source hashes are retained in side-report-custody.json. g3 has 26,137 elements at 0.25 mm² and side sequence 0.9765216896409545; 11772 has 25,608 and side sequence 0.8918998553971407. Their certify sequences remain 0.9590825616164743 and 0.8823392882835103. Existing A1–A3 execution passes coexist with failed design sequences.

Correction to the handoff prose: g3's retained REPORT.md/JSON assign the near-90%-peak area of approximately 40.39 mm² to the blade and 2.89 mm² to the groove. File08's introductory sentence reverses those areas; the source record is authoritative and was not edited.

11860 A1–A3 is independent of its missing solid iterations; it is blocked here by lane admission, not by skfem. The existing public report_fields API and generator were inspected; the generator hardcodes COMMITTED_SEQ and g3 identity. Adapting it requires an owned admitted lane. 11522 still needs its own required mesh under file04. Native subjects need file05. A4 lacks a distinct support model, bore support, foundation stiffness and a valid buckling calculation. No arbitrary eigensolver result was substituted.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.

Missing input / resume condition: Admit a lane to adapt the reporting helper and run 11860 at 0.25 mm² with its own genome hash, mass, sequence labels, peaks/areas and m=10/20/30 shares. 11522/native need their own mesh prerequisites. A4 additionally needs a separate defined support model and valid buckling computation; certified run_b stays fixed.
