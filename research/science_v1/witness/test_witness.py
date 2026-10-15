"""Unit tests for T15 witness contracts (T15-01..06)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.witness.contracts import (
    check_mass_coupling,
    check_reader_environment,
    check_shared_selftest,
    check_strain_vs_damage,
    check_warning_persistence,
    check_witness_invalid,
)


class TestWitnessContracts(unittest.TestCase):
    def test_T15_01_strain_vs_damage_positive(self) -> None:
        self.assertEqual(check_strain_vs_damage(0.004, 0.3, trigger_latch=False).status, "pass")

    def test_T15_01_strain_vs_damage_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_strain_vs_damage(0.004, 0.3, trigger_latch=True)

    def test_T15_02_witness_invalid_positive(self) -> None:
        self.assertEqual(check_witness_invalid(debonded_or_broken=True, report_structural_safe=False).status, "unknown")

    def test_T15_02_witness_invalid_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_witness_invalid(debonded_or_broken=True, report_structural_safe=True)

    def test_T15_03_shared_selftest_positive(self) -> None:
        self.assertEqual(check_shared_selftest(True, True, claim_selftest_valid=True).status, "pass")

    def test_T15_03_shared_selftest_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_shared_selftest(True, False, claim_selftest_valid=True)

    def test_T15_04_warning_persistence_positive(self) -> None:
        self.assertEqual(check_warning_persistence(True, True).status, "pass")

    def test_T15_04_warning_persistence_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_warning_persistence(True, False)

    def test_T15_05_reader_environment_positive(self) -> None:
        self.assertEqual(check_reader_environment(1.0, 2.0, 5.0, accept_uncompensated=True).status, "pass")

    def test_T15_05_reader_environment_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_reader_environment(1.0, 12.0, 5.0, accept_uncompensated=True)

    def test_T15_06_mass_coupling_positive(self) -> None:
        self.assertEqual(check_mass_coupling(0.2, 1.0, 0.0, claim_non_intrusive=True).status, "pass")

    def test_T15_06_mass_coupling_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_mass_coupling(2.5, 1.0, 5.0, claim_non_intrusive=True)


if __name__ == "__main__":
    unittest.main()
