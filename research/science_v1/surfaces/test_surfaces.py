"""Unit tests for T13 surface, film, topological, and hydrogen reservoir contracts (T13-01..07)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.surfaces.contracts import (
    check_balance_reservoir,
    check_barrier_vs_structure,
    check_charge_not_loss,
    check_coupling_null,
    check_process_vs_film,
    check_segmentation_bias,
    check_topology_average,
)


class TestSurfaceContracts(unittest.TestCase):
    def test_T13_01_process_vs_film_positive(self) -> None:
        v = check_process_vs_film(["uncoated", "thermal_only", "gas_only", "full_process"], attribute_to_film_alone=True)
        self.assertEqual(v.finding, "process_and_film_separated")

    def test_T13_01_process_vs_film_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_process_vs_film(["uncoated", "full_process"], attribute_to_film_alone=True)

    def test_T13_02_coupling_null_positive(self) -> None:
        v = check_coupling_null(coupled_error=0.04, uncoupled_error=0.12, complexity_penalty=0.02, claim_coupling_supported=True)
        self.assertEqual(v.finding, "coupling_supported")

    def test_T13_02_coupling_null_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_coupling_null(coupled_error=0.11, uncoupled_error=0.12, complexity_penalty=0.02, claim_coupling_supported=True)

    def test_T13_03_topology_average_positive(self) -> None:
        v = check_topology_average(mean_matched=True, topology_differs=True, holdout_passed=True, claim_topology_predictive=True)
        self.assertEqual(v.finding, "topology_beyond_average_verified")

    def test_T13_03_topology_average_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_topology_average(mean_matched=False, topology_differs=True, holdout_passed=True, claim_topology_predictive=True)

    def test_T13_04_segmentation_bias_positive(self) -> None:
        v = check_segmentation_bias(stable_across_thresholds=True, lot_train=["L1"], lot_test=["L2"], claim_descriptor_robust=True)
        self.assertEqual(v.finding, "segmentation_invariant")

    def test_T13_04_segmentation_bias_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_segmentation_bias(stable_across_thresholds=False, lot_train=["L1"], lot_test=["L2"], claim_descriptor_robust=True)
        with self.assertRaises(ResearchContractError):
            check_segmentation_bias(stable_across_thresholds=True, lot_train=["L1"], lot_test=["L1"], claim_descriptor_robust=True)

    def test_T13_05_balance_reservoir_positive(self) -> None:
        v = check_balance_reservoir(uptake=10.0, mobile=3.0, Reversible=4.0, deep_trap=2.5, residual=0.45, tol=0.1)
        self.assertEqual(v.finding, "reservoir_balance_closed")

    def test_T13_05_balance_reservoir_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_balance_reservoir(uptake=10.0, mobile=3.0, Reversible=2.0, deep_trap=1.0, residual=0.0, tol=0.1)

    def test_T13_06_charge_not_loss_positive(self) -> None:
        v = check_charge_not_loss(charged_ppm=45.0, mechanical_loss_pct=1.2, loss_threshold_pct=5.0, claim_embrittlement_reversed_without_mech_test=False)
        self.assertEqual(v.finding, "benign_trapping_no_mechanical_loss")

    def test_T13_06_charge_not_loss_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_charge_not_loss(charged_ppm=45.0, mechanical_loss_pct=1.2, loss_threshold_pct=5.0, claim_embrittlement_reversed_without_mech_test=True)

    def test_T13_07_barrier_vs_structure_positive(self) -> None:
        v = check_barrier_vs_structure(permeation_reduced=True, microstructural_damage_present=False, claim_net_protective_coating=True)
        self.assertEqual(v.finding, "net_protective_barrier")

    def test_T13_07_barrier_vs_structure_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_barrier_vs_structure(permeation_reduced=True, microstructural_damage_present=True, claim_net_protective_coating=True)


if __name__ == "__main__":
    unittest.main()
