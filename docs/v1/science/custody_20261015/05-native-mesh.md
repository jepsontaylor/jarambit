Status: BLOCKED
Subject: C.10a, C.9.2, C.9.3; each separately BLOCKED
Date: 2026-10-15T06:58:24.299742+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/native-dispositions.json](evidence/native-dispositions.json), SHA-256 `a1b3b9a09eea0f02c9e25a9354df8d9ad8a55a660c099ba3e9fbde7203d92277`
- [evidence/dependencies.json](evidence/dependencies.json), SHA-256 `b19c4c671fe966c4195646f56c0abf0671eb233f89b3bc03b5c787a9fc81b554`
- [evidence/source-files/evidence/cad_battery/c10a.json](evidence/source-files/evidence/cad_battery/c10a.json), SHA-256 `188013b9289c368a3dd43c259692fc07bab35160f66aac0747ff8f7892823338`
- [evidence/source-files/evidence/cad_battery/c92.json](evidence/source-files/evidence/cad_battery/c92.json), SHA-256 `9840d0f53bfc3dc13da3ccbe04b8a7b8bed70490d1f520be076c128c9019eb32`
- [evidence/source-files/evidence/cad_battery/c93.json](evidence/source-files/evidence/cad_battery/c93.json), SHA-256 `c7585298f57ee3cf8be88a0dbfe782f974c03d982382e8af8548eb74fb13ea81`

Numbers and full main-blob hashes:

```json
{
  "c10a": {
    "disposition": "BLOCKED",
    "geometry": {
      "designs/switchback/C10a/cad/switchback_revC10a_ground.step": {
        "sha256": "441cfabc284efd632b69b169816bd1242088508d95dd93839dcea419e582dbe7",
        "bytes": 8073736
      },
      "designs/switchback/C10a/cad/switchback_revC10a_ground.stl": {
        "sha256": "0bcadad61bff550d9c527266e183440e8242c3a0222b9a89755cdc682b214411",
        "bytes": 4680484
      }
    },
    "mass": {
      "step_g": 64.84116307039213,
      "readme_g": 64.841,
      "stl_g": 64.8483944338768,
      "step_vs_readme": {
        "status": "PASS",
        "rel": 2.5149271623446703e-06,
        "tolerance": 0.001
      },
      "stl_vs_readme": {
        "status": "PASS",
        "rel": 0.00011403947929260022,
        "tolerance": 0.01
      }
    },
    "units": {
      "units": "mm",
      "units_source": "step_declaration"
    },
    "one_solid": {
      "solids": 1
    },
    "gate_rs_v2": {
      "id": "gate.rs_v2",
      "kind": "gate",
      "status": "blocked",
      "solver": null,
      "geometry_sha256": "441cfabc284efd632b69b169816bd1242088508d95dd93839dcea419e582dbe7",
      "source_commit": "a580ffa3b339faccfdf0d818e69ef4ec56617bd3",
      "evidence_path": null,
      "fresh_this_lane": false,
      "reason": "B-rep is not an RS-karambit-v2 genome"
    },
    "missing": "STEP-capable mesher + solver emitting iterations; own bound three-level family and native observables"
  },
  "c92": {
    "disposition": "BLOCKED",
    "geometry": {
      "designs/switchback/C9.2/cad/switchback_revC9_2_ground.step": {
        "sha256": "2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307",
        "bytes": 8453798
      },
      "designs/switchback/C9.2/cad/switchback_revC9_2_ground.stl": {
        "sha256": "10b8c41f80b898c255cc090a349559722258f87f8af849ce9a605e14d762e847",
        "bytes": 4517384
      }
    },
    "mass": {
      "step_g": 66.7639275744453,
      "readme_g": 66.764,
      "stl_g": 66.76688922451434,
      "step_vs_readme": {
        "status": "PASS",
        "rel": 1.0847995130809342e-06,
        "tolerance": 0.001
      },
      "stl_vs_readme": {
        "status": "PASS",
        "rel": 4.3275185943744283e-05,
        "tolerance": 0.01
      }
    },
    "units": {
      "units": "mm",
      "units_source": "step_declaration"
    },
    "one_solid": {
      "solids": 1
    },
    "gate_rs_v2": {
      "id": "gate.rs_v2",
      "kind": "gate",
      "status": "blocked",
      "solver": null,
      "geometry_sha256": "2ad2a8ecaf4fca67ea4debe5b5da48d2d6216f4a8960296985a9fa38f5b1c307",
      "source_commit": "a580ffa3b339faccfdf0d818e69ef4ec56617bd3",
      "evidence_path": null,
      "fresh_this_lane": false,
      "reason": "B-rep is not an RS-karambit-v2 genome"
    },
    "missing": "STEP-capable mesher + solver emitting iterations; own bound three-level family and native observables"
  },
  "c93": {
    "disposition": "BLOCKED",
    "geometry": {
      "designs/switchback/C9.3/cad/switchback_revC9_3_ground.step": {
        "sha256": "3a818183bcb5b9a9093da947e00414ed29aa9bfebbb614046b8fb0b16dcbe919",
        "bytes": 8227796
      },
      "designs/switchback/C9.3/cad/switchback_revC9_3_ground.stl": {
        "sha256": "1aeda17eba396bcec7380ac27f7d20886d64d234f70ad8d3d0cc57aaf63d74ca",
        "bytes": 4399584
      }
    },
    "mass": {
      "step_g": 66.77269897407103,
      "readme_g": 66.773,
      "stl_g": 66.77640763073035,
      "step_vs_readme": {
        "status": "PASS",
        "rel": 4.508198358055162e-06,
        "tolerance": 0.001
      },
      "stl_vs_readme": {
        "status": "PASS",
        "rel": 5.103306321942664e-05,
        "tolerance": 0.01
      }
    },
    "units": {
      "units": "mm",
      "units_source": "step_declaration"
    },
    "one_solid": {
      "solids": 1
    },
    "gate_rs_v2": {
      "id": "gate.rs_v2",
      "kind": "gate",
      "status": "blocked",
      "solver": null,
      "geometry_sha256": "3a818183bcb5b9a9093da947e00414ed29aa9bfebbb614046b8fb0b16dcbe919",
      "source_commit": "a580ffa3b339faccfdf0d818e69ef4ec56617bd3",
      "evidence_path": null,
      "fresh_this_lane": false,
      "reason": "B-rep is not an RS-karambit-v2 genome"
    },
    "missing": "STEP-capable mesher + solver emitting iterations; own bound three-level family and native observables"
  }
}
```

All three retained geometry/mass evaluations pass: one solid, declared mm, STEP/README tolerance 0.1%, STL/README tolerance 1%. This was not a new geometry measurement. Only OCP imports in venv-cad; no checked STEP mesher plus iteration-reporting solver exists. OCP alone is insufficient. Old unnamed ladders have not been admitted: a level lacking this STEP hash and solver counts/iterations cannot bind a result. Native SPG/aesthetics/sequence need their own defined derivation; no genome values may fill them. C.10c remains archived.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.

Missing input / resume condition: An admitted lane, existing STEP mesher/solver and a bound three-level family for each body, then its own load/sequence/SPG/aes definitions and observations. Run C.10a, then C.9.2, then C.9.3, one body per lease. gate.rs_v2 remains blocked for native bodies.
