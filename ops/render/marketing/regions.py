"""Deterministic surface labels and finish directions; no geometry edits.

The fallback assumes a predominantly planar product whose smallest PCA axis
is Z. Labels are appearance segmentation, not a claim about manufactured CAD.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter1d
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

LABELS = {0: "body", 1: "bevel", 2: "edge_apex", 3: "serration", 4: "ring", 5: "pad", 6: "spine"}
COLORS = [(133, 146, 163), (54, 181, 229), (255, 217, 63), (235, 100, 90),
          (170, 111, 220), (70, 195, 139), (234, 151, 60)]


def triangle_geometry(V, F):
    tri = V[F]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    size = np.linalg.norm(cross, axis=1)
    if np.any(size <= 0) or not np.isfinite(size).all():
        raise ValueError("degenerate or non-finite triangle")
    return cross / size[:, None], size / 2, tri.mean(axis=1)


def topology(V, F, tolerance=None):
    """Weld *indices for analysis*, retaining every position in the mesh.

    First representative in input order wins; a neighbouring spatial cell is
    searched as well, so seams straddling cell boundaries are joined.
    """
    tolerance = tolerance or float(np.linalg.norm(np.ptp(V, axis=0))) * 1e-6
    cells, representatives = {}, []
    vertex_map = np.empty(len(V), dtype=np.int32)
    for i, p in enumerate(V):
        cell = tuple(np.floor(p / tolerance).astype(np.int64))
        match = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in cells.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()):
                        if np.linalg.norm(p - V[representatives[j]]) <= tolerance:
                            match = j if match is None else min(match, j)
        if match is None:
            match = len(representatives)
            representatives.append(i)
            cells.setdefault(cell, []).append(match)
        vertex_map[i] = match
    TF = vertex_map[F]
    edges = np.sort(np.concatenate([TF[:, [0, 1]], TF[:, [1, 2]], TF[:, [2, 0]]]), axis=1)
    owners = np.tile(np.arange(len(F)), 3)
    unique, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
    order = np.argsort(inverse, kind="stable")
    starts = np.r_[0, np.cumsum(counts)[:-1]]
    two = counts == 2
    pairs = np.column_stack([owners[order[starts[two]]], owners[order[starts[two] + 1]]])
    used = np.unique(TF)
    return {"V": V[representatives], "F": TF, "map": vertex_map, "edges": unique,
            "counts": counts, "pairs": pairs, "paired_edges": unique[two],
            "euler": int(len(used) - len(unique) + len(F)),
            "boundary_edges": int(np.sum(counts == 1)),
            "nonmanifold_edges": int(np.sum(counts > 2)), "tolerance_m": tolerance}


def _components(mask, pairs):
    ids = np.flatnonzero(mask)
    if not len(ids):
        return []
    mapping = np.full(len(mask), -1, dtype=int)
    mapping[ids] = np.arange(len(ids))
    selected = pairs[mask[pairs].all(axis=1)]
    local = mapping[selected]
    graph = coo_matrix((np.ones(len(local) * 2),
                        (np.r_[local[:, 0], local[:, 1]], np.r_[local[:, 1], local[:, 0]])),
                       shape=(len(ids), len(ids))).tocsr()
    count, labels = connected_components(graph, directed=False)
    return [ids[labels == i] for i in range(count)]


def projected_loops(V, F, normals, analysis=None):
    """Closed boundary loops of the front half projected into the blade plane.

    A closed 3D genus-one mesh has no free edges. Its front-half boundary does:
    this extracts the outer silhouette and the bore without altering the CAD.
    """
    if analysis is not None:
        V, F = analysis["V"], analysis["F"]
    front = F[normals[:, 2] > 0.2]
    if not len(front):
        return []
    directed = np.concatenate([front[:, [0, 1]], front[:, [1, 2]], front[:, [2, 0]]])
    edges = np.sort(directed, axis=1)
    edges = edges[edges[:, 0] != edges[:, 1]]
    directed = directed[directed[:, 0] != directed[:, 1]]
    _, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
    boundary = sorted(map(tuple, directed[counts[inverse] == 1].tolist()))
    outgoing = {}
    for a, b in boundary:
        outgoing.setdefault(a, []).append(b)
    visited, loops = set(), []
    for start, second in boundary:
        if (start, second) in visited:
            continue
        loop, previous, current = [], start, second
        while (previous, current) not in visited:
            visited.add((previous, current))
            loop.append(previous)
            if current == start:
                break
            options = [j for j in outgoing.get(current, []) if (current, j) not in visited]
            if not options:
                break
            incoming = V[current, :2] - V[previous, :2]

            def turn(j):
                direction = V[j, :2] - V[current, :2]
                return (float(np.arctan2(incoming[0] * direction[1] - incoming[1] * direction[0],
                                        np.dot(incoming, direction))), j)

            # Follow the boundary with the selected surface on the left, even
            # at vertices where two front patches touch and degree is four.
            previous, current = current, min(options, key=turn)
        if current == start and len(loop) >= 3:
            # Traverse in 3D first. Projecting before finding loops merges
            # unrelated top/bottom groove boundaries that share XY positions.
            poly = V[loop, :2]
            good = np.linalg.norm(poly - np.roll(poly, 1, axis=0), axis=1) > 1e-12
            poly = poly[good]
            if len(poly) < 3:
                continue
            area = abs(float(np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - poly[:, 1] * np.roll(poly[:, 0], -1)) / 2))
            if area > 0:
                loops.append((area, poly))
    return sorted(loops, key=lambda x: -x[0])


def ring_loop(loops):
    """Largest circular interior loop; other CAD holes remain distinct."""
    candidates = []
    for area, poly in loops[1:]:
        radius = np.linalg.norm(poly - poly.mean(axis=0), axis=1)
        perimeter = np.linalg.norm(np.roll(poly, -1, axis=0) - poly, axis=1).sum()
        circularity = 4 * np.pi * area / perimeter ** 2
        if radius.std() / radius.mean() < 0.12 and circularity > 0.85:
            candidates.append((area, poly))
    if not candidates:
        return None
    largest = max(candidates, key=lambda x: x[0])
    center = largest[1].mean(axis=0)
    # Concentric circles can be ring-face grooves. The innermost boundary at
    # this center is the bore; do not assign a groove wall as the ring bore.
    concentric = [p for p in candidates if np.linalg.norm(p[1].mean(axis=0) - center) < 0.001]
    return min(concentric, key=lambda x: x[0])[1]


def outline_distance(points, polygon):
    """Exact nearest point on piecewise-linear outline, with bounded scratch."""
    if polygon is None:
        return np.full(len(points), np.inf), np.zeros_like(points), np.zeros(len(points), dtype=int)
    a, b = polygon, np.roll(polygon, -1, axis=0)
    ab = b - a
    length2 = np.sum(ab * ab, axis=1)
    distances, nearest, indices = [], [], []
    for start in range(0, len(points), 256):
        p = points[start:start + 256]
        t = np.clip(np.einsum("ijk,jk->ij", p[:, None] - a, ab) / length2, 0, 1)
        q = a + t[:, :, None] * ab
        d2 = np.sum((p[:, None] - q) ** 2, axis=2)
        idx = d2.argmin(axis=1)
        distances.append(np.sqrt(d2[np.arange(len(p)), idx]))
        nearest.append(q[np.arange(len(p)), idx])
        indices.append(idx)
    return np.concatenate(distances), np.concatenate(nearest), np.concatenate(indices)


def cotan_curvature(V, F, normals, areas):
    """Signed discrete mean curvature (1/m), cotangent Laplacian."""
    tri = V[F]
    lap = np.zeros_like(V)
    vertex_area = np.zeros(len(V))
    vertex_normal = np.zeros_like(V)
    for k in range(3):
        i, j = (k + 1) % 3, (k + 2) % 3
        u, v = tri[:, i] - tri[:, k], tri[:, j] - tri[:, k]
        cot = np.einsum("ij,ij->i", u, v) / (2 * areas)
        contribution = cot[:, None] * (tri[:, j] - tri[:, i])
        np.add.at(lap, F[:, i], contribution)
        np.add.at(lap, F[:, j], -contribution)
        np.add.at(vertex_area, F[:, k], areas / 3)
        np.add.at(vertex_normal, F[:, k], normals * areas[:, None])
    vertex_normal /= np.maximum(np.linalg.norm(vertex_normal, axis=1)[:, None], 1e-30)
    return np.einsum("ij,ij->i", lap, vertex_normal) / np.maximum(4 * vertex_area, 1e-30)


def _serration_segments(polygon):
    if polygon is None or len(polygon) < 32:
        return set(), {}
    length = np.linalg.norm(np.roll(polygon, -1, axis=0) - polygon, axis=1)
    s = np.r_[0, np.cumsum(length)]
    at = np.linspace(0, s[-1], 2048, endpoint=False)
    closed = np.vstack([polygon, polygon[0]])
    q = np.column_stack([np.interp(at, s, closed[:, k]) for k in range(2)])
    q = gaussian_filter1d(q, 1.0, axis=0, mode="wrap")
    tangent = np.roll(q, -1, axis=0) - np.roll(q, 1, axis=0)
    angle = np.arctan2(tangent[:, 1], tangent[:, 0])
    curvature = np.angle(np.exp(1j * (np.roll(angle, -1) - np.roll(angle, 1))))
    high = curvature - gaussian_filter1d(curvature, 24, mode="wrap")
    power = abs(np.fft.rfft(high)) ** 2
    peak = int(np.argmax(power[8:257]) + 8)
    fraction = float(power[peak] / max(power[8:].sum(), 1e-30))
    changes = int(np.sum(np.diff(np.sign(high)) != 0))
    metrics = {"fft_cycles": peak, "fft_power_fraction": fraction, "curvature_sign_changes": changes}
    periodic = np.zeros(len(at), dtype=bool)
    if fraction >= 0.08 and changes >= 8 and power[peak] >= 5 * np.median(power[8:257]):
        periodic[:] = True
    # A product can have several tooth pitches on two different arcs. A global
    # FFT spreads their power across frequencies, so test overlapping local
    # arc windows as well, with a Hann window to suppress truncation artefacts.
    detected = 0
    for start in range(0, len(at), 128):
        ids = np.arange(start, start + 256) % len(at)
        local = high[ids]
        power_local = abs(np.fft.rfft(local * np.hanning(256))) ** 2
        peak_local = int(np.argmax(power_local[4:80]) + 4)
        frac_local = power_local[peak_local] / max(power_local[4:80].sum(), 1e-30)
        if (frac_local >= 0.10 and power_local[peak_local] > 5 * np.median(power_local[4:80])
                and np.sum(np.diff(np.sign(local)) != 0) >= 8 and abs(local).max() > 0.08):
            periodic[ids] = True
            detected += 1
    metrics["periodic_arc_windows"] = detected
    selected = periodic & (abs(high) > max(float(np.quantile(abs(high), 0.65)), 0.01))
    return set((np.searchsorted(s, at[selected], side="right") - 1).tolist()), metrics


def plane_frame(V):
    """Map canonical upright XZ CAD to an XY analysis plane, preserving handedness."""
    if np.var(V, axis=0).argmin() == 1:
        return np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=float)
    return np.eye(3)


def read_brep_faces(path, R=None, t=None):
    """Read analytic surface descriptors in STEP explorer face order, without meshing."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    R = np.eye(3) if R is None else np.asarray(R)
    t = np.zeros(3) if t is None else np.asarray(t)
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError("STEP reader rejected region source")
    reader.SetSystemLengthUnit(1.0)
    if not reader.TransferRoots():
        raise ValueError("no B-rep region source faces")
    explorer = TopExp_Explorer(reader.OneShape(), TopAbs_FACE)
    records = {}
    while explorer.More():
        surface = BRepAdaptor_Surface(TopoDS.Face_s(explorer.Current()))
        kind = str(surface.GetType()).split(".")[-1].replace("GeomAbs_", "").lower()
        rec = {"type": kind}
        if kind in ("cylinder", "cone", "torus", "plane"):
            analytic = getattr(surface, {"cylinder": "Cylinder", "cone": "Cone", "torus": "Torus", "plane": "Plane"}[kind])()
            axis = analytic.Axis()
            origin, direction = axis.Location(), axis.Direction()
            rec["origin_m"] = (R @ (np.array([origin.X(), origin.Y(), origin.Z()]) * .001) + t).tolist()
            rec["axis"] = (R @ np.array([direction.X(), direction.Y(), direction.Z()])).tolist()
            if kind == "cylinder":
                rec["radius_m"] = analytic.Radius() * .001
            if kind == "torus":
                rec["major_radius_m"] = analytic.MajorRadius() * .001
                rec["minor_radius_m"] = analytic.MinorRadius() * .001
            if kind != "plane":
                rec["u_span_rad"] = surface.LastUParameter() - surface.FirstUParameter()
        records[len(records)] = rec
        explorer.Next()
    return records


def classify_brep(V, F, face_id, faces, N_corner=None, tags=None, analysis=None):
    """Classify analytic B-rep features before any triangle-level refinement.

    Full concave cylinders identify the bore; coaxial tori/cones/cylinders are
    ring details, never blade bevels. Conical wheel patches identify serration
    grinds. BSpline ruled grind patches use analytic corner normals, so triangle
    count and faceting cannot change their finish. A finite thin edge land is
    the apex even when its dihedral is below the STL sharp-crease threshold.
    """
    V, F, face_id = np.asarray(V), np.asarray(F), np.asarray(face_id)
    geom_normal, area, center = triangle_geometry(V, F)
    normals = geom_normal if N_corner is None else np.asarray(N_corner).mean(axis=1).astype(float)
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    ids = np.unique(face_id)
    if any(int(fid) not in faces for fid in ids):
        raise ValueError("B-rep descriptors do not cover mesh face IDs")
    kinds = np.array([faces[int(fid)]["type"] for fid in face_id])
    planes = [int(fid) for fid in ids if faces[int(fid)]["type"] == "plane"]
    if planes:
        largest = max(planes, key=lambda fid: float(area[face_id == fid].sum()))
        plate = np.asarray(faces[largest]["axis"], dtype=float)
    else:
        plate = plane_frame(V)[2]
    plate /= np.linalg.norm(plate)
    angle = np.degrees(np.arccos(np.clip(abs(normals @ plate), 0, 1)))
    mid = (np.min(V @ plate) + np.max(V @ plate)) / 2
    candidates = []
    for fid in ids:
        rec = faces[int(fid)]
        if rec["type"] != "cylinder" or rec["u_span_rad"] < 2 * np.pi - .01 or abs(np.dot(rec["axis"], plate)) < .995:
            continue
        s = face_id == fid
        axis = np.asarray(rec["axis"])
        radial = center[s] - rec["origin_m"]
        radial -= np.outer(radial @ axis, axis)
        inward = np.average(np.einsum("ij,ij->i", normals[s], radial), weights=area[s]) < 0
        if inward:
            candidates.append((float(area[s].sum()), int(fid)))
    bore = max(candidates)[1] if candidates else None
    ring_ids = []
    if bore is not None:
        origin = np.asarray(faces[bore]["origin_m"])
        axis = np.asarray(faces[bore]["axis"])
        for fid in ids:
            rec = faces[int(fid)]
            if rec["type"] not in ("cylinder", "cone", "torus"):
                continue
            delta = np.asarray(rec["origin_m"]) - origin
            if np.linalg.norm(delta - axis * np.dot(delta, axis)) < 1e-6 and abs(np.dot(rec["axis"], axis)) > .995:
                ring_ids.append(int(fid))
    ring = np.isin(face_id, ring_ids)
    blade = center[:, 0] > (V[:, 0].min() + V[:, 0].max()) / 2 if bore is not None else np.ones(len(F), bool)
    labels = np.zeros(len(F), np.uint8)
    labels[(angle > 75) & ~ring] = 6
    oblique = (angle > 12) & (angle <= 75)
    # Planar chamfers are explicit CAD faces. Curved ruled grinds are restricted
    # to the blade when a bore establishes the handle side.
    labels[oblique & (kinds == "plane") & ~ring] = 1
    labels[oblique & np.isin(kinds, ["bsplinesurface", "beziersurface", "surfaceofextrusion", "surfaceofrevolution"]) & blade & ~ring] = 1
    cone = (kinds == "cone") & blade & ~ring
    labels[cone & oblique] = 3
    labels[ring] = 4
    topo = analysis if analysis is not None else topology(V, F, min(np.linalg.norm(np.ptp(V, axis=0)) * 1e-6, 1e-9))
    grind = np.isin(labels, [1, 3])
    adjacent = np.zeros(len(F), bool)
    pairs = topo["pairs"]
    near_grind = pairs[np.any(grind[pairs], axis=1)]
    adjacent[near_grind.ravel()] = True
    thin_land = np.max(abs(V[F] @ plate - mid), axis=1) <= .00025 + 1e-9
    apex = thin_land & (angle > 75) & blade & ~ring & adjacent
    labels[apex] = 2
    # A broad connected handle plane remains body unless the exporter explicitly
    # tags a brand pad. Calling the entire handle a glossy pad hides the finish.
    if tags is not None:
        for key, value in tags.items():
            label = {v: k for k, v in LABELS.items()}.get(value, value) if isinstance(value, str) else value
            if int(key) not in ids or label not in LABELS:
                raise ValueError(f"unknown face ID or region tag: {key}={value}")
            labels[face_id == int(key)] = label
    tangent = plate - normals * (normals @ plate)[:, None]
    flat = np.linalg.norm(tangent, axis=1) < 1e-8
    tangent[flat] = [1, 0, 0]
    if bore is not None:
        radial = center - np.asarray(faces[bore]["origin_m"])
        tangent[ring] = np.cross(np.asarray(faces[bore]["axis"]), radial[ring])
    tangent -= normals * np.einsum("ij,ij->i", tangent, normals)[:, None]
    zero = np.linalg.norm(tangent, axis=1) < 1e-12
    tangent[zero] = V[F[zero, 1]] - V[F[zero, 0]]
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    delta = V[F] - center[:, None]
    uv = np.stack([np.einsum("mki,mi->mk", delta, tangent), np.einsum("mki,mi->mk", delta, np.cross(normals, tangent))], axis=2)
    info = {"schema": "jarambit.render.regions.v1", "revision": 2, "labels": LABELS,
            "method": "tags" if tags is not None else "brep",
            "params": {"classification_priority": ["exporter_tags", "analytic_brep_features", "analytic_corner_normals"],
                       "body_angle_deg": 12, "bevel_angle_max_deg": 75, "apex_land_half_thickness_mm": .25,
                       "blade_plane_normal": plate.tolist(), "ring_policy": "concave_bore_and_coaxial_analytic_details",
                       "serration_policy": "conical_wheel_grinds", "pad_policy": "explicit_face_tags_only"},
            "area_mm2": {name: float(area[labels == key].sum() * 1e6) for key, name in LABELS.items()},
            "labels_sha256": hashlib.sha256(labels.tobytes()).hexdigest(),
            "diagnostics": {"bore_face_id": bore, "ring_face_ids": ring_ids, "finite_edge_land_triangles": int(apex.sum()),
                            "boundary_edges": topo["boundary_edges"], "nonmanifold_edges": topo["nonmanifold_edges"],
                            "euler_characteristic": topo["euler"], "review": "pending"}}
    return labels, tangent.astype(np.float32), uv.astype(np.float32), info


def classify(V, F, face_id=None, surface_types=None, tags=None, analysis=None, *, brep_faces=None, N_corner=None):
    """Return region_id, tangent, uv and the frozen regions.json record.

    `tags` maps zero-based face IDs to label names or integer IDs. Partial
    tags override B-rep/heuristic results only for the named faces.
    """
    V, F = np.asarray(V), np.asarray(F)
    if brep_faces is not None:
        return classify_brep(V, F, face_id, brep_faces, N_corner, tags, analysis)
    Q = plane_frame(V)
    planar_analysis = None
    if analysis is not None:
        planar_analysis = {**analysis, "V": analysis["V"] @ Q.T}
    labels, tangent, uv, info = _classify_planar(V @ Q.T, F, face_id, surface_types, tags, planar_analysis)
    info["params"]["blade_plane_normal"] = Q[2].tolist()
    info["params"]["analysis_plane_R"] = Q.tolist()
    return labels, (tangent @ Q).astype(np.float32), uv, info


def _classify_planar(V, F, face_id=None, surface_types=None, tags=None, analysis=None):
    normals, areas, centers = triangle_geometry(V, F)
    topo = analysis if analysis is not None else topology(V, F)
    pairs = topo["pairs"]
    loops = projected_loops(V, F, normals, topo)
    outer = loops[0][1] if loops else None
    hole = ring_loop(loops) if topo["euler"] <= 0 and not topo["boundary_edges"] and not topo["nonmanifold_edges"] else None
    distance, nearest, outline_ids = outline_distance(centers[:, :2], outer)
    angle = np.degrees(np.arccos(np.clip(abs(normals[:, 2]), 0, 1)))
    curvature = cotan_curvature(topo["V"], topo["F"], normals, areas)
    labels = np.zeros(len(F), dtype=np.uint8)
    bevel = (angle > 12) & (angle <= 75) & (distance <= 0.018)
    if hole is not None:
        # The ring locates the handle. Sloped groove walls on that half are
        # not blade grinds even when they lie inside the outer 18 mm band.
        bevel &= centers[:, 0] > (V[:, 0].min() + V[:, 0].max()) / 2
    for component in _components(bevel, pairs):
        if areas[component].sum() >= 20e-6:
            labels[component] = 1
    method = "heuristic"
    if surface_types is not None:
        method = "brep"
        # Analytic oblique planar faces are explicit chamfers, not noisy STL normals.
        oblique = (np.asarray(surface_types) == "plane") & (angle > 12) & (angle <= 75)
        labels[oblique] = 1
    labels[(angle > 75) & (distance <= 0.001)] = 6
    ring_center = None
    if hole is not None:
        ring_center = hole.mean(axis=0)
        hd, _, _ = outline_distance(centers[:, :2], hole)
        labels[(hd < 0.0005) & (angle > 75)] = 4
    planar = (angle < 1) & (centers[:, 0] < (V[:, 0].min() + V[:, 0].max()) / 2)
    if ring_center is not None:
        radius = np.linalg.norm(hole - ring_center, axis=1).max()
        planar &= centers[:, 0] > ring_center[0] + radius
    comps = _components(planar & (labels == 0), pairs)
    if comps:
        # Select the largest plane on each side of the handle, without joining
        # it across a crease or claiming an engraved logo.
        for sign in (-1, 1):
            side = [c for c in comps if np.mean(normals[c, 2]) * sign > 0]
            if side:
                pad = max(side, key=lambda c: float(areas[c].sum()))
                if areas[pad].sum() >= 20e-6:
                    labels[pad] = 5
    dihedral = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", normals[pairs[:, 0]], normals[pairs[:, 1]]), -1, 1)))
    sharp = (dihedral > 120) & np.any(labels[pairs] == 1, axis=1)
    if sharp.any():
        endpoints = topo["V"][topo["paired_edges"][sharp]]
        from scipy.spatial import cKDTree
        # Sample creases at <=0.05 mm spacing for the 0.25 mm apex band.
        samples = []
        for a, b in endpoints:
            count = max(2, int(np.ceil(np.linalg.norm(b - a) / 0.00005)) + 1)
            samples.append(np.linspace(a, b, count))
        near = cKDTree(np.concatenate(samples)).query(centers, workers=1)[0] <= 0.00025
        labels[near & (labels == 1)] = 2
    segments, serration = _serration_segments(outer)
    if segments:
        labels[(labels == 1) & (distance < 0.001) & np.isin(outline_ids, sorted(segments))] = 3
    if tags is not None:
        if face_id is None:
            raise ValueError("face_id is required for region tags")
        valid_ids = set(np.asarray(face_id).tolist())
        for key, value in sorted(tags.items(), key=lambda kv: int(kv[0])):
            fid = int(key)
            label = {v: k for k, v in LABELS.items()}.get(value, value) if isinstance(value, str) else value
            if fid not in valid_ids or label not in LABELS:
                raise ValueError(f"unknown face ID or region tag: {key}={value}")
            labels[np.asarray(face_id) == fid] = label
        method = "tags"
    direction = np.column_stack([centers[:, :2] - nearest, np.zeros(len(F))])
    if outer is None:
        direction[:] = [1, 0, 0]
    direction -= normals * np.einsum("ij,ij->i", direction, normals)[:, None]
    small = np.linalg.norm(direction, axis=1) < 1e-12
    direction[small] = V[F[small, 1]] - V[F[small, 0]]
    if ring_center is not None:
        radial = centers[:, :2] - ring_center
        direction[labels == 4] = np.column_stack([-radial[:, 1], radial[:, 0], np.zeros(len(F))])[labels == 4]
    direction -= normals * np.einsum("ij,ij->i", direction, normals)[:, None]
    direction /= np.maximum(np.linalg.norm(direction, axis=1)[:, None], 1e-30)
    bitangent = np.cross(normals, direction)
    delta = V[F] - centers[:, None]
    uv = np.stack([np.einsum("mki,mi->mk", delta, direction), np.einsum("mki,mi->mk", delta, bitangent)], axis=2)
    info = {"schema": "jarambit.render.regions.v1", "labels": LABELS, "method": method,
            "params": {"body_angle_deg": 12, "bevel_angle_max_deg": 75, "outer_band_mm": 18,
                       "component_min_area_mm2": 20, "sharp_dihedral_deg": 120, "apex_band_mm": 0.25,
                       "blade_plane_normal": [0, 0, 1], "finish_uv_units": "m",
                       "blade_half_gate_when_ring_found": True,
                       "topology_weld_tolerance_m": topo["tolerance_m"]},
            "area_mm2": {name: float(areas[labels == key].sum() * 1e6) for key, name in LABELS.items()},
            "labels_sha256": hashlib.sha256(labels.tobytes()).hexdigest(),
            "diagnostics": {"euler_characteristic": topo["euler"], "boundary_edges": topo["boundary_edges"],
                            "nonmanifold_edges": topo["nonmanifold_edges"], "projected_loops": len(loops),
                            "genus_one_assumption_met": topo["euler"] == 0 and not topo["boundary_edges"] and not topo["nonmanifold_edges"],
                            "ring_center_m": ring_center.tolist() if ring_center is not None else None,
                            "dihedral_max_deg": float(dihedral.max()) if len(dihedral) else 0,
                            "cotan_curvature_abs_p95_per_m": float(np.quantile(abs(curvature), 0.95)),
                            "serration": serration, "review": "pending"}}
    return labels, direction.astype(np.float32), uv.astype(np.float32), info


def debug_overlay(V, F, labels, path):
    """Front/back orthographic segmentation sheet with a fixed label legend."""
    V = V @ plane_frame(V).T
    width, height = 1600, 940
    image = Image.new("RGB", (width, height), (24, 28, 34))
    draw = ImageDraw.Draw(image)
    lo, hi = V[:, :2].min(axis=0), V[:, :2].max(axis=0)
    scale = min((width - 80) / (hi[0] - lo[0]), (height / 2 - 80) / (hi[1] - lo[1]))
    normals, _, centers = triangle_geometry(V, F)
    for panel, sign in enumerate([1, -1]):
        xy = (V[:, :2] - (lo + hi) / 2) * scale
        xy[:, 0] += width / 2
        xy[:, 1] = height / 4 + panel * height / 2 - xy[:, 1]
        order = np.argsort(sign * centers[:, 2], kind="stable")
        for i in order:
            if sign * normals[i, 2] > 0.02:
                draw.polygon([tuple(p) for p in xy[F[i]]], fill=COLORS[int(labels[i])])
        draw.text((20, 12 + panel * height / 2), "front" if panel == 0 else "back", fill="white")
    for i, name in LABELS.items():
        x = 20 + i * 215
        draw.rectangle((x, height - 28, x + 16, height - 12), fill=COLORS[i])
        draw.text((x + 22, height - 28), name, fill="white")
    image.save(path, format="PNG")


def debug_overlay_3q(V, F, labels, path):
    """Oblique false-color view shows bore walls and finite edge lands."""
    from .framing import camera_basis
    basis = camera_basis(35, 20)
    points = V @ basis.T
    normals, _, center = triangle_geometry(V, F)
    width, height = 1600, 900
    image = Image.new("RGB", (width, height), (24, 28, 34))
    draw = ImageDraw.Draw(image)
    lo, hi = points[:, :2].min(0), points[:, :2].max(0)
    scale = min((width - 80) / (hi[0] - lo[0]), (height - 80) / (hi[1] - lo[1]))
    xy = (points[:, :2] - (lo + hi) / 2) * scale
    xy[:, 0] += width / 2
    xy[:, 1] = height / 2 - xy[:, 1]
    for i in np.argsort(center @ basis[2], kind="stable"):
        if normals[i] @ basis[2] > 0:
            draw.polygon([tuple(p) for p in xy[F[i]]], fill=COLORS[int(labels[i])])
    for i, name in LABELS.items():
        x = 20 + i * 215
        draw.rectangle((x, height - 28, x + 16, height - 12), fill=COLORS[i])
        draw.text((x + 22, height - 28), name, fill="white")
    image.save(path, format="PNG")


def write_regions_v2(bundle_path, out):
    """Publish a new directory with immutable NPZ plus external v2 attributes."""
    import shutil
    from .ingest import HERO_SHA256, sha256

    bundle_path, out = Path(bundle_path).resolve(), Path(out).resolve()
    base = bundle_path.parent
    if out == base or base in out.parents or out.exists():
        raise ValueError("regions v2 requires a new directory outside the production mesh")
    before = {p.name: sha256(p) for p in base.iterdir() if p.is_file()}
    bundle = json.loads(bundle_path.read_text())
    if bundle["source"]["sha256"] != HERO_SHA256 or sha256(bundle["source"]["path"]) != HERO_SHA256:
        raise ValueError("C.9.2 source pin mismatch")
    if before["mesh.npz"] != bundle["npz_sha256"]:
        raise ValueError("production NPZ hash mismatch")
    with np.load(base / "mesh.npz", allow_pickle=False) as archive:
        mesh = {key: archive[key] for key in archive.files}
    faces = read_brep_faces(bundle["source"]["path"], bundle["pose"]["R"], bundle["pose"]["t"])
    labels, tangent, _, info = classify_brep(mesh["V"], mesh["F"], mesh["face_id"], faces, mesh["N_corner"])
    stage = out.with_name(out.name + ".staging")
    stage.mkdir(parents=True, exist_ok=False)
    for name in ("mesh.npz", "bundle.json", "framing.json"):
        if (base / name).exists():
            shutil.copy2(base / name, stage / name)
    np.save(stage / "region_id.npy", labels, allow_pickle=False)
    np.save(stage / "tangent.npy", tangent, allow_pickle=False)
    info["base_npz_sha256"] = before["mesh.npz"]
    info["source_cad_sha256"] = HERO_SHA256
    info["attribute_overrides"] = {name: {"path": name + ".npy", "sha256": sha256(stage / (name + ".npy"))}
                                   for name in ("region_id", "tangent")}
    (stage / "regions.json").write_text(json.dumps(info, sort_keys=True, indent=2, allow_nan=False) + "\n")
    (stage / "brep_faces.json").write_text(json.dumps(faces, sort_keys=True, indent=2, allow_nan=False) + "\n")
    debug_overlay(mesh["V"], mesh["F"], labels, stage / "regions_debug.png")
    debug_overlay_3q(mesh["V"], mesh["F"], labels, stage / "regions_debug_3q.png")
    from .region_io import apply_region_overrides
    applied = apply_region_overrides(mesh, stage / "regions.json", before["mesh.npz"])
    assert np.array_equal(applied["region_id"], labels)
    assert sha256(stage / "mesh.npz") == before["mesh.npz"]
    assert before == {p.name: sha256(p) for p in base.iterdir() if p.is_file()}, "production directory changed"
    (stage / "validation.json").write_text(json.dumps({"production_files_sha256": before, "production_unchanged": True,
        "npz_byte_identical": True, "labels_sha256": info["labels_sha256"], "art_review": "pending"}, indent=2) + "\n")
    stage.rename(out)
    return info


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publish B-rep regions v2 with a byte-identical production NPZ")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    info = write_regions_v2(args.bundle, args.out)
    print(json.dumps({"out": str(args.out), "labels_sha256": info["labels_sha256"], "area_mm2": info["area_mm2"]}))


if __name__ == "__main__":
    main()
