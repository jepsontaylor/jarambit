"""Unit tests for T10 neighborhood contracts (T10-01..05)."""
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.neighborhood.contracts import (
    check_chemistry_organization,
    check_physical_rotation,
    check_resolution_boundary,
    check_same_marginals_graph,
    check_shuffle_control,
)


class TestNeighborhoodContracts(unittest.TestCase):
    def test_T10_01_same_marginals_graph_positive(self) -> None:
        nodes = [0, 0, 1, 1]
        edges_a = [(0, 1), (2, 3), (0, 2), (1, 3)]
        edges_b = [(0, 2), (0, 3), (1, 2), (1, 3)]
        v = check_same_marginals_graph(nodes, edges_a, edges_b, histogram_only=False)
        self.assertEqual(v.finding, "topology_contrast_distinguished")

    def test_T10_01_same_marginals_graph_adverse(self) -> None:
        nodes = [0, 0, 1, 1]
        edges_a = [(0, 1), (2, 3), (0, 2), (1, 3)]
        edges_b = [(0, 2), (0, 3), (1, 2), (1, 3)]
        with self.assertRaises(ResearchContractError):
            check_same_marginals_graph(nodes, edges_a, edges_b, histogram_only=True)

    def test_T10_02_physical_rotation_positive(self) -> None:
        v = check_physical_rotation([1.0, 2.0, 2.2360679775], [1.0, 2.0, 2.2360679775], frame_dependent_feature_used=False)
        self.assertEqual(v.finding, "rotation_invariant_feature_verified")

    def test_T10_02_physical_rotation_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_physical_rotation([1.0, 2.0], [1.0, 2.0], frame_dependent_feature_used=True)

    def test_T10_03_shuffle_control_positive(self) -> None:
        v = check_shuffle_control([2, 2, 2, 2], [2, 2, 2, 2], claim_manufactured_specimen=False)
        self.assertEqual(v.finding, "marginal_preserving_null_control")

    def test_T10_03_shuffle_control_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_shuffle_control([2, 2, 2, 2], [2, 2, 2, 2], claim_manufactured_specimen=True)

    def test_T10_04_resolution_boundary_positive(self) -> None:
        v = check_resolution_boundary(interior_grains=42, boundary_truncated_grains=9, drop_boundary_uncertainty=False)
        self.assertEqual(v.detail["boundary_truncated_grains"], 9)

    def test_T10_04_resolution_boundary_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_resolution_boundary(interior_grains=42, boundary_truncated_grains=9, drop_boundary_uncertainty=True)

    def test_T10_05_chemistry_organization_positive(self) -> None:
        v = check_chemistry_organization(bulk_cert_only=True, direct_sro_measurement=False, claim_short_range_order=False)
        self.assertEqual(v.finding, "bulk_composition_only_local_order_unknown")

    def test_T10_05_chemistry_organization_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_chemistry_organization(bulk_cert_only=True, direct_sro_measurement=False, claim_short_range_order=True)


if __name__ == "__main__":
    unittest.main()
