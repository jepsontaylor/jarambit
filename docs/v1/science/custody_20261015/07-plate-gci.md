Status: BLOCKED
Subject: Real plate refinement families for four genomes and three native bodies
Date: 2026-10-15T06:58:24.314475+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/worktree-inventory.json](evidence/worktree-inventory.json), SHA-256 `2d671156d63f3f1107028805e857ebeeed235c2dfeb3be2f7bb31549bc051018`
- [evidence/plate-gci-dispositions.json](evidence/plate-gci-dispositions.json), SHA-256 `62ca511dd76b7a51b4043c77c1030604cbbc69adea03b4de972d86ebbc360601`

Numbers: zero stored three-level plate families in the four bound battery records. These say `no three-mesh plate family stored`; native rows say `no mesh bound`. Rust is the available implementation path; missing skfem does not itself block the Rust plate solver. Current work is blocked by lane admission: 35 registered checkouts, at least 24 expressly protected historical snapshots, no ownership transfer and no heavy lane admitted. No new plate levels ran, including no 0.125 mm² run. Solid GCI evidence is a different observable and supplies no plate family.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.

Missing input / resume condition: An eligible owned lane under the eight-lane limit and one admitted four-CPU/eight-GiB lease away from CPU0. Start g3 at requested areas 4/1/0.25 mm², then the other genomes. Bind lateral peak stress (same units/region/exclusions/reduction), actual counts and supported refinement definition. Retain unsupported or oscillatory results without assuming a ratio. Native families also need file05.
