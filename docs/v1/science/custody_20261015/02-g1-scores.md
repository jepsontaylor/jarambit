Status: DONE-PASS
Subject: G1 arithmetic; four genome records
Date: 2026-10-15T06:57:56.116637+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/metric-reconciliation.json](evidence/metric-reconciliation.json), SHA-256 `cf873a989f8ce898d9afa60e10449a0db562933a1d21594d1d2159e8bef2b064`
- [evidence/source-files/metrics/global_metric.py](evidence/source-files/metrics/global_metric.py), SHA-256 `fc8d4cee369550413db640982b07054fd42e026e453ed5a020426aaf59be04e9`
- [evidence/source-files/evidence/cad_battery/g3.json](evidence/source-files/evidence/cad_battery/g3.json), SHA-256 `c36a2dad447b6b93f56549aeb4b5dac7816b35a850fbdf787170fcca38ee6c4a`
- [evidence/source-files/evidence/cad_battery/w271b_11772.json](evidence/source-files/evidence/cad_battery/w271b_11772.json), SHA-256 `c3af41ce3821cd064a38872e9acd0ff484bb6fdc39d1a41eebada3ed20d4aa98`
- [evidence/source-files/evidence/cad_battery/w271b_11860.json](evidence/source-files/evidence/cad_battery/w271b_11860.json), SHA-256 `27aae63d220b57a940b5ed27df55f70824acf28123f8df024da55ef4abf1cee1`
- [evidence/source-files/evidence/cad_battery/w271c_11522.json](evidence/source-files/evidence/cad_battery/w271c_11522.json), SHA-256 `f500ab4091832f4672ec1ea2409e064c1595b03cc5233d3296d43d1af0820178`

Formula: `G = .35*min(solid_tip_SF,2) + .35*(SPG/4) + .20*aes - .05*max(0,mass_g-77)/10 - .05*max(0,1.2-seq_ratio)/1.2`.

```json
{
  "g3": {
    "inputs": {
      "mass_g": 84.80209229536577,
      "spg": 4.14687,
      "seq_ratio": 0.9590825616164743,
      "solid_tip_sf_nodal_max": 1.6003,
      "aes_score": 0.6486
    },
    "G": 1.0036274369238576,
    "terms": {
      "tip": 1.6003,
      "tip_source": "solid_tip_sf_nodal_max",
      "tip_missing": false,
      "provisional": false,
      "spg_n": 1.0367175,
      "aes": 0.6486,
      "mass_pen": 0.7802092295365768,
      "seq_gap": 0.20076453198627137,
      "status": "COMPLETE",
      "missing": [],
      "metric_version": "G1"
    },
    "subject_sha256": "c36a2dad447b6b93f56549aeb4b5dac7816b35a850fbdf787170fcca38ee6c4a"
  },
  "w271b_11772": {
    "inputs": {
      "mass_g": 78.5515514925079,
      "spg": 3.89964,
      "seq_ratio": 0.8823392882835103,
      "solid_tip_sf_nodal_max": 0.8337,
      "aes_score": 0.6928
    },
    "G": 0.7505798795492734,
    "terms": {
      "tip": 0.8337,
      "tip_source": "solid_tip_sf_nodal_max",
      "tip_missing": false,
      "provisional": false,
      "spg_n": 0.97491,
      "aes": 0.6928,
      "mass_pen": 0.15515514925078974,
      "seq_gap": 0.26471725976374144,
      "status": "COMPLETE",
      "missing": [],
      "metric_version": "G1"
    },
    "subject_sha256": "c3af41ce3821cd064a38872e9acd0ff484bb6fdc39d1a41eebada3ed20d4aa98"
  },
  "w271b_11860": {
    "inputs": {
      "mass_g": 73.32648797691759,
      "spg": 3.69093,
      "seq_ratio": 0.8917967778864481,
      "aes_score": 0.6332
    },
    "G": null,
    "terms": {
      "tip": null,
      "tip_source": null,
      "tip_missing": true,
      "provisional": true,
      "spg_n": 0.9227325,
      "aes": 0.6332,
      "mass_pen": 0.0,
      "seq_gap": 0.25683601842795994,
      "status": "INCOMPLETE",
      "missing": [
        "tip: solid_tip_sf_nodal_max: missing; plate_tipsub_screen_sf: missing; twist_tipzone_sf_strict: missing"
      ],
      "metric_version": "G1"
    },
    "subject_sha256": "27aae63d220b57a940b5ed27df55f70824acf28123f8df024da55ef4abf1cee1"
  },
  "w271c_11522": {
    "inputs": {
      "mass_g": 79.96161512803431,
      "seq_ratio": 0.7784421108892615
    },
    "G": null,
    "terms": {
      "tip": null,
      "tip_source": null,
      "tip_missing": true,
      "provisional": true,
      "spg_n": null,
      "aes": null,
      "mass_pen": 0.29616151280343106,
      "seq_gap": 0.3512982409256154,
      "status": "INCOMPLETE",
      "missing": [
        "tip: solid_tip_sf_nodal_max: missing; plate_tipsub_screen_sf: missing; twist_tipzone_sf_strict: missing",
        "spg: missing",
        "aes_score: missing"
      ],
      "metric_version": "G1"
    },
    "subject_sha256": "f500ab4091832f4672ec1ea2409e064c1595b03cc5233d3296d43d1af0820178"
  }
}
```

Smoke G: `0.9674999999999999` (target 0.9675 within 1e-9). Deleting `aes_score` from actual complete g3 inputs returns null / INCOMPLETE with `aes_score: missing`. 11860 lists all three absent tip alternatives, in the locked order. 11522 also lacks SPG and aesthetics. No tip alternative was inserted. The full terms and negative control are retained in the calculation record. These are completed arithmetic checks; failed hard gates remain failed.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.
