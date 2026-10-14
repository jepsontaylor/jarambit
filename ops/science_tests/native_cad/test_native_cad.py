"""Harness tests. A passing test may record a failing candidate."""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

from ops.science_tests.native_cad.evaluate import (
    HISTORICAL_RECEIPT,
    HISTORICAL_RECEIPT_SHA256,
    ROOT,
    AttemptRefused,
    PinUnavailable,
    asset_sha256_matches,
    dump_strict,
    evaluate_subject,
    read_pin,
    read_pinned_object,
    render_markdown,
    resolve_pinned,
    write_attempt,
)
from ops.science_tests.native_cad.fixtures import (
    SYNTHETIC_LABEL,
    analytic_box,
    degenerate_face,
    inverted_box,
    near_coincident_gap,
    nonfinite_triangle,
    nonmanifold_edge,
    open_box,
    two_closed_boxes,
)
from ops.science_tests.native_cad.geometry import (
    analytic_step_box,
    length_unit_from_step_text,
    mass_check,
    mass_g_from_mm3,
    real_number,
    rigid_volume,
    stl_report,
)
from ops.science_tests.native_cad.pins import PIN_COMMIT, SUBJECTS
from ops.science_tests.native_cad.provenance import (
    binding_status,
    reported_provenance,
    verified_native_measurement,
)

_MILLI = "#10 = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );"
_METRE = "#11 = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT($,.METRE.) );"
_INCH = "#12 = ( LENGTH_UNIT() NAMED_UNIT(*) CONVERSION_BASED_UNIT('INCH',#13) );"
_MISSING = "ISO-10303-21; DATA; ENDSEC; END-ISO-10303-21;"
_COMMENT_ONLY = "/* #14 = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) ); */"
_QUOTED_ONLY = "#1 = FILE_DESCRIPTION('#15 = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );','2;1');"


class ProvenanceTests(unittest.TestCase):
    def test_reported_classes_are_not_verified_measurements(self):
        self.assertEqual(reported_provenance("w80d g2 carry", subject="C10c"), "reported_carried_or_ratio")
        self.assertEqual(
            reported_provenance("w80d direct 1.630 x g2 ratio 0.988", subject="C10c"),
            "reported_carried_or_ratio",
        )
        self.assertEqual(
            reported_provenance("record (C.10a 0.738)", subject="C10c"),
            "reported_carried_or_ratio",
        )
        self.assertEqual(reported_provenance("direct r0p2", subject="C10c"), "reported_direct_unverified")
        self.assertEqual(reported_provenance("B-rep ray probe", subject="C10c"), "reported_direct_unverified")
        self.assertEqual(
            reported_provenance("solved directly on C.10a", subject="C10a"),
            "reported_direct_unverified",
        )
        self.assertFalse(verified_native_measurement("direct r0p2"))
        self.assertFalse(verified_native_measurement("direct r0p2", certificate="abc"))

    def test_negation_other_design_and_missing_text(self):
        self.assertEqual(reported_provenance("not direct", subject="C10c"), "reported_missing")
        self.assertEqual(reported_provenance("not a direct native solve", subject="C10c"), "reported_missing")
        self.assertEqual(reported_provenance("indirect donor", subject="C10c"), "reported_missing")
        self.assertEqual(reported_provenance("solved on C.10b", subject="C10c"), "reported_carried_or_ratio")
        self.assertEqual(reported_provenance("C.9.3 section", subject="C10c"), "reported_carried_or_ratio")
        self.assertEqual(reported_provenance("", subject="C10c"), "reported_missing")
        self.assertEqual(reported_provenance("   ", subject="C10c"), "reported_missing")
        self.assertEqual(reported_provenance("method not stated", subject="C10c"), "reported_missing")

    def test_nonempty_genome_id_is_not_a_binding(self):
        self.assertEqual(binding_status(None), "INCOMPLETE")
        self.assertEqual(binding_status(""), "INCOMPLETE")
        self.assertEqual(binding_status("genome-present"), "INCOMPLETE")
        self.assertEqual(binding_status("genome-present", contract="S08"), "INCOMPLETE")

    def test_pinned_source_text_is_in_the_e150bb9_blob(self):
        readme = read_pin(SUBJECTS["C10c"]["readme"]).decode()
        board = read_pin(SUBJECTS["C10c"]["board"]).decode()
        blob = readme + "\n" + board
        for text in SUBJECTS["C10c"]["sources"].values():
            self.assertIn(text, blob)
        c10a = read_pin(SUBJECTS["C10a"]["readme"]).decode()
        for text in SUBJECTS["C10a"]["claim_snippets"].values():
            self.assertIn(text, c10a)


class ControlTests(unittest.TestCase):
    def test_analytic_box_is_a_positive_control(self):
        mesh = analytic_box()
        self.assertEqual(mesh.metadata["synthetic"], SYNTHETIC_LABEL)
        report = stl_report(mesh)
        self.assertTrue(report["finite"])
        self.assertTrue(report["watertight_exact"])
        self.assertTrue(report["winding_consistent_exact"])
        self.assertEqual(report["components_exact"], 1)
        self.assertEqual(report["degenerate_faces_exact"], 0)
        self.assertEqual(report["edges_exact"]["boundary_edges"], 0)
        self.assertEqual(report["edges_exact"]["nonmanifold_edges"], 0)
        self.assertAlmostEqual(report["volume_signed_mm3"], 6000.0, places=6)
        self.assertTrue(report["volume_used_for_mass"])
        self.assertAlmostEqual(mass_g_from_mm3(6000.0), 26.58, places=6)
        step = analytic_step_box(10, 20, 30)
        self.assertEqual(step["solids"], 1)
        self.assertTrue(step["valid"])
        self.assertEqual(step["units"], "mm")
        self.assertEqual(step["units_source"], "constructor")
        self.assertAlmostEqual(step["volume_mm3"], 6000.0, places=6)
        self.assertEqual(step["bounds_compared"]["method"], "BRepBndLib.AddOptimal_s")
        self.assertEqual(step["bounds_loose"]["method"], "BRepBndLib.Add_s")
        self.assertFalse(step["bounds_loose"]["use_for_comparison"])
        self.assertAlmostEqual(step["bounds_compared"]["extents"][0], 10.0, places=6)
        self.assertGreater(step["bounds_loose"]["extents"][0], 10.0)

    def test_small_and_large_constructor_boxes_stay_millimetres(self):
        small = analytic_step_box(0.1, 0.2, 0.3)
        large = analytic_step_box(3000, 10, 10)
        self.assertEqual(small["units"], "mm")
        self.assertEqual(small["units_source"], "constructor")
        self.assertTrue(small["units_agree"])
        self.assertIsNone(small["reader_length_units"])
        self.assertEqual(small["normalized_length_context"], "constructor")
        self.assertAlmostEqual(small["volume_mm3"], 0.006, places=9)
        self.assertEqual(large["units"], "mm")
        self.assertEqual(large["units_source"], "constructor")
        self.assertTrue(large["units_agree"])
        self.assertAlmostEqual(large["volume_mm3"], 300000.0, places=3)
        self.assertAlmostEqual(large["bounds_compared"]["extents"][0], 3000.0, places=4)

    def test_step_unit_text_is_not_inferred_from_size(self):
        self.assertEqual(length_unit_from_step_text(_MILLI)["units"], "mm")
        self.assertEqual(length_unit_from_step_text(_MILLI)["units_source"], "step_declaration")
        self.assertEqual(length_unit_from_step_text(_METRE)["units"], "metre")
        inch = length_unit_from_step_text(_INCH)
        self.assertEqual(inch["units"], "unsupported")
        self.assertEqual(inch["declared_length_unit"], "INCH")
        missing = length_unit_from_step_text(_MISSING)
        self.assertEqual(missing["units"], "unknown")
        self.assertEqual(missing["units_source"], "missing")
        bare = "( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );"
        self.assertEqual(length_unit_from_step_text(bare)["units"], "unknown")
        source = (ROOT / "ops/science_tests/native_cad/geometry.py").read_text()
        self.assertNotIn("max_extent", source)

    def test_comment_quote_and_ambiguous_units_are_not_millimetres(self):
        comment = length_unit_from_step_text(_COMMENT_ONLY)
        self.assertEqual(comment["units"], "unknown")
        quoted = length_unit_from_step_text(_QUOTED_ONLY)
        self.assertEqual(quoted["units"], "unknown")
        both = length_unit_from_step_text(_MILLI + "\n" + _METRE)
        self.assertEqual(both["units"], "ambiguous")
        self.assertEqual(both["units_source"], "multiple_length_contexts")
        self.assertNotEqual(both["units"], "mm")
        unclosed = length_unit_from_step_text("/* " + _MILLI)
        self.assertEqual(unclosed["units"], "ambiguous")
        self.assertEqual(unclosed["units_source"], "unresolved_context")
        beside_comment = length_unit_from_step_text(_MILLI + "\n" + _COMMENT_ONLY)
        self.assertEqual(beside_comment["units"], "mm")
        self.assertEqual(beside_comment["units_source"], "step_declaration")

    def test_negative_mass_pair_is_unavailable(self):
        negative = mass_check(-1.0, -1.0, 0.01)
        self.assertEqual(negative["status"], "UNAVAILABLE")
        self.assertEqual(negative["reason"], "nonpositive_mass")
        self.assertEqual(mass_check(-1.0, 1.0, 0.01)["status"], "UNAVAILABLE")
        self.assertEqual(mass_check(1.0, -1.0, 0.01)["status"], "UNAVAILABLE")
        self.assertEqual(mass_check(26.58, 26.58, 0.0)["status"], "PASS")
        self.assertEqual(mass_check(26.58, 26.58, 0.01)["status"], "PASS")
        self.assertEqual(mass_check(1.0, 2.0, 0.0)["status"], "FAIL")
        self.assertIsNone(mass_g_from_mm3(1e308))

    def test_repeat_and_partial_attempts_keep_their_bytes(self):
        historical = HISTORICAL_RECEIPT.read_bytes()
        with tempfile.TemporaryDirectory() as fresh_name:
            fresh = Path(fresh_name)
            first = write_attempt(fresh, argv=["first"], reports=[])
            receipt = (fresh / "receipt.json").read_bytes()
            self.assertEqual(first["argv"], ["first"])
            self.assertFalse((fresh / ".attempt-partial").exists())
            self.assertTrue((fresh / "NATIVE_CAD_VALIDATION.md").is_file())
            with self.assertRaises(AttemptRefused):
                write_attempt(fresh, argv=["second"], reports=[])
            self.assertEqual((fresh / "receipt.json").read_bytes(), receipt)
        with tempfile.TemporaryDirectory() as partial_name:
            partial = Path(partial_name) / ".attempt-partial"
            partial.write_bytes(b"partial-bytes")
            with self.assertRaises(AttemptRefused):
                write_attempt(Path(partial_name), argv=["resume"], reports=[])
            self.assertEqual(partial.read_bytes(), b"partial-bytes")
            self.assertFalse((Path(partial_name) / "receipt.json").exists())
        self.assertEqual(HISTORICAL_RECEIPT.read_bytes(), historical)

    def test_planted_defects_stay_rejected(self):
        opened = stl_report(open_box())
        self.assertFalse(opened["watertight_exact"])
        self.assertGreater(opened["edges_exact"]["boundary_edges"], 0)
        self.assertFalse(opened["volume_used_for_mass"])
        branched = stl_report(nonmanifold_edge())
        self.assertGreater(branched["edges_exact"]["nonmanifold_edges"], 0)
        self.assertFalse(branched["volume_used_for_mass"])
        broken = stl_report(nonfinite_triangle())
        self.assertFalse(broken["finite"])
        self.assertFalse(broken["watertight_exact"])
        self.assertIsNone(broken["volume_signed_mm3"])
        flat = stl_report(degenerate_face())
        self.assertGreater(flat["degenerate_faces_exact"], 0)
        self.assertFalse(flat["volume_used_for_mass"])

    def test_inverted_and_disconnected_meshes_do_not_become_mass(self):
        inverted = stl_report(inverted_box())
        self.assertTrue(inverted["watertight_exact"])
        self.assertTrue(inverted["winding_consistent_exact"])
        self.assertLess(inverted["volume_signed_mm3"], 0.0)
        self.assertAlmostEqual(inverted["volume_signed_mm3"], -6000.0, places=6)
        self.assertFalse(inverted["volume_used_for_mass"])
        self.assertIsNone(mass_g_from_mm3(inverted["volume_signed_mm3"]))
        pair = stl_report(two_closed_boxes())
        self.assertTrue(pair["watertight_exact"])
        self.assertGreater(pair["volume_signed_mm3"], 0.0)
        self.assertEqual(pair["components_exact"], 2)
        self.assertFalse(pair["volume_used_for_mass"])

    def test_near_coincident_gap_survives_exact_merge(self):
        mesh = near_coincident_gap()
        report = stl_report(mesh)
        self.assertFalse(report["coordinates_moved"])
        self.assertFalse(report["rounded_merge"])
        self.assertGreater(report["edges_exact"]["boundary_edges"], 0)
        self.assertFalse(report["watertight_exact"])
        rounded = mesh.copy()
        rounded.merge_vertices()
        self.assertTrue(rounded.is_watertight)

    def test_untyped_mass_arguments_do_not_pass(self):
        bad = [True, False, float("nan"), float("inf"), float("-inf"), "1.0", None]
        for value in bad:
            self.assertNotEqual(mass_check(value, 1.0, 0.01)["status"], "PASS")
            self.assertNotEqual(mass_check(1.0, value, 0.01)["status"], "PASS")
            self.assertNotEqual(mass_check(1.0, 1.0, value)["status"], "PASS")
        self.assertEqual(mass_check(1.0, 1.0, True)["status"], "UNAVAILABLE")
        self.assertEqual(mass_check(1.0, 1.0, float("inf"))["status"], "UNAVAILABLE")
        self.assertIsNone(real_number(True))
        self.assertIsNone(mass_g_from_mm3(float("nan")))
        self.assertIsNone(mass_g_from_mm3(-1.0))

    def test_integer_mass_overflow_is_unavailable(self):
        self.assertIsNone(real_number(10**400))
        overflow = mass_check(10**400, 1.0, 0.01)
        self.assertEqual(overflow["status"], "UNAVAILABLE")
        self.assertIsNone(overflow["rel"])
        self.assertEqual(mass_check(26.58, 26.58, 0.0)["status"], "PASS")
        self.assertEqual(real_number(10), 10.0)

    def test_strict_json_rejects_nonfinite_numbers(self):
        with self.assertRaises(ValueError):
            dump_strict({"value": float("nan")})
        with self.assertRaises(ValueError):
            dump_strict({"value": float("inf")})
        text = dump_strict({"value": 1.0, "flag": False})
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)
        json.loads(text)

    def test_strict_json_rejects_nonstring_keys(self):
        with self.assertRaises(TypeError):
            dump_strict({1: {"status": "FAIL"}, "1": {"status": "PASS"}})
        with self.assertRaises(TypeError):
            dump_strict({"outer": {1: {"status": "FAIL"}, "1": {"status": "PASS"}}})
        text = dump_strict({"1": {"status": "FAIL"}, "2": {"status": "PASS"}})
        loaded = json.loads(text)
        self.assertEqual(set(loaded), {"1", "2"})
        self.assertEqual(loaded["1"]["status"], "FAIL")
        self.assertEqual(loaded["2"]["status"], "PASS")

    def test_missing_pin_is_unavailable(self):
        with self.assertRaises(PinUnavailable):
            read_pinned_object("0" * 40, SUBJECTS["C10c"]["readme"])
        source = (ROOT / "ops/science_tests/native_cad/evaluate.py").read_text()
        self.assertNotIn("git fetch", source)
        self.assertNotIn("ls-remote", source)

    def test_full_commit_id_rejects_revision_and_blob(self):
        path = SUBJECTS["C10a"]["readme"]
        pinned = read_pinned_object(PIN_COMMIT, path)
        self.assertIn(SUBJECTS["C10a"]["claim_snippets"]["identity"].encode(), pinned)
        expression = "HEAD" + "~0" * 18
        self.assertEqual(len(expression), 40)
        with self.assertRaises(PinUnavailable):
            read_pinned_object(expression, path)
        blob = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", f"{PIN_COMMIT}:{path}"],
            text=True,
        ).strip()
        self.assertEqual(len(blob), 40)
        self.assertNotEqual(blob, PIN_COMMIT)
        with self.assertRaises(PinUnavailable):
            read_pinned_object(blob, path)

    def test_rigid_transform_and_repeat_keep_box_volume(self):
        mesh = analytic_box()
        transform = trimesh.transformations.rotation_matrix(0.4, [0.2, 0.5, 0.8])
        transform[:3, 3] = [12.0, -4.0, 3.0]
        moved, original = rigid_volume(mesh, transform)
        self.assertAlmostEqual(moved, original, places=6)
        self.assertTrue(np.allclose(mesh.vertices, analytic_box().vertices))
        again = stl_report(analytic_box())
        self.assertAlmostEqual(again["volume_signed_mm3"], original, places=6)
        opened = open_box()
        shift = np.eye(4)
        shift[:3, 3] = [50.0, -20.0, 5.0]
        moved_open, original_open = rigid_volume(opened, shift)
        opened_report = stl_report(opened)
        self.assertFalse(opened_report["volume_used_for_mass"])
        self.assertTrue(np.isfinite([moved_open, original_open]).all())

    def test_asset_hash_is_identity_only(self):
        c10a, c10a_tmp = resolve_pinned(SUBJECTS["C10a"]["stl"], SUBJECTS["C10a"]["stl_sha256"])
        c10c, c10c_tmp = resolve_pinned(SUBJECTS["C10c"]["stl"], SUBJECTS["C10c"]["stl_sha256"])
        try:
            self.assertTrue(asset_sha256_matches(SUBJECTS["C10a"]["stl_sha256"], c10a))
            self.assertFalse(asset_sha256_matches(SUBJECTS["C10a"]["stl_sha256"], c10c))
            self.assertFalse(asset_sha256_matches(SUBJECTS["C10c"]["step_sha256"], c10a))
        finally:
            if c10a_tmp is not None:
                c10a_tmp.unlink(missing_ok=True)
            if c10c_tmp is not None:
                c10c_tmp.unlink(missing_ok=True)
        source = (ROOT / "ops/science_tests/native_cad/evaluate.py").read_text()
        self.assertNotIn("def certificate_applies", source)
        self.assertIn("Identity only", source)

    def test_geometry_module_does_not_fill_or_weld(self):
        source = (ROOT / "ops/science_tests/native_cad/geometry.py").read_text()
        self.assertNotIn("fill_holes", source)
        self.assertNotIn("trimesh.repair", source)
        self.assertNotIn(".merge_vertices(", source)


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = {name: evaluate_subject(name) for name in ("C10a", "C10c")}
        cls.historical = HISTORICAL_RECEIPT.read_bytes()
        cls.attempt_dir = tempfile.TemporaryDirectory()
        cls.attempt = write_attempt(
            cls.attempt_dir.name,
            argv=["python", "-m", "ops.science_tests.native_cad.attempt", cls.attempt_dir.name],
            reports=[cls.reports["C10a"], cls.reports["C10c"]],
        )
        cls.markdown = (Path(cls.attempt_dir.name) / "NATIVE_CAD_VALIDATION.md").read_text()

    @classmethod
    def tearDownClass(cls):
        cls.attempt_dir.cleanup()

    def test_attempt_leaves_the_historical_receipt(self):
        digest = hashlib.sha256(HISTORICAL_RECEIPT.read_bytes()).hexdigest()
        self.assertEqual(digest, HISTORICAL_RECEIPT_SHA256)
        self.assertEqual(HISTORICAL_RECEIPT.read_bytes(), self.historical)
        receipt_text = (Path(self.attempt_dir.name) / "receipt.json").read_text()
        self.assertNotIn("NaN", receipt_text)
        self.assertNotIn("Infinity", receipt_text)
        loaded = json.loads(receipt_text)
        self.assertEqual(loaded["data_pin"], PIN_COMMIT)
        self.assertEqual(loaded["code_git_head"], self.attempt["code_git_head"])
        self.assertIn("argv", loaded)
        self.assertEqual(loaded["exit_code"], 0)
        self.assertIn("python", loaded["environment"])
        self.assertEqual(loaded["input_sha256"]["C10a"]["step"], SUBJECTS["C10a"]["step_sha256"])
        self.assertTrue(loaded["code_module_sha256"]["geometry.py"])

    def test_identity_is_the_e150bb9_pin(self):
        for name, report in self.reports.items():
            self.assertEqual(report["pin_commit"], PIN_COMMIT)
            self.assertTrue(report["identity_ok"])
            self.assertEqual(report["step"]["sha256"], SUBJECTS[name]["step_sha256"])
            self.assertEqual(report["stl"]["sha256"], SUBJECTS[name]["stl_sha256"])
            self.assertIsNone(SUBJECTS[name]["genome_id"])
            self.assertEqual(report["genome_binding"], "INCOMPLETE")
            self.assertFalse(report["pipeline_eligible"])
            self.assertFalse(report["physical_qualification"])
            self.assertNotEqual(report["candidate_status"], "PASS")

    def test_c10c_open_mesh_remains_a_candidate_failure(self):
        report = self.reports["C10c"]
        self.assertTrue(report["archived"])
        self.assertEqual(report["role"], "archived_diagnostic")
        self.assertFalse(report["stl"]["watertight_exact"])
        self.assertGreater(report["stl"]["edges_exact"]["boundary_edges"], 0)
        self.assertEqual(report["stl"]["edges_exact"]["nonmanifold_edges"], 0)
        self.assertFalse(report["stl"]["volume_used_for_mass"])
        self.assertIn("stl", report["geometry_flags"])
        self.assertIn("boundary", report["geometry_flags"])
        self.assertEqual(report["candidate_status"], "FAIL")
        self.assertIn("S08", report["s08_gap"])
        self.assertEqual(report["mass"]["stl_vs_readme"]["status"], "UNAVAILABLE")

    def test_carried_cases_are_not_native_passes(self):
        rows = {row["case"]: row for row in self.reports["C10c"]["provenance"]}
        self.assertEqual(rows["V3"]["reported_class"], "reported_direct_unverified")
        self.assertFalse(rows["V3"]["verified_native_measurement"])
        self.assertEqual(rows["GateS"]["reported_class"], "reported_direct_unverified")
        self.assertFalse(rows["GateS"]["verified_native_measurement"])
        for case_id in ("V1", "V2", "V4", "V5", "V6", "V7"):
            self.assertEqual(rows[case_id]["reported_class"], "reported_carried_or_ratio")
            self.assertFalse(rows[case_id]["verified_native_measurement"])
        self.assertEqual(self.reports["C10c"]["fitness_status"], "REPORTED_NOT_QUALIFIED")

    def test_step_is_one_declared_millimetre_solid(self):
        for report in self.reports.values():
            self.assertTrue(report["step"]["valid"])
            self.assertEqual(report["step"]["solids"], 1)
            self.assertEqual(report["step"]["units"], "mm")
            self.assertEqual(report["step"]["units_source"], "step_declaration")
            self.assertEqual(report["step"]["declared_length_unit"], "millimetre")
            self.assertEqual(report["step"]["reader_length_units"], ["millimetre"])
            self.assertTrue(report["step"]["units_agree"])
            self.assertAlmostEqual(report["step"]["normalized_system_length_unit"], 1.0, places=9)
            self.assertGreater(report["step"]["volume_mm3"], 1000.0)
            self.assertEqual(report["step"]["bounds_compared"]["method"], "BRepBndLib.AddOptimal_s")
            self.assertFalse(report["step"]["bounds_loose"]["use_for_comparison"])

    def test_repeat_evaluation_matches(self):
        again = evaluate_subject("C10a")
        first = self.reports["C10a"]
        self.assertEqual(again["stl"]["volume_signed_mm3"], first["stl"]["volume_signed_mm3"])
        self.assertEqual(again["step"]["volume_mm3"], first["step"]["volume_mm3"])
        self.assertEqual(again["candidate_status"], first["candidate_status"])

    def test_report_does_not_waive_the_candidate(self):
        text = self.markdown
        self.assertEqual(text, render_markdown([self.reports["C10a"], self.reports["C10c"]]))
        self.assertIn("archived diagnostic", text)
        self.assertIn("INCOMPLETE", text)
        self.assertIn("physical qualification", text)
        self.assertIn("FAIL", text)
        self.assertIn("verified_native_measurement False", text)
        self.assertIn("does not fetch", text)
        self.assertNotIn("all 178", text.lower())
        self.assertNotIn("all178", text.lower())
        self.assertNotIn("direct_native", text)


class EarlierRevisionPins(unittest.TestCase):
    """C.9.2 and C.9.3 use the same pin rules as C.10a. They are not product passes."""

    @classmethod
    def setUpClass(cls):
        cls.reports = {name: evaluate_subject(name) for name in ("C92", "C93")}

    def test_identity_sentences_are_in_the_pinned_readme(self):
        for name in ("C92", "C93"):
            text = read_pin(SUBJECTS[name]["readme"]).decode()
            self.assertIn(SUBJECTS[name]["claim_snippets"]["identity"], text)
            self.assertIsNone(SUBJECTS[name]["genome_id"])

    def test_step_mass_and_stl_are_measured(self):
        for name, report in self.reports.items():
            self.assertTrue(report["identity_ok"])
            self.assertEqual(report["step"]["solids"], 1)
            self.assertEqual(report["step"]["units"], "mm")
            self.assertEqual(report["step"]["units_source"], "step_declaration")
            self.assertEqual(report["mass"]["step_vs_readme"]["status"], "PASS")
            self.assertTrue(report["stl"]["watertight_exact"])
            self.assertEqual(report["mass"]["stl_vs_readme"]["status"], "PASS")
            self.assertEqual(report["geometry_status"], "PASS")
            self.assertEqual(report["genome_binding"], "INCOMPLETE")
            self.assertEqual(report["candidate_status"], "INCOMPLETE")
            self.assertFalse(report["pipeline_eligible"])
            self.assertFalse(report["physical_qualification"])


if __name__ == "__main__":
    unittest.main()
