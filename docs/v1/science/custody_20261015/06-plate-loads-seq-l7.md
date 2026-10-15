Status: DONE-FAIL
Subject: Four genomes; native subjects remain BLOCKED on file05
Date: 2026-10-15T06:58:24.308935+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/plate-reconciliation.json](evidence/plate-reconciliation.json), SHA-256 `e02dbe3fd94936bf77365ba3293338be63f6ddad48064385bdcb7468b68ce5e0`
- [evidence/source-files/evidence/cad_battery/g3.json](evidence/source-files/evidence/cad_battery/g3.json), SHA-256 `c36a2dad447b6b93f56549aeb4b5dac7816b35a850fbdf787170fcca38ee6c4a`
- [evidence/source-files/evidence/cad_battery/w271b_11772.json](evidence/source-files/evidence/cad_battery/w271b_11772.json), SHA-256 `c3af41ce3821cd064a38872e9acd0ff484bb6fdc39d1a41eebada3ed20d4aa98`
- [evidence/source-files/evidence/cad_battery/w271b_11860.json](evidence/source-files/evidence/cad_battery/w271b_11860.json), SHA-256 `27aae63d220b57a940b5ed27df55f70824acf28123f8df024da55ef4abf1cee1`
- [evidence/source-files/evidence/cad_battery/w271c_11522.json](evidence/source-files/evidence/cad_battery/w271c_11522.json), SHA-256 `f500ab4091832f4672ec1ea2409e064c1595b03cc5233d3296d43d1af0820178`

Numbers (each vector comes from its own subject JSON):

```json
{
  "g3": {
    "disposition": "DONE-FAIL",
    "subject_sha256": "c36a2dad447b6b93f56549aeb4b5dac7816b35a850fbdf787170fcca38ee6c4a",
    "geometry_sha256": "fba8743fd011683b4fd171eb73dcd098941d06d0f6ea949ee02ebafa0f2cf1e2",
    "evidence_path": "evidence/rs_v2/g3_tip+00_t60_tt3.json",
    "loads": {
      "hiker_lateral_n": {
        "value_n_or_sf": 351.6634692341955,
        "compared_with": 180
      },
      "hunter_lateral_n": {
        "value_n_or_sf": 351.6634692341955,
        "compared_with": 260
      },
      "ring_pull_n": {
        "value_n_or_sf": 17463.975804201444,
        "compared_with": 1500
      },
      "chord_twist_human_max_sf": {
        "value_n_or_sf": 0.13210292745211555,
        "compared_with": 16200
      },
      "spine_sf": {
        "value_n_or_sf": 0.4189305474633907,
        "compared_with": 3427
      },
      "ring_back_sf": {
        "value_n_or_sf": 2.660229597729158,
        "compared_with": 3000
      },
      "tip_inplane_sf_record_only": {
        "value_n_or_sf": 0.5648925162300026,
        "compared_with": 1000
      },
      "pry": null
    },
    "sequence": {
      "seq_ratio": 0.9590825616164743,
      "seq_target": 1.2,
      "side_report_seq_ratio": 0.9765216896409545
    },
    "l7": {
      "label": "screening",
      "not": "spec \u00a77.3 L7",
      "fat_sf": 0.9823103780720044,
      "cycles": "1e7",
      "load": "0..180 N"
    },
    "gates": {
      "gates": {
        "aesthetic_and_geometric": "fail",
        "fatigue": "fail",
        "floors_828_joint": "pass",
        "human_max": "fail",
        "seq_hard": "fail",
        "solid_tip_sf": "pass",
        "strict_hunter_lateral": "pass",
        "twist_floor_body_and_tipsub_strict": "pass"
      },
      "all_hard": false
    }
  },
  "w271b_11772": {
    "disposition": "DONE-FAIL",
    "subject_sha256": "c3af41ce3821cd064a38872e9acd0ff484bb6fdc39d1a41eebada3ed20d4aa98",
    "geometry_sha256": "5418a4f1dde60341675a202b6b9d4d834b07c42a90ae0a11946a889039322cab",
    "evidence_path": "evidence/rs_v2/w271b_11772.json",
    "loads": {
      "hiker_lateral_n": {
        "value_n_or_sf": 306.3229630221624,
        "compared_with": 180
      },
      "hunter_lateral_n": {
        "value_n_or_sf": 306.3229630221624,
        "compared_with": 260
      },
      "ring_pull_n": {
        "value_n_or_sf": 15492.611845093023,
        "compared_with": 1500
      },
      "chord_twist_human_max_sf": {
        "value_n_or_sf": 0.07566315653722758,
        "compared_with": 16200
      },
      "spine_sf": {
        "value_n_or_sf": 0.4177895337213913,
        "compared_with": 3427
      },
      "ring_back_sf": {
        "value_n_or_sf": 2.418769313140643,
        "compared_with": 3000
      },
      "tip_inplane_sf_record_only": {
        "value_n_or_sf": 0.5967145313584783,
        "compared_with": 1000
      },
      "pry": null
    },
    "sequence": {
      "seq_ratio": 0.8823392882835103,
      "seq_target": 1.2,
      "side_report_seq_ratio": 0.8918998553971407
    },
    "l7": {
      "label": "screening",
      "not": "spec \u00a77.3 L7",
      "fat_sf": 0.8556596062528332,
      "cycles": "1e7",
      "load": "0..180 N"
    },
    "gates": {
      "gates": {
        "aesthetic_and_geometric": "pass",
        "fatigue": "fail",
        "floors_828_joint": "pass",
        "human_max": "fail",
        "seq_hard": "fail",
        "solid_tip_sf": "fail",
        "strict_hunter_lateral": "pass",
        "twist_floor_body_and_tipsub_strict": "fail"
      },
      "all_hard": false
    }
  },
  "w271b_11860": {
    "disposition": "DONE-FAIL",
    "subject_sha256": "27aae63d220b57a940b5ed27df55f70824acf28123f8df024da55ef4abf1cee1",
    "geometry_sha256": "3340300af53f3244b85d546c44e2065828ffe27b2d670567bfca937d0f192e03",
    "evidence_path": "evidence/rs_v2/w271b_11860.json",
    "loads": {
      "hiker_lateral_n": {
        "value_n_or_sf": 270.6431212247853,
        "compared_with": 180
      },
      "hunter_lateral_n": {
        "value_n_or_sf": 270.6431212247853,
        "compared_with": 260
      },
      "ring_pull_n": {
        "value_n_or_sf": 12880.024538819793,
        "compared_with": 1500
      },
      "chord_twist_human_max_sf": {
        "value_n_or_sf": 0.07501161359989089,
        "compared_with": 16200
      },
      "spine_sf": {
        "value_n_or_sf": 0.38407761198659196,
        "compared_with": 3427
      },
      "ring_back_sf": {
        "value_n_or_sf": 1.9114154621840507,
        "compared_with": 3000
      },
      "tip_inplane_sf_record_only": {
        "value_n_or_sf": 0.5275654193903646,
        "compared_with": 1000
      },
      "pry": null
    },
    "sequence": {
      "seq_ratio": 0.8917967778864481,
      "seq_target": 1.2,
      "side_report_seq_ratio": null
    },
    "l7": {
      "label": "screening",
      "not": "spec \u00a77.3 L7",
      "fat_sf": 0.7559942103507366,
      "cycles": "1e7",
      "load": "0..180 N"
    },
    "gates": {
      "gates": {
        "aesthetic_and_geometric": "pass",
        "fatigue": "fail",
        "floors_828_joint": "pass",
        "human_max": "fail",
        "seq_hard": "fail",
        "solid_tip_sf": "unverified",
        "strict_hunter_lateral": "pass",
        "twist_floor_body_and_tipsub_strict": "fail"
      },
      "all_hard": false
    }
  },
  "w271c_11522": {
    "disposition": "DONE-FAIL",
    "subject_sha256": "f500ab4091832f4672ec1ea2409e064c1595b03cc5233d3296d43d1af0820178",
    "geometry_sha256": "735d7c49199393af55653525fd19dfb6a0e075bb1e1c34c661e8cea39ab70276",
    "evidence_path": "evidence/rs_v2/w271c_11522.json",
    "loads": {
      "hiker_lateral_n": {
        "value_n_or_sf": 274.69077251697746,
        "compared_with": 180
      },
      "hunter_lateral_n": {
        "value_n_or_sf": 274.69077251697746,
        "compared_with": 260
      },
      "ring_pull_n": {
        "value_n_or_sf": 13403.844789238432,
        "compared_with": 1500
      },
      "chord_twist_human_max_sf": {
        "value_n_or_sf": 0.09651947249219367,
        "compared_with": 16200
      },
      "spine_sf": {
        "value_n_or_sf": 0.41939747194547083,
        "compared_with": 3427
      },
      "ring_back_sf": {
        "value_n_or_sf": 1.9923488470274096,
        "compared_with": 3000
      },
      "tip_inplane_sf_record_only": {
        "value_n_or_sf": 0.5739417829204602,
        "compared_with": 1000
      },
      "pry": null
    },
    "sequence": {
      "seq_ratio": 0.7784421108892615,
      "seq_target": 1.2,
      "side_report_seq_ratio": null
    },
    "l7": {
      "label": "screening",
      "not": "spec \u00a77.3 L7",
      "fat_sf": 0.7673006161022223,
      "cycles": "1e7",
      "load": "0..180 N"
    },
    "gates": {
      "gates": {
        "aesthetic_and_geometric": "pass",
        "fatigue": "fail",
        "floors_828_joint": "pass",
        "human_max": "fail",
        "seq_hard": "fail",
        "solid_tip_sf": "unverified",
        "strict_hunter_lateral": "pass",
        "twist_floor_body_and_tipsub_strict": "fail"
      },
      "all_hard": false
    }
  }
}
```

Each genome has failed plate.loads, plate.seq and plate.l7. The cycle string is `1e7`, the load string `0..180 N`, and L7 is screening, explicitly not spec §7.3 L7. `compared_with` is retained verbatim: a dimensionless SF is judged against 1 for the named demand, not compared numerically to its demand in N or N·mm. Pry remains absent on the certify records. Certify and side sequences are separately labeled; side nulls remain null. All_hard remains false. No certify rerun was needed. Native rows remain blocked on their own meshes.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.
