"""Bounded CAD ingest into the frozen marketing mesh/region bundle.

Host Python only: no bpy. Geometry is never smoothed or repaired. Coordinate
conversion is a recorded scale and rigid pose; topology welding and normal
splitting are analysis/shading policies and do not move source vertices.
"""
import argparse
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import zipfile

import numpy as np

if __package__:
    from . import regions
else:  # direct CLI and Grok's path-based peer loader
    import regions
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plan as plan_mod  # noqa: E402  (source registry: hero hash + model names live in plan.py)

# Hero identity comes from plan.py's registry, never from constants here.
HERO_SHA256 = plan_mod.HERO_STEP_SHA256
HERO_STL_SHA256 = plan_mod.HERO_STL_SHA256
HERO_PATH = Path(plan_mod.HERO_STEP_PATH)
HERO_NAME = HERO_PATH.name
HERO_STL_NAME = Path(plan_mod.HERO_STL_PATH).name
# Retained exclusively for the committed decimated smoke fixture's provenance.
LEGACY_FIXTURE_SHA256 = "04404820cf8385f5e34a42ef9d39a79aecda8eb88895c78aa21f4e3a92fe28c5"
MAX_TRIANGLES = 20_000_000
MAX_FILE_BYTES = 1024 * 1024 * 1024
UNIT_SCALE = {"mm": 0.001, "cm": 0.01, "m": 1.0, "in": 0.0254}


@dataclass
class Mesh:
    V: np.ndarray
    F: np.ndarray
    face_id: np.ndarray
    N_corner: np.ndarray | None = None
    surface_types: np.ndarray | None = None
    source_units: str = "mm"
    unit_scale_to_m: float = 0.001
    source_sha256: str = ""


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _exact_weld(V, F):
    # Retain the first original coordinate, including its float bits; np.unique
    # is used only to construct the index map, never to average positions.
    _, first, inverse = np.unique(V, axis=0, return_index=True, return_inverse=True)
    order = np.argsort(first)
    remap = np.empty(len(order), dtype=np.int32)
    remap[order] = np.arange(len(order))
    return V[first[order]], remap[inverse][F].astype(np.int32)


def _validate(V, F, max_triangles):
    V, F = np.asarray(V, dtype=np.float64), np.asarray(F)
    if V.ndim != 2 or V.shape[1] != 3 or F.ndim != 2 or F.shape[1] != 3 or not len(F):
        raise ValueError("CAD must contain 3D vertices and triangles")
    if len(F) > max_triangles:
        raise ValueError(f"triangle limit exceeded ({max_triangles})")
    if not np.isfinite(V).all() or abs(V).max() > 1e9:
        raise ValueError("non-finite or unbounded CAD coordinates")
    if not np.issubdtype(F.dtype, np.integer) or F.min() < 0 or F.max() >= len(V):
        raise ValueError("invalid triangle vertex index")
    F = F.astype(np.int32)
    regions.triangle_geometry(V, F)
    return V, F


def _stl(path, max_triangles):
    size = path.stat().st_size
    with path.open("rb") as f:
        header = f.read(84)
        count = struct.unpack("<I", header[80:84])[0] if len(header) == 84 else 0
        if size == 84 + count * 50:
            if not 0 < count <= max_triangles:
                raise ValueError("binary STL triangle limit exceeded or empty STL")
            dtype = np.dtype([("normal", "<f4", (3,)), ("V", "<f4", (3, 3)), ("attribute", "<u2")])
            data = np.fromfile(f, dtype=dtype, count=count)
            if len(data) != count or not np.isfinite(data["normal"]).all():
                raise ValueError("truncated or non-finite binary STL")
            V = data["V"].astype(np.float64).reshape(-1, 3)
            F = np.arange(len(V), dtype=np.int32).reshape(-1, 3)
            return _exact_weld(*_validate(V, F, max_triangles))
    # A strict streaming grammar catches truncation, extra vertices and garbage;
    # a regex for just 'vertex' would silently accept all three.
    vertices = []
    state, count, ended = "solid", 0, False
    with path.open("rt", encoding="ascii") as f:
        for line in f:
            if len(line) > 4096:
                raise ValueError("STL line exceeds parser bound")
            tokens = line.split()
            if not tokens:
                continue
            if ended:
                raise ValueError("unexpected data after endsolid")
            if state == "solid" and tokens[0] == "solid":
                state = "facet"
            elif state == "facet" and tokens[0] == "endsolid":
                ended = True
            elif state == "facet" and tokens[:2] == ["facet", "normal"] and len(tokens) == 5:
                if not np.isfinite(np.asarray(tokens[2:], dtype=float)).all():
                    raise ValueError("non-finite STL normal")
                count += 1
                if count > max_triangles:
                    raise ValueError("ASCII STL triangle limit exceeded")
                state = "outer"
            elif state == "outer" and tokens == ["outer", "loop"]:
                state = "v0"
            elif state in ("v0", "v1", "v2") and tokens[0] == "vertex" and len(tokens) == 4:
                vertices.append([float(x) for x in tokens[1:]])
                state = {"v0": "v1", "v1": "v2", "v2": "endloop"}[state]
            elif state == "endloop" and tokens == ["endloop"]:
                state = "endfacet"
            elif state == "endfacet" and tokens == ["endfacet"]:
                state = "facet"
            else:
                raise ValueError(f"malformed STL: expected {state}")
    if not ended or not count:
        raise ValueError("truncated or empty ASCII STL")
    V = np.asarray(vertices, dtype=np.float64)
    F = np.arange(len(V), dtype=np.int32).reshape(-1, 3)
    return _exact_weld(*_validate(V, F, max_triangles))


def _triangulate_polygon(V, ids):
    """Ear-clip a planar OBJ polygon, retaining its winding and vertices.

    Fan triangulation fills outside concave polygons. The input bound also
    caps the quadratic ear search at 4096 vertices per polygon.
    """
    if len(ids) == 3:
        return [ids]
    if len(ids) > 4096 or len(set(ids)) != len(ids):
        raise ValueError("OBJ polygon exceeds 4096 vertices or repeats a vertex")
    points = V[ids]
    centered = points - points[0]
    normal = np.cross(centered, np.roll(centered, -1, axis=0)).sum(axis=0)
    span = np.linalg.norm(np.ptp(points, axis=0))
    eps = max(span ** 2 * 1e-12, 1e-30)
    if np.linalg.norm(normal) <= eps:
        raise ValueError("degenerate or self-intersecting OBJ polygon")
    normal /= np.linalg.norm(normal)
    if np.max(abs((points - points[0]) @ normal)) > span * 1e-8:
        raise ValueError("non-planar OBJ polygon")
    xy = np.delete(centered, np.argmax(abs(normal)), axis=1)

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    signed_area = sum(cross(a, b) for a, b in zip(xy, np.roll(xy, -1, axis=0)))
    sign = 1 if signed_area > 0 else -1
    remaining = list(range(len(ids)))
    result = []
    while len(remaining) > 3:
        for k, current in enumerate(remaining):
            previous, following = remaining[k - 1], remaining[(k + 1) % len(remaining)]
            a, b, c = xy[[previous, current, following]]
            if sign * cross(b - a, c - b) <= eps:
                continue
            inside = False
            for j in remaining:
                if j not in (previous, current, following):
                    p = xy[j]
                    if min(sign * cross(b - a, p - a), sign * cross(c - b, p - b), sign * cross(a - c, p - c)) >= -eps:
                        inside = True
                        break
            if not inside:
                result.append([ids[previous], ids[current], ids[following]])
                remaining.pop(k)
                break
        else:
            raise ValueError("cannot triangulate degenerate or self-intersecting OBJ polygon")
    result.append([ids[j] for j in remaining])
    return result


def _obj_ply(path, max_triangles):
    import trimesh

    if path.suffix.lower() == ".obj":
        vertices, triangles = 0, 0
        coords, polygons = [], []
        with path.open("rt", encoding="utf8") as f:
            for line in f:
                if len(line) > 1024 * 1024:
                    raise ValueError("OBJ line exceeds parser bound")
                tokens = line.split("#", 1)[0].split()
                if not tokens:
                    continue
                if tokens[0] == "v":
                    if len(tokens) < 4 or not np.isfinite(np.asarray(tokens[1:4], dtype=float)).all():
                        raise ValueError("malformed or non-finite OBJ vertex")
                    if len(tokens) == 5 and float(tokens[4]) != 1:
                        raise ValueError("OBJ homogeneous vertex weight must be 1")
                    coords.append([float(x) for x in tokens[1:4]])
                    vertices += 1
                elif tokens[0] == "f":
                    if len(tokens) < 4:
                        raise ValueError("OBJ polygon has fewer than three vertices")
                    polygon = []
                    if len(tokens) > 4097:
                        raise ValueError("OBJ polygon exceeds 4096 vertices")
                    for token in tokens[1:]:
                        index = int(token.split("/", 1)[0])
                        if index == 0 or index < -vertices:
                            raise ValueError("invalid OBJ vertex index")
                        polygon.append(index - 1 if index > 0 else vertices + index)
                    polygons.append(polygon)
                    triangles += len(tokens) - 3
                if triangles > max_triangles or vertices > 3 * max_triangles:
                    raise ValueError("OBJ exceeds geometry bounds")
        V = np.asarray(coords, dtype=np.float64)
        if not polygons or any(max(p) >= len(V) for p in polygons):
            raise ValueError("empty OBJ or invalid polygon index")
        faces, face_ids = [], []
        for fid, polygon in enumerate(polygons):
            triangulated = _triangulate_polygon(V, polygon)
            faces.extend(triangulated)
            face_ids.extend([fid] * len(triangulated))
        # Construct through trimesh without its automatic welding/material or
        # fan triangulation policies. Source polygons keep their face IDs.
        mesh = trimesh.Trimesh(vertices=V, faces=faces, process=False)
        face_ids = np.asarray(face_ids, dtype=np.int32)
    else:
        with path.open("rb") as f:
            header = []
            total = 0
            while True:
                line = f.readline(4097)
                total += len(line)
                if not line or len(line) > 4096 or total > 65536:
                    raise ValueError("malformed or oversized PLY header")
                text = line.decode("ascii").strip()
                header.append(text)
                if text == "end_header":
                    break
            if header[0] != "ply":
                raise ValueError("invalid PLY header")
            for line in header:
                tokens = line.split()
                if tokens[:1] == ["element"]:
                    if len(tokens) != 3 or not 0 <= int(tokens[2]) <= 3 * max_triangles:
                        raise ValueError("PLY element limit exceeded")
                    if tokens[1] == "face" and int(tokens[2]) > max_triangles:
                        raise ValueError("PLY face limit exceeded")
        with path.open("rb") as f:
            mesh = trimesh.load_mesh(f, file_type="ply", process=False, fix_texture=False,
                                     skip_materials=True, resolver=None)
        face_ids = np.arange(len(mesh.faces), dtype=np.int32)
    V, F = _exact_weld(*_validate(mesh.vertices, mesh.faces, max_triangles))
    return V, F, face_ids


def _step(path, validated_brep, max_triangles):
    # Required imports intentionally fail when OCP is missing.
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TColStd import TColStd_SequenceOfAsciiString
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SHELL
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt, gp_Vec

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError("STEP reader rejected CAD")
    lengths, angles, solid_angles = (TColStd_SequenceOfAsciiString() for _ in range(3))
    reader.FileUnits(lengths, angles, solid_angles)
    names = sorted({lengths.Value(i).ToCString().lower() for i in range(1, lengths.Length() + 1)})
    aliases = {"millimetre": "mm", "millimeter": "mm", "metre": "m", "meter": "m",
               "centimetre": "cm", "centimeter": "cm", "inch": "in"}
    units = aliases.get(names[0], names[0]) if len(names) == 1 else "mixed:" + ",".join(names)
    # OCCT transfers every representation (including mixed-unit assemblies)
    # into millimetres. Header units are retained in the source record.
    reader.SetSystemLengthUnit(1.0)
    if not reader.TransferRoots():
        raise ValueError("STEP contains no transferable shapes")
    shape = reader.OneShape()
    if shape.IsNull():
        raise ValueError("empty STEP shape")
    if validated_brep:
        shells = TopExp_Explorer(shape, TopAbs_SHELL)
        count = 0
        closed = True
        while shells.More():
            count += 1
            closed &= BRep_Tool.IsClosed_s(shells.Current())
            shells.Next()
        if not count or not closed or not BRepCheck_Analyzer(shape).IsValid():
            raise ValueError("validated_brep requires a valid closed B-rep shell; no STL fallback")
    mesher = BRepMesh_IncrementalMesh(shape, 0.01, False, 0.1, False)
    if not mesher.IsDone():
        raise ValueError("STEP tessellation failed")
    vertices, faces, corner_normals, ids, surface_types = [], [], [], [], []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    fid, offset, triangle_count = 0, 0, 0
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        loc = TopLoc_Location()
        poly = BRep_Tool.Triangulation_s(face, loc)
        if poly is None or not poly.HasUVNodes():
            raise ValueError(f"STEP face {fid} has no triangulation/analytic UV coordinates")
        triangle_count += poly.NbTriangles()
        if triangle_count > max_triangles:
            raise ValueError("STEP triangle limit exceeded")
        surface = BRepAdaptor_Surface(face)
        kind = str(surface.GetType()).split(".")[-1].replace("GeomAbs_", "").lower()
        rev = face.Orientation() == TopAbs_REVERSED
        xyz, normals = [], []
        for i in range(1, poly.NbNodes() + 1):
            p = poly.Node(i).Transformed(loc.Transformation())
            xyz.append([p.X(), p.Y(), p.Z()])
            uv = poly.UVNode(i)
            point, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
            surface.D1(uv.X(), uv.Y(), point, du, dv)
            n = du.Crossed(dv)
            if n.Magnitude() < 1e-14:
                # Singular poles require an analytic limit, never a fabricated
                # smoothed mesh normal. Evaluate infinitesimally inside the face.
                u = np.clip(uv.X(), surface.FirstUParameter() + 1e-7, surface.LastUParameter() - 1e-7)
                v = np.clip(uv.Y(), surface.FirstVParameter() + 1e-7, surface.LastVParameter() - 1e-7)
                surface.D1(float(u), float(v), point, du, dv)
                n = du.Crossed(dv)
            if n.Magnitude() < 1e-14:
                raise ValueError(f"undefined analytic normal on STEP face {fid}")
            n.Normalize()
            normals.append(np.array([n.X(), n.Y(), n.Z()]) * (-1 if rev else 1))
        xyz, normals = np.asarray(xyz), np.asarray(normals)
        local_faces = np.array([poly.Triangle(i).Get() for i in range(1, poly.NbTriangles() + 1)], dtype=np.int32) - 1
        if rev:
            local_faces = local_faces[:, [0, 2, 1]]
        vertices.append(xyz)
        faces.append(local_faces + offset)
        corner_normals.append(normals[local_faces])
        ids.extend([fid] * len(local_faces))
        surface_types.extend([kind] * len(local_faces))
        offset += len(xyz)
        fid += 1
        explorer.Next()
    if not faces:
        raise ValueError("STEP contains no faces")
    V, F = _exact_weld(*_validate(np.concatenate(vertices), np.concatenate(faces), max_triangles))
    return Mesh(V * 0.001, F, np.asarray(ids, dtype=np.int32), np.concatenate(corner_normals),
                np.asarray(surface_types), units, UNIT_SCALE.get(units, 0.001))


def load_cad(path, units=None, validated_brep=False, expected_sha256=None,
             max_triangles=MAX_TRIANGLES, max_file_bytes=MAX_FILE_BYTES):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= max_file_bytes:
        raise ValueError("CAD input missing, empty, or larger than the byte limit")
    digest = sha256(path)
    pinned = plan_mod.pinned_sha_for_name(path.name)
    if pinned is not None and expected_sha256 is not None and expected_sha256 != pinned:
        raise ValueError("requested hero sha256 conflicts with the owner-pinned source")
    expected = pinned or expected_sha256
    if expected is not None and digest != expected:
        raise ValueError(f"source CAD sha256 mismatch: expected {expected}, got {digest}")
    suffix = path.suffix.lower()
    if suffix in (".step", ".stp"):
        if units is not None:
            raise ValueError("STEP units come from the header; --units is for mesh formats")
        mesh = _step(path, validated_brep, max_triangles)
    elif suffix in (".stl", ".obj", ".ply"):
        if validated_brep:
            raise ValueError("validated_brep requires STEP/STP; no mesh fallback")
        units = units or "mm"
        if units not in UNIT_SCALE:
            raise ValueError(f"unsupported units: {units}")
        if suffix == ".stl":
            V, F = _stl(path, max_triangles)
            face_ids = np.arange(len(F), dtype=np.int32)
        else:
            V, F, face_ids = _obj_ply(path, max_triangles)
        mesh = Mesh(V * UNIT_SCALE[units], F, face_ids,
                    source_units=units, unit_scale_to_m=UNIT_SCALE[units])
    else:
        raise ValueError("supported CAD formats: STEP, STP, STL, OBJ, PLY")
    _validate(mesh.V, mesh.F, max_triangles)
    mesh.source_sha256 = digest
    return mesh


def canonical_pose(V, F):
    """PCA: longest X, second Z, smallest -Y; Z up, ring on the left.

    The blade plane faces the default az=0, el=0 camera on -Y. A temporary
    XY plane is used only to resolve the bore sign before the upright pose.
    """
    # Integrate over triangle area: a dense bore tessellation must not pull the
    # pose toward the ring or rotate the blade plane relative to coarser faces.
    _, area, centroids = regions.triangle_geometry(V, F)
    total_area = area.sum()
    center = np.sum(centroids * area[:, None], axis=0) / total_area
    q = V - center
    tri = q[F]
    sums = tri.sum(axis=1)
    covariance = (np.einsum("m,mki,mkj->ij", area, tri, tri)
                  + np.einsum("m,mi,mj->ij", area, sums, sums)) / (12 * total_area)
    values, vectors = np.linalg.eigh(covariance)
    order = np.argsort(-values, kind="stable")
    values, vectors = values[order], vectors[:, order]
    # Resolve repeated eigenvalues by projected world axes, rather than leaving
    # an arbitrary LAPACK eigenbasis for square/cubic fixtures.
    begin = 0
    while begin < 3:
        end = begin + 1
        while end < 3 and abs(values[end] - values[begin]) <= max(values[0], 1e-30) * 1e-10:
            end += 1
        sub = vectors[:, begin:end]
        projector = sub @ sub.T
        basis = []
        for axis in np.eye(3):
            p = projector @ axis
            for b in basis:
                p -= b * np.dot(p, b)
            if np.linalg.norm(p) > 1e-8:
                basis.append(p / np.linalg.norm(p))
            if len(basis) == end - begin:
                break
        vectors[:, begin:end] = np.column_stack(basis)
        begin = end
    for k in (0, 2):
        coord = q @ vectors[:, k]
        tc = coord[F]
        third = (tc.sum(axis=1) * (tc * tc).sum(axis=1) + tc.prod(axis=1)) / 10
        moment = np.sum(area * third) / total_area
        if abs(moment) > max(np.max(abs(coord)) ** 3, 1e-30) * 1e-10:
            sign = 1 if moment >= 0 else -1
        else:
            sign = 1 if vectors[np.argmax(abs(vectors[:, k])), k] >= 0 else -1
        vectors[:, k] *= sign
    vectors[:, 1] = np.cross(vectors[:, 2], vectors[:, 0])
    R = vectors.T
    posed = q @ R.T
    normals, _, _ = regions.triangle_geometry(posed, F)
    loops = regions.projected_loops(posed, F, normals)
    ring = regions.ring_loop(loops)
    if ring is not None and ring[:, 0].mean() > 0:
        R[:2] *= -1
    upright = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
    R = upright @ R
    rotated = V @ R.T
    t = -(rotated.min(axis=0) + rotated.max(axis=0)) / 2
    return R, t


def split_normals(V, F, analysis):
    """Area-weighted normals on connected corner fans, split at 30 degrees."""
    normals, areas, _ = regions.triangle_geometry(V, F)
    TF = analysis["F"]
    parent = np.arange(len(F) * 3, dtype=np.int32)

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in analysis["pairs"]:
        if np.dot(normals[a], normals[b]) < np.cos(np.radians(30)):
            continue
        for ca in range(3):
            matches = np.flatnonzero(TF[b] == TF[a, ca])
            if len(matches) == 1:
                ra, rb = root(a * 3 + ca), root(b * 3 + matches[0])
                parent[max(ra, rb)] = min(ra, rb)
    roots = np.array([root(i) for i in range(len(parent))])
    weighted = np.repeat(normals * areas[:, None], 3, axis=0)
    sums = np.zeros((len(parent), 3))
    np.add.at(sums, roots, weighted)
    result = sums[roots]
    lengths = np.linalg.norm(result, axis=1)
    if np.any(lengths <= 0):
        raise ValueError("undefined split shading normal")
    return (result / lengths[:, None]).reshape(-1, 3, 3).astype(np.float32)


def _atomic_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n")
    os.replace(tmp, path)


def _deterministic_npz(path, arrays):
    # Fixed zip timestamps make the content hash stable across separate runs.
    tmp = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, array in sorted(arrays.items()):
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.asarray(array), allow_pickle=False)
            entry = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, buf.getvalue())
    os.replace(tmp, path)


def ingest(path, out, *, units=None, validated_brep=False, expected_sha256=None, pose=None, tags_path=None):
    path, out = Path(path), Path(out)
    mesh = load_cad(path, units, validated_brep, expected_sha256)
    if pose is None:
        R, t = canonical_pose(mesh.V, mesh.F)
    else:
        override = json.loads(Path(pose).read_text())
        R, t = np.asarray(override["R"], dtype=float), np.asarray(override["t"], dtype=float)
        if (R.shape != (3, 3) or t.shape != (3,) or not np.isfinite(R).all() or not np.isfinite(t).all()
                or not np.allclose(R @ R.T, np.eye(3), atol=1e-10) or not np.isclose(np.linalg.det(R), 1, atol=1e-10)):
            raise ValueError("pose.json must specify a finite right-handed rigid R,t (t in metres)")
    V = mesh.V @ R.T + t
    # STEP meshing can contain valid edges much shorter than the STL seam
    # tolerance. Use a 1 nm ceiling for analytic CAD topology analysis.
    tolerance = min(float(np.linalg.norm(np.ptp(V, axis=0))) * 1e-6, 1e-9) if mesh.N_corner is not None else None
    topo = regions.topology(V, mesh.F, tolerance)
    policy = "brep_analytic" if mesh.N_corner is not None else "split_crease30_weighted"
    N = (mesh.N_corner @ R.T).astype(np.float32) if mesh.N_corner is not None else split_normals(V, mesh.F, topo)
    sidecar = Path(tags_path) if tags_path else path.with_suffix(".regions.json")
    tags = None
    if sidecar.exists():
        tagged = json.loads(sidecar.read_text())
        tags = tagged.get("faces", tagged)
        if not isinstance(tags, dict):
            raise ValueError("regions sidecar must map face IDs to labels")
    elif tags_path is not None:
        raise ValueError("requested region tags sidecar is missing")
    descriptors = regions.read_brep_faces(path, R, t) if mesh.N_corner is not None else None
    labels, tangent, uv, info = regions.classify(V, mesh.F, mesh.face_id, mesh.surface_types, tags, topo,
                                              brep_faces=descriptors, N_corner=N)
    mesh_dir = out / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    _deterministic_npz(mesh_dir / "mesh.npz", {"V": V.astype(np.float64), "F": mesh.F.astype(np.int32),
                      "N_corner": N, "face_id": mesh.face_id, "region_id": labels, "tangent": tangent, "uv": uv})
    source = {"path": str(path), "format": path.suffix[1:].lower(), "sha256": mesh.source_sha256, "units": mesh.source_units}
    src_info = plan_mod.source_info(mesh.source_sha256)  # keyed by the --cad file's verified hash
    if src_info is not None:
        source["model"] = src_info["model"]
        source["reference_mass_g"] = src_info["reference_mass_g"]
        source["role"] = src_info["role"]
    if tags is not None:
        source["regions_sidecar"] = {"path": str(sidecar), "sha256": sha256(sidecar)}
    bundle = {"schema": "jarambit.render.mesh.v1", "source": source, "unit_scale_to_m": mesh.unit_scale_to_m,
              "n_vertices": len(V), "n_triangles": len(mesh.F), "bbox_m": [V.min(axis=0).tolist(), V.max(axis=0).tolist()],
              "pose": {"R": R.tolist(), "t": t.tolist()}, "normal_policy": policy,
              "canonical_axes": {"longest": "X", "blade_plane": "XZ", "world_up": "Z", "front": "-Y"},
              "npz_sha256": sha256(mesh_dir / "mesh.npz"), "validated_brep": bool(validated_brep),
              "geometry_policy": "source_positions_preserved; exact_index_weld; scale_then_rigid_pose",
              "topology_weld": {"tolerance_m": topo["tolerance_m"], "analysis_only": True},
              "step_tessellation": {"linear_mm": 0.01, "angular_rad": 0.1, "relative": False} if mesh.N_corner is not None else None}
    _atomic_json(mesh_dir / "regions.json", info)
    debug_tmp = mesh_dir / "regions_debug.png.tmp"
    regions.debug_overlay(V, mesh.F, labels, debug_tmp)
    os.replace(debug_tmp, mesh_dir / "regions_debug.png")
    # Publish the manifest last so consumers do not see a partially written bundle.
    _atomic_json(mesh_dir / "bundle.json", bundle)
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cad", type=Path, nargs="?", default=HERO_PATH,
                        help="CAD path; defaults to plan.HERO_STEP_PATH (the current pinned hero)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--units", choices=UNIT_SCALE)
    parser.add_argument("--validated-brep", action="store_true")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--pose", type=Path)
    parser.add_argument("--regions", type=Path, help="face-ID region tags; otherwise auto-load <cad-stem>.regions.json")
    args = parser.parse_args(argv)
    try:
        result = ingest(args.cad, args.out, units=args.units, validated_brep=args.validated_brep,
                        expected_sha256=args.expected_sha256, pose=args.pose, tags_path=args.regions)
    except (ValueError, OSError, ImportError, RuntimeError) as exc:
        parser.exit(1, f"CAD ingest failed: {exc}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
