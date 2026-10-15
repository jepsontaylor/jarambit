"""Unit tests for T18 falsification contracts (T18-01..07)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.falsification.contracts import (
    check_audit_independent,
    check_authority_boundary,
    check_budget_menu,
    check_failed_acquisition,
    check_mixed_none_models,
    check_nonidentifiable,
    check_strategy_comparison,
)


class TestFalsificationContracts(unittest.TestCase):
    def test_T18_01_mixed_none_models_positive(self) -> None:
        self.assertEqual(
            check_mixed_none_models(["m1", "m2", "mixed_mechanism", "none_of_the_above"], force_single_winner_when_all_poor=False).status,
            "pass",
        )

    def test_T18_01_mixed_none_models_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_mixed_none_models(["m1", "m2"], force_single_winner_when_all_poor=True)

    def test_T18_02_nonidentifiable_positive(self) -> None:
        self.assertEqual(check_nonidentifiable(1e-9, 1e-3, claim_parameters_identified=False).status, "inconclusive")

    def test_T18_02_nonidentifiable_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_nonidentifiable(1e-9, 1e-3, claim_parameters_identified=True)

    def test_T18_03_audit_independent_positive(self) -> None:
        self.assertEqual(check_audit_independent(["p1", "p2"], ["a1"], 0.25, 0.20).status, "pass")

    def test_T18_03_audit_independent_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_audit_independent(["p1"], ["p1"], 0.25, 0.20)
        with self.assertRaises(ResearchContractError):
            check_audit_independent(["p1"], ["a1"], 0.05, 0.20)

    def test_T18_04_budget_menu_positive(self) -> None:
        self.assertEqual(check_budget_menu(80.0, 100.0, 2, 4, feasible_setup=True).status, "pass")

    def test_T18_04_budget_menu_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_budget_menu(140.0, 100.0, 6, 4, feasible_setup=True)

    def test_T18_05_strategy_comparison_positive(self) -> None:
        self.assertEqual(check_strategy_comparison(0.04, 0.09, True, True, claim_active_superior=True).status, "pass")

    def test_T18_05_strategy_comparison_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_strategy_comparison(0.04, 0.09, False, False, claim_active_superior=True)

    def test_T18_06_failed_acquisition_positive(self) -> None:
        self.assertEqual(check_failed_acquisition(True, impute_as_confirming_observation=False).status, "pass")

    def test_T18_06_failed_acquisition_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_failed_acquisition(True, impute_as_confirming_observation=True)

    def test_T18_07_authority_boundary_positive(self) -> None:
        self.assertEqual(check_authority_boundary(True, human_signoff_present=True, auto_execute=False).status, "pass")

    def test_T18_07_authority_boundary_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_authority_boundary(True, human_signoff_present=False, auto_execute=True)


if __name__ == "__main__":
    unittest.main()
