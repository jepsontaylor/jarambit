"""KnifeInterfaceV1 contract: Pheno adapter, INCOMPLETE semantics (needs shapely; skips otherwise)."""
import math, os, sys, unittest, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    import shapely  # noqa
    HAVE = True
except Exception:
    HAVE = False


def crescent():
    th = [math.radians(a) for a in range(200, 341, 5)]
    outer = [(60 * math.cos(t), 60 * math.sin(t) + 40) for t in th]
    inner = [(45 * math.cos(t), 45 * math.sin(t) + 40) for t in reversed(th)]
    ring = [(-50 + 12 * math.cos(t), 15 + 12 * math.sin(t)) for t in [2 * math.pi * k / 24 for k in range(24)]]
    out = [(-70, 15)] + outer + inner + [(-70, 30)]
    return {"outline": out, "holes": [], "hole_names": [], "edge_in": inner, "edge_sp": outer[-6:], "tip": list(outer[-1]), "t": 4.5, "mass_g": 60.0}


@unittest.skipUnless(HAVE, "shapely missing")
class Contract(unittest.TestCase):
    def test_pheno_declares_spine_sharp_and_is_incomplete(self):
        from sheath.interface import from_pheno, validate
        f = from_pheno(crescent())
        names = [r["name"] for r in f["sharp_regions"]]
        self.assertIn("edge_sp", names); self.assertIn("edge_in", names)
        ok, v = validate(f)
        self.assertTrue(ok); self.assertEqual(v["outcome"], "incomplete")
        self.assertIn("retention_lands", v["missing"])

    def test_missing_key_fails(self):
        from sheath.interface import from_pheno, validate
        f = from_pheno(crescent()); del f["keepouts"]
        self.assertEqual(validate(f)[1]["outcome"], "fail")

    def test_annotation_hash_binding(self):
        from sheath.interface import load_annotations
        p = os.path.join(os.path.dirname(__file__), "..", "..", "designs", "switchback", "C9.3", "sheath", "knife_interface_annotations.json")
        a, st = load_annotations(p, "3a818183bcb5b9a9093da947e00414ed29aa9bfebbb614046b8fb0b16dcbe919")
        self.assertIsNotNone(a); self.assertTrue(st.startswith("APPROVED"))         # delegated review 2026-10-13
        self.assertIn("hook_back_edge_sp", [d["name"] for d in a["declared_sharp"]])
        self.assertNotIn("hook_back", [b["name"] for b in a.get("bumper_lands", [])])
        a2, st2 = load_annotations(p, "0" * 64)
        self.assertIsNone(a2)
