"""Candidate reports for pinned native CAD. Failures stay visible.

Pinned bytes are read with ``git show <pin>:<path>`` from a clone that
already contains that commit. This module does not fetch. A missing git
object raises PinUnavailable. That is a dependency error, not a pass.

Historical receipt ``receipts/native_cad_e150bb9.json`` is immutable.
Fresh output goes to an attempt directory via ``write_attempt``.
"""

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh

from ops.science_tests.native_cad import provenance
from ops.science_tests.native_cad.geometry import (
    load_step,
    load_stl,
    mass_check,
    mass_g_from_mm3,
    real_number,
    sha256_file,
)
from ops.science_tests.native_cad.pins import (
    PIN_COMMIT,
    STEP_README_REL_TOL,
    STL_README_REL_TOL,
    SUBJECTS,
)

ROOT = Path(__file__).resolve().parents[3]
HISTORICAL_RECEIPT = ROOT / "ops/science_tests/native_cad/receipts/native_cad_e150bb9.json"
HISTORICAL_RECEIPT_SHA256 = "d4f8bf474af0cd18426021e44cfb668abd0308aedbbd85344a1309f78cb514d0"
S08_GAP = (
    "S08 native CAD adapter is not established. This diagnostic does not "
    "bind a genome, mesh, load, material, or observable, and it does not "
    "run fresh FEM. Integration owns assurance/adapters and the certified "
    "evaluator. No physical qualification is claimed."
)
PIN_ACCESS = (
    "An approved runner obtains a pinned file with "
    f"`git show {PIN_COMMIT}:<path>` from a repository that already has that "
    "commit. This diagnostic does not fetch from a remote and does not "
    "treat a missing object as a pass."
)


class PinUnavailable(RuntimeError):
    """The pinned Git object is not in this clone. No fetch was attempted."""


class AttemptRefused(RuntimeError):
    """Completed or partial attempt output already exists. No bytes were changed."""


_ATTEMPT_OUTPUTS = (
    "receipt.json",
    "NATIVE_CAD_VALIDATION.md",
    ".attempt-partial",
    ".receipt.json.partial",
    ".NATIVE_CAD_VALIDATION.md.partial",
)


_FULL_COMMIT_ID = re.compile(r"^[0-9a-fA-F]{40}$")


def read_pinned_object(commit, repo_path):
    """Return blob bytes at a full commit id. Missing objects raise PinUnavailable."""
    if not isinstance(commit, str) or _FULL_COMMIT_ID.fullmatch(commit) is None:
        raise PinUnavailable(f"pinned commit {commit!r} is not a full object id")
    kind = subprocess.run(
        ["git", "cat-file", "-t", commit],
        cwd=ROOT,
        capture_output=True,
    )
    if kind.returncode != 0 or kind.stdout.strip() != b"commit":
        raise PinUnavailable(
            f"Pinned object {commit} is not a commit in this clone. " + PIN_ACCESS
        )
    proc = subprocess.run(
        ["git", "show", f"{commit}:{repo_path}"],
        cwd=ROOT,
        capture_output=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip().splitlines()
        tail = detail[-1] if detail else "git show failed"
        raise PinUnavailable(
            f"Pinned object {commit}:{repo_path} is unavailable ({tail}). "
            + PIN_ACCESS
        )
    return proc.stdout


def read_pin(repo_path):
    """Bytes of a path at the pin commit, whether or not later main still has it."""
    return read_pinned_object(PIN_COMMIT, repo_path)


def _git_show(repo_path, destination):
    destination.write_bytes(read_pin(repo_path))


def resolve_pinned(repo_path, expected_sha):
    """Use the worktree file when it still matches the e150bb9 pin.

    After a revert, materialize the blob from that commit into a temp file.
    Never write the archived CAD back into the tree. Never fetch.
    """
    candidate = ROOT / repo_path
    if candidate.is_file() and sha256_file(candidate) == expected_sha:
        return candidate, None
    handle = tempfile.NamedTemporaryFile(prefix="pinned-", delete=False)
    handle.close()
    path = Path(handle.name)
    try:
        _git_show(repo_path, path)
    except PinUnavailable:
        path.unlink(missing_ok=True)
        raise
    actual = sha256_file(path)
    if actual != expected_sha:
        path.unlink(missing_ok=True)
        raise PinUnavailable(
            f"pin mismatch for {repo_path}: {actual}. " + PIN_ACCESS
        )
    return path, path


def _worse(left, right):
    rank = {"PASS": 0, "INCOMPLETE": 1, "FAIL": 2}
    return left if rank[left] >= rank[right] else right


def _source_rows(subject, spec):
    rows = []
    for case_id, text in spec.get("sources", {}).items():
        kind = provenance.reported_provenance(text, subject=subject)
        rows.append(
            {
                "case": case_id,
                "source": text,
                "reported_class": kind,
                "verified_native_measurement": provenance.verified_native_measurement(text),
            }
        )
    return rows


def _stl_problem_flags(stl):
    flags = []
    if not stl.get("finite"):
        flags.append("nonfinite")
    edges = stl.get("edges_exact") or {}
    if stl.get("finite"):
        if not stl.get("watertight_exact"):
            flags.append("boundary")
        if edges.get("nonmanifold_edges"):
            flags.append("nonmanifold")
        if stl.get("winding_consistent_exact") is not True:
            flags.append("winding")
        if stl.get("degenerate_faces_exact"):
            flags.append("degenerate")
        if stl.get("components_exact") != 1:
            flags.append("components")
    volume = stl.get("volume_signed_mm3")
    if real_number(volume) is None or volume <= 0.0:
        flags.append("signed_volume")
    return flags


def _measurement(volume_mm3, claim_g, tolerance, use_for_mass):
    if not use_for_mass:
        return None, {
            "status": "UNAVAILABLE",
            "rel": None,
            "tolerance": tolerance,
            "reason": "volume_not_a_mass_input",
        }
    mass = None if volume_mm3 is None else mass_g_from_mm3(volume_mm3)
    if mass is None:
        return None, {
            "status": "UNAVAILABLE",
            "rel": None,
            "tolerance": tolerance,
            "reason": "non_positive_or_untyped_volume",
        }
    return mass, mass_check(mass, claim_g, tolerance)


def evaluate_subject(subject):
    spec = SUBJECTS[subject]
    step_path, step_tmp = resolve_pinned(spec["step"], spec["step_sha256"])
    stl_path, stl_tmp = resolve_pinned(spec["stl"], spec["stl_sha256"])
    try:
        step = load_step(step_path)
        _mesh, stl = load_stl(stl_path)
        step["path"] = spec["step"]
        stl["path"] = spec["stl"]
    finally:
        if step_tmp is not None:
            step_tmp.unlink(missing_ok=True)
        if stl_tmp is not None:
            stl_tmp.unlink(missing_ok=True)
    step_mass, step_mass_check = _measurement(
        step.get("volume_mm3"),
        spec["readme_mass_g"],
        STEP_README_REL_TOL,
        bool(step.get("volume_positive")) and step.get("units") == "mm",
    )
    stl_mass, stl_mass_check = _measurement(
        stl.get("volume_signed_mm3"),
        spec["readme_mass_g"],
        STL_README_REL_TOL,
        bool(stl.get("volume_used_for_mass")),
    )
    identity_ok = (
        step.get("sha256") == spec["step_sha256"] and stl.get("sha256") == spec["stl_sha256"]
    )
    geometry_flags = []
    if not identity_ok:
        geometry_flags.append("identity")
    step_ok = (
        step.get("valid")
        and step.get("solids") == 1
        and step.get("units") == "mm"
        and step.get("units_source") == "step_declaration"
        and step.get("units_agree") is True
        and step.get("volume_positive") is True
    )
    if not step_ok:
        geometry_flags.append("step")
    stl_flags = _stl_problem_flags(stl)
    if stl_flags:
        geometry_flags.append("stl")
        geometry_flags.extend(stl_flags)
    if step_mass_check["status"] != "PASS" or stl_mass_check["status"] != "PASS":
        geometry_flags.append("mass")
    geometry_status = "FAIL" if geometry_flags else "PASS"
    binding = provenance.binding_status(spec.get("genome_id"))
    # Missing binding stays INCOMPLETE. An open or inconsistent mesh stays FAIL.
    overall = _worse(geometry_status, "INCOMPLETE" if binding == "INCOMPLETE" else "PASS")
    if overall == "PASS":
        overall = "INCOMPLETE"
    return {
        "subject": subject,
        "role": spec["role"],
        "archived": spec["archived"],
        "pin_commit": PIN_COMMIT,
        "product_claim": False,
        "pipeline_eligible": False,
        "identity_ok": identity_ok,
        "step": step,
        "stl": stl,
        "mass": {
            "density_g_per_cc": 4.43,
            "density_is_material_qualification": False,
            "readme_g": spec["readme_mass_g"],
            "step_g": step_mass,
            "stl_g": stl_mass,
            "step_vs_readme": step_mass_check,
            "stl_vs_readme": stl_mass_check,
        },
        "reported_fitness": spec["reported_fitness"],
        "fitness_status": "REPORTED_NOT_QUALIFIED",
        "provenance": _source_rows(subject, spec),
        "genome_binding": binding,
        "geometry_status": geometry_status,
        "geometry_flags": geometry_flags,
        "candidate_status": overall,
        "s08_gap": S08_GAP,
        "physical_qualification": False,
    }


def asset_sha256_matches(expected_sha256, asset_path):
    """True when the file bytes have this sha256. Identity only, not a certificate."""
    return sha256_file(asset_path) == expected_sha256


def render_markdown(reports):
    lines = [
        "# Native CAD validation — science v1 diagnostic",
        "",
        "Pinned to commit `e150bb906e8b8a265077de60ee148f6ba773a83a`.",
        "C.10a is the comparison baseline. C.10c is an archived diagnostic subject",
        "after revert `#68` and is not a standard-pipeline candidate.",
        "No genome binding exists. No fresh FEM was run. Nothing here is a",
        "physical qualification or a manufacturing release.",
        "",
        S08_GAP,
        "",
        PIN_ACCESS,
        "",
        "STEP length units come from the file's LENGTH_UNIT entity, or from the",
        "analytic constructor when the shape was built in millimetres. Extent is",
        "not a unit. Compared bounds use `BRepBndLib.AddOptimal_s`. `Add_s` is",
        "labeled and is not treated as a dimension error.",
        "",
        "Mass uses Gr5 density 4.43 g/cm³ and the drawing factor `mm³ × 4.43e-3`",
        "only for a positive signed volume. This is density arithmetic, not a",
        "measured material. STL mass is unavailable unless the exact-merged mesh",
        "is one finite, watertight, winding-consistent component with no",
        "degenerate or nonmanifold edges. An open, inverted, or disconnected",
        "mesh stays a candidate failure. Meshes are not hole-filled or rounded.",
        "",
        "Published case text is a reported class only. Verified native",
        "measurement stays false until an S08 exact-subject certificate exists.",
        "The historical receipt `native_cad_e150bb9.json` is unchanged.",
        "",
    ]
    for report in reports:
        lines.append(f"## {report['subject']} ({report['role']})")
        lines.append("")
        lines.append(f"- Candidate status: **{report['candidate_status']}**.")
        lines.append(
            f"- Geometry status: {report['geometry_status']} "
            f"({', '.join(report['geometry_flags']) or 'none'})."
        )
        lines.append(f"- Genome binding: {report['genome_binding']}. Pipeline eligible: false.")
        step = report["step"]
        stl = report["stl"]
        tight = step.get("bounds_compared") or {}
        loose = step.get("bounds_loose") or {}
        lines.append(
            f"- STEP solids {step['solids']}, valid {step['valid']}, "
            f"units {step['units']} via {step.get('units_source')}, "
            f"declared {step.get('declared_length_unit')} ({step.get('declared_units_source')}), "
            f"reader units {step.get('reader_length_units')}, "
            f"normalized system length {step.get('normalized_system_length_unit')}, "
            f"agree {step.get('units_agree')}, "
            f"volume {step['volume_mm3']} mm³, mass {report['mass']['step_g']} g "
            f"({report['mass']['step_vs_readme']['status']})."
        )
        lines.append(
            f"- STEP compared bounds ({tight.get('method')}): {tight.get('extents')}. "
            f"Loose bounds ({loose.get('method')}): {loose.get('extents')}."
        )
        edges = stl.get("edges_exact") or {}
        lines.append(
            f"- STL merge {stl.get('merge_method')}, watertight {stl.get('watertight_exact')}, "
            f"winding {stl.get('winding_consistent_exact')}, "
            f"components {stl.get('components_exact')}, "
            f"degenerate faces {stl.get('degenerate_faces_exact')}, "
            f"boundary edges {edges.get('boundary_edges')}, "
            f"nonmanifold edges {edges.get('nonmanifold_edges')}, "
            f"finite {stl.get('finite')}, "
            f"signed volume {stl.get('volume_signed_mm3')} mm³, "
            f"mass input {stl.get('volume_used_for_mass')}, "
            f"mass {report['mass']['stl_g']} g "
            f"({report['mass']['stl_vs_readme']['status']})."
        )
        lines.append(f"- Reported fitness {report['reported_fitness']} is {report['fitness_status']}.")
        if report["provenance"]:
            lines.append("- Case sources (reported, not verified):")
            for row in report["provenance"]:
                lines.append(
                    f"  - {row['case']}: {row['reported_class']} "
                    f"(verified_native_measurement {row['verified_native_measurement']}) "
                    f"— {row['source']}"
                )
        lines.append("")
    lines.append("Analytic box controls live in the unit tests and are not knife subjects.")
    lines.append("T05's twelve challenge groups are not claimed. This file is the isolated native-CAD subset only.")
    lines.append("")
    return "\n".join(lines)


def dump_strict(payload):
    """JSON text. NaN, Infinity, and nonstring keys raise instead of being written."""
    return json.dumps(_json_ready(payload), indent=2, sort_keys=True, allow_nan=False) + "\n"


def _json_ready(value):
    if isinstance(value, dict):
        ready = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"unsupported JSON key {type(key).__name__}")
            ready[key] = _json_ready(item)
        return ready
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not np.isfinite(number):
            raise ValueError("nonfinite JSON value")
        return number
    raise TypeError(f"unsupported JSON value {type(value).__name__}")


def _git_capture(args):
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _module_sha256():
    folder = Path(__file__).resolve().parent
    digests = {}
    for path in sorted(folder.glob("*.py")):
        digests[path.name] = sha256_file(path)
    return digests


def _environment():
    ocp_version = None
    try:
        import OCP

        ocp_version = getattr(OCP, "__version__", None)
    except ImportError:
        ocp_version = None
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "trimesh": trimesh.__version__,
        "ocp": ocp_version,
        "executable": sys.executable,
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
    }


def _attempt_blocked(attempt_dir):
    if attempt_dir.exists() and not attempt_dir.is_dir():
        return True
    return any((attempt_dir / name).exists() for name in _ATTEMPT_OUTPUTS)


def _exclusive_text(path, text):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


def _refuse_existing_attempt(attempt_dir):
    if attempt_dir.resolve() == HISTORICAL_RECEIPT.resolve():
        raise AttemptRefused("historical receipt is immutable")
    if attempt_dir.resolve() == HISTORICAL_RECEIPT.parent.resolve():
        raise AttemptRefused("refusing to write into the historical receipt directory")
    if _attempt_blocked(attempt_dir):
        raise AttemptRefused(
            f"attempt output already exists in {attempt_dir}; leaving those bytes unchanged"
        )


def write_attempt(attempt_dir, argv, reports=None):
    """Create one attempt. A second write, or a partial directory, is refused.

    The receipt is published after the markdown. Existing bytes are not opened
    for writing. The historical receipt is not a destination.
    """
    attempt_dir = Path(attempt_dir)
    if HISTORICAL_RECEIPT.is_file() and sha256_file(HISTORICAL_RECEIPT) != HISTORICAL_RECEIPT_SHA256:
        raise RuntimeError("historical receipt hash changed; leaving it untouched")
    _refuse_existing_attempt(attempt_dir)
    reports = list(reports) if reports is not None else [evaluate_subject(name) for name in ("C10a", "C10c")]
    status = _git_capture(["status", "--porcelain"])
    payload = {
        "attempt_dir": str(attempt_dir),
        "argv": [str(item) for item in argv],
        "exit_code": 0,
        "finite_output": True,
        "code_git_head": _git_capture(["rev-parse", "HEAD"]),
        "code_status_porcelain": status,
        "code_module_sha256": _module_sha256(),
        "data_pin": PIN_COMMIT,
        "historical_receipt": str(HISTORICAL_RECEIPT.relative_to(ROOT)),
        "historical_receipt_sha256": HISTORICAL_RECEIPT_SHA256,
        "environment": _environment(),
        "input_sha256": {
            name: {"step": spec["step_sha256"], "stl": spec["stl_sha256"]}
            for name, spec in SUBJECTS.items()
        },
        "candidate_counts": {
            report["subject"]: report["candidate_status"]
            for report in reports
            if isinstance(report, dict) and "subject" in report and "candidate_status" in report
        },
        "pin_access": PIN_ACCESS,
        "pin_commit": PIN_COMMIT,
        "subjects": reports,
    }
    text = dump_strict(payload)
    markdown = render_markdown(reports)
    _refuse_existing_attempt(attempt_dir)
    attempt_dir.mkdir(parents=True, exist_ok=True)
    partial = attempt_dir / ".attempt-partial"
    try:
        _exclusive_text(partial, "reserved\n")
    except FileExistsError:
        raise AttemptRefused(
            f"attempt reservation already exists in {attempt_dir}; leaving those bytes unchanged"
        ) from None
    try:
        _exclusive_text(attempt_dir / "NATIVE_CAD_VALIDATION.md", markdown)
        _exclusive_text(attempt_dir / "receipt.json", text)
    except FileExistsError:
        raise AttemptRefused(
            f"attempt output appeared in {attempt_dir}; existing bytes were not replaced"
        ) from None
    partial.unlink()
    if sha256_file(HISTORICAL_RECEIPT) != HISTORICAL_RECEIPT_SHA256:
        raise RuntimeError("historical receipt was modified")
    return payload


def write_outputs(reports, receipt_path, markdown_path):
    """Strict writer. Refuses an existing destination instead of replacing it."""
    receipt_path = Path(receipt_path)
    markdown_path = Path(markdown_path)
    if receipt_path.resolve() == HISTORICAL_RECEIPT.resolve():
        raise AttemptRefused("historical receipt is immutable")
    if receipt_path.exists() or markdown_path.exists():
        raise AttemptRefused("output already exists; leaving those bytes unchanged")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pin_commit": PIN_COMMIT, "subjects": reports}
    _exclusive_text(markdown_path, render_markdown(reports))
    _exclusive_text(receipt_path, dump_strict(payload))
