"""Unit tests for T08 multimodal contracts (T08-01..06)."""
import math
import unittest
from research.science_v1.common import ResearchContractError
from research.science_v1.multimodal.contracts import (
    MAX_APPROVED_BYTES,
    check_bounded_download,
    check_group_acquisition,
    check_matched_slip_missing,
    check_orientation_symmetry,
    check_registration_truth,
    check_units_metadata,
)


class TestMultimodalContracts(unittest.TestCase):
    def test_T08_01_bounded_download_positive(self) -> None:
        v = check_bounded_download(120_000_000, 450_000_000)
        self.assertEqual(v.status, "pass")
        self.assertEqual(v.finding, "within_approved_cap")

    def test_T08_01_bounded_download_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_bounded_download(100_000_000, MAX_APPROVED_BYTES + 1)

    def test_T08_02_units_metadata_positive(self) -> None:
        v = check_units_metadata(
            {"length_unit": "um", "doi": "10.5281/zenodo.1001", "version": "1.0", "license": "CC-BY-4.0"},
            "10.5281/zenodo.1001",
            "1.0",
        )
        self.assertEqual(v.finding, "metadata_resolved")

    def test_T08_02_units_metadata_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_units_metadata(
                {"length_unit": "pixels", "doi": "10.5281/zenodo.1001", "version": "1.0", "license": "CC-BY-4.0"},
                "10.5281/zenodo.1001",
                "1.0",
            )

    def test_T08_03_registration_truth_positive(self) -> None:
        src = [(0.0, 0.0), (2.0, 0.0), (0.0, 3.0)]
        th = 0.25
        c, s = math.cos(th), math.sin(th)
        dst = [(c * x - s * y + 1.5, s * x + c * y - 0.5) for x, y in src]
        v = check_registration_truth(src, dst, [10, 11, 12], [10, 11, 12])
        self.assertEqual(v.finding, "proper_rigid_transform_verified")

    def test_T08_03_registration_truth_adverse(self) -> None:
        src = [(0.0, 0.0), (2.0, 0.0), (0.0, 3.0)]
        mirrored = [(-x, y) for x, y in src]
        with self.assertRaises(ResearchContractError):
            check_registration_truth(src, mirrored, [10, 11, 12], [10, 11, 12])
        with self.assertRaises(ResearchContractError):
            check_registration_truth(src, src, [10, 11, 12], [10, 12, 11])

    def test_T08_04_orientation_symmetry_positive(self) -> None:
        v = check_orientation_symmetry(15.0, "deg", 75.0, "deg", symmetry_fold=6)
        self.assertEqual(v.finding, "symmetry_equivalent")

    def test_T08_04_orientation_symmetry_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_orientation_symmetry(15.0, "deg", math.radians(15.0), "rad", symmetry_fold=6)

    def test_T08_05_matched_slip_missing_positive(self) -> None:
        v = check_matched_slip_missing(["EBSD", "DCT"], claim_full_slip_reproduction=False)
        self.assertEqual(v.finding, "importer_only_receipt")

    def test_T08_05_matched_slip_missing_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_matched_slip_missing(["EBSD", "DCT"], claim_full_slip_reproduction=True)

    def test_T08_06_group_acquisition_positive(self) -> None:
        v = check_group_acquisition({"spec_A": [1, 2, 3, 4]}, unobserved_grains=[5, 6], claim_independent_specimens=1)
        self.assertEqual(v.detail["n_specimens"], 1)
        self.assertAlmostEqual(v.detail["coverage"], 4.0 / 6.0)

    def test_T08_06_group_acquisition_adverse(self) -> None:
        with self.assertRaises(ResearchContractError):
            check_group_acquisition({"spec_A": [1, 2, 3, 4]}, unobserved_grains=[5], claim_independent_specimens=4)


if __name__ == "__main__":
    unittest.main()
