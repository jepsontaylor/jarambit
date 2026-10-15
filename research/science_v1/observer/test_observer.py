"""Unit tests for T12 observer contracts (T12-01..05)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.observer.contracts import (
    check_created_erased,
    check_drift_only,
    check_observation_arms,
    check_prep_transfer,
    check_true_nuisance,
)


class TestObserverContracts(unittest.TestCase):
    def test_T12_01_observation_arms_positive(self) -> None:
        v = check_observation_arms(["frequent", "sparse", "endpoint_only", "prep", "sham"], handling_matched=True, claim_zero_observer_effect=True)
        self.assertEqual(v.finding, "observer_arms_identifiable")

    def test_T12_01_observation_arms_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_observation_arms(["frequent"], handling_matched=False, claim_zero_observer_effect=True)

    def test_T12_02_created_erased_positive(self) -> None:
        v = check_created_erased(endpoint_only_mean=0.1, frequent_beam_mean=0.8, claim_universal_artifact_or_real="scoped")
        self.assertEqual(v.finding, "observer_perturbed_signal")

    def test_T12_02_created_erased_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_created_erased(endpoint_only_mean=0.1, frequent_beam_mean=0.8, claim_universal_artifact_or_real="universal")

    def test_T12_03_drift_only_positive(self) -> None:
        v = check_drift_only(raw_signal_shift=0.42, reference_channel_shift=0.41, tol=0.05, diagnose_damage=False)
        self.assertEqual(v.finding, "drift_compensated_no_damage")

    def test_T12_03_drift_only_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_drift_only(raw_signal_shift=0.42, reference_channel_shift=0.41, tol=0.05, diagnose_damage=True)

    def test_T12_04_true_nuisance_positive(self) -> None:
        v = check_true_nuisance(signal_shift=1.2, nuisance_value=5.0, validated_max_nuisance=10.0, claim_definitive_status=True)
        self.assertEqual(v.status, "pass")
        v_out = check_true_nuisance(signal_shift=1.2, nuisance_value=25.0, validated_max_nuisance=10.0, claim_definitive_status=False)
        self.assertEqual(v_out.status, "unknown")

    def test_T12_04_true_nuisance_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_true_nuisance(signal_shift=1.2, nuisance_value=25.0, validated_max_nuisance=10.0, claim_definitive_status=True)

    def test_T12_05_prep_transfer_positive(self) -> None:
        v = check_prep_transfer("Ti-6Al-4V", "Ti-6Al-4V", target_qualified=True)
        self.assertEqual(v.finding, "prep_scope_valid")

    def test_T12_05_prep_transfer_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_prep_transfer("Cu-OFHC", "Ti-6Al-4V", target_qualified=False)


if __name__ == "__main__":
    unittest.main()
