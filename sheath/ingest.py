"""CAD ingestion: knife STEP (+ STL tessellation) -> KnifeInterfaceV1 (planform, holes, thickness field, sharp edges, tip, ring).

Assumes the current jarambit/SWITCHBACK convention: part lies in the XY plane, thickness along Z, ring centre at origin.
For crescent genomes the same interface is filled from Pheno (outline, holes, edge_in, edge_sp, tip) — see plan §6.1.
"""
import hashlib, json, math
import numpy as np


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def step_props(step_path):
    """Volume/bbox from the B-rep (OCC via CadQuery). Returns dict; mass at Ti-6Al-4V 4.43 g/cm3."""
    import cadquery as cq
    s = cq.importers.importStep(step_path).val()
    bb = s.BoundingBox()
    return {"volume_mm3": s.Volume(), "mass_g_ti64": s.Volume() * 4.43e-3, "n_solids": len(cq.Workplane().add(s).solids().vals()),
            "bbox": [[bb.xmin, bb.ymin, bb.zmin], [bb.xmax, bb.ymax, bb.zmax]]}


def planform(mesh):
    """Union of +z-facing triangles projected to XY -> shapely Polygon (with holes)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    up = mesh.face_normals[:, 2] > 1e-6
    tris = mesh.vertices[mesh.faces[up]][:, :, :2]
    P = unary_union([Polygon(t) for t in tris if abs((t[1][0]-t[0][0])*(t[2][1]-t[0][1])-(t[1][1]-t[0][1])*(t[2][0]-t[0][0])) > 1e-9])
    if P.geom_type != "Polygon":
        P = max(P.geoms, key=lambda g: g.area)
    return P.buffer(0.01).buffer(-0.01).simplify(0.02)


def thickness_at(mesh, xy):
    """Through-thickness at XY points by ray casting (+z from below)."""
    xy = np.asarray(xy, float)
    z0 = mesh.bounds[0][2] - 1.0
    origins = np.c_[xy, np.full(len(xy), z0)]
    dirs = np.tile([0, 0, 1.0], (len(xy), 1))
    loc, idx, _ = mesh.ray.intersects_location(origins, dirs, multiple_hits=True)
    t = np.zeros(len(xy))
    if len(idx):
        for i in np.unique(idx):
            z = loc[idx == i][:, 2]
            t[i] = z.max() - z.min()
    return t


def sharp_edges(mesh, P, step=0.5, probe=0.6, t_sharp=1.0):
    """Boundary samples whose thickness `probe` mm inward is < t_sharp -> sharpened (ground to ~0 edge width)."""
    ring = P.exterior
    n = int(ring.length / step)
    pts = np.array([ring.interpolate(i * step).coords[0] for i in range(n)])
    tang = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
    nrm = np.c_[-tang[:, 1], tang[:, 0]]
    nrm /= np.linalg.norm(nrm, axis=1)[:, None] + 1e-12
    from shapely.geometry import Point
    # make normals point inward
    test = pts + nrm * probe
    inside = np.array([P.contains(Point(q)) for q in test])
    nrm[~inside] *= -1
    t = thickness_at(mesh, pts + nrm * probe)
    return pts, t, t < t_sharp


def ingest(step_path, stl_path):
    import trimesh
    mesh = trimesh.load(stl_path, force="mesh")
    P = planform(mesh)
    pts, t_probe, sharp = sharp_edges(mesh, P)
    holes = []
    for r in P.interiors:
        from shapely.geometry import Polygon
        h = Polygon(r); c = h.centroid
        holes.append({"centroid": [c.x, c.y], "area_mm2": h.area, "eq_radius_mm": math.sqrt(h.area / math.pi)})
    ring = max(holes, key=lambda h: h["area_mm2"])
    # tip: boundary point farthest from ring centre (always a hazard, sharp-ground or not)
    d = np.linalg.norm(pts - np.array(ring["centroid"]), axis=1)
    tip = pts[np.argmax(d)]
    sharp = sharp | (np.linalg.norm(pts - tip, axis=1) < 6.0)   # tip zone (6 mm) joins the hazard set
    # sharpened runs (contiguous)
    runs, cur = [], []
    for i, s in enumerate(sharp):
        if s: cur.append(i)
        elif cur: runs.append(cur); cur = []
    if cur:
        if runs and runs[0][0] == 0: runs[0] = cur + runs[0]
        else: runs.append(cur)
    runs = [r for r in runs if len(r) * 0.5 >= 3.0]
    grid_x = np.linspace(P.bounds[0], P.bounds[2], 120)
    tmax = float(mesh.bounds[1][2] - mesh.bounds[0][2])
    out = {
        "schema": "jarambit.sheath.knife_interface.v1",
        "source": {"step": step_path, "step_sha256": sha256(step_path), "stl": stl_path, "stl_sha256": sha256(stl_path)},
        "units": "mm", "frame": "part XY plane, thickness Z, ring centre ~origin",
        "stl_volume_mm3": float(mesh.volume), "stl_watertight": bool(mesh.is_watertight),
        "t_max_mm": tmax,
        "planform": {"exterior": [list(c) for c in P.exterior.coords], "interiors": [[list(c) for c in r.coords] for r in P.interiors],
                     "area_mm2": P.area, "bounds": list(P.bounds)},
        "holes": holes, "ring": ring, "tip": tip.tolist(),
        "sharp_runs": [{"n": len(r), "length_mm": 0.5 * len(r), "pts": pts[r].tolist()} for r in runs],
        "sharp_total_mm": float(0.5 * sharp.sum()),
        "review_status": "AUTO — annotations proposed, human review required before safety use",
    }
    try:
        out["brep"] = step_props(step_path)
    except Exception as e:  # pragma: no cover
        out["brep"] = {"status": "failed", "reason": repr(e)}
    return out, mesh, P
