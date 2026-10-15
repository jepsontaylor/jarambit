"""Unit tests for T14 inspection contracts (T14-01..09)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.inspection.contracts import (
    check_blind_zone,
    check_healthy_nuisance,
    check_instrument_nonlinearity,
    check_lot_session_holdout,
    check_pod_prevalence,
    check_shared_sensor_bias,
    check_silent_damage,
    check_truth_independent,
    check_warning_censor,
)


class TestInspectionContracts(unittest.TestCase):
    def test_T14_01_truth_independent_positive(self) -> None:
        self.assertEqual(check_truth_independent("eddy_current_v1", "metallography_section_v1").status, "pass")

    def test_T14_01_truth_independent_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_truth_independent("eddy_current_v1", "eddy_current_v1")

    def test_T14_02_silent_damage_positive(self) -> None:
        self.assertEqual(check_silent_damage(0.01, 0.05, 30.0, claim_safe_from_proxy_alone=False).status, "pass")

    def test_T14_02_silent_damage_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_silent_damage(0.01, 0.05, 30.0, claim_safe_from_proxy_alone=True)

    def test_T14_03_healthy_nuisance_positive(self) -> None:
        self.assertEqual(check_healthy_nuisance(0.15, damage_present=False, false_reject=False).status, "pass")

    def test_T14_03_healthy_nuisance_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_healthy_nuisance(0.15, damage_present=False, false_reject=True)

    def test_T14_04_instrument_nonlinearity_positive(self) -> None:
        self.assertEqual(check_instrument_nonlinearity(False, False, 0.4, 1.0, emit_valid_sizing=True).status, "pass")

    def test_T14_04_instrument_nonlinearity_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_instrument_nonlinearity(True, False, 0.4, 1.0, emit_valid_sizing=True)

    def test_T14_05_lot_session_holdout_positive(self) -> None:
        self.assertEqual(check_lot_session_holdout(["L1"], ["L2"], ["S1"], ["S2"]).status, "pass")

    def test_T14_05_lot_session_holdout_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_lot_session_holdout(["L1"], ["L1"], ["S1"], ["S2"])

    def test_T14_06_pod_prevalence_positive(self) -> None:
        self.assertEqual(check_pod_prevalence(0.94, 0.90, prevalence_shifted=True, report_uncalibrated_accuracy_only=False).status, "pass")

    def test_T14_06_pod_prevalence_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_pod_prevalence(0.94, 0.90, prevalence_shifted=True, report_uncalibrated_accuracy_only=True)

    def test_T14_07_blind_zone_positive(self) -> None:
        self.assertEqual(check_blind_zone(0.2, 0.5, claim_inspected_clear=False).status, "unknown")

    def test_T14_07_blind_zone_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_blind_zone(0.2, 0.5, claim_inspected_clear=True)

    def test_T14_08_warning_censor_positive(self) -> None:
        self.assertEqual(check_warning_censor(retired_after_warning=True, count_as_non_failure_survival=False).status, "pass")

    def test_T14_08_warning_censor_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_warning_censor(retired_after_warning=True, count_as_non_failure_survival=True)

    def test_T14_09_shared_sensor_bias_positive(self) -> None:
        self.assertEqual(check_shared_sensor_bias("coil_temp_bus_1", "coil_temp_bus_1", claim_independent_fusion=False).status, "pass")

    def test_T14_09_shared_sensor_bias_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_shared_sensor_bias("coil_temp_bus_1", "coil_temp_bus_1", claim_independent_fusion=True)


if __name__ == "__main__":
    unittest.main()
