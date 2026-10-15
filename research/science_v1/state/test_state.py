"""Unit tests for T09 state contracts (T09-01..06)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.state.contracts import (
    check_early_irreversible,
    check_latent_collision,
    check_lot_confirmation,
    check_low_power_null,
    check_matching_bias,
    check_sufficient_null,
)


class TestStateContracts(unittest.TestCase):
    def test_T09_01_latent_collision_positive(self) -> None:
        v = check_latent_collision([1.0, 1.0, 1.0, 1.0], ["A", "A", "B", "B"], [0.2, 0.3, 1.4, 1.5])
        self.assertEqual(v.finding, "omitted_latent_state_detected")

    def test_T09_01_latent_collision_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_latent_collision([1.0, 1.0, 1.0, 1.0], ["A", "A", "B", "B"], [0.2, 0.25, 0.22, 0.24])

    def test_T09_02_sufficient_null_positive(self) -> None:
        v = check_sufficient_null([1.0, 1.02], [0.99, 1.01], threshold=0.05, claim_hidden_state=False)
        self.assertEqual(v.finding, "scoped_null_accepted")

    def test_T09_02_sufficient_null_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_sufficient_null([1.0, 1.02], [0.99, 1.01], threshold=0.05, claim_hidden_state=True)

    def test_T09_03_matching_bias_positive(self) -> None:
        v = check_matching_bias(matched_after_outcome=False, survivor_filtered=False)
        self.assertEqual(v.finding, "pre_outcome_protocol_valid")

    def test_T09_03_matching_bias_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_matching_bias(matched_after_outcome=True, survivor_filtered=False)

    def test_T09_04_early_irreversible_positive(self) -> None:
        v = check_early_irreversible(residual_plastic_strain=2.5e-4, noise_floor=5.0e-5, claim_crack_or_lifetime=False)
        self.assertEqual(v.finding, "early_irreversible_slip_detected")

    def test_T09_04_early_irreversible_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_early_irreversible(residual_plastic_strain=2.5e-4, noise_floor=5.0e-5, claim_crack_or_lifetime=True)

    def test_T09_05_lot_confirmation_positive(self) -> None:
        v = check_lot_confirmation(["lot_1", "lot_2"], ["lot_3", "lot_4"], grains_counted_as_lots=False)
        self.assertEqual(v.finding, "disjoint_lot_holdout_verified")

    def test_T09_05_lot_confirmation_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_lot_confirmation(["lot_1", "lot_2"], ["lot_2", "lot_3"], grains_counted_as_lots=False)
        with self.assertRaises(ResearchContractError):
            check_lot_confirmation(["lot_1"], ["lot_2"], grains_counted_as_lots=True)

    def test_T09_06_low_power_null_positive(self) -> None:
        v = check_low_power_null(n_specimens=2, ci_half_width=0.45, max_equiv_bound=0.10, claim_universal_sufficiency=False)
        self.assertEqual(v.status, "inconclusive")

    def test_T09_06_low_power_null_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_low_power_null(n_specimens=2, ci_half_width=0.45, max_equiv_bound=0.10, claim_universal_sufficiency=True)


if __name__ == "__main__":
    unittest.main()
