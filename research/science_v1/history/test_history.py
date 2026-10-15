"""Unit tests for T11 history contracts (T11-01..07)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.history.contracts import (
    check_acceleration_mode,
    check_competing_censor,
    check_cycle_time_clock,
    check_hold_redistribution,
    check_order_null,
    check_order_positive,
    check_sequence_controls,
)


class TestHistoryContracts(unittest.TestCase):
    def test_T11_01_sequence_controls_positive(self) -> None:
        v = check_sequence_controls(
            ["A_then_B", "B_then_A", "A_only", "B_only", "unexposed", "sham"],
            clocks_matched=True,
            intermediate_observed=True,
        )
        self.assertEqual(v.finding, "sequence_order_isolated")

    def test_T11_01_sequence_controls_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_sequence_controls(["A_then_B", "B_then_A"], clocks_matched=False, intermediate_observed=False)

    def test_T11_02_order_null_positive(self) -> None:
        v = check_order_null([10.0, 10.1], [10.05, 10.05], tol=0.1, force_history_term=False)
        self.assertEqual(v.finding, "commutative_null_accepted")

    def test_T11_02_order_null_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_order_null([10.0, 10.1], [10.05, 10.05], tol=0.1, force_history_term=True)

    def test_T11_03_order_positive_positive(self) -> None:
        v = check_order_positive([12.0, 12.4], [7.0, 7.2], min_effect=2.0, preregistered=True)
        self.assertEqual(v.finding, "noncommutative_order_effect_detected")

    def test_T11_03_order_positive_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_order_positive([12.0, 12.4], [7.0, 7.2], min_effect=2.0, preregistered=False)

    def test_T11_04_cycle_time_clock_positive(self) -> None:
        v = check_cycle_time_clock(cycles_equal=True, elapsed_time_equal=True, temp_rise_equal=True, claim_pure_cycle_effect=True)
        self.assertEqual(v.finding, "dual_clock_control_verified")

    def test_T11_04_cycle_time_clock_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_cycle_time_clock(cycles_equal=True, elapsed_time_equal=False, temp_rise_equal=False, claim_pure_cycle_effect=True)

    def test_T11_05_hold_redistribution_positive(self) -> None:
        v = check_hold_redistribution(local_relaxation_observed=False, assume_local_state_frozen=False)
        self.assertEqual(v.finding, "local_hold_evolution_unknown")

    def test_T11_05_hold_redistribution_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_hold_redistribution(local_relaxation_observed=False, assume_local_state_frozen=True)

    def test_T11_06_acceleration_mode_positive(self) -> None:
        v = check_acceleration_mode("transgranular_fatigue", "intergranular_oxide_spall", claim_service_years=False)
        self.assertEqual(v.finding, "nontransferable_mode_shift_flagged")

    def test_T11_06_acceleration_mode_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_acceleration_mode("transgranular_fatigue", "intergranular_oxide_spall", claim_service_years=True)

    def test_T11_07_competing_censor_positive(self) -> None:
        v = check_competing_censor({"groove_crack": 4, "bore_yield": 2}, right_censored=3, interval_censored=1, reported_total=10)
        self.assertEqual(v.detail["n_total"], 10)

    def test_T11_07_competing_censor_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_competing_censor({"groove_crack": 4, "bore_yield": 2}, right_censored=3, interval_censored=1, reported_total=6)


if __name__ == "__main__":
    unittest.main()
