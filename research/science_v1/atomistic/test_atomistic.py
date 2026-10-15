"""Unit tests for T17 atomistic contracts (T17-01..06)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.atomistic.contracts import (
    check_ensemble_shared_bias,
    check_holdout_reference,
    check_model_domain,
    check_rate_sensitivity,
    check_time_bridge,
    check_transition_error,
)


class TestAtomisticContracts(unittest.TestCase):
    def test_T17_01_model_domain_positive(self) -> None:
        self.assertEqual(check_model_domain(True, 0.05, 0.15, accept_prediction=True).status, "pass")

    def test_T17_01_model_domain_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_model_domain(False, 0.45, 0.15, accept_prediction=True)

    def test_T17_02_transition_error_positive(self) -> None:
        self.assertEqual(check_transition_error(5.0, 20.0, 50.0, claim_kinetics_accurate=True).status, "pass")

    def test_T17_02_transition_error_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_transition_error(3.0, 220.0, 50.0, claim_kinetics_accurate=True)

    def test_T17_03_ensemble_shared_bias_positive(self) -> None:
        self.assertEqual(check_ensemble_shared_bias(1, 150.0, 30.0, claim_true_error_bounded_by_spread=False).status, "pass")

    def test_T17_03_ensemble_shared_bias_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_ensemble_shared_bias(1, 150.0, 30.0, claim_true_error_bounded_by_spread=True)

    def test_T17_04_rate_sensitivity_positive(self) -> None:
        self.assertEqual(check_rate_sensitivity(1e8, 1e-3, 0.08, claim_direct_rate_equivalence=False).status, "pass")

    def test_T17_04_rate_sensitivity_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_rate_sensitivity(1e8, 1e-3, 0.08, claim_direct_rate_equivalence=True)

    def test_T17_05_time_bridge_positive(self) -> None:
        self.assertEqual(check_time_bridge(True, False, claim_long_time_kinetics_certified=True).status, "pass")

    def test_T17_05_time_bridge_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_time_bridge(False, True, claim_long_time_kinetics_certified=True)

    def test_T17_06_holdout_reference_positive(self) -> None:
        self.assertEqual(check_holdout_reference(["bulk_bcc", "vac_mono"], ["screw_core_glide", "h_trap_gb"]).status, "pass")

    def test_T17_06_holdout_reference_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_holdout_reference(["screw_core_glide"], ["screw_core_glide"])


if __name__ == "__main__":
    unittest.main()
