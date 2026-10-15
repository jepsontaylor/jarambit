Status: DONE-PASS
Subject: g3 and 11772 retained-stress side calculations; other subjects BLOCKED
Date: 2026-10-15T06:58:24.344781+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/fracture-side-calculations.json](evidence/fracture-side-calculations.json), SHA-256 `7c725a72e01d8c9e634a318d8197a6fe903d94c5cc72d78316300db72445b24e`
- [evidence/external/home/ubuntu/jarambit_review_custody/disposition-20261014/report-a1/g3_a1a3.json](evidence/external/home/ubuntu/jarambit_review_custody/disposition-20261014/report-a1/g3_a1a3.json), SHA-256 `3e419ac1cbd2576b9b2f92296862d937e763abe27cc2a065c4937ff6ec4a85f9`
- [evidence/source-files/evidence/cad_battery/side/w271b_11772_a1a3.json](evidence/source-files/evidence/cad_battery/side/w271b_11772_a1a3.json), SHA-256 `843f64b9a1ab9270d43a488adcf55b57a68bdefb957513ecc4e9359eae0f8340`
- [evidence/source-files/evidence/rs_v2/w271b_11860.json](evidence/source-files/evidence/rs_v2/w271b_11860.json), SHA-256 `84a22dec14a475f4128f83c5ec83dc036c563792e858784b7459269666b3e8f5`
- [evidence/source-files/evidence/rs_v2/w271c_11522.json](evidence/source-files/evidence/rs_v2/w271c_11522.json), SHA-256 `9b157abc59d37ea777bcd50f5a5db5f7947eed8bb09365cdb7e76d6af53af3d4`

Numbers:

```json
{
  "g3": {
    "status": "DONE-PASS calculation only",
    "side_source_sha256": "3e419ac1cbd2576b9b2f92296862d937e763abe27cc2a065c4937ff6ec4a85f9",
    "geometry_csv": "evidence/rs_v2/genomes/g3_tip+00_t60_tt3.csv",
    "geometry_csv_sha256": "fba8743fd011683b4fd171eb73dcd098941d06d0f6ea949ee02ebafa0f2cf1e2",
    "n_elem": 26137,
    "area_mm2": 0.25,
    "load": "lateral 0..180 N; R=0, code L7 screen; not spec L7",
    "groove_delta_sigma_MPa": 371.03242170640027,
    "formula": "a[m] = (DeltaK[MPa sqrt(m)] / (1.12 * Delta_sigma[MPa]))^2 / pi",
    "rows": [
      {
        "delta_K_MPa_sqrt_m": 2.0,
        "one_direction_depth_um": 7.37310385641528,
        "assumed_same_amplitude_reversing_depth_um": 1.84327596410382
      },
      {
        "delta_K_MPa_sqrt_m": 4.0,
        "one_direction_depth_um": 29.49241542566112,
        "assumed_same_amplitude_reversing_depth_um": 7.37310385641528
      },
      {
        "delta_K_MPa_sqrt_m": 6.0,
        "one_direction_depth_um": 66.35793470773751,
        "assumed_same_amplitude_reversing_depth_um": 16.58948367693438
      }
    ],
    "inspection_comparison": "no inspection size",
    "reversing_assumption": "hypothetical -180..180 N doubles elastic stress range; not a measured spectrum or certify replacement",
    "scientific_limit": "DeltaK values are sensitivities, not measured lot thresholds or qualification"
  },
  "w271b_11772": {
    "status": "DONE-PASS calculation only",
    "side_source_sha256": "843f64b9a1ab9270d43a488adcf55b57a68bdefb957513ecc4e9359eae0f8340",
    "geometry_csv": "evidence/rs_v2/genomes/w271b_11772_genome.csv",
    "geometry_csv_sha256": "5418a4f1dde60341675a202b6b9d4d834b07c42a90ae0a11946a889039322cab",
    "n_elem": 25608,
    "area_mm2": 0.25,
    "load": "lateral 0..180 N; R=0, code L7 screen; not spec L7",
    "groove_delta_sigma_MPa": 421.392747567998,
    "formula": "a[m] = (DeltaK[MPa sqrt(m)] / (1.12 * Delta_sigma[MPa]))^2 / pi",
    "rows": [
      {
        "delta_K_MPa_sqrt_m": 2.0,
        "one_direction_depth_um": 5.716101864395401,
        "assumed_same_amplitude_reversing_depth_um": 1.4290254660988502
      },
      {
        "delta_K_MPa_sqrt_m": 4.0,
        "one_direction_depth_um": 22.864407457581603,
        "assumed_same_amplitude_reversing_depth_um": 5.716101864395401
      },
      {
        "delta_K_MPa_sqrt_m": 6.0,
        "one_direction_depth_um": 51.44491677955861,
        "assumed_same_amplitude_reversing_depth_um": 12.861229194889653
      }
    ],
    "inspection_comparison": "no inspection size",
    "reversing_assumption": "hypothetical -180..180 N doubles elastic stress range; not a measured spectrum or certify replacement",
    "scientific_limit": "DeltaK values are sensitivities, not measured lot thresholds or qualification"
  }
}
```

Both calculations reproduce their own retained side-record tables. No stress was borrowed between subjects. The screening and reversing assumptions are explicitly separate; the code L7 screen is 0..180 N. The G1-input exclusion assertions passed for every active subject, and protected fitness code is unchanged. Weibull/shakedown/flaw quantities remain side data. These tables are retained in custody beside exact battery evidence copies; product publication is deferred to an admitted lane.

11860 and 11522 RS records do not supply the required own lateral stress range/field for this calculation; no table is fabricated. Native bodies need their own mesh/stress. Specification-grade L7 remains BLOCKED on the specification text, required spectrum and calculation. Existing four screening failures and fatigue hard-gate failures remain failures. No actual inspection procedure exists in the supplied evidence: no inspection size.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.
