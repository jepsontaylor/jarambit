"""Meta-verification that all 70 T08..T18 catalog cases in TEST_CASE_CATALOG.json have exact allowed paths and paired positive/adverse tests."""
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "v1" / "science" / "tests" / "TEST_CASE_CATALOG.json"


class TestAllT08ToT18CatalogCoverage(unittest.TestCase):
    def test_all_70_t08_to_t18_cases_have_exact_paths_and_controls(self) -> None:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        target_units = {"T08", "T09", "T10", "T11", "T12", "T13", "T14", "T15", "T16", "T17", "T18"}
        cases = [c for c in catalog["cases"] if c["work_unit"] in target_units]
        self.assertEqual(len(cases), 70)

        for case in cases:
            cid = case["id"]
            prefix = cid.split("-")[0] + "_" + cid.split("-")[1]  # e.g. T08_01
            test_rel = case["allowed_test_path"]
            test_dir = ROOT / test_rel
            prod_path = test_dir / "contracts.py"
            test_path = test_dir / f"test_{test_dir.name}.py"

            self.assertTrue(prod_path.is_file(), f"Missing production contract file for {cid}: {prod_path}")
            self.assertTrue(test_path.is_file(), f"Missing test file for {cid}: {test_path}")

            spec = importlib.util.spec_from_file_location(f"science_v1_{test_dir.name}", test_path)
            self.assertIsNotNone(spec)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)

            method_names = [
                attr
                for obj in vars(module).values()
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase)
                for attr in dir(obj)
                if attr.startswith(f"test_{prefix}_")
            ]
            self.assertTrue(
                any(m.endswith("_positive") for m in method_names),
                f"No positive control method for {cid} in {test_path}",
            )
            self.assertTrue(
                any(m.endswith("_adverse") for m in method_names),
                f"No adverse control method for {cid} in {test_path}",
            )


if __name__ == "__main__":
    unittest.main()
