"""STEP and STL measurements. Meshes are not filled, welded, or repaired."""

import hashlib
import math
import re
from pathlib import Path

import numpy as np
import trimesh
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TColStd import TColStd_SequenceOfAsciiString
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from trimesh import grouping

from ops.science_tests.native_cad.pins import DENSITY_G_PER_CC

_SI_ENTITY = re.compile(
    r"#\d+\s*=\s*\(\s*LENGTH_UNIT\s*\(\s*\)\s*NAMED_UNIT\s*\(\s*\*\s*\)\s*"
    r"SI_UNIT\s*\(\s*(\.[A-Z]+\.|\$)\s*,\s*\.METRE\.\s*\)",
    re.IGNORECASE,
)
_CONVERSION_ENTITY = re.compile(
    r"#\d+\s*=\s*\(\s*LENGTH_UNIT\s*\(\s*\)\s*NAMED_UNIT\s*\(\s*\*\s*\)\s*"
    r"CONVERSION_BASED_UNIT\s*\(\s*'([^']*)'",
    re.IGNORECASE,
)
_SI_PREFIX = {
    ".MILLI.": ("mm", "millimetre"),
    ".CENTI.": ("centimetre", "centimetre"),
    ".MICRO.": ("micrometre", "micrometre"),
    ".KILO.": ("kilometre", "kilometre"),
    "$": ("metre", "metre"),
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def real_number(value):
    """Finite int or float. Booleans, non-numeric values, and overflow are rejected."""
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    if not np.isfinite(number):
        return None
    return number


def mass_g_from_mm3(volume_mm3):
    """Positive mm^3 times 4.43 g/cm^3 times 1e-3.

    A negative signed volume is inverted geometry. It is not a mass.
    """
    volume = real_number(volume_mm3)
    if volume is None or volume <= 0.0:
        return None
    scaled = volume * DENSITY_G_PER_CC
    if not math.isfinite(scaled):
        return None
    mass = scaled * 1e-3
    if not math.isfinite(mass):
        return None
    return mass


def _unavailable(reason):
    return {"status": "UNAVAILABLE", "rel": None, "tolerance": None, "reason": reason}


def relative_delta(measured, claim):
    measured_n = real_number(measured)
    claim_n = real_number(claim)
    if measured_n is None or claim_n is None or measured_n <= 0.0 or claim_n <= 0.0:
        return None
    delta = measured_n - claim_n
    if not math.isfinite(delta):
        return None
    rel = abs(delta) / claim_n
    if not math.isfinite(rel):
        return None
    return rel


def mass_check(measured_g, claim_g, tolerance):
    """PASS only for positive finite masses inside a finite non-negative tolerance.

    Booleans, NaN, Infinity, nonpositive masses, and overflow are UNAVAILABLE.
    """
    measured = real_number(measured_g)
    claim = real_number(claim_g)
    tol = real_number(tolerance)
    if measured is None or claim is None or tol is None or tol < 0.0:
        return _unavailable("non_finite_or_untyped")
    if measured <= 0.0 or claim <= 0.0:
        return _unavailable("nonpositive_mass")
    delta = measured - claim
    if not math.isfinite(delta):
        return _unavailable("overflow")
    rel = abs(delta) / claim
    if not math.isfinite(rel):
        return _unavailable("overflow")
    status = "PASS" if rel <= tol else "FAIL"
    return {"status": status, "rel": rel, "tolerance": tol}


def _edge_counts(mesh):
    if len(mesh.faces) == 0:
        return {"boundary_edges": 0, "manifold_edges": 0, "nonmanifold_edges": 0}
    edges = np.asarray(mesh.edges_sorted)
    if len(edges) == 0:
        return {"boundary_edges": 0, "manifold_edges": 0, "nonmanifold_edges": 0}
    _unique, inverse = grouping.unique_rows(edges)
    counts = np.bincount(inverse)
    return {
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "manifold_edges": int(np.count_nonzero(counts == 2)),
        "nonmanifold_edges": int(np.count_nonzero(counts > 2)),
    }


def _component_count(mesh):
    face_count = len(mesh.faces)
    if face_count == 0:
        return 0
    parent = list(range(face_count))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    adjacency = np.asarray(mesh.face_adjacency)
    for edge in adjacency:
        left = find(int(edge[0]))
        right = find(int(edge[1]))
        if left != right:
            parent[right] = left
    return len({find(index) for index in range(face_count)})


def exact_coordinate_merge(mesh):
    """Merge only identical stored coordinates. Points are not moved or rounded."""
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if vertices.size == 0 or not np.isfinite(vertices).all():
        return None
    packed = np.ascontiguousarray(vertices, dtype=np.float64)
    width = packed.dtype.itemsize * packed.shape[1]
    rows = packed.view(np.dtype((np.void, width))).ravel()
    _unique, index, inverse = np.unique(rows, return_index=True, return_inverse=True)
    merged = trimesh.Trimesh(packed[index], inverse[faces], process=False)
    return {
        "mesh": merged,
        "unique_index": index,
        "inverse": inverse,
        "coordinates_moved": False,
    }


def _empty_stl(mesh, finite):
    return {
        "finite": finite,
        "vertices_raw": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "vertices_exact": None,
        "merge_method": "exact_coordinate",
        "coordinates_moved": False,
        "rounded_merge": False,
        "watertight_exact": False,
        "winding_consistent_exact": None,
        "degenerate_faces_exact": None,
        "components_exact": None,
        "edges_raw": None,
        "edges_exact": None,
        "volume_signed_mm3": None,
        "volume_used_for_mass": False,
        "extents_mm": None,
        "hole_fill": False,
    }


def stl_report(mesh):
    """Topology after exact-coordinate duplicate merging. No hole fill."""
    vertices = np.asarray(mesh.vertices, dtype=float)
    finite = bool(vertices.size and np.isfinite(vertices).all())
    if not finite:
        return _empty_stl(mesh, False)
    raw_edges = _edge_counts(mesh)
    merged_info = exact_coordinate_merge(mesh)
    merged = merged_info["mesh"]
    merged_edges = _edge_counts(merged)
    areas = np.asarray(merged.area_faces, dtype=float)
    degenerate = int(np.count_nonzero(~np.isfinite(areas) | (areas <= 1e-16))) if areas.size else 0
    winding = bool(merged.is_winding_consistent)
    watertight = bool(merged.is_watertight)
    components = _component_count(merged)
    raw_volume = float(merged.volume)
    volume = raw_volume if math.isfinite(raw_volume) else None
    volume_used = (
        watertight
        and winding
        and degenerate == 0
        and merged_edges["nonmanifold_edges"] == 0
        and merged_edges["boundary_edges"] == 0
        and components == 1
        and volume is not None
        and volume > 0.0
    )
    extents = np.asarray(merged.extents, dtype=float)
    return {
        "finite": True,
        "vertices_raw": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "vertices_exact": int(len(merged.vertices)),
        "merge_method": "exact_coordinate",
        "coordinates_moved": False,
        "rounded_merge": False,
        "watertight_exact": watertight,
        "winding_consistent_exact": winding,
        "degenerate_faces_exact": degenerate,
        "components_exact": components,
        "edges_raw": raw_edges,
        "edges_exact": merged_edges,
        "volume_signed_mm3": volume,
        "volume_used_for_mass": volume_used,
        "extents_mm": [float(value) for value in extents],
        "hole_fill": False,
    }


def load_stl(path):
    mesh = trimesh.load(path, file_type="stl", force="mesh", process=False)
    report = stl_report(mesh)
    report["sha256"] = sha256_file(path)
    report["path"] = str(path)
    return mesh, report


def _corner_extents(box):
    low = box.CornerMin()
    high = box.CornerMax()
    extents = [high.X() - low.X(), high.Y() - low.Y(), high.Z() - low.Z()]
    return [float(value) for value in extents]


def _bounds(shape):
    """Tight bounds are AddOptimal_s. Add_s is recorded and not compared."""
    loose = Bnd_Box()
    BRepBndLib.Add_s(shape, loose)
    tight = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, tight, False, False)
    return {
        "bounds_compared": {
            "method": "BRepBndLib.AddOptimal_s",
            "use_for_comparison": True,
            "extents": _corner_extents(tight),
        },
        "bounds_loose": {
            "method": "BRepBndLib.Add_s",
            "use_for_comparison": False,
            "note": (
                "Add_s includes control and tessellation enlargement. "
                "It is not a dimension discrepancy against the STL."
            ),
            "extents": _corner_extents(loose),
        },
    }


def _inactive_spans(text):
    """Comment and quoted-string spans. None when one of them is unclosed."""
    spans = []
    index = 0
    limit = len(text)
    while index < limit:
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                return None
            spans.append((index, end + 2))
            index = end + 2
            continue
        if text[index] == "'":
            start = index
            index += 1
            closed = False
            while index < limit:
                if text[index] == "'":
                    if index + 1 < limit and text[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    spans.append((start, index))
                    closed = True
                    break
                index += 1
            if not closed:
                return None
            continue
        index += 1
    return spans


def _starts_inside(position, spans):
    """True when position lies in a comment or quoted string."""
    return any(left <= position < right for left, right in spans)


def _unit_record(units, source, declared):
    return {
        "units": units,
        "units_source": source,
        "declared_length_unit": declared,
        "declared_units": units,
        "declared_units_source": source,
    }


def length_unit_from_step_text(text):
    """Read one active LENGTH_UNIT entity. Comments and quotes are not declarations.

    More than one length context is ambiguous. This is not a general STEP parser.
    """
    if not text or not str(text).strip():
        return _unit_record("unknown", "missing", None)
    spans = _inactive_spans(text)
    if spans is None:
        return _unit_record("ambiguous", "unresolved_context", None)
    found = []
    for match in _SI_ENTITY.finditer(text):
        if _starts_inside(match.start(), spans):
            continue
        prefix = match.group(1).upper()
        mapped = _SI_PREFIX.get(prefix)
        if mapped is None:
            found.append(("unsupported", "step_declaration", prefix))
        else:
            units, declared = mapped
            found.append((units, "step_declaration", declared))
    for match in _CONVERSION_ENTITY.finditer(text):
        if _starts_inside(match.start(), spans):
            continue
        found.append(("unsupported", "conversion_based", match.group(1) or None))
    if not found:
        return _unit_record("unknown", "missing", None)
    if len(found) != 1:
        return _unit_record("ambiguous", "multiple_length_contexts", None)
    units, source, declared = found[0]
    return _unit_record(units, source, declared)


def _reader_length_names(reader):
    lengths = TColStd_SequenceOfAsciiString()
    angles = TColStd_SequenceOfAsciiString()
    solid_angles = TColStd_SequenceOfAsciiString()
    reader.FileUnits(lengths, angles, solid_angles)
    names = []
    for index in range(1, lengths.Length() + 1):
        names.append(str(lengths.Value(index).ToCString()))
    return names


def _apply_reader_units(declared, reader_names, system_unit):
    """Keep the file declaration distinct from OCCT's normalized length factor.

    Millimetres are accepted only when the text, FileUnits, and a system
    length of 1 agree. Nothing is scaled to force that agreement.
    """
    report = dict(declared)
    report["reader_length_units"] = reader_names
    report["normalized_system_length_unit"] = system_unit
    system_ok = (
        isinstance(system_unit, float)
        and math.isfinite(system_unit)
        and abs(system_unit - 1.0) <= 1e-9
    )
    agree = (
        declared["units"] == "mm"
        and declared["units_source"] == "step_declaration"
        and reader_names == ["millimetre"]
        and system_ok
    )
    report["units_agree"] = agree
    if declared["units"] == "mm" and not agree:
        report["units"] = "ambiguous"
        report["units_source"] = "transfer_disagreement"
    return report


def _solid_count(shape):
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def step_report_from_shape(shape, units, units_source, declared_length_unit):
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    raw_volume = float(props.Mass())
    volume = raw_volume if math.isfinite(raw_volume) else None
    report = {
        "valid": bool(BRepCheck_Analyzer(shape).IsValid()),
        "solids": _solid_count(shape),
        "volume_mm3": volume,
        "volume_positive": bool(volume is not None and volume > 0.0),
        "units": units,
        "units_source": units_source,
        "declared_length_unit": declared_length_unit,
    }
    report.update(_bounds(shape))
    return report


def load_step(path):
    text = Path(path).read_text(errors="replace")
    declared = length_unit_from_step_text(text)
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if int(status) != int(IFSelect_RetDone):
        combined = _apply_reader_units(declared, None, None)
        report = {
            "valid": False,
            "solids": 0,
            "volume_mm3": None,
            "volume_positive": False,
            "read_status": int(status),
            "sha256": sha256_file(path),
        }
        report.update(combined)
        return report
    reader_names = _reader_length_names(reader)
    reader.TransferRoots()
    system_unit = float(reader.SystemLengthUnit())
    if not math.isfinite(system_unit):
        system_unit = None
    combined = _apply_reader_units(declared, reader_names, system_unit)
    report = step_report_from_shape(
        reader.OneShape(),
        units=combined["units"],
        units_source=combined["units_source"],
        declared_length_unit=combined["declared_length_unit"],
    )
    report.update(combined)
    report["sha256"] = sha256_file(path)
    report["read_status"] = int(status)
    return report


def analytic_step_box(dx, dy, dz):
    """Constructor arguments are millimetres. Extent is not consulted."""
    shape = BRepPrimAPI_MakeBox(float(dx), float(dy), float(dz)).Shape()
    report = step_report_from_shape(
        shape,
        units="mm",
        units_source="constructor",
        declared_length_unit="millimetre",
    )
    report["declared_units"] = "mm"
    report["declared_units_source"] = "constructor"
    report["reader_length_units"] = None
    report["normalized_system_length_unit"] = None
    report["units_agree"] = True
    report["normalized_length_context"] = "constructor"
    report["analytic_volume_mm3"] = float(dx) * float(dy) * float(dz)
    return report


def rigid_volume(mesh, transform):
    """Signed volume of a transformed copy. The input mesh is left unchanged."""
    copied = mesh.copy()
    copied.apply_transform(transform)
    return float(copied.volume), float(mesh.volume)
