"""Unit tests for T16 recovery contracts (T16-01..06)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.recovery.contracts import (
    check_closure_false_heal,
    check_failure_migration,
    check_isotope_exchange,
    check_nanoscale_transfer,
    check_recovery_positive,
    check_source_ambiguity,
)


class TestRecoveryContracts(unittest.TestCase):
    def test_T16_01_closure_false_heal_positive(self) -> None:
        self.assertEqual(check_closure_false_heal(True, 0.92, 0.85, claim_structural_healing=True).status, "pass")

    def test_T16_01_closure_false_heal_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_closure_false_heal(True, 0.25, 0.85, claim_structural_healing=True)

    def test_T16_02_recovery_positive_positive(self) -> None:
        self.assertEqual(check_recovery_positive(400.0, 520.0, 430.0, 50.0, claim_active_recovery=True).status, "pass")

    def test_T16_02_recovery_positive_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_recovery_positive(400.0, 440.0, 435.0, 50.0, claim_active_recovery=True)

    def test_T16_03_failure_migration_positive(self) -> None:
        self.assertEqual(check_failure_migration(True, 0.96, 0.90, claim_component_restored=True).status, "pass")

    def test_T16_03_failure_migration_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_failure_migration(True, 0.65, 0.90, claim_component_restored=True)

    def test_T16_04_isotope_exchange_positive(self) -> None:
        self.assertEqual(check_isotope_exchange(3.5, 1.1, transport_detected=True).status, "pass")

    def test_T16_04_isotope_exchange_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_isotope_exchange(1.0, 1.2, transport_detected=True)

    def test_T16_05_source_ambiguity_positive(self) -> None:
        self.assertEqual(check_source_ambiguity(True, True, claim_unique_source=False).status, "inconclusive")

    def test_T16_05_source_ambiguity_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_source_ambiguity(True, True, claim_unique_source=True)

    def test_T16_06_nanoscale_transfer_positive(self) -> None:
        self.assertEqual(check_nanoscale_transfer(True, bulk_coupon_tested=True, claim_bulk_component_healing=True).status, "pass")

    def test_T16_06_nanoscale_transfer_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_nanoscale_transfer(True, bulk_coupon_tested=False, claim_bulk_component_healing=True)


if __name__ == "__main__":
    unittest.main()
