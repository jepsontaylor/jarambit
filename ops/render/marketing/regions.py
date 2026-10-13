"""Deterministic surface labels and finish directions; no geometry edits.

The fallback assumes a predominantly planar product whose smallest PCA axis
is Z. Labels are appearance segmentation, not a claim about manufactured CAD.
"""
from __future__ import annotations

import hashlib

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


def classify(V, F, face_id=None, surface_types=None, tags=None, analysis=None):
    """Return region_id, tangent, uv and the frozen regions.json record.

    `tags` maps zero-based face IDs to label names or integer IDs. Partial
    tags override B-rep/heuristic results only for the named faces.
    """
    V, F = np.asarray(V), np.asarray(F)
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
