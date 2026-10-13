import hashlib, pathlib, unittest
ROOT = pathlib.Path(__file__).resolve().parents[3]

class BenchWorkload(unittest.TestCase):
    def test_frozen_sha(self):
        d = ROOT / "bench/fixed_1k"
        want = (d / "SHA256SUMS").read_text().split()[0]
        self.assertEqual(hashlib.sha256((d / "genomes.csv").read_bytes()).hexdigest(), want)

    def test_thousand_unique_rows(self):
        rows = (ROOT / "bench/fixed_1k/genomes.csv").read_text().splitlines()[1:]
        self.assertEqual(len(rows), 1000)
        self.assertGreaterEqual(len(set(rows)), 990)

if __name__ == "__main__":
    unittest.main()
