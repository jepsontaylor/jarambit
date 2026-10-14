"""Generic passport and test-plan controls. Incomplete records are not a lab pass."""
import json
import unittest
from pathlib import Path

from assurance.laboratory import records
from assurance.testing.contracts import scientific_hash

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
FORBIDDEN = (
    "commissioning",
    "coupon_protocol",
    "hardness",
    "modulus",
    "protocol",
    "setpoint",
    "tensile",
    "yield_strength",
    "yield_strength_mpa",
)


def _load(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


class GenericLaboratoryRecords(unittest.TestCase):
    def test_schemas_stay_closed_and_omit_physical_recommendations(self):
        names = [
            "specimen.v1.json",
            "exposure_history.v1.json",
            "measurement_intervention.v1.json",
            "material_state.v1.json",
            "test_plan.v1.json",
        ]
        for name in names:
            document = _load(name)
            self.assertFalse(document["additionalProperties"], name)
            encoded = json.dumps(document)
            for banned in FORBIDDEN:
                self.assertNotIn(f'"{banned}"', encoded, name)

    def test_unknown_material_state_stays_incomplete(self):
        record = {
            "schema": "material_state.v1",
            "id": "MS-TOY-1",
            "passport_id": "PP-TOY-1",
            "route_id": "RT-TOY-1",
            "state": "unknown",
            "properties": {"unknown": "not measured"},
        }
        actual = records.validate_material_state(record)
        self.assertEqual(actual["outcome"], "accepted")
        self.assertEqual(actual["completion"], "incomplete")
        self.assertIs(actual["lab_pass"], False)
        self.assertEqual(actual["state"], "unknown")

    def test_numeric_strength_is_not_a_measured_property(self):
        record = {
            "schema": "material_state.v1",
            "id": "MS-TOY-1",
            "passport_id": "PP-TOY-1",
            "route_id": "RT-TOY-1",
            "state": "identified",
            "properties": {"yield_strength_mpa": 900},
        }
        actual = records.validate_material_state(record)
        self.assertEqual(actual["outcome"], "refused")
        self.assertEqual(actual["reason"], "physical_property_not_measured")
        self.assertIs(actual["lab_pass"], False)

    def test_distinct_fit_and_validation_ids_do_not_pass_a_lab(self):
        plan = {
            "schema": "test_plan.v1",
            "id": "TP-TOY-1",
            "specimen_units": ["SP-TOY-1"],
            "datasets": [
                {"id": "DS-FIT-TOY", "role": "fit"},
                {"id": "DS-VAL-TOY", "role": "validation"},
            ],
        }
        actual = records.validate_test_plan(plan)
        self.assertEqual(actual["outcome"], "accepted")
        self.assertEqual(actual["completion"], "incomplete")
        self.assertIs(actual["lab_pass"], False)

    def test_one_dataset_cannot_be_both_fit_and_validation(self):
        plan = {
            "schema": "test_plan.v1",
            "id": "TP-TOY-2",
            "specimen_units": ["SP-TOY-1"],
            "datasets": [
                {"id": "DS-SAME-TOY", "role": "fit"},
                {"id": "DS-SAME-TOY", "role": "validation"},
            ],
        }
        actual = records.validate_test_plan(plan)
        self.assertEqual(actual["outcome"], "refused")
        self.assertEqual(actual["reason"], "fit_validation_not_distinct")
        self.assertIs(actual["lab_pass"], False)

    def test_alloy_name_still_does_not_license_an_additive_route(self):
        passport = {
            "alloy": "Ti-6Al-4V",
            "id": "SP-AM-TOY",
            "material_lot": "LOT-TOY",
            "process_route": "additive_lpbf",
        }
        qualification = {
            "passport_sha256": scientific_hash(passport),
            "scope": "wrought_bar",
        }
        actual = records.check_transfer(qualification, passport)
        self.assertEqual(actual, {
            "outcome": "refused",
            "reason": "unapproved_route_transfer",
        })


if __name__ == "__main__":
    unittest.main()
