Status: BLOCKED
Subject: Current-source T01-12 through T01-18 catalog execution attribution
Date: 2026-10-15T07:01:14.482236+00:00
Source identity: `b35dacff5a74a5654e16d0164a625cd97c82bb3f` (product reference; no product checkout claimed).

Evidence and sha256:

- [evidence/preflight-manifest.json](evidence/preflight-manifest.json), SHA-256 `134526facdd6ea36b615bd00d6f9e94115c8f0a4e4b309646837d349d40aa30c`
- [evidence/T01-attribution.json](evidence/T01-attribution.json), SHA-256 `97a42f35b7b3e20c6dd574e371c510ff91c70fdc1b6b6c0e9aaa5ea7f6fbba7e`
- [evidence/worktree-inventory.json](evidence/worktree-inventory.json), SHA-256 `2d671156d63f3f1107028805e857ebeeed235c2dfeb3be2f7bb31549bc051018`
- [evidence/retained/held-S02/REVIEW.json](evidence/retained/held-S02/REVIEW.json), SHA-256 `2ce78ccd61e739a2f4f88a8e8c7ad39a01872a764b95769b8c2a0f249cab873c`
- [evidence/source-files/docs/v1/science/tests/TEST_UPGRADE_PLAN.md](evidence/source-files/docs/v1/science/tests/TEST_UPGRADE_PLAN.md), SHA-256 `95eb4c6f652cac1479f69076f54ee9dfdf5ad4c2cd91091add211eb5e9682159`

Numbers: all seven named controls already exist; all seven also have retained historical paired receipts at source 69f02fcee66411a26dfc0abdba0ec71ad1c69748. The historical final003 inventory covers all 18 IDs with no missing rows. No implementation was rebuilt and no historical proof was retagged as new.

```json
{
  "T01-12-threshold_edge": {
    "implementation_path": "fem_solid/tests/test_gci_evidence.py",
    "test_name": "test_T01_12_threshold_edge",
    "current_source_sha256": "81543f3197ba05122dd1f75b7abb7a14e82623e05855bbdc025fe4c69b37fb7b",
    "frozen_allowed_path": "fem_solid/tests/test_gci.py",
    "path_matches_catalog": false,
    "historical_execution": "passed; paired controls",
    "historical_source": "69f02fcee66411a26dfc0abdba0ec71ad1c69748",
    "receipt": {
      "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-12-threshold_edge.json",
      "custody_path": "evidence/retained/T01/cases/T01-12-threshold_edge.json",
      "sha256": "37ad42c7aa090cd7bf55dcea79edec7af8024a5ac642ec30895e31ec14e0221b",
      "bytes": 810
    },
    "artifacts": [
      {
        "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-12-threshold_edge.result.txt",
        "custody_path": "evidence/retained/T01/cases/T01-12-threshold_edge.result.txt",
        "sha256": "9f8fc6c17f314869924a4d46856a7c2fe961d1f06e6b95a65402f362fdffa7d7",
        "bytes": 556
      }
    ],
    "current_attempt": "not_run; no lane transfer/admission",
    "catalog_status_preserved": "proposed; not implemented or executed"
  },
  "T01-13-negative_error_band": {
    "implementation_path": "fem_solid/tests/test_gci_evidence.py",
    "test_name": "test_T01_13_negative_error_band",
    "current_source_sha256": "81543f3197ba05122dd1f75b7abb7a14e82623e05855bbdc025fe4c69b37fb7b",
    "frozen_allowed_path": "fem_solid/tests/test_gci.py",
    "path_matches_catalog": false,
    "historical_execution": "passed; paired controls",
    "historical_source": "69f02fcee66411a26dfc0abdba0ec71ad1c69748",
    "receipt": {
      "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-13-negative_error_band.json",
      "custody_path": "evidence/retained/T01/cases/T01-13-negative_error_band.json",
      "sha256": "7450f717f9120a496809aa2e826754ba30d7f81019cb3d8434e525cfb73c39bb",
      "bytes": 820
    },
    "artifacts": [
      {
        "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-13-negative_error_band.result.txt",
        "custody_path": "evidence/retained/T01/cases/T01-13-negative_error_band.result.txt",
        "sha256": "2f5dcd0c20470e3668fbf0596b23e1403eee62a7ca3b0c3ecb54d379d2b0799e",
        "bytes": 561
      }
    ],
    "current_attempt": "not_run; no lane transfer/admission",
    "catalog_status_preserved": "proposed; not implemented or executed"
  },
  "T01-14-inventory_empty": {
    "implementation_path": "fem_solid/tests/test_gci_evidence.py",
    "test_name": "test_T01_14_inventory_empty",
    "current_source_sha256": "81543f3197ba05122dd1f75b7abb7a14e82623e05855bbdc025fe4c69b37fb7b",
    "frozen_allowed_path": "fem_solid/tests/test_gci.py",
    "path_matches_catalog": false,
    "historical_execution": "passed; paired controls",
    "historical_source": "69f02fcee66411a26dfc0abdba0ec71ad1c69748",
    "receipt": {
      "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-14-inventory_empty.json",
      "custody_path": "evidence/retained/T01/cases/T01-14-inventory_empty.json",
      "sha256": "125849e006c3bf348f0e2d8c2acd9eaad02657757404ce7010a128a52d9a4939",
      "bytes": 812
    },
    "artifacts": [
      {
        "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-14-inventory_empty.result.txt",
        "custody_path": "evidence/retained/T01/cases/T01-14-inventory_empty.result.txt",
        "sha256": "be295309af4ee0281d66933ec2006e1fd5ad6c01f377c58b6cb7271e504ed719",
        "bytes": 557
      }
    ],
    "current_attempt": "not_run; no lane transfer/admission",
    "catalog_status_preserved": "proposed; not implemented or executed"
  },
  "T01-15-stale_noop": {
    "implementation_path": "fem_solid/tests/test_fresh_attempts.py",
    "test_name": "test_T01_15_stale_noop",
    "current_source_sha256": "66f17bd6054d6ecd114360b6302ac6aacea1c36771fd1ebb499d42f529017646",
    "frozen_allowed_path": "fem_solid/tests/test_gci.py",
    "path_matches_catalog": false,
    "historical_execution": "passed; paired controls",
    "historical_source": "69f02fcee66411a26dfc0abdba0ec71ad1c69748",
    "receipt": {
      "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-15-stale_noop.json",
      "custody_path": "evidence/retained/T01/cases/T01-15-stale_noop.json",
      "sha256": "54ce678d09afbe2c523b0cfa81ca0719a89bfb4cee9e455a9286c3eb9647bac0",
      "bytes": 802
    },
    "artifacts": [
      {
        "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-15-stale_noop.result.txt",
        "custody_path": "evidence/retained/T01/cases/T01-15-stale_noop.result.txt",
        "sha256": "f0dee14cfe4050e4f2eb807f42bf1605498bc30fbeaf68f41a93ff098e085035",
        "bytes": 556
      }
    ],
    "current_attempt": "not_run; no lane transfer/admission",
    "catalog_status_preserved": "proposed; not implemented or executed"
  },
  "T01-16-cache_identity": {
    "implementation_path": "fem_solid/tests/test_fresh_attempts.py",
    "test_name": "test_T01_16_cache_identity",
    "current_source_sha256": "66f17bd6054d6ecd114360b6302ac6aacea1c36771fd1ebb499d42f529017646",
    "frozen_allowed_path": "fem_solid/tests/test_gci.py",
    "path_matches_catalog": false,
    "historical_execution": "passed; paired controls",
    "historical_source": "69f02fcee66411a26dfc0abdba0ec71ad1c69748",
    "receipt": {
      "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-16-cache_identity.json",
      "custody_path": "evidence/retained/T01/cases/T01-16-cache_identity.json",
      "sha256": "f755bee37763ef0bffeb781577f83fb74773406d287a0fbe4090d85447cbbec9",
      "bytes": 810
    },
    "artifacts": [
      {
        "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-16-cache_identity.result.txt",
        "custody_path": "evidence/retained/T01/cases/T01-16-cache_identity.result.txt",
        "sha256": "014b591df00054a38af7e470145bb6fcbc7bb624a78e1087e9dae0d90cea5515",
        "bytes": 560
      }
    ],
    "current_attempt": "not_run; no lane transfer/admission",
    "catalog_status_preserved": "proposed; not implemented or executed"
  },
  "T01-17-partial_atomic": {
    "implementation_path": "fem_solid/tests/test_fresh_attempts.py",
    "test_name": "test_T01_17_partial_atomic",
    "current_source_sha256": "66f17bd6054d6ecd114360b6302ac6aacea1c36771fd1ebb499d42f529017646",
    "frozen_allowed_path": "fem_solid/tests/test_gci.py",
    "path_matches_catalog": false,
    "historical_execution": "passed; paired controls",
    "historical_source": "69f02fcee66411a26dfc0abdba0ec71ad1c69748",
    "receipt": {
      "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-17-partial_atomic.json",
      "custody_path": "evidence/retained/T01/cases/T01-17-partial_atomic.json",
      "sha256": "50514a666d350ff993fcddd2270625e326c6e35601343864eb3026eddc16ab91",
      "bytes": 810
    },
    "artifacts": [
      {
        "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-17-partial_atomic.result.txt",
        "custody_path": "evidence/retained/T01/cases/T01-17-partial_atomic.result.txt",
        "sha256": "3912ec628d568713069c9cd410d1cf88246fcc582d4281ff76be483342359dc1",
        "bytes": 560
      }
    ],
    "current_attempt": "not_run; no lane transfer/admission",
    "catalog_status_preserved": "proposed; not implemented or executed"
  },
  "T01-18-peak_singularity": {
    "implementation_path": "fem_solid/tests/test_gci.py",
    "test_name": "test_T01_18_peak_singularity",
    "current_source_sha256": "2e03474e80d6e4bc4848e9437f8719825492df2e04ad318ac862ff1f0e75cf1e",
    "frozen_allowed_path": "fem_solid/tests/test_gci.py",
    "path_matches_catalog": true,
    "historical_execution": "passed; paired controls",
    "historical_source": "69f02fcee66411a26dfc0abdba0ec71ad1c69748",
    "receipt": {
      "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-18-peak_singularity.json",
      "custody_path": "evidence/retained/T01/cases/T01-18-peak_singularity.json",
      "sha256": "58ef9c0eb1a094163b748219f9c2db272bf8ec061bd448704b9067776bf509f4",
      "bytes": 814
    },
    "artifacts": [
      {
        "original_path": "/home/ubuntu/jarambit/.agent/worktrees/codex-science-v1-integration/.agent/science-s02/final-003/cases/T01-18-peak_singularity.result.txt",
        "custody_path": "evidence/retained/T01/cases/T01-18-peak_singularity.result.txt",
        "sha256": "1972b03f8521bfc88e98f8cf70f46d90aedaff7d3eb65a142c434e47f3ac5fde",
        "bytes": 541
      }
    ],
    "current_attempt": "not_run; no lane transfer/admission",
    "catalog_status_preserved": "proposed; not implemented or executed"
  }
}
```

The threshold controls retain nextafter below/exact/above 0.03, negative bands, expected inventories, stale/no-op refusal, cache identities and atomic-publication faults. T01-18 stays synthetic and separates local from global peaks. Six implementations are in the reporter/fresh-attempt modules rather than the frozen allowed test_gci.py entrypoint. The later historical S02 lease explicitly allowed those modules, but this handoff still requires catalog-facing entrypoints and current-source receipt/CI attribution. That work needs an owned lane. T01-01..11 retain their recorded executed status / CI 38662560217. The held packet and REVIEW hash are preserved; no production threshold or numerical floor was activated.

Left byte-identical: `metrics/global_metric.py`, `crates/crescent/src/qd.rs`, `crates/physics/src/lib.rs`, `evidence/fem_solid/gci/*.json`, `fem_solid/gci.py`, `fem_solid/tip_solid.py`, `ops/ci/run_bounded.sh`, the planning catalog, `release-v1.json`, and every battery subject/manifest. See `evidence/preflight-manifest.json` and final `evidence/protected-check.json`.

Missing input / resume condition: An eligible owned lane and exact-source execution/CI admission. Add only necessary thin allowed-path entrypoints, retain the existing controls, then freeze the source and retain per-case receipts. Resolve any scope/oracle conflict explicitly; do not rewrite frozen catalog or protected numerical code.
