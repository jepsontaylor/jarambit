"""Frozen T07 record controls. Oracles are the sealed plan-69 literals.

A passing count is not group acceptance and not a laboratory pass.
"""
import copy
import json
import unittest

from assurance.laboratory import history, observation, records
from assurance.testing.contracts import scientific_hash

FIXTURES = json.loads(r"""
[
  {
    "id": "FX-01-p",
    "group": "T07-01-specimen_identity",
    "control": "positive",
    "consumer": "records.validate_specimen",
    "input": {
      "passport": {
        "alloy": "Ti-6Al-4V",
        "chain_of_custody": [
          "receipt:CC-1"
        ],
        "geometry_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
        "heat_treatment": "HT-1",
        "id": "SP-1",
        "material_lot": "LOT-A",
        "parent_stock": "BAR-7",
        "process_route": "wrought_bar",
        "surface_process": "machined",
        "schema": "specimen.v1"
      },
      "registry": []
    },
    "oracle": {
      "material_state": "identified",
      "outcome": "accepted"
    },
    "input_sha256": "6515da5dff3e7d4b021a1237cb7c0a4d5150b94c40949a6423e8a976c968c057",
    "oracle_sha256": "968a96e85cb874e8709c6d26cc4dc342cff67c7531eee5e014d2f6be68479cf1"
  },
  {
    "id": "FX-01-a",
    "group": "T07-01-specimen_identity",
    "control": "adverse",
    "consumer": "records.validate_specimen",
    "input": {
      "passport": {
        "alloy": "Ti-6Al-4V",
        "chain_of_custody": [
          "receipt:CC-1"
        ],
        "geometry_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
        "heat_treatment": "HT-1",
        "id": "SP-1",
        "material_lot": "LOT-B",
        "parent_stock": "BAR-7",
        "process_route": "wrought_bar",
        "surface_process": "machined"
      },
      "registry": [
        {
          "alloy": "Ti-6Al-4V",
          "chain_of_custody": [
            "receipt:CC-1"
          ],
          "geometry_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
          "heat_treatment": "HT-1",
          "id": "SP-1",
          "material_lot": "LOT-A",
          "parent_stock": "BAR-7",
          "process_route": "wrought_bar",
          "surface_process": "machined"
        }
      ]
    },
    "oracle": {
      "outcome": "refused",
      "reason": "specimen_id_collision"
    },
    "input_sha256": "5be1dbf1f6e596516df015a6c8066646b16be11bcbeaf9eef17d2945abad1c78",
    "oracle_sha256": "184ece81d5734016e014e164f3021411cc19186c9e4691fe53927bf71316c17f"
  },
  {
    "id": "FX-01-a-absent_route",
    "group": "T07-01-specimen_identity",
    "control": "adverse",
    "consumer": "records.validate_specimen",
    "input": {
      "claim": {
        "scope": "process_specific"
      },
      "passport": {
        "alloy": "Ti-6Al-4V",
        "chain_of_custody": [
          "receipt:CC-1"
        ],
        "geometry_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
        "heat_treatment": "HT-1",
        "id": "SP-2",
        "material_lot": "LOT-A",
        "parent_stock": "BAR-7",
        "process_route": {
          "unknown": "not recorded"
        },
        "surface_process": "machined"
      },
      "registry": []
    },
    "oracle": {
      "material_state": "unknown",
      "outcome": "refused",
      "reason": "unknown_applicability"
    },
    "input_sha256": "63861c1bdcba2fa92b290d700f257702c15c6053839072047d90272c0e4415a8",
    "oracle_sha256": "2db6d145ce009d78e5f93ae3d263d67d4b6388312e0fae592d6c28cac884b362"
  },
  {
    "id": "FX-02-p",
    "group": "T07-02-unapproved_transfer",
    "control": "positive",
    "consumer": "records.check_transfer",
    "input": {
      "passport": {
        "alloy": "Ti-6Al-4V",
        "chain_of_custody": [
          "receipt:CC-1"
        ],
        "geometry_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
        "heat_treatment": "HT-1",
        "id": "SP-1",
        "material_lot": "LOT-A",
        "parent_stock": "BAR-7",
        "process_route": "wrought_bar",
        "surface_process": "machined",
        "schema": "specimen.v1"
      },
      "qualification": {
        "passport_sha256": "71bda73d711bd0ed90df3ae4bf2fa65548913768b7e636eabdcf8e8c22a569a4",
        "scope": "machined Ti-6Al-4V wrought_bar",
        "covered_routes": [
          "wrought_bar"
        ],
        "covered_surfaces": [
          "machined"
        ]
      }
    },
    "oracle": {
      "outcome": "accepted"
    },
    "input_sha256": "1ee39b6e06cc87c7cc0f99590d68953ea3e9bb5f0b7efc8a18cdb9889d9fe7e6",
    "oracle_sha256": "e2bbffc39c435ef1866ec771fc8f49e936dacd7ae30c19d98b5fa3c4751b7155"
  },
  {
    "id": "FX-02-a",
    "group": "T07-02-unapproved_transfer",
    "control": "adverse",
    "consumer": "records.check_transfer",
    "input": {
      "passport": {
        "alloy": "Ti-6Al-4V",
        "chain_of_custody": [
          "receipt:CC-1"
        ],
        "geometry_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
        "heat_treatment": "HT-1",
        "id": "SP-1",
        "material_lot": "LOT-A",
        "parent_stock": "BAR-7",
        "process_route": "wrought_bar",
        "surface_process": "shot_peened"
      },
      "qualification": {
        "passport_sha256": "ad916e7c3af764ff356323168ede1e90431c101052e689b8d41e9ddf819ecd90",
        "scope": "machined"
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "qualification_dependency_invalidated"
    },
    "input_sha256": "2f12e68b171e971db954390da8000d20920309301949f4c896a59385e01f6215",
    "oracle_sha256": "34529d1a5e9629d08128cfea901eb4666b70d91403bb3d36da061ae861f67b60"
  },
  {
    "id": "FX-02-a-alloy_name_transfer",
    "group": "T07-02-unapproved_transfer",
    "control": "adverse",
    "consumer": "records.check_transfer",
    "input": {
      "passport": {
        "alloy": "Ti-6Al-4V",
        "chain_of_custody": [
          "receipt:CC-1"
        ],
        "geometry_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
        "heat_treatment": "HT-1",
        "id": "SP-AM",
        "material_lot": "LOT-A",
        "parent_stock": "BAR-7",
        "process_route": "additive_lpbf",
        "surface_process": "machined"
      },
      "qualification": {
        "passport_sha256": "d48bf6e1180a66bdfb9fa40239650bf3ed6aa6ab8fd2a3534a3a3ae2e1e4ae50",
        "scope": "wrought_bar"
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "unapproved_route_transfer"
    },
    "input_sha256": "172ce305ec1ca769bca6a134a1771c145d44a6313f4acae079d47595aef8b2ce",
    "oracle_sha256": "b9bd6a8b2fba40e57f9776711ec4350de2b3181a5d2f83b7b1f599d483e6e1de"
  },
  {
    "id": "FX-03-p",
    "group": "T07-03-history_prefix",
    "control": "positive",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1",
        "schema": "exposure_history.v1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0,
        "schema": "measurement_intervention.v1"
      },
      "raw_bytes_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
    },
    "oracle": {
      "available": true,
      "outcome": "accepted"
    },
    "input_sha256": "0b3d470a80d1c39045a5298fc263bbbc3453353322ab9fb2983aca12470cbd93",
    "oracle_sha256": "ce3c299ad995bade685910bb6a92573d77d7cdc9e14bf497e3aada7a3fcc200a"
  },
  {
    "id": "FX-03-a",
    "group": "T07-03-history_prefix",
    "control": "adverse",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T00:30:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "history_prefix_mismatch"
    },
    "input_sha256": "35f31724e5ba08409b1b565461ccc62210248544d7c8e0a7fd22d79c835ae6e5",
    "oracle_sha256": "daf2cc7eda3f4112739f19fd0b1920a602b3d44111474deae78975808f14749b"
  },
  {
    "id": "FX-04-p",
    "group": "T07-04-clock_segments",
    "control": "positive",
    "consumer": "history.validate_history",
    "input": {
      "events": [
        {
          "end_utc": "2026-01-01T01:00:00Z",
          "id": "E1",
          "kind": "load_block",
          "segment": "S1",
          "start_utc": "2026-01-01T00:00:00Z",
          "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
        },
        {
          "end_utc": "2026-01-01T03:30:00Z",
          "id": "E2",
          "kind": "dwell",
          "segment": "S2",
          "start_utc": "2026-01-01T03:00:00Z",
          "trace_sha256": "4444444444444444444444444444444444444444444444444444444444444444"
        }
      ],
      "id": "HX-1",
      "segments": [
        {
          "clock": "monotonic",
          "id": "S1",
          "origin_utc": "2026-01-01T00:00:00Z",
          "uncertainty_s": 0.5
        },
        {
          "clock": "monotonic",
          "id": "S2",
          "origin_utc": "2026-01-01T03:00:00Z",
          "uncertainty_s": 1.0
        }
      ],
      "specimen": "SP-1",
      "schema": "exposure_history.v1"
    },
    "oracle": {
      "continuous_elapsed": null,
      "outcome": "accepted",
      "segments": [
        "S1",
        "S2"
      ]
    },
    "input_sha256": "ed441012aa521603061efe1f8eab844b904b1c9f70627ba58d0a42e688832254",
    "oracle_sha256": "9f83ac5acbba27f7d79c98176e7e5d7b43e738ee3adf9a1ef17970f1b50b0e23"
  },
  {
    "id": "FX-04-p-overlap_gap",
    "group": "T07-04-clock_segments",
    "control": "positive",
    "consumer": "history.validate_history",
    "input": {
      "events": [
        {
          "end_utc": "2026-01-01T01:00:00Z",
          "id": "E1",
          "kind": "load_block",
          "segment": "S1",
          "start_utc": "2026-01-01T00:00:00Z",
          "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222",
          "interruptions": [],
          "missing_intervals": [
            {
              "end_utc": "2026-01-01T00:40:00Z",
              "reason": "logged_gap",
              "start_utc": "2026-01-01T00:20:00Z"
            }
          ]
        },
        {
          "end_utc": "2026-01-01T01:30:00Z",
          "id": "E2",
          "kind": "dwell",
          "segment": "S2",
          "start_utc": "2026-01-01T00:30:00Z",
          "trace_sha256": "4444444444444444444444444444444444444444444444444444444444444444",
          "interruptions": [],
          "missing_intervals": []
        }
      ],
      "id": "HX-1",
      "segments": [
        {
          "clock": "monotonic",
          "id": "S1",
          "origin_utc": "2026-01-01T00:00:00Z",
          "uncertainty_s": 0.5
        },
        {
          "clock": "monotonic",
          "id": "S2",
          "origin_utc": "2026-01-01T00:30:00Z",
          "uncertainty_s": 1.0
        }
      ],
      "specimen": "SP-1",
      "schema": "exposure_history.v1"
    },
    "oracle": {
      "continuous_elapsed": null,
      "missing_intervals_recorded": true,
      "outcome": "accepted",
      "overlap_recorded": true,
      "segments": [
        "S1",
        "S2"
      ]
    },
    "input_sha256": "897706c8aa81c465bcd11c93190553b216812eecd22853ac0ca32aea4c1c279a",
    "oracle_sha256": "d0dee8ba6e9961268b517b0a976e9346a670c2ee5d7bbad764c7d71b0f1b2b58"
  },
  {
    "id": "FX-04-a",
    "group": "T07-04-clock_segments",
    "control": "adverse",
    "consumer": "history.validate_history",
    "input": {
      "events": [
        {
          "end_utc": "2026-01-01T01:00:00Z",
          "id": "E1",
          "kind": "load_block",
          "segment": "S1",
          "start_utc": "2026-01-01T00:00:00",
          "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
        }
      ],
      "id": "HX-1",
      "segments": [
        {
          "clock": "monotonic",
          "id": "S1",
          "origin_utc": "2026-01-01T00:00:00Z",
          "uncertainty_s": 0.5
        }
      ],
      "specimen": "SP-1"
    },
    "oracle": {
      "outcome": "refused",
      "reason": "timestamp_without_utc_offset"
    },
    "input_sha256": "a1d9e896316e3e35ca8452d12c2cb30a7224a4123618c01b800d4035cdb0232d",
    "oracle_sha256": "250e73ee9d1c5c53ad1f7188a33dfa78ca9bf8797ea0dd9fefd182fe0e6dfcff"
  },
  {
    "id": "FX-04-a-reversed_interval",
    "group": "T07-04-clock_segments",
    "control": "adverse",
    "consumer": "history.validate_history",
    "input": {
      "events": [
        {
          "end_utc": "2025-12-31T23:00:00Z",
          "id": "E1",
          "kind": "load_block",
          "segment": "S1",
          "start_utc": "2026-01-01T00:00:00Z",
          "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
        }
      ],
      "id": "HX-1",
      "segments": [
        {
          "clock": "monotonic",
          "id": "S1",
          "origin_utc": "2026-01-01T00:00:00Z",
          "uncertainty_s": 0.5
        }
      ],
      "specimen": "SP-1"
    },
    "oracle": {
      "outcome": "refused",
      "reason": "impossible_interval_order"
    },
    "input_sha256": "7d327c4b3ecc4800b7f9022b1c09c08b859344af1116b2fff345197767cce329",
    "oracle_sha256": "d288a748e3fc3b3a83e0824ceb6b2f15d7451b10acfd3cc83735cb6b9032bcee"
  },
  {
    "id": "FX-04-a-non_utc",
    "group": "T07-04-clock_segments",
    "control": "adverse",
    "consumer": "history.validate_history",
    "input": {
      "events": [
        {
          "end_utc": "2026-01-01T01:00:00Z",
          "id": "E1",
          "kind": "load_block",
          "segment": "S1",
          "start_utc": "2026-01-01T00:00:00+01:00",
          "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
        }
      ],
      "id": "HX-1",
      "segments": [
        {
          "clock": "monotonic",
          "id": "S1",
          "origin_utc": "2026-01-01T00:00:00Z",
          "uncertainty_s": 0.5
        }
      ],
      "specimen": "SP-1"
    },
    "oracle": {
      "outcome": "refused",
      "reason": "timestamp_offset_not_utc"
    },
    "input_sha256": "e01b82cf72188df3992ed4368a136b6fb8f6e446adbb1478545551a4398b6d6e",
    "oracle_sha256": "d1bde7f9354915d6d38fdedebe07b593e9bb2ee4e524f5a1a173ca28de8dd455"
  },
  {
    "id": "FX-05-p",
    "group": "T07-05-raw_calibration",
    "control": "positive",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1",
        "schema": "exposure_history.v1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0,
        "schema": "measurement_intervention.v1"
      },
      "raw_bytes_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
    },
    "oracle": {
      "available": true,
      "outcome": "accepted"
    },
    "input_sha256": "0b3d470a80d1c39045a5298fc263bbbc3453353322ab9fb2983aca12470cbd93",
    "oracle_sha256": "ce3c299ad995bade685910bb6a92573d77d7cdc9e14bf497e3aada7a3fcc200a"
  },
  {
    "id": "FX-05-a",
    "group": "T07-05-raw_calibration",
    "control": "adverse",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0
      },
      "raw_bytes_sha256": "5555555555555555555555555555555555555555555555555555555555555555"
    },
    "oracle": {
      "outcome": "refused",
      "reason": "raw_acquisition_mismatch"
    },
    "input_sha256": "9fcaa495c1257db797ed6a5a85cb8cd3b9a4885d7203bf0196d8926e7e59035c",
    "oracle_sha256": "c7519494ae354f2a9e05d58de435ff817420579f9ae7489b521968f4a1c11188"
  },
  {
    "id": "FX-05-a-future_calibration",
    "group": "T07-05-raw_calibration",
    "control": "adverse",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2026-01-05T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0
      },
      "raw_bytes_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
    },
    "oracle": {
      "outcome": "refused",
      "reason": "calibration_not_valid_at_acquisition"
    },
    "input_sha256": "74b5843abed562e3f433584658045445798ed39f2d0ed5c00bf4c8407ec074b2",
    "oracle_sha256": "7b5870a30152575d864aa8281443345b7f2c70543ee9d03282df0c92ddac32c7"
  },
  {
    "id": "FX-06-p",
    "group": "T07-06-lab_reduction",
    "control": "positive",
    "consumer": "observation.reduce_trace",
    "input": {
      "trace": {
        "baseline_counts": 2,
        "drift_counts_per_s": 1,
        "gain_n_per_count": 0.5,
        "samples": [
          [
            0,
            2
          ],
          [
            1,
            13
          ],
          [
            2,
            null
          ],
          [
            3,
            25
          ]
        ],
        "termination": "runout_censored",
        "unit_in": "count",
        "unit_out": "newton"
      }
    },
    "oracle": {
      "outcome": "accepted",
      "reduction": {
        "failure_observed": false,
        "n_missing": 1,
        "n_samples": 4,
        "termination": "runout_censored",
        "values_n": [
          0.0,
          5.0,
          null,
          10.0
        ]
      }
    },
    "input_sha256": "d2fe8998f83124d2da06d1add16bc9e0113b3282cf1dd8deda41cb569c11da51",
    "oracle_sha256": "d05e15befe8f416536d79c25743375df31c49040ea7efaaf8660ddbbd77d72ba"
  },
  {
    "id": "FX-06-a",
    "group": "T07-06-lab_reduction",
    "control": "adverse",
    "consumer": "observation.validate_reduction",
    "input": {
      "summary": {
        "failure_observed": false,
        "n_missing": 0,
        "n_samples": 3,
        "termination": "runout_censored",
        "values_n": [
          0.0,
          5.0,
          10.0
        ]
      },
      "trace": {
        "baseline_counts": 2,
        "drift_counts_per_s": 1,
        "gain_n_per_count": 0.5,
        "samples": [
          [
            0,
            2
          ],
          [
            1,
            13
          ],
          [
            2,
            null
          ],
          [
            3,
            25
          ]
        ],
        "termination": "runout_censored",
        "unit_in": "count",
        "unit_out": "newton"
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "reduction_omits_missing"
    },
    "input_sha256": "0717f5d568b23a903bc18453f32ee0c3a7c96d1056d21455531a274df2fe079b",
    "oracle_sha256": "07d347db9a0ebe5d199e5b69b4b204624b52e144ed2fadb3c07346e2d7974a24"
  },
  {
    "id": "FX-06-a-runout_relabel",
    "group": "T07-06-lab_reduction",
    "control": "adverse",
    "consumer": "observation.validate_reduction",
    "input": {
      "summary": {
        "failure_observed": false,
        "n_missing": 1,
        "n_samples": 4,
        "termination": "failure",
        "values_n": [
          0.0,
          5.0,
          null,
          10.0
        ]
      },
      "trace": {
        "baseline_counts": 2,
        "drift_counts_per_s": 1,
        "gain_n_per_count": 0.5,
        "samples": [
          [
            0,
            2
          ],
          [
            1,
            13
          ],
          [
            2,
            null
          ],
          [
            3,
            25
          ]
        ],
        "termination": "runout_censored",
        "unit_in": "count",
        "unit_out": "newton"
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "runout_relabeled_failure"
    },
    "input_sha256": "b5138e67ddb21950d854f7830b718b61ff7e4f354dd61ccdde81c02b30132bc7",
    "oracle_sha256": "b7f2b5183512d7839513c5cb880bb42ea19aa37fe1e2e9fd0a0fb3ca0d583f9c"
  },
  {
    "id": "FX-06-a-observation_unit_count",
    "group": "T07-06-lab_reduction",
    "control": "adverse",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "count",
        "value": 100.0
      },
      "raw_bytes_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
    },
    "oracle": {
      "outcome": "refused",
      "reason": "unknown_unit"
    },
    "input_sha256": "056e76cf2769bd7055ed831c16fac318e783043712d4c0aa5f7b6d71fc78982a",
    "oracle_sha256": "9ae1cb63fd0d4c2576d0f4ff29380a266444d2213b87539386582f0de16d0e58"
  },
  {
    "id": "FX-06-a-observation_unit_alias_N",
    "group": "T07-06-lab_reduction",
    "control": "adverse",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "N",
        "value": 100.0
      },
      "raw_bytes_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
    },
    "oracle": {
      "outcome": "refused",
      "reason": "unknown_unit"
    },
    "input_sha256": "560f6a7352f53a21634efc0b7650b3fe05f936083717e677ad0e336f9e6a2827",
    "oracle_sha256": "9ae1cb63fd0d4c2576d0f4ff29380a266444d2213b87539386582f0de16d0e58"
  },
  {
    "id": "FX-06-p-A02-03_scope",
    "group": "T07-06-lab_reduction",
    "control": "positive",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "scope": "implementation_consistency",
        "target": "reduced_load"
      },
      "lineage": {
        "checked_against": "independent_reducer_oracle",
        "target_role": "derived_reduction"
      }
    },
    "oracle": {
      "outcome": "accepted",
      "scope": "implementation_consistency"
    },
    "input_sha256": "5db6bac53b7f0735fe7a9665b5bb00d0d33229f19f46fdfc0b324912c78c46a4",
    "oracle_sha256": "d97cdc8c85e9ffc6f551c20b7217c842fcbc2375ce35a10af4f15441d38842e2"
  },
  {
    "id": "FX-06-a-A02-03_scope",
    "group": "T07-06-lab_reduction",
    "control": "adverse",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "scope": "physical_validation",
        "target": "reduced_load"
      },
      "lineage": {
        "checked_against": "independent_reducer_oracle",
        "target_role": "derived_reduction"
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "consistency_relabeled_physical_validation"
    },
    "input_sha256": "3f8645d388ce2d43ef75c067b15e0b37f3880a49c958d66ce1756f12401d53bf",
    "oracle_sha256": "c74043ea379214ac25571681b6f4c36010a456a2f461289b439fdf5726201a62"
  },
  {
    "id": "FX-07-p",
    "group": "T07-07-finished_mass",
    "control": "positive",
    "consumer": "records.validate_mass",
    "input": {
      "records": [
        {
          "configuration": "bare",
          "role": "raw_measurement",
          "uncertainty": [
            {
              "amount": 0.05,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "value_g": 70.0
        },
        {
          "configuration": "assembly",
          "role": "raw_measurement",
          "uncertainty": [
            {
              "amount": 0.05,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "value_g": 78.5
        }
      ],
      "requested": "assembly"
    },
    "oracle": {
      "configuration": "assembly",
      "outcome": "accepted",
      "value_g": 78.5
    },
    "input_sha256": "a18360d3a11198e4a9dd054e0db5811be1bbed3c56026b6e2aa42b8ff04a4756",
    "oracle_sha256": "c9a6985a025c5a722139babf764fe27565e48312c03dc9aa46028c008d65de8e"
  },
  {
    "id": "FX-07-a",
    "group": "T07-07-finished_mass",
    "control": "adverse",
    "consumer": "records.validate_mass",
    "input": {
      "records": [
        {
          "configuration": "bare",
          "role": "raw_measurement",
          "uncertainty": [
            {
              "amount": 0.05,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "value_g": 70.0
        },
        {
          "configuration": "assembly",
          "role": "derived_bare_plus_nominal_finish",
          "uncertainty": [],
          "value_g": 78.5
        }
      ],
      "requested": "assembly"
    },
    "oracle": {
      "outcome": "refused",
      "reason": "unmeasured_configuration_substitution"
    },
    "input_sha256": "8230faf7f832bcf654bbeb4068a6004f7344ca3a288d1c50f22c6c31c3c151b2",
    "oracle_sha256": "b5ef77321b966a5567fe9de361eb8e6b95cf9d7ce001a6fc2ee61f68b2b78b1d"
  },
  {
    "id": "FX-08-p",
    "group": "T07-08-frame_unit",
    "control": "positive",
    "consumer": "observation.validate_observation_support",
    "input": {
      "claim": {
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "unit": "megapascal"
      },
      "observation": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0,
        "schema": "measurement_intervention.v1"
      }
    },
    "oracle": {
      "outcome": "accepted"
    },
    "input_sha256": "94dc7cd2a7e0bc4eb072435d8583b4368c916978779195d6568197d947ab61f3",
    "oracle_sha256": "e2bbffc39c435ef1866ec771fc8f49e936dacd7ae30c19d98b5fa3c4751b7155"
  },
  {
    "id": "FX-08-a",
    "group": "T07-08-frame_unit",
    "control": "adverse",
    "consumer": "observation.validate_observation_support",
    "input": {
      "claim": {
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "unit": "megapascal"
      },
      "observation": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "left",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "frame_handedness_mismatch"
    },
    "input_sha256": "2e9dd46a7dc3bb04f2af404afa199e7cfd91ffdac59cf80892a28d0876916fb2",
    "oracle_sha256": "22b68df46cba2d1f7eb6010f022c5d6c088f20381f1c926e6131f5259def0270"
  },
  {
    "id": "FX-08-p-A03-01_support",
    "group": "T07-08-frame_unit",
    "control": "positive",
    "consumer": "observation.validate_observation_support",
    "input": {
      "claim": {
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "unit": "megapascal"
      },
      "observation": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0,
        "schema": "measurement_intervention.v1"
      }
    },
    "oracle": {
      "outcome": "accepted"
    },
    "input_sha256": "94dc7cd2a7e0bc4eb072435d8583b4368c916978779195d6568197d947ab61f3",
    "oracle_sha256": "e2bbffc39c435ef1866ec771fc8f49e936dacd7ae30c19d98b5fa3c4751b7155"
  },
  {
    "id": "FX-08-a-A03-01_support",
    "group": "T07-08-frame_unit",
    "control": "adverse",
    "consumer": "observation.validate_observation_support",
    "input": {
      "claim": {
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "support": {
          "kind": "diffraction_gauge_volume",
          "reference_state": "d0_unstressed_powder",
          "size_mm": 3.0
        },
        "unit": "megapascal"
      },
      "observation": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "support_or_reference_mismatch"
    },
    "input_sha256": "8acdb8b7c74a1e7ed22f88d6fb689d7f31f1ed2a99f40752affc8d55220b0597",
    "oracle_sha256": "34e68807ee8bd9e4eee4238a09dee4c4a78ee81bd7958c1657894177a3c1c286"
  },
  {
    "id": "FX-09-p",
    "group": "T07-09-censored_zero",
    "control": "positive",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1",
        "schema": "exposure_history.v1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": {
          "basis": "limit_of_detection",
          "limit": 0.5,
          "type": "left"
        },
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": null,
        "schema": "measurement_intervention.v1"
      },
      "raw_bytes_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
    },
    "oracle": {
      "censoring": "left",
      "limit": 0.5,
      "outcome": "accepted",
      "value": null
    },
    "input_sha256": "5aaf4d63a8825a775b0aa53ddf1ddda9a5bb5db5dfd14a6df9ded840a28167d1",
    "oracle_sha256": "fc8cc4b2ab53689124f780feb95c98ccc773f424e749dc7e3a302a36dee11ac3"
  },
  {
    "id": "FX-09-p-measured_zero",
    "group": "T07-09-censored_zero",
    "control": "positive",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1",
        "schema": "exposure_history.v1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 0.0,
        "schema": "measurement_intervention.v1"
      },
      "raw_bytes_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
    },
    "oracle": {
      "censoring": null,
      "outcome": "accepted",
      "value": 0.0
    },
    "input_sha256": "989c70b28ae81836d8d69974a0bf0971c4c9c19c3e0ff36701500403da341a10",
    "oracle_sha256": "ed5c9c1d5532e6dc2abbb70074e705f7016896f0d69fa01fbac806fbf576ced8"
  },
  {
    "id": "FX-09-a",
    "group": "T07-09-censored_zero",
    "control": "adverse",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": {
          "basis": "limit_of_detection",
          "limit": 0.5,
          "type": "left"
        },
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 0.0
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "censored_value_not_null"
    },
    "input_sha256": "50c63d0c89f898d9a0ebe149ac25a537b0cd1fa1fdaeb50dac56d98892f4fbfd",
    "oracle_sha256": "fd48b3a6f6b5103a6cb3067cb7d26bc96a4c874eb330db6d054908900d482357"
  },
  {
    "id": "FX-09-p-A03-03_components",
    "group": "T07-09-censored_zero",
    "control": "positive",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1",
        "schema": "exposure_history.v1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "components": {
          "xx": 100.0,
          "xy": {
            "unknown": "not measured"
          },
          "yy": 20.0
        },
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": null,
        "schema": "measurement_intervention.v1"
      },
      "raw_bytes_sha256": "3333333333333333333333333333333333333333333333333333333333333333"
    },
    "oracle": {
      "components_unknown": [
        "xy"
      ],
      "outcome": "accepted"
    },
    "input_sha256": "609ffc65f70ae4d363b7845660d63547709d7d1997e4bb131b601f373770b70a",
    "oracle_sha256": "479d08000234f969dde465b755456300f1b13b1f98a66eb745e53366e05014f9"
  },
  {
    "id": "FX-09-a-A03-03_components",
    "group": "T07-09-censored_zero",
    "control": "adverse",
    "consumer": "observation.bind_observation",
    "input": {
      "history": {
        "events": [
          {
            "end_utc": "2026-01-01T01:00:00Z",
            "id": "E1",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T00:00:00Z",
            "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
          }
        ],
        "id": "HX-1",
        "segments": [
          {
            "clock": "monotonic",
            "id": "S1",
            "origin_utc": "2026-01-01T00:00:00Z",
            "uncertainty_s": 0.5
          }
        ],
        "specimen": "SP-1"
      },
      "measurement": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "component_roles": {
          "xy": "measured"
        },
        "components": {
          "xx": 100.0,
          "xy": 0.0,
          "yy": 20.0
        },
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "strain_gauge",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "gauge_area",
          "reference_state": "unloaded_0",
          "size_mm": 3.0
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": null
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "inferred_component_labeled_measured"
    },
    "input_sha256": "478ba6d4e689c6989d16346a791b1781729d518b7e30904a9a39ef4ff3bb3563",
    "oracle_sha256": "ecb871c4de2cbf03cf02bc169614bd55a13351cdb5dc2858ebd538aa1ec74021"
  },
  {
    "id": "FX-10-p",
    "group": "T07-10-chemistry_scope",
    "control": "positive",
    "consumer": "observation.validate_observation_support",
    "input": {
      "claim": {
        "scope": "bulk_composition"
      },
      "observation": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "bulk_icp",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "bulk",
          "reference_state": "as_received",
          "size_mm": null
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0,
        "schema": "measurement_intervention.v1"
      }
    },
    "oracle": {
      "outcome": "accepted"
    },
    "input_sha256": "0545eab3105c5c70e4072ee86b2f049cd0ba6e62f8c90f9e2e845d8a4dc94e2b",
    "oracle_sha256": "e2bbffc39c435ef1866ec771fc8f49e936dacd7ae30c19d98b5fa3c4751b7155"
  },
  {
    "id": "FX-10-a",
    "group": "T07-10-chemistry_scope",
    "control": "adverse",
    "consumer": "observation.validate_observation_support",
    "input": {
      "claim": {
        "scope": "local_organization"
      },
      "observation": {
        "calibration": {
          "id": "CAL-1",
          "valid_from_utc": "2025-12-01T00:00:00Z",
          "valid_to_utc": "2026-02-01T00:00:00Z"
        },
        "censoring": null,
        "experimental_unit": {
          "lot": "LOT-A",
          "operator": "OP-1",
          "session": "SES-1",
          "specimen": "SP-1"
        },
        "frame": {
          "axes": [
            "x",
            "y",
            "z"
          ],
          "handedness": "right",
          "id": "F-spec"
        },
        "history_prefix_events": [
          "E1"
        ],
        "id": "M-1",
        "method": "bulk_icp",
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
        "role": "raw_measurement",
        "specimen": "SP-1",
        "support": {
          "kind": "bulk",
          "reference_state": "as_received",
          "size_mm": null
        },
        "time_utc": "2026-01-01T02:00:00Z",
        "uncertainty": [
          {
            "amount": 2.0,
            "coverage_interpretation": "standard_uncertainty",
            "dependence": "independent_within_session",
            "domain": "fixture",
            "kind": "measurement",
            "method": "synthetic_declared"
          }
        ],
        "unit": "megapascal",
        "value": 100.0
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "scope_exceeds_support"
    },
    "input_sha256": "1694ea590c81ef10c7ce5486c657f7b3d0122444e44f93db30734f6b601f4777",
    "oracle_sha256": "473102381d6b0fbb5daddcdb5774f6042a276b944457a5cbfd1f9f14f711103f"
  },
  {
    "id": "FX-10-a-prep_hydrogen",
    "group": "T07-10-chemistry_scope",
    "control": "adverse",
    "consumer": "observation.validate_intervention",
    "input": {
      "claim": {
        "scope": "intrinsic",
        "species": "H"
      },
      "intervention": {
        "id": "PREP-1",
        "kind": "electropolish",
        "may_introduce": [
          "H"
        ]
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "preparation_induced_not_intrinsic"
    },
    "input_sha256": "d91a7767bc147fad4722a6ad26c43e08a618371046f2f58d6cebb459d57b3b41",
    "oracle_sha256": "d13c8338dbdfb1c79507b653f667d4bf5c48a446bf1e15d6c8c5e5173396a06a"
  },
  {
    "id": "FX-11-p",
    "group": "T07-11-measurement_lineage",
    "control": "positive",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "independent_observations": 2
      },
      "observations": [
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-1",
          "method": "strain_gauge",
          "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0,
          "schema": "measurement_intervention.v1"
        },
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-2",
            "specimen": "SP-3"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-3",
          "method": "strain_gauge",
          "raw_sha256": "6666666666666666666666666666666666666666666666666666666666666666",
          "role": "raw_measurement",
          "specimen": "SP-3",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0,
          "schema": "measurement_intervention.v1"
        }
      ]
    },
    "oracle": {
      "independent_units": 2,
      "outcome": "accepted"
    },
    "input_sha256": "39435549acf876a29fefedd6da4e1d5e28959fa7e8d411a2218bbf1d11f3ef91",
    "oracle_sha256": "67ca833df0432498e05f56eb64e15ec962480aeb1decc96b77cfda10bf40dab8"
  },
  {
    "id": "FX-11-a-specimen_mismatch",
    "group": "T07-11-measurement_lineage",
    "control": "adverse",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "independent_observations": 2
      },
      "observations": [
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-1",
          "method": "strain_gauge",
          "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0
        },
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-2",
            "specimen": "SP-3"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-3",
          "method": "strain_gauge",
          "raw_sha256": "6666666666666666666666666666666666666666666666666666666666666666",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0
        }
      ]
    },
    "oracle": {
      "outcome": "refused",
      "reason": "specimen_field_disagrees_with_experimental_unit"
    },
    "input_sha256": "c14f3270a920756f9876f1b8c4b64b007119e8a77f2c372cb96f0f28696f3ab6",
    "oracle_sha256": "23bf8f2be3909ce67d072e6d298405e96f8f70487fc448dd3d8b05c1caef2612"
  },
  {
    "id": "FX-11-a",
    "group": "T07-11-measurement_lineage",
    "control": "adverse",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "independent_observations": 2
      },
      "observations": [
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-1",
          "method": "strain_gauge",
          "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0
        },
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-2",
          "method": "strain_gauge",
          "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0
        }
      ]
    },
    "oracle": {
      "outcome": "refused",
      "reason": "duplicate_acquisition_counted_independent"
    },
    "input_sha256": "975c4f393f5c815c8e14eb614726a5aa690dc5f22d4b8bef76cb260b6d343cd7",
    "oracle_sha256": "422512af60b60f07b062ff80ce5aa3f6fe6462366a0c64d5afbcef2ccef2e75b"
  },
  {
    "id": "FX-11-a-missing_grouping",
    "group": "T07-11-measurement_lineage",
    "control": "adverse",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "independent_observations": 2
      },
      "observations": [
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-1",
          "method": "strain_gauge",
          "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0
        },
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": {
              "unknown": "not logged"
            },
            "session": {
              "unknown": "not logged"
            },
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-4",
          "method": "strain_gauge",
          "raw_sha256": "7777777777777777777777777777777777777777777777777777777777777777",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0
        }
      ]
    },
    "oracle": {
      "grouping": "unknown",
      "outcome": "refused",
      "reason": "grouping_unknown_not_independent"
    },
    "input_sha256": "84df5eb31bead9f67581540ae272e2823547edb76275f1388a67ee73c52e0562",
    "oracle_sha256": "99f21f1fe6cf18312aefe6ce2ddb72c28cb05036df9e706eef1d1e785564d795"
  },
  {
    "id": "FX-11-p-A02-02_derived",
    "group": "T07-11-measurement_lineage",
    "control": "positive",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "independent_observations": 1
      },
      "observations": [
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-1",
          "method": "strain_gauge",
          "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0,
          "schema": "measurement_intervention.v1"
        },
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-5",
          "method": "strain_gauge",
          "parents": [
            "M-1"
          ],
          "raw_sha256": "8888888888888888888888888888888888888888888888888888888888888888",
          "role": "derived",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0,
          "schema": "measurement_intervention.v1"
        }
      ]
    },
    "oracle": {
      "independent_units": 1,
      "outcome": "accepted",
      "parent_links": [
        "M-1"
      ]
    },
    "input_sha256": "494e9355121ae32201d73adb322b02d07ea1bcfa405ae739795a76ff2ce1af66",
    "oracle_sha256": "6505dac5c27037454ec510a8583048b925a27ebfd1dfccddbbcaf3dffdfd5022"
  },
  {
    "id": "FX-11-a-A02-02_rehash",
    "group": "T07-11-measurement_lineage",
    "control": "adverse",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "independent_observations": 2
      },
      "observations": [
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-1",
          "method": "strain_gauge",
          "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0
        },
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-5",
          "method": "strain_gauge",
          "parents": [
            "M-1"
          ],
          "raw_sha256": "8888888888888888888888888888888888888888888888888888888888888888",
          "role": "derived",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0
        }
      ]
    },
    "oracle": {
      "outcome": "refused",
      "reason": "derived_copy_counted_independent"
    },
    "input_sha256": "d58252f9c7376bc6715870b88db5bc924b26c0e9c8eeabdeba237ee4d8d86383",
    "oracle_sha256": "0fad8b07f7b76bf4f60705b8c0aae1942e2d6407accee937acb43a802b506d6c"
  },
  {
    "id": "FX-12-p",
    "group": "T07-12-interpretation_unknown",
    "control": "positive",
    "consumer": "observation.interpret",
    "input": {
      "claim": {
        "diagnostic": "change_vs_baseline",
        "history": {
          "schema": "exposure_history.v1",
          "id": "HX-1",
          "specimen": "SP-1",
          "segments": [
            {
              "clock": "monotonic",
              "id": "S1",
              "origin_utc": "2026-01-01T00:00:00Z",
              "uncertainty_s": 0.5
            }
          ],
          "events": [
            {
              "end_utc": "2026-01-01T01:00:00Z",
              "id": "E1",
              "kind": "load_block",
              "segment": "S1",
              "start_utc": "2026-01-01T00:00:00Z",
              "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222"
            }
          ]
        },
        "raw_bytes_by_id": {
          "M-1": "3333333333333333333333333333333333333333333333333333333333333333"
        }
      },
      "observations": [
        {
          "calibration": {
            "id": "CAL-1",
            "valid_from_utc": "2025-12-01T00:00:00Z",
            "valid_to_utc": "2026-02-01T00:00:00Z"
          },
          "censoring": null,
          "experimental_unit": {
            "lot": "LOT-A",
            "operator": "OP-1",
            "session": "SES-1",
            "specimen": "SP-1"
          },
          "frame": {
            "axes": [
              "x",
              "y",
              "z"
            ],
            "handedness": "right",
            "id": "F-spec"
          },
          "history_prefix_events": [
            "E1"
          ],
          "id": "M-1",
          "method": "strain_gauge",
          "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
          "role": "raw_measurement",
          "specimen": "SP-1",
          "support": {
            "kind": "gauge_area",
            "reference_state": "unloaded_0",
            "size_mm": 3.0
          },
          "time_utc": "2026-01-01T02:00:00Z",
          "uncertainty": [
            {
              "amount": 2.0,
              "coverage_interpretation": "standard_uncertainty",
              "dependence": "independent_within_session",
              "domain": "fixture",
              "kind": "measurement",
              "method": "synthetic_declared"
            }
          ],
          "unit": "megapascal",
          "value": 100.0,
          "schema": "measurement_intervention.v1"
        }
      ]
    },
    "oracle": {
      "finding": "supported_within_scope",
      "outcome": "accepted"
    },
    "input_sha256": "b0bbd9027ad9b4513658e4df52534741265d9526616729623ab1c219e96270f3",
    "oracle_sha256": "12870b8eb14cb79a599bf329d6fc07c121320d6a5fdfa70e09e901ec48ddbe50"
  },
  {
    "id": "FX-12-a",
    "group": "T07-12-interpretation_unknown",
    "control": "adverse",
    "consumer": "observation.interpret",
    "input": {
      "claim": {
        "asserted": "healthy",
        "diagnostic": "change_vs_baseline"
      },
      "observations": []
    },
    "oracle": {
      "diagnostic": "unable_to_determine",
      "finding": "inconclusive",
      "outcome": "refused",
      "reason": "absent_measurement_cannot_be_healthy"
    },
    "input_sha256": "c42cbc65eb785ac1c70897afab6809a64929fb28d929be8cfc9e36abbf60177a",
    "oracle_sha256": "2681ed7db4b1780e3443e867da4a0ba240b01d1aed1ba144dbf52bf497fdc06c"
  },
  {
    "id": "FX-12-p-A03-02_ambiguity",
    "group": "T07-12-interpretation_unknown",
    "control": "positive",
    "consumer": "observation.interpret",
    "input": {
      "alternatives": [
        [
          1,
          0
        ],
        [
          0,
          1
        ]
      ],
      "claim": {
        "unique": true
      },
      "observed": [
        1,
        1
      ],
      "operator_rows": [
        [
          1,
          1
        ],
        [
          1,
          0
        ]
      ]
    },
    "oracle": {
      "identified": [
        [
          1,
          0
        ]
      ],
      "outcome": "accepted"
    },
    "input_sha256": "36bedc11bb80b923ed9b2f4727fc085c5b89d186c09663b744c668578b260dfd",
    "oracle_sha256": "f5f1531abdfa89a2d521186f6b31b06854056e8cb0263a39fa2dbdab92673ad6"
  },
  {
    "id": "FX-12-a-A03-02_ambiguity",
    "group": "T07-12-interpretation_unknown",
    "control": "adverse",
    "consumer": "observation.interpret",
    "input": {
      "alternatives": [
        [
          1,
          0
        ],
        [
          0,
          1
        ]
      ],
      "claim": {
        "unique": true
      },
      "observed": [
        1
      ],
      "operator_rows": [
        [
          1,
          1
        ]
      ]
    },
    "oracle": {
      "alternatives": [
        [
          1,
          0
        ],
        [
          0,
          1
        ]
      ],
      "finding": "inconclusive",
      "outcome": "refused",
      "reason": "not_identified"
    },
    "input_sha256": "49b069bcf68adc9a181c06ac5a7acd60eb93f08eef2a4a04538d553bba5590a2",
    "oracle_sha256": "f0451fae8b2591499a5b5f99b5a1a20103e046699c27fe6107ae3dc42e7f30f7"
  },
  {
    "id": "FX-12-p-A02-01_withheld",
    "group": "T07-12-interpretation_unknown",
    "control": "positive",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "scope": "independent_validation",
        "target": "T1"
      },
      "lineage": {
        "fit_constraints": [
          "C1"
        ],
        "target": "T1",
        "target_role": "withheld"
      }
    },
    "oracle": {
      "outcome": "accepted",
      "scope": "independent_validation_candidate"
    },
    "input_sha256": "658713e77cf5d2ef384a0aaef63f67a98c70bec48e0c5aafcf8a9d3bff682ae3",
    "oracle_sha256": "869d8d09c74ff0c1000de1ee1e780a1154877c746416f0e8b01ac40e904bac94"
  },
  {
    "id": "FX-12-a-A02-01_withheld",
    "group": "T07-12-interpretation_unknown",
    "control": "adverse",
    "consumer": "records.validate_validation_lineage",
    "input": {
      "claim": {
        "scope": "independent_validation",
        "target": "C1"
      },
      "lineage": {
        "fit_constraints": [
          "C1"
        ],
        "target": "C1",
        "target_role": "imposed_constraint"
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "imposed_constraint_not_validation",
      "scope": "implementation_consistency"
    },
    "input_sha256": "1a20c24568077716536edc46238aac3232d617c094852c6765402c86bc13d729",
    "oracle_sha256": "8712a1110556e0d6c70a26b358a3fdf004b6ee85d2939e744f2244d426266d45"
  },
  {
    "id": "FX-13-p",
    "group": "T07-13-historical_adapter",
    "control": "positive",
    "consumer": "records.load_historical",
    "input": {
      "record": {
        "id": "LEGACY-7",
        "schema": 0,
        "specimen": "SP-OLD",
        "unit": "megapascal",
        "value": 812.0
      }
    },
    "oracle": {
      "claim_eligible": false,
      "outcome": "accepted",
      "scope": "historical_display"
    },
    "input_sha256": "bb88a6d980192896fdde42e6cd5496f2fd734117bacb4ca82ce82420382e7caf",
    "oracle_sha256": "7377c401e61429b2972c63e8cc10055921b4a74374a42d4b07b49b4944811ab6"
  },
  {
    "id": "FX-13-a",
    "group": "T07-13-historical_adapter",
    "control": "adverse",
    "consumer": "records.load_historical",
    "input": {
      "claim": {
        "scope": "process_specific_qualification"
      },
      "record": {
        "id": "LEGACY-7",
        "schema": 0,
        "specimen": "SP-OLD",
        "unit": "megapascal",
        "value": 812.0
      }
    },
    "oracle": {
      "outcome": "refused",
      "reason": "historical_record_cannot_qualify_new_claim"
    },
    "input_sha256": "f543cec4380c58e50928fdaaa73d10b8566e9c8ed19a3aeb7765d1964c7bff2f",
    "oracle_sha256": "99db88c1f5a52f68d9d2c02d6aed385087b1c382909f3d24c610bfbed2703882"
  }
]
""")


def _run(fixture):
    payload = fixture["input"]
    consumer = fixture["consumer"]
    if consumer == "records.validate_specimen":
        return records.validate_specimen(
            payload["passport"], payload["registry"], payload.get("claim"))
    if consumer == "records.check_transfer":
        return records.check_transfer(payload["qualification"], payload["passport"])
    if consumer == "history.validate_history":
        return history.validate_history(payload)
    if consumer == "observation.bind_observation":
        return observation.bind_observation(
            payload["measurement"], payload["history"], payload.get("raw_bytes_sha256"))
    if consumer == "observation.reduce_trace":
        return observation.reduce_trace(payload["trace"])
    if consumer == "observation.validate_reduction":
        return observation.validate_reduction(payload["summary"], payload["trace"])
    if consumer == "records.validate_mass":
        return records.validate_mass(payload["records"], payload["requested"])
    if consumer == "observation.validate_observation_support":
        return observation.validate_observation_support(
            payload["observation"], payload["claim"])
    if consumer == "observation.validate_intervention":
        return observation.validate_intervention(
            payload["intervention"], payload["claim"])
    if consumer == "records.validate_validation_lineage":
        return records.validate_validation_lineage(
            payload["claim"],
            lineage=payload.get("lineage"),
            observations=payload.get("observations"),
        )
    if consumer == "observation.interpret":
        return observation.interpret(
            observations=payload.get("observations"),
            claim=payload.get("claim"),
            operator_rows=payload.get("operator_rows"),
            observed=payload.get("observed"),
            alternatives=payload.get("alternatives"),
        )
    if consumer == "records.load_historical":
        return records.load_historical(payload["record"], payload.get("claim"))
    raise AssertionError(consumer)


def _bind(fixture):
    def test(self):
        self.assertEqual(
            scientific_hash(fixture["input"]), fixture["input_sha256"], fixture["id"])
        self.assertEqual(
            scientific_hash(fixture["oracle"]), fixture["oracle_sha256"], fixture["id"])
        self.assertEqual(_run(fixture), fixture["oracle"], fixture["id"])
    test.__doc__ = fixture["id"]
    return test


class FrozenT07Controls(unittest.TestCase):
    def test_inventory_is_the_fifty_one_frozen_fixtures(self):
        self.assertEqual([fixture["id"] for fixture in FIXTURES], [
            "FX-01-p", "FX-01-a", "FX-01-a-absent_route",
            "FX-02-p", "FX-02-a", "FX-02-a-alloy_name_transfer",
            "FX-03-p", "FX-03-a",
            "FX-04-p", "FX-04-p-overlap_gap", "FX-04-a", "FX-04-a-reversed_interval", "FX-04-a-non_utc",
            "FX-05-p", "FX-05-a", "FX-05-a-future_calibration",
            "FX-06-p", "FX-06-a", "FX-06-a-runout_relabel",
            "FX-06-a-observation_unit_count", "FX-06-a-observation_unit_alias_N",
            "FX-06-p-A02-03_scope", "FX-06-a-A02-03_scope",
            "FX-07-p", "FX-07-a",
            "FX-08-p", "FX-08-a", "FX-08-p-A03-01_support", "FX-08-a-A03-01_support",
            "FX-09-p", "FX-09-p-measured_zero", "FX-09-a",
            "FX-09-p-A03-03_components", "FX-09-a-A03-03_components",
            "FX-10-p", "FX-10-a", "FX-10-a-prep_hydrogen",
            "FX-11-p", "FX-11-a-specimen_mismatch", "FX-11-a", "FX-11-a-missing_grouping",
            "FX-11-p-A02-02_derived", "FX-11-a-A02-02_rehash",
            "FX-12-p", "FX-12-a", "FX-12-p-A03-02_ambiguity", "FX-12-a-A03-02_ambiguity",
            "FX-12-p-A02-01_withheld", "FX-12-a-A02-01_withheld",
            "FX-13-p", "FX-13-a",
        ])

    def test_thirteen_groups_keep_a_positive_and_an_adverse(self):
        grouped = {}
        for fixture in FIXTURES:
            grouped.setdefault(fixture["group"], set()).add(fixture["control"])
        self.assertEqual(len(grouped), 13)
        for group, controls in grouped.items():
            self.assertIn("positive", controls, group)
            self.assertIn("adverse", controls, group)

    def test_plus_00_00_is_the_other_utc_form(self):
        history_record = {
            "schema": "exposure_history.v1",
            "id": "HX-UTC",
            "specimen": "SP-1",
            "segments": [{
                "clock": "monotonic",
                "id": "S1",
                "origin_utc": "2026-01-01T00:00:00+00:00",
                "uncertainty_s": 0.5,
            }],
            "events": [{
                "end_utc": "2026-01-01T01:00:00+00:00",
                "id": "E1",
                "kind": "load_block",
                "segment": "S1",
                "start_utc": "2026-01-01T00:00:00+00:00",
                "trace_sha256": "2222222222222222222222222222222222222222222222222222222222222222",
            }],
        }
        actual = history.validate_history(history_record)
        self.assertEqual(actual["outcome"], "accepted")
        self.assertIsNone(actual["continuous_elapsed"])
        self.assertEqual(actual["segments"], ["S1"])


for _fixture in FIXTURES:
    _name = "test_" + _fixture["id"].replace("-", "_")
    setattr(FrozenT07Controls, _name, _bind(_fixture))


def _fixture(fixture_id):
    for fixture in FIXTURES:
        if fixture["id"] == fixture_id:
            return copy.deepcopy(fixture["input"])
    raise AssertionError(fixture_id)


class SameConsumerContractControls(unittest.TestCase):
    """Healthy and adverse inputs call the same function on disposable copies."""

    def test_validate_reduction_accepts_only_the_independent_trace(self):
        healthy = _fixture("FX-06-a-runout_relabel")
        healthy["summary"]["termination"] = "runout_censored"
        accepted = observation.validate_reduction(healthy["summary"], healthy["trace"])
        self.assertEqual(accepted["outcome"], "accepted")
        self.assertEqual(accepted["reduction"]["values_n"], [0.0, 5.0, None, 10.0])
        wrong_value = _fixture("FX-06-a-runout_relabel")
        wrong_value["summary"]["termination"] = "runout_censored"
        wrong_value["summary"]["values_n"][3] = 999.0
        refused = observation.validate_reduction(wrong_value["summary"], wrong_value["trace"])
        self.assertEqual(refused["reason"], "reduction_mismatch")
        changed_raw = _fixture("FX-06-a-runout_relabel")
        changed_raw["summary"]["termination"] = "runout_censored"
        changed_raw["trace"]["samples"][3][1] = 99
        raw_refused = observation.validate_reduction(
            changed_raw["summary"], changed_raw["trace"])
        self.assertEqual(raw_refused["reason"], "reduction_mismatch")
        changed_time = _fixture("FX-06-a-runout_relabel")
        changed_time["summary"]["termination"] = "runout_censored"
        changed_time["trace"]["samples"][3][0] = 4
        time_refused = observation.validate_reduction(
            changed_time["summary"], changed_time["trace"])
        self.assertEqual(time_refused["reason"], "reduction_mismatch")

    def test_interpret_requires_a_validated_observation(self):
        healthy = _fixture("FX-12-p")
        accepted = observation.interpret(
            observations=healthy["observations"], claim=healthy["claim"])
        self.assertEqual(accepted, {
            "finding": "supported_within_scope",
            "outcome": "accepted",
        })
        invalid = _fixture("FX-12-p")
        invalid["observations"][0]["unit"] = "N"
        refused = observation.interpret(
            observations=invalid["observations"], claim={"diagnostic": "healthy"})
        self.assertEqual(refused["diagnostic"], "unable_to_determine")
        self.assertNotIn("identified", refused)
        self.assertNotEqual(refused.get("finding"), "supported_within_scope")
        empty_rows = observation.interpret(
            operator_rows=[], observed=[], alternatives=[[1, 0]])
        self.assertNotIn("identified", empty_rows)
        self.assertEqual(empty_rows["reason"], "not_identified")
        malformed = observation.interpret(
            operator_rows=[[1, 1]], observed=[1], alternatives=[[1, 0], [0, 1, 0]])
        self.assertNotIn("identified", malformed)
        self.assertEqual(malformed["reason"], "alternative_dimension_mismatch")

    def test_raw_identity_is_required_at_the_caller_boundary(self):
        healthy = _fixture("FX-05-p")
        accepted = observation.bind_observation(
            healthy["measurement"], healthy["history"], healthy["raw_bytes_sha256"])
        self.assertEqual(accepted, {"available": True, "outcome": "accepted"})
        omitted = observation.bind_observation(
            healthy["measurement"], healthy["history"], None)
        self.assertEqual(omitted["reason"], "raw_identity_unavailable")
        mismatch = _fixture("FX-05-p")
        refused = observation.bind_observation(
            mismatch["measurement"], mismatch["history"], "ab" * 32)
        self.assertEqual(refused["reason"], "raw_acquisition_mismatch")
        missing = _fixture("FX-05-p")
        del missing["measurement"]["raw_sha256"]
        unavailable = observation.bind_observation(
            missing["measurement"], missing["history"], None)
        self.assertEqual(unavailable["reason"], "raw_identity_unavailable")

    def test_one_specimen_over_two_sessions_is_one_unit(self):
        paired = _fixture("FX-11-p")
        paired["observations"][1]["specimen"] = "SP-1"
        paired["observations"][1]["experimental_unit"]["specimen"] = "SP-1"
        paired["claim"]["independent_observations"] = 1
        accepted = records.validate_validation_lineage(
            paired["claim"], observations=paired["observations"])
        self.assertEqual(accepted, {"independent_units": 1, "outcome": "accepted"})
        overclaimed = _fixture("FX-11-p")
        overclaimed["observations"][1]["specimen"] = "SP-1"
        overclaimed["observations"][1]["experimental_unit"]["specimen"] = "SP-1"
        refused = records.validate_validation_lineage(
            overclaimed["claim"], observations=overclaimed["observations"])
        self.assertEqual(refused["reason"], "duplicate_acquisition_counted_independent")
        orphan = _fixture("FX-11-p-A02-02_derived")
        orphan["observations"][1]["parents"] = ["M-404"]
        orphan_result = records.validate_validation_lineage(
            orphan["claim"], observations=orphan["observations"])
        self.assertEqual(orphan_result["reason"], "orphan_parent")

    def test_unknown_support_cannot_substantiate_a_local_claim(self):
        present = _fixture("FX-08-p")["observation"]
        accepted = observation.validate_observation_support(
            present, {"scope": "local_organization"})
        self.assertEqual(accepted, {"outcome": "accepted"})
        missing = _fixture("FX-10-p")["observation"]
        del missing["support"]
        refused = observation.validate_observation_support(
            missing, {"scope": "local_organization"})
        self.assertEqual(refused["reason"], "scope_exceeds_support")
        self.assertEqual(refused["diagnostic"], "unable_to_determine")
        permuted = _fixture("FX-08-p")
        permuted["observation"]["frame"]["axes"] = ["z", "x", "y"]
        axes = observation.validate_observation_support(
            permuted["observation"], permuted["claim"])
        self.assertEqual(axes["reason"], "frame_axes_mismatch")
        unit = _fixture("FX-08-p")
        unit["observation"]["unit"] = "gram"
        unit_result = observation.validate_observation_support(
            unit["observation"], unit["claim"])
        self.assertEqual(unit_result["reason"], "unit_mismatch")

    def test_measured_zero_is_not_a_value_keyed_fill(self):
        measured = _fixture("FX-09-p-A03-03_components")
        measured["measurement"]["components"] = {
            "xx": 0.0,
            "xy": {"unknown": "not measured"},
            "yy": 20.0,
        }
        measured["measurement"]["component_roles"] = {"xx": "measured", "yy": "measured"}
        accepted = observation.bind_observation(
            measured["measurement"], measured["history"], measured.get("raw_bytes_sha256"))
        self.assertEqual(accepted["outcome"], "accepted")
        self.assertEqual(accepted["components_unknown"], ["xy"])
        filled = _fixture("FX-09-a-A03-03_components")
        filled["measurement"]["components"]["xy"] = 7.5
        refused = observation.bind_observation(
            filled["measurement"], filled["history"], filled.get("raw_bytes_sha256"))
        self.assertEqual(refused["reason"], "inferred_component_labeled_measured")

    def test_active_exposure_is_not_a_completed_prefix(self):
        during = _fixture("FX-03-p")
        during["history"]["events"].append({
            "end_utc": "2026-01-01T03:00:00Z",
            "id": "E2",
            "kind": "load_block",
            "segment": "S1",
            "start_utc": "2026-01-01T01:30:00Z",
            "trace_sha256": "5" * 64,
        })
        refused = observation.bind_observation(
            during["measurement"], during["history"], during.get("raw_bytes_sha256"))
        self.assertEqual(refused["reason"], "measurement_during_active_exposure")

    def test_history_rejects_bad_clocks_without_an_exception(self):
        negative = _fixture("FX-04-p")
        negative["segments"][1]["uncertainty_s"] = -1.0
        self.assertEqual(
            history.validate_history(negative)["reason"], "segment_uncertainty_invalid")
        missing_segment = _fixture("FX-04-p")
        missing_segment["events"][1]["segment"] = "S9"
        self.assertEqual(
            history.validate_history(missing_segment)["reason"], "segment_reference_unknown")
        impossible = _fixture("FX-04-p")
        impossible["events"][0]["start_utc"] = "2026-02-30T00:00:00Z"
        self.assertEqual(
            history.validate_history(impossible)["reason"], "timestamp_not_a_calendar_date")
        gap = _fixture("FX-04-p")
        gap["events"].append({
            "end_utc": "2026-01-01T02:00:00Z",
            "id": "E1b",
            "kind": "dwell",
            "segment": "S1",
            "start_utc": "2026-01-01T01:30:00Z",
            "trace_sha256": "6" * 64,
        })
        self.assertEqual(history.validate_history(gap)["reason"], "uncovered_gap")

    def test_mass_and_trace_reject_non_numbers(self):
        blank = _fixture("FX-07-p")
        blank["records"][1]["value_g"] = None
        self.assertEqual(
            records.validate_mass(blank["records"], blank["requested"])["reason"],
            "mass_value_invalid",
        )
        conflict = _fixture("FX-07-p")
        extra = copy.deepcopy(conflict["records"][1])
        extra["value_g"] = 91.0
        conflict["records"].append(extra)
        self.assertEqual(
            records.validate_mass(conflict["records"], conflict["requested"])["reason"],
            "conflicting_configuration_measurements",
        )
        textual = _fixture("FX-06-p")
        textual["trace"]["gain_n_per_count"] = "1/2"
        self.assertEqual(
            observation.reduce_trace(textual["trace"])["reason"], "non_numeric_value")
        boolean = _fixture("FX-05-p")
        boolean["measurement"]["value"] = True
        self.assertEqual(
            observation.bind_observation(
                boolean["measurement"], boolean["history"], boolean["raw_bytes_sha256"]
            )["reason"],
            "non_numeric_value",
        )

    def test_intervention_pair_uses_one_function(self):
        accepted = observation.validate_intervention(
            {
                "schema": "measurement_intervention.v1",
                "id": "IV-1",
                "specimen": "SP-1",
                "time_utc": "2026-01-01T02:00:00Z",
                "role": "intervention",
                "may_introduce": [],
            },
            {"scope": "intrinsic", "species": "H"},
        )
        self.assertEqual(accepted, {"outcome": "accepted"})
        refused = observation.validate_intervention(
            {}, {"scope": "intrinsic", "species": "H"})
        self.assertEqual(refused["reason"], "preparation_undeclared")
        self.assertEqual(refused["diagnostic"], "unable_to_determine")
        induced = observation.validate_intervention(
            {"may_introduce": ["H"]}, {"scope": "intrinsic", "species": "H"})
        self.assertEqual(induced["reason"], "preparation_induced_not_intrinsic")

    def test_closed_schema_rejects_an_extra_passport_field(self):
        passport = _fixture("FX-01-p")["passport"]
        passport["finish_claim"] = "polished"
        refused = records.validate_specimen(passport, [])
        self.assertEqual(refused["reason"], "schema_rejected")
        self.assertEqual(refused["material_state"], "unknown")

    def test_schema_version_is_required_on_a_canonical_passport(self):
        passport = _fixture("FX-01-p")["passport"]
        del passport["schema"]
        refused = records.validate_specimen(passport, [])
        self.assertEqual(refused["reason"], "schema_rejected")
        self.assertEqual(refused["material_state"], "unknown")

    def test_unknown_measurement_field_cannot_bind(self):
        bound = _fixture("FX-05-p")
        bound["measurement"]["qualified"] = True
        refused = observation.bind_observation(
            bound["measurement"], bound["history"], bound["raw_bytes_sha256"])
        self.assertEqual(refused["reason"], "schema_rejected")

    def test_interpret_uses_the_binding_not_the_record_label(self):
        healthy = _fixture("FX-12-p")
        accepted = observation.interpret(
            observations=healthy["observations"], claim=healthy["claim"])
        self.assertEqual(accepted["outcome"], "accepted")
        invalid = _fixture("FX-12-p")
        invalid["observations"][0]["calibration"]["valid_from_utc"] = "2026-01-01T03:00:00Z"
        refused = observation.interpret(
            observations=invalid["observations"], claim=invalid["claim"])
        self.assertEqual(refused["diagnostic"], "unable_to_determine")
        self.assertEqual(refused["reason"], "calibration_not_valid_at_acquisition")
        flagged = _fixture("FX-12-p")
        flagged["observations"][0]["validated"] = True
        flagged["observations"][0]["accepted"] = True
        unknown = observation.interpret(
            observations=flagged["observations"], claim=flagged["claim"])
        self.assertEqual(unknown["reason"], "schema_rejected")
        bare = observation.interpret(
            observations=healthy["observations"],
            claim={"diagnostic": "change_vs_baseline"},
        )
        self.assertEqual(bare["diagnostic"], "unable_to_determine")
        self.assertNotEqual(bare.get("finding"), "supported_within_scope")

    def test_legacy_scope_tokens_are_not_route_or_surface_coverage(self):
        healthy = _fixture("FX-02-p")
        self.assertEqual(
            records.check_transfer(healthy["qualification"], healthy["passport"]),
            {"outcome": "accepted"},
        )
        surface_as_route = _fixture("FX-02-p")
        surface_as_route["passport"]["process_route"] = "machined"
        surface_as_route["qualification"]["passport_sha256"] = scientific_hash(
            surface_as_route["passport"])
        refused_route = records.check_transfer(
            surface_as_route["qualification"], surface_as_route["passport"])
        self.assertEqual(refused_route["reason"], "unapproved_route_transfer")
        shot = _fixture("FX-02-p")
        shot["passport"]["surface_process"] = "shot_peened"
        shot["qualification"]["passport_sha256"] = scientific_hash(shot["passport"])
        refused_surface = records.check_transfer(
            shot["qualification"], shot["passport"])
        self.assertEqual(refused_surface["reason"], "unapproved_route_transfer")
        missing = _fixture("FX-02-p")
        del missing["qualification"]["covered_surfaces"]
        refused_missing = records.check_transfer(
            missing["qualification"], missing["passport"])
        self.assertEqual(refused_missing["reason"], "unapproved_route_transfer")

    def test_duplicate_ids_and_missing_lots_stay_incomplete(self):
        duplicate = _fixture("FX-11-p")
        duplicate["observations"][1]["id"] = duplicate["observations"][0]["id"]
        refused_id = records.validate_validation_lineage(
            duplicate["claim"], observations=duplicate["observations"])
        self.assertEqual(refused_id["reason"], "duplicate_observation_id")
        missing_lot = _fixture("FX-11-p")
        for observation_record in missing_lot["observations"]:
            del observation_record["experimental_unit"]["lot"]
        refused_lot = records.validate_validation_lineage(
            missing_lot["claim"], observations=missing_lot["observations"])
        self.assertEqual(refused_lot["reason"], "experimental_unit_incomplete")
        self.assertNotEqual(refused_lot["outcome"], "accepted")

    def test_acquisition_boundary_stays_in_the_completed_prefix(self):
        def event(end_utc, start_utc):
            return {
                "end_utc": end_utc,
                "id": "E2",
                "kind": "load_block",
                "segment": "S1",
                "start_utc": start_utc,
                "trace_sha256": "5" * 64,
            }

        def bind(payload):
            return observation.bind_observation(
                payload["measurement"], payload["history"], payload["raw_bytes_sha256"])

        before = _fixture("FX-03-p")
        before["history"]["events"].append(
            event("2026-01-01T01:30:00Z", "2026-01-01T01:00:00Z"))
        self.assertEqual(bind(before)["reason"], "history_prefix_mismatch")
        before["measurement"]["history_prefix_events"] = ["E1", "E2"]
        self.assertEqual(bind(before)["outcome"], "accepted")
        at_boundary = _fixture("FX-03-p")
        at_boundary["history"]["events"].append(
            event("2026-01-01T02:00:00Z", "2026-01-01T01:30:00Z"))
        self.assertEqual(bind(at_boundary)["reason"], "history_prefix_mismatch")
        at_boundary["measurement"]["history_prefix_events"] = ["E1", "E2"]
        self.assertEqual(bind(at_boundary)["outcome"], "accepted")
        after = _fixture("FX-03-p")
        after["history"]["events"].append(
            event("2026-01-01T03:00:00Z", "2026-01-01T01:30:00Z"))
        self.assertEqual(bind(after)["reason"], "measurement_during_active_exposure")

    def test_supplied_component_raw_is_not_filled_in(self):
        raw = "3" * 64
        measured = _fixture("FX-09-p-A03-03_components")
        measured["measurement"]["components"] = {
            "xx": 0.0,
            "xy": {"unknown": "not measured"},
            "yy": 20.0,
        }
        measured["measurement"]["component_roles"] = {"xx": "measured", "yy": "measured"}
        accepted = observation.bind_observation(
            measured["measurement"], measured["history"], raw)
        self.assertEqual(accepted["outcome"], "accepted")
        self.assertEqual(accepted["components_unknown"], ["xy"])
        invented = _fixture("FX-09-a-A03-03_components")
        invented["measurement"]["components"]["xy"] = 7.5
        invented["measurement"]["component_roles"] = {
            "xx": "measured",
            "xy": "measured",
            "yy": "measured",
        }
        invented["measurement"]["component_raw"] = {"xx": raw, "yy": raw}
        refused = observation.bind_observation(
            invented["measurement"], invented["history"], raw)
        self.assertEqual(refused["reason"], "inferred_component_labeled_measured")
        complete = _fixture("FX-09-p-A03-03_components")
        complete["measurement"]["components"] = {"xx": 0.0, "yy": 20.0}
        complete["measurement"]["component_roles"] = {"xx": "measured", "yy": "measured"}
        complete["measurement"]["component_raw"] = {"xx": raw, "yy": raw}
        mapped = observation.bind_observation(
            complete["measurement"], complete["history"], raw)
        self.assertEqual(mapped["outcome"], "accepted")


if __name__ == "__main__":
    unittest.main()
